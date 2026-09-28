# Decision architecture

Version 0.0.6 follows the way the Laya/Jev ecosystem is used in public examples: deterministic application code projects state and defines typed alternatives; the model ranks a bounded choice; application code validates and reduces the answer into an effect. The additional [Laya architecture and evaluation](docs/LAYA_ARCHITECTURE.md) explains the root checkpoint's limitations, tokenizer-aware context and bounded comparisons introduced after 0.0.3.

References reviewed before this redesign:

- [Laya SDK](https://github.com/NandhaKishorM/laya) — typed `choice`, `score`, and `noul` decisions over compact state.
- [Laya + Jev laboratory](https://github.com/yibie/laya-jev-lab) — practical composition of the local model and typed decision layer.
- [JevLoop](https://github.com/zjunlp/JevLoop) and [Typesafe Jev examples](https://github.com/rajivkuriakose/typesafe-jev-examples) — narrow typed decisions inside a deterministic control loop.
- [Jev use-case playbook](https://github.com/Anil-matcha/awesome-jev-by-typesafe/blob/main/docs/jev-use-case-playbook.md) — conditional follow-up questions are built after the selected branch is known.

## Pipeline

```text
RIMAPI snapshot
  → deterministic feasibility and safety gates
  → decision domain (only when the candidate set is large)
  → action family (only when still large)
  → one concrete action
  → parameters for that action only
  → validation against the same snapshot
  → ordinary RimWorld job / bill / zone / blueprint / designation
  → decision log and overlay
```

Hunting, taming, wild harvesting, flooring, paths, doctrine, sculpture placement, temples, construction projects, trade and combat rosters therefore have conditional parameter stages. A rejected branch cannot accidentally select or execute one of its targets.

Long-term strategy has its own content-aware cascade:

```text
active package IDs + live research/building/work catalogues + workforce fit
  -> broad strategic domain
  -> one compatible archetype
  -> settlement/economy/technology/defense/society/endgame axes
  -> product inside the chosen economy family
  -> mineral only when that product is mining
  -> saved versioned doctrine
```

`colony_strategy.py` owns the audited Core/DLC catalogue. It filters inactive expansion mechanics before inference and turns the saved doctrine into live research, architecture and fortification candidates. `DIRECTION_AUDIT.md` records the coverage boundary and official sources.

Player guidance is a separate input, not a game command:

```text
laya_gui priorities/note/safety boundaries
  -> validated autopilot-preferences.json
  -> compact player_preferences model context
  -> candidate ordering and explanation
  -> normal feasibility/safety validation still wins
```

The UI itself is isolated in `laya_gui/`; `autopilot_control.py` is the public launcher and `laya_control.py` remains a compatibility entry point. Normal history is deliberately user-facing. Technical mode changes both presentation and persistence: development cycles add full details/snapshots, while combat cycles retain their full snapshot only when that switch is active. See `GUI.md`.

Combat follows its own hierarchy:

```text
verified hostile state
  -> feasible tactical templates
  -> exact healthy roster
  -> exact caster/psycast only for a psychic tactic
  -> RIMAPI live-map positioning and path validation
```

`colony_combat.py` owns tactical meaning. `CombatTacticsHelper` owns game-state mutation and refuses movement paths containing a player trap. Defensive structures are read from the map, so `killbox_hold`, doorway blocking, fallback lines, EMP positions and mortar options are only offered/applied with real infrastructure.

Events use a parallel pipeline:

```text
all loaded IncidentDefs + recent occurrences + conditions + letters + quests
  -> colony_events.py family (or unknown/mod fallback)
  -> proportional response
  -> nested trader, quest or rescue-site parameters when selected
  -> deduplicated normal-game action
```

This avoids a permanent hard-coded event switch: new DLC/mod incidents remain visible and receive a conservative generic decision even before a dedicated family rule is added.

Architecture is a deeper instance of the same rule:

```text
need + profession doctrine + loaded BuildingDefs
  → building program
  → house style (residences only)
  → 3–4 generated variants
  → resource/research validation
  → ordinary blueprint
```

`colony_architect.py` contains functional programs and generators rather than a long list of saved maps. A deterministic seed produces 24 residential alternatives (six styles by four door/size/furniture arrangements) and bounded variants for other facilities. Existing buildings are never demolished merely because a doctrine or material preference changes.

`colony_professions.py` reads the live `WorkTypeDef` catalog, so Core, DLC and modded jobs remain visible. Strategic directions are scored from each pawn's skill, passion, learning traits, health and work restrictions. Skill training uses the same hierarchy: choose the action first, then the exact pawn/skill/work mapping.

## Responsibility boundary

Laya decides preferences and trade-offs. Code remains responsible for facts and invariants:

- target IDs must exist in the current snapshot;
- research, skills, materials, temperature and power prerequisites must be satisfied;
- remote API addresses and cheat endpoints are rejected;
- dangerous/lethal organ plans are explicit, never a side effect of a sale/recruit choice;
- battle candidates carry weapon, trait, injury, pain and body-capacity context;
- repeated orders are suppressed, while stalled plans can be retried after a bounded interval.
- darkness is measured from the real glow grid; a light blueprint uses a verified empty room cell;
- throne-room choices use the current royal title and unmet requirements, while hospital variants follow unlocked bed/monitor/floor technology;
- workbench upgrades are additive: the old bench remains until the successor exists.

This is intentionally not a free-form agent that invents API calls. Adding a capability requires a typed candidate, compact context, validation, a normal-game executor and a deterministic test.
