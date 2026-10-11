# Affordances

`colony_affordances` registers ability, interaction and subcore-scanner work;
`colony_sessions` completes an active native targeting stage before ordinary work.

## API contracts

| Endpoint | Transport and response |
| --- | --- |
| GET `/api/v1/affordances/context` | Query `map_id`; response `available`, `abilities`, `options`, `target_count`, `missing_adapters`. |
| POST `/api/v1/affordances/order` | JSON `map_id`, `kind`, `pawn_id`, `target_id`, optional `ability`, `label`. Response object `applied`, `reason`, `completion=unverified`; menus may report `job_changed`, `choice_opened`. |
| GET `/api/v1/affordances/targeting` | Response `active`; when active: `session_id`, `map_id`, `source`, `effect_identity`, `effect_label`, `effect_description`, `effect_cost`, `caster_facts`, `options`, `limits`. |
| POST `/api/v1/affordances/targeting` | Query `session_id`, `map_id`, `target_id`, `x`, `z`, `cancel`; response `applied`, `reason`, `completion=unverified` for selected target. |

Options bind `key`, `kind`, `pawn_id`, `target_id`, `ability`, `label` where
applicable. Descriptions, worker/target clinical facts, costs and collateral are
comparison evidence, never arbitrary API command fields. Snake case serialization
and the normal API wrapper apply. The client unwraps `ApiResult.data`.

Targeting options expose target identity, cells, definition, hostility, downed,
health/bleed, visible clinical stages, roof/fire, nearby hostiles/allies and actual
ability-radius allied count. `actual_cost` includes target-dependent psyfocus,
heat and remaining charges. `caster_facts` binds identity and clinical readiness.
For scanner commands `scanner_facts` binds native state, occupant ID, selected
pawn ID and required/remaining ingredient counts. Fabrication countdown is display
information. Ability order costs now include actual remaining charges (`-1` when
unlimited), rather than a charges-used boolean.

## Native lifecycle and decisions

Native eligibility excludes care/baby/lesson/deathrest work, dead/downed/mental
actors. Interactions additionally exclude drafted workers, forbidden targets,
unsafe gas, nearby threats and unsafe routes. Ability queue/disabled/target/range,
psyfocus and entropy checks come from the native ability. Catalogue entries do
not guarantee beneficial effects or completed jobs.

Choices stage mechanical purpose, target and worker. Ambiguous equal-label native
commands are deferred. Source/target identities and evidence are refreshed before
an order. Native execution regenerates menu/gizmo legality. Scanner cancellation
may open a destructive native confirmation; invoking it is not brain destruction
or completed production.

Targeting has a bounded static generation counter. Harmony patches all five
installed public `Targeter.BeginTargeting` overloads and `StopTargeting`. A reused
Verb, stop/reopen or destination second stage gets a new generation. No history
of sessions accumulates. The integer counter wraps only at `int.MaxValue`.
This token is process-local and is invalidated by native lifecycle, not saved as
campaign state. A current cancellation checks native map/session and remains
explicitly selectable even with no feasible targets.

After model targeting choice, sessions reread the targeting context and bind
session/map/effect/caster/target, costs/charges, collateral and clinical stages.
Ordinary movement of a target pawn is allowed because its ID follows it. Health
and bleeding drift up to 0.02 is tolerated; stage/downed/hostility changes and
changed allies/costs require a new decision. A cell remains bound to coordinates.
Cancellation has the native identity guard without unnecessary clinical comparison.
Native `Valid` performs legality again immediately before invoking the callback.

## Retry and loop audit

Affordance defer records the actually compared semantic options for 2500 game
ticks, allowing new actors/targets/effects immediately. Accepted orders dwell for
2500 ticks by stable identity even when their own charge/cost changes. Stale,
rejected, malformed response and GET/POST failures record 150-tick retries with a 30-second real-time minimum for
that selected state fingerprint. Material stage/collateral/cost/urgency changes
can reopen defer/failure; ordinary health noise and movement do not. Expired,
future, malformed and legacy cooldown records are pruned, and the schema round
trips through JSON.

Active targeting uses a single bounded retry record with wall-clock delays
1, 2, 4, then at most 5 seconds, so paused games cannot spin model/order calls on
an unchanged rejection. Fresh native observations remain available; new sessions
or meaningful actor/target/effect/collateral/cost/clinical context bypass retry.
Moving pawn anchors are not treated as a new failed cell decision. An empty
catalogue still permits explicit cancellation; native cancellation itself has no
retry restriction. Initial GET transport errors retain the central scheduler
retry policy. A target POST exception records its selected pending retry before
propagating to that scheduler.
Unknown blocking native windows are recorded and
wait quietly rather than automatically dismissed.

## Verification limits

The 2026-10-07 quest correction adds a shared `interaction_pending` record for
accepted menu jobs: target plus effect label, independent of actor, with minimum
120 real seconds and 30000 game ticks. Ending-site interactions consult the same
record. This extends menu retry protection beyond the existing per-actor dwell;
new targets/labels remain available. Nested comparisons now protect current food,
clinical facts and chosen ending. See the [quest audit](../audits/quest-prompts-native-contract-2026-10-07.md).
The repeated monolith reassignment is tested offline; real investigation
completion after installing the change remains unverified.

Offline `tests.test_affordances` and `tests.test_progression` pass together (61
tests at this revision). Regression tests prove Python transport freshness,
clinical drift, moved pawn identity, changed allies/stage/cost/generation,
scanner occupant/state/ingredients and last charge. Source assertions bind the
Harmony method selection and new native DTO members; these are not live Harmony
or native cast/save/load proof. Installed ILSpy source confirms all five public
BeginTargeting overloads, StopTargeting, scanner State/Occupant/GetRequiredCountOf,
and public inherited SelectedPawn. No game, live API, model weights, observer,
build or git operation was used in this follow-up.

Target cells are native-valid observed anchors/offsets, not exhaustive map search.
Some callback-based targets expose only the original command cost; permits retain
native favor/cooldown text. Unknown mod effects cannot be inferred from a generic
ability catalogue. The allied radius count does not simulate directional lines,
cover or every effect component. Applied means invocation/queue/choice; only
subsequent native observations prove jobs, health consequences or completion.
