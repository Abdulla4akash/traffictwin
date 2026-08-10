# AppTest Cold-Start Timeout Contract

## Observed failure class

Claude 2 observed flaky `RuntimeError: AppTest script run timed out after 10(s)` in `tests/integration/test_ui_demo_flow.py` and similar AppTest suites. The failure was `RuntimeError` from `streamlit.testing.v1.AppTest.run(timeout=10)`, not `AssertionError` from test logic. Line `:483` (an `assert any(...)` in `test_home_starts_and_advances_guided_demo`) was never reached when the AppTest timed out; the test failed at `app.run(timeout=10)` before any assertion.

## RuntimeError vs AssertionError distinction

- `RuntimeError: AppTest script run timed out after 10(s)` — infrastructure: the Streamlit script did not finish within the requested `timeout`. No test assertion was evaluated.
- `AssertionError` — test logic: the AppTest completed but the asserted condition was false.
- Conflating `FAILED (exit 1)` with `PASSED (exit 0)` is invalid. Pytest exit code `0` means all collected tests passed; `1` means at least one failed. A timeout is always `exit 1`.

## Cold vs warm measurements (local engineering evidence, darwin, Python 3.13.5, 2026-08-09)

- Inventory: `grep -rn 'timeout\s*=\s*10' tests` → **98 occurrences** in **16 files** (59 in `tests/integration/test_ui_demo_flow.py` alone). No `tests/conftest.py` existed.
- Single AppTest `test_streamlit_app_starts_with_apptest` warm: `1 passed in 5.71s` (real 7.45s) — already >50% of the 10s budget after imports.
- First AppTest in a fresh pytest process (cold imports, `import streamlit`, `import traffictwin`) consistently measured **8–12s** wall-clock for `app.run(timeout=10)` on this machine, leaving no margin for the 10s budget. Second AppTest in the same process measured **3–5s** (imports cached).
- `E1` checked dynamically via `pgrep -fl` before heavy runs; serial execution only, no `pytest -n`.

## Test-order proof

- Fresh process A: `pytest tests/ui/test_portfolio_explorer.py::test_portfolio_explorer_has_exactly_one_title tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest -v` → first test (portfolio) timed out `RuntimeError: 10(s)` in cold run, second passed warm.
- Fresh process B: `pytest tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest tests/ui/test_portfolio_explorer.py::test_portfolio_explorer_has_exactly_one_title -v` → first test (demo flow) timed out, second passed.
- Conclusion: failure follows **first AppTest in cold process**, not a particular product test. This reflects shared first-cold import/startup overhead — whichever AppTest runs first may fail under a 10-second budget. PR #13 was not the cause of the rehearsal failure (rehearsal `git diff` showed no change to `guided.py`/`home.py` AppTest implementation, and the failure followed first-cold, not a specific product).

## Infrastructure root cause

`timeout=10` is a reasonable warm-run budget but insufficient for the first AppTest's cold import/startup cost (Streamlit + TrafficTwin import graph). No product bug, no test logic bug, no research/SUMO dependency.

## Selected first-run timeout policy

- **Cold floor:** `COLD_FLOOR_SECONDS = 60` (defensible: 6× normal budget, covers observed 12s cold + margin, not absurdly large).
- **First AppTest run in a pytest process:** `effective = max(requested, 60)`
- **Subsequent runs:** `effective = requested` (e.g., `10→10`, `25→25`, `80→80`)
- **Never reduced:** `effective >= requested` always.
- **No hidden warm-up AppTest** before the named test; the first *real* test remains the first AppTest execution, it simply gets an adequate budget.

## Why subsequent timeouts remain unchanged

Turning every `timeout=10` into `60` would hide genuine hangs (a later AppTest that truly hangs would stall 60s instead of 10s). The floor applies only once per pytest process, isolating import cost without weakening the suite's ability to detect real deadlocks.

## Actual installer architecture

- `tests/_apptest_runtime.py` owns the shipped behavior: `effective_timeout()`, `install_apptest_run_patch()`, `uninstall_apptest_run_patch()`, `reset_apptest_cold_state()`, `is_patched()`. Pure `effective_timeout` is independently unit-tested; `install` closes over the exact original `AppTest.run` at install time (wrapper never resolves mutable global `_original_run` at call time, so a captured reference survives `uninstall`) and `uninstall` restores via bookkeeping. Invariant: `_installed` is the single source of truth for idempotence.
- `tests/conftest.py` and root `conftest.py` orchestrate the installer, contain no second implementation, and never import Streamlit at module import. They install a `sys.meta_path` finder for `streamlit.testing.v1` that patches `AppTest.run` after `exec_module`, plus `pytest_collection_finish`/`pytest_runtest_setup` fallbacks for already-loaded cases, and restore at `pytest_sessionfinish`. The import hook does not import Streamlit for pure-unit collection.
- Tests import and execute the same installer used by conftest — no private copy. `tests/unit/test_apptest_cold_start_hardening.py` exercises the real wrapper over a fake `streamlit.testing.v1.AppTest` and verifies: first 10→60, second 10→10, later 25→25, first 90→90, never reduced, call count 1, args/kwargs preserved, return preserved, RuntimeError preserved, arbitrary exception preserved, idempotent, uninstall restores, reset gives new allowance, no hidden AppTest call during install, and captured-wrapper-after-uninstall/reinstall regressions. Breaking the real installer makes these fail.

## Lazy Streamlit proof

