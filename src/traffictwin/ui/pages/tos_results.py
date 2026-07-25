"""TOS evaluation matrix, paired comparison, and generalisation page."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    TosPackageView,
    TosResultsView,
    compare_tos_campaigns_for_ui,
    tos_results_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tos_context import active_tos_package


def render(config: UiConfig) -> None:
    """Render descriptive imported-simulation result exploration."""

    render_page_header(UiPage.TOS_RESULTS)
    badge_row(["IMPORTED SIMULATION", "READ ONLY", "PAIRED FLEET SEEDS"])
    st.info(
        "The explorer reports source-defined deadline success, latency, energy, and decision "
        "shares. It does not establish real-world validation or causal conclusions."
    )
    package = active_tos_package(config)
    if package is None:
        return
    measures = tos_results_for_ui(package)
    if isinstance(measures, ServiceError):
        st.error(measures.message)
        return
    labels = {definition.human_name: definition.key for definition in measures.measures}
    controls = st.columns(2)
    preferred_fleet = measures.fleets.index("uk2030") if "uk2030" in measures.fleets else 0
    fleet = controls[0].selectbox(
        "Evaluation fleet",
        measures.fleets,
        index=preferred_fleet,
        key="tos_results_fleet",
    )
    label = controls[1].selectbox("Source measure", list(labels), key="tos_results_measure")
    result = tos_results_for_ui(package, measure_key=labels[label], evaluation_fleet=fleet)
    if isinstance(result, ServiceError):
        st.error(result.message)
        return
    matrix = result.matrix
    st.subheader("Evaluation matrix")
    z = []
    text = []
    by_key = {(entry.campaign, entry.cell): entry for entry in matrix.entries}
    for campaign in matrix.campaigns:
        row_values: list[float | None] = []
        row_text: list[str] = []
        for cell in matrix.cells:
            entry = by_key.get((campaign, cell))
            value = entry.statistics.mean if entry else None
            row_values.append(value)
            row_text.append(
                "Unavailable"
                if entry is None
                else f"mean={_number(value)}<br>n={entry.statistics.n}"
            )
        z.append(row_values)
        text.append(row_text)
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=matrix.cells,
            y=matrix.campaigns,
            text=text,
            hovertemplate="%{y} / %{x}<br>%{text}<extra></extra>",
            colorbar_title=matrix.measure.unit,
            colorscale="Viridis",
        )
    )
    figure.update_layout(
        xaxis_title="Manchester source scenario cell",
        yaxis_title="Campaign",
        height=max(420, 36 * len(matrix.campaigns)),
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    st.plotly_chart(figure, width="stretch")
    st.caption("Each cell is the arithmetic mean across available fleet seeds. Hover shows n.")
    with st.expander("Measure definition and limitations"):
        st.write(matrix.measure.description)
        st.code(matrix.measure.key)
        for limitation in matrix.measure.limitations:
            st.warning(limitation)

    _render_comparison(package, result.campaigns, fleet, matrix.measure.key)
    _render_generalisation(result)


def _render_comparison(package: TosPackageView, campaigns: list[str], fleet: str, key: str) -> None:
    st.subheader("Paired campaign comparison")
    if "baseline" not in campaigns or len(campaigns) < 2:
        st.info("A baseline and at least one variation campaign are required.")
        return
    options = [campaign for campaign in campaigns if campaign != "baseline"]
    columns = st.columns(2)
    baseline = columns[0].selectbox("Baseline campaign", ["baseline"], disabled=True)
    variation = columns[1].selectbox("Variation campaign", options)
    comparison = compare_tos_campaigns_for_ui(
        package,
        baseline,
        variation,
        measure_key=key,
        evaluation_fleet=fleet,
    )
    if isinstance(comparison, ServiceError):
        st.error(comparison.message)
        if comparison.detail:
            st.caption(comparison.detail)
        return
    rows = [
        {
            "cell": item.cell,
            "paired n": item.paired_difference_statistics.n,
            "baseline mean": item.baseline_statistics.mean,
            "variation mean": item.variation_statistics.mean,
            "mean delta": item.paired_difference_statistics.mean,
            "sample SD of deltas": item.paired_difference_statistics.sample_sd,
            "compatibility": "; ".join(item.compatibility_findings) or "compatible",
        }
        for item in comparison.comparisons
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    delta_figure = go.Figure(
        go.Bar(
            x=[item.cell for item in comparison.comparisons],
            y=[item.paired_difference_statistics.mean for item in comparison.comparisons],
            customdata=[item.paired_difference_statistics.n for item in comparison.comparisons],
            hovertemplate="%{x}<br>mean delta=%{y:.6f}<br>paired n=%{customdata}<extra></extra>",
        )
    )
    delta_figure.add_hline(y=0, line_width=1, line_color="#68726d")
    delta_figure.update_layout(
        xaxis_title="Scenario cell",
        yaxis_title=f"Variation - baseline ({comparison.comparisons[0].measure.unit})",
        height=340,
        showlegend=False,
    )
    st.plotly_chart(delta_figure, width="stretch")
    st.caption(
        "Pairing uses common fleet_seed values within the same cell and fleet. Direction is "
        "descriptive; it is not labelled as a causal improvement or degradation."
    )


def _render_generalisation(result: TosResultsView) -> None:
    st.subheader("Training/evaluation domain matrix")
    generalisation = result.generalisation
    st.dataframe(
        [
            {
                "campaign": entry.campaign,
                "cell": entry.cell,
                "domain": entry.evaluation_domain.value,
                "evidence": entry.evidence_statement,
                "source": entry.evidence_file or "unavailable",
            }
            for entry in generalisation.entries
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "UNKNOWN is retained when the package does not explicitly establish whether a cell is "
        "in-domain or held out. The label does not assess performance quality."
    )


def _number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6f}"
