$ErrorActionPreference='Stop'
$taskRepo=Split-Path -Parent $PSScriptRoot
$taskMeditation=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/MeditationPlanningHelper.cs')
$taskStart=$taskMeditation.IndexOf('public static bool ScheduleOpportunity')
$taskEnd=$taskMeditation.IndexOf('private static IEnumerable<Thing>', $taskStart)
$taskSchedule=$taskMeditation.Substring($taskStart,$taskEnd-$taskStart)
$taskDrugs=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/DrugCapacitySafety.cs')
$taskStart=$taskDrugs.IndexOf('public static bool Risk(bool')
$taskEnd=$taskDrugs.IndexOf('public static bool Risk(Pawn', $taskStart)
$taskRisk=$taskDrugs.Substring($taskStart,$taskEnd-$taskStart)
$taskAutonomy=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/AutonomyDrugSafety.cs')
$taskStart=$taskAutonomy.IndexOf('public static bool Block(bool')
$taskEnd=$taskAutonomy.IndexOf('private static bool Required', $taskStart)
$taskBlock=$taskAutonomy.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
public static class MeditationDrugBoundary {
SCHEDULE
RISK
BLOCK
static int n;
static void Check(bool value,string reason){n++;if(!value)throw new System.Exception(reason);}
public static int Run(){
Check(ScheduleOpportunity(false,true,false,true,true,0),"Natural non-psycaster excluded");
Check(!ScheduleOpportunity(false,true,false,false,true,0),"Ineligible tree visitor promoted");
Check(!ScheduleOpportunity(true,true,true,true,true,0),"Protected caregiver reassigned");
Check(!ScheduleOpportunity(false,false,true,true,true,0),"Hungry/tired/downed worker scheduled");
Check(!ScheduleOpportunity(false,true,false,true,false,0),"Unseen tree inferred");
Check(ScheduleOpportunity(false,true,true,false,false,0),"Other focus psycaster excluded");
Check(!ScheduleOpportunity(false,true,true,true,true,4),"Meditation consumed unlimited labor");
Check(Risk(false,false,.53f,.15f,.48f,true,false),"Injured sedation unrecognized");
Check(Risk(false,true,1,1,1,false,true),"Appetite increase during starvation ignored");
Check(!Risk(false,false,1,1,1,true,false),"Healthy social policy universally prohibited");
Check(!Risk(false,true,.53f,.15f,.48f,false,false),"Non-sedating medicine incorrectly blocked");
Check(Risk(true,false,1,1,1,true,false),"Downed sedation ignored");
Check(Block(true,true,true,false,true),"Unsafe autonomous dose permitted");
Check(!Block(false,true,true,false,true),"Ordinary human play was changed");
Check(!Block(true,false,true,false,true),"Other faction affected");
Check(!Block(true,true,false,false,true),"Medical dose blocked");
Check(!Block(true,true,true,true,true),"Addiction or genetic dose blocked");
Check(!Block(true,true,true,false,false),"Healthy safe dose blocked");
return n;}
}
'@
$taskCode=$taskCode.Replace('SCHEDULE',$taskSchedule).Replace('RISK',$taskRisk).Replace('BLOCK',$taskBlock)
Add-Type -TypeDefinition $taskCode -Language CSharp
[MeditationDrugBoundary]::Run()
