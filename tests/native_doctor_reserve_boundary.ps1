$ErrorActionPreference='Stop'
$taskBase=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'
$taskReserve=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatDoctorReserveHelper.cs')
$taskMath=$taskReserve.Substring($taskReserve.IndexOf('    public static class CombatDoctorReserveMath'),$taskReserve.IndexOf('    public static partial class CombatControlHelper')-$taskReserve.IndexOf('    public static class CombatDoctorReserveMath'))
$taskGuard=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatFireDoctorGuardHelper.cs')
$taskStart=$taskGuard.IndexOf('        private static bool PreserveDoctorPosition(')
$taskEnd=$taskGuard.IndexOf('        // Native Wait_Combat', $taskStart)
$taskMethod=$taskGuard.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;
using System.Linq;
using System.Collections.Generic;
MATH
public struct IntVec3 {public int x,z;public IntVec3(int x,int z){this.x=x;this.z=z;}public bool InBounds(Map m)=>true;public float DistanceTo(IntVec3 b)=>(float)Math.Sqrt((x-b.x)*(x-b.x)+(z-b.z)*(z-b.z));}
public sealed class Map {public Pawns mapPawns=new Pawns();}
public sealed class Pawns {public List<Pawn> AllPawnsSpawned=new List<Pawn>();}
public sealed class Equipment {public Thing Primary;}
public sealed class Thing {public Def def=new Def();}
public sealed class Def {public bool IsRangedWeapon;}
public static class JobDefOf {public static readonly object Goto=new object(),Wait_Combat=new object();}
public sealed class Pawn {public bool IsDoctor=true,Reserved=true,Danger,Enemy,Melee,Abduction,Owned;public object CurJobDef,CurJob;public IntVec3 Position;public Map Map=new Map();public Equipment equipment;public float CurrentExposure,ProposedExposure,CurrentForecast,ProposedForecast;}
public static class CombatOrderHelper {public static bool Owned(Pawn p,object j)=>p.Owned;}
public static class CombatNativeHelper {public static bool AbductionThreat(Pawn p)=>p.Abduction;}
public static class RealDoctorReserveRegression {
 static int n;
 static void Check(bool b,string why){n++;if(!b)throw new Exception(why);}
 static bool NativeDoctor(Pawn p)=>p.IsDoctor;
 static bool IsReservedDoctor(Pawn p)=>p.Reserved;
 static bool TeamImmediateDanger(Pawn p)=>p.Danger;
 static bool Threat(Pawn p)=>p.Enemy;
 static bool MeleeThreat(Pawn p)=>p.Melee;
 static void TeamEvent(string r,Pawn p){}
 static float IncomingRangedExposure(Pawn p,IntVec3 c)=>c.x==p.Position.x && c.z==p.Position.z?p.CurrentExposure:p.ProposedExposure;
 static float DoctorProjectedExposure(Pawn p,IntVec3 c,float h)=>c.x==p.Position.x && c.z==p.Position.z?p.CurrentForecast:p.ProposedForecast;
METHOD
 public static int Run(){
  var p=new Pawn{Position=new IntVec3(113,113),CurJobDef=JobDefOf.Goto,CurJob=new object(),Owned=true};
  var enemy=new Pawn{Position=new IntVec3(118,118),Enemy=true,Melee=true};p.Map.mapPawns.AllPawnsSpawned.Add(enemy);
  Check(PreserveDoctorPosition(p,new IntVec3(115,114)),"U physician forward support bypassed protection because current job was Goto");
  p.Owned=false;p.CurJobDef=JobDefOf.Wait_Combat;
  Check(PreserveDoctorPosition(p,new IntVec3(115,114)),"Unowned native idle bypassed the physician's placement role");
  Check(!PreserveDoctorPosition(p,new IntVec3(111,113)),"A genuine rear exit was blocked as forward support");
  p.Danger=true;Check(!PreserveDoctorPosition(p,new IntVec3(115,114)),"Position preference vetoed an independently checked immediate emergency");p.Danger=false;
  enemy.Abduction=true;Check(!PreserveDoctorPosition(p,new IntVec3(115,114)),"Position preference replaced the existing kidnapping interception checks");enemy.Abduction=false;
  p.IsDoctor=false;Check(!PreserveDoctorPosition(p,new IntVec3(115,114)),"Role guard commanded a protected/nonmedical actor");p.IsDoctor=true;
  enemy.Melee=false;enemy.equipment=new Equipment{Primary=new Thing{def=new Def{IsRangedWeapon=true}}};
  p.CurrentForecast=0;p.ProposedForecast=2;
  Check(PreserveDoctorPosition(p,new IntVec3(111,113)),"Current zero exposure hid a known future firing lane");
  p.CurrentForecast=2;p.ProposedForecast=0;
  Check(!PreserveDoctorPosition(p,new IntVec3(111,113)),"A safer projected medical position was blocked");
  Check(CombatDoctorReserveMath.Early(0,2),"Current cover prevented all review of an observed approaching flank");
  Check(!CombatDoctorReserveMath.Early(2,2),"Already exposed doctor was removed from the existing urgent withdrawal handler");
  Check(!CombatDoctorReserveMath.Early(0,0),"No observed threat authorized an optional move");
  foreach(float x in new[]{float.NaN,float.PositiveInfinity,-1f}){
   Check(!CombatDoctorReserveMath.Early(0,x),"Unknown projection became a known flank");
   Check(CombatDoctorReserveMath.Worse(0,x),"Unknown proposal bypassed position protection");
  }
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskMath).Replace('METHOD',$taskMethod)
Add-Type -TypeDefinition $taskCode -Language CSharp
[RealDoctorReserveRegression]::Run()
$taskControl=Get-Content -Raw -LiteralPath (Join-Path $taskBase 'CombatControlHelper.cs')
if($taskControl -notmatch 'ReviewDoctorPreposition\(\);'){throw 'Early medical review is not connected'}
if($taskReserve -notmatch 'ReviewEscapeCells\(p,key,"doctor_early_position",cells,2\)'){throw 'Medical warning search has no completing finite page'}
if($taskReserve -match 'FindPathNow|ReleaseToPool|\.Reset\(|Rand\.'){throw 'Medical positioning bypasses native cooldown or detached path ownership'}
