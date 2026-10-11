# Dayouinum thermal care and terminal outcome — 7 October 2026

## Recorded outcome

One random cold-biome landing, 54m22s continuous autonomy, native GameOver934203.
Two founders died from Hypothermia, a third from BloodLoss after observed insect
wounds, and the Labrador from BloodLoss. The final storyteller replacement was
kidnapped, not confirmed dead. No rollback or technical pause occurred during play.
The final save934368/campaign was checked on disk, then RimWorld quit at user request.
Automation remains paused. The original food-commitment revision was installed for
this run; the corrections below were made after the outcome, without live replay.

## Confirmed defects and changes

- A downed nonbleeding patient at Hypothermia0.643 remained outside while a21.50C
  roofed bedroom existed. The active frostbite TendPatient blocked rescue. Exact
  care yielding previously required starvation, feasible food and no life-threatening
  exposure. A separate native same-patient TendPatient→Rescue now requires thermal
  exposure, zero bleeding, no other protected disease and a usable roofed bed with
  safe patient temperature and at least5C improvement. FeedPatient, carrying and
  queued care cannot yield. Native workgiver/capacity/bed/path checks repeat at POST.
- The native rescue workgiver can select the nearest outdoor bed. Thermal rescue
  now examines alternative completed native-usable beds, reservation, occupancy,
  worker safety and the entire ordinary rescue route. It schedules normal Rescue;
  it neither relocates instantly nor edits health/temperature.
- Thermal rescue is compared before wound-only care. The model first compares the
  environmental response, then chooses an exact native actor/patient. Bleeding and
  real medical diseases retain their existing clinical path. Food is not a prerequisite
  for moving a freezing patient to warmth. Native-feasible mobile ill helpers are
  considered while protected care actors remain scoped.
- Detailed and combat incapacitation flags both exclude unavailable helpers.
  A failed unchanged care pair is remembered across JSON persistence for both30real
  seconds and2000ticks; new clinical circumstances and rollback reopen it. Other
  patients and ordinary workers remain available. Routine nonbleeding treatment
  avoids known hostile approaches instead of repeated civilian entry near hive guards.
- Building DTOs expose actual room, roof and temperature. Campfire prompts state that
  heating stops with empty fuel even under a roof; auto_refuel is not delivered fuel.
  Short thermal errand, hostile/gas/fallout and fuel-stock guards are retained.
- An already correct AttackStatic from a clear current firing cell is preserved
  on repeated focus-fire. The three terminal melee no-ops had no commands and were
  already preserving a job; they were not three failed attack orders.
- No local population means no new local building/economic doctrine choices. It
  does not declare a defeat; native world and ending evidence remains authoritative.

## Evidence correction

The earlier startup summary inferred arrival from LayDown targeting bed37788.
At84670 the patient was161,72 while that bed was184,174. Physical bed placement
was not proved. The report is corrected; `patient_in_completed_bed` already uses
native in_bed/current_bed and physical position rather than a job target.

## Offline checks and their limits

- 1256 Python tests, including8cycle rescue/persistence, stale-route rejection,
  bleeding/infection/feeding/carry protection, failed-care alternatives and actual
  bed-position evidence. An economic-intent fixture now includes a real resident;
  the separate empty-map case verifies no hypothetical development choices.
- 311 routes, zero missing literal calls or duplicate routes.
- Release-1.6 compiles with zero warnings/errors. Eight boundary cases execute the
  actual native thermal-improvement predicate, including unsafe destination and
  insufficient improvement; these do not run Unity pathfinding or bed reservations.
- Cached Laya on CUDA/4CPU selects rescue through the actual new pipeline in both
  native option orders, followed by8cycles with no repeated order. Native feasibility
  and acknowledgments are DTO-shaped offline fixtures. Early single direct-ID
  comparisons selected defer; the final response-then-binding pipeline is the tested
  change. This is not proof that every possible prompt or actor ordering is optimal.

Live completed rescue, actual warming/cooling, repeated fuel delivery, protected
care during a simultaneous attack and a fully recorded successful defense remain
open. The old pre-generation NRE is not explained or declared fixed. Crop and quest
gates from earlier runs are not closed by this cold landing. No new colony was launched.
