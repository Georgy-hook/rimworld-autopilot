from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
import traceback
from collections import Counter, deque
from pathlib import Path
from typing import Any

import rimworld_laya as bridge
import colony_architect as architect
import colony_professions as professions
import colony_events as events
import colony_growth as growth
import colony_strategy as strategy
import laya_preferences
from laya_decisions import ask_laya_choice


RESEARCH_ROUTE = [
    "Electricity",
    "Batteries",
    "MicroelectronicsBasics",
    "MultiAnalyzer",
    "Fabrication",
    "AdvancedFabrication",
    "ShipBasics",
    "ShipCryptosleep",
    "ShipReactor",
    "ShipEngine",
    "ShipComputerCore",
    "ShipSensorCluster",
]

PATIENT_FEED_RETRY_TICKS = 12000

ACTION_DESCRIPTIONS = {
    "plan_architecture": "Choose a needed building program first, then let Laya select one procedurally generated, resource- and technology-aware layout. Housing alone provides 24 varied designs without storing 24 rigid blueprints.",
    "build_catalog_building": "Choose any currently unlocked and affordable building from RimWorld's live catalog, including DLC and modded definitions. Laya selects its category, exact building and compatible material; the game checks the site before an order is placed.",
    "build_research_bench": "Build the first affordable research bench so the colony can start research. Choose a compatible material from current stock; the game validates the site before placing its blueprint.",
    "improve_room_lighting": "Add a real light source to one dark high-value room selected by Laya; work rooms and hospital treatment should not operate in darkness.",
    "develop_colonist_skill": "Choose a colonist, skill and matching live WorkType using current level, small/large passion flames, learning traits, health and the colony's strategic gaps.",
    "optimize_night_owl_schedule": "Move one Night Owl colonist's sleep to 11:00-18:59 and leave the night flexible for work and recreation.",
    "schedule_recreation": "Give one stressed, recreation-starved colonist two protected Joy hours each day. This costs work time but can prevent an early mental break even before new furniture is ready.",
    "build_recreation_pin": "Build a ten-wood horseshoes pin near the shelter to add a different kind of recreation. It competes with urgent beds and walls for scarce wood.",
    "upgrade_workbench": "Build an unlocked successor workbench beside the old one; keep the old bench until the upgrade is completed so production never disappears mid-transition.",
    "unforbid_supplies": "Remove the red forbidden marks from landed supplies so colonists can eat, equip and haul them.",
    "equip_colonists": "Equip unarmed colonists with real nearby ranged weapons before a raid; otherwise even a small animal can close to melee range.",
    "rescue_downed_colonist": "Send a mobile colonist to carry a downed ally to a completed bed; bleeding and starvation can kill while the colony waits.",
    "rescue_neutral_arrival": "Carry a downed non-hostile visitor to a completed bed. They may later ask to join, but rescue is not guaranteed recruitment; food, care and labor are costs.",
    "tend_colonist": "Send an available doctor directly to an injured colonist with an untreated wound or active bleeding, even when no bed exists.",
    "create_food_stockpile": "Place a temporary food-only stockpile near, but outside, the first bedroom; a proper freezer can replace it later.",
    "build_sleeping_spots": "Place free sleeping spots for colonists, using an empty roofed room when one is available; these cannot waste scarce materials in botched attempts.",
    "build_basic_beds": "Build a real bed inside an already completed roofed room. Outdoor sleeping spots are temporary; an outdoor bed wastes material and still leaves the sleeper exposed.",
    "build_campfire": "Build a 20-wood campfire near the house for immediate cooking. It burns out after a few days and is not a permanent clean kitchen.",
    "assign_real_bed": "Move a colonist sleeping outdoors or on a ground spot into an available completed indoor bed; this interrupts the current sleep but gives them a sheltered bed thereafter.",
    "prepare_emergency_medical_bed": "Mark a completed real bed for medical use now, so the wounded can rest properly without waiting for a new hospital.",
    "build_animal_spots": "Place free animal sleeping spots so injured colony animals can rest and receive treatment.",
    "care_for_injured_animal": "Send the best available doctor to the most seriously injured colony animal and assign animal bed rest.",
    "feed_hungry_animal": "Immediately feed the hungriest resting colony animal before starvation becomes critical.",
    "feed_hungry_colonist": "Immediately feed the hungriest downed colonist who cannot walk to available food.",
    "eat_available_meal": "Send a mobile hungry colonist to eat an actual unlocked meal now. Other work can wait; delay risks malnutrition even when the colony owns food.",
    "create_nearby_food_cache": "Make a high-priority meal stockpile at the settlement because all available meals are far away; a hauler must then bring food within easy walking distance.",
    "open_sealed_food_store": "Meals are trapped inside a legacy freezer built without a door. Send a builder to deconstruct one exact wall tile; this restores food access without destroying the room.",
    "open_blocked_food_path": "A colonist is sealed behind walls or has repeatedly failed to reach food. Open one adjacent built wall before another meal order; leaving the pawn trapped can be fatal.",
    "finish_freezer_entrance": "Install a normal door in the repaired freezer entrance once the blocking wall is gone, preserving access and cooling.",
    "build_cemetery": "Create a real graveyard outside the living and food areas so human corpses can be buried normally.",
    "create_human_corpse_dump": "Create a critical-priority human-corpse dumping stockpile far outside colonist sight; this is faster than digging many graves.",
    "create_animal_corpse_dump": "Create a critical-priority animal-corpse stockpile beside the butcher area so carcasses are hauled and processed efficiently.",
    "build_butcher_spot": "Place a free butcher spot beside accessible animal carcasses and add its forever butchering bill. Hunting and hauling alone cannot turn carcasses into food.",
    "create_stone_chunk_dump": "Create a preferred stone-chunk dumping stockpile beside the stonecutter to remove long hauling trips.",
    "build_crematorium": "Build an electric crematorium and configure corpse cremation when power, steel, components and labor justify it.",
    "build_prison": "Prepare a small enclosed two-place prison before the next raid so Laya can capture and recruit a downed enemy; materials, food, medicine and guard labor are the costs.",
    "build_hospital": "Build a small enclosed two-bed clinic and later mark its completed beds medical.",
    "build_passive_cooler": "Install a 50-wood passive cooler in a hot occupied bedroom or clinic. Untreated heatstroke can kill even a fed, bandaged patient; the cooler needs wood refills and construction time.",
    "build_room_campfire": "Warm a cold occupied room with a 20-wood indoor campfire. It needs regular wood refills and can overheat a small room; without heat a hypothermic patient can die.",
    "build_room_heater": "Warm a cold occupied room with an electric heater (50 steel, one component, 175 W). It needs a working power connection; an unpowered heater will not rescue a patient.",
    "connect_room_heater_power": "Lay a checked conduit route from the live generator grid to an existing unpowered bedroom heater. The cable consumes steel and builder time before it can warm anyone.",
    "prioritize_thermal_project": "Choose an unfinished cooler or heater in a threatened patient's room and a capable builder. A blueprint alone changes no temperature; delaying construction can be fatal.",
    "configure_hospital_beds": "Mark the completed clinic beds as medical beds.",
    "floor_critical_room": "Floor a real shared bedroom, kitchen, food room or hospital chosen by Laya with an affordable material, balancing comfort, cleanliness, fire and reserves.",
    "build_pathways": "Build an affordable two-wide path between the colony core, stores and fields to improve routine movement speed.",
    "build_temple": "Build an Ideology-compatible ritual room around the colony's actual altar or ideogram precept, with no beds or work facilities.",
    "choose_colony_doctrine": "Choose or deliberately revise a persistent colony doctrine: settlement form/material, peaceful or aggressive posture, military investment, and production identity. Existing buildings are never replaced merely because the doctrine changes.",
    "build_private_bedroom": "Build one separate private bedroom in the current settlement material, improving sleep privacy and enabling an impressive-bedroom mood bonus without rebuilding existing rooms.",
    "excavate_mountain_bedroom": "Mine a compact bedroom into a verified solid natural-rock block, leaving natural rock walls and a one-cell entrance; furnish it only after excavation completes.",
    "finish_mountain_bedroom": "Furnish the already excavated mountain bedroom with a door, bed, light and climate control without replacing older housing.",
    "commission_sculptures": "Build or use an art bench and commission small sculptures so Laya can later place actual finished art in the highest-value room.",
    "install_sculpture": "Install one actual finished sculpture in a room selected by Laya: usually a shared dining/rec room, a weak bedroom, hospital, or long-duration workshop.",
    "build_weapon_shelves": "Build high-priority shelves for weapons and armor, protecting equipment from deterioration and removing loose-item beauty penalties.",
    "prioritize_armament": "Prioritize the doctrine's weapon or armor research and configure normal crafting bills when the required workshop and resources exist.",
    "build_animal_barn": "Build a temperature-aware animal barn with sleeping places and optional low-filth straw matting, preserving fire safety and hay reserves.",
    "build_animal_pen": "Build a finished fenced pen with a gate and marker before taming or buying livestock that can roam away.",
    "pause_late_sowing": "Disable sowing in existing outdoor growing zones when present temperature and remaining growing season make a harvest unlikely; existing mature crops remain harvestable.",
    "resume_seasonal_sowing": "Re-enable sowing when outdoor growing conditions become viable again.",
    "unforbid_corpses": "Remove forbidden marks from corpses so haulers can bury people and butcher usable animal carcasses.",
    "prioritize_burial": "Give Hauling priority 1 so exposed corpses are taken to graves or the butcher area.",
    "build_freezer": "Build a compact powered freezer around the food stockpile.",
    "create_stockpile": "Create an organized stockpile so materials are hauled into one known place.",
    "expand_stockpile": "Expand general storage because at least 90% of current stockpile cells are occupied.",
    "create_growing_zone": "Create a rice growing zone to establish renewable food production.",
    "build_starter_base": "Start a compact shared house on verified dry ground, with real beds, a door, light and interior flooring. A separate kitchen and food store can follow once shelter is usable.",
    "configure_food_bills": "Add sustainable simple-meal and butchering bills to completed work tables.",
    "rebalance_cooking": "Choose a real cook to assign or free from competing animal work when prepared meals are gone despite abundant edible ingredients.",
    "advance_research": "Select the next available project on the default route toward fabrication and starflight.",
    "advance_doctrine_research": "Let Laya choose one currently available research project whose live definition advances the selected economy, technology, defense or endgame direction.",
    "build_power": "Choose a power source from the live catalog, research a better source, or defer generation. Compare fuel, output, construction skill, grid demand and current consumers before placing a checked blueprint.",
    "connect_power_consumer": "Connect an existing unpowered device to the generator's actual electrical network with a continuous, checked conduit route.",
    "build_battery_shelter": "Enclose an existing outdoor battery under an automatic roof. Rain on an exposed battery can short the grid and start fires; a small shed costs about 70 wall material plus a door and builder time.",
    "build_hitech_lab": "Place blueprints for a hi-tech research bench and multi-analyzer.",
    "build_fabrication": "Place a fabrication bench needed for advanced components.",
    "build_ship": "Place a connected starter starship blueprint with reactor, engine, computer, sensor and cryptosleep caskets.",
    "income_drugs": "Adopt a psychoid cash-crop route: grow surplus psychoid, research drug production, and later make sale-only flake/yayo.",
    "income_tailoring": "Adopt a textile route: grow cotton and turn surplus textiles/leather into trade apparel.",
    "income_art": "Adopt an art route: build a sculptor table and make sale sculptures from renewable wood or stone.",
    "income_livestock": "Adopt an animal route: prioritize handling and sell surplus animals, wool, milk and leather without starving the herd.",
    "income_biofuel": "Adopt a chemfuel route: tame boomalopes when safe and refine surplus organics after Biofuel Refining.",
    "income_mining": "Adopt a mining route: mine local gold/silver first, then research long-range scanning for guarded resource expeditions.",
    "income_crops": "Adopt a low-tech surplus-crop route: grow corn after the emergency rice supply is secure and sell only the reserve above colony needs.",
    "income_brewing": "Adopt a beer route: grow hops, research brewing, make wort and ferment it into a durable trade product.",
    "income_travel_food": "Adopt a caravan-food route: make pemmican or packaged survival meals for sale and for longer trade expeditions.",
    "income_orbital": "Adopt an orbital trade route: research microelectronics and build a comms console plus beacon for passing ships.",
    "income_organs": "Adopt a prisoner-organ trade route, balancing doctor skill, medicine, surgery risk, ideology and colony mood against organ value.",
    "build_income_infrastructure": "Build the missing workshop for the chosen income strategy after its prerequisite research is complete.",
    "build_killbox": "Build an early open-path defensive funnel with cover and spike traps; it is only the outer layer, not the whole defense.",
    "build_fallback_defense": "Build an internal fallback firing line and melee choke so breachers, drop pods and infestations do not bypass every defense.",
    "build_turret_defense": "Add powered turrets with spaced cover after Gun Turrets research; colonists still provide the main firepower.",
    "build_mortar_post": "Add a protected mortar position after Mortars research to answer sieges and enemies waiting at the map edge.",
    "build_firefoam_defense": "Place firefoam coverage near power, fuel and the defensive line so incendiary raids do not destroy the colony.",
    "expand_home_area": "Expand Home area only around a threatened live fire so assigned firefighters can reach it; a remote wilderness fire may be left alone.",
    "start_stonecutting": "Research/build stonecutting and cut the stone type chosen by Laya from actual nearby chunks into fireproof blocks.",
    "start_taming": "Designate the exact nearby species and sex chosen by Laya for taming, considering handler skill and revenge risk.",
    "tame_wild_human": "A wild person can become a full colonist through ordinary taming when an Animals 7 handler is available. Review their health, proximity, food needs and the chance the attempt fails.",
    "breed_animals": "Keep a chosen adult male/female pair of the same tame species together and prioritize handling so they can reproduce naturally.",
    "plan_human_reproduction": "Choose an existing romantic couple and a reproductive approach only when food, housing and safety can support a child.",
    "process_mechanoids": "Research/build machining and add a bill to dismantle mechanoid corpses for useful materials.",
    "prepare_trade_caravan": "Prepare a guarded trade expedition to a friendly settlement, keeping enough defenders, food and medicine at home.",
    "prepare_trade_rations": "Unblock the chosen sale route: research pemmican, then cook enough travel rations at a real campfire or stove before sending a caravan.",
    "configure_income_production": "Configure the chosen workshop with a repeatable sale-goods bill while preserving survival reserves.",
    "prioritize_construction": "Give Construction priority 1 to the healthiest best builder so issued blueprints are completed.",
    "prioritize_construction_project": "Let Laya choose one exact unfinished blueprint/frame and a suitable builder, then issue a normal forced construction job.",
    "prioritize_firefighting": "Assign Firefighter priority 1 to every capable healthy colonist in one response while live flames threaten the Home area.",
    "prioritize_research": "Reserve one healthy researcher for the selected project: give Research priority 1 and move their ordinary priority-1 jobs to priority 2 while emergency duties stay available.",
    "prioritize_cooking": "Give Cooking priority 1 to a capable healthy cook while prepared meals are scarce.",
    "prioritize_growing": "Give Growing priority 1 to a capable healthy grower so crops are planted and harvested.",
    "harvest_local_plants": "Let Laya choose one real nearby mature wild plant type, then designate only those exact plants for harvesting.",
    "harvest_food_crops_early": "Harvest a selected batch of edible crops before full maturity when meals run low. This feeds the colony sooner but sacrifices some eventual yield; Laya chooses the crop and batch size.",
    "harvest_nearby_trees": "Cut a small group of nearby mature trees for wood when unfinished shelter and furniture cannot be built from empty stores.",
    "prioritize_hauling": "Give Hauling priority 1 so unlocked food reaches the protected food stockpile.",
    "prioritize_hunting": "Give Hunting priority 1 to the best healthy shooter.",
    "prioritize_handling": "Give Handling priority 1 so colony animals are fed, trained and managed.",
    "prioritize_plant_cutting": "Give Plant Cutting priority 1 for wood and wild-food gathering.",
    "prioritize_cleaning": "Give Cleaning priority 1 to reduce filth, infection and food poisoning risk.",
    "prioritize_rescue": "Give Basic priority 1 so a healthy colonist rescues downed allies before routine work.",
    "prioritize_doctor": "Give Doctor priority 1 so injuries are treated before routine work.",
    "designate_safe_hunting": "Let Laya choose one exact nearby animal using meat/leather/value, revenge risk and the colony's available fighters; thrumbos require a strong firing team.",
    "consider_dangerous_hunt": "Evaluate a dangerous wild animal separately from routine hunting. Laya chooses the target, then explicitly decides whether its likely revenge and combat power justify risking the colony now.",
    "leave_wildlife_alone": "Deliberately leave nearby valuable or dangerous wildlife alone when taming and hunting are not worth the present risk or workload.",
    "hold_survival": "Issue no new project while colonists eat, sleep, recover or finish already-issued survival work.",
    "select_research": "Choose any currently startable research project from the game's live technology tree, including modded projects.",
    "set_work_priority": "Choose a live work type, an eligible colonist and a priority from 1 to 4; the model decides the assignment.",
}

ACTION_LABELS = {
    "plan_architecture": "архитектурный проект",
    "build_catalog_building": "постройка из полного каталога",
    "connect_power_consumer": "подключить прибор к электросети",
    "build_research_bench": "первый исследовательский стол",
    "improve_room_lighting": "освещение комнаты",
    "develop_colonist_skill": "развитие навыка",
    "optimize_night_owl_schedule": "расписание совы",
    "schedule_recreation": "время для отдыха",
    "build_recreation_pin": "игра в подковы",
    "upgrade_workbench": "модернизация верстака",
    "unforbid_supplies": "разрешить припасы",
    "equip_colonists": "вооружить колонистов",
    "rescue_downed_colonist": "спасти упавшего колониста",
    "rescue_neutral_arrival": "спасти раненого гостя",
    "tend_colonist": "лечить раненого колониста",
    "create_food_stockpile": "пищевой склад",
    "build_sleeping_spots": "спальные места",
    "build_basic_beds": "обычные кровати",
    "build_campfire": "костёр для готовки",
    "assign_real_bed": "переселить в кровать",
    "prepare_emergency_medical_bed": "подготовить медицинскую кровать",
    "build_animal_spots": "лежанки животных",
    "care_for_injured_animal": "лечение животного",
    "feed_hungry_animal": "кормление животного",
    "feed_hungry_colonist": "кормление лежачего колониста",
    "eat_available_meal": "отправить колониста поесть",
    "create_nearby_food_cache": "ближний склад еды",
    "open_sealed_food_store": "открыть запертый склад еды",
    "finish_freezer_entrance": "дверь пищевого склада",
    "build_cemetery": "кладбище",
    "create_human_corpse_dump": "дальняя свалка человеческих трупов",
    "create_animal_corpse_dump": "свалка туш у разделки",
    "build_butcher_spot": "место разделки животных",
    "create_stone_chunk_dump": "склад каменных глыб у камнетёса",
    "build_crematorium": "крематорий",
    "build_prison": "тюрьма",
    "build_hospital": "больница",
    "build_passive_cooler": "охладить жилую комнату",
    "build_room_campfire": "согреть комнату костром",
    "build_room_heater": "согреть комнату обогревателем",
    "connect_room_heater_power": "подключить обогреватель к сети",
    "prioritize_thermal_project": "срочно достроить обогрев или охлаждение",
    "configure_hospital_beds": "медицинские койки",
    "floor_critical_room": "пол в критической комнате",
    "build_pathways": "дорожки",
    "build_temple": "храм и ритуальная комната",
    "choose_colony_doctrine": "доктрина колонии",
    "build_private_bedroom": "отдельная спальня",
    "excavate_mountain_bedroom": "вырубить спальню в скале",
    "finish_mountain_bedroom": "обставить спальню в скале",
    "commission_sculptures": "заказать скульптуры",
    "install_sculpture": "поставить скульптуру",
    "build_weapon_shelves": "полки оружия и брони",
    "prioritize_armament": "оружие и броня",
    "build_animal_barn": "дом для животных",
    "build_animal_pen": "загон для животных",
    "pause_late_sowing": "остановить поздний посев",
    "resume_seasonal_sowing": "возобновить сезонный посев",
    "unforbid_corpses": "разрешить перенос трупов",
    "prioritize_burial": "захоронение и трупы",
    "build_freezer": "морозилка",
    "create_stockpile": "общий склад",
    "expand_stockpile": "расширение склада",
    "create_growing_zone": "рисовое поле",
    "build_starter_base": "жилой блок",
    "configure_food_bills": "рецепты еды",
    "rebalance_cooking": "время для готовки",
    "advance_research": "новое исследование",
    "advance_doctrine_research": "исследование по доктрине",
    "build_power": "электросеть",
    "build_battery_shelter": "крыша для батареи",
    "build_hitech_lab": "лаборатория",
    "build_fabrication": "станок компонентов",
    "build_ship": "космический корабль",
    "income_drugs": "доход: психоид",
    "income_tailoring": "доход: одежда",
    "income_art": "доход: скульптуры",
    "income_livestock": "доход: животные",
    "income_biofuel": "доход: химтопливо",
    "income_mining": "доход: ценные руды",
    "income_crops": "доход: излишки урожая",
    "income_brewing": "доход: пиво",
    "income_travel_food": "доход: дорожная еда",
    "income_orbital": "доход: орбитальная торговля",
    "income_organs": "доход: органы пленных",
    "build_income_infrastructure": "цех выбранного дохода",
    "build_killbox": "защитный коридор",
    "build_fallback_defense": "внутренняя линия обороны",
    "build_turret_defense": "турельная линия",
    "build_mortar_post": "миномётная позиция",
    "build_firefoam_defense": "противопожарная защита",
    "expand_home_area": "защитить дом от пожара",
    "start_stonecutting": "каменные блоки",
    "start_taming": "приручение животного",
    "tame_wild_human": "приручение дикого человека",
    "breed_animals": "разведение животных",
    "plan_human_reproduction": "планирование ребёнка",
    "process_mechanoids": "разбор механоидов",
    "prepare_trade_caravan": "торговая вылазка",
    "prepare_trade_rations": "пеммикан для торговли",
    "configure_income_production": "производство на продажу",
    "prioritize_construction": "строительство",
    "prioritize_construction_project": "приоритет конкретной постройки",
    "prioritize_firefighting": "тушение пожара",
    "prioritize_research": "исследования",
    "prioritize_cooking": "готовка",
    "prioritize_growing": "растениеводство",
    "prioritize_hauling": "переноска",
    "prioritize_hunting": "охота",
    "prioritize_handling": "животноводство",
    "prioritize_plant_cutting": "заготовка растений",
    "prioritize_cleaning": "уборка",
    "prioritize_rescue": "спасение раненых",
    "prioritize_doctor": "лечение",
    "designate_safe_hunting": "безопасная охота",
    "consider_dangerous_hunt": "рискованная охота",
    "leave_wildlife_alone": "оставить диких животных в покое",
    "harvest_local_plants": "сбор дикоросов",
    "harvest_food_crops_early": "ранний сбор урожая",
    "harvest_nearby_trees": "рубка деревьев для стройки",
    "open_blocked_food_path": "открыть путь к еде",
    "hold_survival": "наблюдать",
    "select_research": "выбрать исследование",
    "set_work_priority": "назначить приоритет работы",
}

# The game overlay follows RimWorld's language, independently of the GUI
# language. Unlisted actions remain readable through their English API names.
ACTION_LABELS_EN = {
    "plan_architecture": "Design a building", "unforbid_supplies": "Unforbid supplies",
    "build_catalog_building": "Choose a catalog building",
    "connect_power_consumer": "Connect a powered device",
    "build_research_bench": "Build the first research bench",
    "equip_colonists": "Equip colonists", "rescue_downed_colonist": "Rescue a colonist",
    "rescue_neutral_arrival": "Rescue a visitor",
    "tend_colonist": "Tend a colonist",
    "create_food_stockpile": "Food stockpile", "build_sleeping_spots": "Sleeping spots",
    "build_basic_beds": "Beds", "build_animal_spots": "Animal sleeping spots",
    "build_campfire": "Cooking campfire",
    "assign_real_bed": "Assign a real bed", "prepare_emergency_medical_bed": "Make a medical bed",
    "schedule_recreation": "Schedule recreation", "build_recreation_pin": "Horseshoes pin",
    "care_for_injured_animal": "Treat injured animal", "feed_hungry_animal": "Feed animal",
    "feed_hungry_colonist": "Feed colonist", "build_cemetery": "Cemetery",
    "eat_available_meal": "Eat a meal", "create_nearby_food_cache": "Nearby food cache",
    "open_sealed_food_store": "Open food store", "finish_freezer_entrance": "Food store door",
    "create_human_corpse_dump": "Human corpse dump", "create_animal_corpse_dump": "Animal corpse dump",
    "build_butcher_spot": "Butcher spot",
    "build_crematorium": "Crematorium", "build_prison": "Prison", "build_hospital": "Hospital",
    "build_passive_cooler": "Cool a patient room",
    "build_room_campfire": "Warm a room with a campfire",
    "build_room_heater": "Warm a room with a heater",
    "connect_room_heater_power": "Connect a bedroom heater",
    "prioritize_thermal_project": "Finish urgent temperature control",
    "choose_colony_doctrine": "Colony strategy", "build_private_bedroom": "Private bedroom",
    "build_freezer": "Freezer", "create_stockpile": "Stockpile", "expand_stockpile": "Expand stockpile",
    "create_growing_zone": "Growing zone", "build_starter_base": "Starter base",
    "build_killbox": "Defensive corridor", "build_fallback_defense": "Fallback defense",
    "expand_home_area": "Protect home from fire",
    "start_stonecutting": "Cut stone blocks", "start_taming": "Tame animal",
    "tame_wild_human": "Tame wild person",
    "build_animal_pen": "Build animal pen",
    "process_mechanoids": "Process mechanoids", "prepare_trade_caravan": "Trade caravan",
    "prepare_trade_rations": "Prepare trade rations",
    "prioritize_construction": "Prioritize construction", "prioritize_research": "Prioritize research",
    "prioritize_growing": "Prioritize growing", "prioritize_hauling": "Prioritize hauling",
    "prioritize_hunting": "Prioritize hunting", "prioritize_handling": "Prioritize animal handling",
    "prioritize_plant_cutting": "Prioritize plant cutting", "prioritize_cleaning": "Prioritize cleaning",
    "prioritize_rescue": "Prioritize rescue", "prioritize_doctor": "Prioritize medical care",
    "designate_safe_hunting": "Choose hunting target", "leave_wildlife_alone": "Leave wildlife alone",
    "consider_dangerous_hunt": "Risky hunt",
    "harvest_local_plants": "Harvest wild plants", "hold_survival": "Wait and observe",
    "harvest_food_crops_early": "Harvest food crops early",
    "rebalance_cooking": "Make time for cooking",
    "harvest_nearby_trees": "Cut nearby trees",
    "open_blocked_food_path": "Open food access",
    "select_research": "Choose research", "set_work_priority": "Set work priority",
    "prioritize_firefighting": "Fight the active fire",
}


def load_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"maps": {}}


def save_state(path: Path, state: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(state, ensure_ascii=False, indent=2)
    # A GUI/antivirus reader can momentarily deny FILE_SHARE_DELETE on Windows.
    # Preserve the in-memory state and retry on the next cycle if it stays busy.
    for attempt in range(6):
        try:
            temp.write_text(serialized, encoding="utf-8")
            temp.replace(path)
            return True
        except OSError:
            time.sleep(0.05 * (attempt + 1))
    try:
        path.write_text(serialized, encoding="utf-8")
        return True
    except OSError:
        print(f"Colony state file busy; will retry: {path}", file=sys.stderr)
        return False


def position(x: int, z: int) -> dict[str, int]:
    return {"x": int(x), "y": 0, "z": int(z)}


def campfire_safe_placement(cells: list[dict[str, Any]], structures: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Keep an indoor flame at least three cells from known combustible structures."""
    combustible = []
    for structure in structures:
        label = str(structure.get("label") or "").lower()
        stuff = str(structure.get("stuff_def_name") or structure.get("stuff") or "").lower()
        if not any(material in label or material in stuff
                   for material in ("wooden", "woodlog", "cloth", "leather", "straw", "hay")):
            continue
        point = structure.get("position") or {}
        if point.get("x") is not None and point.get("z") is not None:
            combustible.append((int(point["x"]), int(point["z"])))
    for cell in cells:
        x, z = int(cell.get("x") or 0), int(cell.get("z") or 0)
        if all(max(abs(x - wood_x), abs(z - wood_z)) > 2
               for wood_x, wood_z in combustible):
            return cell
    return None


def building(def_name: str, x: int, z: int, *, stuff: str | None = None, rotation: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = {"def_name": def_name, "rel_x": x, "rel_z": z, "rotation": rotation}
    if stuff:
        result["stuff_def_name"] = stuff
    return result


def floor(def_name: str, x: int, z: int) -> dict[str, Any]:
    return {"def_name": def_name, "rel_x": int(x), "rel_z": int(z)}


def blueprint(buildings: list[dict[str, Any]], width: int, height: int, floors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"width": width, "height": height, "floors": floors or [], "buildings": buildings}


def starter_base_blueprint(colonist_count: int, *, cold: bool = False,
                           wall_stuff: str = "WoodLog") -> dict[str, Any]:
    """The first house is small enough to finish before a second night.

    Workstations belong in later dedicated rooms: crowding the first house
    with them previously exhausted the starting wood before it gained a roof.
    """
    if cold:
        # At severe subzero temperatures the original 7x7 room took longer
        # to enclose and roof than the founders could remain conscious. Keep
        # three sleeping spots entirely inside this smaller heated shell.
        items = []
        for x in range(5):
            if x != 2:
                items.append(building("Wall", x, 0, stuff=wall_stuff))
            items.append(building("Wall", x, 5, stuff=wall_stuff))
        for z in range(1, 5):
            items.append(building("Wall", 0, z, stuff=wall_stuff))
            items.append(building("Wall", 4, z, stuff=wall_stuff))
        items.append(building("Door", 2, 0, stuff=wall_stuff))
        items.append(building("Campfire", 2, 4))
        for index in range(min(3, max(1, colonist_count))):
            items.append(building("SleepingSpot", 1 + index, 2))
        return blueprint(items, 5, 6)
    items: list[dict[str, Any]] = []
    for x in range(7):
        if x != 3:
            items.append(building("Wall", x, 0, stuff=wall_stuff))
        items.append(building("Wall", x, 6, stuff=wall_stuff))
    for z in range(1, 6):
        items.append(building("Wall", 0, z, stuff=wall_stuff))
        items.append(building("Wall", 6, z, stuff=wall_stuff))
    items.append(building("Door", 3, 0, stuff=wall_stuff))
    for index in range(min(3, max(1, colonist_count))):
        items.append(building("Bed", 1 + 2 * index, 2, stuff="WoodLog"))
    items.append(building("TorchLamp", 3, 5))
    floors = [floor("WoodPlankFloor", x, z) for x in range(1, 6) for z in range(1, 6)]
    return blueprint(items, 7, 7, floors)


def starter_outdoor_c(dev: dict[str, Any]) -> float:
    """The cold threat is calculated later than the first shelter candidate."""
    weather = (dev.get("weather") or {}).get("temperature")
    cold = (dev.get("cold_threat") or {}).get("outside_c")
    return float(weather if weather is not None else cold if cold is not None else 20)


def animal_spots_blueprint(animal_count: int) -> dict[str, Any]:
    count = max(1, min(6, int(animal_count)))
    return blueprint([building("AnimalSleepingSpot", index * 2, 0) for index in range(count)], count * 2, 1)


def animal_pen_blueprint(size: int, material: str) -> dict[str, Any]:
    """A closed grazing pen: marker and passable gate are required by RimWorld."""
    size = max(9, min(17, int(size) | 1))
    gate_x = size // 2
    items = []
    for x in range(size):
        if x != gate_x:
            items.append(building("Fence", x, 0, stuff=material))
        items.append(building("Fence", x, size - 1, stuff=material))
    for z in range(1, size - 1):
        items.append(building("Fence", 0, z, stuff=material))
        items.append(building("Fence", size - 1, z, stuff=material))
    items.append(building("FenceGate", gate_x, 0, stuff=material))
    items.append(building("PenMarker", gate_x, gate_x, stuff=material))
    return blueprint(items, size, size)


def cemetery_blueprint(grave_count: int = 8) -> dict[str, Any]:
    """Two orderly rows of real 1x2 graves with walking space between them."""
    count = max(2, min(12, int(grave_count)))
    columns = min(4, count)
    items = [
        building("Grave", (index % columns) * 2, (index // columns) * 3)
        for index in range(count)
    ]
    rows = (count + columns - 1) // columns
    return blueprint(items, columns * 2 - 1, rows * 3 - 1)


def prison_blueprint(stuff: str = "WoodLog") -> dict[str, Any]:
    """A legitimate enclosed two-bed prison; beds are marked for prisoners after construction."""
    items: list[dict[str, Any]] = []
    for x in range(7):
        if x != 3:
            items.append(building("Wall", x, 0, stuff=stuff))
        items.append(building("Wall", x, 6, stuff=stuff))
    for z in range(1, 6):
        items.append(building("Wall", 0, z, stuff=stuff))
        items.append(building("Wall", 6, z, stuff=stuff))
    items.extend([
        building("Door", 3, 0, stuff=stuff),
        building("SleepingSpot", 2, 3),
        building("SleepingSpot", 4, 3),
    ])
    return blueprint(items, 7, 7)


def prison_material(item_counts: dict[str, Any]) -> str | None:
    """The 23 walls and one door need about 140 units of one material."""
    for stuff in ("WoodLog", "Steel"):
        if int(item_counts.get(stuff) or 0) >= 140:
            return stuff
    return None


def installable_sculpture(thing: dict[str, Any]) -> bool:
    """Only a finished, spawned minified sculpture has an installable thing ID."""
    return (str(thing.get("def_name") or "") == "MinifiedThing"
            and "sculpture" in str(thing.get("inner_def_name") or "").lower())


def hospital_blueprint() -> dict[str, Any]:
    """A small enclosed clinic; ordinary beds are later toggled medical by RIMAPI."""
    items: list[dict[str, Any]] = []
    for x in range(7):
        if x != 3:
            items.append(building("Wall", x, 0, stuff="WoodLog"))
        items.append(building("Wall", x, 6, stuff="WoodLog"))
    for z in range(1, 6):
        items.append(building("Wall", 0, z, stuff="WoodLog"))
        items.append(building("Wall", 6, z, stuff="WoodLog"))
    items.extend([
        building("Door", 3, 0, stuff="WoodLog"),
        building("Bed", 2, 3, stuff="WoodLog"),
        building("Bed", 4, 3, stuff="WoodLog"),
        building("TorchLamp", 3, 5),
    ])
    return blueprint(items, 7, 7)


def room_floor_blueprint(cells: list[dict[str, Any]], floor_def: str) -> tuple[dict[str, Any], dict[str, int]]:
    if not cells:
        raise ValueError("Room has no floorable cells")
    min_x = min(int(c.get("x") or 0) for c in cells)
    min_z = min(int(c.get("z") or 0) for c in cells)
    max_x = max(int(c.get("x") or 0) for c in cells)
    max_z = max(int(c.get("z") or 0) for c in cells)
    floors = [floor(floor_def, int(c.get("x") or 0) - min_x, int(c.get("z") or 0) - min_z) for c in cells]
    return blueprint([], max_x - min_x + 1, max_z - min_z + 1, floors), {"x": min_x, "z": min_z}


def terrain_defs_at_cells(terrain_map: dict[str, Any], cells: list[dict[str, Any]]) -> dict[tuple[int, int], str]:
    """Read exact terrain at requested coordinates from RIMAPI's row-major RLE grid."""
    width = int(terrain_map.get("width") or 0)
    height = int(terrain_map.get("height") or 0)
    palette = terrain_map.get("palette") or []
    runs = terrain_map.get("grid") or []
    if width <= 0 or height <= 0 or not palette or len(runs) % 2:
        raise ValueError("Terrain API returned an incomplete grid")
    targets = sorted((int(cell["z"]) * width + int(cell["x"]),
                      (int(cell["x"]), int(cell["z"])))
                     for cell in cells if 0 <= int(cell["x"]) < width and 0 <= int(cell["z"]) < height)
    result: dict[tuple[int, int], str] = {}
    target_index = 0
    run_start = 0
    for count, palette_index in zip(runs[::2], runs[1::2]):
        run_end = run_start + int(count)
        while target_index < len(targets) and targets[target_index][0] < run_end:
            linear, coord = targets[target_index]
            if linear >= run_start and 0 <= int(palette_index) < len(palette):
                result[coord] = str(palette[int(palette_index)])
            target_index += 1
        run_start = run_end
        if target_index >= len(targets):
            break
    if len(result) != len({coord for _, coord in targets}):
        raise ValueError("Terrain API grid does not cover the requested room cells")
    return result


def needs_first_floor(terrain_def: str | None) -> bool:
    """A finished floor is never a routine construction deficit."""
    name = str(terrain_def or "")
    return name in {"Soil", "SoilRich", "Gravel", "Sand", "Mud", "Marsh", "MarshyTerrain"} or name.startswith("Rough")


def floor_project_cells(projects: list[dict[str, Any]]) -> set[tuple[int, int]]:
    floors = {"Concrete", "PavedTile", "WoodPlankFloor", "StrawMatting",
              "MetalTile", "SterileTile"}
    return {
        (int(pos["x"]), int(pos["z"]))
        for row in projects if isinstance(row, dict)
        for pos in [row.get("position") or {}]
        if pos.get("x") is not None and pos.get("z") is not None
        and (str(row.get("kind") or "").lower() in {"terrain", "floor"}
             or str(row.get("def_name") or "") in floors
             or str(row.get("def_name") or "").startswith(("Tile", "Carpet", "Flagstone")))
    }


def pathway_blueprint(
    floor_def: str, anchor: dict[str, int], growing_anchor: dict[str, int]
) -> tuple[dict[str, Any], dict[str, int]]:
    """One-cell-wide outdoor route; broad paved plazas are an avoidable early-game expense."""
    min_x = min(int(growing_anchor["x"]), int(anchor["x"]) - 15)
    max_x = int(anchor["x"]) + 22
    min_z = int(anchor["z"])
    path_z = int(anchor["z"]) + 9
    absolute = {(x, path_z) for x in range(min_x, max_x + 1)}
    absolute |= {(int(anchor["x"]), z) for z in range(min_z, path_z + 1)}
    floors = [floor(floor_def, x - min_x, z - min_z) for x, z in sorted(absolute)]
    return blueprint([], max_x - min_x + 1, path_z - min_z + 1, floors), {"x": min_x, "z": min_z}


def affordable_floor_options(
    item_counts: dict[str, Any],
    finished: set[str],
    cell_count: int,
    best_builder: int,
    *,
    pathway: bool = False,
    wood_reserve: int = 180,
) -> dict[str, str]:
    """Return only materials that preserve a practical emergency reserve."""
    options: dict[str, str] = {}
    steel = int(item_counts.get("Steel") or 0)
    wood = int(item_counts.get("WoodLog") or 0)
    silver = int(item_counts.get("Silver") or 0)
    # Concrete is steel, despite looking like a cheap road. Outdoor paths use
    # renewable stone flagstone only; steel remains reserved for power, coolers,
    # weapons and the ship.
    if not pathway and "Stonecutting" in finished and steel >= cell_count + 100:
        options["Concrete"] = f"{cell_count} steel; fast, nonflammable, neutral cleanliness, ugly"
    for stone in ("Granite", "Limestone", "Sandstone", "Slate", "Marble"):
        blocks = int(item_counts.get(f"Blocks{stone}") or 0)
        if blocks >= cell_count * 4 + 80:
            def_name = f"Flagstone{stone}" if pathway else f"Tile{stone}"
            options[def_name] = f"{cell_count * 4} {stone.lower()} blocks; nonflammable, slower work"
    if not pathway and wood >= cell_count * 3 + wood_reserve:
        options["WoodPlankFloor"] = f"{cell_count * 3} wood; quick and cheap but flammable"
    if not pathway and "Smithing" in finished and best_builder >= 3 and steel >= cell_count * 7 + 150:
        options["MetalTile"] = f"{cell_count * 7} steel; +0.2 cleanliness and fast cleaning"
    if (
        not pathway and "SterileMaterials" in finished and best_builder >= 6
        and steel >= cell_count * 3 + 100 and silver >= cell_count * 12 + 300
    ):
        options["SterileTile"] = f"{cell_count * 3} steel + {cell_count * 12} silver; +0.6 cleanliness, very slow to build"
    return options


def structure_material_options(item_counts: dict[str, Any], *, minimum_units: int = 125) -> dict[str, str]:
    """Materials that can finish a small room while retaining a survival reserve."""
    options: dict[str, str] = {}
    wood = int(item_counts.get("WoodLog") or 0)
    if wood >= minimum_units + 80:
        options["WoodLog"] = f"{wood} available; fastest and renewable, but 100% flammable"
    stone_notes = {
        "Granite": "highest common stone wall durability and fireproof",
        "Limestone": "durable all-round stone and fireproof",
        "Sandstone": "fastest common stone to build and fireproof",
        "Slate": "lower durability but fireproof",
        "Marble": "+1 wall beauty and fireproof",
    }
    for stone, note in stone_notes.items():
        amount = int(item_counts.get(f"Blocks{stone}") or 0)
        if amount >= minimum_units + 50:
            options[f"Blocks{stone}"] = f"{amount} blocks available; {note}"
    steel = int(item_counts.get("Steel") or 0)
    if steel >= minimum_units + 300:
        options["Steel"] = f"{steel} available; fast and 300 HP, but steel structures remain 40% flammable"
    uranium = int(item_counts.get("Uranium") or 0)
    if uranium >= minimum_units + 250:
        options["Uranium"] = f"{uranium} available; 750 HP and nonflammable, but strategically scarce"
    plasteel = int(item_counts.get("Plasteel") or 0)
    if plasteel >= minimum_units + 300:
        options["Plasteel"] = f"{plasteel} available; 840 HP and nonflammable, but needed for advanced equipment and the ship"
    jade = int(item_counts.get("Jade") or 0)
    if jade >= minimum_units + 500:
        options["Jade"] = f"{jade} available; beautiful and fireproof but weak and valuable"
    silver = int(item_counts.get("Silver") or 0)
    if silver >= minimum_units + 3000:
        options["Silver"] = f"{silver} available; beautiful but weak, flammable and spendable"
    gold = int(item_counts.get("Gold") or 0)
    if gold >= minimum_units + 1500:
        options["Gold"] = f"{gold} available; extremely beautiful but weak and strategically valuable"
    return options


def private_bedroom_blueprint(
    wall_stuff: str,
    *,
    powered: bool = False,
    complex_furniture: bool = False,
    climate: str = "temperate",
) -> dict[str, Any]:
    """A 5x5 interior private bedroom; material changes apply only to this new room."""
    items: list[dict[str, Any]] = []
    for x in range(7):
        if x != 3:
            items.append(building("Wall", x, 0, stuff=wall_stuff))
        items.append(building("Wall", x, 6, stuff=wall_stuff))
    for z in range(1, 6):
        items.append(building("Wall", 0, z, stuff=wall_stuff))
        items.append(building("Wall", 6, z, stuff=wall_stuff))
    items.extend([
        building("Door", 3, 0, stuff=wall_stuff),
        building("Bed", 2, 3, stuff="WoodLog"),
        building("StandingLamp" if powered else "TorchLamp", 4, 4),
    ])
    if complex_furniture:
        items.extend([
            building("EndTable", 1, 3, stuff="WoodLog"),
            building("Dresser", 3, 5, stuff="WoodLog"),
        ])
    if powered and climate == "cold":
        items.append(building("Heater", 4, 2))
    elif climate == "hot":
        items.append(building("PassiveCooler", 4, 2))
    return blueprint(items, 7, 7)


def animal_barn_blueprint(
    wall_stuff: str,
    animal_count: int,
    *,
    straw_floor: bool,
    powered: bool,
    climate: str,
) -> dict[str, Any]:
    """Enclosed barn with an animal flap, beds and optional climate mitigation."""
    items: list[dict[str, Any]] = []
    for x in range(9):
        if x != 4:
            items.append(building("Wall", x, 0, stuff=wall_stuff))
        items.append(building("Wall", x, 6, stuff=wall_stuff))
    for z in range(1, 6):
        items.append(building("Wall", 0, z, stuff=wall_stuff))
        items.append(building("Wall", 8, z, stuff=wall_stuff))
    items.append(building("AnimalFlap", 4, 0, stuff=wall_stuff))
    for index in range(max(2, min(8, animal_count + 2))):
        items.append(building("AnimalSleepingSpot", 1 + index % 4 * 2, 2 + index // 4 * 2))
    if powered and climate == "cold":
        items.append(building("Heater", 7, 4))
    elif climate == "hot":
        items.append(building("PassiveCooler", 7, 4))
    floors = [floor("StrawMatting", x, z) for x in range(1, 8) for z in range(1, 6)] if straw_floor else []
    return blueprint(items, 9, 7, floors)


def weapon_shelves_blueprint(stuff: str) -> dict[str, Any]:
    return blueprint([
        building("Shelf", 0, 0, stuff=stuff),
        building("Shelf", 0, 2, stuff=stuff),
        building("Shelf", 0, 4, stuff=stuff),
    ], 2, 5)


def mining_bedroom_rect(ores: dict[str, Any], preferred_center: dict[str, int]) -> tuple[dict[str, int], dict[str, int]] | None:
    """Find a compact 7x7 fully mineable natural-rock block for a mountain bedroom."""
    width = int(ores.get("map_width") or 0)
    if width <= 0:
        return None
    natural: set[tuple[int, int]] = set()
    for name, group in (ores.get("ores") or {}).items():
        lowered = str(name).lower()
        if not lowered.startswith("mineable") or any(token in lowered for token in ("steel", "gold", "silver", "uranium", "component", "plasteel", "jade")):
            continue
        for value in group.get("cells") or []:
            cell = int(value)
            natural.add((cell % width, cell // width))
    if len(natural) < 49:
        return None
    candidates: list[tuple[int, int, int]] = []
    for x, z in natural:
        if all((x + dx, z + dz) in natural for dx in range(7) for dz in range(7)):
            distance = (x - int(preferred_center["x"])) ** 2 + (z - int(preferred_center["z"])) ** 2
            candidates.append((distance, x, z))
    if not candidates:
        return None
    _, x, z = min(candidates)
    return position(x, z), position(x + 6, z + 6)


def mineable_natural_rock_cells(ores: dict[str, Any]) -> set[tuple[int, int]]:
    width = int(ores.get("map_width") or 0)
    result: set[tuple[int, int]] = set()
    if width <= 0:
        return result
    for name, group in (ores.get("ores") or {}).items():
        lowered = str(name).lower()
        if not lowered.startswith("mineable") or any(token in lowered for token in ("steel", "gold", "silver", "uranium", "component", "plasteel", "jade")):
            continue
        for value in group.get("cells") or []:
            cell = int(value)
            result.add((cell % width, cell // width))
    return result


def mountain_bedroom_furnishing(*, powered: bool, climate: str) -> dict[str, Any]:
    items = [
        building("Door", 3, 0, stuff="WoodLog"),
        building("Bed", 2, 3, stuff="WoodLog"),
        building("StandingLamp" if powered else "TorchLamp", 4, 4),
    ]
    if powered and climate == "cold":
        items.append(building("Heater", 4, 2))
    elif climate == "hot":
        items.append(building("PassiveCooler", 4, 2))
    return blueprint(items, 7, 7)


def killbox_blueprint() -> dict[str, Any]:
    """An early-game open funnel: enemies retain a path while traps and cover shape it."""
    items: list[dict[str, Any]] = []
    for z in range(11):
        if z != 0:
            items.append(building("Wall", 0, z, stuff="WoodLog"))
            items.append(building("Wall", 8, z, stuff="WoodLog"))
    for x in range(1, 8):
        if x != 4:
            items.append(building("Wall", x, 0, stuff="WoodLog"))
    # A clear entrance at (4,0), staggered traps, and a protected firing line.
    for x, z in ((4, 2), (3, 4), (5, 6), (4, 8)):
        items.append(building("TrapSpike", x, z, stuff="WoodLog"))
    for x in range(2, 7):
        items.append(building("Barricade", x, 9, stuff="WoodLog"))
    return blueprint(items, 9, 11)


def fallback_defense_blueprint() -> dict[str, Any]:
    """A compact second line with a one-cell melee choke and ranged cover."""
    items = [
        building("Wall", 0, 0, stuff="WoodLog"),
        building("Wall", 1, 0, stuff="WoodLog"),
        building("Door", 2, 0, stuff="WoodLog"),
        building("Wall", 3, 0, stuff="WoodLog"),
        building("Wall", 4, 0, stuff="WoodLog"),
    ]
    for x in range(0, 5):
        items.append(building("Barricade", x, 3, stuff="WoodLog"))
    return blueprint(items, 5, 4)


def turret_defense_blueprint() -> dict[str, Any]:
    items = [
        building("TurretGun", 0, 0),
        building("TurretGun", 6, 0),
        building("Barricade", 2, 2, stuff="Steel"),
        building("Barricade", 3, 2, stuff="Steel"),
        building("Barricade", 4, 2, stuff="Steel"),
    ]
    for x in range(0, 7):
        items.append(building("PowerConduit", x, 1))
    return blueprint(items, 7, 3)


def mortar_post_blueprint() -> dict[str, Any]:
    items = [building("Mortar", 2, 2)]
    for x in range(5):
        items.append(building("Wall", x, 0, stuff="Steel"))
        items.append(building("Wall", x, 4, stuff="Steel"))
    for z in range(1, 4):
        items.append(building("Wall", 0, z, stuff="Steel"))
        if z != 2:
            items.append(building("Wall", 4, z, stuff="Steel"))
    items.append(building("Door", 4, 2, stuff="Steel"))
    return blueprint(items, 5, 5)


def orbital_trade_blueprint() -> dict[str, Any]:
    return blueprint([
        building("CommsConsole", 0, 0, rotation=2),
        building("OrbitalTradeBeacon", 5, 1),
    ], 8, 4)


def workshop_blueprint(def_name: str, *, stuff: str | None = None) -> dict[str, Any]:
    return blueprint([building(def_name, 0, 0, stuff=stuff, rotation=2)], 4, 3)


def sleeping_spots_blueprint(colonist_count: int) -> dict[str, Any]:
    count = max(3, min(colonist_count + 1, 8))
    return blueprint(
        [building("SleepingSpot", index * 2, 0) for index in range(count)],
        max(1, count * 2 - 1),
        1,
    )


def basic_beds_blueprint(colonist_count: int, stuff: str = "WoodLog") -> dict[str, Any]:
    count = max(1, min(int(colonist_count), 8))
    return blueprint(
        [building("Bed", (index % 4) * 2, (index // 4) * 3, stuff=stuff) for index in range(count)],
        max(1, min(4, count) * 2 - 1),
        max(2, ((count - 1) // 4) * 3 + 2),
    )


def freezer_blueprint(*, include_generator: bool = False, wall_stuff: str = "WoodLog") -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for x in range(6):
        items.append(building("Wall", x, 0, stuff=wall_stuff))
        if x != 3:
            items.append(building("Wall", x, 5, stuff=wall_stuff))
    for z in range(1, 5):
        items.append(building("Wall", 0, z, stuff=wall_stuff))
        if z not in {2, 3}:
            items.append(building("Wall", 5, z, stuff=wall_stuff))
    items.append(building("Door", 3, 5, stuff=wall_stuff))
    items.append(building("Cooler", 5, 2, rotation=1))
    for x in range(5, 7):
        items.append(building("PowerConduit", x, 3))
    return blueprint(items, 7, 6)


def freezer_resource_plan(
    building_counts: dict[str, Any], item_counts: dict[str, Any], best_builder: int, finished: set[str],
    generator_defs: set[str] | None = None,
) -> dict[str, Any] | None:
    if "Electricity" not in finished or int(building_counts.get("Cooler", 0)) > 0 or best_builder < 3:
        return None
    power_defs = {"WoodFiredGenerator", "SolarGenerator", "WindTurbine", "WatermillGenerator", "GeothermalGenerator"}
    power_defs.update(generator_defs or set())
    has_generator = any(int(building_counts.get(name, 0)) > 0 for name in power_defs)
    if not has_generator:
        return None
    required = {
        "components": 3,
        "steel": 90,
        "wood": 150,
    }
    if (
        int(item_counts.get("ComponentIndustrial") or 0) < required["components"]
        or int(item_counts.get("Steel") or 0) < required["steel"]
        or int(item_counts.get("WoodLog") or 0) < required["wood"]
    ):
        return None
    return {"include_generator": False, "requirements": required}


def temple_blueprint(altar_def: str, wall_stuff: str) -> dict[str, Any]:
    """A floored 7x7-interior ritual room; no beds or work facilities."""
    items: list[dict[str, Any]] = []
    for x in range(9):
        if x != 4:
            items.append(building("Wall", x, 0, stuff=wall_stuff))
        items.append(building("Wall", x, 8, stuff=wall_stuff))
    for z in range(1, 8):
        items.append(building("Wall", 0, z, stuff=wall_stuff))
        items.append(building("Wall", 8, z, stuff=wall_stuff))
    items.extend([
        building("Door", 4, 0, stuff=wall_stuff),
        building(altar_def, 4, 5, stuff=wall_stuff, rotation=2),
        building("Column", 1, 1, stuff=wall_stuff),
        building("Column", 7, 1, stuff=wall_stuff),
        building("Column", 1, 7, stuff=wall_stuff),
        building("Column", 7, 7, stuff=wall_stuff),
        building("TorchLamp", 4, 2),
    ])
    floor_def = "WoodPlankFloor" if wall_stuff == "WoodLog" else (
        f"Tile{wall_stuff.removeprefix('Blocks')}" if wall_stuff.startswith("Blocks") else "Concrete"
    )
    floors = [floor(floor_def, x, z) for x in range(1, 8) for z in range(1, 8)]
    return blueprint(items, 9, 9, floors)


def battery_shelter_blueprint(material: str) -> dict[str, Any]:
    """Four-by-five enclosure; an existing battery occupies its inner left cells."""
    items: list[dict[str, Any]] = []
    for x in range(4):
        if x != 2:
            items.append(building("Wall", x, 0, stuff=material))
        items.append(building("Wall", x, 4, stuff=material))
    for z in range(1, 4):
        items.append(building("Wall", 0, z, stuff=material))
        items.append(building("Wall", 3, z, stuff=material))
    items.append(building("Door", 2, 0, stuff=material))
    return blueprint(items, 4, 5)


def power_strategy_options(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Offer the game's actual generators and their research prerequisites."""
    dev = snapshot.get("development") or {}
    catalog = [row for row in dev.get("building_catalog") or []
               if isinstance(row, dict) and row.get("is_power_generator")]
    plans = {name: plan for group in architect.catalog_construction_options(dev).values()
             for name, plan in group.items() if plan.get("is_power_generator")}
    best_skill = max((int(((pawn.get("skills") or {}).get("Construction") or {}).get("level") or 0)
                      for pawn in snapshot.get("colonists") or []
                      if not pawn.get("downed")), default=0)
    plans = {name: plan for name, plan in plans.items()
             if best_skill >= int(plan.get("minimum_construction_skill") or 0)}
    research = live_research_options(snapshot)
    locked = {prerequisite: name for row in catalog if not row.get("available_now")
              for name in [str(row.get("def_name"))]
              for prerequisite in row.get("research_prerequisites") or []
              if prerequisite in research}
    buildings = dev.get("buildings") or []
    consumers = [row for row in buildings if row.get("requires_power")]
    unpowered = [row for row in consumers if not row.get("power_on")]
    power = dev.get("power_info") or {}
    choices = {
        f"build:{name}": (
            f"{plan['label']}: nominal {plan.get('nominal_power_output') or '?'} W; "
            f"fuel {plan.get('requires_fuel')}; cost {plan.get('cost_list')} + "
            f"{plan.get('cost_stuff_count')} material; Construction "
            f"{plan.get('minimum_construction_skill') or 0}; already {plan.get('existing_count') or 0}"
        ) for name, plan in plans.items()
    }
    choices.update({f"research:{name}": f"Research {name} to unlock {generator}; {research[name]}"
                    for name, generator in locked.items()})
    choices["defer"] = "Wait for a better technology or higher demand; no generator is placed now."
    return {"choices": choices, "plans": plans, "research": locked,
            "demand": {"consumers": [str(row.get("def")) for row in consumers[:12]],
                       "unpowered": [str(row.get("def")) for row in unpowered[:12]],
                       "generation_w": power.get("current_power"),
                       "consumption_w": power.get("total_consumption"),
                       "stored_wh": power.get("currently_stored_power")}}


def hitech_blueprint() -> dict[str, Any]:
    return blueprint(
        [
            building("HiTechResearchBench", 0, 0, rotation=2),
            building("MultiAnalyzer", 5, 1),
        ],
        8,
        4,
    )


def fabrication_blueprint() -> dict[str, Any]:
    return blueprint([building("FabricationBench", 0, 0, rotation=2)], 4, 3)


def ship_blueprint(colonist_count: int) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for x in range(2, 22, 2):
        items.append(building("Ship_Beam", x, 8))
    items.extend(
        [
            building("Ship_Reactor", 8, 5),
            building("Ship_ComputerCore", 12, 5),
            building("Ship_SensorCluster", 16, 5),
            building("Ship_Engine", 2, 5, rotation=3),
        ]
    )
    for index in range(max(3, min(colonist_count, 8))):
        items.append(building("Ship_CryptosleepCasket", 4 + index * 2, 9, rotation=0))
    return blueprint(items, 24, 14)


def anchor_from_snapshot(snapshot: dict[str, Any]) -> dict[str, int]:
    # A lone hunter or hauler can be over 100 tiles from the landing supplies.
    # Existing colony structures and meals give a stabler settlement centre
    # than the mean of roaming pawn positions when a save is first loaded.
    buildings = (snapshot.get("development") or {}).get("buildings") or []
    def landed(row: dict[str, Any]) -> bool:
        pos = row.get("position") or {}
        return isinstance(pos, dict) and int(pos.get("x") or 0) >= 10 and int(pos.get("z") or 0) >= 10

    core = [row for row in buildings if row.get("def") in {
        "Wall", "Door", "Bed", "SleepingSpot", "Cooler", "FueledStove",
        "WoodFiredGenerator", "SimpleResearchBench", "HiTechResearchBench",
    } and landed(row)]
    # At tick zero the crashlanded food is forbidden and the pawns can still
    # report (0, 0) while their drop pods open.  Use the actual landing
    # supplies even before Laya un-forbids them; never anchor a base to (0, 0).
    landing_meals = [row for row in (snapshot.get("development") or {}).get("things") or []
                     if isinstance(row, dict) and landed(row)
                     and ("FoodMeals" in (row.get("categories") or [])
                          or row.get("def_name") == "MealSurvivalPack")]
    # Starting cargo comes in full stacks; unrelated single survival meals
    # can be scattered across ruins on the same map.  Center on the cargo.
    cargo_meals = [row for row in landing_meals if int(row.get("stack_count") or 0) >= 5]
    source = core if len(core) >= 5 else (cargo_meals or landing_meals)
    if not source:
        source = [row for row in snapshot.get("colonists") or [] if landed(row)]
    if not source:
        return {"x": 125, "z": 125}
    xs = sorted(int((row.get("position") or {}).get("x", 125)) for row in source)
    zs = sorted(int((row.get("position") or {}).get("z", 125)) for row in source)
    center_x = xs[len(xs) // 2] if xs else 125
    center_z = zs[len(zs) // 2] if zs else 125
    return {"x": max(12, min(220, center_x + 12)), "z": max(12, min(220, center_z + 12))}


def map_state_for_snapshot(state: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep orders tied to one actual playthrough, not just a reusable world seed.

    RimWorld can create another colony with the same map seed and map index.
    Loading an older save also rewinds the tick clock. Old issued orders and
    base coordinates are no longer evidence of work in the loaded colony.
    A doctrine chosen before the restored tick still belongs to this colony.
    """
    map_info = snapshot.get("map") or {}
    key = ":".join(str(map_info[field]) if map_info.get(field) is not None else "unknown"
                   for field in ("seed", "tile_id", "id"))
    maps = state.setdefault("maps", {})
    current = maps.setdefault(key, {"issued": {}})
    tick = int((snapshot.get("game") or {}).get("tick") or 0)
    present = {int(pawn["id"]) for pawn in snapshot.get("colonists") or [] if pawn.get("id") is not None}
    known = set(map(int, current.get("known_colonist_ids") or []))
    previous_tick = current.get("last_seen_tick")
    restarted = previous_tick is not None and tick + 100 < int(previous_tick)
    replaced_roster = bool(present and known and not present.intersection(known))
    if restarted or replaced_roster:
        prior = current
        current = {"issued": {}}
        if restarted and not replaced_roster and prior.get("doctrine"):
            doctrine_tick = int(prior.get("doctrine_tick") or 0)
            if doctrine_tick > 0 and doctrine_tick <= tick:
                current["doctrine"] = prior["doctrine"]
                current["doctrine_tick"] = doctrine_tick
                if prior.get("income_strategy"):
                    current["income_strategy"] = prior["income_strategy"]
        maps[key] = current
    current.setdefault("first_seen_tick", tick)
    current["last_seen_tick"] = tick
    current["known_colonist_ids"] = sorted(present | (set() if restarted or replaced_roster else known))
    return current


def decode_terrain(data: dict[str, Any]) -> tuple[int, int, list[str]]:
    width = int(data.get("width") or 0)
    height = int(data.get("height") or 0)
    palette = list(map(str, data.get("palette") or []))
    encoded = data.get("grid") or []
    cells: list[str] = []
    for index in range(0, len(encoded), 2):
        run = int(encoded[index])
        palette_index = int(encoded[index + 1])
        name = palette[palette_index] if 0 <= palette_index < len(palette) else "Unknown"
        cells.extend([name] * run)
    if width <= 0 or height <= 0 or len(cells) != width * height:
        raise ValueError("Invalid terrain grid returned by RIMAPI")
    return width, height, cells


def power_conduit_route(development: dict[str, Any], target: dict[str, int],
                        terrain: dict[str, Any]) -> list[dict[str, int]] | None:
    """Route continuous cable from a producing power net to a consumer."""
    power = development.get("power_info") or {}
    try:
        width, height, cells = decode_terrain(terrain)
    except (ValueError, TypeError, IndexError):
        return None
    cable_defs = {"PowerConduit", "HiddenConduit", "WaterproofConduit"}
    cables = set()
    cable_nets: dict[tuple[int, int], int] = {}
    blocked = set()
    for row in list(development.get("buildings") or []) + list(development.get("construction_projects") or []):
        if not isinstance(row, dict):
            continue
        pos = row.get("position") or {}
        if pos.get("x") is None or pos.get("z") is None:
            continue
        x, z = int(pos["x"]), int(pos["z"])
        name = str(row.get("def") or row.get("def_name") or "")
        if name in cable_defs:
            cables.add((x, z))
            if row.get("power_net_id") is not None:
                cable_nets[(x, z)] = int(row["power_net_id"])
        elif name not in {"Wall", "Door"} and not name.endswith("Floor") and name not in {"Concrete", "Flagstone", "PavedTile"}:
            size = row.get("size") or {}
            blocked.update((x + dx, z + dz)
                           for dx in range(max(1, int(size.get("x") or 1)))
                           for dz in range(max(1, int(size.get("z") or 1))))
    # Use actual net identity when RIMAPI exposes it. A cable across a wall
    # can be nearby without sharing the generator's electrical network.
    active_sources = {"WoodFiredGenerator", "SolarGenerator", "WindTurbine",
                      "WatermillGenerator", "GeothermalGenerator"}
    active_sources.update(str(row.get("def_name")) for row in development.get("building_catalog") or []
                          if row.get("is_power_generator"))
    if int(power.get("currently_stored_power") or 0) >= 50:
        active_sources.add("Battery")
    generators = [(int((row.get("position") or {}).get("x") or -1000),
                   int((row.get("position") or {}).get("z") or -1000),
                   row.get("power_net_id"))
                  for row in development.get("buildings") or []
                  if str(row.get("def") or "") in active_sources]
    if (int(power.get("current_power") or 0) <= 0
            and int(power.get("currently_stored_power") or 0) <= 0
            and not any(net is not None for _, _, net in generators)):
        return None
    live_nets = {int(net) for _, _, net in generators if net is not None}
    target_building = next((row for row in development.get("buildings") or []
                            if row.get("requires_power")
                            and int((row.get("position") or {}).get("x") or -1) == int(target["x"])
                            and int((row.get("position") or {}).get("z") or -1) == int(target["z"])), None)
    if target_building and target_building.get("power_net_id") in live_nets:
        return []
    source = {cell for cell in cables
              if ((cell in cable_nets and cable_nets[cell] in live_nets) if live_nets else
                  any((cell[0] - gx) ** 2 + (cell[1] - gz) ** 2 <= 4
                      for gx, gz, _ in generators))}
    if not source:
        source = {(gx, gz) for gx, gz, _ in generators
                  if 1 <= gx < width - 1 and 1 <= gz < height - 1}
    if not source:
        return None
    connected = set(source)
    pending = deque(source)
    while pending:
        x, z = pending.popleft()
        for adjacent in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if adjacent in cables and adjacent not in connected:
                connected.add(adjacent)
                pending.append(adjacent)
    tx, tz = int(target["x"]), int(target["z"])
    if any((x - tx) ** 2 + (z - tz) ** 2 <= 1 for x, z in connected):
        return []
    forbidden_terrain = {"Marsh", "DeepWater", "ShallowWater", "MovingWater",
                         "OceanDeep", "OceanShallow", "Mud", "Ice"}
    route_queue = deque(sorted(connected, key=lambda p: (p[0] - tx) ** 2 + (p[1] - tz) ** 2))
    previous: dict[tuple[int, int], tuple[int, int] | None] = {cell: None for cell in connected}
    endpoint = None
    while route_queue:
        x, z = route_queue.popleft()
        if (x - tx) ** 2 + (z - tz) ** 2 <= 1:
            endpoint = (x, z)
            break
        for adjacent in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            ax, az = adjacent
            if (not 1 <= ax < width - 1 or not 1 <= az < height - 1
                    or adjacent in previous or adjacent in blocked
                    or cells[az * width + ax] in forbidden_terrain):
                continue
            previous[adjacent] = (x, z)
            route_queue.append(adjacent)
    if endpoint is None:
        return None
    route = []
    cursor = endpoint
    while cursor not in connected:
        route.append({"x": cursor[0], "z": cursor[1]})
        cursor = previous[cursor]
    route.reverse()
    return route if len(route) <= 80 else None


def wired_heater_blueprint(target: dict[str, int], route: list[dict[str, int]],
                           *, include_heater: bool) -> tuple[dict[str, int], dict[str, Any]]:
    points = list(route) + ([target] if include_heater else [])
    if not points:
        raise ValueError("Empty heater wiring plan")
    x0 = min(int(point["x"]) for point in points)
    z0 = min(int(point["z"]) for point in points)
    x1 = max(int(point["x"]) for point in points)
    z1 = max(int(point["z"]) for point in points)
    items = [building("PowerConduit", int(point["x"]) - x0, int(point["z"]) - z0)
             for point in route]
    if include_heater:
        items.append(building("Heater", int(target["x"]) - x0, int(target["z"]) - z0))
    return position(x0, z0), blueprint(items, x1 - x0 + 1, z1 - z0 + 1)


def find_terrain_rect(
    terrain: dict[str, Any],
    center: dict[str, int],
    rect_width: int,
    rect_height: int,
    allowed: set[str],
    radius: int = 70,
    blocked: set[tuple[int, int]] | None = None,
    clearance: int = 0,
) -> dict[str, int] | None:
    width, height, cells = decode_terrain(terrain)
    margin_x = 5 if width > rect_width + 10 else 0
    margin_z = 5 if height > rect_height + 10 else 0
    min_x = max(margin_x, center["x"] - radius)
    max_x = min(width - rect_width - margin_x, center["x"] + radius)
    min_z = max(margin_z, center["z"] - radius)
    max_z = min(height - rect_height - margin_z, center["z"] + radius)
    candidates: list[tuple[int, int, int]] = []
    blocked = blocked or set()
    for z in range(min_z, max_z + 1):
        for x in range(min_x, max_x + 1):
            if blocked and any(
                (bx, bz) in blocked
                for bz in range(z - clearance, z + rect_height + clearance)
                for bx in range(x - clearance, x + rect_width + clearance)
            ):
                continue
            valid = True
            for dz in range(rect_height):
                row = (z + dz) * width
                if any(cells[row + x + dx] not in allowed for dx in range(rect_width)):
                    valid = False
                    break
            if valid:
                distance = (x - center["x"]) ** 2 + (z - center["z"]) ** 2
                candidates.append((distance, x, z))
    if not candidates:
        return None
    _, x, z = min(candidates)
    return {"x": x, "z": z}


def architecture_occupied_cells(development: dict[str, Any], map_state: dict[str, Any]) -> set[tuple[int, int]]:
    """Reserve live structures, issued rooms, and a standoff from sealed ruins."""
    occupied: set[tuple[int, int]] = set()
    for row in (list(development.get("buildings") or [])
                + list(development.get("construction_projects") or [])):
        pos = row.get("position") or {}
        if "x" not in pos or "z" not in pos:
            continue
        size = row.get("size") or {}
        for dx in range(max(1, int(size.get("x") or 1))):
            for dz in range(max(1, int(size.get("z") or 1))):
                occupied.add((int(pos["x"]) + dx, int(pos["z"]) + dz))
    # Loose stone/slag chunks are not edifices in terrain.edifice_grid, but
    # they can block a campfire's interaction cell and prevent whole layouts
    # from placing. Reserve their cells until a hauler actually clears them.
    for row in development.get("things") or []:
        if not str(row.get("def_name") or "").startswith("Chunk"):
            continue
        pos = row.get("position") or {}
        if pos.get("x") is not None and pos.get("z") is not None:
            occupied.add((int(pos["x"]), int(pos["z"])))
    for project in map_state.get("architecture_projects") or []:
        pos = project.get("origin") or {}
        if "x" not in pos or "z" not in pos:
            continue
        for dx in range(max(1, int(project.get("width") or 1))):
            for dz in range(max(1, int(project.get("height") or 1))):
                occupied.add((int(pos["x"]) + dx, int(pos["z"]) + dz))
    # A construction site beside a sealed Ancient Danger can expose it long
    # before Laya intentionally chooses to open it. The room is visible in the
    # map API even when its contents are still hidden from the player.
    for room in development.get("rooms") or []:
        if (room.get("touches_map_edge") or not room_is_ancient_danger(room)
                or int(room.get("cells_count") or 0) > 500):
            continue
        lower, upper = room.get("min") or {}, room.get("max") or {}
        if any(key not in lower or key not in upper for key in ("x", "z")):
            continue
        for x in range(int(lower["x"]) - 12, int(upper["x"]) + 13):
            for z in range(int(lower["z"]) - 12, int(upper["z"]) + 13):
                occupied.add((x, z))
    return occupied


def find_clear_layout_site(client: bridge.RimApiClient, map_id: int,
                           desired: dict[str, int], layout: dict[str, Any],
                           development: dict[str, Any], map_state: dict[str, Any],
                           *, radius: int = 30) -> dict[str, int] | None:
    """Find stable ground without old plans, natural edifices or trees."""
    terrain = client.get("/api/v1/map/terrain", map_id=map_id)
    blocked = architecture_occupied_cells(development, map_state)
    blocked.update((int((plant.get("position") or {}).get("x") or -1),
                    int((plant.get("position") or {}).get("z") or -1))
                   for plant in development.get("plants") or []
                   if "Tree" in str(plant.get("def_name") or ""))
    edifice_grid = terrain.get("edifice_grid") or []
    if edifice_grid:
        width, height, _ = decode_terrain(terrain)
        edifice_cells = []
        for index in range(0, len(edifice_grid), 2):
            edifice_cells.extend([int(edifice_grid[index + 1])] * int(edifice_grid[index]))
        if len(edifice_cells) == width * height:
            blocked.update((index % width, index // width)
                           for index, occupied in enumerate(edifice_cells) if occupied)
    allowed = {str(name) for name in terrain.get("palette") or [] if
               str(name) in {"Soil", "SoilRich", "Gravel", "Sand"}
               or str(name).startswith(("Rough", "Smooth", "Flagstone", "Paved", "Concrete"))}
    return find_terrain_rect(terrain, desired, int(layout["width"]), int(layout["height"]),
                             allowed, radius=radius, blocked=blocked, clearance=2)


def can_fight(pawn: dict[str, Any]) -> bool:
    """Use actual disabled skills, not a healthy-headcount proxy for defense."""
    skills = pawn.get("skills") or {}
    fighting = [skills[name] for name in ("Shooting", "Melee")
                if isinstance(skills.get(name), dict)]
    return not fighting or any(not skill.get("disabled") for skill in fighting)


def find_dry_starter_site(terrain: dict[str, Any], center: dict[str, int],
                          development: dict[str, Any] | None = None,
                          map_state: dict[str, Any] | None = None) -> dict[str, int] | None:
    """Keep the first house dry, clear of other plans, and accessible on all sides."""
    dry_ground = {str(name) for name in terrain.get("palette") or [] if (
        str(name) in {"Soil", "SoilRich", "Gravel", "Sand"}
        or str(name).startswith(("Rough", "Smooth", "Flagstone", "Paved", "Concrete"))
    )}
    blocked = architecture_occupied_cells(development or {}, map_state or {})
    blocked.update((int((plant.get("position") or {})["x"]),
                    int((plant.get("position") or {})["z"]))
                   for plant in (development or {}).get("plants") or []
                   if "Tree" in str(plant.get("def_name") or "")
                   and (plant.get("position") or {}).get("x") is not None
                   and (plant.get("position") or {}).get("z") is not None)
    edifice_grid = terrain.get("edifice_grid") or []
    if edifice_grid:
        width, height, _ = decode_terrain(terrain)
        edifice_cells = []
        for index in range(0, len(edifice_grid), 2):
            edifice_cells.extend([int(edifice_grid[index + 1])] * int(edifice_grid[index]))
        if len(edifice_cells) != width * height:
            raise ValueError("Invalid edifice grid returned by RIMAPI")
        blocked.update((index % width, index // width)
                       for index, occupied in enumerate(edifice_cells) if occupied)
    return find_terrain_rect(terrain, center, 7, 7, dry_ground, radius=45,
                             blocked=blocked, clearance=2)


def find_starter_food_site(terrain: dict[str, Any], anchor: dict[str, int],
                           development: dict[str, Any], map_state: dict[str, Any]) -> dict[str, int] | None:
    """Keep the temporary food zone off the future bedroom and growing field."""
    dry_ground = {str(name) for name in terrain.get("palette") or [] if (
        str(name) in {"Soil", "SoilRich", "Gravel", "Sand"}
        or str(name).startswith(("Rough", "Smooth", "Flagstone", "Paved", "Concrete"))
    )}
    blocked = architecture_occupied_cells(development, map_state)
    blocked.update((x, z)
                   for x in range(int(anchor["x"]) - 1, int(anchor["x"]) + 8)
                   for z in range(int(anchor["z"]) - 1, int(anchor["z"]) + 8))
    for plant in development.get("plants") or []:
        if str(plant.get("def_name") or "") not in {"Plant_Rice", "Plant_Potato", "Plant_Corn"}:
            continue
        pos = plant.get("position") or {}
        if pos.get("x") is not None and pos.get("z") is not None:
            blocked.add((int(pos["x"]), int(pos["z"])))
    return find_terrain_rect(terrain, {"x": int(anchor["x"]) + 9,
                                    "z": int(anchor["z"]) + 1},
                             4, 4, dry_ground, radius=16, blocked=blocked, clearance=1)


def open_recreation_site(terrain: dict[str, Any], anchor: dict[str, int],
                         development: dict[str, Any],
                         desired: dict[str, int] | None = None) -> dict[str, int] | None:
    """Find a dry, unoccupied outdoor patch for a cheap recreation pin."""
    width, height, cells = decode_terrain(terrain)
    palette = set(terrain.get("palette") or [])
    stable = {name for name in palette if name in {"Soil", "SoilRich", "Gravel", "Sand"}
              or name.startswith(("Rough", "Smooth", "Flagstone", "Paved", "Concrete"))}
    occupied: set[tuple[int, int]] = set()
    for row in ((development.get("buildings") or []) + (development.get("construction_projects") or [])
                + (development.get("things") or [])):
        if not isinstance(row, dict) or not isinstance(row.get("position"), dict):
            continue
        pos = row["position"]
        x, z = int(pos.get("x") or 0), int(pos.get("z") or 0)
        size = row.get("size") or {}
        for dx in range(max(1, int(size.get("x") or 1))):
            for dz in range(max(1, int(size.get("z") or 1))):
                occupied.add((x + dx, z + dz))
    desired_x = int(desired["x"]) if desired is not None else int(anchor["x"]) + 8
    desired_z = int(desired["z"]) if desired is not None else int(anchor["z"]) + 8
    candidates = []
    for z in range(max(2, desired_z - 18), min(height - 2, desired_z + 19)):
        for x in range(max(2, desired_x - 18), min(width - 2, desired_x + 19)):
            patch = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
            if any((px, pz) in occupied or cells[pz * width + px] not in stable
                   for px, pz in patch):
                continue
            candidates.append(((x - desired_x) ** 2 + (z - desired_z) ** 2, x, z))
    if not candidates:
        return None
    _, x, z = min(candidates)
    return {"x": x, "z": z}


def open_bed_site(terrain: dict[str, Any], anchor: dict[str, int],
                  development: dict[str, Any],
                  excluded: set[tuple[int, int]] | None = None) -> dict[str, int] | None:
    """Place a 1x2 bed near the shelter without overlapping existing objects."""
    width, height, cells = decode_terrain(terrain)
    stable = {str(name) for name in terrain.get("palette") or [] if (
        str(name) in {"Soil", "SoilRich", "Gravel", "Sand"}
        or str(name).startswith(("Rough", "Smooth", "Flagstone", "Paved", "Concrete"))
    )}
    occupied: set[tuple[int, int]] = set()
    for row in ((development.get("buildings") or []) +
                (development.get("construction_projects") or []) +
                (development.get("things") or [])):
        if not isinstance(row, dict) or not isinstance(row.get("position"), dict):
            continue
        pos = row["position"]
        size = row.get("size") or {}
        for dx in range(max(1, int(size.get("x") or 1))):
            for dz in range(max(1, int(size.get("z") or 1))):
                occupied.add((int(pos.get("x") or 0) + dx, int(pos.get("z") or 0) + dz))
    desired = (int(anchor["x"]) + 1, int(anchor["z"]) + 10)
    excluded = excluded or set()
    options = []
    for z in range(max(2, desired[1] - 12), min(height - 3, desired[1] + 13)):
        for x in range(max(2, desired[0] - 12), min(width - 2, desired[0] + 13)):
            footprint = ((x, z), (x, z + 1))
            if (x, z) not in excluded and all(cell not in occupied and cells[cell[1] * width + cell[0]] in stable
                   for cell in footprint):
                options.append(((x - desired[0]) ** 2 + (z - desired[1]) ** 2, x, z))
    if not options:
        return None
    _, x, z = min(options)
    return {"x": x, "z": z}


def collect_development(client: bridge.RimApiClient, snapshot: dict[str, Any]) -> dict[str, Any]:
    warnings = snapshot.setdefault("warnings", [])
    map_id = snapshot["map"]["id"]
    buildings = bridge.safe_get(client, "/api/v1/map/buildings", warnings, map_id=map_id) or []
    power_info = bridge.safe_get(client, "/api/v1/map/power/info", warnings, map_id=map_id) or {}
    rooms_raw = bridge.safe_get(client, "/api/v1/map/rooms", warnings, map_id=map_id) or {}
    zones_raw = bridge.safe_get(client, "/api/v1/map/zones", warnings, map_id=map_id) or {}
    finished_raw = bridge.safe_get(client, "/api/v1/research/finished", warnings) or {}
    current = bridge.safe_get(client, "/api/v1/research/progress", warnings) or {}
    research_tree_raw = bridge.safe_get(client, "/api/v1/research/tree", warnings) or {}
    work_tables = bridge.safe_get(client, "/api/v1/map/work-tables", warnings, map_id=map_id) or []
    forbidden = bridge.safe_get(client, "/api/v1/things/forbidden", warnings, map_id=map_id) or []
    things = bridge.safe_get(client, "/api/v1/map/things", warnings, map_id=map_id) or []
    plants = bridge.safe_get(client, "/api/v1/map/plants", warnings, map_id=map_id) or []
    settlements = bridge.safe_get(client, "/api/v1/world/settlements", warnings) or []
    trade_destinations = bridge.safe_get(client, "/api/v1/world/trade/destinations", warnings, map_id=map_id) or []
    trade_opportunities = bridge.safe_get(client, "/api/v1/trade/opportunities", warnings, map_id=map_id) or []
    raid_destinations = bridge.safe_get(client, "/api/v1/world/raid/destinations", warnings, map_id=map_id) or []
    caravans = bridge.safe_get(client, "/api/v1/world/caravans", warnings) or []
    quests = bridge.safe_get(client, "/api/v1/quests", warnings, map_id=map_id) or []
    ores = bridge.safe_get(client, "/api/v1/map/ore", warnings, map_id=map_id) or {}
    storage = bridge.safe_get(client, "/api/v1/resources/storages/summary", warnings, map_id=map_id) or {}
    weather = bridge.safe_get(client, "/api/v1/map/weather", warnings, map_id=map_id) or {}
    fire_situation = bridge.safe_get(client, "/api/v1/map/fire/situation", warnings, map_id=map_id) or {}
    farm = bridge.safe_get(client, "/api/v1/map/farm/summary", warnings, map_id=map_id) or {}
    projects_raw = bridge.safe_get(client, "/api/v1/builder/projects", warnings, map_id=map_id) or {}
    ideology = bridge.safe_get(client, "/api/v1/colony/ideology", warnings) or {}
    work_types = bridge.safe_get(client, "/api/v1/work-list/details", warnings) or []
    building_catalog = bridge.safe_get(client, "/api/v1/buildings/catalog", warnings) or []
    royalty = bridge.safe_get(client, "/api/v1/colony/royalty", warnings) or {}
    active_mods = bridge.safe_get(client, "/api/v1/mods/list", warnings) or []
    tile_id = snapshot.get("map", {}).get("tile_id")
    tile_details = bridge.safe_get(client, "/api/v1/world/tile/details", warnings, id=int(tile_id)) if tile_id is not None else {}
    zones = zones_raw.get("zones", []) if isinstance(zones_raw, dict) else []
    rooms = rooms_raw.get("rooms", []) if isinstance(rooms_raw, dict) else []
    finished = finished_raw.get("finished_projects", []) if isinstance(finished_raw, dict) else []
    corpses = [
        row for row in things if isinstance(row, dict)
        and any(str(category) in {"CorpsesHumanlike", "CorpsesAnimal"} for category in row.get("categories") or [])
    ]
    item_counts = Counter()
    trade_value = 0.0
    for row in things:
        if not isinstance(row, dict) or row.get("is_forbidden"):
            continue
        amount = max(1, int(row.get("stack_count") or 1))
        item_counts[str(row.get("def_name") or "")] += amount
        trade_value += float(row.get("market_value") or 0.0) * amount
    snapshot["development"] = {
        "building_counts": dict(Counter(str(row.get("def")) for row in buildings if isinstance(row, dict))),
        "buildings": buildings,
        "power_info": power_info if isinstance(power_info, dict) else {},
        "rooms": rooms,
        "zones": zones,
        "finished_research": finished,
        "current_research": current,
        "research_tree": research_tree_raw.get("projects", []) if isinstance(research_tree_raw, dict) else [],
        "work_tables": work_tables,
        "forbidden": forbidden,
        "things": things,
        "plants": plants,
        "corpses": corpses,
        "item_counts": dict(item_counts),
        "trade_value": round(trade_value, 1),
        "settlements": settlements,
        "trade_destinations": trade_destinations,
        "trade_opportunities": trade_opportunities,
        "raid_destinations": raid_destinations,
        "caravans": caravans,
        "quests": quests,
        "ores": ores,
        "storage": storage,
        "weather": weather or {},
        "fire_situation": fire_situation if isinstance(fire_situation, dict) else {},
        "farm": farm or {},
        "tile_details": tile_details or {},
        "construction_projects": projects_raw.get("projects", []) if isinstance(projects_raw, dict) else [],
        "ideology": ideology if isinstance(ideology, dict) else {},
        "work_types": work_types if isinstance(work_types, list) else [],
        "building_catalog": building_catalog if isinstance(building_catalog, list) else [],
        "building_catalog_summary": architect.summarize_catalog(building_catalog if isinstance(building_catalog, list) else []),
        "royalty": royalty if isinstance(royalty, dict) else {},
        "active_mods": active_mods if isinstance(active_mods, list) else [],
    }
    snapshot["development"]["profession_context"] = professions.profession_context(
        snapshot.get("colonists", []), snapshot["development"]["work_types"]
    )
    return snapshot


def issued_recently(map_state: dict[str, Any], name: str, tick: int, retry_ticks: int = 60000) -> bool:
    issued = map_state.setdefault("issued", {})
    value = issued.get(name)
    if value is None:
        return False
    try:
        age = tick - int(value)
    except (TypeError, ValueError):
        issued.pop(name, None)
        return False
    if age < 0:
        # Loading an older save must not leave orders from the abandoned future
        # permanently suppressing food, construction, hauling or medical work.
        issued.pop(name, None)
        return False
    return age < retry_ticks


def reconcile_issued_timeline(map_state: dict[str, Any], tick: int) -> list[str]:
    """Discard future issue markers after a save rollback and report what changed."""
    issued = map_state.setdefault("issued", {})
    removed: list[str] = []
    for name, value in list(issued.items()):
        try:
            invalid = int(value) > tick
        except (TypeError, ValueError):
            invalid = True
        if invalid:
            removed.append(str(name))
            issued.pop(name, None)
    return removed


def relevant_forbidden(snapshot: dict[str, Any], radius: int = 80) -> list[dict[str, Any]]:
    mobile_pawns = [pawn for pawn in snapshot.get("colonists", [])
                    if not pawn.get("downed") and not pawn.get("in_mental_state")
                    and (pawn.get("position") or {}).get("x") is not None
                    and (pawn.get("position") or {}).get("z") is not None]
    radius_squared = radius * radius
    result = []
    for thing in snapshot.get("development", {}).get("forbidden", []):
        categories = {str(value) for value in thing.get("categories") or []}
        if any(category.startswith("Corpses") for category in categories):
            continue
        pos = thing.get("position") or {}
        if pos.get("x") is None or pos.get("z") is None:
            continue
        x, z = int(pos["x"]), int(pos["z"])
        if any((x - int((pawn.get("position") or {})["x"])) ** 2
               + (z - int((pawn.get("position") or {})["z"])) ** 2 <= radius_squared
               and not bridge.combat_planner.errand_exposed(snapshot, pos, pawn.get("position"))
               for pawn in mobile_pawns):
            result.append(thing)
    return result


def forbidden_supply_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    """Amounts the colony already owns but cannot use until unforbidden."""
    counts = {"meals": 0, "wood": 0, "steel": 0, "guns": 0, "medicine": 0}
    for thing in relevant_forbidden(snapshot):
        name = str(thing.get("def_name") or "")
        categories = {str(value) for value in thing.get("categories") or []}
        amount = max(0, int(thing.get("stack_count") or 0))
        if name == "MealSurvivalPack" or "FoodMeals" in categories:
            counts["meals"] += amount
        elif name == "WoodLog":
            counts["wood"] += amount
        elif name == "Steel":
            counts["steel"] += amount
        elif name.startswith("Gun_"):
            counts["guns"] += amount
        elif name.startswith("Medicine"):
            counts["medicine"] += amount
    return counts


def is_edible_wild_harvest(thing_def: str) -> bool:
    """Separate immediate food from herbs/drugs in the wild-harvest menu."""
    name = thing_def.lower()
    return name.startswith("raw") or any(token in name for token in ("berry", "fruit", "cocoa"))


def available_meals(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Actual, unlocked meal stacks, not the map-wide nutrition estimate."""
    return [row for row in (snapshot.get("development") or {}).get("things") or []
            if isinstance(row, dict) and "FoodMeals" in (row.get("categories") or [])
            and not row.get("is_forbidden") and row.get("thing_id") is not None
            and not bridge.combat_planner.errand_exposed(snapshot, row.get("position"))
            and int(row.get("stack_count") or 0) > 0]


def squared_distance(first: dict[str, Any], second: dict[str, Any]) -> int:
    return (int(first.get("x") or 0) - int(second.get("x") or 0)) ** 2 + \
        (int(first.get("z") or 0) - int(second.get("z") or 0)) ** 2


def legacy_freezer_entrance(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Recognize the exact old 6x6 freezer whose door was overbuilt by a wall."""
    buildings = (snapshot.get("development") or {}).get("buildings") or []
    at = {(int((row.get("position") or {}).get("x", -1)),
           int((row.get("position") or {}).get("z", -1))): row
          for row in buildings if isinstance(row, dict)}
    meals = available_meals(snapshot)
    for cooler in buildings:
        if cooler.get("def") != "Cooler":
            continue
        cooler_pos = cooler.get("position") or {}
        origin_x = int(cooler_pos.get("x") or 0) - 5
        origin_z = int(cooler_pos.get("z") or 0) - 2
        doorway = (origin_x + 3, origin_z + 5)
        expected = ({(origin_x + x, origin_z) for x in range(6)}
                    | {(origin_x + x, origin_z + 5) for x in range(6) if x != 3}
                    | {(origin_x, origin_z + z) for z in range(1, 5)}
                    | {(origin_x + 5, origin_z + z) for z in (1, 3, 4)})
        if not all((at.get(cell) or {}).get("def") == "Wall" for cell in expected):
            continue
        if not any(origin_x + 1 <= int((meal.get("position") or {}).get("x") or -1) <= origin_x + 4
                   and origin_z + 1 <= int((meal.get("position") or {}).get("z") or -1) <= origin_z + 4
                   for meal in meals):
            continue
        doorway_building = at.get(doorway) or {}
        if doorway_building.get("def") == "Door":
            continue
        if doorway_building and doorway_building.get("def") != "Wall":
            continue
        return {"position": position(*doorway), "status": "sealed" if doorway_building else "open",
                "wall_id": doorway_building.get("id")}
    return None


def reachable_meals(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Do not direct an Ingest job through a known wall-only freezer."""
    meals = available_meals(snapshot)
    freezer = legacy_freezer_entrance(snapshot)
    if not freezer or freezer["status"] != "sealed":
        return meals
    doorway = freezer["position"]
    origin_x, origin_z = int(doorway["x"]) - 3, int(doorway["z"]) - 5
    return [meal for meal in meals
            if not (origin_x + 1 <= int((meal.get("position") or {}).get("x", -1)) <= origin_x + 4
                    and origin_z + 1 <= int((meal.get("position") or {}).get("z", -1)) <= origin_z + 4)]


def sealed_colonist_walls(snapshot: dict[str, Any], colonist: dict[str, Any]) -> list[dict[str, Any]]:
    """Find a pawn boxed into one cell by four completed walls.

    Nearby meals alone cannot prove path access. This exact geometry is a
    reliable emergency signal without assuming that every map obstacle is
    represented in the building inventory.
    """
    pos = colonist.get("position") or {}
    if pos.get("x") is None or pos.get("z") is None:
        return []
    x, z = int(pos["x"]), int(pos["z"])
    walls = {
        (int((row.get("position") or {}).get("x", -1)),
         int((row.get("position") or {}).get("z", -1))): row
        for row in (snapshot.get("development") or {}).get("buildings") or []
        if isinstance(row, dict) and row.get("def") == "Wall" and row.get("id") is not None
    }
    adjacent = [walls.get((x + dx, z + dz)) for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1))]
    return [wall for wall in adjacent if wall is not None] if all(adjacent) else []


def corpse_rows(snapshot: dict[str, Any], category: str | None = None) -> list[dict[str, Any]]:
    rows = snapshot.get("development", {}).get("corpses", [])
    if category is None:
        return list(rows)
    return [row for row in rows if category in (row.get("categories") or [])]


def forbidden_corpses(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    hostiles = bridge.combat_planner.live_hostiles(snapshot)
    mobile = [pawn for pawn in snapshot.get("colonists", [])
              if not pawn.get("downed") and not pawn.get("in_mental_state")
              and pawn.get("position")]
    return [row for row in corpse_rows(snapshot) if row.get("is_forbidden")
            and (not hostiles or any(not bridge.combat_planner.errand_exposed(
                snapshot, row.get("position"), pawn.get("position")) for pawn in mobile))]


def hazardous_haul_items(snapshot: dict[str, Any], things: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Loose items beside live enemies must not become automatic hauling jobs."""
    if not bridge.combat_planner.live_hostiles(snapshot):
        return []
    return [row for row in things if isinstance(row, dict)
            and row.get("thing_id") is not None and not row.get("is_forbidden")
            and bridge.combat_planner.errand_exposed(snapshot, row.get("position"))]


def unsafe_active_errand_pawns(snapshot: dict[str, Any],
                               things: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An already issued pickup can remain dangerous after its item is forbidden."""
    by_id = {int(row["thing_id"]): row for row in things
             if isinstance(row, dict) and row.get("thing_id") is not None}
    errands = {"equip", "haultocell", "haultocontainer", "ingest", "takeinventory"}
    return [pawn for pawn in (snapshot.get("combat") or {}).get("colonists") or []
            if not pawn.get("is_dead") and not pawn.get("is_downed")
            and str(pawn.get("current_job") or "").lower() in errands
            and pawn.get("current_job_target_id") is not None
            and int(pawn["current_job_target_id"]) in by_id
            and bridge.combat_planner.errand_exposed(
                snapshot, by_id[int(pawn["current_job_target_id"])].get("position"),
                pawn.get("position"))]


def run_hazard_exclusion_cycle(client: bridge.RimApiClient, snapshot: dict[str, Any],
                               log_path: Path,
                               map_state: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Forbid exposed pickups and release our bans once the item becomes safe."""
    tracked = map_state.setdefault("hazard_forbidden", {}) if map_state is not None else {}
    if not bridge.combat_planner.live_hostiles(snapshot) and not tracked:
        return None
    map_id = int((snapshot.get("map") or {}).get("id") or 0)
    things = client.get("/api/v1/map/things", map_id=map_id) or []
    things = things if isinstance(things, list) else []
    by_id = {int(row["thing_id"]): row for row in things if isinstance(row, dict)
             and row.get("thing_id") is not None}
    released = []
    for key in list(tracked):
        row = by_id.get(int(key))
        if row is None or not row.get("is_forbidden"):
            tracked.pop(key, None)
        elif not bridge.combat_planner.errand_exposed(snapshot, row.get("position")):
            released.append(int(key))
    release_response = None
    if released:
        release_response = client.post("/api/v1/things/set-forbidden", body={
            "map_id": map_id, "thing_ids": sorted(released), "forbidden": False,
        })
        if release_response.get("success", True):
            for item_id in released:
                tracked.pop(str(item_id), None)
    rows = hazardous_haul_items(snapshot, things)
    unsafe_pawns = unsafe_active_errand_pawns(snapshot, things)
    if not rows and not unsafe_pawns and not released:
        return None
    ids = sorted({int(row["thing_id"]) for row in rows})
    response = (client.post("/api/v1/things/set-forbidden", body={
        "map_id": map_id, "thing_ids": ids, "forbidden": True,
    }) if ids else None)
    if ids and response.get("success", True):
        tracked.update({str(item_id): True for item_id in ids})
    retreats = []
    stopped = []
    for pawn in unsafe_pawns:
        if not bridge.combat_planner.errand_exposed(snapshot, pawn.get("position")):
            # Cancel a dangerous route without moving a currently safe helper
            # farther from bleeding patients or normal colony work.
            stop_response = client.post("/api/v1/pawn/job", body={
                "pawn_id": int(pawn["id"]), "job_def": "Wait_MaintainPosture",
            })
            stopped.append({"pawn_id": int(pawn["id"]), "response": stop_response})
            continue
        choice = ("withdraw_and_regroup" if pawn.get("can_fight", True) and pawn.get("weapon_def")
                  else "civilian_retreat")
        action = bridge.plan_action(snapshot, {
            "choice": choice, "selected_fighter_ids": [int(pawn["id"])],
        })
        commands = [command for command in action.get("commands") or []
                    if command["endpoint"] == "/api/v1/combat/tactic"]
        if commands:
            retreat_response = client.post(commands[0]["endpoint"], body=commands[0]["body"])
            retreats.append({"pawn_id": int(pawn["id"]), "choice": choice,
                             "response": retreat_response})
    record = {"timestamp": bridge.utc_now(), "mode": "hazard-guard",
              "items": [{"id": int(row["thing_id"]), "def": row.get("def_name"),
                         "position": row.get("position")} for row in rows],
              "result": response, "released": sorted(released),
              "release_result": release_response,
              "retreats": retreats, "stopped": stopped}
    bridge.append_log(log_path, record)
    return record


def animal_needs_tending(animal: dict[str, Any]) -> bool:
    """True only when the game reports a treatable injury or active bleeding."""
    return bool(animal.get("tendable_now")) or float(animal.get("bleeding_rate") or 0.0) > 0.0


def animal_needs_assisted_feeding(animal: dict[str, Any]) -> bool:
    """Only patients that cannot walk to food should receive a forced feed job."""
    current_job = str(animal.get("current_job") or "").lower()
    is_patient = bool(animal.get("downed")) or any(
        marker in current_job for marker in ("laydown", "patient", "bedrest")
    )
    return is_patient and bridge.first_number(animal.get("hunger"), 1.0) < 0.35


def colonist_needs_assisted_feeding(colonist: dict[str, Any]) -> bool:
    """A conscious mobile colonist should reserve the normal self-feeding job."""
    return bool(colonist.get("downed") or colonist.get("is_downed")) and bridge.first_number(colonist.get("hunger"), 1.0) < 0.35


def action_backoff_remaining(map_state: dict[str, Any], choice: str, now: float | None = None) -> float:
    """Return the real-time cooldown left for an action that recently failed."""
    failure = (map_state.get("action_failures") or {}).get(choice) or {}
    return max(0.0, float(failure.get("retry_after") or 0.0) - (time.time() if now is None else now))


def register_action_failure(
    map_state: dict[str, Any],
    choice: str,
    error: Exception | str,
    now: float | None = None,
) -> dict[str, Any]:
    """Persist bounded exponential backoff so one rejected order cannot become a loop."""
    current_time = time.time() if now is None else now
    failures = map_state.setdefault("action_failures", {})
    previous = failures.get(choice) or {}
    count = min(8, int(previous.get("count") or 0) + 1)
    cooldown = min(300.0, 30.0 * (2 ** (count - 1)))
    failure = {
        "count": count,
        "error": str(error)[:500],
        "failed_at": current_time,
        "retry_after": current_time + cooldown,
    }
    failures[choice] = failure
    return failure


def clear_action_failure(map_state: dict[str, Any], choice: str) -> None:
    failures = map_state.get("action_failures")
    if isinstance(failures, dict):
        failures.pop(choice, None)


def filter_backed_off_choices(
    map_state: dict[str, Any],
    choices: list[str] | dict[str, Any],
    *,
    prefix: str = "",
) -> tuple[list[str], dict[str, float]]:
    """Remove temporarily failing choices while preserving their remaining delay."""
    names = list(choices)
    blocked = {
        name: action_backoff_remaining(map_state, f"{prefix}{name}")
        for name in names
        if action_backoff_remaining(map_state, f"{prefix}{name}") > 0.0
    }
    return [name for name in names if name not in blocked], blocked


def available_sale_categories(snapshot: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for row in snapshot.get("development", {}).get("things", []):
        if row.get("is_forbidden"):
            continue
        name = str(row.get("def_name") or "")
        categories = " ".join(map(str, row.get("categories") or []))
        if name in {"Flake", "Yayo", "SmokeleafJoint"}: found.add("drugs")
        if "Apparel" in categories: found.add("apparel")
        if name.startswith("Sculpture") or installable_sculpture(row): found.add("art")
        if any(token in name for token in ("Wool", "Leather", "Milk")): found.add("animal_products")
        if name == "Chemfuel": found.add("chemfuel")
        if name in {"Gold", "Jade"}: found.add("precious")
        if name == "Beer": found.add("beer")
        if name in {"MealSurvivalPack", "Pemmican"}: found.add("travel_food")
        if name in {"RawCorn", "RawRice", "RawPotatoes", "AgaveFruit", "Berries"}: found.add("raw_food")
    plans = snapshot.get("development", {}).get("prisoner_plans") or {}
    prisoner_ids = {str(p.get("id")) for p in snapshot.get("combat", {}).get("prisoners", [])}
    if any(policy == "sell" and str(pawn_id) in prisoner_ids for pawn_id, policy in plans.items()):
        found.add("prisoners")
    return sorted(found)


def needs_cooking_fuel_reserve(snapshot: dict[str, Any]) -> bool:
    """A wood stove with raw ingredients still needs logs after its current fuel burns out."""
    dev = snapshot.get("development") or {}
    counts = dev.get("building_counts") or {}
    resources = (snapshot.get("map") or {}).get("resources") or {}
    return (int(resources.get("meals") or 0) <= max(30, len(snapshot.get("colonists") or []) * 12)
            and int(resources.get("raw_food") or 0) >= 40
            and int((dev.get("item_counts") or {}).get("WoodLog") or 0) < 100
            and any(int(counts.get(name) or 0) > 0 for name in ("Campfire", "FueledStove"))
            and int(counts.get("ElectricStove") or 0) == 0)


def action_description(name: str, snapshot: dict[str, Any]) -> str:
    if name == "build_butcher_spot":
        count = int((snapshot.get("development") or {}).get("butchery_gap") or 0)
        return (f"Place a free instant butcher spot beside {count} accessible animal carcass(es) "
                "and activate its forever bill. "
                "Without a station and bill, hauling and more hunting produce no meat; the carcasses may rot.")
    if name == "configure_food_bills" and any(
        row.get("thing_def") in {"ButcherSpot", "TableButcher"}
        for row in (snapshot.get("development") or {}).get("work_tables") or []
    ):
        return ("Add a forever butchering bill to the completed station so an enabled cook can turn "
                "stored animal carcasses into meat; also repair missing meal bills on cooking stations.")
    if name == "prioritize_plant_cutting":
        wood = int(((snapshot.get("development") or {}).get("item_counts") or {}).get("WoodLog") or 0)
        return ("Raise Plant Cutting work priority; this does not mark any trees to cut. "
                + ("Wood is zero: choose 'Cut nearby trees' to create the actual orders, "
                   "then workers can harvest and haul logs."
                   if wood == 0 else "Workers only cut plants already designated."))
    if name == "prioritize_construction":
        wood = int(((snapshot.get("development") or {}).get("item_counts") or {}).get("WoodLog") or 0)
        if wood == 0 and (snapshot.get("development") or {}).get("construction_projects"):
            return ("Raise Construction work priority, but wood is zero. Workers cannot finish wooden "
                    "walls or a campfire until nearby trees are designated, cut and hauled.")
    if name == "harvest_nearby_trees":
        dev = snapshot.get("development") or {}
        wood = int((dev.get("item_counts") or {}).get("WoodLog") or 0)
        projects = dev.get("construction_projects") or []
        if needs_cooking_fuel_reserve(snapshot):
            resources = (snapshot.get("map") or {}).get("resources") or {}
            return (f"Mark nearby mature trees for cooking fuel: {wood} spare wood, "
                    f"{int(resources.get('meals') or 0)} meals and {int(resources.get('raw_food') or 0)} raw food. "
                    "The campfire or fueled stove may stop without logs; cutting and hauling cost worker time. "
                    "Compare this with eating raw food or building an electric stove if available.")
        forecast = [float(value) for value in
                    (dev.get("weather") or {}).get("next_twelfth_average_temperatures") or []]
        cold_note = (f"; future five-day average can fall to {round(min(forecast))} C"
                     if forecast and min(forecast) < 5 else "")
        if dev.get("cold_threat"):
            generator_starved = (int((dev.get("building_counts") or {}).get("WoodFiredGenerator") or 0) > 0
                                 and int((dev.get("power_info") or {}).get("current_power") or 0) == 0)
            power_note = (" The wood-fired generator produces 0 W. A battery may run the heater "
                          "temporarily, but Hauling must refuel the generator before stored power is exhausted."
                          if generator_starved else "")
            return (f"Mark trees to cut for indoor heat: {wood} wood, {len(projects)} unfinished projects"
                    f"{cold_note}. Without logs a campfire cannot be built or refueled; cutting and hauling take labor."
                    + power_note)
        return (f"Cut nearby trees: {wood} wood for {len(projects)} unfinished projects"
                f"{cold_note}. An open house cannot protect sleepers from cold; tree cutting and hauling take labor.")
    if name in {"build_room_campfire", "build_room_heater", "connect_room_heater_power", "prioritize_thermal_project"}:
        cold = (snapshot.get("development") or {}).get("cold_threat") or {}
        heat = (snapshot.get("development") or {}).get("heat_threat") or {}
        patients = cold.get("patients") or heat.get("patients") or []
        patient_text = ", ".join(
            f"{patient.get('name')} {int(float(patient.get('severity') or 0) * 100)}%"
            for patient in patients[:2]
        )
        if name == "prioritize_thermal_project":
            wiring = (snapshot.get("development") or {}).get("power_connection_options") or {}
            return (f"{patient_text or 'Occupied beds'}: temperature injury is lethal at 100%. "
                    "Finish the existing cooler/heater blueprint in that room now; a blueprint changes no temperature. "
                    + ("An existing heater still needs its missing cable route before it can warm anyone. "
                       if wiring else "") +
                    "Choose an eligible builder and weigh other immediate danger.")
        if name == "build_room_campfire":
            return (f"Cold danger outside {cold.get('outside_c')} C; {patient_text or 'occupied beds'}; "
                    "place a 20-wood campfire inside a closed, roofed bedroom. It needs refueling and "
                    "can overheat a small room, but works without electricity.")
        if name == "connect_room_heater_power":
            options = (snapshot.get("development") or {}).get("power_connection_options") or {}
            lengths = [int(option.get("conduit_cost") or 0) for option in options.values()]
            return (f"Cold danger outside {cold.get('outside_c')} C; an existing heater has no cable connection. "
                    f"Connecting it needs {min(lengths) if lengths else '?'} steel and construction time. "
                    "Until both cable and heater are finished, the room will not warm.")
        options = (snapshot.get("development") or {}).get("heater_room_options") or {}
        lengths = [int(option.get("conduit_cost") or 0) for option in options.values()]
        return (f"Cold danger outside {cold.get('outside_c')} C; {patient_text or 'occupied beds'}; "
                "place an electric heater and a route to the live grid inside a closed bedroom. "
                f"It consumes 50 steel plus {min(lengths) if lengths else '?'} steel for cable, "
                "one component and 175 W. Both heater and cable need construction time.")
    if name == "build_passive_cooler":
        heat = (snapshot.get("development") or {}).get("heat_threat") or {}
        patients = heat.get("patients") or []
        patient_text = ", ".join(
            f"{patient.get('name')} {int(float(patient.get('severity') or 0) * 100)}% heatstroke"
            for patient in patients[:2]
        )
        return (f"Heat danger {heat.get('outside_c')} C; "
                + (f"{patient_text}; " if patient_text else "")
                + "choose an occupied room for a 50-wood passive cooler. It needs building and refueling; "
                  "without cooling a bedbound patient can die despite food and bandages.")
    if name == "hold_survival":
        projects = (snapshot.get("development") or {}).get("construction_projects") or []
        if projects:
            builders = sum(
                str(pawn.get("current_job") or "").lower().startswith(("construct", "build"))
                for pawn in snapshot.get("colonists") or []
            )
            return (f"Wait instead of assigning work: {len(projects)} building projects are unfinished and "
                    f"{builders} colonists are building right now. Waiting gives time to eat and sleep, "
                    "but it will not itself change work priorities or finish neglected projects.")
    if name == "prioritize_construction_project":
        projects = (snapshot.get("development") or {}).get("construction_project_options") or []
        heat = (snapshot.get("development") or {}).get("heat_threat") or {}
        if heat.get("patients") and any(row.get("def_name") == "PassiveCooler" for row in projects):
            patient = heat["patients"][0]
            return (f"Finish a passive cooler before {patient.get('name')}'s "
                    f"{int(float(patient.get('severity') or 0) * 100)}% heatstroke worsens. "
                    "Choose that exact cooler blueprint and a mobile builder; other rooms can wait.")
        home = model_decision_context(snapshot).get("home") or {}
        if home.get("roofed_sleepers", 0) < home.get("target", 0) and any(
            row.get("def_name") in {"Wall", "Door", "Bed"} for row in projects
        ):
            return ("Choose an exact unfinished shelter wall, door or bed and a capable builder. "
                    f"Only {home.get('roofed_sleepers', 0)}/{home.get('target', 0)} colonists sleep under a roof "
                    f"after {home.get('exposed_days', 0)} exposed days; finish the house before expanding.")
        if any(row.get("def_name") == "Bed" for row in projects):
            return "Choose an exact unfinished project and builder. A real bed is waiting while colonists still sleep on the ground; weigh this against other urgent projects."
        if any(row.get("def_name") == "HorseshoesPin" for row in projects):
            return "Choose an exact unfinished project and builder. Recreation equipment is waiting while low joy threatens mood; compare it with other work."
    if name == "unforbid_supplies":
        count = len(relevant_forbidden(snapshot))
        locked = forbidden_supply_counts(snapshot)
        parts = [f"{locked['meals']} packed meals" if locked["meals"] else "",
                 f"{locked['guns']} guns" if locked["guns"] else "",
                 f"{locked['wood']} wood" if locked["wood"] else "",
                 f"{locked['steel']} steel" if locked["steel"] else "",
                 f"{locked['medicine']} medicine" if locked["medicine"] else ""]
        summary = ", ".join(part for part in parts if part) or f"{count} supply stacks"
        return (f"Free instant unlock: {summary} are forbidden now. "
                "Colonists cannot use these existing supplies before this order.")
    if name == "leave_wildlife_alone":
        locked = forbidden_supply_counts(snapshot)
        if locked["meals"]:
            return (f"Skip hunting and taming now; does not unlock {locked['meals']} already owned "
                    "packed meals or help finish shelter.")
    if name == "prioritize_cooking":
        resources = (snapshot.get("map") or {}).get("resources") or {}
        cooks = [pawn for pawn in snapshot.get("colonists") or []
                 if isinstance((pawn.get("work_priorities") or {}).get("Cooking"), dict)
                 and not pawn["work_priorities"]["Cooking"].get("disabled")]
        fuel_note = (" No spare wood remains for the campfire/fueled stove; a cook alone cannot refuel it."
                     if needs_cooking_fuel_reserve(snapshot) else "")
        return (f"Give Cooking priority 1: {int(resources.get('meals') or 0)} prepared meals versus "
                f"{int(resources.get('raw_food') or 0)} raw food for {len(snapshot.get('colonists') or [])} people; "
                f"{len(cooks)} capable cook(s). Cooking takes time from their other work, "
                "but raw food may spoil and hungry colonists need meals." + fuel_note)
    if name == "rebalance_cooking":
        resources = (snapshot.get("map") or {}).get("resources") or {}
        options = cooking_rebalance_options(snapshot)
        return (f"{int(resources.get('meals') or 0)} meals, {int(resources.get('raw_food') or 0)} raw: "
                f"choose among {len(options)} real cook staffing changes. "
                "Cooking 1 tied with Handling 1 can leave the stove idle; deferring handling delays taming, "
                "while another cook may be less skilled.")
    if name.startswith("prisoner_policy:"):
        _, pawn_id, policy = name.split(":", 2)
        pawn = next((p for p in snapshot.get("combat", {}).get("prisoners", []) if str(p.get("id")) == pawn_id), {})
        skills = ", ".join(map(str, pawn.get("top_skills") or [])) or "skills unknown"
        if policy == "recruit":
            return f"Recruit prisoner {pawn.get('name', pawn_id)}: {skills}; traits {pawn.get('traits') or []}; requires warden time and food."
        if policy == "release":
            return f"Release healed prisoner {pawn.get('name', pawn_id)} for goodwill when their faction permits it; current goodwill {pawn.get('faction_goodwill', 0)}."
        if policy == "organs_nonlethal":
            return (f"Schedule removal of one kidney and one lung from prisoner {pawn.get('name', pawn_id)} without intentionally killing them. "
                    f"Value {pawn.get('market_value', 0):.0f}; account for surgery failure, medicine, doctor skill, mood and ideology.")
        if policy == "organs_lethal":
            return (f"Schedule lethal heart removal from prisoner {pawn.get('name', pawn_id)}. This is irreversible and may cause severe mood, ideology and diplomatic costs; "
                    f"use only if the medical and social context clearly justifies it.")
        return f"Hold prisoner {pawn.get('name', pawn_id)} for sale; value {pawn.get('market_value', 0):.0f}, requiring food, guarding and a suitable trader."
    if name.startswith("human_reproduction:"):
        _, first_id, second_id, approach = name.split(":", 3)
        by_id = {str(c.get("id")): c.get("name") for c in snapshot.get("colonists", [])}
        return f"Set {by_id.get(first_id, first_id)} and {by_id.get(second_id, second_id)} to {approach}; TryForBaby also requires a shared double bed and strong reserves."
    if name.startswith("breed_animals:"):
        species = name.split(":", 1)[1]
        return f"Encourage natural breeding of the available healthy adult male/female {species} pair while preserving feed reserves."
    if name.startswith("trade_to:"):
        _, destination_id, sale = name.split(":", 2)
        row = next((d for d in snapshot["development"].get("trade_destinations", []) if str(d.get("settlement_id")) == destination_id), {})
        stock = row.get("known_stock") or []
        knowledge = f" known stock: {', '.join(str(x.get('label')) for x in stock[:8])}" if stock else " stock unknown until visited"
        prisoner_note = " buys prisoners" if row.get("will_buy_humanlike_prisoners") else " does not buy prisoners"
        return (f"Send a normal guarded caravan to {row.get('name', destination_id)} ({row.get('faction_name', '?')}, "
                f"{row.get('relation', '?')} goodwill {row.get('goodwill', 0)}, distance {row.get('approximate_distance_tiles', '?')} tiles) "
                f"selling {sale};{prisoner_note}.{knowledge}")
    if name.startswith("raid_to:"):
        destination_id = name.split(":", 1)[1]
        row = next((d for d in snapshot["development"].get("raid_destinations", []) if str(d.get("settlement_id")) == destination_id), {})
        return (f"Raid {row.get('name', destination_id)} of {row.get('faction_name', '?')}: estimated defenders "
                f"{row.get('estimated_defenders_min', '?')}-{row.get('estimated_defenders_max', '?')}, tech {row.get('tech_level', '?')}, "
                f"weapons {row.get('likely_weapon_tags', [])}, armor {row.get('likely_apparel_tags', [])}, "
                f"possible loot {row.get('possible_loot', [])}, starts war={row.get('would_start_war', False)}.")
    return ACTION_DESCRIPTIONS[name]


def action_label(name: str, snapshot: dict[str, Any], language: str = "ru") -> str:
    if language == "en":
        if name.startswith("prisoner_policy:"):
            _, pawn_id, policy = name.split(":", 2)
            pawn = next((p for p in snapshot.get("combat", {}).get("prisoners", []) if str(p.get("id")) == pawn_id), {})
            return f"Prisoner {pawn.get('name', pawn_id)}: {policy.replace('_', ' ')}"
        if name.startswith("human_reproduction:"):
            return f"Family planning: {name.rsplit(':', 1)[1]}"
        if name.startswith("breed_animals:"):
            return f"Breed animals: {name.split(':', 1)[1]}"
        if name.startswith("trade_to:") or name.startswith("raid_to:"):
            return name.replace(":", " ").replace("_", " ").capitalize()
        return ACTION_LABELS_EN.get(name, name.replace("_", " ").capitalize())
    if name.startswith("prisoner_policy:"):
        _, pawn_id, policy = name.split(":", 2)
        pawn = next((p for p in snapshot.get("combat", {}).get("prisoners", []) if str(p.get("id")) == pawn_id), {})
        labels = {
            "recruit": "вербовать", "release": "освободить", "sell": "продать",
            "organs_nonlethal": "почка и лёгкое", "organs_lethal": "летальное изъятие органа",
        }
        return f"пленный {pawn.get('name', pawn_id)}: {labels.get(policy, policy)}"
    if name.startswith("human_reproduction:"):
        return f"размножение колонистов: {name.rsplit(':', 1)[1]}"
    if name.startswith("breed_animals:"):
        return f"разведение: {name.split(':', 1)[1]}"
    if name.startswith("trade_to:"):
        _, destination_id, sale = name.split(":", 2)
        row = next((d for d in snapshot["development"].get("trade_destinations", []) if str(d.get("settlement_id")) == destination_id), {})
        return f"торговля: {row.get('name', destination_id)} / {sale}"
    if name.startswith("raid_to:"):
        destination_id = name.split(":", 1)[1]
        row = next((d for d in snapshot["development"].get("raid_destinations", []) if str(d.get("settlement_id")) == destination_id), {})
        return f"набег: {row.get('name', destination_id)}"
    return ACTION_LABELS.get(name, name)


def next_research(client: bridge.RimApiClient, finished: set[str], map_state: dict[str, Any] | None = None) -> str | None:
    income_strategy = str((map_state or {}).get("income_strategy") or "")
    doctrine = (map_state or {}).get("doctrine") or {}
    strategy_route = {
        "drugs": ["DrugProduction"],
        "tailoring": ["ComplexClothing", "Devilstrand"],
        "art": ["Stonecutting"],
        "livestock": ["ComplexFurniture"],
        "biofuel": ["BiofuelRefining"],
        "mining": ["Machining", "MicroelectronicsBasics", "LongRangeMineralScanner"],
        "crops": [],
        "brewing": ["Brewing"],
        "travel_food": ["Pemmican", "PackagedSurvivalMeal"],
        "orbital": ["MicroelectronicsBasics"],
    }.get(income_strategy, [])
    military_route = {
        "weapons": ["Smithing", "Machining", "Gunsmithing", "BlowbackOperation", "GasOperation"],
        "armor": ["Smithing", "PlateArmor", "Machining", "FlakArmor"],
        "fortifications": ["Machining", "GunTurrets", "Mortars", "Firefoam"],
        "balanced": ["Smithing", "Machining", "FlakArmor", "Gunsmithing", "GunTurrets"],
    }.get(str(doctrine.get("military") or "balanced"), [])
    route = ["Electricity", "Batteries", *military_route, *strategy_route, *RESEARCH_ROUTE[2:]]
    for name in dict.fromkeys(route):
        if name in finished:
            continue
        try:
            project = client.get("/api/v1/research/project", name=name)
        except bridge.RimApiError:
            continue
        if project.get("can_start_now"):
            return name
    return None


def live_research_options(snapshot: dict[str, Any]) -> dict[str, str]:
    """Expose every startable project, rather than a prewritten victory route."""
    current = str(((snapshot.get("development") or {}).get("current_research") or {}).get("name") or "")
    if current.lower() not in {"", "none"}:
        return {}  # Keep the chosen project until completion; repeated switches waste research work.
    options = {}
    for row in (snapshot.get("development") or {}).get("research_tree") or []:
        name = str(row.get("name") or "")
        if (not name or row.get("is_finished") or not row.get("can_start_now")
                or row.get("player_has_any_appropriate_research_bench") is False or name == current):
            continue
        options[name] = (
            f"{row.get('label') or name}; {row.get('tech_level') or 'technology'}; "
            f"cost {row.get('research_points') or '?'}; {str(row.get('description') or '')[:90]}"
        )
    return options


def live_work_options(snapshot: dict[str, Any]) -> dict[str, str]:
    """Read actual Core/DLC/mod work types and pawn eligibility from the map."""
    colonists = snapshot.get("colonists") or []
    development = snapshot.get("development") or {}
    counts = development.get("building_counts") or {}
    resources = (snapshot.get("map") or {}).get("resources") or {}
    result = {}
    for row in (snapshot.get("development") or {}).get("work_types") or []:
        work = str((row.get("def_name") or row.get("name")) if isinstance(row, dict) else row or "")
        if not work:
            continue
        if work == "Research" and not any("ResearchBench" in str(name) and int(amount or 0) > 0
                                            for name, amount in counts.items()):
            continue
        if work == "Cooking" and not any(int(counts.get(name) or 0) > 0
                                           for name in ("Campfire", "FueledStove", "ElectricStove")):
            continue
        eligible = [c for c in colonists if not c.get("downed") and not (c.get("work_priorities") or {}).get(work, {}).get("disabled")
                    and work in (c.get("work_priorities") or {})]
        if not eligible:
            continue
        label = str(row.get("label") or work) if isinstance(row, dict) else work
        skills = ", ".join(map(str, row.get("relevant_skills") or [])) if isinstance(row, dict) else ""
        assigned = sum(int((pawn.get("work_priorities") or {}).get(work, {}).get("priority") or 0) > 0
                       for pawn in eligible)
        note = ""
        if work == "Construction":
            note = f"; {len(development.get('construction_projects') or [])} unfinished projects, {assigned} assigned"
        elif work in {"Hunting", "PlantCutting", "Growing", "Cooking"}:
            note = (f"; {int(resources.get('meals') or 0)} meals, "
                    f"{int(resources.get('raw_food') or 0)} raw food for {len(colonists)} people")
        result[work] = (f"{label}; {len(eligible)} eligible workers; {assigned} assigned"
                        + (f"; skills {skills}" if skills else "") + note)
    return result


def cooking_rebalance_options(snapshot: dict[str, Any], reserved_researcher_id: int = 0) -> dict[str, dict[str, Any]]:
    """Offer actual staffing tradeoffs when ingredients are not becoming meals.

    Priority 1 alone is not enough when an endless, naturally higher-priority
    Handling job also has priority 1. Laya chooses whether to defer that work
    or enlist a different cook; no worker assignment is made automatically.
    """
    resources = (snapshot.get("map") or {}).get("resources") or {}
    meals = int(resources.get("meals") or 0)
    raw = int(resources.get("raw_food") or 0)
    tables = (snapshot.get("development") or {}).get("work_tables") or []
    if meals > 4 or raw < 80 or not any(
        str(table.get("thing_def") or "") in {"Campfire", "FueledStove", "ElectricStove"}
        for table in tables if isinstance(table, dict)
    ):
        return {}
    options: dict[str, dict[str, Any]] = {}
    alternative_cooks = [pawn for pawn in snapshot.get("colonists") or []
                         if int(pawn.get("id") or 0) != reserved_researcher_id
                         and not pawn.get("downed") and not pawn.get("in_mental_state")
                         and isinstance((pawn.get("work_priorities") or {}).get("Cooking"), dict)
                         and not pawn["work_priorities"]["Cooking"].get("disabled")]
    for pawn in snapshot.get("colonists") or []:
        if pawn.get("downed") or pawn.get("in_mental_state"):
            continue
        priorities = pawn.get("work_priorities") or {}
        cooking = priorities.get("Cooking")
        if not isinstance(cooking, dict) or cooking.get("disabled"):
            continue
        pawn_id = int(pawn.get("id") or 0)
        if pawn_id <= 0:
            continue
        if pawn_id == reserved_researcher_id and alternative_cooks:
            continue
        cooking_level = int(cooking.get("priority") or 0)
        skill = int((((pawn.get("skills") or {}).get("Cooking") or {}).get("level")) or 0)
        name = str(pawn.get("name") or pawn_id)
        handling = priorities.get("Handling") or {}
        handling_level = int(handling.get("priority") or 0)
        if cooking_level != 1:
            options[f"assign:{pawn_id}"] = {
                "pawn_id": pawn_id, "work": "Cooking", "priority": 1,
                "summary": (f"Assign {name} Cooking 1 (now {cooking_level}, skill {skill}); "
                            "adds a meal cook but takes time from current duties; low skill risks food poisoning."),
            }
        elif handling_level == 1 and not handling.get("disabled"):
            options[f"defer_handling:{pawn_id}"] = {
                "pawn_id": pawn_id, "work": "Handling", "priority": 2,
                "summary": (f"Free {name} (Cooking 1, skill {skill}): Handling 1 -> 2. "
                            "Cooking can beat taming; animal care and training may wait."),
            }
    return options


def sleeping_place_counts(dev: dict[str, Any]) -> tuple[int, int | None]:
    """Count colonist-usable beds separately from beds in enclosed rooms."""
    buildings = dev.get("buildings")
    if buildings is None:
        counts = dev.get("building_counts") or {}
        return int(counts.get("Bed", 0)) + int(counts.get("SleepingSpot", 0)), None
    beds = [row for row in buildings if row.get("def") in {"Bed", "SleepingSpot"}
            and not row.get("medical") and not row.get("for_prisoners")]
    rooms = dev.get("rooms")
    if rooms is None:
        return len(beds), None
    sheltered_ids = {
        int(bed_id) for room in rooms
        if not room.get("touches_map_edge") and not room.get("is_prison_cell")
        and not room.get("is_doorway") and not room_is_ancient_danger(room)
        and int(room.get("open_roof_count") or 0) == 0
        for bed_id in room.get("contained_beds_ids") or []
    }
    return len(beds), sum(int(row.get("id") or 0) in sheltered_ids for row in beds)


def patient_in_completed_bed(pawn: dict[str, Any], snapshot: dict[str, Any],
                             beds: list[dict[str, Any]]) -> bool:
    """A paralyzed recruit already lying in a bed does not need repeated rescue."""
    combat_pawn = next((row for row in (snapshot.get("combat") or {}).get("colonists") or []
                        if str(row.get("id")) == str(pawn.get("id"))), {})
    bed_ids = {str(row.get("id")) for row in beds if row.get("id") is not None}
    if (str(combat_pawn.get("current_job") or "").casefold() == "laydown"
            and str(combat_pawn.get("current_job_target_id")) in bed_ids):
        return True
    position = pawn.get("position") or {}
    return bool(position) and any(
        (row.get("position") or {}).get("x") == position.get("x")
        and (row.get("position") or {}).get("z") == position.get("z")
        for row in beds
    )


def room_is_ancient_danger(room: dict[str, Any]) -> bool:
    """An enclosed ruin is not a safe bedroom just because it has a roof."""
    defs = {str(name) for name in room.get("contained_thing_defs") or []}
    return bool(defs & {"AncientCryptosleepCasket", "RectTrigger", "SignalAction_Letter"}) \
        or any(name.startswith("Mech_") for name in defs)


def sheltered_real_bed_count(dev: dict[str, Any],
                             anchor: dict[str, int] | None = None) -> int | None:
    """Count finished, roofed beds rather than outdoor beds or sleeping spots."""
    buildings, rooms = dev.get("buildings"), dev.get("rooms")
    if buildings is None or rooms is None:
        return None
    real_ids = {int(row["id"]) for row in buildings
                if row.get("def") in {"Bed", "HospitalBed"}
                and row.get("id") is not None
                and not row.get("medical") and not row.get("for_prisoners")
                and (anchor is None or (
                    # The first dry house can be well away from the landing
                    # anchor; twelve cells excluded its three actual beds and
                    # made Laya repeatedly plan more. Keep distant ruins out.
                    abs(int((row.get("position") or {}).get("x") or -999) - int(anchor["x"])) <= 48
                    and abs(int((row.get("position") or {}).get("z") or -999) - int(anchor["z"])) <= 48))}
    return sum(len(real_ids.intersection(int(bed_id) for bed_id in room.get("contained_beds_ids") or []))
               for room in rooms
               if not room.get("touches_map_edge") and not room.get("is_prison_cell")
               and not room_is_ancient_danger(room)
               and not room.get("is_doorway") and int(room.get("open_roof_count") or 0) == 0)


def exposed_batteries(dev: dict[str, Any]) -> list[dict[str, Any]]:
    """Identify batteries outside completely roofed enclosed rooms."""
    roofed_rooms = [room for room in dev.get("rooms") or []
                    if not room.get("touches_map_edge") and not room.get("is_doorway")
                    and int(room.get("cells_count") or 0) > 0
                    and int(room.get("open_roof_count") or 0) == 0]
    batteries = []
    for building_row in dev.get("buildings") or []:
        if building_row.get("def") != "Battery":
            continue
        point = building_row.get("position") or {}
        x, z = int(point.get("x") or -1), int(point.get("z") or -1)
        if any(int((room.get("min") or {}).get("x") or -1) <= x <= int((room.get("max") or {}).get("x") or -1)
               and int((room.get("min") or {}).get("z") or -1) <= z <= int((room.get("max") or {}).get("z") or -1)
               for room in roofed_rooms):
            continue
        batteries.append(building_row)
    return batteries


def retire_starter_sleeping_spots(client: bridge.RimApiClient, snapshot: dict[str, Any],
                                  map_state: dict[str, Any], log_path: Path) -> None:
    """Retire free outdoor spots after everyone has a completed roofed bed."""
    population = len(snapshot.get("colonists") or [])
    if not population or (sheltered_real_bed_count(snapshot.get("development") or {}) or 0) < population:
        return
    anchor = map_state.get("anchor") or {}
    if not anchor:
        return
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    attempts = map_state.setdefault("retired_starter_spots", {})
    for spot in snapshot.get("development", {}).get("buildings") or []:
        if spot.get("def") != "SleepingSpot" or spot.get("id") is None:
            continue
        point = spot.get("position") or {}
        if not point or squared_distance(point, anchor) > 18 ** 2:
            continue
        spot_id = str(spot["id"])
        if spot_id in attempts and tick - int(attempts[spot_id]) < 30000:
            continue
        attempts[spot_id] = tick
        try:
            result = client.post("/api/v1/order/designate/area", body={
                "map_id": snapshot["map"]["id"], "point_a": point,
                "point_b": point, "type": "remove-sleeping-spot",
            })
            bridge.append_log(log_path, {"timestamp": bridge.utc_now(),
                "mode": "housekeeping", "event": "retire_starter_sleeping_spot",
                "bed_id": spot_id, "result": result})
        except bridge.RimApiError as exc:
            bridge.append_log(log_path, {"timestamp": bridge.utc_now(),
                "mode": "housekeeping", "event": "retire_starter_sleeping_spot",
                "bed_id": spot_id, "error": str(exc)})


def prison_site_for_state(map_state: dict[str, Any], anchor: dict[str, int]) -> dict[str, int]:
    site = map_state.get("prison_site") or {}
    return {"x": int(site.get("x", int(anchor["x"]) - 12)),
            "z": int(site.get("z", int(anchor["z"]) - 8))}


def ready_prison_beds(dev: dict[str, Any], site: dict[str, int]) -> list[dict[str, Any]]:
    """Capture can designate an enclosed ordinary bed as a prisoner bed on demand."""
    sheltered_ids = {
        int(bed_id) for room in dev.get("rooms") or []
        if not room.get("touches_map_edge") and not room.get("is_doorway")
        and int(room.get("open_roof_count") or 0) == 0
        for bed_id in room.get("contained_beds_ids") or []
    }
    return [bed for bed in dev.get("buildings") or []
            if bed.get("id") is not None and int(bed["id"]) in sheltered_ids
            and bed.get("def") in {"Bed", "SleepingSpot"} and not bed.get("medical")
            and site["x"] <= int((bed.get("position") or {}).get("x") or -999) <= site["x"] + 6
            and site["z"] <= int((bed.get("position") or {}).get("z") or -999) <= site["z"] + 6]


def choose_prison_site(terrain: dict[str, Any], anchor: dict[str, int],
                       dev: dict[str, Any], map_state: dict[str, Any]) -> dict[str, int] | None:
    if map_state.get("prison_site"):
        return prison_site_for_state(map_state, anchor)
    stable = {str(name) for name in terrain.get("palette") or [] if (
        str(name) in {"Soil", "SoilRich", "Gravel", "Sand"}
        or str(name).startswith(("Rough", "Smooth", "Flagstone", "Paved", "Concrete"))
    )}
    preferred = {"x": int(anchor["x"]) - 12, "z": int(anchor["z"]) - 8}
    return find_terrain_rect(terrain, preferred, 7, 7, stable, radius=25,
                             blocked=architecture_occupied_cells(dev, map_state), clearance=1)


def empty_indoor_sleeping_spot(dev: dict[str, Any],
                               anchor: dict[str, int] | None = None,
                               excluded: set[tuple[int, int]] | None = None) -> dict[str, int] | None:
    """Find a free roofed sleeping place near the colony, not in distant ruins."""
    buildings = dev.get("buildings") or []
    excluded = excluded or set()
    occupied: set[tuple[int, int]] = set()
    for row in buildings:
        pos, size = row.get("position") or {}, row.get("size") or {}
        if pos.get("x") is None or pos.get("z") is None:
            continue
        for dx in range(max(1, int(size.get("x") or 1))):
            for dz in range(max(1, int(size.get("z") or 1))):
                occupied.add((int(pos["x"]) + dx, int(pos["z"]) + dz))
    for project in dev.get("construction_projects") or []:
        pos = project.get("position") or {}
        if pos.get("x") is not None and pos.get("z") is not None:
            occupied.add((int(pos["x"]), int(pos["z"])))
    rooms = sorted(dev.get("rooms") or [], key=lambda room: (
        not bool(room.get("contained_beds_ids")), int(room.get("cells_count") or 0)))
    for room in rooms:
        if (room.get("touches_map_edge") or room.get("is_prison_cell") or room.get("is_doorway")
                or room_is_ancient_danger(room)
                or int(room.get("open_roof_count") or 0) != 0):
            continue
        cells = {(int(cell["x"]), int(cell["z"])) for cell in room.get("cells") or []
                 if cell.get("x") is not None and cell.get("z") is not None}
        if not cells or len(cells) > 300:
            continue
        center_x = sum(x for x, _ in cells) / len(cells)
        center_z = sum(z for _, z in cells) / len(cells)
        for x, z in sorted(cells, key=lambda cell: (abs(cell[0] - center_x) + abs(cell[1] - center_z), cell)):
            footprint = {(x, z), (x, z + 1)}
            if anchor is not None and (
                abs(x - int(anchor["x"])) > 12 or abs(z - int(anchor["z"])) > 12
            ):
                continue
            if (x, z) not in excluded and footprint <= cells and not footprint & occupied:
                return {"x": x, "z": z}
    return None


def replaceable_indoor_sleeping_spot(dev: dict[str, Any], anchor: dict[str, int],
                                    colonists: list[dict[str, Any]],
                                    excluded: set[tuple[int, int]] | None = None) -> dict[str, Any] | None:
    """Find a roofed temporary spot that a real bed can replace in place."""
    sheltered_ids = {
        int(bed_id)
        for room in dev.get("rooms") or []
        if not room.get("touches_map_edge") and not room.get("is_prison_cell")
        and not room.get("is_doorway") and not room_is_ancient_danger(room)
        and int(room.get("open_roof_count") or 0) == 0
        for bed_id in room.get("contained_beds_ids") or []
    }
    occupied_ids = {
        int(pawn.get("current_job_target_id") or 0)
        for pawn in colonists
        if str(pawn.get("current_job") or "").lower() == "laydown"
    }
    for spot in dev.get("buildings") or []:
        if spot.get("def") != "SleepingSpot" or spot.get("id") is None:
            continue
        spot_id = int(spot["id"])
        point = spot.get("position") or {}
        if (spot_id not in sheltered_ids or spot_id in occupied_ids
                or point.get("x") is None or point.get("z") is None):
            continue
        x, z = int(point["x"]), int(point["z"])
        if (abs(x - int(anchor["x"])) > 12 or abs(z - int(anchor["z"])) > 12
                or (x, z) in (excluded or set())):
            continue
        return {"id": spot_id, "position": {"x": x, "z": z}}
    return None


def colonist_is_idle(colonist: dict[str, Any]) -> bool:
    """RimWorld reports ordinary idle wandering as an actual job name."""
    if colonist.get("downed") or colonist.get("in_mental_state"):
        return False
    return str(colonist.get("current_job") or "").lower() in {
        "", "unknown", "wait", "wait_maintainposture", "wait_wander",
        "gotowander", "idle", "none",
    }


def requires_builder_now(action: str) -> bool:
    """Hide orders that can only add unbuildable blueprints without a builder."""
    if action in {"build_sleeping_spots", "build_animal_spots", "build_butcher_spot"}:
        return False  # Free spots are placed immediately without a builder.
    if action.startswith(("build_", "finish_", "floor_", "install_")):
        return True
    return action in {
        "plan_architecture", "improve_room_lighting", "upgrade_workbench",
        "commission_sculptures", "process_mechanoids", "start_stonecutting",
    }


def estimated_food_runway_days(resources: dict[str, Any], people_count: int) -> float | None:
    """Rough planning horizon, not a rule that decides the colony's next action.

    RimWorld reports total stored nutrition. A humanlike's typical 1.6/day
    demand is only an estimate; work, traits and food access can change it.
    """
    if people_count <= 0:
        return None
    nutrition = bridge.first_number(resources.get("nutrition"))
    if resources.get("nutrition") is None:
        nutrition = 0.9 * int(resources.get("food") or resources.get("meals") or 0)
    return round(max(0.0, nutrition) / (1.6 * people_count), 1)


def firefighter_priority_options(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Living colonists whose Firefighter work is allowed but not priority 1."""
    return [pawn for pawn in snapshot.get("colonists") or []
            if not pawn.get("downed") and not pawn.get("in_mental_state")
            and bridge.first_number(pawn.get("health"), 1) >= 0.75
            and isinstance((pawn.get("work_priorities") or {}).get("Firefighter"), dict)
            and not pawn["work_priorities"]["Firefighter"].get("disabled")
            and int(pawn["work_priorities"]["Firefighter"].get("priority") or 0) != 1]


def focus_active_fire_choices(actions: list[str], home_fire: bool = False) -> list[str]:
    """Respond to a verified nearby fire before routine colony work."""
    if "prioritize_firefighting" in actions:
        return ["prioritize_firefighting"]
    if "expand_home_area" in actions:
        return ["expand_home_area"]
    if home_fire:
        # With firefighters already assigned, let them work. A research switch
        # or new construction order spends the scarce decision window while
        # wooden rooms burn. Rescue and treatment remain available.
        emergency = {"rescue_downed_colonist", "tend_colonist", "prioritize_rescue",
                     "prioritize_doctor", "prepare_emergency_medical_bed",
                     "open_blocked_food_path", "feed_hungry_colonist", "hold_survival"}
        focused = [action for action in actions if action in emergency]
        return focused if focused else ["hold_survival"]
    return actions


def focus_cold_start_choices(snapshot: dict[str, Any], actions: list[str],
                             details: dict[str, Any]) -> list[str]:
    """Finish a heated first room before exposure makes every builder collapse."""
    dev = snapshot.get("development") or {}
    cold = dev.get("cold_threat") or {}
    outside_c = float(cold.get("outside_c") if cold.get("outside_c") is not None else 20)
    if (not cold or (not cold.get("patients") and outside_c > -5)
            or (snapshot.get("map") or {}).get("enemies")
            or (dev.get("fire_situation") or {}).get("fires")):
        return actions
    resources = (snapshot.get("map") or {}).get("resources") or {}
    runway = estimated_food_runway_days(resources, len(snapshot.get("colonists") or []))
    if runway is not None and runway < 1 and outside_c > -10 and not cold.get("patients"):
        return actions
    occupied_rooms = [room for room in dev.get("rooms") or [] if (
        not room.get("touches_map_edge") and not room.get("is_prison_cell")
        and int(room.get("open_roof_count") or 0) == 0
        and bool(room.get("contained_beds_ids"))
    )]
    if occupied_rooms and any(float(room.get("temperature") if room.get("temperature") is not None else outside_c) >= 12
                              for room in occupied_rooms):
        return actions
    if occupied_rooms:
        heat = {"prioritize_thermal_project", "build_room_campfire",
                "connect_room_heater_power", "build_room_heater"}
        focused = [action for action in actions if action in heat]
        if focused:
            dev["cold_start_focus"] = "heat_occupied_room"
            return focused
    if "unforbid_supplies" in actions:
        dev["cold_start_focus"] = "unlock_shelter_materials"
        return ["unforbid_supplies"]
    if "build_starter_base" in actions:
        dev["cold_start_focus"] = "place_heated_shelter"
        return ["build_starter_base"]
    projects = details.get("construction_project_options") or []
    shell = [row for row in projects if str(row.get("def_name") or "") in {"Wall", "Door"}]
    urgent_projects = shell or [row for row in projects
                                if str(row.get("def_name") or "") in {"Campfire", "Heater"}]
    if urgent_projects:
        details["construction_project_options"] = urgent_projects
        dev["construction_project_options"] = urgent_projects
    if "prioritize_construction" in actions and urgent_projects:
        dev["cold_start_focus"] = "assign_builder"
        return ["prioritize_construction"]
    if urgent_projects and any(
        str(pawn.get("current_job") or "").lower() in {
            "finishframe", "haultocontainer", "constructdeliverresourcestoframes",
            "constructdeliverresourcestoblueprints", "constructfinishframes",
        }
        for pawn in snapshot.get("colonists") or [] if not pawn.get("downed")
    ):
        dev["cold_start_focus"] = "builders_working"
        return ["hold_survival"]
    if "prioritize_construction_project" in actions and urgent_projects:
        dev["cold_start_focus"] = "finish_shell" if shell else "finish_heat"
        return ["prioritize_construction_project"]
    for name in ("prioritize_thermal_project", "build_room_campfire",
                 "connect_room_heater_power", "build_room_heater",
                 "harvest_nearby_trees"):
        if name in actions:
            dev["cold_start_focus"] = name
            return [name]
    if any(str(row.get("def_name") or "") in {"Wall", "Door", "Campfire", "Heater"}
           for row in dev.get("construction_projects") or []):
        dev["cold_start_focus"] = "wait_for_shell"
        return ["hold_survival"]
    # When nobody can construct, rescue and medical care remain available.
    return actions


def focus_cooking_gap_choices(snapshot: dict[str, Any], actions: list[str]) -> list[str]:
    """Complete a meal source before scarce ready meals become starvation."""
    resources = (snapshot.get("map") or {}).get("resources") or {}
    development = snapshot.get("development") or {}
    counts = development.get("building_counts") or {}
    if (not development.get("cooking_gap_urgent")
            or int(resources.get("raw_food") or 0) < 40
            or any(int(counts.get(name) or 0) > 0 for name in
                   ("Campfire", "FueledStove", "ElectricStove"))):
        return actions
    if development.get("urgent_cooking_projects") and "prioritize_construction_project" in actions:
        selected = "prioritize_construction_project"
    elif "build_campfire" in actions:
        selected = "build_campfire"
    else:
        return actions
    # Direct care and access to existing meals still outrank a new kitchen.
    concurrent = {"rescue_downed_colonist", "tend_colonist", "feed_hungry_colonist",
                  "eat_available_meal", "open_blocked_food_path", "unforbid_supplies"}
    development["cooking_gap_focus"] = selected
    return [action for action in actions if action == selected or action in concurrent]


def focus_imminent_food_choices(snapshot: dict[str, Any], actions: list[str]) -> list[str]:
    """Offer only actionable survival work when stored food is nearly gone.

    Laya still chooses between foraging, hunting, unlocked supplies, cooking,
    treatment and temperature care. Stonecutting, art and generic work-priority
    edits cannot produce food before a starving pawn collapses, so they are not
    feasible *for this decision window*. They return when reserves recover.
    """
    if (int((snapshot.get("development") or {}).get("butchery_gap") or 0) > 0
            and "build_butcher_spot" in actions):
        actions = [action for action in actions
                   if action not in {"designate_safe_hunting", "prioritize_hunting"}]
    resources = (snapshot.get("map") or {}).get("resources") or {}
    people = snapshot.get("colonists") or []
    runway = estimated_food_runway_days(resources, len(people))
    crops = ((snapshot.get("development") or {}).get("farm") or {}).get("crop_types") or []
    near_ready_crop = any(
        int(crop.get("total_plants") or 0) > 0
        and (bridge.first_number(crop.get("growth_progress_average"), 0.0) >= 70.0
             or int(crop.get("harvestable_plants") or 0) > 0)
        for crop in crops if isinstance(crop, dict)
    )
    # Food choices and their runway stay visible several days in advance, but
    # hard-filtering all development at a four-day reserve traps the colony in
    # gathering work. Reserve that filter for a near-term shortage. A nearly
    # ripe field gives a little more time unless cooking fuel is missing.
    urgency_window = 1.5 if near_ready_crop else 2.5
    fuel_gap = needs_cooking_fuel_reserve(snapshot)
    # Nearly ripe crops do not solve an empty wood reserve for the campfire.
    # Preserve a wider, still model-chosen food/fuel window in that case.
    if runway is None or (runway > urgency_window and not (fuel_gap and runway <= 5.0)):
        return actions
    replenishment = {
        "harvest_local_plants", "harvest_food_crops_early",
        "designate_safe_hunting", "open_sealed_food_store", "open_blocked_food_path",
        "build_butcher_spot",
    }
    if fuel_gap:
        replenishment.add("harvest_nearby_trees")
    # Eating an existing meal does not replenish the pantry. Do not focus an
    # otherwise productive cycle around that action alone.
    if not replenishment.intersection(actions):
        return actions
    related = {
        *replenishment, "unforbid_supplies", "eat_available_meal",
        "feed_hungry_colonist", "prioritize_plant_cutting", "prioritize_hunting",
        "prioritize_cooking", "configure_food_bills", "rebalance_cooking", "build_campfire",
        "create_nearby_food_cache", "prioritize_hauling", "prioritize_growing",
        "rescue_downed_colonist", "tend_colonist", "prioritize_doctor",
        "prioritize_rescue", "equip_colonists", "build_room_campfire",
        "build_room_heater", "connect_room_heater_power",
        "prioritize_thermal_project", "build_passive_cooler",
        "expand_home_area", "hold_survival",
    }
    if (snapshot.get("development") or {}).get("urgent_cooking_projects"):
        related.add("prioritize_construction_project")
    # A newly arrived worker can add to food production only if they can rest
    # safely. One indoor bed is quick to finish while several days of food
    # remain; keep it visible beside gathering and cooking choices.
    if runway > 2.0 and not fuel_gap:
        related.update({"build_basic_beds", "build_sleeping_spots", "assign_real_bed"})
    if int((snapshot.get("development") or {}).get("butchery_gap") or 0) > 0 and "build_butcher_spot" in actions:
        # A new kill only enlarges the inaccessible carcass pile. Hunting is
        # still available outside this immediate food decision window.
        related.difference_update({"designate_safe_hunting", "prioritize_hunting"})
    food_present = int(resources.get("food") or 0) > 0
    raw_present = int(resources.get("raw_food") or 0) > 0
    wild_food = bool((snapshot.get("development") or {}).get("wild_plant_options"))
    crop_food = bool((snapshot.get("development") or {}).get("early_crop_options"))
    hunt_food = bool((snapshot.get("development") or {}).get("hunt_options"))
    if not wild_food and not crop_food:
        related.discard("prioritize_plant_cutting")
    if not hunt_food:
        related.discard("prioritize_hunting")
    if not raw_present:
        related.difference_update({"prioritize_cooking", "configure_food_bills", "build_campfire"})
        if any(row.get("thing_def") in {"TableButcher", "ButcherSpot"}
               for row in (snapshot.get("development") or {}).get("work_tables") or []) and any(
                   not row.get("is_forbidden") for row in corpse_rows(snapshot, "CorpsesAnimal")
               ):
            related.update({"prioritize_cooking", "configure_food_bills"})
    # Growing more plants will not feed anyone in this window. At under 1.5
    # days, even generic hauling is less direct than gathering or hunting.
    related.discard("prioritize_growing")
    if not food_present:
        related.difference_update({"prioritize_hauling", "create_nearby_food_cache"})
    if runway <= 1.5:
        related.discard("prioritize_hauling")
    if fuel_gap:
        # These are literal no-ops when the stove already has its bill and a
        # healthy cook/cutter is assigned; leave the concrete tree order visible.
        def assigned(work: str) -> bool:
            return any(not pawn.get("downed") and not pawn.get("in_mental_state")
                       and int(((pawn.get("work_priorities") or {}).get(work) or {}).get("priority") or 0) == 1
                       for pawn in people)

        if assigned("Cooking"):
            related.discard("prioritize_cooking")
        if assigned("PlantCutting"):
            related.discard("prioritize_plant_cutting")
        if assigned("Hauling"):
            related.discard("prioritize_hauling")
        if assigned("Hunting"):
            related.discard("prioritize_hunting")
        cooking_tables = [table for table in (snapshot.get("development") or {}).get("work_tables") or []
                          if str(table.get("thing_def") or "") in {"Campfire", "FueledStove", "ElectricStove"}]
        if cooking_tables and all(int(table.get("bills_count") or 0) > 0 for table in cooking_tables):
            related.discard("configure_food_bills")
    if (((snapshot.get("development") or {}).get("cold_threat") or {}).get("patients")
            or fuel_gap):
        related.add("harvest_nearby_trees")
    focused = [action for action in actions if action in related]
    if focused:
        snapshot.setdefault("development", {})["deferred_during_food_crisis"] = [
            action for action in actions if action not in related
        ]
    return focused or actions


def focus_misaligned_research_choice(snapshot: dict[str, Any], actions: list[str]) -> list[str]:
    """Spend one safe decision to repair a fresh detour from the saved course."""
    if ("advance_doctrine_research" not in actions
            or not (snapshot.get("development") or {}).get("research_misalignment")
            or (snapshot.get("map") or {}).get("enemies")
            or any(fire.get("in_home") for fire in
                   ((snapshot.get("development") or {}).get("fire_situation") or {}).get("fires") or [])):
        return actions
    people = snapshot.get("colonists") or []
    runway = estimated_food_runway_days((snapshot.get("map") or {}).get("resources") or {}, len(people))
    if (runway is not None and runway < 1.5) or any(
            pawn.get("downed") or bridge.first_number(pawn.get("bleeding_rate"), 0.0) > 0.05
            for pawn in people):
        return actions
    return ["advance_doctrine_research"]


def model_decision_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    """A decision-first summary sized for Laya's *token*, not character, budget.

    The previous 12,000-character snapshot could occupy thousands of tokens;
    the English checkpoint sees at most roughly 320 state tokens after its
    question head. Exact target/worker facts belong in the relevant option
    descriptions and are requested only after Laya chooses that operation.
    """
    dev = snapshot.get("development") or {}
    people = snapshot.get("colonists") or []
    animals = snapshot.get("animals") or []
    resources = (snapshot.get("map") or {}).get("resources") or {}
    food_runway = estimated_food_runway_days(resources, len(people))
    planted_crops = [crop for crop in (dev.get("farm") or {}).get("crop_types") or []
                     if int(crop.get("total_plants") or 0) > 0]
    harvestable_crops = sum(int(crop.get("harvestable_plants") or 0) for crop in planted_crops)
    crop_progress = round(max((float(crop.get("growth_progress_average") or 0)
                               for crop in planted_crops), default=0))
    counts = dev.get("building_counts") or {}
    sick = sorted(
        (c for c in people if c.get("downed") or bridge.first_number(c.get("health"), 1) < 0.8),
        key=lambda c: bridge.first_number(c.get("health"), 1),
    )[:2]
    doctrine = dev.get("doctrine") or {}
    weather = dev.get("weather") or {}
    least_hunger = min((bridge.first_number(c.get("hunger"), 1) for c in people), default=1)
    least_rest = min((bridge.first_number(c.get("rest"), 1) for c in people), default=1)
    pending_projects = len(dev.get("construction_projects") or [])
    active_builders = sum(
        str(c.get("current_job") or "").lower().startswith(
            ("construct", "build", "finishframe", "placeframe", "deconstruct")
        ) for c in people if not c.get("downed")
    )
    eligible_builders = sum(
        isinstance((c.get("work_priorities") or {}).get("Construction"), dict)
        and not c["work_priorities"]["Construction"].get("disabled")
        and not c.get("downed")
        for c in people
    )
    construction_workers = sum(
        isinstance((c.get("work_priorities") or {}).get("Construction"), dict)
        and not c["work_priorities"]["Construction"].get("disabled")
        and int(c["work_priorities"]["Construction"].get("priority") or 0) > 0
        and not c.get("downed")
        for c in people
    )
    bed_count, sheltered_beds = sleeping_place_counts(dev)
    sheltered_beds = sheltered_beds if sheltered_beds is not None else 0
    real_beds = int(counts.get("Bed") or 0) + int(counts.get("HospitalBed") or 0)
    sheltered_real_beds = sheltered_real_bed_count(dev, dev.get("base_anchor")) or 0
    exposed_days = round(float(dev.get("shelter_exposure_days") or 0), 1)
    forbidden = relevant_forbidden(snapshot)
    idle = [c for c in people if colonist_is_idle(c)]
    low_mood = sorted((c for c in people if bridge.first_number(c.get("mood"), 1) < 0.45),
                      key=lambda c: bridge.first_number(c.get("mood"), 1))[:2]
    mood_signals = []
    for colonist in low_mood:
        signals = [name for name, value, threshold in (
            ("hungry", colonist.get("hunger"), 0.35),
            ("exhausted", colonist.get("rest"), 0.25),
            ("bored", colonist.get("joy"), 0.3),
            ("pain", 1 - bridge.first_number(colonist.get("pain"), 0), 0.75),
            ("uncomfortable", colonist.get("comfort"), 0.25),
            ("ugly surroundings", colonist.get("beauty"), 0.4),
        ) if bridge.first_number(value, 1) < threshold]
        mood_signals.append({"name": str(colonist.get("name") or "")[:20],
                             "mood": colonist.get("mood"), "joy": colonist.get("joy"),
                             "pain": colonist.get("pain"), "beauty": colonist.get("beauty"),
                             "comfort": colonist.get("comfort"),
                             "mental_break": bool(colonist.get("in_mental_state")),
                             "signals": signals[:5]})
    risks = []
    if food_runway is not None and food_runway < 5:
        risks.append(
            f"Food runway is short: about {food_runway} days of stored nutrition for {len(people)} people; "
            f"{int(resources.get('raw_food') or 0)} raw food items, {harvestable_crops} ready crops, "
            f"planted crops about {crop_progress}% grown. "
            "Wild edible plants or safe game could replenish it; new rooms and crafts use labor before food arrives."
        )
    if dev.get("exposed_batteries"):
        risks.append(f"{len(dev['exposed_batteries'])} battery/batteries are exposed to rain; "
                     "short circuits can waste stored power and start fires. A roofed shed costs building labor and material.")
    heat = dev.get("heat_threat") or {}
    if heat:
        patients = heat.get("patients") or []
        risk = (f"Heat danger: outside {heat.get('outside_c')} C; coolest roofed room "
                f"{heat.get('coolest_roofed_c')} C. ")
        if patients:
            risk += ("Heatstroke " + ", ".join(
                f"{patient['name']} {int(float(patient['severity']) * 100)}%"
                for patient in patients[:3]
            ) + "; staying in a hot bed can kill even after feeding or wound treatment.")
        else:
            risk += "A heat wave can incapacitate workers; a cooled occupied room is safer than an uncooled bedroom."
        risks.append(risk)
    cold = dev.get("cold_threat") or {}
    if cold:
        patients = cold.get("patients") or []
        risk = (f"Cold danger: outside {cold.get('outside_c')} C; warmest roofed room "
                f"{cold.get('warmest_roofed_c')} C. ")
        if patients:
            risk += ("Hypothermia " + ", ".join(
                f"{patient['name']} {int(float(patient['severity']) * 100)}%"
                for patient in patients[:3]
            ) + "; an unheated bed can be fatal. A blueprint cannot rewarm anyone.")
        else:
            risk += "Indoor heating or warm clothing may be needed before a cold snap worsens."
        risks.append(risk)
        if (int((dev.get("building_counts") or {}).get("WoodFiredGenerator") or 0) > 0):
            wood = int((dev.get("item_counts") or {}).get("WoodLog") or 0)
            battery = int((dev.get("power_info") or {}).get("currently_stored_power") or 0)
            output = int((dev.get("power_info") or {}).get("current_power") or 0)
            if output == 0:
                risks.append(f"The wood-fired generator currently produces 0 W and only {wood} wood is stocked. "
                             f"Battery charge is {battery} Wd: a connected heater can warm temporarily, "
                             "but will stop when charge runs out. Mark mature trees for cutting if needed, "
                             "then Hauling/refueling must bring wood to the generator; Plant Cutting priority alone marks no trees.")
            elif wood == 0 and int((dev.get("building_counts") or {}).get("Heater") or 0) > 0:
                risks.append("The heater works now, but the wood-fired generator has no spare logs. "
                             "Its internal fuel is finite: mark trees to cut before an outage, then let Hauling refuel it.")
        wiring = dev.get("power_connection_options") or {}
        if wiring:
            fewest = min(int(row.get("conduit_cost") or 0) for row in wiring.values())
            risks.append(f"A bedroom heater is not connected to the live grid: it needs about {fewest} "
                         "steel conduits plus construction time. Completing the heater alone cannot cure hypothermia; "
                         "a fueled indoor campfire may be faster if wood is available.")
    if resources.get("food", 0) <= 0 and least_hunger < 0.2:
        risks.append("No food and a colonist is close to starvation; delay can kill.")
    early_crops = dev.get("early_crop_options") or {}
    wild_food_options = dev.get("wild_plant_options") or {}
    if early_crops and wild_food_options:
        wild_yield = sum(int(group.get("expected_yield") or 0) for group in wild_food_options.values())
        risks.append(
            f"Nearby mature wild plants may yield about {wild_yield} food without cutting the immature rice. "
            "Compare walking and harvesting time against the immediate need before sacrificing the field."
        )
    if early_crops:
        crop_count = sum(int(group.get("count") or 0) for group in early_crops.values())
        risks.append(
            f"Only {int(resources.get('food') or 0)} food left for {len(people)} people; "
            f"{crop_count} edible crops can be harvested now. Early harvest reduces yield, "
            "but waiting for full maturity risks hunger."
        )
    if resources.get("raw_food", 0) > resources.get("meals", 0) * 3 and resources.get("raw_food", 0) >= 40:
        risks.append("Most food is raw, not prepared meals; cooking and storage matter before it spoils, especially in heat.")
    if dev.get("butchery_gap"):
        risks.append(f"{int(dev['butchery_gap'])} accessible animal carcasses are stored but there is no butcher spot or table. "
                     "Hauling and hunting will not yield meat until a spot and forever butchering bill exist.")
    if needs_cooking_fuel_reserve(snapshot):
        wood = int(((snapshot.get("development") or {}).get("item_counts") or {}).get("WoodLog") or 0)
        risks.append(f"Only {wood} spare wood for a campfire or fueled stove, with raw ingredients but few meals. "
                     "Cooking priority and bills cannot replace missing fuel; consider marking mature trees to cut "
                     "and hauling logs, or another way to feed the colony.")
    if (resources.get("raw_food", 0) > 0 and not any(int(counts.get(name) or 0)
            for name in ("Campfire", "FueledStove", "ElectricStove"))):
        risks.append("Raw ingredients are present but no cooking station is finished; a 20-wood campfire can turn them into meals while a clean kitchen is planned.")
    if resources.get("nutrition_rotting_soon", 0) >= 2:
        risks.append(f"About {resources['nutrition_rotting_soon']:.1f} nutrition will rot soon unless cooked, eaten or cooled.")
    if dev.get("blocked_food_pawn"):
        risks.append(f"{dev['blocked_food_pawn']} cannot reach food despite nearby supplies. "
                     "An adjacent wall must be opened before another meal order can work.")
    if resources.get("meals", 0) > 0 and least_hunger < 0.35:
        risks.append("A colonist is hungry despite stocked meals: continuing other jobs can cause lethal malnutrition. "
                     + ("Unlocked meals are nearby, but distance alone does not prove a path." if reachable_meals(snapshot)
                        else "No unlocked meal stack is visible until storage is opened."))
    if pending_projects >= max(12, construction_workers * 8) and construction_workers:
        project_label = f"at least {pending_projects}" if pending_projects >= 100 else str(pending_projects)
        risks.append(
            f"{project_label} unfinished building jobs for {construction_workers} assigned builder(s); "
            f"{eligible_builders} could build. Finishing critical frames or enabling another builder may pay off "
            "before ordering more rooms."
        )
    if dev.get("deferred_for_construction_capacity"):
        risks.append("The construction queue exceeds current worker capacity. Optional new blueprints are "
                     "deferred until existing projects progress; Laya can prioritize an exact project, "
                     "assign builders, or choose other productive work now.")
    if (dev.get("sealed_food_store") or {}).get("status") == "sealed":
        risks.append("Food freezer sealed: meals are unreachable. Open one wall before starvation.")
    meal_distance = (dev.get("food_distance_context") or {}).get("nearest_meal_to_base")
    if meal_distance is not None and meal_distance > 50:
        risks.append(f"Closest meal stack is {meal_distance} tiles from the settlement; a local food cache and hauling can shorten future trips.")
    if any(bridge.first_number(c.get("bleeding_rate")) > 0.05 for c in people):
        risks.append("Untreated bleeding may kill; treatment also takes a worker away from other tasks.")
    if sum(bool(c.get("downed")) for c in people):
        risks.append("A downed colonist needs a direct rescue or tending job now; a work priority alone may not start one.")
    if forbidden:
        locked = forbidden_supply_counts(snapshot)
        if locked["meals"] or locked["guns"]:
            risks.append(
                f"Owned starting supplies are forbidden: {locked['meals']} packed meals and "
                f"{locked['guns']} guns are unusable. Unforbidding is instant and costs no worker time; "
                "foraged berries do not replace ready meals or weapons."
            )
    if people and bed_count < len(people):
        risks.append(f"Only {bed_count} sleeping places for {len(people)} colonists; sleeping on the ground worsens rest and mood. Free sleeping spots need no materials.")
    if people and sheltered_beds < len(people):
        risks.append(f"Only {sheltered_beds} of {len(people)} colonists have roofed sleeping places after {exposed_days} days; a compact completed house matters more than extra blueprints.")
    if people and sheltered_real_beds < len(people):
        risks.append(f"Only {sheltered_real_beds} of {len(people)} colonists have finished beds under a roof; sleeping spots and outdoor beds are temporary.")
    if people and len(people) <= 3:
        risks.append(
            f"A {len(people)}-person crew can collapse after one injury or kidnapping. "
            f"Ready meals per person: {int(resources.get('meals') or 0) // len(people)}; "
            "new people add labor and defense but also need food, indoor beds and care. "
            "A finished prison makes capture-and-recruit possible before raiders bleed out."
        )
    if any(bridge.first_number(c.get("joy"), 1) < 0.4 and bridge.first_number(c.get("mood"), 1) < 0.5
           for c in people):
        risks.append("Low recreation and mood can compound into an early mental break. Protected Joy hours cost work time; a horseshoes pin costs 10 wood but adds recreation variety.")
    if any(float(room.get("impressiveness") or 0) < -15
           and (room.get("contained_beds_ids") or str(room.get("role_label") or "").lower() == "barracks")
           for room in dev.get("rooms") or []):
        risks.append("The current barracks is very unimpressive; cramped, dirty sleeping quarters and ground beds can keep mood low even after everyone gets indoors.")
    if idle and people:
        risks.append("Healthy colonists are idle; waiting creates no work. Issue a concrete order or set a usable priority.")
    if any(c.get("in_mental_state") for c in people):
        risks.append("A colonist is in a mental break and may ignore forced jobs. Do not repeatedly assign that pawn the same task; protect food and safety until it passes.")
    if pending_projects and not (dev.get("item_counts") or {}).get("WoodLog", 0):
        forecast = [float(value) for value in weather.get("next_twelfth_average_temperatures") or []]
        future_cold = (f" A coming five-day average is {round(min(forecast))} C; "
                       "an open bedroom offers no shelter from hypothermia."
                       if forecast and min(forecast) < 5 else "")
        risks.append("Construction is queued but accessible wood is zero; harvest nearby mature trees "
                     "and haul logs before wooden walls or a campfire can be finished." + future_cold)
    if pending_projects and not construction_workers:
        risks.append("No living colonist can do Construction. Unfinished buildings cannot progress until the colony gains a capable worker.")
    research_bench_missing = not any("ResearchBench" in str(name) and int(amount or 0) > 0
                                     for name, amount in counts.items())
    research_bench_pending = any("ResearchBench" in str(row.get("def_name") or "")
                                 for row in dev.get("construction_projects") or [])
    if research_bench_missing and not research_bench_pending and dev.get("research_bench_options"):
        risks.append("No completed research bench or bench blueprint exists. Research is blocked until the first affordable bench is built.")
    if (not research_bench_missing
            and str((dev.get("current_research") or {}).get("name") or "none").lower() != "none"
            and not researcher_is_dedicated(snapshot)):
        risks.append("A research project and bench exist, but no worker has protected research time. Research priority 1 alone can lose to other priority-1 jobs; reserve one worker without removing emergency duties.")
    if dev.get("research_misalignment"):
        item = dev["research_misalignment"]
        risks.append(f"The new {item.get('current')} project has only {item.get('progress_percent')}% progress and does not support the chosen income or victory route; Laya can redirect it to a live aligned project.")
    if (snapshot.get("map") or {}).get("enemies", 0):
        risks.append("Hostiles can injure or kidnap colonists; combat consumes food and rest.")
    fires = (dev.get("fire_situation") or {}).get("fires") or []
    threatened_fires = [fire for fire in fires if int(fire.get("nearby_player_buildings") or 0) > 0]
    if threatened_fires:
        risks.append(f"{len(threatened_fires)} live fire(s) threaten colony buildings; firefighters only work inside Home area.")
    if any(a.get("tendable_now") or bridge.first_number(a.get("bleeding_rate")) > 0.05 for a in animals):
        risks.append("An injured colony animal may worsen or die without care.")
    if any(a.get("requires_pen") is True and not a.get("has_suitable_enclosed_pen") for a in animals):
        risks.append("Roaming livestock has no completed reachable enclosed pen and may leave the colony.")
    active_hostiles = [row for row in (snapshot.get("combat") or {}).get("hostiles", [])
                       if not row.get("is_dead") and not row.get("is_downed")]
    return {
        "course": {
            **{name: doctrine.get(name) for name in (
                "primary_direction", "economy_product", "diplomacy", "endgame") if doctrine.get(name)},
            "recorded_sales": (dev.get("economic_outlook") or {}).get("recent_approx_sale_value", 0),
        },
        "income": {key: (dev.get("economic_outlook") or {}).get(key) for key in (
            "horizon", "next_milestone", "buyer_route", "recent_approx_sale_value")
            if (dev.get("economic_outlook") or {}).get(key) is not None},
        "goal": "Develop a thriving colony; choose strategy and next action, not a scripted build order.",
        "threats": (snapshot.get("map") or {}).get("enemies", 0),
        "threat_state": {
            "phase": "preparing" if active_hostiles and all(
                bridge.combat_planner.hostile_is_preparing(row) for row in active_hostiles
            ) else "active" if active_hostiles else "unknown" if (snapshot.get("map") or {}).get("enemies", 0) else "none",
            "nearest": round(min((bridge.first_number(row.get("distance_to_nearest_opponent"), 9999)
                                  for row in active_hostiles), default=9999)),
        },
        "people": len(people),
        "home": {"roofed_sleepers": sheltered_beds, "real_beds": real_beds,
                 "roofed_real_beds": sheltered_real_beds,
                 "exposed_days": exposed_days, "target": len(people),
                 "threatened_fires": len(threatened_fires),
                 "prison_beds": sum(bool(b.get("for_prisoners")) for b in dev.get("buildings") or []),
                 "meals_per_person": int(resources.get("meals") or 0) // max(1, len(people)),
                 "bed_moves": len({key.split("|", 1)[0] for key in
                                   (dev.get("bed_assignment_options") or {})}),
                 "growth_ready": bool(dev.get("population_growth_context"))},
        "needs": {
            "food": resources.get("food", 0), "meals": resources.get("meals", 0),
            "raw_food": resources.get("raw_food", 0),
            "food_runway_days_estimate": food_runway,
            "crop_growth_percent": crop_progress,
            "harvestable_crops": sum(int(group.get("count") or 0) for group in early_crops.values()),
            "nutrition_rotting_soon": resources.get("nutrition_rotting_soon", 0),
            "least_hunger": round(least_hunger, 2), "least_rest": round(least_rest, 2),
            "nearest_meal_to_base": meal_distance,
            "downed": sum(bool(c.get("downed")) for c in people),
            "patients": [{"name": str(c.get("name") or "")[:32], "health": c.get("health"), "bleed": c.get("bleeding_rate")} for c in sick],
            "beds": bed_count, "sheltered_beds": sheltered_beds,
            "corpses": len(dev.get("corpses") or []),
            "forbidden_stacks": len(forbidden),
            "idle_workers": len(idle),
            "pending_blueprints": pending_projects,
            "research_bench_missing": research_bench_missing,
            "active_builders": active_builders,
            "construction_workers": construction_workers,
            "eligible_builders": eligible_builders,
            "worst_barracks": [
                {"impressiveness": round(float(room.get("impressiveness") or 0)),
                 "cells": int(room.get("cells_count") or 0),
                 "temperature": round(float(room.get("temperature") or 0)),
                 "glow": round(float(room.get("average_glow") or 0), 2)}
                for room in dev.get("rooms") or []
                if str(room.get("role_label") or "").lower() == "barracks"
            ][:2],
            "low_mood": mood_signals,
        },
        "stock": {name: (dev.get("item_counts") or {}).get(name, 0) for name in ("WoodLog", "Steel", "ComponentIndustrial", "MedicineIndustrial")},
        "environment": {"temp": weather.get("temperature"), "growing": weather.get("growth_season_now"),
                        "coldest_upcoming_five_day_average_c": round(min(
                            float(value) for value in weather.get("next_twelfth_average_temperatures") or []
                        )) if weather.get("next_twelfth_average_temperatures") else None},
        "heat": {"outside_c": heat.get("outside_c"),
                 "coolest_roofed_c": heat.get("coolest_roofed_c"),
                 "patients": [{"name": patient.get("name"), "severity": patient.get("severity"),
                               "downed": patient.get("downed")}
                              for patient in (heat.get("patients") or [])[:2]]} if heat else {},
        "cold": {"outside_c": cold.get("outside_c"),
                 "warmest_roofed_c": cold.get("warmest_roofed_c"),
                 "patients": [{"name": patient.get("name"), "severity": patient.get("severity"),
                               "downed": patient.get("downed")}
                              for patient in (cold.get("patients") or [])[:2]]} if cold else {},
        "research": (dev.get("current_research") or {}).get("name"),
        "risks": risks,
        "recent": (dev.get("recent_decisions") or [])[-2:],
        "player_weights": (dev.get("user_preferences") or {}).get("priorities") or {},
        "guidance": str((dev.get("user_preferences") or {}).get("personal_note") or "")[:160],
        "animals": {"count": len(animals),
                    "unpenned_roamers": sum(a.get("requires_pen") is True and not a.get("has_suitable_enclosed_pen") for a in animals),
                    "hungry": sum(bridge.first_number(a.get("hunger"), 1) < 0.3 for a in animals),
                    "tendable": sum(bool(a.get("tendable_now")) for a in animals),
                    "lowest_health": round(min((bridge.first_number(a.get("health"), 1) for a in animals), default=1), 2)},
    }


def fit_model_context(agent: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Keep the entire decision state visible to the loaded Laya checkpoint."""
    tokenizer = getattr(agent, "tok", None)
    if tokenizer is None:
        return state
    config = getattr(agent, "cfg", {}) or {}
    budget = max(64, int(config.get("max_len", 512)) - int(config.get("head_max_len", 192)) - 8)
    state = json.loads(json.dumps(state, ensure_ascii=False, default=str))

    def token_count() -> int:
        # We only need to know whether the state exceeds the budget. A bounded
        # count avoids the tokenizer's 8192-token warning on crowded maps.
        payload = json.dumps(state, ensure_ascii=False)
        try:
            encoded = tokenizer(payload, add_special_tokens=False,
                                truncation=True, max_length=budget + 1)
        except TypeError:
            encoded = tokenizer(payload, add_special_tokens=False)
        return len(encoded["input_ids"])

    if token_count() <= budget:
        return state
    # Discard the least recent/exact details first, never the current food,
    # injuries or threats. A giant personal note cannot evict survival state.
    for key, replacement in (
        ("guidance", str(state.get("guidance") or "")[:60]),
        ("recent", list(state.get("recent") or [])[-1:]),
        ("player_weights", {}),
        ("income", {}),
        ("goal", "Develop the colony; choose the next action."),
    ):
        state[key] = replacement
        if token_count() <= budget:
            return state
    state["needs"]["patients"] = (state["needs"].get("patients") or [])[:1]
    if token_count() <= budget:
        return state
    state["risks"] = [str(risk)[:66] for risk in (state.get("risks") or [])[:2]]
    state["course"] = {key: str(value)[:24] for key, value in (state.get("course") or {}).items()}
    state["stock"] = {key: value for key, value in (state.get("stock") or {}).items() if value}
    state["guidance"] = str(state.get("guidance") or "")[:30]
    if token_count() <= budget:
        return state
    # A crowded event map must still produce a usable decision instead of
    # stopping the director because optional prose crowded out survival facts.
    essential = {
        "goal": "Choose feasible action.",
        "threats": state.get("threats"),
        "people": state.get("people"),
        "heat": state.get("heat"),
        "cold": state.get("cold"),
        "home": state.get("home"),
        "needs": {key: value for key, value in (state.get("needs") or {}).items() if key in {
            "food", "meals", "raw_food", "food_runway_days_estimate", "crop_growth_percent", "nutrition_rotting_soon", "least_hunger", "least_rest", "beds", "sheltered_beds", "downed", "patients", "forbidden_stacks", "idle_workers", "pending_blueprints", "active_builders", "construction_workers", "eligible_builders", "low_mood",
        }},
        "stock": {key: (state.get("stock") or {}).get(key, 0)
                  for key in ("WoodLog", "Steel", "ComponentIndustrial")},
        "risks": (state.get("risks") or [])[:2],
        "course": state.get("course") or {},
    }
    state = essential
    if token_count() <= budget:
        return state
    state["needs"]["patients"] = (state["needs"].get("patients") or [])[:1]
    state["needs"]["low_mood"] = (state["needs"].get("low_mood") or [])[:1]
    state["risks"] = [str(risk)[:48] for risk in state["risks"][:1]]
    if token_count() <= budget:
        return state
    state["stock"] = {"WoodLog": state["stock"]["WoodLog"]}
    if token_count() <= budget:
        return state
    # Preserve the immediate survival facts even for unusually verbose local
    # tokenizers. Failing here would stop the entire decision cycle.
    needs = state.get("needs") or {}
    home = state.get("home") or {}
    state = {
        "course": state.get("course") or {},
        "people": state.get("people"), "threats": state.get("threats"),
        "heat": state.get("heat") or {},
        "cold": state.get("cold") or {},
        "food": needs.get("food"), "meals": needs.get("meals"),
        "raw_food": needs.get("raw_food"),
        "food_runway_days_estimate": needs.get("food_runway_days_estimate"),
        "crop_growth_percent": needs.get("crop_growth_percent"),
        "hunger": needs.get("least_hunger"), "downed": needs.get("downed"),
        "idle": needs.get("idle_workers"), "roofed_beds": home.get("roofed_real_beds"),
        "wood": (state.get("stock") or {}).get("WoodLog"),
        "meals_per_person": home.get("meals_per_person"),
        "prison_beds": home.get("prison_beds"),
        "bed_moves": home.get("bed_moves"),
        "growth_ready": home.get("growth_ready"),
        "harvestable_crops": needs.get("harvestable_crops"),
    }
    if token_count() <= budget:
        return state
    for key in ("wood", "idle", "roofed_beds", "hunger", "downed", "food", "raw_food", "meals", "crop_growth_percent"):
        state.pop(key, None)
        if token_count() <= budget:
            return state
    return state


def candidate_actions(client: bridge.RimApiClient, snapshot: dict[str, Any], map_state: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    dev = snapshot["development"]
    map_id = int(snapshot["map"].get("id") or 0)
    # The production collector supplies these fields; keep incomplete replay
    # snapshots usable now that emergency branches no longer return early.
    for key, default in (
        ("building_counts", {}), ("zones", []), ("finished_research", []),
        ("current_research", {}), ("work_tables", []), ("item_counts", {}),
        ("plants", []), ("things", []), ("rooms", []), ("research_tree", []),
    ):
        dev.setdefault(key, default)
    counts = dev["building_counts"]
    cooking_defs = {"Campfire", "FueledStove", "ElectricStove"}
    has_cooking_station = any(int(counts.get(name) or 0) > 0 for name in cooking_defs)
    dev.pop("cold_start_focus", None)
    dev.pop("urgent_cooking_projects", None)
    dev.pop("construction_project_options", None)
    zones = dev["zones"]
    tick = int(snapshot["game"].get("tick") or 0)
    finished = set(map(str, dev["finished_research"]))
    current = str((dev["current_research"] or {}).get("name") or "none")
    details: dict[str, Any] = {}
    one_time: list[str] = []
    item_counts = dev.get("item_counts", {})
    can_work = lambda work: bridge.choose_worker(snapshot.get("colonists", []), work) is not None
    # Research benches are Building_ResearchBench, not Building_WorkTable;
    # /map/work-tables intentionally omits them.
    has_research_bench = any("ResearchBench" in str(name) and int(amount or 0) > 0
                             for name, amount in counts.items())
    rolled_back_orders = reconcile_issued_timeline(map_state, tick)
    if rolled_back_orders:
        details["discarded_future_orders"] = rolled_back_orders
    resources = (snapshot.get("map") or {}).get("resources") or {}
    pending_cooking = any(str(row.get("def_name") or "") in cooking_defs
                          for row in dev.get("construction_projects") or [])
    campfire_issued = int((map_state.get("issued") or {}).get("campfire") or 0)
    old_cooking_plan = (pending_cooking and campfire_issued > 0
                        and tick - campfire_issued >= 30000)
    meal_threshold = max(12, (18 if old_cooking_plan else 8)
                         * len(snapshot.get("colonists") or []))
    cooking_gap = (not has_cooking_station
                   and int(resources.get("raw_food") or 0) >= 40
                   and int(resources.get("meals") or 0) <= meal_threshold)
    dev["cooking_gap_urgent"] = cooking_gap

    if relevant_forbidden(snapshot) and not issued_recently(
        map_state, "unforbid_supplies", tick, retry_ticks=2500
    ):
        one_time.append("unforbid_supplies")

    unarmed_fighters = [pawn for pawn in (snapshot.get("combat") or {}).get("colonists", [])
                        if not pawn.get("is_dead") and not pawn.get("is_downed")
                        and not pawn.get("has_ranged_weapon") and bridge.first_number(pawn.get("manipulation"), 1) >= 0.65]
    free_weapons = [weapon for weapon in (snapshot.get("combat") or {}).get("available_weapons", [])
                    if weapon.get("is_ranged") and weapon.get("id") is not None
                    and any(not bridge.combat_planner.errand_exposed(
                        snapshot, weapon.get("position"), pawn.get("position"))
                        for pawn in unarmed_fighters)]
    if unarmed_fighters and free_weapons and not issued_recently(map_state, "equip_colonists", tick, retry_ticks=2500):
        details["equip_context"] = {"unarmed": len(unarmed_fighters), "available_ranged": len(free_weapons)}
        one_time.append("equip_colonists")

    issued = map_state.setdefault("issued", {})
    resources = snapshot["map"]["resources"]
    lowest_food = min((float(c.get("hunger") or 0.0) for c in snapshot["colonists"]), default=1.0)
    meals = reachable_meals(snapshot)
    sealed_food_store = legacy_freezer_entrance(snapshot)
    if sealed_food_store:
        dev["sealed_food_store"] = sealed_food_store
        details["sealed_food_store"] = sealed_food_store
        door_materials = {material: f"{int(item_counts.get(material) or 0)} available; 25 needed for one door"
                          for material in ("WoodLog", "Steel") if int(item_counts.get(material) or 0) >= 25}
        details["freezer_door_materials"] = door_materials
        dev["freezer_door_materials"] = door_materials
        if sealed_food_store["status"] == "sealed" and not issued_recently(
            map_state, "open_sealed_food_store", tick, retry_ticks=2500
        ):
            one_time.append("open_sealed_food_store")
        elif (sealed_food_store["status"] == "open" and door_materials
              and not any(str(project.get("def_name") or "") == "Door"
                          and (project.get("position") or {}).get("x") == sealed_food_store["position"]["x"]
                          and (project.get("position") or {}).get("z") == sealed_food_store["position"]["z"]
                          for project in dev.get("construction_projects") or [])
              and not issued_recently(map_state, "finish_freezer_entrance", tick, retry_ticks=15000)):
            one_time.append("finish_freezer_entrance")
    meal_attempts = map_state.setdefault("meal_attempts", {})
    for colonist in snapshot["colonists"]:
        attempt = meal_attempts.get(str(colonist.get("id")))
        if not isinstance(attempt, dict):
            continue
        if float(colonist.get("hunger") or 0) > float(attempt.get("hunger") or 0) + 0.15:
            meal_attempts.pop(str(colonist["id"]), None)
        elif (tick - int(attempt.get("tick") or 0) >= 1800
              and int(attempt.get("checked_tick") or 0) < int(attempt.get("tick") or 0)):
            attempt["failures"] = int(attempt.get("failures") or 0) + 1
            attempt["checked_tick"] = tick
    sealed = {str(pawn["id"]): sealed_colonist_walls(snapshot, pawn)
              for pawn in snapshot["colonists"] if pawn.get("id") is not None}
    trapped = [pawn for pawn in snapshot["colonists"]
               if not pawn.get("in_mental_state") and (
                   sealed.get(str(pawn.get("id"))) or (
                       not pawn.get("downed") and float(pawn.get("hunger") or 0) < 0.15
                       and int((meal_attempts.get(str(pawn.get("id"))) or {}).get("failures") or 0) >= 2
                   ))]
    blocked_pawn_ids: set[str] = {pawn_id for pawn_id, walls in sealed.items() if walls}
    if trapped and not issued_recently(map_state, "open_blocked_food_path", tick, retry_ticks=900):
        victim = min(trapped, key=lambda pawn: (
            not bool(sealed.get(str(pawn.get("id")))), float(pawn.get("hunger") or 0)))
        nearby_meal = min(meals, key=lambda meal: squared_distance(
            victim.get("position") or {}, meal.get("position") or {})) if meals else None
        victim_pos = victim.get("position") or {}
        walls = sealed.get(str(victim["id"])) or [
            row for row in dev.get("buildings", [])
            if row.get("def") == "Wall" and row.get("id") is not None
            and abs(int((row.get("position") or {}).get("x") or 0) - int(victim_pos.get("x") or 0))
            + abs(int((row.get("position") or {}).get("z") or 0) - int(victim_pos.get("z") or 0)) == 1
        ]
        builders = {pawn_id: criterion for pawn_id, criterion in worker_criteria(snapshot, "Construction").items()
                    if pawn_id != str(victim["id"])}
        if walls and builders:
            details["blocked_food_pawn"] = victim["name"]
            details["blocked_food_pawn_id"] = victim["id"]
            details["blocked_food_meal"] = nearby_meal.get("position") if nearby_meal else None
            details["blocked_food_wall_options"] = walls
            details["blocked_food_builders"] = builders
            dev["blocked_food_pawn"] = victim["name"]
            dev["blocked_food_pawn_id"] = victim["id"]
            dev["blocked_food_meal"] = nearby_meal.get("position") if nearby_meal else None
            dev["blocked_food_wall_options"] = walls
            dev["blocked_food_builders"] = builders
            dev["blocked_food_emergency"] = bool(sealed.get(str(victim["id"])))
            blocked_pawn_ids.add(str(victim["id"]))
            one_time.append("open_blocked_food_path")
    hungry_eaters: dict[str, str] = {}
    for colonist in snapshot["colonists"]:
        if (colonist.get("downed") or colonist.get("in_mental_state")
                or str(colonist.get("id")) in blocked_pawn_ids
                or float(colonist.get("hunger") or 0.0) >= 0.35
                or str(colonist.get("current_job") or "").lower() == "ingest"
                or bridge.first_number((colonist.get("capacities") or {}).get("moving"), 1.0) < 0.3
                or issued_recently(map_state, f"meal_order:{colonist['id']}", tick, retry_ticks=2500)):
            continue
        if meals:
            distance = min(squared_distance(colonist.get("position") or {}, meal.get("position") or {})
                           for meal in meals) ** 0.5
            if distance > 60:
                continue
            hungry_eaters[str(colonist["id"])] = (
                f"{colonist.get('name') or colonist['id']}: food need {float(colonist.get('hunger') or 0):.2f}; "
                f"nearest unlocked meal {distance:.0f} tiles; current job {colonist.get('current_job') or 'unknown'}"
            )
    if hungry_eaters:
        details["hungry_eater_options"] = hungry_eaters
        dev["hungry_eater_options"] = hungry_eaters
        one_time.append("eat_available_meal")
    anchor = map_state.get("anchor") or {"x": 125, "z": 125}
    fire_options = {
        str(fire["id"]): (
            f"Fire size {float(fire.get('size') or 0):.1f} at ({fire.get('x')},{fire.get('z')}); "
            f"{int(fire.get('nearby_player_buildings') or 0)} nearby colony buildings; outside Home area"
        )
        for fire in (dev.get("fire_situation") or {}).get("fires") or []
        if fire.get("id") is not None and not fire.get("in_home")
        and (int(fire.get("nearby_player_buildings") or 0) > 0
             or (int(fire.get("x") or 0) - int(anchor["x"])) ** 2
             + (int(fire.get("z") or 0) - int(anchor["z"])) ** 2 <= 14 ** 2)
    }
    if fire_options and not issued_recently(map_state, "expand_home_area", tick, retry_ticks=600):
        dev["fire_options"] = fire_options
        one_time.append("expand_home_area")
    home_fires = [fire for fire in (dev.get("fire_situation") or {}).get("fires") or []
                  if fire.get("in_home") and int(fire.get("nearby_player_buildings") or 0) > 0]
    firefighters = firefighter_priority_options(snapshot)
    if home_fires and firefighters:
        details["firefighter_worker_ids"] = [int(pawn["id"]) for pawn in firefighters]
        dev["active_home_fires"] = len(home_fires)
        one_time.append("prioritize_firefighting")
    nearest_meal_to_base = min(
        (squared_distance(anchor, meal.get("position") or {}) ** 0.5 for meal in meals),
        default=None,
    )
    dev["food_distance_context"] = {
        "nearest_meal_to_base": round(nearest_meal_to_base) if nearest_meal_to_base is not None else None,
        "meal_stacks": len(meals),
    }
    if (not sealed_food_store and nearest_meal_to_base is not None and nearest_meal_to_base > 50
            and not any("Stockpile" in str(zone.get("type")) and "Laya Forward Food Cache" in str(zone.get("label") or "")
                        for zone in dev["zones"])
            and not issued_recently(map_state, "nearby_food_cache", tick, retry_ticks=3000)):
        one_time.append("create_nearby_food_cache")
    hungry_colonist_patients = sorted(
        (colonist for colonist in snapshot["colonists"] if colonist_needs_assisted_feeding(colonist)),
        key=lambda colonist: bridge.first_number(colonist.get("hunger"), 1.0),
    )
    if int(resources.get("food") or 0) > 0 and hungry_colonist_patients:
        patient = hungry_colonist_patients[0]
        patient_id = int(patient["id"])
        if not issued_recently(
            map_state, f"colonist_feed:{patient_id}", tick,
            retry_ticks=PATIENT_FEED_RETRY_TICKS,
        ):
            details["hungry_colonist_id"] = patient_id
            details["hungry_colonist_name"] = str(patient.get("name") or patient_id)
            one_time.append("feed_hungry_colonist")
    # One starving pawn with stocked meals needs access or feeding, not a hunt
    # across the map. Treat actual supply depletion as the hunting emergency.
    food_runway = estimated_food_runway_days(resources, len(snapshot["colonists"]))
    food_emergency = (food_runway is not None and food_runway < 5) or lowest_food < 0.12
    supply_emergency = (food_runway is not None and food_runway < 3) or (lowest_food < 0.12 and not meals)
    cultivated_food_defs = {"Plant_Rice", "Plant_Potato", "Plant_Corn"}
    # Early cutting is a real last-mile food option, not routine harvesting.
    # With several days of stocked meals, growing rice can mature while Laya
    # chooses foraging, hunting, construction or other work instead.
    if ((food_runway is not None and food_runway < 2.5)
            and int(resources.get("raw_food") or 0) < max(40, len(snapshot["colonists"]) * 8)
            and can_work("PlantCutting")
            and not issued_recently(map_state, "early_crop_harvest", tick, retry_ticks=12000)):
        crop_groups: dict[str, dict[str, Any]] = {}
        for plant in dev.get("plants", []):
            name = str(plant.get("def_name") or "")
            if (name not in cultivated_food_defs or not plant.get("harvestable_now")
                    or plant.get("thing_id") is None):
                continue
            pos = plant.get("position") or {}
            if squared_distance(pos, anchor) > 60 ** 2:
                continue
            plant_id = int(plant["thing_id"])
            if issued_recently(map_state, f"early_crop:{plant_id}", tick, retry_ticks=60000):
                continue
            group = crop_groups.setdefault(name, {
                "label": str(plant.get("label") or name), "count": 0,
                "expected_yield": 0, "growth_sum": 0.0, "ranked_ids": [],
            })
            growth = float(plant.get("growth") or 0.0)
            group["count"] += 1
            group["expected_yield"] += int(plant.get("harvest_yield") or 0)
            group["growth_sum"] += growth
            group["ranked_ids"].append((growth, plant_id))
        if crop_groups:
            for group in crop_groups.values():
                group["average_growth"] = round(group.pop("growth_sum") / group["count"], 2)
                group["ids"] = [plant_id for _, plant_id in sorted(group.pop("ranked_ids"), reverse=True)]
            details["early_crop_options"] = crop_groups
            dev["early_crop_options"] = crop_groups
            one_time.append("harvest_food_crops_early")
    if food_emergency:
        anchor = map_state.get("anchor") or {"x": 125, "z": 125}
        # At zero stored food, do not wait for a ripe field when edible wild
        # plants and safe small game sit just beyond the normal search ring.
        # Keep the expansion bounded so starving workers do not cross the map.
        radius_squared = (90 if int(resources.get("food") or 0) == 0 else 60) ** 2
        wild_food_groups: dict[str, dict[str, Any]] = {}
        for plant in dev.get("plants", []):
            if str(plant.get("def_name") or "") in cultivated_food_defs:
                continue
            harvested = str(plant.get("harvested_thing_def") or "")
            if not plant.get("harvestable_now") or not is_edible_wild_harvest(harvested):
                continue
            plant_id = int(plant.get("thing_id") or -1)
            if plant_id < 0 or issued_recently(map_state, f"wild_plant:{plant_id}", tick, retry_ticks=120000):
                continue
            pos = plant.get("position") or {}
            if (int(pos.get("x") or 0) - int(anchor["x"])) ** 2 + (int(pos.get("z") or 0) - int(anchor["z"])) ** 2 > radius_squared:
                continue
            if bridge.combat_planner.errand_exposed(snapshot, pos):
                continue
            name = str(plant.get("def_name") or harvested)
            group = wild_food_groups.setdefault(name, {
                "label": str(plant.get("label") or name),
                "harvested_thing": harvested,
                "count": 0,
                "expected_yield": 0,
                "ids": [],
            })
            group["count"] += 1
            group["expected_yield"] += int(plant.get("harvest_yield") or 0)
            group["ids"].append(plant_id)

        combat_rows = snapshot.get("combat", {}).get("colonists", [])
        healthy_armed = [
            row for row in combat_rows
            if row.get("has_ranged_weapon") and not row.get("is_downed") and float(row.get("health") or 0.0) >= 0.65
        ]
        emergency_hunt_options = []
        if healthy_armed and supply_emergency:
            for animal in snapshot.get("wild_animals", []):
                pos = animal.get("position") or {}
                close = (int(pos.get("x") or 0) - int(anchor["x"])) ** 2 + (int(pos.get("z") or 0) - int(anchor["z"])) ** 2 <= radius_squared
                safe = (
                    close
                    and not animal.get("predator")
                    and "boom" not in str(animal.get("def") or "").lower()
                    and float(animal.get("harm_revenge_chance") or 0.0) <= 0.05
                    and float(animal.get("combat_power") or 0.0) <= 100
                    and not issued_recently(map_state, f"hunt:{animal.get('id')}", tick, retry_ticks=60000)
                )
                if safe:
                    emergency_hunt_options.append(animal)
        emergency_hunt_options.sort(
            key=lambda animal: (int(animal.get("meat_amount") or 0), -float(animal.get("combat_power") or 0.0)),
            reverse=True,
        )

        emergency_actions: list[str] = []
        if wild_food_groups and supply_emergency and not issued_recently(map_state, "harvest", tick, retry_ticks=2500):
            details["wild_plant_options"] = wild_food_groups
            dev["wild_plant_options"] = wild_food_groups
            emergency_actions.append("harvest_local_plants")
        if emergency_hunt_options:
            details["hunt_options"] = emergency_hunt_options
            details["fighter_context"] = {
                "healthy_ranged": len(healthy_armed),
                "average_shooting": round(sum(int(row.get("shooting_skill") or 0) for row in healthy_armed) / len(healthy_armed), 1),
                "food_emergency": True,
            }
            dev["hunt_options"] = emergency_hunt_options
            dev["fighter_context"] = details["fighter_context"]
            emergency_actions.append("designate_safe_hunting")
        if wild_food_groups and can_work("PlantCutting") and not issued_recently(map_state, "priority:PlantCutting", tick, retry_ticks=15000):
            emergency_actions.append("prioritize_plant_cutting")
        if emergency_hunt_options and can_work("Hunting") and not issued_recently(map_state, "priority:Hunting", tick, retry_ticks=15000):
            emergency_actions.append("prioritize_hunting")
        if (int(resources.get("raw_food") or 0) > 0 and has_cooking_station
                and can_work("Cooking") and not issued_recently(map_state, "priority:Cooking", tick, retry_ticks=15000)):
            emergency_actions.append("prioritize_cooking")
        details["food_emergency_context"] = {
            "food": int(resources.get("food") or 0),
            "raw_food": int(resources.get("raw_food") or 0),
            "meals": int(resources.get("meals") or 0),
            "lowest_hunger": round(lowest_food, 3),
            "harvestable_food_types": list(wild_food_groups),
            "safe_hunt_targets": len(emergency_hunt_options),
        }
        dev["food_emergency_context"] = details["food_emergency_context"]
        one_time.extend(emergency_actions)

    human_corpses = corpse_rows(snapshot, "CorpsesHumanlike")
    all_corpses = corpse_rows(snapshot)
    if forbidden_corpses(snapshot) and not issued_recently(map_state, "unforbid_corpses", tick, retry_ticks=15000):
        one_time.append("unforbid_corpses")
    human_dump_exists = any("Laya Human Corpse Dump" in str(z.get("label") or "") for z in zones)
    animal_dump_exists = any("Laya Animal Carcasses" in str(z.get("label") or "") for z in zones)
    corpse_actions: list[str] = []
    if human_corpses and not human_dump_exists and "human_corpse_dump" not in issued:
        corpse_actions.append("create_human_corpse_dump")
    grave_projects = sum(str(row.get("def_name") or "") == "Grave"
                         for row in dev.get("construction_projects") or [])
    existing_graves = int(counts.get("Grave") or 0) + grave_projects
    if (human_corpses and existing_graves < min(4, len(human_corpses))
            and not issued_recently(map_state, "cemetery", tick, retry_ticks=6000)):
        details["grave_count"] = min(8, max(2, len(human_corpses))) - existing_graves
        corpse_actions.append("build_cemetery")
    stone_blocks = [name for name, amount in item_counts.items() if name.startswith("Blocks") and int(amount or 0) >= 170]
    if (
        human_corpses and counts.get("ElectricCrematorium", 0) == 0 and stone_blocks
        and int(item_counts.get("Steel") or 0) >= 70
        and int(item_counts.get("ComponentIndustrial") or 0) >= 4
        and max((int((c.get("skills", {}).get("Construction") or {}).get("level") or 0) for c in snapshot["colonists"]), default=0) >= 4
        and "crematorium" not in issued
    ):
        details["crematorium_stuff"] = stone_blocks[0]
        corpse_actions.append("build_crematorium")
    elif human_corpses and counts.get("ElectricCrematorium", 0) > 0 and not issued_recently(map_state, "crematorium_bill", tick, retry_ticks=60000):
        corpse_actions.append("build_crematorium")
    animal_corpses = [row for row in corpse_rows(snapshot, "CorpsesAnimal")
                      if not row.get("is_forbidden")]
    if animal_corpses and not animal_dump_exists and "animal_corpse_dump" not in issued:
        corpse_actions.append("create_animal_corpse_dump")
    butcher_station = any(int(counts.get(name) or 0) > 0 for name in ("ButcherSpot", "TableButcher"))
    butcher_project = any(str(project.get("def_name") or "") in {"ButcherSpot", "TableButcher"}
                          for project in dev.get("construction_projects") or [])
    if animal_corpses and not butcher_station and not butcher_project:
        dev["butchery_gap"] = len(animal_corpses)
        if not issued_recently(map_state, "butcher_spot", tick, retry_ticks=1500):
            corpse_actions.append("build_butcher_spot")
    if all_corpses and can_work("Hauling") and (human_dump_exists or animal_dump_exists or counts.get("Grave", 0) > 0) and not issued_recently(map_state, "priority:Burial", tick, retry_ticks=30000):
        corpse_actions.append("prioritize_burial")
    if corpse_actions:
        details["corpse_context"] = {
            "human": len(human_corpses),
            "animal": len(corpse_rows(snapshot, "CorpsesAnimal")),
            "butchery_gap": dev.get("butchery_gap", 0),
            "colonists": len(snapshot["colonists"]),
            "human_dump_exists": human_dump_exists,
            "animal_dump_exists": animal_dump_exists,
            "graves": counts.get("Grave", 0),
            "crematorium": counts.get("ElectricCrematorium", 0),
        }
        dev["corpse_context"] = details["corpse_context"]
        one_time.extend(corpse_actions)

    food_zone = any(
        "Stockpile" in str(z.get("type"))
        and any(label in str(z.get("label") or "") for label in ("Laya Food", "Laya Temporary Food"))
        for z in zones
    )
    if not food_zone and not issued_recently(map_state, "food_stockpile", tick, retry_ticks=3000):
        one_time.append("create_food_stockpile")
    pending_sleeping_spots = sum(str(project.get("def_name") or "") == "SleepingSpot"
                                 for project in dev.get("construction_projects") or [])
    usable_beds, sheltered_beds = sleeping_place_counts(dev)
    indoor_sleeping_spot = empty_indoor_sleeping_spot(dev, anchor) if sheltered_beds is not None else None
    if ((usable_beds + pending_sleeping_spots < len(snapshot["colonists"])
            or (sheltered_beds is not None and sheltered_beds < len(snapshot["colonists"])
                and indoor_sleeping_spot is not None))
            and not issued_recently(map_state, "sleeping_spots", tick, retry_ticks=3000)):
        if indoor_sleeping_spot is not None:
            details["indoor_sleeping_spot"] = indoor_sleeping_spot
        one_time.append("build_sleeping_spots")

    scheduled_recreation = set(map(int, map_state.get("recreation_schedules") or []))
    recreation_options = {
        str(pawn["id"]): (
            f"{pawn.get('name')}: mood {bridge.first_number(pawn.get('mood'), 0.5):.2f}, "
            f"recreation {bridge.first_number(pawn.get('joy'), 0.5):.2f}, "
            f"rest {bridge.first_number(pawn.get('rest'), 0.5):.2f}, "
            f"pain {bridge.first_number(pawn.get('pain')):.2f}; "
            "two Joy hours protect mood but reduce work time"
        )
        for pawn in snapshot["colonists"]
        if pawn.get("id") is not None and int(pawn["id"]) not in scheduled_recreation
        and not pawn.get("downed")
        and bridge.first_number(pawn.get("joy"), 0.5) < 0.55
        and bridge.first_number(pawn.get("mood"), 0.5) < 0.6
    }
    if recreation_options:
        details["recreation_schedule_options"] = recreation_options
        dev["recreation_schedule_options"] = recreation_options
        one_time.append("schedule_recreation")

    recreation_defs = {"HorseshoesPin", "ChessTable", "PokerTable", "BilliardsTable"}
    pending_recreation = any(str(project.get("def_name") or "") in recreation_defs
                             for project in dev.get("construction_projects") or [])
    if (not any(int(counts.get(name) or 0) for name in recreation_defs)
            and not pending_recreation and int(item_counts.get("WoodLog") or 0) >= 10
            and not issued_recently(map_state, "recreation_pin", tick, retry_ticks=30000)):
        one_time.append("build_recreation_pin")

    best_builder = max(
        (int((c.get("skills", {}).get("Construction") or {}).get("level") or 0) for c in snapshot["colonists"]),
        default=0,
    )
    sheltered_cells = {
        (int(cell["x"]), int(cell["z"]))
        for room in dev.get("rooms") or []
        if not room.get("touches_map_edge") and not room.get("is_prison_cell")
        and not room.get("is_doorway") and not room_is_ancient_danger(room)
        and int(room.get("open_roof_count") or 0) == 0
        for cell in room.get("cells") or []
        if cell.get("x") is not None and cell.get("z") is not None
        and abs(int(cell["x"]) - int(anchor["x"])) <= 12
        and abs(int(cell["z"]) - int(anchor["z"])) <= 12
    }
    pending_beds = sum(
        str(project.get("def_name") or "") == "Bed"
        and (int((project.get("position") or {}).get("x") or -999),
             int((project.get("position") or {}).get("z") or -999)) in sheltered_cells
        for project in dev.get("construction_projects") or []
    )
    failed_bed_sites = {(int(row["x"]), int(row["z"])) for row in map_state.get("failed_bed_sites") or []}
    indoor_bed_site = empty_indoor_sleeping_spot(dev, anchor, failed_bed_sites)
    replacement_spot = (replaceable_indoor_sleeping_spot(
        dev, anchor, snapshot["colonists"], failed_bed_sites)
        if indoor_bed_site is None else None)
    sheltered_real_beds = sheltered_real_bed_count(dev, anchor) or 0
    missing_beds = max(0, len(snapshot["colonists"]) - sheltered_real_beds - pending_beds)
    bed_materials = {
        material: f"{int(item_counts.get(material) or 0)} available; 45 needed per bed"
        for material in ("WoodLog", "Steel", "BlocksGranite", "BlocksSlate", "BlocksMarble", "BlocksSandstone", "BlocksLimestone")
        if int(item_counts.get(material) or 0) >= 45
    }
    if (
        missing_beds and (indoor_bed_site is not None or replacement_spot is not None)
        and bed_materials and best_builder >= 3
        and not issued_recently(map_state, "basic_beds", tick, retry_ticks=5000)
    ):
        details["basic_bed_count"] = 1
        details["basic_bed_materials"] = bed_materials
        details["indoor_bed_site"] = indoor_bed_site or replacement_spot["position"]
        if replacement_spot is not None:
            details["replace_sleeping_spot_id"] = replacement_spot["id"]
        dev["basic_bed_materials"] = bed_materials
        one_time.append("build_basic_beds")

    real_beds = [b for b in dev.get("buildings") or []
                 if str(b.get("def") or "") in {"Bed", "HospitalBed"}
                 and b.get("id") is not None and not b.get("for_prisoners")]
    sheltered_bed_ids = {
        int(bed_id)
        for room in dev.get("rooms") or []
        if not room.get("touches_map_edge") and not room.get("is_prison_cell")
        and not room.get("is_doorway") and not room_is_ancient_danger(room)
        and int(room.get("open_roof_count") or 0) == 0
        for bed_id in room.get("contained_beds_ids") or []
    }
    sleeping_spot_ids = {int(b["id"]) for b in dev.get("buildings") or []
                         if str(b.get("def") or "") == "SleepingSpot" and b.get("id") is not None}
    assigned_beds = set(map(int, (map_state.get("assigned_real_beds") or {}).values())) & sheltered_bed_ids
    combat_by_id = {int(p["id"]): p for p in (snapshot.get("combat") or {}).get("colonists") or []
                    if p.get("id") is not None}
    bed_pairs = {}
    for pawn in snapshot["colonists"]:
        if pawn.get("downed") or pawn.get("in_mental_state") or pawn.get("id") is None:
            continue
        pawn_id = int(pawn["id"])
        live = combat_by_id.get(pawn_id) or {}
        current_bed_id = live.get("current_job_target_id")
        prior_assignment = (map_state.get("assigned_real_beds") or {}).get(str(pawn_id))
        if (str(pawn.get("current_job") or "") != "LayDown"
                or current_bed_id not in sleeping_spot_ids | {int(b["id"]) for b in real_beds}
                or (current_bed_id in sheltered_bed_ids and current_bed_id not in sleeping_spot_ids)
                or (prior_assignment is not None and int(prior_assignment) in sheltered_bed_ids)):
            continue
        for bed in real_beds:
            if bed.get("medical") or int(bed["id"]) not in sheltered_bed_ids or int(bed["id"]) in assigned_beds:
                continue
            if int(bed["id"]) == current_bed_id:
                continue
            bed_pairs[f"{pawn_id}|{int(bed['id'])}"] = (
                f"{pawn.get('name')} is sleeping {'outdoors' if current_bed_id not in sheltered_bed_ids else 'on a ground spot'}; "
                f"claim the roofed {bed.get('label')} at {bed.get('position')}."
            )
    if bed_pairs:
        dev["bed_assignment_options"] = bed_pairs
        one_time.append("assign_real_bed")
    if (real_beds and not any(b.get("medical") for b in real_beds)
            and any(p.get("downed") or bridge.first_number(p.get("health"), 1) < 0.85
                    for p in snapshot["colonists"])):
        medical_beds = {str(b["id"]): f"{b.get('label')} at {b.get('position')}; reserve for patients"
                        for b in real_beds if not b.get("medical") and int(b["id"]) not in assigned_beds}
        if medical_beds:
            dev["emergency_medical_bed_options"] = medical_beds
            one_time.append("prepare_emergency_medical_bed")

    colony_animals = [animal for animal in snapshot.get("animals", []) if not animal.get("dead")]
    # Low health after a wound has already been tended only needs rest. Reissuing
    # a tend job every cycle steals a doctor and cannot improve the animal.
    tendable_animals = sorted(
        (
            animal for animal in colony_animals
            if animal_needs_tending(animal)
        ),
        key=lambda animal: (
            bridge.first_number(animal.get("health"), 1.0),
            -bridge.first_number(animal.get("bleeding_rate"), 0.0),
        ),
    )
    hungry_animals = sorted(
        (animal for animal in colony_animals if animal_needs_assisted_feeding(animal)),
        key=lambda animal: bridge.first_number(animal.get("hunger"), 1.0),
    )
    animal_emergency: list[str] = []
    if colony_animals and counts.get("AnimalSleepingSpot", 0) < len(colony_animals) and "animal_spots" not in map_state["issued"]:
        animal_emergency.append("build_animal_spots")
    if tendable_animals:
        target = tendable_animals[0]
        details["injured_animal_id"] = int(target["id"])
        details["injured_animal_name"] = str(target["name"])
        # At 3x, a 2,500-tick retry offers the same already-accepted tend
        # order on almost every decision cycle. Give the doctor time to reach
        # a non-bleeding patient, but retry sooner when blood loss is active.
        retry_ticks = (3000 if bridge.first_number(target.get("bleeding_rate"), 0.0) >= 0.05
                       else PATIENT_FEED_RETRY_TICKS)
        if not issued_recently(map_state, f"animal_care:{target['id']}", tick, retry_ticks=retry_ticks):
            animal_emergency.append("care_for_injured_animal")
    if hungry_animals:
        hungry = hungry_animals[0]
        details["hungry_animal_id"] = int(hungry["id"])
        details["hungry_animal_name"] = str(hungry["name"])
        # A successful patient-feed order needs time to reserve food, walk to the
        # bed and complete ingestion. Reissuing it every few seconds interrupts
        # normal work and creates an apparent decision loop.
        if not issued_recently(
            map_state, f"animal_feed:{hungry['id']}", tick,
            retry_ticks=PATIENT_FEED_RETRY_TICKS,
        ):
            animal_emergency.insert(0, "feed_hungry_animal")
    one_time.extend(animal_emergency)

    if not any("Growing" in str(z.get("type")) for z in zones) and not issued_recently(map_state, "growing", tick, retry_ticks=3000):
        one_time.append("create_growing_zone")

    finished_electricity = "Electricity" in finished
    freezer_plan = freezer_resource_plan(counts, item_counts, best_builder, finished, {
        str(row.get("def_name")) for row in dev.get("building_catalog") or []
        if row.get("is_power_generator")
    })
    if freezer_plan and "freezer" not in map_state["issued"]:
        details["freezer_include_generator"] = freezer_plan["include_generator"]
        details["freezer_requirements"] = freezer_plan["requirements"]
        one_time.append("build_freezer")

    if not any(
        "Stockpile" in str(z.get("type")) and "Laya Main" in str(z.get("label") or "")
        for z in zones
    ) and not issued_recently(map_state, "stockpile", tick, retry_ticks=3000):
        one_time.append("create_stockpile")
    storage_utilization = int((dev.get("storage") or {}).get("utilization_percent") or 0)
    if storage_utilization >= 90 and not issued_recently(map_state, "expand_stockpile", tick, retry_ticks=120000):
        one_time.append("expand_stockpile")
    current_doctrine = map_state.get("doctrine") or {}
    profession_context = dev.get("profession_context") or professions.profession_context(
        snapshot.get("colonists", []), dev.get("work_types") or []
    )
    dev["profession_context"] = profession_context

    night_owls = professions.night_owl_options(snapshot.get("colonists", []))
    unscheduled_night_owls = {
        pawn_id: description for pawn_id, description in night_owls.items()
        if str(pawn_id) not in {str(value) for value in map_state.get("night_owl_schedules", [])}
    }
    if unscheduled_night_owls:
        details["night_owl_options"] = unscheduled_night_owls
        dev["night_owl_options"] = unscheduled_night_owls
        one_time.append("optimize_night_owl_schedule")

    training = professions.training_options(snapshot.get("colonists", []), dev.get("work_types") or [])
    if training and not issued_recently(map_state, "skill_development", tick, retry_ticks=180000):
        details["skill_training_options"] = training
        dev["skill_training_options"] = training
        one_time.append("develop_colonist_skill")
    # A save rewind clears issue markers. Inspect the map itself so that a
    # partly built house is finished instead of ordering an identical second
    # house on top of it.
    nearby_shell = sum(
        str(building.get("def") or "") in {"Wall", "Door"}
        and squared_distance(building.get("position") or {}, anchor) <= 15 ** 2
        for building in dev.get("buildings") or []
    ) + sum(
        str(project.get("def_name") or "") in {"Wall", "Door"}
        and squared_distance(project.get("position") or {}, anchor) <= 15 ** 2
        for project in dev.get("construction_projects") or []
    )
    existing_starter_house = nearby_shell >= 6
    cold_start = starter_outdoor_c(dev) <= 5
    starter_materials_ready = not cold_start or (
        int(item_counts.get("WoodLog") or 0) >= 130
        or (int(item_counts.get("Steel") or 0) >= 110
            and int(item_counts.get("WoodLog") or 0) >= 20)
    )
    if (can_work("Construction") and starter_materials_ready
            and map_state.get("starter_site_verified", True)
            and "starter_base" not in map_state["issued"]
            and not existing_starter_house
            and sleeping_place_counts(dev)[1] != len(snapshot["colonists"])):
        one_time.append("build_starter_base")
    tables = dev["work_tables"]
    food_tables = [row for row in tables if str(row.get("thing_def") or "") in {
        "Campfire", "FueledStove", "ElectricStove", "TableButcher", "ButcherSpot",
    }]
    if (food_tables and food_bills_need_configuration(client, food_tables)
            and not issued_recently(map_state, "food_bills", tick, retry_ticks=15000)):
        one_time.append("configure_food_bills")
    cooking_options = cooking_rebalance_options(snapshot, int(map_state.get("reserved_researcher_id") or 0))
    if cooking_options and not issued_recently(map_state, "cooking_rebalance", tick, retry_ticks=12000):
        details["cooking_rebalance_options"] = cooking_options
        dev["cooking_rebalance_options"] = cooking_options
        one_time.append("rebalance_cooking")
    if "Electricity" in finished and can_work("Construction"):
        power_options = power_strategy_options(snapshot)
        generator_defs = {str(row.get("def_name")) for row in dev.get("building_catalog") or []
                          if row.get("is_power_generator")}
        generators_present = any(int(counts.get(name) or 0) > 0 for name in generator_defs)
        generators_planned = any(str(row.get("def_name")) in generator_defs
                                 for row in dev.get("construction_projects") or [])
        if (not generators_present and not generators_planned
                and len(power_options["choices"]) > 1
                and not issued_recently(map_state, "power_strategy", tick, retry_ticks=30000)):
            details["power_source_options"] = power_options
            dev["power_source_options"] = power_options
            one_time.append("build_power")
        if generators_present and int(item_counts.get("Steel") or 0) >= 2:
            source_nets = {row.get("power_net_id") for row in dev.get("buildings") or []
                           if str(row.get("def")) in generator_defs and row.get("power_net_id") is not None}
            disconnected = [row for row in dev.get("buildings") or []
                            if row.get("requires_power") and row.get("id") is not None
                            and row.get("power_net_id") not in source_nets]
            if disconnected and client is not None:
                terrain = dev.get("terrain") or bridge.safe_get(
                    client, "/api/v1/map/terrain", snapshot.setdefault("warnings", []),
                    map_id=map_id)
                if terrain:
                    connection_options = {}
                    for row in disconnected[:12]:
                        target = row.get("position") or {}
                        if target.get("x") is None or target.get("z") is None:
                            continue
                        if issued_recently(map_state, f"power_connection:{row['id']}", tick, retry_ticks=12000):
                            continue
                        route = power_conduit_route(dev, target, terrain)
                        if route and len(route) <= int(item_counts.get("Steel") or 0):
                            connection_options[str(row["id"])] = {
                                "building": str(row.get("def")), "position": target,
                                "route": route, "steel_cost": len(route),
                            }
                    if connection_options:
                        details["power_consumer_options"] = connection_options
                        dev["power_consumer_options"] = connection_options
                        one_time.append("connect_power_consumer")
    if dev.get("rooms") is not None:
        exposed = exposed_batteries(dev)
        dev["exposed_batteries"] = [
            {"id": battery.get("id"), "position": battery.get("position")}
            for battery in exposed
        ]
        materials = {name: f"{int(amount)} available; about 70 needed for walls and a door"
                     for name, amount in (item_counts or {}).items()
                     if (name in {"WoodLog", "Steel"} or name.startswith("Blocks"))
                     and int(amount or 0) >= 75}
        if (exposed and materials and best_builder >= 3
                and not issued_recently(map_state, "battery_shelter", tick, retry_ticks=30000)):
            dev["battery_shelter_options"] = {
                "batteries": exposed,
                "materials": materials,
            }
            one_time.append("build_battery_shelter")
    if "MicroelectronicsBasics" in finished and (counts.get("HiTechResearchBench", 0) == 0 or counts.get("MultiAnalyzer", 0) == 0) and "hitech" not in map_state["issued"]:
        one_time.append("build_hitech_lab")
    if "Fabrication" in finished and counts.get("FabricationBench", 0) == 0 and "fabrication" not in map_state["issued"]:
        one_time.append("build_fabrication")
    ship_ready = all(name in finished for name in RESEARCH_ROUTE[6:])
    chosen_endgame = str(current_doctrine.get("endgame") or "ship_escape")
    if ship_ready and chosen_endgame == "ship_escape" and counts.get("Ship_ComputerCore", 0) == 0 and "ship" not in map_state["issued"]:
        one_time.append("build_ship")
    if has_research_bench:
        research_tree = dev.get("research_tree") or []
        doctrine_research = strategy.doctrine_research_candidates(
            current_doctrine, research_tree
        ) if current_doctrine else {}
        all_aligned_research = strategy.doctrine_research_candidates(
            current_doctrine, research_tree, limit=max(12, len(research_tree))
        ) if current_doctrine else {}
        current_progress = bridge.first_number((dev.get("current_research") or {}).get("progress_percent"), 0.0)
        redirect_unaligned = (current.lower() != "none" and current not in all_aligned_research
                              and current_progress < 0.25 and bool(doctrine_research))
        if doctrine_research and (current.lower() == "none" or redirect_unaligned):
            details["doctrine_research_options"] = doctrine_research
            dev["doctrine_research_options"] = doctrine_research
            if redirect_unaligned:
                dev["research_misalignment"] = {
                    "current": current, "progress_percent": round(current_progress * 100, 1),
                    "reason": "The just-selected project does not advance the saved economy or victory course.",
                }
            one_time.append("advance_doctrine_research")
        # The live research catalogue below remains available even if no
        # project matches the saved doctrine. Never silently substitute a
        # hard-coded ship route for the model's research decision.
    anchor = map_state.get("anchor") or {"x": 125, "z": 125}
    weather = dev.get("weather") or {}
    outdoor_temperature = float(weather.get("temperature") or 0.0)
    climate_mode = "cold" if outdoor_temperature < 8 else "hot" if outdoor_temperature > 30 else "temperate"
    heat_patients = [
        {"name": str(pawn.get("name") or pawn.get("id")),
         "severity": round(float(condition.get("severity") or 0.0), 2),
         "downed": bool(pawn.get("downed")), "position": pawn.get("position") or {}}
        for pawn in snapshot.get("colonists") or []
        for condition in pawn.get("health_conditions") or []
        if str(condition.get("def_name") or "") == "Heatstroke"
    ]
    heat_patients.sort(key=lambda patient: (patient["severity"], patient["downed"]), reverse=True)
    if outdoor_temperature >= 32 or heat_patients:
        dev["heat_threat"] = {
            "outside_c": round(outdoor_temperature),
            "patients": heat_patients[:4],
            "coolest_roofed_c": round(min(
                (float(room.get("temperature") or 0.0) for room in dev.get("rooms") or []
                 if not room.get("touches_map_edge") and int(room.get("cells_count") or 0) <= 100),
                default=outdoor_temperature,
            )),
        }
        cooler_unlocked = any(
            row.get("def_name") == "PassiveCooler" and row.get("available_now")
            for row in dev.get("building_catalog") or []
        )
        if (cooler_unlocked and int(item_counts.get("WoodLog") or 0) >= 50
                and can_work("Construction")):
            occupied_project_cells = {
                (int((project.get("position") or {}).get("x") or -1),
                 int((project.get("position") or {}).get("z") or -1))
                for project in dev.get("construction_projects") or []
            }
            cool_room_options: dict[str, dict[str, Any]] = {}
            for room in dev.get("rooms") or []:
                if (room.get("touches_map_edge") or room.get("is_prison_cell")
                        or not room.get("contained_beds_ids") or not room.get("light_placement_cells")
                        or float(room.get("temperature") or 0.0) < 30):
                    continue
                defs = set(map(str, room.get("contained_thing_defs") or []))
                if defs & {"PassiveCooler", "Blueprint_PassiveCooler", "Frame_PassiveCooler"}:
                    continue
                cells = {(int(cell.get("x") or 0), int(cell.get("z") or 0))
                         for cell in room.get("cells") or []}
                if any(str(project.get("def_name") or "") == "PassiveCooler"
                       and (int((project.get("position") or {}).get("x") or -1),
                            int((project.get("position") or {}).get("z") or -1)) in cells
                       for project in dev.get("construction_projects") or []):
                    continue
                placement = next((cell for cell in room.get("light_placement_cells") or []
                                  if (int(cell.get("x") or 0), int(cell.get("z") or 0))
                                  not in occupied_project_cells), None)
                room_id = int(room.get("id") or 0)
                if placement is None or issued_recently(
                    map_state, f"passive_cooler_room:{room_id}", tick, retry_ticks=12000
                ):
                    continue
                patients = [patient for patient in heat_patients
                            if (int(patient["position"].get("x") or -1),
                                int(patient["position"].get("z") or -1)) in cells]
                cool_room_options[str(room_id)] = {
                    "room_id": room_id, "role": str(room.get("role_label") or "bedroom"),
                    "temperature": round(float(room.get("temperature") or 0.0)),
                    "patients": patients, "beds": len(room.get("contained_beds_ids") or []),
                    "placement": placement,
                }
            if cool_room_options:
                # During a medical emergency this action means cooling an
                # actual patient's room, not upgrading an empty bedroom.
                # Once those rooms have a cooler, other hot bedrooms can be
                # considered on later decisions.
                patient_rooms = {key: row for key, row in cool_room_options.items()
                                 if row["patients"]}
                if patient_rooms:
                    cool_room_options = patient_rooms
                elif heat_patients:
                    cool_room_options = {}
                cool_room_options = dict(sorted(
                    cool_room_options.items(),
                    key=lambda pair: (
                        -max((float(patient.get("severity") or 0.0)
                              for patient in pair[1]["patients"]), default=0.0),
                        -float(pair[1]["temperature"]),
                    ),
                ))
                if cool_room_options:
                    details["cool_room_options"] = cool_room_options
                    dev["cool_room_options"] = cool_room_options
                    one_time.append("build_passive_cooler")
    cold_patients = [
        {"name": str(pawn.get("name") or pawn.get("id")),
         "severity": round(float(condition.get("severity") or 0.0), 2),
         "downed": bool(pawn.get("downed")), "position": pawn.get("position") or {}}
        for pawn in snapshot.get("colonists") or []
        for condition in pawn.get("health_conditions") or []
        if str(condition.get("def_name") or "") == "Hypothermia"
    ]
    cold_patients.sort(key=lambda patient: (patient["severity"], patient["downed"]), reverse=True)
    if outdoor_temperature <= 5 or cold_patients:
        dev["cold_threat"] = {
            "outside_c": round(outdoor_temperature),
            "patients": cold_patients[:4],
            "warmest_roofed_c": round(max(
                (float(room.get("temperature") or 0.0) for room in dev.get("rooms") or []
                 if not room.get("touches_map_edge") and int(room.get("cells_count") or 0) <= 100),
                default=outdoor_temperature,
            )),
        }
        catalog = {str(row.get("def_name")): row for row in dev.get("building_catalog") or []
                   if isinstance(row, dict)}
        campfire_ready = (bool(catalog.get("Campfire", {}).get("available_now"))
                          and int(item_counts.get("WoodLog") or 0) >= 20)
        powered_grid_ready = (int((dev.get("power_info") or {}).get("current_power") or 0) >= 175
                              or int((dev.get("power_info") or {}).get("currently_stored_power") or 0) >= 50)
        heater_ready = (bool(catalog.get("Heater", {}).get("available_now"))
                        and powered_grid_ready
                        and int(item_counts.get("Steel") or 0) >= 50
                        and int(item_counts.get("ComponentIndustrial") or 0) >= 1
                        and any(int((pawn.get("skills") or {}).get("Construction", {}).get("level") or 0) >= 5
                                and not pawn.get("downed") and not pawn.get("in_mental_state")
                                and not ((pawn.get("work_priorities") or {}).get("Construction") or {}).get("disabled")
                                for pawn in snapshot.get("colonists") or []))
        if can_work("Construction") and (campfire_ready or heater_ready or powered_grid_ready):
            terrain = dev.get("terrain") or (
                bridge.safe_get(client, "/api/v1/map/terrain", snapshot.setdefault("warnings", []), map_id=map_id)
                if client is not None and powered_grid_ready else {})
            occupied_project_cells = {
                (int((project.get("position") or {}).get("x") or -1),
                 int((project.get("position") or {}).get("z") or -1))
                for project in dev.get("construction_projects") or []
            }
            warm_room_options: dict[str, dict[str, Any]] = {}
            heater_room_options: dict[str, dict[str, Any]] = {}
            power_connection_options: dict[str, dict[str, Any]] = {}
            for room in dev.get("rooms") or []:
                if (room.get("touches_map_edge") or room.get("is_prison_cell")
                        or not room.get("contained_beds_ids") or not room.get("light_placement_cells")
                        or float(room.get("temperature") or 0.0) >= 16
                        or int(room.get("open_roof_count") or 0) > int(room.get("cells_count") or 0) // 4):
                    continue
                defs = set(map(str, room.get("contained_thing_defs") or []))
                cells = {(int(cell.get("x") or 0), int(cell.get("z") or 0))
                         for cell in room.get("cells") or []}
                thermal_projects = [project for project in dev.get("construction_projects") or []
                                    if str(project.get("def_name") or "") in {"Campfire", "Heater"}
                                    and (int((project.get("position") or {}).get("x") or -1),
                                         int((project.get("position") or {}).get("z") or -1)) in cells]
                free_cells = [cell for cell in room.get("light_placement_cells") or []
                              if (int(cell.get("x") or 0), int(cell.get("z") or 0))
                              not in occupied_project_cells]
                placement = next(iter(free_cells), None)
                campfire_cell = campfire_safe_placement(
                    free_cells, (dev.get("buildings") or []) + (dev.get("construction_projects") or []))
                room_id = int(room.get("id") or 0)
                existing_heater = next((project.get("position") for project in thermal_projects
                                        if project.get("def_name") == "Heater"), None)
                existing_heater = existing_heater or next((building.get("position")
                    for building in dev.get("buildings") or []
                    if building.get("def") == "Heater"
                    and (int((building.get("position") or {}).get("x") or -1),
                         int((building.get("position") or {}).get("z") or -1)) in cells), None)
                if existing_heater and powered_grid_ready and terrain:
                    route = power_conduit_route(dev, existing_heater, terrain)
                    if (route and int(item_counts.get("Steel") or 0) >= len(route)
                            and not issued_recently(map_state, f"heater_power_room:{room_id}", tick, retry_ticks=12000)):
                        power_connection_options[str(room_id)] = {
                            "room_id": room_id, "role": str(room.get("role_label") or "bedroom"),
                            "temperature": round(float(room.get("temperature") or 0)),
                            "beds": len(room.get("contained_beds_ids") or []),
                            "patients": [patient for patient in cold_patients
                                         if (int((patient.get("position") or {}).get("x") or -1),
                                             int((patient.get("position") or {}).get("z") or -1)) in cells],
                            "target": existing_heater, "route": route,
                            "conduit_cost": len(route),
                        }
                if (placement is None or defs & {"Campfire", "Blueprint_Campfire", "Frame_Campfire"}
                        or any(project.get("def_name") == "Campfire" for project in thermal_projects)
                        or (not existing_heater and issued_recently(
                            map_state, f"heating_room:{room_id}", tick, retry_ticks=12000))):
                    continue
                route = (power_conduit_route(dev, placement, terrain)
                         if heater_ready and terrain and not existing_heater else None)
                can_wire_heater = (not existing_heater and route is not None and
                                   int(item_counts.get("Steel") or 0) >= 50 + len(route))
                if not campfire_ready and not can_wire_heater:
                    continue
                patients = [patient for patient in cold_patients
                            if (int(patient["position"].get("x") or -1),
                                int(patient["position"].get("z") or -1)) in cells]
                room_option = {
                    "room_id": room_id, "role": str(room.get("role_label") or "bedroom"),
                    "temperature": round(float(room.get("temperature") or 0.0)),
                    "patients": patients, "beds": len(room.get("contained_beds_ids") or []),
                    "placement": campfire_cell or placement,
                    "campfire_safe": campfire_cell is not None,
                }
                warm_room_options[str(room_id)] = room_option
                if can_wire_heater:
                    heater_room_options[str(room_id)] = {
                        **room_option, "placement": placement,
                        "route": route, "conduit_cost": len(route),
                    }
            if power_connection_options:
                details["power_connection_options"] = power_connection_options
                dev["power_connection_options"] = power_connection_options
                one_time.append("connect_room_heater_power")
            if warm_room_options:
                patient_rooms = {key: row for key, row in warm_room_options.items() if row["patients"]}
                if patient_rooms:
                    warm_room_options = patient_rooms
                    heater_room_options = {key: row for key, row in heater_room_options.items()
                                           if key in warm_room_options}
                elif cold_patients:
                    warm_room_options = {}
                    heater_room_options = {}
                warm_room_options = dict(sorted(warm_room_options.items(), key=lambda pair: (
                    -max((float(patient.get("severity") or 0.0)
                          for patient in pair[1]["patients"]), default=0.0),
                    float(pair[1]["temperature"]),
                )))
                if warm_room_options:
                    safe_campfire_rooms = {key: row for key, row in warm_room_options.items()
                                           if row["campfire_safe"]}
                    if campfire_ready and safe_campfire_rooms:
                        details["warm_room_options"] = safe_campfire_rooms
                        dev["warm_room_options"] = safe_campfire_rooms
                        one_time.append("build_room_campfire")
                    if heater_room_options:
                        details["heater_room_options"] = heater_room_options
                        dev["heater_room_options"] = heater_room_options
                        one_time.append("build_room_heater")
    material_options = structure_material_options(item_counts)
    mountain_rect = mining_bedroom_rect(dev.get("ores") or {}, anchor)
    chosen_material = str(current_doctrine.get("material") or "")
    chosen_material_available = int(item_counts.get(chosen_material) or 0) if chosen_material else 0
    income_blocked = bool(
        current_doctrine
        and str(current_doctrine.get("economy_product") or "") not in strategy.DIRECT_INCOME_PLANS
        and str(map_state.get("income_strategy") or current_doctrine.get("economy_product") or "")
            not in strategy.DIRECT_INCOME_PLANS
        and tick - int(map_state.get("doctrine_tick") or -999999) >= 90000
    )
    victory_required = bool((dev.get("user_preferences") or laya_preferences.load_preferences()).get("victory_required"))
    victory_missing = victory_required and str(current_doctrine.get("endgame") or "") == "enduring_colony"
    doctrine_due = (
        not current_doctrine
        or int(current_doctrine.get("schema_version") or 1) < 2
        or tick - int(map_state.get("doctrine_tick") or -999999) >= 3600000
        or income_blocked
        or (victory_missing and tick - int(map_state.get("doctrine_tick") or -999999) >= 30000)
        or (tick - int(map_state.get("doctrine_tick") or -999999) >= 30000
            and (strategy.DIRECTIONS.get(str(current_doctrine.get("primary_direction"))) or {}).get("domain") == "endgame"
            and strategy.course_alignment(current_doctrine) !=
                "Direction and ending are not visibly in conflict.")
        or (tick - int(map_state.get("doctrine_tick") or -999999) >= 300000
            and strategy.course_alignment(current_doctrine) !=
                "Direction and ending are not visibly in conflict.")
    )
    doctrine_starved = bool(current_doctrine and chosen_material and chosen_material_available < 125
                           and material_options
                           and tick - int(map_state.get("doctrine_tick") or -999999) >= 300000)
    if doctrine_due or doctrine_starved:
        doctrine_context = {
            "current": current_doctrine,
            "income_blocked": income_blocked,
            "victory_required": victory_required,
            "course_alignment": strategy.course_alignment(current_doctrine),
            "material_options": material_options,
            "mountain_possible": mountain_rect is not None,
            "tile": dev.get("tile_details") or {},
            "weather": weather,
            "boom_animals_nearby": sum(1 for a in snapshot.get("wild_animals", []) if "boom" in str(a.get("def") or "").lower()),
            "ores": {name: len((group or {}).get("cells") or []) for name, group in (dev.get("ores", {}).get("ores") or {}).items()},
            "profession_directions": profession_context.get("directions") or {},
            "profession_choices": professions.direction_choice_descriptions(profession_context),
            "item_counts": item_counts,
            "building_counts": counts,
            "work_tables": dev.get("work_tables") or [],
            "zones": zones,
            "trade_destinations": dev.get("trade_destinations") or [],
            "trade_opportunities": dev.get("trade_opportunities") or [],
            "trade_ledger": map_state.get("trade_ledger") or [],
            "recent_course_changes": (map_state.get("doctrine_history") or [])[-3:],
            "population": len(snapshot.get("colonists") or []),
            "resources": snapshot.get("map", {}).get("resources") or {},
            "building_catalog": dev.get("building_catalog") or [],
            "research_tree": dev.get("research_tree") or [],
            "active_mods": dev.get("active_mods") or [],
            "ideology": dev.get("ideology") or {},
            "royalty": dev.get("royalty") or {},
        }
        doctrine_context["direction_audit"] = strategy.audit_directions(doctrine_context)
        details["doctrine_context"] = doctrine_context
        dev["doctrine_context"] = details["doctrine_context"]
        one_time.append("choose_colony_doctrine")

    doctrine_form = str(current_doctrine.get("settlement_form") or "")
    private_rooms = [
        room for room in dev.get("rooms", [])
        if "bedroom" in str(room.get("role_label") or "").lower() and not room.get("is_prison_cell")
    ]
    housing_shortage = len(private_rooms) < len(snapshot["colonists"])
    if current_doctrine and housing_shortage:
        if doctrine_form == "mountain" and mountain_rect is not None and not map_state.get("mountain_bedroom"):
            details["mountain_bedroom_rect"] = mountain_rect
            one_time.append("excavate_mountain_bedroom")
        elif doctrine_form == "mountain" and map_state.get("mountain_bedroom"):
            plan = map_state["mountain_bedroom"]
            natural = mineable_natural_rock_cells(dev.get("ores") or {})
            x, z = int(plan["x"]), int(plan["z"])
            interior = {(x + dx, z + dz) for dx in range(1, 6) for dz in range(1, 6)} | {(x + 3, z)}
            if not (interior & natural) and not plan.get("furnished"):
                one_time.append("finish_mountain_bedroom")
        # Surface settlements are handled by the procedural architecture
        # planner below. Mountain bedrooms retain their separate mining phase.

    upgrade_options = architect.workbench_upgrade_options(dev)
    if upgrade_options and not issued_recently(map_state, "workbench_upgrade", tick, retry_ticks=120000):
        details["workbench_upgrade_options"] = upgrade_options
        dev["workbench_upgrade_options"] = upgrade_options
        one_time.append("upgrade_workbench")

    dark_room_options: dict[str, dict[str, Any]] = {}
    for room in dev.get("rooms", []):
        if (room.get("touches_map_edge") or room_is_ancient_danger(room)
                or not room.get("light_placement_cells")):
            continue
        role = str(room.get("role_label") or "room")
        defs = set(map(str, room.get("contained_thing_defs") or []))
        high_value = any(token in role.lower() for token in ("hospital", "kitchen", "workshop", "laboratory", "dining", "bedroom"))
        high_value = high_value or bool(defs & {"HospitalBed", "Bed", "FueledStove", "ElectricStove", "SimpleResearchBench", "HiTechResearchBench"})
        if high_value and float(room.get("dark_cells_percent") or 0.0) >= 40.0:
            dark_room_options[str(room.get("id"))] = {
                "room_id": int(room.get("id") or 0),
                "role": role,
                "average_glow": round(float(room.get("average_glow") or 0.0), 2),
                "dark_percent": round(float(room.get("dark_cells_percent") or 0.0), 1),
                "temperature": round(float(room.get("temperature") or 0.0), 1),
                "placement_cells": room.get("light_placement_cells") or [],
            }
    if dark_room_options and not issued_recently(map_state, "room_lighting", tick, retry_ticks=60000):
        details["dark_room_options"] = dark_room_options
        dev["dark_room_options"] = dark_room_options
        one_time.append("improve_room_lighting")

    architecture_material = chosen_material if chosen_material in material_options else next(iter(material_options), "")
    architecture_context = {
        "building_counts": counts,
        "buildings": dev.get("buildings") or [],
        "rooms": dev.get("rooms") or [],
        "colonists": snapshot.get("colonists") or [],
        "animals": colony_animals,
        "royalty": dev.get("royalty") or {},
        "ideology": dev.get("ideology") or {},
        "storage": dev.get("storage") or {},
        "professions": profession_context,
        "doctrine": current_doctrine,
        "finished_research": list(finished),
        "building_catalog": dev.get("building_catalog") or [],
        "item_counts": item_counts,
        "material": architecture_material,
        "material_options": material_options,
        "powered": finished_electricity,
        "climate": climate_mode,
        "wealth": snapshot.get("game", {}).get("wealth") or 0,
        "animal_count": len(colony_animals),
        "potential_patients": [
            {
                "name": pawn.get("name"), "health": pawn.get("health"), "downed": pawn.get("downed"),
                "conditions": [condition.get("label") or condition.get("def_name") for condition in pawn.get("health_conditions", [])],
            }
            for pawn in snapshot.get("colonists", [])
            if pawn.get("downed") or bridge.first_number(pawn.get("health"), 1.0) < 0.9 or pawn.get("health_conditions")
        ],
        "variant_seed": int(snapshot.get("map", {}).get("id") or 0) * 1000003 + tick // 60000,
        "altar_defs": [str(row.get("def_name")) for row in (dev.get("ideology") or {}).get("ritual_buildings", []) if row.get("def_name")],
        "bench_defs": [str(row.get("def_name")) for row in dev.get("building_catalog", []) if row.get("is_work_table") and row.get("available_now")],
    }
    architecture_programs = {
        program: description for program, description in architect.program_options(architecture_context).items()
        if architect.affordable_material_options(program, architecture_context, material_options,
                                                  seed=int(architecture_context["variant_seed"]))
    } if architecture_material else {}
    pending_projects = dev.get("construction_projects") or []
    full_catalog_options = architect.catalog_construction_options(dev)
    dev["catalog_access_audit"] = architect.catalog_access_audit(dev, full_catalog_options)
    people_count = len(snapshot.get("colonists") or [])
    sheltered_beds = sheltered_real_bed_count(dev, anchor) or 0
    prison_exists = bool(ready_prison_beds(dev, prison_site_for_state(map_state, anchor)))
    essential_rooms_ready = people_count > 0 and sheltered_beds >= people_count
    ritual_allowed = essential_rooms_ready and people_count >= 3 and prison_exists
    ritual_defs = {str(row.get("def_name")) for row in (dev.get("ideology") or {}).get("ritual_buildings") or []
                   if row.get("def_name")}
    catalog_options = {
        category: {name: plan for name, plan in plans.items()
                   if (name not in ritual_defs or ritual_allowed)
                   and not (name in ritual_defs and (int(counts.get(name) or 0) > 0
                           or any(row.get("def_name") == name for row in pending_projects)))}
        for category, plans in full_catalog_options.items()
    }
    catalog_options = {category: plans for category, plans in catalog_options.items() if plans}
    pending_research_bench = any("ResearchBench" in str(row.get("def_name") or "")
                                 for row in pending_projects)
    research_bench_options = {
        name: plan for category in catalog_options.values() for name, plan in category.items()
        if name in {"SimpleResearchBench", "HiTechResearchBench"}
    }
    if (not has_research_bench and not pending_research_bench and research_bench_options
            and can_work("Construction")
            and not issued_recently(map_state, "research_bench", tick, retry_ticks=15000)):
        details["research_bench_options"] = research_bench_options
        dev["research_bench_options"] = research_bench_options
        one_time.append("build_research_bench")
    if (catalog_options and essential_rooms_ready and (people_count >= 3 or prison_exists)
            and can_work("Construction")
            and len(pending_projects) < max(6, len(snapshot.get("colonists") or []) * 4)
            and not issued_recently(map_state, "catalog_building", tick, retry_ticks=60000)):
        details["catalog_building_options"] = catalog_options
        dev["catalog_building_options"] = catalog_options
        one_time.append("build_catalog_building")
    if (
        architecture_programs and not pending_projects
        and not issued_recently(map_state, "architecture_project", tick, retry_ticks=90000)
        and not issued_recently(map_state, "architecture_site_search", tick, retry_ticks=60000)
    ):
        details["architecture_context"] = architecture_context
        details["architecture_program_options"] = architecture_programs
        dev["architecture_context"] = architecture_context
        dev["architecture_program_options"] = architecture_programs
        one_time.append("plan_architecture")

    sculptures = [row for row in dev.get("things", []) if installable_sculpture(row)]
    valued_rooms = [
        room for room in dev.get("rooms", [])
        if not room.get("touches_map_edge") and room.get("cells")
        and any(token in str(room.get("role_label") or "").lower() for token in ("dining", "rec", "bedroom", "hospital", "workshop"))
        and float(room.get("impressiveness") or 0.0) < 120
    ]
    if sculptures and valued_rooms and not issued_recently(map_state, "install_sculpture", tick, retry_ticks=30000):
        install_options: dict[str, dict[str, Any]] = {}
        for sculpture in sculptures[:8]:
            for room in sorted(valued_rooms, key=lambda r: float(r.get("impressiveness") or 0.0))[:6]:
                key = f"{int(sculpture['thing_id'])}|{int(room['id'])}"
                install_options[key] = {
                    "thing_id": int(sculpture["thing_id"]),
                    "sculpture": sculpture.get("label"),
                    "beauty": sculpture.get("beauty", 0),
                    "quality": sculpture.get("inner_quality", -1),
                    "room_id": int(room["id"]),
                    "room_role": room.get("role_label"),
                    "impressiveness": round(float(room.get("impressiveness") or 0.0), 1),
                    "cells": room.get("cells") or [],
                }
        if install_options:
            details["sculpture_install_options"] = install_options
            dev["sculpture_install_options"] = install_options
            one_time.append("install_sculpture")
    elif not sculptures and not issued_recently(map_state, "commission_sculptures", tick, retry_ticks=120000):
        best_artist = max((int((c.get("skills", {}).get("Artistic") or {}).get("level") or 0) for c in snapshot["colonists"]), default=0)
        if best_artist >= 3 and (int(item_counts.get("WoodLog") or 0) >= 200 or any(name.startswith("Blocks") and int(value or 0) >= 100 for name, value in item_counts.items())):
            one_time.append("commission_sculptures")

    shelf_area = {
        "min_x": int(anchor["x"]) - 8, "max_x": int(anchor["x"]) - 7,
        "min_z": int(anchor["z"]) + 9, "max_z": int(anchor["z"]) + 13,
    }
    weapon_shelves = [
        b for b in dev.get("buildings", []) if str(b.get("def")) in {"Shelf", "ShelfSmall"}
        and shelf_area["min_x"] <= int((b.get("position") or {}).get("x") or -999) <= shelf_area["max_x"]
        and shelf_area["min_z"] <= int((b.get("position") or {}).get("z") or -999) <= shelf_area["max_z"]
    ]
    if int(snapshot["map"]["resources"].get("weapons") or 0) > 0 and "ComplexFurniture" in finished:
        if len(weapon_shelves) < 3 and not issued_recently(map_state, "weapon_shelves", tick, retry_ticks=90000):
            one_time.append("build_weapon_shelves")
        elif weapon_shelves and not map_state.get("weapon_shelves_configured"):
            details["weapon_shelf_ids"] = [int(b["id"]) for b in weapon_shelves]
            one_time.append("build_weapon_shelves")

    military_focus = str(current_doctrine.get("military") or "balanced")
    armament_focus = {
        "ranged_firepower": "weapons", "turret_mortar": "weapons",
        "melee_chokepoints": "armor", "fortified_depth": "balanced",
        "mobile_response": "balanced", "peaceful_deterrence": "balanced",
        "psychic_force": "balanced", "mechanized_force": "balanced",
        "anomaly_weapons": "weapons", "gravship_security": "balanced",
    }.get(military_focus, military_focus)
    can_equip_fighters = bool(unarmed_fighters and free_weapons)
    can_start_armament_research = has_research_bench and current.lower() == "none"
    if current_doctrine and (can_equip_fighters or can_start_armament_research) and not issued_recently(map_state, "armament", tick, retry_ticks=60000):
        underarmed = sum(1 for p in snapshot.get("combat", {}).get("colonists", []) if not p.get("has_ranged_weapon"))
        if underarmed or armament_focus in {"weapons", "armor", "balanced"}:
            details["armament_context"] = {
                "focus": armament_focus,
                "doctrine": military_focus,
                "unarmed_colonists": underarmed,
                "loose_weapons": snapshot.get("combat", {}).get("available_weapons", [])[:12],
                "steel": item_counts.get("Steel", 0),
                "components": item_counts.get("ComponentIndustrial", 0),
            }
            one_time.append("prioritize_armament")

    if colony_animals and current_doctrine and "animal_barn" not in map_state.setdefault("issued", {}) and material_options:
        min_comfort = min((float(a.get("min_comfortable_temperature") or -10) for a in colony_animals), default=-10)
        max_comfort = max((float(a.get("max_comfortable_temperature") or 40) for a in colony_animals), default=40)
        climate_risk = outdoor_temperature < min_comfort + 5 or outdoor_temperature > max_comfort - 5
        hay = int(item_counts.get("Hay") or item_counts.get("HayGrass") or 0)
        details["animal_barn_options"] = {
            "material_options": material_options,
            "straw_available": hay >= 100,
            "hay": hay,
            "climate_risk": climate_risk,
            "climate": climate_mode,
            "animal_count": len(colony_animals),
            "comfort_range": [min_comfort, max_comfort],
        }
        dev["animal_barn_options"] = details["animal_barn_options"]
        if climate_risk or len(colony_animals) >= 2:
            one_time.append("build_animal_barn")

    growing_zones = [z for z in zones if "Growing" in str(z.get("type"))]
    crop_days = [float(c.get("days_until_harvest") or 0.0) for c in (dev.get("farm") or {}).get("crop_types", []) if int(c.get("total_plants") or 0) > 0]
    future_temperatures = [float(v) for v in weather.get("next_twelfth_average_temperatures") or []]
    late_season = (not bool(weather.get("growth_season_now"))) or (future_temperatures and min(future_temperatures) < 6 and max(crop_days or [0]) > 5)
    if growing_zones and late_season and any(z.get("allow_sow") is not False for z in growing_zones):
        details["sowing_zone_ids"] = [int(z["id"]) for z in growing_zones if z.get("allow_sow") is not False]
        one_time.append("pause_late_sowing")
    elif growing_zones and bool(weather.get("growth_season_now")) and (not future_temperatures or min(future_temperatures[:2]) >= 6) and any(z.get("allow_sow") is False for z in growing_zones):
        details["sowing_zone_ids"] = [int(z["id"]) for z in growing_zones if z.get("allow_sow") is False]
        one_time.append("resume_seasonal_sowing")
    capture_needs_room = bool((snapshot.get("combat") or {}).get("prisoners")) or any(
        hostile.get("is_downed") and not hostile.get("is_dead")
        for hostile in (snapshot.get("combat") or {}).get("hostiles") or []
    )
    prison_site = prison_site_for_state(map_state, anchor)
    prison_ready = ready_prison_beds(dev, prison_site)
    prison_pending = any(
        str(project.get("def_name") or "") in {"Wall", "Door", "SleepingSpot", "Bed"}
        and prison_site["x"] <= int((project.get("position") or {}).get("x") or -999) <= prison_site["x"] + 6
        and prison_site["z"] <= int((project.get("position") or {}).get("z") or -999) <= prison_site["z"] + 6
        for project in dev.get("construction_projects") or []
    )
    safe_to_prepare_growth = (
        1 <= len(snapshot["colonists"]) <= 4
        and sheltered_real_bed_count(dev, anchor) is not None
        and (sheltered_real_bed_count(dev, anchor) or 0) >= len(snapshot["colonists"])
        and (int(resources.get("meals") or 0) >= len(snapshot["colonists"]) * 6
             or (int(resources.get("meals") or 0) >= len(snapshot["colonists"]) * 4
                 and int(resources.get("food") or 0) >= len(snapshot["colonists"]) * 12))
        and not (snapshot.get("map") or {}).get("enemies")
    )
    prison_stuff = prison_material(item_counts)
    if ((capture_needs_room or safe_to_prepare_growth) and not prison_ready and not prison_pending
            and can_work("Construction") and prison_stuff
            and not issued_recently(map_state, "prison_blueprint", tick, retry_ticks=90000)):
        dev["population_growth_context"] = {
            "population": len(snapshot["colonists"]), "ready_meals": int(resources.get("meals") or 0),
            "roofed_real_beds": sheltered_real_bed_count(dev, anchor) or 0,
            "prison_ready": False, "material": prison_stuff, "material_cost": 140,
        }
        one_time.append("build_prison")
    hospital_a = {"x": int(anchor["x"]) + 25, "z": int(anchor["z"])}
    hospital_b = {"x": hospital_a["x"] + 6, "z": hospital_a["z"] + 6}
    hospital_rects = [(hospital_a, hospital_b)]
    for project in map_state.get("architecture_projects", []):
        if project.get("program") != "hospital":
            continue
        origin = project.get("origin") or {}
        start = {"x": int(origin.get("x") or 0), "z": int(origin.get("z") or 0)}
        end = {
            "x": start["x"] + int(project.get("width") or 1) - 1,
            "z": start["z"] + int(project.get("height") or 1) - 1,
        }
        hospital_rects.append((start, end))
    hospital_beds = [
        b for b in dev.get("buildings", [])
        if any(
            start["x"] <= int((b.get("position") or {}).get("x") or -999) <= end["x"]
            and start["z"] <= int((b.get("position") or {}).get("z") or -999) <= end["z"]
            for start, end in hospital_rects
        )
        and str(b.get("def") or "") in {"Bed", "HospitalBed", "SleepingSpot"}
    ]
    has_generated_hospital = any(row.get("program") == "hospital" for row in map_state.get("architecture_projects", []))
    if not has_generated_hospital and int(item_counts.get("WoodLog") or 0) >= 180 and "hospital_blueprint" not in map_state.setdefault("issued", {}):
        one_time.append("build_hospital")
    elif hospital_beds and not all(bool(b.get("medical")) for b in hospital_beds) and not issued_recently(map_state, "hospital_beds", tick, retry_ticks=15000):
        one_time.append("configure_hospital_beds")

    medical_bed_ids = {int(b["id"]) for b in dev.get("buildings", []) if b.get("medical") and b.get("id") is not None}
    critical_floor_options: dict[str, dict[str, Any]] = {}
    floor_terrain = dev.get("terrain")
    planned_floor_cells = floor_project_cells(dev.get("construction_projects") or [])
    for room in dev.get("rooms", []):
        if f"floor_room:{int(room.get('id') or 0)}" in map_state.setdefault("issued", {}):
            continue
        cells = room.get("cells") or []
        if not cells or room.get("touches_map_edge") or int(room.get("cells_count") or 0) > 100:
            continue
        defs = set(map(str, room.get("contained_thing_defs") or []))
        role = str(room.get("role_label") or "").lower()
        is_kitchen = bool(defs & {"FueledStove", "ElectricStove", "Campfire"})
        is_hospital = role == "hospital" or bool(medical_bed_ids & set(map(int, room.get("contained_beds_ids") or [])))
        is_barracks = bool(room.get("contained_beds_ids")) and not is_hospital
        if not (is_kitchen or is_hospital or is_barracks):
            continue
        if not floor_terrain and client is not None:
            floor_terrain = bridge.safe_get(
                client, "/api/v1/map/terrain", snapshot.setdefault("warnings", []), map_id=map_id)
        if not floor_terrain:
            continue
        actual_floors = terrain_defs_at_cells(floor_terrain, cells)
        bare_cells = [cell for cell in cells
                      if needs_first_floor(actual_floors.get((int(cell["x"]), int(cell["z"]))))
                      and (int(cell["x"]), int(cell["z"])) not in planned_floor_cells]
        if not bare_cells:
            continue
        material_options = affordable_floor_options(
            item_counts, finished, len(bare_cells), best_builder,
            wood_reserve=50 if is_barracks else 180,
        )
        for floor_def, cost in material_options.items():
            key = f"{int(room['id'])}|{floor_def}"
            critical_floor_options[key] = {
                "room_id": int(room["id"]),
                "room_kind": "hospital" if is_hospital else "kitchen" if is_kitchen else "shared bedroom",
                "cleanliness": round(float(room.get("cleanliness") or 0.0), 2),
                "cells": bare_cells,
                "floor_def": floor_def,
                "cost": cost,
            }
    if critical_floor_options and not issued_recently(map_state, "critical_floor", tick, retry_ticks=120000):
        details["critical_floor_options"] = critical_floor_options
        dev["critical_floor_options"] = critical_floor_options
        one_time.append("floor_critical_room")
    path_options = affordable_floor_options(item_counts, finished, 60, best_builder, pathway=True)
    if path_options and "pathways" not in map_state.setdefault("issued", {}):
        details["path_floor_options"] = path_options
        dev["path_floor_options"] = path_options
        one_time.append("build_pathways")

    nearby_stones: Counter[str] = Counter()
    for row in dev.get("things", []):
        name = str(row.get("def_name") or "")
        if not name.startswith("Chunk") or name in {"ChunkSlagSteel", "ChunkMechanoidSlag"}:
            continue
        pos = row.get("position") or {}
        if (int(pos.get("x") or 0) - int(anchor["x"])) ** 2 + (int(pos.get("z") or 0) - int(anchor["z"])) ** 2 <= 60 ** 2:
            nearby_stones[name] += 1
    has_stonecutter = any(str(table.get("thing_def") or "") == "TableStonecutter" for table in dev.get("work_tables", []))
    stone_dump_exists = any("Laya Stone Chunks" in str(z.get("label") or "") for z in zones)
    if has_stonecutter and nearby_stones and not stone_dump_exists and "stone_chunk_dump" not in map_state.setdefault("issued", {}):
        stonecutter = next(
            (row for row in dev.get("work_tables", []) if str(row.get("thing_def") or "") == "TableStonecutter"),
            {},
        )
        details["stone_dump_anchor"] = stonecutter.get("position") or anchor
        one_time.append("create_stone_chunk_dump")
    stonecutting_needed = (
        ("Stonecutting" not in finished and current.lower() == "none")
        or ("Stonecutting" in finished and not has_stonecutter and not issued_recently(map_state, "stonecutting_table", tick, retry_ticks=60000))
        or (has_stonecutter and "stonecutting_complete" not in map_state.setdefault("issued", {}))
    )
    if nearby_stones and stonecutting_needed:
        details["stone_options"] = dict(nearby_stones)
        dev["stone_options"] = dict(nearby_stones)
        one_time.append("start_stonecutting")
    handler_rows = sorted(
        snapshot["colonists"],
        key=lambda c: int((c.get("skills", {}).get("Animals") or {}).get("level") or 0),
        reverse=True,
    )
    best_handler_row = handler_rows[0] if handler_rows else {}
    best_handler = int((best_handler_row.get("skills", {}).get("Animals") or {}).get("level") or 0)
    inspired_taming = "taming" in str(best_handler_row.get("inspiration") or "").lower()
    owned_unpenned = [animal for animal in snapshot.get("animals", [])
                      if animal.get("requires_pen") is True and not animal.get("has_suitable_enclosed_pen")]
    potential_livestock = [animal for animal in snapshot.get("wild_animals", [])
                           if animal.get("requires_pen") is True and not animal.get("has_suitable_enclosed_pen")
                           and animal.get("can_tame") is True
                           and int(animal.get("minimum_handling_skill") or 0) <= best_handler
                           and squared_distance(animal.get("position") or {}, anchor) <= 60 ** 2]
    unpenned_animals = owned_unpenned + potential_livestock
    pen_marker_present = any(str(row.get("def") or row.get("def_name") or "") == "PenMarker"
                             for row in (dev.get("buildings") or []) + (dev.get("construction_projects") or []))
    pen_materials = {material: f"{count} available; closed 9x9 pen costs about 85"
                     for material, count in (item_counts or {}).items()
                     if (material in {"WoodLog", "Steel"} or material.startswith("Blocks")) and int(count or 0) >= 85}
    if (unpenned_animals and pen_materials and not pen_marker_present
            and not issued_recently(map_state, "animal_pen", tick, retry_ticks=60000)
            and not issued_recently(map_state, "animal_pen_site_search", tick, retry_ticks=60000)):
        pen_sizes = {"9": "9×9 starter pen, about 85 material; faster to finish"}
        if all(int(item_counts[material] or 0) >= 101 for material in pen_materials):
            pen_sizes["13"] = "13×13 grazing pen, about 101 material; more pasture space"
        details["animal_pen_options"] = {
            "materials": pen_materials,
            "sizes": pen_sizes,
            "waiting_animals": [f"{animal.get('def')} {animal.get('gender')}" for animal in owned_unpenned[:8]],
            "optional_wildlife": [f"{animal.get('def')} {animal.get('gender')}" for animal in potential_livestock[:8]],
        }
        dev["animal_pen_options"] = details["animal_pen_options"]
        one_time.append("build_animal_pen")
    tame_options = []
    for animal in snapshot.get("wild_animals", []):
        pos = animal.get("position") or {}
        close = (int(pos.get("x") or 0) - int(anchor["x"])) ** 2 + (int(pos.get("z") or 0) - int(anchor["z"])) ** 2 <= 60 ** 2
        if (animal.get("can_tame") and close
                and (animal.get("requires_pen") is False or animal.get("has_suitable_enclosed_pen"))
                and f"tame:{animal.get('id')}" not in map_state.setdefault("issued", {})
                and int(animal.get("minimum_handling_skill") or 0) <= best_handler):
            tame_options.append(animal)
    wildlife_paused = issued_recently(map_state, "wildlife_pause", tick, retry_ticks=15000)
    if (tame_options and not wildlife_paused
            and (len(snapshot.get("colonists") or []) >= 2
                 or not dev.get("construction_projects"))):
        details["tame_options"] = tame_options
        details["handler_context"] = {"name": best_handler_row.get("name"), "skill": best_handler, "inspiration": best_handler_row.get("inspiration")}
        dev["tame_options"] = tame_options
        dev["handler_context"] = details["handler_context"]
        one_time.append("start_taming")
    wild_human_options = []
    if best_handler >= 7:
        for person in snapshot.get("wild_humans") or []:
            pos = person.get("position") or {}
            close = (int(pos.get("x") or 0) - int(anchor["x"])) ** 2 + (int(pos.get("z") or 0) - int(anchor["z"])) ** 2 <= 60 ** 2
            if (close and not person.get("downed") and float(person.get("health") or 0) > 0.4
                    and not issued_recently(map_state, f"wild_human_tame:{person.get('id')}", tick, retry_ticks=30000)):
                wild_human_options.append(person)
    if wild_human_options and not wildlife_paused:
        details["wild_human_options"] = wild_human_options
        dev["wild_human_options"] = wild_human_options
        one_time.append("tame_wild_human")
    combat_rows = snapshot.get("combat", {}).get("colonists", [])
    colony_recovering = any(
        pawn.get("downed") or bridge.first_number(pawn.get("health"), 1.0) < 0.8
        or bridge.first_number(pawn.get("bleeding_rate")) > 0.05
        for pawn in snapshot["colonists"]
    )
    emergency_hunt_needed = int(resources.get("food") or 0) < max(8, len(snapshot["colonists"]) * 4)
    healthy_armed = [
        row for row in combat_rows
        if row.get("has_ranged_weapon") and not row.get("is_downed") and float(row.get("health") or 0.0) >= 0.8
    ]
    average_shooting = sum(int(row.get("shooting_skill") or 0) for row in healthy_armed) / max(1, len(healthy_armed))
    serious_ranged = [
        row for row in healthy_armed
        if any(token in str(row.get("weapon_def") or "").lower() for token in (
            "rifle", "smg", "lmg", "minigun", "charge", "sniper", "needle", "launcher",
        ))
    ]
    hunt_options = []
    risky_hunt_options = []
    for animal in snapshot.get("wild_animals", []):
        pos = animal.get("position") or {}
        close = (int(pos.get("x") or 0) - int(anchor["x"])) ** 2 + (int(pos.get("z") or 0) - int(anchor["z"])) ** 2 <= 60 ** 2
        if not close or f"hunt:{animal.get('id')}" in map_state.setdefault("issued", {}):
            continue
        safe_small_game = (
            not animal.get("predator")
            and "boom" not in str(animal.get("def") or "").lower()
            and float(animal.get("harm_revenge_chance") or 0.0) <= 0.05
            and float(animal.get("combat_power") or 0.0) <= 100
        )
        if safe_small_game and healthy_armed and (not colony_recovering or emergency_hunt_needed):
            hunt_options.append(animal)
        elif not safe_small_game and healthy_armed and not colony_recovering:
            risky_hunt_options.append(animal)
    hunt_options.sort(key=lambda a: (
        "thrumbo" in str(a.get("def") or "").lower(),
        int(a.get("meat_amount") or 0) + int(a.get("leather_amount") or 0),
        float(a.get("market_value") or 0.0),
    ), reverse=True)
    if hunt_options and not wildlife_paused:
        details["hunt_options"] = hunt_options
        dev["hunt_options"] = hunt_options
    if risky_hunt_options and not wildlife_paused and not issued_recently(
        map_state, "dangerous_hunt_review", tick, retry_ticks=30000
    ):
        details["risky_hunt_options"] = risky_hunt_options
        dev["risky_hunt_options"] = risky_hunt_options
        one_time.append("consider_dangerous_hunt")
    if details.get("hunt_options") or details.get("risky_hunt_options"):
        details["fighter_context"] = {
            "healthy_ranged": len(healthy_armed),
            "serious_ranged_weapons": len(serious_ranged),
            "average_shooting": round(average_shooting, 1),
            "injured_colonists": sum(bridge.first_number(c.get("health"), 1) < 0.8 for c in snapshot["colonists"]),
            "food": int(resources.get("food") or 0),
        }
        dev["fighter_context"] = details["fighter_context"]
    if not wildlife_paused and (details.get("tame_options") or details.get("hunt_options") or details.get("risky_hunt_options")):
        one_time.append("leave_wildlife_alone")
    colony_animals = [a for a in snapshot.get("animals", []) if a.get("reproductive") and not a.get("pregnant")]
    breed_species = sorted({
        str(a.get("def")) for a in colony_animals
        if a.get("gender") == "Male" and any(b.get("def") == a.get("def") and b.get("gender") == "Female" for b in colony_animals)
    })
    for species in breed_species:
        if not issued_recently(map_state, f"breed:{species}", tick, retry_ticks=60000):
            one_time.append(f"breed_animals:{species}")
    colonists_by_id = {int(c["id"]): c for c in snapshot["colonists"]}
    couples: set[tuple[int, int]] = set()
    for colonist in snapshot["colonists"]:
        for relation in colonist.get("relations", []):
            if str(relation.get("relation_def_name")) not in {"Spouse", "Lover", "Fiance"}:
                continue
            digits = "".join(ch for ch in str(relation.get("other_pawn_id") or "") if ch.isdigit())
            if not digits or int(digits) not in colonists_by_id:
                continue
            pair = tuple(sorted((int(colonist["id"]), int(digits))))
            if pair[0] != pair[1]:
                couples.add(pair)
    for first_id, second_id in sorted(couples):
        if issued_recently(map_state, f"human_reproduction:{first_id}:{second_id}", tick, retry_ticks=3600000):
            continue
        if len(snapshot["colonists"]) >= 2:
            one_time.extend([
                f"human_reproduction:{first_id}:{second_id}:TryForBaby",
                f"human_reproduction:{first_id}:{second_id}:Normal",
                f"human_reproduction:{first_id}:{second_id}:AvoidPregnancy",
            ])
    prisoner_plans = map_state.setdefault("prisoner_plans", {})
    best_doctor = max((int((c.get("skills", {}).get("Medicine") or {}).get("level") or 0) for c in snapshot["colonists"]), default=0)
    organ_context = {
        "doctor_skill": best_doctor,
        "medicine": int(snapshot["map"]["resources"].get("medicine") or 0),
        "colonist_traits": {
            str(c.get("name")): [str(t.get("label") or t.get("name")) for t in c.get("traits", [])]
            for c in snapshot["colonists"]
        },
        "ideology_precepts": (dev.get("ideology") or {}).get("precepts", []),
    }
    for prisoner in snapshot.get("combat", {}).get("prisoners", []):
        pawn_id = str(prisoner.get("id"))
        if pawn_id in prisoner_plans:
            continue
        if prisoner.get("recruitable", True):
            one_time.append(f"prisoner_policy:{pawn_id}:recruit")
        if prisoner.get("faction_can_give_goodwill") and not prisoner.get("faction_permanent_enemy"):
            one_time.append(f"prisoner_policy:{pawn_id}:release")
        one_time.append(f"prisoner_policy:{pawn_id}:sell")
        if best_doctor >= 8 and int(snapshot["map"]["resources"].get("medicine") or 0) >= 2:
            one_time.append(f"prisoner_policy:{pawn_id}:organs_nonlethal")
            one_time.append(f"prisoner_policy:{pawn_id}:organs_lethal")
            details["organ_context"] = organ_context
            dev["organ_context"] = organ_context
    # Laya chooses a profit specialization only after immediate food and medical
    # needs are stable. The choice controls later infrastructure and research,
    # but is deliberately revisited after one in-game year rather than permanent.
    strategy_tick = int(map_state.get("income_strategy_tick") or -999999)
    if not current_doctrine and (not map_state.get("income_strategy") or tick - strategy_tick >= 3600000):
        one_time.extend([
            "income_drugs",
            "income_tailoring",
            "income_art",
            "income_livestock",
            "income_biofuel",
            "income_mining",
            "income_crops",
            "income_brewing",
            "income_travel_food",
            "income_orbital",
            "income_organs",
        ])
    income_strategy = str(map_state.get("income_strategy") or "")
    if (current_doctrine and income_strategy in strategy.DIRECT_INCOME_PLANS
            and map_state.get("income_plan_started") != income_strategy):
        # A saved money-making policy needs a real first order, not just a GUI
        # label. Laya still chooses when to start it among live priorities.
        one_time.append(f"income_{income_strategy}")
    strategy_tables = {
        "drugs": {"DrugLab"},
        "tailoring": {"HandTailoringBench", "ElectricTailoringBench"},
        "art": {"TableSculpting"},
        "biofuel": {"BiofuelRefinery"},
        "brewing": {"Brewery"},
        "travel_food": {"FueledStove", "ElectricStove"},
    }
    strategy_research = {
        "drugs": "DrugProduction",
        "biofuel": "BiofuelRefining",
        "brewing": "Brewing",
        "orbital": "MicroelectronicsBasics",
    }
    required_research = strategy_research.get(income_strategy)
    if (
        income_strategy in {"drugs", "biofuel", "brewing", "orbital"}
        and (required_research is None or required_research in finished)
        and not issued_recently(map_state, f"income_infrastructure:{income_strategy}", tick, retry_ticks=60000)
    ):
        present = any(
            str(table.get("thing_def") or "") in strategy_tables.get(income_strategy, set())
            for table in dev.get("work_tables", [])
        )
        if income_strategy == "orbital":
            present = counts.get("CommsConsole", 0) > 0 and counts.get("OrbitalTradeBeacon", 0) > 0
        if not present:
            one_time.append("build_income_infrastructure")
    if income_strategy in strategy_tables and any(
        str(table.get("thing_def") or "") in strategy_tables[income_strategy] for table in dev.get("work_tables", [])
    ) and (income_strategy != "travel_food" or {"Pemmican", "PackagedSurvivalMeal"} & finished
    ) and not issued_recently(map_state, f"income_bills:{income_strategy}", tick, retry_ticks=30000):
        one_time.append("configure_income_production")
    travel_rations = int(item_counts.get("Pemmican") or 0) + int(item_counts.get("MealSurvivalPack") or 0)
    if (income_strategy in strategy.DIRECT_INCOME_PLANS
            and dev.get("trade_destinations") and not dev.get("trade_opportunities")
            and travel_rations < max(26, len(snapshot["colonists"]) * 5 + 16)):
        current_project = str((dev.get("current_research") or {}).get("name") or "none").lower()
        if "Pemmican" in finished:
            has_campfire = any(str(table.get("thing_def") or "") in {"Campfire", "FueledStove", "ElectricStove"}
                               for table in dev.get("work_tables") or [])
            if has_campfire and not issued_recently(map_state, "trade_rations_bill", tick, retry_ticks=60000):
                one_time.append("prepare_trade_rations")
        elif current_project == "none" and has_research_bench and any(
                row.get("name") == "Pemmican" and row.get("can_start_now")
                for row in dev.get("research_tree") or []):
            if not issued_recently(map_state, "trade_rations_research", tick, retry_ticks=30000):
                one_time.append("prepare_trade_rations")

    ideology = dev.get("ideology") or {}
    ritual_buildings = ideology.get("ritual_buildings") or []
    if ideology.get("active") and ritual_buildings and "temple" not in map_state.setdefault("issued", {}):
        altar_options = {
            str(row.get("def_name")): (
                f"{row.get('label')} / {row.get('precept_name')}; size {row.get('size_x')}x{row.get('size_z')}; "
                f"stuff cost {row.get('cost_stuff_count')}"
            )
            for row in ritual_buildings if row.get("def_name") and counts.get(str(row.get("def_name")), 0) == 0
        }
        temple_materials = {
            name: note for name, note in structure_material_options(item_counts, minimum_units=500).items()
            if name == "WoodLog" or (name.startswith("Blocks") and "Stonecutting" in finished)
        }
        if ritual_allowed and altar_options and temple_materials:
            details["temple_options"] = {"altars": altar_options, "materials": temple_materials, "ideology": ideology.get("name")}
            dev["temple_options"] = details["temple_options"]
            one_time.append("build_temple")

    failed_projects = map_state.setdefault("failed_construction_projects", {})
    wood_now = int(item_counts.get("WoodLog") or 0)
    sealed_danger_cells = {
        (int(cell["x"]), int(cell["z"]))
        for room in dev.get("rooms") or [] if room_is_ancient_danger(room)
        for cell in room.get("cells") or []
        if cell.get("x") is not None and cell.get("z") is not None
    }
    available_builders = [pawn for pawn in snapshot.get("colonists") or []
                          if not pawn.get("downed") and not pawn.get("in_mental_state")
                          and not ((pawn.get("work_priorities") or {}).get("Construction") or {}).get("disabled")]
    maximum_builder_skill = max((int(((pawn.get("skills") or {}).get("Construction") or {}).get("level") or 0)
                                 for pawn in available_builders), default=0)
    projects = [row for row in dev.get("construction_projects", []) if isinstance(row, dict)
                and int(row.get("minimum_construction_skill") or 0) <= maximum_builder_skill
                and not issued_recently(map_state, f"construction_project:{row.get('thing_id')}", tick,
                                        retry_ticks=15000 if int(row.get("minimum_construction_skill") or 0) >= 3 else 5000)
                and (int((row.get("position") or {}).get("x") or -999),
                     int((row.get("position") or {}).get("z") or -999)) not in sealed_danger_cells
                and (not (failure := failed_projects.get(str(row.get("thing_id"))))
                     or tick - int(failure.get("tick") or 0) >= 30000
                     or wood_now > int(failure.get("wood") or 0))]
    # Forty near-identical wall frames can bury a single bed or joy object in
    # the model's context. Show a rotating, diverse actionable shortlist.
    shelter_unfinished = sleeping_place_counts(dev)[1] != len(snapshot["colonists"])
    project_rank = ({"Wall": 0, "Door": 1, "Bed": 2, "WoodPlankFloor": 3,
                     "TorchLamp": 4, "HorseshoesPin": 5, "FueledStove": 6,
                     "Table2x2c": 7, "SimpleResearchBench": 8}
                    if shelter_unfinished else
                    {"Bed": 0, "HorseshoesPin": 1, "FueledStove": 2, "Table2x2c": 3,
                     "TorchLamp": 4, "Door": 5, "SimpleResearchBench": 6,
                     "TableStonecutter": 7, "Shelf": 8, "Barricade": 9, "Wall": 10})
    if (dev.get("heat_threat") or {}).get("patients"):
        project_rank["PassiveCooler"] = -1
    if (dev.get("cold_threat") or {}).get("patients"):
        project_rank["Campfire"] = -1
        project_rank["Heater"] = -1
    if cooking_gap:
        project_rank.update({"Campfire": -1, "FueledStove": -1, "ElectricStove": -1})
    projects.sort(key=lambda row: (
        project_rank.get(str(row.get("def_name")), 11),
        0 if row.get("kind") == "frame" else 1,
        -float(row.get("percent_complete") or 0),
        squared_distance(row.get("position") or {}, anchor),
    ))
    project_types: Counter[str] = Counter()
    shortlist = []
    for project in projects:
        kind = str(project.get("def_name") or "other")
        if project_types[kind] >= 2:
            continue
        project_types[kind] += 1
        shortlist.append(project)
        if len(shortlist) >= 16:
            break
    if (projects and worker_criteria(snapshot, "Construction")
            and not issued_recently(map_state, "construction_project_priority", tick, retry_ticks=2500)):
        cooking_shortlist = [row for row in shortlist
                             if str(row.get("def_name") or "") in cooking_defs]
        if cooking_gap and cooking_shortlist:
            dev["urgent_cooking_projects"] = cooking_shortlist
            shortlist = cooking_shortlist
        details["construction_project_options"] = shortlist
        dev["construction_project_options"] = shortlist
        one_time.append("prioritize_construction_project")
    all_cooking_projects = [row for row in dev.get("construction_projects") or []
                            if str(row.get("def_name") or "") in cooking_defs]
    actionable_cooking_project = any(str(row.get("def_name") or "") in cooking_defs
                                     for row in projects)
    last_campfire = int((map_state.get("issued") or {}).get("campfire") or 0)
    retry_stalled_campfire = (bool(all_cooking_projects) and not actionable_cooking_project
                              and last_campfire > 0 and tick - last_campfire >= 30000
                              and int(map_state.get("campfire_attempts") or 1) < 2)
    if (not has_cooking_station and not actionable_cooking_project
            and (not all_cooking_projects or retry_stalled_campfire)
            and int(item_counts.get("WoodLog") or 0) >= 20
            and can_work("Construction")
            and not issued_recently(map_state, "campfire", tick, retry_ticks=5000)):
        one_time.append("build_campfire")
    threatened_rooms: list[tuple[set[tuple[int, int]], set[str], str]] = []
    for threat_key, source_defs, label in (
        ("heat_threat", {"PassiveCooler"}, "heatstroke"),
        ("cold_threat", {"Campfire", "Heater"}, "hypothermia"),
    ):
        patients = (dev.get(threat_key) or {}).get("patients") or []
        for room in dev.get("rooms") or []:
            cells = {(int(cell.get("x") or 0), int(cell.get("z") or 0))
                     for cell in room.get("cells") or []}
            if any((int((patient.get("position") or {}).get("x") or -1),
                    int((patient.get("position") or {}).get("z") or -1)) in cells
                   for patient in patients):
                threatened_rooms.append((cells, source_defs, label))
    thermal_projects = []
    for project in projects:
        pos = project.get("position") or {}
        cell = (int(pos.get("x") or -1), int(pos.get("z") or -1))
        for cells, source_defs, label in threatened_rooms:
            if cell in cells and str(project.get("def_name") or "") in source_defs:
                thermal_projects.append({**project, "threat": label})
                break
    if (thermal_projects and worker_criteria(snapshot, "Construction")
            and not issued_recently(map_state, "thermal_project_priority", tick, retry_ticks=600)):
        details["thermal_project_options"] = thermal_projects[:6]
        dev["thermal_project_options"] = details["thermal_project_options"]
        one_time.append("prioritize_thermal_project")
    item_counts = dev.get("item_counts", {})
    defense_styles = {
        "fortified_depth": {"killbox", "fallback", "turret", "mortar", "firefoam"},
        "mobile_response": {"fallback", "firefoam"},
        "ranged_firepower": {"fallback", "turret", "mortar", "firefoam"},
        "melee_chokepoints": {"killbox", "fallback", "firefoam"},
        "turret_mortar": {"fallback", "turret", "mortar", "firefoam"},
        "peaceful_deterrence": {"fallback", "firefoam"},
        "psychic_force": {"fallback", "firefoam"},
        "mechanized_force": {"fallback", "turret", "firefoam"},
        "anomaly_weapons": {"fallback", "firefoam"},
        "gravship_security": {"fallback", "turret", "firefoam"},
    }
    allowed_defenses = defense_styles.get(str(current_doctrine.get("military") or ""), {"killbox", "fallback", "turret", "mortar", "firefoam"})
    if "killbox" in allowed_defenses and int(item_counts.get("WoodLog") or 0) >= 180 and "killbox" not in map_state["issued"]:
        one_time.append("build_killbox")
    if "fallback" in allowed_defenses and int(item_counts.get("WoodLog") or 0) >= 100 and "fallback_defense" not in map_state["issued"]:
        one_time.append("build_fallback_defense")
    if "turret" in allowed_defenses and "GunTurrets" in finished and int(item_counts.get("Steel") or 0) >= 220 and int(item_counts.get("ComponentIndustrial") or 0) >= 6 and "turret_defense" not in map_state["issued"]:
        one_time.append("build_turret_defense")
    if "mortar" in allowed_defenses and "Mortars" in finished and int(item_counts.get("Steel") or 0) >= 120 and int(item_counts.get("ReinforcedBarrel") or 0) >= 1 and "mortar_post" not in map_state["issued"]:
        one_time.append("build_mortar_post")
    if "firefoam" in allowed_defenses and "Firefoam" in finished and int(item_counts.get("Steel") or 0) >= 75 and "firefoam_defense" not in map_state["issued"]:
        one_time.append("build_firefoam_defense")
    mech_remains = [
        row for row in dev.get("things", [])
        if "Mechanoid" in str(row.get("def_name") or "")
        or "CorpsesMechanoid" in (row.get("categories") or [])
    ]
    machining_project = next((row for row in dev.get("research_tree") or []
                              if row.get("name") == "Machining"), {})
    machining_actionable = (
        bool(any(row.get("thing_def") == "TableMachining" for row in dev.get("work_tables") or []))
        or "Machining" in finished
        or (machining_project.get("can_start_now")
            and machining_project.get("player_has_any_appropriate_research_bench") is not False)
    )
    if mech_remains and machining_actionable and not issued_recently(map_state, "mech_processing", tick, retry_ticks=60000):
        one_time.append("process_mechanoids")
    planned_sale_ids = {str(k) for k, v in (map_state.get("prisoner_plans") or {}).items() if v == "sell"}
    prisoner_sale_value = sum(
        float(p.get("market_value") or 0.0)
        for p in snapshot.get("combat", {}).get("prisoners", [])
        if str(p.get("id")) in planned_sale_ids
    )
    home_fighters = [pawn for pawn in snapshot["colonists"]
                     if not pawn.get("downed") and float(pawn.get("health") or 0) >= 0.8
                     and can_fight(pawn)]
    armed_fighters = [pawn for pawn in snapshot.get("combat", {}).get("colonists", [])
                      if not pawn.get("is_downed") and float(pawn.get("health") or 0) >= 0.8
                      and pawn.get("weapon_def")]
    trade_ready = (
        len(home_fighters) >= 3
        and (not snapshot.get("combat", {}).get("colonists") or len(armed_fighters) >= 3)
        and int(item_counts.get("MealSurvivalPack") or 0) + int(item_counts.get("Pemmican") or 0) >= 26
        and (bool(available_sale_categories(snapshot)) or int(item_counts.get("Silver") or 0) >= 1000
             or prisoner_sale_value >= 250)
        and dev.get("trade_destinations")
        and not dev.get("caravans")
        and not issued_recently(map_state, "trade_caravan", tick, retry_ticks=60000)
    )
    if trade_ready:
        sale_categories = available_sale_categories(snapshot)
        destinations = [row for row in dev.get("trade_destinations", []) if row.get("can_trade_now")][:5]
        for destination in destinations:
            for sale in sale_categories or (["funds"] if int(item_counts.get("Silver") or 0) >= 1000 else []):
                one_time.append(f"trade_to:{int(destination['settlement_id'])}:{sale}")
    healthy_fighters = [
        pawn for pawn in snapshot["colonists"]
        if not pawn.get("downed") and float(pawn.get("health") or 0.0) >= 0.85
        and can_fight(pawn)
    ]
    raid_ready = (
        len(healthy_fighters) >= 6
        and int(resources.get("food") or 0) >= 80
        and int(resources.get("medicine") or 0) >= 15
        and not dev.get("caravans")
        and not issued_recently(map_state, "raid_caravan", tick, retry_ticks=120000)
    )
    if raid_ready:
        for destination in dev.get("raid_destinations", [])[:6]:
            one_time.append(f"raid_to:{int(destination['settlement_id'])}")
    maintenance: list[str] = []
    meals = int(resources.get("meals") or 0)
    medical_emergency = any(
        c.get("downed") or bridge.first_number(c.get("health"), 1.0) < 0.65
        or bridge.first_number(c.get("bleeding_rate")) > 0.05 or c.get("tendable_now")
        for c in snapshot["colonists"]
    )
    if medical_emergency:
        available_rescuers = [colonist for colonist in snapshot["colonists"]
                              if not colonist.get("downed") and bridge.first_number(colonist.get("health"), 1) >= 0.5
                              and bridge.first_number((colonist.get("capacities") or {}).get("moving"), 1) >= 0.6]
        untreated = [colonist for colonist in snapshot["colonists"]
                     if colonist.get("tendable_now") or bridge.first_number(colonist.get("bleeding_rate")) > 0.05]
        completed_beds = [building for building in dev.get("buildings") or []
                          if str(building.get("def") or building.get("thing_def") or "") in {
                              "Bed", "HospitalBed", "SleepingSpot",
                          } and building.get("id") is not None]
        downed = [colonist for colonist in snapshot["colonists"]
                  if colonist.get("downed") and not patient_in_completed_bed(colonist, snapshot, completed_beds)]
        if downed and available_rescuers and completed_beds and not issued_recently(
            map_state, "direct_rescue", tick, retry_ticks=1200
        ):
            dev["rescue_patient_options"] = {str(pawn["id"]): (
                f"{pawn.get('name')}: health {pawn.get('health')}, bleeding {pawn.get('bleeding_rate')}, "
                f"hunger {pawn.get('hunger')}; rescue occupies one worker"
            ) for pawn in downed}
            one_time.append("rescue_downed_colonist")
        doctors = [pawn for pawn in available_rescuers
                   if isinstance((pawn.get("work_priorities") or {}).get("Doctor"), dict)
                   and not pawn["work_priorities"]["Doctor"].get("disabled")]
        if untreated and any(any(doctor["id"] != patient["id"] for doctor in doctors) for patient in untreated) and not issued_recently(
            map_state, "direct_tend", tick, retry_ticks=1200
        ):
            dev["tend_patient_options"] = {str(pawn["id"]): (
                f"{pawn.get('name')}: health {pawn.get('health')}, bleeding {pawn.get('bleeding_rate')}, "
                f"wounds {[condition.get('label') for condition in pawn.get('health_conditions') or [] if condition.get('tendable_now')][:3]}"
            ) for pawn in untreated}
            one_time.append("tend_colonist")
        if can_work("BasicWorker") and not issued_recently(map_state, "priority:BasicWorker", tick, retry_ticks=30000):
            maintenance.append("prioritize_rescue")
        if can_work("Doctor") and not issued_recently(map_state, "priority:Doctor", tick, retry_ticks=30000):
            maintenance.append("prioritize_doctor")
        # Injury changes the context and adds response options; it does not
        # remove unrelated feasible work from Laya's decision space.
    neutral_downed = [pawn for pawn in (snapshot.get("combat") or {}).get("neutral_downed") or []
                      if pawn.get("id") is not None and pawn.get("is_downed") and not pawn.get("is_dead")]
    neutral_rescuers = [pawn for pawn in snapshot["colonists"]
                        if not pawn.get("downed") and not pawn.get("in_mental_state")
                        and bridge.first_number((pawn.get("capacities") or {}).get("moving"), 1) >= 0.6]
    neutral_beds = [bed for bed in dev.get("buildings") or []
                    if bed.get("id") is not None and bed.get("def") in {"Bed", "HospitalBed", "SleepingSpot"}
                    and not bed.get("for_prisoners")]
    active_neutral_rescues = {int(pawn["current_job_target_id"])
                              for pawn in (snapshot.get("combat") or {}).get("colonists") or []
                              if str(pawn.get("current_job") or "").lower() == "rescue"
                              and pawn.get("current_job_target_id") is not None}
    neutral_options = {str(pawn["id"]): (
        f"{pawn.get('name')}, {pawn.get('gender')}, age {pawn.get('biological_age')}; "
        f"health {pawn.get('health')}, bleeding {pawn.get('bleeding_rate')}; "
        f"skills {pawn.get('top_skills') or []}, traits {pawn.get('traits') or []}. "
        "Rescue may lead to a join request but is not guaranteed; treatment and food cost labor."
    ) for pawn in neutral_downed
        if int(pawn["id"]) not in active_neutral_rescues
        and not issued_recently(map_state, f"neutral_rescue:{pawn['id']}", tick, retry_ticks=1800)}
    if neutral_options and neutral_rescuers and neutral_beds:
        dev["neutral_rescue_options"] = neutral_options
        dev["neutral_rescuers"] = {str(pawn["id"]): (
            f"{pawn.get('name')}: health {pawn.get('health')}, current job {pawn.get('current_job')}; "
            f"Medicine {((pawn.get('skills') or {}).get('Medicine') or {}).get('level', 0)}"
        ) for pawn in neutral_rescuers}
        one_time.append("rescue_neutral_arrival")
    if counts.get("Bed", 0) + counts.get("SleepingSpot", 0) < len(snapshot["colonists"]) or any(
        counts.get(name, 0) == 0 for name in ("FueledStove", "SimpleResearchBench")
    ):
        if can_work("Construction") and not issued_recently(map_state, "priority:Construction", tick, retry_ticks=60000):
            maintenance.append("prioritize_construction")
    if current.lower() != "none" and has_research_bench and not researcher_is_dedicated(snapshot):
        if research_staffing_plan(snapshot) and not issued_recently(map_state, "priority:Research", tick, retry_ticks=12000):
            maintenance.append("prioritize_research")
    if has_cooking_station and meals < max(8, len(snapshot["colonists"]) * 4):
        if can_work("Cooking") and not issued_recently(map_state, "priority:Cooking", tick, retry_ticks=60000):
            maintenance.append("prioritize_cooking")
    if can_work("Growing") and not issued_recently(map_state, "priority:Growing", tick, retry_ticks=60000):
        maintenance.append("prioritize_growing")
    if can_work("Hauling") and not issued_recently(map_state, "priority:Hauling", tick, retry_ticks=60000):
        maintenance.append("prioritize_hauling")
    if can_work("PlantCutting") and not issued_recently(map_state, "priority:PlantCutting", tick, retry_ticks=60000):
        maintenance.append("prioritize_plant_cutting")
    if can_work("Cleaning") and not issued_recently(map_state, "priority:Cleaning", tick, retry_ticks=60000):
        maintenance.append("prioritize_cleaning")
    if snapshot["map"].get("animals", 0) > 0:
        if (not colony_recovering and can_work("Hunting")
                and not issued_recently(map_state, "priority:Hunting", tick, retry_ticks=60000)):
            maintenance.append("prioritize_hunting")
        if can_work("Handling") and not issued_recently(map_state, "priority:Handling", tick, retry_ticks=60000):
            maintenance.append("prioritize_handling")
        if details.get("hunt_options") and not issued_recently(map_state, "safe_hunting", tick, retry_ticks=60000):
            maintenance.append("designate_safe_hunting")
    all_wild_plant_groups: dict[str, dict[str, Any]] = {}
    cultivated_defs = {"Plant_Rice", "Plant_Corn", "Plant_Potato", "Plant_Cotton", "Plant_Psychoid", "Plant_Hops", "Plant_Healroot"}
    for plant in dev.get("plants", []):
        if not plant.get("harvestable_now") or plant.get("is_designated_for_harvest"):
            continue
        name = str(plant.get("def_name") or "")
        if name in cultivated_defs:
            continue
        pos = plant.get("position") or {}
        if (int(pos.get("x") or 0) - int(anchor["x"])) ** 2 + (int(pos.get("z") or 0) - int(anchor["z"])) ** 2 > 45 ** 2:
            continue
        if bridge.combat_planner.errand_exposed(snapshot, pos):
            continue
        plant_id = int(plant.get("thing_id") or -1)
        if plant_id < 0 or issued_recently(map_state, f"wild_plant:{plant_id}", tick, retry_ticks=120000):
            continue
        group = all_wild_plant_groups.setdefault(name, {
            "label": str(plant.get("label") or name),
            "harvested_thing": str(plant.get("harvested_thing_def") or "unknown"),
            "count": 0,
            "expected_yield": 0,
            "ids": [],
        })
        group["count"] += 1
        group["expected_yield"] += int(plant.get("harvest_yield") or 0)
        group["ids"].append(plant_id)
    # Wood has its own explicit tree-cutting action. A large timber yield must
    # not masquerade as food under the wild-foraging action during starvation.
    wild_plant_groups = {name: group for name, group in all_wild_plant_groups.items()
                         if group["harvested_thing"] != "WoodLog"
                         and (not food_emergency or is_edible_wild_harvest(group["harvested_thing"]))}
    if wild_plant_groups and can_work("PlantCutting") and not issued_recently(map_state, "harvest", tick, retry_ticks=30000):
        details["wild_plant_options"] = wild_plant_groups
        dev["wild_plant_options"] = wild_plant_groups
        maintenance.append("harvest_local_plants")
    pending_tree_wood = sum(
        int(plant.get("harvest_yield") or 0)
        for plant in dev.get("plants", [])
        if plant.get("harvestable_now")
        and plant.get("harvested_thing_def") == "WoodLog"
        and (plant.get("is_designated_for_harvest") or issued_recently(
            map_state, f"tree:{plant.get('thing_id')}", tick, retry_ticks=120000))
    )
    dev["pending_tree_wood"] = pending_tree_wood
    tree_yield_by_id = {
        int(plant.get("thing_id") or -1): int(plant.get("harvest_yield") or 0)
        for plant in dev.get("plants", []) if plant.get("harvested_thing_def") == "WoodLog"
    }
    tree_groups = {}
    for name, group in all_wild_plant_groups.items():
        if "Tree" not in name or group["harvested_thing"] != "WoodLog":
            continue
        fresh_ids = [plant_id for plant_id in group["ids"] if not issued_recently(
            map_state, f"tree:{plant_id}", tick, retry_ticks=120000
        )]
        if fresh_ids:
            tree_groups[name] = {**group, "count": len(fresh_ids), "ids": fresh_ids,
                                 "expected_yield": sum(tree_yield_by_id.get(plant_id, 0)
                                                       for plant_id in fresh_ids)}
    if (tree_groups and pending_tree_wood < 120 and can_work("PlantCutting")
            and ((int(item_counts.get("WoodLog") or 0) < 50
                  and (dev.get("construction_projects") or dev.get("cold_threat")))
                 or needs_cooking_fuel_reserve(snapshot))
            and not issued_recently(map_state, "wood_harvest", tick, retry_ticks=6000)):
        details["tree_options"] = tree_groups
        dev["tree_options"] = tree_groups
        one_time.append("harvest_nearby_trees")
    research_options = live_research_options(snapshot) if has_research_bench else {}
    # Once Laya has a concrete doctrine or caravan prerequisite, an unfiltered
    # catalogue can override it with unrelated technology. Keep the broad
    # catalogue only when no aligned, startable step is available.
    aligned_research_ready = ("advance_doctrine_research" in one_time
                              or "prepare_trade_rations" in one_time)
    if (research_options and not aligned_research_ready
            and not issued_recently(map_state, "research_change", tick, retry_ticks=30000)):
        dev["live_research_options"] = research_options
        one_time.append("select_research")
    work_options = live_work_options(snapshot)
    if work_options and not issued_recently(map_state, "work_priority_change", tick, retry_ticks=60000):
        dev["live_work_options"] = work_options
        one_time.append("set_work_priority")
    actionable = list(dict.fromkeys(one_time + maintenance))
    if not can_work("Construction"):
        actionable = [action for action in actionable if not requires_builder_now(action)]
    actionable = defer_discretionary_work_until_shelter(snapshot, map_state, actionable)
    actionable = defer_new_construction_when_backlogged(snapshot, actionable)
    actionable = focus_active_fire_choices(actionable, bool(home_fires))
    actionable = focus_cold_start_choices(snapshot, actionable, details)
    if not dev.get("cold_start_focus"):
        actionable = focus_imminent_food_choices(snapshot, actionable)
        actionable = focus_cooking_gap_choices(snapshot, actionable)
        actionable = focus_misaligned_research_choice(snapshot, actionable)
    if dev.get("blocked_food_emergency") and "open_blocked_food_path" in actionable:
        # A pawn surrounded by completed walls cannot walk to food, escape a
        # raid or be rescued. Eating the nearest meal is not an executable
        # alternative, even if that stack is only a few cells away.
        actionable = ["open_blocked_food_path"]
    idle_workers = any(colonist_is_idle(colonist) for colonist in snapshot["colonists"])
    urgent = (bool(home_fires) or bool(fire_options) or food_emergency or medical_emergency or bool((dev.get("heat_threat") or {}).get("patients"))
              or bool((dev.get("cold_threat") or {}).get("patients"))
              or bool(relevant_forbidden(snapshot)) or bool(hungry_eaters) or bool(sealed_food_store))
    # Waiting is a meaningful choice only while work is really under way or
    # colonists need time to sleep/eat. It must not dominate an idle emergency.
    if not actionable or (not urgent and not idle_workers):
        actionable.append("hold_survival")
    return actionable, details


def defer_discretionary_work_until_shelter(
    snapshot: dict[str, Any], map_state: dict[str, Any], actions: list[str]
) -> list[str]:
    """Keep Laya's choices focused on work the founding crew can finish.

    This is an action-feasibility budget, not a prescribed build order: Laya
    still chooses among food, equipment, jobs, bedding and the first house.
    Resource-heavy expansions cannot compete for the same wood and sole builder
    before anybody has a roof. Live threats and patient care remain available.
    """
    people = snapshot.get("colonists") or []
    if not people:
        return actions
    development = snapshot.get("development") or {}
    _, sheltered = sleeping_place_counts(development)
    sheltered_real_beds = sheltered_real_bed_count(development, map_state.get("anchor"))
    if sheltered is None or (sheltered >= len(people)
                             and sheltered_real_beds is not None
                             and sheltered_real_beds >= len(people)):
        return actions
    active_threat = bool((snapshot.get("map") or {}).get("enemies"))
    def deferred(action: str) -> bool:
        if action.startswith("income_") or action.startswith(("trade_to:", "raid_to:")):
            return True
        if action in {
            "build_cemetery", "build_crematorium", "build_freezer", "build_power",
            "build_hitech_lab", "build_fabrication", "build_hospital",
            "build_weapon_shelves", "build_prison", "build_animal_barn", "build_animal_pen",
            "plan_architecture", "commission_sculptures", "install_sculpture",
            "start_stonecutting", "start_taming", "tame_wild_human", "choose_colony_doctrine",
            "develop_colonist_skill", "build_temple", "build_pathways",
            "build_catalog_building", "floor_critical_room", "upgrade_workbench",
            "build_income_infrastructure", "configure_income_production",
        }:
            return True
        if action in {"build_killbox", "build_fallback_defense", "build_turret_defense",
                      "build_mortar_post", "build_firefoam_defense"}:
            return not active_threat
        return False
    filtered = [action for action in actions if not deferred(action)]
    snapshot.setdefault("development", {})["deferred_until_shelter"] = [
        action for action in actions if deferred(action)
    ]
    return filtered or actions


def defer_new_construction_when_backlogged(
    snapshot: dict[str, Any], actions: list[str]
) -> list[str]:
    """Keep the model's next construction choice executable by the current crew.

    A large existing queue is already a set of Laya-approved building choices.
    New optional blueprints would compete for the same builders and materials,
    so present completion and staffing choices until capacity returns. Genuine
    shelter, food, temperature and immediate-defense gaps remain available.
    """
    development = snapshot.setdefault("development", {})
    development.pop("deferred_for_construction_capacity", None)
    projects = development.get("construction_projects") or []
    people = snapshot.get("colonists") or []
    builders = sum(
        not pawn.get("downed") and not pawn.get("in_mental_state")
        and not ((pawn.get("work_priorities") or {}).get("Construction") or {}).get("disabled")
        and int(((pawn.get("work_priorities") or {}).get("Construction") or {}).get("priority") or 0) > 0
        for pawn in people
    )
    capacity = max(24, builders * 10)
    if not builders or len(projects) < capacity:
        return actions

    counts = development.get("building_counts") or {}
    resources = (snapshot.get("map") or {}).get("resources") or {}
    _, sheltered = sleeping_place_counts(development)
    sheltered_real = sheltered_real_bed_count(development, development.get("base_anchor"))
    shelter_gap = (sheltered is not None and sheltered < len(people)) or (
        sheltered_real is not None and sheltered_real < len(people)
    )
    cooking_gap = (int(resources.get("raw_food") or 0) > 0
                   and not any(int(counts.get(name) or 0)
                               for name in ("Campfire", "FueledStove", "ElectricStove")))
    heat_threat = bool(development.get("heat_threat"))
    cold_threat = bool(development.get("cold_threat"))
    active_enemy = bool((snapshot.get("map") or {}).get("enemies")
                        or (snapshot.get("combat") or {}).get("hostiles"))
    capturable_enemy = bool((snapshot.get("combat") or {}).get("prisoners")) or any(
        hostile.get("is_downed") and not hostile.get("is_dead")
        for hostile in (snapshot.get("combat") or {}).get("hostiles") or []
    )
    vital = set()
    if shelter_gap:
        vital.update({"build_starter_base", "build_basic_beds", "build_sleeping_spots"})
    if cooking_gap:
        vital.add("build_campfire")
    if heat_threat:
        vital.add("build_passive_cooler")
    if cold_threat:
        vital.update({"build_room_campfire", "build_room_heater"})
    if active_enemy:
        vital.update({"build_fallback_defense", "build_firefoam_defense"})
    if capturable_enemy:
        vital.add("build_prison")
    deferred = [action for action in actions
                if requires_builder_now(action) and action not in vital]
    if not deferred:
        return actions
    development["deferred_for_construction_capacity"] = deferred
    return [action for action in actions if action not in deferred]


def build_decision_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    capabilities: dict[str, dict[str, Any]] = {}
    all_skill_names = sorted({
        str(skill_name)
        for colonist in snapshot.get("colonists", [])
        for skill_name in (colonist.get("skills") or {})
    })
    for skill_name in all_skill_names:
        ranked = sorted(snapshot.get("colonists", []), key=lambda c: int((c.get("skills", {}).get(skill_name) or {}).get("level") or 0), reverse=True)
        if ranked:
            skill = (ranked[0].get("skills", {}).get(skill_name) or {})
            capabilities[skill_name] = {
                "best": ranked[0].get("name"),
                "level": int(skill.get("level") or 0),
                "passion": professions.passion_info(skill.get("passion"))["icon"],
                "learning_percent": professions.passion_info(skill.get("passion"))["xp_percent"],
            }
    people = []
    colonists = snapshot.get("colonists", [])
    for c in colonists[:10]:
        skill_rows = sorted(
            (c.get("skills") or {}).items(),
            key=lambda item: (
                bool((item[1] or {}).get("passion")),
                int((item[1] or {}).get("level") or 0),
                not bool((item[1] or {}).get("disabled")),
            ),
            reverse=True,
        )[:8]
        people.append({
            "id": c.get("id"), "name": c.get("name"), "health": c.get("health"), "food": c.get("hunger"),
            "rest": c.get("rest"), "mood": c.get("mood"), "joy": c.get("joy"),
            "beauty": c.get("beauty"), "comfort": c.get("comfort"),
            "downed": c.get("downed"), "job": c.get("current_job"),
            "traits": [t.get("label") or t.get("name") for t in c.get("traits", [])[:5]],
            "capacities": {
                name: (c.get("capacities") or {}).get(name)
                for name in ("consciousness", "moving", "manipulation", "sight", "talking")
                if name in (c.get("capacities") or {})
            },
            "pain": c.get("pain", 0), "bleeding_rate": c.get("bleeding_rate", 0),
            "tendable_wounds": sum(bool(h.get("tendable_now")) for h in c.get("health_conditions", [])),
            "conditions": [
                f"{h.get('label') or h.get('def_name')}:{h.get('part')}"
                for h in c.get("health_conditions", [])[:6]
            ],
            "skills": {
                name: {
                    "level": int(row.get("level") or 0),
                    "flame": professions.passion_info(row.get("passion"))["icon"],
                    "disabled": bool(row.get("disabled")),
                }
                for name, row in skill_rows
            },
        })
    dev = snapshot.get("development", {})
    profession_directions = (dev.get("profession_context") or {}).get("directions", {})
    compact_directions = {
        name: {
            "label": row.get("label"),
            "fit": row.get("fit_score"),
            "best_people": [
                {
                    "pawn": person.get("pawn"), "skill": person.get("skill"),
                    "level": person.get("level"), "flame": person.get("flame"),
                }
                for person in (row.get("people") or [])[:2]
            ],
            "work": list(row.get("work_types") or [])[:5],
            "buildings": list(row.get("building_programs") or [])[:4],
        }
        for name, row in sorted(
            profession_directions.items(),
            key=lambda item: float((item[1] or {}).get("fit_score") or 0.0),
            reverse=True,
        )[:12]
    }
    work_types = []
    for row in (dev.get("profession_context") or {}).get("work_types", [])[:48]:
        if isinstance(row, dict):
            work_types.append({
                "name": row.get("def_name") or row.get("name"),
                "label": row.get("label"),
                "skills": list(row.get("relevant_skills") or [])[:3],
            })
        else:
            work_types.append(str(row))
    catalog = dev.get("building_catalog_summary") or {}
    compact_catalog = {
        "total": catalog.get("total_player_buildings"),
        "available_now": catalog.get("available_now"),
        "affordable_now": (dev.get("catalog_access_audit") or {}).get("affordable_now"),
        "categories": dict(list((catalog.get("categories") or {}).items())[:20]),
        "worktables": list(catalog.get("worktables") or [])[:32],
        "programs": {
            name: (row or {}).get("label")
            for name, row in list((catalog.get("programs") or {}).items())[:24]
        },
    }
    active_mods = [
        {
            "name": row.get("name"),
            "package_id": row.get("package_id"),
            "version": row.get("version"),
        }
        for row in dev.get("active_mods", [])[:24]
        if isinstance(row, dict)
    ]
    weather = dev.get("weather") or {}
    # The storyteller's easy-join routes taper off as the colony grows. Keep
    # alternative recruitment routes visible through the early/mid game.
    population = growth.population_context(snapshot) if len(colonists) <= 8 else None
    state = {
        "goal": "A self-sufficient colony pursuing its saved doctrine and chosen long-term ending.",
        "population_growth": ({
            "best_skills": population["best_skills"],
            "live_signals": population["live_signals"],
            "routes": population["routes"],
            "tradeoff": population["tradeoff"],
        } if population else None),
        "player_preferences": laya_preferences.model_context(dev.get("user_preferences") or laya_preferences.load_preferences()),
        "colony": {
            "date": snapshot.get("game", {}).get("date"),
            "wealth": snapshot.get("game", {}).get("wealth"),
            "population": len(colonists),
            "people_omitted": max(0, len(colonists) - len(people)),
            "threats": snapshot.get("map", {}).get("enemies"),
        },
        "resources": snapshot.get("map", {}).get("resources", {}),
        "people": people,
        "capabilities": capabilities,
        "colony_animals": {
            "count": len(snapshot.get("animals", [])),
            "hungry": sum(
                1 for animal in snapshot.get("animals", [])
                if bridge.first_number(animal.get("hunger"), 1.0) < 0.3
            ),
        },
        "development": {
            "buildings": dict(list((dev.get("building_counts") or {}).items())[:80]),
            "zones": [z.get("label") for z in dev.get("zones", [])[:24]],
            "research": (dev.get("current_research") or {}).get("name"),
            "finished_research": list(dev.get("finished_research") or [])[:80],
            "human_corpses": len(corpse_rows(snapshot, "CorpsesHumanlike")), "animal_corpses": len(corpse_rows(snapshot, "CorpsesAnimal")),
            "corpse_context": dev.get("corpse_context"), "organ_context": dev.get("organ_context"),
            "trade_goods_value": dev.get("trade_value", 0), "income_strategy": dev.get("income_strategy"), "doctrine": dev.get("doctrine"),
            "recent_course_changes": (dev.get("doctrine_history") or [])[-2:],
            "doctrine_audit": dev.get("doctrine_audit"), "active_mods": active_mods,
            "weather": {
                name: weather.get(name)
                for name in (
                    "weather", "temperature", "growth_season_now", "day_of_year",
                    "quadrum", "current_twelfth", "next_twelfth_average_temperatures",
                )
                if name in weather
            },
            "growing_period": (dev.get("tile_details") or {}).get("growing_period"),
            "rooms": [{"id": r.get("id"), "role": r.get("role_label"), "cleanliness": r.get("cleanliness"), "impressiveness": r.get("impressiveness"), "temperature": r.get("temperature"), "average_glow": r.get("average_glow"), "dark_percent": r.get("dark_cells_percent")} for r in dev.get("rooms", []) if not r.get("touches_map_edge")][:20],
            "storage_utilization_percent": (dev.get("storage") or {}).get("utilization_percent", 0),
            "materials": {name: dev.get("item_counts", {}).get(name, 0) for name in ("Silver", "WoodLog", "Steel", "ComponentIndustrial", "MedicineHerbal", "MedicineIndustrial", "Ambrosia")},
            "profession_direction_fit": compact_directions,
            "all_loaded_work_types": work_types,
            "building_catalog": compact_catalog,
            "royalty": dev.get("royalty", {}),
        },
    }
    return enforce_model_state_budget(state)


def enforce_model_state_budget(state: dict[str, Any], max_characters: int = 12000) -> dict[str, Any]:
    """Bound Laya input without discarding survival, patients, threats or doctrine.

    Laya truncates the encoded state to its configured inference window, but its
    tokenizer first sees the whole JSON document.  Large mod descriptions and
    definition catalogs therefore caused tokenizer warnings and hid useful state
    behind irrelevant metadata.  The normal builder already summarizes those
    catalogs; this final guard also protects heavily modded and mature colonies.
    """
    def size() -> int:
        return len(json.dumps(state, ensure_ascii=False, separators=(",", ":"), default=str))

    if size() <= max_characters:
        return state
    development = state.get("development") or {}
    reductions = (
        ("all_loaded_work_types", lambda value: list(value or [])[:24]),
        ("profession_direction_fit", lambda value: dict(list((value or {}).items())[:8])),
        ("rooms", lambda value: list(value or [])[:10]),
        ("finished_research", lambda value: list(value or [])[:40]),
        ("active_mods", lambda value: list(value or [])[:12]),
        ("buildings", lambda value: dict(list((value or {}).items())[:40])),
    )
    for key, reducer in reductions:
        development[key] = reducer(development.get(key))
        if size() <= max_characters:
            return state
    catalog = development.get("building_catalog") or {}
    development["building_catalog"] = {
        "total": catalog.get("total"),
        "available_now": catalog.get("available_now"),
        "affordable_now": catalog.get("affordable_now"),
        "categories": catalog.get("categories", {}),
        "programs": catalog.get("programs", {}),
    }
    if size() <= max_characters:
        return state
    for person in state.get("people") or []:
        person["skills"] = dict(list((person.get("skills") or {}).items())[:4])
        person["conditions"] = list(person.get("conditions") or [])[:3]
    if size() <= max_characters:
        return state
    state["people"] = list(state.get("people") or [])[:6]
    development["rooms"] = list(development.get("rooms") or [])[:6]
    development["profession_direction_fit"] = dict(
        list((development.get("profession_direction_fit") or {}).items())[:5]
    )
    if size() <= max_characters:
        return state
    # Personal guidance remains present, but a pasted essay must not evict live
    # hunger, health and threat data from the model's short inference window.
    preferences = state.get("player_preferences")
    if isinstance(preferences, dict):
        state["player_preferences"] = {
            key: (value[:500] if isinstance(value, str) else value)
            for key, value in list(preferences.items())[:20]
        }
    if size() <= max_characters:
        return state
    # Last-resort shape for extremely modded saves. Candidate generation and
    # feasibility checks have already consumed the full snapshot, so removing
    # definition catalogs here cannot make an impossible action executable.
    state["resources"] = dict(list((state.get("resources") or {}).items())[:24])
    state["capabilities"] = dict(list((state.get("capabilities") or {}).items())[:12])
    state["development"] = {
        key: development.get(key)
        for key in (
            "research", "human_corpses", "animal_corpses", "corpse_context",
            "organ_context", "trade_goods_value", "income_strategy", "doctrine",
            "recent_course_changes",
            "weather", "growing_period", "storage_utilization_percent", "materials",
        )
    }
    return state


def action_domain(name: str) -> str:
    if name in {"prioritize_thermal_project", "build_room_campfire", "build_room_heater", "connect_room_heater_power"}:
        return "care"
    if name.startswith(("income_", "trade_to:", "raid_to:", "prisoner_policy:")): return "economy_diplomacy"
    if name.startswith(("prioritize_", "harvest_", "designate_", "start_", "breed_")) or name in {"develop_colonist_skill", "optimize_night_owl_schedule", "schedule_recreation", "set_work_priority", "rebalance_cooking"}: return "work_orders"
    if name.startswith(("build_killbox", "build_fallback", "build_turret", "build_mortar", "build_firefoam", "process_mechanoids")): return "defense"
    if name in {"care_for_injured_animal", "feed_hungry_animal", "feed_hungry_colonist", "eat_available_meal", "open_sealed_food_store", "open_blocked_food_path", "build_hospital", "build_passive_cooler", "configure_hospital_beds", "build_prison", "assign_real_bed", "prepare_emergency_medical_bed", "rescue_neutral_arrival"}: return "care"
    if name in {"unforbid_corpses", "create_human_corpse_dump", "create_animal_corpse_dump", "build_cemetery", "build_crematorium"}: return "corpse_management"
    if name.startswith(("build_", "create_", "expand_", "floor_", "install_", "commission_", "excavate_", "finish_")) or name in {"plan_architecture", "improve_room_lighting", "upgrade_workbench"}: return "construction"
    return "strategy"


def action_family(name: str) -> str:
    if name in {"prioritize_thermal_project", "build_room_campfire", "build_room_heater",
                "connect_room_heater_power",
                "build_passive_cooler"}:
        return "temperature_care"
    for prefix in ("trade_to:", "raid_to:", "prisoner_policy:", "human_reproduction:", "breed_animals:"):
        if name.startswith(prefix): return prefix.rstrip(":")
    if name.startswith("income_"): return "income_strategy"
    if name.startswith("prioritize_") or name in {"set_work_priority", "rebalance_cooking"}: return "work_priority"
    if name.startswith("build_"): return "building_project"
    if name in {"plan_architecture", "improve_room_lighting", "upgrade_workbench"}: return "building_project"
    if name in {"develop_colonist_skill", "optimize_night_owl_schedule", "schedule_recreation"}: return "workforce_development"
    if name.startswith("create_"): return "zone_or_production"
    return name.split(":", 1)[0]


def worker_criteria(snapshot: dict[str, Any], skill_name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    work_def = next((row for row in (snapshot.get("development") or {}).get("work_types") or []
                     if isinstance(row, dict) and str(row.get("def_name") or row.get("name")) == skill_name), {})
    relevant_skills = list(work_def.get("relevant_skills") or []) or [skill_name]
    for pawn in snapshot.get("colonists", []):
        if pawn.get("downed") or pawn.get("in_mental_state"):
            continue
        work_name = "Hauling" if skill_name == "Hauling" else skill_name
        priority = (pawn.get("work_priorities") or {}).get(work_name)
        if not isinstance(priority, dict) or priority.get("disabled"):
            continue
        skills = []
        for relevant in relevant_skills[:3]:
            skill_row = (pawn.get("skills") or {}).get(relevant) or {}
            passion = professions.passion_info(skill_row.get("passion"))
            skills.append(f"{relevant} {int(skill_row.get('level') or 0)} {passion['icon']}")
        traits = ", ".join(str(t.get("label") or t.get("name")) for t in pawn.get("traits", [])) or "no notable traits"
        conditions = ", ".join(f"{h.get('label') or h.get('def_name')} {h.get('part')}" for h in pawn.get("health_conditions", [])) or "no visible injury"
        caps = pawn.get("capacities") or {}
        result[str(pawn["id"])] = (
            f"{pawn.get('name')}: {skill_name}; {', '.join(skills)}; current priority {priority.get('priority')}; "
            f"job {pawn.get('current_job')}; traits {traits}; health {pawn.get('health')}; pain {pawn.get('pain')}; "
            f"moving {caps.get('moving', 1)}, manipulation {caps.get('manipulation', 1)}, sight {caps.get('sight', 1)}; {conditions}"
        )
    return result


def foraging_worker_criteria(snapshot: dict[str, Any]) -> dict[str, str]:
    workers = worker_criteria(snapshot, "PlantCutting")
    by_id = {str(row.get("id")): row for row in snapshot.get("colonists") or []}
    options: dict[str, str] = {}
    for pawn_id in workers:
        pawn = by_id.get(pawn_id) or {}
        priorities = pawn.get("work_priorities") or {}
        grow = int((priorities.get("Growing") or {}).get("priority") or 0)
        cut = int((priorities.get("PlantCutting") or {}).get("priority") or 0)
        plants = int(((pawn.get("skills") or {}).get("Plants") or {}).get("level") or 0)
        job = str(pawn.get("current_job") or "idle")
        competition = "; sowing may delay cut" if grow == 1 and job == "Sow" else ""
        options[pawn_id] = (f"{pawn.get('name')}; Grow {grow}, Cut {cut}; now {job}; "
                            f"Plants {plants}, health {bridge.first_number(pawn.get('health'), 1):.0%}"
                            + competition)
    return options


def subchoice_questions_for_action(action: str, snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dev = snapshot.get("development", {})
    q: dict[str, dict[str, Any]] = {}
    if action == "rebalance_cooking" and dev.get("cooking_rebalance_options"):
        q["cooking_rebalance_choice"] = {
            "type": "choice",
            "instructions": "Choose who should make meals now. Compare cooking skill and food-poisoning risk with the animal work or other duties this delays.",
            "criteria": {key: row["summary"] for key, row in dev["cooking_rebalance_options"].items()},
        }
    if action == "assign_real_bed" and dev.get("bed_assignment_options"):
        q["bed_assignment"] = {
            "type": "choice", "instructions": "Choose which sleeping colonist should claim which completed bed now.",
            "criteria": dict(dev["bed_assignment_options"]),
        }
    elif action == "rescue_neutral_arrival":
        if len(dev.get("neutral_rescue_options") or {}) > 1:
            q["neutral_patient"] = {"type": "choice",
                "instructions": "Choose which downed non-hostile person to rescue, weighing survival, skills, travel and colony food.",
                "criteria": dict(dev["neutral_rescue_options"])}
        if len(dev.get("neutral_rescuers") or {}) > 1:
            q["neutral_rescuer"] = {"type": "choice",
                "instructions": "Choose a mobile rescuer; this interrupts their current work while the visitor is carried to a bed.",
                "criteria": dict(dev["neutral_rescuers"])}
    elif action == "prepare_emergency_medical_bed" and dev.get("emergency_medical_bed_options"):
        q["emergency_medical_bed"] = {
            "type": "choice", "instructions": "Choose a completed bed to reserve for patients; it will no longer be an ordinary owned bed.",
            "criteria": dict(dev["emergency_medical_bed_options"]),
        }
    if action == "open_sealed_food_store":
        workers = worker_criteria(snapshot, "Construction")
        if len(workers) > 1:
            q["worker_pawn"] = {
                "type": "choice",
                "instructions": "Choose a mobile builder to remove the single wall blocking all stored meals. Consider construction skill, injuries and distance; the colony may starve if this waits.",
                "criteria": workers,
            }
    elif action == "eat_available_meal":
        options = dev.get("hungry_eater_options") or {}
        if len(options) > 1:
            q["hungry_eater"] = {
                "type": "choice",
                "instructions": "Choose which mobile colonist should interrupt work to eat now. Compare hunger, meal distance and the cost of interrupting current work.",
                "criteria": options,
            }
    elif action == "open_blocked_food_path" and dev.get("blocked_food_wall_options"):
        victim = next((p for p in snapshot.get("colonists", []) if p.get("name") == dev.get("blocked_food_pawn")), {})
        meal = dev.get("blocked_food_meal") or {}
        q["blocked_food_wall"] = {"type": "choice", "instructions":
            f"{dev.get('blocked_food_pawn')} cannot get out or has failed to reach food. Pick one adjacent wall to open toward meals at {meal}; deconstruction may expose the room and costs shelter.",
            "criteria": {str(w["id"]): f"Wall at {w.get('position')}; pawn at {victim.get('position')}; food at {meal}"
                         for w in dev["blocked_food_wall_options"]}}
        q["worker_pawn"] = {"type": "choice", "instructions": "Choose a mobile builder outside the blocked room to deconstruct the selected wall.",
                            "criteria": dev.get("blocked_food_builders") or {}}
    elif action == "finish_freezer_entrance":
        materials = dev.get("freezer_door_materials") or {}
        if len(materials) > 1:
            q["freezer_door_material"] = {
                "type": "choice",
                "instructions": "Choose an available door material. Steel uses scarce metal but avoids more wood cutting; wood is cheaper if a stock exists.",
                "criteria": materials,
            }
    elif action in {"rescue_downed_colonist", "tend_colonist"}:
        options = dev.get("rescue_patient_options" if action == "rescue_downed_colonist" else "tend_patient_options") or {}
        if len(options) > 1:
            q["medical_patient"] = {
                "type": "choice",
                "instructions": "Choose which injured colonist receives this direct medical action. Compare bleeding, health and time to death; other patients remain at risk.",
                "criteria": options,
            }
    elif action == "plan_architecture" and dev.get("architecture_program_options"):
        q["architecture_program"] = {
            "type": "choice",
            "instructions": "Choose the function of the next building first. Layout, size and furniture are asked only after this program is selected.",
            "criteria": dict(dev["architecture_program_options"]),
        }
    elif action == "advance_doctrine_research" and dev.get("doctrine_research_options"):
        misalignment = dev.get("research_misalignment") or {}
        instructions = (f"The current {misalignment.get('current')} project has only "
                        f"{misalignment.get('progress_percent')}% progress and misses the saved goal. "
                        "Choose a live project aligned with income or victory."
                        if misalignment else
                        "Choose one currently startable project that best advances the saved doctrine. Only live ResearchProjectDefs are listed.")
        q["doctrine_research_target"] = {
            "type": "choice",
            "instructions": instructions,
            "criteria": dict(dev["doctrine_research_options"]),
        }
    elif action == "improve_room_lighting" and dev.get("dark_room_options"):
        q["lighting_room"] = {
            "type": "choice",
            "instructions": "Choose the room where darkness currently causes the most work, treatment or quality loss.",
            "criteria": {
                str(key): f"{row.get('role')} room {row.get('room_id')}; average glow {row.get('average_glow')}; {row.get('dark_percent')}% dark; {row.get('temperature')} C"
                for key, row in dev["dark_room_options"].items()
            },
        }
    elif action == "develop_colonist_skill" and dev.get("skill_training_options"):
        q["skill_training_plan"] = {
            "type": "choice",
            "instructions": "Choose one real colonist-skill-work plan. Large flame learns at 150%, small flame at 100%, no flame at 35%; also consider current competence, Fast/Slow Learner traits and colony gaps.",
            "criteria": {
                str(key): (
                    f"{row.get('pawn_name')}: {row.get('skill')} {row.get('level')} {row.get('flame')} "
                    f"({row.get('xp_percent')}% passion multiplier, learning factor {row.get('learning_trait_factor')}); "
                    f"train through {', '.join(row.get('work_types') or [])}; traits {row.get('traits')}"
                ) for key, row in dev["skill_training_options"].items()
            },
        }
    elif action == "optimize_night_owl_schedule" and dev.get("night_owl_options"):
        q["night_owl_pawn"] = {
            "type": "choice",
            "instructions": "Choose which Night Owl receives a day-sleep/night-awake timetable now.",
            "criteria": dict(dev["night_owl_options"]),
        }
    elif action == "schedule_recreation" and dev.get("recreation_schedule_options"):
        q["recreation_pawn"] = {
            "type": "choice",
            "instructions": "Choose whose low recreation and mood justify two protected Joy hours. Consider pain, sleep and lost work time.",
            "criteria": dict(dev["recreation_schedule_options"]),
        }
        q["recreation_slot"] = {
            "type": "choice",
            "instructions": "Choose a daily two-hour recreation window; all options leave the usual night sleep intact.",
            "criteria": {
                "morning": "08:00-09:59: recover after waking, but delay early work",
                "midday": "12:00-13:59: break up the workday, but reduce peak work time",
                "evening": "18:00-19:59: finish work first, but mood may worsen earlier",
            },
        }
    elif action == "build_passive_cooler" and dev.get("cool_room_options"):
        q["cool_room"] = {
            "type": "choice",
            "instructions": "Choose which hot occupied room to cool first. A bedbound heatstroke patient can die before a general comfort upgrade is built; wood and builder time are finite.",
            "criteria": {
                str(key): (f"{row.get('role')} room {row.get('room_id')}: {row.get('temperature')} C, "
                           f"{row.get('beds')} beds, patients "
                           + (", ".join(f"{patient.get('name')} {int(float(patient.get('severity') or 0) * 100)}% heatstroke"
                                        for patient in row.get('patients') or []) or "none"))
                for key, row in dev["cool_room_options"].items()
            },
        }
    elif action in {"build_room_campfire", "build_room_heater", "connect_room_heater_power"} and (
            dev.get("warm_room_options") or dev.get("power_connection_options")):
        options = (dev.get("power_connection_options") if action == "connect_room_heater_power" else
                   dev.get("heater_room_options") if action == "build_room_heater" else
                   dev.get("warm_room_options")) or {}
        q["warm_room"] = {
            "type": "choice",
            "instructions": "Choose which cold occupied room to warm first. A bedbound hypothermia patient may die before another bedroom is made comfortable. Cable routes cost one steel per tile and take builder time.",
            "criteria": {
                str(key): (f"{row.get('role')} room {row.get('room_id')}: {row.get('temperature')} C, "
                           f"{row.get('beds')} beds, patients "
                           + (", ".join(f"{patient.get('name')} {int(float(patient.get('severity') or 0) * 100)}% hypothermia"
                                        for patient in row.get('patients') or []) or "none")
                           + (f"; cable {row.get('conduit_cost')} steel" if row.get('conduit_cost') is not None else ""))
                for key, row in options.items()
            },
        }
    elif action == "build_basic_beds" and dev.get("basic_bed_materials"):
        q["bed_material"] = {
            "type": "choice",
            "instructions": "Choose material for one real bed. Wood and steel preserve scarce resources differently; stone is durable but less comfortable.",
            "criteria": dict(dev["basic_bed_materials"]),
        }
    elif action == "upgrade_workbench" and dev.get("workbench_upgrade_options"):
        q["workbench_upgrade"] = {
            "type": "choice",
            "instructions": "Choose one unlocked and affordable production transition. The old bench remains until the new one is completed.",
            "criteria": {
                str(key): f"{row.get('old')} -> {row.get('new')}: {row.get('benefit')}; research {row.get('research')}; fixed costs {row.get('costs')}"
                for key, row in dev["workbench_upgrade_options"].items()
            },
        }
    elif action.startswith("trade_to:"):
        q["trade_purchase_plan"] = {"type": "choice", "instructions": "Choose a purchase priority; survival reserves are protected by code.", "criteria": {
            "medicine": "Medicine", "components": "Components and advanced components", "food": "Shelf-stable food",
            "weapons": "Weapons or armor", "livestock": "Productive or pack animals",
            "slaves": "Inspect actual people offered at the settlement; buy one only if Laya chooses them after arrival",
            "none": "Sell only and preserve silver",
        }}
    elif action == "start_stonecutting" and dev.get("stone_options"):
        q["stone_type"] = {"type": "choice", "instructions": "Choose the nearby chunk type to cut.", "criteria": {str(k): f"{v} nearby chunks" for k, v in dev["stone_options"].items()}}
    elif action == "start_taming" and dev.get("tame_options"):
        handler = dev.get("handler_context") or {}
        q["tame_target"] = {"type": "choice", "instructions": f"Choose an exact animal. Handler {handler}.", "criteria": {
            str(a["id"]): f"{a.get('def')} {a.get('gender')}; wildness {a.get('wildness')}; minimum skill {a.get('minimum_handling_skill')}; revenge {a.get('manhunter_on_tame_fail_chance')}; value {a.get('market_value')}"
            for a in dev["tame_options"]
        }}
    elif action == "tame_wild_human" and dev.get("wild_human_options"):
        q["wild_human_target"] = {"type": "choice", "instructions": "Choose one nearby wild person to tame; this can recruit them but needs a handler with Animals 7 and may fail.", "criteria": {
            str(person["id"]): f"{person.get('name')} {person.get('gender')}, age {person.get('age')}, health {person.get('health')}"
            for person in dev["wild_human_options"]
        }}
    elif action == "designate_safe_hunting" and dev.get("hunt_options"):
        q["hunt_target"] = {"type": "choice", "instructions": f"Choose the exact target using food need and fighter context {dev.get('fighter_context')}.", "criteria": {
            str(a["id"]): f"{a.get('def')} {a.get('gender')}; power {a.get('combat_power')}; revenge {a.get('harm_revenge_chance')}; meat {a.get('meat_amount')}; leather {a.get('leather_amount')}; value {a.get('market_value')}"
            for a in dev["hunt_options"]
        }}
    elif action == "consider_dangerous_hunt" and dev.get("risky_hunt_options"):
        q["risky_hunt_target"] = {"type": "choice", "instructions": "Pick a dangerous target to assess, not yet to attack. High revenge can summon a herd and wipe out a small colony.", "criteria": {
            str(a["id"]): f"{a.get('def')} {a.get('gender')}; power {a.get('combat_power')}; revenge {float(a.get('harm_revenge_chance') or 0)*100:.0f}%; meat {a.get('meat_amount')}; value {a.get('market_value')}"
            for a in dev["risky_hunt_options"]
        }}
    elif action == "harvest_local_plants" and dev.get("wild_plant_options"):
        q["wild_plant_type"] = {"type": "choice", "instructions": "Choose mature edible plants by reachable yield. Gathering them preserves the planted rice for a fuller later harvest.", "criteria": {
            str(k): f"{v.get('label')}: {v.get('count')} plants, expected {v.get('expected_yield')} {v.get('harvested_thing')}" for k, v in dev["wild_plant_options"].items()
        }}
        workers = foraging_worker_criteria(snapshot)
        if workers:
            q["wild_plant_worker"] = {"type": "choice", "instructions": (
                "Choose who will cut the selected plants. A worker currently sowing with Growing priority 1 "
                "may keep sowing before Plant Cutting; weigh skill, health and competing jobs."),
                "criteria": workers}
    elif action == "harvest_food_crops_early" and dev.get("early_crop_options"):
        nearby_wild = sum(int(group.get("expected_yield") or 0)
                          for group in (dev.get("wild_plant_options") or {}).values())
        q["early_crop_type"] = {"type": "choice", "instructions": (
            f"Choose a crop only after weighing about {nearby_wild} food from mature nearby wild plants. "
            "Early cutting sacrifices the remaining rice growth; waiting risks hunger."), "criteria": {
            str(name): f"{group['count']} {group['label']} plants; average growth {group['average_growth']:.0%}; up to {group['expected_yield']} food now. Waiting yields more but food may run out."
            for name, group in dev["early_crop_options"].items()
        }}
        q["early_crop_batch"] = {"type": "choice", "instructions": "Choose how many of the most mature plants to cut now; the remainder keep growing.", "criteria": {
            "10": "Up to 10 plants: small immediate buffer, least future yield sacrificed.",
            "20": "Up to 20 plants: moderate food buffer and moderate yield loss.",
            "40": "Up to 40 plants: faster large supply, more immature plants cut.",
        }}
        workers = foraging_worker_criteria(snapshot)
        if workers:
            q["early_crop_worker"] = {"type": "choice", "instructions": (
                "Choose who will cut the selected crops now. Growing priority 1 can keep this worker sowing "
                "instead; compare the alternative worker's skill and current job."), "criteria": workers}
    elif action == "harvest_nearby_trees" and dev.get("tree_options"):
        q["tree_type"] = {"type": "choice", "instructions": "Choose a nearby mature tree species to cut for stalled construction. Up to eight trees will be marked now; avoid needless clear-cutting.", "criteria": {
            str(k): f"{v.get('label')}: {v.get('count')} nearby trees, up to {v.get('expected_yield')} wood in total" for k, v in dev["tree_options"].items()
        }}
    elif action == "floor_critical_room" and dev.get("critical_floor_options"):
        q["critical_floor_plan"] = {"type": "choice", "instructions": "Choose a real shared bedroom, kitchen or hospital and affordable floor.", "criteria": {
            str(k): f"{v.get('room_kind')} {v.get('room_id')}; cleanliness {v.get('cleanliness')}; {v.get('floor_def')} {v.get('cost')}" for k, v in dev["critical_floor_options"].items()
        }}
    elif action == "expand_home_area" and dev.get("fire_options"):
        q["fire_target"] = {"type": "choice", "instructions": "Choose one live fire near buildings to add to Home area for firefighters.",
                            "criteria": dict(dev["fire_options"])}
    elif action == "build_pathways" and dev.get("path_floor_options"):
        q["path_material"] = {"type": "choice", "instructions": "Choose fireproof outdoor flagstone; steel floors are intentionally unavailable.", "criteria": dict(dev["path_floor_options"])}
    elif action == "install_sculpture" and dev.get("sculpture_install_options"):
        q["sculpture_install_plan"] = {"type": "choice", "instructions": "Choose the finished sculpture and room.", "criteria": {
            str(k): f"{v.get('sculpture')} beauty {v.get('beauty')} -> {v.get('room_role')} room {v.get('room_id')}" for k, v in dev["sculpture_install_options"].items()
        }}
    elif action == "build_animal_barn" and dev.get("animal_barn_options"):
        opts = dev["animal_barn_options"]
        q["animal_barn_material"] = {"type": "choice", "instructions": "Choose the barn wall material.", "criteria": dict(opts.get("material_options") or {})}
        if opts.get("straw_available"):
            q["animal_barn_floor"] = {"type": "choice", "instructions": "Choose straw or bare ground considering filth, hay and fire.", "criteria": {"straw": "Low filth, consumes hay, highly flammable", "bare": "Free, nonflammable natural ground"}}
    elif action == "build_animal_pen" and dev.get("animal_pen_options"):
        opts = dev["animal_pen_options"]
        q["animal_pen_material"] = {"type": "choice", "instructions": "Choose fence, gate and marker material; preserve food and shelter supplies.", "criteria": dict(opts["materials"])}
        q["animal_pen_size"] = {"type": "choice", "instructions": (
            f"Choose the enclosed pasture size. Owned livestock without a pen: {opts.get('waiting_animals') or 'none'}; "
            f"nearby tameable wild candidates: {opts.get('optional_wildlife') or 'none'}. "
            "Wild animals are not waiting for housing and may never be tamed."
        ), "criteria": dict(opts["sizes"])}
    elif action == "build_battery_shelter" and dev.get("battery_shelter_options"):
        opts = dev["battery_shelter_options"]
        if len(opts.get("batteries") or []) > 1:
            q["battery_shelter_target"] = {"type": "choice", "instructions": "Choose which exposed battery to roof first; compare grid importance, rain and nearby building conflicts.", "criteria": {
                str(row["id"]): f"Battery at {row.get('position')}" for row in opts["batteries"] if row.get("id") is not None}}
        if len(opts.get("materials") or {}) > 1:
            q["battery_shelter_material"] = {"type": "choice", "instructions": "Choose a material for the small battery shed. Stone is fireproof but slow; wood is quicker and flammable; steel competes with power equipment.", "criteria": dict(opts["materials"])}
    elif action == "build_temple" and dev.get("temple_options"):
        opts = dev["temple_options"]
        q["temple_altar"] = {"type": "choice", "instructions": f"Choose the exact ritual focus for {opts.get('ideology')}.", "criteria": dict(opts.get("altars") or {})}
        q["temple_material"] = {"type": "choice", "instructions": "Choose an affordable, preferably fireproof temple material.", "criteria": dict(opts.get("materials") or {})}
    elif action == "connect_power_consumer" and dev.get("power_consumer_options"):
        q["power_consumer"] = {"type": "choice", "instructions":
            "Choose which disconnected powered building to wire first. Compare survival need, steel and route length.",
            "criteria": {key: f"{row['building']} at {row['position']}; {row['steel_cost']} steel for continuous conduit"
                         for key, row in dev["power_consumer_options"].items()}}
    elif action == "prioritize_construction_project" and dev.get("construction_project_options"):
        q["construction_project"] = {"type": "choice", "instructions": "Choose one exact unfinished project. Prefer survival-critical, nearly finished, and materially feasible work.", "criteria": {
            str(p["thing_id"]): f"{p.get('label')} ({p.get('kind')}) {float(p.get('percent_complete') or 0) * 100:.0f}% at {p.get('position')}; stuff {p.get('stuff_def_name')}; minimum Construction {p.get('minimum_construction_skill') or 0}; repeated low-skill work can botch" for p in dev["construction_project_options"]
        }}
        q["worker_pawn"] = {"type": "choice", "instructions": "Choose a builder using Construction, manipulation, movement, traits and injuries.", "criteria": worker_criteria(snapshot, "Construction")}
    elif action == "prioritize_thermal_project" and dev.get("thermal_project_options"):
        q["thermal_project"] = {"type": "choice", "instructions": "Choose an exact unfinished temperature-control blueprint in a threatened patient's room.", "criteria": {
            str(p["thing_id"]): f"{p.get('label')} ({p.get('kind')}) {float(p.get('percent_complete') or 0) * 100:.0f}% at {p.get('position')}; {p.get('threat')} patient"
            for p in dev["thermal_project_options"] if p.get("thing_id") is not None
        }}
        q["worker_pawn"] = {"type": "choice", "instructions": "Choose a mobile capable builder to finish the temperature control now; consider current injuries and other urgent duties.", "criteria": worker_criteria(snapshot, "Construction")}
    elif action in {"prioritize_construction", "prioritize_burial"}:
        skill = "Construction" if action == "prioritize_construction" else "Hauling"
        q["worker_pawn"] = {"type": "choice", "instructions": "Choose the exact colonist. Corpse-tolerant traits reduce mood cost; injuries and missing limbs reduce throughput.", "criteria": worker_criteria(snapshot, skill)}
    elif action == "choose_colony_doctrine" and dev.get("doctrine_context"):
        # Doctrine uses its own conditional cascade in choose_action: broad
        # domain -> exact direction -> compatible axes -> economy product.
        return {}
    return {name: question for name, question in q.items() if question.get("criteria")}


def choose_action(agent: Any, snapshot: dict[str, Any], candidates: list[str]) -> dict[str, Any]:
    state = fit_model_context(agent, model_decision_context(snapshot))
    raw_domain = None
    raw_family = None
    resources = (snapshot.get("map") or {}).get("resources") or {}
    people_count = len(snapshot.get("colonists") or [])
    food_runway = estimated_food_runway_days(resources, people_count)
    low_food = food_runway is not None and food_runway < 5

    def survival_tradeoff(name: str) -> str:
        if not low_food:
            return ""
        prefix = (f"Food runway about {food_runway} days: {int(resources.get('meals') or 0)} meals, "
                  f"{int(resources.get('raw_food') or 0)} raw food items for {people_count} people. ")
        development = snapshot.get("development") or {}
        wild_yield = sum(int(group.get("expected_yield") or 0)
                         for group in (development.get("wild_plant_options") or {}).values())
        early_yield = sum(int(group.get("expected_yield") or 0)
                          for group in (development.get("early_crop_options") or {}).values())
        notes = {
            "harvest_local_plants": (
                f"Mature wild plants offer about {wild_yield} food now; preserve growing rice."
                if wild_yield else "Gather mature edible wild plants, not timber."
            ),
            "harvest_food_crops_early": (
                f"Immature rice offers up to {early_yield} food but loses later yield; "
                f"mature wild plants offer about {wild_yield} without that loss."
                if wild_yield else "Harvest partly grown food now at lower final yield."
            ),
            "designate_safe_hunting": "Mark safe prey; shooting, butchering and cooking take time.",
            "build_butcher_spot": (
                f"Free and instant: {int(development.get('butchery_gap') or 0)} carcasses cannot become meat "
                "without a butcher spot and forever bill; this action supplies both. More hunting adds to the rotting pile."
            ),
            "prioritize_hunting": "Raise Hunting priority; prey still needs a designation.",
            "prioritize_plant_cutting": "Raise Plant Cutting priority; plants still need designation.",
            "prioritize_cooking": "Raise Cooking priority for delivered edible ingredients.",
            "rebalance_cooking": "Give a real cook time at the stove; compare taming delay with backup cook skill.",
            "harvest_nearby_trees": (
                "No spare wood to refuel the campfire/fueled stove; cut and haul logs for cooking, "
                "though raw food can be eaten meanwhile."
                if needs_cooking_fuel_reserve(snapshot)
                else "Wood cannot be eaten; may finish a stove or shelter."
            ),
            "start_stonecutting": "Make stone blocks, not food; costs worker time.",
            "configure_food_bills": (
                "Set the forever butchering bill to turn stored carcasses into raw meat."
                if any(table.get("thing_def") in {"ButcherSpot", "TableButcher"}
                       for table in development.get("work_tables") or [])
                else "Set cooking bills; only helps once ingredients arrive."
            ),
        }
        if name in notes:
            return notes[name] + " " + prefix
        if action_domain(name) == "construction" and name not in {"build_campfire"}:
            pending = len((snapshot.get("development") or {}).get("construction_projects") or [])
            return (f"{action_label(name, snapshot, 'en')}: adds to {pending} unfinished projects; "
                    + prefix + "Weigh shelter and food labor.")
        if name in {"prioritize_burial", "prioritize_cleaning", "develop_colonist_skill",
                    "select_research", "prioritize_construction_project"}:
            return (f"{action_label(name, snapshot, 'en')}: no immediate food; " + prefix
                    + "Weigh its benefit against gathering or cooking.")
        return ""

    def described_action(name: str, limit: int) -> str:
        tradeoff = survival_tradeoff(name)
        return tradeoff if tradeoff else action_description(name, snapshot)[:limit]

    player_preferences = snapshot.get("development", {}).get("user_preferences") or laya_preferences.load_preferences()
    considered = sorted(candidates, key=lambda name: laya_preferences.priority_for_action(name, player_preferences), reverse=True)
    domain_purposes = {
        "strategy": "research, doctrine, supplies, or wait",
        "work_orders": "assign colonists, harvest, hunt, or tame",
        "construction": "build shelter, beds, workshops, or zones",
        "care": "feed, rescue, heal, or house patients",
        "corpse_management": "haul, bury, or burn corpses",
        "economy_diplomacy": "produce, trade, or travel",
        "defense": "prepare defenses or fight threats",
    }
    if "unforbid_supplies" in candidates:
        locked = forbidden_supply_counts(snapshot)
        if locked["meals"] or locked["guns"]:
            domain_purposes["strategy"] = (
                f"owned but unusable: {locked['meals']} ready meals and {locked['guns']} guns; "
                "instant free unlock is available now"
            )
    if low_food:
        fuel_explanation = (
            "wood is not edible, but the campfire needs logs to cook stored raw food"
            if needs_cooking_fuel_reserve(snapshot)
            else "wood and stone cannot replenish food"
        )
        domain_purposes["work_orders"] = (
            ("urgent: food is empty; " if int(resources.get("food") or 0) <= 0 else "urgent: food is low; ")
            + f"about {food_runway} days of nutrition for {people_count} people, "
            f"{int(resources.get('raw_food') or 0)} raw food items; "
            f"edible plants, crops or safe hunting can replenish food; {fuel_explanation}"
        )
        domain_purposes["construction"] = (
            f"about {food_runway} days of food for {people_count} people; "
            f"{len((snapshot.get('development') or {}).get('construction_projects') or [])} unfinished projects. "
            "New construction consumes labor before food arrives."
        )
    elif ("harvest_nearby_trees" in candidates
          and not (snapshot.get("development") or {}).get("item_counts", {}).get("WoodLog", 0)
          and (snapshot.get("development") or {}).get("construction_projects")):
        domain_purposes["work_orders"] = (
            "urgent: wood is zero and shelter projects are unfinished; cut nearby mature trees "
            "and haul logs before cold weather reaches the open bedroom"
        )
    if "rescue_downed_colonist" in candidates or "tend_colonist" in candidates:
        domain_purposes["care"] = "urgent: directly rescue or tend an injured ally before blood loss; other work waits only if Laya chooses"
    if "build_passive_cooler" in candidates and (snapshot.get("development") or {}).get("heat_threat", {}).get("patients"):
        domain_purposes["care"] = "urgent: a patient has worsening heatstroke in a hot room; food and wound treatment alone cannot cool them"
    if ("prioritize_thermal_project" in candidates
            or any(action in candidates for action in ("build_room_campfire", "build_room_heater"))):
        domain_purposes["care"] = "urgent: temperature can kill a patient; choose a real heat source or finish the unfinished cooler/heater before other buildings"
    if "open_sealed_food_store" in candidates:
        domain_purposes["care"] = "urgent: stored meals are trapped behind a wall; open the freezer before colonists starve"
    elif "eat_available_meal" in candidates or "feed_hungry_colonist" in candidates:
        domain_purposes["care"] = "urgent: people are hungry; choose who eats or is fed before malnutrition worsens"
    if "build_research_bench" in candidates:
        domain_purposes["construction"] += "; first affordable research bench is available and research is blocked until it is built"
    if len(candidates) > 6:
        domains: dict[str, list[str]] = {}
        for name in considered:
            domains.setdefault(action_domain(name), []).append(name)
        if len(domains) > 1:
            def domain_criterion(domain: str, names: list[str]) -> str:
                priority = max(laya_preferences.priority_for_action(name, player_preferences) for name in names)
                # A broad label such as "care" is misleading when its only
                # available choices are future buildings, or "strategy" has
                # narrowed to waiting. Describe the actual feasible actions.
                if len(names) <= 3:
                    available = "; ".join(described_action(name, 105) for name in names)
                else:
                    available = (f"{domain_purposes.get(domain, domain)}; available now: "
                                 + ", ".join(action_label(name, snapshot, "en") for name in names[:4]))
                return f"priority {priority}/100; {len(names)} available; {available}"

            selected_domain, raw_domain = ask_laya_choice(agent, state, "colony_goal_domain",
                "Choose the most valuable area of attention now.", {
                    domain: domain_criterion(domain, names)
                    for domain, names in domains.items()
                })
            considered = domains[selected_domain]
    if len(considered) > 6:
        families: dict[str, list[str]] = {}
        for name in considered:
            families.setdefault(action_family(name), []).append(name)
        if len(families) > 1:
            selected_family, raw_family = ask_laya_choice(agent, state, "colony_goal_family",
                "Choose the work family to examine.", {
                    family: (f"priority {max(laya_preferences.priority_for_action(name, player_preferences) for name in names)}/100; "
                             + ("research cannot start until its first bench is built; "
                                if family == "building_project" and "build_research_bench" in names else "")
                             + ", ".join(described_action(name, 45).split(".", 1)[0][:75] for name in names[:2]))
                    for family, names in families.items()
                })
            considered = families[selected_family]

    raw_action = None
    if len(considered) == 1:
        choice = considered[0]
        action_answer = {"choice": choice, "confidence": 1.0, "probabilities": {choice: 1.0}}
        mode = "single_feasible_action"
    else:
        choice, raw_action = ask_laya_choice(agent, state, "colony_goal_action",
            "Choose the next feasible action. Weigh urgent needs, longer-term course, and player guidance.", {
            name: f"{described_action(name, 86)} Preference {laya_preferences.priority_for_action(name, player_preferences)}."
            for name in considered
        })
        action_answer = raw_action.get("answers", {}).get("colony_goal_action", {})
        mode = "hierarchical"

    parsed: dict[str, Any] = {}
    merged_answers = {"colony_goal_action": action_answer}
    if choice == "choose_colony_doctrine":
        cascade = strategy.choose_cascaded_doctrine(
            agent, state, snapshot.get("development", {}).get("doctrine_context") or {}
        )
        parsed["doctrine_selection"] = cascade["selection"]
        parsed["doctrine_retained"] = bool(cascade.get("retained"))
        parsed["doctrine_direction_audit"] = cascade["audit"]
        merged_answers.update(cascade["answers"])
        raw_details: dict[str, Any] | None = {"mode": "cascaded", "steps": cascade["raw_steps"]}
    elif choice == "select_research":
        selected, raw_details = ask_laya_choice(agent, state, "research_target",
            "Choose a live startable technology. Consider colony needs and chosen course.",
            snapshot.get("development", {}).get("live_research_options") or {})
        parsed["research_target"] = selected
        merged_answers.update(raw_details.get("answers", {}))
    elif choice == "build_research_bench":
        plans = snapshot.get("development", {}).get("research_bench_options") or {}
        steps = []
        if len(plans) > 1:
            name, bench_raw = ask_laya_choice(agent, state, "research_bench_def",
                "Choose a currently affordable research bench that can start the colony's first project.", {
                    def_name: f"{plan['label']}; cost {plan['cost_list']} + {plan['cost_stuff_count']} material"
                    for def_name, plan in plans.items()
                })
            steps.append(bench_raw)
            merged_answers.update(bench_raw.get("answers", {}))
        else:
            name = next(iter(plans))
        parsed["research_bench_def"] = name
        materials = plans[name].get("materials") or {}
        if len(materials) > 1:
            material, material_raw = ask_laya_choice(agent, state, "research_bench_material",
                "Choose a compatible bench material while preserving supplies needed for food and shelter.", materials)
            steps.append(material_raw)
            merged_answers.update(material_raw.get("answers", {}))
        else:
            material = next(iter(materials), "")
        parsed["research_bench_material"] = material
        raw_details = {"mode": "first_research_bench", "steps": steps}
    elif choice == "build_power":
        options = snapshot.get("development", {}).get("power_source_options") or {}
        context = options.get("demand") or {}
        source, raw = ask_laya_choice(agent, state, "power_source",
            "Choose a power plan. Compare every available generator with current consumers, "
            f"unpowered devices, generation and stored energy: {context}. "
            "Research and defer are valid decisions when a fuel generator would only serve a lamp.",
            options.get("choices") or {})
        parsed["power_source"] = source
        merged_answers.update(raw.get("answers", {}))
        raw_details = {"mode": "power_strategy", "steps": [raw]}
    elif choice == "build_catalog_building":
        groups = snapshot.get("development", {}).get("catalog_building_options") or {}
        category, category_raw = ask_laya_choice(agent, state, "catalog_building_category",
            "Choose a currently buildable category. The exact loaded buildings follow.", {
                name: f"{len(rows)} affordable buildings: {', '.join(list(rows)[:4])}"
                for name, rows in groups.items() if rows
            })
        plans = groups[category]
        name, building_raw = ask_laya_choice(agent, state, "catalog_building_def",
            "Choose one exact building; compare its use, existing count, cost and power need.", {
                def_name: (f"{plan['label']}; {plan['size_x']}x{plan['size_z']}; "
                           f"cost {plan['cost_list']} + {plan['cost_stuff_count']} material; "
                           f"already built {plan['existing_count']}; power {plan['requires_power']}")
                for def_name, plan in plans.items()
            })
        plan = plans[name]
        parsed.update(catalog_building_category=category, catalog_building_def=name)
        steps = [category_raw, building_raw]
        if plan["materials"]:
            material, material_raw = ask_laya_choice(agent, state, "catalog_building_material",
                "Choose a compatible material from current colony stock.", plan["materials"])
            parsed["catalog_building_material"] = material
            steps.append(material_raw)
        merged_answers.update(category_raw.get("answers", {}))
        merged_answers.update(building_raw.get("answers", {}))
        if len(steps) > 2:
            merged_answers.update(steps[-1].get("answers", {}))
        raw_details = {"mode": "live_catalog", "steps": steps}
    elif choice == "set_work_priority":
        work, work_raw = ask_laya_choice(agent, state, "work_type",
            "Choose a live profession whose priority should change now.",
            snapshot.get("development", {}).get("live_work_options") or {})
        workers = worker_criteria(snapshot, work)
        pawn, pawn_raw = ask_laya_choice(agent, state, "worker_pawn",
            f"Choose an eligible {work} worker using skills, passion, health and other duties.", workers)
        chosen_worker = next((c for c in snapshot.get("colonists", []) if str(c.get("id")) == pawn), {})
        current_priority = int((((chosen_worker.get("work_priorities") or {}).get(work) or {}).get("priority")) or 0)
        priorities = {str(level): f"Priority {level}; current {current_priority}; 1 is highest, 4 lowest"
                      for level in range(1, 5) if level != current_priority}
        level, level_raw = ask_laya_choice(agent, state, "work_priority",
            "Choose a sustainable priority for the next game day. Higher urgency is 1; 4 yields to other jobs. Repeatedly reversing the same assignment wastes work time.", priorities)
        parsed.update(work_type=work, worker_pawn=int(pawn), work_priority=int(level))
        merged_answers.update(work_raw.get("answers", {}))
        merged_answers.update(pawn_raw.get("answers", {}))
        merged_answers.update(level_raw.get("answers", {}))
        raw_details = {"steps": [work_raw, pawn_raw, level_raw]}
    else:
        detail_questions = subchoice_questions_for_action(choice, snapshot)
        if detail_questions:
            raw_details = {"answers": {}, "steps": []}
            for question_id, question in detail_questions.items():
                _, question_raw = ask_laya_choice(agent, state, question_id,
                    str(question["instructions"]), dict(question["criteria"]))
                raw_details["answers"].update(question_raw.get("answers", {}))
                raw_details["steps"].append(question_raw)
        else:
            raw_details = None
        if raw_details:
            merged_answers.update(raw_details.get("answers", {}))
            for question_id, question in detail_questions.items():
                selected = str(raw_details.get("answers", {}).get(question_id, {}).get("choice") or "")
                if selected not in question["criteria"]:
                    continue
                if question_id in {"tame_target", "wild_human_target", "hunt_target", "risky_hunt_target", "worker_pawn", "wild_plant_worker", "early_crop_worker", "construction_project", "thermal_project", "night_owl_pawn", "recreation_pawn", "medical_patient", "hungry_eater", "blocked_food_wall"}:
                    parsed[question_id] = int(selected)
                else:
                    parsed[question_id] = selected

    if choice == "consider_dangerous_hunt" and parsed.get("risky_hunt_target") is not None:
        animal = next((row for row in snapshot.get("development", {}).get("risky_hunt_options") or []
                       if int(row.get("id") or -1) == parsed["risky_hunt_target"]), {})
        fighter = snapshot.get("development", {}).get("fighter_context") or {}
        risk_state = {
            "colony": {"people": len(snapshot.get("colonists") or []), "food": fighter.get("food"),
                       "healthy_ranged": fighter.get("healthy_ranged"),
                       "serious_ranged_weapons": fighter.get("serious_ranged_weapons"),
                       "average_shooting": fighter.get("average_shooting"),
                       "injured_colonists": fighter.get("injured_colonists")},
            "target": {"animal": animal.get("def"), "combat_power": animal.get("combat_power"),
                       "revenge_chance": animal.get("harm_revenge_chance"), "meat": animal.get("meat_amount")},
            "risk": "A revenge can turn this into a herd attack. Hunters may be isolated; one downed gunner can leave the base defenseless.",
        }
        commitment, commitment_raw = ask_laya_choice(
            agent, risk_state, "dangerous_hunt_decision",
            "After comparing colony strength, food need and animal retaliation, decide whether to risk this hunt now.",
            {"defer": "Do not hunt this target now; preserve the fighters and use safer food sources or prepare first.",
             "proceed": "Accept the retaliation and possible colony-wipe risk; designate this exact animal for hunting."},
        )
        parsed["dangerous_hunt_decision"] = commitment
        merged_answers.update(commitment_raw.get("answers", {}))
        if raw_details is None:
            raw_details = {"answers": {}, "steps": []}
        raw_details.setdefault("steps", []).append(commitment_raw)

    if choice == "plan_architecture" and parsed.get("architecture_program"):
        program = str(parsed["architecture_program"])
        architecture_context = dict(snapshot.get("development", {}).get("architecture_context") or {})
        seed = int(architecture_context.get("variant_seed") or 0)
        material_options = architect.affordable_material_options(
            program, architecture_context,
            architecture_context.get("material_options") or structure_material_options(architecture_context.get("item_counts") or {}),
            seed=seed,
        )
        material, material_raw = ask_laya_choice(agent, state, "architecture_material",
            "Choose a wall material for this new building, considering fire, stock and the colony course.", material_options)
        parsed["architecture_material"] = material
        merged_answers.update(material_raw.get("answers", {}))
        architecture_context["material"] = material
        architecture_steps = [material_raw]
        if program != "defense":
            entry, entry_raw = ask_laya_choice(agent, state, "architecture_entry",
                "Choose where the entrance should face; the exact door offset varies with the saved design seed.", {
                    "south": "Approach from the south; allow access around the wall",
                    "east": "Approach from the east; allow access around the wall",
                    "north": "Approach from the north; allow access around the wall",
                    "west": "Approach from the west; allow access around the wall",
                })
            parsed["architecture_entry"] = entry
            merged_answers.update(entry_raw.get("answers", {}))
            architecture_context["entry_side"] = entry
            architecture_steps.append(entry_raw)
        variants = architect.affordable_variants(
            architect.generate_program_variants(program, architecture_context, seed=seed), architecture_context)
        considered_variants = variants
        if program == "residence" and variants:
            styles = {
                style: description for style, description in architect.HOUSE_STYLES.items()
                if any(row.get("style") == style for row in variants.values())
            }
            style, style_raw = ask_laya_choice(agent, state, "architecture_house_style",
                "Choose a house character; size, door and furniture proposals follow.", styles)
            parsed["architecture_house_style"] = style
            considered_variants = {key: row for key, row in variants.items() if row.get("style") == style}
            merged_answers.update(style_raw.get("answers", {}))
            architecture_steps.append(style_raw)
        if considered_variants:
            variant, variant_raw = ask_laya_choice(agent, state, "architecture_variant",
                "Choose the generated layout using room size, furniture, light and known material cost.",
                {key: str(row.get("summary") or key) for key, row in considered_variants.items()})
            parsed["architecture_variant"] = variant
            merged_answers.update(variant_raw.get("answers", {}))
            architecture_steps.append(variant_raw)
        raw_architecture = {"steps": architecture_steps, "seed": seed}
    else:
        raw_architecture = None

    aliases = {"trade_purchase_plan": "trade_purchase"}
    for source, target in aliases.items():
        if source in parsed: parsed[target] = parsed.pop(source)
    raw = {"mode": mode, "visible_state": state, "domain": raw_domain, "family": raw_family,
           "action": raw_action, "details": raw_details, "architecture": raw_architecture,
           "answers": merged_answers}
    return {"choice": choice, "confidence": bridge.first_number(action_answer.get("confidence"), 1.0), **parsed, "raw": raw}


def merge_decision_details(details: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Pass every validated nested choice through to action execution."""
    return {**details, **{key: value for key, value in decision.items()
                        if key not in {"choice", "confidence", "raw"} and value is not None}}


def probability_bars(
    probabilities: dict[str, Any],
    labels: dict[str, str],
    selected: str,
    limit: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        ((str(name), bridge.first_number(value)) for name, value in probabilities.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    visible = ranked[:limit]
    if selected in probabilities and selected not in {name for name, _ in visible}:
        visible = (visible[:-1] if visible else []) + [(selected, bridge.first_number(probabilities[selected]))]
    return [
        {
            "label": (str(labels.get(name) or name)[:43] + "…"
                      if len(str(labels.get(name) or name)) > 44
                      else str(labels.get(name) or name)),
            "value": max(0.0, min(1.0, value)),
            "selected": name == selected,
        }
        for name, value in visible
    ]


def overlay_language(client: bridge.RimApiClient | None) -> str:
    """Use RimWorld's language rather than the separate desktop GUI setting."""
    try:
        game_language = str((client.get("/api/v1/game/settings") or {}).get("language") or "") if client else ""
    except (bridge.RimApiError, AttributeError, TypeError):
        game_language = ""
    return "ru" if game_language.lower().startswith("russian") else "en"


_CYRILLIC_LATIN = str.maketrans(dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ("a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"),
)))
_CYRILLIC_LATIN.update({ord(char.upper()): value.capitalize() for char, value in zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ("a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"),
)})


def show_overlay(
    client: bridge.RimApiClient,
    *,
    compact_lines: list[str],
    full_lines: list[str],
    bars: list[dict[str, Any]] | None = None,
    duration: float = 12.0,
    color: str = "#E8F4FF",
) -> None:
    # The stream observer owns the 20-second death memorial. Do not replace it
    # with a fresh Laya choice HUD (or the disabled-HUD clear command).
    try:
        observer_status = laya_preferences.preferences_path().parent / "logs" / "observer-status.json"
        spotlight = json.loads(observer_status.read_text(encoding="utf-8-sig"))
        if (spotlight.get("state") == "running"
                and float(spotlight.get("death_overlay_until") or 0) > time.time()):
            return
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    overlay = laya_preferences.load_preferences().get("overlay") or {}
    if not overlay.get("enabled", True):
        client.post(
            "/api/v1/ui/announce",
            body={"text": "", "duration": 0.0, "color": color, "scale": 1.0, "panel": True, "compact": True, "bars": []},
        )
        return
    compact = bool(overlay.get("compact", True))
    max_options = max(3, min(8, int(overlay.get("max_options", 5))))
    english = overlay_language(client) == "en"
    displayed_lines = compact_lines if compact else full_lines
    displayed_text = "\n".join(displayed_lines)
    displayed_bars = list(bars or [])[:max_options]
    if english:
        # Modded pawn/incident names can still be Cyrillic on an English UI.
        displayed_text = displayed_text.translate(_CYRILLIC_LATIN)
        displayed_bars = [
            {**bar, "label": str(bar.get("label") or "").translate(_CYRILLIC_LATIN)}
            for bar in displayed_bars
        ]
    client.post(
        "/api/v1/ui/announce",
        body={
            "text": displayed_text,
            "duration": duration,
            "color": color,
            "scale": 1.0,
            "panel": True,
            "compact": compact,
            "bars": displayed_bars,
        },
    )


def publish_overlay(
    client: bridge.RimApiClient,
    snapshot: dict[str, Any],
    candidates: list[str],
    decision: dict[str, Any],
) -> None:
    language = overlay_language(client)
    english = language == "en"
    probabilities: dict[str, float] = {}
    raw = decision.get("raw") or {}
    try:
        probabilities = {
            str(name): float(value)
            for name, value in raw["answers"]["colony_goal_action"].get("probabilities", {}).items()
        }
    except (KeyError, TypeError, ValueError):
        pass
    choice = str(decision["choice"])
    bar_choice = choice
    stage_labels = ({
        "strategy": "Strategy", "work_orders": "Work", "construction": "Construction",
        "care": "Care", "corpse_management": "Corpses", "economy_diplomacy": "Trade",
        "defense": "Defense",
    } if english else {
        "strategy": "Стратегия", "work_orders": "Работа", "construction": "Строительство",
        "care": "Забота", "corpse_management": "Тела", "economy_diplomacy": "Торговля",
        "defense": "Оборона",
    })
    # A domain or family can narrow to one feasible action without another
    # model question. Never present that structural singleton as 100% model
    # certainty; display the latest genuine multi-option answer instead.
    if len(probabilities) < 2:
        probabilities = {}
        for stage, question_id in (("family", "colony_goal_family"), ("domain", "colony_goal_domain")):
            answer = ((raw.get(stage) or {}).get("answers") or {}).get(question_id) or {}
            options = answer.get("probabilities") or {}
            if len(options) >= 2:
                probabilities = {str(name): float(value) for name, value in options.items()}
                bar_choice = str(answer.get("choice") or "")
                break

    def display_label(name: str) -> str:
        return stage_labels.get(name) or action_label(name, snapshot, language)

    ordered = sorted(probabilities, key=lambda name: probabilities[name], reverse=True)
    option_lines = []
    for name in ordered:
        marker = ">" if name == bar_choice else " "
        probability = probabilities.get(name)
        score = f" {probability * 100:4.1f}%" if probability is not None else ""
        option_lines.append(f"{marker} {display_label(name)}{score}")
    for question_id, answer in (raw.get("answers") or {}).items():
        if question_id == "colony_goal_action" or not isinstance(answer, dict):
            continue
        sub_probabilities = answer.get("probabilities") or {}
        selected = str(answer.get("choice") or "")
        option_lines.append("")
        option_lines.append(f"{question_id}:")
        for name, value in sorted(sub_probabilities.items(), key=lambda item: float(item[1]), reverse=True)[:8]:
            option_lines.append(f"{'> ' if str(name) == selected else '  '}{name} {float(value) * 100:.1f}%")
    resources = snapshot["map"]["resources"]
    lowest_food = min((float(c.get("hunger") or 0.0) for c in snapshot["colonists"]), default=0.0)
    jobs = ", ".join(f"{c['name']}: {c['current_job']}" for c in snapshot["colonists"][:4])
    animal_status = ", ".join(
        f"{a['name']} {float(a['health']) * 100:.0f}%"
        for a in snapshot.get("animals", [])[:3]
    ) or ("none" if english else "нет")
    corpses = snapshot.get("development", {}).get("corpses", [])
    doctrine_lines: list[str] = []
    doctrine = decision.get("doctrine_selection") or snapshot.get("development", {}).get("doctrine") or {}
    if doctrine:
        if english:
            doctrine_lines = [
                "",
                f"Direction: {str(doctrine.get('primary_direction') or 'unset').replace('_', ' ')} | endgame: {str(doctrine.get('endgame') or 'unset').replace('_', ' ')}",
                f"Economy: {str(doctrine.get('economy') or 'unset').replace('_', ' ')} | technology: {str(doctrine.get('technology') or 'unset').replace('_', ' ')}",
                f"Defense: {str(doctrine.get('military') or 'unset').replace('_', ' ')} | society: {str(doctrine.get('society') or 'unset').replace('_', ' ')}",
            ]
        else:
            labels = doctrine.get("labels") or strategy.doctrine_labels(doctrine)
            doctrine_lines = [
                "",
                f"Курс: {labels.get('primary_direction', '—')} | финал: {labels.get('endgame', '—')}",
                f"Экономика: {labels.get('economy', '—')} | технологии: {labels.get('technology', '—')}",
                f"Оборона: {labels.get('military', '—')} | общество: {labels.get('society', '—')}",
            ]
    english_text = "\n".join(
        [
            "LAYA — COLONY DIRECTOR",
            f"Food: {resources.get('food', 0)} | lowest satiety: {lowest_food * 100:.0f}% | enemies: {snapshot['map']['enemies']}",
            f"Current jobs: {jobs}",
            f"Animals: {animal_status}",
            f"Unburied corpses: {len(corpses)} | colony wealth: {snapshot['development'].get('trade_value', 0):.0f}",
            "",
            "Options this cycle:",
            *option_lines,
            *doctrine_lines,
            "",
            f"Chosen: {action_label(choice, snapshot, language)}",
        ]
    )
    russian_text = "\n".join(
        [
            "LAYA — автономный директор",
            f"Еда: {resources.get('food', 0)} | мин. сытость: {lowest_food * 100:.0f}% | враги: {snapshot['map']['enemies']}",
            f"Сейчас: {jobs}",
            f"Животные: {animal_status}",
            f"Незахоронённые трупы: {len(corpses)} | стоимость имущества: {snapshot['development'].get('trade_value', 0):.0f}",
            "",
            "Варианты этого цикла:",
            *option_lines,
            *doctrine_lines,
            "",
            f"Выбрано: {action_label(choice, snapshot, language)}",
        ]
    )
    bars = probability_bars(
        probabilities,
        {name: display_label(name) for name in probabilities},
        bar_choice,
        8,
    )
    show_overlay(
        client,
        compact_lines=(["LAYA — COLONY DIRECTOR",
            f"Food: {resources.get('food', 0)} · enemies: {snapshot['map']['enemies']}",
            f"Chosen: {action_label(choice, snapshot, language)}"] if english else [
            "LAYA — автономный директор",
            f"Еда: {resources.get('food', 0)} · враги: {snapshot['map']['enemies']}",
            f"Выбрано: {action_label(choice, snapshot, language)}",
        ]),
        full_lines=(english_text if english else russian_text).splitlines(),
        bars=bars,
        duration=12.0,
        color="#E8F4FF",
    )


def publish_combat_overlay(client: bridge.RimApiClient, record: dict[str, Any], repeated: bool = False) -> None:
    english = overlay_language(client) == "en"
    snapshot = record["snapshot"]
    decision = record["decision"]
    choice = str(decision.get("choice") or "hold_and_observe")
    probabilities: dict[str, float] = {}
    try:
        answer = next(iter((decision.get("raw") or {})["answers"].values()))
        probabilities = {str(k): float(v) for k, v in answer.get("probabilities", {}).items()}
    except (KeyError, TypeError, ValueError, StopIteration):
        pass
    lines = [
        "LAYA — COMBAT" if english else "LAYA — БОЕВОЙ РЕЖИМ",
        (f"Enemies: {len(snapshot['combat']['hostiles'])}" if english
         else f"Противники: {len(snapshot['combat']['hostiles'])}"),
        "",
        "Options:" if english else "Варианты:",
    ]
    for name, value in sorted(probabilities.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"{'> ' if name == choice else '  '}{name} {value * 100:.1f}%")
    lines.extend(["", (f"Order: {record['action']['description']}" if english
                       else f"Приказ: {record['action']['description']}")])
    if repeated:
        lines.append("Order still in progress; not sent again." if english else "Приказ уже выполняется; повторно не отправлен.")
    show_overlay(
        client,
        compact_lines=(["LAYA — COMBAT", f"Enemies: {len(snapshot['combat']['hostiles'])}",
                        f"Order: {record['action']['description']}",
                        *(["Order in progress"] if repeated else [])] if english else [
            "LAYA — БОЕВОЙ РЕЖИМ", f"Противники: {len(snapshot['combat']['hostiles'])}",
            f"Приказ: {record['action']['description']}",
            *(["Приказ уже выполняется"] if repeated else []),
        ]),
        full_lines=lines,
        bars=probability_bars(probabilities, {name: name for name in probabilities}, choice, 8),
        duration=12.0,
        color="#FFD7D7",
    )


def post_blueprint(client: bridge.RimApiClient, map_id: int, anchor: dict[str, int], layout: dict[str, Any], dx: int = 0, dz: int = 0) -> Any:
    return client.post(
        "/api/v1/builder/blueprint",
        body={
            "map_id": map_id,
            "position": position(anchor["x"] + dx, anchor["z"] + dz),
            "blueprint": layout,
            "clear_obstacles": False,
        },
    )


def place_checked_building(client: bridge.RimApiClient, map_id: int, plan: dict[str, Any],
                           near: dict[str, int], stuff: str | None = None, *,
                           radius: int = 80, expand_search: bool = True,
                           snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Place one exact catalog def only at a site approved by RimWorld."""
    name = str(plan["def_name"])
    lookup = {"map_id": map_id, "def_name": name, "stuff_def_name": stuff,
              "near": position(int(near["x"]), int(near["z"])), "radius": radius,
              "limit": 24 if snapshot is not None else 8}
    try:
        site_result = client.post("/api/v1/builder/site-options", body=lookup)
        if expand_search and not site_result.get("sites"):
            lookup["radius"] = 250
            site_result = client.post("/api/v1/builder/site-options", body=lookup)
        sites = site_result.get("sites") or []
        if not sites:
            return {"applied": False, "building": name,
                    "reason": site_result.get("reason") or "No valid site found"}
        errors = []
        for site in sites:
            target = site.get("position") or {}
            x, z = target.get("x"), target.get("z")
            if x is None or z is None:
                continue
            if snapshot is not None and bridge.combat_planner.errand_exposed(snapshot, target):
                continue
            rotation = int(site.get("rotation") or 0)
            try:
                terrain = plan.get("construction_kind") == "terrain"
                layout = blueprint(
                    [] if terrain else [building(name, 0, 0, stuff=stuff, rotation=rotation)],
                    int(plan.get("size_x") or 1), int(plan.get("size_z") or 1),
                    [floor(name, 0, 0)] if terrain else [],
                )
                response = post_blueprint(client, map_id, position(int(x), int(z)), layout)
                projects_raw = client.get("/api/v1/builder/projects", map_id=map_id)
                projects = projects_raw.get("projects") or [] if isinstance(projects_raw, dict) else []
                verified = any(row.get("def_name") == name
                               and (row.get("position") or {}).get("x") == int(x)
                               and (row.get("position") or {}).get("z") == int(z)
                               for row in projects)
                kind = "blueprint"
                if not verified:
                    built = client.get("/api/v1/map/buildings", map_id=map_id)
                    verified = any(row.get("def") == name
                                   and (row.get("position") or {}).get("x") == int(x)
                                   and (row.get("position") or {}).get("z") == int(z)
                                   for row in built if isinstance(row, dict))
                    kind = "building"
                if verified:
                    return {"applied": True, "building": name, "site": position(int(x), int(z)),
                            "rotation": rotation, "kind": kind, "response": response}
                errors.append(f"{x},{z}: API accepted the request but no blueprint or building appeared")
            except bridge.RimApiError as error:
                errors.append(f"{x},{z}: {error}")
        return {"applied": False, "building": name,
                "reason": "; ".join(errors[:3]) or "No safe valid site found"}
    except bridge.RimApiError as error:
        return {"applied": False, "building": name, "reason": str(error)}


RESEARCH_PROTECTED_WORK = frozenset({
    "Research", "Firefighter", "Patient", "PatientBedRest", "Doctor", "BasicWorker", "Warden", "Childcare",
})


def research_routine_priority_one(pawn: dict[str, Any]) -> list[str]:
    return [work for work, setting in (pawn.get("work_priorities") or {}).items()
            if work not in RESEARCH_PROTECTED_WORK and isinstance(setting, dict)
            and not setting.get("disabled") and int(setting.get("priority") or 0) == 1]


def researcher_is_dedicated(snapshot: dict[str, Any]) -> bool:
    return any(
        not pawn.get("downed") and not pawn.get("in_mental_state")
        and not ((pawn.get("work_priorities") or {}).get("Research") or {}).get("disabled")
        and int(((pawn.get("work_priorities") or {}).get("Research") or {}).get("priority") or 0) == 1
        and not research_routine_priority_one(pawn)
        for pawn in snapshot.get("colonists") or []
    )


def research_staffing_plan(snapshot: dict[str, Any]) -> tuple[dict[str, Any], list[str]] | None:
    """Prefer a spare researcher over the colony's only cook or grower."""
    pawns = snapshot.get("colonists") or []
    food = int(((snapshot.get("map") or {}).get("resources") or {}).get("food") or 0)
    meals = int(((snapshot.get("map") or {}).get("resources") or {}).get("meals") or 0)
    workers = [pawn for pawn in pawns if not pawn.get("downed") and not pawn.get("in_mental_state")
               and not ((pawn.get("work_priorities") or {}).get("Research") or {}).get("disabled")
               and "Research" in (pawn.get("work_priorities") or {})]
    if not workers:
        return None
    cooks = [pawn for pawn in pawns if int(((pawn.get("work_priorities") or {}).get("Cooking") or {}).get("priority") or 0) > 0]
    growers = [pawn for pawn in pawns if int(((pawn.get("work_priorities") or {}).get("Growing") or {}).get("priority") or 0) > 0]

    def score(pawn: dict[str, Any]) -> float:
        priorities = pawn.get("work_priorities") or {}
        intellect = (pawn.get("skills") or {}).get("Intellectual") or {}
        value = float(intellect.get("level") or 0) + 2 * float(intellect.get("passion") or 0)
        value -= 0.4 * len(research_routine_priority_one(pawn))
        if len(cooks) == 1 and cooks[0].get("id") == pawn.get("id") and meals < max(18, 8 * len(pawns)):
            value -= 20
        if len(growers) == 1 and growers[0].get("id") == pawn.get("id") and food < 50 * len(pawns):
            value -= 10
        return value

    worker = max(workers, key=lambda pawn: (score(pawn), -int(pawn.get("id") or 0)))
    return worker, research_routine_priority_one(worker)


def dedicate_researcher(client: bridge.RimApiClient, snapshot: dict[str, Any]) -> dict[str, Any]:
    plan = research_staffing_plan(snapshot)
    if plan is None:
        return {"applied": False, "reason": "No available researcher"}
    worker, defer_jobs = plan
    changes = []
    research_priority = int(((worker.get("work_priorities") or {}).get("Research") or {}).get("priority") or 0)
    if research_priority != 1:
        changes.append(("Research", 1, client.post("/api/v1/colonist/work-priority", body={
            "id": worker["id"], "work": "Research", "priority": 1,
        })))
    for work in defer_jobs:
        changes.append((work, 2, client.post("/api/v1/colonist/work-priority", body={
            "id": worker["id"], "work": work, "priority": 2,
        })))
    return {"applied": bool(changes), "colonist": worker.get("name"), "pawn_id": worker.get("id"),
            "reserved_for": "Research", "adjustments": [
                {"work": work, "priority": priority, "response": response}
                for work, priority, response in changes]}


def prioritize(client: bridge.RimApiClient, snapshot: dict[str, Any], work: str, pawn_id: int | None = None,
               *, avoid_ids: set[int] | None = None) -> Any:
    target = next(
        (p for p in snapshot["colonists"] if pawn_id is not None and int(p.get("id", -1)) == int(pawn_id)),
        None,
    )
    if target is None and pawn_id is None and avoid_ids:
        alternatives = [pawn for pawn in snapshot["colonists"]
                        if int(pawn.get("id") or 0) not in avoid_ids]
        target = bridge.choose_worker(alternatives, work)
    target = target or bridge.choose_worker(snapshot["colonists"], work)
    if target is None:
        return {"applied": False, "reason": f"No eligible colonist for {work}"}
    response = client.post(
        "/api/v1/colonist/work-priority",
        body={"id": target["id"], "work": work, "priority": 1},
    )
    return {"applied": True, "colonist": target["name"], "work": work, "response": response}


def free_cold_shelter_builder(client: bridge.RimApiClient, snapshot: dict[str, Any],
                             pawn_id: int) -> dict[str, Any] | None:
    """Let a builder finish heat while non-bleeding hypothermia patients wait."""
    focus = (snapshot.get("development") or {}).get("cold_start_focus")
    if focus not in {"assign_builder", "finish_shell", "finish_heat"}:
        return None
    if any(bridge.first_number(pawn.get("bleeding_rate")) >= 0.05
           for pawn in snapshot.get("colonists") or []):
        return None
    builder = next((pawn for pawn in snapshot.get("colonists") or []
                    if int(pawn.get("id") or 0) == int(pawn_id)), None)
    doctor = ((builder or {}).get("work_priorities") or {}).get("Doctor") or {}
    if doctor.get("disabled") or int(doctor.get("priority") or 0) != 1:
        return None
    response = client.post("/api/v1/colonist/work-priority", body={
        "id": int(pawn_id), "work": "Doctor", "priority": 2,
    })
    return {"doctor_priority": 2, "builder_id": int(pawn_id), "response": response}


def food_bills_need_configuration(client: bridge.RimApiClient | None,
                                  tables: list[dict[str, Any]]) -> bool:
    """Offer the recipe action only when a real food table lacks its bill."""
    recipes_by_table = {
        "Campfire": "CookMealSimple", "FueledStove": "CookMealSimple",
        "ElectricStove": "CookMealSimple", "TableButcher": "ButcherCorpseFlesh",
        "ButcherSpot": "ButcherCorpseFlesh",
    }
    for table in tables:
        required = recipes_by_table.get(str(table.get("thing_def") or ""))
        if not required:
            continue
        if int(table.get("bills_count") or 0) <= 0:
            return True
        if client is None or table.get("id") is None:
            continue
        try:
            bills = client.get("/api/v1/buildings/bills", building_id=int(table["id"]))
        except bridge.RimApiError:
            return True  # Unknown bill state: keep the repair available.
        if isinstance(bills, list) and not any(
            isinstance(row, dict) and str(row.get("recipe_def_name") or "") == required
            for row in bills
        ):
            return True
    return False


def configure_food_bills(client: bridge.RimApiClient, tables: list[dict[str, Any]]) -> dict[str, Any]:
    responses = []
    for table in tables:
        def_name = str(table.get("thing_def") or "")
        table_id = int(table.get("id"))
        try:
            bills = client.get("/api/v1/buildings/bills", building_id=table_id)
        except bridge.RimApiError:
            continue
        recipes = {str(row.get("recipe_def_name")) for row in bills if isinstance(row, dict)}
        if def_name in {"Campfire", "FueledStove", "ElectricStove"} and "CookMealSimple" not in recipes:
            responses.append(client.post(
                "/api/v1/buildings/bills/add",
                query={"building_id": table_id},
                body={"recipe_def_name": "CookMealSimple", "repeat_mode": "TargetCount", "target_count": 20, "pause_when_satisfied": True, "unpause_when_you_have": 8},
            ))
        if def_name in {"TableButcher", "ButcherSpot"} and "ButcherCorpseFlesh" not in recipes:
            responses.append(client.post(
                "/api/v1/buildings/bills/add",
                query={"building_id": table_id},
                body={"recipe_def_name": "ButcherCorpseFlesh", "repeat_mode": "Forever"},
            ))
    return {"applied": bool(responses), "responses": responses}


def ensure_bill(client: bridge.RimApiClient, table: dict[str, Any], recipe: str, target_count: int = 20) -> Any:
    table_id = int(table.get("id"))
    bills = client.get("/api/v1/buildings/bills", building_id=table_id)
    if any(str(row.get("recipe_def_name")) == recipe for row in bills if isinstance(row, dict)):
        return {"applied": False, "reason": f"{recipe} already configured"}
    return client.post(
        "/api/v1/buildings/bills/add",
        query={"building_id": table_id},
        body={
            "recipe_def_name": recipe,
            "repeat_mode": "TargetCount",
            "target_count": target_count,
            "pause_when_satisfied": True,
            "unpause_when_you_have": max(1, target_count // 3),
        },
    )


def researched_travel_ration_recipe(client: bridge.RimApiClient, table: dict[str, Any]) -> str | None:
    """Use the live table catalogue; RimWorld calls pemmican Make_Pemmican."""
    recipes = client.get("/api/v1/buildings/recipes", building_id=int(table["id"]), only_researched=True)
    available = {str(row.get("def_name") or "") for row in (recipes or []) if isinstance(row, dict)}
    return next((name for name in ("Make_Pemmican", "Make_PemmicanBulk", "CookMealSurvivalPack")
                 if name in available), None)


def stonecutting_recipe(client: bridge.RimApiClient, table: dict[str, Any], stone_type: str) -> str:
    """Resolve the chosen chunk against recipes the completed table can use."""
    block_def = "Blocks" + stone_type.removeprefix("Chunk")
    recipes = client.get("/api/v1/buildings/recipes", building_id=int(table["id"]))
    for recipe in recipes if isinstance(recipes, list) else []:
        if not isinstance(recipe, dict):
            continue
        if any(isinstance(product, dict) and product.get("thing_def") == block_def
               for product in recipe.get("products") or []):
            name = str(recipe.get("def_name") or "")
            if name:
                return name
    raise bridge.RimApiError(f"No available stonecutting recipe produces {block_def}")


def select_research_if_available(client: bridge.RimApiClient, name: str) -> dict[str, Any]:
    project = client.get("/api/v1/research/project", name=name)
    if not project.get("can_start_now") or project.get("player_has_any_appropriate_research_bench") is False:
        return {"applied": False, "reason": f"{name} needs finished prerequisites and an appropriate completed research bench"}
    return client.post("/api/v1/research/target", query={"name": name, "force": False})


def execute_action(client: bridge.RimApiClient, snapshot: dict[str, Any], map_state: dict[str, Any], choice: str, details: dict[str, Any]) -> Any:
    map_id = snapshot["map"]["id"]
    tick = int(snapshot["game"].get("tick") or 0)
    anchor = map_state["anchor"]
    issued = map_state.setdefault("issued", {})
    dev = snapshot.get("development") or {}
    active_research = str((dev.get("current_research") or {}).get("name") or "none").lower() != "none"
    reserved_researcher_id = int(map_state.get("reserved_researcher_id") or 0)
    routine_avoid = ({reserved_researcher_id} if active_research and reserved_researcher_id
                     and any(int(pawn.get("id") or 0) == reserved_researcher_id and not pawn.get("downed")
                             for pawn in snapshot.get("colonists") or []) else set())

    if choice == "build_research_bench":
        name = str(details.get("research_bench_def") or "")
        plan = (details.get("research_bench_options") or {}).get(name)
        if not plan:
            return {"applied": False, "reason": "Laya did not select a live, affordable research bench"}
        stuff = str(details.get("research_bench_material") or "")
        if plan.get("materials") and stuff not in plan["materials"]:
            return {"applied": False, "reason": "Selected research bench material is unavailable or incompatible"}
        if not plan.get("materials") and stuff:
            return {"applied": False, "reason": "This research bench does not use a material"}
        result = place_checked_building(client, map_id, plan, anchor, stuff or None)
        if result.get("applied"):
            issued["research_bench"] = tick
            issued[f"research_bench:{name}"] = tick
        return result

    if choice == "build_catalog_building":
        category = str(details.get("catalog_building_category") or "")
        name = str(details.get("catalog_building_def") or "")
        plan = ((details.get("catalog_building_options") or {}).get(category) or {}).get(name)
        if not plan:
            return {"applied": False, "reason": "Laya did not select a live, affordable building definition"}
        stuff = str(details.get("catalog_building_material") or "")
        if plan.get("materials") and stuff not in plan["materials"]:
            return {"applied": False, "reason": "Selected construction material is unavailable or incompatible"}
        if not plan.get("materials") and stuff:
            return {"applied": False, "reason": "This building does not use a construction material"}
        near = anchor
        if name in {"TableButcher", "ButcherSpot"}:
            carcasses = [row.get("position") or {} for row in corpse_rows(snapshot, "CorpsesAnimal")]
            carcasses = [row for row in carcasses if row.get("x") is not None and row.get("z") is not None]
            if carcasses:
                near = position(
                    sorted(int(row["x"]) for row in carcasses)[len(carcasses) // 2],
                    sorted(int(row["z"]) for row in carcasses)[len(carcasses) // 2],
                )
        result = place_checked_building(client, map_id, plan, near, stuff or None)
        if not result.get("applied"):
            return result
        issued["catalog_building"] = tick
        issued[f"catalog_building:{name}"] = tick
        map_state.setdefault("catalog_buildings", []).append({
            "def_name": name, "stuff": stuff or None, "site": result["site"], "issued_tick": tick,
        })
        return result

    if choice == "plan_architecture":
        program = str(details.get("architecture_program") or "")
        variant_id = str(details.get("architecture_variant") or "")
        context = dict(details.get("architecture_context") or {})
        material = str(details.get("architecture_material") or "")
        entry = str(details.get("architecture_entry") or "")
        if material not in (context.get("material_options") or structure_material_options(context.get("item_counts") or {})):
            return {"applied": False, "reason": "Selected wall material is not available in current stock"}
        if entry and entry not in {"south", "east", "north", "west"}:
            return {"applied": False, "reason": "Selected entrance side is invalid"}
        context["material"] = material
        context["entry_side"] = entry
        variants = architect.affordable_variants(architect.generate_program_variants(
            program, context, seed=int(context.get("variant_seed") or 0)
        ), context) if program else {}
        selected = variants.get(variant_id)
        if not selected:
            return {"applied": False, "reason": "Laya did not select a valid generated architecture variant"}
        sequence = int(map_state.get("architecture_sequence") or 0)
        # Grow in a compact ring around the starter house. The previous fixed
        # +32/-18 offset sent the first kitchen beside a sealed Ancient Danger.
        offsets = ((10, 0), (0, 10), (-10, 0), (0, -10),
                   (18, 8), (-8, 18), (18, -8), (-8, -18))
        dx, dz = offsets[sequence % len(offsets)]
        ring = sequence // len(offsets)
        desired = {"x": int(anchor["x"]) + dx + (4 * ring if dx >= 0 else -4 * ring),
                   "z": int(anchor["z"]) + dz + (4 * ring if dz >= 0 else -4 * ring)}
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        origin = find_terrain_rect(
            terrain,
            desired,
            int(selected["width"]),
            int(selected["height"]),
            {"Soil", "SoilRich", "Gravel", "Sand"},
            radius=16,
            blocked=architecture_occupied_cells(snapshot.get("development") or {}, map_state),
            clearance=1,
        )
        if origin is None:
            issued["architecture_site_search"] = tick
            return {"applied": False, "reason": "No dry, unoccupied site with access clearance for this building"}
        response = client.post("/api/v1/builder/blueprint", body={
            "map_id": map_id,
            "position": position(origin["x"], origin["z"]),
            "blueprint": selected["layout"],
            "clear_obstacles": False,
        })
        project = {
            "program": program,
            "variant": variant_id,
            "style": selected.get("style"),
            "material": material,
            "entry": entry or "generated",
            "estimated_stuff_cost": selected.get("estimated_stuff_cost"),
            "origin": origin,
            "width": int(selected["width"]),
            "height": int(selected["height"]),
            "issued_tick": tick,
        }
        map_state.setdefault("architecture_projects", []).append(project)
        map_state["architecture_sequence"] = sequence + 1
        issued["architecture_project"] = tick
        issued[f"architecture:{program}:{sequence}"] = tick
        return {
            "applied": True,
            "project": project,
            "summary": selected.get("summary"),
            "blueprint": response,
            "construction": prioritize(client, snapshot, "Construction"),
        }

    if choice == "improve_room_lighting":
        key = str(details.get("lighting_room") or "")
        room = (details.get("dark_room_options") or {}).get(key)
        if not room or not room.get("placement_cells"):
            return {"applied": False, "reason": "No verified empty placement cell remains in the chosen dark room"}
        target = room["placement_cells"][0]
        powered = "Electricity" in set(map(str, snapshot.get("development", {}).get("finished_research") or []))
        light_def = "StandingLamp" if powered else "TorchLamp"
        response = client.post("/api/v1/builder/blueprint", body={
            "map_id": map_id,
            "position": position(int(target["x"]), int(target["z"])),
            "blueprint": architect.blueprint([architect.building(light_def, 0, 0)], 1, 1),
            "clear_obstacles": False,
        })
        issued["room_lighting"] = tick
        issued[f"room_lighting:{room.get('room_id')}"] = tick
        return {"applied": True, "room": room, "light": light_def, "response": response}

    if choice == "develop_colonist_skill":
        key = str(details.get("skill_training_plan") or "")
        plan = (details.get("skill_training_options") or {}).get(key)
        if not plan:
            return {"applied": False, "reason": "Laya did not select a valid skill-development plan"}
        response = client.post("/api/v1/colonist/work-priority", body={
            "id": int(plan["pawn_id"]),
            "work": str(plan["work_type"]),
            "priority": 2,
        })
        map_state.setdefault("skill_development_plans", {})[str(plan["pawn_id"])] = {
            "skill": plan["skill"], "work_type": plan["work_type"], "started_tick": tick,
            "passion": plan["passion"],
        }
        issued["skill_development"] = tick
        return {"applied": True, "plan": plan, "response": response}

    if choice == "optimize_night_owl_schedule":
        pawn_id = details.get("night_owl_pawn")
        if pawn_id is None or str(pawn_id) not in (details.get("night_owl_options") or {}):
            return {"applied": False, "reason": "Laya did not select a valid Night Owl colonist"}
        responses = [
            client.post("/api/v1/colonist/time-assignment", body={
                "pawn_id": int(pawn_id), "hour": hour, "assignment": assignment,
            })
            for hour, assignment in professions.night_owl_schedule().items()
        ]
        scheduled = map_state.setdefault("night_owl_schedules", [])
        if int(pawn_id) not in scheduled:
            scheduled.append(int(pawn_id))
        issued[f"night_owl:{int(pawn_id)}"] = tick
        return {"applied": True, "pawn_id": int(pawn_id), "schedule": professions.night_owl_schedule(), "responses": responses}

    if choice == "schedule_recreation":
        pawn_id = details.get("recreation_pawn")
        slot = str(details.get("recreation_slot") or "")
        if str(pawn_id) not in (details.get("recreation_schedule_options") or {}):
            return {"applied": False, "reason": "Laya did not select an eligible recreation-starved colonist"}
        start = {"morning": 8, "midday": 12, "evening": 18}.get(slot)
        if start is None:
            return {"applied": False, "reason": "Laya did not select a valid recreation window"}
        responses = [client.post("/api/v1/colonist/time-assignment", body={
            "pawn_id": int(pawn_id), "hour": hour, "assignment": "Joy",
        }) for hour in (start, start + 1)]
        map_state.setdefault("recreation_schedules", []).append(int(pawn_id))
        issued[f"recreation:{int(pawn_id)}"] = tick
        return {"applied": True, "pawn_id": int(pawn_id), "hours": [start, start + 1], "responses": responses}

    if choice == "upgrade_workbench":
        key = str(details.get("workbench_upgrade") or "")
        plan = (details.get("workbench_upgrade_options") or {}).get(key)
        if not plan:
            return {"applied": False, "reason": "Laya did not select a valid workbench transition"}
        old = next((row for row in snapshot.get("development", {}).get("buildings", []) if str(row.get("def")) == str(plan["old"])), None)
        if not old:
            return {"applied": False, "reason": f"Source workbench {plan['old']} is no longer present"}
        old_pos = old.get("position") or anchor
        target_row = next((row for row in snapshot.get("development", {}).get("building_catalog", []) if row.get("def_name") == plan["new"]), {})
        stuff = plan.get("stuff")
        response = place_checked_building(client, map_id, {
            "def_name": str(plan["new"]),
            "size_x": int(target_row.get("size_x") or 1),
            "size_z": int(target_row.get("size_z") or 1),
        }, position(int(old_pos.get("x") or 0) + 4, int(old_pos.get("z") or 0)), stuff)
        if not response.get("applied"):
            return response
        issued["workbench_upgrade"] = tick
        issued[f"workbench_upgrade:{plan['new']}"] = tick
        map_state.setdefault("workbench_upgrades", []).append({**plan, "issued_tick": tick, "old_retained": True})
        return {"applied": True, "transition": plan, "old_retained": True, "response": response}

    if choice == "choose_colony_doctrine":
        doctrine = dict(details.get("doctrine_selection") or {})
        if not doctrine:
            return {"applied": False, "reason": "The cascaded doctrine selection is incomplete"}
        previous = map_state.get("doctrine") or {}
        if previous != doctrine:
            history = map_state.setdefault("doctrine_history", [])
            history.append({
                "tick": tick,
                "change": "initial" if not previous else "Laya_revision",
                "from": {key: previous.get(key) for key in (
                    "primary_direction", "economy_product", "diplomacy", "endgame") if previous.get(key)},
                "to": {key: doctrine.get(key) for key in (
                    "primary_direction", "economy_product", "diplomacy", "endgame") if doctrine.get(key)},
            })
            map_state["doctrine_history"] = history[-12:]
        map_state["doctrine"] = doctrine
        map_state["doctrine_audit"] = {
            "coverage": (details.get("doctrine_direction_audit") or {}).get("coverage", {}),
            "expansions": (details.get("doctrine_direction_audit") or {}).get("expansions", {}),
            "available_directions": list((details.get("doctrine_direction_audit") or {}).get("available", {})),
            "unavailable_directions": {
                name: row.get("reason") for name, row in (details.get("doctrine_direction_audit") or {}).get("unavailable", {}).items()
            },
        }
        map_state["doctrine_tick"] = tick
        map_state["income_strategy"] = strategy.legacy_income(doctrine)
        map_state["income_strategy_tick"] = tick
        issued["doctrine"] = tick
        return {
            "applied": True,
            "doctrine": doctrine,
            "retained": bool(details.get("doctrine_retained")),
            "audit": map_state["doctrine_audit"],
            "note": "Existing buildings remain unchanged; the doctrine affects only future research, projects and priorities.",
        }
    if choice == "build_private_bedroom":
        material = str(details.get("bedroom_material") or (map_state.get("doctrine") or {}).get("material") or "WoodLog")
        room_count = sum(1 for r in snapshot["development"].get("rooms", []) if "bedroom" in str(r.get("role_label") or "").lower())
        layout = private_bedroom_blueprint(
            material,
            powered="Electricity" in set(map(str, snapshot["development"].get("finished_research", []))),
            complex_furniture="ComplexFurniture" in set(map(str, snapshot["development"].get("finished_research", []))),
            climate="cold" if float((snapshot["development"].get("weather") or {}).get("temperature") or 0) < 8 else "hot" if float((snapshot["development"].get("weather") or {}).get("temperature") or 0) > 30 else "temperate",
        )
        result = post_blueprint(client, map_id, anchor, layout, dx=34 + (room_count % 3) * 8, dz=(room_count // 3) * 8)
        issued[f"private_bedroom:{room_count}"] = tick
        return {"applied": True, "material": material, "response": result}
    if choice == "excavate_mountain_bedroom":
        rect = details.get("mountain_bedroom_rect")
        if not rect:
            return {"applied": False, "reason": "No verified solid natural-rock room is available"}
        point_a, point_b = rect
        x, z = int(point_a["x"]), int(point_a["z"])
        responses = [
            client.post("/api/v1/order/designate/area", body={"map_id": map_id, "point_a": position(x + 1, z + 1), "point_b": position(x + 5, z + 5), "type": "mine"}),
            client.post("/api/v1/order/designate/area", body={"map_id": map_id, "point_a": position(x + 3, z), "point_b": position(x + 3, z), "type": "mine"}),
            prioritize(client, snapshot, "Mining"),
        ]
        map_state["mountain_bedroom"] = {"x": x, "z": z, "furnished": False}
        issued["mountain_bedroom_mine"] = tick
        return {"applied": True, "responses": responses}
    if choice == "finish_mountain_bedroom":
        plan = map_state.get("mountain_bedroom") or {}
        if not plan:
            return {"applied": False, "reason": "No excavated mountain bedroom plan exists"}
        temperature = float((snapshot["development"].get("weather") or {}).get("temperature") or 0)
        climate = "cold" if temperature < 8 else "hot" if temperature > 30 else "temperate"
        result = post_blueprint(client, map_id, {"x": int(plan["x"]), "z": int(plan["z"])}, mountain_bedroom_furnishing(powered="Electricity" in set(map(str, snapshot["development"].get("finished_research", []))), climate=climate))
        plan["furnished"] = True
        issued["mountain_bedroom_furnish"] = tick
        return {"applied": True, "response": result}
    if choice == "commission_sculptures":
        tables = [row for row in snapshot["development"].get("work_tables", []) if row.get("thing_def") == "TableSculpting"]
        if not tables:
            material = str((map_state.get("doctrine") or {}).get("material") or "WoodLog")
            if material not in {"WoodLog", "Steel"} and not material.startswith("Blocks"):
                material = "WoodLog"
            result = post_blueprint(client, map_id, anchor, workshop_blueprint("TableSculpting", stuff=material), dx=18, dz=24)
        else:
            result = ensure_bill(client, tables[0], "Make_SculptureSmall", 4)
        issued["commission_sculptures"] = tick
        return {"applied": True, "response": result, "art_work": prioritize(client, snapshot, "Art")}
    if choice == "install_sculpture":
        key = str(details.get("sculpture_install_plan") or "")
        plan = (details.get("sculpture_install_options") or {}).get(key)
        if not plan:
            return {"applied": False, "reason": "Laya did not select a valid sculpture and room"}
        cells = plan.get("cells") or []
        target = cells[len(cells) // 2] if cells else None
        if not target:
            return {"applied": False, "reason": "Selected room has no installation cell"}
        result = client.post("/api/v1/builder/install-minified", body={"map_id": map_id, "thing_id": int(plan["thing_id"]), "position": target, "rotation": 0})
        issued["install_sculpture"] = tick
        return {"applied": True, "room": plan.get("room_role"), "response": result}
    if choice == "build_weapon_shelves":
        shelf_ids = list(map(int, details.get("weapon_shelf_ids") or []))
        if shelf_ids:
            result = client.post("/api/v1/builder/storage/configure", body={"map_id": map_id, "building_ids": shelf_ids, "allowed_item_categories": ["Weapons"], "allowed_item_defs": [], "priority": 4})
            map_state["weapon_shelves_configured"] = True
            return {"applied": True, "phase": "configure", "response": result}
        material = str((map_state.get("doctrine") or {}).get("material") or "WoodLog")
        if material.startswith("Blocks"):
            material = "WoodLog"
        layout = weapon_shelves_blueprint(material)
        near = position(int(anchor["x"]) - 8, int(anchor["z"]) + 9)
        site = find_clear_layout_site(client, map_id, near, layout, dev, map_state)
        if site is None:
            return {"applied": False, "reason": "No clear dry site for weapon shelves"}
        result = post_blueprint(client, map_id, site, layout)
        issued["weapon_shelves"] = tick
        return {"applied": True, "phase": "build", "site": site, "response": result}
    if choice == "equip_colonists":
        fighters = [pawn for pawn in snapshot.get("combat", {}).get("colonists", [])
                    if not pawn.get("is_dead") and not pawn.get("is_downed")
                    and not pawn.get("has_ranged_weapon") and bridge.first_number(pawn.get("manipulation"), 1) >= 0.65]
        weapons = [weapon for weapon in snapshot.get("combat", {}).get("available_weapons", [])
                   if weapon.get("is_ranged") and weapon.get("id") is not None]
        fighters.sort(key=lambda pawn: int(pawn.get("shooting_skill") or 0), reverse=True)
        responses = []
        assignments = []
        for pawn in fighters:
            safe_weapons = [weapon for weapon in weapons if not bridge.combat_planner.errand_exposed(
                snapshot, weapon.get("position"), pawn.get("position"))]
            if not safe_weapons:
                continue
            pos = pawn.get("position") or {}
            weapon = min(safe_weapons, key=lambda row: (
                bridge.first_number((row.get("position") or {}).get("x")) - bridge.first_number(pos.get("x"))
            ) ** 2 + (
                bridge.first_number((row.get("position") or {}).get("z")) - bridge.first_number(pos.get("z"))
            ) ** 2)
            weapons.remove(weapon)
            if weapon.get("is_forbidden"):
                responses.append(client.post("/api/v1/things/set-forbidden", body={
                    "map_id": map_id, "thing_ids": [int(weapon["id"])], "forbidden": False,
                }))
            responses.append(client.post("/api/v1/pawn/job", body={
                "pawn_id": int(pawn["id"]), "job_def": "Equip", "target_thing_id": int(weapon["id"]),
            }))
            assignments.append(f"{pawn.get('name')} -> {weapon.get('label') or weapon.get('def_name')}")
        if responses:
            issued["equip_colonists"] = tick
        return {"applied": bool(responses), "assignments": assignments, "responses": responses}
    if choice == "prioritize_armament":
        unarmed = [p for p in snapshot.get("combat", {}).get("colonists", []) if not p.get("has_ranged_weapon") and not p.get("is_dead") and not p.get("is_downed")]
        weapons = [w for w in snapshot.get("combat", {}).get("available_weapons", []) if w.get("is_ranged")]
        responses = []
        for pawn in unarmed:
            weapon = next((row for row in weapons if not bridge.combat_planner.errand_exposed(
                snapshot, row.get("position"), pawn.get("position"))), None)
            if weapon is None:
                continue
            weapons.remove(weapon)
            if weapon.get("is_forbidden"):
                responses.append(client.post("/api/v1/things/set-forbidden", body={"map_id": map_id, "thing_ids": [int(weapon["id"])], "forbidden": False}))
            responses.append(client.post("/api/v1/pawn/job", body={"pawn_id": int(pawn["id"]), "job_def": "Equip", "target_thing_id": int(weapon["id"])}))
        if responses:
            issued["armament"] = tick
            return {"applied": True, "phase": "equip", "responses": responses}
        if not any("ResearchBench" in str(name) and int(amount or 0) > 0
                   for name, amount in (snapshot["development"].get("building_counts") or {}).items()):
            return {"applied": False, "reason": "No completed research bench is available"}
        current_research = str((snapshot["development"].get("current_research") or {}).get("name") or "none")
        if current_research.lower() != "none":
            return {"applied": False, "reason": f"Research already active: {current_research}"}
        target = next_research(client, set(map(str, snapshot["development"].get("finished_research", []))), map_state)
        if not target:
            return {"applied": False, "reason": "No suitable armament research is available"}
        response = select_research_if_available(client, target)
        applied = bool(response) and not (isinstance(response, dict) and response.get("applied") is False)
        if applied:
            issued["armament"] = tick
        return {"applied": applied, "phase": "research", "response": response}
    if choice == "build_animal_barn":
        options = details.get("animal_barn_options") or {}
        material = str(details.get("animal_barn_material") or (map_state.get("doctrine") or {}).get("material") or "WoodLog")
        floor_choice = str(details.get("animal_barn_floor") or "bare")
        layout = animal_barn_blueprint(material, int(options.get("animal_count") or len(snapshot.get("animals", []))),
                                       straw_floor=floor_choice == "straw",
                                       powered="Electricity" in set(map(str, snapshot["development"].get("finished_research", []))),
                                       climate=str(options.get("climate") or "temperate"))
        near = position(int(anchor["x"]) - 22, int(anchor["z"]) + 18)
        site = find_clear_layout_site(client, map_id, near, layout, dev, map_state)
        if site is None:
            return {"applied": False, "reason": "No stable unoccupied site for the barn"}
        result = post_blueprint(client, map_id, site, layout)
        issued["animal_barn"] = tick
        return {"applied": True, "material": material, "floor": floor_choice,
                "site": site, "response": result}
    if choice == "build_animal_pen":
        options = details.get("animal_pen_options") or {}
        material = str(details.get("animal_pen_material") or "")
        size = int(details.get("animal_pen_size") or 9)
        if material not in (options.get("materials") or {}) or str(size) not in (options.get("sizes") or {}):
            return {"applied": False, "reason": "Selected pen material or size is unavailable"}
        desired = {"x": int(anchor["x"]) + 15, "z": int(anchor["z"]) + 13}
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        origin = find_terrain_rect(
            terrain, desired, size, size,
            {"Soil", "SoilRich", "Gravel", "Sand"}, radius=30,
            blocked=architecture_occupied_cells(snapshot.get("development") or {}, map_state),
            clearance=1,
        )
        if origin is None:
            issued["animal_pen_site_search"] = tick
            return {"applied": False, "reason": "No unoccupied dry site for a fully enclosed pen"}
        result = client.post("/api/v1/builder/blueprint", body={
            "map_id": map_id, "position": position(origin["x"], origin["z"]),
            "blueprint": animal_pen_blueprint(size, material), "clear_obstacles": False,
        })
        issued["animal_pen"] = tick
        return {"applied": True, "origin": origin, "size": size, "material": material,
                "response": result, "construction": prioritize(client, snapshot, "Construction")}
    if choice in {"pause_late_sowing", "resume_seasonal_sowing"}:
        allow = choice == "resume_seasonal_sowing"
        responses = [client.post("/api/v1/map/zone/growing/sowing", body={"map_id": map_id, "zone_id": int(zone_id), "allow_sow": allow}) for zone_id in details.get("sowing_zone_ids") or []]
        issued[choice] = tick
        return {"applied": bool(responses), "allow_sow": allow, "responses": responses}

    if choice == "unforbid_supplies":
        ids = [int(row["thing_id"]) for row in relevant_forbidden(snapshot) if row.get("thing_id") is not None]
        if not ids:
            return {"applied": False, "reason": "No forbidden supplies remain"}
        result = client.post(
            "/api/v1/things/set-forbidden",
            body={"map_id": map_id, "thing_ids": ids, "forbidden": False},
        )
        issued["unforbid_supplies"] = tick
        return {"applied": True, "stacks_unforbidden": len(ids), "response": result}
    if choice == "unforbid_corpses":
        ids = [int(row["thing_id"]) for row in forbidden_corpses(snapshot) if row.get("thing_id") is not None]
        if not ids:
            return {"applied": False, "reason": "No forbidden corpses remain"}
        result = client.post(
            "/api/v1/things/set-forbidden",
            body={"map_id": map_id, "thing_ids": ids, "forbidden": False},
        )
        issued["unforbid_corpses"] = tick
        return {"applied": True, "corpses_unforbidden": len(ids), "response": result}
    if choice == "build_cemetery":
        plan = next((row for row in snapshot.get("development", {}).get("building_catalog") or []
                     if row.get("def_name") == "Grave"),
                    {"def_name": "Grave", "size_x": 1, "size_z": 2})
        graveyard = position(int(anchor["x"]) - 12, int(anchor["z"]) + 14)
        placed = []
        failure = None
        for _ in range(max(1, min(8, int(details.get("grave_count") or 2)))):
            result = place_checked_building(client, map_id, plan, graveyard,
                                            radius=25, expand_search=False,
                                            snapshot=snapshot)
            if not result.get("applied"):
                failure = result.get("reason")
                break
            placed.append(result)
        issued["cemetery"] = tick
        return {"applied": bool(placed), "placed_graves": len(placed),
                "sites": [row["site"] for row in placed], "reason": failure}
    if choice == "create_human_corpse_dump":
        dump_x = max(6, min(240, int(anchor["x"]) + (50 if int(anchor["x"]) < 125 else -50)))
        dump_z = max(6, min(240, int(anchor["z"]) + (45 if int(anchor["z"]) < 125 else -45)))
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        dump_anchor = find_terrain_rect(
            terrain, {"x": dump_x, "z": dump_z}, 6, 6,
            {"Soil", "SoilRich", "Gravel", "Sand", "MarshyTerrain"}, radius=35,
        ) or {"x": dump_x, "z": dump_z}
        dump_x, dump_z = int(dump_anchor["x"]), int(dump_anchor["z"])
        result = client.post("/api/v1/map/zone/stockpile", body={
            "map_id": map_id,
            "point_a": position(dump_x, dump_z),
            "point_b": position(dump_x + 5, dump_z + 5),
            "name": "Laya Human Corpse Dump",
            "priority": 5,
            "allowed_item_categories": ["CorpsesHumanlike"],
        })
        issued["human_corpse_dump"] = tick
        return {"applied": True, "distance_from_base": abs(dump_x - int(anchor["x"])) + abs(dump_z - int(anchor["z"])), "response": result}
    if choice == "create_animal_corpse_dump":
        result = client.post("/api/v1/map/zone/stockpile", body={
            "map_id": map_id,
            "point_a": position(anchor["x"] + 15, anchor["z"] + 7),
            "point_b": position(anchor["x"] + 19, anchor["z"] + 10),
            "name": "Laya Animal Carcasses",
            "priority": 5,
            "allowed_item_categories": ["CorpsesAnimal"],
        })
        issued["animal_corpse_dump"] = tick
        return result
    if choice == "build_butcher_spot":
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        # The map anchor can drift after the stockpile is created. Locate the
        # actual carcass cluster, excluding remote unhauled kills with medians.
        carcass_positions = [row.get("position") or {} for row in corpse_rows(snapshot, "CorpsesAnimal")]
        carcass_positions = [point for point in carcass_positions
                             if point.get("x") is not None and point.get("z") is not None]
        near_carcasses = position(
            sorted(int(point["x"]) for point in carcass_positions)[len(carcass_positions) // 2],
            sorted(int(point["z"]) for point in carcass_positions)[len(carcass_positions) // 2],
        ) if carcass_positions else anchor
        site = open_recreation_site(terrain, anchor, snapshot["development"], desired=near_carcasses)
        if site is None:
            return {"applied": False, "reason": "No dry empty tile near the carcasses for a butcher spot"}
        response = post_blueprint(client, map_id, site, blueprint([building("ButcherSpot", 0, 0)], 1, 1))
        if not response.get("success"):
            return {"applied": False, "site": site, "response": response}
        issued["butcher_spot"] = tick
        bill_response: dict[str, Any] = {"applied": False, "reason": "Butcher spot has not appeared as a work table yet"}
        bill_configured = False
        try:
            tables = client.get("/api/v1/map/work-tables", map_id=map_id)
            spot = next((table for table in tables if table.get("thing_def") == "ButcherSpot"
                         and (table.get("position") or {}).get("x") == site["x"]
                         and (table.get("position") or {}).get("z") == site["z"]), None)
            if spot is not None:
                bill_result = configure_food_bills(client, [spot])
                bill_response = {"applied": bill_result["applied"], "recipes": [
                    row.get("recipe_def_name") for row in bill_result["responses"] if isinstance(row, dict)
                ]}
                bills = client.get("/api/v1/buildings/bills", building_id=int(spot["id"]))
                bill_configured = any(
                    bill.get("recipe_def_name") == "ButcherCorpseFlesh"
                    and bill.get("repeat_mode") == "Forever"
                    and not bill.get("suspended") and not bill.get("paused")
                    for bill in bills if isinstance(bill, dict)
                )
        except bridge.RimApiError as error:
            bill_response = {"applied": False, "reason": str(error)}
        return {"applied": True, "site": site, "response": response,
                "bill_configured": bill_configured, "bill_response": bill_response}
    if choice == "create_stone_chunk_dump":
        near = details.get("stone_dump_anchor") or anchor
        x, z = int((near or {}).get("x") or anchor["x"]), int((near or {}).get("z") or anchor["z"])
        result = client.post("/api/v1/map/zone/stockpile", body={
            "map_id": map_id,
            "point_a": position(x + 2, z - 2),
            "point_b": position(x + 5, z + 2),
            "name": "Laya Stone Chunks",
            "priority": 3,
            "allowed_item_categories": ["StoneChunks"],
        })
        issued["stone_chunk_dump"] = tick
        return result
    if choice == "build_crematorium":
        tables = [row for row in snapshot["development"].get("work_tables", []) if row.get("thing_def") == "ElectricCrematorium"]
        if tables:
            result = ensure_bill(client, tables[0], "CremateCorpse", 25)
            issued["crematorium_bill"] = tick
            return {"applied": True, "phase": "configure", "response": result}
        stuff = str(details.get("crematorium_stuff") or "BlocksGranite")
        result = post_blueprint(client, map_id, anchor, workshop_blueprint("ElectricCrematorium", stuff=stuff), dx=-18, dz=19)
        issued["crematorium"] = tick
        return {"applied": True, "phase": "build", "stuff": stuff, "response": result}
    if choice == "build_prison":
        stuff = prison_material(snapshot["development"].get("item_counts") or {})
        if not stuff:
            return {"applied": False, "reason": "Prison needs 140 wood or steel; stock changed before placement"}
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        site = choose_prison_site(terrain, anchor, snapshot["development"], map_state)
        if site is None:
            issued["prison_blueprint"] = tick
            return {"applied": False, "reason": "No clear dry seven-cell site for an enclosed prison"}
        result = post_blueprint(client, map_id, site, prison_blueprint(stuff))
        map_state["prison_site"] = site
        issued["prison_blueprint"] = tick
        return {"applied": True, "site": site, "material": stuff, "blueprint": result,
                "construction": prioritize(client, snapshot, "Construction")}
    if choice == "build_hospital":
        result = post_blueprint(client, map_id, anchor, hospital_blueprint(), dx=25, dz=0)
        issued["hospital_blueprint"] = tick
        return {"applied": True, "blueprint": result, "construction": prioritize(client, snapshot, "Construction")}
    if choice == "build_passive_cooler":
        key = str(details.get("cool_room") or "")
        options = details.get("cool_room_options") or {}
        if not key and len(options) == 1:
            key = next(iter(options))
        room = options.get(key)
        if not room or not room.get("placement"):
            return {"applied": False, "reason": "No verified cooler position in the chosen occupied room"}
        target = room["placement"]
        response = client.post("/api/v1/builder/blueprint", body={
            "map_id": map_id,
            "position": position(int(target["x"]), int(target["z"])),
            "blueprint": blueprint([building("PassiveCooler", 0, 0)], 1, 1),
            "clear_obstacles": False,
        })
        issued[f"passive_cooler_room:{room['room_id']}"] = tick
        return {"applied": True, "room": room["room_id"], "target": target,
                "blueprint": response, "construction": prioritize(client, snapshot, "Construction")}
    if choice in {"build_room_campfire", "build_room_heater", "connect_room_heater_power"}:
        key = str(details.get("warm_room") or "")
        options = (details.get("power_connection_options") if choice == "connect_room_heater_power" else
                   details.get("heater_room_options") if choice == "build_room_heater" else
                   details.get("warm_room_options")) or {}
        if not key and len(options) == 1:
            key = next(iter(options))
        room = options.get(key)
        if not room or not (room.get("target") or room.get("placement")):
            return {"applied": False, "reason": "No verified heating position in the chosen occupied room"}
        source = "Campfire" if choice == "build_room_campfire" else "Heater"
        target = room.get("target") or room.get("placement")
        if choice == "build_room_campfire":
            if campfire_safe_placement([target], (snapshot["development"].get("buildings") or [])
                                       + (snapshot["development"].get("construction_projects") or [])) is None:
                return {"applied": False, "reason": "Campfire is too close to a combustible structure"}
            origin = position(int(target["x"]), int(target["z"]))
            # A free cell can still have a blocked interaction spot at the
            # default rotation. Ask RimWorld's placement checker for the
            # exact live cell and use the rotation it accepts.
            checked = client.post("/api/v1/builder/site-options", body={
                "map_id": map_id, "def_name": "Campfire", "near": origin,
                "radius": 1, "limit": 12,
            })
            valid = next((site for site in checked.get("sites") or []
                          if (site.get("position") or {}).get("x") == origin["x"]
                          and (site.get("position") or {}).get("z") == origin["z"]), None)
            if valid is None:
                issued[f"heating_room:{room['room_id']}"] = tick
                return {"applied": False, "reason": "The room's campfire cell has no valid interaction rotation",
                        "target": origin, "placement_check": checked.get("reason")}
            layout = blueprint([building("Campfire", 0, 0, rotation=int(valid["rotation"]))], 1, 1)
        else:
            route = room.get("route")
            if route is None or (choice == "connect_room_heater_power" and not route):
                return {"applied": False, "reason": "No verified live-grid cable route"}
            origin, layout = wired_heater_blueprint(
                target, route, include_heater=choice == "build_room_heater")
        response = client.post("/api/v1/builder/blueprint", body={
            "map_id": map_id,
            "position": origin,
            "blueprint": layout,
            "clear_obstacles": False,
        })
        marker = (f"heater_power_room:{room['room_id']}" if choice == "connect_room_heater_power"
                  else f"heating_room:{room['room_id']}")
        issued[marker] = tick
        return {"applied": True, "room": room["room_id"], "source": source,
                "target": target, "conduit_count": len(room.get("route") or []),
                "blueprint": response,
                "construction": prioritize(client, snapshot, "Construction")}
    if choice == "configure_hospital_beds":
        generated_hospitals = [
            row for row in map_state.get("architecture_projects", [])
            if row.get("program") == "hospital"
        ]
        if generated_hospitals:
            hospital = generated_hospitals[-1]
            start = hospital["origin"]
            point_a = position(int(start["x"]), int(start["z"]))
            point_b = position(
                int(start["x"]) + int(hospital["width"]) - 1,
                int(start["z"]) + int(hospital["height"]) - 1,
            )
        else:
            point_a = position(anchor["x"] + 25, anchor["z"])
            point_b = position(anchor["x"] + 31, anchor["z"] + 6)
        result = client.post("/api/v1/map/beds/configure", body={
            "map_id": map_id,
            "point_a": point_a,
            "point_b": point_b,
            "medical": True,
            "for_prisoners": False,
        })
        issued["hospital_beds"] = tick
        return result
    if choice == "floor_critical_room":
        plan_key = str(details.get("critical_floor_plan") or "")
        plan = (details.get("critical_floor_options") or {}).get(plan_key)
        if not plan:
            return {"applied": False, "reason": "Laya did not select an available critical-room floor plan"}
        terrain_map = client.get("/api/v1/map/terrain", map_id=map_id)
        actual_terrain = terrain_defs_at_cells(terrain_map, plan["cells"])
        planned_cells = floor_project_cells(dev.get("construction_projects") or [])
        remaining = [cell for cell in plan["cells"]
                     if needs_first_floor(actual_terrain.get((int(cell["x"]), int(cell["z"]))))
                     and (int(cell["x"]), int(cell["z"])) not in planned_cells]
        if not remaining:
            issued[f"floor_room:{int(plan['room_id'])}"] = tick
            return {"applied": False, "skipped": "already_floored_or_planned", "plan": plan_key}
        layout, origin = room_floor_blueprint(remaining, str(plan["floor_def"]))
        result = client.post("/api/v1/builder/blueprint", body={
            "map_id": map_id,
            "position": position(origin["x"], origin["z"]),
            "blueprint": layout,
            "clear_obstacles": False,
        })
        issued[f"floor_room:{int(plan['room_id'])}"] = tick
        issued["critical_floor"] = tick
        return {"applied": True, "plan": plan_key, "cost": plan.get("cost"), "response": result}
    if choice == "expand_home_area":
        fire_id = str(details.get("fire_target") or "")
        if fire_id not in (snapshot["development"].get("fire_options") or {}):
            return {"applied": False, "reason": "Selected fire is no longer a threatened live target"}
        fire = next((row for row in (snapshot["development"].get("fire_situation") or {}).get("fires") or []
                     if str(row.get("id")) == fire_id), None)
        if fire is None:
            return {"applied": False, "reason": "Selected fire has disappeared"}
        x, z = int(fire["x"]), int(fire["z"])
        response = client.post("/api/v1/order/designate/area", body={
            "map_id": map_id, "type": "home",
            "point_a": position(x - 2, z - 2), "point_b": position(x + 2, z + 2),
        })
        issued["expand_home_area"] = tick
        return {"applied": True, "fire_id": int(fire_id), "response": response}
    if choice == "build_pathways":
        material = str(details.get("path_material") or "")
        if material not in (details.get("path_floor_options") or {}):
            return {"applied": False, "reason": "Laya did not select an affordable path material"}
        layout, origin = pathway_blueprint(material, anchor, map_state.get("growing_anchor") or anchor)
        terrain_map = client.get("/api/v1/map/terrain", map_id=map_id)
        absolute = [{"x": origin["x"] + int(row["rel_x"]),
                     "z": origin["z"] + int(row["rel_z"])} for row in layout["floors"]]
        terrain_at_path = terrain_defs_at_cells(terrain_map, absolute)
        planned = floor_project_cells(dev.get("construction_projects") or [])
        layout["floors"] = [row for row, cell in zip(layout["floors"], absolute)
                            if needs_first_floor(terrain_at_path.get((cell["x"], cell["z"])))
                            and (cell["x"], cell["z"]) not in planned]
        if not layout["floors"]:
            issued["pathways"] = tick
            return {"applied": False, "skipped": "already_floored_or_planned"}
        result = client.post("/api/v1/builder/blueprint", body={
            "map_id": map_id,
            "position": position(origin["x"], origin["z"]),
            "blueprint": layout,
            "clear_obstacles": False,
        })
        issued["pathways"] = tick
        return {"applied": True, "material": material, "response": result}
    if choice == "build_temple":
        altar = str(details.get("temple_altar") or "")
        material = str(details.get("temple_material") or "")
        options = details.get("temple_options") or {}
        if altar not in (options.get("altars") or {}) or material not in (options.get("materials") or {}):
            return {"applied": False, "reason": "Laya did not select a valid ideology altar and affordable material"}
        result = post_blueprint(client, map_id, anchor, temple_blueprint(altar, material), dx=35, dz=17)
        issued["temple"] = tick
        return {"applied": True, "altar": altar, "material": material, "response": result}
    if choice == "prioritize_burial":
        result = prioritize(client, snapshot, "Hauling", details.get("worker_pawn"))
        issued["priority:Burial"] = tick
        issued["priority:Hauling"] = tick
        return result
    if choice == "create_food_stockpile":
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        site = find_starter_food_site(terrain, anchor, snapshot["development"], map_state)
        if site is None:
            issued["food_stockpile"] = tick
            return {"applied": False, "reason": "No dry food-stockpile patch clear of the bedroom, crops and sealed ruin"}
        result = client.post("/api/v1/map/zone/stockpile", body={
            "map_id": map_id,
            "point_a": position(site["x"], site["z"]),
            "point_b": position(site["x"] + 3, site["z"] + 3),
            "name": "Laya Temporary Food",
            "priority": 2,
            "allowed_item_categories": ["FoodMeals", "FoodRaw"],
        })
        issued["food_stockpile"] = tick
        return {"applied": True, "site": site, "response": result}
    if choice == "build_sleeping_spots":
        indoor = details.get("indoor_sleeping_spot")
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        outdoor = open_bed_site(terrain, anchor, snapshot["development"])
        sites = [site for site in (indoor, outdoor) if site is not None]
        issued["sleeping_spots"] = tick
        if not sites:
            return {"applied": False, "reason": "No clear dry sleeping place near the colony"}
        for site in sites:
            result = post_blueprint(client, map_id, site,
                                    blueprint([building("SleepingSpot", 0, 0)], 1, 2))
            buildings = client.get("/api/v1/map/buildings", map_id=map_id)
            if isinstance(buildings, list) and any(
                row.get("def") == "SleepingSpot" and row.get("position", {}).get("x") == site["x"]
                and row.get("position", {}).get("z") == site["z"] for row in buildings
            ):
                return {"applied": True, "site": site, "response": result}
        return {"applied": False, "reason": "RIMAPI accepted the request but placed no sleeping spot"}
    if choice == "assign_real_bed":
        selected = str(details.get("bed_assignment") or "")
        if selected not in (snapshot["development"].get("bed_assignment_options") or {}):
            return {"applied": False, "reason": "Selected pawn-bed pair is no longer available"}
        pawn_id, bed_id = map(int, selected.split("|", 1))
        result = client.post("/api/v1/pawn/medical/bed-rest", body={
            "patient_pawn_id": pawn_id, "bed_building_id": bed_id,
        })
        map_state.setdefault("assigned_real_beds", {})[str(pawn_id)] = bed_id
        return {"applied": True, "pawn_id": pawn_id, "bed_id": bed_id, "response": result}
    if choice == "prepare_emergency_medical_bed":
        bed_id = str(details.get("emergency_medical_bed") or "")
        if bed_id not in (snapshot["development"].get("emergency_medical_bed_options") or {}):
            return {"applied": False, "reason": "Selected completed bed is no longer available"}
        bed = next((b for b in snapshot["development"].get("buildings") or []
                    if str(b.get("id")) == bed_id), None)
        if bed is None:
            return {"applied": False, "reason": "Selected bed disappeared"}
        point = bed["position"]
        result = client.post("/api/v1/map/beds/configure", body={
            "map_id": map_id, "point_a": point, "point_b": point,
            "medical": True, "for_prisoners": False,
        })
        return {"applied": True, "bed_id": int(bed_id), "response": result}
    if choice == "build_basic_beds":
        failed_sites = map_state.setdefault("failed_bed_sites", [])
        site = empty_indoor_sleeping_spot(
            snapshot["development"], anchor,
            excluded={(int(row["x"]), int(row["z"])) for row in failed_sites},
        )
        replacement = None
        if site is None:
            replacement = replaceable_indoor_sleeping_spot(
                snapshot["development"], anchor, snapshot["colonists"],
                {(int(row["x"]), int(row["z"])) for row in failed_sites},
            )
            if replacement is not None:
                site = replacement["position"]
        issued["basic_beds"] = tick
        if site is None:
            return {"applied": False, "reason": "No clear or replaceable two-cell bed site inside a completed roofed room"}
        materials = details.get("basic_bed_materials") or {}
        material = details.get("bed_material") or next(iter(materials), None)
        if material not in materials:
            return {"applied": False, "reason": "Selected bed material is no longer available"}
        if replacement is not None:
            client.post("/api/v1/order/designate/area", body={
                "map_id": map_id, "point_a": position(site["x"], site["z"]),
                "point_b": position(site["x"], site["z"]), "type": "remove-sleeping-spot",
            })
        try:
            result = post_blueprint(client, map_id, site, basic_beds_blueprint(1, stuff=material))
        except bridge.RimApiError:
            if replacement is not None:
                post_blueprint(client, map_id, site,
                               blueprint([building("SleepingSpot", 0, 0)], 1, 2))
            raise
        projects = client.get("/api/v1/builder/projects", map_id=map_id)
        rows = projects.get("projects", []) if isinstance(projects, dict) else []
        buildings = client.get("/api/v1/map/buildings", map_id=map_id)
        bed_at_site = any(
            str(row.get("def_name") or row.get("def") or "") == "Bed"
            and (row.get("position") or {}).get("x") == site["x"]
            and (row.get("position") or {}).get("z") == site["z"]
            for row in [*rows, *(buildings if isinstance(buildings, list) else [])]
        )
        if not bed_at_site:
            failed_sites.append(site)
            if replacement is not None:
                post_blueprint(client, map_id, site,
                               blueprint([building("SleepingSpot", 0, 0)], 1, 2))
            return {"applied": False, "reason": "RIMAPI accepted the request but placed no bed blueprint",
                    "site": site, "material": material}
        return {"applied": True, "beds": 1, "material": material, "site": site,
                "replaced_sleeping_spot_id": replacement["id"] if replacement else None,
                "response": result}
    if choice == "build_recreation_pin":
        terrain = client.get("/api/v1/map/terrain", map_id=map_id)
        site = open_recreation_site(terrain, anchor, snapshot["development"])
        if site is None:
            issued["recreation_pin"] = tick
            return {"applied": False, "reason": "No dry, unoccupied recreation patch near the shelter"}
        result = post_blueprint(client, map_id, site,
                                blueprint([building("HorseshoesPin", 0, 0, stuff="WoodLog")], 1, 1))
        issued["recreation_pin"] = tick
        return {"applied": True, "site": site, "response": result}
    if choice == "build_animal_spots":
        animals = [animal for animal in snapshot.get("animals", []) if not animal.get("dead")]
        result = post_blueprint(
            client,
            map_id,
            anchor,
            animal_spots_blueprint(len(animals)),
            dx=9,
            dz=8,
        )
        issued["animal_spots"] = tick
        return result
    if choice == "care_for_injured_animal":
        animal_id = int(details["injured_animal_id"])
        animal = next((row for row in snapshot.get("animals", []) if int(row.get("id", -1)) == animal_id), None)
        doctor = bridge.choose_worker(snapshot["colonists"], "Doctor")
        beds = [
            row for row in snapshot["development"]["buildings"]
            if isinstance(row, dict) and row.get("def") == "AnimalSleepingSpot"
        ]
        responses: list[Any] = []
        errors: list[str] = []
        bed = None
        if beds and animal:
            ax = float((animal.get("position") or {}).get("x") or 0)
            az = float((animal.get("position") or {}).get("z") or 0)
            bed = min(beds, key=lambda row: (
                float((row.get("position") or {}).get("x") or 0) - ax
            ) ** 2 + (
                float((row.get("position") or {}).get("z") or 0) - az
            ) ** 2)
        if bed and animal and animal.get("downed") and doctor is not None:
            bed_pos = bed.get("position") or {}
            animal_pos = animal.get("position") or {}
            distance = abs(int(bed_pos.get("x") or 0) - int(animal_pos.get("x") or 0)) + abs(
                int(bed_pos.get("z") or 0) - int(animal_pos.get("z") or 0)
            )
            if distance > 1:
                try:
                    responses.append(client.post(
                        "/api/v1/pawn/job",
                        body={
                            "pawn_id": int(doctor["id"]),
                            "job_def": "Rescue",
                            "target_thing_id": animal_id,
                            "target_thing_id_b": int(bed["id"]),
                        },
                    ))
                    issued[f"animal_care:{animal_id}"] = tick
                    return {
                        "applied": True,
                        "animal": details.get("injured_animal_name", animal_id),
                        "doctor": doctor.get("name"),
                        "phase": "rescue_to_animal_bed",
                        "responses": responses,
                        "errors": errors,
                    }
                except bridge.RimApiError as exc:
                    errors.append(str(exc))
        if bed and animal and not animal.get("downed"):
            try:
                responses.append(client.post(
                    "/api/v1/pawn/medical/bed-rest",
                    body={"patient_pawn_id": animal_id, "bed_building_id": int(bed["id"])},
                ))
            except bridge.RimApiError as exc:
                errors.append(str(exc))
        tend_body: dict[str, Any] = {"patient_pawn_id": animal_id}
        if doctor is not None:
            tend_body["doctor_pawn_id"] = int(doctor["id"])
        try:
            responses.append(client.post("/api/v1/pawn/medical/tend", body=tend_body))
        except bridge.RimApiError as exc:
            errors.append(str(exc))
        issued[f"animal_care:{animal_id}"] = tick
        return {
            "applied": bool(responses),
            "animal": details.get("injured_animal_name", animal_id),
            "doctor": doctor.get("name") if doctor else "automatic",
            "responses": responses,
            "errors": errors,
        }
    if choice == "feed_hungry_animal":
        animal_id = int(details["hungry_animal_id"])
        feeder = bridge.choose_worker(snapshot["colonists"], "Handling") or bridge.choose_worker(snapshot["colonists"], "Doctor")
        body: dict[str, Any] = {"patient_pawn_id": animal_id}
        if feeder is not None:
            body["feeder_pawn_id"] = int(feeder["id"])
        try:
            response = client.post("/api/v1/pawn/medical/feed", body=body)
        except bridge.RimApiError as exc:
            # The patient's state can change between observation and execution
            # (for example, an animal stands up and can eat by itself). Treat that
            # race as a skipped order instead of crashing every following cycle.
            issued[f"animal_feed:{animal_id}"] = tick
            return {
                "applied": False,
                "skipped": "patient_feeding_unavailable",
                "animal": details.get("hungry_animal_name", animal_id),
                "feeder": feeder.get("name") if feeder else "automatic",
                "error": str(exc),
            }
        issued[f"animal_feed:{animal_id}"] = tick
        return {
            "applied": True,
            "animal": details.get("hungry_animal_name", animal_id),
            "feeder": feeder.get("name") if feeder else "automatic",
            "response": response,
        }
    if choice == "feed_hungry_colonist":
        patient_id = int(details["hungry_colonist_id"])
        feeder = bridge.choose_worker(snapshot["colonists"], "Doctor") or bridge.choose_worker(snapshot["colonists"], "BasicWorker")
        body: dict[str, Any] = {"patient_pawn_id": patient_id}
        if feeder is not None and int(feeder.get("id", -1)) != patient_id:
            body["feeder_pawn_id"] = int(feeder["id"])
        try:
            response = client.post("/api/v1/pawn/medical/feed", body=body)
        except bridge.RimApiError as exc:
            issued[f"colonist_feed:{patient_id}"] = tick
            return {
                "applied": False,
                "skipped": "patient_feeding_unavailable",
                "colonist": details.get("hungry_colonist_name", patient_id),
                "feeder": feeder.get("name") if feeder else "automatic",
                "error": str(exc),
            }
        issued[f"colonist_feed:{patient_id}"] = tick
        return {
            "applied": True,
            "colonist": details.get("hungry_colonist_name", patient_id),
            "feeder": feeder.get("name") if feeder else "automatic",
            "response": response,
        }
    if choice == "eat_available_meal":
        options = details.get("hungry_eater_options") or {}
        selected_id = str(details.get("hungry_eater") or next(iter(options), ""))
        eater = next((pawn for pawn in snapshot["colonists"] if str(pawn.get("id")) == selected_id), None)
        if selected_id not in options or eater is None or eater.get("downed"):
            return {"applied": False, "reason": "The selected hungry colonist can no longer eat independently"}
        meals = [meal for meal in reachable_meals(snapshot)
                 if squared_distance(eater.get("position") or {}, meal.get("position") or {}) <= 60 ** 2
                 and not bridge.combat_planner.errand_exposed(
                     snapshot, meal.get("position"), eater.get("position"))]
        if not meals:
            return {"applied": False, "reason": "No unlocked meal stack remains"}
        meal = min(meals, key=lambda row: squared_distance(eater.get("position") or {}, row.get("position") or {}))
        response = client.post("/api/v1/pawn/job", body={
            "pawn_id": int(selected_id), "job_def": "Ingest", "target_thing_id": int(meal["thing_id"]),
        })
        issued[f"meal_order:{selected_id}"] = tick
        attempts = map_state.setdefault("meal_attempts", {})
        previous = attempts.get(selected_id) or {}
        attempts[selected_id] = {"tick": tick, "hunger": eater.get("hunger"),
                                 "failures": previous.get("failures", 0),
                                 "checked_tick": previous.get("checked_tick", 0)}
        return {"applied": True, "colonist": eater.get("name"), "meal": meal.get("label"),
                "distance": round(squared_distance(eater.get("position") or {}, meal.get("position") or {}) ** 0.5),
                "response": response}
    if choice == "open_blocked_food_path":
        wall_id = details.get("blocked_food_wall")
        wall = next((row for row in details.get("blocked_food_wall_options") or []
                     if int(row.get("id") or -1) == int(wall_id or -1)), None)
        builder_id = details.get("worker_pawn")
        if (wall is None or builder_id is None
                or str(builder_id) not in (details.get("blocked_food_builders") or {})):
            return {"applied": False, "reason": "No exact exit wall and builder were selected"}
        response = client.post("/api/v1/pawn/job", body={
            "pawn_id": int(builder_id), "job_def": "Deconstruct", "target_thing_id": int(wall_id),
        })
        issued["open_blocked_food_path"] = tick
        map_state.setdefault("meal_attempts", {}).pop(str(details.get("blocked_food_pawn_id")), None)
        return {"applied": True, "wall": wall_id, "builder": builder_id,
                "starving_colonist": details.get("blocked_food_pawn"), "response": response}
    if choice == "create_nearby_food_cache":
        result = client.post("/api/v1/map/zone/stockpile", body={
            "map_id": map_id,
            "point_a": position(anchor["x"] + 1, anchor["z"] + 1),
            "point_b": position(anchor["x"] + 4, anchor["z"] + 4),
            "name": "Laya Forward Food Cache",
            "priority": 5,
            "allowed_item_categories": ["FoodMeals", "FoodRaw"],
        })
        issued["nearby_food_cache"] = tick
        return {"applied": True, "reason": "Nearby high-priority food storage is ready for hauling", "response": result}
    if choice == "open_sealed_food_store":
        sealed = legacy_freezer_entrance(snapshot)
        if not sealed or sealed["status"] != "sealed" or sealed.get("wall_id") is None:
            return {"applied": False, "reason": "The legacy freezer wall is already open or no longer matches the map"}
        builder = next((pawn for pawn in snapshot["colonists"]
                        if str(pawn.get("id")) == str(details.get("worker_pawn")) and not pawn.get("downed")), None)
        builder = builder or bridge.choose_worker(snapshot["colonists"], "Construction")
        if builder is None:
            return {"applied": False, "reason": "No mobile builder can open the food store"}
        response = client.post("/api/v1/pawn/job", body={
            "pawn_id": int(builder["id"]), "job_def": "Deconstruct", "target_thing_id": int(sealed["wall_id"]),
        })
        issued["open_sealed_food_store"] = tick
        return {"applied": True, "builder": builder.get("name"), "wall": sealed["wall_id"], "response": response}
    if choice == "finish_freezer_entrance":
        sealed = legacy_freezer_entrance(snapshot)
        if not sealed or sealed["status"] != "open":
            return {"applied": False, "reason": "The freezer entrance is already built or still blocked"}
        materials = details.get("freezer_door_materials") or {}
        material = str(details.get("freezer_door_material") or next(iter(materials), ""))
        if material not in materials:
            return {"applied": False, "reason": "No affordable door material remains"}
        response = post_blueprint(client, map_id, sealed["position"],
                                  blueprint([building("Door", 0, 0, stuff=material)], 1, 1))
        issued["finish_freezer_entrance"] = tick
        return {"applied": True, "position": sealed["position"], "material": material, "response": response}
    if choice == "build_freezer":
        layout = freezer_blueprint()
        near = position(int(anchor["x"]) + 12, int(anchor["z"]))
        site = find_clear_layout_site(client, map_id, near, layout, dev, map_state, radius=28)
        if site is None:
            return {"applied": False, "reason": "No clear, dry freezer site is available"}
        response = post_blueprint(client, map_id, site, layout)
        issued["freezer"] = tick
        return {"applied": True, "site": site, "response": response}
    if choice == "create_stockpile":
        result = client.post("/api/v1/map/zone/stockpile", body={
            "map_id": map_id,
            "point_a": position(anchor["x"] - 8, anchor["z"] + 1),
            "point_b": position(anchor["x"] - 3, anchor["z"] + 6),
            "name": "Laya Main Stockpile",
            "priority": 1,
        })
        issued["stockpile"] = tick
        return result
    if choice == "expand_stockpile":
        expansion_index = int(map_state.get("stockpile_expansions") or 0)
        result = client.post("/api/v1/map/zone/stockpile", body={
            "map_id": map_id,
            "point_a": position(anchor["x"] - 15 - expansion_index * 7, anchor["z"] + 1),
            "point_b": position(anchor["x"] - 10 - expansion_index * 7, anchor["z"] + 6),
            "name": f"Laya Main Stockpile {expansion_index + 2}",
            "priority": 1,
        })
        map_state["stockpile_expansions"] = expansion_index + 1
        issued["expand_stockpile"] = tick
        return result
    if choice == "create_growing_zone":
        growing_anchor = map_state.get("growing_anchor", anchor)
        result = client.post("/api/v1/map/zone/growing", body={
            "map_id": map_id,
            "plant_def": "Plant_Rice",
            "point_a": position(growing_anchor["x"], growing_anchor["z"]),
            "point_b": position(growing_anchor["x"] + 9, growing_anchor["z"] + 7),
        })
        issued["growing"] = tick
        return result
    if choice == "build_starter_base":
        use_heated_shelter = starter_outdoor_c(snapshot["development"]) <= 5
        stock = snapshot["development"].get("item_counts") or {}
        if use_heated_shelter and not (
            int(stock.get("WoodLog") or 0) >= 130
            or (int(stock.get("Steel") or 0) >= 110 and int(stock.get("WoodLog") or 0) >= 20)
        ):
            return {"applied": False, "reason": "Not enough wood or steel for a heated shelter"}
        wall_stuff = "WoodLog" if int(stock.get("WoodLog") or 0) >= 130 else "Steel"
        result = post_blueprint(client, map_id, anchor, starter_base_blueprint(
            len(snapshot["colonists"]), cold=use_heated_shelter, wall_stuff=wall_stuff))
        issued["starter_base"] = tick
        if use_heated_shelter and not (isinstance(result, dict) and result.get("success") is False):
            staffing = []
            for pawn in snapshot["colonists"]:
                construction = (pawn.get("work_priorities") or {}).get("Construction") or {}
                if pawn.get("downed") or construction.get("disabled"):
                    continue
                pawn_id = int(pawn["id"])
                doctor_change = free_cold_shelter_builder(
                    client, {**snapshot, "development": {**snapshot["development"],
                            "cold_start_focus": "assign_builder"}}, pawn_id)
                if int(construction.get("priority") or 0) != 1:
                    staffing.append(prioritize(client, snapshot, "Construction", pawn_id))
                if doctor_change is not None:
                    staffing.append(doctor_change)
            issued["priority:Construction"] = tick
            if isinstance(result, dict):
                result["cold_shelter_staffing"] = staffing
        return result
    if choice == "build_campfire":
        catalog = next((row for row in dev.get("building_catalog") or []
                        if row.get("def_name") == "Campfire" and row.get("available_now")), None)
        if catalog is None:
            return {"applied": False, "reason": "Campfire is not available in the live building catalog"}
        result = place_checked_building(client, map_id, {
            "def_name": "Campfire", "size_x": 1, "size_z": 1,
        }, anchor, snapshot=snapshot)
        if result.get("applied"):
            issued["campfire"] = tick
            map_state["campfire_attempts"] = int(map_state.get("campfire_attempts") or 0) + 1
        return result
    if choice == "configure_food_bills":
        result = configure_food_bills(client, snapshot["development"]["work_tables"])
        issued["food_bills"] = tick
        return result
    if choice == "advance_research":
        target = details["research_target"]
        result = client.post("/api/v1/research/target", query={"name": target, "force": False})
        issued[f"research:{target}"] = tick
        return result
    if choice == "select_research":
        target = str(details.get("research_target") or "")
        if target not in live_research_options(snapshot):
            raise bridge.RimApiError(f"Research {target!r} is no longer startable")
        result = client.post("/api/v1/research/target", query={"name": target, "force": False})
        issued["research_change"] = tick
        issued[f"research:{target}"] = tick
        return {"applied": True, "target": target, "response": result}
    if choice == "advance_doctrine_research":
        target = str(details.get("doctrine_research_target") or "")
        if target not in (details.get("doctrine_research_options") or {}):
            return {"applied": False, "reason": "Laya did not select a live doctrine research project"}
        result = client.post("/api/v1/research/target", query={"name": target, "force": False})
        issued[f"research:{target}"] = tick
        return {"applied": True, "target": target, "doctrine": map_state.get("doctrine"), "response": result}
    if choice == "connect_power_consumer":
        key = str(details.get("power_consumer") or "")
        plan = (details.get("power_consumer_options") or {}).get(key)
        if plan is None or not plan.get("route"):
            return {"applied": False, "reason": "Selected disconnected consumer has no valid conduit route"}
        origin, layout = wired_heater_blueprint(plan["position"], plan["route"], include_heater=False)
        response = post_blueprint(client, map_id, origin, layout)
        projects_raw = client.get("/api/v1/builder/projects", map_id=map_id)
        projects = projects_raw.get("projects") or [] if isinstance(projects_raw, dict) else []
        built = client.get("/api/v1/map/buildings", map_id=map_id)
        present = {(int((row.get("position") or {}).get("x") or -1),
                    int((row.get("position") or {}).get("z") or -1))
                   for row in list(projects) + list(built or [])
                   if str(row.get("def_name") or row.get("def")) in
                   {"PowerConduit", "HiddenConduit", "WaterproofConduit"}}
        missing = [cell for cell in plan["route"]
                   if (int(cell["x"]), int(cell["z"])) not in present]
        if missing:
            return {"applied": False, "reason": "Conduit route was only partly placed",
                    "missing_cells": missing[:8], "response": response}
        issued[f"power_connection:{key}"] = tick
        return {"applied": True, "consumer": key, "conduit_count": len(plan["route"]),
                "response": response}
    if choice == "build_power":
        options = details.get("power_source_options") or {}
        selected = str(details.get("power_source") or "")
        if selected not in (options.get("choices") or {}):
            return {"applied": False, "reason": "Laya did not select a live power option"}
        if selected == "defer":
            issued["power_strategy"] = tick
            return {"applied": True, "power_strategy": "defer"}
        if selected.startswith("research:"):
            target = selected.removeprefix("research:")
            if target not in live_research_options(snapshot):
                return {"applied": False, "reason": "Power research is no longer startable"}
            response = client.post("/api/v1/research/target", query={"name": target, "force": False})
            issued["power_strategy"] = tick
            issued[f"research:{target}"] = tick
            return {"applied": True, "power_strategy": selected, "response": response}
        name = selected.removeprefix("build:")
        plan = (options.get("plans") or {}).get(name)
        if plan is None:
            return {"applied": False, "reason": "Selected generator is unavailable"}
        materials = plan.get("materials") or {}
        stuff = next(iter(materials), None)
        result = place_checked_building(client, map_id, plan, anchor, stuff, snapshot=snapshot)
        if result.get("applied"):
            issued["power_strategy"] = tick
            issued[f"power_generator:{name}"] = tick
        return result
    if choice == "build_battery_shelter":
        options = dev.get("battery_shelter_options") or {}
        batteries = options.get("batteries") or []
        selected = str(details.get("battery_shelter_target") or (batteries[0].get("id") if batteries else ""))
        battery = next((row for row in batteries if str(row.get("id")) == selected), None)
        materials = options.get("materials") or {}
        material = str(details.get("battery_shelter_material") or next(iter(materials), ""))
        if battery is None or material not in materials:
            return {"applied": False, "reason": "The exposed battery or shelter material is no longer available"}
        point = battery.get("position") or {}
        origin = {"x": int(point["x"]) - 1, "z": int(point["z"]) - 1}
        result = post_blueprint(client, map_id, origin, battery_shelter_blueprint(material))
        issued["battery_shelter"] = tick
        return result
    if choice == "build_hitech_lab":
        result = post_blueprint(client, map_id, anchor, hitech_blueprint(), dx=10, dz=13)
        issued["hitech"] = tick
        return result
    if choice == "build_fabrication":
        result = post_blueprint(client, map_id, anchor, fabrication_blueprint(), dx=19, dz=13)
        issued["fabrication"] = tick
        return result
    if choice == "build_ship":
        result = post_blueprint(client, map_id, anchor, ship_blueprint(len(snapshot["colonists"])), dx=-5, dz=25)
        issued["ship"] = tick
        return result
    if choice.startswith("human_reproduction:"):
        _, first_id, second_id, approach = choice.split(":", 3)
        first_id_int, second_id_int = int(first_id), int(second_id)
        responses: list[Any] = []
        if approach == "TryForBaby" and snapshot["development"]["building_counts"].get("DoubleBed", 0) == 0:
            if not issued_recently(map_state, "reproduction_double_bed", tick, retry_ticks=60000):
                responses.append(post_blueprint(
                    client, map_id, anchor,
                    workshop_blueprint("DoubleBed", stuff="WoodLog"), dx=7, dz=5,
                ))
                issued["reproduction_double_bed"] = tick
        responses.append(client.post("/api/v1/map/colonists/reproduction", body={
            "map_id": map_id,
            "first_pawn_id": first_id_int,
            "second_pawn_id": second_id_int,
            "approach": approach,
        }))
        issued[f"human_reproduction:{first_id_int}:{second_id_int}"] = tick
        map_state["human_reproduction_plan"] = {
            "first": first_id_int, "second": second_id_int, "approach": approach,
        }
        return {"applied": True, "approach": approach, "responses": responses}
    if choice.startswith("income_"):
        income_strategy = choice.removeprefix("income_")
        strategy_names = {
            "drugs": "drugs", "tailoring": "tailoring", "art": "art",
            "livestock": "livestock", "biofuel": "biofuel", "mining": "mining",
            "crops": "crops", "brewing": "brewing", "travel_food": "travel_food",
            "orbital": "orbital", "organs": "organs",
        }
        if income_strategy not in strategy_names:
            raise bridge.RimApiError(f"Unknown income strategy: {income_strategy}")
        map_state["income_strategy"] = strategy_names[income_strategy]
        map_state["income_strategy_tick"] = tick
        issued[f"income:{income_strategy}"] = tick
        if income_strategy == "drugs":
            response = client.post("/api/v1/map/zone/growing", body={
                "map_id": map_id,
                "plant_def": "Plant_Psychoid",
                "point_a": position(map_state["growing_anchor"]["x"], map_state["growing_anchor"]["z"] + 10),
                "point_b": position(map_state["growing_anchor"]["x"] + 9, map_state["growing_anchor"]["z"] + 17),
            })
            return {"applied": True, "strategy": income_strategy, "response": response}
        if income_strategy == "tailoring":
            grow = client.post("/api/v1/map/zone/growing", body={
                "map_id": map_id,
                "plant_def": "Plant_Cotton",
                "point_a": position(map_state["growing_anchor"]["x"] + 11, map_state["growing_anchor"]["z"] + 10),
                "point_b": position(map_state["growing_anchor"]["x"] + 18, map_state["growing_anchor"]["z"] + 17),
            })
            bench = post_blueprint(client, map_id, anchor, workshop_blueprint("HandTailoringBench", stuff="WoodLog"), dx=16, dz=12)
            return {"applied": True, "strategy": income_strategy, "responses": [grow, bench]}
        if income_strategy == "art":
            existing = next((row for row in snapshot["development"].get("work_tables", [])
                             if row.get("thing_def") == "TableSculpting"), None)
            if existing:
                return {"applied": True, "strategy": income_strategy,
                        "phase": "existing_workshop", "workshop_id": existing.get("id")}
            response = post_blueprint(client, map_id, anchor, workshop_blueprint("TableSculpting", stuff="WoodLog"), dx=16, dz=16)
            return {"applied": True, "strategy": income_strategy, "phase": "build_workshop", "response": response}
        if income_strategy == "livestock":
            return {"applied": True, "strategy": income_strategy, "response": prioritize(client, snapshot, "Handling")}
        if income_strategy == "biofuel":
            response = select_research_if_available(client, "BiofuelRefining")
            return {"applied": bool(response.get("applied", True)), "strategy": income_strategy, "response": response}
        if income_strategy == "crops":
            response = client.post("/api/v1/map/zone/growing", body={
                "map_id": map_id,
                "plant_def": "Plant_Corn",
                "point_a": position(map_state["growing_anchor"]["x"] + 20, map_state["growing_anchor"]["z"]),
                "point_b": position(map_state["growing_anchor"]["x"] + 29, map_state["growing_anchor"]["z"] + 9),
            })
            return {"applied": True, "strategy": income_strategy, "response": response}
        if income_strategy == "brewing":
            grow = client.post("/api/v1/map/zone/growing", body={
                "map_id": map_id,
                "plant_def": "Plant_Hops",
                "point_a": position(map_state["growing_anchor"]["x"] + 20, map_state["growing_anchor"]["z"] + 11),
                "point_b": position(map_state["growing_anchor"]["x"] + 27, map_state["growing_anchor"]["z"] + 18),
            })
            research = select_research_if_available(client, "Brewing")
            return {"applied": True, "strategy": income_strategy, "responses": [grow, research]}
        if income_strategy == "travel_food":
            research = select_research_if_available(client, "PackagedSurvivalMeal")
            if not research.get("applied", True):
                research = select_research_if_available(client, "Pemmican")
            return {"applied": True, "strategy": income_strategy, "response": research}
        if income_strategy == "orbital":
            research = select_research_if_available(client, "MicroelectronicsBasics")
            return {"applied": bool(research.get("applied", True)), "strategy": income_strategy, "response": research}
        if income_strategy == "organs":
            return {
                "applied": True,
                "strategy": income_strategy,
                "note": "Organ harvesting remains per-prisoner and is offered only with doctor skill 8+, medicine, and explicit Laya selection.",
            }
        # Mine the compact local gold vein first. Long-range scanning is added to
        # the research route after local precious ore is exhausted.
        ores = snapshot["development"].get("ores", {}).get("ores", {})
        vein = ores.get("mineable_gold") or ores.get("mineable_silver") or {}
        cells = [int(value) for value in vein.get("cells", [])[:16]]
        if cells:
            width = int(snapshot["development"].get("ores", {}).get("map_width") or 250)
            xs = [cell % width for cell in cells]
            zs = [cell // width for cell in cells]
            response = client.post("/api/v1/order/designate/area", body={
                "map_id": map_id,
                "type": "mine",
                "point_a": position(min(xs), min(zs)),
                "point_b": position(max(xs), max(zs)),
            })
        else:
            response = select_research_if_available(client, "LongRangeMineralScanner")
        return {"applied": True, "strategy": income_strategy, "response": response}
    if choice == "build_income_infrastructure":
        income_strategy = str(map_state.get("income_strategy") or "")
        if income_strategy == "drugs":
            response = post_blueprint(client, map_id, anchor, workshop_blueprint("DrugLab"), dx=21, dz=16)
        elif income_strategy == "biofuel":
            response = post_blueprint(client, map_id, anchor, workshop_blueprint("BiofuelRefinery"), dx=21, dz=20)
        elif income_strategy == "brewing":
            layout = blueprint([
                building("Brewery", 0, 0, rotation=2),
                building("FermentingBarrel", 4, 0),
                building("FermentingBarrel", 5, 0),
                building("FermentingBarrel", 6, 0),
            ], 8, 3)
            response = post_blueprint(client, map_id, anchor, layout, dx=21, dz=24)
        elif income_strategy == "orbital":
            response = post_blueprint(client, map_id, anchor, orbital_trade_blueprint(), dx=21, dz=28)
        else:
            return {"applied": False, "reason": f"No separate infrastructure is required for {income_strategy}"}
        issued[f"income_infrastructure:{income_strategy}"] = tick
        return {"applied": True, "strategy": income_strategy, "response": response}
    if choice == "prepare_trade_rations":
        finished_now = set(dev.get("finished_research") or [])
        if "Pemmican" not in finished_now:
            current_project = str((dev.get("current_research") or {}).get("name") or "none").lower()
            if current_project != "none":
                return {"applied": False, "reason": f"Finish {current_project} before switching to Pemmican"}
            response = select_research_if_available(client, "Pemmican")
            if response.get("success") or response.get("applied"):
                issued["trade_rations_research"] = tick
            return {"applied": bool(response.get("success") or response.get("applied")),
                    "phase": "research", "response": response}
        table = next((row for row in dev.get("work_tables") or []
                      if str(row.get("thing_def") or "") in {"Campfire", "FueledStove", "ElectricStove"}), None)
        if table is None:
            return {"applied": False, "reason": "No completed campfire or stove for travel rations"}
        recipe = researched_travel_ration_recipe(client, table)
        if not recipe:
            return {"applied": False, "reason": "No researched travel-ration recipe on this table"}
        target = max(50, len(snapshot["colonists"]) * 5 + 16)
        response = ensure_bill(client, table, recipe, target)
        issued["trade_rations_bill"] = tick
        return {"applied": bool(response.get("success") or response.get("applied")),
                "phase": "bill", "recipe": recipe, "target_count": target, "response": response}
    if choice == "configure_income_production":
        income_strategy = str(map_state.get("income_strategy") or "")
        recipe_by_strategy = {
            "drugs": ("DrugLab", "Make_Flake", 50),
            "tailoring": ("HandTailoringBench", "Make_Duster", 10),
            "art": ("TableSculpting", "Make_SculptureSmall", 8),
            "biofuel": ("BiofuelRefinery", "Make_ChemfuelFromOrganics", 150),
            "brewing": ("Brewery", "Make_Wort", 50),
            "travel_food": ("FueledStove", "", 50),
        }
        table_def, recipe, target = recipe_by_strategy[income_strategy]
        table = next(
            (row for row in snapshot["development"]["work_tables"] if str(row.get("thing_def")) == table_def),
            None,
        )
        if table is None and income_strategy == "tailoring":
            table = next((row for row in snapshot["development"]["work_tables"] if row.get("thing_def") == "ElectricTailoringBench"), None)
        if table is None and income_strategy == "travel_food":
            table = next((row for row in snapshot["development"]["work_tables"] if row.get("thing_def") == "ElectricStove"), None)
        if table is None:
            return {"applied": False, "reason": f"No completed workshop for {income_strategy}"}
        if income_strategy == "travel_food":
            recipe = researched_travel_ration_recipe(client, table)
            if not recipe:
                return {"applied": False, "reason": "No researched travel-ration recipe on this table"}
        response = ensure_bill(client, table, recipe, target)
        issued[f"income_bills:{income_strategy}"] = tick
        return {"applied": True, "strategy": income_strategy, "response": response}
    if choice == "build_killbox":
        response = post_blueprint(client, map_id, anchor, killbox_blueprint(), dx=13, dz=-16)
        issued["killbox"] = tick
        return response
    if choice == "build_fallback_defense":
        response = post_blueprint(client, map_id, anchor, fallback_defense_blueprint(), dx=12, dz=-6)
        issued["fallback_defense"] = tick
        return response
    if choice == "build_turret_defense":
        response = post_blueprint(client, map_id, anchor, turret_defense_blueprint(), dx=12, dz=-10)
        issued["turret_defense"] = tick
        return response
    if choice == "build_mortar_post":
        response = post_blueprint(client, map_id, anchor, mortar_post_blueprint(), dx=-20, dz=-12)
        issued["mortar_post"] = tick
        return response
    if choice == "build_firefoam_defense":
        response = post_blueprint(client, map_id, anchor, workshop_blueprint("FirefoamPopper"), dx=5, dz=10)
        issued["firefoam_defense"] = tick
        return response
    if choice == "start_stonecutting":
        stone_type = str(details.get("stone_type") or map_state.get("stone_type") or "")
        if not stone_type:
            return {"applied": False, "reason": "Laya did not select a nearby stone type"}
        map_state["stone_type"] = stone_type
        finished = set(map(str, snapshot["development"]["finished_research"]))
        tables = [row for row in snapshot["development"]["work_tables"] if row.get("thing_def") == "TableStonecutter"]
        if "Stonecutting" not in finished:
            response = select_research_if_available(client, "Stonecutting")
            return {"applied": bool(response.get("applied", True)), "stone_type": stone_type, "phase": "research", "response": response}
        if not tables:
            response = post_blueprint(client, map_id, anchor, workshop_blueprint("TableStonecutter", stuff="WoodLog"), dx=16, dz=20)
            issued["stonecutting_table"] = tick
            return {"applied": True, "stone_type": stone_type, "phase": "build_table", "response": response}
        recipe = stonecutting_recipe(client, tables[0], stone_type)
        response = ensure_bill(client, tables[0], recipe, 300)
        issued["stonecutting_complete"] = tick
        return {"applied": True, "stone_type": stone_type, "recipe": recipe,
                "phase": "bill", "response": response}
    if choice == "start_taming":
        animal_id = details.get("tame_target")
        animal = next((a for a in details.get("tame_options", []) if int(a.get("id", -1)) == int(animal_id or -1)), None)
        if animal is None:
            return {"applied": False, "reason": "Laya did not select an available taming target"}
        live_animals = client.get("/api/v1/map/animals", map_id=map_id)
        live_animal = next((row for row in live_animals if int(row.get("id") or -1) == int(animal_id)), None)
        if not live_animal or not live_animal.get("can_be_designated_for_taming"):
            return {"applied": False, "reason": "The chosen animal is no longer tameable"}
        if live_animal.get("requires_pen") is not False and not live_animal.get("has_suitable_enclosed_pen"):
            return {"applied": False, "reason": "A completed, reachable enclosed pen is needed before taming this roaming animal"}
        response = client.post("/api/v1/map/animal/tame", body={"map_id": map_id, "animal_id": int(animal_id)})
        issued[f"tame:{animal_id}"] = tick
        issued["priority:Handling"] = tick
        handling = prioritize(client, snapshot, "Handling")
        return {"applied": True, "animal": animal, "responses": [response, handling]}
    if choice == "tame_wild_human":
        person_id = details.get("wild_human_target")
        person = next((row for row in details.get("wild_human_options") or []
                       if int(row.get("id") or -1) == int(person_id or -1)), None)
        if person is None:
            return {"applied": False, "reason": "Laya did not select a live wild person"}
        live_people = client.get("/api/v1/map/wild-humans", map_id=map_id)
        if not any(int(row.get("id") or -1) == int(person_id) and not row.get("downed")
                   for row in live_people):
            return {"applied": False, "reason": "The selected wild person left or can no longer be tamed"}
        response = client.post("/api/v1/map/wild-human/tame", body={
            "map_id": map_id, "pawn_id": int(person_id)})
        issued[f"wild_human_tame:{person_id}"] = tick
        return {"applied": True, "person": person, "responses": [response, prioritize(client, snapshot, "Handling")]}
    if choice.startswith("breed_animals:"):
        species = choice.split(":", 1)[1]
        issued[f"breed:{species}"] = tick
        map_state["animal_breeding_plan"] = species
        return {"applied": True, "species": species, "response": prioritize(client, snapshot, "Handling")}
    if choice == "process_mechanoids":
        tables = [row for row in snapshot["development"]["work_tables"] if row.get("thing_def") == "TableMachining"]
        if tables:
            response = ensure_bill(client, tables[0], "SmashCorpseMechanoid", 10)
        elif "Machining" in set(map(str, snapshot["development"]["finished_research"])):
            response = post_blueprint(client, map_id, anchor, workshop_blueprint("TableMachining", stuff="Steel"), dx=21, dz=12)
        else:
            response = select_research_if_available(client, "Machining")
        issued["mech_processing"] = tick
        return {"applied": True, "response": response}
    if choice.startswith("prisoner_policy:"):
        _, pawn_id_text, policy = choice.split(":", 2)
        pawn_id = int(pawn_id_text)
        if policy in {"organs_nonlethal", "organs_lethal"}:
            organs = ["Kidney", "Lung"] if policy == "organs_nonlethal" else ["Heart"]
            responses = [
                client.post("/api/v1/pawn/prisoner/organ-plan", body={
                    "prisoner_pawn_id": pawn_id,
                    "organ_def_name": organ,
                    "allow_lethal": policy == "organs_lethal",
                })
                for organ in organs
            ]
            map_state.setdefault("prisoner_plans", {})[str(pawn_id)] = policy
            issued[f"prisoner:{pawn_id}:{policy}"] = tick
            return {"applied": True, "prisoner_id": pawn_id, "policy": policy, "organs": organs, "responses": responses}
        response = client.post("/api/v1/pawn/prisoner/policy", body={
            "prisoner_pawn_id": pawn_id,
            "policy": policy,
        })
        map_state.setdefault("prisoner_plans", {})[str(pawn_id)] = policy
        issued[f"prisoner:{pawn_id}:{policy}"] = tick
        return {"applied": True, "prisoner_id": pawn_id, "policy": policy, "response": response}
    if choice.startswith("trade_to:"):
        _, destination_id, sale = choice.split(":", 2)
        sale_categories = ["none"] if sale == "funds" else available_sale_categories(snapshot) if sale == "mixed" else [sale]
        purchase = str(details.get("trade_purchase") or "none")
        sale_prisoner_ids = [
            int(pawn_id) for pawn_id, policy in (map_state.get("prisoner_plans") or {}).items()
            if policy == "sell" and any(int(p.get("id", -1)) == int(pawn_id) for p in snapshot.get("combat", {}).get("prisoners", []))
        ]
        response = client.post("/api/v1/world/caravan/trade/start", body={
            "map_id": map_id,
            "destination_settlement_id": int(destination_id),
            "minimum_home_defenders": 2,
            "minimum_food_at_home": 20,
            "minimum_medicine_at_home": 8,
            "sale_categories": sale_categories,
            "purchase_priorities": [] if purchase == "none" else [purchase],
            "prisoner_ids": sale_prisoner_ids,
        })
        issued["trade_caravan"] = tick
        map_state["caravan_plan"] = {"kind": "trade", "destination_id": int(destination_id), "purchase": purchase}
        return response
    if choice.startswith("raid_to:"):
        destination_id = int(choice.split(":", 1)[1])
        destination = next((d for d in snapshot["development"].get("raid_destinations", []) if int(d.get("settlement_id", -1)) == destination_id), {})
        response = client.post("/api/v1/world/caravan/raid/start", body={
            "map_id": map_id,
            "destination_settlement_id": destination_id,
            "minimum_home_defenders": 2,
            "minimum_food_at_home": 30,
            "minimum_medicine_at_home": 10,
            "allow_starting_war": bool(destination.get("would_start_war")),
        })
        issued["raid_caravan"] = tick
        map_state["caravan_plan"] = {"kind": "raid", "destination_id": destination_id}
        return response
    if choice == "prepare_trade_caravan":
        # The endpoint refuses unsafe parties and keeps at least two healthy
        # defenders, food and medicine at home.
        destination = next((row for row in snapshot["development"].get("trade_destinations", []) if row.get("can_trade_now")), None)
        if destination is None:
            return {"applied": False, "reason": "No safe trading destination is currently available"}
        response = client.post("/api/v1/world/caravan/trade/start", body={
            "map_id": map_id,
            "destination_settlement_id": int(destination["settlement_id"]),
            "minimum_home_defenders": 2,
            "minimum_food_at_home": 20,
            "minimum_medicine_at_home": 8,
        })
        issued["trade_caravan"] = tick
        return response
    if choice == "prioritize_construction":
        worker_id = details.get("worker_pawn")
        if worker_id is None:
            worker = bridge.choose_worker(snapshot["colonists"], "Construction")
            worker_id = worker.get("id") if worker else None
        doctor_change = free_cold_shelter_builder(client, snapshot, int(worker_id)) if worker_id is not None else None
        result = prioritize(client, snapshot, "Construction", worker_id)
        if doctor_change is not None:
            result["cold_shelter_staffing"] = doctor_change
        issued["priority:Construction"] = tick
        return result
    if choice == "prioritize_firefighting":
        available_ids = set(details.get("firefighter_worker_ids") or [])
        eligible = [pawn for pawn in snapshot["colonists"] if pawn.get("id") in available_ids
                    and int(((pawn.get("work_priorities") or {}).get("Firefighter") or {}).get("priority") or 0) != 1]
        if not eligible:
            return {"applied": False, "reason": "No capable colonist still needs Firefighter priority 1"}
        responses = []
        for firefighter in eligible:
            result = prioritize(client, snapshot, "Firefighter", int(firefighter["id"]))
            responses.append(result)
            if result.get("applied"):
                issued[f"firefighter:{int(firefighter['id'])}"] = tick
        return {"applied": any(result.get("applied") for result in responses),
                "assigned_ids": [int(pawn["id"]) for pawn in eligible], "responses": responses}
    if choice == "set_work_priority":
        work = str(details.get("work_type") or "")
        pawn_id = int(details.get("worker_pawn") or 0)
        level = int(details.get("work_priority") or 0)
        pawn = next((c for c in snapshot.get("colonists", []) if int(c.get("id") or 0) == pawn_id), None)
        row = ((pawn or {}).get("work_priorities") or {}).get(work)
        if work not in live_work_options(snapshot) or pawn is None or pawn.get("downed") or not isinstance(row, dict) or row.get("disabled") or level not in (1, 2, 3, 4):
            raise bridge.RimApiError("Selected work assignment is no longer feasible")
        if int(row.get("priority") or 0) == level:
            return {"applied": False, "reason": "Work priority is already at this level"}
        result = client.post("/api/v1/colonist/work-priority", body={"id": pawn_id, "work": work, "priority": level})
        issued["work_priority_change"] = tick
        return {"applied": True, "colonist": pawn.get("name"), "work": work, "priority": level, "response": result}
    if choice in {"prioritize_construction_project", "prioritize_thermal_project"}:
        project_key = "thermal_project" if choice == "prioritize_thermal_project" else "construction_project"
        project_id = details.get(project_key)
        worker_id = details.get("worker_pawn")
        if project_id is None and choice == "prioritize_thermal_project":
            options = details.get("thermal_project_options") or []
            if len(options) == 1:
                project_id = options[0].get("thing_id")
        if project_id is None or worker_id is None:
            return {"applied": False, "reason": "Laya did not select both an exact project and builder"}
        project = next((row for row in dev.get("construction_projects") or []
                        if str(row.get("thing_id")) == str(project_id)), None)
        worker = next((row for row in snapshot.get("colonists") or []
                       if str(row.get("id")) == str(worker_id)), None)
        if (project is not None and worker is not None and
                int(((worker.get("skills") or {}).get("Construction") or {}).get("level") or 0)
                < int(project.get("minimum_construction_skill") or 0)):
            return {"applied": False, "reason": "Selected builder cannot complete this project's skill requirement"}
        doctor_change = free_cold_shelter_builder(client, snapshot, int(worker_id))
        priority = prioritize(client, snapshot, "Construction", int(worker_id))
        response = client.post("/api/v1/builder/prioritize", body={
            "map_id": map_id,
            "project_thing_id": int(project_id),
            "pawn_id": int(worker_id),
        })
        if isinstance(response, dict) and response.get("applied") is False:
            map_state.setdefault("failed_construction_projects", {})[str(project_id)] = {
                "tick": tick,
                "wood": int((snapshot["development"].get("item_counts") or {}).get("WoodLog") or 0),
            }
            return {"applied": False, "project_id": int(project_id),
                    "builder_id": int(worker_id), "reason": response.get("reason"),
                    "responses": [priority, response]}
        issued["thermal_project_priority" if choice == "prioritize_thermal_project"
               else "construction_project_priority"] = tick
        issued[f"construction_project:{project_id}"] = tick
        return {"applied": True, "project_id": int(project_id), "builder_id": int(worker_id),
                "cold_shelter_staffing": doctor_change, "responses": [priority, response]}
    if choice == "prioritize_research":
        result = dedicate_researcher(client, snapshot)
        if result.get("applied"):
            issued["priority:Research"] = tick
            map_state["reserved_researcher_id"] = int(result["pawn_id"])
        return result
    if choice == "prioritize_cooking":
        result = prioritize(client, snapshot, "Cooking", avoid_ids=routine_avoid)
        issued["priority:Cooking"] = tick
        return result
    if choice == "rebalance_cooking":
        selected = str(details.get("cooking_rebalance_choice") or "")
        plan = (details.get("cooking_rebalance_options") or {}).get(selected)
        if plan is None or selected not in cooking_rebalance_options(snapshot, reserved_researcher_id):
            return {"applied": False, "reason": "The selected cooking staffing change is no longer available"}
        pawn_id = int(plan["pawn_id"])
        work = str(plan["work"])
        priority = int(plan["priority"])
        response = client.post("/api/v1/colonist/work-priority", body={
            "id": pawn_id, "work": work, "priority": priority,
        })
        issued["cooking_rebalance"] = tick
        return {"applied": True, "worker": pawn_id, "work": work,
                "priority": priority, "response": response}
    if choice == "prioritize_growing":
        result = prioritize(client, snapshot, "Growing", avoid_ids=routine_avoid)
        issued["priority:Growing"] = tick
        return result
    if choice == "prioritize_hauling":
        result = prioritize(client, snapshot, "Hauling", avoid_ids=routine_avoid)
        issued["priority:Hauling"] = tick
        return result
    if choice == "prioritize_hunting":
        result = prioritize(client, snapshot, "Hunting", avoid_ids=routine_avoid)
        issued["priority:Hunting"] = tick
        return result
    if choice == "prioritize_handling":
        result = prioritize(client, snapshot, "Handling", avoid_ids=routine_avoid)
        issued["priority:Handling"] = tick
        return result
    if choice == "prioritize_plant_cutting":
        result = prioritize(client, snapshot, "PlantCutting", avoid_ids=routine_avoid)
        issued["priority:PlantCutting"] = tick
        return result
    if choice == "prioritize_cleaning":
        result = prioritize(client, snapshot, "Cleaning", avoid_ids=routine_avoid)
        issued["priority:Cleaning"] = tick
        return result
    if choice == "prioritize_rescue":
        result = prioritize(client, snapshot, "BasicWorker")
        issued["priority:BasicWorker"] = tick
        return result
    if choice == "rescue_neutral_arrival":
        options = snapshot["development"].get("neutral_rescue_options") or {}
        rescuers = snapshot["development"].get("neutral_rescuers") or {}
        patient_id = str(details.get("neutral_patient") or next(iter(options), ""))
        rescuer_id = str(details.get("neutral_rescuer") or next(iter(rescuers), ""))
        if patient_id not in options or rescuer_id not in rescuers:
            return {"applied": False, "reason": "The selected visitor or rescuer is no longer available"}
        visitor = next((pawn for pawn in (snapshot.get("combat") or {}).get("neutral_downed") or []
                        if str(pawn.get("id")) == patient_id and pawn.get("is_downed") and not pawn.get("is_dead")), None)
        if visitor is None:
            return {"applied": False, "reason": "The visitor is no longer downed on this map"}
        sheltered_ids = {
            int(bed_id) for room in snapshot["development"].get("rooms") or []
            if not room.get("touches_map_edge") and int(room.get("open_roof_count") or 0) == 0
            for bed_id in room.get("contained_beds_ids") or []
        }
        beds = [bed for bed in snapshot["development"].get("buildings") or []
                if bed.get("id") is not None and bed.get("def") in {"Bed", "HospitalBed", "SleepingSpot"}
                and not bed.get("for_prisoners")]
        if not beds:
            return {"applied": False, "reason": "No completed bed is available for the visitor"}
        place = visitor.get("position") or {}
        bed = min(beds, key=lambda row: (
            int(row["id"]) not in sheltered_ids,
            not bool(row.get("medical")), row.get("def") == "SleepingSpot",
            (bridge.first_number((row.get("position") or {}).get("x")) - bridge.first_number(place.get("x"))) ** 2
            + (bridge.first_number((row.get("position") or {}).get("z")) - bridge.first_number(place.get("z"))) ** 2,
        ))
        response = client.post("/api/v1/pawn/job", body={
            "pawn_id": int(rescuer_id), "job_def": "Rescue",
            "target_thing_id": int(patient_id), "target_thing_id_b": int(bed["id"]),
        })
        issued[f"neutral_rescue:{patient_id}"] = tick
        return {"applied": True, "visitor_id": int(patient_id),
                "rescuer_id": int(rescuer_id), "bed_id": int(bed["id"]), "response": response}
    if choice in {"rescue_downed_colonist", "tend_colonist"}:
        completed_beds = [building for building in snapshot["development"].get("buildings") or []
                          if str(building.get("def") or building.get("thing_def") or "") in {
                              "Bed", "HospitalBed", "SleepingSpot",
                          } and building.get("id") is not None]
        patients = [pawn for pawn in snapshot["colonists"] if (
            pawn.get("downed") and not patient_in_completed_bed(pawn, snapshot, completed_beds)
            if choice == "rescue_downed_colonist" else
            pawn.get("tendable_now") or bridge.first_number(pawn.get("bleeding_rate")) > 0.05
        )]
        if not patients:
            return {"applied": False, "reason": "Patient no longer needs the selected care"}
        selected_id = details.get("medical_patient")
        patient = next((pawn for pawn in patients if str(pawn["id"]) == str(selected_id)), None)
        patient = patient or min(patients, key=lambda pawn: (
            bridge.first_number(pawn.get("health"), 1), -bridge.first_number(pawn.get("bleeding_rate")),
        ))
        helpers = [pawn for pawn in snapshot["colonists"] if pawn["id"] != patient["id"]
                   and not pawn.get("downed") and bridge.first_number(pawn.get("health"), 1) >= 0.5
                   and bridge.first_number((pawn.get("capacities") or {}).get("moving"), 1) >= 0.6]
        if choice == "tend_colonist":
            helpers = [pawn for pawn in helpers if isinstance((pawn.get("work_priorities") or {}).get("Doctor"), dict)
                       and not pawn["work_priorities"]["Doctor"].get("disabled")]
        if not helpers:
            return {"applied": False, "reason": "No mobile helper is available"}
        patient_pos = patient.get("position") or {}
        helper = max(helpers, key=lambda pawn: (
            int(((pawn.get("skills") or {}).get("Medicine") or {}).get("level") or 0) if choice == "tend_colonist" else 0,
            -abs(bridge.first_number((pawn.get("position") or {}).get("x")) - bridge.first_number(patient_pos.get("x")))
            -abs(bridge.first_number((pawn.get("position") or {}).get("z")) - bridge.first_number(patient_pos.get("z"))),
        ))
        if choice == "tend_colonist":
            response = client.post("/api/v1/pawn/medical/tend", body={
                "patient_pawn_id": int(patient["id"]), "doctor_pawn_id": int(helper["id"]),
            })
            issued["direct_tend"] = tick
        else:
            beds = completed_beds
            if not beds:
                return {"applied": False, "reason": "No completed bed remains"}
            bed = min(beds, key=lambda building: (
                not bool(building.get("medical")),
                str(building.get("def") or building.get("thing_def")) == "SleepingSpot",
                (bridge.first_number((building.get("position") or {}).get("x")) - bridge.first_number(patient_pos.get("x"))) ** 2
                + (bridge.first_number((building.get("position") or {}).get("z")) - bridge.first_number(patient_pos.get("z"))) ** 2,
            ))
            response = client.post("/api/v1/pawn/job", body={
                "pawn_id": int(helper["id"]), "job_def": "Rescue", "target_thing_id": int(patient["id"]),
                "target_thing_id_b": int(bed["id"]),
            })
            issued["direct_rescue"] = tick
        return {"applied": True, "patient": patient.get("name"), "helper": helper.get("name"), "response": response}
    if choice == "prioritize_doctor":
        result = prioritize(client, snapshot, "Doctor")
        issued["priority:Doctor"] = tick
        return result
    if choice in {"designate_safe_hunting", "consider_dangerous_hunt"}:
        risky = choice == "consider_dangerous_hunt"
        if risky and details.get("dangerous_hunt_decision") != "proceed":
            issued["dangerous_hunt_review"] = tick
            return {"applied": False, "reason": "Laya deferred the dangerous hunt after considering the colony-wide retaliation risk"}
        animal_id = details.get("risky_hunt_target" if risky else "hunt_target")
        animal = next((a for a in details.get("risky_hunt_options" if risky else "hunt_options", [])
                       if int(a.get("id", -1)) == int(animal_id or -1)), None)
        if animal is None:
            return {"applied": False, "reason": "Laya did not select an available hunting target"}
        result = client.post("/api/v1/map/animal/hunt", body={"map_id": map_id, "animal_id": int(animal_id)})
        issued[f"hunt:{animal_id}"] = tick
        issued["dangerous_hunt_review" if risky else "safe_hunting"] = tick
        issued["priority:Hunting"] = tick
        hunting = prioritize(client, snapshot, "Hunting", avoid_ids=routine_avoid)
        return {"applied": True, "animal": animal, "responses": [result, hunting]}
    if choice == "leave_wildlife_alone":
        issued["wildlife_pause"] = tick
        return {"applied": False, "reason": "Laya chose to leave nearby wildlife alone for now"}
    if choice == "harvest_food_crops_early":
        crop_type = str(details.get("early_crop_type") or "")
        selected = (details.get("early_crop_options") or {}).get(crop_type)
        if not selected:
            return {"applied": False, "reason": "Laya did not select a harvestable edible crop"}
        batch = max(1, min(40, int(details.get("early_crop_batch") or 10)))
        plant_ids = list(map(int, (selected.get("ids") or [])[:batch]))
        if not plant_ids:
            return {"applied": False, "reason": "Selected crops have already been marked for early harvest"}
        try:
            result = client.post("/api/v1/map/plants/harvest", body={"map_id": map_id, "plant_ids": plant_ids})
        except bridge.RimApiError as exc:
            if "No selected mature plants could be designated" not in str(exc):
                raise
            issued["early_crop_harvest"] = tick
            for plant_id in plant_ids:
                issued[f"early_crop:{plant_id}"] = tick
            return {"applied": False, "reason": "Selected mature crops were already marked or harvested"}
        issued["early_crop_harvest"] = tick
        for plant_id in plant_ids:
            issued[f"early_crop:{plant_id}"] = tick
        growing = prioritize(client, snapshot, "PlantCutting", details.get("early_crop_worker"))
        return {"applied": True, "crop_type": crop_type, "plant_count": len(plant_ids),
                "worker": details.get("early_crop_worker"),
                "average_growth": selected.get("average_growth"), "responses": [result, growing]}
    if choice == "harvest_local_plants":
        plant_type = str(details.get("wild_plant_type") or "")
        selected = (details.get("wild_plant_options") or {}).get(plant_type)
        if not selected:
            return {"applied": False, "reason": "Laya did not select an available mature wild plant type"}
        worker_id = details.get("wild_plant_worker")
        worker = next((pawn for pawn in snapshot.get("colonists", [])
                       if str(pawn.get("id")) == str(worker_id)), None)
        plants_by_id = {int(plant["thing_id"]): plant for plant in snapshot["development"].get("plants", [])
                        if plant.get("thing_id") is not None}
        plant_ids = [int(plant_id) for plant_id in selected.get("ids", [])
                     if int(plant_id) in plants_by_id and not bridge.combat_planner.errand_exposed(
                         snapshot, plants_by_id[int(plant_id)].get("position"),
                         worker.get("position") if worker else None)][:60]
        if not plant_ids:
            return {"applied": False, "reason": "Selected plants are exposed to live hostiles"}
        result = client.post("/api/v1/map/plants/harvest", body={
            "map_id": map_id,
            "plant_ids": plant_ids,
        })
        issued["harvest"] = tick
        for plant_id in plant_ids:
            issued[f"wild_plant:{plant_id}"] = tick
        cutting = prioritize(client, snapshot, "PlantCutting", details.get("wild_plant_worker"))
        return {"applied": True, "plant_type": plant_type, "worker": details.get("wild_plant_worker"),
                "expected_yield": selected.get("expected_yield"),
                "responses": [result, cutting]}
    if choice == "harvest_nearby_trees":
        tree_type = str(details.get("tree_type") or "")
        selected = (details.get("tree_options") or {}).get(tree_type)
        if not selected:
            return {"applied": False, "reason": "Laya did not select an available nearby tree species"}
        plants_by_id = {int(plant["thing_id"]): plant for plant in snapshot["development"].get("plants", [])
                        if plant.get("thing_id") is not None}
        anchor = map_state["anchor"]
        ids = sorted((int(plant_id) for plant_id in selected.get("ids", [])), key=lambda plant_id:
                     squared_distance((plants_by_id.get(plant_id) or {}).get("position") or anchor, anchor))[:8]
        if not ids:
            return {"applied": False, "reason": "Selected trees have already been cut"}
        live_raw = client.get("/api/v1/map/plants", map_id=map_id)
        live = {int(row["thing_id"]): row for row in live_raw if row.get("thing_id") is not None}
        ids = [plant_id for plant_id in ids if plant_id in live
               and live[plant_id].get("harvestable_now")
               and not live[plant_id].get("is_designated_for_harvest")]
        if not ids:
            issued["wood_harvest"] = tick
            return {"applied": False, "reason": "The selected trees are already designated or no longer mature"}
        result = client.post("/api/v1/map/plants/harvest", body={"map_id": map_id, "plant_ids": ids})
        issued["wood_harvest"] = tick
        for plant_id in ids:
            issued[f"tree:{plant_id}"] = tick
        return {"applied": True, "tree_type": tree_type, "trees": ids, "response": result}
    if choice == "hold_survival":
        return {"applied": False, "reason": "Survival work already issued; waiting for colonists"}
    raise bridge.RimApiError(f"Unknown colony director action: {choice}")


def run_development_cycle(client: bridge.RimApiClient, agent: Any, state: dict[str, Any], state_path: Path, log_path: Path) -> dict[str, Any]:
    snapshot = collect_development(client, bridge.collect_snapshot(client))
    player_preferences = laya_preferences.load_preferences()
    snapshot["development"]["user_preferences"] = player_preferences
    seed = str(snapshot["map"].get("seed") or snapshot["map"]["id"])
    map_state = map_state_for_snapshot(state, snapshot)
    snapshot["development"]["shelter_exposure_days"] = max(
        0.0, (int(snapshot["game"].get("tick") or 0) - int(map_state.get("first_seen_tick") or 0)) / 60000.0
    )
    snapshot["development"]["income_strategy"] = map_state.get("income_strategy")
    snapshot["development"]["prisoner_plans"] = map_state.get("prisoner_plans", {})
    snapshot["development"]["doctrine"] = map_state.get("doctrine", {})
    snapshot["development"]["doctrine_history"] = (map_state.get("doctrine_history") or [])[-3:]
    snapshot["development"]["trade_ledger"] = (map_state.get("trade_ledger") or [])[-8:]
    snapshot["development"]["economic_outlook"] = strategy.economic_outlook(
        map_state.get("doctrine") or {}, {
            **snapshot["development"],
            "population": len(snapshot.get("colonists") or []),
            "resources": snapshot.get("map", {}).get("resources") or {},
        })
    snapshot["development"]["doctrine_audit"] = map_state.get("doctrine_audit", {})
    snapshot["development"]["recent_decisions"] = (map_state.get("recent_decisions") or [])[-2:]
    # Existing colonies may have an older, already issued house at their saved
    # anchor. Never move all future building plans away from that house while
    # migrating to the stricter site check; it applies to new houses only.
    existing_house_plan = "starter_base" in (map_state.get("issued") or {})
    if existing_house_plan and "anchor" in map_state:
        map_state.setdefault("starter_site_verified", True)
    if ("anchor" not in map_state or "growing_anchor" not in map_state
            or (not existing_house_plan and map_state.get("starter_site_verified") is not True)):
        center = anchor_from_snapshot(snapshot)
        terrain = client.get("/api/v1/map/terrain", map_id=snapshot["map"]["id"])
        safe_site = find_dry_starter_site(terrain, center, snapshot["development"], map_state)
        if safe_site is None:
            snapshot.setdefault("warnings", []).append("No fully dry 7x7 starter site was found near the landing supplies")
        map_state["starter_site_verified"] = safe_site is not None
        if not existing_house_plan and (safe_site is not None or "anchor" not in map_state):
            map_state["anchor"] = safe_site or center
        growing_center = {"x": max(12, center["x"] - 24), "z": center["z"]}
        map_state.setdefault(
            "growing_anchor",
            find_terrain_rect(terrain, growing_center, 10, 8, {"Soil", "SoilRich"}, radius=45) or growing_center,
        )
    snapshot["development"]["base_anchor"] = map_state["anchor"]
    retire_starter_sleeping_spots(client, snapshot, map_state, log_path)
    candidates, details = candidate_actions(client, snapshot, map_state)
    candidates = laya_preferences.filter_candidates(candidates, player_preferences)
    candidates, blocked_actions = filter_backed_off_choices(map_state, candidates)
    if not candidates:
        candidates = ["hold_survival"]
    if blocked_actions:
        snapshot["development"]["temporarily_blocked_actions"] = {
            choice: round(remaining, 1) for choice, remaining in blocked_actions.items()
        }
    decision = choose_action(agent, snapshot, candidates)
    details = merge_decision_details(details, decision)
    choice = str(decision["choice"])
    try:
        result = execute_action(client, snapshot, map_state, choice, details)
    except bridge.RimApiError as exc:
        if (choice in {"prioritize_construction_project", "prioritize_thermal_project"}
                and details.get("thermal_project" if choice == "prioritize_thermal_project" else "construction_project") is not None
                and "/api/v1/builder/prioritize" in str(exc)):
            failed_id = details["thermal_project" if choice == "prioritize_thermal_project" else "construction_project"]
            map_state.setdefault("failed_construction_projects", {})[str(failed_id)] = {
                "tick": int(snapshot["game"].get("tick") or 0),
                "wood": int((snapshot["development"].get("item_counts") or {}).get("WoodLog") or 0),
            }
        failure = register_action_failure(map_state, choice, exc)
        result = {
            "applied": False,
            "skipped": "api_error_backoff",
            "error": str(exc),
            "failure_count": failure["count"],
            "retry_in_seconds": round(float(failure["retry_after"]) - time.time(), 1),
        }
    else:
        if choice in {"prioritize_construction_project", "prioritize_thermal_project"}:
            project_id = details.get("thermal_project" if choice == "prioritize_thermal_project" else "construction_project")
            if project_id is not None and isinstance(result, dict) and result.get("applied"):
                map_state.setdefault("failed_construction_projects", {}).pop(str(project_id), None)
        if (choice.startswith("income_") and choice.removeprefix("income_") in strategy.DIRECT_INCOME_PLANS
                and isinstance(result, dict) and result.get("applied")):
            map_state["income_plan_started"] = choice.removeprefix("income_")
        clear_action_failure(map_state, choice)
    try:
        publish_overlay(client, snapshot, candidates, decision)
    except bridge.RimApiError as exc:
        snapshot.setdefault("warnings", []).append(f"Overlay: {exc}")
    record = {
        "timestamp": bridge.utc_now(),
        "mode": "colony-director",
        "goal": str((map_state.get("doctrine") or {}).get("endgame") or "self-sufficient_colony"),
        "map_seed": seed,
        "anchor": map_state["anchor"],
        "candidates": candidates,
        "decision": decision,
        "result": result,
    }
    map_state.setdefault("recent_decisions", []).append({
        "action": choice,
        "applied": bool(result.get("applied")) if isinstance(result, dict) else True,
        "error": str(result.get("error") or "")[:80] if isinstance(result, dict) else "",
    })
    map_state["recent_decisions"] = map_state["recent_decisions"][-4:]
    if player_preferences.get("technical_logging"):
        record["technical"] = {"snapshot": snapshot, "details": details}
    save_state(state_path, state)
    bridge.append_log(log_path, record)
    return record


def _event_quest(context: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    quests = [row for row in context.get("active_quests") or [] if isinstance(row, dict)]
    event_id = event.get("id") if event.get("source") == "quest" else None
    if event_id is not None:
        exact = next((row for row in quests if int(row.get("id", -1)) == int(event_id)), None)
        if exact:
            return exact
        return None
    if event.get("source") == "kidnapped":
        return next(iter(events.matching_rescue_quests(event, context)), None)
    return None


def live_purchase_options(trader: dict[str, Any], population: int) -> dict[str, str]:
    """Only offer categories backed by actual stock on the selected trader."""
    options = {"none": "Buy nothing; sell surplus or preserve silver."}
    for item in trader.get("stock") or []:
        name = str(item.get("def_name") or "").lower()
        label = str(item.get("label") or name)
        value = float(item.get("market_value") or 0)
        summary = f"{label} x{item.get('count')}, base value {value:.0f} each"
        if item.get("humanlike"):
            skills = ", ".join(map(str, (item.get("skills") or [])[:5]))
            options["slaves"] = (f"Potential new colonist: {summary}; health {item.get('health')}; "
                                  f"skills {skills}. Buying needs food, housing and safe silver reserves; "
                                  f"population now {population}.")
        elif item.get("animal"):
            options["livestock"] = f"Animal for breeding, products, hauling or companionship: {summary}."
        elif "medicine" in name or "neutroamine" in name:
            options["medicine"] = summary
        elif "componentadvanced" in name:
            options["advanced_components"] = summary
        elif "component" in name:
            options["components"] = summary
        elif any(word in name for word in ("meal", "rice", "corn", "potato", "pemmican", "berry")):
            options["food"] = summary
        elif any(word in name for word in ("armor", "helmet", "vest")):
            options["armor"] = summary
        elif any(word in name for word in ("rifle", "revolver", "pistol", "shotgun", "smg", "sword")):
            options["weapons"] = summary
        elif "plasteel" in name:
            options["plasteel"] = summary
    return options


def verified_trade_options(preview: dict[str, Any], side: str) -> dict[str, str]:
    """Expose only categories that the game's live trade deal can fulfill."""
    rows = preview.get("sale_options" if side == "sale" else "purchase_options") or []
    return {str(row["category"]): (
        f"{row.get('example')} x{int(row.get('maximum_units') or 0)}, "
        f"about {float(row.get('unit_price') or 0):.0f} silver per unit"
    ) for row in rows if int(row.get("maximum_units") or 0) > 0 and row.get("category")}


def preview_live_traders(client: bridge.RimApiClient, context: dict[str, Any],
                         map_id: int, reserve: int) -> list[dict[str, Any]]:
    """A listed visitor is not necessarily an actionable trading opportunity."""
    viable = []
    for trader in context.get("trade_opportunities") or []:
        trader_id = str(trader.get("id") or "")
        if not trader_id:
            continue
        try:
            preview = client.get("/api/v1/trade/preview", map_id=map_id, trader_id=trader_id,
                                 minimum_silver_reserve=reserve, maximum_spend=4000)
        except bridge.RimApiError as exc:
            context.setdefault("trade_preview_errors", []).append(f"{trader_id}: {exc}")
            continue
        if verified_trade_options(preview, "sale") or verified_trade_options(preview, "purchase"):
            viable.append({**trader, "preview": preview})
    return viable


def _execute_event_response(
    client: bridge.RimApiClient,
    snapshot: dict[str, Any],
    map_state: dict[str, Any],
    event: dict[str, Any],
    context: dict[str, Any],
    response: str,
    details: dict[str, Any],
) -> Any:
    map_id = int(snapshot["map"]["id"])
    tick = int(snapshot["game"].get("tick") or 0)
    if response in {"observe_event", "skip_trade", "defer_rescue", "defer_quest", "evaluate_animals", "evaluate_recruit", "ask_laya_generic"}:
        return {"applied": False, "reason": response}
    if response == "rescue_arrival":
        return {"applied": False, "reason": "Downed neutral rescue is offered as a persistent colony action with a specific visitor, rescuer and bed."}
    if response == "delegate_to_combat_planner":
        return {"applied": False, "reason": "The combat planner owns verified hostile pawns and will run on the next combat tick."}
    if response == "prepare_undrafted":
        commands = []
        for pawn in snapshot.get("combat", {}).get("colonists", []):
            if pawn.get("is_drafted"):
                commands.append(client.post("/api/v1/pawn/edit/status", body={"pawn_id": int(pawn["id"]), "is_drafted": False}))
        if snapshot.get("game", {}).get("is_paused"):
            commands.append(client.post("/api/v1/game/speed", query={"speed": 1}))
        return {"applied": bool(commands), "responses": commands}
    if response == "prioritize_firefighting":
        return prioritize(client, snapshot, "Firefighter")
    if response == "prioritize_medical":
        return prioritize(client, snapshot, "Doctor")
    if response == "emergency_harvest":
        plants = snapshot.get("development", {}).get("plants", [])
        ids = [
            int(row["id"]) for row in plants
            if row.get("id") is not None and (
                row.get("can_harvest") or row.get("is_harvestable")
                or float(row.get("growth") or row.get("growth_progress") or 0) >= 0.95
            )
        ][:120]
        if not ids:
            return {"applied": False, "reason": "No verified mature plant is available for emergency harvest."}
        return client.post("/api/v1/map/plants/harvest", body={"map_id": map_id, "plant_ids": ids})
    if response == "pause_sowing":
        results = []
        for zone in snapshot.get("development", {}).get("zones", []):
            if zone.get("allow_sow") is True:
                results.append(client.post("/api/v1/map/zone/growing/sowing", body={"map_id": map_id, "zone_id": int(zone["id"]), "allow_sow": False}))
        return {"applied": bool(results), "responses": results}
    if response == "collect_event_resources":
        forbidden = snapshot.get("development", {}).get("forbidden", [])
        ids = [int(row["id"]) for row in forbidden if row.get("id") is not None][:100]
        if not ids:
            return {"applied": False, "reason": "No forbidden event resource is currently visible."}
        return client.post("/api/v1/things/set-forbidden", body={"map_id": map_id, "thing_ids": ids, "forbidden": False})
    if response in {"accept_rescue_quest", "accept_quest"}:
        quest = _event_quest(context, event)
        if not quest:
            return {"applied": False, "reason": "No live quest matches this event."}
        return client.post("/api/v1/quest/accept", body={"quest_id": int(quest["id"])})
    if response == "prepare_rescue_mission":
        quest = _event_quest(context, event)
        if not quest:
            return {"applied": False, "reason": "No rescue quest with a world target is active."}
        responses = []
        if not quest.get("ever_accepted"):
            responses.append(client.post("/api/v1/quest/accept", body={"quest_id": int(quest["id"])}))
        targets = [row for row in quest.get("look_targets") or [] if row.get("world_object_id") is not None]
        if not targets:
            return {"applied": bool(responses), "reason": "Quest accepted, but no visitable rescue site exists yet.", "responses": responses}
        target = min(targets, key=lambda row: float(row.get("estimated_threat_points") or 0))
        responses.append(client.post("/api/v1/world/caravan/rescue/start", body={
            "map_id": map_id,
            "quest_id": int(quest["id"]),
            "site_id": int(target["world_object_id"]),
            "minimum_home_defenders": 2,
            "minimum_food_at_home": max(20, len(snapshot.get("colonists", [])) * 5),
            "minimum_medicine_at_home": 8,
        }))
        map_state["rescue_mission"] = {"quest_id": int(quest["id"]), "site_id": int(target["world_object_id"]), "started_tick": tick}
        return {"applied": True, "responses": responses}
    if response == "trade_now":
        trader_id = str(details.get("trader_id") or "")
        trader = next((row for row in context.get("trade_opportunities") or []
                       if str(row.get("id")) == trader_id), None)
        if trader is None:
            return {"applied": False, "reason": "The selected trader has departed."}
        sale = str(details.get("sale_category") or "none")
        purchase = str(details.get("purchase_priority") or "none")
        preview = details.get("trade_preview") or trader.get("preview") or {}
        if sale != "none" and sale not in verified_trade_options(preview, "sale"):
            return {"applied": False, "reason": "Selected sale is no longer verified for this trader"}
        if purchase != "none" and purchase not in verified_trade_options(preview, "purchase"):
            return {"applied": False, "reason": "Selected purchase is no longer verified for this trader"}
        purchase_pawn_id = details.get("purchase_pawn_id")
        if purchase == "slaves" and not any(
            str(offer.get("pawn_id")) == str(purchase_pawn_id)
            for offer in preview.get("humanlike_offers") or []
        ):
            return {"applied": False, "reason": "Chosen recruit is no longer verified for this trader"}
        if sale == "none" and purchase == "none":
            return {"applied": False, "reason": "Laya chose no sale and no purchase"}
        budget = int(details.get("trade_budget") or 1800)
        body = {
            "map_id": map_id,
            "trader_id": trader_id,
            "sale_categories": [] if sale == "none" else [sale],
            "purchase_priorities": [] if purchase == "none" else [purchase],
            "minimum_silver_reserve": int(details.get("minimum_silver_reserve")
                                          if details.get("minimum_silver_reserve") is not None
                                          else (100 if len(snapshot.get("colonists") or []) <= 2 else 300)),
            "maximum_spend": budget,
        }
        if purchase == "slaves":
            body["purchase_pawn_id"] = int(purchase_pawn_id)
        trade = client.post("/api/v1/trade/execute", body=body)
        return {"applied": bool(trade.get("executed")), "trade": trade}
    if response == "protect_home_from_fire":
        targets = [row for row in (context.get("fire_situation") or {}).get("fires") or []
                   if not row.get("in_home") and int(row.get("nearby_player_buildings") or 0) > 0]
        target = next((row for row in targets if str(row.get("id")) == str(details.get("fire_target"))), None)
        if target is None:
            return {"applied": False, "reason": "The chosen threatened fire is no longer present"}
        x, z = int(target["x"]), int(target["z"])
        area = client.post("/api/v1/order/designate/area", body={
            "map_id": map_id, "type": "home",
            "point_a": position(x - 2, z - 2), "point_b": position(x + 2, z + 2),
        })
        worker = prioritize(client, snapshot, "Firefighter")
        return {"applied": True, "fire_id": target["id"], "responses": [area, worker]}
    if response in {"power_emergency", "weather_emergency", "psychic_schedule_response", "contain_anomaly", "use_opportunity"}:
        if snapshot.get("game", {}).get("is_paused"):
            return client.post("/api/v1/game/speed", query={"speed": 1})
        return {"applied": False, "reason": f"{response}: context recorded; no universally safe forced order exists."}
    raise bridge.RimApiError(f"Unknown event response: {response}")


def publish_event_overlay(client: bridge.RimApiClient, event: dict[str, Any], options: dict[str, str], answer: dict[str, Any], result: Any) -> None:
    english = overlay_language(client) == "en"
    choice = str(answer.get("choice") or "observe_event")
    probabilities = answer.get("probabilities") or {}
    lines = [
        "LAYA — EVENT" if english else "LAYA — СОБЫТИЕ",
        f"{event.get('label') or event.get('name') or event.get('def_name') or event.get('incident_def')}",
        (f"Type: {event.get('family')} | source: {event.get('source')}" if english
         else f"Семейство: {event.get('family')} | источник: {event.get('source')}"),
        "",
        "Options:" if english else "Варианты:",
    ]
    for name in options:
        score = probabilities.get(name)
        suffix = f" {float(score) * 100:.1f}%" if score is not None else ""
        lines.append(f"{'> ' if name == choice else '  '}{name}{suffix}")
    lines.extend(["", (f"Decision: {choice}" if english else f"Решение: {choice}"),
                  (f"Result: {str(result)[:180]}" if english else f"Результат: {str(result)[:180]}")])
    event_label = str(event.get("label") or event.get("name") or event.get("def_name") or event.get("incident_def") or ("Event" if english else "Событие"))
    short_labels_ru = {
        "skip_trade": "Не торговать", "trade_now": "Торговать",
        "observe_event": "Наблюдать", "defer_rescue": "Отложить спасение",
        "defer_quest": "Отложить задание", "evaluate_animals": "Оценить животных",
        "evaluate_recruit": "Оценить пополнение", "ask_laya_generic": "Решить позже",
    }
    short_labels_en = {
        "skip_trade": "Skip trade", "trade_now": "Trade now",
        "observe_event": "Observe event", "defer_rescue": "Defer rescue",
        "defer_quest": "Defer quest", "evaluate_animals": "Evaluate animals",
        "evaluate_recruit": "Evaluate recruit", "ask_laya_generic": "Decide later",
    }
    short_labels = short_labels_en if english else short_labels_ru
    show_overlay(
        client,
        compact_lines=(["LAYA — EVENT", event_label, f"Decision: {choice}"] if english
                       else ["LAYA — СОБЫТИЕ", event_label, f"Решение: {choice}"]),
        full_lines=lines,
        bars=probability_bars(probabilities, {
            name: short_labels.get(name, name.replace("_", " ").capitalize()) for name in options
        }, choice, 8),
        duration=15.0,
        color="#F3E6FF",
    )


def run_event_cycle(
    client: bridge.RimApiClient,
    agent: Any,
    state: dict[str, Any],
    state_path: Path,
    log_path: Path,
) -> dict[str, Any] | None:
    snapshot = collect_development(client, bridge.collect_snapshot(client))
    seed = str(snapshot["map"].get("seed") or snapshot["map"]["id"])
    map_state = map_state_for_snapshot(state, snapshot)
    context = bridge.safe_get(client, "/api/v1/events/context", snapshot.setdefault("warnings", []), map_id=snapshot["map"]["id"]) or {}
    context["fire_situation"] = snapshot["development"].get("fire_situation") or {}
    stock = snapshot["development"].get("item_counts") or {}
    travel_food = int(stock.get("Pemmican") or 0) + int(stock.get("MealSurvivalPack") or 0)
    travel_medicine = sum(int(amount or 0) for name, amount in stock.items() if str(name).startswith("Medicine"))
    reserve = max(20, len(snapshot.get("colonists") or []) * 5)
    context["rescue_readiness"] = {
        "travel_food": travel_food, "minimum_travel_food": reserve + 16,
        "medicine": travel_medicine, "minimum_medicine": 10,
        "ready": travel_food >= reserve + 16 and travel_medicine >= 10,
    }
    context["trade_opportunities"] = [row for row in context.get("trade_opportunities") or []
        if not row.get("orbital") or (row.get("has_powered_comms_console")
                                      and row.get("has_powered_orbital_beacon"))]
    # A preliminary zero-reserve preview reveals real people and prices. Laya
    # chooses the actual reserve later, before any transaction is executed.
    trade_reserve = 0
    context["trade_opportunities"] = preview_live_traders(
        client, context, int(snapshot["map"]["id"]), trade_reserve)
    tick = int(snapshot["game"].get("tick") or 0)
    history = map_state.setdefault("handled_events", {})
    history = {str(key): int(value) for key, value in history.items() if tick - int(value) < 120000}
    map_state["handled_events"] = history
    pending = events.pending_events(context, set(history))
    if not pending:
        return None
    event = next((row for row in pending if not (
        row.get("family") == "trade" and action_backoff_remaining(
            map_state, f"event:{row['signature']}:trade_now") > 0
    )), None)
    if event is None:
        return None
    if event.get("family") == "trade" and not context["trade_opportunities"]:
        history[event["signature"]] = tick
        record = {"timestamp": bridge.utc_now(), "mode": "event-director",
                  "event": event, "decision": {"choice": "trade_unavailable", "status": "no_verified_transaction"},
                  "result": {"applied": False, "reason": "No live trade meets stock, negotiator and silver-reserve checks",
                             "preview_errors": context.get("trade_preview_errors") or []}}
        save_state(state_path, state)
        bridge.append_log(log_path, record)
        return record
    options = events.response_options(event, context)
    failure_prefix = f"event:{event['signature']}:"
    available_responses, blocked_responses = filter_backed_off_choices(
        map_state, options, prefix=failure_prefix
    )
    if not available_responses:
        return None
    options = {name: options[name] for name in available_responses}
    event_model_context = events.event_context_for_model(event, context, snapshot)
    event_model_context["player_preferences"] = laya_preferences.model_context(laya_preferences.load_preferences())
    response, raw = ask_laya_choice(agent, event_model_context, "event_response",
        "Choose one proportional response to this verified live event. Prefer reversible normal-game actions and preserve food, medicine, defenders and deadlines.", options)
    answer = raw.get("answers", {}).get("event_response", {})
    details: dict[str, Any] = {}
    if response == "trade_now":
        traders = context.get("trade_opportunities") or []
        trader_question = {"event_trader": {
            "type": "choice",
            "instructions": "Choose the exact live trader using remaining time, stock, negotiator skill and orbital infrastructure.",
            "criteria": {
                str(row["id"]): f"{row.get('name')} ({row.get('trader_kind')}); orbital={row.get('orbital')}; departs in {row.get('ticks_until_departure')} ticks; stock {[(item.get('label'), item.get('count')) for item in (row.get('stock') or [])[:18]]}"
                for row in traders if row.get("id")
            },
        }}
        if trader_question["event_trader"]["criteria"]:
            trader_id, trader_raw = ask_laya_choice(agent, event_model_context, "event_trader",
                str(trader_question["event_trader"]["instructions"]),
                dict(trader_question["event_trader"]["criteria"]))
            details["trader_id"] = trader_id
            selected_trader = next((row for row in traders if str(row.get("id")) == trader_id), {})
            preview = selected_trader.get("preview") or {}
            sale_options = verified_trade_options(preview, "sale")
            purchase_options = verified_trade_options(preview, "purchase")
            if purchase_options:
                sale_options = {"none": "Buy only; preserve all colony goods", **sale_options}
            sale_category, sale_raw = ask_laya_choice(agent, event_model_context, "sale_category",
                "Choose a verified surplus to sell, or preserve it for the colony.", sale_options)
            selected_preview = preview
            if sale_category != "none":
                try:
                    selected_preview = client.get(
                        "/api/v1/trade/preview", map_id=int(snapshot["map"]["id"]),
                        trader_id=trader_id, minimum_silver_reserve=trade_reserve,
                        maximum_spend=4000, sale_category=sale_category)
                except bridge.RimApiError as exc:
                    details["financed_preview_error"] = str(exc)
                    selected_preview = preview
            reserve = 100 if len(snapshot.get("colonists") or []) <= 2 else 300
            reserve_raw = None
            if verified_trade_options(selected_preview, "purchase"):
                possible_cash = float(selected_preview.get("colony_silver") or 0) + float(
                    selected_preview.get("planned_sale_value") or 0)
                recruits = selected_preview.get("humanlike_offers") or []
                reserve_options = {
                    str(amount): (
                        f"Keep {amount} silver after the deal; up to {max(0, possible_cash - amount):.0f} "
                        f"can be spent. Affordable people here: "
                        f"{', '.join(str(row.get('name')) for row in recruits if float(row.get('unit_price') or 0) <= possible_cash - amount) or 'none'}. "
                        + ("Spending all cash leaves no emergency buffer for food, medicine or defenses."
                           if amount == 0 else "A larger buffer may rule out a needed recruit.")
                    ) for amount in (0, 100, 300, 500)
                }
                reserve_choice, reserve_raw = ask_laya_choice(
                    agent, {**event_model_context, "growth": growth.trade_population_context(snapshot)},
                    "trade_reserve", "Choose the cash reserve for this actual trade. A lower reserve may buy "
                    "a worker now but leave the colony unable to handle the next emergency.", reserve_options)
                reserve = int(reserve_choice)
                if reserve:
                    try:
                        selected_preview = client.get(
                            "/api/v1/trade/preview", map_id=int(snapshot["map"]["id"]),
                            trader_id=trader_id, minimum_silver_reserve=reserve,
                            maximum_spend=4000,
                            **({"sale_category": sale_category} if sale_category != "none" else {}))
                    except bridge.RimApiError as exc:
                        details["reserved_preview_error"] = str(exc)
                        selected_preview = {**selected_preview, "purchase_options": [], "humanlike_offers": []}
            purchase_options = verified_trade_options(selected_preview, "purchase")
            if "slaves" in purchase_options and not selected_preview.get("humanlike_offers"):
                purchase_options.pop("slaves")
            if "slaves" in purchase_options:
                recruits = selected_preview.get("humanlike_offers") or []
                prices = [float(row.get("unit_price") or 0) for row in recruits]
                labor = growth.trade_population_context(snapshot)
                purchase_options["slaves"] = (
                    f"Recruit one of {len(recruits)} people for {min(prices):.0f}-{max(prices):.0f} silver; "
                    f"only {labor['able_workers']} of {labor['population']} colonists can work now. "
                    "Next choose the exact person, or cancel.")
            purchase_options = {"none": "Do not buy anyone or anything from this trader", **purchase_options}
            purchase_context = {
                "growth": growth.trade_population_context(snapshot),
                "trade": {"silver": selected_preview.get("colony_silver"), "reserve": reserve,
                          "sale_value": selected_preview.get("planned_sale_value")},
                "recruits": [growth.brief_humanlike_offer_description(row)
                             for row in (selected_preview.get("humanlike_offers") or [])[:5]],
            }
            purchase_priority, purchase_raw = ask_laya_choice(agent, purchase_context, "purchase_priority",
                "Choose an affordable live purchase, or sell only.", purchase_options)
            pawn_raw = None
            if purchase_priority == "slaves":
                offers = {
                    str(offer["pawn_id"]): growth.humanlike_offer_description(offer)
                    for offer in selected_preview.get("humanlike_offers") or []
                    if offer.get("pawn_id") is not None
                }
                offers["cancel_purchase"] = "Do not recruit from this trader after reviewing the people and costs."
                pawn_choice, pawn_raw = ask_laya_choice(
                    agent, purchase_context,
                    "recruit_candidate",
                    "Choose the specific person to buy, considering missing skills, health, work restrictions, food, beds and silver; or cancel.",
                    offers)
                if pawn_choice == "cancel_purchase":
                    purchase_priority = "none"
                else:
                    details["purchase_pawn_id"] = int(pawn_choice)
            budget_raw = None
            budget = "1800"
            if purchase_priority != "none":
                unit_price = next((float(row.get("unit_price") or 0)
                                   for row in selected_preview.get("purchase_options") or []
                                   if row.get("category") == purchase_priority), 0)
                if purchase_priority == "slaves":
                    unit_price = next((float(row.get("unit_price") or 0)
                                       for row in selected_preview.get("humanlike_offers") or []
                                       if int(row.get("pawn_id") or -1) == details["purchase_pawn_id"]), unit_price)
                budgets = {str(amount): f"Spend up to {amount} silver; keep {reserve} in reserve"
                           for amount in (500, 1800, 4000) if amount >= unit_price}
                budget, budget_raw = ask_laya_choice(agent, event_model_context, "trade_budget",
                    "Choose a spending cap for this verified purchase.", budgets)
            details["sale_category"] = sale_category
            details["purchase_priority"] = purchase_priority
            details["minimum_silver_reserve"] = reserve
            details["trade_budget"] = int(budget)
            details["trade_preview"] = selected_preview
            raw["trade"] = {"trader": trader_raw, "sale": sale_raw, "purchase": purchase_raw,
                            "reserve": reserve_raw, "recruit": pawn_raw, "budget": budget_raw}
    if response == "protect_home_from_fire":
        targets = {str(row["id"]): (
            f"size {float(row.get('size') or 0):.1f}, {int(row.get('nearby_player_buildings') or 0)} "
            f"nearby buildings, position ({row.get('x')},{row.get('z')})"
        ) for row in (context.get("fire_situation") or {}).get("fires") or []
            if row.get("id") is not None and not row.get("in_home")
            and int(row.get("nearby_player_buildings") or 0) > 0}
        if targets:
            fire_id, fire_raw = ask_laya_choice(agent, event_model_context, "fire_target",
                "Choose which real fire threatens the colony most.", targets)
            details["fire_target"] = fire_id
            raw["fire_target"] = fire_raw
    execution_failed = False
    try:
        result = _execute_event_response(client, snapshot, map_state, event, context, response, details)
    except bridge.RimApiError as exc:
        execution_failed = True
        failure = register_action_failure(map_state, f"{failure_prefix}{response}", exc)
        result = {
            "applied": False,
            "skipped": "event_api_error_backoff",
            "error": str(exc),
            "failure_count": failure["count"],
            "retry_in_seconds": round(float(failure["retry_after"]) - time.time(), 1),
        }
    else:
        clear_action_failure(map_state, f"{failure_prefix}{response}")
    if response == "trade_now" and bool((result or {}).get("applied")):
        trade = (result or {}).get("trade") or {}
        map_state.setdefault("trade_ledger", []).append({
            "tick": tick, "trader": str(trade.get("trader_name") or "")[:60],
            "sold_units": int(trade.get("sold_units") or 0),
            "bought_units": int(trade.get("bought_units") or 0),
            "sale_value": float(trade.get("approximate_sale_value") or 0),
            "purchase_value": float(trade.get("approximate_purchase_value") or 0),
        })
        map_state["trade_ledger"] = map_state["trade_ledger"][-12:]
    # Quest acceptance is phase one; a fresh snapshot must be allowed to offer
    # the newly created/updated rescue site on the next cycle.
    if not execution_failed and response != "accept_rescue_quest":
        history[event["signature"]] = tick
    try:
        publish_event_overlay(client, event, options, answer, result)
    except bridge.RimApiError as exc:
        snapshot.setdefault("warnings", []).append(str(exc))
    record = {
        "timestamp": bridge.utc_now(), "mode": "event-director", "map_seed": seed,
        "event": event, "options": options, "blocked_options": blocked_responses,
        "decision": {"choice": response, "raw": raw, **details}, "result": result,
    }
    save_state(state_path, state)
    bridge.append_log(log_path, record)
    return record


def run_rescue_site_cycle(
    client: bridge.RimApiClient,
    state: dict[str, Any],
    state_path: Path,
    log_path: Path,
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    active_plans = [
        map_state for map_state in state.setdefault("maps", {}).values()
        if isinstance(map_state, dict) and map_state.get("rescue_mission")
    ]
    if not active_plans or not snapshot.get("map", {}).get("is_temp_incident_map"):
        return None
    status = client.get("/api/v1/world/rescue/site/status", map_id=int(snapshot["map"]["id"]))
    if status.get("active_threat"):
        return None
    if status.get("captive_pawn_ids"):
        release_active = any(
            "releaseprisoner" in str(pawn.get("current_job") or "").replace("_", "").lower()
            for pawn in snapshot.get("combat", {}).get("colonists", [])
        )
        if release_active:
            result = {"applied": False, "reason": "normal prisoner release job is still active"}
            phase = "wait-for-release"
        else:
            result = client.post("/api/v1/world/rescue/site/secure", body={"map_id": int(snapshot["map"]["id"])})
            phase = "free-captive"
    elif status.get("can_return_home"):
        result = client.post("/api/v1/world/rescue/site/return", body={"map_id": int(snapshot["map"]["id"])})
        phase = "return-home"
        for map_state in active_plans:
            map_state["last_rescue_mission"] = map_state.pop("rescue_mission")
            map_state["last_rescue_mission"]["completed_tick"] = int(snapshot["game"].get("tick") or 0)
    else:
        return None
    record = {
        "timestamp": bridge.utc_now(), "mode": "rescue-site", "phase": phase,
        "status": status, "result": result,
    }
    try:
        if overlay_language(client) == "en":
            rescue_lines = ["LAYA — RESCUE MISSION", f"Phase: {phase}",
                            f"Captives: {', '.join(status.get('captive_names') or []) or 'freed'}"]
        else:
            rescue_lines = ["LAYA — СПАСАТЕЛЬНАЯ ОПЕРАЦИЯ", f"Этап: {phase}",
                            f"Пленники: {', '.join(status.get('captive_names') or []) or 'освобождены'}"]
        show_overlay(client, compact_lines=rescue_lines, full_lines=rescue_lines, duration=12.0, color="#CFFFE0")
    except bridge.RimApiError:
        pass
    save_state(state_path, state)
    bridge.append_log(log_path, record)
    return record


def downed_raider_leave_description(downed: list[dict[str, Any]]) -> str:
    lowest_bleeding = min((bridge.first_number(row.get("bleeding_rate")) for row in downed), default=0.0)
    return (f"Leave {len(downed)} downed raider(s), lowest bleeding {lowest_bleeding:.2f}. "
            "A survivor can stand up and attack again; no prison labor is spent now.")


def recurring_entity_hostile(hostile: dict[str, Any]) -> bool:
    """Shamblers are not ordinary recruits and can rise again without bleeding."""
    kind = str(hostile.get("kind_def") or "").lower()
    faction = str(hostile.get("faction") or "").lower()
    conditions = " ".join(map(str, hostile.get("health_conditions") or [])).lower()
    return "shambler" in kind or "shambler" in conditions or faction == "entities"


def recurring_entity_unresolved(snapshot: dict[str, Any]) -> bool:
    return any(row.get("is_downed") and not row.get("is_dead")
               and recurring_entity_hostile(row)
               and bridge.first_number(row.get("bleeding_rate")) <= 0.05
               for row in (snapshot.get("combat") or {}).get("hostiles") or [])


def run_downed_raider_cycle(
    client: bridge.RimApiClient,
    agent: Any,
    state: dict[str, Any],
    state_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    """Let Laya resolve verified downed hostiles without treating them as an active assault."""
    snapshot = collect_development(client, bridge.collect_snapshot(client))
    seed = str(snapshot["map"].get("seed") or snapshot["map"]["id"])
    map_state = map_state_for_snapshot(state, snapshot)
    if "anchor" not in map_state:
        map_state["anchor"] = anchor_from_snapshot(snapshot)
    anchor = map_state["anchor"]
    tick = int(snapshot["game"].get("tick") or 0)
    issued = map_state.setdefault("issued", {})
    downed = [h for h in snapshot["combat"]["hostiles"] if h.get("is_downed") and not h.get("is_dead")]
    prison_site = prison_site_for_state(map_state, anchor)
    prison_a = position(prison_site["x"], prison_site["z"])
    prison_b = position(prison_site["x"] + 6, prison_site["z"] + 6)
    prison_beds = ready_prison_beds(snapshot["development"], prison_site)
    recurring = [hostile for hostile in downed if recurring_entity_hostile(hostile)
                 and bridge.first_number(hostile.get("bleeding_rate")) <= 0.05]
    healthy_fighters = [pawn for pawn in snapshot["combat"]["colonists"]
                        if not pawn.get("is_downed") and bridge.first_number(pawn.get("health")) >= 0.75
                        and str(pawn.get("current_job") or "").lower() not in {"rescue", "tendpatient"}]
    urgent_entity = bool(recurring and healthy_fighters)
    criteria: dict[str, str] = ({} if urgent_entity else {
        "leave_downed_raiders": downed_raider_leave_description(downed),
    })
    can_build_prison = (bridge.choose_worker(snapshot.get("colonists") or [], "Construction") is not None
                        and prison_material(snapshot["development"].get("item_counts") or {}) is not None)
    if not urgent_entity and not prison_beds and can_build_prison:
        if not issued_recently(map_state, "prison_blueprint", tick, retry_ticks=90000):
            criteria["build_prison"] = "Place a normal enclosed prison now; capture becomes possible only after construction finishes, and this raider may bleed out first."
        else:
            criteria["wait_for_prison"] = "Keep colonists undrafted and prioritize construction while the already-issued prison is completed."
    for hostile in downed:
        if urgent_entity and hostile not in recurring:
            continue
        pawn_id = int(hostile["id"])
        name = str(hostile.get("name") or pawn_id)
        if healthy_fighters:
            criteria[f"finish_downed:{pawn_id}"] = (
                f"Kill {name} with an ordinary drafted attack. Health {float(hostile.get('health') or 0) * 100:.0f}%, "
                f"bleeding {float(hostile.get('bleeding_rate') or 0):.2f}; "
                + ("this shambler can rise and attack again and cannot be recruited or traded."
                   if recurring_entity_hostile(hostile) else
                   "this avoids prison costs but may affect mood or ideology.")
            )
        if prison_beds and not recurring_entity_hostile(hostile) and not urgent_entity:
            skills = ", ".join(map(str, hostile.get("top_skills") or [])) or "unknown skills"
            if hostile.get("recruitable", True):
                criteria[f"capture_recruit:{pawn_id}"] = (
                    f"Capture {name} and set Recruit. {hostile.get('gender')}, age {hostile.get('biological_age')}; "
                    f"top skills {skills}; traits {hostile.get('traits') or []}; value {hostile.get('market_value', 0):.0f}."
                )
            if hostile.get("faction_can_give_goodwill") and not hostile.get("faction_permanent_enemy"):
                criteria[f"capture_release:{pawn_id}"] = (
                    f"Capture and heal {name}, then Release for faction goodwill. Current goodwill {hostile.get('faction_goodwill', 0)}."
                )
            criteria[f"capture_sell:{pawn_id}"] = (
                f"Capture {name} and hold with no recruitment interaction for a later slaver/settlement sale; "
                f"market value {hostile.get('market_value', 0):.0f}, requiring food, guarding and transport."
            )
    resources = snapshot["map"]["resources"]
    material_counts = snapshot["development"].get("item_counts", {})
    context = {
        "goal": "Resolve downed raiders while preserving colony survival and future growth.",
        "player_preferences": laya_preferences.model_context(laya_preferences.load_preferences()),
        "colony": {
            "population": len(snapshot["colonists"]),
            "food": resources.get("food"),
            "medicine": resources.get("medicine"),
            "wood": material_counts.get("WoodLog", 0),
            "silver": material_counts.get("Silver", 0),
            "prison_beds_ready": len(prison_beds),
            "best_social": max((int((c.get("skills", {}).get("Social") or {}).get("level") or 0) for c in snapshot["colonists"]), default=0),
            "best_medicine": max((int((c.get("skills", {}).get("Medicine") or {}).get("level") or 0) for c in snapshot["colonists"]), default=0),
        },
        "downed_raiders": downed,
    }
    choice, raw = ask_laya_choice(agent, context, "downed_raider_action",
        "Choose one normal RimWorld action. Compare recruitable skills and value against prison food, treatment, escape and moral costs. A release helps only factions that can grant goodwill.",
        criteria)
    answer = raw["answers"]["downed_raider_action"]
    responses: list[Any] = []
    description = criteria[choice]
    if choice in {"leave_downed_raiders", "wait_for_prison"}:
        for pawn in snapshot["combat"]["colonists"]:
            if pawn.get("is_drafted"):
                responses.append(client.post("/api/v1/pawn/edit/status", body={"pawn_id": int(pawn["id"]), "is_drafted": False}))
        if choice == "wait_for_prison":
            responses.append(prioritize(client, snapshot, "Construction"))
        result: Any = {"applied": bool(responses), "responses": responses, "reason": choice}
    elif choice == "build_prison":
        terrain = client.get("/api/v1/map/terrain", map_id=snapshot["map"]["id"])
        site = choose_prison_site(terrain, anchor, snapshot["development"], map_state)
        if site is None:
            result = {"applied": False, "reason": "No clear dry site for a seven-cell prison"}
        else:
            stuff = prison_material(material_counts)
            if not stuff:
                result = {"applied": False, "reason": "Prison needs 140 wood or steel"}
                responses = []
            else:
                responses.append(post_blueprint(client, snapshot["map"]["id"], site, prison_blueprint(stuff)))
                map_state["prison_site"] = site
                issued["prison_blueprint"] = tick
                responses.append(prioritize(client, snapshot, "Construction"))
                result = {"applied": True, "site": site, "material": stuff, "responses": responses}
    elif choice.startswith("finish_downed:"):
        target_id = int(choice.split(":", 1)[1])
        fighters = healthy_fighters
        target = next((row for row in downed if int(row["id"]) == target_id), None)
        actor = min(fighters, key=lambda pawn: (
            squared_distance(pawn.get("position") or {}, (target or {}).get("position") or {}),
            -int(pawn.get("melee_skill") or 0)), default=None)
        if actor is None:
            result = {"applied": False, "reason": "No healthy colonist can finish the target"}
        elif (str(actor.get("current_job") or "").lower() == "attackmelee"
              and int(actor.get("current_job_target_id") or 0) == target_id):
            result = {"applied": False, "in_progress": True, "actor": actor.get("name"),
                      "target_id": target_id, "reason": "Finishing attack is already underway"}
        else:
            responses.append(client.post("/api/v1/pawn/edit/status", body={"pawn_id": int(actor["id"]), "is_drafted": True}))
            responses.append(client.post("/api/v1/pawn/job", body={
                "pawn_id": int(actor["id"]),
                "job_def": "AttackMelee",
                "target_thing_id": target_id,
            }))
            issued[f"finish_downed:{target_id}"] = tick
            result = {"applied": True, "actor": actor.get("name"), "target_id": target_id, "responses": responses}
    else:
        policy, target_text = choice.split(":", 1)
        target_id = int(target_text)
        policy_name = policy.removeprefix("capture_")
        result = client.post("/api/v1/pawn/prisoner/capture", body={
            "map_id": snapshot["map"]["id"],
            "prisoner_pawn_id": target_id,
            "point_a": prison_a,
            "point_b": prison_b,
            "policy": policy_name,
        })
        issued[f"prisoner:{target_id}:{policy_name}"] = tick
        map_state.setdefault("prisoner_plans", {})[str(target_id)] = policy_name
    record = {
        "timestamp": bridge.utc_now(),
        "mode": "downed-raider",
        "snapshot": snapshot,
        "decision": {"choice": choice, "confidence": bridge.first_number(answer.get("confidence")), "raw": raw},
        "action": {"description": description},
        "result": result,
    }
    save_state(state_path, state)
    bridge.append_log(log_path, record)
    publish_combat_overlay(client, record)
    return record


def get_ancient_danger(client: bridge.RimApiClient, map_id: int) -> dict[str, Any]:
    try:
        value = client.get("/api/v1/map/ancient-danger", map_id=map_id)
        return value if isinstance(value, dict) else {}
    except bridge.RimApiError:
        return {}


def run_ancient_danger_cycle(
    client: bridge.RimApiClient,
    agent: Any,
    state: dict[str, Any],
    state_path: Path,
    log_path: Path,
    status: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve the warning as a sealed site decision, never as a raid."""
    snapshot = collect_development(client, bridge.collect_snapshot(client))
    seed = str(snapshot["map"].get("seed") or snapshot["map"]["id"])
    map_state = map_state_for_snapshot(state, snapshot)
    tick = int(snapshot["game"].get("tick") or 0)
    prior = map_state.get("ancient_danger") or {}
    same_notice = (prior.get("position") is not None
                   and prior.get("position") == status.get("position"))
    retry_after = 30000 if prior.get("policy") == "prepare_ancient_danger" else 600000
    if same_notice and tick - int(prior.get("decision_tick") or 0) < retry_after:
        if snapshot["game"].get("is_paused") and not prior.get("resumed"):
            client.post("/api/v1/game/speed", query={"speed": 1})
            prior["resumed"] = True
            save_state(state_path, state)
        return None

    colonists_by_id = {str(p.get("id")): p for p in snapshot["colonists"]}
    healthy = [
        p for p in snapshot.get("combat", {}).get("colonists", [])
        if not p.get("is_dead") and not p.get("is_downed") and float(p.get("health") or 0) >= 0.75
        and can_fight(colonists_by_id.get(str(p.get("id"))) or {})
    ]
    ranged = [p for p in healthy if p.get("has_ranged_weapon")]
    fighter_details = [
        {"name": p.get("name"), "health": p.get("health"),
         "rest": colonists_by_id.get(str(p.get("id")), {}).get("rest"),
         "weapon": p.get("weapon_label") or p.get("weapon_def") or "unarmed",
         "position": p.get("position")}
        for p in healthy
    ]
    noncombatants = [p.get("name") for p in snapshot["colonists"]
                     if not can_fight(p)]
    low_rest = [p["name"] for p in fighter_details
                if p["rest"] is not None and float(p["rest"]) < 0.5]
    resources = snapshot["map"]["resources"]
    context = {
        "event": "A proximity warning revealed a sealed Ancient Danger. This is not an active raid.",
        "player_preferences": laya_preferences.model_context(laya_preferences.load_preferences()),
        "known_information": {
            "warning": status.get("notice"),
            "sealed": bool(status.get("sealed")),
            "contents": "unknown; do not assume hidden enemies or loot",
            "can_designate_opening_wall": bool(status.get("can_open")),
        },
        "colony": {
            "population": len(snapshot["colonists"]),
            "healthy_fighters": len(healthy),
            "healthy_ranged_fighters": len(ranged),
            "fighter_details": fighter_details,
            "noncombatants": noncombatants,
            "fighters_low_on_rest": low_rest,
            "sheltered_completed_beds": sheltered_real_bed_count(snapshot.get("development") or {}),
            "unfinished_construction_count": len(snapshot.get("development", {}).get("construction_projects") or []),
            "active_caravans": len(snapshot.get("development", {}).get("caravans") or []),
            "defensive_structures": snapshot.get("combat", {}).get("defenses") or [],
            "medicine": resources.get("medicine", 0),
            "food": resources.get("food", 0),
            "weapons": resources.get("weapons", 0),
            "current_doctrine": map_state.get("doctrine", {}),
        },
        "consequences": {
            "open_now": "Opening may release lethal hostiles without warning. If tired or underarmed fighters fall, the entire colony and any incapacitated pawns can be lost; noncombatants cannot defend it.",
            "leave_or_prepare": "The sealed site is not currently attacking. Delaying preserves the colony and permits rest, shelter, equipment and a defended firing line; potential loot or rescue opportunities wait.",
        },
    }
    criteria = {
        "leave_ancient_danger_sealed": "Acknowledge the warning, keep the tomb sealed, undraft everyone, resume time, and revisit only much later or after a major strength increase.",
        "prepare_ancient_danger": "Keep it sealed, add a fallback firing line/traps using normal construction, resume time, and reconsider after colonists finish preparations.",
    }
    if status.get("can_open"):
        criteria["open_ancient_danger"] = "Designate one outer wall for deconstruction now. Contents can be immediately lethal. Evaluate each actual fighter's weapon and rest, any noncombatants, defenses and the chance of losing the whole colony; the warning alone creates no urgency."
    choice, raw = ask_laya_choice(agent, context, "ancient_danger_action",
        "Choose autonomously whether to leave, prepare for, or open the sealed Ancient Danger. It is a strategic opportunity/risk, not a raid; never keep colonists drafted merely because the warning paused the game.",
        criteria)
    answer = raw.get("answers", {}).get("ancient_danger_action", {})
    responses: list[Any] = []
    if choice == "prepare_ancient_danger":
        anchor = map_state.get("anchor") or anchor_from_snapshot(snapshot)
        map_state.setdefault("anchor", anchor)
        responses.append(post_blueprint(client, snapshot["map"]["id"], anchor, fallback_defense_blueprint(), dx=12, dz=-6))
        responses.append(prioritize(client, snapshot, "Construction"))
    elif choice == "open_ancient_danger":
        responses.append(client.post("/api/v1/map/ancient-danger/open", body={"map_id": snapshot["map"]["id"]}))
    # This is the only pause transition here: a verified Ancient Danger warning.
    if snapshot["game"].get("is_paused"):
        responses.append(client.post("/api/v1/game/speed", query={"speed": 1}))
    map_state["ancient_danger"] = {
        "policy": choice,
        "detected_tick": int(status.get("detected_tick") or 0),
        "decision_tick": tick,
        "resumed": bool(snapshot["game"].get("is_paused")),
        "position": status.get("position"),
    }
    probabilities = answer.get("probabilities") or {}
    english = overlay_language(client) == "en"
    lines = (["LAYA — ANCIENT DANGER", "This is a sealed tomb, not an active raid.",
              f"Fighters: {len(healthy)} | shooters: {len(ranged)} | medicine: {resources.get('medicine', 0)}",
              "", "Options:"] if english else [
        "LAYA — ДРЕВНЯЯ ОПАСНОСТЬ", "Это запечатанная гробница, не активный рейд.",
        f"Бойцы: {len(healthy)} | стрелки: {len(ranged)} | медицина: {resources.get('medicine', 0)}",
        "", "Варианты:",
    ])
    for name in criteria:
        score = probabilities.get(name)
        suffix = f" {float(score) * 100:.1f}%" if score is not None else ""
        lines.append(f"{'> ' if name == choice else '  '}{name}{suffix}")
    lines.extend(["", (f"Decision: {choice}" if english else f"Решение: {choice}"),
                  ("Auto-pause cleared; colonists need not stay drafted for a warning." if english
                   else "Автопауза снята; колонисты не держатся мобилизованными из-за одного предупреждения.")])
    try:
        show_overlay(
            client,
            compact_lines=(["LAYA — ANCIENT DANGER",
                f"Fighters: {len(healthy)} · shooters: {len(ranged)} · medicine: {resources.get('medicine', 0)}",
                f"Decision: {choice}"] if english else [
                "LAYA — ДРЕВНЯЯ ОПАСНОСТЬ",
                f"Бойцы: {len(healthy)} · стрелки: {len(ranged)} · медицина: {resources.get('medicine', 0)}",
                f"Решение: {choice}",
            ]),
            full_lines=lines,
            bars=probability_bars(probabilities, {name: name for name in criteria}, choice, 8),
            duration=16.0,
            color="#FFE5A8",
        )
    except bridge.RimApiError:
        pass
    record = {
        "timestamp": bridge.utc_now(),
        "mode": "ancient-danger",
        "snapshot": snapshot,
        "status": status,
        "decision": {"choice": choice, "confidence": bridge.first_number(answer.get("confidence")), "raw": raw},
        "result": {"applied": True, "responses": responses},
    }
    save_state(state_path, state)
    bridge.append_log(log_path, record)
    return record


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Long-horizon Laya colony director for RimWorld")
    p.add_argument("--api-url", default=bridge.DEFAULT_API_URL)
    p.add_argument("--model", default=bridge.DEFAULT_MODEL)
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cuda")
    p.add_argument("--interval", type=float, default=10.0)
    p.add_argument("--state", type=Path, default=Path(__file__).with_name("logs") / "colony-state.json")
    p.add_argument("--log", type=Path, default=Path(__file__).with_name("logs") / "decisions.jsonl")
    p.add_argument("--pid-file", type=Path, default=Path(__file__).with_name("logs") / "director.pid")
    p.add_argument("--runtime-status", type=Path, default=Path(__file__).with_name("logs") / "runtime-status.json")
    return p


def write_runtime_status(path: Path, state: str, detail: str = "") -> bool:
    """Publish health without ever letting a Windows file-sharing race stop Laya."""
    payload = {
        "pid": os.getpid(),
        "state": state,
        "detail": detail[:500],
        "updated_at": bridge.utc_now(),
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    for attempt in range(4):
        try:
            temporary.write_text(serialized, encoding="utf-8")
            temporary.replace(path)
            return True
        except OSError:
            time.sleep(0.025 * (attempt + 1))
    # Antivirus and the GUI can briefly hold the destination without FILE_SHARE_DELETE.
    # A direct write is less atomic but still preferable to terminating the autopilot.
    try:
        path.write_text(serialized, encoding="utf-8")
        return True
    except OSError:
        return False
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def classify_runtime_problem(detail: str) -> tuple[str, str, str]:
    """Separate an unavailable game from an actual decision-cycle failure."""

    lowered = detail.lower()
    if "no loaded map" in lowered or "load a colony" in lowered:
        return "waiting", detail, "Waiting for a loaded colony"
    unavailable_markers = (
        "winerror 10061",
        "connection refused",
        "actively refused",
        "конечный компьютер отверг",
        "expecting value: line 1 column 1",
    )
    if any(marker in lowered for marker in unavailable_markers):
        return "waiting", "RimWorld or RIMAPI is not available yet", "Waiting for RimWorld/RIMAPI"
    return "error", detail, "Decision cycle problem"


def cycle_retry_policy(runtime_state: str, consecutive_errors: int, interval: float) -> tuple[float, int]:
    """Return retry delay and next error count without busy-looping the API."""
    if runtime_state == "waiting":
        return min(10.0, max(2.0, interval)), 0
    next_count = min(8, consecutive_errors + 1)
    delay = min(300.0, max(10.0, interval) * (2 ** (next_count - 1)))
    return delay, next_count


def combat_order_signature(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    """Return only changes that justify replacing an active combat order.

    Exact positions and pawn jobs change while a drafted pawn walks to cover.
    Including them made the director re-plan and resend the same order every two
    seconds, which could keep a pawn from ever completing it. The signature still
    changes for casualties, material health loss, drafting, target changes and a
    transition from raid preparation to active attack.
    """
    combat = snapshot.get("combat") or {}
    colonists = list(combat.get("colonists") or [])
    hostiles = [row for row in (combat.get("hostiles") or []) if not row.get("is_dead")]

    def hostile_intent(row: dict[str, Any]) -> str:
        job = str(row.get("current_job") or "").lower()
        if bridge.combat_planner.hostile_is_preparing(row):
            return "staging"
        for intent, markers in (
            ("kidnap", ("kidnap", "capture")),
            ("flee", ("flee", "exitmap")),
            ("breach", ("breach", "sap")),
            ("steal", ("steal",)),
            ("attack", ("attack", "assault", "goto")),
        ):
            if any(marker in job for marker in markers):
                return intent
        return "unknown"

    living = [
        row for row in colonists
        if row.get("id") is not None
        and not row.get("is_dead")
        and not row.get("is_downed")
    ]
    hostile_intents = tuple(sorted(hostile_intent(row) for row in hostiles))
    actively_fighting = any(row.get("is_drafted") and str(row.get("current_job") or "").lower() in {
        "attackstatic", "attackmelee", "goto",
    } for row in living)
    staging_distance = 70 if actively_fighting else 35
    staging = bool(living) and bool(hostiles) and all(
        bridge.first_number(row.get("distance_to_nearest_opponent"), 9999) > staging_distance
        for row in living
    ) and all(intent == "staging" for intent in hostile_intents)
    fighter_state = tuple(sorted(
        (
            int(row["id"]), bool(row.get("is_drafted")), bool(row.get("is_downed")),
            bool(row.get("is_in_mental_state")),
            int(bridge.first_number(row.get("health"), 0.0) * 10),
            str(row.get("weapon_def") or ""),
        )
        for row in colonists if row.get("id") is not None
    ))
    hostile_state = tuple(sorted(
        (
            int(row["id"]), bool(row.get("is_downed")),
            hostile_intent(row), int(row.get("carrying_pawn_id") or 0),
            (0 if bridge.first_number(row.get("distance_to_nearest_opponent"), 9999) < 6
             else 1 if bridge.first_number(row.get("distance_to_nearest_opponent"), 9999) < 15
             else 2 if bridge.first_number(row.get("distance_to_nearest_opponent"), 9999) < 35
             else 3),
        )
        for row in hostiles if row.get("id") is not None
    ))
    return ("staging" if staging else "active", fighter_state, hostile_state)


def combat_replan_due(signature: tuple[Any, ...], previous: tuple[Any, ...] | None,
                      elapsed: float, has_record: bool, urgent: bool = False) -> bool:
    """Keep orders long enough to execute, but never leave stale tactics indefinitely."""
    return not has_record or (urgent and signature != previous) or (signature != previous and elapsed >= 5.0) or elapsed >= 30.0


def combat_positioning_finished(snapshot: dict[str, Any], record: dict[str, Any] | None,
                                elapsed: float) -> bool:
    """Re-plan promptly when a short approach/backstep has actually ended."""
    if not record or elapsed < 2.0:
        return False
    commands = (record.get("action") or {}).get("commands") or []
    responses = (record.get("result") or {}).get("responses") or []
    positioned_ids = {
        int(pawn_id)
        for index, command in enumerate(commands)
        if command.get("endpoint") == "/api/v1/combat/tactic"
        and command.get("body", {}).get("tactic") in {
            "focus_fire", "intercept_kidnapper", "advance_to_range", "backstep_fire", "kite",
        }
        for pawn_id in ((responses[index] if index < len(responses) else {}) or {}).get("positioned_pawn_ids", [])
    }
    if not positioned_ids:
        return False
    colonists = {int(row["id"]): row for row in snapshot.get("combat", {}).get("colonists", [])
                 if row.get("id") is not None}
    return any(
        pawn_id in colonists and not colonists[pawn_id].get("is_dead")
        and not colonists[pawn_id].get("is_downed")
        and str(colonists[pawn_id].get("current_job") or "").lower() != "goto"
        for pawn_id in positioned_ids
    )


def preemptive_advance_state(snapshot: dict[str, Any], record: dict[str, Any] | None,
                             elapsed: float) -> tuple[str, dict[str, Any] | None]:
    """Continue Laya's strike in short map-validated hops, or reassess new danger."""
    if not record or (record.get("decision") or {}).get("choice") != "preemptive_strike":
        return "none", None
    commands = (record.get("action") or {}).get("commands") or []
    command = next((row for row in commands if row.get("endpoint") == "/api/v1/combat/tactic"), None)
    if not command or (command.get("body") or {}).get("tactic") != "preemptive_strike":
        return "none", None
    body = command["body"]
    hostile = next((row for row in snapshot.get("combat", {}).get("hostiles", [])
                    if row.get("id") == body.get("target_pawn_id") and not row.get("is_dead") and not row.get("is_downed")), None)
    live_hostiles = [row for row in snapshot.get("combat", {}).get("hostiles", [])
                     if not row.get("is_dead") and not row.get("is_downed")]
    initial_ids = {row.get("id") for row in ((record.get("snapshot") or {}).get("combat") or {}).get("hostiles", [])
                   if not row.get("is_dead") and not row.get("is_downed")}
    if (hostile is None or any(not bridge.combat_planner.hostile_is_preparing(row) for row in live_hostiles)
            or (initial_ids and {row.get("id") for row in live_hostiles} != initial_ids)):
        return "replan", None
    fighters = [row for row in snapshot.get("combat", {}).get("colonists", [])
                if row.get("id") in body.get("fighter_ids", []) and not row.get("is_dead") and not row.get("is_downed")]
    if len(fighters) < 2 or any(bridge.first_number(row.get("health")) < 0.72 for row in fighters):
        return "replan", None
    responses = (record.get("result") or {}).get("responses") or []
    tactic_index = commands.index(command)
    tactic_response = responses[tactic_index] if len(responses) > tactic_index else {}
    if tactic_response and not (tactic_response.get("positioned_pawn_ids") or tactic_response.get("attacking_pawn_ids")):
        return "wait", None
    if elapsed < 2.0 or any(str(row.get("current_job") or "").lower() == "goto" for row in fighters):
        return "wait", None
    if all(str(row.get("current_job") or "").lower() == "attackstatic" for row in fighters):
        return "wait", None
    return "advance", body


def post_combat_care_options(snapshot: dict[str, Any],
                             buildings: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Offer treatment and rescue as distinct choices after a fight."""
    colonists = snapshot.get("combat", {}).get("colonists", [])
    capabilities = {int(row["id"]): row for row in snapshot.get("colonists", [])
                    if row.get("id") is not None}

    def can_do_medicine(pawn: dict[str, Any]) -> bool:
        details = capabilities.get(int(pawn["id"])) or {}
        medicine = (details.get("skills") or {}).get("Medicine") or {}
        return not bool(medicine.get("disabled"))

    active_patients = {
        int(pawn["current_job_target_id"])
        for pawn in colonists
        if str(pawn.get("current_job") or "").lower() == "tendpatient"
        and pawn.get("current_job_target_id") is not None
    }
    available_helpers = [pawn for pawn in colonists
               if not pawn.get("is_dead") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
               and str(pawn.get("current_job") or "").lower() not in {"tendpatient", "rescue"}
               and bridge.first_number(pawn.get("moving"), 1) >= 0.5
               and bridge.first_number(pawn.get("manipulation"), 1) >= 0.5]
    doctors = [pawn for pawn in available_helpers if can_do_medicine(pawn)]
    patients = sorted(
        [pawn for pawn in colonists if pawn.get("tendable_now")
         and not pawn.get("is_dead") and int(pawn["id"]) not in active_patients],
        key=lambda pawn: (-bridge.first_number(pawn.get("bleeding_rate")),
                          bridge.first_number(pawn.get("health"), 1)),
    )[:5]
    options: dict[str, dict[str, Any]] = {}
    beds = [row for row in buildings or [] if row.get("id") is not None
            and not row.get("for_prisoners")
            and str(row.get("def") or row.get("thing_def") or "") in {
                "Bed", "HospitalBed", "SleepingSpot",
            }]
    active_rescues = {int(pawn["current_job_target_id"]) for pawn in colonists
                      if str(pawn.get("current_job") or "").lower() == "rescue"
                      and pawn.get("current_job_target_id") is not None}
    reserved_beds = {int(pawn["current_job_target_id_b"]) for pawn in colonists
                     if str(pawn.get("current_job") or "").lower() == "rescue"
                     and pawn.get("current_job_target_id_b") is not None}
    for patient in colonists:
        if not patient.get("is_downed") or patient.get("is_dead") or int(patient["id"]) in active_rescues or not beds:
            continue
        patient_id = int(patient["id"])
        if patient_in_completed_bed(capabilities.get(patient_id) or patient, snapshot, beds):
            continue
        patient_pos = patient.get("position") or {}
        free_beds = [row for row in beds if int(row["id"]) not in reserved_beds
                     and not any(other.get("id") != patient_id and not other.get("is_dead")
                                 and patient_in_completed_bed(
                                     capabilities.get(int(other["id"])) or other,
                                     snapshot, [row])
                                 for other in colonists if other.get("id") is not None)]
        if not free_beds:
            continue
        bed = min(free_beds, key=lambda row: (
            not bool(row.get("medical")),
            str(row.get("def") or row.get("thing_def")) == "SleepingSpot",
            (bridge.first_number((row.get("position") or {}).get("x")) - bridge.first_number(patient_pos.get("x"))) ** 2
            + (bridge.first_number((row.get("position") or {}).get("z")) - bridge.first_number(patient_pos.get("z"))) ** 2,
        ))
        # Carrying an untreated patient to a remote bed can take longer than
        # their remaining bleed time. A doctor can tend at their current cell.
        bleeding = bridge.first_number(patient.get("bleeding_rate"))
        bed_distance = squared_distance(patient_pos, bed.get("position") or {}) ** 0.5
        if (patient.get("tendable_now") and any(int(doctor["id"]) != patient_id for doctor in doctors)
                and (bleeding >= 2.0 or (bleeding >= 0.5 and bed_distance >= 20))):
            continue
        helpers = sorted(
            [pawn for pawn in available_helpers if int(pawn["id"]) != patient_id],
            key=lambda pawn: (
                bridge.first_number((pawn.get("position") or {}).get("x")) - bridge.first_number(patient_pos.get("x"))) ** 2
                + (bridge.first_number((pawn.get("position") or {}).get("z")) - bridge.first_number(patient_pos.get("z"))) ** 2,
        )[:2]
        for helper in helpers:
            distance = round(((bridge.first_number((helper.get("position") or {}).get("x")) - bridge.first_number(patient_pos.get("x"))) ** 2
                             + (bridge.first_number((helper.get("position") or {}).get("z")) - bridge.first_number(patient_pos.get("z"))) ** 2) ** 0.5)
            key = f"rescue_{patient_id}_{int(helper['id'])}"
            options[key] = {
                "patient_id": patient_id, "doctor_id": int(helper["id"]), "bed_id": int(bed["id"]),
                "kind": "rescue", "self_tend": False,
                "summary": (f"Carry downed {patient.get('name')} to an unoccupied bed with {helper.get('name')} "
                            f"({distance} cells away). Bleeding {bridge.first_number(patient.get('bleeding_rate')):.2f} "
                            "continues during travel. "
                            + ("Critical bleeding may kill them before arrival; rescue does not treat wounds. "
                               if bridge.first_number(patient.get("bleeding_rate")) >= 2 else "")
                            + "Tending on the ground may stop bleeding sooner but leaves them exposed."),
            }
    for patient in patients:
        patient_id = int(patient["id"])
        bleeding = bridge.first_number(patient.get("bleeding_rate"))
        conditions = (capabilities.get(patient_id) or {}).get("health_conditions") or []
        infections = [condition for condition in conditions
                      if "infection" in str(condition.get("def_name") or condition.get("label") or "").lower()]
        infection_risk = (
            "Active infection " + ", ".join(
                f"{condition.get('part') or 'body'} severity {bridge.first_number(condition.get('severity')):.2f}"
                for condition in infections
            ) + "; untreated infection can kill despite full displayed health and no bleeding. "
            if infections else ""
        )
        infection_note = (f" infection severity {max(bridge.first_number(c.get('severity')) for c in infections):.2f};"
                          if infections else "")
        # A rescuer carrying this very patient must be allowed to switch to
        # field tending if their bleeding is critical. Rescue never stops it.
        rescuer_doctors = [pawn for pawn in colonists
                           if bleeding >= 1.5 and int(pawn.get("current_job_target_id") or 0) == patient_id
                           and str(pawn.get("current_job") or "").lower() == "rescue"
                           and not pawn.get("is_dead") and not pawn.get("is_downed")
                           and can_do_medicine(pawn)]
        available_doctors = sorted(
            [pawn for pawn in doctors + rescuer_doctors if int(pawn["id"]) != patient_id],
            key=lambda pawn: (bridge.first_number(pawn.get("medicine_skill")),
                              bridge.first_number(pawn.get("health"), 1)), reverse=True,
        )[:2]
        for doctor in available_doctors:
            key = f"tend_{patient_id}_{int(doctor['id'])}"
            patient_pos = patient.get("position") or {}
            doctor_pos = doctor.get("position") or {}
            distance = (f", {round(squared_distance(patient_pos, doctor_pos) ** 0.5)} cells away"
                        if patient_pos and doctor_pos else "")
            options[key] = {"patient_id": patient_id, "doctor_id": int(doctor["id"]), "kind": "tend",
                            "self_tend": False,
                            "summary": (f"Doctor {doctor.get('name')} medicine {doctor.get('medicine_skill', 0)}{distance}; "
                                        f"tend {patient.get('name')};{infection_note} bleed {bleeding:.2f}, "
                                        f"health {bridge.first_number(patient.get('health')):.2f}. "
                                        "Low skill risks weak treatment or infection; waiting risks blood loss. "
                                        + infection_risk)}
        if not patient.get("is_downed") and patient_id in {int(row["id"]) for row in doctors}:
            key = f"self_tend_{patient_id}"
            options[key] = {"patient_id": patient_id, "doctor_id": patient_id, "kind": "tend",
                            "self_tend": True,
                            "summary": (f"Self-tend {patient.get('name')} medicine {patient.get('medicine_skill', 0)};"
                                        f"{infection_note} bleed {bleeding:.2f}, health {bridge.first_number(patient.get('health')):.2f}. "
                                        "Risk poor care versus waiting for another doctor. " + infection_risk)}
    # Give the most seriously bleeding downed patient the next doctor before
    # stable injuries or a long rescue consume that decision window.
    urgent = next((pawn for pawn in patients if pawn.get("is_downed")
                   and bridge.first_number(pawn.get("bleeding_rate")) >= 1.5), None)
    if urgent is not None:
        urgent_tends = {name: row for name, row in options.items()
                        if row.get("kind") == "tend" and row.get("patient_id") == int(urgent["id"])}
        if urgent_tends:
            return urgent_tends
    return options


def treatment_job_in_progress(snapshot: dict[str, Any]) -> bool:
    """Keep a model-selected tend order alive until its wound is actually treated."""
    colonists = snapshot.get("combat", {}).get("colonists", [])
    patients = {int(row["id"]) for row in colonists
                if row.get("id") is not None and row.get("tendable_now") and not row.get("is_dead")}
    return any(
        str(row.get("current_job") or "").lower() == "tendpatient"
        and row.get("current_job_target_id") is not None
        and int(row["current_job_target_id"]) in patients
        for row in colonists
    )


def rescue_job_in_progress(snapshot: dict[str, Any]) -> bool:
    colonists = snapshot.get("combat", {}).get("colonists", [])
    downed = {int(row["id"]) for row in colonists if row.get("id") is not None
              and row.get("is_downed") and not row.get("is_dead")}
    return any(str(row.get("current_job") or "").lower() == "rescue"
               and row.get("current_job_target_id") is not None
               and int(row["current_job_target_id"]) in downed for row in colonists)


def urgent_care_unassigned(snapshot: dict[str, Any]) -> bool:
    """Do not wait for one rescue while another colonist bleeds untreated."""
    colonists = snapshot.get("combat", {}).get("colonists", [])
    tended = {int(row["current_job_target_id"]) for row in colonists
              if str(row.get("current_job") or "").lower() == "tendpatient"
              and row.get("current_job_target_id") is not None}
    return any(row.get("id") is not None and int(row["id"]) not in tended
               and row.get("tendable_now") and not row.get("is_dead")
               and bridge.first_number(row.get("bleeding_rate")) >= 1.5
               for row in colonists)


def urgent_care_actionable(snapshot: dict[str, Any]) -> bool:
    return urgent_care_unassigned(snapshot) and any(
        name.startswith("tend_") for name in post_combat_care_options(snapshot))


def post_combat_care_retry_delay(snapshot: dict[str, Any], applied: bool,
                                 interval: float) -> float:
    """Give an accepted nonurgent tend job time to finish while colony work runs."""
    if urgent_care_actionable(snapshot):
        return 2.0
    return max(60.0, interval * 3) if applied else interval


def live_threat_care_needed(snapshot: dict[str, Any]) -> bool:
    """A free civilian doctor can make a real triage decision before an ally bleeds out."""
    if not bridge.combat_planner.live_hostiles(snapshot) or not urgent_care_unassigned(snapshot):
        return False
    drafted = {int(row["id"]) for row in snapshot.get("combat", {}).get("colonists", [])
               if row.get("id") is not None and row.get("is_drafted")}
    return any(row.get("kind") == "tend" and int(row.get("doctor_id") or 0) not in drafted
               for row in post_combat_care_options(snapshot).values())


def publish_post_combat_care_overlay(client: bridge.RimApiClient, snapshot: dict[str, Any],
                                     choice: str, raw: dict[str, Any],
                                     options: dict[str, dict[str, Any]]) -> None:
    english = overlay_language(client) == "en"
    colonists = {int(row["id"]): str(row.get("name") or row["id"])
                for row in snapshot.get("combat", {}).get("colonists", []) if row.get("id") is not None}
    selected = options.get(choice)

    def label(name: str) -> str:
        if name == "defer_care":
            return "Defer care" if english else "Отложить лечение"
        if name == "withdraw_civilian":
            return "Withdraw helper" if english else "Отвести помощника"
        if name == "resume_colony_decisions":
            return "Resume colony work" if english else "Вернуться к делам колонии"
        row = options.get(name) or {}
        patient = colonists.get(int(row.get("patient_id") or 0), "patient" if english else "пациент")
        doctor = colonists.get(int(row.get("doctor_id") or 0), "doctor" if english else "врач")
        if row.get("self_tend"):
            return f"Self-tend {patient}" if english else f"Самолечение: {patient}"
        if row.get("kind") == "rescue":
            return f"Rescue {patient} — {doctor}" if english else f"Спасти {patient} — {doctor}"
        return f"Treat {patient} — {doctor}" if english else f"Лечить {patient} — {doctor}"

    answer = ((raw.get("answers") or {}).get("post_combat_care") or {})
    probabilities = answer.get("probabilities") or {}
    status = (("Care order in progress" if english else "Помощь выполняется") if selected else
              ("Helper withdrawing" if english else "Помощник отступает") if choice == "withdraw_civilian" else
              ("Care deferred" if english else "Помощь отложена"))
    show_overlay(
        client,
        compact_lines=(["LAYA — MEDICAL", f"Chosen: {label(choice)}",
                        status] if english else [
                        "LAYA — МЕДИЦИНА", f"Выбрано: {label(choice)}",
                        status]),
        full_lines=(["LAYA — MEDICAL", f"Chosen: {label(choice)}"] if english else [
                    "LAYA — МЕДИЦИНА", f"Выбрано: {label(choice)}"]),
        bars=probability_bars(probabilities, {name: label(name) for name in probabilities}, choice, 8),
        duration=20.0,
        color="#D7F1E7",
    )


def run_post_combat_care_cycle(client: bridge.RimApiClient, agent: Any,
                               snapshot: dict[str, Any], log_path: Path,
                               *, live_threat: bool = False) -> dict[str, Any] | None:
    hostiles = bridge.combat_planner.live_hostiles(snapshot)
    if hostiles and not live_threat:
        return None
    buildings = []
    if any(pawn.get("is_downed") for pawn in snapshot.get("combat", {}).get("colonists", [])) and hasattr(client, "get"):
        try:
            buildings = client.get("/api/v1/map/buildings", map_id=int(snapshot.get("map", {}).get("id") or 0)) or []
            if not isinstance(buildings, list):
                buildings = []
        except bridge.RimApiError:
            pass
    options = post_combat_care_options(snapshot, buildings)
    if live_threat:
        # Do not pull a drafted defender out of an active fight to tend; a
        # mobile civilian may still choose to risk a field treatment.
        drafted_ids = {int(pawn["id"]) for pawn in snapshot.get("combat", {}).get("colonists", [])
                       if pawn.get("id") is not None and pawn.get("is_drafted")}
        options = {name: row for name, row in options.items()
                   if int(row.get("doctor_id") or 0) not in drafted_ids}
    if not options:
        return None
    if recurring_entity_unresolved(snapshot) and not any(
            row.get("kind") == "tend"
            and bridge.first_number(next((pawn.get("bleeding_rate") for pawn in
                                          snapshot.get("combat", {}).get("colonists", [])
                                          if pawn.get("id") == row.get("patient_id")), 0.0)) >= 1.5
            for row in options.values()):
        # Treat bleeding first. Stable wounds can wait until a finisher has
        # dealt with an entity that will recover and attack again.
        return None
    active_infection = any(
        "infection" in str(condition.get("def_name") or condition.get("label") or "").lower()
        and condition.get("tendable_now")
        for pawn in snapshot.get("colonists", [])
        for condition in pawn.get("health_conditions") or []
    )
    delay_risk = ("Untreated infection can kill even when displayed health is full and bleeding is zero."
                  if active_infection else
                  "A severely bleeding colonist can die before the next review.")
    safe_urgent_tends = {}
    if live_threat and urgent_care_unassigned(snapshot):
        pawns = {int(pawn["id"]): pawn for pawn in snapshot.get("combat", {}).get("colonists", [])
                 if pawn.get("id") is not None}
        safe_urgent_tends = {name: row for name, row in options.items()
                             if row.get("kind") == "tend"
                             and (doctor := pawns.get(int(row.get("doctor_id") or 0)))
                             and (patient := pawns.get(int(row.get("patient_id") or 0)))
                             and not bridge.combat_planner.errand_exposed(
                                 snapshot, patient.get("position"), doctor.get("position"))}
        if safe_urgent_tends:
            # An enemy elsewhere on the map is not a reason to leave a
            # reachable, severely bleeding patient untreated.
            options = safe_urgent_tends
    alternatives = {
        "defer_care": f"Do not treat now. {delay_risk} Choose only if delay is worth that risk.",
        "resume_colony_decisions": f"Return to other colony work without a treatment order. {delay_risk}",
    }
    if safe_urgent_tends:
        alternatives = {}
    elif live_threat:
        alternatives = {
            "defer_care": ("Leave the bleeding patient exposed for now. The nearby enemy may kill the doctor, "
                           "but untreated blood loss can kill the patient."),
            "withdraw_civilian": ("Move the mobile civilian away from the hostile. This protects the last helper "
                                  "but the bleeding patient may die without treatment."),
        }
        if not any(not pawn.get("is_dead") and not pawn.get("is_downed")
                   and not pawn.get("is_in_mental_state")
                   and bridge.first_number(pawn.get("moving"), 1) >= 0.65
                   and (not pawn.get("can_fight", True) or not pawn.get("weapon_def"))
                   and bridge.combat_planner.errand_exposed(snapshot, pawn.get("position"))
                   for pawn in snapshot.get("combat", {}).get("colonists", [])):
            alternatives.pop("withdraw_civilian")
    elif urgent_care_actionable(snapshot):
        alternatives = {}
    def danger_distance(patient_id: int) -> int | None:
        patient = next((row for row in snapshot.get("combat", {}).get("colonists", [])
                        if row.get("id") == patient_id), None)
        if patient is None or not (patient.get("position") or {}) or not hostiles:
            return None
        distances = [squared_distance(patient["position"], hostile["position"]) ** 0.5
                     for hostile in hostiles if hostile.get("position")]
        return round(min(distances)) if distances else None
    care_options = {**{key: (row["summary"] + (
        f" Nearest live enemy {danger_distance(int(row['patient_id']))} cells from patient; "
        "approach may expose the doctor." if live_threat else ""))
        for key, row in options.items()}, **alternatives}
    choice, raw = ask_laya_choice(agent, {
        "task": "Emergency field care under live threat" if live_threat else "Choose treatment, rescue or another action after combat",
        "triage": ("A successful API order is not a completed treatment. Severe bleeding can kill "
                   "while a rescuer travels or while a doctor is reassigned. Verify bleeding falls before "
                   "moving the only doctor to a stable patient."),
        "colonists": [
            {"id": row.get("id"), "name": row.get("name"), "health": row.get("health"),
             "bleeding_rate": row.get("bleeding_rate"), "is_downed": row.get("is_downed"),
             "moving": row.get("moving"), "pain": row.get("pain"),
             "conditions": [str((condition.get("label") or condition.get("def_name") or condition)
                                if isinstance(condition, dict) else condition)
                            for condition in (row.get("health_conditions") or [])[:3]],
             "current_job": row.get("current_job"),
             "job_target": row.get("current_job_target_id")}
            for row in snapshot.get("combat", {}).get("colonists", [])
        ],
        "remaining_hostiles": [
            {"id": row.get("id"), "name": row.get("name"), "downed": row.get("is_downed")}
            for row in snapshot.get("combat", {}).get("hostiles", []) if not row.get("is_dead")],
        "medicine": (snapshot.get("map", {}).get("resources") or {}).get("medicine"),
    }, "post_combat_care", (
        "Choose whether an undrafted helper should risk field treatment or retreat from live hostiles. "
        "Compare the patient's bleed time with enemy distance; sleeping while an ally bleeds is not care. "
        if live_threat else
        "Choose whether to tend on the ground, carry a downed ally to a bed, defer, or return to colony work. "
        "Travel delays treatment; leaving a patient exposed can also be fatal. "
        "The wounds, bleeding, distance, doctor skill and supplies are context, not a forced choice."
    ), care_options)
    selected = options.get(choice)
    publish_post_combat_care_overlay(client, snapshot, choice, raw, options)
    try:
        if snapshot.get("game", {}).get("is_paused"):
            client.post("/api/v1/game/speed", query={"speed": 1})
        if selected is None and choice == "withdraw_civilian":
            retreat = bridge.plan_action(snapshot, {"choice": "civilian_retreat"})
            responses = [client.post(command["endpoint"], query=command.get("query"),
                                     body=command.get("body"))
                         for command in retreat.get("commands") or []]
            result = {"applied": bool(responses), "retreat": retreat.get("description"),
                      "responses": responses}
        elif selected is None:
            result = {"applied": False, "deferred": True,
                      "revisit": choice == "defer_care", "reason": alternatives[choice]}
        else:
            doctor = next((pawn for pawn in snapshot["combat"]["colonists"]
                           if int(pawn["id"]) == selected["doctor_id"]), None)
            patient = next((pawn for pawn in snapshot["combat"]["colonists"]
                            if int(pawn["id"]) == selected["patient_id"]), None)
            if doctor and doctor.get("is_drafted"):
                client.post("/api/v1/pawn/edit/status", body={"pawn_id": selected["doctor_id"], "is_drafted": False})
            patient_hold = None
            if selected.get("kind") == "rescue":
                response = client.post("/api/v1/pawn/job", body={
                    "pawn_id": selected["doctor_id"], "job_def": "Rescue",
                    "target_thing_id": selected["patient_id"], "target_thing_id_b": selected["bed_id"],
                })
                result = {"applied": True, "response": response}
            else:
                if (patient and not patient.get("is_downed") and not selected["self_tend"]
                    and bridge.first_number(patient.get("bleeding_rate")) > 0
                    and str(patient.get("current_job") or "").lower() not in {
                        "laydown", "wait_maintainposture", "tendpatient",
                    }):
                    # Keep a mobile bleeding patient in reach of the doctor.
                    patient_hold = client.post("/api/v1/pawn/job", body={
                        "pawn_id": selected["patient_id"], "job_def": "Wait_MaintainPosture",
                    })
                response = client.post("/api/v1/pawn/medical/tend", body={
                    "patient_pawn_id": selected["patient_id"],
                    "doctor_pawn_id": selected["doctor_id"],
                    "self_tend": selected["self_tend"],
                })
                result = {"applied": True, "response": response}
                if patient_hold is not None:
                    result["patient_hold"] = patient_hold
    except bridge.RimApiError as exc:
        result = {"applied": False, "error": str(exc)}
    record = {"timestamp": bridge.utc_now(),
              "mode": "live-threat-care" if live_threat else "post-combat-care",
              "candidates": list(options), "decision": {"choice": choice, "raw": raw},
              "plan": selected, "result": result}
    bridge.append_log(log_path, record)
    return record


def run_window_cycle(client: bridge.RimApiClient, agent: Any, snapshot: dict[str, Any],
                     state: dict[str, Any], log_path: Path) -> dict[str, Any] | None:
    """Resolve live multi-choice game dialogues through Laya, never blind-close them."""
    windows = bridge.safe_get(client, "/api/v1/ui/windows", snapshot.setdefault("warnings", [])) or []
    def actionable_window(row: dict[str, Any]) -> bool:
        window_type = str(row.get("window_type") or "")
        return ((window_type.startswith("Dialog_NodeTree") and bool(row.get("enabled_options")))
                or (window_type.startswith("Dialog_NamePlayer") and bool(row.get("suggested_names"))))

    # RimWorld draws newer dialogs above older ones. Match the visible top
    # dialog rather than a stale node-tree underneath another choice window.
    dialogue = next((row for row in reversed(windows) if actionable_window(row)), None)
    if dialogue is None:
        return None
    naming = str(dialogue.get("window_type") or "").startswith("Dialog_NamePlayer")
    options = list(dict.fromkeys(str(label) for label in
                                  dialogue["suggested_names" if naming else "enabled_options"] if label))
    if not options:
        return None
    map_state = map_state_for_snapshot(state, snapshot)
    key = "|".join([str(dialogue.get("window_type")), str(dialogue.get("dialog_text") or "")[:120], *options])
    if time.time() < float((map_state.get("deferred_dialogs") or {}).get(key) or 0):
        return None
    criteria = {f"option_{index}": label for index, label in enumerate(options)}
    # A force-pausing dialogue cannot make progress while left open. In
    # particular, naming the settlement is a genuine choice among suggested
    # names, but postponing it only freezes unattended play.
    if not dialogue.get("force_pause"):
        criteria["defer"] = "Leave this dialogue open for now."
    model_state = {
        "dialogue": str(dialogue.get("dialog_text") or "")[:550],
        "population": len(snapshot.get("colonists") or []),
        "food": (snapshot.get("map") or {}).get("resources", {}).get("food"),
        "downed": sum(bool(p.get("downed")) for p in snapshot.get("colonists") or []),
        "threats": (snapshot.get("map") or {}).get("enemies", 0),
    }
    selected, raw = ask_laya_choice(agent, model_state, "live_dialogue",
        ("Choose a name for the colony/faction from game-generated suggestions."
         if naming else
         "Choose a visible RimWorld dialogue option after weighing colony population, survival and any quest risk."), criteria)
    if selected == "defer":
        map_state.setdefault("deferred_dialogs", {})[key] = time.time() + 60
        result = {"applied": False, "reason": "Laya deferred the dialogue for 60 seconds"}
    else:
        label = options[int(selected.removeprefix("option_"))]
        body = {"window_type": dialogue["window_type"],
                "suggested_name" if naming else "option_label": label}
        if not naming:
            body["dialog_text"] = dialogue.get("dialog_text")
        try:
            result = client.post("/api/v1/ui/window/name" if naming else "/api/v1/ui/window/choose",
                                 body=body)
        except bridge.RimApiError as exc:
            map_state.setdefault("deferred_dialogs", {})[key] = time.time() + 60
            result = {"applied": False, "error": str(exc),
                      "reason": "Dialogue reply failed; paused before retry rather than selecting blindly."}
    record = {"timestamp": bridge.utc_now(), "mode": "live-dialogue", "dialogue": model_state,
              "candidates": criteria, "decision": {"choice": selected, "raw": raw}, "result": result}
    bridge.append_log(log_path, record)
    return record


def run_caravan_trade_cycle(client: bridge.RimApiClient, agent: Any, snapshot: dict[str, Any],
                            state: dict[str, Any], log_path: Path) -> dict[str, Any] | None:
    """Finish a real faction-settlement trade session, including a chosen recruit."""
    session = bridge.safe_get(client, "/api/v1/trade/caravan/session",
                              snapshot.setdefault("warnings", [])) or {}
    if not session.get("active"):
        return None
    map_state = map_state_for_snapshot(state, snapshot)
    settlement_id = int(session.get("settlement_id") or 0)
    retry = map_state.setdefault("caravan_trade_retry", {})
    if time.time() < float(retry.get(str(settlement_id)) or 0):
        return {"timestamp": bridge.utc_now(), "mode": "caravan-trade",
                "decision": {"choice": "wait_for_retry"},
                "result": {"applied": False, "reason": "Waiting after a trade API error"}}
    cash = int(session.get("colony_silver") or 0)
    trader_cash = int(session.get("trader_silver") or 0)
    sale_options = {str(row["category"]): row for row in session.get("sale_options") or []
                    if isinstance(row, dict) and row.get("category")}
    people = [row for row in session.get("humanlike_offers") or [] if isinstance(row, dict)
              and row.get("pawn_id") is not None]
    context = {
        "settlement": session.get("settlement_name"), "cash": cash, "trader_cash": trader_cash,
        "population": len(snapshot.get("colonists") or []),
        "food": (snapshot.get("map") or {}).get("resources", {}).get("food"),
        "course": {key: (map_state.get("doctrine") or {}).get(key) for key in
                   ("economy_product", "diplomacy", "endgame")},
        "growth": growth.trade_population_context(snapshot),
        "risk": "A recruit adds labor but also consumes food, beds and medicine. Keep travel supplies and a cash reserve; the trader's stock may not be available again.",
    }
    sale_choice, sale_raw = ask_laya_choice(agent, context, "caravan_sale",
        "Choose one verified category to sell at this settlement, or keep all goods. Caravan food is reserved for the return trip.",
        {"none": "Keep current inventory for the colony.", **{
            key: f"{row.get('example')}, up to {row.get('maximum_units')} units at about {row.get('unit_price')} silver each; buyer has {trader_cash} silver"
            for key, row in sale_options.items()}})
    sale_row = sale_options.get(sale_choice) or {}
    estimated_proceeds = min(trader_cash, float(sale_row.get("unit_price") or 0)
                             * int(sale_row.get("maximum_units") or 0))
    reserve_options = {str(amount): f"Keep at least {amount} silver after this trade"
                       for amount in (0, 100, 300) if amount <= cash + estimated_proceeds}
    reserve, reserve_raw = ask_laya_choice(agent, {**context, "chosen_sale": sale_choice},
        "caravan_cash_reserve", "Choose a reserve for the journey home and urgent purchases.", reserve_options)
    affordable = [row for row in people if 0 < float(row.get("unit_price") or 0)
                  <= cash + estimated_proceeds - int(reserve)]
    recruit_choice, recruit_raw = ask_laya_choice(agent,
        {**context, "chosen_sale": sale_choice, "reserve": int(reserve)}, "caravan_recruit",
        "Choose one actual person to buy or decline. Compare skills, health, work limits, price and population needs.",
        {"none": "Do not buy a person at this settlement.", **{
            str(row["pawn_id"]): growth.brief_humanlike_offer_description(row)
            for row in affordable}})
    body = {"settlement_id": settlement_id, "sale_category": sale_choice,
            "purchase_pawn_id": int(recruit_choice) if recruit_choice != "none" else None,
            "minimum_silver_reserve": int(reserve), "maximum_spend": max(0, cash + int(estimated_proceeds)),
            "close_without_trade": sale_choice == "none" and recruit_choice == "none"}
    try:
        trade = client.post("/api/v1/trade/caravan/session/execute", body=body)
    except bridge.RimApiError as exc:
        retry[str(settlement_id)] = time.time() + 30
        result = {"applied": False, "error": str(exc), "retry_in_seconds": 30}
    else:
        retry.pop(str(settlement_id), None)
        if trade.get("executed"):
            map_state.setdefault("trade_ledger", []).append({
                "tick": int(snapshot.get("game", {}).get("tick") or 0),
                "trader": str(trade.get("trader_name") or "")[:60],
                "sold_units": int(trade.get("sold_units") or 0),
                "bought_units": int(trade.get("bought_units") or 0),
                "sale_value": float(trade.get("approximate_sale_value") or 0),
                "purchase_value": float(trade.get("approximate_purchase_value") or 0),
            })
            map_state["trade_ledger"] = map_state["trade_ledger"][-12:]
        result = {"applied": bool(trade.get("executed") or body["close_without_trade"]),
                  "trade": trade, "closed_without_trade": body["close_without_trade"]}
    record = {"timestamp": bridge.utc_now(), "mode": "caravan-trade", "session": context,
              "decision": {"choice": "trade" if not body["close_without_trade"] else "leave",
                           "sale": sale_choice, "recruit": recruit_choice, "reserve": int(reserve),
                           "raw": [sale_raw, reserve_raw, recruit_raw]}, "result": result}
    bridge.append_log(log_path, record)
    return record


def run_letter_cycle(client: bridge.RimApiClient, agent: Any, snapshot: dict[str, Any],
                     state: dict[str, Any], log_path: Path) -> dict[str, Any] | None:
    """Handle live joiner/quest choice letters before their opportunity expires."""
    context = bridge.safe_get(client, "/api/v1/events/context", snapshot.setdefault("warnings", []),
                              map_id=int(snapshot["map"]["id"])) or {}
    tick = int(snapshot["game"].get("tick") or 0)
    map_state = map_state_for_snapshot(state, snapshot)
    handled = map_state.setdefault("handled_choice_letters", {})
    letters = context.get("letters") or []
    terminal = next((row for row in letters
                     if str(row.get("label") or "").strip().casefold() == "game over"
                     or "everyone is dead or gone" in str(row.get("text") or "").casefold()), None)
    if terminal is not None:
        # This is the colony's terminal screen, not a joiner/quest offer.
        # Preserve the final screen and stop issuing orders.
        record = {"timestamp": bridge.utc_now(), "mode": "game-over",
                  "letter": {"id": terminal.get("id"), "label": terminal.get("label"),
                             "details": str(terminal.get("text") or "")[:750]},
                  "decision": {"choice": "stop_director"},
                  "result": {"applied": False, "reason": "Colony ended"}}
        bridge.append_log(log_path, record)
        return record
    for letter in letters:
        letter_id = str(letter.get("id")) if letter.get("id") is not None else ""
        letter_text = str(letter.get("text") or "")
        options = list(dict.fromkeys(str(label) for label in letter.get("enabled_options") or [] if label))
        meaningful = [label for label in options
                      if label.strip().casefold() not in {
                          "close", "jump to location", "view quest", "read more", "dismiss"}]
        if (not letter_id or not options or letter_id in handled
                or not meaningful
                or tick - int(letter.get("arrival_tick") or 0) > 90000):
            continue
        if time.time() < float((map_state.get("deferred_letters") or {}).get(letter_id) or 0):
            continue
        # Camera/letter housekeeping buttons are not a response to the offer.
        # Keeping them in the choice set could silently discard a recruit or quest.
        options = meaningful
        criteria = {f"option_{index}": label for index, label in enumerate(options)}
        criteria["defer"] = "Leave the offer unanswered for now; it may expire."
        labor = growth.trade_population_context(snapshot)
        immobile_arrival = any(token in letter_text.casefold() for token in (
            "paralytic abasia", "unable to walk", "cannot walk", "paralyzed", "paralysed"))
        model_state = {
            "letter": str(letter.get("label") or "")[:110],
            "population": labor["population"],
            "able_workers": labor["able_workers"],
            "bedbound": labor["bedbound"],
            "incoming_labor": ("This person cannot work or defend until mobility recovers; "
                               "they will need feeding and medical care in the meantime."
                               if immobile_arrival else "Check the offer for injuries and work limits."),
            "details": letter_text[:750],
            "food": (snapshot.get("map") or {}).get("resources", {}).get("food", 0),
            "ready_meals": (snapshot.get("map") or {}).get("resources", {}).get("meals", 0),
            "roofed_beds": sheltered_real_bed_count(snapshot.get("development") or {}) or 0,
            "prisoners": len((snapshot.get("combat") or {}).get("prisoners") or []),
            "threats": (snapshot.get("map") or {}).get("enemies", 0),
            "risk": "A recruit adds skills and labor but also needs food, a sheltered bed, treatment and defense; declining can lose a rare chance to rebuild a small colony.",
            "best_skills": labor["best_skills"],
        }
        selected, raw = ask_laya_choice(agent, model_state, "letter_response",
            "Decide whether to accept a live joiner or quest offer after weighing colony needs, deadline and risk.", criteria)
        if selected == "defer":
            map_state.setdefault("deferred_letters", {})[letter_id] = time.time() + 60
            result = {"applied": False, "reason": "Laya deferred this letter for 60 seconds"}
        else:
            label = options[int(selected.removeprefix("option_"))]
            try:
                result = client.post("/api/v1/events/letter/choose", body={
                    "letter_id": int(letter_id), "option_label": label,
                    "letter_text": letter_text,
                })
                handled[letter_id] = tick
            except bridge.RimApiError as exc:
                map_state.setdefault("deferred_letters", {})[letter_id] = time.time() + 60
                result = {"applied": False, "error": str(exc),
                          "reason": "Letter reply failed; other colony decisions may continue."}
        record = {"timestamp": bridge.utc_now(), "mode": "choice-letter", "letter": model_state,
                  "candidates": criteria, "decision": {"choice": selected, "raw": raw}, "result": result}
        bridge.append_log(log_path, record)
        return record
    return None


def staging_development_allowed(snapshot: dict[str, Any], combat_record: dict[str, Any] | None) -> bool:
    """Laya may keep planning normal work after choosing to stand down during staging."""
    if (combat_record or {}).get("decision", {}).get("choice") not in {
        "prepare_undrafted", "continue_safe_colony_work",
    }:
        return False
    combat = snapshot.get("combat") or {}
    hostiles = [row for row in combat.get("hostiles", []) if not row.get("is_dead") and not row.get("is_downed")]
    if any(row.get("is_downed") or bridge.first_number(row.get("bleeding_rate")) > 0.05
           for row in combat.get("colonists", []) if not row.get("is_dead")):
        return False
    if any(bridge.first_number(row.get("distance_to_nearest_opponent"), 9999) <= 35
           for row in combat.get("colonists", []) if not row.get("is_dead")):
        return False
    return bool(hostiles) and all(bridge.combat_planner.hostile_is_preparing(row) for row in hostiles) \
        and not any(row.get("is_drafted") for row in combat.get("colonists", []))


def main() -> int:
    # The standalone director may be launched by an older packaged GUI or a
    # console whose code page cannot encode pawn names and modded item labels.
    # A successful action must never become a failed cycle just because its
    # diagnostic line contains a Unicode character.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            pass
    args = parser().parse_args()
    singleton_handle = None
    if os.name == "nt":
        singleton_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\RimWorldLayaColonyDirector")
        if ctypes.windll.kernel32.GetLastError() == 183:
            print("Another Laya colony director is already active; exiting duplicate process.", flush=True)
            return 2
    args.pid_file.parent.mkdir(parents=True, exist_ok=True)
    args.pid_file.write_text(str(os.getpid()), encoding="ascii")
    write_runtime_status(args.runtime_status, "starting", "Loading the local Laya model")
    client = bridge.RimApiClient(args.api_url)
    try:
        agent = bridge.load_agent(args.model, args.device)
        state = load_state(args.state)
    except Exception as exc:
        write_runtime_status(args.runtime_status, "error", f"Model startup failed: {exc}")
        raise
    last_wait_message = 0.0
    last_combat_signature: tuple[Any, ...] | None = None
    last_combat_record: dict[str, Any] | None = None
    last_combat_order_time = 0.0
    last_combat_step_time = 0.0
    next_colony_cycle = 0.0
    next_downed_cycle = 0.0
    next_post_combat_care_cycle = 0.0
    next_live_threat_care_cycle = 0.0
    next_hazard_scan = 0.0
    post_combat_pending = False
    care_bootstrapped = False
    post_combat_care_failures = 0
    care_assignment_time = 0.0
    retry_not_before = 0.0
    consecutive_cycle_errors = 0
    runtime_state = "running"
    runtime_detail = "Ready for the next decision cycle"
    print("Laya colony director active: survival -> doctrine -> chosen endgame. Ctrl+C stops safely.", flush=True)
    try:
        while True:
            started = time.monotonic()
            # Refresh the heartbeat without erasing a waiting/error state.  The
            # GUI must not briefly claim that a failing director is healthy
            # merely because another retry has started.
            write_runtime_status(args.runtime_status, runtime_state, runtime_detail)
            try:
                snapshot = bridge.collect_snapshot(client)
                map_state = map_state_for_snapshot(state, snapshot)
                if (bridge.combat_planner.live_hostiles(snapshot)
                        or map_state.get("hazard_forbidden")) and time.monotonic() >= next_hazard_scan:
                    hazard_record = run_hazard_exclusion_cycle(
                        client, snapshot, args.log, map_state)
                    next_hazard_scan = time.monotonic() + 8.0
                    if hazard_record is not None:
                        save_state(args.state, state)
                        print(f"[{hazard_record['timestamp']}] hazard guard: forbade "
                              f"{len(hazard_record['items'])} exposed item(s), released "
                              f"{len(hazard_record['released'])} safe item(s)", flush=True)
                if not care_bootstrapped:
                    # A restart must not forget an unfinished wound from the
                    # previous session. Laya still chooses whether to treat it.
                    post_combat_pending = any(
                        row.get("tendable_now") and not row.get("is_dead")
                        for row in snapshot.get("combat", {}).get("colonists", [])
                    )
                    care_bootstrapped = True
                remaining_retry = retry_not_before - time.monotonic()
                if remaining_retry > 0.0:
                    elapsed = time.monotonic() - started
                    time.sleep(max(0.0, min(2.0, remaining_retry) - elapsed))
                    continue
                caravan_trade_record = run_caravan_trade_cycle(client, agent, snapshot, state, args.log)
                if caravan_trade_record is not None:
                    save_state(args.state, state)
                    print(f"[{caravan_trade_record['timestamp']}] caravan trade: "
                          f"{caravan_trade_record['decision']['choice']} | {caravan_trade_record['result']}", flush=True)
                    elapsed = time.monotonic() - started
                    time.sleep(max(0.0, 2.0 - elapsed))
                    continue
                dialogue_record = run_window_cycle(client, agent, snapshot, state, args.log)
                if dialogue_record is not None:
                    save_state(args.state, state)
                    print(f"[{dialogue_record['timestamp']}] dialogue: "
                          f"{dialogue_record['decision']['choice']} | {dialogue_record['result']}", flush=True)
                    if dialogue_record["result"].get("applied", False) or dialogue_record["decision"]["choice"] != "defer":
                        elapsed = time.monotonic() - started
                        time.sleep(max(0.0, 2.0 - elapsed))
                        continue
                letter_record = run_letter_cycle(client, agent, snapshot, state, args.log)
                if letter_record is not None:
                    save_state(args.state, state)
                    print(f"[{letter_record['timestamp']}] letter: "
                          f"{letter_record['decision']['choice']} | {letter_record['result']}", flush=True)
                    if letter_record.get("mode") == "game-over":
                        return 0
                    if letter_record["decision"]["choice"] != "defer":
                        elapsed = time.monotonic() - started
                        time.sleep(max(0.0, 2.0 - elapsed))
                        continue
                # A new crashlanded game exposes map ruins and pawns before
                # drop-pod cargo arrives.  Planning a base against that partial
                # map permanently pins it to the wrong end of the colony.
                # Advance a few in-game minutes, then let Laya see the cargo.
                if int(snapshot["game"].get("tick") or 0) < 600:
                    if snapshot["game"].get("is_paused"):
                        client.post("/api/v1/game/speed", query={"speed": 1})
                    elapsed = time.monotonic() - started
                    time.sleep(max(0.0, 2.0 - elapsed))
                    continue
                if snapshot["map"]["enemies"] > 0 or any(c.get("is_drafted") for c in snapshot["combat"]["colonists"]):
                    living_hostiles = [h for h in snapshot["combat"]["hostiles"] if not h.get("is_dead")]
                    if any(not hostile.get("is_downed") for hostile in living_hostiles):
                        post_combat_pending = True
                    now = time.monotonic()
                    if live_threat_care_needed(snapshot) and now >= next_live_threat_care_cycle:
                        care_record = run_post_combat_care_cycle(
                            client, agent, snapshot, args.log, live_threat=True)
                        care_choice = str((care_record or {}).get("decision", {}).get("choice") or "")
                        next_live_threat_care_cycle = time.monotonic() + (
                            8.0 if care_choice in {"withdraw_civilian", "defer_care"}
                            else 4.0 if care_record and care_record["result"].get("applied") else 8.0)
                        if care_record is not None:
                            print(f"[{care_record['timestamp']}] live-threat care: "
                                  f"{care_record['decision']['choice']} | {care_record['result']}", flush=True)
                            elapsed = time.monotonic() - started
                            time.sleep(max(0.0, 2.0 - elapsed))
                            continue
                    if living_hostiles and all(h.get("is_downed") for h in living_hostiles):
                        now = time.monotonic()
                        if post_combat_pending and now >= next_post_combat_care_cycle:
                            care_record = run_post_combat_care_cycle(client, agent, snapshot, args.log)
                            if care_record is None:
                                post_combat_pending = recurring_entity_unresolved(snapshot)
                                next_post_combat_care_cycle = now + args.interval
                            else:
                                next_post_combat_care_cycle = now + post_combat_care_retry_delay(
                                    snapshot, bool(care_record["result"].get("applied")), args.interval)
                                if care_record["result"].get("deferred"):
                                    post_combat_pending = bool(care_record["result"].get("revisit"))
                                    if post_combat_pending:
                                        next_post_combat_care_cycle = now + max(60.0, args.interval * 3)
                                    post_combat_care_failures = 0
                                else:
                                    post_combat_care_failures = (0 if care_record["result"].get("applied")
                                                                 else post_combat_care_failures + 1)
                                    if care_record["result"].get("applied"):
                                        care_assignment_time = now
                                if post_combat_care_failures >= 3:
                                    post_combat_pending = False
                                print(f"[{care_record['timestamp']}] post-combat care: {care_record['decision']['choice']} | {care_record['result']}", flush=True)
                                elapsed = time.monotonic() - started
                                time.sleep(max(0.0, 2.0 - elapsed))
                                continue
                        if post_combat_pending and urgent_care_actionable(snapshot):
                            elapsed = time.monotonic() - started
                            time.sleep(max(0.0, 2.0 - elapsed))
                            continue
                        if now >= next_downed_cycle:
                            record = run_downed_raider_cycle(client, agent, state, args.state, args.log)
                            downed_choice = str((record.get("decision") or {}).get("choice") or "")
                            next_downed_cycle = now + (5.0 if recurring_entity_unresolved(snapshot)
                                                       else max(60.0, args.interval * 6)
                                                       if downed_choice in {"leave_downed_raiders", "wait_for_prison"}
                                                       else args.interval)
                            last_combat_record = record
                            print(f"[{record['timestamp']}] downed raider: {record['decision']['choice']} | {record['result']}", flush=True)
                        elif last_combat_record is not None:
                            publish_combat_overlay(client, last_combat_record, repeated=True)
                        if ((last_combat_record or {}).get("decision") or {}).get("choice") in {
                            "leave_downed_raiders", "wait_for_prison",
                        } and now >= next_colony_cycle and not recurring_entity_unresolved(snapshot) \
                                and not snapshot["map"].get("is_temp_incident_map"):
                            development_record = run_development_cycle(client, agent, state, args.state, args.log)
                            next_colony_cycle = time.monotonic() + args.interval
                            print(f"[{development_record['timestamp']}] colony work beside downed raider: "
                                  f"{development_record['decision']['choice']}", flush=True)
                        elapsed = time.monotonic() - started
                        time.sleep(max(0.0, 2.0 - elapsed))
                        continue
                    next_downed_cycle = 0.0
                    signature = combat_order_signature(snapshot)
                    now = time.monotonic()
                    advance_state, advance_body = preemptive_advance_state(snapshot, last_combat_record, now - last_combat_step_time)
                    urgent = advance_state == "replan" or any(
                        bridge.first_number(row.get("distance_to_nearest_opponent"), 9999) < 15
                        for row in living_hostiles
                    )
                    positioning_finished = combat_positioning_finished(
                        snapshot, last_combat_record, now - last_combat_order_time
                    )
                    if advance_state in {"advance", "wait"} and now - last_combat_order_time >= 60:
                        advance_state = "replan"
                    if advance_state == "advance" and advance_body is not None:
                        step_result = client.post("/api/v1/combat/tactic", body=advance_body)
                        last_combat_step_time = now
                        if not step_result.get("positioned_pawn_ids") and not step_result.get("attacking_pawn_ids"):
                            last_combat_signature = None
                        if snapshot["game"].get("is_paused"):
                            client.post("/api/v1/game/speed", query={"speed": 1})
                        publish_combat_overlay(client, last_combat_record, repeated=True)
                    elif advance_state == "wait" or (advance_state != "replan" and not positioning_finished
                                                       and not combat_replan_due(signature, last_combat_signature,
                                                         now - last_combat_order_time, last_combat_record is not None, urgent)):
                        if snapshot["game"].get("is_paused") and living_hostiles:
                            client.post("/api/v1/game/speed", query={"speed": 1})
                        publish_combat_overlay(client, last_combat_record, repeated=True)
                    else:
                        record = bridge.run_cycle(client, agent, apply=True, confidence=0.0, log_path=args.log)
                        publish_combat_overlay(client, record)
                        last_combat_signature = signature
                        last_combat_record = record
                        last_combat_order_time = now
                        last_combat_step_time = now
                        print(f"[{record['timestamp']}] combat: {record['action']['description']}", flush=True)
                    if now >= next_colony_cycle and (last_combat_record or {}).get("decision", {}).get("choice") in {
                        "prepare_undrafted", "continue_safe_colony_work",
                    }:
                        # Refresh after the combat order; the enemy may have begun
                        # advancing while Laya was deciding.
                        staging_snapshot = bridge.collect_snapshot(client)
                        if staging_development_allowed(staging_snapshot, last_combat_record):
                            # This is a second Laya decision, not a scripted work order.
                            # The development state includes the raid phase and distance.
                            development_record = run_development_cycle(client, agent, state, args.state, args.log)
                            next_colony_cycle = time.monotonic() + args.interval
                            print(f"[{development_record['timestamp']}] raid preparation work: "
                                  f"{development_record['decision']['choice']}", flush=True)
                else:
                    last_combat_signature = None
                    last_combat_record = None
                    last_combat_order_time = 0.0
                    last_combat_step_time = 0.0
                    now = time.monotonic()
                    fire_state = bridge.safe_get(client, "/api/v1/map/fire/situation", [],
                                                 map_id=int(snapshot["map"]["id"])) or {}
                    active_home_fire = any(
                        fire.get("in_home") and int(fire.get("nearby_player_buildings") or 0) > 0
                        for fire in fire_state.get("fires") or [])
                    if active_home_fire:
                        next_colony_cycle = min(next_colony_cycle, now)
                    # A lingering post-combat treatment must not keep every
                    # firefighter at low priority while the Home area burns.
                    if post_combat_pending and firefighter_priority_options(snapshot) and active_home_fire:
                        fire_record = run_development_cycle(client, agent, state, args.state, args.log)
                        next_colony_cycle = time.monotonic() + 2.0
                        print(f"[{fire_record['timestamp']}] fire emergency: "
                              f"{fire_record['decision']['choice']} | {fire_record['result']}", flush=True)
                        if (fire_record["decision"]["choice"] == "prioritize_firefighting"
                                and fire_record["result"].get("applied")):
                            continue
                    if (post_combat_pending and care_assignment_time > 0
                            and any(row.get("tendable_now") or row.get("is_downed")
                                    for row in snapshot["combat"]["colonists"])
                            and not urgent_care_actionable(snapshot)
                            and (now - care_assignment_time < 15.0
                                 or ((treatment_job_in_progress(snapshot) or rescue_job_in_progress(snapshot))
                                     and now - care_assignment_time < 120.0))):
                        if snapshot["game"].get("is_paused"):
                            client.post("/api/v1/game/speed", query={"speed": 1})
                        elapsed = time.monotonic() - started
                        time.sleep(max(0.0, min(args.interval, 2.0) - elapsed))
                        continue
                    if post_combat_pending and now >= next_post_combat_care_cycle:
                        care_record = run_post_combat_care_cycle(client, agent, snapshot, args.log)
                        if care_record is None:
                            post_combat_pending = False
                            post_combat_care_failures = 0
                        else:
                            next_post_combat_care_cycle = now + post_combat_care_retry_delay(
                                snapshot, bool(care_record["result"].get("applied")), args.interval)
                            if care_record["result"].get("deferred"):
                                post_combat_pending = bool(care_record["result"].get("revisit"))
                                if post_combat_pending:
                                    next_post_combat_care_cycle = now + max(60.0, args.interval * 3)
                                post_combat_care_failures = 0
                            else:
                                post_combat_care_failures = (0 if care_record["result"].get("applied")
                                                             else post_combat_care_failures + 1)
                                if care_record["result"].get("applied"):
                                    care_assignment_time = now
                            if post_combat_care_failures >= 3:
                                post_combat_pending = False
                            print(f"[{care_record['timestamp']}] post-combat care: {care_record['decision']['choice']} | {care_record['result']}", flush=True)
                            if urgent_care_actionable(snapshot):
                                elapsed = time.monotonic() - started
                                time.sleep(max(0.0, 2.0 - elapsed))
                                continue
                    rescue_record = run_rescue_site_cycle(client, state, args.state, args.log, snapshot)
                    away_site = bool(snapshot.get("map", {}).get("is_temp_incident_map"))
                    if rescue_record is not None:
                        next_colony_cycle = now + args.interval
                        print(f"[{rescue_record['timestamp']}] rescue site: {rescue_record['phase']} | {rescue_record['result']}", flush=True)
                    ancient = get_ancient_danger(client, snapshot["map"]["id"]) if rescue_record is None and not away_site else {}
                    ancient_record = None
                    event_record = None
                    if ancient.get("detected") and ancient.get("sealed"):
                        ancient_record = run_ancient_danger_cycle(client, agent, state, args.state, args.log, ancient)
                        if ancient_record is not None:
                            next_colony_cycle = now + args.interval
                            print(f"[{ancient_record['timestamp']}] ancient danger: {ancient_record['decision']['choice']}", flush=True)
                    if (rescue_record is None and ancient_record is None and not away_site
                            and not active_home_fire and now >= next_colony_cycle):
                        event_record = run_event_cycle(client, agent, state, args.state, args.log)
                        if event_record is not None:
                            next_colony_cycle = now + args.interval
                            print(f"[{event_record['timestamp']}] event: {event_record['decision']['choice']} | {event_record['result']}", flush=True)
                    if rescue_record is None and ancient_record is None and event_record is None and not away_site and now >= next_colony_cycle:
                        record = run_development_cycle(client, agent, state, args.state, args.log)
                        next_colony_cycle = now + (2.0 if active_home_fire else args.interval)
                        print(f"[{record['timestamp']}] colony: {record['decision']['choice']} | {record['result']}", flush=True)
                runtime_state = "running"
                runtime_detail = "Last decision cycle completed"
                consecutive_cycle_errors = 0
                retry_not_before = 0.0
                write_runtime_status(args.runtime_status, runtime_state, runtime_detail)
            except (bridge.RimApiError, OSError, ValueError, RuntimeError) as exc:
                now = time.monotonic()
                detail = str(exc)
                runtime_state, runtime_detail, prefix = classify_runtime_problem(detail)
                retry_delay, consecutive_cycle_errors = cycle_retry_policy(
                    runtime_state, consecutive_cycle_errors, args.interval
                )
                if runtime_state != "waiting":
                    runtime_detail = f"{runtime_detail} Retrying in {retry_delay:.0f}s."
                retry_not_before = time.monotonic() + retry_delay
                write_runtime_status(args.runtime_status, runtime_state, runtime_detail)
                if now - last_wait_message >= 60:
                    print(f"[{bridge.utc_now()}] {prefix}: {exc}", flush=True)
                    last_wait_message = now
                bridge.append_log(args.log, {"timestamp": bridge.utc_now(), "mode": runtime_state, "error": repr(exc)})
            except Exception as exc:
                retry_delay, consecutive_cycle_errors = cycle_retry_policy(
                    "error", consecutive_cycle_errors, args.interval
                )
                retry_not_before = time.monotonic() + retry_delay
                runtime_state = "error"
                runtime_detail = f"Unexpected cycle error: {exc}. Retrying in {retry_delay:.0f}s."
                write_runtime_status(args.runtime_status, runtime_state, runtime_detail)
                traceback.print_exc()
                bridge.append_log(args.log, {"timestamp": bridge.utc_now(), "mode": "error", "error": repr(exc)})
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, 2.0 - elapsed))
    except KeyboardInterrupt:
        print("Stopped. No further commands will be sent.")
        return 0
    finally:
        try:
            write_runtime_status(args.runtime_status, "stopped", "Director stopped")
        except OSError:
            pass
        try:
            if args.pid_file.read_text(encoding="ascii").strip() == str(os.getpid()):
                args.pid_file.unlink(missing_ok=True)
        except OSError:
            pass
        if singleton_handle:
            ctypes.windll.kernel32.CloseHandle(singleton_handle)


if __name__ == "__main__":
    raise SystemExit(main())
