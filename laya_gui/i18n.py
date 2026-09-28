from __future__ import annotations

from typing import Any

import colony_strategy as strategy
import colony_architect as architect


TEXT = {
    "ru": {
        "app": "RimWorld Autopilot",
        "overview": "Обзор", "strategy": "Стратегия", "priorities": "Приоритеты", "history": "История", "stream": "Эфир", "settings": "Настройки",
        "overview_sub": "Понятная картина того, что происходит с колонией прямо сейчас.",
        "hero_title": "Колония в надёжных руках",
        "hero_subtitle": "Laya наблюдает, выбирает курс и действует локально.",
        "strategy_sub": "Курс развития, выбранный Laya, и доступные альтернативы.",
        "priorities_sub": "Ваши пожелания влияют на выбор модели, но не отменяют безопасность и реальные ограничения игры.",
        "history_sub": "Что Laya видела, какие варианты сравнивала и что произошло.",
        "settings_sub": "Язык, диагностика, обслуживание и экспорт.",
        "stream_sub": "Камера сама показывает главное, пока вы отошли от компьютера.",
        "observer_title": "Режиссёр трансляции", "observer_help": "Независимый режим камеры для Twitch. Laya продолжает руководить колонией; наблюдатель только выбирает кадр и снимает паузу в игре. Работает и после закрытия этого окна.",
        "observer_start": "Включить наблюдателя", "observer_stop": "Выключить", "observer_online": "Наблюдатель работает", "observer_waiting": "Наблюдатель ждёт игру", "observer_offline": "Наблюдатель выключен", "observer_error": "Ошибка наблюдателя",
        "observer_focus": "Сейчас: {kind} · {target} · ещё {seconds} с", "observer_no_focus": "Камера ждёт загруженную колонию.",
        "observer_shot_death": "память о погибшем", "observer_shot_combat": "бой", "observer_shot_raiders": "прибытие врагов", "observer_shot_medical": "здоровье колониста", "observer_shot_idle": "жизнь колонии", "observer_shot_tour": "обзор карты",
        "observer_rules_title": "Как выбирается кадр", "observer_rules": "Сначала погибшие и бой, затем новые враги и раненые. В спокойное время камера меняет колонистов примерно раз в 45 секунд и каждые 10 минут показывает карту издалека. Включённый режим снимает и поставленную вручную паузу — выключите его, если хотите остановить игру.",
        "laya_online": "Laya работает", "laya_offline": "Laya остановлена", "laya_starting": "Laya запускается", "laya_waiting": "Laya ждёт игру", "laya_error": "Ошибка цикла Laya", "laya_unresponsive": "Laya не отвечает", "game_online": "Игра подключена", "game_offline": "Игра не найдена",
        "start": "Запустить Laya", "stop": "Остановить", "pause": "Пауза", "resume": "Продолжить",
        "current_course": "Текущий курс", "latest_choice": "Последнее решение", "waiting": "Жду первое решение Laya…",
        "no_doctrine": "Laya ещё не выбрала долгосрочный курс.", "available_directions": "Доступные направления",
        "expansions": "Активный контент", "hidden_directions": "Скрыто недоступных направлений",
        "save": "Сохранить мои пожелания", "saved": "Пожелания сохранены. Laya увидит их в следующем цикле.", "reset": "Вернуть рекомендуемые значения",
        "personal_note": "Личная корректировка для Laya", "personal_note_hint": "Например: сначала укрепи производство еды, не продавай последнюю медицину и избегай войны до зимы.",
        "safety": "Границы решений", "avoid_attacks": "Не начинать неспровоцированные нападения", "peaceful_trade": "Предпочитать мирную торговлю", "protect_food": "Не тратить аварийный запас еды",
        "technical_logging": "Технический режим журнала", "technical_help": "Добавляет полный снимок состояния для диагностики. Файлы становятся значительно больше.",
        "overlay_title": "HUD Laya в RimWorld", "overlay_help": "Компактный HUD показывает относительные оценки вариантов Laya, а не шанс успеха. Его можно скрыть без остановки Laya.", "overlay_enabled": "Показывать HUD Laya в игре", "overlay_compact": "Компактный HUD", "overlay_saved": "Настройки HUD сохранены.",
        "friendly_mode": "Понятный режим", "technical_mode": "Технический режим", "details": "Контекст и варианты",
        "language": "Язык интерфейса", "installer": "Установка", "run_installer": "Открыть помощник установки", "open_folder": "Открыть папку", "export_history": "Экспортировать историю", "export_bundle": "Экспортировать Autopilot",
        "install_help": "Помощник создаст отдельное окружение Python, установит пакеты и подключит мод к RimWorld.",
        "maintenance": "Управление приложением", "maintenance_help": "Удаление выполняет штатный деинсталлятор Windows. Ваши журналы и настройки в LocalAppData сохраняются для безопасного обновления.", "uninstall": "Удалить Autopilot",
        "ready": "Готово", "running": "работает", "stopped": "остановлена", "check": "проверка…",
        "decision_intro": "Laya рассмотрела {count} вариантов и выбрала: {choice}.", "confidence": "Чёткость выбора", "result": "Результат", "why": "Последовательность выбора",
        "alternatives": "Что рассматривала Laya", "more_options": "и ещё {count} вариантов",
        "correct_decision": "Оценить решение", "correction_title": "Помочь обучить Laya",
        "correction_help": "Выберите лучший вариант из доступных тогда. Это сохранит пример для будущего дообучения, но не изменит модель сразу.",
        "correct_choice": "Лучшее действие", "correction_note": "Почему? (необязательно)",
        "correction_saved": "Оценка сохранена для будущего обучения Laya.",
        "correction_unavailable": "Для этого старого решения не сохранён контекст модели.",
        "seen_context": "Что видела Laya", "seen_food": "Еда", "seen_hunger": "Минимальная сытость", "seen_risks": "Риски",
        "done": "Выполнено", "not_applied": "Пока не выполнено: игровые условия ещё не готовы.", "error": "Произошла ошибка. Подробности доступны в техническом режиме.", "none": "Нет данных",
    },
    "en": {
        "app": "RimWorld Autopilot",
        "overview": "Overview", "strategy": "Strategy", "priorities": "Priorities", "history": "History", "stream": "Stream", "settings": "Settings",
        "overview_sub": "A clear view of what is happening in the colony right now.",
        "hero_title": "Your colony, thoughtfully guided",
        "hero_subtitle": "Laya watches, chooses a course and acts locally.",
        "strategy_sub": "Laya's chosen development course and the alternatives currently available.",
        "priorities_sub": "Your preferences guide the model without bypassing safety or real game constraints.",
        "history_sub": "What Laya saw, which options it compared, and what happened.",
        "settings_sub": "Language, diagnostics, maintenance and export.",
        "stream_sub": "The camera follows the action while you are away.",
        "observer_title": "Stream director", "observer_help": "An independent camera mode for Twitch. Laya still runs the colony; the observer only chooses the shot and unpauses the game. It keeps running when this window closes.",
        "observer_start": "Enable observer", "observer_stop": "Turn off", "observer_online": "Observer running", "observer_waiting": "Observer waiting for game", "observer_offline": "Observer off", "observer_error": "Observer error",
        "observer_focus": "Now: {kind} · {target} · {seconds}s left", "observer_no_focus": "Waiting for a loaded colony.",
        "observer_shot_death": "fallen colonist", "observer_shot_combat": "combat", "observer_shot_raiders": "incoming hostiles", "observer_shot_medical": "colonist health", "observer_shot_idle": "colony life", "observer_shot_tour": "map tour",
        "observer_rules_title": "Shot priorities", "observer_rules": "Deaths and active combat come first, followed by incoming hostiles and injured colonists. In quiet moments, the camera changes colonists about every 45 seconds and tours the map every 10 minutes. While enabled it also resumes manual pauses; turn it off to pause the game yourself.",
        "laya_online": "Laya is running", "laya_offline": "Laya is stopped", "laya_starting": "Laya is starting", "laya_waiting": "Laya is waiting for the game", "laya_error": "Laya cycle error", "laya_unresponsive": "Laya is not responding", "game_online": "Game connected", "game_offline": "Game not found",
        "start": "Start Laya", "stop": "Stop", "pause": "Pause", "resume": "Resume",
        "current_course": "Current course", "latest_choice": "Latest decision", "waiting": "Waiting for Laya's first decision…",
        "no_doctrine": "Laya has not selected a long-term course yet.", "available_directions": "Available directions",
        "expansions": "Active content", "hidden_directions": "Unavailable directions hidden",
        "save": "Save my preferences", "saved": "Preferences saved. Laya will read them on the next cycle.", "reset": "Restore recommended values",
        "personal_note": "Personal guidance for Laya", "personal_note_hint": "For example: secure food production first, keep the last medicine, and avoid war until winter.",
        "safety": "Decision boundaries", "avoid_attacks": "Do not begin unprovoked attacks", "peaceful_trade": "Prefer peaceful trade", "protect_food": "Protect the emergency food reserve",
        "technical_logging": "Technical logging", "technical_help": "Adds a full state snapshot for diagnostics. Log files become much larger.",
        "overlay_title": "Laya HUD in RimWorld", "overlay_help": "The compact HUD shows Laya's relative option weights, not the chance of success. Hide it without stopping Laya.", "overlay_enabled": "Show the Laya HUD in game", "overlay_compact": "Compact HUD", "overlay_saved": "HUD settings saved.",
        "friendly_mode": "Friendly view", "technical_mode": "Technical view", "details": "Context and options",
        "language": "Interface language", "installer": "Installation", "run_installer": "Open setup assistant", "open_folder": "Open folder", "export_history": "Export history", "export_bundle": "Export Autopilot",
        "install_help": "The assistant creates an isolated Python environment, installs packages and connects the mod to RimWorld.",
        "maintenance": "App management", "maintenance_help": "Removal uses the standard Windows uninstaller. Logs and preferences in LocalAppData are kept for safe upgrades.", "uninstall": "Uninstall Autopilot",
        "ready": "Ready", "running": "running", "stopped": "stopped", "check": "checking…",
        "decision_intro": "Laya considered {count} options and chose: {choice}.", "confidence": "Choice clarity", "result": "Result", "why": "Decision path",
        "alternatives": "Options Laya considered", "more_options": "and {count} more options",
        "correct_decision": "Rate decision", "correction_title": "Help train Laya",
        "correction_help": "Choose the best option available at that moment. This saves a future training example; it does not update the model immediately.",
        "correct_choice": "Best action", "correction_note": "Why? (optional)",
        "correction_saved": "Feedback saved for future Laya training.",
        "correction_unavailable": "This older decision has no saved model context.",
        "seen_context": "What Laya saw", "seen_food": "Food", "seen_hunger": "Lowest food need", "seen_risks": "Risks",
        "done": "Completed", "not_applied": "Not completed yet: game conditions are not ready.", "error": "An error occurred. Details are available in technical view.", "none": "No data",
    },
}

