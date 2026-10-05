# Intermittent endings GET collection invalidation

## Confirmed source cause

`EndingController.Context` previously enumerated `site.Map.mapPawns.FreeColonistsSpawned` at the site/pawn loop, then read `FreeColonistsSpawned` again inside each enabled job row to populate colony labels. Installed RimWorld 1.6 `MapPawns.FreeColonistsSpawned` delegates to `FreeHumanlikesSpawnedOfFaction`. That getter clears and repopulates the same faction scratch `List<Pawn>` and returns it. The nested read therefore increments the list version and invalidates the outer enumerator. The next `MoveNext` throws `InvalidOperationException: Collection was modified`, even on a completely paused game with one thread. Disabled-only options and absence of ending sites avoid the direct enabled-row trigger, explaining intermittent availability.

There are additional callback boundaries in quest acceptance, native float-menu generation and inspection. They may themselves read shared pawn getters. Copying only after those callbacks would leave the same defect reachable.

## Dispatch boundary

`ApiServer.ListenForRequestsAsync` enqueues requests. `RimApiServerProcess.Update` drains the queue on Unity's thread. `AutoRouteRegistry` invokes the controller through reflection; `EndingController.Context` has no await before its final response send. The observed source path is synchronous during native data collection. No background tick race is required to explain this defect. The fix adds an explicit `UnityData.IsInMainThread`/playing-game check so a future off-thread invocation does not try to snapshot concurrently changing game state.

## Scoped fix

Only `EndingController.Context` and a pure `EndingReadBoundary` helper changed. Before native option/inspection/quest callbacks, context captures owned arrays of maps, per-map colonists/sites, quests, and each quest's parts/targets. Colony labels and hostile counts are materialized in this read phase. All subsequent loops use owned arrays; nested callbacks can repopulate borrowed engine scratch lists without invalidating them. Native options are generated once per site/pawn and split into enabled jobs and disabled blockers from that one preview. No option action is executed. The async response contains scalar values and materialized arrays, with no deferred native enumerable surviving into serialization. Mutation endpoints and dispatch architecture are unchanged; no catch/retry masks the exception.

## Regression evidence

`tests/test_endings_read_boundary.py` compiles and runs the **actual production C# helper** in an isolated .NET 8 console, with no Unity/game/API process. A native-style getter clears/repopulates a shared `List<Pawn>`. The original nested loop genuinely throws the collection-modified exception. Eight cycles through the owned capture/projection helper remain stable while option and inspect callbacks repeatedly refill the same source list. Assertions cover all three original pawns/labels, one preview per pawn (24 total), both enabled/disabled paths, response stability after another getter read, and zero invoked actions. This proves the collection/read-boundary contract, not actual Unity pathfinding or ending eligibility.

Parent integration owns the combined RIMAPI build and subsequent read-only paused-game endpoint checks. No game orders, process changes or installation were performed for this regression.
