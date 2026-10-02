using System;
using System.Linq;
using System.Collections.Generic;
using RimWorld;
using Verse;
using Verse.AI;
using RIMAPI.Core;
using RIMAPI.Models;
namespace RIMAPI.Helpers {
 public static class SustenanceHelper {
  public sealed class Plan { public string key; public string kind; public int target_id; public string value; public string label; public string cost; public string risk; }
  static bool Protected(Pawn p) => p.Dead || p.Downed || p.Drafted || p.InMentalState || p.CurJobDef==JobDefOf.TendPatient || p.CurJobDef==JobDefOf.Rescue || p.CurJobDef==JobDefOf.FeedPatient || p.CurJobDef==JobDefOf.DoBill;
  static bool Safe(Thing t) => !t.IsForbidden(Faction.OfPlayer) && !t.IsBurning() && (t.TryGetComp<CompRottable>()==null || t.TryGetComp<CompRottable>().Stage==RotStage.Fresh)
  ;
  static bool FoodRecipe(RecipeDef r) => r.products.Any(p=>p.thingDef.ingestible!=null && p.thingDef.ingestible.foodType!=FoodTypeFlags.None && !p.thingDef.IsDrug) || r.defName=="ButcherCorpseFlesh";
  static bool Pending(Bill b) => !(b is Bill_Production p && p.repeatMode==BillRepeatModeDefOf.RepeatCount && p.repeatCount==0);
  static bool Worker(Pawn p, Building_WorkTable t, RecipeDef r) {
   var w=r.requiredGiverWorkType ?? DefDatabase<WorkTypeDef>.GetNamedSilentFail("Cooking");
   return !Protected(p) && !t.IsForbidden(p) && p.CanReserve(t) && t.GetWorkgiver()?.Worker.MissingRequiredCapacity(p)==null && p.workSettings!=null && w!=null && !p.WorkTypeIsDisabled(w) && p.workSettings.GetPriority(w)>0 && r.PawnSatisfiesSkillRequirements(p)
    && p.CanReach(t.InteractionCell,PathEndMode.OnCell,Danger.Some);
  }
  static Bill_Production FoodBill(Building_WorkTable table, RecipeDef recipe) {
   var trial=ProductionRecipeHelper.Trial(table,recipe,null,true);
   trial.billStack=table.BillStack;
   var allowed=new HashSet<ThingDef>(trial.ingredientFilter.AllowedThingDefs);
   return table.BillStack.Bills.OfType<Bill_Production>().FirstOrDefault(b=>b.recipe==recipe && b.GetType()==trial.GetType() && b.repeatMode==BillRepeatModeDefOf.RepeatCount && b.repeatCount==0 && allowed.SetEquals(b.ingredientFilter.AllowedThingDefs)) ?? trial;
  }
  // Mirror only the native zone selection, without allocating a Job, rolling
  // random fish cells or firing an ideology event during GET. Execution still
  // asks the real giver and rejects a changed requested zone.
  static Zone_Fishing NativeFishingZone(Pawn pawn) {
   var map=pawn.Map;
   if(pawn.CanReserve(pawn.Position,1,-1,ReservationLayerDefOf.Floor) && !pawn.Position.GetTerrain(map).IsWater)
    for(int i=0;i<4;i++) {
     var cell=pawn.Position+GenAdj.CardinalDirections[(i+pawn.thingIDNumber)%4];
     if(cell.InBounds(map) && cell.GetZone(map) is Zone_Fishing adjacent && adjacent.ShouldFishNow
      && adjacent.IsFishable(cell) && !cell.IsForbidden(pawn) && pawn.CanReserve(cell,1,-1,ReservationLayerDefOf.Floor))return adjacent;
    }
   Zone_Fishing nearest=null;float distance=float.MaxValue;
   foreach(var zone in map.zoneManager.AllZones.OfType<Zone_Fishing>().Where(z=>z.ShouldFishNow && z.HasAnyFishableCells)) {
    float next=pawn.Position.DistanceToSquared(zone.Cells[0]);
    if(nearest==null || next<distance){nearest=zone;distance=next;}
   }
   return nearest;
  }
  static List<Plan> Plans(Map m) {
   var list=new List<Plan>();
   var stock=m.listerThings.AllThings.Where(t=>(t.def.category==ThingCategory.Item || t is Corpse) && Safe(t)).ToArray();
   var reachable=new Dictionary<Pawn,Thing[]>();
   foreach(var t in m.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>().Where(t=>t.CurrentlyUsableForBills()))
    foreach(var r in t.def.AllRecipes.Where(r=>r.AvailableNow && r.AvailableOnNow(t) && FoodRecipe(r) && r.defName!="Make_Kibble" && !t.BillStack.Bills.Any(b=>b.recipe==r && Pending(b)))) {
     var bill=FoodBill(t,r);
     if(!t.BillStack.Bills.Contains(bill) && t.BillStack.Bills.Count>=15)continue;
     if(m.mapPawns.FreeColonistsSpawned.Any(p=> {
      if(!Worker(p,t,r) || !bill.PawnAllowedToStartAnew(p))return false;
      if(!reachable.TryGetValue(p,out Thing[] pool)){pool=stock.Where(x=>!x.IsForbidden(p) && p.CanReserveAndReach(x,PathEndMode.ClosestTouch,Danger.Some)).ToArray();reachable[p]=pool;}
      return ProductionRecipeHelper.Supplies(pool,bill);
     }))
      list.Add(new Plan{key=$"bill:{t.thingIDNumber}:{r.defName}",kind="bill",target_id=t.thingIDNumber,value=r.defName,label=t.LabelShortCap+": "+r.LabelCap,cost=string.Join("; ",r.ingredients.Select(i=>i.SummaryFor(r))),risk="One ordinary bill batch; food/ingredients and cook labor consumed; poisoning depends on loaded recipe, cook and room; Loaded ingredient filter may consume human corpses/meat or fertilized eggs; compare ideology, mood and breeding loss"});
    }
   foreach(var p in m.mapPawns.FreeColonistsSpawned.Where(p=>p.foodRestriction?.Configurable==true))
    foreach(var policy in Current.Game.foodRestrictionDatabase.AllFoodRestrictions.Where(f=>f!=p.foodRestriction.CurrentFoodPolicy))
     if(m.listerThings.AllThings.Any(t=>t.def.ingestible!=null && Safe(t) && policy.Allows(t) && p.RaceProps.CanEverEat(t.def) && !t.IsForbidden(p) && p.CanReserveAndReach(t,PathEndMode.ClosestTouch,Danger.Some)))
      list.Add(new Plan{key=$"diet:{p.thingIDNumber}:{policy.id}",kind="diet",target_id=p.thingIDNumber,value=policy.id.ToString(),label=p.LabelShortCap+": "+policy.label,cost="Changes permitted food; no food is created or forced eaten",risk="Compare actual policy ingredients, ideology, raw food, mood and scarcity; reachable allowed stock checked"});
   foreach(var pawn in m.mapPawns.FreeColonistsSpawned.Where(p=>p.foodRestriction?.Configurable==true)) {
    var current=pawn.foodRestriction.CurrentFoodPolicy;
    if(current==null)continue;
    var edible=stock.Where(t=>t.def.ingestible!=null && !t.def.IsDrug && pawn.RaceProps.CanEverEat(t.def) && !t.IsForbidden(pawn) && pawn.CanReserveAndReach(t,PathEndMode.ClosestTouch,Danger.Some)).ToArray();
    foreach(var def in edible.Select(t=>t.def).Distinct()) {
     bool allow=!current.Allows(def);
     if(!allow && !edible.Any(t=>t.def!=def && current.Allows(t)))continue;
     list.Add(new Plan{key=$"customdiet:{pawn.thingIDNumber}:{def.defName}:{allow}",kind="customdiet",target_id=pawn.thingIDNumber,value=def.defName+":"+allow,label=pawn.LabelShortCap+": "+(allow?"allow ":"avoid ")+def.LabelCap,cost="Copies current policy into a dedicated per-pawn policy, changes one loaded edible definition",risk="ideology="+(pawn.Ideo?.name ?? "none")+"; precepts="+string.Join(",",pawn.Ideo?.PreceptsListForReading.Select(p=>p.def.defName) ?? Enumerable.Empty<string>())+"; raw poisoning; human/insect ingredients and scarcity"});
    }
   }
   foreach(var giver in DefDatabase<WorkGiverDef>.AllDefs.Where(d=>d.Worker is WorkGiver_Milk || d.Worker is WorkGiver_Shear)) {
    var scanner=(WorkGiver_Scanner)giver.Worker;
    foreach(var pawn in m.mapPawns.FreeColonistsSpawned.Where(p=>!Protected(p) && p.workSettings!=null && !p.WorkTypeIsDisabled(giver.workType) && p.workSettings.GetPriority(giver.workType)>0 && scanner.MissingRequiredCapacity(p)==null))
     foreach(var animal in m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal && !p.IsForbidden(pawn) && pawn.CanReserveAndReach(p,PathEndMode.Touch,Danger.Some) && scanner.HasJobOnThing(pawn,p,false)))
      list.Add(new Plan{key=$"gather:{animal.thingIDNumber}:{giver.defName}:{pawn.thingIDNumber}",kind="gather",target_id=animal.thingIDNumber,value=giver.defName+":"+pawn.thingIDNumber,label=pawn.LabelShortCap+": "+giver.LabelCap+" "+animal.LabelShortCap,cost="Normal handling labor; only full active native milk/wool resource",risk="Interrupts non-care worker task; animal availability and path checked again; products only after ordinary job"});
   }
   if(ModsConfig.OdysseyActive && ResearchProjectDefOf.Fishing?.IsFinished==true && !m.zoneManager.AllZones.OfType<Zone_Fishing>().Any()) {
    // One bounded map-grid pass only for bootstrap; at most one accessible shoreline patch per actual water type.
    var selectedTypes=new HashSet<WaterBodyType>();
    var shorelineHostiles=m.mapPawns.AllPawnsSpawned.Where(p=>!p.Dead && p.HostileTo(Faction.OfPlayer)).ToArray();
    foreach(var cell in m.AllCells) {
     var type=cell.GetWaterBodyType(m);
     if(type==WaterBodyType.None || selectedTypes.Contains(type) || shorelineHostiles.Any(p=>p.Position.DistanceToSquared(cell)<900) || cell.GetTerrain(m).passability==Traversability.Impassable || !m.waterBodyTracker.AnyFishPopulationAt(cell) || cell.GetZone(m)!=null || !Designator_ZoneAdd.IsZoneableCell(cell,m))continue;
     if(!m.mapPawns.FreeColonistsSpawned.Any(p=>!Protected(p) && GenAdj.CardinalDirections.Any(d=>{var bank=cell+d;return bank.InBounds(m) && bank.Standable(m) && !bank.GetTerrain(m).IsWater && !bank.IsForbidden(p) && p.CanReserveAndReach(bank,PathEndMode.OnCell,Danger.Some);})))continue;
     var footprint=new[]{cell}.Concat(GenAdj.CardinalDirections.Select(d=>cell+d)).Where(c=>c.InBounds(m) && c.GetWaterBodyType(m)==type && c.GetTerrain(m).passability!=Traversability.Impassable && m.waterBodyTracker.AnyFishPopulationAt(c) && c.GetZone(m)==null && Designator_ZoneAdd.IsZoneableCell(c,m)).ToArray();
     var encoded=string.Join(";",footprint.Select(c=>c.x+","+c.z));
     list.Add(new Plan{key="fishzone:"+encoded,kind="fishzone",target_id=-1,value=encoded,label="Create fishing zone: "+type+" at "+cell,cost="Existing legal fish-bearing water; native zone creation, one catch cycle then stop",risk="population="+m.waterBodyTracker.PopulationPercentAt(cell)+"; fish slaughter precepts; dangerous catches; worker/spot still required"});selectedTypes.Add(type);
    }
   }
   if(ModsConfig.OdysseyActive) {
    foreach(var existingFishing in m.zoneManager.AllZones.OfType<Zone_Fishing>().Where(z=>z.Allowed && z.HasAnyFishableCells && !z.AllFishableCellsFrozen && (z.repeatMode!=FishRepeatMode.RepeatCount || z.repeatCount==0)))
     list.Add(new Plan{key=$"fishpolicy:{existingFishing.ID}:1",kind="fishpolicy",target_id=existingFishing.ID,value="1",label=existingFishing.label+": one fishing cycle",cost="Replaces current repeat mode with one ordinary catch cycle; stock/hauling remain normal",risk="population="+(existingFishing.Cells.Count>0?m.waterBodyTracker.PopulationPercentAt(existingFishing.Cells[0]):0)+"; existing population floor="+existingFishing.targetPopulationPct+" remains; slaughter precepts and dangerous catches"});
    var giver=DefDatabase<WorkGiverDef>.AllDefs.FirstOrDefault(d=>d.Worker is WorkGiver_Fish);
    if(giver!=null)foreach(var pawn in m.mapPawns.FreeColonistsSpawned.Where(p=>!Protected(p) && p.workSettings!=null && !p.WorkTypeIsDisabled(giver.workType) && p.workSettings.GetPriority(giver.workType)>0 && giver.Worker.MissingRequiredCapacity(p)==null))
     foreach(var zone in new[]{NativeFishingZone(pawn)}.Where(z=>z!=null)) {
      // Native jobgiver performs final ideology, spot, floor reservation and stand-position checks on execution.
      if(!zone.Cells.Any(c=>zone.IsFishable(c) && !c.IsForbidden(pawn) && pawn.CanReserveAndReach(c,PathEndMode.Touch,Danger.Some,1,-1,ReservationLayerDefOf.Floor)))continue;
      list.Add(new Plan{key=$"fish:{pawn.thingIDNumber}:{zone.ID}",kind="fish",target_id=pawn.thingIDNumber,value=giver.defName+":"+zone.ID,label=pawn.LabelShortCap+": fish existing "+zone.label,cost="Fishing labor; loaded seasonal population/yield and zone settings",risk="Fish slaughter precepts, dangerous catches/water and depleted population; native jobgiver may reject; no instant fish"});
     }
   }
   foreach(var b in m.listerBuildings.allBuildingsColonist.Where(b=>b.def.defName=="Cooler")) {
    var temp=b.TryGetComp<CompTempControl>(); if(temp==null)continue;
    foreach(int target in new[]{-9,-3,4}) if(Math.Abs(temp.targetTemperature-target)>0.1f)
     list.Add(new Plan{key=$"cooler:{b.thingIDNumber}:{target}",kind="cooler",target_id=b.thingIDNumber,value=target.ToString(),label=b.LabelShortCap+" target "+target+" C",cost="Electricity and heat exhaust; setting alone cannot guarantee freezing",risk="4 C slows rot; below freezing arrests rot but room insulation, ambient conditions and power matter"});
   }
   foreach(var b in m.listerBuildings.allBuildingsColonist.OfType<Building_Storage>().GroupBy(b=>b.GetStoreSettings()).Select(g=>g.First())) {
    var s=b.GetStoreSettings(); if(!s.filter.AllowedThingDefs.Any(d=>d.ingestible!=null))continue;
    foreach(int priority in new[]{2,4,5}) if((int)s.Priority!=priority)
     list.Add(new Plan{key=$"storage:{b.thingIDNumber}:{priority}",kind="storage",target_id=b.thingIDNumber,value=priority.ToString(),label=b.LabelShortCap+" priority "+priority,cost="Hauling labor; existing filter remains",risk="Linked shelves sharing settings affected="+m.listerBuildings.allBuildingsColonist.OfType<Building_Storage>().Count(shelf=>shelf.GetStoreSettings()==b.GetStoreSettings())+"; higher priority draws permitted food; compare temperatures/access"});
   }
   foreach(var z in m.zoneManager.AllZones.OfType<Zone_Stockpile>().Where(z=>z.Cells.Any())) {
    if(z.settings.filter.AllowedThingDefs.Any(d=>d.ingestible!=null)) foreach(int priority in new[]{2,4,5}) if((int)z.settings.Priority!=priority)
     list.Add(new Plan{key=$"stockpile:{z.ID}:{priority}",kind="stockpile",target_id=z.ID,value=priority.ToString(),label=z.label+" priority "+priority,cost="Ordinary hauling labor",risk="Existing food filter remains; compare cold storage, roof protection and animal access"});
    foreach(var def in m.listerThings.AllThings.Where(t=>t.def.ingestible!=null && Safe(t) && !t.def.IsDrug).Select(t=>t.def).Distinct()) if(!z.settings.filter.Allows(def))
     list.Add(new Plan{key=$"stockfood:{z.ID}:{def.defName}",kind="stockfood",target_id=z.ID,value=def.defName,label=z.label+": permit "+def.LabelCap,cost="Hauling and storage space; other allowances remain",risk="Food may be hauled into this stockpile according to priority; temperature, roof, competition and feeding access must be assessed"});
   }
   foreach(var p in m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal && p.playerSettings!=null)) {
    foreach(MedicalCareCategory care in Enum.GetValues(typeof(MedicalCareCategory))) if(p.playerSettings.medCare!=care)
     list.Add(new Plan{key=$"care:{p.thingIDNumber}:{(int)care}",kind="care",target_id=p.thingIDNumber,value=((int)care).ToString(),label=p.LabelShortCap+": "+care,cost="Sets maximum medicine allowed for ordinary tending; does not order surgery",risk=care==MedicalCareCategory.NoCare ? "No ordinary tending is permitted: injury, infection and illness may worsen or kill this animal; deliberate policy only"
      : care==MedicalCareCategory.NoMeds ? "Ordinary tending without medicine; lower tend quality may worsen serious disease"
      : care==MedicalCareCategory.Best ? "Allows the best loaded medicine, including glitterworld medicine; competes with human critical-care reserves"
      : "Medicine ceiling may reduce tend quality; permitted medicine competes with human reserves"});
    if(p.playerSettings.SupportsAllowedAreas && !Protected(p)) foreach(var a in m.areaManager.AllAreas.OfType<Area_Allowed>().Where(a=>a.TrueCount>0 && a!=p.playerSettings.AreaRestrictionInPawnCurrentMap))
     list.Add(new Plan{key=$"area:{p.thingIDNumber}:{a.ID}",kind="area",target_id=p.thingIDNumber,value=a.ID.ToString(),label=p.LabelShortCap+": "+a.Label,cost="Movement restriction; ordinary animal AI chooses feeding/rest",risk="Must compare food, beds, temperature and predators inside area; restriction may interrupt current animal job"});
   }
   foreach(var p in m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal && p.RaceProps.IsFlesh && !p.Downed && !p.Dead && (p.HomeFaction==null || p.HomeFaction==Faction.OfPlayer) && !p.health.hediffSet.hediffs.Any(h=>h is Hediff_Pregnant) && p.relations.GetFirstDirectRelationPawn(PawnRelationDefOf.Bond,x=>!x.Dead)==null)) {
    bool pending=m.designationManager.DesignationOn(p,DesignationDefOf.ReleaseAnimalToWild)!=null;
    if(!m.mapPawns.FreeColonistsSpawned.Any(d=>d.CurJob?.def.defName=="ReleaseAnimalToWild" && d.CurJob.targetA.Thing==p))
     list.Add(new Plan{key=$"release:{p.thingIDNumber}:{!pending}",kind="release",target_id=p.thingIDNumber,value=(!pending).ToString(),label=p.LabelShortCap+": "+(pending ? "cancel release" : "release to wild"),cost=pending ? "Retain animal feed demand" : "Permanent loss of ownership, breeding and products after handler job",risk="No slaughter meat, animal may remain nearby as wildlife; nonpregnant unbonded player-home animal; handler job and route not guaranteed"});
   }
   var sterilize=DefDatabase<RecipeDef>.GetNamedSilentFail("Sterilize");
   if(sterilize!=null && sterilize.AvailableNow) foreach(var p in m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal && !p.Dead && (p.HomeFaction==null || p.HomeFaction==Faction.OfPlayer))) {
    var pending=p.BillStack.Bills.Where(b=>b.recipe==sterilize).ToArray();
    bool underway=m.mapPawns.FreeColonistsSpawned.Any(d=>d.CurJobDef==JobDefOf.DoBill && d.CurJob.targetA.Thing==p);
    if(pending.Any() && !underway) list.Add(new Plan{key=$"sterilize:{p.thingIDNumber}:cancel",kind="sterilize",target_id=p.thingIDNumber,value="cancel",label=p.LabelShortCap+": cancel pending sterilization",cost="Preserves reproductive capacity if operation has not started",risk="Future breeding and feed demand continue; no current operation is interrupted"});
    else if(!pending.Any() && !p.health.hediffSet.HasHediff(HediffDefOf.Sterilized) && !p.health.hediffSet.hediffs.Any(h=>h is Hediff_Pregnant) && !p.Downed && p.BillStack.Bills.Count<15 && p.playerSettings.medCare>=MedicalCareCategory.HerbalOrWorse
     && m.mapPawns.FreeColonistsSpawned.Any(d=>!Protected(d) && d.workSettings!=null && !d.WorkTypeIsDisabled(WorkTypeDefOf.Doctor) && d.workSettings.GetPriority(WorkTypeDefOf.Doctor)>0 && sterilize.PawnSatisfiesSkillRequirements(d) && d.health.capacities.CapableOf(PawnCapacityDefOf.Manipulation) && !p.IsForbidden(d) && d.CanReserveAndReach(p,PathEndMode.ClosestTouch,Danger.Some)
      && sterilize.ingredients.All(i=>m.listerThings.AllThings.Where(t=>Safe(t) && i.filter.Allows(t) && sterilize.fixedIngredientFilter.Allows(t) && t.def.IsMedicine && p.playerSettings.medCare.AllowsMedicine(t.def) && !t.IsForbidden(d) && d.CanReserveAndReach(t,PathEndMode.ClosestTouch,Danger.Some)).Sum(t=>(float)t.stackCount/Math.Max(1,i.CountRequiredOfFor(t.def,sterilize)))>=1f)))
     list.Add(new Plan{key=$"sterilize:{p.thingIDNumber}:queue",kind="sterilize",target_id=p.thingIDNumber,value="queue",label=p.LabelShortCap+": sterilization surgery bill",cost=string.Join("; ",sterilize.ingredients.Select(i=>i.SummaryFor(sterilize)))+" plus doctor work",risk="Permanent loss of breeding, anesthesia and surgical failure risk. Non-pregnant player-owned animal; bill is not completed surgery; compare sex composition and sustainable herd policy alternatives"});
   }
   foreach(var g in m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal && AutoSlaughterManager.CanEverAutoSlaughter(p)).GroupBy(p=>p.def)) {
    var cfg=m.autoSlaughterManager.configs.FirstOrDefault(c=>c.animal==g.Key); if(cfg==null)continue;
    foreach(int cap in new[]{-1,Math.Max(2,g.Count()),Math.Max(2,(int)Math.Ceiling(g.Count()*0.75))}.Distinct())
     if(cfg.maxTotal!=cap || cfg.allowSlaughterPregnant || cfg.allowSlaughterBonded)
      list.Add(new Plan{key=$"herd:{g.Key.defName}:{cap}",kind="herd",value=g.Key.defName+":"+cap,label=g.Key.LabelCap+" total cap "+cap,cost="Ordinary slaughter may kill excess animals; reduces breeding/products and yields meat after butchering",risk="Protect pregnant and bonded animals; retained sex/age limits also apply; assess explosive deaths, veneration and breeding stock; -1 removes total limit only"});
   }
   foreach(var table in m.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>().Where(t=>t.def.AllRecipes.Any(FoodRecipe))) {
    var room=table.InteractionCell.GetRoom(m);
    if(room==null || room.PsychologicallyOutdoors || !room.Cells.Any(c=>!m.areaManager.Home[c]))continue;
    if(m.mapPawns.AllPawnsSpawned.Any(p=>!p.Dead && !p.Downed && p.HostileTo(Faction.OfPlayer) && p.GetRoom()==room))continue;
    list.Add(new Plan{key=$"kitchenhome:{table.thingIDNumber}",kind="kitchenhome",target_id=table.thingIDNumber,value="home",label=table.LabelShortCap+": include existing enclosed kitchen in home area",cost="Expands ordinary cleaning and fire response labor to current room",risk="Home area controls routine cleaning/fire response; does not clean instantly and may expand worker travel"});
   }
   var kitchenRooms=new HashSet<Room>(m.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>().Where(t=>t.def.AllRecipes.Any(FoodRecipe)).Select(t=>t.InteractionCell.GetRoom(m)).Where(r=>r!=null));
   foreach(var giver in DefDatabase<WorkGiverDef>.AllDefsListForReading.Where(d=>d.defName=="CleanFilth")) {
    var scanner=giver.Worker as WorkGiver_Scanner;if(scanner==null)continue;
    IEnumerable<Thing> targets=giver.defName=="CleanFilth" ? m.listerThings.AllThings.OfType<Filth>().Where(f=>kitchenRooms.Contains(f.GetRoom())).Cast<Thing>() : m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal).Cast<Thing>();
    foreach(var target in targets) foreach(var worker in m.mapPawns.FreeColonistsSpawned.Where(p=>!Protected(p) && p.workSettings!=null && !p.WorkTypeIsDisabled(giver.workType) && p.workSettings.GetPriority(giver.workType)>0))
     if(scanner.MissingRequiredCapacity(worker)==null && !scanner.ShouldSkip(worker,false) && worker.CanReserveAndReach(target,PathEndMode.Touch,Danger.Some) && scanner.HasJobOnThing(worker,target,false))
      list.Add(new Plan{key=$"job:{giver.defName}:{worker.thingIDNumber}:{target.thingIDNumber}",kind="job",target_id=target.thingIDNumber,value=giver.defName+":"+worker.thingIDNumber,label=worker.LabelShortCap+": "+giver.label+" "+target.LabelShortCap,cost="Ordinary worker time and any medicine/feed selected by vanilla workgiver",risk="Does not complete cleaning, feeding, tending or rescue; current non-care task may be interrupted; fresh vanilla workgiver checks apply"});
   }
   var markers=m.listerBuildings.allBuildingsColonist.Select(b=>b.TryGetComp<CompAnimalPenMarker>()).Where(c=>c!=null && c.PenState?.Enclosed==true).ToArray();
   foreach(var marker in markers) foreach(var species in m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal && !p.playerSettings.SupportsAllowedAreas).Select(p=>p.def).Distinct()) {
    bool allowed=marker.AnimalFilter.Allows(species);
    // Exclusion is offered only when another enclosed pen accepts every affected live animal.
    if(!allowed || m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.def==species && marker.AcceptsToPen(p)).All(p=>markers.Any(other=>other!=marker && other.AcceptsToPen(p))))
     list.Add(new Plan{key=$"pen:{marker.parent.thingIDNumber}:{species.defName}:{!allowed}",kind="pen",target_id=marker.parent.thingIDNumber,value=species.defName+":"+(!allowed),label=marker.RenamableLabel+": "+(!allowed ? "allow " : "exclude ")+species.LabelCap,cost="Handlers must perform ordinary roping/transfer work",risk="Alternate accepting enclosed pen required for exclusion; acceptance is not proof of feed or safe route; species separation can reduce grazing pressure"});
   }
   return list;
  }
  public static ApiResult<object> Context(int id) {
   var m=MapHelper.GetMapByID(id); if(m==null)return ApiResult<object>.Fail("Map missing");
   var animals=m.mapPawns.SpawnedPawnsInFaction(Faction.OfPlayer).Where(p=>p.RaceProps.Animal).Select(p=>new{id=p.thingIDNumber,label=p.LabelShortCap,species=p.def.defName,gender=p.gender.ToString(),age=p.ageTracker.AgeBiologicalYearsFloat,food=p.needs?.food?.CurLevelPercentage,rest=p.needs?.rest?.CurLevelPercentage,downed=p.Downed,pregnant=p.health.hediffSet.hediffs.Any(h=>h is Hediff_Pregnant),medical_care=p.playerSettings?.medCare.ToString(),area=p.playerSettings?.AreaRestrictionInPawnCurrentMap?.Label,diet=p.RaceProps.foodType.ToString(),health=p.health.hediffSet.hediffs.Where(h=>h.Visible).Select(h=>new{def_name=h.def.defName,severity=h.Severity,stage_index=h.CurStageIndex,life_threatening=h.CurStage?.lifeThreatening ?? false}).ToArray(),inspect=p.GetInspectString()}).ToArray();
   var food_pawns=m.mapPawns.FreeColonistsSpawned.Where(p=>p.foodRestriction?.Configurable==true).Select(p=>new{id=p.thingIDNumber,label=p.LabelShortCap,food=p.needs?.food?.CurLevelPercentage,downed=p.Downed,current_policy=p.foodRestriction.CurrentFoodPolicy?.id,health=p.health.hediffSet.hediffs.Where(h=>h.Visible).Select(h=>new{def_name=h.def.defName,severity=h.Severity,stage_index=h.CurStageIndex,life_threatening=h.CurStage?.lifeThreatening ?? false}).ToArray()}).ToArray();
   var pens=m.listerBuildings.allBuildingsColonist.Select(b=>b.TryGetComp<CompAnimalPenMarker>()).Where(c=>c!=null).Select(c=> {var f=c.PenFoodCalculator; f.ResetAndProcessPen(c);return new{id=c.parent.thingIDNumber,label=c.RenamableLabel,enclosed=c.PenState?.Enclosed,pasture_nutrition_per_day=f.NutritionPerDayToday,consumption_per_day=f.SumNutritionConsumptionPerDay,stockpiled_nutrition=f.sumStockpiledNutritionAvailableNow,inspect=c.CompInspectStringExtra()};}).ToArray();
   var cooking=DefDatabase<WorkTypeDef>.GetNamedSilentFail("Cooking");
   var medicines=m.listerThings.AllThings.Where(t=>t.def.IsMedicine && Safe(t)).GroupBy(t=>t.def).Select(g=>new{def_name=g.Key.defName,count=g.Sum(t=>t.stackCount)}).ToArray();
   var doctors=m.mapPawns.FreeColonistsSpawned.Where(p=>p.workSettings!=null && !p.WorkTypeIsDisabled(WorkTypeDefOf.Doctor) && p.workSettings.GetPriority(WorkTypeDefOf.Doctor)>0 && !Protected(p)).Select(p=>new{id=p.thingIDNumber,label=p.LabelShortCap,medicine_skill=p.skills?.GetSkill(SkillDefOf.Medicine)?.Level}).ToArray();
   var cooks=m.mapPawns.FreeColonistsSpawned.Where(p=>cooking!=null && p.workSettings!=null && !p.WorkTypeIsDisabled(cooking)).Select(p=>new{id=p.thingIDNumber,label=p.LabelShortCap,cooking_skill=p.skills?.GetSkill(SkillDefOf.Cooking)?.Level,priority=p.workSettings.GetPriority(cooking),poison_chance=p.GetStatValue(StatDefOf.FoodPoisonChance),protected_care_job=Protected(p)}).ToArray();
   var perishables=m.listerThings.AllThings.Where(t=>t.TryGetComp<CompRottable>()!=null && (t.def.ingestible!=null || t is Corpse)).Select(t=>new{id=t.thingIDNumber,def_name=t.def.defName,count=t.stackCount,temperature=t.AmbientTemperature,ticks_until_rot=t.TryGetComp<CompRottable>().TicksUntilRotAtCurrentTemp,stage=t.TryGetComp<CompRottable>().Stage.ToString(),eligible=Safe(t)}).ToArray();
   var tables=m.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>().Where(t=>t.def.AllRecipes.Any(FoodRecipe)).Select(t=>new{id=t.thingIDNumber,label=t.LabelShortCap,temperature=t.AmbientTemperature,cleanliness=t.InteractionCell.GetRoom(m)?.GetStat(RoomStatDefOf.Cleanliness),home_cells=t.InteractionCell.GetRoom(m)?.Cells.Count(c=>m.areaManager.Home[c]),bills=t.BillStack.Bills.Select(b=>new{recipe=b.recipe.defName,suspended=b.suspended}).ToArray()}).ToArray();
   var food=m.listerThings.AllThings.Where(t=>t.def.ingestible!=null).GroupBy(t=>t.def).Select(g=>new{def_name=g.Key.defName,nutrition=g.Sum(t=>t.GetStatValue(StatDefOf.Nutrition)*t.stackCount),fresh_eligible_nutrition=g.Where(Safe).Sum(t=>t.GetStatValue(StatDefOf.Nutrition)*t.stackCount),food_type=g.Key.ingestible.foodType.ToString()}).ToArray();
   var storages=m.listerBuildings.allBuildingsColonist.OfType<Building_Storage>().Select(b=>new{id=b.thingIDNumber,label=b.LabelShortCap,temperature=b.AmbientTemperature,priority=(int)b.GetStoreSettings().Priority,linked_storage_count=m.listerBuildings.allBuildingsColonist.OfType<Building_Storage>().Count(other=>other.GetStoreSettings()==b.GetStoreSettings()),allowed_food=b.GetStoreSettings().filter.AllowedThingDefs.Where(d=>d.ingestible!=null).Select(d=>d.defName).ToArray()}).ToArray();
   var areas=m.areaManager.AllAreas.OfType<Area_Allowed>().Select(a=>new{id=a.ID,label=a.Label,cells=a.TrueCount,fire_cells=a.ActiveCells.Count(c=>c.GetFirstThing<Fire>(m)!=null),min_temperature=a.ActiveCells.Any() ? a.ActiveCells.Min(c=>c.GetTemperature(m)) : 0f,max_temperature=a.ActiveCells.Any() ? a.ActiveCells.Max(c=>c.GetTemperature(m)) : 0f,foods=m.listerThings.AllThings.Where(t=>a[t.Position] && t.def.ingestible!=null && Safe(t)).Select(t=>t.def.defName).Distinct().ToArray(),animal_beds=m.listerBuildings.allBuildingsColonist.OfType<Building_Bed>().Count(b=>b.def.building.bed_humanlike==false && a[b.Position])}).ToArray();
   var stockpiles=m.zoneManager.AllZones.OfType<Zone_Stockpile>().Where(z=>z.Cells.Any()).Select(z=>new{id=z.ID,label=z.label,cells=z.Cells.Count,space_remaining=z.SpaceRemaining,priority=(int)z.settings.Priority,temperature=z.Cells.Average(c=>c.GetTemperature(m)),roofed_fraction=z.Cells.Count(c=>c.Roofed(m))/(float)z.Cells.Count,allowed_food=z.settings.filter.AllowedThingDefs.Where(d=>d.ingestible!=null).Select(d=>d.defName).ToArray()}).ToArray();
   var diets=Current.Game.foodRestrictionDatabase.AllFoodRestrictions.Select(p=>new{id=p.id,label=p.label,allowed=p.filter.AllowedThingDefs.Select(d=>d.defName).ToArray()}).ToArray();
   var coolers=m.listerBuildings.allBuildingsColonist.Where(b=>b.TryGetComp<CompTempControl>()!=null).Select(b=>new{id=b.thingIDNumber,label=b.LabelShortCap,temperature=b.AmbientTemperature,target=b.TryGetComp<CompTempControl>().targetTemperature,powered=b.TryGetComp<CompPowerTrader>()?.PowerOn}).ToArray();
   var fishing=ModsConfig.OdysseyActive ? m.zoneManager.AllZones.OfType<Zone_Fishing>().Select(z=>new{id=z.ID,label=z.label,allowed=z.Allowed,should_fish=z.ShouldFishNow,fishable=z.HasAnyFishableCells,frozen=z.AllFishableCellsFrozen,mode=z.repeatMode.ToString(),repeat=z.repeatCount,target=z.targetCount,population_floor=z.targetPopulationPct,population=z.Cells.Count>0?m.waterBodyTracker.PopulationPercentAt(z.Cells[0]):0,owned_fish=z.OwnedFishCount}).ToArray() : null;
   return ApiResult<object>.Ok(new {available=true,options=Plans(m),fishing,odyssey_active=ModsConfig.OdysseyActive,animals,food_pawns,pens,tables,cooks,doctors,medicines,perishables,food,storages,stockpiles,areas,diets,coolers,outdoor_temperature=m.mapTemperature.OutdoorTemp,herds=m.autoSlaughterManager.configs.Select(c=>new{species=c.animal.defName,total=c.maxTotal,males=c.maxMales,females=c.maxFemales,young_males=c.maxMalesYoung,young_females=c.maxFemalesYoung,allow_pregnant=c.allowSlaughterPregnant,allow_bonded=c.allowSlaughterBonded}).ToArray()});
  }
  public static ApiResult<object> Policy(SustenancePolicyDto request) {
   var m=MapHelper.GetMapByID(request.MapId);if(m==null)return ApiResult<object>.Fail("Map missing");
   var plan=Plans(m).FirstOrDefault(p=>p.key==request.Key);if(plan==null)return ApiResult<object>.Ok(new{applied=false,reason="live_option_unavailable"});
   var thing=m.listerThings.AllThings.FirstOrDefault(t=>t.thingIDNumber==plan.target_id);
   switch(plan.kind) {
    case "kitchenhome":foreach(var cell in ((Building_WorkTable)thing).InteractionCell.GetRoom(m).Cells)m.areaManager.Home[cell]=true;break;
    case "bill":
     var table=(Building_WorkTable)thing;var recipe=DefDatabase<RecipeDef>.GetNamed(plan.value);
     var bill=FoodBill(table,recipe);bool adding=!table.BillStack.Bills.Contains(bill);
     bill.repeatMode=BillRepeatModeDefOf.RepeatCount;bill.repeatCount=1;bill.suspended=false;
     if(adding){bill.InitializeAfterClone();table.BillStack.AddBill(bill);}break;
    case "fishpolicy":var fishPolicyZone=m.zoneManager.AllZones.OfType<Zone_Fishing>().First(z=>z.ID==plan.target_id);fishPolicyZone.repeatMode=FishRepeatMode.RepeatCount;fishPolicyZone.repeatCount=1;break;
    case "fishzone":var newFishZone=new Zone_Fishing(m.zoneManager);newFishZone.repeatMode=FishRepeatMode.RepeatCount;newFishZone.repeatCount=1;m.zoneManager.RegisterZone(newFishZone);foreach(var encodedCell in plan.value.Split(';')){var coords=encodedCell.Split(',');newFishZone.AddCell(new IntVec3(int.Parse(coords[0]),0,int.Parse(coords[1])));}break;
    case "customdiet":
     var dietPawn=(Pawn)thing;var dietParts=plan.value.Split(':');var dedicatedLabel="Laya food "+dietPawn.thingIDNumber;
     var dedicated=Current.Game.foodRestrictionDatabase.AllFoodRestrictions.FirstOrDefault(f=>f.label==dedicatedLabel);
     if(dedicated!=null && PawnsFinder.AllMapsCaravansAndTravellingTransporters_Alive.Any(p=>p!=dietPawn && p.foodRestriction?.CurrentFoodPolicy==dedicated))dedicated=null;
     if(dedicated==null){dedicated=Current.Game.foodRestrictionDatabase.MakeNewFoodRestriction();dedicated.label=dedicatedLabel;}
     if(dedicated!=dietPawn.foodRestriction.CurrentFoodPolicy)dedicated.CopyFrom(dietPawn.foodRestriction.CurrentFoodPolicy);
     dedicated.filter.SetAllow(DefDatabase<ThingDef>.GetNamed(dietParts[0]),bool.Parse(dietParts[1]));dietPawn.foodRestriction.CurrentFoodPolicy=dedicated;break;
    case "gather":var gatherParts=plan.value.Split(':');var handler=m.mapPawns.FreeColonistsSpawned.First(p=>p.thingIDNumber==int.Parse(gatherParts[1]));var gatherer=(WorkGiver_Scanner)DefDatabase<WorkGiverDef>.GetNamed(gatherParts[0]).Worker;var gatherJob=gatherer.JobOnThing(handler,thing,false);if(gatherJob==null)return ApiResult<object>.Ok(new{applied=false,reason="gather_unavailable"});handler.jobs.TryTakeOrderedJob(gatherJob);if(handler.CurJob!=gatherJob)return ApiResult<object>.Ok(new{applied=false,reason="gather_not_started"});break;
    case "fish":var fisher=(Pawn)thing;var fishGiver=DefDatabase<WorkGiverDef>.GetNamed(plan.value.Split(':')[0]).Worker;var fishJob=fishGiver.NonScanJob(fisher);if(fishJob==null || fishJob.targetA.Cell.GetZone(m)?.ID!=int.Parse(plan.value.Split(':')[1]))return ApiResult<object>.Ok(new{applied=false,reason="native_fishing_unavailable"});fisher.jobs.TryTakeOrderedJob(fishJob);if(fisher.CurJob!=fishJob)return ApiResult<object>.Ok(new{applied=false,reason="fishing_not_started"});break;
    case "release":if(bool.Parse(plan.value))m.designationManager.AddDesignation(new Designation(thing,DesignationDefOf.ReleaseAnimalToWild));else m.designationManager.RemoveDesignation(m.designationManager.DesignationOn(thing,DesignationDefOf.ReleaseAnimalToWild));break;
    case "sterilize":var animal=(Pawn)thing;if(plan.value=="queue")HealthCardUtility.CreateSurgeryBill(animal,RecipeDefOf.Sterilize,null);else foreach(var pending in animal.BillStack.Bills.Where(b=>b.recipe==RecipeDefOf.Sterilize).ToArray())animal.BillStack.Delete(pending);break;
    case "job": var jobParts=plan.value.Split(':');var worker=m.mapPawns.FreeColonistsSpawned.First(p=>p.thingIDNumber==int.Parse(jobParts[1]));var scanner=(WorkGiver_Scanner)DefDatabase<WorkGiverDef>.GetNamed(jobParts[0]).Worker;var job=scanner.JobOnThing(worker,thing,false);if(job==null)return ApiResult<object>.Ok(new{applied=false,reason="ordinary_job_unavailable"});worker.jobs.TryTakeOrderedJob(job);if(worker.CurJob!=job)return ApiResult<object>.Ok(new{applied=false,reason="ordinary_job_not_started"});break;
    case "pen": var penParts=plan.value.Split(':');thing.TryGetComp<CompAnimalPenMarker>().AnimalFilter.SetAllow(DefDatabase<ThingDef>.GetNamed(penParts[0]),bool.Parse(penParts[1]));break;
    case "diet": ((Pawn)thing).foodRestriction.CurrentFoodPolicy=Current.Game.foodRestrictionDatabase.AllFoodRestrictions.First(p=>p.id.ToString()==plan.value);break;
    case "cooler": thing.TryGetComp<CompTempControl>().targetTemperature=int.Parse(plan.value);break;
    case "stockpile":var zone=m.zoneManager.AllZones.OfType<Zone_Stockpile>().First(z=>z.ID==plan.target_id);zone.settings.Priority=(StoragePriority)int.Parse(plan.value);zone.Notify_SettingsChanged();break;
    case "stockfood":var foodZone=m.zoneManager.AllZones.OfType<Zone_Stockpile>().First(z=>z.ID==plan.target_id);foodZone.settings.filter.SetAllow(DefDatabase<ThingDef>.GetNamed(plan.value),true);foodZone.Notify_SettingsChanged();break;
    case "storage": var storage=(Building_Storage)thing;storage.GetStoreSettings().Priority=(StoragePriority)int.Parse(plan.value);storage.Notify_SettingsChanged();break;
    case "care": ((Pawn)thing).playerSettings.medCare=(MedicalCareCategory)int.Parse(plan.value);break;
    case "area": ((Pawn)thing).playerSettings.AreaRestrictionInPawnCurrentMap=m.areaManager.AllAreas.OfType<Area_Allowed>().First(a=>a.ID.ToString()==plan.value);break;
    case "herd":var parts=plan.value.Split(':');var config=m.autoSlaughterManager.configs.First(c=>c.animal.defName==parts[0]);config.maxTotal=int.Parse(parts[1]);config.allowSlaughterPregnant=false;config.allowSlaughterBonded=false;m.autoSlaughterManager.Notify_ConfigChanged();break;
    default:return ApiResult<object>.Ok(new{applied=false,reason="unsupported"});
   }
   return ApiResult<object>.Ok(new{applied=true,reason=plan.kind=="bill" ? "bill_accepted_not_produced" : "ordinary_policy_changed"});
  }
 }
}
