# DLC specialist systems and hazards

Coverage was checked against installed RimWorld **1.6.4871** (`Version.txt`: rev590), with Core, Royalty, Ideology, Biotech and Anomaly data present. Odyssey data is absent: its native assembly workflows compile but cannot be runtime verified here. Installed XML and decompiled Assembly-CSharp provide technical rules. Official Ludeon articles give supplementary design context; exact actions use current native eligibility checks.

## Executable additions

`colony_specialists.py` owns `specialists_mech_mode` and `specialists_suppress_entity`; domains are `work_orders` and `care`. `SpecialistController.cs`, `SpecialistAutomationHelper.cs`, `SpecialistDtos.cs` implement `/api/v1/specialists/context` and `/api/v1/specialists/order`. Director hooks: store `collect` return in `development.specialists`, call `prepare`, register action metadata, and delegate native choice/execution/assessment. Add this Python file to installer payload and the module registry. The new C# controller follows existing controller discovery and response conventions.

The expanded action inventory additionally owns `specialists_ritual`, `specialists_genetics`, `specialists_mech_boss`, `specialists_permit`, and `specialists_policy`. Separate native controllers expose `/specialists/rituals`, `/specialists/genetics`, `/specialists/mech-bosses`, and `/specialists/permits`. Each choice first selects a target, then compares concrete options with benefit/risk/cost/inaction/uncertainty fields. The facts retain only that stage's native quality, blockers, gene biostats and consequences; large colony-wide inventories are not sent wholesale to the decision head. Execution recollects exact command identity and relevant readiness. Benign observation drift does not invalidate configuration commands; changed costs or irreversible Begin participants, packs, blockers and quality require a new decision.

`pending_action(context)` and `PENDING_WINDOWS` allow the root session router to service native force-paused ritual, xenogerm and gravship-launch dialogs. Configuration offers explicit native cancel; it has no tick cooldown and no indefinite defer. After starting a ritual or boss summon, normal jobs/time/combat still have to occur.

### Native rituals and role changes

`SpecialistRitualController` opens ordinary `Command_Ritual` or `CompPsychicRitualSpot` commands. The exact native `Dialog_BeginRitual`/`Dialog_BeginPsychicRitual` assignments supply participant candidates and role eligibility. Laya explicitly assigns/removes participants and spectators, selects an eligible ideology role in an actual role-change ritual, and compares native `BlockingIssues`, `CanBegin`, `PopulateQualityFactors` and duration before invoking the normal Start handler. Role assignment is obtained by the real ceremony; `Precept_Role.Assign` is never called as an instant shortcut. The role card exposes disabled work and apparel requirements. Protected doctors/caregivers/operating workers and dangerously sick pawns cannot be diverted into a ritual. Native low-quality/destructive confirmations remain pending for an explicit decision.

The same dialog workflow supports `Dialog_BeginGravshipLaunch`: navigator/participants and visitor, colony animal and colony mech boarding policies are explicit choices. The flight still requires a native console job, launch ceremony, destination, fuel and landing confirmation, as documented in progression.

### Native gene design and assembly

`SpecialistGeneticsController` opens an enabled ordinary gene assembler Recombine command. It presents whole available genepacks and every included gene's description, complexity, metabolism, archites and prerequisite. Selection mirrors the native checkbox plus `OnGenesChanged`, retaining native overrides/random conflict behavior. The actual current complexity/metabolism/archite totals, facility maximum, missing genes/research/capsules and name requirement are visible. Laya can explicitly select the game's generated-name button and invoke the native `CanAccept`/`Accept` flow. Replacement retains the game's confirmation. The normal assembler still needs power, capsules and colonist work; no xenogerm is finished or implanted by the API. Gene extraction, implantation and body care use separate ordinary map menus/medical operations.

### Mech boss progression and royal aid

`SpecialistMechBossController` regenerates `Command_CallBossgroup.IsDisabled` and its native menu for each healthy mechanitor. Selection invokes the exact native summon-job action, retaining boss availability, pending-wave and cooldown checks. Choices expose current hostiles, defenders and mechanitor job. Summoning deliberately attracts a threat; combat, looting the chip, analysis/research and fabrication remain actual work. No chip, boss kill or victory is granted.

