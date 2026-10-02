# Production and resource workflows

Target: installed RimWorld 1.6.4871, Core/Royalty/Ideology/Biotech/Anomaly. Odyssey is absent. Loaded defs determine costs, products and prerequisites. Gameplay/model launches were not performed.

| Mechanic family | Live implementation | Boundary |
|---|---|---|
| Fuel and power service | Existing building flick commands and allow-auto-refuel policies; actual connected/powered/output/fuel facts | Vanilla hauling/flick work required. No battery/cable forecast or invented electricity. |
| Kibble | Finite loaded researched batch, effective finite-bill filter, compatible animals, Cooking/skill gates | Diet compatibility is not proof of feeding access; sustenance adds pens, stocks and hunger facts. |
| Food/cooking/butchery/preservation | Sustenance module loaded recipe batches, kitchen sanitation, diets, cooler/storage policies | See sustenance inventory for raw-food poisoning, stockpile/freezer and animal care workflows. |
| Medicines/components/textiles/equipment/drugs/chemfuel/loaded recycling | `production_recipe_batch` discovers every researched available nonfood nonsurgery recipe at an existing usable table. Actual material choices, enabled work type, skill, live reachable/reservable stocks | Conservative feasibility estimate; bill acceptance is not product completion. No pawn/corpse human donors or fertilized eggs are allocated. |
| Basic subcores, mech forming/gestation/resurrection | Correct native BillUtility subtype mapping (parameterless previews, ID initialization only for accepted additions), mechanitor requirement, `PawnAllowedToStartAnew` bandwidth and gestator state, loaded cycles/ingredient costs | Continued power, work, ingredients, hauling and toxic-waste handling remain ordinary gameplay. Does not spawn mechs or force complete cycles. |
| Standard/high subcores | Separate scanner state/power/ingredient/occupant/brain-destruction observations | Building_SubcoreScanner is an enterable building, not a recipe table. Native gizmo/float-menu affordances manage scanners; generic production never invents a table recipe or supplies a human donor. |
| Hemogen extraction/administering | Pawn medical/native-affordance domain | ExtractHemogen is a surgery recipe, excluded from generic table production. Blood loss, donor rights and biological costs require patient-specific medical workflow. |
| Wastepacks/pollution/atomizer | Mech waste downside + ordinary available table recycling; progression waste observation and native utility/affordance routes | Atomizer is infrastructure, not assumed to have a recipe menu. No direct deletion of pollution/waste. |
| Crops/blight/hydroponics/seasonal planting | Existing colony_capabilities plus sustenance pasture/pen facts | Growth, weather, harvest and hauling remain vanilla; no fabricated yield. |

## Feasibility, finite bills and performance

A fresh observation scans eligible item/corpse stock once. Reachability/reservability is lazily calculated once per eligible worker and shared across recipe/material variants. Immutable recipe product/category/cost characteristics are cached by loaded RecipeDef. Research, table usability, bills, worker skills/priorities, reservations and mechanitor state are always fresh.

Ingredient allocation uses integer units in one shared pool. No-mix recipes require sufficient units of one allowed def; mixing recipes use loaded IngredientValueGetter.ValuePerUnitOf and whole-unit ceiling allocation. The same stack cannot satisfy multiple ingredient slots. Conservative ordering can decline a recipe that a more elaborate ingredient search could find; vanilla workgiver still performs exact search when the bill starts.

New finite bills use native MakeNewBill, including unfinished-item, autonomous, gestation and resurrection variants. Completed same-recipe bills are reused only with matching subtype and matching ingredient allowances. Existing pawn/filter restrictions are retained. Autonomous bills reset their completed cycle state before scheduling one new repeat. Existing pending bills suppress duplicate batch proposals. No indefinite production order is created.

Native Laya chooses category, actual recipe, and table/material with defer at every stage. Short local aliases and five independent consequence fields retain costs, downside, waiting and uncertainty in the 512-token decision budget. A late recipe among 50 alternatives has a budget regression test; it remains reachable to the model.

