# Stream Observer

Open **Stream / Эфир** in RimWorld Autopilot and select **Enable Observer / Включить наблюдателя** after loading a colony. The status and current shot appear on that page. **Disable / Выключить** stops the camera process. The observer is independent of Laya's colony director: it never assigns jobs, drafts colonists, or changes Laya's choices. It can run while the GUI is closed; reopening the GUI shows the same process. If enabled in preferences, reopening the GUI also restarts it after a prior exit.

The shot order is based on real elapsed time:

1. A colonist death gets one 20-second close-up and an English caption with the cause reported by RIMAPI. If the game does not report a cause, the caption says so or names the last known condition. After that, the camera returns to a living colonist. A departure from the map alone is not treated as death.
2. Active fights take priority. The camera starts close, moves to a medium view after 10 seconds, and rotates among multiple fighters every 30 seconds.
3. New raiders receive a montage of up to 30 seconds, divided between the visible enemies, before the camera returns to the colony. Active fighting interrupts this montage.
4. Injured or sick colonists get occasional priority shots, with a cooldown so one patient cannot monopolize the broadcast.
5. During quieter work, the camera rotates between colonists every 45 seconds: 10 seconds close, then a wide view. Every 10 minutes it takes a short five-stop tour of the map at wide zoom.

While this mode is on, the observer permits game time only with a fresh heartbeat from a live, ready director. Otherwise it keeps the colony paused. Normal target speed is 3×; home fire, critical bleeding, dangerous immune disease, serious thermal illness, starvation of a patient or attack on a downed colonist reduce it to 1×. Shot lengths and camera rotations use real seconds. Turn the mode off to retain a manual pause. Native final defeat/victory stops pacing; ordinary unavailable API state is not proof of defeat. This mode does not start an OBS or Twitch broadcast by itself.

Hourly verification also assesses screenshots, placement and actual outputs, animal losses, raid outcomes, population, income and ending progress. See [the colony verification protocol](COLONY_VERIFICATION.md). Healthy processes or accepted orders are not proof of a successful colony.

The script can also run without the GUI, using the configured Python environment:

```powershell
.\.venv\Scripts\python.exe stream_observer.py `
  --pid-file logs\observer.pid `
  --status logs\observer-status.json `
  --log logs\observer.jsonl
```

The local RIMAPI address defaults to `http://localhost:8765`; use `--api-url` if you configured another loopback address. Only run one observer process against a game at a time. The GUI owns its observer process and writes status/log files alongside the director logs; installed builds place them under `%LOCALAPPDATA%\RimWorld Autopilot\logs`.
