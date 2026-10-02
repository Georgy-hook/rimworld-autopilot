"""Offline geometry contract from installed Core ship defs and native ShipUtility.

Sizes: Core/Defs/ThingDefs_Buildings/Buildings_Ship.xml (2026-10-02).
Attachment: ShipUtility.ShipBuildingsAttachedTo uses cardinal occupied edges.
Casket head: PlaceWorker_HeadOnShipBeam checks loc - north; entry offset east.
"""
import unittest
from collections import Counter
from colony_director import ship_blueprint

SIZES={'Ship_Beam':(2,6),'Ship_Reactor':(6,7),'Ship_ComputerCore':(2,2),
       'Ship_SensorCluster':(2,2),'Ship_Engine':(3,4),'Ship_CryptosleepCasket':(1,2)}

def cells(part):
    assert part['rotation']==0
    w,h=SIZES[part['def_name']]
    x=part['rel_x']-(w-1)//2;z=part['rel_z']-(h-1)//2
    return {(a,b) for a in range(x,x+w) for b in range(z,z+h)}

class ShipLayoutTests(unittest.TestCase):
    def test_whole_ship_is_one_nonoverlapping_cardinal_component(self):
        for count in (1,3,9,20):
            layout=ship_blueprint(count);parts=layout['buildings'];occupied={}
            for index,part in enumerate(parts):
                for cell in cells(part):
                    self.assertNotIn(cell,occupied,(count,part,cell))
                    occupied[cell]=index
            attached={0};queue=[0]
            while queue:
                index=queue.pop()
                for x,z in cells(parts[index]):
                    for adjacent in ((x+1,z),(x-1,z),(x,z+1),(x,z-1)):
                        neighbor=occupied.get(adjacent)
                        if neighbor is not None and neighbor not in attached:
                            attached.add(neighbor);queue.append(neighbor)
            self.assertEqual(len(attached),len(parts))
            self.assertTrue(all(x>=0 and z>=0 for x,z in occupied))

    def test_native_required_parts_and_capacity_above_eight(self):
        counts=Counter(p['def_name'] for p in ship_blueprint(12)['buildings'])
        for name,minimum in {'Ship_CryptosleepCasket':12,'Ship_Engine':3,'Ship_Reactor':1,
                             'Ship_ComputerCore':1,'Ship_SensorCluster':1,'Ship_Beam':1}.items():
            self.assertGreaterEqual(counts[name],minimum)

    def test_casket_head_on_beam_and_entry_unblocked(self):
        parts=ship_blueprint(12)['buildings']
        beam_cells=set().union(*(cells(p) for p in parts if p['def_name']=='Ship_Beam'))
        occupied=set().union(*(cells(p) for p in parts))
        for p in parts:
            if p['def_name']=='Ship_CryptosleepCasket':
                self.assertIn((p['rel_x'],p['rel_z']-1),beam_cells)
                self.assertNotIn((p['rel_x']+1,p['rel_z']),occupied)

if __name__=='__main__':unittest.main()
