"""Thin Streamlit surface for deterministic STA-01 through STA-05 studies."""

from __future__ import annotations

import streamlit as st

from traffictwin.experiments.equivalence_testing import (
    EquivalenceConclusion,
    EquivalenceMarginBasis,
    EquivalenceStudy,
    EquivalenceStudyConfig,
    EquivalenceStudyStatus,
    equivalence_study_to_csv,
    equivalence_study_to_markdown,
)
from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.experiments.n_way_ranking import (
    NWayRankingConfig,
    NWayRankingStatus,
    NWayRankingStudy,
    n_way_ranking_to_csv,
    n_way_ranking_to_markdown,
)
from traffictwin.experiments.power_analysis import (
    PairedVarianceBasis,
    PowerAnalysis,
    PowerAnalysisConfig,
    PowerAnalysisStatus,
    TargetEffectBasis,
    power_analysis_to_csv,
    power_analysis_to_markdown,
)
from traffictwin.experiments.regression_gate import (
    RegressionGateReport,
    RegressionGateStatus,
    RegressionSubjectKind,
    regression_gate_to_csv,
    regression_gate_to_markdown,
)
from traffictwin.experiments.statistical_study import (
    PairedStudyConfig,
    StatisticalStudy,
    StatisticalStudyStatus,
    statistical_study_pairs_to_csv,
    statistical_study_to_markdown,
)
from traffictwin.ui.charts import bar_figure
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    evaluate_equivalence_study_for_ui,
    evaluate_metric_regression_gate_for_ui,
    evaluate_n_way_ranking_for_ui,
    evaluate_power_analysis_for_ui,
    evaluate_statistical_regression_gate_for_ui,
    evaluate_statistical_study_for_ui,
    load_statistical_study_catalog,
    parse_regression_golden_for_ui,
    regression_metric_runs_for_ui,
    statistical_study_experiments_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import table_column_config


def render(config: UiConfig) -> None:
    """Collect one complete plan and render only typed library output."""

    render_page_header(UiPage.STATISTICAL_STUDY)
    st.warning(
        "Declare the metric, conditions, policy, checkpoint, interval, repetitions, and seed "
        "before inspecting the result. This page does not persist a plan, remove inconvenient "
        "pairs, establish causality, or treat non-significance as equivalence."
    )
    analysis_type = st.radio(
        "Study type",
        [
            "Paired baseline-versus-variation (STA-01)",
            "N-way policy ranking (STA-02)",
            "Paired equivalence TOST (STA-03)",
            "Versioned regression gate (STA-04)",
            "Power analysis helper (STA-05)",
        ],
        horizontal=True,
    )
    if analysis_type.startswith("Power analysis"):
        _render_power_analysis_controls()
        return
    if analysis_type.startswith("Versioned regression"):
        _render_regression_controls(config)
        return

    experiments = statistical_study_experiments_for_ui(config.registry_path)
    if isinstance(experiments, ServiceError):
        _render_error(experiments)
        return
    if not experiments:
        st.info(
            "No registered experiment currently has stored MetricCollections. Import and compute "
            "the predeclared common-seed runs first."
        )
        return
    if analysis_type.startswith("N-way"):
        _render_n_way_controls(config, experiments)
        return
    if analysis_type.startswith("Paired equivalence"):
        _render_equivalence_controls(config, experiments)
        return

    experiment_id = st.selectbox("Registered experiment", experiments)
    catalog = load_statistical_study_catalog(config.registry_path, str(experiment_id))
    if isinstance(catalog, ServiceError):
        _render_error(catalog)
        return
    if not catalog.variation_seed_ids or not catalog.algorithms:
        st.info("The registered plan does not contain a variation and policy comparison.")
        return

    selectors = st.columns(3)
    variation_seed = selectors[0].selectbox("Variation seed", catalog.variation_seed_ids)
    algorithm = selectors[1].selectbox("Policy or algorithm", catalog.algorithms)
    checkpoint = selectors[2].selectbox(
        "Checkpoint",
        catalog.checkpoints,
        format_func=lambda value: str(value) if value is not None else "No checkpoint",
    )
    metric_key = st.selectbox("Primary scalar metric", catalog.metric_keys)
    method_controls = st.columns(4)
    objective = ObjectiveDirection(
        method_controls[0].selectbox(
            "Objective direction",
            [item.value for item in ObjectiveDirection],
        )
    )
    confidence_level = float(
        method_controls[1].selectbox("Interval confidence level", [0.90, 0.95, 0.99], index=1)
    )
    bootstrap_repetitions = int(
        method_controls[2].selectbox(
            "Bootstrap repetitions",
            [1_000, 5_000, 10_000, 50_000],
            index=2,
        )
    )
    randomisation_repetitions = int(
        method_controls[3].selectbox(
            "Randomisation repetitions",
            [1_000, 5_000, 10_000, 50_000],
            index=2,
        )
    )
    resampling_seed = int(
        st.number_input(
            "Deterministic resampling seed",
            min_value=0,
            max_value=2**53 - 1,
            value=20_260_720,
            step=1,
        )
    )
    st.caption(
        f"Registered baseline: {catalog.baseline_seed_id} | Planned common seeds: "
        f"{', '.join(str(seed) for seed in catalog.expected_random_seeds) or 'none'} | Stored "
        f"collections in experiment: {catalog.collection_count}. The difference is always "
        "variation minus baseline; objective affects interpretation only."
    )

    request = PairedStudyConfig(
        experiment_id=catalog.experiment_id,
        baseline_seed_id=catalog.baseline_seed_id,
        variation_seed_id=str(variation_seed),
        algorithm=str(algorithm),
        checkpoint=checkpoint,
        metric_key=str(metric_key),
        objective=objective,
        confidence_level=confidence_level,
        bootstrap_repetitions=bootstrap_repetitions,
        randomisation_repetitions=randomisation_repetitions,
        resampling_seed=resampling_seed,
        expected_random_seeds=catalog.expected_random_seeds,
    )
    if st.button("Evaluate paired study", type="primary"):
        st.session_state["statistical_study"] = evaluate_statistical_study_for_ui(
            config.registry_path,
            request,
        )

    result = st.session_state.get("statistical_study")
    if isinstance(result, ServiceError):
        _render_error(result)
        return
    if not isinstance(result, StatisticalStudy):
        st.info("Complete the analysis plan and run the paired study.")
        return
    if result.config_fingerprint != request.fingerprint():
        st.info("The analysis controls changed. Evaluate the paired study again for this plan.")
        return
    _render_study(result)


