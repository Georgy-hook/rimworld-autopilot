"""Independent, opt-in camera director for an unattended RimWorld stream.

The observer never orders pawns or changes Laya's decisions. Its only game
writes are camera moves, zoom, an English death caption, and pacing at 3x
outside a home fire, critical bleeding, dangerous disease, serious thermal illness, starvation of a patient,
or an attack on a downed colonist,
when it slows to 1x. Game time is permitted only while a fresh, live director
heartbeat reports running; otherwise the loaded colony stays paused.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import signal
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rimworld_laya import normalize_colonists, thermal_emergency_context


DIRECTOR_HEARTBEAT_SECONDS = 180.0


def _process_alive(pid: int) -> bool:
    """Use the GUI read_pid liveness pattern without modifying its pid file."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except OSError:
            return False
    import ctypes
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


def director_ready(status_path: Path, *, now: float | None = None) -> bool:
    """Only a fresh running heartbeat from a live director permits game time."""
    try:
        with status_path.open(encoding="utf-8-sig") as handle:
            text = handle.read(65537)
        if len(text) > 65536:
            return False
        row = json.loads(text)
        if not isinstance(row, dict) or row.get("state") != "running":
            return False
        pid = row.get("pid")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return False
        stamp = datetime.fromisoformat(str(row.get("updated_at") or "").replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False
        age = (time.time() if now is None else now) - stamp.timestamp()
        return -5 <= age <= DIRECTOR_HEARTBEAT_SECONDS and _process_alive(pid)
    except (OSError, ValueError, TypeError, OverflowError):
        return False


CLOSE_ZOOM = 18
MEDIUM_ZOOM = 34
FAR_ZOOM = 72
DEATH_SECONDS = 20.0
COMBAT_SECONDS = 30.0
IDLE_SECONDS = 45.0
TOUR_INTERVAL = 600.0
TOUR_STOP_SECONDS = 5.0
RAID_SECONDS = 30.0
TARGET_GAME_SPEED = 3
EMERGENCY_GAME_SPEED = 1
SPEED_RETRY_SECONDS = 5.0
TAB_LIFETIME_SECONDS = 30.0
TAB_CLOSE_RETRY_SECONDS = 5.0
MEDICAL_SCAN_SECONDS = 5.0


def _id(row: dict[str, Any]) -> int:
    return int(row.get("id") or 0)


def _position(row: dict[str, Any]) -> dict[str, int] | None:
    pos = row.get("position") or {}
    if pos.get("x") is None or pos.get("z") is None:
        return None
    return {"x": int(pos["x"]), "z": int(pos["z"])}


def _medical_priority(pawn: dict[str, Any]) -> int:
    if float(pawn.get("bleeding_rate") or 0) > 0 or pawn.get("tendable_now"):
        return 2
    if float(pawn.get("health") if pawn.get("health") is not None else 1) < 0.75:
        return 2
    conditions = " ".join(str(value).lower() for value in pawn.get("health_conditions") or [])
    return 1 if any(word in conditions for word in (
        "infection", "flu", "plague", "malaria", "disease", "toxic", "poison", "hypothermia", "heatstroke",
        "gunshot", "stab", "cut", "bite", "bruise", "burn", "malnutrition",
    )) else 0


def _fighting(pawn: dict[str, Any], hostiles: list[dict[str, Any]]) -> bool:
    if pawn.get("is_dead") or pawn.get("is_downed"):
        return False
    job = str(pawn.get("current_job") or "").lower()
    if any(word in job for word in ("attack", "shoot", "fight", "melee", "cast")):
        return True
    if not hostiles:
        return False
    distance = float(pawn.get("distance_to_nearest_opponent") or 9999)
    return bool(pawn.get("is_drafted")) and distance <= max(22.0, float(pawn.get("weapon_range") or 0) + 5)


def _downed_under_attack(colonists: list[dict[str, Any]], hostiles: list[dict[str, Any]]) -> bool:
    """Slow only when an active enemy is near a colony with downed pawns."""
    if not any(pawn.get("is_downed") and not pawn.get("is_dead") for pawn in colonists):
        return False
    return any(
        not hostile.get("is_dead") and not hostile.get("is_downed")
        and isinstance(hostile.get("distance_to_nearest_opponent"), (int, float))
        and hostile["distance_to_nearest_opponent"] <= 40
        for hostile in hostiles
    )


def _critical_disease(rows: Any) -> bool:
    """Summary health and zero bleeding can hide a fatal immunity race."""
    for row in rows if isinstance(rows, list) else []:
        details = row.get("detailes") or row
        medical = details.get("medical_info") or details.get("colonist_medical_info") or {}
        if medical.get("is_dead"):
            continue
        for h in medical.get("hediffs") or []:
            immunity = h.get("immunity")
            if not h.get("can_ever_kill") or not isinstance(immunity, (float, int)) or immunity >= 1:
                continue
            severity = float(h.get("severity") or 0)
            lethal = float(h.get("lethal_severity") or 1)
            if h.get("is_currently_life_threatening") or (
                    severity >= 0.5 * lethal and immunity <= severity):
                return True
    return False


def _pause_if_colony_ended(api: Any, game: dict[str, Any], map_id: int) -> bool:
    # Zero pawns on a map also occurs during caravans and initial loading.
    # Require the actual terminal letter before stopping playback.
    if game.get("colonist_count") != 0:
        return False
    context = api.request("/api/v1/events/context?" + urlencode({"map_id": map_id})) or {}
    ended = any(str(row.get("letter_def") or "") == "GameEnded"
                or "everyone is dead or gone" in str(row.get("text") or "").casefold()
                for row in context.get("letters") or [])
    if not ended:
        return False
    api.request("/api/v1/game/speed?speed=0", post=True)
    return True


def _critical_starvation(rows: Any) -> bool:
    """Stopping bleeding does not make an unfed, immobile patient safe at 3x."""
    for row in rows if isinstance(rows, list) else []:
        details = row.get("detailes") or row
        medical = details.get("medical_info") or details.get("colonist_medical_info") or {}
        if medical.get("is_dead"):
            continue
        for condition in medical.get("hediffs") or []:
            if str(condition.get("def_name") or "") != "Malnutrition":
                continue
            severity = float(condition.get("severity") or 0)
            if condition.get("is_currently_life_threatening") or severity >= 0.5 or (
                    medical.get("is_downed") and severity > 0):
                return True
    return False


def _cause_text(raw: str | None, fallback: str | None = None) -> str:
    cause = str(raw or "").strip()
    if not cause or cause.lower() == "unknown":
        return (f"not reported by the game (last observed condition: {fallback})"
                if fallback else "not reported by the game")
    labels = {
        "Bullet": "gunshot wounds", "Cut": "blade wounds", "Blunt": "blunt-force trauma",
        "Flame": "fire", "Starvation": "starvation", "Malnutrition": "malnutrition", "BloodLoss": "blood loss",
    }
    return labels.get(cause, re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cause).replace("_", " ").lower())


