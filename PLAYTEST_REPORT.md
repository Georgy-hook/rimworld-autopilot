# Colony playtest log

Current candidate: **0.0.8**. Historical tests below retain their own revision and version context.

This log tracks real runs and explicitly identified technical replays. Death records distinguish native causes, final-save conditions and uncertain observer captions. Wall-clock runtime excludes intentional development pauses when noted.

## 5 October 2026 — Goberium/Theentbum, material and wildlife repairs

- Latest same-colony continuation: **11:59:40.658 UTC**, tick474194, speed3.
  At12:00:15/tick489278 all three founders were alive, without downed/bleeding;
  Holster and Kitty actually performed HarvestDesignated, Vega Ingest. The
  preservation refusal at11:59:45 yielded to rest at11:59:54 and harvesting
  at12:00:05. Earlier Heatstroke, cooking fuel and food remain observation
  concerns. One CUDA director/four CPU threads, observer and read-only monitor;
  hourly review resumes no earlier than13:00 UTC. Technical pauses are excluded.

- Installed source **5bdab53**, native package **688acbf**: **1066 Python
  tests pass**, native Release-1.6 has zero errors/warnings. Six wildlife and
  inspiration observations were verified in the actual loaded game. The
  nonviolent finishing order was rejected without changing Vega's job/draft.
  No living downed hostile remained for a positive finishing test.
- Ichabod8483's actual training is Obedience3/3, available Release0/2;
  Rescue/Haul are blocked by body size. A real CUDA model replay chose Release
  with Vega, but issued no game orders and is not completed learning.
- The first continuation at11:42:59 UTC exposed 17 repeated preservation
  defers. Their 250-tick memory expired before the next ten-second cycle;
  purpose refusal remembered only representative alternatives. Native storage
  context also treated standing Plant_Dandelion as stored food. Same progress
  was preserved at tick473870 for repair. Deferrals now retain stage/subject
  scope and a120-second/30000-tick floor; actual item food is separated from
  grazing. Native hunting also survives the emergency food focus and replaces
  both legacy hunt paths when its endpoint is available.
- At paused tick474194, installed API reported7.1 nutrition in actual berries
  and agave, ten separate grazing plant definitions, and zero Plant_* storage
  options. A real model replay deferred preservation, retained that refusal
  across a synthetic40000-tick advance, and then chose resilience_rest. This
  replay sent no game orders. Loading advanced324 technical ticks; no rollback.

- Earlier technical pause: **10:45:27 UTC, tick378997**, all three founders
  alive, upright and not bleeding. Current save filename is **Theentbum
  (Permadeath)**; saved XML verifies the same world seed, tile and founders.
  Director stopped and hourly automation paused for the user's reported
  finish-downed issue and hunting/inspiration/animal-training audit.
- Three finish decisions at10:43:05,10:43:15,10:43:25 selected Vega770 despite
  `can_fight=false`. Actual job stayed `Wait_Combat` while API calls returned
  acceptance. Generic melee also omitted native `killIncappedTarget`, required
  to continue attacking downed targets. Target Rok21897 disappeared from the
  living roster by10:43:34; no kill by Vega is proven. Prior severe bleeding
  is evidence of a possible alternative cause, not a confirmed death cause.
- One fresh random generation: tile **55904**, world seed
  `laya-thermal-progress-20261005`, Cassandra/Medium/permadeath; baseline tick40.
  Founders Holster767, Vega770 and Kitty782. Kitty arrived with nonlethal Asthma.
- Speed3 autonomy began **10:03:28 UTC** on Python5876caf/native0927d3c.
  At **10:09:31**, technical pause/save tick143482 preserved all three alive.
  The last wooden wall lacked four logs; 776 steel was available, but no beds
  were roofed. Timber leaves omitted measured demand and repeatedly deferred;
  sleep/work changes also reopened the same rest defer.
- Python **a724457**, **1004 passing tests**, preserves complete parameter facts,
  presents actual bounded harvest cost and validated structural replacements,
  and remembers clinical/material refusals across normal state drift. Native
  DLL unchanged. A real CUDA replay locally persisted a rest defer and then
  selected steel replacement; it sent no game orders.
- The **same colony** resumed **10:34:51.965 UTC**, tick143482. At10:35:06 Laya
  autonomously selected replacement of Wall20213 with Steel. Native readback
  observed Blueprint20651. At **10:35:38, tick159558**, there were **23 finished
  walls, one door, three roofed beds and no unfinished projects**. Room52 had
  open_roof_count0, temperature33.22C; outside30.92C. All three founders were
  alive, upright and not bleeding;33 survival meals remained. Laya next selected
  equipment. Roof completion does not establish cooling or long-term survival.
- Hourly observation re-enabled, first review no earlier than **11:38 UTC**.
  Run evidence: `work/longrun-007-thermal-progress-20261005` outside the repo.
  [Material context and defer audit](docs/audits/material-parameter-context-2026-10-05.md).
- Esia remains a separate suspended technical run at saved tick200289 with all
  three alive, two downed. Its later21-tick native reassignment check is technical
  verification, not recovery or a new autonomous outcome. Neither save was rerolled.

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


## Recovery run final outcome — 2026-10-03

Nation of Kobutalora / Unhisda Nation, random tile 10268, Cassandra/Medium, dd28b1d: autonomous 08:30:45–09:19:29 UTC, ticks 1560–928750 (15.45 game days). Native Game Over: Yunxin BloodLoss, Dweeb PsychiteAddiction per native letter, Virgil LungRot; Barbara kidnapped. Zero colony population does not mean all former colonists died. Final save and logs preserved; game and runtime stopped.

Integrated repairs cover clinical transition scheduling, guarded doctor reassignment, nonimmune lethal disease, actual sanitation jobs, shot/job continuity, weapon assignment churn, material-adjusted building costs and unaffordable bench recovery. Real-model replay exposed ordering bias and empty waiting; root attention facts, feasible overdue-shelter progress and a known-doctor Pareto frontier now bound these choices. 907 tests pass, native Release-1.6 build clean; API audit has no missing literal routes. Real CUDA replay selects construction in both option orders. These checks do not establish end-to-end survival or victory. [Detailed causal audit](docs/audits/recovery-root-causes-2026-10-03.md).

## Esia reboot continuation — 2026-10-05

Esia, tile 4516, BorealForest, world seed `laya-progress-20261003-1312`, Cassandra/Medium: October 3 startup never reached a valid director cycle, while the observer advanced the game. The reboot save was already at tick 50889. Three technical continuations on October 5 verified initial commands, forest placement and real construction, but exposed further care/thermal scheduling failures. The last preserved save is tick 200289: Red and Furr downed, Moon upright and tending; all three alive. The house has ten walls and one door, no verified warm room. Furr's lost toe and bleeding are real accumulated damage and were not reverted. The run was saved and suspended at 09:30 UTC, then the game closed at 09:48:59 UTC. This is not Game Over and is not a clean autonomous benchmark.

Repairs and their verification boundaries are recorded in [the reboot causal audit](docs/audits/reboot-resume-2026-10-05.md). The user-requested next clean run must use a new randomly chosen tile and fresh memory; retain the Esia evidence separately.


## Theentbum: first hour, infection death and bed-rest correction — 2026-10-05

The same Goberium/Theentbum colony on tile55904 exceeded one continuous hour after the 11:59:40 UTC continuation. At the 13:08 check all three founders were alive, population four, with real butchering and Microelectronics progress. Food/fuel remained unstable and the endings API returned a collection-modified error.

Kitty subsequently died of Infection, confirmed by the native save letter; she first disappears from the minute timeline at 13:26:16 UTC. Right-lung infection overtook immunity despite observed rest. Repeat tend quality fell to about7%; the last sampled severity/immunity was0.915/0.7512. The relationship to the independent repeated rest orders is not established. This is an individual death, not the end of the colony.

A user-reported Bed Rest loop was confirmed: 185 assignments of one chronic patient's bed in a bounded log tail. HeartArteryBlockage's zero-gain Immunizable component was mistaken for an immunity race, and rest was reissued during travel and meals. Preserved technical pause13:44:51 UTC/tick1994622; source b326db5, native package f2eddbd installed. After287 load-transition ticks, the same party resumed around13:56:23 UTC at3x. No new colony or memory reset.1071 tests, clean native build, installed API refusal before mutation, and17 post-resume records without a rest assignment support the specific fix. At13:58:31/tick2037862 four residents were alive and upright. This short regression is not evidence that all medical or survival failures are solved. [Bed-rest causal audit](docs/audits/bed-rest-loop-2026-10-05.md).

## Theentbum: approved rollback, Vega death and worker-selection stall — 2026-10-05

The hidden-window continuation was discarded with the user's explicit approval: the in-memory tick 2054622 could not be saved, while disk remained at 1994622. Normal visible recovery resumed the same colony at 14:20:01.733 UTC from a verified paused baseline of 1994988 (366 loading ticks). Disk persistence and progression past the old autosave boundary were verified. Do not combine the discarded 13:56 continuation with this recovered timeline.

Vega died at tick 2149108, observed at 14:29:09 UTC. Native letters confirm Lopas entered a murderous rage targeting Vega after Kitty's death, and Vega was beaten to death. Holster then suffered catatonia after her brother Vega died. At tick 2514747, Nevil and Lopas were downed with extreme malnutrition (0.892 and 0.832); Holster was catatonic with malnutrition 0.600. Zeeray 60037 had joined and was performing FeedPatient. Four living residents remain; this is not Game Over.

At 15:05:36 UTC the director began repeating ValueError('No feasible options for worker_pawn'). Observer correctly paused on director_not_ready; game time remained 2514747 through the hourly review. Nine errors were recorded by 15:26:18 UTC. The same frozen snapshot reproduces a contract mismatch: live_work_options advertises 20 work types with Zeeray eligible, but worker_criteria excludes the only mobile pawn because he is feeding a patient. All 20 worker lists are empty. The set_work_priority selection path can thus throw globally; while paused, the protected care job cannot finish. The precise selected work type was not recorded by the failing log. No model replay, code repair or game mutation was performed during this hourly observation.

The autonomous segment lasted about 45m35s, not a full uninterrupted hour, and advanced about 8.66 game days. Food and fuel failures predate the pause: campfire fuel 0, zero meals, 7 raw food items, zero wood; Microelectronics 1578/3000, no recorded sales. Existing ButcherSpots have active flesh-butchery bills. No repeat of the specific rest_46181_20163 loop was found in the bounded tail covering the whole recovered segment. The endings endpoint succeeded in this snapshot, but its earlier intermittent failure remains open. Last disk save: tick 2474622 at 14:54:15 UTC; current in-memory progress was not saved during read-only observation.

Evidence and detailed Russian report: workspace outputs/colony-hourly-20261005-1522.md and run-directory hourly-20261005-1522-* files. Hourly observation remains active; no new colony, manual memory reset, restart or forced game order.

## Same colony: reboot, starvation transport failures and conditional technical restores — 2026-10-06

After the user's reboot, the disk checkpoint was2515596 with four living residents. Worker-choice repair a6cde49/package5f84255 was already installed. Visible load produced a technical paused baseline2517462; the first diagnostic continuation began09:00:09 UTC at1x for severe pre-existing starvation. The child died of Malnutrition at2530056, observed09:03:49. Paused endpoint2538649 was preserved. Doctor priority0 incorrectly suppressed forced care scans; the wound-only scheduler also omitted the unwounded starving child. Generic patient facts lacked severity and comparative deadlines.

Source62ead7c/package593f56c plus Python2462c29 exposed normal forced rescue/feed/tend and exact scoped care replacements. Under the user's conditional permission for technical failures, the first diagnostic branch was restored to2515596, then verified at2515657. The09:49 continuation rescued the child, but deferred feeding and took the distant patient. A newly added native care gate incorrectly classified zero-gain chronic heart immunity as an unfinished infection, hiding later feeding options. The child died again, observed09:53:48; native save letter confirms Malnutrition. The paused2531238 branch and memory were retained. Neither death is silently removed from the journal; these discarded segments cannot be included in the final continuation's survival duration.

Corrective source cb79e9f and package4b4fbf8 fix chronic immunity capability, preserve expected job/patient bindings through the legacy medical executor, and use actual carrying DTOs. Windows process checks now reject retained terminated process objects. All1145 Python tests pass; the308-route audit has no missing literal calls or duplicate routes; native Release-1.6 has zero warnings/errors. GUI rebuilt from4b4fbf8. Exact payload hashes are retained privately.

A direct diagnostic FeedPatient on the discarded three-survivor branch changed hunger0→0.828 and Malnutrition0.959→0.950, ticks2533529–2536412. This tests real ordinary food consumption, not autonomous choice. Then the verified four-survivor checkpoint2515657 was restored again for the corrected native block; the final load added993 technical ticks, with stable pause and disk persistence at2516650. No manual colony-memory reset or resource/health editing.

Final autonomous continuation began10:14:28.938 UTC on the same tile55904. Normal target3x, observed1x due severe starvation. At10:15:23/tick2519642 all four residents remained alive: Laya had actually rescued and fed the child (hunger0.894), and the caregiver was rescuing the distant adult. No direct technical feed command occurred in this final segment. Food production, adult recovery and long-term strategy remain unsettled; model replay still shows option-order sensitivity. Startup NullReferenceException duplicates remain unresolved. Hourly observation is being restored against this final segment, with technical branches reported separately.

See [the care-yield audit](docs/audits/starvation-care-yield-2026-10-06.md) for contract, source evidence and verification limits. Private Russian report: workspace outputs/worker-food-recovery-20261006.md.

