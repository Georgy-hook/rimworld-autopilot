$ErrorActionPreference='Stop'
$taskRepo=Split-Path -Parent $PSScriptRoot
$taskSource=Get-Content -Raw -LiteralPath (Join-Path $taskRepo 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/StorageProfileHelper.cs')
$taskStart=$taskSource.IndexOf('public static HashSet<ThingDef> Definitions(')
$taskEnd=$taskSource.IndexOf('public static bool Specialized(', $taskStart)
if($taskStart -lt 0 -or $taskEnd -le $taskStart){throw 'Native storage definitions boundary missing'}
$taskMethods=$taskSource.Substring($taskStart,$taskEnd-$taskStart)
$taskCode=@'
using System;
using System.Collections.Generic;
using System.Linq;
#pragma warning disable 0649
enum ThingCategory {Item,Building}
enum FoodTypeFlags {None,Vegetable,Meal,Corpse}
enum StoragePriority {Normal=3,Preferred=4}
class Map {}
class ThingCategoryDef {public string defName; public List<ThingCategoryDef> Parents=new List<ThingCategoryDef>();}
class Race {public bool Animal;}
class Ingestible {public FoodTypeFlags foodType=FoodTypeFlags.Vegetable;public ThingDef sourceDef;}
class ThingDef {public string defName;public ThingCategory category=ThingCategory.Item;public bool IsCorpse,IsMedicine,IsNutritionGivingIngestible,IsWeapon,IsApparel;
 public Ingestible ingestible;public Race race;public List<ThingCategoryDef> thingCategories=new List<ThingCategoryDef>();}
static class DefDatabase<T> {public static List<T> AllDefs=new List<T>();}
public static class StorageBoundaryFixture {
METHODS
static ThingDef Def(string name,string category=null,bool food=false) {
 var d=new ThingDef {defName=name}; if(category!=null)d.thingCategories.Add(new ThingCategoryDef {defName=category});
 if(food){d.ingestible=new Ingestible();d.IsNutritionGivingIngestible=true;} DefDatabase<ThingDef>.AllDefs.Add(d);return d;
}
static void Check(bool b,string msg) {if(!b)throw new Exception(msg);}
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
 Check(Definitions("kitchen_inputs").SetEquals(new[]{berries,milk}),"Kitchen raw ingredients/eggs filter");
 Check(Definitions("meals").SetEquals(new[]{meal}),"Meal filter");
 Check(Definitions("cold_food").SetEquals(new[]{berries,milk,meal}),"Cold food must exclude corpses, eggs, metal, drugs");
 Check(Definitions("medicine").SetEquals(new[]{med}),"Medicine filter");
 Check(Definitions("construction").SetEquals(new[]{steel,wood}),"Construction must not steal components from indoor workshop");
 Check(Definitions("workshop_inputs").SetEquals(new[]{steel,component}),"Workshop metals/components must not steal medicine or drugs");
 Check(Definitions("fuel").SetEquals(new[]{wood,chem}),"Fuel filter");
 Check(Definitions("armory").SetEquals(new[]{gun}),"Armory filter");
 Check(Definitions("fresh_carcasses").SetEquals(new[]{corpse}),"Human corpses not animal-food warehouse");
 Check(!Definitions("dry_goods").Contains(berries)&&!Definitions("dry_goods").Contains(chunk)&&!Definitions("dry_goods").Contains(chem),"Dry goods contamination");
 Check(Definitions("unknown").Count==0,"Unknown purpose must be unavailable");
 Check(Priority("workshop_inputs")>Priority("dry_goods"),"Work buffers must outrank overflow");
 return 12;
}
}
'@
$taskCode=$taskCode.Replace('METHODS',$taskMethods.Replace('public static HashSet','private static HashSet').Replace('public static StoragePriority','private static StoragePriority'))
Add-Type -TypeDefinition $taskCode -Language CSharp
[StorageBoundaryFixture]::Run()
