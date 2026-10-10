# Progression audit

Inspected against installed RimWorld 1.6.4871 on 2026-10-02. Active scope: Core, Royalty, Ideology, Biotech, Anomaly. Odyssey is inactive. A strategy label describes an intention, never a completed chain or verified victory.

## Additions and hooks

`colony_progression.collect(client, snapshot)` reads research tree, current project and `/api/v1/colony/progression`. Store its result in `snapshot['development']['progression']`. `prepare`, `choose`, `execute`, `assess`, `DESCRIPTIONS`, `LABELS`, `ACTIONS`, `DOMAINS` implement the module router contract. `progression_research` exposes actual visible and hidden prerequisites for the chosen route: ship requirements or loaded infrastructure support targets. The chosen doctrine route is present in decision facts; `imperial_ascension` maps to `royal_ascent` and `mechhive` to `odyssey_mechhive`. Infrastructure support never substitutes for native title, wealth, study or discovery gates. Laya compares that frontier against all feasible alternatives and keeping the current project. This repairs the existing doctrine token filter: a prerequisite such as Microelectronics can be essential although its name does not match ship/starflight tokens. This is an optional route comparison, not an automatic ship build order.

Execution refreshes the tree/current project, rejects missing benches, completed or unavailable projects, sets the ordinary research target with `force=false`, and confirms the returned target. Research still consumes pawn labor. Remaining research points are work, not a promised date. No research choice verifies victory.

`ProgressionController` uses the installed engine's `ShipUtility` for each connected ship component. It reports actual attached parts, required counts, hibernation and localized launch blockers. Disconnected parts are separate ships. Required counts come from the engine, not from a hardcoded Python guess. Occupied caskets and reactor startup state remain engine launch conditions.

## Coverage matrix

| Route/mechanic | Status | Measured/executable coverage | Remaining blockers |
|---|---|---|---|
| Core research prerequisite chain | Covered | Visible + hidden prerequisite frontier; bench and analysis blockers; ordinary target mutation | Throughput and actual pawn work still depend on colony management |
| Core self-built escape ship | Partial | All six ship research milestones; engine attached-part counts and launch failure reasons | Site planning and connected construction, AI persona core procurement, still depend on existing ordinary construction/job systems. This module implements explicit ordinary self-entry and downed-passenger carry jobs, native startup and launch after live validation; reserve counts do not prove survival |
| Core journey to existing escape ship | Partial | Existing event/expedition tools can plan travel | No verified sequence from world destination through caravan arrival, reactor defense and launch |
| Economy and trade | Partial | Existing trader transactions, production and event choices | No guarantee of persona core acquisition or sustainable reserves; increasing wealth can raise threats |
| Quests and expeditions | Partial | Existing offer acceptance, rescue matching and caravan preparation | Generic acceptance does not prove rewards, site completion, return, or an ending; individual quest part conditions still need observation |
| Royalty Royal Ascent | Native route actions | Live ending quest requirements, eligible accepter selection, ordinary quest acceptance, actual credits observation; royal rooms/titles and native shuttle affordances remain separate systems | Must earn honor/title, host and protect guests and explicitly board departure shuttle; acceptance is never success |
| Ideology Archonexus | Native route actions | Live offered cycle gates; explicit take/leave people, animals, relics and items with native limits; native consequence confirmation; final core float-menu job; actual credits observation | Native cinematic continuation, validated settlement TilePicker and explicit existing/current ideology confirmation are implemented; rebuilding, study, wealth and travel remain actual colony work |
| Biotech | Partial | Research and ordinary production can support genes/mechs | No separate victory path promised; specialist gene, mechanitor, boss and waste chains remain outside this module |
| Anomaly monolith/void | Native route actions | Native investigate/activate monolith menus regenerated per pawn, void structure/node menus, explicit final native dialog choice, level/inspect context, real credits observer | Actual discovery/study, containment and surviving void awakening are required; neither study counts nor activation infer success |
| Odyssey mechhive | Compiled native workflow; inactive here | Ordinary pilot-console job, native launch ritual and passenger policies, fuel/range/jammer-validated multilayer destination picker, native footprint placement/landing, final Cerebrex interaction and true credits observer | Odyssey Data is absent on this machine; this workflow is source-inspected and compiled, not runtime verified |

## Primary sources

