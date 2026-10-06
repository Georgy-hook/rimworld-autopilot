# Allied Berserk and care observation contract — 2026-10-06

The terminal colony evidence records a starvation-triggered Berserk, ordinary
combat replies targeting that resident, then a blood-loss death. The child died
from beating; the fatal actor is not established. Timeline samples contain an
actual `TendPatient` job for the caregiver, but do not identify its patient.
An accepted tend assignment does not establish timely treatment of that resident.

## Execution ownership

`MentalSafetyHelper.Options/Context` now describe Berserk alongside murderous
rage. Murderous rage retains its named victim. Berserk exposes the observed
current job target and feasible ordinary evacuation/arrest/rescue options for
nearby allies; this does not predict a permanent victim, force recovery or
promise nonlethal arrest. Route screening excludes the aggressor from the generic
raid hazard check, while its explicit pursuit-distance checks remain in place.
Other hostile pawns, structures, fire and visibility still screen the route.

Native `TakeDefenceOrder` binds only the newly accepted current or queued attack on a currently
active allied mental aggressor. Each lease has an opaque key, actor, map, mental
state session, target and exact native Job object. `Context` observes leases.
Python `reconcile_defence` requests cancellation only for an observed stale lease.
Native `CancelDefence` repeats exact job and threat validation before ending the current matching job or removing the matching queued job.
A different care/raid job or fresh session cannot be cancelled with the old key.
Cancellation neither globally stands down the colony nor undrafts the actor.
A newly threatening enemy remains available for subsequent model choices.
Native leases are transient and are not restored from a save; this change does
not adopt arbitrary pre-existing or manual attacks after process/save restart.

`colony_downed_combat.finishable_target` excludes player/colonist/prisoner/allied
rows from finishing proposals and issue. The native executor independently
rejects allied targets before drafting, using faction relation and player identity.
Native `HostileTo` during a mental break does not authorize finishing a friend.

Post-combat care uses `colony_medical_recovery.validate_post_combat_plan` to
repeat the existing care catalogue with fresh combat facts. An exact current
TendPatient/Rescue/LayDown is preserved without a second order. Native assignment
acceptance remains `applied`; `assignment_accepted` and `job_observed` distinguish
acceptance from fresh job/target observation. Treatment completion remains
unverified. Lost readback reports unknown; the existing care cycle retry timing
remains responsible for revisiting it. This is not a new clinical progress lease,
and native bed/route feasibility remains authoritative at execution.

## Offline verification

375 targeted sequence, director, hive, thermal-tokenizer and existing combat/care tests passed. Added sequences
exercise active attack → downing → scoped release, recovered target with a fresh
care-job race, allied finishing refusal before any command, new raid eligibility,
accepted care with wrong patient, exact current care without restart and lost
readback. Integrated selections then change the doctor to drafted/downed/mental
state before fresh validation: no order is issued, and a recovered doctor can
subsequently choose a new urgent patient. Cached options cannot override a fresh
unavailable actor or replace unrelated current tending. Offline care transport
returns real combat DTO shape and records exact native job targets without
pretending that assignment has stopped bleeding. Native source assertions accompany transport doubles; they do not prove
native job completion. The parent native validation build passed with zero warnings and errors.
The repository-wide gates and final distributable package belong to the parent
release preparation task. No live game was started or commanded.
