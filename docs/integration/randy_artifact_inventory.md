# Randy/SUMO Artifact Inventory

Discovery date: 2026-07-17

TrafficTwin root inspected: repository root

Workspace inspected: repository parent workspace

## Discovery Method

The discovery pass inspected the approved TrafficTwin repository, the wider workspace, and the historical `XITS/` notes. It searched for:

- Randy/VEC output files, logs, configurations, checkpoints, scripts, notebooks, and job files;
- SUMO configuration, network, route, additional, FCD, tripinfo, detector, queue, and summary outputs;
- CSV, YAML, JSON, XML, ZIP, SQLite, Parquet, pickle, checkpoint, shell, notebook, SLURM, PBS, log, and output artifacts.

No destructive commands were used. No source files were modified during discovery.

## Summary Finding

No real Randy/VEC environment artifacts and no SUMO artifacts are present in the inspected workspace.

The only tabular run files present are TrafficTwin's own synthetic fixtures under `tests/fixtures/bundles/`. Their manifests explicitly declare `source: synthetic_fixture` and `environment.name: synthetic`, so they are valid evidence for the internal TrafficTwin bundle contract but not evidence of Randy's real schema, SUMO schema, units, invocation commands, or runtime behavior.

## Candidate Files Found

| Source name | Producer | Purpose | Format | Status | Canonical target | Sample row count | Sufficient for current metrics | Sufficient for R1 | Sufficient for R2 | Sufficient for R3 |
|---|---|---|---|---|---|---:|---|---|---|---|
| `tests/fixtures/bundles/baseline_valid/manifest.yaml` | TrafficTwin synthetic fixture generator | Synthetic baseline manifest | YAML | confirmed synthetic | Run-bundle manifest | n/a | yes, synthetic only | partial, synthetic only | partial, synthetic only | no |
| `tests/fixtures/bundles/baseline_valid/tasks.csv` | TrafficTwin synthetic fixture generator | Synthetic task records | CSV | confirmed synthetic | `TaskRecord` | 3 | yes, synthetic only | partial, no vehicle-tier cross-tab | no | no |
| `tests/fixtures/bundles/baseline_valid/infra_state.csv` | TrafficTwin synthetic fixture generator | Synthetic RSU state | CSV | confirmed synthetic | `InfrastructureRecord` | 4 | yes, synthetic only | partial, utilisation only | partial, no task-window overlap | no |
| `tests/fixtures/bundles/baseline_valid/traffic_obs.csv` | TrafficTwin synthetic fixture generator | Synthetic traffic observations | CSV | confirmed synthetic | `TrafficObservationRecord` | 2 | yes, synthetic only | no | no | no |
| `tests/fixtures/bundles/baseline_valid/trips.csv` | TrafficTwin synthetic fixture generator | Synthetic trip records | CSV | confirmed synthetic | `TripRecord` | 2 | yes, synthetic only | no | no | no |
| `tests/fixtures/bundles/variation_valid/*` | TrafficTwin synthetic fixture generator | Synthetic variation bundle | YAML/CSV | confirmed synthetic | Manifest plus task, infrastructure, traffic, trip records | tasks 4, infra 4, traffic 2, trips 2 | yes, synthetic only | partial, synthetic only | partial, synthetic only | no |
| `tests/fixtures/bundles/partial_valid/*` | TrafficTwin synthetic fixture generator | Synthetic partial bundle with tasks only | YAML/CSV | confirmed synthetic | Manifest plus `TaskRecord` | tasks 2 | task metrics only | insufficient infrastructure and vehicle-tier evidence | insufficient | no |
| `tests/fixtures/bundles/invalid_manifest/*` | TrafficTwin synthetic fixture generator | Unsupported manifest-schema fixture | YAML | confirmed synthetic | Rejected manifest case | n/a | no | no | no | no |
| `tests/fixtures/bundles/invalid_rows/*` | TrafficTwin synthetic fixture generator | Invalid-row validation fixture | YAML/CSV | confirmed synthetic | Validation-error case | tasks 2, infra 1, trips 1 | invalid or partial by policy | no | no | no |
| `tests/fixtures/diagnostics/cases.json` | TrafficTwin synthetic diagnostic fixture generator | Evidence-level synthetic diagnostic cases | JSON | confirmed synthetic | EvidencePack test inputs, not raw environment data | 7 cases | n/a | yes, implementation test only | yes, implementation test only | yes, implementation test only |
| `examples/seeds/arena_gridlock.yaml` | TrafficTwin example | Example ScenarioSeed | YAML | confirmed synthetic/structural | `ScenarioSeed` | n/a | no run data | no | no | no |
| `docs/traffictwin-design-v0_4.md` | Abdulla/Sandra/Randy design notes | Product and research specification | Markdown | confirmed design document | Architecture guidance | n/a | no raw data | no | no | no |
| `../XITS/*.md` | Historical research notes | Superseded research context and literature notes | Markdown | confirmed historical notes | none | n/a | no | no | no | no |
| Randy/VEC task logs | Not present | Unknown | Unknown | unsupported | `TaskRecord` | 0 | no | no | no | no |
| Randy/VEC infrastructure logs | Not present | Unknown | Unknown | unsupported | `InfrastructureRecord` | 0 | no | no | no | no |
| Randy/VEC vehicle-state logs | Not present | Unknown | Unknown | unsupported | `VehicleStateRecord` | 0 | no | no | no | no |
| Randy/VEC config files | Not present | Unknown | Unknown | unsupported | ScenarioSeed/control mapping | 0 | no | no | no | no |
| Randy checkpoints | Not present | Unknown | `.pt`, `.pth`, `.ckpt`, or equivalent | unsupported | Run provenance only | 0 | no | no | no | no |
| Randy plotting or metric scripts | Not present | Unknown | Python/notebook/shell | unsupported | Metric reconciliation | 0 | no | no | no | no |
| SUMO `.sumocfg` | Not present | Mobility configuration | XML | unsupported | Scenario/execution provenance | 0 | no | no | no | no |
| SUMO network/route/additional XML | Not present | Mobility network and routes | XML | unsupported | Vehicle, traffic, trip context | 0 | no | no | no | no |
| SUMO FCD XML | Not present | Vehicle trajectories | XML | unsupported | `VehicleStateRecord` | 0 | no | no | no | no |
| SUMO tripinfo XML | Not present | Trip outcomes | XML | unsupported | `TripRecord` | 0 | no | no | no | no |
| SUMO detector/summary/queue output | Not present | Traffic detector or queue summaries | XML/CSV | unsupported | `TrafficObservationRecord` or infrastructure records | 0 | no | no | no | no |
| CSF, SLURM, PBS, or shell job scripts | Not present | Execution contract | shell/job script | unsupported | Launcher contract | 0 | no | no | no | no |

