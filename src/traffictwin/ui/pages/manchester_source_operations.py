"""Manchester Source Operations page — typed, offline, secret-free."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.manchester_source_operations import (
    build_demonstrator_catalogue,
    build_quality_inputs_for_catalogue,
    catalogue_row_display,
    make_demonstrator_registry,
)
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def render() -> None:
    """Render Manchester Source Operations (Lane 14)."""

    st.title("Manchester Source Operations")

    st.caption(
        "Truthful per-family source standing, credential presence without values, "
        "rights/licence, retention, geography, freshness, snapshots, receipts, "
        "owner actions and CAN/CANNOT contracts. Backed only by Lane 13 frozen "
        "source definitions, catalogue and snapshot registry. Offline, secret-free."
    )
    badge_row(["OFFLINE", "SECRET-FREE", "DETERMINISTIC", "BOUNDED"])

    st.info(
        "This page performs no network retrieval, filesystem discovery, credential "
        "probing, or private persistence. All states are derived from an explicit "
        "typed catalogue and registry; the demonstrator is built through real "
        "models and receipts."
    )

    try:
        catalogue = build_demonstrator_catalogue()
        registry = make_demonstrator_registry(catalogue.evaluated_at_utc)
        diagnostics = build_quality_inputs_for_catalogue(catalogue, registry)
    except Exception:  # pragma: no cover
        st.error(
            "Unable to build demonstrator catalogue (MANCHESTER_SOURCE_OPS_BUILD_FAILED). "
            "Check operational inputs and retry."
        )
        return

    st.caption(
        f"Catalogue evaluated at {catalogue.evaluated_at_utc.isoformat()} · "
        f"registry {catalogue.snapshot_registry_fingerprint[:12]}… · "
        f"method {catalogue.method_version} · schema {catalogue.schema_version}"
    )
    st.caption(
        "Lane-local page: not registered in shared navigation (parent reconciliation deferred); "
        "reachable via direct import `traffictwin.ui.pages.manchester_source_operations:render`."
    )
    st.caption(
        "Demonstrator states: BODS credential-required, DFT/WebTRIS historical-only, "
        "National Highways credential-required, TfGM provider-data-required, "
        "SUMO not-detected, Manual synthetic-available, Static static-available. "
        "No credentials or measured TfGM traffic are claimed."
    )

    st.subheader("Catalogue summary")
    cols = st.columns(4)
    cols[0].metric("Source families", len(catalogue.sources))
    blocked_count = sum(1 for r in catalogue.sources if r.blocker is not None)
    cols[1].metric("Blocked families", blocked_count)
    credential_present = sum(
        1 for r in catalogue.sources if r.credential_presence.value == "present"
    )
    cols[2].metric("Credentials present", credential_present)
    with_receipt = sum(1 for r in catalogue.sources if r.receipt is not None)
    cols[3].metric("With operational receipt", with_receipt)
    st.caption(
        "Counts are per-family and not combined into a quality score. "
        "Each family retains its own evidence standing and freshness contract."
    )
    st.caption(
        "Network access: not performed · Credential values: never displayed · "
        "Directory used as acceptance: never"
    )

    st.subheader("Source operations")
    rows = [catalogue_row_display(r) for r in catalogue.sources]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            rows,
            overrides={
                "family": ColumnDisplay(key="family", label="Family"),
                "provider": ColumnDisplay(key="provider", label="Provider"),
                "semantic_role": ColumnDisplay(key="semantic_role", label="Semantic role"),
                "current_standing": ColumnDisplay(key="current_standing", label="Current standing"),
                "credential_presence": ColumnDisplay(
                    key="credential_presence", label="Credential presence"
                ),
                "rights": ColumnDisplay(key="rights", label="Rights"),
                "licence": ColumnDisplay(key="licence", label="Licence"),
                "retention": ColumnDisplay(key="retention", label="Retention"),
                "supported_geography": ColumnDisplay(
                    key="supported_geography", label="Supported geography"
                ),
                "freshness": ColumnDisplay(key="freshness", label="Freshness"),
                "latest_retrieval": ColumnDisplay(key="latest_retrieval", label="Latest retrieval"),
                "latest_accepted": ColumnDisplay(key="latest_accepted", label="Latest accepted"),
                "latest_rejected": ColumnDisplay(key="latest_rejected", label="Latest rejected"),
                "schema": ColumnDisplay(key="schema", label="Schema"),
                "receipt": ColumnDisplay(key="receipt", label="Receipt"),
                "blocker": ColumnDisplay(key="blocker", label="Blocker"),
                "owner_action": ColumnDisplay(key="owner_action", label="Owner action"),
                "evidence_standing": ColumnDisplay(
                    key="evidence_standing", label="Evidence standing"
                ),
            },
        ),
    )
    st.caption("BODS is bus public-transport operations, never general road traffic.")
    st.caption("DfT is historical; WebTRIS/National Highways are strategic-road external evidence.")
    st.caption("TfGM measured traffic requires provider data — static geography is context only.")
    st.caption("SUMO is simulation tooling/engineering output, never observation.")

    st.subheader("Source detail — CAN/CANNOT and snapshot receipts")
    for row in catalogue.sources:
        display = catalogue_row_display(row)
        with st.expander(f"{row.source.family.value} — {row.source.provider}"):
            st.markdown(f"**Provider:** {display['provider']}")
            st.markdown(f"**Semantic role:** {display['semantic_role']}")
            st.markdown(f"**Evidence standing:** {display['evidence_standing']}")
            st.markdown(f"**Current standing:** {display['current_standing']}")
            st.markdown(f"**Credential presence:** {display['credential_presence']}")
            st.caption("Credential presence only; no secret value is stored or displayed.")
            st.markdown(f"**Rights:** {display['rights']}")
            st.markdown(f"**Licence:** {display['licence']}")
            st.markdown(f"**Retention:** {display['retention']}")
            st.markdown(f"**Supported geography:** {display['supported_geography']}")
            st.markdown(f"**Freshness:** {display['freshness']}")
            st.markdown(f"**Latest retrieval:** {display['latest_retrieval']}")
            st.markdown(f"**Latest accepted:** {display['latest_accepted']}")
            st.markdown(f"**Latest rejected:** {display['latest_rejected']}")
            st.markdown(f"**Schema:** {display['schema']}")
            st.markdown(f"**Receipt:** {display['receipt']}")
            st.markdown(f"**Blocker:** {display['blocker']}")
            st.markdown(f"**Owner action:** {display['owner_action']}")
            if row.tool_version is not None:
                st.markdown(f"**Tool version:** {display['tool_version']}")
            st.markdown(f"**CAN infer:** {display['can_infer']}")
            st.markdown(f"**CANNOT infer:** {display['cannot_infer']}")
            if row.source.family.value == "bods":
                st.warning(
                    "BODS is bus public-transport operations — CANNOT infer general or "
                    "private-vehicle road traffic, traffic volume, or city-wide traffic state."
                )
            if row.source.family.value == "tfgm":
                st.warning(
                    "TfGM measured traffic: PROVIDER_DATA_REQUIRED — no accepted snapshot; "
                    "static signal locations are context, not measured flow."
                )
            if row.source.family.value == "sumo":
                if row.current_standing.value == "not_detected":
                    st.info(
                        "SUMO: NOT_DETECTED — no installation receipt supplied; "
                        "detection requires exact operational metadata and receipt."
                    )
                st.caption("SUMO is simulation output, never observation.")
            if row.source.family.value == "static_manchester_geography":
                st.caption("Static geography is context only — not traffic evidence.")
            if row.latest_accepted_snapshot is not None:
                st.caption(
                    f"Accepted receipt fingerprint: "
                    f"`{row.latest_accepted_snapshot.validation_receipt_fingerprint[:12]}…` "
                    f"(not provenance) validated at "
                    f"{row.latest_accepted_snapshot.validated_at_utc.isoformat()}"
                )
            if row.latest_rejected_snapshot is not None:
                st.caption(
                    f"Rejected: {row.latest_rejected_snapshot.rejection_code} — "
                    f"{row.latest_rejected_snapshot.rejection_reason}"
                )

    st.subheader("Quality and coverage diagnostics")
    st.caption(
        "Each diagnostic is computed from explicit typed inputs only; rates return "
        "None on zero denominators or unavailable inputs and no composite quality "
        "score is invented. Accepted/rejected row counts are in **rows** from the "
        "latest accepted/rejected snapshot record_count only (aggregation: latest "
        "exact pointer per family/state ordered by retrieved_at, no summation). "
        "Components not measured by the snapshot contract (total_expected, missing, "
        "duplicates, interval gaps, parser rejected rows, spatial denominator) are "
        "unavailable and shown as —."
    )
    quality_rows = []
    for family, diag in diagnostics.items():
        quality_rows.append(
            {
                "family": family.value,
                "accepted_rows": diag.accepted_rows,
                "rejected_rows": diag.rejected_rows,
                "rejected_rate": f"{diag.rejected_rate:.3f}"
                if diag.rejected_rate is not None
                else "—",
                "total_expected": "—"
                if diag.total_expected_rows is None
                else str(diag.total_expected_rows),
                "present": "—" if diag.present_rows is None else str(diag.present_rows),
                "missing": "—" if diag.missing_rows is None else str(diag.missing_rows),
                "missingness": f"{diag.missingness:.3f}" if diag.missingness is not None else "—",
                "duplicate_rate": f"{diag.duplicate_rate:.3f}"
                if diag.duplicate_rate is not None
                else "—",
                "spatial_coverage": f"{diag.spatial_coverage_rate:.3f}"
                if diag.spatial_coverage_rate is not None
                else "—",
                "timestamp_range_s": str(diag.timestamp_range_seconds)
                if diag.timestamp_range_seconds is not None
                else "—",
                "freshness_delay_s": str(diag.freshness_delay_seconds)
                if diag.freshness_delay_seconds is not None
                else "—",
                "interval_gaps": diag.interval_gap_count,
                "parser_warnings": diag.parser_warning_count,
                "limitations": "; ".join(diag.limitations) or "—",
            }
        )
    st.dataframe(
        quality_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            quality_rows,
            overrides={
                "family": ColumnDisplay(key="family", label="Family"),
                "missingness": ColumnDisplay(key="missingness", label="Missingness"),
                "duplicate_rate": ColumnDisplay(key="duplicate_rate", label="Duplicate rate"),
                "rejected_rate": ColumnDisplay(key="rejected_rate", label="Rejected rate (rows)"),
                "spatial_coverage": ColumnDisplay(key="spatial_coverage", label="Spatial coverage"),
            },
        ),
    )
    st.caption(
        "Denominators (exact units): missingness = missing_rows (rows) / "
        "total_expected_rows (rows); duplicate_rate = duplicate_rows (rows) / "
        "present_rows (rows); rejected_rate = rejected_rows (rows) / "
        "(accepted_rows (rows) + rejected_rows (rows)); spatial_coverage = "
        "covered_cells / total_cells; "
        "all None on zero/absent denominators; interval gaps where gap > expected interval. "
        "Unavailable (—) means not measured by the snapshot contract — never inferred as 0. "
        "Rejected rate denominator is rows from latest snapshots only, never snapshot counts."
    )
    with st.expander("Advanced: catalogue JSON (secret-free)"):
        st.download_button(
            "Download catalogue JSON",
            data=catalogue.model_dump_json(indent=2),
            file_name=f"{catalogue.snapshot_registry_fingerprint[:12]}-source-operations.json",
            mime="application/json",
            key="source_ops_download_json",
        )
        st.json(catalogue.model_dump(mode="json"))
        st.caption(
            f"Fingerprint: `{catalogue.snapshot_registry_fingerprint[:12]}…` binds "
            f"evaluated_at, registry fingerprint, and all eight families. No secrets, "
            f"no private paths, no network access."
        )

    st.caption(
        "Page backed only by the frozen source definitions, catalogue and snapshot registry; "
        "no duplication of the Evidence Hub or provider adapters. "
        "Any SUMO installation display would require an exact operational receipt."
    )
