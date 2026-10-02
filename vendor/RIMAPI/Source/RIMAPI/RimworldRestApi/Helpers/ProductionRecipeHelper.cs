using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;
using Verse.AI;

namespace RIMAPI.Helpers
{
    public static class ProductionRecipeHelper
    {
        public sealed class Choice
        {
            public string key;
            public int building_id;
            public string recipe;
            public string material;
            public string category;
            public int gestation_cycles;
            public string label;
            public string cost;
            public string risk;
            public int[] worker_ids;
        }

        private sealed class RecipeInfo
        {
            public bool Food;
            public string Category;
            public string Cost;
        }

        // Def characteristics are immutable after loading; availability and all pawn/map state are read afresh.
        private static readonly Dictionary<RecipeDef, RecipeInfo> recipeInfo = new Dictionary<RecipeDef, RecipeInfo>();

        private static RecipeInfo Info(RecipeDef recipe)
        {
            if (recipeInfo.TryGetValue(recipe, out RecipeInfo cached)) return cached;
            var info = new RecipeInfo
            {
                Food = recipe.products.Any(p => p.thingDef.ingestible != null && !p.thingDef.IsDrug
                    && p.thingDef.ingestible.foodType != FoodTypeFlags.None) || recipe.defName == "ButcherCorpseFlesh",
                Category = recipe.gestationCycles > 0 || recipe.mechanitorOnlyRecipe ? "mech"
                    : recipe.products.Any(p => p.thingDef.IsMedicine) ? "medicine"
                    : recipe.products.Any(p => p.thingDef.IsDrug) ? "drugs"
                    : recipe.products.Any(p => p.thingDef.IsWeapon || p.thingDef.IsApparel) ? "equipment" : "materials",
                Cost = string.Join("; ", recipe.ingredients.Select(i => i.SummaryFor(recipe)))
            };
            recipeInfo[recipe] = info;
            return info;
        }

        private static bool Protected(Pawn pawn)
        {
            return pawn.Dead || pawn.Downed || pawn.Drafted || pawn.InMentalState
                || pawn.CurJobDef == JobDefOf.DoBill || pawn.CurJobDef == JobDefOf.TendPatient
                || pawn.CurJobDef == JobDefOf.Rescue || pawn.CurJobDef == JobDefOf.FeedPatient;
        }

        private static bool UnsafeDef(ThingDef def)
        {
            return def.ingestible?.sourceDef?.race?.Humanlike == true
                || (def.comps?.OfType<CompProperties_Hatcher>().Any() ?? false);
        }

        private static bool Stock(Thing thing)
        {
            return (thing.def.category == ThingCategory.Item || thing is Corpse)
                && !thing.IsForbidden(Faction.OfPlayer) && !thing.IsBurning()
                && (thing.TryGetComp<CompRottable>() == null || thing.TryGetComp<CompRottable>().Stage == RotStage.Fresh)
                && !(thing is Corpse corpse && corpse.InnerPawn.RaceProps.Humanlike) && !UnsafeDef(thing.def);
        }

        internal static Bill_Production Trial(Building_WorkTable table, RecipeDef recipe, string material, bool allowSensitive = false)
        {
            // Parameterless native constructors keep observation from consuming persistent bill IDs.
            Bill_Production bill = recipe.UsesUnfinishedThing ? (Bill_Production)new Bill_ProductionWithUft()
                : recipe.mechResurrection ? new Bill_ResurrectMech()
                : recipe.gestationCycles > 0 ? new Bill_ProductionMech()
                : recipe.formingTicks > 0 ? new Bill_Autonomous()
                : new Bill_Production();
            bill.recipe = recipe;
            bill.ingredientFilter = new ThingFilter();
            bill.ingredientFilter.CopyAllowancesFrom(recipe.defaultIngredientFilter);
            if (bill == null) return null;
            bill.billStack = table.BillStack;
            bill.repeatMode = BillRepeatModeDefOf.RepeatCount;
            bill.repeatCount = 1;
            foreach (ThingDef def in bill.ingredientFilter.AllowedThingDefs.ToArray())
                if ((!allowSensitive && UnsafeDef(def)) || material != null && def.IsStuff && def.defName != material)
                    bill.ingredientFilter.SetAllow(def, false);
            return bill;
        }

