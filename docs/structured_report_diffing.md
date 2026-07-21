# Structured Report Diffing

`REP-03` compares compatible TrafficTwin report payloads before rendering. It is useful for
reviewing whether computed metrics, rule results, or comparison results changed between two report
generations without mistaking prose or layout edits for evidence.

## What It Compares

Each report carries a typed snapshot for every scientific claim already present in its claim
inventory:

- metrics: status, exact value, unit, scope, dimensions, implementation version, and reason codes;
- diagnostic rules: rule version, categorical status/confidence, evidence keys, typed observed
  values, missing-evidence keys, and scalar metadata;
- metric comparisons: status, baseline, variation, absolute/relative delta, direction, unit, and
  reason codes.

The report layer does not recalculate any of these values. It projects them from the existing
deterministic artifacts.

The diff never compares section-body prose, Markdown, HTML, PDF layout, titles, timestamps, source
display paths, warnings, claim labels, reproduction commands, analyst annotations, or annotation
targets as scientific evidence.

## Compatibility

Version 1.0 supports structured `run`, `diagnostics`, `comparison`, and `full` reports. Both inputs
must share:

- report payload schema version;
- report type;
- source mode (`synthetic` or imported/non-synthetic);
- claim-denominator definition; and
- a complete claim-reference/snapshot inventory.

An incompatible pair produces a saved `unavailable` result with stable compatibility codes. It
does not fall back to a text diff.

## Classifications

Sections and claims use five deterministic classifications:

| Classification | Meaning |
|---|---|
| `unchanged` | Eligible typed content is exactly equal. |
| `added` | The section or claim exists only in the variation report. |
| `removed` | The section or claim exists only in the baseline report. |
| `changed` | Eligible typed fields differ at one or more published JSON Pointer paths. |
| `unavailable` | Scientific comparison is not admissible, including narrative-only sections or unavailable typed evidence. |

Added/removed section titles are structural differences. A matching narrative-only section is
`unavailable` with `NO_TYPED_CLAIMS`; its text is deliberately ignored.

## CLI Workflow

First save two reports as structured JSON. The same report type should be used on both sides:

```bash
uv run traffictwin report run tests/fixtures/bundles/baseline_valid \
  --output reports/baseline_report.json

uv run traffictwin report run tests/fixtures/bundles/variation_valid \
  --output reports/variation_report.json
```

Generate the complete machine-readable diff:

```bash
uv run traffictwin report diff \
  reports/baseline_report.json \
  reports/variation_report.json \
  --output reports/structured_report_diff.json
```

Or create the presentation-oriented Markdown view:

```bash
uv run traffictwin report diff \
  reports/baseline_report.json \
  reports/variation_report.json \
  --output reports/structured_report_diff.md
```

Inspect the machine-readable boundary:

```bash
uv run traffictwin report diff-contract --format json
```

JSON contains all paths and exact values. Markdown shortens unusually long display values and
marks the truncation; use JSON for exact automated review.

## Reports Page

1. Open **Reports**.
2. Under **Regenerate Report**, use a `.json` output path to save each typed report payload.
3. Under **Structured Report Diff (REP-03)**, select the baseline and variation JSON files.
4. Choose **Compare Structured Reports**.
5. Inspect section classifications and download the complete JSON or Markdown result.

The page calls the same library used by the CLI. It does not parse prose or calculate scientific
differences in Streamlit.

## Python API

```python
from pathlib import Path

from traffictwin.reporting.diffing import (
    compare_structured_reports,
    parse_research_report_json,
    report_diff_to_markdown,
)

baseline = parse_research_report_json(Path("reports/baseline_report.json").read_bytes())
variation = parse_research_report_json(Path("reports/variation_report.json").read_bytes())
result = compare_structured_reports(baseline, variation)

print(result.status.value)
print(result.classification_counts)
print(result.fingerprint())
print(report_diff_to_markdown(result))
```

## Interpretation Limits

- A changed value is descriptive; it is not automatically better, worse, significant, causal, or
  attributable to one source row.
- REP-03 does not replace ordinary baseline-versus-variation metric comparison, statistical
  studies, regression gates, or difference provenance.
- `unavailable` must remain unavailable. Do not substitute zero or infer equality.
- Reports generated before typed claim snapshots should be regenerated with the current software.
- Analyst annotations remain a separate append-only human record and are never diff evidence.

The exact architecture decision is [ADR-041](decisions/ADR-041-typed-structured-report-diffing.md).
