from __future__ import annotations

import tempfile
import unittest
import ast
from pathlib import Path

from install_payload import MOD_FILES, MOD_FOLDERS, RUNTIME_FILES, copy_install_payload


class InstallPayloadTests(unittest.TestCase):
    def test_live_capabilities_are_part_of_installed_runtime(self):
        self.assertIn("colony_capabilities.py", RUNTIME_FILES)
        self.assertIn("colony_medical_recovery.py", RUNTIME_FILES)

    def test_installed_modules_include_their_local_import_dependencies(self):
        root = Path(__file__).resolve().parents[1]
        installed = set(RUNTIME_FILES)
        for name in RUNTIME_FILES:
            if not name.endswith('.py'):
                continue
            tree = ast.parse((root / name).read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                modules = ([a.name.split('.')[0] for a in node.names] if isinstance(node, ast.Import)
                           else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
                for module in modules:
                    if (root / (module + '.py')).is_file():
                        self.assertIn(module + '.py', installed, f'{name} imports unpackaged {module}')

    def test_only_runtime_files_are_installed_without_overwriting_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "installed"
            source.mkdir()
            destination.mkdir()
            for name in RUNTIME_FILES:
                (source / name).write_text(name, encoding="utf-8")
            mod = source / "vendor" / "RIMAPI"
            for name in MOD_FILES:
                item = mod / name
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_text(name, encoding="utf-8")
            for name in MOD_FOLDERS:
                folder = mod / name
                folder.mkdir(parents=True)
                (folder / "example.xml").write_text(name, encoding="utf-8")
            for name in ("README.md", "RELEASE_NOTES.md", "PLAYTEST_REPORT.md"):
                (source / name).write_text("source only", encoding="utf-8")
            for name in ("assets", "docs", "laya_gui", "tools", "vendor/RIMAPI/Source"):
                item = source / name
                item.mkdir(parents=True)
                (item / "unneeded.txt").write_text("source only", encoding="utf-8")
            config = destination / "rimworld-autopilot.json"
            config.write_text("user configuration", encoding="utf-8")

            copy_install_payload(source, destination)

            self.assertEqual(config.read_text(encoding="utf-8"), "user configuration")
            for name in RUNTIME_FILES:
                self.assertTrue((destination / name).is_file(), name)
            for name in MOD_FILES:
                self.assertTrue((destination / "vendor" / "RIMAPI" / name).is_file(), name)
            for name in MOD_FOLDERS:
                self.assertTrue((destination / "vendor" / "RIMAPI" / name / "example.xml").is_file(), name)
            for name in ("README.md", "RELEASE_NOTES.md", "PLAYTEST_REPORT.md", "assets", "docs", "laya_gui", "tools", "vendor/RIMAPI/Source"):
                self.assertFalse((destination / name).exists(), name)

    def test_build_executable_can_come_from_dist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "installed"
            source.mkdir()
            for name in RUNTIME_FILES:
                if name == "RimWorld-Autopilot.exe":
                    continue
                (source / name).write_text(name, encoding="utf-8")
            build_executable = source / "dist" / "RimWorld-Autopilot.exe"
            build_executable.parent.mkdir()
            build_executable.write_text("built", encoding="utf-8")
            mod = source / "vendor" / "RIMAPI"
            for name in MOD_FILES:
                item = mod / name
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_text(name, encoding="utf-8")
            for name in MOD_FOLDERS:
                (mod / name).mkdir(parents=True)

            copy_install_payload(source, destination)

            self.assertEqual((destination / "RimWorld-Autopilot.exe").read_text(encoding="utf-8"), "built")


if __name__ == "__main__":
    unittest.main()
