# Ecology, resources and production audit

Truth source: installed RimWorld **1.6.4871**, Core + Royalty, Ideology, Biotech, Anomaly; Odyssey inactive. Loaded definitions are queried at runtime, so DLC/mod overrides determine actual options. No game or Laya run was performed.

## Coverage matrix

| Mechanic | Coverage | Evidence / remaining gap |
|---|---|---|
| Crops, soil, blight, seasons, greenhouse | Existing support, offline verified | `colony_capabilities.py`; this module does not duplicate crop selection. Live game verification remains absent. |
| Basic meals, butcher, cooking stations | Covered elsewhere | Director ordinary bills and emergency cooking. |
| Stone, medicine, clothing, trade production | Partial elsewhere | Director `ensure_bill`, stonecutting and income doctrine routes; generic recipes lack material feasibility and strong server validation. |
| Fuel hauling | Covered elsewhere | `BuildingMaintenanceHelper.Refuel` uses native WorkGiver. |
| Fuel allocation / automatic refill | Added | Actual per-building capacity, stock definitions, consumption and allow-auto-refuel flag; Laya may stop or resume future fueling. Existing fuel is not removed. |
| Power consumption / service switching | Added, partial | Actual `CompPowerTrader.PowerOutput`, connection and operating state; switch uses CompFlickable's own gizmo and vanilla designation. Full network surplus, battery isolation, cable routing, weather forecasts remain absent. |
| Kibble protein + greens chain | Added | One finite researched recipe bill at existing usable table; each ingredient group must have map nutrition stock, Cooking worker required; no duplicate bill. Human meat/fertilized eggs/insect jelly excluded. |
| Animal feed / grazing / diets | Partial, expanded | Live species, food level, food-type flags, CanEverEat(Kibble), potential grazing capability. Offer requires suitable animals; actual pasture/pen feed access remains unknown. |
| Perishable temperature / time to rot | Added observation, partial control | Actual `CompRottable.TicksUntilRotAtCurrentTemp`, item count and temperature. Existing freezer/construction routes; no new automatic storage relocation or stockpile policy. |
| Renewable wild resources / mining depletion | Partial elsewhere | Harvest/mining director routes; no new ecological carrying-capacity model. |

## Confirmed mechanics and implementation

Installed primary sources: `Data/Core/Defs/ThingDefs_Buildings/Buildings_Power.xml` specifies wood generator 22 fuel/day and chemfuel generator 4.5/day with 1000 W base generation. These are definition examples, not hardcoded policy recommendations. Runtime data uses actual components.

`Data/Core/Defs/RecipeDefs/Recipes_Food.xml` specifies Make_Kibble: protein 1 nutrition, greens 1 nutrition, 50 kibble, 450 work; greens permit hay. Recipe output and ingredient definitions are exposed live. Existing income biofuel conversion already exists, so duplicating that path would add little; limited animal-feed production was missing.

Installed `Assembly-CSharp.dll`, decompiled through ILSpy, confirms `CompFlickable.CompGetGizmosExtra()` updates wanted state and `FlickUtility.UpdateFlickDesignation`; implementation calls that normal command, never `SwitchIsOn` directly. `CompRefuelable.allowAutoRefuel` is the ordinary player policy; `CompProperties_Refuelable.showAllowAutoRefuelToggle` limits available changes. `Building_WorkTable.CurrentlyUsableForBills()` and `RecipeDef.AvailableNow` are rechecked before adding one native `Bill_Production`.

Web cross-check: [Ludeon official translation repository: fuel target controls](https://github.com/Ludeon/RimWorld-ru/issues/323). Historical [decompiled CompRefuelable](https://github.com/josh-m/RW-Decompile/blob/master/RimWorld/CompRefuelable.cs) corroborates terminology only; installed 1.6 code supersedes historical behavior.

## Integration

Register DESCRIPTIONS/LABELS/ACTIONS/DOMAINS from `colony_production`. Save `collect(client,snapshot)` into `snapshot['development']['production']`; collect is GET-only. Append `prepare(snapshot,map_state)` candidates, route choose/execute/assess through module. Both action domains are `work_orders`. Add the three unique Production C# files to payload packaging if packaging does not discover source automatically.

Endpoints: GET `/api/v1/production/context?map_id=...`, POST `/api/v1/production/policy` with map_id/building_id/policy. Policy whitelist is switch_on/off, enable/disable_refuel, kibble_batch. Policy is revalidated immediately before POST and server rechecks ownership, component, pending flick, recipe, usable table and duplicate bill. Return `applied` is mandatory for success. Kibble success means **bill accepted, not food produced**.

Tests: `python -m unittest tests.test_production -v` passes eleven regressions: nutrition groups/worker capability, missing animals/incompatible diets, protected care/disabled work/skill eligibility, eligible stocks, completed finite bill availability, stale supply, unavailable API context, pending flick, duplicate bill, stale policy revalidation, missing applied response, defer cooldown and risk context. C# compilation is coordinated by root; runtime gameplay behavior remains unverified.

## Limits

Total stock counts include all map items; separate eligible nutrition excludes forbidden, burning and rotting items and unsafe feed definitions. Eligibility still does not prove reachable/unreserved supply. Safe feed definitions are cached once from loaded definitions, avoiding a full definition scan per stack. Context uses the effective existing finite bill filter and native PawnAllowedToStartAnew; completed finite bills are resumed for one batch without duplicate orders or widening their filters. Cooking eligibility rechecks positive work priority, recipe skills and protected care/DoBill work. Species CanEverEat(Kibble) establishes diet support; actual feed access remains unknown and defer is offered. No generalized production recipe planner, ingredient assignment, raw-food reserve filter, per-network battery forecast or feed delivery was added.
