# Quest and decision follow-up — 10 October 2026

This follows the completed candidate playtest and the user's request to identify
the quest exception, improve mining/feed choices, and then start a new test.
The completed campaign and its evidence remain private and preserved.

## Reproduced quest failure

The preserved save contains expired, unaccepted joiner quests whose
`QuestPart_JoinPlayer`, `QuestPart_DropPods` and `QuestPart_PawnsArrive` pawn lists
include null references. Using the installed game's actual `Assembly-CSharp.dll`,
each of these three native parts reproduces `NullReferenceException` through
`Quest.IncreasesPopulation` → `PawnsArriveQuestPartUtility.IncreasesPopulation`
→ `pawn.RaceProps`. The old collection reader called this getter on historical
quests. This reconstructs and reproduces the saved-record trigger; the first
HTTP failure did not retain its original stack or exact offending record order.

Historical DTOs now read stable metadata without invoking live population,
target, faction, reward-string or acceptance callbacks on discarded actors.
They explicitly disclose historical status. Active callback failures still
produce an unavailable/partial record through the existing observation boundary;
they are never represented as a healthy offer with guessed requirements. The
save and native pawn lists are not repaired or edited by this read boundary.

## Decision context and staging

Mining and measured animal feed/thermal choices now retain complete numeric
facts for the actual compared options inside the token budget. These include
yield, nominal value, remaining ore HP, mining speed, estimated work, worker
food/job/malnutrition, or animal hunger/illness/temperature, finite delivered
nutrition and the remaining human reserve. Oversized required facts fail
explicitly instead of silently cutting away constraints.

Purpose/product/subject classification is separate from the final exact action
comparison. The final comparison still includes waiting. No alternative action
is forced after Laya chooses `defer`. Native discretionary mining eligibility
also excludes urgently hungry/starving workers, independently of model choice.
The work estimate follows the loaded 1.6 pick-hit interval and ore HP damage;
travel, needs, interruptions and mod changes remain excluded.

The earlier mining fixture described a starving worker with no food. It was not
a valid demonstration of a healthy profitable opportunity. The revised fixtures
separately describe fed workers and finite feed with a preserved human reserve.

## Verification and limits

- 1,308 Python tests passed. Four new tests use the cached real tokenizer to
  verify complete compared facts and both option orders within the model budget.
- The actual native getter reproduced the three null-pawn failures; the new
  production boundary avoided their callbacks. Three standalone boundary cases
  additionally preserve healthy live reads and live failure visibility.
- The postmortem native suite now has 27 cases, including work estimates per
  cell and invalid mining speed. Release-1.6 compilation remains a package gate.
- The final cached-model replay covers 10 scenarios, with both option orders.
  Healthy mining chose the exact Jade batch in both orders. Finite feed chose
  delivery in both orders, both alone and when a thermal alternative was offered.
  The warm-spot-only scenario still chose `defer` in both orders.
- A deliberately contradictory starving-miner fixture still elicits mining.
  Native eligibility does not offer that plan. This is evidence of remaining
  model weakness, not safe model reasoning or a real native dispatch.
- All replay transports are in-memory mocks: zero game mutations. Accepted
  fixture responses prove no extraction, hauling, eating, rescue, sale or survival.

Earlier prompt iterations varied between action and waiting. The final replay
is reported above without substituting a more favorable earlier result. These
changes repair lost facts and repeated decision gates; they do not establish
general decision quality. The newly authorized game is the next live check.
Candidate 0.0.8 remains unreleased; stable branches are unchanged.
