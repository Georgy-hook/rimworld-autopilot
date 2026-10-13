using System;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Helpers {
 public static class OrdinaryWorkSafety {
  public static bool WorkingTemperatureSafe(float temperature,float comfortableMin,float comfortableMax)
   => temperature>=comfortableMin-10f && temperature<=comfortableMax+10f;
  public static bool OriginSafe(Pawn p) {
   Map m=p.Map;var c=p.Position;
   return !c.Fogged(m) && !c.ContainsStaticFire(m)
    && m.gasGrid.DensityAt(c,GasType.ToxGas)==0 && m.gasGrid.DensityAt(c,GasType.DeadlifeDust)==0 && m.gasGrid.DensityAt(c,GasType.RotStink)==0
    && WorkingTemperatureSafe(c.GetTemperature(m),p.GetStatValue(StatDefOf.ComfyTemperatureMin),p.GetStatValue(StatDefOf.ComfyTemperatureMax))
    && (c.Roofed(m) || !m.gameConditionManager.ActiveConditions.Any(g=>g.def.defName=="ToxicFallout"));
  }
  public static string WorkerBlocker(Pawn p, WorkTypeDef work) {
   if(p==null || !p.Spawned || !p.IsColonistPlayerControlled || p.Dead)return "not_live_player_worker";
   if(p.Downed || p.Drafted || p.InMentalState)return "downed_drafted_or_mental_state";
   if(p.workSettings==null || p.WorkTypeIsDisabled(work))return "work_disabled";
   if(p.carryTracker.CarriedThing!=null)return "carrying";
   if(CareTriageHelper.QueuedCare(p) || CombatNativeHelper.HasCareJob(p))return "protected_patient_care";
   if(p.CurJob?.def.forceCompleteBeforeNextJob ?? false)return "job_must_complete";
   if(new[]{"Ingest","LayDown","GotoSafeTemperature","Hunt","DoBill","ButcherDoBill","Mine","AttackMelee","AttackStatic","HaulToCell"}.Contains(p.CurJobDef?.defName))return "protected_current_job";
   if(p.health.hediffSet.BleedRateTotal!=0f)return "worker_bleeding";
   if(CareTriageHelper.DiseaseCareProtected(p))return "worker_disease_care";
   if(!(p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness)>=.5f))return "consciousness_below_0_5";
   if(!(p.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.6f))return "moving_below_0_6";
   if(!(p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)>=.4f))return "manipulation_below_0_4";
   return null;
  }
  public static bool Worker(Pawn p, WorkTypeDef work) => WorkerBlocker(p,work)==null;
  public static bool Route(Pawn p, IntVec3 from, IntVec3 to, PathEndMode end) {
   Map m=p.Map;
   // A normal work path cannot cure an already unsafe origin. Shelter transitions
   // use their separate native contract; avoid an A* search for every rejected ore.
   if(!to.InBounds(m) || to.Fogged(m) || from==p.Position && !OriginSafe(p))return false;
   using(var path=m.pathFinder.FindPathNow(from,to,p,null,end)) {
    if(!path.Found)return false;
    var enemies=m.mapPawns.AllPawnsSpawned.Where(e=>!e.Dead && !e.Downed && !e.Position.Fogged(m) && (e.HostileTo(p) || CombatNativeHelper.ActivePredation(e))).ToArray();
    var turrets=m.listerBuildings.allBuildingsNonColonist.Where(b=>!b.Position.Fogged(m) && CombatNativeHelper.ActiveStructure(b)).ToArray();
    float comfortableMin=p.GetStatValue(StatDefOf.ComfyTemperatureMin)-10f,comfortableMax=p.GetStatValue(StatDefOf.ComfyTemperatureMax)+10f;
    bool fallout=m.gameConditionManager.ActiveConditions.Any(g=>g.def.defName=="ToxicFallout");
    foreach(var c in path.NodesReversed) {
     float temp=c.GetTemperature(m);
     if(c.Fogged(m) || c.ContainsStaticFire(m) || m.gasGrid.DensityAt(c,GasType.ToxGas)>0 || m.gasGrid.DensityAt(c,GasType.DeadlifeDust)>0 || m.gasGrid.DensityAt(c,GasType.RotStink)>0
      || temp<comfortableMin || temp>comfortableMax
      || !c.Roofed(m) && fallout
      || enemies.Any(e=>c.InHorDistOf(e.Position,Math.Max(12f,(e.equipment?.Primary?.def.Verbs?.FirstOrDefault()?.range ?? 0f)+3f)))
      || turrets.Any(b=>c.InHorDistOf(b.Position,Math.Max(12f,((b as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f)+3f))))return false;
    }
   }
   return true;
  }
 }
}
