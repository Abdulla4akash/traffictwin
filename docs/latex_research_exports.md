# LaTeX Research Tables And Static Figures

TrafficTwin REP-01 turns already-computed typed artifacts into publication-oriented LaTeX table
fragments and optional SVG or PDF figures. The exporter is deterministic template code. It does
not calculate metrics, re-run statistics, reinterpret diagnostic results, or use an LLM.

## Supported Use Cases

| Artifact | Table contents | Figure contents |
|---|---|---|
| `MetricCollection` | metric key, availability, value, and unit | available finite scalar metrics |
| `ComparisonReport` | baseline, variation, delta, status, and unit | available finite deltas |
| `StatisticalStudy` | predeclared estimates, intervals, tests, effects, and audit values | finite study estimates already stored in the artifact |
| `DiagnosticReport` | rule title, exact status/confidence, and evidence counts | categorical rule statuses |

Rule figures are categorical summaries. They never convert confidence or status to probability.
Numeric bars use a signed linear scale; bar direction does not mean that an outcome is favourable.

## Initialise A Standalone Workspace

From the repository root:

```bash
uv sync --extra dev
uv run traffictwin demo initialise --workspace .demo
```

The examples below use the labelled synthetic demo bundles. Replace them with a validated imported
bundle when exporting imported evidence.

## CLI Usage

Inspect the versioned contract:

```bash
uv run traffictwin report latex-contract
```

Export a metric table and SVG figure:

```bash
uv run traffictwin report latex-metrics .demo/bundles/baseline \
  --output .demo/exports/baseline-metrics.tex \
  --figure .demo/exports/baseline-metrics.svg
```

Export a comparison table and PDF figure:

```bash
uv run traffictwin report latex-comparison \
  .demo/bundles/baseline .demo/bundles/stressed_demand \
  --output .demo/exports/comparison.tex \
  --figure .demo/exports/comparison.pdf
```

Export an existing STA-01 statistical-study artifact:

```bash
uv run traffictwin report latex-study statistical_study.json \
  --output .demo/exports/statistical-study.tex \
  --figure .demo/exports/statistical-study.svg
```

Export deterministic diagnostic rule results:

```bash
uv run traffictwin report latex-rules .demo/bundles/under_offloading \
  --output .demo/exports/rules.tex \
  --figure .demo/exports/rules.pdf
```

Existing output files are refused by default. Add `--overwrite` only after checking the exact
paths. The table path must end in `.tex`; the optional figure must end in `.svg` or `.pdf`.

Every successful command prints a projection fingerprint plus each output filename, format,
SHA-256 checksum, and byte size. The receipt uses filenames rather than absolute paths.

## Compile A Fragment

The table fragment uses only ordinary LaTeX2e `table`, `tabular`, and `hline` constructs. A minimal
document is:

```tex
\documentclass{article}
\begin{document}
\input{.demo/exports/baseline-metrics.tex}
\end{document}
```

Compile it with an installed LaTeX engine, for example:

```bash
tectonic document.tex
```

The output is a fragment rather than a complete dissertation template, so the researcher retains
control of document class, typography, placement, and surrounding interpretation. Inspect the
compiled table and any PDF figure visually before submission.

## Streamlit Usage

Start the UI:

```bash
TRAFFICTWIN_WORKSPACE=.demo uv run streamlit run src/traffictwin/ui/app.py
```

Open **Reports**, then use **LaTeX research export**:

1. select Metrics, Comparison, Statistical study, or Diagnostic rules;
2. enter the validated bundle or saved study path;
3. for Comparison, enter the second bundle;
4. choose the exact `.tex` destination and optional SVG/PDF destination;
5. enable overwrite only when replacing those exact files; and
6. select **Generate research export**.

The UI delegates to the same typed library and shows the same projection fingerprint and file
receipt as the CLI.

## Python API

