# Starvation care prerequisites and scoped yield — 2026-10-06

## Observed failure

The archived reboot baseline (tick 2517462) has a child downed on the ground, food zero and native Malnutrition 0.912 / lethal severity 1. Another patient has bleeding 0.244 and Malnutrition 0.850. The only mobile caregiver is harvesting: Doctor priority is 0, but Doctor is not disabled; his old gunshot is permanent, already treated and not threatening. Native resilience offers no rescue/feed/tend. At tick 2528359 the child remains unbedded, approaching the lethal limit, while the caregiver is tending the other patient, whose bleeding has stopped. The child later dies of Malnutrition, confirmed by the native letter. These are archived observations, not a replay of new code.

There are three separate blockers: normal native patient feeding requires a bed; the contextual scanner required autonomous Doctor priority >0 even for explicit manual orders; and all existing care jobs were excluded without a narrowly validated clinical alternative. The previous Python comparative deadline covered BloodLoss only. Root separately owns action scheduling and compact nutrition/defer facts.

## Transport

GET `/api/v1/resilience/context?map_id=...` retains ordinary options. Care options add `travel_distance`, `starvation_ticks`, `malnutrition_severity`, `lethal_margin`. A permissible replacement additionally carries `expected_current_job`, `expected_care_patient_id`, and `care_yield_reason`. Native patient rows add the same clinical facts plus `bleedout_ticks` and `bleeding_evidence_complete=true`.

POST `/api/v1/resilience/order`: existing map/kind/worker/target/giver plus the two optional `expected_*` fields. POST medical feed: existing patient/feeder IDs plus the same optional fields. Missing binding preserves ordinary protection; a supplied stale or partial binding is rejected before order mutation. Python `care_order_fields(row)` transfers only a well formed binding. `offered_care_yield(snapshot,row)` checks exact observed worker job, target, carrying state and newly visible clinical danger. `clinical_deadline(patient, native_option=None)` compares minimum known death estimates without changing the existing `triage()` tuple contract.

Normal player-forced feed/rescue/tend scans use native `forced:true` with work-disabled and native required-capacity checks, without changing work priorities. Other autonomous work retains its existing priority requirement.

## Native limits

Only exact current TendPatient or Rescue may yield. FeedPatient and already carrying Rescue cannot yield. Current/queued care protects against repeats. Tend requires stopped bleeding; travelling Rescue may yield when the old patient's known bleedout estimate exceeds the new starvation estimate by a factor of two plus 600 ticks, and the old patient's starvation estimate is more than 600 ticks later. Unfinished immunity races and other currently threatening diseases remain protected. New starvation must be native Starving and either life threatening or severity >=0.75. Native food, actual bed, reservations, forbidden state and both approach/carry or food-delivery path legs are checked before taking the ordinary job. No EndCurrentJob, manual disease change or draft change is added.

Applied is verified against actual current FeedPatient food/patient targets or Rescue patient/bed targets. If only queued or rejected, remove only the attempted queued Job object; retain unrelated/current jobs. Completion and nutrition gain are never inferred from order acceptance.

## Primary installed 1.6 evidence

Local ILSpy extracts are under `work/inspection-tools/starvation-triage/`:

- `Need_Food.cs`: private `MalnutritionSeverityPerInterval` at line 87 is `0.0011325 * Lerp(0.8,1.2,Rand.ValueSeeded(pawnID ^ 0x26EF7A))`. `NeedInterval()` at line 158 applies the value every 150 ticks while Starving and not frozen (or deathresting). The helper reflects the actual per-pawn getter and native IsFrozen; missing/getter failure returns unknown. ETA assumes unchanged hunger and normal need intervals; no wall-clock death promise.
- `FeedPatientUtility.cs`: ShouldBeFed requires human patient InBed and ShouldSeekMedicalRest. Ground feeding is not a valid substitute for rescue.
- `WorkGiver_RescueDowned.cs`: HasJobOnThing calls native CanRescueNow and FindBed; wounds are not a prerequisite. JobOnThing creates ordinary Rescue with the actual patient and bed.
- `HediffGiver_Bleeding.cs`: rate >=0.1 increases severity by rate*0.001 per 60-tick interval; below 0.1 it heals. The helper treats native rate<0.1 as no finite bleedout; JSON exports null instead of Infinity. Python uses this only with explicit native completeness, preserving unknown fixture evidence. Conservative Tend still requires stopped bleeding.

## Scheduling and compact context

Before the wound-only care pass, the director projects native feasible feed and rescue options for downed colonists with severe Malnutrition. Food must be natively available. Laya compares these real jobs and may defer. A selected job is refreshed and checked before dispatch; its actual current job is observed before the wound pass sees the actor again. Clinical deadline, lethal margin, travel and the bed prerequisite are offered without equating Medicine skill with feeding ability.

Nutrition consequences state that food stops starvation and tending supplies no calories. Deferring an idle caregiver does not claim to preserve a medical job. Finite patient-scoped dwell reopens at new severe malnutrition bands or a newly offered exact care binding, while active feed/carrying leases prevent repeated orders. Other urgent patients remain reachable.

## Offline verification and limits

12 new behavioral projection/sequence tests cover woundless child, Doctor0 projection, disabled Doctor, exact binding/JSON roundtrip, changed job/target, carrying and FeedPatient protection, same-patient feed from stable tending, dangerous/unknown bleed and immunity protection, existing lease/repeat suppression, new urgent target and starvation comparison. 22 existing medical recovery tests, 8 scheduler tests and 7 existing source guards pass. One existing source guard changed only the worker-loop marker; its no-truncation assertions remain intact.

These tests exercise Python projection/sequence behavior and source contracts. They do not instantiate native Pawns or prove a live meal was delivered. Root also tests the installed CUDA model against recorded contexts: late-state comparisons still include defer and do not establish optimal patient ranking. The urgent nutrition path selected a real feeding option in both orderings. Native installation, real food consumption and longer survival require separately recorded live observations. No victory guarantee follows from the offline checks.

Final integration: 1134 Python tests pass. Native Release-1.6 from source 62ead7c has zero warnings/errors; package 593f56c is installed and exposes real rescue options for the ground child and distant adult despite Doctor=0. Recorded paused checks estimate starvation at about14397 versus24070 ticks and travel19 versus125 cells. Explicit relative deadlines are descriptive context, not a forced target. Actual CUDA replay still exposes option-order sensitivity in patient ranking; the real game continuation must be assessed by delivery and nutrition, not a chosen key.
