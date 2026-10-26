$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatFallbackCohortHelper.cs')
$taskStart=$taskSource.IndexOf('        private static object FallbackDiagnostics()')
$taskEnd=$taskSource.IndexOf(';',$taskStart)+1
$taskCode=@'
using System;
using System.Collections.Generic;
public static class CohortDiagnosticRegression {
 private static readonly List<object> FallbackProofs=new List<object>();
 private static readonly List<object> FallbackReviews=new List<object>();
 private static readonly List<object> MemberReceipts=new List<object>();
 private static readonly Dictionary<string,int> FallbackReasons=new Dictionary<string,int>();
 METHOD
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 public static int Run(){
  FallbackReasons["no_cover_gun"]=7;
  var dto=FallbackDiagnostics();
  var receipts=(object[])dto.GetType().GetProperty("member_receipts").GetValue(dto);
  MemberReceipts.Add(new object());
  Check(receipts.Length==0,"Prepared member receipts changed after a later combat review");
  var snapshot=(IDictionary<string,int>)dto.GetType().GetProperty("reasons").GetValue(dto);
  Check(!Object.ReferenceEquals(snapshot,FallbackReasons),"Mutable counter dictionary escaped to response serialization");
  FallbackReasons["no_cover_gun"]=9;
  FallbackReasons["new_reason"]=1;
  Check(snapshot["no_cover_gun"]==7,"Prepared response changed after a combat tick");
  Check(!snapshot.ContainsKey("new_reason"),"Later tick extended an earlier response");
  var enumerator=snapshot.GetEnumerator();Check(enumerator.MoveNext(),"Missing captured counter");
  FallbackReasons.Clear();
  Check(enumerator.Current.Value==7,"Source pruning invalidated the response counter");
  Check(!enumerator.MoveNext(),"Response enumeration changed with live counters");
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('METHOD',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[CohortDiagnosticRegression]::Run()
