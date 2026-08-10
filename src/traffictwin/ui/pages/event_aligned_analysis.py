"""Event-Aligned Analysis — thin UI over the deterministic service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from traffictwin.event_aligned.exports import (
    export_phase_summaries_csv,
    export_points_csv,
    export_report_json,
)
from traffictwin.event_aligned.models import EventAlignedReport
from traffictwin.metrics.catalogue import _WINDOW_ANCHORS_BY_KEY, METRIC_DEFINITIONS
from traffictwin.ui.charts import line_figure
from traffictwin.ui.services.event_aligned import compute_event_aligned_for_ui
from traffictwin.ui.services.models import ServiceError
from traffictwin.ui.tables import ColumnDisplay, table_column_config

WINDOW_APPLICABLE_KEYS = sorted(_WINDOW_ANCHORS_BY_KEY.keys())
DEFAULT_METRIC = (
    "task.completion.rate"
    if "task.completion.rate" in WINDOW_APPLICABLE_KEYS
    else WINDOW_APPLICABLE_KEYS[0]
)


def _available_bundle_options() -> list[str]:
    base = Path("tests/fixtures/bundles")
    options: list[str] = []
    if base.exists():
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "manifest.yaml").exists():
                options.append(str(child))
    # Workspace bundles fallback
    workspace = Path(st.session_state.get("selected_bundle_path", ""))
    if workspace and str(workspace) not in options and workspace.exists():
        options.append(str(workspace))
    # Selected baseline/variation from session
    for key in ("selected_baseline_run", "selected_variation_run"):
        val = st.session_state.get(key)
        if val and val not in options and Path(val).exists():
            options.append(val)
    if not options:
        options = [
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/variation_valid",
        ]
    return options


def render() -> None:
    """Render the Event-Aligned Analysis workflow."""

    st.title("Event-Aligned Analysis")
    st.caption(
        "Align compatible temporal evidence around a declared event anchor and compare before, during "  # noqa: E501
        "and after windows. Manual timestamps and authored incidents are labelled authored anchors, not observed incidents. "  # noqa: E501
        "Windows use [start, end). No interpolation is performed; missing bins remain unavailable, not zero-filled. "  # noqa: E501
        "Differences are descriptive during the declared event window, not causal effects."
    )
    st.caption(
        "Canonical time basis: utc_bundle_created_at_offset_v1 — timestamps are seconds offset from bundle created_at in UTC."  # noqa: E501
    )

    options = _available_bundle_options()
    # Run/bundle selectors
    st.subheader("1. Select runs")
    st.caption(
        "Choose 2 to 8 compatible runs or bundles. Metric name, version, unit and denominator compatibility is enforced."  # noqa: E501
    )
    selected = st.multiselect(
        "Bundles (2–8)",
        options,
        default=options[:2] if len(options) >= 2 else options,
        key="event_aligned_bundles",
    )
    if len(selected) < 2:
        st.info("Select at least two bundles to build the aligned analysis.")
        return
    if len(selected) > 8:
        st.error("Select at most 8 bundles.")
        return

    st.subheader("2. Select metric")
    metric_key = st.selectbox(
        "Supported metric",
        WINDOW_APPLICABLE_KEYS,
        index=WINDOW_APPLICABLE_KEYS.index(DEFAULT_METRIC),
    )
    definition = METRIC_DEFINITIONS[str(metric_key)]
    st.caption(
        f"Metric: `{definition.key}` | Version: `{definition.implementation_version}` | Unit: `{definition.unit}` | "  # noqa: E501
        f"Domain: `{definition.domain.value}` | Window anchor: `{definition.time_anchor}`"
    )
    st.caption(f"Human name: {definition.human_name}")

    st.subheader("3. Choose event anchor")
    st.caption(
        "All anchors are authored, not observed. Choose from declared bundle/scenario event metadata, authored incident metadata, or a manual authored timestamp."  # noqa: E501
    )
    anchor_kind = st.selectbox(
        "Event anchor kind",
        ["bundle_declared_event", "authored_incident", "manual_authored_timestamp"],
        index=2,
        help="Manual timestamps and authored incidents are labelled authored anchors, not observed incidents.",  # noqa: E501
    )
    kind_label_map = {
        "bundle_declared_event": "Authored — Bundle declared event",
        "authored_incident": "Authored — Incident",
        "manual_authored_timestamp": "Authored — Manual timestamp",
    }
    st.caption(f"Source label: {kind_label_map[anchor_kind]}")

    # Per-run anchor timestamps
    st.caption(
        "Per-run authored timestamps (timezone-aware ISO8601). Example: 2026-07-17T12:00:05+00:00"
    )
    anchor_timestamps: list[str] = []
    # Suggest defaults based on each bundle's created_at + 5s
    from traffictwin.ingestion.bundle import validate_bundle

    for path_str in selected:
        default_ts = "2026-07-17T12:00:05Z"
        try:
            result = validate_bundle(Path(path_str))
            if result.manifest and result.manifest.bundle.created_at.tzinfo is not None:
                ca = result.manifest.bundle.created_at.astimezone(UTC)
                # Suggest 5 seconds after creation for demo
                suggested = ca.replace(microsecond=0) + __import__("datetime").timedelta(  # noqa: S110
                    seconds=5
                )
                default_ts = suggested.isoformat().replace("+00:00", "Z")
        except Exception:  # noqa: S110
            pass
        ts = st.text_input(
            f"Anchor for {Path(path_str).name}", value=default_ts, key=f"anchor_{path_str}"
        )
        anchor_timestamps.append(ts)

    st.subheader("4. Choose windows")
    c1, c2, c3, c4 = st.columns(4)
    pre_duration = float(
        c1.number_input(
            "Pre-event duration (s)", min_value=0.001, value=10.0, step=5.0, key="pre_dur"
        )
    )
    event_duration = float(
        c2.number_input(
            "Event duration (s)", min_value=0.001, value=10.0, step=5.0, key="event_dur"
        )
    )
    post_duration = float(
        c3.number_input(
            "Post-event duration (s)", min_value=0.001, value=10.0, step=5.0, key="post_dur"
        )
    )
    bin_width = float(
        c4.number_input("Bin width (s)", min_value=0.001, value=5.0, step=1.0, key="bin_w")
    )

    st.subheader("5. Preview exact half-open windows")
    # Show preview for first anchor
    try:
        from traffictwin.event_aligned.models import EventAlignedWindowSpec

        definition = METRIC_DEFINITIONS[str(metric_key)]
        preview_spec = EventAlignedWindowSpec(
            pre_duration_s=pre_duration,
            event_duration_s=event_duration,
            post_duration_s=post_duration,
            bin_width_s=bin_width,
            metric_key=str(metric_key),
            metric_version=definition.implementation_version,
            metric_unit=definition.unit,
        )
        first_anchor_dt = datetime.fromisoformat(anchor_timestamps[0].replace("Z", "+00:00"))
        if first_anchor_dt.tzinfo is None:
            st.error("Anchor timestamps must be timezone-aware; naive timestamps are rejected.")
        else:
            preview = preview_spec.preview_windows(first_anchor_dt)
            rows = [
                {
                    "phase": name,
                    "window_start_utc": start.isoformat().replace("+00:00", "Z"),
                    "window_end_utc": end.isoformat().replace("+00:00", "Z"),
                    "boundary": "[start,end)",
                }
                for name, (start, end) in preview.items()
            ]
            st.dataframe(rows, hide_index=True, width="stretch")
            st.caption(
                f"Pre: [{rows[0]['window_start_utc']}, {rows[0]['window_end_utc']}) | "
                f"Event: [{rows[1]['window_start_utc']}, {rows[1]['window_end_utc']}) | "
                f"Post: [{rows[2]['window_start_utc']}, {rows[2]['window_end_utc']}) — half-open, deterministic bin boundaries."  # noqa: E501
            )
            st.caption(
                f"Total bins: {preview_spec.total_bins()} (pre {pre_duration / bin_width:.1f}, event {event_duration / bin_width:.1f}, post {post_duration / bin_width:.1f})"  # noqa: E501
            )
    except Exception as exc:
        st.error(f"Window preview error: {exc}")

    # Build button
    if st.button("Build aligned analysis", type="primary", key="build_event_aligned"):
        result = compute_event_aligned_for_ui(
            bundle_paths=selected,
            metric_key=str(metric_key),
            pre_duration_s=pre_duration,
            event_duration_s=event_duration,
            post_duration_s=post_duration,
            bin_width_s=bin_width,
            anchor_kind=str(anchor_kind),
            anchor_timestamps=anchor_timestamps,
            anchor_labels=[kind_label_map[str(anchor_kind)]] * len(selected),
        )
        if isinstance(result, ServiceError):
            st.session_state["event_aligned_report"] = result
        else:
            st.session_state["event_aligned_report"] = result

    report = st.session_state.get("event_aligned_report")
    if isinstance(report, ServiceError):
        st.error(report.message)
        if report.detail:
            st.code(report.detail)
        return
    if not isinstance(report, EventAlignedReport):
        st.info("Choose the temporal contract and build the aligned analysis.")
        return

    # Verify fingerprint excludes generated_at
    if not report.verify_fingerprint():
        st.warning("Fingerprint verification failed; report may be corrupted.")

    with st.container(border=True):
        st.markdown("**Report identity**")
        cols = st.columns(3)
        cols[0].metric("Accepted runs", len(report.accepted_runs), border=True)
        cols[1].metric("Excluded runs", len(report.excluded_runs), border=True)
        cols[2].metric("Metric points", len(report.metric_points), border=True)
        st.caption(
            f"Report ID: `{report.report_id}` | Fingerprint: `{report.fingerprint[:12]}…` | Canonical time basis: `{report.canonical_time_basis}`"  # noqa: E501
        )
        st.caption(
            f"Spec: pre {report.spec.pre_duration_s}s, event {report.spec.event_duration_s}s, post {report.spec.post_duration_s}s, bin {report.spec.bin_width_s}s, metric {report.spec.metric_key} v{report.spec.metric_version} ({report.spec.metric_unit})"  # noqa: E501
        )
        with st.expander("Advanced: fingerprint and canonical JSON"):
            st.code(
                f"fingerprint: {report.fingerprint}\ncanonical_json: {report.canonical_json()[:800]}…",  # noqa: E501
                language="json",
            )

    # Warnings and limitations
    for w in report.warnings:
        st.warning(w)
    with st.expander("Limitations"):
        for lim in report.limitations:
            st.write(f"- {lim}")

    # Excluded runs
    if report.excluded_runs:
        st.subheader("Excluded runs and reasons")
        excl_rows = [
            {"run_id": r.run_id, "reason_code": r.reason_code, "reason_detail": r.reason_detail}
            for r in report.excluded_runs
        ]
        st.dataframe(excl_rows, hide_index=True, width="stretch")
    else:
        st.caption("No runs were excluded; all selected runs are compatible.")

    # Per-run anchor source
    st.subheader("Per-run anchor provenance")
    anchor_rows = [
        {
            "run_id": r.run_id,
            "anchor_kind": r.anchor.kind.value,
            "source_label": r.anchor.source_label,
            "anchor_time_utc": r.anchor.anchor_time_utc.isoformat().replace("+00:00", "Z"),
            "bundle_id": r.bundle_id,
        }
        for r in report.accepted_runs
    ]
    st.dataframe(anchor_rows, hide_index=True, width="stretch")
    st.caption("All anchors are labelled authored, not observed incidents.")

    # Before/during/after summaries
    st.subheader("Before / During / After summaries")
    for summary in sorted(report.phase_summaries, key=lambda s: (s.run_id, s.phase.value)):
        with st.container(border=True):
            st.markdown(f"**{summary.run_id} — {summary.phase.value}** — {summary.metric_key}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Bins", summary.bin_count, border=True)
            m2.metric("Available", summary.available_count, border=True)
            m3.metric("Empty", summary.empty_count, border=True)
            m4.metric("Partial", summary.partial_count, border=True)
            if summary.mean_value is not None:
                st.caption(
                    f"Mean {summary.mean_value:.4f} | Min {summary.min_value:.4f} | Max {summary.max_value:.4f} | Median {summary.median_value:.4f} {summary.metric_unit}"  # noqa: E501
                )
            else:
                st.caption(
                    "No available numeric values for this phase (missing bins are not zero-filled)."
                )

    # Pairwise deltas
    if report.pairwise_deltas:
        st.subheader("Pairwise descriptive differences (not causal)")
        delta_rows = [
            {
                "baseline": d.baseline_run_id,
                "variation": d.variation_run_id,
                "phase": d.phase.value,
                "baseline_mean": d.baseline_mean,
                "variation_mean": d.variation_mean,
                "absolute_difference": d.absolute_difference,
                "description": d.description,
            }
            for d in report.pairwise_deltas
        ]
        st.dataframe(delta_rows, hide_index=True, width="stretch")
        for d in report.pairwise_deltas:
            st.caption(d.description)
    else:
        st.caption(
            "No pairwise deltas available (requires at least two accepted runs with available values)."  # noqa: E501
        )

    # Relative-time series and chart
    st.subheader("Relative-time series")
    st.caption(
        "Chart and table consume the same report rows. Missing bins are unavailable, not zero-filled."  # noqa: E501
    )
    chart_rows = []
    for point in sorted(report.metric_points, key=lambda p: (p.run_id, p.bin_index)):
        chart_rows.append(
            {
                "run_id": point.run_id,
                "phase": point.phase.value,
                "relative_start_s": point.relative_start_s,
                "relative_end_s": point.relative_end_s,
                "relative_mid_s": (point.relative_start_s + point.relative_end_s) / 2,
                "value": point.value,
                "status": point.status,
                "coverage_state": point.coverage_state.value,
                "coverage_fraction": point.coverage_fraction,
                "bin_index": point.bin_index,
            }
        )
    st.dataframe(
        chart_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            chart_rows,
            hide_machine_ids=False,
            units={"relative_start_s": "s", "relative_end_s": "s", "coverage_fraction": ""},
            number_formats={"coverage_fraction": "%.3f", "value": "%.4f"},
            overrides={
                "value": ColumnDisplay(key="value", label="Metric value", hidden=False),
                "coverage_state": ColumnDisplay(
                    key="coverage_state", label="Coverage", hidden=False
                ),
            },
        ),
    )

    # Chart: filter available only
    available_for_chart = [
        r for r in chart_rows if r["status"] == "available" and isinstance(r["value"], (int, float))
    ]
    if available_for_chart:
        # Build line figure per run over relative_mid_s
        # line_figure expects x_key and y_keys
        st.plotly_chart(
            line_figure(
                available_for_chart,
                x_key="relative_mid_s",
                y_keys=["value"],
                title=f"{report.spec.metric_key} by relative time (event at 0)",
                y_title=f"Metric value ({report.spec.metric_unit})",
            ),
            width="stretch",
        )
        # Alternative multi-run faceting: if multiple runs, show per-run lines using same y but distinguish?  # noqa: E501
        # For simplicity, show value vs relative_mid colored by run? Our line_figure doesn't support hue, so we note.  # noqa: E501
        st.caption(
            "Chart plots only available windows over already-computed values; same rows as table."
        )
    else:
        st.info("No available numeric windows to chart.", icon=":material/info:")

    # Coverage and gap table
    st.subheader("Coverage and gap table")
    gap_rows = [
        {
            "run_id": p.run_id,
            "bin_index": p.bin_index,
            "phase": p.phase.value,
            "relative_window": f"[{p.relative_start_s}, {p.relative_end_s})",
            "absolute_window": f"[{p.absolute_window_start_utc.isoformat().replace('+00:00', 'Z')}, {p.absolute_window_end_utc.isoformat().replace('+00:00', 'Z')})",  # noqa: E501
            "coverage_state": p.coverage_state.value,
            "coverage_fraction": p.coverage_fraction,
            "status": p.status,
            "value": p.value if p.value is not None else "",
            "source_counts": json.dumps(p.source_record_counts, sort_keys=True),
        }
        for p in report.metric_points
    ]
    st.dataframe(gap_rows, hide_index=True, width="stretch")
    st.caption(
        "Empty bins stay visible with unavailable status; a missing metric is never filled with zero. Partial bins are truncated final phase bins."  # noqa: E501
    )

    # Exports
    st.subheader("Portable exports")
    st.caption(
        "Deterministic JSON and tabular CSV. Fingerprint excludes wall clock, rendering state, local paths and secrets."  # noqa: E501
    )
    json_data = export_report_json(report)
    csv_points = export_points_csv(report)
    csv_summaries = export_phase_summaries_csv(report)
    st.download_button(
        "Download JSON (deterministic)",
        data=json_data,
        file_name=f"{report.report_id}.json",
        mime="application/json",
        key="dl_json",
    )
    st.download_button(
        "Download points CSV",
        data=csv_points,
        file_name=f"{report.report_id}_points.csv",
        mime="text/csv",
        key="dl_points_csv",
    )
    st.download_button(
        "Download summaries CSV",
        data=csv_summaries,
        file_name=f"{report.report_id}_summaries.csv",
        mime="text/csv",
        key="dl_summaries_csv",
    )

    with st.expander("Advanced: raw report JSON"):
        st.json(report.model_dump(mode="json"))
