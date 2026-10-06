# Food deferrals and kitchen preparation — 2026-10-06

Scope: offline repair of two source-confirmed scheduling defects after the final continuation. No game or model was launched, no resources/jobs were completed by the audit, and no release was published. Private evidence remains outside the repository; pawn identities and saves are omitted here.

## Observed evidence and source cause

The bounded final-segment decisions contain material-logistics declines at 11:16:10.928, 11:16:20.976 and 11:16:31.290 UTC. All return `applied:false`, `laya_deferred_production`. The final report records 44 material-logistics selections and 47 production deferrals. Before this repair, nonutility `colony_production.execute` remembered a deliberate refusal through `_remember_selection(..., BACKOFF_TICKS)`: only 250 game ticks, without a real-time floor. This allows unchanged logistics questions on the ordinary decision cadence.

At 11:02:27 UTC, the food-batch decision's shown alternatives contain 78 `job:CleanFilth` keys (39 filth targets with two worker alternatives) and its purpose stage has only `job` or `defer`. The visible observation has zero prepared meals, 14 raw-food items and least food level about 0.092. The previous description advertised a food recipe batch although the offered workflow was cleaning only. This establishes misleading preparation context, not completion of food production.

Native `SustenanceHelper` also gathered kitchen rooms without excluding psychologically outdoor rooms, then included every filth thing with the same room. An outdoor room can cover much of the map. Exact distances of the 39 recorded targets are not established by those option keys; the source defect is the unbounded room-based eligibility rule. The final native snapshot separately had outdoor sleeping rooms and empty campfire/cooler fuel. Neither aggregate food stock nor accepted jobs establish timely feeding or refueling.

Survival waits were recorded as deferred with completion unverified. Wood-refusal repeats were observed, but this patch does not change their signature: its particular reopening cause remains unverified. These two repairs do not establish that the terminal deaths would have been prevented.

## Repair and boundaries

Recipe, feed and material-logistics refusals now use a separate JSON-safe history with 30000 game ticks and 120 real seconds; both must expire. Memory binds the actually shown alternatives. Recipe identity binds table, recipe and material; logistics binds workflow, target, material/policy and exact canonical footprint. Interchangeable worker IDs, labels and stock-count drift do not reopen a declined workflow. A new feasible target, material, recipe or footprint remains visible without deleting earlier refusals. Missing shown-option attribution does not lock an entire category. Game rollback, real-clock rollback and malformed retry history expire the refusal. Accepted-work dwell is unchanged.

Native cleanup now includes the actual enclosed kitchen room, or the same outdoor room within squared distance 9 of an outdoor food table's interaction cell. The native predicate is used by the option filter. Fresh ordinary workgiver, capacity, reachability/reservation and protected care-job checks remain. No food recipe is forced and no filth is deleted directly.

Food-batch consequences explicitly identify preparation-only observations. Purpose choices name cleaning and home-area configuration as preparation that produces no food. A newly feasible bill has its own scope and remains selectable after preparation was declined.

## Offline verification

`python -m unittest tests.test_production tests.test_sustenance tests.test_domain_cycle_contracts -q` — 89 tests passed on 2026-10-06. Added sequences cover defer without API mutation; JSON persistence; expiration requiring both clocks; worker/label/stock/footprint-order drift; new target/material/footprint/recipe/feed table; retained earlier refusal; game and real-clock rollback; unchanged accepted-work dwell; preparation-only wording; and a newly feasible native-shaped food bill after fuel arrival and preparation decline. The latter verifies exact-key posting and explicitly does not assert produced food.

`powershell -NoProfile -File tests/native_kitchen_cleanup_boundary.ps1` is the serial parent-QA command for the actual dependency-free native predicate extracted from the helper. It covers distant outdoor room-0 filth, the three-cell boundary, the first excluded distance, a nearby different room, and an enclosed kitchen room. It was not run by this delegated repair because C# compilation belongs to serial parent QA. The normal API assembly build also remains for parent QA. Neither check proves ordinary cleaning, hauling, cooking or feeding completion in RimWorld.

Parent QA review is required before including this repair in the 0.0.7 candidate.
