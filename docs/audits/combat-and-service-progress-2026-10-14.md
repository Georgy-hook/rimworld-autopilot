# Combat orders and repeated service work

## Reproduced boundaries

- A short observed target path cannot establish that an immediately available native shot is impossible beyond the path's end. Firing uses actual distance for projectile travel; a zero-distance reposition no longer replaces a shot.
- Holding cover has a bounded defensive move. It does not inherit the long pursuit used by an explicit advance or interception plan.
- Combat responses distinguish a changed job/draft state, a preserved exact attack or moving job, and no change. Readback includes current jobs. An acknowledgement, queue or preserved job does not prove a shot, hit or win.
- A distant animal corpse alone does not justify another butcher station when a station or project already exists. Delivery and processing need separate observations.
- Before unforbidding selected corpses, reread current things and intersect exact IDs. Missing targets are deferred without broadening the selection. A race returning a specific not-found error is retained as a changed target.
- Animal-carcass storage uses fresh native dry-foundation, mountain-roof and stockpile-availability grids. A missing or conflicting footprint defers placement with both real-time and game-time retry limits.
- Native roster-eligible food constrains generic perishable nutrition. Generic corpse edibility cannot expand the human reserve beyond that roster's food policy.
- Drug-policy changes use both real-time and game-time commitment. Switching to another profile does not itself reopen the same decision; materially changed clinical facts can reopen review. Existing medicine, addiction, genetic and protected-care guards remain required.

## Verification

The full Python suite passes 1,498 tests, including 14 new combat/service regressions. Nineteen native boundary suites pass under PowerShell 7; the intercept suite now contains 24 assertions. The release native build succeeds with no warnings or errors. The offline API audit finds all 315 registered routes, with no missing literal routes or duplicate registrations.

PowerShell 5 could not compile the modern C# boundary fixtures; those environment failures were retained and the suites were rerun under the configured PowerShell 7 runtime. Deliberately injected CUDA test failures exercise fallback paths and are not observations of a live GPU failure.

The tests establish these boundaries. They do not establish sustainable food production, completed refrigeration or maintenance, trading income, a rescued captive, survival or victory. Private campaign data, saves, logs, photographs and reports are excluded from this document.
