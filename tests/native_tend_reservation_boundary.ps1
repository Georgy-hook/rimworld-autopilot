$ErrorActionPreference='Stop'
$taskRoot=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi'
$taskDto=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'Models/Pawns/ColonistDto.cs')
$taskStart=$taskDto.IndexOf('    public class MedicalTendResultDto')
$taskDto=$taskDto.Substring($taskStart,$taskDto.IndexOf('    public class MedicalTendRequestDto')-$taskStart)
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'Services/Pawns/PawnJobService/PawnJobService.cs')
$taskStart=$taskSource.IndexOf('                if (!doctor.CanReserveAndReach(patient, PathEndMode.Touch, Danger.Some))')
$taskBranch=$taskSource.Substring($taskStart,$taskSource.IndexOf('                bool wasSelfTend', $taskStart)-$taskStart)
$taskStart=$taskSource.IndexOf('        private static ApiResult<MedicalTendResultDto> TendRefusal(')
$taskRefusal=$taskSource.Substring($taskStart,$taskSource.IndexOf('        public ApiResult<MedicalTendResultDto> AssignTendJob(',$taskStart)-$taskStart)
$taskResult=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'Core/HttpContext/ResponceBuilder.cs')
$taskStart=$taskResult.IndexOf('    public class ApiResult<T>')
$taskResult=$taskResult.Substring($taskStart,$taskResult.IndexOf('    public class ApiResult'+[Environment]::NewLine,$taskStart)-$taskStart)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
DTO
RESULT
public enum PathEndMode {Touch}public enum Danger {Some}
public sealed class Hediff {public bool TendableNow()=>true;}
public sealed class Set {public List<Hediff> hediffs=new List<Hediff>{new Hediff()};}
public sealed class Health {public Set hediffSet=new Set();}
public sealed class Pawn {public int thingIDNumber;public bool Reserve;public int Queries;public Health health=new Health();public bool CanReserveAndReach(Pawn p,PathEndMode m,Danger d){Queries++;return Reserve;}}
public static class RealTendReservationBoundary {
REFUSAL
 static ApiResult<MedicalTendResultDto> Review(Pawn doctor,Pawn patient){
  var request=new {PatientPawnId=patient.thingIDNumber};
BRANCH
  return ApiResult<MedicalTendResultDto>.Ok(new MedicalTendResultDto{Applied=true});
 }
 public static int Run(){
  var d=new Pawn{thingIDNumber=8814,Reserve=false};var p=new Pawn{thingIDNumber=8822};var r=Review(d,p);
  if(!r.Success || r.Data.Applied || !r.Data.Blocked || r.Data.InProgress || r.Errors.Count!=0 || r.Data.PatientPawnId!=8822 || r.Data.DoctorPawnId!=8814 || d.Queries!=1 || r.Data.Reason!="patient_reserved_or_unreachable")throw new Exception("Actual reservation refusal became500/acceptance or lost exact binding");
  d.Reserve=true;r=Review(d,p);if(!r.Success || !r.Data.Applied)throw new Exception("Reachable reservation was rejected");
  p.health.hediffSet.hediffs.Clear();r=Review(d,p);if(!r.Success || r.Data.Applied || !r.Data.Blocked || r.Data.Reason!="no_tendable_condition")throw new Exception("No tendable condition became a fake accepted job or HTTP500");
  return 3;
 }
}
'@
$taskCode=$taskCode.Replace('DTO',$taskDto).Replace('RESULT',$taskResult).Replace('BRANCH',$taskBranch).Replace('REFUSAL',$taskRefusal)
Add-Type -TypeDefinition $taskCode -Language CSharp
[RealTendReservationBoundary]::Run()
$taskMethod=$taskSource.Substring($taskSource.IndexOf('        public ApiResult<MedicalTendResultDto> AssignTendJob('))
$taskMethod=$taskMethod.Substring(0,$taskMethod.IndexOf('        public ApiResult AssignBedRest('))
if($taskMethod.IndexOf('MedicalTendResultDto.Refused') -gt $taskMethod.IndexOf('doctor.drafter.Drafted = false')){throw 'Reservation refusal releases combat before validation'}
if($taskMethod.IndexOf('doctor.jobs.jobQueue.Any()') -gt $taskMethod.IndexOf('MedicalTendResultDto.Refused')){throw 'Later queued instructions are no longer protected'}
if($taskMethod -notmatch 'Applied=false,InProgress=true'){throw 'Repeated exact tend binding was counted as a new job'}
$taskTeam=Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'Helpers/CombatTeamCareHelper.cs')
if($taskTeam -notmatch 'result.Success && result.Data\?\.Applied==true'){throw 'Native first-care accepts a structured refusal'}
