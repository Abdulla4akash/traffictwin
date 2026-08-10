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
    "Weighted declared normalized objective ranks candidates only when every required component is available and compatible.",  # noqa: E501
    "Scalar objective uses explicit declared per-metric normalization scales to become dimensionless; raw MAEs of different units are never summed.",  # noqa: E501
    "Lowest declared normalized objective among compatible candidates is not a validated model claim.",  # noqa: E501
    "No synthetic evidence is relabelled as observed.",
    "No production-readiness or Manchester evidence is claimed unless genuine admitted evidence is supplied.",  # noqa: E501
]


def _safe_relative_error(signed_error: float, observed: float) -> float | None:
    if abs(observed) < 1e-9:
        return None
    return signed_error / observed


def _pairing_key(
    sensor_id: str,
    window_index: int,
    metric_key: str,
) -> tuple[str, int, str]:
    return (sensor_id, window_index, metric_key)


def _mapped_candidate_sensor(
    observed_sensor: str,
    sensor_mapping: dict[str, str],
) -> str:
    return sensor_mapping.get(observed_sensor, observed_sensor)


def _compute_alignment_audit(
    *,
    candidate: CalibrationCandidate,
    observed: CalibrationObservedReference,
    specs: list[CalibrationMetricSpec],
    study: CalibrationStudy,
) -> CalibrationAlignmentAudit:
    tol = study.alignment_spec.temporal_tolerance_s
    obs_start = observed.window_start_utc
    obs_end = observed.window_end_utc
    cand_start = candidate.window_start_utc
    cand_end = candidate.window_end_utc
    bin_width_match = abs(candidate.bin_width_s - observed.bin_width_s) < 1e-9
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

    # Unit compatibility: check observed AND candidate against spec, deduplicate
    mismatch_set: set[str] = set()
    for spec in specs:
        # Observed metric_units
        obs_unit = observed.metric_units.get(spec.metric_key)
        if obs_unit is not None and obs_unit != spec.unit:
            mismatch_set.add(f"{spec.metric_key}: observed expected {spec.unit!r} got {obs_unit!r}")
        # Candidate metric_units
        cand_unit = candidate.metric_units.get(spec.metric_key)
        if cand_unit is not None and cand_unit != spec.unit:
            mismatch_set.add(
                f"{spec.metric_key}: candidate expected {spec.unit!r} got {cand_unit!r}"
            )
        # If not in metric_units, check per-bin units: observed bins
        obs_bin_units = {b.unit for b in observed.bins if b.metric_key == spec.metric_key}
        for u in obs_bin_units:
            if u != spec.unit:
                mismatch_set.add(
                    f"{spec.metric_key}: observed bin unit {u!r} != spec {spec.unit!r}"
                )
        cand_bin_units = {b.unit for b in candidate.bins if b.metric_key == spec.metric_key}
        for u in cand_bin_units:
            if u != spec.unit:
                mismatch_set.add(
                    f"{spec.metric_key}: candidate bin unit {u!r} != spec {spec.unit!r}"
                )
        # If units sets disagree internally but we already captured spec mismatch, deduplicate is enough  # noqa: E501
    mismatches = sorted(mismatch_set)
    unit_compatible = len(mismatches) == 0

    # Sensor mapping completeness
    sensor_map = study.alignment_spec.sensor_mapping
    missing_sensors: list[str] = []
    if sensor_map:
        for obs_sensor, sim_sensor in sensor_map.items():
            if obs_sensor not in observed.sensor_ids:
                missing_sensors.append(f"observed mapping key missing: {obs_sensor}")
            if sim_sensor not in candidate.sensor_ids:
                missing_sensors.append(
                    f"candidate mapping target missing: {sim_sensor} for {obs_sensor}"
                )
    else:
        for s in observed.sensor_ids:
            if (
                s not in candidate.sensor_ids
                and _mapped_candidate_sensor(s, sensor_map) not in candidate.sensor_ids
            ):
                missing_sensors.append(s)
    sensor_mapping_complete = len(missing_sensors) == 0

    # Coverage will be computed via pairing logic in _compute_metric_results, but for audit we compute preliminary  # noqa: E501
    # Use eligible reference bins definition: observed bins that belong to declared spec, in window, non-missing observed value  # noqa: E501
    # For audit, we compute eligible count and paired count via same pairing function
    # To avoid duplication, call helper that computes coverage directly
    # We compute here by reusing the same _eligible_and_paired logic
    eligible, paired, extra = _count_eligible_paired_extra(
        observed=observed,
        candidate=candidate,
        specs=specs,
        sensor_mapping=sensor_map,
    )
    total_bins = eligible
    available_bins = paired
    missing_bins = max(0, eligible - paired)
    coverage_pct = (paired / eligible * 100.0) if eligible > 0 else 0.0
    extra_count = extra

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
    elif coverage_pct < study.alignment_spec.coverage_threshold * 100.0 - 1e-9:
        # Strictly less than threshold is insufficient; equal is accepted
        excluded = True
        reason_code = ExclusionReasonCode.COVERAGE_INSUFFICIENT.value
        reason_detail = f"coverage {coverage_pct:.1f}% < threshold {study.alignment_spec.coverage_threshold * 100:.1f}%"  # noqa: E501

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
        extra_candidate_bin_count=extra_count,
        is_excluded=excluded,
        exclusion_reason_code=reason_code,
        exclusion_detail=reason_detail,
    )


