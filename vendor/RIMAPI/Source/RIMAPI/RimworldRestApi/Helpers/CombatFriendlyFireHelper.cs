// Read-only loaded shot geometry; no RNG, projectile, accuracy or damage changes.
using System;
using System.Linq;
using Verse;
using RimWorld;
namespace RIMAPI.Helpers
{
    /// <summary>A local ShotReport value describes a proposed firing cell without moving the real pawn, changing stats or sampling the native RNG.</summary>
    public static class CombatFriendlyFireHelper
    {
        private static readonly Func<ShotReport,float,float,float,float,float,ShotReport> WithGeometry=BindGeometry();
        private static readonly Func<ShotReport,float,ShotReport> WithDarkness=BindDarkness();
        private static Func<ShotReport,float,ShotReport> BindDarkness()
        {
            try
            {
                var field=typeof(ShotReport).GetField("offsetFromDarkness",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);
                if(field==null || field.FieldType!=typeof(float))return null;
                var method=new System.Reflection.Emit.DynamicMethod("LayaReportDarkness",typeof(ShotReport),new[]{typeof(ShotReport),typeof(float)},typeof(CombatFriendlyFireHelper),true);
                var code=method.GetILGenerator();code.Emit(System.Reflection.Emit.OpCodes.Ldarga_S,(byte)0);
                code.Emit(System.Reflection.Emit.OpCodes.Ldarg_1);code.Emit(System.Reflection.Emit.OpCodes.Stfld,field);
                code.Emit(System.Reflection.Emit.OpCodes.Ldarg_0);code.Emit(System.Reflection.Emit.OpCodes.Ret);
                return (Func<ShotReport,float,ShotReport>)method.CreateDelegate(typeof(Func<ShotReport,float,ShotReport>));
            }
            catch{return null;}
        }
        private static Func<ShotReport,float,float,float,float,float,ShotReport> BindGeometry()
        {
            try
            {
                var types=new[]{typeof(ShotReport),typeof(float),typeof(float),typeof(float),typeof(float),typeof(float)};
                var method=new System.Reflection.Emit.DynamicMethod("LayaReportAtCell",typeof(ShotReport),types,typeof(CombatFriendlyFireHelper),true);
                var code=method.GetILGenerator();
                var names=new[]{"distance","factorFromShooterAndDist","factorFromEquipment","factorFromWeather","factorFromCoveringGas"};
                for(int i=0;i<names.Length;i++)
                {
                    var field=typeof(ShotReport).GetField(names[i],System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);
                    if(field==null || field.FieldType!=typeof(float))return null;
                    code.Emit(System.Reflection.Emit.OpCodes.Ldarga_S,(byte)0);
                    code.Emit(System.Reflection.Emit.OpCodes.Ldarg,(short)(i+1));
                    code.Emit(System.Reflection.Emit.OpCodes.Stfld,field);
                }
                code.Emit(System.Reflection.Emit.OpCodes.Ldarg_0);code.Emit(System.Reflection.Emit.OpCodes.Ret);
                return (Func<ShotReport,float,float,float,float,float,ShotReport>)method.CreateDelegate(typeof(Func<ShotReport,float,float,float,float,float,ShotReport>));
            }
            catch{return null;}
        }
        public static bool LaneClear(Pawn pawn,Pawn target,IntVec3 from,ShootLine line)
        {
            var allies=pawn.Map.mapPawns.AllPawnsSpawned.Where(p=>p!=pawn && p!=target && !p.Dead
                && (!p.HostileTo(pawn) && !CombatNativeHelper.ActivePredation(p)
                    || pawn.Faction==Faction.OfPlayer && p.IsPrisonerOfColony)
                && VerbUtility.InterceptChanceFactorFromDistance(line.Source.ToVector3Shifted(),p.Position)>0f).ToArray();
            if(allies.Length==0)return true;
            var verb=pawn.equipment?.Primary?.TryGetComp<CompEquippable>()?.PrimaryVerb;
            if(verb==null)return false;
            LocalTargetInfo shotTarget=line.Dest==target.Position?new LocalTargetInfo(target):new LocalTargetInfo(line.Dest);
            float? radius=MissRadius(pawn,verb,shotTarget,from,line,target);
            if(!radius.HasValue)return false;
            return !allies.Any(p=>CombatInterceptMath.InterveningMissFan(line.Source.x,line.Source.z,line.Dest.x,line.Dest.z,
                p.Position.x,p.Position.z,radius.Value,CombatInterceptMath.FriendlyBodyRadius(p.BodySize)));
        }
        public static float? CandidateAim(Pawn pawn,Verb verb,LocalTargetInfo target,IntVec3 from,ShootLine line,IntVec3? projectedCell=null)
        {
            if(WithGeometry==null)return null;
            var cell=projectedCell ?? target.Cell;
            float distance=from.DistanceTo(cell);
            float shooter=verb.verbProps.canGoWild?ShotReport.HitFactorFromShooter(pawn,distance,null):1f;
            float equipment=verb.verbProps.GetHitChanceFactor(verb.EquipmentSource,distance);
            float weather=from.Roofed(pawn.Map) && cell.Roofed(pawn.Map)?1f:
                Math.Min(1f,pawn.Map.weatherManager.CurWeatherAccuracyMultiplier);
            float gas=line.Points().Any(c=>c.AnyGas(pawn.Map,GasType.BlindSmoke)) ? .7f : 1f;
            // Ignoring weather/smoke maluses can improve real accuracy; this
            // candidate estimate deliberately keeps the lower accuracy bound.
            var report=WithGeometry(ShotReport.HitReportFor(pawn,verb,target),distance,shooter,equipment,weather,gas);
            if(cell!=target.Cell && ModsConfig.IdeologyActive)
            {
                if(WithDarkness==null)return null;
                float darkness=new[]{StatDefOf.ShootingAccuracyOutdoorsLitOffset,StatDefOf.ShootingAccuracyOutdoorsDarkOffset,
                    StatDefOf.ShootingAccuracyIndoorsLitOffset,StatDefOf.ShootingAccuracyIndoorsDarkOffset}
                    .Select(s=>pawn.GetStatValue(s)).Min();
                report=WithDarkness(report,darkness);
            }
            float aim=report.AimOnTargetChance_StandardTarget;
            return aim>0f && !float.IsInfinity(aim)?(float?)aim:null;
        }
        public static float? MissRadius(Pawn pawn,Verb verb,LocalTargetInfo target,IntVec3 from,ShootLine line,Pawn observedTarget=null)
        {
            var projectile=verb.verbProps.defaultProjectile?.projectile;
            if(projectile==null)return null;
            float wild=0f;
            if(verb.verbProps.canGoWild)
            {
                // Keep the observed Pawn in the report when only its future
                // cell is projected. No guessed minimum-accuracy disk.
                LocalTargetInfo reportTarget=target.HasThing?target:new LocalTargetInfo(observedTarget);
                if(!reportTarget.IsValid)return null;
                float? aim=from==pawn.Position && target.Cell==reportTarget.Cell
                    ?(float?)ShotReport.HitReportFor(pawn,verb,reportTarget).AimOnTargetChance_StandardTarget
                    :CandidateAim(pawn,verb,reportTarget,from,line,target.Cell);
                if(!aim.HasValue)return null;
                wild=ShootTuning.MissDistanceFromAimOnChanceCurves.Evaluate(aim.Value,1f);
            }
            float forced=VerbUtility.CalculateAdjustedForcedMiss(verb.verbProps.ForcedMissRadius
                *verb.verbProps.GetForceMissFactorFor(verb.EquipmentSource,pawn),target.Cell-from);
            // Native cell quantization (<=sqrt(.5)) plus Launch's independent
            // 0.3 horizontal jitter (<=sqrt(.18)), rounded conservatively.
            float radius=Math.Max(wild,forced)+1.25f;
            return radius>=0f && !float.IsInfinity(radius)?(float?)radius:null;
        }
    }

}
