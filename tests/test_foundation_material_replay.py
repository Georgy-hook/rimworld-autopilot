import copy
import unittest
import colony_architect as a

BENCH={'def_name':'SimpleResearchBench','label':'Bench','available_now':True,'cost_stuff_count':75,
       'cost_list':[{'thing_def':'Steel','count':25}], 'stuff_categories':['Metallic'],
       'allowed_stuff_defs':['Steel','Silver'],'size_x':3,'size_z':2,
       'effective_costs_by_stuff':{'Steel':[{'thing_def':'Steel','count':100}],
         'Silver':[{'thing_def':'Silver','count':750},{'thing_def':'Steel','count':25}]}}
PROJECT={'thing_id':69051,'def_name':'SimpleResearchBench','kind':'frame','stuff_def_name':'Silver',
         'position':{'x':126,'y':0,'z':89},'rotation':2,'materials_needed':[
          {'def_name':'Steel','required_count':15},{'def_name':'Silver','required_count':750}]}

def development():
    return {'item_counts':{'Silver':491,'Steel':921},'building_catalog':[copy.deepcopy(BENCH)],
            'construction_projects':[copy.deepcopy(PROJECT)]}

class Client:
    def __init__(self, reject=False): self.dev=development();self.posts=[];self.reject=reject
    def get(self,path,**kwargs):
        if path.endswith('/projects'):return {'projects':copy.deepcopy(self.dev['construction_projects'])}
        if path.endswith('/catalog'):return self.dev['building_catalog']
        if path.endswith('/things'):return [{'def_name':n,'stack_count':v} for n,v in self.dev['item_counts'].items()]
        raise AssertionError(path)
    def post(self,path,**kwargs):
        self.posts.append((path,kwargs)); body=kwargs['body']
        if self.reject:return {'success':False}
        self.dev['construction_projects']=[{**copy.deepcopy(PROJECT),'thing_id':69099,'stuff_def_name':body['replacement_stuff_def_name']}]
        return {'success':True,'replacement_project_id':69099}

class FoundationMaterialReplayTests(unittest.TestCase):
    def test_native_silver_cost_is_tenfold_not_seventy_five(self):
        self.assertEqual({'Silver':750,'Steel':25},a.effective_building_cost(BENCH,'Silver'))
        plans=a.catalog_construction_options({**development(),'construction_projects':[]})
        materials=next(iter(plans.values()))['SimpleResearchBench']['materials']
        self.assertNotIn('Silver',materials); self.assertIn('Steel',materials)
        layout={'buildings':[{'def_name':'SimpleResearchBench','stuff_def_name':'Silver'}]}
        self.assertEqual({'Silver':750,'Steel':25},a.estimated_stuff_cost(layout,[BENCH]))

    def test_pending_remaining_reserves_deduplicate_without_double_counting_frame_held(self):
        dev=development();dev['construction_projects'].append(copy.deepcopy(PROJECT))
        self.assertEqual({'Silver':0,'Steel':906},a.unreserved_construction_stock(dev))
        dev['item_counts']['Steel']=110
        dev['construction_projects'].append({'thing_id':22,'materials_needed':[{'def_name':'Steel','required_count':20}]})
        self.assertEqual({},a.catalog_construction_options(dev))

    def test_eight_prepare_execute_cycles_only_replaces_exact_unfinished_target_once(self):
        client=Client()
        for cycle in range(8):
            options=a.research_bench_repair_options(client.dev)
            if cycle==0:
                self.assertEqual(['69051|Steel'],list(options))
                result=a.execute_research_bench_repair(client,{'map':{'id':1}},'69051|Steel',None)
                self.assertTrue(result['applied']);self.assertEqual(69099,result['replacement_project_id'])
            else:
                self.assertFalse(a.execute_research_bench_repair(client,{'map':{'id':1}},'69051|Steel',None)['applied'])
        self.assertEqual(1,len(client.posts))
        self.assertEqual({'map_id':1,'project_thing_id':69051,'expected_def_name':'SimpleResearchBench','replacement_stuff_def_name':'Steel'},client.posts[0][1]['body'])

    def test_rejected_cancel_readback_retains_original_no_claimed_replacement(self):
        client=Client(reject=True)
        result=a.execute_research_bench_repair(client,{'map':{'id':1}},'69051|Steel',None)
        self.assertFalse(result['applied']);self.assertEqual('research_bench_cancel_unobserved',result['reason'])
        client.dev['construction_projects']=[]
        self.assertFalse(a.execute_research_bench_repair(client,{'map':{'id':1}},'69051|Steel',None)['applied'])
        self.assertEqual(1,len(client.posts))

    def test_fresh_material_loss_prevents_cancel(self):
        client=Client();client.dev['item_counts']['Steel']=40
        self.assertFalse(a.execute_research_bench_repair(client,{'map':{'id':1}},'69051|Steel',None)['applied'])
        self.assertFalse(client.posts)
