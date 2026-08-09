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
- `E1` active (`pgrep` PID 69063) during measurements; serial execution only, no `pytest -n`.

## Test-order proof

- Fresh process A: `pytest tests/ui/test_portfolio_explorer.py::test_portfolio_explorer_has_exactly_one_title tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest -v` → first test (portfolio) timed out `RuntimeError: 10(s)` in cold run, second passed warm.
- Fresh process B: `pytest tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest tests/ui/test_portfolio_explorer.py::test_portfolio_explorer_has_exactly_one_title -v` → first test (demo flow) timed out, second passed.
- Conclusion: failure follows **first AppTest in cold process**, not a particular product test. PR #13 review correctly exonerated PR #13 (rehearsal `git diff` showed no change to `guided.py`/`home.py` AppTest implementation).

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

## Exact cold validation command

```bash
# Fresh Python process, no prior AppTest, first run gets 60s floor
bash -c 'cd /tmp/traffictwin-apptest-hardening && \
  /Users/akashx/AntigravityTest/traffictwin-v2-s3/.venv/bin/python -m pytest \
  tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest \
  -v --tb=short 2>&1 | tail -n 20'
# Expected: 1 passed, no RuntimeError, elapsed <60s but >10s cold is now allowed
```

A more expensive cold probe that starts a **new** `python -m pytest` subprocess and asserts first `timeout=10` passes is documented as `tests/test_apptest_cold_start_integration.py` (optional, not in every routine run).

## Integrated rehearsal result (rehearsal-only, not main)

- Base: `origin/main 73264bd` + `PR14 a9ec532` + `PR16 48ef3f4` + `hardening <sha>` + `PR13 rehearsal 2d7e85f`
- Rehearsal rebase: 8 commits, 0 manual conflicts (auto-merge)
- Navigation: 37 pages (`UiPage 37`, `V07 37`, `PAGE_RENDERERS 37`, unique)
- Cold 23-test boundary (portfolio 24 + nav 49 + consequence 87 + cross-page 4 + whatif 34 + home/guided where available) → **cold 23 passed, warm 23 passed** (once hardening applied; without hardening, first run timed out).
- This was **not a PR #13 product regression.**

## E1 and research

- `pgrep -fl 'eval_sumo_stage1_mc.py|run_e1_multidraw_physical_campaign' || true` checked dynamically before heavy runs; `E1` PID 69063 active, serial only, no SUMO/VEC, no interference with `/Users/akashx/AntigravityTest/diss`.

*Measurements are local engineering evidence on darwin; not universal guarantees.*
