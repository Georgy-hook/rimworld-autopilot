$ErrorActionPreference='Stop'
$taskPath=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatControlLeaseHelper.cs'
$taskSource=Get-Content -Raw -LiteralPath $taskPath
$taskStubs=@'
using System;using System.Linq;using System.Collections.Generic;using RIMAPI.Models;using RimWorld;using Verse;
namespace Verse {
 public class JobDef{}public struct IntVec3 {public int v;public static bool operator ==(IntVec3 a,IntVec3 b)=>a.v==b.v;public static bool operator !=(IntVec3 a,IntVec3 b)=>a.v!=b.v;public override bool Equals(object o)=>o is IntVec3 x&&x==this;public override int GetHashCode()=>v;}
 public class Map{}public class Job {public bool playerForced;public JobDef def;public Target targetA=new Target();}
 public class Target{public Pawn Thing;} public class Q{public Job job;}
 public class Jobs{public List<Q> jobQueue=new List<Q>();}
 public class Pawn{public int thingIDNumber;public bool Eligible=true,Hostile=true;public Map Map;public Job CurJob;public JobDef CurJobDef=>CurJob?.def;public Jobs jobs=new Jobs();public IntVec3 Position;}
 public static class Find{public static Clock TickManager=new Clock();}public class Clock{public int TicksGame=100;}
}
namespace RimWorld {public static class JobDefOf{public static Verse.JobDef AttackStatic=new Verse.JobDef(),Wait_Combat=new Verse.JobDef(),Wait_MaintainPosture=new Verse.JobDef(),Goto=new Verse.JobDef();}}
namespace RIMAPI.Models{public class CombatTacticRequestDto{public string Tactic;public int? TargetPawnId;}}
namespace RIMAPI.Helpers {
 public static class CombatOrderHelper{public static HashSet<Verse.Job> OwnedJobs=new HashSet<Verse.Job>();public static bool Owned(Verse.Pawn p,Verse.Job j)=>j!=null&&OwnedJobs.Contains(j);}
 public static partial class CombatControlHelper {
  class Plan {public Verse.Pawn Pawn,Target;public string Tactic;public int UntilTick=1200;public DateTime UntilUtc=DateTime.UtcNow.AddMinutes(1);public Verse.Job OwnedJob,QueuedShot=null;public Verse.IntVec3 ProgressCell=default(Verse.IntVec3);}
  class Move {public Verse.Job Key=null;}
  static Dictionary<int,Plan> Plans=new Dictionary<int,Plan>();static Dictionary<Verse.Pawn,Move> SelectedMoves=new Dictionary<Verse.Pawn,Move>();
  static HashSet<string> RangedPlans=new HashSet<string>{"hold_cover","stationary_fire"};
  static bool Eligible(Verse.Pawn p)=>p.Eligible;static bool Threat(Verse.Pawn p)=>p.Hostile;
  static bool Valid(Plan p)=>Eligible(p.Pawn)&&Verse.Find.TickManager.TicksGame<=p.UntilTick&&DateTime.UtcNow<=p.UntilUtc;
  static int assertions;static void Check(bool x,string why){assertions++;if(!x)throw new Exception(why);}
  public static int Run(){
   var map=new Verse.Map();Verse.Pawn p=null;Plan plan=null;RIMAPI.Models.CombatTacticRequestDto request=null;
   Action reset=()=>{Plans.Clear();SelectedMoves.Clear();CombatOrderHelper.OwnedJobs.Clear();p=new Verse.Pawn{thingIDNumber=1,Map=map};var enemy=new Verse.Pawn{thingIDNumber=2};var job=new Verse.Job{def=RimWorld.JobDefOf.AttackStatic,playerForced=true};job.targetA.Thing=enemy;p.CurJob=job;CombatOrderHelper.OwnedJobs.Add(job);plan=new Plan{Pawn=p,Target=enemy,Tactic="hold_cover",OwnedJob=job};Plans[1]=plan;request=new RIMAPI.Models.CombatTacticRequestDto{Tactic="hold_cover",TargetPawnId=2};};
   reset();var before=p.CurJob;Check(RetainControlLeases(map,new List<int>{1,1},request).SequenceEqual(new[]{1}),"Exact fresh role not renewed or duplicate IDs expanded");Check(plan.UntilTick==1300&&p.CurJob==before&&p.jobs.jobQueue.Count==0,"Renewal created/replaced order or changed duration");
   reset();plan.UntilTick=99;Check(RetainControlLeases(map,new List<int>{1},request).Count==0&&plan.UntilTick==99,"Expired native lease revived");
   reset();plan.UntilUtc=DateTime.UtcNow.AddSeconds(-1);Check(RetainControlLeases(map,new List<int>{1},request).Count==0,"Expired wall-time lease revived");
   reset();Check(RetainControlLeases(new Verse.Map(),new List<int>{1},request).Count==0,"Other-map actor retained");
   reset();request.Tactic="stationary_fire";Check(RetainControlLeases(map,new List<int>{1},request).Count==0,"New tactic silently adopted");
   reset();request.TargetPawnId=3;Check(RetainControlLeases(map,new List<int>{1},request).Count==0,"New target silently adopted");
   reset();plan.Target.Hostile=false;Check(RetainControlLeases(map,new List<int>{1},request).Count==0,"Ordinary attack request retained a stale target");Check(RetainControlLeases(map,new List<int>{1}).Count==1,"Explicit live-role refresh cannot reach post-clear handoff");
   reset();p.Eligible=false;Check(RetainControlLeases(map,new List<int>{1},request).Count==0,"Unavailable/clinical pawn retained");
   reset();p.jobs.jobQueue.Add(new Verse.Q{job=new Verse.Job()});Check(RetainControlLeases(map,new List<int>{1},request).Count==0&&p.jobs.jobQueue.Count==1,"Foreign queue erased or adopted");
   reset();p.CurJob=new Verse.Job{def=RimWorld.JobDefOf.Wait_Combat,playerForced=true};before=p.CurJob;Check(RetainControlLeases(map,new List<int>{1}).Count==0&&p.CurJob==before,"Later manual hold adopted");
   reset();p.CurJob=new Verse.Job{def=RimWorld.JobDefOf.Wait_Combat};Check(RetainControlLeases(map,new List<int>{1},request).Count==1,"Native stationary post-job state lost");
   reset();p.CurJob=new Verse.Job{def=RimWorld.JobDefOf.Wait_Combat};p.Position=new Verse.IntVec3{v=9};Check(RetainControlLeases(map,new List<int>{1},request).Count==0,"Displaced unowned idle adopted");
   reset();Check(RetainControlLeases(map,new List<int>()).Count==0&&RetainControlLeases(null,new List<int>{1}).Count==0&&RetainControlLeases(map,null).Count==0,"Empty/null input expanded selection");
   reset();Check(RetainControlLeases(map,new List<int>{3}).Count==0,"Unselected actor adopted");
   reset();var shot=new Verse.Job();p.jobs.jobQueue.Add(new Verse.Q{job=shot});CombatOrderHelper.OwnedJobs.Add(shot);Check(RetainControlLeases(map,new List<int>{1},request).Count==1&&p.jobs.jobQueue[0].job==shot,"Existing owned follow-up lost");
   return assertions;
  }
 }
}
'@
Add-Type -TypeDefinition ($taskStubs+"`n"+($taskSource -replace '(?m)^using [^;]+;\r?\n','')) -Language CSharp
[RIMAPI.Helpers.CombatControlHelper]::Run()
