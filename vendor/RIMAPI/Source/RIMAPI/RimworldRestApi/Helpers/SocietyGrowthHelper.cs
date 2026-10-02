using System;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using RimWorld;
using Verse;
using RIMAPI.Core;
using RIMAPI.Models;
namespace RIMAPI.Helpers
{
    public static class SocietyGrowthHelper
    {
        private static IEnumerable<ChoiceLetter_GrowthMoment> Letters(Map map) => Find.LetterStack.LettersListForReading.OfType<ChoiceLetter_GrowthMoment>()
            .Where(l=>!l.ArchiveView && !l.choiceMade && !l.TimeoutPassed && l.pawn != null && l.pawn.Map == map && l.pawn.IsColonistPlayerControlled);
        public static bool Pending() => ModsConfig.BiotechActive && Find.LetterStack.LettersListForReading.OfType<ChoiceLetter_GrowthMoment>().Any(l=>!l.ArchiveView && !l.choiceMade && !l.TimeoutPassed && l.pawn != null && l.pawn.Spawned && l.pawn.IsColonistPlayerControlled);
        public static void AddContext(Map map,SocietyContextDto result)
        {
            if(!ModsConfig.BiotechActive)return;
            foreach(var letter in Letters(map))
            {
                bool ready=(letter.passionGainsCount==0 || letter.passionChoices != null) && (letter.traitChoiceCount==0 || letter.traitChoices != null);
                result.GrowthMoments.Add(new{letter_id=letter.ID,pawn_id=letter.pawn.thingIDNumber,name=letter.pawn.LabelShort,growth_tier=letter.growthTier,passion_gains=letter.passionGainsCount,
                    ready=ready,traits=letter.traitChoices?.Select((t,i)=>new{index=i,label=t.Label,description=t.TipString(letter.pawn)}).ToList(),no_trait=letter.noTraitOptionShown,
                    passions=letter.passionChoices?.Select(s=>new{def_name=s.defName,label=s.label,level=letter.pawn.skills.GetSkill(s).Level,current_passion=letter.pawn.skills.GetSkill(s).passion.ToString(),description=s.description}).ToList(),enabled_work=letter.enabledWorkTypes});
                if(!ready)result.NativeOptions.Add(new SocietyNativeOptionDto{Kind="growth_prepare",PawnId=letter.pawn.thingIDNumber,LetterId=letter.ID,Value="prepare",Label=$"Open normal growth choices for {letter.pawn.LabelShort}",
                    Effects=new Dictionary<string,string>{{"benefit",$"{letter.pawn.LabelShort} tier={letter.growthTier}; reveal actual offered choices"},{"risk","Permanent awards are not chosen yet"},{"cost","One native random offer generation; never reroll"},{"inaction","Letter awaits choice until native timeout"},{"uncertainty","Trait/passion alternatives depend on earned growth tier"}}});
                else result.NativeOptions.Add(new SocietyNativeOptionDto{Kind="growth",PawnId=letter.pawn.thingIDNumber,LetterId=letter.ID,Value="select",Label=$"Choose normal growth awards for {letter.pawn.LabelShort}",
                    Effects=new Dictionary<string,string>{{"benefit",$"{letter.pawn.LabelShort} tier={letter.growthTier}; passions={letter.passionGainsCount}"},{"risk","Permanent offered trait/passions; compare drawbacks"},{"cost","Forgoes other offered options"},{"inaction","Native letter timeout may choose automatically"},{"uncertainty","Future role and gene passion effects matter"}}});
            }
        }
        public static ApiResult<CapabilityOrderResultDto> Execute(SocietyNativeRequestDto request)
        {
            Map map=MapHelper.GetMapByID(request.MapId);var result=new CapabilityOrderResultDto{TargetId=request.PawnId};
            var letter=map == null ? null : Letters(map).FirstOrDefault(l=>l.ID==request.LetterId && l.pawn.thingIDNumber==request.PawnId);
            if(letter==null)return ApiResult<CapabilityOrderResultDto>.Fail("Pending native growth letter not found.");
            if(request.Kind=="growth_prepare")
            {
                // Same one-time cache initialization used by OpenLetter, without opening UI.
                var initialize=typeof(ChoiceLetter_GrowthMoment).GetMethod("TrySetChoices",BindingFlags.Instance|BindingFlags.NonPublic);
                if(initialize==null)return ApiResult<CapabilityOrderResultDto>.Fail("Native growth initializer unavailable.");
                initialize.Invoke(letter,null);
                result.Applied=true;result.Reason="native_growth_options_cached; awards_not_selected";
            }
            else if(request.Kind=="growth")
            {
                var skills=(request.SkillDefs ?? new List<string>()).Select(n=>DefDatabase<SkillDef>.GetNamedSilentFail(n)).ToList();
                if(skills.Count != letter.passionGainsCount || skills.Distinct().Count()!=skills.Count || skills.Any(s=>s==null || letter.passionChoices==null || !letter.passionChoices.Contains(s) || letter.pawn.skills.GetSkill(s).passion==Passion.Major))
                {result.Reason="passion_choices_no_longer_valid";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
                Trait trait=null;
                if(request.TraitIndex==-2 && letter.noTraitOptionShown)trait=ChoiceLetter_GrowthMoment.NoTrait;
                else if(request.TraitIndex>=0 && letter.traitChoices!=null && request.TraitIndex<letter.traitChoices.Count)trait=letter.traitChoices[request.TraitIndex];
                else if(letter.traitChoices?.Count>0 || (letter.traitChoiceCount>0 && letter.traitChoices==null))
                {result.Reason="trait_choice_no_longer_valid";return ApiResult<CapabilityOrderResultDto>.Ok(result);}
                letter.MakeChoices(skills,trait);Find.LetterStack.RemoveLetter(letter);result.Applied=true;result.Reason="native_growth_choices_applied";
            }
            return ApiResult<CapabilityOrderResultDto>.Ok(result);
        }
    }
}
