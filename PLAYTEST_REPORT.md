# Colony playtest log

App version: **0.0.5** (development branch; the tests below may use unreleased changes).

This log tracks real, unattended runs. “Cause” is the last condition reported by the game API, not a medically certain cause of death. Wall-clock runtime excludes intentional development pauses when noted.

## Test 1 — 25 September 2026

- Colony: Pepe, Triv and Bolton; Doc joined later. Cassandra, seed `16622162`.
- Decision log: 07:59–09:08 UTC, about 45 minutes of active decisions with a development pause between 08:29 and 08:53.
- End state: Pepe and Triv were both downed; the run was stopped rather than observed to their deaths.

| Colonist | Outcome | Time (UTC) | Last reported condition / context |
| --- | --- | --- | --- |
| Doc | Died | 09:06 | Scratch wound to arm; the group had engaged a rhinoceros in melee. |
| Bolton | Died | 09:07 | Bruise to torso; the same rhinoceros fight. |
| Pepe | Downed at stop | 09:08 | Could not be fed because no mobile feeder was available. |
| Triv | Downed at stop | 09:08 | Cause of incapacitation was not established from the retained log. |

Main Laya failures: it repeatedly chose to wait despite unfinished survival work, then sent multiple colonists into melee against a rhinoceros. Post-fight care could not feed the remaining downed people.

## Test 2 — 25 September 2026

- Colony: restarted from an earlier save with Pepe, Triv and Bolton; same seed `16622162`.
- Decision log: 09:16–10:22 UTC, about 66 minutes elapsed.
- End state: Pepe remained as the sole colonist.

| Colonist | Outcome | Time (UTC) | Last reported condition / context |
| --- | --- | --- | --- |
| Bolton | Died | 10:16 | Arm wound infection. |
| Triv | Died | 10:17 | Scratch wound to torso; the death caption incorrectly repeated on later camera passes. |
| Pepe | Alive at stop | 10:22 | Sole survivor. |

Main Laya failures: wounds and infection still overwhelmed care; the camera replayed Triv's death instead of showing it once. Laya attempted orbital trading without powered communications infrastructure, and the shelter was still unfinished. A visiting trader transaction did succeed earlier in the run (five medicine purchased).

## Test 3 — 25 September 2026

- Colony: seed `16622162`, Cassandra, new three-person start.
- Observed: 10:56–12:00 UTC; approximately 60 minutes of active play plus a four-minute development pause.
- End state: one survivor (Skagnetti); the game was paused for fixes. The founding colony failed to sustain its population.

| Colonist | Outcome | Time (UTC) | Last reported condition / context |
| --- | --- | --- | --- |
| Merandil | Died | 11:20 | Stab wound to torso; injury and infection were present during the run. |
| Ivy | Died | 11:47 | Scratch wound to neck; wounded after a melee raid. |
| Sleepy | Died | 11:48 | Stab wound to arm; downed during the same raid. |
| Skagnetti | Alive at stop | 12:00 | Joined later; the only remaining colonist. |

Notes and main Laya failures:

- The first housing plan was too large and displaced from the dry-site check. Walls, beds and floors did not become a complete roofed home; several beds existed but colonists still used ground spots.
- Laya queued dozens of projects while wood and construction labor were scarce. It continued to consider research and hunting with shelter unfinished.
- During a close melee raid, two armed colonists selected a melee response rather than keeping a shooting lane. Both eventually died. The choice context exposed their weapons, but the final tactical comparison omitted a retreat-and-fire option.
- The observer restored 3× after raid speed resets; death captions and camera dwell were checked. The game UI and API were cross-checked during the run.
- Fixes prompted by this test are being developed and must be judged by a fresh colony, not credited retroactively to this run.

## Test 4 — 25 September 2026

- Colony: Shen, Lee and Miray; Kaiser joined later. Cassandra, temperate forest on seed `16622162`, tile `20942`.
- Observed: about 13:27–14:37 UTC, approximately 70 minutes elapsed, including development pauses and director restarts. The colony reached 1 Jugust 5501.
- End state: Miray and Kaiser alive. Lee and Shen were kidnapped in separate raids; neither was confirmed dead. The run was stopped because the remaining crew had no eligible builder, no stored food, and no completed cooking station.

