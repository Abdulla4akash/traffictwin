# User Guide

TrafficTwin is an import-first Streamlit prototype. It supports repository-contained synthetic
fixtures, standard imported historical bundles, and optional read-only inspection of Randy's
separately supplied TOS Data result package. It does not run Randy/VEC or SUMO and does not provide
live Manchester or near-live feeds.

## Launching The UI

Install the project first:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Launch:

```bash
streamlit run src/traffictwin/ui/app.py
```

The UI reads local paths. The demo fixture paths are:

- `tests/fixtures/bundles/baseline_valid`
- `tests/fixtures/bundles/variation_valid`
- `tests/fixtures/bundles/partial_valid`

## Home / Project Status

Use Home to check:

- current phase label;
- registry path and counts;
- latest runs where a registry exists;
- capability manifest;
- prototype limitations.

Warning: direct simulator launch, live data, and full Randy/SUMO integration are not implemented.
The generic adapter and TOS result reader both report direct launch as unsupported.

## Scenario Builder

Scenario Builder creates deterministic synthetic scenario configurations and can generate standard
TrafficTwin run bundles from those configurations.

Steps:

1. Choose an existing synthetic preset to duplicate.
2. Edit documented generator parameters such as vehicle count, trip count, congestion multiplier,
   RSU count, RSU capacity, task-arrival rate, task mix, random seed, and synthetic policy profile.
3. Review validation errors from `SyntheticScenarioConfig`.
4. Review the expected bundle ID, run ID, and file list.
5. Download the generator configuration YAML or generate a bundle directory.
6. Validate the generated bundle through the normal import-first workflow.

The builder exposes only the current synthetic generator model. It does not launch Randy, SUMO, or
any live data source.

## Bundle Import & Validation

Use this page to validate a bundle path without pretending that rejected data is usable.

Steps:

1. Enter a bundle directory or ZIP path.
2. Click validate.
3. Review manifest summary and declared files.
4. Review validation counts and findings.
5. Review evidence availability.
6. Import only accepted or warning-level bundles.

Findings include stable code, severity, file, row, field, message, affected capabilities, and whether processing may continue.

Warning: a rejected bundle must not be used in Run Overview, comparison, evidence, or diagnostics as if it were valid.

## TOS Data Import

The `TOS Data Import` page is an optional, read-only workflow for the separately checked-out result
package supplied by Randy. Install the optional dependency first:

```bash
python -m pip install -e ".[dev,tos]"
```

Then:

1. Open `TOS Data Import` and enter the local package directory.
2. Select **Inspect Package** for a structural inventory or **Deep Validate NPZ Contracts** for
   archive key/shape checks and JSON-summary reconciliation.
3. Review the package commit, fingerprint, engine version, findings, and capability boundary.
4. Expand **vec_env source contract** to see confirmed units, field meanings, the semantics commit,
   and why direct launch remains disabled.
5. Optionally import evaluation summaries into a separate SQLite registry. Repeated import is
   idempotent.
6. Filter the evaluation table, select a run, and inspect source-provided completion, latency, and
   action-share metrics.
7. For matched showcase runs, inspect a historical replay frame, load bounded RSU pressure
   history, or inspect a bounded per-arrival task/action sample.
8. Download the partial EvidencePack, DiagnosticReport, or aggregate provenance trace.

The import page is the validation gate. After inspection, use the focused pages:

### TOS Results

1. Choose an evaluation fleet and one source-analysis measure.
2. Read the campaign-by-cell heatmap; each cell is a fleet-seed mean and hover text reports `n`.
3. Choose a variation campaign for an exact common-fleet-seed comparison against baseline.
4. Read deltas as `variation - baseline`; the UI does not label them causal improvements.
5. Inspect the in-domain/held-out/unknown matrix. Unknown means the package does not establish the
   relationship.

### TOS Mobility & RSU Replay

1. Select an instrumented run.
2. Use play, pause, restart, step, speed, and jump controls on the logical source timeline.
3. Load a spatial frame deliberately when a source coordinate snapshot is needed.
4. Expand the processed mobility profile for active-slot speed over simulation time.
5. Expand the RSU explorer for in-flight concurrency pressure and remaining compute backlog.
6. For one of six per-task showcases, build the exact task-class/decision outcome summary or load
   a bounded source sample.

Warning: processed FCD is simulation mobility state, not a live map or trip output. Vehicle slots
are recycled, and RSU pressure is not CPU utilisation.

### TOS Training & Audit

1. Filter and select a source training history.
2. Inspect training-distribution completion and decision-share curves. Warm-up `nan` values appear
   as unavailable.
