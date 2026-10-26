$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatCoverTurnHelper.cs')
$taskMathStart=$taskSource.IndexOf('    public static class CombatCoverTurnMath')
$taskMathEnd=$taskSource.IndexOf('    // Native route proofs')
$taskCursorStart=$taskSource.IndexOf('        private sealed class EscapeSearch')
$taskCursorEnd=$taskSource.IndexOf('        private sealed class CoverTurn')
$taskCode=@'
using System;
using System.Collections.Generic;
using System.Linq;
MATH
public struct IntVec3 {
 public int x;public IntVec3(int v){x=v;}
 public static bool operator==(IntVec3 a,IntVec3 b)=>a.x==b.x;
 public static bool operator!=(IntVec3 a,IntVec3 b)=>a.x!=b.x;
 public override bool Equals(object o)=>o is IntVec3 v && v==this;
 public override int GetHashCode()=>x;
}
public sealed class Pawn {public IntVec3 Position=new IntVec3(0);}
public static class Find {public static TickManager TickManager=new TickManager();}
public sealed class TickManager {public int TicksGame=1;}
public static class CursorSubject {
CURSOR
 public static IEnumerable<IntVec3> Review(Pawn p,Pawn t,IEnumerable<IntVec3> cells)=>ReviewEscapeCells(p,t,"test",cells);
}
public static class CoverTurnRegression {
 static int count;static void Check(bool ok,string why){count++;if(!ok)throw new Exception(why);}
 public static int Run(){
 // Counterexample to the former two-complete-cycle cover requirement: one
 // actual short burst fits, while the helper still keeps its own escape time.
 Check(CombatCoverTurnMath.CoverBurstFits(211,32,21,107),"A measured short covering burst lost its own escape margin");
 Check(!CombatCoverTurnMath.CoverBurstFits(190,32,21,107),"Equality at the last escape boundary authorized another hold");
 Check(!CombatCoverTurnMath.CoverBurstFits(120,32,21,107),"Cover held a gun past its own contact deadline");
 Check(!CombatCoverTurnMath.CoverBurstFits(float.NaN,0,0,0),"Unknown contact became useful cover");
 Check(!CombatCoverTurnMath.CoverBurstFits(300,float.PositiveInfinity,0,0),"Unavailable native aim duration became a ready gun");
 // Retained ranged counterexample: travel589.9999 versus holding589.871,
 // terminal hard shelter0 versus continuing exposure1.576. The same finite
 // post-arrival cycle changes the comparison without inventing a heal.
 Check(CombatCoverTurnMath.ProtectedArrivalImproves(589.9999f,589.871f,0,1.576f,374.2835f,175),"Protected arrival benefit was truncated at the end of travel");
 Check(!CombatCoverTurnMath.ProtectedArrivalImproves(590,590,.5f,1.576f,374,175),"An exposed destination was called hard shelter");
 Check(!CombatCoverTurnMath.ProtectedArrivalImproves(1100,590,0,1.576f,374,175),"Excess crossing exposure was hidden by protected arrival");
 Check(!CombatCoverTurnMath.ProtectedArrivalImproves(590,590,0,1.576f,374,0),"Zero post-arrival observation fabricated an advantage");
 Check(!CombatCoverTurnMath.ProtectedArrivalImproves(590,590,float.PositiveInfinity,1.576f,374,175),"Unknown native endpoint exposure authorized an escape");
 Check(!CombatCoverTurnMath.ProtectedArrivalImproves(590,float.NaN,0,1.576f,374,175),"Unknown staying exposure authorized an escape");
 var pawn=new Pawn();var enemy=new Pawn();var cells=Enumerable.Range(0,12).Select(x=>new IntVec3(x)).ToArray();
 using(var e=CursorSubject.Review(pawn,enemy,cells).GetEnumerator()){
  Check(e.MoveNext() && e.Current.x==0,"Fresh search did not start at the first candidate");
  Check(e.MoveNext() && e.Current.x==1,"Completed rejection did not advance the cursor");
  // An incomplete candidate is abandoned here, like a BudgetDeferred unwind.
 }
 var next=CursorSubject.Review(pawn,enemy,cells).ToArray();
 Check(next.Length==8 && next.First().x==1 && next.Last().x==8,"Deferred review retried the rejected prefix or skipped the incomplete candidate");
 Check(CursorSubject.Review(pawn,enemy,cells).First().x==9,"Next bounded review restarted the first eight rejected candidates");
 pawn.Position=new IntVec3(7);
 Check(CursorSubject.Review(pawn,enemy,new[]{new IntVec3(50)}).First().x==50,"Changed native origin retained stale search order");
 Check(CursorSubject.Review(pawn,new Pawn(),new[]{new IntVec3(60)}).First().x==60,"Changed target retained a stale search cursor");
 Find.TickManager.TicksGame=1000;
 Check(CursorSubject.Review(pawn,enemy,new[]{new IntVec3(70)}).First().x==70,"Expired candidate cursor was retained");
 return count;
 }
}
'@
$taskCode=$taskCode.Replace('MATH',$taskSource.Substring($taskMathStart,$taskMathEnd-$taskMathStart)).Replace('CURSOR',$taskSource.Substring($taskCursorStart,$taskCursorEnd-$taskCursorStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[CoverTurnRegression]::Run()
