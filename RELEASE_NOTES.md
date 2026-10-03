# 0.0.7 — Unreleased candidate

This section describes source changes in `fix/0.0.7-cold-start`. It is not a
published installer or a claim of demonstrated autonomous victory. See the
[current documentation index](docs/README.md) and
[API/loop audit](docs/audits/api-loop-audit-2026-10-02.md) for reviewed coverage.

- Added registered production, sustenance, resilience, society, progression,
  specialist and affordance domains. Laya receives bounded benefit, risk, cost,
  inaction and uncertainty for choices; subsequent observations remain distinct
  from command acceptance.
- Expanded live crop/season, blight, augmentation, equipment, trained-animal,
  medical, kitchen, storage and DLC context with ordinary game executors.
- Added campaign identity and cross-map goal persistence, staged connected ship
  construction, travel supply/manifest checks, royal hospitality prerequisites
  and explicit Core/DLC ending continuations. Odyssey runtime validation remains
  pending where its Data is unavailable.
- Corrected repeated or suppressed care/utility decisions, stale API selection
  handling, canceled caravan intent, empty native continuations and target/session
  freshness. Per-module audit reports distinguish Python fixtures, native source
  checks and actual gameplay evidence.
- Isolated domain preparation failures and extended retry backoff to world/modal
  reads. Updated source/installer version metadata and the documentation map.
- Added exact-plan expedition previews with native nutrition, both travel legs,
  carrying capacity and home reserves. Failed previews become dated planning
  evidence; formation acceptance is separate from travel or rescue completion.
- Reconcile partial rooms and hospitals against their saved layouts before
  repairing missing elements. Failed choices retain a real-time retry floor at
  3× game speed without hiding other patients, buildings or projects.
- Corrected the observed startup equipment loop by sharing candidate, parameter
  and execution plans. Added repeated-cycle fixtures, native active-job context,
  exact-target retry histories and nonmodal scheduler fallthrough. See the
  [2026-10-03 incident and verification](docs/audits/startup-loop-replay-2026-10-03.md);
  the subsequent colony outcome is recorded in the playtest journal.
- Following Requader's founder losses, added a verified temporary-bed, rescue and
  feeding chain, controllable caregiver checks, blood-loss urgency context and
  malnutrition emergency pacing. Optional weapon/drug deferrals now survive
  unrelated state drift; observed starter construction enables an eligible builder.
- Injured shooters retain verified stationary shots, traveling medical jobs are
  distinguished from bedside care, and retreat can seek a covering ally through
  a checked path. Native death events preserve the exact culprit where supplied.
  These repairs have offline verification; no new colony was launched. See the
  [Requader postmortem](docs/audits/requader-postmortem-2026-10-03.md).

# 0.0.6 — construction coverage, fire response and colony survival

The 0.0.6 release includes the construction and fire changes originally developed on the 0.0.7 feature branch. Live results and remaining limitations are recorded in `docs/RELEASE_READINESS_0.0.6.md` and `docs/CONSTRUCTION_FIRE_AUDIT_0.0.6.md`.

- The construction catalog now exposes all 533 player construction definitions seen in the tested RimWorld 1.6 game, including 301 constructed terrains. Laya can select unlocked definitions by category and exact ID; the bridge checks research, compatible materials and actual placement rules. A controlled audit received normal site responses for all 533 definitions.
- Butcher spots, butcher tables and simple research benches are available through the same catalog. In a 3× run Laya placed a SimpleResearchBench, and the colony completed it. Laya chose a research project, but research points did not advance in that observation; effective research staffing remains to be verified.
- Construction orders that cannot proceed because of reachability, materials or skill return an actionable non-applied result instead of an API error. The director also skips an already finished floor.
- A fire threatening buildings in the Home area remains an urgent choice after the incident event has passed. Laya can raise each eligible colonist's Firefighter priority to 1. In a replay beginning with 54 fires, colonists performed firefighting work and the blaze reached zero; substantial property loss remains possible. Post-combat context was shortened to avoid model input overflow during that scenario.

