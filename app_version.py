"""Product version shared by source and frozen desktop entry points."""
from pathlib import Path
import sys


RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_VERSION = (RESOURCE_ROOT / "VERSION").read_text(encoding="utf-8").strip()
