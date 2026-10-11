using System;

namespace RIMAPI.Helpers
{
    public static class QuestPublicReadBoundary
    {
        // Historical targets may already have been discarded. Do not mutate
        // those lists or turn missing past actors into live opportunities.
        public static T Live<T>(bool historical, Func<T> read, T historicalValue)
            => historical ? historicalValue : read();
    }
}
