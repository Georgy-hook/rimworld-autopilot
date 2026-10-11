using System;
using System.Linq;
using System.Collections.Generic;
using RimWorld;
using Verse;
using Verse.AI;
using Verse.AI.Group;
using RIMAPI.Models;
namespace RIMAPI.Helpers
{
    public static class CombatNativeHelper
    {
        public static bool PredationIntent(bool dead, bool downed, string job, bool playerPrey) => !dead && !downed && job == "PredatorHunt" && playerPrey;
        public static bool ActivePredation(Pawn pawn) => pawn != null && PredationIntent(pawn.Dead, pawn.Downed,
            pawn.CurJobDef?.defName, pawn.CurJob?.targetA.Thing is Pawn prey && prey.Faction == Faction.OfPlayer);
        public static bool IsPlayerThreat(Pawn pawn) => pawn != null
            && (pawn.HostileTo(Faction.OfPlayer) || ActivePredation(pawn));
        private static readonly HashSet<string> Care=new HashSet<string>{"TendPatient","Rescue","FeedPatient","DoBill","Deathrest","Breastfeed","BottleFeedBaby","BreastfeedCarryToMom","BringBabyToSafety","BringBabyToSafetyUnforced","CarryToMomAfterBirth","BabySuckle","BabyPlay","PlayStatic","PlayWalking","PlayToys","Lessongiving","Lessonreceiving","PrisonerInterrogateIdentity"};
        private static readonly Dictionary<int, KeyValuePair<Pawn, Job>> CareRetreats = new Dictionary<int, KeyValuePair<Pawn, Job>>();
        public static void RememberCareRetreat(Pawn pawn, Job job) =>
            CareRetreats[pawn.thingIDNumber] = new KeyValuePair<Pawn, Job>(pawn, job);
        public static bool HasCareRetreat(Pawn pawn) => pawn != null && !pawn.Dead && !pawn.Downed
            && !pawn.InMentalState && pawn.Spawned && Find.Maps.Contains(pawn.Map)
            && pawn.CurJobDef == JobDefOf.Goto && CareRetreats.TryGetValue(pawn.thingIDNumber, out var record)
            && record.Key == pawn && record.Value == pawn.CurJob;
        public static List<int> CareRetreatPawnIds(Map map)
        {
            foreach (int id in CareRetreats.Keys.ToList())
                if (!HasCareRetreat(CareRetreats[id].Key)) CareRetreats.Remove(id);
            return map.mapPawns.FreeColonistsSpawned.Where(HasCareRetreat).Select(p => p.thingIDNumber).ToList();
        }
        public static bool HasCareJob(Pawn pawn) => HasCareRetreat(pawn) || Care.Contains(pawn.CurJobDef?.defName ?? "");
        public static bool HasClinicalCareJob(Pawn pawn) => pawn.CurJobDef == JobDefOf.TendPatient
            || pawn.CurJobDef == JobDefOf.Rescue || pawn.CurJobDef == JobDefOf.FeedPatient;
        public static bool ImmediateCareThreat(Pawn pawn, Thing enemy)
        {
            if (enemy == null || enemy.Destroyed || !enemy.Spawned || enemy.Map != pawn.Map
                || !(enemy is Pawn threat ? IsPlayerThreat(threat) : enemy.HostileTo(Faction.OfPlayer))
                || enemy.Position.Fogged(pawn.Map)) return false;
            if (enemy is Building_Turret turret)
                return ActiveStructure(turret) && turret.AttackVerb.CanHitTarget(pawn);
            if (!(enemy is Pawn attacker) || attacker.Dead || attacker.Downed) return false;
            if (enemy.Position.InHorDistOf(pawn.Position, 7f)) return true;
            Verb verb = attacker.CurrentEffectiveVerb;
            return verb != null && !verb.IsMeleeAttack && verb.Available() && verb.CanHitTarget(pawn);
        }
        public static Thing CareTarget(Pawn pawn)
        {
            Job job = pawn.CurJob;
            if (job == null || !HasCareJob(pawn)) return null;
            if (job.def == JobDefOf.FeedPatient) return job.targetB.Thing;
            string name = job.def.defName;
            if (name.IndexOf("Baby", StringComparison.OrdinalIgnoreCase) >= 0
                || name.IndexOf("Breastfeed", StringComparison.OrdinalIgnoreCase) >= 0)
                return pawn.carryTracker?.CarriedThing as Pawn ?? job.targetA.Thing as Pawn
                    ?? job.targetB.Thing as Pawn ?? job.targetC.Thing as Pawn;
            return job.targetA.Thing;
        }
        public static bool CareAtBedside(Pawn pawn)
        {
            if (!HasCareJob(pawn)) return false;
            if (pawn.carryTracker?.CarriedThing is Pawn) return true;
            Thing target = CareTarget(pawn);
            if (target != null && target.Spawned && target.Map == pawn.Map)
                return pawn.Position.InHorDistOf(target.Position, 2f);
            return (pawn.CurJobDef?.defName ?? "") == "Deathrest";
        }
        public static bool Protected(Pawn pawn)
        {
            // Generic group tactics cannot borrow a doctor even at contact.
            // Only an exact, freshly checked caregiver_retreat order can suspend care.
            if (HasClinicalCareJob(pawn) || HasCareRetreat(pawn)) return true;
            if (!HasCareJob(pawn)) return false;
            List<Pawn> threats = pawn.Map.mapPawns.AllPawnsSpawned
                .Where(e => !e.Dead && !e.Downed && IsPlayerThreat(e)).ToList();
            if (threats.Any(e => e.Position.InHorDistOf(pawn.Position, 4f))) return false;
            if (pawn.Map.listerBuildings.allBuildingsNonColonist.Any(b => ActiveStructure(b)
                && b.Position.InHorDistOf(pawn.Position, 4f))) return false;
            // Other care-like work may still be traveling to a remote target.
            // Clinical care and its exact escape job already returned above.
            if (!CareAtBedside(pawn) && (threats.Any(e => e.Position.InHorDistOf(pawn.Position,
                Math.Max(22f, Math.Min(55f, (e.equipment?.Primary?.def?.Verbs?.FirstOrDefault()?.range ?? 0f) + 8f))))
                || pawn.Map.listerBuildings.allBuildingsNonColonist.Any(b => ActiveStructure(b)
                    && b.Position.InHorDistOf(pawn.Position,
                        Math.Max(22f, Math.Min(55f, (b.def.Verbs?.FirstOrDefault()?.range ?? 0f) + 8f))))))
                return false;
            return true;
        }
        public static bool Kidnapper(Pawn pawn) => pawn.carryTracker?.CarriedThing is Pawn victim && victim.Faction==Faction.OfPlayer
            && (pawn.CurJobDef?.defName.IndexOf("Kidnap",StringComparison.OrdinalIgnoreCase)>=0 || pawn.GetLord()?.LordJob?.GetType().Name.IndexOf("Kidnap",StringComparison.OrdinalIgnoreCase)>=0);
        public static bool ActiveStructure(Thing thing) => thing is Building_Turret turret && !thing.Destroyed && thing.HostileTo(Faction.OfPlayer)
            && (thing.TryGetComp<CompCanBeDormant>()?.Awake ?? true) && (thing.TryGetComp<CompPowerTrader>()?.PowerOn ?? true)
            && (thing.TryGetComp<CompInitiatable>()?.Initiated ?? true) && turret.AttackVerb!=null;
        private static IEnumerable<Thing> Targets(Map map) => map.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && !p.Downed && IsPlayerThreat(p) && !p.Position.Fogged(map)).Cast<Thing>()
            .Concat(map.listerBuildings.allBuildingsNonColonist.Where(b=>!b.Destroyed && b.HostileTo(Faction.OfPlayer) && !b.Position.Fogged(map) && ActiveStructure(b)).Cast<Thing>());
        private static bool Fighter(Pawn pawn) => !pawn.Dead && !pawn.Downed && !pawn.InMentalState && !pawn.WorkTagIsDisabled(WorkTags.Violent) && !Protected(pawn);
        private static Dictionary<string,string> Effects(string benefit,string risk,string cost,string uncertainty)=>new Dictionary<string,string>{{"benefit",benefit},{"risk",risk},{"cost",cost},{"inaction","Hostile attacks/coverage persist; ordinary defense may suffice"},{"uncertainty",uncertainty}};
        private static bool FriendlyBlastSafe(Map map,Pawn shooter,Thing target,float radius) => !(target is Pawn carrier && carrier.carryTracker?.CarriedThing is Pawn carried && carried.Faction==Faction.OfPlayer) && !map.mapPawns.AllPawnsSpawned.Any(p=>p!=shooter && p.Faction==Faction.OfPlayer && p.Position.InHorDistOf(target.Position,radius));
        public static List<CombatNativeOptionDto> Options(Map map)
        {
            var result=new List<CombatNativeOptionDto>();var targets=Targets(map).ToList();
            foreach (Pawn caregiver in map.mapPawns.FreeColonistsSpawned.Where(p => !p.Dead && !p.Downed
                && !p.InMentalState && HasClinicalCareJob(p) && !(p.carryTracker?.CarriedThing is Pawn)))
            {
                Pawn patient = CareTarget(caregiver) as Pawn;
                Thing attacker = targets.Where(e => ImmediateCareThreat(caregiver, e))
                    .OrderBy(e => caregiver.Position.DistanceToSquared(e.Position)).FirstOrDefault();
                if (patient == null || attacker == null) continue;
                result.Add(new CombatNativeOptionDto { Tactic = "caregiver_retreat", FighterId = caregiver.thingIDNumber,
                    TargetId = attacker.thingIDNumber, ExpectedCurrentJob = caregiver.CurJobDef.defName,
                    ExpectedCarePatientId = patient.thingIDNumber,
                    Label = $"{caregiver.LabelShort}: suspend {caregiver.CurJobDef.defName} for {patient.LabelShort} and escape {attacker.LabelShort}",
                    Effects = Effects("Preserve this caregiver from an immediate attacker through a checked normal retreat job",
                        $"Patient {patient.LabelShort} loses current care; bleed={patient.health.hediffSet.BleedRateTotal:0.00}; rescue/feeding/treatment may be delayed",
                        $"Only {caregiver.LabelShort}'s exact current care is interrupted; remaining caregivers keep their jobs",
                        "Route is checked before suspension; escape and patient survival are not guaranteed") });
            }
            foreach(Pawn pawn in map.mapPawns.FreeColonistsSpawned.Where(Fighter))
            {
                Verb verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
                var projectile=verb?.verbProps.defaultProjectile?.projectile;
                bool emp=projectile?.damageDef==DamageDefOf.EMP;
                bool smoke=projectile?.postExplosionGasType==GasType.BlindSmoke;
                if(verb!=null && (emp || smoke) && verb.Available())
                foreach(Thing target in targets.Where(t=>emp ? (t is Pawn mech && mech.RaceProps.IsMechanoid) || t is Building_Turret || t.def.defName.IndexOf("Shield",StringComparison.OrdinalIgnoreCase)>=0 : t is Building_Turret))
                    if(verb.CanHitTarget(target) && (smoke || FriendlyBlastSafe(map,pawn,target,projectile.explosionRadius+2f)))
                        result.Add(new CombatNativeOptionDto{Tactic=emp ? "emp_control" : "smoke_advance",FighterId=pawn.thingIDNumber,TargetId=target.thingIDNumber,
                            Label=$"{pawn.LabelShort}: {pawn.equipment.Primary.LabelShort} at {target.LabelShort}",Effects=Effects($"{target.LabelShort}: {(emp ? "native EMP stun/control" : "native smoke blocks turret sight")}",emp ? "EMP adaptation, resistance and friendly implant/mech stun; not health damage" : "Smoke also blocks allied sight; melee/overhead fire not neutralized",$"{pawn.LabelShort} firing time; actual equipped weapon",emp ? "Stun can fail/adapt; conventional damage still required" : "Gas disperses; only native sight rules apply")});
                if(!emp && !smoke)
                foreach(Thing target in targets.Where(t=>t is Building))
                {
                    bool ranged=verb!=null && !verb.IsMeleeAttack;
                    if(ranged ? verb.Available() && verb.CanHitTarget(target) && FriendlyBlastSafe(map,pawn,target,(projectile?.explosionRadius ?? 0f)+2f)
                        : pawn.CanReserveAndReach(target,PathEndMode.Touch,Danger.Deadly))
                        result.Add(new CombatNativeOptionDto{Tactic="attack_structure",FighterId=pawn.thingIDNumber,TargetId=target.thingIDNumber,Label=$"{pawn.LabelShort}: attack {target.LabelShort}",
                            Effects=Effects($"Hostile {target.LabelShort}; HP={target.HitPoints}/{target.MaxHitPoints}","Static turret fire/explosion; route and friendly fire risk",$"{pawn.LabelShort} {(ranged ? "weapon fire" : "melee exposure")}","Shield/power/dormancy and destruction effects remain native")});
                }
                foreach(var mortar in map.listerBuildings.allBuildingsColonist.OfType<Building_TurretGun>().Where(t=>t.def.building.IsMortar && !t.Position.Roofed(map)))
                {
                    var man=mortar.TryGetComp<CompMannable>();var ammunition=mortar.gun?.TryGetComp<CompChangeableProjectile>();
                    if(man==null || (man.MannedNow && man.ManningPawn!=pawn) || !pawn.CanReserveAndReach(mortar,PathEndMode.InteractionCell,Danger.Some)
                        || !ResilienceAutomationHelper.RoutineRouteSafe(pawn,mortar) || (mortar.TryGetComp<CompRefuelable>() is CompRefuelable fuel && !fuel.HasFuel))continue;
                    ThingDef shell=ammunition?.LoadedShell;
                    if(shell==null && ammunition!=null)
                    {
                        var stock=map.listerThings.AllThings.Where(t=>t.def.IsShell && ammunition.allowedShellsSettings.AllowedToAccept(t)
                            && !t.IsForbidden(pawn) && pawn.CanReserveAndReach(t,PathEndMode.ClosestTouch,Danger.Some) && ResilienceAutomationHelper.RoutineRouteSafe(pawn,t)).ToList();
                        if(stock.Count>0)result.Add(new CombatNativeOptionDto{Tactic="mortar_reload",FighterId=pawn.thingIDNumber,TargetId=mortar.thingIDNumber,DefenseBuildingId=mortar.thingIDNumber,
                            Label=$"{pawn.LabelShort}: load {mortar.LabelShort} with existing permitted ammunition",Effects=Effects("Prepare empty mortar; observe actual shell before force targeting","Hold fire enabled; operator exposed while hauling shells",string.Join(",",stock.GroupBy(t=>t.def.defName).Select(g=>g.Key+"="+g.Sum(t=>t.stackCount))),"Native loader chooses permitted shell; follow-up fire requires observed loaded shell")});
                        continue;
                    }
                    if(shell==null)continue;
                    Verb mortarVerb=mortar.AttackVerb;var props=shell.projectileWhenLoaded?.projectile;if(mortarVerb==null || props==null)continue;
                    foreach(Thing target in targets)
                    {
                        float distance=mortar.Position.DistanceTo(target.Position);float scatter=Math.Max(8f,VerbUtility.CalculateAdjustedForcedMiss(mortarVerb.verbProps.ForcedMissRadius * mortarVerb.verbProps.GetForceMissFactorFor(mortar.gun,pawn),target.Position-mortar.Position));
                        if(distance<mortarVerb.verbProps.EffectiveMinRange(target,mortar) || distance>mortarVerb.EffectiveRange || target.Position.GetRoof(map)?.isThickRoof==true
                            || !FriendlyBlastSafe(map,pawn,target,props.explosionRadius+scatter))continue;
                        result.Add(new CombatNativeOptionDto{Tactic="mortar_counterbattery",FighterId=pawn.thingIDNumber,TargetId=target.thingIDNumber,DefenseBuildingId=mortar.thingIDNumber,
                            Label=$"{pawn.LabelShort}: {mortar.LabelShort} {shell.label} at {target.LabelShort}",Effects=Effects($"{target.LabelShort}: overhead fire range={distance:0} shell={shell.defName}","Scatter, friendly structures, moving targets, shield interception; no guaranteed hit",$"One normal {shell.label} round; manning/reload labor; barrel/fuel consumption","Native aiming/weather, shell effects and target movement decide outcome; later reloads may choose another permitted shell; observe before new targets")});
                    }
                }
            }
            foreach(var option in result)
            {
                Pawn worker=MapHelper.GetThingOnMapById(map.uniqueID,option.FighterId) as Pawn;
                option.Effects["risk"]=$"{worker.LabelShort} health={worker.health.summaryHealth.SummaryHealthPercent:0.00} bleed={worker.health.hediffSet.BleedRateTotal:0.00} job={worker.CurJobDef?.defName}; "+option.Effects["risk"];
            }
            return result;
        }
        public static CombatTacticResponseDto Apply(Map map,CombatTacticRequestDto request)
        {
            var result=new CombatTacticResponseDto{Tactic=request.Tactic};
            var option=Options(map).FirstOrDefault(o=>o.Tactic==request.Tactic && request.FighterIds.Contains(o.FighterId) && o.TargetId==request.TargetPawnId
                && (!request.Tactic.StartsWith("mortar_") || o.DefenseBuildingId==request.DefenseBuildingId));
            if(option==null){result.Notes.Add("Native weapon/ammunition/target option no longer feasible.");return result;}
            var pawn=MapHelper.GetThingOnMapById(map.uniqueID,option.FighterId) as Pawn;Thing target=MapHelper.GetThingOnMapById(map.uniqueID,option.TargetId);
            pawn.drafter.Drafted=true;result.DraftedPawnIds.Add(pawn.thingIDNumber);result.TargetPawnId=target.thingIDNumber;
            if(request.Tactic.StartsWith("mortar_"))
            {
                var mortar=MapHelper.GetThingOnMapById(map.uniqueID,option.DefenseBuildingId) as Building_TurretGun;
                var job=JobMaker.MakeJob(JobDefOf.ManTurret,mortar);
                if((pawn.CurJobDef==JobDefOf.ManTurret && pawn.CurJob.targetA.Thing==mortar) || pawn.jobs.TryTakeOrderedJob(job)){
                    foreach(var toggle in mortar.GetGizmos().OfType<Command_Toggle>().Where(g=>g.defaultLabel=="CommandHoldFire".Translate().ToString() && g.isActive()!=(request.Tactic=="mortar_reload")))toggle.toggleAction();
                    if(request.Tactic=="mortar_reload"){result.PositionedPawnIds.Add(pawn.thingIDNumber);result.Notes.Add("Native shell loading with hold fire; select fire only after actual loaded shell observed.");return result;}
                    mortar.OrderAttack(target);result.AttackingPawnIds.Add(pawn.thingIDNumber);result.Notes.Add("Native manning/reloading/force-target queued; outcome unobserved.");}
            }
            else
            {
                var job=JobMaker.MakeJob(request.Tactic=="attack_structure" && (pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb?.IsMeleeAttack ?? true) ? JobDefOf.AttackMelee : JobDefOf.AttackStatic,target);job.verbToUse=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
                if(pawn.jobs.TryTakeOrderedJob(job))result.AttackingPawnIds.Add(pawn.thingIDNumber);
            }
            return result;
        }
    }
}
