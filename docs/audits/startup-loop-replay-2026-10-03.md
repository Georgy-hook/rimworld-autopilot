# Startup loop incident and sequence verification — 2026-10-03

Candidate: 0.0.7, source starting at `50d4a19`. This supersedes the startup
readiness inference drawn from the 2026-10-02 API audit. That audit's unit and
route checks did not exercise the real founder equipment decision cascade.

## Observed failure

Requader, random tile 40061, began at 06:09 UTC. After equipping Alyssa with a
revolver, Laya repeatedly selected `equip_colonists` for already-armed Alyssa
and a loose bolt-action rifle. The parameter chooser used all capability
equipment plans; the legacy executor accepted only unarmed founders. It returned
`applied:false`, empty assignments and empty responses. The director cleared
failure memory whenever execution did not throw. The same action remained
eligible until combat interrupted development; interruption was not recovery.

The colony was saved and paused at tick 216457 with all three colonists alive.
The director, observer and periodic monitor were stopped. Hourly automation
was paused. The regression work made no subsequent gameplay mutations.

## Repairs and reviewed evidence

| Failure sequence | Correction and verification |
|---|---|
| Candidate, parameter choice and executor disagree about eligible weapon recipients | Founder arming projects one shared capability plan. Exact model-selected pawn and weapon reach the native atomic Equip handler; no implicit auto-equip branch in armament research. Actual startup fixture covers armed Alyssa, unarmed Dawn and pacifist Garrett. |
| Empty/unknown response erases failure memory | Explicit command outcome classification. Unexplained no-effect calls retain retry memory across persistence; candidates are filtered before focus rules. The next full director cycle retains construction. |
| Accepted/rejected response confused with completed work | Endpoint-specific acknowledgments, stateful readback for bills/priorities/heating and separate pending job observations. Tests include false/string/empty replies, partial placement and lost responses with actual observed effects. |
| One subject blocks an entire category | Production dwell and downstream deferral are scoped to selected targets/recipes; society and resilience preserve other patients. New subjects are immediately eligible. |
| Repeated hauling, feeding or rescue interrupts a job after a timer expires | Native `active_orders` expose worker, target and job. Context and POST guards exclude an active same-target job; fresh Python checks cover races during model inference. Completion/interruption removes the live exclusion. FeedPatient targetB and Rescue targetA verified against installed game code. |
| Impossible butcher site suppresses useful food alternatives | Candidate requires a safe native-approved local site; execution revalidates that exact site. Failed/unknown bill reads do not mean missing bills or success. |
| Maintenance promotes every worker or repeatedly assigns priority 1 | Routine maintenance checks the best suitable worker's actual deficit; explicit urgent recipient selection remains possible. Readback confirms the change. |
| Native configuration/targeting repeats without a changed session | Persisted bounded transition observations separate accepted, rejected and unknown results. Meaningful readiness changes reopen choices; ordinary movement/health drift does not. Nonmodal waiting yields to colony work. |
| Failed events or rescue waits consume development cycles | Explicit scheduler blocking contract. Failed event work and ongoing release jobs permit other work. Unacknowledged letters remain available after retry rather than marked handled. |
| Rejected combat tactic repeatedly wins the same choice | Exact command/target/fighter retry history presents alternatives after repeated rejection; new meaningful threats bypass the old history. Native DTO acknowledgments are checked without inventing an `applied` field. |

Three GPT-6.1 Sol agents worked on disjoint modules using proposal, parent review,
implementation and QA. Parent review rejected revisions that hid all workers,
treated continuous bleeding drift as new readiness, or required an `applied`
field absent from the native combat DTO. Those were corrected before acceptance.

## Mandatory sequence checks before the next launch

Run the ordinary suite and these actual preparation/selection/execution sequences:

```powershell
python -m unittest discover -s tests -q
python tools/audit_api_contracts.py --output api-contracts.json
python tools/replay_startup_decisions.py --device cuda --output startup-replay.json
```

The sequence tests cover eight or more unchanged cycles, persisted/reloaded
memory, unrelated drift, newly available targets, denied/unknown acknowledgments,
accepted but unchanged native sessions, partial success and response loss. The
startup fixture originates from the actual first empty equipment decision.
Transport doubles implement resulting observations instead of returning arbitrary
success for every POST. Candidate/parameter/executor stages are not stubbed away.

The actual local Laya model on CUDA chose **Dawn → bolt-action rifle**, then
**build_sleeping_spots** in the original offline startup replay. After generated
pawn names were redacted in the committed fixture, it deferred equipment and
also moved to **build_sleeping_spots**. Both left the reported loop. The first comparison was
restricted to the reported failing equipment action; the next comparison used
all available development candidates. Only an offline equipment transport double
was used. This demonstrates exit from the reported loop, not construction or
survival in RimWorld.

Build the native C# assembly after source commit, verify its provenance, and
verify installed Python/native hashes before the next gameplay run. A route
inventory or passing test count alone cannot close a gameplay defect.

Final offline gate: **840 Python tests passed** (38 more than the pre-launch
802), including the recorded startup and repeated-cycle scenarios. The native
build completed with zero errors and warnings. Route inventory: 297 registered,
236 literal client calls and 20 dynamic calls; no missing literal routes or
duplicate registrations. Dynamic payloads require their scenario tests.

## Limits and next runtime gate

This verification closes the reproduced failures above. It does not prove that
every possible modded state or a full autonomous victory is error-free. Ambiguous
network/reservation failures remain recoverable; their scoped delayed retries
must not block unrelated work. Long-term strategy and native job completion still
need the next controlled run of the saved colony. Do not describe that run as
completed while it is paused.
