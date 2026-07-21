"""What-if comparison page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.metrics.comparison import ComparisonReport
from traffictwin.provenance.completeness import provenance_completeness_report_to_csv
from traffictwin.provenance.differences import difference_contribution_report_to_csv
from traffictwin.ui.services import (
    BundleAnalysis,
    ServiceError,
    compare_runs_for_ui,
    comparison_provenance_completeness_for_ui,
    difference_contributions_for_ui,
    validate_bundle_for_ui,
)
from traffictwin.ui.tables import comparison_rows


def render() -> None:
    """Render comparison page."""

    st.title("What-if Compare")
    baseline_path = Path(
        st.text_input(
            "Baseline bundle path",
            value=str(
                st.session_state.get(
                    "selected_baseline_run", "tests/fixtures/bundles/baseline_valid"
                )
            ),
        )
    )
    variation_path = Path(
        st.text_input(
            "Variation bundle path",
            value=str(
                st.session_state.get(
                    "selected_variation_run", "tests/fixtures/bundles/variation_valid"
                )
            ),
        )
    )
    st.session_state["selected_baseline_run"] = str(baseline_path)
    st.session_state["selected_variation_run"] = str(variation_path)

    if not baseline_path.exists() or not variation_path.exists():
        st.error("Both baseline and variation bundle paths must exist.")
        return

    baseline = validate_bundle_for_ui(baseline_path)
    variation = validate_bundle_for_ui(variation_path)
    report = compare_runs_for_ui(baseline, variation)
    if isinstance(report, ServiceError):
        st.error(report.message)
        return

    st.subheader("Compatibility")
    st.json(
        {
            "same_experiment": report.baseline_context.get("experiment_id")
            == report.variation_context.get("experiment_id"),
            "same_random_seed": report.baseline_context.get("random_seed")
            == report.variation_context.get("random_seed"),
            "metric_version": report.baseline_context.get("metric_version"),
            "synthetic_flags": {
                "baseline": report.baseline_context.get("synthetic"),
                "variation": report.variation_context.get("synthetic"),
            },
            "warnings": report.warnings,
        }
    )

    st.subheader("Changed Scenario Parameters")
    if report.changed_seed_parameters:
        st.table(
            [
                {
                    "path": change["path"],
                    "baseline": str(change["baseline"]),
                    "variation": str(change["variation"]),
                }
                for change in report.changed_seed_parameters
            ],
            hide_index=True,
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
            st.table(domain_rows, hide_index=True)
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
    st.write(
        {
            "status": result.status.value,
            "comparison_basis": result.comparison_basis,
            "absolute_delta": result.absolute_delta,
            "arithmetic_contribution_sum": result.arithmetic_contribution_sum,
            "reconciles": result.reconciles_to_absolute_delta,
            "baseline_eligible_rows": result.baseline.included_row_count,
            "variation_eligible_rows": result.variation.included_row_count,
        }
    )
    st.dataframe(
        [
            {
                "side": row.side.value,
                "source": f"{row.source_file}:{row.source_row}",
                "record_id": row.record_id,
                "included": row.included,
                "run contribution": row.run_metric_contribution,
                "signed difference contribution": row.signed_difference_contribution,
                "reason": row.inclusion_reason,
            }
            for row in result.rows
        ],
        hide_index=True,
        width="stretch",
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
    st.table(
        [
            {
                "metric": claim.artifact_key,
                "status": claim.artifact_status,
                "classification": claim.classification.value,
                "candidate rows": claim.candidate_source_row_count,
                "reasons": "; ".join(claim.reason_codes),
            }
            for claim in result.claims
        ],
        hide_index=True,
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
