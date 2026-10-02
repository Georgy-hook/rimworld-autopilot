# Comprehensive capability audit — 0.0.7, 2026-10-02

## Scope and method

The audit starts from mechanics, not from the most recently reported symptom:
installed tutorial concepts → native definitions and engine methods → observation
fields → offered choices → ordinary execution → offline regression.
Three GPT-6.1 Sol agents researched and implemented food/animals/production,
health/environment/society/combat, and DLC systems/endings. The root integrated
the modules, pending game sessions, finite objectives, data budgets and QA.

The installed version is **1.6.4871 rev590** with Core, Royalty, Ideology,
Biotech and Anomaly. The inventory contains **83 ConceptDef records: 82 named
concepts and one abstract parent**. This is the complete installed tutorial
inventory, not a claim that 82 concepts enumerate the entire game.
Odyssey is **not installed in Data**. Its native classes exist in the shared
1.6 assembly; Odyssey paths are compiled and DLC-gated, with no claimed gameplay
verification. No game, model weights, director or colony was started.

## Mechanics and execution map

| Area | Concrete support and source of alternatives | Main owner |
|---|---|---|
| Food and butchery | Loaded recipes, actual fresh corpses/ingredients, usable tables, skills, capacity, reachable allowed stock and bill radius; finite batches with native subtype; completed compatible bills reused | sustenance / production |
| Food safety | Cook poisoning stat, dirty kitchen, current food poisoning, diet/precept risks, home-area sanitation, ordinary cleaning, preservation and storage priorities | sustenance / resilience |
| Diets and agriculture | Existing and individual food policies; loaded edible alternatives; existing crop catalog with biome, soil, temperature, season, blight and greenhouse workflows | sustenance / capabilities / architect |
| Animals | Native diets, pasture and stored feed, pregnancy, pens, medical care, rescue/tend/feed, beds/areas, herd limits, sterilization/release, milk/wool jobs; existing training/master/release combat controls | sustenance / resilience / capabilities |
| Fishing | Native Odyssey fishing zones, legal water/bank, population/frozen/repeat context, ordinary fishing job; inactive without DLC | sustenance |
| Disease and disability | Visible hediffs, capacities, bleeding, pain, immunity gain vs severity, tend quality/expiry, nutrition and environment; rescue, self-tend, feeding, rest, prevention and therapeutic native bills | resilience / society |
| Surgery and augmentation | Loaded therapeutic and implant recipes, exact body parts, actual stock, medicine, qualified doctor, suitable bed and ideology; normal anesthesia, failure and recovery | society / capabilities |
| Children, drugs, sanguophages | Infant safety/feed/play, lessons, exact earned growth awards, individual drug policies/dependencies, hemogen and normal deathrest/auto-wake | society |
| Shelter, mountain and insects | Loaded construction catalog, actual support geometry before mining/deconstruction, climate/gas/roof context, genuine one-cell defended doorway, interior melee line and rear shooters | architect / resilience / combat |
| Industry, power and logistics | Loaded non-food/non-surgery recipes including native autonomous/mech bill types; research/skills/materials; real net energy, stored power, utility policies, ordinary material hauling and exact storage footprints | production |
| Population, economy and society | Existing trader/recruitment/quest/caravan workflows, native prisoner goals, needs and beliefs, learning/recreation time and earned roles/rituals | growth / society / specialists |
| Royalty | Owned learned abilities and actual targets/costs, royal permits with native payment/cooldown, meditation/focus timetable, title/hospitality/quest prerequisites | affordances / specialists / progression |
| Ideology | Actual precepts, role/ritual eligibility and participant configuration, native ritual execution, Gauranlen connection/pruning/caste and normal dryad work | specialists |
| Biotech | Native mechs/groups/energy/waste, production and boss gates, subcore scanner choices including lethal donor risk, whole-pack xenogerm assembly, extraction/implant menus, children and sanguophage needs | specialists / production / affordances / society |
| Anomaly | Containment strength/activity, capture/transfer/study/extraction, suppression, native psychic rituals, monolith/structures/finale; visible evidence before surgical inspection/interrogation | specialists / progression / resilience |
| Odyssey | Gravship pilot/launch ritual policies, fuel/layer/destination checks, footprint/rotation/landing confirmation, native world targeting and Mechhive ending; fishing | progression / specialists / sustenance |
| General loaded mechanics | Current native ability and thing float-menu alternatives, subcore scanner command whitelist, local/destination/world targeting and real confirmation dialogs | affordances / sessions |

