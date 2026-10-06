# Resilience: patients and environmental survival

## Bedside recovery after Requader (2026-10-03)

`colony_medical_recovery.py` supplies the director's patient and helper choices
from native Resilience options. A hungry downed human or animal without a usable
bed can produce a temporary-bed prerequisite. Native bed search, reservations,
route and actual food eligibility remain separate facts. The builder verifies a
real site and placement; subsequent snapshots enable rescue and feeding. A spot
alone does not rescue or feed anyone. Active jobs and bounded pending placement
prevent repeated orders. Exact current-bed identity distinguishes occupied beds.

Uncontrollable caregivers are rejected before selection and again natively.
Emergency care may interrupt cleaning, while ongoing patient care is protected.
Malnutrition remains urgent after bleeding stops. Triage includes blood already
lost and an explicitly approximate constant-rate bleedout estimate, preserving
other feasible patients. Native accepted jobs are scheduled, not cured patients.
Permanent-tend conditions do not query the invalid treatment-overlap property.
The [postmortem](../audits/requader-postmortem-2026-10-03.md) records verification limits.

The module observes all spawned player colonists, prisoners and player animals, not just gunshot victims. Every visible hediff is described by its installed definition, affected part, severity, lethality threshold, bleeding, life threat, current tendability, immunity, current immunity gain, severity component rates, tend quality, treatment expiry and next treatment time. Thus infection, influenza, plague, malaria, sleeping sickness, gut worms, muscle parasites, food poisoning, toxic buildup, heatstroke, hypothermia, anesthesia, pain, pregnancy, blood loss and DLC health effects retain their different causes and recovery rules. Severity component rates are observations, not guaranteed time-to-death forecasts.

Eleven real choices have live native feasibility checks and a Laya defer alternative:

| Workflow | Native behavior | Limits and tradeoffs |
|---|---|---|
| Tend | Installed DoctorTendEmergency, DoctorTendToHumanlikes, DoctorTendToSelf and DoctorTendToAnimals workgivers select normal medicine/job | Respects medical ceiling, reservations, posture, work enablement, capacities and path. Medicine and doctor labor cost; the observation must confirm later recovery. |
| Rescue | DoctorRescue chooses a normal appropriate bed and carrying job | Handles downed illness/temperature/toxic/pain victims as well as injuries. An available reachable bed is required; rescue is not treatment. |
| Feed | DoctorFeedHumanlikes / DoctorFeedAnimals choose normal food and feeding job | Native dependency, bed, diet and reservation rules apply. Food and caregiver time are spent. |
| Clean | CleanFilth chooses accessible filth in enclosed sick-patient, hospital-bed and native electric/fueled stove kitchen rooms | Cleaning reduces environmental contamination; it does not treat already poisoned food or prevent random disease incidents. |
| Rest | PatientBedRest work priority becomes 1 | Ordinary recuperation remains autonomous. This is distinct from the Patient work type used for emergency treatment. Work output falls; a bed and normal AI decision are still needed. |
| Prevention | One normal Ingest job for available Penoxycyline | Adults without current protected illnesses/active preventive hediff only. Prevents new malaria, plague and sleeping sickness; no immunity injection or cure. Doses are consumed. |
| Inspection | Queue SurgicalInspection normal medical bill after observable gray flesh/completed analysis/visible discovered anomaly evidence | Native Medicine3 and 2 medicine requirements; four cut damage and one day anesthesia. Matching biosignature analysis is needed for detection, infected doctors can lie, and detection can trigger emergence. Hidden implant rows are never used as a known diagnosis. |
| Interrogation policy | Enable Interrogate for an existing adult prisoner | Warden labor and uncertain detection; arrest is a separate gameplay choice. |
| Interrogate | Native InterrogatePrisoner workgiver executes enabled identity interrogation | Respects prisoner interaction cooldown, awake/posture, talking, reservation and route requirements. A negative result does not prove safety. |
| Roof guard | Cancel a selected mine/deconstruct designation which removes planned roof support | Roof-connected 6.9-cell searches follow the native support geometry with planned removals excluded. Resources or construction are delayed; replacement supports must be built first. Thick mountain roofs remain unremovable. |
| Temperature | Existing owned heater/cooler thermostat gets 18, 21 or 26 C in a hot/cold occupied human-care bedroom | Power, roof, insulation, outside temperature and vent/door heat transfer determine actual result. It is not an instant temperature edit. |

