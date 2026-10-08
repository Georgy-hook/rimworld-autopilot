# Colony development audit — 8 October 2026

Follow-up: [systemic runtime verification](SYSTEMIC_COLONY_VERIFICATION_20261008.md)
records later prompt preservation, persistent progress, actor ownership,
ending consistency and real-model checks. Test counts below are historical.

## Evidence and scope

The user requested a comparison with real RimWorld players: population, prison recruitment, purchases, quests, family development, weapons, productive infrastructure and wasted effort. The private audit collected complete public captions for 33 original tutorials from Francis John, Adam Vs Everything and Noobert. Main development chapters were reviewed; the private source index distinguishes full-text reads from selected sections. The 12.45-hour corpus size is not a claim of watching every video in full. Full caption text is not part of this repository or its payload.

Sources supporting the main comparisons:

- [Francis John: work priorities](https://www.youtube.com/watch?v=Zn2S4MScvF8): specialists, backup labor and temporary priority changes. Equal priorities do not allocate equal time.
- [Francis John: starter part 1](https://www.youtube.com/watch?v=HtQF9vptgvo), [part 2](https://www.youtube.com/watch?v=vHtWRuJqQf4): food, prisoner handling, trade, equipment, research and use of unlocked recipes form connected chains.
- [Francis John: crops and power](https://www.youtube.com/watch?v=hc_MWFPbfLA), [kitchen](https://www.youtube.com/watch?v=op-XLjsERL0): first harvest, soil, labor, storage, ingredients and usable production.
- [Adam Vs Everything: more colonists](https://www.youtube.com/watch?v=2-X__Y2xu9k): distinct join, rescue, purchase, tame and prisoner recruitment routes with obligations.
- [Adam Vs Everything: wealth management 1.6](https://www.youtube.com/watch?v=rVu_LcalIeM): useful stock and construction, constrained production and trade into defensive capability.
- [Noobert: trading](https://www.youtube.com/watch?v=Wf9cQafwk-U): matching products and trader demand, a suitable negotiator and an actual transaction.
- [Ludeon: reproduction and children](https://ludeon.com/blog/2022/10/biotech-preview-3-reproduction-children-genetic-modification-release-date/): family development creates continuing care and supply needs, not an immediate adult worker.

Older numeric advice, animal zoning, collision tricks and version-specific exploits are not treated as current 1.6 contracts. Live definitions, native prices, job eligibility, routes and physiology remain authoritative.

## Confirmed defects corrected

1. The shelter gate required real `Bed` furniture even when every colonist had an enclosed roofed `SleepingSpot`. This removed preventive prison, research, economic and defensive preparation from a warm starter colony's choices. Usable human sleeping places now satisfy that gate; furniture upgrades remain available.
2. Shared human beds now contribute two sleeping places. Medical/prison/animal beds, ancient rooms and remote beds are not ordinary local shelter. Sleeping capacity does not establish assignment, safe temperature or fertility.
3. Preventive prison readiness uses actual stored nutrition when known, with a three-day preparation reserve. A count of ingestible “meal” items cannot override inadequate native nutrition. The unknown-nutrition legacy fallback remains explicit. Capture and recruitment still require their own checks and outcomes.
4. `prioritize_construction` is exposed only for actual unfinished projects. Missing furniture or a missing research bench without a blueprint does not justify changing the workforce to construction.
5. Workforce context distinguishes incapable, novice, temporarily unavailable and unassigned roles. Research and Crafting are included in skill needs. The root briefing retains measured development facts beside ordinary care/quest facts when they fit; critical clinical and quest information takes precedence under budget pressure.
6. Quest counts consume the native `active_quests` collection, excluding ended history and avoiding the old object-key count.
7. The saved-evidence verification card now includes assignments, work and skills, weapons/ranges/armor, prison places, family observations, workshops and research. Missing observations remain unknown; a bed or production queue never proves recruitment, birth, income or successful defense.

## Why this does not explain every failed colony

- At Thieron tick195173, the old shelter gate removed research/prison/cover preparation; the new gate retains those choices. It also retains refueling and patient feeding. This is an offline filter comparison, not a model choice or a completed building.
- At Western tick1225199, the same furniture gate persisted, but Research/Warden providers were unavailable or unassigned. Unlocking the gate alone cannot staff those jobs.
- Lenrobum tick2347655 and Roinor tick1074902 already passed the old shelter gate. Their farming, labor, architecture and outcome failures require separate evidence.
- Lenrobum's bounded 100-command sample had 84 crop configuration choices. This is command frequency, not 84% of pawn working hours. Its art bench had no bills and there was no verified sale; stored silver is not income.
- In four inspected starting rosters, no internal spouse/lover/fiance pair existed. The current pregnancy-approach executor validates an existing romantic relationship. Formation, fertility, pregnancy, birth and childcare remain separate stages to verify.
- Fenix was a real permanent ritual recruit. Men in black were storyteller assistance. Quest guests, offered recruits and carried patients do not automatically become permanent workers.

Food/clinical emergencies, live threats, material limits, protected care actors and native execution guards remain applicable. Population increase is an option with costs, not a universal survival requirement.

## Regression verification

`tests/test_development_readiness.py` uses native-shaped records to cover roofed ground places, shared human beds, real-nutrition readiness, pending project staffing, neutral predator defense, novice/incapable/unknown skills, temporary unavailability, native quest history and incomplete combat observations. A cached real Laya tokenizer checks that ordinary starvation and development facts fit the 312-token consequence budget together.

`tests/test_colony_verification.py` verifies that observed roles, armament, empty production and unknown family/prison outcomes are not converted into successful progression. The read-only card tool can run directly as a script or as a module.

The complete Python suite passed: 1268 tests in 7.827 seconds, with no failures or skips. Direct script execution generated a saved-state verification card and coordinate SVG.

No native/DLL contract changed in this audit. Offline tests and an expanded action set do not prove future live choices or survival.

## Follow-up evidence required

Each checkpoint should connect prerequisites to an actual result:

| Chain | Evidence needed |
|---|---|
| Defense | Available armed actors, armor, cover/routes before threats; actual attacks, losses and raid outcomes |
| Recruitment | Live offer or capturable person, costs, Warden/clinical availability; verified membership and assigned productive work |
| Family | Native partner/fertility readiness, safe place, food and caregiver capacity; actual pregnancy, birth and continued care |
| Food | Accessible nutrition and consumption, first harvest deadline, bridge source; repeated collection, delivery, cooking and eating |
| Economy | Skilled worker, recipe, inputs, capped bill and buyer; product output and ledger transaction with costs |
| Research | Appropriate bench, capable available assigned worker, actual progress; completed unlock put into use |
| Architecture | Construction/maintenance effort, congestion, fire/material/power costs; observed benefit to work, shelter or defense |

Do not score a native raid letter as a repelled raid, a selected project as research, an item swap as better equipment, a join offer as a worker or an accepted HTTP request as completed work. Unknown outcomes must stay unknown.
