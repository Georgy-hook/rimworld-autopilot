# Systemic colony planning verification — 8 October 2026

## Request and conclusion

The user asked whether the development and mountain/insect reports actually
reach Laya, and why successive colonies fail before an ending. The audit found
defects in observation delivery, candidate availability, actor ownership and
progress accounting. Adding a longer tutorial prompt would not repair these
mechanisms: the model's state window is 312 tokens.

This change preserves a complete short plan through selection, keeps progress
observations independently of the latest command, exposes productive workers
while other actors provide care, and distinguishes accepted orders from work.
It does **not** establish a live victory or explain every death with one cause.

Earlier evidence and sources are in
[development audit](COLONY_DEVELOPMENT_AUDIT_20261008.md) and
[mountain/insect audit](MOUNTAIN_INSECTS_AUDIT_20261008.md). Their earlier test
counts and open issues describe those checkpoints; this is their follow-up.

## What the recorded colonies demonstrate

Only prepared bounded decision tails were inspected, not complete JSONL logs.

| Recorded observation | Supported diagnosis | Limit |
|---|---|---|
| Lenrobum 990966: empty food, crop choices 23/64, one ranged weapon for three fighters, no cover | Food bridge, available labor and defense preparation need to survive the selection window together | Command counts are not pawn working hours |
| Lenrobum 2360865: empty food, closing sample 88/100 crop choices, Todd/Fenix sampled Repair | Configuration intent and possible yield did not establish supplied food or useful labor allocation | Six ready designated berry plants were still observed; ordinary collection was not universally impossible |
| Western 698451: hungry Stone, incapacitated Jill already in bed, mature designated berries | A rest-priority policy cannot change a downed patient's existing LayDown job; another worker can still collect food | Jill's wounds/catatonia remain clinical needs, not a claim that all care is unnecessary |
| Western final tail: 11 fallback_line responses positioned Ondra with no attacking pawn; sampled Wait_Combat as hunger worsened | Accepted positioning needs engagement/progress checks and a safe work window | This is not the sole established cause of Ondra's death |
| Western native defeat 2248520, last death Malnutrition2248121 | The run failed; selected research and built infrastructure did not deliver a completed ending | All previous causes, animal losses and partial raid outcomes remain separately recorded |

Warm roofed ground sleeping places were previously excluded from the development
gate. That explains lost preparation choices in Thieron; it does not explain
Lenrobum, which already had real beds. Their sleeping rooms were aboveground;
prior deaths are not attributed to mountain housing.

## Report-to-runtime coverage

The Markdown reports and caption collections are evidence for engineering, not
runtime prompts. Runtime uses small measured facts, action consequences and
fresh native feasibility. Public captions are not packaged or committed.

| Lesson | Actual runtime path | Result required |
|---|---|---|
| Food must arrive before the first harvest | Existing native edible crop/product and stock/consumption checks; `colony_plan.brief`; food actions and work-priority execution | Repeated harvest/haul/butcher/cook/eat, not an estimated yield |
| Useful early shelter should permit preparation | Roofed human sleeping-place capacity in the director; shared-bed capacity and ancient/prison exclusions | Completed usable shelter, temperature and fuel observed separately |
| Assign labor to a real source | Workforce missing/unassigned roles in the complete plan; priority changes read back from native state | Actual jobs/output; a priority assignment is explicitly not job completion |
| Prepare weapons, cover and patients before threats | Measured ranged fighters/cover; native actor capability, path and shot guards | Engagement, losses and recovery; no raid-letter victory counter |
| Care protects its actor rather than the whole colony | Exact protected care/retreat actors; fresh live-threat and post-combat scheduling | Preserve Tend/Feed/Rescue while unrelated safe workers act |
| Recruitment is a chain with continuing costs | Preventive prison readiness, native active quest offers, population/workforce previews and ordinary capture/purchase/join executors | Verified membership and productive assignment; offered/guest/storyteller arrival stays distinct |
| Family is not immediate adult labor | Native existing relationship/fertility and pregnancy-approach checks; family evidence in cards | Actual pregnancy, birth and continuing care; no fabricated partner or forced reproduction |
| Revenue requires a product and buyer | Empty workshop and labor observations; native production/trade plans and ledger verification | Output and a verified transaction after costs; stored silver is not profit |
| Research must advance toward a finite ending | Complete ending in every root comparison and doctrine step; native research frontier; independent progress observations | Gained points, finished unlocks and use of prerequisites |
| Mountain expansion has access, labor, heat and insect costs | Exposed north/west survey geometry, expansion readiness, two doors, actual power evidence and physical furnishing reconciliation | Safe routes/roof/temperature and actual defense remain independent checks |
| Distant passive threats must not idle the entire workforce indefinitely | Semantic positioning history and conservative safe-work actors | Fresh distance and intent, no active allied attack, no unprotected caregiver; native errands still validate paths |

