"""Observed inspiration opportunities; models choose whether to spend them."""
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent

DESCRIPTIONS = {"inspirations_recruit": "Choose an exact available warden/prisoner interaction or defer. Inspired recruitment can use the next qualifying interaction; unwavering loyalty is excluded. Recruitment is still pending until observed."}
LABELS = {"inspirations_recruit": "recruitment inspiration opportunity"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {a: "economy_diplomacy" for a in ACTIONS}
ENDPOINT = "/api/v1/inspirations/"


def read(client, snapshot, name):
    result = client.get(ENDPOINT + name, map_id=snapshot["map"]["id"])
    if not isinstance(result, dict) or result.get("available") is not True:
        raise ValueError("inspiration observation unavailable: " + name)
    if not isinstance(result.get("pawns" if name == "context" else "options"), list):
        raise ValueError("malformed inspiration observation: " + name)
    return result


def collect(client, snapshot):
    observed = {"available": True, "endpoint_status": {}}
    for name in ("context", "taming", "recruitment"):
        try:
            data = read(client, snapshot, name)
            if name == "context": observed.update(data)
            else: observed[name] = data
            observed["endpoint_status"][name] = {"available":True}
        except Exception as exc:
            observed["endpoint_status"][name] = {"available":False,"error":str(exc)[:200]}
            if name == "context": observed["pawns"] = []
            else: observed[name] = {"available":False,"options":[]}
    if not any(p["available"] for p in observed["endpoint_status"].values()):
        raise ValueError("All inspiration observations unavailable")
    for pawn in snapshot.get("colonists") or []:
        live = next((p for p in observed.get("pawns") or [] if p.get("pawn_id") == pawn.get("id")), None)
        if live is None and observed["endpoint_status"]["context"]["available"]:
            pawn.pop("inspiration_context",None)
            pawn["inspiration"]=""
        if live is not None:
            pawn["inspiration_context"] = live
            pawn["inspiration"] = live.get("def_name") or ""
    return observed


def opportunities(snapshot, family=None):
    rows = (snapshot.get("development", {}).get("inspirations") or {}).get("pawns") or []
    relevant = {"animal_husbandry": {"Inspired_Taming"}, "art_culture": {"Inspired_Creativity", "Frenzy_Work"},
                "craft_industry": {"Inspired_Creativity", "Frenzy_Work"}, "medicine_biotech": {"Inspired_Surgery"},
                "trade_diplomacy": {"Inspired_Trade", "Inspired_Recruitment"}, "security_hunting": {"Frenzy_Shoot", "Frenzy_Go"}}
    return [{"pawn": p.get("name"), "id": p.get("pawn_id"), "def": p.get("def_name"),
             "left": p.get("remaining_ticks"), "effect": p.get("effect")}
            for p in rows if isinstance(p, dict) and p.get("def_name")
            and (family is None or p.get("def_name") in relevant.get(family, {"Frenzy_Work", "Frenzy_Go"}))][:8]


def _scope(plan):
    return repr((plan.get("key"),plan.get("expected_inspiration"),plan.get("expected_identity")))


def _history(memory,snapshot):
    tick=int(snapshot.get("game",{}).get("tick") or 0)
    map_id=snapshot["map"]["id"]
    state=memory.setdefault("inspiration_order_history",{})
    if state.get("map_id")!=map_id or tick < state.get("tick",tick):
        state.clear();state.update(map_id=map_id,entries={})
    state["tick"]=tick
    entries=state.setdefault("entries",{})
    for key in list(entries):
        if not recent(entries[key],tick,600):del entries[key]
    while len(entries)>128:entries.pop(next(iter(entries)))
    return entries


def ready_pairs(plans,memory,snapshot):
    history=_history(memory,snapshot)
    return {k:p for k,p in plans.items() if _scope(p) not in history}


def tame_options(snapshot):
    rows = (snapshot.get("development", {}).get("inspirations", {}).get("taming") or {}).get("options") or []
    return {p["key"]: p for p in rows if isinstance(p, dict) and isinstance(p.get("key"), str)
            and isinstance(p.get("worker_id"), int) and isinstance(p.get("target_id"), int)}


def tame_description(p):
    chance = "guaranteed next attempt" if p.get("guaranteed_attempt") else "ordinary chance; failure may provoke revenge"
    return (f"{p.get('label')}; displaces {p.get('worker_job')}; walk {p.get('distance')}; Animals {p.get('animals_skill')}/{p.get('minimum_skill')}; {chance}; "
            f"effective tame stat {p.get('tame_chance_stat')}; value {p.get('value')}; {p.get('products')}; wildness {p.get('wildness')}; revenge {p.get('revenge_on_failure')}; "
            f"food {p.get('food_count')} from {p.get('food_id') or 'carried food'}; inspiration left {p.get('remaining_ticks')}")


def exact_order(client, snapshot, original, kind, memory=None):
    history=_history(memory,snapshot) if memory is not None else None
    if history is not None and _scope(original) in history:
        return {"applied":False,"reason":"inspiration_pair_wait","blocks_development":False}
    def failed(result):
        if history is not None and not result.get("reconsider"):
            history[_scope(original)]=failure_record(int(snapshot.get("game",{}).get("tick") or 0),seconds=60)
        return result
    try:
        current = read(client, snapshot, "taming" if kind == "tame" else "recruitment")
    except Exception as exc:
        return failed({"applied": False, "reason": "inspiration_observation_failed", "error": str(exc)[:200]})
    live = next((p for p in current["options"] if p.get("key") == original.get("key")), None)
    if live is None:
        return {"applied": False, "reason": "exact_pair_no_longer_available", "reconsider": True}
    identity = ("worker_id", "target_id", "expected_inspiration", "expected_identity")
    if any(live.get(k) != original.get(k) for k in identity):
        return {"applied": False, "reason": "inspiration_changed_reconsider", "reconsider": True}
    try:
        response = client.post(ENDPOINT + kind, body={"map_id": snapshot["map"]["id"],
            **{k: live.get(k) for k in identity}})
    except Exception as exc:
        # A lost acknowledgement is unknown. Reobserve the actual actor/target job before retrying.
        try:
            pawns=read(client,snapshot,"context")["pawns"]
            actor=next((p for p in pawns if p.get("pawn_id")==live["worker_id"]),{})
            if actor.get("current_job")==("Tame" if kind=="tame" else "PrisonerAttemptRecruit") and actor.get("current_job_target_id")==live["target_id"]:
                response={"applied":True,"reason":"exact_job_observed_after_lost_ack","worker_id":live["worker_id"],"target_id":live["target_id"]}
            else: return failed({"applied":False,"reason":"inspiration_transport_unknown","outcome_unknown":True,"error":str(exc)[:200]})
        except Exception:
            return failed({"applied":False,"reason":"inspiration_transport_unknown","outcome_unknown":True,"error":str(exc)[:200]})
    if not isinstance(response, dict) or not isinstance(response.get("applied"), bool):
        return failed({"applied": False, "reason": "invalid_inspiration_response", "outcome_unknown": True, "response": response})
    result={**response,"response":response}
    if not response["applied"]: return failed(result)
    if history is not None:
        history[_scope(original)]=failure_record(int(snapshot.get("game",{}).get("tick") or 0),seconds=60)
    return result


def prepare(snapshot, memory):
    context = snapshot.setdefault("development", {}).setdefault("inspirations", {})
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    history = memory.setdefault("inspiration_recruit_defer", {})
    for key in list(history):
        if not recent(history[key], tick, 15000): del history[key]
    rows = (context.get("recruitment") or {}).get("options") or []
    context["recruit_options"] = ready_pairs({p["key"]: p for p in rows if isinstance(p, dict) and p.get("key")
        and p.get("expected_inspiration") == "Inspired_Recruitment"
        and not recent(history.get(repr((p["key"],p.get("expected_identity")))),tick,15000)},memory,snapshot)
    return ["inspirations_recruit"] if context["recruit_options"] else []


def choose(agent, state, action, snapshot):
    plans = snapshot["development"]["inspirations"].get("recruit_options") or {}
    rows = {f"o{i}": p for i,p in enumerate(plans.values())}
    effects = {k: {"benefit": f"{p.get('label')}; {p.get('inspiration')}", "cost": "Warden time; consumes next qualifying inspiration",
                  "risk": "Colonist joins only after actual interaction; current urgent jobs protected", "inaction": "Prisoner remains; inspiration may expire",
                  "uncertainty": "Actual native interaction pending"} for k,p in rows.items()}
    effects["defer"] = {"benefit": "Preserve worker time and inspiration", "cost": "No new order", "risk": "Inspiration expiry", "inaction": "Prisoner remains", "uncertainty": "Future opportunities unknown"}
    key,raw = ask_laya_choice(agent,{**state,"decision_facts":state.get("decision_facts") or state.get("attention_facts") or {},"option_effects":effects},"inspiration_recruitment","Choose a native eligible pair or defer.",
                              {**{k:p.get("label") for k,p in rows.items()},"defer":"Preserve current work"},detailed=True)
    if key not in {*rows,"defer"}: raise ValueError("Unverified inspiration choice")
    return {"inspiration_plan":rows.get(key),"deferred_inspiration_plans":list(plans.values()) if key=="defer" else []},raw


def execute(client,snapshot,memory,action,selected):
    plan=selected.get("inspiration_plan")
    if not plan:
        history=memory.setdefault("inspiration_recruit_defer",{})
        for p in selected.get("deferred_inspiration_plans") or []:
            history[repr((p["key"],p.get("expected_identity")))]=failure_record(int(snapshot.get("game",{}).get("tick") or 0))
        while len(history)>64: history.pop(next(iter(history)))
        return {"applied":False,"reason":"laya_deferred"}
    observed=(snapshot.get("development",{}).get("inspirations",{}).get("recruit_options") or {}).get(plan.get("key"))
    if observed!=plan:return {"applied":False,"reason":"unverified_inspiration_pair"}
    return exact_order(client,snapshot,plan,"recruit",memory)


def assess(action,snapshot):
    return {"available":bool(snapshot.get("development",{}).get("inspirations",{}).get("recruit_options")),
            "benefit":"Choose exact inspired warden and recruitable prisoner; next qualifying interaction succeeds",
            "risk":"Current work displaced; inspiration consumed only by actual qualifying interaction; unwavering loyalty excluded",
            "cost":"Warden time and future colony food/housing", "inaction":"Prisoner remains; timed inspiration may expire",
            "uncertainty":"Accepted job is not completed recruitment; native readiness revalidated"}
