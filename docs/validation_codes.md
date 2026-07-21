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
| `TABULAR_FILE_INVALID` | fatal | Declared CSV, gzip, or Parquet bytes cannot be decoded through the selected format. |
| `TABULAR_SIZE_LIMIT_EXCEEDED` | fatal | A generic table exceeds the 10,000,000-byte decoded ingestion limit. |
| `TABULAR_CHUNK_SIZE_EXCEEDED` | fatal | One decoded row or Parquet batch slice cannot fit the configured streaming chunk-byte bound. |
| `TABULAR_COLUMNS_DUPLICATE` | fatal | A generic table contains duplicate column names. |
| `PARQUET_SCHEMA_UNSUPPORTED` | fatal | Parquet contains a nested, binary, temporal, or otherwise unsupported column type. |
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
| `TASK_ENERGY_NEGATIVE` | error | Per-task energy is negative. |
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

### Manifest inference codes

| Code | Typical severity | Meaning |
|---|---|---|
| `MANIFEST_INFERENCE_SOURCE_INVALID` | fatal/error | Source is not a safe readable directory or contains an unsafe CSV path. |
| `MANIFEST_INFERENCE_NO_CSV` | fatal | Source contains no CSV files. |
| `MANIFEST_INFERENCE_LIMIT_EXCEEDED` | fatal/error | Published file/column/sample bounds are exceeded. |
| `MANIFEST_INFERENCE_CSV_INVALID` | error | CSV encoding, structure, or headers cannot be profiled safely. |
| `MANIFEST_INFERENCE_FILE_AMBIGUOUS` | warning | Several file kinds have equal eligible evidence; no kind is selected. |
| `MANIFEST_INFERENCE_FILE_UNRESOLVED` | warning | No kind has every required field mapped. |
| `MANIFEST_INFERENCE_FIELD_AMBIGUOUS` | warning | A required field has equally supported source columns. |
| `MANIFEST_INFERENCE_FIELD_UNMAPPED` | warning | A required field has no supported source candidate. |
| `MANIFEST_INFERENCE_CONFIRMATION_REQUIRED` | info | Draft is non-executable until accepted or edited. |
| `MANIFEST_INFERENCE_STALE_SOURCE` | error | CSV bytes/set changed after draft creation. |
| `MANIFEST_INFERENCE_EDIT_INVALID` | error | Reserved for an unsupported or inconsistent explicit edit. |

### SUMO result adapter codes

| Code | Typical severity | Meaning |
|---|---|---|
| `SUMO_SOURCE_DIRECTORY_INVALID` | fatal | The input is not a readable result directory. |
| `SUMO_MANIFEST_MISSING` | fatal | `sumo-source.yaml` is absent. |
| `SUMO_MANIFEST_INVALID` | fatal | Source YAML does not satisfy the strict manifest contract. |
| `SUMO_MANIFEST_SCHEMA_UNSUPPORTED` | fatal | Source-manifest version is unsupported. |
| `SUMO_VERSION_UNSUPPORTED` | error | The declared SUMO version has not passed adapter acceptance. |
| `SUMO_SOURCE_PROVENANCE_DECLARED` | info | Required source/licence/retrieval/checksum metadata is declared. |
| `SUMO_FILE_DECLARED_MISSING` | error | A declared XML file is missing or is not a regular file. |
| `SUMO_FILE_PATH_UNSAFE` | error | A declared raw file is a symlink or escapes the source root. |
| `SUMO_FILE_CHECKSUM_MISMATCH` | error | Raw XML differs from its declared SHA-256 checksum. |
| `SUMO_XML_UNSAFE` | fatal | DTD or entity declarations are present. |
| `SUMO_XML_MALFORMED` | fatal | XML cannot be parsed. |
| `SUMO_XML_ROOT_INVALID` | fatal | XML root is not the declared SUMO output type. |
| `SUMO_XML_REQUIRED_ATTRIBUTE_MISSING` | error | A required mapped attribute is absent. |
| `SUMO_XML_VALUE_INVALID` | error | A mapped numeric/count value violates the contract. |
| `SUMO_XML_ATTRIBUTE_IGNORED` | warning | An unmapped attribute remains raw and is not interpreted. |
| `SUMO_XML_ELEMENT_IGNORED` | warning | An unsupported child result remains raw. |
| `SUMO_TRIP_ID_DUPLICATE` | error | A tripinfo vehicle ID appears more than once. |
| `SUMO_TRIPINFO_CANONICALISED` | info | Safe departed tripinfo records were mapped. |
| `SUMO_TRIPINFO_INCOMPLETE` | warning | Departed unfinished/vaporised trips have no canonical duration. |
| `SUMO_TRIPINFO_UNDEPARTED` | warning | Negative-departure sentinel records remain source-only. |
| `SUMO_SUMMARY_TIME_ORDER_INVALID` | error | Summary timestamps are not strictly increasing. |
| `SUMO_SUMMARY_SOURCE_ONLY` | info | Summary steps are typed source evidence, not traffic counts. |
| `SUMO_FCD_MAPPING_REQUIRED` | info/fatal | FCD is unavailable; declaring it without a contract is fatal. |
| `SUMO_DIRECT_LAUNCH_UNSUPPORTED` | info | The result adapter cannot launch SUMO. |

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
- [SUMO output adapter](integration/sumo_output_adapter.md)
- [Manifest inference wizard](integration/manifest_inference_wizard.md)
- [Data contract](data_contract.md)
- [Metrics catalogue](metrics_catalogue.md)
- [Testing strategy](testing_strategy.md)
- [Generated validation-code catalogue](reference/generated/validation_codes.json)