RISK_TEXT_RU = {
    "No food and a colonist is close to starvation; delay can kill.": "Еды нет, колонист близок к голодной смерти; задержка опасна.",
    "Untreated bleeding may kill; treatment also takes a worker away from other tasks.": "Кровотечение может убить; лечение временно отвлечёт работника от других дел.",
    "Downed people cannot work or feed themselves.": "Лежачие колонисты не могут работать и есть самостоятельно.",
    "Hostiles can injure or kidnap colonists; combat consumes food and rest.": "Враги могут ранить или похитить людей; бой расходует силы и время.",
    "An injured colony animal may worsen or die without care.": "Раненое домашнее животное может погибнуть без ухода.",
}


def risk_text(value: str, language: str) -> str:
    if language != "ru":
        return value
    if value in RISK_TEXT_RU:
        return RISK_TEXT_RU[value]
    return next((translated for english, translated in RISK_TEXT_RU.items()
                 if len(value) > 20 and english.startswith(value)), value)

PRIORITY_TEXT = {
    "ru": {
        "survival": ("Выживание", "Сон, лечение и срочные угрозы"), "food": ("Еда", "Посевы, готовка и запасы"),
        "construction": ("Строительство", "Помещения, склады и инфраструктура"), "research": ("Исследования", "Новые технологии и верстаки"),
        "economy": ("Экономика", "Производство, продажа и серебро"), "defense": ("Оборона", "Вооружение, укрепления и готовность"),
        "animals": ("Животные", "Лечение, корм, приручение и разведение"), "diplomacy": ("Дипломатия", "Торговля, квесты и отношения"),
    },
    "en": {
        "survival": ("Survival", "Rest, treatment and urgent threats"), "food": ("Food", "Crops, cooking and reserves"),
        "construction": ("Construction", "Rooms, storage and infrastructure"), "research": ("Research", "New technology and workbenches"),
        "economy": ("Economy", "Production, sales and silver"), "defense": ("Defense", "Weapons, fortifications and readiness"),
        "animals": ("Animals", "Care, feed, taming and breeding"), "diplomacy": ("Diplomacy", "Trade, quests and relations"),
    },
}

