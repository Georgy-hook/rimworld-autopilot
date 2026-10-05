# Thermal facts in colony attention prompts

The archived observer log records the last 3x request at 09:04:34.384512 UTC
and the first 1x request at 09:04:38.401352 UTC on 2026-10-05. The old .5
thermal guard reacted; installation mismatch is not the diagnosis.

Current source replay of the archived baseline (tick 5485, -7.36 C,
Hypothermia .068 on three pawns) offers unlock supplies, then heated shelter
once the next hypothetical observed stock is unlocked. These offline reads
and hypothetical project fixtures did not execute construction in RimWorld.
The hypothetical 18-piece project fixture is not proof that the current
shell is completed or survivable.

The remaining prompt defect was factual truncation: final action comparison
clipped the attention facts JSON at 64 tokens. Temperature came after food,
while thermal severity and native stage were absent. Archived action prompts
for butcher and sleeping spots end before the outside temperature value.

`attention_facts` now carries a bounded `care_risks` block containing maximum
observed severity/stage per Hypothermia/Heatstroke, outside temperature,
roofed sleeping places, temperatures of observed fully roofed bed rooms,
food level/meals, maximum bleeding, downed count, threats and home fires.
Both `dead` and `is_dead` exclude a pawn from the protected care aggregate. Unobserved
roofed bed room temperature remains `unverified`. Stage labels are not parsed.
This block contains no whole health records or assumed completed heating.

The consequence prompt preserves this block as structured facts, reducing
long option prose before sacrificing measured hazards. Nonthermal callers
retain their existing packing. This changes model-visible context, not
eligibility, executor behavior, game speed or decision cadence.

Regression uses the cached Laya tokenizer without loading model weights,
actual `fit_model_context` and `ask_laya_choice` with four shelter/food/care
choices through both narrowing rounds and the final comparison, two thermal
conditions, concurrent hostiles/home fires and oversized explanatory text. It verifies
stage, food, bleeding and unresolved roof evidence survive the 312-token
state budget. Additional tests cover missing roof evidence, dead pawns and
bounded aggregation across a large roster.
