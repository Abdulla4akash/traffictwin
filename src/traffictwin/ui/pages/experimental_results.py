"""Display imported, authenticated dissertation results without launching experiments."""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from traffictwin.integration.dissertation_results import (
    DissertationResults,
    ResultsImportError,
    load_builtin_results,
    load_results_directory,
    load_results_zip,
)

ARM_LABELS = {
    "ingress_dla": "Ingress",
    "dla": "Common-target",
    "per_task_dla": "Per-task",
    "causal_round_robin": "Round-robin",
}
ARM_COLORS = {
    "ingress_dla": "#64748b",
    "dla": "#d97706",
    "per_task_dla": "#0891b2",
    "causal_round_robin": "#8b5cf6",
}


def _contrast_label(contrast: str) -> str:
    treated, control = contrast.split(" minus ")
    return f"{ARM_LABELS[treated]} − {ARM_LABELS[control]}"


def render() -> None:
    """Load and present one original study; invalid imports never retain old results."""

    st.title("Experimental Results")
    st.caption("Workflow demonstration · completed simulation evidence · 8 September 2026")
    with st.expander("Import study evidence", expanded=False):
        source = st.radio(
            "Evidence source",
            ("Dissertation study", "Upload evidence ZIP", "Local evidence folder"),
            horizontal=True,
        )
        st.caption(
            "Supports the frozen joint-confirmation study: CELL_RESULTS.csv, "
            "PAIRED_EFFECTS.csv, the analysis, protocol seal and validation receipts. "
            "Use the downloadable evidence ZIP to move the study between computers."
        )
        uploaded = None
        folder = ""
        if source == "Upload evidence ZIP":
            uploaded = st.file_uploader("Study evidence ZIP", type=["zip"])
        elif source == "Local evidence folder":
            folder = st.text_input(
                "Study package folder",
                placeholder="Folder containing evidence/ and confirmation/",
            )
    try:
        if source == "Upload evidence ZIP":
            if uploaded is None:
                st.info("Choose the study evidence ZIP to display its results.")
                return
            results = load_results_zip(uploaded.getvalue())
        elif source == "Local evidence folder":
            if not folder.strip():
                st.info("Enter the study package folder to display its results.")
                return
            results = load_results_directory(Path(folder).expanduser())
        else:
            results = load_builtin_results()
    except (ResultsImportError, OSError) as exc:
        st.error(f"Evidence import refused: {exc}")
        return

    st.subheader("Joint-randomness confirmation")
    st.caption(
        "Morning trace · frozen vehicle actor · four infrastructure scheduling policies · "
        "fleet and evaluator seeds vary together across eight paired blocks"
    )
    cols = st.columns(4)
    cols[0].metric("Paired blocks", len({cell.block for cell in results.cells}))
    cols[1].metric("Completed runs", len(results.cells))
    cols[2].metric("Policies", len({cell.arm for cell in results.cells}))
    cols[3].metric("Cell receipts matched", len(results.receipt_summary))
    st.success(
        "Original study files match their recorded hashes. "
        "Compact result arithmetic and receipt bindings checked."
    )
    st.caption(
        "Task-level validation is recorded in the historical receipts; "
        "raw simulation arrays are not rechecked by this view."
    )

    paired, runs, evidence = st.tabs(
        ["Paired comparisons", "Runs & blocks", "Evidence & downloads"]
    )
    with paired:
        _render_paired(results)
    with runs:
        _render_runs(results)
    with evidence:
        _render_evidence(results)