def _critical_condition(conditions: list[str]) -> str | None:
    """Show a relevant last observation without calling an old scar the cause."""
    names = [str(condition) for condition in conditions]
    markers = ("bloodloss", "blood loss", "malnutrition", "infection", "heatstroke",
               "hypothermia", "toxic", "plague", "flu", "malaria", "disease")
    # Combat DTO strings have no severity. Do not rank residual blood loss above
    # concurrent starvation and accidentally imply that it caused the death.
    relevant = dict.fromkeys(name for name in names if any(marker in name.lower() for marker in markers))
    return "; ".join(relevant)[:240] or None


def parse_sse_event(event_type: str, data: str) -> dict[str, Any] | None:
    if event_type != "pawn_killed":
        return None
    try:
        payload = json.loads(data)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    pawn = payload.get("pawn") or {}
    if not isinstance(pawn, dict) or not pawn.get("isColonist") or not pawn.get("id"):
        return None
    try:
        pawn_id = int(pawn["id"])
    except (ValueError, TypeError):
        return None
    event = {"id": pawn_id, "name": str(pawn.get("name") or "Colonist"),
             "cause": str(payload.get("cause") or "Unknown"), "ticks": payload.get("ticks")}
    if payload.get("cause_source"):
        event["cause_source"] = payload["cause_source"]
    return event


