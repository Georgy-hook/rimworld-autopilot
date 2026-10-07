# Quest offers and consequential letters

Updated 2026-10-07. `colony_quests.py` owns the common terms review and exact
acceptance used by events and ending routes. It is included in the runtime
payload. Native definitions determine which quests exist; Python does not
generate quests or whitelist acceptable ordinary quest names.

## API contract

| Endpoint | Contract |
| --- | --- |
| GET `/api/v1/quests/catalog` | All loaded `QuestScriptDef` entries, source pack, native root, offer/utility flags and description rules; includes internal scripts for inventory. |
| GET `/api/v1/quest/offer?quest_id=…` | Fresh visible nonhistorical offer: full description, native eligibility/reason, offer expiry, public reward groups, eligible accepters, requirements, acceptance diplomacy and stable `offer_version`. |
| GET `/api/v1/events/context` | Visible active quests and letters with `quest_id`; accepted quests remain commitments. |
| POST `/api/v1/quest/accept` | JSON `quest_id`, `offer_version`, `reward_choices=[{part_index, choice_index}]`, `accepter_pawn_id` or null. All bindings, expiry and eligibility checked before selection. |

Legacy `/api/v1/colony/endings/accept` uses the same native guard and requires a
review body. Offered quest letters cannot accept through `/events/letter/choose`.
Python ending acceptance uses the common `/quest/accept` route. Old clients
without the new review fields are rejected; install matching Python and native
packages together before a future playtest.

`expiry_hours` is the offer acceptance deadline, not an accepted quest's work
deadline. It is null when absent or already accepted; `has_offer_expiry` states
whether it exists. `accepted_hours_ago` reports elapsed time for commitments;
work duration still comes from the public terms.

Public reward groups preserve alternatives. The legacy flattened `reward` field
remains for compatibility and is not repeated in Laya's input when groups exist.
`population_reward_possible` and the legacy population flag include `Reward_Pawn`;
they do not promise a healthy permanent worker. Hidden quests, hidden factions
and hidden future betrayal signals are not exposed as offers.

## Model input

The installed model has a 512-token window, a 192-token question head and a
312-token state budget including an eight-token reserve. The actual cached
tokenizer measures the complete JSON envelope. `review_pages` packs complete
small fields together and pages long fields without discarding their tail.
Reconstruction recovers all supplied public terms.

Every page repeats food, meals, medicine, mobile/downed residents, bleeding,
starvation, known defenders and threats, plus a short chosen ending. Missing
observations stay unknown. Full strategy and long doctrine text have their own
fields; issued-job history is excluded. Other fields supply observed reachable
food, patient/work restrictions, skills, defense/care capability, sheltered beds,
temperature, animals, beliefs and existing commitments.

The comparison rule covers immediate/delayed threat, diplomacy, travel, labor,
food, care, duration, ideology and the chosen ending. Quest text is data, never
instructions. Laya compares accept/defer on every page. Any defer prevents
acceptance; a later reward page cannot erase it. Multi-choice rewards and
accepters use complete bounded pairwise comparisons and exact native IDs.
Ties/defer leave the offer pending. Only a single alternative needs no inference.
Native legality is not a strategic recommendation.

## Fresh execution and results

Execution reads a fresh colony snapshot and offer. It binds the resident roster,
capacity and emergencies. New threats, greater bleeding, more starving residents,
lost observations or lost reserves require a new review. Small ordinary
consumption and improving injuries do not invalidate an unchanged decision.
The native guard checks the offer again.

All reward objects are resolved before the first native `Choose`, which can
remove quest parts and shift later group indices. Requirements and the accepter
are rechecked after selection, before `Quest.Accept`.
`quest_accept_requested_not_completed` means acceptance only. Arrival, work,
reward delivery, return and credits require later observations.

Joiner and already accepted quest letters receive their whole public text,
labor costs, colony facts and chosen ending. Different page responses or any
defer postpone the reply; early positive prose cannot outvote a late warning.
Ordinary single-page replies retain their native option labels.

## Interaction memory

Generic native menus and ending-site jobs share `interaction_pending`, keyed by
target and effect label without worker ID. An accepted but unverified action has
minimum 120-second and 30000-tick retry floors. Switching worker or module does
not immediately reissue the same investigation. Different targets/effects stay
available. This suppresses the observed rapid reassignment; it does not establish
completion or permanently forbid a later retry.

Nested purpose/target/worker and ending comparisons retain current food,
clinical facts and ending as protected factual units measured alongside effects.
Equal overlapping counters appear once. When the joint envelope needs a smaller
representation, complete thermal condition/stage/danger facts use readable text;
clinical values are not removed to make room for reward prose.

## Verification and limits

See the [dated audit](../audits/quest-prompts-native-contract-2026-10-07.md) and
[complete installed inventory](../audits/quest-script-inventory-2026-10-07.json).
Offline transport checks cover all 120 named scripts in installed Core, Royalty,
Ideology, Biotech and Anomaly, including automatic/internal utilities. XML
templates are not generated live offers. Odyssey is absent here. Unknown loaded
mod offers use the same review; their native behavior was not played through.

Exact quest monument blueprint placement remains unsupported for
`BuildMonument*` and `Decree_BuildMonument*`; those offers are deferred.
Complete transport, native compilation and two actual model diagnostics do not
prove every quest chain or reliable survival.
