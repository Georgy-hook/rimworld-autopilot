from __future__ import annotations

import csv
import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


from app_version import APP_VERSION

APP_NAME = f"RimWorld Autopilot {APP_VERSION}"
BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
# Resolve data-directory junctions before passing paths to a Store Python child.
# Its AppData view can otherwise differ from the native GUI's view.
DATA_DIR = ((Path(os.environ.get("LOCALAPPDATA", str(BASE_DIR))) / "RimWorld Autopilot") if getattr(sys, "frozen", False) else BASE_DIR).resolve()
CONFIG_PATH = DATA_DIR / "rimworld-autopilot.json"
PACKAGED_CONFIG_PATH = BASE_DIR / "rimworld-autopilot.json"
LEGACY_CONFIG_PATH = BASE_DIR / "laya-control.json"
PREFERENCES_PATH = DATA_DIR / "autopilot-preferences.json"
FEEDBACK_PATH = DATA_DIR / "laya-feedback.jsonl"
OBSERVER_STATUS_PATH = DATA_DIR / "logs" / "observer-status.json"
OBSERVER_PID_PATH = DATA_DIR / "logs" / "observer.pid"
OBSERVER_LOG_PATH = DATA_DIR / "logs" / "observer.jsonl"
DEFAULT_CONFIG = {
    "python_exe": str(BASE_DIR / ".venv" / "Scripts" / "python.exe"),
    "director_script": str(BASE_DIR / "colony_director.py"),
    "api_url": "http://localhost:8765",
    "device": "cuda",
    "interval": 10,
}


def resolve_log_dir(config: dict[str, Any]) -> Path:
    """Select one run directory without changing existing filesystem links."""
    configured = config.get("logs_dir")
    if not isinstance(configured, (str, os.PathLike)) or not str(configured).strip():
        configured = "logs"
    path = Path(configured)
    return (path if path.is_absolute() else DATA_DIR / path).resolve()


def active_map_key(maps_response: dict[str, Any]) -> str | None:
    """Match the director's map-state key for the map currently on screen."""
    maps = maps_response.get("data") or []
    if not isinstance(maps, list):
        return None
    current = next((row for row in maps if isinstance(row, dict) and row.get("is_current_map")), None)
    if current is None:
        current = next((row for row in maps if isinstance(row, dict) and row.get("is_player_home")), None)
    if current is None:
        return None
    return ":".join(str(current[field]) if current.get(field) is not None else "unknown"
                    for field in ("seed", "tile_id", "id"))


def load_config() -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    try:
        source = next((path for path in (CONFIG_PATH, PACKAGED_CONFIG_PATH, LEGACY_CONFIG_PATH) if path.exists()), CONFIG_PATH)
        loaded = json.loads(source.read_text(encoding="utf-8-sig"))
        if isinstance(loaded, dict):
            config.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass
    for key in ("python_exe", "director_script"):
        value = Path(str(config[key]))
        if not value.is_absolute():
            config[key] = str((BASE_DIR / value).resolve())
    return config


def process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    process = kernel.OpenProcess(0x1000, False, pid)
    if not process:
        return False
    try:
        exit_code = wintypes.DWORD()
        # A terminated process object can remain open while another handle is
        # retained. OpenProcess success alone is not evidence of a live worker.
        return bool(kernel.GetExitCodeProcess(process, ctypes.byref(exit_code))) and exit_code.value == 259
    finally:
        kernel.CloseHandle(process)


def read_pid(path: Path) -> int | None:
    try:
        pid = int(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None
    if process_running(pid):
        return pid
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return None


def read_director_health(pid_path: Path, status_path: Path, stale_after: float = 45.0) -> dict[str, Any]:
    """Combine process liveness with a fresh director heartbeat.

    A PID alone can describe a hung director or, after PID reuse, an unrelated
    process. The status file is written by the director and carries the same PID,
    current phase and a UTC heartbeat.
    """

    pid = read_pid(pid_path)
    if not pid:
        return {"state": "stopped", "pid": None, "healthy": False, "detail": ""}
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or int(payload.get("pid") or 0) != pid:
            raise ValueError("runtime status belongs to another process")
        updated = datetime.fromisoformat(str(payload.get("updated_at") or "").replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - updated).total_seconds())
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        try:
            age = max(0.0, (datetime.now().timestamp() - pid_path.stat().st_mtime))
        except OSError:
            age = stale_after + 1
        state = "starting" if age <= stale_after else "unresponsive"
        return {"state": state, "pid": pid, "healthy": False, "detail": "", "age": age}
    state = str(payload.get("state") or "running")
    if age > stale_after:
        state = "unresponsive"
    return {
        **payload,
        "state": state,
        "pid": pid,
        "healthy": state == "running",
        "age": age,
        "detail": str(payload.get("detail") or ""),
    }


def tail_jsonl(path: Path, limit: int = 80, max_bytes: int | None = 8_000_000) -> list[dict[str, Any]]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            chunks: list[bytes] = []
            lines = 0
            loaded = 0
            while size > 0 and lines <= limit and (max_bytes is None or loaded < max_bytes):
                take = min(65536, size, max_bytes - loaded if max_bytes is not None else size)
                size -= take
                handle.seek(size)
                chunk = handle.read(take)
                chunks.append(chunk)
                lines += chunk.count(b"\n")
                loaded += take
            data = b"".join(reversed(chunks))
            if size > 0:
                # The capped read can start mid-record. Ignore that fragment.
                data = data.partition(b"\n")[2]
        rows = []
        for line in data.splitlines()[-limit:]:
            try:
                value = json.loads(line.decode("utf-8"))
                if isinstance(value, dict):
                    rows.append(value)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return rows
    except OSError:
        return []


