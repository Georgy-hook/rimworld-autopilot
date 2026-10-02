using System;
using System.Linq;
using System.Collections.Generic;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
namespace RIMAPI.Helpers {
 public static class ProductionHelper {
  private static readonly Lazy<HashSet<ThingDef>> UnsafeFeedDefs=new Lazy<HashSet<ThingDef>>(()=>new HashSet<ThingDef>(
   DefDatabase<ThingDef>.AllDefsListForReading.Where(d=>d.IsCorpse || d.defName=="InsectJelly" || (d.comps?.OfType<CompProperties_Hatcher>().Any() ?? false))
   .Concat(DefDatabase<ThingDef>.AllDefsListForReading.Where(d=>d.race!=null && d.race.Humanlike).Select(d=>d.race.meatDef))));
  private static bool SafeFeedDef(ThingDef d) => !UnsafeFeedDefs.Value.Contains(d);
  private static bool EligibleStock(Thing t) => !t.IsForbidden(Faction.OfPlayer) && !t.IsBurning()
   && (t.TryGetComp<CompRottable>()==null || t.TryGetComp<CompRottable>().Stage==RotStage.Fresh);
  private static bool Pending(Bill b) => !(b is Bill_Production p && p.repeatMode==BillRepeatModeDefOf.RepeatCount && p.repeatCount==0);
  private static bool Cook(Pawn p, RecipeDef r) {
   var cooking=DefDatabase<WorkTypeDef>.GetNamedSilentFail("Cooking");
   return cooking!=null && p.IsColonist && !p.Dead && !p.Downed && !p.Drafted && !p.InMentalState
    && p.workSettings!=null && !p.WorkTypeIsDisabled(cooking) && p.workSettings.GetPriority(cooking)>0
    && r.PawnSatisfiesSkillRequirements(p) && p.CurJobDef!=JobDefOf.DoBill && p.CurJobDef!=JobDefOf.TendPatient && p.CurJobDef!=JobDefOf.Rescue && p.CurJobDef!=JobDefOf.FeedPatient;
  }
  private static Bill_Production Reusable(Building_WorkTable t,RecipeDef r) => t.BillStack.Bills.OfType<Bill_Production>().FirstOrDefault(b=>b.recipe==r && !Pending(b));
  private static ThingFilter Effective(Building_WorkTable t,RecipeDef r) => Reusable(t,r)?.ingredientFilter ?? r.defaultIngredientFilter ?? r.fixedIngredientFilter;
  private static bool Supplies(Building_WorkTable table,RecipeDef r) => r.ingredients.All(i=>table.Map.listerThings.AllThings
   .Where(t=>EligibleStock(t) && SafeFeedDef(t.def) && i.filter.Allows(t) && r.fixedIngredientFilter.Allows(t) && Effective(table,r).Allows(t))
   .Sum(t=>t.GetStatValue(StatDefOf.Nutrition)*t.stackCount)>=i.GetBaseCount());
  public static ApiResult<object> Context(int mapId) {
   var map = MapHelper.GetMapByID(mapId);
   if(map == null) return ApiResult<object>.Fail("Map not found");
   var buildings = map.listerBuildings.allBuildingsColonist.Select(b => {
    var fuel = b.TryGetComp<CompRefuelable>(); var power = b.TryGetComp<CompPowerTrader>(); var flick = b.TryGetComp<CompFlickable>();
    return new { id=b.thingIDNumber, def_name=b.def.defName, label=b.LabelShortCap,
     temperature=b.AmbientTemperature, power_output=power?.PowerOutput, powered=power?.PowerOn,
     connected=power?.PowerNet != null, switch_on=flick?.SwitchIsOn, flick_pending=flick?.WantsFlick() ?? false,
     fuel=fuel?.Fuel, capacity=fuel?.Props.fuelCapacity, fuel_per_day=fuel?.Props.fuelConsumptionRate,
     consume_only_when_used=fuel?.Props.consumeFuelOnlyWhenUsed, auto_refuel=fuel?.allowAutoRefuel,
     can_set_auto_refuel=fuel?.Props.showAllowAutoRefuelToggle ?? false,
     fuel_defs=fuel?.Props.fuelFilter.AllowedThingDefs.Select(d=>d.defName).ToArray() };
   }).Where(b=>b.switch_on.HasValue || b.fuel.HasValue).ToArray();
   var stocks = map.listerThings.AllThings.Where(t=>t.def.category==ThingCategory.Item).GroupBy(t=>t.def.defName)
    .Select(g=>new {def_name=g.Key, count=g.Sum(t=>t.stackCount), nutrition=g.Sum(t=>t.def.ingestible==null ? 0f : t.GetStatValue(StatDefOf.Nutrition)*t.stackCount),
      eligible_nutrition=g.Where(t=>EligibleStock(t) && SafeFeedDef(t.def)).Sum(t=>t.def.ingestible==null ? 0f : t.GetStatValue(StatDefOf.Nutrition)*t.stackCount)}).ToArray();
   var recipe=DefDatabase<RecipeDef>.GetNamedSilentFail("Make_Kibble");
   var feedTables=map.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>()
    .Where(t=>recipe!=null && recipe.AvailableNow && t.def.AllRecipes.Contains(recipe))
    .Select(t=>new {id=t.thingIDNumber, label=t.LabelShortCap, usable=t.CurrentlyUsableForBills(),
     existing_bill=t.BillStack.Bills.Any(b=>b.recipe==recipe && Pending(b)), eligible_worker_ids=map.mapPawns.FreeColonistsSpawned.Where(p=>Cook(p,recipe) && (Reusable(t,recipe)?.PawnAllowedToStartAnew(p) ?? true)).Select(p=>p.thingIDNumber).ToArray(),
     ingredients=recipe.ingredients.Select(i=>new {count=i.GetBaseCount(), units="nutrition", allowed_defs=i.filter.AllowedThingDefs
      .Where(d=>recipe.fixedIngredientFilter.Allows(d) && Effective(t,recipe).Allows(d) && SafeFeedDef(d))
      .Select(d=>d.defName).ToArray()}).ToArray(),
     product=recipe.products.Select(p=>new {def_name=p.thingDef.defName,count=p.count}).ToArray()}).ToArray();
   var perishables=map.listerThings.AllThings.Where(t=>t.def.category==ThingCategory.Item && t.TryGetComp<CompRottable>()!=null)
    .Select(t=>new {id=t.thingIDNumber,def_name=t.def.defName,count=t.stackCount,temperature=t.AmbientTemperature,
     ticks_until_rot=t.TryGetComp<CompRottable>().TicksUntilRotAtCurrentTemp}).ToArray();
   var kibble=DefDatabase<ThingDef>.GetNamedSilentFail("Kibble");
   var animals=map.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal)
    .Select(p=>new {id=p.thingIDNumber,species=p.def.defName,diet=p.RaceProps.foodType.ToString(),can_eat_kibble=kibble!=null && p.RaceProps.CanEverEat(kibble),
     food_level=p.needs?.food?.CurLevelPercentage, can_graze=p.RaceProps.Eats(FoodTypeFlags.Plant), downed=p.Downed}).ToArray();
   return ApiResult<object>.Ok(new {buildings, stocks, feed_tables=feedTables, perishables, animals});
  }
  public static ApiResult<CapabilityOrderResultDto> Policy(ProductionPolicyDto r) {
   var b=MapHelper.GetThingOnMapById(r.MapId,r.BuildingId) as Building;
   if(b==null || b.Faction!=Faction.OfPlayer || !b.Spawned) return ApiResult<CapabilityOrderResultDto>.Fail("Player building missing");
   var result=new CapabilityOrderResultDto {TargetId=r.BuildingId,Reason="unsupported_policy"};
   var fuel=b.TryGetComp<CompRefuelable>(); var flick=b.TryGetComp<CompFlickable>();
   if(r.Policy=="enable_refuel" || r.Policy=="disable_refuel") {
    if(fuel==null || !fuel.Props.showAllowAutoRefuelToggle) return ApiResult<CapabilityOrderResultDto>.Ok(result);
    bool wanted=r.Policy=="enable_refuel"; result.Applied=fuel.allowAutoRefuel!=wanted;
    fuel.allowAutoRefuel=wanted; result.Reason=result.Applied ? "refuel_policy_changed" : "already_configured";
   } else if(r.Policy=="kibble_batch") {
    var table=b as Building_WorkTable; var recipe=DefDatabase<RecipeDef>.GetNamedSilentFail("Make_Kibble");
    if(table==null || recipe==null || !recipe.AvailableNow || !table.def.AllRecipes.Contains(recipe)
      || !table.CurrentlyUsableForBills() || !table.Map.mapPawns.FreeColonistsSpawned.Any(p=>Cook(p,recipe) && (Reusable(table,recipe)?.PawnAllowedToStartAnew(p) ?? true)) || !Supplies(table,recipe)
      || !table.Map.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Any(p=>p.RaceProps.Animal && p.RaceProps.CanEverEat(DefDatabase<ThingDef>.GetNamed("Kibble")))
      || table.BillStack.Bills.Any(x=>x.recipe==recipe && Pending(x)))
     {result.Reason="feed_bill_unavailable_or_existing";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
    var bill=Reusable(table,recipe);
    bool adding=bill==null;
    if(adding && table.BillStack.Bills.Count>=15) {result.Reason="bill_stack_full";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
    if(adding) bill=new Bill_Production(recipe);
    bill.repeatMode=BillRepeatModeDefOf.RepeatCount;bill.repeatCount=1;bill.suspended=false;
    // Explicitly protect human meat, fertilized eggs and insect jelly in the bill filter.
    foreach(var def in bill.ingredientFilter.AllowedThingDefs.ToList())
     if(!SafeFeedDef(def)) bill.ingredientFilter.SetAllow(def,false);
    if(adding) table.BillStack.AddBill(bill);result.Applied=true;result.Reason="one_feed_batch_bill_accepted_not_produced";
   } else if(r.Policy=="switch_on" || r.Policy=="switch_off") {
    if(flick==null || flick.WantsFlick()) {result.Reason="missing_switch_or_pending_flick";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
    bool wanted=r.Policy=="switch_on";
    if(flick.SwitchIsOn==wanted) {result.Reason="already_configured";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
    var command=flick.CompGetGizmosExtra().OfType<Command_Toggle>().FirstOrDefault();
    if(command!=null) {command.toggleAction();result.Applied=true;result.Reason="flick_designation_requested";}
   }
   return ApiResult<CapabilityOrderResultDto>.Ok(result);
  }
 }
}
