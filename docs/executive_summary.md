# One-page Executive Summary

`REP-04` produces a bounded supervisor-facing summary from one existing typed
`ResearchReport` JSON payload. It is a deterministic projection and renderer: it does not rerun
validation, calculate metrics, evaluate rules, compare experiments, infer causes, or use an LLM.

The authoritative machine-readable boundary is
[`executive_summary_contract.json`](reference/generated/executive_summary_contract.json). The
architectural decision is [ADR-042](decisions/ADR-042-deterministic-one-page-executive-summary.md).

## What The Summary Shows

Every summary visibly retains:

- source mode (`synthetic` or `imported`), source report type and exact source identifiers;
- complete typed-claim totals, available/unavailable counts, and per-kind counts;
- no more than five selected existing typed claims, with status, display value, reason codes, and
  exact claim fingerprints;
- the number of source claims outside the bounded highlight set;
- all three mandatory interpretation warnings plus every warning supplied by the source report;
- every item in the source report's exact `Limitations` section, or an explicit statement that no
  such section was supplied;
- a source-report link plus one claim-specific provenance link for every selected highlight;
- the published selection policy and explicit statements that analyst annotations are excluded
  and scientific recomputation did not occur.

The source payload and scientific-content fingerprints are both retained. Absolute source display
paths are reduced to their basename before rendering. Generated links are relative to the saved
source-report filename and never invent a remote service or live provenance endpoint.

## Deterministic Selection

The v1 policy is closed and fingerprinted:

1. select at most two triggered rule results;
2. select at most two available comparison results whose existing direction is not `unchanged`;
3. select at most one unavailable claim;
4. select at most one remaining rule result;
5. fill unused positions with available metrics, remaining comparisons, remaining rules, and then
   other claims;
6. break every tie by the report-independent scientific claim key.

Each earlier selection reduces the remaining five-slot capacity. The policy does not decide which
result is desirable or important, and it does not calculate a score. The complete inventory count
and source-report link make the bounded omission visible.

## Warning And Page-fit Policy

Warnings and limitations use `retain_all_or_refuse`. The projector refuses inputs with more than
100 source warnings or 100 limitations instead of silently dropping entries. Markdown, HTML, and
JSON retain the complete bounded projection.

The PDF renderer writes invariant A4 output and then verifies that the result has exactly one
page. If complete content requires multiple pages, PDF export fails with an explicit overflow
message. It never shrinks away, truncates, or removes a warning or limitation to satisfy the page
count. Use the full report, reduce the source report through its governed upstream process, or use
the complete Markdown/HTML/JSON projection; do not edit the generated evidence silently.

## CLI Usage

First save a typed structured report:

```bash
uv run traffictwin report run tests/fixtures/bundles/baseline_valid \
  --output reports/baseline-report.json
```

Inspect the machine-readable contract:

```bash
uv run traffictwin report executive-contract --format json
```

Render any supported format:

```bash
uv run traffictwin report executive reports/baseline-report.json \
  --output reports/baseline-executive.pdf
uv run traffictwin report executive reports/baseline-report.json \
  --output reports/baseline-executive.html
uv run traffictwin report executive reports/baseline-report.json \
  --output reports/baseline-executive.md
uv run traffictwin report executive reports/baseline-report.json \
  --output reports/baseline-executive.json
```

The source must be a compatible v1.0 run, diagnostics, comparison, or full report with a complete
typed claim-reference/snapshot inventory. Old presentation-only reports must be regenerated.

## Reports Page

Open **Reports**, find **One-page Executive Summary (REP-04)**, enter the saved report JSON path,
and choose **Generate One-page Executive Summary**. The page shows availability cards, selected
claims, all warnings, limitations, and provenance links. PDF, HTML, Markdown, and JSON downloads
come from the same library projection; Streamlit does not calculate or select claims itself.

## Interpretation Limits

- The summary is an index into existing computed evidence, not a replacement for the full report.
- `synthetic` never means real-world or Manchester validation.
- `imported` never means live, complete, representative, or externally validated.
- An unavailable claim is evidence of a boundary or gap, not a zero result.
- A selected diagnostic result remains a candidate hypothesis, not an established cause.
- A comparison direction is descriptive and does not establish significance, desirability, or
  causality.
- Provenance links identify exact source payloads and claims; they do not prove data truth or
  causal attribution.
- Analyst annotations are intentionally excluded because they are human commentary, not computed
  scientific claims.

## Verification

Acceptance coverage includes deterministic selection and fingerprints, complete availability
reconciliation, warning/limitation retention, absolute-path redaction, hostile-text escaping,
incomplete-inventory refusal, explicit PDF overflow refusal, byte-deterministic single-page A4
PDF, exact golden JSON, all four CLI formats, UI service downloads, Streamlit controls, generated
schemas/contracts, and a rendered PNG visual inspection for clipping, overlap, and legibility.
