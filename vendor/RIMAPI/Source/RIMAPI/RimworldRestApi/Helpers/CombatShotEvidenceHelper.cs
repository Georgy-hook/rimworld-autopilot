using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using RimWorld;
using UnityEngine;
using Verse;

namespace RIMAPI.Helpers
{
    // Native observations only: an accepted AttackStatic or a cooldown alone
    // does not establish that the covering gun actually fired at this enemy.
    public static class CombatShotEvidenceHelper
    {
        private sealed class Shot {public int Tick,Target;}
        private static readonly Dictionary<Pawn,Shot> Last=new Dictionary<Pawn,Shot>();
        public static int LastTick(Pawn actor,int target)
            =>Last.TryGetValue(actor,out var s) && s.Target==target?s.Tick:-1;
        public static void Observe(Pawn actor,Pawn target)
        {
            if(actor?.Faction!=Faction.OfPlayer || target==null || Find.TickManager==null)return;
            if(Last.Count>=128)
                foreach(var old in Last.Keys.Where(p=>!p.Spawned || p.Dead || Find.TickManager.TicksGame-Last[p].Tick>1800).ToArray())Last.Remove(old);
            if(Last.Count>=128 && !Last.ContainsKey(actor))return;
            Last[actor]=new Shot{Tick=Find.TickManager.TicksGame,Target=target.thingIDNumber};
        }
    }
    [HarmonyPatch]
    public static class CombatNativeShotObservation
    {
        public static MethodBase TargetMethod()=>typeof(Projectile).GetMethods(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)
            .Single(m=>m.Name=="Launch" && m.GetParameters().Any(p=>p.ParameterType==typeof(Vector3)));
        public static void Postfix(MethodBase __originalMethod,object[] __args)
        {
            Pawn actor=null,target=null;
            var parameters=__originalMethod.GetParameters();
            for(int i=0;i<parameters.Length;i++)
            {
                if(parameters[i].Name=="launcher")actor=__args[i] as Pawn;
                if(parameters[i].Name=="intendedTarget" && __args[i] is LocalTargetInfo info)target=info.Thing as Pawn;
            }
            CombatShotEvidenceHelper.Observe(actor,target);
        }
    }
}