`SpecialistPermitController` enumerates owned faction permits and the actual enabled `RoyalTitlePermitWorker.GetRoyalAidOptions`, with faction, favor, cooldown and native payment wording. It invokes that freshly generated option and preserves the normal local targeter or subsequent confirmation. The root affordance targeting workflow chooses the explicit legal target. Spending honor can delay noble titles and Royal Ascent; the model compares that cost instead of treating aid as free.

Laya chooses a target and then a concrete mode or worker, with **defer at both stages**. Selected target facts are put in detailed choice context so short decision-head prompts do not hide energy, waste, containment strength, activity or skill facts. Python recollects and compares an allowlisted exact payload; unrelated director details are ignored. C# repeats target/map/ownership/DLC/capability checks. Applied orders and deliberate deferrals use target/family history outside pending dialogs. Paused configuration uses session and transition history; short failed-option retries never claim progress. See the cycle contract below.

### Biotech mech control group policy

Live group members, exact mech energy, current mode, recharge thresholds and current jobs are exposed. Normal `MechanitorControlGroup.SetWorkMode` allows Work, Recharge or SelfShutdown. It neither fills energy nor creates mechs/bandwidth/chips. Work delegates type-supported labor to native autonomous jobs. Recharge delegates charger search and charging to native jobs. SelfShutdown gives very slow self-charge and sacrifices labor/defense. Escort/combat targeting, mixed-group splitting and mod-added work modes are not implemented here.

All members are affected. Candidate groups require a living safe controlled mechanitor, all members on the same map and owned by the player, and no downed/drafted/mental/active medical jobs/dangerous illness. **An actively charging member excludes a mode change**, avoiding native `SetWorkModeForPawn` interruption of a MechCharge job. No tactical redeployment is promised. Powered chargers are observed but compatibility, reservations, free charger slot, future power and waste capacity are not certified. Existing Work mode already charges according to its configured thresholds; Recharge is an explicit alternative, not a forced low-energy strategy.

### Anomaly entity suppression

For player-owned occupied holding platforms, context includes actual containment strength, held entity minimum strength, activity, suppression enabled/threshold, current containment mode and activity study factor. Each exported worker option uses a nonallocating readiness mirror of installed `WorkGiver_Warden_SuppressActivity.JobOnThing(worker, platform, false)`, after checking a healthy enabled nonzero-priority Warden, path access, and `ActivitySuppressionUtility.CanBeSuppressed`. The scanner retains native reservation, interaction-cell, activity/threshold and suppression-rate checks. Workers tending/rescuing/feeding/operating, drafted/downed/in mental state, dangerously ill or already suppressing are excluded.

Execution regenerates the same native job and calls `TryTakeOrderedJob`. **Assigned is not completed.** Activity is not edited. Disabled suppression is not silently enabled, and configured thresholds are not overwritten. Lower activity can reduce containment pressure but slows study; weak containment remains weak, and no no-escape guarantee is made. Capture/transfer commands and psychic rituals use the separate native policy and ritual endpoints described above. Redesigning containment cells uses architecture; suppression itself never executes an entity.

## Live hazard and opportunity context

The read-only collector reports actual DLC activation. It exposes polluted cells/percentage, each spawned wastepack's count/frozen/dissolution status/temperature, powered mech chargers, controlled group energy and gene-bearing colonists' active genes, gene resources (including hemogen), resource targets, gene-caused needs and visible hediff names. A compact `hazard_summary` preserves unfrozen waste counts, observed energy below 20%, insufficient-strength platforms and resource/need values. Public `summary(snapshot)` provides five small model-fact fields: low-energy mechs, insufficient containment, pollution/unfrozen waste, gene resources below their actual target and gene needs below 20%. Counts remain complete; each example list is bounded to four entries. Twenty percent is a summary marker, not a native urgent threshold or mandatory recharge instruction.

Royalty context includes actual owned abilities with untargeted CanCast acceptance/reason, cooldown, base psyfocus cost/entropy gain, current psyfocus/relative entropy, title definitions, granted permit definitions, faction favor and permit cooldown. **CanCast does not mean any chosen target is legal**; permit presence/cooldown does not mean a call can succeed. Owned permits execute through the native permit endpoint; targeted casting and permit targets continue through the root affordance/session workflow.

