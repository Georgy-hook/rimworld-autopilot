using System.Net;
using System.Threading.Tasks;
using RIMAPI.Core;
using RIMAPI.Http;
using RIMAPI.Helpers;
using RIMAPI.Models;

namespace RIMAPI.Controllers
{
    public class CapabilitiesController : BaseController
    {
        [Get("/api/v1/plants/catalog")]
        public async Task Plants(HttpListenerContext context)
        {
            int? x = int.TryParse(context.Request.QueryString["center_x"], out int px) ? px : (int?)null;
            int? z = int.TryParse(context.Request.QueryString["center_z"], out int pz) ? pz : (int?)null;
            await context.SendJsonResponse(PlantAutomationHelper.Catalog(RequestParser.GetMapId(context), x, z));
        }
        [Post("/api/v1/map/zone/growing/crop")]
        public async Task Crop(HttpListenerContext context)
        {
            await context.SendJsonResponse(PlantAutomationHelper.SetCrop(await context.Request.ReadBodyAsync<SetCropRequestDto>()));
        }
        [Post("/api/v1/map/plants/cut-blight")]
        public async Task Blight(HttpListenerContext context)
        {
            await context.SendJsonResponse(PlantAutomationHelper.CutBlight(await context.Request.ReadBodyAsync<CutBlightRequestDto>()));
        }
        [Get("/api/v1/weapons/catalog")]
        public async Task Weapons(HttpListenerContext context)
        {
            await context.SendJsonResponse(WeaponAutomationHelper.Catalog());
        }
        [Get("/api/v1/medical/augmentations")]
        public async Task Augmentations(HttpListenerContext context)
        {
            await context.SendJsonResponse(AugmentationAutomationHelper.Context(RequestParser.GetMapId(context)));
        }
        [Post("/api/v1/medical/augmentation")]
        public async Task Install(HttpListenerContext context)
        {
            await context.SendJsonResponse(AugmentationAutomationHelper.Install(await context.Request.ReadBodyAsync<AugmentationRequestDto>()));
        }
        [Post("/api/v1/map/animal/training")]
        public async Task Training(HttpListenerContext context)
        {
            await context.SendJsonResponse(AnimalTrainingAutomationHelper.Configure(await context.Request.ReadBodyAsync<AnimalTrainingRequestDto>()));
        }
        [Post("/api/v1/combat/animals/release")]
        public async Task Release(HttpListenerContext context)
        {
            await context.SendJsonResponse(AnimalTrainingAutomationHelper.Release(await context.Request.ReadBodyAsync<ReleaseAnimalsRequestDto>()));
        }
    }
}
