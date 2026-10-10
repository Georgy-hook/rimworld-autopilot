"""Choose a visible connected vein and ordinary miner; observe output separately."""
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent
import colony_labor as labor

DESCRIPTIONS = {'mining_extract': 'Choose a visible connected mineral vein and an available miner. Compare concrete product, remaining HP, loaded yield, native mining stats, travel, food/care coverage and buyer availability. Designations and a mining job are not output, delivery or profit.'}
DESCRIPTIONS['mining_haul'] = 'Choose a reachable mineral stack and a native ordinary haul to completed storage. This transports observed goods; it does not prove their origin or a sale.'
LABELS = {'mining_haul':'перевозка добытых материалов', 'mining_extract': 'добыча конкретной жилы выбранным шахтёром'}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {a: 'work_orders' for a in ACTIONS}


def collect(client, snapshot):
    data = client.get('/api/v1/mining/context', map_id=snapshot['map']['id'])
    if not isinstance(data, dict) or data.get('available') is not True or not isinstance(data.get('options'), list):
        raise ValueError('mining observation unavailable')
    return data


def token(value):
    return str(value or '').replace('_', '').lower()


def plans(snapshot, action=None):
    people = {p.get('id'): p for p in snapshot.get('colonists') or []}
    return {p['key']: p for p in snapshot.get('development', {}).get('mining', {}).get('options') or []
            if isinstance(p, dict) and isinstance(p.get('key'), str) and p.get('product_def')
            and p.get('thing_ids') and len(p['thing_ids']) <= 12
            and (action is None or (p.get('kind', 'extract') == 'haul') == (action == 'mining_haul'))
            and p.get('worker_id') in people and labor.can_assign(snapshot, people[p['worker_id']], 'Hauling' if p.get('kind')=='haul' else 'Mining')}


def prepare(snapshot, memory):
    context = snapshot.get('development', {}).get('mining') or {}
    tick = int(snapshot.get('game', {}).get('tick') or 0)
    history = memory.setdefault('mining_history', {})
    for key in list(history):
        row = history[key]
        if not isinstance(row,dict) or row.get('map_id') != snapshot['map']['id'] or not recent(row, tick, 30000):
            del history[key]
    preferred = (memory.get('doctrine') or {}).get('mining_product') or memory.get('mining_product')
    ready = plans(snapshot)
    for key, plan in ready.items():
        plan['preferred_product'] = token(preferred) in {token(plan.get('product_def')), token(plan.get('ore_def'))}
    # A new vein has its own subject even if an older income doctrine was deferred.
    context['prepared_options'] = {k: p for k, p in ready.items() if k not in history}
    prior = memory.get('mining_intent') or {}
    if prior and prior.get('map_id') == snapshot['map']['id'] and tick >= prior.get('tick', tick):
        # Options omit designated blocks. Only the general visible ore observation
        # can show disappearance; a plan disappearing is not a mined block.
        ores = snapshot.get('development', {}).get('ores') or {}
        groups = ores.get('ores')
        identity_available = isinstance(groups, dict) and all(
            isinstance(g, dict) and isinstance(g.get('thing_ids'), list) for g in groups.values())
        ids = {i for g in groups.values() for i in g['thing_ids']} if identity_available else set()
        stock = next((p.get('count') for p in context.get('product_stocks') or []
                      if p.get('product_def') == prior.get('product_def')), 0)
        context['progress'] = {'selected_blocks_no_longer_observed': len(set(prior.get('thing_ids') or [])-ids) if identity_available else None,
            'product_stock': stock, 'product_stock_change': stock-prior.get('product_stock', 0),
            'completion': 'stock change/disappearance do not prove actor attribution, hauling or a sale'}
    return [a for a in ACTIONS if any(k in context.get('prepared_options', {}) for k in plans(snapshot,a))]


def effects(plan):
    if plan.get('kind') == 'haul':
        return {'benefit':f"Transport {plan.get('base_yield')} {plan['product_def']} to the native destination", 'cost':f"Hauler {plan.get('worker')}, travel {plan.get('travel_distance')}", 'risk':'Displaces worker; destination and both route legs rechecked', 'inaction':'Goods remain where observed', 'uncertainty':'No source attribution or sale; delivery unverified'}
    return {'benefit': f"{plan['product_def']}: base yield {plan.get('base_yield')}, nominal value {plan.get('nominal_market_value')} before trader modifiers",
            'cost': f"{plan.get('worker')}: Mining {plan.get('mining_skill')}, travel {plan.get('travel_distance')}, HP {plan.get('remaining_hp')}, native speed/yield {plan.get('mining_speed')}/{plan.get('mining_yield')}",
            'risk': 'Miner displaced from other labor; travel/exposure. No food produced. Fresh native path and whole-batch roof support are rechecked.',
            'inaction': 'Visible resource remains; food/care may take priority',
            'uncertainty': 'No measured income per hour; a buyer, negotiation, output and delivery remain necessary'}


