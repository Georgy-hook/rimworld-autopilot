using System.Collections.Generic;
namespace RIMAPI.Models {
 public class MiningOrderDto { public int MapId {get;set;} public string Key {get;set;} }
 public class MiningPlanDto {
  public string Key {get;set;} public int WorkerId {get;set;} public string Worker {get;set;}
  public string Kind {get;set;} = "extract";
  public string OreDef {get;set;} public string ProductDef {get;set;}
  public int VeinCells {get;set;} public List<int> ThingIds {get;set;}
  public List<PositionDto> Cells {get;set;} public int RemainingHp {get;set;}
  public int BaseYield {get;set;} public float NominalMarketValue {get;set;}
  public float MiningSpeed {get;set;} public float MiningYield {get;set;}
  public int MiningSkill {get;set;} public float TravelDistance {get;set;}
  public int? EstimatedWorkTicks {get;set;}
 }
}