## Synthetic Fixture Columns And Units

These columns are confirmed only for TrafficTwin's synthetic generic bundle contract.

| File | Source columns | Declared source units | Canonical fields | Transformations |
|---|---|---|---|---|
| `tasks.csv` | `task_id`, `vehicle_id`, `task_class`, `arrival_time`, `deadline_ms`, `decision`, `completed`, `completion_time`, `latency_ms`, `target_id` | `arrival_time: s`, `completion_time: s`, `deadline_ms: ms`, `latency_ms: ms` | `TaskRecord` identity, class, arrival, deadline, decision, completion, latency, target, provenance | Manifest-driven parse and explicit unit validation. No Randy-specific assumptions. |
| `infra_state.csv` | `timestamp`, `rsu_id`, `queue_length`, `utilisation` | `timestamp: s`, `utilisation: fraction` | `InfrastructureRecord` timestamp, RSU, queue length, utilisation, provenance | Manifest-driven parse. No capacity inference. |
| `traffic_obs.csv` | `timestamp`, `sensor_id`, `count`, `average_speed` | `timestamp: s`, `average_speed: m/s` | `TrafficObservationRecord` timestamp, sensor, count, speed, provenance | Manifest-driven parse. Count interval semantics remain documented limitation. |
| `trips.csv` | `trip_id`, `vehicle_id`, `departure_time`, `arrival_time`, `duration`, `route_id` | `departure_time: s`, `arrival_time: s`, `duration: s` | `TripRecord` identity, departure, arrival, duration, route, provenance | Manifest-driven parse and consistency checks. |

## Unresolved Ambiguity

- Randy/VEC task schema is unknown.
- Randy/VEC infrastructure schema is unknown.
- Randy/VEC vehicle-tier, action-availability, link-quality, queue, capacity, energy, workload, data-size, and drop-reason outputs are unknown.
- SUMO output formats present in the intended environment are unknown.
- Time, speed, distance, utilisation, data-size, workload, energy, and queue units are unknown for real artifacts.
- Identifier conventions for vehicles, RSUs, tasks, routes, sensors, and decision targets are unknown.
- Whether outputs represent training, validation, lightweight simulation, SUMO validation, or experiment summaries is unknown.
- Existing metric or plotting scripts are unavailable, so metric reconciliation cannot begin.

## Discovery Conclusion

Phase 6B adapter implementation is not supported by repository evidence. The correct next step is to request a real or sanitised Randy/SUMO sample set with schemas, units, and execution documentation.
