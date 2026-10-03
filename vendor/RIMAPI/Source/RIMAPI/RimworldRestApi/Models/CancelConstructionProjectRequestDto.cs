namespace RIMAPI.Models
{
    public class CancelConstructionProjectRequestDto
    {
        public int MapId { get; set; }
        public int ProjectThingId { get; set; }
        public string ExpectedDefName { get; set; }
        public string ReplacementStuffDefName { get; set; }
    }
}
