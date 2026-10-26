# Combat control candidate — 26 October 2026

This is preparation for **0.0.9**, not a release or a claim of reliable raid
defense. Source and regression tests are committed separately from the packaged
normal assembly so its informational version can identify its source commit.
Private saves, campaign history, runtime state and raw test logs are excluded.

## Changed behavior

- Selected combat control has finite game-time and real-time leases tied to the
  actual actor, map and owned native job. Deferred geometry retains accepted
  partial actions and explicit readback instead of redispatching a whole plan.
- Movement startup distinguishes an owned pending Goto from an actual moving
  path. The common withdrawal executor records the same receipt used by that
  review. Arrival, a selected shot and a launched projectile remain different
  observations; old arrival receipts cannot complete a reopened bound.
- Covering fire remains bound to the exact moving ally and enemy until arrival,
  expiry, changed ownership or an escape/clinical safety condition. Temporary
  inability to launch the next shot does not automatically free the gun for a
  different mover. Shot geometry and friendly-fire checks remain independent.
- Melee fallback proposals translate the observed formation instead of drawing
  every gun into a common small rally. A ranged rally that has never admitted a
  move cannot veto an otherwise checked independent move. Optional range-post
  departures consider observed danger to the group and actual remaining guns.
- Current/queued feeding, tending, rescue, carrying and medical bills retain
  their protection. Caregivers can meet food/rest needs and return to native
  treatment. Production bills are not mistaken for patient care.
- Scoped native path queries return detached observations, release owned pooled
  paths, and leave borrowed game paths with the engine. Live controller reviews
  retain their eight-query limit and expose incomplete reviews explicitly.
- Interception and contact defense retain target identity, native movement/aim
  windows, exact job readback and violence/medical eligibility. Current and
  predicted friendly lanes use the native projectile rules; enemy behavior,
  hits, damage and battle outcomes remain native.

## Verification and limits

The final candidate passed **1,663 Python tests**, **61 native boundary suites**
and **1,049 numeric assertions**. Normal and explicitly opted-in laboratory
assemblies compiled. Laboratory controllers, fixture mutation routes, clock
hooks and diagnostics are excluded from normal builds.

The focused investigation used only the original rush202 and ranged204 cases:
six corrected candidate pairs, twelve native battle cases, with failures retained.
The final frozen candidate cleared both in the same prospective pair. Rush had
one defender downed and fifteen native Tend completions; ranged had two downed
and seven Tend completions. All original defenders remained alive and spawned,
with bleeding stopped and no kidnapping or allied damage in that final pair.
These are stabilized victories, not clean victories without downing.

The recorded pooled-path acquisitions and releases balanced with no outstanding
owned paths. Bounded semantic action-error review found no HTTP/action errors
in the retained decision windows. New response-write `IOException` messages from
remote connection resets remain a separate transport follow-up; successful case
completion does not make the transport handler error-free.

A single successful pair does not estimate a stable win rate, establish an
isolated causal effect for every policy change or qualify other raids. Fixed
initial saves constrain starting conditions, not later rendering/RNG and dispatch
timing. No additional eleven-case qualification series was run after this pair.
Ordinary colony survival, deployment and a complete ending remain separate gates.

## Reproduction

Run the Python suite from the repository root:

```powershell
python -m unittest discover -s tests
```

Run each `tests/native*_boundary.ps1` in its own PowerShell 7 process, since
several suites compile isolated C# types with shared test names. See the
[native laboratory instructions](../../tests/native_combat_lab/README.md) for
the explicit build opt-in, disposable world guards and interpretation rules.
Do not use an ordinary colony as a fixture or weaken the evaluator to obtain a
passing outcome.
