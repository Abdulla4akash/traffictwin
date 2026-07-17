"""What-if comparison page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.services import ServiceError, compare_runs_for_ui, validate_bundle_for_ui
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
        st.dataframe(
            [
                {
                    "path": change["path"],
                    "baseline": str(change["baseline"]),
                    "variation": str(change["variation"]),
                }
                for change in report.changed_seed_parameters
            ],
            width="stretch",
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
            st.dataframe(domain_rows, width="stretch", hide_index=True)
        else:
            st.info(f"No {title.lower()} comparisons available.")

    st.caption("Direction is neutral and does not imply improvement or causality.")
