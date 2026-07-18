# Release Guide

TrafficTwin `0.1.0` is a standalone research prototype release candidate.

## Release Status

- Package version: `0.1.0`
- Release label: `v0.1.0 standalone prototype`
- Licence: not yet specified
- Production status: research prototype, not production-ready

## Pre-Release Checks

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=traffictwin --cov-report=term-missing
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
/tmp/tt-wheel-test/bin/python -m pip install dist/traffictwin-0.1.0-py3-none-any.whl
/tmp/tt-wheel-test/bin/traffictwin synthetic presets
```

## Git Tag Instructions

Only tag after quality gates pass:

```bash
git tag -a v0.1.0 -m "TrafficTwin v0.1.0 standalone prototype"
git push origin v0.1.0
```

## Release Checklist

- [ ] Working tree clean.
- [ ] Quality gates pass.
- [ ] Standalone workspace initialises.
- [ ] Streamlit dry-run command prints expected command.
- [ ] Reports contain no real-data claims.
- [ ] No private credentials or large data are committed.
- [ ] Licence status remains explicit.
- [ ] Synthetic Netlify site manifest reports `synthetic: true` and `live_data: false`.
- [ ] Private TOS supervisor pack checksums pass, when the external package is available.
- [ ] No public TOS atlas is staged without recorded publication permission.

Related documents:

- [Standalone demo](standalone_demo.md)
- [Testing strategy](testing_strategy.md)
- [Reproducibility](reproducibility.md)
- [Limitations and future work](limitations_and_future_work.md)
- [Deployment](deployment.md)
- [Supervisor and viva pack](supervisor_pack.md)
