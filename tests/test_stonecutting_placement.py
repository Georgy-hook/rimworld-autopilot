import unittest
import colony_director as director


def snapshot():
    return {'game':{'tick':12000},'map':{'id':0},'colonists':[],
            'development':{'finished_research':['Stonecutting'],'work_tables':[],
                           'buildings':[],'construction_projects':[]}}


class Client:
    def __init__(self,free=True,registered=False):self.free=free;self.registered=registered;self.posts=[]
    def get(self,path,**kw):
        if path=='/api/v1/map/terrain':
            return {'width':50,'height':50,'palette':['Soil'],'grid':[2500,0],
                    'dry_foundation_grid':[2500,1],'mountain_roof_grid':[2500,0],
                    'stockpile_available_grid':[2500,int(self.free)]}
        if path=='/api/v1/builder/projects':
            rows=[]
            if self.posts and self.registered:
                p=self.posts[-1]['position'];rows=[{'def_name':'TableStonecutter','position':p}]
            return {'projects':rows}
        if path=='/api/v1/map/buildings':return []
        raise AssertionError(path)
    def post(self,path,**kw):self.posts.append(kw['body']);return {'success':True}


class StonePlacementTests(unittest.TestCase):
    def test_existing_frame_does_not_place_a_second_table(self):
        s=snapshot();s['development']['construction_projects']=[{'def_name':'TableStonecutter','kind':'frame'}]
        c=Client();m={'anchor':{'x':10,'z':10}}
        r=director.execute_action(c,s,m,'start_stonecutting',{'stone_type':'Slate'})
        self.assertEqual(r['reason'],'existing_stonecutting_table_in_progress');self.assertEqual(c.posts,[])

    def test_no_verified_free_footprint_has_no_blind_coordinate_fallback(self):
        c=Client(free=False);m={'anchor':{'x':10,'z':10}}
        r=director.execute_action(c,snapshot(),m,'start_stonecutting',{'stone_type':'Slate'})
        self.assertFalse(r['applied']);self.assertEqual(c.posts,[])
        self.assertNotIn('stonecutting_table',m['issued'])

    def test_success_ack_without_registered_blueprint_is_not_issued(self):
        c=Client();m={'anchor':{'x':10,'z':10}}
        r=director.execute_action(c,snapshot(),m,'start_stonecutting',{'stone_type':'Slate'})
        self.assertFalse(r['applied']);self.assertEqual(len(c.posts),1)
        self.assertNotIn('stonecutting_table',m['issued'])

    def test_overlapped_old_anchor_uses_another_verified_plot(self):
        s=snapshot();s['development']['buildings']=[{'def':'TableSculpting','position':{'x':26,'z':30},
            'occupied_cells':[{'x':26,'z':30},{'x':27,'z':30}]}]
        c=Client(registered=True);m={'anchor':{'x':10,'z':10}}
        r=director.execute_action(c,s,m,'start_stonecutting',{'stone_type':'Slate'})
        self.assertTrue(r['applied']);self.assertEqual(m['issued']['stonecutting_table'],12000)
        self.assertNotEqual((r['origin']['x'],r['origin']['z']),(26,30))
        self.assertIn('building_and_blocks_unverified',r['completion'])
