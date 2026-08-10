"""Deterministic calibration service — read-only descriptive comparison."""

from __future__ import annotations

import json
import math

from traffictwin.calibration.models import (
    CalibrationAlignmentAudit,
    CalibrationBin,
    CalibrationCandidate,
    CalibrationCandidateSummary,
    CalibrationExclusion,
    CalibrationMetricResult,
    CalibrationMetricSpec,
    CalibrationObservedReference,
    CalibrationReport,
    CalibrationResidual,
    CalibrationStatus,
    CalibrationStudy,
    ExclusionReasonCode,
    canonical_json_bytes,
    sha256_hex,
)

EVIDENCE_BOUNDARY = (
    "Read-only descriptive comparison of admitted observed traffic evidence "
    "with imported simulation candidates. No causality is claimed. No candidate "
    "is declared validated or optimal. Evidence is admitted only when bound by "
    "fingerprint; synthetic demonstration evidence is labelled synthetic demonstration evidence."
)

LIMITATIONS = [
    "Descriptive fit only — no parameter tuning is performed.",
    "Half-open window semantics [start,end) are enforced; bins not overlapping are unmatched.",
    "Missing evidence is never zero-filled; unavailable bins are skipped.",
    "Relative error is computed only with a safe non-zero denominator.",
    "Weighted declared objective ranks candidates only when every required component is available and compatible.",  # noqa: E501
    "Lowest declared objective among compatible candidates is not a validated model claim.",
    "No synthetic evidence is relabelled as observed.",
    "No production-readiness or Manchester evidence is claimed unless genuine admitted evidence is supplied.",  # noqa: E501
]


def _fingerprint_for_study_canonical(study: CalibrationStudy) -> str:
    payload = study.canonical_dict()
    return sha256_hex(canonical_json_bytes(payload))


def _safe_relative_error(signed_error: float, observed: float) -> float | None:
    # safe denominator: absolute observed > epsilon
    if abs(observed) < 1e-9:
        return None
    return signed_error / observed


