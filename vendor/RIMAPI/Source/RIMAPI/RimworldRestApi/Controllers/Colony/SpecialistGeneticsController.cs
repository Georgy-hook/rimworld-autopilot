using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Threading.Tasks;
using HarmonyLib;
using RIMAPI.Core;
using RIMAPI.Helpers;
using RIMAPI.Http;
using RimWorld;
using UnityEngine;
using Verse;

namespace RIMAPI.Controllers
{
    public class SpecialistGeneticsController
    {
        private static T Field<T>(object target, string name) => (T)AccessTools.Field(target.GetType(), name).GetValue(target);
        private static Dialog_CreateXenogerm Dialog => Find.WindowStack.Windows.OfType<Dialog_CreateXenogerm>().FirstOrDefault();
        private static Command_Action Assemble(Building_GeneAssembler assembler) => assembler.GetGizmos().OfType<Command_Action>()
            .FirstOrDefault(c => c.defaultLabel == "Recombine".Translate() + "..." && !c.Disabled);
        private static List<string> Blockers(Dialog_CreateXenogerm dialog) {
            var result = new List<string>();
            var packs = Field<List<Genepack>>(dialog, "selectedGenepacks");
            var genes = packs.SelectMany(p => p.GeneSet.GenesListForReading).ToList();
            if (packs.Count == 0) result.Add("No selected genepacks");
            if (Field<int>(dialog, "gcx") > Field<int>(dialog, "maxGCX")) result.Add("Complexity exceeds connected facilities");
            if (Field<int>(dialog, "met") < GeneTuning.BiostatRange.TrueMin) result.Add("Metabolism below native minimum");
            if (Field<string>(dialog, "xenotypeName").NullOrEmpty()) result.Add("Name required");
            if (Field<int>(dialog, "arc") > 0 && !ResearchProjectDefOf.Archogenetics.IsFinished) result.Add("Archogenetics research required");
            if (!(bool)AccessTools.Method(typeof(Dialog_CreateXenogerm), "ColonyHasEnoughArchites").Invoke(dialog, null)) result.Add("Insufficient archite capsules");
            if (genes.Any(g => g.prerequisite != null && !genes.Contains(g.prerequisite))) result.Add("Missing selected gene prerequisite");
            return result;
        }
        [Get("/api/v1/specialists/genetics")]
        [EndpointMetadata("Read native xenogerm design, whole genepacks, actual complexity/metabolism/archite limits and assembler work state")]
        public async Task Context(HttpListenerContext context) {
            var dialog = Dialog;
            var assemblers = Find.Maps.SelectMany(m => m.listerThings.AllThings.OfType<Building_GeneAssembler>()).Where(b => b.Faction == Faction.OfPlayer).Select(b => new {
                map_id = b.Map.uniqueID, thing_id = b.thingIDNumber, working = b.Working, powered = b.PowerOn, progress = b.ProgressPercent,
                max_complexity = b.MaxComplexity(), can_open = Assemble(b) != null, inspect = b.GetInspectString()
            }).ToList();
            var packs = new List<object>();
            if (dialog != null) {
                var selected = Field<List<Genepack>>(dialog, "selectedGenepacks");
                var unpowered = Field<List<Genepack>>(dialog, "unpoweredGenepacks");
                foreach (var pack in Field<List<Genepack>>(dialog, "libraryGenepacks")) packs.Add(new {
                    thing_id = pack.thingIDNumber, label = pack.LabelCap.ToString(), selected = selected.Contains(pack), powered = !unpowered.Contains(pack),
                    genes = pack.GeneSet.GenesListForReading.Select(g => new { name = g.defName, label = g.label, description = g.description,
                        complexity = g.biostatCpx, metabolism = g.biostatMet, archites = g.biostatArc, prerequisite = g.prerequisite?.defName }).ToList()
                });
            }
            var blockers = dialog == null ? new List<string>() : Blockers(dialog);
            await context.SendJsonResponse(ApiResult<object>.Ok(new { available = ModsConfig.BiotechActive, configuring = dialog != null,
                assemblers, packs, blockers, can_begin = dialog != null && blockers.Count == 0,
                complexity = dialog == null ? 0 : Field<int>(dialog, "gcx"), metabolism = dialog == null ? 0 : Field<int>(dialog, "met"),
                archites = dialog == null ? 0 : Field<int>(dialog, "arc"), max_complexity = dialog == null ? 0 : Field<int>(dialog, "maxGCX"),
                name = dialog == null ? null : Field<string>(dialog, "xenotypeName"),
                warning = "Whole genepacks are combined; conflicts may override or randomly choose genes. Poor metabolism increases food demand. Assembly requires real work and power; implanting remains a separate medical action." }));
        }
        [Post("/api/v1/specialists/genetics")]
        [EndpointMetadata("Select whole native genepacks or begin normal xenogerm assembly after exact GUI CanAccept checks; never finishes work or implants genes")]
        public async Task Act(HttpListenerContext context) {
            if (!ModsConfig.BiotechActive || !RequestParser.GetBooleanParameter(context, "confirmed")) { await context.SendJsonResponse(ApiResult<string>.Fail("Biotech inactive or unconfirmed")); return; }
            string operation = RequestParser.GetStringParameter(context, "operation");
            int id = RequestParser.GetIntParameter(context, "thing_id");
            var dialog = Dialog;
            if (operation == "open" && dialog == null) {
                var assembler = Find.Maps.SelectMany(m => m.listerThings.AllThings.OfType<Building_GeneAssembler>()).FirstOrDefault(b => b.thingIDNumber == id && b.Faction == Faction.OfPlayer);
                var command = assembler == null ? null : Assemble(assembler);
                if (command != null) { command.action(); await context.SendJsonResponse(ApiResult<string>.Ok("gene_design_opened")); return; }
            }
            if (dialog == null) { await context.SendJsonResponse(ApiResult<string>.Fail("Gene design stage changed")); return; }
            if (operation == "cancel") { dialog.Close(); await context.SendJsonResponse(ApiResult<string>.Ok("gene_design_cancelled")); return; }
            if (operation == "select") {
                var assembler = Field<Building_GeneAssembler>(dialog, "geneAssembler");
                var pack = Field<List<Genepack>>(dialog, "libraryGenepacks").FirstOrDefault(p => p.thingIDNumber == id);
                bool desired = RequestParser.GetBooleanParameter(context, "selected");
                if (pack == null || (desired && !assembler.GetGenepacks(true, false).Contains(pack))) { await context.SendJsonResponse(ApiResult<string>.Fail("Genepack power/access changed")); return; }
                var selected = Field<List<Genepack>>(dialog, "selectedGenepacks");
                if (desired && !selected.Contains(pack)) selected.Add(pack);
                if (!desired) selected.Remove(pack);
                AccessTools.Method(typeof(Dialog_CreateXenogerm), "OnGenesChanged").Invoke(dialog, null);
                await context.SendJsonResponse(ApiResult<string>.Ok("gene_selection_updated")); return;
            }
            if (operation == "name") {
                // This is the game's own Randomize name button, explicitly chosen by Laya.
                var genes = Field<List<Genepack>>(dialog, "selectedGenepacks").SelectMany(p => p.GeneSet.GenesListForReading).ToList();
                if (genes.Count > 0) { AccessTools.Field(typeof(GeneCreationDialogBase), "xenotypeName").SetValue(dialog, GeneUtility.GenerateXenotypeNameFromGenes(genes));
                    await context.SendJsonResponse(ApiResult<string>.Ok("gene_name_chosen")); return; }
            }
            var currentAssembler = Field<Building_GeneAssembler>(dialog, "geneAssembler");
            bool packsAccessible = currentAssembler != null && currentAssembler.PowerOn && Field<List<Genepack>>(dialog, "selectedGenepacks").All(p => currentAssembler.GetGenepacks(true, false).Contains(p));
            if (operation == "begin" && packsAccessible && (bool)AccessTools.Method(typeof(Dialog_CreateXenogerm), "CanAccept").Invoke(dialog, null)) {
                AccessTools.Method(typeof(Dialog_CreateXenogerm), "Accept").Invoke(dialog, null);
                await context.SendJsonResponse(ApiResult<string>.Ok("gene_assembly_requested")); return;
            }
            await context.SendJsonResponse(ApiResult<string>.Fail("Native gene requirements changed"));
        }
    }
}
