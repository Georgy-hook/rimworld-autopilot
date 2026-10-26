using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    // A Pawn is a different native shooting target from an empty cell: both
    // shooter and target can lean. Do not move a real pawn to test a candidate.
    public static class CombatExposureHelper
    {
#if LAYA_COMBAT_LAB
        private static readonly List<string> BindingFailures=new List<string>();
        private static int CandidateReads,UnknownReads,NativeCellReads;
        private static double TotalMilliseconds,MaximumMilliseconds;
#endif
        private static T NativeMethod<T>(string name,params Type[] parameters) where T:class
        {
            try
            {
                var method=typeof(Verb).GetMethod(name,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance,
                    null,parameters,null);
                if(method==null)throw new MissingMethodException(typeof(Verb).FullName,name);
                // Cache a typed wrapper for public or private predicates. Its
                // body calls the loaded native method without object[] or
                // per-candidate reflection, stat changes or target movement.
                var invoke=typeof(T).GetMethod("Invoke");
                var signature=invoke.GetParameters();var arguments=new Type[signature.Length];
                for(int i=0;i<arguments.Length;i++)arguments[i]=signature[i].ParameterType;
                var wrapper=new DynamicMethod("LayaNative"+name,invoke.ReturnType,arguments,
                    typeof(CombatExposureHelper),true);
                var code=wrapper.GetILGenerator();
                for(int i=0;i<arguments.Length;i++)code.Emit(OpCodes.Ldarg,(short)i);
                code.Emit(OpCodes.Call,method);code.Emit(OpCodes.Ret);
                return wrapper.CreateDelegate(typeof(T)) as T;
            }
            catch(Exception error)
            {
                _=error;
#if LAYA_COMBAT_LAB
                BindingFailures.Add(name+": "+error.GetType().Name+": "+error.Message);
#endif
                return null;
            }
        }
        private static readonly Func<Verb,IntVec3,LocalTargetInfo,CellRect,bool> OutOfRange=
            NativeMethod<Func<Verb,IntVec3,LocalTargetInfo,CellRect,bool>>("OutOfRange",
                typeof(IntVec3),typeof(LocalTargetInfo),typeof(CellRect));
        private static readonly Func<Verb,IntVec3,IntVec3,bool,bool> HitCell=
            NativeMethod<Func<Verb,IntVec3,IntVec3,bool,bool>>("CanHitCellFromCellIgnoringRange",
                typeof(IntVec3),typeof(IntVec3),typeof(bool));

        // Same native Pawn branch as Verb.TryFindShootLineFromTo: root range,
        // root shot first, then native shooter lean and native target lean.
        // A changed/inaccessible native method is unknown, never safe cover.
        public static bool? CanHitCandidate(Verb verb,IntVec3 from,IntVec3 cell,Map map)
        {
#if LAYA_COMBAT_LAB
            long started=System.Diagnostics.Stopwatch.GetTimestamp();
            try
            {
                var result=Candidate(verb,from,cell,map);CandidateReads++;
                if(!result.HasValue)UnknownReads++;
                return result;
            }
            finally
            {
                double elapsed=(System.Diagnostics.Stopwatch.GetTimestamp()-started)*1000d/System.Diagnostics.Stopwatch.Frequency;
                TotalMilliseconds+=elapsed;MaximumMilliseconds=Math.Max(MaximumMilliseconds,elapsed);
            }
#else
            return Candidate(verb,from,cell,map);
#endif
        }
        private static bool? Candidate(Verb verb,IntVec3 from,IntVec3 cell,Map map)
            => TryCandidateShootLine(verb,from,cell,map,out _);

        // Return the same checked lean endpoints as the one-cell native Pawn
        // branch. Friendly-body checks must use this line, not switch back to
        // a bare cell target after the future Pawn geometry was accepted.
        public static bool? TryCandidateShootLine(Verb verb,IntVec3 from,IntVec3 cell,Map map,out ShootLine line)
        {
            line=new ShootLine(from,cell);
            if(verb==null || map==null || !from.InBounds(map) || !cell.InBounds(map)
                || OutOfRange==null || HitCell==null)return null;
            if(OutOfRange(verb,from,new LocalTargetInfo(cell),CellRect.SingleCell(cell)))return false;
            if(!verb.verbProps.requireLineOfSight)return true;
            var destinations=new List<IntVec3>(5);
            if(HitFrom(verb,from,cell,map,destinations,out var hit))
            {line=new ShootLine(from,hit);return true;}
            var sources=new List<IntVec3>(5);
            ShootLeanUtility.LeanShootingSourcesFromTo(from,cell,map,sources);
            foreach(var source in sources)
                if(HitFrom(verb,source,cell,map,destinations,out hit))
                {line=new ShootLine(source,hit);return true;}
            return false;
        }
        public static bool? TryPawnShootLine(Verb verb,Pawn target,IntVec3 from,IntVec3 cell,out ShootLine line)
        {
            line=new ShootLine(from,cell);var map=target?.Map;
            if(verb==null || map==null || !from.InBounds(map) || !cell.InBounds(map))return null;
            if(cell==target.Position)return verb.TryFindShootLineFromTo(from,new LocalTargetInfo(target),out line);
            if(target.def.size.x!=1 || target.def.size.z!=1)return null;
            return TryCandidateShootLine(verb,from,cell,map,out line);
        }
        // Preserve the native Thing target at its actual position. At an
        // observed future position use the validated one-cell Pawn branch,
        // including target lean; an empty LocalTargetInfo(cell) is different.
        // Unsupported footprints/bindings remain unknown to each caller.
        public static bool? CanHitPawnAt(Verb verb,Pawn target,IntVec3 from,IntVec3 cell)
        {
            var map=target?.Map;
            if(verb==null || map==null || !from.InBounds(map) || !cell.InBounds(map))return null;
            if(cell==target.Position)return verb.CanHitTargetFrom(from,new LocalTargetInfo(target));
            if(target.def.size.x!=1 || target.def.size.z!=1)return null;
            return CanHitCandidate(verb,from,cell,map);
        }
        private static bool HitFrom(Verb verb,IntVec3 from,IntVec3 cell,Map map,List<IntVec3> destinations,out IntVec3 hit)
        {
            hit=cell;
            ShootLeanUtility.LeanShootingSourcesFromTo(cell,from,map,destinations);
            foreach(var destination in destinations)
            {
#if LAYA_COMBAT_LAB
                NativeCellReads++;
#endif
                if(HitCell(verb,from,destination,false)){hit=destination;return true;}
            }
            return false;
        }
#if LAYA_COMBAT_LAB
        public static object Diagnostics()=>new{range_binding=OutOfRange!=null,cell_binding=HitCell!=null,
            binding_failures=BindingFailures.ToArray(),candidate_reads=CandidateReads,unknown_reads=UnknownReads,
            native_cell_reads=NativeCellReads,total_ms=TotalMilliseconds,max_ms=MaximumMilliseconds};
#endif
        public static float Lane(Pawn threat,Pawn target,IntVec3 cell,IntVec3 from)
        {
            var map=target?.Map;
            var verb=threat?.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null || map==null || map!=threat.Map || !cell.InBounds(map))return float.PositiveInfinity;
            bool? hit;
            LocalTargetInfo nativeTarget;
            if(cell==target.Position)
            {
                nativeTarget=new LocalTargetInfo(target);
                hit=verb.CanHitTargetFrom(from,nativeTarget);
            }
            else
            {
                // Multi-cell future footprints need their own native model.
                if(target.def.size.x!=1 || target.def.size.z!=1)return float.PositiveInfinity;
                nativeTarget=new LocalTargetInfo(cell);
                hit=CanHitCandidate(verb,from,cell,map);
            }
            if(!hit.HasValue)return float.PositiveInfinity;
            if(!hit.Value)return 0f;
            return target.def.CanBenefitFromCover
                ?Math.Max(0f,1f-CoverUtility.CalculateOverallBlockChance(nativeTarget,from,map)):1f;
        }
    }
}
