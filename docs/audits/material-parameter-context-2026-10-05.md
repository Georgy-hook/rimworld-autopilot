# Goberium material choice and rest replay — 2026-10-05

## Observed failure

Goberium Coalition was generated once on random tile 55904 (world seed
`laya-thermal-progress-20261005`). The baseline is tick 40. Autonomous speed 3
started at 10:03:28 UTC. At 10:09:31 the director was stopped and the observer
held tick 143482. All three founders were alive, upright and fed. This is a
technical pause, not a colony death or a completed survival benchmark.

The shelter had 22 completed walls, a door and three beds. Its last frame,
Wall #20213 at (145,128), needed four WoodLog. Loose wood was zero, steel 776,
and there were no roofed sleeping places. Native plant observations offered a
SmashedStump as well as living Saguaro and Drago; the paused replay conservatively
estimated the damaged stump at three wood. Repeated
`harvest_nearby_trees` selections ended in `tree_type=defer`.

The detailed plant comparison showed no decision facts. The broad colony
description was clipped before the actual shortage and roof state. Root
attention alone therefore did not give the final plant choice the evidence
needed to compare the cost of preserving plants against an unfinished shelter.
The following worker question also ran after declining to harvest anything.

Native project replacement already supported a validated material change,
but Python exposed it only for research benches. The existing frame therefore
had neither visible measured demand at the leaf nor an offered steel alternative.

## Repair contract

- Legacy parameter questions receive a separate measured facts record. Small
  explicit records remain complete in every bounded comparison; prose is
  shortened before their fields. Unknown observations remain unknown.
- Timber decisions receive the actual shell shortage, roof and temperature
  state, observed cutting precepts, and available material alternatives. A
  ritual named TreeConnection is not treated as a cutting prohibition.
- A defer ends the timber branch before worker selection and is persisted with
  finite game and wall-clock backoff. Changed resources, alternatives or a new
  serious thermal risk permit earlier reconsideration.
- Material replacement is limited to unfinished unaffordable walls/doors with
  an affordable compatible alternative. Original identity is rechecked; the
  native endpoint validates placement and full replacement cost before
  cancellation. Native refusal must preserve the original project.
- Harvest batches cover the actual gap or a measured fuel reserve, with an
  eight-plant maximum. Designated wood is counted against the same demand.

## Independent rest loop

Kitty had nonlethal Asthma at arrival. An unchanged rest refusal reappeared when
normal `in_bed` and food fields changed. The rest-specific persisted projection
now compares actual clinical deterioration and newly available assistance.
Sleeping, eating, changing ordinary jobs and improving symptoms do not restart
the question during its finite floor. New patients, bleeding, treatment need,
downed state and serious thermal stage changes remain actionable. Native
nonlethal asthma with immunity zero is not an immunity race.

Eight-cycle persisted replays exercise actual Kitty conditions, ordinary
sleep/work transitions, material shortage and observed delivery. Cached model
tokenizer checks verify the facts survive all comparison stages. Such tests
establish contracts; only subsequent game observations can establish completed
construction or long-term survival.

An actual CUDA replay of tick 143482 retained the full timber facts in every
comparison, within the 312-token state budget. The model still chose to defer
cutting; this is not evidence of successful harvesting. Root candidates included
both replacement and harvesting alongside patient rest and survival waiting.
The first root choice was rest followed by defer. Subsequent autonomous choices
must demonstrate whether persisted deferrals allow the other option to proceed.

Final integrated verification: 1004 tests pass. Read-only QA confirmed native
pre-cancellation validation and replacement readback; failed materials retain
separate retry records to prevent Steel/Silver ping-pong. Cold rooms without a
heater and older snapshots without ingredient counts retain their supply path;
unknown demand is labelled unknown rather than silently treated as zero.

The final actual-model sequence kept the game frozen at tick 143482. First,
Laya deferred Kitty's rest. After locally persisting only that defer and
recomputing real candidates, Laya selected `replace_blocked_shell_material`
and `20213|Steel`. All HTTP POST operations were forbidden in this replay.
It confirms movement to another available action, not construction completion.