def _render_paired(results: DissertationResults) -> None:
    st.markdown("**Change in deadline attainment**")
    st.caption(
        "Successes ÷ all offered tasks. Each paired block has equal weight; "
        "individual tasks are not statistical replicates."
    )
    figure = go.Figure()
    for contrast in results.primary:
        label = _contrast_label(contrast.contrast)
        figure.add_trace(
            go.Scatter(
                x=[contrast.mean_pp],
                y=[label],
                mode="markers+text",
                text=[f"{contrast.mean_pp:+.3f} pp"],
                textposition="top center",
                cliponaxis=False,
                marker={"size": 13, "color": "#0891b2"},
                error_x={
                    "type": "data",
                    "symmetric": False,
                    "array": [contrast.family95_high_pp - contrast.mean_pp],
                    "arrayminus": [contrast.mean_pp - contrast.family95_low_pp],
                    "thickness": 2,
                    "width": 7,
                },
                name=label,
                hovertemplate=f"{label}<br>Mean: %{{x:+.3f}} pp<extra></extra>",
            )
        )
    figure.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
    figure.update_layout(
        height=270,
        margin={"l": 0, "r": 20, "t": 15, "b": 0},
        showlegend=False,
        xaxis_title="Difference in percentage points (pp)",
        yaxis={"autorange": "reversed"},
    )
    st.plotly_chart(figure, width="stretch", key="dissertation_paired_effects")
    st.dataframe(
        [
            {
                "Comparison": _contrast_label(contrast.contrast),
                "Mean difference (pp)": f"{contrast.mean_pp:+.3f}",
                "Simultaneous 95% interval (pp)": (
                    f"[{contrast.family95_low_pp:+.3f}, {contrast.family95_high_pp:+.3f}]"
                ),
                "Paired blocks": len(contrast.effects_pp),
            }
            for contrast in results.primary
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Original three-contrast family: Bonferroni simultaneous 95% t intervals, "
        "7 degrees of freedom; approximate normality of block differences assumed. "
        "This study is separate from prior experiments; results are not pooled."
    )


def _render_runs(results: DissertationResults) -> None:
    st.markdown("**Deadline attainment across the eight paired blocks**")
    figure = go.Figure()
    for arm, label in ARM_LABELS.items():
        rows = sorted((cell for cell in results.cells if cell.arm == arm), key=lambda c: c.block)
        figure.add_trace(
            go.Scatter(
                x=[cell.block for cell in rows],
                y=[cell.attainment_pct for cell in rows],
                name=label,
                mode="lines+markers",
                line={"color": ARM_COLORS[arm]},
                hovertemplate="Block %{x}<br>Attainment: %{y:.3f}%<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(
        height=330,
        margin={"l": 0, "r": 10, "t": 10, "b": 0},
        xaxis={"title": "Paired block", "dtick": 1},
        yaxis_title="Deadline successes / offered tasks (%)",
        legend={"orientation": "h", "y": 1.15},
    )
    st.plotly_chart(figure, width="stretch", key="dissertation_block_rates")
    block = st.selectbox("Inspect block", ["All blocks", *[str(b) for b in range(8)]])
    selected = [c for c in results.cells if block == "All blocks" or str(c.block) == block]
    st.dataframe(
        [
            {
                "Block": cell.block,
                "Policy": ARM_LABELS[cell.arm],
                "Fleet seed": cell.fleet_seed,
                "Evaluator seed": cell.evaluator_seed,
                "Offered": cell.offered,
                "Admitted": cell.admitted,
                "Deadline successes": cell.successes,
                "Attainment (%)": cell.attainment_pct,
                "Gate rejected": cell.gate_rejected,
                "Admitted misses": cell.admitted_misses,
                "Terminal failures": cell.terminal_failures,
            }
            for cell in selected
        ],
        hide_index=True,
        width="stretch",
        column_config={"Attainment (%)": st.column_config.NumberColumn(format="%.3f")},
    )
    st.caption(
        "Filtering this table does not change the sealed eight-block analysis. "
        "Offered = admitted + terminal failures; admitted = successes + admitted misses. "
        "Gate rejection is one terminal category. All categories remain in CELL_RESULTS.csv."
    )


def _render_evidence(results: DissertationResults) -> None:
    st.markdown("**Evidence chain**")
    st.write(
        "Sealed protocol → 32 cell receipts and summaries → eight block-control receipts "
        "→ cell counts → paired effects and the original analysis."
    )
    st.caption(
        "File matching establishes identity with the archived study. It does not independently "
        "validate the simulator or establish that the findings transfer to other traces or actors."
    )
    st.download_button(
        "Download study evidence ZIP",
        data=results.export_zip(),
        file_name="traffictwin-joint-confirmation-evidence.zip",
        mime="application/zip",
        key="dissertation_packet_download",
    )
    cols = st.columns(3)
    for column, name in zip(cols[:2], ("CELL_RESULTS.csv", "PAIRED_EFFECTS.csv"), strict=True):
        column.download_button(
            f"Download {name}",
            data=results.files[f"evidence/{name}"],
            file_name=name,
            mime="text/csv",
        )
    cols[2].download_button(
        "Download import check receipt",
        data=json.dumps(results.validation_receipt(), indent=2),
        file_name="TRAFFICTWIN_IMPORT_CHECK.json",
        mime="application/json",
    )
    with st.expander("Cell validation receipts"):
        st.dataframe(results.receipt_summary, hide_index=True, width="stretch")
        names = sorted(name for name in results.files if name.endswith("/VALIDATED.json"))
        chosen = st.selectbox("Original cell receipt", names)
        st.download_button(
            "Download selected receipt",
            data=results.files[chosen],
            file_name=chosen.replace("/", "_"),
            mime="application/json",
        )
        st.json(json.loads(results.files[chosen]), expanded=False)
    with st.expander("File hashes and protocol seal"):
        st.caption("SHA-256 fingerprints of the exact imported bytes")
        st.code(f"Protocol seal: {results.seal_sha256}\nEvidence ZIP: {results.packet_sha256}")
        st.dataframe(
            [{"File": name, "SHA-256": digest} for name, digest in results.hashes.items()],
            hide_index=True,
            width="stretch",
        )
