"""Finite manufacturing intentions, grounded in the loaded public recipe catalog.

Planning is separate from executable bills. It neither unlocks a recipe nor
assigns a worker, and stock growth alone cannot prove manufactured output.
"""
from __future__ import annotations

import colony_decision_context as facts
import colony_quests as review
from colony_retry import failure_record, recent


def catalog(snapshot):
    rows = ((snapshot.get('development', {}).get('production') or {}).get('recipe_context') or {}).get('planning_catalog')
    return {r['recipe']: r for r in rows or [] if isinstance(r, dict) and r.get('recipe')
            and r.get('products') and r.get('table_defs')}


def requirements(row, product):
    """Carry this one batch's actual costs; don't sum alternative worktables."""
    result = {k: row.get(k) for k in ('recipe', 'fixed_ingredients', 'variable_ingredients',
        'missing_research', 'skill_requirements', 'table_defs', 'completed_table_ids')}
    result['product_def'] = product
    # Tables are alternatives, not a request to build every one of them.
    result['table_alternatives'] = row.get('tables') or []
    return result


def prepare(snapshot, memory):
    dev = snapshot.setdefault('development', {})
    rows = catalog(snapshot)
    goal = memory.get('manufacturing_goal') or {}
    if goal.get('recipe') in rows:
        row = rows[goal['recipe']]
        dev['manufacturing_goal'] = requirements(row, goal['product_def'])
        product = next((p for p in row['products'] if p['def_name'] == goal['product_def']), {})
        current, target = facts.number(product.get('stock')), facts.number(goal.get('target_stock'))
        if current is not None and target is not None and current >= target:
            dev['manufacturing_goal']['stock_target_met'] = True
            dev['manufacturing_goal']['outcome'] = 'Observed stock target; source not attributed to manufacturing'
            # Keep the receipt, but stop treating its ingredients as outstanding.
            dev['manufacturing_goal']['fixed_ingredients'] = []
        else:
            import colony_progression
            targets = list(row.get('missing_research') or [])
            # Only require a table path when no completed alternative exists.
            if not row.get('completed_table_ids'):
                # Alternative paths stay distinct in the goal. Expose their
                # feasible research frontier; the model still chooses a path.
                targets += [r for t in row.get('tables') or [] for r in t.get('missing_research') or []]
            progression = dev.setdefault('progression', {})
            progression['manufacturing_product'] = {'product': goal['product_def'], 'recipe': row['recipe']}
            progression['manufacturing_support'] = colony_progression.research_frontier(
                progression.get('research_tree') or dev.get('research_tree'), targets)
    else:
        dev.pop('manufacturing_goal', None)
    tick = int((snapshot.get('game') or {}).get('tick') or 0)
    return bool(rows) and not recent(memory.get('manufacturing_review'), tick, 30000)


