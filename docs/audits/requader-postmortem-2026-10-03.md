# Requader: founder losses and user-ended run — 2026-10-03

Candidate 0.0.7, installed Python `55892f2`, native build `dadd0fb` from
`56bcc38`. This follows the earlier startup equipment loop and paused repairs;
it is not a fresh colony or an uninterrupted test of one revision.

## Outcome and preserved evidence

The user ended the run after all founders died. Nanda, an emergency joiner,
remained alive. Native game-over and victory flags were false. Classify this
as **user-ended after founder loss**, not a zero-survivor native game over.

| Founder | Death tick from save | First observed death, UTC | Save evidence |
|---|---:|---|---|
| Garrett, 260 | 222769 | 07:22:31 | BloodLoss severity 1 |
| Alyssa, 254 | 233664 | 07:25:33 | BloodLoss severity 1 |
| Dawn, 257 | 347665 | 07:30:57 | Malnutrition severity 1; residual BloodLoss 0.09963 |

The director, observer and monitor were stopped; technical pause occurred at
07:36:37 UTC, tick 494099. The API save completed at 07:36:39 UTC. An in-game
naming dialogue had renamed the save to `Union of Atin (Permadeath).rws`.
Its final contents were copied before analysis. RimWorld and the GUI were closed;
hourly automation `laya` was paused. No replacement colony is authorized.

Local evidence is in `work/longrun-007-api-loops-20261003-0900`:
`final-ended-by-user.rws`, `final-ended-by-user-20261003-snapshot.json`,
`run-outcome.json`, `timeline.jsonl`, `decisions.jsonl`, `observer.jsonl`, and
`Player-final.log`. A streaming extraction in `work/requader-postmortem-20261003`
retains the compact decision timeline and death events without copying large
map payloads into the report.

## Confirmed failure chains

1. **Uncontrollable doctor accepted.** Legacy tending selected Dawn during an
   insulting spree. The native assignment also accepted that actor. The command
   was reported applied at 07:21:21, yet the next observation still showed
   `Insult` and untreated Garrett. A capability and job-outcome failure, not
   evidence that treatment had completed.
2. **Recovery stopped after tending.** Nanda did stop Dawn's bleeding: by
   07:26:37 all 26 wounds were treated and bleeding was zero. Dawn remained
   immobile, with no proper bed available for the native feeding job. No chain
   prepared a bed, rescued her and fed her. Food was stocked. Malnutrition
   reached 1 in the final save while blood loss was recovering.
3. **Weapon refusal did not persist.** The armed survivor repeatedly received
   the same optional equipment comparison and kept the current loadout.
   `improve_weapon_loadout` returned without recording the semantic deferral.
4. **Unrelated hunger reopened elective drug policy.** Its defer fingerprint
   included all need bands. Ordinary food changes reopened the same policy
   comparison despite unchanged medical and drug-policy circumstances.
5. **Combat alternatives disappeared.** Capability thresholds removed stationary
   defensive shooting from injured but mobile armed colonists. A traveling
   `TendPatient` job was protected like actual bedside care despite a nearby
   attacker, hiding the new survivor from tactical selection.
6. **Retreat acceptance was confused with useful retreat.** Repeated retreat
   orders preceded worsening rat injuries. Native retreat used an eight-cell
   displacement away from a pursuer without seeking covering allies. This
   evidence does not prove that every accepted retreat path was identical.
7. **Observer attribution and pacing were incomplete.** The death fallback
   prioritized the name BloodLoss regardless of severity. It thus hid Dawn's
   terminal starvation. Emergency pacing returned to 3x once bleeding stopped,
   despite the immobile patient's developing malnutrition.
8. **Urgency discarded blood already lost.** At tick 230248 Alyssa had blood
   loss 0.857 and bleeding 2.547/day, Dawn 0.412 and 4.324/day. The old urgency
   order selected the higher rate and hid the other patient. A constant-rate
   estimate gives about 3369 versus 8159 ticks to full blood loss; this is
   comparative context, not a guaranteed survival deadline.
