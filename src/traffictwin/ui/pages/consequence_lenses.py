"""Consequence Lenses page — curated traffic and VEC views over existing comparison."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import provenance_badge
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.components.first_run import first_run_guidance
from traffictwin.ui.consequence_cache import session_validate_bundle
from traffictwin.ui.consequence_lenses import (
    ConsequenceLensReport,
    build_consequence_lens_report,
)
from traffictwin.ui.consequence_tables import consequence_lens_table_rows
from traffictwin.ui.formatting import format_scalar
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.services import ServiceError
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def _provenance_badge(synthetic_flag: object) -> str:
    """Shared three-state provenance badge — delegates to ui.components.badges."""

    return provenance_badge(synthetic_flag)


def _format_identity(value: object) -> str:
    """Return display for run/seed/bundle identifiers; None/empty → Unavailable."""

    if value is None:
        return "Unavailable"
    if isinstance(value, str) and not value.strip():
        return "Unavailable"
    # Use truncated fingerprint for long IDs, otherwise raw
    text = str(value).strip()
    return fingerprint_summary(text)


def _format_tri(value: object) -> str:
    """Tri-state display: True→yes, False→no, None/unknown→unknown."""

    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def _row_dicts(report: ConsequenceLensReport, domain: str) -> list[dict[str, object]]:
    """Thin page wrapper — delegates to shared ui.tables helper."""

    return consequence_lens_table_rows(report, domain)


def _render_domain_section(report: ConsequenceLensReport, domain: str, title: str) -> None:
    summary = report.traffic_summary if domain == "traffic" else report.vec_summary
    st.subheader(title)
    with st.container(border=True):
        cols = st.columns(4)
        cols[0].metric("Available", summary.available_count, border=True)
        cols[1].metric("Partial", summary.partial_count, border=True)
        cols[2].metric("Unavailable", summary.unavailable_count, border=True)
        cols[3].metric("Total", len(summary.rows), border=True)
        comparable = summary.available_count + summary.partial_count
        st.caption(f"Comparable (available + partial): {comparable}")
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

    # Draft vs committed state: widget values are draft (consequence_*_path),
    # committed cross-page keys are selected_baseline_run / selected_variation_run
    # which represent last known valid selections. We must not clobber committed
    # state with empty/invalid draft input.
    committed_baseline = str(
        st.session_state.get(
            "selected_baseline_run",
            "tests/fixtures/bundles/baseline_valid",
        )
    )
    committed_variation = str(
        st.session_state.get(
            "selected_variation_run",
            "tests/fixtures/bundles/variation_valid",
        )
    )

    # Ensure widget keys exist before synchronisation to avoid duplicate-default warning
    # (value= is redundant when keys are already seeded; we initialise explicitly).
    if "consequence_baseline_path" not in st.session_state:
        st.session_state["consequence_baseline_path"] = committed_baseline
    if "consequence_variation_path" not in st.session_state:
        st.session_state["consequence_variation_path"] = committed_variation
    # Synchronise keyed widget draft state with authoritative committed pair.
    # Streamlit ignores changed `value=` when a widget key already has persistent
    # widget state, so an external What-If Studio commit would otherwise leave
    # stale draft paths visible and re-commit the stale pair. Detect external
    # change via a marker and explicitly seed the widget keys from the new
    # committed pair before constructing the keyed widgets.
    current_pair = (committed_baseline, committed_variation)
    last_synced = st.session_state.get("_consequence_last_synced_pair")
    # Normalise stored marker to tuple of strings for robust comparison
    if isinstance(last_synced, (list, tuple)) and len(last_synced) == 2:
        try:
            last_pair = (str(last_synced[0]), str(last_synced[1]))
        except Exception:  # pragma: no cover - defensive
            last_pair = None
    else:
        last_pair = None
    if last_pair != current_pair:
        st.session_state["consequence_baseline_path"] = committed_baseline
        st.session_state["consequence_variation_path"] = committed_variation
        st.session_state["_consequence_last_synced_pair"] = current_pair

    baseline_input = st.text_input(
        "Baseline bundle path",
        key="consequence_baseline_path",
    )
    variation_input = st.text_input(
        "Variation bundle path",
        key="consequence_variation_path",
    )
    # Do not commit draft immediately. Draft is baseline_input / variation_input.
    # Committed state is updated atomically only after both inputs are valid.
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

    # Resolve draft strings to paths only after confirming non-empty; Path("") would
    # normalize to "." and must never be written back to committed session state.
    baseline_path = Path(baseline_str)
    variation_path = Path(variation_str)

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

    baseline = session_validate_bundle(baseline_path, st.session_state)
    variation = session_validate_bundle(variation_path, st.session_state)

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

    # Atomic commit: only after both bundles are valid and report built do we
    # update the authoritative cross-page session keys. This prevents blank or
    # invalid draft input from poisoning selected state and keeps the pair atomic.
    st.session_state["selected_baseline_run"] = str(baseline_path)
    st.session_state["selected_variation_run"] = str(variation_path)
    # Keep the synchronisation marker in step with the authoritative pair so
    # our own commit is not misinterpreted as an external change on next render
    # and invalid blank/invalid drafts do not falsely mark sync.
    st.session_state["_consequence_last_synced_pair"] = (
        str(baseline_path),
        str(variation_path),
    )

    # Baseline and variation identities (logical only, no absolute paths)
    st.subheader("Pair identity")
    with st.container(border=True):
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Baseline**")
            baseline_prov = _provenance_badge(report.evidence_standing.get("baseline_synthetic"))
            # Use helper that returns Unavailable for None
            baseline_run = _format_identity(report.evidence_standing.get("baseline_run_id"))
            baseline_seed = _format_identity(report.evidence_standing.get("baseline_seed_id"))
            # For fingerprint we use logical report fingerprint, not bundle path
            st.markdown(
                f"**Provenance:** {baseline_prov} "
                f"**Run:** `{baseline_run}` **Seed:** `{baseline_seed}`"
            )
        with cols[1]:
            st.markdown("**Variation**")
            variation_prov = _provenance_badge(report.evidence_standing.get("variation_synthetic"))
            variation_run = _format_identity(report.evidence_standing.get("variation_run_id"))
            variation_seed = _format_identity(report.evidence_standing.get("variation_seed_id"))
            st.markdown(
                f"**Provenance:** {variation_prov} "
                f"**Run:** `{variation_run}` **Seed:** `{variation_seed}`"
            )
        st.caption(f"Report fingerprint: `{_format_identity(report.fingerprint)}`")
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
        # Local paths are NOT part of report identity; show only as local debug if needed
        with st.expander("Advanced: local bundle paths (not part of report identity)"):
            st.caption("LOCAL PATH — NOT PART OF REPORT IDENTITY. For local debugging only.")
            st.json(
                {
                    "baseline_local_path": str(baseline.source_path),
                    "variation_local_path": str(variation.source_path),
                }
            )

    # Compatibility status (tri-state) — typed model, single authoritative warnings
    st.subheader("Compatibility")
    compat = report.compatibility

    same_exp = compat.same_experiment
    same_seed = compat.same_random_seed
    synthetic_match = compat.synthetic_match
    same_version = compat.same_metric_version
    is_compat = compat.is_compatible
    # Metric versions are per-side typed fields, not dead; display both symmetrically
    baseline_mv = compat.baseline_metric_version
    variation_mv = compat.variation_metric_version
    # Authoritative global warnings live once at report level (not fan-out)
    warning_list: list[str] = list(report.warnings) if isinstance(report.warnings, list) else []
    with st.container(border=True):
        st.markdown(
            f"**Same experiment:** {_format_tri(same_exp)} · "
            f"**Same random seed:** {_format_tri(same_seed)} · "
            f"**Same metric version:** {_format_tri(same_version)} · "
            f"**Synthetic provenance match:** {_format_tri(synthetic_match)}"
        )
        # Symmetric metric version display — both sides visible, unknown truthfully
        baseline_mv_disp = format_scalar(baseline_mv) if baseline_mv is not None else "Unavailable"
        # Treat empty string as unavailable via format_scalar but ensure explicit
        if isinstance(baseline_mv, str) and not baseline_mv.strip():
            baseline_mv_disp = "Unavailable"
        variation_mv_disp = (
            format_scalar(variation_mv) if variation_mv is not None else "Unavailable"
        )
        if isinstance(variation_mv, str) and not variation_mv.strip():
            variation_mv_disp = "Unavailable"
        st.markdown(
            f"**Baseline metric version:** `{baseline_mv_disp}` · "
            f"**Variation metric version:** `{variation_mv_disp}`"
        )
        base_badge = _provenance_badge(report.evidence_standing.get("baseline_synthetic"))
        var_badge = _provenance_badge(report.evidence_standing.get("variation_synthetic"))
        st.markdown(f"**Baseline:** {base_badge} **Variation:** {var_badge}")
        if synthetic_match is False:
            st.warning(
                "Synthetic provenance mismatch: baseline and variation have different "
                "synthetic/imported standing."
            )
        elif synthetic_match is None:
            st.warning("Synthetic provenance is unknown; compatibility cannot be confirmed.")
        if not bool(is_compat):
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
                "compatibility": compat.model_dump(mode="json"),
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
        # Canonical portable export (deterministic, no absolute paths)
        portable_json = report.to_json()
        st.download_button(
            "Download consequence lens JSON",
            data=portable_json,
            file_name=(
                f"{report.fingerprint[:12]}-lens.json"
                if report.fingerprint
                else "consequence-lens.json"
            ),
            mime="application/json",
            key="consequence_download_json",
        )
        # Show portable payload only (no local paths)
        st.json(report.to_portable_dict() | {"fingerprint": report.fingerprint})

    st.caption(
        "Direction is neutral and does not imply improvement or causality. Variation − baseline."
    )
