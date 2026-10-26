$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorReserveHelper.cs')
$taskStart=$taskSource.IndexOf('        private static bool DoctorReserveStationary(')
$taskStationary=$taskSource.Substring($taskStart,$taskSource.IndexOf('        private static bool DoctorReserveGun(')-$taskStart)
$taskStart=$taskSource.IndexOf('                    .OrderBy(c=>BesideOpaqueCover(')
$taskRank=$taskSource.Substring($taskStart,$taskSource.IndexOf(';',$taskStart)-$taskStart)
$taskCode=@'
using System;using System.Collections.Generic;using System.Linq;
public struct IntVec3 {public int x,z;public IntVec3(int x,int z){this.x=x;this.z=z;}public float DistanceTo(IntVec3 p)=>(float)Math.Sqrt(DistanceToSquared(p));public int DistanceToSquared(IntVec3 p)=>(x-p.x)*(x-p.x)+(z-p.z)*(z-p.z);}
public static class JobDefOf {public static object Wait_Combat=new object();}
public sealed class Job {public bool playerForced;}
public sealed class Pather {public bool Moving;}
public sealed class Jobs {public List<object> jobQueue=new List<object>();}
public sealed class Carry {public object CarriedThing;}
public sealed class Pawn {public object Map=new object();public object CurJobDef=JobDefOf.Wait_Combat;public Job CurJob=new Job();public IntVec3 Position=new IntVec3(119,114);public Pather pather=new Pather();public Jobs jobs=new Jobs();public Carry carryTracker=new Carry();}
public sealed class Plan {public Pawn Pawn=new Pawn();public bool Active=true,Own;}
public static class ActualPhysicianDeadlineRegression {
 static int n;static void Check(bool b,string m){n++;if(!b)throw new Exception(m);}
 static bool OwnStationaryGun(Plan p)=>p.Own;static bool Valid(Plan p)=>p.Active;
 static bool WallEdge;static bool BesideOpaqueCover(object map,IntVec3 c)=>WallEdge&&c.x==108;
STATIONARY
 static IEnumerable<IntVec3> Rank(IEnumerable<IntVec3> cells,Pawn p,List<Tuple<IntVec3,float>> rangeBounds)=>cells RANK;
 public static int Run(){
  var g=new Plan();Check(DoctorReserveStationary(g),"The selected unforced native Wait_Combat after tick15 prevented every fresh early physician review");
  g.Pawn.CurJob.playerForced=true;Check(!DoctorReserveStationary(g),"A manual forced Wait_Combat was adopted");g.Pawn.CurJob.playerForced=false;
  g.Pawn.pather.Moving=true;Check(!DoctorReserveStationary(g),"A moving gun was counted stationary");g.Pawn.pather.Moving=false;
  g.Pawn.jobs.jobQueue.Add(new object());Check(!DoctorReserveStationary(g),"A later queue was ignored");g.Pawn.jobs.jobQueue.Clear();
  g.Pawn.carryTracker.CarriedThing=new Pawn();Check(!DoctorReserveStationary(g),"Carrying was counted available");g.Pawn.carryTracker.CarriedThing=null;
  g.Active=false;Check(!DoctorReserveStationary(g),"An expired/unselected plan was adopted");g.Active=true;
  g.Pawn.CurJobDef=new object();Check(!DoctorReserveStationary(g),"A foreign native work job was adopted");
  var a=new IntVec3(108,114);var b=new IntVec3(101,114);
  var bounds=new List<Tuple<IntVec3,float>>{Tuple.Create(new IntVec3(146,114),23f),Tuple.Create(new IntVec3(120,99),23f),Tuple.Create(new IntVec3(120,135),23f)};
  var first=Rank(new[]{a,b},new Pawn(),bounds).First();Check(first.x==101,"Paging near the rear midpoint consumed the warning window before a proposal outside the observed loaded range");
  WallEdge=true;first=Rank(new[]{a,b},new Pawn(),bounds).First();Check(first.x==108,"An existing nearer opaque edge was never proposed before exposed open ground");
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('STATIONARY',$taskStationary).Replace('RANK',$taskRank)) -Language CSharp
[ActualPhysicianDeadlineRegression]::Run()
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatControlHelper.cs')
$taskTick=$taskControl.Substring($taskControl.IndexOf('        private static void TickBudgeted()'))
if($taskTick.IndexOf('ReviewFireDoctorGuard(true);') -gt $taskTick.IndexOf('ReviewCoordinatedFire();') -or $taskTick.IndexOf('ReviewFireDoctorGuard(true);') -lt 0){throw 'Physician exit is still behind optional coordination'}
if($taskControl -notmatch 'medicalDeadline &= NativeDoctor\(pawn\) && IsReservedDoctor\(pawn\);'){throw 'Any caller can skip generic peer waiting without the reserved medical role'}
if($taskControl -notmatch 'if\(!medicalDeadline && MeleeCohort' -or $taskControl -notmatch 'CombatInterceptMath.UsefulEscape\(before,after,cycle,actualCover,path.TotalCost\+ownLock\)'){throw 'Deadline priority bypassed the measured escape proof'}
$taskGuard=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatFireDoctorGuardHelper.cs')
if($taskGuard -notmatch 'if\(physicianOnly\)GuardReviews.Remove\(p\);'){throw 'A deferred medical deadline waits its ordinary completed-review delay'}
if($taskSource -notmatch 'stationary<2' -or $taskSource -notmatch 'SaferRangedRoute\(p,route,false,out _,null,600f,true\)'){throw 'Native idle admission removed stationary-gun or full unexposed route gates'}
