# Instant building placement

`POST /api/v1/builder/blueprint` uses the loaded game's `WorkToBuild` stat,
including inherited and material-specific values. As in RimWorld's
`Designator_Build`, a building with exactly zero work is placed immediately.
There is no developer-mode bypass. A building with positive work remains a
blueprint and requires normal materials, skill, construction time and success.

This covers caravan, crafting, double sleeping, gathering, meditation and ritual
spots as well as the previously supported sleeping and butcher spots. It is not
a definition-name allowlist. Native research, material, footprint, terrain and
PlaceWorker validation applies before placement. PostPlace hooks and ideology
styles are retained.

A request for a matching legacy zero-work blueprint/frame replaces that invalid
project with the completed marker only after placement validation. Repeating the
request for an existing completed marker retains its ID. It does not cancel or
complete neighboring ordinary construction projects.

`GET /api/v1/buildings/catalog` and `GET /api/v1/builder/projects` export
`work_to_build` and `is_instant_building`. An instant building appearing in the
projects list is a legacy invalid project, not work for a colonist.
`POST /api/v1/builder/prioritize` rejects such a project without assigning a job.
Project `percent_complete` is a finite number in [0, 1], including old zero-work
frames whose vanilla percentage would be 0/0. These GET routes are read-only.

Regression checks:

- `tests/native_instant_construction_boundary.ps1` compiles the shipped helper
  with a stat lookup fixture and checks generic definitions, material overrides,
  ordinary positive-work buildings and finite progress boundaries.
- A separate authorized paused-game check must verify legacy marker migration,
  repeat-request identity, retained ordinary frames, campaign/tick preservation,
  and the saved XML. Passing the helper checks alone does not prove live repair.
