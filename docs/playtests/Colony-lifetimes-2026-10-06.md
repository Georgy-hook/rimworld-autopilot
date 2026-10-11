# Colony observation durations — 6 October 2026

Dates use Moscow time. Run labels below are anonymized; they do not expose player names, saves or private diagnostic paths. Observation time is not always a colony's full lifetime. Snapshot intervals are not measured director runtime. A segment is a single continuation; development pauses, loading and discarded rollback branches are excluded from clean segment durations. Game days are tick advancement divided by 60000.

| Date | Anonymous run | Measured time / qualification | Game days | Outcome |
|---|---|---|---|---|
| 28 Sep | R14 | Unknown; controlled replays | Unknown | Three alive after technical replay |
| 29 Sep | R29-A | Snapshot interval 11m12s; early unmanaged time | 2.571 | Two lost, one survivor remains |
| 29 Sep | R29-B | About 43m38s to Game Over | ≥10.38 | All residents died after injuries |
| 29 Sep | R29-C | Snapshot interval 15m17s | 4.383 | Founders lost, emergency survivor alive |
| 29 Sep | R29-D | Snapshot interval 35m42s | 12.371 | Kidnapping and another resident lost |
| 29 Sep | R29-E | Snapshot interval 8m08s | 3.321 | Founders lost before heating completed |
| 29 Sep | R29-F | Snapshot interval 6m05s | 2.378 | Technical stop, all founders alive |
| 29 Sep | R29-G | Snapshot interval 4m04s | 1.613 | Technical stop, all founders alive |
| 29 Sep | R29-H | Active time unknown; repairs/reloads | ≈22.096 total progression | Injury and predator losses ended colony |
| 29–30 Sep | R30-A | Final autonomous segment 42m39s | 14.737 segment | Heatstroke, blood loss and kidnapping |
| 3 Oct | R03-A | Total unknown; final continuation ≈15m31s | 8.193 total; 4.607 continuation | User ended run with survivor |
| 3 Oct | R03-B | Autonomous segment 48m44s | 15.453 | Blood loss, disease and kidnapping |
| 3–5 Oct | R05-A | Unknown; three technical continuations | 2.49 from reboot checkpoint | Suspended technical run, all alive |
| 5–6 Oct | R06-A | ≈3h56m retained autonomous phases; final segment 48m34s | 46.189 total progression; 3.337 final segment | Beating, blood loss and malnutrition |
| 6 Oct | R06-B | Published 0.0.7, one generation, ≈39m44s to native Game Over detection | 5.141 | Three blood-loss deaths; emergency survivor infection |

R06-A lasted about **3h56m across seven retained autonomous phases** before
definitive defeat. The final 48m34s is only its last continuation. Metadata gives
a phase sum of 3h55m54s, including ordinary decision waiting. The exact growth
modal freeze falls between consecutive minute observations, introducing up to
61.85s uncertainty (approximately 3h54m53s–3h55m54s); some earlier boundaries also
use rounded timestamps.

The 46.189 game days span baseline tick 40 to Game Over 2771391 and include
technical loading ticks. Technical pauses and three discarded diagnostic branches
are excluded from the real-time sum. A worker-selection error began 0.476s before
its phase stop. The bounded terminal timeline had 47 pre-defeat samples with no
paused or repeated ticks and no API errors; later samples show terminal pause.
Unrecorded shorter delays inside phases were not subtracted. These figures
measure retained autonomous elapsed phases, not continuous productive execution.

Death evidence is graded separately from outcome. A lethal health severity in a save supports an inference; it is not a native death-cause letter.

R06-B began at 13:16:44.651655 UTC, baseline 25, and ended at Game Over 308496,
detected 13:56:28 UTC. All four causes are confirmed by native death letters:
three founders BloodLoss, emergency survivor WoundInfection. One founder had
megaspider wounds, the other two rat-teeth wounds. The prior disk save 300000
does not contain the last death; native live evidence, letters and director
memory establish defeat. [Outcome report](Release-007-2026-10-06.md).

Subsequently the user requested closure and offline repairs. Terminal XML 308589
was saved at 15:10:53 UTC and RimWorld exited at 15:10:55 UTC. This replaces the older
save as the latest retained checkpoint; it does not extend the colony's 39m44s
autonomous lifetime. No new colony was started.

- R14: one founder died in a discarded blocked-path branch; exact cause unverified. The completed replay retained all three.
- R29-A: two founders died after insect injuries; exact causes unknown.
- R29-B: four residents died; observer BloodLoss captions were last-known conditions, not confirmed death causes.
- R29-C: three founders died after observed hypothermia; exact causes unknown. Emergency survivor alive at last observation.
- R29-D: one founder kidnapped, another absent from living roster; exact fate/cause unknown. One survivor remained.
- R29-E: three founders died before heating; exact causes unknown. Emergency survivor remained.
- R29-F and R29-G: no confirmed resident deaths.
- R29-H: founder H1 had severe bleeding, exact death cause unknown; H2 and later resident H4 died of blood loss according to letters; H3 had infection, terminal cause unknown. Game Over confirmed.
- R30-A: founder T1 died of Infection by letter; T2 was dead with BloodLoss 1 in the save, so blood loss is inferred. Founder T3 and dependent child T4 died of Heatstroke by letters. Emergency resident T5 was kidnapped and alive in the final save. Colony dog died of BloodLoss by letter. Everyone dead or gone does not mean every former resident died.
- R03-A: founders Q1/Q2 had BloodLoss 1 in the final save; Q3 had Malnutrition 1 and residual BloodLoss. Causes are inferred from save conditions. Emergency survivor alive; user ended the run, no native Game Over.
- R03-B: resident K1 BloodLoss, K2 PsychiteAddiction, emergency resident K3 LungRot were recorded as native causes. K4 kidnapped, death unconfirmed. Colony dog BloodLoss by letter. Game Over confirmed.
- R05-A: two founders downed, third tending; all alive at suspension.
- R06-A: founder G1 Infection, founder G2 and child G4 beaten to death, adult G5 BloodLoss, founder G3 and caregiver G6 Malnutrition; native letters confirm causes. Game Over at 14:48:46 Moscow, tick2771391. Discarded diagnostic malnutrition deaths of G4 are excluded from this final history.

The retained colony playtest journal and dated reports provide the source account. None of these observations establishes autonomous victory. Unknown wall-clock fields have not been reconstructed from game speed.
