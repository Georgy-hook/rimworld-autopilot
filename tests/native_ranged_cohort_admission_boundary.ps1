$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatFallbackCohortHelper.cs')
$taskFrom=$taskSource.IndexOf('    public static class CombatFallbackMath')
$taskMath=$taskSource.Substring($taskFrom,$taskSource.IndexOf('    public static partial class CombatControlHelper')-$taskFrom)
$taskFrom=$taskSource.IndexOf('        private static bool PendingCohort(')
$taskPending=$taskSource.Substring($taskFrom,$taskSource.IndexOf('        private static bool CohortGunFreeFor(')-$taskFrom)
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatControlHelper.cs')
$taskPlans=[regex]::Match($taskControl,'private static readonly HashSet<string> RangedPlans=.*?;').Value
$taskDefensive=[regex]::Match($taskControl,'private static bool DefensivePlan\(string tactic\).*?;').Value
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
MATH
public sealed class Map {public Pawns mapPawns=new Pawns();}public sealed class Pawns {public List<Pawn> AllPawnsSpawned=new List<Pawn>();}
public sealed class Pawn {public int thingIDNumber;public Map Map;public object CurJobDef;public bool Owned=true,Stationary=true,Idle=true,Danger,Warning,Threat,Melee;}
public sealed class Plan {public Pawn Pawn;}
public sealed class FallbackCohort {public Pawn PendingMover,PendingGun,PendingEnemy;public HashSet<Pawn> Staged=new HashSet<Pawn>();public int PendingUntil=300;}
public static class JobDefOf {public static object Goto=new object(),AttackMelee=new object();}
public static class Find {public static TickManager TickManager=new TickManager();}public sealed class TickManager {public int TicksGame=100;}
public static class ActualRangedCohortAdmissionRegression {
 static int n;static bool Window=true,Free=true;static FallbackCohort Live;
 static Dictionary<int,Plan> Plans=new Dictionary<int,Plan>();
PLANS
DEFENSIVE
 static bool CohortLive(Pawn p,out FallbackCohort c){c=Live;return c!=null;}
 static bool CohortOwned(Pawn p)=>p.Owned;static bool OwnStationaryGun(Plan p)=>p.Pawn.Stationary;
 static bool DoctorReserveStationary(Plan p)=>p.Pawn.Stationary||p.Pawn.Idle;
 static bool Threat(Pawn p)=>p.Threat;static bool MeleeThreat(Pawn p)=>p.Melee;
 static bool TeamImmediateDanger(Pawn p)=>p.Danger;static bool MedicalFunctionWarning(Pawn p)=>p.Warning;
 static bool CohortGunFreeFor(Pawn g,Pawn p,Pawn e)=>Free;
 static bool CohortCoverWindow(Pawn g,Pawn e,List<Pawn> t)=>Window && (g.Stationary||!t.All(MeleeThreat)&&g.Idle);
PENDING
 static void Check(bool b,string m){n++;if(!b)throw new Exception(m);}
 public static int Run(){
  foreach(string tactic in new[]{"hold_cover","firing_line","focus_fire","backstep_fire","kite","spread_out"})Check(CohortCompatible(tactic,false,false),"Ranged optional directive escaped the shared finite cohort: "+tactic);
  foreach(string tactic in new[]{"advance_to_range","preemptive_strike","intercept_kidnapper","withdraw_and_regroup"})Check(!CohortCompatible(tactic,false,false),"Explicit assault/intercept/withdrawal silently rewritten as optional cohort: "+tactic);
  Check(!CohortCompatible("kite",true,false)&&CohortCompatible("kite",true,true),"Unenrolled melee behavior changed");
  var map=new Map();var mover=new Pawn{thingIDNumber=1,Map=map};var gun=new Pawn{thingIDNumber=2,Map=map,Stationary=false};var enemy=new Pawn{Map=map,Threat=true};map.mapPawns.AllPawnsSpawned.Add(enemy);
  Plans[2]=new Plan{Pawn=gun};Live=new FallbackCohort{PendingMover=mover,PendingGun=gun,PendingEnemy=enemy};
  Check(PendingCohort(Live),"Selected ranged idle cover lost target preparation before real projectile");
  Check(!CombatFallbackMath.CoverObserved(100,0,100,60),"A preparation was counted as a covering shot");
  gun.Owned=false;Check(!PendingCohort(Live),"Foreign gun adopted");gun.Owned=true;
  gun.Danger=true;Check(!PendingCohort(Live),"Threatened gun committed to cover");gun.Danger=false;
  gun.Warning=true;Check(!PendingCohort(Live),"Clinically incapable gun retained");gun.Warning=false;
  Free=false;Check(!PendingCohort(Live),"Another mover's real cover lease overwritten");Free=true;
  Window=false;Check(!PendingCohort(Live),"Unsafe firing/FF window omitted");Window=true;
  enemy.Threat=false;Check(!PendingCohort(Live),"Stale enemy retained");enemy.Threat=true;
  Find.TickManager.TicksGame=300;Check(!PendingCohort(Live),"Preparation did not expire");Find.TickManager.TicksGame=100;
  mover.CurJobDef=JobDefOf.Goto;Check(!PendingCohort(Live),"A mover already in transit started a second preparation");mover.CurJobDef=null;
  enemy.Melee=true;Check(!PendingCohort(Live),"Ranged idle exception weakened melee ownership");gun.Stationary=true;Check(PendingCohort(Live),"Existing melee cover was broken");
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('MATH',$taskMath).Replace('PLANS',$taskPlans).Replace('DEFENSIVE',$taskDefensive).Replace('PENDING',$taskPending)) -Language CSharp
[ActualRangedCohortAdmissionRegression]::Run()
if($taskSource -notmatch 'CohortInTransit\(p\) \|\| DoctorBoundInTransit\(p\)' -or $taskSource -notmatch 'TryDoctorBoundAnchor\(doctor,out medicalPost\)'){throw 'Physician transit slot or committed shared anchor was not wired'}
if($taskSource -match 'ContainedBeds|OwnedBed'){throw 'A bedroom replaced actual tactical group/physician origin'}
if($taskSource -notmatch 'return target!=null;' -or $taskSource -notmatch 'next.Value.InHorDistOf\(CohortFormationPost\(cohort,p\),4f\)'){throw 'Blind post blocks fresh local firing-angle review indefinitely'}
