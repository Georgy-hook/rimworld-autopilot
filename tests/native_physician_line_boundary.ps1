$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatPhysicianLineHelper.cs')
$taskFrom=$taskSource.IndexOf('    public static class CombatPhysicianLineMath')
$taskMath=$taskSource.Substring($taskFrom,$taskSource.IndexOf('    public static partial class CombatControlHelper')-$taskFrom)
$taskFrom=$taskSource.IndexOf('        private static bool CoveredPhysicianRejoin(')
$taskMethods=$taskSource.Substring($taskFrom,$taskSource.IndexOf('        private static bool CohortAnchorHasShot(',$taskFrom)-$taskFrom)
$taskFrom=$taskSource.IndexOf('        private static bool CohortCoverWindow(')
$taskCover=$taskSource.Substring($taskFrom,$taskSource.IndexOf('        private static bool PhysicianAtBlindPost(',$taskFrom)-$taskFrom)
$taskBurst=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatCoverTurnHelper.cs')
$taskFrom=$taskBurst.IndexOf('    public static class CombatCoverTurnMath')
$taskMath+=$taskBurst.Substring($taskFrom,$taskBurst.IndexOf('    // Native route proofs')-$taskFrom)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
MATH
public struct IntVec3 {public int x;public IntVec3(int a){x=a;}public static bool operator==(IntVec3 a,IntVec3 b)=>a.x==b.x;public static bool operator!=(IntVec3 a,IntVec3 b)=>!(a==b);public override bool Equals(object o)=>o is IntVec3 && this==(IntVec3)o;public override int GetHashCode()=>x;}
public sealed class Bleed {public float BleedRateTotal;}
public sealed class Health {public Bleed hediffSet=new Bleed();}
public sealed class Pather {public bool Moving;public IntVec3 nextCell;public float nextCellCostLeft;}
public sealed class Jobs {public List<object> jobQueue=new List<object>();}
public enum VerbState {Idle,Bursting}public sealed class VerbProps {public float warmupTime=.5f;public int burstShotCount=1,ticksBetweenBurstShots;}
public sealed class Verb {public VerbState state;public VerbProps verbProps=new VerbProps();}
public sealed class CompEquippable {public Verb PrimaryVerb=new Verb();}
public sealed class Thing {public CompEquippable comp=new CompEquippable();public T TryGetComp<T>() where T:class=>comp as T;}
public sealed class Equipment {public Thing Primary=new Thing();}
public sealed class Focus {public Pawn Thing;}public sealed class Stance_Warmup {public Focus focusTarg=new Focus();public int ticksLeft;}
public sealed class Stances {public object curStance;}
public static class StatDefOf {public static object AimingDelayFactor=new object();}
public static class JobDefOf {public static object Goto=new object();}
public sealed class Pawn {public int thingIDNumber=1;public bool Doctor=true,Critical,Warning,Safe=true,Eligible=true,Owned=true,Stationary=true,Hit=true,Support=true,Melee,MeleeWindow;public float Exposure=.9f,Contact=10000;public object CurJobDef;public IntVec3 Position;public Health health=new Health();public Jobs jobs=new Jobs();public Pather pather=new Pather();public Equipment equipment=new Equipment();public Stances stances=new Stances();public float GetStatValue(object stat)=>1;}
public sealed class Plan {public Pawn Pawn=new Pawn();}
public static class CombatPathBudgetHelper {public static void Checkpoint(string s){}public sealed class Observation {public bool Found=true;public float TotalCost=999;public System.Collections.ObjectModel.ReadOnlyCollection<IntVec3> NodesReversed=new List<IntVec3>{new IntVec3(2),new IntVec3(1),new IntVec3(0)}.AsReadOnly();}}
public static class CombatInterceptHelper {public static bool MovementSafe(Pawn p,CombatPathBudgetHelper.Observation o)=>p.Safe;public static float MovementLockTicks(Pawn p)=>0;public static float PlannedJogStepTicks(Pawn p,IntVec3 a,IntVec3 b)=>10;}
public static class CombatNativeHelper {public static bool Protected(Pawn p)=>!p.Doctor;}
public static class CareTriageHelper {public static bool QueuedCare(Pawn p)=>false;}
public static class CombatShotEvidenceHelper {public static int LastTick(Pawn p,int id)=>p.Support?10:-1;}
public static class ActualPhysicianLineRegression {
 static int n;static Func<IntVec3,float,float> Exposure=(c,t)=>c.x==0?0:.3f;
 static List<float> Horizons=new List<float>();
 static bool NativeDoctor(Pawn p)=>p.Doctor;static bool CriticalRangedInjury(Pawn p)=>p.Critical;static bool MedicalFunctionWarning(Pawn p)=>p.Warning;static float TeamCycle(Pawn p)=>120;
 static float IncomingRangedExposure(Pawn p,IntVec3 c,float t=0){Horizons.Add(t);return Exposure(c,t);}
 static IEnumerable<IntVec3> RemainingRangedCells(Pawn p,CombatPathBudgetHelper.Observation o)=>o.NodesReversed.AsEnumerable().Reverse().SkipWhile(c=>c==p.Position);
METHODS
 static Dictionary<int,Plan> Plans=new Dictionary<int,Plan>();
 static bool Eligible(Pawn p)=>p.Eligible;static bool TeamImmediateDanger(Pawn p)=>!p.Safe;
 static bool CohortOwned(Pawn p)=>p.Owned;static bool DoctorReserveStationary(Plan p)=>p.Pawn.Stationary;
 static bool MeleeThreat(Pawn p)=>p.Melee;static bool CoverGunWindow(Pawn p,Pawn e,List<Pawn> ts)=>p.MeleeWindow;
 static bool TeamCoverReady(Pawn p,Pawn e,List<Pawn> ts)=>p.Support;static float EarliestContact(Pawn p,List<Pawn> ts)=>p.Contact;
 static float Speed(Pawn p)=>4;static float IncomingRangedExposure(Pawn p,IntVec3 c)=>p.Exposure;
COVER
 static void Check(bool b,string m){n++;if(!b)throw new Exception(m);}
 public static int Run(){
  Check(CombatPhysicianLineMath.Cover(.9f,true),"Actual healthy same-enemy support was rejected solely by the stricter preparation ceiling");
  Check(!CombatPhysicianLineMath.Cover(.9f,false),"An exposed unproven preparation became cover");
  Check(!CombatPhysicianLineMath.Cover(1.41f,true),"Existing support envelope1.4 bypassed");
  Check(CombatPhysicianLineMath.Terminal(1.2f,false)&&!CombatPhysicianLineMath.Terminal(1.2f,true),"Physician and firing-line exposure purposes conflated");
  Check(CombatPhysicianLineMath.Rejoin(.5f,.5f,180,120),"Finite covered physician rejoin refused");
  foreach(float bad in new[]{float.NaN,float.PositiveInfinity,-1f}){
   Check(!CombatPhysicianLineMath.Cover(bad,true),"Unknown exposure became cover");
   Check(!CombatPhysicianLineMath.Rejoin(bad,.1f,180,120),"Unknown route became medical rejoin");
  }
  Check(!CombatPhysicianLineMath.Rejoin(.61f,.1f,180,120),"Exposed route exceeded finite physician ceiling");
  Check(!CombatPhysicianLineMath.Rejoin(.1f,.61f,180,120),"Future terminal risk omitted");
  Check(!CombatPhysicianLineMath.Rejoin(.1f,.1f,241,120),"Long new sortie replaced short rejoin");
  Check(!CombatPhysicianLineMath.Rejoin(.1f,.1f,180,500),"Unknown beyond600tick forecast acquired safety");
  var p=new Pawn{Exposure=0};var path=new CombatPathBudgetHelper.Observation();
  Check(CoveredPhysicianRejoin(p,path),"Actual finite route rejected solely because old safe origin was safer than a useful firing post");
  p.Doctor=false;Check(!CoveredPhysicianRejoin(p,path),"Nonmedical actor received physician exception");p.Doctor=true;
  p.Critical=true;Check(!CoveredPhysicianRejoin(p,path),"Critical physician exposed");p.Critical=false;
  p.health.hediffSet.BleedRateTotal=.1f;Check(!CoveredPhysicianRejoin(p,path),"Bleeding physician exposed");p.health.hediffSet.BleedRateTotal=0;
  p.jobs.jobQueue.Add(new object());Check(!CoveredPhysicianRejoin(p,path),"Later job was erased");p.jobs.jobQueue.Clear();
  p.Safe=false;Check(!CoveredPhysicianRejoin(p,path),"Native fire/gas route safety bypassed");p.Safe=true;
  Exposure=(c,t)=>c.x==1?.7f:0;Check(!CoveredPhysicianRejoin(p,path),"Unsafe intermediate step omitted");
  Exposure=(c,t)=>c.x==2&&t>100?float.PositiveInfinity:0;Check(!CoveredPhysicianRejoin(p,path),"Unknown post-arrival geometry accepted");
  Exposure=(c,t)=>t>=600?2f:0;Check(CoveredPhysicianRejoin(p,path),"A future state after the finite measured firing cycle rejected the short action");
  Exposure=(c,t)=>t>=120?.7f:0;Check(!CoveredPhysicianRejoin(p,path),"Finite actual firing window was dropped along with long prefilter");
  Exposure=(c,t)=>0;Horizons.Clear();p.pather.Moving=true;p.pather.nextCell=new IntVec3(1);p.pather.nextCellCostLeft=3;
  Check(RejoinRemainingSafe(new Plan{Pawn=p},path)&&Horizons.Contains(3)&&Horizons.Contains(133),"Remaining path ignored native partly completed step or used original TotalCost");
  p.Warning=true;Check(!RejoinRemainingSafe(new Plan{Pawn=p},path),"Clinical deterioration failed to release rejoin");
  p=new Pawn();Plans[p.thingIDNumber]=new Plan{Pawn=p};var enemy=new Pawn{thingIDNumber=2};var threats=new List<Pawn>{enemy};
  Check(CohortCoverWindow(p,enemy,threats),"Actual ranged cover path still has the old blanket exposure veto");
  p.Support=false;Check(!CohortCoverWindow(p,enemy,threats),"Exposed gun without real same-enemy support was admitted");p.Support=true;
  p.Owned=false;Check(!CohortCoverWindow(p,enemy,threats),"Manual gun adopted");p.Owned=true;
  p.Hit=false;Check(!CohortCoverWindow(p,enemy,threats),"Current native shot/FF lane omitted");p.Hit=true;
  p.Contact=30;Check(!CohortCoverWindow(p,enemy,threats),"Contact deadline omitted");p.Contact=10000;
  p.Critical=true;Check(!CohortCoverWindow(p,enemy,threats),"Wounded gun committed as cover");p.Critical=false;
  p.jobs.jobQueue.Add(new object());Check(!CohortCoverWindow(p,enemy,threats),"Foreign queue touched");p.jobs.jobQueue.Clear();
  enemy.Melee=true;p.MeleeWindow=false;Check(!CohortCoverWindow(p,enemy,threats),"Melee protection changed");p.MeleeWindow=true;Check(CohortCoverWindow(p,enemy,threats),"Original melee cover entry point not retained");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskMath).Replace('METHODS',$taskMethods).Replace('COVER',$taskCover)
$taskCode=$taskCode.Replace('public static bool MovementSafe(Pawn p,CombatPathBudgetHelper.Observation o)=>p.Safe;', 'public static bool CanShootNow(Pawn p,Pawn e)=>p.Hit;public static bool MovementSafe(Pawn p,CombatPathBudgetHelper.Observation o)=>p.Safe;')
Add-Type -TypeDefinition $taskCode -Language CSharp
[ActualPhysicianLineRegression]::Run()
if($taskSource -match 'FindPathNow|ReleaseToPool|\.Reset\(|Rand\.') {throw 'New firing purpose bypasses detached path/RNG'}
if($taskSource -notmatch 'TeamCoverReady\(p,enemy,threats\)' -or $taskSource -notmatch 'CombatInterceptHelper.FutureFriendlyLaneClear'){throw 'Cover/rejoin lost native actual-shot or FF proof'}
$taskCohort=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatFallbackCohortHelper.cs')
if($taskCohort -notmatch 'terminalHorizon=physicianRejoin\?0:Math.Min' -or $taskCohort -notmatch 'physicianRejoin\?CoveredPhysicianRejoin\(pawn,path\):SaferRangedRoute'){throw 'Finite route purpose is not wired after the current-only prefilter'}
