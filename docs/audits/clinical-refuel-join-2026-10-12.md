# Clinical refuel join — 12 October 2026

The routine-care refuel check combined the detailed pawn roster with the combat
roster. Combat health conditions are display strings; they replaced structured
clinical records, causing an AttributeError while checking malnutrition before
the cold-patient test. A warm patient being tended could trigger the failure.

The check now retains live job, target and bleeding information while taking
medical conditions from the detailed roster, joined by the exact pawn IDs.
Missing or malformed clinical conditions make this heat transfer unavailable.
The director can continue evaluating other actions. Feeding, rescue, bleeding,
infection and other care protections remain in place.

Regression coverage includes display labels, differently ordered rosters, warm
routine tending, severe malnutrition on either pawn, live bleeding, protected
jobs and unknown clinical data. The focused source suites passed 47 tests; the
installed function passed 13 patient-heat tests and the formerly failing saved
snapshot. Real continuation completed decision cycles without the previous
Python exception. These checks establish recovery of the director, not survival.

Deployment was limited to this Python function. The existing native DLL and GUI
were retained; the pending shelf-policy update was not included. No release was
published by this repair.
