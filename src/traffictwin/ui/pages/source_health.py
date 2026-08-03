"""Read-only local health for the two configured automatic source workers."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.source_health import (
    SourceHealthError,
    SourceHealthRow,
    load_source_health,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    st.title("Source Health")
    badge_row(["READ-ONLY", "LOCAL METADATA", "NO PROVIDER REQUEST"])
    st.caption(
        "Configuration presence, process-worker state and accepted aggregate control history "
        "for BODS and National Highways. This page never tests credentials, requests a "
        "provider, reveals a private path or identifier, or grants publication permission."
    )
    if config.workspace_path is None:
        st.info(
            "Source health is unavailable until TRAFFICTWIN_WORKSPACE_PATH names a verified "
            "durable v0.7 workspace."
        )
        return
    _render_live_health(str(config.workspace_path))


@st.fragment(run_every="30s")  # type: ignore[untyped-decorator]
def _render_live_health(workspace_path: str) -> None:
    """Rerender local metadata; the service itself performs no network request or write."""

    try:
        report = load_source_health(workspace_path)
    except SourceHealthError as error:
        st.warning(f"Source health unavailable: {error}")
        return

    columns = st.columns(2)
    for column, source in zip(columns, report.sources, strict=True):
        with column.container(border=True):
            _render_source(source)

    st.subheader("Aggregate operational history")
    history_columns = st.columns(3)
    history_columns[0].metric("Journal records", report.aggregate_journal_records)
    history_columns[1].metric(
        "Journal integrity", report.aggregate_journal_integrity.replace("_", " ").upper()
    )
    history_columns[2].metric("Provider quota", "UNKNOWN")
    st.caption(
        "The journal contains aggregate operational observations only. The displayed polling "
        "interval is TrafficTwin's conservative local control, not a provider-published quota."
    )
    st.download_button(
        "Download safe health metadata",
        data=report.download_json(),
        file_name="traffictwin-source-health.json",
        mime="application/json",
        help=(
            "Excludes credentials, hashes, request-scope coordinates, private paths, raw rows "
            "and detector or vehicle identifiers."
        ),
    )
    st.caption(
        f"Local metadata evaluated {_format_time(report.evaluated_at_utc)}. Automatic local "
        "rerender: 30 seconds. Use Manchester Operations for source actions; no public hosting "
        "or scientific evidence is created here."
    )


def _render_source(source: SourceHealthRow) -> None:
    st.subheader(source.source)
    badge_row(
        [
            source.worker_status.upper().replace("_", " "),
            source.configuration_status.upper().replace("_", " "),
            source.truth_state.upper(),
        ]
    )
    metrics = st.columns(3)
    metrics[0].metric("Hot history", source.hot_history_entries)
    metrics[1].metric("Long-term records", source.long_term_journal_records)
    metrics[2].metric(
        "Local interval",
        "OFF"
        if source.conservative_interval_seconds is None
        else f"{source.conservative_interval_seconds}s",
    )
    st.dataframe(
        [
            {"field": "Evidence role", "value": source.evidence_role.replace("_", " ")},
            {"field": "Scope", "value": source.scope},
            {"field": "Credential", "value": "present" if source.credential_present else "absent"},
            {"field": "Request scope", "value": source.request_scope_status},
            {"field": "Last attempt (UTC)", "value": _format_time(source.last_attempt_at_utc)},
            {
                "field": "Last accepted success (UTC)",
                "value": _format_time(source.last_success_at_utc),
            },
            {"field": "Last source time (UTC)", "value": _format_time(source.last_source_time_utc)},
            {
                "field": "Next locally eligible (UTC)",
                "value": _format_time(source.next_locally_eligible_at_utc),
            },
            {"field": "Safe failure code", "value": source.safe_failure_code or "none"},
            {"field": "Aggregate journal", "value": source.long_term_integrity},
            {"field": "Provider limit", "value": "unknown"},
        ],
        hide_index=True,
        width="stretch",
    )
    blockers = (*source.operational_blockers, *source.policy_blockers)
    if blockers:
        with st.expander(f"Blockers ({len(blockers)})"):
            for blocker in blockers:
                st.write(f"- `{blocker}`")
    st.caption(
        f"Decision record: {source.decision_record}. Retention remains owner-controlled; "
        "identifier publication and public hosting are not approved."
    )


def _format_time(value: datetime | None) -> str:
    return "unavailable" if value is None else value.isoformat()
