$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskHelper = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/BuildingMaintenanceHelper.cs') -Raw
$taskStart = $taskHelper.IndexOf('public static bool ThermalMaintenanceDue')
$taskEnd = $taskHelper.IndexOf('public static ApiResult<BuildingRefuelResultDto> Refuel')
if ($taskStart -lt 0 -or $taskEnd -le $taskStart) { throw 'Actual native maintenance boundary missing' }
$taskMethods = $taskHelper.Substring($taskStart,$taskEnd-$taskStart).Replace('private static bool CanYieldRoutineTend','public static bool CanYieldRoutineTend')
$taskCare = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CareTriageHelper.cs') -Raw
$taskDiseaseStart = $taskCare.IndexOf('public static bool DiseaseCareProtected')
$taskDiseaseEnd = $taskCare.IndexOf('public static bool CanYield(')
$taskDisease = $taskCare.Substring($taskDiseaseStart,$taskDiseaseEnd-$taskDiseaseStart)
$taskMal = [regex]::Match($taskCare,'public static Hediff Malnutrition\([^;]+;').Value
$taskQueued = [regex]::Match($taskCare,'public static bool QueuedCare\([^;]+;').Value
$taskCareJob = [regex]::Match($taskCare,'public static bool Care\([^;]+;').Value
$taskCode = @'
using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Models { public class BuildingRefuelRequestDto { public string ExpectedCurrentJob; public int? ExpectedCarePatientId; } }
namespace Verse.AI {
 public enum PathEndMode { Touch } public enum Danger { Some }
 public class Target { public Thing Thing; }
 public class Job { public JobDef def = JobDefOf.TendPatient; public Target targetA = new Target(); }
 public class JobDef { public bool forceCompleteBeforeNextJob; }
 public class QueuedJob { public Job job; }
 public class Jobs { public bool interruptible=true; public List<QueuedJob> jobQueue=new List<QueuedJob>(); public bool IsCurrentJobPlayerInterruptible()=>interruptible; }
}
namespace RimWorld {
 public static class JobDefOf { public static JobDef TendPatient=new JobDef(), FeedPatient=new JobDef(), Rescue=new JobDef(); }
 public static class ThingDefOf { public static object Campfire=new object(); }
 public static class HediffDefOf { public static HediffDef Hypothermia=new HediffDef(), Heatstroke=new HediffDef(), BloodLoss=new HediffDef(), Malnutrition=new HediffDef(); }
 public static class PawnCapacityDefOf { public static object Moving=new object(), Manipulation=new object(); }
 public static class StatDefOf { public static object ComfyTemperatureMin=new object(); }
 public class HediffComp_Immunizable { public float Immunity; }
}
namespace Verse {
 public class HediffDef { public string defName="Other"; public float lethalSeverity; }
 public class Hediff { public HediffDef def; public bool Visible=true, IsCurrentlyLifeThreatening, tendable, immune; public float Severity; public HediffComp_Immunizable immunizable=new HediffComp_Immunizable(); public bool TendableNow()=>tendable; public T TryGetComp<T>() where T:class => immunizable as T; }
 public class Set { public float BleedRateTotal; public List<Hediff> hediffs=new List<Hediff>(); }
 public class Capacities { public float moving=1; public bool manipulation=true; public float GetLevel(object c)=>moving; public bool CapableOf(object c)=>manipulation; }
 public class Health { public Set hediffSet=new Set(); public Capacities capacities=new Capacities(); }
 public class MapPawns { public List<Pawn> FreeColonists=new List<Pawn>(); }
 public class Map { public MapPawns mapPawns=new MapPawns(); }
 public class Cell { public float temperature=-3; public bool roofed=true; public bool Roofed(Map m)=>roofed; public float GetTemperature(Map m)=>temperature; }
 public class Thing { public object def=ThingDefOf.Campfire; public int thingIDNumber; public Map Map; public Cell Position=new Cell(); public object room; public object GetRoom()=>room; }
 public class Building:Thing { public List<Cell> cells=new List<Cell>{new Cell()}; public List<Cell> OccupiedRect()=>cells; }
 public class Carry { public Thing CarriedThing; }
 public class Pawn:Thing { public bool IsColonistPlayerControlled=true, Dead, Spawned=true, inBed=true, reachable=true; public Health health=new Health(); public Carry carryTracker=new Carry(); public Jobs jobs=new Jobs(); public Job CurJob=new Job(); public JobDef CurJobDef=>CurJob.def; public Building bed=new Building(); public float minimum=16; public bool InBed()=>inBed; public Building CurrentBed()=>bed; public float GetStatValue(object d)=>minimum; public bool CanReach(Pawn p,PathEndMode e,Danger d)=>p.reachable; }
 public class FuelProps { public float fuelCapacity=20; }
 public class CompRefuelable { public float Fuel=0; public FuelProps Props=new FuelProps(); }
}
namespace RIMAPI.Helpers {
 // This boundary covers nonburning thermal patients; attached-fire identity is checked in the separate native job contract.
 public static class BurningPawnSafetyHelper { public static bool ProtectsPatient(Job j)=>false; }
 public static class PawnHelper { public static bool CanDevelopImmunity(Hediff h)=>h.immune; }
 public static class CareTriageHelper {
 MAL
 DISEASE
 CAREJOB
 QUEUED
 }
 public static class MaintenanceFixture {
 METHODS
 public static int Run() {
  int count=0;
  for(int mode=0;mode<23;mode++) {
   var room=new object(); var map=new Map(); var fire=new Building{room=room,Map=map};
   var patient=new Pawn{thingIDNumber=2,room=room,Map=map};
   patient.health.hediffSet.hediffs.Add(new Hediff{def=HediffDefOf.Hypothermia,Severity=.9f,IsCurrentlyLifeThreatening=true});
   patient.health.hediffSet.hediffs.Add(new Hediff{def=new HediffDef{defName="Frostbite"},Severity=2,tendable=true});
   var worker=new Pawn{thingIDNumber=1,Map=map};worker.CurJob.targetA.Thing=patient;
   map.mapPawns.FreeColonists.AddRange(new[]{worker,patient});
   var fuel=new CompRefuelable();var request=new BuildingRefuelRequestDto{ExpectedCurrentJob="TendPatient",ExpectedCarePatientId=2};
   bool expected=mode==0||mode==1||mode==22;
   switch(mode) {
    case 1:fuel.Fuel=4.9f;break;
    case 2:request.ExpectedCarePatientId=9;break;
    case 3:request.ExpectedCurrentJob=null;break;
    case 4:worker.CurJob.def=JobDefOf.FeedPatient;break;
    case 5:worker.CurJob.def=JobDefOf.Rescue;break;
    case 6:patient.health.hediffSet.BleedRateTotal=.2f;break;
    case 7:worker.health.hediffSet.BleedRateTotal=.1f;break;
    case 8:patient.health.hediffSet.hediffs.Add(new Hediff{def=new HediffDef{defName="WoundInfection"},immune=true});break;
    case 9:worker.health.hediffSet.hediffs.Add(new Hediff{def=new HediffDef(),immune=true});break;
    case 10:patient.Position.temperature=20;break;
    case 11:patient.room=new object();break;
    case 12:patient.inBed=false;break;
    case 13:patient.bed.cells[0].roofed=false;break;
    case 14:worker.carryTracker.CarriedThing=patient;break;
    case 15:worker.jobs.jobQueue.Add(new QueuedJob{job=new Job()});break;
    case 16:worker.jobs.interruptible=false;break;
    case 17:worker.health.capacities.moving=.3f;break;
    case 18:patient.health.hediffSet.hediffs.Add(new Hediff{def=HediffDefOf.Malnutrition,Severity=.8f});break;
    case 19:fuel.Fuel=6;break;
    case 20:fire.def=new object();break;
    case 21:map.mapPawns.FreeColonists.Add(new Pawn{Map=map,health=new Health{hediffSet=new Set{BleedRateTotal=.1f}}});break;
    case 22:map.mapPawns.FreeColonists.Add(new Pawn{Map=map,reachable=false,health=new Health{hediffSet=new Set{BleedRateTotal=.1f}}});break;
   }
   bool actual=CanYieldRoutineTend(worker,fire,fuel,request);
   if(actual!=expected)throw new Exception("Actual native patient heat boundary case "+mode+": "+actual);
   count++;
  }
  return count;
 }
 }
}
'@
$taskCode=$taskCode.Replace('METHODS',$taskMethods).Replace('DISEASE',$taskDisease).Replace('MAL',$taskMal).Replace('CAREJOB',$taskCareJob).Replace('QUEUED',$taskQueued)
Add-Type -TypeDefinition $taskCode
$taskCount=[RIMAPI.Helpers.MaintenanceFixture]::Run()
Write-Output ('PASS: '+$taskCount+' actual native patient heat boundary cases; routes and fuel job remain native and completion unverified')
