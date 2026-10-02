# Contributing

Issues and pull requests are welcome. Please keep gameplay automation honest: use normal RimWorld jobs, designations, bills, blueprints, research and trade. Do not add resource spawning, stat editing, teleportation, fog-of-war leaks or instant construction.

Before opening a pull request:

```powershell
python -m unittest discover -s tests -v
python tools/audit_api_contracts.py --output logs/api-contract-audit.json
dotnet build vendor/RIMAPI/Source/RIMAPI/RimApi.csproj -c Release-1.6
```

Never include a save or files from `logs/` in a bug report. Redact pawn names and other player-specific data from diagnostics.

Read [the current documentation index](docs/README.md) and
[module contracts](docs/MODULE_ARCHITECTURE_0.0.7.md). Keep new behavior in its
own domain; registering an action also requires observation, consequence
context, fresh validation and an ordinary executor. Include new runtime modules
in `install_payload.py`.

For loop fixes, exercise a sequence: propose, accept/reject/defer, change the
observed state, then propose again. Verify a new urgent target stays available,
unchanged failures have bounded retry, save rollback resets future history, and
ordinary work is not repeatedly restarted. A source assertion or passing HTTP
status alone does not demonstrate native job completion.

Offline tests and a C# build do not require launching RimWorld or model weights.
Live tests must be separately authorized and recorded as gameplay, technical
replay or direct intervention. The current candidate targets `developing`
through PR #4; `main` is the stable branch. Do not rename branches or publish
a release as part of an audit.