Workers tending, rescuing, feeding or performing bills are protected from module interruption. An explicitly offered clinical yield can replace only exact stable TendPatient or travelling Rescue before pickup with urgently needed feeding/rescue; native freshness, disease, food, bed, reservation and path checks still apply. Feeding and carrying stay protected. Injured/sick workers may select their normal enabled self-tend job; they are excluded from other discretionary errands. Drafted, downed and mental-state workers are unavailable. Direct patient care uses native forced scans, retaining work-disabled, capacity, forbidden and reservation checks even when autonomous Doctor priority is zero. Other work retains its priority requirement. Automation rejects dangerous gas destinations, exposed fallout destinations and temperatures far outside personal comfortable limits for ordinary errands. Rescue explicitly permits exposure at the downed victim while keeping the bed safe; Laya compares the rescuer exposure against leaving the victim. Straight routes through hostile range remain rejected. Straight-route rejection is conservative; it is not proof of the path RimWorld eventually chooses. Safe distant treatment/rescue/feeding is also protected from automatic combat drafting. Imminent enemy contact can override that protection.

Environment context contains active conditions, personal roof/temperature/comfortable limits, smoke/toxic gas/rot stink/deadlife dust density, occupied/bed/kitchen room cleanliness and temperature, thick mountain roof counts, hive/tunnel-spawner locations and every existing climate device's target/power/room state. Thick mountain roofs cannot be removed through ordinary roofing. A thermostat action does not make a whole mountain infestation-proof, and no speculative burn-room orders are issued. Existing combat templates supply door/melee blocking, withdrawal, ranged concentration and insect kiting; architect and animal allowed-area workflows own shelter construction and policies.

## Sources and implementation evidence

Primary evidence is the installed RimWorld 1.6.4871 `Assembly-CSharp.dll`, inspected with ILSpy without running the game, and installed XML definitions:

- `RimWorld.WorkGiver_Tend`: posture and native medicine selection; it permits Deadly paths, so this module deliberately narrows danger to Some.
- `Verse.HediffComp_Immunizable`: immunity comes from the pawn's immunity record; random severity factors and hediff factors mean treatment does not instantly grant immunity.
- `Verse.HediffComp_TendDuration`: tend quality, overlap/re-treatment timer, expiry and accumulated-quality recovery differ from immunity.
- `RimWorld.Recipe_SurgicalInspection`: native failure checks, diagnosis, four surgical-cut damage and 60000-tick anesthesia.
- `Verse.HediffComp_SurgeryInspectableMetalhorror`: matching analysis signature must be satisfied; infected surgeons can report nothing; valid detection triggers emergence. No internal infection flags are read to select patients.
- `RimWorld.WorkGiver_Warden_InterrogateIdentity`: native policy/cooldown, consciousness, talking, reservation, posture and anomaly availability checks.
- `RimWorld.CompTempControl`: the player-facing thermostat changes TargetTemperature; thermal transfer remains simulation-driven.
- `Verse.RoofCollapseUtility`: native roof-connected support radius is 6.9 cells; support-removal analysis treats currently designated mine/deconstruct holders as absent.
- `RimWorld.BiomeDef`: disease mean interval and public CommonalityOfDisease supply loaded biome-specific incidence context.
- `Verse.GasGrid` / `Verse.GasType`: BlindSmoke, ToxGas, RotStink and DeadlifeDust are separately observable densities.
- `Data/Core/Defs/WorkGiverDefs/WorkGivers.xml`, `WorkTypeDefs/WorkTypes.xml`, `HediffDefs/Hediffs_Local_Infections.xml`, `Hediffs_Global_Misc.xml`, and drug definitions: exact loaded workgiver names, separate Patient/PatientBedRest semantics, parasites, food poisoning and prevention.

