$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'Services/Pawns/PawnJobService/PawnJobService.cs')
$taskFrom=$taskSource.IndexOf('        private static ApiResult<SleepingBedResultDto> SleepingBedRefusal(')
$taskMethods=$taskSource.Substring($taskFrom,$taskSource.IndexOf('        public ApiResult<MedicalFeedResultDto> AssignFeedJob(',$taskFrom)-$taskFrom)
$taskDto=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'Models/Pawns/ColonistDto.cs')
$taskFrom=$taskDto.IndexOf('    public class SleepingBedResultDto')
$taskDto=$taskDto.Substring($taskFrom,$taskDto.IndexOf('    public class MedicalFeedResultDto')-$taskFrom)
$taskResult=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'Core/HttpContext/ResponceBuilder.cs')
$taskFrom=$taskResult.IndexOf('    public class ApiResult<T>')
$taskResult=$taskResult.Substring($taskFrom,$taskResult.IndexOf('    public class ApiResult'+[Environment]::NewLine,$taskFrom)-$taskFrom)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
DTO
RESULT
public sealed class Faction {public static Faction OfPlayer=new Faction();}
public enum PathEndMode {OnCell}public enum Danger {Some}
public sealed class Building_Bed {public int thingIDNumber=20;public bool Spawned=true,Medical,ForPrisoners;public object Map=PawnHelper.Map,def=new object();public Faction Faction=Faction.OfPlayer;public List<Pawn> OwnersForReading=new List<Pawn>();}
public sealed class Target {public object Thing;}
public sealed class Job {public object def;public Target targetA=new Target();public bool restUntilHealed;}
public sealed class Jobs {public List<Job> jobQueue=new List<Job>();public int Takes;public bool Accept=true,Throw;public bool TryTakeOrderedJob(Job j){Takes++;if(Throw)throw new Exception("Declared unexpected engine failure");return Accept;}}
public sealed class Carry {public object CarriedThing;}
public sealed class Ownership {public Building_Bed OwnedBed;public int Claims;public bool Accept=true;public void ClaimBedIfNonMedical(Building_Bed b){Claims++;if(Accept)OwnedBed=b;}}
public sealed class Pawn {public int thingIDNumber=1;public bool Spawned=true,Dead,Downed,Drafted,InMentalState,Care,Retreat,Recovery,Reach=true,Safe=true,Compatible=true;public Faction Faction=Faction.OfPlayer;public object Map=PawnHelper.Map;public Jobs jobs=new Jobs();public Carry carryTracker=new Carry();public Ownership ownership=new Ownership();public Job CurJob=new Job();public object CurJobDef=>CurJob.def;public bool CanReserveAndReach(Building_Bed b,PathEndMode p,Danger d)=>Reach;}
public static class JobDefOf {public static object Ingest=new object(),LayDown=new object();}
public static class JobMaker {public static Job MakeJob(object def,Building_Bed b)=>new Job{def=def,targetA=new Target{Thing=b}};}
public static class PawnHelper {public static object Map=new object();public static Pawn Actor;public static Pawn FindPawnById(int i)=>Actor;}
public static class BuildingHelper {public static Building_Bed Bed;public static object FindBuildingByID(int i)=>Bed;}
public static class CombatNativeHelper {public static bool HasClinicalCareJob(Pawn p)=>p.Care;public static bool HasCareRetreat(Pawn p)=>p.Retreat;}
public static class CaregiverRecoveryHelper {public static bool Protected(Pawn p)=>p.Recovery;}
public static class RestUtility {public static bool CanUseBedEver(Pawn p,object d)=>p.Compatible;}
public static class ResilienceAutomationHelper {public static bool RoutineRouteSafe(Pawn p,Building_Bed b)=>p.Safe;}
public sealed class ActualSleepAssignmentRegression {
METHODS
 static int n;static void Check(bool b,string m){n++;if(!b)throw new Exception(m);}
 static MedicalBedRestRequestDto Request()=>new MedicalBedRestRequestDto{PatientPawnId=1,BedBuildingId=20};
 static Pawn Fresh(){PawnHelper.Actor=new Pawn();BuildingHelper.Bed=new Building_Bed();return PawnHelper.Actor;}
 static void Refuse(Action<Pawn> change,string reason){var p=Fresh();change(p);var r=new ActualSleepAssignmentRegression().AssignSleepingBed(Request());Check(r.Success&&!r.Data.Applied&&r.Data.Blocked&&r.Data.PatientPawnId==1&&r.Data.BedBuildingId==20&&r.Data.Reason==reason&&p.jobs.Takes==0&&p.ownership.Claims==0,"Invalid ordinary sleep replaced work/owner or became HTTP500: "+reason);}
 public static int Run(){
  Refuse(p=>BuildingHelper.Bed.OwnersForReading.Add(new Pawn()),"sleeping_bed_owned_or_incompatible");
  Refuse(p=>p.Compatible=false,"sleeping_bed_owned_or_incompatible");
  Refuse(p=>p.Care=true,"sleep_assignment_would_interrupt_care_or_food");
  Refuse(p=>p.Retreat=true,"sleep_assignment_would_interrupt_care_or_food");
  Refuse(p=>p.CurJob.def=JobDefOf.Ingest,"sleep_assignment_would_interrupt_care_or_food");
  Refuse(p=>p.jobs.jobQueue.Add(new Job()),"sleep_assignment_would_interrupt_queue_or_carry");
  Refuse(p=>p.carryTracker.CarriedThing=new Pawn(),"sleep_assignment_would_interrupt_queue_or_carry");
  Refuse(p=>p.Recovery=true,"caregiver_recovery_in_progress");
  Refuse(p=>p.Reach=false,"sleeping_bed_unreachable_or_unsafe");
  Refuse(p=>p.Safe=false,"sleeping_bed_unreachable_or_unsafe");
  Refuse(p=>p.Drafted=true,"ordinary_sleeping_bed_or_actor_unavailable");
  Refuse(p=>BuildingHelper.Bed.Medical=true,"ordinary_sleeping_bed_or_actor_unavailable");
  var service=new ActualSleepAssignmentRegression();var p=Fresh();var r=service.AssignSleepingBed(Request());Check(r.Success&&r.Data.Applied&&r.Data.Assigned&&!r.Data.InProgress&&p.jobs.Takes==1&&p.ownership.Claims==1,"Native ordered sleep and ownership not reported");
  p=Fresh();p.ownership.Accept=false;r=service.AssignSleepingBed(Request());Check(r.Success&&r.Data.Applied&&!r.Data.Assigned&&p.jobs.Takes==1,"Accepted native job fabricated an ownership change");
  p=Fresh();p.CurJob=JobMaker.MakeJob(JobDefOf.LayDown,BuildingHelper.Bed);p.ownership.OwnedBed=BuildingHelper.Bed;r=service.AssignSleepingBed(Request());Check(r.Success&&!r.Data.Applied&&r.Data.Assigned&&r.Data.InProgress&&p.jobs.Takes==0&&p.ownership.Claims==0,"Exact sleeping job restarted or re-counted as applied");
  p=Fresh();p.CurJob=JobMaker.MakeJob(JobDefOf.LayDown,BuildingHelper.Bed);r=service.AssignSleepingBed(Request());Check(r.Success&&r.Data.Applied&&r.Data.Assigned&&r.Data.InProgress&&p.jobs.Takes==0&&p.ownership.Claims==1,"Exact sleeping job failed to report real claim without restart");
  p=Fresh();p.CurJob=JobMaker.MakeJob(JobDefOf.LayDown,BuildingHelper.Bed);p.ownership.Accept=false;r=service.AssignSleepingBed(Request());Check(r.Success&&!r.Data.Applied&&!r.Data.Assigned&&p.jobs.Takes==0,"Rejected native claim fabricated assignment");
  p=Fresh();p.jobs.Accept=false;r=service.AssignSleepingBed(Request());Check(!r.Success&&p.ownership.Claims==0,"Unexpected ordered-job failure was hidden or claimed bed");
  p=Fresh();p.jobs.Throw=true;r=service.AssignSleepingBed(Request());Check(!r.Success&&r.Errors.Any(e=>e.Contains("Declared unexpected"))&&p.ownership.Claims==0,"Unexpected native exception was silently treated as a normal refusal");
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('DTO',$taskDto).Replace('RESULT',$taskResult).Replace('METHODS',$taskMethods)) -Language CSharp
[ActualSleepAssignmentRegression]::Run()
