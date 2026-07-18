# Validation Codes

Every validation finding includes:

- stable `code`;
- `severity`: `info`, `warning`, `error`, or `fatal`;
- message;
- affected file;
- affected row;
- affected field;
- observed value when useful;
- `may_continue`;
- affected capabilities.

## Severity Policy

- `info`: non-problematic context.
- `warning`: import may continue, but downstream evidence may be partial or unavailable.
- `error`: invalid data or metadata. Import may continue only if the finding explicitly has `may_continue: true`.
- `fatal`: validation cannot continue safely.

Overall import status:

- `accepted`: no warnings, errors, or fatal findings.
- `accepted_with_warnings`: import may continue but findings exist.
- `rejected`: at least one finding has `may_continue: false`.

## Bad Row Policy

Validation continues where safe so a complete report is produced.

- Missing identity fields generally skip the row and block import.
- Invalid optional numeric fields may be retained as unavailable/null when safe.
- Duplicate task IDs, impossible task timing, negative latency, unknown units, and invalid trip timing block import.
- Out-of-range utilisation is retained as unavailable for that field and blocks dependent infrastructure capabilities.

## Codes

| Code | Typical severity | Meaning |
|---|---|---|
| `BUNDLE_MANIFEST_MISSING` | fatal | `manifest.yaml` is absent. |
| `BUNDLE_MANIFEST_INVALID` | fatal | Manifest YAML cannot be parsed or validated. |
| `MANIFEST_SCHEMA_UNSUPPORTED` | fatal | Manifest schema version is unsupported. |
| `MANIFEST_REQUIRED_FIELD_MISSING` | fatal | Required manifest metadata is missing. |
| `FILE_DECLARED_MISSING` | error | A manifest-declared file is absent. |
| `FILE_UNDECLARED_PRESENT` | warning | A known source file is present but undeclared. |
| `FILE_UNREADABLE` | fatal | Bundle or source file cannot be read. |
| `FILE_CHECKSUM_MISMATCH` | error | Declared checksum does not match file content. |
| `SEED_MISSING` | fatal | `seed.yaml` is absent or invalid. |
| `SEED_ID_MISMATCH` | error | Manifest seed ID differs from `seed.yaml`. |
| `RUN_ID_DUPLICATE` | error | Reserved for duplicate run checks. |
| `RUN_METADATA_INCONSISTENT` | error | Reserved for inconsistent run metadata. |
| `ENVIRONMENT_VERSION_MISSING` | error | Neither environment version nor commit is supplied. |
| `REQUIRED_COLUMN_MISSING` | error | A required declared column is absent. |
| `UNKNOWN_COLUMN` | warning | Source column is not declared or mapped. |
| `UNKNOWN_UNIT` | error | Unit is required but missing. |
| `UNIT_CONVERSION_UNSUPPORTED` | error | Declared unit conversion is unsupported. |
| `TYPE_PARSE_FAILED` | error | A value cannot be parsed to the required type. |
| `TASK_ID_MISSING` | error | Task row has no task ID. |
| `TASK_ID_DUPLICATE` | error | Task ID is duplicated within the run. |
| `TASK_CLASS_UNKNOWN` | warning | Task class is not `T1`, `T2`, or `T3`. |
| `TASK_DECISION_UNKNOWN` | warning | Decision is not `local`, `v2i`, or `v2v`. |
| `TASK_COMPLETION_BEFORE_ARRIVAL` | error | Completion precedes arrival. |
| `TASK_LATENCY_NEGATIVE` | error | Latency is negative. |
| `TASK_DEADLINE_NEGATIVE` | error | Deadline is negative. |
| `TASK_COMPLETION_INCONSISTENT` | error | Reserved for inconsistent completion fields. |
| `RSU_ID_MISSING` | error | Infrastructure row has no RSU ID. |
| `UTILISATION_OUT_OF_RANGE` | error | Utilisation is outside `[0, 1]`. |
| `QUEUE_LENGTH_NEGATIVE` | error | Queue length is negative. |
| `TIMESTAMP_INVALID` | error | Timestamp is missing or invalid. |
| `SPEED_NEGATIVE` | error | Speed is negative. |
| `COUNT_NEGATIVE` | error | Count is negative. |
| `VEHICLE_ID_MISSING` | error | Vehicle ID is missing. |
| `TRIP_ARRIVAL_BEFORE_DEPARTURE` | error | Trip arrival precedes departure. |
| `TRIP_DURATION_NEGATIVE` | error | Trip duration is negative. |
| `TRIP_DURATION_INCONSISTENT` | warning | Duration differs from arrival minus departure. |
| `TASK_COUNT_MISMATCH` | error | Reserved for cross-file task-count reconciliation. |
| `UNKNOWN_VEHICLE_REFERENCE` | warning | Task references an unknown vehicle. |
| `UNKNOWN_RSU_REFERENCE` | warning | V2I task references an unknown RSU. |
| `TEMPORAL_COVERAGE_GAP` | warning | Reserved for temporal coverage checks. |
| `EVIDENCE_TASKS_UNAVAILABLE` | warning | Task evidence is unavailable. |
| `EVIDENCE_INFRA_UNAVAILABLE` | warning | Infrastructure evidence is unavailable. |
| `EVIDENCE_TRAFFIC_UNAVAILABLE` | warning | Traffic evidence is unavailable. |
| `EVIDENCE_TRIPS_UNAVAILABLE` | warning | Trip evidence is unavailable. |
| `EVIDENCE_INSUFFICIENT_FOR_DIAGNOSIS` | warning | Diagnostic rules must treat evidence as insufficient. |

