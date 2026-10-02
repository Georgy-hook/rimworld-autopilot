# Combat and threats audit

Version: installed RimWorld 1.6.4871; Core, Royalty, Ideology, Biotech, Anomaly; Odyssey inactive. Offline tests validate planning, not battlefield outcomes. No game or model session was launched.

| Threat/mechanic | Existing support | Remaining limitations |
|---|---|---|
| Human assault, ranged/melee contact | Native jobs, cover/range, retreat, cooperative melee | Cover templates cannot guarantee a safe route or successful fight. |
| Insects / guarding hives | Passive-hive distinction, verified doorway choke, lure/backstep, emergency gun acquisition | Heat/ignition plans are descriptive catalog entries; no verified sealed-room burn control. |
| Mechanoids / clusters | Ordinary target selection, ranged/melee tactics | EMP is catalogued but no active Python executor hook; adaptation/resistance and hostile static turrets need more live data. |
| Kidnapping | Carrier interception, target preference, civilian exposure risks | Carrying any pawn is currently treated as kidnapping evidence; carried pawn faction/job intent not fully represented. |
| Siege / preparing raiders | Preparing-lord/job detection, long-range harassment, sniper options | Not a complete enemy mortar/ammunition strategy; descriptive mortar entry lacks executable hook. |
| Fire / extreme heat | Director evacuation/care infrastructure; combat catalog mentions fire retreat | Combat pawn-only snapshot cannot prove non-burning routes or active fire coverage. |
| Psycasts / mental states | Castability, focus/heat/cost, hostile/support casts; mental-state fighters excluded | Unknown target immunities and ability-specific hazards remain native API validation concerns. |
| Anomaly entities | Generic live pawn threats can be fought | Invisibility, hypnotized victims, swallowed pawns, regeneration/reanimation and unnatural darkness are not complete tactical planners. |

## Concrete changes

1. **Zero distance was erased by Python truthiness.** `distance_to_nearest_opponent or 9999` interpreted immediate contact as distant safety. It could suppress retreat/backstep and protect a tending medic directly beside an attacker. `opponent_distance` preserves zero, rejects invalid/nonfinite values, and only protects emergency medical care with confirmed distance greater than four. Unknown telemetry no longer proves a medic safe.
2. **Unknown positions were ranked as nearest attack targets.** Missing hostile coordinates previously returned distance zero. Target ranking now uses confirmed opponent-distance telemetry or unknown infinity; fighters in mental states, incapable fighters and fighters without coordinates do not establish targeting geometry. A known nearby target wins over an unlocated high-power target, preserving carrier priority in actual interception.
3. Added compact `threat_facts(snapshot)` with contact, carriers, preparing enemies, mental-state colonists and explicit mechanism uncertainty for native Laya decisions. Integration hook: include this object early in combat `choice_context` in `rimworld_laya.py`. It does not add unimplemented tactics or replace model choice with fixed formations.

## Primary evidence

Installed `Data/Core/Defs/DamageDefs/Damages_Stun.xml`: EMP `harmsHealth=false`, stun adaptation 2200 ticks and loaded EMPResistance stat. A generic EMP-as-damage strategy is therefore unsound. Existing catalog EMP and smoke descriptions were not activated without executor support.

Installed `Data/Anomaly/Defs/ThingDefs_Races/Races_Entities_Misc.xml`: Revenant has Flammability 0; descriptive reveal methods do not establish that setting a revenant on fire will damage it. Official [Ludeon Anomaly integration changes](https://ludeon.com/blog/2024/04/integrating-anomaly-more-with-the-rest-of-the-game/) independently documents the flammability adjustment. Official [Anomaly announcement](https://ludeon.com/blog/2024/03/anomaly-expansion-and-update-1-5-announced/) establishes specialized anomalous threats; current installed XML takes precedence over release descriptions.

The installed Assembly-CSharp and existing native CombatTacticsHelper resolve actual positions with `IntVec3.DistanceTo`; zero is valid contact, not missing telemetry. Changes preserve finite numerical zero throughout Python planning. No arbitrary movement speed advantage or safe fighting distance was invented.

## Verification

`tests.test_combat_module`: six regression scenarios pass (zero contact withdrawal/backstep, medic contact, unknown medic distance, invalid telemetry, unknown target position, factual risk context). Existing `tests.test_combat_scenarios`: 51 scenarios pass. Production QA alongside combat: 11 tests pass. Live AI choices and battle outcomes remain unverified.