Follow-up10:21:46 UTC/tick2541826: four residents alive, actual hunger0.670/0.526/0.791 for the three patients, distant patient's bleeding0. The child is no longer downed and actually Harvesting. No new direct intervention. Director/observer/monitor heartbeats are fresh, stderr empty; startup Player.log ceased growing after loading. Hourly observation active, first full review11:22 UTC. These are short recovery results; adults remain downed and food/fuel/gene-dependency strategy remains unverified.
## Theentbum: resolved growth window forced pause — 2026-10-06

After the 10:14 continuation, the minute timeline first showed tick2571140
paused at10:30:37 UTC; the last lower tick was2569291 at10:29:36. All four
residents remained alive. Python was responsive but the resolved, archived
growth dialog exposed no API button and held native forcePause. Repeated speed
commands could not advance it. The user reported the stop.

Source dd80168/native package ba80742 add native readiness and scoped OK for
informational growth windows, observed closure and bounded retries; unmade
awards retain Society's choice path.1153 tests passed,308-route audit clean,
Release-1.6 zero warnings/errors. Current progress was saved at2571140 and
reloaded without rollback or memory reset;21 technical ticks reached2571161.
The same archived letter was reopened normally for a technical replay:
generic close removed zero windows, stale identity was rejected, the installed
director's exact OK closed it, and observed traits/skills were unchanged.
This replay is separate from autonomous play.

The same colony resumed at11:00:12 UTC. At11:02:18/tick2578430 all four were
alive and upright; the formerly catatonic resident had hunger0.974 and DoBill,
the child was Ingest. Normal decisions resumed after combat. Severe
malnutrition still required emergency1x, normal target3x. The modal-frozen
interval and technical pause are not continuous autonomous survival time.
The short continuation does not establish sustainable food or a completed
ending. Positive live unmade-award selection, loading NullReferenceException
duplicates and redundant hazard-guard logging remain separate verification
items. [Causal report](docs/audits/growth-dialog-pause-2026-10-06.md).

## Theentbum: final defeat after growth-modal recovery — 2026-10-06

Native Game Over arrived at tick 2771391. The observer stopped at 11:48:46 UTC
and the director completed at 11:48:46.607, paused tick 2771459, population 0,
caravans 0, no victory. All four final residents died: the child was beaten to
death at 2623288; the adult with go-juice dependency died of BloodLoss at 2633482;
the remaining female founder and last caregiver died of Malnutrition at 2721806
and 2770992. Native letters and the final saved XML confirm these causes.

Installed source dd80168/package ba80742 had resumed this same colony at
11:00:12.222, tick 2571161. The last segment lasted 48m34s and advanced 200230
ticks to Game Over, about 3.337 game days. Technical pauses/replays and the
earlier discarded child-starvation branches are excluded. The successful
growth-window acknowledgement did not establish survival; no repeat of that
modal stall explains the terminal losses.

Starvation triggered an allied Berserk letter; combat orders targeted that
ally. Accepted tending did not prevent his blood-loss death. The last
caregiver became catatonic from recreation deprivation, and both remaining
patients starved. Repeated production deferrals and unavailable-fighter waits,
empty cooking/cooling fuel, scarce prepared meals and final exposed beds are
recorded as follow-up findings rather than a proved single root cause.
Research barely advanced and no sale was recorded; 90 silver was a caravan gift.

The prior autosave 2751140 was retained separately; the final 2771459 save was
verified on disk at 12:04:54.955 UTC. Logs/memory are preserved privately.
Hourly automation is paused, all Laya/observer/monitor workers are stopped,
and RimWorld remains on the final pause. No code changes or new run were made
for this documentation request. [Final report](docs/playtests/Theentbum-2026-10-06.md).

The full retained history contains about 3h56m of elapsed autonomous phases
over 5–6 October; 48m34s is only the last segment. Total progression from
baseline tick 40 was 46.189 game days, including technical loading ticks.
[Duration history](docs/playtests/Colony-lifetimes-2026-10-06.md) qualifies the
phase boundaries and distinguishes discarded branches.

The subsequent user request authorized offline repairs and 0.0.7 preparation.
Confirmed production cooldown, kitchen footprint, allied Berserk/care and
clinical prompt defects were corrected; 1174 tests and native compilation pass.
At that preparation checkpoint these changes had not yet been played in the
ended colony or a new one. See [0.0.7 readiness](docs/RELEASE_READINESS_0.0.7.md).

## Published 0.0.7: new random colony ended before first hourly review — 2026-10-06

The separate run on tile 119304 used source f6786a2/package 5dc1168. One generation,
Cassandra/Medium/permadeath; autonomy began 13:16:44 UTC at tick 25. Native Game Over
arrived at 308496 and was detected 13:56:28 UTC: approximately 39m44s, 5.141 game days.
Population 0, caravans 0, victory=false; the final pause is 308589. Director,
observer and read-only monitor exited without manual process termination.

Native letters confirm three founder deaths from BloodLoss and the emergency
man-in-black death from WoundInfection. The sole fighter first had megaspider
wounds; the two pacifist founders later acquired rat-teeth wounds. The survivor
stopped his own bleeding, ate and rested, but right-leg infection 0.996 exceeded
immunity 0.6527 before death. Treatment quality was initially 9.8%, later 24.5%.

Remaining findings include tending/retreat alternation for the same caregivers,
nine redundant self-tend HTTP 500s while care was already running, 44 medical
policy deferrals and 10 rest choices returning exact_care_job_in_progress. These
are observed competing/repeated orders; their individual causal contributions
need separate investigation. Initial shelter and some food/recreation facilities
were actually completed. No research or sale was recorded; final campfire fuel 0
despite 161 accessible wood. The bounded tail contains 451 decision records;
the full decisions log was not read.

The first hourly review after 14:22 UTC confirmed the already ended run. The last
disk save 300000 predates the terminal death; live evidence, letters and memory
verify the outcome. One pre-autonomy NRE remained unchanged in Player.log.
Hourly automation is paused. No fixes, replay, new colony or memory reset were
performed during observation. [Detailed outcome](docs/playtests/Release-007-2026-10-06.md).

## Authorized offline repairs after the release run — 2026-10-06

At the user's request the terminal state was saved and actual disk XML tick
308589 verified at 15:10:53 UTC. RimWorld quit normally; process exit was
verified at 15:10:55 UTC. The hourly automation remains paused. This later
technical save is separate from the hourly review's older save at 300000.

The care/retreat conflict was reproduced offline: generic protection previously
disappeared at contact or on exposed travel. Clinical tending, feeding and rescue
now retain ownership in Python, native group tactics and the draft/attack APIs.
An exact `caregiver_retreat` choice lets Laya explicitly weigh abandoning one
patient against an immediate pawn/turret threat. Native POST rechecks the actor,
job, patient, carried pawn and escape route before replacing care. Group orders
cannot implicitly make that decision. The accepted exact escape retains its
actor until that native Job finishes; another doctor can still help the patient.
Rejected identical escape routes are bounded by native retry memory.

Redundant self-tend proposals are suppressed while the actor already provides
care; repeated native tending of the same patient preserves the current job.
Medicine inability is distinguished from a disabled automatic Doctor priority.
The 44 medical-policy deferrals were ceiling choices, not refusals to perform
treatment: the last survivor already permitted Best medicine. Proposals now
require an actual stock-access improvement or a genuine scarcity tradeoff.
Native context includes permissions/potency/quality limits for stocked
medicines and actual infection immunity/tend facts. Medical defer memory ignores
unrelated hunger changes and spans both 120 real seconds and 30000 game ticks,
unless a meaningful clinical or supply change occurs.

The repeated rest requests found an already observed LayDown. The previous
validation returned early without configuring recovery priorities; now the
selected priorities are set once while that exact rest job continues. Urgent
temperature maintenance can also be offered to a sick but mobile survivor,
with recovery cost stated explicitly and active clinical care still protected.
Rejected refueling no longer creates an issued marker, observed ongoing
refueling is not reoffered, and the native facility/fuel routes are checked.

Verification: **1204 Python tests passed**, including 30 added regressions/source
contracts; four prior protection expectations were updated to require an
explicit care suspension. Release-1.6 compilation: **0 warnings, 0 errors**.
Offline inventory: **308 routes**, no missing literal calls or duplicate routes.
No game, autonomous director, colony, rollback or memory reset was launched for
these repairs. Native job completion, escape success and future survival remain
gameplay checks. [Repair details](docs/playtests/Release-007-offline-fixes-2026-10-06.md).

## New random cold colony after the care fixes — 2026-10-06

One generation on tile 34927, seed laya-care-ownership-20261006,
Cassandra/Medium/permadeath, baseline tick 21. Initial temperature -30.8°C.
The three founders survived the startup interval; their roofed shelter had
13 walls, a door, a campfire and three sleeping spots, but serious hypothermia
developed while it was still cold.

A startup contract check caught native escape IDs omitted by collect_snapshot.
The same game was saved and paused at 16077, the Python forwarding fix passed
1206 tests, then the same progress/memory resumed at 17:11:49 UTC. No reroll,
rollback or game restart. At 17:12:18 UTC the bedroom reached 13.16°C and two
founders were actually Wait_SafeTemperature with declining hypothermia; the
third was eating and still seriously hypothermic. One finger acquired frostbite.
All three alive, no downed or bleeding. A real save at 17755 and subsequent tick
17779 were verified. Normal 3× with 1× for thermal emergencies; hourly observation
active, first full check after 18:12 UTC. Native care escape completion is still
unproven. [Startup evidence](docs/playtests/Care-ownership-start-2026-10-06.md).

At 17:16:58 UTC, tick 110889, all three remained alive, upright and nonbleeding;
hypothermia had cleared from their actual health records and frostbite was also
absent. The human bedroom was 19.78°C against outdoors -25.91°C. Two actually
rested and one ate. Observer returned to 3×. Stock declined to 27 initial meals;
this confirms early thermal recovery, not sustainable nutrition or survival.

First hourly review after 18:12 UTC: this same campaign is now Complete Union
of Leler (Permadeath). At tick 659160 food was zero, two founders were downed
with extreme malnutrition, and the empty campfire left the roofed bedroom at
-19.64°C despite 162 wood. Later two founders died from Malnutrition, native
ticks 666631/669060, observer 18:16:23/18:17:05 UTC. Continuous autonomy after
the startup pause was about 64m34s/65m16s. Native letters and exact_culprit
confirm both causes. A surviving founder plus the man in black remain alive;
GameOver/victory false at 18:19 UTC. No terminal colony outcome is claimed.

Open observed defects: ordinary assign_real_bed repeatedly calls medical
bed-rest and gets medical_rest_not_indicated; repeated refuel requests get
unsafe_fuel_route; zero food does not reliably keep effective food work ahead
of accepted ending requests and deferrals. Late hold_survival is an active
waiting loop with worsening patients, not a frozen Python process. Earlier
brief meat/meal production occurred, so the issue is sustained provisioning.
Current save XML 660000 and matching campaign ID verified on disk. Hourly
observation continues without runtime edits or game intervention. Further
evidence is appended to the startup playtest document linked above.

Closing 18:24:34 UTC, tick 694676: two alive. The surviving founder actually
received food (0.949, malnutrition 0.536), but remained downed with extreme
hypothermia 0.719. Stock food still zero, observer 1×, GameOver/victory false.

Second hourly review 19:16:07 UTC, tick 1176699: last founder and man in black
remain alive and mobile; a temporary nonworking hospitality guest is present.
No new colonist death confirmed. Thermal recovery/fueled campfire and cleared
construction backlog are real, but human reachable nutrition is zero and
malnutrition severe. Immature rice does not yet feed them. Bounded decisions
showed flowers/dye selected during starvation and repeated native-menu
monolith investigation, completion unverified. Production logistics returned
HTTP 200 with an empty JSON body twice, despite top-level module availability.
Save XML 1140000 and campaign verified; emergency 1×, observation active.

The last founder subsequently died from Malnutrition, native tick1205026,
observer19:24:35UTC, exact cause also in the native letter. Total autonomy
excluding the startup pause about2h14m06s. All founders lost; this is not
the terminal campaign outcome. At19:26UTC the man in black, guest and new
arrival remained alive; nativeGameOver/victoryfalse. Observation continues.

## Third hourly review after 20:12 UTC — 2026-10-06

At 20:16:48 UTC, tick 1385905, all three replacement/guest pawns were
starving. The man in black died from Malnutrition at native tick 1391721,
observer 20:18:25 UTC; native letter and exact_culprit agree. At 20:18:47 UTC,
tick 1393053, two remain alive: the temporary nonworking guest and a colony
member, now downed with malnutrition 0.855. The guest was Ingest with food
still zero; intake is not yet confirmed. GameOver/victory false.

Food did arrive briefly during this interval: sampled stock peaked at 11
and food levels rose. Sustainable supply still failed. Thirty of 31 rice
plants were harvestable at the main snapshot; early rice harvest requests
were accepted twice but delivered nutrition was unverified. A fresh caribou
corpse had a nearby third butcher spot and an active bill. Nine sampled
monolith requests reassigned the same unfinished investigation, four to the
working arrival and five to the guest. Hunger and malnutrition are present
in decision evidence, so missing all hunger context is not established.
The rice zone was configured for dandelions and zone count grew from six to
11. One bed blueprint failed because it would block the campfire interaction
cell, failure_count eight. Nested production logistics remains unavailable.

