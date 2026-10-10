# GUI installation paths — 10 October 2026

The working `0.0.8` candidate targets `developing` through PR #5. It is not the
published `0.0.7` installer. No RimWorld process, save, map, speed, mod activation
or current installed payload is changed by this audit.

## What the path means

Setup accepts a user-selected absolute RimWorld root, validates
`RimWorldWin64.exe` and `Data/Core`, and installs the ordinary bundled mod in
that root's `Mods/RIMAPI`. It stores `rimworld_path` in application configuration
and `%LOCALAPPDATA%/RimWorld Autopilot/rimworld-autopilot.json`. The control center
loads that configuration and shows the selected folder in Settings. Laya itself
connects to `api_url` on the running game; neither its prompt nor director startup
needs the game filesystem path.

Before this change, manual custom folders already worked, but automatic discovery
only checked two Program Files Steam locations. The selected path had no visible
Settings control. The post-install helper was temporary and deleted, leaving no
repeatable GUI path to configure a moved game.

## Current contract

- Prefer a still-valid saved selection, then registered Steam game paths and
  Windows Steam roots in both registry views.
- Read `steamapps/libraryfolders.vdf` and legacy `config/libraryfolders.vdf`,
  including other library drives. Use `appmanifest_294100.acf`'s actual local
  `installdir`, then the conventional `RimWorld` child; validate each candidate.
- Paths are normalized, duplicate candidates removed, and stale/malformed
  metadata ignored. No recursive drive scan. With no valid match, the field is
  empty and Browse remains available for Steam or standalone installations.
- Accept quotes, environment variables, spaces, Unicode and a pasted game EXE.
  Saves, Mods and incomplete roots fail validation.
- Keep the application outside the game/source trees. Check Mods write access
  before downloading dependencies or model files. Reject escaping RIMAPI links.
- Stage the new mod before moving the old mod to application `mod-backups`,
  outside the game's mod scan. Restore the old copy if final replacement fails.
- Persist the canonical game path and preserve unrelated run settings, API URL
  and interval. Both generated configurations use UTF-8 and atomic replacement.
- Package the setup executable permanently. Settings launches it with the app
  directory and saved game as separate quoted arguments using Windows elevation.
  A stale game path is omitted to allow fresh discovery; the original GUI user's
  data directory is passed explicitly instead of inferring it from elevation.
  Existing director/observer services must first be stopped by the user.
- The source PowerShell installer uses the same discovery/validation/mod helper
  and writes the selected game path; `-RimWorldPath` supports explicit locations.
- Keep private playtest journals out of both the runtime payload and source ZIP.

## User flow

1. Install Autopilot into its own application folder.
2. Confirm the detected RimWorld folder or choose Browse. Select the root
   containing `RimWorldWin64.exe` and `Data/Core`.
3. Finish setup; enable Harmony followed by RIMAPI in RimWorld, restart the game,
   and load the intended colony before starting Laya.
4. If the game moves, stop Laya/observer, close RimWorld, and open the setup
   assistant from Settings. Select the new folder and complete setup there.

[Steam's official moving/installing guide](https://help.steampowered.com/en/faqs/view/4BD4-4528-6B2E-8327)
confirms games can live in different Steam libraries. Discovery uses locally
observed Steam metadata, not an assumed installation drive. Automatic discovery
for non-Steam stores is not promised; their installed game roots are accepted
manually. Enabling mods/restarting a game remains a player action.

## Verification scope

Behavioral tests create isolated directories with Unicode/spaces, modern/legacy
Steam metadata, custom manifest names, stale selections and incomplete installs.
They check actual selected-folder copies, old-mod preservation/recovery, unchanged
save bytes, UTF-8 config round trips, pre-download permission failure and GUI
argument forwarding. Pip/model calls and UAC launches are mocked there. Separate
GUI smoke/build and distribution checks are recorded privately; they do not
demonstrate a clean-machine dependency download or live RimWorld startup.

The final source passed **1349 Python tests**, including **11 installation
behavior tests**. The API audit found 313 routes with no missing/duplicate calls
and made no runtime contact. Both source GUIs passed Russian and English smoke
checks (four checks), and PyInstaller plus Inno Setup produced the two GUI EXEs,
full installer and source ZIP. The real packaged DLL and runtime files were
copied and verified in an isolated relocated application/game tree. Actual UAC
consent and a clean-machine Python/model download remain outside this test.