DIRECTION_EN = {
    "resilient_settlement": "Resilient self-sufficient colony", "agrarian_colony": "Agrarian colony", "ranching_colony": "Ranching colony",
    "medical_sanctuary": "Medical sanctuary", "industrial_manufacturing": "Industrial manufacturing hub", "mining_metallurgy": "Mining and metallurgy",
    "luxury_artisans": "Artisans and luxury", "trade_hub": "Trade and logistics hub", "research_starflight": "Science colony and starship",
    "royal_court": "Imperial court", "tribal_psychic": "Natural psychic tradition", "ideological_community": "Ideological community",
    "dryad_ecology": "Dryad ecology", "archonexus_pilgrimage": "Archonexus pilgrimage", "mechanitor_swarm": "Mechanitor swarm",
    "xenogenetics": "Xenogenetics laboratory", "family_dynasty": "Family dynasty and education", "sanguophage_coven": "Sanguophage community",
    "pollution_adaptation": "Toxic industry", "anomaly_containment": "Anomaly containment facility", "void_ritualists": "Void ritualists",
    "anomaly_mastery": "Monolith mastery", "fortress_state": "Layered fortress", "raider_empire": "Raider expansion",
    "caravan_nomads": "Caravan nomads", "quest_expeditionary": "Expeditionary corps", "gravship_nomads": "Mobile gravship colony",
    "orbital_salvagers": "Orbital salvagers", "fishing_wildlife": "Fishing and specialized wildlife", "mechhive_crusade": "Mechhive campaign",
}

ACTION_EN = {
    "choose_colony_doctrine": "choose a long-term colony course", "advance_doctrine_research": "start doctrine-aligned research",
    "hold_survival": "let the colony finish its current work", "build_freezer": "build a food freezer", "create_stockpile": "create organized storage",
    "expand_stockpile": "expand storage", "create_growing_zone": "plant a food field", "build_sleeping_spots": "make emergency sleeping places",
    "build_basic_beds": "build proper beds", "configure_food_bills": "configure cooking", "prioritize_construction": "prioritize construction",
    "prioritize_growing": "prioritize growing", "prioritize_cooking": "prioritize cooking", "prioritize_research": "prioritize research",
    "plan_architecture": "plan the next building", "designate_safe_hunting": "choose a safe hunting target", "harvest_local_plants": "gather useful wild plants",
    "start_taming": "tame an animal", "prepare_trade_caravan": "prepare a trade caravan", "build_killbox": "build an outer defensive funnel",
    "build_fallback_defense": "build an internal defense line", "build_turret_defense": "build turret defenses", "build_mortar_post": "build a mortar position",
    "advance_research": "start the next research project", "create_food_stockpile": "organize food storage",
    "build_firefoam_defense": "improve fire protection", "care_for_injured_animal": "care for an injured animal",
    "feed_hungry_animal": "feed a hungry animal", "build_animal_spots": "make animal sleeping spots",
    "build_animal_barn": "build an animal shelter", "unforbid_supplies": "allow colonists to collect supplies",
    "unforbid_corpses": "allow colonists to move bodies", "create_human_corpse_dump": "create a remote body disposal area",
    "create_animal_corpse_dump": "store animal carcasses near butchering", "build_cemetery": "create a cemetery",
    "build_crematorium": "set up cremation", "prioritize_burial": "remove exposed bodies",
    "build_starter_base": "build a basic shelter", "build_power": "build a reliable power supply",
    "build_hitech_lab": "build a high-tech laboratory", "build_fabrication": "build component production",
    "build_ship": "begin constructing the escape ship", "develop_colonist_skill": "develop a colonist's skill",
    "optimize_night_owl_schedule": "adjust a night owl's schedule", "prioritize_armament": "improve weapons and armor",
    "process_mechanoids": "dismantle mechanoid remains", "build_prison": "build a prison", "build_hospital": "build a hospital",
    "build_temple": "build a temple", "improve_room_lighting": "improve room lighting", "floor_critical_room": "install a clean floor in a critical room",
    "build_pathways": "build efficient walkways", "install_sculpture": "place a sculpture", "commission_sculptures": "commission sculptures",
    "prioritize_cleaning": "clean critical rooms", "prioritize_hauling": "move urgent supplies", "prioritize_doctor": "prioritize medical care",
    "prioritize_rescue": "rescue a downed person", "prioritize_firefighting": "fight an active fire", "prioritize_handling": "prioritize animal handling",
    "prioritize_hunting": "prioritize hunting", "prioritize_plant_cutting": "prioritize plant cutting", "start_stonecutting": "cut stone into blocks",
    "create_stone_chunk_dump": "create a stone chunk stockpile", "build_private_bedroom": "build a private bedroom",
    "build_table": "build a dining table", "build_weapon_shelves": "store weapons on shelves", "configure_hospital_beds": "configure hospital beds",
    "build_income_infrastructure": "build income-producing facilities", "configure_income_production": "configure profitable production",
    "prepare_ancient_danger": "prepare for an ancient danger", "open_ancient_danger": "open the ancient danger",
    "prepare_rescue_mission": "prepare a rescue mission", "plan_human_reproduction": "plan family growth", "hold_and_observe": "wait and observe safely",
    "build_passive_cooler": "cool an occupied bedroom", "build_room_campfire": "warm a bedroom with a campfire",
    "build_room_heater": "install a wired electric heater", "connect_room_heater_power": "connect the bedroom heater",
    "prioritize_thermal_project": "finish urgent temperature control",
}

