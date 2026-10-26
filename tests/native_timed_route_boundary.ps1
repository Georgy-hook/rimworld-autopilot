$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatTimedRouteMath.cs')
$taskTests=@'
public static class TimedRouteBoundary {
 static int count;
 static void Check(bool v,string reason){count++;if(!v)throw new System.Exception(reason);}
 static RIMAPI.Helpers.CombatTimedPoint P(float x,float z,float t)=>new RIMAPI.Helpers.CombatTimedPoint(x,z,t);
 static bool Near(float a,float b)=>System.Math.Abs(a-b)<.001f;
 public static int Run(){
  var a=new[]{P(0,0,0),P(10,0,10)};var b=new[]{P(5,-5,0),P(5,5,10)};
  var r=RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,0,10);
  Check(r.Valid && Near(r.Minimum,0) && Near(r.MinimumAt,5),"Crossing between native path nodes was missed");
  Check(Near(r.Maximum,(float)System.Math.Sqrt(50)),"Separation maximum was not at interval endpoints");
  b=new[]{P(0,6,0),P(10,6,10)};r=RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,0,10);
  Check(r.Valid && Near(r.Minimum,6) && Near(r.Maximum,6),"Parallel safe corridor was falsely crossing");
  r=RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,3,7);
  Check(r.Valid && Near(r.Minimum,6),"Interior segment bounds lost native travel timing");
  a=new[]{P(0,0,0)};b=new[]{P(20,0,0),P(10,0,10)};r=RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,0,10);
  Check(r.Valid && Near(r.Minimum,10) && Near(r.Maximum,20),"Arrival hold did not preserve stationary firing cell");
  Check(!RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,0,11).Valid,"Unknown target motion after observed endpoint was extrapolated");
  Check(!RIMAPI.Helpers.CombatTimedRouteMath.Separation(null,b,0,1).Valid,"Missing actor route acquired safety");
  Check(!RIMAPI.Helpers.CombatTimedRouteMath.Separation(new[]{P(0,0,1)},b,0,1).Valid,"Route without an observed origin acquired safety");
  Check(!RIMAPI.Helpers.CombatTimedRouteMath.Separation(new[]{P(0,0,0),P(1,0,0)},b,0,1).Valid,"Duplicate path times acquired a velocity");
  Check(!RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,2,1).Valid,"Reversed interval acquired safety");
  Check(!RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,0,float.NaN).Valid,"NaN time acquired safety");
  a=new[]{P(0,0,0),P(0,0,5),P(10,0,10)};b=new[]{P(5,0,0),P(5,0,10)};r=RIMAPI.Helpers.CombatTimedRouteMath.Separation(a,b,0,10);
  Check(r.Valid && Near(r.MinimumAt,7.5f) && Near(r.Minimum,0),"Loaded initial movement lock was ignored");
  return count;
 }
}
'@
Add-Type -TypeDefinition ($taskSource.Replace('#if LAYA_COMBAT_LAB','').Replace('#endif','')+$taskTests) -Language CSharp
[TimedRouteBoundary]::Run()
