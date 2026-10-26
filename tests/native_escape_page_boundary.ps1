$ErrorActionPreference='Stop'
$taskPages=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatCoverTurnHelper.cs')
$taskFrom=$taskPages.IndexOf('        private sealed class EscapeSearch')
$taskTo=$taskPages.IndexOf('        private sealed class CoverTurn')
$taskPageCode=@'
using System;
using System.Linq;
using System.Collections.Generic;
namespace ActualEscapePages {
 public struct IntVec3 {public int x;public IntVec3(int v){x=v;}public static bool operator ==(IntVec3 a,IntVec3 b)=>a.x==b.x;public static bool operator !=(IntVec3 a,IntVec3 b)=>a.x!=b.x;public override bool Equals(object o)=>o is IntVec3 c&&c.x==x;public override int GetHashCode()=>x;}
 public sealed class Pawn {public IntVec3 Position;}
 public sealed class Clock {public int TicksGame;}
 public static class Find {public static Clock TickManager=new Clock();}
 public static class Proof {
 ACTUAL
 public static int Run(){
  var p=new Pawn();var t=new Pawn();var cells=Enumerable.Range(1,8).Select(x=>new IntVec3(x)).ToArray();
  if(ReviewEscapeCells(p,t,"melee",cells,1).Single().x!=1)throw new Exception("first page");
  if(ReviewEscapeCells(p,t,"melee",cells,1).Single().x!=2)throw new Exception("completed one-proof page restarted rejected prefix");
  using(var it=ReviewEscapeCells(p,t,"melee",cells,1).GetEnumerator()){it.MoveNext();if(it.Current.x!=3)throw new Exception("third page");}
  if(ReviewEscapeCells(p,t,"melee",cells,1).Single().x!=3)throw new Exception("incomplete safety proof was silently skipped");
  if(ReviewEscapeCells(p,t,"melee",cells,1).Single().x!=4)throw new Exception("resumed completed proof did not advance");
  p.Position=new IntVec3(10);
  if(ReviewEscapeCells(p,t,"melee",cells,1).Single().x!=1)throw new Exception("new origin reused stale proof cursor");
  return 6;
 }
 }
}
'@
$taskPageCode=$taskPageCode.Replace('ACTUAL',$taskPages.Substring($taskFrom,$taskTo-$taskFrom))
Add-Type -TypeDefinition $taskPageCode -Language CSharp
[ActualEscapePages.Proof]::Run()
$taskRetreat=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatControlHelper.cs')
if($taskRetreat -notmatch '"handoff":"melee",ranked,1\)'){throw 'Individual retreat still consumes an unfinished eight-query page'}
