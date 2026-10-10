# Documentation index — 0.0.8 candidate

The working branch is `feature/0.0.8`, targeting `developing` through the candidate pull request.
Tag `v0.0.7` records the 6 October release; this working branch contains later
corrections. A dated test result describes its tested
revision and scenario; it does not establish the current build's runtime result.

## Current contracts

- [Game folder discovery, custom installations and repeatable GUI setup](audits/gui-installation-paths-2026-10-10.md)
- [Animal shelters, compatible feed reserves and husbandry decisions](audits/animal-husbandry-contract-2026-10-10.md)
- [Instant construction markers and legacy-frame migration](API_INSTANT_CONSTRUCTION.md)
- [Repository architecture and ownership](../ARCHITECTURE.md)
- [Modular decisions, API boundaries, memory and model budgets](MODULE_ARCHITECTURE_0.0.7.md)
- [Laya model interface, training and evaluation limits](LAYA_ARCHITECTURE.md)
- [Production](modules/production.md), [food and animals](modules/sustenance.md),
  [care and environmental hazards](modules/resilience.md), [people and policies](modules/society.md)
- [Progression and endings](modules/progression.md), [specialists and DLC](modules/specialists.md),
  [native abilities, interactions and targeting](modules/affordances.md), [combat](modules/combat.md)
- [Crops, implants, equipment and training](modules/capabilities.md)
- [Selected hunting groups and animal training](modules/wildlife.md)
- [Exact mining veins, workers and mineral hauling](modules/mining.md)
- [Inspiration opportunities and exact workers](audits/professional-inspirations-native-contract-2026-10-05.md)
- [Explicit finishing jobs and observed completion](audits/finish-downed-native-contract-2026-10-05.md)
- [Trade, raid and rescue expeditions](modules/expeditions.md)
- [Complete quest terms, rewards and fresh acceptance](modules/quests.md)
- [All installed quests and prompt audit, 2026-10-07](audits/quest-prompts-native-contract-2026-10-07.md)
- [Construction recovery and ship identity](audits/architecture-recovery-contract-audit-2026-10-02.md)
- [Comprehensive inventory](COMPREHENSIVE_AUDIT_0.0.7.md): distinguishes current
  executors, observations and gaps; consult newer dated audits when they close a finding.
- [Contributing and offline checks](../CONTRIBUTING.md), [Windows release process](RELEASING.md)

## Evidence and history

- [Postmortem source repairs: food labor, animals, corpses, mining and quest reads, 2026-10-10](audits/postmortem-source-repairs-2026-10-10.md)

- [Dayouinum thermal rescue, truthful care evidence and shutdown](audits/dayouinum-thermal-care-2026-10-07.md)
- [Food commitments and starvation selection after Lenrobum](audits/lenrobum-food-commitment-2026-10-07.md)
- [0.0.8 recovery changes and remaining live gates](RELEASE_READINESS_0.0.8.md)
- [Final quest-review colony outcome and root causes](audits/roinor-recovery-2026-10-07.md)

- [Colony screenshots, layout, losses, raids, economy and comparison](COLONY_VERIFICATION.md)
- [0.0.7 release preparation and remaining gates](RELEASE_READINESS_0.0.7.md)
- [Clinical context and truthful waiting, 2026-10-06](audits/clinical-context-wait-2026-10-06.md)
- [Production deferral and kitchen boundary, 2026-10-06](audits/food-deferral-kitchen-2026-10-06.md)
- [Allied Berserk and exact post-combat care, 2026-10-06](audits/allied-berserk-care-contract-2026-10-06.md)
- [Dated colony durations and cause evidence](playtests/Colony-lifetimes-2026-10-06.md)
- [Theentbum final defeat and confirmed causes, 2026-10-06](playtests/Theentbum-2026-10-06.md)
- [Resolved growth modal and forced pause, 2026-10-06](audits/growth-dialog-pause-2026-10-06.md)
- [Starvation care prerequisites, scoped yielding and nutrition context, 2026-10-06](audits/starvation-care-yield-2026-10-06.md)

- [Worker-choice stall, food context and utility repairs, 2026-10-05](audits/worker-food-utility-recovery-2026-10-05.md)
- [Named allied murderous-rage protection](audits/murderous-rage-protection-2026-10-05.md)
- [Ending API reentrant list failure](audits/endings-reentrant-read-boundary-2026-10-05.md)

- [Requader founder losses and postmortem, 2026-10-03](audits/requader-postmortem-2026-10-03.md):
  user-ended outcome, medical/development/combat failures and offline repair limits.
- [Startup loop incident and sequence verification, 2026-10-03](audits/startup-loop-replay-2026-10-03.md):
  actual first-run failure, corrected contracts, model replay and launch gates.

- [API and repeated-decision audit, 2026-10-02](audits/api-loop-audit-2026-10-02.md):
  agent review decisions, concrete failure sequences and repository corrections.

- `audits/`: dated source/API/definition audits. Check revision and limitations
  before relying on a test count or a closure statement.
- `playtests/` and [colony journal](../PLAYTEST_REPORT.md): observed game results,
  including losses and technical replays.
- [Release notes](../RELEASE_NOTES.md): unpublished working changes are separate
  from the tagged 0.0.7 build and earlier versions.
- [0.0.6 readiness](RELEASE_READINESS_0.0.6.md) and other versioned reports stay
  as historical evidence. Their open issues may be superseded by later audits;
  they are not the current development checklist.

Game definitions and engine guards decide what is currently possible. Catalog
coverage, offline fixtures and compilation do not prove good strategic choices,
native work completion or a guaranteed ending.
