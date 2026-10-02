from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from install_payload import copy_install_payload
from app_version import APP_VERSION
from .services import BASE_DIR, RESOURCE_DIR
from .theme import COLORS, FONTS, FancyButton, ShadowCard, configure_styles, render_photo


PRODUCT_NAME = "RimWorld Autopilot"
DEFAULT_INSTALL_DIR = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / PRODUCT_NAME


def _default_rimworld() -> Path:
    candidates = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam/steamapps/common/RimWorld",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam/steamapps/common/RimWorld",
    )
    return next((path for path in candidates if (path / "RimWorldWin64.exe").exists()), candidates[0])


def _source_root() -> Path:
    for candidate in (BASE_DIR, BASE_DIR.parent):
        if (candidate / "requirements.txt").exists() and (candidate / "vendor" / "RIMAPI").exists():
            return candidate
    return BASE_DIR


def _argument_path(name: str, fallback: Path) -> Path:
    try:
        index = sys.argv.index(name)
        return Path(sys.argv[index + 1]).expanduser().resolve()
    except (ValueError, IndexError, OSError):
        return fallback


DEFAULT_RIMWORLD = _default_rimworld()

SETUP_TEXT = {
    "ru": {
        "title": "Установка RimWorld Autopilot", "subtitle": "Красивый и понятный запуск локальной Laya — без командной строки.",
        "install_dir": "Куда установить приложение", "game": "Где установлен RimWorld", "browse": "Выбрать…",
        "device": "Как запускать модель", "auto": "Автоматически", "cuda": "Видеокарта NVIDIA", "cpu": "Процессор",
        "shortcut": "Добавить ярлык на рабочий стол", "install": "Установить Autopilot", "working": "Установка…",
        "ready": "Всё готово. Настройки можно изменить позже.",
        "python_missing": "Python 3.10–3.12 не найден. Открыть страницу загрузки Python?",
        "done": "RimWorld Autopilot установлен. Включите Harmony и RIMAPI — RimWorld Autopilot в списке модов, перезапустите игру и откройте приложение с рабочего стола.",
        "invalid": "В выбранной папке не найден RimWorldWin64.exe.", "invalid_install": "Выберите отдельную папку установки.",
        "error": "Не удалось завершить установку", "step_copy": "Размещаю приложение и иллюстрации…",
        "step_python": "Создаю отдельное окружение Python…", "step_packages": "Устанавливаю необходимые пакеты…",
        "step_model": "Загружаю Laya для первого запуска… Это может занять несколько минут.",
        "model_failed": "Не удалось загрузить Laya. Проверьте интернет и свободное место, затем повторите установку.",
        "step_mod": "Подключаю игровой мод…", "step_config": "Сохраняю настройки и создаю ярлык…",
        "privacy": "Модель работает локально. Установщик не просит ключ API и не отправляет сохранения в интернет.",
        "art_caption": "Локальный ИИ-пилот\nдля живой колонии",
    },
    "en": {
        "title": "Install RimWorld Autopilot", "subtitle": "A friendly local Laya setup with no command line required.",
        "install_dir": "Application folder", "game": "RimWorld folder", "browse": "Browse…",
        "device": "Run the model using", "auto": "Automatic", "cuda": "NVIDIA GPU", "cpu": "CPU",
        "shortcut": "Add a desktop shortcut", "install": "Install Autopilot", "working": "Installing…",
        "ready": "Everything is ready. You can change these settings later.",
        "python_missing": "Python 3.10–3.12 was not found. Open the Python download page?",
        "done": "RimWorld Autopilot is installed. Enable Harmony and RIMAPI — RimWorld Autopilot in RimWorld's mod list, restart the game, then open the desktop shortcut.",
        "invalid": "RimWorldWin64.exe was not found in the selected folder.", "invalid_install": "Choose a separate installation folder.",
        "error": "Setup could not finish", "step_copy": "Installing the application and artwork…",
        "step_python": "Creating an isolated Python environment…", "step_packages": "Installing the required packages…",
        "step_model": "Downloading Laya for first launch… This may take several minutes.",
        "model_failed": "Could not download Laya. Check your Internet connection and free disk space, then retry setup.",
        "step_mod": "Connecting the game mod…", "step_config": "Saving settings and creating the shortcut…",
        "privacy": "The model runs locally. Setup does not ask for an API key or upload save files.",
        "art_caption": "A local AI autopilot\nfor a living colony",
    },
}


class SetupWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        if os.environ.get("LAYA_GUI_SMOKE_TEST") == "1":
            self.withdraw()
        self.language = "ru"
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.title(f"{PRODUCT_NAME} {APP_VERSION} — Setup")
        self.geometry("980x700")
        self.resizable(False, False)
        self.configure(bg=COLORS["window"])
        configure_styles(self)
        self.install_var = tk.StringVar(value=str(_argument_path("--installed-dir", DEFAULT_INSTALL_DIR)))
        self.rimworld_var = tk.StringVar(value=str(_argument_path("--rimworld-dir", DEFAULT_RIMWORLD)))
        self.shortcut_var = tk.BooleanVar(value=True)
        self.device_code = "auto"
        self.device_var = tk.StringVar(value="")
        self.ui_images: dict[str, tk.PhotoImage] = {}
        self._build()
        self.after(100, self._poll_events)

    def t(self, key: str) -> str:
        return SETUP_TEXT[self.language][key]

    def _build(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        shell = tk.Frame(self, bg=COLORS["window"])
        shell.pack(fill="both", expand=True, padx=22, pady=22)

        art_panel = ShadowCard(shell, padx=0, pady=0, radius=24)
        art_panel.pack(side="left", fill="y", padx=(0, 12))
        art_canvas = tk.Canvas(art_panel.body, width=330, height=628, bg=COLORS["navy"], highlightthickness=0)
        art_canvas.pack()
        self.setup_art = self._load_image("setup-art", "autopilot-setup-kit.png", (300, 274))
        if self.setup_art:
            art_canvas.create_image(165, 285, image=self.setup_art)
        else:
            art_canvas.create_text(165, 270, text="AUTOPILOT", fill=COLORS["cyan"], font=FONTS["title"])
        art_canvas.create_text(30, 34, text="RIMWORLD", fill=COLORS["text"], font=("Segoe UI Black", 18), anchor="nw")
        art_canvas.create_text(30, 66, text="AUTOPILOT", fill=COLORS["cyan"], font=("Segoe UI Semibold", 12), anchor="nw")
        art_canvas.create_text(30, 525, text=self.t("art_caption"), fill=COLORS["text"], font=("Segoe UI Semibold", 18), anchor="nw")
        art_canvas.create_text(30, 592, text="LOCAL  •  PRIVATE  •  OPEN SOURCE", fill=COLORS["violet"], font=("Segoe UI Semibold", 8), anchor="nw")

        right = tk.Frame(shell, bg=COLORS["window"])
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        language = tk.Frame(right, bg=COLORS["window"])
        language.pack(fill="x")
        ru_flag = self._load_image("flag-ru", "flag-ru.png", (24, 24))
        en_flag = self._load_image("flag-en", "flag-gb.png", (24, 24))
        FancyButton(language, text="RU", image=ru_flag, width=84, height=36, variant="accent" if self.language == "ru" else "soft", command=lambda: self._set_language("ru")).pack(side="right", padx=(6, 0))
        FancyButton(language, text="EN", image=en_flag, width=84, height=36, variant="accent" if self.language == "en" else "soft", command=lambda: self._set_language("en")).pack(side="right")
        tk.Label(right, text=self.t("title"), bg=COLORS["window"], fg=COLORS["text"], font=FONTS["display"]).pack(anchor="w", pady=(14, 0))
        tk.Label(right, text=self.t("subtitle"), bg=COLORS["window"], fg=COLORS["muted"], font=FONTS["body"]).pack(anchor="w", pady=(4, 14))

        card = ShadowCard(right, padx=22, pady=20, radius=22)
        card.pack(fill="both", expand=True)
        self._folder_field(card.body, "install_dir", self.install_var, self._browse_install)
        self._folder_field(card.body, "game", self.rimworld_var, self._browse_game)
        tk.Label(card.body, text=self.t("device"), bg=COLORS["panel"], fg=COLORS["text"], font=FONTS["heading"]).pack(anchor="w")
        device_labels = {"auto": self.t("auto"), "cuda": self.t("cuda"), "cpu": self.t("cpu")}
        self.device_var.set(device_labels.get(self.device_code, self.t("auto")))
        self.device = ttk.Combobox(card.body, state="readonly", textvariable=self.device_var, values=tuple(device_labels.values()), width=31)
        self.device.bind("<<ComboboxSelected>>", lambda _event: setattr(self, "device_code", next((key for key, value in device_labels.items() if value == self.device_var.get()), "auto")))
        self.device.pack(anchor="w", pady=(8, 12))
        ttk.Checkbutton(card.body, text=self.t("shortcut"), variable=self.shortcut_var).pack(anchor="w", pady=(0, 12))
        tk.Label(card.body, text=self.t("privacy"), bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["small"], justify="left", wraplength=490).pack(anchor="w", pady=(0, 12))
        self.progress = ttk.Progressbar(card.body, mode="indeterminate")
        self.progress.pack(fill="x", pady=(4, 7))
        self.status = tk.Label(card.body, text=self.t("ready"), bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["small"], anchor="w")
        self.status.pack(fill="x")
        self.install_button = FancyButton(card.body, text=self.t("install"), width=220, height=46, variant="accent", command=self._begin)
        self.install_button.pack(side="bottom", anchor="e", pady=(14, 0))

    def _load_image(self, key: str, filename: str, size: tuple[int, int]) -> tk.PhotoImage | None:
        if key in self.ui_images:
            return self.ui_images[key]
        try:
            image = render_photo(RESOURCE_DIR / "assets" / "gui" / filename, size)
            self.ui_images[key] = image
            return image
        except (OSError, tk.TclError):
            return None

    def _folder_field(self, parent: tk.Misc, label: str, variable: tk.StringVar, command) -> None:
        tk.Label(parent, text=self.t(label), bg=COLORS["panel"], fg=COLORS["text"], font=FONTS["heading"]).pack(anchor="w")
        row = tk.Frame(parent, bg=COLORS["panel"])
        row.pack(fill="x", pady=(8, 14))
        tk.Entry(row, textvariable=variable, bg=COLORS["panel_alt"], fg=COLORS["text"], insertbackground=COLORS["cyan"], relief="flat", font=FONTS["body"]).pack(side="left", fill="x", expand=True, ipady=8)
        FancyButton(row, text=self.t("browse"), width=104, height=36, variant="soft", command=command).pack(side="right", padx=(8, 0))

    def _set_language(self, language: str) -> None:
        if language != self.language:
            self.language = language
            self._build()

    def _browse_install(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.install_var.get() or str(DEFAULT_INSTALL_DIR.parent))
        if selected:
            self.install_var.set(selected)

    def _browse_game(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.rimworld_var.get() or str(DEFAULT_RIMWORLD))
        if selected:
            self.rimworld_var.set(selected)

    def _begin(self) -> None:
        rimworld = Path(self.rimworld_var.get()).resolve()
        install_dir = Path(self.install_var.get()).resolve()
        if not (rimworld / "RimWorldWin64.exe").exists():
            messagebox.showerror(self.t("title"), self.t("invalid"))
            return
        source = _source_root().resolve()
        if source in install_dir.parents:
            messagebox.showerror(self.t("title"), self.t("invalid_install"))
            return
        python = self._find_python()
        if not python:
            if messagebox.askyesno(self.t("title"), self.t("python_missing")):
                webbrowser.open("https://www.python.org/downloads/windows/")
            return
        self.install_button.configure(state="disabled", text=self.t("working"))
        self.progress.start(12)
        threading.Thread(target=self._install, args=(python, rimworld, install_dir, self.device_code, self.shortcut_var.get()), daemon=True).start()

    @staticmethod
    def _find_python() -> Path | None:
        candidates = []
        if not getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable))
        for name in ("py", "python"):
            executable = shutil.which(name)
            if not executable:
                continue
            command = [executable, "-3.12", "-c", "import sys;print(sys.executable)"] if name == "py" else [executable, "-c", "import sys;print(sys.executable)"]
            try:
                candidates.append(Path(subprocess.check_output(command, text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()))
            except (OSError, subprocess.SubprocessError):
                pass
        for candidate in candidates:
            try:
                version = subprocess.check_output([str(candidate), "-c", "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')"], text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
                major, minor = map(int, version.split("."))
                if major == 3 and 10 <= minor <= 12:
                    return candidate
            except (OSError, ValueError, subprocess.SubprocessError):
                continue
        return None

    def _emit(self, kind: str, value: str) -> None:
        self.events.put((kind, value))

    @staticmethod
    def _run(args: list[str], cwd: Path) -> None:
        subprocess.run(args, cwd=cwd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)

    @staticmethod
    def _copy_payload(source: Path, destination: Path) -> None:
        copy_install_payload(source, destination)

    @staticmethod
    def _create_shortcut(install_dir: Path, venv_python: Path) -> None:
        executable = install_dir / "RimWorld-Autopilot.exe"
        arguments = ""
        if not executable.exists():
            executable = venv_python.with_name("pythonw.exe")
            arguments = f'"{install_dir / "autopilot_control.py"}"'
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        shortcut = desktop / "RimWorld Autopilot.lnk"
        env = os.environ.copy()
        env.update({"RWA_LINK": str(shortcut), "RWA_TARGET": str(executable), "RWA_ARGS": arguments, "RWA_WORK": str(install_dir), "RWA_ICON": str(install_dir / "RimWorld-Autopilot.exe")})
        script = "$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut($env:RWA_LINK);$s.TargetPath=$env:RWA_TARGET;$s.Arguments=$env:RWA_ARGS;$s.WorkingDirectory=$env:RWA_WORK;if(Test-Path -LiteralPath $env:RWA_ICON){$s.IconLocation=$env:RWA_ICON};$s.Save()"
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script], check=True, env=env, creationflags=subprocess.CREATE_NO_WINDOW)

    def _install(self, python: Path, rimworld: Path, install_dir: Path, device: str, shortcut: bool) -> None:
        try:
            installed_payload = (install_dir / "requirements.txt").exists() and (install_dir / "vendor" / "RIMAPI").exists()
            source_root = install_dir if installed_payload else _source_root().resolve()
            self._emit("status", self.t("step_copy"))
            if source_root != install_dir:
                self._copy_payload(source_root, install_dir)
            venv = install_dir / ".venv"
            venv_python = venv / "Scripts" / "python.exe"
            self._emit("status", self.t("step_python"))
            if not venv_python.exists():
                self._run([str(python), "-m", "venv", str(venv)], install_dir)
            self._emit("status", self.t("step_packages"))
            self._run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], install_dir)
            self._run([str(venv_python), "-m", "pip", "install", "-r", str(install_dir / "requirements.txt")], install_dir)
            self._emit("status", self.t("step_model"))
            try:
                self._run([str(venv_python), str(install_dir / "rimworld_laya.py"), "download-model"], install_dir)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(self.t("model_failed")) from exc
            self._emit("status", self.t("step_mod"))
            source = (install_dir / "vendor" / "RIMAPI").resolve()
            mods = (rimworld / "Mods").resolve()
            target = (mods / "RIMAPI").resolve()
            if mods not in target.parents or not source.exists():
                raise RuntimeError("Invalid RIMAPI source or target path")
            if target.exists():
                backup = mods / f"RIMAPI.backup-{datetime.now():%Y%m%d-%H%M%S}"
                shutil.move(str(target), str(backup))
            shutil.copytree(source, target)
            self._emit("status", self.t("step_config"))
            config = {
                "python_exe": str(venv_python), "director_script": str(install_dir / "colony_director.py"),
                "api_url": "http://localhost:8765", "device": device, "interval": 10,
                "rimworld_path": str(rimworld),
            }
            serialized = json.dumps(config, ensure_ascii=False, indent=2)
            (install_dir / "rimworld-autopilot.json").write_text(serialized, encoding="utf-8")
            user_data = Path(os.environ.get("LOCALAPPDATA", str(install_dir))) / PRODUCT_NAME
            user_data.mkdir(parents=True, exist_ok=True)
            (user_data / "rimworld-autopilot.json").write_text(serialized, encoding="utf-8")
            if shortcut:
                self._create_shortcut(install_dir, venv_python)
            self._emit("done", self.t("done"))
        except Exception as exc:
            self._emit("error", f"{self.t('error')}: {exc}")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                self.status.configure(text=value, fg=COLORS["red"] if kind == "error" else COLORS["green"] if kind == "done" else COLORS["muted"])
                if kind in {"done", "error"}:
                    self.progress.stop()
                    self.install_button.configure(state="normal", text=self.t("install"))
                    (messagebox.showinfo if kind == "done" else messagebox.showerror)(self.t("title"), value)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)


def run() -> None:
    SetupWindow().mainloop()
