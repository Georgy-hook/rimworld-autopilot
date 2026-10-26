using System;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using RimWorld;
using Verse;

namespace RIMAPI.Helpers
{
    // A carried ally is absent from AllPawnsSpawned, but may be dropped into
    // the flight of a second gun's already launched projectile. Coordinate
    // terminal bursts; never alter projectiles or cancel a native burst.
    public static class CombatCarrierVolleyHelper
    {
        private static readonly FieldInfo Intended=typeof(Projectile).GetField("intendedTarget",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);
        public static bool BindingsAvailable=>Intended!=null && Intended.FieldType==typeof(LocalTargetInfo);
#if LAYA_COMBAT_LAB
        private static readonly List<object> Holds=new List<object>();
        public static object Diagnostics()=>new{bindings_available=BindingsAvailable,holds=Holds.ToArray()};
        public static void Reset()=>Holds.Clear();
        public static void Record(Pawn actor,Pawn carrier,string reason,int[] pending,int? leader)
        {
            if(Holds.Count<128)Holds.Add(new{tick=Find.TickManager.TicksGame,actor=actor.thingIDNumber,carrier=carrier.thingIDNumber,
                captive=(carrier.carryTracker?.CarriedThing as Pawn)?.thingIDNumber,
                health=carrier.health.summaryHealth.SummaryHealthPercent,reason,pending_projectiles=pending,other_gun=leader,
                meaning="Deferred an unfired terminal burst while another real volley is committed. Existing projectiles/bursts remain native."});
        }
#endif
        public static bool ShouldHold(Pawn actor,Pawn carrier,out string reason,out int[] pending,out int? leader)
        {
            reason=null;pending=new int[0];leader=null;
            if(!BindingsAvailable || !(carrier?.carryTracker?.CarriedThing is Pawn captive) || captive.Faction!=Faction.OfPlayer
                || carrier.Dead || carrier.Downed || carrier.health.summaryHealth.SummaryHealthPercent>.55f)return false;
            pending=actor.Map.listerThings.ThingsInGroup(ThingRequestGroup.Projectile).OfType<Projectile>()
                .Where(p=>!p.Destroyed && p.Launcher is Pawn shooter && shooter.Faction==Faction.OfPlayer
                    && ((LocalTargetInfo)Intended.GetValue(p)).Thing==carrier).Take(64).Select(p=>p.thingIDNumber).ToArray();
            if(pending.Length>0){reason="terminal_projectiles_in_flight";return true;}
            var own=actor.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(own==null)return false;
            var ownWarmup=actor.stances.curStance as Stance_Warmup;
            float ownDelay=ownWarmup?.verb==own && ownWarmup.focusTarg.Thing==carrier ? ownWarmup.ticksLeft
                :CombatInterceptHelper.MovementLockTicks(actor)+own.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor);
            foreach(var gun in actor.Map.mapPawns.FreeColonistsSpawned.Where(p=>p!=actor && !p.Dead && !p.Downed && p.Drafted
                && !CombatNativeHelper.Protected(p) && !CareTriageHelper.QueuedCare(p)))
            {
                var verb=gun.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
                if(verb==null || verb.IsMeleeAttack || CombatControlHelper.AimTarget(gun)!=carrier
                    || !CombatInterceptHelper.CanShootNow(gun,carrier))continue;
                if(verb.state==VerbState.Bursting){leader=gun.thingIDNumber;reason="other_terminal_burst";return true;}
                var warmup=gun.stances.curStance as Stance_Warmup;
                if(warmup?.verb==verb && warmup.focusTarg.Thing==carrier
                    && (warmup.ticksLeft<ownDelay || warmup.ticksLeft==ownDelay && gun.thingIDNumber<actor.thingIDNumber))
                {leader=gun.thingIDNumber;reason="earlier_terminal_warmup";return true;}
            }
            return false;
        }
    }
}
