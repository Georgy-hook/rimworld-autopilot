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
                immunity_per_day=record == null ? (float?)null : record.ImmunityChangePerTick(p,true,h)*60000f,
                immunity_gain_speed=p.GetStatValue(StatDefOf.ImmunityGainSpeed),
                severity_modifiers_per_day=(h as HediffWithComps)?.comps?.OfType<HediffComp_SeverityModifierBase>().Sum(c => c.SeverityChangePerDay()),
                lethal_severity=h.def.lethalSeverity, part=h.Part?.Label, bleeding=h.BleedRate,
                tendable_now=h.TendableNow(), life_threatening=h.IsCurrentlyLifeThreatening,
                tend_quality=tend?.tendQuality, treatment_ticks_left=tend?.tendTicksLeft,
                parasite_total_tend_quality_target=tend == null || tend.TProps.disappearsAtTotalTendQuality < 0 ? (float?)null : tend.TProps.disappearsAtTotalTendQuality,
                next_tend_ticks=tend == null ? (int?)null : Math.Max(0,tend.tendTicksLeft-tend.TProps.TendTicksOverlap) };
        }
        private static WorkTypeDef RestWork => DefDatabase<WorkTypeDef>.GetNamed("PatientBedRest");
        private static readonly Dictionary<string, string[]> Givers = new Dictionary<string, string[]>
        {
            { "tend", new[] { "DoctorTendEmergency", "DoctorTendToHumanlikes", "DoctorTendToSelf", "DoctorTendToAnimals" } },
            { "rescue", new[] { "DoctorRescue" } },
            { "feed", new[] { "DoctorFeedHumanlikes", "DoctorFeedAnimals" } },
            { "clean", new[] { "CleanFilth" } },
            { "interrogate", new[] { "InterrogatePrisoner" } }
        };
        private static bool NeedsCare(Pawn p) => p.health.hediffSet.hediffs.Where(h => h.Visible).Any(h => h.TendableNow() || h.IsCurrentlyLifeThreatening
            || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable c && c.Immunity < 1));
        private static bool Idle(Pawn p) => p.IsColonistPlayerControlled && !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState
            && !CombatNativeHelper.HasCareJob(p) && p.CurJobDef?.defName != "Clean" && p.CurJobDef != JobDefOf.Ingest;
        private static bool Available(Pawn p) => Idle(p) && !NeedsCare(p);
        public static bool RoutineRouteSafe(Pawn worker, Thing target) => Safe(worker,target);
        public static bool RescueRouteSafe(Pawn worker, Thing target) => Safe(worker,target,true);
        // The native tend workgiver accepts Deadly; automation explicitly requires Some.
        // Nearby live hostiles additionally reject civilian routes, including passive hive guards.
        private static bool Safe(Pawn worker, Thing target, bool rescueExposure = false)
        {
            if (!worker.CanReach(target, PathEndMode.Touch, Danger.Some) || target.IsForbidden(worker)) return false;
            if (!rescueExposure && (worker.Map.gasGrid.DensityAt(target.Position, GasType.ToxGas) > 0
                || worker.Map.gasGrid.DensityAt(target.Position, GasType.DeadlifeDust) > 0
                || worker.Map.gasGrid.DensityAt(target.Position, GasType.RotStink) > 0)) return false;
            float temperature=target.Position.GetTemperature(worker.Map);
            if (!rescueExposure && (temperature < worker.GetStatValue(StatDefOf.ComfyTemperatureMin)-10f || temperature > worker.GetStatValue(StatDefOf.ComfyTemperatureMax)+10f)) return false;
            if (!rescueExposure && worker.Map.gameConditionManager.ActiveConditions.Any(c => c.def.defName == "ToxicFallout") && !target.Position.Roofed(worker.Map)) return false;
            foreach (Thing hostile in worker.Map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && !p.Downed && p.HostileTo(worker)).Cast<Thing>()
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
        private static WorkGiver_Scanner NativeScanner(Pawn worker, Thing target, string kind, string giverName)
        {
            bool selfTend=kind == "tend" && worker == target && Idle(worker);
            bool rescueExposure=kind == "rescue" && target is Pawn victim && victim.Downed;
            if (kind == null || giverName == null || (!Available(worker) && !selfTend) || !Safe(worker, target,rescueExposure) || !Givers.TryGetValue(kind, out string[] allowed) || !allowed.Contains(giverName)) return null;
            WorkGiverDef def = DefDatabase<WorkGiverDef>.GetNamedSilentFail(giverName);
            if (def == null || worker.WorkTypeIsDisabled(def.workType) || (worker.workSettings?.GetPriority(def.workType) ?? 0) == 0
                || def.Worker.ShouldSkip(worker) || !(def.Worker is WorkGiver_Scanner scanner)) return null;
            if (def.requiredCapacities != null && def.requiredCapacities.Any(c => !worker.health.capacities.CapableOf(c))) return null;
            if(scanner is WorkGiver_Warden_InterrogateIdentity)
            {
                if(!(target is Pawn prisoner) || !ModsConfig.AnomalyActive || !prisoner.IsPrisonerOfColony || !prisoner.guest.PrisonerIsSecure
                    || prisoner.InMentalState || target.IsForbidden(worker) || prisoner.IsFormingCaravan() || !worker.CanReserveAndReach(target,PathEndMode.OnCell,worker.NormalMaxDanger())
                    || !prisoner.guest.IsInteractionEnabled(PrisonerInteractionModeDefOf.Interrogate) || !prisoner.guest.ScheduledForInteraction
                    || (prisoner.Downed && !prisoner.InBed()) || !worker.health.capacities.CapableOf(PawnCapacityDefOf.Talking) || !prisoner.Awake())return null;
            }
            else if (!scanner.HasJobOnThing(worker, target, false)) return null;
            return scanner;
        }
        private static Job NativeJob(Pawn worker,Thing target,string kind,string giverName)
        {
            var scanner=NativeScanner(worker,target,kind,giverName);
            if(scanner==null)return null;
            bool rescueExposure=kind=="rescue" && target is Pawn victim && victim.Downed;
            Job job = scanner.JobOnThing(worker, target, false);
            if (job == null) return null;
            foreach (LocalTargetInfo t in new[] { job.targetA, job.targetB, job.targetC })
                if (t.HasThing && t.Thing.Spawned && !Safe(worker, t.Thing,rescueExposure && t.Thing == target)) return null;
            return job;
        }
        private static bool Preventible(Pawn p, Thing drug) => Available(p) && p.RaceProps.Humanlike && p.DevelopmentalStage.Adult()
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
            var plannedSupportCache=new Dictionary<IntVec3,bool>();
            foreach (Designation designation in map.designationManager.AllDesignations.Where(d => d.def == DesignationDefOf.Mine || d.def == DesignationDefOf.Deconstruct))
            {
                Thing support=designation.target.HasThing ? designation.target.Thing : designation.target.Cell.GetEdifice(map);
                if (RemovalWouldEndangerRoof(support,plannedSupportCache)) result.Options.Add(new ResilienceOptionDto {Kind="roof_guard",WorkerId=0,TargetId=support.thingIDNumber,Giver=designation.def.defName,Target=support.LabelShort});
            }
            var patients = map.mapPawns.AllPawnsSpawned.Where(p => !p.Dead && (p.IsColonistPlayerControlled || p.IsPrisonerOfColony || p.Faction == Faction.OfPlayer)).ToList();
            foreach (Pawn p in patients)
                result.Patients.Add(new { pawn_id = p.thingIDNumber, name = p.LabelShort, downed = p.Downed, drafted = p.Drafted,
                    mental_state = p.MentalStateDef?.defName, current_job = p.CurJobDef?.defName, in_bed = p.InBed(),
                    tendable_now = p.health.hediffSet.hediffs.Any(h => h.Visible && h.TendableNow()), life_threatening = p.health.hediffSet.hediffs.Any(h => h.Visible && h.IsCurrentlyLifeThreatening),
                    medical_care = p.playerSettings?.medCare.ToString(), bed_rest_priority = p.workSettings?.GetPriority(RestWork),
                    temperature = p.Position.GetTemperature(map), roof = map.roofGrid.RoofAt(p.Position)?.defName,
                    comfortable_min=p.GetStatValue(StatDefOf.ComfyTemperatureMin), comfortable_max=p.GetStatValue(StatDefOf.ComfyTemperatureMax),
                    gases=Enum.GetValues(typeof(GasType)).Cast<GasType>().ToDictionary(g => g.ToString(),g => (int)map.gasGrid.DensityAt(p.Position,g)),
                    food = p.needs?.food?.CurLevelPercentage,
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
            foreach (Pawn worker in patients.Where(Idle))
            {
                foreach (var pair in Givers)
                {
                    IEnumerable<Thing> targets = pair.Key == "clean"
                        ? map.listerThings.AllThings.Where(t => t is Filth && careRooms.Contains(t.GetRoom()) && (t.GetRoom()?.GetStat(RoomStatDefOf.Cleanliness) ?? 0f) < 0f)
                        : patients.Cast<Thing>();
                    foreach (Thing target in targets) foreach (string giver in pair.Value)
                        if (NativeScanner(worker, target, pair.Key, giver) != null)
                            result.Options.Add(new ResilienceOptionDto { Kind=pair.Key, WorkerId=worker.thingIDNumber, TargetId=target.thingIDNumber,
                                Giver=giver, Worker=worker.LabelShort, Target=target.LabelShort, MedicineSkill=worker.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0,RoomCleanliness=target.GetRoom()?.GetStat(RoomStatDefOf.Cleanliness) });
                }
                foreach (Thing drug in map.listerThings.AllThings.Where(t => t.def.defName == "Penoxycyline"))
                    if (Preventible(worker, drug)) result.Options.Add(new ResilienceOptionDto {Kind="prevent", WorkerId=worker.thingIDNumber,TargetId=drug.thingIDNumber,Worker=worker.LabelShort,Target=drug.LabelShort});
            }
            foreach (Pawn patient in patients.Where(p => p.IsColonistPlayerControlled && !p.Drafted && !p.InMentalState && NeedsCare(p)
                && p.workSettings != null && !p.WorkTypeIsDisabled(RestWork) && p.workSettings.GetPriority(RestWork) != 1))
                result.Options.Add(new ResilienceOptionDto {Kind="rest", WorkerId=patient.thingIDNumber,TargetId=patient.thingIDNumber,Worker=patient.LabelShort,Target=patient.LabelShort});
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
            if (request.Kind == "rest" && worker == target && worker.IsColonistPlayerControlled && !worker.Drafted && !worker.InMentalState
                && NeedsCare(worker) && worker.workSettings != null && !worker.WorkTypeIsDisabled(RestWork)
                && worker.workSettings.GetPriority(RestWork) != 1)
            { worker.workSettings.SetPriority(RestWork,1); result.Applied=true; result.Reason="bed_rest_prioritized; autonomous_job_required"; }
            else
            {
                Job job = request.Kind == "prevent" && Preventible(worker,target) ? JobMaker.MakeJob(JobDefOf.Ingest,target) : NativeJob(worker,target,request.Kind,request.Giver);
                if (job != null)
                { if (request.Kind == "prevent") job.count=1;
                    result.Applied=worker.jobs.TryTakeOrderedJob(job); result.Reason=result.Applied ? "normal_job_scheduled; completion_unobserved" : "job_rejected"; }
                else result.Reason="selection_no_longer_feasible";
            }
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}
