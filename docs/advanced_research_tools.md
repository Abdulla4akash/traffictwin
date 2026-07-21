# Advanced Research Tools

This increment adds nine research-support features while preserving TrafficTwin's import-first,
deterministic boundary. Every generated study artifact is labelled synthetic or mock. No command
launches Randy/VEC, SUMO, training, or a live-data process.

## 1. Expanded Synthetic Fault Evaluation

`build_extended_fixture_set` expands the declared diagnostic fixture catalogue across low,
moderate, and high severity and three deterministic random seeds. `evaluate_fixture_set` reports
per-rule true/false positives, true/false negatives, precision, recall, false-positive rate,
specificity, development/held-out summaries, severity robustness, failure case IDs, and a
transparent KPI-threshold baseline. It covers R0-R5.

```bash
traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json --extended
```

This is software fault injection, not external diagnostic validation.

## 2. Portfolio Statistics And Reports

The held-out portfolio study now reports selected-score and regret variability, per-constituent
variability, failed seed IDs, min/max values, and a pairwise dominance matrix. JSON, CSV, and
Markdown outputs use the same deterministic study object.

```bash
traffictwin experiment portfolio-study \
  --registry .demo/registry.sqlite \
  --experiment-id exp-synthetic-portfolio-study \
  --format markdown
```

The selector remains a hand-authored synthetic workflow demonstration, not a trained or calibrated
policy.

## 3. Synthetic Case-Study Pack

The case-study builder creates baseline, incident/demand, and reduced-infrastructure bundles,
metrics, diagnostics, individual reports, pairwise comparison reports, SHA-256 checksums, and a
manifest. The destination must be empty unless overwrite is explicit.

```bash
traffictwin synthetic case-study-pack --output case-study --overwrite
```

Every scenario is a deterministic synthetic fixture. The pack does not establish traffic or VEC
causality.

## 4. Complete Accepted-Row Metric Ledgers

`MetricContributionReport` lists every accepted canonical candidate row for a selected metric,
its source file and row, canonical values, inclusion state, and deterministic inclusion reason.
The ledger is unbounded and available as JSON or CSV.

```bash
traffictwin provenance contributors .demo/bundles/baseline \
  task.latency.mean_ms --format csv --output contributors.csv
```

For grouped and percentile metrics, inclusion identifies the complete input set. The ledger does
not invent causal weights. Rows rejected before canonicalisation remain in the validation report.

`DifferenceContributionReport` extends this audit to a compatible baseline/variation pair. Direct
count/sum/mean/rate formulas expose signed terms only after exact delta reconciliation;
non-decomposable scalar metrics retain both eligible populations with null weights.

```bash
traffictwin provenance difference-contributors .demo/bundles/baseline \
  .demo/bundles/stressed_demand task.completion.rate --format json
```

See [difference provenance](difference_provenance.md). Reconciliation is calculation lineage, not
causal attribution.

## 5. Dissertation PDF Export

Any report command writes A4 PDF when the output suffix is `.pdf`. The renderer uses ReportLab,
adds a consistent header/footer and page numbers, preserves deterministic report contents, and
embeds no remote assets or JavaScript.

```bash
traffictwin report full .demo/bundles/stressed_demand \
  --comparison-baseline .demo/bundles/baseline \
  --output dissertation-report.pdf
```

PDF rendering does not calculate metrics. Generated files should be rendered to images and
visually inspected before submission.

## 6. Browser Screenshots And Accessibility Regression Checks

`scripts/ui_browser_audit.py` starts or connects to Streamlit, captures five desktop pages and a
mobile Home view, and checks main-heading count, visible interactive names, image alt attributes,
duplicate DOM IDs, and horizontal overflow.

```bash
python -m playwright install chromium
python scripts/ui_browser_audit.py --output output/ui-audit
```

The audit is a regression aid, not a WCAG conformance claim. Keyboard, screen-reader, contrast,
and participant testing remain separate work.

## 7. Synthetic/Source Corridor Plane

Replay renders coordinate-bearing vehicle histories and current positions at the logical replay
time. Axes are explicitly labelled non-geographic. Incident location is displayed only as source
metadata unless coordinates exist. Missing x/y evidence produces an unavailable panel instead of
an invented map.

## 8. Labelled Mock Participant Analysis

The participant analyser accepts only `dataset_mode: synthetic_mock`. It validates the published
anonymised schema, excludes withdrawn records, and computes descriptive task, timing, assistance,
rating-distribution, and supplied comment-code summaries.

```bash
traffictwin participant-evaluation analyse-mock docs/evaluation/mock_results.json
```

The bundled JSON is a software fixture, not collected participant evidence. The tool does not
authorise recruitment, infer ethics approval, perform qualitative coding, or estimate a
population effect.

## 9. Constrained Findings Renderer

The findings renderer converts an existing `DiagnosticReport` into JSON or Markdown. It copies
only declared statuses, hypotheses, findings, evidence keys, conditional actions, prerequisites,
verification steps, and limitations. Every finding sentence cites its finding ID and evidence
keys. It performs no metric calculation, diagnosis, or LLM call.

```bash
traffictwin diagnose render .demo/bundles/under_offloading \
  --format markdown --output diagnostic-narrative.md
```

An LLM could only be introduced later behind the same computed-finding boundary. It must never
calculate metrics, invent findings, or recommend unsupported actions.

## Verification

The code paths have unit, integration, CLI, UI, PDF-parsing, AppTest, and real-browser coverage.
The full project gate is:

```bash
ruff check .
mypy
pytest -q
python -m build
python scripts/generate_reference_docs.py
git diff --exit-code docs/reference/generated
python scripts/ui_browser_audit.py --output output/ui-audit
```
