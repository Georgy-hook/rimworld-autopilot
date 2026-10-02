# Architecture and ship recovery contracts (2026-10-02)

Offline source review and mocked executor tests; no game/API server/model launch, native build, or commit.

## Findings and changes

1. `colony_shipbuilding.identity` previously certified any matching def/anchor without rotation. It now requires exact native rotation for oriented ship parts. Installed Core Buildings_Ship.xml marks ComputerCore/SensorCluster nonrotatable; their orientation is irrelevant. Missing rotation cannot certify beam/engine/reactor/casket. GET /builder/projects now exports Rotation; GET /map/buildings already exports it. Existing differently oriented structures remain intact.
2. `estimated_stuff_cost` now uses loaded terrain CostList first. Installed Royalty Terrain_Floors_FineStoneTile.xml requires 20 BlocksGranite for FineTileGranite. Known legacy floor costs remain fallbacks only when metadata is absent. Unrecognized floor costs create an explicit unavailable-budget entry instead of treating the floor as free.
3. New plans persist the exact original layout, map_id and origin. Reconciliation counts matching queued versus completed structures separately, checks stuff/orientation and observes completed floors through terrain. Explicit `repair_architecture` asks Laya which saved partial project to restore. It re-reads physical evidence, loaded costs/research and stock minus pending requirements; all remaining elements must pass native read-only blueprint preview including footprint and interaction-cell checks. It never redesigns or demolishes. Different material/orientation at the intended anchor is a visible blocker.
4. Blueprint POST failure does not establish rollback. Architecture and ship executors read after a failed transport response; observed partial mutation retains its original site. Ship site is committed only after observed relevant parts. If observation itself fails, provisional intent remains until the next fresh read. A positively observed empty failed ship site is released with a 2500-tick retry bound; subsequent placement repeats native site search.

## Exact transport

### Legacy hospital follow-up

The legacy `build_hospital` branch now uses the same exact-plan observation, fresh budget, native preview and saved-project reconciliation helpers. Its permanent `hospital_blueprint` candidate exclusion is replaced by a 2500-tick attempt gate. Actual beds in the hospital region and active hospital projects prevent a second copy. New requests persist the original 27-element layout, map ID and origin before POST; complete placement is claimed only after matching observed definitions, coordinates, stuff and rotation. Queued placement remains distinct from completed construction.

Preview and placement contain only missing elements at the saved site. Partial/lost-reply effects preserve intent and become explicit `repair_architecture` choices. If every element is positively observed absent, reconciliation releases the empty reservation after the bounded interval; a new `build_hospital` choice reuses the exact layout and runs the existing clear-site search. The last eight failed empty placement origins are bounded search exclusions, preventing repetition on the same native-blocked site. Partial physical intent retains its original site. Actual human medical beds elsewhere also prevent a new clinic copy. No demolition occurs. Failed post-observation keeps provisional intent and reports unknown outcome until fresh evidence establishes what exists.

An old lifetime marker without trustworthy exact layout/origin is not converted into invented recovered intent. After the bounded interval, actual current hospital/beds context can allow a new model choice; only newly issued plans acquire exact recovery metadata. Offline regressions cover candidate retry after rejection/all cancellation, partial same-site repair, full-existing duplicate prevention, old-marker expiry and lost observation.

GET `/api/v1/map/buildings`, `/api/v1/builder/projects`, `/api/v1/map/terrain`, `/api/v1/map/things`: query `map_id`.
GET `/api/v1/buildings/catalog`: no map query (loaded definition costs/research).
POST `/api/v1/builder/blueprint/preview` and `/api/v1/builder/blueprint`: body `{map_id, position:{x,y:0,z}, blueprint:<original or missing subset>, clear_obstacles:false}`.
Native builder POST may partially succeed; response alone never proves completed construction. Both preview and mutation use native placement rules; preview does not simulate future dependencies.

## Retry, cancellation and saved state

Repair issuance has per-project 2500-tick suppression. Failed hospital/repair options additionally use shared colony_retry.failure_record/recent with a 30-second minimum: both clocks must expire. Other projects remain eligible; actual observed progress removes failure memory. Future timestamps reset to current observation after rollback. Empty cancelled plans stop reserving the old rectangle after that horizon, allowing hospital planning again. Legacy saved rectangles without exact layouts can release empty reservations but cannot safely manufacture a repair plan; model-visible state reports the missing original layout. Active partial hospital intent has an explicit repair choice. New code resides in existing installed runtime modules, so no install payload addition is required.

## Verification

`tests/test_construction_recovery.py`: 10 tests, including actual director initial placement -> partial mutation/lost reply -> JSON reload -> explicit same-site missing-door repair; blueprint versus building distinction; material conflict; native preview rejection/backoff/rollback/cancellation; wrong map/unknown orientation; native floor costs; ship POST applied then exception; failed empty ship site retry/reselection.
Existing architecture observation fixtures now supply native preview and catalog responses. Targeted architecture suites (21), campaign contracts (16), and ship geometry (3) passed during this change.

Limits: fixtures establish transport/recovery contracts, not actual Laya decisions, native construction completion, connected ship launch readiness, or playthrough survival. Blocked original designs remain blocked until their prerequisites change; there is no automatic demolition or strategic forced repair.