9. **No assigned builder for a warm starter base.** Nanda's Construction
   priority was zero. The starter-base action enabled builders only in cold
   weather. Partially accepted layouts also require staffing and reconciliation.

## Reviewed corrections

- `colony_medical_recovery` consumes exact native patient/helper options and
  preserves every feasible patient's choice. It handles temporary spot, observed
  placement, rescue, active care, actual bed identity and feeding as distinct
  stages. Food-route feasibility determines recovery focus. Rejected or stale
  choices do not become success; lost replies can reconcile an observed job,
  which still does not prove completed care. Active care is not rescheduled.
- Legacy and native tending reject uncontrollable/incapable helpers. Emergency
  care can interrupt cleaning; routine cleaning cannot repeatedly interrupt
  itself. Mobile sick pawns retain bed-rest options when a real bed is reachable.
- Weapon refusal persists per pawn until equipment, compatible alternatives,
  skills or threats materially change. Native weapon/improvised classification
  retains the catalog while avoiding routine log/beer substitutions for guns.
  Drug refusal ignores ordinary hunger/rest drift. Clinical, policy or relevant
  stock changes reopen it; elective policy no longer displaces missing shelter.
- Starter construction staffs capable workers after real projects appear,
  protects current caregivers and keeps a validated partial plan for missing-cell
  retries after restart. A partial layout is not reported as a completed one.
- Injured shooters can use a native-verified stationary shot. The API preserves
  an equal ongoing attack's warmup. Actual patient targets distinguish traveling
  care from bedside work. Covered retreat has a shared 16-path-attempt budget;
  path and actual weapon rules remain native. Uncontrollable defense is blocked,
  not recorded as tactical progress.
- Observer pacing includes critical starvation. Native death events use the
  exact culprit when supplied; uncertain fallback captions retain multiple
  conditions rather than implying that BloodLoss is always the cause. Permanent
  treatment no longer queries the engine's invalid treatment-overlap property.
- The installer payload includes the new medical module. Repository ownership,
  module notes and the playtest journal record this outcome and these changes.

## Verification boundary

Final offline suite: **874 tests passed**. RIMAPI Release-1.6 builds against
1.6.4871 with zero warnings/errors. Route inventory: 297 registered routes,
243 literal Python calls, no missing or duplicate route; 20 dynamic calls are
covered separately by module tests rather than that static inventory.

Cached real-tokenizer audit: 16 module scenarios, 299 comparisons, maximum 308
state tokens, complete state retained. The new medical comparison uses at most
171 state tokens. An actual CUDA model probe initially selected the less urgent
recorded patient despite complete numeric context. Explicit comparative delay
consequences changed selection to Alyssa, with the earlier estimated bleedout.

**Residual model-quality finding:** in an additional illustrative equal-distance
two-doctor comparison, the actual model still selected the lower-quality/slower
doctor after both native tend stats and tradeoffs were visible. Requader had only
Nanda available at that stage; the added doctor's stats are test inputs, not
historical API measurements. This exposes an unresolved general ranking risk,
not a missing executor or claimed proof of good caregiver selection. Keep it as
a launch-readiness item. No doctor ID/name was hard-coded and no unfavorable
comparison was discarded from the evidence.

Corrections are reviewed against the recorded states, native DTOs and successive
decision/job readbacks. Tests must include refused and interrupted orders,
unchanged-state repetitions, changed eligibility, and progress through care
prerequisites. API acceptance alone is not treatment, rescue, feeding or escape.
No new gameplay is part of this repair. Runtime tactical success and long-term
survival remain to be observed only after a new user-authorized launch.

The startup `NullReferenceException` references in Player.log lack their original
stack and were not reproduced during this offline repair. They remain an open
diagnostic item, not a claimed fixed cause of the colony deaths.