External cross-checks broadened the inventory; implementation relies on installed native methods and definitions: [disease](https://rimworldwiki.com/wiki/Disease), [penoxycyline](https://rimworldwiki.com/wiki/Penoxycyline), [infestation](https://rimworldwiki.com/wiki/Infestation), [roof](https://rimworldwiki.com/wiki/Roof), [food](https://rimworldwiki.com/wiki/Food), [temperature](https://rimworldwiki.com/wiki/Temperature), [pollution](https://rimworldwiki.com/wiki/Pollution), [events guide](https://rimworldwiki.com/wiki/Events_Guide). They distinguish incident disease from wound infection, immunity disease from parasites requiring accumulated tend quality, kitchen/cook/raw-food poisoning vectors, and fallout roof shelter from pollution that roofs do not mitigate.

Core, Royalty, Ideology, Biotech and Anomaly are installed. Odyssey is absent in the installed Data directory; [vacuum](https://rimworldwiki.com/wiki/Vacuum) and orbit hazards were researched but native Odyssey gravship/airlock/vacuum workflows were not validated or enabled.

Integration boundaries: society now owns native therapeutic surgery, including eligible amputation of visible diseased/permanently damaged parts; colony_capabilities owns loaded augmentation choices. Sustenance owns animal sterilization, herd policies and areas. Specialists/affordances own genetics and containment. No module force-ends mental breaks, creates a disease cure by editing health, or promises an infestation-free mountain. Architecture and ordinary worker completion remain necessary. Tests cover stale target rejection, cross-action payload rejection, cooldowns, native defer, illness variants and preserved caregivers. No game or model was launched.

Native defense helpers now validate a real single-cell door between opposing solid walls and assign up to three melee fighters to the interior front row, with ranged pawns behind. Each exact destination must be standable, unoccupied, trap-free and reachable. An arbitrary wall is not accepted as an insect choke. Roof-removal admission can call RemovalWouldEndangerRoof before designation, preventing new unsafe mining/deconstruction plans.

Choices are staged by live patient/device/support and then worker/workgiver. Each option carries benefit, risk, cost, inaction and uncertainty separately so the model token budget preserves both sides. Tests include 20 patients where the last patient has unique critical plague evidence; the disease and selected target survive the 512-token configuration.

Anomaly source cross-checks: [metalhorror](https://rimworldwiki.com/wiki/Metalhorror), [gray flesh sample](https://rimworldwiki.com/wiki/Gray_flesh_sample), [doctoring](https://rimworldwiki.com/wiki/Doctoring). Hidden diagnoses are filtered with Hediff.Visible in native observations and readiness; Python also rejects explicitly hidden rows. Observable symptoms, uncertainty and forensic evidence remain available. Inspection and interrogation are proposals, not claims that a named pawn is secretly infected. Regressions include hidden-implant nondisclosure, diagnostic cost/uncertainty and late-patient token pressure.


## Resilience cycle contract audit (2026-10-02)

Transport is GET `/api/v1/resilience/context?map_id=<id>` and POST `/api/v1/resilience/order` with `{map_id, kind, worker_id, target_id, giver}`. Native DTOs and request/response snake_case resolver agree with these keys; `RimApiClient` unwraps `ApiResult.data` and raises native error envelopes. `kind` is a native string whitelist; `giver` is the exact loaded workgiver name, inspection bed ID string, temperature string, or designation name as applicable. Python compares this identity tuple against a fresh context; naturally changing severity/immunity values are not stale keys. Native feasibility runs again before mutation. Bounded Laya answers are validated as `answers[question_id].choice`, including both patient and worker stages.

Successful cooldowns now key on action plus semantic patient/device/support (prevention keys the recipient), independent of worker. A new patient is therefore eligible while a recently ordered patient remains suppressed. Defer records only offered targets with discrete clinical flags, hunger/severity bands, dangerous thermal/gas exposure and significant immunity deficit. Small floating changes do not reset defer; new or materially changed patients do. Loading an older tick bypasses these timers. Failed/stale options get a 60-tick identity-specific suppression and at least 15 seconds of real time; another worker or target remains eligible. Native care-job protection remains authoritative. Feed effects preserve native food, dependency posture and downed state for both selection stages.

Kitchen admission now includes the native electric/fueled stove room, while ordinary native CleanFilth work enablement, reservation, enclosed room and route checks remain. Inspection no longer truncates to three patient-feasible beds before checking the doctor: every bed receives the doctor route check. No inspection outcome is invented; queued bills and scheduled jobs require the next native snapshot to confirm progress.

Targeted offline resilience tests: 21 pass, covering semantic cooldown, new/discretely worsened defer targets, exact failed-option suppression/expiry, feed facts, kitchen source admission and bed feasibility ordering. C# source guards do not execute native pathfinding or prove recovery. No build, game, live API, or model was launched for this patch. Approved thermostat admission now requires an enclosed occupied human-care room, with a bed usable by the present patient. Cold (<10 C) admits only heaters; hot (>32 C) only coolers. A negative cooler target anywhere in that same room marks intentional freezer use and excludes correction. A current target within 18–26 C suppresses all alternative rotations, including while unpowered or still warming/cooling. Context and POST both use the same admission predicate; effects include actual room temperature, existing target and power. Configuration acceptance still does not prove thermal recovery. Source tests check these native predicates and DTO transport; they do not run the native thermal simulation.

Expired and future-tick issued/deferred/failed history is pruned during prepare using the corresponding cooldown horizon; empty buckets and memory are removed. JSON save/load preserves discrete defer signatures, and rollback invalidates future history. A 20000-entry expired history regression leaves only still-current records.

The director exposes severe downed starvation before wound-only triage through the same resilience options and executor. The native per-pawn need rate estimates starvation time; incomplete evidence remains unknown. See [starvation care and yield audit](../audits/starvation-care-yield-2026-10-06.md).
