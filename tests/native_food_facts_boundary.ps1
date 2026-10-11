$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Models/Common/ThingDto.cs') -Raw
$taskStart = $taskSource.IndexOf('public static void SetFoodFacts')
if ($taskStart -lt 0) { throw 'Production food mapper missing' }
$taskOpen = $taskSource.IndexOf('{', $taskStart)
$taskDepth = 1
$taskEnd = $taskOpen + 1
while ($taskDepth -gt 0 -and $taskEnd -lt $taskSource.Length) {
    if ($taskSource[$taskEnd] -eq '{') { $taskDepth++ }
    if ($taskSource[$taskEnd] -eq '}') { $taskDepth-- }
    $taskEnd++
}
$taskMethod = $taskSource.Substring($taskStart, $taskEnd - $taskStart)
$taskResources = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/ResourcesHelper.cs') -Raw
if ($taskSource -notmatch 'SetFoodFacts\(dto, thing\);' -or $taskResources -notmatch 'ThingDto.SetFoodFacts\(dto, thing\);') {
    throw 'Both thing observation routes must invoke the tested food mapper'
}
$taskStubs = @'
namespace RimWorld { public enum RotStage { Fresh, Rotting, Dessicated } }
public class Thing { public CompRottable Rot; public T TryGetComp<T>() where T:class { return Rot as T; } }
public class CompRottable { public RimWorld.RotStage Stage; public int TicksUntilRotAtCurrentTemp; }
public class RaceProperties { public bool Animal; public bool IsFlesh; }
public class Pawn { public int thingIDNumber; public RaceProperties RaceProps = new RaceProperties(); }
public class Corpse:Thing { public Pawn InnerPawn; public int timeOfDeath; }
public class ThingDto { public string RotStage; public int? TicksUntilRot; public int? CorpseInnerPawnId;
 public int? CorpseDeathTick; public bool? CanButcher;
'@
Add-Type -TypeDefinition ($taskStubs + $taskMethod + '}')
$taskCount = 0
foreach ($taskStage in @('Fresh', 'Rotting', 'Dessicated')) {
    foreach ($taskAnimal in @($true, $false)) {
        $taskCorpse = New-Object Corpse
        $taskCorpse.InnerPawn = New-Object Pawn
        $taskCorpse.InnerPawn.thingIDNumber = 91
        $taskCorpse.InnerPawn.RaceProps.Animal = $taskAnimal
        $taskCorpse.InnerPawn.RaceProps.IsFlesh = $true
        $taskCorpse.timeOfDeath = 1234
        $taskCorpse.Rot = New-Object CompRottable
        $taskCorpse.Rot.Stage = [RimWorld.RotStage]::$taskStage
        $taskCorpse.Rot.TicksUntilRotAtCurrentTemp = 900
        $taskDto = New-Object ThingDto
        [ThingDto]::SetFoodFacts($taskDto, $taskCorpse)
        if ($taskDto.RotStage -ne $taskStage -or $taskDto.CorpseInnerPawnId -ne 91 -or $taskDto.CorpseDeathTick -ne 1234 -or
            $taskDto.CanButcher -ne ($taskAnimal -and $taskStage -eq 'Fresh')) { throw 'Corpse food classification failed' }
        $taskCount++
    }
}
$taskDto = New-Object ThingDto
[ThingDto]::SetFoodFacts($taskDto, (New-Object Thing))
if ($taskDto.CanButcher -or $null -ne $taskDto.CorpseInnerPawnId -or $null -ne $taskDto.RotStage) { throw 'Unknown thing became food' }
$taskCount++
Write-Output ('PASS: ' + $taskCount + ' production food mapper cases and both route bindings; no game orders')
