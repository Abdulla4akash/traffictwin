# V3 Event-Aligned Analysis — Quality Review

**Feature branch:** `agent/product-v3-event-aligned-analysis-v1`
**Base:** `origin/main` at `3b7933dfecf05b579ff9c223729128109a933d93`
**Page:** `Event-Aligned Analysis` (`EVENT_ALIGNED_ANALYSIS`)
**Date:** 2026-08-10
**Remote before push:** `origin/agent/product-v3-event-aligned-analysis-v1` at `7fcf883b5e6b65a30146c4c2139b0de4c2f5e5d4`
**Head after fixes + reconciliation:** `7c9cddd5de3f7a5e29f7d93ff0a3a21d9f276d8d` (after reordering, fix before register)
**Claude re-review of 933cbdf:** REQUEST CHANGES (F2 bomb weak, F3 vacuous, new partial_count double+2 regression)
**New head after surgical fix:** `1025c6bf64c02f38102509f427e621e22ec96a40`

## 1. Product goal

Multi-run analysis that aligns compatible temporal evidence around a declared event anchor and compares before, during and after windows. Reuses the existing deterministic fixed-window metric engine; adds relative-event alignment, multi-run comparability, coverage accounting, and event-centred export. Does not become a second temporal-metrics implementation.

## 2. User journey

1. Select 2–8 compatible runs/bundles.
2. Select a supported metric (window-applicable, version/unit displayed).
3. Choose an event anchor from:
   - bundle-declared event (`bundle_declared_event`)
   - authored incident (`authored_incident`)
   - manual authored timestamp (`manual_authored_timestamp`)
4. Choose pre-event duration, event duration, post-event duration and bin width.
5. Preview exact half-open windows `[anchor - pre, anchor)`, `[anchor, anchor+event)`, `[anchor+event, anchor+event+post)`.
6. Build aligned analysis.
7. Inspect relative-time series and before/during/after summaries (mean/min/max/median over available bins; PARTIAL numeric values are included, status retained).
8. Inspect gaps, partial windows, exclusions and incompatible runs (reason codes).
9. Export deterministic JSON and tabular CSV.

Manual and incident anchors are labelled `Authored — ...`, never observed incidents.

## 3. Typed contracts and identity policy

| Model | Key fields |
|---|---|
| `EventAnchorKind` | `bundle_declared_event`, `authored_incident`, `manual_authored_timestamp`; all `is_authored==True`, label `Authored — ...` |
| `EventAnchor` | `kind`, `anchor_time_utc: datetime (aware, normalised to UTC)`, `source_label` (rejects `observed`), `provenance_detail`, `incident_id`, `bundle_id`, `run_id` |
| `EventAlignedWindowSpec` | `pre/event/post_duration_s`, `bin_width_s`, `metric_key`, `metric_version`, `metric_unit`, `canonical_time_basis="utc_bundle_created_at_offset_v1"`, `bin_boundary="[start,end)"`, `max_bins` (default 10k, 1–100k), `total_bins()` |
| `EventAlignedMetricPoint` | `run_id`, `phase`, `bin_index`, `relative_start/end_s`, `absolute_window_start/end_utc` (aware UTC), `coverage_state` (`empty|partial|complete`), `coverage_fraction`, `source_record_counts`, `metric_key/version/unit`, `status`, `value`, `reason_codes` |
| `EventAlignedPhaseSummary` | per-run/phase `bin_count`, `available/empty/partial_count`, `mean/min/max/median` (mean over available+partial) |
| `EventAlignedRun` | `run_id`, `bundle_id/fingerprint`, `anchor`, `time_coverage_s`, warnings |
| `ExcludedRun` | `run_id`, `reason_code/detail`, optional anchor (`INVALID_TIME_BASIS`, `INSUFFICIENT_TEMPORAL_RANGE`, `METRIC_NOT_WINDOW_APPLICABLE`) |
| `PairwiseDelta` | `baseline/variation_run_id`, `phase`, `baseline/variation_mean`, `absolute/relative_difference`, `description` (non-causal validator) |
| `EventAlignedReport` | `spec`, `accepted/excluded_runs`, `metric_points`, `phase_summaries`, `pairwise_deltas`, `warnings`, `limitations`, `created_at_utc`, `fingerprint`, `canonical_dict()`, `to_portable_dict()` |

