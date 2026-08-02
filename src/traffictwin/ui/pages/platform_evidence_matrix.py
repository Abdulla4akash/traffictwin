"""Evidence Matrix: coverage and provenance, never pooled effects."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st

from traffictwin.platform.evidence_matrix import EvidenceRole, RowStatus
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.platform_console_services import (
    PlatformConsoleError,
    SourceLink,
    load_evidence_console,
)
from traffictwin.ui.state import UiConfig


def _render_links(links: tuple[SourceLink, ...]) -> None:
    for link in links:
        st.markdown(f"- [{link.label}]({link.url}) — SHA-256 `{link.sha256}`")


def render(config: UiConfig) -> None:
    del config
    st.title("Evidence Matrix")
    badge_row(["READ-ONLY COVERAGE", "NO META-ANALYSIS", "STANDING PRESERVED"])
    st.caption(
        "Digest-pinned coverage across designs, traces, actors, capacities and seeds. Counts are "
        "coverage only: no effects are pooled, completion is not admission, proposed rows remain "
        "evidence=false, and NON_ADMITTED rows stay in a separate explicit view."
    )
    try:
        complete = load_evidence_console(Path.cwd())
    except PlatformConsoleError as error:
        st.warning(f"Evidence Matrix unavailable: {error}")
        return

    traces = ("All traces", *sorted({row.trace_family for row in complete.matrix.rows}))
    statuses = ("All standings", *sorted({row.status for row in complete.matrix.rows}))
    roles = ("All evidence roles", *sorted({row.evidence_role for row in complete.matrix.rows}))
    trace_value = st.selectbox("Evidence trace filter", traces)
    status_value = st.selectbox("Evidence standing filter", statuses)
    role_value = st.selectbox("Evidence role filter", roles)
    include_non_admitted = st.checkbox(
        "Include the separate NON_ADMITTED view",
        value=False,
        help="This never changes a row's standing or adds it to admitted coverage.",
    )
    try:
        console = load_evidence_console(
            Path.cwd(),
            trace_family=None if trace_value == "All traces" else str(trace_value),
            status=(
                None if status_value == "All standings" else cast(RowStatus, str(status_value))
            ),
            evidence_role=(
                None if role_value == "All evidence roles" else cast(EvidenceRole, str(role_value))
            ),
            include_non_admitted=include_non_admitted,
        )
    except PlatformConsoleError as error:
        st.warning(f"Evidence Matrix selection refused: {error}")
        return

    summary = console.summary
    metrics = st.columns(4)
    metrics[0].metric("Included rows", summary.row_count)
    metrics[1].metric("Unique traces", len(summary.unique_traces))
    metrics[2].metric("Unique capacities", len(summary.unique_capacity_arms))
    metrics[3].metric("Unique seeds", len(summary.unique_seeds))
    st.caption(
        f"Matrix build digest `{summary.build_digest}`. Exact included ids: "
        f"{', '.join(summary.row_ids) or 'none'}. NON_ADMITTED included: "
        f"`{str(console.selection.includes_non_admitted).lower()}`."
    )
    if not console.selection.rows:
        st.info(
            "No row matches this selection. The empty cell is a coverage/filter gap, not a zero "
            "and not evidence that a comparison was run."
        )
    else:
        st.dataframe(
            [
                {
                    "design": row.design_id,
                    "standing": row.status,
                    "admission qualifier": row.admission_qualifier,
                    "role": row.evidence_role,
                    "trace": row.trace_family,
                    "actor": row.actor_family,
                    "capacity arms": ", ".join(row.capacity_arms),
                    "seed support": (
                        ", ".join(str(seed) for seed in row.seed_set)
                        if isinstance(row.seed_set, tuple)
                        else row.seed_set
                    ),
                    "primary endpoint": row.primary_endpoint,
                    "deviation": row.execution_deviation or "none recorded",
                    "exclusion": row.exclusion_reason or "included",
                }
                for row in console.selection.rows
            ],
            hide_index=True,
            width="stretch",
        )
    if summary.significance_notes:
        for note in summary.significance_notes:
            st.warning(note)

    st.subheader("Inclusion and exclusion provenance")
    st.dataframe(
        [
            {"design": design_id, "selection outcome": reason}
            for design_id, reason in sorted(console.exclusions.items())
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Exclusion reasons describe this view only; filters never alter source standing or write "
        "back to the experiment registry."
    )

    st.subheader("Digest-bound sources and citations")
    if console.source_links:
        _render_links(console.source_links)
    else:
        st.info("No selected row has a displayable source link because the selection is empty.")
    st.markdown(
        "Producer citation contract: "
        "[docs/producer_citation_requirements.md]"
        "(https://github.com/Abdulla4akash/traffictwin/blob/main/"
        "docs/producer_citation_requirements.md)"
    )
