# Growth information modal stalled unattended play — 2026-10-06

## Observed failure

The current colony stopped advancing at tick 2571140 while all four residents
were alive. RimWorld and the Python workers were responsive. A
`Dialog_GrowthMomentChoices` held a forced pause, although its archived growth
letter had already resolved its awards and displayed only OK. The window API
returned no usable buttons. Society correctly excluded the resolved letter
from pending award choices, leaving the director in a quiet native-window wait.
Repeated speed requests cannot release a native forced pause.

The installed RimWorld 1.6 methods `Dialog_GrowthMomentChoices.CanClose`,
`DoWindowContents` and `ChoiceLetter_GrowthMoment.MakeChoices` were inspected.
An archived letter's `MakeChoices` is a no-op. The native OK callback invokes
it, closes that dialog and removes its letter. Unmade award choices must still
use the separate Society selection path.

## Contract changes

- Window observations include `confirmation_only`, actual growth dialog text
  and the localized OK label only when the native close condition accepts and
  no unmade trait or passion choice is bypassed.
- Acknowledgement requires the current top modal's exact type, runtime window
  identity, text and localized label. The engine rechecks eligibility before
  invoking the ordinary OK callback.
- Generic close requests exclude growth windows, including explicit type
  requests. Society award execution closes only dialogs bound to the letter
  whose validated awards it just applied.
- The director verifies that the selected window disappeared. An accepted
  command without observed closure remains unverified and backs off for 60
  seconds. A different window identity remains eligible during that backoff.
- One informational OK is resolved by the existing singleton-choice path
  without model inference. Multiple trait/passion alternatives remain Laya
  decisions; this repair does not change growth rewards or reroll offers.

## Verification

Eight behavioral tests cover scoped localized acknowledgement, subsequent
absence, accepted commands without closure, bounded retries, new identities,
unmade awards, older API observations, ambiguous buttons, and stacked modals.
The complete suite passed 1153 tests. The offline API audit found 308 routes,
no missing literal calls and no duplicate routes.

Native Release-1.6 built from source `dd80168` with zero warnings/errors; package
`ba80742` was installed with matching runtime and native hashes. The game was
restarted in its visible window and loaded the current tick 2571140 save; 21
loading transition ticks reached a verified stable pause at 2571161. No save
rollback or manual memory reset was performed.

The same archived growth letter was reopened through normal History/Messages
UI. The installed API exposed `confirmation_only=true` and one OK. An explicit
generic-close request removed zero windows; a stale identity was rejected and
left the dialog intact. The installed director then invoked the scoped OK,
observed that window disappear, and found no further acknowledgement to issue.
The child's complete observed trait and skill records were identical before
and after; the game remained at the same paused tick throughout this technical
replay. This is positive informational-acknowledgement evidence, not a new
autonomous growth award selection.

Observers started before the director. Autonomous continuation resumed at
11:00:12 UTC. At 11:02:18/tick 2578430 all four residents were alive and upright;
one formerly catatonic patient had actually received food and was doing a bill.
Ordinary combat and colony decisions resumed. Severe malnutrition kept the
observer's emergency speed at 1x; the normal target remains 3x. This short
observation establishes continued simulation, not durable survival or victory.

The new native closure after an unmade award selection remains a source/build
gate rather than a positive live award-selection result. Loading-time
NullReferenceException duplicates and redundant hazard-guard records remain
separate open observations; neither was established as the growth modal's
cause. Hourly observation continued on this same colony.

The subsequent continuation ended in native Game Over at11:48:46 UTC on
6 October. All four final residents died; the outcome and paused observation
are recorded in [the final report](../playtests/Theentbum-2026-10-06.md).
