# VEC-06 / VEC-07 Preflight Diagnostic — Current Condition

## Why this investigation exists

Five VEC tests fail identically on `origin/main @ 73264bd125ead979cd2615d5e4b50c2cfe6c50ae` and `PR #20 @ ea37dd3` when run from the normal checkout layout where `../external/vec_env` is reachable:

* `tests/integration/test_vec_fcd_preprocessing.py::test_pinned_pipeline_is_deterministic_atomic_and_non_mutating`
* `tests/integration/test_vec_fcd_preprocessing.py::test_execution_refuses_existing_and_overlapping_destinations`
* `tests/integration/test_vec_runner.py::test_real_pinned_two_step_run_is_isolated_validated_and_non_mutating`
* `tests/integration/test_vec_runner.py::test_real_vec06_receipt_trace_is_admitted_by_vec07`
* `tests/integration/test_vec_interface.py::test_real_source_snapshot_is_read_only_and_ready_when_repositories_exist`

The failures are genuine `VEC-06 preflight is rejected` / `VEC-07 preflight is rejected` / `ready_for_exact_blob_access == False`, **not** missing external infrastructure and **not** caused by Compare.

## What Claude's `/tmp` sweep missed

A `/tmp` worktree changes the path topology:

```
# Production code pattern
ROOT = Path(__file__).parents[2]          # → traffictwin checkout root
VEC_REPO = (ROOT.parent / "external" / "vec_env").resolve()
```

| checkout location | `ROOT.parent` | `VEC_REPO` exists? | test outcome |
|---|---|---|---|
| `.../AntigravityTest/traffictwin-vec-main` | `.../AntigravityTest` | `external/vec_env` **exists** | exercises lane → `REJECTED` |
| `/tmp/traffictwin-XXXX` | `/tmp` | `/tmp/external/vec_env` **does not exist** | `pytest.skip("private external …")` → **skipped**, lane never exercised |

All five tests guard on `if not VEC_REPO.is_dir(): pytest.skip(...)`. In `/tmp` they skipped, so the lane appeared healthy.

## Current environment (redacted / logical identifiers)

| item | observed (redacted) |
|---|---|
| TrafficTwin HEAD | `73264bd` (`origin/main`) |
| VEC repo logical path | `external/vec_env` |
| VEC `HEAD` | `e984411` (`akash-traffictwin-discovery`) |
| VEC `origin/main` | `0f01f4d` |
| VEC pinned expected | `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` |
| VEC pinned blob reachable | `true` (`cat-file -e` 0, both `eval/build_trace.py` & `place_rsus_cover.py` hashes match) |
| VEC clean | `true` |
| `tos-data` logical path | `external/tos-data` |
| tos-data `HEAD` | `d27294e` (`main`) |
| tos-data `origin/main` | `a75bbdb` |
| tos-data pinned expected | `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff` |
| tos-data pinned blob reachable | `true` |
| tos-data clean | `true` |
| `VEC_HEAD` ∩ `origin/main` intersection (vec_env) | `0` commits (forced remote update; see below) |
| `TRAFFICTWIN_VEC_FRESH_RESULT_DIR` | unset |
| `TRAFFICTWIN_TOS_DATA_REPO` | unset |
| Python | `3.13.5` in checkout `.venv` |
| `jax` in this venv | `false` (`No module named 'jax'`) — E2 uses `e0_runtime/vec-jax-0.4.30` separately |
| `numpy / pyproj / sumolib` | `2.5.1 / 3.7.2 / 1.27.0` (V06 deps **pass**) |

History note: `vec_env` `origin/main` was previously at `068b4ea`; reflog shows `fetch --prune: forced-update 068b4ea → 0f01f4d`. Current pinned `068b4ea` is a child of `bb91d0b → e984411` and is **disjoint** from `0f01f4d` lineage (intersection 0). `tos-data` `f6c67ac` vs `a75bbdb` similarly disjoint. Both pinned commits remain locally reachable but no longer on `origin/main`.

## VEC-06 blockers (exact)

`preflight_vec_fcd(.../synthetic_micro, vec_env, request)` → `status: rejected` with findings:

