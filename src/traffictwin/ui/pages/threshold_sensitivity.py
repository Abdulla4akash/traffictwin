"""Interactive deterministic DIA-06 threshold-sensitivity explorer."""

from __future__ import annotations

import streamlit as st

from traffictwin.diagnostics.threshold_sweep import (
    ThresholdSensitivityReport,
    ThresholdSweepStatus,
    threshold_sweep_axis,
)
from traffictwin.evidence.pack import EvidencePack
from traffictwin.rules.config import RuleSetConfig
from traffictwin.ui.charts import threshold_sweep_figure
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import (
    ServiceError,
    evaluate_threshold_sweep_for_ui,
    parse_rule_config_json_for_ui,
    rule_config_json_for_ui,
    sweep_point_config_json_for_ui,
)
from traffictwin.ui.tables import ColumnDisplay, table_column_config

RULE_OPTIONS = {
    "R5 — training-validation maximum gap": "R5",
    "R7 — operational outcome gap": "R7",
    "R8 — completed-task energy": "R8",
}


def render() -> None:
    """Render explicit config exchange and the complete library-computed sweep grid."""

    st.title("Threshold Sensitivity")
    analysis = load_selected_analysis()
    if analysis is None:
        return
    render_source_caption(analysis)
    st.warning(
        "All displayed thresholds are provisional. A sweep is descriptive sensitivity, not "
        "calibration, optimisation, statistical significance, or a recommendation to replace a "
        "default. Every evaluated grid point remains visible."
    )
    if not isinstance(analysis.evidence_pack, EvidencePack):
        st.info("An EvidencePack is required before threshold sensitivity can be evaluated.")
        return

    config = _active_config()
    with st.expander("Complete rule configuration import and export"):
        st.caption(
            "Import applies only after the explicit button below and remains in this browser "
            "session. Downloads do not update the registry, repository, source bundle, or package "
            "defaults."
        )
        uploaded = st.file_uploader(
            "Import complete RuleSetConfig JSON",
            type=["json"],
            key="threshold_sweep_config_upload",
        )
        actions = st.columns(2)
        if actions[0].button("Apply imported rule configuration"):
            if uploaded is None:
                st.error("Choose a complete RuleSetConfig JSON file before applying it.")
            else:
                imported = parse_rule_config_json_for_ui(uploaded.getvalue())
                if isinstance(imported, ServiceError):
                    st.error(imported.message)
                    if imported.detail:
                        st.code(imported.detail)
                else:
                    st.session_state["threshold_sweep_rule_config"] = imported
                    config = imported
                    st.success("Complete rule configuration applied to this session only.")
        if actions[1].button("Use packaged provisional defaults"):
            config = RuleSetConfig()
            st.session_state["threshold_sweep_rule_config"] = config
            st.success("Packaged provisional defaults restored for this session.")
        st.download_button(
            "Export current complete RuleSetConfig JSON",
            data=rule_config_json_for_ui(config),
            file_name="traffictwin-ruleset.json",
            mime="application/json",
        )

    selected_label = st.selectbox("Rule threshold", list(RULE_OPTIONS))
    rule_id = RULE_OPTIONS[str(selected_label)]
    axis = threshold_sweep_axis(rule_id)
    section = getattr(config, rule_id.lower())
    source_threshold = float(getattr(section, axis.field_name))
    st.caption(
        f"Source threshold: {source_threshold:g} {axis.unit} | Parameter: "
        f"{axis.parameter_path} | Boundary: observed ≥ threshold | Ruleset: "
        f"{config.ruleset_version}. Non-swept support and dimension settings stay fixed."
    )

    lower_default, upper_default, step = _default_bounds(rule_id, source_threshold)
    controls = st.columns(3)
    minimum = float(
        controls[0].number_input(
            "Inclusive minimum threshold",
            min_value=0.0,
            value=lower_default,
            step=step,
            format="%.6f",
            key=f"threshold_sweep_minimum_{rule_id}",
        )
    )
    maximum = float(
        controls[1].number_input(
            "Inclusive maximum threshold",
            min_value=0.0,
            max_value=1.0 if rule_id == "R7" else None,
            value=upper_default,
            step=step,
            format="%.6f",
            key=f"threshold_sweep_maximum_{rule_id}",
        )
    )
    point_count = int(
        controls[2].slider(
            "Requested grid points",
            min_value=2,
            max_value=51,
            value=11,
            key=f"threshold_sweep_points_{rule_id}",
        )
    )
    if st.button("Run Threshold Sweep", type="primary"):
        report = evaluate_threshold_sweep_for_ui(
            analysis.evidence_pack,
            rule_id=rule_id,
            minimum_threshold=minimum,
            maximum_threshold=maximum,
            point_count=point_count,
            rule_config=config,
        )
        st.session_state["threshold_sensitivity_report"] = report
        st.session_state["threshold_sweep_source_config"] = config

    result = st.session_state.get("threshold_sensitivity_report")
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            st.code(result.detail)
        return
    if not isinstance(result, ThresholdSensitivityReport):
        st.info("Declare the bounded grid and run the threshold sweep.")
        return
    _render_report(result)


