# Run Bundle Specification

TrafficTwin Phase 2 supports import-first run bundles as either directories or ZIP archives.

Only `manifest.yaml` is universally required. `seed.yaml` is required in Phase 2 unless a future manifest version embeds a complete immutable seed snapshot or resolves a registered seed locally.

## Shape

```text
manifest.yaml
seed.yaml
tasks.csv
infra_state.csv
vehicle_state.csv
traffic_obs.csv
trips.csv
incidents.csv
```

All CSV files are optional at the bundle level. If a CSV file is present and should be used, it must be declared in `manifest.yaml`. A declared file that is missing is an import-blocking error.

## Manifest

The manifest is versioned with `schema_version: "1.0"` and contains:

- bundle metadata;
- run metadata;
- environment metadata;
- declared files;
- per-file schema version;
- required canonical columns;
- optional column mappings;
- explicit units;
- optional SHA-256 checksums;
- provenance.

Column mappings are canonical-field to source-column mappings. If no mapping is provided, the source column name must match the canonical field name.

## Unit Policy

TrafficTwin converts only explicitly declared supported units:

- time to seconds: `s`, `ms`, `min`;
- durations to milliseconds: `ms`, `s`;
- speed to metres per second: `m/s`, `mps`, `km/h`;
- data size to bytes: `bytes`, `B`, `KB`;
- energy: `J`;
- workload: `cycles`;
- utilisation: `fraction`.

Unknown units and unsupported conversions are validation errors. Units are never inferred silently.

## ZIP Security

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

## Partial Bundles

Missing optional files do not automatically reject a bundle. Instead, evidence availability marks the corresponding categories as `unavailable`, and the validation report records evidence limitation findings.