The new member belongs to PlayerColony in the save, with no host faction or
quest tags; permanent membership is supported. His prosthetic arm and child
MissingBodyPart entries predate this review and are not new surgical damage.
Campfire fuel 1.118/20, wood zero, roofed bedroom 28.35 C. Save XML 1380000,
mtime 20:15:05 UTC, same campaign and stable read verified. All processes live,
observer 1x for critical starvation, no forced pause. No runtime fixes,
orders, restart, rollback or memory reset. Observation remains active.

The new colony member died at 2026-10-06T20:23:54.841148+00:00, native 1411247, cause Malnutrition, corroborated by native letter and observer exact_culprit.
Follow-up 2026-10-06T20:25:06.253440+00:00, tick 1415177: 1 alive; GameOver/victory False/False. At 20:23:49 UTC the temporary guest actually had food 0.427 and malnutrition fell to 0.612; she had returned to InvestigateMonolith. The new member was then downed at malnutrition 0.998. No game or runtime intervention.

## Native terminal outcome of the care-ownership colony — 2026-10-06

GameOver verified on the same campaign at native tick 1565355; director
completed at 2026-10-06T20:38:21.644705+00:00, observer and monitor stopped normally.
Read-only confirmation at 21:09/21:10 UTC: zero colonists, zero caravans,
victory false, same campaign ID, game paused at 1565358. Total autonomy
excluding the startup technical pause was about 3h28m (26.1 game days).
All founders were already lost after about 2h14m. Native outcome is
"everyone dead or gone"; this does not establish that every guest died.
A late pawn died by gunfire, but the last guest's precise fate still needs
individual evidence. No runtime code, game orders, replay, restart, rollback
or memory reset was performed. Hourly automation is being paused.

Final evidence refinement: both last pawns' bodies are present on the map.
The temporary guest's corpse ID 27478 confirms death; observer first reported
it at 20:38:07 UTC with Unknown cause, no exact native tick. Blood loss had
risen to 0.917 while malnutrition was falling; blood loss is a plausible
cause, not native-confirmed. The late arrival was the Intro_Deserter reward,
not another man in black. She died by gunfire at native 1564956, corpse 27497.

New confirmed context defect: the actual accept-quest model input at
20:37:07 had empty decision_facts and only the event JSON prefix through
the pawn name. Empire hostility, immediate attacking trooper and colony
clinical state did not survive. _detailed_state clips the broad event context
to budget/6; agent.predict receives exactly that clipped visible_state.
Only 116 of 312 state tokens were used. Installed and source SHA256 match
for laya_decisions.py and colony_events.py. The API supplied the full quest
description; population flag was nevertheless false for its Reward_Pawn.
The selected imperial ending also conflicted with the quest's Empire hostility.

Five direct-tend plans were rejected while the same actor was actively
rescuing that patient. Distance declined, so this was not a frozen actor.
The mismatch between offered plans and care job protection remains open;
a successful alternative treatment is not established. A late rice harvest
request accepted designations despite worker=None and no eligible PlantCutting
worker. These are observations only. Runtime and game state were not changed.
The scheduled observation is PAUSED; RimWorld remains on the native final pause.

## Offline quest corrections after the final care-ownership loss — 2026-10-07

No colony was started or resumed and no game commands were issued. The recorded
deserter acceptance exposed loss of public consequences before inference; it is
not treated as the only cause of the preceding starvation losses. Complete
terms review, exact native rewards/accepters, stale-offer/roster guards and
cross-module interaction retry memory are now corrected in source.

All 120 installed named quest scripts passed complete-field/tokenizer transport
checks; automatic/internal scripts are included in that count. The Python suite
passed 1223 tests, native guards and index-mutation selection passed, and the
native bridge compiled. Actual cached Laya deferred the recorded deserter crisis
and accepted a prepared trade fixture without any game/API command. This is
offline evidence, not a successful colony or a guarantee of completing all quests.
See the [quest audit](docs/audits/quest-prompts-native-contract-2026-10-07.md)
for exact scope, script inventory and remaining live/monument gaps.


## Quest-review candidate: one new random colony — 2026-10-07

User authorized a new launch. Installed Python/package 3e7aa57, native source 75a0aea
and DLL 1.10.0+75a0aea after 1223 tests, 310 routes and 120 quest-context checks.
One random generation: Southwestern Hadussia Manifest League (Permadeath),
tile 16155, world seed laya-quest-review-20261007, map seed 16622162,
campaign 3323562a948840808815db9d068482ea; Cassandra/Medium.
Baseline 22; autonomy 07:21:26.913835 UTC, normal 3x, CUDA with 4 CPU threads.
No previous save/memory reused, no reroll/rollback or direct pawn orders.

At 07:25:51 UTC tick 93175 all three founders 985/988/991 were alive,
without downed/bleeding/conditions; 43 initial meals remained.
Actual 23 walls/door/3 beds, room 60 fully roofed at 23.04C;
the animal spot was outdoors. HarvestDesignated observed earlier, sustainable
food and actual quest/reward completion remain unproved.
Imperial ending selected alongside anomaly direction/raider diplomacy;
their consistency needs actual observation. Disk save 88618 and later 88742
verified the same campaign. One director/observer/read-only monitor, stderr 0.
One pre-new-game NRE Ref 8B5D0CDC without original stack remains unresolved;
Player.log did not grow after 07:20:18 UTC. Hourly heartbeat active,
first full check 08:23 UTC. This is an ongoing run, not a survival success.

Closing minute sample 07:28:25 UTC, tick 144397: all three alive without
downed/conditions, food levels 0.924/0.864/0.996, 36 initial meals and a
fully roofed bedroom at 23.31C. No hourly outcome is available yet.

## First quest-review hour — 2026-10-07

Same campaign 3323562a948840808815db9d068482ea, now named Roinor (Permadeath).
Primary evidence 08:28:03 UTC / 1074902: all three founders alive after
1h06m37s autonomous time, about 17.91 game days. Stock food/meals/raw 0;
Sandoval and Noah had early Malnutrition. Across 65 minute samples there
were no growing zones/crops, despite an active growing season. Raw food and
meal replenishment did occur earlier; do not report complete absence of cooking.

Bounded latest 100 decisions, 08:19:56–08:28:03 UTC: 66 hold_survival records,
all single_feasible_action with only that candidate. Nine at-risk crop harvests
were accepted: seven expected only WoodLog, one WoodLog/MedicineHerbal,
one WoodLog/RawBerries. The model criterion said dying crops without these
actual products; source permits arbitrary dying harvestable plants/trees.
This is a confirmed meaning mismatch; indefinite looping is not established.

Bonded Labrador Lilith 5045 died from native-confirmed Blood loss at 860978,
between minute samples 08:13:16–08:14:18 UTC, about 52 minutes after autonomy.
Her last four samples had 9 tendable wounds, quality 0 / ticks_left -1 and
BloodLoss 0.324/0.520/0.706/0.902. Successful tending was not confirmed.
An unrelated Beggars child's corpse is present; precise death cause/time unknown.

Generator 1000W powered one 30W lamp; Cooler 45765 was off in a different network.
26 fires/two home fires and a pyromaniac spree existed on the primary slice;
observer's emergency 1x was justified, ticks moved and force_pause was false.
Later closing 08:35:59 UTC / 1221140: all three still alive after 1h14m32s,
no downed/bleeding/Malnutrition, food 17 (meal 1 / raw 16) / 1.7 nutrition,
Sugar DoBill at Campfire 43337, Noah HaulToCell; Sandoval recovering FoodPoisoning.
Fires 0 then; extinction cannot be attributed uniquely to pawns versus rain.

Real research bench, Microelectronics 75/3000; no new permanent residents/sales.
Intro_Wimp and Hospitality_Refugee offers expired unaccepted; Beggars failed.
No actual new quest acceptance/reward verified. Production/logistics returned
valid data / 19 options on this slice; earlier empty-body fault remains open.
Same-campaign renamed disk save 1260000 / mtime 08:37:46 UTC checked stable;
no save POST issued. Single services healthy, stderr 0, Player.log unchanged.
GameOver/victory false; hourly monitoring ACTIVE, next 09:23 UTC.
No runtime/game edits, pawn orders, replay, restart, rollback or memory reset.

## Second quest-review hour and expanded verification — 2026-10-07

Same Roinor campaign, installed runtime unchanged at package 3e7aa57/native 75a0aea.
Primary 09:22:21 UTC / 2000507, closing 09:42:06 / 2316515:
2h20m40s continuous autonomy, 38.61 game days from baseline 22.
Founders lost from the map: Sugar 988 died at 1400386, observer 08:49:27 UTC,
exact Scratch after a red-fox predation letter (1h28m); Sandoval 985 died at
2004266, observer 09:23:27 UTC, exact Bruise / beaten to death after Berserk
(2h02m). Killer unverified. Noah 991 was kidnapped at 2109028 by Blight Party,
between 09:28:22 and 09:29:25 minute slices; not recorded as dead.
Hanson 78079 is the emergency man in black, not planned recruitment.
GameOver/victory remain false.

New animal loss: colony rhinoceros 39292 executed by cutting at 2040602 after
Noah's Slaughterer 2040038 / Malnourished. Earlier bonded Labrador blood-loss
death remains a separate, already recorded event. Rhino's last observed
Obedience/Release were unlearned, unwanted, no master/follow_drafted; sampled
tameness steps 4 to 1. Wild prey are excluded from pet losses.

Sixteen self_tend_985 attempts 09:19:58–09:22:16 rejected
care_actor_or_patient_changed; actor remained drafted/Wait_Combat while the
only observed hostile was downed. No completed care. Her subsequent beating
death is not attributed solely to this delay. Thirteen at-risk crop harvests
in primary100: nine wood-only, two herbs/wood, one herbs, one berries.
Twenty-three elective augmentation choices in closing100 were deferred;
no surgery or stocked bionic/prosthetic part. The same patient became hungry/downed.

Two growing zones finally appeared, both roses, 45/46 cells, edible yield 0;
fertility 1.0, year-round temperate forest. Five beds in three roofed rooms
17.5–19.6C, but primary barracks cleanliness -13.4/hospital -4.33 and corpse
contamination. Stove/cooler off, generator empty/output zero at closing;
earlier networks differed. Microelectronics 75 to 77/3000; trade ledger empty,
no comms/beacon, no planned permanent population gain or completed ending milestone.

User requested verification of pictures/layout, losses/raids and colony plans.
Added docs/COLONY_VERIFICATION.md and a saved-evidence-only card/layout utility
tools/colony_verification.py, five targeted tests passed. Actual cards were
generated for this run and the prior cold colony; no game/runtime behavior changed.
Base PNG verified between 2300371–2300384 at 09:39:08 UTC. Only camera/UI capture;
no jobs, speed, pause, save or memory commands. Native screenshot required
snake_case fields; HideUI did not visibly clear the interface. Five archived
raid announcements: two older threats disappeared across repeated minute
slices with all founders alive, one encounter unobserved, one downed attacker
in the later defense, latest raid kidnapped Noah. Complete attacker fates / a
count of clean repelled raids remain unverified.

Closing Hanson downed/hunger0, infection0.905/immunity1.0, raw34/1.7nutrition.
Later 09:59:41 UTC / 2608819: still alive, mobile; infection, malnutrition and
poisoning gone, hunger rose 0.065 to 0.258, Ingest then BeatFire. Recovery/food
are observed, stable supply is not: raw1/0.05nutrition, meals0. Campaign ongoing.
Disk 2280000 / mtime09:36:59 UTC verified; services healthy, stderr0,
Player.log still old3331bytes. Reports and comparison retained in private outputs.
No full decision history read; each tail at most8MB/100records. Hourly ACTIVE,
next10:23 UTC, expanded assessment now in the automation prompt.

## Quest-review colony concluded by user; 0.0.8 corrections — 2026-10-07

Single landing, 07:21:26–10:27:09 UTC, **3h05m43s**, 44.82 game days, no
rollback or technical pause during autonomy. Founder A died of Scratch at
1400386 (08:49:27 observation); Founder B died of Bruise at2004266
(09:23:27 observation). Founder C was kidnapped at2109028: death unverified.
The bonded dog died of Blood loss860978; the tamed rhinoceros was executed
by cutting2040602 during a starvation-triggered Slaughterer break. A later
arrival's Burn death2679614 is recorded separately, membership unverified.
Original founders lost; final campaign nativeGameOver=false/victory=false:
the man in black was alive/downed/catatonic/hunger0, and a fresh quest arrival
was healthy and performing Rescue. User ended this run; do not fabricate a
complete native defeat or attribute every loss to the same code defect.

Final2689439: food0/medicine0, no surviving real beds/research bench/generator/
stove. Sleeping spots outdoors, major fire visible in the final base screenshot,
roof-collapse letters. Several raid letters, last late attack2580000, do not
establish how many raids were repelled. Microelectronics77/3000, completed
sales0. Initial shelter succeeded; sustainable food, permanent growth and a
compatible ending plan did not. Full private report has named outcomes,
screenshots, map coordinates, bounded decision samples and save evidence.

Stopped the one director, observer and monitor, paused scheduled observation,
verified XML2689439/mtime10:27:35UTC and campaign, copied final save, then closed
RimWorld. Their last 'running' status files precede termination, not proof of
continued processes. No new map was generated during the repairs.

