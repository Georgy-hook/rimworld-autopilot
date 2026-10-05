# Professional inspiration contract audit — RimWorld 1.6

## Primary evidence

The paused colony loaded Core, Royalty, Ideology, Biotech and Anomaly, plus Harmony/RIMAPI. Odyssey was not loaded. Recursive inspection of the installed Data tree found eight InspirationDefs, all in `Data/Core/Defs/InspirationDefs/Inspirations.xml`; Harmony and RIMAPI supplied none. The runtime endpoint nevertheless enumerates **loaded** `DefDatabase<InspirationDef>.AllDefs`, including future mod definitions, rather than treating eight names as a complete API catalog.

Installed assembly inspected offline: `C:/Program Files (x86)/Steam/steamapps/common/RimWorld/RimWorldWin64_Data/Managed/Assembly-CSharp.dll`. Decompiled references were saved outside the repository in `work/inspiration-audit-20261005`. Source classes: `Inspiration`, `InspirationHandler`, `InteractionWorker_RecruitAttempt`, `WorkGiver_Tame`, `WorkGiver_InteractAnimal`, `QualityUtility`, `TradeDeal`, `SurgeryOutcomeEffectDef`, `SurgeryOutcomeComp_Inspired`, `SurgeryOutcomeComp_Factor`, `Bill`, and `Pawn_JobTracker`.

A secondary mechanics cross-check was [RimWorld Wiki: Inspirations](https://rimworldwiki.com/wiki/Inspirations). Installed definitions and assembly were authoritative where online claims differed.

| Loaded def | Observed native semantics |
|---|---|
| Frenzy_Work | Timed work speed factor 1.8 in installed XML |
| Frenzy_Go | Timed movement speed factor 1.4 |
| Frenzy_Shoot | Timed shooting accuracy offset 8 |
| Inspired_Trade | Trade improvement offset .18; `TradeDeal` consumes only after `actuallyTraded` |
| Inspired_Recruitment | Next qualifying recruitment succeeds; unwavering loyalty is excluded; ReduceResistance is not that recruitment interaction |
| Inspired_Taming | Guaranteed next actual tame interaction; consumed by the attempt; minimum Animals skill, food, reservations and reachability still apply |
| Inspired_Surgery | Applicable native surgery outcome multiplier; installed inspired comp excludes mech patients; `PreApply` consumes only an applicable inspiration; minimum failure remains |
| Inspired_Creativity | Actual quality generation adds two quality levels, capped at Legendary; consumed at quality creation, including qualifying furniture/crafts/art |

Timed definitions expire at their loaded `baseDurationDays` (eight days for these installed defs). Runtime stat factors/offsets, loaded descriptions and active remaining ticks are exported. Unknown mod definitions have unknown consumption guarantees; their descriptions and stat modifiers remain available for inspection.

## Causal defects

Taming selected the colony's highest Animals skill, computed an unused inspired flag, then placed a designation and changed generic Handling priority. That did not bind the desired inspired handler to the desired animal. Production exposed eligible worker IDs but chose no worker and created an unrestricted finite bill. It lacked quality-bearing product/value/work and quantitative per-material ingredient context. An inspired artist could therefore finish a cheap competing order rather than the selected valuable affordable item. Profession direction context did not show inspirations or expiry.

## Implemented contracts

- Separate `/api/v1/inspirations/context`, `/taming`, `/recruitment` observations and exact `/tame`, `/recruit` orders. Endpoint failures are independent; successful empty active context clears old normalized inspiration facts.
- Inspiration identity is an opaque token attached to the actual native Inspiration object using a weak table. Tick/age drift does not replace it. Reload, expiry, consumption or a new instance requires reconsideration, not a permanent failure latch.
- Taming observes exact animal/handler pairs, native interaction skill/readiness, actual food source/count, pen readiness, effective tame stat, value/products, worker's current job and walking distance. Observation creates no designation and never invokes a taming interaction. Execution revalidates identity and native readiness, then uses the ordinary `WorkGiver_Tame` job for that exact handler/animal. Failed new designation is removed. No automatic Thrumbo/megasloth preference.
- Observation work is bounded: at most eight available handlers, a union of sixteen valuable and sixteen nearby animal targets, and 128 pair previews. This is a candidate budget, not a claim that every map animal was considered.
- Producers compare quality-bearing recipes, normal abstract market value for the actual material, native adjusted ingredient requirements and reservable stock, work amount, eligible worker skill/speed and inspiration expiry **before** selecting the recipe. Quality outcomes remain uncertain; a rare-resource masterpiece is not forced.
- The selected finite vanilla bill is restricted to the selected producer. For a creative quality-bearing order, the native scanner must assign the exact bill and `CurJob.bill` must confirm it. A queue-only outcome does not establish the advertised creative opportunity. Failure removes the new bill or restores the reused bill's repeat count, suspension, index, pawn/slave/mech policy and ingredient search tick; only the newly attempted queued job is removed. Autonomous resetting occurs only after acceptance; inspired autonomous quality promises are rejected.
- No preview calls `QualityUtility.GenerateQualityCreatedByPawn`, performs RNG quality generation, executes surgery outcome hooks, trades or tames. Value shown is a normal-quality estimate, not an exact future sale price or promised Legendary outcome.
- Surgery details expose actual native inspired-comp applicability and multiplier for the exact patient/recipe/part/doctor. Selected inspiration identity is checked before bed/bill mutation. Mech exclusion is explicit. Expiry permits reconsidering ordinary surgery or deferral without a failed-option latch.
- Trade compares the effective negotiating stat, which already includes the loaded inspiration modifier. It now exposes inspiration/expiry and guards the selected negotiator identity before opening a transaction. Preview does not consume inspiration.
- Profession directions expose relevant active work/movement/shooting, art, animal, trade/recruitment and surgical opportunities. Runtime unknown inspirations remain in the profession context. Existing urgent care, eating, exhausted/critically hungry actors and active production are protected by native execution checks.
- Per-pair accepted/failed/unknown memory is bounded and JSON-safe, with a 60-second recovery floor and game-tick/map reset. A lost POST acknowledgement reobserves the exact actor/target job; unknown outcome suppresses only that pair. New target/inspiration identity bypasses it immediately.

## Verification and limits

`tests/test_inspirations.py` exercises real Python prepare/choice/execution functions with fake native observations: eight-cycle accepted taming and recruitment, persisted response/job state, 60-second failed-pair recovery despite fast ticks, new pair and tick rollback, lost-ACK job readback, expiry/new-session reconsideration, independent endpoint failures, native eligibility authority, all eight/unknown profession contexts, and production acceptance followed by a distinct simulated completion observation. Cached Laya tokenizer tests inspect actual compared states at every recipe stage within 312 tokens, including inspiration before the worker stage. Surgery tests compare applicable/inapplicable metadata and verify expiry rejects mutation without auxiliary priority changes.

These are offline contract/replay tests, not Unity pathfinding, actual taming probabilities, measured crafting completion or long-run survival evidence. Native compilation and paused-game API checks belong to parent integration. Stock observed as reservable is not a material reservation for an unstarted bill; pending bills are explicitly exported and costs warn about competing commitments. Assigning one exact bill starts the selected opportunity but cannot guarantee that inspiration will outlive a long craft or future interruptions.
