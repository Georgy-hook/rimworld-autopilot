$ErrorActionPreference='Stop'
$taskSource=Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/CombatPhysicianLineHelper.cs')
$taskFrom=$taskSource.IndexOf('        private static bool PhysicianAtBlindPost(')
$taskTo=$taskSource.IndexOf('        // A post-arrival firing rejoin', $taskFrom)
$taskCode=@'
using System;using System.Linq;using System.Collections.Generic;
public sealed class Bleed {public float BleedRateTotal;}
public sealed class Summary {public float SummaryHealthPercent=1;}
public sealed class Health {public Bleed hediffSet=new Bleed();public Summary summaryHealth=new Summary();}
public sealed class Jobs {public List<object> jobQueue=new List<object>();}
public sealed class Carry {public object CarriedThing;}
public sealed class Stances {public object curStance;}
public sealed class Stance_Warmup {}
public static class JobDefOf {public const string Goto="Goto",Ingest="Ingest";}
public sealed class Pawn {public int Position;public string CurJobDef="Wait_Combat";public Jobs jobs=new Jobs();public Carry carryTracker=new Carry();public Stances stances=new Stances();public Health health=new Health();public bool Doctor=true,Owned=true,Critical,Danger,Hit;}
public sealed class Plan {public Pawn Pawn;}
public sealed class FallbackCohort {public Pawn Doctor;public Dictionary<Pawn,int> Posts=new Dictionary<Pawn,int>();}
public sealed class DoctorBound {public int Goal;public bool Eligible=true;}
public static class CombatInterceptHelper {public static bool CanShootNow(Pawn p,Pawn t)=>p.Hit;}
public static class ActualPhysicianArrivalRegression {
 static int n;static void Check(bool ok,string why){n++;if(!ok)throw new Exception(why);}
 static Dictionary<Pawn,DoctorBound> DoctorBounds=new Dictionary<Pawn,DoctorBound>();
 static bool DoctorBoundEligible(Pawn p,DoctorBound b)=>b.Eligible;
 static bool NativeDoctor(Pawn p)=>p.Doctor;static bool CohortOwned(Pawn p)=>p.Owned;
 static bool CriticalRangedInjury(Pawn p)=>p.Critical;static bool TeamImmediateDanger(Pawn p)=>p.Danger;
METHOD
 public static int Run(){
  var p=new Pawn{Position=94};var plan=new Plan{Pawn=p};var c=new FallbackCohort{Doctor=p};c.Posts[p]=103;var threats=new List<Pawn>{new Pawn()};
  Check(!PhysicianAtBlindPost(plan,c,threats),"Assigned stale post was mistaken for arrival");
  var b=new DoctorBound{Goal=94};DoctorBounds[p]=b;
  Check(PhysicianAtBlindPost(plan,c,threats),"AD second actual refuge arrival remained invisible behind old front-group post");
  b.Goal=93;Check(!PhysicianAtBlindPost(plan,c,threats),"Unreached native goal became firing origin");b.Goal=94;
  b.Eligible=false;Check(!PhysicianAtBlindPost(plan,c,threats),"Expired/foreign-map receipt adopted");b.Eligible=true;
  p.CurJobDef=JobDefOf.Goto;Check(!PhysicianAtBlindPost(plan,c,threats),"Working early route replaced in transit");p.CurJobDef=JobDefOf.Ingest;Check(!PhysicianAtBlindPost(plan,c,threats),"Eating doctor diverted");p.CurJobDef="Wait_Combat";
  p.Owned=false;Check(!PhysicianAtBlindPost(plan,c,threats),"Foreign intent adopted");p.Owned=true;
  p.jobs.jobQueue.Add(new object());Check(!PhysicianAtBlindPost(plan,c,threats),"Later queued care erased");p.jobs.jobQueue.Clear();
  p.health.hediffSet.BleedRateTotal=.01f;Check(!PhysicianAtBlindPost(plan,c,threats),"Bleeding physician exposed");p.health.hediffSet.BleedRateTotal=0;
  p.health.summaryHealth.SummaryHealthPercent=.84f;Check(!PhysicianAtBlindPost(plan,c,threats),"Impaired physician exposed");p.health.summaryHealth.SummaryHealthPercent=1;
  p.Hit=true;Check(!PhysicianAtBlindPost(plan,c,threats),"Useful stationary fire replaced by blind-post search");p.Hit=false;
  p.stances.curStance=new Stance_Warmup();Check(!PhysicianAtBlindPost(plan,c,threats),"Actual warmup interrupted");p.stances.curStance=null;
  p.carryTracker.CarriedThing=new Pawn();Check(!PhysicianAtBlindPost(plan,c,threats),"Carrying patient abandoned");p.carryTracker.CarriedThing=null;
  return n;
 }
}
'@
Add-Type -TypeDefinition $taskCode.Replace('METHOD',$taskSource.Substring($taskFrom,$taskTo-$taskFrom)) -Language CSharp
[ActualPhysicianArrivalRegression]::Run()