def _compute_alignment_audit(
    *,
    candidate: CalibrationCandidate,
    observed: CalibrationObservedReference,
    specs: list[CalibrationMetricSpec],
    alignment_spec: CalibrationStudy,
) -> CalibrationAlignmentAudit:
    # temporal alignment: compare candidate window to observed/alignment spec window
    tol = alignment_spec.alignment_spec.temporal_tolerance_s
    obs_start = observed.window_start_utc
    obs_end = observed.window_end_utc
    cand_start = candidate.window_start_utc
    cand_end = candidate.window_end_utc
    # Check bin_width match (must be exact or within tolerance for windows, but bin_width strict)
    bin_width_match = abs(candidate.bin_width_s - observed.bin_width_s) < 1e-9
    # temporal window alignment: start and end within tolerance
    start_diff = abs((cand_start - obs_start).total_seconds())
    end_diff = abs((cand_end - obs_end).total_seconds())
    temporal_aligned = bin_width_match and start_diff <= tol and end_diff <= tol
    temporal_reason: str | None = None
    if not bin_width_match:
        temporal_reason = f"bin_width mismatch: observed {observed.bin_width_s} vs candidate {candidate.bin_width_s}"  # noqa: E501
    elif start_diff > tol:
        temporal_reason = f"window_start misalignment {start_diff:.1f}s > tolerance {tol:.1f}s"
    elif end_diff > tol:
        temporal_reason = f"window_end misalignment {end_diff:.1f}s > tolerance {tol:.1f}s"

    # unit compatibility: for each spec, check candidate metric_units matches spec unit
    mismatches: list[str] = []
    for spec in specs:
        cand_unit = candidate.metric_units.get(spec.metric_key)
        if cand_unit is None:
            # If candidate doesn't declare unit for that metric, try to infer from bins
            # Look for any bin with that metric_key
            units = {b.unit for b in candidate.bins if b.metric_key == spec.metric_key}
            if units:
                # if any mismatched
                for u in units:
                    if u != spec.unit:
                        mismatches.append(f"{spec.metric_key}: expected {spec.unit!r} got {u!r}")
            else:
                # Not having that metric is not unit mismatch but missing evidence; treat as not mismatched here  # noqa: E501
                continue
        elif cand_unit != spec.unit:
            mismatches.append(f"{spec.metric_key}: expected {spec.unit!r} got {cand_unit!r}")
        # Also check observed unit matches spec (should be, but if not, candidate still evaluated)
        # Check per-bin unit mismatches as well (strict)
        for b in candidate.bins:
            if b.metric_key == spec.metric_key and b.unit != spec.unit:
                key = f"{spec.metric_key}: bin unit {b.unit!r} != spec {spec.unit!r}"
                if key not in mismatches:
                    mismatches.append(key)
    unit_compatible = len(mismatches) == 0

    # sensor mapping completeness: alignment_spec sensor_mapping must be satisfied
    sensor_map = alignment_spec.alignment_spec.sensor_mapping
    missing_sensors: list[str] = []
    if sensor_map:
        # sensor_map keys are observed sensors, values are simulation sensor/link ids
        # Check that observed has those sensors and candidate has mapped sensors
        for obs_sensor, sim_sensor in sensor_map.items():
            if obs_sensor not in observed.sensor_ids:
                missing_sensors.append(f"observed mapping key missing: {obs_sensor}")
            if sim_sensor not in candidate.sensor_ids:
                missing_sensors.append(
                    f"candidate mapping target missing: {sim_sensor} for {obs_sensor}"
                )
    else:
        # default: require candidate to have at least the observed sensors (or overlapping)
        # If candidate missing any observed sensor, that's incomplete
        for s in observed.sensor_ids:
            if s not in candidate.sensor_ids:
                missing_sensors.append(s)
    sensor_mapping_complete = len(missing_sensors) == 0

    # coverage calculation
    # total_bins defined by observed: sensors * windows * metrics? Actually totalbins per alignment spec total bins * sensors  # noqa: E501
    # For simplicity: total_bins = len(observed.bins) if observed bins present else alignment_spec total_bins * len(observed.sensor_ids)  # noqa: E501
    # We'll compute from observed bins count (if populated) else from alignment spec
    if observed.bins:
        total_bins = len(observed.bins)
    else:
        total_bins = alignment_spec.alignment_spec.total_bins() * len(observed.sensor_ids)
    # available bins for candidate vs observed pairing: count of observed+sim both present
    # Here for audit, available_bins = number of candidate bins that could be paired (non-missing value?)  # noqa: E501
    # But we can compute coverage as candidate non-missing bins / total_bins? Simpler: ratio of candidate bins with value not None  # noqa: E501
    # Instead we audit coverage of candidate: non-missing values among its bins divided by total expected  # noqa: E501
    # We'll use len of candidate bins with non-None value / total_bins
    candidate_non_missing = sum(1 for b in candidate.bins if b.value is not None)
    # Missing bins for audit is total minus available
    available_bins = candidate_non_missing
    missing_bins = max(0, total_bins - available_bins) if total_bins > 0 else 0
    coverage_pct = (available_bins / total_bins * 100.0) if total_bins > 0 else 0.0

    # Determine exclusion
    excluded = False
    reason_code: str | None = None
    reason_detail: str | None = None
    if not temporal_aligned:
        excluded = True
        reason_code = ExclusionReasonCode.TEMPORAL_MISALIGNMENT.value
        reason_detail = temporal_reason or "temporal misalignment"
    elif not unit_compatible:
        excluded = True
        reason_code = ExclusionReasonCode.UNIT_MISMATCH.value
        reason_detail = "; ".join(mismatches)
    elif not sensor_mapping_complete:
        excluded = True
        reason_code = ExclusionReasonCode.SENSOR_MAPPING_INCOMPLETE.value
        reason_detail = f"missing sensors: {', '.join(missing_sensors)}"
    elif coverage_pct < alignment_spec.alignment_spec.coverage_threshold * 100.0:
        excluded = True
        reason_code = ExclusionReasonCode.COVERAGE_INSUFFICIENT.value
        reason_detail = f"coverage {coverage_pct:.1f}% < threshold {alignment_spec.alignment_spec.coverage_threshold * 100:.1f}%"  # noqa: E501

    return CalibrationAlignmentAudit(
        candidate_id=candidate.candidate_id,
        temporal_aligned=temporal_aligned,
        temporal_reason=temporal_reason,
        unit_compatible=unit_compatible,
        unit_mismatches=mismatches,
        sensor_mapping_complete=sensor_mapping_complete,
        missing_sensor_ids=missing_sensors,
        coverage_percentage=coverage_pct,
        total_bins=total_bins,
        available_bins=available_bins,
        missing_bins=missing_bins,
        is_excluded=excluded,
        exclusion_reason_code=reason_code,
        exclusion_detail=reason_detail,
    )


