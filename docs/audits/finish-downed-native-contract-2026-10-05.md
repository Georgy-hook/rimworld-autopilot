# Explicit downed-hostile finishing job

## Observed fault and installed 1.6 evidence

Parent extracted repeated finish orders in the Goberium run at 10:43:05,
10:43:15 and 10:43:25: Vega #770 approached downed raider #21897 and returned
to Wait_Combat. Vega's combat facts reported can_fight=false. The target later
ceased living; this is not a positive execution replay. The active save was
subsequently observed as Theentbum (Permadeath), seed-matched, tick 378997.

Primary inspection used the installed game's Assembly-CSharp.dll:
`C:/Program Files (x86)/Steam/steamapps/common/RimWorld/RimWorldWin64_Data/Managed/Assembly-CSharp.dll`.
ILSpy tool is `work/inspection-tools/ilspycmd.exe`; this workstation's runtime
is `C:/Users/Georgy/.dotnet`. Decompiled types/methods:

- `RimWorld.FloatMenuUtility.GetMeleeAttackAction`: rejects disabled Violent
  work tag, missing melee verb, unreachable target and other native control,
  faction and ideology restrictions. The accepted delegate creates AttackMelee
  and sets `job.killIncappedTarget = targetPawn.Downed`.
- `RimWorld.FloatMenuOptionProvider_DraftedAttack.GetMeleeAttackAction`: labels
  a downed pawn attack as MeleeAttackToDeath and delegates native eligibility.
- `Verse.AI.JobDriver_AttackMelee.MakeNewToils`: only special starvation duty
  and dormant Anomaly cases automatically set killIncappedTarget.
- `Verse.AI.Toils_Combat.FollowAndMeleeAttack`: for an ordinary downed target,
  false killIncappedTarget calls ReadyForNextToil before the melee hit action.
- `Verse.AI.Pawn_JobTracker.TryTakeOrderedJob`: immediately returns true for
  an existing same job.
- `Verse.AI.Job.JobIsSameAs`: compares definition, verb, bill and targets;
  killIncappedTarget is not compared. A second same-target job cannot repair
  the old false flag by replacing its request alone.

## Narrow API change

`POST /api/v1/pawn/job` accepts optional `kill_incapped_target` bool, default
false. True requires exact AttackMelee, explicit `map_id`, a spawned living
player-controlled actor (drafted or explicitly requesting atomic drafting), no mental state/downing/protected care or
Ingest job, and a visible living downed hostile pawn on that exact map that
is not a colony prisoner. Native FloatMenuUtility eligibility is evaluated
without invoking its order-producing delegate. Generic AttackMelee/AttackStatic
and definitions using derived attack drivers reject disabled Violent work.

All eligibility checks precede job assignment and any flag mutation. For an
existing same-target AttackMelee, true intent upgrades only its false flag;
an already true flag succeeds without restarting the job. A new explicitly
validated finishing job receives true before TryTakeOrderedJob. Ordinary
attack requests retain their native false default. Only explicit validated
finishing requests may ask this endpoint to draft, as described below.

Rejections use the existing `ApiResult.Fail` response envelope; the Python
bridge raises a controlled RimApiError on success=false. This does not prove
combat success and must not be reported as applied. Native owns draft rollback;
Python verifies the actual finishing job and tracks pending results.

`GET /api/v1/combat/state` exposes nullable
`current_job_kill_incapped_target` from the actual current native job. Accepted
assignment is not death confirmation: parent must verify current job, exact
target and true flag, then observe completion separately.

## Verification scope

No game orders were issued during this inspection. No text-matching tests
are presented as behavioral proof. Source inspection establishes the native
branch and flag mismatch; a Release-1.6 compile checks API compatibility.
Parent's Python request/readback regressions and a genuinely eligible live
or restored positive scenario are separate verification gates. Current dead
target cannot be used to demonstrate a successful finishing order.

## ACK, progress and atomic drafting correction

Optional `request_draft_for_finishing` defaults false and requires explicit
`kill_incapped_target`. Native validates the controlled player colonist,
visible downed hostile, protected care/food activity, melee verb and reach
before drafting. Installed FloatMenuUtility's `ignoreControlled: true`
skips draft/control checks only; explicit actor gates cover control. No
order delegate is invoked. Rejected job acceptance restores only the draft
change made by this request. Existing drafted matching attacks upgrade the
flag without restarting their job.

Conditional `cancel_finishing_target_id` requires pawn/map and cancels only
an actual same-target AttackMelee with true finishing flag. It cannot replace
a fresh care job. Python `reconcile(client, snapshot, map_state, protected)`
keeps its lease until actual readback proves the job ended. Unknown cancel
readback retains the lease and suppresses retries for 10 seconds and 60 ticks.
Unknown assignment ACK is reconciled immediately; failed readback retains
pending intent until a complete next combat snapshot. Alternatives are
blocked while that lease exists. Progress uses strictly improving distance
and target health highwater marks; A/B movement cannot reset the window.
An existing attack remains tracked below the new-order health threshold.

Twelve offline Python behavioral tests pass, including lost ACK, unknown GET,
JSON persistence, oscillation, conditional cancellation/readback, existing
low-health attack retention and refusal without Python draft mutation.
Fake native refusal tests verify request handling, not real native behavior.
C# compilation and eligible positive live execution remain parent gates.