@dataclass
class Shot:
    kind: str
    started: float
    duration: float
    target_id: int | None = None
    target_name: str = ""
    position: dict[str, int] | None = None
    zoomed_out: bool = False
    last_follow: float = 0.0


class TimedWindowCloser:
    """Leave research and quest tabs visible briefly, then return to the map."""

    def __init__(self) -> None:
        self.first_seen: dict[str, float] = {}
        self.last_attempt: dict[str, float] = {}

    def step(self, windows: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
        visible = {
            name for row in windows if isinstance(row, dict)
            if (name := str(row.get("window_type") or ""))
            and name.casefold().startswith("maintabwindow_")
            and any(token in name.casefold() for token in ("research", "quest"))
        }
        self.first_seen = {name: self.first_seen.get(name, now) for name in visible}
        self.last_attempt = {name: attempted for name, attempted in self.last_attempt.items()
                             if name in visible}
        actions = []
        for name in sorted(visible):
            if (now - self.first_seen[name] >= TAB_LIFETIME_SECONDS
                    and now - self.last_attempt.get(name, -9999.0) >= TAB_CLOSE_RETRY_SECONDS):
                self.last_attempt[name] = now
                actions.append({"kind": "close_window", "window_type": name})
        return actions


class ObserverPlanner:
    """Pure wall-clock shot scheduler; API calls are performed by the runner."""

    def __init__(self) -> None:
        self.map_key: tuple[Any, ...] | None = None
        self.last_game_tick: int | None = None
        self.known: dict[int, dict[str, Any]] = {}
        self.missing_since: dict[int, float] = {}
        self.shown_deaths: set[int] = set()
        self.death_queue: list[dict[str, Any]] = []
        self.shot: Shot | None = None
        self.last_unpause = -9999.0
        self.last_speed_request = -9999.0
        self.last_requested_speed: int | None = None
        self.last_shown: dict[int, float] = {}
        self.medical_last_shown: dict[int, float] = {}
        self.seen_hostiles: set[int] = set()
        self.raid_ids: list[int] = []
        self.raid_started = 0.0
        self.raid_index = -1
        self.next_tour_at = 0.0
        self.tour_started = 0.0
        self.tour_index = -1
        self.last_fighter_id: int | None = None

    def _reset_for_map(self, key: tuple[Any, ...], now: float) -> None:
        self.__init__()
        self.map_key = key
        self.next_tour_at = now + TOUR_INTERVAL

    def _start(self, kind: str, now: float, duration: float, *, pawn: dict[str, Any] | None = None,
               position: dict[str, int] | None = None, caption: str = "", zoom: int = CLOSE_ZOOM) -> list[dict[str, Any]]:
        pawn_id = _id(pawn or {}) or None
        self.shot = Shot(kind, now, duration, pawn_id, str((pawn or {}).get("name") or ""), position, False, now)
        actions: list[dict[str, Any]] = []
        if pawn_id is not None:
            actions.append({"kind": "follow", "pawn_id": pawn_id})
            self.last_shown[pawn_id] = now
        elif position:
            actions.append({"kind": "position", **position})
        actions.append({"kind": "zoom", "zoom": zoom})
        if caption:
            actions.append({"kind": "caption", "text": caption, "duration": DEATH_SECONDS})
        return actions

    @staticmethod
    def _tour_points(map_row: dict[str, Any]) -> list[dict[str, int]]:
        dimensions = re.findall(r"\d+", str(map_row.get("size") or "250x250"))
        # RIMAPI reports Unity map dimensions as (x, y, z); y is normally 1.
        width, height = (int(dimensions[0]), int(dimensions[-1])) if len(dimensions) >= 2 else (250, 250)
        return [{"x": int(width * x), "z": int(height * z)} for x, z in (
            (0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75), (0.5, 0.5),
        )]

    def _collect_deaths(self, colonists: list[dict[str, Any]], corpses: list[dict[str, Any]],
                        events: list[dict[str, Any]], now: float) -> None:
        alive_ids = {_id(pawn) for pawn in colonists}
        event_ids = {int(event.get("id") or 0) for event in events}
        for pawn_id, previous in self.known.items():
            if pawn_id in alive_ids:
                self.missing_since.pop(pawn_id, None)
                continue
            self.missing_since.setdefault(pawn_id, now)
            if pawn_id in self.shown_deaths or pawn_id in event_ids:
                continue
            # A pawn can leave the map without dying. Require a matching corpse.
            name = str(previous.get("name") or "").lower()
            corpse = next((row for row in corpses if name and name in str(row.get("label") or "").lower()
                           and "corpse" in str(row.get("def_name") or "").lower()), None)
            if corpse:
                conditions = previous.get("health_conditions") or []
                self.death_queue.append({"id": pawn_id, "name": previous.get("name"), "cause": "Unknown",
                                         "fallback": _critical_condition(conditions),
                                         "position": _position(corpse) or _position(previous)})
                event_ids.add(pawn_id)
        for event in events:
            pawn_id = int(event.get("id") or 0)
            if not pawn_id or pawn_id in self.shown_deaths or any(int(row["id"]) == pawn_id for row in self.death_queue):
                continue
            previous = self.known.get(pawn_id) or {}
            corpse = next((row for row in corpses if str(event.get("name") or "").lower()
                           in str(row.get("label") or "").lower()
                           and "corpse" in str(row.get("def_name") or "").lower()), None)
            conditions = previous.get("health_conditions") or []
            self.death_queue.append({**event, "fallback": _critical_condition(conditions),
                                     "position": _position(corpse or {}) or _position(previous)})
        previous_known = self.known
        self.known = {_id(pawn): dict(pawn) for pawn in colonists if _id(pawn)}
        # Corpses can appear one or more API polls after a pawn disappears.
        for pawn_id, previous in previous_known.items():
            if pawn_id not in alive_ids and pawn_id not in self.shown_deaths and now - self.missing_since[pawn_id] <= 15:
                self.known[pawn_id] = previous
        self.missing_since = {pawn_id: missing_at for pawn_id, missing_at in self.missing_since.items()
                              if pawn_id not in alive_ids and pawn_id in self.known}

    def step(self, snapshot: dict[str, Any], events: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
        game = snapshot.get("game") or {}
        map_row = snapshot.get("map") or {}
        colonists = [row for row in snapshot.get("colonists") or [] if _id(row) and not row.get("is_dead")]
        hostiles = [row for row in snapshot.get("hostiles") or [] if _id(row) and not row.get("is_dead")]
        corpses = snapshot.get("corpses") or []
        key = (map_row.get("id"), map_row.get("seed"), map_row.get("tile_id"))
        tick = int(game.get("game_tick") or 0)
        if self.map_key != key or (self.last_game_tick is not None and tick + 100 < self.last_game_tick):
            self._reset_for_map(key, now)
        self.last_game_tick = tick
        actions: list[dict[str, Any]] = []
        # SSE is not replayed, but a queued event can survive a save rollback.
        fresh_events = []
        for event in events:
            try:
                if event.get("ticks") is None or 0 <= tick - int(event["ticks"]) <= 30000:
                    fresh_events.append(event)
            except (ValueError, TypeError):
                continue
        self._collect_deaths(colonists, corpses, fresh_events, now)
        by_id = {_id(pawn): pawn for pawn in colonists}
        hostile_by_id = {_id(pawn): pawn for pawn in hostiles}

        if self.shot and self.shot.kind == "death" and now - self.shot.started < DEATH_SECONDS:
            return actions
        if self.death_queue:
            event = self.death_queue.pop(0)
            self.shown_deaths.add(int(event["id"]))
            caption = f"{event.get('name') or 'Colonist'} died\nCause: {_cause_text(event.get('cause'), event.get('fallback'))}"
            actions.extend(self._start("death", now, DEATH_SECONDS, position=event.get("position"), caption=caption))
            # Keep structured evidence in observer.jsonl; captions alone lose
            # the pawn ID, native tick and exact/unknown cause distinction.
            actions[-1]["death"] = {key: event.get(key) for key in
                ("id", "name", "cause", "cause_source", "ticks", "fallback")}
            return actions

        fighters = [pawn for pawn in colonists if _fighting(pawn, hostiles)]
        if fighters:
            self.raid_ids = []  # active combat supersedes the pre-battle tour
            fighter_ids = {_id(pawn) for pawn in fighters}
            if (not self.shot or self.shot.kind != "combat" or self.shot.target_id not in fighter_ids
                    or (len(fighters) > 1 and now - self.shot.started >= COMBAT_SECONDS)):
                ordered = sorted(fighters, key=_id)
                next_index = next((i for i, pawn in enumerate(ordered) if _id(pawn) == self.last_fighter_id), -1) + 1
                fighter = ordered[next_index % len(ordered)]
                self.last_fighter_id = _id(fighter)
                actions.extend(self._start("combat", now, COMBAT_SECONDS, pawn=fighter))
            else:
                actions.extend(self._maintain_focus(now, MEDIUM_ZOOM))
            return actions

        if self.shot and self.shot.kind == "death" and colonists:
            # The memorial ends on the colony, even when hostiles are still on
            # the map. A fresh raider montage can wait for the next shot.
            pawn = min(colonists, key=lambda row: (self.last_shown.get(_id(row), -9999), -_medical_priority(row), _id(row)))
            actions.extend(self._start("idle", now, IDLE_SECONDS, pawn=pawn))
            return actions

        current_hostiles = set(hostile_by_id)
        if not current_hostiles:
            self.seen_hostiles.clear()
            self.raid_ids = []
        elif current_hostiles - self.seen_hostiles and not self.raid_ids:
            self.raid_ids = sorted(current_hostiles)
            self.raid_started = now
            self.raid_index = -1
        self.seen_hostiles |= current_hostiles
        if self.raid_ids and now - self.raid_started < RAID_SECONDS:
            available = [pawn_id for pawn_id in self.raid_ids if pawn_id in hostile_by_id]
            if available:
                slot = RAID_SECONDS / len(available)
                index = min(len(available) - 1, int((now - self.raid_started) / slot))
                if index != self.raid_index or not self.shot or self.shot.kind != "raiders":
                    self.raid_index = index
                    actions.extend(self._start("raiders", now, slot, pawn=hostile_by_id[available[index]], zoom=MEDIUM_ZOOM))
                return actions
        if self.raid_ids:
            self.raid_ids = []

        urgent = [pawn for pawn in colonists if _medical_priority(pawn)
                  and now - self.medical_last_shown.get(_id(pawn), -9999) >= 120]
        if urgent and (not self.shot or self.shot.kind not in {"medical", "idle"}
                       or now - self.shot.started >= IDLE_SECONDS
                       or (self.shot.kind == "idle" and now - self.shot.started >= 10)):
            pawn = min(urgent, key=lambda row: (self.medical_last_shown.get(_id(row), -9999), -_medical_priority(row)))
            self.medical_last_shown[_id(pawn)] = now
            actions.extend(self._start("medical", now, IDLE_SECONDS, pawn=pawn))
            return actions

        if now >= self.next_tour_at:
            points = self._tour_points(map_row)
            if not self.shot or self.shot.kind != "tour":
                self.tour_started, self.tour_index = now, -1
            index = int((now - self.tour_started) / TOUR_STOP_SECONDS)
            if index < len(points):
                if index != self.tour_index:
                    self.tour_index = index
                    actions.extend(self._start("tour", now, TOUR_STOP_SECONDS, position=points[index], zoom=FAR_ZOOM))
                return actions
            self.next_tour_at = self.tour_started + TOUR_INTERVAL

        if not colonists:
            self.shot = None
            return actions
        if not self.shot or self.shot.kind not in {"idle", "medical"} or self.shot.target_id not in by_id or now - self.shot.started >= IDLE_SECONDS:
            pawn = min(colonists, key=lambda row: (self.last_shown.get(_id(row), -9999), -_medical_priority(row), _id(row)))
            actions.extend(self._start("idle", now, IDLE_SECONDS, pawn=pawn))
        else:
            actions.extend(self._maintain_focus(now, FAR_ZOOM))
        return actions

    def pacing_actions(self, game: dict[str, Any], now: float, *, home_fire: bool = False,
                       critical_bleeding: bool = False,
                       downed_under_attack: bool = False,
                       critical_disease: bool = False, critical_starvation: bool = False,
                       critical_thermal: bool = False,
                       director_is_ready: bool = True) -> list[dict[str, Any]]:
        """Run at 3x normally and give Laya more cycles during live emergencies."""
        target = EMERGENCY_GAME_SPEED if home_fire or critical_bleeding or downed_under_attack or critical_disease or critical_starvation or critical_thermal else TARGET_GAME_SPEED
        if not director_is_ready:
            target = 0
            if game.get("is_paused"):
                self.last_requested_speed = 0
                return []
        changed = target != self.last_requested_speed
        if game.get("is_paused"):
            if not changed and now - self.last_unpause < SPEED_RETRY_SECONDS:
                return []
            self.last_unpause = now
        elif not changed and now - self.last_speed_request < SPEED_RETRY_SECONDS:
            return []
        self.last_speed_request = now
        self.last_requested_speed = target
        return [{"kind": "ensure_speed", "speed": target}]

    def _maintain_focus(self, now: float, zoom_out: int) -> list[dict[str, Any]]:
        shot = self.shot
        if shot is None:
            return []
        actions: list[dict[str, Any]] = []
        if not shot.zoomed_out and now - shot.started >= 10:
            actions.append({"kind": "zoom", "zoom": zoom_out})
            shot.zoomed_out = True
        if shot.target_id and now - shot.last_follow >= 3:
            actions.append({"kind": "follow", "pawn_id": shot.target_id})
            shot.last_follow = now
        return actions


class RimApi:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, *, post: bool = False, body: dict[str, Any] | None = None) -> Any:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(self.base_url + path, data=payload, method="POST" if post else "GET",
                      headers={"Content-Type": "application/json", "Accept": "application/json"})
        with urlopen(req, timeout=3) as response:
            result = json.load(response)
        if not result.get("success", False):
            raise RuntimeError("; ".join(map(str, result.get("errors") or [])) or path)
        return result.get("data")


class DeathEventReader(threading.Thread):
    def __init__(self, base_url: str, outbox: queue.Queue[dict[str, Any]], stop: threading.Event) -> None:
        super().__init__(daemon=True, name="rimworld-death-events")
        self.url, self.outbox, self.stop = base_url.rstrip("/") + "/api/v1/events", outbox, stop

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                with urlopen(Request(self.url, headers={"Accept": "text/event-stream"}), timeout=10) as response:
                    event_type, payload = "", []
                    while not self.stop.is_set():
                        raw_line = response.readline()
                        if not raw_line:
                            break
                        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                        if not line:
                            event = parse_sse_event(event_type, "\n".join(payload))
                            if event:
                                self.outbox.put(event)
                            event_type, payload = "", []
                        elif line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            payload.append(line[5:].strip())
            except (OSError, HTTPError, URLError, TimeoutError, ValueError):
                self.stop.wait(2)
            else:
                self.stop.wait(1)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # GUI polling can briefly hold the destination open on Windows. Status is
    # advisory; a failed replace must not terminate the camera director.
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt < 7:
                time.sleep(0.04 * (attempt + 1))


def _log(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=False) + "\n")