def _render_power_analysis_controls() -> None:
    """Collect one prospective plan and delegate all calculations to STA-05."""

    st.warning(
        "This prospective normal-approximation result is a planning aid, not guaranteed achieved "
        "power or evidence about a completed study. Declare and defend the target effect and "
        "paired-difference variance before confirmatory results are inspected."
    )
    identity = st.columns(2)
    metric_key = identity[0].text_input(
        "Power-analysis metric key",
        value="task.completion.rate",
    )
    unit = identity[1].text_input("Power-analysis metric unit", value="ratio")
    inputs = st.columns(4)
    target_effect = float(
        inputs[0].number_input(
            "Target paired effect",
            value=0.05,
            format="%.12g",
            help="Signed variation-minus-baseline effect in the metric's original unit.",
        )
    )
    paired_variance = float(
        inputs[1].number_input(
            "Paired-difference variance",
            min_value=0.0,
            value=0.0025,
            format="%.12g",
            help="Prospective variance in the metric unit squared.",
        )
    )
    alpha = float(inputs[2].selectbox("Two-sided alpha", [0.10, 0.05, 0.025, 0.01], index=1))
    target_power = float(
        inputs[3].selectbox("Target planning power", [0.80, 0.85, 0.90, 0.95], index=0)
    )
    bases = st.columns(2)
    target_effect_basis = TargetEffectBasis(
        bases[0].selectbox(
            "Target-effect basis",
            [item.value for item in TargetEffectBasis],
            index=3,
        )
    )
    variance_basis = PairedVarianceBasis(
        bases[1].selectbox(
            "Paired-variance basis",
            [item.value for item in PairedVarianceBasis],
            index=2,
        )
    )
    target_effect_justification = st.text_input(
        "Target-effect justification",
        value="Explicit synthetic target for prospective method demonstration",
    )
    variance_justification = st.text_input(
        "Paired-variance justification",
        value="Explicit synthetic variance for prospective method demonstration",
    )
    references = st.columns(2)
    target_effect_reference = references[0].text_input(
        "Target-effect reference (required for literature basis)",
        value="",
    )
    variance_reference = references[1].text_input(
        "Variance reference (required for literature basis)",
        value="",
    )
    flags = st.columns(3)
    uses_pilot = (
        target_effect_basis is TargetEffectBasis.PILOT_STUDY
        or variance_basis is PairedVarianceBasis.PILOT_STUDY
    )
    pilot_sample_size = (
        int(
            flags[0].number_input(
                "Pilot common-seed pairs",
                min_value=2,
                value=10,
                step=1,
            )
        )
        if uses_pilot
        else None
    )
    synthetic = bool(
        flags[1].checkbox(
            "Inputs are synthetic",
            value=True,
            help="Required when either input basis is synthetic.",
        )
    )
    maximum_replicates = int(
        flags[2].number_input(
            "Maximum common-seed pairs",
            min_value=3,
            max_value=1_000_000,
            value=100_000,
            step=1,
        )
    )
    if not metric_key.strip() or not unit.strip():
        st.info("Provide a non-empty metric key and original unit.")
        return
    if len(target_effect_justification.strip()) < 12 or len(variance_justification.strip()) < 12:
        st.info("Provide both planning-input justifications with at least 12 characters.")
        return
    if target_effect_basis is TargetEffectBasis.LITERATURE and not target_effect_reference.strip():
        st.info("A literature target-effect basis requires a reference.")
        return
    if variance_basis is PairedVarianceBasis.LITERATURE and not variance_reference.strip():
        st.info("A literature variance basis requires a reference.")
        return
    uses_synthetic_basis = (
        target_effect_basis is TargetEffectBasis.SYNTHETIC
        or variance_basis is PairedVarianceBasis.SYNTHETIC
    )
    if uses_synthetic_basis and not synthetic:
        st.info("Mark the inputs synthetic when either planning basis is synthetic.")
        return
    request = PowerAnalysisConfig(
        metric_key=metric_key,
        unit=unit,
        target_effect=target_effect,
        paired_difference_variance=paired_variance,
        alpha=alpha,
        target_power=target_power,
        target_effect_basis=target_effect_basis,
        target_effect_justification=target_effect_justification,
        target_effect_reference=target_effect_reference or None,
        variance_basis=variance_basis,
        variance_justification=variance_justification,
        variance_reference=variance_reference or None,
        pilot_sample_size=pilot_sample_size,
        synthetic=synthetic,
        maximum_replicates=maximum_replicates,
    )
    if st.button("Calculate required common-seed pairs", type="primary"):
        st.session_state["power_analysis"] = evaluate_power_analysis_for_ui(request)
    result = st.session_state.get("power_analysis")
    if isinstance(result, ServiceError):
        _render_error(result)
        return
    if not isinstance(result, PowerAnalysis):
        st.info("Declare the prospective planning inputs and calculate the required pair count.")
        return
    if result.config_fingerprint != request.fingerprint():
        st.info("The planning controls changed. Calculate the power analysis again.")
        return
    _render_power_analysis(result)