Recovery audit: [root causes and limits](docs/audits/roinor-recovery-2026-10-07.md).
1235 tests,311 routes(no missing literal calls/duplicates), native build0warnings/
0errors, six actual predator-intent boundary cases. Cached-model crop replay
now selects human food for both option orders; startup replay exits equipment
to hunting after two observed offline acknowledgments. Live completion remains
unverified. Development continues as0.0.8; published0.0.7 advanced to stablemain
anddeveloping without force. Obsolete merged branch names removed; historical
clean checkouts preserved detached. Branch rename closed oldPR4, so a replacement
candidate PR carries its continuation.

## Candidate 0.0.8: one new random landing — 2026-10-07

After offline repairs, source29df0ef and package2a3572d were pushed to
feature/0.0.8, draftPR5 into developing. Both native installs hash-match
DLL1.10.0+29df0ef; runtime files and rebuilt0.0.8GUI verified, backups retained.
Stablemain/developing remain publishedv0.0.7, not this working candidate.
Random tile10598, one generation, Cassandra/Medium/permadeath, no previous
save/memory reuse. Autonomy began11:11:50UTC, baseline22; normal3x.
First hourly observation no earlier12:13UTC/15:13MSK. Automationlaya ACTIVE.

Startup11:14:53UTC/65760: three founders alive, no new injuries/downed/bleeding.
One has an initial prosthetic leg and missing replaced components, not a new
operation. Two cannot fight fires, one cannot cook, one cannot perform medicine;
workforce limitations must remain visible. Food51meals/45.9nutrition, medicine34,
outside14.10C/growthseasontrue. Native orders unlocked supplies and built
22walls/door/3beds/torch; room23 remains outdoors(openroof58777), so neither
this physical inventory nor the screenshot proves completed shelter.
Fields, sustainable production, sales and permanent growth unverified.

One visible game, CUDA director4CPU, observer and read-onlymonitor verified;
venv parent/child pairs are one logical worker. Stderr0. Actual ticks grew after
save; XML60000/mtime11:14:35UTC/campaign verified. Logistics returned realJSON
12then17options; this does not close every future serialization boundary.
Screenshot, native positions, comparison card and SVG retained privately.
Solitary pre-generation NRE still lacks a stack. No manual pawn orders,
diagnostic gameplay replay, rollback or second landing were used.

## Candidate 0.0.8: first hourly observation — 2026-10-07

Same tile10598/campaign and installed package2a3572d/native29df0ef, renamed
Lenrobum. Primary12:16:05UTC/990966:1h04m15s continuous autonomy,16.52game
days. Closing12:20:39/1002224:1h08m48s; all three founders alive, GameOver/
victoryfalse. No restart, rollback, technical pause or manual memory reset.
Food/meals/raw/reachable nutrition0; founderA Malnutrition0.806/downed outside,
founderB0.447/mobile, founderC0.803/downed in bed. Real founderB Rescue targetA,
bed53349 observed; no pickup/food yet. health1.0 does not negate starvation.

First field appeared at513281/~8.55game days after landing. Primary13zones:
two potato, six hops, five cotton;87actual potato plants~12.7%/9.21days to
harvest, no harvestable crops. Closing14zones. Earlier raw food and replenished
meals did occur, including meals1to11; do not report complete lack of cooking.
Since11:57:18 minute stocks remained0;26of62food0 samples include the initially
forbidden baseline. Campfire fueled18.41/20, active meal bill; nearby butcher
spot/active Forever bill. Production/logistics validJSON/23options; no current
ingredients ready. More production setup alone has not sustained nutrition.

Bounded64decisions12:04:43–12:15:53(last8MB, not whole history):23configure_crop,
including exact potato-to-hops changes on zones7,3,10,12 over5–6minutes. Two new
plots selected psychoid/hops. This is accepted reconfiguration, not measured
destruction of every plant or a claim of indefinite looping. Actual prompt has
food0/hunger0/runway0 but potential8.3nutrition/day versus demand4.8,
renewable_food_gapfalse. Source only preserves food plots/enforces edible choices
while potential capacity is inadequate: future crops unlock nonfood changes
despite empty inventory and harvest days away. Confirmed guard weakness; not
the sole established cause of starvation. Criterion/context truncation also
observed; total absence of food context disproved.

Bonded initial monkey died at708683, between11:46:52–11:47:54UTC(~36minutes),
native letter beaten to death. Same-campaign XML healthStateDead and finalBruise
combatLogText identify second-raid attacker. Flu had been tended quality0.230;
last immunity0.602>illness0.513. Do not attribute this death to absent flu care.
Current tamed squirrel healthy; no new completed training. Three raid arrivals
324000/706000/820000; first two observed attackers later corpses, third Flee/
downed. Founders survived, pet lost; complete repelled-raid count unverified.

Physical shelter useful: original three beds room47roofed; by closing new room50
also roofed/three beds,23.4–23.6C. Animal spot outside.54wooden walls/2doors,
stonecutter/table/chair,3shelves, unpowered standing lamp without generator/
conduits. Art bench frame and45concrete floor frames started during starvation;
researchbench absent/currentnone, no completed sales. Screenshot/native
coordinates/card/SVG inspected. Room cleanliness-2.6, dead human near new house;
no exact sanitation/path causality inferred.

Skylantern ritual began12:13:45 during starvation, occupied two workers about
three game hours. Real beautiful result70%,+6mood, visitors and offered joiner;
offer not accepted/three residents at closing. Taming wild human and active
rescue quest have not produced another worker. Orbital income attempt rejected
for missing research bench; doctrine imperial ascent/anomaly/raiding still lacks
completed compatible milestones. Positive ritual result and labor cost retained
separately. Comparison with previous first hour: fields earlier but unstable
food unchanged; previous dog blood-loss death is not this monkey's combat loss.

Single game/CUDA4CPUdirector/observer/read-onlymonitor healthy, fresh heartbeats,
stderr0. Emergency1x from starvation, actual ticks grow, no force_pause windows.
Disk Lenrobum XML960000/mtime12:04:17UTC/campaign stable; not latest tick save.
No savePOST issued. Old startupNRE has no new repeats, zone-on-marble warnings
added. Hourly ACTIVE, next13:13UTC. Private report/evidence includes named
outcomes and PNG12:18:56UTC; camera-only capture, no runtime/game corrections.
Final read-only12:28:18UTC/1021112:1h16m28s, all three alive/nativeendingfalse.
FounderA now actually in bed53349 after Rescue; founderC bed38017. All satiety0,
stockfood0; MalnutritionA0.937/C0.938/B0.612. Delivery to bed confirmed, feeding
not confirmed. Mobile B FinishFrame54005; ritual joiner offer remains unaccepted.
Single services fresh/emergency1x. No new human death at this final check.

## Candidate 0.0.8: second hourly observation — 2026-10-07

Same Lenrobum/tile10598/campaign, no restart/rollback/pause or memory reset.
Primary13:14:06UTC/1315565:2h02m16s continuous autonomy,21.93game days.
FounderC died of Malnutrition1029878, observer12:31:53UTC:1h20m03s from
landing. FounderA Malnutrition1030230,12:32:13UTC:1h20m24s. Exact native
culprit, Death letters and XML Dead agree; wall times are observer detection.
Nine later Unknown/ticknull captions repeat founderA's one death, not nine
additional deaths. Observer deduplication remains an open reporting defect.

FounderB survives. Ritual-offered joiner actually arrived at1052177; real
cooking/harvest/construction jobs observed. XML faction14/kindColonist,
hostFactionnull and hidden WandererJoins3 endedSuccess confirm joining.
Quest3.pawn tag remains; do not infer temporary guest status from the tag.
Existing go-juice dependency/scar are not new infection or implantation.
Stock/satiety0 again. Short food pulses and feeding occurred:2meals/5raw
at12:43UTC, later10raw;38of44minute stocks since prior closing0. Sustainable
nutrition still fails, not a claim that no cooking or feeding ever happened.

Primary26plots:12hops/9cotton,1each potato/corn/tinctoria/nutrifungus/fibercorn.
Seven of68actual potato plants natively harvestable/alreadydesignated; most
future crop estimates are days away.11configure_crop in14primary bounded
decisions;30in40closing decisions. Future capacity guard weakness remains.
New event emergency_harvest rejected13:11:47 for no verified mature plant.
Saved native21092plant DTOs all use thing_id/harvestable_now and no id;
event executor10673 reads id/can_harvest/is_harvestable. Confirmed contract
mismatch, independently of the ordinary harvest path. No live replay/fix;
neither the mismatch nor one failed action alone establishes death causation.

Six roofed human beds persist; animal spot outdoors. Art bench completed but
bills0; no completed sales or researchbench/currentresearch. Unpowered lamps,
no generator/conduits. Native Heatwave1308000; similar heatwave offer remains
unaccepted, do not blame accepted quest. At closing13:21:21UTC/1334195 all
two residents alive/GameOverfalse/victoryfalse: founderB Malnutrition0.755,
joiner0.328, satiety0/bothFinishFrame. Outside40.7C/bedrooms37.9and36.7C,
no Heatstroke yet. Fueled PassiveCooler built; adequate cooling unverified.
Third steel house/three additional beds planned:40projects while food0.
Native Starving tantrum for founderB and unburied-colonist tantrum for joiner.

No new colony-pet death found; earlier monkey raid death unchanged. A bison
self-tamed1220000, not a completed Laya tame. No new raid letters this hour;
old full repelled count unverified. FounderB now rifle/joinerautopistol.
Imperial/anomaly/raider doctrine unchanged, no completed ending milestone.
Silver stock not profit. True PNG13:16:00/ticks1320331–1320334 inspected;
card/SVG compare crops/base/animals/raids/growth/economy with prior hour.

One visible game/CUDA4CPUdirector/observer/read-onlymonitor fresh/stderr0,
ticks advance/no force_pause. Native starvation1x, no manual speed orders.
XML1320000/mtime13:15:52UTC/campaign stable; no savePOST. Player.log3801bytes
unchanged, old startup NRE not reclassified. Only bounded8MB/max100decisions,
camera-only capture; no runtime edits or gameplay commands. Automation ACTIVE,
next14:13UTC/17:13MSK. Named report and evidence retained privately.

## Candidate 0.0.8: third hourly observation — 2026-10-07

Same Lenrobum/tile10598/campaign/package2a3572d/native29df0ef. Primary
14:14:08UTC/1577071:3h02m18s uninterrupted autonomy,26.28game days.
Last founderB died Malnutrition1362449, observer13:32:16.777028UTC:
2h20m26s from landing. Exact culprit, native Death letter and XML Dead/
Malnutrition1 agree. All original founders lost; complete campaign defeat
still false. Earlier founderA/C deaths unchanged, not new observations.

Only joined worker remains. Primary hunger0/Malnutrition0.321/Repair; closing
14:21:27UTC/1594299 hunger0.612/Malnutrition0.375/Repair, alive/mobile/no
bleeding/nativeGameOverfalse/victoryfalse. FoodPoisoning0.913 new, source
unverified; existing go-juice deficiency1.807, not immune disease. Real food
intake occurred:49of50minute stocks0, one3meals/4raw pulse. Native HideInRoom
1448718 final straw Ate human meat; meat source/command/poisoning cause unknown.

Primary39of52potatoes harvestable/expected353product, closing29of34/266;
potential yield not delivered food, missing plants not solely blamed on fire.
31growing zones now19tinctoria/9cotton/2nutrifungus/1potato. Prior plants
remain despite new settings. No sampled HarvestDesignated for remaining worker
in50minutes; shorter work between samples not excluded. Plants0 but capability
enabled/GrowingandPlantCuttingpriority1; no fabricated skill prohibition.

Bounded100decisions14:05:51–14:14:03UTC:96hold_survival,4expand_home_area;
69candidate lists onlyhold, so not96independent model refusals. Actual context
food0/runway0/hunger0. Native home fire and Firefighter.disabledtrue coincide
with source focus_active_fire_choices2803: homefire retainscare/wait, dropping
harvest without checking a firefighter exists. Confirmed suppression rule,
likely contribution to observed waiting; other guards/cooldowns not excluded,
no live pipeline replay or sole-cause proof. Previous emergency_harvest contract
mismatch remains open; ordinary harvesting is a separate path.

Fire127/36home primary,306/111home closing. Roofed bedrooms108.76C/426.06C,
third22.99C; outside21.81C. Centered real PNG14:22:32UTC/ticks1597200–1597203
shows two houses burning and the remaining worker in third. Eight real beds/
three roofed rooms for one resident,103walls/6doors; steel shell does not prove
combustible contents safe. Both animal beds outside; squirrel/bison alive,
no new verified pet loss. New raid1505000/currenthostiles0, full outcome and
possible involvement of visiting combat supplier unverified; not counted as
a confirmed Laya repelled raid. Fire cause not established by raid timing.

Campfire fueled5.45/20, two passivecoolers9.24and10.72/50, butcher/bills present;
no electrical network/researchbench/currentresearch, artbenchbills0/sales0.
Silver857stock, not income. Doctrine ending has no completed new milestone.

One visible responsive game/CUDA4CPUdirector/observer/read-onlymonitor fresh,
actual tick growth/no force_pause. Normal target3x, native fire emergency1x;
current worker no thermal condition, not safe-room proof. Director stderr201bytes
new Transformers warning10485tokens>8192; director continues, crash/index error
not established. Other stderr0, Player.log3801bytes unchanged. SaveXML1560000/
mtime14:07:07UTC/campaignstable, no savePOST. Only8MB/max100decisiontail,
camera-only captures, no runtime edits/orders/pause/restart/rollback/reset.
Private report/card/SVG/deathXML/firefilterproof saved; automation ACTIVE,
next15:13UTC/18:13MSK. Complete native defeat/victory not established.