def _build_index(
    bins: list[CalibrationBin],
) -> dict[tuple[str, int, str], CalibrationBin]:
    """Index bins by (sensor_id, window_index, metric_key)."""
    idx: dict[tuple[str, int, str], CalibrationBin] = {}
    for b in bins:
        key = (b.sensor_id, b.window_index, b.metric_key)
        # If duplicate, keep first; validation should prevent duplicates but be deterministic
        if key not in idx:
            idx[key] = b
    return idx


def _compute_metric_results_and_residuals(
    *,
    observed: CalibrationObservedReference,
    candidate: CalibrationCandidate,
    specs: list[CalibrationMetricSpec],
    audit: CalibrationAlignmentAudit,
) -> tuple[list[CalibrationMetricResult], list[CalibrationResidual], float]:
    if audit.is_excluded:
        # For excluded candidates, still compute residuals partially but no objective
        return [], [], 0.0

    candidate_idx = _build_index(candidate.bins)

    # Gather all unique keys that should be evaluated per spec
    metric_results: list[CalibrationMetricResult] = []
    residuals: list[CalibrationResidual] = []
    overall_available = 0
    overall_total = 0

    for spec in specs:
        # Filter keys for this metric
        # Find all bins for this metric_key across sensors/windows
        # Use observed windows as ground: iterate over observed bins for that metric
        observed_bins_for_metric = [b for b in observed.bins if b.metric_key == spec.metric_key]
        # Also need to consider sensors that exist but have no bin? For simplicity count observed_bins_for_metric as denominator  # noqa: E501
        count_paired = 0
        count_missing_obs = 0
        count_missing_sim = 0
        errors: list[float] = []
        signed_errors: list[float] = []
        relative_errors: list[float] = []
        # For residuals, iterate over observed_bins_for_metric (or union if candidate has extra)
        # Use observed-driven iteration to keep half-open semantics deterministic
        for obs_bin in observed_bins_for_metric:
            key = (obs_bin.sensor_id, obs_bin.window_index, obs_bin.metric_key)
            cand_bin = candidate_idx.get(key)
            # Half-open window check: windows must match exactly (start/end alignment)
            # If candidate missing key or window mismatch, treat as missing_sim
            if cand_bin is None:
                # No candidate bin for this window/sensor/metric
                count_missing_sim += 1
                # Also check if observed itself is missing
                if obs_bin.value is None:
                    count_missing_obs += 1
                    # residuals with both missing? Still create residual with none values
                    residuals.append(
                        CalibrationResidual(
                            sensor_id=obs_bin.sensor_id,
                            window_index=obs_bin.window_index,
                            window_start_utc=obs_bin.window_start_utc,
                            window_end_utc=obs_bin.window_end_utc,
                            metric_key=spec.metric_key,
                            observed_value=obs_bin.value,
                            simulated_value=None,
                            signed_error=None,
                            absolute_error=None,
                            relative_error=None,
                        )
                    )
                else:
                    if obs_bin.value is None:
                        count_missing_obs += 1
                    residuals.append(
                        CalibrationResidual(
                            sensor_id=obs_bin.sensor_id,
                            window_index=obs_bin.window_index,
                            window_start_utc=obs_bin.window_start_utc,
                            window_end_utc=obs_bin.window_end_utc,
                            metric_key=spec.metric_key,
                            observed_value=obs_bin.value,
                            simulated_value=None,
                            signed_error=None,
                            absolute_error=None,
                            relative_error=None,
                        )
                    )
                continue
            # Both bins exist, now check values
            obs_val = obs_bin.value
            sim_val = cand_bin.value
            # Verify unit already validated, but still ensure
            # Window semantics: half-open [start,end) — already ensured by exact window_index and start/end match  # noqa: E501
            # If windows differ, we already excluded via temporal_aligned but per-bin check:
            if (
                obs_bin.window_start_utc != cand_bin.window_start_utc
                or obs_bin.window_end_utc != cand_bin.window_end_utc
            ):
                # Temporal misalignment at bin level — treat as missing_sim with reason
                count_missing_sim += 1
                if obs_val is None:
                    count_missing_obs += 1
                residuals.append(
                    CalibrationResidual(
                        sensor_id=obs_bin.sensor_id,
                        window_index=obs_bin.window_index,
                        window_start_utc=obs_bin.window_start_utc,
                        window_end_utc=obs_bin.window_end_utc,
                        metric_key=spec.metric_key,
                        observed_value=obs_val,
                        simulated_value=sim_val,
                        signed_error=None,
                        absolute_error=None,
                        relative_error=None,
                    )
                )
                continue
            # Handle missing per missingness policy: NEVER zero-fill
            if obs_val is None:
                count_missing_obs += 1
            if sim_val is None:
                count_missing_sim += 1
            if obs_val is None or sim_val is None:
                # Cannot compute error; record residual with missing error fields
                residuals.append(
                    CalibrationResidual(
                        sensor_id=obs_bin.sensor_id,
                        window_index=obs_bin.window_index,
                        window_start_utc=obs_bin.window_start_utc,
                        window_end_utc=obs_bin.window_end_utc,
                        metric_key=spec.metric_key,
                        observed_value=obs_val,
                        simulated_value=sim_val,
                        signed_error=None,
                        absolute_error=None,
                        relative_error=None,
                    )
                )
                continue
            # Both available — compute errors
            signed = sim_val - obs_val
            abs_err = abs(signed)
            rel = _safe_relative_error(signed, obs_val)
            errors.append(abs_err)
            signed_errors.append(signed)
            if rel is not None:
                relative_errors.append(abs(rel) if rel is not None else 0)

            residuals.append(
                CalibrationResidual(
                    sensor_id=obs_bin.sensor_id,
                    window_index=obs_bin.window_index,
                    window_start_utc=obs_bin.window_start_utc,
                    window_end_utc=obs_bin.window_end_utc,
                    metric_key=spec.metric_key,
                    observed_value=obs_val,
                    simulated_value=sim_val,
                    signed_error=signed,
                    absolute_error=abs_err,
                    relative_error=rel,
                )
            )
            count_paired += 1

        # Also handle candidate bins that have no observed counterpart? For now ignore extra simulation bins not in observed  # noqa: E501

        # Compute metric stats
        total_for_metric = len(observed_bins_for_metric)
        coverage_pct = (count_paired / total_for_metric * 100.0) if total_for_metric > 0 else 0.0
        is_available = count_paired > 0

        # If no paired bins, metric unavailable
        mae: float | None = None
        rmse: float | None = None
        mean_signed: float | None = None
        rel_mean: float | None = None
        if count_paired > 0:
            mae = sum(errors) / len(errors) if errors else None
            # RMSE: sqrt(mean(squared error))
            sq = [(s**2) for s in signed_errors]
            rmse = math.sqrt(sum(sq) / len(sq)) if sq else None
            mean_signed = sum(signed_errors) / len(signed_errors) if signed_errors else None
            rel_mean = sum(relative_errors) / len(relative_errors) if relative_errors else None
        else:
            # No paired — metric unavailable
            mae = None
            rmse = None
            mean_signed = None
            rel_mean = None

        metric_results.append(
            CalibrationMetricResult(
                metric_key=spec.metric_key,
                metric_version=spec.metric_version,
                unit=spec.unit,
                count_paired=count_paired,
                count_missing_observed=count_missing_obs,
                count_missing_simulation=count_missing_sim,
                mae=mae,
                rmse=rmse,
                mean_signed_error=mean_signed,
                relative_error_mean=rel_mean,
                coverage_percentage=coverage_pct,
                is_available=is_available,
            )
        )
        overall_available += count_paired
        overall_total += total_for_metric

    overall_coverage = (overall_available / overall_total * 100.0) if overall_total > 0 else 0.0
    return metric_results, residuals, overall_coverage


