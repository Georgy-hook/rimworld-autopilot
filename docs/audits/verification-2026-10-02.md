# Offline verification — 2026-10-02

Scope: campaign API/strategy architecture and start-to-ending contract repair.
Starting source revision: `ca8c032`, branch `fix/0.0.7-cold-start`.

| Gate | Result |
|---|---|
| `python -m unittest discover -s tests -q` | 661 passed |
| `dotnet build vendor/RIMAPI/Source/RIMAPI/RimApi.csproj -c Release-1.6 --no-restore -v minimal` | Success; 0 errors, 0 warnings |
| `tools/audit_api_contracts.py` | 296 registered routes; 242 direct literal calls; 0 missing route/method combinations; 0 duplicate registrations |
| Nonliteral call sites | 14 listed separately: fixed endpoint tables, whitelisted ending suffixes, native specialist tables, typed command objects and `safe_get` forwarding; not counted as direct literal proof |
| `tools/audit_module_prompts.py` with locally cached real tokenizer and Laya encoder | 15 scenarios, 298 comparisons; largest state 308 tokens, largest encoded sequence 419; all prepared state tokens and all option markers retained |
| Checkpoint limits | `max_len=512`, `head_max_len=192`; explicit state budget 312 |
| `git diff --check` | Passed |

The tokenizer scenarios include 80 animals, 20 patients, 50 recipes, specialist
actions, ship decisions, exact native targets, full doctrine cascade with every
DLC represented in a fixture, oversized legacy state, royal assignment and
journey food/ETA decisions. Loaded model weights: **false**.

The mocked model-start unit test prints a loading message. It does not load
weights. No game process, director, observer or colony was started; no gameplay
HTTP request was made for these checks. Compilation writes the repository DLL,
not an installed mod in a live game.

Raw route inventory and actual tokenizer-visible comparisons are written under
the workspace `work/path-contract-audit-20261002/`. The final user report in
`outputs` records source/DLL commit identities and the compiled DLL hash.

Source inspection is grounded in installed 1.6 definitions and native assembly
methods. Odyssey Data is absent; its handler compilation and fixtures do not
establish a complete played Odyssey ending. None of these tests establish a
successful policy rollout, measured live CPU improvement or victory probability.

See [the complete conditional walkthrough](campaign-path-walkthrough-2026-10-02.md)
for API evidence, actual actions, completion criteria and remaining proof limits.
