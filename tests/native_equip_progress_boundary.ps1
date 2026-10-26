$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'Services/Pawns/PawnJobService/PawnJobService.cs')
$taskFrom=$taskSource.IndexOf('                    if (pawn.CurJobDef == JobDefOf.Equip && pawn.CurJob.targetA.Thing == equipTarget)')
$taskBranch=$taskSource.Substring($taskFrom,$taskSource.IndexOf('                    if (!pawn.CanReserveAndReach(equipTarget,',$taskFrom)-$taskFrom)
$taskDto=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'Models/Pawns/PawnJobInProgressResultDto.cs')
$taskResult=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'Core/HttpContext/ResponceBuilder.cs')
$taskFrom=$taskResult.IndexOf('    public class ApiResult'+[Environment]::NewLine)
$taskResult=$taskResult.Substring($taskFrom,$taskResult.IndexOf('    public static class ResponseBuilder')-$taskFrom)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
namespace RIMAPI.Core {RESULT}
DTO
public sealed class Target {public object Thing;}
public sealed class Job {public Target targetA=new Target();}
public sealed class Thing {public int thingIDNumber=20;}
public sealed class Pawn {public int thingIDNumber=1;public object CurJobDef;public Job CurJob=new Job();}
public static class JobDefOf {public static object Equip=new object();}
public static class EquipProgressRegression {
 static RIMAPI.Core.ApiResult Review(Pawn pawn,Thing equipTarget){
BRANCH
  return null;
 }
 public static int Run(){
  var p=new Pawn();var target=new Thing();p.CurJobDef=JobDefOf.Equip;p.CurJob.targetA.Thing=target;var original=p.CurJob;
  var r=Review(p,target) as RIMAPI.Models.PawnJobInProgressResultDto;
  if(r==null||!r.Success||r.Applied||!r.InProgress||r.PawnId!=1||r.TargetThingId!=20||r.Errors.Count!=0||p.CurJob!=original)throw new Exception("Exact native Equip became error/applied/restarted or lost binding");
  if(Review(p,new Thing())!=null)throw new Exception("A different target was falsely read back as current Equip");
  p.CurJobDef=new object();if(Review(p,target)!=null)throw new Exception("A different native job became Equip in progress");
  return 3;
 }
}
'@
$taskCode='using RIMAPI.Models;'+[Environment]::NewLine+$taskCode.Replace('RESULT',$taskResult).Replace('DTO',$taskDto).Replace('BRANCH',$taskBranch)
Add-Type -TypeDefinition $taskCode -Language CSharp
[EquipProgressRegression]::Run()
