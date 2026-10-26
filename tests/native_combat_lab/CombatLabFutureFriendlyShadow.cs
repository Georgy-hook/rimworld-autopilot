#if LAYA_COMBAT_LAB
// Bounded observation of the old bare-cell vs actual projected-Pawn body guard.
// The postfix never changes arguments, the selected line, return or RNG state.
using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Helpers;
namespace RIMAPI.Controllers
{
    [HarmonyPatch(typeof(CombatInterceptHelper),nameof(CombatInterceptHelper.FutureFriendlyLaneClear))]
    public static class CombatLabFutureFriendlyShadow
    {
        private static readonly List<object> Rows=new List<object>(),Failures=new List<object>();
        private static readonly HashSet<string> Seen=new HashSet<string>();
        private static int Calls,Checks,Skipped,RngChanges;private static double Milliseconds;
        public static void Reset(){Rows.Clear();Failures.Clear();Seen.Clear();Calls=Checks=Skipped=RngChanges=0;Milliseconds=0;}
        private static object[] Bodies(Pawn pawn,Pawn target,ShootLine line)=>pawn.Map.mapPawns.AllPawnsSpawned
            .Where(p=>p!=pawn && p!=target && !p.Dead
                && (!p.HostileTo(pawn) && !CombatNativeHelper.ActivePredation(p)
                    || pawn.Faction==Faction.OfPlayer && p.IsPrisonerOfColony)
                && VerbUtility.InterceptChanceFactorFromDistance(line.Source.ToVector3Shifted(),p.Position)>0f
                && CombatInterceptMath.InterveningAlly(line.Source.x,line.Source.z,line.Dest.x,line.Dest.z,p.Position.x,p.Position.z,
                    CombatInterceptMath.FriendlyBodyRadius(p.BodySize),1f))
            .Select(p=>(object)new{id=p.thingIDNumber,x=p.Position.x,z=p.Position.z,downed=p.Downed,job=p.CurJobDef?.defName}).ToArray();
        public static void Postfix(Pawn pawn,Pawn target,IntVec3 from,IntVec3 future,string phase,bool __result)
        {
            Calls++;
            if(pawn?.Map!=CombatLabState.Map || Checks>=2048 || Rows.Count>=128){Skipped++;return;}
            string key=phase+":"+pawn.thingIDNumber+":"+target.thingIDNumber+":"+from+":"+future+":"+(Find.TickManager.TicksGame/60);
            if(!Seen.Add(key)){Skipped++;return;}
            var started=System.Diagnostics.Stopwatch.StartNew();
            string before=CombatLabState.RandomProperty.GetValue(null,null).ToString();
            try
            {
                Checks++;
                bool old=CombatInterceptHelper.FriendlyLaneClear(pawn,new LocalTargetInfo(future),from);
                if(old==__result)return;
                var verb=pawn.equipment.Primary.TryGetComp<CompEquippable>().PrimaryVerb;
                bool oldNative=verb.TryFindShootLineFromTo(from,new LocalTargetInfo(future),out var oldLine);
                bool newNative=CombatExposureHelper.TryPawnShootLine(verb,target,from,future,out var newLine)==true;
                Rows.Add(new{phase,tick=Find.TickManager.TicksGame,actor=pawn.thingIDNumber,target=target.thingIDNumber,
                    from_x=from.x,from_z=from.z,future_x=future.x,future_z=future.z,
                    old_result=old,actual_result=__result,old_native_line=oldNative,projected_pawn_native_line=newNative,
                    old_source_x=oldLine.Source.x,old_source_z=oldLine.Source.z,old_dest_x=oldLine.Dest.x,old_dest_z=oldLine.Dest.z,
                    new_source_x=newLine.Source.x,new_source_z=newLine.Source.z,new_dest_x=newLine.Dest.x,new_dest_z=newLine.Dest.z,
                    old_intervening_bodies=oldNative?Bodies(pawn,target,oldLine):new object[0],
                    new_intervening_bodies=newNative?Bodies(pawn,target,newLine):new object[0],
                    actor_x=pawn.Position.x,actor_z=pawn.Position.z,job=pawn.CurJobDef?.defName,
                    mode=CombatControlHelper.TestMode(pawn),plan_target=CombatControlHelper.TestTarget(pawn),
                    interpretation="Observed difference in the actual predicate; this postfix never selects an alternative outcome"});
            }
            catch(Exception e){if(Failures.Count<10)Failures.Add(new{tick=Find.TickManager.TicksGame,error=e.ToString()});}
            finally
            {
                if(before!=CombatLabState.RandomProperty.GetValue(null,null).ToString())RngChanges++;
                Milliseconds+=started.Elapsed.TotalMilliseconds;
            }
        }
        public static object State(bool full)=>new{available=true,calls=Calls,checks=Checks,check_cap=2048,skipped=Skipped,
            row_cap=128,recorded=Rows.Count,rng_changes=RngChanges,total_ms=Milliseconds,errors=Failures.Count,
            rows=full?Rows.ToArray():new object[0],failures=Failures.ToArray(),
            scope="Read-only LAB Harmony postfix; identical production binary, no return/arguments/RNG/pawn/stat/physics changes"};
    }
}
#endif
