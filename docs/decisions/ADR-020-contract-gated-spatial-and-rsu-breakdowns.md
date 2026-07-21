# ADR-020: Contract-Gated Spatial And Per-RSU Breakdowns

Status: accepted

## Context

TrafficTwin v0.5 `MET-05` requires per-RSU completion, load, miss, and supported spatial
summaries. Canonical tasks already preserve `decision` and `target_id`, infrastructure rows
preserve `rsu_id`, and vehicle rows preserve `x/y`. Those fields alone do not prove that a V2I
target is the executing RSU, that every target joins, that coordinates share a known unit/frame,
or that a task can be spatially interpolated. Current TOS slots are time-local, and current SUMO
support contains trips rather than compatible task/vehicle/RSU rows.

## Decision

- Add two independent strict v1.0 manifest contracts:
  - `TaskRsuTargetContract` declares that canonical `target_id` on a V2I task is its observed
    executing RSU, joined exactly to canonical `infrastructure.rsu_id`;
  - `VehicleSpatialGridContract` declares vehicle-position-at-observation semantics, metre units,
    a named source coordinate frame, fixed origin/cell geometry, and floor-based assignment.
- A task-to-RSU contract requires tasks and infrastructure declarations, with mapped `target_id`
  and `rsu_id` source columns explicitly required.
- A vehicle-grid contract requires a vehicle declaration, required mapped `x/y` columns, and
  explicit `m` units for both axes.
- Admit per-RSU task outcomes only for canonical V2I tasks. Require every in-scope V2I task to
  have a non-empty target that matches an in-scope canonical RSU. Do not drop unmatched tasks.
- Compute:
  - V2I task count by target RSU;
  - V2I completion rate by target RSU;
  - completed-observed deadline-miss rate by target RSU.
- Preserve the ordinary miss denominator: completed tasks with observed latency and deadline.
  Missing group support remains null/partial; it is never zero.
- Reuse existing per-RSU infrastructure evidence for load: `infra.rsu.summary` and
  `fairness.rsu.capacity_normalised_load.by_group` provide source-row and strict normalised-load
  views respectively.
- Require finite `x/y` for every in-scope vehicle observation before releasing any grid output.
  Compute:
  - observation count by cell;
  - distinct vehicle count by cell;
  - mean eligible speed by cell, with missing speed visibly partial/null.
- Attach contract version/fingerprint, exact group/cell-set fingerprint, support, coverage,
  geometry, frame identity, and eligibility metadata.
- Apply the same contracts after independent fixed-window filtering. A task window does not borrow
  an out-of-window RSU row, and a vehicle window does not borrow an out-of-window coordinate.
- Do not infer nearest RSUs, task positions, routes, coordinate reference systems, geographic
  areas, target causality, or missing values.

## Consequences

- Six new single-run/windowed definitions increase the ordinary catalogue from 57 to 63 and the
  window-applicable total from 54 to 60; the three comparison-only definitions remain unchanged.
- Generated synthetic bundles declare both contracts because the generator owns target and
  coordinate semantics. Their positions remain labelled synthetic and non-geographic.
- Existing uncontracted generic bundles retain canonical fields for replay but keep the new
  metrics unavailable.
- Current SUMO and TOS contracts keep the family unavailable. SUMO trip identifiers are not V2I
  task targets; TOS padded slots and processed coordinate arrays do not provide persistent
  canonical identities or a compatible manifest contract.
- Exact target grouping records observed execution lineage. It does not prove that an RSU caused
  success, failure, delay, or load.
- `MET-05` does not add task-position interpolation, geographic heatmaps, routing inference, or an
  R7 rule.

## Acceptance Evidence

- Unit tests pin strict manifest contracts, fingerprints, exact grouping/grid values, target and
  coordinate coverage failures, incompatible joins, partial latency/speed support, windows, and
  complete accepted-row ledgers.
- A reviewed golden projection pins the complete generated-synthetic metric family.
- CLI, report, capability, SUMO/TOS boundary, generated-reference, Streamlit, lint, typing,
  package-build, and full-suite gates cover public surfaces.

## Alternatives Considered

- Treat every V2I `target_id` as an RSU without a contract: rejected because the external semantic
  meaning is not established by a column name.
- Assign missing targets to the nearest RSU: rejected because infrastructure coordinates and a
  target-selection rule are not evidenced.
- Join tasks to the latest/nearest vehicle coordinate: rejected because temporal interpolation and
  location-at-execution semantics are not contracted.
- Treat raw `x/y` as latitude/longitude or Manchester coordinates: rejected because no CRS or
  geographic mapping is declared.
- Drop rows with missing coordinates or targets: rejected because this could materially change a
  spatial or per-RSU conclusion while hiding coverage loss.
- Fill missing per-cell speeds or per-RSU misses with zero: rejected because unavailable is not
  zero.
