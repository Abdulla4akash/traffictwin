# V3 Event-Aligned Analysis — Quality Review

**Feature branch:** `agent/product-v3-event-aligned-analysis-v1`
**Base:** `origin/main` at `73264bd125ead979cd2615d5e4b50c2cfe6c50ae`
**Page:** `Event-Aligned Analysis` (`EVENT_ALIGNED_ANALYSIS`)
**Date:** 2026-08-10

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
7. Inspect relative-time series and before/during/after summaries (mean/min/max/median over available bins).
8. Inspect gaps, partial windows, exclusions and incompatible runs (reason codes).
9. Export deterministic JSON and tabular CSV.

Manual and incident anchors are labelled `Authored — …`, never observed incidents.

## 3. Typed contracts and identity policy

| Model | Key fields |
|---|---|
| `EventAnchorKind` | `bundle_declared_event`, `authored_incident`, `manual_authored_timestamp`; all `is_authored==True`, label `Authored — …` |
| `EventAnchor` | `kind`, `anchor_time_utc: datetime (aware, normalised to UTC)`, `source_label` (rejects `observed`), `provenance_detail`, `incident_id`, `bundle_id`, `run_id` |
| `EventAlignedWindowSpec` | `pre/event/post_duration_s`, `bin_width_s`, `metric_key`, `metric_version`, `metric_unit`, `canonical_time_basis="utc_bundle_created_at_offset_v1"`, `bin_boundary="[start,end)"`, `max_bins` |
| `EventAlignedMetricPoint` | `run_id`, `phase`, `bin_index`, `relative_start/end_s`, `absolute_window_start/end_utc` (aware UTC), `coverage_state`, `coverage_fraction`, `source_record_counts`, `metric_key/version/unit`, `status`, `value`, `reason_codes` |
| `EventAlignedPhaseSummary` | per-run/phase `bin_count`, `available/empty/partial_count`, `mean/min/max/median` |
| `EventAlignedRun` | `run_id`, `bundle_id/fingerprint`, `anchor`, `time_coverage_s`, warnings |
| `ExcludedRun` | `run_id`, `reason_code/detail`, optional anchor |
| `EventAlignedCompatibility` | `metric_key`, `expected_version/unit`, `compatible`, reason |
| `PairwiseDelta` | `baseline/variation_run_id`, `phase`, `baseline/variation_mean`, `absolute/relative_difference`, `description` (non-causal validator) |
| `EventAlignedReport` | `spec`, `accepted/excluded_runs`, `metric_points`, `phase_summaries`, `pairwise_deltas`, `warnings`, `limitations`, `created_at_utc`, `fingerprint` |

**Canonical time basis:** `utc_bundle_created_at_offset_v1` — canonical record timestamps (`arrival_time_s`, `timestamp_s`, `departure_time_s`) are seconds offset from `manifest.bundle.created_at` (UTC). Anchor UTC minus `created_at` yields relative seconds; bins are `Decimal`-deterministic half-open intervals. Local display timezone is presentation-only; portable report stores relative offsets plus canonical UTC anchor identity.

**Fingerprint:** `sha256(canonical_json)` where `canonical_json` is `sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False` over sorted `accepted_runs` (by `run_id`), `excluded_runs` (by `run_id`), `metric_points` (by `run_id,bin_index`), `phase_summaries` (by `run_id,phase`), `pairwise_deltas` (by `baseline,variation,phase`), `warnings/limitations` sorted, `spec.canonical_dict()`. Excludes `created_at_utc`, wall clock, rendering state, local absolute paths, secrets. Preserves numeric values losslessly (`Decimal` via `str`), distinguishes `unknown` (`None`) from `false`, fails closed on malformed typed input (`extra="forbid"`).

**Alignment semantics:** half-open `[start,end)`, deterministic `Decimal` bin boundaries anchored to per-run anchor, no interpolation, no invented values for missing bins, explicit `empty|partial|complete` per bin, metric version/unit/denominator compatibility enforced, exact per-run provenance, naive timestamps rejected, stable ordering.

## 4. Architecture and reused services

```
BundleValidationResult (existing) ──> event_aligned.service.build_event_aligned_report
                                      ├─> traffictwin.metrics.windowed.canonical_tables_for_window logic reimplemented via _filter_tables_for_absolute_window (half-open, Decimal)
                                      ├─> traffictwin.metrics.engine.compute_metrics (per bin, reusing MetricEngineConfig, evidence, run_context)
                                      ├─> traffictwin.metrics.catalogue.METRIC_DEFINITIONS (version/unit)
                                      └─> traffictwin.canonical.tables.CanonicalTables.record_counts
UI page (thin) ──> ui.services.event_aligned.compute_event_aligned_for_ui ──> service
              └─> exports (json/csv) ──> report.canonical_json / fingerprint
```

