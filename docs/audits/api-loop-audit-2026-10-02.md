# API and repeated-decision audit — 2026-10-02

Candidate: 0.0.7. Starting revision: `5a80895`.
Scope: offline source, DTO/route wiring, installed RimWorld 1.6.4871 engine
contracts and sequential regression fixtures. No live gameplay/API, game launch,
director process, observer or model weights are part of this audit.

## Review method

Three GPT-6.1 Sol agents audit one module at a time. For each module they first
report a reproduction, source evidence and a proposed change without editing it.
The parent reads the affected code, accepts or corrects the proposal, then
authorizes implementation. Completed patches receive parent review and QA.
The parent owns orchestration, repository layout, packaging metadata and docs.

## Findings accepted for repair

| Area | Failure sequence | Review decision |
|---|---|---|
| Resilience | Successful care/defer for one patient suppresses every patient for that action | Target-based history; new patients and discrete deterioration remain visible; prune stale/future entries |
| Resilience | Cold room repeatedly offers 18/21/26 targets while warming or unpowered | Stop rotating a safe target; match heater/cooler direction and preserve intentional freezers |
| Resilience | Hunger omitted from feeding comparison; dirty kitchen excluded; beds capped before doctor access | Pass actual hunger, include kitchens, filter before truncation |
| Production | Unsafe first stack hides later usable stack of the same definition | Apply feasibility before selecting representatives |
| Production | Permission on a full shelf treated as available storage | Native physical-capacity checks; distinguish route/worker blockers from need to expand storage |
| Production | Stale selection immediately repeats; unrelated endpoint failure disables utility control | Short per-option backoff and independent endpoint status; refresh only the selected command's observation |
| Production | Switching one lamp blocks a newly cold heater for 15000 ticks | Dwell by building/policy family; new buildings and meaningful thermal changes remain visible |
| Progression | Canceled/changed caravan formation leaves a saved route blocking all later journeys | Track exact native forming lord and roster; explicit invalidation, exact caravan creation callback |
| Progression | Ordinary home-food/job changes reject otherwise eligible journey/boarding | Stable identity/manifest and material eligibility checks with fresh native validation |
| Progression | Empty native landing options repeatedly invoke an empty model question | Explicit blocked continuation; correct-map action and bounded landing search |
| Society | Global care timers hide a new baby; persistent addiction can repeat administration | Target-specific history and native dose-due predicates |
| Society | Baby exposure exception bypasses hostile-route guard; discretionary surgery interrupts care | Distinguish environmental rescue exposure from enemy routes; protect ongoing care |
| Society | Need-specific context omitted; rejected deathrest reports scheduling | Expose actual need and distinguish accepted/rejected reasons |
| Sustenance | One animal's policy locks all animals; stale orders retry immediately | Subject/family dwell, short exact-option failure history, discrete clinical changes reopen choices |
| Sustenance | Policy dwell prevents canceling sterilization or release | Native cancellation bypasses successful/deferred dwell; accepted cancellation prevents immediate requeue |
| Sustenance | Nutrition, clinical facts and campaign supply goal disappear in later choices | Carry compact actual facts through all three choices; expose all native medical-care levels with their risks |
| Sustenance | Advertised fishing zone differs from the native jobgiver's selected zone | Mirror its pure zone-selection rule, then ask the native jobgiver at execution; do not allocate a job during GET |
| Specialists | Unrelated continuous context changes invalidate commands; successful policy toggles have no dwell | Compare identity and operation prerequisites, record target/family history, preserve fresh native checks |
| Specialists | Closed/reopened dialogs reuse intent; role/pack/policy toggles can cycle while paused | Bind a window generation, retain bounded observed transition history, permit first undo and explicit Begin/Cancel |
| Specialists | Generic parsing requires irrelevant IDs for cancel/name/role/policy operations | Parse mandatory fields by operation; no dummy IDs; verify Python query shapes |
| Specialists | Already assigned roles are offered again; hidden hediffs exposed; choices use current UI map | Filter no-op assignments and hidden conditions; explicit map scope, pending dialog retains its own map |
| Affordances | Target/cost/consequences change during inference; reopened targeter retains identity | Refresh selected target evidence; native generation changes on targeting start/stop |
| Affordances | Accepted ability changes its own charges and evades cooldown; failed option can spin | Separate semantic identity from readiness fingerprint; short failures, target-specific accepted dwell and bounded paused retries |
| Affordances | Scanner occupant/state and actual target costs are absent from comparisons | Expose actual scanner state, charges, collateral and clinical facts before execution |
| Combat | Nonempty response counts as success although native accepted no order | Decode endpoint-specific acceptance; preserve partial results and observed native movement/attack |
| Combat | Failed preemptive step can wait up to a minute | Short failure retry, updated hop results and prompt replan on meaningful threat changes |
| Combat | Stale intercept accepts a carrier who is no longer kidnapping a player pawn | Revalidate native kidnapping intent before drafting; other targets retain ordinary focus fire |
| Capabilities | Global locks hide another animal/patient/fighter; failed requests retry without memory | Subject/family history, short selected-option failure history and fresh execution checks |
| Capabilities | Duplicate augmentation can alter a preexisting bill/bed; incapable surgeon offered | Check native medical capacities and duplicate/current operations before any mutation |
| Capabilities | Stale Equip can interrupt newly started patient care | Atomic native equipment and care validation; preserve already active equipment work |
| Capabilities | First 200 ineligible blighted plants hide a later eligible plant; re-designation claims success | Filter before cap; count actual changes; preserve existing native cutting job |
| Capabilities | GET plant preview constructs a zone and consumes a native unique ID | Pure preview without a Zone_Growing allocation |
| Capabilities | Primary success hides failure of enabling work/sowing | Preserve partial step results and repair only the missing auxiliary step |
| Capabilities | Same-definition EMP improvement disappears because generic damage score is zero | Expose real differing properties as alternatives without choosing a weapon for Laya |
| Architecture | Partial room reserves its rectangle indefinitely and suppresses hospital replacement | Persist exact intended layout; reconcile and explicitly repair missing elements at its original site |
| Architecture | Some loaded floor definitions cost zero in the estimate | Read native terrain cost lists before known legacy fallbacks |
| Ship construction | Wrong rotation satisfies a planned component; failed first placement fixes a bad site forever | Observe rotation; retain a site only with physical evidence and reconcile unknown POST outcomes |
| Legacy hospital | A lifetime issued flag prevents recovery; an empty failed site is reused indefinitely | Observe existing medical beds; retain partial layout, repair missing elements, and permit bounded new-site search only after positively empty failure |
| Expeditions | Raw ration counts, missing return ETA and unbound formation identity permit unsafe or stuck departures | Shared native nutrition/mass/two-leg preview, explicit exact-plan confirmation and persisted Lord/roster identity |
| Rescue site | Rejected return clears the mission; first unavailable worker hides feasible rescue pairs | Require explicit acknowledgment, retain unknown/rejected attempts with retry, select feasible pairs before truncation; return requested remains unverified |
| Planning context | A rejected expedition's readiness disappears; disabled workers inflate skill summaries | Project dated bounded readiness with expiry; summarize usable non-disabled skills and use the native Medicine skill key |
| Shared retries | At 3× game speed a short tick-only failure expires before the next decision | Keep an exact-option real-time floor, invalidate malformed clocks/rollback, preserve other recipients |
| Events/growth | Rejected events are marked handled; mental or disabled workers counted as available skill | Store deliberate/accepted acknowledgments only, short real-time retry; report usable workforce |
| Orchestration | World/modal errors occur before the old retry gate | Gate all cycle reads; offline clock fixture verifies attempts at 0, 10, 30 seconds |
| Orchestration | One domain's malformed preparation aborts the whole colony cycle repeatedly | Clear that domain's partial context, record error phase, continue other domains; fresh collection permits recovery |