| finding code | severity | message | contributing |
|---|---|---|---|
| `VEC_SOURCE_REF_MISMATCH` | `error` | `vec_env origin/main does not match the audited VEC-06 commit` | **blocking** |
| dependencies | `info` | `numpy 2.5.1 sumolib 1.27.0 ok` | non-blocking |
| inputs | `pass` | valid FCD/network (one-second, boundary ok) | non-blocking |

Diagnostic projection `diagnose_vec06(...)` → `vec06_ready: false`, checks:
`vec_env_clean: pass`, `vec_env_origin_pinned: fail REVISION_MISMATCH`, `vec_env_audited_blobs_available: pass`, `vec06_dependencies: pass`, `vec06_inputs: pass`, `fresh_result_dir_configured: info CONFIG_UNSET (not required)`.

## VEC-07 blockers (exact)

`preflight_vec_run(tos-data, vec_env, tos-data, VecRunRequest{trace_we_fullrsu, mappo_17dim})` → `status: rejected` with findings:

| code | severity | message |
|---|---|---|
| `VEC_SOURCE_REF_MISMATCH` | `error` | `vec_env origin/main does not identify the audited commit` |
| `VEC_SOURCE_REF_MISMATCH` | `error` | `tos-data origin/main does not identify the audited commit` |
| `VEC_RUNTIME_UNAVAILABLE` | `error` | `optional vec-runner dependencies are unavailable` (jax) |

Diagnostic `diagnose_vec07` → `vec07_ready: false`, checks: `vec_env_origin_pinned: fail REVISION_MISMATCH`, `tos-data_origin_pinned: fail REVISION_MISMATCH`, `vec07_runtime: unavailable JAX_RUNTIME_UNAVAILABLE`, plus `clean`/`blobs` pass, `inputs` pass, `fresh_result_dir: info`.

`inspect_vec_interface(vec_env, tos-data)` → snapshot `ready_for_exact_blob_access: false` for both repos, `audited_commit_available: true`, `origin != pinned`. Diagnostic `explain_vec_interface_snapshot` → same 8 checks plus `fresh_result_dir_configured: info`.

## Which are intended (fail-closed)

The `origin/main == pinned` gate is **intended**. Gate A / VEC-03 provenance requires execution against an exact reviewed commit. The mirror advancing (comment-only / provenance commits) is expected; local `origin/main` moving ahead does not automatically move the audited commit. **Keep rejected until an operator explicitly updates the pinned constants after review — do not weaken.** Classification: **A**.

## Which are environment / dependency debt

* **JAX absent in product `.venv`** → `VEC_RUNTIME_UNAVAILABLE`. The checkout's venv is minimal; the E2 pilot correctly uses a separate `e0_runtime/vec-jax-0.4.30` with `jax==0.4.30`. In a JAX-enabled environment, V07 would go from `REJECTED(3)` → `REJECTED(2)` (only the two `REVISION_MISMATCH` remain; JAX check would be `pass`). If only the repo mismatch were fixed, V07 would be `UNAVAILABLE(1)` (JAX only). **Not the root blocker.** Classification: **B**.

* `TRAFFICTWIN_VEC_FRESH_RESULT_DIR` unset is **not** a V06/V07 blocker; it is `INFO` (`CONFIG_UNSET`, `required:false`) used only by `admit_vec_fresh_run`. That chain correctly skips when unset.

## Which are actual defects (if any)

1. **Test masking (C).** `test_execution_refuses_existing_and_overlapping_destinations` expects `VecFcdPreprocessingError: must not already exist / must not overlap` from `_validate_destination`, but `preprocess_vec_fcd` validates `preflight` **before** destination. With a rejected preflight, destination validation is never reached, so the test fails with the wrong regex. Production order is correct (cheap preflight first); the test is brittle to a non-green preflight. The diagnostic now surfaces both concerns separately (`destination_absent`, `destination_non_overlapping`).

2. **Coarse `REJECTED` string (C).** `VEC-06 preflight is rejected` collapses three independent reasons into one string. Tooling had to re-parse `preflight.findings`. The new `VecPreflightDiagnostic` maps each finding to a stable `blocker_code` (`REVISION_MISMATCH`, `JAX_RUNTIME_UNAVAILABLE`, etc.) with `required` and `observed_summary` without absolute paths, reusing the authoritative preflight reports (no duplicated semantics, no writes).

