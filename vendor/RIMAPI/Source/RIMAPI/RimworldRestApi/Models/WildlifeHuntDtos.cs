using System.Collections.Generic;
namespace RIMAPI.Models {
 public class WildlifeHuntOrderDto { public int MapId {get;set;} public int TargetId {get;set;} public string Mode {get;set;} public List<int> PawnIds {get;set;} = new List<int>(); public List<int> OwnedDraftIds {get;set;} = new List<int>(); }
}
