# Report Export

TrafficTwin report export is deterministic template rendering over existing pipeline artifacts.
It does not use an LLM and does not calculate metrics in the reporting layer.

## Commands

```bash
traffictwin report run .demo/bundles/baseline --output .demo/reports/run.md
traffictwin report compare .demo/bundles/baseline .demo/bundles/stressed_demand \
  --output .demo/reports/comparison.md
traffictwin report diagnostics .demo/bundles/under_offloading \
  --output .demo/reports/diagnostics.md
traffictwin report full .demo/bundles/stressed_demand \
  --comparison-baseline .demo/bundles/baseline \
  --output .demo/reports/full.html
traffictwin report run .demo/bundles/baseline --output .demo/reports/run.pdf
```

Outputs ending in `.json` preserve the complete typed `ResearchReport` payload, `.html` outputs are
standalone HTML, `.pdf` outputs are A4 PDF, and other outputs are Markdown. PDF output uses the
same payload and adds a consistent header, footer, and page numbers. It embeds no remote assets or
JavaScript.

## LaTeX Tables And Static Figures

REP-01 exports four already-computed typed artifact families as escaped `.tex` table fragments and
optional deterministic SVG/PDF figures:

```bash
traffictwin report latex-metrics .demo/bundles/baseline \
  --output .demo/exports/metrics.tex --figure .demo/exports/metrics.svg
traffictwin report latex-comparison .demo/bundles/baseline \
  .demo/bundles/stressed_demand \
  --output .demo/exports/comparison.tex --figure .demo/exports/comparison.pdf
traffictwin report latex-study statistical_study.json \
  --output .demo/exports/study.tex
traffictwin report latex-rules .demo/bundles/under_offloading \
  --output .demo/exports/rules.tex
```

Both renderings derive from one bounded typed projection and carry the same projection fingerprint.
The exporter performs no scientific calculation. Source mode, unavailable values, warnings,
units, statistical method labels, and rule statuses remain explicit; local absolute paths are
redacted. See [LaTeX research tables and static figures](latex_research_exports.md) for compilation,
UI, Python, safety, and interpretation guidance.

## Append-Only Analyst Annotations

REP-02 can attach matching registry history when the registry is passed explicitly:

```bash
traffictwin report run .demo/bundles/baseline \
  --registry .demo/registry.sqlite \
  --output .demo/reports/annotated-run.html
```

Annotations render only in **Analyst Annotations — Non-computed**. They remain outside computed
sections, typed claim references, metrics, rules, provenance, and source fingerprints. See
[analyst annotations](analyst_annotations.md) for append/list commands and integrity limits.

## Structured Report Diffing

REP-03 compares two saved typed report JSON payloads before rendering:

```bash
traffictwin report run .demo/bundles/baseline \
  --output .demo/reports/baseline.json
traffictwin report run .demo/bundles/stressed_demand \
  --output .demo/reports/variation.json
traffictwin report diff .demo/reports/baseline.json .demo/reports/variation.json \
  --output .demo/reports/structured-diff.json
```

The complete JSON publishes compatibility, fingerprints, section/claim classifications, and exact
JSON Pointer field changes. Markdown is available with a `.md` output suffix. Section bodies,
rendered formats, timestamps, labels, warnings, commands, and analyst annotations are excluded
from scientific diffing. See [structured report diffing](structured_report_diffing.md).

## One-page Executive Summary

REP-04 consumes one saved typed report rather than a bundle or rendered document:

```bash
traffictwin report executive .demo/reports/baseline.json \
  --output .demo/reports/baseline-executive.pdf
```

The same command supports `.json`, `.md`/`.markdown`, and `.html`. It publishes complete
availability and omitted-highlight counts, chooses at most five existing typed claims by a closed
policy, retains all mandatory/source warnings and exact limitations, and includes relative
fingerprinted source/claim links. Analyst annotations do not enter the projection. A PDF that
needs more than one A4 page is refused rather than shortened. See
[one-page executive summary](executive_summary.md).

## Contents

Reports include:

- synthetic/imported disclaimer;
- run provenance;
- scenario and environment context;
- validation summary;
- evidence availability;
- task, infrastructure, traffic, and trip metrics where available;
- comparison deltas where requested;
- diagnostic hypotheses and missing evidence;
- provenance summary;
- limitations;
- reproduction commands.
- optional, visibly separate append-only analyst history when an annotation registry is requested.

Supported report payloads also carry a non-rendered typed claim inventory used by PRO-03 and
prose-free claim snapshots used by REP-03 and REP-04. Run and
diagnostics reports reference selected metric results plus every rule result; comparison reports
reference selected typed comparisons; full reports combine and rebase those claims. The inventory
does not change Markdown/HTML/PDF wording. It provides the explicit denominator for the separate
[provenance completeness](provenance_completeness.md) artifact, where unavailable claims remain
visible.

## Security And Path Policy

- Report text is deterministic and template-based.
- HTML output escapes untrusted text.
- Reports do not embed remote assets or JavaScript.
- Absolute local paths are normalised to repository-relative or basename references where practical.
- Large raw CSV tables are not embedded.
- PDF generation uses ReportLab and performs no metric or diagnostic calculation.

## Limitations

- Registry-run report shortcuts are not the primary supported path; bundle paths are supported first.
- Reports do not prove correctness or causality.
- Structured report changes are descriptive and do not establish significance, desirability,
  attribution, or causality.
- Synthetic reports are demonstration artifacts only.
- Render PDF pages to images and inspect them visually before dissertation submission.

## TOS Imported-Simulation Exports

The optional TOS workbench exports a deterministic report and aggregate static atlas:

```bash
traffictwin integration tos results-pack "$TOS_DATA_PATH" --output tos-results
```

This output uses source-analysis models rather than canonical Phase 3 metrics. It carries a
publication-permission warning and must not be publicly deployed until source-data permission is
confirmed. See [TOS Results Workbench](integration/tos_results_workbench.md).

Related documents:

- [Standalone demo](standalone_demo.md)
- [Provenance Explorer](provenance_explorer.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Security and privacy](security_and_privacy.md)
- [LaTeX research tables and static figures](latex_research_exports.md)
- [Structured report diffing](structured_report_diffing.md)