def _compute_weighted_objective(
    *,
    metric_results: list[CalibrationMetricResult],
    specs: list[CalibrationMetricSpec],
) -> float | None:
    # Weighted objective only if every required spec is available
    spec_by_key = {s.metric_key: s for s in specs}
    total_weight = 0.0
    weighted_sum = 0.0
    for res in metric_results:
        spec = spec_by_key.get(res.metric_key)
        if spec is None:
            continue
        # If spec weight is zero, it does not affect objective but still requires availability if required?  # noqa: E501
        # For this implementation, weight 0 metric does not require availability for objective
        if spec.weight == 0:
            continue
        # If metric not available, objective unavailable
        if not res.is_available or res.mae is None:
            # Fail-closed: any required component missing => objective unavailable
            # Policy MISSINGNESS: should not zero-fill
            return None
        # Use MAE as the error metric for objective (deterministic)
        # For higher_is_better direction, we still use MAE (error magnitude) so lower is better
        weighted_sum += spec.weight * res.mae
        total_weight += spec.weight
    if total_weight == 0:
        return None
    # Normalize by total weight to keep comparable
    return weighted_sum / total_weight


def build_calibration_report(study: CalibrationStudy) -> CalibrationReport:
    """Build deterministic calibration report for a study.

    - Never zero-fills missing evidence.
    - Computes MAE, RMSE, signed error, relative error with safe denominator.
    - Determines exclusions via temporal, unit, sensor mapping, coverage.
    - Weighted objective only when all required components are available.
    - Ranking uses "lowest declared objective among compatible candidates" wording.
    """
    candidate_summaries: list[CalibrationCandidateSummary] = []
    exclusions: list[CalibrationExclusion] = []

    for candidate in study.candidates:
        audit = _compute_alignment_audit(
            candidate=candidate,
            observed=study.observed,
            specs=study.metric_specs,
            alignment_spec=study,
        )
        # Build metric results and residuals
        metric_results, residuals, overall_coverage = _compute_metric_results_and_residuals(
            observed=study.observed,
            candidate=candidate,
            specs=study.metric_specs,
            audit=audit,
        )

        # Determine status and exclusions
        exclusion: CalibrationExclusion | None = None
        status = CalibrationStatus.AVAILABLE

        if audit.is_excluded:
            status = CalibrationStatus.EXCLUDED
            exclusion = CalibrationExclusion(
                candidate_id=candidate.candidate_id,
                reason_code=audit.exclusion_reason_code
                or ExclusionReasonCode.COVERAGE_INSUFFICIENT.value,
                reason_detail=audit.exclusion_detail or "excluded by alignment audit",
                failing_metric=None,
            )
            exclusions.append(exclusion)
            weighted_objective: float | None = None
            # For excluded, metric_results may be empty or partial; coverage is 0 or audit coverage
            # Ensure coverage_percentage reflects audit coverage for excluded
            candidate_coverage = audit.coverage_percentage
            # metric_results for excluded we keep empty? But we already computed empty list for excluded above  # noqa: E501
            # Keep them empty for excluded to avoid misleading numbers
            metric_results = []
            residuals = []
        else:
            # Check for metric-level exclusions: if any spec is alignment_required and metric not available, candidate excluded?  # noqa: E501
            # For now, candidate remains available but objective unavailable if any required metric missing  # noqa: E501
            # Determine coverage for non-excluded
            candidate_coverage = overall_coverage if metric_results else audit.coverage_percentage
            weighted_objective = _compute_weighted_objective(
                metric_results=metric_results, specs=study.metric_specs
            )
            # If weighted objective unavailable due to missing required component, mark status UNAVAILABLE and add exclusion?  # noqa: E501
            # Spec says: "A candidate lacking required compatible coverage remains unavailable or excluded."  # noqa: E501
            # So if any required spec metric is not available, candidate should be UNAVAILABLE (objective None) but not necessarily excluded from table  # noqa: E501
            # We'll keep status AVAILABLE but weighted_objective None; however for ranking they will be excluded  # noqa: E501
            # Alternatively mark UNAVAILABLE status when objective None due to missing
            if weighted_objective is None:
                # Check if any required metric had zero paired
                any_missing_required = any(
                    (not r.is_available)
                    for r in metric_results
                    for s in study.metric_specs
                    if s.metric_key == r.metric_key and s.alignment_required and s.weight > 0
                )
                if any_missing_required:
                    status = CalibrationStatus.UNAVAILABLE
                    # Add exclusion for insufficient paired bins but keep candidate summary for display  # noqa: E501
                    missing_metric = next(
                        (r.metric_key for r in metric_results if not r.is_available),
                        None,
                    )
                    exclusion = CalibrationExclusion(
                        candidate_id=candidate.candidate_id,
                        reason_code=ExclusionReasonCode.MISSING_REQUIRED_METRIC.value,
                        reason_detail="required metric has no paired bins; objective unavailable (no zero-fill)",  # noqa: E501
                        failing_metric=missing_metric,
                    )
                    exclusions.append(exclusion)
                else:
                    # No missing required but weighted none due to all weights zero? Keep available
                    status = CalibrationStatus.AVAILABLE
            else:
                status = CalibrationStatus.AVAILABLE

        candidate_summaries.append(
            CalibrationCandidateSummary(
                candidate_id=candidate.candidate_id,
                fingerprint=candidate.fingerprint,
                label=candidate.label,
                status=status,
                alignment_audit=audit,
                metric_results=metric_results,
                residuals=residuals,
                coverage_percentage=candidate_coverage,
                weighted_objective=weighted_objective,
                exclusion=exclusion,
            )
        )

    # Ranking: only available candidates with weighted_objective not None, sorted ascending
    compatible = [
        c
        for c in candidate_summaries
        if c.status == CalibrationStatus.AVAILABLE and c.weighted_objective is not None
    ]
    ranking = [
        c.candidate_id
        for c in sorted(
            compatible,
            key=lambda x: (
                x.weighted_objective if x.weighted_objective is not None else float("inf")
            ),
        )
    ]

    # Build provisional report without fingerprint to compute canonical fingerprint
    # candidate fingerprints sorted already via model canonical, but store sorted
    candidate_fps = sorted([c.fingerprint for c in study.candidates])

    provisional = CalibrationReport(
        report_id=f"{study.study_id}-report",
        study_id=study.study_id,
        study_name=study.study_name,
        observed_fingerprint=study.observed.fingerprint,
        candidate_fingerprints=candidate_fps,
        metric_specs=sorted(study.metric_specs, key=lambda x: x.metric_key),
        alignment_spec=study.alignment_spec,
        candidate_summaries=sorted(candidate_summaries, key=lambda x: x.candidate_id),
        exclusions=sorted(exclusions, key=lambda x: x.candidate_id),
        ranking=ranking,
        fingerprint="0" * 64,
        limitations=LIMITATIONS,
        evidence_boundary=EVIDENCE_BOUNDARY,
    )
    fingerprint = sha256_hex(provisional.to_canonical_bytes())
    # Real report with fingerprint
    report = provisional.model_copy(update={"fingerprint": fingerprint})
    return report


