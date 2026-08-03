# Release Guide

TrafficTwin `0.7.0` is the current research-prototype package identity on `main`. It includes the
import-first analysis baseline, audited Randy/VEC integration, bounded Manchester source workflows,
the task-oriented UI and the additive Meeting 3 platform surfaces.

The immutable `v0.6.0` tag remains the frozen comparison baseline. Version `0.7.0` does not imply
production readiness, complete Manchester telemetry, public deployment or acceptance of a
capability whose evidence gate remains open. Consult [implementation status](implementation-status.md)
and the [Meeting 1–3 live feature-gap audit](meeting_1_2_3_live_feature_gap_audit.md) before making
an operational or scientific claim.

## Release status

- Package version: `0.7.0`
- Release label: `v0.7.0 research prototype`
- Licence: not yet specified
- Production status: research prototype; not production-ready
- Final `v0.7.0` Git tag: owner-authorised annotated tag at
  `e840be6c09ac4579e3604665110db2e3209fc7dd`
- GitHub Release and package publication: not created

The exact tag target passed the Python 3.11/3.12 branch and draft-PR matrices. The subsequent
tag-push run did not start a runner because GitHub reported an account payment/spending-limit
block; it was not a code or test failure and requires an owner billing/settings resolution before
that event can be rerun.

## Technical pre-release checks

Use the locked environment and the same commands as CI:

```bash
uv sync --locked --extra dev --extra vec-runner
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run python -m pytest --cov=traffictwin --cov-report=term-missing
uv run python scripts/generate_reference_docs.py
git diff --exit-code -- docs/reference/generated
uv run python scripts/check_markdown_links.py
uv run python scripts/verify_release.py
git diff --exit-code -- tests/fixtures examples
git diff --check
```

Run a standalone synthetic-demo smoke in a temporary directory:

```bash
release_smoke_root="$(mktemp -d)"
uv run traffictwin demo initialise "$release_smoke_root/demo"
uv run traffictwin synthetic verify "$release_smoke_root/demo"
uv run traffictwin provenance export "$release_smoke_root/demo/bundles/baseline" \
  --root-type metric --root-id task.completion.rate --format json \
  --output "$release_smoke_root/demo/exports/provenance.json"
uv run traffictwin report run "$release_smoke_root/demo/bundles/baseline" \
  --output "$release_smoke_root/demo/reports/run.md"
uv run traffictwin report full "$release_smoke_root/demo/bundles/stressed_demand" \
  --comparison-baseline "$release_smoke_root/demo/bundles/baseline" \
  --output "$release_smoke_root/demo/reports/full.html"
uv run traffictwin release stage-demo-site "$release_smoke_root/demo" \
  --output "$release_smoke_root/public"
```

These are technical checks. Expected unavailable provider, real-workspace, scientific and human
acceptance states must remain visible; do not “fix” them with invented inputs.

## Package build and clean installation

Build both distributions from the locked development environment:

```bash
uv run python -m build
```

This creates `dist/traffictwin-0.7.0-py3-none-any.whl` and
`dist/traffictwin-0.7.0.tar.gz`. Test the wheel without using the editable checkout:

```bash
wheel_smoke_root="$(mktemp -d)"
uv venv --python 3.12 "$wheel_smoke_root/venv"
uv pip install --python "$wheel_smoke_root/venv/bin/python" \
  dist/traffictwin-0.7.0-py3-none-any.whl
"$wheel_smoke_root/venv/bin/python" -c \
  "import traffictwin; assert traffictwin.__version__ == '0.7.0'"
"$wheel_smoke_root/venv/bin/traffictwin" synthetic presets
```

The GitHub Actions matrix repeats the build and clean-wheel smoke on Python 3.11 and 3.12.

## Owner-only publication actions

The owner-authorised `v0.7.0` tag already exists and must not be moved. Do not create another tag,
create a GitHub Release, upload to PyPI, choose a licence or deploy a public service from this guide
alone. Each remaining action requires separate explicit repository-owner authorisation after the
technical checks and the applicable licence, publication and evidence boundaries have been
reviewed. Commands for those irreversible publication actions remain intentionally omitted.

## Release checklist

- [ ] Working tree is clean and the intended release commit is reviewed.
- [ ] Locked dependency, formatting, lint, typing and full-suite gates pass.
- [ ] Generated references regenerate without tracked drift.
- [ ] Repository-local Markdown links resolve.
- [ ] Source and wheel distributions build, and the clean wheel smoke passes.
- [ ] Standalone demo/report/provenance/static-site smoke passes.
- [ ] Fixture directories remain byte-unchanged after validation.
- [ ] GitHub Actions passes on Python 3.11 and 3.12 for the intended commit.
- [ ] Expected unavailable product/provider/scientific states remain accurately documented.
- [ ] Reports contain no fabricated real-data, operational or production claims.
- [ ] No private credential, path, raw identifier or unapproved large data is committed.
- [ ] Licence and publication status remain explicit and have owner approval before publication.
- [ ] Synthetic site manifest reports `synthetic: true` and `live_data: false`.
- [ ] Private TOS supervisor-pack checksums pass when the authorised external package is available.
- [ ] No public TOS atlas is staged without recorded publication permission.
- [ ] `CITATION.cff` and any archive-specific authors, identifiers and dates are owner-reviewed.
- [ ] Every published research object passes `traffictwin archive verify`; raw embed/reference
      permission and licence are recorded, otherwise the raw artifact is excluded.
- [x] Final `v0.7.0` tag has explicit owner authority and resolves to the reviewed commit.
- [ ] GitHub Release, package upload and deployment each have separate explicit owner authority.

Related documents:

- [v0.7 housekeeping completion record](quality/v07_housekeeping_completion_20260803.md)
- [v0.7 main-branch release integration](quality/v07_main_release_integration_20260803.md)
- [v0.7 technical release-readiness audit](quality/v07_release_readiness_audit_20260802.md)
- [v0.7 local-input and handoff audit](quality/v07_local_input_and_handoff_audit_20260802.md)
- [Standalone demo](standalone_demo.md)
- [Testing strategy](testing_strategy.md)
- [Reproducibility](reproducibility.md)
- [Limitations and future work](limitations_and_future_work.md)
- [Deployment](deployment.md)
- [Supervisor and viva pack](supervisor_pack.md)
- [RO-Crate research objects and citation](research_objects.md)
