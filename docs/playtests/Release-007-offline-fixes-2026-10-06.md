# Offline repairs after the published 0.0.7 run

The colony on random tile 119304 ended after 39m44s, approximately 5.141 game days.
All three founders died of BloodLoss; the emergency survivor died of
WoundInfection, confirmed by native death letters. The separate outcome report
retains the autonomous history. User-authorized repairs below happened after
defeat, with RimWorld closed and hourly observation paused.

| Finding | Cause established in code/evidence | Repair |
|---|---|---|
| Accepted tending followed by civilian drafting | Generic protection disappeared at contact or on exposed travel | Clinical job ownership survives group tactics, drafting and generic attack requests |
| Caregiver needs to escape an immediate attack | A generic retreat cannot express the cost to the named patient | Native exact caregiver/job/patient/threat choice with explicit opportunity cost and route revalidation; carried patients are retained |
| Nine duplicate self-tend HTTP 500s | Same-patient active TendPatient was rejected as other care | Exclude busy actors from new self-tend choices; exact native repeat is idempotent |
| 44 medical-ceiling deferrals | Best already admitted available medicine; hunger changed unrelated defer state | Offer actual permission improvements or stock scarcity tradeoffs; preserve semantic defer on both clocks |
| Ten exact-rest readbacks with unchanged policy | Validation stopped before configuring Patient/PatientBedRest | Configure selected recovery priorities once without restarting the observed LayDown |
| Empty thermal facility despite wood | Routine worker selection excluded the only mobile infected worker | Offer urgent Campfire/PassiveCooler maintenance with explicit recovery costs; preserve clinical care |
| Refuel rejection remembered as issued | Issued marker was written without Applied | Record actual accepted/in-progress assignment only; exclude observed Refuel jobs and check both native routes |

## Contracts

`/api/v1/combat/tactic` accepts `caregiver_retreat` for exactly one caregiver with
`expected_current_job` and `expected_care_patient_id`. GET native options expose
those same bindings. POST verifies current ownership, immediate pawn/turret
danger, absence of a carried patient, and a reachable route avoiding traps/fire
and hostile contact. Rejection retains current care; successful positioning
remains an assignment, not verified escape completion. Ordinary group tactics
and generic draft/attack routes do not implicitly suspend clinical care.

`/api/v1/combat/state` exports `care_retreat_pawn_ids` only for the exact current
native escape Job instance and actor. Ordinary work, care, rest and undrafting
cannot take that actor before the move finishes; another doctor can still help
the abandoned patient. A later unrelated Goto is not owned. This process-local
ownership does not persist through a full RimWorld restart. Rejected identical
escape routes use the existing native retry memory; a changed exact patient/job
binding or material danger permits reconsideration.

`/api/v1/society/context` additionally exports `medicine_catalog` with each
stocked medicine type's native allowed ceilings, potency and maximum quality, plus
condition immunity applicability and actual tend quality/timer. Raw stock is
not proof of safe access or use. All ceilings remain visible; proposals omit
changes that have no present treatment or scarcity benefit. Real scarcity can
still expose a harmful lowering choice with its patient-death risk stated.
Medical defer memory lasts until both 120 real seconds and 30000 game ticks expire
unless clinical danger, permitted stock or another meaningful opportunity changes.

Already observed rest does not queue another LayDown. Only the selected recovery
priorities are configured. Existing patient feeding, rescue and tending retain
their actors; emergency temperature maintenance does not grant ordinary hauling
or generator-refueling permission to a recovering worker. An exposed drafted
Goto is preserved against generic undraft preparation until it reaches safety.

## Verification and limits

- 1204 Python tests passed: 30 new regressions/source contracts and four updated
  earlier expectations that had authorized generic care cancellation.
- Native Release-1.6 build: 0 warnings and 0 errors.
- Offline API inventory: 308 registered routes, no missing literal calls or
  duplicate routes. No running API was contacted by that inventory.
- Terminal save XML 308589 verified on disk 15:10:53 UTC; RimWorld exit 15:10:55 UTC.
  No game, autonomous worker or new colony was launched for validation.

The last survivor's Medicine 0, low tend quality, pain-related break and immunity
lag remain real clinical constraints. Code fixes do not retroactively change
the outcome. The precise trigger of the first insect attack and a single
pre-autonomy loading NullReferenceException without an original stack are
unresolved evidence questions. Neither is established as the cause of all
deaths. Escape completion, sustained warmth, treatment improvement and survival
must be assessed in a later user-authorized game run.

## Live collection follow-up

The next user-authorized random landing exposed a context-collection omission:
native `/combat/state` included `care_retreat_pawn_ids`, but Python's explicitly
constructed snapshot omitted it. The new colony was saved and technically paused
at tick 16077; the current game, colonists and memory were retained. Forwarding is
now covered from actual server-shaped JSON through collection to medical/combat
ownership, including malformed IDs and IDs from a different map. The updated
suite passes 1206 tests. Native code did not change in this follow-up. The earlier
offline checks used already constructed snapshots and did not catch this boundary.