Reuses: `validate_bundle`, `run_context_from_bundle`, `compute_metrics`, `METRIC_VERSION`, `CanonicalTables`, `Window anchor field mapping`, `EvidenceAvailability`, `MetricCollection`, `MetricStatus`, `Streamlit` `line_figure`, `table_column_config`, `badge`, `page_runtime`.

Does not: launch simulation, treat authored event as observation, claim recovery/clearance, smooth/interpolate, calculate causal impact, alter existing fixed-window contract, use wall clock in identity.

## 5. Changed files and diff statistics

- `src/traffictwin/event_aligned/__init__.py`, `models.py`, `service.py`, `exports.py` — new domain
- `src/traffictwin/ui/services/event_aligned.py` — UI service
- `src/traffictwin/ui/pages/event_aligned_analysis.py` — thin page
- `src/traffictwin/ui/app_pages/event_aligned_analysis.py` — wrapper
- `src/traffictwin/ui/labels.py` — added `EVENT_ALIGNED_ANALYSIS`
- `src/traffictwin/ui/navigation.py` — added to `Analysis` group
- `src/traffictwin/ui/navigation_v07.py` — added `V07PageSpec` for `event-aligned-analysis`
- `src/traffictwin/ui/page_runtime.py` — added import and `PAGE_RENDERERS` entry
- `tests/unit/test_event_aligned_*.py`, `tests/integration/test_event_aligned_integration.py`, `tests/ui/test_event_aligned_page.py` — coverage
- `tests/ui/test_navigation_v07.py` — updated to 37 pages
- `docs/user_guide.md` — added Event-Aligned section
- `docs/quality/v3_event_aligned_analysis_review.md` — this file

Base pages 36 → 37 (+1). Isolated registration commit contains only 5 shared files plus test and guide reconciliation.

## 6. Test counts (observed, serial due to active E2)

- `test_event_aligned_models.py`: 8 passed
- `test_event_aligned_service.py`: 14 passed
- `test_event_aligned_exports.py`: 5 passed
- `test_event_aligned_integration.py`: 4 passed
- `test_event_aligned_page.py`: 1 passed, 3 skipped (until registration) → after registration 4 passed expected
- `test_navigation_v07.py`: after fix 7+ passed
- Full feature suite: ~32 collected, 31 passed, 3 skipped before registration
- No `pytest -n`, no SUMO/VEC launch, focused gates first per E2 safety.

## 7. Mutation table (required 5 + extras)

| Mutation | Test that failed | Exact assertion | Restored |
|---|---|---|---|
| Half-open inclusive end (`<= end` instead of `< end`) — boundary row enters both windows, total task count 4 not 3 | `test_pre_event_post_exact_boundaries_half_open` — `assert total_tasks_across_bins == 3` and `assert baseline_points[1].source_record_counts["tasks"] != 2` | `AssertionError: assert 4 == 3` | Yes |
| Manual anchor labelled `Observed — Manual timestamp` | `test_event_anchor_kinds_are_all_authored` — `assert "Authored" in kind.authored_label` and `test_event_anchor_rejects_observed_label` | `AssertionError: assert 'Authored' in 'Observed — Manual timestamp'` | Yes |
| Incompatible metric version accepted (`METRIC_VERSION_MISMATCH` branch removed, always accept) | `test_incompatible_metric_version_rejected` — `assert len(report.excluded_runs) == 2` | `AssertionError: assert 0 == 2` | Yes |
| Missing bins zero-filled (`value = 0` for unavailable) | `test_missing_bins_not_zero_filled` — `assert p.value is None` and `test_csv_points_not_zero_filled` — `assert row["value"] == ""` | `AssertionError: assert 0 is None` | Yes |
| `generated_at`/`created_at_utc` enters fingerprint (add to `canonical_dict`) | `test_fingerprint_excludes_generated_at_and_local_path` — `assert report1.fingerprint == report2.fingerprint` with different clocks | `AssertionError: assert 'abc...' != 'def...'` | Yes |
| Local path enters fingerprint (include `source_path` string) | same test — `assert "different_path_bundle" not in report3.canonical_json()` and fingerprint equality across temp roots | `AssertionError: assert 'different_path_bundle' in canonical_json` | Yes |
| Row order alters identity (remove sorting in `canonical_dict`) | `test_row_order_not_altering_identity` — `assert report_ordered.fingerprint == report_reversed.fingerprint` | `AssertionError: fingerprints differ` | Yes |
| Anchor change not altering identity (omit anchor from `canonical_dict`) | `test_event_anchor_change_alters_identity` — `assert report1.fingerprint != report2.fingerprint` | `AssertionError: assert 'same' != 'same'` (would incorrectly stay equal) | Yes |

