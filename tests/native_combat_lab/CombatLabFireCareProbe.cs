#if LAYA_COMBAT_LAB
using System;
using System.Collections.Generic;
using System.Linq;
using RIMAPI.Helpers;
using Verse;
using Verse.AI;

namespace RIMAPI.Controllers
{
    // Declared physical contracts only. No call from a raid benchmark.
    public static class CombatLabFireCareProbe
    {
        public static object Run(string phase)
        {
            if(CombatLabState.Scenario?.StartsWith("execution_contract_",StringComparison.Ordinal)!=true)
                throw new InvalidOperationException("A declared executor fixture is required");
            var p=CombatLabState.Allies[0];var checks=new Dictionary<string,bool>();
            var before=p.CurJob;var queued=p.jobs.jobQueue.Select(q=>q.job).ToArray();
            var enginePath=p.pather.curPath;
            int cursor=enginePath?.NodesLeftCount ?? -1;
            var goal=new IntVec3(110,0,108);
            if(phase=="pool")
            {
                if(!CombatLabState.HoldInitial || !CombatLabState.Scenario.EndsWith("blocked",StringComparison.Ordinal))
                    throw new InvalidOperationException("Held blocked contract fixture required");
                var initial=CombatPathBudgetHelper.Query(p,p.Position,goal,PathEndMode.OnCell);
                checks["real_native_path_found"]=initial.Found;
                var nodes=initial.NodesReversed.ToArray();float cost=initial.TotalCost;
                var identities=new HashSet<int>();
                for(int n=0;n<80;n++)
                {
                    var observation=CombatPathBudgetHelper.Query(p,p.Position,goal,PathEndMode.OnCell);
                    if(!observation.Found || CombatPathBudgetHelper.TestOutstanding!=0)
                        throw new InvalidOperationException("A native path escaped its Query lifetime");
                    identities.Add(CombatPathBudgetHelper.TestLastNativeIdentity);
                }
                checks["native_pool_reuses_returned_objects"]=identities.Count<80;
                checks["retained_observation_immutable"]=initial.TotalCost==cost && initial.NodesReversed.SequenceEqual(nodes);
                checks["owned_paths_return_before_observation_use"]=CombatPathBudgetHelper.TestOutstanding==0;
                var no=CombatPathBudgetHelper.Query(p,p.Position,CombatLabExecutionProbe.Goal,PathEndMode.OnCell);
                checks["actual_enclosed_destination_not_found"]=!no.Found;
                bool threw=false;
                try
                {
                    CombatPathBudgetHelper.TestThrowAfterCopy=true;
                    CombatPathBudgetHelper.Query(p,p.Position,goal,PathEndMode.OnCell);
                }
                catch(InvalidOperationException e){threw=e.Message=="Declared native path ownership exception";}
                finally{CombatPathBudgetHelper.TestThrowAfterCopy=false;}
                checks["exception_returns_native_path"]=threw && CombatPathBudgetHelper.TestOutstanding==0;
                bool tooLong=false;
                try{CombatPathBudgetHelper.Query(p,p.Position,goal,PathEndMode.OnCell,1);}
                catch(CombatReviewDeferredException e){tooLong=e.Message.StartsWith("RouteIncomplete:",StringComparison.Ordinal);}
                checks["analysis_node_limit_never_returns_truncated_safe_path"]=tooLong && CombatPathBudgetHelper.TestOutstanding==0;
                bool shared=false;
                using(CombatPathBudgetHelper.Begin("native_nested_contract",1))
                {
                    CombatPathBudgetHelper.Query(p,p.Position,goal,PathEndMode.OnCell);
                    using(CombatPathBudgetHelper.Begin("nested_cannot_reset_quota",64))
                        try{CombatPathBudgetHelper.Query(p,p.Position,goal,PathEndMode.OnCell);}
                        catch(CombatReviewDeferredException e){shared=e.Message.StartsWith("BudgetDeferred:",StringComparison.Ordinal);}
                }
                checks["nested_review_does_not_reset_query_quota"]=shared;
            }
            else if(phase=="live_budget")
            {
                if(CombatLabState.HoldInitial)throw new InvalidOperationException("Live native clock required");
                bool deferred=false;
                using(CombatPathBudgetHelper.Begin("native_live_contract",8))
                    try
                    {
                        for(int n=0;n<24;n++)
                            CombatPathBudgetHelper.Query(p,p.Position,goal,PathEndMode.OnCell);
                    }
                    catch(CombatReviewDeferredException e){deferred=e.Message.StartsWith("BudgetDeferred:",StringComparison.Ordinal);}
                checks["live_review_budget_defers"]=deferred;
                checks["native_paths_returned_after_live_deferral"]=CombatPathBudgetHelper.TestOutstanding==0;
                if(enginePath!=null && enginePath.Found)
                {
                    var copy=CombatPathBudgetHelper.Borrowed(enginePath);
                    checks["borrowed_engine_path_keeps_identity_and_cursor"]=ReferenceEquals(enginePath,p.pather.curPath)
                        && enginePath.NodesLeftCount==cursor && copy.Found;
                }
                else checks["borrowed_engine_path_keeps_identity_and_cursor"]=false;
            }
            else throw new InvalidOperationException("Unknown declared fire-care contract phase");
            checks["current_job_and_queue_unchanged_by_path_review"]=ReferenceEquals(before,p.CurJob)
                && queued.SequenceEqual(p.jobs.jobQueue.Select(q=>q.job));
            return new{phase,tick=Find.TickManager.TicksGame,checks,pass=checks.Values.All(x=>x),
                paths=CombatPathBudgetHelper.Diagnostics(),
                statement="Native physical contract. Node-limit branch uses declared analysis limit1; ordinary production limit4096 is unchanged. No raid score."};
        }
    }
}
#endif