These are concrete failure sequences, not a claim that a language model can
never choose the same strategically poor option twice.

## Parent review corrections

Proposals were not accepted solely on an agent's completion message. The parent
read the changed Python and native paths and required these additional changes:

- Preserve new patients, buildings and animals instead of moving an action-wide
  lock into a different dictionary.
- Keep safe thermostat targets stable while rooms warm; preserve intentional
  freezers and distinguish heaters from coolers.
- Limit native landing search work per request; an unavailable landing remains
  a blocked continuation without repeated empty model questions.
- Remove a proposed global stock fingerprint from dialog-loop memory. Only
  relevant observed prerequisites may reset the guard; unrelated food decay or
  hidden items must not reopen a repeated transition.
- Allow one configuration undo and urgent policy cancellation. Loop prevention
  must not force a ritual, surgery, release or gene assembly to begin.
- Put concrete cost, collateral and clinical facts before long loaded
  descriptions so truncation cannot silently remove the decisive downside.
- Retain exact native response contracts and distinguish accepted work from
  completed work. A route-name inventory alone does not validate payloads.
- Identify the main combat command separately from reserve/support commands;
  reserve movement cannot acknowledge a rejected preemptive strike.
- Do not serialize native Lord/map graphs into expedition observations. Export
  scalar identity and status; persist native references through game serialization.
