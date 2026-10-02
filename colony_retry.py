"""JSON-safe retry clocks for one failed option, independent of game speed."""
from __future__ import annotations
import math
import time


def _number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def failure_record(tick: int, seconds: float = 30) -> dict:
    now = time.time()
    return {"tick": tick, "retry_started_at": now, "retry_until": now + seconds}


def recent(record, tick, tick_horizon, *, now=None) -> bool:
    """Expire after both clocks; invalidate malformed data and clock rollback.

    Successful/deferred and legacy records without wall-clock fields retain
    their game-time policy. Only failure_record adds the real-time floor.
    """
    if not isinstance(record, dict) or not all(_number(v) for v in (record.get("tick"), tick, tick_horizon)):
        return False
    if tick_horizon <= 0 or tick < record["tick"]:
        return False
    game_pending = tick - record["tick"] < tick_horizon
    if "retry_started_at" not in record and "retry_until" not in record:
        return game_pending
    start, end = record.get("retry_started_at"), record.get("retry_until")
    now = time.time() if now is None else now
    if not all(_number(v) for v in (start, end, now)) or not 0 < end - start <= 300 or now < start:
        return False
    return game_pending or now < end
