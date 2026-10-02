# Modular decisions and measured outcomes — 0.0.7

This is an incremental extraction, not a claim that the legacy director has
already been fully decomposed. New domain executors are outside the director.
Its existing emergency sequencing, construction orchestration and event loop
remain in place and continue to require scenario validation.

## Boundaries

```mermaid
flowchart TD
    Game[RimWorld definitions and live objects] --> API[Read-only domain observations]
    API --> Router[colony_modules: observation and proposal routing]
    Router --> Guards[Existing emergency and feasibility guards]
    Guards --> Cards[Benefit, risk, cost, waiting, uncertainty]
    Cards --> Laya[Native typed Laya choice]
    Laya --> Parameters[Target and parameter choices with defer]
    Parameters --> Validate[Fresh Python and engine validation]
    Validate --> Jobs[Ordinary game jobs, bills, policies or commands]
    Jobs --> Memory[Command result and next observed state]
    Memory --> Cards
```

| Module | Responsibility | Main evidence |
|---|---|---|
| `colony_actions` | Legacy vocabulary and overlay labels | Existing action definitions; no execution |
| `colony_modules` | Whitelisted domain ownership, collection status, proposal and execution routing | No model-generated Python or endpoints |
| `colony_production` | Utilities, loaded table recipes and material logistics | Native components, whole-unit stock allocation, ordinary bills and workers |
| `colony_sustenance` | Food, preservation, animal husbandry, diets and fishing | Native stock, recipes, pens, medicine/food policies and jobs |
| `colony_resilience` | Patient care, disease, sanitation, temperature, roof and diagnosis | Visible symptoms, native workgivers, evidence-gated operations |
| `colony_society` | Medicine, prisoner policies, childcare, growth, drugs, deathrest and surgery | Instantiated needs, earned options, beliefs and ordinary policies/jobs |
| `colony_progression` | Prerequisite frontier and finite Core/DLC ending chains | Native quests, blockers, intermediate choices and persisted credits evidence |
| `colony_specialists` | Mechs, containment, rituals, genes, permits, meditation and dryads | Active DLC, native dialogs and current capabilities |
| `colony_affordances`, `colony_sessions` | Loaded abilities/interactions and pending native choices | Current callbacks/targets, costs, effect identity and modal/session validation |
| `colony_capabilities` | Crops, blight, augmentation, equipment and trained animals | Previous capability audit; retained |
| `colony_combat` | Threat geometry, available tactics and target selection | Live positions, capabilities and contact distance |
| `colony_architect` | Building purpose, materials and generated layouts | Actual catalog, stock, research and placement checks |
| `colony_strategy`, `colony_growth`, `colony_professions`, `colony_events` | Existing course, population, workforce and event support | These remain partial; catalogue entries are not completed chains |
| `colony_reasoning`, `laya_decisions` | Consequence descriptions and bounded native comparisons | Exact compared state is logged |
| `colony_outcomes` | Last order and subsequent measured changes | Acceptance, observation and completion are distinct |

## Extension contract

Each registered domain defines `DESCRIPTIONS`, `LABELS`, `ACTIONS`, `DOMAINS` and:

1. `collect(client, snapshot) -> dict`: read current context; never issue orders.
2. `prepare(snapshot, map_state) -> list[str]`: propose registered actions and
   store current typed options inside its own development namespace.
3. `assess(action, snapshot) -> dict`: benefit, risk, cost, inaction, uncertainty.
4. `choose(agent, state, action, snapshot) -> (parameters, raw)`: native Laya
   choice over actual alternatives, including retaining the current policy.
5. `execute(client, snapshot, map_state, action, parameters) -> dict`: allowlist
   parameters, refresh eligibility and use an ordinary game action. Return an
   explicit boolean `applied`; do not replace the selected action silently.

Module identifiers are static code registrations. Duplicate or wrongly prefixed
actions are rejected. Collection errors clear stale module context, suppress
that domain's candidates and produce a warning; unrelated modules remain usable.
All new runtime modules are included in `install_payload.py`.