3. Keep the greedy evaluation separate from Manchester evaluation results.
4. Review reproducibility checks and blocked artifacts.
5. Deliberately prepare and download the Markdown report, standalone HTML report, or static atlas.

Warning: confirm source-data permission before publicly hosting or sharing Randy-provided aggregate
results. TrafficTwin does not deploy the atlas automatically.

Important limitations:

- `completion` is presented as source-defined deadline success per arrival, not eventual physical
  completion.
- source mean latency includes deadline-missing arrivals and may include backlog delay.
- `rsu_load` is confirmed as in-flight task count, `rsu_busy_ms` as remaining compute backlog, and
  `rsu_max_concurrent` as the concurrency bound. Their ratio is displayed as source-specific
  concurrency pressure, not TrafficTwin queue length or CPU utilisation.
- vehicle entries are time-indexed array slots, not persistent canonical vehicle IDs.
- positions are SUMO network metres, speed is metres per second, and time is simulation seconds.
- no trip, raw SUMO XML/config, per-vehicle tier, action-target, or link-quality evidence is
  invented.
- this is imported historical simulation output, not live data.

The page does not convert the package to a standard TrafficTwin run bundle. See
[integration/tos_data_adapter.md](integration/tos_data_adapter.md) for the exact supported boundary.
The analysis and export workflow is documented in
[integration/tos_results_workbench.md](integration/tos_results_workbench.md).

## Reading Validation Findings

Severity meanings:

- `info`: context only.
- `warning`: import may proceed, but downstream evidence may be limited.
- `error`: invalid data or metadata; import may proceed only when the finding says it may continue.
- `fatal`: validation cannot safely continue.

Unavailable evidence is not the same as zero. It means the required source table or field is absent, invalid, or not declared.

## Experiment Manager

Experiment Manager is a read-only organisational page for browsing local project state.

It shows:

- experiments;
- runs;
- seeds;
- synthetic policy labels;
- bundle fingerprints;
- stored metric and evidence counts;
- available comparisons;
- reports.

Use the search and filter controls to narrow tables. The page does not modify experiments or rerun
analysis.

## Replay

Replay is historical replay only.

Expected labels:

- `HISTORICAL REPLAY`
- `SYNTHETIC` or `IMPORTED`

The replay clock filters imported timestamps. It does not consume wall-clock live data. If
coordinates are absent, the UI shows time-series and tables rather than fabricating a map.

Controls include play, pause, resume, restart, timestamp jump, scrubber, speed presets, step
forward/back, and filters for vehicle, RSU, task class, and incident type where evidence exists.

## Run Overview

Run Overview displays metric cards and charts for accepted bundles:

- tasks generated and completed;
- completion and incomplete rates;
- observed completed-task deadline-miss rate;
- latency P50/P95;
- offload rate;
- decision shares;
- class breakdown;
- provenance and validation status.

Unavailable metrics are shown as unavailable with reason codes. They are never shown as zero.

## Infrastructure & Congestion

This page uses `infra_state` evidence where available:

- queue length over time;
- utilisation over time;
- per-RSU summaries;
- saturation episode count;
- saturation duration;
- load-balance availability.

The saturation threshold is a configurable demo threshold, default `0.90`. It is not a validated research threshold.

## Comparison

Compare an accepted baseline and variation.

The page shows:

- compatibility checks;
- changed seed parameters when seed snapshots are available;
- baseline value;
- variation value;
- absolute delta;
- relative delta;
- neutral direction: increased, decreased, unchanged, or unavailable.

Warning: TrafficTwin does not automatically label a change as better or worse unless a metric definition safely supports that interpretation. Current comparison wording is descriptive.

## Journey-Time Lens

Journey-Time Lens uses imported trip records, not live journey-time prediction.

It shows:

- total trip records;
- completed and incomplete trip counts;
- duration mean/P50/P95/min/max;
- distribution and comparison where available.

Use labels such as synthetic trip duration or imported trip duration. Do not interpret fixture outputs as real Manchester journey-time predictions.

## Diagnostics & Evidence

This page displays:

- validation summary;
- evidence availability;
- EvidencePack ID/fingerprint;
- rule status for R0-R3;
- triggered candidate hypotheses;
- insufficient rules;
- conflicting evidence;
- alternatives;
- missing evidence;
- conditional recommendations;
- DiagnosticReport JSON download.

Warning: these are deterministic, evidence-based diagnostic hypotheses. They are not proven root causes and should be verified through controlled follow-up experiments.

## Provenance Explorer

