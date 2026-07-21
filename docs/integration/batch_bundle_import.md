# Batch Bundle Import

TrafficTwin v0.5 `ING-04` validates or imports an explicit set of directory/ZIP run bundles through
the ordinary bundle contract. It adds orchestration and reporting only; it does not change
validation, fingerprints, registry identity, metrics, or diagnostic rules.

## CLI Usage

Validate several explicit paths:

```bash
traffictwin bundle batch-validate \
  tests/fixtures/bundles/baseline_valid \
  tests/fixtures/bundles/variation_valid
```

Validate a glob. Quote it so TrafficTwin performs deterministic expansion and records the original
reference:

```bash
traffictwin bundle batch-validate 'data/runs/run-*' --format json
```

Import accepted candidates independently:

```bash
traffictwin bundle batch-import 'data/runs/*.zip' data/runs/manual-bundle \
  --registry data/registry/traffictwin.sqlite \
  --format json \
  --output build/batch-import.json
```

Supported output formats are `text`, `json`, and `csv`. JSON is the complete machine-readable
audit artifact. CSV contains one row per resolved candidate and therefore does not represent
unmatched-glob issues when no candidate row exists.

Exit code `0` means every explicit input completed. Exit code `1` means `partial` or `failed` and
does not imply that zero bundles were imported. Always inspect `created_count`, `idempotent_count`,
`rejected_count`, `conflict_count`, `failed_count`, and the per-bundle results.

## Streamlit Usage

Open **Bundle Import & Validation**, expand **Batch validate or import**, and enter one path or glob
per line. **Validate Batch** performs no registry mutation. **Import Accepted Batch** uses the
registry path shown above the expander. The page shows consolidated counts, input issues, ordered
per-bundle outcomes, and a JSON download.

Batch import registers bundle/run metadata only. It does not automatically compute or store every
bundle's metrics and EvidencePack; use the existing analysis commands/pages for those deliberate
downstream operations.

## Resolution Contract

- At most 64 non-empty path/glob references and 256 unique resolved candidates are admitted.
- `~` and recursive glob syntax are supported.
- Overlapping references are deduplicated by resolved path; `matched_by` preserves all references.
- Candidates run in lexicographic resolved-path order.
- An unmatched glob becomes `BATCH_GLOB_UNMATCHED`; matched neighbours still run.
- A missing literal is validated as one rejected bundle candidate.
- Exceeding an input or candidate limit rejects the request before any registry mutation.

## Import Outcomes

Each accepted candidate gets its own ordinary registry transaction:

- `created`: bundle/run metadata was newly registered;
- `idempotent`: the exact bundle identity was already registered;
- `rejected`: validation forbade import and the registry was not touched;
- `conflict`: an existing identifier has different identity/metadata;
- `failed`: a registry or local I/O failure affected this candidate;
- `not_requested`: validation-only request.

The consolidated status is `complete` when there are no issues, `partial` when successful and
unsuccessful outcomes coexist, and `failed` when no candidate succeeds.

## Python API

```python
from traffictwin.ingestion.batch import import_bundle_batch, validate_bundle_batch

validation = validate_bundle_batch(["data/runs/run-*", "data/manual.zip"])
summary = import_bundle_batch(
    ["data/runs/run-*", "data/manual.zip"],
    "data/registry/traffictwin.sqlite",
)
print(summary.to_json())
```

Do not publish an unreviewed summary: resolved `source` paths can contain local directory names.

## Local Benchmark

Reproduce the implementation benchmark with:

```bash
uv run python scripts/benchmark_batch_ingestion.py 'tests/fixtures/bundles/*' --repeat 5
```

The recorded result is in [Batch ingestion benchmark](../evaluation/batch_ingestion_benchmark.md).
It is a small local fixture benchmark, not evidence of city-scale simulator throughput.

See [ADR-014](../decisions/ADR-014-failure-isolated-batch-bundle-import.md) for the transaction and
failure-isolation decision.
