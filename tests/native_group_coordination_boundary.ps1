$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatGroupCoordinationHelper.cs')
$taskStart=$taskSource.IndexOf('        public static bool KeepFire(')
$taskEnd=$taskSource.IndexOf('    public static partial class', $taskStart)
$taskCover=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatCoverTurnHelper.cs')
$taskMathStart=$taskCover.IndexOf('    public static class CombatCoverTurnMath')
$taskMathEnd=$taskCover.IndexOf('    // Native route proofs')
$taskCode=@'
using System;
COVER
public static class GroupCoordinationSubject {
METHOD
public static class Regression {
 public static int Run(){
  int n=0;
  // Rush: a legal shot exists at the old cell, another gun needs cover.
  if(!GroupCoordinationSubject.KeepFire(false,false,true,true,false,false))throw new Exception("Forward support discards an already available shot");n++;
  // Ranged: a second healthy rotation must wait for the first gun's arrival.
  if(!GroupCoordinationSubject.KeepFire(false,true,false,true,true,false))throw new Exception("Both covering guns rotate simultaneously");n++;
  // Do not strand a healthy supporter beyond every other gun's reach.
  if(!GroupCoordinationSubject.KeepFire(false,false,false,false,false,true))throw new Exception("Optional move leaves the supporting cohort");n++;
  // This is not a blanket movement ban: open a blocked lateral lane or cover.
  if(GroupCoordinationSubject.KeepFire(false,false,true,false,false,false))throw new Exception("An otherwise checked blocked-lane approach was banned");n++;
  if(GroupCoordinationSubject.KeepFire(false,false,true,true,true,false))throw new Exception("A checked improving cover move was banned");n++;
  for(int bits=0;bits<32;bits++){
   if(GroupCoordinationSubject.KeepFire(true,(bits&1)!=0,(bits&2)!=0,(bits&4)!=0,(bits&8)!=0,(bits&16)!=0))
    throw new Exception("Cohort guard overrode a separately checked emergency exit");n++;
  }
  if(!GroupCoordinationSubject.RejoinFits(false,false,true,400,75,20,108))throw new Exception("Arrival immediately lost its safe first burst");n++;
  if(GroupCoordinationSubject.RejoinFits(false,false,true,180,75,20,108))throw new Exception("Rejoin waited past its own escape deadline");n++;
  if(GroupCoordinationSubject.RejoinFits(false,false,true,float.PositiveInfinity,75,20,108))throw new Exception("Unknown contact licensed holding");n++;
  if(GroupCoordinationSubject.RejoinFits(true,false,true,400,75,20,108))throw new Exception("A wounded exit was blocked");n++;
  if(GroupCoordinationSubject.RejoinFits(false,true,true,400,75,20,108))throw new Exception("Real first projectile failed to release rejoin");n++;
  if(GroupCoordinationSubject.RejoinFits(false,false,false,400,75,20,108))throw new Exception("Blocked/absent shot trapped the gun");n++;
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('COVER',$taskCover.Substring($taskMathStart,$taskMathEnd-$taskMathStart))
$taskCode=$taskCode.Replace('METHOD',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[Regression]::Run()
