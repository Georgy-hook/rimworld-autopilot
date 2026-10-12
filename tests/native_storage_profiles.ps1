param([string]$DefinitionAuditJson, [string]$AuditOutputJson)
$ErrorActionPreference='Stop'
$taskRepo=Split-Path -Parent $PSScriptRoot
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/StorageProfileHelper.cs')
$taskStart=$taskSource.IndexOf('public static readonly string[] Roles')
$taskEnd=$taskSource.IndexOf('public static bool Specialized(', $taskStart)
if($taskStart -lt 0 -or $taskEnd -le $taskStart){throw 'Native storage definitions boundary missing'}
$taskMethods=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;
using System.Collections.Generic;
using System.Linq;
#pragma warning disable 0649
enum ThingCategory {Item,Building}
[Flags] enum FoodTypeFlags {None=0,Vegetable=1,Meal=2,Corpse=4,Kibble=8,Plant=16}
enum StoragePriority {Normal=3,Preferred=4}
class Map {}
class ThingCategoryDef {public string defName; public List<ThingCategoryDef> Parents=new List<ThingCategoryDef>();}
class StuffProps {public List<ThingCategoryDef> categories=new List<ThingCategoryDef>();}
class Race {public bool Animal;public bool CanEverEat(ThingDef d) {return d.ingestible!=null&&d.ingestible.foodType!=FoodTypeFlags.Plant;}}
static class ThingDefOf {public static ThingDef Human=new ThingDef {race=new Race()};}
class CompProperties {}
class CompProperties_Explosive:CompProperties {}
class CompProperties_GoldenCube:CompProperties {}
class CompProperties_Studiable:CompProperties {}
class CompProperties_HoldingPlatformTarget:CompProperties {}
class CompProperties_CompAnalyzableBiosignature:CompProperties {}
class CompProperties_SpawnsRevenant:CompProperties {}
class CompProperties_Dissolution:CompProperties {}
class CompProperties_GasOnDamage:CompProperties {}
class UnfinishedThing {}
class MinifiedThing {}
class ProjectionExplosive:CompProperties_Explosive {}
class Ingestible {public FoodTypeFlags foodType=FoodTypeFlags.Vegetable;public ThingDef sourceDef;}
class ThingDef {public string defName;public ThingCategory category=ThingCategory.Item;public bool IsCorpse,IsMedicine,IsNutritionGivingIngestible,IsWeapon,IsApparel;
 public Ingestible ingestible;public Race race;public StuffProps stuffProps;public Type thingClass;public List<CompProperties> comps=new List<CompProperties>();
 public bool Storable=true;public bool EverStorable(bool _) {return Storable;}
 public List<ThingCategoryDef> thingCategories=new List<ThingCategoryDef>();}