def _render_power_analysis(analysis: PowerAnalysis) -> None:
    """Render only values already computed by the STA-05 library service."""

    result = analysis.calculation
    st.subheader("Prospective Paired Common-Seed Power Plan")
    st.markdown(f"**Planning status:** {badge_markdown(analysis.status.value)}")
    cards = st.columns(3)
    cards[0].metric(
        "Required common-seed pairs",
        result.required_common_seed_replicates or "Unavailable",
        border=True,
    )
    cards[1].metric(
        "Required policy runs",
        result.required_total_policy_runs or "Unavailable",
        border=True,
    )
    cards[2].metric("Approximate power", _display(result.achieved_power), border=True)
    with st.container(border=True):
        st.markdown("**Declared study design**")
        design = st.columns(2)
        design[0].markdown(
            f"**Labels:** {', '.join(item.value for item in analysis.labels)}\n\n"
            f"**Target effect:** {analysis.config.target_effect}\n\n"
            f"**Paired-difference variance:** {analysis.config.paired_difference_variance}\n\n"
            f"**Standardised effect magnitude:** {result.standardised_effect_magnitude}"
        )
        design[1].markdown(
            f"**Alpha:** {analysis.config.alpha}\n\n"
            f"**Target power:** {analysis.config.target_power}\n\n"
            f"**Preceding replicate count:** {result.preceding_replicate_count}\n\n"
            f"**Preceding power:** {result.preceding_power}"
        )
        st.caption(f"Reason code: {result.reason_code.value}")
    if analysis.status is PowerAnalysisStatus.UNAVAILABLE:
        st.warning(result.reason or "This planning calculation is unavailable.")
    else:
        st.success(
            "The displayed integer is the smallest evaluated count meeting the declared target "
            "under the versioned normal-approximation assumptions."
        )
    st.caption(
        "Planning power is not guaranteed achieved power. The helper assumes complete compatible "
        "baseline/variation pairs and does not inflate for attrition, missing evidence, or "
        "multiple comparisons."
    )
    downloads = st.columns(3)
    downloads[0].download_button(
        "Download PowerAnalysis JSON",
        data=analysis.to_json(),
        file_name=f"{analysis.analysis_id}.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Download PowerAnalysis Markdown",
        data=power_analysis_to_markdown(analysis),
        file_name=f"{analysis.analysis_id}.md",
        mime="text/markdown",
    )
    downloads[2].download_button(
        "Download PowerAnalysis CSV",
        data=power_analysis_to_csv(analysis),
        file_name=f"{analysis.analysis_id}.csv",
        mime="text/csv",
    )
    with st.expander("Advanced/Evidence: planning provenance, warnings, assumptions, limitations"):
        st.json(
            {
                "config": analysis.config.model_dump(mode="json"),
                "config_fingerprint": analysis.config_fingerprint,
                "provenance": analysis.provenance,
                "warnings": analysis.warnings,
                "assumptions": analysis.assumptions,
                "limitations": analysis.limitations,
                "analysis_fingerprint": analysis.fingerprint(),
            }
        )


