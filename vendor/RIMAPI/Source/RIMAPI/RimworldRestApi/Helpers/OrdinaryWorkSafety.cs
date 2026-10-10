using System;
using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Helpers {
 public static class OrdinaryWorkSafety {
  public static bool Worker(Pawn p, WorkTypeDef work) => p!=null && p.Spawned && p.IsColonistPlayerControlled
   && !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState && p.workSettings!=null && !p.WorkTypeIsDisabled(work)
   && p.carryTracker.CarriedThing==null && !CareTriageHelper.QueuedCare(p)
   && !CombatNativeHelper.HasCareJob(p) && !(p.CurJob?.def.forceCompleteBeforeNextJob ?? false)
   && !new[]{"Ingest","LayDown","GotoSafeTemperature","Hunt","DoBill","ButcherDoBill","Mine","AttackMelee","AttackStatic","HaulToCell"}.Contains(p.CurJobDef?.defName)
   && p.health.hediffSet.BleedRateTotal==0f && !CareTriageHelper.DiseaseCareProtected(p)
   && p.health.capacities.GetLevel(PawnCapacityDefOf.Consciousness)>=.5f
   && p.health.capacities.GetLevel(PawnCapacityDefOf.Moving)>=.6f
   && p.health.capacities.GetLevel(PawnCapacityDefOf.Manipulation)>=.4f;
  public static bool Route(Pawn p, IntVec3 from, IntVec3 to, PathEndMode end) {
   Map m=p.Map;
   if(!to.InBounds(m) || to.Fogged(m))return false;
   using(var path=m.pathFinder.FindPathNow(from,to,p,null,end)) {
    if(!path.Found)return false;
    var enemies=m.mapPawns.AllPawnsSpawned.Where(e=>!e.Dead && !e.Downed && !e.Position.Fogged(m) && (e.HostileTo(p) || CombatNativeHelper.ActivePredation(e))).ToArray();
    var turrets=m.listerBuildings.allBuildingsNonColonist.Where(b=>!b.Position.Fogged(m) && CombatNativeHelper.ActiveStructure(b)).ToArray();
    foreach(var c in path.NodesReversed) {
     float temp=c.GetTemperature(m);
     if(c.Fogged(m) || c.ContainsStaticFire(m) || m.gasGrid.DensityAt(c,GasType.ToxGas)>0 || m.gasGrid.DensityAt(c,GasType.DeadlifeDust)>0 || m.gasGrid.DensityAt(c,GasType.RotStink)>0
      || temp<p.GetStatValue(StatDefOf.ComfyTemperatureMin)-10f || temp>p.GetStatValue(StatDefOf.ComfyTemperatureMax)+10f
      || !c.Roofed(m) && m.gameConditionManager.ActiveConditions.Any(g=>g.def.defName=="ToxicFallout")
      || enemies.Any(e=>c.InHorDistOf(e.Position,Math.Max(12f,(e.equipment?.Primary?.def.Verbs?.FirstOrDefault()?.range ?? 0f)+3f)))
      || turrets.Any(b=>c.InHorDistOf(b.Position,Math.Max(12f,((b as Building_Turret)?.AttackVerb?.EffectiveRange ?? 0f)+3f))))return false;
    }
   }
   return true;
  }
 }
}
