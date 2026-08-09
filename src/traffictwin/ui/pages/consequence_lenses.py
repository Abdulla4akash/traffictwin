"""Consequence Lenses page — curated traffic and VEC views over existing comparison."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.components.first_run import first_run_guidance
from traffictwin.ui.consequence_lenses import (
    ConsequenceLensReport,
    build_consequence_lens_report,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.services import ServiceError, validate_bundle_for_ui
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def _provenance_badge(synthetic_flag: object) -> str:
    if synthetic_flag is None:
        return ":gray-badge[UNKNOWN]"
    return badge_markdown("synthetic") if bool(synthetic_flag) else ":gray-badge[IMPORTED]"


def _format_value(value: object) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _row_dicts(report: ConsequenceLensReport, domain: str) -> list[dict[str, object]]:
    summary = report.traffic_summary if domain == "traffic" else report.vec_summary
    rows: list[dict[str, object]] = []
    for row in summary.rows:
        rows.append(
            {
                "metric_key": row.metric_key,
                "label": row.label,
                "status": row.status,
                "baseline": _format_value(row.baseline),
                "variation": _format_value(row.variation),
                "absolute_delta": _format_value(row.absolute_delta),
                "relative_delta": _format_value(row.relative_delta),
                "unit": row.unit or "",
                "direction": _direction(row.absolute_delta, row.status),
                "reason_codes": ", ".join(row.reason_codes),
                "denominator": row.denominator_description or "",
            }
        )
    return rows


def _direction(delta: float | None, status: str) -> str:
    if status == "unavailable":
        return "unavailable"
    if delta is None:
        return "unavailable"
    if delta > 0:
        return "increased"
    if delta < 0:
        return "decreased"
    return "unchanged"


def _render_domain_section(report: ConsequenceLensReport, domain: str, title: str) -> None:
    summary = report.traffic_summary if domain == "traffic" else report.vec_summary
    st.subheader(title)
    with st.container(border=True):
        cols = st.columns(3)
        cols[0].metric("Available", summary.available_count, border=True)
        cols[1].metric("Unavailable", summary.unavailable_count, border=True)
        cols[2].metric("Total", len(summary.rows), border=True)
        if summary.warnings:
            st.warning("\n".join(summary.warnings))
    rows = _row_dicts(report, domain)
    if rows:
        st.dataframe(
            rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                rows,
                overrides={
                    "metric_key": ColumnDisplay(key="metric_key", label="Metric", hidden=False),
                    "label": ColumnDisplay(key="label", label="Label", hidden=False),
                    "absolute_delta": ColumnDisplay(
                        key="absolute_delta",
                        label="Variation − baseline",
                        hidden=False,
                    ),
                },
            ),
        )
    else:
        st.info(f"No {domain} consequence rows available.")
    # Unavailable reasons visible
    unavailable = [row for row in summary.rows if row.status == "unavailable"]
    if unavailable:
        st.caption(f"{len(unavailable)} {domain} metrics are unavailable with exact reason codes.")
        with st.expander(f"Advanced: {domain} unavailable reasons"):
            reason_rows = [
                {
                    "metric_key": row.metric_key,
                    "reason_codes": ", ".join(row.reason_codes),
                    "compatibility_findings": "; ".join(row.compatibility_findings),
                }
                for row in unavailable
            ]
            st.dataframe(
                reason_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(reason_rows),
            )
    # Denominator wording
    denom_rows = [row for row in summary.rows if row.denominator_description is not None]
    if denom_rows:
        with st.expander(f"Advanced: {domain} denominator definitions"):
            denom_table = [
                {
                    "metric_key": row.metric_key,
                    "denominator": row.denominator_description or "",
                }
                for row in denom_rows
            ]
            st.dataframe(
                denom_table,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(denom_table),
            )


def render() -> None:
    """Render Consequence Lenses page."""

    st.title("Consequence Lenses")

    baseline_input = st.text_input(
        "Baseline bundle path",
        value=str(
            st.session_state.get(
                "selected_baseline_run",
                "tests/fixtures/bundles/baseline_valid",
            )
        ),
        key="consequence_baseline_path",
    )
    variation_input = st.text_input(
        "Variation bundle path",
        value=str(
            st.session_state.get(
                "selected_variation_run",
                "tests/fixtures/bundles/variation_valid",
            )
        ),
        key="consequence_variation_path",
    )
    baseline_path = Path(baseline_input)
    variation_path = Path(variation_input)
    st.session_state["selected_baseline_run"] = str(baseline_path)
    st.session_state["selected_variation_run"] = str(variation_path)

    # Empty and failure states
    baseline_str = baseline_input.strip()
    variation_str = variation_input.strip()
    if not baseline_str or not variation_str:
        st.error("Both baseline and variation bundle paths must be selected.")
        first_run_guidance(
            actions=[
                ("Start Guided Demo", UiPage.GUIDED_DEMO),
                ("Import a Run Bundle", UiPage.BUNDLE_IMPORT),
                ("Open Compare", UiPage.COMPARE),
            ],
            message=(
                "No baseline/variation pair is selected. Use Bundle Import to select "
                "example bundles, or enter two existing bundle paths above. The current "
                "product's Compare page also uses these same session keys."
            ),
            key_prefix="consequence_no_pair",
        )
        return

    if not baseline_path.exists() and not variation_path.exists():
        st.error("Both baseline and variation bundle paths do not exist.")
        first_run_guidance(
            actions=[
                ("Start Guided Demo", UiPage.GUIDED_DEMO),
                ("Import a Run Bundle", UiPage.BUNDLE_IMPORT),
            ],
            message=(
                "A consequence view needs two existing run bundles. The guided demo creates "
                "a baseline and a stressed variation, or import your own bundles."
            ),
            key_prefix="consequence_both_missing",
        )
        return
    if not baseline_path.exists():
        st.error(f"Baseline bundle path does not exist: {baseline_path}")
        st.info("Baseline is missing. Enter a valid baseline bundle path.")
        return
    if not variation_path.exists():
        st.error(f"Variation bundle path does not exist: {variation_path}")
        st.info("Variation is missing. Enter a valid variation bundle path.")
        return

    baseline = validate_bundle_for_ui(baseline_path)
    variation = validate_bundle_for_ui(variation_path)

    if not baseline.analysis_ready:
        st.error("Baseline bundle is invalid and cannot be used for consequence lenses.")
        with st.expander("Advanced: baseline validation report"):
            st.json(baseline.validation.report.model_dump(mode="json"))
        return
    if not variation.analysis_ready:
        st.error("Variation bundle is invalid and cannot be used for consequence lenses.")
        with st.expander("Advanced: variation validation report"):
            st.json(variation.validation.report.model_dump(mode="json"))
        return

    report = build_consequence_lens_report(baseline, variation)
    if isinstance(report, ServiceError):
        st.error(report.message)
        if report.detail:
            st.caption(report.detail)
        return

    # Baseline and variation identities
    st.subheader("Pair identity")
    with st.container(border=True):
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Baseline**")
            st.code(str(baseline.source_path), language=None)
            baseline_prov = _provenance_badge(report.evidence_standing.get("baseline_synthetic"))
            baseline_run = fingerprint_summary(str(report.evidence_standing.get("baseline_run_id")))
            baseline_seed = fingerprint_summary(
                str(report.evidence_standing.get("baseline_seed_id"))
            )
            st.markdown(
                f"**Provenance:** {baseline_prov} "
                f"**Run:** `{baseline_run}` **Seed:** `{baseline_seed}`"
            )
            fp = fingerprint_summary(str(report.evidence_standing.get("baseline_fingerprint")))
            st.caption(f"Bundle fingerprint: `{fp}`")
        with cols[1]:
            st.markdown("**Variation**")
            st.code(str(variation.source_path), language=None)
            variation_prov = _provenance_badge(report.evidence_standing.get("variation_synthetic"))
            variation_run = fingerprint_summary(
                str(report.evidence_standing.get("variation_run_id"))
            )
            variation_seed = fingerprint_summary(
                str(report.evidence_standing.get("variation_seed_id"))
            )
            st.markdown(
                f"**Provenance:** {variation_prov} "
                f"**Run:** `{variation_run}` **Seed:** `{variation_seed}`"
            )
            var_fp = fingerprint_summary(str(report.evidence_standing.get("variation_fingerprint")))
            st.caption(f"Bundle fingerprint: `{var_fp}`")
        st.caption(f"Report fingerprint: `{fingerprint_summary(report.fingerprint)}`")
        if report.fingerprint:
            with st.expander("Advanced: full fingerprints and identities"):
                st.json(
                    {
                        "baseline_identity": report.baseline_identity,
                        "variation_identity": report.variation_identity,
                        "evidence_standing": report.evidence_standing,
                        "fingerprint": report.fingerprint,
                    }
                )

    # Compatibility status
    st.subheader("Compatibility")
    compat = report.compatibility
    same_exp = bool(compat.get("same_experiment"))
    same_seed = bool(compat.get("same_random_seed"))
    warnings = compat.get("warnings")
    warning_list: list[str] = warnings if isinstance(warnings, list) else []
    with st.container(border=True):
        st.markdown(
            f"**Same experiment:** {'yes' if same_exp else 'no'} · "
            f"**Same random seed:** {'yes' if same_seed else 'no'} · "
            f"**Metric version:** {report.baseline_identity.get('metric_version')}"
        )
        base_badge = _provenance_badge(report.evidence_standing.get("baseline_synthetic"))
        var_badge = _provenance_badge(report.evidence_standing.get("variation_synthetic"))
        st.markdown(f"**Baseline:** {base_badge} **Variation:** {var_badge}")
        if not bool(compat.get("is_compatible")):
            st.warning(
                "Pair is not fully compatible. Deltas for mismatched metrics "
                "are withheld with exact reasons."
            )
        if warning_list:
            st.warning("\n".join(str(item) for item in warning_list))
    with st.expander("Advanced: raw compatibility context JSON"):
        st.json(
            {
                "baseline_context": report.baseline_identity,
                "variation_context": report.variation_identity,
                "compatibility": compat,
                "warnings": report.warnings,
            }
        )

    # Changed scenario parameters
    st.subheader("Changed scenario parameters")
    if report.changed_seed_parameters:
        change_rows = [
            {
                "path": str(change.get("path", "")),
                "baseline": str(change.get("baseline", "")),
                "variation": str(change.get("variation", "")),
            }
            for change in report.changed_seed_parameters
        ]
        st.dataframe(
            change_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(change_rows),
        )
    else:
        st.info("No seed snapshots or parameter changes available.")

    # Traffic consequences
    _render_domain_section(report, "traffic", "Traffic consequences")
    st.info(
        "These are deterministic consequences observed in the selected "
        "imported or synthetic runs. They are not a live Manchester forecast "
        "or proof that the intervention caused the difference."
    )

    # VEC consequences
    _render_domain_section(report, "vec", "VEC consequences")
    st.info(
        "These are deterministic VEC outcomes for the selected runs. They do not prove "
        "that an algorithm, RSU placement or infrastructure intervention caused the difference."
    )

    # Evidence and denominators summary
    st.subheader("Evidence and denominators")
    st.caption(
        "Completion rates are reported over generated valid tasks; deadline-miss rates over "
        "completed tasks with observed latency; decision shares over recognised decisions. "
        "Missing or partial evidence is kept unavailable, never zero-filled. "
        "An unavailable metric retains its exact reason codes and missing-evidence description."
    )
    if report.warnings:
        st.caption("Warnings: " + "; ".join(report.warnings))

    # Navigation actions
    st.subheader("Continue")
    cols = st.columns(3)
    navigation_button(
        cols[0].button,
        "Open full Compare",
        UiPage.COMPARE,
        key="consequence_nav_compare",
        width="stretch",
    )
    navigation_button(
        cols[1].button,
        "Open Provenance",
        UiPage.PROVENANCE,
        key="consequence_nav_provenance",
        width="stretch",
    )
    navigation_button(
        cols[2].button,
        "Open Reports",
        UiPage.REPORTS,
        key="consequence_nav_reports",
        width="stretch",
    )
    st.caption(
        "View baseline or variation in Run Overview via the Bundle Import selection, "
        "or continue to full Compare."
    )
    with st.expander("Advanced: consequence lens JSON export"):
        st.download_button(
            "Download consequence lens JSON",
            data=report.to_json(),
            file_name=(
                f"{report.fingerprint[:12]}-lens.json"
                if report.fingerprint
                else "consequence-lens.json"
            ),
            mime="application/json",
            key="consequence_download_json",
        )
        st.json(report.model_dump(mode="json"))

    st.caption(
        "Direction is neutral and does not imply improvement or causality. Variation − baseline."
    )
