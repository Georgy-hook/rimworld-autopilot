"""Offline stock/decision/payload checks; fake agents do not establish Laya competence."""
import copy
from pathlib import Path
import tempfile
import unittest
import colony_director as director

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / 'vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers'


class Agent:
    def __init__(self, choices):
        self.choices = choices
        self.seen = []
    def predict(self, state, questions):
        qid, question = next(iter(questions.items()))
        self.seen.append((qid, copy.deepcopy(question)))
        choice = self.choices.get(qid.split('_round_')[0], 'none')
        if choice not in question['criteria']:
            choice = next(iter(question['criteria']))
        return {'answers': {qid: {'choice': choice}}}


class Client:
    def __init__(self, session):
        self.session = session
        self.posts = []
        self.gets = []
    def get(self, endpoint, **query):
        self.gets.append((endpoint, query))
        return copy.deepcopy(self.session)
    def post(self, endpoint, **kwargs):
        self.posts.append((endpoint, kwargs))
        return {'executed': not kwargs['body'].get('close_without_trade'), 'bought_units': 1, 'trader_name': 'Town'}


def snapshot():
    return {'map': {'id': 1, 'seed': 'qa', 'tile_id': 2, 'resources': {'food': 50}},
            'game': {'tick': 1000}, 'colonists': [{'id': 1}], 'development': {}}


def session(cash=7000):
    return {'active': True, 'settlement_id': 52, 'settlement_name': 'Town', 'colony_silver': cash,
            'trader_silver': 3000, 'sale_options': [], 'humanlike_offers': [], 'purchase_options': [
                {'thing_id': 99, 'category': 'item:AIPersonaCore', 'example': 'AI persona core',
                 'maximum_units': 1, 'unit_price': 6000, 'description': 'Ship computer material'}]}


class ProcurementContracts(unittest.TestCase):
    def test_expensive_native_item_survives_preview_and_budget(self):
        preview = {'colony_silver': 7000, 'purchase_options': session()['purchase_options']}
        self.assertIn('item:AIPersonaCore', director.verified_trade_options(preview, 'purchase'))
        budgets = director.trade_spending_options(6000, 7000, 300)
        self.assertEqual(set(budgets), {'6000', '6700'})
        self.assertFalse(director.trade_spending_options(6000, 6200, 300))
        client = Client(preview)
        traders = director.preview_live_traders(client, {'trade_opportunities': [{'id': 'ship:1'}]}, 1, 300)
        self.assertEqual(len(traders), 1)
        self.assertGreater(client.gets[0][1]['maximum_spend'], 6000)

    def test_local_core_selected_payload_uses_native_exact_goods_priority(self):
        preview = {'purchase_options': session()['purchase_options']}
        client = Client(preview)
        result = director._execute_event_response(client, snapshot(), {}, {}, {'trade_opportunities': [{'id': 'ship:1', 'preview': preview}]}, 'trade_now', {
            'trader_id': 'ship:1', 'sale_category': 'none', 'purchase_priority': 'item:AIPersonaCore',
            'trade_budget': 6000, 'minimum_silver_reserve': 300, 'trade_preview': preview})
        self.assertTrue(result['applied'])
        body = client.posts[0][1]['body']
        self.assertEqual(body['purchase_priorities'], ['item:AIPersonaCore'])
        self.assertEqual(body['maximum_spend'], 6000)
        self.assertEqual(body['minimum_silver_reserve'], 300)

    def test_settlement_core_requires_explicit_item_and_budget_choices(self):
        client = Client(session())
        agent = Agent({'caravan_cash_reserve': '300', 'caravan_item': '99', 'caravan_budget': '6000'})
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_caravan_trade_cycle(client, agent, snapshot(), {}, Path(folder) / 'trade.jsonl')
        body = client.posts[0][1]['body']
        self.assertEqual(body['purchase_thing_id'], 99)
        self.assertIsNone(body['purchase_pawn_id'])
        self.assertEqual(body['maximum_spend'], 6000)
        self.assertEqual(body['expected_unit_price'], 6000)
        self.assertEqual(record['decision']['item'], '99')
        self.assertEqual([qid for qid, _ in agent.seen], ['caravan_cash_reserve', 'caravan_item', 'caravan_budget'])

    def test_reserve_excludes_unaffordable_core_and_mapless_caravan_preserves_doctrine(self):
        client = Client(session(6200))
        snap = snapshot(); snap['map'].pop('id')
        state = {'native_session': {'doctrine': {'endgame': 'ship_escape'}}}
        agent = Agent({'caravan_cash_reserve': '300'})
        with tempfile.TemporaryDirectory() as folder:
            record = director.run_caravan_trade_cycle(client, agent, snap, state, Path(folder) / 'trade.jsonl')
        self.assertTrue(client.posts[0][1]['body']['close_without_trade'])
        self.assertIsNone(client.posts[0][1]['body']['purchase_thing_id'])
        self.assertEqual(record['session']['course']['endgame'], 'ship_escape')
        self.assertNotIn('caravan_budget', [qid for qid, _ in agent.seen])

    def test_native_source_uses_stock_and_normal_transfer_and_restores_preview_scope(self):
        local = (HELPERS / 'LiveTradeAutomationHelper.cs').read_text(encoding='utf-8')
        self.assertIn('"item:" + t.ThingDef.defName', local)
        self.assertIn('row.ThingDef.defName == priority.Substring(5)', local)
        self.assertIn('!row.IsCurrency && row.ThingDef.race == null', local)
        self.assertIn('pendingItems.Count > 0', local)
        preview = local[:local.index('public static ApiResult<LiveTradeResponseDto> Execute')]
        for field, previous in [('trader', 'previousTrader'), ('playerNegotiator', 'previousNegotiator'), ('deal', 'previousDeal'), ('giftMode', 'previousGiftMode')]:
            self.assertIn('TradeSession.' + field + '=' + previous, preview)
        caravan = (HELPERS / 'CaravanTradeSessionHelper.cs').read_text(encoding='utf-8')
        self.assertIn('request.PurchaseThingId.Value', caravan)
        self.assertIn('request.ExpectedUnitPrice.Value-price', caravan)
        self.assertIn('Existing manual trade selections', caravan)
        self.assertIn('selected.ForceToSource(1)', caravan)
        self.assertIn('deal.TryExecute(out bool actuallyTraded)', caravan)

    def test_caravan_financing_uses_executable_sale_value(self):
        value = session(4000)
        value['sale_options'] = [{'category': 'art', 'example': 'Sculpture', 'maximum_units': 10,
                                  'unit_price': 1000, 'planned_sale_value': 1000}]
        client = Client(value)
        agent = Agent({'caravan_sale': 'art', 'caravan_cash_reserve': '0', 'caravan_item': '99'})
        with tempfile.TemporaryDirectory() as folder:
            director.run_caravan_trade_cycle(client, agent, snapshot(), {}, Path(folder) / 'trade.jsonl')
        self.assertIsNone(client.posts[0][1]['body']['purchase_thing_id'])
        self.assertNotIn('caravan_item', [qid for qid, _ in agent.seen])


if __name__ == '__main__':
    unittest.main()