## Structural changes

### Complete plan across root narrowing

`colony_plan.brief` records observed food days, free labor, sleeping capacity,
malnutrition/bleeding/thermal emergencies, weapons/cover, research, role gaps,
join offers, empty workshops, unfinished projects and the saved finite ending.
Available native research prerequisites accompany a selected route.

`laya_decisions._planning_state` reserves this unit intact before sharing the
remaining window between alternatives. Domain, family and final action calls
receive the same plan. Benefit, risk, cost and inaction receive separate space.
There is no reliance on the encoder silently preserving late JSON fields.

Doctrine comparisons also preserve ending, direction, income, diplomacy and
relevant ending constraints intact. In particular, the Empire relationship
requirement survives the diplomacy comparison. A support direction can differ
from an ending; it must not silently initiate a different terminal chain.

### Independent progress observations

`development_observations` persists bounded food, research, defense and housing
observations across command changes, waits and state-file reloads. A blueprint
ACK or unrelated order cannot erase an unchanged domain.

Research target changes do not count as research work. Newly observed projects
establish a baseline; subsequent point gains and completed unlocks establish
progress. Changing Electricity to Batteries and back at zero leaves the stall
clock intact. Tick rollback starts a new observation baseline. Unknown
telemetry remains unknown.

This supplies feedback for the model, not an assertion that unchanged housing
is inherently bad or an automatic fixed build order.

### Actor ownership and meaningful alternatives

Repeated live-threat care no longer skips all combat/development decisions.
Fresh native job ownership protects the doctor while other actors remain
eligible. The post-combat branch likewise permits independent undrafted workers
beside downed ordinary raiders after rechecking active threats. Drafted actors
and unresolved recurring entities retain their restrictions.

Rest-priority changes are excluded for a downed patient already executing
LayDown in a native bed. Feeding, rescue and tending remain available, and
ordinary rest priority is reconsidered when the patient's state changes.
Rest and animal medicine-policy consequences explicitly state that they do
not feed or cure starvation.

### Combat progress and return to work

Holding tactics record accepted positioning separately from attacks. An actor
remaining idle against the same target for at least 30 real seconds **and**
2000 ticks establishes a temporary stall. Changing formation names or a
wanderer's coordinates does not erase it. Actual range/contact, a shot,
health/intent changes or a different actor/target permit reconsideration.

Safe work requires all observed allies to be beyond the conservative threat
radius, known finite distance, staging/passive hostile intent, no kidnapping or
active attack, and preserved care/retreat actors. Only idle drafted eligible
workers may be released by Laya's safe-work choice. Missing distance, assault
or a nearby patient closes the window. This never declares the raid won.

### Ending and construction commitments

Progression canonicalizes the chosen route. RoyalAscent, VoidMonolith, ship and
Odyssey options are matched by their actual native route/site/kind, not a
generic label. Execution checks the current commitment again; pending transfer
and targeting transactions remain resolvable. An accepted route intention is
not completion or victory.

