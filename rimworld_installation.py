"""Locate a user's RimWorld installation and install its local mod safely."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4


GAME_EXE = "RimWorldWin64.exe"
STEAM_APP_ID = "294100"


def normalize_game_path(value: str | os.PathLike[str]) -> Path:
    text = os.fspath(value).strip().strip('"')
    if not text:
        raise ValueError("Choose the RimWorld folder.")
    path = Path(os.path.expandvars(text)).expanduser().resolve()
    return path.parent if path.name.casefold() == GAME_EXE.casefold() else path


def validate_game_path(value: str | os.PathLike[str]) -> Path:
    path = normalize_game_path(value)
    if not (path / GAME_EXE).is_file() or not (path / "Data" / "Core").is_dir():
        raise ValueError(f"RimWorldWin64.exe and Data/Core were not found in: {path}")
    return path


def _read_keyvalues(path: Path) -> dict:
    """Read Steam's quoted KeyValues, including escaped Windows backslashes."""
    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return {}
    tokens = []
    for token in re.finditer(r'//[^\n]*|"((?:\\.|[^"\\])*)"|([{}])', source):
        if token.group(1) is not None:
            tokens.append(re.sub(r'\\([\\"])', r'\1', token.group(1)))
        elif token.group(2):
            tokens.append(token.group(2))
    root: dict = {}
    stack = [root]
    index = 0
    while index < len(tokens):
        key = tokens[index]
        if key == "}":
            if len(stack) == 1:
                return {}
            stack.pop()
            index += 1
            continue
        if key == "{" or index + 1 >= len(tokens) or tokens[index + 1] == "}":
            return {}
        value = tokens[index + 1]
        if value == "{":
            child: dict = {}
            stack[-1][key.casefold()] = child
            stack.append(child)
        else:
            stack[-1][key.casefold()] = value
        index += 2
    return root if len(stack) == 1 else {}


def _registry_paths() -> tuple[list[Path], list[Path]]:
    steam, games = [], []
    try:
        import winreg
    except ImportError:
        return steam, games
    locations = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", ("SteamPath", "InstallPath"), steam),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", ("InstallPath", "SteamPath"), steam),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 294100", ("InstallLocation",), games),
    )
    for hive, key, names, destination in locations:
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as handle:
                    for name in names:
                        try:
                            value = winreg.QueryValueEx(handle, name)[0]
                            if isinstance(value, str) and value.strip():
                                destination.append(Path(os.path.expandvars(value)))
                        except OSError:
                            pass
            except OSError:
                pass
    return steam, games


def discover_game_paths(saved_path: str = "", *, steam_roots=None, game_roots=None) -> list[Path]:
    """Check known metadata only; never crawl drives or accept missing games."""
    registry_steam, registry_games = _registry_paths() if steam_roots is None or game_roots is None else ([], [])
    roots = list(registry_steam if steam_roots is None else steam_roots)
    roots += [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam",
              Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam"]
    candidates = ([saved_path] if saved_path else []) + list(registry_games if game_roots is None else game_roots)
    libraries = []
    for root in roots:
        libraries.append(Path(root))
        for relative in ("steamapps/libraryfolders.vdf", "config/libraryfolders.vdf"):
            folders = _read_keyvalues(Path(root) / relative).get("libraryfolders", {})
            if not isinstance(folders, dict):
                continue
            for key, entry in folders.items():
                if key.isdecimal():
                    value = entry.get("path") if isinstance(entry, dict) else entry
                    if isinstance(value, str) and value.strip():
                        libraries.append(Path(value))
    for library in libraries:
        common = library / "steamapps" / "common"
        manifest = _read_keyvalues(library / "steamapps" / f"appmanifest_{STEAM_APP_ID}.acf").get("appstate", {})
        if isinstance(manifest, dict) and manifest.get("appid") == STEAM_APP_ID:
            folder = manifest.get("installdir")
            if isinstance(folder, str) and folder and Path(folder).name == folder and folder not in {".", ".."}:
                candidates.append(common / folder)
        candidates.append(common / "RimWorld")
    found, seen = [], set()
    for candidate in candidates:
        try:
            path = validate_game_path(candidate)
        except (ValueError, OSError, RuntimeError):
            continue
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            found.append(path)
    return found


def validate_application_path(destination: Path, source: Path, game: Path) -> Path:
    destination, source, game = destination.resolve(), source.resolve(), game.resolve()
    if (destination == game or destination in game.parents or game in destination.parents
            or destination in source.parents or source in destination.parents):
        raise ValueError("Choose a separate application folder, outside RimWorld and the source package.")
    return destination


def prepare_mod_directory(game: Path) -> Path:
    game = validate_game_path(game)
    mods = (game / "Mods").resolve()
    mods.mkdir(parents=True, exist_ok=True)
    # Fail before downloading packages/model when this location is not writable.
    with tempfile.TemporaryFile(dir=mods):
        pass
    target = mods / "RIMAPI"
    if target.resolve() != target or target.is_symlink():
        raise ValueError("The RIMAPI target points outside the selected Mods folder.")
    return mods


def install_mod(source: Path, game: Path, backup_root: Path) -> Path:
    """Stage first; keep old mods outside Mods to avoid duplicate package IDs."""
    source = source.resolve()
    for relative in ("About/About.xml", "1.6/Assemblies/RIMAPI.dll"):
        if not (source / relative).is_file():
            raise FileNotFoundError(source / relative)
    mods = prepare_mod_directory(game)
    target = mods / "RIMAPI"
    stage = mods / f".RIMAPI-install-{uuid4().hex}"
    backup_root = backup_root.resolve()
    if backup_root == mods or mods in backup_root.parents:
        raise ValueError("Mod backups must stay outside RimWorld's Mods folder.")
    backup = backup_root / f"RIMAPI-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    moved = False
    try:
        shutil.copytree(source, stage)
        if target.exists():
            backup_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(backup))
            moved = True
        stage.replace(target)
    except Exception:
        if moved and not target.exists():
            shutil.move(str(backup), str(target))
        raise
    finally:
        if stage.exists() and stage.resolve().parent == mods:
            shutil.rmtree(stage)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", default="")
    parser.add_argument("--install-mod", type=Path)
    parser.add_argument("--game", type=Path)
    parser.add_argument("--backup-root", type=Path)
    args = parser.parse_args()
    try:
        if args.install_mod:
            if not args.game or not args.backup_root:
                parser.error("--install-mod requires --game and --backup-root")
            print(install_mod(args.install_mod, args.game, args.backup_root))
            raise SystemExit(0)
        paths = [validate_game_path(args.validate)] if args.validate else discover_game_paths()
        if not paths:
            raise ValueError("RimWorld was not found. Pass -RimWorldPath with its actual folder.")
        print(paths[0])
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
