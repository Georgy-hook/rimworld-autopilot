# Food commitments after the 7 October defeat

The single random 0.0.8 playtest ended with native GameOver at tick 2431617,
approximately 5 h 36 min after autonomy began. All five human deaths have native
Malnutrition evidence. Founders were lost after about 1 h 20 min, 1 h 20 min and
2 h 20 min; the later worker and storyteller helper did not recover the colony.
The playtest report preserves observer times separately from native death ticks.

## Confirmed faults and corrections

Potential field output was being used to release food protection even with zero
stored food and a harvest days away. Food planning now separates stored runway,
potential production and acreage. A viable edible field, including an accepted
but unsown field, stays committed while reserves are short and its removal would
leave inadequate food acreage. Native edible products determine food, including
loaded definitions; hops, wood and flowers do not qualify.

Field configuration previously outpaced ordinary growing work. A successful
choice now has a farm-wide and site dwell lasting at least 120 real seconds and
30000 game ticks. Switching the worker or field does not bypass it. Real new
shortage, unsafe growing conditions, or save rollback permit reconsideration.
Enough planned acreage prevents additional food plots during a shortage. The
first-field planning window includes native harvest time and two days for
sowing/delivery, rather than waiting for the final two days of supplies.

When ripe food or a hunt is available during starvation, obtaining it stays
ahead of configuring more fields. Optional construction, art, rituals and
research cannot consume an otherwise empty survival decision. A chosen food
worker receives a priority above their routine priority-one ties; other
colonists and medical priorities are preserved. Existing food work and care are
not restarted. Priority readback proves assignments, not completed food jobs.

The cached model exposed a further fault: a healthy animal's medicine ceiling,
empty-shelf policies, and cleaning a kitchen without ingredients competed with
food acquisition. Sustenance now requires relevant patients, existing food, or
an executable kitchen bill during a food crisis. A new sick animal, usable food
or feasible recipe immediately reopens the relevant choice. Execution checks
these prerequisites again against the freshly read context.

Home-fire filtering previously removed harvest when nobody could fight the
fire. It now considers actual available firefighters; without one, guarded food
and patient actions remain available. This does not claim safe routes through
fire. The event harvest executor now uses native `thing_id` and
`harvestable_now`, verified edible products and a small batch, rather than
nonexistent `id`/`can_harvest` fields. Designations are not delivered food.

The observer now excludes queued and displayed pawn IDs from fallback death
captions. Model token-budget probes use bounded tokenization, avoiding the
observed overlength warning before the existing compact decision is produced.

## Evidence

- 1245 Python tests passed, including sequences for food commitments, new
  availability, rapid game-time progress, JSON persistence, rollback, native
  harvest DTOs, selected-worker priority readback, protected jobs and death queues.
- Cached local Laya on recorded first-hour and fifth-hour starvation snapshots,
  in forward and reversed candidate order, selected foraging in three cases and
  hunter priority in one. Empty policy/preparation alternatives were absent.
- The actual model selected an edible potato configuration with a specific
  grower. Accept, persist and advance by 40000 ticks retained the farm dwell.
- The complete API audit and Release-1.6 build remain required package gates.
  Private snapshots/replay outputs are retained outside Git; no game calls were
  made by the replay tool.

These are observed fault corrections and offline decision checks. Sustained
harvest, cooking, animal rescue, raids, income and ending progress still require
the authorized next autonomous colony. The old loading NRE, unknown bison
outcome and unsupported monument executor are not closed by these changes.