def choose(agent, state, action, snapshot):
    allowed = plans(snapshot,action)
    rows = {k:p for k,p in snapshot['development']['mining'].get('prepared_options',allowed).items() if k in allowed}
    products = sorted({p['product_def'] for p in rows.values()})
    product_choices = {p: p + ('; chosen doctrine product' if any(r.get('preferred_product') for r in rows.values() if r['product_def'] == p) else '') for p in products}
    product_choices['defer'] = 'Preserve labor for food/care; defer extraction'
    facts = {'food_nutrition': snapshot.get('map', {}).get('resources', {}).get('nutrition'),
             'people': [{k: p.get(k) for k in ('id','current_job','downed','hunger')} for p in snapshot.get('colonists') or []],
             'buyer_status': snapshot.get('quest_context', {}).get('trade_opportunities', 'unknown'),
             'option_effects': {p: effects(next(r for r in rows.values() if r['product_def'] == p)) for p in products}}
    product, first = ask_laya_choice(agent, {'decision_facts':facts}, 'mining_product', DESCRIPTIONS[action], product_choices, detailed=True)
    if product == 'defer':
        return {'mining_plan':'defer', 'shown_mining_options':list(rows)}, {'stages':[first]}
    if product not in products:
        raise ValueError('Unverified mineral product')
    indexed = {f'v{i}': (key, p) for i, (key, p) in enumerate(rows.items()) if p['product_def'] == product}
    criteria = {alias: f"{p.get('worker')}; {p.get('ore_def')} at {p['cells'][0]}, {len(p['thing_ids'])}/{p.get('vein_cells')} cells" for alias, (_, p) in indexed.items()}
    criteria['defer'] = 'Keep labor on current needs; defer this product'
    chosen, raw = ask_laya_choice(agent, {'decision_facts':{**facts, 'option_effects':{a:effects(p) for a,(_,p) in indexed.items()}}},
                                  'mining_vein_and_worker', DESCRIPTIONS[action], criteria, detailed=True)
    if chosen == 'defer':
        return {'mining_plan':'defer', 'shown_mining_options':[k for k,p in rows.items() if p['product_def']==product]}, {'stages':[first,raw]}
    if chosen not in indexed:
        raise ValueError('Unverified vein/worker')
    return {'mining_plan':indexed[chosen][0]}, {'stages':[first,raw]}


def execute(client, snapshot, memory, action, selected):
    if action not in ACTIONS:
        return {'applied':False,'reason':'unsupported_action'}
    key = selected.get('mining_plan')
    allowed = plans(snapshot,action)
    known = {k:p for k,p in snapshot.get('development', {}).get('mining', {}).get('prepared_options',allowed).items() if k in allowed}
    history = memory.setdefault('mining_history', {})
    def remember(keys, seconds=30):
        for k in keys:
            history[k] = {**failure_record(int(snapshot.get('game', {}).get('tick') or 0),seconds), 'map_id':snapshot['map']['id']}
    if key == 'defer':
        remember([k for k in selected.get('shown_mining_options') or [] if k in known],120)
        return {'applied':False,'reason':'laya_deferred_mining'}
    original = known.get(key)
    if original is None:
        return {'applied':False,'reason':'unverified_mining_plan'}
    try:
        fresh = collect(client, snapshot)
        current = next((p for p in fresh['options'] if p.get('key')==key), None)
        if current is None or any(current.get(f)!=original.get(f) for f in ('worker_id','thing_ids','product_def','cells','kind')):
            remember([key]); return {'applied':False,'reason':'mining_plan_changed'}
        result = client.post('/api/v1/mining/order', body={'map_id':snapshot['map']['id'],'key':key})
    except Exception as exc:
        remember([key]);return {'applied':False,'reason':'mining_transport_failed','error':str(exc)[:240]}
    if not isinstance(result,dict) or result.get('applied') is not True:
        remember([key]);return {'applied':False,'reason':result.get('reason','mining_not_started') if isinstance(result,dict) else 'invalid_response'}
    remember([key],120)
    if current.get('kind')!='haul': labor.remember(snapshot,current['worker_id'],'Mining',current['thing_ids'])
    stock = next((p.get('count') for p in fresh.get('product_stocks') or [] if p.get('product_def')==current['product_def']),0)
    memory['mining_intent' if current.get('kind')!='haul' else 'mineral_haul_intent'] = {'tick':snapshot.get('game', {}).get('tick'), 'map_id':snapshot['map']['id'],
        'worker_id':current['worker_id'],'thing_ids':current['thing_ids'],'product_def':current['product_def'],'product_stock':stock}
    completion = ('haul_job_observed; arrival_storage_sale_unverified' if current.get('kind') == 'haul'
                  else 'mining_job_observed; product_haul_sale_unverified')
    return {'applied':True,'reason':result.get('reason'),'response':result,'completion':completion}


def assess(action, snapshot):
    if action == 'mining_haul':
        return {'benefit':DESCRIPTIONS[action], 'cost':'Concrete hauler time and travel',
                'risk':'Food/care displacement and exposure; no buyer guaranteed',
                'inaction':'Observed goods remain; other work continues',
                'uncertainty':'An ordinary haul job is not arrival, source attribution or income'}
    return {'benefit':DESCRIPTIONS[action], 'cost':'Concrete miner time, travel and remaining ore HP',
            'risk':'Food/care displacement and exposure; no buyer guaranteed', 'inaction':'Ore remains; other work continues',
            'uncertainty':'Only a native ordinary Mine job is accepted; output, hauling and income are separate observations'}


def summary(snapshot):
    rows = plans(snapshot)
    return {'mining_opportunities':len(rows)}