**Canonical time basis:** `utc_bundle_created_at_offset_v1` — canonical record timestamps (`arrival_time_s`, `timestamp_s`, `departure_time_s`) are seconds offset from `manifest.bundle.created_at` (UTC). Anchor UTC minus `created_at` yields relative seconds; bins are `Decimal`-deterministic half-open intervals. Local display timezone is presentation-only; portable report stores relative offsets plus canonical UTC anchor identity. Naive `bundle.created_at` is rejected (`INVALID_TIME_BASIS`), no 1970 fallback.

**Fingerprint:** `sha256(canonical_json)` where `canonical_json` is `sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False` over sorted `accepted_runs` (by `run_id`), `excluded_runs` (by `run_id`), `metric_points` (by `run_id,bin_index`), `phase_summaries` (by `run_id,phase`), `pairwise_deltas` (by `baseline,variation,phase`), `warnings/limitations` sorted, `spec.canonical_dict()`. Excludes `created_at_utc`, wall clock, rendering state, local absolute paths, secrets. Preserves numeric values losslessly (`Decimal` via `str`), distinguishes `unknown` (`None`) from `false`, fails closed on malformed typed input (`extra="forbid"`).

**Alignment semantics:** half-open `[start,end)`, deterministic `Decimal` bin boundaries anchored to per-run anchor, no interpolation, no invented values for missing bins, explicit `empty|partial|complete` per bin, metric version/unit compatibility enforced against authoritative catalogue, exact per-run provenance, naive timestamps rejected, stable ordering. `max_bins` preflight before materialisation (total_bins and overall 100k).

## 4. Architecture and reused services

```
BundleValidationResult (existing) ──> event_aligned.service.build_event_aligned_report
                                      ├─> traffictwin.metrics.windowed.canonical_tables_for_window logic reimplemented via _filter_tables_for_absolute_window (half-open, Decimal)
                                      ├─> traffictwin.metrics.engine.compute_metrics (per bin, reusing MetricEngineConfig, evidence, run_context) — run_context/evidence hoisted before bin loop
                                      ├─> traffictwin.metrics.catalogue.METRIC_DEFINITIONS and window_metric_catalogue (version/unit/window-applicability)
                                      └─> traffictwin.canonical.tables.CanonicalTables.record_counts
UI page (thin) ──> ui.services.event_aligned.compute_event_aligned_for_ui ──> service (public catalogue, bounded inputs secondary defense)
              └─> exports (json/csv) ──> report.to_portable_dict / fingerprint (deterministic, excludes created_at_utc)
```

Reuses: `validate_bundle`, `run_context_from_bundle`, `compute_metrics`, `METRIC_VERSION`, `window_metric_catalogue`, `CanonicalTables`, `EvidenceAvailability`, `MetricCollection`, `MetricStatus`, `Streamlit` `line_figure`, `table_column_config`, `badge`, `page_runtime`.

Does not: launch simulation, treat authored event as observation, claim recovery/clearance, smooth/interpolate, calculate causal impact, alter existing fixed-window contract, use wall clock in identity. PARTIAL numeric values are preserved in summaries/CSV/pairwise while retaining PARTIAL status.

## 5. Changed files and diff statistics