The Provenance Explorer is a read-only audit page. It shows how TrafficTwin derived a displayed
metric or diagnostic hypothesis from available artifacts.

Use it to trace:

- `task.completion.rate` back to the metric definition, canonical `TaskRecord` samples, `tasks.csv`
  rows, manifest, seed, run, environment, and fingerprint;
- `infra.utilisation.p95` back to `InfrastructureRecord` samples and `infra_state.csv`;
- `trip.duration.p95_s` back to `TripRecord` samples and `trips.csv`;
- a diagnostic rule result back through findings, evidence keys, metric results, definitions, and
  unavailable links.

Steps:

1. Load an accepted bundle through the existing workflow.
2. Open `Provenance Explorer`.
3. Choose `Metric`, `Diagnostic rule`, `Source file row`, or `Run metadata`.
4. Inspect completeness, lineage, grouped nodes, source-row previews, and validation context.
5. Download trace JSON or Markdown if needed.

Warnings:

- Provenance supports auditability; it does not prove real-world causality.
- Aggregate metrics show eligible input rows and exact counts, not per-row causal weights.
- EvidencePack-only fault-injection traces cannot inspect source rows unless a source bundle exists.
- Source-row previews are bounded and read-only.

## Downloading JSON

The UI can expose:

- EvidencePack JSON;
- DiagnosticReport JSON;
- ProvenanceTrace JSON and Markdown;
- validation/metric data through CLI commands.

These JSON documents are useful for reproducibility, tests, and dissertation appendices.

## Reports

Reports lists deterministic Markdown and HTML reports in the active workspace.

You can:

- search reports by name, type, format, or scenario hint;
- download existing reports;
- deliberately regenerate a selected report from explicit bundle paths.

Reports are never regenerated automatically. Report content comes from `traffictwin.reporting`, not
from Streamlit page logic.

## Search

Search performs local substring search over registry metadata, reports, metrics, diagnostic rules,
and source file names. It does not use an external search engine.

## Settings

Settings stores session-scoped preferences such as theme label, default replay speed, default report
format, preferred export directory, and demo defaults. It does not create user accounts or persist
profiles outside the Streamlit session.

## About

About shows package version, synthetic generator version, metric version, diagnostic ruleset
version, provenance schema version, Python version, commit hash when available, and licence status.
The licence remains not yet specified.

## Data-Mode Labels

| Label | Meaning in current prototype |
|---|---|
| `SYNTHETIC` | Repository fixture data, not real experiment output. |
| `IMPORTED` | A user-supplied historical bundle accepted by validation. |
| `HISTORICAL REPLAY` | Timestamp-driven replay over imported records. |
| `NEAR-LIVE` | Future unsupported mode. |
| `TRUE LIVE` | Future unsupported mode requiring real live source. |

## Standalone Demo Workspace

For a complete offline demonstration:

```bash
traffictwin demo initialise .demo
traffictwin demo launch .demo
```

The Home page will show a `Standalone Demo` section when the UI is launched through
`traffictwin demo launch`. Use the generated bundles under `.demo/bundles/` in the same pages as
ordinary imported bundles. The generated reports under `.demo/reports/` can be opened directly or
regenerated with `traffictwin report ...` commands.

Reset only with explicit confirmation:

```bash
traffictwin demo reset .demo --yes
```

Warnings:

- Standalone data is synthetic.
- Synthetic policy profiles are not real trained algorithms.
- The standalone demo does not enable direct launch, Randy/SUMO integration, or live data.

## Public Synthetic Dashboard

Create the static demonstration with:

```bash
traffictwin release stage-demo-site .demo --output public
```

Open `public/index.html` or deploy the directory through the included Netlify configuration. The
scenario selector displays existing precomputed synthetic metrics and diagnostic statuses. It is not
the Streamlit application and does not run calculations in the browser.

## Private TOS Supervisor Pack

On `TOS Training & Audit`, select a comparison campaign and press `Prepare private research
exports`. Download the supervisor ZIP to obtain reports, checksums, evaluation notes, and current
integration gates.

Keep this ZIP private until permission to share Randy-derived aggregate results is recorded. The
public TOS atlas command is intentionally separate and permission-gated.

Related documents:

- [Standalone demo](standalone_demo.md)
- [Demo script](demo_script.md)
- [Demo checklist](demo_checklist.md)
- [CLI reference](cli_reference.md)
- [Deployment](deployment.md)
- [Supervisor and viva pack](supervisor_pack.md)
- [Provenance Explorer](provenance_explorer.md)
- [Limitations and future work](limitations_and_future_work.md)