- **A.** Importing `tests/conftest.py` alone does not place `streamlit` in `sys.modules` (verified via fresh `python -c "import tests.conftest; assert 'streamlit' not in sys.modules"`).
- **B.** Collecting a pure-unit test (`tests/unit/test_whatif_pair.py`) with `pytest --collect-only -p no:cacheprovider` does not import Streamlit nor install the patch (verified via `pytest.main` in subprocess: `'streamlit' not in sys.modules and not is_patched()`).
- **C.** After `import importlib; importlib.import_module('streamlit.testing.v1')` post-conftest, `is_patched()` is True and `AppTest.run` has `_is_cold_patched` before any `run` call.
- **D.** `install_apptest_run_patch()` is idempotent — second call returns same `AppTest.run` object.
- **E.** `pytest_sessionfinish` removes the `sys.meta_path` finder and restores `AppTest.run` to the original.

## Fail-closed import behavior

`tests/conftest.py` imports `tests._apptest_runtime` at module import without `except ImportError: pass`. Only `ModuleNotFoundError` for `streamlit` (genuinely not installed) is tolerated, and only when the current invocation does not need Streamlit (pure-unit). A broken `tests/_apptest_runtime` (simulated `raise ImportError('simulated helper breakage')`) fails closed: a temporary copy of the repo with a broken helper and `pytest --collect-only` exits non-zero and surfaces the helper breakage. The test `test_broken_helper_import_fails_closed` proves this.

## Cold marker registration and explicit opt-in

`pyproject.toml` registers:

```toml
[tool.pytest.ini_options]
addopts = "-ra"
markers = ["cold_apptest: expensive genuine cold AppTest proof requiring fresh cache (run with --run-cold-apptest -m cold_apptest)"]
```

`conftest.py` (root and `tests/conftest.py`) implement explicit opt-in:

```python
def pytest_addoption(parser):
    parser.addoption("--run-cold-apptest", action="store_true", help="run expensive cold AppTest controls")

def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-cold-apptest"):
        return
    for item in items:
        if item.get_closest_marker("cold_apptest"):
            item.add_marker(pytest.mark.skip(reason="cold AppTest control requires --run-cold-apptest"))
```

By default all `cold_apptest` tests are skipped/deselected. Only `pytest --run-cold-apptest -m cold_apptest` (or plain `--run-cold-apptest`) may execute them. A caller-supplied `-m` expression cannot accidentally re-enable them — `not foo` still skips cold. Verified via tiny temporary marked tests in `tests/unit/test_apptest_cold_start_hardening.py`.

The old unregistered `slow` marker and global `addopts = "-m 'not cold_apptest'"` are removed.

## Genuinely cold proof and opportunistic evidence

Each control uses:

- unique empty `PYTHONPYCACHEPREFIX` (per-test `tmp_path / "pyc_..."`),
- `-p no:cacheprovider`,
- fresh `python -m pytest` subprocess,
- no preceding AppTest in that process,
- outer timeout 240s with full diagnostics on `TimeoutExpired` (command, stdout, stderr, elapsed, hardening enabled, pycache prefix).

Inner target identical: `tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest` (`app.run(timeout=10)`).

- **Negative control** (`--noconftest`, hardening disabled): expected `RuntimeError` timeout / non-zero exit when cold >10s.
- **Positive control** (hardening enabled): expected `1 passed`, no `RuntimeError`.

**Truth about evidence:** Deterministic installer/wrapper unit tests are the standing invariant. The cold negative control is an opportunistic environmental demonstration — `PYTHONPYCACHEPREFIX` and `-p no:cacheprovider` do **not** flush the OS page cache, so a negative control may legitimately skip on a warm machine. On this darwin machine one observed cold invocation **did** reproduce the timeout when hardening was disabled (`RuntimeError` after ~11s), while later warm OS-page-cache runs passed (<8s) and therefore skipped via `pytest.skip`. The positive control passed consistently (e.g., 9.33s with hardening). Do not claim every invocation reproduces the timeout; do not tie it specifically to PR #14.

## 23-test boundary

`tests/integration/test_ui_demo_flow.py` (19) + `tests/ui/test_cross_page_state.py` (4) = 23 tests.

```bash
PYTHONPATH=src:. python -m pytest tests/integration/test_ui_demo_flow.py tests/ui/test_cross_page_state.py -q
# cold: 23 passed in 29.97s
# warm (immediate rerun): 23 passed in 40.00s
```

Both cold and warm are green with the hardening (`PYTHONPATH` ensures the hardening worktree's `src` is used, not the `traffictwin-v2-s3` editable).

## Full sweep

```bash
PYTHONPATH=src:. python -m pytest tests/ui tests/unit/ui tests/integration -q
# 942 passed, 8 skipped in 160.22s
```

No monkeypatch distortion of unrelated AppTest behavior. Navigation remains 36 (main, 73264bd) — rehearsal with PR #13/PR #14/PR #16 is separate.

## Attribution

The evidence supports shared first-cold overhead (whichever AppTest runs first may fail under 10s), not a specific product or PR #14 branch. No claim is made that the current `agent/product-v2-home-guided-whatif` branch at `a9ec532` reproduces a cold timeout in isolation without genuine cold isolation; the invariant proof is the deterministic installer contract plus the two cold controls above. PR #13 was not the cause of the rehearsal timeout.

## E1 and research

`pgrep -fl 'eval_sumo_stage1_mc.py|run_e1_multidraw_physical_campaign' || true` checked dynamically before heavy runs; serial only, no SUMO/VEC, no interference with `diss`.

*Measurements are local engineering evidence on darwin; not universal guarantees.*
