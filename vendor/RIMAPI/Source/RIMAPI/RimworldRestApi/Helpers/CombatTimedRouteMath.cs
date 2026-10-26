using System;
using System.Collections.Generic;
namespace RIMAPI.Helpers
{
    public struct CombatTimedPoint
    {
        public readonly float X,Z,Tick;
        public CombatTimedPoint(float x,float z,float tick){X=x;Z=z;Tick=tick;}
    }
    public struct CombatTimedRange
    {
        public readonly bool Valid;public readonly float Minimum,Maximum,MinimumAt;
        public CombatTimedRange(float min,float max,float at){Valid=true;Minimum=min;Maximum=max;MinimumAt=at;}
    }
    // Piecewise path estimates only; no movement or native physics changes.
    public static class CombatTimedRouteMath
    {
        private static bool Finite(float x)=>!float.IsNaN(x) && !float.IsInfinity(x);
        private static bool Valid(IList<CombatTimedPoint> p)
        {
            if(p==null || p.Count==0 || p[0].Tick!=0f)return false;
            for(int i=0;i<p.Count;i++)
                if(!Finite(p[i].X) || !Finite(p[i].Z) || !Finite(p[i].Tick)
                    || i>0 && p[i].Tick<=p[i-1].Tick)return false;
            return true;
        }
        private static void Position(IList<CombatTimedPoint> p,int i,float tick,out float x,out float z)
        {
            if(i+1==p.Count){x=p[i].X;z=p[i].Z;return;}
            float f=Math.Max(0f,Math.Min(1f,(tick-p[i].Tick)/(p[i+1].Tick-p[i].Tick)));
            x=p[i].X+(p[i+1].X-p[i].X)*f;z=p[i].Z+(p[i+1].Z-p[i].Z)*f;
        }
        public static CombatTimedRange Separation(IList<CombatTimedPoint> actor,IList<CombatTimedPoint> target,float start,float end)
        {
            if(!Valid(actor) || !Valid(target) || !Finite(start) || !Finite(end) || start<0 || end<start
                || target[target.Count-1].Tick<end)return new CombatTimedRange();
            int ai=0,ti=0,steps=0;float current=start,min=float.PositiveInfinity,max=0f,at=start;
            while(true)
            {
                while(ai+1<actor.Count && actor[ai+1].Tick<=current)ai++;
                while(ti+1<target.Count && target[ti+1].Tick<=current)ti++;
                Position(actor,ai,current,out var ax,out var az);Position(target,ti,current,out var tx,out var tz);
                float rx=ax-tx,rz=az-tz,first=rx*rx+rz*rz;
                if(first<min){min=first;at=current;}max=Math.Max(max,first);
                if(current>=end)break;
                if(++steps>actor.Count+target.Count+2)return new CombatTimedRange();
                float next=Math.Min(end,Math.Min(ai+1<actor.Count?actor[ai+1].Tick:float.PositiveInfinity,
                    ti+1<target.Count?target[ti+1].Tick:float.PositiveInfinity));
                if(next<=current)return new CombatTimedRange();
                Position(actor,ai,next,out var bx,out var bz);Position(target,ti,next,out var ux,out var uz);
                float ex=bx-ux,ez=bz-uz,dx=ex-rx,dz=ez-rz,n=dx*dx+dz*dz;
                float f=n>0?Math.Max(0f,Math.Min(1f,-(rx*dx+rz*dz)/n)):0f;
                float cx=rx+dx*f,cz=rz+dz*f,value=cx*cx+cz*cz;
                if(value<min){min=value;at=current+(next-current)*f;}
                max=Math.Max(max,ex*ex+ez*ez);current=next;
            }
            return new CombatTimedRange((float)Math.Sqrt(min),(float)Math.Sqrt(max),at);
        }
    }
}
