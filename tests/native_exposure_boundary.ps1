$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatExposureHelper.cs')
$taskCode=@'
namespace RimWorld { }
namespace Verse {
 public struct IntVec3 {
  public int x,z;public IntVec3(int a,int b){x=a;z=b;}
  public bool InBounds(Map m)=>x>=0 && z>=0 && x<100 && z<100;
  public static bool operator ==(IntVec3 a,IntVec3 b)=>a.x==b.x && a.z==b.z;
  public static bool operator !=(IntVec3 a,IntVec3 b)=>!(a==b);
  public override bool Equals(object b)=>b is IntVec3 && this==(IntVec3)b;
  public override int GetHashCode()=>x*100+z;
 }
 public struct ShootLine {public IntVec3 Source,Dest;public ShootLine(IntVec3 s,IntVec3 d){Source=s;Dest=d;}}
 public struct IntVec2 {public int x,z;}
 public struct CellRect {public IntVec3 Cell;public static CellRect SingleCell(IntVec3 c)=>new CellRect{Cell=c};}
 public class ThingDef {public IntVec2 size=new IntVec2{x=1,z=1};public bool CanBenefitFromCover=true;}
 public class Thing {public ThingDef def=new ThingDef();public T TryGetComp<T>() where T:class=>Comp as T;public object Comp;}
 public class Pawn:Thing {public Map Map;public IntVec3 Position;public Equipment equipment=new Equipment();}
 public class Equipment {public Thing Primary;}
 public class CompEquippable {public Verb PrimaryVerb;}
 public struct LocalTargetInfo {public IntVec3 Cell;public Pawn Thing;public LocalTargetInfo(IntVec3 c){Cell=c;Thing=null;}public LocalTargetInfo(Pawn p){Cell=p.Position;Thing=p;}}
 public class VerbProperties {public bool requireLineOfSight=true;}
 public class Verb {
  public VerbProperties verbProps=new VerbProperties();public int Range=30,Calls;public bool PawnHit,CellHit;
  public System.Func<IntVec3,IntVec3,bool> Hit=(a,b)=>false;
  public bool CanHitTargetFrom(IntVec3 from,LocalTargetInfo target)=>target.Thing!=null?PawnHit:CellHit;
  public bool TryFindShootLineFromTo(IntVec3 from,LocalTargetInfo target,out ShootLine line){line=new ShootLine(from,target.Cell);return target.Thing!=null?PawnHit:CellHit;}
  public bool OutOfRange(IntVec3 from,LocalTargetInfo target,CellRect rect)=>System.Math.Abs(from.x-rect.Cell.x)>Range;
  private bool CanHitCellFromCellIgnoringRange(IntVec3 from,IntVec3 to,bool full){Calls++;return Hit(from,to);}
 }
 public class Map {public System.Func<IntVec3,IntVec3,System.Collections.Generic.List<IntVec3>> Lean=(a,b)=>new System.Collections.Generic.List<IntVec3>{a};}
 public static class ShootLeanUtility {
  public static void LeanShootingSourcesFromTo(IntVec3 from,IntVec3 to,Map m,System.Collections.Generic.List<IntVec3> list){list.Clear();list.AddRange(m.Lean(from,to));}
 }
 public static class CoverUtility {public static float CalculateOverallBlockChance(LocalTargetInfo target,IntVec3 from,Map m)=>.5f;}
}
public static class ExposureBoundary {
 static int count;static void Check(bool value,string text){count++;if(!value)throw new System.Exception(text);}
 static Verse.IntVec3 Cell(int x,int z=10)=>new Verse.IntVec3(x,z);
 public static int Run(){
  var map=new Verse.Map();var verb=new Verse.Verb{PawnHit=true,CellHit=false};
  var threat=new Verse.Pawn{Map=map,Position=Cell(20)};threat.equipment.Primary=new Verse.Thing{Comp=new Verse.CompEquippable{PrimaryVerb=verb}};
  var target=new Verse.Pawn{Map=map,Position=Cell(10)};
  Check(RIMAPI.Helpers.CombatExposureHelper.Lane(threat,target,target.Position,threat.Position)==.5f,"Pawn-only native firing lane was reported as protected");
  verb.PawnHit=false;
  Check(RIMAPI.Helpers.CombatExposureHelper.Lane(threat,target,target.Position,threat.Position)==0,"A blocked current pawn was reported exposed");
  verb.Hit=(a,b)=>a==Cell(20) && b==Cell(12,11);
  map.Lean=(a,b)=>a==Cell(12)?new System.Collections.Generic.List<Verse.IntVec3>{Cell(12,11)}:new System.Collections.Generic.List<Verse.IntVec3>{a};
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(verb,Cell(20),Cell(12),map)==true,"Target leaning was omitted from the future position");
  Check(RIMAPI.Helpers.CombatExposureHelper.Lane(threat,target,Cell(12),Cell(20))==.5f,"Future Pawn lane did not use native leaning");
  map.Lean=(a,b)=>a==Cell(20)?new System.Collections.Generic.List<Verse.IntVec3>{Cell(20,11)}:
    a==Cell(12) && b==Cell(20,11)?new System.Collections.Generic.List<Verse.IntVec3>{Cell(12,11)}:new System.Collections.Generic.List<Verse.IntVec3>{a};
  verb.Hit=(a,b)=>a==Cell(20,11) && b==Cell(12,11);verb.Calls=0;
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(verb,Cell(20),Cell(12),map)==true,"Shooter and target simultaneous leaning was omitted");
  Check(verb.Calls==2,"Native root-first check or early success bound was lost");
  verb.Range=3;verb.Calls=0;
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(verb,Cell(20),Cell(12),map)==false && verb.Calls==0,"Leaning extended native root range");
  verb.verbProps.requireLineOfSight=false;
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(verb,Cell(20),Cell(12),map)==false,"No-LOS weapon ignored native range");
  verb.Range=30;
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(verb,Cell(20),Cell(12),map)==true,"No-LOS native weapon acquired a fake LOS gate");
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(null,Cell(20),Cell(12),map)==null,"Missing native verb was assumed protected");
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitCandidate(verb,Cell(20),Cell(-1),map)==null,"Out-of-map candidate was assumed protected");
  verb.verbProps.requireLineOfSight=true;verb.PawnHit=true;verb.CellHit=false;
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitPawnAt(verb,target,Cell(20),target.Position)==true,"Current native Pawn geometry was replaced by the empty-cell branch");
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitPawnAt(verb,target,Cell(20),Cell(12))==true,"Observed future Pawn lost simultaneous native shooter/target lean");
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitPawnAt(null,target,Cell(20),Cell(12))==null,"Unknown future verb became a proved firing line");
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitPawnAt(verb,null,Cell(20),Cell(12))==null,"Missing target acquired geometry");
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitPawnAt(verb,target,Cell(-1),Cell(12))==null,"Out-of-map shooter acquired future geometry");
  Check(RIMAPI.Helpers.CombatExposureHelper.TryPawnShootLine(verb,target,Cell(20),target.Position,out var nativeLine)==true
    && nativeLine.Source==Cell(20) && nativeLine.Dest==target.Position,"Actual Pawn line was replaced by hypothetical empty-cell geometry");
  Check(RIMAPI.Helpers.CombatExposureHelper.TryPawnShootLine(verb,target,Cell(20),Cell(12),out var leanLine)==true
    && leanLine.Source==Cell(20,11) && leanLine.Dest==Cell(12,11),"Future Pawn line lost the checked simultaneous native lean endpoints");
  Check(RIMAPI.Helpers.CombatExposureHelper.TryPawnShootLine(null,target,Cell(20),Cell(12),out _)==null,"Missing native verb invented a future line");
  verb.Range=3;
  Check(RIMAPI.Helpers.CombatExposureHelper.TryPawnShootLine(verb,target,Cell(20),Cell(12),out _)==false,"Future lean endpoints extended native root range");
  verb.Range=30;
  target.def.size.x=2;
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitPawnAt(verb,target,Cell(20),Cell(12))==null,"Unmodeled multi-cell future footprint acquired a proved shot");
  Check(RIMAPI.Helpers.CombatExposureHelper.CanHitPawnAt(verb,target,Cell(20),target.Position)==true,"Multi-cell current target lost its exact native Thing branch");
  Check(float.IsPositiveInfinity(RIMAPI.Helpers.CombatExposureHelper.Lane(threat,target,Cell(12),Cell(20))),"Unsupported multi-cell future target was assumed protected");
  Check(target.Position==Cell(10) && threat.Position==Cell(20),"Exposure inspection moved a real pawn");
  return count;
 }
}
'@
Add-Type -TypeDefinition ("using System;using System.Collections.Generic;using System.Reflection;using System.Reflection.Emit;using RimWorld;using Verse;`n"+$taskCode+$taskSource.Replace('using System;','').Replace('using System.Collections.Generic;','').Replace('using System.Reflection;','').Replace('using System.Reflection.Emit;','').Replace('using RimWorld;','').Replace('using Verse;','')) -Language CSharp
[ExposureBoundary]::Run()
