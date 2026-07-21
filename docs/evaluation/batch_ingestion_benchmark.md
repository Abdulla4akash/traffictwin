# Batch Ingestion Implementation Benchmark

Status: reproducible local implementation measurement for v0.5 `ING-04`.

This benchmark measures deterministic validation of the five repository bundle fixtures. It does
not measure simulator execution, production storage, network I/O, large-city datasets, or
`ING-05` streaming ingestion.

Command run from the repository root on 20 July 2026:

```bash
uv run python scripts/benchmark_batch_ingestion.py 'tests/fixtures/bundles/*' --repeat 5
```

Environment and fixture:

- Python: 3.12.13
- platform: macOS 26.4.1, arm64
- unique bundle candidates: 5
- total raw fixture bytes: 9,609
- accepted/rejected candidates: 3/2
- input issues: 0

Measured result:

- runtime samples (seconds): `0.039303`, `0.035070`, `0.035210`, `0.034859`, `0.034662`
- median runtime: `0.035070` seconds
- peak traced-memory samples (bytes): `1,092,623`, `1,077,506`, `1,077,119`, `1,076,882`,
  `1,076,551`
- maximum traced memory: `1,092,623` bytes
- sequential equivalence: `true`

`sequential_equivalence` compares the ordered batch projection—source, bundle/run identifiers,
fingerprint, status, import permission, and finding count—with independent calls to the ordinary
`validate_bundle` function for every resolved candidate. It does not claim that `tracemalloc`
captures all process or native-library memory.

Run the command again on the target deployment hardware and retain its JSON output when making a
performance claim. Filesystem caches, Python version, fixture composition, and host load can change
runtime and memory measurements.