| Colonist | Outcome | Time (UTC) | Last reported condition / context |
| --- | --- | --- | --- |
| Lee | Kidnapped | About 14:00 | Taken by Trash Packers in the first major raid; a future rescue opportunity may appear. |
| Shen | Kidnapped | About 14:29 | Taken in a later raid after repeated fighting and mental breaks. |
| Miray | Alive at stop | 14:37 | Could haul and grow, but could not do Construction. Food reserves were empty. |
| Kaiser | Alive at stop | 14:37 | Joined after Shen was taken; was hunting, but could not do Construction. |

Notes and main Laya failures:

- The verified dry-site start produced a roofed barracks, but real beds were initially scattered outdoors or in distant rooms. A later roof collapse and raids left only sleeping spots.
- Starting food ran out without a finished cooking station. Laya could designate hunts and harvests, but no one left in the colony could build a campfire after Shen was captured.
- Shen suffered exhaustion- and mood-related breaks. Persephone, a bonded yorkshire terrier, died during the run, further affecting Miray's mood.
- The first rescue handler repeatedly accepted an unrelated quest for Makoto as if it rescued Lee. This was fixed during the run; the mistaken acceptance is not a successful Lee rescue.
- Other live fixes addressed notification letters interrupting the decision loop, an oversized decision context, a lost medical-bed/fire-target selection, and rapid work-priority reversals. They need a fresh colony to verify their long-term effect.

## Test 5 — 25 September 2026

- Colony: Buck, Greg and Kelly; Cassandra, seed `16622162`, tile `42283`.
- Observed: 14:53–19:03 UTC, approximately 60 minutes of active Laya decisions after excluding development pauses. The game reached 6 Jugust 5500, about 20 in-game days.
- End state: Buck and Greg alive; Kelly kidnapped. The run was saved as `Codex Laya QA 2026-09-25 Test 5 End` and stopped for a fresh-start test. This is not a claim that both survivors later died.

| Colonist | Outcome | Time (UTC) | Last reported condition / context |
| --- | --- | --- | --- |
| Kelly | Kidnapped | About 18:45 | A knife raider attacked him while unarmed; both riflemen had fallen out of firing range and repeatedly held a distant line. |
| Buck | Alive at stop | 19:03 | Major break risk and a later daze; still the most capable builder. |
| Greg | Alive at stop | 19:03 | Sad wandering and food scarcity; still harvesting when observed. |

Notes and main Laya failures:

- Earlier in the run, a residence plan overlapped the generator room and sealed its access door with a wall. The blocking wall was removed during testing. New site selection now reserves completed buildings, blueprints and prior room footprints, but this run started before that change; a new colony must verify it.
- A visiting merchant had live affordable food and medicine in the new trade preview. Laya genuinely compared `trade_now` and `skip_trade` and chose to skip (about 41% versus 59%); no transaction occurred. An earlier direct transaction proved the RIMAPI execution path, but it does not count as Laya trading. Orbital traders without powered infrastructure are now reported as unavailable rather than presented as a fake 100% skip.
- The game completed an enclosed pen with a gate and marker during the run. The new live animal context withholds pen-dependent taming and livestock purchases until a suitable pen exists; a fresh colony is needed to judge the full build-before-tame sequence.
- During the raid, the combat log showed zero of two guns in range while Laya continued choosing `firing_line`. The descriptions and compact battle context now state that holding this line cannot fire or advance to protect an exposed civilian. This was fixed after Kelly was kidnapped, so the outcome cannot be credited to the fix.
- With zero stored food and a starving pawn, Laya still chose to cut wood. The hierarchical choice labels now expose the immediate food tradeoff without forbidding Laya's choice. After the update, a live choice visibly favored harvesting wild plants over hunting or changing work priority, but the long-term food supply was not recovered in this run.

## Test 6 — 25 September 2026

