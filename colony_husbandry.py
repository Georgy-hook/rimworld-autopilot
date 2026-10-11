"""Shared husbandry planning from measured native needs, feed and season data.

No game commands live here. Stock, reachable feed, pasture and future crops stay
separate; a seasonal mean or an accepted job is never a survival guarantee.
"""
from __future__ import annotations

from collections import deque
import copy
import math


def number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def native_context(snapshot):
    return ((snapshot.get("development") or {}).get("sustenance") or {}).get("husbandry") or {}


def _unique_pools(context):
    seen = set()
    for i, pool in enumerate(context.get("feed_pools") or []):
        identity = pool.get("thing_id", ("row", i))
        if identity in seen: continue
        seen.add(identity)
        yield pool


def _human_capacity(context, days):
    stock = number(context.get("human_nutrition"))
    minimum = number(context.get("human_reserve_nutrition"))
    daily = number(context.get("human_demand_nutrition_day"))
    # An unknown human demand cannot authorize spending shared human food on
    # a long animal reserve. Dedicated hay/feed remains usable independently.
    if None in (stock, minimum, daily): return 0.
    return max(0., stock-max(minimum, daily*days))


def _reserve_horizon(context):
    horizon = 15.
    hostile_start = None
    for period in context.get("seasonal_means") or []:
        mean = number(period.get("mean_c")); offset = number(period.get("offset_days"))
        duration = number(period.get("duration_days"))
        if None in (mean, offset, duration): continue
        hostile = mean <= 0 or mean >= 42
        if hostile_start is None and hostile and offset <= 15: hostile_start = offset
        if hostile_start is not None:
            if not hostile: break
            horizon = max(horizon, offset+max(0., duration))
    bridge=number(context.get("post_climate_feed_growth_days_normal"))
    if hostile_start is not None and bridge is not None: horizon+=max(0.,bridge)
    return horizon


def _allocated_nutrition(animals, pools, days, human_capacity, *, access):
    """Continuous nutrition allocation: each shared stack can be spent once."""
    edges = {}
    def edge(a, b, cap):
        edges.setdefault(a, {})[b] = edges.setdefault(a, {}).get(b, 0) + max(0, cap)
        edges.setdefault(b, {}).setdefault(a, 0)
    demand = sum(a["recovery_nutrition_per_day"] * days for a in animals)
    edge("source", "human_food", human_capacity)
    seen = set()
    for i, pool in enumerate(pools):
        identity = pool.get("thing_id", ("row", i))
        if identity in seen: continue
        seen.add(identity)
        rot = number(pool.get("ticks_until_rot"))
        if rot is not None and rot < days * 60000: continue
        amount = number(pool.get("nutrition"))
        if amount is None or amount <= 0: continue
        node = ("pool", i)
        edge("human_food" if pool.get("human_edible") else "source", node, amount)
        ids = pool.get("accessible_ids" if access else "compatible_ids") or []
        for animal in animals:
            if animal["id"] in ids: edge(node, ("animal", animal["id"]), demand)
    for animal in animals:
        edge(("animal", animal["id"]), "sink", animal["recovery_nutrition_per_day"] * days)
    delivered = 0.0
    while delivered + 1e-7 < demand:
        parent = {"source": None}; queue = deque(["source"])
        while queue and "sink" not in parent:
            node = queue.popleft()
            for target, capacity in edges.get(node, {}).items():
                if capacity > 1e-8 and target not in parent:
                    parent[target] = node; queue.append(target)
        if "sink" not in parent: return delivered
        flow = demand - delivered; node = "sink"
        while parent[node] is not None:
            flow = min(flow, edges[parent[node]][node]); node = parent[node]
        node = "sink"
        while parent[node] is not None:
            source = parent[node]; edges[source][node] -= flow; edges[node][source] += flow; node = source
        delivered += flow
    return delivered


def _feeds_cover(animals, pools, days, human_capacity, *, access):
    needed=sum(a['recovery_nutrition_per_day']*days for a in animals)
    return _allocated_nutrition(animals,pools,days,human_capacity,access=access)+1e-7>=needed


def feed_cover_days(context, *, access=True):
    animals = context.get("animals") or []
    if not animals or any(number(a.get("recovery_nutrition_per_day")) is None for a in animals): return None
    if sum(a["recovery_nutrition_per_day"] for a in animals) <= 0: return None
    lower, upper = 0., 60.
    for _ in range(18):
        middle = (lower + upper) / 2
        if _feeds_cover(animals, list(_unique_pools(context)), middle, _human_capacity(context, middle), access=access): lower=middle
        else: upper=middle
    return round(lower, 3)


