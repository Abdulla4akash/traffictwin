# Randy/SUMO Schema Mapping

Discovery date: 2026-07-17

## Mapping Status

No real Randy/VEC or SUMO source schemas were found in the inspected workspace. Therefore no real adapter mapping is confirmed.

The mappings below document the existing generic synthetic bundle contract only. They must not be treated as Randy's schema or SUMO's schema.

## Confirmed Internal Generic Bundle Mapping

| Source file | Source status | Source columns | Source units | Canonical target | Canonical fields | Validation requirements | Status |
|---|---|---|---|---|---|---|---|
| `tasks.csv` | TrafficTwin synthetic fixture | `task_id`, `vehicle_id`, `task_class`, `arrival_time`, `deadline_ms`, `decision`, `completed`, optional `completion_time`, `latency_ms`, `target_id` | Declared per manifest: seconds and milliseconds | `TaskRecord` | `task_id`, `vehicle_id`, `task_class`, `arrival_time_s`, `deadline_ms`, `decision`, `completed`, `completion_time_s`, `latency_ms`, `target_id`, `source_file`, `source_row` | Required columns, known units, parseable types, unique task IDs, recognised classes and decisions, non-negative deadlines and latency, completion not before arrival | confirmed for synthetic generic CSV only |
| `infra_state.csv` | TrafficTwin synthetic fixture | `timestamp`, `rsu_id`, `queue_length`, `utilisation` | Declared per manifest: seconds and fraction | `InfrastructureRecord` | `timestamp_s`, `rsu_id`, `queue_length`, `utilisation_fraction`, `source_file`, `source_row` | Required columns, known units, non-negative queue length, utilisation in `[0, 1]`, parseable timestamp | confirmed for synthetic generic CSV only |
| `traffic_obs.csv` | TrafficTwin synthetic fixture | `timestamp`, `sensor_id`, optional `count`, `average_speed` | Declared per manifest: seconds and metres per second | `TrafficObservationRecord` | `timestamp_s`, `sensor_id`, `count`, `average_speed_mps`, `source_file`, `source_row` | Required columns, known units, non-negative counts and speeds | confirmed for synthetic generic CSV only |
| `trips.csv` | TrafficTwin synthetic fixture | `trip_id`, optional `vehicle_id`, `departure_time`, optional `arrival_time`, `duration`, `route_id` | Declared per manifest: seconds | `TripRecord` | `trip_id`, `vehicle_id`, `departure_time_s`, `arrival_time_s`, `duration_s`, `route_id`, `source_file`, `source_row` | Required columns, known units, arrival not before departure, duration non-negative, explicit and derived duration consistency | confirmed for synthetic generic CSV only |

## Randy/VEC Mapping Status

| Desired evidence | Canonical target | Current status | Required before adapter work |
|---|---|---|---|
| Task output headers and sample rows | `TaskRecord` | unknown | Sample log or CSV, units, completion semantics, class labels, decision labels, target identifiers |
| Task data-size, workload, energy, drop reason | Optional `TaskRecord` fields | unknown | Source columns, units, missing-value policy |
| Vehicle tier and state | `VehicleStateRecord` | unknown | Source file, tier labels, coordinate/speed units, timestamp convention |
| Per-RSU utilisation and queue history | `InfrastructureRecord` | unknown | Time-series file, queue units, utilisation units/range, RSU identifiers |
| Arrivals, active tasks, drops, capacity | Optional `InfrastructureRecord` fields | unknown | Source columns, units, aggregation interval |
| Environment metadata | `Run` and manifest context | unknown | Environment name/version/commit, algorithm, checkpoint, random seed, training budget, execution mode |
| Existing metrics or plots | Reconciliation documentation | unknown | Script/notebook/formula definitions and expected outputs |

## SUMO Mapping Status

| Potential SUMO source | Canonical target | Current status | Required before adapter work |
|---|---|---|---|
| `.sumocfg` | Execution provenance and scenario context | not present | File sample and command used to run it |
| Network and route XML | Scenario and route context | not present | `.net.xml`, `.rou.xml`, `.add.xml` where used |
| FCD XML | `VehicleStateRecord` | not present | XML sample, timestep units, position and speed units, vehicle ID conventions |
| `tripinfo` XML | `TripRecord` | not present | XML sample, depart/arrival/duration units, route ID conventions |
| Detector or summary output | `TrafficObservationRecord` or aggregate context | not present | Output sample, detector semantics, interval length, units |
| Queue output | Infrastructure/traffic congestion context | not present | Output sample, queue definition, units |

## Mapping Rules For Future Phase 6B

- Do not infer units from column names alone.
- Do not put Randy-specific behavior into `adapters.generic_csv`.
- Real mappings must live in adapter-specific modules and declare accepted schemas and units.
- Fields absent from real outputs must remain null or unavailable.
- Every mapped row must preserve `source_file` and `source_row`.
- Unsupported or ambiguous conversions must emit validation findings.
- Generated TrafficTwin bundles must pass the existing Phase 2 validator before metrics or diagnostics run.

## Current Decision

The only confirmed mappings are the internal synthetic generic CSV mappings. Randy/VEC and SUMO mappings remain `unknown`, and real adapter implementation is blocked.
