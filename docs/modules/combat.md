# Combat and threats audit

Version: installed RimWorld 1.6.4871; Core, Royalty, Ideology, Biotech, Anomaly; Odyssey inactive. Offline tests validate planning, not battlefield outcomes. No game or model session was launched.

## Requader follow-up, 2026-10-03

Injured ranged pawns retain `stationary_fire` when actual native weapon
availability and shootable target IDs verify a shot. It never issues movement;
moving tactics retain capacity checks. Repeated same-target `AttackStatic` keeps
the ongoing warmup. An uncontrollable roster reports blocked defense.

Care observations expose actual patient identity and position; FeedPatient uses
target B. Safe bedside care is protected, while exposed traveling caregivers can
defend. Covered retreat can move toward a real shooter with a verified shot,
checking path nodes for fire, traps and live threats. The nearest three covering
shooters share a maximum sixteen extra path attempts per order across fighters.
The original checked fallback remains. Passive animals do not become staged
human raids. Offline repeated-cycle and native compile checks pass; no battlefield
outcome is claimed. See the [postmortem](../audits/requader-postmortem-2026-10-03.md).

| Threat/mechanic | Existing support | Remaining limitations |
|---|---|---|
| Human assault, ranged/melee contact | Native jobs, cover/range, retreat, cooperative melee | Cover templates cannot guarantee a safe route or successful fight. |
| Insects / guarding hives | Passive-hive distinction, verified doorway choke, lure/backstep, emergency gun acquisition | Heat/ignition plans are descriptive catalog entries; no verified sealed-room burn control. |
| Mechanoids / clusters | Ordinary target selection, ranged/melee tactics | Actual equipped EMP and smoke verbs, native shell reload/mortar targeting and visible active turret attack options now execute. Adaptation, shields and accuracy remain native uncertainty. |
| Kidnapping | Carrier interception, target preference, civilian exposure risks | Interception requires an actual carried player-owned victim plus kidnapping job/lord intent; carrying an enemy ally or unknown victim is not evidence. |
| Siege / preparing raiders | Preparing-lord/job detection, long-range harassment, sniper options | Reload under native hold-fire, observe the actual loaded shell, then select a live in-range target. No claimed shield timing or guaranteed hit. |
| Fire / extreme heat | Director evacuation/care infrastructure; combat catalog mentions fire retreat | Visible hostile structures and native options are observed; no complete fire-safe movement planner. |
| Psycasts / mental states | Castability, focus/heat/cost, hostile/support casts; mental-state fighters excluded | Unknown target immunities and ability-specific hazards remain native API validation concerns. |
| Anomaly entities | Generic live pawn threats can be fought | Invisibility, hypnotized victims, swallowed pawns, regeneration/reanimation and unnatural darkness are not complete tactical planners. |

## Concrete changes

1. **Zero distance was erased by Python truthiness.** `distance_to_nearest_opponent or 9999` interpreted immediate contact as distant safety. It could suppress retreat/backstep and protect a tending medic directly beside an attacker. `opponent_distance` preserves zero, rejects invalid/nonfinite values, and only protects emergency medical care with confirmed distance greater than four. Unknown telemetry no longer proves a medic safe.
2. **Unknown positions were ranked as nearest attack targets.** Missing hostile coordinates previously returned distance zero. Target ranking now uses confirmed opponent-distance telemetry or unknown infinity; fighters in mental states, incapable fighters and fighters without coordinates do not establish targeting geometry. A known nearby target wins over an unlocated high-power target, preserving carrier priority in actual interception.
3. Added compact `threat_facts(snapshot)` with contact, carriers, preparing enemies, mental-state colonists and explicit mechanism uncertainty for native Laya decisions. Integration hook: include this object early in combat `choice_context` in `rimworld_laya.py`. It does not add unimplemented tactics or replace model choice with fixed formations.

## Primary evidence

Installed `Data/Core/Defs/DamageDefs/Damages_Stun.xml`: EMP `harmsHealth=false`, stun adaptation 2200 ticks and loaded EMPResistance stat. A generic EMP-as-damage strategy is therefore unsound. The executable EMP option uses actual native projectile DamageDef EMP and AttackStatic; native smoke uses BlindSmoke projectile gas and the same ordinary firing job. No artificial stun/damage is applied.

