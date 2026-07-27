# Appendix — Quality-gate snapshot

Generated 2026-07-27T17:44:40+00:00 by `uv run python scripts/generate_quality_snapshot.py`.

Every number below is printed beside the exact command that reproduces it. Nothing
here was retyped from a terminal, and no test was executed to collect it — the
suites are inventoried with `--collect-only`, never run.

## Gaps in this snapshot

- The working tree carried 4 uncommitted path(s) when this snapshot was taken, so the figures describe that tree rather than the named commit alone.

## Test inventory

| Measure | Value | Reproduce with |
|---|---|---|
| Unit tests | 2,765 collected | `uv run pytest tests/unit --collect-only -q` |
| UI tests | 476 collected | `uv run pytest tests/ui --collect-only -q` |
| Integration tests | 214 collected | `uv run pytest tests/integration --collect-only -q` |
| Golden tests | 63 collected | `uv run pytest tests/golden --collect-only -q` |
| All suites | 3,518 collected | `uv run pytest --collect-only -q` |

Collected, not passed: this is the number of tests the suite contains, which is an inventory rather than a result.

## Static gates

| Measure | Value | Reproduce with |
|---|---|---|
| Lint (ruff check) | clean — All checks passed! | `uv run ruff check src tests scripts` |
| Format (ruff format --check) | clean — 824 files already formatted | `uv run ruff format --check src tests scripts` |
| Strict type check | 797 source files checked | `uv run mypy src tests` |

Supplied by the operator from a run of the command beside it. A full type-check sweep is sustained compute and is not performed by this generator.

## Toolchain

| Measure | Value | Reproduce with |
|---|---|---|
| Python | Python 3.12.13 | `uv run python --version` |
| uv | uv 0.11.19 (Homebrew 2026-06-03 aarch64-apple-darwin) | `uv --version` |
| Ruff | ruff 0.15.22 | `uv run ruff --version` |
| mypy | mypy 2.3.0 (compiled: yes) | `uv run mypy --version` |
| pytest | pytest 9.1.1 | `uv run pytest --version` |

## Repository

| Measure | Value | Reproduce with |
|---|---|---|
| Commit | `49209fb25254c99a8138dd0345f0177356b45f40` | `git rev-parse HEAD` |
| Branch | claude/complete-v0.7 | `git rev-parse --abbrev-ref HEAD` |
| Working tree | dirty — 4 uncommitted path(s) | `git status --porcelain` |

## How to read this appendix

- **Collected is not passed.** The test-inventory rows report how many tests each
  suite contains. A suite result is a separate claim, made by running the suite.
- **The snapshot is of one commit.** If the repository row reports a dirty working
  tree, the figures describe that tree and not the named commit alone.
- **Nothing here is a scientific result.** These are software-quality gates for the
  implementation chapter; they say nothing about any measurement the system makes.
