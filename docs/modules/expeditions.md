# Expeditions: trade, raid and rescue

`colony_expeditions.py` is a director decision helper, not a registered colony
module. `install_payload.py` includes it. Development choices `trade_to:*`,
`raid_to:*`, and `prepare_trade_caravan`, plus the event response
`prepare_rescue_mission`, use the same preview/confirmation/execute contract.
Generic trade preparation first asks for a real destination or defer. Rescue
requires a previously accepted disclosed quest and explicitly selected quest site.

## API and units

`POST /api/v1/world/caravan/preview` is read-only despite using POST: complex
trade categories/prisoner selections use a body. It does not create jobs, Lords,
caravans, routes, stock or game dialogs. It reads selected-map reachable items,
selected destination and at most one policy-derived candidate roster. Native
world path calculation runs twice per candidate, once for each travel leg.

Body: `mode` (`trade`, `raid`, `rescue`), `map_id`,
`destination_settlement_id` or `quest_id` + `site_id`,
`minimum_home_defenders`, `minimum_food_at_home`,
`minimum_medicine_at_home`, `margin_days` (1..15), and mode-specific
`sale_categories`, `purchase_priorities`, `prisoner_ids`, `allow_starting_war`.
Preview candidates are suggestions; they never authorize departure.

Response: `plans`, `blockers`, partial `readiness`, scalar `pending` (max four)
and `last_result`, plus limitations in `warning`. A plan includes:

- Exact `pawn_ids`, `home_pawn_ids`, and `manifest` rows
  `{thing_id, def_name, count}`; `essentials` binds policy, target, roster,
  cargo, carried equipment/inventory identity, nutrition needs and material
  destination consequences. Ordinary job/position and ETA drift are excluded.
- `outbound_days`, `return_days`, `margin_days`, `food_days`,
  `food_margin_days`, `food_nutrition`, `daily_nutrition`, and `diets` per human
  traveler/prisoner (native diet/policy, compatible rations, consumption).
- `mass`, `capacity`, `carried_gear_mass`, `home_defenders`, `home_medicine`,
  `home_food_items`, `home_food_nutrition`, `minimum_home_food_items`,
  `minimum_home_food_nutrition`, estimate explanation and consequences.

Nutrition fields are nutrition units; days are game days. The existing
`minimum_food_at_home` field remains **item units**, not nutrition. Its minimum
nutrition conversion is shown separately using actual remaining stacks, smallest
nutrition units first. Fourteen Pemmican units (.05 nutrition each) are .7
nutrition; fourteen survival meals (.9 each) are 12.6. They are not interchangeable
travel budgets. Native food-days calculation and each selected pawn's native
food consumption also validate the selected supplies.

The existing `POST /api/v1/world/caravan/{trade,raid,rescue}/start` endpoints retain
mode-specific bodies and additionally require `confirmed:true`, `essentials`,
exact traveler/home IDs and manifest. Start regenerates feasibility for that
selection and policy; it does not silently substitute another team or stack.
It tolerates informational ETA drift while rechecking food coverage for the
current native estimate. Explicit `applied:true`, `status:forming` and
`formation_id` acknowledge formation only. `already_forming` returns the
existing exact pending intent after an unknown response, without another Lord.

## Lifecycle

`ExpeditionRouteState` persists origin map, exact forming Lord reference and
load ID, formation GUID, mode/target/quest, exact roster, policy and essentials.
Every 60 ticks it validates identity and membership. Missing/canceled Lord,
map/target loss, changed/downed roster and legacy identity gaps explicitly
invalidate the routing intent. Ordinary vanilla formation remains untouched:
there is no automatic cancel or restart. Readiness and scalar route projection
show a still-active native formation. There is currently no expedition cancel
endpoint; vanilla cancellation or a later supported explicit action is required.

The existing exact `ExitMapAndCreateCaravan(IEnumerable<Pawn>, Faction,
PlanetTile, PlanetTile, PlanetTile, bool)` Harmony hook captures the forming Lord
before native exit removes it and dispatches the returned caravan to both ending
and ordinary expedition components. Only that Lord plus the complete matching
roster can request the chosen route. Native arrival `StillValid` and reachability
are rechecked. No ANY-pawn overlap search is used. Trade opens the normal trade
session; it does not auto-sell people or silently close that session. Native path
and arrival persistence take over after `travel_requested`.

This differs from the earlier ending-specific journey component, whose narrow
compromised-roster handling can stop its exact formation. Ordinary expeditions
do not inherit that behavior or campaign ending state.

## Decision and retry audit

Laya compares the exact feasible plan against `defer`. Separate bounded effects
put outbound/return days, food margin, actual mass/nutrition, home reserves and
ETA exclusions before optional names. Twenty long names cannot hide these facts
in the tested 512-token adapter configuration. An empty/unknown-ETA/insufficient
margin preview causes no model confirmation or start call. Blockers/readiness
are returned for later planning; a previously attempted readiness summary is
historical evidence, not a fresh guarantee.

A rejected start does not mark `issued` or `caravan_plan`. Development failed
options retry on bounded wall time; deliberate expedition defer waits 30 seconds.
Event mutations use 5/10/20/30-second failure backoff, with explicit observation/
defer acknowledgments separated from rejection. The legacy rescue item-count
pre-gate is bypassed only when `native_preview_required` is explicitly set;
native nutrition/ETA/capacity readiness remains authoritative.

## Bounds and unproven behavior

This is a conservative human-only expedition planner. No animal feed/pack animals
or foraging credit; all packed travel rations must be edible and policy-allowed
for every selected human, including prisoners. Mixed separate diet pools are
not implemented. Supported rations are packaged survival meals and Pemmican;
rottable life must cover the whole budget at conservative 40C, which is not a
promise about future weather above 40C. Native ETA uses full legal carrying
capacity and rest/season rules; it excludes formation, encounters and future
incidents. Unknown ETA blocks a plan rather than becoming zero. Existing carried
inventory contributes mass but is not credited as safe nutrition.

A two-leg budget does not guarantee later return food after recruits, sales,
combat, illness or delays. Rescue return remains a separate fresh action.
Site threat is an estimate; preview does not generate unexplored maps or reveal
hidden sites. Preview currently proposes one native-ranked roster for a chosen
policy, rather than enumerating every possible team.

Focused offline tests verify Python transport, prompts, no-start cases and native
source contracts. Installed ILSpy source confirms the hook overload, Lord ID,
food need/ration utility, `CompRottable.TicksUntilRotAtTemp`, and native path
estimator APIs; `Settlement.TraderKind` and `CanTradeNow` are reads. Trade preview
uses native `Pawn.CanTradeWith` eligibility and rejects settlements with existing
maps. These checks are **not** live Harmony, save/load or gameplay proof. No game,
live API, model weights or observer was started during this audit.