static class DefDatabase<T> {public static List<T> AllDefs=new List<T>();}
public static class StorageBoundaryFixture {
METHODS
static ThingDef Def(string name,string category=null,bool food=false) {
 var d=new ThingDef {defName=name}; if(category!=null)d.thingCategories.Add(new ThingCategoryDef {defName=category});
 if(food){d.ingestible=new Ingestible();d.IsNutritionGivingIngestible=true;} DefDatabase<ThingDef>.AllDefs.Add(d);return d;
}
static int checks;
static void Check(bool b,string msg) {checks++;if(!b)throw new Exception(msg);}
public static int Run() {
 var raw=new ThingCategoryDef {defName="FoodRaw"};
 var berries=Def("RawBerries","PlantFoodRaw",true);berries.thingCategories[0].Parents.Add(raw);
 var milk=Def("Milk","AnimalProductRaw",true);milk.thingCategories[0].Parents.Add(raw);
 var eggs=Def("ChickenEggFertilized","EggsFertilized",true);eggs.thingCategories[0].Parents.Add(raw);
 var meal=Def("MealSimple","FoodMeals",true); var steel=Def("Steel","ResourcesRaw");
 var component=Def("ComponentIndustrial","Manufactured"); var wood=Def("WoodLog","ResourcesRaw");
 var chem=Def("Chemfuel","Manufactured");var med=Def("MedicineIndustrial","Medicine");med.IsMedicine=true;med.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Manufactured"});
 var drug=Def("Yayo","Drugs",true);drug.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Manufactured"});
 var corpse=Def("Corpse_Elk",null,true);corpse.IsCorpse=true;corpse.ingestible.sourceDef=new ThingDef {race=new Race {Animal=true}};
 var human=Def("Corpse_Human",null,true);human.IsCorpse=true;human.ingestible.sourceDef=new ThingDef {race=new Race()};
 var chunk=Def("ChunkGranite","StoneChunks");var gun=Def("Gun_Revolver","Weapons");gun.IsWeapon=true;
 chunk.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Chunks"});
 berries.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Foods"});milk.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Foods"});
 meal.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Foods"});
 Check(Definitions("kitchen_inputs").SetEquals(new[]{berries,milk}),"Kitchen raw ingredients/eggs filter");
 Check(Definitions("meals").SetEquals(new[]{meal}),"Meal filter");
 Check(Definitions("cold_food").SetEquals(new[]{berries,milk,meal}),"Cold food must exclude corpses, eggs, metal, drugs");
 Check(Definitions("medicine").SetEquals(new[]{med}),"Medicine filter");
 Check(Definitions("construction").SetEquals(new[]{steel,wood}),"Construction must not steal components from indoor workshop");
 Check(Definitions("workshop_inputs").SetEquals(new[]{component}),"Workshop shelves must exclude bulk metal, medicine and drugs");
 Check(Definitions("fuel").SetEquals(new[]{wood}),"Wood fuel belongs on ground, not a mixed chemfuel shelf");
 Check(Definitions("armory").SetEquals(new[]{gun}),"Armory filter");
 Check(Definitions("fresh_carcasses").SetEquals(new[]{corpse}),"Human corpses not animal-food warehouse");
 Check(!Definitions("dry_goods").Contains(berries)&&!Definitions("dry_goods").Contains(chunk)&&!Definitions("dry_goods").Contains(chem),"Dry goods contamination");
 Check(Definitions("unknown").Count==0,"Unknown purpose must be unavailable");
 Check(Priority("workshop_inputs")>Priority("dry_goods"),"Work buffers must outrank overflow");
 var modMetal=Def("ModAlloy","ResourcesRaw");modMetal.stuffProps=new StuffProps();modMetal.stuffProps.categories.Add(new ThingCategoryDef {defName="Metallic"});
 Check(Definitions("bulk_materials").SetEquals(new[]{steel,wood,modMetal}),"Construction resources belong in free ground storage");
 Check(!Definitions("dry_goods").Contains(steel)&&!Definitions("workshop_inputs").Contains(modMetal),"Bulk metal must not consume warehouse shelves");
 var blocks=Def("BlocksGranite","StoneBlocks");var jade=Def("Jade","ResourcesRaw");
 var modWood=Def("ModLumber","ResourcesRaw");modWood.stuffProps=new StuffProps();modWood.stuffProps.categories.Add(new ThingCategoryDef {defName="Woody"});
 var modStone=Def("ModStone","ResourcesRaw");modStone.stuffProps=new StuffProps();modStone.stuffProps.categories.Add(new ThingCategoryDef {defName="Stony"});
 var hay=Def("Hay","Foods",true);hay.ingestible.foodType=FoodTypeFlags.Plant;
 var kibble=Def("Kibble","Foods",true);kibble.ingestible.foodType=FoodTypeFlags.Kibble;
 var shell=Def("Shell_EMP","MortarShells");shell.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Manufactured"});
 var modBomb=Def("ModExplosive","Manufactured");modBomb.comps.Add(new ProjectionExplosive());
 var unknown=Def("UnknownItem");var waste=Def("Wastepack","ItemsMisc");
 var unfinished=Def("UnfinishedComponent","Unfinished");var minified=Def("MinifiedThing");minified.thingClass=typeof(MinifiedThing);
 var fertilized=Def("EggFertilized","EggsFertilized",true);fertilized.thingCategories[0].Parents.Add(raw);
 var genes=Def("Genepack","ItemsMisc");var embryo=Def("HumanEmbryo","ItemsMisc");var blood=Def("HemogenPack","Foods",true);
 var cube=Def("GoldenCube","ItemsMisc");cube.comps.Add(new CompProperties_GoldenCube());
 var sample=Def("Sample","ItemsMisc");sample.comps.Add(new CompProperties_CompAnalyzableBiosignature());
 var spine=Def("RevenantSpine","ItemsMisc");spine.comps.Add(new CompProperties_SpawnsRevenant());
 var book=Def("TextBook","Books");var implant=Def("BionicArm","BodyParts");var techprint=Def("Techprint","Techprints");
 var cloth=Def("Cloth","Textiles");cloth.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="Manufactured"});
 var chocolate=Def("Chocolate","Foods",true);var leaf=Def("PsychoidLeaves","PlantMatter",true);leaf.thingCategories[0].Parents.Add(new ThingCategoryDef {defName="ResourcesRaw"});
 var inaccessible=Def("InternalGun","Weapons");inaccessible.IsWeapon=true;inaccessible.Storable=false;
 var core=Def("AIPersonaCore","ItemsMisc");var techcore=Def("TechprofSubpersonaCore","ItemsMisc");
 var tusk=Def("ElephantTusk","ItemsMisc");var horn=Def("ThrumboHorn","ItemsMisc");var skull=Def("Skull","ItemsMisc");
 var allowed=KnownShelfItems();
 foreach(var d in new[]{wood,modWood,steel,modMetal,blocks,jade,modStone,hay,chem,shell,modBomb,unknown,waste,unfinished,minified,
                       fertilized,genes,embryo,blood,cube,sample,spine,corpse,human,chunk,inaccessible,skull})
     Check(!allowed.Contains(d),"Unexpected shelf candidate: "+d.defName);
 foreach(var d in new[]{component,med,drug,gun,book,implant,techprint,cloth,chocolate,kibble,leaf,core,techcore,tusk,horn})
     Check(allowed.Contains(d),"Missing reviewed shelf candidate: "+d.defName);
 foreach(string role in Roles)
     Check(ShelfDefinitions(role).All(d=>ShelfExclusionReason(d)==null),"Unsafe profile: "+role);
 Check(ShelfDefinitions("fuel").Count==0&&ShelfDefinitions("construction").Count==0,"Ground-only role cannot buy a shelf");
 Check(!Definitions("cold_food").Contains(kibble)&&!Definitions("kitchen_inputs").Contains(hay),"Animal fodder is not kitchen supply");
 Check(ShelfDefinitions("animal_feed").SetEquals(new[]{kibble}),"Bulk hay stays on covered ground; small kibble buffer may use a shelf");
 Check(ShelfDefinitions("drugs").Contains(drug)&&!ShelfDefinitions("dry_goods").Contains(drug),"Dedicated drug filter");
 Check(ShelfDefinitions("dry_goods").Contains(book)&&!ShelfDefinitions("dry_goods").Contains(shell),"Books protected; shells isolated");
 return checks;
}
public static void Reset() {DefDatabase<ThingDef>.AllDefs.Clear();}
public static void AddAudit(string name,string[] categories,string[] stuff,string[] components,string thingClass,string food,bool nutritious,bool storable) {
 var d=Def(name);d.Storable=storable;
 foreach(string cat in categories)d.thingCategories.Add(new ThingCategoryDef {defName=cat});
 d.IsMedicine=categories.Contains("Medicine");d.IsWeapon=categories.Contains("Weapons");d.IsApparel=categories.Contains("Apparel");
 d.stuffProps=new StuffProps();foreach(string s in stuff)d.stuffProps.categories.Add(new ThingCategoryDef {defName=s});
 if(!string.IsNullOrEmpty(food)) {d.ingestible=new Ingestible();d.ingestible.foodType=food=="Plant"?FoodTypeFlags.Plant:food=="Kibble"?FoodTypeFlags.Kibble:FoodTypeFlags.Vegetable;d.IsNutritionGivingIngestible=nutritious;}
 if(thingClass!=null&&thingClass.StartsWith("Minified"))d.thingClass=typeof(MinifiedThing);
 if(thingClass=="UnfinishedThing")d.thingClass=typeof(UnfinishedThing);
 foreach(string c in components) {var type=typeof(StorageBoundaryFixture).Assembly.GetType(c);if(type!=null&&typeof(CompProperties).IsAssignableFrom(type))d.comps.Add((CompProperties)Activator.CreateInstance(type));}
}
public static string[] Audit(string name) {var d=DefDatabase<ThingDef>.AllDefs.First(x=>x.defName==name);
 return new[]{ShelfExclusionReason(d)??(KnownShelfItems().Contains(d)?"reviewed_shelf_item":"unclassified_no_generic_shelf"),
              string.Join(",",Roles.Where(r=>ShelfDefinitions(r).Contains(d)))};}
}
'@
$taskCode=$taskCode.Replace('METHODS',$taskMethods.Replace('public static HashSet','private static HashSet').Replace('public static StoragePriority','private static StoragePriority').Replace('public static bool','private static bool').Replace('public static string','private static string'))
Add-Type -TypeDefinition $taskCode -Language CSharp
[StorageBoundaryFixture]::Run()
if($DefinitionAuditJson) {
    $taskInventory=Get-Content -Raw -LiteralPath $DefinitionAuditJson | ConvertFrom-Json
    [StorageBoundaryFixture]::Reset()
    foreach($taskItem in $taskInventory.items) {
        [StorageBoundaryFixture]::AddAudit($taskItem.def_name,[string[]]$taskItem.categories,[string[]]$taskItem.stuff_categories,
            [string[]]$taskItem.comps,$taskItem.thing_class,$taskItem.food_type,([double]$taskItem.nutrition -gt 0),
            ($taskItem.categories.Count -gt 0 -or $taskItem.thing_class -like 'Minified*'))
    }
    $taskRows=@(foreach($taskItem in $taskInventory.items) {
        $taskPolicy=[StorageBoundaryFixture]::Audit($taskItem.def_name)
        [pscustomobject]@{def_name=$taskItem.def_name;dlc=$taskItem.dlc;policy=$taskPolicy[0];shelf_roles=$taskPolicy[1]}
    })
    if($AuditOutputJson) {$taskRows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $AuditOutputJson -Encoding utf8}
    $taskRows | Group-Object policy | Select-Object Name,Count | ConvertTo-Json -Compress
}
