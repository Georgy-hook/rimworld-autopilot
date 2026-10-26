$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatControlHelper.cs')
$taskStart=$taskControl.IndexOf('        private static bool TryReleaseCompletedEscape(')
$taskEnd=$taskControl.IndexOf('        // A forecast cover transit', $taskStart)
$taskMethod=$taskControl.Substring($taskStart,$taskEnd-$taskStart)
$taskIntercept=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatInterceptHelper.cs')
$taskMath=$taskIntercept.Substring($taskIntercept.IndexOf('    public static class CombatInterceptMath'),$taskIntercept.IndexOf('    public static class CombatInterceptHelper')-$taskIntercept.IndexOf('    public static class CombatInterceptMath'))
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
MATH
public struct IntVec3 {public int x,z;public IntVec3(int x,int z){this.x=x;this.z=z;}public float DistanceTo(IntVec3 b)=>(float)Math.Sqrt((x-b.x)*(x-b.x)+(z-b.z)*(z-b.z));public bool ContainsStaticFire(Map m)=>false;public bool Fogged(Map m)=>false;}
public enum GasType {ToxGas,DeadlifeDust}public enum LocomotionUrgency {Jog,Sprint}
public sealed class Gas {public float DensityAt(IntVec3 p,GasType t)=>0;}
public sealed class Map {public Gas gasGrid=new Gas();}
public sealed class JobDef {}public static class JobDefOf {public static readonly JobDef Goto=new JobDef(),AttackStatic=new JobDef();}
public sealed class Target {public Pawn Thing;public IntVec3 Cell;}
public sealed class Job {public JobDef def=JobDefOf.Goto;public Target targetA=new Target();public bool playerForced,Owned=true;public LocomotionUrgency locomotionUrgency;}
public sealed class Queued {public Job job;}
public sealed class Jobs {public List<Queued> jobQueue=new List<Queued>();}
public sealed class Carry {public object CarriedThing;}
public sealed class Summary {public float SummaryHealthPercent=1;}
public sealed class Hediffs {public float BleedRateTotal;}
public sealed class Caps {public float GetLevel(object stat)=>1;}
public sealed class Health {public Summary summaryHealth=new Summary();public Hediffs hediffSet=new Hediffs();public Caps capacities=new Caps();}
public sealed class ProjectileData {public float SpeedTilesPerTick=1;}
public sealed class ProjectileDef {public ProjectileData projectile=new ProjectileData();}
public sealed class VerbProps {public float warmupTime=.5f;public int burstShotCount=1,ticksBetweenBurstShots=5;public ProjectileDef defaultProjectile=new ProjectileDef();}
public sealed class Verb {public VerbProps verbProps=new VerbProps();}
public sealed class CompEquippable {public Verb PrimaryVerb=new Verb();}
public sealed class Weapon {public T TryGetComp<T>()where T:new()=>new T();}
public sealed class Equipment {public Weapon Primary=new Weapon();}
public sealed class Pawn {public bool Dead,Downed,Spawned=true,Doctor=true,Reserved=true,Pursuer,Closing=true,Melee=true,ShotSafe=true,QueuedCare,Protected;public float Exposure,Lock=5;public int TicksPerMoveCardinal=12,Takes;public Map Map=new Map();public IntVec3 Position;public Pawn Victim;public Job CurJob=new Job();public JobDef CurJobDef=>CurJob?.def;public Jobs jobs=new Jobs();public Carry carryTracker=new Carry();public Health health=new Health();public Equipment equipment=new Equipment();public float GetStatValue(object stat)=>1;}
public sealed class Plan {public Pawn Pawn,Target;public string Mode="retreat",Tactic="hold_cover";public Job OwnedJob,QueuedShot;}
public static class PawnCapacityDefOf {public static object Moving=new object();}public static class StatDefOf {public static object AimingDelayFactor=new object();}
public static class JobMaker {public static Job MakeJob(JobDef d,Pawn p)=>new Job{def=d,targetA=new Target{Thing=p}};}
public static class CareTriageHelper {public static bool QueuedCare(Pawn p)=>p.QueuedCare;}
public static class CombatNativeHelper {public static bool Protected(Pawn p)=>p.Protected;}
public static class CombatPathBudgetHelper {public static void Checkpoint(){}}
public static class CombatInterceptHelper {public static bool Pursuing(Pawn t,Pawn p)=>t.Pursuer;public static bool CanShootNow(Pawn p,Pawn t)=>p.ShotSafe;public static float MovementLockTicks(Pawn p)=>p.Lock;}
public static class CombatOrderHelper {public static bool Owned(Pawn p,Job j)=>j.Owned;public static bool Take(Pawn p,ref Job j){p.Takes++;p.CurJob=j;return true;}}
public static class ActualPhysicianFireReturnRegression {
 static int n;static void Check(bool b,string why){n++;if(!b)throw new Exception(why);}
 static bool OwnedRangePostInTransit(Plan p)=>false;static bool CohortInTransit(Plan p)=>false;
 static bool DoctorBoundInTransit(Plan p)=>false;
 static bool NativeDoctor(Pawn p)=>p.Doctor;static bool IsReservedDoctor(Pawn p)=>p.Reserved;
 static bool MeleeThreat(Pawn p)=>p.Melee;static bool ClosingMelee(Pawn p,Pawn v)=>p.Melee&&p.Closing;
 static object ObservedVictim(Pawn p)=>p.Victim;
 static float IncomingRangedExposure(Pawn p,IntVec3 c)=>p.Exposure;
 static Pawn GroupTarget(Pawn p,List<Pawn> t,object ignored)=>t.FirstOrDefault();
METHOD
 static Plan Fixture(out Pawn p,out Pawn enemy){p=new Pawn{Position=new IntVec3(0,0)};enemy=new Pawn{Position=new IntVec3(10,0),Pursuer=true};return new Plan{Pawn=p,OwnedJob=p.CurJob,Target=new Pawn{Dead=true}};}
 public static int Run(){
  Pawn p,e;var plan=Fixture(out p,out e);
  Check(TryReleaseCompletedEscape(plan,new List<Pawn>{e})&&p.Takes==1&&p.CurJob.def==JobDefOf.AttackStatic&&plan.Target==e,"Dead original target plus a distant different pursuer hid a current checked physician shot");
  plan=Fixture(out p,out e);p.Doctor=false;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"Generic escape rule was relaxed for all pawns");
  plan=Fixture(out p,out e);e.Position=new IntVec3(4,0);Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e})&&p.Takes==0,"Physician stopped without a finite volley before contact");
  plan=Fixture(out p,out e);p.Lock=200;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"Native movement/cooldown lock was omitted");
  plan=Fixture(out p,out e);p.ShotSafe=false;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"Friendly-fire/current firing gate bypassed");
  plan=Fixture(out p,out e);var other=new Pawn{Position=new IntVec3(1,0),Closing=false};Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e,other}),"A nonpursuing nearby melee threat was omitted from the retarget bound");
  plan=Fixture(out p,out e);e.Melee=false;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"Ranged escape was stopped as a melee medical rejoin");
  plan=Fixture(out p,out e);plan.Target.Dead=false;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"An active original escape cause was discarded");
  plan=Fixture(out p,out e);p.jobs.jobQueue.Add(new Queued{job=new Job{Owned=false}});Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e})&&p.Takes==0,"Later manual queue was erased");
  plan=Fixture(out p,out e);p.QueuedCare=true;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"Queued clinical work was interrupted");
  plan=Fixture(out p,out e);p.Protected=true;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"Protected care was interrupted");
  plan=Fixture(out p,out e);p.carryTracker.CarriedThing=new Pawn();Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"Carrying a patient was interrupted");
  plan=Fixture(out p,out e);p.health.summaryHealth.SummaryHealthPercent=.5f;Check(!TryReleaseCompletedEscape(plan,new List<Pawn>{e}),"A critical physician lost clinical transit protection");
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath).Replace('METHOD',$taskMethod)) -Language CSharp
[ActualPhysicianFireReturnRegression]::Run()
$taskTick=$taskControl.Substring($taskControl.IndexOf('        private static void TickBudgeted()'))
if(!($taskTick.IndexOf('ReviewImmediateTeamDanger();') -lt $taskTick.IndexOf('ReviewPhysicianFireReturn();') -and $taskTick.IndexOf('ReviewPhysicianFireReturn();') -lt $taskTick.IndexOf('ReviewDoctorPreposition();') -and $taskTick.IndexOf('ReviewDoctorPreposition();') -lt $taskTick.IndexOf('ReviewCoordinatedFire();'))){throw 'The checked physician phases are still starved by optional coordination, or precede immediate danger'}
$taskReserve=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorReserveHelper.cs')
if($taskReserve -notmatch '(?s)catch\(CombatReviewDeferredException\).*DoctorPrepositionReviews.Remove\(p\);.*throw;'){throw 'Deferred early route waits out its normal completed-review cooldown'}
$taskEarly=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatPhysicianFireReturnHelper.cs')
if($taskEarly -match 'FindPathNow|ReleaseToPool|\.Reset\(|Rand\.' -or $taskEarly -notmatch 'p.CurJob!=plan.OwnedJob'){throw 'Physician early return bypasses exact job/native path/RNG/cooldown boundary'}
