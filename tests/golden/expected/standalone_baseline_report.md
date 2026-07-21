# TrafficTwin Run Report: run-baseline-7

- Report ID: `report-run-run-baseline-7`
- Generated at: `2026-07-18T00:00:00+00:00`
- Source: `baseline`
- Synthetic: `True`

## Report Summary

- TrafficTwin standalone report.
- This report uses synthetic fixture data, not live or externally validated traffic data.
- Run: `run-baseline-7`
- Bundle: `bundle-baseline-7`

## Run Provenance

- Experiment: `exp-standalone-demo`
- Seed: `seed-baseline`
- Algorithm/profile: `synthetic-balanced`
- Checkpoint: `none`
- Random seed: `7`
- Environment: `synthetic` version `1.0`
- Bundle fingerprint: `d6b7a88794bfedaad3ceb0d7da1cce1faace3ca509e0c48d46d066a6ef773fed`

## Validation Results

- Status: `accepted`
- May import: `True`
- Findings: `0`
- error: `0`
- fatal: `0`
- info: `0`
- warning: `0`

## Evidence Availability

- Available: tasks, infrastructure, vehicles, traffic, trips, diagnosis
- Unavailable: incidents
- Canonical counts: incidents=0, infrastructure=22, tasks=33, traffic=11, trips=12, vehicles=220

## Metrics

- Metric version: `1.0`
- `task.generated.count`: 33
- `task.completed.count`: 31
- `task.completion.rate`: 0.939394
- `task.incomplete.rate`: 0.0606061
- `task.latency.p95_ms`: 308.135 ms
- `task.latency.p99_ms`: 426.023 ms
- `task.energy.mean_per_observed_task_j`: 0.994194 J/task
- `task.energy.per_completed_j`: 0.994194 J/task
- `task.energy_delay_product.mean_j_ms`: 215.273 J*ms/task
- `fairness.vehicle_tier.completion_rate.max_gap`: 0.166667
- `fairness.vehicle_tier.completion_rate.jain`: 0.993127 index
- `fairness.rsu.capacity_normalised_load.max_gap`: 0 fraction
- `infra.load_balance.jain_capacity_normalised`: 1 index
- `spatial.rsu.task.count_by_target`: {'rsu-1': 11, 'rsu-2': 7}
- `spatial.rsu.task.completion_rate_by_target`: {'rsu-1': 1.0, 'rsu-2': 1.0}
- `spatial.rsu.task.deadline_miss.completed_observed_rate_by_target`: {'rsu-1': 0.0, 'rsu-2': 0.0}
- `spatial.vehicle.observation_count_by_grid_cell`: {'x0:y0': 19, 'x1:y0': 52, 'x2:y0': 77, 'x3:y0': 52, 'x4:y0': 20} observations
- `spatial.vehicle.distinct_count_by_grid_cell`: {'x0:y0': 7, 'x1:y0': 15, 'x2:y0': 20, 'x3:y0': 16, 'x4:y0': 8} vehicles
- `spatial.vehicle.speed.mean_mps_by_grid_cell`: {'x0:y0': 12.473684210526315, 'x1:y0': 11.826923076923077, 'x2:y0': 11.87012987012987, 'x3:y0': 11.76923076923077, 'x4:y0': 12.0} m/s
- `task.offload.rate`: 0.606061
- `infra.utilisation.p95`: 0.561 fraction
- `infra.queue_length.max`: 3 tasks
- `trip.duration.p95_s`: 598 s
- `traffic.speed.mean_mps`: 14 m/s

## Diagnostic Hypotheses

- Report: `diagnostic-b07e1f7bc22d`
- Overall readiness: `partially_ready`
- Triggered rules: none
- Insufficient rules: R3, R5, R6
- Cross-rule policy: `1.0`
- Cross-rule relationships: conflict=0, corroboration=0, suppression=0
- Suppressed-for-action rules: none (all original results retained)
- `R0` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R1` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R2` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R3` insufficient_evidence: no candidate hypothesis (confidence `unavailable`)
- `R4` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R5` insufficient_evidence: no candidate hypothesis (confidence `unavailable`)
- `R6` insufficient_evidence: no candidate hypothesis (confidence `unavailable`)
- `R7` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R8` not_triggered: no candidate hypothesis (confidence `unavailable`)

## Provenance Summary

- Trace: `provenance-c4a3f8991a74`
- Completeness: `partial`
- Nodes: `143`
- Edges: `198`

## Limitations

- Synthetic records are deterministic software fixtures, not real-world validation.
- Diagnostic outputs are candidate hypotheses and do not establish root causes.
- No Randy/VEC, SUMO, live Manchester, near-live, or true-live integration is active.

## Reproduction Commands

- `traffictwin bundle validate baseline`
- `traffictwin metrics compute baseline`
- `traffictwin diagnose bundle baseline`
- `traffictwin provenance run baseline`
