#if LAYA_COMBAT_LAB
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using RIMAPI.Helpers;
using Verse;
namespace RIMAPI.Controllers
{
    // Read-only measurements; no path, RNG, enemy or clock replacement.
    public static class CombatLabExecutionTiming
    {
        public sealed class Scope {public long Start;public int Paths;public int Searches;public string Name;public bool Closed;}
        private static readonly Stack<Scope> Active=new Stack<Scope>();
        private static readonly List<object> Slow=new List<object>();
        private static int scopes,paths,coreQueries,over25;private static double maxMs,pathMaxMs;
        public static Scope Enter(string name)
        {var s=new Scope{Start=Stopwatch.GetTimestamp(),Name=name};Active.Push(s);return s;}
        public static void Exit(Scope s)
        {
            if(s==null || s.Closed)return;s.Closed=true;
            if(Active.Count==0 || Active.Peek()!=s)throw new InvalidOperationException("Native timing scope mismatch");
            Active.Pop();scopes++;double ms=(Stopwatch.GetTimestamp()-s.Start)*1000d/Stopwatch.Frequency;
            maxMs=Math.Max(maxMs,ms);
            if(ms>25){over25++;if(Slow.Count<32)Slow.Add(new{tick=Find.TickManager?.TicksGame,name=s.Name,ms,path_calls=s.Paths,core_searches=s.Searches});}
        }
        public static long PathStart(bool core) { if(Active.Count==0)return 0; if(core){coreQueries++;foreach(var s in Active)s.Searches++;} return Stopwatch.GetTimestamp(); }
        public static void PathEnd(long stamp)
        {
            if(stamp==0)return;paths++;
            foreach(var scope in Active)scope.Paths++;
            pathMaxMs=Math.Max(pathMaxMs,(Stopwatch.GetTimestamp()-stamp)*1000d/Stopwatch.Frequency);
        }
        public static object State()=>new{controller_scopes=scopes,actual_FindPathNow_calls=paths,native_searches=coreQueries,
            max_controller_ms=maxMs,max_single_path_ms=pathMaxMs,over_25ms=over25,slow_scopes=Slow.ToArray(),
            instrumentation="Lab-only read-only timing: raw FindPathNow entries retained; native_searches counts only the TraverseParms core overload once"};
    }
    [HarmonyPatch(typeof(CombatControlHelper),nameof(CombatControlHelper.Tick))]
    public static class CombatLabExecutionTickTiming
    {
        public static void Prefix(out CombatLabExecutionTiming.Scope __state)=>__state=CombatLabExecutionTiming.Enter("Tick");
        public static void Postfix(CombatLabExecutionTiming.Scope __state)=>CombatLabExecutionTiming.Exit(__state);
        public static Exception Finalizer(Exception __exception,CombatLabExecutionTiming.Scope __state)
        {CombatLabExecutionTiming.Exit(__state);return __exception;}
    }
    [HarmonyPatch(typeof(CombatTacticsHelper),nameof(CombatTacticsHelper.Apply))]
    public static class CombatLabExecutionApplyTiming
    {
        public static void Prefix(out CombatLabExecutionTiming.Scope __state)=>__state=CombatLabExecutionTiming.Enter("Apply");
        public static void Postfix(CombatLabExecutionTiming.Scope __state)=>CombatLabExecutionTiming.Exit(__state);
        public static Exception Finalizer(Exception __exception,CombatLabExecutionTiming.Scope __state)
        {CombatLabExecutionTiming.Exit(__state);return __exception;}
    }
    [HarmonyPatch]
    public static class CombatLabCareReviewTiming
    {
        public static IEnumerable<MethodBase> TargetMethods()
        {
            foreach(var name in new[]{"MedicalTendReviewHelper","CaregiverRecoveryHelper"})
            {
                var type=typeof(CombatControlHelper).Assembly.GetType("RIMAPI.Helpers."+name);
                var method=type?.GetMethod("Tick",BindingFlags.Public|BindingFlags.Static);
                if(method!=null)yield return method;
            }
        }
        public static void Prefix(MethodBase __originalMethod,out CombatLabExecutionTiming.Scope __state)
            =>__state=CombatLabExecutionTiming.Enter(__originalMethod.DeclaringType.Name+".Tick");
        public static void Postfix(CombatLabExecutionTiming.Scope __state)=>CombatLabExecutionTiming.Exit(__state);
        public static Exception Finalizer(Exception __exception,CombatLabExecutionTiming.Scope __state)
        {CombatLabExecutionTiming.Exit(__state);return __exception;}
    }
    [HarmonyPatch]
    public static class CombatLabExecutionPathTiming
    {
        public static IEnumerable<MethodBase> TargetMethods()
        {
            var type=AccessTools.Field(typeof(Map),"pathFinder")?.FieldType ?? AccessTools.Property(typeof(Map),"pathFinder")?.PropertyType;
            if(type==null)throw new InvalidOperationException("Cannot locate native pathfinder for actual-call measurement");
            var methods=type.GetMethods(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance).Where(m=>m.Name=="FindPathNow").Cast<MethodBase>().ToArray();
            if(methods.Length==0)throw new InvalidOperationException("No native FindPathNow to measure");
            return methods;
        }
        public static void Prefix(MethodBase __originalMethod,out long __state)=>__state=CombatLabExecutionTiming.PathStart(__originalMethod.GetParameters().Any(p=>p.ParameterType.Name=="TraverseParms"));
        public static void Postfix(long __state)=>CombatLabExecutionTiming.PathEnd(__state);
    }
}
#endif
