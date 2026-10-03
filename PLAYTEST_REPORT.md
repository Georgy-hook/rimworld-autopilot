# Colony playtest log

Current candidate: **0.0.7**. Historical tests below retain their own revision and version context.

This log tracks real runs and explicitly identified technical replays. Death records distinguish native causes, final-save conditions and uncertain observer captions. Wall-clock runtime excludes intentional development pauses when noted.

## 3 October 2026 — Requader startup loop, paused

- Fresh Crashlanded colony, Cassandra/Medium/permadeath, random tile 40061.
  Autonomous 3× play began around 06:09 UTC on the 0.0.7 candidate; GUI data-path
  correction caused a separate technical restart around 06:14–06:15 UTC.
- Founder equipment repeatedly chose an armed pawn excluded by its legacy
  executor. Empty non-applied results left the same candidate available. Combat
  later interrupted the repetition; that did not establish recovery.
- At the user's complaint, director and observer were stopped, progress saved,
  game paused at tick **216457** with **three living colonists**. Hourly automation
  and the local read-only monitor were stopped. No new colony was created.
- Subsequent work used offline recorded snapshots, fake transports with actual
  readback and local-model replay. These are technical tests, not autonomous
  gameplay. [Incident, repairs and verification](docs/audits/startup-loop-replay-2026-10-03.md).

### Requader continuation — 3 October, 07:21 UTC

- The user requested continuation of the same saved colony. Load briefly advanced
  216457 -> 217712 before the technical pause. No reset or new colony.
- The paused startup gate found unsupported `remain_drafted` at zero threats.
  Commit `55892f2` removes that no-threat option and repairs compact pawn flags;
  842 tests passed. Installed native DLL remains the build from `dadd0fb`.
- At 07:21:06 UTC the runtime issued `stand_down`, then colony decisions resumed.
  The colony already had severe untreated injuries: Garrett downed, Alyssa
  incapable of medicine, and Dawn in an insulting spree.
- Garrett's death was observed at **07:22:31 UTC**. Exact native cause was absent;
  last observed condition was severe blood loss. API accepted Dawn's treatment
  order at 07:21:21, but her subsequent job remained `Insult`; treatment was not
  verified. This executor/result discrepancy remains open.
- At 07:23:16 UTC, tick 225391, Alyssa was downed and Dawn mobile but bleeding.
  Nanda subsequently joined and began real treatment. The final outcome follows.

### Requader final outcome — user ended the run, 3 October

- Garrett died at tick 222769 and Alyssa at 233664, both with BloodLoss severity
  1 in the final save. Dawn died at 347665 with Malnutrition 1 and residual
  BloodLoss 0.09963. First observed deaths: 07:22:31, 07:25:33 and 07:30:57 UTC.
- Nanda had stopped Dawn's bleeding and treated all 26 wounds by 07:26:37, but
  the dependent patient remained without the bed/rescue/feeding chain despite
  stocked food. The old BloodLoss caption did not establish Dawn's terminal cause.
- The user ended the colony with Nanda alive. Native game-over/victory were
  false: record this as **user-ended after all founders died**, not everyone dead.
  Workers stopped, game paused at tick 494099 and final progress saved at
  07:36:39 UTC. The naming dialogue had renamed the save to
  `Union of Atin (Permadeath)`. RimWorld and the GUI closed; hourly observation paused.
- Confirmed repair targets include uncontrollable doctors, blood-loss urgency,
  missing care prerequisites, repeated weapon/drug deferrals, ineffective combat
  choices, and Construction disabled for the sole warm-biome builder. Recorded
  snapshots drive offline sequence tests; this does not replay or reverse deaths.
- [Postmortem, fixes and verification limits](docs/audits/requader-postmortem-2026-10-03.md).

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

## Test 9 — 26–27 September 2026

- Colony: Nails, Huck and Blas; fresh Crashlanded/Cassandra start, seed `16622162`, flat temperate-forest tile `67361`. Baseline save: `Laya Fresh Colony QA 2026-09-26`.
- This was a development playtest with pauses and controlled reloads from saved checkpoints, not one uninterrupted survival run. The warm-weather branch reached day 19. Its final observed state was saved as `Laya Fresh Colony Test 9 Heat Outcome 2026-09-27`.
- End state of that branch: Nails and Blas alive; Huck dead from heatstroke. The result does not establish long-term survival.

| Colonist | Outcome | Last reported condition / context |
| --- | --- | --- |
| Nails | Alive at save | Survived the heatwave after a passive cooler was finally completed. |
| Blas | Alive at save | Survived the heatwave in the cooled bedroom. |
| Huck | Died | Heatstroke reached its lethal severity while he was bedridden in a room above 50°C. |

Notes and main Laya failures:

- The first start failed early because a shelter plan collided with an ancient-danger site. The site-reservation fix was applied and the baseline restarted.
- A timber-wolf fight exposed a combat-role failure and killed Nails in one branch. A combat fix was made; the later branch was replayed from an autosave rather than presented as recovery from that death.
- When Huck was downed and hungry, the feed-patient endpoint rejected the task because it used the wrong RimWorld work-giver definition. The DLL was corrected to use `DoctorFeedHumanlikes`; Laya subsequently chose feeding and the order worked.
- During the heatwave, Laya first placed a passive cooler in an empty room. The room selection was changed to prefer the threatened patient's occupied room. In a later replay she placed the cooler there, but it remained a blueprint while Huck's heatstroke rose to about 96%; she even chose lighting before emergency construction. Huck died before the cooler was finished. Laya then repeatedly chose urgent cooler construction, and the room temperature fell from roughly 45°C to 23°C after completion. This proves the build path can work, not that her timing was safe.
- The compact decision context now surfaces the threatened patient, room temperature, and lethal heatstroke threshold earlier. A cold-weather mirror test is required to judge heating choices and timely construction.

## Test 10 — 27 September 2026

- Colony: Miu, Dennis and Ace; fresh Crashlanded/Cassandra start on flat tundra, seed `16622162`, tile `97817` (annual average about -11°C). Baseline: `Laya Fresh Cold Colony QA 2026-09-27`; pre-snap checkpoint: `Laya Fresh Cold Colony Before Snap 2026-09-27`.
- The cold snap was triggered in two controlled branches from the pre-snap checkpoint. This was an iterative playtest with pauses, a save reload and director restarts while fixing the observed heater defect, not one uninterrupted survival run.
- Final observed state: game tick 448,366 (about 7.5 in-game days), all three founders alive, no hypothermia in the final snapshot. Saved as `Laya Fresh Cold Colony Test 10 Outcome 2026-09-27`; the game is paused and Laya stopped.

| Colonist | Outcome | Cold-snap observation |
| --- | --- | --- |
| Miu | Alive at save | Developed hypothermia, cut the trees Laya designated, later refueled the generator through normal Hauling work, and had recovered by the final save. |
| Dennis | Alive at save | Worked outside while hypothermic; severity reached about 21% in the later cold-snap snapshot, then cleared after the snap. |
| Ace | Alive at save | Worked outside while hypothermic; severity reached about 23% in the later cold-snap snapshot, then cleared after the snap. |

Notes and main Laya failures:

- In the first branch, the colony exhausted its starting wood with an unfinished house, all three people became hypothermic, and a later raid kidnapped Miu while the house burned. This branch was saved as `Laya Cold Snap Failure Branch 2026-09-27` and was not counted as a survival success.
- In the replay, Laya eventually marked eight nearby birches for cutting and workers closed the roofed three-bed shelter. At that point the occupied bedroom was only about +5°C and hypothermia had already begun. The delayed tree order remains a weakness.
- Laya chose an electric heater in the actual occupied bedroom, but the previous implementation placed only the appliance blueprint. The working generator and its nearest cables were roughly 40 cells away. The director now checks for a live generator or charged battery, plans a clear-terrain cable route, includes its steel/build time in the choice, and offers a repair choice for an already-placed unwired heater.
- After restart, Laya chose that repair action itself. It planned a 44-cell conduit route; workers completed both the route and heater. The bedroom subsequently held about +20 to +21°C while the cold snap still put the exterior near -10°C. This directly verifies functioning electric heat, not merely an API-accepted blueprint.
- The wood-fired generator later produced 0 W with no wood in storage. The connected heater ran temporarily from a battery; Laya chose another nearby tree-cutting order, and a colonist later took a normal Refuel job. Generator output returned to 1,000 W. The decision context now distinguishes temporary battery power from sustainable fuel supply.
- All three founders survived and their hypothermia was absent at the final checkpoint, but the cold snap had ended and the outside had warmed by then. This run proves the heated-room and power/fuel path; it does not prove Laya will keep outdoor workers safe through a much longer winter or prioritize heated bed rest early enough in every case.

## Test 11 — 27 September 2026

- Colony: Nose, Batze and Sammy; fresh Crashlanded/Cassandra/Adventure start on a flat boreal-forest tile (`114408`, map seed `16622162`). Baseline save: `Laya Fresh Boreal QA 2026-09-27`. Played at 3× with observer pacing, interrupted for source and DLL repairs. The failure branch reached tick about 574,000, roughly 9.6 in-game days. Failure save: `Laya Fresh Boreal QA Test 11 Failure 2026-09-27`.
- End state: only Nose remained. The save's death letters explicitly give **malnutrition** as the cause for both deaths.

