# Reproducibility Guide

TrafficTwin is designed so that every reported number comes from deterministic code over explicit inputs.

## Environment Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The package supports Python 3.11+. The checked local environment for this documentation pass used Python 3.12.

## Deterministic Design Choices

- Scenario seeds are versioned YAML.
- Run bundles carry manifest, run, environment, file, unit, and provenance metadata.
- Validation runs before metrics.
- Metrics consume canonical records, not raw CSV text.
- Diagnostic rules consume EvidencePack objects, not raw data.
- Rules do not recompute metrics.
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
- RuleSet schema/ruleset: `1.0`

Run provenance includes run ID, experiment ID, seed ID, algorithm, checkpoint, random seed, environment name, environment version or commit where supplied, and source bundle fingerprint.

## Fingerprints

Bundle fingerprints are built from source files during validation. EvidencePack and DiagnosticReport fingerprints are based on canonical JSON with volatile generated timestamps normalised.

These fingerprints support reproducibility checks. They are not cryptographic signatures for adversarial security.

## Directory/ZIP Equivalence

The loader supports directory and ZIP bundles. Tests check equivalent validation/canonicalisation for ZIP and directory fixtures. ZIP loading rejects path traversal, absolute paths, and symlink entries.

## Synthetic Fixture Provenance

Repository fixtures under `tests/fixtures/` are synthetic and hand-auditable. They are suitable for:

- testing validation behavior;
- testing metric formulas;
- testing comparison output;
- testing diagnostic rule implementation.

They are not real Manchester, Randy/VEC, or SUMO results.

## Quality Gates

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=traffictwin --cov-report=term-missing
.venv/bin/python scripts/generate_reference_docs.py
```

Current verified snapshot from this documentation pass:

- tests: 119 passed;
- coverage: 76%.

## Reproduce The Baseline-Versus-Variation Demo

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

## Regenerate Evidence And Diagnostics

```bash
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output evidence-baseline.json
traffictwin diagnose evidence evidence-baseline.json
traffictwin diagnose report tests/fixtures/bundles/baseline_valid --format json
```

## Confirm Fixture Immutability

Before and after a run:

```bash
git status --short tests/fixtures examples/seeds
```

No fixture files should be modified by validation, metrics, evidence, diagnostics, CLI, or UI workflows.

## Known Sources Of Non-Determinism

- Real current time appears in non-golden CLI/UI report generation unless a fixed clock is injected.
- SQLite timestamps are generated at write time.
- Streamlit reruns are UI state events, not research computations.
- Future external simulators may introduce runtime and stochastic variability; they must record seeds and environment versions.

## External Integration Limitations

Phase 6A found no real Randy/VEC or SUMO artifacts. Real integration cannot be reproduced yet because no real schemas, units, commands, runtimes, or output samples are present.

Related documents:

- [Testing strategy](testing_strategy.md)
- [Run bundle specification](run_bundle_spec.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Integration decision](integration/phase6_decision.md)
