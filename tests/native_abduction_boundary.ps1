$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatNativeHelper.cs')
$taskStart=$taskSource.IndexOf('public static bool AbductionThreat(')
$taskEnd=$taskSource.IndexOf('public static bool ActiveStructure(', $taskStart)
$taskMethod=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;
public class Faction {public static Faction OfPlayer=new Faction();}
public class Cell {public bool fog;public bool Fogged(object map)=>fog;}
public class Def {public string defName;}
public class Target {public object Thing;}
public class Job {public Def def;public Target targetA=new Target();}
public class Pawn {
 public bool Dead,Downed,Spawned=true,Hostile,Carrier;
 public object Map;public Faction Faction;public Cell Position=new Cell();public Job CurJob;
 public Def CurJobDef=>CurJob?.def;
}
public static class CombatNativeHelper {
 static bool IsPlayerThreat(Pawn p)=>p.Hostile;
 static bool Kidnapper(Pawn p)=>p.Carrier;
 METHOD
}
public static class AbductionRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 static Pawn Attempt(){var map=new object();return new Pawn{Map=map,Hostile=true,
  CurJob=new Job{def=new Def{defName="Kidnap"},targetA=new Target{Thing=new Pawn{Map=map,Faction=Faction.OfPlayer,Downed=true}}}};}
 public static int Run(){
  var p=Attempt();Check(CombatNativeHelper.AbductionThreat(p),"Native pickup attempt was ignored until the victim was already carried");
  p=Attempt();((Pawn)p.CurJob.targetA.Thing).Downed=false;Check(!CombatNativeHelper.AbductionThreat(p),"Standing unrelated target became a pickup emergency");
  p=Attempt();((Pawn)p.CurJob.targetA.Thing).Dead=true;Check(!CombatNativeHelper.AbductionThreat(p),"Corpse hauling became colonist kidnapping");
  p=Attempt();((Pawn)p.CurJob.targetA.Thing).Faction=new Faction();Check(!CombatNativeHelper.AbductionThreat(p),"Foreign patient became our colonist");
  p=Attempt();((Pawn)p.CurJob.targetA.Thing).Map=new object();Check(!CombatNativeHelper.AbductionThreat(p),"Different-map target authorized local interception");
  p=Attempt();((Pawn)p.CurJob.targetA.Thing).Spawned=false;Check(!CombatNativeHelper.AbductionThreat(p),"Missing uncarried target counted as a pickup attempt");
  p=Attempt();p.CurJob.def.defName="Goto";Check(!CombatNativeHelper.AbductionThreat(p),"Movement target alone fabricated kidnapping intent");
  p=Attempt();p.CurJob.targetA.Thing=new object();Check(!CombatNativeHelper.AbductionThreat(p),"Non-pawn cargo became a patient");
  p=Attempt();p.Hostile=false;Check(!CombatNativeHelper.AbductionThreat(p),"Friendly rescuer treated as hostile");
  p=Attempt();p.Dead=true;Check(!CombatNativeHelper.AbductionThreat(p),"Dead raider retained pickup intent");
  p=Attempt();p.Downed=true;Check(!CombatNativeHelper.AbductionThreat(p),"Downed raider retained pickup intent");
  p=Attempt();p.Spawned=false;Check(!CombatNativeHelper.AbductionThreat(p),"Off-map raider retained pickup intent");
  p=Attempt();p.Position.fog=true;Check(!CombatNativeHelper.AbductionThreat(p),"Unobserved fogged job authorized interception");
  p=Attempt();p.CurJob=null;Check(!CombatNativeHelper.AbductionThreat(p),"Unknown job fabricated pickup intent");
  p=Attempt();p.Map=null;Check(!CombatNativeHelper.AbductionThreat(p),"Missing map authorized interception");
  p=Attempt();p.Carrier=true;p.CurJob=null;Check(CombatNativeHelper.AbductionThreat(p),"Existing independently verified carrier lost its priority");
  return n;
 }
}
'@
Add-Type -TypeDefinition ($taskCode.Replace('METHOD',$taskMethod)) -Language CSharp
[AbductionRegression]::Run()