| Colonist | Outcome | Game tick | Last reported condition / context |
| --- | --- | ---: | --- |
| Batze | Died | 552,977 | Malnutrition; food had already fallen to zero while the construction queue remained long. |
| Sammy | Died | 559,989 | Malnutrition; earlier survived a club raid with injuries, then recovered most health before starving. |
| Nose | Alive at stop | About 574,000 | Sole survivor; had resumed cutting plants after the other two deaths. |

Notes and main Laya failures:

- Laya did unlock and equip the landing supplies, place a rice field and finish a roofed three-bed barracks. Nevertheless, it left free outdoor sleeping spots in service. On the first cold night after the barracks was completed, two colonists slept outside. The old deconstruction API reported success without removing the spots. A targeted `remove-sleeping-spot` API operation was built and deployed; the three spots disappeared in a live reload. This verifies removal, not every future bed-assignment decision.
- Laya queued more than 60 unfinished building jobs for roughly one assigned builder. It planned an exposed outdoor battery, which suffered the reported rain-short risk, and a livestock pen despite owning only a cat. The power blueprint now includes a roofable battery shed; a separate existing-battery shelter option was offered and partially built during the failure branch. The pen choice now distinguishes owned livestock from nearby realistically tameable wild candidates.
- With about two meals per person and no raw food, Laya chose stonecutting; at zero food it still chose sculptures, weapon shelves and other non-food work. A stronger low-food runway and construction-backlog comparison was added to model choice context, but **this alone did not prevent the malnutrition deaths**. It needs further architectural work and a fresh outcome test.
- The wild-foraging action misleadingly included birch trees and chopped stumps. With no food, Laya selected trees for their large wood yield. The subsequent repair separates wood cutting from other wild harvesting and tracks individual harvest designations to avoid retrying already-marked plants. This repair is under a controlled replay from the baseline, not credited to the failed branch.
- Laya repelled one human club raider, but sent rifle carrier Sammy into melee and left her temporarily below half health. Combat survived this encounter; that does not establish adequate tactics against larger raids.

## Test 12 — 27 September 2026

- Replayed Test 11's untouched boreal baseline with Nose, Batze and Sammy. This is a controlled development replay with pauses and restarts, not an uninterrupted survival claim. A food checkpoint was saved at game tick 356,775; a later food-crisis checkpoint was saved at tick 567,152. All three founders were alive at the latter checkpoint.
- At tick about 193,500 the colony had a roofed three-bed barracks and no remaining outdoor sleeping spots. Its battery was inside a six-cell room with zero open-roof cells. This verifies the new sleeping-spot removal and roofable battery blueprint in live play. The observer remained enabled at 3× and reissued speed 3 after a club raid had slowed the game.
- Food planning was still poor. At tick 274,175, 17 meals remained and the rice crop averaged about 25% growth, but Laya chose a freezer, sculptures and floor/building work before obtaining a replenishing food source. The first context repair added an estimated nutrition runway; at the later crisis, six raw food items held only 0.3 nutrition, but the wording mistakenly suppressed food urgency whenever raw food count was nonzero.
- The second repair bases food urgency on total nutrition regardless of raw item count and presents the runway and food tradeoff in the actual model questions. Automated tests cover both a 4.5-day runway with unready crops and a 0.1-day runway despite six raw items. By tick 663,846, all three founders were alive and Laya had issued early crop harvests, wild foraging and safe hunting orders, but stored nutrition was still only about 3.1. Live continuation is still under observation; no survival result is claimed yet.
- Laya's crop and wild-harvest actions now ask which eligible worker should carry out the chosen order, showing each worker's current job and competing Growing/Plant Cutting priorities within the model's short choice budget. In one live crop decision Laya chose Nose while Sammy was sowing; the API accepted Nose's Plant Cutting priority. This shows the nested choice and order work, but does not yet prove the selected worker completes the harvest. At about tick 899,451 all three founders remained alive, with zero stored food and Batze at roughly 37% health after another fight; the colony is still in danger.
- A follow-up shortened the worker choices to put `Grow`, `Cut`, current job, plant skill and health first. A live choice at about tick 930,000 showed both Nose (`Grow 2`, `Cut 1`) and Sammy (`Grow 1`, `Cut 1`) without truncating those facts; later only Sammy was eligible and the one-option worker step was resolved without querying the model. The three founders were still alive at tick 931,139, but stored food was just five raw items (0.25 nutrition), with Batze severely injured. Observer pacing was active at 3× after the second raid as well. Long-term survival remains unverified.
- **Final outcome:** the colony was lost, and RimWorld returned to its main menu. The director had still been making choices up to the Game Over screen; it had not frozen. Batze died with malnutrition as the observer's last-known condition. Nose's last-known condition was hypothermia. Sammy also died, but the observer only retained a leg bite as his last-known condition, so the exact cause is not verified. These observer captions are not equivalent to RimWorld's death letters.
- At zero stored nutrition the model had still been offered and selected discretionary tasks, including stonecutting and production. After this run, the food runway calculation was corrected so an explicit zero nutrition value cannot fall back to a misleading food-item count. When the colony has no more than about six days of food and its crops are still immature, feasible food acquisition is considered ahead of discretionary projects; the window shortens to 2.5 days when a crop is nearly ready. Laya still chooses among the feasible responses. This change passed unit tests; its live result is evaluated in Test 13 below.