ACTION_RU = {
    "build_passive_cooler": "охладить жилую комнату", "build_room_campfire": "согреть спальню костром",
    "build_room_heater": "установить обогреватель с проводкой", "connect_room_heater_power": "подключить обогреватель",
    "prioritize_thermal_project": "достроить отопление или охлаждение",
    "choose_colony_doctrine": "выбрать долгосрочный курс колонии", "advance_doctrine_research": "начать исследование по курсу",
    "advance_research": "начать следующее исследование", "hold_survival": "дать колонии закончить текущую работу",
    "build_freezer": "построить холодильник для еды", "create_stockpile": "организовать общий склад", "expand_stockpile": "расширить склад",
    "create_food_stockpile": "организовать склад еды", "create_growing_zone": "посадить продовольственное поле",
    "build_sleeping_spots": "сделать временные места для сна", "build_basic_beds": "построить нормальные кровати",
    "configure_food_bills": "настроить приготовление еды", "prioritize_construction": "ускорить строительство",
    "prioritize_growing": "ускорить посевы и сбор урожая", "prioritize_cooking": "ускорить готовку", "prioritize_research": "ускорить исследования",
    "plan_architecture": "спланировать следующее здание", "designate_safe_hunting": "выбрать безопасную цель охоты",
    "harvest_local_plants": "собрать полезные дикорастущие растения", "start_taming": "приручить животное",
    "prepare_trade_caravan": "подготовить торговый караван", "build_killbox": "построить внешний защитный коридор",
    "build_fallback_defense": "построить внутреннюю линию обороны", "build_turret_defense": "построить турельную защиту",
    "build_mortar_post": "построить миномётную позицию", "build_firefoam_defense": "усилить противопожарную защиту",
    "care_for_injured_animal": "оказать помощь раненому животному", "feed_hungry_animal": "накормить голодное животное",
    "build_animal_spots": "сделать лежанки для животных", "build_animal_barn": "построить дом для животных",
    "unforbid_supplies": "разрешить перенос припасов", "unforbid_corpses": "разрешить перенос трупов",
    "create_human_corpse_dump": "создать удалённую свалку трупов", "create_animal_corpse_dump": "создать склад туш у разделочной",
    "build_cemetery": "создать кладбище", "build_crematorium": "организовать кремацию", "prioritize_burial": "убрать трупы",
    "build_starter_base": "построить базовое убежище", "build_power": "построить электросеть", "build_hitech_lab": "построить современную лабораторию",
    "build_fabrication": "построить производство компонентов", "build_ship": "начать строительство корабля",
    "develop_colonist_skill": "развивать навык колониста", "optimize_night_owl_schedule": "настроить режим ночной совы",
    "prioritize_armament": "улучшить оружие и броню", "process_mechanoids": "разобрать останки механоидов",
    "build_prison": "построить тюрьму", "build_hospital": "построить больницу", "build_temple": "построить храм",
    "improve_room_lighting": "улучшить освещение", "floor_critical_room": "сделать чистый пол в важной комнате",
    "build_pathways": "проложить удобные дорожки", "install_sculpture": "установить скульптуру", "commission_sculptures": "заказать скульптуры",
    "prioritize_cleaning": "убрать важные помещения", "prioritize_hauling": "перенести срочные припасы", "prioritize_doctor": "дать приоритет лечению",
    "prioritize_rescue": "спасти упавшего человека", "prioritize_firefighting": "потушить пожар", "prioritize_handling": "заняться животными",
    "prioritize_hunting": "ускорить охоту", "prioritize_plant_cutting": "ускорить вырубку и сбор", "start_stonecutting": "обтесать камни в блоки",
    "create_stone_chunk_dump": "создать склад каменных глыб", "build_private_bedroom": "построить отдельную спальню",
    "build_table": "построить обеденный стол", "build_weapon_shelves": "разместить оружие на полках", "configure_hospital_beds": "настроить больничные койки",
    "build_income_infrastructure": "построить производство для заработка", "configure_income_production": "настроить прибыльное производство",
    "prepare_ancient_danger": "подготовиться к древней опасности", "open_ancient_danger": "вскрыть древнюю опасность",
    "prepare_rescue_mission": "подготовить спасательную экспедицию", "plan_human_reproduction": "спланировать развитие семьи", "hold_and_observe": "безопасно подождать и наблюдать",
}

