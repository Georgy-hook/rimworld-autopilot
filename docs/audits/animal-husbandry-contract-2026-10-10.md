# Animal husbandry: alternatives, rations and thermal transfer

10 October 2026, unpublished 0.0.8 candidate. This is an offline source repair
and controlled model evaluation, not completed work in a running colony,
retraining of Laya, or proof of survival through winter.

## Findings

The agent already had ordinary animal rescue, pen/area policies, training,
milking/shearing, reproductive policies, and a kibble production module. Important
observations and alternatives were incomplete:

- A count-based sleeping-spot action could choose an outdoor position. A patient
  in that spot was then mistaken for adequate accommodation.
- Barn construction depended on doctrine and a one-time flag. Its flap could
  replace an exterior door and use wall material rather than textile/leather.
- Native needs and pen observations lacked one shared, species-compatible
  reserve forecast; pasture, stored food and future crops were not enough.
- Long seasonal context crowded exact emergency consequences out of the small
  model window. Adding prose to every question made selection worse.

The building catalog already includes terrain definitions. Straw was not
missing from it. Loaded availability/costs do not prove usable shelter.

## Housing alternatives

| Situation | Alternatives | Required observation |
|---|---|---|
| Mobile livestock, suitable weather | Enclosed indoor pen, or roofed barn with internal flap and its own fenced run | Accepted PenMarker, enclosure, feed, route, ordinary roping; fences do not exclude predators |
| Cold | Bare or straw floor; campfire/heater when available; free place in an existing measured shelter | Roof, species comfort, real temperature, fuel delivery or useful power |
| Heat | Passive cooler or exterior-wall cooler when available | Fuel, power, exhaust geometry and temperature |
| Pets supporting areas | Pet shelter or suitable permitted indoor place | Area restrictions, reach, predator exposure, actual food/bed access |
| Downed exposed patient | Roofed comfortable free place, then separate ordinary rescue to a completed free bed | Fresh clinic/worker/route checks; carry, arrival and warming remain separate |
| Incompatible temperature ranges | Separate housing cohorts | Each physical room, thermostat, marker/area assignment and feed allocation |