## Test 13 — 27 September 2026

- Colony: Foxy, Nyx and Prince; fresh Crashlanded/Cassandra/Adventure start in temperate forest, map seed `16622162`, tile `111323`. Baseline save: `Laya Fresh Food Test 13 Baseline 2026-09-27` (1st Aprimay, 5500, 6h). Observer pacing was 3×, with development stops and a baseline reload. The first branch was saved as `Laya Fresh Food Test 13 Failure 2026-09-27`; a second branch replays the same untouched baseline with the later food-context repair.
- First branch: Laya unlocked the landing supplies, equipped the rifle and revolver carriers, planted an 80-cell rice field and completed a roofed three-bed house. Its later choices still left food reserves falling while the rice was immature. At about day eight it designated partly grown rice for early harvest despite mature wild edible plants being available. This sacrifices later crop yield when foraging could have supplied food sooner.
- First-branch outcome: Prince died at game tick 549,906; the game's death letter says **blood loss** after combat. Foxy died at tick 650,184; the death letter says **infection**. Nyx alone was alive at the last checkpoint, around tick 713,000. This is a failed colony, not a successful survival test. The game-save endpoint preserved the failure branch without overwriting the baseline.
- Repair under replay: the model now sees estimated yield from nearby mature edible plants and from immature crops, plus the explicit future-yield cost of cutting rice early. At the start of the replay, Laya selected nearby mature berry bushes twice and designated them for harvesting. Stored raw berries rose to 222 items by the first afternoon, while the founders and rice field remained intact. This confirms the foraging order can be selected and executed; whether Laya sustains the colony or later repeats an early-rice mistake remains under observation.
- Third branch: reloaded the same untouched baseline after clarifying that the landing supplies contained 50 ready meals. Laya unlocked those supplies on the first afternoon, armed Nyx and Prince, built a roofed three-bed barracks, planted rice and repeatedly chose mature berry foraging. At the 10th Aprimay checkpoint all three founders were alive; 28 meals plus 20 raw food items were stored (about 26 nutrition). The first branch had already lost Prince to blood loss before this point.
- The replay also exposed a narrower decision-list bug: with about four days of stocked food and some rice already harvestable, the six-day food focus hid most ordinary work and repeatedly presented early rice cutting. Laya chose three ten-plant early cuts despite available mature bushes. This is not a confirmed all-clear on crop judgment. The director now leaves broad colony work visible when any field crops are harvestable and offers destructive early crop cutting only below a 2.5-day stored-food runway. Wild edible foraging remains available as its own choice. Automated tests cover the four-day/harvestable-field case; the updated director was deployed into this live branch for continued observation.
- An early slaver caravan offered three affordable people while the colony held 913 silver. Laya chose to talk but then declined every purchase, so population stayed at three. The offer and choice were visible in the log; no trade API failure was observed. Whether the model properly weighs recruitment against food and labor needs remains open.
- Latest controlled checkpoint: `Laya Fresh Food Test 13 Foraging Checkpoint 2026-09-27`, saved around tick 690,900 on 12th Aprimay at 18h. Foxy, Nyx and Prince were all alive, upright and not bleeding; 19 meals plus 118 raw food items represented about 23 stored nutrition (roughly 4.8 days for three people). This passes the first branch's death ticks of 549,906 and 650,184, but is not a long-term survival result. After the live director update, recent choice logs showed foraging, hunting, hauling, growing and construction, with no further early-rice option at a four-to-five-day food runway. Earlier rice designations from before the update were still being worked, so a fresh untouched-baseline replay remains the cleanest way to quantify crop preservation.
- Clean replay from the untouched baseline with the full updated director: the landing meals were unlocked on day one, all 80 rice cells were sown by day three, and on day four Laya selected mature `Plant_Berry` (131 expected berries) while early rice cutting was not offered. By day five at tick 253,512, stored raw food had risen to 122 items; all 80 rice plants were still present at about 27% average growth, and all three founders were alive. This verifies the berry designation was actually executed and supplied food without sacrificing the young rice. Later outcome is still under observation.
- At day eight, all 80 rice plants were still present at roughly 63% average growth and food remained for about three days. By day ten, ripe individual plants had reached 100% growth and workers harvested them normally; stored raw food climbed above 500 items. The clean replay log recorded several berry-foraging decisions and **zero selected early-rice cuts**, although that emergency option was briefly offered as the food runway crossed 2.5 days. All three founders were alive. Saved the clean branch as `Laya Fresh Food Test 13 Clean Replay Day 10 2026-09-27`.
- A separate concern emerged after the harvest: only Prince had Cooking enabled at priority 1, tied with his Handling, Construction, Plant Cutting and Hauling jobs. The campfire and simple-meal bill exist, but the meal stock was down to four while more than 500 raw food items were stored. Whether Laya rebalances work and converts that harvest into meals is not yet verified.
- Continued clean branch, cooking diagnosis: Laya chose a new staffing option and assigned Nyx Cooking priority 1, weighing her low skill and food-poisoning risk against Prince's competing work. Prepared meals nevertheless stayed at zero. On 3rd Jugust, four colonists were present (Chris had joined), raw food was above 300 items, and the completed campfire still had an active simple-meal bill. The live map and the saved game showed **zero spare wood logs**. Staffing alone did not address the fuel bottleneck; the API does not expose the campfire's exact internal fuel level, so a direct fuel reading is not claimed.
- By the 7th of Jugust, this no-fuel branch still had four living colonists but only 73 raw food items and zero meals; one person had been downed. It was preserved as `Laya Fresh Food Test 13 No Fuel Branch 2026-09-27`, not counted as a survival success. The director now offers nearby tree cutting when a wood-burning cooking station has few meals, raw ingredients and fewer than 50 spare logs, even with no unfinished construction. It also explains the fuel tradeoff in the model's food context. All 314 automated tests pass.
- Controlled replay from the clean day-ten checkpoint with the updated director: the model saw zero spare wood, a completed campfire and more than 500 raw food items. It selected `harvest_nearby_trees` itself and designated eight nearby poplars. A worker cut the first tree; the map then showed 27 wood. By 13th Aprimay at about 12h, the stock was about 105 wood, four prepared meals existed, and Foxy was actively working a cooking bill at the campfire. All three founders were alive. This verifies the choice, tree cutting and actual meal production in this branch. It does not yet establish that Laya will maintain a durable fuel reserve or avoid later food crises.
- Later in that replay the spare wood fell back to zero while the campfire still produced meals from its remaining fuel. With roughly three days of food and mature crops, the existing food-window logic showed 34 broad choices; tree cutting was present but repeatedly lost to already-set work priorities and an already-configured bill. The low-fuel window now retains concrete food, fuel and care choices while filtering those no-op repeats. In the paused live snapshot it left three choices: cut nearby trees, designate safe hunting, or harvest wild plants. Laya then selected another tree order itself. It subsequently issued several more batches before the first was completed: at tick 1,017,184, 47 marked trees still stood, representing about 1,303 potential wood. To avoid flooding the work queue, new tree batches are now withheld while at least 120 expected wood remains designated and standing. This backlog guard passed unit tests; the pending trees have not yet been observed becoming stocked wood in this later branch.
- Follow-up on the same clean replay: the pending tree orders eventually became real work. Prince and Nyx were both observed on `HarvestDesignated` jobs, while Foxy was on `Refuel`; the number of designated standing trees dropped to one and loose wood logs on the map rose to 658. By tick 1,176,211 (5th Jugust, 20h), all three original founders were alive. The map held about 1,008 wood logs, 12 prepared meals and 244 raw food items (23 stored nutrition). Saved as `Laya Fresh Food Test 13 Foraging and Fuel Outcome 2026-09-27`. The clean replay selected mature wild berries ahead of premature rice cutting, then later harvested ripe rice normally; it also recovered cooking fuel and prepared meals. This is a roughly 20-day development checkpoint, not proof of a stable or winning colony. The excessive original tree designation remains a known work-queue mistake even though a guard now prevents further batches while a large standing backlog exists.
- Release-readiness continuation: at tick 1,290,528 the same three founders were still alive with 17 prepared meals and 84 raw food items, but the construction endpoint returned its maximum 100 unfinished projects for only three colonists. The actual queue may have been larger because that endpoint truncates its list at 100. Saved this branch as `Laya Test 13 Construction Backlog QA 2026-09-27`. This is a release blocker: Laya had added optional rooms and facilities while many previous blueprints remained unfinished. A new candidate-capacity check now defers optional new construction when the existing queue exceeds the available builders' capacity, while preserving Laya's choices among finishing projects, staffing, food and genuinely urgent construction. A paused live snapshot with 100 reported projects showed optional freezer, sculpture, shelf, hospital, floor, stonecutter and defensive plans removed from the immediate choice set, with construction completion still available. The final version of this check and the no-op cooking-bill filter pass automated tests, but a sustained live replay of those final changes is still required before release.

