# Decision architecture

The 0.0.7 candidate uses deterministic application code to project state and define typed alternatives; Laya ranks a bounded choice; application code validates the answer against fresh game state before issuing an ordinary command. Start with the [documentation index](docs/README.md), [module contracts](docs/MODULE_ARCHITECTURE_0.0.7.md) and [model interface and limits](docs/LAYA_ARCHITECTURE.md).

## Repository map

| Location | Owns |
|---|---|
| `colony_director.py` | Scheduling, snapshots, emergency ordering and legacy orchestration |
| `colony_modules.py` | Seven registered domains and their collect/prepare/choose/execute/assess interface |
| `colony_{production,society,progression,specialists,sustenance,resilience,affordances}.py` | Domain observations, typed options, fresh command validation |
| `colony_retry.py` | Shared JSON-safe failure clocks; per-option policy stays in domain modules |
| `colony_sessions.py` | Pending native dialogs and world continuations |
| `colony_expeditions.py` | Shared trade, raid and rescue preview, consequence cards and exact-plan confirmation |
| Other `colony_*.py` | Construction, combat, strategy, capabilities, events and supporting policy; see module contracts for ownership |
| `laya_decisions.py`, `rimworld_laya.py` | Bounded model comparisons; model/runtime and local HTTP transport |
| `laya_gui/` | Desktop UI and process services; `autopilot_*.py` are launchers |
| `vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/` | C# API routes, DTOs, engine observations and ordinary command executors |
| `vendor/RIMAPI/1.6/Assemblies/RIMAPI.dll` | Deliberately tracked playable build; source revision is embedded |
| `tests/`, `tools/` | Offline regression fixtures and explicit audits/build/media utilities |
| `docs/modules/`, `docs/audits/`, `docs/playtests/` | Current domain contracts, dated audits and historical observations |
| `installer/`, `Build-GUI.ps1`, `install_payload.py` | Windows packaging; `VERSION` is the product version source |
| `assets/`, `artifacts/` | Shipped UI/promotional assets and retained source material |
| `logs/`, `dist/`, build/venv folders | Ignored runtime and generated output |

Root Python modules keep their existing names because launch scripts, payload
assembly and imports use them. The registry extraction is incremental:
the director still owns legacy orchestration. A folder move alone would not
remove that coupling. New domain behavior belongs in its module and native helper;
cross-domain requirements pass through compact shared observations.

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
  → fresh validation of identity, prerequisites and material changes
  → ordinary RimWorld job / bill / zone / blueprint / designation
  → command acceptance log and overlay
  → subsequent observation of progress, blockage or completion
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
- retries use bounded, target-specific history where available; new targets and material state changes must remain visible. Individual domain rules are documented and regression-tested; this is not a proof that every possible strategy terminates;
- darkness is measured from the real glow grid; a light blueprint uses a verified empty room cell;
- throne-room choices use the current royal title and unmet requirements, while hospital variants follow unlocked bed/monitor/floor technology;
- workbench upgrades are additive: the old bench remains until the successor exists.

This is intentionally not a free-form agent that invents API calls. Adding a capability requires a typed candidate, compact context, validation, a normal-game executor and a deterministic test.

## State and API boundaries

Campaign identity binds persistent doctrine across maps. Map-local coordinates,
construction intents and command history stay with the map; loading an earlier
tick invalidates future history. Native pending sessions carry their own
identity and are handled before normal development. An empty continuation is a
blocked observation, not permission to submit an empty model question.

GET observations must expose absence, unavailability and native blockers
explicitly. Python transport unwraps the API envelope; module code consumes
the documented data object. POST success establishes command acceptance only.
Native jobs can still wait, fail or be interrupted. Revalidation preserves
strategic meaning (selected target, manifest, cost and protected work) while
allowing ordinary informational drift that does not change eligibility.

The project does not infer completion or victory from HTTP status, an accepted
bill, a blueprint, or launch countdown. Offline tests cover finite scenarios;
live long-term reliability remains a separate gate.
