# Run Bundle Specification

TrafficTwin supports import-first run bundles as either directories or ZIP archives. Generic
tables may be explicitly declared as plain CSV, gzip-compressed CSV, or flat scalar Parquet.

The public SUMO adapter is a separate v0.5 result-directory contract using `sumo-source.yaml`, not
a generic Phase 2 CSV bundle and not a ZIP input. See
[Eclipse SUMO Output Adapter](integration/sumo_output_adapter.md).

Only `manifest.yaml` is universally required. `seed.yaml` is required in Phase 2 unless a future manifest version embeds a complete immutable seed snapshot or resolves a registered seed locally.

## Shape

```text
manifest.yaml
seed.yaml
tasks.csv | tasks.csv.gz | tasks.parquet
infra_state.csv | infra_state.csv.gz | infra_state.parquet
vehicle_state.csv | vehicle_state.csv.gz | vehicle_state.parquet
traffic_obs.csv | traffic_obs.csv.gz | traffic_obs.parquet
trips.csv | trips.csv.gz | trips.parquet
incidents.csv | incidents.csv.gz | incidents.parquet
```

All source tables are optional at the bundle level. If a table is present and should be used, it
must be declared in `manifest.yaml`. A declared file that is missing is an import-blocking error.

The generic `incidents.csv` contract supports `incident_id`, `timestamp`, `incident_type`,
`location`, `severity`, `duration`, `lanes_closed`, `demand_multiplier`, and
`vehicles_involved`. The first three are required for generated bundles. Duration uses an explicit
declared time unit; `vehicles_involved` is a pipe-delimited list in CSV and becomes a canonical
string list.

## Manifest

The manifest is versioned with `schema_version: "1.0"` and contains:

- bundle metadata;
- run metadata;
- environment metadata;
- declared files;
- per-file schema version;
- explicit physical format (`csv`, the default, or `parquet`);
- optional outer `compression: gzip` for CSV;
- required canonical columns;
- optional column mappings;
- explicit units;
- optional SHA-256 checksums;
- provenance.

Column mappings are canonical-field to source-column mappings. If no mapping is provided, the source column name must match the canonical field name.

The manifest, not the filename suffix, is authoritative. Parquet outer compression is rejected;
normal compression inside a Parquet file is supported by the reader. Flat null, string, boolean,
integer, floating-point, and decimal Parquet columns are admitted. Nested, binary, and date/time
columns remain unsupported. Duplicate columns and files exceeding the 10,000,000-byte decoded
table limit are rejected. See [Declared tabular inputs](integration/tabular_formats.md).

An optional `canonicalisation` block records a mapping produced through the v0.5 inference wizard:

- inference version;
- complete source fingerprint;
- draft fingerprint;
- confirmation fingerprint;
- confirmation state (`accepted_suggestions` or `edited`);
- non-sensitive `confirmed_by` analyst/role label.

This block is generated only after explicit confirmation. A `ManifestInferenceDraft` is not a
bundle manifest and cannot be used for validation, metrics, or import. The wizard can apply a
confirmed mapping to a complete metadata template, but it does not invent bundle/run/environment
metadata or `seed.yaml`. See the
[manifest inference guide](integration/manifest_inference_wizard.md).

An optional `energy_contract` block admits the canonical task-energy metric family only when the
source semantics are explicit. The supported v1.0 contract is:

```yaml
energy_contract:
  schema_version: "1.0"
  quantity: per_task_total_energy
  canonical_energy_unit: J
  observation_level: one_value_per_task_record
  per_task_eligibility: finite_non_negative_energy
  per_completed_eligibility: completed_and_finite_non_negative_energy
  energy_delay_eligibility: completed_with_finite_non_negative_energy_and_latency
  canonical_delay_unit: ms
```

The tasks declaration must also map `energy_j` and declare `units.energy_j: J`. Without this
contract, energy metrics remain unavailable even when an energy-like column exists. Negative
energy is rejected; missing energy remains missing rather than becoming zero. Comparisons require
the exact same semantic-contract fingerprint on both runs. The contract does not make aggregate
source energy, power, battery state, or per-arrival energy equivalent to per-task total energy.

Optional `task_rsu_target_contract` and `vehicle_spatial_grid_contract` blocks independently admit
the two `MET-05` paths. The target contract fixes V2I `target_id` as the observed executing RSU and
requires mapped `target_id`/`rsu_id` columns to be required plus complete exact row joins. The grid
contract fixes position-at-observation semantics, a named source frame, metre units, origin/cell
geometry, floor assignment, and complete finite vehicle x/y. The vehicle declaration must require
x/y and declare `units.x: m` and `units.y: m`.

