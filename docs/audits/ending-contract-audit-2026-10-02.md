# Offline ending contract audit — 2026-10-02

Scope: `colony_progression.py`, native ending controllers and progression boarding/startup helpers. No game, director, observer or model was launched. This is source and contract evidence, not a played victory.

## Reproduced blockers and fixes

1. Ending execution required entire regenerated rows to equal the original choice. Native quest rows include `expires_in_ticks`, so ordinary elapsed time during deliberation rejected an otherwise eligible quest. Fresh execution now compares every native field except that countdown and accepts additional director metadata. The refreshed `can_accept`, accepter IDs, native route and consequences still must match. The server independently rechecks `QuestUtility.CanAcceptQuest` and `CanPawnAcceptQuest`.
2. Verified credits previously suppressed only `ending_options`; ship/research/boarding actions could remain selectable, including choices made before credits arrived. `prepare` now stops every progression action after verified evidence; `execute` independently checks fresh evidence before any mutation.
3. A revealed escape ship or Archonexus site did not have a concrete progression caravan start. New GET/POST `/api/v1/colony/endings/journey` exposes explicit native destination, traveler group and 5/15/30 food-budget alternatives plus a native ETA-derived budget when needed. Python collects and presents these as `kind=journey`, reports carried nutrition, medicine, mass/capacity and people left behind, then sends exact native pawn IDs on execution. Native code regenerates feasible plans, requires confirmation, checks reachable destination, home-map threats, healthy travelers, available supplies and mass, and invokes `CaravanFormingUtility.StartFormingCaravan`.
4. Pending native journey routes persist in `EndingJourneyState` until the caravan forms. A matching caravan receives the game's ordinary `CaravanArrivalAction_VisitEscapeShip` or `CaravanArrivalAction_VisitSite`; subsequent destination/arrival persistence belongs to the game. The arrival callback generates/enters the real ship/site map. It does not teleport pawns or synthesize a site.
5. The credits source observer could incorrectly relabel an already running ordinary ship countdown when a Royal Ascent signal reached `QuestPart_EndGame` and its native method returned early. The observer now records whether no countdown existed before the signal; only a newly started countdown updates Royal attribution. The attribution flag is serialized alongside credits evidence.
6. Ending sites previously dropped native disabled float-menu options entirely. `/colony/endings` now returns `site_blockers` with actual labels, map/pawn/thing IDs and native inspect text. This exposes monolith discovery/condition and site reachability blockers without turning them into executable actions.
7. `EndingEvidence` now persists a fresh GUID as `layaCampaignId`, exposed as `campaign_id` by `/colony/ending-evidence`. It survives map replacement and ordinary save/load; a legacy save missing the field obtains a GUID in `PostLoadInit`. Root integrates this identity with doctrine persistence.
8. An empty expedition list no longer hides preparations. Journey GET exposes per-destination/group readiness and blockers, actual diet-acceptable stocks, required nutrition, threats, workforce, home reserves and capacity. Native `MealSurvivalPack` recipes expose `PackagedSurvivalMeal` research, Cooking 8 and their actual stations; when ration stock is missing, Python walks this supporting research frontier for the explicitly chosen `ship_journey`/`archonexus` route. The compact `summary(snapshot)` and the first model fact carry chosen-route needs into adjacent decisions. Native full readiness remains available for inspection. Research supports ration production rather than silently choosing self-built ship research.
9. Native route ETA is now distinct from food supply duration. The actual native exit tile and `WorldPath` feed `CaravanArrivalTimeEstimator`, with actual traveler speeds from `CaravanTicksPerMoveUtility` at conservative full carrying capacity. The route/team estimate is shared across supply alternatives; readiness and choices expose nullable travel days, explicit unknown reason and food margin. A route-budget alternative rounds ETA plus two days, and feasible plans require at least one native estimated food day beyond ETA. The estimate includes native route/rest/season costs and excludes formation delays and future events. Execution tolerates at most 0.25 day of ordinary estimate drift; larger changed route cost requires a fresh decision.

## Concrete source evidence

Installed source authority: `C:/Program Files (x86)/Steam/steamapps/common/RimWorld/RimWorldWin64_Data/Managed/Assembly-CSharp.dll`, read with local ILSpy. Existing decompiled inspection files were checked against the handlers below; `EscapeShip`, `CaravanArrivalAction_VisitEscapeShip`, `CaravanArrivalAction_Enter`, `WorldReachability`, `MassUtility` and `TransferableOneWay` were additionally decompiled during this audit.

