from __future__ import annotations

import re
from typing import Any

import colony_growth as growth


EVENT_FAMILIES: dict[str, dict[str, Any]] = {
    "combat": {"tokens": ("raid", "siege", "attack", "manhunter", "infestation", "mechcluster", "revenant", "sightstealer"), "urgency": 100},
    "kidnap_rescue": {"tokens": ("kidnap", "rescue", "ransom", "prisonerrescue", "captive"), "urgency": 95},
    "fire": {"tokens": ("fire", "flashstorm", "drythunderstorm"), "urgency": 90},
    "disease": {"tokens": ("disease", "plague", "flu", "malaria", "infection", "sickness", "parasite", "mechanite"), "urgency": 85},
    "crop_crisis": {"tokens": ("blight", "cold", "heatwave", "toxicfallout", "volcanicwinter", "longnight"), "urgency": 80},
    "power_crisis": {"tokens": ("solarflare", "emidynamo", "eclipse", "sunblocker"), "urgency": 75},
    "weather": {"tokens": ("weather", "storm", "rain", "fog", "aurora", "cold", "heat"), "urgency": 65},
    "trade": {"tokens": ("trader", "tradeship", "visitor", "caravan"), "urgency": 55},
    "arrival": {"tokens": ("wanderer", "refugee", "podcrash", "wildman", "join", "transportpod"), "urgency": 60},
    "resources": {"tokens": ("resourcepod", "cargopod", "meteorite", "shipchunk", "ambrosia", "sprout", "migration", "selftame"), "urgency": 45},
    "animals": {"tokens": ("thrumbo", "alphabeaver", "animal", "herd", "pack"), "urgency": 50},
    "psychic": {"tokens": ("psychic", "drone", "soothe"), "urgency": 55},
    "quest": {"tokens": ("quest", "royal", "monument", "hospitality", "shuttle", "peace", "charity"), "urgency": 50},
    "anomaly": {"tokens": ("anomaly", "entity", "darkness", "pitgate", "obelisk", "cult", "unnatural", "void"), "urgency": 90},
    "positive": {"tokens": ("inspiration", "party", "wedding", "soothe", "aurora", "good"), "urgency": 20},
}


RESPONSE_OPTIONS: dict[str, dict[str, str]] = {
    "combat": {
        "delegate_to_combat_planner": "Hand the live enemy roster to the tactical planner; do not improvise from the event name alone.",
        "prepare_undrafted": "If enemies are still preparing, let colonists eat, sleep, treat wounds and finish defenses while monitoring them.",
    },
    "kidnap_rescue": {
        "accept_rescue_quest": "Accept a verified rescue/ransom quest when population, expiry, travel distance, threat, food and medicine justify it.",
        "prepare_rescue_mission": "Form a guarded caravan to the quest site, preserving defenders and survival reserves at home.",
        "defer_rescue": "Do not launch an expedition that cannot reach the site or survive the estimated threat.",
    },
    "fire": {
        "protect_home_from_fire": "Expand Home area around a live fire threatening colony buildings and assign a healthy firefighter; a remote fire may be left alone.",
        "prioritize_firefighting": "Set Firefighter priority 1 for healthy colonists and resume time.",
        "observe_event": "Observe only when the fire is remote, rain-controlled or already extinguished.",
    },
    "disease": {
        "prioritize_medical": "Prioritize doctoring, patient bed rest, medicine and clean treatment rooms.",
        "observe_event": "Observe a minor, already-tended condition without repeatedly interrupting work.",
    },
    "crop_crisis": {
        "emergency_harvest": "Harvest mature outdoor crops before blight or lethal temperature destroys them.",
        "pause_sowing": "Stop new outdoor sowing during a condition that prevents a viable harvest.",
        "observe_event": "Preserve work when crops and food reserves are already safe.",
    },
    "power_crisis": {
        "power_emergency": "Protect food, patients and temperature-sensitive rooms; avoid starting new power-dependent projects.",
        "observe_event": "Wait when passive temperature and food reserves safely cover the outage.",
    },
    "weather": {
        "weather_emergency": "Adjust work and shelter priorities using actual temperature and active-condition duration.",
        "observe_event": "No special order when current clothing, rooms and crops are safe.",
    },
    "trade": {
        "trade_now": "Evaluate the live trader inventory and transact before departure using the best healthy negotiator.",
        "skip_trade": "Skip a trader that cannot buy the colony's surplus or offer a useful purchase at a safe price.",
    },
    "arrival": {
        "rescue_arrival": "Pass a downed non-hostile arrival to the colony's live rescue choices; this event acknowledgement alone does not order a rescue.",
        "evaluate_recruit": "Review the join opportunity; an actual joiner letter is answered separately with food, housing and skills context.",
        "observe_event": "Do not attack or capture a neutral arrival without a deliberate reason.",
    },
    "resources": {
        "collect_event_resources": "Unforbid and haul useful event resources when the route and storage are safe.",
        "observe_event": "Leave low-value or dangerous resources until higher priorities are stable.",
    },
    "animals": {
        "evaluate_animals": "Pass actual animals to the existing tame/hunt/leave hierarchy with handler and combat context.",
        "observe_event": "Leave wildlife alone when taming or hunting is unsafe.",
    },
    "psychic": {
        "psychic_schedule_response": "Reduce risky field work and protect affected pawns according to mood and consciousness.",
        "observe_event": "Use no special order when mood and safety remain stable.",
    },
    "quest": {
        "accept_quest": "Accept only after comparing reward, expiry, threat, travel, labor and ideological consequences.",
        "defer_quest": "Leave an offered quest pending while prerequisites are not met.",
    },
    "anomaly": {
        "contain_anomaly": "Prioritize containment and a prepared fallback; do not treat an unknown anomaly as an ordinary raid.",
        "observe_event": "Avoid provoking a dormant entity without sufficient information and force.",
    },
    "positive": {
        "use_opportunity": "Exploit the opportunity only if it does not interrupt survival work.",
        "observe_event": "Let the positive event proceed naturally.",
    },
    "unknown": {
        "ask_laya_generic": "Evaluate this loaded DLC/mod event from its live label, description, category, alerts and targets.",
        "observe_event": "Make no irreversible change when the event exposes no actionable target.",
    },
}


