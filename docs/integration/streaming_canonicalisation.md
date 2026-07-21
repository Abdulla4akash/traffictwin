# Chunked And Streaming Canonicalisation

TrafficTwin v0.5 `ING-05` is an opt-in, memory-bounded parser for large declared generic bundle
tables. It supports the same plain CSV, gzip-CSV, and flat scalar Parquet contract as ordinary
ingestion. It does not enable Randy/VEC or SUMO launch and it does not infer external schemas.

## When To Use It

Use ordinary `bundle validate` for normal inputs at or below the 10,000,000-byte decoded-table
limit. Use streaming when one declared table is larger, or when you want an explicit bounded
canonical chunk consumer. The streaming validator retains summaries and a validation report, not
all canonical records.

## CLI

Validate without retaining canonical rows:

```bash
traffictwin bundle stream-validate /path/to/bundle \
  --chunk-rows 1000 \
  --max-chunk-bytes 4000000 \
  --format json \
  --output build/stream-validation.json
```

Validate and register accepted bundle metadata:

```bash
traffictwin bundle stream-import /path/to/bundle \
  --registry .traffictwin/registry.sqlite \
  --chunk-rows 1000
```

Both commands also accept `--max-table-bytes` and `--max-bundle-bytes`. Rejected validation,
identifier conflicts, and invalid bound combinations return a non-zero exit status. Streaming
import preserves ordinary created/idempotent/conflict behavior and does not automatically compute
metrics, EvidencePacks, or diagnostics.

## Streamlit

Open **Bundle Import & Validation**, enable **Use chunked canonicalisation for a large bundle**,
choose the maximum rows per chunk, and select **Stream Validate** or **Stream Validate & Import**.
The page shows canonical counts, source-row counts, observed chunk bounds, the complete validation
report, and a JSON download. Unsupported SUMO/TOS streaming is not implied.

## Python API

For a summary-only validation:

```python
from traffictwin.ingestion import (
    StreamingCanonicalisationConfig,
    validate_bundle_streaming,
)

result = validate_bundle_streaming(
    "/path/to/bundle",
    config=StreamingCanonicalisationConfig(chunk_rows=2_000),
)
if not result.report.may_import:
    raise ValueError(result.report.to_json())
print(result.streaming.canonical_record_counts)
```

For a bounded consumer, process each chunk synchronously and do not retain it:

```python
from traffictwin.ingestion import CanonicalChunk, validate_bundle_streaming

def consume(chunk: CanonicalChunk) -> None:
    # Write to bounded downstream storage or update a deterministic accumulator.
    print(chunk.source_file, chunk.start_source_row, chunk.canonical_record_count)

result = validate_bundle_streaming("/path/to/bundle", consumer=consume)
# Chunks were provisional. Commit staged output only after this final gate.
if not result.report.may_import:
    discard_staged_output()
```

`collect_bundle_streaming(path)` returns ordinary `CanonicalTables` for exact equivalence checks or
existing metric workflows. Because it retains all rows, collected mode is deliberately not
memory-bounded.

## Guarantees And Limits

- Chunk size never changes accepted canonical records, evidence decisions, or validation findings.
- Duplicate task IDs and vehicle/RSU references are checked exactly through temporary disk-backed
  state, including across chunks and source files.
- Logical source rows remain stable across CSV, gzip-CSV, Parquet, and chunk sizes.
- Exact raw checksums and bundle fingerprints are unchanged.
- The reported decoded-byte value is a deterministic format-specific estimate, not whole-process
  memory. Consumer memory and report size are outside the parser bound.
- Do not modify source files while validation is running. Chunks remain provisional until the
  final report is accepted.
- A caller-consumer failure raises `StreamingConsumerError`; it is not misreported as a bad source
  bundle, and temporary reconciliation state is still cleaned.

Run the reproducible benchmark with:

```bash
uv run python scripts/benchmark_streaming_ingestion.py \
  --rows 75000 --chunk-rows 257,1024,4096
```

See [ADR-015](../decisions/ADR-015-memory-bounded-streaming-canonicalisation.md) and the
[recorded benchmark](../evaluation/streaming_ingestion_benchmark.md).
