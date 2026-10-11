# Decision context budget — 11 October 2026

A live care comparison stopped the director before inference. The model allows 312 tokens for state after reserving its decision head. Complete clinical facts fit on their own, but repeating five consequence field names for each option exhausted the remaining space. The previous generic exception reached the director's global retry handler, so the observer held the game paused.

## Repair

- Crowded consequence comparisons share a named column list for benefit, risk, cost, inaction and uncertainty. Option identifiers and protected clinical facts remain intact. Ordinary descriptions receive the same bounded allocation for each option; fitting comparisons keep their existing representation.
- If the complete required facts still cannot fit, the comparison raises a typed unavailable-context result before inference. The log identifies its exact question stage, options, state budget and a lower bound on the required tokens. No model choice or game action is fabricated.
- Care, defense-adjacent, event, dialogue and development cycle boundaries handle that result locally, allowing independent cycles to continue through their ordinary validation. Other programming errors remain visible to the global error handler.
- Clinical safety checks, routes, reservations and native execution predicates are unchanged.

## Verification

- 1388 Python tests passed, including seven regressions for crowded care, both option orders, preserved facts, unavailable planning and care, exact question attribution, independent continuation and unrelated errors.
- A private recorded case reproduced the original exception using the installed pre-fix code and the actual cached tokenizer.
- The corrected recorded comparison used 310 of 312 state tokens with the complete clinical facts retained. Actual cached CUDA inference completed in both option orders; the production care cycle also completed. Game orders were blocked during replay.

The recorded prediction is evidence that inference resumed for this case. It is not evidence of completed treatment or survival. A larger clinical record now produces an explicit local unavailable comparison instead of this global retry failure.
