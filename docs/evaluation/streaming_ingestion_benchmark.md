# Streaming Ingestion Implementation Benchmark

Status: reproducible local implementation measurement for v0.5 `ING-05`.

The benchmark generates a labelled synthetic run bundle with 75,000 unique task rows, validates
it ordinarily, then validates it in bounded streaming mode at three chunk sizes. It compares
canonical per-table SHA-256 digests, record counts, validation-report content, and evidence
availability. The temporary fixture is removed after the run.

Command run from the repository root on 20 July 2026:

```bash
uv run python scripts/benchmark_streaming_ingestion.py \
  --rows 75000 --chunk-rows 257,1024,4096
```

Environment and fixture:

- Python: 3.12.13
- platform: macOS 26.4.1, arm64
- generated raw source bytes: 5,030,354
- canonical task records: 75,000
- other canonical records: 4 infrastructure, 2 traffic, 2 trips, 0 vehicle, 0 incident

| Mode | Chunk rows | Runtime (s) | Peak traced bytes | Chunks | Max observed decoded bytes | Exact equivalence |
|---|---:|---:|---:|---:|---:|---|
| ordinary | n/a | 2.155129 | 159,406,849 | n/a | n/a | reference |
| streaming | 257 | 5.106264 | 2,113,760 | 295 | 40,694 | true |
| streaming | 1,024 | 5.193257 | 3,827,155 | 77 | 162,136 | true |
| streaming | 4,096 | 5.273125 | 15,015,813 | 22 | 648,536 | true |

Every streaming run reported canonical-digest, validation-report, evidence, and record-count
equivalence. This demonstrates the implementation acceptance case on one generated fixture: it is
not a city-scale throughput claim or evidence about Randy/VEC data.

Peak values come from Python `tracemalloc`; they do not capture every native PyArrow allocation or
total process RSS. Runtime includes the deliberate structural pre-pass, canonical pass, and exact
disk-backed global reconciliation. Re-run the script on target hardware and preserve its JSON when
making a performance claim.
