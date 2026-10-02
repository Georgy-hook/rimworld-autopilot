import unittest
import colony_architect as a

def context():
    names={'Wall':(1,1),'Door':(1,1),'RoyalBed':(3,3),'DoubleBed':(2,2),
           'EndTable':(1,1),'Dresser':(2,1),'TileFineMarble':(1,1),
           'GrandThrone':(3,2),'Throne':(1,1),'Brazier':(1,1),'Column':(1,1)}
    catalog=[{'def_name':n,'size_x':w,'size_z':h,'available_now':True} for n,(w,h) in names.items()]
    person={'pawn_id':7,'pawn_name':'Royal guest','quest_lodger':True,'requires_bedroom':True,
            'has_unmet_bedroom_requirements':True,'minimum_bedroom_area':80,'minimum_bedroom_impressiveness':160,
            'bedroom_required_bed_defs':['RoyalBed'], 'bedroom_floor_tags':['FineFloor'],
            'bedroom_compatible_floor_defs':['TileFineMarble'],
            'bedroom_required_things':[{'any_of':['RoyalBed'],'count':1},{'any_of':['Dresser'],'count':1},{'any_of':['EndTable'],'count':1}],
            'requires_throne_room':True,'has_unmet_throne_room_requirements':True,'minimum_throne_room_area':80,
            'minimum_throne_room_impressiveness':160,'throne_required_defs':['GrandThrone'],
            'throne_room_compatible_floor_defs':['TileFineMarble'],'throne_room_floor_tags':['FineFloor'],
            'throne_room_required_things':[{'any_of':['GrandThrone'],'count':1},{'any_of':['Brazier'],'count':2},{'any_of':['Column'],'count':2}]}
    return {'building_catalog':catalog,'material':'WoodLog','item_counts':{'WoodLog':10000},
            'colonists':[{'id':1}], 'rooms':[{'role_label':'bedroom'}], 'royalty':{'colonists':[person]}}

def occupied(part,index):
    row=index[part['def_name']];w,h=row['size_x'],row['size_z']
    x=part['rel_x']-(w-1)//2;z=part['rel_z']-(h-1)//2
    return {(i,j) for i in range(x,x+w) for j in range(z,z+h)}

class RoyalArchitectureTests(unittest.TestCase):
    def test_royal_bedroom_is_offered_despite_no_ordinary_housing_shortage(self):
        c=context();options=a.program_options(c)
        self.assertNotIn('residence',options);self.assertIn('royal_bedroom',options)
    def test_pending_quest_guests_are_planned_before_acceptance(self):
        c=context();person=c['royalty']['colonists'].pop()
        c['royalty']['pending_bedroom_quests']=[{'guests':[person]}]
        self.assertIn('royal_bedroom',a.program_options(c))
        self.assertTrue(a.generate_program_variants('royal_bedroom',c))
    def test_actual_native_floor_bed_area_and_furniture_are_in_every_variant(self):
        c=context();variants=a.generate_program_variants('royal_bedroom',c)
        self.assertTrue(variants)
        index=a.catalog_index(c['building_catalog'])
        for v in variants.values():
            self.assertGreaterEqual(v['structural_area'],80)
            self.assertEqual(v['target_pawn_id'],7)
            names=[p['def_name'] for p in v['layout']['buildings']]
            for n in ('RoyalBed','EndTable','Dresser'):self.assertIn(n,names)
            self.assertTrue(all(f['def_name']=='TileFineMarble' for f in v['layout']['floors']))
            self.assertEqual(len(v['layout']['floors']),v['structural_area'])
            self.assertIn('unverified',v['summary']);self.assertTrue(v['pending_requirements'])
            seen=set()
            for part in v['layout']['buildings']:
                cells=occupied(part,index);self.assertFalse(cells & seen);seen|=cells
                self.assertTrue(all(0<=x<v['width'] and 0<=z<v['height'] for x,z in cells))
    def test_locked_required_bed_or_floor_never_produces_misleading_plan(self):
        for name in ('RoyalBed','TileFineMarble'):
            c=context();next(r for r in c['building_catalog'] if r['def_name']==name)['available_now']=False
            self.assertEqual(a.generate_program_variants('royal_bedroom',c),{})
            self.assertIn('royal_bedroom',a.program_options(c)) # actual need remains observable
            self.assertIn('Unlock/load',a.program_options(c)['royal_bedroom'])
    def test_throne_comes_from_requirement_not_title_name(self):
        c=context();c['royalty']['colonists'][0]['title_def_name']='ModTitle_UnknownName'
        variants=a.generate_program_variants('throne_room',c);self.assertTrue(variants)
        for v in variants.values():
            names=[p['def_name'] for p in v['layout']['buildings']]
            self.assertIn('GrandThrone',names);self.assertNotIn('RoyalBed',names)
            self.assertEqual(names.count('Brazier'),2);self.assertEqual(names.count('Column'),2)
            self.assertTrue(any('glowing' in r for r in v['pending_requirements']))
    def test_research_frontier_uses_locked_native_groups_and_skips_available_alternative(self):
        c=context()
        next(r for r in c['building_catalog'] if r['def_name']=='RoyalBed').update(available_now=False,research_prerequisites=['ModRoyalFurniture'])
        next(r for r in c['building_catalog'] if r['def_name']=='TileFineMarble').update(available_now=False,research_prerequisites=['FineStonecutting'])
        self.assertEqual(a.royal_research_targets(c),['FineStonecutting','ModRoyalFurniture'])
        person=c['royalty']['colonists'][0]
        person['bedroom_required_bed_defs'].append('DoubleBed')
        person['bedroom_required_things'][0]['any_of'].append('DoubleBed')
        self.assertEqual(a.royal_research_targets(c),['FineStonecutting'])
        c['finished_research']=['FineStonecutting']
        self.assertEqual(a.royal_research_targets(c),[])
    def test_pending_guests_keep_goal_and_research_need_without_variants(self):
        c=context();person=c['royalty']['colonists'].pop();c['royalty']['pending_bedroom_quests']=[{'guests':[person]}]
        next(r for r in c['building_catalog'] if r['def_name']=='RoyalBed').update(available_now=False,research_prerequisites=['RoyalFurniture'])
        self.assertEqual(a.generate_program_variants('royal_bedroom',c),{})
        needs=a.royal_goal_needs(c)
        self.assertIn('RoyalFurniture',needs['research_alternatives'])
        self.assertTrue(any(row['room']=='bedroom' and row['pawn']==7 for row in needs['rooms']))

if __name__=='__main__':unittest.main()