def _render_regression_controls(config: UiConfig) -> None:
    """Load one approved golden and delegate its typed target to STA-04."""

    st.warning(
        "A regression pass applies only to the approved scalar assertions in the uploaded golden "
        "contract. Missing or incompatible evidence is unavailable, not a pass or numerical "
        "failure. The evaluator never rewrites or approves the golden."
    )
    uploaded = st.file_uploader(
        "Versioned regression golden contract (JSON)",
        type=["json"],
        key="regression_golden_upload",
    )
    if uploaded is None:
        st.info(
            "Upload a golden generated with `traffictwin experiment regression-golden`. Candidate "
            "contracts remain unavailable until explicitly approved."
        )
        return
    contract = parse_regression_golden_for_ui(uploaded.getvalue())
    if isinstance(contract, ServiceError):
        _render_error(contract)
        return
    st.write(
        {
            "contract_id": contract.contract_id,
            "contract_version": contract.contract_version,
            "approval_status": contract.approval_status.value,
            "subject_kind": contract.subject_kind.value,
            "source_identity_policy": contract.source_identity_policy.value,
            "assertion_count": len(contract.assertions),
            "contract_fingerprint": contract.fingerprint(),
        }
    )
    if contract.subject_kind is RegressionSubjectKind.METRIC_COLLECTION:
        runs = regression_metric_runs_for_ui(config.registry_path)
        if isinstance(runs, ServiceError):
            _render_error(runs)
            return
        if not runs:
            st.info("No stored MetricCollection is available for this golden contract.")
            return
        run_id = st.selectbox("Regression subject run", runs)
        if st.button("Evaluate regression gate", type="primary"):
            st.session_state["regression_gate"] = evaluate_metric_regression_gate_for_ui(
                config.registry_path,
                str(run_id),
                contract,
            )
    else:
        study = st.session_state.get("statistical_study")
        if not isinstance(study, StatisticalStudy):
            st.info(
                "Evaluate a paired STA-01 study in this session first, then return to this mode "
                "with its approved paired-study golden."
            )
            return
        st.caption(f"Current paired-study subject: {study.study_id}")
        if st.button("Evaluate regression gate", type="primary"):
            st.session_state["regression_gate"] = evaluate_statistical_regression_gate_for_ui(
                study,
                contract,
            )
    result = st.session_state.get("regression_gate")
    if isinstance(result, ServiceError):
        _render_error(result)
        return
    if not isinstance(result, RegressionGateReport):
        st.info("Select the typed subject and evaluate the uploaded golden contract.")
        return
    if result.contract_fingerprint != contract.fingerprint():
        st.info("The uploaded golden changed. Evaluate the regression gate again.")
        return
    _render_regression_gate(result)


def _render_regression_gate(report: RegressionGateReport) -> None:
    """Render only the complete typed STA-04 decision and check audit."""

    st.subheader("Versioned Regression Gate And Assertion Audit")
    st.markdown(f"**Gate status:** {badge_markdown(report.status.value)}")
    cards = st.columns(3)
    cards[0].metric("Passed checks", report.passed_count, border=True)
    cards[1].metric("Failed checks", report.failed_count, border=True)
    cards[2].metric("Unavailable checks", report.unavailable_count, border=True)
    if report.status is RegressionGateStatus.FAILED:
        st.error("At least one complete scalar assertion exceeded its declared tolerance.")
    elif report.status is RegressionGateStatus.UNAVAILABLE:
        st.warning("The complete gate could not be decided from compatible available evidence.")
    else:
        st.success("Every declared scalar assertion passed its versioned tolerance.")
    check_rows = [
        {
            "selector": check.selector,
            "status": check.status.value,
            "expected": check.expected_value,
            "actual": check.actual_value,
            "unit": check.unit,
            "absolute_tolerance": check.absolute_tolerance,
            "relative_tolerance": check.relative_tolerance,
            "allowed_error": check.allowed_error,
            "absolute_error": check.absolute_error,
            "reason": check.reason_code.value,
        }
        for check in report.checks
    ]
    st.dataframe(
        check_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(check_rows),
    )
    if report.blocking_findings:
        with st.expander("Advanced/Evidence: blocking compatibility findings"):
            st.json([finding.model_dump(mode="json") for finding in report.blocking_findings])
    downloads = st.columns(3)
    downloads[0].download_button(
        "Download RegressionGate JSON",
        data=report.to_json(),
        file_name=f"{report.gate_id}.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Download RegressionGate Markdown",
        data=regression_gate_to_markdown(report),
        file_name=f"{report.gate_id}.md",
        mime="text/markdown",
    )
    downloads[2].download_button(
        "Download RegressionGate CSV",
        data=regression_gate_to_csv(report),
        file_name=f"{report.gate_id}.csv",
        mime="text/csv",
    )
    with st.expander("Advanced/Evidence: golden, provenance, warnings, and limitations"):
        st.json(
            {
                "golden_contract": report.contract.model_dump(mode="json"),
                "subject_fingerprint": report.subject_fingerprint,
                "source_identity_fingerprint": report.source_identity_fingerprint,
                "provenance": report.provenance,
                "warnings": report.warnings,
                "limitations": report.limitations,
                "report_fingerprint": report.fingerprint(),
            }
        )