As of 2026-10-07, offered ending quests carry a complete `quest_offer` and use
the [common terms/reward/accepter review](quests.md). Acceptance posts through
the same fresh native contract as ordinary events. Stable offer versions allow
countdown drift; changed terms, roster or new clinical danger require review.
Ending-site jobs share target/effect pending memory with generic interactions,
so another worker or module cannot immediately restart the same unverified job.
Current food/care/ending facts survive nested option comparisons. None of these
guards establishes quest completion or credits.

The engine's `GameVictoryUtility.ShowCredits` sets `Screen_Credits.wonGame=true`. `EndingCreditsHook` records that actual call in a saveable `EndingEvidence` component. Ship startup/countdown, successful quest acceptance, survival and colony death do not set victory. `GameEnder.gameEnding` is a defeat/all-colonists-gone detector and is deliberately not used as victory evidence. `exits_to_main_menu` reports whether the native credits require leaving; Anomaly resolution credits can still complete the model's chosen campaign goal even though the game permits continuing.

`/api/v1/colony/endings` exposes all native ending quests with their `QuestUtility.CanAcceptQuest` result, valid accepter IDs, descriptions, states, part types and targets. `progression_ending` offers every eligible quest/site step alongside defer, with the complete alternatives catalogue in decision facts. It never generates quests, sends completion signals, adds research points or grants rewards. Executing a stale pawn job/selection/requirement rejects the decision.

`/api/v1/colony/endings/selection` uses the currently open `Dialog_ChooseThingsForNewColony`, its exact candidate lists and `AcceptanceReport`. Checkbox selection mirrors the GUI's `selected` and `selectedItemCount`; submit calls the exact native `ConfirmArchonexusSettlementConsequences`, which opens the standard consequence confirmation. It never calls the sale callback directly. Every survivor and item selection is explicit and fresh; paused selection changes have no tick cooldown.

