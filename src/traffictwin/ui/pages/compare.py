"""What-if comparison page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.metrics.comparison import ComparisonReport
from traffictwin.provenance.completeness import provenance_completeness_report_to_csv
from traffictwin.provenance.differences import difference_contribution_report_to_csv
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.first_run import first_run_guidance
from traffictwin.ui.labels import UiPage
from traffictwin.ui.services import (
    BundleAnalysis,
    ServiceError,
    compare_runs_for_ui,
    comparison_provenance_completeness_for_ui,
    difference_contributions_for_ui,
    validate_bundle_for_ui,
)
from traffictwin.ui.tables import ColumnDisplay, comparison_rows, table_column_config


def _provenance_badge(synthetic_flag: object) -> str:
    """Render a three-state provenance badge without collapsing unknown to a definite state."""

    if synthetic_flag is None:
        return ":gray-badge[UNKNOWN]"
    return badge_markdown("synthetic") if bool(synthetic_flag) else ":gray-badge[IMPORTED]"


def render() -> None:
    """Render comparison page."""

    st.title("What-if Compare")
    # AUTHORITATIVE state: last successfully validated/comparable pair
    committed_baseline = str(
        st.session_state.get("selected_baseline_run", "tests/fixtures/bundles/baseline_valid")
    )
    committed_variation = str(
        st.session_state.get("selected_variation_run", "tests/fixtures/bundles/variation_valid")
    )
    # Draft inputs: must not become authoritative merely because typed
    baseline_draft = st.text_input(
        "Baseline bundle path",
        value=committed_baseline,
    )
    variation_draft = st.text_input(
        "Variation bundle path",
        value=committed_variation,
    )
    # Strip BEFORE Path construction — Path("") == Path(".") would corrupt session
    baseline_str = baseline_draft.strip()
    variation_str = variation_draft.strip()
    if not baseline_str or not variation_str:
        st.error("Both baseline and variation bundle paths must be selected.")
        first_run_guidance(
            actions=[
                ("Start Guided Demo", UiPage.GUIDED_DEMO),
                ("Import a Run Bundle", UiPage.BUNDLE_IMPORT),
            ],
            message=(
                "A comparison needs two existing run bundles. The guided demo creates "
                "a baseline and a stressed variation to compare, or import your own "
                "bundles and enter their paths above."
            ),
            key_prefix="compare_first_run",
        )
        return
    # Construct Path only from non-blank strings
    baseline_path = Path(baseline_str)
    variation_path = Path(variation_str)
    if not baseline_path.exists() and not variation_path.exists():
        st.error("Both baseline and variation bundle paths do not exist.")
        first_run_guidance(
            actions=[
                ("Start Guided Demo", UiPage.GUIDED_DEMO),
                ("Import a Run Bundle", UiPage.BUNDLE_IMPORT),
            ],
            message=(
                "A comparison needs two existing run bundles. The guided demo creates "
                "a baseline and a stressed variation to compare, or import your own "
                "bundles and enter their paths above."
            ),
            key_prefix="compare_both_missing",
        )
        return
    if not baseline_path.exists():
        st.error(f"Baseline bundle path does not exist: {baseline_path}")
        st.info("Baseline is missing. Enter a valid baseline bundle path.")
        return
    if not variation_path.exists():
        st.error(f"Variation bundle path does not exist: {variation_path}")
        st.info("Variation is missing. Enter a valid variation bundle path.")
        return

    baseline = validate_bundle_for_ui(baseline_path)
    variation = validate_bundle_for_ui(variation_path)
    # Validate suitability for comparison — fail closed without mutating authoritative pair
    if isinstance(baseline, ServiceError) or not getattr(baseline, "analysis_ready", False):
        st.error("Baseline bundle is invalid and cannot be used for comparison.")
        if isinstance(baseline, ServiceError) and baseline.detail:
            st.caption(baseline.detail)
        elif not isinstance(baseline, ServiceError):
            with st.expander("Advanced: baseline validation report"):
                st.json(baseline.validation.report.model_dump(mode="json"))
        return
    if isinstance(variation, ServiceError) or not getattr(variation, "analysis_ready", False):
        st.error("Variation bundle is invalid and cannot be used for comparison.")
        if isinstance(variation, ServiceError) and variation.detail:
            st.caption(variation.detail)
        elif not isinstance(variation, ServiceError):
            with st.expander("Advanced: variation validation report"):
                st.json(variation.validation.report.model_dump(mode="json"))
        return
    report = compare_runs_for_ui(baseline, variation)
    if isinstance(report, ServiceError):
        st.error(report.message)
        if report.detail:
            st.caption(report.detail)
        return
    # Only after pair is successfully usable: atomically assign BOTH
    st.session_state["selected_baseline_run"] = str(baseline_path)
    st.session_state["selected_variation_run"] = str(variation_path)

    st.subheader("Compatibility")
    same_experiment = report.baseline_context.get("experiment_id") == report.variation_context.get(
        "experiment_id"
    )
    same_seed = report.baseline_context.get("random_seed") == report.variation_context.get(
        "random_seed"
    )
    with st.container(border=True):
        st.markdown(
            f"**Same experiment:** {'yes' if same_experiment else 'no'} · "
            f"**Same random seed:** {'yes' if same_seed else 'no'} · "
            f"**Metric version:** {report.baseline_context.get('metric_version')}"
        )
        st.markdown(
            f"**Baseline:** {_provenance_badge(report.baseline_context.get('synthetic'))} "
            f"**Variation:** {_provenance_badge(report.variation_context.get('synthetic'))}"
        )
        if report.warnings:
            st.warning("\n".join(report.warnings))
    with st.expander("Advanced: raw compatibility context JSON"):
        st.json(
            {
                "baseline_context": report.baseline_context,
                "variation_context": report.variation_context,
                "warnings": report.warnings,
            }
        )

    st.subheader("Changed scenario parameters")
    if report.changed_seed_parameters:
        change_rows = [
            {
                "path": change["path"],
                "baseline": str(change["baseline"]),
                "variation": str(change["variation"]),
            }
            for change in report.changed_seed_parameters
        ]
        st.dataframe(
            change_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(change_rows),
        )
    else:
        st.info("No seed snapshots or parameter changes available.")

    rows = comparison_rows(report)
    for title, prefix in [
        ("Task", "task."),
        ("Infrastructure", "infra."),
        ("Traffic", "traffic."),
        ("Trip", "trip."),
    ]:
        domain_rows = [row for row in rows if str(row["metric_key"]).startswith(prefix)]
        st.subheader(title)
        if domain_rows:
            st.dataframe(
                domain_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(domain_rows),
            )
        else:
            st.info(f"No {title.lower()} comparisons available.")

    _render_difference_provenance(baseline, variation, report)
    _render_comparison_completeness(baseline, variation)

    st.caption("Direction is neutral and does not imply improvement or causality.")


def _render_difference_provenance(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
    comparison: ComparisonReport,
) -> None:
    """Render the thin PRO-01 view over the deterministic library report."""

    st.subheader("Difference provenance")
    st.info(
        "Contributor lineage is not causal attribution. Arithmetic terms are shown only for "
        "admitted additive metrics."
    )
    metric_keys = [item.metric_key for item in comparison.comparable_metrics]
    if not metric_keys:
        st.info("No compatible scalar metric difference is available for contributor lineage.")
        return
    default_index = (
        metric_keys.index("task.completion.rate") if "task.completion.rate" in metric_keys else 0
    )
    metric_key = st.selectbox(
        "Difference provenance metric",
        metric_keys,
        index=default_index,
        key="difference_provenance_metric",
    )
    if not isinstance(metric_key, str):
        return
    result = difference_contributions_for_ui(baseline, variation, metric_key)
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            st.caption(result.detail)
        return
    with st.container(border=True):
        st.markdown(
            f"{badge_markdown(result.status.value)} **Comparison basis:** {result.comparison_basis}"
        )
        st.markdown(
            f"**Absolute delta:** {result.absolute_delta} · "
            f"**Arithmetic contribution sum:** {result.arithmetic_contribution_sum} · "
            f"**Reconciles:** {'yes' if result.reconciles_to_absolute_delta else 'no'}"
        )
        eligible_cols = st.columns(2)
        eligible_cols[0].metric(
            "Baseline eligible rows", result.baseline.included_row_count, border=True
        )
        eligible_cols[1].metric(
            "Variation eligible rows", result.variation.included_row_count, border=True
        )
    lineage_rows = [
        {
            "side": row.side.value,
            "source": f"{row.source_file}:{row.source_row}",
            "record_id": row.record_id,
            "included": row.included,
            "run_contribution": row.run_metric_contribution,
            "signed_difference_contribution": row.signed_difference_contribution,
            "reason": row.inclusion_reason,
        }
        for row in result.rows
    ]
    st.dataframe(
        lineage_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            lineage_rows,
            overrides={"record_id": ColumnDisplay(key="record_id", label="Record", hidden=False)},
        ),
    )
    st.caption(result.non_causality_statement)
    safe_key = metric_key.replace(".", "_")
    columns = st.columns(2)
    columns[0].download_button(
        "Download difference lineage JSON",
        data=result.to_json(),
        file_name=f"{safe_key}-difference-provenance.json",
        mime="application/json",
    )
    columns[1].download_button(
        "Download difference lineage CSV",
        data=difference_contribution_report_to_csv(result),
        file_name=f"{safe_key}-difference-provenance.csv",
        mime="text/csv",
    )


def _render_comparison_completeness(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
) -> None:
    """Render the PRO-03 denominator over the typed comparison-report claims."""

    st.subheader("Comparison provenance completeness")
    result = comparison_provenance_completeness_for_ui(baseline, variation)
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            st.caption(result.detail)
        return
    score = f"{result.score * 100:.1f}%" if result.score is not None else "N/A"
    columns = st.columns(4)
    columns[0].metric("Source-row score", score)
    columns[1].metric("Source-row complete", result.source_row_complete_count)
    columns[2].metric("Aggregate only", result.aggregate_only_count)
    columns[3].metric("Unavailable", result.unavailable_count)
    claim_rows = [
        {
            "metric_key": claim.artifact_key,
            "status": claim.artifact_status,
            "classification": claim.classification.value,
            "candidate_rows": claim.candidate_source_row_count,
            "reasons": "; ".join(claim.reason_codes),
        }
        for claim in result.claims
    ]
    st.dataframe(
        claim_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(claim_rows),
    )
    st.caption(result.denominator_definition)
    downloads = st.columns(2)
    downloads[0].download_button(
        "Download comparison completeness JSON",
        data=result.to_json(),
        file_name=f"{result.report_id}-provenance-completeness.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Download comparison completeness CSV",
        data=provenance_completeness_report_to_csv(result),
        file_name=f"{result.report_id}-provenance-completeness.csv",
        mime="text/csv",
    )
