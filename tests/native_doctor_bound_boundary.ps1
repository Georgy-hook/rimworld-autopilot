$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskBound=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorBoundHelper.cs')
$taskFrom=$taskBound.IndexOf('    public static class CombatDoctorBoundMath')
$taskMath=$taskBound.Substring($taskFrom,$taskBound.IndexOf('    public static partial class CombatControlHelper')-$taskFrom)
$taskReserve=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorReserveHelper.cs')
$taskFrom=$taskReserve.IndexOf('    public static class CombatDoctorReserveMath')
$taskMath+=$taskReserve.Substring($taskFrom,$taskReserve.IndexOf('    public static partial class CombatControlHelper')-$taskFrom)
$taskFrom=$taskReserve.IndexOf('        private static float DoctorProjectedExposure(')
$taskForecast=$taskReserve.Substring($taskFrom,$taskReserve.IndexOf('        // Capability',$taskFrom)-$taskFrom)
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatControlHelper.cs')
$taskFrom=$taskControl.IndexOf('        private static bool SaferRangedRoute(Pawn pawn,CombatPathBudgetHelper.Observation')
$taskRoute=$taskControl.Substring($taskFrom,$taskControl.IndexOf('        private static bool ReviewRangedWithdrawal(',$taskFrom)-$taskFrom)
$taskFrom=$taskBound.IndexOf('        private static float DoctorBoundRemainingTicks(')
$taskRemaining=$taskBound.Substring($taskFrom,$taskBound.IndexOf('        private static bool KeepDoctorBoundRoute(',$taskFrom)-$taskFrom)
$taskTransit=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorTransitHelper.cs')
$taskFrom=$taskTransit.IndexOf('    public static class CombatDoctorTransitMath')
$taskMath+=$taskTransit.Substring($taskFrom,$taskTransit.IndexOf('    public static partial class CombatControlHelper')-$taskFrom)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
MATH
public struct IntVec3 {public int x,z;public IntVec3(int a,int b=0){x=a;z=b;}public static bool operator==(IntVec3 a,IntVec3 b)=>a.x==b.x&&a.z==b.z;public static bool operator!=(IntVec3 a,IntVec3 b)=>!(a==b);public override bool Equals(object o)=>o is IntVec3 && this==(IntVec3)o;public override int GetHashCode()=>x*31+z;}
public sealed class Stance_Warmup {}
public sealed class Stances {public object curStance;}
public sealed class Pather {public bool Moving;public IntVec3 nextCell;public float nextCellCostLeft=10;}
public sealed class Pawn {public int thingIDNumber=7;public IntVec3 Position;public Stances stances=new Stances();public Pather pather=new Pather();}
public sealed class Plan {}
public static class CombatPathBudgetHelper {public static void Checkpoint(string s=null){}public sealed class Observation {public bool Found=true;public float TotalCost=500;public List<IntVec3> NodesReversed=new List<IntVec3>{new IntVec3(2),new IntVec3(1),new IntVec3(0)};}}
public static class CombatInterceptHelper {public static float MovementLockTicks(Pawn p)=>0;public static float PlannedJogStepTicks(Pawn p,IntVec3 a,IntVec3 b)=>10;}
public static class CombatInterceptMath {public static bool RangedRouteImproves(float a,float b,float c,float d,float e)=>false;}
public static class CombatCoverTurnMath {public static bool ProtectedArrivalImproves(float a,float b,float c,float d,float e,float f)=>false;}
public static class CombatRangePostMath {public static bool ContinuingNotWorse(float a,float b,float c,float d,float e,float f,float g)=>false;}
public static class ActualDoctorBoundRegression {
 static int n;static bool Clinical;static Func<IntVec3,float,float> Exposure=(c,t)=>0;static List<float> Samples=new List<float>();
 static Dictionary<int,Plan> Plans=new Dictionary<int,Plan>();static bool OwnedRangePostInTransit(Plan p)=>false;static bool CohortInTransit(Plan p)=>false;
 static bool ClinicalRangedTransit(Pawn p)=>Clinical;static float TeamCycle(Pawn p)=>30;
 static IEnumerable<IntVec3> RemainingRangedCells(Pawn p,CombatPathBudgetHelper.Observation o)=>o.NodesReversed.AsEnumerable().Reverse().SkipWhile(c=>c==p.Position);
 static float IncomingRangedExposure(Pawn p,IntVec3 c,float time=0){Samples.Add(time);return Exposure(c,time);}
FORECAST
REMAINING
ROUTE
 static void Check(bool b,string m){n++;if(!b)throw new Exception(m);}
 public static int Run(){
  Check(CombatDoctorBoundMath.Window(45,195,200,60)==450,"Accepted purpose lost its original forecast horizon during continuation");
  Check(CombatDoctorBoundMath.Window(45,645,200,60)==260,"Remaining travel and firing cycle were omitted after initial horizon");
  Check(float.IsPositiveInfinity(CombatDoctorBoundMath.Window(45,900,100,60)),"A rolling purpose can keep extending beyond finite age900");
  Check(float.IsPositiveInfinity(CombatDoctorBoundMath.Window(45,44,1,1)),"Time reversal retained a bound");
  foreach(float bad in new[]{float.NaN,float.PositiveInfinity,-1f})Check(float.IsPositiveInfinity(CombatDoctorBoundMath.Window(0,1,bad,1)),"Unknown travel acquired a safe bound");
  Check(CombatDoctorBoundMath.Keep(true,false,false,false,150),"Valid exact purpose was not retained");
  foreach(var flags in new[]{new[]{false,false,false,false},new[]{true,true,false,false},new[]{true,false,true,false},new[]{true,false,false,true}})Check(!CombatDoctorBoundMath.Keep(flags[0],flags[1],flags[2],flags[3],150),"Foreign/clinical/immediate or nonexact job was retained");
  Check(!CombatDoctorBoundMath.Keep(true,false,false,false,901),"Purpose did not expire");
  var p=new Pawn();var path=new CombatPathBudgetHelper.Observation();float score;
  Check(DoctorBoundRemainingTicks(p,path)==20,"Original total search cost replaced remaining native steps");
  p.pather.Moving=true;p.pather.nextCell=new IntVec3(1);p.pather.nextCellCostLeft=3;
  Check(DoctorBoundRemainingTicks(p,path)==13,"Partly completed native current step was charged again");p.pather.Moving=false;
  Check(!SaferRangedRoute(p,path,true,out score,null,450,true,false),"An ordinary equal route acquired unrestricted retention");
  Check(SaferRangedRoute(p,path,true,out score,null,450,true,true),"Z: safe exact continuing medical route cancelled because no further improvement");
  Check(!SaferRangedRoute(p,path,false,out score,null,450,true,true),"A new equal route bypassed ordinary admission");
  Check(!SaferRangedRoute(p,path,true,out score,null,450,false,true),"A caller without the full unexposed requirement acquired retention");
  Exposure=(c,t)=>c.x==1?.2f:0;Check(!SaferRangedRoute(p,path,true,out score,null,450,true,true),"Exposed intermediate cell retained");
  Exposure=(c,t)=>c.x==2&&t>=450?.2f:0;Check(!SaferRangedRoute(p,path,true,out score,null,450,true,true),"Late terminal threat omitted");
  Exposure=(c,t)=>float.NaN;Check(!SaferRangedRoute(p,path,true,out score,null,450,true,true),"Unknown geometry acquired medical retention");
  Exposure=(c,t)=>0;Clinical=true;Check(SaferRangedRoute(p,path,true,out score,null,450,true,true),"Exact safe route failed actual clinical prefix/timing predicates");
  Exposure=(c,t)=>c.x==1?.3f:0;Check(!SaferRangedRoute(p,path,true,out score,null,450,true,true),"Clinical exposed prefix bypassed");
  Clinical=false;path.Found=false;Check(!SaferRangedRoute(p,path,true,out score,null,450,true,true),"Missing native path acquired safety");
  Samples.Clear();Exposure=(c,t)=>t==80?.5f:0;Check(DoctorProjectedExposure(p,p.Position,80)==.5f&&Samples.Contains(80),"Forecast less than120 ticks never checked its endpoint");
  Samples.Clear();Exposure=(c,t)=>t==150?.5f:0;Check(DoctorProjectedExposure(p,p.Position,150)==.5f&&Samples.Contains(120)&&Samples.Contains(150),"Nonmultiple terminal forecast gap");
  Samples.Clear();Check(float.IsPositiveInfinity(DoctorProjectedExposure(p,p.Position,float.NaN))&&Samples.Count==0,"Invalid horizon ran native geometry");
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath).Replace('FORECAST',$taskForecast).Replace('REMAINING',$taskRemaining).Replace('ROUTE',$taskRoute)) -Language CSharp
[ActualDoctorBoundRegression]::Run()
if($taskBound -match 'FindPathNow|ReleaseToPool|\.Reset\(|Rand\.') {throw 'Purpose retention mutated engine-owned path or RNG'}
if($taskBound -notmatch 'p.Map==b.Map' -or $taskBound -notmatch 'plan.OwnedJob==b.Move.Value' -or $taskBound -notmatch 'AbductionThreat') {throw 'Bound lost map, exact ownership or abduction release'}
if($taskControl -notmatch 'PruneDoctorBounds\(\)' -or $taskReserve -notmatch 'RememberDoctorBound\(p,move,cell\)') {throw 'Native accepted move/finite pruning not wired'}
