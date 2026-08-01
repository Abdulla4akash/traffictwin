"""Data Inventory page: one honest table of what exists, and what does not.

An allowlisted schema reader over workspace session records, scheduled
markers, activity aggregates, the retention report, and the committed
publication-safe GPU preservation records. Read-only by construction: no
acquisition, retention, re-admission or campaign action can be triggered
here, and no raw quarantine byte is ever opened.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.platform_services import (
    PlatformServiceError,
    load_platform_inventory,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    st.title("Data Inventory")
    badge_row(["READ-ONLY", "ALLOWLISTED RECORDS", "NO RAW BYTES"])
    st.caption(
        "What this page claims: an inventory of recorded datasets and their "
        "standing, read from allowlisted schemas only. What it does not claim: "
        "completeness beyond those schemas, evidence standing for any listed "
        "diagnostic, or any action — nothing can be acquired, deleted, or "
        "re-admitted from here."
    )
    try:
        inventory = load_platform_inventory(
            config.workspace_path,
            Path.cwd(),
            today=datetime.now(UTC).date(),
        )
    except PlatformServiceError as error:
        st.warning(f"Inventory unavailable: {error}")
        return

    st.caption(inventory.workspace_note)
    if not inventory.rows:
        st.info(
            "No inventory records exist yet. That is the honest state, not an "
            "error: scheduled sessions, attended aggregates, and committed "
            "archive records appear here once they exist."
        )
    else:
        st.dataframe(
            [
                {
                    "dataset": row.dataset,
                    "source": row.source,
                    "mode": row.acquisition_mode,
                    "rows/snapshots": row.count_label,
                    "last updated": row.last_updated,
                    "digest": row.digest_prefix,
                    "freshness": row.freshness,
                    "standing": row.standing,
                    "deviation": row.deviation or "",
                }
                for row in inventory.rows
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Private diagnostic archives (GPU preservation records) are listed "
            "through their committed records only, status verbatim; their metrics "
            "never enter forecasts, prediction comparisons, or evidence headlines."
        )

    st.subheader("Freshness against the committed schedule")
    if not inventory.gaps:
        st.caption(
            "No schedule gap is recorded or inferred for the reconciled window. "
            "A same-day late window would appear from its skip marker; an older "
            "missing day is inferred as an absence."
        )
    else:
        st.dataframe(
            [
                {
                    "date": gap.session_date,
                    "window": gap.window,
                    "kind": gap.kind,
                    "detail": gap.detail,
                }
                for gap in inventory.gaps
            ],
            hide_index=True,
            width="stretch",
        )

    st.subheader("Retention")
    if inventory.retention_note is None:
        st.caption(
            "No retention report exists yet. Deletion of private raw snapshots is "
            "owner-confirmed and never automatic."
        )
    else:
        st.caption(inventory.retention_note)
    if inventory.unreadable_artifacts:
        st.caption(
            f"{inventory.unreadable_artifacts} artifact(s) were unreadable and are "
            "counted rather than silently skipped."
        )