3. **Naming clarity (C).** `ready_for_exact_blob_access` is `false` even though the pinned blob *is* locally reachable (`audited_commit_available:true`). `ready` conflates reachability with `origin==pinned`. Diagnostic now exposes all four fields (`clean`, `audited_commit_available`, `origin_pinned`, `ready`) individually.

No scientific-semantics mutation; no evidence fabrication.

## Safe next action (proposed hardening — already implemented on this branch)

*Do not* `git checkout` pinned commits or force-move `origin/main` in private clones.

Implemented on `agent/vec-preflight-diagnostic-v1` (from `origin/main`, no rebase of PR #14/#18/#20):

* **Typed diagnostic** `src/traffictwin/integration/vec_preflight_diagnostic.py` (`VecPreflightCheck`, `VecPreflightDiagnostic`, `explain_vec06_preflight`, `explain_vec07_preflight`, `explain_vec_interface_snapshot`, `diagnose_vec06/07`, `diagnose_destination`, `diagnose_current_environment`). Reuses `preflight_vec_fcd` / `preflight_vec_run` / `inspect_vec_interface`; performs no execution, no writes, no network, redacts absolute paths to logical locators (`vec_env`, `tos-data`, `{VEC_REPO}` in logs), uses stable `VecBlockerCode` vocabulary.

* **Hermetic unit tests** `tests/unit/test_vec_preflight_diagnostic.py` (12 tests, all with `tmp_path` fake repos):
  repo missing → `REPO_UNAVAILABLE`; wrong revision → `REVISION_MISMATCH`; blob missing → `BLOB_MISSING`; JAX absent → `JAX_RUNTIME_UNAVAILABLE`; fresh dir unset → `CONFIG_UNSET` (INFO, not blocking); destination exists → `DESTINATION_EXISTS`; overlap → `DESTINATION_OVERLAP`; all satisfied → no required failures; portability (no `/Users/` leak); non-mutation; fail-closed; informational non-blocker.

* **Real-env diagnostic test** `tests/integration/test_vec_preflight_diagnostic_real.py` (skips when `external/vec_env` absent, otherwise asserts diagnostic explains current `REVISION_MISMATCH` and `vec06_ready==vec07_ready==False`, never writes).

* This documentation file.

## Mutation proofs (on this branch)

| mutant | expectation | result |
|---|---|---|
| M1 diagnostic drops one real blocker (`REVISION_MISMATCH` filtered) | `blocker-set` test fails | verified — `test_repo_present_but_wrong_revision…` fails |
| M2 labels repo-missing as `JAX_RUNTIME_UNAVAILABLE` | exact blocker-code test fails | verified — `test_repo_missing…` asserts `REPO_UNAVAILABLE` |
| M3 absolute private path enters `observed_summary` / JSON | portability test fails | verified — `test_portability…` checks `"/Users/" not in` |
| M4 preflight mutates external destination (creates dir) | non-mutation test fails | verified — `test_diagnostic_does_not_mutate…` checks `HEAD` unchanged & `dest.exists()==False` |
| M5 makes `vec06_ready==True` when `REVISION_MISMATCH` remains | fail-closed test fails | verified — `test_fail_closed…` asserts `ready==False` |
| M6 makes `fresh_result_dir` (INFO) `required:true` and blocking | requirement-classification test fails | verified — `test_non_required…` asserts `required==False` |

Restored after each mutant. **MUTANT count: 0 for non-equivalent mutants.**

## Research & product isolation

* E2 pilot (`run_e2_native_placement_pilot.py`, `eval_sumo_stage1_mc.py`) still running (`pgrep` shows both); no `kill`/`renice`/`launch SUMO/VEC`; `diss`, `external/vec_env`, `external/tos-data`, `tos-data` not mutated (`git status --porcelain` clean).
* No `pip install` into external checkouts; no `SUMO`/`VEC` execution started.
* Branch is `agent/vec-preflight-diagnostic-v1` from `origin/main @ 73264bd`; PR #14 (`a9ec53…`), #18 (`1ec74c…`), #20 (`ea37dd…`) heads unchanged and remain `OPEN DRAFT`.
