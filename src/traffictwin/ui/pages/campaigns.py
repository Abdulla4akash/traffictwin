"""Campaigns page: a read-only inventory of one campaign receipt at a time.

A thin surface over :mod:`traffictwin.ui.campaigns_services`. The person names
one receipt file; the page shows the design identity it records, the approval
provenance it carries, one row per declared cell, and what the run consumed.

Three statements the page keeps visible rather than implied. A receipt is a
terminal record, so nothing here is live or running. This page reads receipts
only — no registry is opened and no scientific number is computed or shown. And
it never searches: without a typed path it shows nothing, which is what keeps an
executing campaign's directory closed.
"""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.campaigns_services import (
    NOT_LIVE_STATEMENT,
    CampaignReceiptView,
    CampaignsError,
    approval_rows,
    arm_summaries,
    budget_usage,
    cell_rows,
    declared_seeds,
    identity_rows,
    load_campaign_receipt,
    phase_badges,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.state import UiConfig

RECEIPT_PATH_KEY = "campaigns_receipt_path"


def render(_config: UiConfig) -> None:
    """Render the campaign receipt the person named, or the empty state."""

    st.title("Campaigns")
    badge_row(["RECEIPTS ONLY", "READ-ONLY", "NOT LIVE"])
    st.caption(
        "Inventory of one campaign receipt file at a time. " + NOT_LIVE_STATEMENT + " "
        "No registry is opened here and no scientific result is computed or shown — "
        "a receipt records execution states, elapsed times, and byte counts only."
    )

    receipt_path = st.text_input(
        "Campaign receipt file",
        value="",
        key=RECEIPT_PATH_KEY,
        placeholder="path/to/campaign_receipt.json",
        help=(
            "The exact path to one campaign receipt JSON file. This page never lists "
            "or scans directories, so no campaign is opened unless you name it."
        ),
    )

    loaded = load_campaign_receipt(receipt_path)
    if isinstance(loaded, CampaignsError):
        st.info(loaded.message)
        if loaded.detail:
            with st.expander("Advanced: technical detail"):
                st.code(loaded.detail, language=None)
        return

    _render_identity(loaded)
    _render_approval(loaded)
    _render_cells(loaded)
    _render_usage(loaded)
    _render_recorded_notes(loaded)


def _render_identity(view: CampaignReceiptView) -> None:
    receipt = view.receipt
    st.subheader("Design identity")
    badge_row(phase_badges(receipt))
    st.caption(
        f"Read from `{view.source_path}`. Phase and status are the receipt's own values, "
        "shown verbatim."
    )
    st.dataframe(
        [{"Field": row.label, "Value": row.value} for row in identity_rows(receipt)],
        hide_index=True,
        width="stretch",
    )
    seeds = declared_seeds(receipt)
    st.dataframe(
        [
            {
                "Arm": summary.arm_label,
                "Cells": summary.cell_count,
                "Admitted": summary.admitted,
                "Reused": summary.reused,
                "Failed": summary.failed,
                "Skipped": summary.skipped,
            }
            for summary in arm_summaries(receipt)
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"Fleet seeds named by the recorded cells: {', '.join(str(seed) for seed in seeds)}. "
        "Arms and seeds are read back from the cells the receipt lists; the receipt does not "
        "embed the design document itself."
    )


def _render_approval(view: CampaignReceiptView) -> None:
    st.subheader("Approval provenance")
    st.caption(
        "Exactly what the receipt records about the approval that authorised this "
        "campaign. This page displays those fields; it does not evaluate whether the "
        "approval was appropriate, and it never treats a missing value as consent."
    )
    st.dataframe(
        [{"Field": row.label, "Value": row.value} for row in approval_rows(view.receipt)],
        hide_index=True,
        width="stretch",
    )


def _render_cells(view: CampaignReceiptView) -> None:
    st.subheader("Declared cells")
    rows = cell_rows(view.receipt)
    st.caption(
        f"{len(rows)} declared cells, in the order the receipt records them. Elapsed time "
        "and output size are execution facts, not results."
    )
    st.dataframe(
        [
            {
                "Arm": row.arm_label,
                "Fleet seed": row.fleet_seed,
                "State": row.state,
                "Elapsed (s)": row.elapsed_seconds,
                "Output (bytes)": row.output_bytes,
                "Run id": row.run_id,
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )
    with st.expander("Advanced: per-cell recorded detail"):
        st.dataframe(
            [{"Run id": row.run_id, "State": row.state, "Detail": row.detail} for row in rows],
            hide_index=True,
            width="stretch",
        )


def _render_usage(view: CampaignReceiptView) -> None:
    usage = budget_usage(view.receipt)
    st.subheader("Budget usage")
    columns = st.columns(4)
    columns[0].metric("Declared cells", usage.planned_cell_count)
    columns[1].metric("Admitted", usage.admitted_cell_count)
    columns[2].metric("Output bytes", usage.total_output_bytes)
    columns[3].metric("Elapsed seconds", round(usage.total_elapsed_seconds, 1))
    st.caption(usage.ceilings_unavailable_reason)


def _render_recorded_notes(view: CampaignReceiptView) -> None:
    receipt = view.receipt
    st.subheader("Recorded notes")
    if receipt.findings:
        st.markdown("**Findings recorded by the run**")
        for item in receipt.findings:
            st.markdown(f"- {item}")
    else:
        st.caption("The run recorded no findings.")
    st.markdown("**Limitations recorded by the run**")
    for item in receipt.limitations:
        st.markdown(f"- {item}")
