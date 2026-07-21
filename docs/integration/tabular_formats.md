# Declared CSV, gzip-CSV, and Parquet Inputs

TrafficTwin `ING-03` extends the ordinary import-first run bundle. It does not add a new importer:
the existing bundle CLI, Streamlit page, metrics, diagnostics, and provenance workflows accept a
mix of declared plain CSV, gzip-compressed CSV, and Parquet files.

## Manifest declarations

Plain CSV remains backward compatible:

```yaml
files:
  tasks:
    path: tasks.csv
    format: csv       # optional because csv is the default
    required_columns: [task_id, vehicle_id, task_class, arrival_time, deadline_ms, decision, completed]
    units: {arrival_time: s, deadline_ms: ms}
```

For gzip-compressed CSV, declare both the CSV format and outer compression:

```yaml
files:
  tasks:
    path: tasks.csv.gz
    format: csv
    compression: gzip
    checksum_sha256: "<sha256 of the unchanged .gz bytes>"
    required_columns: [task_id, vehicle_id, task_class, arrival_time, deadline_ms, decision, completed]
    units: {arrival_time: s, deadline_ms: ms}
```

For Parquet:

```yaml
files:
  tasks:
    path: tasks.parquet
    format: parquet
    checksum_sha256: "<sha256 of the unchanged Parquet bytes>"
    required_columns: [task_id, vehicle_id, task_class, arrival_time, deadline_ms, decision, completed]
    units: {arrival_time: s, deadline_ms: ms}
```

`column_map`, `required`, schema version, checksum, and unit behavior are identical in all three
representations. A single bundle may mix them. TrafficTwin does not infer the declaration from the
suffix. The manifest-inference wizard remains plain-CSV-only.

## Supported Parquet values

The generic adapter admits flat columns containing null, string, boolean, integer, floating-point,
or decimal values. It rejects nested lists/structs, binary values, and date/time columns because
the existing canonical contract requires explicit flat mappings and numeric time units. Convert
such fields outside TrafficTwin only when their semantics are known, preserve the original source,
and record the preprocessing provenance.

The ordinary importer caps each decoded table at 10,000,000 bytes. Opt-in `ING-05` streaming keeps
that ordinary safeguard unchanged while admitting larger explicitly bounded tables through the
same format contract. See [chunked and streaming canonicalisation](streaming_canonicalisation.md).

## Run it

No new command is needed:

```bash
traffictwin bundle validate /path/to/bundle
traffictwin bundle inspect /path/to/bundle
traffictwin metrics compute /path/to/bundle
traffictwin provenance source /path/to/bundle tasks.parquet 2
traffictwin bundle import /path/to/bundle --registry .traffictwin/registry.sqlite
```

In Streamlit, open **Bundle Import & Validation**, enter the directory or ZIP path, and review the
declared `format` and `compression` columns before importing.

## Identity and provenance

Checksums and the bundle fingerprint cover exact raw bytes. Recompressing a CSV or converting it to
Parquet therefore creates a different raw bundle fingerprint even when the decoded rows are the
same. This is intentional: raw evidence must not be collapsed. Equivalent representations are
tested by comparing canonical evidence and deterministic metric outputs.

For all three formats, the first data record has provenance locator `source_row: 2`; this is a
logical tabular-record locator, not a claim that Parquet has text line numbers. Source previews
show decoded scalar values, the declared format/compression, canonical values, and matching
validation findings.

See [ADR-013](../decisions/ADR-013-declared-tabular-formats-and-raw-identity.md) for the complete
decision.