## Candidate 0.0.8: fourth hourly observation — 2026-10-07

Same campaign/tile10598/package2a3572d/native29df0ef; primary15:13:29UTC,
tick1808720:4h01m39s uninterrupted autonomy,30.14game days. Closing15:22:04UTC,
1944354:4h10m14s,32.41game days. No new verified human death, native complete
GameOver/victoryfalse. All previous founder hunger deaths remain recorded.

A man in black arrived1706598, first observed14:48:06UTC. Native letter and
XML StrangerInBlack/player faction confirm storyteller aid, not planned Laya
recruitment or a quest reward. Initial permanent arm/leg scars are not new.
Actual Rescue targeted joined worker/bed at14:48and14:49; worker in that bed
14:50with satiety0.880, mobile again14:52. Delivery and nutrition verified,
exact feeder/source/issuing model decision unverified. Closing joined worker
no Malnutrition/FoodPoisoning, satiety0.134/DoBill; rescuer0.392/Sow. Both mobile,
no bleeding. Existing go-juice deficiency worsened1.807->2.973, supply absent.

Raw potatoes88/nutrition4.4/meals0 at primary and closing.44of50minute stock
samples since previous closing0; short unsampled cooking is not excluded.
New worker Harvest13of25sampled jobs, real crop acquisition. Primary campfire
empty/WoodLog0 despite ingredients; closing actually fueled19.35/20/WoodLog9.
DoBill target or completed cooking unverified; stock meals still0.

Primary bounded100choices14:55:35–15:13:22UTC include84configure_crop:
40cotton,39tinctoria,3potato,2corn. Same zones switch food->nonfood and cycle
cotton/tinctoria; accepted settings not completed crops or proof of destroying
each old plant. Primary36plots:16cotton/13tinctoria/5nutrifungus/2corn; closing
38:18cotton/14tinctoria/5nutrifungus/1corn. No configured potato zone despite
old potato plants. Future-capacity protection and emergency-harvest DTO mismatch
remain open. No hold_survival in primary bounded tail after fire stopped;
this is not a code fix of the fire-focus suppression rule.

Sampled fire peak332; first0 at14:31:24UTC/FoggyRain. Exact extinguishing cause
unknown, not attributed to joined worker who cannot firefight. RoofCollapse
1619331 crushed torch73%. Beds8->3, walls103->80, doors6->4 after fire; no built
passivecooler remains. One intact roofed bedroom17.31C primary/24.27C closing,
three beds; animal spots outside. Additional bed/cooler remain projects. Real
PNG15:15:39UTC/ticks1842319–1842337 inspected, shows fire damage. Separate
API/photo/XML times retained. New physical simple research bench157,135 first
sampled15:00:41; native Autodoors can_start_now/appropriate_benchtrue. Current
researchnone/bothResearchpriority0/no newly completed project. Artbenchbills0,
no confirmed sales or ending milestone, silver857stock; hops102->332 not food.

Squirrel healthy; bison last alive14:26:10UTC/1607117, mental state/Goto near
map edge, no enclosed pen. Subsequently absent from API and XML1860000;
no death letter/corpse. Fate unknown, not recorded as killed. Current handlers
Animals0 are below squirrel8/bison6 requirement. No new verified pet death or
new raid announcement; old raid outcomes still partial, no fabricated repelled
count. New worker is storyteller aid, not a confirmed completed quest.

Same visible game/CUDA4CPUdirector/observer/read-onlymonitor, fresh running
status/real ticks advancing/no force_pause, observer normal3x. Director stderr
201bytes unchanged (old10485tokens>8192warning), others0. Player.log4106bytes:
new Direct3D timing warnings, no new NRE. Logistics JSON14options/recipes3 is
a positive reading, not proof prior empty200 fixed. Save1920000/mtime15:20:16UTC/
campaign stable. Only bounded8MB/max100decisions per capture, no savePOST.
Camera and reporting only: no runtime edits/orders/speed/pause/restart/rollback/
memory reset/live replay. Private report/card/SVG/care/crop/bison evidence saved;
automation ACTIVE, next16:13UTC/19:13MSK. Complete campaign outcome not verified.

## Candidate 0.0.8: fifth hourly observation — 2026-10-07

Same campaign/tile10598/package2a3572d/native29df0ef. Primary16:13:25UTC,
2347655:5h01m35s uninterrupted autonomy,39.13game days. Closing16:18:57UTC,
2360865:5h07m07s,39.35game days. Both remaining colonists alive/mobile/no
bleeding, native complete GameOver/victoryfalse. Earlier founder losses unchanged.
No new verified colony-member death; neutral refugee loss recorded separately.

Food/raw/meals0 and both satiety0 again. Closing rescuer Malnutrition0.640,
joined worker0.459; bothRepair.35of49minute stock samples0, max59food/3meals:
short actual cooking/intake happened, not sustainable supply. Campfire0/20,
torch0/20, WoodLog0; active meal/butcher bills persist. Cooler still blueprint
needs50wood/available0. Broad equal work priorities did not secure nutrition.

Bounded100choices15:54:28–16:13:19UTC include83configure_crop:42hops/35cotton/
5potato/1fibercorn. Same zones35/21/20/3 potato->hops, repeatedcotton/hops.
Actual contextfood0/hunger0 includesberry harvest and9safehunt options; not
complete loss of hunger context. Primary50plots:25hops/15cotton/6nutrifungus/
2fibercorn/1potato/1tinctoria; closing21hops/19cotton/other counts unchanged.
Actual food plants:potato0,fungi5unharvestable,corn1unharvestable.669total
plants includesgrass/commercial crops, not a food reserve. Growthseasontrue.
Earlier future-capacity protection/emergency-harvest DTO issues remain open.

New raid2181000. Rescuer actualAttackStatic targeted known pigskin79441 at
2193048. XML corpse Dead and Gunshot combatLogText confirm rescuer revolver
hits2190306/2190723/2193946. Rescuer lost right arm2192617 to that raider's
autopistol, exact XML combatLogText; first sampled15:38:33UTC, previous
15:37:31without loss. Hand/fingers are descendants of one arm loss, not separate
new ten-part events. Full raid roster/terminal cause/loot/kidnapping unverified;
not counted as fully verified repelled raid. Currenthostiles0 alone is insufficient.
Closing rescuer manipulation0.32/moving0.57, overallhealth1 despite missingarm.

Transport relative/refugee77707 arrived2094000, found Dead in same-campaign
XML2340000/factionnull/SpaceRefugee/BloodLoss1. Never verified colony member.
Death tick/exact culprit/full rescue-attempt history unknown. New second pod
2288000 has unknown outcome, not assumed dead or rescued. Native Beggars now
EndedSuccess but item transfer/reward not independently verified. Deserter and
hospitality offers expired unaccepted. RoyalAscent newNotYetAccepted; logging
site observedOngoing not completed expedition. Older refugee quest failed state
was already present before this hour, not reclassified as a new failure.

Joined worker go-juice deficiency2.973->4.362, no verified supply. New dependency
tantrum/advanced-starvation hallucination/hunger tantrum letters. Ingest target
79724 at15:52:13 corresponds known raider corpse; intake/result/policy issuer
not fully established. Both food and dependency remain actionable risks.

Four human beds in two roofed rooms21.11C/18.71C closing, walls80/doors3.
Diningtable/chair/electriclamp missing since previous hour; exact cause of each
removal unverified despite tantrum letters. No new fires. Real PNG16:15:49UTC/
ticks2353662–2353665 inspected; protected human rooms/scattered plots visible,
animal spots outdoors. Native Batteries selected15:22:46, progress2by15:23:49,
still2/400 primary/closing; no sampled Research job or newly finished project.
RescuerResearchpriority1/joiner0. Artbenchbills0/no verified new sales,
silver857stock/hops83not food or income; no completed ending milestone.

Squirrel alive/Tameness4->3of5, wantedtrue but handlersAnimals0 below8.
Handlingpriority1 does not establish training. Bison still missing with no new
death/escape proof; no new verified player-pet death. Old raid outcomes remain
partial. Report/card/SVG/crop/battle/XML/quest-state evidence retained privately.

Same visible responsive game/CUDA4CPUdirector/observer/read-onlymonitor fresh,
actual ticks advance/no force_pause. Observer1x withcritical_starvationtrue/
other_emergency is a slowdown, not a freeze. Stderr201bytes unchanged for
director, otherstderr0; old model10485tokens>8192warning still unresolved.
SaveXML2340000/mtime16:11:02UTC/campaignstable, no savePOST. Only bounded
8MB/max100decisions per capture; file about238MB. Camera/reporting only, no
runtime edits/orders/speed changes/pause/restart/rollback/reset/live replay.
Automation ACTIVE, next17:13UTC/20:13MSK; complete campaign outcome unverified.

## 2026-10-07 — candidate 0.0.8 terminal outcome (Lenrobum)

One random map, Cassandra/Medium, Permadeath; autonomy 11:11:50–16:47:49 UTC,
5h35m59s / 40.53 game days. Native GameOver tick2431617, matching campaign,
zero colonists/caravans, victory=false. Director, observer and read-only monitor
ended normally on native confirmation; no technical pause, restart, rollback
or memory reset during this run. Hourly automation paused for user-authorized
corrections and a new test colony after verification.

All three founders and both later permanent inhabitants died of Malnutrition,
confirmed by native letters and exact culprit. Founder loss ticks1029878,
1030230,1362449; later losses2410253,2431218. The latest disk save2400000
predates the final deaths; terminal API/letters/observer, not that XML, prove
full defeat. The previous monkey combat death is unchanged; the living squirrel
has declining tameness, the missing bison's fate remains unknown. Partial raid
results do not establish a complete repelled-raid count.

Food was acquired, cooked and consumed intermittently, but last28minute samples
had stock/meals0. Future crop capacity incorrectly lifted food protection before
harvest, while crop configuration repeatedly displaced food work. First field
at8.55game days; final51zones predominantly cotton/dye. The emergency event
harvest DTO mismatch and fire focus without a capable firefighter remain
confirmed defects. Both late inhabitants became downed before terminal waiting;
all42final hold rows had one candidate, not42 model refusals. No new completed
research, verified sales or ending milestone; silver+108 was a gift. Roofed
housing survived but empty fuel and missing food made it insufficient.

Private report outputs/colony-008-final-20261007-2013.md; read-only evidence,
terminal card, exact death chronology and inspected base PNG in this run folder.
No source/game changes were made during hourly observation. Fixes and the next
campaign must be verified and documented separately.

## 2026-10-07 — candidate 0.0.8 food commitment fixes and Dayouinum start

User-authorized corrections after Lenrobum's native defeat, then one random
new colony. Source 7b1e810, package d2b476b, installed DLL 1.10.0+7b1e810;
payload SHA256 verified. 1245 Python tests, 311-route contract audit and
Release-1.6 build pass with zero warnings/errors. Local cached-model replays
on the former campaign's food-crisis slices selected food work and retained
the edible crop across persisted global dwell checks. Offline verification
does not guarantee a live colony's survival. No 0.0.8 release or tag created.

Corrections separate reserve/first-harvest timing from potential crop capacity,
preserve edible planting, enforce cross-actor/plot crop dwell, fix emergency
harvest native DTO and food exclusion by fire focus without a firefighter,
raise a selected food worker above equal-priority routine tasks, and exclude
empty-store/healthy-animal/unexecutable-kitchen distractions during shortage.
Observer death captions deduplicate a pawn already announced; tokenizer fit
probes are bounded. Audit docs/audits/lenrobum-food-commitment-2026-10-07.md.

Dayouinum (Permadeath), random tile51033, world seed
laya-food-commitment-008-20261007, map16622162, Cassandra/Medium,
campaign1e4b7bc1228b42f282d6a7dbcca28884. One generation, baseline20,
autonomy18:23:57UTC/21:23:57MSK. No restart, rollback, manual pawn orders or
memory reset after autonomy began. Different campaign from all prior runs.
Initial -32.27C/no growing season; all founders cannot Research/DarkStudy.
Unforbidding supplies,13walls/door/campfire/3sleeping spots completed by Laya;
room37 roofed and21.50C by18:29, then26.73C. That did not establish rescue.

Founder286 died Hypothermia58685, observer18:37:07UTC,13m11s from start;
founder289 Hypothermia59261,18:37:27UTC,13m31s. Both remained outside the warm
house. Founder292 BloodLoss92945,18:43:16UTC,19m20s; fresh megaspider wounds,
LayDown targeted bed37788 but actual position161,72 was far from184,174;
physical bed placement was not proved. Severe bleeding documented. All human exact
culprit/native letters agree. Labrador30406 BloodLoss94331 native letter;
wall-clock death time/killer not established. These new cold/care failures
are recorded separately and are not claimed fixed by the earlier food patch.

Native StrangerInBlack38032 joined81325: storyteller rescue, not a planned
hire or verified quest reward. Closing18:47:07UTC/175840 only this inhabitant
alive, health1/hunger0.808/LayDown/no bleeding/downed. Native GameOver and
victory false, campaign continues after complete founder loss. Stock94food/
47.2nutrition/27medicine, campfire0fuel, roofed bedroom-23.47C/outside-25.13C:
stored food and a roof do not establish sustainable supply or adequate warmth.
No confirmed completed raid, sales, research or ending step. No fields/power
network/research bench/commercial output; all routes and rescue order history
are not yet fully assessed. Real inspected PNG18:31 predates deaths/late cold.

