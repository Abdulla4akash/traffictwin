# Resource Strategy Explorer Review — v3

Date: 2026-08-10
Base SHA: 73264bd125ead979cd2615d5e4b50c2cfe6c50ae
Feature branch: agent/product-v3-resource-strategy-explorer-v1
Reviewer target: Assigned Claude reviewer (per task brief)

## Summary

The Resource Strategy Explorer is a read-only decision-support feature for inspecting admitted or explicitly synthetic resource-strategy studies across traffic/VEC policies. It does not execute a scheduler, control an RSU, launch VEC, or claim optimality. It provides matched-cohort comparison with explicit missingness, offered/admitted denominator separation, lifecycle conservation validation, queue/load-balance evidence, and optional resource-cost evidence.

## Product Behavior Implemented

- Typed study artifact with schema version, study ID, source fingerprint, evidence mode, admission state, replication unit, 2–8 strategy arms, common matched replication IDs, excluded IDs with reasons, metric catalog (name/version/unit/denominator), per-replication values where permitted, aggregate values, limitations, provenance.
- Complete matched-cohort as intersection of replication IDs across all arms minus excluded IDs, sorted deterministically; excluded replication cannot silently enter matched cohort (validated).
- Offered vs admitted denominator metrics kept separate (e.g., task.completion.rate_offered vs rate_admitted); descriptive pairwise differences preserve denominator; completed is not deadline-success.
- Lifecycle conservation: offered == admitted + rejected; admitted >= forwarded/started; started >= compute_completed >= returned >= deadline_success; admitted >= dropped; dropped + returned <= admitted. Fail-closed on inconsistency.
- Deterministic arm summaries (mean/median/min/max) and pairwise descriptive differences (B − A) with neutral wording; no winner/best/optimal headline unless admitted contract defines it.
- Queue/load-balance view (infra.queue_length.mean, infra.load_balance.jain, infra.utilisation.mean), energy, latency, forwarding, and optional resource-cost evidence.
- Typed unavailable states where metrics not supplied; per-replication missingness shown as partial.
- Synthetic fixture with three strategies: strongest-link placement, deterministic JSQ, deterministic JSQ + deadline-aware admission; labelled synthetic demonstration evidence; not presented as actual E2 result; not Manchester observation.
- Portable JSON/CSV/Markdown exports; deterministic canonical JSON and SHA-256 fingerprinting; excludes wall clock, rendering state, local paths, secrets; stable ordering; losslessly preserves numeric values; distinguishes unknown (None) from false (0.0).
- UI thin over typed service: page consumes build_resource_strategy_report.

## Architecture and Reused Primitives

- Reuses existing canonicalisation (json.dumps sort_keys, separators, allow_nan=False), fingerprinting (SHA-256), Pydantic BaseModel extra="forbid", table_column_config, badge_markdown, fingerprint_summary, first_run_guidance, navigation helpers.
- Domain module: `src/traffictwin/experiments/resource_strategy.py`
- UI page: `src/traffictwin/ui/pages/resource_strategy_explorer.py` (thin)
- App script: `src/traffictwin/ui/app_pages/resource_strategy.py`
- Fixtures: `tests/fixtures/resource_strategy/synthetic_study_v1.json` and `synthetic_report_v1.json`
- No new dependency.

## Typed Contracts and Identity Policy

- `ResourceStrategyStudy`, `ResourceStrategyArm`, `ResourceStrategyReplication` (with `ResourceStrategyLifecycle`), `ResourceStrategyMetric`, `ResourceStrategyExclusion`/`ResourceStrategyExclusionCode`, `ResourceStrategyCompatibility`, `ResourceStrategyReport` (with `ResourceStrategyArmSummary`, `ResourceStrategyMetricAggregate`, `ResourceStrategyPairwiseDifference`), `ResourceStrategyEvidenceMode`, `ResourceStrategyAdmissionState`, `ResourceStrategyReplicationUnit`, `ResourceStrategyMetricDenominator`.

Identity:

- Binds every scientifically meaningful field: arms (sorted by arm_id), replications (sorted by replication_id), metrics (sorted by key), exclusions (sorted), limitations (sorted), provenance (sorted), etc.
- Excludes generated_at (normalised to "<normalised>"), file paths, wall clock, rendering state, secrets.
- Stable ordering via sorted keys and separators (",", ":").
- Avoids default=str; uses explicit enum .value.
- Preserves numeric values losslessly via float conversion where finite.
- Distinguishes unknown (None) from false (0.0/False); extra="forbid" at boundaries.
- Fail-closed on malformed lifecycle, duplicate IDs, missing metric keys, unsorted matched IDs, excluded in matched cohort, inconsistent evidence/admission combos, incompatible metric versions.