def classify_event(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("incident_def", "def_name", "label", "category", "description", "quest_def", "name")).lower().replace(" ", "")
    for family, spec in EVENT_FAMILIES.items():
        if any(token in text for token in spec["tokens"]):
            return family
    return "unknown"


def event_signature(row: dict[str, Any]) -> str:
    source = row.get("source") or "event"
    identity = row.get("incident_def") or row.get("def_name") or row.get("quest_def") or row.get("name") or row.get("label") or "unknown"
    stamp = row.get("incident_hour") or row.get("started_tick") or row.get("id") or row.get("load_id") or 0
    return f"{source}:{identity}:{stamp}"


def matching_rescue_quests(event: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    """Never mistake a stranger's rescue quest for a kidnapped colonist's."""
    quests = [row for row in context.get("active_quests") or [] if isinstance(row, dict)
              and classify_event(row) == "kidnap_rescue"]
    if event.get("source") == "quest" and event.get("id") is not None:
        return [row for row in quests if str(row.get("id")) == str(event["id"])]
    if event.get("source") != "kidnapped":
        return quests
    name = str(event.get("name") or "").strip()
    if not name:
        return []
    pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)
    return [row for row in quests if pattern.search(" ".join(str(row.get(key) or "")
                for key in ("name", "description", "reward")))]


