using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
using RimWorld.Planet;
using RIMAPI.Core;
using RIMAPI.Models;
namespace RIMAPI.Helpers
{
    public static class ResilienceAutomationHelper
    {
        public static List<ActiveNativeOrderDto> ActiveOrders(Map map)
        {
            var orders = new List<ActiveNativeOrderDto>();
            foreach (Pawn worker in map.mapPawns.AllPawnsSpawned.Where(p => p.IsColonistPlayerControlled && !p.Dead))
            {
                Job job = worker.CurJob;
                if (job == null) continue;
                string kind;
                Thing target;
                Thing carried = worker.carryTracker?.CarriedThing;
                // Native FoodFeedPatient.Deliveree is targetB; targetA is food.
                // Native TakeToBed.Takee is targetA.
                if (job.def == JobDefOf.FeedPatient) { kind = "feed"; target = job.targetB.Thing; }
                else if (job.def == JobDefOf.TendPatient) { kind = "tend"; target = job.targetA.Thing; }
                else if (job.def == JobDefOf.Rescue) { kind = "rescue"; target = job.targetA.Thing; }
                else if (job.def == JobDefOf.HaulToCell || job.def == JobDefOf.HaulToContainer)
                {
                    kind = "haul";
                    // A split stack may change identity: use only the known
                    // carried item when pickup has already happened.
                    target = carried ?? job.targetA.Thing;
                }
                else continue;
                if (target == null || target.Destroyed) continue;
                orders.Add(new ActiveNativeOrderDto { Kind = kind, WorkerId = worker.thingIDNumber,
                    TargetId = target.thingIDNumber, JobDef = job.def.defName,
                    CarriedThingId = carried?.thingIDNumber });
            }
            return orders;
        }

