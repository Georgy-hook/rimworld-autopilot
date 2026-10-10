# Survival recovery audit — 10 October 2026

The completed cold-biome run exposed several blocked survival choices. Recorded observations were checked offline; the finished campaign was not replayed or repaired in place.

## Changes

- A current or remembered Research/Mining assignment can yield to feasible food work during an immediate food gap. Another food task, protected care, eating and disease recovery retain their existing checks.
- Selecting a food worker lowers competing priority-1 hauling and cleaning, as well as routine development work. Doctor and Firefighter priorities remain protected.
- Required timber can be sought within 90 cells when no safe mature timber remains within 45 cells. Batches stay bounded to eight plants; the model sees travel distance and can defer. Existing danger checks and fresh plant validation remain in effect.
- Animal patient feeding requires a completed compatible current bed. A LayDown job alone does not establish this; exposed downed animals retain rescue choices.
- Housing decisions compare sharing a measured comfortable existing room with constructing a separate building. Shared spots use fresh native revalidation; placement does not prove arrival. A separate single-pet shelter is 5×5, and a known unsafe temperature forecast removes unheated proposals.
- Both thing observation mappers expose the same actual corpse freshness, identity and butcherability facts. Human, rotten and unknown corpses are not counted as fresh animal food.
- Building and construction-project observations expose native occupied cells. Bed and shelter planning uses these cells to handle rotated furniture.
- A hungry but mobile armed hunter with malnutrition can be considered for an ordinary native hunting plan. Bleeding, serious incapacity, exhaustion, disease care, violence restrictions, protected jobs, weapons and target/position feasibility still block unsafe actors. The model receives malnutrition and capacity facts and chooses whether to hunt.

## Verification

- 1373 Python tests passed, including survival regressions and installation tests.
- Offline route audit: 313 routes, no missing literal bindings or duplicate routes.
- Native boundary checks passed: food mapper (7), hunting recovery (9), husbandry (8), thermal transfer (8), predation intent (6), instant construction (33).
- RimWorld 1.6 native assembly compiled with no warnings or errors.
- Cached Laya inference on the recorded late starvation observation selected timber and a worker with both option orders. On the recorded housing observation, the isolated housing parameter decision selected the existing warm room with both option orders. Transport acknowledgements were simulated; no game commands were sent.

The native Unity rendering crash has no established causal link to Laya/RIMAPI and has no claimed fix. Offline checks establish available choices and contracts; they do not prove completed work, successful defense or colony survival. A new campaign is the next live check.