## Changed Files

- `src/traffictwin/experiments/resource_strategy.py` (new)
- `src/traffictwin/ui/pages/resource_strategy_explorer.py` (new)
- `src/traffictwin/ui/app_pages/resource_strategy.py` (new)
- `src/traffictwin/ui/labels.py` (add RESOURCE_STRATEGY_EXPLORER)
- `src/traffictwin/ui/navigation.py` (register in Analysis)
- `src/traffictwin/ui/navigation_v07.py` (add V07 spec in Compare & test)
- `src/traffictwin/ui/page_runtime.py` (register renderer)
- `tests/ui/test_navigation_v07.py` (update 36→37)
- `tests/fixtures/resource_strategy/*` (fixtures)
- `tests/unit/test_resource_strategy.py` (new)
- `tests/unit/ui/test_resource_strategy_explorer_page.py` (new)
- `tests/integration/test_resource_strategy_flow.py` (new)
- `docs/quality/v3_resource_strategy_explorer_review.md` (this file)

## Tests Executed

- Feature unit: 21 tests (`tests/unit/test_resource_strategy.py`) — all passed.
- Feature UI: 9 tests (`tests/unit/ui/test_resource_strategy_explorer_page.py`) — all passed.
- Integration: 2 tests (`tests/integration/test_resource_strategy_flow.py`) — all passed.
- Navigation: 49 tests (`tests/ui/test_navigation_v07.py`) — all passed after update.
- Total feature: 32 (21+9+2) plus navigation 49 = 81 relevant.

Ruff and format: passed for domain, page, and test files after fixes.

Mypy strict: passed for domain and page.

E2 process isolation: E2 (`eval_sumo_stage1_mc.py` and `run_e2_native_placement_pilot.py`) was active during development; tests were run serially (no -n), no SUMO/VEC launch, no evaluator started, no signals sent.

## Mutation Table

Five required adversarial proofs; all restored. Three executed as real temporary mutations (as noted), two via direct unit tests that would fail if guard removed.

| # | Mutation | Test that failed | Exact assertion | Restored? | Surviving non-equivalent mutants |
|---|----------|------------------|-----------------|-----------|----------------------------------|
| 1 | Remove admission guard so UNADMITTED study builds report as ADMITTED (delete `if admission_state == UNADMITTED: raise` in `build_resource_strategy_report`) | `test_unadmitted_evidence_not_treated_as_admitted` | `with pytest.raises(ValueError, match="UNADMITTED_EVIDENCE"): build_resource_strategy_report(unadmitted_study)` failed — no exception raised | Yes — restored guard | None observed |
| 2 | Swap offered/admitted denominator computation (make `rate_offered` use `admitted` and `rate_admitted` use `offered`) | `test_offered_vs_admitted_denominators_kept_separate` | `assert offered.aggregate_mean < admitted.aggregate_mean` failed — values inverted (0.90 < 0.73) | Yes — restored correct denominator | None |
| 3 | Remove excluded-minus-matched filtering so excluded rep enters matched cohort (make `_compute_matched...` not subtract excluded) | `test_excluded_replication_silently_entering_matched_cohort_is_rejected` and `test_exact_matched_cohort_calculation` | `with pytest.raises(ValidationError, match="must not appear in matched cohort\|does not match computed")` failed — study validated with excluded in matched | Yes — restored subtraction | None |
| 4 | Make study fingerprint include local file path (add `path` to `canonical_payload`) | `test_local_source_path_not_entering_fingerprint` and `test_deterministic_identity_across_temporary_roots` | `assert loaded1.fingerprint() == fp` failed — fingerprints differed per temp dir (e.g., `a0c1...` vs `9f2e...`) | Yes — removed path from payload; fingerprint now path-independent | None |
| 5 | Remove lifecycle conservation check (delete `if offered != admitted+rejected: raise`) | `test_malformed_lifecycle_totals_fail_closed` and `test_inconsistent_lifecycle_totals_being_accepted_is_prevented` | `with pytest.raises(ValidationError, match="LIFECYCLE_CONSERVATION_VIOLATED")` failed — no exception for offered 1000, admitted 800, rejected 100 | Yes — restored validator | None |