These blocks do not infer targets, task positions, nearest RSUs, routes, CRS/geography, or
causality. Without the relevant block, canonical fields may still support source replay but the
corresponding metrics remain unavailable. See
[ADR-020](decisions/ADR-020-contract-gated-spatial-and-rsu-breakdowns.md).

An optional `synthetic_measurement_impairment` block is valid only for a synthetic execution/source
bundle created by the standalone generator. It embeds the complete EXP-03 configuration,
configuration/audit fingerprints, exactly reconciled field/dropout audits, and fixed synthetic/
not-calibrated/raw-unchanged declarations. Every referenced table must be declared. Missing,
extra, duplicate, unit/bound/clamp-inconsistent, fraction-inconsistent, or fingerprint-invalid
audits reject the manifest. This block never authorises impairment of imported raw evidence or an
external launch. See [Synthetic measurement noise and dropout](measurement_imperfections.md).

## Unit Policy

TrafficTwin converts only explicitly declared supported units:

- time to seconds: `s`, `ms`, `min`;
- durations to milliseconds: `ms`, `s`;
- speed to metres per second: `m/s`, `mps`, `km/h`;
- contracted vehicle x/y coordinates: `m` only;
- data size to bytes: `bytes`, `B`, `KB`;
- energy: `J`;
- workload: `cycles`;
- utilisation: `fraction`.

Unknown units and unsupported conversions are validation errors. Units are never inferred silently.

## Compressed and ZIP Security

Gzip decoding counts uncompressed bytes and stops at the generic table limit. Parquet metadata and
the decoded table are checked against the same limit. Original gzip/Parquet bytes remain unchanged
and are used for declared checksums and bundle fingerprints.

ZIP loading:

- rejects absolute paths;
- rejects `..` path traversal;
- rejects symlink entries;
- caps total uncompressed size;
- extracts only into a controlled temporary directory;
- cleans temporary files after validation/import.

Directory and ZIP bundles must produce equivalent validation and canonicalisation results.

## Import Idempotency

Accepted imports register:

- run metadata;
- bundle ID;
- source reference;
- bundle fingerprint;
- manifest JSON;
- validation report JSON.

Importing the same bundle ID with the same run ID and fingerprint is idempotent. Reusing a run ID for different bundle content is rejected.

The fingerprint identifies exact raw paths and bytes. Equivalent CSV, gzip-CSV, and Parquet
representations therefore have different raw fingerprints; equivalence is assessed at the
canonical/metric layer, not by collapsing evidence identity.

## Batch Validation And Import

An explicit set of bundle paths and/or glob patterns can be processed with `bundle batch-validate`
or `bundle batch-import`. Resolution is deterministic: paths are resolved, overlapping matches are
deduplicated, and unique candidates are sorted. The request is limited to 64 input references and
256 candidates; an over-limit request performs no import.

Batch import is failure-isolated, not all-or-nothing. Every accepted candidate uses the ordinary
single-bundle registry transaction. Invalid candidates do not reach the registry, while conflicts
and local failures are reported per candidate and later candidates continue. Exact idempotency and
identifier-conflict rules above remain unchanged. See the
[batch bundle import guide](integration/batch_bundle_import.md).

## Streaming Validation And Import

`bundle stream-validate` and `bundle stream-import` process one directory or ZIP bundle through
ordered row/decoded-byte-bounded chunks. They retain the same manifest, checksum, fingerprint,
unit, logical source-row, evidence, validation, and registry identity semantics. Exact duplicate
task and vehicle/RSU-reference checks use temporary disk-backed state across all chunks.

Chunks supplied to a Python consumer are provisional until the final report permits import.
Streaming registry import stores accepted metadata only and does not automatically materialise
canonical tables, metrics, EvidencePacks, or diagnostics. See the
[streaming guide](integration/streaming_canonicalisation.md).

## Partial Bundles

Missing optional files do not automatically reject a bundle. Instead, evidence availability marks the corresponding categories as `unavailable`, and the validation report records evidence limitation findings.

## Related Documents

- [Data contract](data_contract.md)
- [Validation codes](validation_codes.md)
- [Generic schema mapping](integration/randy_schema_mapping.md)
- [SUMO output adapter](integration/sumo_output_adapter.md)
- [Manifest inference wizard](integration/manifest_inference_wizard.md)
- [Declared tabular inputs](integration/tabular_formats.md)
- [Batch bundle import](integration/batch_bundle_import.md)
- [Chunked and streaming canonicalisation](integration/streaming_canonicalisation.md)
- [Security and privacy](security_and_privacy.md)
- [Reproducibility guide](reproducibility.md)