def _render_equivalence_controls(config: UiConfig, experiments: list[str]) -> None:
    """Collect one predeclared margin and delegate paired TOST to the typed service."""

    st.warning(
        "The equivalence margin must have a practical, literature, or explicitly provisional "
        "basis chosen before this result is inspected. Failed TOST means equivalence was not "
        "demonstrated; it does not prove a meaningful difference."
    )
    experiment_id = st.selectbox(
        "Registered equivalence experiment",
        experiments,
        key="equivalence_experiment_id",
    )
    catalog = load_statistical_study_catalog(config.registry_path, str(experiment_id))
    if isinstance(catalog, ServiceError):
        _render_error(catalog)
        return
    if not catalog.variation_seed_ids or not catalog.algorithms:
        st.info("The registered plan does not contain a paired comparison.")
        return
    selectors = st.columns(3)
    variation_seed = selectors[0].selectbox(
        "Equivalence variation seed",
        catalog.variation_seed_ids,
    )
    algorithm = selectors[1].selectbox("Equivalence policy or algorithm", catalog.algorithms)
    checkpoint = selectors[2].selectbox(
        "Equivalence checkpoint",
        catalog.checkpoints,
        format_func=lambda value: str(value) if value is not None else "No checkpoint",
    )
    metric_key = st.selectbox("Equivalence scalar metric", catalog.metric_keys)
    method_controls = st.columns(4)
    objective = ObjectiveDirection(
        method_controls[0].selectbox(
            "Equivalence objective direction",
            [item.value for item in ObjectiveDirection],
        )
    )
    margin = float(
        method_controls[1].number_input(
            "Absolute equivalence margin",
            min_value=1e-12,
            value=0.05,
            format="%.12g",
            help="Use the selected metric's original unit.",
        )
    )
    margin_basis = EquivalenceMarginBasis(
        method_controls[2].selectbox(
            "Margin basis",
            [item.value for item in EquivalenceMarginBasis],
            index=2,
        )
    )
    alpha = float(
        method_controls[3].selectbox(
            "One-sided alpha",
            [0.10, 0.05, 0.025, 0.01],
            index=1,
        )
    )
    margin_justification = st.text_input(
        "Margin justification",
        value="Provisional design margin for exploratory synthetic analysis",
    )
    margin_reference = st.text_input(
        "Margin reference (required for literature basis)",
        value="",
    )
    st.caption(
        f"Registered baseline: {catalog.baseline_seed_id} | Planned common seeds: "
        f"{', '.join(str(seed) for seed in catalog.expected_random_seeds) or 'none'} | Stored "
        f"collections: {catalog.collection_count}. The margin is symmetric around a "
        "variation-minus-baseline difference of zero."
    )
    if len(margin_justification.strip()) < 12:
        st.info("Provide a margin justification of at least 12 characters.")
        return
    if margin_basis is EquivalenceMarginBasis.LITERATURE and not margin_reference.strip():
        st.info("A literature-based margin requires a reference.")
        return
    request = EquivalenceStudyConfig(
        experiment_id=catalog.experiment_id,
        baseline_seed_id=catalog.baseline_seed_id,
        variation_seed_id=str(variation_seed),
        algorithm=str(algorithm),
        checkpoint=checkpoint,
        metric_key=str(metric_key),
        objective=objective,
        equivalence_margin=margin,
        margin_basis=margin_basis,
        margin_justification=margin_justification,
        margin_reference=margin_reference or None,
        alpha=alpha,
        expected_random_seeds=catalog.expected_random_seeds,
    )
    if st.button("Evaluate equivalence study", type="primary"):
        st.session_state["equivalence_study"] = evaluate_equivalence_study_for_ui(
            config.registry_path,
            request,
        )
    result = st.session_state.get("equivalence_study")
    if isinstance(result, ServiceError):
        _render_error(result)
        return
    if not isinstance(result, EquivalenceStudy):
        st.info("Declare the margin and evaluate the paired equivalence study.")
        return
    if result.config_fingerprint != request.fingerprint():
        st.info("The analysis controls changed. Evaluate the equivalence study again.")
        return
    _render_equivalence_study(result)


def _render_equivalence_study(study: EquivalenceStudy) -> None:
    """Render only values already computed by the STA-03 library service."""

    tost = study.tost
    st.subheader("Paired TOST Equivalence Result And Common-Seed Audit")
    st.markdown(
        f"**Study status:** {badge_markdown(study.status.value)} · "
        f"**Conclusion:** {badge_markdown(tost.conclusion.value)}"
    )
    cards = st.columns(2)
    cards[0].metric("Eligible pairs", study.pairing_audit.eligible_pair_count, border=True)
    cards[1].metric(
        "Mean paired difference",
        _display(tost.mean_paired_difference, study.metric_unit),
        border=True,
    )
    st.caption(
        f"Study {study.study_id} | Method {study.method_version} | Margin "
        f"({tost.margin_lower:.6g}, {tost.margin_upper:.6g}) {study.metric_unit or ''} | "
        f"Basis: {study.config.margin_basis.value}"
    )
    if study.status is EquivalenceStudyStatus.AVAILABLE:
        results = st.columns(4)
        results[0].metric(
            f"{tost.interval.confidence_level:.0%} Student-t interval",
            f"[{_display(tost.interval.lower)}, {_display(tost.interval.upper)}]",
        )
        results[1].metric(
            "Lower one-sided p",
            _display(tost.lower_test.p_value if tost.lower_test is not None else None),
        )
        results[2].metric(
            "Upper one-sided p",
            _display(tost.upper_test.p_value if tost.upper_test is not None else None),
        )
        rejected = tost.conclusion is EquivalenceConclusion.DEMONSTRATED
        with results[3], st.container(border=True):
            st.caption("Both one-sided nulls rejected")
            st.markdown(badge_markdown("yes" if rejected else "no"))
    else:
        st.info(tost.reason or "Paired TOST is unavailable.")
    with st.container(border=True):
        st.markdown("**Predeclared margin design**")
        st.markdown(
            f"**Basis:** {study.config.margin_basis.value} · **Alpha:** {study.config.alpha}\n\n"
            f"**Justification:** {study.config.margin_justification or 'none'}\n\n"
            f"**Reference:** {study.config.margin_reference or 'none'}"
        )
    st.caption(
        "Equivalence requires both predeclared one-sided tests to reject. An ordinary "
        "non-significant difference test is not equivalence, and failed TOST does not prove "
        "meaningful difference."
    )
    if study.observations:
        observation_rows = [
            {
                "random_seed": row.random_seed,
                "baseline_run": row.baseline_run_id,
                "variation_run": row.variation_run_id,
                "baseline": row.baseline_value,
                "variation": row.variation_value,
                "variation_minus_baseline": row.paired_difference,
            }
            for row in study.observations
        ]
        st.dataframe(
            observation_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                observation_rows,
                units=(
                    {
                        "baseline": study.metric_unit,
                        "variation": study.metric_unit,
                        "variation_minus_baseline": study.metric_unit,
                    }
                    if study.metric_unit
                    else None
                ),
            ),
        )
    with st.expander("Advanced/Evidence: complete inherited STA-01 pairing audit"):
        st.json(study.pairing_audit.model_dump(mode="json"))
    downloads = st.columns(3)
    downloads[0].download_button(
        "Download EquivalenceStudy JSON",
        data=study.to_json(),
        file_name=f"{study.study_id}.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Download Equivalence Markdown",
        data=equivalence_study_to_markdown(study),
        file_name=f"{study.study_id}.md",
        mime="text/markdown",
    )
    downloads[2].download_button(
        "Download Equivalence Audit CSV",
        data=equivalence_study_to_csv(study),
        file_name=f"{study.study_id}-audit.csv",
        mime="text/csv",
    )
    with st.expander("Advanced/Evidence: equivalence plan, provenance, assumptions, limitations"):
        st.json(
            {
                "config": study.config.model_dump(mode="json"),
                "config_fingerprint": study.config_fingerprint,
                "source_paired_study_fingerprint": study.source_paired_study_fingerprint,
                "provenance": study.provenance,
                "warnings": study.warnings,
                "assumptions": study.assumptions,
                "limitations": study.limitations,
                "study_fingerprint": study.fingerprint(),
            }
        )


