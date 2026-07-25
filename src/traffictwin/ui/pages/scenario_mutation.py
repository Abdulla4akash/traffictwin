"""Controlled deterministic scenario-mutation page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.experiments.scenario_mutation import (
    MutationOperator,
    ScenarioMutationResult,
)
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.cards import fingerprint_summary, section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    execute_scenario_mutation_for_ui,
    prepare_scenario_mutation_for_ui,
    scenario_mutation_catalog_for_ui,
    scenario_mutation_result_json_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import table_column_config


def _stage_caption() -> None:
    """Render the ordered three-stage workflow indicator."""

    st.markdown(
        f"{badge_markdown('source')} **1 Source scenario** → "
        f"{badge_markdown('mutation')} **2 Requested mutation** → "
        f"{badge_markdown('candidate')} **3 Resulting candidate**"
    )
    st.caption(
        "Each stage is deterministic and import-first. Building a mutation copies and validates a "
        "bundle through the ordinary import path; it never executes or validates a simulator."
    )


def render(config: UiConfig) -> None:
    """Render EXP-02 through the typed mutation library service."""

    render_page_header(UiPage.SCENARIO_MUTATION)
    badge_row(["SYNTHETIC EVALUATION", "PARENT READ-ONLY", "VALIDATED COPY", "NO DIRECT LAUNCH"])
    _stage_caption()
    st.info(
        "Apply one bounded deterministic mutation to a copied synthetic/evaluation bundle. "
        "TrafficTwin records every changed row and validates the derived bundle through the "
        "ordinary import-first path."
    )
    catalog = scenario_mutation_catalog_for_ui()
    default_parent = str(st.session_state.get("selected_bundle_path", ""))
    default_output = (
        config.workspace_path / "exports" / "scenario-mutations" / "mutation-ui"
        if config.workspace_path is not None
        else Path("generated/scenario-mutations/mutation-ui")
    )

    section_header(
        "Mutation Declaration",
        f"One operator per copy; exact ledger limit: {catalog.max_changed_rows:,} rows.",
    )
    with st.form("scenario-mutation-form"):
        parent_bundle = st.text_input("Parent synthetic/evaluation bundle", value=default_parent)
        mutation_id = st.text_input("Mutation ID", value="mutation-ui")
        title = st.text_input("Title", value="Controlled robustness mutation")
        description = st.text_area(
            "Purpose",
            value="Inspect deterministic analysis stability under a declared mutation.",
        )
        operator = st.selectbox(
            "Mutation operator",
            [item.value for item in catalog.operators],
            format_func=_operator_label,
        )
        is_rsu = operator == MutationOperator.RSU_REMOVAL.value
        table_kind = st.selectbox(
            "Target table",
            [item.value for item in catalog.table_kinds],
            disabled=is_rsu,
            help="RSU removal always targets infra_state.",
        )
        drop_fraction = st.number_input(
            "Drop fraction",
            min_value=0.000001,
            max_value=1.0,
            value=0.25,
            step=0.05,
            disabled=operator != MutationOperator.ROW_DROPOUT.value,
        )
        max_jitter = st.number_input(
            "Maximum absolute timestamp jitter (seconds)",
            min_value=0.000001,
            max_value=float(catalog.max_absolute_jitter_s),
            value=1.0,
            step=0.5,
            disabled=operator != MutationOperator.TIMESTAMP_JITTER.value,
        )
        rsu_id = st.text_input(
            "RSU ID to remove",
            value="rsu-2",
            disabled=not is_rsu,
            help="Task targets are retained; TrafficTwin does not invent rerouting.",
        )
        random_seed = st.number_input(
            "Deterministic mutation seed",
            min_value=0,
            max_value=2_147_483_647,
            value=17,
            step=1,
            disabled=is_rsu,
        )
        output_dir = st.text_input("Output directory", value=str(default_output))
        overwrite = st.checkbox("Replace this exact output directory if it exists", value=False)
        submitted = st.form_submit_button("Build Mutated Copy", type="primary")

    if submitted:
        request = prepare_scenario_mutation_for_ui(
            parent_bundle=parent_bundle.strip(),
            mutation_id=mutation_id,
            title=title,
            description=description,
            operator=operator,
            table_kind=table_kind,
            drop_fraction=float(drop_fraction),
            max_absolute_jitter_s=float(max_jitter),
            rsu_id=rsu_id,
            random_seed=int(random_seed),
        )
        if isinstance(request, ServiceError):
            st.session_state["latest_scenario_mutation"] = None
            st.error(request.message)
            if request.detail:
                st.caption(request.detail)
        else:
            result = execute_scenario_mutation_for_ui(
                parent_bundle.strip(),
                request,
                output_dir.strip(),
                overwrite=overwrite,
            )
            if isinstance(result, ServiceError):
                st.session_state["latest_scenario_mutation"] = None
                st.error(result.message)
                if result.detail:
                    st.caption(result.detail)
            else:
                st.session_state["latest_scenario_mutation"] = result
                st.session_state["latest_scenario_mutation_output"] = output_dir.strip()
                st.success(
                    f"Built a validated copied bundle with {result.changed_row_count} exact row "
                    "changes. The parent remains unchanged."
                )

    result = st.session_state.get("latest_scenario_mutation")
    if isinstance(result, ScenarioMutationResult):
        _render_result(result, str(st.session_state.get("latest_scenario_mutation_output", "")))


def _render_result(result: ScenarioMutationResult, output_dir: str) -> None:
    section_header("Mutation Result", "Exact changed-row and file reconciliation.")

    # Stage 1 — Source scenario (the read-only parent).
    with st.container(border=True):
        st.markdown(f"{badge_markdown('source')} **Stage 1 · Source scenario**")
        source_cols = st.columns(2)
        source_cols[0].metric("Parent rows edited in place", 0)
        source_cols[1].markdown(
            f"**Parent identity:** `{fingerprint_summary(result.parent_bundle_fingerprint)}`"
        )
        st.caption("The parent synthetic/evaluation bundle is read-only and is never modified.")

    # Stage 2 — Requested mutation (the declared operator).
    with st.container(border=True):
        st.markdown(f"{badge_markdown('mutation')} **Stage 2 · Requested mutation**")
        mutation_cols = st.columns(2)
        mutation_cols[0].markdown(
            f"**Operator:** {badge_markdown(_operator_label(result.mutation.operator.value))}"
        )
        mutation_cols[1].metric("Changed rows", result.changed_row_count)
        st.caption("One bounded deterministic operator per copy; no simulator is executed.")

    # Stage 3 — Resulting candidate (the validated derived copy).
    with st.container(border=True):
        st.markdown(f"{badge_markdown('candidate')} **Stage 3 · Resulting candidate**")
        candidate_cols = st.columns(2)
        candidate_cols[0].markdown(
            f"**Import validation:** {badge_markdown(result.validation_status)}"
        )
        candidate_cols[1].markdown(
            f"**Derived identity:** `{fingerprint_summary(result.derived_bundle_fingerprint)}`"
        )
        st.caption(f"Output directory: `{output_dir}`. Import validation is not simulation.")

    section_header("Before / After Field Changes", "Human-readable per-field mutation of the copy.")
    field_rows = [
        {
            "table": change.table_kind.value,
            "parent_row": change.parent_source_row,
            "field": field.canonical_field,
            "before": field.before,
            "after": field.after,
            "action": change.action,
        }
        for change in result.row_changes
        for field in change.field_changes
    ]
    excluded_rows = [
        {
            "table": change.table_kind.value,
            "parent_row": change.parent_source_row,
            "field": "(whole row)",
            "before": "present",
            "after": "removed",
            "action": change.action,
        }
        for change in result.row_changes
        if not change.field_changes
    ]
    combined = field_rows + excluded_rows
    if combined:
        st.dataframe(
            combined,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(combined),
        )
        changed = len(field_rows)
        excluded = len(excluded_rows)
        st.caption(
            f"Changed fields: {changed} · Excluded (removed) rows: {excluded}. Fields not listed "
            "are unchanged; controls disabled for this operator are unsupported for the selection."
        )
    else:
        st.info("This mutation produced no per-field changes.")

    if result.validation_finding_codes:
        st.warning("Ordinary validation findings: " + ", ".join(result.validation_finding_codes))
    for warning in result.warnings:
        st.warning(warning)

    with st.expander("Advanced: fingerprints, changed files, and manifest"):
        st.caption(f"Complete parent fingerprint: {result.parent_bundle_fingerprint}")
        st.caption(f"Complete derived fingerprint: {result.derived_bundle_fingerprint}")
        st.markdown("**Row-level provenance fingerprints**")
        st.dataframe(
            [
                {
                    "table": change.table_kind.value,
                    "parent_row": change.parent_source_row,
                    "action": change.action,
                    "before_fingerprint": change.row_fingerprint_before,
                    "after_fingerprint": change.row_fingerprint_after or "removed",
                }
                for change in result.row_changes
            ],
            hide_index=True,
            width="stretch",
        )
        st.markdown("**Changed files**")
        st.dataframe(
            [item.model_dump(mode="json") for item in result.file_changes],
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Download Mutation Manifest JSON",
            data=scenario_mutation_result_json_for_ui(result),
            file_name=f"{result.mutation_id}.json",
            mime="application/json",
            width="stretch",
        )


def _operator_label(value: str) -> str:
    return {
        MutationOperator.ROW_DROPOUT.value: "Deterministic row dropout",
        MutationOperator.TIMESTAMP_JITTER.value: "Bounded timestamp jitter",
        MutationOperator.RSU_REMOVAL.value: "Exact RSU removal",
    }[value]