```python
from pathlib import Path

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.reporting.latex import (
    project_metric_collection,
    write_projection_exports,
)

validation = validate_bundle(Path(".demo/bundles/baseline"))
metrics = compute_metrics_for_bundle(validation)
projection = project_metric_collection(metrics)
receipt = write_projection_exports(
    projection,
    Path(".demo/exports/metrics.tex"),
    figure_path=Path(".demo/exports/metrics.svg"),
)
print(receipt.projection_fingerprint)
```

The other projection functions are `project_comparison_report`, `project_statistical_study`, and
`project_diagnostic_report`. Rendering functions are available separately for in-memory use:
`projection_to_latex_fragment`, `projection_to_svg`, and `projection_to_pdf`.

## Reproducibility Contract

The table and optional figure are rendered from one validated `ResearchExportProjection`:

- the projection has a canonical SHA-256 fingerprint;
- both outputs embed the first 12 characters of that fingerprint;
- table rows and figure entries are deterministically ordered by their typed projector;
- diagnostic exports identify stable evidence rather than the clock-derived report ID;
- SVG has fixed geometry and no scripts, links, fonts, or remote assets;
- PDF uses invariant ReportLab metadata and fixed geometry; and
- exact golden fragments and a real minimal-document compile test protect the renderers.

Repeated rendering of the same projection produces identical text or bytes. Different source
artifacts, values, warnings, or source modes intentionally produce a different fingerprint.

## Bounds And Safety

Version 1.0 applies the following hard bounds:

- 200 table rows;
- 8 table columns;
- 160 characters per cell; and
- 64 figure entries.

When a typed artifact exceeds a renderer bound, the projection records a visible truncation
warning. LaTeX-special characters are escaped. Absolute POSIX and Windows filesystem paths in
rendered content are replaced with basename-only local-path markers, while normal web URLs are
preserved. Outputs are staged as sibling temporary files and atomically replace only their exact
targets. Symbolic-link targets are refused.

The exporter does not embed raw CSV rows, remote resources, JavaScript, shell commands, or local
absolute paths. It preserves the input artifact and writes only the requested exports.

## Source And Interpretation Labels

Every table and figure states one source mode:

- `synthetic` for labelled synthetic artifacts;
- `imported or non-synthetic` when the source declares non-synthetic evidence; or
- `unresolved` when the typed source cannot establish either state.

These labels do not establish external validity. A deterministic export can still contain
synthetic, provisional, unavailable, or insufficient evidence. Availability, warnings, units,
method names, and exact rule statuses remain visible rather than being converted to a positive
claim.

## Limitations

- REP-01 is a renderer, not a spreadsheet, statistical engine, or scientific plotting package.
- Figures are compact static summaries, not substitutes for the complete typed JSON artifacts.
- Signed bars do not encode desirability, causality, or significance.
- Rule status bars do not encode likelihood.
- Long artifacts are explicitly truncated at the published rendering bounds.
- Tables may still require dissertation-specific layout or pagination work.
- PDF and LaTeX output must be visually reviewed in the final document environment.
- Imported evidence remains subject to its source contract, permissions, and validation limits.

## Troubleshooting

**The destination already exists:** choose another filename or explicitly add `--overwrite`.

**The study export is rejected:** pass the exact saved STA-01 `StatisticalStudy` JSON artifact,
not a rendered Markdown/PDF report or arbitrary JSON.

**No bars appear:** the source has no eligible finite scalar entries, or every result is
unavailable. The table remains the authoritative projection of that state.

**LaTeX does not find the fragment:** run the compiler from the directory assumed by `\input`, or
adjust the relative input path. TrafficTwin deliberately does not emit an absolute path.

**A wide table overflows:** use the fragment as an auditable starting point and apply a reviewed
document-level layout choice. Do not silently remove warnings or unavailable rows to make it fit.

Related records:

- [ADR-039](decisions/ADR-039-deterministic-latex-and-static-figure-exports.md)
- [Report export](report_export.md)
- [Statistical studies](statistical_studies.md)
- [Security and privacy](security_and_privacy.md)
- [Generated REP-01 contract](reference/generated/latex_export_contract.json)