One visible game/CUDA4CPUdirector/observer/read-onlymonitor, real commands
verified, statuses fresh, stderr0, force_pausefalse, ticks175840->176643.
AutosaveXML120000/mtime18:44:45UTC/campaign stable, older than final API tick;
technical startup saves16680/48432 separately recorded. Old pre-generation
NRERef335BBC32 remains unexplained, no new repeat at final check. Private
report outputs/colony-008-food-commitment-20261007.md and current run's
review-20261007-184706 evidence/card/SVG/death records. First full hourly
review no earlier than19:25UTC/22:25MSK; continue this same campaign without
source/game changes during observation, stop only on native full ending.

## 2026-10-07 — Dayouinum native defeat at first hourly review

Same one-random-map campaign1e4b7bc1228b42f282d6a7dbcca28884, tile51033,
Cassandra/Medium/Permadeath. Native GameOver934203, observer19:18:19UTC,
54m22s continuous autonomy /15.57 game days from baseline20. Review19:28:59UTC
paused934368, zero people/caravans, victoryfalse. Director/observer/monitor
ended normally on native confirmation; visible game remains responsive.
No technical pause, restart, rollback or memory reset during the run.

New verified loss is kidnapping of sole replacement38032 by Pest Army791905,
native letter plus kidnapped_pawns/health0.619. Last seen alive19:14:27UTC/
788197, first absent19:15:28/812442; wall-clock is only an interval. No
confirmed death of this inhabitant. Previously recorded founder286/289
Hypothermia58685/59261, founder292 BloodLoss92945 and Labrador30406
BloodLoss94331 unchanged; do not count this kidnapping as another death.

Base still13woodwalls/1door/3sleeping spots; roofed room37,18.69C at finale,
outside17.65C, campfire0fuel. Earlier room min-28.11/max29.68C in minute
samples, failed actual warm rescue already documented. Two butcher spots
157,69 and162,177, one bill each/campfire one bill; recreation pin added.
No electrical network, research bench, fields, commercial workshop or new
research.55minute samples all growing_zones/crop_plants0; seasonfalse.
No full route verification. Real inspected PNG19:32:52UTC/934368 shows
compact house near mountains, no completed defense line; hide_ui retained UI.

Nutrition8.85 remains/23meals+1raw, medicine31.54of55stock samples nonzero,
sole zero at forbidden-supplies baseline. Actual repeated Ingest and one
campfire DoBill observed; source of each stack/long-term output unverified.
Different failure path from earlier starvation: cold/clinical founder losses,
then raid kidnapping despite stored food. Cold biome cannot certify edible
crop preservation and all food-loop regressions. No recorded sales/ledger
entries or new ending milestone; anomaly_level0 after sampled investigations.
Doctrine imperial/anomaly/raider still lacks demonstrated coherent execution.

Raid announcements324000/787000; complete first outcome unknown, second
confirmed kidnapped sole resident. Not recorded as two repelled raids. Bounded
last100choices19:06:08-19:18:19: positioning/cover without attacking IDs,
later focus-fire with attacking38032, then accepted melee and three empty
appliedfalse no-ops. Later inspection confirms commands=[] on those three;
they preserved the current job, not three failed reissued attacks. Completion unverified; this sequence does not establish
the sole cause of loss.12hold rows after worker absence interleaved with other
choices; zero-worker waiting is not rescue. Future correction needs actual
combat/cold-care sequence evidence, not assumed HTTP completion.

## 2026-10-07 — Dayouinum corrections and shutdown at user request

The same campaign's final paused tick934368 was saved on disk19:48:27UTC,
XML/campaign/mtime verified, then native quit succeeded; RimWorld process absent.
Director, observer and private monitor already exited at native defeat. Automation
laya remains PAUSED. No new colony, restart, rollback, memory reset or live replay.

Recorded31104 exposes a nonbleeding downed patient with Hypothermia0.643,
life_threatening=true, frostbite tending active, while roofed bedroom37 was21.50C.
The previous exact-care yield supported starvation only: life-threatening cold
blocked the transition from TendPatient to Rescue, and rescue tied to food feasibility.
Thermal rescue now has a separate exact same-patient clinical binding, native usable
roofed bed at safe temperature and route checks, repeated at POST. It requires no
food. Bleeding, immune disease, feeding, lifted patients and queued care stay protected.
A sick but mobile idle caregiver may be natively considered for this rescue.

The main pipeline compares the thermal response before wound-only care, then its
exact native actor/patient. Tending frostbite is explicitly not warming. Native
rescue examines completed safe-temperature beds instead of accepting a nearest
outdoor spot. Detailed downed/dead caregiver flags are respected; unchanged failed
care pairs wait at least30real seconds and2000ticks, other patients remain available
and a material clinical change or rollback reopens the pair. Routine nonbleeding
care avoids known hostile approaches. Clear shots from the current position preserve
an exact ongoing AttackStatic. Empty-map development offers no new building/doctrine;
native world/ending evidence still determines the outcome.

Building telemetry now exports current temperature, room and roof. Refuel prompts
distinguish an empty cold campfire from auto_refuel configuration. Neither this
context correction nor accepted jobs prove completed heat maintenance or recovery.

QA:1256Python tests,311route audit/no missing literal calls or duplicates,
native Release-1.6 zero warnings/errors,8actual native thermal-transfer boundary
cases. Cached-model CUDA/4CPU full thermal sequence chooses rescue in both native
option orders and preserves it through8following cycles. This is fixture-native
feasibility plus offline model/transport, not a live safe-route or warming proof.
Early direct-ID prompts still chose defer; the final response-then-binding pipeline
is the tested correction. Generic three-way wound/rescue prompt optimization does
not establish safety for every illness; the explicit thermal gate avoids wound-only
triage for this verified nonbleeding exposure case.

Full live rescue-to-bed warming, repeated thermal fuel delivery, infection/wound
care under a simultaneous attack, and complete raid defense remain future gates.
The old startup NRE remains unexplained. See
docs/audits/dayouinum-thermal-care-2026-10-07.md and private correction evidence.

Latest same-campaign stable autosaveXML900000/mtime19:17:31UTC predates
GameOver; terminal API/letter/observer prove outcome. Stderr0; Player.log4519
contains earlier single pre-generation NRE and zone-over-Granite warnings,
no new NRE repeat. No source/game orders, speed changes, savePOST or live
replay during review. Private final report outputs/colony-008-food-commitment-
final-20261007-2225.md, prepared192858evidence and terminal card/SVG/photo.
Hourly automation paused after recording native ending; no new colony started.

## 2026-10-08 — candidate 0.0.8 thermal-care verification, single random start

Human-authorized new run following completed Dayouinum. Source fc133c9,
package bacc429, DLL1.10.0+fc133c9;59 installed/source payload hashes verified.
1256 prior Python tests,311 routes,8 native thermal predicate boundaries and
native build/model replay passed offline. New live rescue is not yet proven.
One generation, tile52676, worldseed laya-thermal-care-008-20261008,
map16622162, Cassandra/Medium/Permadeath, campaign171f3d445b5a41f0a30ec525f6cf7b9d.
Visible game launched; baseline21; autonomy06:38:56UTC/09:38:56MSK.
No restart, rollback, manual pawn jobs or previous-memory reset. Separate
campaign state preserves prior run records. Founders427/430/433 have no initial
health conditions;430 incapable of violence;Medicine1/2/5,Construction3/2/2.
All have Firefighter/Research capability. Initial-29.74C/growing-seasonfalse;
forbidden starting food is not absence of food. Laya unforbade supplies and
completed13woodwalls/door/campfire/3sleeping spots, roofed room80.
Closing06:42:41UTC/tick78089: three alive, no downed/bleeding,
Hypothermia absent after earlier427=.186/433=.054. Room80=29.57C,
fuel8.20/20;food47/meals46,nutrition41.65.
Native downed thermal rescue not encountered; warmth recovery is not its proof.
No farm/network/researchbench/commercial workshop/revenue/verified raid win or
new permanent recruitment at startup. Native Anomaly dialogue resolved by
director; no endpoint acceptance labeled victory. Five sampled loadout changes
require further actual weapon/job review. Bed ownership/target != arrival.
PNG06:41:30UTC/ticks51158–51338 viewed; earlier frame occluded by native dialogue;
hide_ui still leaves interface. Coordinates125,148/campfire and125,144/door;
bed36006–36008 in room80; outdoor33250 separately. Full route/firebreak audit
not performed. Disk saveXML77661/06:42:38UTC, campaign
matches;live77709 confirms progress. Startup saves are
technical verification, not autonomous actions. Game64888,director46212
CUDA/4CPU,observer13212,monitor91220;fresh/running,stderr0,force-pausefalse.
Player.log3333bytes has single pre-generation NRE without initial stack;
cause unresolved, no new repeats observed. First full check>=07:40UTC/10:40MSK,
then hourly atminute40; readonly checks, silence without meaningful change.
Private report outputs/colony-008-thermal-care-20261008.md and comparable
JSON/SVG/PNG in longrun-008-thermal-care-20261008; no0.0.8release/tag created.

Later startup closing06:48:06UTC/tick195173/live195413: three alive,
no downed/bleeding, founder427 mildHypothermia.015, othersno conditions;
hunger.780/.580/.420. Room80roofed28.28C,fuel17.82/20,
food22/meals21/raw1,19.15nutrition. Prior46meals ->21 proves initial reserve
consumption, not renewed production. No new death/native end. Allservices
fresh/running/empty stderr, observer normal3x. Newer closing evidence/card/layout
preserved, automationlayaACTIVE/minute40. No behavioral changes after startup.

## 2026-10-08 — Thieron, first hourly observation (10:40 MSK)

Same campaign171f3d445b5a41f0a30ec525f6cf7b9d renamed Western Ashinaneria
Strong Covenant. Primary07:42:16UTC/t698451,1h03m20s/11.64game days;
closing07:53:45UTC/t739330,1h14m49s/12.32days, no pause/restart/rollback.
Unay430 died Bite544278, exact/native/XML; wolf attack injury at death tick
names Wolf_Timber. Observer07:05:09.679UTC,26m13.5s life; not Malnutrition.
Gleb29067 died Malnutrition737293, native letter; exact wall time unknown,
between live07:49:24 and confirmation07:53:45. Failed feed_hungry_animal
twice patient_not_available_in_bed; no successful pet feed verified.
Stone/Jill alive, nativeGameOver/victoryfalse. ClosingStone hunger0/Malnutrition
.546/Wait_Combat, Jill downed/catatonia/hunger.002/Malnutrition.230/LayDown.
Autonomous StoneFeedPatient→Jill and hunger.891 at07:44:49 verified feeding;
stock6 InsectJelly/.3nutrition is not six cooked meals or sustainable supply.
Roofed room80 remains27.49C, campfire8.72/20,13walls/one door/three sleeping
spots, no real beds/grid/researchbench/commercial production. New food zones
Rice/Rice, actual7potato/7rice immature; firstzone557594/~9.29game days.
Bounded100 decisions80hold,41single feasible and39hierarchical; mental state
explains some worker unavailability. Not proven infinite loop or80 independent
model deferrals. Raid324000 partially evidenced OrthoziteDead + wounds from
Stone/Jill; second727000 ongoingBriggs37286. No invented full raid victory.
Silver800 stock, no verified revenue/recruit/research/final stage; quest offer
expired unaccepted. PNG07:44:26 viewed, separate API/XML times, comparable
cards/layout. Minimized window restored only; servicesfresh,stderr0,ticks
grow,forcePausefalse,observer1xcriticalStarvation. SaveXML720000/mtime
07:48:19UTC/campaign stable predates pet death. Player.log3697 with oldstartup
NRE/no new repeat. Production JSON readings positive, not global fix proof.
No code/game behavior/jobs/speed/manual memory changes or savePOST/replay.
Detailed Russian report outputs/colony-008-thermal-care-hourly-20261008-1040.md;
review-20261008-074214,074922,075343 evidence in longrun-008-thermal-care-20261008.
Automation laya ACTIVE, next08:40UTC/11:40MSK.


## Дополнение при записи Demo — 08:11:46 UTC / 11:11:46 МСК

Тик804982, native GameOver/victoryfalse. Ondra37382 прибыл как Man in black741502:
помощь рассказчика, не плановый найм. Jill мобильна/TendPatient, кататония
больше не наблюдается. Stone downed/Wait_Downed/hunger0/Malnutrition.235 со
свежими ранами; Ondra downed/LayDown со множественными свежими травмами.
У всех bleeding0, Jillhunger.047; полное выздоровление не подтверждено.
MadCaribou782000 и CaribouRevenge788134 — новые угрозы, не отбитые рейды.
Food14/meals7/raw7/6.65питания — новый запас, не устойчивое снабжение.
SaveXML780000/mtime08:05:05.555UTC/campaignstable новее смертиGleb, но до
указанных caribou events. Службыfresh/stderr0, observer1×. Доказательства
review-20261008-081144-* сохранены; это дополнение, не второй полный контроль.

Demo08:09:42UTC, тики797681→799479, реальная игра/nativeLayaHUD, без игровых
приказов или изменения скорости. Застывший первый захват отброшен. Готовый
outputs/laya-demo-20261008/Laya-live-demo-30s.mp4:1080p/30fps/900кадров/30.000с;
48из48 проверенных кадров после титра различаются. Сохранились доказательства
recording-live-evidence.json и просмотренное preview-live.png. Следующий полный
контроль08:40UTC/11:40МСК, автоматизацияACTIVE.

