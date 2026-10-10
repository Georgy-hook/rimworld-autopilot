using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;

namespace RIMAPI.Models
{
    public class ThingDto
    {
        public bool? Blighted { get; set; }
        public bool? IsCultivated { get; set; }
        public bool? Dying { get; set; }
        public bool? DyingFromPollution { get; set; }
        public bool? DyingFromNoPollution { get; set; }
        public bool? IsDesignatedForCut { get; set; }
        public float? GrowthRate { get; set; }
        public float? DaysUntilHarvestEstimate { get; set; }
        public int ThingId { get; set; }
        public string DefName { get; set; }
        public string Label { get; set; }
        public List<string> Categories { get; set; }
        public PositionDto Position { get; set; }
        public int Rotation { get; set; }
        public PositionDto Size { get; set; }
        public int StackCount { get; set; }
        public double MarketValue { get; set; }
        public bool IsForbidden { get; set; }
        public int Quality { get; set; }
        public string StuffDefName { get; set; }
        public int HitPoints { get; set; }
        public int MaxHitPoints { get; set; }
        public string Description { get; set; }
        public float Growth { get; set; }
        public bool HarvestableNow { get; set; }
        public bool IsDesignatedForHarvest { get; set; }
        public int HarvestYield { get; set; }
        public string HarvestedThingDef { get; set; }
        public string InnerDefName { get; set; }
        public int InnerQuality { get; set; } = -1;
        public float Beauty { get; set; }
        public string RotStage { get; set; }
        public int? TicksUntilRot { get; set; }
        public int? CorpseInnerPawnId { get; set; }
        public int? CorpseDeathTick { get; set; }
        public bool? CanButcher { get; set; }

        public static ThingDto ToDto(Thing thing)
        {
            var dto = new ThingDto
            {
                ThingId = thing.thingIDNumber,
                DefName = thing.def.defName,
                Label = thing.Label,
                Categories = thing.def.thingCategories?.Select(c => c.defName).ToList() ?? new List<string>(),
                Position = new PositionDto
                {
                    X = thing.Position.x,
                    Y = thing.Position.y,
                    Z = thing.Position.z,
                },
                StackCount = thing.stackCount,
                MarketValue = thing.MarketValue,
                IsForbidden = thing.IsForbidden(Faction.OfPlayer),
                HitPoints = thing.HitPoints,
                MaxHitPoints = thing.MaxHitPoints,
                Rotation = thing.Rotation.AsInt,

                // Map the new fields
                StuffDefName = thing.Stuff?.defName,
                Description = thing.DescriptionDetailed
            };

            // Safely get Quality
            var qualityComp = thing.TryGetComp<CompQuality>();
            var rot = thing.TryGetComp<CompRottable>();
            dto.RotStage = rot?.Stage.ToString();
            dto.TicksUntilRot = rot?.TicksUntilRotAtCurrentTemp;
            if (thing is Corpse corpse)
            {
                dto.CorpseInnerPawnId = corpse.InnerPawn?.thingIDNumber;
                dto.CorpseDeathTick = corpse.timeOfDeath;
                dto.CanButcher = corpse.InnerPawn?.RaceProps.Animal == true && corpse.InnerPawn.RaceProps.IsFlesh
                    && (rot?.Stage ?? RimWorld.RotStage.Fresh) == RimWorld.RotStage.Fresh;
            }
            if (qualityComp != null)
            {
                dto.Quality = (int)qualityComp.Quality;
            }

            return dto;
        }
    }

    public class SetForbiddenRequestDto
    {
        public List<int> ThingIds { get; set; }
        public int MapId { get; set; }
        public bool Forbidden { get; set; }
    }

    public class HarvestPlantsRequestDto
    {
        public int MapId { get; set; }
        public List<int> PlantIds { get; set; }
    }

    public class ThingSourcesDto
    {
        public string DefName { get; set; }
        public string Label { get; set; }
        public List<string> ThingCategories { get; set; }

        // -- Acquisition Flags --
        public bool CanCraft { get; set; }
        public bool CanTrade { get; set; }
        public bool CanHarvest { get; set; } // Plants
        public bool CanMine { get; set; }    // Ores
        public bool CanButcher { get; set; } // Meat/Leather

        // -- Detailed Sources --
        public List<string> CraftingRecipes { get; set; } // e.g. "Smelt metal from slag"
        public List<string> HarvestedFrom { get; set; }   // e.g. "Oak tree", "Corn plant"
        public List<string> MinedFrom { get; set; }       // e.g. "Compacted machinery"
        public List<string> TradeTags { get; set; }       // e.g. "ExoticMisc", "ResourcesRaw"
    }
}