ACTION_EN.update({
    "breed_animals": "plan animal breeding", "excavate_mountain_bedroom": "excavate a mountain bedroom", "finish_mountain_bedroom": "finish a mountain bedroom",
    "income_art": "earn silver from sculptures", "income_biofuel": "earn silver from chemfuel", "income_brewing": "earn silver from beer",
    "income_crops": "earn silver from surplus crops", "income_drugs": "earn silver from psychite products", "income_livestock": "earn silver from animals and their products",
    "income_mining": "earn silver from valuable minerals", "income_orbital": "develop orbital trade", "income_organs": "earn silver from prisoner organs",
    "income_tailoring": "earn silver from clothing", "income_travel_food": "earn silver from travel food", "leave_wildlife_alone": "leave wildlife alone",
    "pause_late_sowing": "pause crops that cannot mature in time", "prioritize_construction_project": "prioritize a specific construction project",
    "resume_seasonal_sowing": "resume viable seasonal planting", "upgrade_workbench": "build the next workbench upgrade",
    "hold_cover": "hold strong cover", "focus_fire": "concentrate fire", "firing_line": "form a safe firing line", "spread_out": "spread out against explosives",
    "kite": "kite slow melee enemies", "staggered_retreat": "make a staggered retreat", "melee_block": "hold a three-on-one melee block",
    "door_defense": "defend a doorway", "killbox_hold": "hold the prepared kill zone", "fallback_line": "withdraw to internal defenses",
    "wide_flank": "make a wide flanking move", "pincer": "form a two-sided pincer", "counter_snipe": "counter-snipe",
    "rush_ranged": "rush isolated ranged enemies", "emp_control": "control mechanoids with EMP", "smoke_advance": "advance under smoke",
    "siege_harass": "harass the siege and withdraw", "mortar_counterbattery": "fire a mortar counter-battery", "drop_pod_encircle": "encircle drop pods",
    "infestation_choke": "contain insects at a chokepoint", "infestation_burn": "use a controlled infestation burn", "cluster_poke": "wake a mech cluster from range",
    "intercept_kidnapper": "intercept a kidnapper", "covered_rescue": "rescue under covering fire", "fire_retreat": "retreat from fire and heat", "civilian_retreat": "withdraw unarmed civilians",
    "psycast_control": "use a control psycast", "psycast_support": "use a support psycast", "stand_down": "stand down after combat",
    "prepare_undrafted": "prepare without exhausting drafted colonists", "preemptive_strike": "launch a coordinated preemptive strike",
    "engage_ranged": "engage with ranged fighters", "engage_melee": "engage with melee fighters", "draft_best_defender": "draft the healthiest defenders",
    "remain_drafted": "remain drafted", "keep_current_plan": "keep the current plan", "equip_ranged_weapon": "equip ranged weapons",
    "equip_melee_weapon": "equip melee weapons", "equip_emp_weapon": "equip EMP weapons", "focus_mechanoids": "focus fire on mechanoids", "focus_insects": "focus fire on insects",
})

ACTION_RU.update({
    "breed_animals": "спланировать разведение животных", "excavate_mountain_bedroom": "вырубить спальню в скале", "finish_mountain_bedroom": "обставить спальню в скале",
    "income_art": "зарабатывать на скульптурах", "income_biofuel": "зарабатывать на химтопливе", "income_brewing": "зарабатывать на пиве",
    "income_crops": "продавать излишки урожая", "income_drugs": "зарабатывать на психоидных продуктах", "income_livestock": "зарабатывать на животных и их продуктах",
    "income_mining": "зарабатывать на ценных ископаемых", "income_orbital": "развивать орбитальную торговлю", "income_organs": "зарабатывать на органах пленных",
    "income_tailoring": "зарабатывать на одежде", "income_travel_food": "зарабатывать на дорожной еде", "leave_wildlife_alone": "не трогать диких животных",
    "pause_late_sowing": "остановить посевы, которые не успеют созреть", "prioritize_construction_project": "ускорить конкретную постройку",
    "resume_seasonal_sowing": "возобновить подходящие сезонные посевы", "upgrade_workbench": "построить улучшенный верстак",
    "hold_cover": "держать надёжное укрытие", "focus_fire": "сосредоточить огонь", "firing_line": "построить безопасную линию огня", "spread_out": "рассредоточиться против взрывов",
    "kite": "выманивать медленных врагов", "staggered_retreat": "отступать поочерёдно", "melee_block": "удерживать узкий проход бойцами ближнего боя",
    "door_defense": "защищать дверной проём", "killbox_hold": "удерживать подготовленный защитный коридор", "fallback_line": "отойти к внутренней обороне",
    "wide_flank": "совершить широкий обход", "pincer": "атаковать с двух сторон", "counter_snipe": "вести контрснайперский огонь",
    "rush_ranged": "сблизиться со стрелками противника", "emp_control": "оглушать механоидов ЭМИ-оружием", "smoke_advance": "наступать под дымовой завесой",
    "siege_harass": "обстреливать осаду и отходить", "mortar_counterbattery": "вести ответный миномётный огонь", "drop_pod_encircle": "окружить десантные капсулы",
    "infestation_choke": "сдерживать насекомых в узком проходе", "infestation_burn": "контролируемо выжечь заражение", "cluster_poke": "разбудить кластер механоидов издалека",
    "intercept_kidnapper": "перехватить похитителя", "covered_rescue": "спасти раненого под прикрытием", "fire_retreat": "отступить от огня и жара", "civilian_retreat": "отвести безоружных жителей",
    "psycast_control": "применить сдерживающую псионику", "psycast_support": "применить поддерживающую псионику", "stand_down": "снять боевую готовность",
    "prepare_undrafted": "готовиться, не изматывая мобилизованных колонистов", "preemptive_strike": "провести согласованную упреждающую атаку",
    "engage_ranged": "вступить в бой стрелками", "engage_melee": "вступить в ближний бой", "draft_best_defender": "мобилизовать самых здоровых защитников",
    "remain_drafted": "сохранить боевую готовность", "keep_current_plan": "не менять текущий план", "equip_ranged_weapon": "выдать стрелковое оружие",
    "equip_melee_weapon": "выдать оружие ближнего боя", "equip_emp_weapon": "выдать ЭМИ-оружие", "focus_mechanoids": "сосредоточить огонь на механоидах", "focus_insects": "сосредоточить огонь на насекомых",
})


