# Same-colony terminal outcome — 2026-10-06

The Goberium/Theentbum colony on tile 55904, Cassandra/Medium/permadeath,
ended in defeat. Installed source was `dd80168`, native package `ba80742`.
Native ending evidence confirms `game_over_verified=true`,
`victory_verified=false`, zero colony population and zero caravans.
Game Over arrived at tick 2771391; observer/director detected it at
11:48:46 UTC and held the final pause at 2771459.

## Confirmed losses

Pawn names are retained only in the private report and save. Native death
letters, including the final persisted save, confirm the deaths of all four
final residents.

| Resident | Death tick | Native cause | Observer delivery, UTC |
|---|---:|---|---|
| Ten-year-old child | 2623288 | Beaten to death | 11:09:13 |
| Adult with go-juice dependency | 2633482 | Blood loss | 11:12:07 |
| Remaining female founder | 2721806 | Malnutrition | 11:35:02 |
| Last caregiver | 2770992 | Malnutrition | 11:48:44 |

The former founder infection death and earlier beating death remain part of
this colony's history. Two child starvation deaths on discarded diagnostic
branches are documented separately; they are not this final child's cause.

## Continuation and observed failure sequence

The final continuation began at 11:00:12.222 UTC, tick 2571161, after the
growth-window repair. It lasted about 48m34s and advanced 200230 ticks to
Game Over, about 3.337 game days. It ended before the scheduled full hourly
review. Modal freezes, technical replays/loading and earlier diagnostic
restores are excluded. The entire multi-day development run is not a clean
uninterrupted autonomy benchmark.

Across seven retained autonomous phases on 5–6 October, elapsed autonomy was
about 3h56m (metadata sum 3h55m54s, with roughly one minute of growth-freeze
uncertainty). Overall history from tick 40 reached 46.189 game days, including
technical loading ticks. See the [dated duration history](Colony-lifetimes-2026-10-06.md)
for boundaries and excluded branches.

- Native Berserk letter at 2621212 identifies starvation as the adult's final
  trigger. The child soon died from human-fist trauma. This report does not
  establish the specific actor that delivered the fatal blow.
- From 11:08:39, combat replies identify that allied adult as target and allied
  residents as attackers. The last sampled patient had bleeding 5.76 and
  BloodLoss 0.72. A tend order was accepted at 11:11:00, before the 11:12:07 death
  event; acceptance does not establish timely completion or cessation of fire.
- The remaining caregiver became catatonic at 2643792; the letter identifies
  recreation deprivation. Both remaining residents were later downed/unfed;
  their final sampled Malnutrition was 0.994 and 0.986.
- Across 48 samples with changing ticks, prepared meals ranged 0–1, raw food 0–99
  and wood reached 20. Final campfire and passive cooler fuel was 0. A remaining
  survival meal in aggregate stock does not establish patient access. Final
  beds belonged to room 0 with a large open-roof count; sheltered sleeping was
  not verified by that snapshot.
- The bounded tail covers 415 final-segment records: 44 material-logistics
  selections, 47 production deferrals, 24 survival waits, 61 no-controllable-fighter
  waits and 178 hazard-guard records. These are unresolved repetition and
  scheduling observations. Their code-level cause remains unverified; some
  waits reflect genuine incapacity.

Microelectronics moved about 1578→1582/3000. No sale ledger entries were
recorded; a 90-silver increase is explained by the native caravan gift letter.
The ending objective was not achieved. Local butcher spots existed, while
food production and care failed to sustain the colony.

## Evidence and follow-up boundary

The growth modal no longer froze the run; no repeat of that specific failure
explains this outcome. Python stderr files were empty. Loading-time
NullReferenceException duplicates remain unresolved and are not attributed as
the cause of these deaths.

Private evidence contains final API/snapshot, bounded logs, native letters,
combat/care extracts, memory and Player.log. The preceding autosave 2751140
was preserved separately. Final save persistence was verified at 2771459,
mtime 12:04:54.955 UTC, with all four death letters and Game Over.
The director and observer stopped themselves; the remaining read-only monitor
was closed during documentation. Hourly automation is paused, and RimWorld
remains on its final pause. No code repair or new colony was performed for
this outcome-recording request. Clinical/combat continuity, Berserk protection,
food access and repeated deferrals remain follow-up investigations.

## Subsequent release preparation

After recording defeat, the user requested fixes, a commit/push and preparation
of 0.0.7. Source review confirmed short production deferrals, outdoor cleanup
spreading through room 0, incomplete allied Berserk protection and lossy
nonthermal clinical context. These concrete defects were corrected and checked
offline; no new colony was launched and the terminal outcome is unchanged.
See [release readiness](../RELEASE_READINESS_0.0.7.md) for verified gates and
remaining live checks. Some recorded waits reflect actual incapacity and are
not thereby diagnosed as defects.
