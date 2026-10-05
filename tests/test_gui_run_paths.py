import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from laya_gui import app, services


class GuiRunPathsTests(unittest.TestCase):
    def test_default_relative_absolute_and_empty_config(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(services, "DATA_DIR", Path(folder)):
            for config in ({}, {"logs_dir": None}, {"logs_dir": ""}, {"logs_dir": "  "}, {"logs_dir": []}):
                self.assertEqual(services.resolve_log_dir(config), Path(folder, "logs").resolve())
            self.assertEqual(services.resolve_log_dir({"logs_dir": "runs/Esia"}), Path(folder, "runs/Esia").resolve())
            absolute = Path(folder, "active run").resolve()
            self.assertEqual(services.resolve_log_dir({"logs_dir": str(absolute)}), absolute)
            self.assertFalse(absolute.exists())  # Resolution is read-only.

    def center(self, folder):
        center = SimpleNamespace(config_data={"logs_dir": str(Path(folder, "active"))},
            preferences={}, language="en", footer=mock.Mock(), refresh_views=mock.Mock())
        app.ControlCenter._configure_run_paths(center)
        return center

    def test_gui_initialization_and_all_runtime_paths_share_configured_run(self):
        with tempfile.TemporaryDirectory() as folder:
            center = self.center(folder)
            for field, filename in (("log_path", "decisions.jsonl"), ("state_path", "colony-state.json"),
                ("pid_path", "director.pid"), ("runtime_status_path", "runtime-status.json"),
                ("observer_pid_path", "observer.pid"), ("observer_status_path", "observer-status.json"),
                ("observer_log_path", "observer.jsonl")):
                self.assertEqual(getattr(center, field), center.log_dir / filename)

    def test_auto_manual_observer_launch_health_stop_use_explicit_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            center = self.center(folder)
            with mock.patch.object(app, "read_director_health", return_value={"pid": 12, "state": "unresponsive"}) as health, \
                 mock.patch.object(app, "stop_director") as stop, mock.patch.object(app, "launch_observer") as launch, \
                 mock.patch.object(app.laya_preferences, "save_preferences"):
                for method in (app.ControlCenter._auto_start_observer, app.ControlCenter.start_stream_observer):
                    method(center)
                    health.assert_called_with(center.observer_pid_path, center.observer_status_path)
                    stop.assert_called_with(center.observer_pid_path, center.observer_status_path)
                    launch.assert_called_with(center.config_data, pid_path=center.observer_pid_path,
                        status_path=center.observer_status_path, log_path=center.observer_log_path)
                app.ControlCenter.stop_stream_observer(center)
                stop.assert_called_with(center.observer_pid_path, center.observer_status_path)
            with mock.patch.object(app, "read_director_health", return_value={"state": "running"}), \
                 mock.patch.object(app, "launch_observer") as launch:
                app.ControlCenter._auto_start_observer(center)
                launch.assert_not_called()

    def test_director_start_and_status_read_use_same_run_without_rendering(self):
        with tempfile.TemporaryDirectory() as folder:
            center = self.center(folder)
            with mock.patch.object(app, "read_director_health", return_value={"state": "stopped"}) as health, \
                 mock.patch.object(app, "start_director", return_value=123) as launch:
                app.ControlCenter.start_laya(center)
                health.assert_called_once_with(center.pid_path, center.runtime_status_path)
                launch.assert_called_once_with(center.config_data, center.log_path, center.state_path,
                                               center.pid_path, center.runtime_status_path)
            center.log_dir.mkdir()
            center.observer_status_path.write_text('{"shot":"medical","target":"Red","remaining":3}', encoding="utf-8")
            for name in ("laya_chip", "observer_chip", "observer_status_label", "observer_focus_label", "sidebar_status"):
                setattr(center, name, mock.Mock())
            center.game_online = True
            center._load_map_state = mock.Mock(return_value={})
            center._refresh_doctrine = mock.Mock()
            center._refresh_history = mock.Mock()
            with mock.patch.object(app, "read_director_health", side_effect=[{"state":"stopped"}, {"state":"running"}]) as health:
                app.ControlCenter.refresh_views(center)
                self.assertEqual(health.call_args_list, [mock.call(center.pid_path, center.runtime_status_path),
                    mock.call(center.observer_pid_path, center.observer_status_path)])
                self.assertIn("Red", center.observer_focus_label.configure.call_args.kwargs["text"])


if __name__ == "__main__":
    unittest.main()
