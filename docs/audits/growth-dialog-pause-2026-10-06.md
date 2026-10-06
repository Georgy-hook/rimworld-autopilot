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

Native build and live installation evidence are recorded separately after
verification. Offline tests alone do not establish live window closure,
continued ticks, or colony survival. The paused current progress was preserved;
this incident requires no save rollback.