- Colony: Gennady, Four Eyes and Miko; Cassandra, temperate forest on seed `16622162`, tile `18296`. Same initial save retained for a controlled replay.
- Observed: 19:16–19:50 UTC, about 34 minutes elapsed including diagnosis and code changes; the director ran for most of the interval. The game reached spring 5500.
- End state: Miko died; Gennady and Four Eyes survived. Schlitzer joined later. Saved as `Codex Laya QA 2026-09-25 Test 6 End` before restarting with the combat fix.

| Colonist | Outcome | Time (UTC) | Last reported condition / context |
| --- | --- | --- | --- |
| Miko | Died | About 19:29 | Scratched repeatedly by a manhunter guinea pig while unarmed and isolated; bleeding rose sharply. The last observed body was at map cell (84, 89). |
| Gennady | Alive at stop | 19:50 | Rifleman; remained healthy during the fight. |
| Four Eyes | Alive at stop | 19:50 | Revolver user; remained healthy during the fight. |
| Schlitzer | Alive at stop | 19:50 | Joined after Miko's death. |

Notes and main Laya failures:

- Laya built a roofed barracks with completed beds, designated crops, and built a pen before taming. These are visible improvements over earlier starts, but do not establish long-term survival.
- On the animal attack, Laya repeatedly chose `hold_cover`. The unarmed Miko was one or two cells from the attacker while the two gunmen drifted 35–50 cells away, beyond effective range. The tactic had picked distant barricades as cover; it did not preserve a firing lane. Miko bled out while the shooters returned.
- After the enemy died, the post-combat choice set contained only a direct treatment order (plus defer/resume); it did not offer carrying the downed patient to a completed bed. Successful API acknowledgement did not prove the doctor reached him in time. Both the cover selection and the missing rescue choice were changed after the death and require replay verification.
- The desktop GUI became sluggish while reading a very large decision log, and the director intermittently reported a Windows character-encoding error after applying an action. The GUI history is now byte-bounded, and the director configures UTF-8 output at startup; both still need installed-runtime verification.

## Test 7 — 25 September 2026

- Colony: Gennady, Four Eyes and Miko; controlled restart from the Test 6 initial save, Cassandra, seed `16622162`, tile `18296`.
- Observed: about 19:56–21:02 UTC, roughly 66 minutes elapsed including development pauses and a director restart. The colony reached 3 Jugust 5500, approximately 17 in-game days.
- End state: all three founders alive; Miko recovering from wounds. No new colonist joined. The in-game save was copied to `Codex Laya QA 2026-09-25 Test 7 End` before updating the mod.

| Colonist | Outcome | Time (UTC) | Last reported condition / context |
| --- | --- | --- | --- |
| Gennady | Alive at save | 21:02 | Healthy, equipped with a bolt-action rifle. |
| Four Eyes | Alive at save | 21:02 | Healthy, equipped with a revolver. |
| Miko | Alive at save | 21:02 | About 70% health, recovering in a bed after animal and knife-raider attacks. |

Notes and main Laya failures:

- The colony completed roofed rooms, beds, fields and a pen, and maintained substantial raw-food stores. Outdoor beds still existed and the indoor-bed reassignment was not proven by this run. A three-person colony for over two weeks remains a growth failure; the newly offered prison/rescue path did not produce a recruit in this interval.
- At 20:17, a manhunter guinea pig reached unarmed Miko while the rifle and revolver users were more than 110 cells away. Five consecutive `hold_cover`/`firing_line` orders produced no shots and no movement from either gun. Miko was downed but eventually rescued.
- At 20:50, a knife raider reproduced the defect at a 50–57-cell gun gap: both shooters had zero clear firing lanes, while Laya ordered Miko into melee and he was downed again. The raider was defeated and Miko was rescued. The model saw that no guns could shoot, but its selected defensive tactic had no effective movement execution.
- The C# tactic executor was changed after these encounters to advance a blocked or out-of-range shooter toward a reachable firing lane, and to make an isolated unarmed `guard_shooters` pawn retreat/regroup instead of attacking alone. The melee-role prompt now states the actual support gap and gun coverage. These changes passed the build and unit suite but were not yet active for the recorded battles.
- The decision-log writer briefly stopped on a Windows file-sharing error during a diagnostic read. It now retries and spills records instead of crashing; the director restarted successfully. The RIMAPI save endpoint returned a null-reference error, so the end save was made through the game's Save menu and copied without overwriting earlier test saves.

