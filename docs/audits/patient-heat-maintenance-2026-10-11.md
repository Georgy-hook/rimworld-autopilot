# Patient heat maintenance — 11 October 2026

A completed cold-weather run exposed a heated room that became dangerously cold while nonbleeding frostbite care continued. Fuel later became available, but maintenance was not offered consistently before further construction. Nearby food-cache placement repeatedly conflicted with occupied cells or zones.

## Repairs

- A low-fuel completed campfire remains a survival choice in a cold, roofed occupied room. When fuel and an eligible worker are present, maintaining this source takes precedence over constructing another heater. Patient feeding and other urgent care remain available.
- A routine caregiver can be offered refueling for the exact current patient's cold room. Python refreshes the patient, current job, room, building and stock before sending the scoped request. Native code verifies the expected TendPatient job and patient identity, a compatible roofed current bed, actual hypothermia and cold, low fuel, available capacities, reservations and both routes.
- Feeding, rescue, carrying a patient, queued care, bleeding, disease care and immunity races remain protected. A different reachable urgent patient also blocks this interruption. Assignment acknowledgement is not fuel delivery or recovery.
- The terrain observation now exposes compressed native stockpile availability. The cache planner checks every cell for fog, standability, zones, construction footprints and recorded building reservations. It rechecks the selected rectangle before placing a zone and records only a successful acknowledgement.

## Checks

- 1381 Python tests passed, including eight new heat/cache regressions and existing installation and care suites.
- 23 cases exercised the actual native patient heat predicate, including changed patient identity, feeding/rescue, bleeding, infection, unsafe bed conditions, carrying, queued care, immobility and absent or sufficient heat.
- The native thermal transfer suite (8 cases) and food observation suite (7 cases) passed.
- The offline route audit found 313 registered routes, no missing literal bindings and no duplicate routes.
- The RimWorld 1.6 assembly compiled without warnings or errors.
- Cached CUDA inference through the production candidate and parameter path selected refueling in both runs. A separate unrestricted two-choice clinical head changed its answer when option order was reversed; this limitation is retained rather than presented as stable model reasoning. No game orders were sent by these checks.

The final raid established lethal knife wounds and blood loss. It did not establish a defective combat API or reconstruct every movement and shot, so no speculative combat patch was made. The earlier Unity rendering crash also has no established cause or claimed repair. Completed heating, defense and survival require the next live campaign.