## What “consider negative outcomes” means here

The installed English Laya is a typed decision model, not a text-generating
planner. It chooses among supplied alternatives; we cannot obtain a textual
internal deliberation by asking for it. The checkpoint in this installation has
`max_len=512`, `head_max_len=192`. This matches the English entry in the
[author's model card](https://huggingface.co/convaiinnovations/laya/blob/main/README.md).
Other checkpoints have different limits; this change does not switch models or
load larger weights.

Before action selection, each compared alternative gets five explicit fields:

- benefit: what the action can provide;
- risk: how it can harm the colony or fail;
- cost: material, labor, service interruption or recovery;
- inaction: what continues if the order is not issued;
- uncertainty: what current observations do not establish.

These are game-grounded descriptions, not calibrated probabilities or simulated
future outcomes. Legacy actions receive conservative family-level descriptions
with specific crop, hunting, power and surgery overrides. Detailed new actions
provide their own native facts. Authoring more text alone does not train Laya.

The adapter reserves space **by field and by compared alternative**, so a long
benefit cannot evict all downside. Token counts include the full JSON envelope.
Each comparison records the actual visible state and budget. Context never
pretends an omitted fact was seen. Detailed legacy descriptions still use
bounded prefixes; this limitation is distinct from the new consequence cards.

## Cost and performance

- Broad domain/family selection remains hierarchical; detailed evidence is
  supplied when choosing an operation and its parameters.
- Consequence comparisons use pairs. For N alternatives the tournament requires
  at most N−1 predictions. This costs more calls than one coarse six-way choice,
  but preserves meaningful downside within the installed window. No extra
  “critic” model or second GPU model is loaded.
- A tournament is order-sensitive and can miss a preference cycle; its winner
  and reported weights are not a proof of an optimal plan or survival odds.
- Prompt clipping uses binary search instead of repeatedly removing a few
  characters and tokenizing the whole string. Token-count caching is local to a
  comparison and cannot accumulate colony histories.
- Shared research observations are reused for proposal collection. Execution
  refreshes them. Live stock, injuries, targets and eligibility are not cached
  across execution.
- Production's exclusion set is derived once from loaded definitions, rather
  than scanning the entire ThingDef database for every stack and recipe item.
- Every module records observation time (`read_ms`). These measurements support
  later profiling; no claim is made that the previously reported CPU spikes
  have been reproduced or fixed.

## Observation, memory and intent

The existing doctrine remains the persistent intended course. Progression now
compares that intention with a real prerequisite frontier and engine blockers.
Ship launch countdown is distinct from verified victory. Native Core, Royalty,
Ideology, Anomaly and Odyssey ending paths have explicit continuation handlers.
Odyssey is DLC-gated and compiled against shared classes; its Data is absent here.

`colony_outcomes` stores one bounded before-observation per map and reconciles it
at the next decision. It records changed meals, nutrition, on-map population,
downed people, construction count, completed research and threats. A changed
count is **not causal attribution**, a missing on-map pawn is **not a diagnosed
death**, and no measured change is **not proof of failure**. Exact domain
completion still requires domain-specific observation. Same-tick decisions
report that game progress is pending; a backwards tick discards the previous
timeline's order.

## Evidence and remaining coverage

See the [comprehensive inventory and closure audit](COMPREHENSIVE_AUDIT_0.0.7.md),
[production](modules/production.md), [society](modules/society.md),
[progression](modules/progression.md), [combat](modules/combat.md) and
[specialists](modules/specialists.md). Each distinguishes executable additions,
read-only context and missing mechanics. Installed RimWorld 1.6 definitions and
engine methods are the primary compatibility evidence; web sources supply
reference context. Odyssey is not treated as active on this installation.

Offline fixtures, compilation and tokenizer checks establish code and protocol
properties. They do not establish successful colony survival, correct live job
completion or victory. No game, colony, director or observer was started for
this change. No model weights were trained.
