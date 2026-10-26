using RIMAPI.Models;

namespace RIMAPI.Helpers
{
    public static class CombatTacticReadinessHelper
    {
        public static CombatTacticResponseDto StandDownBlocked(string tactic,int? requestedTarget)
        {
            var result=new CombatTacticResponseDto{Tactic=tactic,TargetPawnId=requestedTarget,
                Applied=false,Deferred=false,ReviewComplete=true};
            result.Notes.Add("hostiles_remain_current_state: Hostiles remain; stand down no longer feasible. Existing defense, drafts, clinical jobs and queues are retained; no stand-down applied.");
            return result;
        }
        // A target disappearing between observation and Apply is an ordinary
        // stale precondition. It is neither a server crash nor an executed
        // tactic. Do not draft, retarget, stand down, retry or erase old jobs.
        public static CombatTacticResponseDto NoSelectedFighters(string tactic,int? requestedTarget)
        {
            var result=new CombatTacticResponseDto{Tactic=tactic,TargetPawnId=requestedTarget,
                Applied=false,Deferred=false,ReviewComplete=true};
            result.Notes.Add("selected_fighters_unavailable_current_state: no selected living mobile fighter is available; request not applied, no new draft or replacement actor. Existing jobs and care queues are retained.");
            return result;
        }
        public static CombatTacticResponseDto NoActiveTarget(string tactic,int? requestedTarget)
        {
            var result=new CombatTacticResponseDto{Tactic=tactic,TargetPawnId=requestedTarget,
                Applied=false,Deferred=false,ReviewComplete=true};
            result.Notes.Add("target_unavailable_current_state: selected target is no longer an active hostile; request not applied, no new fighters drafted. Existing jobs are retained; this does not prove the whole raid is over.");
            return result;
        }
    }
}
