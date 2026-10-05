# Named allied murderous rage protection

Evidence: the 5 October hourly records report an allied murderous rage at tick
2135362 targeting a nonviolent colonist, then death by Bruise at 2149108,
concurrent with a raid. This does not prove
any alternative order would guarantee survival. Existing combat only exposed
IsInMentalState; MurderousRage does not override base ForceHostileTo=false.
The allied aggressor therefore stays separate from enemy attack targets.

Primary installed 1.6 Assembly-CSharp.dll inspection: Verse.AI.MentalState_MurderousRage
has public target and retargets every 120 ticks if unreachable; RimWorld.JobGiver_MurderousRage
creates AttackMelee with canBashDoors and killIncappedTarget true. Walls and
victim downing are not reliable protection. FloatMenuOptionProvider_Arrest
uses CanBeArrestedBy, actual prisoner bed, normal GetAcceptArrestChance;
JobDriver_TakeToBed runs CheckAcceptArrest during the ordinary job. No preview
or helper invokes CheckAcceptArrest/RecoverFromState or forces success.

Additive combat fields mental_state_def/label/target_id/target_position preserve
actual victim identity into bridge. Observer slows to 1x on named active rage,
logs active_murderous_rage and mental_context; director-not-ready still pauses.

GET /api/v1/mental-safety/context map_id returns available/map_id/options/orders/threats/blocker.
Only named live same-map allied rage is considered. Options are ordinary Goto,
Arrest or Rescue, exact actor/target/bed/cell, with native mentalstate instance
GUID. No shooting/kill ally option. Current care/food/force-complete jobs are
protected. Paths screen observed raid pawns/turrets, fire and fog; rescue uses
shared native rescue route gate and screens both approach and carry route.
Evacuation is relative distance improvement, not a guarantee against pursuit.
Arrest approach deliberately admits aggressor exposure and reports resistance.
Rescue is only for downed victim and undrafted worker with real native bed.

POST /order takes map_id/key/session; re-evaluates actual eligibility before
optional draft and normal assignment, then checks actual exact current job.
Rejected assignment removes only its queued job and restores only own draft.
Conditional cancellation takes cancel=true and original option; verifies same
native state/victim/player actor/map and actual job/cell/target/bed before ending
that job. It cannot cancel a fresh care or defense job. No colony-wide orders.

Python lease uses actual readback, bounded pair/session retries and highwater
distance progress. ACK lost recovers actual job; incomplete observation retains
pending intent. Observe has stable session/target/option dwell including no-option
case, new target/options bypass. Ended/changed rage releases lease immediately
and retains ordinary job. Persistent unknown readback yields peaceful actor
protection after finite window while retaining semantic pending intent, so urgent
raid/care can take over without blind reassignment or cancellation.

Parent integration: register mental_safety module and install payload; invoke
reconcile after snapshot/map_state, union active_ids only into peaceful job
protection. Offer mental_safety_response concurrently with raid and urgent care
before ordinary combat dispatch; do not globally continue/block either domain.
Module result blocks_development=false is not an assertion victim is safe.

Offline behavioral doubles prove Python envelopes/reconciliation/choices only.
C# compilation verifies installed API compatibility; live successful arrest,
evacuation/rescue and survival are separate evidence, not claimed here.
