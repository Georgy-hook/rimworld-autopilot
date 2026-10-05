using System;
using System.Collections.Generic;
using System.Linq;
namespace RIMAPI.Helpers {
    // Call only in the synchronous Unity-thread read phase, before invoking native callbacks.
    // Native MapPawns/PawnsFinder getters return borrowed scratch lists which another getter can clear.
    public static class EndingReadBoundary {
        public static T[] Capture<T>(Func<IEnumerable<T>> readBorrowed) => readBorrowed().ToArray();
        public static TResult[] Project<T, TResult>(T[] owned, Func<T, TResult> nativeProjection) => owned.Select(nativeProjection).ToArray();
    }
}
