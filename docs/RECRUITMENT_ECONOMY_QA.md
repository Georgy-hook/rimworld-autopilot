# Recruitment, economy, and choice API audit — 2026-09-26

This note records what was checked in a disposable RimWorld 1.6 QA session and what remains unproven. It is not a claim that the colony can already win unattended.

## Choice API

The Python director now treats a live node-tree dialog, a choice letter, a naming prompt, and a quest acceptance as different game operations. Requests carry the observed dialog/letter text and exact enabled label. A stale request is rejected and retried after a short delay; it is not redirected to another window. Camera/navigation buttons on a letter are not offered as answers to a joiner or quest.

Live QA on a copy of `Laya Growth Rescue QA 2026-09-26`:

| Operation | Observation |
| --- | --- |
| Two-option `Dialog_NodeTree` | Stale text rejected; exact option activated; window closed. |
| Joiner `ChoiceLetter` | Stale text rejected. `Accept` completed a `WandererJoinAbasia` quest and removed its letter. A second event's `Reject` removed its letter without an API exception. |
| Quest acceptance | Unknown quest ID rejected. A live `Hospitality_Prisoners` quest requiring an accepter changed from `NotYetAccepted` to `Ongoing` with `ever_accepted=true`. |
| Faction/settlement name | Invented name rejected. A game-provided suggestion was accepted and the naming prompt closed. |
| Visiting trader preview | A live slaver's two human offers were read without a required `sale_category`; purchase was not executed. |

The QA session was closed without saving the named test save. The public mod still needs broader playtesting of DLC/modded dialog types. Older runtime logs also contain job-level refusals (patient feeding, an unreachable construction priority, an unsafe caravan party) that are not dialogue/letter dispatch errors; their presence must not be mistaken for proof that every action API now succeeds.

## First house

The three-bed starter blueprint contains exactly one door and no duplicate wall cells. Its placement search now requires a dry 7×7 site clear of existing plans and the game's actual edifice grid, with a two-cell margin around the walls and door. Existing colonies keep their saved building anchor when migrated to this check.

A live test found a separate root cause: the builder put floor blueprints down first, then mistook those floor plans for obstacles to the beds and lamp. Before the fix, the same 7×7 layout produced 25 floor plans, 23 walls, one door, **zero beds**, and no lamp. After rebuilding and reinstalling the mod, a repeat on the same named QA save produced 25 floors, 23 walls, one door, **three beds**, and one lamp, with no duplicate wall positions. Construction and colonist occupancy over multiple in-game days have not yet been retested.

## Ways to grow the colony

The [PopulationIntent mechanics](https://rimworldwiki.com/wiki/PopulationIntent) explain why visiting slavers and spontaneous joiners become less likely as population rises. Laya therefore cannot count on another slaver arriving. The supported routes and their current verification level are:

| Route | Current bridge status |
| --- | --- |
| Wanderer/joiner and transport-pod letters | Live `Accept`/`Reject` checked. Candidate is given food, bed, health and labor context. |
| Visiting slaver | Live preview checked: exact people, prices, health and skills are visible. Buying in this QA save was not executed. With Ideology, a purchased person may become a slave rather than a free colonist; the actual trade offer must decide this. |
| Friendly faction settlement | Purchase route and cash-preserving caravan trade session implemented and unit-tested; a real settlement transaction remains to be observed. |
| Downed raider/prisoner | Capture, prison-bed planning and recruitment policy exist. Recruitment is slow and can fail; it was not replayed in this audit. |
| Neutral crash survivor | Rescue/medical action exists; joining after rescue is possible, not guaranteed. |
| Wild human | Wild-human map API and Animals 7 taming order implemented; endpoint checked on a map without a wild human, so actual tame remains untested. |
| Rescue quest | Live quest list and acceptance checked; off-map rescue and return were not replayed. |
| Threatened joiner/deserter | Live letter and quest acceptance paths can answer the offer. The accompanying threat and diplomatic costs remain situation-dependent. |
| Refugee lodgers | May later ask to join, but arrive as temporary guests and may betray the colony. Laya sees this possibility; guest-mood management specifically for recruitment is not implemented. |
| Ancient casket occupant | Rescue or capture may be possible after opening an ancient danger. Existing danger handling can consider the site, but this route is not automated as a reliable recruit source. |
| Ideology ritual with Random Recruit reward | Exposed as a strategic possibility only when Ideology is loaded; no ritual execution API is wired yet. |
| Biotech childbirth | Long-term reproduction choice exists; not a short-term solution for missing workers and not verified in this audit. |
| Anomaly creepjoiner | A live offer can be answered through the letter/dialogue path; hidden risks are explicit in the model context. No occurrence was replayed in this audit. |

The [PopulationIntent mechanics](https://rimworldwiki.com/wiki/PopulationIntent) reduce several easy-join routes as population rises. The [quest guide](https://rimworldwiki.com/wiki/Quest) describes prisoner rescue, threatened joiners and refugee lodgers; the [ancient-casket guide](https://mail.rimworldwiki.com/wiki/Ancient_cryptosleep_casket) documents the danger of opening caskets. The [prisoner guide](https://rimworldwiki.com/wiki/Prisoner) covers recruiting captives; [Ideology rituals](https://rimworldwiki.com/wiki/Throne_speech) can offer a random recruit; the [trade guide](https://www.rimworldwiki.com/wiki/Trade) describes settlement, visitor and orbital channels. All of these are conditional on the game's live event, faction, DLC and stock.

## Economic course

The selected direction, main product, diplomacy and ending are persisted per actual colony and put at the front of Laya's next decision context. A revision now starts with an explicit keep/change choice; it is no longer silently replaced when one production prerequisite is missing. For routes with an implemented first production order, that order becomes a feasible option after shelter rather than leaving the chosen product as a GUI label. Existing rooms are not demolished when a course changes.

Initial course selection and actual Laya revisions are recorded in the colony's bounded `doctrine_history`; simply reaffirming the course adds no false change entry. The two most recent changes return to Laya's short decision context, so a new course is visible in later choices rather than only in the GUI label.

The economic outlook distinguishes candidate inventory from **completed sales**. It reports workshop readiness, a live visitor versus a settlement requiring a caravan, food reserve pressure, and the next milestone. It deliberately does not invent a silver-per-day or future profit figure from item market values. Purchases do not count as sales.

The saved QA state inspected in this audit contains no confirmed completed sales for the current colony. Consequently, the model's long-run profitability, settlement trade execution, and ability to hold a coherent policy across a full season **are not yet demonstrated**. Those require a longer unattended colony run with a real buyer and trade ledger entries.
