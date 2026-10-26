using System;

using System.Collections.Generic;

using System.Linq;

using RimWorld;

using Verse;

using Verse.AI;

namespace RIMAPI.Helpers

{

    // Longer interception is restricted to the sole observed native abductor.

    // Native routes/costs are estimates; no future job, hit or rescue is asserted.

    public static class CombatCarrierSearchMath
    {
        public static int PageEnd(int start,int total)=>Math.Min(Math.Max(0,total),Math.Max(0,start)+4);
        public static bool Reuse(bool target,bool job,bool map,int age,int remaining)
            =>target && job && map && age>=0 && age<=600 && remaining>0;
    }
    public static class CombatCarrierInterceptHelper

    {

        private sealed class Search

        {

            public Pawn Actor,Target;public Map Map;public Verb Verb;

            public List<Tuple<IntVec3,float>> Route;public List<CombatTimedPoint> TargetPoints;

            public float Range,Minimum,Aim,Engagement,Flight,OwnLock,Until;public int Queries;

#if LAYA_COMBAT_LAB

            public double CoarseMilliseconds;
            public int GeneratedCells,CoarseCells,ShortlistedCells;
            public bool TraceEvaluations,UseLoadedRangeWindowForProbe;public Dictionary<string,object> LastTrial;

#endif

            public float Horizon(float travel)=>CombatInterceptMath.ShotHorizon(travel+OwnLock,Aim+Engagement,Flight);

            public IntVec3 Future(float time)=>Route.LastOrDefault(r=>r.Item2<=time)?.Item1 ?? Route[0].Item1;

        }

        private sealed class Evaluation

        {

            public IntVec3 Cell,Future;public float Travel,Horizon,Score,MoveMinimum,VolleyMinimum,VolleyMaximum;

        }

#if LAYA_COMBAT_LAB

        private static readonly List<object> Events=new List<object>();

        public static void ResetDiagnostics()=>Events.Clear();

        public static object Diagnostics()=>new{available=true,event_cap=128,events=Events.ToArray()};

        private static void Record(Search s,Evaluation e,bool kept,double elapsed)

        {

            if(Events.Count<128)Events.Add(new{tick=Find.TickManager.TicksGame,actor=s.Actor.thingIDNumber,target=s.Target.thingIDNumber,

                selected=e!=null,kept_waypoint=kept,path_queries=s.Queries,path_query_cap=48,total_ms=elapsed,coarse_ms=s.CoarseMilliseconds,
                actor_x=s.Actor.Position.x,actor_z=s.Actor.Position.z,target_x=s.Target.Position.x,target_z=s.Target.Position.z,
                generated_cells=s.GeneratedCells,coarse_cells=s.CoarseCells,shortlisted_cells=s.ShortlistedCells,

                x=e?.Cell.x,z=e?.Cell.z,travel=e?.Travel,horizon=e?.Horizon,known_until=s.Until,

                movement_min=e?.MoveMinimum,volley_min=e?.VolleyMinimum,volley_max=e?.VolleyMaximum,

                meaning="Actual production selection and estimated timing guards; no arrival, shot, hit or rescue credit"});

        }

#endif

        public static bool Eligible(Pawn target)

        {

            if(target==null || !target.Spawned || target.Dead || target.Downed || target.Position.Fogged(target.Map)

                || !CombatNativeHelper.Kidnapper(target))return false;

            var map=target.Map;

            return !map.mapPawns.AllPawnsSpawned.Any(p=>p!=target && !p.Dead && !p.Downed

                    && !p.Position.Fogged(map) && CombatNativeHelper.IsPlayerThreat(p))

                && !map.listerBuildings.allBuildingsNonColonist.Any(b=>!b.Position.Fogged(map) && CombatNativeHelper.ActiveStructure(b));

        }

        private static List<CombatTimedPoint> ActorRoute(Pawn actor,CombatPathBudgetHelper.Observation path,float total,float ownLock)

        {

            var result=new List<CombatTimedPoint>{new CombatTimedPoint(actor.Position.x,actor.Position.z,0f)};

            var raw=new List<CombatTimedPoint>();var previous=actor.Position;float elapsed=0f;

            foreach(var c in path.NodesReversed.AsEnumerable().Reverse().Skip(1))

            {
                CombatPathBudgetHelper.Checkpoint();elapsed+=CombatInterceptHelper.PlannedJogStepTicks(actor,previous,c);raw.Add(new CombatTimedPoint(c.x,c.z,elapsed));previous=c;}

            if(ownLock>0)result.Add(new CombatTimedPoint(actor.Position.x,actor.Position.z,ownLock));

            if(total>0 && elapsed<=0)return new List<CombatTimedPoint>();

            foreach(var point in raw)result.Add(new CombatTimedPoint(point.X,point.Z,ownLock+point.Tick*total/elapsed));

            return result;

        }

