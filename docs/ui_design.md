# UI Design

The current UI is a thin Streamlit layer over the tested TrafficTwin library.

## Principles

- Validation, metrics, comparison, evidence packs, diagnostics, and provenance traces are computed by library services.
- Streamlit pages render state and call UI service functions.
- Unsupported and unknown capabilities are disabled.
- Direct launch is visibly unavailable for the generic CSV adapter.
- Every analysis view labels data as synthetic, imported, or historical replay.

## Pages

- Home: registry counts, workspace status, quick actions, recent reports, capability manifest, and
  limitations.
- Guided Demo: mobile-visible, stage-based navigation through either the standalone synthetic
  pipeline or the read-only imported TOS evidence workflow.
- Experiment Planner: registered-seed selection, common-random-seed design, bounded run-matrix
  preview, seed diff, planned-experiment registration, exhaustive protocol YAML/CSV, and read-only
  completed-bundle matching without run creation.
- Scenario Builder: synthetic generator configuration, validation, YAML preview, bundle generation,
  optional bounded EXP-03 measurement-noise/dropout controls with separate seed and fingerprinted
  audit preview, and normal bundle validation.
- Manifest Inference Wizard: bounded deterministic CSV suggestions, visible ambiguity and evidence
  methods, editable file/column/unit selections, explicit acknowledgement, and confirmed artifact
  downloads. It does not validate, canonicalise, import, or analyse its draft.
- Bundle Import & Validation: single, explicit batch paths/globs, or opt-in chunked large-bundle
  processing; consolidated/per-bundle or streaming bounds/counts, manifest, files, validation
  findings, evidence availability, and isolated/metadata import.
- TOS Data Import: read-only external result inventory, NPZ contract validation, source-summary
  registry import, source-contract inspection, and aggregate provenance.
- TOS Results: source evaluation matrix, exact fleet-seed paired deltas, and explicit
  in-domain/held-out/unknown labels.
- TOS Mobility & RSU Replay: logical source playback, deliberate processed-FCD spatial snapshots,
  bounded task views, and RSU pressure/backlog. Pressure remains separate from canonical
  utilisation/queue metrics.
- TOS Training & Audit: bounded training curves, greedy summaries, reproducibility checks,
  machine-readable integration gates, and deliberate private supervisor/report/atlas downloads.
- Experiment Manager: experiments, runs, seeds, policies, fingerprints, comparisons, reports, metric
  storage, evidence storage, and manual protocol-slot tracking.
- Triviality: selectable scalar metric/objective, explicit ordered training-validation pairs, R3
  and R5 results, compatibility-filtered per-seed winner map, transparent synthetic portfolio and
  fixed held-out study evaluation, and JSON downloads.
- Replay: validated dataset selector, historical replay clock, deterministic controls, filters,
  and time-series views. The standalone demo prefers an incident-capable synthetic dataset so the
  vehicle and incident controls can be exercised immediately; absent evidence remains visibly
  unavailable after switching datasets.
- Run Overview: KPI cards, task charts, metric availability, provenance.
- Temporal Metrics: library-computed fixed-window series, explicit range/alignment/edge controls,
  visible empty/unavailable intervals, scalar chart, typed R6 evidence/declared-event controls,
  deterministic results, contract details, and JSON downloads.
- Energy Evidence: exact MET-03 values, contract/coverage/count identity, and library-evaluated R8
  threshold/support controls without mixed-unit conversion or hardware-efficiency claims.
- Fairness Evidence: operational vehicle-tier/RSU group values, gaps/Jain, support, coverage,
  policy identity, and library-evaluated R7 dimension/threshold controls without protected-
  attribute claims.
- Spatial & RSU Evidence: exact V2I target-RSU outcomes plus contracted source-frame grid cells,
  coverage, geometry, and contract identity without inferred targets, geography, or causality.
- Infrastructure & Congestion: RSU queue/utilisation, saturation config, load balance availability.
- Comparison: compatibility, seed diff, metric deltas by domain, and PRO-01 difference lineage.
  The page shows signed row terms only for admitted direct formulas; percentiles and other
  non-decomposable scalar metrics retain eligible rows with null weights and mandatory
  non-causality language.