def planning_context(snapshot, *, margin=1.25):
    context = native_context(snapshot)
    if context.get("available") is not True:
        return {"available": False, "reason": context.get("reason", "native_husbandry_not_observed")}
    animals = context.get("animals") or []
    if any(number(a.get("recovery_nutrition_per_day")) is None or number(a.get("adult_baseline_nutrition_per_day")) is None for a in animals):
        return {"available":False,"reason":"nutrition_demand_unavailable"}
    # Prepare before an approaching cold/hot season, not only after grass is
    # gone. Public seasonal means are a planning assumption, not weather.
    horizon = _reserve_horizon(context)
    now = sum(a["recovery_nutrition_per_day"] for a in animals)
    grown = sum(max(a["recovery_nutrition_per_day"], a["adult_baseline_nutrition_per_day"]) for a in animals)
    births = 0.; unknown_births = 0; future=[]
    for animal in animals:
        future.append({**animal, "recovery_nutrition_per_day":max(animal["recovery_nutrition_per_day"],animal["adult_baseline_nutrition_per_day"])})
        if not animal.get("pregnant"): continue
        due = number(animal.get("birth_days_nominal"))
        litter = number(animal.get("litter_max_estimate")); baby = number(animal.get("newborn_baseline_nutrition_per_day"))
        if due is None or litter is None or baby is None: unknown_births += 1
        elif due < horizon:
            # Adult allowance for offspring is deliberately conservative.
            extra = max(baby, animal["adult_baseline_nutrition_per_day"]) * litter * (horizon-max(0,due))
            births += extra
            future[-1]["recovery_nutrition_per_day"] += extra/horizon
    amounts = [number(f.get("nutrition")) for f in _unique_pools(context)]
    stored = sum(v for v in amounts if v is not None)
    result = {"available":True, "observed_tick":context.get("observed_tick"), "animals":len(animals),
        "demand_now_nutrition_day":round(now,3), "adult_allowance_nutrition_day":round(grown,3),
        "reserve_horizon_days":horizon, "reserve_margin":margin,
        "reserve_target_nutrition":round((grown*horizon+births)*max(1.,margin),3),
        "birth_allowance_nutrition":round(births*max(1.,margin),3), "unknown_pregnancies":unknown_births,
        "stored_compatible_nutrition":round(stored,3),
        "unallocated_corpse_sources":len(context.get("corpse_food_potential") or []),
        "accessible_cover_days":feed_cover_days(context),
        "stock_cover_days_if_delivered":feed_cover_days(context,access=False),
        "human_reserve_nutrition":context.get("human_reserve_nutrition"),
        "human_horizon_reserve_nutrition":(round(max(context["human_reserve_nutrition"],context["human_demand_nutrition_day"]*horizon),3)
            if number(context.get("human_reserve_nutrition")) is not None and number(context.get("human_demand_nutrition_day")) is not None else None),
        "climate_forecast_known":bool(context.get("seasonal_means")),
        "forecast_is_conditional":True, "pasture_not_in_stock":True}
    supplied=_allocated_nutrition(future,list(_unique_pools(context)),horizon*max(1.,margin),
        _human_capacity(context,horizon),access=False)
    result['reserve_deficit_nutrition']=round(max(0.,result['reserve_target_nutrition']-supplied),3)
    result["fodder_gap"] = unknown_births>0 or result['reserve_deficit_nutrition']>1e-7
    return result


def brief(snapshot):
    plan = planning_context(snapshot)
    if not plan.get("available"): return {"livestock_forecast":"unavailable"}
    result={k:plan[k] for k in ("animals","demand_now_nutrition_day","reserve_horizon_days",
        "reserve_target_nutrition","accessible_cover_days","stock_cover_days_if_delivered","human_reserve_nutrition")}
    if plan["unallocated_corpse_sources"]: result["unallocated_corpse_sources"]=plan["unallocated_corpse_sources"]
    return result


def comfort_intersection(animals):
    minimum = [number(a.get("min_comfortable_temperature",a.get("comfortable_min"))) for a in animals]
    maximum = [number(a.get("max_comfortable_temperature",a.get("comfortable_max"))) for a in animals]
    if not animals or None in minimum or None in maximum: return None
    return [max(minimum),min(maximum)]


def crop_feed_estimate(definition, site, reserve=None, animal_ids=None):
    days = number(definition.get("calendar_days_to_harvest_estimate"))
    yield_ = number(definition.get("harvest_yield")); nutrition = number(definition.get("product_nutrition"))
    cells = number(definition.get("legal_cells"))
    amount = cells*yield_*nutrition if None not in (cells,yield_,nutrition) else None
    grazed = bool(site.get("pen_ids") and definition.get("grazing_animal_ids"))
    live = number(definition.get("live_plant_nutrition"))
    compatible=definition.get('compatible_product_animal_ids') or []
    deficit=number((reserve or {}).get('reserve_deficit_nutrition'))
    per_cell=yield_*nutrition if None not in (yield_,nutrition) else None
    needed=(math.ceil(deficit/per_cell) if not grazed and deficit is not None and per_cell is not None
        and per_cell>0 and animal_ids and set(animal_ids).issubset(compatible) else None)
    return {"compatible_ids":compatible,
        "graze_ids":definition.get("grazing_animal_ids") or [],
        "pen_ids":site.get("pen_ids"), "harvest_days":None if grazed else days,
        "potential_nutrition":round(amount,3) if amount is not None and not grazed else None,
        "nutrition_day":round(amount/days,3) if not grazed and amount is not None and days is not None and days>0 else None,
        "live_graze_nutrition_per_mature_plant":live if grazed else None,
        "grazing_prevents_assured_harvest":grazed,
        "sow_and_harvest_work": (definition.get("work_to_sow") or 0)+(definition.get("work_to_harvest") or 0),
        "delivered_nutrition":0, 'reserve_deficit_nutrition':deficit,
        'harvest_cells_lower_bound':needed,
        'cell_estimate_is_conditional':True}


def straw_feeding_safe(snapshot, hay_cost):
    context = copy.deepcopy(native_context(snapshot))
    unit = number(context.get("hay_unit_nutrition"))
    if context.get("available") is not True or unit is None or unit<=0: return False
    remaining = hay_cost*unit
    for pool in context.get("feed_pools") or []:
        if pool.get("def_name") != "Hay": continue
        used = min(remaining,max(0,number(pool.get("nutrition")) or 0))
        pool["nutrition"] -= used; remaining -= used
    # If no animal can eat hay, it is still a legal building resource.
    compatible_hay = any(p.get("def_name")=="Hay" for p in context.get("feed_pools") or [])
    if compatible_hay and remaining > 1e-7: return False
    forecast = planning_context({"development":{"sustenance":{"husbandry":context}}})
    return forecast.get("available") and not forecast.get("fodder_gap")
