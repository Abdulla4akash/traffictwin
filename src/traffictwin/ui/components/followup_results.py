"""Presentation of the completed September 15 experiment summaries."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from traffictwin.integration.dissertation_results import ResultsImportError
from traffictwin.integration.followup_results import (
    ARM_LABELS,
    STUDY_LABELS,
    FollowupCell,
    FollowupResults,
    load_followup_results,
)

CONTRAST_LABELS = {
    "per_task_minus_two_choice": "Per-task − two-choice",
    "two_choice_minus_ingress": "Two-choice − ingress",
    "two_choice_minus_round_robin": "Two-choice − round-robin",
    "per_task_dla_minus_ingress_dla": "Per-task − ingress",
    "dla_minus_ingress_dla": "Common-target − ingress",
    "per_task_dla_minus_causal_round_robin": "Per-task − round-robin",
    "change_in_per_task_minus_round_robin_gap": "Change in per-task / round-robin gap",
}
DESCRIPTIONS = {
    "07_two_choice": (
        "Two-choice placement compared with ingress, per-task and round-robin. "
        "8 new two-choice runs use 24 reused historical comparator runs."
    ),
    "08_half_speed": (
        "RSU service rate halved at unchanged offered demand: 32 new runs across four policies. "
        "The gap-change comparison additionally uses 16 original-speed reference runs."
    ),
    "09_second_actor": (
        "A second frozen actor, trained on a UK fleet distribution: "
        "32 new runs across four policies at normal server speed."
    ),
}
LIMITATIONS = {
    "07_two_choice": (
        "Two-choice samples with replacement from the substep backlog snapshot. "
        "Per-task placement sees earlier reservations, so this comparison also changes "
        "reservation visibility."
    ),
    "08_half_speed": (
        "This tests one reduction in modeled RSU processing capacity at fixed demand. "
        "It does not establish a general load-response curve."
    ),
    "09_second_actor": (
        "The two checkpoints share training seed 100. This adds checkpoint sensitivity "
        "coverage, not independent training-seed replication."
    ),
}


def render_followup_results() -> None:
    """Render only verified summaries, keeping historical studies distinct."""
    st.caption("Workflow demonstration · completed simulation evidence · 15 September 2026")
    try:
        results = load_followup_results()
    except ResultsImportError as exc:
        st.error(f"Evidence display refused: {exc}")
        return

    cols = st.columns(4)
    for col, label, value in zip(
        cols,
        (
            "New completed runs",
            "Reused historical controls",
            "Paired blocks per study",
            "Follow-ups",
        ),
        (72, 32, 8, 3),
        strict=True,
    ):
        col.metric(label, value)
    st.caption(
        "The three follow-ups use the same eight previously examined fleet/evaluator seed pairs. "
        "The 32 historical controls are counted once in the totals above."
    )
    study = st.selectbox(
        "Experiment",
        options=list(STUDY_LABELS),
        format_func=STUDY_LABELS.__getitem__,
        key="followup_experiment",
    )
    st.subheader(STUDY_LABELS[study])
    st.write(DESCRIPTIONS[study])
    paired, runs, evidence = st.tabs(
        ["Paired comparisons", "Runs & blocks", "Evidence & downloads"]
    )
    with paired:
        _render_comparisons(results, study)
    with runs:
        _render_runs(results, study)
    with evidence:
        _render_evidence(results)
    st.caption(LIMITATIONS[study])
    st.caption(
        "These follow-ups remain separate from the original confirmation family. "
        "Results are conditional on the selected morning trace and simulator. "
        "An interval crossing zero is inconclusive, not evidence of equivalence."
    )


def _render_comparisons(results: FollowupResults, study: str) -> None:
    st.markdown("**Change in deadline attainment**")
    st.caption(
        "Successes ÷ all offered tasks, including rejected tasks. Each paired block has equal "
        "weight; individual tasks are not statistical replicates."
    )
    contrasts = [item for item in results.contrasts if item.study == study]
    figure = go.Figure()
    for item in contrasts:
        figure.add_trace(
            go.Scatter(
                x=[item.mean_pp],
                y=[CONTRAST_LABELS[item.name]],
                mode="markers+text",
                text=[f"{item.mean_pp:+.3f} pp"],
                textposition="top center",
                cliponaxis=False,
                marker={"size": 13, "color": "#0891b2"},
                error_x={
                    "type": "data",
                    "symmetric": False,
                    "array": [item.high_pp - item.mean_pp],
                    "arrayminus": [item.mean_pp - item.low_pp],
                    "thickness": 2,
                    "width": 7,
                },
                hovertemplate="%{y}<br>Mean: %{x:+.3f} pp<extra></extra>",
            )
        )
    figure.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
    figure.update_layout(
        height=120 + 65 * len(contrasts),
        margin={"l": 0, "r": 35, "t": 30, "b": 0},
        showlegend=False,
        xaxis_title="Difference in percentage points (pp)",
        yaxis={"autorange": "reversed", "automargin": True},
    )
    st.plotly_chart(figure, width="stretch", key="followup_paired_effects")
    st.dataframe(
        [
            {
                "Comparison": CONTRAST_LABELS[item.name],
                "Mean difference (pp)": f"{item.mean_pp:+.3f}",
                "All-ten simultaneous 95% interval (pp)": (
                    f"[{item.low_pp:+.3f}, {item.high_pp:+.3f}]"
                ),
                "Paired blocks": len(item.effects_pp),
            }
            for item in contrasts
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Original saved Bonferroni simultaneous 95% t intervals across all ten follow-up "
        "comparisons; 7 degrees of freedom. Approximate normality of block differences assumed. "
        "Selecting an experiment does not change the interval family or sample size."
    )
    if study == "08_half_speed":
        st.info(
            "Gap change = (per-task − round-robin) at half speed "
            "minus (per-task − round-robin) at original speed, paired within each block. "
            "This is a change in the policy gap, not another policy."
        )


def _cell_rows(cells: tuple[FollowupCell, ...]) -> list[dict[str, str | int | float]]:
    return [
        {
            "Block": cell.block,
            "Policy": ARM_LABELS[cell.arm],
            "Run source": "Reused original-speed control"
            if cell.reused_reference
            else "New follow-up",
            "Fleet seed": cell.fleet_seed,
            "Evaluator seed": cell.evaluator_seed,
            "Offered": cell.offered,
            "Admitted": cell.admitted,
            "Deadline successes": cell.successes,
            "Attainment (%)": cell.attainment_pct,
        }
        for cell in sorted(cells, key=lambda c: (c.block, c.arm))
    ]


def _render_runs(results: FollowupResults, study: str) -> None:
    cells = results.cells_for(study)
    st.markdown("**Deadline attainment across the eight paired blocks**")
    figure = go.Figure()
    for condition, arm in sorted({(cell.study, cell.arm) for cell in cells}):
        series = sorted(
            (c for c in cells if (c.study, c.arm) == (condition, arm)), key=lambda c: c.block
        )
        label = ARM_LABELS[arm] + (" (reused)" if condition == "baseline" else "")
        figure.add_trace(
            go.Scatter(
                x=[c.block for c in series],
                y=[c.attainment_pct for c in series],
                name=label,
                mode="lines+markers",
                hovertemplate="Block %{x}<br>Attainment: %{y:.3f}%<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(
        height=350,
        margin={"l": 0, "r": 15, "t": 35, "b": 0},
        xaxis={"title": "Paired block", "dtick": 1},
        yaxis_title="Deadline successes / offered tasks (%)",
        legend={"orientation": "h", "y": 1.15},
    )
    st.plotly_chart(figure, width="stretch", key="followup_block_rates")
    st.dataframe(
        [
            {
                "Policy": ARM_LABELS[arm],
                "Run source": "Reused control" if condition == "baseline" else "New follow-up",
                "Mean attainment (%)": results.means[condition, arm],
                "Paired blocks": 8,
            }
            for condition, arm in sorted({(cell.study, cell.arm) for cell in cells})
        ],
        hide_index=True,
        width="stretch",
        column_config={"Mean attainment (%)": st.column_config.NumberColumn(format="%.3f")},
    )
    block = st.selectbox("Inspect block", ["All blocks", *map(str, range(8))], key="followup_block")
    selected = tuple(c for c in cells if block == "All blocks" or str(c.block) == block)
    st.dataframe(
        _cell_rows(selected),
        hide_index=True,
        width="stretch",
        column_config={"Attainment (%)": st.column_config.NumberColumn(format="%.3f")},
    )
    st.caption("Block filtering changes this table only; the saved comparisons remain unchanged.")
    if study == "08_half_speed":
        with st.expander("Reused original-speed controls for the gap-change comparison"):
            st.dataframe(
                _cell_rows(results.gap_reference_cells()), hide_index=True, width="stretch"
            )
    st.caption(
        "This compact study provides offered, admitted and deadline-success counts. "
        "Queue lengths and additional task-lifecycle stages are not supplied in this display."
    )


def _render_evidence(results: FollowupResults) -> None:
    st.success(
        "Original compact files match their packaged fingerprints and historical audit bindings."
    )
    st.caption(
        "The display checks summary arithmetic and the recorded analysis audit. "
        "Raw simulation arrays are not rechecked, and no experiments are launched. "
        "Downloads contain the full three-study packet, including all 104 new and reused rows."
    )
    st.download_button(
        "Download follow-up evidence ZIP",
        data=results.packet,
        file_name="traffictwin-followups-2026-09-15.zip",
        mime="application/zip",
    )
    cols = st.columns(3)
    for col, name in zip(
        cols, ("CELL_RESULTS.csv", "PAIRED_EFFECTS.csv", "RESULTS.md"), strict=True
    ):
        col.download_button(
            f"Download {name}",
            data=results.files[name],
            file_name=name,
            mime="text/markdown" if name.endswith(".md") else "text/csv",
        )
    with st.expander("File fingerprints and source identity"):
        st.code(
            f"Archived in repository: {results.repository_commit}\n"
            f"Executed experiment source: {results.execution_source_commit}"
        )
        st.dataframe(
            [{"File": name, "SHA-256": digest} for name, digest in results.hashes.items()],
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Download original analysis audit",
            data=results.files["evidence/FINAL_ANALYSIS_AUDIT.json"],
            file_name="FINAL_ANALYSIS_AUDIT.json",
            mime="application/json",
        )
