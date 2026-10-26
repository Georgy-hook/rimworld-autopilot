$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatFallbackCohortHelper.cs')
$taskFrom=$taskSource.IndexOf('        private static bool CohortGunFreeFor(')
$taskTo=$taskSource.IndexOf('        private static Pawn CohortCoverTarget', $taskFrom)
$taskCode=@'
using System;
using System.Collections.Generic;
public sealed class Pawn {}
public sealed class Transfer {public Pawn Mover,Enemy;public bool Active;}
public static class ActualCoverLeaseRegression {
 static Dictionary<Pawn,Transfer> CoverTransfers=new Dictionary<Pawn,Transfer>();
 static bool KeepTransferredCover(Pawn gun,Pawn unused)=>CoverTransfers.TryGetValue(gun,out var c)&&c.Active;
 static bool ActiveCoverTransfer(Pawn gun,Transfer transfer)=>transfer.Active;
 ACTUAL
 public static int Run(){
  var gun=new Pawn();var first=new Pawn();var next=new Pawn();var enemy=new Pawn();var other=new Pawn();
  if(!CohortGunFreeFor(gun,next,other))throw new Exception("Free gun unavailable");
  CoverTransfers[gun]=new Transfer{Mover=first,Enemy=enemy,Active=true};
  if(CohortGunFreeFor(gun,next,other))throw new Exception("Q: pending cover asked a gun to abandon its real in-flight mover");
  if(CohortGunFreeFor(gun,next,enemy))throw new Exception("Same enemy overwrote another exact mover lease");
  if(!CohortGunFreeFor(gun,first,enemy))throw new Exception("Exact retained handoff was not idempotent");
  if(CohortGunFreeFor(gun,first,other))throw new Exception("Same mover silently changed its covering enemy");
  CoverTransfers[gun].Active=false;
  if(!CohortGunFreeFor(gun,next,other))throw new Exception("Completed or invalid native cover did not release gun");
  return 6;
 }
}
'@
$taskCode=$taskCode.Replace('ACTUAL',$taskSource.Substring($taskFrom,$taskTo-$taskFrom))
Add-Type -TypeDefinition $taskCode -Language CSharp
[ActualCoverLeaseRegression]::Run()
if(([regex]::Matches($taskSource,'CohortGunFreeFor\(')).Count -ne 4){throw 'Opening, new and retained pending gun admission must all check the real cover lease'}