- Statistical Study: registered paired, N-way, paired-equivalence, versioned regression-gate, or
  prospective paired-power selection; exact
  common-seed compatibility/exclusion audit; original-unit paired effects/tests, per-family policy
  ranks and joint-bootstrap uncertainty, predeclared-margin paired TOST, uploaded immutable golden
  assertion audit, or declared-effect/variance power plan; provenance,
  assumptions/limitations, and JSON/Markdown/CSV downloads.
- Journey-Time Lens: imported trip duration metrics and comparison.
- Diagnostics & Evidence: validation/evidence state, rule results, alternatives, missing evidence,
  conditional recommendations, typed DIA-07 conflict/corroboration/suppression relationships,
  retained originals, and report downloads.
- Threshold Sensitivity: explicit complete-config import/export, bounded R5/R7/R8 grid controls,
  every ordinary rule status, neutral stability chart/table, sampled flip intervals, embedded
  exact DIA-05 boundary when admissible, provenance, limitations, and report download. Controls
  are session-only and never silently persist defaults.
- Parameter Sweep: one to four closed synthetic axes, explicit seed/local/external mode, complete
  point provenance, local core-metric response rows, JSON/CSV downloads, and visible no-launch/
  synthetic-evaluation labels. The page delegates validation, generation, and metrics to services.
- Scenario Mutations: one closed dropout/jitter/RSU-removal operator over a copied valid labelled
  synthetic/evaluation bundle, exact row/file ledger and fingerprints, JSON export, explicit
  parent-read-only/no-launch labels, and visible unsupported-source/encoding errors. The page
  delegates planning, execution, and validation to services.
- Provenance Explorer: PRO-03 run/diagnostics claim inventory and score plus read-only metric,
  diagnostic-rule, source-row, and run-context traces with bounded path-safe/structure-only graph
  rendering, exact omission counts, node inspection, and JSON/CSV/Markdown/DOT/GraphML export.
- Reports: existing report inventory/downloads, explicit report regeneration (including typed
  `.json` payloads), a REP-01 panel for metric/comparison/STA-01/rule `.tex` tables plus optional
  SVG/PDF figures, a REP-02 panel for typed append-only analyst notes/history plus opt-in annotated
  report generation, a REP-03 panel for compatibility-gated structured JSON comparison with exact
  JSON/non-causal Markdown downloads, and a REP-04 panel for complete-availability supervisor
  summaries with fail-closed one-page PDF plus HTML/Markdown/JSON downloads.
- Search: local metadata search over runs, experiments, reports, metrics, rules, and source files.
- Settings: session-scoped UI preferences.
- About: version, schema, generator, diagnostic, provenance, build, licence, and trusted custom-
  metric boundary metadata. It explicitly says there is no upload or sandbox.

## Shared Components

The UI uses reusable helpers for:

- `StatusBadge`, `ScenarioBadge`, `EvidenceBadge`, and related compact labels;
- `MetricCard`;
- `ReportCard`;
- `SectionHeader`;
- metadata tables;
- unavailable-data panels.

Pages should call service functions and shared components rather than duplicating formulas, report
builders, validation logic, or diagnostic interpretation.

The Reports REP-01 panel calls `generate_research_export_for_ui`. Streamlit only collects the
artifact family, explicit source/output paths, figure format, and overwrite decision. The service
loads or computes the ordinary typed artifact and delegates projection/rendering/publication to
`reporting.latex`. The page cannot calculate a value, turn missing evidence into zero, convert rule
confidence to probability, infer favourable bar direction, or regenerate an existing file without
explicit overwrite.

The REP-02 panel calls `append_analyst_annotation_for_ui` and
`list_analyst_annotations_for_ui`. It collects only a closed target kind, path-free identifier,
optional exact fingerprint, author label, decision label, and bounded note. The registry owns
target verification, sequence, identity, and append-only enforcement. The page cannot edit/delete
history or merge notes into computed findings. Annotated regeneration delegates complete matching
history to `attach_registry_annotations` and labels it non-computed.

