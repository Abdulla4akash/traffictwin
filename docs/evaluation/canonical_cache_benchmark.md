# Canonical-table Cache Implementation Benchmark

This is local `OPS-02` implementation evidence, not a simulator, city-scale, deployment, or
performance guarantee. It measures cold validation plus verified cache publication separately from
warm verified reuse.

## Fixture and Method

- Generated synthetic implementation fixture: 20,000 canonical task rows, four infrastructure
  rows, two traffic rows, two trip rows, and empty vehicle/incident tables.
- Initial raw bundle size: 1,327,021 bytes.
- Runtime: Python 3.12.13 on macOS 26.4.1 arm64.
- Memory: maximum Python allocation traced by `tracemalloc`, not whole-process RSS.
- Cold sample: one ordinary validation/canonicalisation plus six-Parquet publication and reread.
- Warm samples: five complete raw-fingerprint, checksum, Parquet-read, and Pydantic-validation hits.
- Invalidation: append one valid unique task row, inspect the old cache, then rebuild under the new
  key.
- Command:

```bash
.venv/bin/python scripts/benchmark_canonical_cache.py \
  --rows 20000 \
  --warm-repeat 5
```

## Measured Result

| Path | Runtime (s) | Peak Python-traced memory (bytes) | State |
|---|---:|---:|---|
| Cold validate + publish | 2.841765 | 129,041,732 | `written` |
| Warm hit 1 | 0.691980 | 42,832,349 | `hit` |
| Warm hit 2 | 0.684838 | 42,833,862 | `hit` |
| Warm hit 3 | 0.692257 | 42,833,897 | `hit` |
| Warm hit 4 | 0.684706 | 42,834,249 | `hit` |
| Warm hit 5 | 0.659921 | 42,834,061 | `hit` |
| Invalidated cold rebuild | 1.858087 | 104,831,745 | `written` |

The five-hit median was **0.684838 seconds** and the maximum warm traced memory was **42,834,249
bytes**. The cache contained 490,772 bytes after retaining both content-addressed keys.

## Correctness and Invalidation Checks

- every warm `BundleValidationResult` was exactly equal to the cold result;
- canonical counts were identical;
- raw file hashes were unchanged by cache publication and reuse;
- changing one raw task row produced `miss` before rebuild;
- the rebuilt entry used a different complete key;
- all warm results were verified hits, not assumed hits.

The invalidated rebuild ran after Python/PyArrow warm-up, so it must not be interpreted as a second
independent cold-start measurement. The benchmark establishes path separation, equivalence, and
invalidation behavior. It does not establish city-scale capacity, full-process memory, concurrent
writer performance, network-storage behavior, or a universal speed-up ratio. Question 22 in the
design specification remains open for dissertation and future representative workload sizes.
