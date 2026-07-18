# Reproducibility Guide

TrafficTwin is designed so that every reported number comes from deterministic code over explicit inputs.

## Environment Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The package supports Python 3.11+. The checked local environment for this documentation pass used Python 3.12.

The complete dependency graph is committed in `uv.lock`:

```bash
uv sync --extra dev --extra tos
uv lock --check
```

## Deterministic Design Choices

- Scenario seeds are versioned YAML.
- Run bundles carry manifest, run, environment, file, unit, and provenance metadata.
- Validation runs before metrics.
- Metrics consume canonical records, not raw CSV text.
- Diagnostic rules consume EvidencePack objects, not raw data.
- Rules do not recompute metrics.
- Provenance traces consume existing validation, metric, EvidencePack, and DiagnosticReport objects;
  they do not recalculate results.
- Golden tests use fixed clocks or stable projections.
- JSON fingerprints normalise generated timestamps where implemented.

## Versions And Provenance

Current schema/config versions:

- Seed schema: `1.0`
- Run-bundle manifest schema: `1.0`
- File schema: `1.0`
- Metric version: `1.0`
- EvidencePack schema: `1.0`
- DiagnosticReport schema: `1.0`
- ProvenanceTrace schema: `1.0`
- RuleSet schema/ruleset: `1.0`

Run provenance includes run ID, experiment ID, seed ID, algorithm, checkpoint, random seed, environment name, environment version or commit where supplied, and source bundle fingerprint.

## Fingerprints

Bundle fingerprints are built from source files during validation. EvidencePack, DiagnosticReport,
and ProvenanceTrace fingerprints are based on canonical JSON with volatile generated timestamps
normalised.

These fingerprints support reproducibility checks. They are not cryptographic signatures for adversarial security.

## Directory/ZIP Equivalence

The loader supports directory and ZIP bundles. Tests check equivalent validation/canonicalisation for ZIP and directory fixtures. ZIP loading rejects path traversal, absolute paths, and symlink entries.

## Synthetic Fixture Provenance

Repository fixtures under `tests/fixtures/` are synthetic and hand-auditable. They are suitable for:

- testing validation behavior;
- testing metric formulas;
- testing comparison output;
- testing diagnostic rule implementation;
- testing provenance trace construction and source-row preview.

They are not real Manchester, Randy/VEC, or SUMO results.

## Quality Gates

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=traffictwin --cov-report=term-missing
uv lock --check
.venv/bin/python scripts/generate_reference_docs.py
.venv/bin/traffictwin demo initialise .demo --force
.venv/bin/traffictwin synthetic verify .demo
.venv/bin/traffictwin report full .demo/bundles/stressed_demand \
  --comparison-baseline .demo/bundles/baseline \
  --output .demo/reports/stressed_full.html
traffictwin release stage-demo-site .demo --output public
```

Current verified snapshot after the release, supervisor, and evaluation increment:

- tests: 206 passed;
- coverage: 78%.

## Reproduce The Baseline-Versus-Variation Demo

Standalone workspace:

```bash
traffictwin demo initialise .demo
traffictwin compare .demo/bundles/baseline .demo/bundles/stressed_demand
traffictwin diagnose bundle .demo/bundles/under_offloading
traffictwin diagnose evidence .demo/exports/trivial_multi_algorithm_evidence.json
```

Repository fixture path:

```bash
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin bundle validate tests/fixtures/bundles/variation_valid
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin metrics compute tests/fixtures/bundles/variation_valid
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
```

For UI:

```bash
streamlit run src/traffictwin/ui/app.py
```

Then follow [demo_checklist.md](demo_checklist.md).

The public static demonstration is reproduced from the same workspace:

```bash
traffictwin release stage-demo-site .demo --output public
```

`public/site-manifest.json` records synthetic/live/external-integration flags and page hashes.

## Regenerate Evidence And Diagnostics

```bash
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output evidence-baseline.json
traffictwin diagnose evidence evidence-baseline.json
traffictwin diagnose report tests/fixtures/bundles/baseline_valid --format json
```

## Regenerate Provenance Traces

```bash
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
traffictwin provenance rule tests/fixtures/bundles/variation_valid R2 --format json
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
traffictwin provenance export tests/fixtures/bundles/baseline_valid \
  --root-type metric \
  --root-id task.completion.rate \
  --format markdown \
  --output provenance-task-completion.md
```

## Confirm Fixture Immutability

Before and after a run:

```bash
git status --short tests/fixtures examples/seeds
```

No fixture files should be modified by validation, metrics, evidence, diagnostics, provenance, CLI,
or UI workflows.

## Known Sources Of Non-Determinism

- Real current time appears in non-golden CLI/UI report generation unless a fixed clock is injected.
- SQLite timestamps are generated at write time.
- Streamlit reruns are UI state events, not research computations.
- Future external simulators may introduce runtime and stochastic variability; they must record seeds and environment versions.

## External Integration Limitations

Phase 6A inspected Randy's separately supplied TOS Data result package and established reproducible
contracts for evaluation summaries, JSON reconciliation, NPZ key/shape validation, bounded
historical replay, and per-arrival samples. The package remains external to this repository.

Install the optional reader and validate a local checkout with:

```bash
python -m pip install -e ".[dev,tos]"
traffictwin integration tos validate ../external/tos-data --format json > tos-validation.json
traffictwin integration tos import ../external/tos-data \
  --registry data/registry/traffictwin-tos.sqlite
```

Reproducibility is tied to the source package Git commit, deterministic package fingerprint,
source row, engine version, actor reference, fleet seed, TrafficTwin source-metric version, and a
separate `vec_env` semantics commit. Source inspection now confirms trace units, task/action
semantics, RSU active-task/backlog meanings, and the evaluator CLI. Exact producer commits,
checkpoints, the instrumented writer, local runtime verification, persistent identity, physical
completion, and raw SUMO/trip outputs remain unavailable. Full canonical conversion and direct
execution therefore cannot yet be reproduced.

Related documents:

- [Testing strategy](testing_strategy.md)
- [Run bundle specification](run_bundle_spec.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Provenance model](provenance_model.md)
- [Integration decision](integration/phase6_decision.md)
