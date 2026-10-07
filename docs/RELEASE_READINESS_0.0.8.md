# 0.0.8 candidate

Development continues in `feature/0.0.8`, through a candidate PR into `developing`.
The active continuation is [PR #5](https://github.com/Georgy-hook/rimworld-autopilot/pull/5);
branch rename closed the former PR #4.
`main` and `developing` were advanced without force to the published `v0.0.7`
package. Historical merged test branches were removed after ancestry and clean
checkout checks; their checkouts and commits remain recoverable.

This candidate includes the quest review and colony verification work following
the 0.0.7 tag and [the final colony corrections](audits/roinor-recovery-2026-10-07.md).
`VERSION=0.0.8` labels the working candidate; no 0.0.8 tag/release is published.

Offline gates: 1235 tests, 311 routes, native Release-1.6 without warnings/errors,
actual native predator boundaries and cached-model crop/startup replay.
Install both native copies from the DLL whose embedded revision matches the
audited source commit, and hash-check runtime payloads before the next landing.

Live gates: actual food production and reserves; care and predator defense;
ordinary beds and safe thermal refuel; complete JSON logistics; wiring and
consumer operation; animal losses/training; raid outcomes; permanent growth,
completed sales and progress toward a compatible finite ending. Include the
base screenshot and functional layout in every hourly comparison.

The isolated startup NRE and unsupported monument executor remain open.
Successful API calls and a healthy director do not close these live gates.

The authorized new single random landing started 7 October at11:11:50UTC on
tile10598. Its startup inventory is recorded in PLAYTEST_REPORT.md; food reserves
are initial supplies, and roofed shelter was not yet confirmed at the first
startup assessment. Hourly observations include the real base screenshot and
the comparison card. This is an ongoing playtest, not release approval.