        private static Evaluation Evaluate(Search s,IntVec3 cell)
        {
#if LAYA_COMBAT_LAB
            if(s.TraceEvaluations)s.LastTrial=new Dictionary<string,object>{{"reason","preconditions"}};
#endif
            if(s.Queries>=48 || !cell.InBounds(s.Map) || !cell.Standable(s.Map) || cell.Fogged(s.Map)
                || !s.Actor.CanReserve(cell) || CombatControlHelper.CellClaimed(s.Actor,cell)
                || cell.GetThingList(s.Map).OfType<Pawn>().Any(p=>p!=s.Actor))return null;
            s.Queries++;
            using(var path=CombatPathBudgetHelper.Query(s.Actor,s.Actor.Position,cell,PathEndMode.OnCell))
            {
#if LAYA_COMBAT_LAB
                if(s.TraceEvaluations){s.LastTrial["reason"]="movement_path_or_hazard";s.LastTrial["path_found"]=path.Found;s.LastTrial["travel"]=path.TotalCost;}
#endif
                if(!CombatInterceptHelper.MovementSafe(s.Actor,path))return null;
                float travel=path.TotalCost,h=s.Horizon(travel);
#if LAYA_COMBAT_LAB
                if(s.TraceEvaluations){s.LastTrial["reason"]="after_observed_route_end";s.LastTrial["horizon"]=h;s.LastTrial["observed_until"]=s.Until;}
#endif
                if(h>s.Until)return null;
                var future=s.Future(h);bool window=CombatInterceptMath.FiringWindow(s.Range,s.Minimum,cell.DistanceTo(future));
#if LAYA_COMBAT_LAB
                if(s.UseLoadedRangeWindowForProbe)window=CombatInterceptMath.FiringWindow(s.Range,s.Minimum,cell.DistanceTo(future));
#endif
#if LAYA_COMBAT_LAB
                if(s.TraceEvaluations){s.LastTrial["reason"]="endpoint_range";s.LastTrial["future_x"]=future.x;s.LastTrial["future_z"]=future.z;s.LastTrial["distance"]=cell.DistanceTo(future);}
#endif
                if(!window)return null;
#if LAYA_COMBAT_LAB
                if(s.TraceEvaluations)s.LastTrial["reason"]="native_future_pawn_line";
#endif
                if(CombatExposureHelper.CanHitPawnAt(s.Verb,s.Target,cell,future)!=true)return null;
#if LAYA_COMBAT_LAB
                if(s.TraceEvaluations)s.LastTrial["reason"]="friendly_future_lane";
#endif
                if(!CombatInterceptHelper.FutureFriendlyLaneClear(s.Actor,s.Target,cell,future,"long_carrier_position"))return null;
                var actorRoute=ActorRoute(s.Actor,path,travel,s.OwnLock);float arrival=travel+s.OwnLock;
                var movement=CombatTimedRouteMath.Separation(actorRoute,s.TargetPoints,0f,arrival);
                var volley=CombatTimedRouteMath.Separation(actorRoute,s.TargetPoints,arrival,h);
#if LAYA_COMBAT_LAB
                if(s.TraceEvaluations){s.LastTrial["reason"]="continuous_separation_or_range";s.LastTrial["movement_known"]=movement.Valid;s.LastTrial["volley_known"]=volley.Valid;
                    s.LastTrial["movement_min"]=movement.Valid?(float?)movement.Minimum:null;s.LastTrial["volley_min"]=volley.Valid?(float?)volley.Minimum:null;
                    s.LastTrial["volley_max"]=volley.Valid?(float?)volley.Maximum:null;s.LastTrial["interior_range_max"]=s.Range-Math.Max(3f,s.Range*.12f);}
#endif
                if(!movement.Valid || !volley.Valid || movement.Minimum<3.5f || volley.Minimum<6f
                    || volley.Maximum>s.Range-Math.Max(3f,s.Range*.12f))return null;
#if LAYA_COMBAT_LAB
                if(s.TraceEvaluations)s.LastTrial["reason"]="accepted";
#endif
                return new Evaluation{Cell=cell,Future=future,Travel=travel,Horizon=h,
                    Score=h*.3f+cell.DistanceTo(future)*12f-CoverUtility.CalculateOverallBlockChance(new LocalTargetInfo(cell),s.Target.Position,s.Map)*100f,
                    MoveMinimum=movement.Minimum,VolleyMinimum=volley.Minimum,VolleyMaximum=volley.Maximum};
            }
        }
        private static Search PrepareSearch(Pawn actor,Pawn target,List<Tuple<IntVec3,float>> observed)

