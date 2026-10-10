$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskSource = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/QuestOfferBoundary.cs') -Raw
Add-Type -TypeDefinition $taskSource
$taskOffers = @(
    @('', 'v1', $true, $true, $true, 'quest_offer_review_required'),
    @('v1', 'v2', $true, $true, $true, 'quest_offer_changed'),
    @('v1', 'v1', $false, $true, $true, 'quest_not_offered'),
    @('v1', 'v1', $true, $false, $true, 'quest_requirements_not_met_or_expired'),
    @('v1', 'v1', $true, $true, $false, 'quest_accepter_not_eligible'),
    @('v1', 'v1', $true, $true, $true, $null)
)
foreach ($taskCase in $taskOffers) {
    $taskActual = [RIMAPI.Helpers.QuestOfferBoundary]::ValidateOffer($taskCase[0], $taskCase[1], $taskCase[2], $taskCase[3], $taskCase[4])
    if ($taskActual -ne $taskCase[5]) { throw ('Offer boundary failed: ' + ($taskCase -join ',')) }
}
$taskGroups = [System.Collections.Generic.Dictionary[int,int[]]]::new()
$taskGroups.Add(3, [int[]]@(0,1))
$taskGroups.Add(11, [int[]]@(0,1,2))
$taskCases = @(
    @{Rows=''; Error='quest_reward_choice_required'},
    @{Rows='3:0'; Error='quest_reward_choice_required'},
    @{Rows='3:0;3:1;11:2'; Error='quest_reward_binding_duplicate'},
    @{Rows='3:0;12:0'; Error='quest_reward_choice_changed'},
    @{Rows='3:0;11:3'; Error='quest_reward_choice_changed'},
    @{Rows='3:1;11:2'; Error=$null},
    @{Rows='3'; Error='quest_reward_binding_invalid'}
)
foreach ($taskCase in $taskCases) {
    $taskRows = [System.Collections.Generic.List[int[]]]::new()
    if ($taskCase.Rows) {
        foreach ($taskRow in $taskCase.Rows.Split(';')) { $taskRows.Add([int[]]$taskRow.Split(':')) }
    }
    $taskActual = [RIMAPI.Helpers.QuestOfferBoundary]::ValidateRewards($taskGroups, $taskRows)
    if ($taskActual -ne $taskCase.Error) { throw ('Reward boundary failed: ' + $taskCase.Error + ' actual=' + $taskActual) }
}
Write-Output ('PASS: ' + ($taskOffers.Count + $taskCases.Count) + ' actual native quest validation cases; no game started')

# Execute the production method with a small mutation fixture: choosing the
# first group shifts the second group's live Index. This is not a game replay.
$taskHelper = Get-Content -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/QuestOfferHelper.cs') -Raw
$taskMethod = [regex]::Match($taskHelper, 'public static void SelectRewards\(.*?\r?\n        \}', [Text.RegularExpressions.RegexOptions]::Singleline).Value
if (-not $taskMethod) { throw 'Production reward selection method missing' }
$taskFixture = @'
using System;
using System.Collections.Generic;
using System.Linq;
namespace QuestMutationFixture {
 public class Quest { public List<object> PartsListForReading = new List<object>(); }
 public class QuestPart_Choice {
  public Quest quest; public bool choiceUsed; public string selected;
  public List<string> choices = new List<string> { "first", "second" };
  public int Index { get { return quest.PartsListForReading.IndexOf(this); } }
  public void Choose(string value) { selected = value; choiceUsed = true; quest.PartsListForReading.Remove(this); }
 }
 public class QuestRewardSelectionDto { public int PartIndex; public int ChoiceIndex; }
 public class QuestActionRequestDto { public List<QuestRewardSelectionDto> RewardChoices = new List<QuestRewardSelectionDto>(); }
 public static class Harness {
 METHOD
 public static void Run() {
  var q = new Quest(); var first = new QuestPart_Choice { quest=q }; var second = new QuestPart_Choice { quest=q };
  q.PartsListForReading.Add(new object()); q.PartsListForReading.Add(first);
  q.PartsListForReading.Add(new object()); q.PartsListForReading.Add(second);
  var request = new QuestActionRequestDto();
  request.RewardChoices.Add(new QuestRewardSelectionDto { PartIndex=1, ChoiceIndex=1 });
  request.RewardChoices.Add(new QuestRewardSelectionDto { PartIndex=3, ChoiceIndex=1 });
  SelectRewards(q, request);
  if (first.selected != "second" || second.selected != "second") throw new Exception("Shifted part index changed requested reward");
 }
 }
}
'@
Add-Type -TypeDefinition $taskFixture.Replace('METHOD', $taskMethod)
[QuestMutationFixture.Harness]::Run()
Write-Output 'PASS: actual production reward-selection method preserves both choices across index mutation; native signals untested'