def request_json(url: str, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method, headers=headers)
    with urlopen(req, timeout=1.5) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def start_director(config: dict[str, Any], log_path: Path, state_path: Path, pid_path: Path, runtime_status_path: Path) -> int:
    python_exe = Path(str(config["python_exe"]))
    director = Path(str(config["director_script"]))
    if not python_exe.exists() or not director.exists():
        raise FileNotFoundError(f"{python_exe}\n{director}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stdout = (log_path.parent / "director.stdout.log").open("ab")
    stderr = (log_path.parent / "director.stderr.log").open("ab")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    args = [
        str(python_exe), "-u", str(director), "--device", str(config.get("device", "cuda")),
        "--interval", str(config.get("interval", 10)), "--api-url", str(config.get("api_url", "http://localhost:8765")),
        "--log", str(log_path), "--state", str(state_path), "--pid-file", str(pid_path),
        "--runtime-status", str(runtime_status_path),
    ]
    environment = os.environ.copy()
    environment["RIMWORLD_AUTOPILOT_PREFERENCES"] = str(PREFERENCES_PATH)
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        runtime_status_path.unlink(missing_ok=True)
        pid_path.unlink(missing_ok=True)
        process = subprocess.Popen(args, cwd=BASE_DIR, stdout=stdout, stderr=stderr, creationflags=flags, env=environment)
        # A Windows venv launcher can create a child python3.x process. The
        # director writes its own real PID immediately; overwriting it with the
        # launcher PID would make its heartbeat look unrelated to the process.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                director_pid = int(pid_path.read_text(encoding="ascii").strip())
                if director_pid > 0:
                    return director_pid
            except (OSError, ValueError):
                time.sleep(0.05)
        return process.pid
    finally:
        stdout.close()
        stderr.close()


def stop_director(pid_path: Path, runtime_status_path: Path | None = None) -> int | None:
    pid = read_pid(pid_path)
    if not pid:
        return None
    os.kill(pid, signal.SIGTERM)
    pid_path.unlink(missing_ok=True)
    if runtime_status_path is not None:
        runtime_status_path.unlink(missing_ok=True)
    return pid


def start_observer(config: dict[str, Any], pid_path: Path = OBSERVER_PID_PATH,
                   status_path: Path = OBSERVER_STATUS_PATH, log_path: Path = OBSERVER_LOG_PATH) -> int:
    """Start the light camera process independently from the Laya model."""
    python_exe = Path(str(config["python_exe"]))
    script = Path(str(config.get("observer_script") or BASE_DIR / "stream_observer.py"))
    if not python_exe.exists() or not script.exists():
        raise FileNotFoundError(f"{python_exe}\n{script}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.unlink(missing_ok=True)
    pid_path.unlink(missing_ok=True)
    stdout = (log_path.parent / "observer.stdout.log").open("ab")
    stderr = (log_path.parent / "observer.stderr.log").open("ab")
    try:
        process = subprocess.Popen([
            str(python_exe), "-u", str(script), "--api-url", str(config.get("api_url", "http://localhost:8765")),
            "--pid-file", str(pid_path), "--status", str(status_path), "--log", str(log_path),
        ], cwd=BASE_DIR, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                return int(pid_path.read_text(encoding="ascii").strip())
            except (OSError, ValueError):
                if process.poll() is not None:
                    raise RuntimeError("Observer exited during startup; see observer.stderr.log")
                time.sleep(0.05)
        return process.pid
    finally:
        stdout.close()
        stderr.close()


def export_history(log_path: Path, destination: Path) -> None:
    if destination.suffix.lower() == ".jsonl":
        shutil.copy2(log_path, destination)
        return
    records = tail_jsonl(log_path, limit=100000, max_bytes=None)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "mode", "choice", "confidence", "candidates", "result"])
        for row in records:
            decision = row.get("decision") or {}
            writer.writerow([
                row.get("timestamp"), row.get("mode"), decision.get("choice"), decision.get("confidence"),
                ", ".join(row.get("candidates") or []), json.dumps(row.get("result"), ensure_ascii=False),
            ])


def append_feedback(path: Path, record: dict[str, Any], corrected_choice: str, note: str = "") -> None:
    """Keep human corrections as labels; never treat them as online weight updates."""
    candidates = list(record.get("candidates") or [])
    raw = (record.get("decision") or {}).get("raw") or {}
    if corrected_choice not in candidates:
        raise ValueError("Correction must be one of the recorded feasible actions")
    if not isinstance(raw.get("visible_state"), dict):
        raise ValueError("This older decision has no saved model context to label")
    feedback = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_timestamp": record.get("timestamp"),
        "map_seed": record.get("map_seed"),
        "visible_state": raw["visible_state"],
        "candidates": candidates,
        "model_choice": (record.get("decision") or {}).get("choice"),
        "human_choice": corrected_choice,
        "note": str(note)[:1000],
        "question_path": {key: raw.get(key) for key in ("domain", "family", "action", "details")},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(feedback, ensure_ascii=False, default=str) + "\n")


def export_bundle(destination: Path, log_path: Path, state_path: Path) -> None:
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for pattern in ("*.py", "*.md", "*.ps1", "*.cmd", "*.json"):
            for path in BASE_DIR.glob(pattern):
                archive.write(path, path.name)
        for folder in ("laya_gui", "assets"):
            root = BASE_DIR / folder
            if root.exists():
                for path in root.rglob("*"):
                    if path.is_file() and "__pycache__" not in path.parts:
                        archive.write(path, path.relative_to(BASE_DIR))
        for path in (log_path, state_path, FEEDBACK_PATH):
            if path.exists():
                archive.write(path, f"logs/{path.name}")


def timestamped_export_name(prefix: str, suffix: str) -> str:
    return f"{prefix}-{datetime.now():%Y%m%d-%H%M}.{suffix}"
