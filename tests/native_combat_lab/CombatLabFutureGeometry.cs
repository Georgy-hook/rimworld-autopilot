#if LAYA_COMBAT_LAB
// Diagnostic-only comparison at the existing prediction decision. Never changes its result.
using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using RIMAPI.Helpers;

namespace RIMAPI.Controllers
{
    public static class CombatLabFutureGeometry
    {
        public const int PerPhaseLimit=256;
        private static readonly List<object> Rows=new List<object>();
        private static readonly List<object> FriendlyLines=new List<object>();
        private static readonly HashSet<string> FriendlySeen=new HashSet<string>();
        private static int CurrentLineMismatches;
        private static readonly HashSet<string> Seen=new HashSet<string>();
        private static readonly Dictionary<string,int> Counts=new Dictionary<string,int>();
        private static int Calls,Skipped,Mismatches,CurrentMismatches,Unknown,Errors;
        private static double Milliseconds;
        public static void Reset(){CombatCarrierInterceptHelper.ResetDiagnostics();CombatLabFutureFriendlyShadow.Reset();FriendlyLines.Clear();FriendlySeen.Clear();CurrentLineMismatches=0;Rows.Clear();Seen.Clear();Counts.Clear();Calls=Skipped=Mismatches=CurrentMismatches=Unknown=Errors=0;Milliseconds=0;}
        public static void Record(string phase,Pawn actor,Pawn target,Verb verb,IntVec3 from,IntVec3 future,
            float horizon,float observedUntil,bool originalCellResult,bool? selectedResult=null)
        {
            Calls++;
            if(actor?.Map==null || actor.Map!=CombatLabState.Map || target?.Map!=actor.Map
                || target.def.size.x!=1 || target.def.size.z!=1 || verb==null){Skipped++;return;}
            if(Counts.TryGetValue(phase,out var count) && count>=PerPhaseLimit){Skipped++;return;}
            string key=phase+":"+actor.thingIDNumber+":"+target.thingIDNumber+":"+from+":"+future+":"+target.Position;
            if(!Seen.Add(key))return;
            Counts[phase]=count+1;
            long start=System.Diagnostics.Stopwatch.GetTimestamp();
            try
            {
                bool? candidate=CombatExposureHelper.CanHitCandidate(verb,from,future,actor.Map);
                bool? currentCandidate=CombatExposureHelper.CanHitCandidate(verb,from,target.Position,actor.Map);
                bool currentPawn=verb.CanHitTargetFrom(from,target);
                bool nativeCurrentLine=verb.TryFindShootLineFromTo(from,target,out var nativeLine);
                bool? candidateCurrentLine=CombatExposureHelper.TryCandidateShootLine(verb,from,target.Position,actor.Map,out var candidateLine);
                bool currentLineMismatch=candidateCurrentLine.HasValue && (candidateCurrentLine.Value!=nativeCurrentLine
                    || nativeCurrentLine && (nativeLine.Source!=candidateLine.Source || nativeLine.Dest!=candidateLine.Dest));
                if(!candidate.HasValue || !currentCandidate.HasValue)Unknown++;
                bool mismatch=candidate.HasValue && candidate.Value!=originalCellResult;
                bool currentMismatch=currentCandidate.HasValue && currentCandidate.Value!=currentPawn;
                var rngBefore=CombatLabState.RandomProperty?.GetValue(null,null)?.ToString();
                float? futureScatter=null;
                if(verb.TryFindShootLineFromTo(from,new LocalTargetInfo(future),out var scatterLine))
                    futureScatter=CombatFriendlyFireHelper.MissRadius(actor,verb,new LocalTargetInfo(future),from,scatterLine,target);
                bool scatterRngUnchanged=rngBefore==CombatLabState.RandomProperty?.GetValue(null,null)?.ToString();
                if(mismatch)Mismatches++;
                if(currentMismatch)CurrentMismatches++;
                if(currentLineMismatch)CurrentLineMismatches++;
                Rows.Add(new{phase,tick=Find.TickManager.TicksGame,actor=actor.thingIDNumber,target=target.thingIDNumber,
                    from_x=from.x,from_z=from.z,target_x=target.Position.x,target_z=target.Position.z,
                    future_x=future.x,future_z=future.z,horizon,observed_until=observedUntil,
                    future_within_observed_route=horizon<=observedUntil,
                    future_maximum_endpoint_radius=futureScatter,future_scatter_rng_unchanged=scatterRngUnchanged,
                    original_cell_result=originalCellResult,candidate_pawn_result=candidate,
                    current_pawn_result=currentPawn,current_candidate_result=currentCandidate,
                    future_form_mismatch=mismatch,current_geometry_mismatch=currentMismatch,
                    current_line_mismatch=currentLineMismatch,native_current_line_result=nativeCurrentLine,
                    reconstructed_current_line_result=candidateCurrentLine,
                    native_line_source_x=nativeLine.Source.x,native_line_source_z=nativeLine.Source.z,
                    native_line_dest_x=nativeLine.Dest.x,native_line_dest_z=nativeLine.Dest.z,
                    candidate_line_source_x=candidateLine.Source.x,candidate_line_source_z=candidateLine.Source.z,
                    candidate_line_dest_x=candidateLine.Dest.x,candidate_line_dest_z=candidateLine.Dest.z,
                    returned_control_result=selectedResult??originalCellResult,
                    returned_original_cell_result=!selectedResult.HasValue || selectedResult.Value==originalCellResult,
                    control_uses_future_pawn_geometry=selectedResult.HasValue});
            }
            catch(Exception error){Errors++;Rows.Add(new{phase,tick=Find.TickManager.TicksGame,error=error.GetType().Name+": "+error.Message});}
            finally{Milliseconds+=(System.Diagnostics.Stopwatch.GetTimestamp()-start)*1000d/System.Diagnostics.Stopwatch.Frequency;}
        }
        public static void RecordFutureFriendlyLine(string phase,Pawn actor,Pawn target,Verb verb,IntVec3 from,IntVec3 future,ShootLine line)
        {
            if(actor.Map!=CombatLabState.Map || FriendlyLines.Count>=256
                || verb.TryFindShootLineFromTo(from,new LocalTargetInfo(future),out _))return;
            string key=phase+":"+actor.thingIDNumber+":"+target.thingIDNumber+":"+from+":"+future;
            if(!FriendlySeen.Add(key))return;
            FriendlyLines.Add(new{phase,tick=Find.TickManager.TicksGame,actor=actor.thingIDNumber,target=target.thingIDNumber,
                from_x=from.x,from_z=from.z,future_x=future.x,future_z=future.z,
                checked_source_x=line.Source.x,checked_source_z=line.Source.z,checked_dest_x=line.Dest.x,checked_dest_z=line.Dest.z,
                old_bare_cell_line=false,projected_pawn_line=true,current_friendly_bodies_clear=true,
                interpretation="This actual future-window check now retains its native Pawn line through the body guard; not a shot/hit or predicted ally motion"});
        }
        public static object State(bool includeRows)=>new{available=true,per_phase_limit=PerPhaseLimit,calls=Calls,skipped=Skipped,
            sampled=Rows.Count,phase_counts=Counts,future_form_mismatches=Mismatches,current_geometry_mismatches=CurrentMismatches,current_line_mismatches=CurrentLineMismatches,
            unknown=Unknown,errors=Errors,total_ms=Milliseconds,rows=includeRows?Rows.ToArray():new object[0],
            friendly_line_corrections=includeRows?FriendlyLines.ToArray():new object[0],
            meaning="Read-only bounded samples; returned_control_result records the actual predicate used. Future differences need actual-Pawn parity and known observed route. No pawn/stat/physics/RNG changes."};
    }
}
#endif
