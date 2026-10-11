# Random cold landing after the care fixes — 2026-10-06

One generated colony on random tile 34927, world seed
`laya-care-ownership-20261006`, map seed 16622162; Cassandra/Medium/permadeath,
250×250. The ended published-release run on tile 119304 remains separate.
Baseline tick 21, three founders, approximately -30.8°C, no growing season.
The second founder's permanent leg scar was present at generation.

Python source 75aed23, native source e7bd662, native package cf04eca,
DLL 1.10.0+e7bd662. The last Python-only collection fix passes 1206 tests.

First autonomy began 17:05:31 UTC. Laya built 13 walls, a door, a campfire and
three sleeping spots and removed supply prohibitions. The roof completed, but
the room was still near -7°C and all three developed serious hypothermia.

A startup contract check found that the native care escape ownership IDs were
omitted by Python snapshot construction. The game was saved and technically
paused at tick 16077 around 17:06:51 UTC. Forwarding was corrected and verified
from actual server-shaped JSON through collection to actor ownership. The game,
map, progress and memory were retained; no new generation, rollback or restart.
Technical pause time is excluded from autonomy.

The same colony continued at 17:11:49 UTC; normal target speed is 3×, with native
thermal emergencies currently requiring 1×. At 17:12:18 UTC, snapshot tick 17645
and subsequent live tick 17779 confirmed progression. All three remained alive,
upright and nonbleeding. Room 34 was roofed at 13.16°C, outside -19.34°C. The
second and third founders were actually Wait_SafeTemperature, with hypothermia
reduced to 0.319/0.349 from 0.393/0.376. The first was eating with severity 0.425;
the third had acquired frostbite in a finger. Health 1.0 does not exclude thermal
danger. The 53 prepared meals are initial supplies, not verified cooking.

Save tick 17755 and mtime 17:12:18 UTC were verified on disk; the simulation
continued after saving. One visible game, one CUDA/four-thread director, one
observer and one read-only monitor were verified; Windows venv launcher/worker
pairs are not duplicates. Hourly observation resumed, first full check no
earlier than 18:12 UTC. Sustained warmth, clinical outcomes, escape completion
and autonomous survival remain unproven.

Follow-up at 17:16:58 UTC, tick 110889: all three were alive, upright and
nonbleeding. Hypothermia was absent from all health records; the third founder's
frostbite was also absent. Only the second founder's baseline scar remained.
The human bedroom was roofed at 19.78°C, outdoors -25.91°C. Two founders were
actually LayDown, the third Ingest. Normal 3× resumed; director/observer/monitor
were running with empty stderr. Stock had declined to 27 initial meals and
29 medicine. Early thermal recovery is verified; sustainable food is not.

## First hourly review after 18:12 UTC

This same campaign was renamed Complete Union of Leler (Permadeath).
The live campaign ID remained unchanged. Its autosave was verified at XML
tick 660000, mtime 18:14:25 UTC; the old filename in startup metadata was
not the current save path.

At 18:14 UTC, tick 659160, all three founders were still alive, but two
were downed with extreme malnutrition. Food was zero, campfire fuel zero
despite 162 wood, and the roofed bedroom had cooled to -19.64°C. One founder
was resting outdoors. Earlier small meat/meal recoveries did not sustain
the colony; saying that no butchery or cooking ever occurred would be false.

Two founders then died from Malnutrition at native ticks 666631 and 669060,
registered by observer at 18:16:23 and 18:17:05 UTC. Both native death
letters and exact_culprit telemetry confirm the cause. Their continuous
autonomy after the startup technical pause lasted approximately 64m34s and
65m16s. The surviving founder and a newly arrived man in black remained
alive at 18:19 UTC; GameOver and victory were false. His actual TendPatient
job is not proof of feeding or preventing another death.

Four sampled assign_real_bed actions failed with HTTP 500
medical_rest_not_indicated: ordinary bed relocation still uses the medical
rest endpoint. Four sampled refuel attempts returned unsafe_fuel_route.
The native routine route guard checks fuel-cell temperature; rejection
does not identify the specific stock or failed predicate. A cold exposure
conflict is plausible but individual route failures need further evidence.

Bounded decision samples also contained repeated ending requests and
deferrals while hungry. Thirty-two of 34 sampled progression_ending choices
were accepted requests, not verified completed milestones. Final repeated
hold_survival observed no new work while starvation advanced. No runtime
code, game orders, replay, rollback, restart or memory reset was performed
during this review. Hourly observation remains active.

Closing sample at 18:24:34 UTC, tick 694676: the last founder and man in
black were still alive. The founder's food rose to 0.949 and malnutrition
fell from 0.673 to 0.536, proving actual intake; the exact feeder was not
established by this sample. He remained downed with life-threatening
hypothermia 0.719 and new frostbite. Stock food stayed zero. Observer held
1× for the thermal emergency. GameOver/victory false; observation continues.

## Second hourly review after 19:12 UTC

At 19:16:07 UTC, tick 1176699, the same campaign had three live controlled
people: the last founder, man in black and a temporary hospitality guest.
The guest must be hosted for 22 days and will not work; she is not a verified
permanent colony worker. The founder recovered from hypothermia and was
actually sowing, but his and the man in black's malnutrition reached 0.772
and 0.789. All three food levels were zero, human_food was empty and native
reachable nutrition zero. GameOver/victory remained false. No new colonist
death was confirmed during the second interval.

Campfire fuel was actually 9.125/20, bedroom roofed at 28.95°C, outdoors
12.14°C. The construction backlog fell to zero. Thirty-one rice plants were
growing, not harvestable, with about 3.18 game days estimated to harvest.
Several other zones were being configured for roses, daylilies and dye
despite starvation. A newly created dye zone was changed to roses about
12 seconds later. This is observed reconfiguration, not proof of an infinite
cycle. Six bounded-tail native-menu interactions reassigned investigation of
the same fallen monolith, completion unverified. The nested decisions have
only endgame/threats/downed as structured facts; worker facts may also appear
in uncertainty text, so total loss of hunger context is not established.

New API defect: production logistics was unavailable inside a module marked
available. Two read-only GETs returned HTTP 200 with a zero-byte JSON body.
One weapon request also failed as unreachable/reserved immediately after
another pawn was assigned that item. No runtime fixes or game intervention
were made. Save XML 1140000, mtime 19:05:15 UTC and matching campaign ID
verified; observation remains active on emergency 1× for starvation.

During the subsequent review the last founder died from Malnutrition,
native tick 1205026, observer 19:24:35 UTC. Native letter and exact_culprit
agree. Continuous resumed autonomy lasted 2h12m46s; total autonomy excluding
the startup pause about 2h14m06s, around 20.1 game days. All three founders
are now lost. At 19:26:06 UTC, tick 1210255, the man in black, temporary
guest and a new arrival were alive. The man in black was downed with
malnutrition 0.979 but food had risen to 0.651. GameOver/victory false;
the campaign continues, without a new map or technical intervention.

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
