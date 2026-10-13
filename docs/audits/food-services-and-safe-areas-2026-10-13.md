# Food services and temporary safe areas

This audit describes changes in the 0.0.9 candidate. A compiled build, offline tests and model decisions do not establish survival or a victory ending.

## Confirmed defects and repairs

| Defect | Change | Required observed result |
| --- | --- | --- |
| Mobile people had no early executable fallout shelter response | Native connected safe home areas and a normal walk are available before optional interaction pages. Native care, carrying, ingestion, mental states and drafted combat remain protected. | Actual arrival under a safe roof, reduced exposure, food and sleep access |
| An area could remain forgotten after the hazard | A saved record preserves the previous area. An independent native review runs after both 30 real seconds and 2,000 game ticks. It broadens completed safe connections and restores the earlier area after hazards clear or thermal injury recovers. Later area overrides are preserved; a missing previous area cannot become unrestricted silently. | Current restriction, location, needs, clinical state and job |
| Normal area filtering was treated as route safety | Both the initial transition and supported routine workflows check actual native paths. A short shelter transition is distinct from an ordinary exposed errand. | Safe complete path; area assignment alone is insufficient |
| Fresh grain with little HP looked like a long food reserve | Native food observations include HP, loaded deterioration rate, roof/shelf protection, rot stage and nutrition. The planner uses the earlier rot/HP horizon as an estimate. | Actual protected stock and consumption; loss cause is not inferred from disappearance |
| Food had no explicit delivery into available protection | Native choices can create a small free covered food pantry or schedule one normal haul into protective storage. Paths, cells, filters, capacity and worker commitments are checked again before execution. | Pickup, delivery and repeated feeding |
| Additional fields remained available after sufficient capacity | New food acreage requires a capacity or first-delivery gap. Existing sowing can pause during excess capacity or unsafe fallout and resume after a fresh gap; standing plants are retained. Animal demand and season remain separate planning constraints. | Finite acreage, real harvest/haul/processing, compatible feed |
| Legacy food/corpse zones chose terrain without checking current cell availability | Their complete footprints now use the native availability, dry foundation and mountain-roof grids; the corpse dump has no blind coordinate fallback. Unknown or unavailable cells suppress the placement. | Actual registered zone followed by delivery; no repeated conflicted rectangle |
| Freezer construction required all resources before exposing their need | A selected finite preservation goal carries loaded material/research needs into mining and trade comparisons. | Actual mined/bought materials and their delivery |
| The freezer template had an unsealed conduit gap | The east wall is completed next to the cooler. Loaded construction costs include conduits. Placement is read back before marking it issued. | Complete walls/door/roof, connected live power, correct exhaust, stored food and measured temperature |
| A full-HP component failure was invisible | Production observations report breakdown, required component, active repair and exact feasible workers. A normal `FixBrokenDownBuilding` job uses the native component target. Switch/refuel is no longer a repair remedy. | Component consumed, breakdown cleared and real output restored |
| Trade value was capped by merchant cash before barter | Live and caravan transactions can use conditional sale credit against a selected purchase. Minified finished art is recognized through native art components. Final native balance, reserve and execution checks remain authoritative. | Actual transaction, goods/membership, net balance; a preview is not income |
| The same unrepresentable optional policy repeated indefinitely | Exact unchanged consequence facts suppress the same unavailable policy subject until its facts change. Another person's care remains available. | Useful cycles and outcomes; this is not a model-crash repair |
| Nonimmunizable toxin with immunity zero was treated as an infection race | Worker planning requires actual immunity development before applying the immunity-race exclusion. Mild nonimmunizable exposure remains a shelter/work safety issue. Ordinary production bills are distinguished from medical bills using the native job shape. | Current capacities, exposure and actual care commitment |

Additional startup review corrected two proposal gates: created bulk ground zones are recognized under their current names, and a pen for unowned wildlife requires a selected livestock plan. Existing owned pen animals still expose their actual enclosure need.

## Area uses and exit rules

* **Fallout:** use existing roofed, clear home cells and covered connections. Prefer a connected footprint with meals/raw food, usable beds and completed work tables. A roof protects from fallout but does not refrigerate food or seal a room.
* **Cold or heat injury:** use the person's loaded comfortable temperature range and actual room temperatures. Existing warm/cool cells are useful only if reachable safely. Release after recovery and safe current temperature; reassess outdoor clothing and shelter instead of indefinite confinement.
* **Raid or active predator:** civilian work uses home cells outside observed enemy weapon/predator reach. Drafted defenders are controlled separately. An empty hostile list alone is not a verified raid victory.
* **Local fire, toxic gas, deadlife dust or rot stink:** exclude hazardous cells and paths. A clear destination behind a dangerous route is not a valid refuge. A restriction cannot replace extinguishing fire, corpse removal or appropriate treatment.
* **Allowed-area animals:** use species comfort, food and bed compatibility. Pen animals need a physical connected pen/barn; an allowed-area policy does not enclose livestock.

During a restriction, retain feeding, tending, sleep, recreation and useful safe indoor cooking, cleaning, hauling, crafting and research. Unmet food/rest access is explicit evidence requiring safe supply or a completed protective connection. New roofs, doors and changing temperatures trigger footprint review. The restriction must not erase a person's previous limitation, change the Home area, draft anyone, teleport, cure a hediff or count a queued job as completed.

## Performance evidence

The game state now exposes a bounded recent Unity frame-time window (mean FPS, 95th percentile and maximum frame interval), plus managed heap bytes. These are distinct from simulation ticks, whole-process RAM and GPU usage. Frame collection does not force garbage collection or change speed. Dynamic hazard checks remain fresh; immutable per-frame observed threat positions are shared within a context, and temporary-area geometry is limited to the existing Home footprint.

Live startup profiling identified a mining-context read taking 4,615 ms alongside a 4,621 ms maximum frame interval and an observer timeout. The search previously checked a native path to every block before sorting by distance. Mono also evaluated every predicate through `OrderBy().FirstOrDefault(predicate)`, even though a desktop .NET boundary test short-circuited. Explicit ordered iteration now stops at the first feasible block, preserving nearest-feasible selection and stable ties. In a paused live comparison it retained the same 68 option keys, reduced path checks from 1,442 to 68, and reduced the HTTP read from 1,038 ms to 157 ms. Whole-batch roof support facts share only the identical excluded-block set and are invalidated when the batch shrinks.

A later live read showed a second avoidable scan: a free worker was already on a cell colder than the ordinary work route permitted. Current origin fire, gas, fallout and loaded temperature limits are now checked before ordinary mining paths. Native diagnostics retain that blocker. Shelter transitions keep their separate contract; this optimization does not authorize unsafe work or suppress escape. Boundary regressions cover stable nearest selection, unavailable routes and exact temperature thresholds. These measurements are specific to the observed map, workers and jobs; they do not promise a constant FPS.

This identifies one measured source of frame stalls. It does not establish the only cause of the user's previous freezes or repair an unidentified Unity render/shader fault. Live before/after measurements and ordinary long-run observation remain distinct from the algorithmic test.

## Verification

The candidate passed 1,470 Python tests, all 18 native boundary suites and 315 offline route bindings, with no missing or duplicate routes. Native compilation succeeded with zero errors and warnings. New regression cases cover food deadlines, retained plants, resumption, missing components, finite goals, the freezer wall, small meal batches, clinical job shape, fresh area options, native stockpile availability and bounded model comparisons. Live gameplay outcomes require the next campaign's actual evidence.
