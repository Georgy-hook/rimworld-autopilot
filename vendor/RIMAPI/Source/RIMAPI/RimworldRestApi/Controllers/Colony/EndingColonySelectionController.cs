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
    // This mirrors the existing sale dialog's checkbox and Accept handlers. It never
    // calls postAccepted directly, so the game's consequence confirmation is retained.
    public class EndingColonySelectionController
    {
        private static Dialog_ChooseThingsForNewColony Dialog => Find.WindowStack.Windows.OfType<Dialog_ChooseThingsForNewColony>().FirstOrDefault();
        private static T Field<T>(Dialog_ChooseThingsForNewColony dialog, string name) => (T)AccessTools.Field(typeof(Dialog_ChooseThingsForNewColony), name).GetValue(dialog);
        private static AcceptanceReport Report(Dialog_ChooseThingsForNewColony dialog) => (AcceptanceReport)AccessTools.Property(typeof(Dialog_ChooseThingsForNewColony), "AcceptanceReport").GetValue(dialog, null);
        [Get("/api/v1/colony/endings/selection")]
        [EndpointMetadata("Read the currently open native Archonexus sale selection, category limits and exact transfer candidates")]
        public async Task Context(HttpListenerContext context) {
            var dialog = Dialog;
            if (dialog == null) { await context.SendJsonResponse(ApiResult<object>.Ok(new { available = false })); return; }
            var selected = Field<HashSet<Thing>>(dialog, "selected");
            var quantities = Field<Dictionary<Thing, int>>(dialog, "itemArchonexusAllowedStackCount");
            var rows = new List<object>();
            foreach (string category in new[] { "colonists", "animals", "relics", "items" })
                foreach (var thing in Field<List<Thing>>(dialog, category)) rows.Add(new {
                    thing_id = thing.thingIDNumber, category, label = thing.LabelCap.ToString(),
                    def_name = thing.def.defName, selected = selected.Contains(thing),
                    quantity = quantities.TryGetValue(thing, out int count) ? count : thing.stackCount,
                    description = thing.DescriptionDetailed,
                    is_slave = thing is Pawn pawn && pawn.IsSlaveOfColony
                });
            await context.SendJsonResponse(ApiResult<object>.Ok(new { available = true, rows,
                max_colonists = Field<int>(dialog, "maxColonists"), max_animals = Field<int>(dialog, "maxAnimals"),
                max_relics = Field<int>(dialog, "maxRelics"), max_items = Field<int>(dialog, "maxItems"),
                can_submit = Report(dialog).Accepted, blocker = Report(dialog).Reason,
                consequence = "Selling the colony abandons every unselected person, animal and item. The landed escape ship is removed. The game opens another explicit confirmation before the sale." }));
        }
        [Post("/api/v1/colony/endings/selection")]
        [EndpointMetadata("Toggle one explicit native colony-sale selection or request its normal consequence confirmation")]
        public async Task Select(HttpListenerContext context) {
            var dialog = Dialog;
            string operation = RequestParser.GetStringParameter(context, "operation");
            if (dialog == null || !RequestParser.GetBooleanParameter(context, "confirmed")) {
                await context.SendJsonResponse(ApiResult<string>.Fail("Selection absent or unconfirmed")); return;
            }
            var selected = Field<HashSet<Thing>>(dialog, "selected");
            if (operation == "cancel") {
                Field<System.Action>(dialog, "cancel")?.Invoke(); dialog.Close();
                await context.SendJsonResponse(ApiResult<string>.Ok("sale_cancelled")); return;
            }
            if (operation == "submit") {
                if (!Report(dialog).Accepted) { await context.SendJsonResponse(ApiResult<string>.Fail(Report(dialog).Reason)); return; }
                AccessTools.Method(typeof(Dialog_ChooseThingsForNewColony), "ConfirmArchonexusSettlementConsequences")
                    .Invoke(dialog, new object[] { selected.ToList(), dialog.ColonistCount == dialog.SlaveCount });
                await context.SendJsonResponse(ApiResult<string>.Ok("sale_confirmation_opened")); return;
            }
            int id = RequestParser.GetIntParameter(context, "thing_id");
            var candidates = new[] { "colonists", "animals", "relics", "items" }.SelectMany(c => Field<List<Thing>>(dialog, c));
            var thing = candidates.FirstOrDefault(t => t.thingIDNumber == id);
            bool desired = RequestParser.GetBooleanParameter(context, "selected");
            if (operation != "select" || thing == null || thing.Destroyed) { await context.SendJsonResponse(ApiResult<string>.Fail("Transfer candidate changed")); return; }
            bool changed = desired ? selected.Add(thing) : selected.Remove(thing);
            if (changed && Field<List<Thing>>(dialog, "items").Contains(thing))
                AccessTools.Field(typeof(Dialog_ChooseThingsForNewColony), "selectedItemCount").SetValue(dialog,
                    Field<int>(dialog, "selectedItemCount") + (desired ? 1 : -1));
            await context.SendJsonResponse(ApiResult<string>.Ok("sale_selection_updated"));
        }
    }
}
