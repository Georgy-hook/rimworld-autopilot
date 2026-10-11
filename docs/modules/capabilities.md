# Capabilities contracts

Offline audit and patch, 2026-10-02. No game, model, live API, build or git operations were used. Native compilation is a root review gate.

## Producer → consumer → order

Director `collect_development` reads the native catalog/context on the selected map. Bridge unwraps generic `ApiResult<T>.Data`, while nongeneric `ApiResult` keeps its `success` envelope. Native JSON uses snake_case. Capabilities prepares legal alternatives, Laya chooses, and execute sends the following requests.

| Observation | Order | Required selection/body | Acceptance |
|---|---|---|---|
| GET `/api/v1/plants/catalog?map_id=…&center_x=…&center_z=…`, map plant observations | POST `/api/v1/map/zone/growing` | map_id, plant_def, point_a, point_b | legacy GrowingZoneDto: matching plant_def_name and positive zone.cells_count; creation may be partial |
| Same catalog, existing ground/basin | POST `/api/v1/map/zone/growing/crop` | map_id, plant_def, zone_id or building_id | CapabilityOrderResultDto.applied |
| Actual blighted plants | POST `/api/v1/map/plants/cut-blight` | map_id, plant_ids, worker_pawn_id | applied, actual affected_count; already designated/sowing-paused targets are no changes |
| Harvestable dying plants | POST `/api/v1/map/plants/harvest` | map_id, plant_ids | nongeneric success |
| GET `/api/v1/medical/augmentations?map_id=…` | POST `/api/v1/medical/augmentation` | map_id, patient_pawn_id, doctor_pawn_id, bed_id, recipe_def, body_part_index | applied queues installation; never reports completed surgery |
| Native animal training observations in bridge colony-animal projection | POST `/api/v1/map/animal/training` | map_id, animal_id, trainable_def, wanted, handler_pawn_id; or master_pawn_id, follow_drafted | applied changes training/master policy; learning remains pending |
| GET `/api/v1/combat/state?map_id=…`, GET `/api/v1/weapons/catalog` | POST `/api/v1/pawn/job` | pawn_id, job_def=Equip, target_thing_id, map_id, allow_unforbid_equip | nongeneric success accepts ordered job, not completed equipment transfer |
| Research tree/current project and greenhouse context | POST `/api/v1/research/target?name=…&force=false` | chosen startable prerequisite | returned name matches requested project |

Auxiliary POST `/api/v1/colonist/work-priority` uses `{id,work,priority}`; POST `/api/v1/map/zone/growing/sowing` uses `{map_id,zone_id,allow_sow}`. Both return nongeneric success. A successful main effect with rejected/lost auxiliary permission is returned as `applied:true, partial:true`, with each auxiliary result and unknown outcome explicitly recorded. No accepted surgery, crop change or animal policy is repeated to repair priority/sowing.

## Retry and dwell

`capability_history` scopes successes by action and subject, including patient, animal, field, fighter or research project. Implant operations share patient dwell. Plant batches use individual thing IDs. Existing global `issued[capability:action]` entries are ignored. Successful policy dwell remains 15,000 game ticks; finite designation batches use 250 ticks and native designation observations remove completed requests.

Failures/unknown POST results use 250 game ticks **and** a minimum 30 seconds of wall time through shared colony_retry.failure_record/recent: both horizons must expire. Other subjects remain eligible. This prevents fast game speed from expiring suppression before the next ordinary director cycle. Defer remembers only subjects advertised in the actual choice stages, for 250 ticks. No unseen patient/fighter is deferred.

`capability_auxiliary` contains only missing work/sowing steps per selected subject. Retries submit only those steps; accepted steps disappear. Pending repair expires 15,000 ticks after the original partial effect, rather than extending indefinitely on each failure. Priority repairs are idempotent. History is bounded to 512 entries, JSON serializable, and prunes expired/malformed/future entries, wall-clock rollback, malformed/far-future retry deadlines and other maps. A tick rollback does not retain future action history.

## Native safety and purity

Food/crop exception, 7 October: stored nutrition and future acreage are separate
facts. Short reserves protect viable edible fields, including unsown commitments.
Crop configuration uses shared farm/site dwell of at least120 real seconds and
30000 ticks. A meaningful food/climate change reopens it; other actors or sites
do not. A selected grower's routine priority-one ties are lowered while clinical
priorities and jobs are preserved. See the
[food commitment audit](../audits/lenrobum-food-commitment-2026-10-07.md).

Plant GET preview passes null grower only for new-ground sites: the new-ground sow-tag branch does not call CanSowOnGrower; null is safe for the power type check. It no longer constructs a Zone_Growing, whose installed native base constructor consumes a unique zone ID. Existing ground/basin paths retain real growers.

Blight walks actual map plants once with a requested-ID HashSet. Eligibility precedes the 200-change bound, so stale/unreachable/already handled input IDs cannot starve later eligible plants. It counts new cut designations or actual sowing pauses, preserves a currently running blight-cut job, and does not mutate healthy plants.

Augmentation uses loaded medical WorkGiver required capacities (including Manipulation), actual recipe skills, materials/medicine, reach and bed constraints. Before any bed, bed-rest or bill mutation POST rejects an already queued exact operation or any ongoing surgery on that patient. Existing bill, surgeon restriction and bed are preserved. There is no preparatory auto-amputation.

Equip remains in the existing generic endpoint, with a narrow guarded Equip branch. It validates current owned controlled pawn/map, live map target, native CanEquip, reserve/reach and protected activity before touching forbidden permission. Already running Equip is preserved. An explicit allow_unforbid_equip is scoped to the verified target; failed/thrown job acceptance restores the previous forbidden flag. Other generic jobs retain their existing contract.

Python workers and weapon recipients, native augmentation patient/surgeon and animal handlers/masters protect the full CombatNativeHelper care set plus Ingest. Priority zero remains eligible for explicit selection because enabling the chosen worker is a separate, observable auxiliary step. Different-quality/condition same-def specialist weapons remain explicit Laya alternatives; EMP score zero no longer hides them or automatically chooses a replacement.

## Verification and boundaries

`tests/test_capability_contracts.py` covers sequential success/new subject, rejection/expiry, unknown transport, accepted surgery followed only by priority repair, shown-patient defer/new patient, JSON/malformed/map/rollback pruning, fast-game/wall-time expiry, full care exclusions, designated blight and same-def EMP alternatives. Existing capability tests also pass. These are offline fixture tests; native game behavior and compilation remain unexecuted here.

There is no colony_ecology.py. Seasonal sow/resume and acreage/greenhouse orchestration partly live in director. Animal release/recall lives outside capabilities.execute and uses the existing native release endpoint; no new combat strategy was added.