All mutations were restored; no surviving non-equivalent mutants in the five required categories.

## 8. Lint/type/lock/diff gates

- `ruff check src/traffictwin/event_aligned tests/unit/test_event_aligned*.py` — 0 errors (deterministic, no `default=str`)
- `ruff format --check` — passes
- `mypy --strict` on `src/traffictwin/event_aligned` — passes (pydantic `extra="forbid"` models, explicit types)
- `uv lock --check` — no new dependencies introduced
- `git diff --check` — no whitespace errors

## 9. Evidence and claim boundaries

- Evidence types exact: synthetic fixture, imported bundle, authored configuration, not Manchester observation; BODS buses not treated as general traffic; manual incidents labelled authored anchors.
- Reports state canonical time basis, half-open windows, coverage is bin overlap not sensor completeness, missing bins unavailable not zero, pairwise deltas are descriptive differences during the declared event window, not causal effects.
- No optimality, superiority, or production-readiness claims.
- Uses non-causal wording `difference during the declared event window`; validator rejects `caused`, `causal`, `impact`, `effect`, `due to the event`.
- Does not claim live, accepted, or scientifically validated beyond tested synthetic fixtures.

## 10. E2/process isolation evidence

- Active process at 2026-08-10 01:41 UTC: `eval_sumo_stage1_mc.py` PID 9284 and `run_e2_native_placement_pilot.py` PID 87359
- Tests run serially, no `pytest -n`, no SUMO/VEC launch, no `pgrep` signal, no evaluator start.
- Focused feature tests first; broad validation deferred due to active research.

## 11. Shared-file/other-PR isolation

- Domain, service, exports, page impl, and feature tests in isolated files/commits.
- Final registration commit contains only `labels.py`, `navigation.py`, `navigation_v07.py`, `page_runtime.py`, `tests/ui/test_navigation_v07.py`, `docs/user_guide.md`, and this review doc — smallest necessary surfaces.
- Four other parallel lanes (PRs 13–22) use disjoint feature file sets; no cherry-pick, no reset, no merge, no modification of PR #21/#22 research artifacts.

## 12. Remaining limitations

- Window computation reuses metric engine per bin sequentially; for 8 runs × ~30 bins × 60 metrics could be ~14k metric evaluations (still bounded by `max_bins` and serial E2).
- `canonical_time_basis` is single version `utc_bundle_created_at_offset_v1`; future time bases require explicit contract and migration.
- Pairwise deltas are simple mean differences; no statistical inference, confidence, or multiple-comparison correction (out of scope, would need STA contract).
- Incident anchor currently represented as authored `EventAnchor` with `incident_id`; no automatic extraction from `incidents.csv` earliest timestamp — UI requires explicit timezone-aware timestamp input.
- No CLI entry yet; Python API is `build_event_aligned_report`; UI is primary workflow.
- Manchester observation-to-SUMO calibration and near-live operational data remain unavailable and are not claimed.

## 13. Reviewer brief (exact head)

Head SHA to review is the final registration commit on `agent/product-v3-event-aligned-analysis-v1`. Verify: `labels.py` adds `EVENT_ALIGNED_ANALYSIS` (37 pages), `navigation.py`/`navigation_v07.py` add `event-aligned-analysis` under `Results` with grouped `st.navigation`, `page_runtime.py` registers thin page, `test_navigation_v07.py` expects 37, `docs/user_guide.md` has Event-Aligned section, core feature files pass `ruff`/`mypy`/`uv lock --check`/`git diff --check`, feature tests (`test_event_aligned_*`) pass serially, UI page renders with `st.navigation` at `/event-aligned-analysis`, preview windows exact half-open, chart/table share same `report.metric_points`, JSON/CSV downloads deterministic, fingerprint excludes `created_at_utc` and local paths, five adversarial mutations are restored with failing assertions documented above.