OPTION_EN = {
    "survival": "Survival and resilience", "prosperity": "Production and wealth", "technology": "Science and transformation",
    "society": "Society, beliefs and legacy", "power": "Military and political power", "exploration": "Exploration and mobility", "endgame": "Long-term victory",
    "food_crops": "Farming and food processing", "animals": "Animals and animal products", "manufacturing": "Crafting and industry",
    "extraction": "Resource extraction", "commerce": "Trade and services", "biotech": "Biotechnology", "anomaly": "Anomaly industry", "salvage_raiding": "Salvage and expeditions",
    "crops": "Durable crop surplus", "drugs": "Psychite and drugs", "brewing": "Hops and beer", "travel_food": "Pemmican and travel meals",
    "livestock": "Animals, milk, wool, eggs and leather", "biofuel": "Boomalopes and chemfuel", "tailoring": "Clothing", "art": "Sculptures",
    "stoneblocks": "Stone blocks", "weapons": "Weapons", "armor": "Armor", "components": "Components", "mining": "Ore, deep drilling and scanners",
    "caravan_trade": "Caravan trade", "orbital": "Orbital trade", "quest_rewards": "Quests and rewards", "genes": "Genes and xenogerms",
    "mechanoids": "Mechanoids and subcores", "organs": "Prisoner organs, with ethical consequences", "bioferrite": "Bioferrite and entity containment",
    "anomaly_arms": "Anomaly serums and weapons", "raiding": "Settlement raids", "salvage": "Ruins and quest sites", "orbital_salvage": "Orbital salvage",
    "starflight": "Starship construction", "industrial": "Industry and components", "agriculture": "Agriculture and food", "medical": "Medicine and prosthetics",
    "military": "Weapons and defense", "energy": "Power and climate control", "trade_logistics": "Communications, transport and logistics", "psycasting": "Psycasting",
    "royal_permits": "Imperial technology and permits", "transhumanism": "Biosculpting and neural enhancement", "mechanitor": "Mechanitors and mechs",
    "genetics": "Genetics", "pollution": "Waste and pollution", "containment": "Entity containment and study", "void_research": "Void technology",
    "gravtech": "Gravtech and flight", "orbital_life_support": "Vacuum and life support",
    "fortified_depth": "Layered fortress", "mobile_response": "Mobile reserve", "ranged_firepower": "Long-range firepower", "melee_chokepoints": "Melee chokepoints",
    "turret_mortar": "Turrets and mortars", "peaceful_deterrence": "Minimal defense and deterrence", "psychic_force": "Psychic support",
    "mechanized_force": "Combat mechs", "anomaly_weapons": "Entities and Void technology", "gravship_security": "Mobile ship security",
    "pragmatic": "Pragmatic community", "egalitarian": "Egalitarian community", "hierarchical": "Specialized hierarchy", "royal": "Imperial court",
    "ideological": "Follow the colony's ideology", "family": "Family and child education", "transhumanist": "Transhumanism", "xenodiverse": "Xenotype diversity",
    "sanguophage": "Sanguophage community", "anomaly_scholars": "Anomaly scholars", "nomadic_crew": "Mobile gravship crew",
    "enduring_colony": "An enduring prosperous colony", "ship_escape": "Build and launch a starship", "imperial_ascension": "Leave with the Imperial high stellarch",
    "archonexus": "Reach the Archonexus", "anomaly_void": "Resolve the monolith and machine god", "mechhive": "Mechhive orbital campaign",
    "peaceful_trade": "Peaceful trade", "alliance_builder": "Alliances and goodwill", "quest_contractors": "Rewarded quest work", "humanitarian": "Rescue and assistance",
    "defensive": "Defense without unnecessary wars", "isolationist": "Minimal outside contact", "expansionist": "Active expeditions and military pressure", "raider": "Systematic raiding",
    "compact": "Compact connected base", "separate_houses": "Separate homes", "courtyard": "Courtyard settlement", "tribal_village": "Low-tech village",
    "industrial_complex": "Industrial complex", "noble_estate": "Noble estate", "ideological_commune": "Ideological temple community",
    "mechanitor_hub": "Automated mechanitor hub", "containment_facility": "Containment research complex", "gravship": "Mobile gravship", "mountain": "Mountain base",
    "shared_first": "Dining and recreation rooms first", "bedrooms_first": "Bedrooms first", "hospital_work_first": "Hospital and work rooms first", "balanced": "Improve the weakest important room",
    "food_agriculture": "Food, farming and cooking", "animal_husbandry": "Animal husbandry and products", "construction_architecture": "Construction and architecture",
    "mining_metallurgy": "Mining, stone and metallurgy", "craft_industry": "Crafting, tailoring and industry", "research_technology": "Research and high technology",
    "medicine_biotech": "Medicine, surgery and biotechnology", "trade_diplomacy": "Trade, diplomacy and prisoner relations", "art_culture": "Art, beauty and culture",
    "security_hunting": "Security, hunting and layered defense", "colony_services": "Logistics, cleaning and colony services",
    "raw_food": "Raw food", "precious": "Gold, silver and jade", "beer": "Beer", "prisoners": "Prisoners",
}