## Test 14 — 28 September 2026

- New Crashlanded/Cassandra/Adventure colony in temperate forest, world seed `laya-006-independent-20260928`, tile `67364`: Cray, Holloway and Max. Saved untouched baseline `Laya Test 14 Fresh Colony Baseline 2026-09-28`. Source director and observer were run with the observer maintaining 3×; development stops, save reloads and direct diagnostic API actions below make this a controlled playtest, not one uninterrupted autonomy claim.
- Holloway became enclosed by four built walls while food lay a few cells away. More than 20 accepted `Ingest` orders could not overcome the blocked path; she died in the failed branch. After a direct wall-removal rescue proved reachability, the director was changed to detect the completed-wall enclosure, offer `open_blocked_food_path`, exclude the trapped pawn as builder, and stop issuing futile eating orders. In a replay from `Laya Test 14 Before Holloway Death 2026-09-28`, Laya chose to open a wall, Holloway escaped, ate, and her malnutrition cleared. This verifies the repair in that saved situation, not all possible pathfinding traps.
- The actual stonecutter recipe was `Make_StoneBlocksSlate`; the old hard-coded `CutStoneBlocks_Slate` returned 404. Recipe selection now resolves the desired block product against the completed table's live recipe catalog. This repair passes a test; a complete stonecutting production replay remains open.
- At the 3rd Jugust butchery checkpoint, 16 animal carcasses existed, 11 in `Laya Animal Carcasses`, with no Butcher spot/table or butchering bill. The director could configure a bill on an existing table but had no candidate to build the free spot. A first direct diagnostic action placed a spot and a separate bill; at 3× one carcass was processed and squirrel meat appeared. That direct intervention alone is not credited as Laya's choice.
- A controlled replay from `Laya Test 14 Butchery Blocker Before Fix 2026-09-28` showed Laya eventually selecting `build_butcher_spot` herself after the raid. The first implementation used a stale base anchor and put the spot far from the carcass pile; it also left the bill for a later decision. The final action uses the actual carcass-position median, places a spot adjacent to the piled corpses, and immediately adds and verifies an unsuspended `ButcherCorpseFlesh` bill in `Forever` mode. Hunting is no longer offered as an immediate food replenishment choice while the carcass pile has no processing station.
- In the final autonomous 3× replay, Laya chose the revised spot-and-bill action; the spot was at `(156,149)` beside the carcass cluster around `(153–157,145–147)`. At the `Laya Test 14 Autonomous Butchery Verified 2026-09-28` checkpoint, carcasses fell from 16 to 14 and raw meat included 12 squirrel plus 66 donkey. Cray, Holloway and Max were all alive and upright. This verifies the full butchering chain, while longer-term throughput and food stability remain open.
- In another Test 14 raid branch Cray was downed, then recovered to full health; Max was treated and developed immunity to malaria. This is positive post-fight evidence, but does not close the prior fatal bleeding/infection scenarios. One controlled replay logged a transient `/api/v1/pawn/job` 404 because a target disappeared between planning and execution; the command executor now records a stale target and returns to replanning rather than putting the whole director into error backoff. That code-level repair passes a regression test and still needs a live race recurrence to verify. Token-budget probes now use bounded tokenization to avoid an 8192-token warning when measuring oversized context; the live effect remains to be checked.
- The source Python suite passes 324 tests. The current installed app remains 0.0.5; Test 14 is source playtesting, not a release candidate or packaged smoke test. The colony is paused at the verified checkpoint.