def _build_candidate_index(
    candidate: CalibrationCandidate,
) -> dict[tuple[str, int, str], CalibrationBin]:
    # Returns mapping from candidate sensor's pairing key to bin and its window bounds for exact half-open check  # noqa: E501
    # Key is (candidate_sensor_id, window_index, metric_key)
    idx: dict[tuple[str, int, str], CalibrationBin] = {}
    for b in candidate.bins:
        key = (b.sensor_id, b.window_index, b.metric_key)
        if key not in idx:
            idx[key] = b
    return idx


def _count_eligible_paired_extra(
    *,
    observed: CalibrationObservedReference,
    candidate: CalibrationCandidate,
    specs: list[CalibrationMetricSpec],
    sensor_mapping: dict[str, str],
) -> tuple[int, int, int]:
    """Return (eligible, paired, extra) counts for coverage audit."""
    spec_keys = {s.metric_key for s in specs}
    # Build candidate index for fast lookup using mapped sensor
    cand_idx: dict[tuple[str, int, str], CalibrationBin] = {}
    for b in candidate.bins:
        key = (b.sensor_id, b.window_index, b.metric_key)
        if key not in cand_idx:
            cand_idx[key] = b

    # Observed eligible bins
    eligible_keys: set[tuple[str, int, str]] = set()
    for b in observed.bins:
        if b.metric_key not in spec_keys:
            continue
        # Must lie in analysis window (already enforced via model, but double-check half-open)
        if (
            b.window_start_utc < observed.window_start_utc
            or b.window_end_utc > observed.window_end_utc
        ):
            continue
        # Observed value must be non-missing to be eligible
        if b.value is None:
            continue
        # Sensor must be in requested set (observed sensor_ids)
        if b.sensor_id not in observed.sensor_ids:
            continue
        eligible_keys.add((b.sensor_id, b.window_index, b.metric_key))

    paired = 0
    for key in eligible_keys:
        obs_sensor, win_idx, metric = key
        # Find observed bin for this key to get its window bounds
        obs_bin = next(
            (
                x
                for x in observed.bins
                if x.sensor_id == obs_sensor
                and x.window_index == win_idx
                and x.metric_key == metric
            ),
            None,
        )
        if obs_bin is None:
            continue
        mapped = _mapped_candidate_sensor(obs_sensor, sensor_mapping)
        cand_key = (mapped, win_idx, metric)
        cand_bin = cand_idx.get(cand_key)
        if cand_bin is None:
            continue
        # Half-open window start/end must match exactly
        if (
            obs_bin.window_start_utc != cand_bin.window_start_utc
            or obs_bin.window_end_utc != cand_bin.window_end_utc
        ):
            continue
        # Unit already checked via audit, but require candidate value not None and unit compatible
        if cand_bin.value is None:
            continue
        # If units incompatible, not paired (audit already marks excluded, but for coverage we still not count)  # noqa: E501
        # Check unit compatibility for this specific bin
        # We already know spec unit, but we can check quickly
        spec_unit = next((s.unit for s in specs if s.metric_key == metric), None)
        if spec_unit is not None and cand_bin.unit != spec_unit:
            continue
        if obs_bin.unit != spec_unit:
            continue
        paired += 1

    # Extra candidate bins: candidate bins whose mapped observed counterpart is not in eligible set  # noqa: E501
    # For this count, we consider any candidate bin where there is no eligible observed counterpart (or observed extra)  # noqa: E501
    # We use the same key space: candidate bins that are not pairable because no eligible observed bin exists  # noqa: E501
    extra = 0
    for b in candidate.bins:
        # Reverse mapping: which observed sensor would map to this candidate sensor?  # noqa: E501
        # Inverting sensor_mapping; if mapping empty, observed sensor == candidate sensor
        # For counting extra, we treat extra as candidate bins where no observed eligible bin exists for that mapped key  # noqa: E501
        # Find observed sensor that maps to this candidate sensor
        observed_sensor_for_cand: str | None = None
        if sensor_mapping:
            for obs_s, cand_s in sensor_mapping.items():
                if cand_s == b.sensor_id:
                    observed_sensor_for_cand = obs_s
                    break
            if observed_sensor_for_cand is None:
                # candidate sensor not in mapping values -> not part of declared pairing, count as extra?  # noqa: E501
                # If candidate sensor is not a mapped target, it's extra unless observed has same id and mapping empty  # noqa: E501
                extra += 1
                continue
        else:
            observed_sensor_for_cand = b.sensor_id
        key = (observed_sensor_for_cand, b.window_index, b.metric_key)
        if key not in eligible_keys:
            extra += 1
    return (len(eligible_keys), paired, extra)