def _render_n_way_controls(config: UiConfig, experiments: list[str]) -> None:
    """Collect one complete N-way plan and delegate it to the typed service."""

    st.warning(
        "Policies are ranked independently inside each selected scenario family over identical "
        "complete common seeds. Numerical ties are not equivalence, interval overlap is not a "
        "test, and incompatible contracts receive no rank."
    )
    experiment_id = st.selectbox(
        "Registered N-way experiment",
        experiments,
        key="n_way_experiment_id",
    )
    catalog = load_statistical_study_catalog(config.registry_path, str(experiment_id))
    if isinstance(catalog, ServiceError):
        _render_error(catalog)
        return
    if len(catalog.algorithms) < 2:
        st.info("The registered plan needs at least two policies for an N-way ranking.")
        return
    seed_options = [catalog.baseline_seed_id, *catalog.variation_seed_ids]
    seed_ids = st.multiselect(
        "Scenario families",
        seed_options,
        default=seed_options,
        help="Each family receives its own policy ranking; scenarios are never pooled.",
    )
    algorithms = st.multiselect(
        "Policies or algorithms",
        catalog.algorithms,
        default=catalog.algorithms,
        help="Select at least two policies declared by the registered experiment.",
    )
    controls = st.columns(3)
    checkpoint = controls[0].selectbox(
        "N-way checkpoint",
        catalog.checkpoints,
        format_func=lambda value: str(value) if value is not None else "No checkpoint",
    )
    metric_key = controls[1].selectbox("N-way scalar metric", catalog.metric_keys)
    objective = ObjectiveDirection(
        controls[2].selectbox(
            "N-way objective direction",
            [item.value for item in ObjectiveDirection],
        )
    )
    method_controls = st.columns(4)
    confidence_level = float(
        method_controls[0].selectbox(
            "N-way confidence level",
            [0.90, 0.95, 0.99],
            index=1,
        )
    )
    bootstrap_repetitions = int(
        method_controls[1].selectbox(
            "N-way bootstrap repetitions",
            [1_000, 5_000, 10_000, 50_000],
            index=2,
        )
    )
    resampling_seed = int(
        method_controls[2].number_input(
            "N-way resampling seed",
            min_value=0,
            max_value=2**53 - 1,
            value=20_260_720,
            step=1,
        )
    )
    tie_tolerance = float(
        method_controls[3].number_input(
            "Absolute tie tolerance",
            min_value=0.0,
            value=1e-12,
            format="%.12g",
        )
    )
    st.caption(
        f"Planned common seeds: "
        f"{', '.join(str(seed) for seed in catalog.expected_random_seeds) or 'none'} | "
        f"Stored collections: {catalog.collection_count}. Joint resampling keeps every selected "
        "policy together within a seed row."
    )
    if len(seed_ids) < 1 or len(algorithms) < 2:
        st.info("Select at least one scenario family and two policies.")
        return
    request = NWayRankingConfig(
        experiment_id=catalog.experiment_id,
        seed_ids=[str(seed_id) for seed_id in seed_ids],
        algorithms=[str(algorithm) for algorithm in algorithms],
        checkpoint=checkpoint,
        metric_key=str(metric_key),
        objective=objective,
        confidence_level=confidence_level,
        bootstrap_repetitions=bootstrap_repetitions,
        resampling_seed=resampling_seed,
        tie_tolerance=tie_tolerance,
        expected_random_seeds=catalog.expected_random_seeds,
    )
    if st.button("Evaluate N-way ranking", type="primary"):
        st.session_state["n_way_ranking_study"] = evaluate_n_way_ranking_for_ui(
            config.registry_path,
            request,
        )
    result = st.session_state.get("n_way_ranking_study")
    if isinstance(result, ServiceError):
        _render_error(result)
        return
    if not isinstance(result, NWayRankingStudy):
        st.info("Complete the plan and evaluate the N-way ranking.")
        return
    if result.config_fingerprint != request.fingerprint():
        st.info("The analysis controls changed. Evaluate the N-way ranking again.")
        return
    _render_n_way_study(result)


