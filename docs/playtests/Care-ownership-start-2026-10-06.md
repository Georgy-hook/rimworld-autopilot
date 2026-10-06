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