This map describes concrete commands and observations. It does not promise an
optimal layout, perfect breeding plan, guaranteed battle victory, or that a
queued job will complete. Construction, production, research and treatment still
need ordinary pawn labor and resources. Missing DLC, missing stock, native
blockers and changed targets do not become successful orders.

## Finite objectives

Laya must choose an available finite ending when the user's victory requirement
is enabled; indefinite survival cannot silently remain the objective. The
economic/military support direction does not automatically select the ending.

Supported ending families and distinct native steps:

- Core ship escape: constructed ship or travel to the offered landed ship;
  real prerequisites, boarding, reactor defense and launch.
- Royal Ascent: earned title/honor, offered quest, hospitality and native departure.
- Archonexus: each sale, selection of transferred people/animals/items,
  settlement cinematic, new tile and existing ideology selection, final site.
- Anomaly: discovered research and monolith progression, awakening, native
  final embrace/disrupt decision and credits.
- Odyssey Mechhive: gravship progression, destination/landing and native objective;
  the final route can finish the observed run even if the game allows continuation.

Research context distinguishes mandatory native gates from optional supporting
infrastructure. Quest acceptance, a countdown, or a chosen doctrine is not
victory evidence. Native credits events persist route/tick/text in the save.
The director and observer stop on that evidence; native GameEnded defeat is
identified independently of translated text.

## Architecture and QA repairs

1. Seven registered development domains implement collect/prepare/assess/choose/
   execute. Detailed objects remain in their domain; Laya sees the selected
   subject and actual feasible alternatives.
2. Each comparison preserves **benefit, risk, cost, inaction and uncertainty**.
   Large lists are staged by purpose/subject/operator and use short identifiers.
   The installed model has 512 tokens total and 192 for its decision head.
3. The offline tokenizer audit uses the actual cached tokenizer and encoder;
   it verifies that every compared option and every consequence field survives
   serialization without hidden state truncation. It loads no model weights.
4. Pending native targets/configurations finish before ordinary work. Higher
   modal windows block targets underneath them. Archonexus/world continuation
   can execute when no playable map exists.
5. Cold/fire early branches now preserve urgent rescue/tend/feed/infant choices.
   Immediate care also survives shelter-material and founder-equipment filters.
6. Native menus retain the original purpose; stale window IDs, targets, actor
   state, changed costs and expired native choices are rejected.
7. Read-only recipe previews no longer allocate persistent bill IDs. Stock and
   pawn facts are reused within an observation; native eligibility is refreshed
   at execution. Job construction is confined to mutation paths where possible.
8. Hostile routes, false ingredient availability, wrong recipe subtype, duplicate
   completed bills, roof support loss and false insect choke geometry were fixed
   during review rather than accepted because compilation passed.

The root's QA found and returned defects to the agents. Evidence distinguishes
Python logic tests, native compilation and tokenizer checks from gameplay.
No weights were trained and no live performance improvement is asserted.

## Complete installed Learning Helper review

Every named installed concept belongs to one of these reviewed groups. Some are
manual camera/interface lessons rather than autonomous colony work.