| Route | Native gate/action/evidence checked | Supported endpoint chain and remaining obligation |
|---|---|---|
| Self-built ship | Installed `ResearchProjects_5_Ship.xml` contains all six `SHIP_RESEARCH` names. `Buildings_Ship.xml` provides actual part dimensions and reactor startup. `ShipUtility.RequiredParts`, connected attachment traversal and `LaunchFailReasons` govern native controller acceptance. `ShipCountdown.CountdownEnded` calls `GameVictoryUtility.ShowCredits`. | Research target → director construction/procurement → `/colony/progression` connected ship snapshot → `/progression/ship` startup → `/progression/board` ordinary jobs → launch countdown → observed credits. Root owns construction/procurement integration and corrected ship geometry. No credits are inferred from research, blueprints, boarding orders or countdown. |
| Existing escape ship | Installed `Core/Defs/WorldObjectDefs/WorldObjects.xml` defines `EscapeShip` with `EscapeShipComp`; ILSpy shows it inherits `MapParent`, not `Site`. `CaravanArrivalAction_VisitEscapeShip` takes the actual component, generates the map if absent and enters it through the native caravan utility. | New `ship_journey` doctrine and journey options → forming caravan → saved native visit action → observed destination map → existing ordinary ship startup/boarding/launch chain. This doctrine does not require self-built ship research. |
| Royal Ascent | Installed `Royalty/Defs/QuestScriptDefs/Hospitality/Script_EndGame_RoyalAscent.xml` contains minimum title definition `Count`, whose installed `RoyalTitles/RoyalTitles_Empire.xml` label is `archon`, and hospitality/shuttle failure signals. ILSpy `QuestPart_EndGame` starts the string-overload countdown only on the matching signal and only if no countdown already runs. | Native quest eligibility/acceptance → hospitality, title/honor and shuttle work through the other modules → actual departure signal → native credits. Accepting the offer does not satisfy title, hospitality or departure. |
| Archonexus | Installed Ideology quest roots are `EndGame_ArchonexusVictory` and first/second/third-cycle variants. ILSpy `QuestNode_Root_ArchonexusVictory_Cycle` has required wealth 350000, five colonists/five animals and native sale selection. `Building_ArchonexusCore.GetMultiSelectFloatMenuOptions` orders `ActivateArchonexusCore` after reachability; it never invokes the developer gizmo. | Live quest gates → explicit survivor/item selection → native consequence confirmation → native settlement tile/ideology continuation → campaign doctrine preserved by root → repeat gates → journey to revealed Site → ordinary core job → `ArchonexusCountdown` → credits. Selection has no automatic survivor list. |
| Anomaly | ILSpy `Building_VoidMonolith.CanActivate` checks `EntityCodex.DiscoveredCount` against next-level category/count and prohibited active conditions. The native menu provides investigation/activation and disabled discovery/condition labels. `CompVoidNode` derives from `CompInteractable`; final decisions call `VoidAwakeningUtility.EmbraceTheVoid`/`DisruptTheLink`, both calling credits. | Discovery/study/containment work through other modules → ordinary monolith job → emergency/void-node interaction → explicit final dialog choice → credits. Discovery gates cannot be replaced by a research target. Catalog prose is a planning description; native gate text and acceptance remain authoritative. |
| Odyssey | ILSpy `CompCerebrexCore.DeactivateCore(bool)` covers both scavenging and destruction and calls credits with `exitToMainMenu=false`; stabilizers and defenses gate ordinary interaction. Existing pilot/destination/landing endpoints use native callbacks. | Construction/fuel/space preparation → native pilot job → explicit destination/landing choices → combat/stabilizers → final native choice → credits. Installed Odyssey Data definitions are absent, so full build/material/world-generation gates are not locally proven. Assembly type availability alone does not establish active DLC. |

## Tests and proof limits

`python -m unittest discover -s tests -p test_progression.py`: **30 passed** after these changes. New tests reproduce elapsed quest ticks, live loss of eligibility, director metadata, stop after verified credits including in-flight choices, exact journey endpoint/pawn-ID payload, rejection of changed traveler groups, and journey home map → observed destination map → ship launch contract. They explicitly assert formation and countdown do not verify victory. The native source contract test checks diet/rate, nonrottable supplies, destination disclosure and persisted native arrival APIs. An empty-supplies test verifies no expedition order while ration research and compact readiness remain visible.

