using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;
using RIMAPI.Core;
using RIMAPI.Models;

namespace RIMAPI.Helpers
{
    public static class SocietyAutomationHelper
    {
        // Player-facing policies only. Existing work givers perform the actual care/social jobs.
        private static readonly string[] Care = { "NoMeds", "HerbalOrWorse", "NormalOrWorse", "Best" };
        private static bool NeedsCare(Pawn p) => p.health.hediffSet.hediffs.Any(h => h.IsCurrentlyLifeThreatening || h.TendableNow()
            || (h.TryGetComp<HediffComp_Immunizable>() is HediffComp_Immunizable immunity && immunity.Immunity < 1));
        private static bool ProtectedActivity(Pawn p) => p.Downed || p.Drafted || p.InMentalState || p.CurJobDef == JobDefOf.TendPatient
            || p.CurJobDef == JobDefOf.Rescue || p.CurJobDef == JobDefOf.FeedPatient || p.CurJobDef == JobDefOf.DoBill;
        private static bool AvailableStaff(Pawn p, WorkTypeDef work) => p.IsColonistPlayerControlled && !ProtectedActivity(p)
            && !NeedsCare(p) && !p.WorkTypeIsDisabled(work) && (p.workSettings?.GetPriority(work) ?? 0) > 0;
        private static List<string> PrisonerOptions(Pawn p)
        {
            var result = new List<string>();
            if (!p.IsPrisonerOfColony || p.guest == null || !p.DevelopmentalStage.Adult()) return result;
            result.Add("MaintainOnly");
            if (!p.IsWildMan() && p.guest.Recruitable)
            { result.Add("AttemptRecruit"); if (p.guest.resistance > 0) result.Add("ReduceResistance"); }
            if (ModsConfig.IdeologyActive && !Find.IdeoManager.classicMode && p.Ideo != null)
                if (p.Map.mapPawns.FreeColonists.Any(w => AvailableStaff(w, WorkTypeDefOf.Warden) && w.Ideo != null && w.Ideo != p.Ideo))
                    result.Add("Convert");
            return result.Where(n => DefDatabase<PrisonerInteractionModeDef>.GetNamedSilentFail(n) != null).ToList();
        }
        public static ApiResult<SocietyContextDto> Context(int mapId)
        {
            var map = MapHelper.GetMapByID(mapId);
            if (map == null) return ApiResult<SocietyContextDto>.Fail("Map not found.");
            var result = new SocietyContextDto();
            foreach (var group in map.listerThings.AllThings.Where(t => t.def.IsMedicine && !t.Destroyed).GroupBy(t => t.def.defName))
                result.Medicine[group.Key] = group.Sum(t => t.stackCount);
            foreach (var p in map.mapPawns.AllPawnsSpawned.Where(p => p.RaceProps.Humanlike && (p.IsColonistPlayerControlled || p.IsPrisonerOfColony)))
            {
                var row = new SocietyPersonDto { PawnId = p.thingIDNumber, Name = p.LabelShort, Dead = p.Dead,
                    Downed = p.Downed, Drafted = p.Drafted, MentalState = p.InMentalState, CurrentJob = p.CurJobDef?.defName,
                    MedicineSkill = p.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0,
                    SocialSkill = p.skills?.GetSkill(SkillDefOf.Social)?.Level ?? 0,
                    CanDoctor = AvailableStaff(p, WorkTypeDefOf.Doctor), CanWarden = AvailableStaff(p, WorkTypeDefOf.Warden),
                    DoctorPriority = p.workSettings?.GetPriority(WorkTypeDefOf.Doctor) ?? 0,
                    WardenPriority = p.workSettings?.GetPriority(WorkTypeDefOf.Warden) ?? 0,
                    Certainty = p.ideo?.Certainty,
                    MinorBreakThreshold = p.mindState?.mentalBreaker?.BreakThresholdMinor,
                    MedicalCare = p.playerSettings?.medCare.ToString(),
                    MedicalAttention = NeedsCare(p),
                    PrisonerMode = p.IsPrisonerOfColony ? p.guest?.ExclusiveInteractionMode?.defName : null,
                    Resistance = p.IsPrisonerOfColony ? (float?)p.guest.resistance : null,
                    PrisonerOptions = PrisonerOptions(p), Ideology = p.Ideo?.name };
                if (p.playerSettings != null) row.CareOptions.AddRange(Care);
                if (p.needs != null) foreach (var n in p.needs.AllNeeds)
                    row.Needs.Add(new SocietyNeedDto { DefName = n.def.defName, Level = n.CurLevelPercentage, Description = n.def.description });
                if (p.needs?.mood?.thoughts != null)
                { var thoughts = new List<Thought>(); p.needs.mood.thoughts.GetAllMoodThoughts(thoughts);
                    row.Thoughts.AddRange(thoughts.Select(t => new SocietyThoughtDto { DefName = t.def.defName, Label = t.LabelCap, MoodOffset = t.MoodOffset() })); }
                foreach (var h in p.health.hediffSet.hediffs)
                { var immune = h.TryGetComp<HediffComp_Immunizable>();
                    row.Conditions.Add(new SocietyConditionDto { DefName = h.def.defName, Severity = h.Severity,
                        Immunity = immune == null ? (float?)null : immune.Immunity, LifeThreatening = h.IsCurrentlyLifeThreatening }); }
                if (p.Ideo != null) row.Beliefs.AddRange(p.Ideo.PreceptsListForReading.Select(precept => precept.def.defName + ": " + precept.def.description));
                if (p.learning != null) row.LearningDesires.AddRange(p.learning.ActiveLearningDesires.Select(d => d.defName));
                if (p.IsColonistPlayerControlled && p.timetable != null)
                    for (int h = 0; h < 24; h++) row.Timetable.Add(p.timetable.GetAssignment(h).defName);
                result.People.Add(row);
            }
            return ApiResult<SocietyContextDto>.Ok(result);
        }
        public static ApiResult<CapabilityOrderResultDto> Configure(SocietyPolicyRequestDto request)
        {
            var p = MapHelper.GetThingOnMapById(request.MapId, request.PawnId) as Pawn;
            var result = new CapabilityOrderResultDto { TargetId = request.PawnId };
            if (p == null || p.Dead || !p.Spawned || !p.RaceProps.Humanlike || (!p.IsColonistPlayerControlled && !p.IsPrisonerOfColony))
                return ApiResult<CapabilityOrderResultDto>.Fail("Living controlled human not found on this map.");
            if (request.Kind == "medical" && p.playerSettings != null && Care.Contains(request.Value)
                && NeedsCare(p)
                && Enum.TryParse(request.Value, out MedicalCareCategory care))
            { p.playerSettings.medCare = care; result.Applied = true; result.Reason = "medicine_ceiling_set; normal_doctor_jobs_still_required"; }
            else if (request.Kind == "prisoner" && PrisonerOptions(p).Contains(request.Value))
            { p.guest.SetExclusiveInteraction(DefDatabase<PrisonerInteractionModeDef>.GetNamed(request.Value));
                result.Applied = true; result.Reason = "prisoner_policy_set; normal_warden_jobs_still_required"; }
            else if (request.Kind == "timetable" && p.IsColonistPlayerControlled && p.timetable != null
                && !ProtectedActivity(p)
                && request.Value == "Joy" && request.Hour.HasValue && request.Hour.Value >= 0 && request.Hour.Value < 24
                && p.timetable.GetAssignment(request.Hour.Value) == TimeAssignmentDefOf.Work
                && p.needs.AllNeeds.Any(n => (n.def.defName == "Learning" && n.CurLevelPercentage < .9f) || (n.def.defName == "Joy" && n.CurLevelPercentage < .5f)))
            { p.timetable.SetAssignment(request.Hour.Value, TimeAssignmentDefOf.Joy); result.Applied = true;
                result.Reason = "one_work_hour_changed; normal_learning_or_recreation_jobs_still_required"; }
            else result.Reason = "policy_no_longer_feasible";
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}