| Concepts | Coverage / interpretation |
|---|---|
| CapturingEntities, ContainingEntities, StudyingEntities, EntityCodex, SuppressingEntities, AnomalyResearch, ColonyGhouls, VoidProvocation | Entity/ritual/health/loaded-native catalogs and observed research. Codex is reference data; a learned command does not mean an entity outcome is known. |
| PollutedTerrain, Babies, Children, Deathrest, GenesAndXenotypes, Mechanitors, MechsInCaravans | Pollution/storage/production, society, genetics/mech policies and native caravan controls. Normal waste processing and travel consume their actual resources. |
| ReformCaravan, FormCaravan, InteractingWithTraders, BuildOrbitalTradeBeacon, OpeningComms, GettingMoreTraders, TradeGoodsMustBeNearBeacon, MaxNumberOfPlayerSettlements, TradingRequiresPermit | Existing caravan/trade/building/quest workflows, genuine engine gates and faction permissions; no invented trader inventory or settlement limit bypass. |
| Rescuing, Capturing, DrugAddiction, DrugPolicies, TVForSickPeople, PrisonerTab, MedicalOperations, ArrestingCreatesEnemies | Care/society/native medical recipes and actual diplomacy/ideology risks. Entertainment requires normal facilities; capture/recruitment are separate from rescue. |
| ShieldBelts, Drafting, GroupGotoHereDragging, AnimalsDontAttackDoors, DoorOpenSpeed, QueueOrders, EquippingWeapons, CoverAndShooting, HostilityResponse, FirePreparation, ShotAccuracyTooltip, FriendlyFireSafety | Equipment and combat data/jobs, real movement, preparation, line-of-fire and collateral risks. No assumption that doors stop every threat or that a displayed hit chance guarantees a hit. |
| BillsTab, DrugBurning, Shelves, Stockpiles, Forbidding, GrowingFood, SetGrowingZonePlant, Mining, WorkTab, StorageTab, HomeArea, SpoilageAndFreezers, Deterioration, SwitchFlickingDesignation | Loaded bills/recipes/material logistics, farm catalogs, roof-safe mining, work priorities, cleaning/fire area and utility control. Reversible settings still need workers to produce effects. |
| AnimalTaming, AnimalTraining, AllowedAreas, Outfits, TimeAssignments, ManualWorkPriorities, Books, ForbiddingDoors | Existing gear/training/area/work policies plus new care/society/native interactions; jobs respect actual accessibility and protected care. No instant reading/training or arbitrary skill grants. |
| MeditationSchedule, MeditationDesiredPsyfocus | Native timetable and desired focus, available personal focus and normal meditation work. |
| EditingMemes, EditingPrecepts | Actual ideology is observed and governs choices; existing ideology selection in Archonexus is executable. Authoring/reforming a new ideology is a separate player-facing editor, not an artificial precept mutation. |
| WorldCameraMovement, CameraDolly, CameraZoom, TimeControls, Pause, Alerts, InfoCard, TileInspector, HistoryTab, ClickingMessages, SteamDeckControlsMainMenu, SteamDeckControlsGame | UI/information controls; equivalent information, speed and native messages are accessed through API. Steam Deck button tutorials do not require colony actions. |

The unnamed record is the abstract NotedOpportunisticBase tutorial parent, not
a missing gameplay mechanic. See the machine-readable inventory for exact
installed paths. Loaded definitions remain the authority for costs, eligibility,
DLC availability and mod-added content.

## Source review

Primary technical evidence: installed XML and decompiled methods named in
[production](modules/production.md), [sustenance](modules/sustenance.md),
[society](modules/society.md), [resilience](modules/resilience.md),
[combat](modules/combat.md), [specialists](modules/specialists.md) and
[progression](modules/progression.md). Source-derived rules are version-bound,
not guesses copied from old guides.

The user's references were consulted as discovery/checklists:

- [The big list of RimWorld tips](https://www.reddit.com/r/RimWorld/comments/zq7gi8/the_big_list_of_rimworld_tips/):
  logistics, policy, food, childcare and defensive ideas were checked against installed rules.
- [Beyond the Basics](https://steamcommunity.com/sharedfiles/filedetails/?id=768426725):
  workload, health and defenses; old drug/mech claims are not used as 1.6 constants.
- [Tips and tricks part 1](https://www.reddit.com/r/RimWorld/comments/1piopj1/rimworld_tips_and_tricks_part_1/):
  diet differentiation, storage, mood and mountain heat risks. Deliberately overheating
  patients and engineered trader attacks are not adopted as default care or income plans.
- [TheGamer beginner tips](https://www.thegamer.com/rimworld-beginner-tips/):
  retrieval failed; its contents are **not claimed as read**. The audit used installed
  sources and the other accessible references.

Official ending cross-checks:
[Odyssey announcement](https://ludeon.com/blog/2025/06/announcing-odyssey-and-update-1-6/),
[Mechhive preview](https://ludeon.com/blog/2025/07/odyssey-preview-4-quests-the-mechhive-endgame-drones-and-more/),
[Ideology overview](https://rimworldgame.com/index.php/ideology).
Community suggestions are discovery evidence, not authority to override native rules.
