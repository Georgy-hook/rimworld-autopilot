# Mining: exact veins, workers and observed goods

The mining domain observes visible loaded ore products through
`GET /api/v1/mining/context`. It offers extraction and mineral hauling as
separate actions. The model chooses the product, connected vein and worker, or
defers. A doctrine preference is context, not permission to substitute gold or
silver. New visible resources are eligible independently of the legacy income
strategy timer.

## Ordinary execution

- Native extraction plans bind a free capable miner to at most twelve exact,
  connected, visible ore IDs. Facts include remaining HP, loaded base yield,
  nominal market value, mining speed/yield, skill and travel distance.
- Native validation tests roof support with the whole batch absent. It shrinks
  a batch that would remove required supports. It checks current worker health,
  protected jobs, actual routes, temperature, gases and visible threats.
- `POST /api/v1/mining/order` regenerates current plans. It places normal Mine
  designations at the selected cells and asks the ordinary miner workgiver for
  the first job. If the job does not start, only newly added designations are
  removed. No mined products are spawned.
- A haul plan binds an observed mineral stack, worker and native completed
  storage destination. Both route legs are checked; execution starts an
  ordinary hauling job. These goods may have come from sources other than the
  selected vein.

## Labor, memory and outcomes

`colony_labor` protects current cooking, hunting, plant, mining and research
jobs across discretionary reassignment. Accepted role commitments last at
least 120 real seconds **and** 30,000 ticks unless the source becomes unavailable.
Care and firefighting use their own fresh urgency checks. Map changes, removed
workers and tick rollback release irrelevant history.

Mining retry/defer history is scoped to the exact worker and target batch. A
new vein is available even while an unchanged rejected plan is suppressed.
Python refreshes product, worker, IDs, cells and plan kind before posting; the
native handler checks the current plan again.

Job acceptance is not extraction completion. Later visible block identity and
product stock changes are reported separately. Missing identity data is unknown,
not proof that a vein disappeared. Arrival, provenance, an available buyer,
actual trade and income still require their own observations. Nominal ore value
does not establish profit or income per hour; mining does not supply food.

The offline contract is recorded in
[the postmortem repair audit](../audits/postmortem-source-repairs-2026-10-10.md).
