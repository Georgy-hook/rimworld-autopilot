# Esia restart defects — 2026-10-05

## Evidence

The October 3 technical start failed before a valid director cycle: combat health conditions were display strings but the new clinical reassessment code treated them as objects. The real snapshot at tick 5485 also showed all three capable builders incorrectly excluded by `active_recovery_diseases`: Hypothermia 0.068 has a lethal threshold but no medical tending component.

The GUI's independent observer had started on opening the panel and continued issuing speed 3 while the director was failing. The last saved Esia state was tick 50889, not the intended technical pause at 5485. The three founders were alive but hungry and cold. This segment is not a valid autonomous test of the repaired director. The save is preserved as `pre-resume-latest-20261005.rws` in `work/longrun-007-progress-20261003-1312`.

On October 5 the actual latest save was loaded. The first pause request during load did not persist through completion of loading. A second request established a stable pause at 52885, verified by repeated API reads and the saved XML. These 1996 ticks are technical loading time and are recorded separately. No pawn, colony, seed or progress reroll was performed.

Live inspection also reproduced HTTP 500 in `/api/v1/medical/augmentations` on the paused map. In installed RimWorld 1.6, `MapPawns.FreeColonistsSpawned` reuses a list which is cleared/refilled on subsequent access. Nested doctor/ingredient queries during the outer patient enumeration invalidated its enumerator. A paused game does not prevent reentrant mutation of that list.

## Repairs and verification boundaries

- Clinical reassessment joins detailed medical records from `snapshot.colonists` by pawn ID. Combat display labels are not parsed as medical objects. Tests cover differently ordered lists, worsening disease, and label-only fallback.
- Nonimmune scalar diseases require evidence of medical treatment: currently tendable, or a present native tending quality/duration field. Zero quality and -1/0 remaining ticks still identify the component. LungRot remains protected between treatments; cold, heat and toxic exposure retain their environmental and rescue pipelines. A lethal threshold alone no longer excludes every builder.
- The observer requires a fresh `running` heartbeat and a living director process before allowing game time. Missing, stale, starting, errored or stopped directors cause a pause. Camera observation remains independent. Tests include eight paused cycles, running/error/recovery transitions and a failed camera read after the pause command.
- Augmentation context must enumerate a materialized patient roster while nested queries inspect eligibility and ingredients. It must return real options or actual unavailability; an empty response on exception is not an acceptable repair.

The integrated Python suite has 916 passing behavioral tests. The augmentation repair is checked by compiling the native mod and repeating the formerly failing live GET; text matching of the implementation is not used as evidence of native behavior.

The original snapshot now passes the actual candidate-generation path: all three construction workers remain available and the first required action is `unforbid_supplies`, under cold-start material access. This is a read-only replay; no game commands were sent. Its results are stored in `offline-resume-contracts-20261005.json`.

The next live gate is a successful augmentation response, successful director cycles, stable process count and actual food/shelter work. Unit tests and a paused API response do not demonstrate long-term survival or victory.

## First live continuation and additional failures

The installed augmentation endpoint returned HTTP 200 three times with 64 catalog entries and 234 real options. The observer held tick 52922 while the director was missing/loading. Autonomous speed 3 began at 08:38:45.903744 UTC. Laya unlocked supplies, placed a food stockpile and a ButcherSpot with an active bill, equipped a weapon, placed sleeping spots and ordered meals. All three founders remained alive.

At 08:41–08:43, repeated `resilience_rest` decisions ended in `laya_deferred` while no house was planned. The director was stopped for diagnosis and the observer correctly held tick 153033. The actual save was verified at that tick and backed up. This is a technical pause, not a colony outcome. Moon still had minor Hypothermia (~0.2505), so upright/fed status must not be reported as complete recovery.

Two independent blockers were reproduced:

1. The starter site search treated every tree as a permanent obstacle, requiring an empty 7x7 footprint plus two cells on each side. The boreal map has 3769 trees; the old search returned no site despite available materials and builders. A fallback now permits ordinary, non-forbidden wild timber while retaining all rock/building/plan/ruin exclusions and protecting special, cultivated and unknown trees. Native construction jobs cut blocking ordinary plants; no instant clearing is used. The saved map returns site (126,146); native read-only site checks accepted all 28 warm-layout placements.
2. Rest defer expired after 2500 game ticks, but actual 3x decision intervals advanced about 4366 ticks. It therefore expired before the next choice. Per-patient deferral now also observes a 120-second wall-clock floor, with immediate reassessment on changed clinical stage, urgency, patient or available assistance. Replay tests advance 4500 ticks every 10 seconds, persist memory between cycles, and verify both suppression and emergency bypass.

A separate logging defect duplicated the entire merged candidate context in weapon selection results, including ~781 KB of doctrine and ~597 KB of architecture data. Default logging now retains the selected IDs and actually shown evidence; full execution results are available under technical logging. Execution, model input and outcome accounting are unchanged. Console output is bounded for every result.

The common forest placement rules also cover hospitals/freezers and prison placement; prison sites now respect the native edifice grid and protected trees. All 22 positions of the cold shelter also passed native read-only site validation. A replay through real candidate generation now exposes `build_starter_base` alongside `resilience_rest`, instead of hiding shelter altogether. The complete integrated suite passes 937 tests; source changes were reviewed before installation.

## Thermal work and care scheduling

On source `fe94871`, autonomy resumed at 09:03:35.369122 UTC. One rest defer was followed by `build_starter_base` at 09:03:50, then actual construction: seven walls and a door were finished by tick 184175. This verified that forest placement and rest retry had been unblocked.

Cold exposure nevertheless deteriorated while the house was incomplete. At 09:05:39 the director was stopped and the map was paused/saved at tick 184175. Red/Furr/Moon had Hypothermia 0.517/0.566/0.516. All three were standing. Furr had lost a toe to frostbite and was bleeding at 0.96. Red was lying outdoors with rest 0.94, Furr was finishing a wall, and Moon was tending. These injuries are real and have not been reverted.

The next layer of failure was global work suppression: the nominal downed-care gate returned `wait` for any active treatment, even with no downed pawn; main then skipped the entire development cycle. A second post-combat-care branch did the same while noncritical treatment continued. Independently, cold construction focus chose a colony-wide wait whenever even one builder was working. Ongoing care/building must protect its actors and patients without preventing a separate capable colonist from finishing shelter.

The observer had correctly slowed from 3x to 1x at 09:04:38.401 UTC, but only after the old thermal threshold of 0.5. The threshold is now based on native serious stage (index 3, Core threshold 0.35) for both Hypothermia and Heatstroke. Native stage fields survive Python normalization, and observer status records thermal facts and the reason for slowing. No wrong installation was found: all 34 runtime hashes matched before continuation.

Native construction dispatch also checked reservations with `forced=true`, which can ignore another worker's reservation. An explicit non-forced reservation check now precedes the ordered job; forced dispatch can still wake a resting eligible worker, but cannot steal an occupied project. Native compilation succeeded with no warnings or errors.

The integrated thermal/care/worker changes pass 952 tests. Main-loop replay executes eight real priority orders/readbacks while ongoing care is protected; another series makes a builder newly downed and critically bleeding and verifies immediate medical reassessment and construction moving only to the remaining capable worker. Thermal regression now checks actual pacing through native DTO normalization rather than asserting that thermal injury belongs to the immunity-disease helper.
