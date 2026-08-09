"""Manchester Evidence Hub page — source inventory and activation readiness."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.manchester_evidence_hub import build_manchester_hub_view
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def render() -> None:
    """Render Manchester Evidence Hub."""

    st.title("Manchester Evidence Hub")

    # Evidence summary — offline, secret-free
    st.caption(
        "Source inventory, readiness, evidence standing, activation blockers and next actions. "
        "This hub reuses existing Manchester integration contracts and does not automatically acquire provider data."
    )
    badge_row(["OFFLINE", "SECRET-FREE", "DETERMINISTIC", "BOUNDED"])

    # Determine workspace for local evidence checks (offline, no network)
    workspace_input = st.text_input(
        "Workspace path (optional, local only)",
        value=str(st.session_state.get("selected_workspace", "")),
        key="manchester_hub_workspace",
    )
    workspace: Path | None = Path(workspace_input) if workspace_input.strip() else None
    if workspace is not None and not workspace.exists():
        st.info(f"Workspace path does not exist: {workspace} — showing empty-state readiness.")
        workspace = None

    view = build_manchester_hub_view(workspace)

    # 1. Evidence summary cards
    st.subheader("Evidence summary")
    cols = st.columns(4)
    cols[0].metric("Sources known", len(view.sources))
    cols[1].metric("Accepted local evidence", view.accepted_evidence_count)
    cols[2].metric("Acquisition-ready", view.available_count)
    cols[3].metric("Blocked/unavailable", view.blocked_count + view.unavailable_count)
    st.caption(f"Workspace: {view.workspace_state} · No provider data fetched on render.")
    for w in view.warnings:
        st.caption(w)
    # Do not combine incompatible counts into fake total
    st.info(
        "Counts are per-source and not combined into a Manchester total. Each source retains its own coverage and freshness contract."
    )

    # 2. Source readiness table
    st.subheader("Source readiness")
    table_rows = [
        {
            "source": s.display_name,
            "what_it_represents": s.source_role,
            "evidence_state": s.local_evidence_state,
            "freshness": s.freshness_state,
            "local_artifact": s.last_receipt_summary or "—",
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
                "what_it_represents": ColumnDisplay(key="what_it_represents", label="What it represents"),
                "evidence_state": ColumnDisplay(key="evidence_state", label="Evidence state"),
                "freshness": ColumnDisplay(key="freshness", label="Freshness"),
                "acquisition_readiness": ColumnDisplay(key="acquisition_readiness", label="Acquisition readiness"),
                "blocking_decision": ColumnDisplay(key="blocking_decision", label="Blocking decision"),
            },
        ),
    )

    # 3. Source detail expanders
    st.subheader("Source detail")
    for src in view.sources:
        with st.expander(f"{src.display_name} — {src.source_role}"):
            st.markdown(f"**Coverage:** {src.coverage_scope}")
            st.markdown(f"**Evidence type:** {src.evidence_type}")
            st.markdown(f"**Freshness:** {src.freshness_state}")
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
            # Truthful per-source warnings
            if src.source_id == "bods":
                st.warning("BODS is live/recent BUS positions only — NOT general private-vehicle traffic, NOT Manchester-wide road flow.")
            if src.source_id == "national_highways":
                st.warning("National Highways is strategic-road operational evidence only — NOT general Manchester city-road coverage.")
            if src.source_id == "dft":
                st.caption("DfT: historical traffic count evidence — NOT live traffic.")
            if src.source_id == "manual_incident":
                st.success("Manual incident: AUTHORED SCENARIO INPUT — not an observation.")
            if src.source_id == "social_media":
                st.info("Social media: deferred — no ingestion.")

    # 4. Scientific / owner blockers
    st.subheader("Scientific / owner blockers")
    st.info(
        "Software readiness (portfolio, freshness, acquisition controls) is distinct from provider, "
        "rights/retention and scientific acceptance. Successful API configuration does not imply scientific acceptance."
    )
    blocker_rows = [
        {
            "gate": s.display_name,
            "scientific_state": s.scientific_gate_state,
            "rights_state": s.rights_retention_state,
            "blockers": "; ".join(s.blockers) or "None",
        }
        for s in view.sources
        if "BLOCKED" in s.scientific_gate_state or "REQUIRED" in s.rights_retention_state
    ]
    if blocker_rows:
        st.dataframe(blocker_rows, hide_index=True, width="stretch", column_config=table_column_config(blocker_rows))
    else:
        st.success("No scientific/owner blockers beyond displayed source readiness.")
    st.warning(
        "Scientific gates still BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED before calibrated Manchester baseline: "
        "map matching policy, ambiguity threshold, road-class policy, calibration objective, parameter bounds, "
        "uncertainty, development/held-out split, minimum coverage, comparison weighting, missing-data handling, "
        "174 map-review decisions, viable demand — not implemented in this slice."
    )

    # 5. Next actions
    st.subheader("Next actions")
    cols = st.columns(3)
    if cols[0].button("Open Manchester Operations", key="hub_next_manchester_ops"):
        st.switch_page("app_pages/manchester.py")
    navigation_button(cols[1].button, "Open Scenario Builder", UiPage.SCENARIO, key="hub_next_scenario")
    navigation_button(cols[2].button, "Review Provenance", UiPage.PROVENANCE, key="hub_next_provenance")
    st.caption("Acquisition controls live in Manchester Operations; this hub does not clone them. Manual incident authoring uses Scenario Builder.")
    with st.expander("Advanced: hub view JSON (secret-free)"):
        st.download_button(
            "Download hub view JSON",
            data=view.model_dump_json(indent=2),
            file_name=f"{view.fingerprint[:12]}-manchester-hub.json" if view.fingerprint else "manchester-hub.json",
            mime="application/json",
            key="hub_download_json",
        )
        st.json(view.model_dump(mode="json"))
        st.caption(f"Fingerprint: `{view.fingerprint[:12]}…` binds source IDs, evidence states, freshness, readiness, blockers and accepted artifact IDs (no secrets).")

    st.caption("This hub never displays API keys, bearer tokens or raw credentials; it shows Configured / Not configured only. No network call is made on render.")
