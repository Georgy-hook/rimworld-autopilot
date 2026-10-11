$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskResilience = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/ResilienceAutomationHelper.cs') -Raw
$taskStart = $taskResilience.IndexOf('private static bool CarePatient(Pawn p)')
$taskEnd = $taskResilience.IndexOf('public static ApiResult<ResilienceContextDto> Context', $taskStart)
if ($taskStart -lt 0 -or $taskEnd -le $taskStart) { throw 'Actual native patient boundary missing' }
$taskPatient = $taskResilience.Substring($taskStart, $taskEnd-$taskStart).Replace('private static bool CarePatient', 'public static bool CarePatient')
$taskOrdinary = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/OrdinaryWorkSafety.cs') -Raw
$taskStart = $taskOrdinary.IndexOf('public static string WorkerBlocker')
$taskEnd = $taskOrdinary.IndexOf('public static bool Route', $taskStart)
if ($taskStart -lt 0 -or $taskEnd -le $taskStart) { throw 'Actual native worker boundary missing' }
$taskWorker = $taskOrdinary.Substring($taskStart, $taskEnd-$taskStart)
$taskCode = @'
using System;
using System.Linq;
public class Faction { public static Faction OfPlayer=new Faction(); }
public class Race { public bool Humanlike=true; }
public class Cell { public bool fog; public bool Fogged(object map)=>fog; }
public class WorkTypeDef { }
public class JobDef { public string defName="Wait"; public bool forceCompleteBeforeNextJob; }
public class Job { public JobDef def=new JobDef(); }
public class Carry { public object CarriedThing; }
public class Capacities { public float consciousness=1,moving=1,manipulation=1; public float GetLevel(object c)=>c==PawnCapacityDefOf.Consciousness?consciousness:c==PawnCapacityDefOf.Moving?moving:manipulation; }
public class Set { public float BleedRateTotal; }
public class Health { public Set hediffSet=new Set(); public Capacities capacities=new Capacities(); }
public class Pawn { public bool Dead,Downed,Drafted,InMentalState,IsPrisonerOfColony,Spawned=true,IsColonistPlayerControlled=true,hostile,disabled,queued,care,disease;
 public Faction Faction,HostFaction; public Race RaceProps=new Race(); public Cell Position=new Cell(); public object Map=new object(),workSettings=new object(); public Carry carryTracker=new Carry(); public Job CurJob=new Job(); public JobDef CurJobDef=>CurJob.def; public Health health=new Health();
 public bool HostileTo(Faction f)=>hostile; public bool WorkTypeIsDisabled(WorkTypeDef w)=>disabled; }
public static class PawnCapacityDefOf { public static object Consciousness=new object(),Moving=new object(),Manipulation=new object(); }
public static class CareTriageHelper { public static bool QueuedCare(Pawn p)=>p.queued; public static bool DiseaseCareProtected(Pawn p)=>p.disease; }
public static class CombatNativeHelper { public static bool HasCareJob(Pawn p)=>p.care; }
public static class DecisionBoundaryFixture {
PATIENT
WORKER
static void Check(bool b,string name) { if(!b)throw new Exception(name); }
public static int Run() {
 int n=0; var work=new WorkTypeDef();
 var neutral=new Pawn { IsColonistPlayerControlled=false,Downed=true };
 Check(CarePatient(neutral),"Visible neutral downed patient missing");n++;
 neutral.Downed=false;Check(!CarePatient(neutral),"Healthy neutral is not an urgent patient");n++;
 neutral.HostFaction=Faction.OfPlayer;Check(CarePatient(neutral),"Previously rescued neutral guest missing");n++;
 neutral.hostile=true;Check(!CarePatient(neutral),"Hostile neutral care bypass");n++;
 neutral.hostile=false;neutral.Position.fog=true;Check(!CarePatient(neutral),"Hidden neutral information leak");n++;
 neutral.Position.fog=false;neutral.Dead=true;Check(!CarePatient(neutral),"Dead patient included");n++;
 Check(CarePatient(new Pawn()),"Colonist regression");n++;
 Check(CarePatient(new Pawn {IsColonistPlayerControlled=false,IsPrisonerOfColony=true}),"Prisoner regression");n++;
 var animal=new Pawn {IsColonistPlayerControlled=false,Faction=Faction.OfPlayer};animal.RaceProps.Humanlike=false;
 Check(CarePatient(animal),"Owned animal regression");n++;
 animal.Faction=null;animal.Downed=true;Check(!CarePatient(animal),"Wild animal exposed as player patient");n++;
 var p=new Pawn();Check(Worker(p,work)&&WorkerBlocker(p,work)==null,"Ready worker");n++;
 p.queued=true;Check(!Worker(p,work)&&WorkerBlocker(p,work)=="protected_patient_care","Queued care bypass");n++;
 p.queued=false;p.care=true;Check(!Worker(p,work),"Active care bypass");n++;
 p.care=false;p.CurJob.def.defName="Ingest";Check(!Worker(p,work),"Food ingestion interrupted");n++;
 p.CurJob.def.defName="Research";Check(Worker(p,work),"Ordinary research should remain eligible");n++;
 p.CurJob.def.forceCompleteBeforeNextJob=true;Check(!Worker(p,work),"Required completion bypass");n++;
 p.CurJob.def.forceCompleteBeforeNextJob=false;p.health.hediffSet.BleedRateTotal=.1f;Check(!Worker(p,work),"Bleeding worker bypass");n++;
 p.health.hediffSet.BleedRateTotal=0;p.disease=true;Check(!Worker(p,work),"Disease protected worker bypass");n++;
 p.disease=false;p.disabled=true;Check(!Worker(p,work),"Disabled work bypass");n++;
 p.disabled=false;p.health.capacities.moving=.59f;Check(!Worker(p,work),"Low movement bypass");n++;
 p.health.capacities.moving=1;p.health.capacities.manipulation=float.NaN;Check(!Worker(p,work),"NaN capacity must not become ready");n++;
 p.health.capacities.manipulation=1;p.IsColonistPlayerControlled=false;Check(!Worker(p,work),"Neutral patient accidentally selected as worker");n++;
 return n;
}}
'@
$taskCode = $taskCode.Replace('PATIENT', $taskPatient).Replace('WORKER', $taskWorker)
Add-Type -TypeDefinition $taskCode -Language CSharp
$taskPassed = [DecisionBoundaryFixture]::Run()
Write-Output "native decision context boundary: $taskPassed cases passed; no game orders"