## Test 15 — 30 September 2026: saved-colony continuation

- Resumed random tile 39150 from the latest permadeath checkpoint (tick 151,144), rather than starting a new colony. The save was initially named Laya 007 Butchery Layout Baseline and was renamed by the game to Tium (Permadeath) after settlement naming. The previous logs stopped when the game closed around 16:18 UTC on 29 September; no overnight survival is claimed.
- Nine rejected construction orders targeted wood floors while loose wood was zero and all three beds remained unroofed. RIMAPI now exposes each project's remaining material costs and usable loose stock. The director skips zero-stock projects, preserves fully supplied frames, chooses a tree cutter, and keeps starter wood for enclosure before optional floors or the first research bench. Six old floor blueprints were cancelled during this controlled verification.
- Laya selected eight nearby Drago trees and Pepper as cutter. At tick 191,869 all three founders had roofed beds, the house had 23 completed walls and a door, loose wood was 88, and no construction project remained. This verifies the resumed situation; the updated floor-free starter template has unit coverage but no new untouched-start replay yet.
- Laya independently placed an active Forever-bill ButcherSpot. Rat meat (13) and leather (7) appeared, confirming actual processing. A later snapshot showed two active local butchering bills and an active simple-meal bill. The colony dog was healthy and fed and had a sleeping spot.
- Generic catalog choices previously omitted descriptions, and Laya built a GibbetCage inside the shared bedroom despite having no slaves. Building purposes now reach the model, the ideology endpoint exposes slave count, corpse-display buildings receive contextual eligibility and room/doorway checks, and generic placement also checks hazards. The existing cage was uninstalled by a healthy worker during this controlled test. The full building catalog remains known.
- A later knife raid downed Pepper and badly wounded Yakov. LayDown targeting a bed while the pawn lay far outside it exposed a false already-rescued check; rescue completion now requires the actual bed position. An occupied doctor also blocked a second patient's self-tending because urgent-care detection ignored self_tend keys. The care gate and downed-care choice set now preserve that urgent option. By tick 357,755 both founders had zero bleeding and were physically in beds; Pepper was still downed. Their complete recovery and a simultaneous bleeding recurrence after the final fix remain open.
- Both combat-capable founders met that raid without guns even though their starting rifle and revolver lay nearby. Once shelter is usable, safe loose firearms and no armed fighter now defer optional expansion while food, temperature and care remain available. Pacifists cannot consume those equipment assignments. A new battle with this final behavior remains unverified.
- A 20-second CPU sample found no duplicate directors: director 0.13%, observer 0.06%, monitor 0.01% of total CPU on 20 logical processors, versus RimWorld 8.84%. CUDA and four CPU threads are used. This average does not rule out the reported short CPU spikes.
- Verification: 357 director/observer/combat tests pass; RIMAPI Release-1.6 builds with zero errors and warnings. Startup Player.log still contains duplicate NullReferenceException entries without their original stack; this is an open investigation, not a resolved defect. Save reloads, technical pauses, floor cancellation and cage removal make this a controlled continuation rather than an uninterrupted autonomy claim.