These are offline contract tests with native-shaped API fixtures. They do not establish successful caravan formation, safe travel, job completion, generated-map scheduling, Harmony execution, saved-game migration or the actual quality of model decisions. Root builds the C# assembly and runs the broader offline suite. No native callback was invoked against a live game.

Journey food budgets use each selected pawn's actual native food consumption rate, including gene effects, through `NutritionBetweenHungryAndFed` and `TicksUntilHungryWhenFedIgnoringMalnutrition`. A native `DaysWorthOfFoodCalculator` estimate is exposed separately. Every packed item must satisfy `CaravanPawnsNeedsUtility.CanEatForNutritionEver` and every traveler's current food policy. Only nonrottable packaged survival meals are packed; pemmican is conservatively excluded because installed `Items_Food.xml` shows it rots after 70 days and remaining shelf life on a hot route is unknown. Food days are not native route ETA. Targets require a nonhidden, nondismissed ending quest look target or already generated escape ship map; unknown/hidden Site parts are excluded. Plans carry no animals and expose scout/migration groups without arbitrary pawn/item editing. A migration can contain one healthy traveler. Scout preserves at least two armed mobile defenders; migration explicitly shows whoever remains. Long routes, changing needs, biome, illness and events can defeat a feasible starting plan. Pending route callbacks remove a stale destination or reject native invalid arrival; victory is never inferred from that route state.

Completion across all endings remains a conditional executable architecture, not a guarantee that any seed, storyteller, starting pawn set or chosen model policy wins. Resource acquisition, hospitality, discovery, combat and rebuilding require the root's adjacent module audit; authoritative credits evidence is the terminal proof.


## Reviewed follow-up: continuation and freshness fixes

Parent approved four reproduced defects before edits. Implementation changes:

1. `EndingJourneyState` persists `FormingLord` with Scribe references, origin map,
   formation ID, and last lifecycle result. A Harmony prefix captures the exact
   native forming lord at `CaravanExitMapUtility.ExitMapAndCreateCaravan`;
   postfix receives the actual caravan. Only this matched callback sets the
   ending arrival action. Missing/cancelled lord, missing target, changed owned
   roster or downed companion invalidates intent, removing the blocking route.
   Old records without identity are invalidated without touching another lord.
   No elapsed-time cancellation and no unrelated caravan lookup/rerouting.
2. Journey freshness uses real roster IDs and supplies manifest. GET supplies
   `home_pawn_ids` and `manifest:[{def_name,count}]`; POST supplies sorted home
   IDs and `manifest=DefName:count,...`. Empty home IDs are valid migration.
   Native plans regenerate safety/stock thresholds. Ordinary reserve drift is
   accepted; changed roster, cost or substantial ETA/food-margin changes fail.
3. Empty continuation reports `native-continuation-wait` with blocked reason,
   quiet repeated results, no model calls, and resumes when native choices exist.
   Odyssey exposes required landing map and marker session; explicit
   `view_landing_map` sets that map after identity revalidation. Placement and
   landing also verify marker session. An empty coarse placement sample now
   searches at most 256 additional native cells per GET for viable recovery, otherwise records a blocker. There
   is no implicit strategic cancellation or fabricated landing success.
4. Boarding permits ordinary Goto/Wait job progress while rechecking identity,
   readiness and care protection. Site jobs similarly tolerate ordinary jobs;
   native `SpecialistNativeSafety.Protected` regenerates care/health eligibility.

Installed assembly evidence inspected with ILSpy, without game execution:
`RimWorld.LordJob_FormAndSendCaravan.SendCaravan` calls
`RimWorld.Planet.CaravanFormingUtility.FormAndCreateCaravan`, which immediately
calls the exact six-argument PlanetTile overload of
`CaravanExitMapUtility.ExitMapAndCreateCaravan`. `downedPawns` is public;
`StopFormingCaravan` removes its actual lord. Native gravship controller already
uses `Current.Game.CurrentMap = map`, the same API used for explicit recovery.

Offline regression evidence: `python -m unittest tests.test_progression` passes
35 tests. New tests exercise ordinary boarding job progress vs care, reserve
consumption vs changed manifest/roster/cost, empty continuation without model,
quiet wait and recovery, landing POST identity/session freshness. Source contract
assertions check persisted lord/callback and landing bounded incremental fallback. Source
assertions do not execute Harmony/native lifecycle and must not be described as
runtime proof. No build, game, live API, model weights, observer or git operation
was run for this follow-up. Parent compilation/review remains required; native
save/load, caravan creation and Odyssey landing are still runtime-unverified.


