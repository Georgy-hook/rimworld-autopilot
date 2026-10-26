$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatTeamCareHelper.cs')
$taskStart=$taskSource.IndexOf('    public static class CombatIdleFireMath')
$taskEnd=$taskSource.IndexOf('    public static partial class CombatControlHelper')
$taskCode=@'
using System;
MATH
public static class IdleFireRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  Check(CombatIdleFireMath.Control(true,true,false,false,true,false),"J projectile22158: unsafe unowned native idle bypassed selected fire control and hit a caregiver");
  Check(!CombatIdleFireMath.Control(true,true,false,false,false,true),"K: harmless native idle was unnecessarily reordered, changing the successful rush fire schedule");
  Check(!CombatIdleFireMath.Control(true,true,false,false,true,true),"Safe in-progress native burst was needlessly interrupted");
  Check(!CombatIdleFireMath.Control(true,true,false,false,false,false),"Stale cooldown focus was treated as a prospective unsafe shot");
  Check(!CombatIdleFireMath.Control(false,true,false,false,false,false),"Unselected pawn was commandeered");
  Check(!CombatIdleFireMath.Control(true,false,false,false,false,false),"A manual forced wait was adopted");
  Check(!CombatIdleFireMath.Control(true,true,true,false,false,false),"Later foreign queue was erased");
  Check(!CombatIdleFireMath.Control(true,true,false,true,false,false),"Clinical or recovery actor was diverted");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[IdleFireRegression]::Run()
if($taskSource -notmatch 'var target=firing\?AimTarget\(p\) \?\? selected:selected;'){throw 'Urgent safety still uses stale cooldown focus'}
