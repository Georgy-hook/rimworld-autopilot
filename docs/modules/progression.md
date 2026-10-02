# Progression audit

Inspected against installed RimWorld 1.6.4871 on 2026-10-02. Active scope: Core, Royalty, Ideology, Biotech, Anomaly. Odyssey is inactive. A strategy label describes an intention, never a completed chain or verified victory.

## Additions and hooks

`colony_progression.collect(client, snapshot)` reads research tree, current project and `/api/v1/colony/progression`. Store its result in `snapshot['development']['progression']`. `prepare`, `choose`, `execute`, `assess`, `DESCRIPTIONS`, `LABELS`, `ACTIONS`, `DOMAINS` implement the module router contract. `progression_research` becomes available only when a missing ship prerequisite is actionable, including hidden prerequisites. Laya compares that frontier against all feasible alternatives and keeping the current project. This repairs the existing doctrine token filter: a prerequisite such as Microelectronics can be essential although its name does not match ship/starflight tokens. This is an optional route comparison, not an automatic ship build order.

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
| Royalty Royal Ascent | Partial | Strategy catalogue and live royal room/title context exist | Title/honor eligibility, generated hospitality conditions, guest survival/mood, threats and shuttle departure are not a verified complete chain |
| Ideology Archonexus | Not executable | Catalogue acknowledges the route; installed cycle quest descriptions document colony/research transfer | Wealth gate alone is insufficient: cycle study, colonist/animal/item selection, reset/new settlement and final core activation need native handlers |
| Biotech | Partial | Research and ordinary production can support genes/mechs | No separate victory path promised; specialist gene, mechanitor, boss and waste chains remain outside this module |
| Anomaly monolith/void | Not executable | Catalogue names the route; ordinary research can only choose projects already feasible | Monolith stages, entity discovery/study, containment, final threat sequence and ending choice have no complete native handler here |
| Odyssey | Inactive | No claim of coverage | Must stay unavailable when the pack is inactive |

## Primary sources

Installed game root: `C:/Program Files (x86)/Steam/steamapps/common/RimWorld`.

