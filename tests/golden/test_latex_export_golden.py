from __future__ import annotations

from pathlib import Path

from traffictwin.reporting.latex import (
    ResearchExportKind,
    ResearchExportProjection,
    ResearchFigureEntry,
    projection_to_latex_fragment,
    projection_to_svg,
)

EXPECTED = Path("tests/golden/expected")


def test_latex_table_and_svg_match_exact_golden_fragments() -> None:
    projection = ResearchExportProjection(
        kind=ResearchExportKind.METRICS,
        source_id="run-golden",
        title="TrafficTwin Metric Results",
        caption="Deterministic metric results for run-golden.",
        columns=["Metric", "Status", "Value", "Unit"],
        rows=[
            ["task.completion.rate", "available", "0.875", "ratio"],
            ["task.latency.p95_ms", "available", "125.5", "ms"],
            ["plugin.a&b_1", "unavailable", "unavailable", "count"],
        ],
        figure_entries=[
            ResearchFigureEntry(label="task.completion.rate", numeric_value=0.875),
            ResearchFigureEntry(label="task.latency.p95_ms", numeric_value=125.5),
        ],
        synthetic=True,
        warnings=["Synthetic evidence; not real-world validation"],
    )

    assert projection_to_latex_fragment(projection) == (
        EXPECTED / "latex_metric_fragment.tex"
    ).read_text(encoding="utf-8")
    assert projection_to_svg(projection) == (EXPECTED / "latex_metric_figure.svg").read_text(
        encoding="utf-8"
    )