Installed `Data/Anomaly/Defs/ThingDefs_Races/Races_Entities_Misc.xml`: Revenant has Flammability 0; descriptive reveal methods do not establish that setting a revenant on fire will damage it. Official [Ludeon Anomaly integration changes](https://ludeon.com/blog/2024/04/integrating-anomaly-more-with-the-rest-of-the-game/) independently documents the flammability adjustment. Official [Anomaly announcement](https://ludeon.com/blog/2024/03/anomaly-expansion-and-update-1-5-announced/) establishes specialized anomalous threats; current installed XML takes precedence over release descriptions.

The installed Assembly-CSharp and existing native CombatTacticsHelper resolve actual positions with `IntVec3.DistanceTo`; zero is valid contact, not missing telemetry. Changes preserve finite numerical zero throughout Python planning. No arbitrary movement speed advantage or safe fighting distance was invented.

## Native tactical workflows and threat activation

`CombatNativeHelper` exports exact `(tactic, fighter, target, defense)` alternatives with benefit/risk/cost/inaction/uncertainty. Five workflows now have normal native execution:

* `emp_control`: an actually equipped available EMP verb, a valid in-range mechanoid/turret/shield target and a friendly-blast check. EMP controls the target; conventional damage is still required.
* `smoke_advance`: an actually equipped BlindSmoke projectile weapon and a shootable hostile turret. It schedules smoke fire; it does not promise safe advancement or stop overhead/melee attacks.
* `mortar_reload`: an empty reachable suitable unroofed mortar with existing permitted reachable shells; normal ManTurret loads through the game. Native hold-fire is turned on. It does not silently change shell filters or pretend a nearest preview shell is the loaded round.
* `mortar_counterbattery`: only an actually loaded shell, native minimum/maximum range, no thick roof over target, usable barrel/fuel and conservative friendly blast/scatter exclusion. ManTurret and native OrderAttack execute with hold-fire turned off. Other ammo after future reloads must be observed before a new target order.
* `attack_structure`: normal AttackStatic or AttackMelee against an observed active hostile turret, using actual weapon availability/range or native reachability. Turret explosions and shield effects remain uncertain.

Visible hostile buildings remain in context, but `active_threat` is true only for hostile turrets with an attack verb which are awake, powered and initiated where those components exist. Dormant clusters, noncombat buildings and fogged structures do not create a permanent combat loop. Native tactical target collection follows this same rule. Shell attacks reject a carrier holding a player-owned pawn and conservative nearby friendly blast/scatter exposure. This is not a complete path or friendly-structure certification.

Kidnapping fields now include actual victim ownership, faction and job/lord intent. Python target preference and opportunity generation require both actual player victim and kidnapping intent. A rescue of an enemy ally is not treated as colonist abduction.

The shared native helper excludes distant active tend/rescue/feed/surgery/deathrest/childcare/lesson jobs from drafted tactical staff; direct contact can permit emergency defense. Python checks both patient target A and B for feeding and protects native correctly spelled BottleFeedBaby, breastfeeding carry, safety carry, adult play and lessons. Root director has matching protections. Existing psycast/native ability validation and Society/Resilience medical workflows remain separate executable families.

The infestation choke now requires a real owned doorway, wall flanks, enemy approach on one side, a healthy armored melee front and at least two capable ranged pawns behind. Root native integration uses the exact front/back cells and safe paths. It does not invent a sealed-room burn plan.

## Additional primary evidence

Installed Core `ThingDefs_Misc/Weapons/RangedIndustrial.xml`, `RangedIndustrialGrenades.xml`, `ThingDefs_Items/Items_Resource_Shell.xml`, `ThingDefs_Buildings/Buildings_Security.xml`; Biotech native childcare job definitions. Decompiled installed `Building_TurretGun.OrderAttack`, `AttackVerb`, `JobDriver_ManTurret` (native shell loading/refueling), `CompChangeableProjectile.LoadedShell`, `CompMannable`, `CompCanBeDormant.Awake`, `CompInitiatable.Initiated`, `WorkGiver_Scanner.HasJobOnThing` (default delegates to JobOnThing), `WorkGiver_Teach` (job construction mutates child's teacher target), `WorkGiver_BringBabyToSafety` (NonScanJob), and native childcare predicates.

Observation no longer constructs Resilience care jobs or Society breastfeeding/bottle/carry/warden hemogen/interrogation jobs. Exact native predicates replace default HasJobOnThing paths which allocate jobs. Gameplay random state used by read-only play eligibility is pushed/popped. Job construction and teacher linking occur only during POST; failed teacher dispatch restores its previous link.

Official [Ludeon update archive](https://ludeon.com/blog/page/8/) documents mortar miss-radius adjustments; [Ludeon development notes](https://ludeon.com/blog/?from=AppAgg.com) identify a smoke/EMP incendiary-classification correction. These reinforce why installed projectile definitions and native verbs decide behavior rather than weapon-name assumptions. Supplementary browsed [Mortar](https://rimworldwiki.com/wiki/Mortar), [EMP shell](https://rimworldwiki.com/wiki/EMP_shell) and [EMP grenade](https://rimworldwiki.com/wiki/EMP_grenade) references provided audit leads; implementation mechanics above use installed primary evidence.

## Verification

`tests.test_combat_module`: 11 scenarios cover contact zero/unknown distances, care patients including animals/target B, real carried victim plus kidnapping intent, enemy/unknown carried victims, building-only threats, all feasible native tactical families, missing-equipment refusal, exact native IDs and childcare/surgery/deathrest protection. Combined local Society/Resilience/Combat module suite: 36 tests pass. Parent owns full scenario suite and shared C# integration. No game/model launch or runtime battle verification; firing, stun, gas, shell loading and damage outcomes remain native and unobserved.


## Reviewed acceptance and retry follow-up (2026-10-02)

`rimworld_laya.command_acceptance` interprets actual response contracts, including
explicit `applied:false` and `success:false`, rather than treating any received
response as success. The native tactic DTO supplies `drafted_pawn_ids`,
`positioned_pawn_ids`, `attacking_pawn_ids`, `psycast_queued`, optional psycast/
target identity and notes. All empty acceptance fields mean refusal. A structured
explicit applied flag takes precedence. Unknown endpoint responses remain unknown.

Installed speed, pawn status/job/medical tend/bed-rest/feed and colonist work
priority services use non-generic `ApiResult.Ok()` with `success:true` and no data
member. These acknowledgments remain accepted. Generic wrappers are unwrapped;
unknown data is not promoted to applied. Accepted invocation/queued work never
proves hit, cure, rescued patient, weapon equipped or combat victory.

Command batches preserve response alignment, per-command tri-state acceptance and
partial acceptance. On a POST error the failed row carries its error and unknown
outcome; earlier accepted work remains visible. A confirmed stale-target 404 is
rejected and triggers fresh planning. Remaining commands are not sent after a
failed POST. Unknown POST transport outcomes are explicitly reported because the
server may already have executed the request.

A rejected tactical record retries after five wall-clock seconds, with material
combat signature changes permitting earlier reconsideration. Rejected preemptive
moves no longer renew a sixty-second continuation wait. Automatic advance replaces
the recorded current-hop response; an earlier accepted move cannot mask denial
of a later hop. Native acknowledged Goto/AttackStatic waits remain unchanged.
Drafting by itself is an applied status change, but cannot establish tactical
movement/attack acceptance for the continuation hold.

Native interception verifies `CombatNativeHelper.Kidnapper(target)` before any
fighter drafting: a hostile must actually carry a player-owned pawn and have
kidnapping job/lord intent. Ordinary focus fire against other carriers remains
normal focus fire; its aggressive carrier-chase fallback is reserved for actual
kidnappers. Interception still risks separating pursuers and exposing the base.

Offline targeted suite (combat follow-up, combat module/scenarios, affordances,
progression and existing preemptive helper regression) passes 132 tests. Tests
cover empty/native refusal, non-generic success envelopes, unknown/partial/error
outcomes, five-second retry sequences and overwritten failed-hop acknowledgment.
The interceptor ordering check is a native source assertion, not runtime proof.
Installed ILSpy shows Pawn_JobTracker.TryTakeOrderedJob immediately returns true
for an equal current job, preserving existing attack warmup for repeated identical
orders; this mechanism was verified rather than changed. No game/live API/model/
observer/build/git operation was run in this follow-up.