        private static Bill_Production Reusable(Building_WorkTable table, Bill_Production trial)
        {
            var allowed = new HashSet<ThingDef>(trial.ingredientFilter.AllowedThingDefs);
            return table.BillStack.Bills.OfType<Bill_Production>().FirstOrDefault(b => b.recipe == trial.recipe
                && b.GetType() == trial.GetType() && b.repeatMode == BillRepeatModeDefOf.RepeatCount
                && b.repeatCount == 0 && allowed.SetEquals(b.ingredientFilter.AllowedThingDefs));
        }

        private static bool Pending(Bill bill)
        {
            return !(bill is Bill_Production production) || production.repeatMode != BillRepeatModeDefOf.RepeatCount
                || production.repeatCount > 0;
        }

        internal static bool Supplies(IReadOnlyList<Thing> pool, Bill_Production bill)
        {
            RecipeDef recipe = bill.recipe;
            var giver = (Thing)bill.billStack.billGiver;
            float radiusSquared = bill.ingredientSearchRadius * bill.ingredientSearchRadius;
            // Thing-level filtering preserves special allowances, hit-point/quality ranges and reused search radius.
            var remaining = pool.Where(t => bill.IsFixedOrAllowedIngredient(t)
                && (t.Position - giver.Position).LengthHorizontalSquared < radiusSquared)
                .ToDictionary(t => t, t => t.stackCount);
            foreach (IngredientCount ingredient in recipe.ingredients.OrderBy(i => i.filter.AllowedDefCount))
            {
                if (ingredient.GetBaseCount() <= 0) continue;
                Thing[] eligible = remaining.Keys.Where(t => remaining[t] > 0 && ingredient.filter.Allows(t)
                    && (ingredient.IsFixedIngredient || bill.ingredientFilter.Allows(t))).ToArray();
                if (!recipe.allowMixingIngredients)
                {
                    var group = eligible.GroupBy(t => t.def).FirstOrDefault(g => g.Sum(t => remaining[t])
                        >= ingredient.CountRequiredOfFor(g.Key, recipe, bill));
                    if (group == null) return false;
                    int needed = ingredient.CountRequiredOfFor(group.Key, recipe, bill);
                    foreach (Thing thing in group)
                    {
                        int take = Math.Min(remaining[thing], needed);
                        remaining[thing] -= take;
                        needed -= take;
                        if (needed <= 0) break;
                    }
                    continue;
                }
                float neededValue = ingredient.GetBaseCount();
                foreach (Thing thing in eligible.OrderBy(t => recipe.IngredientValueGetter.ValuePerUnitOf(t.def)))
                {
                    float perUnit = recipe.IngredientValueGetter.ValuePerUnitOf(thing.def);
                    if (perUnit <= 0) continue;
                    int take = Math.Min(remaining[thing], (int)Math.Ceiling(neededValue / perUnit));
                    remaining[thing] -= take;
                    neededValue -= take * perUnit;
                    if (neededValue <= 0.0001f) break;
                }
                if (neededValue > 0.0001f) return false;
            }
            return true;
        }

        private static bool WorkerReady(Pawn pawn, Building_WorkTable table, WorkTypeDef workType, Bill_Production bill, WorkGiverDef giver)
        {
            RecipeDef recipe = bill.recipe;
            return !Protected(pawn) && workType != null && !table.IsForbidden(pawn)
                && pawn.CanReserve(table) && giver != null && giver.Worker.MissingRequiredCapacity(pawn) == null && pawn.workSettings != null
                && !pawn.WorkTypeIsDisabled(workType) && pawn.workSettings.GetPriority(workType) > 0
                && recipe.PawnSatisfiesSkillRequirements(pawn)
                && (!recipe.mechanitorOnlyRecipe || MechanitorUtility.IsMechanitor(pawn))
                && bill.PawnAllowedToStartAnew(pawn)
                && pawn.CanReserveAndReach(table.InteractionCell, PathEndMode.OnCell, Danger.Some)
                && (!(table is Building_MechGestator gestator) || gestator.CanBeUsedNowBy(pawn));
        }

