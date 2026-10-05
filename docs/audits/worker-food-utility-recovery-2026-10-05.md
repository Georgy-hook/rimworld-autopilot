# Worker selection, food and utility recovery

## Observed failure

The last mobile colonist was feeding a patient. All 20 generic work types
advertised that colonist as eligible, but the nested worker selector correctly
protected the feeding job. Its empty options raised a generic ValueError. The
observer paused after the director error, so feeding could never finish and
release the worker. This is a scheduling deadlock, independently reproducible
from the recorded snapshot without model weights or game mutations.

Work types now project `worker_criteria`, including care and cold-shelter rules.
Selection refreshes those criteria; execution checks the exact selected pawn.
`NoFeasibleChoice` yields a logged non-applied result without an incomplete order
or fatal director state. Invalid model output remains an error. Regression
sequences preserve FeedPatient for eight cycles, then release staffing when
the observed job ends; a stale candidate produces no order and the next
development cycle still executes.

Priority changes also preserve the distinction between a suitable worker and
one whose priority still needs changing. Avoiding the reserved researcher must
not select an alternative already at priority 1 and falsely report no worker.
Rescue/doctor/burial staffing proposals now require an actual priority deficit.

## Food evidence

Rough plant inventory included hops as human nutrition. The native context now
separates race-edible human stock from industrial/animal food and exposes each
patient's current policy, self reach, potential feeding reach, native feeding
job eligibility and actually active feeders. Those are distinct observations;
an allowed stack or accepted job is not consumed nutrition.

Food bills expose finite count, requested state, suspended state, active workers
and blockers (fuel, power, ingredients, workers and reach). Completed finite
kibble orders are not evidence of current production. An actually requested
unused feed bill can be offered for suspension; humans' emergency use remains
explicit. No bills are silently deleted.

Cooking fuel demand remains visible with small or missing ingredient deliveries.
An electric stove only resolves fuel demand when observed powered. Lighting
requires an affordable real service plan; an existing lamp or lamp project in
the room suppresses duplicate construction. A new electrical light includes a
continuous route to a producing network, and a torch discloses heat/fuel costs.
Placement readback verifies the plan, not completed illumination.

Utilities use per-building/policy dwell with real and game-time floors. Meaningful
fuel/network/temperature-band changes reopen the choice; minute fuel drift does
not. At-risk harvest records accepted designation separately from delivered
nutrition, preserves an observed harvest job, and tracks plant-specific dwell.
New plants and changed danger can still be considered. The historical count of
25 at-risk orders alone cannot prove 25 repeats of identical plant IDs.

## Verification limits

Offline behavior sequences, API route audit and compilation cover these
contracts. Live recovery is recorded separately in the colony journal. Existing
malnutrition, dependency and deaths preceded the worker deadlock; fixing the
loop does not reverse those outcomes or establish guaranteed survival.