OPTION_RU = {
    **strategy.DOMAIN_LABELS,
    **{key: str(data["label"]) for key, data in strategy.ECONOMY_FAMILIES.items()},
    **{key: str(label) for data in strategy.ECONOMY_FAMILIES.values() for key, label in data["products"].items()},
    **{key: str(value[0]) for source in (strategy.TECHNOLOGY, strategy.DEFENSE, strategy.SOCIETY, strategy.ENDGAMES, strategy.SETTLEMENTS) for key, value in source.items()},
    **strategy.DIPLOMACY,
    **strategy.BEAUTY,
    "mountain": "Горная база",
    "food_agriculture": "Еда, земледелие и готовка", "animal_husbandry": "Животноводство и продукты животных",
    "construction_architecture": "Строительство и архитектура", "mining_metallurgy": "Добыча, камень и металлургия",
    "craft_industry": "Ремесло, пошив и промышленность", "research_technology": "Исследования и высокие технологии",
    "medicine_biotech": "Медицина, хирургия и биотехнологии", "trade_diplomacy": "Торговля, дипломатия и работа с пленными",
    "art_culture": "Искусство, красота и культура", "security_hunting": "Безопасность, охота и эшелонированная оборона",
    "colony_services": "Логистика, уборка и обслуживание колонии",
    "raw_food": "Сырая еда", "precious": "Золото, серебро и нефрит", "beer": "Пиво", "prisoners": "Пленные",
}

QUESTION_TEXT = {
    "ru": {"colony_goal_action": "Следующее действие", "colony_goal_domain": "Область следующей задачи", "colony_goal_family": "Группа задач", "doctrine_domain": "Область развития", "doctrine_primary_direction": "Основной курс", "doctrine_economy_family": "Тип экономики", "doctrine_economy_product": "Продукт или доход", "doctrine_technology": "Технологический приоритет", "doctrine_military": "Оборонная доктрина", "doctrine_society": "Устройство общества", "doctrine_endgame": "Долгосрочная цель", "doctrine_diplomacy": "Внешняя политика", "doctrine_settlement_form": "Форма поселения", "doctrine_material": "Материал", "doctrine_beauty": "Красота помещений", "doctrine_specialization": "Специализация колонистов", "hunt_target": "Цель охоты", "tame_target": "Животное для приручения", "wild_plant_type": "Растение для сбора", "worker_pawn": "Исполнитель", "construction_project": "Строительный проект", "architecture_program": "Назначение здания", "architecture_material": "Материал здания", "architecture_entry": "Сторона входа", "architecture_house_style": "Стиль дома", "architecture_variant": "Вариант планировки", "doctrine_research_target": "Следующее исследование", "lighting_room": "Помещение для освещения", "skill_training_plan": "План обучения", "night_owl_pawn": "Колонист с ночным режимом", "workbench_upgrade": "Улучшение верстака", "trade_purchase_plan": "Что купить в поездке", "stone_type": "Тип камня", "critical_floor_plan": "Помещение и покрытие пола", "path_material": "Материал дорожки", "sculpture_install_plan": "Скульптура и помещение", "animal_barn_material": "Материал дома животных", "animal_barn_floor": "Пол дома животных", "temple_altar": "Ритуальный объект", "temple_material": "Материал храма"},
    "en": {"colony_goal_action": "Next action", "colony_goal_domain": "Next task domain", "colony_goal_family": "Task family", "doctrine_domain": "Development domain", "doctrine_primary_direction": "Primary course", "doctrine_economy_family": "Economy family", "doctrine_economy_product": "Product or income", "doctrine_technology": "Technology focus", "doctrine_military": "Defense doctrine", "doctrine_society": "Social organization", "doctrine_endgame": "Long-term objective", "doctrine_diplomacy": "Foreign policy", "doctrine_settlement_form": "Settlement form", "doctrine_material": "Material", "doctrine_beauty": "Room beauty", "doctrine_specialization": "Colonist specialization", "hunt_target": "Hunting target", "tame_target": "Animal to tame", "wild_plant_type": "Plant to gather", "worker_pawn": "Assigned colonist", "construction_project": "Construction project", "architecture_program": "Building purpose", "architecture_material": "Building material", "architecture_entry": "Entrance side", "architecture_house_style": "House style", "architecture_variant": "Layout variant", "doctrine_research_target": "Next research", "lighting_room": "Room to light", "skill_training_plan": "Training plan", "night_owl_pawn": "Night Owl colonist", "workbench_upgrade": "Workbench upgrade", "trade_purchase_plan": "Purchase priority", "stone_type": "Stone type", "critical_floor_plan": "Room and flooring", "path_material": "Path material", "sculpture_install_plan": "Sculpture and room", "animal_barn_material": "Animal shelter material", "animal_barn_floor": "Animal shelter floor", "temple_altar": "Ritual focus", "temple_material": "Temple material"},
}

ARCHITECTURE_RU = {
    "residence": "Отдельный дом", "residential_compound": "Жилой комплекс",
    "dining_recreation": "Столовая и отдых", "kitchen": "Кухня", "freezer": "Холодильник",
    "hospital": "Больница", "throne_room": "Тронный зал", "temple": "Храм",
    "workshop": "Мастерская", "factory": "Фабрика", "research_lab": "Лаборатория",
    "storage": "Склад", "prison": "Тюрьма", "barn": "Дом для животных",
    "nursery": "Детская и школа", "defense": "Оборонительные сооружения",
    "power_utility": "Энергетический блок",
}
HOUSE_STYLE_RU = {
    "compact": "небольшой", "comfort": "уютный", "garden": "с растениями",
    "artisan": "украшенный", "couple": "для пары", "family": "семейный",
}
HOUSE_STYLE_EN = {
    "compact": "compact", "comfort": "comfortable", "garden": "garden",
    "artisan": "decorated", "couple": "couple's", "family": "family",
}
BUILDING_CHOICE_LABELS = {
    "ru": {"north": "Северный вход", "east": "Восточный вход", "south": "Южный вход",
           "west": "Западный вход", "WoodLog": "Дерево", "BlocksGranite": "Гранит",
           "BlocksLimestone": "Известняк", "BlocksSandstone": "Песчаник",
           "BlocksSlate": "Сланец", "BlocksMarble": "Мрамор", "Steel": "Сталь",
           "Plasteel": "Пласталь", "Uranium": "Уран"},
    "en": {"north": "North entrance", "east": "East entrance", "south": "South entrance",
           "west": "West entrance", "WoodLog": "Wood", "BlocksGranite": "Granite",
           "BlocksLimestone": "Limestone", "BlocksSandstone": "Sandstone",
           "BlocksSlate": "Slate", "BlocksMarble": "Marble", "Steel": "Steel",
           "Plasteel": "Plasteel", "Uranium": "Uranium"},
}


