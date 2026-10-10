$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/InstantConstructionHelper.cs') -Raw
# Compile the shipped helper unchanged. Only the game's stat lookup is stubbed;
# live placement/migration checks must additionally use the loaded game DLL.
$taskStubs = @'
namespace RimWorld { public static class StatDefOf { public static readonly object WorkToBuild = new object(); } }
namespace Verse {
    public enum ThingCategory { Building, Item }
    public class ThingDef {
        public string defName;
        public ThingCategory category = ThingCategory.Building;
        public float work;
        public float? stuffWorkOverride;
        public float GetStatValueAbstract(object stat, ThingDef stuff = null) {
            return stuff != null && stuff.stuffWorkOverride.HasValue ? stuff.stuffWorkOverride.Value : work;
        }
    }
}
'@
Add-Type -TypeDefinition ($taskSource + $taskStubs)
$taskCases = 0
function Assert-Instant($taskName, [single]$taskWork, [bool]$taskExpected, $taskCategory = 'Building', $taskStuff = $null) {
    $taskDef = [Verse.ThingDef]::new()
    $taskDef.defName = $taskName
    $taskDef.work = $taskWork
    $taskDef.category = [Verse.ThingCategory]::$taskCategory
    $taskActual = [RIMAPI.Helpers.InstantConstructionHelper]::IsInstantBuilding($taskDef, $taskStuff)
    if ($taskActual -ne $taskExpected) { throw "Instant classification failed: $taskName / $taskWork" }
    $script:taskCases++
}
foreach ($taskName in @('SleepingSpot','DoubleSleepingSpot','AnimalSleepingSpot','ButcherSpot','CraftingSpot',
                        'CaravanPackingSpot','PartySpot','MarriageSpot','MeditationSpot','RitualSpot','PsychicRitualSpot','ModdedInstantMarker')) {
    Assert-Instant $taskName 0 $true
}
Assert-Instant 'SleepingSpot' 10 $false
Assert-Instant 'FreeButRequiresWork' 600 $false
Assert-Instant 'PollutionPump' 2200 $false
Assert-Instant 'InvalidNegativeWork' -1 $false
Assert-Instant 'InvalidNaN' ([single]::NaN) $false
Assert-Instant 'InvalidInfinity' ([single]::PositiveInfinity) $false
Assert-Instant 'ZeroWorkItem' 0 $false 'Item'
$taskStuff = [Verse.ThingDef]::new()
$taskStuff.stuffWorkOverride = 0
Assert-Instant 'MaterialSpecificWork' 100 $true 'Building' $taskStuff
$taskStuff.stuffWorkOverride = 100
Assert-Instant 'MaterialSpecificWork' 0 $false 'Building' $taskStuff
if ([RIMAPI.Helpers.InstantConstructionHelper]::IsInstantBuilding($null)) { throw 'Null def is not a building' }
$taskCases++
foreach ($taskCase in @(@(0,0,0),@(10,0,0),@(4,8,.5),@(8,8,1),@(20,8,1),@(-1,8,0),
                        @([single]::NaN,8,0),@([single]::PositiveInfinity,8,0),
                        @(1,[single]::NaN,0),@(1,[single]::PositiveInfinity,0),@(1,-1,0))) {
    $taskActual = [RIMAPI.Helpers.InstantConstructionHelper]::Progress($taskCase[0],$taskCase[1])
    if ([single]::IsNaN($taskActual) -or [single]::IsInfinity($taskActual) -or $taskActual -ne $taskCase[2]) {
        throw ('Invalid construction progress: ' + ($taskCase -join ','))
    }
    $taskCases++
}
Write-Output "PASS: $taskCases actual native instant-building/progress cases; live placement is a separate gate"