- `src/traffictwin/event_aligned/__init__.py`, `models.py`, `service.py`, `exports.py` — new domain (after fix: removed CoverageState.EXCLUDED, EventAlignedCompatibility, dead validators)
- `src/traffictwin/ui/services/event_aligned.py` — UI service (uses public catalogue)
- `src/traffictwin/ui/pages/event_aligned_analysis.py` — thin page (bounded inputs)
- `src/traffictwin/ui/app_pages/event_aligned_analysis.py` — wrapper
- `src/traffictwin/ui/labels.py` — added `EVENT_ALIGNED_ANALYSIS`
- `src/traffictwin/ui/navigation.py` — added to `Analysis` group
- `src/traffictwin/ui/navigation_v07.py` — added `V07PageSpec` for `event-aligned-analysis`
- `src/traffictwin/ui/page_runtime.py` — added import and `PAGE_RENDERERS` entry
- `tests/unit/test_event_aligned_*.py` (4 files, including `test_event_aligned_blockers.py` M1-M8), `tests/integration/test_event_aligned_integration.py`, `tests/ui/test_event_aligned_page.py` — coverage
- `tests/ui/test_navigation_v07.py` — updated to 39 pages (live base 38 + 1)
- `docs/user_guide.md` — added Event-Aligned section
- `docs/quality/v3_event_aligned_analysis_review.md` — this file

```
20 files changed, 3582 insertions(+), 3 deletions(-) (3b7933d..HEAD)
Isolated registration commit (7c9cddd): 6 files changed, 22 insertions(+), 3 deletions(-)
  docs/user_guide.md, src/traffictwin/ui/labels.py, src/traffictwin/ui/navigation.py,
  src/traffictwin/ui/navigation_v07.py, src/traffictwin/ui/page_runtime.py, tests/ui/test_navigation_v07.py
```

Base pages 38 → 39 (+1). Isolated registration contains only smallest necessary shared surfaces.

Commit history after reconciliation (reordered fix before register):
- 0d213ae feat(event-aligned): add typed domain, deterministic service reusing windowed engine, exports and thin UI page
- 01d36fa test(event-aligned): add unit/integration/UI coverage with adversarial mutation proofs
- 420e9c9 style(event-aligned): ruff format and lint fixes, add quality review
- fd15853 fix(event-aligned): address Claude review blockers (naive 1970, max_bins preflight, PARTIAL, catalogue guard, JSON determinism, engine-contract, hoist)
- 7c9cddd feat(event-aligned): register Event-Aligned Analysis page (isolated)

## 6. Test counts (observed, serial, E2 active → no -n/SUMO/VEC)

- `test_event_aligned_models.py`: 8 collected, 8 passed
- `test_event_aligned_service.py`: 14 collected, 14 passed
- `test_event_aligned_exports.py`: 5 collected, 5 passed
- `test_event_aligned_blockers.py`: 14 collected, 14 passed (M1–M9 + partial_count semantics + invariant)
- `test_event_aligned_integration.py`: 4 collected, 4 passed
- `test_event_aligned_page.py`: 4 collected, 4 passed
- `test_navigation_v07.py`: 51 collected, 51 passed (including event_aligned_analysis smoke)
- Full feature suite (above 6 files + integration): 49 collected, 49 passed (serial, 8.77s)
- Combined with navigation: 100 collected, 100 passed (49+51)
- No `pytest -n`, no SUMO/VEC launch, focused gates first.

**At 933cbdf:** same 8/14/5/9/4/4/51 = 44+51=95. At 933cbdf M3 was vacuous (zero PARTIAL service points, fallback assert True) and partial_count double-counted (partial 2 for bin 1). At 1025c6b M3 is real (2 PARTIAL points via energy contract), M9 and invariant added, M2 bomb added → 49+51=100.

## 7. Mutation table (M1–M9 blocker regressions)

At `933cbdf`: M3 was vacuous — `test_M3_partial_numeric_preserved` produced zero `status=="partial"` points via `build_event_aligned_report`, fell through `if not found_partial:` to engine-only `assert True`, so reverting `status in ("available","partial")` to `status=="available"` left all 44 feature tests green. `partial_count` also double-counted bins that were both metric-partial and coverage-partial (bin 1 → partial 2). Corrected at `1025c6b`.

