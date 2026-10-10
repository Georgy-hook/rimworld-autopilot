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

The latest [10 October postmortem repair gate](audits/postmortem-source-repairs-2026-10-10.md)
supersedes the test totals below: 1304 Python tests, 313 routes, native actual-source
boundaries and zero-warning Release-1.6. It adds shared labor commitments, exact
mining/hauling, fresh carcass geometry, finite pen feed, animal thermal rescue,
elective surgery safeguards, partial quest reads and bed replacement recovery.
The completed playtest was preserved; none of these repairs were tested by
injecting them into that game. Sustained survival and native completion remain
required live gates before a release.

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

The single random landing started 7 October at11:11:50UTC on tile10598 and
ended with native GameOver2431617 after about5h36m. All five human deaths were
Malnutrition. Hourly observations and the terminal report include real base
screenshots, layout comparisons and cause evidence. The
[food commitment corrections](audits/lenrobum-food-commitment-2026-10-07.md)
passed1245 tests and cached-model starvation replay; the next authorized random
colony must establish sustained food production and actual survival.

The following Dayouinum cold landing ended after54m22s: two founders died from
hypothermia, one from blood loss, and the replacement was kidnapped. The
[thermal-care correction](audits/dayouinum-thermal-care-2026-10-07.md) adds exact
safe-temperature rescue, response-before-wound context, failed-pair memory and
temperature-aware fuel evidence. Gates:1256Python tests,311routes,8actual native
thermal boundaries, zero-warning Release-1.6 and cached-model thermal sequence
in both option orders. Actual warming and repeated heating remain live gates.
At user request the final save was verified, the game closed and observation
paused; no new colony or0.0.8 release was started.