An animal flap permits livestock movement. It joins barn and run internally;
it is not the containing exterior boundary of an indoor pen. The new layout
keeps a normal exterior door or fenced run with gate, and uses the loaded textile
or leather requirement. See [animal flap](https://rimworldwiki.com/wiki/Animal_flap)
and [pens](https://rimworldwiki.com/wiki/Pen).

Inspected straw matting consumes two hay per tile, reduces filth and is highly
flammable. It provides neither heat nor edible feed. Bare flooring remains an
alternative when flooring would break the feed reserve. See
[straw matting](https://rimworldwiki.com/wiki/Straw_matting) and the
[official 1.3 announcement](https://ludeon.com/blog/2021/07/announcing-update-1-3-and-the-ideology-expansion/).

Warm-place preview requires species comfort, roof, legal empty placement,
no hazardous gas/fire and no nearby hostile/active predator. Potential carriers
are counted, not treated as completed rescue. Existing same-patient clinical
guards, protected jobs and thermal benefit remain. A cold occupied bed no longer
suppresses a measured warm-bed candidate.
Missing or failed native housing measurements suppress rescue destination
selection instead of falling back to an unmeasured outdoor sleeping spot.

Plans scale places with the cohort and keep a roof supportable width. Exact paid
intent is reserved before submission; partial plans reconcile at the original
origin. Blueprint ACK leaves construction, roof, heat, feed and transfer unverified.

## Context and forecast

`AnimalHusbandryHelper` extends the existing sustenance observation with:

- species/stage/diet, recovery food decline without starvation slowdown, adult
  allowance, pregnancy, nominal birth time and loaded litter support;
- actual temperature/comfort, completed compatible beds, roof, occupants,
  thermal benefit and connected enclosed pen IDs;
- each fresh feed stack once: nutrition, compatibility, safe current access,
  human use, roof and current-temperature spoilage;
- actual human demand, loaded hay nutrition, public five-day seasonal means
  and an explicit normal-soil post-thaw growth assumption.

Unavailable reads cannot authorize spending a reserve. Fresh animal carcasses
are separate possible direct food/butchery sources, not invented stored nutrition.
Desiccated bodies are not fresh feed. Kibble still needs a usable table, loaded
recipe, real ingredients and ordinary work; acceptance does not produce food.

`colony_husbandry.py` allocates nutrition across compatible stacks and animals.
Shared stacks are spent once. Current-access cover differs from cover conditional
on delivery; both are capped at 60 days. Human-edible feed is available only above
the larger of immediate human reserve and human consumption over the horizon.

The horizon starts at 15 game days and extends across approaching cold/hot
periods. Loaded hay can add normal post-thaw growth time. This excludes actual
sowing/harvest/haul delays and is conditional on soil/temperature, not a guaranteed
thaw or harvest. Young animals receive at least adult allowance; estimated litters
add future allowance. A 1.25 reserve margin is an exposed assumption.

The forecast includes target, compatible allocation, deficit, growth and birth
uncertainty. A compatible crop supplies a conditional lower bound on harvest
cells: 30 missing nutrition and hay yield 18 × 0.05 require at least 34 mature
harvested cells. This is not a sown plot or delivered feed. No single-crop acreage
claim is made when it cannot feed every observed diet.

Crop observations include harvested-product/grazing compatibility, live-plant
nutrition, pen membership and sow/harvest work. A separate legal fodder plot does
not replace a committed human field. Immediate human starvation does not fund a
fodder detour. Hydroponics/mod crops use actual loaded sow rules.

Hay inside a pen is a grazing alternative, not a promised full harvest. Inspected
haygrass yields 18 hay (0.9 nutrition) when harvested; eating the live plant does
not deliver that crop. Normal growth takes time. See
[haygrass](https://rimworldwiki.com/wiki/Haygrass) and the
[husbandry guide](https://rimworldwiki.com/wiki/Animal_husbandry).
Actual installed definitions/engine checks decide DLC/mod availability.

## Decisions and execution

Seasonal planning belongs in herd, fodder, shelter and kibble comparisons.
Emergency stages retain compact numeric clinic, human reserve, costs, risks and
inaction. The model still chooses and may defer. There is no scripted preferred
action, virtual food, teleportation or automatic slaughter.

Delivery is a finite ordinary non-storage haul, not a Critical stockpile that
attracts every human meal. Placement, patient, worker and route are rechecked
natively. Free spots use the loaded zero-work zero-material definition. Paid
shelter and floors use normal construction.

## Evaluation and remaining gates

Fixtures cover shared stock, incompatible diets, gates, winter/growth delay,
litters, human reserve, rot, unknown context, acreage, protected fields, grazing,
crop legality, flap materials/containment, large cohorts, straw reserve, disjoint
comfort, hot shelters, partial plans, fresh feed loss, cold-bed relocation and
bounded model packets. Native checks execute the production roof/temperature
predicate, not Unity routes or jobs.

Verified before packaging: 1,338 Python tests, including 29 husbandry tests;
all eight PowerShell native boundary suites (91 extracted-boundary cases);
313 registered API routes, no missing/duplicate routes; Release-1.6 compiled
with zero warnings/errors. The packaged DLL must be rebuilt after the source
commit so its informational version identifies that commit.

The cached Laya replay uses offline transport and both original/reversed order.
Before context compaction, warm-place scenarios deferred. Afterwards warm-only,
finite-feed-only, combined urgency and preventive-place scenarios selected a
feasible welfare action in both orders; both crop cases selected fodder purpose.
Crop identity remained order-sensitive. These are controlled choices, not native
execution, optimal selection or winter survival. Run
`tools/replay_husbandry_decisions.py` and retain the exact private result.

Remaining risks and live gates:

- Actual roof/heat/power, carriers, transfer, eating and repeated feeding must
  be observed after installation in an authorized run.
- Labor, storage, changing spoilage, cold snaps, drought and fallout can require
  more than minimum acreage/reserve; seasonal means are not weather prediction.
- Quarantine, fire compartments, explosive animals and incompatible herds need
  physical separation and routes; walls/areas/training are not guaranteed defense.
- Milk, wool, eggs, breeding, training, medicine and hauling compete for labor.
- Veneration, bonds, human meat, fertilized eggs and elective surgery have
  opportunity/ideology costs; successful surgery is never assumed.
- Fresh carcass potential is visible but not allocated to the reserve.
- The model is not guaranteed to choose the best option. Uninstalled source
  cannot change the behavior of an already running campaign.
