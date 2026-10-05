# Documentation index — 0.0.7 candidate

The working branch is `fix/0.0.7-cold-start`, targeting `developing` in PR #4.
This source candidate is unreleased. A dated test result describes its tested
revision and scenario; it does not establish the current build's runtime result.

## Current contracts

- [Repository architecture and ownership](../ARCHITECTURE.md)
- [Modular decisions, API boundaries, memory and model budgets](MODULE_ARCHITECTURE_0.0.7.md)
- [Laya model interface, training and evaluation limits](LAYA_ARCHITECTURE.md)
- [Production](modules/production.md), [food and animals](modules/sustenance.md),
  [care and environmental hazards](modules/resilience.md), [people and policies](modules/society.md)
- [Progression and endings](modules/progression.md), [specialists and DLC](modules/specialists.md),
  [native abilities, interactions and targeting](modules/affordances.md), [combat](modules/combat.md)
- [Crops, implants, equipment and training](modules/capabilities.md)
- [Selected hunting groups and animal training](modules/wildlife.md)
- [Inspiration opportunities and exact workers](audits/professional-inspirations-native-contract-2026-10-05.md)
- [Explicit finishing jobs and observed completion](audits/finish-downed-native-contract-2026-10-05.md)
- [Trade, raid and rescue expeditions](modules/expeditions.md)
- [Construction recovery and ship identity](audits/architecture-recovery-contract-audit-2026-10-02.md)
- [Comprehensive inventory](COMPREHENSIVE_AUDIT_0.0.7.md): distinguishes current
  executors, observations and gaps; consult newer dated audits when they close a finding.
- [Contributing and offline checks](../CONTRIBUTING.md), [Windows release process](RELEASING.md)

## Evidence and history

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
- [Release notes](../RELEASE_NOTES.md): 0.0.7 is explicitly unreleased;
  0.0.6 and earlier describe their own builds.
- [0.0.6 readiness](RELEASE_READINESS_0.0.6.md) and other versioned reports stay
  as historical evidence. Their open issues may be superseded by later audits;
  they are not the current development checklist.

Game definitions and engine guards decide what is currently possible. Catalog
coverage, offline fixtures and compilation do not prove good strategic choices,
native work completion or a guaranteed ending.