### Test 15 continuation: infection and medicine

- At 10:40:14 UTC the observer detected Yakov's death. The saved death letter explicitly says Infection; his infection severity was 1.0, immunity 0.8077755, and last tend quality 0.401919. Bleeding had stopped, but low Patient/PatientBedRest priorities allowed ordinary work. The medical API's direct TendPatient job also omitted medicine. Zero bleeding and rising summary health were insufficient recovery criteria.
- Direct tending now uses the game's reachable medicine selection and patient care policy. Bed-rest orders use the requested bed and restUntilHealed. Human and colony-animal health expose immunity, lethal severity where applicable, tend quality and remaining tend ticks. Laya sees those values before prompt truncation, can select roofed-bed recovery between treatments, and excludes recovering disease patients from routine labor. Severe infection is urgent without bleeding; the observer slows to 1x while a dangerous immunity race is unresolved, otherwise retaining 3x. The observer reads detailed medical state every five seconds.
- Controlled integration replay on a copy of the earlier wounded checkpoint: tick 332,498 to 336,630 at 1x, director and observer stopped. Sunny's accepted tending job targeted actual industrial medicine (ID 3828); medicine stock fell 29 to 24, Pepper's bleeding fell 3.481 to 0, and treated wounds showed qualities about 0.63–0.94. Two nonbleeding wounds still required treatment at the end. This proves real medicine use and bleeding control, not complete recovery or infection immunity. The current two-survivor save was restored afterward; Yakov remains dead in the continued party.
- Weapon shelving was repeatedly rebuilt outside the planner's original search rectangle. Its actual site is now persisted and pending shelf projects block duplicate plans. The existing three shelves at (134,142–146) were recovered from the first successful order; nine redundant untouched steel-shelf blueprints were cancelled in the controlled continuation.
- Updated verification: 364 tests pass; the installed RIMAPI DLL matches the tested build. At tick 626,839 Sunny and Pepper were upright, displayed full summary health and zero bleeding, and the three beds were roofed in a room around 22.85 C versus about 44.39 C outdoors. Prepared meals were only three despite abundant raw food and zero wood: fuel and actual cooking output remain a priority for the next slice. Disease survival after this repair, emergency surgery options, long-term population growth and victory remain open live checks.

### Test 15 final outcome: colony ended before the first full hourly review