- `Data/Core/Defs/ResearchProjectDefs/ResearchProjects_5_Ship.xml`: ShipBasics, ShipCryptosleep, ShipReactor, ShipEngine, ShipComputerCore, ShipSensorCluster and their prerequisite/cost definitions.
- `RimWorldWin64_Data/Managed/Assembly-CSharp.dll`, inspected with ILSpy: `RimWorld.ShipUtility.RequiredParts`, `ShipBuildingsAttachedTo`, `LaunchFailReasons`, `HasHibernatingParts`, `ShipStartupGizmos, Building_ShipComputerCore.GetGizmos/TryLaunch, ShipCountdown.CountingDown and CompHibernatable.Startup`. Startup is a separate player command with a warning/confirmation; Laya explicitly compares startup/launch with defer. Native startup invokes the same StartupHibernatingParts operation as the player confirmation; launch executes the enabled ordinary computer launch gizmo after rechecking LaunchFailReasons. No ForceLaunch shortcut is called.
- `Data/Royalty/Defs/QuestScriptDefs/Hospitality/Script_EndGame_RoyalAscent.xml`: native Royal Ascent quest, distinct from a doctrine label.
- `Data/Ideology/Defs/QuestScriptDefs/Script_EndGame_ArchonexusVictory.xml`: three cycle defs, colony wealth requirement, transfer of colony and recorded research, limited traveling people/animals, later cycle study requirement.
- Official publisher descriptions: [Royalty](https://store.steampowered.com/app/1149640/RimWorld__Royalty/), [Ideology](https://store.steampowered.com/app/1392840/RimWorld__Ideology/), [Anomaly](https://store.steampowered.com/app/2380740/RimWorld__Anomaly/). These establish route intent; installed definitions and engine conditions determine feasibility.

## Validation

Eighteen offline tests cover hidden prerequisite traversal, bench exclusion, no victory inferred from completed research, stale-project rejection ordinary non-forced research mutation confirmation, engine passenger/readiness option gating shared research cache reuse, changed-passenger rejection and countdown distinct from verified victory. C# compilation is performed by the parent integration task. No game, director, commit or push was run.


Ship execution refreshes native facts, rejects changed passengers/home population/defender counts, then revalidates native engine conditions at mutation. Startup facts include definition-provided days, mobile combat-capable colonists (not proof of health/armor), downed colonists, hostiles and total item nutrition (includes corpses, forbidden/inaccessible items, unsuitable feed and unhealthy food; not safe edible reserves). Launch reports countdown initiation; credits/victory remain unverified. No startup or launch is automatic.



## Phase 2: boarding and success semantics

`progression_boardship` asks Laya to choose a single passenger/casket, or a carrier for a downed passenger, or defer. Native `ProgressionBoardingHelper` reports only options with a complete connected ship, an empty player-ejectable attached casket, `Accepts(pawn)`, reservations and a path at `Danger.Some`. Quest lodgers, drafted/mental-state pawns and currently hostile maps are excluded. Mobile passengers wait until every hibernatable ship part is Running; downed passengers may be preserved before startup using a mobile carrier. Choices report passenger health fraction, medicine skill, worker current job, remaining mobile combat colonists/doctors, reactor state and psychic bond separation warning. These counts are not proof that remaining defenders are armed or medically healthy. Boarding never automatically iterates the whole colony.

The boarding endpoint refreshes native options and orders `JobDefOf.EnterCryptosleepCasket` (target A: casket) or `JobDefOf.CarryToCryptosleepCasket` (A: passenger, B: casket) via `TryTakeOrderedJob`. No direct `TryAcceptThing`, despawn, teleport or forced container insertion occurs in the helper. Success requires the accepted job to be the current job. It reports `boarding_job_started`, never boarding complete. The native drivers perform travel, reservations, carrying and a 500-tick wait; subsequent telemetry must show actual casket occupancy.

ILSpy inspection of the installed assembly confirms `Building_ShipComputerCore.GetGizmos` binds the normal launch command directly to `TryLaunch`; it checks `CanLaunchNow` and initiates `ShipCountdown`. This path has no confirmation dialog. Endpoint success checks the countdown after invoking the enabled command. The ordinary self-entry driver may open a last-colonist warning only for non-player-ejectable caskets; those are excluded by this helper. The installed `Ship_CryptosleepCasket` definition explicitly has `isPlayerEjectable=true`.

`collect` filters native milestones to `snapshot.map.id` when supplied. Execution bypasses the earlier-cycle research cache, retains that map filter, and compares boarding identity/readiness fields; unrelated director metadata does not affect the selected job or get sent to the API. Regression tests cover selected-map isolation, normal boarding endpoint/identity forwarding, unrelated metadata, hostility gating and honest failure semantics. C# compilation remains the root integration gate.


Final consequence packing: every ship, boarding and research subchoice now supplies distinct benefit/risk/cost/inaction/uncertainty fields, including defer. Native startup days and unboarded names are short decision facts; startup raid duration, unboarded count and remaining armed/doctor counts lead each risk field. Huge benefit prose cannot consume the risk allocation. Active TendPatient, Rescue, FeedPatient and DoBill workers cannot receive a boarding order. Additional tests check installed Core ship casket ejectability/reactor raid-beacon definitions, ordinary job source contract, and retained risk fields under a deterministic tokenizer budget.



Progression retry memory is bounded to three per-action progression:action cooldown records. Deliberate defer waits 15000 game ticks; confirmed research target waits 30000, confirmed ship command 15000, and accepted boarding job only 600 so the next passenger can follow. Failed/stale commands do not record progress or an applied cooldown. Prepare removes any future-tick record after save rollback even when that action currently has no candidates. Tests cover actual prepare suppression, expiry, rollback and differentiated boarding/research periods.
