# Colony verification and comparison

Added 7 October 2026 at the user's request. This is observation and evaluation;
it does not insert corrective orders into an autonomous game.

## Evidence package for every colony

Keep campaign ID, version/source/DLL hashes, scenario, storyteller/difficulty,
world/tile, founders, baseline tick, start time, technical pauses and discarded
branches. Compare the first hour, later hourly checkpoints and final outcome.
Use both autonomous elapsed time and game days. Different climates, starting
workers and emergency speeds are material differences, not interchangeable trials.

At each checkpoint retain:

- A real game screenshot with its native tick (or a before/after tick interval).
  Keep a base overview and, where needed, an interaction/defense close view.
  Record UI/camera-only actions used for the picture. Do not issue pawn orders.
- Native snapshot, rooms/roofs, building IDs/coordinates, actual power networks,
  zone settings/cells and crops. A coordinate diagram supplements the screenshot.
- Bounded decisions (last 8 MB, at most 100 records), minute timeline, native
  letters, corpses and exact-cause evidence. Record the sampled time interval.
- Actual save mtime/XML tick/campaign and process/heartbeat/window/log checks.

`tools/colony_verification.py` turns prepared JSON evidence into a consistent
card and a coordinate SVG. It has no network or model access and never changes
the game, director state or source evidence. It refuses mixed campaigns and
more than 100 decision records. Missing information stays null/unknown.

```powershell
python tools/colony_verification.py --snapshot snapshot.json --evidence evidence.json `
  --metadata run-metadata.json --baseline baseline-snapshot.json `
  --timeline timeline.json --decisions-tail decisions-tail.json --events events.json `
  --review assessment.json --output verification.json --layout layout.svg
```

The review JSON contains evidence-linked `assessment`, `population_changes`,
`animal_losses`, `animal_loss_coverage`, `raid_outcomes`, `income`, `economy`,
`progression`, and `screenshot`. It is a human review of observed consequences;
the script does not manufacture a score, victory or causal claim.

## Mandatory assessment

| Area | What to verify | Evidence of useful completion |
|---|---|---|
| Site | Biome/season, terrain/fertility/water, distance from landing supplies and food, hazards, expansion routes | Actual coordinates and native terrain/path evidence; reason in the offered/selected site context |
| Shelter/layout | Bed ownership, roof and temperature, free doors/interaction cells, kitchen/storage/hospital adjacency, contamination, animals and corpses near living areas | Occupied usable room, safe temperature, actual access; no inference of safety from roof alone |
| Construction | What was offered and built, material/fuel cost, queue, useful function versus delayed essentials | A completed functional building, its real work/outputs and prerequisite networks |
| Food/crops | Zones and exact crop, edible versus beauty purpose, season/growth/harvest, water/temperature, harvest→haul→butcher→cook→eat | Delivered nutrition and repeated meals/food levels; flowers and designated plants are not food stock |
| Power | Alternatives/research, fuel source and route, topology, generation and consumption, cooler/stove connection | Actual powered useful consumer and temperature/production result; generator existence is insufficient |
| Animals | Initial/acquired roster, feed, shelter, injury treatment, training/masters and use, deaths versus intentional slaughter | Pawn identity plus native letter/cause or corpse, observed care/training; wild hunted prey is separate |
| Defense/raids | Each arrival, composition, weapons, traps/cover and actual use, pursuit/retreat, casualties, kidnapping, cleanup and return to work | Verified killed/retreated attackers and surviving roster; zero enemies alone is not a successful defense |
| Population | Founders, permanent joins, prisoners/recruitment, temporary guests, departures, kidnapping and death | Native affiliation/quest terms and actual change; man in black is emergency replacement, not planned growth |
| Economy | Proposed product, available skills/materials, production buildings/bills, traders/diplomacy, transactions | Actual produced sellable stock, completed transaction and net income; an orbital doctrine is not earnings |
| Life plan | Concrete ending, compatible technology/economy/diplomacy, food and workforce needed at each stage | Completed prerequisites/milestones and native ending evidence; accepting an obligation is not its reward |
| Priorities | Urgent needs versus recreation/beauty/endgame; sampled work and lost opportunities | Offered options → model selection → fresh validation → actual job/result → consequences |
| Repetition | Same actor/target/parameters, rejection reason, pending work, true changes over time | A bounded trace with progress/no progress; identical labels alone do not establish an infinite loop |

## Raids, losses and comparisons

Maintain an event ledger keyed by campaign and pawn/letter ID plus native tick.
For a raid record `arrived`, `ongoing`, `repelled_verified`, `loss`, or `unknown`,
with supporting files/ticks. Partial defense can coexist with death or kidnapping.
Do not count predation, social fights or mental-break violence as repelled raids.
Animal deaths must distinguish bonded/tamed losses, crisis slaughter and normal
food slaughter. Being absent from the map is not evidence of death.

For each new colony/checkpoint compare these columns with prior evidence:
site/climate; clean autonomous duration/game days; founders retained; confirmed
people/animal losses; raid outcomes; functional housing/kitchen/power; food crop
and meal continuity; research; permanent growth; actual income; ending milestones;
repeated errors and confirmed improvement. Retrospective missing screenshots,
loss counts or causes remain unknown. Do not infer them from another campaign.

Assessment states are **confirmed useful**, **confirmed problem**, **pending**,
and **unknown**. Explain consequences and likely cause separately. A correction
requires a trace of the responsible context/filter/ranking/executor and a relevant
offline sequence check, then a later observed result. Fixes are done after the
observation is ended or explicitly interrupted; they are not live coaching.

The purpose is to check whether the colony converts decisions into food, safety,
people, income and an ending. More buildings, more API acceptance or more tests
do not by themselves improve this assessment.