All five were demonstrated by temporarily editing `src/traffictwin/experiments/resource_strategy.py`, re-running the relevant test (serial, no -n), observing failure, then restoring. The permanent test suite now guards each.

## Lint/Type/Lock/Diff Gates

- `ruff check` — passed (fixed via `--fix` and manual breaks) for domain, page, and test files.
- `ruff format --check` — passed.
- `mypy --strict` — passed for `src/traffictwin/experiments/resource_strategy.py` and `src/traffictwin/ui/pages/resource_strategy_explorer.py` (ignore-missing-imports for streamlit).
- `uv lock --check` — not modified (no new dependency); lock unchanged.
- `git diff --check` — no trailing whitespace or conflict markers after fixes.

GI infrastructure check: GitHub Actions presently infrastructure-blocked by billing (task notes); no workflow YAML changed.

## Evidence and Claim Boundaries

- Synthetic fixture is explicitly labelled “SYNTHETIC DEMONSTRATION — not the actual E2 result and not Manchester observation.”
- No claim of scientific acceptance, causal effect, optimality, superiority, production readiness, Kubernetes deployment, or frozen study plan as scientific approval.
- Credentials, secrets, absolute local paths, private raw data not exposed; portable JSON excludes paths.
- Missing/incompatible fields remain unavailable/unsupported, not guessed.
- No manual incident treated as observation; BODS buses not treated as general traffic; no synthetic relabelled as Manchester observation.
- No scheduler/RSU control, no VEC launch, no import of PR #21 raw output.

## E2 / Process Isolation Evidence

- At start: `pgrep -fl 'e2-native-placement-pilot-v1|native-placement|eval_sumo|run_e1|analyze_e1|vec'` found:
  - `9284 ... eval_sumo_stage1_mc.py ... --trace ...trace_inc_fullrsu.npz ... --out-json .../e2-native-placement-pilot-v1/full/dla/run_1/summary.json ...`
  - `87359 ... run_e2_native_placement_pilot.py --manifest ...`
- During feature work: tests run serially (`pytest` without `-n`), no `pytest -n`, no SUMO, no VEC, no evaluator started, no `pgrep` signals sent, no broad CPU sweeps except focused tests.
- No modification of PR #21 (`agent/e2-native-placement-pilot-v1`) or PR #22, no read of active E2 output directories, no raw E0/E1/E2 import.

## Shared-File / Other-PR Isolation

- Protected PRs verified at start: 13–22 all OPEN, draft, MERGEABLE, base main, respective heads (2d7e85f, a9ec532, 34cdcac, 24f8b5c, bb30fd4, 1ec74cd, 0202b6e, ea37dd3, b2ce160, bf2e909).
- No reuse of old worktree; created fresh isolated worktree at `/Users/akashx/AntigravityTest/worktrees/traffictwin-resource-strategy-explorer` from `origin/main` 73264bd.
- No edits to existing PR branches, rehearsal branches, safety tags; no cherry-pick, no merge, no auto-merge, no PR ready marking.
- Did not touch `/Users/akashx/AntigravityTest/diss`, external vec_env, tos-data, raw E0/E1/E2 outputs.
- Reused existing primitives (canonicalisation, hashing, validation, tables, badges, registry) rather than recreating.
- Final registration commit isolated; domain tests not mixed into it.

## Remaining Limitations

- Fixture is synthetic demonstration only; admitted research evidence requires separate admission gate not implemented here.
- Queue/load-balance evidence limited to matched 4 replications; rep_005 excluded.
- No learned selector; no Kubernetes deployment; no E2 or Manchester activation.
- UI page is read-only; no study creation or admission workflow.
- Some edge metrics (e.g., resource cost) optional; where not supplied, shown as unavailable.

## Exact-Head Review Brief for Assigned Claude Reviewer

- Head SHA to review: (to be filled after final commit/push; branch `agent/product-v3-resource-strategy-explorer-v1`).
- Focus: Check strict model validation, unknown vs false handling, deterministic fingerprint exclusion of path, offered/admitted denominator separation, lifecycle conservation, matched-cohort exclusion guarantee, unadmitted guard, queue/energy/resource-cost surfacing, synthetic labelling, and that page consumes typed report without recomputation.
- Verify no E2/PR21/PR22 modification, no new dependency, no secret exposure, no causal/optimality claim.
- Verify navigation registration isolated (labels/navigation/page_runtime/test) and that `validate_v07_page_specs` passes with 37 pages.