def _render_n_way_study(study: NWayRankingStudy) -> None:
    """Render only values already computed by the N-way library service."""

    st.subheader("N-Way Policy Ranking And Common-Seed Audit")
    st.markdown(f"**Study status:** {badge_markdown(study.status.value)}")
    cards = st.columns(3)
    cards[0].metric("Scenario families", len(study.entries), border=True)
    cards[1].metric(
        "Available families",
        sum(entry.status is NWayRankingStatus.AVAILABLE for entry in study.entries),
        border=True,
    )
    cards[2].metric(
        "Complete seed rows",
        sum(entry.audit.complete_seed_count for entry in study.entries),
        border=True,
    )
    st.caption(
        f"Study {study.study_id} | Config {study.config_fingerprint[:16]}… | "
        f"Method {study.method_version} | {study.config.bootstrap_repetitions} joint bootstrap "
        "repetitions."
    )
    for entry in study.entries:
        st.markdown(f"### Scenario family `{entry.seed_id}`")
        st.caption(
            f"Status: {entry.status.value} | complete={entry.audit.complete_seed_count} | "
            f"incomplete={len(entry.audit.incomplete_random_seeds)} | "
            f"incompatible={len(entry.audit.incompatible_random_seeds)} | "
            f"exclusions={entry.audit.exclusion_count} | bootstrap seed={entry.bootstrap.seed}"
        )
        if entry.policy_ranks:
            rank_rows = [
                {
                    "rank": row.rank,
                    "policy": row.algorithm,
                    "n": row.observation_count,
                    "mean": row.mean,
                    "mean_interval_lower": row.mean_interval_lower,
                    "mean_interval_upper": row.mean_interval_upper,
                    "top_rank_frequency": row.top_rank_frequency,
                    "rank_interval": (
                        f"[{row.rank_interval_lower}, {row.rank_interval_upper}]"
                        if row.rank_interval_lower is not None
                        else "Unavailable"
                    ),
                    "regret": row.regret,
                    "winner": row.winner,
                }
                for row in entry.policy_ranks
            ]
            st.dataframe(
                rank_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(rank_rows),
            )
        else:
            st.info(entry.status_reason or "No compatible policy ranking is available.")
        with st.expander(f"Advanced/Evidence: common-seed audit — {entry.seed_id}"):
            st.json(entry.audit.model_dump(mode="json"))
            if entry.observations:
                st.dataframe(
                    [
                        {
                            "random_seed": row.random_seed,
                            **row.values_by_algorithm,
                        }
                        for row in entry.observations
                    ],
                    hide_index=True,
                    width="stretch",
                )
    downloads = st.columns(3)
    downloads[0].download_button(
        "Download NWayRankingStudy JSON",
        data=study.to_json(),
        file_name=f"{study.study_id}.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Download N-Way Markdown",
        data=n_way_ranking_to_markdown(study),
        file_name=f"{study.study_id}.md",
        mime="text/markdown",
    )
    downloads[2].download_button(
        "Download N-Way Audit CSV",
        data=n_way_ranking_to_csv(study),
        file_name=f"{study.study_id}-audit.csv",
        mime="text/csv",
    )
    with st.expander("Advanced/Evidence: N-way plan, provenance, assumptions, and limitations"):
        st.json(
            {
                "config": study.config.model_dump(mode="json"),
                "config_fingerprint": study.config_fingerprint,
                "provenance": study.provenance,
                "warnings": study.warnings,
                "assumptions": study.assumptions,
                "limitations": study.limitations,
                "study_fingerprint": study.fingerprint(),
            }
        )