        public static List<Choice> Options(Map map)
        {
            var choices = new List<Choice>();
            // One inventory scan per observation and one reach/reservation pass per eligible worker, not per recipe.
            Thing[] stock = map.listerThings.AllThings.Where(Stock).ToArray();
            var reachable = new Dictionary<Pawn, Thing[]>();
            Pawn[] workers = map.mapPawns.FreeColonistsSpawned.Where(p => !Protected(p)).ToArray();
            foreach (Building_WorkTable table in map.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>())
            {
                if (!table.CurrentlyUsableForBills()) continue;
                WorkGiverDef tableGiver = table.GetWorkgiver();
                WorkTypeDef tableWork = tableGiver?.workType;
                foreach (RecipeDef recipe in table.def.AllRecipes)
                {
                    RecipeInfo info = Info(recipe);
                    if (info.Food || recipe.IsSurgery || !recipe.AvailableNow || !recipe.AvailableOnNow(table)
                        || table.BillStack.Bills.Any(b => b.recipe == recipe && Pending(b))) continue;
                    string[] materials = recipe.productHasIngredientStuff
                        ? stock.Where(x => x.def.IsStuff && recipe.ingredients.Count > 0 && recipe.ingredients[0].filter.Allows(x))
                            .Select(x => x.def.defName).Distinct().ToArray() : new string[] { null };
                    foreach (string material in materials)
                    {
                        Bill_Production trial = Trial(table, recipe, material);
                        if (trial == null) continue;
                        Bill_Production reuse = Reusable(table, trial);
                        if (reuse == null && table.BillStack.Bills.Count >= 15) continue;
                        Bill_Production effective = reuse ?? trial;
                        var eligible = new List<int>();
                        foreach (Pawn pawn in workers)
                        {
                            if (!WorkerReady(pawn, table, recipe.requiredGiverWorkType ?? tableWork, effective, tableGiver)) continue;
                            if (!reachable.TryGetValue(pawn, out Thing[] pool))
                            {
                                pool = stock.Where(x => !x.IsForbidden(pawn) && pawn.CanReserveAndReach(x, PathEndMode.ClosestTouch, Danger.Some)).ToArray();
                                reachable[pawn] = pool;
                            }
                            if (Supplies(pool, effective)) eligible.Add(pawn.thingIDNumber);
                        }
                        if (eligible.Count == 0) continue;
                        choices.Add(new Choice
                        {
                            key = $"{table.thingIDNumber}:{recipe.defName}:{material ?? "default"}",
                            building_id = table.thingIDNumber, recipe = recipe.defName, material = material,
                            gestation_cycles = recipe.gestationCycles, category = info.Category,
                            label = table.LabelShortCap + ": " + recipe.LabelCap + (material == null ? "" : " material " + material),
                            cost = info.Cost, worker_ids = eligible.ToArray(),
                            risk = "Scarce ingredients/labor/power; mech bandwidth and waste; biological/drug consequences remain vanilla. No pawn donors allocated."
                        });
                    }
                }
            }
            return choices;
        }

        public static ApiResult<object> Context(int id)
        {
            Map map = MapHelper.GetMapByID(id);
            if (map == null) return ApiResult<object>.Fail("Map missing");
            var scanners = map.listerBuildings.allBuildingsColonist.OfType<Building_SubcoreScanner>().Select(b => new
            {
                id = b.thingIDNumber, label = b.LabelShortCap, state = b.State.ToString(), powered = b.PowerOn,
                loaded = b.AllRequiredIngredientsLoaded, destroys_brain = b.DestroyOccupantBrain,
                occupant = b.Occupant?.thingIDNumber, inspect = b.GetInspectString()
            }).ToArray();
            return ApiResult<object>.Ok(new
            {
                available = true, options = Options(map), subcore_scanners = scanners,
                stocks = map.listerThings.AllThings.Where(Stock).GroupBy(t => t.def.defName)
                    .Select(g => new { def_name = g.Key, count = g.Sum(t => t.stackCount) }).ToArray()
            });
        }

        public static ApiResult<object> Policy(ProductionRecipePolicyDto request)
        {
            Map map = MapHelper.GetMapByID(request.MapId);
            if (map == null) return ApiResult<object>.Fail("Map missing");
            Choice choice = Options(map).FirstOrDefault(c => c.key == request.Key);
            if (choice == null) return ApiResult<object>.Ok(new { applied = false, reason = "recipe_no_longer_available" });
            var table = map.listerBuildings.allBuildingsColonist.OfType<Building_WorkTable>().First(t => t.thingIDNumber == choice.building_id);
            Bill_Production trial = Trial(table, DefDatabase<RecipeDef>.GetNamed(choice.recipe), choice.material);
            Bill_Production bill = Reusable(table, trial);
            if (bill != null)
            {
                if (bill is Bill_Autonomous autonomous) autonomous.Reset();
                bill.repeatCount = 1;
                bill.suspended = false;
            }
            else { trial.InitializeAfterClone(); table.BillStack.AddBill(trial); }
            return ApiResult<object>.Ok(new { applied = true, reason = "finite_loaded_recipe_bill_accepted_not_produced" });
        }
    }
}
