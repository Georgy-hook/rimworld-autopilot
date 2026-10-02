import unittest
from unittest.mock import patch
import colony_director as d

class Client:
    def __init__(self, projects): self.projects=projects;self.posts=[]
    def get(self,path,**kwargs):
        if path.endswith('/catalog'): return [{'def_name':n,'available_now':True,'cost_list':[]} for n in ('Wall','Door')]
        return {'projects':self.projects} if path.endswith('/projects') else [] if path.endswith('/buildings') else {}
    def post(self,path,**kwargs):self.posts.append((path,kwargs));return {'all_placeable':True} if path.endswith('/preview') else {'success':True,'warnings':['Partial native placement']}

class ArchitectureObservationTests(unittest.TestCase):
    def execute(self, projects):
        state={'anchor':{'x':10,'z':10},'issued':{}}
        layout={'buildings':[{'def_name':'Wall','rel_x':0,'rel_z':0},{'def_name':'Door','rel_x':1,'rel_z':0}],'floors':[]}
        variant={'layout':layout,'width':2,'height':1}
        client=Client(projects)
        with patch.object(d.architect,'generate_program_variants',return_value={'v':variant}), \
             patch.object(d.architect,'affordable_variants',side_effect=lambda v,c:v), \
             patch.object(d,'find_terrain_rect',return_value={'x':40,'z':20}), \
             patch.object(d,'prioritize',return_value={'applied':True}):
            result=d.execute_action(client,{'map':{'id':1},'game':{'tick':500},'development':{}},state,'plan_architecture',
                {'architecture_program':'residence','architecture_variant':'v','architecture_material':'WoodLog',
                 'architecture_context':{'material_options':{'WoodLog':'wood'}}})
        return result,state
    def test_acceptance_envelope_without_actual_projects_is_not_success(self):
        result,state=self.execute([])
        self.assertFalse(result['applied']);self.assertNotIn('architecture_projects',state)
        self.assertNotIn('architecture_project',state['issued'])
    def test_wrong_coordinate_does_not_verify_native_placement(self):
        result,state=self.execute([{'def_name':'Wall','position':{'x':41,'z':20}}])
        self.assertFalse(result['applied']);self.assertEqual(result['verified_count'],0)
    def test_partial_reserves_actual_site_without_claiming_complete_plan(self):
        result,state=self.execute([{'def_name':'Wall','position':{'x':40,'z':20}}])
        self.assertFalse(result['applied']);self.assertEqual(result['reason'],'partial_architecture_plan_observed')
        self.assertEqual(state['architecture_projects'][0]['verified_count'],1)
        self.assertNotIn('architecture_project',state['issued'])
    def test_full_exact_projects_can_record_architecture(self):
        result,state=self.execute([{'def_name':'Wall','position':{'x':40,'z':20}},{'def_name':'Door','position':{'x':41,'z':20}}])
        self.assertTrue(result['applied']);self.assertEqual(state['issued']['architecture_project'],500)

if __name__=='__main__':unittest.main()
