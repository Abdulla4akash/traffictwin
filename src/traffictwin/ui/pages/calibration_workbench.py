"""Calibration Workbench — thin UI over the deterministic calibration service."""

from __future__ import annotations

import json

import streamlit as st

from traffictwin.calibration.fixtures import (
    make_candidate_good,
    make_candidate_incompatible,
    make_candidate_missing,
    make_candidate_poor,
    make_candidate_temporal_misaligned,
    make_observed_fixture,
)
from traffictwin.calibration.models import (
    CalibrationAlignmentSpec,
    CalibrationCandidate,
    CalibrationMetricSpec,
    CalibrationStudy,
    Direction,
    MissingnessPolicy,
)
from traffictwin.calibration.service import (
    build_calibration_report,
    export_candidate_summary_csv,
    export_metric_results_csv,
    export_residuals_csv,
)

EVIDENCE_NOTICE = (
    "Evidence and authority boundary — read-only descriptive comparison. "
    "Observed evidence is admitted only when bound by fingerprint; synthetic demonstration "
    "evidence is explicitly labelled 'Synthetic demonstration evidence'. No causality is claimed. "
    "No candidate is declared validated, optimal, or true calibration. The weighted objective "
    "ranks candidates only as 'lowest declared objective among compatible candidates' when every "
    "required component is available and compatible."
)

LIMITATIONS_NOTICE = (
    "Limitations: descriptive fit only, no parameter tuning, no SUMO launch, half-open windows "
    "[start,end), no zero-fill of missing evidence, relative error only with safe denominator, "
    "coverage audit enforced, exclusions are fail-closed."
)


def _default_specs() -> list[CalibrationMetricSpec]:
    return [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            direction=Direction.LOWER_IS_BETTER,
            weight=0.6,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            direction=Direction.LOWER_IS_BETTER,
            weight=0.4,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]


def _all_candidates() -> dict[str, CalibrationCandidate]:
    return {
        "candidate_good_fit": make_candidate_good(),
        "candidate_poor_fit": make_candidate_poor(),
        "candidate_incompatible": make_candidate_incompatible(),
        "candidate_missing_evidence": make_candidate_missing(),
        "candidate_temporal_misaligned": make_candidate_temporal_misaligned(),
    }


