"""Manchester Evidence Hub page — source inventory and activation readiness."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.manchester_evidence_hub import (
    RightsRetentionState,
    ScientificGateState,
    build_manchester_hub_view,
)
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def render() -> None:
    """Render Manchester Evidence Hub."""

    st.title("Manchester Evidence Hub")

    st.caption(
        "Source inventory, readiness, evidence standing, activation blockers and next actions. "
        "This hub reuses existing Manchester integration contracts and does not automatically acquire provider data."  # noqa: E501
    )
    badge_row(["OFFLINE", "SECRET-FREE", "DETERMINISTIC", "BOUNDED"])

    workspace_input = st.text_input(
        "Workspace path (optional, local only)",
        value=str(st.session_state.get("selected_workspace", "")),
        key="manchester_hub_workspace",
    )
    workspace: Path | None = Path(workspace_input) if workspace_input.strip() else None
    if workspace_input.strip():
        st.caption(f"LOCAL PATH — NOT PART OF EVIDENCE IDENTITY: `{workspace_input.strip()}`")
        st.caption(
            "This local path is for debugging only and is excluded from the downloadable evidence fingerprint and export."  # noqa: E501
        )
    if workspace is not None and not workspace.exists():
        st.info(f"Workspace path does not exist: {workspace} — showing empty-state readiness.")
        workspace = None

    view = build_manchester_hub_view(workspace)

    # 1. Evidence summary cards — typed-derived, never combined into fake total
    st.subheader("Evidence summary")
    cols = st.columns(5)
    cols[0].metric("Sources known", view.known_source_count)
    cols[1].metric("Accepted", view.accepted_evidence_count)
    cols[2].metric("Acquisition-ready", view.acquisition_ready_count)
    cols[3].metric("Blocked", view.blocked_count)
    cols[4].metric("Unavailable", view.unavailable_count)
    st.caption(f"Workspace: {view.workspace_state} · No provider data fetched on render.")
    st.caption(
        f"Known sources (definitions): {view.known_source_count} — distinct from accepted local evidence sources: {view.accepted_evidence_count}."  # noqa: E501
    )
    st.caption(
        f"Blocked or unavailable (unique): {view.blocked_unavailable_union_count} — never exceeds known sources ({view.known_source_count}); blocked and unavailable overlap honestly."  # noqa: E501
    )
    for w in view.warnings:
        st.caption(w)
    st.info(
        "Counts are per-source and not combined into a Manchester total. Each source retains its own coverage and freshness contract."  # noqa: E501
    )

    # 2. Source readiness table
    st.subheader("Source readiness")
    table_rows = [
        {
            "source": s.display_name,
            "what_it_represents": s.source_role,
            "evidence_ceiling": s.evidence_ceiling,
            "evidence_state": s.local_evidence_state,
            "freshness": s.freshness_state,
            "software_support": s.software_support_state,
            "acquisition_readiness": s.acquisition_readiness,
            "blocking_decision": "; ".join(s.blockers) or "None",
            "next_action": s.next_action,
        }
        for s in view.sources
    ]
    st.dataframe(
        table_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            table_rows,
            overrides={
                "source": ColumnDisplay(key="source", label="Source"),
                "what_it_represents": ColumnDisplay(
                    key="what_it_represents", label="What it represents"
                ),
                "evidence_ceiling": ColumnDisplay(key="evidence_ceiling", label="Evidence ceiling"),
                "evidence_state": ColumnDisplay(key="evidence_state", label="Evidence state"),
                "freshness": ColumnDisplay(key="freshness", label="Freshness"),
                "software_support": ColumnDisplay(key="software_support", label="Software support"),
                "acquisition_readiness": ColumnDisplay(
                    key="acquisition_readiness", label="Acquisition readiness"
                ),
                "blocking_decision": ColumnDisplay(
                    key="blocking_decision", label="Blocking decision"
                ),
            },
        ),
    )

    # 3. Source detail expanders
    st.subheader("Source detail")
    for src in view.sources:
        with st.expander(f"{src.display_name} — {src.source_role}"):
            st.markdown(f"**Coverage:** {src.coverage_scope}")
            st.markdown(f"**Evidence type:** {src.evidence_type}")
            st.markdown(f"**Evidence ceiling:** {src.evidence_ceiling}")
            st.markdown(f"**Freshness:** {src.freshness_state}")
            st.markdown(f"**Software support:** {src.software_support_state}")
            st.markdown(f"**Configuration:** {src.configuration_state}")
            st.markdown(f"**Local evidence:** {src.local_evidence_state}")
            st.markdown(f"**Acquisition readiness:** {src.acquisition_readiness}")
            st.markdown(f"**Rights/retention:** {src.rights_retention_state}")
            st.markdown(f"**Scientific gate:** {src.scientific_gate_state}")
            if src.last_receipt_summary:
                st.caption(f"Last receipt: {src.last_receipt_summary}")
            for lim in src.limitations:
                st.caption(f"Limitation: {lim}")
            if src.blockers:
                st.warning("Blockers: " + "; ".join(src.blockers))
            st.info(f"Next action: {src.next_action}")
            if src.source_id == "bods":
                st.warning(
                    "BODS is live/recent BUS-only positions — NOT general private-vehicle traffic, NOT Manchester-wide road flow."  # noqa: E501
                )
            if src.source_id == "national_highways":
                st.warning(
                    "National Highways is strategic-road operational evidence only — NOT general Manchester city-road coverage."  # noqa: E501
                )
            if src.source_id == "dft":
                st.caption("DfT: historical traffic count evidence — NOT live traffic.")
            if src.source_id == "webtris":
                st.caption(
                    "WebTRIS: historical/latest-available per accepted contract — NOT live city-road traffic."  # noqa: E501
                )
            if src.source_id == "tfgm":
                st.caption(
                    "TfGM: infrastructure/reference only — NOT traffic telemetry unless supplied and accepted."  # noqa: E501
                )
            if src.source_id == "tfgm_ntis_measured_traffic":
                st.warning(
                    "TfGM/NTIS measured traffic: UNAVAILABLE — provider contract required before any adapter or ingestion."  # noqa: E501
                )
            if src.source_id == "static_boundaries":
                st.caption("Static ONS boundaries: geographic context only — NOT traffic evidence.")
            if src.source_id == "manual_incident":
                st.success("Manual incident: AUTHORED SCENARIO INPUT — not an observation.")
            if src.source_id == "social_media":
                st.info("Social media: deferred — no ingestion.")
            if src.source_id == "tfgm_ntis_measured_traffic":
                st.info(
                    "No TfGM/NTIS traffic adapter exists until provider contract, schema, and retention are reviewed."  # noqa: E501
                )

    # 4. Scientific / owner blockers
    st.subheader("Scientific / owner blockers")
    st.info(
        "Software readiness (portfolio, freshness, acquisition controls) is distinct from provider, "  # noqa: E501
        "rights/retention and scientific acceptance. Successful API configuration does not imply scientific acceptance."  # noqa: E501
    )
    st.caption(
        "Display, do not solve, the human/scientific gates — no defaults are invented. "
        "Missing decisions remain blocked until an owner/supervisor decision is recorded."
    )
    blocker_rows = [
        {
            "gate": s.display_name,
            "scientific_state": s.scientific_gate_state,
            "rights_state": s.rights_retention_state,
            "blockers": "; ".join(s.blockers) or "None",
        }
        for s in view.sources
        if s.scientific_gate_typed != ScientificGateState.NOT_APPLICABLE
        or s.rights_typed != RightsRetentionState.RECORDED
    ]
    if blocker_rows:
        st.dataframe(
            blocker_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(blocker_rows),
        )
    else:
        st.success("No scientific/owner blockers beyond displayed source readiness.")
    st.warning(
        "Scientific gates still BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED before calibrated Manchester baseline: "  # noqa: E501
        "boundary/network decision, map-matching policy, ambiguity policy, road-class policy, direction policy, "  # noqa: E501
        "confidence thresholds, 174 named-person map reviews, viable demand, calibration objective, calibration parameter bounds, "  # noqa: E501
        "uncertainty method, development/held-out split, minimum coverage, observed-vs-simulated weighting, missing-data policy "  # noqa: E501
        "— not implemented in this slice."
    )

    # 5. Next actions
    st.subheader("Next actions")
    cols = st.columns(3)
    if cols[0].button("Open Manchester Operations", key="hub_next_manchester_ops"):
        st.switch_page("app_pages/manchester.py")
    navigation_button(
        cols[1].button, "Open Scenario Builder", UiPage.SCENARIO, key="hub_next_scenario"
    )
    navigation_button(
        cols[2].button, "Review Provenance", UiPage.PROVENANCE, key="hub_next_provenance"
    )
    st.caption(
        "Acquisition controls live in Manchester Operations; this hub does not clone them. Manual incident authoring uses Scenario Builder."  # noqa: E501
    )
    with st.expander("Advanced: hub view JSON (secret-free)"):
        # Publication-safe export: view dump contains no secrets or absolute paths;
        # workspace path is deliberately excluded from the model.
        st.download_button(
            "Download hub view JSON",
            data=view.model_dump_json(indent=2),
            file_name=f"{view.fingerprint[:12]}-manchester-hub.json"
            if view.fingerprint
            else "manchester-hub.json",
            mime="application/json",
            key="hub_download_json",
        )
        st.json(view.model_dump(mode="json"))
        st.caption(
            f"Fingerprint: `{view.fingerprint[:12]}…` binds source IDs, roles, evidence ceiling, software support, "  # noqa: E501
            "acquisition state, local evidence presence, freshness, coverage, rights/retention, blocker codes, and next-action class (no secrets, no paths, no wall clock)."  # noqa: E501
        )

    st.caption(
        "This hub never displays API keys, Bearer [REDACTED] or raw credentials; it shows Configured / Not configured only. No network call is made on render."  # noqa: E501
    )