The REP-03 panel calls `compare_structured_reports_for_ui`. It collects two explicit saved report
JSON paths and displays only the library's section classifications. The service performs bounded
strict parsing, compatibility checks, typed claim comparison, fingerprinting, and JSON/Markdown
rendering. Streamlit never parses values from prose, compares rendered bodies, or calculates a
metric/rule/comparison difference.

The REP-04 panel calls `build_executive_summary_for_ui` with one explicit saved report JSON path.
The service owns compatible-inventory admission, deterministic claim selection, availability
reconciliation, warning/limitation retention, provenance links, escaping, and PDF page-count
verification. The page displays those returned values and downloads; it cannot select claims,
recalculate results, hide caveats, or include analyst annotations.

Guided Demo is an action-aware workflow assistant rather than a page catalogue. Its
framework-independent stage and progress models persist the selected evidence track, current
stage, completions, and explicit skips. Starting or resuming a workflow opens the current real
page, where a persistent guide gives the exact task and interpretation boundary. Successful
experiment registration and report regeneration emit typed completion signals and open the next
stage automatically; inspection stages require one explicit **Reviewed — continue** acknowledgement.
The guide itself performs no scientific computation, makes no scientific choice, and never
advances from elapsed time.

Experiment Planner delegates design validation to `traffictwin.experiments.planning` and registry
operations to `ui.services`. `traffictwin.experiments.protocol` supplies every slot, fingerprint,
export, and match result. The page does not generate synthetic records, compute metrics, create
`Run` objects, import matched bundles, or expose a launch control.

Triviality delegates all calculations to experiment services. It labels the portfolio as a
synthetic prototype and does not calculate pair compatibility, ranks, regret, or rule results in
the page. Experiment
Manager's tracking controls apply only validated manual lifecycle transitions; they do not execute
or import a run.

## Visual Policy

The UI uses neutral Plotly time-series and bar charts. It does not use colours to imply improvement, harm, or causal judgement. It does not render maps when coordinates are absent.

Temporal Metrics charts only available scalar values and retains a table row for every resolved
window. The page must show grid/effective bounds, coverage, partial disposition, source count,
availability, and reasons. Coverage is requested-range overlap, never a visual claim of sensor
uptime or sampling completeness. All filtering and calculation remains in
`traffictwin.metrics.windowed` via `ui.services`.

R6 controls call the temporal diagnostic library service. The page may expose provisional
thresholds and an optional declared event, but it must not drop a gap, infer an event, calculate a
rule, or strengthen a candidate hypothesis into a causal finding.

R7 controls likewise call `ui.services.evaluate_fairness_diagnostic_for_ui`. The page selects one
dimension and renders the typed `RuleResult`; it cannot merge dimensions, drop thin groups,
calculate gaps, load declarative YAML, or turn an operational disparity into protected-attribute,
geographic, statistical, or causal language.

R8 controls call `ui.services.evaluate_energy_diagnostic_for_ui`. The page renders admitted metric
and rule artifacts; it cannot calculate energy, repair coverage, convert units, relabel source-
specific measures, persist threshold changes, or strengthen a candidate into statistical, causal,
hardware-efficiency, or recommendation language.

Threshold Sensitivity calls `ui.services.evaluate_threshold_sweep_for_ui`, which delegates the
entire grid to `diagnostics.threshold_sweep`. The page may render points, statuses, fixed config,
stability, sampled intervals, and embedded DIA-05 output; it cannot calculate a rule, omit a grid
point, relabel a sampled interval as exact, lower support, or treat a threshold as calibrated.
Config changes remain in session state until the user explicitly downloads/imports a complete
validated `RuleSetConfig`; no registry, repository, package default, bundle, or raw evidence is
updated.

Diagnostics & Evidence renders `DiagnosticReport.cross_rule_analysis` directly. It displays typed
relationship counts, exact shared keys, precedence, presentation effects, suppressed and
unclassified IDs, provenance/limitations, and a JSON download before showing every original
RuleResult. The page cannot infer a relationship, rank rules, raise confidence, hide a suppressed
target, or convert corroboration into causal support.

