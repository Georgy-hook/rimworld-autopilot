# Postmortem source repairs — 10 October 2026

Scope: the completed 9 October candidate playtest and confirmed implementation
defects. The private terminal report preserves the colony, identities, clinical
evidence, screenshot, save and log excerpts. It records native GameOver after
6h40m of autonomy, starvation and hypothermia, nine owned animal losses, stalled
research and no demonstrated mineral output or sale. Cooking, feeding and
heating occurred earlier; sustained supply failed. A kidnapped living pawn
outside the map is not recorded as a death.

The completed game, installed runtime, memory and save were not changed by these
repairs. Observation was paused after native GameOver. No new landing, restart,
load, gameplay replay or forced save was performed. Candidate 0.0.8 remains
unreleased on `feature/0.0.8`, targeting `developing` through PR #5.

## Corrected implementation contracts

| Finding | Source correction | What still requires observation |
|---|---|---|
| Opposite food priorities repeatedly selected the same worker; generic health excluded an actor who could work | Shared live-job and role commitments across cooking, hunting, growing, cutting, mining and research; both real/tick clocks, changed-source release and rollback; specific capacities replace the aggregate health threshold | Actual job completion and sustained reserves; priority readback does not prove a meal |
| Cooking candidates included unavailable queues and nonfood burning bills | Loaded recipe food classification, usable table, requested bill, reachable ingredients and capable/active worker IDs are required when the context is observed | Completed batches, hauling, repeated eating and winter supply |
| A selected mineral preference was replaced by gold/silver rectangles; a new meteorite did not trigger that legacy income path | New mining domain chooses the actual loaded product, exact connected batch and miner independently of the legacy income timer; whole-batch roof support and actual paths checked; ordinary Mine job and separate mineral haul | Output, provenance, storage arrival, buyer, actual sale and income per hour |
| Corpse storage used a fixed offset overlapping an animal pen and allowed desiccated bodies | Native rot/death identity fields, fresh-only ingredient selection, actual pen/zone geometry, fresh/rotten stockpile filters and full-footprint validation before zone registration | Hauling, corpse spoilage and actual food; an existing bad old zone is not silently migrated |
| Standing pen animals were sent through patient feeding rather than supplied with accessible feed | Finite compatible fresh-food haul into connected pen cells with actual operator, reservations and both route legs; reachable human-compatible reserve preserved; no permanent Critical feeder zone | Arrival, eating and repetition; ordinary haulers may later move nonstorage feed |
| An animal already in a cold outdoor bed was excluded from useful thermal rescue | Actual harmful temperature replaces blanket in-bed rejection; owned animal, same-patient nonbleeding Tend-to-Rescue exception; checked completed warm bed and route; loaded free warm animal sleeping spot when missing | Physical arrival, safe room, warmth and feeding; a spot alone does not rescue |
| Elective animal surgery could use a weak doctor on an unsafe patient | Fed stable patient in roofed comfortable bed; Medicine >=8 and projected surgeon-stat × bed-factor >=0.9; reachable medicine; exact doctor restriction on the ordinary medical bill | Native failure chance remains; medicine potency and later condition changes do not become guaranteed success |
| One damaged quest record caused a collection failure | Per-record read boundary, explicit partial/unavailable DTOs, null-safe historical references, no acceptance from incomplete terms; complete fresh reward/accepter/version validation retained | The original exact offending record/stack was not recovered; these changes were not injected into the old game to claim a live fix |
| Bed replacement ignored the second occupied cell and restored a spot after an uncertain reply | Full two-cell room/neighbor check, protection of a downed occupant, bounded failed sites and observed paid-project readback before restoration | Native final placement, paid construction and safe bed use |

The mining and welfare native executors rederive offered plans before mutation.
They respect protected care, ingestion and ongoing production, capabilities,
loaded definitions, reservations, actual paths, visible threats and environmental
hazards. Paid buildings stay ordinary projects; warm spots use the previously
authorized loaded zero-work, zero-cost marker contract.

Completed mining batches release their worker commitment when observed target
IDs disappear. Unknown/legacy ore identity does not establish disappearance.
Disappearance or stock growth also does not prove mining attribution or profit.
Feed count is bounded by actual stack and nutrition, including rejection when a
single modded item exceeds the finite batch allowance. The human reserve guard
does not turn inaccessible or fogged food into usable reserves.

## Verification

- Full Python suite: **1304 tests passed**.
- API contract audit: **313 registered routes**, no missing literal route and
  no duplicates; no runtime contacted.
- Native Release-1.6 compile: **0 warnings, 0 errors**.
- Actual-source native checks: 33 instant-building/progress, 8 thermal transfer,
  6 predation-intent, 13 quest validation, 5 kitchen-footprint and 23 new
  observation/connected-vein/feed/surgery cases; one additional production
  reward-index mutation scenario. These are offline boundaries, not game jobs.
- Sequence fixtures cover accept, reject, defer, new source, changed worker,
  changed terms, both clocks, JSON persistence, tick rollback, exact thermal
  care yielding, failed feed delivery and paid bed placement after a lost reply.
- Cached-model offline startup replay exited the equipment loop. The separate
  mining/welfare replay produced valid typed deferrals in four scenarios across
  both option orders; the model deferred those offered jobs. That establishes
  neither actual mining/feed dispatch nor optimal choices. The thermal replay
  chose both offered rescue pairs and preserved each job across eight cycles.
  Every transport was an in-memory fixture; game mutations were zero.

Tests and builds do not establish autonomous survival, optimal economic choices,
completed native work, defense outcomes or a victory. Actual sustained food,
animal heat/feed, care, research, trades and finite ending progress remain live
gates for a separately authorized future run. Raw playtest data stays private.

## Native package verification

Source commit: `70486e27b4f9a8856c582ba3f956167fce997971`, committed before
the final native build. Distributed DLL: `1.10.0+70486e2`, 2,592,256 bytes,
SHA-256 `b2bb45b75bb92fcb0e62cff2a11b81e718027764c2ae2e26701826b0d09da2e9`.
The isolated install-payload copy matched all **62** source-file hashes and
included all three new runtime modules. It did not replace the game installation.
See [the package record](postmortem-native-package-2026-10-10.json).