## Reviewed follow-up: affordances and targeting

Parent reviewed and approved semantic freshness, native targeting generation,
scanner identity/ingredients and remaining-charge evidence, followed by visible
comparison cards and retry repairs. See `docs/modules/affordances.md` for exact
DTOs and lifetime/retry contracts. Model cards now expose actual target costs,
minimum finite remaining charges, maximum actual-radius allied exposure and worst
clinical stages. Scanner state and affected person identities appear first.

Stable identity and state fingerprints are separate: successful 2500-tick dwell
survives its own charge use; defer binds actually offered current-stage options;
failed/stale/rejected/API-error options retry after 150 ticks and reopen on
meaningful state change. Expired/future/malformed/legacy timestamps are removed.
Paused targeting uses one JSON retry record, wall-clock 1/2/4/5-second delays and
immediate new-session/meaningful-context bypass. Fresh native context reads still
occur; repeated identical failures suppress model and POST calls. Empty target
catalogue permits cancellation; native cancellation has no retry restriction.

Offline progression+affordances suite passes 60 tests. New regressions cover
visible model evidence within the 312-token state budget, deferred-new-target
availability, accepted dwell after charge use, stale/rejected/GET/POST failures,
expiry/rollback/JSON and paused targeting retry. Installed ILSpy confirms five
public `Targeter.BeginTargeting` overloads and `StopTargeting`, native scanner
State/Occupant/GetRequiredCountOf and inherited public SelectedPawn. Harmony source
assertions and Python transport tests are not live native proof. No build/game/
live API/model weights/observer/git operation was used. Separate combat findings
were reported read-only and are awaiting parent review before edits.


## Event and growth follow-up

Approved event fixes preserve explicit observation/defer acknowledgments, but
rejected or unknown mutation results no longer enter handled-event history.
Native non-generic `success:true` quest acknowledgments remain accepted; explicit
`applied:false` takes precedence. Failed options use persisted wall-clock retry
5/10/20/30 seconds; history prunes malformed, expired and future timestamps.
The native caravan planning/lifecycle redesign remains a proposal awaiting review.
Growth cards count mental-state and bedbound pawns as unavailable; best skills
exclude unavailable workers and disabled skills. Bedbound remains a clinical
mobility count, with a separate unavailable_workers value.
Offline tests exercise rejection→bounded retry→acceptance→tick rollback and
existing unavailable-trade acknowledgment. No game, API server or Harmony runtime
was launched; native expedition execution remains unproven.


## Shared ordinary expedition contracts (approved follow-up)

The trade/raid/rescue helper previously used raw ration counts (10/12/14 per
person) and a nonpersisted route list matched by ANY original pawn. All three
starts now delegate to shared `ExpeditionPlanHelper`: read-only native preview,
explicit Laya confirm/defer, regenerated exact roster/cargo/policy and native
nutrition/diet/ETA/capacity checks. `ExpeditionRouteState` persists the exact Lord
and native creation callback dispatch; canceled/compromised intents never
restart or reroute overlapping unrelated caravans. Invalidating intent does not
cancel an ordinary vanilla formation. Native graph references are never sent to
JSON; bounded scalar projections expose still-active formation.

Focused gate: 13 offline tests across expedition contracts, event/growth
follow-up, baseline bridge stale-response regression and legacy rescue readiness.
This includes the real choice adapter with fake tokenizer at its 512-token
configuration; it is not a checkpoint inference or native runtime test.
Native source checks assert exact hook/roster/persistence/diet/cost contracts,
not live interception or saved-game roundtrip execution. See
[expedition module/helper documentation](../modules/expeditions.md) for precise
units, API changes, supported rations and remaining execution limitations.

Residual strategy/professions audit coverage: active expansion filters,
endgame-coherent axes, direction→research/native-plan integration, disabled skill
handling and profession ranking were read. Confirmed secondary security skill
`Medical` was corrected to installed native `Medicine`; fixture verifies Medicine
16 contributes 9.6 to its 0.3 weighted security score. Training potential is a
long-term assessment with deliberate minimum health/capacity factors; it does
not itself verify an executable current job. No additional confirmed strategy
DTO mismatch was found in this narrow read-only pass. This is not a claim of
complete scenario/runtime coverage for every strategic direction.
