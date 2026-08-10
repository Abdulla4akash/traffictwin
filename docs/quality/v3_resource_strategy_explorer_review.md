# Resource Strategy Explorer Review — v3

Date: 2026-08-10
Feature branch: agent/product-v3-resource-strategy-explorer-v1
Base: origin/main

## Provenance

- **Old Claude-reviewed head (REQUEST CHANGES):** `e5111da400c729f18334ccade90c66646eb1a7a3`
  - Claude 1 found 6 defect classes: (1) pairwise interpretation missing magnitude/unit/descriptive qualifier (dangling f-string), (2) `synthetic_report_v1.json` invalid/non-service-produced (fingerprint mismatch, `<normalised>` sentinel), (3) JSON export not re-importable with real `generated_at`, (4) compatibility audit always `COMPATIBLE` (dead `INCOMPATIBLE`), (5) reserved metric values silently overridden, (6) dead constants/helpers and CSV/noqa cleanup.

- **Remediation head at task start:** `a0937174f7c8a1346d0d88337082cbe70c2d6163`
  - Contains remediation commit `015b48b927785fb9bcb30d498cc3e84b37340f94` —
    `fix(resource-strategy): address Muse 1 blockers 2-6 — compatible audit, reserved metrics, portable JSON, complete pairwise, golden verification, csv fidelity`
  - Prior commits: `b29ae60` navigation 37, `8bde790` review record, `4eff660` thin page, `6f429d7` domain model.

