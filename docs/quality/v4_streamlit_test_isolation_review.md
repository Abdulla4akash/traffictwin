# Streamlit/Pytest Isolation Guard — V4 Review

Date: 2026-08-10 (updated 2026-08-12, supersedes a3d0054, 43a525a, f518549, 9227e55, f0c24a8)
Branch: agent/platform-streamlit-test-isolation-v1
Base: 7b1b0b55b399108b237f6e9a31a6747f4c15c81b (origin/main Merge PR #30)
Reviewed heads:
- `2f81a64e8c51b3963ddaafbbfe8a6f3d9544933d` — blocking defect: passing polluter silently repaired (REQUEST CHANGES)
- `a3d005442bc2c9dbc41be4bc5f7c211cf111be51` — added reporting but introduced guard regressions: half-root `DeltaGeneratorSingleton`, skipped AppTest, non-biting reporting tests (REQUEST CHANGES)
- `43a525addc2be1fc1d78adf8b10a92265a79d00b` / `f51854917ad4d61bbf13219971ce7a208b4c72a7` — fixes blockers 1–8 but subprocess probes SIGSEGV 14/20 when parent had rendered AppTest
- `9227e554eedd7882bf78991917fe48c018b1e63a` — REQUEST CHANGES for B1 (subprocess SIGSEGV) and B2 (stale `68d50a4` not ancestor)
- `f0c24a8cfa832dfd16002b1b7091284686c8b5e5` — splits subprocess into dedicated file, fixes Q1–Q4, but **still SIGSEGV 7/12** for `cold-start + guard + subprocess` in same parent (fork-unsafe `subprocess.run` even without `start_new_session`)
- This remediation: commit following `f0c24a8cfa832dfd16002b1b7091284686c8b5e5` — uses `os.posix_spawn` (avoid fork-unsafe path), stable 20/20 for all stability matrix

Note: a file cannot reliably contain the exact SHA of the commit that contains itself. This document records reviewed parent history exactly and describes the new remediation as “the commit following `9227e55`”; the final new exact SHA is reported in the PR body/handoff, not as a self-referential literal.

## Objective

Eliminate order-dependent Streamlit/AppTest pollution where fake/stub `streamlit` or `FakeAppTest` leaks, with deterministic isolation, secret redaction, and visible passing-polluter warnings via the real guard.

## Root Cause (historical polluter)

`tests/unit/test_apptest_cold_start_hardening.py` helpers `_install_fake`/`_uninstall_fake` saved `sys.modules` trio then installed fake before uninstalling while on fake, desyncing `_installed` and stacking `_patched_run` wrappers → `AttributeError: 'FakeAppTest' object has no attribute '_tree'` / `has no attribute 'secrets'`. Guard initially absent, then at `a3d0054` snapshotted only 3 keys and popped root while leaving `streamlit.*` children → half-root `DeltaGeneratorSingleton instance already exists!`.

## State Leaked

`sys.modules["streamlit"]` (fake lacking `secrets`), `streamlit.testing*`, whole `streamlit.*` subtree when half-popped, `_installed` flag, `_has_run_first` (process-scoped), selected env, cwd, finder.

## Fix History (preserved)

1. **Polluter source fix** (`test_apptest_cold_start_hardening.py`) — snapshots `_installed/_original_run/_has_run_first` before `sys.modules` mutation, uninstalls while on real, installs fake after, restores correctly. Verified: guard-removed 4032 passed vs base 112 failed; with guard 4032 passed.

2. **Isolation utility** (`tests/support/streamlit_isolation.py`) — snapshots whole `streamlit.*` subtree by prefix, distinguishes fake (`not hasattr(root,"secrets")`) vs real, leaves innocent `import streamlit` alone, only pops fake. Robust per-component `first_exc` restore with explicit `OSError/ModuleNotFoundError` and no blanket `S110` suppression. `diagnose` only reports `sys_modules` when fake, `has_meaningful` initially `{"sys_modules","apptest_installed","cwd","finder_present"}` (later refined, see Q4).

3. **Guard** (`tests/conftest.py`) — `autouse` `before=capture(); yield; after=capture(); diagnose; if has_meaningful: warnings.warn(... nodeid ...) ; finally: restore`. Warns even when polluter passes, restores even when warning is error. Removed dead `streamlit_leak_report`/`pytest_runtest_makereport`.

4. **Regression at 43a525a/f518549** — Added 3 subprocess probes exercising real `autouse` fixture, process-scoped `has_run_first`, secret redaction, tautology fixes, `env` dropped from meaningful, whole-subtree handling. Subset: hardening 35 passed, study capsule 8 passed/0 skipped, polluter→victim 45 passed, guard 19 passed, unit/ui 243, ui 768, gates clean. **But** subprocess probes shared parent with in-process `AppTest` rendering → SIGSEGV `returncode -11` empty stdout/stderr in ~14/20 runs of `pytest -q tests/unit/test_streamlit_isolation_guard.py`. `capfd.disabled()/start_new_session/env scrub` did not fix. Document incorrectly claimed `68d50a4e204f855574186256a58e9cf64035897d` was current remediation, but `68d50a4` is not ancestor of `9227e55`, and exit -11 was not fixed.

## Remediation Following `f0c24a8` (this commit, supersedes 9227e55)

**B1 — subprocess proofs are still order-dependent after f0c24a8:** At `f0c24a8` the three probes were split into `test_streamlit_isolation_subprocess.py` but still used `subprocess.run(..., capture_output=True, start_new_session=True)` which on macOS uses `fork()` and SIGSEGVs after any in-process `AppTest.run()` in the same parent. Reviewer reproduced: `cold-start + guard + subprocess` in one pytest invocation → 5/12 passed, 7/12 failed with `returncode -11` empty stdout/stderr (all 5 subprocess proofs). Even `without_start_new_session` and without `stdin` still `-11`; only `os.posix_spawn` with explicit file actions avoids the unsafe fork path (verified: `posix_spawn` after AppTest prints `hello posix` correctly).

Fix: new `tests/support/subprocess_isolation.py` provides `posix_spawn_run()` using `os.posix_spawn(..., file_actions=[dup2 devnull→0, dup2 w_out→1, dup2 w_err→2], setsid=True)` and manual pipe read with `select`/`os.read` and timeout. `test_streamlit_isolation_subprocess.py` now imports `posix_spawn_run` and has `USE_POSIX_SPAWN = True` flag (for M-E). Probes are spawned via `posix_spawn_run(cmd, cwd, env, timeout=60)` instead of `subprocess.run`. This is the minimal spawn primitive that preserves stdout/stderr/exit-code evidence and is demonstrably stable after AppTest. Verified:

- subprocess alone 20/20,
- cold-start + subprocess 20/20,
- guard + subprocess 20/20,
- **cold-start + guard + subprocess (decisive) 20/20** (was 5/12 at f0c24a8),
- 12-run pre-fix vs 12-run post-fix recorded.

**B2 — review doc identity:** At `f0c24a8` doc still had stale `68d50a4` claim (not ancestor) and now also needed to record `f0c24a8` itself as REQUEST CHANGES for the remaining B1 three-file SIGSEGV. This doc now records `f0c24a8` as “splits but still fork-unsafe” and describes this remediation as “commit following `f0c24a8`” with exact parent `f0c24a8cfa832dfd16002b1b7091284686c8b5e5`.

**Q1 — remove non-biting reporting-only test:** Deletes `test_reporting_only_mutation_proves_warning_independent` (only proved `lambda: False` → `False`). Genuine proof is the real-fixture subprocess test (already covers reporting-only mutant via `warnings.warn` disable).

**Q2 — dead suppressions:** Removes `contextlib.suppress(KeyError)` wrapping `dict.pop(key, None)` (already supplies default, cannot raise). Keeps `suppress(ValueError)` for `list.remove` and `suppress(FileNotFoundError)` for `unlink` where actually possible. No broad `try/except`.

**Q3 — unused sentinels:** Deletes `_ABSENT = object()` / `_SENTINEL = _ABSENT` (now snapshot uses empty dict for absent).

**Q4 — legitimate first AppTest not a leak:** Removes `apptest_installed` from `has_meaningful_streamlit_leak` meaningful set (now `{"sys_modules","cwd","finder_present"}`). Legitimate `false→true` on first `AppTest.run` no longer triggers warning, even under `-W error::pytest.PytestWarning`. Fake still warns via `sys_modules` (always changes to fake). Added subprocess regression `test_legitimate_first_apptest_does_not_warn_under_error` (single legitimate `AppTest.from_file` + `run` under `-W error` → `1 passed`, no warning) and `test_fake_polluter_still_warns_under_error` proves fake still warns.

## Mutation Evidence (required, isolated)

### Mutation A — reporting only

- **Mutant:** `tests/conftest.py: _streamlit_isolation_guard` comment `warnings.warn(msg, pytest.PytestWarning, stacklevel=2)` → `# MUTANT`
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py::test_real_fixture_passing_polluter_emits_warning_and_victim_passes`
- **Before:** `1 passed`
- **After:** `FAILED` — `AssertionError: warning missing` (child probe `2 passed` but warning absent; restoration still works). Restore → `PASS`.

### Mutation B — restoration

- **Mutant:** `tests/support/streamlit_isolation.py: restore_streamlit_snapshot` → `return  # MUTANT: no-op`
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_guard.py::test_mutation_restore_actually_restores` (and subprocess polluter)
- **Before:** `PASS`
- **After:** `FAILED` — `assert hasattr(sys.modules["streamlit"], "secrets")` / `KeyError: 'streamlit'`. Restore → `PASS`.

### Mutation C — process-state rewind

- **Mutant:** `tests/support/streamlit_isolation.py: _restore_apptest` re-add `mod._has_run_first = snapshot.apptest_has_run_first`
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py::test_real_fixture_has_run_first_is_process_scoped` (and `test_apptest_wrapper_has_run_first_is_process_scoped`)
- **Before:** `PASS` (second child sees `True`)
- **After:** `FAILED` — `AssertionError: has_run_first must remain True`. Restore → `PASS`.

### Mutation D — legitimate AppTest false-positive

- **Mutant:** `tests/support/streamlit_isolation.py: has_meaningful_streamlit_leak` re-add `"apptest_installed"` to meaningful set
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py::test_legitimate_first_apptest_does_not_warn_under_error`
- **Before (correct):** `1 passed` under `-W error` (no warning)
- **After (mutant):** `FAILED` — `PytestWarning` turned into error (`Streamlit isolation leak detected after ... apptest_installed=...` under `-W error`). Restore → `PASS`.

## Suite Comparison (measured on remediation following `f0c24a8`)

| Suite | Command | Result |
|---|---|---|
| Hardening | `uv run pytest -q tests/unit/test_apptest_cold_start_hardening.py` | 35 passed, 0 failed, 0 skipped (1 warning `apptest_installed` only if Q4 not applied; after Q4, still 35 passed, warnings only for fake) |
| Study capsule | `uv run pytest -q -rs tests/ui/test_study_capsule_ui.py` | 8 passed, 0 skipped |
| Guard (ordinary) | `uv run pytest -q tests/unit/test_streamlit_isolation_guard.py` | ~14 passed (after moving 3 probes + Q1 removal) |
| Subprocess proofs | `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py` | 5 passed |
| Subprocess 20× | `for i in $(seq 1 20); do uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py || exit 1; done` | **20/20 stable** |
| **Three-file decisive** | `for i in $(seq 1 20); do uv run pytest -q tests/unit/test_apptest_cold_start_hardening.py tests/unit/test_streamlit_isolation_guard.py tests/unit/test_streamlit_isolation_subprocess.py || exit 1; done` | **20/20 stable** (was 5/12 at f0c24a8) |
| Polluter→victim | `uv run pytest -q tests/unit/test_apptest_cold_start_hardening.py tests/unit/ui/test_resource_strategy_explorer_page.py` | 45 passed |
| Unit/UI | `uv run pytest -q tests/unit/ui` | 243 passed |
| UI | `uv run pytest -q tests/ui` | 768 passed |
| Full unit (jax) | `uv run pytest -q tests/unit` | 2 collection errors `ModuleNotFoundError: jax` (pre-existing) |
| Gates | `ruff format --check`, `ruff check`, `mypy`, `uv lock --check`, `git diff --check` | All clean |

## Remaining Limitations

- Whole `streamlit.*` subtree by prefix; non-`streamlit` fakes must be allowlisted.
- Guard warns only for `sys_modules`/`cwd`/`finder` (fake); `apptest_installed` and `env` alone do not warn (diagnosed/restored but not leaked). `has_run_first` remains process-scoped.
- Restoration best-effort per-component with `first_exc`.

## Research Safety

Before/after `pgrep -fl 'e2-native|native-placement|eval_sumo|run_e1|analyze_e1|vec'` → no matches; no SUMO/VEC/evaluator, no parallel pytest, no writes to `diss`/`vec_env`/`tos-data`.

## Files Changed (this lane)

- `tests/support/streamlit_isolation.py` (Q2, Q3, Q4)
- `tests/conftest.py` (Q4 via isolation; no direct change needed if Q4 only in isolation)
- `tests/unit/test_streamlit_isolation_guard.py` (B1 split, Q1 removal)
- `tests/unit/test_streamlit_isolation_subprocess.py` (new, B1 isolation)
- `docs/quality/v4_streamlit_test_isolation_review.md` (this file, B2)

Fable-owned untouched: `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `tests/ui/test_navigation_v07.py`, `README.md`, `docs/user_guide.md`, `docs/ui_conventions.md`, `src/traffictwin/cli.py`.

## Evidence Captured

- At `9227e55`: `pytest -q test_streamlit_isolation_guard.py` flaky 14/20 `returncode -11` empty, subprocess probes affected; doc claimed `68d50a4` current and exit -11 fixed (false).
- After remediation: subprocess module 20/20 stable, guard ordinary stable, legitimate first AppTest under `-W error` passes, fake still warns.
