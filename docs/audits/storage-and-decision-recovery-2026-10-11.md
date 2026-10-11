# Storage and decision recovery — 11 October 2026

## Changes included in 0.0.8

The decision head has 312 tokens for state. Equal clinical facts are shared;
complete protected observations are retained. A comparison that cannot fit
returns a typed, recorded local defer instead of stopping the director with
`Consequence envelope exceeds Laya state budget`. Question ID, minimum size
and budget are recorded. This does not make the model's choices infallible.

Quest terms and reward alternatives now repeat observed fuel, food, room
temperature, forecast and the public duration. Before acceptance, changed
terms, roster and relevant supplies require a new review. A weather quest's
reward or `EndedSuccess` does not establish that its weather controller ended.
The 69-uranium example advertised a Schematic before acceptance; the later
book title must not be supplied to an earlier decision as foreknowledge.

Visible nonhostile downed pod arrivals enter native rescue and tending
comparisons. Bleedout deadline, temperature, current bed and real immunity
races survive target and caregiver selection. Native routes, reservations,
beds, protected feeding, carrying and urgent treatment remain authoritative.
A hidden automatically accepted pod quest is not a voluntary model choice,
and rescue does not promise a recruited worker.

Mood decisions preserve actual negative thoughts, break thresholds and joy.
Food, cold, grief, bedding and weapon penalties can require attention even
when recreation is already high. Brawler traits and observed ideological
weapon thoughts reach equipment selection; melee preference does not justify
closing into enemy gunfire. Unknown penalties for alternate weapons stay unknown.

Mining now reports why workers have no executable options. That is distinct
from the model explicitly declining a vein. Stocks and remaining selected
construction or recipe requirements accompany each compared product. Funded
frames and every recipe in the catalog are not charged again as current demand.
Manufacturing exposes loaded research, bench, builder, power, ingredient and
crafting requirements even when no current recipe is executable. A finite
one-batch intention can guide prerequisites; planning is not a manufactured item.

## Storage filters and placement

Shelves previously inherited broad filters, and material logistics could add
another material to an existing shelf. Paid new blueprints now carry their
role through the native blueprint, frame and completed storage settings.
Generic material logistics cannot widen an already specialized filter.
Mixed completed shelves can be specialized only when displaced stacks have
other roofed accepting storage with native capacity. Linked shelves are treated
as one group, with the whole changed filter shown as the cost.

| Plan | Allowed contents | Nearby destination |
|---|---|---|
| Kitchen inputs | Raw human food; no corpses or fertilized eggs | Stove or campfire |
| Meals | Prepared food | Kitchen or dining area |
| Cold food | Raw ingredients and meals | Freezer |
| Medicine | Loaded medicines | Patient beds |
| Workshop inputs | Components, non-bulk resources and textiles | Worktables |
| Bulk materials | Metals and stone blocks on the ground; no shelves or paid building | Free supply zone |
| Armory | Weapons | Non-prison storage |
| Dry goods | Nonfood goods, excluding corpses and chemfuel | General roofed warehouse |
| Fresh carcasses | Fresh animal corpses | Butcher, away from beds and kitchen |

Steel, plasteel, silver, gold, uranium and loaded metallic stuff definitions are
excluded from shelf profiles and shelf-widening options. Bulk materials get free
ground zones rather than an obligatory roofed warehouse. Components remain a
separate small workshop input; putting every metal on shelves wastes building
materials without meeting a current preservation need.

General storage uses Normal priority; local input buffers use Preferred. Filters
do not move a stack, refrigeration still needs real cooling, and current shelf
contents can differ from the new allowed list. Smaller ingredient buffers near
their benches and separating kitchen traffic from butchering are practical
layouts described by their authors in the [storage and base-efficiency discussion](https://steamcommunity.com/app/294100/discussions/0/1644290549123433646/).
Priority and filters are separate controls in the [RimWorld Access storage guide](https://rimworldaccess.com/building/zones-stockpiles/).

Six ordinary warehouse layouts provide loaded bare, concrete, paved or stone
floor alternatives with their real material cost. Bare floors remain a valid
early choice. Kitchen, medical and workshop plans start their site search near
actual completed facilities. Adjacency is a search preference, not proof of a
short safe route. New ordinary storage rejects water, mud, marsh, weak ground,
unrevealed cells, thick mountain roof, existing zones and occupied footprints.
The entire footprint and its margin must pass; placement repeats native checks.
This avoids blindly placing a warehouse against a rock face or on a bog.

Freezer shelves have food roles, the cooler has an outward exhaust, and the
cold-biome furniture template no longer adds a campfire or heater inside the
freezer. Food-only powered rooms can receive a normal cooling target after a
fresh port, occupant and exhaust check. A target temperature is not achieved cold.

## Conditional insect heat enclosure

The experimental proposal is offered only with revealed dry cells, a verified
thick-roof hot enclosure beside a non-mountain cold room, a capable builder,
nonflammable wall material, loaded coolers and at least 400 W of active surplus.
It needs no excavation into unknown rock. Two coolers exhaust north into an
empty roofed compartment; that compartment has no shelves, beds or ordinary
door. The plan can be rejected or deferred on any biome, including maps with no
suitable mountain roof. It is never an assumed part of every starting base.

The [first-hand infestation experiment](https://www.reddit.com/r/RimWorld/comments/q9kiwy/infestation_spawn_rate_deep_analysis_and_how_to/)
was checked against the installed 1.6 `InfestationCellFinder` and `Building_Cooler`
methods. Actual spawn scoring uses thick roof, visibility, walkability, colony
distance, mountainousness, temperature and light. Cleanliness or laying a floor
does not itself exclude an infestation. Older guide light thresholds are not
used as a 1.6 guarantee. Quest hives and other incidents can have different rules.

A cooler produces exhaust heat only while actively cooling; efficiency drops
with a large temperature difference. Reaching its cold target can stop heat
production. Heatstroke takes time, insects may breach walls, and a blackout or
changed exhaust geometry can defeat the plan. This is a conditional construction
option, not a demonstrated trap, instant insect death or a survival guarantee.

## Verification and limits

- 1414 Python tests passed, including actual cached-tokenizer budget checks.
- Native boundaries: 23 patient-heat, 8 thermal-transfer, 7 food mapping,
  22 decision-context and 14 storage-profile cases passed in isolated processes.
- C# Release-1.6 build passed with zero warnings and errors; 313 offline routes
  have no missing literal calls or duplicate registration.
- The recorded budget failure passed actual cached CUDA prediction in both
  option orders with 310 state tokens and intact clinical facts. The public
  weather offer with a labeled cold/empty-fuel fixture was deferred in both
  orders; all eight term/reward comparisons stayed within 312 tokens.
- Additional rescue, equipment, mining and manufacturing cases are explicitly
  synthetic feasibility checks. They do not reconstruct old motives or prove
  successful rescue, mining, crafting, hauling, cooling or insect kills.

No archived save, raw decisions, clinical identities or proprietary decompiled
game source are part of this public document. Private evidence preserves their
original timestamps and separates API, photograph and natural-save observations.