def calibration_report_to_json(report: CalibrationReport) -> str:
    """Deterministic JSON export for report."""
    # Include fingerprint and canonical payload
    data = report.model_dump(mode="json")
    # Ensure deterministic ordering for export
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2)


def calibration_report_to_csv_rows(report: CalibrationReport) -> list[dict[str, object]]:
    """Rows for tabular residual export (CSV)."""
    rows: list[dict[str, object]] = []
    for summary in report.candidate_summaries:
        for r in summary.residuals:
            rows.append(
                {
                    "candidate_id": summary.candidate_id,
                    "sensor_id": r.sensor_id,
                    "window_index": r.window_index,
                    "window_start_utc": r.window_start_utc.isoformat().replace("+00:00", "Z"),
                    "window_end_utc": r.window_end_utc.isoformat().replace("+00:00", "Z"),
                    "metric_key": r.metric_key,
                    "observed_value": r.observed_value,
                    "simulated_value": r.simulated_value,
                    "signed_error": r.signed_error,
                    "absolute_error": r.absolute_error,
                    "relative_error": r.relative_error,
                }
            )
    # Sort deterministically
    rows.sort(
        key=lambda x: (
            str(x["candidate_id"]),
            str(x["sensor_id"]),
            int(str(x["window_index"])),
            str(x["metric_key"]),
        )
    )
    return rows


