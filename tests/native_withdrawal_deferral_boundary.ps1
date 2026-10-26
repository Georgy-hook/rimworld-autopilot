$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatControlHelper.cs')
$taskFrom=$taskSource.IndexOf('        private static bool ReviewRangedWithdrawal(')
$taskMethod=$taskSource.Substring($taskFrom,$taskSource.IndexOf('        private static Pawn RangedShotAfterMove(',$taskFrom)-$taskFrom)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
public sealed class CombatReviewDeferredException:Exception{}
public sealed class Job {public bool Owned=true;}
public sealed class Stamp {public Job Value;}
public sealed class Queued {public Job job;}
public enum JobCondition {InterruptForced}
public static class JobDefOf {public static object Goto=new object();}
public sealed class Jobs {public List<Queued> jobQueue=new List<Queued>();public int Ends;public void EndCurrentJob(JobCondition c,bool start){Ends++;}}
public sealed class Pather {public object curPath=new object();}
public sealed class Pawn {public Jobs jobs=new Jobs();public Pather pather=new Pather();public Job CurJob=new Job();public object CurJobDef=JobDefOf.Goto;}
public sealed class Plan {public Pawn Pawn=new Pawn();public string Mode="retreat";public Stamp RangedWithdrawal;public int RangedCoverReviewTick,RecoveryUntilTick;public Job OwnedJob,QueuedShot;}
public static class Find {public static Ticks TickManager=new Ticks();}public sealed class Ticks {public int TicksGame=100;}
public static class CombatOrderHelper {public static int Drops;public static bool Owned(Pawn p,Job j)=>j.Owned;public static void DropQueued(Pawn p){Drops++;}}
public static class CombatPathBudgetHelper {public static int Borrows;public static bool Found=true;public sealed class Observation:IDisposable {public bool Found=CombatPathBudgetHelper.Found;public void Dispose(){}}public static Observation Borrowed(object p){Borrows++;return new Observation();}}
public static class CombatInterceptHelper {public static bool MovementCellsSafe(Pawn p,IEnumerable<object> cells)=>true;}
public static class ActualWithdrawalDeferralRegression {
 static bool Defer,Medical=true,Safe=true;static bool PendingOwnedRangedMove(Plan p)=>false;static bool MovingOrBusy(Pawn p)=>true;
 static IEnumerable<object> RemainingRangedCells(Pawn p,object path)=>Array.Empty<object>();
 static bool DoctorBoundInTransit(Plan p)=>Medical;
 static bool KeepDoctorBoundRoute(Plan p,CombatPathBudgetHelper.Observation o){if(Defer)throw new CombatReviewDeferredException();return Safe;}
 static bool SaferRangedRoute(Pawn p,CombatPathBudgetHelper.Observation o,bool c,out float score){score=0;if(Defer)throw new CombatReviewDeferredException();return Safe;}
 static bool TryBreakRangedContact(Plan p,List<Pawn> ts,bool x)=>false;
METHOD
 static Plan Fresh(){var p=new Plan();p.OwnedJob=p.Pawn.CurJob;p.RangedWithdrawal=new Stamp{Value=p.Pawn.CurJob};CombatOrderHelper.Drops=0;CombatPathBudgetHelper.Borrows=0;return p;}
 public static int Run(){
  foreach(bool medical in new[]{true,false}){
   Medical=medical;var p=Fresh();var original=p.Pawn.CurJob;Defer=true;bool threw=false;
   try{ReviewRangedWithdrawal(p,new List<Pawn>());}catch(CombatReviewDeferredException){threw=true;}
   if(!threw||p.RangedCoverReviewTick!=100||p.Pawn.jobs.Ends!=0||CombatOrderHelper.Drops!=0||p.Pawn.CurJob!=original)throw new Exception("Deferred native proof consumed a completed-review cooldown or cancelled route");
   Defer=false;if(!ReviewRangedWithdrawal(p,new List<Pawn>())||p.RangedCoverReviewTick!=160)throw new Exception("Next pulse did not perform and retain completed safe review");
  }
  var foreign=Fresh();foreign.Pawn.jobs.jobQueue.Add(new Queued{job=new Job{Owned=false}});Defer=true;
  if(!ReviewRangedWithdrawal(foreign,new List<Pawn>())||CombatPathBudgetHelper.Borrows!=0||foreign.Pawn.jobs.Ends!=0)throw new Exception("Later foreign queue was touched before proof");
  Defer=false;Safe=false;var unsafePlan=Fresh();if(ReviewRangedWithdrawal(unsafePlan,new List<Pawn>())||unsafePlan.Pawn.jobs.Ends!=1||unsafePlan.RangedWithdrawal!=null)throw new Exception("Actually completed unsafe route was silently retained");
  return 6;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('METHOD',$taskMethod)) -Language CSharp
[ActualWithdrawalDeferralRegression]::Run()
