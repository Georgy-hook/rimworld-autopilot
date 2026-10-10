from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.error import URLError
from typing import Any

import colony_strategy as strategy
import laya_preferences
from rimworld_installation import validate_game_path

from .i18n import PRIORITY_TEXT, QUESTION_TEXT, doctrine_view, humanize, risk_text, tr
from .services import (
    APP_NAME, BASE_DIR, DATA_DIR, FEEDBACK_PATH, PREFERENCES_PATH, RESOURCE_DIR,
    active_map_key, append_feedback, export_bundle, export_history, load_config, read_director_health, read_pid, request_json, resolve_log_dir,
    save_config, start_director, start_observer as launch_observer, stop_director, tail_jsonl,
    timestamped_export_name,
)
from .theme import (
    COLORS, FONTS, FancyButton, ModernScrollbar, ScrollablePage, ShadowCard,
    configure_styles, render_photo, rounded_rectangle, status_color,
)


class ControlCenter(tk.Tk):
    def _configure_run_paths(self) -> None:
        self.log_dir = resolve_log_dir(self.config_data)
        self.log_path = self.log_dir / "decisions.jsonl"
        self.state_path = self.log_dir / "colony-state.json"
        self.pid_path = self.log_dir / "director.pid"
        self.runtime_status_path = self.log_dir / "runtime-status.json"
        self.observer_pid_path = self.log_dir / "observer.pid"
        self.observer_status_path = self.log_dir / "observer-status.json"
        self.observer_log_path = self.log_dir / "observer.jsonl"

    def __init__(self) -> None:
        super().__init__()
        if os.environ.get("LAYA_GUI_SMOKE_TEST") == "1":
            self.withdraw()
        self.config_data = load_config()
        self._configure_run_paths()
        self.preferences = laya_preferences.load_preferences(PREFERENCES_PATH)
        self.language = str(self.preferences.get("language") or "ru")
        self.records: list[dict[str, Any]] = []
        self.last_log_signature: tuple[int, int] | None = None
        self.game_online = False
        self.active_map_key: str | None = None
        self.active_game_tick: int | None = None
        self.current_page = "overview"
        self.animation_tick = 0
        self.animation_started = time.perf_counter()
        self._hero_resize_job: str | None = None
        self._hero_render_width = 0
        self.title(APP_NAME)
        self.geometry("1440x900")
        self.minsize(1240, 800)
        self.configure(bg=COLORS["window"])
        configure_styles(self)
        self._build_ui()
        self.after(150, self.refresh_all)
        self.after(16, self._animate_mascot)
        if self.preferences.get("observer", {}).get("enabled") and os.environ.get("LAYA_GUI_SMOKE_TEST") != "1":
            self.after(300, self._auto_start_observer)

    def _build_ui(self) -> None:
        self._hero_resize_job = None
        self._hero_render_width = 0
        self.nav_buttons: dict[str, FancyButton] = {}
        self.ui_images: dict[str, tk.PhotoImage] = {}
        self.pages: dict[str, tk.Widget] = {}
        self.priority_scales: dict[str, ttk.Scale] = {}
        self.priority_values: dict[str, tk.Label] = {}
        self._load_ui_variables()
        self._load_shared_images()

        shell = tk.Frame(self, bg=COLORS["window"])
        shell.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(shell, bg=COLORS["sidebar"], width=232)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Frame(shell, bg=COLORS["shadow"], width=7).pack(side="left", fill="y")

        self.main = tk.Frame(shell, bg=COLORS["window"])
        self.main.pack(side="left", fill="both", expand=True)
        self._build_sidebar()
        self._build_header()
        self.page_host = tk.Frame(self.main, bg=COLORS["window"])
        self.page_host.pack(fill="both", expand=True, padx=24, pady=(4, 14))
        self._build_overview_page()
        self._build_strategy_page()
        self._build_priorities_page()
        self._build_history_page()
        self._build_stream_page()
        self._build_settings_page()
        self.footer = tk.Label(self.main, text=tr(self.language, "ready"), bg=COLORS["sidebar"], fg=COLORS["muted"], anchor="w", padx=20, pady=8, font=FONTS["small"])
        self.footer.pack(fill="x", side="bottom")
        self.switch_page(self.current_page)

    def _load_ui_variables(self) -> None:
        self.tech_var = tk.BooleanVar(value=bool(self.preferences.get("technical_logging")))
        safety = self.preferences.get("safety") or {}
        self.avoid_attacks_var = tk.BooleanVar(value=bool(safety.get("avoid_unprovoked_attacks")))
        self.peaceful_trade_var = tk.BooleanVar(value=bool(safety.get("prefer_peaceful_trade")))
        self.protect_food_var = tk.BooleanVar(value=bool(safety.get("protect_food_reserve", True)))
        overlay = self.preferences.get("overlay") or {}
        self.overlay_enabled_var = tk.BooleanVar(value=bool(overlay.get("enabled", True)))
        self.overlay_compact_var = tk.BooleanVar(value=bool(overlay.get("compact", True)))
        self.game_folder_var = tk.StringVar(value=str(self.config_data.get("rimworld_path") or tr(self.language, "game_folder_unset")))

    def _load_shared_images(self) -> None:
        self.flag_images = {
            "ru": self._load_ui_image("flag-ru", "flag-ru.png", (24, 24)),
            "en": self._load_ui_image("flag-gb", "flag-gb.png", (24, 24)),
        }

    def _load_ui_image(self, key: str, filename: str, size: tuple[int, int]) -> tk.PhotoImage | None:
        asset = RESOURCE_DIR / "assets" / "gui" / filename
        try:
            image = render_photo(asset, size)
            self.ui_images[key] = image
            return image
        except (OSError, tk.TclError) as exc:
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                with (self.log_dir / "ui-assets.log").open("a", encoding="utf-8") as handle:
                    handle.write(f"{datetime.now().isoformat()} | {asset} | {exc}\n")
            except OSError:
                pass
            return None

    def _build_sidebar(self) -> None:
        self.mascot_canvas = tk.Canvas(self.sidebar, width=224, height=150, bg=COLORS["sidebar"], highlightthickness=0)
        self.mascot_canvas.pack(pady=(12, 0))
        self.mascot_canvas.create_oval(42, 119, 182, 139, fill="#080A10", outline="")
        self.mascot_canvas.create_oval(38, 16, 186, 132, outline=COLORS["line"], width=1)
        self.orbit_items = [
            self.mascot_canvas.create_oval(0, 0, 7, 7, fill=color, outline="")
            for color in (COLORS["cyan"], COLORS["violet"], COLORS["amber"])
        ]
        self.mascot_item = None
        self.mascot_image = self._load_ui_image("emblem", "autopilot-emblem.png", (112, 112))
        if self.mascot_image:
            self.mascot_item = self.mascot_canvas.create_image(113, 74, image=self.mascot_image)
        else:
            self.mascot_canvas.create_text(112, 73, text="AUTOPILOT", fill=COLORS["cyan"], font=FONTS["heading"])
        tk.Label(self.sidebar, text="RIMWORLD", bg=COLORS["sidebar"], fg=COLORS["text"], font=("Segoe UI Black", 15)).pack()
        tk.Label(self.sidebar, text="AUTOPILOT", bg=COLORS["sidebar"], fg=COLORS["cyan"], font=("Segoe UI Semibold", 9)).pack(pady=(0, 18))

        for page in ("overview", "strategy", "priorities", "history", "stream", "settings"):
            icon = None if page == "stream" else self._load_ui_image(f"nav-{page}", f"nav-{page}.png", (34, 34))
            button = FancyButton(
                self.sidebar, text=tr(self.language, page), width=208, height=52, variant="ghost", align="left",
                image=icon, icon="◉" if page == "stream" else "",
                command=lambda name=page: self.switch_page(name),
            )
            button.pack(padx=10, pady=2)
            self.nav_buttons[page] = button

        self.sidebar_status = tk.Label(self.sidebar, text="", bg=COLORS["sidebar"], fg=COLORS["muted"], justify="left", anchor="w", font=FONTS["small"])
        self.sidebar_status.pack(side="bottom", fill="x", padx=20, pady=20)

    def _build_header(self) -> None:
        header = tk.Frame(self.main, bg=COLORS["window"])
        header.pack(fill="x", padx=26, pady=(20, 10))
        titles = tk.Frame(header, bg=COLORS["window"])
        titles.pack(side="left", fill="x", expand=True)
        self.page_title = tk.Label(titles, text="", bg=COLORS["window"], fg=COLORS["text"], font=FONTS["display"], anchor="w")
        self.page_title.pack(anchor="w")
        self.page_subtitle = tk.Label(titles, text="", bg=COLORS["window"], fg=COLORS["muted"], font=FONTS["body"], anchor="w")
        self.page_subtitle.pack(anchor="w", pady=(2, 0))

        target_language = "en" if self.language == "ru" else "ru"
        self.language_button = FancyButton(
            header, text=target_language.upper(), image=self.flag_images.get(target_language), width=94, height=38, variant="soft",
            command=lambda: self.set_language("en" if self.language == "ru" else "ru"),
        )
        self.language_button.pack(side="right", padx=(10, 0))
        self.game_chip = tk.Label(header, text=tr(self.language, "game_offline"), bg=COLORS["panel"], fg=COLORS["red"], padx=12, pady=7, font=("Segoe UI Semibold", 9))
        self.game_chip.pack(side="right", padx=5)
        self.laya_chip = tk.Label(header, text=tr(self.language, "laya_offline"), bg=COLORS["panel"], fg=COLORS["red"], padx=12, pady=7, font=("Segoe UI Semibold", 9))
        self.laya_chip.pack(side="right", padx=5)
        self.observer_chip = tk.Label(header, text=tr(self.language, "observer_offline"), bg=COLORS["panel"], fg=COLORS["muted"], padx=12, pady=7, font=("Segoe UI Semibold", 9))
        self.observer_chip.pack(side="right", padx=5)

    def _new_page(self, name: str, *, scroll: bool = False) -> tk.Frame:
        container = tk.Frame(self.page_host, bg=COLORS["window"])
        self.pages[name] = container
        if not scroll:
            return container
        viewport = ScrollablePage(container)
        viewport.pack(fill="both", expand=True)
        return viewport.body

    def _build_overview_page(self) -> None:
        page = self._new_page("overview")
        art = ShadowCard(page, padx=0, pady=0, radius=22)
        art.pack(fill="x", pady=(0, 14))
        self.hero_canvas = tk.Canvas(art.body, height=188, bg=COLORS["panel"], highlightthickness=0, bd=0)
        self.hero_canvas.pack(fill="x")
        self.hero_image = None
        self.hero_art_item = None
        rounded_rectangle(self.hero_canvas, 28, 28, 530, 160, 18, fill="#0B1021", outline=COLORS["line"], width=1)
        self.hero_canvas.create_text(52, 52, text="RIMWORLD AUTOPILOT", fill=COLORS["cyan"], font=("Segoe UI Black", 11), anchor="nw")
        self.hero_canvas.create_text(52, 82, text=tr(self.language, "hero_title"), fill=COLORS["text"], font=("Segoe UI Semibold", 21), anchor="nw")
        self.hero_canvas.create_text(52, 121, text=tr(self.language, "hero_subtitle"), fill=COLORS["muted"], font=FONTS["body"], anchor="nw")
        self.hero_canvas.bind("<Configure>", self._position_hero)

        hero = ShadowCard(page, padx=22, pady=18)
        hero.pack(fill="x", pady=(0, 14))
        left = tk.Frame(hero.body, bg=COLORS["panel"])
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text=tr(self.language, "current_course"), bg=COLORS["panel"], fg=COLORS["violet"], font=("Segoe UI Semibold", 10)).pack(anchor="w")
        self.overview_course = tk.Label(left, text=tr(self.language, "no_doctrine"), bg=COLORS["panel"], fg=COLORS["text"], font=FONTS["title"], justify="left", anchor="w", wraplength=660)
        self.overview_course.pack(anchor="w", pady=(5, 3))
        self.overview_course_details = tk.Label(left, text="", bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["body"], justify="left", anchor="w", wraplength=700)
        self.overview_course_details.pack(anchor="w")

        controls = tk.Frame(hero.body, bg=COLORS["panel"])
        controls.pack(side="right", padx=(20, 0))
        FancyButton(controls, text=tr(self.language, "start"), width=216, variant="accent", command=self.start_laya).grid(row=0, column=0, columnspan=2, pady=(0, 7))
        FancyButton(controls, text=tr(self.language, "stop"), width=216, variant="danger", command=self.stop_laya).grid(row=1, column=0, columnspan=2, pady=(0, 7))
        FancyButton(controls, text=tr(self.language, "pause"), width=104, variant="soft", command=lambda: self.set_speed(0)).grid(row=2, column=0, padx=(0, 4))
        FancyButton(controls, text=tr(self.language, "resume"), width=104, variant="soft", command=lambda: self.set_speed(1)).grid(row=2, column=1, padx=(4, 0))

        row = tk.Frame(page, bg=COLORS["window"])
        row.pack(fill="both", expand=True)
        latest = ShadowCard(row)
        latest.pack(side="left", fill="both", expand=True, padx=(0, 7))
        tk.Label(latest.body, text=tr(self.language, "latest_choice"), bg=COLORS["panel"], fg=COLORS["cyan"], font=FONTS["heading"]).pack(anchor="w")
        self.latest_choice = tk.Label(latest.body, text=tr(self.language, "waiting"), bg=COLORS["panel"], fg=COLORS["text"], font=FONTS["title"], justify="left", anchor="nw", wraplength=430)
        self.latest_choice.pack(fill="x", pady=(12, 6))
        self.latest_result = tk.Label(latest.body, text="", bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["body"], justify="left", anchor="nw", wraplength=430)
        self.latest_result.pack(fill="x")

        content = ShadowCard(row)
        content.pack(side="left", fill="both", expand=True, padx=(7, 0))
        tk.Label(content.body, text=tr(self.language, "expansions"), bg=COLORS["panel"], fg=COLORS["amber"], font=FONTS["heading"]).pack(anchor="w")
        self.content_summary = tk.Label(content.body, text="—", bg=COLORS["panel"], fg=COLORS["text"], font=FONTS["title"], justify="left", anchor="nw", wraplength=430)
        self.content_summary.pack(fill="x", pady=(12, 6))
        self.content_details = tk.Label(content.body, text="", bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["body"], justify="left", anchor="nw", wraplength=430)
        self.content_details.pack(fill="x")

    def _build_strategy_page(self) -> None:
        page = self._new_page("strategy")
        summary = ShadowCard(page)
        summary.pack(fill="x", pady=(0, 14))
        tk.Label(summary.body, text=tr(self.language, "current_course"), bg=COLORS["panel"], fg=COLORS["violet"], font=FONTS["heading"]).pack(anchor="w")
        self.strategy_summary = tk.Label(summary.body, text=tr(self.language, "no_doctrine"), bg=COLORS["panel"], fg=COLORS["text"], font=FONTS["body"], justify="left", anchor="w", wraplength=950)
        self.strategy_summary.pack(fill="x", pady=(10, 0))
        catalog = ShadowCard(page)
        catalog.pack(fill="both", expand=True)
        tk.Label(catalog.body, text=tr(self.language, "available_directions"), bg=COLORS["panel"], fg=COLORS["cyan"], font=FONTS["heading"]).pack(anchor="w", pady=(0, 8))
        self.direction_catalog = tk.Text(catalog.body, bg=COLORS["panel"], fg=COLORS["text"], relief="flat", bd=0, wrap="word", font=FONTS["body"], padx=2, pady=2, cursor="arrow")
        self.direction_catalog.pack(fill="both", expand=True)
        self.direction_catalog.configure(state="disabled")

    def _build_priorities_page(self) -> None:
        page = self._new_page("priorities", scroll=True)
        grid = ShadowCard(page, padx=20, pady=16)
        grid.pack(fill="x", pady=(0, 14))
        priorities = self.preferences.get("priorities") or {}
        for index, key in enumerate(laya_preferences.DEFAULT_PRIORITIES):
            row, column = divmod(index, 2)
            cell = tk.Frame(grid.body, bg=COLORS["panel"])
            cell.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 20, 20 if column == 0 else 0), pady=8)
            grid.body.grid_columnconfigure(column, weight=1)
            title, help_text = PRIORITY_TEXT[self.language][key]
            top = tk.Frame(cell, bg=COLORS["panel"])
            top.pack(fill="x")
            tk.Label(top, text=title, bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 10)).pack(side="left")
            value = tk.Label(top, text=str(int(priorities.get(key, 50))), bg=COLORS["panel"], fg=COLORS["cyan"], font=("Segoe UI Semibold", 10))
            value.pack(side="right")
            tk.Label(cell, text=help_text, bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["small"]).pack(anchor="w")
            scale = ttk.Scale(cell, from_=0, to=100, value=int(priorities.get(key, 50)), command=lambda raw, name=key: self._priority_changed(name, raw))
            scale.pack(fill="x", pady=(5, 0))
            self.priority_scales[key] = scale
            self.priority_values[key] = value

        lower = tk.Frame(page, bg=COLORS["window"])
        lower.pack(fill="both", expand=True)
        note_card = ShadowCard(lower)
        note_card.pack(side="left", fill="both", expand=True, padx=(0, 7))
        tk.Label(note_card.body, text=tr(self.language, "personal_note"), bg=COLORS["panel"], fg=COLORS["violet"], font=FONTS["heading"]).pack(anchor="w")
        tk.Label(note_card.body, text=tr(self.language, "personal_note_hint"), bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["small"], justify="left", wraplength=480).pack(anchor="w", pady=(4, 8))
        self.personal_note = tk.Text(note_card.body, height=7, bg=COLORS["panel_alt"], fg=COLORS["text"], insertbackground=COLORS["cyan"], relief="flat", wrap="word", font=FONTS["body"], padx=10, pady=8)
        self.personal_note.pack(fill="both", expand=True)
        self.personal_note.insert("1.0", str(self.preferences.get("personal_note") or ""))

        safety = ShadowCard(lower)
        safety.pack(side="left", fill="both", expand=True, padx=(7, 0))
        tk.Label(safety.body, text=tr(self.language, "safety"), bg=COLORS["panel"], fg=COLORS["amber"], font=FONTS["heading"]).pack(anchor="w", pady=(0, 8))
        ttk.Checkbutton(safety.body, text=tr(self.language, "avoid_attacks"), variable=self.avoid_attacks_var).pack(anchor="w", pady=5)
        ttk.Checkbutton(safety.body, text=tr(self.language, "peaceful_trade"), variable=self.peaceful_trade_var).pack(anchor="w", pady=5)
        ttk.Checkbutton(safety.body, text=tr(self.language, "protect_food"), variable=self.protect_food_var).pack(anchor="w", pady=5)
        actions = tk.Frame(safety.body, bg=COLORS["panel"])
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(actions, text=tr(self.language, "save"), style="Accent.TButton", command=self.save_priorities).pack(side="left")
        ttk.Button(actions, text=tr(self.language, "reset"), style="Soft.TButton", command=self.reset_priorities).pack(side="right")

    def _build_history_page(self) -> None:
        page = self._new_page("history")
        toolbar = tk.Frame(page, bg=COLORS["window"])
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text=tr(self.language, "correct_decision"), style="Soft.TButton",
                   command=self.rate_selected_decision).pack(side="left")
        ttk.Checkbutton(toolbar, text=tr(self.language, "technical_mode"), variable=self.tech_var, command=self.toggle_technical).pack(side="right")
        history = ShadowCard(page, padx=10, pady=10)
        history.pack(fill="both", expand=True)
        table = tk.Frame(history.body, bg=COLORS["panel"])
        table.pack(fill="both", expand=True)
        columns = ("time", "choice", "confidence", "result")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse", height=9)
        headings = {"time": "Время" if self.language == "ru" else "Time", "choice": "Выбор Laya" if self.language == "ru" else "Laya's choice", "confidence": tr(self.language, "confidence"), "result": tr(self.language, "result")}
        widths = {"time": 135, "choice": 360, "confidence": 110, "result": 360}
        for name in columns:
            self.tree.heading(name, text=headings[name])
            self.tree.column(name, width=widths[name], anchor="w")
        scroll = ModernScrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y", padx=(8, 0))
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.show_selected)
        tk.Label(history.body, text=tr(self.language, "details"), bg=COLORS["panel"], fg=COLORS["violet"], font=FONTS["heading"]).pack(anchor="w", pady=(12, 5))
        self.details = tk.Text(history.body, height=9, bg=COLORS["panel_alt"], fg=COLORS["text"], relief="flat", font=FONTS["body"] if not self.tech_var.get() else FONTS["mono"], wrap="word", padx=12, pady=10, cursor="arrow")
        self.details.pack(fill="both", expand=True)

    def _build_stream_page(self) -> None:
        page = self._new_page("stream")
        control = ShadowCard(page, padx=26, pady=24)
        control.pack(fill="x", pady=(0, 14))
        tk.Label(control.body, text=tr(self.language, "observer_title"), bg=COLORS["panel"], fg=COLORS["cyan"], font=FONTS["title"]).pack(anchor="w")
        tk.Label(control.body, text=tr(self.language, "observer_help"), bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["body"],
                 justify="left", wraplength=880).pack(anchor="w", pady=(8, 16))
        buttons = tk.Frame(control.body, bg=COLORS["panel"])
        buttons.pack(anchor="w")
        FancyButton(buttons, text=tr(self.language, "observer_start"), width=206, variant="accent", command=self.start_stream_observer).pack(side="left", padx=(0, 10))
        FancyButton(buttons, text=tr(self.language, "observer_stop"), width=206, variant="soft", command=self.stop_stream_observer).pack(side="left")
        self.observer_status_label = tk.Label(control.body, text=tr(self.language, "observer_offline"), bg=COLORS["panel"],
                                              fg=COLORS["muted"], font=FONTS["heading"], anchor="w")
        self.observer_status_label.pack(fill="x", pady=(20, 4))
        self.observer_focus_label = tk.Label(control.body, text=tr(self.language, "observer_no_focus"), bg=COLORS["panel"],
                                             fg=COLORS["text"], font=FONTS["body"], anchor="w")
        self.observer_focus_label.pack(fill="x")

        guide = ShadowCard(page, padx=26, pady=24)
        guide.pack(fill="x")
        tk.Label(guide.body, text=tr(self.language, "observer_rules_title"), bg=COLORS["panel"], fg=COLORS["amber"], font=FONTS["heading"]).pack(anchor="w")
        tk.Label(guide.body, text=tr(self.language, "observer_rules"), bg=COLORS["panel"], fg=COLORS["text"],
                 font=FONTS["body"], justify="left", wraplength=950).pack(anchor="w", pady=(10, 0))

    def _build_settings_page(self) -> None:
        page = self._new_page("settings", scroll=True)
        row = tk.Frame(page, bg=COLORS["window"])
        row.pack(fill="x")
        language = ShadowCard(row)
        language.pack(side="left", fill="both", expand=True, padx=(0, 7))
        tk.Label(language.body, text=tr(self.language, "language"), bg=COLORS["panel"], fg=COLORS["cyan"], font=FONTS["heading"]).pack(anchor="w", pady=(0, 10))
        buttons = tk.Frame(language.body, bg=COLORS["panel"])
        buttons.pack(anchor="w")
        FancyButton(buttons, text="Русский", image=self.flag_images.get("ru"), width=150, variant="accent" if self.language == "ru" else "soft", command=lambda: self.set_language("ru")).pack(side="left", padx=(0, 7))
        FancyButton(buttons, text="English", image=self.flag_images.get("en"), width=150, variant="accent" if self.language == "en" else "soft", command=lambda: self.set_language("en")).pack(side="left")

        logging = ShadowCard(row)
        logging.pack(side="left", fill="both", expand=True, padx=(7, 0))
        ttk.Checkbutton(logging.body, text=tr(self.language, "technical_logging"), variable=self.tech_var, command=self.toggle_technical).pack(anchor="w")
        tk.Label(logging.body, text=tr(self.language, "technical_help"), bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["small"], justify="left", wraplength=440).pack(anchor="w", pady=(8, 0))

        installation = ShadowCard(page)
        installation.pack(fill="x", pady=(14, 0))
        tk.Label(installation.body, text=tr(self.language, "game_folder"), bg=COLORS["panel"], fg=COLORS["cyan"], font=FONTS["heading"]).pack(anchor="w")
        tk.Entry(installation.body, textvariable=self.game_folder_var, state="readonly", readonlybackground=COLORS["panel_alt"],
                 fg=COLORS["text"], relief="flat", font=FONTS["body"]).pack(fill="x", pady=(8, 8), ipady=6)
        tk.Label(installation.body, text=tr(self.language, "game_folder_help"), bg=COLORS["panel"], fg=COLORS["muted"],
                 font=FONTS["small"], justify="left", wraplength=940).pack(anchor="w", pady=(0, 10))
        FancyButton(installation.body, text=tr(self.language, "run_installer"), width=250, variant="soft", command=self.open_setup).pack(anchor="w")

        runtime = ShadowCard(page)
        runtime.pack(fill="x", pady=(14, 0))
        tk.Label(runtime.body, text=tr(self.language, "model_device"), bg=COLORS["panel"], fg=COLORS["cyan"], font=FONTS["heading"]).pack(anchor="w")
        device_labels = {key: tr(self.language, f"device_{key}") for key in ("auto", "cuda", "cpu")}
        self.model_device_var = tk.StringVar(value=device_labels.get(self.config_data.get("device"), device_labels["auto"]))
        device_box = ttk.Combobox(runtime.body, state="readonly", textvariable=self.model_device_var,
                                  values=tuple(device_labels.values()), width=31)
        device_box.pack(anchor="w", pady=(8, 6))
        device_box.bind("<<ComboboxSelected>>", lambda _event: self.save_model_device(
            next(key for key, label in device_labels.items() if label == self.model_device_var.get())))
        tk.Label(runtime.body, text=tr(self.language, "model_device_help"), bg=COLORS["panel"], fg=COLORS["muted"],
                 font=FONTS["small"], justify="left", wraplength=940).pack(anchor="w", pady=(0, 8))
        self.model_runtime_label = tk.Label(runtime.body, text=tr(self.language, "device_not_loaded"), bg=COLORS["panel"],
                                           fg=COLORS["text"], font=FONTS["small"], justify="left", wraplength=940)
        self.model_runtime_label.pack(anchor="w")

        overlay = ShadowCard(page)
        overlay.pack(fill="x", pady=(14, 0))
        tk.Label(overlay.body, text=tr(self.language, "overlay_title"), bg=COLORS["panel"], fg=COLORS["amber"], font=FONTS["heading"]).pack(anchor="w")
        tk.Label(overlay.body, text=tr(self.language, "overlay_help"), bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["small"], justify="left", wraplength=940).pack(anchor="w", pady=(5, 8))
        ttk.Checkbutton(overlay.body, text=tr(self.language, "overlay_enabled"), variable=self.overlay_enabled_var, command=self.save_overlay_settings).pack(anchor="w", pady=4)
        ttk.Checkbutton(overlay.body, text=tr(self.language, "overlay_compact"), variable=self.overlay_compact_var, command=self.save_overlay_settings).pack(anchor="w", pady=4)

        maintenance = ShadowCard(page)
        maintenance.pack(fill="x", pady=14)
        tk.Label(maintenance.body, text=tr(self.language, "maintenance"), bg=COLORS["panel"], fg=COLORS["amber"], font=FONTS["heading"]).pack(anchor="w")
        tk.Label(maintenance.body, text=tr(self.language, "maintenance_help"), bg=COLORS["panel"], fg=COLORS["muted"], font=FONTS["body"], justify="left", wraplength=800).pack(side="left", pady=(8, 0))
        ttk.Button(maintenance.body, text=tr(self.language, "uninstall"), style="Danger.TButton", command=self.open_uninstaller).pack(side="right", padx=(15, 0))

        exports = ShadowCard(page)
        exports.pack(fill="x")
        ttk.Button(exports.body, text=tr(self.language, "export_history"), style="Soft.TButton", command=self.export_history).pack(side="left", padx=(0, 8))
        ttk.Button(exports.body, text=tr(self.language, "export_bundle"), style="Soft.TButton", command=self.export_bundle).pack(side="left", padx=8)
        ttk.Button(exports.body, text=tr(self.language, "open_folder"), style="Soft.TButton", command=lambda: os.startfile(BASE_DIR)).pack(side="right")

    def switch_page(self, name: str) -> None:
        if name not in self.pages:
            name = "overview"
        self.current_page = name
        self.last_log_signature = None
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for key, button in self.nav_buttons.items():
            active = key == name
            button.configure(variant="soft" if active else "ghost")
        self.page_title.configure(text=tr(self.language, name))
        self.page_subtitle.configure(text=tr(self.language, f"{name}_sub"))

    def set_language(self, language: str) -> None:
        if language not in {"ru", "en"} or language == self.language:
            return
        self._capture_preferences()
        self.language = language
        self.preferences["language"] = language
        laya_preferences.save_preferences(self.preferences, PREFERENCES_PATH)
        self.last_log_signature = None
        if self._hero_resize_job:
            self.after_cancel(self._hero_resize_job)
            self._hero_resize_job = None
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self.refresh_views()

    def _priority_changed(self, key: str, raw: str) -> None:
        if key in self.priority_values:
            self.priority_values[key].configure(text=str(int(float(raw))))

    def save_priorities(self) -> None:
        self._capture_preferences()
        laya_preferences.save_preferences(self.preferences, PREFERENCES_PATH)
        self.footer.configure(text=tr(self.language, "saved"), fg=COLORS["green"])

    def _capture_preferences(self) -> None:
        self.preferences["priorities"] = {key: int(float(scale.get())) for key, scale in self.priority_scales.items()}
        self.preferences["personal_note"] = self.personal_note.get("1.0", "end").strip()[:1200]
        self.preferences["safety"] = {
            "avoid_unprovoked_attacks": self.avoid_attacks_var.get(),
            "prefer_peaceful_trade": self.peaceful_trade_var.get(),
            "protect_food_reserve": self.protect_food_var.get(),
        }
        self.preferences["technical_logging"] = self.tech_var.get()
        self.preferences["overlay"] = {
            "enabled": self.overlay_enabled_var.get(),
            "compact": self.overlay_compact_var.get(),
            "max_options": int((self.preferences.get("overlay") or {}).get("max_options", 5)),
        }

    def save_overlay_settings(self) -> None:
        self._capture_preferences()
        laya_preferences.save_preferences(self.preferences, PREFERENCES_PATH)
        if not self.overlay_enabled_var.get():
            try:
                request_json(
                    f"{str(self.config_data['api_url']).rstrip('/')}/api/v1/ui/announce",
                    method="POST",
                    body={"text": "", "duration": 0.0, "panel": True, "compact": True, "bars": []},
                )
            except Exception:
                pass
        self.footer.configure(text=tr(self.language, "overlay_saved"), fg=COLORS["green"])

    def reset_priorities(self) -> None:
        for key, value in laya_preferences.DEFAULT_PRIORITIES.items():
            self.priority_scales[key].set(value)
            self.priority_values[key].configure(text=str(value))
        self.avoid_attacks_var.set(False)
        self.peaceful_trade_var.set(False)
        self.protect_food_var.set(True)

    def toggle_technical(self) -> None:
        self.preferences["technical_logging"] = self.tech_var.get()
        laya_preferences.save_preferences(self.preferences, PREFERENCES_PATH)
        if hasattr(self, "details"):
            self.details.configure(font=FONTS["mono"] if self.tech_var.get() else FONTS["body"])
            self.show_selected()

    def start_laya(self) -> None:
        health = read_director_health(self.pid_path, self.runtime_status_path)
        existing = health.get("pid")
        if existing and health.get("state") in {"running", "starting", "waiting"}:
            messagebox.showinfo(APP_NAME, tr(self.language, "laya_online"))
            return
        try:
            # A live PID with a stale/error heartbeat is not a healthy
            # autopilot. Replace it instead of leaving the Start button inert.
            if existing:
                stop_director(self.pid_path, self.runtime_status_path)
            pid = start_director(self.config_data, self.log_path, self.state_path, self.pid_path, self.runtime_status_path)
            self.footer.configure(text=f"{tr(self.language, 'laya_online')} · PID {pid}", fg=COLORS["green"])
        except (OSError, FileNotFoundError) as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'error')}: {exc}")

    def save_model_device(self, device: str) -> None:
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError(f"Unknown model device: {device!r}")
        config = dict(self.config_data, device=device)
        try:
            save_config(config)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'error')}: {exc}")
            return
        self.config_data = config
        self.footer.configure(text=tr(self.language, "device_saved"), fg=COLORS["cyan"])

    def stop_laya(self) -> None:
        try:
            pid = stop_director(self.pid_path, self.runtime_status_path)
            self.footer.configure(text=tr(self.language, "laya_offline") if pid else tr(self.language, "laya_offline"), fg=COLORS["muted"])
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'error')}: {exc}")

    def _auto_start_observer(self) -> None:
        health = read_director_health(self.observer_pid_path, self.observer_status_path)
        if health.get("state") in {"running", "starting", "waiting"}:
            return
        try:
            if health.get("pid"):
                stop_director(self.observer_pid_path, self.observer_status_path)
            launch_observer(self.config_data, pid_path=self.observer_pid_path,
                            status_path=self.observer_status_path, log_path=self.observer_log_path)
        except (OSError, RuntimeError, FileNotFoundError) as exc:
            self.footer.configure(text=f"{tr(self.language, 'observer_error')}: {exc}", fg=COLORS["red"])

    def start_stream_observer(self) -> None:
        health = read_director_health(self.observer_pid_path, self.observer_status_path)
        try:
            if health.get("pid") and health.get("state") not in {"running", "starting", "waiting"}:
                stop_director(self.observer_pid_path, self.observer_status_path)
            if health.get("state") not in {"running", "starting", "waiting"}:
                launch_observer(self.config_data, pid_path=self.observer_pid_path,
                            status_path=self.observer_status_path, log_path=self.observer_log_path)
            self.preferences["observer"] = {"enabled": True}
            laya_preferences.save_preferences(self.preferences, PREFERENCES_PATH)
            self.refresh_views()
        except (OSError, RuntimeError, FileNotFoundError) as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'observer_error')}: {exc}")

    def stop_stream_observer(self) -> None:
        try:
            stop_director(self.observer_pid_path, self.observer_status_path)
            self.preferences["observer"] = {"enabled": False}
            laya_preferences.save_preferences(self.preferences, PREFERENCES_PATH)
            self.refresh_views()
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'observer_error')}: {exc}")

    def set_speed(self, speed: int) -> None:
        url = f"{str(self.config_data['api_url']).rstrip('/')}/api/v1/game/speed?speed={speed}"
        try:
            result = request_json(url, method="POST")
            if not result.get("success", False):
                raise RuntimeError("; ".join(result.get("errors") or [tr(self.language, "error")]))
            self.footer.configure(text=tr(self.language, "pause" if speed == 0 else "resume"), fg=COLORS["cyan"])
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'error')}: {exc}")

    def export_history(self) -> None:
        target = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("JSON Lines", "*.jsonl")], initialfile=timestamped_export_name("autopilot-history", "csv"))
        if not target:
            return
        try:
            export_history(self.log_path, Path(target))
            self.footer.configure(text=f"{tr(self.language, 'done')}: {target}", fg=COLORS["green"])
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def export_bundle(self) -> None:
        target = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP", "*.zip")], initialfile=timestamped_export_name("autopilot-export", "zip"))
        if not target:
            return
        try:
            export_bundle(Path(target), self.log_path, self.state_path)
            self.footer.configure(text=f"{tr(self.language, 'done')}: {target}", fg=COLORS["green"])
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def open_uninstaller(self) -> None:
        executable = BASE_DIR / "unins000.exe"
        try:
            if executable.exists():
                subprocess.Popen([str(executable)], cwd=BASE_DIR)
            else:
                os.startfile("ms-settings:appsfeatures")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'error')}: {exc}")

    def open_setup(self) -> None:
        for pid_path, status_path in ((self.pid_path, self.runtime_status_path),
                                      (self.observer_pid_path, self.observer_status_path)):
            health = read_director_health(pid_path, status_path)
            if health.get("pid") and health.get("state") not in {"stopped", "completed"}:
                messagebox.showinfo(APP_NAME, tr(self.language, "setup_stop_first"))
                return
        arguments = ["--installed-dir", str(BASE_DIR), "--user-data-dir", str(DATA_DIR)]
        game = self.config_data.get("rimworld_path")
        if game:
            try:
                arguments += ["--rimworld-dir", str(validate_game_path(str(game)))]
            except (ValueError, OSError, RuntimeError):
                pass  # Let setup rediscover a moved game from its current metadata.
        executable = BASE_DIR / "RimWorld-Autopilot-Setup.exe"
        try:
            if executable.is_file():
                # The assistant writes Program Files / game Mods. Popen cannot
                # launch its administrator manifest from a non-elevated GUI.
                os.startfile(str(executable), "runas", subprocess.list2cmdline(arguments), str(BASE_DIR))
            elif not getattr(sys, "frozen", False) and (BASE_DIR / "autopilot_setup.py").is_file():
                subprocess.Popen([sys.executable, str(BASE_DIR / "autopilot_setup.py"), *arguments], cwd=BASE_DIR,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            else:
                raise FileNotFoundError(tr(self.language, "setup_missing"))
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"{tr(self.language, 'error')}: {exc}")

    def _refresh_game_folder(self) -> None:
        game = load_config().get("rimworld_path") or ""
        self.config_data["rimworld_path"] = game
        self.game_folder_var.set(str(game) or tr(self.language, "game_folder_unset"))

    def refresh_all(self) -> None:
        self._refresh_game_folder()
        self.refresh_views()
        threading.Thread(target=self._probe_game, daemon=True).start()
        self.after(2000, self.refresh_all)

    def refresh_views(self) -> None:
        health = read_director_health(self.pid_path, self.runtime_status_path)
        state = str(health.get("state") or "stopped")
        status_key = {
            "running": "laya_online",
            "starting": "laya_starting",
            "waiting": "laya_waiting",
            "error": "laya_error",
            "unresponsive": "laya_unresponsive",
        }.get(state, "laya_offline")
        color = COLORS["green"] if state == "running" else COLORS["amber"] if state in {"starting", "waiting"} else COLORS["red"]
        status_text = tr(self.language, status_key)
        self.laya_chip.configure(text=status_text, fg=color)
        if hasattr(self, "model_runtime_label"):
            runtime = health.get("model_runtime") or {}
            actual = str(runtime.get("actual_device") or "")
            runtime_text = tr(self.language, "device_not_loaded")
            if actual and runtime.get("model_loaded"):
                label = tr(self.language, "device_cpu") if actual == "cpu" else f"NVIDIA {runtime.get('gpu_name') or actual}"
                runtime_text = tr(self.language, "device_actual").format(device=label, threads=runtime.get("cpu_threads", "—"))
                reason = runtime.get("fallback_reason")
                if reason and actual == "cpu":
                    runtime_text += "\n" + tr(self.language, "device_fallback").format(reason=tr(self.language, f"device_reason_{reason}"))
            self.model_runtime_label.configure(text=runtime_text)
        observer_health = read_director_health(self.observer_pid_path, self.observer_status_path)
        observer_state = str(observer_health.get("state") or "stopped")
        observer_key = {"running": "observer_online", "waiting": "observer_waiting", "starting": "observer_waiting",
                        "unresponsive": "observer_error", "error": "observer_error"}.get(observer_state, "observer_offline")
        observer_text = tr(self.language, observer_key)
        observer_color = COLORS["green"] if observer_state == "running" else COLORS["amber"] if observer_state in {"waiting", "starting"} else COLORS["muted"]
        self.observer_chip.configure(text=observer_text, fg=observer_color)
        self.observer_status_label.configure(text=observer_text, fg=observer_color)
        try:
            observer_status = json.loads(self.observer_status_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            observer_status = {}
        shot = str(observer_status.get("shot") or "")
        target = str(observer_status.get("target") or "")
        if observer_state == "running" and shot:
            focus = tr(self.language, "observer_focus").format(
                kind=tr(self.language, f"observer_shot_{shot}"), target=target or "—",
                seconds=int(float(observer_status.get("remaining") or 0)),
            )
        else:
            focus = tr(self.language, "observer_no_focus")
        self.observer_focus_label.configure(text=focus)
        self.sidebar_status.configure(text=f"● {status_text}\n● {tr(self.language, 'game_online' if self.game_online else 'game_offline')}\n● {observer_text}")
        if state in {"error", "unresponsive"} and health.get("detail"):
            self.footer.configure(text=str(health["detail"])[:180], fg=COLORS["red"])
        map_state = self._load_map_state()
        self._refresh_doctrine(map_state)
        self._refresh_history()

    def _load_map_state(self) -> dict[str, Any]:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8-sig"))
            maps = state.get("maps") or {}
            current = maps.get(self.active_map_key, {}) if self.active_map_key else {}
            last_seen = current.get("last_seen_tick")
            if (self.active_game_tick is not None and last_seen is not None
                    and self.active_game_tick + 100 < int(last_seen)):
                return {}
            return current
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _refresh_doctrine(self, map_state: dict[str, Any]) -> None:
        doctrine = map_state.get("doctrine") or {}
        audit = map_state.get("doctrine_audit") or {}
        if doctrine:
            labels = doctrine_view(doctrine, self.language)
            course = labels.get("primary_direction", "—")
            details = " · ".join(filter(None, [
                labels.get("economy"), labels.get("technology"), labels.get("military"), labels.get("endgame"),
            ]))
            strategy_text = "\n".join([
                f"{tr(self.language, 'current_course')}: {course}",
                f"{('Экономика' if self.language == 'ru' else 'Economy')}: {labels.get('economy', '—')}",
                f"{('Технологии' if self.language == 'ru' else 'Technology')}: {labels.get('technology', '—')}",
                f"{('Оборона' if self.language == 'ru' else 'Defense')}: {labels.get('military', '—')}",
                f"{('Общество' if self.language == 'ru' else 'Society')}: {labels.get('society', '—')}",
                f"{('Финальная цель' if self.language == 'ru' else 'Long-term objective')}: {labels.get('endgame', '—')}",
            ])
        else:
            course, details, strategy_text = tr(self.language, "no_doctrine"), "", tr(self.language, "no_doctrine")
        self.overview_course.configure(text=course)
        self.overview_course_details.configure(text=details)
        self.strategy_summary.configure(text=strategy_text)

        coverage = audit.get("coverage") or {}
        available = list(audit.get("available_directions") or strategy.DIRECTIONS)
        unavailable = audit.get("unavailable_directions") or {}
        expansions = [name.title() for name, active in (audit.get("expansions") or {}).items() if active]
        self.content_summary.configure(text=", ".join(expansions) or "Core")
        self.content_details.configure(text=f"{coverage.get('available', len(available))}/{coverage.get('total', len(strategy.DIRECTIONS))} · {tr(self.language, 'hidden_directions')}: {len(unavailable)}")
        lines = []
        if available:
            by_domain: dict[str, list[str]] = {}
            for key in available:
                spec = strategy.DIRECTIONS.get(key) or {}
                domain = str(spec.get("domain") or "other")
                by_domain.setdefault(domain, []).append(humanize(key, self.language))
            for domain, names in by_domain.items():
                domain_label = strategy.DOMAIN_LABELS.get(domain, domain) if self.language == "ru" else domain.replace("_", " ").title()
                lines.append(f"{domain_label}\n  • " + "\n  • ".join(names))
        else:
            lines.append(tr(self.language, "no_doctrine"))
        self.direction_catalog.configure(state="normal")
        self.direction_catalog.delete("1.0", "end")
        self.direction_catalog.insert("1.0", "\n\n".join(lines))
        self.direction_catalog.configure(state="disabled")

    def _probe_game(self) -> None:
        map_key = None
        game_tick = None
        try:
            result = request_json(f"{str(self.config_data['api_url']).rstrip('/')}/api/v1/game/state")
            online = bool(result.get("success"))
            if online:
                game_tick = int((result.get("data") or {}).get("game_tick") or 0)
                maps = request_json(f"{str(self.config_data['api_url']).rstrip('/')}/api/v1/maps")
                map_key = active_map_key(maps)
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            online = False
        self.game_online = online
        self.active_map_key = map_key
        self.active_game_tick = game_tick
        self.after(0, lambda: self.game_chip.configure(text=tr(self.language, "game_online" if online else "game_offline"), fg=status_color(online)))

    def _refresh_history(self) -> None:
        try:
            stat = self.log_path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            signature = None
        if signature == self.last_log_signature and self.records:
            return
        self.last_log_signature = signature
        # The director's technical records can contain large map snapshots.
        # Keep the overview responsive; load a wider slice only on History.
        self.records = tail_jsonl(self.log_path, limit=30, max_bytes=4_000_000) if self.current_page == "history" else tail_jsonl(
            self.log_path, limit=1, max_bytes=1_000_000)
        selected = self.tree.selection() if hasattr(self, "tree") else ()
        selected_index = int(selected[0]) if selected else None
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.records):
            decision = row.get("decision") or {}
            result = row.get("result") or {}
            timestamp = str(row.get("timestamp") or "")
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone().strftime("%d.%m %H:%M")
            except ValueError:
                pass
            choice = humanize(decision.get("choice") or row.get("error") or "—", self.language)
            confidence = decision.get("confidence")
            confidence_text = f"{float(confidence) * 100:.0f}%" if confidence is not None else "—"
            done = result.get("applied") is True or (result.get("applied") is None and result.get("success") is True)
            result_text = tr(self.language, "done") if done else tr(self.language, "error") if row.get("error") else tr(self.language, "not_applied")
            self.tree.insert("", "end", iid=str(index), values=(timestamp, choice, confidence_text, result_text))
        if self.records:
            target = str(selected_index if selected_index is not None and selected_index < len(self.records) else len(self.records) - 1)
            self.tree.selection_set(target)
            self.tree.see(target)
            self.show_selected()
            latest = self.records[-1]
            latest_decision = latest.get("decision") or {}
            self.latest_choice.configure(text=humanize(latest_decision.get("choice") or "—", self.language)
                                         if self.active_map_key else tr(self.language, "waiting"))
            confidence = latest_decision.get("confidence")
            suffix = f"{tr(self.language, 'confidence')}: {float(confidence) * 100:.0f}%" if confidence is not None else ""
            self.latest_result.configure(text=suffix)
        else:
            self.latest_choice.configure(text=tr(self.language, "waiting"))
            self.latest_result.configure(text="")

    def show_selected(self, _event=None) -> None:
        if not hasattr(self, "tree"):
            return
        selection = self.tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if not 0 <= index < len(self.records):
            return
        row = self.records[index]
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        if self.tech_var.get():
            self.details.insert("1.0", json.dumps(row, ensure_ascii=False, indent=2, default=str))
        else:
            decision = row.get("decision") or {}
            raw = decision.get("raw") or {}
            answers = raw.get("answers") or {}
            choice = humanize(decision.get("choice") or "—", self.language)
            lines = [tr(self.language, "decision_intro", count=len(row.get("candidates") or []), choice=choice)]
            confidence = decision.get("confidence")
            if confidence is not None:
                lines.append(f"{tr(self.language, 'confidence')}: {float(confidence) * 100:.0f}%")
            visible_state = raw.get("visible_state") or {}
            if visible_state:
                needs = visible_state.get("needs") or {}
                lines.extend(["", tr(self.language, "seen_context") + ":",
                              f"• {tr(self.language, 'seen_food')}: {needs.get('food', '—')}",
                              f"• {tr(self.language, 'seen_hunger')}: {needs.get('least_hunger', '—')}"])
                for risk in (visible_state.get("risks") or [])[:3]:
                    lines.append(f"• {tr(self.language, 'seen_risks')}: {risk_text(str(risk), self.language)}")
            action_answer = answers.get("colony_goal_action") or {}
            probabilities = action_answer.get("probabilities") or {}
            ranked = sorted(probabilities.items(), key=lambda item: float(item[1]), reverse=True)
            if ranked:
                visible = ranked[:12]
                lines.extend(["", tr(self.language, "alternatives") + ":"])
                lines.extend(f"• {humanize(name, self.language)} — {float(probability) * 100:.0f}%" for name, probability in visible)
                if len(ranked) > len(visible):
                    lines.append(f"• {tr(self.language, 'more_options', count=len(ranked) - len(visible))}")
            elif row.get("candidates"):
                candidates = list(row.get("candidates") or [])
                lines.extend(["", tr(self.language, "alternatives") + ":"])
                lines.extend(f"• {humanize(name, self.language)}" for name in candidates[:12])
                if len(candidates) > 12:
                    lines.append(f"• {tr(self.language, 'more_options', count=len(candidates) - 12)}")
            path = []
            for question_id, answer in answers.items():
                if not isinstance(answer, dict) or question_id == "colony_goal_action":
                    continue
                label = QUESTION_TEXT[self.language].get(str(question_id), humanize(question_id, self.language))
                path.append(f"• {label}: {humanize(answer.get('choice'), self.language)}")
            if path:
                lines.extend(["", tr(self.language, "why") + ":", *path])
            result = row.get("result") or {}
            result_text = tr(self.language, "done") if result.get("applied") is True else tr(self.language, "error") if row.get("error") else tr(self.language, "not_applied")
            lines.extend(["", f"{tr(self.language, 'result')}: {result_text}"])
            self.details.insert("1.0", "\n".join(lines))
        self.details.configure(state="disabled")

    def rate_selected_decision(self) -> None:
        selection = self.tree.selection() if hasattr(self, "tree") else ()
        if not selection or not 0 <= int(selection[0]) < len(self.records):
            return
        record = self.records[int(selection[0])]
        candidates = list(record.get("candidates") or [])
        if not candidates or not ((record.get("decision") or {}).get("raw") or {}).get("visible_state"):
            messagebox.showinfo(tr(self.language, "correction_title"), tr(self.language, "correction_unavailable"), parent=self)
            return
        window = tk.Toplevel(self)
        window.title(tr(self.language, "correction_title"))
        window.configure(bg=COLORS["window"])
        window.geometry("620x345")
        window.minsize(500, 300)
        window.transient(self)
        window.grab_set()
        tk.Label(window, text=tr(self.language, "correction_help"), bg=COLORS["window"],
                 fg=COLORS["text"], wraplength=560, justify="left", font=FONTS["body"]).pack(fill="x", padx=22, pady=(22, 14))
        tk.Label(window, text=tr(self.language, "correct_choice"), bg=COLORS["window"],
                 fg=COLORS["cyan"], font=FONTS["heading"]).pack(anchor="w", padx=22)
        labels = {f"{humanize(name, self.language)}  [{name}]": name for name in candidates}
        selected_name = str((record.get("decision") or {}).get("choice") or "")
        default_label = next((label for label, name in labels.items() if name == selected_name), next(iter(labels)))
        selected = tk.StringVar(value=default_label)
        ttk.Combobox(window, textvariable=selected, values=list(labels), state="readonly").pack(fill="x", padx=22, pady=(5, 16))
        tk.Label(window, text=tr(self.language, "correction_note"), bg=COLORS["window"],
                 fg=COLORS["muted"], font=FONTS["body"]).pack(anchor="w", padx=22)
        note = tk.Text(window, height=4, bg=COLORS["panel_alt"], fg=COLORS["text"],
                       insertbackground=COLORS["cyan"], relief="flat", wrap="word", font=FONTS["body"])
        note.pack(fill="both", expand=True, padx=22, pady=(5, 12))

        def save() -> None:
            try:
                append_feedback(FEEDBACK_PATH, record, labels[selected.get()], note.get("1.0", "end").strip())
            except (OSError, ValueError, KeyError) as exc:
                messagebox.showerror(tr(self.language, "correction_title"), str(exc), parent=window)
                return
            window.destroy()
            messagebox.showinfo(tr(self.language, "correction_title"), tr(self.language, "correction_saved"), parent=self)

        ttk.Button(window, text=tr(self.language, "save"), style="Accent.TButton", command=save).pack(anchor="e", padx=22, pady=(0, 18))

    def _animate_mascot(self) -> None:
        elapsed = time.perf_counter() - self.animation_started
        if getattr(self, "mascot_item", None) and self.mascot_canvas.winfo_exists():
            y = 74 + math.sin(elapsed * 1.9) * 3
            self.mascot_canvas.coords(self.mascot_item, 113, y)
            for index, item in enumerate(getattr(self, "orbit_items", [])):
                angle = elapsed * 0.72 + index * math.tau / 3
                x = 112 + math.cos(angle) * 73
                particle_y = 74 + math.sin(angle) * 56
                self.mascot_canvas.coords(item, x - 3, particle_y - 3, x + 3, particle_y + 3)
        self.after(16, self._animate_mascot)

    def _position_hero(self, event: tk.Event) -> None:
        width = max(1, event.width)
        if abs(width - self._hero_render_width) < 2:
            return
        if self._hero_resize_job:
            self.after_cancel(self._hero_resize_job)
        self._hero_resize_job = self.after(35, lambda target=width: self._render_hero(target))

    def _render_hero(self, width: int) -> None:
        self._hero_resize_job = None
        asset = RESOURCE_DIR / "assets" / "gui" / "autopilot-hero.png"
        try:
            self.hero_image = render_photo(asset, (width, 188), cover=True, radius=18)
            if self.hero_art_item is None:
                self.hero_art_item = self.hero_canvas.create_image(0, 0, image=self.hero_image, anchor="nw")
                self.hero_canvas.tag_lower(self.hero_art_item)
            else:
                self.hero_canvas.itemconfigure(self.hero_art_item, image=self.hero_image)
            self._hero_render_width = width
        except (OSError, tk.TclError) as exc:
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                with (self.log_dir / "ui-assets.log").open("a", encoding="utf-8") as handle:
                    handle.write(f"{datetime.now().isoformat()} | {asset} | {exc}\n")
            except OSError:
                pass


def run() -> None:
    ControlCenter().mainloop()