def _render_report(report: ThresholdSensitivityReport) -> None:
    if report.status is not ThresholdSweepStatus.AVAILABLE or report.stability is None:
        st.info(f"{report.reason_code.value}: {report.reason}")
        return
    if report.rule_id != report.request.rule_id:
        st.error("Sweep report rule identity is inconsistent.")
        return

    source_status = report.source_status.value if report.source_status else "unavailable"
    with st.container(border=True):
        st.markdown(f"**Source-threshold rule status:** {badge_markdown(source_status)}")
        summary = st.columns(3)
        summary[0].metric("Evaluated grid points", report.evaluated_point_count, border=True)
        summary[1].metric("Triggered points", report.stability.triggered_point_count, border=True)
        summary[2].metric("Sampled flip intervals", len(report.flip_boundaries), border=True)
        st.caption(
            f"Predeclared grid: {report.requested_point_count} requested points over "
            f"[{report.points[0].threshold:g}, {report.points[-1].threshold:g}] "
            f"{report.threshold_unit}; {report.evaluated_point_count} evaluated. "
            f"Source threshold inserted: {str(report.source_threshold_injected).lower()}. "
            f"Triggered fraction: {report.stability.triggered_fraction:.3f}. "
            "Every grid point stays visible; this is descriptive sensitivity, not an optimum."
        )
        status_counts = report.stability.status_counts
        if status_counts:
            st.caption(
                "Status reconciliation: "
                + " · ".join(f"{state}: {count}" for state, count in sorted(status_counts.items()))
            )

    rows = [
        {
            "ordinal": point.ordinal,
            "threshold": point.threshold,
            "status": point.status.value,
            "triggered": point.triggered,
            "source_threshold": point.is_source_threshold,
            "findings": point.finding_count,
            "missing_evidence": point.missing_evidence_count,
        }
        for point in report.points
    ]
    st.plotly_chart(threshold_sweep_figure(report), width="stretch")
    st.caption(
        f"Threshold-response over the predeclared grid ({report.threshold_unit}). "
        "Unavailable or missing-evidence points remain visible rather than dropped."
    )
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            rows,
            units={"threshold": report.threshold_unit or ""},
            overrides={
                "ordinal": ColumnDisplay(key="ordinal", label="Grid point", hidden=False),
                "missing_evidence": ColumnDisplay(
                    key="missing_evidence", label="Missing evidence", hidden=False
                ),
            },
        ),
    )

    st.subheader("Flip Boundaries And Stability")
    if report.flip_boundaries:
        boundary_rows = [boundary.model_dump(mode="json") for boundary in report.flip_boundaries]
        st.dataframe(
            boundary_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(boundary_rows, units={}),
        )
        st.caption(
            "Each interval is bounded by adjacent sampled points and is not the exact boundary."
        )
    else:
        st.info("No adjacent evaluated points changed trigger membership.")
    nearest = report.nearest_flip
    if nearest is not None and nearest.status.value == "available":
        candidate = nearest.candidates[0]
        st.info(
            f"DIA-05 exact verified nearest flip: {candidate.parameter_path} = "
            f"{candidate.flip_value:g} {candidate.unit}; absolute delta "
            f"{candidate.absolute_delta:g}. This is not a recommended threshold."
        )
    elif nearest is not None:
        st.caption(
            f"Exact DIA-05 nearest flip unavailable: {nearest.reason_code.value} — {nearest.reason}"
        )
    with st.container(border=True):
        st.markdown("**Stability across the grid**")
        stability_columns = st.columns(2)
        stability_columns[0].metric(
            "Status transitions", report.stability.status_transition_count, border=True
        )
        stability_columns[1].metric(
            "Trigger transitions", report.stability.trigger_transition_count, border=True
        )
        identical = "yes" if report.stability.all_statuses_identical else "no"
        monotonic = "yes" if report.stability.triggered_membership_monotonic_prefix else "no"
        st.markdown(
            f"**All statuses identical:** {badge_markdown(identical)} · "
            f"**Monotonic triggered prefix:** {badge_markdown(monotonic)}"
        )

    source_config = st.session_state.get("threshold_sweep_source_config")
    if isinstance(source_config, RuleSetConfig):
        selected_threshold = float(
            st.selectbox(
                "Evaluated threshold to export",
                [point.threshold for point in report.points],
                index=next(
                    (
                        index
                        for index, point in enumerate(report.points)
                        if point.is_source_threshold
                    ),
                    0,
                ),
                format_func=lambda value: f"{float(value):g} {report.threshold_unit}",
            )
        )
        exported = sweep_point_config_json_for_ui(report, source_config, selected_threshold)
        if isinstance(exported, ServiceError):
            st.error(exported.message)
        else:
            st.download_button(
                "Export selected point as complete RuleSetConfig JSON",
                data=exported,
                file_name=f"{report.rule_id.lower()}-{selected_threshold:g}-ruleset.json",
                mime="application/json",
            )

    if report.limitations:
        st.caption("Limitations: " + "; ".join(report.limitations))
    with st.expander("Advanced: per-point result fingerprints"):
        fingerprint_rows = [
            {
                "ordinal": point.ordinal,
                "threshold": point.threshold,
                "result_fingerprint": fingerprint_summary(point.result_fingerprint),
            }
            for point in report.points
        ]
        st.dataframe(
            fingerprint_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                fingerprint_rows,
                hide_machine_ids=False,
                units={"threshold": report.threshold_unit or ""},
                overrides={
                    "result_fingerprint": ColumnDisplay(
                        key="result_fingerprint", label="Result fingerprint", hidden=False
                    )
                },
            ),
        )
        st.caption(f"Report fingerprint: `{report.fingerprint()}`")
    with st.expander("Advanced: complete sweep contract, provenance, and limitations (raw)"):
        st.json(
            {
                "request": report.request.model_dump(mode="json"),
                "source_rule_config": report.source_rule_config,
                "fixed_rule_config": report.fixed_rule_config,
                "provenance": report.provenance,
                "limitations": report.limitations,
                "report_fingerprint": report.fingerprint(),
            }
        )
    st.download_button(
        "Download complete threshold-sensitivity report (JSON)",
        data=report.to_json(),
        file_name=f"{report.evidence_pack_id}-{report.rule_id.lower()}-threshold-sweep.json",
        mime="application/json",
    )


def _active_config() -> RuleSetConfig:
    stored = st.session_state.get("threshold_sweep_rule_config")
    if isinstance(stored, RuleSetConfig):
        return stored
    if isinstance(stored, dict):
        try:
            return RuleSetConfig.model_validate(stored)
        except ValueError:
            pass
    return RuleSetConfig()


def _default_bounds(rule_id: str, source_threshold: float) -> tuple[float, float, float]:
    if rule_id == "R7":
        return 0.0, 1.0, 0.05
    if rule_id == "R5":
        return 0.0, max(0.2, source_threshold * 2.0), 0.01
    return 0.0, max(3.0, source_threshold * 2.0), 0.1