- Laya now identifies a pile of animal carcasses without a processing station, can choose a free Butcher spot beside the actual pile, and adds an active forever butchering bill in the same action. A controlled 3× replay showed Laya choosing it and two carcasses turning into 78 raw meat.
- A fresh-colony replay exposed a colonist sealed behind completed walls while food was nearby. Laya can choose to open the blocked path; the affected colonist then reached food and recovered.
- The director resolves stonecutting recipes from the completed workbench instead of assuming a nonexistent recipe ID.
- A vanished combat job target no longer puts the entire decision cycle into error backoff. Token-budget probes are bounded before calling the tokenizer.
- Earlier 0.0.6 work also expands live food and fuel planning, construction-capacity checks, medical context and the available colony choices. The release-readiness document separates tested outcomes from open regressions.

# 0.0.5 — Better shelter, live trade and responsive defense

- Added indoor-bed reassignment: when completed roofed beds are available, Laya can move colonists out of outdoor beds and sleeping spots. New real beds are planned inside finished rooms rather than scattered outside.
- Expanded recruitment preparation with a small prison plan, live rescue choices for downed neutral arrivals, and more explicit context for join opportunities, food and housing costs.
- Improved trader previews and compact trade context so Laya can compare actual affordable goods, prices and colony needs before buying or selling. The bridge re-checks live trade availability before committing an order.
- Tightened construction siting against existing rooms, blueprints and door access, and made early work priorities and survival trade-offs more visible to the model.
- Fixed ranged tactics that could leave shooters idle behind walls: the mod checks real line of sight, finds trap-free firing cells or advances in short steps, and regroups an isolated unarmed guard. Existing `AttackStatic` orders no longer count as active fire when a wall blocks the target.
- Improved desktop history loading and active-map state after a save reload. The English playtest log now records seven colony runs and a focused combat replay.
- Verification: 255 Python tests, a zero-warning RIMAPI 1.6 build, and a live two-squirrel manhunter replay. In that replay both shooters ultimately attacked and the wounded colonist was tended. It did not exactly reproduce the original two-gun wall obstruction; long-term colony growth remains unproven.

# 0.0.4 — Laya-directed choices, squad combat and the first promo

- Updated the local Laya SDK pin to 0.3.7. Decision input is checked against the actual tokenizer; large option sets use bounded comparisons so late options remain reachable, and one-option questions are resolved without calling the model.
- Kept Laya responsible for strategic trade-offs while the bridge validates live IDs, costs and normal-game commands. Current needs, risks and recent outcomes reach the model in compact context; decisions and relative option weights are recorded for inspection. The root checkpoint is **not** trained for reliable RimWorld play, and displayed weights are not success probabilities.
- Expanded combat to 36 situational tactics, including mixed melee/ranged groups, per-fighter melee roles, bounded kiting, short trap-free advances into firing range and regrouping. The model sees the opposing force and the risks of retreating or leaving fighters exposed; group orders and post-combat care have additional deterministic coverage.
- Extended procedural construction choices with verified wall materials, entrance direction, room character, resource and component costs, and seeded variations. The selected design is retained for execution instead of silently substituting a different plan.
- Added local decision feedback in the GUI for future training data; submitting a correction does not retrain the current checkpoint. Clarified the English in-game HUD and kept unequal yellow bars tied to actual model output.
- Added a 56-second promotional montage, four GIF previews in the README, the five original footage clips as optional release assets, and an honest architecture/evaluation document.
- 153 Python tests passed; the GUI asset validator passed, the updated C# RIMAPI build finished with zero warnings/errors, and fresh PyInstaller/Inno Setup packages were produced. This is not an exhaustive live-game combat benchmark. Autonomy is still experimental: use a copied save, and do not assume these improvements guarantee survival or victory.

# 0.0.3 — First-run model download and raid-response fixes

