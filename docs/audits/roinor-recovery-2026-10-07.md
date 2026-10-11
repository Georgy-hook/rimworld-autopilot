# Quest-review colony: final outcome and corrections, 7 October 2026

The single random landing ran from 07:21:26 to 10:27:09 UTC, **3 h 05 m 43 s**,
roughly 44.82 game days, without a technical rollback. The user ended the run.
The original three-person colony was lost; this is not a verified native GameOver.
Two later arrivals remained alive when the progress was saved and RimWorld closed.
Names, raw decisions and the save are retained privately.

| Subject | Verified outcome | Evidence and limit |
|---|---|---|
| Founder A | Death, Scratch, tick 1400386 | Predator-hunting letter preceded death; observed at 08:49:27 UTC. |
| Founder B | Death, Bruise, tick 2004266 | Native death letter; a Berserk break preceded death. Killer unverified. Observed 09:23:27 UTC. |
| Founder C | Kidnapped, tick 2109028 | Native kidnapping letter. Do not report a death. |
| Bonded dog | Death, Blood loss, tick 860978 | Four worsening, untended observations; no successful treatment established. |
| Tamed rhinoceros | Executed by cutting, tick 2040602 | Slaughterer break after malnutrition; not a successful planned food operation. |
| Later arrival | Death, Burn, tick 2679614 | Native death letter; permanent membership and exact fire origin unverified. |

At the end, food and medicine were zero, the remaining patient was catatonic and
malnourished, and a fresh arrival had a Rescue job. Sleeping places were outdoors;
the previous beds, generator, kitchen appliances and research bench were gone.
Microelectronics had reached only 77/3000 and there were no verified sales.
Raid letters establish multiple attacks, not a count of successful defenses.

## Observed defects and changes

- **Food planning:** no growing zone in the first roughly 18 days; later fields
  repeatedly selected flowers or timber. Native legal crop choices now receive
  demand, viable field capacity and harvest-delay context. Below five days of
  reserve with a food-capacity deficit, a food plot uses verified human-edible
  products; rice, potato, corn and compatible mod crops remain native choices.
  Existing viable occupied food plots are preserved in this deficit. Nonfood
  crops return when reserve/capacity permits. This does not deliver today's food.
- **Misleading harvest:** dying wild trees were described as rescued crops.
  Actual product and nutrition survive module dispatch and the low-food prompt.
  Designations use at most twelve nearby plants of one product, not an entire
  dying forest. Timber is still useful for fuel and cannot be counted as food.
- **Care ownership:** a patient's active Feed/Rescue job could collapse all
  colony choices into waiting. Spare workers may now continue productive work.
  Drafted patients cannot propose self-treatment. A fresh, exact unstarted
  Rescue may yield to critical bleeding treatment; a carried patient and other
  clinical jobs remain protected by Python and the native executor.
- **Ordinary beds:** sleeping-bed assignment uses its own native route instead
  of medical rest. Rejected or absent acknowledgments never claim an assignment.
- **Predators:** a neutral animal actively hunting a player pawn is included
  in combat threat, target validation, stand-down and care-route checks. Passive
  wildlife remains outside this predicate. Six actual native intent boundaries
  pass; a successful live defense has not yet been observed.
- **Repeated elective deferral:** implant planning now retains patient-scoped
  refusal for at least 120 real seconds and 30000 ticks. New stock/readiness or
  rollback invalidates the relevant history; changing limbs cannot evade it.
- **Power:** survival filtering retains connection of disconnected consumers,
  with explicit stove/cooler function rather than a generic construction label.
- **Refueling:** the returned fuel route identifies the exact stock, location,
  temperature and clothing comfort. Laya may explicitly permit a bounded short
  thermal trip for a near-empty cooking/heating/cooling facility. Native gates
  limit it to twelve cells, adequate mobility, no significant thermal illness,
  and temperature within 40 C of comfort; poison, fallout and hostile checks
  remain. Acceptance is not refueling completion.
- **Transport:** logistics cells use finite position DTOs instead of exposing
  recursive Verse vector properties. JSON is serialized before response headers;
  serialization failures produce a logged structured failure, not empty HTTP 200.
- **Strategy context:** the selected ending's requirements and diplomatic
  conflicts survive the next strategy comparison. A declared goal or an orbital
  trade channel is not income, research progress or victory.

## Verification and practical limits

1235 Python tests passed; 311 registered routes had no missing literal calls or
duplicates. Release-1.6 built with zero warnings/errors. Offline cached-model
replay using the native crop catalogue chose human food in both option orders
(potato and corn), after the earlier version still selected Fibercorn.
The root can still choose timber needed for a cooking-fuel gap; that is not
food production. The new colony must verify actual harvest, delivery and meals.

The isolated pre-generation NullReferenceException lacks a stack and remains
unresolved. Live animal treatment, autonomous raid defense, sustainable income,
quest rewards and a complete autonomous ending remain separate verification
gates. Offline checks do not establish that the colony will survive or win.