External cross-checks, researched 2026-10-02: [official Royalty description](https://store.steampowered.com/app/1149640/RimWorld__Royalty/), [official Ideology description](https://store.steampowered.com/app/1392840/RimWorld__Ideology/), [official Anomaly description](https://store.steampowered.com/app/2380740/RimWorld__Anomaly/), and the [community endings inventory](https://rimworldwiki.com/wiki/Endings). Official descriptions identify the hospitality, colony-sale and monolith campaigns; exact gates/actions above were independently verified against the installed defs and ILSpy assembly, not inferred from those descriptions.

Installed game root: `C:/Program Files (x86)/Steam/steamapps/common/RimWorld`.

- `Data/Core/Defs/ResearchProjectDefs/ResearchProjects_5_Ship.xml`: ShipBasics, ShipCryptosleep, ShipReactor, ShipEngine, ShipComputerCore, ShipSensorCluster and their prerequisite/cost definitions.
- `RimWorldWin64_Data/Managed/Assembly-CSharp.dll`, inspected with ILSpy: `RimWorld.ShipUtility.RequiredParts`, `ShipBuildingsAttachedTo`, `LaunchFailReasons`, `HasHibernatingParts`, `ShipStartupGizmos, Building_ShipComputerCore.GetGizmos/TryLaunch, ShipCountdown.CountingDown and CompHibernatable.Startup`. Startup is a separate player command with a warning/confirmation; Laya explicitly compares startup/launch with defer. Native startup invokes the same StartupHibernatingParts operation as the player confirmation; launch executes the enabled ordinary computer launch gizmo after rechecking LaunchFailReasons. No ForceLaunch shortcut is called.
- `Data/Royalty/Defs/QuestScriptDefs/Hospitality/Script_EndGame_RoyalAscent.xml`: native Royal Ascent quest, distinct from a doctrine label.
- `Data/Ideology/Defs/QuestScriptDefs/Script_EndGame_ArchonexusVictory.xml`: three cycle defs, colony wealth requirement, transfer of colony and recorded research, limited traveling people/animals, later cycle study requirement.
- ILSpy `QuestUtility.CanAcceptQuest/CanPawnAcceptQuest`, `Quest.Accept`, `QuestPart_NewColony`, `Dialog_ChooseThingsForNewColony`, `Building_ArchonexusCore.GetMultiSelectFloatMenuOptions`, `Building_VoidMonolith.GetFloatMenuOptions`, `CompVoidStructure`, `CompVoidNode`, `VoidAwakeningUtility.EmbraceVoid/DisruptLink`, `GameVictoryUtility.ShowCredits`, `QuestPart_EndGame`, `ShipCountdown`, `ArchonexusCountdown`: native eligibility, action callbacks, selections, final choices and true success evidence.
- Official publisher descriptions: [Royalty](https://store.steampowered.com/app/1149640/RimWorld__Royalty/), [Ideology](https://store.steampowered.com/app/1392840/RimWorld__Ideology/), [Anomaly](https://store.steampowered.com/app/2380740/RimWorld__Anomaly/). These establish route intent; installed definitions and engine conditions determine feasibility.

## Validation

Twenty-two offline tests cover hidden prerequisite traversal, bench exclusion, no victory inferred from completed research, stale-project rejection ordinary non-forced research mutation confirmation, engine passenger/readiness option gating shared research cache reuse, changed-passenger rejection and countdown distinct from verified victory. C# compilation is performed by the parent integration task. No game, director, commit or push was run.


Ship execution refreshes native facts, rejects changed passengers/home population/defender counts, then revalidates native engine conditions at mutation. Startup facts include definition-provided days, mobile combat-capable colonists (not proof of health/armor), downed colonists, hostiles and total item nutrition (includes corpses, forbidden/inaccessible items, unsuitable feed and unhealthy food; not safe edible reserves). Launch reports countdown initiation; only the separately observed native credits call verifies victory. No startup or launch is automatic.



## Phase 2: boarding and success semantics

`progression_boardship` asks Laya to choose a single passenger/casket, or a carrier for a downed passenger, or defer. Native `ProgressionBoardingHelper` reports only options with a complete connected ship, an empty player-ejectable attached casket, `Accepts(pawn)`, reservations and a path at `Danger.Some`. Quest lodgers, drafted/mental-state pawns and currently hostile maps are excluded. Mobile passengers wait until every hibernatable ship part is Running; downed passengers may be preserved before startup using a mobile carrier. Choices report passenger health fraction, medicine skill, worker current job, remaining mobile combat colonists/doctors, reactor state and psychic bond separation warning. These counts are not proof that remaining defenders are armed or medically healthy. Boarding never automatically iterates the whole colony.

The boarding endpoint refreshes native options and orders `JobDefOf.EnterCryptosleepCasket` (target A: casket) or `JobDefOf.CarryToCryptosleepCasket` (A: passenger, B: casket) via `TryTakeOrderedJob`. No direct `TryAcceptThing`, despawn, teleport or forced container insertion occurs in the helper. Success requires the accepted job to be the current job. It reports `boarding_job_started`, never boarding complete. The native drivers perform travel, reservations, carrying and a 500-tick wait; subsequent telemetry must show actual casket occupancy.

ILSpy inspection of the installed assembly confirms `Building_ShipComputerCore.GetGizmos` binds the normal launch command directly to `TryLaunch`; it checks `CanLaunchNow` and initiates `ShipCountdown`. This path has no confirmation dialog. Endpoint success checks the countdown after invoking the enabled command. The ordinary self-entry driver may open a last-colonist warning only for non-player-ejectable caskets; those are excluded by this helper. The installed `Ship_CryptosleepCasket` definition explicitly has `isPlayerEjectable=true`.

`collect` filters native milestones to `snapshot.map.id` when supplied. Execution bypasses the earlier-cycle research cache, retains that map filter, and compares boarding identity/readiness fields; unrelated director metadata does not affect the selected job or get sent to the API. Regression tests cover selected-map isolation, normal boarding endpoint/identity forwarding, unrelated metadata, hostility gating and honest failure semantics. C# compilation remains the root integration gate.


Final consequence packing: every ship, boarding and research subchoice now supplies distinct benefit/risk/cost/inaction/uncertainty fields, including defer. Native startup days and unboarded names are short decision facts; startup raid duration, unboarded count and remaining armed/doctor counts lead each risk field. Huge benefit prose cannot consume the risk allocation. Active TendPatient, Rescue, FeedPatient and DoBill workers cannot receive a boarding order. Additional tests check installed Core ship casket ejectability/reactor raid-beacon definitions, ordinary job source contract, and retained risk fields under a deterministic tokenizer budget.



Progression retry memory is bounded to three per-action progression:action cooldown records. Deliberate defer waits 15000 game ticks; confirmed research target waits 30000, confirmed ship command 15000, and accepted boarding job only 600 so the next passenger can follow. Failed/stale commands do not record progress or an applied cooldown. Prepare removes any future-tick record after save rollback even when that action currently has no candidates. Tests cover actual prepare suppression, expiry, rollback and differentiated boarding/research periods.

## Complete ending workflow inventory

Five ending families contain six campaign alternatives: self-built ship escape, journey to the offered existing ship, Royal Ascent, Archonexus, Anomaly void resolution and Odyssey mechhive resolution. Biotech adds capabilities and costs but no independent credits ending. Existing-ship arrival and all infrastructure construction use ordinary caravan/build/production systems; no sequence is claimed successful before observed native credits.

Archonexus continuation proceeds through explicit transfer selections and irreversible native confirmation, the cinematic, a fresh valid settlement tile, then keeping or selecting an existing ideology and the native restart callback. It does not stop after selling the colony. `/endings/continuation` owns those stages; new ideology authoring is outside this endpoint. Each subsequent cycle still needs its actual offered quest and live study/wealth/faction requirements.

`/endings/odyssey` exposes current engine fuel, missing facilities, orbital warnings and who is outside the gravship. Piloting opens the actual launch ritual; specialist ritual configuration explicitly selects visitor, animal and mech boarding policy. The native ritual starts the destination picker. Destination options use real planet layers and current fuel/range/path/jammer rules. Placement uses `Designator_MoveGravship.CanDesignateCell`; confirmation calls the actual marker landing action. Final core jobs use ordinary pawn menus and native final choices; fuel use, takeoff, landing or defeating unrelated mech bosses never count as the ending.

`/endings/world-targeting` supports an already open native WorldTargeter, including world abilities, with session identity, native validator, actual callback and explicit cancel. `/endings/pending` is a cheap continuation probe for the root paused-session dispatcher. Configuration stages have no tick cooldown and offer valid continuation or cancel rather than indefinite defer.

Credits source attribution is scoped around the native ship countdown, Archonexus countdown, void resolution and Cerebrex core methods, with exception-safe cleanup. `ending_route`, `ending_tick`, `ending_text`, `victory_verified` and `exits_to_main_menu` are evidence fields. Royal countdown is identified from the real ending quest signal. Route intention and native success evidence are separate; a chosen Anomaly/Odyssey resolution can end automation even when the game permits continuing.

Additional inspected assembly classes: `Screen_ArchonexusSettlementCinematics`, `MoveColonyUtility`, `TilePicker`, `Dialog_ConfigureIdeo`, `CompPilotConsole`, `Dialog_BeginGravshipLaunch`, `Building_GravEngine`, `GravshipUtility`, `WorldComponent_GravshipController`, `Designator_MoveGravship`, `CompCerebrexCore` and `WorldTargeter`. Python progression/specialist regressions pass together (38 tests). All ending controllers have passed the parent shared build; no game/Laya runtime launch or actual campaign victory was attempted.
Settlement alternatives use native neighbor BFS bounded to 2048 inspected tiles until twelve valid nearby choices, plus twenty-four geographically spread candidates. GET no longer validates or sorts the entire world. Explicit POST tile IDs still pass current settlement and TilePicker validators.


### Formation identity and blocked landing continuation (2026-10-02)

Journey GET now binds each feasible plan to `home_pawn_ids` and a `manifest`
(list of `def_name`, `count`). POST sends those identities as sorted comma-separated
IDs and `DefName:count` pairs. Empty home IDs represent migration. Fresh native
plan eligibility still checks supply reserves, care, carrying capacity and route.
Informational reserve consumption and ordinary jobs no longer invalidate an
otherwise identical decision. Roster, manifest, medicine and meaningful travel
estimate changes require a new decision.

Pending journey intent persists the actual native forming lord, origin map and
formation ID. Only the native caravan-creation callback for that lord may start
its ending route. Cancelled formation, missing destination, changed roster or
legacy records without a lord are invalidated explicitly; no timeout is used.
GET exposes `pending_routes` and `last_journey_result` (`status`, `reason`).
`travel_requested` means path requested, never observed arrival or victory.

Odyssey GET exposes `landing_map_id`, `landing_session`, `landing_blocker`.
A wrong visible map offers explicit `view_landing_map`; POST revalidates map and
session, selects the native landing map and returns
`gravship_landing_map_selected`. Placement and landing also require that session.
A coarse grid without valid cells falls back to at most 256 native cell checks
per GET. Search progress is scoped to marker/map/rotation; returned cells are
revalidated. Exhausted searches restart within 30 seconds. If none exist, sessions record blocked native
continuation and wait for fresh readiness without model calls or cancellation.
The repeated unchanged blocked result is quiet; an available option resumes normal
choice. This is an offline source/contract change; native runtime remains unproven.


Ordinary trade/raid/rescue trips now use the shared
[expedition preview and formation contract](expeditions.md), independently of
campaign ending state. They share the exact native creation callback dispatch;
ordinary invalidated intents do not cancel vanilla formation.