Mountain heat/light no longer depend on researched Electricity alone. A cold
unpowered room uses a fueled heat/light plan; powered furnishing requires an
observed operating network in that room. The two planned entrances must be
exposed in the rock survey. Stored food, established shelter and available
mining labor are expansion prerequisites.

Furniture intent survives reloads. Built objects, queued projects and missing
objects are separate. Accepted blueprints leave completion unverified; partial
construction or a lost project reopens only missing items. Physically completed
furniture does not certify safe temperature, roof type, fuel or evacuation.

The new planning module is in the explicit installation payload, with a test
checking local import dependencies of every packaged Python module.

## Verification

- **1287 Python tests passed**, zero failures/errors/skips. The final full run
  took 9.863 seconds (10.529 seconds including discovery/reporting).
- Sequence tests cover state reload, intervening commands, unchanged research
  across target switches, physical research progress and tick rollback;
  unchanged positioning across formation/wander changes; exact caregiver
  ownership; renewed assault/missing distance; fresh ending commitment and
  pending transfer; partial mountain construction, destruction and ACK only.
- The real cached Laya tokenizer checks root plan and severe clinical facts
  against the 312-token window, plus complete doctrine/diplomatic requirements.
- The actual cached Laya model ran offline on CUDA with four CPU threads on
  four recorded colony states, in both original and reversed candidate order:

| Recorded tick | Choice in both final orderings |
|---|---|
| Lenrobum990966 | prioritize_plant_cutting |
| Lenrobum2360865 | prioritize_plant_cutting |
| Western698451 | prioritize_plant_cutting |
| Western1225199 | harvest_food_crops_early: rice, up to40 plants, Ondra37382 |

  All 22 root comparisons retained the complete plan; measured state sizes were
  at most208/312 tokens, with no selection unavailable. The three priority cases
  had mature designated berry plants observed. The parameterized crop case
  chose an actual available worker. These are choices/assignment opportunities,
  **not** collected food or proof of optimality in every scenario.

  The earlier pass still selected resilience_rest in one ordering. Reading its
  actual native patient showed an incapacitated person already resting. The
  final feasibility correction removes that ineffective priority change,
  rather than declaring the earlier model result successful.

- Offline route inventory:311 native routes,266 literal client calls,27 dynamic
  call sites, no missing or duplicate route registrations. This checks wiring,
  not every native payload or gameplay outcome.
- Actual payload copy includes colony_plan.py; all local imports are included.
  The recorded live installation's59 files remain unchanged.
- No live replay, pawn command, save POST, memory reset, new generation, speed
  change, process restart or DLL change occurred during this verification.

Private evidence: outputs/laya-systemic-verification-20261008 contains final
test, route, payload/install, model-prompt and source-hash records. The offline
replay tool never creates a game client. Its saved memory is a fresh diagnostic
baseline, not a reproduction of every prior session's brain state.

## Remaining live evidence and unsupported work

The previous native defeat remains a defeat. Root decisions, staged files and
unit tests cannot establish survival through later raids or a completed ending.
The installed game/runtime has not received these source changes yet.

A future run must verify sustained nutrition before crop maturity, repeat fuel
and patient care, armed defense with actual engagement, return to productive
work, assigned research that gains points, productive recruits, transactions
and observed prerequisites of the selected finite ending. Original roster,
biome and season must remain part of comparisons; no fixed population count
can substitute for functioning food, care and defense.

`BuildMonument` and `Decree_BuildMonument` still lack an executor and remain
deferred. `infestation_burn` is not a supported executor. Mountain survey
geometry does not prove path connectivity, thick roof, hive safety, exhaust or
independent evacuation; full safe mountain occupation remains a live boundary.
Family formation, birth and long-term childcare are not claimed from a
pregnancy-approach policy. Unknown raid outcomes and unverified transactions
remain unknown.
