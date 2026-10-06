namespace RIMAPI.Models {
 public class MentalSafetyOrderDto { public string DefenceKey {get;set;} public int MapId {get;set;} public string Key {get;set;} public string Session {get;set;} public bool Cancel {get;set;} public MentalSafetyOptionDto Option {get;set;} }
 public class MentalSafetyOptionDto {
  public string Key {get;set;} public string Session {get;set;} public string Kind {get;set;}
  public int AggressorId {get;set;} public int VictimId {get;set;} public int ActorId {get;set;}
  public int? BedId {get;set;} public PositionDto Cell {get;set;} public float? ArrestChance {get;set;}
  public string Label {get;set;} public string Risk {get;set;}
 }
}