- Use actual native nutrition and travel estimates, preserve the existing home
  reserve item's unit, and state unsupported diets/pack animals explicitly.
- Keep an empty failed hospital site distinct from a partially built hospital;
  only the former permits relocation, while missing parts require explicit repair.
- Require rescue return acknowledgment and preserve the mission after unknown
  replies; a request to return is not evidence of arrival or survival.

The parent also inspected the shared choice adapter and outcome memory. Each
tournament round reduces the candidate count; packing loops shorten bounded
strings or raise an explicit error, rather than retrying model inference forever.
Outcome memory retains one before-observation per map and reports observation,
not inferred causation. These structural bounds do not prove that repeated
strategic choices across game cycles will be beneficial.

## Repository and documentation

- Active branch: `fix/0.0.7-cold-start`; PR #4 targets `developing`.
  `main` is the stable branch. At the start of this audit the branch was six
  local commits ahead of its remote and zero behind after fetching references.
  Other local worktrees and branch pointers were retained.
- Flat `colony_*.py` names are retained to preserve imports, launch scripts
  and installation. The architecture guide now maps ownership and explicitly
  identifies the remaining director orchestration. Seven domains use the registry.
- `VERSION` advances to the unreleased 0.0.7 candidate. Source GUI,
  frozen GUI resources, PowerShell install and Inno packaging now share it;
  the separate RIMAPI assembly version is not the product version.
- Added a documentation index; corrected current release instructions, the
  case-sensitive `RimApi.csproj` path and old snapshot-validation wording.
  Versioned playtests and audits remain dated historical evidence.
- `.gitignore` covers environment files and save backups while allowing
  synthetic JSONL fixtures and environment templates. The distributed
  `RIMAPI.dll` remains tracked intentionally; generated bin/obj/dist stay ignored.
- Full GUI/installer packaging is a separate release check; this audit verifies
  version-resource lookup, payload inclusion and PowerShell syntax.

## Verification

| Reviewed ownership | Paths and checks |
|---|---|
| Care agent | Resilience, society, specialists, architecture and ship construction: DTO fields, feasibility, target/session identity, dwell, partial outcomes and recovery |
| Sustenance agent | Production, sustenance, capabilities and legacy hospital follow-up: observations, units, native command guards, partial execution and retry scope |
| Ending agent | Progression, affordances/sessions, combat, events/growth, ordinary expeditions and strategy: dynamic continuations, payloads, acceptance, saved identity and finite-choice loops |
| Parent | Proposals and final patches, shared orchestration/clocks, compact readiness/skills, rescue acknowledgment, real-tokenizer budget, repository and packaging contracts |

Final offline gates after review:

- **802 Python tests pass**. Fixtures cover distinct recipients, game/real clock
  drift, partial and lost responses, malformed/stale state, exact construction
  identity, no-start cases, prompt consequences and rejected command handling.
- **Release-1.6 C# build passes with zero warnings and zero errors**, against
  installed 1.6.4871 references. The distributed DLL is rebuilt after the source
  commit so its embedded revision identifies the audited source.
- API inventory: **297 registered routes, 238 literal calls, 20 dynamic calls,
  zero missing literal routes and zero duplicate routes**. Inventory alone does
  not validate payloads or dynamic targets; those paths received module review.
- Real installed tokenizer: **16 scenarios, 299 comparisons**, maximum state
  **308/312 tokens**, maximum combined sequence **419/512 tokens**; complete
  packed state retained. The expedition probe includes twenty long pawn names
  and checks that travel, food, mass, home reserves and uncertainty survive.
  No model weights were loaded or decisions inferred.
- Documentation links, runtime payload imports, ignored tracked files and
  PowerShell parsing were checked. Source and frozen VERSION lookup is covered
  by tests. Full GUI/installer packaging was not performed.

Evidence is stored outside the checkout in `work/loop-audit-20261002`:
`tests-full.log`, `native-build.log`, `api-contracts.json`, `model-inputs.json`
and `repository.json`. The final user report records the resulting commits.

Native map/job scenarios cannot be certified by Python DTO fixtures or source
assertions. Harmony callbacks, saved native references, dialogs and actual jobs
still require a live test. Odyssey Data is absent on this installation; shared
native code compiles but its landing/endgame behavior remains unverified.
Ordinary expeditions currently offer one suggested human roster, common packaged
rations and no pack animals/foraging; there is no dedicated cancel endpoint for
a still-active vanilla formation. See the [expedition contract](../modules/expeditions.md).
An initial return-food allowance does not guarantee food after trading, recruits,
illness or combat. Autonomous survival and victory remain live evaluation gates.