def tr(language: str, key: str, **values: Any) -> str:
    text = TEXT.get(language, TEXT["ru"]).get(key, TEXT["en"].get(key, key))
    return text.format(**values) if values else text


def humanize(value: Any, language: str = "ru") -> str:
    key = str(value or "")
    if key in BUILDING_CHOICE_LABELS[language]:
        return BUILDING_CHOICE_LABELS[language][key]
    if key.startswith("house_"):
        style, _, number = key.removeprefix("house_").rpartition("_")
        if style in HOUSE_STYLE_RU and number.isdigit():
            return (f"{HOUSE_STYLE_RU[style].capitalize()} дом · вариант {number}" if language == "ru"
                    else f"{HOUSE_STYLE_EN[style].capitalize()} house · option {number}")
    if key in architect.PROGRAM_CATALOG:
        return ARCHITECTURE_RU.get(key, key) if language == "ru" else str(architect.PROGRAM_CATALOG[key]["label"]).capitalize()
    for program in architect.PROGRAM_CATALOG:
        if key.startswith(f"{program}_") and key.removeprefix(f"{program}_").isdigit():
            number = key.removeprefix(f"{program}_")
            label = ARCHITECTURE_RU.get(program, program) if language == "ru" else str(architect.PROGRAM_CATALOG[program]["label"]).capitalize()
            return f"{label} · {'вариант' if language == 'ru' else 'option'} {number}"
    if key.startswith("trade_to:"):
        parts = key.split(":", 2)
        destination = f"поселение №{parts[1]}" if language == "ru" else f"settlement #{parts[1]}"
        goods = humanize(parts[2], language) if len(parts) > 2 else ""
        return ("торговая поездка" if language == "ru" else "trade journey") + f" · {destination}" + (f" · {goods}" if goods else "")
    if key.startswith("raid_to:"):
        destination = key.split(":", 1)[1]
        return f"нападение на поселение №{destination}" if language == "ru" else f"raid settlement #{destination}"
    if key.startswith("prisoner_policy:"):
        parts = key.split(":", 2)
        policies = {
            "ru": {"recruit": "вербовать", "release": "освободить", "sell": "продать", "organs_nonlethal": "изъять органы без намеренного убийства", "organs_lethal": "провести смертельное изъятие органа"},
            "en": {"recruit": "recruit", "release": "release", "sell": "sell", "organs_nonlethal": "remove nonlethal organs", "organs_lethal": "perform lethal organ removal"},
        }
        policy_key = parts[2] if len(parts) > 2 else ""
        fallback = "решить судьбу" if language == "ru" else "decide their future"
        policy = policies[language].get(policy_key, fallback)
        return f"пленный №{parts[1]}: {policy}" if language == "ru" else f"prisoner #{parts[1]}: {policy}"
    if key.startswith("human_reproduction:"):
        approach = key.rsplit(":", 1)[-1]
        labels = {
            "TryForBaby": ("попытаться завести ребёнка", "try for a baby"),
            "Normal": ("обычное планирование семьи", "normal family planning"),
            "AvoidPregnancy": ("избегать беременности", "avoid pregnancy"),
        }
        return labels.get(approach, ("планирование семьи", "family planning"))[0 if language == "ru" else 1]
    if key.startswith("breed_animals:"):
        species = key.split(":", 1)[1]
        return f"разводить животных: {species}" if language == "ru" else f"breed animals: {species}"
    if key in strategy.DIRECTIONS:
        return str(strategy.DIRECTIONS[key]["label"]) if language == "ru" else DIRECTION_EN.get(key, key.replace("_", " ").title())
    option_text = OPTION_RU if language == "ru" else OPTION_EN
    if key in option_text:
        return option_text[key]
    if language == "en" and key in ACTION_EN:
        return ACTION_EN[key]
    if language == "ru":
        return ACTION_RU.get(key, key.replace("_", " ").replace(":", " → "))
    return key.replace("_", " ").replace(":", " → ").strip().title()


def doctrine_view(doctrine: dict[str, Any], language: str) -> dict[str, str]:
    if language == "ru":
        labels = doctrine.get("labels") or strategy.doctrine_labels(doctrine)
        return {str(k): str(v) for k, v in labels.items()}
    return {
        "domain": str(doctrine.get("domain") or "—").replace("_", " ").title(),
        "primary_direction": DIRECTION_EN.get(str(doctrine.get("primary_direction")), humanize(doctrine.get("primary_direction"), "en")),
        "settlement_form": humanize(doctrine.get("settlement_form"), "en"),
        "economy": humanize(doctrine.get("economy_product") or doctrine.get("economy"), "en"),
        "technology": humanize(doctrine.get("technology"), "en"), "military": humanize(doctrine.get("military"), "en"),
        "society": humanize(doctrine.get("society"), "en"), "endgame": humanize(doctrine.get("endgame"), "en"),
        "diplomacy": humanize(doctrine.get("diplomacy"), "en"),
    }
