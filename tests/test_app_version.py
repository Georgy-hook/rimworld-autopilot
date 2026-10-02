"""Verify version resource lookup in source and a frozen bundle."""
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch


class AppVersionTests(unittest.TestCase):
    def test_source_reads_the_packaged_version_resource(self):
        root = Path(__file__).resolve().parents[1]
        values = runpy.run_path(str(root / "app_version.py"))
        self.assertEqual(values["APP_VERSION"], (root / "VERSION").read_text().strip())

    def test_frozen_lookup_uses_bundle_not_working_directory(self):
        module = Path(__file__).resolve().parents[1] / "app_version.py"
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "VERSION").write_text("9.8.7\n", encoding="utf-8")
            with patch.object(sys, "_MEIPASS", folder, create=True):
                self.assertEqual(runpy.run_path(str(module))["APP_VERSION"], "9.8.7")


if __name__ == "__main__":
    unittest.main()