        {

            if(actor==null || actor.Map!=target?.Map || !Eligible(target) || observed==null || observed.Count<2

                || actor.Dead || actor.Downed || actor.InMentalState || actor.WorkTagIsDisabled(WorkTags.Violent)

                || CombatNativeHelper.Protected(actor) || CareTriageHelper.QueuedCare(actor)

                || actor.carryTracker?.CarriedThing is Pawn)return null;

            var verb=actor.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;

            if(verb==null || verb.IsMeleeAttack || verb.verbProps.range<=6f)return null;

            var projectile=verb.verbProps.defaultProjectile?.projectile;

            if(projectile==null || projectile.explosionRadius>0 || projectile.damageDef==DamageDefOf.Flame)return null;

            float targetLock=CombatInterceptHelper.MovementLockTicks(target);

            var route=new List<Tuple<IntVec3,float>>{Tuple.Create(target.Position,0f)};

            if(targetLock>0)route.Add(Tuple.Create(target.Position,targetLock));

            route.AddRange(observed.Skip(1).Select(r=>Tuple.Create(r.Item1,r.Item2+targetLock)));

            var s=new Search{Actor=actor,Target=target,Map=actor.Map,Verb=verb,Route=route,

                TargetPoints=route.Select(r=>new CombatTimedPoint(r.Item1.x,r.Item1.z,r.Item2)).ToList(),

                Range=verb.verbProps.range,Minimum=verb.verbProps.minRange,Until=Math.Min(3600f,route.Last().Item2),

                OwnLock=actor.stances.curStance is Stance_Warmup?0f:CombatInterceptHelper.MovementLockTicks(actor),

                Aim=verb.verbProps.warmupTime*60f*actor.GetStatValue(StatDefOf.AimingDelayFactor),

                Flight=CombatInterceptMath.NativeFlightTicks(verb.verbProps.range,projectile.SpeedTilesPerTick)};

            if(float.IsInfinity(s.Flight))return null;

            s.Engagement=CombatInterceptMath.EngagementTicks(true,false,s.Aim,

                Math.Max(0,verb.verbProps.burstShotCount-1)*verb.verbProps.ticksBetweenBurstShots,

                actor.equipment.Primary.GetStatValue(StatDefOf.RangedWeapon_Cooldown)*60f);

            return s;

        }

        private static HashSet<IntVec3> CandidateCells(Search s)

        {

            var actor=s.Actor;

                var cells=new HashSet<IntVec3>();

                foreach(var c in GenRadial.RadialCellsAround(actor.Position,36f,true).Where((c,i)=>i%8==0))cells.Add(c);

                foreach(float horizon in new[]{120f,240f,480f,720f,960f,1440f,1920f,2400f,3000f})

                {
                CombatPathBudgetHelper.Checkpoint();

                    var lead=s.Future(Math.Min(horizon,s.Until));int offset=(int)Math.Max(7f,s.Range*.55f);

                    foreach(var direction in GenAdj.CardinalDirections)

                        foreach(var c in GenRadial.RadialCellsAround(lead+direction*offset,3f,true))cells.Add(c);

                }

            // Sample nearby parallel lanes along the same observed finite route.
            // Every candidate still needs the full native path and volley checks.
            int lane=(int)Math.Ceiling(Math.Max(7f,s.Minimum+1f));
            for(int i=0;i<s.Route.Count;i+=8)
            {
                if(s.Route[i].Item2>s.Until)break;
                foreach(var direction in GenAdj.CardinalDirections)
                    foreach(var c in GenRadial.RadialCellsAround(s.Route[i].Item1+direction*lane,2f,true))cells.Add(c);
            }
            return cells;

        }

#if LAYA_COMBAT_LAB

        public static object TestCandidateGrid(Pawn actor,Pawn target,IntVec3 center)

        {

