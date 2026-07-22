# Release Guide

TrafficTwin `0.6.0` is a research prototype release candidate with import-first analysis,
audited Randy/VEC integration, and controlled source-specific VEC and SUMO execution.

## Release Status

- Package version: `0.6.0`
- Release label: `v0.6.0 research prototype`
- Licence: not yet specified
- Production status: research prototype, not production-ready

## Pre-Release Checks

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=traffictwin --cov-report=term-missing
.venv/bin/traffictwin doctor --format text
.venv/bin/traffictwin demo initialise .release-demo --force
.venv/bin/traffictwin synthetic verify .release-demo
.venv/bin/traffictwin report full .release-demo/bundles/stressed_demand \
  --comparison-baseline .release-demo/bundles/baseline \
  --output .release-demo/reports/full.html
.venv/bin/python scripts/verify_release.py
.venv/bin/python -m build
uv lock --check
```

## Package Build

Install build tooling through the development extra:

```bash
python -m pip install -e ".[dev]"
python -m build
```

This should create `dist/*.whl` and `dist/*.tar.gz`.

The committed `uv.lock` pins the complete dependency graph. Recreate a development environment with:

```bash
uv sync --extra dev --extra tos
```

## Clean Installation Smoke

Use a temporary virtual environment:

```bash
python3.12 -m venv /tmp/tt-wheel-test
/tmp/tt-wheel-test/bin/python -m pip install dist/traffictwin-0.6.0-py3-none-any.whl
/tmp/tt-wheel-test/bin/traffictwin synthetic presets
```

## Git Tag Instructions

Only tag after quality gates pass:

```bash
git tag -a v0.6.0 -m "TrafficTwin v0.6.0 research prototype"
git push origin v0.6.0
```

## Release Checklist

- [ ] Working tree clean.
- [ ] Quality gates pass.
- [ ] `traffictwin doctor` reports no blocked required checks for the release environment.
- [ ] Standalone workspace initialises.
- [ ] Streamlit dry-run command prints expected command.
- [ ] Reports contain no real-data claims.
- [ ] No private credentials or large data are committed.
- [ ] Licence status remains explicit.
- [ ] Synthetic Netlify site manifest reports `synthetic: true` and `live_data: false`.
- [ ] Private TOS supervisor pack checksums pass, when the external package is available.
- [ ] No public TOS atlas is staged without recorded publication permission.
- [ ] Repository `CITATION.cff` and any archive-specific authors/identifier/date are reviewed.
- [ ] Every release research object passes `traffictwin archive verify`; imported public raw
      embed/reference has recorded permission basis and licence, otherwise use `exclude`.

Related documents:

- [Standalone demo](standalone_demo.md)
- [Testing strategy](testing_strategy.md)
- [Reproducibility](reproducibility.md)
- [Limitations and future work](limitations_and_future_work.md)
- [Deployment](deployment.md)
- [Supervisor and viva pack](supervisor_pack.md)
- [RO-Crate research objects and citation](research_objects.md)