- The configuration assistant now downloads the required public root Laya checkpoint during setup. A missing cache is also recovered on launch; an unavailable network or incomplete download produces an explicit error. Model weights remain outside the installer and run locally after download.
- A dedicated `download-model` command fetches only the five required root files without loading the model into GPU memory or needing RimWorld.
- Raid staging and distant assaults no longer block ordinary colony work or keep defenders drafted all day. Laya can choose to equip capable colonists from available weapons before the enemy closes.
- Ranged focus fire is offered only when a shooter can reach the enemy. The roster and issued order exclude out-of-range shooters; unarmed colonists can choose a trap-free retreat instead of standing idle or charging into melee.
- Combat telemetry excludes passive distant hive occupants and exposes raid intent; short preemptive advances are reassessed when the enemy starts attacking. Wounded or reserved fighters are undrafted.
- 104 deterministic Python tests, GUI smoke checks and a C# build with no warnings/errors. Disposable live raids verified weapon pickup, staging, fighting and stand-down; this experimental autopilot does not guarantee colony survival.

# 0.0.2 — RimWorld Autopilot, hierarchical decisions and colony logistics

Development release focused on correcting the decision architecture and the survival failures observed in live colonies.

Highlights:

- renamed the product and repository to **RimWorld Autopilot**, while retaining Laya as the local decision model;
- redesigned dark fancy-cartoon GUI with semantic color tokens, rounded cards, animated buttons/orbit particles, a panoramic colony scene, original ImageGen emblem, setup illustrations and five coordinated navigation illustrations;
- protected 1240×800 minimum layout plus scrollable priority/settings pages, modern rounded history scrollbar and keyboard-visible button focus;
- local real-country flag artwork for Russian/English selection, with packaged-asset diagnostics instead of silent placeholders;
- complete Russian/English interface with friendly default explanations and a switchable raw technical view;
- persistent player guidance: eight priority weights, a personal note, peaceful preferences and an enforceable no-unprovoked-raids boundary;
- compact normal logs plus opt-in diagnostic snapshots in technical logging mode;
- heartbeat-based process health, so the GUI distinguishes loading, waiting, decision errors and a hung director instead of trusting PID existence alone;
- a closed or still-starting RimWorld/RIMAPI connection is reported as waiting for the game, not as a Laya decision-cycle failure;
- optional compact in-game HUD with thin, true-scale yellow probability bars, heavier labels above the fills, and an immediate hide switch in Settings;
- assisted animal feeding is offered only to downed or resting patients; a stale impossible feed order is skipped instead of trapping the director in an error loop;
- every rejected colony or event action enters a persisted 30-300 second bounded backoff and is removed from Laya's choices during that period so another valid response can be selected; unexpected combat and system cycle errors use the same bounded retry policy instead of hammering RIMAPI every two seconds;
- active combat orders are no longer replaced merely because pawns are walking or enemies crossed a five-cell boundary; Laya re-plans only for staging/attack transitions, target changes, drafting changes, casualties or material health loss;
- patient feeding now leaves enough time for the feeder to reserve food, walk and complete ingestion instead of reissuing the same order every few seconds;
- verbose mod descriptions and definition catalogs are summarized into a bounded model context, preserving hunger, patients, threats, skills and doctrine without exceeding Laya's tokenizer limit;
- doctrine application no longer fails when an income-strategy variable shadows the strategy module;
- Windows heartbeat publication tolerates transient GUI/antivirus file locks and can no longer terminate the director merely because the status file was being read;
- loading an older save discards future-timeline order markers, and zero-food/critical-hunger colonies immediately offer reachable wild-food harvests, safe hunts and the matching work priorities instead of idling behind stale issued-work flags;
- once food becomes available, a downed starving colonist receives a normal patient-feeding job while mobile colonists remain free to eat by themselves;
- a central decision guard that resolves a sole feasible action without calling Laya, guaranteeing that the model only receives choices with at least two real alternatives;
- standard dark/light Windows installer with custom portrait art, Program Files destination, optional desktop shortcut, temporary configuration assistant, registered Installed-apps entry and normal uninstaller;
- audited doctrine v2 with 30 strategic archetypes covering Core, Royalty, Ideology, Biotech, Anomaly and Odyssey;
- active-package filtering so unavailable DLC mechanics cannot be selected, while future/mod definitions remain discoverable through live catalogues;
- conditional doctrine cascade: domain → direction → compatible axes → selected economy product → mineral only for mining;
- doctrine-driven live research, architecture, fortification filtering and ending selection;
- expanded GUI doctrine panel with active DLC coverage, every currently valid direction, and probability history for every cascade stage;
- hierarchical Laya/Jev flow: domain → action family → action → only the selected action's parameters;
- exact construction-project and builder selection through normal RimWorld work givers;
- real beds after emergency sleeping spots, with skill and resource gates;
- distant human-corpse dumps, animal-carcass storage by butchering, graves, cremation, and Laya-selected corpse haulers;
- stone-chunk storage next to stonecutting;
- outdoor roads limited to stone flagstone; early paths are one cell wide;
- freezers are not placed without enough steel/components and either existing power or the resources for a generator;
- full pawn context for traits, visible injuries, missing body parts, pain, consciousness, movement, manipulation and sight;
- Laya-selected combat roster using that pawn context;
- optional prisoner-organ economy with explicit nonlethal/lethal plans and normal surgery bills;
- Ideology context plus a ritual-room plan using the colony's actual altar or ideogram;
- live profession catalog and profession-fit doctrine based on every colonist's skills, work restrictions and passions;
- passion-aware development plans: no flame 35%, small flame 100%, large flame 150%, plus Fast/Slow Learner and Too Smart context;
- Night Owl schedules with daytime sleep and flexible nighttime work/recreation;
- procedural architecture module with 17 functional programs and 24 distinct residential layouts, selected through program → style → variant nesting;
- room glow telemetry and Laya-selected lighting for dark work, medical and living spaces;
- hospitals that advance to hospital beds, vitals monitor and clean flooring when unlocked;
- throne-room planning driven by actual Royalty titles and unmet room requirements;
- additive workbench upgrade chains that retain the old bench until its researched replacement is constructed;
- a live building-definition catalog so DLC/mod construction is discoverable without hard-coding every Def;
- stockpile priorities now preserve RimWorld's complete 0–5 range, so Critical food/corpse zones work as intended;
- 82 deterministic Python tests, two GUI smoke tests and a zero-warning C# build.

