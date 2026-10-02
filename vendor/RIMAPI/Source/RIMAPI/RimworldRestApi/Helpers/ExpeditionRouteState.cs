using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using RimWorld.Planet;
using Verse;
using Verse.AI.Group;

namespace RIMAPI.Helpers {
    public class ExpeditionRoute : IExposable {
        public int OriginMapId = -1, NativeLordId = -1, ObjectId, QuestId;
        public List<int> PawnIds = new List<int>();
        public Lord FormingLord;
        public string FormationId, Mode, Essentials, Policy, Status = "forming", Reason;
        public void ExposeData() {
            Scribe_Values.Look(ref NativeLordId, "nativeLordId", -1); Scribe_Values.Look(ref OriginMapId, "originMapId", -1); Scribe_Values.Look(ref ObjectId, "objectId"); Scribe_Values.Look(ref QuestId, "questId");
            Scribe_Collections.Look(ref PawnIds, "pawnIds", LookMode.Value); Scribe_References.Look(ref FormingLord, "formingLord");
            Scribe_Values.Look(ref FormationId, "formationId"); Scribe_Values.Look(ref Mode, "mode"); Scribe_Values.Look(ref Essentials, "essentials");
            Scribe_Values.Look(ref Policy, "policy"); Scribe_Values.Look(ref Status, "status", "forming"); Scribe_Values.Look(ref Reason, "reason");
        }
    }
    public class ExpeditionRouteState : GameComponent {
        public List<ExpeditionRoute> Routes = new List<ExpeditionRoute>();
        public ExpeditionRoute LastResult;
        public ExpeditionRouteState(Game game) { }
        public override void ExposeData() {
            Scribe_Collections.Look(ref Routes, "layaExpeditionRoutes", LookMode.Deep); Scribe_Deep.Look(ref LastResult, "layaExpeditionResult");
            if (Scribe.mode == LoadSaveMode.PostLoadInit && Routes == null) Routes = new List<ExpeditionRoute>();
        }
        public override void GameComponentTick() { if (Find.TickManager.TicksGame % 60 == 0) ValidateRoutes(); }
        private void Finish(ExpeditionRoute route, string status, string reason) {
            route.Status = status; route.Reason = reason; route.FormingLord = null; LastResult = route; Routes.Remove(route);
        }
        public void ValidateRoutes() {
            if (Find.WorldObjects == null || Routes == null) return;
            foreach (var route in Routes.ToList()) {
                var map = Find.Maps.FirstOrDefault(m => m.uniqueID == route.OriginMapId);
                if (route.FormingLord == null || route.PawnIds == null || string.IsNullOrEmpty(route.FormationId)) { Finish(route, "invalidated", "Legacy/missing exact native formation identity; new decision required"); continue; }
                if (map == null || !map.lordManager.lords.Contains(route.FormingLord)) { Finish(route, "cancelled", "Exact native Lord no longer belongs to origin map; no caravan callback observed"); continue; }
                var target = Find.WorldObjects.AllWorldObjects.OfType<MapParent>().FirstOrDefault(t => t.ID == route.ObjectId);
                if (target == null || !(route.FormingLord.LordJob is LordJob_FormAndSendCaravan job) || job.downedPawns.Any() ||
                    !route.PawnIds.OrderBy(v => v).SequenceEqual(route.FormingLord.ownedPawns.Select(p => p.thingIDNumber).OrderBy(v => v))) {
                    // Intent invalidation is read-only with respect to vanilla formation.
                    // The native Lord may still be active; no automatic cancellation/restart.
                    Finish(route, "invalidated", (target == null ? "Chosen destination disappeared" : "Exact formation roster or native state changed") + "; native formation remains active and requires an explicit later decision");
                }
            }
        }
        public void CaravanCreated(Lord formingLord, Caravan caravan) {
            var route = Routes.FirstOrDefault(r => r.FormingLord == formingLord);
            if (route == null) return;
            if (caravan == null || !caravan.IsPlayerControlled || !route.PawnIds.OrderBy(v => v).SequenceEqual(caravan.PawnsListForReading.Select(p => p.thingIDNumber).OrderBy(v => v))) {
                Finish(route, "invalidated", "Created caravan differs from exact selected formation"); return;
            }
            var target = Find.WorldObjects.AllWorldObjects.OfType<MapParent>().FirstOrDefault(t => t.ID == route.ObjectId);
            CaravanArrivalAction arrival = null;
            if (route.Mode == "rescue" && target is Site site) {
                var quest = Find.QuestManager.QuestsListForReading.FirstOrDefault(q => q.id == route.QuestId && !q.Historical);
                if (quest != null && quest.QuestLookTargets.Any(t => t.WorldObject == site)) arrival = new CaravanArrivalAction_VisitSite(site);
            } else if (target is Settlement settlement && route.Mode == "trade") arrival = new CaravanArrivalAction_Trade(settlement);
            else if (target is Settlement raid && route.Mode == "raid") arrival = new CaravanArrivalAction_AttackSettlement(raid);
            if (arrival == null || !arrival.StillValid(caravan, target.Tile) || !Find.WorldReachability.CanReach(caravan, target.Tile)) {
                Finish(route, "invalidated", "Native arrival eligibility changed; created caravan requires a new route decision"); return;
            }
            caravan.pather.StartPath(target.Tile, arrival, true);
            Finish(route, "travel_requested", "Exact native formation created caravan and requested chosen route; arrival/return unobserved");
        }
    }
}
