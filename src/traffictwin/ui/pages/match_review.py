"""Resumable one-row-at-a-time named-person map-match review workspace."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st
from pydantic import ValidationError

from traffictwin.integration.manchester.observation_review import (
    ReviewDecisionKind,
    ReviewerIdentity,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.review_services import (
    CandidateBucket,
    DecisionState,
    LoadedReviewContext,
    RegisteredReviewArtifact,
    ReviewRowView,
    ReviewServiceError,
    ReviewSort,
    changed_decision_count,
    discover_registered_review_artifacts,
    filtered_review_rows,
    load_review_context,
    record_decision_for_ui,
    review_ledger_path,
    seal_ledger_for_export,
)
from traffictwin.ui.state import UiConfig

_KIND_LABELS = {
    "Accept one candidate road group": ReviewDecisionKind.ACCEPT_GROUP,
    "Reject every listed candidate": ReviewDecisionKind.REJECT_ALL_CANDIDATES,
    "Defer — cannot decide from this evidence": ReviewDecisionKind.DEFER,
}
_DECISION_LABELS: dict[DecisionState, str] = {
    "pending": "Pending",
    "accepted": "Accepted",
    "rejected": "Rejected",
    "deferred": "Deferred",
}
_CANDIDATE_LABELS: dict[CandidateBucket, str] = {
    "none": "No candidate",
    "one": "One candidate group",
    "multiple": "Multiple candidate groups",
}
_SORT_LABELS: dict[str, ReviewSort] = {
    "Count-point ID": "count_point",
    "Candidate count": "candidate_count",
    "Disposition": "disposition",
}


def render(config: UiConfig) -> None:
    """Render one registered queue; neither the page nor software makes a decision."""

    st.title("Match Review")
    badge_row(["NAMED PERSON", "ONE ROW AT A TIME", "NO RECOMMENDED ACTION"])
    st.caption(
        "A named person reviews one queued count point at a time. Decisions are append-only "
        "analyst-reviewed candidates, never supervisor or scientific approval. Filtering and "
        "sorting change presentation only; no bulk or automatic decision exists."
    )
    discovered = discover_registered_review_artifacts(config.workspace_path)
    if isinstance(discovered, ReviewServiceError):
        _render_error(discovered)
        return
    if not discovered:
        st.info(
            "The exact registered Manchester v1.1 artifact is not present in this verified "
            "workspace. Rebuild or import it through the bounded operator workflow; this page "
            "does not accept arbitrary file paths."
        )
        return
    artifact = _select_artifact(discovered)
    assert config.workspace_path is not None
    context = load_review_context(
        artifact.artifact_path,
        review_ledger_path(config.workspace_path, artifact),
        policy_fingerprint=artifact.registration.policy_fingerprint,
    )
    if isinstance(context, ReviewServiceError):
        _render_error(context)
        return

    _render_status(context)
    reviewer = _render_session_identity(context)
    views = _render_filters(context)
    if not views:
        st.info("No review row matches the current presentation filters.")
    else:
        _render_selected_row(context, views, reviewer)
    _render_export(context)


def _select_artifact(
    artifacts: tuple[RegisteredReviewArtifact, ...],
) -> RegisteredReviewArtifact:
    labels = [item.display_label for item in artifacts]
    selected = st.selectbox("Registered review artifact", labels)
    return artifacts[labels.index(selected)]


def _render_status(context: LoadedReviewContext) -> None:
    status = context.status
    columns = st.columns(7)
    for column, (label, value) in zip(
        columns,
        (
            ("Queued", status.queued_total),
            ("Pending", status.pending_total),
            ("Accepted", status.accepted_total),
            ("Rejected", status.rejected_total),
            ("Deferred", status.deferred_total),
            ("No candidate", status.no_candidate_preserved_total),
            ("Revisions", changed_decision_count(context)),
        ),
        strict=True,
    ):
        column.metric(label, value)
    queue_handle = f"queue-{context.queue.fingerprint()[:12]}"
    st.caption(
        f"Queue `{queue_handle}` · policy `{context.ledger.policy_id}` · "
        f"session saves `{int(st.session_state.get(_session_count_key(context), 0))}`. "
        f"{status.no_candidate_preserved_total} no-suitable-candidate row(s) in the registered "
        "queue still require a person."
    )


def _render_session_identity(context: LoadedReviewContext) -> ReviewerIdentity | None:
    with st.container(border=True):
        st.subheader("Local review-session identity")
        identity_columns = st.columns(2)
        name = identity_columns[0].text_input(
            "Reviewer name",
            key=f"reviewer_name::{context.queue.fingerprint()}",
            help="A real person; placeholders and agent identities are refused.",
        )
        role = identity_columns[1].text_input(
            "Reviewer role",
            key=f"reviewer_role::{context.queue.fingerprint()}",
        )
        try:
            reviewer = ReviewerIdentity(reviewer_name=name, reviewer_role=role)
        except ValidationError:
            st.caption(
                "Enter the authorised person's real name and role. Identity remains local and is "
                "written only when that person submits a decision."
            )
            return None
        badge_row(["IDENTITY READY", "NOT YET A DECISION"])
        st.caption(
            f"Every submitted form will bind reviewer **{reviewer.reviewer_name}** "
            f"({reviewer.reviewer_role})."
        )
        return reviewer


def _render_filters(context: LoadedReviewContext) -> tuple[ReviewRowView, ...]:
    with st.expander("Find and sort review rows", expanded=context.status.queued_total > 25):
        query = st.text_input(
            "Search count-point ID, signed road reference, road name or review reason"
        )
        filter_columns = st.columns(3)
        disposition_options = sorted({item.disposition for item in context.queue.entries})
        dispositions = tuple(filter_columns[0].multiselect("Disposition", disposition_options))
        selected_decision_labels = filter_columns[1].multiselect(
            "Decision state", list(_DECISION_LABELS.values()), default=["Pending"]
        )
        decision_states = tuple(
            state for state, label in _DECISION_LABELS.items() if label in selected_decision_labels
        )
        selected_candidate_labels = filter_columns[2].multiselect(
            "Candidate groups", list(_CANDIDATE_LABELS.values())
        )
        candidate_buckets = tuple(
            bucket
            for bucket, label in _CANDIDATE_LABELS.items()
            if label in selected_candidate_labels
        )
        sort_label = st.selectbox("Sort presentation", list(_SORT_LABELS))
    return filtered_review_rows(
        context,
        query=query,
        dispositions=dispositions,
        decision_states=decision_states,
        candidate_buckets=candidate_buckets,
        sort_by=_SORT_LABELS[sort_label],
    )


def _render_selected_row(
    context: LoadedReviewContext,
    views: tuple[ReviewRowView, ...],
    reviewer: ReviewerIdentity | None,
) -> None:
    by_id = {view.entry.count_point_id: view for view in views}
    options = list(by_id)
    selection_key = f"review_selection::{context.queue.fingerprint()}"
    bookmark_key = f"review_bookmark::{context.queue.fingerprint()}"
    preferred = st.session_state.get(bookmark_key)
    if preferred not in by_id:
        preferred = next(
            (item.entry.count_point_id for item in views if item.decision_state == "pending"),
            options[0],
        )
    if st.session_state.get(selection_key) not in by_id:
        st.session_state[selection_key] = preferred
    selected = st.selectbox(
        "Review row",
        options,
        key=selection_key,
        format_func=lambda value: _row_option_label(by_id[int(value)]),
    )
    view = by_id[int(selected)]
    bookmark_columns = st.columns([1, 4])
    if bookmark_columns[0].button("Bookmark this row"):
        st.session_state[bookmark_key] = int(selected)
        bookmark_columns[1].success("Bookmark saved for this local session.")
    _render_row_evidence(view)
    _render_decision_form(context, view, reviewer, selection_key, bookmark_key)


def _render_row_evidence(view: ReviewRowView) -> None:
    entry = view.entry
    row = view.row
    st.subheader(f"Count point {entry.count_point_id}")
    badge_row(
        [
            view.decision_state.upper(),
            entry.disposition.upper().replace("_", " "),
            _CANDIDATE_LABELS[view.candidate_bucket].upper(),
        ]
    )
    st.write(
        f"DfT road type **{entry.dft_road_type}**"
        + (f", signed reference **{entry.dft_normalised_ref}**" if entry.dft_normalised_ref else "")
        + (f", source road name **{row.dft_road_name}**" if row.dft_road_name else "")
    )
    for reason in entry.review_reasons:
        st.caption(f"• {reason}")
    if entry.missing_evidence:
        st.warning("Missing evidence: " + ", ".join(entry.missing_evidence))
    if row.groups:
        st.dataframe(
            [
                {
                    "group key": group.group_key,
                    "road class family": group.road_class_family,
                    "signed ref": group.normalised_ref or "unavailable",
                    "nearest distance (m)": str(group.nearest_distance_m),
                    "member edges": len(group.members),
                    "exact reference": group.exact_reference_match,
                    "override": group.admitted_by_override,
                    "preserved mismatch": group.family_mismatch or "none",
                }
                for group in row.groups
            ],
            hide_index=True,
            width="stretch",
        )
        with st.expander("Candidate member evidence"):
            for group in row.groups:
                st.write(f"**{group.group_key}**")
                st.dataframe(
                    [
                        {
                            "edge": member.edge_id,
                            "road class": member.road_class,
                            "distance (m)": str(member.distance_m),
                            "geometry source": member.geometry_source,
                        }
                        for member in group.members
                    ],
                    hide_index=True,
                    width="stretch",
                )
    else:
        st.info("This row offers no candidate group; accepting is impossible by design.")
    st.caption(
        "Geometry/map unavailable: the registered v1.1 row preserves distance and geometry-source "
        "labels but not source coordinates or edge shapes. No map is inferred; the text/table "
        "evidence above is the complete decision surface for this artifact."
    )
    if view.live_decision is not None:
        decision = view.live_decision
        with st.container(border=True):
            st.write(f"Current decision: **{view.decision_state}**")
            st.caption(
                f"{decision.reviewer.reviewer_name} ({decision.reviewer.reviewer_role}) · "
                f"{decision.decided_at_utc} · {view.revision_count} prior revision(s)"
            )
            st.write(decision.reason)


def _render_decision_form(
    context: LoadedReviewContext,
    view: ReviewRowView,
    reviewer: ReviewerIdentity | None,
    selection_key: str,
    bookmark_key: str,
) -> None:
    current = view.live_decision
    if current is not None:
        revise = st.checkbox(
            "Record an explicit superseding correction",
            help="The current decision and reason remain in the append-only ledger.",
        )
        if not revise:
            return
    available_kinds = list(_KIND_LABELS)
    if not view.row.groups:
        available_kinds.remove("Accept one candidate road group")
    with st.form(f"match_review_decision::{view.entry.count_point_id}::{view.revision_count}"):
        st.caption(
            "Reviewer: "
            + (
                f"{reviewer.reviewer_name} ({reviewer.reviewer_role})"
                if reviewer is not None
                else "identity incomplete — submission will be refused"
            )
        )
        kind_label = st.radio("Decision", available_kinds, index=len(available_kinds) - 1)
        group_key = None
        if view.row.groups:
            group_key = st.selectbox(
                "Accepted group (used only for the accept decision)",
                [group.group_key for group in view.row.groups],
            )
        reason = st.text_area("Reason recorded verbatim (minimum ten characters)")
        submitted = st.form_submit_button(
            "Record this superseding decision"
            if current is not None
            else "Record this one decision",
            disabled=reviewer is None,
        )
    if not submitted or reviewer is None:
        return
    kind = _KIND_LABELS[kind_label]
    outcome = record_decision_for_ui(
        context,
        count_point_id=view.entry.count_point_id,
        kind=kind,
        reviewer_name=reviewer.reviewer_name,
        reviewer_role=reviewer.reviewer_role,
        reason=reason,
        decided_at_utc=datetime.now(tz=UTC).isoformat(),
        accepted_group_key=group_key if kind is ReviewDecisionKind.ACCEPT_GROUP else None,
        supersedes=None if current is None else current.fingerprint(),
    )
    if isinstance(outcome, ReviewServiceError):
        _render_error(outcome)
        return
    st.session_state[_session_count_key(context)] = (
        int(st.session_state.get(_session_count_key(context), 0)) + 1
    )
    st.success(
        f"One decision was atomically saved and read back. {outcome.status.pending_total} rows "
        "remain pending."
    )
    next_pending = next(
        (
            count_point_id
            for count_point_id in outcome.status.pending_count_point_ids
            if count_point_id != view.entry.count_point_id
        ),
        None,
    )
    if next_pending is not None and st.button("Next pending"):
        st.session_state[selection_key] = next_pending
        st.session_state[bookmark_key] = next_pending
        st.rerun()


def _render_export(context: LoadedReviewContext) -> None:
    with st.expander("Seal a tamper-evident export"):
        st.caption(
            f"The content-addressed sealed export preserves {context.status.pending_total} pending "
            "row(s) and leaves the working ledger untouched. It is analyst-review evidence only."
        )
        if st.button("Seal current ledger"):
            outcome = seal_ledger_for_export(context)
            if isinstance(outcome, ReviewServiceError):
                _render_error(outcome)
            else:
                st.success("The sealed export was atomically written and read back.")


def _render_error(error: ReviewServiceError) -> None:
    st.error(f"{error.message} (`{error.code}`)")
    if error.detail:
        with st.expander("Advanced: safe technical class"):
            st.code(error.detail, language=None)


def _row_option_label(view: ReviewRowView) -> str:
    reference = view.entry.dft_normalised_ref or "unsigned"
    return (
        f"{view.entry.count_point_id} · {view.decision_state} · {reference} · "
        f"{len(view.row.groups)} candidate group(s)"
    )


def _session_count_key(context: LoadedReviewContext) -> str:
    return f"review_session_saves::{context.queue.fingerprint()}"