def render(config: object | None = None) -> None:  # noqa: ARG001
    """Render the Calibration Workbench page."""

    st.title("Calibration Workbench")
    st.caption(
        "Compare & test — Observed-to-Simulation Calibration Workbench. "
        "Read-only descriptive comparison of admitted observed evidence with simulation candidates. "  # noqa: E501
        "Windows use [start,end); missing bins are skipped, never zero-filled."
    )
    st.info(EVIDENCE_NOTICE)
    st.warning(LIMITATIONS_NOTICE)

    observed = make_observed_fixture()
    all_cands = _all_candidates()

    # Observed artifact selection
    st.subheader("Observed evidence")
    st.caption(
        "Fingerprint-bound observed reference. Synthetic demo is labelled synthetic demonstration evidence."  # noqa: E501
    )
    st.markdown(f"**Observed ID:** `{observed.observed_id}`")
    st.markdown(f"**Fingerprint:** `{observed.fingerprint[:16]}…` `{observed.fingerprint}`")
    st.markdown(f"**Label:** {observed.evidence_label}")
    st.markdown(
        f"**Window:** `{observed.window_start_utc.isoformat()}` to `{observed.window_end_utc.isoformat()}`"  # noqa: E501
    )
    st.markdown(
        f"**Bin width:** `{observed.bin_width_s}` s, semantics `[start,end)`, sensors `{', '.join(observed.sensor_ids)}`"  # noqa: E501
    )
    st.markdown(f"**Metric units:** `{observed.metric_units}`")
    st.markdown(f"**Bin count:** `{len(observed.bins)}`")
    with st.expander("Advanced: observed bins (first 10)"):
        for b in observed.bins[:10]:
            st.json(b.model_dump(mode="json"))

    # Candidate selection
    st.subheader("Simulation candidates")
    st.caption("Select one or more imported simulation candidates. Each is bound by fingerprint.")
    options = list(all_cands.keys())
    # Default selection includes good, poor, incompatible as per spec three candidates
    default_selection = ["candidate_good_fit", "candidate_poor_fit", "candidate_incompatible"]
    selected_ids = st.multiselect(
        "Candidates",
        options,
        default=default_selection,
        key="calibration_candidate_multiselect",
        help="Choose at least one candidate to compare against observed evidence",
    )
    if not selected_ids:
        st.info(
            "No candidates selected. Choose at least one simulation candidate to build the calibration comparison. "  # noqa: E501
            "Synthetic demonstration candidates are available above: good-fit, poor-fit, and incompatible/missing."  # noqa: E501
        )
        st.stop()

    # Show selected candidate fingerprints
    for cid in selected_ids:
        cand = all_cands[cid]
        st.markdown(
            f"- **{cand.candidate_id}** — `{cand.label}` | fingerprint `{cand.fingerprint[:12]}…` | unit {cand.metric_units}"  # noqa: E501
        )

    # Metric / weight editor
    st.subheader("Metric specification & weights")
    st.caption(
        "Each metric declares key, version, unit, denominator, direction, weight, alignment requirement, and missingness policy. "  # noqa: E501
        "Weights control the weighted declared objective; objective is available only when every required component is compatible."  # noqa: E501
    )
    default_specs = _default_specs()
    edited_specs: list[CalibrationMetricSpec] = []
    for idx, spec in enumerate(default_specs):
        with st.container(border=True):
            st.markdown(
                f"**Metric {idx + 1}:** `{spec.metric_key}` v{spec.metric_version} unit `{spec.unit}`"  # noqa: E501
            )
            st.caption(
                f"Denominator: {spec.denominator} | Direction: {spec.direction.value} | Missingness: {spec.missingness_policy.value}"  # noqa: E501
            )
            weight = st.slider(
                f"Weight for {spec.metric_key}",
                min_value=0.0,
                max_value=10.0,
                value=float(spec.weight),
                step=0.1,
                key=f"calibration_weight_{spec.metric_key}",
            )
            # Keep other fields same but allow weight editing
            edited_specs.append(
                CalibrationMetricSpec(
                    metric_key=spec.metric_key,
                    metric_version=spec.metric_version,
                    unit=spec.unit,
                    denominator=spec.denominator,
                    direction=spec.direction,
                    weight=weight,
                    alignment_required=spec.alignment_required,
                    missingness_policy=spec.missingness_policy,
                )
            )

    # Alignment spec editor (thin - show but allow no edit for simplicity, but still explicit)
    st.subheader("Alignment specification")
    st.caption(
        "Temporal alignment uses half-open windows [start,end) with bin_width, sensor/link mapping, "  # noqa: E501
        "unit compatibility, coverage audit, exclusion reasons, and missing-bin handling (never zero-filled)."  # noqa: E501
    )
    alignment = CalibrationAlignmentSpec(
        window_start_utc=observed.window_start_utc,
        window_end_utc=observed.window_end_utc,
        bin_width_s=observed.bin_width_s,
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    st.json(alignment.model_dump(mode="json"))

    # Build report
    if st.button("Build calibration report", key="calibration_build_report", type="primary"):
        st.session_state["calibration_last_report_json"] = None  # clear previous
        # Build study
        selected_candidates = [all_cands[cid] for cid in selected_ids]
        study = CalibrationStudy(
            study_id="calibration_demo_study",
            study_name="Calibration Workbench Demo Study",
            description="Synthetic demonstration study; not observed evidence.",
            observed=observed,
            candidates=selected_candidates,
            metric_specs=edited_specs,
            alignment_spec=alignment,
        )
        report = build_calibration_report(study)
        st.session_state["calibration_last_report"] = report.model_dump(mode="json")
        st.session_state["calibration_last_report_obj"] = report
        st.success(f"Built report `{report.report_id}` with fingerprint `{report.fingerprint}`")

    report_obj = st.session_state.get("calibration_last_report_obj")
    if report_obj is None:
        st.info(
            "No report built yet. Adjust metric weights and press 'Build calibration report' to see "  # noqa: E501
            "alignment audit, exclusions, residuals, and candidate ranking. "
            "Empty state: build required before results are shown."
        )
        return

    # From here, render typed service outputs only — no recomputation

    st.subheader("Evidence and authority standing")
    st.info(report_obj.evidence_boundary)
    st.caption(f"Report fingerprint: `{report_obj.fingerprint}`")
    st.caption(f"Observed fingerprint: `{report_obj.observed_fingerprint}`")
    st.caption(
        "Candidates are ranked only as 'lowest declared objective among compatible candidates'"
    )

    # Alignment audit
    st.subheader("Alignment audit")
    audit_rows = []
    for summary in report_obj.candidate_summaries:
        a = summary.alignment_audit
        audit_rows.append(
            {
                "candidate_id": summary.candidate_id,
                "temporal_aligned": a.temporal_aligned,
                "temporal_reason": a.temporal_reason or "",
                "unit_compatible": a.unit_compatible,
                "unit_mismatches": "; ".join(a.unit_mismatches),
                "sensor_mapping_complete": a.sensor_mapping_complete,
                "coverage_%": round(a.coverage_percentage, 1),
                "total_bins": a.total_bins,
                "available_bins": a.available_bins,
                "missing_bins": a.missing_bins,
                "excluded": a.is_excluded,
                "exclusion_code": a.exclusion_reason_code or "",
            }
        )
    st.dataframe(audit_rows, use_container_width=True, hide_index=True)

    # Exclusion table
    st.subheader("Exclusions")
    if report_obj.exclusions:
        excl_rows = [
            {
                "candidate_id": e.candidate_id,
                "reason_code": e.reason_code,
                "reason_detail": e.reason_detail,
                "failing_metric": e.failing_metric or "",
            }
            for e in report_obj.exclusions
        ]
        st.dataframe(excl_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No exclusions — all selected candidates passed alignment and unit checks.")

    # Candidate summary
    st.subheader("Candidate summary")
    st.caption(
        "Descriptive fit: MAE, RMSE, signed error, relative error (safe denominator), coverage %, weighted declared objective."  # noqa: E501
    )
    summary_rows = []
    for s in report_obj.candidate_summaries:
        summary_rows.append(
            {
                "candidate_id": s.candidate_id,
                "label": s.label,
                "status": s.status.value,
                "coverage_%": round(s.coverage_percentage, 1),
                "weighted_objective": s.weighted_objective,
                "exclusion": s.exclusion.reason_code if s.exclusion else "",
            }
        )
    st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    # Ranking
    if report_obj.ranking:
        st.markdown(
            f"**Lowest declared objective among compatible candidates:** `{report_obj.ranking[0]}`"
        )
        st.caption(f"Full ranking (compatible only): {report_obj.ranking}")
    else:
        st.caption(
            "No compatible candidates with a declared objective — ranking unavailable (requires every required component available)."  # noqa: E501
        )

    # Per-metric results
    st.subheader("Per-metric fit")
    metric_rows = []
    for s in report_obj.candidate_summaries:
        for m in s.metric_results:
            metric_rows.append(
                {
                    "candidate_id": s.candidate_id,
                    "metric_key": m.metric_key,
                    "unit": m.unit,
                    "paired": m.count_paired,
                    "missing_obs": m.count_missing_observed,
                    "missing_sim": m.count_missing_simulation,
                    "mae": round(m.mae, 4) if m.mae is not None else None,
                    "rmse": round(m.rmse, 4) if m.rmse is not None else None,
                    "mean_signed": round(m.mean_signed_error, 4)
                    if m.mean_signed_error is not None
                    else None,
                    "rel_err_mean": round(m.relative_error_mean, 4)
                    if m.relative_error_mean is not None
                    else None,
                    "coverage_%": round(m.coverage_percentage, 1),
                    "available": m.is_available,
                }
            )
    if metric_rows:
        st.dataframe(metric_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No per-metric results — all candidates excluded or no paired bins.")

    # Residuals
    st.subheader("Per-location / per-window residuals")
    st.caption(
        "Signed error = simulated − observed, absolute error = |signed|, relative error only with safe denominator."  # noqa: E501
    )
    residual_rows = []
    for s in report_obj.candidate_summaries:
        for r in s.residuals:
            residual_rows.append(
                {
                    "candidate_id": s.candidate_id,
                    "sensor_id": r.sensor_id,
                    "window_index": r.window_index,
                    "metric_key": r.metric_key,
                    "observed": r.observed_value,
                    "simulated": r.simulated_value,
                    "signed_error": r.signed_error,
                    "absolute_error": r.absolute_error,
                    "relative_error": round(r.relative_error, 4)
                    if r.relative_error is not None
                    else None,
                }
            )
    if residual_rows:
        st.dataframe(residual_rows, use_container_width=True, hide_index=True)
        # Simple plot: MAE per candidate (if available)
        try:
            chart_data = {}
            for s in report_obj.candidate_summaries:
                if s.weighted_objective is not None:
                    chart_data[s.candidate_id] = s.weighted_objective
            if chart_data:
                st.bar_chart(chart_data)
        except Exception:  # noqa: S110
            pass
    else:
        st.caption("No residuals — candidates excluded or no paired bins.")

    # Limitations
    st.subheader("Explicit limitations")
    for lim in report_obj.limitations:
        st.markdown(f"- {lim}")

    # Exports
    st.subheader("Exports")
    st.caption("JSON is canonical with sorted keys; CSV is deterministic and tabular.")
    json_text = report_obj.to_canonical_json()
    st.download_button(
        "Download report JSON",
        data=json_text,
        file_name=f"{report_obj.report_id}.json",
        mime="application/json",
        key="calibration_download_json",
    )
    residuals_csv = export_residuals_csv(report_obj)
    st.download_button(
        "Download residuals CSV",
        data=residuals_csv,
        file_name=f"{report_obj.report_id}_residuals.csv",
        mime="text/csv",
        key="calibration_download_residuals_csv",
    )
    summary_csv = export_candidate_summary_csv(report_obj)
    st.download_button(
        "Download candidate summary CSV",
        data=summary_csv,
        file_name=f"{report_obj.report_id}_summary.csv",
        mime="text/csv",
        key="calibration_download_summary_csv",
    )
    metric_csv = export_metric_results_csv(report_obj)
    st.download_button(
        "Download per-metric CSV",
        data=metric_csv,
        file_name=f"{report_obj.report_id}_metrics.csv",
        mime="text/csv",
        key="calibration_download_metrics_csv",
    )
    with st.expander("Advanced: canonical report JSON"):
        st.json(json.loads(json_text))
    with st.expander("Advanced: residuals CSV preview"):
        st.code(
            residuals_csv[:2000] + ("\n… truncated" if len(residuals_csv) > 2000 else ""),
            language="csv",
        )