def _execute(api: RimApi, action: dict[str, Any]) -> None:
    kind = action["kind"]
    if kind == "ensure_speed":
        api.request("/api/v1/game/speed?" + urlencode({"speed": action["speed"]}), post=True)
    elif kind == "follow":
        api.request("/api/v1/camera/follow/pawn?" + urlencode({"pawn_id": action["pawn_id"]}), post=True)
    elif kind == "position":
        api.request("/api/v1/camera/change/position?" + urlencode({"x": action["x"], "y": action["z"]}), post=True)
    elif kind == "zoom":
        api.request("/api/v1/camera/change/zoom?" + urlencode({"zoom": action["zoom"]}), post=True)
    elif kind == "caption":
        api.request("/api/v1/ui/announce", post=True, body={
            "text": action["text"], "duration": action["duration"], "color": "#FFF1D6",
            "scale": 1.15, "panel": True, "compact": True, "bars": [],
        })
    elif kind == "close_window":
        api.request("/api/v1/ui/window/close", post=True, body={
            "window_types": [action["window_type"]], "force_pause_only": False,
        })


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Opt-in Twitch camera observer for RimWorld Autopilot")
    parser.add_argument("--api-url", default="http://localhost:8765")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--pid-file", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    api = RimApi(args.api_url)
    planner = ObserverPlanner()
    window_closer = TimedWindowCloser()
    next_window_scan = 0.0
    next_medical_scan = 0.0
    critical_disease = False
    critical_thermal = False
    thermal_context: list[dict[str, Any]] = []
    critical_starvation = False
    outbox: queue.Queue[dict[str, Any]] = queue.Queue()
    DeathEventReader(args.api_url, outbox, stop).start()
    args.pid_file.parent.mkdir(parents=True, exist_ok=True)
    args.pid_file.write_text(str(os.getpid()), encoding="ascii")
    stopped_detail = "Observer stopped"
    try:
        while not stop.is_set():
            now = time.monotonic()
            try:
                ending = api.request("/api/v1/colony/ending-evidence") or {}
                victory = (ending.get("victory_verified") is True
                           and isinstance(ending.get("ending_tick"), int) and ending["ending_tick"] >= 0)
                if victory or ending.get("game_over_verified") is True:
                    try:
                        api.request("/api/v1/game/speed?speed=0", post=True)
                    except (HTTPError, URLError):
                        pass
                    stopped_detail = "Native ending confirmed; observer stopped"
                    _log(args.log, {"action": {"kind": "victory" if victory else "colony_ended", **ending}, "detail": stopped_detail})
                    break
                game = api.request("/api/v1/game/state") or {}
                maps = api.request("/api/v1/maps") or []
                current_map = next((row for row in maps if row.get("is_current_map")), maps[0] if maps else None)
                if game.get("program_state") != "Playing" or current_map is None:
                    _write_json(args.status, {"pid": os.getpid(), "state": "waiting", "updated_at": datetime.now(timezone.utc).isoformat(),
                                              "detail": "Waiting for a loaded colony", "death_overlay_until": 0})
                    stop.wait(2)
                    continue
                if _pause_if_colony_ended(api, game, int(current_map["id"])):
                    stopped_detail = "Colony ended; game paused and observer stopped"
                    _log(args.log, {"action": {"kind": "colony_ended", "tick": game.get("game_tick")},
                                    "detail": stopped_detail})
                    break
                runtime_ready = director_ready(args.status.with_name("runtime-status.json"))
                # Pause before other observation reads: a failed camera/medical
                # request must not let an unattended colony keep advancing.
                if not runtime_ready:
                    for action in planner.pacing_actions(game, now, director_is_ready=False):
                        _execute(api, action)
                        _log(args.log, {"action": action, "reason": "director_not_ready"})
                combat = api.request("/api/v1/combat/state?" + urlencode({"map_id": current_map["id"]})) or {}
                fires = api.request("/api/v1/map/fire/situation?" + urlencode({"map_id": current_map["id"]})) or {}
                home_fire = any(fire.get("in_home") and int(fire.get("nearby_player_buildings") or 0) > 0
                                for fire in fires.get("fires") or [])
                critical_bleeding = any(pawn.get("tendable_now") and not pawn.get("is_dead")
                                        and float(pawn.get("bleeding_rate") or 0) >= 1.5
                                        for pawn in combat.get("colonists") or [])
                if now >= next_medical_scan:
                    medical_rows = api.request("/api/v2/colonists/detailed")
                    critical_disease = _critical_disease(medical_rows)
                    thermal_context = thermal_emergency_context(normalize_colonists(medical_rows))
                    critical_thermal = bool(thermal_context)
                    critical_starvation = _critical_starvation(medical_rows)
                    next_medical_scan = now + MEDICAL_SCAN_SECONDS
                downed_under_attack = _downed_under_attack(
                    combat.get("colonists") or [], combat.get("hostiles") or [])
                events: list[dict[str, Any]] = []
                while True:
                    try:
                        events.append(outbox.get_nowait())
                    except queue.Empty:
                        break
                current_ids = {_id(pawn) for pawn in combat.get("colonists") or []}
                corpses: list[dict[str, Any]] = []
                if events or any(pawn_id not in current_ids for pawn_id in planner.known):
                    things = api.request("/api/v1/map/things?" + urlencode({"map_id": current_map["id"]})) or []
                    corpses = [row for row in things if "corpse" in str(row.get("def_name") or "").lower()]
                snapshot = {"game": game, "map": current_map, "colonists": combat.get("colonists") or [],
                            "hostiles": combat.get("hostiles") or [], "corpses": corpses}
                actions = planner.step(snapshot, events, now)
                # Observation reads can take time; refresh the small heartbeat
                # before allowing an unpause or speed increase.
                runtime_ready = director_ready(args.status.with_name("runtime-status.json"))
                actions = planner.pacing_actions(game, now, home_fire=home_fire,
                                                 critical_bleeding=critical_bleeding,
                                                 downed_under_attack=downed_under_attack,
                                                 critical_disease=critical_disease,
                                                 critical_starvation=critical_starvation,
                                                 critical_thermal=critical_thermal,
                                                 director_is_ready=runtime_ready) + actions
                if now >= next_window_scan:
                    windows = api.request("/api/v1/ui/windows") or []
                    actions.extend(window_closer.step(windows, now))
                    next_window_scan = now + 1.0
                death_until = time.time() + max(0, DEATH_SECONDS - (now - planner.shot.started)) if planner.shot and planner.shot.kind == "death" else 0
                shot = planner.shot
                status = {"pid": os.getpid(), "state": "running", "updated_at": datetime.now(timezone.utc).isoformat(),
                          "detail": "Camera is following the colony", "shot": shot.kind if shot else "waiting",
                          "director_ready": runtime_ready,
                          "target_speed": 0 if not runtime_ready else EMERGENCY_GAME_SPEED if home_fire or critical_bleeding or downed_under_attack or critical_disease or critical_starvation or critical_thermal else TARGET_GAME_SPEED,
                          "critical_disease": critical_disease,
                          "critical_thermal": critical_thermal,
                          "thermal_context": thermal_context,
                          "speed_reason": "director_not_ready" if not runtime_ready else "thermal_emergency" if critical_thermal else "other_emergency" if home_fire or critical_bleeding or downed_under_attack or critical_disease or critical_starvation else "normal",
                          "critical_starvation": critical_starvation,
                          "target": shot.target_name if shot else "", "remaining": round(max(0, shot.duration - (now - shot.started)), 1) if shot else 0,
                          "death_overlay_until": death_until}
                # Mark the death spotlight before announcing it so Laya's HUD
                # cannot immediately replace the cause-of-death caption.
                _write_json(args.status, status)
                for action in actions:
                    try:
                        _execute(api, action)
                        if action["kind"] not in {"follow"}:
                            _log(args.log, {"action": action, "shot": status["shot"],
                                            **({"reason": status["speed_reason"], "thermal_context": thermal_context}
                                               if action["kind"] == "ensure_speed" else {})})
                    except (OSError, RuntimeError, ValueError) as exc:
                        _log(args.log, {"action": action, "error": str(exc)[:300]})
            except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
                _write_json(args.status, {"pid": os.getpid(), "state": "waiting", "updated_at": datetime.now(timezone.utc).isoformat(),
                                          "detail": f"RimWorld connection: {str(exc)[:180]}", "death_overlay_until": 0})
                stop.wait(2)
            stop.wait(max(0.25, args.interval))
    finally:
        _write_json(args.status, {"pid": os.getpid(), "state": "stopped", "updated_at": datetime.now(timezone.utc).isoformat(),
                                  "detail": stopped_detail, "death_overlay_until": 0})
        args.pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