def _build_index(
    bins: list[CalibrationBin],
) -> dict[tuple[str, int, str], CalibrationBin]:
    idx: dict[tuple[str, int, str], CalibrationBin] = {}
    for b in bins:
        key = (b.sensor_id, b.window_index, b.metric_key)
        if key not in idx:
            idx[key] = b
    return idx


def _compute_metric_results_and_residuals(
    *,
    observed: CalibrationObservedReference,
    candidate: CalibrationCandidate,
    specs: list[CalibrationMetricSpec],
    audit: CalibrationAlignmentAudit,
    sensor_mapping: dict[str, str],
) -> tuple[list[CalibrationMetricResult], list[CalibrationResidual], float]:
    if audit.is_excluded:
        return [], [], 0.0

    # Build candidate index keyed by candidate sensor
    candidate_idx: dict[tuple[str, int, str], CalibrationBin] = {}
    for b in candidate.bins:
        key = (b.sensor_id, b.window_index, b.metric_key)
        if key not in candidate_idx:
            candidate_idx[key] = b

    metric_results: list[CalibrationMetricResult] = []
    residuals: list[CalibrationResidual] = []
    overall_available = 0
    overall_total = 0
    for spec in specs:
        observed_bins_for_metric = [
            b for b in observed.bins if b.metric_key == spec.metric_key and b.value is not None
        ]
        # For coverage we consider only non-missing observed as eligible  # noqa: E501
        # But for missing counts we need all observed bins for diagnostic  # noqa: E501
        all_observed_for_metric = [b for b in observed.bins if b.metric_key == spec.metric_key]
        count_paired = 0
        count_missing_obs = sum(1 for b in all_observed_for_metric if b.value is None)
        # count_missing_sim will be counted as eligible but missing candidate
        count_missing_sim = 0
        errors: list[float] = []
        signed_errors: list[float] = []
        relative_errors: list[float] = []

        for obs_bin in observed_bins_for_metric:
            # Eligible observed bin (non-missing)
            mapped_sensor = _mapped_candidate_sensor(obs_bin.sensor_id, sensor_mapping)
            key = (mapped_sensor, obs_bin.window_index, obs_bin.metric_key)
            cand_bin = candidate_idx.get(key)
            if cand_bin is None:
                count_missing_sim += 1
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
            # Check half-open window exact match
            if (
                obs_bin.window_start_utc != cand_bin.window_start_utc
                or obs_bin.window_end_utc != cand_bin.window_end_utc
            ):
                count_missing_sim += 1
                residuals.append(
                    CalibrationResidual(
                        sensor_id=obs_bin.sensor_id,
                        window_index=obs_bin.window_index,
                        window_start_utc=obs_bin.window_start_utc,
                        window_end_utc=obs_bin.window_end_utc,
                        metric_key=spec.metric_key,
                        observed_value=obs_bin.value,
                        simulated_value=cand_bin.value,
                        signed_error=None,
                        absolute_error=None,
                        relative_error=None,
                    )
                )
                continue
            # Check unit compatibility for this bin (already validated)
            if cand_bin.unit != spec.unit or obs_bin.unit != spec.unit:
                count_missing_sim += 1
                residuals.append(
                    CalibrationResidual(
                        sensor_id=obs_bin.sensor_id,
                        window_index=obs_bin.window_index,
                        window_start_utc=obs_bin.window_start_utc,
                        window_end_utc=obs_bin.window_end_utc,
                        metric_key=spec.metric_key,
                        observed_value=obs_bin.value,
                        simulated_value=cand_bin.value,
                        signed_error=None,
                        absolute_error=None,
                        relative_error=None,
                    )
                )
                continue
            sim_val = cand_bin.value
            if sim_val is None:
                count_missing_sim += 1
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
            # Both available
            obs_val = obs_bin.value
            assert obs_val is not None
            assert sim_val is not None
            signed = sim_val - obs_val
            abs_err = abs(signed)
            rel = _safe_relative_error(signed, obs_val)
            errors.append(abs_err)
            signed_errors.append(signed)
            if rel is not None:
                relative_errors.append(abs(rel))

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

        # Missing observed bins not paired  # noqa: E501
        # count_missing_obs already computed as number of missing observed bins for this metric
        total_for_metric = len(observed_bins_for_metric)  # eligible denominator
        coverage_pct = (count_paired / total_for_metric * 100.0) if total_for_metric > 0 else 0.0
        is_available = count_paired > 0

        mae: float | None = None
        rmse: float | None = None
        mean_signed: float | None = None
        rel_mean: float | None = None
        normalized_mae: float | None = None
        if count_paired > 0:
            mae = sum(errors) / len(errors) if errors else None
            sq = [(s**2) for s in signed_errors]
            rmse = math.sqrt(sum(sq) / len(sq)) if sq else None
            mean_signed = sum(signed_errors) / len(signed_errors) if signed_errors else None
            rel_mean = sum(relative_errors) / len(relative_errors) if relative_errors else None
            if mae is not None and spec.objective_scale is not None and spec.objective_scale > 0:
                normalized_mae = mae / spec.objective_scale
        else:
            mae = None
            rmse = None
            mean_signed = None
            rel_mean = None
            normalized_mae = None

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
                normalized_mae=normalized_mae,
                objective_scale=spec.objective_scale,
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
    spec_by_key = {s.metric_key: s for s in specs}
    total_weight = 0.0
    weighted_sum = 0.0
    for res in metric_results:
        spec = spec_by_key.get(res.metric_key)
        if spec is None:
            continue
        if spec.weight == 0:
            continue
        # Require positive scale for positive weight
        if spec.objective_scale is None or not (spec.objective_scale > 0):
            return None
        if not res.is_available or res.mae is None or res.normalized_mae is None:
            return None
        weighted_sum += spec.weight * res.normalized_mae
        total_weight += spec.weight
    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def build_calibration_report(study: CalibrationStudy) -> CalibrationReport:
    candidate_summaries: list[CalibrationCandidateSummary] = []
    exclusions: list[CalibrationExclusion] = []

    for candidate in study.candidates:
        audit = _compute_alignment_audit(
            candidate=candidate,
            observed=study.observed,
            specs=study.metric_specs,
            study=study,
        )
        metric_results, residuals, overall_coverage = _compute_metric_results_and_residuals(
            observed=study.observed,
            candidate=candidate,
            specs=study.metric_specs,
            audit=audit,
            sensor_mapping=study.alignment_spec.sensor_mapping,
        )

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
            candidate_coverage = audit.coverage_percentage
            metric_results = []
            residuals = []
        else:
            candidate_coverage = overall_coverage if metric_results else audit.coverage_percentage
            weighted_objective = _compute_weighted_objective(
                metric_results=metric_results, specs=study.metric_specs
            )
            if weighted_objective is None:
                any_missing_required = any(
                    (not r.is_available)
                    for r in metric_results
                    for s in study.metric_specs
                    if s.metric_key == r.metric_key and s.alignment_required and s.weight > 0
                )
                # Also missing scale triggers unavailable
                any_missing_scale = any(
                    s.weight > 0 and (s.objective_scale is None or s.objective_scale <= 0)
                    for s in study.metric_specs
                )
                if any_missing_required or any_missing_scale:
                    status = CalibrationStatus.UNAVAILABLE
                    missing_metric = next(
                        (r.metric_key for r in metric_results if not r.is_available), None
                    )
                    # Determine failing metric for scale vs missing
                    if any_missing_scale:
                        failing = next(
                            (
                                s.metric_key
                                for s in study.metric_specs
                                if s.weight > 0
                                and (s.objective_scale is None or s.objective_scale <= 0)
                            ),
                            None,
                        )
                        exclusion = CalibrationExclusion(
                            candidate_id=candidate.candidate_id,
                            reason_code=ExclusionReasonCode.MISSING_REQUIRED_METRIC.value,
                            reason_detail="positive-weight metric missing scale; objective unavailable",  # noqa: E501
                            failing_metric=failing,
                        )
                    else:
                        exclusion = CalibrationExclusion(
                            candidate_id=candidate.candidate_id,
                            reason_code=ExclusionReasonCode.MISSING_REQUIRED_METRIC.value,
                            reason_detail="required metric has no paired bins; objective unavailable",  # noqa: E501
                            failing_metric=missing_metric,
                        )
                    exclusions.append(exclusion)
                else:
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

    compatible = [
        c
        for c in candidate_summaries
        if c.status == CalibrationStatus.AVAILABLE and c.weighted_objective is not None
    ]
    # Deterministic tie-break by candidate_id
    ranking = [
        c.candidate_id
        for c in sorted(
            compatible,
            key=lambda x: (
                x.weighted_objective if x.weighted_objective is not None else float("inf"),
                x.candidate_id,
            ),
        )
    ]

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
    report = provisional.model_copy(update={"fingerprint": fingerprint})
    return report


