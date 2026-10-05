"""Forest site searches retain native obstacles and protected vegetation."""
import unittest
import colony_director as d

class Client:
    def __init__(self, terrain): self.terrain = terrain
    def get(self, endpoint, **query): return self.terrain

class ForestLayoutTests(unittest.TestCase):
    def setUp(self):
        self.terrain = {'width':30,'height':30,'palette':['Soil'],'grid':[900,0]}
        self.dev = {'plants':[{'def_name':'Plant_TreePine','harvested_thing_def':'WoodLog',
            'position':{'x':x,'z':z}} for x in range(30) for z in range(30)]}
    def sites(self, terrain=None, dev=None, memory=None):
        terrain = self.terrain if terrain is None else terrain
        dev = self.dev if dev is None else dev
        memory = {} if memory is None else memory
        return [d.find_dry_starter_site(terrain,{'x':10,'z':10},dev,memory),
            d.find_clear_layout_site(Client(terrain),1,{'x':10,'z':10},{'width':7,'height':7},dev,memory),
            d.choose_prison_site(terrain,{'x':22,'z':18},dev,memory)]
    def test_dense_ordinary_forest_all_three_paths_find_site(self):
        self.assertTrue(all(site is not None for site in self.sites()))
    def test_clearing_preferred_to_nearer_timber(self):
        self.dev['plants'] = [p for p in self.dev['plants'] if not (16<=p['position']['x']<=26 and 16<=p['position']['z']<=26)]
        site = d.find_clear_layout_site(Client(self.terrain),1,{'x':10,'z':10},{'width':7,'height':7},self.dev,{})
        self.assertEqual({'x':18,'z':18},site)
    def test_protected_unknown_cultivated_forbidden_trees_block_all_paths(self):
        for extra in [{'def_name':'Plant_TreeAnima'},{'def_name':'Plant_TreeGauranlen'},
                {'def_name':'Plant_TreePolux'},{'is_cultivated':True},{'is_forbidden':True},
                {'harvested_thing_def':None}]:
            with self.subTest(extra=extra):
                dev={'plants':[{**p,**extra} for p in self.dev['plants']]}
                self.assertEqual([None,None,None],self.sites(dev=dev))
    def test_native_edifices_remain_blocked_even_with_timber(self):
        self.assertEqual([None,None,None],self.sites(terrain={**self.terrain,'edifice_grid':[900,1]}))
    def test_projects_and_architecture_reservations_remain_blocked(self):
        for memory,dev in [({'architecture_projects':[{'origin':{'x':0,'z':0},'width':30,'height':30}]},self.dev),
                ({},{**self.dev,'construction_projects':[{'position':{'x':0,'z':0},'size':{'x':30,'z':30}}]})]:
            self.assertEqual([None,None,None],self.sites(dev=dev,memory=memory))
    def test_single_rock_avoided_with_existing_clearance(self):
        terrain={**self.terrain,'edifice_grid':[310,0,1,1,589,0]}
        for index,site in enumerate(self.sites(terrain=terrain)):
            self.assertIsNotNone(site)
            clearance=1 if index==2 else 2
            self.assertFalse(site['x']-clearance<=10<site['x']+7+clearance
                and site['z']-clearance<=10<site['z']+7+clearance)
    def test_invalid_edifice_grid_cannot_prove_site_clear(self):
        with self.assertRaises(ValueError): self.sites(terrain={**self.terrain,'edifice_grid':[899,0]})
    def test_prison_existing_site_preserved(self):
        memory={'prison_site':{'x':14,'z':13}}
        expected=d.prison_site_for_state(memory,{'x':22,'z':18})
        self.assertEqual(expected,d.choose_prison_site({**self.terrain,'edifice_grid':[900,1]},
            {'x':22,'z':18},self.dev,memory))

if __name__=='__main__': unittest.main()
