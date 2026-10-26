using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Linq;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    // This exception means the review is incomplete, never that its route was
    // proved unsafe. Catch it at the review boundary, preserving accepted jobs.
    public sealed class CombatReviewDeferredException : Exception
    {
        public CombatReviewDeferredException(string reason) : base(reason) {}
    }

    public static class CombatPathBudgetHelper
    {
        public const int MaximumNodes=4096;
        // Reserve cleanup/return time inside the declared25ms whole-pass goal.
        private const double WorkMilliseconds=22d;
        private sealed class Review : IDisposable
        {
            public readonly string Name;
            public readonly int Limit;
            public readonly long Start=Stopwatch.GetTimestamp();
            public int Searches,Checks,Deferred;
            public Review(string name,int limit){Name=name;Limit=limit;}
            public double Milliseconds=>(Stopwatch.GetTimestamp()-Start)*1000d/Stopwatch.Frequency;
            public void Dispose()
            {
                if(active!=this)return;
#if LAYA_COMBAT_LAB
                reviews++;searches+=Searches;checks+=Checks;deferrals+=Deferred;
                maxSearches=Math.Max(maxSearches,Searches);maxMs=Math.Max(maxMs,Milliseconds);
                if((Deferred>0 || Milliseconds>25) && Events.Count<128)
                    Events.Add(new{tick=Find.TickManager?.TicksGame,name=Name,caller_queries=Searches,
                        limit=Limit,checks=Checks,deferred=Deferred,ms=Milliseconds,outstanding});
#endif
                active=null;
            }
        }
        private sealed class Nested : IDisposable {public void Dispose(){}}
        [ThreadStatic] private static Review active;
        [ThreadStatic] private static int criticalSafetyDepth;
        private sealed class Safety : IDisposable
        {public Safety(){criticalSafetyDepth++;}public void Dispose(){criticalSafetyDepth--;}}
        public static IDisposable CriticalSafety()=>new Safety();
        private static readonly IDisposable nested=new Nested();
        public static IDisposable Begin(string name,int limit)
            =>active==null?(IDisposable)(active=new Review(name,limit)):nested;
        public static bool Exhausted=>active!=null && (active.Searches>=active.Limit || criticalSafetyDepth==0 && active.Milliseconds>=WorkMilliseconds);
        public static void Checkpoint(string phase="geometry")
        {
            if(active==null)return;
            active.Checks++;
            if(!Exhausted)return;
            active.Deferred++;
            throw new CombatReviewDeferredException("BudgetDeferred:"+phase);
        }
        // Pure data. IDisposable only keeps existing lexical using statements
        // compatible; this object owns no native resource and has no conversion
        // to PawnPath. In particular its node array cannot alias a pooled path.
        public sealed class Observation : IDisposable
        {
            public readonly bool Found;
            public readonly float TotalCost;
            public readonly ReadOnlyCollection<IntVec3> NodesReversed;
            public int NodesLeftCount=>NodesReversed.Count;
            internal Observation(bool found,float cost,IEnumerable<IntVec3> nodes)
            {Found=found;TotalCost=cost;NodesReversed=Array.AsReadOnly(nodes.ToArray());}
            public void Dispose(){}
        }
        private static int outstanding;
        public static Observation Borrowed(PawnPath path)
        {
            // A pather's current path belongs to the game. Copy without changing
            // its cursor or returning it to the pool.
            if(path==null || !path.Found)return new Observation(false,float.PositiveInfinity,Array.Empty<IntVec3>());
            if(path.NodesLeftCount>MaximumNodes)throw new CombatReviewDeferredException("RouteIncomplete:borrowed_too_long");
            return new Observation(true,path.TotalCost,path.NodesReversed.Take(path.NodesLeftCount));
        }
        public static Observation Query(Pawn pawn,IntVec3 start,LocalTargetInfo target,PathEndMode mode,int maximumNodes=MaximumNodes)
        {
            if(maximumNodes<1 || maximumNodes>MaximumNodes)throw new ArgumentOutOfRangeException(nameof(maximumNodes));
            Checkpoint("native_path");
            if(active!=null)active.Searches++;
            PawnPath native=null;
            try
            {
                native=pawn.Map.pathFinder.FindPathNow(start,target,pawn,null,mode);
                if(native==null || ReferenceEquals(native,PawnPath.NotFound))
                    return new Observation(false,float.PositiveInfinity,Array.Empty<IntVec3>());
                outstanding++;
#if LAYA_COMBAT_LAB
                acquired++;maxOutstanding=Math.Max(maxOutstanding,outstanding);
                TestLastNativeIdentity=System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(native);
#endif
                if(!native.Found)return new Observation(false,float.PositiveInfinity,Array.Empty<IntVec3>());
                if(native.NodesReversed.Count>maximumNodes)
                    throw new CombatReviewDeferredException("RouteIncomplete:owned_too_long");
                var result=new Observation(true,native.TotalCost,native.NodesReversed);
#if LAYA_COMBAT_LAB
                if(TestThrowAfterCopy)throw new InvalidOperationException("Declared native path ownership exception");
#endif
                return result;
            }
            finally
            {
                if(native!=null && !ReferenceEquals(native,PawnPath.NotFound))
                {
                    native.ReleaseToPool();outstanding--;
#if LAYA_COMBAT_LAB
                    released++;
#endif
                }
            }
        }
#if LAYA_COMBAT_LAB
        public static bool TestThrowAfterCopy;
        public static int TestLastNativeIdentity;
        public static int TestOutstanding=>outstanding;
        private static int reviews,searches,checks,deferrals,maxSearches,acquired,released,maxOutstanding;
        private static double maxMs;
        private static readonly List<object> Events=new List<object>();
        public static object Diagnostics()=>new{reviews,caller_queries=searches,checks,budget_deferrals=deferrals,
            max_scope_queries=maxSearches,max_scope_ms=maxMs,owned_acquired=acquired,owned_released=released,
            owned_outstanding=outstanding,max_owned_outstanding=maxOutstanding,events=Events.ToArray(),
            meaning="Owned native paths released before Query returns; observations contain detached data only. Borrowed engine paths are never released here."};
#endif
    }
}