            string rng=Controllers.CombatLabState.RandomProperty.GetValue(null,null).ToString();

            int tick=Find.TickManager.TicksGame,actorJob=actor.CurJob?.loadID ?? -1,targetJob=target.CurJob?.loadID ?? -1;

            var actorQueue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();

            var targetQueue=target.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();

            var method=typeof(CombatInterceptHelper).GetMethod("TargetRoute",System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static);

            if(method==null)throw new MissingMethodException("Actual production TargetRoute unavailable");

            var observed=(List<Tuple<IntVec3,float>>)method.Invoke(null,new object[]{target});

            var s=PrepareSearch(actor,target,observed);

            if(s==null)return new{available=false,reason="Native known route or eligible controlled actor unavailable",

                rng_unchanged=rng==Controllers.CombatLabState.RandomProperty.GetValue(null,null).ToString(),

                tick_unchanged=Find.TickManager.TicksGame==tick};

            s.TraceEvaluations=true;
            var single=PrepareSearch(actor,target,observed);single.TraceEvaluations=true;
            single.UseLoadedRangeWindowForProbe=true;
            var generated=CandidateCells(s);var rows=new List<object>();

            for(int dx=-1;dx<=1;dx++)for(int dz=-1;dz<=1;dz++)

            {

                var cell=center+new IntVec3(dx,0,dz);var e=Evaluate(s,cell);var first=Evaluate(single,cell);

                rows.Add(new{x=cell.x,z=cell.z,in_generated_pool=generated.Contains(cell),native_legal=e!=null,

                    travel=e?.Travel,horizon=e?.Horizon,movement_min=e?.MoveMinimum,

                    volley_min=e?.VolleyMinimum,volley_max=e?.VolleyMaximum,

                    future_x=e?.Future.x,future_z=e?.Future.z,full_guard=s.LastTrial,
                    loaded_range_counterfactual_legal=first!=null,loaded_range_guard=single.LastTrial});

            }

            string after=Controllers.CombatLabState.RandomProperty.GetValue(null,null).ToString();

            return new{available=true,native_process_id=Controllers.CombatLabState.ProcessId,native_instance_id=Controllers.CombatLabState.InstanceId,tick,actor=actor.thingIDNumber,target=target.thingIDNumber,

                actor_x=actor.Position.x,actor_z=actor.Position.z,target_x=target.Position.x,target_z=target.Position.z,

                known_until=s.Until,known_route_nodes=s.Route.Count,range=s.Range,aim=s.Aim,engagement=s.Engagement,flight=s.Flight,

                generated_count=generated.Count,native_path_queries=s.Queries+single.Queries,native_path_query_cap=48,loaded_range_guard_diagnostic_only=true,rows,

                tick_unchanged=Find.TickManager.TicksGame==tick,rng_before=rng,rng_after=after,rng_unchanged=rng==after,

                actor_job_unchanged=(actor.CurJob?.loadID ?? -1)==actorJob,target_job_unchanged=(target.CurJob?.loadID ?? -1)==targetJob,

                actor_queue_unchanged=actorQueue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),

                target_queue_unchanged=targetQueue.SequenceEqual(target.jobs.jobQueue.Select(q=>q.job.loadID)),

                limits="LAB-only read of actual production preparation, generated pool and Evaluate on nine specified cells. Full production Evaluate and LAB-only ordinary loaded FiringWindow counterfactual with identical full engagement/nativepath/separation/line/flight/buffer; counterfactual never selects a production job. No issued job, arrival, shot, hit or rescue credit."};

        }

#endif

