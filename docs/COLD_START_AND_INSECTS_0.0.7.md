# 0.0.7: cold start and insect combat checks

## Observed failure, 29 September 2026

The random cold colony started at about -13 C. All three founders developed
hypothermia before the first room was closed. Laya ordered food zones, outdoor
sleeping spots, routine wildlife decisions and treatment while the wall and
door projects remained unfinished. A Man in Black arrived and tended patients,
but the room still did not heat up. The original three founders died; the
rescuer was alive in the last successful sample. The game process disappeared
shortly afterward, so the final fate of the rescuer is not established.

The same run ordered 25 wooden starter floor cells and later attempted concrete
in the room. It also ordered a grand altar twice before stable housing or a
prison. These orders consumed construction time without addressing exposure.

## Survival behavior added

- At -5 C with hypothermia, or at -10 C even before a patient appears, focus
  the next decision on a closed shelter and heat. A cold starter blueprint is
  7x7: 23 walls, one door, one central campfire and three sleeping spots. It
  excludes beds, lamps and floors until the shell is usable.
- The builder needs 160 wood, or 140 steel plus 20 wood for the fire. A pending
  wall/door is prioritized before the fire. If the only builder also has Doctor
  priority 1, move Doctor to 2 while there is no serious bleeding; Construction
  stays at 1. This permits work on the shell rather than repeated treatment of
  exposure in an unheated room.
- A finished floor or a pending floor blueprint is not a deficit. Concrete and
  path plans target only bare natural terrain, preserving wooden floors.
- Ritual buildings wait until each resident has a completed roofed real bed,
  there are at least three residents, and a prison is ready. Catalog auditing
  remains available, but generic catalog construction waits for housing.

## Tactics researched for insects

These are player reports rather than a guarantee for every game version. Two
independent firsthand discussions describe a **one-cell entrance** with an
armored melee blocker and multiple shooters behind: [Ludeon forum: infestation
again](https://ludeon.com/forums/index.php?topic=24548.0), [Steam: infestation
weapons](https://steamcommunity.com/app/294100/discussions/0/3440124373224214932/).
A later firsthand [Steam combat discussion](https://steamcommunity.com/app/294100/discussions/0/600780286524923310/)
describes keeping shooters close behind the blocker to reduce friendly-fire risk.
For an open area, the firsthand [Ludeon discussion on infestations](https://ludeon.com/forums/index.php?topic=26553.0)
recommends fighting from a narrow entrance or retreating and firing rather than
entering the hive room in single file. Its proposed sealed-room burn destroys
contents and depends on a genuine isolated compartment, so Laya does not issue
that tactic automatically.

Current executable rules:

1. Keep work routes away from a distant hive that is defending its territory.
   Do not turn ordinary hauling into a forced assault.
2. For active insects, expose `infestation_choke` only when combat state shows
   a real owned door with walls on both flanks, an armored melee fighter and
   at least two healthy shooters behind it. Pass the exact door ID to RIMAPI.
   A shooter with a clear shot uses focused fire; a blocked shooter regroups
   behind that door instead of advancing into the insects to find a shot.
3. A lone unarmored melee founder in insect contact cannot choose a long melee
   assault. Withdrawal remains available. Coordinated melee against a small
   number of insects remains available for a sufficiently large sword group.

## Still unverified

- Unit tests cover candidate selection and command payloads. The new behavior
  has **not** yet been replayed in a fresh live colony; the game was closed and
  the hourly observer is paused. A live run must check time to roof, indoor
  temperature, builder jobs, survival and whether Doctor priority is raised
  again when warranted.
- Door flank checks do not prove every cell behind the door is reachable or that
  the enemy cannot enter by another route. RIMAPI's `infestation_choke` still
  uses a generic position search; its exact formation and response to a moving
  swarm need a live combat replay before the tactic can be called reliable.
- Controlled fire, hive destruction after combat, and a multi-door fallback
  plan remain future work. No automatic burn was added.
