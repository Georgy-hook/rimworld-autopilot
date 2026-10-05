# Repeated medical rest, 2026-10-05

## Evidence and cause

A bounded live-log tail contained 185 accepted assignments of the same
post-combat rest target over approximately 32 minutes. Some followed Ingest
orders immediately. The disease classifier treated HeartArteryBlockage's
Immunizable component, zero immunity and lethal threshold as evidence of an
active immunity race. Core uses that component to advance chronic severity;
its configured immunity gain while sick is zero. Rest cannot develop immunity
to this condition.

The rest proposal also checked only arrival at the bed, so an accepted order
was proposed again during travel or eating. Both Patient priorities were
already 1. The API accepted and restarted LayDown without validating a current
medical indication.

## Contracts

- Native hediff observations now expose `immunity_can_develop`, using the
  loaded Immunizable properties' `immunityPerDaySick > 0`.
- Colonist and resilience observations expose `should_seek_medical_rest`
  from the game's HealthAIUtility. A numeric immunity value alone does not
  prove an immunity race, including in modded conditions.
- Python honors explicit false and retains a compatibility exclusion for
  HeartArteryBlockage in older recordings. Real infections at immunity zero
  remain eligible for recovery and tending.
- Rest priorities are established once. Travel, eating and ordinary work do
  not reissue the forced bed job after that. Active eating and care jobs are
  protected before setup; new bleeding remains separately actionable.
- The native medical-rest endpoint rejects absent medical indication and
  active Ingest. Assigning the same LayDown target is idempotent. Native
  resilience rest policy choices also require the game's medical indication.
- Other care continues to be polled at its existing fast cadence. No global
  cooldown delays newly urgent patients.

## Verification

1071 Python tests pass, including a sequential accepted-rest → travel → meal →
ordinary work → rest test with no second POST and a newly bleeding patient
still receiving a treatment proposal. Native Release-1.6 builds with zero
errors/warnings. API contract audit: 306 routes, 257 literal calls, no missing
or duplicate routes. These checks do not prove recovery in the live colony.

Runtime source b326db5 and DLL package f2eddbd were installed; all 36 runtime
files and both installed DLL copies matched the payload. The preserved game
resumed around 13:56:23 UTC, following a technical pause at tick1994622 and
287 load-transition ticks. No colony or memory was replaced.

At tick1994909, the native API reported medical rest not indicated and no
developing immunity for the chronic condition. A direct negative bed-rest
check was rejected before mutation; the current DoBill job remained unchanged.
The legacy error envelope uses HTTP500 for this expected refusal. No rest
proposal remained in either Python post-combat care or native resilience.

The first 17 subsequent logged records (13:56:26–13:58:27 UTC) contain zero
rest assignments, with food, refuelling, combat, stand-down and equipment
decisions continuing. The former repeated-rest target was observed doing
production work, later ordinary sleeping; all four current residents remained
alive and upright. This is a two-minute live regression window, not proof of
long-term survival or successful treatment of a new acute infection.
