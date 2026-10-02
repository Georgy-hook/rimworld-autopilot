# Laya as colony director: capabilities and limits

For the 0.0.7 domain contract, bounded consequence comparisons and observed
outcomes, see [Modular decisions](MODULE_ARCHITECTURE_0.0.7.md).

This project is an experiment in giving Laya the strategic decision, while the
RimWorld bridge supplies observations and executable affordances. It is **not**
yet a reliable autonomous RimWorld player. Do not use an irreplaceable save to
evaluate an untrained checkpoint.

## What Laya actually does

The [official model card](https://huggingface.co/convaiinnovations/laya/blob/main/README.md)
describes a non-autoregressive decision model. `predict(state, questions)`
returns typed `choice`, `score` or `noul` answers and a distribution over the
options supplied in each question. It does not generate text, invent an API
call, perform long-horizon search internally, or expose a textual chain of
thought. Its `action.act_probability` is explicitly reported as unusable by
the authors; we do not use it to control the colony.

The installed English checkpoint has a 512-token question window, with up to
192 tokens reserved for the question and options. A 12,000-character JSON
snapshot was therefore not a meaningful bound: the game state could be
silently cut before Laya saw the important evidence. `model_decision_context`
now puts current needs, risks, course and recent outcomes in a compact state;
`fit_model_context` checks the *actual tokenizer* and explicitly compacts
oversized context before encoding; an input that still cannot fit is rejected.
The comparison log records the actual visible state. Exact animal, worker, research and building details are
presented only after Laya selects the corresponding operation.

The official model card also says the English base checkpoint is weak on
unseen typed-decision workflows before specialization, that its probabilities
need domain calibration, and that large option sets lose resolution. An actual
local smoke test on 2026-09-23 illustrates the risk: with food 0 and hunger
0.07, the root checkpoint chose `research_power` (weight 0.376) over
`harvest_berries` (0.256), while `wait` had weight 0.368. Adding an explicit
starvation risk sentence did not fix it (`research_power` 0.475). These two
synthetic trials are not a benchmark, but they are enough to rule out claims
that prompt wording alone makes unattended survival reliable. GUI percentages
are *relative option weights*, not probabilities of success.

## Decision boundary

1. The bridge reads live state and enumerates technically executable actions.
   Emergency signals add context and possibilities; they do not force a
   hard-coded build order. Waiting remains an option.
2. Laya chooses an area, operation and only the parameters that operation
   needs. Long lists use a bounded tournament: every candidate appears in an
   actual model comparison before the finalists are compared. This is a
   capacity workaround, not a calibrated search algorithm.
3. The bridge revalidates IDs, prerequisites and target state before execution.
   It may refuse an impossible command, but it must not quietly replace a
   model choice with a different strategic action.
4. Every development decision records the compact state Laya actually saw,
   compared option text, its output distribution and the API result. Recent
   outcomes are fed back as short memory, not mistaken for online learning.

The History page also lets a user select the best action from that cycle's
recorded feasible options. Corrections are stored locally in
`laya-feedback.jsonl` and included in a diagnostic export. This is labelled
data for a future training run; clicking the button does **not** change the
live checkpoint's parameters or retroactively undo an in-game action.

Two general affordances are now read from the active game's definitions:
`select_research` exposes all currently startable projects (including mods),
and `set_work_priority` exposes loaded work types, eligible people and priority
levels 1–4. Construction also offers a bounded procedural design space: Laya
chooses the building's purpose, wall material, entrance side, house character
where relevant, and a generated layout. The planner reads the live building
catalog for fixed ingredients, component costs and compatible stuff categories,
and estimates floor materials. Only plans that fit currently known stock and
have no duplicate/out-of-bounds blueprint anchors are shown. A stored seed
slightly varies the doorway position while keeping the
same selected design reproducible. This is deliberately not a fixed victory
route. Other actions, especially construction placement, combat, events and
caravans, still contain authored plans and filters. The present system can
create new **combinations** of available actions, not truly unanticipated
atomic gameplay mechanics. Multi-cell and modded building compatibility still
requires validation by RimWorld's engine; no live-game construction result is
claimed by these generator tests.

Combat decisions now receive a compact, tokenizer-checked force summary rather
than a verbose snapshot that silently drops most of the squad. Staging or
distant enemies no longer erase attack and positioning options: Laya may choose
to rest, observe, or act, with the danger of each in context. If she chooses to
stand down while raiders are still staging, the colony decision loop can keep
asking Laya about work; it stops that development path as soon as the enemy
advances or the fighters are drafted. Tactical execution still has a catalog
of authored plans and uses engine-side path/target validation. This change
does **not** prove combat competence; a smoke run only verified that real Laya
inference and the resulting command plan execute without an exception.

## What is required for a stronger Laya director

- Replace remaining authored action families with composable, API-backed
  affordances: inspect a live building/recipe/zone, select target/material/
  placement, preview effects, then execute. Preserve exact validation and
  reversibility; no arbitrary code execution from a model answer.
- Unify development, combat, event and expedition decisions around one bounded
  world model and persistent intent, rather than letting independent loops
  pre-empt one another. Tactical control must still react faster than
  construction decisions.
- Collect labelled decisions and outcomes from disposable saves, human
  corrections and repeatable scenarios. Split by colony/map into training,
  validation and held-out test sets. Do not train on the held-out fights.
- Fine-tune Laya for RimWorld decisions using the [authors' training
  approach](https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb),
  then calibrate each question type/option-count bucket on a separate held-out
  slice. Evaluate survival, food security, injury, construction completion,
  strategic regret, novel mod content and repeated-seed battles. Do not
  mistake a sharper output distribution for improved decisions.
- Only after such evaluation should unattended play be described as reliable.
  Until then, retain save backups and the ability to pause or stop the agent.

This architecture keeps Laya as the chooser wherever choices exist. It also
states its hard boundary plainly: a classifier cannot create a new action
outside its schema without a separate proposal mechanism or training.