## 2026-10-08 — Western Ashinaneria Strong Covenant, second hourly observation (11:40 MSK)

Same campaign171f3d445b5a41f0a30ec525f6cf7b9d; primary08:44:58UTC/t1225199,
2h06m02s autonomous; closing08:56:42/t1272072,2h17m46s/21.20game days.
Jill433 died Scratch911358, observer08:26:56.566UTC/11:26:56MSK,1h48m00s;
exact/native/XMLWolf_Timber claw at death tick, predator907383. Stone427 died
Infection1270701, native Death letter; observer08:56:18.031UTC/11:56:18MSK,
2h17m22s. ObserverUnknown/ticknull does not override native Infection evidence.
Infection.415/.3546→.812/.7133→.949/.8382; tend0→.1603→0, medicine0,
late in_bedtrue/currentbed36007, LayDown and feeding observed, survival failed.
All founders lost, Ondra37382 alive healthy/hunger.442/Wait_Combat; native
GameOver/victoryfalse, no new colony. Closing3RawRice/.15nutrition, meals0.
SevenRicezones,125actualrice/23harvestable/73potentialyield, not stored food;
early designation, observed HarvestDesignated and rice arrival, sustainable
supply still unverified. Food/MealSimple/MealFine arrived earlier, no claim of
no cooking/feeding. Campfire11.07/20, roofedroom80 29.17C,13walls/one door/
3sleepingspots/noBed/grid/researchbench/commercial production; new HorseshoesPin
and distant ButcherSpot48,137. Elkself-tamed835000, no enclosedpen, no newpetdeath.
BriggsDead with Stone/Ondra gunshots; thirdraid841000 has externalparticipants,
complete outcomes/kidnaps/theft unknown. SamSpaceRefugeeDead is not colonist.
Primary25hold/100, some singlefeasible; later priority switching observed.
No verified revenue/research/final stage; baseline7research unchanged,
ShipToStarsOngoing is not completed/modelaccept. Photo08:46:04/t1234992–1235011
viewed, separate API/XMLzonecoordinates1260000; comparablecards/SVG. Minimized
window restored; servicesfresh/stderr0/ticksgrow/forcepausefalse, observer1x
criticalinfection then3x. SaveXML1260000/08:53:16UTC predatesStone death.
Player.log4865 oldNRE only; fullLogisticsJSON not global fix proof.
No workingcode/gamejobs/speed/savePOST/replay/restart/rollback/memoryreset.
Detailed report outputs/colony-008-thermal-care-hourly-20261008-1140.md,
review-20261008-084456/085211/085516/085640 evidence. layaACTIVE,next09:40UTC.

Second-hour later09:05:38UTC/t1475354/native1475421: Ondra alone healthy,
hunger.516/Harvest, food26/meals14/raw12/13.2nutrition, medicine0; one stock
poll is not sustainable supply proof. NativeGameOver/victoryfalse. New verified
autosaveXML1500000/mtime2026-10-08T09:06:27.454715+00:00/samecampaignstable includes
StoneHuman427Dead/WoundInfection1 after death1270701; no savePOST.
See hourly-20261008-0840-final-live-check/final-save.json.

### 2026-10-08 — development audit against real player tutorials (offline)

At the user's request, reviewed the colony evidence against original player
tutorials on recruitment, labor, prisons, weapons, food, trading, construction
and research. Private corpus: complete captions from33 Francis John/Adam Vs
Everything/Noobert videos,170812words/12.45hours. Full reads and selected chapter
coverage are distinguished in the private source index. This is not a claim of
watching every video in full. Full captions are not repository or installer
payload; colony logs/saves were not uploaded to caption services. Older numerical
rules and version-specific exploits are not assumed correct for1.6.

Confirmed source defect: the shelter filter required true Bed furniture even
with enough enclosed roofed SleepingSpot places. It removed preventive prison,
research, income and cover preparation from the healthy warm Thieron start.
Offline old/new filter comparison at195173 and1225199 shows those choices now
survive that gate. Lenrobum2347655 and Roinor1074902 already passed the old gate;
their failures cannot all be attributed to this defect. Other feasibility,
clinical, food, material and native guards remain applicable.

Source changes: count roofed usable human sleeping places, shared beds with two
places, excluding known medical/prison/animal/ancient/remote beds; prepare prison
from real stored food runway rather than misleading meal item counts; offer
general construction prioritization only with actual unfinished projects; retain
measured development facts beside ordinary care/quest facts; distinguish novice,
incapable, temporarily unavailable and unassigned roles; normalize actual native
active quests instead of counting wrapper keys/history. Development context may
yield to critical care/quest data if the real token budget is exceeded.

Verification card now retains work priorities/skills/jobs, weapons/ranges/armor,
prison beds, family observations, workshop bills and research. Unknown is not
zero, assignments are not worker hours, a bed is not a recruit/birth, output is
not income, and a raid announcement is not a confirmed successful defense.

Cross-run evidence: Lenrobum bounded100-command window had84 configure_crop,
not84% of worker time. Its art bench had0bills and no verified sale; Battery
progress remained2/400 for roughly50minutes without sampled Research job.
Some cooking, feeding, actual rescue, combat and a permanent Fenix recruit were
confirmed, so the system is not described as never accomplishing any of them.
Three prioritize_construction choices occurred in the current bounded sample
despite0projects. Four baseline rosters had no internal spouse/lover/fiance pair;
TryForBaby validates an existing couple. Family formation/fertility and sustained
care need separate verification, not forced births as a survival condition.

Regression coverage in tests/test_development_readiness.py and
tests/test_colony_verification.py includes native-shaped records and the cached
real Laya tokenizer/312-token normal consequence budget. Complete suite:
1268 tests passed in 7.827 seconds, no failures or skips. The direct read-only
card script produced the development card and coordinate SVG. The suite log
and generated artifacts are in the private audit folder. No native
source/DLL, running payload, game order, speed, savePOST, restart, rollback,
map generation or memory reset was used for this audit. These source corrections
are not a live survival result. The current campaign's previously logged deaths
and assistance from the man in black remain separate from this technical work.

Detailed private report: outputs/laya-development-audit-20261008.md.
Source/coverage index: outputs/laya-development-audit-20261008/sources.md.
Saved-state filter comparison: saved-state-development-check.json in that folder.
Portable summary: docs/COLONY_DEVELOPMENT_AUDIT_20261008.md.


### 2026-10-08 — Thieron / Western: native defeat 2248520

Same campaign 171f3d445b5a41f0a30ec525f6cf7b9d, tile52676, one generation.
Native GameOver2248520/victoryfalse; observer09:56:56.422680UTC,
continuous autonomy3h18m00.276s from06:38:56.146855UTC,37.48game days.
Final live10:49UTC:0colonists/0caravans, paused2248796. Services completed/stopped
for native ending; one existing RimWorld64888 remains visible and responsive.
New exact Ondra37382 Malnutrition2248121, observer09:56:51.304350UTC.
New Elk1/id36270 Malnutrition2213989/native Death letter and corpse43772;
last alive09:46:38, absent09:47:39. Earlier Unay/Jill wolf wounds,
Stone Infection and Gleb starvation were already recorded, not new deaths.
Four confirmed permanent residents ultimately lost; Ondra was storyteller help.
Hiroki departure is not evidence of successful permanent recruitment.

After09:05:38,51minute samples,27stockfood0,maxnutrition29.7 with real new
meals before depletion. Later Ondra downed/extreme Malnutrition, starvation
death confirmed. MuscleParasites not an immune race or native lethal culprit.
Bounded100 decisions contain11fallback_line on Shambler43669; all accepted
positioning, attacking_pawn_ids[], completionunverified.11sampled drafted
Wait_Combat observations during deteriorating hunger. No verified kill;
defense/labor lock needs investigation, not a claim of sole cause of death.
Late berry order worker=null/No eligible colonist for PlantCutting; designation
and new SleepingSpot did not establish food/build completion while downed.

Final46walls/2doors across two buildings,1Bed+1SleepingSpot roofed room80
at-6.80C, campfire0/20/noWoodLog.4ButcherSpot+TableButcher queues, noingredients.
Research bench built but Microelectronics0/3000, finished research unchanged.
Fence31/gate/marker built, feeding/pen adequacy not established;3traps built,
2frames.7Rice zones/240cells/allallowsowfalse, actualRice0/expectedyield0,
growthseasonfalse.StandingLamp exists but powerproduction/consumption0.
Silver800 is stock/noverifiedsale or income;18projects unfinished.
Raid1963000 and other raid outcomes partial/unknown, no invented repelled count.
Actual PNG10:53:42UTC/t2248796 before-after, viewed; nativeGameOver text visible.
Card/SVG generated from frozen evidence, no model replay or orders.

Save XML2220000/mtime09:48:57.594901UTC/samecampaignstable predates final death:
OndraDown/Malnutrition.803. No claim of final-tick save; no savePOST.
All59installed payload hashes matchbacc429/fc133c9; offline development audit
edits were not installed, so this is not a live test of those source changes.
stderr0; one old startupNRE/no new repeats; logistics fullJSON12options.
Technical actions: foreground existing window, native camera, report files.
No gameplay commands/speed/pause/reset/restart/rollback/new map.
Native defeat warrants automation pause; confirmed status recorded separately.
Report: outputs/colony-008-thermal-care-final-20261008-1348.md; frozen review-20261008-104859-* and final-20261008-1048-* in run folder.

Automation laya PAUSED via automation_update; persisted status verified,
proof final-20261008-1048-automation-paused.json. Current game remains visible,
natively ended/paused; no further hourly check scheduled for this campaign.


### 2026-10-08 — additional creator, Shorts, mountain and insect audit

User requested other creators and Shorts, with special attention to insects
and underground living. Reviewed28 original videos/22 channels, including
17Shorts. Public captions obtained for27 (32547words);25 tracks read fully,
two long-video chapter selections. OmegaConstruct description/frame1:53 and
Exterminater Short geometry frame~0:35 reviewed; no claim of28 full viewings.
Private source index records scope, time and hashes. No private game evidence
was submitted to the transcript service; caption text remains outside payload.

Primary lessons: stage excavation after usable facilities; budget mining and
chunk hauling; verify roof/support, access and evacuation; prepare actual
capable armored melee and shooting positions, substitutions and treatment.
Bait rooms are probabilistic. Burning requires isolated evacuated compartments,
temperature/recovery evidence and accounts for destroyed supplies. The
infestation_burn label has no currently supported executor. Existing native
roof guards and infestation_choke eligibility are acknowledged, not absent.

Current game definitions contradict Cooking8=nofoodpoisoning and straw=sterile:
FoodPoisonChance.0015 at8; strawCleanliness-.1/FilthMultiplier.05/Flammability1.5,
sterileCleanliness+.6. Fungus needs darkness/fertility; fungal gravel needs
thick roof and Tunneler designator eligibility. Odyssey is not in native
active_mods; its new insect examples are separate. Unverified exact spawning
thresholds from imperfect captions were not copied into native contracts.

Saved checkpoints: Lenrobum990966 had23crop choices/64decisions and1revolver/
2knives/armor_sharp0. Its fifth-hour closing2360865 had88/100crop choices,
distinct from primary83/100. Western final2248796 retains11fallback_line
position-only/unverified attack responses. These counts are not worker hours
or independent model refusals. Native bed-room mountain_cells0 at the inspected
checkpoints: previous losses are not established as a mountain-housing failure.

Open source gaps: solid7x7 mining choice without proven accessible entrance/
thickroof/hive/evacuation metadata; mountain Heater chosen from researched
Electricity instead of observed network; cold non-electrical furnishing lacks
a separate heating plan; furnished=True after blueprint ACK. No executor replay,
sole-cause attribution or claim of mechanical fixes to those gaps.

Source correction: mountain doctrine prompt now describes labor and roof,
heat, access, evacuation, insects, combustible contents, food/fuel and fungus
requirements. Read-only verification adds underground_status: selective native
roof coverage per room, actual observed door adjacency, hives/climate devices;
unknown coverage/geometry stays unverified and no safe escape path is inferred.
Native unavailable is not evidence of no hives. Two separate building doors
are not two exits from the same sleeping room.

Validation:11card tests passed, including4new boundaries; strategy importOK;
three saved checkpoints produced cards/SVGs; git diff --checkOK. Prior1268-test
full-suite result belongs to preceding audit and was not rerun after this addendum.
Installedbacc429/fc133c9 unchanged. Only offline source, documents and saved
observation tools changed; no orders/install/savePOST/replay/reset/new colony.
Campaign already ended and automationlayaPAUSED; no new death announced here.

Private report:outputs/laya-mountain-insects-audit-20261008.md; source index,
definition hashes, comparison cards and verification.json in its sibling folder.
Portable summary:docs/MOUNTAIN_INSECTS_AUDIT_20261008.md.

### 2026-10-08 — systemic plan, progress and actor-ownership verification

Direct user request: verify that tutorial/report lessons reach Laya and correct
recurring failures preventing a finite ending. This is an offline engineering
follow-up to the two audits; the Western native defeat remains recorded above.

Confirmed mechanisms corrected:

- A complete compact plan now survives every root domain/family/action and
  doctrine comparison within the312-token model state window. Ending, labor,
  shelter, clinical state, armament, research and development gaps are retained.
- Independent bounded observations survive intervening orders and state reload.
  Switching research targets without gaining points does not reset a stall;
  selected research/blueprint ACKs do not count as completed work.
- Live-threat and post-combat care preserve the exact actor while allowing
  other safe undrafted workers to make development decisions. Fresh threats,
  drafted actors and unresolved recurring entities retain their restrictions.