Ideology context includes the pawn's actual current role and ritual precept presence, plus existing connected Gauranlen trees' bound pawn, actual/desired connection strength, dryad kind, supported dryad count and native pruning hours required to maintain the desired strength. Ritual presence is not readiness; roles are obtained through native ceremonies; caste requests retain the actual change ceremony/work and cocoon delay.

## Coverage matrix

| DLC/system | Concrete observed support | Executable support | Remaining gaps |
|---|---|---|---|
| Royalty psycasting/meditation | Actual abilities, acceptance/cooldown, psyfocus and entropy, costs | Root native abilities, local/destination/world targets and map menus | Native desired-focus policy and a selected Work hour → Meditate are executable; loaded construction supplies focus infrastructure. Actual meditation, psytrainer acquisition and entropy recovery still take game time |
| Royalty titles/permits | Titles, granted permits, favor/cooldown and exact aid/payment options | Native owned permit use and root targeter; ordinary bestowing quests and room/apparel management | Honor must be earned, valid targets chosen and nobles cared for; no rank/favor grants |
| Ideology roles/rituals | Native ritual candidates, assignments, role eligibility, quality range, duration and blockers | Native ceremonies, role-change ceremonies, explicit participant/spectator changes and confirmations; root role abilities | Actual ritual quality/outcome and beliefs depend on colony conditions; new ideology design/reform follows its own UI |
| Ideology Gauranlen/dryads | Actual binding/strength/desired/caste/max and native pruning labor estimate | Connection ritual through plant gizmos, native caste dialog/confirmation and pruning target policy | Actual connector work, cocoon healing and dryad return actions use ordinary native menus; no instant strength/caste/dryads |
| Biotech mechs | Groups/energy/modes/thresholds, powered chargers and live boss summon gates | Native group policies and boss summon jobs; root loaded production recipes and ordinary repair/control menus | Actual chips/research/gestation, bandwidth, charger compatibility and waste capacity must be obtained |
| Biotech pollution/waste | Actual map pollution and frozen/dissolving waste stacks; waste and power costs visible in mech choice | Root loaded building, storage-filter, hauling and production/logistics actions | Waste freezer/pump/atomizer construction and real throughput still consume resources, power and labor; disposal has diplomatic costs |
| Biotech genes/xenotypes | Active genes/resources/needs; whole powered genepacks, native assembly biostats/limits | Native xenogerm design, naming and assembly request; root ordinary extraction/medical menus | Real work, banking, capsules and implant recovery are required; food demand is a consequence, never a guaranteed forecast |
| Biotech sanguophage/deathrest | Actual hemogen resource/target, Deathrest need when present, gene-specific needs and observed conditions | Society native hemogen pack consumption, deathrest menus/policies; root bloodfeed abilities with legal targets | Actual donor safety/anemia, device capacity and recovery must be monitored; never synthesize blood or delete exhaustion |
| Biotech children | Society actual Learning/Play needs and learning desires; normal timetable | Society native learning timetable, baby caregiver jobs and growth choices | Loaded classroom construction and autonomous teacher/pupil work require actual people, schedules and time; see `society.md` |
| Anomaly containment | Occupied player platform/entity strength/activity/threshold/mode/study factor and feasible warden choices | Native suppression, capture/transfer/cancel commands, study/maintain and researched extraction policy | Root loaded construction/logistics supplies containment and inhibitors; actual transport/study/harvesting needs workers and safe strength. Entity release/execution is outside this focused policy endpoint |
| Anomaly research/exploitation | Actual current entity study factor/mode; existing generic research/building catalogs | Native Study policy and researched extraction toggle; root loaded research/building catalogs | Real study discovery gates and harvest labor remain; no guaranteed knowledge forecast |
| Anomaly threats/psychic rituals | Native researched ritual menu, candidates, role assignments, power/quality/blockers and containment context | Native psychic ritual preparation/start plus explicit confirmation; progression monolith/structure/node finale; root native menus/medical diagnosis | Actual ingredients, research, containment, threat investigation and survival remain game work; no hidden infection removal or forced outcome |
| Modded/absent systems | Instantiated active genes/abilities and actual groups/platforms are used, not fabricated | Three verified vanilla mech modes and native suppression worker class | A new mod work mode/ability/job is not automatically authorized; absent DLC creates no corresponding action options |