### Focused combat replay — 21:27–21:29 UTC

- After rebuilding and loading the new RIMAPI DLL, a two-squirrel manhunter pack was triggered against a disposable copy of Test 7 End. This was a short integration check, not another full colony run. The preserved Test 7 End save was reloaded afterwards.
- At first, both ranged colonists were positioned by `focus_fire` with zero immediate attacks. Later, Laya chose `hold_cover`: Gennady moved while Four Eyes fired, and a subsequent `hold_cover` cycle reported both gunmen attacking the remaining squirrel. This confirms the new tactic can re-position a shooter without idling the other gun.
- Both squirrels were neutralized. Gennady was scratched to roughly 67% health and received in-game treatment; Four Eyes and Miko remained unhurt in the observed snapshot. The engagement did **not** reproduce the exact two-gun wall obstruction from the earlier guinea-pig attack, so that case remains a targeted regression test rather than a live victory claim.
- The `focus_fire` planner now reissues orders if an existing `AttackStatic` job has no actual line of sight, instead of treating a target inside weapon range as proof that the pawn can shoot.

## Test 8 — 26 September 2026

- Colony: Masaru, Freddie and Stumpy; fresh Cassandra start, seed `16622162`, tile `93098`. The run reached 10 Decembary 5500, game tick about 280,000 (roughly 4.7 in-game days). Observed between about 08:22 and 10:03 UTC with development pauses and controlled combat/trader replays. The paused QA save is `Laya Trade API QA Before 2026-09-26`.
- End state at the saved checkpoint: four living colonists, but only Masaru and Freddie mobile. Jared and Hakuja joined after Laya accepted their transport-pod offers; both have paralytic abasia and cannot yet work. Stumpy died. This is population growth on paper, not a four-worker colony.

| Colonist | Outcome | Last reported condition / context |
| --- | --- | --- |
| Stumpy | Died | Game letter states blood loss. She had severe bleeding after the squirrel engagement; rescue and tending orders were issued, but bleeding continued. |
| Masaru | Alive at checkpoint | Mobile, about full health. |
| Freddie | Alive at checkpoint | Mobile, wounded in the squirrel engagement, about 90% health. |
| Jared | Alive at checkpoint | Joined through a transport-pod decision; bedbound with paralytic abasia. |
| Hakuja | Alive at checkpoint | Joined through a transport-pod decision; bedbound with paralytic abasia. |

Notes and main Laya failures:

- When Laya was deliberately stopped during module replacement, it could not react to the initial squirrel attack. This is distinct from the real tactical issue: unarmed Freddie ran away from the rifleman, leading the squirrel out of firing range. A saved-combat replay after the guard/regroup fix showed Freddie moving back toward the shooter instead; Laya then fired and killed the squirrel, with Freddie still standing. This is one focused replay, not proof against every animal attack.
- The newly working choice-letter API let Laya accept Jared and Hakuja, moving the headcount from three to five before Stumpy's death. The offers described paralysis, but the decision context did not explicitly distinguish headcount from available labor. This was corrected after the run, without forcing Laya to reject disabled recruits.
- A visiting slaver offered three adults at affordable prices; Laya chose to review the trade, lowered the cash reserve to zero, then chose to buy nothing. A second slaver offered a six-year-old with extensive work restrictions and an older adult with pyromania and psychite dependency; Laya again declined. Both were genuine model choices. A separate manual API transaction successfully purchased one named person and increased headcount from four to five; that transaction was rolled back by loading the pre-purchase QA save and must **not** be credited to Laya.
- Stumpy's care sequence exposed a remaining failure: a rescue bed was reused for another patient, and an accepted treatment order did not guarantee completed treatment before the doctor received another task. Bed occupancy/reservation and the compact bleeding-risk context were changed after this death. The new C# field and Python selection passed automated tests but still require a live medical replay.
- At the checkpoint the colony had a small completed shelter and beds for the bedbound joiners, but several larger building blueprints remained unfinished. With only two available workers, labor capacity, food, shelter and medical care remain the main survival constraints.
