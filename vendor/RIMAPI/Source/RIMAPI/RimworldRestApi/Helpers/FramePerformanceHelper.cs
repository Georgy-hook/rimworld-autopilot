using System;
using System.Collections.Generic;
using System.Linq;
using Verse;

namespace RIMAPI.Helpers
{
    public class FramePerformanceComponent : GameComponent
    {
        public FramePerformanceComponent(Game game) { FramePerformanceHelper.Reset(); }
        public override void GameComponentUpdate()
        {
            if(Current.ProgramState==ProgramState.Playing) FramePerformanceHelper.Record(UnityEngine.Time.unscaledDeltaTime);
        }
    }
    /// <summary>Read-only bounded frame timing, not simulation TPS or a diagnosis of a bottleneck.</summary>
    public static class FramePerformanceHelper
    {
        private static readonly object gate=new object();
        private static readonly Queue<float> samples=new Queue<float>();
        public static void Reset() {lock(gate)samples.Clear();}
        public static void Record(float seconds)
        {
            if(float.IsNaN(seconds) || float.IsInfinity(seconds) || seconds<=0f || seconds>10f)return;
            lock(gate) {samples.Enqueue(seconds*1000f);while(samples.Count>300)samples.Dequeue();}
        }
        public static object Read()
        {
            float[] values;lock(gate)values=samples.ToArray();
            if(values.Length<10)return new {available=false,reason="frame_window_not_ready",sample_count=values.Length};
            Array.Sort(values);
            return new {available=true,sample_count=values.Length,window_seconds=values.Sum()/1000f,
                fps_mean=1000f/values.Average(),frame_ms_p95=values[(int)Math.Floor((values.Length-1)*.95)],
                frame_ms_max=values.Last(),managed_heap_bytes=GC.GetTotalMemory(false),
                note="Unity unscaled frame interval, includes rendering/API work; not process RAM, simulation TPS, GPU usage or proof of cause"};
        }
    }
}