## Metric Unavailability Reason Codes

Phase 3 metric results use separate reason codes from validation findings:

| Reason code | Meaning |
|---|---|
| `REQUIRED_TABLE_UNAVAILABLE` | Required canonical table is absent or unavailable. |
| `REQUIRED_FIELD_UNAVAILABLE` | Required canonical field is absent or has no valid observations. |
| `NO_VALID_ROWS` | No usable rows exist for the metric. |
| `INSUFFICIENT_SAMPLE_SIZE` | Reserved for metrics requiring more observations. |
| `INVALID_SOURCE_DATA` | Bundle validation rejected the source data. |
| `UNIT_UNKNOWN` | Reserved for metrics blocked by unknown units. |
| `CAPACITY_UNAVAILABLE` | Capacity evidence required for the metric is absent. |
| `TASK_CLASS_UNAVAILABLE` | Task-class evidence is absent. |
| `VEHICLE_TIER_UNAVAILABLE` | Vehicle-tier evidence is absent. |
| `NO_COMPLETED_TRIPS` | No completed trip duration evidence exists. |
| `NO_LATENCY_VALUES` | No latency observations exist. |
| `COMPARISON_PAIR_INCOMPATIBLE` | Reserved for incompatible comparison pairs. |
| `RANDOM_SEED_MISMATCH` | Compared runs have different random seeds where matching is required. |
| `BASELINE_ZERO` | Relative delta is unavailable because baseline is zero and variation is non-zero. |
| `METRIC_NOT_APPLICABLE` | Metric is not applicable to the current input. |
| `METRIC_VERSION_MISMATCH` | Compared metric collections use different versions. |
| `UNIT_MISMATCH` | Compared metric values have different units. |
| `EXPERIMENT_MISMATCH` | Compared runs have different experiment IDs where matching is required. |
| `SEED_RELATIONSHIP_UNKNOWN` | Reserved for seed-relationship checks when seed snapshots are absent. |

## Related Documents

- [Run bundle specification](run_bundle_spec.md)
- [Data contract](data_contract.md)
- [Metrics catalogue](metrics_catalogue.md)
- [Testing strategy](testing_strategy.md)
- [Generated validation-code catalogue](reference/generated/validation_codes.json)
