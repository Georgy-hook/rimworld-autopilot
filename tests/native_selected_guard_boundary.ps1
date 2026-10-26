$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatSelectedGuardHelper.cs')
$taskStart=$taskSource.IndexOf('        public static bool Admits(')
$taskEnd=$taskSource.IndexOf('        // This admits', $taskStart)
$taskCode=@'
using System;
public static class SelectedGuardSubject {
METHOD
}
public static class SelectedGuardRegression {
 public static int Run(){
  int n=0;
  if(!SelectedGuardSubject.Admits(true,true,false,true,false,false,false,false,false))throw new Exception("An explicitly selected drafted idle gun could not obtain its native guard");n++;
  bool[] baseline={true,true,false,true,false,false,false,false,false};
  for(int k=0;k<baseline.Length;k++){
   var a=(bool[])baseline.Clone();a[k]=!a[k];
   if(SelectedGuardSubject.Admits(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8]))
    throw new Exception("Admission ignored a draft/range/selected-role/manual/care/queue/warmup/burst boundary at "+k);
   n++;
  }
  return n;
 }
}
'@
$taskCode=$taskCode.Replace('METHOD',$taskSource.Substring($taskStart,$taskEnd-$taskStart))
Add-Type -TypeDefinition $taskCode -Language CSharp
[SelectedGuardRegression]::Run()