The branch remains experimental. Use copied saves and review the GUI/overlay decision history.

# 0.0.1 — experimental public preview

First open-source release of an autonomous RimWorld colony director driven by the local Laya decision model.

Highlights:

- local inference; no remote gameplay service;
- normal RimWorld jobs and designations, with no spawning or instant construction;
- food, farming, storage, rooms, animals, health, research, industry, trade, caravans and long-term starflight planning;
- contextual combat handling for staging raids, insects and mechanoids;
- a separate combat-planning module with 28 tactics tied to live cover, doors, traps, turrets, mortars and fallback defenses;
- strict friendly-trap path inspection for every tactical reposition order;
- complete live psycast context and nested caster/ability choice with focus, cooldown, target and neural-heat validation;
- dynamic incident catalogue and an extensible event director covering combat, disease, fire, climate, crops, power loss, arrivals, resources, wildlife, psychic effects, quests, Anomaly events and unknown mod events;
- kidnapped-pawn tracking, rescue-quest acceptance and reserve-aware caravans to actual quest sites;
- autonomous visiting/orbital trader selection and normal reserve-aware transactions using current stock and departure time;
- Ancient Danger is treated as a sealed strategic site, not a raid, and verified threat auto-pauses are resumed after a decision;
- persistent doctrine covering settlement form, materials, economy, diplomacy, military emphasis and beauty;
- in-game decision overlay and Windows control center with exportable history;
- 50 automated Python tests and a reproducible modified RIMAPI source tree.

This is an experiment, not a promise of competent play. Back up your saves.
