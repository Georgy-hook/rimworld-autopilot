# Wildlife: hunting, taming and training — RimWorld 1.6.4871

## Verified mechanics and gaps

The installed Assembly-CSharp.dll and Core XML are the mechanical authority. The [Ludeon animal-taming release](https://ludeon.com/blog/2015/08/rimworld-alpha-12-animal-taming-released/) confirms normal taming/training use food and handling work; its historical values are not used for current calculations. Odyssey is not active and its special trainables are not assumed available.

| Mechanic | Existing coverage | Changes / limits |
|---|---|---|
| Ordinary hunting | Designation + unspecified Hunting priority | Native solo job binds the selected capable hunter; target reservation limits ordinary Hunt to one actor. |
| Retaliation chance | Species/difficulty base only; >5% classified risky | Exports PawnUtility chance at current and proposed firing distances, using actual HuntingStealth and instigator gene/role factors. The confirmation uses the exact overload invoked by Pawn_MindState, not the distance what-if estimate. The actual damage-event call and explicit distance what-if estimates are distinct; injury likelihood is a separate heuristic. |
| Contextual injury risk | Aggregate gun count and weapon-name list | Manageable/elevated/high/unknown comparative heuristic uses only selected feasible actors: attack cycle, native distance shooting factor, weapon factor, weather/cover/body size, AP vs armor, remaining target healthscale, movement, actor health and actual worn armor coverage. No precise victory probability. |
| Group hunting | Unsupported; bystander weapons could misleadingly reassure | Explicit selected IDs receive verified reachable trap/fire-free firing positions, normal Goto followed by queued AttackStatic. No immediate replacement of Goto. Partial groups are cancelled, not treated as the full force. Moving targets can invalidate jobs. |
| Group lifecycle | Generic peaceful undraft could interrupt it | Persisted lease protects only observed jobs; unknown readbacks retain conservative protection. Health high-water + total time budget prevents movement loops. Scoped cleanup preserves unrelated queued work and previously drafted actors; downed wildlife can be handed to a normal Hunt job. New combat/medical needs may preempt. |
| Taming | Skill/pen gates and generic handler priority | Inspiration module owns exact target/handler binding. Hunting revenge and failed-taming revenge remain separate. |
| Trainability | Native supported/learned/wanted, recursive prerequisite policy | Adds every loaded TrainableDef, steps/total, prerequisites, native handler interaction/food readiness, decay interval, master and follow policy. Already-wanted training is not requested repeatedly. |
| Learning execution | Training policy acknowledged | Fresh native readback distinguishes wanted policy, actual steps and learned state. Existing normal training jobs still need food/time/cooldown. |

## Installed native facts

`PawnUtility.GetManhunterOnDamageChance` multiplies species chance by difficulty; an actual instigator adds the distance factor (3× near one cell, 1× at thirty), HuntingStealth and gene/role factors. `Pawn_MindState` pack escalation is conditional: same race/crossAggro, same district, within 24 cells, big-threat difficulty enabled, and a further roll. It is not an automatic map-wide herd attack.

Core Thrumbo: damage-revenge base 1.0, no failed-tame revenge override (default zero), sharp natural armor 0.6, blunt 0.4, health scale 8, speed 5.5, Advanced trainability. Core Megasloth: damage-revenge 0.5, failed-tame revenge 0.3, health scale 3.6, speed 4.8, Advanced trainability. Live stats can differ with age, injuries, genes or loaded mods; the endpoint supplies the actual pawn stats. No species is excluded by name.

`ArmorUtility` checks worn apparel covering the struck body part separately from natural pawn armor. The module exports the worn items and a coverage-weighted maximum apparel rating over remaining outside parts. That summary is an injury heuristic, not the exact layered per-hit armor result. Planned hit quality uses native distance factors and cover/weather/body-size factors; darkness, gas, movement and random rolls remain uncertainty.

`Pawn_TrainingTracker` requests prerequisites recursively. Training steps decay with a Wildness-dependent interval; Tameness may decay and eventually return an animal to the wild. Wanted training is ordinary automatic learning/maintenance, not a guarantee that a handler has completed it. Core Obedience needs 3 steps, Release 2 after Obedience, Rescue 2 after Obedience with minimum body size, Haul 7 after Obedience with minimum body size. Loaded native definitions govern DLC/mod variations.

Concrete training boundary: a Yorkshire terrier may have learned/wanted Obedience and an assigned master while Release remains available; native body-size restrictions can block Rescue/Haul. A successful policy readback must never be reported as learned Release.

## Verification and limits

Offline scenarios cover equal retaliation with weak versus strong selected forces, worn armor, range hit quality, armor/pack/remaining health/attack timing, missing stats, bystanders, Goto+queued-shot matching, lost acknowledgments, incomplete status, stalled moving prey, scoped cleanup, partial-group refusal, loaded trainables and policy-versus-learning readback. Native build is coordinated by the parent. No live hunting/taming/training order was issued during implementation.

Installed damage-event caveat: Pawn_MindState.Notify_DamageTaken invokes GetManhunterOnDamageChance(pawn, instigator) without its optional distance argument. In this inspected build, default -1 reaches the clamped near-distance factor. Current/planned-distance overload values are exported as what-if information, not claimed to be the exact trigger probability. Per-hit confirmation uses the actual damage-event overload.

Parent integration verified the installed GET contexts and the actual terrier
boundary: Obedience3/3, Release available0/2, Rescue/Haul unavailable. A real CUDA
model replay selected Release with Vega without sending game orders. Learning
completion remains pending. An actual candidate_actions regression now covers
emergency food focus, unavailable-endpoint fallback, corpse/butchery priority
and preservation of an existing group's cleanup lifecycle.

The first prey-versus-defer comparison already names the best contextual harm label among verified feasible plans and its actual mode, actor count and weapons. It describes an available option, not automatic participation: the next choice still selects the exact hunter/team, followed by confirmation. Unselected bystanders never improve that summary.
