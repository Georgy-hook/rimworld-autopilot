"""Copy only the files needed by an installed RimWorld Autopilot."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


RUNTIME_FILES = (
    "RimWorld-Autopilot.exe",
    "colony_architect.py",
    "colony_combat.py",
    "colony_director.py",
    "colony_events.py",
    "colony_professions.py",
    "colony_strategy.py",
    "laya_decisions.py",
    "laya_preferences.py",
    "rimworld_laya.py",
    "stream_observer.py",
    "requirements.txt",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
)

MOD_FILES = (
    "LICENSE",
    "1.6/Assemblies/RIMAPI.dll",
)
MOD_FOLDERS = ("About", "Languages", "Libraries")


def copy_install_payload(source: Path, destination: Path) -> None:
    """Install the GUI, Python director, dependencies list, and playable mod.

    Source releases keep documentation and build sources; the installed app does
    not need them. Existing user configuration and virtual environments in the
    destination are deliberately left untouched.
    """
    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        return
    for name in RUNTIME_FILES:
        candidate = source / name
        if name == "RimWorld-Autopilot.exe" and not candidate.is_file():
            candidate = source / "dist" / name
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
    mod = source / "vendor" / "RIMAPI"
    for name in MOD_FILES:
        if not (mod / name).is_file():
            raise FileNotFoundError(mod / name)
    for name in MOD_FOLDERS:
        if not (mod / name).is_dir():
            raise FileNotFoundError(mod / name)

    destination.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_FILES:
        candidate = source / name
        if name == "RimWorld-Autopilot.exe" and not candidate.is_file():
            candidate = source / "dist" / name
        shutil.copy2(candidate, destination / name)
    destination_mod = destination / "vendor" / "RIMAPI"
    for name in MOD_FILES:
        target = destination_mod / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mod / name, target)
    for name in MOD_FOLDERS:
        shutil.copytree(mod / name, destination_mod / name, dirs_exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    copy_install_payload(arguments.source, arguments.destination)