| Mutation | Test that failed | Exact assertion | Restored | Provenance |
|---|---|---|---|---|
| M1 naive `bundle.created_at` fallback to 1970 | `test_M1_naive_bundle_time_basis_excluded` — `assert len(excluded)==1 and code=="INVALID_TIME_BASIS"` vs `test_M1_tz_aware_accepted` | `AssertionError: assert 0 == 1` (run incorrectly accepted) | Yes | 933cbdf and 1025c6b |
| M2 `max_bins` checked only after materialisation (100M bins) — old could hang 90s | `test_M2_max_bins_preflight_before_materialisation` — structural bomb `patch(_build_bins_for_spec, bomb)` + `pytest.raises(ValueError, match="configured maximum|exceeds")` | `Failed: bin materialisation was reached before max_bins preflight` (bomb, not hang); direct `_build_bins_for_spec` also raises | Yes | 1025c6b (strengthened; old had time<1s but mutant relied on external timeout) |
| M3 PARTIAL numeric discarded (`value=None` for partial) | `test_M3_partial_numeric_preserved` — real service PARTIAL via `_make_partial_energy_bundle` (2 tasks same bin, energy per_completed): `assert partial_points` unconditional, `assert p.value is not None and p.value==1.0`, `assert s.partial_count==1 and s.mean==1.0`, `assert pairwise baseline==1.0`, `assert "1.0" in csv_points` and `assert "1.0" in json`, `assert p.coverage_state` | `AssertionError: PARTIAL must retain numeric value / assert None is not None` (first occurrence) or `assert mean==1.0 got None` (second) | Yes | 1025c6b (real engine; 933cbdf had `if not found_partial: assert True` vacuous) |
| M4 non-window-applicable metric accepted | `test_M4_non_window_metric_rejected` — `with pytest.raises(ValueError, match="not window-applicable")` + UI `ServiceError` | `AssertionError: DID NOT RAISE` | Yes | 933cbdf and 1025c6b |
| M5 JSON includes `created_at_utc` | `test_M5_json_determinism_across_clocks` — `r1.fingerprint==r2.fingerprint and j1==j2 and "created_at_utc" not in j1` | `AssertionError: fingerprints differ` | Yes | 933cbdf and 1025c6b |
| M6 compatibility bypass | `test_M6_compatibility_engine_contract` — `ValueError match "does not match authoritative"` + warning `single current engine contract` | `AssertionError: DID NOT RAISE` | Yes | 933cbdf and 1025c6b |
| M7 `run_context` inside bin loop | `test_M7_run_context_hoisted` — `assert mock_rc.call_count==2 not 30` | `AssertionError: 36 !=2` | Yes | 933cbdf and 1025c6b |
| M8 warning ownership | `test_m8_warning_ownership` — `assert "has no available..." not in report.warnings and "No available..." in summary.warnings` | `AssertionError: not found` | Yes | 933cbdf and 1025c6b |
| M9 partial_count double increment (metric PARTIAL + coverage PARTIAL counted twice) | `test_M9_partial_count_double_increment` — one bin both conditions: `assert s.partial_count==1 not 2` and `assert 0<=partial<=bin_count` + invariant `test_partial_count_invariant_across_report` | `AssertionError: partial_count should be 1 not 2` (got 2) | Yes | 1025c6b (new regression at 933cbdf, not tested) |

Additional semantics tests: `test_partial_count_metric_only` (partial+complete →1), `test_partial_count_coverage_only` (available+partial→1), `test_partial_count_neither` (available+complete→0), `test_partial_count_invariant_across_report` (0≤partial≤bin).

Additional pre-existing mutations (half-open, labelled authored, version mismatch, zero-fill, fingerprint exclusions, row order, anchor change) remain covered by `test_event_aligned_service.py` (see section 7 prior). All restored.

## 8. Lint/type/lock/diff gates

- `ruff check src/traffictwin/event_aligned src/traffictwin/ui/services/event_aligned.py src/traffictwin/ui/pages/event_aligned_analysis.py tests/unit/test_event_aligned_*.py tests/integration/test_event_aligned_integration.py tests/ui/test_event_aligned_page.py` — **0 errors, All checks passed!**
- `ruff format --check` — **6 files already formatted**
- `mypy --strict src/traffictwin/event_aligned` — **Success: no issues found in 4 source files** (pydantic `extra="forbid"`, explicit types)
- `uv lock --check` — **Resolved 91 packages in 13ms, exit 0** (no new dependencies)
- `git diff --check` — **no whitespace errors, exit 0**

