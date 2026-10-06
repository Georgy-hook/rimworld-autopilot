# Clinical context and waiting — 6 October 2026

The terminal colony lost its remaining residents after starvation, mental breaks,
beating and blood loss. This audit closes concrete context defects; it does not
establish that they alone caused the defeat or that the new build will survive.

## Ownership and model input

`colony_reasoning.attention_facts` keeps bounded aggregate clinical facts for
bleeding, malnutrition and hungry downed patients even without a thermal hazard.
`laya_decisions` preserves this factual unit in the complete short comparison
envelope. The previous protected path required a thermal condition, so an
otherwise severe clinical situation could lose facts during context clipping.

Observed low recreation and mood are supplied as needs, not a probability of a
mental break. During imminent food focus, already feasible recreation schedule,
free-time and recreation-building choices remain available when these needs are
acute. Laya compares their labor cost against food and care; no recreation,
construction or clinical intervention is forced by this change.

`hold_survival` describes unavailable residents, idle people and observed jobs.
Its result says that no new order was issued, and does not claim earlier work
was assigned or finished. Unknown jobs and unobserved completion stay unknown.

No second prediction model or additional model call was introduced. Module
preparation and native execution retain responsibility for feasibility.

## Verification

Five sequence tests cover severe nonthermal needs, recovery and a new dependent
patient; acute recreation choices and their return to ordinary selection;
unknown/nonfinite needs; and truthful waiting as actors become unavailable.
The cached model tokenizer checks the complete envelope for four alternatives
with combined severe food, bleeding, cold and heat facts. All comparison inputs
fit the 312-token limit and retain the bounded factual unit.

The repository-wide suite passed 1174 tests. No live game was resumed with these
changes; correct prompt construction does not prove a correct strategic choice.