def export_residuals_csv(report: CalibrationReport) -> str:
    """Export residuals as CSV string with header, deterministic sorted rows."""
    import csv
    import io

    rows = calibration_report_to_csv_rows(report)
    output = io.StringIO()
    if not rows:
        # Still write header
        fieldnames = [
            "candidate_id",
            "sensor_id",
            "window_index",
            "window_start_utc",
            "window_end_utc",
            "metric_key",
            "observed_value",
            "simulated_value",
            "signed_error",
            "absolute_error",
            "relative_error",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        return output.getvalue()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        # Sanitise for spreadsheet injection? Keep numbers as is
        writer.writerow(row)
    return output.getvalue()


def export_candidate_summary_csv(report: CalibrationReport) -> str:
    """Export candidate summary (overall fit) as CSV."""
    import csv
    import io

    output = io.StringIO()
    fieldnames = [
        "candidate_id",
        "label",
        "status",
        "coverage_percentage",
        "weighted_objective",
        "exclusion_reason",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for s in sorted(report.candidate_summaries, key=lambda x: x.candidate_id):
        writer.writerow(
            {
                "candidate_id": s.candidate_id,
                "label": s.label,
                "status": s.status.value,
                "coverage_percentage": s.coverage_percentage,
                "weighted_objective": s.weighted_objective,
                "exclusion_reason": s.exclusion.reason_code if s.exclusion else "",
            }
        )
    return output.getvalue()


def export_metric_results_csv(report: CalibrationReport) -> str:
    """Export per-metric results as CSV."""
    import csv
    import io

    output = io.StringIO()
    fieldnames = [
        "candidate_id",
        "metric_key",
        "unit",
        "count_paired",
        "count_missing_observed",
        "count_missing_simulation",
        "mae",
        "rmse",
        "mean_signed_error",
        "relative_error_mean",
        "coverage_percentage",
        "is_available",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for summary in sorted(report.candidate_summaries, key=lambda x: x.candidate_id):
        for m in sorted(summary.metric_results, key=lambda x: x.metric_key):
            writer.writerow(
                {
                    "candidate_id": summary.candidate_id,
                    "metric_key": m.metric_key,
                    "unit": m.unit,
                    "count_paired": m.count_paired,
                    "count_missing_observed": m.count_missing_observed,
                    "count_missing_simulation": m.count_missing_simulation,
                    "mae": m.mae,
                    "rmse": m.rmse,
                    "mean_signed_error": m.mean_signed_error,
                    "relative_error_mean": m.relative_error_mean,
                    "coverage_percentage": m.coverage_percentage,
                    "is_available": m.is_available,
                }
            )
    return output.getvalue()