- Holding positioning without engagement is tracked across formation and
  wander changes, with a30-real-second AND2000-tick floor and fresh conservative
  safe-work checks. Missing distance/active assault/near patients close it.
- Downed patients already LayDown in bed do not receive another ineffective
  rest-priority choice. Feeding/tending/rescue remain separate; animal medicine
  policy is explicitly not food delivery.
- Native ending route/site/kind and fresh saved commitment prevent a generic
  progression label from starting a different terminal chain. Pending
  transitions remain resolvable.
- Mountain expansion checks exposed survey entrances and established supply;
  two-door furnishing uses actual room power, has independent cold heat, and
  reconciles built/queued/missing objects rather than marking furnished on ACK.
- colony_plan.py is in the install payload; local import dependency closure is
  checked for every packaged Python module.

Final full suite:1287 tests,0 failures/errors/skips,9.863seconds; total including
discovery/reporting10.529seconds. Native source/DLL unchanged. Route audit311
registrations/266literalcalls/27dynamiccalls, no missing or duplicate routes.
Actual payload staging contains the new module; live install59files retain
their recorded hashes.

Actual cached Laya CUDA/4CPU offline replay: four recorded states, both candidate
orders,8cases/22rootcomparisons, complete plan in each, maximum208/312tokens,
no selection_unavailable. Final choices: prioritize_plant_cutting at990966,
2360865 and698451; harvest_food_crops_early at1225199, rice/up to40/Ondra37382.
The priority cases have observed mature designated berry sources. Choices and
priority availability do not prove collection, food delivery or future survival.
An earlier ordering selected rest for an already incapacitated bed patient;
the final candidate correction removed that ineffective policy, preserving
other medical options. No live replay or game client was used.

Portable details:docs/SYSTEMIC_COLONY_VERIFICATION_20261008.md. Private report
outputs/laya-systemic-verification-20261008.md; tests, actual model prompts,
source hashes, routes and payload/install records in the matching evidence
folder. Diagnostic memory is a fresh baseline, not all prior session memory.

No new colony, game restart, pawn command, savePOST, speed change, live install
or memory reset occurred. The installed package remains bacc429/fc133c9 and
laya remains PAUSED. Future live nutrition, treatment, armed defense, research,
productive recruitment/trade and a completed selected ending remain unverified.
Monument executor and infestation_burn are not supported; mountain survey
geometry does not certify complete safe routes, thick roof or evacuation.


## 2026-10-09 — systemic-plan candidate starts East Edbonla

User requested one new colony after the systemic audit. Source/Python payload 3bf5ea8; native/DLL fc133c9 unchanged. All 60 payload/game-DLL records verified, including colony_plan.py. The prior checks passed 1287 tests and audited 311 routes. No release or tag was made.

Campaign b2aafaaef8a546bfa1e6ee73c490caca, tile 82712, seed laya-systemic-plan-008-20261009, map seed 16622162, Cassandra/Medium/Permadeath, TemperateForest. One generation. Baseline tick 23; autonomy began 2026-10-09T07:16:30.737366+00:00. Starting temperature 5.72 C, growing season true. Initially forbidden supplies explain baseline food zero. Founders Lover 393, Takumi 396 and Neiman 399; original scars and role limits recorded separately.

At 2026-10-09T07:22:40.155801+00:00, tick 127717: all three alive, not downed, bleeding zero. Physical 23 walls, one door, three covered beds and TorchLamp; room 30 at 16.22 C, animal sleeping spot outdoors. Research bench exists, Lover has Research job, GeothermalPower 16/3200: work began, no completed new research. Food 42 original meals, 37.8 nutrition; no growing zones or food plants yet, sustained supply remains unverified. Monkey Knuckles 2577 alive; initial training not credited as new. No verified sales, recruits, raid victories, new deaths or ending.

Early risks preserved: two PollutionPump frames need Construction 3 while observed levels are 1/0/1; no power network. Five sampled material replacement choices for the starter shell, four applied: one Silver and three Steel. At tick 62439 Lover/Takumi lack a ranged weapon, Neiman has ToxGrenades; successful conventional defense unverified. Actual root narrowing contains 307 complete plan instances in 36 bounded records; context visibility is not proof of useful choices.

One visible game PID 59996, director 164096 on CUDA with four CPU threads, observer 78700 and monitor 103152. Normal 3x, fresh statuses, stderr empty, force-pause false, actual ticks growing. Save XML tick 120000, mtime 2026-10-09T07:22:03.547961+00:00, same campaign and stable file; no extra save POST after technical startup saves 23/224. After autonomy no pawn orders, reset, rollback, restart or manual speed. Two PNGs viewed; card and coordinate SVG saved. First full hourly check no earlier than 2026-10-09T08:18:00+00:00. Automation laya is ACTIVE at minute 18 each hour, quiet without meaningful changes.

Private details: outputs/colony-008-systemic-plan-20261009.md. Evidence: work/longrun-008-systemic-plan-20261009/closing-startup-* and final-startup-live-check.json. Earlier Western defeat belongs to a separate campaign.

Late technical window check 07:36:01 UTC, tick 364587: same three founders and Knuckles alive, none downed or bleeding. Neiman has new knife-labelled Crack/Cut wounds with observed tend quality; exact treatment actor and full raid outcome unknown. Old Bite scar is separate. A Raid: Poison Gang letter and planted rows are visible; no raid victory or harvest credited from the screenshot. Minimized game window restored via sky, rendering verified, no gameplay input. Details in the private startup report and post-window-restore-live-check.json; hourly monitor remains ACTIVE, first full check at 08:18 UTC.

## 2026-10-09 — focused observation of Construction botched

User requested observation of the construction loop. Same campaign b2aafaaef8a546bfa1e6ee73c490caca, now Onium Planetary Concord (Permadeath). No runtime code, pawn order, speed, memory, replay, restart, rollback or save POST was changed.

At 07:53:48 UTC/tick 704483, CaravanPackingSpot frame 102894 at (152,107) has native percent_complete=NaN; the adjacent (151,107) is blueprint 102895. By 07:56:51 these locations have blueprints 104840/104900, with no completed marker. Installed native fc133c9 treats only SleepingSpot, AnimalSleepingSpot and ButcherSpot as instant markers. Vanilla CaravanPackingSpot has WorkToBuild=0 and no material cost, but falls into ordinary PlaceBlueprintForBuild. The actual game JobDriver_ConstructFinishFrame divides workThisTick by WorkToBuild inside 1-Pow(ConstructSuccessChance,...): positive work with success chance below one always fails at zero work-to-build. Frame percent is 0/0; FailConstruction replaces the blueprint and emits the botched caption. No training occurs in this toil when the resource container is empty. Exact effective pawn stats, total failure count, worker time and material loss are not measured; the marker itself costs no materials. The native marker handling defect remains open.

Separate blocked projects: PollutionPump 39144/39992/41080 at (152/151/153,108) remain 0%, minimum Construction 3 versus observed 1/0/2, with no working electricity network. These are not completed pollution removal or a proven source of the botched caption.

Two focused read-only sampling intervals 07:56:51–07:59:50 and 08:01:01–08:03:01 UTC produced 227 samples, ticks 756006–835317. FinishFrame appears in none; all five project IDs remain stable during these intervals. Harvest, hauling, care, rest and combat are real sampled work; shorter activity between samples is not excluded. Absence of retries during this period does not repair the invalid blueprints. Raw food varies 30–80 items, sampled meals zero; real intake/food production occurred, sustained supply remains unverified.

New animal loss: Knuckles 2577, native Death letter 793585 says torn to death; save 840000 confirms Dead and injuries naming a lynx. Exact wall-clock death second and final killing blow unknown. New human loss: Takumi 396 is downed during the raid at 798000; native combat at 08:01:36/tick 815275 shows Fazred 105822 with Kidnap, carrying_player_pawn=true and carrying_pawn_id=396 at (234,137). Absence from the normal map colonist list alone was not death evidence. Stable autosave 840000/mtime 08:03:16.470663 UTC/same campaign then confirms worldPawns/pawnsDead and healthState Dead/BloodLoss 1. Knife wounds name Fazred; a Gunshot combatLogText says Neiman's revolver missed Fazred and hit Takumi's left shoulder. Exact lethal tick and relative contribution of wounds versus friendly fire remain unknown. No separate Takumi Death letter appears in the sampled events/context, and kidnapped_pawns is empty; direct carry and save evidence take precedence over these omissions. Neither loss is attributed solely to construction without evidence.

At 08:03:28 UTC/tick 843341, Lover and Neiman are alive/mobile/bleeding zero, food 51 raw/2.55 nutrition, native GameOver and victory false. Full raid victory is not credited. Same game and three services are running, stderr empty in captures, force-pause false and ticks growing. Real PNG 07:57:18 UTC viewed. No live correction performed. Existing hourly observation continues with explicit construction-loop, food, defense and loss checks; first full hour remains 08:18 UTC.

Private report: outputs/laya-construction-botch-observation-20261009.md. Evidence: work/longrun-008-systemic-plan-20261009/construction-watch-*, construction-botch-source-evidence.json and review-20261009-075348/080134-*; raw decision reads bounded to last 8 MB and at most 100 records.

Late focused check 08:13:05 UTC/tick 1002693: CaravanPackingSpot blueprints at the same two cells are now 114670/115000; earlier 104900/104840 replaced, no completed marker. The defect persists; exact actor and total attempts between checks remain unmeasured. Pumps retain original IDs/0%. Native Takumi kidnapped letter at 816124 now confirms completed abduction; later save 840000 confirms death outside the map, not an alive captive. New Rhea 113204 is downed/LayDown/hunger 0.190/bleeding zero; membership permanence and joining mechanism unverified. Lover and Neiman alive/mobile/bleeding zero. Food 186 items: 4 meals/182 raw, 12.7 nutrition; provenance and sustained production not established. Native GameOver/victory false. Live evidence construction-watch-final-live.json; visible game restored/rendering verified through sky without gameplay input. Hourly laya ACTIVE with focused construction checks and these already-reported losses.

## 2026-10-09 — authorized construction API repair, technical stop

The user explicitly requested stopping the game and repairing the API and current
colony. Automation laya is PAUSED; only this run's director, observer and monitor
launcher/worker pairs were stopped. Game pause was verified at 1136890 with the
same campaign b2aafaaef8a546bfa1e6ee73c490caca and no subsequent tick growth.
Disk save XML 1136890/campaign/changed mtime/stable read is verified; save, Laya
memory, manifests, Player.log and both old DLL copies are backed up privately.
This is a technical pause, not autonomous survival or a fresh colony.

Source correction replaces the three-name instant-marker allowlist with the
loaded vanilla WorkToBuild=0 predicate. Placement validates before canceling a
matching legacy plan, retains normal construction and native placement hooks,
exports instant/work metadata and finite progress, and refuses construction
jobs on invalid instant projects. All 1287 Python tests and 33 actual native
helper boundary cases pass; preliminary Release-1.6 build has zero warnings and
errors; route audit remains 311 with no missing/duplicate routes. These offline
checks do not yet establish the installed DLL or live migration result.

Private pre-repair proof: construction-repair-pause.json and
construction-repair-before.json in work/longrun-008-systemic-plan-20261009.
Exact pending caravan blueprints at the checkpoint are 129041/129631, cells
(151,107)/(152,107). Ordinary pump frames 39144/39992/41080 are retained;
their separate skill/power limits are not fixed by instant marker handling.

Live repair completed with DLL 1.10.0+e8a195d, source e8a195da5509393f88da0e674823a5287646e932,
SHA256 4e13c8b3840b244344a23b76d831b3524f2d402478ac2d65e87b7698495f6681.
Both installed DLL copies match. Same-save technical close/load was required;
vanilla pause-on-load performs one initialization tick, 1136890 to 1136891.
The temporary pause-on-load preference was restored. No generation, rollback,
memory reset, pawn health edits or autonomous continuation occurred.

Paused live API confirms all 13 loaded zero-work marker definitions. Two exact
caravan blueprints 129041/129631 were migrated to completed Building markers
132830/132831 at (151,107)/(152,107). A repeated request retains both IDs;
projects contains no CaravanPackingSpot/instant frame. Prioritizing the old
instant project returned applied=false without a worker job. A blocked placement
over a normal pump frame was rejected; all three original pump IDs, progress and
delivered materials are preserved. These are not free completions of ordinary
buildings. Laya memory SHA256 is unchanged.

First post-repair save attempt failed with SafeSaver IOException/file in use
during rename. Retrying after a window without reading the original save verified
changed mtime, stable XML 1136891/same campaign and both real marker defs.
Root cause of the lock is not fully established; early polling reads could have
contributed. The stale error dialog was acknowledged and retained in an initial
PNG; a second unobstructed PNG was viewed. Final save mtime 08:45:56.179291 UTC,
SHA256 7e8f690c7bcce8649d2342b37bc05f17b836ccece5ea259fa2b7c46e0acfdb78.
RimWorld was closed again at 08:50:02 UTC after verifying pause/tick/campaign/save
hash. Actual process checks confirm game and all three managed services absent;
automation laya stays PAUSED until the user requests continuation. The technical
repair interval is excluded from 3841.280059 seconds of autonomy before the pause.

Private repair report: outputs/laya-construction-api-repair-20261009.md;
proofs construction-repair-* in this run folder, including actual save XML,
installed hashes, live API checks and construction-repair-after-visible.png.
The observed population losses are retained; this repair is not a colony victory.