def _render_study(study: StatisticalStudy) -> None:
    """Render the typed study without calculating scientific values in Streamlit."""

    st.subheader("Pairing Audit And Statistical Results")
    audit = study.pairing_audit
    source_mode = (
        "synthetic"
        if study.synthetic is True
        else "imported"
        if study.synthetic is False
        else "unavailable"
    )
    st.markdown(
        f"**Study status:** {badge_markdown(study.status.value)} · "
        f"**Source mode:** {badge_markdown(source_mode)}"
    )
    cards = st.columns(3)
    cards[0].metric("Eligible pairs", audit.eligible_pair_count, border=True)
    cards[1].metric("Excluded inputs/pairs", audit.exclusion_count, border=True)
    cards[2].metric(
        "Mean paired difference",
        _display(study.estimate.mean_paired_difference, study.metric_unit),
        border=True,
    )
    st.caption(
        f"Study {study.study_id} | Method {study.method_version}. The difference is always "
        "variation minus baseline; objective affects interpretation only, never causality."
    )

    results_tab, pairs_tab, audit_tab, evidence_tab = st.tabs(
        ["Results", "Paired observations", "Pairing audit", "Exports & evidence"]
    )

    with results_tab:
        if study.status is StatisticalStudyStatus.AVAILABLE:
            results = st.columns(4)
            results[0].metric(
                f"{study.bootstrap_interval.confidence_level:.0%} bootstrap interval",
                f"[{_display(study.bootstrap_interval.lower)}, "
                f"{_display(study.bootstrap_interval.upper)}]",
                border=True,
            )
            results[1].metric(
                "Two-sided sign-flip p", _display(study.randomisation_test.p_value), border=True
            )
            results[2].metric("Cohen's dz", _display(study.effect_sizes.cohen_dz), border=True)
            results[3].metric(
                "Matched rank-biserial",
                _display(study.effect_sizes.matched_pairs_rank_biserial),
                border=True,
            )
            st.caption(
                f"Randomisation mode: {study.randomisation_test.mode.value}; evaluated "
                f"{study.randomisation_test.evaluated_assignments} assignments. The p-value does "
                "not measure effect size, practical importance, equivalence, or causal evidence."
            )
        else:
            st.info(study.estimate.reason or "Inferential components are unavailable.")

    with pairs_tab:
        if study.observations:
            observation_rows = [
                {
                    "random_seed": row.random_seed,
                    "baseline_run": row.baseline_run_id,
                    "variation_run": row.variation_run_id,
                    "baseline": row.baseline_value,
                    "variation": row.variation_value,
                    "variation_minus_baseline": row.paired_difference,
                    "objective_interpretation": row.interpretation.value,
                }
                for row in study.observations
            ]
            st.dataframe(
                observation_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(
                    observation_rows,
                    units=(
                        {
                            "baseline": study.metric_unit,
                            "variation": study.metric_unit,
                            "variation_minus_baseline": study.metric_unit,
                        }
                        if study.metric_unit
                        else None
                    ),
                ),
            )
            differences = [
                float(row.paired_difference)
                for row in study.observations
                if row.paired_difference is not None
            ]
            if differences:
                labels = [
                    str(row.random_seed)
                    for row in study.observations
                    if row.paired_difference is not None
                ]
                y_title = "Difference" + (f" ({study.metric_unit})" if study.metric_unit else "")
                st.plotly_chart(
                    bar_figure(
                        labels,
                        differences,
                        title="Per-seed variation minus baseline",
                        y_title=y_title,
                    ),
                    width="stretch",
                )
                st.caption(
                    "Signed per-seed differences over already-computed pairs; direction is not "
                    "favourability."
                )
        else:
            st.info("No compatible common-seed pairs were admitted.")

    with audit_tab:
        audit_columns = st.columns(2)
        audit_columns[0].markdown(
            f"**Expected random seeds:** {_seed_list(audit.expected_random_seeds)}\n\n"
            f"**Eligible random seeds:** {_seed_list(audit.eligible_random_seeds)}\n\n"
            f"**Missing expected seeds:** {_seed_list(audit.missing_expected_random_seeds)}"
        )
        audit_columns[1].markdown(
            f"**Unmatched baseline seeds:** {_seed_list(audit.unmatched_baseline_random_seeds)}\n\n"
            f"**Unmatched variation seeds:** "
            f"{_seed_list(audit.unmatched_variation_random_seeds)}\n\n"
            f"**Duplicate baseline seeds:** {_seed_list(audit.duplicate_baseline_random_seeds)} · "
            f"**Duplicate variation seeds:** {_seed_list(audit.duplicate_variation_random_seeds)}"
        )
        if audit.exclusions:
            exclusion_rows = [item.model_dump(mode="json") for item in audit.exclusions]
            st.dataframe(
                exclusion_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(exclusion_rows),
            )
        else:
            st.success("No input or pair exclusions were recorded.")

    with evidence_tab:
        downloads = st.columns(3)
        downloads[0].download_button(
            "Download StatisticalStudy JSON",
            data=study.to_json(),
            file_name=f"{study.study_id}.json",
            mime="application/json",
        )
        downloads[1].download_button(
            "Download Study Markdown",
            data=statistical_study_to_markdown(study),
            file_name=f"{study.study_id}.md",
            mime="text/markdown",
        )
        downloads[2].download_button(
            "Download Pair Audit CSV",
            data=statistical_study_pairs_to_csv(study),
            file_name=f"{study.study_id}-pairs.csv",
            mime="text/csv",
        )
        with st.expander("Advanced/Evidence: complete plan, provenance, assumptions, limitations"):
            st.json(
                {
                    "config": study.config.model_dump(mode="json"),
                    "config_fingerprint": study.config_fingerprint,
                    "compatibility_signature_fingerprint": (
                        study.compatibility_signature_fingerprint
                    ),
                    "provenance": study.provenance,
                    "warnings": study.warnings,
                    "assumptions": study.assumptions,
                    "limitations": study.limitations,
                    "study_fingerprint": study.fingerprint(),
                }
            )


def _display(value: float | None, unit: str | None = None) -> str:
    if value is None:
        return "Unavailable"
    suffix = f" {unit}" if unit else ""
    return f"{value:.6g}{suffix}"


def _seed_list(seeds: object) -> str:
    """Render a sequence of seeds as a compact human string."""

    if not isinstance(seeds, (list, tuple)) or not seeds:
        return "none"
    return ", ".join(str(seed) for seed in seeds)


def _render_error(error: ServiceError) -> None:
    st.error(error.message)
    if error.detail:
        st.code(error.detail)