        private static HashSet<string> ActiveTargets(IEnumerable<ActiveNativeOrderDto> orders)
            => new HashSet<string>(orders.Select(o => o.Kind + ":" + o.TargetId));
        // Mirror native roof support's roof-connected search and 6.9-cell radius,
        // treating all currently designated removals plus this candidate as absent.
        public static bool RemovalWouldEndangerRoof(Thing target, Dictionary<IntVec3,bool> plannedSupportCache = null)
        {
            if (target == null || !target.Spawned || !target.def.holdsRoof) return false;
            Map map=target.Map;
            foreach (IntVec3 root in GenRadial.RadialCellsAround(target.Position,RoofCollapseUtility.RoofMaxSupportDistance,true).Where(c => c.InBounds(map) && c.Roofed(map)))
            {
                if (plannedSupportCache != null && plannedSupportCache.TryGetValue(root,out bool cached))
                { if (!cached) return true; continue; }
                var queue=new Queue<IntVec3>(); var visited=new HashSet<IntVec3>(); queue.Enqueue(root); visited.Add(root); bool supported=false;
                while (queue.Count > 0 && !supported)
                {
                    IntVec3 cell=queue.Dequeue();
                    foreach (IntVec3 offset in GenAdj.CardinalDirectionsAndInside)
                    {
                        IntVec3 next=cell+offset;
                        if (!next.InBounds(map) || !next.InHorDistOf(root,RoofCollapseUtility.RoofMaxSupportDistance)) continue;
                        Building holder=next.GetEdifice(map);
                        if (holder != null && holder.def.holdsRoof && holder != target
                            && map.designationManager.DesignationAt(next,DesignationDefOf.Mine) == null
                            && map.designationManager.DesignationOn(holder,DesignationDefOf.Deconstruct) == null)
                        { supported=true; break; }
                        if (next.Roofed(map) && visited.Add(next)) queue.Enqueue(next);
                    }
                }
                if (plannedSupportCache != null) plannedSupportCache[root]=supported;
                if (!supported) return true;
            }
            return false;
        }
        private static object Condition(Pawn p, Hediff h)
        {
            var immune=h.TryGetComp<HediffComp_Immunizable>();
            var tend=h.TryGetComp<HediffComp_TendDuration>();
            var record=p.health.immunity.GetImmunityRecord(h.def);
            return new { def_name=h.def.defName, description=h.def.description, visible=h.Visible, severity=h.Severity,
                immunity=immune == null ? (float?)null : immune.Immunity,
                immunity_can_develop=PawnHelper.CanDevelopImmunity(h),
                immunity_per_day=record == null ? (float?)null : record.ImmunityChangePerTick(p,true,h)*60000f,
                immunity_gain_speed=p.GetStatValue(StatDefOf.ImmunityGainSpeed),
                severity_modifiers_per_day=(h as HediffWithComps)?.comps?.OfType<HediffComp_SeverityModifierBase>().Sum(c => c.SeverityChangePerDay()),
                lethal_severity=h.def.lethalSeverity, part=h.Part?.Label, bleeding=h.BleedRate,
                tendable_now=h.TendableNow(), life_threatening=h.IsCurrentlyLifeThreatening,
                tend_quality=tend?.tendQuality, treatment_ticks_left=tend?.tendTicksLeft,
                parasite_total_tend_quality_target=tend == null || tend.TProps.disappearsAtTotalTendQuality < 0 ? (float?)null : tend.TProps.disappearsAtTotalTendQuality,
                next_tend_ticks=tend == null || tend.TProps.TendIsPermanent ? (int?)null : Math.Max(0,tend.tendTicksLeft-tend.TProps.TendTicksOverlap) };
        }
        private static WorkTypeDef RestWork => DefDatabase<WorkTypeDef>.GetNamed("PatientBedRest");
        private static readonly Dictionary<string, string[]> Givers = new Dictionary<string, string[]>
        {
            { "dispose_corpse", new[] { "HaulCorpses", "HaulGeneral" } },
            { "tend", new[] { "DoctorTendEmergency", "DoctorTendToHumanlikes", "DoctorTendToSelf", "DoctorTendToAnimals" } },
            { "rescue", new[] { "DoctorRescue" } },
            { "feed", new[] { "DoctorFeedHumanlikes", "DoctorFeedAnimals", "HandlingFeedPatientAnimals" } },
            { "clean", new[] { "CleanFilth" } },
            { "interrogate", new[] { "InterrogatePrisoner" } }
        };
        private static bool NeedsCare(Pawn p) => p.health.hediffSet.hediffs.Where(h => h.Visible).Any(h => h.TendableNow() || h.IsCurrentlyLifeThreatening
            || (PawnHelper.CanDevelopImmunity(h) && h.TryGetComp<HediffComp_Immunizable>().Immunity < 1)
            || (h.def.lethalSeverity > 0f && h.TryGetComp<HediffComp_Immunizable>() == null
                && h.def != HediffDefOf.BloodLoss && !h.IsPermanent()));
        private static bool Idle(Pawn p) => p.IsColonistPlayerControlled && !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState
            && !CombatNativeHelper.HasCareJob(p) && p.CurJobDef != JobDefOf.Ingest;
        private static bool Available(Pawn p) => Idle(p) && !NeedsCare(p);
        public static bool FeedFoodAvailable(Pawn worker, Pawn patient) => patient.needs?.food != null
            && FoodUtility.TryFindBestFoodSourceFor(worker, patient, patient.needs.food.CurCategory == HungerCategory.Starving,
                out Thing food, out ThingDef foodDef, canRefillDispenser:false, canUseInventory:true,
                canUsePackAnimalInventory:true, allowForbidden:false, allowCorpse:true,
                allowSociallyImproper:false, allowHarvest:false, forceScanWholeMap:false,
                ignoreReservations:false, calculateWantedStackCount:false, allowVenerated:true);
        public static bool RoutineRouteSafe(Pawn worker, Thing target) => Safe(worker,target);
        public static bool RefuelRouteSafe(Pawn worker, Thing target, bool shortThermal) => Safe(worker,target,false,shortThermal);
        public static bool ShortThermalErrandEligible(Pawn worker, Thing target) =>
            worker.Position.DistanceToSquared(target.Position) <= 144
            && worker.health.capacities.GetLevel(PawnCapacityDefOf.Moving) >= .5f
            && !worker.health.hediffSet.hediffs.Any(h => (h.def == HediffDefOf.Hypothermia || h.def == HediffDefOf.Heatstroke) && h.Severity >= .1f)
            && target.Position.GetTemperature(worker.Map) >= worker.GetStatValue(StatDefOf.ComfyTemperatureMin)-40f
            && target.Position.GetTemperature(worker.Map) <= worker.GetStatValue(StatDefOf.ComfyTemperatureMax)+40f;
        public static bool RescueRouteSafe(Pawn worker, Thing target) => Safe(worker,target,true);
        // The native tend workgiver accepts Deadly; automation explicitly requires Some.
        // Nearby live hostiles additionally reject civilian routes, including passive hive guards.
        private static bool Safe(Pawn worker, Thing target, bool rescueExposure = false, bool shortThermal = false)
        {
            if (!worker.CanReach(target, PathEndMode.Touch, Danger.Some) || target.IsForbidden(worker)) return false;
            if (!rescueExposure && (worker.Map.gasGrid.DensityAt(target.Position, GasType.ToxGas) > 0
                || worker.Map.gasGrid.DensityAt(target.Position, GasType.DeadlifeDust) > 0
                || worker.Map.gasGrid.DensityAt(target.Position, GasType.RotStink) > 0)) return false;
            float temperature=target.Position.GetTemperature(worker.Map);
            if (!rescueExposure && (temperature < worker.GetStatValue(StatDefOf.ComfyTemperatureMin)-10f || temperature > worker.GetStatValue(StatDefOf.ComfyTemperatureMax)+10f)
                && !(shortThermal && ShortThermalErrandEligible(worker,target))) return false;
            if (!rescueExposure && worker.Map.gameConditionManager.ActiveConditions.Any(c => c.def.defName == "ToxicFallout") && !target.Position.Roofed(worker.Map)) return false;
            foreach (Thing hostile in worker.Map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && !p.Downed && (p.HostileTo(worker) || CombatNativeHelper.ActivePredation(p))).Cast<Thing>()
                .Concat(worker.Map.listerBuildings.allBuildingsNonColonist.Where(CombatNativeHelper.ActiveStructure).Cast<Thing>()))
            {
                float range = hostile is Pawn enemy ? enemy.equipment?.Primary?.def.Verbs?.FirstOrDefault()?.range ?? 0f
                    : (hostile as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f;
                float radius = Math.Max(20f, range + 8f);
                var a = worker.Position; var b = target.Position; var e = hostile.Position;
                float dx = b.x - a.x, dz = b.z - a.z;
                float fraction = Math.Max(0f, Math.Min(1f, ((e.x-a.x)*dx + (e.z-a.z)*dz)/Math.Max(1f, dx*dx+dz*dz)));
                float ex = e.x-a.x-fraction*dx, ez=e.z-a.z-fraction*dz;
                if (ex*ex+ez*ez <= radius*radius) return false;
            }
            return true;
        }
        private static WorkGiver_Scanner NativeScanner(Pawn worker, Thing target, string kind, string giverName, HashSet<string> activeTargets = null, bool careYield = false)
        {
            if (kind == "clean" && worker.CurJobDef?.defName == "Clean") return null;
            if ((kind == "feed" || kind == "rescue" || kind == "tend")
                && (activeTargets ?? ActiveTargets(ActiveOrders(worker.Map))).Contains(kind + ":" + target.thingIDNumber)) return null;
            if (kind == "dispose_corpse" && (activeTargets ?? ActiveTargets(ActiveOrders(worker.Map))).Contains("haul:"+target.thingIDNumber)) return null;
            if ((kind == "feed" || kind == "rescue" || kind == "tend") && (CareTriageHelper.QueuedCare(worker)
                || target is Pawn queuedPatient && CareTriageHelper.QueuedFor(worker.Map,queuedPatient,kind))) return null;
            bool selfTend=kind == "tend" && worker == target && Idle(worker);
            bool rescueExposure=(kind == "rescue" && target is Pawn victim && victim.Downed) || (kind == "dispose_corpse" && target is Corpse);
            bool thermalRescue=kind == "rescue" && target is Pawn exposed && CareTriageHelper.ThermalRescueNeeded(exposed) && Idle(worker)
                && worker.health.hediffSet.BleedRateTotal == 0f && !CareTriageHelper.DiseaseCareProtected(worker);
            if (kind == null || giverName == null || (!Available(worker) && !selfTend && !careYield && !thermalRescue) || !Safe(worker, target,rescueExposure) || !Givers.TryGetValue(kind, out string[] allowed) || !allowed.Contains(giverName)) return null;
            WorkGiverDef def = DefDatabase<WorkGiverDef>.GetNamedSilentFail(giverName);
            bool manualCare=kind == "feed" || kind == "rescue" || kind == "tend";
            if (def == null || worker.WorkTypeIsDisabled(def.workType) || (!manualCare && (worker.workSettings?.GetPriority(def.workType) ?? 0) == 0)
                || def.Worker.ShouldSkip(worker,manualCare) || !(def.Worker is WorkGiver_Scanner scanner)) return null;
            if (def.requiredCapacities != null && def.requiredCapacities.Any(c => !worker.health.capacities.CapableOf(c))) return null;
            if(scanner is WorkGiver_Warden_InterrogateIdentity)
            {
                if(!(target is Pawn prisoner) || !ModsConfig.AnomalyActive || !prisoner.IsPrisonerOfColony || !prisoner.guest.PrisonerIsSecure
                    || prisoner.InMentalState || target.IsForbidden(worker) || prisoner.IsFormingCaravan() || !worker.CanReserveAndReach(target,PathEndMode.OnCell,worker.NormalMaxDanger())
                    || !prisoner.guest.IsInteractionEnabled(PrisonerInteractionModeDefOf.Interrogate) || !prisoner.guest.ScheduledForInteraction
                    || (prisoner.Downed && !prisoner.InBed()) || !worker.health.capacities.CapableOf(PawnCapacityDefOf.Talking) || !prisoner.Awake())return null;
            }
            else if (!scanner.HasJobOnThing(worker, target, manualCare)) return null;
            return scanner;
        }
        public static Job NativeJob(Pawn worker,Thing target,string kind,string giverName, string expectedJob = null, int? expectedPatient = null)
        {
            bool careYield = target is Pawn patient && CareTriageHelper.CanYield(worker, patient, kind, expectedJob, expectedPatient, out _);
            if ((expectedJob != null || expectedPatient.HasValue) && !careYield) return null;
            var scanner=NativeScanner(worker,target,kind,giverName, careYield:careYield);
            if(scanner==null)return null;
            bool rescueExposure=(kind=="rescue" && target is Pawn victim && victim.Downed) || (kind=="dispose_corpse" && target is Corpse);
            Job job = scanner.JobOnThing(worker, target, kind == "feed" || kind == "rescue" || kind == "tend");
            if (job == null) return null;
            if (kind == "rescue" && target is Pawn exposed && CareTriageHelper.ThermalRescueNeeded(exposed))
            {
                // Native rescue may choose the closest outdoor spot. Keep native bed eligibility,
                // but compare completed shelter beds before accepting a thermal transfer.
                var beds=worker.Map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>()
                    .Where(b => CareTriageHelper.ThermalBedBeneficial(exposed,b)
                        && !b.CurOccupants.Any(p => p != exposed)
                        && RestUtility.IsValidBedFor(b,exposed,worker,true,false,false,exposed.GuestStatus)
                        && worker.CanReserveAndReach(b,PathEndMode.OnCell,Danger.Some) && Safe(worker,b))
                    .OrderBy(b => exposed.Position.DistanceToSquared(b.Position));
                job=beds.Select(b => JobMaker.MakeJob(JobDefOf.Rescue,exposed,b))
                    .FirstOrDefault(j => CareTriageHelper.JobRouteSafe(worker,j));
                if (job == null) return null;
            }
            if (kind == "dispose_corpse" && !SafeDisposalDestination(worker, job.targetB)) return null;
            foreach (LocalTargetInfo t in new[] { job.targetA, job.targetB, job.targetC })
                if (t.HasThing && t.Thing.Spawned && !Safe(worker, t.Thing,rescueExposure && t.Thing == target)) return null;
            if ((kind == "feed" || kind == "rescue") && !CareTriageHelper.JobRouteSafe(worker,job)) return null;
            return job;
        }
        private static bool ShelterNeeded(Pawn patient) => patient.IsColonistPlayerControlled && !patient.Dead && !patient.Downed
            && !patient.Drafted && !patient.InMentalState && !CombatNativeHelper.HasCareJob(patient)
            && patient.Map.gasGrid.DensityAt(patient.Position,GasType.RotStink)>0;
        private static bool ShelterBedSafe(Pawn patient, Building_Bed bed) => bed != null && bed.Spawned
            && bed.Map==patient.Map && bed.Faction==Faction.OfPlayer && !bed.ForPrisoners
            && RestUtility.CanUseBedEver(patient,bed.def) && Safe(patient,bed)
            && !NearLivingAreaCorpse(patient.Map,bed.Position,15f)
            && !bed.CurOccupants.Any(p=>p!=patient) && patient.CanReserveAndReach(bed,PathEndMode.OnCell,Danger.Some);
        private static bool NearLivingAreaCorpse(Map map, IntVec3 cell, float radius)
            => map.listerThings.AllThings.OfType<Corpse>().Any(c=>c.Position.InHorDistOf(cell,radius));
        private static bool NearLivingArea(Map map, IntVec3 cell, float radius)
            => map.mapPawns.FreeColonistsSpawned.Any(p => !p.Dead && p.Position.InHorDistOf(cell,radius))
                || map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Any(b => b.Position.InHorDistOf(cell,radius));
        private static bool SafeDisposalDestination(Pawn worker, LocalTargetInfo target)
        {
            IntVec3 cell=target.Cell; Map map=worker.Map;
            if (!target.IsValid || !cell.InBounds(map) || NearLivingArea(map,cell,20f)
                || map.gasGrid.DensityAt(cell,GasType.ToxGas)>0 || map.gasGrid.DensityAt(cell,GasType.DeadlifeDust)>0
                || map.gasGrid.DensityAt(cell,GasType.RotStink)>0
                || !worker.CanReach(cell,PathEndMode.Touch,Danger.Some)
                || cell.GetTemperature(map)<worker.GetStatValue(StatDefOf.ComfyTemperatureMin)-10f
                || cell.GetTemperature(map)>worker.GetStatValue(StatDefOf.ComfyTemperatureMax)+10f) return false;
            if (target.HasThing) return Safe(worker,target.Thing);
            if (cell.Roofed(map) || map.gameConditionManager.ActiveConditions.Any(c=>c.def.defName=="ToxicFallout")) return false;
            // The corpse route is already checked. Check its continuation to storage too.
            foreach (Thing hostile in map.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && !p.Downed && (p.HostileTo(worker) || CombatNativeHelper.ActivePredation(p))).Cast<Thing>()
                .Concat(map.listerBuildings.allBuildingsNonColonist.Where(CombatNativeHelper.ActiveStructure).Cast<Thing>()))
            {
                float range=hostile is Pawn enemy ? enemy.equipment?.Primary?.def.Verbs?.FirstOrDefault()?.range ?? 0f
                    : (hostile as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f;
                float radius=Math.Max(20f,range+8f); var a=worker.Position; var e=hostile.Position;
                float dx=cell.x-a.x,dz=cell.z-a.z;
                float fraction=Math.Max(0f,Math.Min(1f,((e.x-a.x)*dx+(e.z-a.z)*dz)/Math.Max(1f,dx*dx+dz*dz)));
                float ex=e.x-a.x-fraction*dx,ez=e.z-a.z-fraction*dz;
                if(ex*ex+ez*ez<=radius*radius)return false;
            }
            return true;
        }
        private static bool Preventible(Pawn p, Thing drug) => Available(p) && p.CurJobDef?.defName != "Clean" && p.RaceProps.Humanlike && p.DevelopmentalStage.Adult()
            && drug.def.defName == "Penoxycyline" && drug.stackCount > 0 && drug.def.IsDrug && Safe(p, drug) && p.CanReserve(drug)
            && !p.health.hediffSet.hediffs.Any(h => h.def.defName == "PenoxycylineHigh" || h.def.defName == "Malaria" || h.def.defName == "Plague" || h.def.defName == "SleepingSickness");
        private static bool ThermalCorrectionNeeded(ThingWithComps device)
        {
            if (device.Faction != Faction.OfPlayer || !(device.TryGetComp<CompTempControl>() is CompTempControl control)) return false;
            Room room=device.GetRoom();
            if (room == null || room.PsychologicallyOutdoors || (control.TargetTemperature >= 18f && control.TargetTemperature <= 26f)) return false;
            // A negative cooler target is evidence of an intentional freezer, including mixed-use rooms.
            if (room.ContainedAndAdjacentThings.OfType<ThingWithComps>().Any(t => t.GetRoom()==room && t.def.defName=="Cooler"
                && t.TryGetComp<CompTempControl>() is CompTempControl cooler && cooler.TargetTemperature < 0f)) return false;
            bool humanCare=device.Map.mapPawns.AllPawnsSpawned.Any(p => !p.Dead && p.RaceProps.Humanlike
                && (p.IsColonistPlayerControlled || p.IsPrisonerOfColony) && p.GetRoom()==room && (p.InBed() || NeedsCare(p))
                && room.ContainedAndAdjacentThings.OfType<Building_Bed>().Any(b => b.GetRoom()==room && RestUtility.CanUseBedEver(p,b.def)));
            return humanCare && ((device.def.defName=="Heater" && room.Temperature < 10f)
                || (device.def.defName=="Cooler" && room.Temperature > 32f));
        }
        public static ApiResult<ResilienceContextDto> Context(int mapId)
        {
            Map map = MapHelper.GetMapByID(mapId);
            if (map == null) return ApiResult<ResilienceContextDto>.Fail("Map not found.");
            var result = new ResilienceContextDto();
            result.ActiveOrders = ActiveOrders(map);
            var activeTargets = ActiveTargets(result.ActiveOrders);
            var plannedSupportCache=new Dictionary<IntVec3,bool>();
            foreach (Designation designation in map.designationManager.AllDesignations.Where(d => d.def == DesignationDefOf.Mine || d.def == DesignationDefOf.Deconstruct))
            {
                Thing support=designation.target.HasThing ? designation.target.Thing : designation.target.Cell.GetEdifice(map);
                if (RemovalWouldEndangerRoof(support,plannedSupportCache)) result.Options.Add(new ResilienceOptionDto {Kind="roof_guard",WorkerId=0,TargetId=support.thingIDNumber,Giver=designation.def.defName,Target=support.LabelShort});
            }
            var patients = map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && (p.IsColonistPlayerControlled || p.IsPrisonerOfColony || p.Faction == Faction.OfPlayer)).ToList();
            foreach (Pawn p in patients)
                result.Patients.Add(new { pawn_id = p.thingIDNumber, name = p.LabelShort, downed = p.Downed, drafted = p.Drafted,
                    mental_state = p.MentalStateDef?.defName, current_job = p.CurJobDef?.defName, in_bed = p.InBed(), current_bed_id=p.CurrentBed()?.thingIDNumber,
                    tendable_now = p.health.hediffSet.hediffs.Any(h => h.Visible && h.TendableNow()), life_threatening = p.health.hediffSet.hediffs.Any(h => h.Visible && h.IsCurrentlyLifeThreatening),
                    medical_care = p.playerSettings?.medCare.ToString(), bed_rest_priority = p.workSettings?.GetPriority(RestWork),
                    should_seek_medical_rest = HealthAIUtility.ShouldSeekMedicalRest(p),
                    temperature = p.Position.GetTemperature(map), roof = map.roofGrid.RoofAt(p.Position)?.defName,
                    comfortable_min=p.GetStatValue(StatDefOf.ComfyTemperatureMin), comfortable_max=p.GetStatValue(StatDefOf.ComfyTemperatureMax),
                    gases=Enum.GetValues(typeof(GasType)).Cast<GasType>().ToDictionary(g => g.ToString(),g => (int)map.gasGrid.DensityAt(p.Position,g)),
                    food = p.needs?.food?.CurLevelPercentage, bleeding_evidence_complete=true,
                    bleedout_ticks=p.health.hediffSet.BleedRateTotal >= .1f ? CareTriageHelper.BleedoutTicks(p) : null, starvation_ticks=CareTriageHelper.StarvationTicks(p),
                    malnutrition_severity=CareTriageHelper.Malnutrition(p)?.Severity,
                    lethal_margin=CareTriageHelper.Malnutrition(p) is Hediff patientMalnutrition ? (float?)(patientMalnutrition.def.lethalSeverity-patientMalnutrition.Severity) : null,
                    pain=p.health.hediffSet.PainTotal, bleeding_total=p.health.hediffSet.BleedRateTotal,
                    breathing=p.health.capacities.GetLevel(PawnCapacityDefOf.Breathing), consciousness=p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness),
                    moving=p.health.capacities.GetLevel(PawnCapacityDefOf.Moving), manipulation=p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation),
                    traits=p.story?.traits?.allTraits.Select(t => t.def.defName).ToList(),
                    conditions = p.health.hediffSet.hediffs.Where(h => h.Visible).Select(h => Condition(p,h)).ToList() });
            var rooms = patients.Select(p => p.GetRoom()).Concat(map.listerThings.AllThings.Where(t => t.def.defName == "ElectricStove" || t.def.defName == "FueledStove" || t.def.defName == "HospitalBed" || t.def.defName == "Bed").Select(t => t.GetRoom())).Where(r => r != null).Distinct().ToList();
            var careRooms=patients.Where(NeedsCare).Select(p => p.GetRoom()).Concat(map.listerThings.AllThings.Where(t => t.def.defName == "HospitalBed" || t.def.defName == "ElectricStove" || t.def.defName == "FueledStove").Select(t => t.GetRoom()))
                .Where(r => r != null && !r.PsychologicallyOutdoors).Distinct().ToList();
            result.Environment = new { biome=map.Biome.defName, disease_mtb_days=map.Biome.diseaseMtbDays,
                biome_diseases=DefDatabase<IncidentDef>.AllDefsListForReading.Where(d => map.Biome.CommonalityOfDisease(d) > 0).Select(d => new {def_name=d.defName,commonality=map.Biome.CommonalityOfDisease(d),description=d.description}).ToList(),
                gray_flesh_samples=map.listerThings.AllThings.Count(t => t.def.defName == "GrayFleshSample" && !t.Position.Fogged(map)),
                completed_anomaly_analyses=Find.AnalysisManager?.AnalysisDetailsForReading.Count(d => d.Satisfied) ?? 0,
                conditions = map.gameConditionManager.ActiveConditions.Select(c => new { def_name = c.def.defName, description = c.def.description }).ToList(),
                rooms = rooms.Select(r => new { id = r.ID, temperature = r.Temperature, outdoors = r.PsychologicallyOutdoors,
                    cleanliness = r.GetStat(RoomStatDefOf.Cleanliness), mountain_cells = r.Cells.Count(c => map.roofGrid.RoofAt(c)?.isThickRoof == true) }).ToList(),
                hives = map.listerThings.AllThings.Where(t => t.def.defName == "Hive" || t.def.defName == "TunnelHiveSpawner").Select(t => new { id=t.thingIDNumber, def_name=t.def.defName, x=t.Position.x, z=t.Position.z }).ToList(),
                climate_devices = map.listerThings.AllThings.OfType<ThingWithComps>().Where(t => t.TryGetComp<CompTempControl>() != null).Select(t => new {id=t.thingIDNumber, def_name=t.def.defName,
                    target=t.TryGetComp<CompTempControl>().TargetTemperature, power_on=t.TryGetComp<CompPowerTrader>()?.PowerOn, room_id=t.GetRoom()?.ID,
                    temperature=t.Position.GetTemperature(map)}).ToList(),
                warning = "Thick mountain roof is unremovable and permits infestations. Cleaning does not prevent incident disease; penoxycyline prevents only new malaria/plague/sleeping sickness. Active smoke/toxic/thermal hazards require safe shelter and architecture." };
            foreach (ThingWithComps device in map.listerThings.AllThings.OfType<ThingWithComps>().Where(ThermalCorrectionNeeded))
                foreach (int targetTemp in new[] {18,21,26})
                    if (Math.Abs(device.TryGetComp<CompTempControl>().TargetTemperature-targetTemp) > .1f)
                        result.Options.Add(new ResilienceOptionDto {Kind="temperature",WorkerId=0,TargetId=device.thingIDNumber,Giver=targetTemp.ToString(),Target=device.LabelShort,CurrentTemperature=device.GetRoom().Temperature,CurrentTargetTemperature=device.TryGetComp<CompTempControl>().TargetTemperature,PowerOn=device.TryGetComp<CompPowerTrader>()?.PowerOn});
            foreach (Pawn worker in patients.Where(p => Idle(p) || p.CurJobDef == JobDefOf.TendPatient || p.CurJobDef == JobDefOf.Rescue))
            {
                foreach (Pawn patient in patients.Where(p => p != worker && p.Downed && !p.InBed()
                    && (p.needs?.food?.CurLevelPercentage ?? 1f) < .35f))
                    if (Available(worker) && !activeTargets.Contains("rescue:" + patient.thingIDNumber)
                        && !worker.WorkTypeIsDisabled(WorkTypeDefOf.Doctor)
                                                && !activeTargets.Contains("feed:" + patient.thingIDNumber)
                        && worker.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation)
                        && Safe(worker, patient, true)
                        && worker.CanReserveAndReach(patient, PathEndMode.Touch, Danger.Some)
                        && RestUtility.FindBedFor(patient, worker, false, false) == null
                        && NativeScanner(worker, patient, "rescue", "DoctorRescue", activeTargets) == null)
                        result.Options.Add(new ResilienceOptionDto { Kind="bed_prerequisite", WorkerId=worker.thingIDNumber,
                            TargetId=patient.thingIDNumber, Giver=patient.RaceProps.Animal ? "AnimalSleepingSpot" : "SleepingSpot",
                            Worker=worker.LabelShort, Target=patient.LabelShort, PrerequisiteReason="no_completed_bed_for_patient",
                            FoodFeasible=FeedFoodAvailable(worker, patient) });
                foreach (var pair in Givers)
                {
                    IEnumerable<Thing> targets = pair.Key == "dispose_corpse"
                        ? map.listerThings.AllThings.OfType<Corpse>().Where(c => NearLivingArea(map,c.Position,15f)).Cast<Thing>()
                        : pair.Key == "clean"
                        ? map.listerThings.AllThings.Where(t => t is Filth && careRooms.Contains(t.GetRoom()) && (t.GetRoom()?.GetStat(RoomStatDefOf.Cleanliness) ?? 0f) < 0f)
                        : patients.Cast<Thing>();
                    foreach (Thing target in targets) foreach (string giver in pair.Value)
                        if (!(pair.Key == "dispose_corpse" && activeTargets.Contains("haul:"+target.thingIDNumber))
                            && NativeScanner(worker, target, pair.Key, giver, activeTargets) != null
                            && ((pair.Key != "dispose_corpse" && pair.Key != "feed" && pair.Key != "rescue") || NativeJob(worker,target,pair.Key,giver) != null))
                            result.Options.Add(new ResilienceOptionDto { Kind=pair.Key, WorkerId=worker.thingIDNumber, TargetId=target.thingIDNumber,
                                Giver=giver, Worker=worker.LabelShort, Target=target.LabelShort, MedicineSkill=worker.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0,RoomCleanliness=target.GetRoom()?.GetStat(RoomStatDefOf.Cleanliness),
                                MedicalTendQuality=pair.Key == "tend" ? worker.GetStatValue(StatDefOf.MedicalTendQuality) : (float?)null,
                                MedicalTendSpeed=pair.Key == "tend" ? worker.GetStatValue(StatDefOf.MedicalTendSpeed) : (float?)null,
                                TravelDistance=worker.Position.DistanceTo(target.Position),
                                StarvationTicks=target is Pawn starving ? CareTriageHelper.StarvationTicks(starving) : null,
                                MalnutritionSeverity=target is Pawn malPatient ? CareTriageHelper.Malnutrition(malPatient)?.Severity : null,
                                LethalMargin=target is Pawn marginPatient && CareTriageHelper.Malnutrition(marginPatient) is Hediff malnutrition ? (float?)(malnutrition.def.lethalSeverity-malnutrition.Severity) : null,
                                FoodFeasible=pair.Key == "feed" || (pair.Key == "rescue" && target is Pawn hungry && FeedFoodAvailable(worker, hungry)) });
                }
                foreach (Pawn patient in patients.Where(p => p != worker && p.IsColonistPlayerControlled))
                    foreach (string kind in new[] { "feed", "rescue" })
                    {
                        string expectedJob=worker.CurJobDef?.defName;
                        int? expectedPatient=(worker.CurJob?.targetA.Thing as Pawn)?.thingIDNumber;
                        if (!CareTriageHelper.CanYield(worker,patient,kind,expectedJob,expectedPatient,out string reason)
                            || (reason != "nonbleeding_tend_to_thermal_rescue_same_patient" && !FeedFoodAvailable(worker,patient))) continue;
                        string giver=kind == "feed" ? "DoctorFeedHumanlikes" : "DoctorRescue";
                        if (NativeJob(worker,patient,kind,giver,expectedJob,expectedPatient) == null) continue;
                        Hediff mal=CareTriageHelper.Malnutrition(patient);
                        result.Options.Add(new ResilienceOptionDto { Kind=kind,WorkerId=worker.thingIDNumber,TargetId=patient.thingIDNumber,
                            Worker=worker.LabelShort,Target=patient.LabelShort,Giver=giver,FoodFeasible=FeedFoodAvailable(worker,patient),
                            ExpectedCurrentJob=expectedJob,ExpectedCarePatientId=expectedPatient,CareYieldReason=reason,
                            TravelDistance=worker.Position.DistanceTo(patient.Position),StarvationTicks=CareTriageHelper.StarvationTicks(patient),
                            MalnutritionSeverity=mal?.Severity,LethalMargin=mal == null ? (float?)null : mal.def.lethalSeverity-mal.Severity });
                    }
                foreach (Thing drug in map.listerThings.AllThings.Where(t => t.def.defName == "Penoxycyline"))
                    if (Preventible(worker, drug)) result.Options.Add(new ResilienceOptionDto {Kind="prevent", WorkerId=worker.thingIDNumber,TargetId=drug.thingIDNumber,Worker=worker.LabelShort,Target=drug.LabelShort});
            }
            foreach (ResilienceOptionDto option in result.Options.Where(o => o.Kind == "rescue"))
            {
                Pawn patient=patients.FirstOrDefault(p => p.thingIDNumber == option.TargetId);
                Pawn worker=map.mapPawns.AllPawnsSpawned.FirstOrDefault(p => p.thingIDNumber == option.WorkerId);
                if (!CareTriageHelper.ThermalRescueNeeded(patient)) continue;
                Job rescue=NativeJob(worker,patient,"rescue",option.Giver,option.ExpectedCurrentJob,option.ExpectedCarePatientId);
                if (!(rescue?.targetB.Thing is Building_Bed bed)) continue;
                option.ThermalRescue=true; option.BedId=bed.thingIDNumber;
                option.CurrentTemperature=patient.Position.GetTemperature(map);
                option.DestinationTemperature=bed.Position.GetTemperature(map);
            }
            foreach (Pawn patient in patients.Where(p => p.IsColonistPlayerControlled && !p.Drafted && !p.InMentalState && HealthAIUtility.ShouldSeekMedicalRest(p)
                && (p.InBed() || (!p.Downed && RestUtility.FindBedFor(p, p, false, false) != null))
                && p.workSettings != null && !p.WorkTypeIsDisabled(RestWork) && p.workSettings.GetPriority(RestWork) != 1))
                result.Options.Add(new ResilienceOptionDto {Kind="rest", WorkerId=patient.thingIDNumber,TargetId=patient.thingIDNumber,Worker=patient.LabelShort,Target=patient.LabelShort});
            foreach (Pawn patient in patients.Where(ShelterNeeded))
                foreach (Building_Bed bed in map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Where(b=>ShelterBedSafe(patient,b)))
                    result.Options.Add(new ResilienceOptionDto {Kind="shelter",WorkerId=patient.thingIDNumber,TargetId=patient.thingIDNumber,
                        Giver=bed.thingIDNumber.ToString(),Worker=patient.LabelShort,Target=patient.LabelShort});
            ResilienceDiagnosisHelper.AddOptions(map,result);
            return ApiResult<ResilienceContextDto>.Ok(result);
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(ResilienceOrderRequestDto request)
        {
            var result = new CapabilityOrderResultDto { TargetId=request.TargetId };
            Pawn worker = MapHelper.GetThingOnMapById(request.MapId, request.WorkerId) as Pawn;
            Thing target = MapHelper.GetThingOnMapById(request.MapId, request.TargetId);
            if (request.Kind == "inspect" || request.Kind == "interrogation_policy")
                return ResilienceDiagnosisHelper.Execute(request);
            if (request.Kind == "roof_guard" && target != null && RemovalWouldEndangerRoof(target))
            {
                Designation designation=request.Giver == "Mine" ? target.Map.designationManager.DesignationAt(target.Position,DesignationDefOf.Mine)
                    : request.Giver == "Deconstruct" ? target.Map.designationManager.DesignationOn(target,DesignationDefOf.Deconstruct) : null;
                if (designation != null) {target.Map.designationManager.RemoveDesignation(designation);result.Applied=true;result.Reason="dangerous_support_removal_cancelled; replacement_support_needed";}
                else result.Reason="designation_no_longer_present";
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            if (request.Kind == "temperature" && target is ThingWithComps device && device.Faction == Faction.OfPlayer
                && (device.def.defName == "Heater" || device.def.defName == "Cooler") && device.TryGetComp<CompTempControl>() is CompTempControl thermostat
                && new[] {"18","21","26"}.Contains(request.Giver) && ThermalCorrectionNeeded(device) && Math.Abs(thermostat.TargetTemperature-int.Parse(request.Giver)) > .1f)
            { thermostat.TargetTemperature=int.Parse(request.Giver); result.Applied=true; result.Reason="thermostat_set; power_and_heat_transfer_required";
                return ApiResult<CapabilityOrderResultDto>.Ok(result); }
            if (worker == null || target == null || worker.Dead || !worker.Spawned || target.Destroyed)
                return ApiResult<CapabilityOrderResultDto>.Fail("Live worker and target required.");
            if (request.Kind == "shelter" && worker == target && ShelterNeeded(worker))
            {
                Building_Bed bed=int.TryParse(request.Giver,out int bedId) ? worker.Map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().FirstOrDefault(b=>b.thingIDNumber==bedId) : null;
                if(ShelterBedSafe(worker,bed))
                { result.Applied=PawnHelper.AssignBedRest(worker,bed); result.Reason=result.Applied ? "safe_bed_rest_scheduled; relocation_unobserved" : "job_rejected"; }
                else result.Reason="safe_shelter_bed_no_longer_feasible";
                return ApiResult<CapabilityOrderResultDto>.Ok(result);
            }
            if (request.Kind == "rest" && worker == target && worker.IsColonistPlayerControlled && !worker.Drafted && !worker.InMentalState
                && HealthAIUtility.ShouldSeekMedicalRest(worker) && worker.workSettings != null && !worker.WorkTypeIsDisabled(RestWork)
                && worker.workSettings.GetPriority(RestWork) != 1)
            { worker.workSettings.SetPriority(RestWork,1); result.Applied=true; result.Reason="bed_rest_prioritized; autonomous_job_required"; }
            else
            {
                Job job = request.Kind == "prevent" && Preventible(worker,target) ? JobMaker.MakeJob(JobDefOf.Ingest,target) : NativeJob(worker,target,request.Kind,request.Giver,request.ExpectedCurrentJob,request.ExpectedCarePatientId);
                if (job != null)
                { if (request.Kind == "prevent") job.count=1;
                    result.Applied=worker.jobs.TryTakeOrderedJob(job);
                    if (request.Kind == "feed" || request.Kind == "rescue")
                    { result.Applied=result.Applied && target is Pawn patient && CareTriageHelper.Matches(worker,job,patient);
                        if (!result.Applied) worker.jobs.jobQueue.RemoveAll(worker,j=>j==job); }
                    result.Reason=result.Applied ? "normal_job_observed; completion_unobserved" : "job_rejected_or_not_current"; }
                else result.Reason="selection_no_longer_feasible";
            }
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}
