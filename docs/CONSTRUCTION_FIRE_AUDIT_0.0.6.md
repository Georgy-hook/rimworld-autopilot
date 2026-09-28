# 0.0.6 construction and fire audit — 28 September 2026

These changes were developed on the 0.0.7 feature branch and included in the final 0.0.6 release at the user's request. The checks below describe observed behavior and open limits, not a claim of complete autonomous survival.

## Construction coverage

The installed RimWorld 1.6 game with its current Core/DLC/mod set exposed 533 player construction definitions: 232 ThingDef buildings and 301 TerrainDef constructions. The previous API catalog omitted all 301 constructed terrains. The catalog now returns all definitions with research status, exact compatible materials, and a per-definition metadata error field. Laya can choose any currently unlocked and affordable definition through a category and exact-def choice, with game-validated placement before issuing a blueprint.

On the controlled Test 14 save, 176 definitions were research-unlocked. The site-options endpoint returned a normal response for every one of the 533 definitions: **0 API errors, 0 metadata errors, 0 material-compatibility omissions**. Near the base (radius 6), 172 of the 176 unlocked definitions had a valid location. Four needed a special context: FungalGravel requires a thick roof, WaterproofConduit requires suitable water terrain, Hopper must adjoin a device that needs one, and Bridge requires bridgeable terrain. An empty site list with a game-rule reason is expected for those four; the audit did not force placement of all 533 objects.

ButcherSpot, TableButcher and SimpleResearchBench are in the live catalog, unlocked, and have valid nearby sites. Direct API placement of the butcher table and bench was verified in controlled reloads. In an actual 3× Laya run, Laya selected `build_research_bench`, placed a wooden SimpleResearchBench blueprint at (164,152), and the game completed the building. Laya then chose Smithing and set a researcher's Research priority to 1. Research progress remained at zero during this run, so effective research staffing is still unverified.

Building orders now validate research, compatible materials, occupied footprints and the game's actual placement rules. A reported successful catalog order is checked against a real blueprint or finished building. An already floored room is skipped without another invalid Concrete request. A construction job blocked by reachability, materials or skill returns `applied: false` with a reason instead of HTTP 500, and Laya backs off that project. The final replay logged 56 colony decisions and no API error backoffs.

## Fire replay at 3×

The first 3× continuation reached a major house fire: 54 live fires at tick 909,213, 52 inside Home, with rooms over 500°C. The director did not offer a persistent in-home firefighting action; all three colonists had Firefighter priority 3 while several ordinary jobs were priority 1. The fire decision existed only for an incident event or an out-of-home area expansion. Post-combat treatment also delayed colony decisions. At tick 942,146 the delayed-response run had one fire remaining and colony wealth around 13,291.

The repair adds a persistent fire action whenever a live fire threatens buildings in Home. It assigns Firefighter priority 1 to eligible colonists, one per decision, and focuses the choice on that immediate threat. An active in-home fire can now staff firefighters before repeated post-combat care. A separate compact post-combat model context addresses the observed 8,734-token warning against the model's 8,192-token limit. A direct CUDA Laya decision on the restored no-hostile control save used 512 input tokens and emitted no length warning.

The saved 54-fire state was replayed with the new code. The director assigned Firefighter priority 1 to all three colonists before the 3× observation; the monitor recorded `BeatFire` jobs in 18 of 25 samples. The blaze briefly grew to 109 fires, then reached zero at tick 942,115. All three colonists survived. Colony wealth at that point was around 13,969. The two runs differ in startup timing and model decisions, so the wealth figures describe observed outcomes, not a controlled estimate of the patch's benefit. The repaired run still lost substantial property: an already large fire can outrun three firefighters before they contain it.

The fire replay logged 23 decisions and no API error backoffs. It expanded Home around exterior fires 11 times as the front moved. This behavior worked, but the area-growth policy and firebreak planning need further scrutiny on a fresh colony with an early, smaller fire.

## Verification and open gates

- 334 Python tests pass; RimWorld 1.6 RIMAPI Release build completes with zero errors and warnings.
- Full final-DLL catalog and site audit: 533/533 normal API responses; 172/176 unlocked definitions have a nearby site.
- Live 3× replay: Laya built a real research bench and selected a project. Live fire replay: all three colonists received and performed Firefighter work, and the recorded fire reached zero.
- **Open:** Research did not gain points. The chosen researcher also had Cooking, Construction, Hauling and other work at priority 1; assigning Research priority 1 alone did not reserve time at the bench. Verify research labor allocation without compromising food or emergency work.
- **Open:** Run a new colony from before ignition to confirm the fire response starts when the first flames appear and to measure structural losses. The saved 54-fire replay tests recovery from an already severe incident.
- **Open:** Generic catalog choice produced a Grand Altar and HoldingSpot in the construction replay. Confirm that discretionary catalog spending follows colony need and does not crowd out food, research or fire prevention.
- **Open:** Packaged 0.0.6 installation and extended autonomous survival checks remain separate verification tasks.

The original `Laya Test 14 Autonomous Butchery Verified 2026-09-28` control save was restored and paused after testing. Fire diagnostics were preserved as `Laya 007 Fire Replay Before Fix` and `Laya 007 Fire Extinguished Early Response` without replacing the control save.
