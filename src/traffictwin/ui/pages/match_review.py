"""Match Review page: one person decides one queued observation at a time.

A thin surface over the sealed review ledger. The page presents the queue's
own evidence — reasons, missing evidence, candidate road groups with their
distances and classes — and records exactly one explicit decision per submit
through the fail-closed service. There is no bulk action anywhere, an earlier
decision is only ever superseded and never overwritten, and the strongest
label a decided row can carry is ``analyst_reviewed_candidate``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from traffictwin.integration.manchester.observation_review import ReviewDecisionKind
from traffictwin.ui.review_services import (
    LoadedReviewContext,
    ReviewServiceError,
    load_review_context,
    record_decision_for_ui,
    seal_ledger_for_export,
)
from traffictwin.ui.state import UiConfig

_KIND_LABELS = {
    "Accept one candidate road group": ReviewDecisionKind.ACCEPT_GROUP,
    "Reject every listed candidate": ReviewDecisionKind.REJECT_ALL_CANDIDATES,
    "Defer — cannot decide from this evidence": ReviewDecisionKind.DEFER,
}


def render(config: UiConfig) -> None:
    """Render the analyst review workflow for one match-results artifact."""

    st.title("Match Review")
    st.caption(
        "A named person decides each queued observation, one at a time, with the "
        "reason recorded. Decisions become analyst-reviewed candidate evidence — "
        "never supervisor approval — and pending rows stay visibly pending."
    )

    artifact_path = st.text_input(
        "Match-results artifact (JSON list of v1.1 rows)",
        value=str(st.session_state.get("match_review_artifact", "")),
        help="The exported ObservationMatchV11 rows this review decides.",
    )
    ledger_path = st.text_input(
        "Working ledger file",
        value=str(
            st.session_state.get(
                "match_review_ledger",
                str(
                    (config.workspace_path / "manchester" / "match_review_ledger.json")
                    if config.workspace_path is not None
                    else "match_review_ledger.json"
                ),
            )
        ),
        help="Created on the first decision; safe to reopen to continue a review.",
    )
    st.session_state["match_review_artifact"] = artifact_path
    st.session_state["match_review_ledger"] = ledger_path
    if not artifact_path.strip():
        st.info(
            "Enter the path of a match-results artifact to begin. The review "
            "queue is rebuilt from the rows themselves, so it can never drift "
            "from the evidence."
        )
        return

    context = load_review_context(artifact_path.strip(), ledger_path.strip())
    if isinstance(context, ReviewServiceError):
        st.error(context.message)
        if context.detail:
            with st.expander("Advanced: technical detail"):
                st.code(context.detail, language=None)
        return

    _render_status(context)
    _render_row_and_form(context)
    _render_export(context)


def _render_status(context: LoadedReviewContext) -> None:
    status = context.status
    columns = st.columns(5)
    columns[0].metric("Queued", status.queued_total)
    columns[1].metric("Pending", status.pending_total)
    columns[2].metric("Accepted", status.accepted_total)
    columns[3].metric("Rejected", status.rejected_total)
    columns[4].metric("Deferred", status.deferred_total)
    st.caption(
        f"{status.no_candidate_preserved_total} no-candidate rows are preserved in "
        "the queue; deciding them still requires a person."
    )


def _render_row_and_form(context: LoadedReviewContext) -> None:
    status = context.status
    if status.pending_total == 0:
        st.success("Every queued row has a live decision. Seal the ledger below to export.")
        return
    selected = st.selectbox(
        "Pending observation (DfT count point)",
        list(status.pending_count_point_ids),
    )
    row = context.rows_by_count_point.get(int(selected))
    entry = next(item for item in context.queue.entries if item.count_point_id == int(selected))
    st.subheader(f"Count point {selected}")
    st.write(
        f"DfT road type **{entry.dft_road_type}**"
        + (f", signed reference **{entry.dft_normalised_ref}**" if entry.dft_normalised_ref else "")
        + f" — disposition `{entry.disposition}`"
    )
    for reason in entry.review_reasons:
        st.caption(f"• {reason}")
    if row is not None and row.groups:
        st.dataframe(
            [
                {
                    "group_key": group.group_key,
                    "road class family": group.road_class_family,
                    "signed ref": group.normalised_ref,
                    "nearest distance (m)": str(group.nearest_distance_m),
                    "exact reference match": group.exact_reference_match,
                    "admitted by override": group.admitted_by_override,
                }
                for group in row.groups
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("This row offers no candidate groups; accepting is impossible by design.")

    with st.form("match_review_decision"):
        kind_label = st.radio("Decision", list(_KIND_LABELS), index=2)
        group_key = None
        if row is not None and row.groups:
            group_key = st.selectbox(
                "Accepted group (used only for the accept decision)",
                [group.group_key for group in row.groups],
            )
        reviewer_name = st.text_input("Reviewer name")
        reviewer_role = st.text_input("Reviewer role")
        reason = st.text_area("Reason (recorded verbatim in the ledger; minimum ten characters)")
        submitted = st.form_submit_button("Record this one decision")
    if not submitted:
        return
    kind = _KIND_LABELS[kind_label]
    outcome = record_decision_for_ui(
        context,
        count_point_id=int(selected),
        kind=kind,
        reviewer_name=reviewer_name,
        reviewer_role=reviewer_role,
        reason=reason,
        decided_at_utc=datetime.now(tz=UTC).isoformat(),
        accepted_group_key=group_key if kind is ReviewDecisionKind.ACCEPT_GROUP else None,
    )
    if isinstance(outcome, ReviewServiceError):
        st.error(outcome.message)
        if outcome.detail:
            with st.expander("Advanced: technical detail"):
                st.code(outcome.detail, language=None)
        return
    st.success(
        f"Recorded. {outcome.status.pending_total} rows remain pending; the working "
        "ledger was saved. Interact with any control to refresh the queue view."
    )


def _render_export(context: LoadedReviewContext) -> None:
    with st.expander("Seal and export this ledger"):
        st.caption(
            "Sealing writes a tamper-evident export beside the untouched working "
            "copy. A sealed ledger is analyst-reviewed candidate evidence; it is "
            "not supervisor approval and does not change any capability state."
        )
        export_path = st.text_input(
            "Sealed export path",
            value=str(context.ledger_path.with_name("match_review_ledger_sealed.json")),
        )
        if st.button("Seal and export"):
            outcome = seal_ledger_for_export(context, export_path)
            if isinstance(outcome, ReviewServiceError):
                st.error(outcome.message)
            else:
                st.success(f"Sealed export written to {outcome}")
