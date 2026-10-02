using System;
using System.Globalization;
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
    public static class SocietyNativeHelper
    {
        private static readonly Dictionary<string,string[]> Jobs=new Dictionary<string,string[]>
        {
            {"baby_safe",new[]{"BringBabyToSafety"}},
            {"baby_feed",new[]{"BreastfeedBaby","BottleFeedBaby","CarryToBreastfeed"}},
            {"baby_play",new[]{"PlayWithBaby"}},
            {"teach",new[]{"ChildcarerTeach"}},
            {"hemogen_feed",new[]{"FeedHemogen","DeliverHemogenToPrisoner"}}
        };
        public static bool Idle(Pawn p) => p.IsColonistPlayerControlled && !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState
            && !new[]{"BottleFeedBaby","BreastfeedCarryToMom","BringBabyToSafetyUnforced","CarryToMomAfterBirth","BabySuckle","BabyPlay","PlayStatic","PlayWalking","PlayToys","Lessonreceiving","TendPatient","Rescue","FeedPatient","DoBill","Deathrest","Breastfeed","BottlefeedBaby","BringBabyToSafety","Lessongiving","PrisonerInterrogateIdentity","Ingest"}.Contains(p.CurJobDef?.defName)
            && !p.health.hediffSet.hediffs.Any(h => h.Visible && (h.TendableNow() || h.IsCurrentlyLifeThreatening
                || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable i && i.Immunity < 1)));
        private static Dictionary<string,string> Effects(string benefit,string risk,string cost,string inaction,string uncertainty)
            => new Dictionary<string,string>{{"benefit",benefit},{"risk",risk},{"cost",cost},{"inaction",inaction},{"uncertainty",uncertainty}};
        private static SocietyNativeOptionDto Option(string kind,Pawn patient,Pawn worker,string value,int target,string label,Dictionary<string,string> effects)
            => new SocietyNativeOptionDto{Kind=kind,PawnId=patient.thingIDNumber,WorkerId=worker?.thingIDNumber ?? 0,TargetId=target,Value=value,Label=label,Effects=effects};
        private static WorkGiver Scanner(Pawn worker,Pawn patient,string kind,string giver)
        {
            if (!Idle(worker) || !Jobs.TryGetValue(kind,out string[] allowed) || !allowed.Contains(giver)) return null;
            WorkGiverDef def=DefDatabase<WorkGiverDef>.GetNamedSilentFail(giver);
            if (def == null || worker.WorkTypeIsDisabled(def.workType) || (worker.workSettings?.GetPriority(def.workType) ?? 0) == 0
                || (def.requiredCapacities != null && def.requiredCapacities.Any(c => !worker.health.capacities.CapableOf(c)))
                || !worker.CanReach(patient,PathEndMode.Touch,Danger.Some)) return null;
            if (kind != "baby_safe" && !ResilienceAutomationHelper.RoutineRouteSafe(worker,patient)) return null;
            // Native play candidates use random order; preserve gameplay RNG while reading.
            Rand.PushState(17591);
            try
            {
                WorkGiver giverWorker=def.Worker;
                if(giverWorker.ShouldSkip(worker,false))return null;
                bool feasible;
                if(giverWorker is WorkGiver_BringBabyToSafety)feasible=ChildcareUtility.FindUnsafeBaby(worker,AutofeedMode.Childcare)==patient;
                else if(giverWorker is WorkGiver_Breastfeed)feasible=ChildcareUtility.CanMomAutoBreastfeedBabyNow(worker,patient,false,out var reason) && patient.mindState.AutofeedSetting(worker)==AutofeedMode.Childcare;
                else if(giverWorker is WorkGiver_Warden_DeliverHemogen)
                {
                    var gene=patient.genes?.GetFirstGeneOfType<Gene_Hemogen>();var room=patient.GetRoom();
                    feasible=patient.IsPrisonerOfColony && patient.guest.PrisonerIsSecure && !patient.InAggroMentalState && !patient.IsFormingCaravan()
                        && !patient.IsForbidden(worker) && worker.CanReserveAndReach(patient,PathEndMode.OnCell,worker.NormalMaxDanger())
                        && patient.guest.CanBeBroughtFood && patient.Position.IsInPrisonCell(patient.Map) && !WardenFeedUtility.ShouldBeFed(patient)
                        && gene!=null && gene.hemogenPacksAllowed && gene.ShouldConsumeHemogenNow()
                        && patient.carryTracker.CarriedCount(ThingDefOf.HemogenPack)==0 && patient.inventory.Count(ThingDefOf.HemogenPack)==0
                        && !patient.Map.listerThings.ThingsOfDef(ThingDefOf.HemogenPack).Any(t=>t.GetRoom()==room)
                        && patient.Map.listerThings.ThingsOfDef(ThingDefOf.HemogenPack).Any(t=>t.GetRoom()!=room && !t.IsForbidden(worker) && worker.CanReserveAndReach(t,PathEndMode.OnCell,Danger.Some));
                }
                else if(giverWorker is WorkGiver_FeedBabyManually)
                {
                    feasible=ChildcareUtility.CanSuckle(patient,out var reason1) && ChildcareUtility.CanSuckleNow(patient,out var reason2)
                        && ChildcareUtility.CanHaulBabyNow(worker,patient,false,out var reason3) && ChildcareUtility.WantsSuckle(patient,out var reason4)
                        && patient.needs.food!=null && !ChildcareUtility.CanBreastfeedMothers(patient).Any(m=>ChildcareUtility.CanMomAutoBreastfeedBabyNow(m,patient,false,out var reason5));
                    if(feasible)feasible=giverWorker is WorkGiver_BottleFeedBaby ? ChildcareUtility.FindBabyFoodForBaby(worker,patient)!=null
                        : ChildcareUtility.CanBreastfeedMothers(patient).Any(m=>ChildcareUtility.CanHaulBabyToDownedMomToBreastfeedNow(worker,m,patient,false,out var reason6));
                }
                else feasible=giverWorker is WorkGiver_Scanner scanner && scanner.GetType().GetMethod("HasJobOnThing").DeclaringType!=typeof(WorkGiver_Scanner) && scanner.HasJobOnThing(worker,patient,false);
                return feasible ? giverWorker : null;
            }
            finally {Rand.PopState();}
        }
        private static bool JobSafe(Pawn worker,Job job,Pawn exposedBaby=null)
        {
            if (job == null) return false;
            return new[]{job.targetA,job.targetB,job.targetC}.Where(t => t.HasThing && t.Thing.Spawned && t.Thing != exposedBaby)
                .All(t => ResilienceAutomationHelper.RoutineRouteSafe(worker,t.Thing));
        }
        public static void AddContext(Map map,SocietyContextDto result)
        {
            var people=map.mapPawns.AllPawnsSpawned.Where(p => p.RaceProps.Humanlike && (p.IsColonistPlayerControlled || p.IsPrisonerOfColony)).ToList();
            result.Facilities=new {school_desks=map.listerThings.AllThings.Where(t => t.def.defName == "SchoolDesk" || t.def.defName == "Blackboard").Select(t => new{id=t.thingIDNumber,def_name=t.def.defName,temperature=t.Position.GetTemperature(map),roofed=t.Position.Roofed(map)}).ToList(),
                baby_food=map.listerThings.AllThings.Where(t => t.def.defName == "BabyFood" || t.def.defName == "Milk").GroupBy(t=>t.def.defName).ToDictionary(g=>g.Key,g=>g.Sum(t=>t.stackCount))};
            foreach (Pawn person in people)
            {
                SocietyPersonDto row=result.People.FirstOrDefault(p => p.PawnId == person.thingIDNumber);
                if (row != null)
                {
                    row.Development=new {age=person.ageTracker.AgeBiologicalYearsFloat,stage=person.DevelopmentalStage.ToString(),awake=person.Awake(),growth_tier=person.ageTracker.GrowthTier,
                        growth_points=person.ageTracker.growthPoints,childcare_priority=DefDatabase<WorkTypeDef>.GetNamedSilentFail("Childcare") is WorkTypeDef childcare ? person.workSettings?.GetPriority(childcare) : null,
                        learning_level=person.needs.TryGetNeed<Need_Learning>()?.CurLevelPercentage,play_level=person.needs.play?.CurLevelPercentage,
                        lesson_pending=ModsConfig.BiotechActive && SchoolUtility.NeedsTeacher(person)};
                    row.Drugs=DrugContext(person,map);
                    var deathrest=person.genes?.GetFirstGeneOfType<Gene_Deathrest>();var hemogen=person.genes?.GetFirstGeneOfType<Gene_Hemogen>();
                    row.Genes=new{deathrest=deathrest == null ? null : (object)new{active=deathrest.Active,need=deathrest.DeathrestNeed?.CurLevelPercentage,resting=deathrest.DeathrestNeed?.Deathresting,
                        progress=deathrest.DeathrestPercent,min_ticks=deathrest.MinDeathrestTicks,auto_wake=deathrest.autoWake,bound_buildings=deathrest.BoundBuildings.Select(t=>t.def.defName).ToList()},
                        hemogen=hemogen == null ? null : (object)new{active=hemogen.Active,level=hemogen.ValuePercent,packs_allowed=hemogen.hemogenPacksAllowed},
                        dependencies=person.genes?.GenesListForReading.OfType<Gene_ChemicalDependency>().Where(g=>g.Active).Select(g=>new{chemical=g.def.chemical.defName,last_ingested_tick=g.lastIngestedTick,description=g.def.description}).ToList()};
                }
                if (ModsConfig.BiotechActive)
                {
                    foreach (Pawn worker in people.Where(p=>p != person && Idle(p))) foreach (var pair in Jobs) foreach(string giver in pair.Value)
                        if (Scanner(worker,person,pair.Key,giver) != null)
                            result.NativeOptions.Add(Option(pair.Key,person,worker,giver,0,$"{worker.LabelShort}: {giver} for {person.LabelShort}",
                                Effects($"{person.LabelShort} {pair.Key}; food={person.needs.food?.CurLevelPercentage:0.00} play={person.needs.play?.CurLevelPercentage:0.00}",
                                    pair.Key == "baby_safe" ? "Rescuer can face temperature/fallout exposure" : "Supplies/path/awake state can change", "Caregiver labor; feeding consumes food/milk/hemogen", "Unmet hunger/play/learning/exposure persists", "Normal job must complete; no instant need gain")));
                    DeathrestOptions(person,map,result);
                }
                DrugOptions(person,map,result);
            }
            result.DrugPolicies=Current.Game.drugPolicyDatabase.AllPolicies.Select(p=>(object)new{id=p.id,label=p.label,entries=Enumerable.Range(0,p.Count).Select(i=>new{drug=p[i].drug.defName,addiction=p[i].allowedForAddiction,joy=p[i].allowedForJoy,scheduled=p[i].allowScheduled,days=p[i].daysFrequency,mood_below=p[i].onlyIfMoodBelow,joy_below=p[i].onlyIfJoyBelow,inventory=p[i].takeToInventory}).ToList()}).ToList();
            SocietyGrowthHelper.AddContext(map,result);
            SocietyMedicalHelper.AddContext(map,result);
        }
        private static void DeathrestOptions(Pawn person,Map map,SocietyContextDto result)
        {
            Gene_Deathrest gene=person.genes?.GetFirstGeneOfType<Gene_Deathrest>();
            if (gene == null || !gene.Active || !person.IsColonistPlayerControlled) return;
            foreach(bool auto in new[]{true,false}) if (auto != gene.autoWake)
                result.NativeOptions.Add(Option("deathrest_wake",person,null,auto ? "auto" : "manual",0,$"{person.LabelShort} { (auto ? "wake when complete" : "remain until manually woken")}",
                    Effects($"autoWake={auto}; progress={gene.DeathrestPercent:0.00}","Early interruption loses deathrest benefits","Resting pawn unavailable for work/defense","Current wake policy continues","Completion depends on efficiency and linked buildings")));
            if (!Idle(person) || !person.CanDeathrest() || gene.DeathrestNeed == null || gene.DeathrestNeed.Deathresting || gene.DeathrestNeed.CurLevelPercentage >= .25f) return;
            foreach(Building_Bed bed in map.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Where(b => b.def.building.bed_humanlike
                && b.CompAssignableToPawn.CanAssignTo(person).Accepted && (b.IsOwner(person) || (b.CompAssignableToPawn.HasFreeSlot && RestUtility.BedOwnerWillShare(b,person,person.guest.GuestStatus)))
                && b.OccupiedRect().All(c=>c.Roofed(map)) && RestUtility.IsValidBedFor(b,person,person,true,false,false,person.GuestStatus)
                && ResilienceAutomationHelper.RoutineRouteSafe(person,b)))
                result.NativeOptions.Add(Option("deathrest",person,person,"start",bed.thingIDNumber,$"{person.LabelShort}: deathrest in {bed.LabelShort}",
                    Effects($"deathrest need={gene.DeathrestNeed.CurLevelPercentage:0.00}; restores capacity","Multi-day incapacity; interruption loses bonuses",$"minimum {gene.MinDeathrestTicks} ticks", "Exhaustion and capacity loss continue", "Duration depends on bed efficiency and building supplies")));
        }
        private static object DrugContext(Pawn person,Map map)
        {
            var policy=person.drugs?.CurrentPolicy;
            return new {policy_id=policy?.id,policy=policy?.label,traits=person.story?.traits.allTraits.Select(t=>t.def.defName).ToList(),
                conditions=person.health.hediffSet.hediffs.Where(h=>h.Visible && (h is Hediff_Addiction || h is Hediff_ChemicalDependency || h.def.defName.IndexOf("Tolerance",StringComparison.OrdinalIgnoreCase)>=0 || h.def.defName=="DrugOverdose" || h.def.defName.IndexOf("Luciferium",StringComparison.OrdinalIgnoreCase)>=0)).Select(h=>new{def_name=h.def.defName,severity=h.Severity,description=h.def.description}).ToList(),
                entries=policy == null ? null : Enumerable.Range(0,policy.Count).Select(i=>new{drug=policy[i].drug.defName,allowed_addiction=policy[i].allowedForAddiction,allowed_joy=policy[i].allowedForJoy,
                    scheduled=policy[i].allowScheduled,days=policy[i].daysFrequency,mood_below=policy[i].onlyIfMoodBelow,joy_below=policy[i].onlyIfJoyBelow,inventory=policy[i].takeToInventory,
                    chemical=DrugStatsUtility.GetChemical(policy[i].drug)?.defName,addictiveness=DrugStatsUtility.GetDrugComp(policy[i].drug)?.addictiveness,
                    overdose=DrugStatsUtility.GetDrugComp(policy[i].drug)?.CanCauseOverdose,safe_interval=DrugStatsUtility.GetSafeDoseInterval(policy[i].drug,person.ageTracker.CurLifeStage.bodySizeFactor),
                    stock=map.listerThings.AllThings.Where(t=>t.def==policy[i].drug && !t.IsForbidden(person)).Sum(t=>t.stackCount),scheduled_allowed=person.drugs.AllowedToTakeScheduledEver(policy[i].drug)}).ToList()};
        }
        private static void DrugOptions(Pawn person,Map map,SocietyContextDto result)
        {
            if (!person.IsColonistPlayerControlled || person.drugs == null || !person.DevelopmentalStage.Adult()) return;
            DrugPolicy current=person.drugs.CurrentPolicy;
            foreach(DrugPolicy policy in Current.Game.drugPolicyDatabase.AllPolicies.Where(p=>p != current))
                result.NativeOptions.Add(Option("drug_policy",person,null,policy.id.ToString(),0,$"{person.LabelShort}: {policy.label}",
                    Effects($"{policy.label}: "+string.Join(",",Enumerable.Range(0,policy.Count).Select(i=>policy[i]).Where(e=>e.allowScheduled || e.allowedForJoy || e.allowedForAddiction).Select(e=>$"{e.drug.defName}: addiction={e.allowedForAddiction} joy={e.allowedForJoy} schedule={(e.allowScheduled ? e.daysFrequency.ToString("0.0") : "off")}")),
                        "Visible dependency/addiction="+string.Join(",",person.health.hediffSet.hediffs.Where(h=>h.Visible && (h is Hediff_Addiction || h is Hediff_ChemicalDependency || h.def.defName.IndexOf("Luciferium",StringComparison.OrdinalIgnoreCase)>=0)).Select(h=>h.def.defName))+"; withdrawal/overdose/ideology",
                        "Dose stock/inventory="+string.Join(",",Enumerable.Range(0,policy.Count).Select(i=>policy[i]).Where(e=>e.allowScheduled || e.takeToInventory>0).Select(e=>$"{e.drug.defName}:{map.listerThings.AllThings.Where(t=>t.def==e.drug && !t.IsForbidden(person)).Sum(t=>t.stackCount)} carry={e.takeToInventory}")),
                        $"Current {current.label} permissions continue","Traits may ignore restrictions; scheduled jobs may lack supplies")));
            for(int i=0;i<current.Count;i++)
            {
                var entry=current[i];ThingDef drug=entry.drug;var comp=DrugStatsUtility.GetDrugComp(drug);var chemical=comp?.chemical;
                bool dependent=person.health.hediffSet.hediffs.Any(h=>h.Visible && ((h is Hediff_Addiction a && DrugStatsUtility.GetNeed(drug)!=null && a.def.chemicalNeed == DrugStatsUtility.GetNeed(drug))
                    || (h is Hediff_ChemicalDependency c && c.chemical==chemical)));
                var presets=new List<string>();
                if (entry.allowedForAddiction || entry.allowedForJoy || entry.allowScheduled || entry.takeToInventory > 0) presets.Add("disabled");
                if (dependent && (!entry.allowedForAddiction || entry.allowedForJoy || entry.allowScheduled)) presets.Add("addiction");
                bool stock=map.listerThings.AllThings.Any(t=>t.def==drug && !t.IsForbidden(person));
                if (stock && (drug.defName=="Penoxycyline" || dependent))
                {
                    float days=drug.defName=="Penoxycyline" ? 5f : drug.defName=="Luciferium" ? 6f : Math.Max(1f,entry.daysFrequency);
                    string schedule="schedule:"+days.ToString(CultureInfo.InvariantCulture);
                    if (!entry.allowScheduled || entry.daysFrequency != days || entry.allowedForJoy) presets.Add(schedule);
                }
                float safe=DrugStatsUtility.GetSafeDoseInterval(drug,person.ageTracker.CurLifeStage.bodySizeFactor);
                if (stock && drug.IsNonMedicalDrug && !dependent && person.CanTakeDrug(drug) && safe >= 0 && safe <= 50 && comp != null && comp.addictiveness < 1f)
                {
                    float days=Math.Max(1f,(float)Math.Ceiling(safe));
                    if (!entry.allowScheduled || entry.daysFrequency != days || entry.onlyIfMoodBelow != .35f || entry.allowedForJoy)
                        presets.Add("mood:"+days.ToString(CultureInfo.InvariantCulture));
                }
                foreach(string preset in presets)
                    result.NativeOptions.Add(Option("drug_entry",person,null,drug.defName+"|"+preset,0,$"{person.LabelShort} {drug.label}: {preset}",
                        Effects($"{drug.defName} {preset}; dependent={dependent}",dependent && preset=="disabled" ? "Withdrawal/genetic deficiency; luciferium need can be fatal" : $"addiction={comp?.addictiveness} overdose={comp?.CanCauseOverdose}; traits/ideology",
                            "Per-pawn copy; doses/inventory consume stock", "Current addiction/recreation/schedule permissions continue", "Native dose interval is not guaranteed safety; body/gene effects and excess doses matter")));
            }
        }
        private static void SetDrugEntry(Pawn person,string value)
        {
            string[] parts=value.Split('|');ThingDef drug=DefDatabase<ThingDef>.GetNamed(parts[0]);string preset=parts[1];
            string label="Laya personal "+person.thingIDNumber;
            DrugPolicy policy=person.drugs.CurrentPolicy;
            if (policy.label != label || PawnsFinder.AllMapsWorldAndTemporary_Alive.Any(p=>p != person && p.drugs?.CurrentPolicy == policy))
            {DrugPolicy copy=Current.Game.drugPolicyDatabase.AllPolicies.FirstOrDefault(p=>p.label==label && !PawnsFinder.AllMapsWorldAndTemporary_Alive.Any(a=>a.drugs?.CurrentPolicy==p));
                if(copy==null)copy=Current.Game.drugPolicyDatabase.MakeNewDrugPolicy();copy.CopyFrom(policy);copy.label=label;policy=copy;person.drugs.CurrentPolicy=policy;}
            var entry=policy[drug];entry.allowedForJoy=false;entry.allowedForAddiction=preset!="disabled";entry.allowScheduled=preset.StartsWith("schedule:") || preset.StartsWith("mood:");
            entry.takeToInventory=0;
            if(entry.allowScheduled){entry.daysFrequency=float.Parse(preset.Split(':')[1],CultureInfo.InvariantCulture);entry.onlyIfMoodBelow=preset.StartsWith("mood:") ? .35f : 1f;entry.onlyIfJoyBelow=1f;}
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(SocietyNativeRequestDto request)
        {
            Map map=MapHelper.GetMapByID(request.MapId);var result=new CapabilityOrderResultDto{TargetId=request.PawnId};
            if(map==null)return ApiResult<CapabilityOrderResultDto>.Fail("Map not found.");
            if(request.Kind=="growth")return SocietyGrowthHelper.Execute(request);
            var live=new SocietyContextDto();AddContext(map,live);
            if(!live.NativeOptions.Any(o=>o.Kind==request.Kind && o.PawnId==request.PawnId && o.WorkerId==request.WorkerId && o.TargetId==request.TargetId && o.LetterId==request.LetterId && o.Value==request.Value))
            {result.Reason="native_option_no_longer_feasible";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
            Pawn person=MapHelper.GetThingOnMapById(request.MapId,request.PawnId) as Pawn;
            Pawn worker=MapHelper.GetThingOnMapById(request.MapId,request.WorkerId) as Pawn;
            if(Jobs.ContainsKey(request.Kind))
            {
                var scanner=Scanner(worker,person,request.Kind,request.Value);
                Job lesson= request.Kind=="teach" ? person.CurJob : null;LocalTargetInfo oldTeacher=lesson?.targetB ?? LocalTargetInfo.Invalid;
                Job job=scanner is WorkGiver_Scanner scanning ? scanning.JobOnThing(worker,person,false) : scanner?.NonScanJob(worker);
                if(job != null && JobSafe(worker,job,request.Kind=="baby_safe" ? person : null))result.Applied=worker.jobs.TryTakeOrderedJob(job);
                if(!result.Applied && lesson != null && person.CurJob==lesson)lesson.SetTarget(TargetIndex.B,oldTeacher);
                result.Reason=result.Applied ? "normal_job_scheduled; outcome_unobserved" : "job_no_longer_safe_or_feasible";
            }
            else if(request.Kind=="drug_policy"){person.drugs.CurrentPolicy=Current.Game.drugPolicyDatabase.AllPolicies.First(p=>p.id.ToString()==request.Value);result.Applied=true;result.Reason="existing_policy_assigned; autonomous_jobs_required";}
            else if(request.Kind=="drug_entry"){SetDrugEntry(person,request.Value);result.Applied=true;result.Reason="personal_policy_entry_set; autonomous_jobs_required";}
            else if(request.Kind=="deathrest_wake"){person.genes.GetFirstGeneOfType<Gene_Deathrest>().autoWake=request.Value=="auto";result.Applied=true;result.Reason="deathrest_wake_policy_set";}
            else if(request.Kind=="deathrest")
            {var bed=MapHelper.GetThingOnMapById(request.MapId,request.TargetId);var job=JobMaker.MakeJob(JobDefOf.Deathrest,bed);job.forceSleep=true;result.Applied=person.jobs.TryTakeOrderedJob(job,JobTag.Misc);result.Reason="normal_deathrest_job_scheduled; completion_unobserved";}
            else if(request.Kind=="growth_prepare")return SocietyGrowthHelper.Execute(request);
            else if(request.Kind=="medical_recipe")return SocietyMedicalHelper.Execute(request);
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}
