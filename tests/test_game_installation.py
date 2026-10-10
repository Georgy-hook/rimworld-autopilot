import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import rimworld_installation as installation
from laya_gui import app, services, setup_app


class GameInstallationTests(unittest.TestCase):
    def game(self, root):
        root.mkdir(parents=True)
        (root / installation.GAME_EXE).write_bytes(b"test executable")
        (root / "Data" / "Core").mkdir(parents=True)
        return root.resolve()

    def mod(self, root, text="new mod"):
        for name in ("About/About.xml", "1.6/Assemblies/RIMAPI.dll"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def discover(self, root, saved="", steam=(), games=()):
        with mock.patch.dict(os.environ, {"ProgramFiles": str(root / "unused"), "ProgramFiles(x86)": str(root / "unused32")}):
            return installation.discover_game_paths(saved, steam_roots=steam, game_roots=games)

    def test_custom_steam_root_second_library_manifest_and_cyrillic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            steam, library = root / "Другой Steam", root / "Библиотека игр"
            game = self.game(library / "steamapps" / "common" / "RimWorld custom")
            (steam / "steamapps").mkdir(parents=True)
            escaped = str(library).replace("\\", "\\\\")
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                f'"libraryfolders" {{ "1" {{ "path" "{escaped}" "apps" {{ "294100" "1234" }} }} }}', encoding="utf-8")
            (library / "steamapps" / "appmanifest_294100.acf").write_text(
                '"AppState" { "appid" "294100" "installdir" "RimWorld custom" }', encoding="utf-8")
            self.assertEqual(self.discover(root, steam=[steam]), [game])

    def test_legacy_libraries_saved_choice_first_and_missing_saved_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            steam, library = root / "Steam", root / "Games"
            found = self.game(library / "steamapps" / "common" / "RimWorld")
            saved = self.game(root / "RimWorld standalone")
            (steam / "config").mkdir(parents=True)
            escaped = str(library).replace("\\", "\\\\")
            (steam / "config" / "libraryfolders.vdf").write_text(
                f'// legacy format\n"LibraryFolders" {{ "1" "{escaped}" }}', encoding="utf-8")
            self.assertEqual(self.discover(root, str(saved), [steam]), [saved, found])
            self.assertEqual(self.discover(root, str(root / "removed"), [steam]), [found])
            self.assertEqual(self.discover(root, str(saved), [steam], [saved]), [saved, found])

    def test_malformed_or_traversing_metadata_does_not_guess_a_game(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            steam = root / "Steam"
            self.game(root / "outside")
            (steam / "steamapps").mkdir(parents=True)
            (steam / "steamapps" / "libraryfolders.vdf").write_text('"libraryfolders" { "1" {', encoding="utf-8")
            (steam / "steamapps" / "appmanifest_294100.acf").write_text(
                '"AppState" { "appid" "294100" "installdir" "../../../outside" }', encoding="utf-8")
            self.assertEqual(self.discover(root, steam=[steam]), [])

    def test_quoted_environment_and_executable_paths_and_incomplete_install(self):
        with tempfile.TemporaryDirectory() as folder:
            game = self.game(Path(folder) / "Мои игры")
            with mock.patch.dict(os.environ, {"TEST_GAME_FOLDER": str(game)}):
                self.assertEqual(installation.validate_game_path(' "%TEST_GAME_FOLDER%" '), game)
                self.assertEqual(installation.validate_game_path(str(game / installation.GAME_EXE)), game)
            for invalid in ("", str(game / "Mods"), str(game / "Data")):
                with self.assertRaises(ValueError):
                    installation.validate_game_path(invalid)
            (game / "Data" / "Core").rmdir()
            with self.assertRaises(ValueError):
                installation.validate_game_path(game)

    def test_install_into_selected_game_and_backup_outside_mods(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = self.game(root / "Игры" / "RimWorld")
            source = self.mod(root / "Laya" / "vendor" / "RIMAPI")
            target = self.mod(game / "Mods" / "RIMAPI", "old mod")
            save = game / "colony.rws"
            save.write_bytes(b"untouched save")
            backup = root / "Laya" / "mod-backups"
            self.assertEqual(installation.install_mod(source, game, backup), target)
            self.assertEqual((target / "About" / "About.xml").read_text(), "new mod")
            self.assertEqual(len(list(backup.iterdir())), 1)
            self.assertEqual(next(backup.iterdir()).joinpath("About/About.xml").read_text(), "old mod")
            self.assertEqual([p.name for p in (game / "Mods").iterdir()], ["RIMAPI"])
            self.assertEqual(save.read_bytes(), b"untouched save")

    def test_failed_replacement_restores_old_mod_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = self.game(root / "game")
            source = self.mod(root / "source")
            target = self.mod(game / "Mods" / "RIMAPI", "old mod")
            with mock.patch.object(Path, "replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    installation.install_mod(source, game, root / "backup")
            self.assertEqual((target / "About/About.xml").read_text(), "old mod")
            self.assertEqual([p.name for p in (game / "Mods").iterdir()], ["RIMAPI"])

    def test_overlapping_application_folders_rejected_and_reconfigure_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, game, destination = root / "source", root / "game", root / "app"
            for invalid in (root, game, game / "Laya", source / "installed"):
                with self.assertRaises(ValueError):
                    installation.validate_application_path(invalid, source, game)
            self.assertEqual(installation.validate_application_path(destination, source, game), destination)
            self.assertEqual(installation.validate_application_path(source, source, game), source)

    def test_gui_worker_persists_custom_game_and_preserves_run_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = self.game(root / "Другой диск" / "RimWorld")
            application = root / "Laya App"
            self.mod(application / "vendor" / "RIMAPI")
            (application / "requirements.txt").write_text("")
            (application / "rimworld-autopilot.json").write_text(json.dumps({"logs_dir": "run keep", "api_url": "http://localhost:9000", "interval": 13}))
            events = []
            window = SimpleNamespace(t=lambda key: setup_app.SETUP_TEXT["en"][key],
                _emit=lambda kind, value: events.append((kind, value)), _run=mock.Mock(), _create_shortcut=mock.Mock())
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "Локальные данные")}), \
                    mock.patch.object(services, "CONFIG_PATH", root / "no config"):
                setup_app.SetupWindow._install(window, Path("fake-python.exe"), game, application, "cpu", False)
            self.assertEqual(events[-1][0], "done", events)
            config = json.loads((application / "rimworld-autopilot.json").read_text(encoding="utf-8"))
            self.assertEqual(config["rimworld_path"], str(game))
            self.assertEqual(config["logs_dir"], "run keep")
            self.assertEqual(config["api_url"], "http://localhost:9000")
            self.assertEqual(config["interval"], 13)
            user_config = root / "Локальные данные" / "RimWorld Autopilot" / "rimworld-autopilot.json"
            self.assertEqual(json.loads(user_config.read_text(encoding="utf-8")), config)
            self.assertTrue((game / "Mods/RIMAPI/1.6/Assemblies/RIMAPI.dll").is_file())
            # Elevation may use another account: the forwarded original user's
            # config must remain the source and destination for reconfiguration.
            original_data = root / "Original GUI user"
            original_data.mkdir()
            original_config = dict(config, logs_dir="original user's run")
            (original_data / "rimworld-autopilot.json").write_text(json.dumps(original_config), encoding="utf-8")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "admin account")}), \
                    mock.patch.object(services, "CONFIG_PATH", root / "admin account/config.json"):
                setup_app.SetupWindow._install(window, Path("fake-python.exe"), game, application, "cpu", False, original_data)
            self.assertEqual(events[-1][0], "done", events)
            self.assertEqual(json.loads((original_data / "rimworld-autopilot.json").read_text())["logs_dir"], "original user's run")
            self.assertFalse((root / "admin account/RimWorld Autopilot/rimworld-autopilot.json").exists())

    def test_bad_or_unwritable_game_fails_before_dependencies_are_downloaded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = self.game(root / "game")
            window = SimpleNamespace(t=lambda key: key, _emit=mock.Mock(), _run=mock.Mock())
            with mock.patch.object(setup_app, "prepare_mod_directory", side_effect=PermissionError("read-only")):
                setup_app.SetupWindow._install(window, Path("fake.exe"), game, root / "app", "cpu", False)
            window._run.assert_not_called()
            self.assertEqual(window._emit.call_args.args[0], "error")

    def test_main_gui_opens_persistent_assistant_with_quoted_selected_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "Программа с пробелами"
            root.mkdir()
            helper = root / "RimWorld-Autopilot-Setup.exe"
            helper.touch()
            game = str(self.game(Path(folder) / "Игры" / "RimWorld"))
            user_data = root / "original user data"
            center = SimpleNamespace(config_data={"rimworld_path": game}, language="ru",
                pid_path=root / "director.pid", runtime_status_path=root / "director.json",
                observer_pid_path=root / "observer.pid", observer_status_path=root / "observer.json")
            with mock.patch.object(app, "BASE_DIR", root), mock.patch.object(app, "DATA_DIR", user_data), \
                    mock.patch.object(app, "read_director_health", return_value={"state": "stopped"}), \
                    mock.patch.object(app.os, "startfile", create=True) as launch:
                app.ControlCenter.open_setup(center)
            launch.assert_called_once_with(str(helper), "runas",
                subprocess.list2cmdline(["--installed-dir", str(root), "--user-data-dir", str(user_data), "--rimworld-dir", game]), str(root))
            center.config_data["rimworld_path"] = str(root / "removed game")
            with mock.patch.object(app, "BASE_DIR", root), mock.patch.object(app, "DATA_DIR", user_data), \
                    mock.patch.object(app, "read_director_health", return_value={"state": "stopped"}), \
                    mock.patch.object(app.os, "startfile", create=True) as launch:
                app.ControlCenter.open_setup(center)
            self.assertNotIn("--rimworld-dir", launch.call_args.args[2])
            with mock.patch.object(app, "read_director_health", return_value={"state": "running", "pid": 33}), \
                    mock.patch.object(app.messagebox, "showinfo") as notice, mock.patch.object(app.os, "startfile", create=True) as launch:
                app.ControlCenter.open_setup(center)
            launch.assert_not_called()
            notice.assert_called_once()

    def test_main_gui_reads_new_saved_folder_without_changing_run_paths(self):
        center = SimpleNamespace(config_data={"logs_dir": "active run"}, language="en", game_folder_var=mock.Mock())
        with mock.patch.object(app, "load_config", return_value={"rimworld_path": "D:/Games/RimWorld"}):
            app.ControlCenter._refresh_game_folder(center)
        self.assertEqual(center.config_data["logs_dir"], "active run")
        self.assertEqual(center.config_data["rimworld_path"], "D:/Games/RimWorld")
        center.game_folder_var.set.assert_called_with("D:/Games/RimWorld")


if __name__ == "__main__":
    unittest.main()
