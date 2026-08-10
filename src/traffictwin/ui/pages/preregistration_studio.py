"""Thin Streamlit surface for versioned preregistration governance."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from traffictwin.metrics.catalogue import METRIC_DEFINITIONS, METRIC_VERSION
from traffictwin.preregistration.models import (
    AnalysisMethod,
    ArtifactAdmission,
    CohortRule,
    DecisionRule,
    EstimandDefinition,
    EvidenceAttachment,
    EvidenceMode,
    ExclusionRule,
    MissingnessPolicy,
    MultiplicityPolicy,
    OutcomeDefinition,
    ReplicationUnit,
    StoppingRule,
    StudyPlan,
    StudyPlanStatus,
    StudyQuestion,
)
from traffictwin.preregistration.service import (
    attach_evidence,
    build_run_matrix,
    create_amendment,
    evaluate_gate,
    export_plan_csv,
    export_plan_json,
    export_plan_yaml,
    freeze_plan,
    import_plan_json,
    import_plan_yaml,
    planned_vs_observed_matrix,
    validate_study_plan,
    verify_plan,
)
from traffictwin.storage.registry import Registry
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import ColumnDisplay, table_column_config

# ---------------------------------------------------------------------------
# Run-matrix column configuration — identity-bearing matrix must remain visible
# ---------------------------------------------------------------------------


def _run_matrix_column_config(
    matrix_rows: list[dict[str, object]],
) -> dict[str, object]:
    """Return column config for the preregistered run matrix.

    The shared table helper hides machine IDs by default (keys ending in
    ``_id`` and ``metric_version``/``seed_id`` via ``MACHINE_ID_COLUMNS``).
    For a preregistered run matrix those identifiers are the experimental
    identity and must remain visible, so every matrix column is overridden
    with an explicit non-hidden ``ColumnDisplay``.
    """

    return table_column_config(
        matrix_rows,
        overrides={
            "cell_id": ColumnDisplay(key="cell_id", label="Cell"),
            "arm_id": ColumnDisplay(key="arm_id", label="Arm"),
            "seed_id": ColumnDisplay(key="seed_id", label="Seed"),
            "policy_label": ColumnDisplay(key="policy_label", label="Policy"),
            "replication_id": ColumnDisplay(key="replication_id", label="Replication"),
            "metric_key": ColumnDisplay(key="metric_key", label="Metric"),
            "metric_version": ColumnDisplay(key="metric_version", label="Version"),
            "replication_unit": ColumnDisplay(key="replication_unit", label="Replication unit"),
        },
    )


def _list_registry_options(config: UiConfig) -> tuple[list[str], list[str], list[str]]:
    """Return seeds, policies, metrics from registry. Fail gracefully if empty."""
    try:
        registry = Registry(config.registry_path)
        seeds = [s.seed_id for s in registry.list_seeds()]
        experiments = registry.list_experiments()
        policies: list[str] = []
        for exp in experiments:
            policies.extend(exp.algorithms)
        policies = sorted(set(policies))
        # metrics from catalogue
        metrics = sorted(METRIC_DEFINITIONS.keys())
        if not policies:
            policies = ["policy-a", "policy-b", "synthetic-policy"]
        return seeds, policies, metrics
    except Exception:
        return [], ["policy-a"], sorted(METRIC_DEFINITIONS.keys())


def _default_plan(seeds: list[str], policies: list[str], metrics: list[str]) -> StudyPlan:
    metric = metrics[0] if metrics else "task.completion.rate"
    return StudyPlan(
        plan_id="plan-demo-001",
        study_question=StudyQuestion(
            text="Does the variation change the primary outcome under the predeclared replication unit?",  # noqa: E501
            hypothesis="Variation improves the primary outcome versus baseline.",
            background="Pre-registered to prevent post-hoc rewriting.",
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key=metric,
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary task completion rate in original ratio unit.",
                higher_is_better=True,
            )
        ],
        secondary_outcomes=[],
        estimand=EstimandDefinition(
            estimand_id="estimand-001",
            description="Mean paired difference variation minus baseline over common seeds.",
            population="common_random_seed replicates",
            effect_measure="mean_difference",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2, 3],
        replication_generation_rule=None,
        planned_arms=["baseline", "variation"],
        seeds=seeds[:2]
        if len(seeds) >= 2
        else (seeds if seeds else ["seed-baseline", "seed-variation"]),
        policies=policies[:2] if len(policies) >= 2 else policies,
        metrics=[metric],
        cohort_rules=[
            CohortRule(
                rule_id="cohort-001",
                description="Include all valid generated tasks with latency observed.",
            )
        ],
        exclusion_rules=[
            ExclusionRule(
                rule_id="exclude-001", description="Exclude runs with invalid source data."
            )
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Fixed sample size with no interim looks; decision after all replicates observed.",  # noqa: E501
            max_replicates=3,
            interim_looks=0,
            criteria="observe all planned replicates",
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            threshold=None,
            interpretation="Reject null if two-sided p < 0.05; otherwise do not reject. Non-significance is not equivalence.",  # noqa: E501
            comparison="two_sided",
        ),
        limitations="Synthetic demonstration limitations: no Manchester observation generalisation claimed. Analysis is planning-only until evidence attached.",  # noqa: E501
        planned_run_cells=[],
        power_plan_fingerprint=None,
    )


def render(config: UiConfig) -> None:
    # Use new enum when registered, otherwise fall back to a title-only header for isolated feature commits.  # noqa: E501
    if hasattr(UiPage, "PREREGISTRATION_STUDIO"):
        render_page_header(UiPage.PREREGISTRATION_STUDIO)
    else:
        st.caption("TrafficTwin / Preregistration Studio")
        st.title("Preregistration Studio")
    st.caption(
        "Versioned scientific-plan workflow: freeze before evidence, amend with diff, attach by fingerprint, evaluate gate."  # noqa: E501
    )
    badge_row(["GOVERNANCE", "DETERMINISTIC", "NO LAUNCH"])
    st.warning(
        "Freezing is not scientific approval. It only means that exact plan version is immutable. "
        "A frozen plan may never be edited in place; an amendment creates a new version with parent fingerprint and exact diff."  # noqa: E501
    )
    st.info(
        "This page never launches SUMO or VEC, never reads active E2 output directories, and never reinterprets unadmitted research evidence as admitted. "  # noqa: E501
        "A missing or incompatible field remains unavailable rather than guessed."
    )

    seeds, policies, metrics = _list_registry_options(config)

    # Session state initialisation
    if "prereg_draft" not in st.session_state:
        st.session_state["prereg_draft"] = _default_plan(seeds, policies, metrics)
    if "prereg_frozen" not in st.session_state:
        st.session_state["prereg_frozen"] = None
    if "prereg_evidence_attached" not in st.session_state:
        st.session_state["prereg_evidence_attached"] = None

    draft: StudyPlan = st.session_state["prereg_draft"]

    # --- Draft editor ---
    section_header(
        "1 · Draft study plan",
        "Select existing seeds, policies, metrics and compatible analysis methods.",
    )
    with st.expander("Draft plan editor", expanded=True):
        plan_id = st.text_input("Plan ID", value=draft.plan_id, key="prereg_plan_id")
        question_text = st.text_area(
            "Study question", value=draft.study_question.text, key="prereg_question"
        )
        hypothesis = st.text_input(
            "Hypothesis (optional)", value=draft.study_question.hypothesis or "", key="prereg_hyp"
        )
        background = st.text_input(
            "Background (optional)", value=draft.study_question.background or "", key="prereg_bg"
        )
        evidence_mode = st.selectbox(
            "Evidence mode",
            [e.value for e in EvidenceMode],
            index=[e.value for e in EvidenceMode].index(draft.evidence_mode.value),
            key="prereg_evidence_mode",
            help="Authored configuration, synthetic evidence, imported evidence, historical observation, near-live operational, admitted/unadmitted research, static geographic, unavailable.",  # noqa: E501
        )
        st.columns(2)
        replication_unit = st.selectbox(
            "Replication unit",
            [e.value for e in ReplicationUnit],
            index=[e.value for e in ReplicationUnit].index(draft.replication_unit.value),
            key="prereg_repl_unit",
        )
        replication_ids_str = st.text_input(
            "Planned replication IDs (comma separated) or generation rule",
            value=",".join(map(str, draft.replication_ids))
            if draft.replication_ids
            else (draft.replication_generation_rule or ""),
            key="prereg_reps",
            help="e.g. 1,2,3 or range:5 or 0..4",
        )
        # Seed/policy/metric selectors from registry
        if seeds:
            selected_seeds = st.multiselect(
                "Registered seeds",
                seeds,
                default=draft.seeds[:2] if draft.seeds else seeds[:1],
                key="prereg_seeds",
            )
        else:
            selected_seeds = (
                st.text_input(
                    "Seeds (comma separated)", value=",".join(draft.seeds), key="prereg_seeds_text"
                ).split(",")
                if st.text_input
                else draft.seeds
            )
            # fallback
            selected_seeds = draft.seeds
        # For simplicity, use text inputs when registry empty
        if policies:
            selected_policies = st.multiselect(
                "Registered policies",
                policies,
                default=draft.policies[:2] if draft.policies else policies[:1],
                key="prereg_policies",
            )
        else:
            selected_policies = draft.policies
        if metrics:
            selected_metrics = st.multiselect(
                "Registered metrics",
                metrics,
                default=draft.metrics[:1] if draft.metrics else metrics[:1],
                key="prereg_metrics",
            )
        else:
            selected_metrics = draft.metrics

        st.markdown("**Planned arms**")
        arms_str = st.text_input(
            "Planned arms (comma separated)", value=",".join(draft.planned_arms), key="prereg_arms"
        )

        # Primary outcome section
        st.markdown("**Primary outcome** (required)")
        primary_metric = st.selectbox(
            "Primary metric key",
            metrics,
            index=metrics.index(draft.primary_outcomes[0].metric_key)
            if draft.primary_outcomes and draft.primary_outcomes[0].metric_key in metrics
            else 0,
            key="prereg_primary_metric",
        )
        primary_unit = st.text_input(
            "Primary unit",
            value=draft.primary_outcomes[0].unit if draft.primary_outcomes else "ratio",
            key="prereg_primary_unit",
        )
        primary_denom = st.text_input(
            "Primary denominator",
            value=draft.primary_outcomes[0].denominator or "generated_tasks",
            key="prereg_primary_denom",
        )
        primary_desc = st.text_input(
            "Primary description",
            value=draft.primary_outcomes[0].description
            if draft.primary_outcomes
            else "Primary outcome description",
            key="prereg_primary_desc",
        )

        # Secondary outcome
        st.markdown("**Secondary outcomes** (optional)")
        secondary_metric = st.selectbox(
            "Secondary metric (optional)",
            ["(none)"] + metrics,
            index=0,
            key="prereg_secondary_metric",
        )
        secondary_desc = st.text_input(
            "Secondary description (if any)", value="", key="prereg_secondary_desc"
        )

        # Cohort / exclusion / missingness
        st.markdown("**Cohort / Exclusion / Missingness**")
        cohort_desc = st.text_area(
            "Inclusion rule",
            value=draft.cohort_rules[0].description if draft.cohort_rules else "",
            key="prereg_cohort",
        )
        exclusion_desc = st.text_area(
            "Exclusion rule",
            value=draft.exclusion_rules[0].description if draft.exclusion_rules else "",
            key="prereg_exclusion",
        )
        missingness = st.selectbox(
            "Missingness policy",
            [e.value for e in MissingnessPolicy],
            index=[e.value for e in MissingnessPolicy].index(draft.missingness_policy.value),
            key="prereg_missing",
        )

        # Analysis method + multiplicity
        st.markdown("**Analysis**")
        analysis_method = st.selectbox(
            "Analysis method",
            [e.value for e in AnalysisMethod],
            index=[e.value for e in AnalysisMethod].index(draft.analysis_method.value),
            key="prereg_analysis",
        )
        multiplicity = st.selectbox(
            "Multiplicity policy",
            [e.value for e in MultiplicityPolicy],
            index=[e.value for e in MultiplicityPolicy].index(draft.multiplicity_policy.value),
            key="prereg_multiplicity",
        )

        # Stopping and decision rules
        st.markdown("**Stopping and decision rules**")
        stopping_desc = st.text_area(
            "Stopping rule description",
            value=draft.stopping_rule.description,
            key="prereg_stopping",
        )
        stopping_max = st.number_input(
            "Stopping max replicates (optional)",
            min_value=0,
            value=draft.stopping_rule.max_replicates or 0,
            step=1,
            key="prereg_stopping_max",
        )
        stopping_looks = st.number_input(
            "Interim looks",
            min_value=0,
            value=draft.stopping_rule.interim_looks,
            step=1,
            key="prereg_stopping_looks",
        )
        decision_type = st.text_input(
            "Decision rule type", value=draft.decision_rule.rule_type, key="prereg_decision_type"
        )
        alpha = st.number_input(
            "Alpha (0-1, 0 to omit)",
            min_value=0.0,
            max_value=1.0,
            value=draft.decision_rule.alpha or 0.05,
            step=0.01,
            key="prereg_alpha",
        )
        threshold = st.number_input(
            "Threshold (0 to omit)",
            value=draft.decision_rule.threshold or 0.0,
            step=0.01,
            key="prereg_threshold",
        )
        comparison = st.selectbox(
            "Comparison",
            ["two_sided", "one_sided_greater", "one_sided_less", "equivalence"],
            index=["two_sided", "one_sided_greater", "one_sided_less", "equivalence"].index(
                draft.decision_rule.comparison
            ),
            key="prereg_comparison",
        )
        interpretation = st.text_area(
            "Decision interpretation", value=draft.decision_rule.interpretation, key="prereg_interp"
        )

        # Power plan linkage
        power_fp = st.text_input(
            "Linked prospective power plan fingerprint (optional)",
            value=draft.power_plan_fingerprint or "",
            key="prereg_power",
        )

        # Limitations
        limitations = st.text_area("Limitations", value=draft.limitations, key="prereg_limitations")

        if st.button("Update draft", type="primary", key="prereg_update_draft"):
            # Parse replication ids or generation rule
            repl_ids: list[int] = []
            repl_rule: str | None = None
            raw = replication_ids_str.strip()
            if raw:
                if any(c in raw for c in [",", "..", "range"]):
                    if raw.startswith("range:") or ".." in raw or "," in raw:
                        repl_rule = raw
                        repl_ids = []
                    else:
                        try:
                            repl_ids = sorted({int(x.strip()) for x in raw.split(",") if x.strip()})
                            repl_rule = None
                        except Exception:
                            repl_rule = raw
                            repl_ids = []
                else:
                    try:
                        repl_ids = [int(raw)]
                        repl_rule = None
                    except Exception:
                        repl_rule = raw
                        repl_ids = []
            # Build new draft
            try:
                new_primary = OutcomeDefinition(
                    outcome_id="primary-001",
                    metric_key=primary_metric,
                    metric_version=METRIC_VERSION,
                    unit=primary_unit,
                    denominator=primary_denom,
                    description=primary_desc,
                    higher_is_better=True,
                )
                secondaries: list[OutcomeDefinition] = []
                if secondary_metric != "(none)" and secondary_desc.strip():
                    secondaries.append(
                        OutcomeDefinition(
                            outcome_id="secondary-001",
                            metric_key=secondary_metric,
                            metric_version=METRIC_VERSION,
                            unit=primary_unit,
                            denominator=primary_denom,
                            description=secondary_desc,
                            higher_is_better=None,
                        )
                    )
                # Parse arms
                arms = [a.strip() for a in arms_str.split(",") if a.strip()] or draft.planned_arms
                # Cohort/exclusion
                cohort_rules = (
                    [CohortRule(rule_id="cohort-001", description=cohort_desc)]
                    if cohort_desc.strip()
                    else []
                )
                exclusion_rules = (
                    [ExclusionRule(rule_id="exclude-001", description=exclusion_desc)]
                    if exclusion_desc.strip()
                    else []
                )
                # Build plan
                updated = StudyPlan(
                    plan_id=plan_id.strip() or draft.plan_id,
                    version=draft.version,
                    status=StudyPlanStatus.DRAFT,
                    study_question=StudyQuestion(
                        text=question_text,
                        hypothesis=hypothesis or None,
                        background=background or None,
                    ),
                    evidence_mode=EvidenceMode(evidence_mode),
                    primary_outcomes=[new_primary],
                    secondary_outcomes=secondaries,
                    estimand=draft.estimand,
                    replication_unit=ReplicationUnit(replication_unit),
                    replication_ids=repl_ids,
                    replication_generation_rule=repl_rule,
                    planned_arms=arms,
                    seeds=[s for s in selected_seeds if s.strip()]
                    if isinstance(selected_seeds, list)
                    else draft.seeds,
                    policies=[p for p in selected_policies if p.strip()]
                    if isinstance(selected_policies, list)
                    else draft.policies,
                    metrics=[m for m in selected_metrics if m.strip()]
                    if isinstance(selected_metrics, list)
                    else draft.metrics,
                    cohort_rules=cohort_rules,
                    exclusion_rules=exclusion_rules,
                    missingness_policy=MissingnessPolicy(missingness),
                    analysis_method=AnalysisMethod(analysis_method),
                    multiplicity_policy=MultiplicityPolicy(multiplicity),
                    stopping_rule=StoppingRule(
                        description=stopping_desc,
                        max_replicates=int(stopping_max) if stopping_max else None,
                        interim_looks=int(stopping_looks),
                        criteria="predeclared",
                    ),
                    decision_rule=DecisionRule(
                        rule_type=decision_type,
                        alpha=float(alpha) if alpha and alpha != 0 else None,
                        threshold=float(threshold) if threshold and threshold != 0 else None,
                        interpretation=interpretation,
                        comparison=comparison,
                    ),
                    limitations=limitations,
                    planned_run_cells=[],
                    power_plan_fingerprint=power_fp.strip() or None,
                    created_at=draft.created_at,
                    frozen_at=None,
                    parent_fingerprint=draft.parent_fingerprint,
                    revision_history=draft.revision_history,
                    evidence_attachments=[],
                    gate_report=None,
                    fingerprint=None,
                )
                st.session_state["prereg_draft"] = updated
                st.success("Draft updated.")
            except Exception as exc:
                st.error(f"Draft update failed: {exc}")

    # --- Validation findings ---
    section_header(
        "2 · Validation findings",
        "A frozen plan must have study question, primary outcome, metric version, unit, denominator, replication unit, arms, replication, inclusion/exclusion, missingness, method, multiplicity, stopping, decision, limitations.",  # noqa: E501
    )
    findings = validate_study_plan(draft)
    if not findings:
        st.success("Validation: freezable — no findings.")
        st.markdown(f"{badge_markdown('available')} **Freezable**")
    else:
        st.warning(f"Validation: {len(findings)} finding(s)")
        for f in findings:
            st.caption(f"• {f}")
        st.markdown(f"{badge_markdown('unavailable')} **Not freezable**")

    # --- Run-matrix preview ---
    section_header(
        "3 · Run-matrix preview",
        "Deterministic matrix from declared plan. Rejects duplicate cells, ambiguous arms, missing primary outcome, inconsistent versions, empty replication.",  # noqa: E501
    )
    try:
        matrix = build_run_matrix(draft)
        matrix_rows = [c.model_dump(mode="json") for c in matrix]
        st.dataframe(
            matrix_rows,
            hide_index=True,
            width="stretch",
            column_config=_run_matrix_column_config(matrix_rows),
        )
        st.caption(f"Deterministic run cells: {len(matrix)}")
        # Store matrix in draft for export
        draft_with_cells = draft.model_copy(update={"planned_run_cells": matrix})
        st.session_state["prereg_draft"] = draft_with_cells
    except Exception as exc:
        st.error(f"Run matrix error: {exc}")

    # --- Freeze action ---
    section_header(
        "4 · Freeze",
        "Freezing makes the exact plan version immutable and produces a deterministic fingerprint. Freezing is not scientific approval.",  # noqa: E501
    )
    if st.button(
        "Freeze deterministic immutable version",
        type="primary",
        key="prereg_freeze",
        disabled=bool(findings),
    ):
        try:
            newly_frozen = freeze_plan(draft)
            st.session_state["prereg_frozen"] = newly_frozen
            st.session_state["prereg_draft"] = newly_frozen.model_copy(
                update={
                    "status": StudyPlanStatus.DRAFT,
                    "version": newly_frozen.version,
                    "fingerprint": None,
                    "frozen_at": None,
                }
            )  # keep draft as new editable? But frozen is immutable
            st.success(
                f"Frozen version {newly_frozen.version} fingerprint: {newly_frozen.fingerprint}"
            )
        except Exception as exc:
            st.error(f"Freeze failed: {exc}")

    frozen: StudyPlan | None = st.session_state.get("prereg_frozen")
    if frozen is not None:
        st.markdown(f"**Frozen fingerprint** `{frozen.fingerprint}`")
        st.caption(
            f"Status: {frozen.status.value} · Version: {frozen.version} · Plan ID: {frozen.plan_id}"
        )
        with st.expander("Advanced: frozen canonical JSON"):
            st.code(export_plan_json(frozen), language="json")
        # Verify
        ok, computed = verify_plan(frozen)
        st.caption(f"Verification: {'PASS' if ok else 'FAIL'} computed {computed[:12]}…")

    # --- Amendment ---
    section_header(
        "5 · Amendment",
        "Create a reasoned amendment as a child version with parent pointer, exact diff, and pre/post-evidence label.",  # noqa: E501
    )
    if frozen is None:
        st.info("Freeze a plan before creating an amendment.")
    else:
        with st.form("amendment_form"):
            amend_reason = st.text_area(
                "Amendment reason (≥12 chars)",
                value="Correct primary outcome denominator clarification for reproducibility.",
                key="amend_reason",
            )
            amend_field = st.selectbox(
                "Field to amend",
                ["limitations", "analysis_method", "decision_rule", "primary_outcomes"],
                key="amend_field",
            )
            amend_value = st.text_input(
                "New value (for limitations) or new method (for analysis_method)",
                value="",
                key="amend_value",
            )
            submitted = st.form_submit_button("Create amendment as child version")
        if submitted:
            try:
                changes: dict[str, object] = {}
                if amend_field == "limitations":
                    changes["limitations"] = amend_value or "Amended limitations clarification."
                elif amend_field == "analysis_method":
                    # Validate enum
                    changes["analysis_method"] = (
                        AnalysisMethod(amend_value)
                        if amend_value in [e.value for e in AnalysisMethod]
                        else AnalysisMethod.DESCRIPTIVE
                    )
                elif amend_field == "decision_rule":
                    # Simple: update interpretation
                    changes["decision_rule"] = DecisionRule(
                        rule_type=frozen.decision_rule.rule_type,
                        alpha=frozen.decision_rule.alpha,
                        threshold=frozen.decision_rule.threshold,
                        interpretation=amend_value or "Amended interpretation.",
                        comparison=frozen.decision_rule.comparison,
                    )
                elif amend_field == "primary_outcomes":
                    # Demonstrate post-evidence replacement attempt (should be via amendment)
                    changes["primary_outcomes"] = [
                        OutcomeDefinition(
                            outcome_id="primary-001",
                            metric_key=metrics[1] if len(metrics) > 1 else "task.latency.mean_ms",
                            metric_version=METRIC_VERSION,
                            unit="ms",
                            denominator="observed_tasks",
                            description="Amended primary outcome after review.",
                        )
                    ]
                amended = create_amendment(frozen, changes=changes, amendment_reason=amend_reason)
                st.session_state["prereg_amended"] = amended
                st.success(
                    f"Amendment created: version {amended.version} parent {amended.parent_fingerprint[:12] if amended.parent_fingerprint else 'none'}…"  # noqa: E501
                )
                st.caption(f"Diff keys: {', '.join(amended.revision_history[-1].diff.keys())}")
                st.caption(
                    f"Label: {amended.revision_history[-1].amendment_label.value} · is_post_evidence={amended.revision_history[-1].is_post_evidence}"  # noqa: E501
                )
                with st.expander("Exact diff"):
                    st.json(amended.revision_history[-1].diff)
                # Offer to freeze amended
                if st.button("Freeze amended version", key="freeze_amended"):
                    try:
                        frozen_amended = freeze_plan(amended)
                        st.session_state["prereg_frozen"] = frozen_amended
                        st.success(
                            f"Frozen amended version {frozen_amended.version} {frozen_amended.fingerprint_or_compute()[:12]}…"  # noqa: E501
                        )
                    except Exception as exc2:
                        st.error(f"Freeze amended failed: {exc2}")
            except Exception as exc:
                st.error(f"Amendment failed: {exc}")

        amended_plan: StudyPlan | None = st.session_state.get("prereg_amended")
        if amended_plan is not None:
            with st.expander("Amended plan preview"):
                st.code(export_plan_json(amended_plan), language="json")

    # --- Evidence attachment ---
    section_header(
        "6 · Evidence attachment",
        "Attach imported evidence by fingerprint. Preserves frozen plan, reconciles expected vs observed, records missing/extra/incompatible, never imports raw research data automatically.",  # noqa: E501
    )
    if frozen is None:
        st.info("Evidence can only be attached after freezing.")
    else:
        # Use frozen as source
        st.session_state.get("prereg_evidence_attached") or frozen
        with st.form("evidence_form"):
            fp1 = st.text_input(
                "Artifact fingerprint 1 (hex, ≥16 chars)", value="a" * 64, key="ev_fp1"
            )
            cell1 = st.text_input(
                "Cell ID for artifact 1",
                value=frozen.planned_run_cells[0].cell_id
                if frozen.planned_run_cells
                else "cell-0001",
                key="ev_cell1",
            )
            admitted = st.checkbox(
                "Admitted (unchecked = unadmitted remains unadmitted)",
                value=True,
                key="ev_admitted",
            )
            obs_version = st.text_input(
                "Observed metric version", value=METRIC_VERSION, key="ev_version"
            )
            obs_key = st.text_input(
                "Observed metric key",
                value=frozen.primary_outcomes[0].metric_key
                if frozen.primary_outcomes
                else "task.completion.rate",
                key="ev_key",
            )
            submitted_ev = st.form_submit_button("Attach evidence by fingerprint")
        if submitted_ev:
            try:
                attachments = [
                    EvidenceAttachment(
                        artifact_fingerprint=fp1,
                        cell_id=cell1,
                        observed_metric_key=obs_key,
                        observed_metric_version=obs_version,
                        observed_unit="ratio",
                        is_admitted=admitted,
                        admission_label=ArtifactAdmission.ADMITTED
                        if admitted
                        else ArtifactAdmission.UNADMITTED,
                        attached_at=datetime.now(UTC),
                    )
                ]
                # If matrix has more than one cell, require multiple attachments to demonstrate missing/extra handling  # noqa: E501
                # For demo, attach one then evaluate gate
                attached = attach_evidence(frozen, attachments)
                st.session_state["prereg_evidence_attached"] = attached
                st.success(
                    f"Attached {len(attachments)} artifact(s). Status: {attached.status.value}"
                )
            except Exception as exc:
                st.error(f"Attach failed: {exc}")

        attached_plan: StudyPlan | None = st.session_state.get("prereg_evidence_attached")
        if attached_plan is not None:
            st.dataframe(
                [a.model_dump(mode="json") for a in attached_plan.evidence_attachments],
                hide_index=True,
                width="stretch",
            )
            # Planned vs observed
            section_header(
                "7 · Planned-versus-observed coverage",
                "Exact reconciliation of expected versus observed cells.",
            )
            matrix_cov = planned_vs_observed_matrix(attached_plan)
            st.dataframe(matrix_cov["rows"], hide_index=True, width="stretch")
            st.caption(
                f"Expected {matrix_cov['expected_count']} · Observed {matrix_cov['observed_count']}"
            )

            # Gate readiness
            section_header(
                "8 · Decision-gate readiness",
                "Gate is READY only if all planned cells have compatible admitted evidence. Otherwise UNAVAILABLE or BLOCKED. Never auto-imports E2 output.",  # noqa: E501
            )
            gate = attached_plan.gate_report or evaluate_gate(attached_plan)
            status_badge = {
                "ready": "available",
                "blocked": "blocked",
                "unavailable": "unavailable",
            }.get(gate.status.value, "unavailable")
            st.markdown(f"{badge_markdown(status_badge)} **Gate: {gate.status.value.upper()}**")
            for reason in gate.reasons:
                st.caption(f"• {reason}")
            if gate.missing_cells:
                st.warning(f"Missing: {', '.join(gate.missing_cells)}")
            if gate.extra_cells:
                st.warning(f"Extra: {', '.join(gate.extra_cells)}")
            if gate.incompatible_cells:
                st.error(f"Incompatible: {', '.join(gate.incompatible_cells)}")
            # Demonstrate that unadmitted remains unadmitted
            for att in attached_plan.evidence_attachments:
                if not att.is_admitted:
                    st.caption(
                        f"Unadmitted evidence remains unadmitted: {att.artifact_fingerprint[:12]}… cell {att.cell_id}"  # noqa: E501
                    )

    # --- Export and verifier ---
    section_header(
        "9 · Export and verifier",
        "Deterministic JSON/YAML export and import verifier. Fingerprint excludes wall-clock, paths, secrets.",  # noqa: E501
    )
    # `draft` is always a StudyPlan (set at page entry), so the fallback chain
    # can never be None; annotating it Optional produced false union-attr errors.
    export_target: StudyPlan = (
        st.session_state.get("prereg_evidence_attached")
        or st.session_state.get("prereg_frozen")
        or draft
    )
    col_a, col_b = st.columns(2)
    col_a.download_button(
        "Download JSON",
        data=export_plan_json(export_target),
        file_name=f"{export_target.plan_id}-v{export_target.version}.json",
        mime="application/json",
        width="stretch",
        key="dl_json",
    )
    col_b.download_button(
        "Download YAML",
        data=export_plan_yaml(export_target),
        file_name=f"{export_target.plan_id}-v{export_target.version}.yaml",
        mime="application/yaml",
        width="stretch",
        key="dl_yaml",
    )
    col_a.download_button(
        "Download run matrix CSV",
        data=export_plan_csv(export_target.planned_run_cells),
        file_name=f"{export_target.plan_id}-matrix.csv",
        mime="text/csv",
        width="stretch",
        key="dl_csv",
    )
    st.caption(
        f"Portable identity fingerprint: `{export_target.compute_fingerprint()[:16]}…` (full {export_target.compute_fingerprint()})"  # noqa: E501
    )
    st.caption(
        "Identity binds every scientifically meaningful field, excludes wall-clock/rendering/paths/secrets, uses stable ordering, preserves numeric values losslessly, distinguishes unknown from false."  # noqa: E501
    )

    with st.expander("Verifier / Import existing plan"):
        uploaded = st.file_uploader(
            "Upload JSON or YAML plan", type=["json", "yaml", "yml"], key="prereg_upload"
        )
        pasted = st.text_area("Or paste JSON/YAML", value="", key="prereg_paste")
        if st.button("Verify / Import", key="prereg_verify"):
            payload = None
            if uploaded is not None:
                payload = uploaded.getvalue().decode("utf-8")
            elif pasted.strip():
                payload = pasted.strip()
            if payload:
                try:
                    if payload.lstrip().startswith("{"):
                        plan = import_plan_json(payload)
                    else:
                        try:
                            plan = import_plan_json(payload)
                        except Exception:
                            plan = import_plan_yaml(payload)
                    ok, comp = verify_plan(plan)
                    st.success(
                        f"Import OK: {plan.plan_id} v{plan.version} status {plan.status.value}"
                    )
                    st.caption(
                        f"Fingerprint verify: {'PASS' if ok else 'FAIL'} computed {comp[:12]}… stored {plan.fingerprint[:12] if plan.fingerprint else 'none'}"  # noqa: E501
                    )
                    st.json(plan.model_dump(mode="json"))
                    # Offer to load as draft
                    if st.button("Load as draft", key="load_imported"):
                        st.session_state["prereg_draft"] = plan.model_copy(
                            update={
                                "status": StudyPlanStatus.DRAFT,
                                "fingerprint": None,
                                "frozen_at": None,
                            }
                        )
                        st.success("Loaded as draft.")
                except Exception as exc:
                    st.error(f"Import failed (fail-closed): {exc}")
            else:
                st.info("Provide a file or paste content.")

    # --- Governance notice ---
    with st.expander("Advanced: governance boundaries"):
        st.markdown(
            "- **Authored configuration** vs **synthetic evidence** vs **imported evidence** vs **historical observation** vs **near-live operational** vs **admitted research** vs **unadmitted research** vs **static geographic** vs **unavailable** are never relabelled.\n"  # noqa: E501
            "- Synthetic data is never presented as Manchester observation.\n"
            "- Manual incidents are not observations.\n"
            "- BODS buses are not general traffic.\n"
            "- A frozen plan is not supervisor-approved.\n"
            "- Credentials never imply scientific acceptance.\n"
            "- Non-significance is never relabelled as equivalence.\n"
            "- A successful process exit is not a decision rule.\n"
            "- Generic arbitrary-code analysis language is not created.\n"
        )