Readonly context is intentionally not described as execution coverage. Native specialist commands cover seven action families. Remaining colony labor and broader DLC interactions are coordinated through ordinary root affordances and production/medical modules; this module does not claim a command guarantees its eventual result.

## Sources and verification

Installed XML: `Data/Biotech/Defs/Misc/MechWorkModes.xml` (Work autonomous/threshold recharge, Recharge overrides group limits, SelfShutdown slow charger-free recovery); `Data/Biotech/Defs/ThingDefs_Items/Items_Resource_Manufactured.xml` (Wastepack dissolution/pollution/damage tox gas); `Data/Biotech/Defs/NeedDefs/Needs.xml` (Deathrest, Learning and gene-caused needs). Installed decompiled classes: `MechanitorControlGroup.SetWorkMode`, `Pawn_MechanitorTracker`, `Need_MechEnergy`, `Building_MechCharger`, `CompDissolution.IsFrozen/CanDissolveNow`, `PollutionGrid`, `Gene_Resource.ValuePercent`, `Gene_Hemogen`, `ActivitySuppressionUtility`, `WorkGiver_Warden_SuppressActivity`, `CompActivity.ActivityResearchFactor`, `CompHoldingPlatformTarget`, `CompEntityHolder`, `Pawn_PsychicEntropyTracker`, `Ability/Psycast.CanCast`, `AbilityDef`, `Pawn_RoyaltyTracker`, `FactionPermit`, `Ideo.GetRole` and `CompTreeConnection.PruningHoursToMaintain`.

