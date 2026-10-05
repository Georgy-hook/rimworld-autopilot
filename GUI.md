# GUI architecture

The 0.0.6 RimWorld Autopilot control center is intentionally separate from the colony controller. `autopilot_control.py` is the public launcher (`laya_control.py` remains compatible); the implementation lives in `laya_gui/`:

- `app.py` composes the six user pages and animated navigation shell;
- `theme.py` owns semantic dark-theme tokens, typography, shadows, focus-visible buttons, rounded scrollbars, scrollable pages and reusable cards;
- `i18n.py` owns Russian/English copy and friendly names for internal decisions;
- `services.py` owns process control, local API checks and export operations;
- `setup_app.py` is the graphical installation assistant;
- `laya_preferences.py` is shared with the autonomous director and validates player guidance.

## Pages

1. **Overview** — Laya/RimWorld status, start/stop/pause controls, current course, latest decision and active content.
2. **Strategy** — the selected doctrine and every direction available in the loaded Core/DLC set.
3. **Priorities** — eight 0–100 preference weights, a free-form personal note and explicit peaceful/safety boundaries.
4. **History** — friendly explanations by default; exact JSON is available only after enabling technical mode.
5. **Stream** — starts/stops a separate camera observer and shows its current shot and target. The observer persists after closing the GUI; the enabled preference restores it when the GUI opens again.
6. **Settings** — Russian/English switch with real flag assets, diagnostic logging, compact/hidden in-game HUD controls, standard Windows uninstall and exports.

The interface uses native Tk widgets and the standard library. It therefore adds no UI framework dependency to the already large local-model installation. Rounded cards, animated buttons and orbit particles are drawn locally. The 1240×800 minimum size protects the decision-boundary controls, while long pages remain vertically scrollable. History and page scrollbars use a compact rounded track with keyboard support instead of legacy arrow controls. Buttons expose keyboard focus and Enter/Space activation.

The emblem, panoramic colony art, setup illustrations and five navigation illustrations are original project-local PNGs generated with the built-in ImageGen tool; prompts are preserved in `assets/gui/README.md`. Russian and United Kingdom flags are local Twemoji PNG assets rather than font emoji, so their appearance does not depend on the user's system font or an online renderer. Missing packaged artwork is recorded in `logs/ui-assets.log` instead of silently substituting a network placeholder.

## Preference contract

`rimworld-autopilot.json` accepts an optional `logs_dir` for the active run.
An absolute path selects that folder; a relative path is resolved under the
writable data directory. The default remains `logs`. History, colony memory,
director and observer PID/status files all use this same folder. Close the
panel and stop the old run before changing it, then reopen the panel. This
keeps each run's evidence separate without replacing filesystem junctions.

The GUI writes `autopilot-preferences.json`. Installed builds keep writable settings and logs in `%LOCALAPPDATA%\RimWorld Autopilot`, while program files remain under Program Files. The file is local runtime state and is excluded from Git. An existing `laya-preferences.json` is read as a compatibility migration. The development planner, combat planner, incident director, downed-raider policy and Ancient Danger decisions read the same validated structure.

Weights guide ordering and model context. They cannot override emergency gates, missing research/resources, invalid targets or API safety checks. “Do not begin unprovoked attacks” additionally removes settlement raids from the feasible candidate set.

Normal logging keeps the visible compact model context, compared options, decisions and outcomes. Technical logging additionally records the complete development snapshot/details; combat logging keeps full snapshots only in technical mode. Laya does not emit a textual chain of thought.

On the History page, **Rate decision** records your corrected choice and an optional explanation in a local feedback file. This creates labelled examples for later training; it does not retrain or change the running model. A full diagnostic export includes the feedback file.

The director writes a separate UTC heartbeat with its PID and current state. The GUI reports loading, waiting for a colony, running, decision errors and an unresponsive process independently; an old but still-live PID can no longer masquerade as a healthy autopilot. The HUD preference is read on every publication, so hiding it takes effect without stopping Laya. Compact mode renders a smaller RimWorld panel with up to five thin yellow bars. High-contrast labels and percentages sit above each bar. The widths show relative model weights, not the likelihood of a successful game outcome; these weights have not been calibrated on RimWorld data.

The stream observer uses its own PID, heartbeat and log, and runs without loading the Laya model. It follows pawns, moves and zooms the camera, shows an English death caption, resumes pauses and retries 3× game speed after raid slowdowns. Camera shots remain timed in real seconds. Death captions temporarily take precedence over Laya's in-game overlay. See [Stream Observer](docs/STREAM_OBSERVER.md) for the shot schedule and operational limitations.

All calls into the Laya decision model pass through one guard. Questions with exactly one feasible answer are accepted deterministically and recorded with probability 1.0 without invoking the model; questions with no feasible answer are rejected as planner errors. Laya therefore receives only genuine decisions with at least two alternatives.

## Installer and uninstaller

`installer/RimWorld-Autopilot.iss` produces the `RimWorld-Autopilot-0.0.6-Setup.exe` candidate. It uses Inno Setup's modern dynamic Windows 11 style, follows the system light/dark preference, displays project-local portrait artwork, requests administrator rights for the Program Files destination and registers the normal Windows uninstaller. It:

1. chooses the Program Files destination and optional desktop shortcut;
2. copies the application, bilingual UI and complete local artwork set;
3. creates Start-menu launch and uninstall entries;
4. extracts `RimWorld-Autopilot-Setup.exe` only into Inno Setup's temporary directory;
5. optionally runs that friendly assistant to locate Python 3.10–3.12 and a real RimWorld folder;
6. creates `.venv`, installs `requirements.txt`, downloads the root Laya model, backs up/replaces `Mods/RIMAPI` and writes local configuration;
7. deletes the temporary assistant as setup exits.

The installer does not request an API key, start RimWorld, alter saves or enable mods without the player. `unins000.exe` is registered in Windows Installed apps and removes files installed by Setup and its shortcuts. Writable LocalAppData and the game mod are preserved deliberately to avoid destructive surprise. The assistant also generates `.venv` and `rimworld-autopilot.json` in the selected application directory after Setup has registered its file list; the uninstaller does not track these, so they may remain and should be reviewed before manual removal.

`Build-GUI.ps1` reproduces the two internal unsigned Windows binaries, assembles `dist/rimworld-autopilot-0.0.6.zip`, converts the ImageGen emblem into the multi-resolution Windows icon and compiles the standard installer. Build-only dependencies are isolated in `.build-venv` and declared in `requirements-build.txt`; Inno Setup 6.7+ is the only external build prerequisite.
