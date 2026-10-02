using System;
using System.Runtime.CompilerServices;
using System.Net;
using System.Linq;
using RimWorld;
using HarmonyLib;
using Verse;
using RIMAPI.Http;
namespace RIMAPI.Helpers
{
    public static class SpecialistWindowSessionHelper
    {
        private sealed class Identity { public string Token=Guid.NewGuid().ToString("N"); }
        private static readonly ConditionalWeakTable<Window,Identity> identities=new ConditionalWeakTable<Window,Identity>();
        public static void Opened(Window window) { if(window==null)return; identities.Remove(window);identities.Add(window,new Identity()); }
        public static string Token(Window window) => window==null ? null : identities.GetValue(window,w=>new Identity()).Token;
        public static bool Matches(Window window,HttpListenerContext context) => window!=null && Find.WindowStack.Windows.Contains(window)
            && Token(window)==RequestParser.GetStringParameter(context,"session_id",false);
    }
    [HarmonyPatch(typeof(WindowStack),nameof(WindowStack.Add))]
    public static class SpecialistWindowGenerationHook
    { public static void Prefix(Window window) => SpecialistWindowSessionHelper.Opened(window); }
}
