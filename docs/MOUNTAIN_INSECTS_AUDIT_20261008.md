# Mountain, insect and Shorts audit — 8 October 2026

Follow-up: [systemic runtime verification](SYSTEMIC_COLONY_VERIFICATION_20261008.md)
records later entrance/heat/furnishing corrections and positioning progress
checks. Open issues and test counts below describe this earlier checkpoint.

## Review scope

The user requested more creators, Shorts, insect defense and life inside rock. The private review covered 28 original videos from 22 channels, including 17 Shorts. There are 27 saved public caption tracks (32,547 words): 25 full-track reads and selected chapters from two long videos. OmegaConstruct had no obtainable captions; its description and frame at 1:53 were reviewed. The Exterminater Short also had a visual geometry check. This is not a claim of watching every long video in full. Full caption text remains outside the repository and package.

Primary examples:

- [Rhadamant: building a secure mountain base](https://www.youtube.com/watch?v=MuZVSReWRw4&t=1320s): staged excavation after functional surface facilities, with hauling, routes, roof and heat exhaust planned.
- [ElanaOrama: infestations](https://www.youtube.com/watch?v=syvoIJf9P2M): probabilistic bait, fighting, treatment, hive removal and the costs of burning.
- [OmegaConstruct: mountain infestations](https://www.youtube.com/watch?v=JfnIBG8nMVo&t=113s), [Exterminater: mountain positions](https://www.youtube.com/shorts/SjyQZ7dCskA): space behind a narrow enemy entry, prepared melee and shooting groups, replacements and rescue.
- [Daggoth03: mountain versus surface](https://www.youtube.com/shorts/D_MWTMrzH4w): an explicit conditional choice.
- [Consieplays: kitchen](https://www.youtube.com/shorts/CmzXYFwnsmI), [Mistr Games: straw floor](https://www.youtube.com/shorts/WocBDxMR7cU): useful logistics ideas accompanied by claims requiring correction against current game definitions.

## Current definitions and applicability

Installed Core distinguishes thin rock roof from thick mountain roof. Native removal already checks roof support. The current cooking skill table gives FoodPoisonChance 0.0015 at Cooking8. StrawMatting has Cleanliness -0.1, FilthMultiplier 0.05 and Flammability1.5; SterileTile has Cleanliness +0.6. Fungus requires darkness and suitable fertility; fungal gravel requires thick roof and its designator is added by Tunneler. First harvest still needs food, labor and suitable temperature beforehand.

Native active_mods contains Core, Royalty, Ideology, Biotech and Anomaly, without Odyssey. Its new insects are not current regression cases. Caption errors, old numbers, bait probabilities and exact spawning temperature thresholds have not been promoted into validated native mechanics.

## Saved colony observations

Prepared tails are bounded to 8MB and at most100 decisions; command frequency is not worker hours.

- Lenrobum first hour, tick990966: food0,23 crop choices/64 decisions; one revolver, two knives and armor_sharp0. Barracks47 has native mountain_cells0 and one observed adjacent door.
- Lenrobum fifth-hour **closing**, tick2360865: food0,88 crop choices/100 decisions. This differs from the earlier primary83/100 window. Fenix has no observed weapon; Todd has a revolver with impaired manipulation. Bed rooms50/65 have mountain_cells0.
- Western/Thieron final, tick2248796:11 fallback_line responses positioned the actor with no attacking pawn and unverified completion. Eleven earlier minute samples show drafted Wait_Combat as hunger worsened. That supports investigating a labor lock, not claiming its sole responsibility for death. Barracks80 has mountain_cells0; its125,144 door is separate from the laboratory's137,151 door. Three hives elsewhere do not establish current aggression.

## Source corrections and open defects

The mountain doctrine prompt now includes excavation/hauling cost, roof support, entrance and evacuation, insect positions, combustible contents, food/fuel, fungus eligibility and cooler exhaust. It no longer promises blanket fire resistance.

The read-only card adds underground_status, joining native mountain roof observations to rooms and recording observed door adjacency, climate devices and hives. Native roof coverage is selective (patient/bed/kitchen rooms); absent coverage remains null. Complete room cells and known door geometry are required. Door adjacency does not certify independent safe exits or melee positions. An unavailable module cannot certify no hives.

Open mechanical gaps remain:

1. mining_bedroom_rect selects solid7×7 rock without establishing an accessible entrance, roof type, hive situation and evacuation plan.
2. Mountain furnishing chooses cold electrical heat from researched Electricity; that does not establish a powered network. Its cold non-electrical variant has no separate heating plan.
3. furnished is recorded after placing blueprints rather than observing actual usable completion.
4. infestation_choke already has capable group and native geometry checks. infestation_burn is a description without a supported executor; burning a living compartment is not a validated tactic.
5. Repeated fallback positioning needs actual threat/progress evidence and a safe return to productive work.

These gaps were identified from source and saved observations; the mountain executor was not replayed. Inspected sleeping rooms were aboveground, so prior deaths are not attributed to mountain housing.

## Verification and next evidence

Eleven card tests passed, including four new boundaries for selective roof coverage, doors in different buildings, incomplete/multi-cell geometry and unavailable native data. The changed strategy module imports successfully. Three saved native checkpoints generated cards and SVGs through direct script execution. git diff --check passed. The prior1268-test full-suite result predates this addition.

The running package/DLL was not changed. No game commands, model replay or new generation were used. Private report, source index, native definition hashes, comparison cards and verification.json are under outputs/laya-mountain-insects-audit-20261008.

Future validation should establish completed food and heat supply, usable rooms, available protected caregivers, actual armed positions and attacks, recovery after threats, assigned research, productive recruits and transaction outcomes. A staged mountain expansion must justify its labor while preserving those chains.
