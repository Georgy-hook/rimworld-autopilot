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
