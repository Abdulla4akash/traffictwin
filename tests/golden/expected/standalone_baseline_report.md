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
- Bundle fingerprint: `4d9b2bc66e3ef4dddc4492e1cbd9a87cf5931c7134ea95474ee2f28698948ad5`

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
- `task.offload.rate`: 0.606061
- `infra.utilisation.p95`: 0.561 fraction
- `infra.queue_length.max`: 3 tasks
- `trip.duration.p95_s`: 598 s
- `traffic.speed.mean_mps`: 14 m/s

## Diagnostic Hypotheses

- Report: `diagnostic-024b2c30d804`
- Overall readiness: `partially_ready`
- Triggered rules: none
- Insufficient rules: R3
- `R0` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R1` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R2` not_triggered: no candidate hypothesis (confidence `unavailable`)
- `R3` insufficient_evidence: no candidate hypothesis (confidence `unavailable`)

## Provenance Summary

- Trace: `provenance-bbf0d0315afc`
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