- **Live main at task start:** `3b7933dfecf05b579ff9c223729128109a933d93` (Manchester Evidence Hub merged via #15, Challenge bridge via #17, Portfolio Explorer via #13)
- **Starting main for this rebase:** `3b7933dfecf05b579ff9c223729128109a933d93`
- **Final integrated review head:** to be filled after final push (see `git rev-parse HEAD`)

## Closure Table — Claude Findings vs Remediation

| Claude Finding | Old Behavior (e5111da) | Current Production Fix (015b48b + HEAD) | Real Test | Mutation | Status |
|---|---|---|---|---|---|
| 1. Complete portable pairwise interpretation | Dangling `higher = f"{arm_b} mean higher..."` + stray `f"by ..."` → interpretation `"strongest_link mean higher than jsq "` without magnitude/unit/`descriptive only`; flowed to UI + Markdown | `src/traffictwin/experiments/resource_strategy.py:1120` now uses parenthesised f-strings: `"<B> mean higher than <A> by {mag:.6g} {unit}; descriptive only"` and `lower`/`equal`/`unavailable` variants, all self-contained with both arm IDs, direction, magnitude, unit, qualifier | `test_pairwise_interpretations_are_complete_and_self_qualifying` checks every pairwise for arm_a/arm_b/unit/`descriptive only`/magnitude/direction, zero case `equal` + qualifier, JSON/Markdown equality | M1 restore dangling f-string → `test_pairwise...` fails `unit ratio missing in '...mean higher than jsq '` | **CLOSED** |
| 2. Golden report must be real or absent | `synthetic_report_v1.json` had `generated_at="<normalised>"` (model invalid), fingerprint `b5fe...` mismatched content, interpretations differed | Regenerated via `build_resource_strategy_report(study)` with deterministic clock, `generated_at=null`, fingerprint `c07480af8e68dc...` verifies (`report_fingerprint == fingerprint()`), canonical payload deterministic, no sentinel, no absolute paths, `evidence_mode=synthetic_demonstration` preserved | `test_synthetic_report_golden_is_service_produced` validates model, fingerprint, `canonical_payload` equality, interpretation exactness, no sentinel/path | M2 tamper interpretation without fingerprint → `assert report_fingerprint == fingerprint()` fails `e819... != c074...` | **CLOSED** (retained+verified) |
| 3. Portable JSON round-trip | `to_json()` set `generated_at="<normalised>"` (datetime\|None field) → `model_validate_json` fails | `to_json()` now sets `generated_at=None` (portable, model-valid), `fingerprint()` via `_fingerprint(canonical_payload())` excludes wall clock | `test_report_json_roundtrip_with_populated_generated_at` builds with `clock=lambda: 2026-08-10`, round-trips, preserves identity/fingerprint, different clocks same identity, no sentinel | M3 restore `"<normalised>"` → `assert "<normalised>" not in js` fails | **CLOSED** |
| 4. Compatibility audit must actually fail | Always `COMPATIBLE` for every metric, `INCOMPATIBLE` dead | Central `EXPECTED_METRIC_CONTRACT` (20 keys) + `RESERVED_METRIC_KEYS`; `build_resource_strategy_report` evaluates version/unit/denominator vs expected, emits `INCOMPATIBLE` with `finding="incompatible: version..."`, pairwise for incompatible becomes `UNAVAILABLE` with `incompatible metric ...` interpretation | `test_compatibility_audit_real` covers A compatible, B version mismatch, C unit mismatch, D denominator mismatch, E not ordinary pairwise, F/G JSON/Markdown/UI | M4 force always `COMPATIBLE` → `assert comp.status == incompatible` fails `compatible == incompatible` | **CLOSED** |
| 5. Reserved metric authority | `rep.metrics["task.completion.rate_offered"]=0.0001` validated, builder silently ignored and recomputed 0.7 | `RESERVED_METRIC_KEYS` (20) central; `@model_validator` rejects any reserved key in `rep.metrics` with `reserved metric ... must not be supplied` | `test_reserved_metric_authority` A canonical computed, B/C conflicting offered/admitted rejected, D custom preserved, E offered/admitted distinct | M5 remove validator → `with pytest.raises(ValidationError)` fails `DID NOT RAISE` | **CLOSED** |
| 6. Dead constants/helpers | `RESOURCE_STRATEGY_METHOD_VERSION` unused, `MIN/MAX` defined but `Field(min_length=2,max_length=8)` hardcoded, `_fingerprint` unused | Removed `METHOD_VERSION`, `Field(min_length=MIN_STRATEGY_ARMS,max_length=MAX_STRATEGY_ARMS)`, `fingerprint()` routes through `_fingerprint(payload)` | `grep` audit: `MIN/MAX` at 39/399 used, `_fingerprint` at 783 used, `METHOD_VERSION` absent | M7 hardcode 2,8 → `grep min_length=MIN` fails (surviving but dead constant would be flagged by ruff) | **CLOSED** |
| Minor CSV | `f"{value:.12g}"` not round-trip safe | `_csv_num` now `repr(float(value))` lossless | `test_csv_numeric_fidelity` checks `2024123.123456789`, `0.12345678901234567`, `1.000...002` parse exact | M6 restore `:.12g` → `assert float(agg) == 0.12345678901234567` fails `0.123456789012 != 0.12345678901234566` | **CLOSED** |
| Minor noqa | Stale `# noqa: ANN401` on `load_...` and dangling B018 missed | Removed stale noqa, remaining 6 suppressions justified (`E501` line length, `ANN401` payload, `S110` try/except) | `uv run --with ruff ruff check` All checks passed, `format --check` passed | — | **CLOSED** |

## Residual Defects Discovered During Verification

- None in production logic. One mutation-induced file left-behind (`Field(min_length=2,max_length=8)` from M7 `set -e` abort) was detected via `git status` and restored before rebase. Navigation count stale (38→39) after Manchester merge was corrected via `tests/ui/test_navigation_v07.py` bump to 39.

## Files Changed During THIS Task (vs origin/main 3b7933d)

- `src/traffictwin/experiments/resource_strategy.py` (remediation already in 015b48b, preserved)
- `src/traffictwin/ui/app_pages/resource_strategy.py` (existing, preserved)
- `src/traffictwin/ui/pages/resource_strategy_explorer.py` (existing, preserved; uses `d.interpretation` directly)
- `src/traffictwin/ui/labels.py` (adds `RESOURCE_STRATEGY_EXPLORER`, preserves `MANCHESTER_EVIDENCE_HUB` + `PORTFOLIO_EXPLORER`)
- `src/traffictwin/ui/navigation.py` (preserves Manchester+Resource Strategy)
- `src/traffictwin/ui/navigation_v07.py` (preserves both)
- `src/traffictwin/ui/page_runtime.py` (preserves both)
- `tests/fixtures/resource_strategy/*` (verified golden)
- `tests/unit/test_resource_strategy.py` (27 tests, includes M1-M6 kill tests)
- `tests/unit/ui/test_resource_strategy_explorer_page.py` (9 tests)
- `tests/integration/test_resource_strategy_flow.py` (2 tests)
- `tests/ui/test_navigation_v07.py` (39-page inventory)
- `docs/quality/v3_resource_strategy_explorer_review.md` (this file)

No edits to `diss`, `vec_env`, `tos-data`, `e2b_outputs`, or PR 13-22 branches.

## Pairwise Examples (production output from synthetic_study_v1.json)

- Positive: `jsq_deadline_aware mean higher than jsq by 0.017 ratio; descriptive only` (task.completion.rate_offered, 0.6955 vs 0.6785)
- Negative: `strongest_link mean lower than jsq by 0.021 ratio; descriptive only` (same metric, 0.657 vs 0.678)
- Zero: `jsq_deadline_aware mean equal to jsq (difference 0 ratio); descriptive only` (task.completion.rate_offered tie, 0.6785 vs 0.6785)

All 30 pairwise rows contain both arm IDs, unit, `descriptive only`; non-zero contain magnitude/direction; zero contains `equal` + qualifier.

## JSON + Markdown + UI Equality Proof

- `uv run python /tmp/verify_pairwise.py` → `JSON preserves exact interpretation`, `Markdown preserves exact interpretation`, UI `pairwise_rows` uses `"interpretation": d.interpretation` directly (src/traffictwin/ui/pages/resource_strategy_explorer.py:381), no recomputation; page caption `Jain load-balance ... descriptive only` is supplemental, not sole qualifier.

## Golden Fixture Disposition

- **Retained+verified:** `tests/fixtures/resource_strategy/synthetic_report_v1.json` (42877 chars, `generated_at=null`, fingerprint `c07480af...`, canonical_payload equals regen, interpretations exact, no sentinel/path, label preserved, test pins via `canonical_payload` equality).

## Portable JSON Proof

- Build with `generated_at=2026-08-10T12:00:00+00:00` → `to_json` → `generated_at=null`, `model_validate_json` succeeds, `study_id`/`study_fingerprint`/`report_fingerprint` preserved, different clocks `2026` vs `2030` same `fingerprint()` and `canonical_payload`, no `<normalised>`.

## Compatibility Negative Examples

- `task.completion.rate_offered` version `2.0` → `incompatible: version '2.0' != expected '1.0'`
- Same key unit `wrong` → `incompatible: unit 'wrong' != expected 'ratio'`
- Same key denominator `admitted_tasks` vs `offered_tasks` → `incompatible: denominator 'admitted_tasks' != expected 'offered_tasks'`
- Incompatible metric pairwise becomes `UNAVAILABLE` with `incompatible metric ...; descriptive only`, not ordinary comparison; UI advanced view (`compatibility`/`incompatible` in page) and JSON/Markdown carry `incompatible`.

## Reserved Metric Negative Proof

- `ResourceStrategyReplication(..., metrics={"task.completion.rate_offered": 0.0001})` → `ValidationError: reserved metric 'task.completion.rate_offered' must not be supplied`
- Same for `task.completion.rate_admitted`; `custom.accuracy` preserved (`0.123456789`); offered/admitted denominators distinct (`rate_offered` ≠ `rate_admitted`).

## Arm-Bound / Dead-Helper Audit

- `rg` → `MIN_STRATEGY_ARMS=2` at 39, used at `Field(min_length=MIN...,max_length=MAX...)` 399; `MAX=8`; `METHOD_VERSION` absent; `def _fingerprint` at 783 used by both `Study.fingerprint()` and `Report.fingerprint()`.

## CSV Numeric Fidelity Proof

- `2024123.123456789 -> 2024123.123456789 -> equal True`
- `0.12345678901234566 -> 0.12345678901234566 -> equal True` (repr of `0.12345678901234567` is `0.12345678901234566` due to float64)
- `1.0000000000000002 -> 1.0000000000000002 -> equal True`
- CSV `custom.high` aggregate `0.12345678901234566` parses to same float; `repr` lossless.

## Test Power Audit

- All 27 unit tests assert production behavior (not counts): strict validation, unknown vs false, fingerprint determinism, arm ordering, metric identity, admission state, exclusion reasons, matched cohort, version mismatch, lifecycle conservation, denominator separation, admission guards, path exclusion, queue/cost, export matching, pairwise completeness, round-trip, compatibility real, reserved authority, CSV fidelity, golden pin.
- No `or True`, broad `or` escape, optional `if` assertions, fake fingerprint, local reimplementation without service call.
- UI tests (9) exercise empty, synthetic label, unadmitted refusal, export matching, no winner headline, queue view, limitations/provenance via AppTest with real service.
- Integration 2 tests exercise load→build→export flow.

## Exact Test Collection Counts

- `tests/unit/test_resource_strategy.py`: 27
- `tests/unit/ui/test_resource_strategy_explorer_page.py`: 9
- `tests/integration/test_resource_strategy_flow.py`: 2
- `tests/ui/test_navigation_v07.py`: 51 (after 39-page bump; 38 spec + 13 ancillary validation tests)
- Total focused: 89 passed

## Mutation Table M1–M7

| Mutation | Test | Exact Failure | Restored |
|---|---|---|---|
| M1 dangling f-string | `test_pairwise_interpretations_are_complete…` | `AssertionError: unit ratio missing in 'jsq_deadline_aware mean higher than jsq '` | yes |
| M2 golden tamper (interpretation) | `test_synthetic_report_golden_is_service_produced` | `AssertionError: 'c07480af...' == 'e81961af...' fingerprint mismatch` | yes |
| M3 `<normalised>` | `test_report_json_roundtrip…` | `AssertionError: '<normalised>' is contained here: ...` | yes |
| M4 always COMPATIBLE | `test_compatibility_audit_real` | `AssertionError: 'compatible' == 'incompatible'` | yes |
| M5 silent reserved override | `test_reserved_metric_authority` | `Failed: DID NOT RAISE ValidationError` | yes |
| M6 old `%.12g` | `test_csv_numeric_fidelity` | `AssertionError: 0.123456789012 == 0.12345678901234566` | yes |
| M7 hardcode 2,8 | N/A (dead constant audit via grep) | `min_length=MIN...` absent would be flagged; equivalent at runtime (same limits) | restored before rebase |

No non-equivalent survivor.

## Lint/Type/Lock/Diff Gates

- `uv run --with ruff ruff check src/traffictwin/experiments/resource_strategy.py src/traffictwin/ui/pages/resource_strategy_explorer.py tests/unit/test_resource_strategy.py tests/unit/ui/test_resource_strategy_explorer_page.py tests/integration/test_resource_strategy_flow.py` → **All checks passed**
- `uv run --with ruff ruff format --check` → **5 files already formatted** (after fixes)
- `uv run --with mypy mypy src/traffictwin/experiments/resource_strategy.py src/traffictwin/ui/pages/resource_strategy_explorer.py --ignore-missing-imports` → **Success**
- `uv lock --check` → **Resolved 91 packages**
- `git diff --check` → **no trailing whitespace/conflict markers**

Ruff B018 reason: old dangling `f"by ..."` was a string expression at module scope inside a function body but not assigned; current ruff with `B018` would flag `Unnecessary expression` but old branch's `ruff check` scope at e5111da was via `uv run --with ruff ruff check src/traffictwin/experiments/resource_strategy.py` (single file) and that file at that time did not have `B018` enabled in `pyproject.toml` `select`? Actually current `pyproject.toml` has `select = ["E","F","I","UP","B"]` includes `B`, but the old file's line `f"by {mean_diff}..."` was on next line indented same as `higher =` but without backslash, so it was parsed as a separate expression statement — B018 should have fired, but the CI at e5111da used `ruff check` without `--select B`? Current verification shows `rg` would have caught; historical miss likely due to `uv run --with ruff ruff check` vs `uv run --no-sync ruff check` missing binary (as observed this task: `Failed to spawn ruff` without `--with`). No speculation beyond config.

## Re-proof of Sound Properties

- A lifecycle conservation 8 relationships all fail closed (offered≠admitted+rejected etc.)
- B matched cohort = intersection minus excluded (synthetic: 4 matched, 1 excluded RSU_OUTAGE)
- C declared matched cohort cross-checked (`must not contain duplicates` sorted, `does not match computed`)
- D offered/admitted denominators separate typing/computation (`rate_offered` vs `rate_admitted`)
- E canonical identity excludes local path (provenance path does not affect fingerprint)
- F excludes `generated_at` (different clocks same fingerprint)
- G-J admission guards: UNADMITTED/REJECTED/PENDING/UNAVAILABLE all raise `UN..._EVIDENCE` before results
- K thin page: `build_resource_strategy_report` + `resource_strategy_report_to_*` only, no metric recomputation
- L-O no scheduler/RSU/VEC/SUMO/k8s import or execution in domain module
- P no winner/best/optimal without contract; all pairwise say `descriptive only`

## Live-Main Navigation Reconciliation

- Starting main: `3b7933dfecf05b579ff9c223729128109a933d93` (Manchester hub #15)
- Previous branch inventory: 38 pages (Portfolio+Resource Strategy, without Manchester)
- After `git rebase origin/main` (6 commits replayed): `335ab65` then `92d84a2`
- Integrated inventory: **39 pages** = `len(UiPage)==39==len(V07_PAGE_SPECS)` (HOME … RESOURCE_STRATEGY_EXPLORER + MANCHESTER_EVIDENCE_HUB + PORTFOLIO_EXPLORER)
- Overlap files handled: `docs/user_guide.md`, `labels.py`, `navigation.py`, `navigation_v07.py`, `page_runtime.py`, `test_navigation_v07.py`, `app_pages/*` — preserved both Manchester and Resource Strategy (verified `grep` shows 50:PORTFOLIO,51:MANCHESTER,59:RESOURCE_STRATEGY)
- Manchester files present: `src/traffictwin/ui/manchester_evidence_hub.py`, `src/traffictwin/ui/pages/manchester_evidence_hub.py`, `tests/ui/test_manchester_evidence_hub.py` etc.

## Dynamic Page Count

- `uv run python -c "from traffictwin.ui.labels import UiPage; print(len(UiPage))"` → **39**

## Force-with-Lease Details

- Pre-rebase remote: `a0937174f7c8a1346d0d88337082cbe70c2d6163`
- First push after 3b7933d rebase: `git push --force-with-lease=agent/product-v3-resource-strategy-explorer-v1:a093717 origin agent/product-v3-resource-strategy-explorer-v1` → new SHA `92d84a2` (and final doc bump)
- Final push with doc update uses same lease guard.

## E2 Process State

- Before task: `pgrep -fl` found `38493 e2_instrumentation_no_effect.py` and `38624 eval_sumo_stage1_mc.py` (JSQ candidate)
- After task: same two observed (no kill/restart/renice), `ps` shows ongoing `eval_sumo` at 100% CPU
- Tests run serially (`pytest ... -q` without `-n`), no SUMO/VEC/evaluator launch, no broad sweeps

## Proof Untouched

- `ls /Users/akashx/AntigravityTest/diss` not accessed; `vec_env`/`tos-data`/`e2b_outputs` not modified (only read `synthetic_study` fixture); `git status` shows only 14 feature files + navigation test.

## PR Body / Review Claims Corrected

- Old body claimed 81 tests at e5111da and 37 pages; new body (to be pushed) states 89 tests at final head, 39 pages, remediation commit 015b48b, final integrated SHA, separate old/new verification sections, no claim that old e5111da gates represent final.

## Remaining Limitations

- Synthetic only; admitted research evidence requires separate admission gate
- 4 matched replications; rep_005 excluded
- No learned selector, no Kubernetes, no E2 import
- Read-only inspection; no study creation workflow
- Some metrics unavailable where not supplied (typed `partial`)

## Exact-Head Review Brief

- **Final head to review:** `<FINAL_SHA>` (after doc push)
- Focus: strict validation, unknown vs false, deterministic fingerprint (excludes path/generated_at), offered/admitted separation, lifecycle conservation, matched-cohort exclusion guarantee, admission guards, pairwise `descriptive only` with magnitude/unit, golden fingerprint, portable JSON, real compatibility, reserved authority, thin page, no scheduler/RSU/VEC/SUMO/k8s, no causal/optimal claim, navigation 39, Manhattan hub preserved.

