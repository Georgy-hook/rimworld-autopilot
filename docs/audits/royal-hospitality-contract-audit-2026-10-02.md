# Royal hospitality prerequisite contract audit — 2026-10-02

## Evidence and scope

Offline inspection used the installed RimWorld 1.6 Royalty definitions and decompiled native Assembly-CSharp.dll. No game, director, observer, or model was launched. Python fixture tests verify projection, explicit choice, stale-choice rejection, and POST transport. Source guards verify native API calls; they do not demonstrate guest survival or an ending.

`Data/Royalty/Defs/QuestScriptDefs/Hospitality/Script_EndGame_RoyalAscent.xml` requires the native Count title gate, bedroom acceptance, and a 720000-tick hospitality stay. Native guest mood and attack conditions remain substantial campaign requirements. Existing generic quest acceptance delegates eligibility and eventual reward to the native quest.

## Concrete missing prerequisites repaired

The existing royalty projection exposed throne requirements but omitted actionable bedroom requirements and the future quest guests. The ordinary bed assignment capability also skipped nobles already owning an inadequate bed. This prevented explicit preparation and ownership upgrades for hospitality.

`RoyalHospitalityHelper.Context` now exports current controlled colonists and actual quest lodgers, separately from pending Royal Ascent guests obtained from native `QuestPart_RequirementsToAcceptBedroom.targetPawns`. Pending acceptance includes the native `CanAccept` result and each guest's individually qualifying unassigned bed IDs. These individual sets do not prove enough distinct beds for the whole party; native quest acceptance remains authoritative.

The schema provides native title, honor, current ownership, effective bedroom/throne requirements, minimum area and impressiveness, native unmet reasons, structured furniture alternatives/counts, compatible native floor definitions, required bed/throne definitions, and guest food/rest/mood/current job. `CanRequireBedroom` and `CanRequireThroneroom` plus effective title requirement retrieval respect native ascetic, room-requirement, prisoner, and quest-lodger waivers. Hostile or neutral titled visitors cannot enter the architecture roster. No fabricated minimum furniture quality is supplied; `min_quality` is null and native room impressiveness remains decisive.

The specialist context exposes `royal_assignments`. Laya explicitly chooses or defers an eligible bed/throne ownership change, including replacing an existing ordinary bed. Python re-fetches exact pawn/thing options before POST. Native execution re-enumerates current options and checks candidate assignment eligibility, ownership, reachability, proper room, and effective room requirements, then calls the ordinary `CompAssignableToPawn.TryAssignPawn`. Thrones evaluate the proposed throne definition while enforcing all other native requirements. No room is instantly improved and no title/honor is granted.

## Integration and remaining limits

The parent director integrates `specialists.royalty_context` into development royalty context. The architecture module consumes the exported structural requirements and generates native construction plans; construction completion, quality, impressiveness, personal-room suitability, guest needs, quest acceptance, defense, and hospitality success must be observed in play. Existing native honor/quest and title acceptance routes remain responsible for gaining the required title.

Verification: `test_royal_hospitality_contracts.py` 3 tests and `test_specialists.py` 17 tests passed with unittest. Parent's native build passed before the final roster/waiver/bed-definition additions; the parent owns the final build gate.
