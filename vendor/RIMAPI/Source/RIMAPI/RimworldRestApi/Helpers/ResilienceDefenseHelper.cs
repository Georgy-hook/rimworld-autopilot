using System.Linq;
using RimWorld;
using Verse;
using Verse.AI;
namespace RIMAPI.Helpers
{
    public static class ResilienceDefenseHelper
    {
        private static bool Solid(IntVec3 cell, Map map) => cell.InBounds(map) && cell.GetEdifice(map) is Building wall
            && !(wall is Building_Door) && wall.def.passability == Traversability.Impassable;
        public static bool IsActualChoke(Building defense)
        {
            if (!(defense is Building_Door) || !defense.Spawned) return false;
            var c=defense.Position; var m=defense.Map;
            return (Solid(c+IntVec3.East,m) && Solid(c+IntVec3.West,m) && (c+IntVec3.North).Standable(m) && (c+IntVec3.South).Standable(m))
                || (Solid(c+IntVec3.North,m) && Solid(c+IntVec3.South,m) && (c+IntVec3.East).Standable(m) && (c+IntVec3.West).Standable(m));
        }
        public static bool TryPosition(Pawn pawn, Pawn hostile, Building defense, int roleIndex, out IntVec3 result)
        {
            result=IntVec3.Invalid;
            if (!IsActualChoke(defense) || hostile == null || roleIndex < 0) return false;
            Map map=defense.Map; IntVec3 door=defense.Position;
            IntVec3 inward=Solid(door+IntVec3.East,map) ? IntVec3.North : IntVec3.East;
            if ((door+inward).DistanceToSquared(hostile.Position) < (door-inward).DistanceToSquared(hostile.Position)) inward=-inward;
            IntVec3 side=new IntVec3(-inward.z,0,inward.x);
            bool ranged=pawn.equipment?.Primary?.def.IsRangedWeapon ?? false;
            if (!ranged && roleIndex >= 3) return false;
            int lane=roleIndex%3-1;
            int depth=ranged ? 2+roleIndex/3 : 1;
            IntVec3 cell=door+inward*depth+side*lane;
            if (!cell.InBounds(map) || !cell.Standable(map) || cell.Fogged(map) || cell.ContainsStaticFire(map)
                || cell.GetThingList(map).Any(t => t is Building_Trap && t.Faction == Faction.OfPlayer)
                || cell.GetThingList(map).OfType<Pawn>().Any(p => p != pawn)) return false;
            PawnPath path=map.pathFinder.FindPathNow(pawn.Position,cell,pawn,null,PathEndMode.OnCell);
            bool valid=path.Found && path.NodesReversed.All(n => !n.GetThingList(map).Any(t => t is Building_Trap && t.Faction == Faction.OfPlayer));
            path.ReleaseToPool();
            if (!valid) return false;
            result=cell; return true;
        }
    }
}