def calibration_report_to_json(report: CalibrationReport) -> str:
    data = report.model_dump(mode="json")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2)


def calibration_report_to_csv_rows(report: CalibrationReport) -> list[dict[str, object]]:
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
    import csv
    import io

    from traffictwin.data_contract.fingerprint import sanitise_for_csv

    rows = calibration_report_to_csv_rows(report)
    output = io.StringIO()
    if not rows:
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
        sanitized = {
            k: sanitise_for_csv(str(v))
            if isinstance(v, str) and k in ("candidate_id", "sensor_id", "metric_key")
            else v
            for k, v in row.items()
        }
        writer.writerow(sanitized)
    return output.getvalue()


def export_candidate_summary_csv(report: CalibrationReport) -> str:
    import csv
    import io

    from traffictwin.data_contract.fingerprint import sanitise_for_csv

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
                "candidate_id": sanitise_for_csv(s.candidate_id),
                "label": sanitise_for_csv(s.label),
                "status": sanitise_for_csv(s.status.value),
                "coverage_percentage": s.coverage_percentage,
                "weighted_objective": s.weighted_objective,
                "exclusion_reason": sanitise_for_csv(
                    s.exclusion.reason_code if s.exclusion else ""
                ),
            }
        )
    return output.getvalue()


def export_metric_results_csv(report: CalibrationReport) -> str:
    import csv
    import io

    from traffictwin.data_contract.fingerprint import sanitise_for_csv

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
        "normalized_mae",
        "objective_scale",
        "coverage_percentage",
        "is_available",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for summary in sorted(report.candidate_summaries, key=lambda x: x.candidate_id):
        for m in sorted(summary.metric_results, key=lambda x: x.metric_key):
            writer.writerow(
                {
                    "candidate_id": sanitise_for_csv(summary.candidate_id),
                    "metric_key": sanitise_for_csv(m.metric_key),
                    "unit": sanitise_for_csv(m.unit),
                    "count_paired": m.count_paired,
                    "count_missing_observed": m.count_missing_observed,
                    "count_missing_simulation": m.count_missing_simulation,
                    "mae": m.mae,
                    "rmse": m.rmse,
                    "mean_signed_error": m.mean_signed_error,
                    "relative_error_mean": m.relative_error_mean,
                    "normalized_mae": m.normalized_mae,
                    "objective_scale": m.objective_scale,
                    "coverage_percentage": m.coverage_percentage,
                    "is_available": m.is_available,
                }
            )
    return output.getvalue()
