# Native raid laboratory

These fixtures execute real RimWorld jobs, projectiles, damage and hostile Lords.
The runner uses the ordinary `colony_director.main` and a separate production
`stream_observer.py` process, with normal model decisions and emergency speed
control. It records failures as well as successes. It never loads an ordinary save.

## Isolation

Build RIMAPI with `-p:CombatLab=true` into a separate output directory. Normal
builds exclude this directory's C# controller, routes, counters and hooks.
Start a dedicated game with `LAYA_COMBAT_LAB=authorized-20261014`, generate a
disposable world whose seed begins `laya-combat-lab-`, and record its exact native
campaign UUID. This is destructive setup **inside that disposable world**:
`/combat-lab/setup` removes existing map pawns and generated things/roofs across
the whole map, preparing flat soil before the cohort is created. Earlier revisions
cleared only an arena rectangle: an outside hive later spawned extra insects.
Those stopped runs remain invalid fixture attempts. No foreign actor is silently
deleted during an active fight.
Every setup, step and state request checks both the seed and exact campaign UUID.
Do not reuse a normal colony or weaken those guards.

The runner requires the lab endpoint, exact UUID, DLL path for a hash, and a new
private output directory:

```powershell
python tests/native_combat_lab/run_realtime.py --case ranged-203 --campaign-id DISPOSABLE_UUID --native-dll ABSOLUTE_LAB_DLL_PATH --output ABSOLUTE_NEW_PRIVATE_DIRECTORY
```

The runner does not launch, generate, load or quit the game. Cases pause at the
observed outcome; the runner stops only its own observer. Do not run another
director concurrently. Output includes full per-case native samples, actual damage
and shots, controller counters, director and observer records, source/DLL hashes
and the expected observer stop proof. Keep these private; do not commit live logs,
model memory, saves or ordinary playtest reports.

Qualification uses **one fixture per fresh native world**. Select its ID with
`--case`; the runner does not launch that world for you. Reusing a world can
retain faction trap knowledge, world history and other state beyond map cleanup.
`--allow-shared-world` permits an explicitly labelled development batch, never
an independent qualification. Setup also removes pawns dropped by destroyed
carriers and old corpses. Unexpected player pawns or hostile actors stop a run
as fixture contamination; they must not silently change its crew or opponents.
The result also retains native actor details when that guard triggers. A setup
guard failure or interrupted fixture is not a combat defeat or a successful defense.

## Controls and interpretation

At setup, generated adult defenders receive skill 8, rifles/SMGs and flak vests;
attackers receive skill 6 and scenario equipment. Traits/backstories remain varied.
The fixture supplies ordinary beds/food and, for fortified cases, prebuilt physical
walls, sandbags and traps. Fortified cases begin with the crew drafted on their
initial firing positions, so model loading cannot send them wandering off the line.
This does not prove that Laya built the defense or deployed that crew. Older laboratory
revisions that began undrafted retain their distinct setup evidence. Cell temperatures
are held at 20 C and random storyteller incidents are suppressed to isolate combat.
There are no health refills, damage/hit overrides, enemy target overrides or scripted
victories during the battle. Same numerical seeds across different generated worlds
are not guaranteed identical paired trials. The controlled temperature applies
to both native cell reads and room temperature reports. Earlier revisions that
held only cell reads at 20 C could report cold rooms to the care planner; retain
that inconsistency when interpreting their postcombat care cutoffs.

`hard_raids.json` covers ranged, mixed and melee groups outnumbering the defenders,
eight Neanderthals attacking a trapped choke, and real `LordJob_ExitMapBest` carriers
with and without an assault escort. A carried captive is initially downed through
native damage. Its survival, continued presence and stopped bleeding are required.

The strict pass requires no original defender ever downed, no deaths/disappearances,
no active enemy left, all defenders released, and completed native stabilization.
A separate survival pass allows temporary downing but still requires no loss,
stopped bleeding and a bed for a downed defender. `fail_fast=false` preserves the
whole fight; a strict first-down cutoff is not itself a native colony defeat.
Orders, warmups, queues and API acknowledgements are not shots, hits or victories.
One passed battery does not establish universal or guaranteed defense.

For the long preparation regression a case can explicitly set
`accelerate_staging_ticks: 1200` and `accelerate_staging_until: 178000`.
The monitor advances real native ticks only while the observed Lord toil is
staging and the director is running. The last approach and the assault use the
ordinary live clock. These results are labelled separately from unaccelerated
raids. Passing also requires three game days, actual ingestion and sleep, no
staging draft, and the observed assault transition. No pawn needs or injuries
are reset at that transition. Polls omit the growing sample archive; the final
result retains the full native trace and damage history.

The `rookie_knife` scenario uses skill 2, a bolt-action rifle and revolver against
ordinary knife attackers. It is a separate low-skill regression, not a substitute
for the outnumbered difficult raids. Fixture and runner source hashes accompany
the loaded runtime and DLL hashes. An interrupted or unreadable run cannot pass.

The production landing-cargo delay must yield to an actual assault even before
tick600. Loading a model alone does not complete its first inspected decision
cycle. Check that first selected defense and the actual native clock together;
do not grant pawns a scripted combat plan in the fixture to bypass that boundary.
An emergency retreat may temporarily lose a firing lane to use a safer rear cell.