        public static bool HasCurrentWindow(Pawn actor,Pawn target,List<Tuple<IntVec3,float>> observed)
        {
            var s=PrepareSearch(actor,target,observed);
            // The same actual native path/whole finite volley envelope applies
            // before stopping an interception at the current cell.
            return s!=null && Evaluate(s,actor.Position)!=null;
        }
#if LAYA_COMBAT_LAB
        public static object TestSelectionBudget(Pawn actor,Pawn target)
        {
            if(!CombatControlHelper.TestDisabled || !Find.TickManager.Paused)
                throw new InvalidOperationException("Only a paused micro-disabled diagnostic may change the search cache");
            int tick=Find.TickManager.TicksGame,actorJob=actor.CurJob?.loadID ?? -1,targetJob=target.CurJob?.loadID ?? -1;
            var actorQueue=actor.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            var targetQueue=target.jobs.jobQueue.Select(q=>q.job.loadID).ToArray();
            string rng=Controllers.CombatLabState.RandomProperty.GetValue(null,null).ToString();
            var observed=CombatInterceptHelper.ReadObservedRoute(target);
            var legacy=PrepareSearch(actor,target,observed);if(legacy==null)throw new InvalidOperationException("Known eligible carrier route required");
            Evaluation oldBest=null;bool oldDeferred=false,oldComplete=false;
            try
            {
                using(CombatPathBudgetHelper.Begin("legacy_carrier_selection_probe",8))
                {
                    foreach(var cell in Shortlist(legacy))
                    {CombatPathBudgetHelper.Checkpoint();var trial=Evaluate(legacy,cell);if(trial!=null && (oldBest==null || trial.Score<oldBest.Score))oldBest=trial;}
                    oldComplete=true;
                }
            }
            catch(CombatReviewDeferredException){oldDeferred=true;}
            Pages.Remove(actor);var rows=new List<object>();IntVec3 selected=IntVec3.Invalid;
            for(int page=0;page<12;page++)
            {
                bool deferred=false,found=false;string note=null;
                try{using(CombatPathBudgetHelper.Begin("paged_carrier_selection_probe",8))found=TryPosition(actor,target,observed,out selected,out note);}
                catch(CombatReviewDeferredException){deferred=true;}
                rows.Add(new{page,found,deferred,x=found?(int?)selected.x:null,z=found?(int?)selected.z:null,note});
                if(found)break;
            }
            return new{native_process_id=Controllers.CombatLabState.ProcessId,native_instance_id=Controllers.CombatLabState.InstanceId,tick,
                actor=actor.thingIDNumber,target=target.thingIDNumber,legacy_completed=oldComplete,legacy_deferred=oldDeferred,
                legacy_returned_position=oldComplete && oldBest!=null,legacy_had_checked_candidate_before_defer=oldBest!=null,
                legacy_queries=legacy.Queries,paged_selected=selected.IsValid,selected_x=selected.IsValid?(int?)selected.x:null,
                selected_z=selected.IsValid?(int?)selected.z:null,pages=rows,
                rng_unchanged=rng==Controllers.CombatLabState.RandomProperty.GetValue(null,null).ToString(),tick_unchanged=tick==Find.TickManager.TicksGame,
                actor_job_unchanged=actorJob==(actor.CurJob?.loadID ?? -1),target_job_unchanged=targetJob==(target.CurJob?.loadID ?? -1),
                actor_queue_unchanged=actorQueue.SequenceEqual(actor.jobs.jobQueue.Select(q=>q.job.loadID)),
                target_queue_unchanged=targetQueue.SequenceEqual(target.jobs.jobQueue.Select(q=>q.job.loadID)),
                meaning="Same paused native frame, original full evaluator/pool/order and8path scope. Legacy all-candidate selection versus finite continuing4candidate pages; no job, shot, hit, rescue or raid credit. Diagnostic search cache changes only."};
        }
#endif
        private sealed class CandidatePage
        {
            public Pawn Target;public Map Map;public int Job,Tick,Next;
            public List<IntVec3> Cells;
        }
        private static readonly Dictionary<Pawn,CandidatePage> Pages=new Dictionary<Pawn,CandidatePage>();
        private static Game PageGame;
        private static List<IntVec3> Shortlist(Search s)
        {
            var cells=CandidateCells(s);var actor=s.Actor;var route=s.Route;
            float cardinal=actor.TicksPerMoveCardinal,diagonal=actor.TicksPerMoveDiagonal;
            float minSq=(float)Math.Pow(Math.Max(6f,s.Minimum+1f),2),maxSq=(float)Math.Pow(s.Range-Math.Max(3f,s.Range*.12f),2);
            var coarse=cells.Where(c=>c.InBounds(s.Map) && c.Standable(s.Map) && !c.Fogged(s.Map)
                && actor.CanReserve(c) && !CombatControlHelper.CellClaimed(actor,c)
                && !c.GetThingList(s.Map).OfType<Pawn>().Any(p=>p!=actor))
                .Select(c=>new{cell=c,arrival=CombatInterceptMath.StraightTravelTicks(c.x-actor.Position.x,c.z-actor.Position.z,cardinal,diagonal)})
                .Where(c=>route.Where(r=>r.Item2>=c.arrival+s.OwnLock && r.Item2<=s.Until).All(r=>c.cell.DistanceToSquared(r.Item1)>=6.5f*6.5f))
                .Select(c=>new{cell=c.cell,lower=s.Horizon(c.arrival)})
                .Select(c=>new{cell=c.cell,first=route.Where(r=>r.Item2>=c.lower && r.Item2<=s.Until
                    && c.cell.DistanceToSquared(r.Item1)>=minSq-.01f && c.cell.DistanceToSquared(r.Item1)<=maxSq+.01f)
                    .Select(r=>r.Item2).DefaultIfEmpty(float.PositiveInfinity).First()})
                .Where(r=>!float.IsInfinity(r.first)).ToList();
            var diverse=coarse.GroupBy(r=>(int)(r.first/300f)).OrderBy(g=>g.Key)
                .SelectMany(g=>g.OrderBy(r=>r.cell.DistanceToSquared(actor.Position)).Take(4)).Select(r=>r.cell);
            var shortlist=diverse.Concat(coarse.OrderBy(r=>r.cell.DistanceToSquared(actor.Position)).Select(r=>r.cell))
                .Distinct().Take(48-s.Queries).ToList();
#if LAYA_COMBAT_LAB
            s.GeneratedCells=cells.Count;s.CoarseCells=coarse.Count;s.ShortlistedCells=shortlist.Count;
#endif
            return shortlist;
        }
        public static bool TryPosition(Pawn actor,Pawn target,List<Tuple<IntVec3,float>> observed,out IntVec3 result,out string prediction)
        {
            result=IntVec3.Invalid;prediction="No checked long carrier firing window";
#if LAYA_COMBAT_LAB
            var started=System.Diagnostics.Stopwatch.StartNew();
#endif
            var s=PrepareSearch(actor,target,observed);if(s==null)return false;
            Evaluation best=null;bool kept=false;
            var committed=actor.CurJobDef==JobDefOf.Goto?actor.CurJob.targetA.Cell:IntVec3.Invalid;
            if(committed.IsValid){best=Evaluate(s,committed);kept=best!=null;}
            if(best==null)
            {
                if(PageGame!=Current.Game){Pages.Clear();PageGame=Current.Game;}
                int tick=Find.TickManager.TicksGame,job=target.CurJob?.loadID ?? -1;
                foreach(var expired in Pages.Where(p=>p.Key.Destroyed || p.Key.Dead || tick-p.Value.Tick>600).Select(p=>p.Key).ToArray())Pages.Remove(expired);
                if(!Pages.TryGetValue(actor,out var page) || !CombatCarrierSearchMath.Reuse(page.Target==target,
                    page.Job==job,page.Map==actor.Map,tick-page.Tick,page.Cells.Count-page.Next))
                {
#if LAYA_COMBAT_LAB
                    var coarse=System.Diagnostics.Stopwatch.StartNew();
#endif
                    page=new CandidatePage{Target=target,Map=actor.Map,Job=job,Tick=tick,Cells=Shortlist(s)};
                    Pages[actor]=page;
#if LAYA_COMBAT_LAB
                    s.CoarseMilliseconds=coarse.Elapsed.TotalMilliseconds;
#endif
                }
                int stop=CombatCarrierSearchMath.PageEnd(page.Next,page.Cells.Count);
                while(page.Next<stop)
                {
                    CombatPathBudgetHelper.Checkpoint();
                    // Advance only after a COMPLETE rejection or acceptance.
                    // A depleted global pulse retries this same unreviewed cell.
                    var candidate=Evaluate(s,page.Cells[page.Next]);
                    if(candidate==null){page.Next++;continue;}
                    // Keep an accepted cell at the cursor until the native job
                    // takes it; downstream API/job admission may still defer.
                    best=candidate;break; // Commit proof before optional work can defer it.
                }
                if(page.Next<page.Cells.Count)prediction="Finite carrier candidate page remains; no unverified movement issued";
            }
#if LAYA_COMBAT_LAB
            Record(s,best,kept,started.Elapsed.TotalMilliseconds);
#endif
            if(best==null)return false;
            result=best.Cell;
            prediction=$"{actor.LabelShort}: native path {best.Travel:0}, complete shot horizon {best.Horizon:0}/{s.Until:0}; "
                +$"fresh target forecast ({best.Future.x},{best.Future.z}), firing cell ({result.x},{result.z}); "
                +"bounded completed route proof, not arrival, projectile, hit or rescue";
            return true;
        }


    }

}