def choose(agent, snapshot, state=None):
    rows = catalog(snapshot)
    if not rows:
        return {'production_policy': 'defer'}, {'reason': 'planning_catalog_unavailable'}
    people = snapshot.get('colonists') or []
    header = {'colony': review.colony_facts(snapshot),
              'supplies': facts.quest_impact(snapshot),
              'goal_is_not_a_bill': True}
    if (state or {}).get('endgame'):
        header['ending'] = state['endgame']
    if (state or {}).get('goal_requirements'):
        header['other_goals'] = state['goal_requirements']
    fighters = [{k:p.get(k) for k in ('id','weapon_def','shooting_skill','melee_skill','is_downed')}
                for p in (snapshot.get('combat') or {}).get('colonists') or [] if not p.get('is_dead')]
    workers = [{'id': p.get('id'), 'downed': p.get('downed'), 'mental': p.get('in_mental_state'),
                'job': p.get('current_job'),
                'skills': {k:v for k,v in (p.get('skills') or {}).items() if k in ('Construction','Crafting')},
                'work': {k:v for k,v in (p.get('work_priorities') or {}).items() if k in ('Construction','Crafting','Smithing')}}
               for p in people if not p.get('dead')]
    products = {}
    for row in rows.values():
        for product in row['products']:
            products.setdefault(product['def_name'], []).append(row)
    categories = {}
    for name, recipes in products.items():
        category = 'components' if name in {'ComponentIndustrial', 'ComponentSpacer'} else 'weapons'
        categories.setdefault(category, {})[name] = {
            'stock': next(p.get('stock') for p in recipes[0]['products'] if p['def_name'] == name),
            'recipes': len(recipes)}
    categories['defer'] = {'response': 'Keep current goods and survival duties; no new production goal'}
    if 'weapons' in categories:
        categories['weapons'] = {'ground_stock': categories['weapons'], 'equipped_weapons': fighters}
    instructions = 'Choose a finite manufacturing intention or defer. Existing stock may already suffice. Research, table, builder, power and skill can block production. A goal creates no product.'
    category, first = review.select_exact(agent, header, 'manufacturing_purpose', categories, instructions,
        question_id='manufacturing_purpose')
    if category == 'defer':
        return {'production_policy': 'defer'}, {'purpose': first}
    group = categories[category].get('ground_stock', categories[category])
    options = {name: {'product': name, 'stock': info['stock'], 'equipped_weapons': fighters,
                     'paths': [{k:r.get(k) for k in ('recipe','cost','missing_research','skill_requirements','table_defs')}
                               for r in products[name]]} for name, info in group.items()}
    options['defer'] = {'response': 'Keep existing equipment/materials and current work'}
    product, second = review.select_exact(agent, header, 'manufacturing_product', options, instructions,
        question_id='manufacturing_product')
    if product == 'defer':
        return {'production_policy': 'defer'}, {'purpose': first, 'product': second}
    paths = {r['recipe']: {**r, 'workers_observed_not_committed': workers,
                           'equipped_weapons': fighters}
             for r in products[product]}
    paths['defer'] = {'response': 'Do not commit to this manufacturing path'}
    recipe, third = review.select_exact(agent, header, 'manufacturing_requirements', paths, instructions,
        question_id='manufacturing_recipe')
    return {'production_policy': recipe, 'product_def': product}, {'purpose': first, 'product': second, 'recipe': third}


def execute(client, snapshot, memory, selected):
    tick = int((snapshot.get('game') or {}).get('tick') or 0)
    if selected.get('production_policy') == 'defer':
        memory['manufacturing_review'] = failure_record(tick, 120)
        return {'applied': False, 'reason': 'laya_deferred_manufacturing_plan'}
    original = catalog(snapshot).get(selected.get('production_policy'))
    if not original or selected.get('product_def') not in {p['def_name'] for p in original['products']}:
        return {'applied': False, 'reason': 'unverified_manufacturing_goal'}
    # Planning writes memory only, but bind it to a fresh loaded native recipe.
    current = client.get('/api/v1/production/recipes', map_id=snapshot['map']['id'])
    if not isinstance(current, dict) or current.get('available') is not True or not isinstance(current.get('planning_catalog'), list):
        return {'applied': False, 'reason': 'manufacturing_catalog_unavailable'}
    live = next((r for r in current['planning_catalog'] if r.get('recipe') == original['recipe']), None)
    if not live or requirements(live, selected['product_def']) != requirements(original, selected['product_def']):
        return {'applied': False, 'reason': 'manufacturing_requirements_changed', 'reconsider': True}
    product = next((p for p in live['products'] if p['def_name'] == selected['product_def']), {})
    stock, count = facts.number(product.get('stock')), facts.number(product.get('count'))
    if stock is None or count is None or count <= 0:
        return {'applied': False, 'reason': 'manufacturing_output_unknown'}
    memory['manufacturing_goal'] = {'recipe': live['recipe'], 'product_def': selected['product_def'],
        'target_stock': stock + count, 'planned_tick': tick}
    memory['manufacturing_review'] = failure_record(tick, 120)
    return {'applied': True, 'plan_only': True, 'recipe': live['recipe'], 'product': selected['product_def'],
            'reason': 'finite_manufacturing_intention_recorded', 'completion_verified': False}
