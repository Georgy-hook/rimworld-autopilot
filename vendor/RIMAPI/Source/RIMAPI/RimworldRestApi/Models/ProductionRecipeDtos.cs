namespace RIMAPI.Models { public class ProductionRecipePolicyDto {
 public int MapId {get;set;} public string Key {get;set;} public int? WorkerId {get;set;}
 public string ExpectedInspiration {get;set;} public string ExpectedIdentity {get;set;} public int? ExpectedStartTick {get;set;}
} }
