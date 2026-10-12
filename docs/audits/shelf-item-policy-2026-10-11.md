# Shelf item policy review — 2026-10-11

This is a follow-up in the **0.0.9 candidate**. The published 0.0.8 package
and the payload already loaded by the current campaign are separate versions.

## Why wood was still on shelves

The earlier exclusion covered metallic stuff and stone blocks. It missed
WoodLog and loaded Woody stuff. The fuel profile explicitly admitted wood;
the dry-goods filter also admitted ordinary non-ingestible wood. That was a
policy omission, not evidence that the model had calculated a benefit.

## Policy

Shelves provide density and deterioration protection. They do not refrigerate
food or stop temperature-dependent rot. These benefits may justify a small
input buffer or protected valuables, but an eligible item does not establish
a need to pay for shelves or a new warehouse. Compare existing protected
ground capacity, stock actually present, construction materials and labor.

The user explicitly chooses free ground zones for bulk construction resources.
This review does not offer a wood/metal shelf exception for storage density.

| Item group | Default handling |
| --- | --- |
| Wood and loaded Woody stuff; metals including precious metals and bioferrite; jade and loaded Stony stuff/stone blocks | Ground construction-resource zones. Assess wood exposure, roof/support and fire separation; ground does not mean weather-proof. |
| Hay | Separate covered ground feed reserve; temperature and spoilage still matter. |
| Chunks/slags, minified buildings/plants, unfinished work | Suitable ground handling. Unfinished work remains tied to its recipe; no shelf investment. |
| Corpses and human remains | Separate appropriate ground handling/burial/butchery; no kitchen, armory or ordinary valuables shelf. |
| Fertilized eggs | Explicit incubation/temperature policy; no automatic kitchen/freezer shelving. |
| Human raw ingredients, meals, chocolate/insect jelly and other compatible food | Food-specific shelves may be useful near cooking/dining or inside a working cold store. Animal feed, drugs and special biological supplies are excluded. |
| Kibble | A small separate animal-feed shelf may be useful in an appropriate animal room. Animal diet/access must be checked separately; this is not a reserve for humans or proof that strict carnivores can eat it. |
| Medicines | Dedicated supply shelf near care. Shelf protection is not treatment or refrigeration. |
| Drugs | Dedicated supply filter, separate from ordinary goods and food. Availability does not authorize consumption or a drug policy. |
| Components, advanced components, neutroamine, small manufactured inputs, textiles and processing plants | Limited workshop/textile input shelves may be useful beside a completed facility. Bulk wood/metals/stone remain on ground. |
| Ordinary weapons/apparel | Armory shelves may be useful; quality, taint, pawn suitability and loadout remain separate decisions. Explosive equipment follows the hazard rule. |
| Books, techprints, neurotrainers, implants, relics and reviewed dry valuables | Protected dry shelf space may be useful. AI/techprof cores, tusks and horns have explicit coverage. |
| Chemfuel, mortar shells, explosive/gas-releasing equipment | Isolated appropriate storage policy. No automatic mixed shelf allowance, kitchen/workshop ground buffer or generic stockpile widening. This change does not claim a complete hazardous-warehouse executor. |
| Wastepacks | Separate frozen ground storage/pollution handling. Native ordinary shelves reject them. |
| Genepacks, xenogerms, ova/embryos, hemogen; studied/holding-platform/anomaly samples and objects | Their specific storage/use requirements must be reviewed. No ordinary warehouse or generic shelf widening. |
| Unknown definitions | No implicit shelf allowance. Use a reviewed purpose before extending the policy. |

## Enforcement and repair

- Profiles resolve from loaded definitions and inherited categories rather than
  assuming that every nonfood item belongs in a dry warehouse.
- A paid storage blueprint needs an explicit reviewed profile. Empty ground-only
  shelf profiles fail before floor or building mutations.
- The generic “allow this material on a shelf” option was removed.
- Existing mixed filters can be restricted through a separately chosen, freshly
  validated ordinary policy. It retains safe allowances, priority, quality and
  freshness. Current displaced stacks need another accepting destination with
  observed capacity; other inappropriate shelves do not count as destinations
  for excluded goods. This is not proof of route safety, concurrent allocation
  or completed hauling.
- GET does not change settings. Policy acceptance does not move a stack.

## Evidence and limits

- Read installed Core, Royalty, Ideology, Biotech and Anomaly XML: **449 explicit
  item definitions**, with inheritance/categories projected for an offline
  policy audit. Every projected row has a documented classification; zero
  unclassified rows remain in that inventory.
- The projection checks categories, material types, food and relevant
  components. It is not a running-game dump: XML patches and generated corpse,
  meat and frame definitions need native boundary coverage. Actual runtime
  eligibility continues to use loaded EverStorable, race diet and parent
  storage filters.
- **75 native assertions** cover wood/metal/stone derivatives, hazardous
  components, corpses, hay/kibble, fertilized eggs, unfinished/minified goods,
  biological/anomaly items, reviewed valuables and an unknown definition.
- **1414 Python tests passed**, including fresh revalidation of a changed
  shelf-restriction choice. Native compilation succeeded without warnings/errors.
- No current game settings, hauling orders, processes or installed payload were
  changed for this review. There is no live claim that existing shelves have
  already been emptied.

Primary background: [Ludeon’s shelf changes in update 1.4](https://store.steampowered.com/news/posts/?appids=294100&enddate=1665179782&feed=steam_community_announcements).
Installed 1.6 shelf definitions and native storage behavior were also inspected
locally; proprietary source and raw audit files are not published.
