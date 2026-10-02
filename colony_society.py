"""Live human needs and reversible care, prisoner and learning policies."""
from __future__ import annotations
from typing import Any
from laya_decisions import ask_laya_choice

DESCRIPTIONS = {
    "society_medical_care": "Choose a patient's permitted medicine ceiling. Treatment still requires a doctor, access and supplies; compare illness and immunity with medicine scarcity.",
    "society_prisoner_policy": "Choose whether to recruit, reduce resistance or maintain a held prisoner. Recruitment takes warden time and adds food and shelter needs; conversion is a separate choice.",
    "society_free_time": "Give a child learning time or an adult recreation time by changing one work hour. Ordinary autonomous activities need accessible facilities and awake companions; lost work may matter.",
}
LABELS = {"society_medical_care": "допуск лекарств пациенту", "society_prisoner_policy": "план общения с пленником", "society_free_time": "время учёбы и отдыха"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {"society_medical_care": "care", "society_prisoner_policy": "economy_diplomacy", "society_free_time": "work_orders"}
CARE_JOBS = {"TendPatient", "Rescue", "FeedPatient", "DoBill"}

def collect(client: Any, snapshot: dict) -> dict:
    try:
        context = client.get("/api/v1/society/context", map_id=snapshot["map"]["id"])
        return context if isinstance(context, dict) else {"available": False, "reason": "invalid_context"}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

def prepare(snapshot: dict, map_state: dict) -> list[str]:
    context = snapshot.setdefault("development", {}).setdefault("society", {})
    plans = {action: {} for action in ACTIONS}
    for p in context.get("people") or []:
        pid = p.get("pawn_id")
        if pid is None or p.get("dead"):
            continue
        if p.get("medical_attention") and p.get("care_options"):
            for care in p["care_options"]:
                if care != p.get("medical_care"):
                    plans["society_medical_care"][f"{pid}:{care}"] = {"pawn_id": pid, "kind": "medical", "value": care, "person": p}
        for mode in p.get("prisoner_options") or []:
            if mode != p.get("prisoner_mode"):
                plans["society_prisoner_policy"][f"{pid}:{mode}"] = {"pawn_id": pid, "kind": "prisoner", "value": mode, "person": p}
        needs = {n.get("def_name"): n.get("level") for n in p.get("needs") or []}
        learning = needs.get("Learning")
        joy = needs.get("Joy")
        if not p.get("downed") and not p.get("drafted") and not p.get("mental_state") and p.get("current_job") not in CARE_JOBS and ((isinstance(learning, (int, float)) and learning < .9) or (isinstance(joy, (int, float)) and joy < .5)):
            for hour, assignment in enumerate(p.get("timetable") or []):
                if assignment == "Work":
                    plans["society_free_time"][f"{pid}:{hour}"] = {"pawn_id": pid, "kind": "timetable", "hour": hour, "value": "Joy", "person": p}
    context["options"] = plans
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    return [a for a, rows in plans.items() if rows and tick - int((map_state.get("issued") or {}).get("society:" + a, -1000000)) >= 15000]

def assess(action: str, snapshot: dict) -> dict:
    facts = {
        "society_medical_care": ("Permits the selected medicine quality for normal treatment.", "Medicine consumption and doctor time.", "A ceiling does not guarantee medicine or timely treatment; lowering it can worsen care.", "Current restrictions can delay appropriate treatment."),
        "society_prisoner_policy": ("Normal wardens can pursue the selected social goal.", "Warden time, prisoner food and possible new colonist upkeep.", "Recruitment can fail; beliefs and prison breaks still matter.", "A maintained prisoner makes no recruitment progress."),
        "society_free_time": ("Allows ordinary recreation or child learning activities in one hour.", "One hour previously available for work.", "Facilities, safe space and available adults may still be missing.", "Low learning limits growth choices; low recreation contributes to low mood."),
    }
    b, c, r, i = facts[action]
    return dict(benefit=b, cost=c, risk=r, inaction=i, uncertainty="Live needs and policy are observed; future jobs and outcomes are not guaranteed.")

def choose(agent: Any, state: dict, action: str, snapshot: dict) -> tuple[dict, dict]:
    plans = snapshot.get("development", {}).get("society", {}).get("options", {}).get(action) or {}
    effects = assess(action, snapshot)
    def describe(row: dict) -> str:
        p = row["person"]
        if row["kind"] == "medical":
            return f"{row['value']}: medicine cost; ceiling only; {p.get('name')} current {p.get('medical_care')}; disease {p.get('conditions')}"
        if row["kind"] == "prisoner":
            return f"{row['value']}: warden time, replaces {p.get('prisoner_mode')}; {p.get('name')} resistance {p.get('resistance')}; beliefs {p.get('ideology')} certainty {p.get('certainty')}"
        return f"Lose work hour {row.get('hour')}; allow learning/recreation, facilities still needed; {p.get('name')} needs {[(n.get('def_name'), n.get('level')) for n in p.get('needs') or [] if n.get('def_name') in {'Joy', 'Learning', 'Mood'}]}"
    criteria = {key: describe(row) for key, row in plans.items()}
    criteria["defer"] = "Keep current policy; preserve supplies and work time; unmet needs and resistance may persist."
    people = {str(row["pawn_id"]): row["person"] for row in plans.values()}
    if not people:
        return {"defer": True}, {"reason": "no_live_society_options"}
    patient_options = {pid: f"{p.get('name')}; current care {p.get('medical_care')}, prisoner goal {p.get('prisoner_mode')}; resistance {p.get('resistance')}; needs {[(n.get('def_name'), n.get('level')) for n in p.get('needs') or [] if n.get('def_name') in {'Learning', 'Joy', 'Mood'}]}; conditions {p.get('conditions')}" for pid, p in people.items()}
    patient_options["defer"] = criteria["defer"]
    pid, first = ask_laya_choice(agent, {"choice_context": {"risk": effects["risk"], "cost": effects["cost"]}, "colony": state}, action + "_person", "Choose who needs this policy change, or defer.", patient_options, detailed=True)
    if pid == "defer":
        return {"defer": True}, first
    people = {pid: people[pid]}
    plans = {k: row for k, row in plans.items() if str(row["pawn_id"]) == pid}
    criteria = {key: describe(row) for key, row in plans.items()}
    criteria["defer"] = "Keep the current policy; unmet needs may persist."
    facts = {pid: {"conditions": p.get("conditions"), "beliefs": p.get("beliefs"), "negative_thoughts": [t for t in p.get("thoughts") or [] if float(t.get("mood_offset") or 0) < 0], "break_threshold": p.get("minor_break_threshold"), "learning_desires": p.get("learning_desires")} for pid, p in people.items()}
    context = snapshot.get("development", {}).get("society", {})
    staff = [{"name": p.get("name"), "medicine": p.get("medicine_skill"), "social": p.get("social_skill"), "doctor": p.get("can_doctor"), "warden": p.get("can_warden"), "doctor_priority": p.get("doctor_priority"), "warden_priority": p.get("warden_priority")} for p in context.get("people") or [] if p.get("can_doctor") or p.get("can_warden")]
    visible = {"choice_context": {"medicine": context.get("medicine"), "people": facts, "staff": staff, "effects": effects}, "colony": state}
    key, raw = ask_laya_choice(agent, visible, action, DESCRIPTIONS[action], criteria, detailed=True)
    raw["society_person_choice"] = first
    return ({"defer": True} if key == "defer" else {k: v for k, v in plans[key].items() if k != "person"}), raw

def execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    if selected.get("defer"):
        map_state.setdefault("issued", {})["society:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
        return {"applied": False, "reason": "laya_deferred"}
    payload = {k: selected[k] for k in ("pawn_id", "kind", "value", "hour") if k in selected}
    live = collect(client, snapshot)
    fresh = {"map": snapshot["map"], "development": {"society": live}}
    prepare(fresh, {})
    rows = live.get("options", {}).get(action, {})
    if not any({k: v for k, v in row.items() if k != "person"} == payload for row in rows.values()):
        return {"applied": False, "reason": "selection_no_longer_feasible"}
    result = client.post("/api/v1/society/policy", body={"map_id": snapshot["map"]["id"], **payload})
    if isinstance(result, dict) and result.get("applied"):
        map_state.setdefault("issued", {})["society:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
    return result if isinstance(result, dict) else {"applied": False, "reason": "invalid_response"}