Endpoints: `/api/v1/production/context`, `/api/v1/production/policy`, `/api/v1/production/recipes`, `/api/v1/production/recipe-bill`. Recipe bill POST accepts only a regenerated exact option key. Python rereads before POST; server regenerates immediately before mutation. `applied=true` means finite bill accepted or policy changed, never completed production.

## Source inventory

Primary installed assembly, inspected with ILSpy: RecipeDef, IngredientCount, IngredientValueGetter, BillUtility.MakeNewBill, WorkGiver_DoBill ingredient search, Bill_Production/Bill_ProductionWithUft/Bill_Autonomous/Bill_Mech, Building_MechGestator, Building_SubcoreScanner, CompFlickable and CompRefuelable. Primary XML: Core RecipeDefs/Recipes_Food.xml and Buildings_Power.xml; Biotech Recipes_MechGestator_Light/Medium/Heavy/SuperHeavy.xml, Recipes_Food.xml and subcore/mech building definitions. No wiki numeric costs are hardcoded.

Secondary research cross-checks: [Subcore encoder](https://rimworldwiki.com/wiki/Subcore_encoder), [Mech gestator](https://rimworldwiki.com/wiki/Mech_gestator), [Mechanitor](https://rimworldwiki.com/wiki/Mechanitor), [Subcore softscanner](https://rimworldwiki.com/wiki/Subcore_softscanner), [Subcore ripscanner](https://rimworldwiki.com/wiki/Subcore_ripscanner), [Wastepack atomizer](https://rimworldwiki.com/wiki/Wastepack_atomizer). Installed 1.6 code overrides historical behavior and wiki estimates.

Validation: production Python tests include native budget retention, recipe worker gates, stale material rejection, utilities/fuel policy revalidation, kibble nutrition/worker/diet gates and defer cooldown. Shared C# build is coordinated by the root task. Runtime behavior remains unverified without an authorized game/model launch.

## Tutorial-driven logistics additions

Installed `Concepts_NotedSelfshow.xml` teaches Stockpiles, Forbidding, StorageTab, HomeArea, SpoilageAndFreezers and Deterioration; `Concepts_NotedOpportunistic.xml` teaches BillsTab and Shelves. These are operational prerequisites, not merely glossary observations. HomeArea explicitly determines cleaning/fire response; sustenance can include an existing enclosed kitchen and then offer normal cleaning. Shelves share settings when linked, so linked storage proposals are deduplicated and shared effects are disclosed.

`production_material_logistics` applies ordinary policies or starts an actual vanilla HaulGeneral job. It can permit one forbidden nonfood resource stack at an observed site without nearby hostiles, allow an otherwise unstorable loaded material in an existing shelf/stockpile, or create a roofed indoor material-only stockpile near a completed worktable. The exact existing unzoned footprint is encoded/revalidated; no building or material is spawned. Storage configuration is offered only when no existing allowed destination accepts that material, avoiding redundant shelves-times-all-definitions menus. Parent fixed storage filters are respected.

One exposed/damaged representative stack per def is used for allow/haul preflight; all material types remain represented. This bounds native job generation by material types rather than every map stack. Native haul job generation validates real destination/path/priority before proposal and again immediately before ordinary job acceptance. Care/bill workers are protected. Returned zone costs include floor cells; roofed ground still has different storage capacity/beauty from shelves. Storage/permission/job acceptance never counts as delivered materials.

Utility observations now include loaded PowerNet.CurrentEnergyGainRate, CurrentStoredEnergy and HasActivePowerSource. Utility and kibble model choices also use separate consequence fields and short aliases; net reserve/fuel/temperature evidence cannot be erased by a long unrelated context list.

Native preflight closure: per-worker forbidden stocks, loaded missing-capacity and table reserve/forbidden checks, existing bill ingredient radius, and Thing-level ingredient filters (including quality/special filters). Logistics collection calls pure HaulAIUtility/StoreUtility preflight; only accepted execution creates and orders a Job. No ingredients, products or workers are mutated during observation.
Kibble uses the same whole-unit Thing-filter/radius allocator and actual reachable enabled worker preflight. Loaded filters govern human meat/fertilized eggs/insect jelly permission; the decision explicitly exposes these costs instead of imposing universal food exclusions.
