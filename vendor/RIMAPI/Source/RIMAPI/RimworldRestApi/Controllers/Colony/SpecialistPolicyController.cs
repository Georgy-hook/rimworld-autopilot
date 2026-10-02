using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using Verse;
namespace RIMAPI.Controllers
{
    public class SpecialistPolicyController
    {
        private static Dialog_ChangeDryadCaste Caste => Find.WindowStack.Windows.OfType<Dialog_ChangeDryadCaste>().FirstOrDefault();
        private static T Field<T>(object o, string key) => (T)AccessTools.Field(o.GetType(), key).GetValue(o);
        private static bool TreeAvailable(Thing t) => t.Spawned && !t.Position.Fogged(t.Map) && t.TryGetComp<CompTreeConnection>()?.ConnectedPawn is Pawn p && p.Spawned && p.Map == t.Map && p.Faction == Faction.OfPlayer;
        private static IEnumerable<Command_Action> Capture(Thing t) {
            var comp = t.TryGetComp<CompHoldingPlatformTarget>();
            if (comp == null) return Enumerable.Empty<Command_Action>();
            return comp.CompGetGizmosExtra().OfType<Command_Action>().Where(c => !c.Disabled && c.action != null && !c.defaultLabel.StartsWith("DEV"));
        }
        [Get("/api/v1/specialists/policies")]
        public async Task Context(HttpListenerContext context) {
            var choices = new List<object>(); var dialog = Caste; int mapId=RequestParser.GetMapId(context);
            if (dialog != null) {
                foreach (var mode in Field<List<GauranlenTreeModeDef>>(dialog,"allDryadModes"))
                    if (mode != Field<GauranlenTreeModeDef>(dialog,"currentMode") && (bool)AccessTools.Method(typeof(Dialog_ChangeDryadCaste),"MeetsRequirements").Invoke(dialog,new object[] { mode }))
                        choices.Add(new { operation="caste", value=mode.defName, label=mode.LabelCap.ToString(), description=mode.Description,
                            warning="Native confirmation; connector changes caste through work and dryads need actual cocoon time." });
                choices.Add(new { operation="cancel", label="Cancel dryad caste choice" });
            } else foreach (var map in Find.Maps.Where(m => m.uniqueID==mapId)) {
                if (ModsConfig.RoyaltyActive) foreach (var pawn in map.mapPawns.FreeColonistsSpawned.Where(p => p.HasPsylink && !SpecialistNativeSafety.Protected(p))) {
                    foreach (int percent in new[] { 25,50,75,95 }) if (Math.Abs(pawn.psychicEntropy.TargetPsyfocus-percent/100f) > .01f)
                        choices.Add(new { map_id=map.uniqueID, operation="focus", pawn_id=pawn.thingIDNumber, value=percent.ToString(), label=pawn.LabelShort+" desired psyfocus "+percent+"%",
                            current=pawn.psychicEntropy.CurrentPsyfocus, desired=pawn.psychicEntropy.TargetPsyfocus, current_job=pawn.CurJobDef?.defName,
                            description="Native desired-focus policy; automatic meditation needs timetable opportunity and a valid personal focus. Higher focus consumes more meditation labor." });
                    if (pawn.timetable != null && MeditationUtility.CanMeditateNow(pawn))
                        for (int hour=0; hour<24; hour++) if (pawn.timetable.GetAssignment(hour)==TimeAssignmentDefOf.Work)
                            choices.Add(new { map_id=map.uniqueID, operation="meditation_hour", pawn_id=pawn.thingIDNumber, value=hour.ToString(), label=pawn.LabelShort+" Work hour "+hour+" → Meditate",
                                current_job=pawn.CurJobDef?.defName, description="Trades one work hour for native meditation. Sleep and recreation assignments are preserved; no focus is granted instantly." });
                }
                if (ModsConfig.IdeologyActive) foreach (var t in map.listerThings.AllThings.Where(TreeAvailable)) {
                    var tree=t.TryGetComp<CompTreeConnection>();
                    foreach (int percent in new[] { 25,50,75,100 }) if (Math.Abs(tree.DesiredConnectionStrength-percent/100f)>.01f)
                        choices.Add(new { map_id=map.uniqueID, operation="pruning", thing_id=t.thingIDNumber, value=percent.ToString(), label=t.LabelCap+" desired strength "+percent+"%",
                            description="Native pruning policy; connector labor competes with medicine, food and defense.", pruning_hours=tree.PruningHoursToMaintain(percent/100f),
                            strength=tree.ConnectionStrength, current=tree.DesiredConnectionStrength, max_dryads=tree.MaxDryads, current_job=tree.ConnectedPawn.CurJobDef?.defName });
                    var command=tree.CompGetGizmosExtra().OfType<Command_Action>().FirstOrDefault(c => c.defaultLabel=="ChangeMode".Translate().ToString() && !c.Disabled);
                    if (command!=null) choices.Add(new { map_id=map.uniqueID, operation="open_caste", thing_id=t.thingIDNumber, label=command.defaultLabel, description=command.defaultDesc });
                }
                if (ModsConfig.AnomalyActive) {
                    var entities=map.listerThings.AllThings.Concat(map.listerBuildings.allBuildingsColonist.OfType<Building_HoldingPlatform>().Select(b => (Thing)b.HeldPawn).Where(p => p!=null)).Distinct();
                    foreach (var t in entities) {
                        var comp=t.TryGetComp<CompHoldingPlatformTarget>(); if (comp==null) continue;
                        if (t.Spawned && !t.Position.Fogged(map)) foreach (var command in Capture(t))
                            choices.Add(new { map_id=map.uniqueID, operation="capture_command", thing_id=t.thingIDNumber, label=command.defaultLabel, description=command.defaultDesc,
                                warning="Native holding-platform target stage; capture/transfer requires worker labor and exposes workers to entity hazards." });
                        if (comp.CurrentlyHeldOnPlatform && comp.HeldPlatform?.Faction==Faction.OfPlayer) {
                            foreach (var mode in new[] { EntityContainmentMode.MaintainOnly, EntityContainmentMode.Study }) if (mode!=comp.containmentMode)
                                choices.Add(new { map_id=map.uniqueID, operation="study_mode", thing_id=t.thingIDNumber, value=mode.ToString(), label=t.LabelCap.ToString()+" → "+mode,
                                    description=("EntityStudyMode_"+mode+"Desc").Translate().ToString(), strength=comp.HeldPlatform.TryGetComp<CompEntityHolder>()?.ContainmentStrength,
                                    minimum=t.GetStatValue(StatDefOf.MinimumContainmentStrength), inspect=t.GetInspectString() });
                            if (ResearchProjectDefOf.BioferriteExtraction.IsFinished && !comp.HeldPlatform.HasAttachedBioferriteHarvester)
                                choices.Add(new { map_id=map.uniqueID, operation="extract", thing_id=t.thingIDNumber, value=(!comp.extractBioferrite).ToString(), label=t.LabelCap.ToString()+" bioferrite extraction "+(!comp.extractBioferrite),
                                    description="Native extraction checkbox; needs normal labor and may reduce health/study potential. Attached harvesters govern their own extraction." });
                        }
                    }
                }
            }
            await context.SendJsonResponse(ApiResult<object>.Ok(new { available=true, configuring=dialog!=null, session_id=SpecialistWindowSessionHelper.Token(dialog), map_id=dialog==null ? mapId : Field<CompTreeConnection>(dialog,"treeConnection").parent.Map.uniqueID, configuration=dialog==null ? null : (object)new {current_mode=Field<GauranlenTreeModeDef>(dialog,"currentMode")?.defName,selected_mode=Field<GauranlenTreeModeDef>(dialog,"selectedMode")?.defName}, choices }));
        }
        [Post("/api/v1/specialists/policies")]
        public async Task Act(HttpListenerContext context) {
            if (!RequestParser.GetBooleanParameter(context,"confirmed")) { await context.SendJsonResponse(ApiResult<string>.Fail("Unconfirmed policy")); return; }
            string operation=RequestParser.GetStringParameter(context,"operation"), value=RequestParser.GetStringParameter(context,"value",false);
            if(new[]{"focus","meditation_hour","pruning","study_mode","extract","caste"}.Contains(operation)) value=RequestParser.GetStringParameter(context,"value");
            var dialog=Caste;
            if (dialog!=null) {
                if(!SpecialistWindowSessionHelper.Matches(dialog,context)) { await context.SendJsonResponse(ApiResult<string>.Fail("Caste dialog session changed"));return; }
                if (operation=="cancel") { dialog.Close(); await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; }
                var mode=DefDatabase<GauranlenTreeModeDef>.GetNamedSilentFail(value);
                if (operation=="caste" && mode!=null && mode!=Field<GauranlenTreeModeDef>(dialog,"currentMode") && (bool)AccessTools.Method(typeof(Dialog_ChangeDryadCaste),"MeetsRequirements").Invoke(dialog,new object[]{mode})) {
                    AccessTools.Field(typeof(Dialog_ChangeDryadCaste),"selectedMode").SetValue(dialog,mode);
                    var tree=Field<CompTreeConnection>(dialog,"treeConnection"); var pawn=tree.ConnectedPawn;
                    Find.WindowStack.Add(Dialog_MessageBox.CreateConfirmation("GauranlenModeChangeDescFull".Translate(tree.parent.Named("TREE"),pawn.Named("CONNECTEDPAWN"),ThingDefOf.DryadCocoon.GetCompProperties<CompProperties_DryadCocoon>().daysToComplete.Named("DURATION")),()=>AccessTools.Method(typeof(Dialog_ChangeDryadCaste),"StartChange").Invoke(dialog,null)));
                    await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return;
                }
            } else {
                int pawnId=operation=="focus" || operation=="meditation_hour" ? RequestParser.GetIntParameter(context,"pawn_id") : -1;
                int thingId=new[]{"pruning","open_caste","capture_command","study_mode","extract"}.Contains(operation) ? RequestParser.GetIntParameter(context,"thing_id") : -1;
                var pawn=PawnsFinder.AllMaps_FreeColonistsSpawned.FirstOrDefault(p=>p.thingIDNumber==pawnId && !SpecialistNativeSafety.Protected(p));
                if (ModsConfig.RoyaltyActive && pawn?.HasPsylink==true && int.TryParse(value,out int number)) {
                    if (operation=="focus" && new[]{25,50,75,95}.Contains(number)) { pawn.psychicEntropy.SetPsyfocusTarget(number/100f); await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; }
                    if (operation=="meditation_hour" && number>=0 && number<24 && pawn.timetable?.GetAssignment(number)==TimeAssignmentDefOf.Work && MeditationUtility.CanMeditateNow(pawn)) { pawn.timetable.SetAssignment(number,TimeAssignmentDefOf.Meditate); await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; }
                }
                var things=Find.Maps.SelectMany(m=>m.listerThings.AllThings.Concat(m.listerBuildings.allBuildingsColonist.OfType<Building_HoldingPlatform>().Select(b=>(Thing)b.HeldPawn).Where(p=>p!=null)));
                var t=things.FirstOrDefault(x=>x.thingIDNumber==thingId); var tree=t?.TryGetComp<CompTreeConnection>();
                if (ModsConfig.IdeologyActive && t!=null && TreeAvailable(t)) {
                    if (operation=="pruning" && int.TryParse(value,out int strength) && new[]{25,50,75,100}.Contains(strength)) { tree.DesiredConnectionStrength=strength/100f; await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; }
                    if (operation=="open_caste") { var command=tree.CompGetGizmosExtra().OfType<Command_Action>().FirstOrDefault(c=>c.defaultLabel=="ChangeMode".Translate().ToString() && !c.Disabled); if(command!=null) { command.action(); await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; } }
                }
                var comp=t?.TryGetComp<CompHoldingPlatformTarget>();
                if (ModsConfig.AnomalyActive && comp!=null) {
                    if(operation=="capture_command" && t.Spawned && !t.Position.Fogged(t.Map)) { var label=RequestParser.GetStringParameter(context,"label"); var command=Capture(t).FirstOrDefault(c=>c.defaultLabel==label); if(command!=null) { command.action(); await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; } }
                    if(comp.CurrentlyHeldOnPlatform && comp.HeldPlatform?.Faction==Faction.OfPlayer) {
                        if(operation=="study_mode" && Enum.TryParse(value,out EntityContainmentMode mode) && (mode==EntityContainmentMode.Study || mode==EntityContainmentMode.MaintainOnly)) { comp.containmentMode=mode; await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; }
                        if(operation=="extract" && ResearchProjectDefOf.BioferriteExtraction.IsFinished && !comp.HeldPlatform.HasAttachedBioferriteHarvester && bool.TryParse(value,out bool extract)) { comp.extractBioferrite=extract; await context.SendJsonResponse(ApiResult<string>.Ok("specialist_policy_requested")); return; }
                    }
                }
            }
            await context.SendJsonResponse(ApiResult<string>.Fail("Native policy requirements changed"));
        }
    }
}