- Final autonomous continuation on `404068d`: 11:44:11 to 12:26:50 UTC, tick 640,064 to the GameEnded letter at 1,524,263 (about 14.74 game days). No intervention occurred during that segment. The earlier technical medical replay is excluded from this outcome.
- Laya accepted Rowe, a child with paralytic abasia, and Sunny carried him to a bed. A man in black, Ducky, later joined after a raid downed the defenders. Population rose from two to three and then four before losses; this was not a zero-growth episode.
- Sunny was kidnapped at tick 1,346,555. The observer subsequently received her death at 12:18:46 UTC; the final save confirms Dead and BloodLoss severity 1.0. Death from blood loss after kidnapping is supported by that state, but no stored death letter specifies her cause. Rowe died of Heatstroke at tick 1,458,675; Pepper died of Heatstroke at 1,523,864. Both causes are explicit game letters. Ducky was kidnapped at 1,496,697 and remained a living world pawn in the final save. Dog Mug died of Blood loss at 1,510,991. The colony ended with everyone dead or gone, not with every former colonist physically dead.
- Bedroom temperatures reached 49.78 C while occupied. Heatstroke progressed on bedbound Rowe despite summary health 1.0; Pepper's wounds were bandaged and bleeding stopped, but heatstroke reached 0.941. Cooling never became sustainable. The built passive cooler and campfire had no fuel in the final save; loose wood stayed at zero or near zero.
- A def-name filter only offered wood plants containing Tree. The actual base had mature SaguaroCactus nearby. An offline comparison of the stored living snapshot at tick 764,170, using the recorded anchor (143,136) and cleared order cooldowns, offered no wood harvest on the old code and 12 Saguaro plants (169 expected wood) plus two stumps on the repaired code. No orders were executed in this comparison.
- Human patient feeding recorded 34 choices: 16 accepted jobs and 18 HTTP 500 refusals. Raw-only feeding requests could precede the game's eligible hunger category. There was no sampled malnutrition on Rowe, and feeding failures are not claimed as the direct cause of his death. The API now returns explicit skipped outcomes, checks normal hunger/bed/reservation rules and avoids interrupting tending. Human medical context exposes feeding eligibility and raw-food acceptance; the director checks them and reports applied=false honestly.
- Buildings now expose actual power and fuel state. Laya can order a selected hauler to refuel an existing facility. Wood harvest accepts every WoodLog-producing plant, preserves thermal fuel reserves, and remains visible during dangerous heatstroke. Thermal deterioration also slows the observer to 1x. These are future behavior repairs, not a survival replay of the lost party.
- Ducky repeatedly alternated focus_fire and prepare_undrafted while the raid was distant. Active movement, shooting and aiming orders now block immediate undrafting. Assault lord toils and Wait_Combat no longer count as staging merely because an enemy pauses. Combat victory and kidnapping prevention still need live validation.
- One decision cycle logged No feasible options for worker_pawn. Live profession options and worker selection now both exclude mental breaks and active immune disease. This closes the reproducible eligibility mismatch; the failed log did not retain the exact selected profession.
- Actual local butchery continued to produce horse, hare and dromedary meat/leather. Pemmican research completed; PackagedSurvivalMeal reached 30.5%. Prepared meals were zero in sampled snapshots after the opening survival meal, no new trade was recorded, and no power grid was operating. Three shelves remained; no new residential altar was observed. A saved ship_escape doctrine did not amount to successful long-term execution.
- The director stopped normally on Game Over at 12:26:50; Python stderr logs were empty. The observer erroneously continued pacing the empty map until the review paused it at tick 2,611,073. The observer now requires zero colony population plus a terminal game letter, pauses and stops; empty caravan/loading states alone do not trigger this. Hourly automation laya was deleted after the terminal outcome.
- Verification: 375 director/observer/combat/hourly regression tests pass; RIMAPI Release-1.6 has zero warnings and errors. Installed DLL SHA256: 621C9BAA5200A831DC1B6C6A879D34815B560015A648497D9CA6FF8A8669A7BB. The final saved ruins verified real fuel/power values, explicit non-applied feeding/refueling responses and terminal observer pause. No new colony or revived-survivor run was started. Positive refueling and future survival remain unverified; startup NullReferenceException and short CPU spikes remain open.

## Test 16 — Closed-game capability audit (2026-09-30)

The user requested code fixes and a report while leaving RimWorld closed. No colony, replay or live gameplay was launched for this package.

- Added live plant/crop suitability, blight cutting and dying-yield recovery; farm reporting includes hydroponics and standing crops after a selection change. Forecasts use normal maturity, fertility, temperature and calendar growth time.
- Wood providers follow the real WoodLog product, including fibercorn and stumps. A full sowing catalog no longer hides harvestable wild trees. Special-tree descriptions and a defer option reach Laya. Wood purchases use actual live deals.
- Added normal augmentation recipe/stock/patient/ideology/doctor/bed context and native deferred choices, exact part purchases and ordinary surgery bills without preliminary amputation.
- Added complete loaded weapon definitions, actual instance stats and compatibility, exact recipient/item choices and no-swap outcomes; trained animals expose real master/follow/release state and normal training/combat commands.
- Added researched soil/hydroponic greenhouse layouts, supported roofs, clear paths, continuous conduits and actual material/peak-power requirements. Short-season research uses a startable prerequisite frontier.
- Full suite: 466 tests pass, including 35 capability tests. Release-1.6 build uses 1.6.4871 references and has zero warnings/errors. Real cached Laya tokenizer check retains both long alternatives inside its 312-token state budget (294 tokens). Installer payload includes the new module.
- These are source/compile/behavioral-fixture checks, not positive game execution. Native model decision quality, actual operations, blight recovery, animal combat, greenhouse crops, runtime performance and the previous colony's survival blockers still need live validation. Startup NullReferenceException and reported short CPU spikes remain open.

Detailed Russian audit: [Capabilities, 30 September](docs/playtests/Capabilities-2026-09-30.md).