def pending_events(context: dict[str, Any], handled: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, source in (("recent_incidents", "incident"), ("active_conditions", "condition"), ("active_quests", "quest")):
        for raw in context.get(key) or []:
            if not isinstance(raw, dict):
                continue
            row = {"source": source, **raw}
            signature = event_signature(row)
            if signature in handled:
                continue
            row["signature"] = signature
            row["family"] = classify_event(row)
            row["urgency"] = int(EVENT_FAMILIES.get(row["family"], {}).get("urgency", 35))
            rows.append(row)
    for raw in context.get("trade_opportunities") or []:
        if not isinstance(raw, dict):
            continue
        row = {"source": "trade", "family": "trade", "urgency": 58, **raw}
        row["signature"] = event_signature({**row, "name": raw.get("id")})
        if row["signature"] not in handled:
            rows.append(row)
    for raw in context.get("kidnapped_pawns") or []:
        if not isinstance(raw, dict):
            continue
        row = {"source": "kidnapped", "family": "kidnap_rescue", "urgency": 98, **raw}
        if not matching_rescue_quests(row, context):
            continue
        row["signature"] = event_signature({**row, "name": raw.get("id")})
        if row["signature"] not in handled:
            rows.append(row)
    return sorted(rows, key=lambda row: (-int(row.get("urgency") or 0), str(row.get("signature"))))


def response_options(event: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
    family = str(event.get("family") or "unknown")
    options = dict(RESPONSE_OPTIONS.get(family, RESPONSE_OPTIONS["unknown"]))
    if family == "trade" and not context.get("trade_opportunities"):
        options.pop("trade_now", None)
    if family == "fire" and not any(
        not row.get("in_home") and int(row.get("nearby_player_buildings") or 0) > 0
        for row in (context.get("fire_situation") or {}).get("fires") or []
    ):
        options.pop("protect_home_from_fire", None)
    if family == "kidnap_rescue":
        quests = matching_rescue_quests(event, context)
        accepted = any(bool(row.get("ever_accepted")) for row in quests)
        has_site = any(row.get("look_targets") for row in quests)
        if not quests or accepted:
            options.pop("accept_rescue_quest", None)
        if not accepted:
            options.pop("prepare_rescue_mission", None)
        if not has_site:
            options.pop("prepare_rescue_mission", None)
    return options or {"observe_event": "No verified safe action is currently exposed."}


def event_context_for_model(event: dict[str, Any], context: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    if event.get("family") == "trade":
        # The raw incident and trader rows include every stock item twice. Laya's
        # short decision context then loses the colony's needs and the prices.
        resources = snapshot.get("map", {}).get("resources") or {}
        colonists = snapshot.get("colonists") or []
        hunger = [float(row["hunger"]) for row in colonists
                  if isinstance(row.get("hunger"), (int, float))]
        traders = []
        for trader in (context.get("trade_opportunities") or [])[:4]:
            preview = trader.get("preview") or {}
            row = {
                "id": trader.get("id"), "name": trader.get("name"),
                "silver": preview.get("colony_silver"),
                "reserve": preview.get("minimum_silver_reserve"),
                "trader_silver": preview.get("trader_silver"),
                "can_sell": [
                    f"{row.get('category')} {row.get('example')} x{row.get('maximum_units')} @ {float(row.get('unit_price') or 0):.1f} silver"
                    for row in (preview.get("sale_options") or [])[:8]
                ],
                "can_buy": [
                    f"{row.get('category')} {row.get('example')} x{row.get('maximum_units')} @ {float(row.get('unit_price') or 0):.1f} silver"
                    for row in (preview.get("purchase_options") or [])[:9]
                ],
            }
            humanlike = [
                growth.brief_humanlike_offer_description(offer)
                for offer in (preview.get("humanlike_offers") or [])[:4]
            ]
            if humanlike:
                row["potential_recruits"] = humanlike
            elif any(item.get("humanlike") for item in (trader.get("stock") or [])):
                row["potential_recruits"] = "Trader has people. Selling surplus or choosing a smaller cash reserve may make one affordable."
            traders.append(row)
        model_context = {
            "event": {"family": "trade", "name": event.get("name"),
                      "trader_kind": event.get("trader_kind")},
            "colony": {"population": len(colonists), "food": resources.get("food"),
                       "meals": resources.get("meals"), "raw_food": resources.get("raw_food"),
                       "medicine": resources.get("medicine"),
                       "lowest_hunger": round(min(hunger), 2) if hunger else None,
                       "hostiles": len(snapshot.get("combat", {}).get("hostiles") or [])},
            "traders": traders,
            "tradeoff": "Sell only goods this trader accepts. Selling extra leather, drugs, crops or clothing can fund a recruit in the same deal, but keep food, warm clothing and enough armed defenders. The trader may depart.",
        }
        if any(row.get("potential_recruits") for row in traders):
            model_context["growth"] = {
                key: value for key, value in growth.population_context(snapshot).items()
                if key in {"population", "able_workers", "bedbound", "total_food", "ready_meals", "best_skills", "tradeoff"}
            }
        return model_context
    return {
        "event": event,
        "active_conditions": context.get("active_conditions") or [],
        "alerts": context.get("alerts") or [],
        "quests": context.get("active_quests") or [],
        "kidnapped_pawns": context.get("kidnapped_pawns") or [],
        "trade_opportunities": context.get("trade_opportunities") or [],
        "fire_situation": context.get("fire_situation") or {},
        "colony": {
            "population": len(snapshot.get("colonists", [])),
            "resources": snapshot.get("map", {}).get("resources", {}),
            "lowest_health": min((float(p.get("health") or 0) for p in snapshot.get("colonists", [])), default=1),
            "lowest_mood": min((float(p.get("mood") or 0) for p in snapshot.get("colonists", [])), default=1),
            "hostiles": len(snapshot.get("combat", {}).get("hostiles", [])),
        },
        "rule": "React only to live targets and normal RimWorld mechanics. An unknown mod event gets a conservative generic review, never an invented action.",
    }