## 9. Evidence and claim boundaries

- Evidence types exact: synthetic fixture, imported bundle, authored configuration, not Manchester observation; BODS buses not treated as general traffic; manual incidents labelled authored anchors.
- Reports state canonical time basis, half-open windows, coverage is bin overlap not sensor completeness, missing bins unavailable not zero, pairwise deltas are descriptive differences during the declared event window, not causal effects. PARTIAL bins retain numeric value with PARTIAL status.
- No optimality, superiority, or production-readiness claims.
- Uses non-causal wording `difference during the declared event window`; validator rejects `caused`, `causal`, `impact`, `effect`, `due to the event`.
- Does not claim live, accepted, or scientifically validated beyond tested synthetic fixtures. Naive time basis fails closed.

## 10. E2/process isolation evidence

- Before rebase (2026-08-10 02:55 UTC): `pgrep -fl eval_sumo|run_e2|native-placement` returned no active E2 pids (empty). Earlier at 01:41 UTC had PIDs but not at verification time.
- After verification: same check empty; no new evaluator started, no `pytest -n`, no SUMO/VEC launch.
- Tests run serially with `.venv/bin/python -m pytest -q` per file.

## 11. Shared-file/other-PR isolation

- Domain, service, exports, page impl, and feature tests in isolated files/commits.
- Registration commit (7c9cddd) contains only `labels.py`, `navigation.py`, `navigation_v07.py`, `page_runtime.py`, `tests/ui/test_navigation_v07.py`, `docs/user_guide.md` — smallest necessary.
- Four other parallel lanes (PRs 13–22) use disjoint feature file sets; no cherry-pick, no reset, no merge, no modification of PR #21/#22 research artifacts. Verified via `git diff --name-only 3b7933d..HEAD` lists only 20 event-aligned files.
- No force-push to other branches, no edits to `/diss`, `vec_env`, `tos-data`, raw E2 outputs.

## 12. Remaining limitations

- Window computation reuses metric engine per bin sequentially; for 8 runs × ~30 bins × 60 metrics could be ~14k evaluations (bounded by `max_bins` 10k and overall 100k).
- `canonical_time_basis` single version `utc_bundle_created_at_offset_v1`; future bases require migration.
- Pairwise deltas are simple mean differences (available+partial); no statistical inference, confidence, or multiple-comparison correction.
- Incident anchor currently as authored `EventAnchor` with `incident_id`; no automatic extraction from `incidents.csv` earliest timestamp — UI requires explicit timezone-aware input.
- No CLI entry; Python API is `build_event_aligned_report`; UI is primary workflow.
- Manchester observation-to-SUMO calibration and near-live operational data remain unavailable and are not claimed.
- Export JSON is portable via `to_portable_dict` (excludes `created_at_utc` and local paths); pretty variant also deterministic.

## 13. Reviewer brief (exact head)

Head SHA to review is `7c9cddd5de3f7a5e29f7d93ff0a3a21d9f276d8d` (final registration commit after fix reordering, on `agent/product-v3-event-aligned-analysis-v1`, base `3b7933d`). Verify: `labels.py` adds `EVENT_ALIGNED_ANALYSIS` (39 pages), `navigation.py`/`navigation_v07.py` add `event-aligned-analysis` under `Analysis`/`Results` with grouped `st.navigation`, `page_runtime.py` registers thin page, `test_navigation_v07.py` expects 39, `docs/user_guide.md` has Event-Aligned section, core files pass `ruff`/`mypy`/`uv lock --check`/`git diff --check`, feature tests 44 passed + 51 navigation = 95, UI page renders with `st.navigation` at `/event-aligned-analysis`, preview windows exact half-open, chart/table share same `report.metric_points`, JSON/CSV deterministic via `to_portable_dict`, fingerprint excludes `created_at_utc` and local paths, PARTIAL numeric preserved, naive bundle fails closed, max_bins preflight, window-applicability via public catalogue, and M1-M8 restored with documented assertions above.

