# Failed run medical and sanitation audit

Run: `longrun-007-recovery-20261003-1127`. Findings use streamed decision/timeline rows, final snapshot and the installed game XML, with no game launch.

## Confirmed mechanisms

At 08:50:57 Virgil was assigned Barbara. The decision actually exposed Barbara blood loss .383, bleeding 5.092 and 7270 estimated ticks remaining versus Yunxin .400, bleeding 4.387 and 8206 ticks remaining. Barbara was the earlier deadline at that observation. The error was subsequent care scheduling and availability: Yunxin was not ordered tended until 08:53:17, about 140 wall seconds later, just before her recorded blood loss death. Barbara's bleeding was already zero at tick407632 while Yunxin's blood loss was .795 and bleeding4.315. The old caregiver exclusion treated all continuing TendPatient jobs as unavailable, including a now stable patient's remaining wounds.

Virgil had LungRot on both lungs. Severity .036 at595478 rose untreated to .579 at704061. At727852 the left lung had .689 severity and .088 tend quality, the right .671/.357 quality. By808092 left severity was .972, right .595. Neither treatment had expired (41117 and42622 ticks left), so repeatedly reissuing tend would not cure the bad quality result. Installed native `Data/Core/Defs/HediffDefs/Hediffs_Local_Infections.xml` defines LungRot lethal severity1, untreated growth .3/day, quality dependent tending modifier -1/day and48 hour tend duration, with no immunizable component. The old immune-only disease helper excluded it entirely from urgent disease gates and work protection. A lack of an immunity race does not make this illness safe.

The final snapshot still has Yunxin corpse at(132,90) and Dweeb at(131,93), near the base anchor(128,91). A remote dump zone and cemetery blueprints had been ordered, but actual corpse disposal never followed. Installed native LungRot letter text identifies long exposure to corpse rot stink as its cause. Timeline lacks per-pawn gas fields, so the precise exposure cell cannot be reconstructed.

Dweeb's native death letter attributes death to PsychiteAddiction. Blood loss was also present; this audit does not replace that attribution with an inferred blood loss cause.

## Implemented changes

- Explicit `active_recovery_diseases` covers lethal scalar illnesses without relabeling them as immunity races. Medical summaries preserve body part, quality and expiry.
- Emergency doctor reassignment is offered only from a TendPatient job whose old patient has stopped bleeding and has no active critical disease, toward an untreated patient with <=6000 estimated bleedout ticks. The native endpoint rechecks exact current target, both patients, reserves and reachability before replacing the job. Residual BloodLoss alone does not block switching. Rescue, feeding and surgery remain excluded.
- Native active care includes tend targets and suppresses duplicate tend orders across the resilience module.
- `resilience_dispose_corpse` uses actual native HaulCorpses/HaulGeneral jobs for corpses within15 cells of occupied colony areas. It verifies an actual safe destination at least20 cells away, clear gas, native reachability and hostile route constraints. Creation of a storage zone or grave blueprint is not disposal completion.
- `resilience_shelter` offers a mobile pawn currently exposed to rot stink a completed clear reachable bed with no nearby corpse source; the native bed rest job remains observable pending movement.
- `development.sanitation_urgent` signals live disposal or shelter options for scheduler priority.

## Verification

Offline regression cases reconstruct the stable Barbara / dying Yunxin reassignment, guard continuing bleeding/illness/surgery, detect LungRot despite no immunity component, suppress duplicate tending and active corpse hauling. Medical faults6, existing medical sequences11, resilience21 and care/combat source contracts7 pass. Director285 tests has2 unrelated building catalog failures (bench material and butcher table steel availability). Native compile and live behavior verification belong to the final integrated run and were not claimed by this audit.

## Model order bias follow-up

The integrated diagnostic found that simply showing superior doctor quality did not reliably overcome model ordering bias. A shared helper frontier now removes only a strictly Pareto inferior known idle caregiver when all four observed comparison values are known: tending quality, tending speed, patient distance and medicine skill. A closer low-quality doctor versus a farther strong doctor remains a choice, as do equal options, missing statistics and unknown or active competing jobs. Both medical helper selection paths expose the exclusion reasons. The previous two-doctor list truncation was removed so it cannot discard an unexamined tradeoff. Regression medical faults9, medical sequences11 and director285 pass after the follow-up.

## Integrated verification

The two catalog fixture failures mentioned above were corrected before integration. Final suite: 907 passing tests; native Release-1.6 compilation: zero warnings/errors. Clinical transition scheduling and the remaining general-work disease guard now also use active recovery diseases. Live behavior remains the next-run validation.