Official primary web context: [Biotech labor mechs](https://ludeon.com/blog/2022/10/biotech-preview-1-mechanitor-infrastructure-and-labor-mechs/) and [mechs and pollution](https://ludeon.com/blog/2022/10/biotech-preview-2-combat-mechanoids-pollution-and-super-mechanoid-bosses/); [Ideology roles and rituals](https://ludeon.com/blog/2021/07/ideology-adds-social-roles-and-rituals/); [sanguophages and deathrest](https://ludeon.com/blog/2022/10/biotech-preview-4-xenotypes-world-factions-and-the-dark-blood-drinkers/); [Royalty meditation](https://ludeon.com/blog/2020/05/update-may-2020/); [Anomaly containment](https://ludeon.com/blog/2024/03/anomaly-preview-2-containment-facilities-creatures-and-release-date/).

`tests/test_specialists.py` covers: loaded DLC/native options only, charging/protected group represented as no option, absent feasible warden, current mode exclusion, native dormant choice, both defer stages/cooldown, selected containment risk in detailed context, stale refusals, director extras allowlist, failed-order no-progress and compact hazard/resource summary. Target facts are compact (mode/energy range/member count or containment strength/activity first). Suppressor lookup filters by native `WorkGiverDef.giverClass` and caches that single worker; it does not instantiate every WorkGiver for each worker/entity pair. Installed `WorkGiverDef.Worker` constructs its worker with `Activator.CreateInstance(giverClass)`, confirming the field. Parent performs the shared C# build and integration test gate. No game/Laya runtime launch, commit or push was performed for these changes.

Additional exact native sources inspected for executable workflows: `Command_Ritual`, `Dialog_BeginRitual`, `Dialog_BeginPsychicRitual`, `Dialog_BeginGravshipLaunch`, native ritual role managers, `RitualRoleIdeoRoleChanger`, `RitualUtility.AllRolesForPawn`, `Dialog_CreateXenogerm.CanAccept/Accept/OnGenesChanged`, `Building_GeneAssembler.GetGenepacks/Start`, `Command_CallBossgroup.IsDisabled/FloatMenuOptions`, and `RoyalTitlePermitWorker.GetRoyalAidOptions`. Pack power/access is rechecked at mutation; protected medical workers are excluded from ending-site, pilot and boss jobs. Native permit targeters are completed by the root local/world targeting session modules. The shared audit records current combined unittest and C# build results.
### Meditation, Gauranlen and entity policy integration

`specialists_policy` and `/specialists/policies` expose explicitly requested-map ordinary policies. Royalty desired psyfocus selects 25/50/75/95 percent using `SetPsyfocusTarget`, and an explicit selected Work hour can become Meditate while preserving Sleep/Joy. The native timetable/job giver then finds a personal valid focus and performs actual meditation; GET never allocates a meditation job or reserves a focus. Higher targets remove worker time from survival/production.

Connected Gauranlen trees offer native desired pruning strength with current strength, maximum dryads and `PruningHoursToMaintain` cost. Unconnected observed trees expose actual connection ritual commands through the ritual controller, with normal participant selection. Caste opens `Dialog_ChangeDryadCaste`, offers only native `MeetsRequirements` modes and the normal irreversible downtime confirmation, then invokes the ordinary StartChange callback. The connector and cocoon work complete the change. The pending-session registry recognizes that dialog and permits explicit cancel rather than indefinite defer.

Anomaly capture/transfer/cancel actions come from actual `CompHoldingPlatformTarget.CompGetGizmosExtra`, excluding debug controls; platform selection runs through the root native targeter and normal handlers subsequently carry the entity. Held entities expose the exact ITab_Entity Study/MaintainOnly radio policy and BioferriteExtraction-researched extraction checkbox when no attached harvester owns extraction. The choice shows containment strength versus minimum and current entity inspect state; legal capture or study does not certify no escape. Loaded construction/storage/logistics/production actions supply infrastructure, materials, waste storage and harvesting jobs. No capture, study, focus or pruning result is synthesized.

Installed primary classes: `Pawn_PsychicEntropyTracker.SetPsyfocusTarget`, `JobGiver_Meditate.GetPriority/TryGiveJob`, `MeditationUtility.CanMeditateNow/GetMeditationJob`, `CompTreeConnection`, `Dialog_ChangeDryadCaste.MeetsRequirements/StartChange`, `ITab_Entity.FillTab`, `CompHoldingPlatformTarget.CompGetGizmosExtra`; Ideology `RitualPatterns.xml` Gauranlen connection uses `ConnectToTree` outcome. The suppression source lacks a nonallocating HasJobOnThing override, so GET mirrors its exact eligibility checks and allocates no Job; POST alone requests the real WorkGiver JobOnThing.
Shared specialist diversion safety also protects the exact installed Society childcare, lesson, deathrest, interrogation and ingestion job names, alongside drafted pawns, treatment/rescue/feed/surgery and dangerous illness.


## Cycle contract repairs (2026-10-02)

Every native GET now receives snapshot `map_id`. Policy GET uses that map rather than UI CurrentMap; other nonconfiguring rows are scoped and filtered by returned map IDs. A configuring dialog owns its native map. Body endpoint `/specialists/order` accepts `{map_id,kind,mechanitor_id,group_index,value,platform_id,worker_id,pawn_id,thing_id}` as applicable. The five named specialist controllers use POST query parameters, `confirmed=true`, native string result inside ApiResult.data, and Python reports accepted effects separately from completion.

### Exact POST operation contracts

All configuring ritual/genetics/caste operations require object-bound `session_id`. WindowStack.Add creates a new Guid generation even when a Window object is reused; weak references avoid retaining closed windows. POST verifies the current open Window and matching token before mutation. Close/reopen isolates both stale command admission and configuration history. Open commands use selected native IDs, with no invented unrelated pawn/thing/role IDs.

| Endpoint | Operation | Required operation fields (besides confirmed) |
|---|---|---|
| rituals | open | map_id, thing_id, label |
| rituals | assign | session_id, pawn_id, role_id |
| rituals | remove / spectate | session_id, pawn_id |
| rituals | role | session_id, role_id |
| rituals | policy | session_id, policy, value |
| rituals | begin / cancel | session_id |
| genetics | open | thing_id |
| genetics | select | session_id, thing_id, selected |
| genetics | name / begin / cancel | session_id |
| policies | focus / meditation_hour | pawn_id, value |
| policies | pruning / study_mode / extract | thing_id, value |
| policies | open_caste | thing_id |
| policies | capture_command | thing_id, label |
| policies | caste | session_id, value |
| policies | cancel | session_id |
| mech-bosses | summon native menu choice | pawn_id, label |
| permits | owned native menu choice | pawn_id, faction_id, permit, label |

Native parsers read only fields required by the selected branch; required fields still reject omission. This repairs previous unconditional thing_id/pawn_id/role_id/value reads that rejected valid Python begin/cancel/configuration queries. Query fields include map identity where available. No dummy IDs are transmitted. DLC and ordinary job/eligibility guards remain native.

Successful dwell is scoped to semantic subject/family, including focus, pruning and containment policies. Another subject remains eligible. Defer uses discrete readiness; failures suppress only the selected command until both 60 game ticks and 30 real seconds expire, or 2 wall-clock seconds for paused configuration. Cancel remains eligible. Expired/future records, inactive sessions and empty buckets are pruned; save/load and rollback are covered.

Paused configuration history records the actual subsequent GET result, without trial mutations. The first undo is allowed; repeating an already traversed source-configuration/command edge in the same session is suppressed (last 32 edges). Native prerequisite or external configuration changes reset that guard; volatile floats/time and unrelated map inventory do not. Gene-name randomization is offered once per selected-pack composition (last 16 compositions). Begin, Cancel and genuinely new transitions remain explicit choices; no strategic Begin is forced. Model/log facts include the previous accepted effect and repeat reason. Missing continuation/identity produces pending_blocker for the session router.

Begin freshness retains native configuration, selected pack data/power, blockers, readiness, caps and quality. Other operations compare command identity plus relevant costs, target policy and military/permit facts. Already assigned roles/spectators are omitted using actual assignments in preview and POST. Gene-pawn health rows filter Hediff.Visible. Both model stages carry native honor/cooldown, defense, containment and other adverse/cost facts within the bounded consequence interface.

Offline verification: 28 specialist tests and 3 royal-hospitality tests pass, including benign focus drift, subject dwell, first undo/repeated edge, external prerequisites, closed/reopened identity, paused wall-time retry with Cancel, composition naming, exact generated query shapes, map filtering, both-stage defense facts, JSON/rollback/history pruning, and native parser/no-op/hidden-condition source guards. Source guards do not execute native windows, pathfinding or ceremony outcomes. No game, live API, model, build or commit was run; final native build belongs to the parent audit.


### Installed native reflection evidence

Offline ILSpy 9.1.0 used installed `C:/Program Files (x86)/Steam/steamapps/common/RimWorld/RimWorldWin64_Data/Managed/Assembly-CSharp.dll` on 2026-10-02. Exact declarations inspected:

- `Dialog_BeginLordJob` itself has no map field. `Dialog_BeginRitual` declares `protected Map map`; gravship launch inherits it. `Dialog_BeginPsychicRitual` declares `private Map map`. The helper resolves `AccessTools.Field(dialog.GetType(), "map")`, including inherited fields.
- `RitualRoleAssignments`: `private Precept_Role roleChangeSelection` and public `RoleChangeSelection` getter. Configuration now uses that public getter directly.
- `Dialog_ChangeDryadCaste`: private `CompTreeConnection treeConnection`, `GauranlenTreeModeDef selectedMode`, `GauranlenTreeModeDef currentMode`.
- `GeneCreationDialogBase`: `protected string xenotypeName`; inherited by `Dialog_CreateXenogerm`, which defines private `bool ColonyHasEnoughArchites()`.
- `Verse.WindowStack`: `public void Add(Window window)`; Harmony prefix parameter name is exactly `window`.

Malformed persisted timer buckets/records and session histories are discarded during prepare rather than failing every subsequent cycle. Bounds remain 32 edges / 16 names per currently active native session.

Long native descriptions are explanatory tails; actual honor/cooldown, hostile/defender counts and containment thresholds lead benefit/risk/cost fields. A 20-target regression with a long loaded description checks both visible stages at the 312-token state budget.
