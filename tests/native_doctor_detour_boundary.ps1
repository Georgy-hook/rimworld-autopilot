$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatDoctorDetourHelper.cs')
$taskMath=$taskSource.Substring($taskSource.IndexOf('    public static class CombatDoctorDetourMath'),$taskSource.IndexOf('    public static partial class CombatControlHelper')-$taskSource.IndexOf('    public static class CombatDoctorDetourMath'))
$taskStart=$taskSource.IndexOf('        private static CombatPathBudgetHelper.Observation JoinDoctorRoute(')
$taskEnd=$taskSource.IndexOf('        private static bool TryDoctorDetour(', $taskStart)
$taskJoin=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;
using System.Linq;
using System.Collections.Generic;
MATH
public sealed class Pawn {public int Position;}
public static class CombatPathBudgetHelper {
 public sealed class Observation {
  public readonly bool Found;public readonly float TotalCost;public readonly int[] NodesReversed;
  public Observation(bool f,float c,IEnumerable<int> n){Found=f;TotalCost=c;NodesReversed=n.ToArray();}
 }
}
public static class RealJoinRegression {
 static int n;
 static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 static IEnumerable<int> RemainingRangedCells(Pawn p,CombatPathBudgetHelper.Observation o)=>o.NodesReversed.Reverse().SkipWhile(c=>c==p.Position);
JOIN
 public static int Run(){
  var p=new Pawn{Position=0};
  var a=new CombatPathBudgetHelper.Observation(true,30,new[]{2,1,0});
  var b=new CombatPathBudgetHelper.Observation(true,40,new[]{4,3,2});
  var result=JoinDoctorRoute(p,a,b,false);
  Check(result.Found && result.TotalCost==70,"Two native legs were not one finite observation");
  Check(result.NodesReversed.SequenceEqual(new[]{4,3,2,1,0}),"Waypoint was skipped or the route was reordered");
  Check(a.NodesReversed.SequenceEqual(new[]{2,1,0}) && b.NodesReversed.SequenceEqual(new[]{4,3,2}),"Borrowed/copied route data was modified");
  p.Position=1;var left=new CombatPathBudgetHelper.Observation(true,15,new[]{2,1});
  var continued=JoinDoctorRoute(p,left,b,true);
  Check(continued.NodesReversed.SequenceEqual(new[]{4,3,2,1}),"Remaining native cursor restarted the completed first step");
  Check(!JoinDoctorRoute(p,left,new CombatPathBudgetHelper.Observation(false,0,new int[0]),true).Found,"Missing second path became a complete corridor");
  Check(CombatDoctorDetourMath.Keep(true,false,false,false,false,false,200),"Exact accepted first leg was lost during native motion");
  Check(CombatDoctorDetourMath.Keep(false,false,true,true,false,false,200),"Native arrival could not transition to a rechecked second leg");
  Check(!CombatDoctorDetourMath.Keep(false,false,true,false,false,false,200),"A later manual job was treated as ordinary idle");
  Check(!CombatDoctorDetourMath.Keep(true,false,false,false,true,false,200),"Foreign queue was ignored");
  Check(!CombatDoctorDetourMath.Keep(true,false,false,false,false,true,200),"Clinical job was overridden");
  Check(!CombatDoctorDetourMath.Keep(true,false,false,false,false,false,601),"Finite corridor intent became an endless hold");
  Check(!CombatDoctorDetourMath.Keep(false,false,false,true,false,false,200),"An unrelated idle position was called waypoint arrival");
  Check(CombatDoctorDetourMath.Keep(false,true,false,false,false,false,200),"An exact queued native first leg was discarded before cooldown ended");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskMath).Replace('JOIN',$taskJoin)
Add-Type -TypeDefinition $taskCode -Language CSharp
[RealJoinRegression]::Run()
if($taskSource -match 'FindPathNow|ReleaseToPool|jobQueue\.Clear|\.Reset\(|Rand\.'){throw 'Detour bypasses detached paths, ownership or native cooldown'}
if($taskSource -notmatch 'SaferRangedRoute\(p,joined,false,out _,via\)' -or $taskSource -notmatch 'SaferRangedRoute\(p,tail,false,out _\)'){throw 'A leg is executed without whole-route and fresh tail checks'}
if($taskSource -notmatch 'ReviewEscapeCells\(p,key,"doctor_two_leg",vias,1\)'){throw 'The bounded detour page cannot complete inside the unchanged path quota'}
