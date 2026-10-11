# Quest consequences and exact acceptance — 2026-10-07

Offline corrections after Complete Union of Leler ended. Working branch
`fix/0.0.7-cold-start`, published base `v0.0.7`. No colony was generated, resumed
or given commands during this correction.

## Recorded failure

At 20:37:07 UTC on 6 October, Laya accepted Royalty `Intro_Deserter` while the
remaining guest was downed and bleeding, food/medicine were zero and no mobile
worker remained. The selected doctrine was `imperial_ascension`. The public API
description disclosed Empire hostility and an immediate pursuing loyalty squad,
but `agent.predict` received only the event JSON prefix through the incoming
pawn's name. `decision_facts` was empty; only 116 of 312 state tokens were used.
Installed/source file hashes matched.

This establishes a transport defect. Consequences, clinical state and the ending
were clipped before inference. The population flag was also false despite a
`Reward_Pawn`; rewards were flattened and acceptance could select the first
alternative silently.

The founders and later workers had already died from malnutrition. The deserter
was shot dead; the last guest's cause remains unconfirmed. This quest defect is
not established as the sole cause of the colony's loss. See the
[playtest history](../playtests/Care-ownership-start-2026-10-06.md).

## Corrections

| Boundary | Correction |
| --- | --- |
| Input | Common `colony_quests` review with complete public terms, actual-tokenizer pages and colony/ending facts on every page. |
| Inventory | Native catalogue of every loaded script and generic offer handling; no ordinary name whitelist. |
| Context reads | Acceptance callbacks/accepter scans run only for pending offers; archived or accepted commitments do not reevaluate obsolete acceptance targets. |
| Consequences | Immediate/delayed threats, diplomacy/current relation, travel, labor, food/care, duration, ideology, ending and uncertainty. |
| Rewards/people | Public reward groups, exact reward/accepter IDs and possible population distinguished from guaranteed labor. |
| Time | Offer expiry and elapsed accepted time separated; work deadlines remain public terms. |
| Execution | Fresh roster/capacity/emergency and offer validation, native version/eligibility/reward checks, pre-resolved objects before index mutation. |
| Alternate routes | Offered quest letters and ending acceptance cannot bypass the contract. |
| Letters | Full text; disagreement/defer postpones the response instead of outvoting a late warning. |
| Repeats | Shared target/effect memory independent of worker; food/clinical facts retained in nested comparisons. |
| Drift | Ordinary consumption, improving injuries and countdown do not create a stale-review loop; new danger/loss requires review. |

See the [quest module contract](../modules/quests.md). Python/native corrections
must be installed together before a future game run.

## Every installed script and its prompt transport

`tools/audit_quest_prompts.py` reads installed `Data/*/Defs/QuestScriptDefs` XML,
resolves inherited rules and passes their whole text/metadata through production
`offer_fields`/`review_pages` using the cached Laya tokenizer. Every field is
reconstructed after public rich-text tag cleanup. Every page retains food zero,
bleeding 3.65 and the imperial goal within 312 tokens.

| Installed pack | Named scripts | Need native-generated description |
| --- | ---: | ---: |
| Core | 23 | 5 |
| Royalty | 61 | 20 |
| Ideology | 14 | 0 |
| Biotech | 10 | 1 |
| Anomaly | 12 | 0 |
| **Total** | **120** | **26** |

These include automatic/internal utilities, not 120 distinct player offers.
Code-generated scripts without XML rules use an explicit offline placeholder
and are marked in the [complete inventory](quest-script-inventory-2026-10-07.json).
In play, the native generated public description is required; missing text causes
defer. Concatenated template variants are not live offer latency measurements.
Odyssey Data is absent. Unknown mod text transport is tested, but modded quest
execution is not. Hidden future outcomes are not inferred from internal signals.

## Verification

| Check | Result | Evidence limit |
| --- | --- | --- |
| Python suite | **1223 tests passed** | Includes 17 new quest/context/sequence regressions; clients/game are mocked. |
| Script/tokenizer audit | **120 scripts; max state 312 tokens** | Complete supplied terms, not native generation/completion. |
| Native harness | **13 guard cases + index mutation fixture passed** | Runs actual validation/selection code offline, not game signals. |
| API inventory | **310 routes; 265 literal calls; zero missing/duplicates** | 27 dynamic calls listed separately. |
| Native `Release-1.6` | **Zero warnings/errors** | Compiles against 1.6.4871 references. |
| Actual encoder audit | **16 scenarios; 299 comparisons; state max 311, sequence max 419 tokens** | Loads tokenizer/config only; no weights or game. |
| Actual cached CUDA Laya: deserter crisis | **defer; four pages** | Recorded public description with representative crisis facts. |
| Actual cached CUDA Laya: prepared trade | **accept; three pages** | Explicit synthetic positive comparison. |

Model diagnostics use four CPU threads and zero game/API commands. These are two
fixtures, not a survival benchmark or a byte-identical full replay. They do not
train model weights.

Cases cover late raid/diplomacy, long Unicode unknown offers, nonfirst reward and
accepter, expiry/stale terms, patient/roster changes, consumption drift, letter
bypass, accepted timing, nonworking guests, late letter disagreement and
cross-module monolith repeats.

A stress case combining bleeding, starvation and two severe thermal conditions
found a joint clinical/quest envelope overflow. Equal overlapping counters now
appear once; if needed, thermal condition names, values, stages and danger flags
use complete readable text. Nothing is prefix-clipped. The regression covers
three patients and a long native ending-job identity without losing dangers.

Reproduce with dependency-equipped Python and a .NET SDK:

```powershell
python -X utf8 -m unittest discover -s tests -q
pwsh -NoProfile -File tests/native_quest_offer_boundary.ps1
python -X utf8 tools/audit_quest_prompts.py --game-data 'C:\Program Files (x86)\Steam\steamapps\common\RimWorld\Data' --output quest-audit.json
python -X utf8 tools/audit_api_contracts.py --output api-audit.json
dotnet build vendor/RIMAPI/Source/RIMAPI/RIMAPI.csproj -c Release-1.6 --nologo
```

`tools/replay_quest_model.py --fixture … --output …` runs only the explicit
cached-model diagnostic, without an HTTP client or director.

## Remaining limits

- Exact `BuildMonument*` / `Decree_BuildMonument*` blueprint placement is still
  unavailable; these offers are deferred rather than accepted without an executor.
- Complete prompts do not guarantee correct strategy. Quest work, travel, care,
  defense, native signals and rewards require live observations. All generated
  variants and quest callbacks have not been exercised with this correction.
- The interaction floor prevents rapid reassignment, not every eventual retry;
  accepted investigation still does not mean completion.
- Separate colony defects remain open: ordinary bed assignment via medical rest,
  rejected fuel routes, empty logistics JSON, sustained nutrition and
  tend-versus-rescue option mismatch. This audit does not mark them resolved.
- No runtime installation, new installer, release tag or colony launch is part
  of this correction. The corrected candidate is built and checked offline.
