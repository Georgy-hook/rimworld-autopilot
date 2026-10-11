using System;
using System.Collections.Generic;

namespace RIMAPI.Helpers
{
    // A failed public subject must not erase unrelated observations. This
    // boundary is read-only; no mutation uses an incomplete observation.
    public static class ObservationBoundary
    {
        public static bool Read<T>(string subject, Func<T> read, Action<T> receive,
            IDictionary<string, string> errors, Action<Exception> diagnose = null)
        {
            try { receive(read()); return true; }
            catch (Exception error)
            {
                errors[subject] = error.GetBaseException().GetType().Name;
                try { diagnose?.Invoke(error); } catch (Exception) { /* The read error remains visible even if diagnostic logging fails. */ }
                return false;
            }
        }
    }
}