Statistical Study calls `ui.services.evaluate_statistical_study_for_ui`,
`ui.services.evaluate_n_way_ranking_for_ui`, or
`ui.services.evaluate_equivalence_study_for_ui`; its regression mode parses one bounded uploaded
golden and calls the metric/study regression service, while its power mode calls
`ui.services.evaluate_power_analysis_for_ui`. Complete calculation remains in
`experiments.statistical_study`, `experiments.n_way_ranking`, `experiments.equivalence_testing`, or
`experiments.regression_gate`, with prospective planning in `experiments.power_analysis`. The page
cannot recompute metrics, remove exclusions, reverse an
estimand, select a favourable compatibility subgroup, persist an analysis, infer interval-based
ties, choose/validate an equivalence margin, regression tolerance, target effect, or variance,
approve/rewrite a golden, calculate retrospective power, reinterpret ordinary non-significance,
or claim causality. Missing evidence remains visibly
unavailable, insufficient, incompatible, or degenerate.

What-if Compare calls `ui.services.difference_contributions_for_ui` after the ordinary comparison
has identified compatible scalar metrics. The service delegates all eligibility, arithmetic,
reconciliation, and unavailable behavior to `provenance.differences`; Streamlit only selects a
metric and renders/downloads the typed JSON/CSV artifact.

Spatial & RSU Evidence renders dictionaries already computed by `metrics.spatial` and the existing
capacity-normalised-load metric. It may combine rows for display, but it cannot assign a target,
cell, task position, or missing value. Source-frame cells are tabular and explicitly non-geographic.

## Data Modes

Operational modes in Phase 4:

- `SYNTHETIC`
- `IMPORTED`
- `HISTORICAL REPLAY`

`NEAR-LIVE` and `TRUE LIVE` may appear only as unsupported future capability labels.

## Diagnostic Presentation

The diagnostic page uses cautious language:

- “candidate hypothesis”
- “may indicate”
- “is consistent with”
- “requires verification”

It avoids causal-proof language that would turn a candidate hypothesis into a settled conclusion. Recommendations are displayed as conditional follow-up checks, not automatic actions.

Cross-rule conflict chooses no winner. Corroboration is labelled contextual and does not increase
confidence. Suppression is always “suppressed for action/presentation” and is accompanied by the
unchanged original result and reason.

## Provenance Presentation

The Provenance Explorer uses a readable vertical lineage and grouped node tables rather than a
force-directed graph. It distinguishes:

- observed source evidence;
- canonical records;
- metric results and definitions;
- rule findings;
- candidate hypotheses;
- missing or unavailable links.

Aggregate metric traces show eligible input rows and bounded samples. A separate expander can
export the complete accepted-candidate-row ledger. The UI must not imply that an individual row
caused an aggregate result.

The PRO-03 expander uses the typed service artifact and a static full claim table. It shows the
denominator, source-row-complete, aggregate-only, and unavailable counts before the score and
aggregate-or-better fraction. Unavailable rows are never filtered from the denominator. The
Comparison page applies the same presentation to comparison-report claims. Streamlit performs no
classification or arithmetic.

Replay includes a source-coordinate corridor plane only when canonical vehicle x/y evidence is
present. Axes are labelled non-geographic and incident locations remain text metadata unless a
coordinate exists. The `Mock Evaluation Analysis` page accepts only explicitly labelled synthetic
mock data and states that ethics approval and participant evidence are absent.

## Standalone Demo Presentation

When launched through `traffictwin demo launch`, Home shows a `Standalone Demo` section with
workspace status, scenario count, imported runs, and diagnostic preparation status. This is a status
badge and selector aid only; the normal import-first pages remain the same.

The UI must continue to label all generated data as synthetic and must not enable direct launch,
full Randy/VEC conversion, SUMO FCD/launch, near-live data, or true-live data from the standalone
workspace. The bounded SUMO Output Import page reads only declared existing XML results. The
optional TOS page labels its content `IMPORTED SIMULATION` and `HISTORICAL REPLAY`.

Home exposes primary actions in the page body because Streamlit collapses its sidebar on narrow
viewports. Guided Demo uses short stage controls and stable dimensions so the workflow remains
usable on phone-sized screens.

## Product Polish

The Product Polish phase adds research workflow pages and consistent navigation without changing the
scientific pipeline. See [Product polish and research UX](product_polish.md).
