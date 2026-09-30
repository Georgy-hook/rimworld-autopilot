using System.Linq;
using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Models;
using RimWorld;
using Verse;

namespace RIMAPI.Controllers
{
    public class IdeologyController
    {
        [Get("/api/v1/colony/ideology")]
        [EndpointMetadata("Get the player ideology, relevant precepts, and exact ritual building definitions")]
        public async Task GetIdeology(HttpListenerContext context)
        {
            var dto = new IdeologyContextDto
            {
                Active = ModsConfig.IdeologyActive,
                SlaveCount = Find.CurrentMap?.mapPawns.AllPawnsSpawned.Count(p => p.IsSlaveOfColony && !p.Dead) ?? 0,
            };
            var ideo = Faction.OfPlayer?.ideos?.PrimaryIdeo;
            if (ModsConfig.IdeologyActive && ideo != null)
            {
                dto.Name = ideo.name;
                dto.Memes = ideo.memes?.Select(m => m.LabelCap.ToString()).ToList() ?? dto.Memes;
                dto.Precepts = ideo.PreceptsListForReading
                    .Where(p => p?.def != null)
                    .Select(p => p.def.defName)
                    .Distinct()
                    .Take(100)
                    .ToList();
                dto.RitualBuildings = ideo.PreceptsListForReading
                    .OfType<Precept_Building>()
                    .Where(p => p.ThingDef != null && p.ThingDef.isAltar)
                    .Select(p => new IdeologyBuildingDto
                    {
                        DefName = p.ThingDef.defName,
                        Label = p.ThingDef.LabelCap.ToString(),
                        PreceptName = p.LabelCap.ToString(),
                        CostStuffCount = p.ThingDef.CostStuffCount,
                        SizeX = p.ThingDef.size.x,
                        SizeZ = p.ThingDef.size.z,
                    })
                    .ToList();
            }
            await context.SendJsonResponse(ApiResult<IdeologyContextDto>.Ok(dto));
        }
    }
}
