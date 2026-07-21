# Data Contract

The ordinary generic bundle path canonicalises declared CSV, gzip-CSV, and flat scalar Parquet
source files into in-memory records. The opt-in streaming path emits the same records in bounded
`CanonicalChunk`/`CanonicalTables` payloads without retaining them all. Raw files remain unchanged,
and persistent full canonical row storage is deferred.

Every canonical record carries:

- `source_file`;
- `source_row`.

For generic tabular input, `source_row` is the one-based data-record ordinal plus the historical
header offset: the first data record is `2` for CSV, gzip-CSV, and Parquet. It is a logical record
locator, not a physical Parquet line number. For the SUMO XML adapter, it is the one-based
source-element ordinal among `tripinfo` elements; the raw source file and checksum remain
authoritative.

`ManifestInferenceDraft` is deliberately outside the canonical data contract: it contains bounded
mapping suggestions, `analysis_ready: false`, and `confirmation_required: true`. After explicit
review, `CanonicalisationManifest` records selected CSV kinds, canonical-to-source columns, units,
complete file checksums, source/draft/confirmation fingerprints, exclusions, and confirmation
provenance. Only applying that confirmed artifact to a complete metadata template creates an
ordinary `BundleManifest`; normal validation still gates canonical records.

The inference workflow remains plain-CSV-only. Independently authored manifests may explicitly
declare gzip-CSV or Parquet, and those representations then use the same column maps, units,
canonical records, availability, and provenance contract. See the
[tabular input guide](integration/tabular_formats.md).

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
- `duration_s` optional, positive when present
- `lanes_closed` optional, non-negative when present
- `demand_multiplier` optional, positive when present
- `vehicles_involved` list, empty when not supplied

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

Task-latency P50/P95/P99 results also carry the percentile fraction, method,
`linear-rank-n-minus-1-v1` method version, valid sample count, and configured minimum sample size.
Unavailable percentile results retain the same metadata so missing and insufficient evidence are
distinguishable without treating either state as zero.

## Windowed Metric Artifact

`WindowedMetricSeries` is a separate versioned view over canonical tables; it does not alter raw
inputs, canonical records, or the whole-run collection. `WindowedMetricConfig` records width,
alignment origin, optional explicit range, partial-edge policy, empty-window policy, and a request
bound. Each `MetricWindow` records aligned and effective half-open `[start,end)` bounds,
requested-range coverage, and partial status. Each included `WindowMetricSlice` records all table
source counts plus an ordinary `MetricCollection` whose results have `time_window` scope.

Table anchors are tasks by `arrival_time_s`, trips by `departure_time_s`, and infrastructure,
vehicles, traffic, and incidents by `timestamp_s`. The anchor-policy version and fields travel in
the series. Empty included windows keep metrics unavailable; excluded partial windows have a null
collection. See [Time-windowed metrics](time_windowed_metrics.md).

Rejected validation reports produce `invalid` metric values rather than computed numbers.

## TaskEnergyContract

`BundleManifest.energy_contract` is optional and versioned separately from canonical rows. Its
v1.0 form confirms that `energy_j` is one finite, non-negative per-task total-energy value in
joules and declares the exact per-task, completed-task, and energy-delay eligibility rules. The
tasks file must also declare `energy_j: J`. The semantic-contract fingerprint travels with energy
metrics, comparisons, EvidencePacks, reports, and provenance.

Without this contract, canonical energy-family metrics remain unavailable even if an energy-like
column exists. This keeps a unit label from silently establishing quantity or denominator meaning.

## OperationalFairnessPolicy

`OperationalFairnessPolicy` is a strict, independently fingerprinted v1.0 calculation policy. It
does not add source attributes to the bundle. Vehicle-tier membership requires an exact
task-to-vehicle join and a non-empty tier that remains stable inside the metric scope. RSU grouping
uses exact canonical `rsu_id`; an admitted load requires non-negative `active_tasks` and positive
`capacity`.

The policy requires two operational groups, at least two eligible observations in every observed
group, and complete coverage. Metric metadata records the policy fingerprint, exact group-set
fingerprint, support counts, eligible/population counts, coverage, and the non-protected group
interpretation. Missing or under-supported evidence remains unavailable. See
[ADR-019](decisions/ADR-019-evidence-gated-operational-fairness.md).

## TaskRsuTargetContract And VehicleSpatialGridContract

`BundleManifest.task_rsu_target_contract` independently declares that canonical `target_id` on a
V2I task is its observed executing RSU. It requires declared tasks/infrastructure files, required
mapped target/RSU columns, complete non-empty V2I target coverage, and an exact in-scope join to
canonical `rsu_id`. Non-V2I tasks are excluded from this outcome grouping.

`BundleManifest.vehicle_spatial_grid_contract` independently declares vehicle-position-at-
observation semantics, a named source coordinate frame, canonical metre units, fixed origin/cell
geometry, floor assignment, and complete finite x/y coverage. Speed coverage is recorded
separately and may be partial.

Both v1.0 contracts carry stable fingerprints. Metric outputs also carry exact target/cell-set
fingerprints, support, and coverage. Neither contract authorises task-position interpolation,
nearest-RSU assignment, geographic/CRS inference, or causal attribution. See
[ADR-020](decisions/ADR-020-contract-gated-spatial-and-rsu-breakdowns.md).

## Evidence Pack Contract

Evidence packs contain validation summaries, evidence availability, metric-engine configuration, metric collections, and provenance. They are the only supported input for deterministic diagnostic rules. They do not include LLM-rendered prose or XAI output.

## Related Documents

- [Run bundle specification](run_bundle_spec.md)
- [SUMO output adapter](integration/sumo_output_adapter.md)
- [Manifest inference wizard](integration/manifest_inference_wizard.md)
- [Declared tabular inputs](integration/tabular_formats.md)
- [Validation codes](validation_codes.md)
- [Metrics catalogue](metrics_catalogue.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [API reference](api_reference.md)
