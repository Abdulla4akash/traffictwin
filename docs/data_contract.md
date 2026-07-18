# Data Contract

Phase 2 canonicalises declared source CSV files into in-memory records only. Raw files remain unchanged, and full canonical row storage is deferred.

Every canonical record carries:

- `source_file`;
- `source_row`.

## TaskRecord

- `task_id`
- `vehicle_id`
- `task_class`: `T1`, `T2`, `T3`, or `unknown`
- `arrival_time_s`
- `deadline_ms`
- `decision`: `local`, `v2i`, `v2v`, or `unknown`
- `completed`
- `completion_time_s` optional
- `latency_ms` optional
- `target_id` optional
- `workload_cycles` optional
- `data_size_bytes` optional
- `energy_j` optional
- `drop_reason` optional

## InfrastructureRecord

- `timestamp_s`
- `rsu_id`
- `queue_length` optional
- `utilisation_fraction` optional
- `arrivals` optional
- `active_tasks` optional
- `drops` optional
- `capacity` optional

## VehicleStateRecord

- `timestamp_s`
- `vehicle_id`
- `x` optional
- `y` optional
- `speed_mps` optional
- `lane` optional
- `tier` optional

## TrafficObservationRecord

- `timestamp_s`
- `sensor_id`
- `count` optional
- `average_speed_mps` optional
- `location` optional

## TripRecord

- `trip_id`
- `vehicle_id` optional
- `departure_time_s`
- `arrival_time_s` optional
- `duration_s` optional
- `route_id` optional

## IncidentRecord

- `incident_id`
- `timestamp_s`
- `incident_type`
- `location` optional
- `severity` optional

## Evidence Availability

Evidence categories use:

- `available`
- `partial`
- `unavailable`
- `invalid`

Future metrics and rules must consume this state before attempting computation.

## Phase 3 Metric Contract

Metric computation consumes `CanonicalTables`, `RunMetricContext`, and `EvidenceAvailability`. It does not mutate canonical records and it does not read raw files directly.

Metric outputs are `MetricValue` records grouped into a `MetricCollection`.

Each `MetricValue` includes:

- stable metric key;
- status: `available`, `unavailable`, `partial`, or `invalid`;
- value or `null`;
- unit;
- aggregation scope;
- required evidence;
- missing evidence;
- stable reason codes;
- implementation version;
- run, experiment, seed, algorithm, checkpoint, random-seed, and synthetic provenance;
- computation timestamp.

Rejected validation reports produce `invalid` metric values rather than computed numbers.

## Evidence Pack Contract

Evidence packs contain validation summaries, evidence availability, metric-engine configuration, metric collections, and provenance. They are the only supported input for deterministic diagnostic rules. They do not include LLM-rendered prose or XAI output.

## Related Documents

- [Run bundle specification](run_bundle_spec.md)
- [Validation codes](validation_codes.md)
- [Metrics catalogue](metrics_catalogue.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [API reference](api_reference.md)
