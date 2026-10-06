# 0.0.7 release preparation — 6 October 2026

Status: **draft release candidate, with live verification gaps**. The source
branch is `fix/0.0.7-cold-start`, targeting `developing` in PR #4. Preparation
does not merge the branch or replace the published stable 0.0.6 installer.

## Verified gates

| Gate | Result |
|---|---|
| Python regression suite | 1174 tests passed, including multi-cycle refusal memory, fresh caregiver changes, exact job readback and real tokenizer limits. |
| API contract audit | 308 native routes, 263 literal Python calls and 27 dynamic call sites; no missing direct calls or duplicate routes. Offline audit did not contact RimWorld. |
| Native build | Release-1.6, zero warnings and errors. Distributable DLL must be rebuilt after the source commit so its embedded revision identifies the audited source. |
| Kitchen geometry | Five boundary cases execute the predicate extracted from native source. This proves the cleanup boundary, not completed cooking. |
| Terminal evidence | Native Game Over, no living residents or caravans and save XML verified. Private saves and logs remain outside Git. Public reports use anonymous residents. |
| History | Fourteen dated runs distinguish measured segments, snapshot spans, technical replays and unverified causes. |

The final source/native/package identity and installer/ZIP digests are recorded
in the release assets and release notes after the Windows packaging step. The
release process requires the versioned installer and fixed-name full installer
to be byte-identical, runtime DLLs to match the source DLL, and uploaded asset
digests to match the local files.

## Confirmed fixes in this preparation

- [Production cooldowns, truthful food preparation and local kitchen cleanup](audits/food-deferral-kitchen-2026-10-06.md).
- [Berserk protection, scoped allied attack cancellation and exact post-combat care](audits/allied-berserk-care-contract-2026-10-06.md).
- [Clinical prompt retention, recreation choices and truthful waiting](audits/clinical-context-wait-2026-10-06.md).

Earlier candidate corrections and expanded modules are described in
[release notes](../RELEASE_NOTES.md) and the [documentation index](README.md).
The [last colony report](playtests/Theentbum-2026-10-06.md) describes the old
installed build's defeat, not a playtest of the final fixes.

## Remaining checks and limits

- Final changes have offline verification only. Native protective arrest,
  defensive cancellation followed by timely treatment, sustained cooking and
  adequate shelter need a separately recorded live run.
- Transient attack leases do not adopt arbitrary manual or restored attacks
  after a game/process restart. Arrest can fail and ordinary combat can kill.
- The latest colony never established reliable food reserves, income or
  completion of an ending. Added context and executors do not establish that
  Laya will make the necessary decisions or win autonomously.
- Loading-only NullReferenceException without the original stack remains
  unresolved. The terminal run's log stopped growing after loading; this is
  insufficient to attribute its deaths to that exception.
- Odyssey runtime verification remains pending where DLC Data is unavailable.
  Offline ending chains are not proof of native ending completion.
- Clean installer/uninstaller execution and post-fix live gameplay are pending.
  Packaging checks verify contents and digests, not installation behavior.

The ended colony and hourly observation stay stopped. A draft can be reviewed
without starting another colony or changing the stable release.
