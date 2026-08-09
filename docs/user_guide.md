# User Guide

TrafficTwin is an import-first Streamlit prototype. It supports repository-contained synthetic
fixtures, standard imported historical bundles, and optional read-only inspection of Randy's
separately supplied TOS Data result package. It can import bounded SUMO 1.27 tripinfo/summary
outputs, but it does not run Randy/VEC or SUMO and does not provide
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
- `tests/fixtures/sumo/square_public`

Before launching the UI, diagnose the active runtime without changing it:

```bash
traffictwin doctor
traffictwin doctor --workspace .traffictwin-demo
```

Use `--registry FILE` for immutable schema/integrity inspection or `--bundle PATH --cache-root
DIRECTORY` for read-only cache status. Missing optional tools and expected unsupported launch
capabilities stay visible but do not make the core generic import-first runtime unhealthy. A
blocked requested target returns exit code `1`. See [TrafficTwin doctor](doctor.md).

## Home / Project Status

Use Home to check:

- current phase label;
- registry path and counts;
- latest runs where a registry exists;
- capability manifest;
- prototype limitations.

Warning: direct simulator launch, live data, full Randy/VEC conversion, and SUMO FCD/other-output
integration are not implemented.
The generic adapter and TOS result reader both report direct launch as unsupported.

When no accepted Manchester scene is available, Home shows a static Greater Manchester
boundary context map (offline ONS December 2025 BGC Generalised 20m, E47000001/E08000003,
OGL-3.0, Contains OS data © Crown copyright 2025). The view is centred and fitted to the
study area with no basemap, no live traffic, and no provider telemetry. A caption states
“Static geographic context — no live or observed traffic scene is loaded.” If an accepted
Manchester scene exists, that scene takes precedence and the static fallback is not shown.
If the offline boundary asset cannot be loaded, Home falls back to a truthful text state.

Home includes visible actions for Guided Demo, Experiment Planner, and imported TOS results. These
actions are available in the main page content, so the first workflow does not depend on opening
Streamlit's sidebar on a phone.

## Guided Demo

Guided Demo presents two evidence tracks without introducing a second analysis pipeline:

- **Standalone synthetic** follows experiment planning, bundle validation, metrics, comparison,
  historical replay, diagnostics, provenance, and report export.
- **Randy/TOS imported simulation** follows package inspection, evaluation results, historical
  mobility/RSU replay, and training/reproducibility audit.

Select **Start guided workflow** once. TrafficTwin opens the real page for the first task and keeps
a compact guide above each subsequent page. A successful experiment-plan registration or report
regeneration completes its action stage and opens the next page automatically. Review-only stages
use one **Reviewed — continue** control after the researcher has inspected the requested evidence.
**Skip** is recorded separately and is never reported as completion; **Previous**, **Exit**, and
**Resume current task** preserve an honest, recoverable workflow.

Each stage shows its evidence input, deterministic operation, output, task instruction, and
interpretation boundary. The guide does not calculate metrics, evaluate rules, choose scientific
settings, launch a simulator, or manufacture evidence. It advances from accepted application
actions or explicit researcher review, never from a timer.

The standalone context reports workspace scenario, run, and comparison counts. When a local TOS
package is configured, the imported track reports its validated artifact inventory and package
fingerprint. An absent package remains an explicit unavailable state.

## Experiment Planner

Experiment Planner records a reproducible research design from seeds already stored in the active
registry. It does not run an algorithm, generate results, or launch a simulator.

Steps:

1. Select one registered baseline seed.
2. Select zero or more registered variation seeds.
3. Choose registered policy/algorithm labels or add explicit planning labels.
4. Enter the common non-negative random seeds that every condition should use.
5. Enter the research question and optional working hypothesis.
6. Select **Validate Plan** and review condition, policy, replicate, and planned-run-slot counts.
7. Inspect the bounded design matrix and deterministic seed-parameter differences.
8. Review the exhaustive **Execution Protocol** run slots and any checkpoint warnings.
9. Download the plan YAML, versioned protocol YAML, or CSV run sheet.
10. Select **Register Planned Experiment** when the design is ready.

Registration writes one `Experiment` with status `planned`. It deliberately creates no `Run`
records. A policy label is planning metadata and does not imply that TrafficTwin can execute that
policy. Use Experiment Manager to inspect the saved plan.

For an existing registered plan, use **Registered Protocol Export** to recreate the same protocol
or run sheet. **Match a completed bundle** first validates the selected directory/ZIP and then
reports `exact`, `compatible`, `mismatch`, or `unmatched`. This check is read-only: it neither
imports the bundle nor changes the experiment. Suggested run and bundle IDs are coordination
metadata, not proof that an external run used the intended configuration.

## Parameter Sweep

Parameter Sweep expands one strict synthetic preset over one to four closed scalar axes. Choose
`Local synthetic bundles + metrics` to create labelled fixtures and an ordinary core-metric
response surface, `Seed snapshots only` to stop after derived seeds, or `External requests` to
write coordination artifacts that remain visibly not executed.

Enter comma-separated scalar values for each enabled axis, select response metrics only in local
mode, choose an exact output directory, and select **Build Parameter Sweep**. Review every point's
assignments, seed, bundle fingerprint or execution state, then download the typed JSON and CSV.
The hard limit is 256 complete points. Broad/protected or symbolic-link destinations are refused,
and replacement requires explicit confirmation. No mode launches Randy, VEC/TOS, SUMO, or training. See the
[parameter sweep guide](parameter_sweeps.md) for the CLI and full contract.

## Scenario Mutations

Scenario Mutations creates a separate synthetic/evaluation bundle with exactly one controlled
change. Select a valid labelled source bundle, choose row dropout, bounded timestamp jitter, or an
exact RSU ID to remove, review the complete plan, choose an output directory, and select
**Build Mutated Scenario**. The page shows validation, parent/derived fingerprints, every changed
row and file, and a downloadable mutation manifest.

The source is never edited. Row and timestamp choices are reproducible from the declared seed.
RSU removal does not reroute tasks or rewrite their target IDs. Imported/raw evidence, compressed
or Parquet mutation targets, source/destination symlinks, protected destinations, and changes above
the exact-ledger bound are refused visibly. This page launches no simulator. See the
[scenario mutation guide](scenario_mutations.md) for request examples and limits.

## Scenario Builder

Scenario Builder creates deterministic synthetic scenario configurations and can generate standard
TrafficTwin run bundles from those configurations.

For a controlled observation-robustness fixture, enable **Synthetic measurement imperfections**,
set a separate measurement seed, and enter at least one bounded error or observation-row dropout
fraction. Preview shows an impairment-qualified bundle/run ID. Generation embeds the exact field
and dropout audit in the ordinary synthetic manifest. These controls do not change clean task,
trip, incident, timestamp, outcome, or routing rows and are not calibrated sensor behavior. See
[Synthetic measurement noise and dropout](measurement_imperfections.md).

Steps:

1. Choose an existing synthetic preset to duplicate.
2. Edit documented generator parameters such as vehicle count, trip count, congestion multiplier,
   RSU count, RSU capacity, task-arrival rate, task mix, random seed, and synthetic policy profile.
3. Review validation errors from `SyntheticScenarioConfig`.
4. Review the expected bundle ID, run ID, and file list.
5. Optionally configure bounded EXP-03 observation noise/dropout and review its fingerprint.
6. Download the generator configuration YAML or generate a bundle directory.
6. Validate the generated bundle through the normal import-first workflow.

The builder exposes only the current synthetic generator model. It does not launch Randy, SUMO, or
any live data source.

## What-If Studio (V2-S1)

What-If Studio provides the V2 one-click what-if pair orchestration. It reuses the existing
synthetic generator and ordinary validation/registry services. It does not run SUMO, VEC,
a provider feed, or an admitted research campaign.

Evidence: every surface is labelled **SYNTHETIC / DETERMINISTIC / LOCAL** and explicitly
**not** Manchester observation, not a live traffic forecast, not SUMO/VEC execution, and not
research admission. The banner states: “This studio generates a deterministic synthetic
baseline and intervention through TrafficTwin’s local generator. It does not run SUMO, VEC,
a provider feed or an admitted research campaign.”

Distinction: **What-If Studio** creates validated baseline/variation bundles (software
evidence) and registers the pair for Compare. **Platform → What-If Composer** predicts from
a bounded surrogate fit and drafts unsigned research campaigns; it cannot approve or execute.

Journey:

1. Choose an existing synthetic preset as the baseline.
2. Define an intervention from the closed set: incident/event enabled/type/location/start/duration/lanes/demand multiplier, congestion/demand multiplier, vehicle count, task arrival rate and T1/T2/T3 mix, RSU count/capacity, and synthetic policy profile.
3. Review the deterministic changed-parameter ledger (canonical field paths, lexical ordering, baseline and variation values, no unchanged rows, no LLM prose).
4. Click **Generate comparison** — the service stages outside final locations, generates both bundles, validates both through the ordinary path, confirms pair compatibility (same experiment identity, variation links to baseline via `baseline_seed_id`, unique scenario IDs, same reproducibility seed unless deliberately changed), publishes both only when the complete pair succeeds, registers both, and sets `selected_bundle_path`, `selected_baseline_run`, `selected_variation_run` plus a small typed receipt for V2-S2.
5. Inspect the success receipt (pair ID `whatif-<name>-<short-digest>`, request/pair fingerprint, baseline/variation IDs, validation standing, synthetic/evidence labels) and continue to **Compare**, baseline **Run Overview**, or variation **Run Overview**.

Transaction and idempotency: the pair is one product transaction. On any failure (generation, validation, compatibility, publish, or registration) no partial bundle or registry state remains, staging is removed, unrelated data is preserved, and a typed user-readable failure is returned. No broad destructive overwrite is enabled. Path safety uses `pathlib`-aware resolved containment checks, not string prefixes. An exact retry returns the verified existing pair; the same sanitised pair ID with changed content refuses; an existing unrelated non-empty destination refuses; a corrupt/partial pair is not treated as success. Pair fingerprints are deterministic; no absolute private path enters a publication-safe receipt.

Supported intervention fields are intentionally bounded (general congestion/demand, vehicle count, task arrival rate and T1/T2/T3 mix, RSU count/capacity, synthetic policy profile, incident/event controls). Traffic-light programmes, alternative-route optimisation, real provider feeds, learned forecasting, cloud controls, or generic SUMO execution are not part of this slice.

Limitations: consequence lenses, Portfolio Explorer, Manchester calibration, provider activation, research admission, and formal user evaluation remain separate gated tracks and are not performed here. The existing Compare page is the first downstream result surface.

## Bundle Import & Validation

Use this page to validate a bundle path without pretending that rejected data is usable.

The ordinary bundle path accepts manifest-declared plain CSV, gzip-compressed CSV, and flat scalar
Parquet files. The Declared Files table shows `format` and `compression`; filename suffixes are not
auto-detected. A bundle may mix representations, and all use the same mappings, units, checksums,
canonical records, metrics, and provenance flow. See the
[declared tabular input guide](integration/tabular_formats.md) for manifest examples and limits.

Steps:

1. Enter a bundle directory or ZIP path.
2. Click validate.
3. Review manifest summary and declared files.
4. Review validation counts and findings.
5. Review evidence availability.
6. Import only accepted or warning-level bundles.

Findings include stable code, severity, file, row, field, message, affected capabilities, and whether processing may continue.

Warning: a rejected bundle must not be used in Run Overview, comparison, evidence, or diagnostics as if it were valid.

For several completed bundles, expand **Batch validate or import**, enter one explicit path or glob
per line, and choose **Validate Batch** or **Import Accepted Batch**. The summary shows input issues
and one outcome per candidate, and can be downloaded as JSON. One invalid or conflicting candidate
does not stop a valid neighbour. Batch import registers metadata only; it does not automatically
compute/store each bundle's metrics or EvidencePack. See the
[batch import guide](integration/batch_bundle_import.md) for limits, status, and privacy guidance.

For one large generic bundle, enable **Use chunked canonicalisation for a large bundle**, choose a
row bound, then use **Stream Validate** or **Stream Validate & Import**. The summary reports source
rows, canonical counts, chunks, and observed byte/row bounds. Import stores metadata only; full
metrics require an explicit downstream path that can retain or accumulate the accepted records.
See the [streaming canonicalisation guide](integration/streaming_canonicalisation.md).

For repeated ordinary analysis of one unchanged accepted generic bundle, the CLI can keep derived
canonical tables in an explicit cache directory outside the bundle. Run `traffictwin bundle
cache-validate BUNDLE --cache-root CACHE` once to publish, then again for a verified hit. Every hit
still re-hashes raw evidence; stale/incompatible/corrupt entries are reported and never used or
overwritten. This is currently a CLI/library operational path, not a Bundle Import page control.
See [canonical-table caching](canonical_table_caching.md).

## Archive A Run For Citation And Reuse

Create and verify a private reference-only research object:

```bash
mkdir -p build
traffictwin archive create path/to/completed-bundle build/run-ro-crate.zip \
  --publication-date 2026-07-21 \
  --raw-evidence reference
traffictwin archive verify build/run-ro-crate.zip
```

Use `embed` only for synthetic or explicitly permitted imported evidence. Use `exclude` when raw
names/hashes must not be disclosed. A public imported embed/reference requires confirmed
permission, its written basis, and a raw-evidence licence. See
[RO-Crate research objects and citation](research_objects.md).

## Manifest Inference Wizard

Use this page when CSV headers do not already match TrafficTwin's generic manifest fields.

1. Enter the directory containing the unchanged CSV files.
2. Inspect the source/draft fingerprints, bounded inference limits, and findings.
3. Include or exclude each CSV and review the selected file kind.
4. Review/edit canonical columns. Required mappings are labelled.
5. Select any unit that is not evidenced by a supported header suffix.
6. Enter a non-sensitive name/role label and acknowledge the review.
7. Confirm and download `canonicalisation.yaml` plus the manifest file fragment.
8. Optionally supply a complete metadata template and download `manifest.yaml`.
9. Place that manifest beside the unchanged CSV files and required `seed.yaml`, then use **Bundle
   Import & Validation**.

A displayed score orders exact-header, alias, and value-pattern evidence; it is not confidence or a
probability. Tied file kinds begin with no selection. The wizard does not import data, run metrics,
infer physical units from numeric magnitude, or invent run/environment metadata. See the
[complete manifest inference contract](integration/manifest_inference_wizard.md).

## Discover And Inspect External Sources

Before using a SUMO or TOS-specific workflow, the OPS-05 CLI can identify the reviewed adapter and
show its exact evidence boundary:

```bash
traffictwin integration external discover path/to/source
traffictwin integration external inspect path/to/source --deep --format json
```

Proceed only from `one_match`. A no-match remains unknown, an ambiguous mixed-marker package needs
an explicit human-owned adapter choice, and symbolic-link markers are blocked. In the inspection,
read validation and `accepted_for_declared_import` together with the exact conversion outputs,
unknown provenance, and blockers. A matched/accepted TOS aggregate summary is still not a canonical
task bundle; a matched/accepted SUMO package still does not provide FCD or canonical traffic flow.
See the [general external-source contract](integration/external_source_contract.md).

## SUMO Output Import

The page now begins with **Controlled one-click SUMO run**: pick the closed
`synthetic_square_smoke` preset, review the discovered SUMO readiness and factual workload,
enter a new output directory, confirm the synthetic run, and press **Validate, Run and
Import**. TrafficTwin preflights, runs SUMO in the foreground with a fixed argv, verifies
the pinned inputs stayed byte-identical, and validates plus imports the outputs through the
ordinary adapter below. If no supported SUMO 1.27.x binary is installed the exact reason is
shown and the button stays disabled (install with `brew install sumo` yourself; TrafficTwin
never installs software or substitutes a fake process). **Imported controlled SUMO execution
records** lists registered runs from the registry and survives restarts. Results are
synthetic evidence only. See the
[controlled SUMO guide](integration/sumo_controlled_execution.md).

Use this page for an existing SUMO 1.27 result directory containing `sumo-source.yaml`,
`tripinfo.xml`, and `summary.xml`.

1. Enter the result-directory and registry paths.
2. Inspect source URL, version, licence, retrieval date, redistribution declaration, and raw hashes.
3. Review incomplete/undeparted trip findings and the source-specific summary charts.
4. Check deterministic canonical trip metrics.
5. Select **Import SUMO Results** only after validation is accepted.

The page never launches SUMO. Summary `running` is network occupancy, not a canonical interval
traffic count. FCD stays unavailable until a separate mapping is approved.

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

## VEC Reproduction Workbench

The Workflow section's **VEC Reproduction Workbench** drives the capability-gated Randy/VEC
services. Section 1 inspects both pinned external repositories. Section 2 is the one-click
controlled execution: pick one closed preset (`smoke_two_step` or `full_reproduction`), keep the
audited input root, enter a new output directory and the active registry path (pre-filled from
the configured registry), confirm the long run when required, and press **Validate, Run and
Import**. TrafficTwin then preflights, executes the exact audited evaluator in the foreground,
revalidates every published byte, verifies both external repositories and the raw trace are
unchanged, and imports one immutable structural record idempotently. Failed or mutated runs
import nothing. Sections 3-5 keep the typed request/receipt, inspection, comparison, and export
workflows. Expand **Imported VEC execution records** in section 2 to inspect persisted imports;
Experiment Manager also lists their `vec:exec:...` run rows. Run Overview remains limited to
canonical bundles and therefore does not invent metric cards for these structural records.
Scientific admission remains explicitly unavailable for local executions. See the
[one-click guide](integration/vec_one_click_execution.md) for click-by-click detail, CLI
equivalents, idempotency, and limitations.

## Reading Validation Findings

Severity meanings:

- `info`: context only.
- `warning`: import may proceed, but downstream evidence may be limited.
- `error`: invalid data or metadata; import may proceed only when the finding says it may continue.
- `fatal`: validation cannot safely continue.

Unavailable evidence is not the same as zero. It means the required source table or field is absent, invalid, or not declared.

## Experiment Manager

Experiment Manager is a read-only organisational page for browsing local project state. Its
**Create Experiment Plan** action navigates to Experiment Planner; the manager itself does not edit
records.

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

Choose the **Replay dataset** first. The selector lists validated top-level bundles and reports the
number of distinct vehicles and incident records in each. In the standalone demo, Replay initially
uses **Stressed Demand**, which contains both vehicle and synthetic-incident evidence; choose
**Baseline** when an incident-free reference is needed.

The replay clock filters imported timestamps. It does not consume wall-clock live data. If
coordinates are absent, the UI shows time-series and tables rather than fabricating a map.

Controls include play, pause, resume, restart, timestamp jump, scrubber, speed presets, step
forward/back, and filters for vehicle, RSU, task class, and incident type where evidence exists.
Vehicle has a direct button grid plus **Previous**, **Next**, and **Clear** controls; the active
vehicle is confirmed above the grid. Current 60-second counts are displayed as metric cards so
filter changes are immediately visible. This avoids relying on a long dropdown on small screens.
Changing the replay dataset resets its clock and filters. A filter is disabled only when the
selected validated bundle contains no matching evidence.

## Run Overview

Run Overview displays metric cards and charts for accepted bundles:

- tasks generated and completed;
- completion and incomplete rates;
- observed completed-task deadline-miss rate;
- latency P50/P95/P99;
- mean energy per observed task, mean energy per completed task, and mean completed-task
  energy-delay product when the bundle declares a compatible task-energy contract;
- offload rate;
- decision shares;
- class breakdown;
- provenance and validation status.

Unavailable metrics are shown as unavailable with reason codes. They are never shown as zero.
The **Energy Evidence** cards also show eligible-row coverage and the semantic-contract
fingerprint. Missing energy values are excluded, negative values reject the bundle, and runs with
different fingerprints are not compared. SUMO and TOS imports currently keep this canonical
family unavailable; the TOS per-arrival aggregate is intentionally separate.

## Temporal Metrics

Temporal Metrics computes all 60 current window-applicable task, infrastructure, traffic, trip,
energy, fairness, and contracted spatial/per-RSU metrics over a selected validated bundle. Choose
a positive window width, alignment origin,
optional explicit range, and whether clipped edge windows are included or excluded, then select
**Compute Windowed Metrics**.

Windows use `[start,end)`: a record on the end boundary moves to the next interval. Tasks are
assigned by arrival cohort, trips by departure cohort, and observation tables by timestamp. Empty
windows remain visible with unavailable values; coverage is requested-range overlap and does not
assert complete sampling. Download the JSON artifact to preserve the exact contract. For CLI,
Python, provenance, and interpretation examples, see
[Time-windowed metrics](time_windowed_metrics.md).

To evaluate R6 on the computed series, select an eligible scalar metric with a declared
better/worse direction. Optionally enter a known event time/label, inspect the provisional
baseline, deterioration, sustained, tolerance, and horizon settings, then choose **Evaluate R6**.
The result shows the exact baseline/episode/recovery ordinals, temporal fingerprints, findings,
and unavailable reasons. Gaps break runs; the page does not infer an event or causal relationship.
See [Temporal diagnosis](temporal_diagnosis.md).

## Energy Evidence

Energy Evidence shows the three `MET-03` task-energy outputs together with their exact semantic-
contract fingerprint, eligible/population counts, and coverage. The page evaluates R8 through the
library service using an explicit provisional energy boundary and completed-task support minimum.

Missing, partial, non-finite, mixed-unit, contract-incompatible, or denominator-inconsistent energy
remains unavailable and is never treated as zero. Treat R8 as a single-run candidate only: it is
not a statistical anomaly test, hardware benchmark, causal diagnosis, efficiency standard, or
energy-saving recommendation. See [R8 energy diagnosis](energy_diagnosis.md).

## Verified Nearest Flip

Use the CLI when an R5, R7, or R8 result is `not_triggered` and you need the exact supported
single-threshold boundary:

```bash
traffictwin diagnose nearest-flip path/to/bundle R8 --format json
```

The artifact keeps pair/group/task support unchanged and re-runs the ordinary rule engine at the
candidate boundary. `unsupported` means the rule has no v1 single-axis contract;
`not_applicable` means the source status, enabled state, evidence, or discrete support is
ineligible. See [nearest-flip analysis](nearest_flip_analysis.md).

### Explore complete threshold sensitivity in the UI

Open **Threshold Sensitivity** under **Analysis** after selecting a validated bundle. Choose R5,
R7, or R8, declare inclusive bounds and 2–51 UI grid points, then select **Run Threshold Sweep**.
The page shows every evaluated status, trigger stability, sampled transition intervals, and the
exact DIA-05 boundary when admissible.

All defaults are labelled provisional. Changing a control does not update a rule default. Use the
configuration expander to explicitly apply a complete `RuleSetConfig` JSON for the current session
or download the current/selected-point complete config. The registry, repository, source bundle,
and raw evidence are never changed by exploration. See
[threshold-sensitivity explorer](threshold_sensitivity_explorer.md).

## Infrastructure & Congestion

This page uses `infra_state` evidence where available:

- queue length over time;
- utilisation over time;
- per-RSU summaries;
- saturation episode count;
- saturation duration;
- Jain load-balance availability and maximum per-RSU load gap.

The saturation threshold is a configurable demo threshold, default `0.90`. It is not a validated research threshold.

## Fairness Evidence

Fairness Evidence shows the six operational group-balance outputs when the selected bundle has
sufficient canonical evidence: completion rate by stable vehicle tier, its maximum gap and Jain
index, and capacity-normalised load by exact RSU, its maximum gap and Jain index. Choose a
validated bundle on the page; the cards and group tables use the ordinary deterministic metric
collection and expose support, coverage, and policy identity.

The fixed v1.0 admission policy requires at least two groups, two eligible observations in every
observed group, and complete coverage. Missing/unstable vehicle tiers or incomplete RSU capacity
and active-task evidence therefore show **Unavailable** with a reason rather than zero. Vehicle
tier means an operational resource category only. A small gap or high Jain index does not prove
good performance, protected-attribute fairness, or causality. Current SUMO and TOS imports do not
satisfy this family and remain visibly unavailable.

The same page includes **R7 Operational Outcome Disparity**. Select exactly one vehicle-tier or
exact target-RSU completion dimension, a provisional gap threshold, and minimum group support.
The library returns a normal rule result with findings, missing evidence, alternatives,
limitations, and definition/configuration metadata. The UI does not calculate the result. Treat
R7 as an operational candidate only; it is not protected-attribute fairness, geography,
significance, or causality. See [R7 diagnosis](fairness_diagnosis.md).

## Spatial & RSU Evidence

Spatial & RSU Evidence combines exact V2I execution-target outcomes with contracted vehicle-grid
summaries. The per-RSU table shows targeted V2I task counts, completion rates, completed-observed
deadline-miss rates, and compatible capacity-normalised load when present. The grid table shows
vehicle observations, distinct vehicle IDs, and mean speed per fixed source-frame cell.

These outputs appear only when the bundle explicitly declares the relevant contract. Per-RSU task
outcomes require a non-empty exact target for every V2I task and an in-scope matching canonical
RSU. Grid outputs require a named metre-based source frame, fixed cell geometry, and finite x/y for
every vehicle observation. Missing target/coordinate evidence makes the family unavailable;
missing latency or speed support remains partial/null. Do not interpret cells as a geographic map,
assign tasks to the nearest RSU, or treat target grouping as causal attribution. Current SUMO/TOS
contracts remain unavailable.

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
- selectable difference provenance over both complete accepted-row ledgers. Direct additive
  formulas show reconciled signed terms; percentiles and other non-decomposable scalar metrics show
  eligible lineage without weights. JSON/CSV downloads retain the non-causality statement.
- a bounded provenance graph tab for metric, rule, and run traces, with safe/structure-only
  disclosure, exact omission counts, node inspection, and DOT/GraphML downloads.

Warning: TrafficTwin does not automatically label a change as better or worse unless a metric definition safely supports that interpretation. Current comparison wording is descriptive.

## Journey-Time Lens

Journey-Time Lens uses imported trip records, not live journey-time prediction.

It shows:

- total trip records;
- completed and incomplete trip counts;
- duration mean/P50/P95/min/max;
- distribution and comparison where available.

Use labels such as synthetic trip duration or imported trip duration. Do not interpret fixture outputs as real Manchester journey-time predictions.

## Consequence Lenses

Consequence Lenses projects existing deterministic comparison evidence into two curated views. It does not create new scientific metrics, rerun a simulator, or claim causality.

**Journey:** select or generate baseline and variation → open Consequence Lenses → verify pair compatibility and identity → inspect Traffic consequences → inspect VEC consequences → inspect unavailable evidence and denominators → continue to full Compare → inspect Provenance → open Reports. The page works now with committed example baseline/variation, demo-workspace bundles, or any compatible pair selected through the current product. After the What-If Studio is available, its generated pair will populate the same stable session keys (`selected_baseline_run`, `selected_variation_run`) and open automatically.

**Traffic consequences:** trip cohort and incomplete journeys (total records, completed, incomplete, completion rate), mean/P50/P95/min/max duration where available, traffic count and speed evidence (observation count, total/mean count, mean/P50/P95/min speed, sensor count, time coverage), and changed scenario parameters when available in the validated manifest/comparison.

**VEC consequences:** task population and denominators (generated/completed tasks, completion/incomplete rates, deadline-miss rate over completed tasks with observed latency), latency (count, mean/P50/P95/P99 with support), decisions/offloading (local/V2I/V2V/unknown shares, offload rate, decision counts, drops by cause where scalar), infrastructure (observed RSU count, queue mean/max, utilisation mean/P95, saturation episodes/duration, load balance and fairness where available, per-RSU or spatial support), and contract-gated energy (mean per observed task, per completed task, energy-delay product).

All rows retain exact baseline/variation values, absolute delta (Variation − baseline), relative delta where already supported by the comparison engine, unit, status, and reason codes. Relative delta is unavailable when the baseline is zero, with `BASELINE_ZERO` and `partial` status. Rates identify their denominator explicitly, for example “Completed valid tasks / generated valid tasks” for `task.completion.rate` and “Completed trips / total trip records” for `trip.completion.rate`. Completion among all offered tasks is not conflated with conditional completion among admitted tasks. Missing or partial evidence is kept unavailable, never zero-filled; unavailable rows show exact reason codes and missing-evidence findings. Energy metrics require an explicit compatible task-energy contract, otherwise they remain unavailable with `COMPARISON_PAIR_INCOMPATIBLE`.

**Evidence wording:** “These are deterministic consequences observed in the selected imported or synthetic runs. They are not a live Manchester forecast or proof that the intervention caused the difference.” and “These are deterministic VEC outcomes for the selected runs. They do not prove that an algorithm, RSU placement or infrastructure intervention caused the difference.” No forecast, route recommendation, queue-clearance estimate, causal effect, live traffic claim, or optimal-policy claim is made.

**Navigation:** the page is in **Results**, close to Journey-Time Lens and Compare. Use the actions to open full Compare, baseline/variation Run Overview (via Bundle Import selection), Provenance, or Reports. Compatibility shows same experiment, same random seed, metric version, synthetic/unknown standing, and warnings; an incompatible pair withholds misleading deltas. The report fingerprint and changed-parameter ledger are deterministic and downloadable as JSON.

## Diagnostics & Evidence

This page displays:

- validation summary;
- evidence availability;
- EvidencePack ID/fingerprint;
- rule status for R0-R8;
- triggered candidate hypotheses;
- insufficient rules;
- conflicting evidence;
- typed cross-rule conflict, corroboration, and suppression records;
- exact shared evidence keys and explicit precedence;
- suppressed-for-action and unclassified triggered IDs, while every original RuleResult remains
  visible;
- alternatives;
- missing evidence;
- conditional recommendations;
- DiagnosticReport JSON download.
- CrossRuleReasoningReport JSON download.

Warning: these are deterministic, evidence-based diagnostic hypotheses. They are not proven root causes and should be verified through controlled follow-up experiments.

The cross-rule section does not rank causes or change confidence. R1/R2 conflict chooses no winner;
R1/R4 corroboration records compatible context only; R0 suppression means a retained result is not
actionable until its evidence blocker is repaired. See
[deterministic cross-rule reasoning](cross_rule_reasoning.md).

## Triviality And Portfolio Research

Open **Triviality** after a registered experiment has stored metric collections. Select the
experiment, primary scalar metric, objective direction, and—when genuine matched data exists—equal
ordered lists of training and validation runs to inspect:

- the reusable experiment EvidencePack;
- R3 scenario-triviality status;
- R5 status and the exact compatibility-checked pair evidence;
- a per-seed policy winner map with rank and regret;
- the default transparent synthetic portfolio decision and descriptive regret;
- for `exp-synthetic-portfolio-study`, the fixed three-family development and S5/S6 held-out
  evaluation plus every constituent's held-out result.

These policy profiles and selector rules are synthetic demonstrations. Use the JSON downloads for
reproducible review, not as evidence of trained-policy performance.

Experiment Manager can initialise manual tracking for a registered protocol and advance slots
through `planned`, `received`, `validated`, `matched`, and `complete`, or mark them `rejected`.
Tracking records external progress only; TrafficTwin still launches nothing.

Scenario Builder includes incident/event type, location, severity, timestamp, duration, lanes
closed, demand multiplier, and vehicle references. It can export a linked incident-seeded what-if
configuration. The synthetic preset catalogue includes S5 stadium-event/RSU-siting and S6
road-clearing/lane-closure workflows. Generated outputs remain synthetic fixtures.

## Manchester Evidence Hub (V2-M1)

Manchester Evidence Hub provides a supervisor-readable source inventory and activation readiness
view over existing Manchester integration contracts. It does not invent a new acquisition path,
does not fetch network data on render, and does not decide scientific policy.

Each source retains its exact semantics:

- **DfT**: historical traffic counts (not live).
- **WebTRIS**: historical/latest per accepted contract (not casually live).
- **BODS**: live/recent BUS positions, bus-only (not general traffic, not Manchester-wide flow).
- **National Highways**: strategic-road operational evidence (not Manchester city-road coverage).
- **TfGM**: infrastructure/reference unless telemetry has been supplied and accepted (not live traffic telemetry).
- **Static ONS boundaries**: geographic context only (not traffic evidence).
- **Manual incident**: AUTHORED SCENARIO INPUT via Scenario Builder (not an observation).
- **Social media**: deferred — no ingestion.

The hub separates six readiness dimensions per source, each machine-typed:

* **Software support** — does TrafficTwin have code for this source?
* **Acquisition readiness** — can acquisition be attempted under current config?
* **Local evidence** — is qualifying local evidence actually present?
* **Rights / retention** — what authority is recorded?
* **Scientific gate** — is this usable for the gated Manchester scientific path?
* **Freshness** — what freshness category applies (authoritative FreshnessTruthState)?

The hub shows per-source freshness (historical, near_live, live_vehicle, stale, unavailable,
synthetic), configuration (Configured / Not configured), local accepted evidence, acquisition
readiness, rights/retention (NOT RECORDED / OWNER DECISION REQUIRED unless explicitly recorded),
and scientific gate state (BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED for map matching,
ambiguity threshold, road-class, calibration objective, parameter bounds, uncertainty, 174
map-review decisions, viable demand — not implemented here). No API key or Bearer [REDACTED] is
displayed; only Configured / Not configured.

Use **Open Manchester Operations** for detailed source use and explicit acquisition controls,
and **Open Scenario Builder** for manual incident authoring. The hub is offline by default and
works with no workspace and no credentials, showing empty-state readiness and next actions.

Fingerprint binds source IDs, source roles, evidence type, evidence ceiling, coverage, freshness,
software support, acquisition readiness, local evidence, rights/retention, scientific gate, blocker
codes and next-action class (no secrets, no paths, no wall clock) via a canonical portable payload;
identical logical state yields identical fingerprint, cosmetic wording does not change counts.

Presentation consistency: typed states are machine truth and determine counts, filters and
fingerprint. Human-readable detail strings are not identity-bound but must not contradict the
typed state — e.g. a BLOCKED scientific gate must not claim APPROVED, and an UNAVAILABLE local
evidence must not claim accepted live evidence. Contradictory prose is rejected by model validation
before export; consistent paraphrase validates and leaves fingerprint unchanged.

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
3. Expand **Report claim provenance completeness (PRO-03)** and choose `run` or `diagnostics` to
   inspect the exact claim denominator, class counts, score, exclusions, and full claim table.
4. Choose `Metric`, `Diagnostic rule`, `Source file row`, or `Run metadata` for an individual
   trace.
5. Inspect trace completeness, lineage, grouped nodes, source-row previews, and validation context.
6. Download trace or report-completeness JSON/CSV/Markdown as appropriate.

Warnings:

- Provenance supports auditability; it does not prove real-world causality.
- Aggregate metrics show eligible input rows and exact counts, not per-row causal weights.
- EvidencePack-only fault-injection traces cannot inspect source rows unless a source bundle exists.
- Source-row previews are bounded and read-only.
- The PRO-03 score measures accepted-row lineage for one named report template. Unavailable claims
  stay in its denominator; it does not measure truth, causal validity, or rejected raw-row yield.

## Downloading JSON

The UI can expose:

- EvidencePack JSON;
- DiagnosticReport JSON;
- ProvenanceTrace JSON and Markdown;
- ProvenanceCompletenessReport JSON and complete claim-inventory CSV;
- validation/metric data through CLI commands.

These JSON documents are useful for reproducibility, tests, and dissertation appendices.

## Reports

Reports lists deterministic JSON, Markdown, HTML, PDF, LaTeX, and SVG report/export artifacts in the
active workspace.

You can:

- search reports by name, type, format, or scenario hint;
- download existing reports;
- deliberately regenerate a selected report from explicit bundle paths.
- export existing metrics, comparisons, STA-01 studies, or diagnostic results as escaped `.tex`
  tables with an optional deterministic SVG/PDF figure.
- append a bounded analyst note/decision to a typed artifact target, inspect immutable ordered
  history, and opt into a visibly separate annotated report section.
- compare two compatible saved structured report JSON payloads and download exact JSON or
  non-causal Markdown section/claim classifications.
- render one compatible saved report as a bounded supervisor summary with complete availability,
  warnings, limitations, and provenance links, downloadable as one-page PDF, HTML, Markdown, or
  JSON.
- search six local research-record categories through a deterministic read-only, path-redacted
  lexical index built on demand.

Reports are never regenerated automatically. Report content comes from `traffictwin.reporting`, not
from Streamlit page logic.

For a research table, choose the artifact family in **LaTeX research export**, enter the explicit
source and destination paths, optionally choose SVG or PDF, and select **Generate research
export**. Comparison requires a second bundle; Statistical study requires an existing saved STA-01
JSON artifact. Existing destinations require deliberate overwrite. Both outputs show the same
projection fingerprint and preserve source mode, warnings, units, availability, and rule status.
See [LaTeX research tables and static figures](latex_research_exports.md).

For human review context, use **Analyst Annotations (REP-02)**. Select the closed target type and
path-free identifier, add an optional exact fingerprint, declared author label, decision label,
and note, then choose **Append Analyst Annotation**. Earlier entries cannot be edited or deleted;
append a correction instead. Enable **Include matching append-only analyst annotations** during
report regeneration. These entries remain outside computed findings and claim counts. See
[analyst annotations](analyst_annotations.md).

For report-version review, regenerate the same report type twice using `.json` output paths. Under
**Structured Report Diff (REP-03)** choose the baseline and variation JSON files, then select
**Compare Structured Reports**. The table shows unchanged, added, removed, changed, or unavailable
sections; downloads retain exact typed claim paths and values. Narrative, layout, timestamps,
warnings, commands, labels, and annotations are not scientific diff inputs. See
[structured report diffing](structured_report_diffing.md).

For supervisor review, save or select one current typed report JSON. Under **One-page Executive
Summary (REP-04)** enter that path and choose **Generate One-page Executive Summary**. The result
shows complete claim availability, the deterministic five-slot highlight selection, the number of
claims outside the highlights, every warning and limitation, and fingerprinted source/claim links.
Download PDF, HTML, Markdown, or JSON. PDF generation refuses content that needs a second page; it
never deletes caveats. See [one-page executive summary](executive_summary.md).

## Search

Search covers findings, append-only annotations, report metadata/text, runs, experiments, and
evidence references. Enter up to 16 terms, select one or more clearly labelled categories, and set
a result limit. Every term must match after Unicode normalisation and absolute-path redaction.
Results show deterministic rank, lexical score, bounded snippet, typed reference, inventory and
omission counts, redaction count, and exact fingerprint. The score is not severity, confidence,
importance, causality, or approval.

The registry is opened read-only and no persistent search index is created. Only bounded direct
non-symlink files under `workspace/reports` are inspected; PDF body text, raw bundle rows, nested
files, and external services are excluded. See [full-text registry search](registry_search.md).

## Registry Maintenance

Before upgrading a valuable workspace, make an independent copy of its SQLite registry. Use
`traffictwin registry migration-status PATH` for a strictly read-only version, ledger, and
integrity check. Use `traffictwin registry migrate PATH` to apply all pending ordered changes in one
transaction. A failure rolls back the whole invocation; a completed target is a byte-idempotent
no-op. TrafficTwin refuses unknown objects, malformed/tampered schemas, future versions, and
downgrades rather than silently repairing them. See
[registry schema migrations](registry_migrations.md).

## Settings

Settings stores session-scoped preferences such as theme label, default replay speed, default report
format, preferred export directory, and demo defaults. It does not create user accounts or persist
profiles outside the Streamlit session.

## About

About shows package version, synthetic generator version, metric version, diagnostic ruleset
version, provenance schema version, Python version, commit hash when available, and licence status.
It also states the custom-metric trust boundary: explicit local registration, two-run repeatability
checking, isolated failures, no uploads, and no sandbox. The licence remains not yet specified.

## Statistical Study

Use **Analysis → Statistical Study** only after an experiment plan and its completed
`MetricCollection` results are in the active registry. Select the exact baseline, variation,
algorithm, checkpoint, metric, objective, common-seed set, and resampling settings, then choose
**Evaluate paired study**. Review exclusions before interpreting the effect. The page shows the
signed original-unit mean, paired-bootstrap interval, sign-flip test, paired effect sizes,
assumptions, limitations, and deterministic JSON/Markdown/CSV downloads.

The page cannot run an experiment, recompute metrics, infer a missing replicate, choose a compatible
subgroup, prove causality, invent a practical margin, or convert synthetic evidence into external
validation.

Select **N-way policy ranking (STA-02)** on the same page to compare two or more registered
policies independently within each selected scenario family. Every policy uses the same complete
common-seed rows. Review missing/incompatible seeds, the numerical tie tolerance, mean interval,
rank frequencies, and top-rank frequency before interpreting the order. Download the typed
JSON/Markdown/audit CSV. Full methods and command examples are in
[paired statistical studies](statistical_studies.md) and [N-way policy ranking](n_way_ranking.md).

Select **Paired equivalence TOST (STA-03)** only after choosing a defensible original-unit margin
before inspecting the result. Declare its practical, literature, or explicitly provisional basis,
write the justification, supply a reference for literature, and choose alpha. Review both
one-sided p-values, the corresponding Student-t interval, conclusion, and inherited STA-01 audit.
An available failed result means equivalence was not demonstrated; it does not prove difference.
See [paired equivalence testing](equivalence_testing.md).

Select **Versioned regression gate (STA-04)** to evaluate a committed golden without changing it.
Upload the candidate or approved JSON. Metric contracts select a registered run; paired-study
contracts use the current STA-01 session result. Review approval status, source policy, every
expected/actual/error/tolerance row, ignored fields, blocking findings, and fingerprints. A pass
covers only declared assertions; fail means a complete scalar exceeded tolerance; unavailable
means the contract could not make its declared comparison. Download JSON/Markdown/CSV. Generate
and deliberately approve goldens with the CLI described in
[versioned regression gates](regression_gates.md).

Select **Power analysis helper (STA-05)** before confirmatory results are inspected. Declare the
metric/unit, signed target effect, prospective paired-difference variance, two-sided alpha, target
power, input bases, justifications, references or pilot size, synthetic state, and search ceiling.
Review the required common-seed pairs, total baseline-plus-variation runs, achieved and preceding
approximate power, labels, warnings, assumptions, and provenance. This is a prospective planning
aid—not guaranteed achieved power or evidence about a completed study. Download deterministic
JSON/Markdown/CSV. See [paired common-seed power analysis](power_analysis.md).

## Trusted Custom Metrics For Developers

Researchers can register reviewed local deterministic functions through the Python
`MetricPluginRegistry` and pass that registry explicitly to whole-run, bundle, window, evidence,
SUMO canonical-trip, or provenance services. This is a developer API rather than an upload form.
Inspect its machine-readable boundary with:

```bash
traffictwin metrics plugin-api --format json
```

The contract must declare canonical inputs, missing-row policy, minimum support, unit, scope,
version, output schema, optional window anchor, unavailable behavior, and provenance. The engine
executes the function twice and isolates failures. Follow the complete example in
[Custom metric plugins](custom_metric_plugins.md).

## Advanced Research Outputs

- On Replay, a source-coordinate corridor plane appears only when vehicle x/y evidence exists; it
  is explicitly non-geographic.
- In Provenance Explorer's metric view, expand the complete contribution ledger to inspect or
  download every accepted candidate row.
- In Diagnostics & Evidence, expand the constrained narrative to read prose that cites the
  existing structured findings and adds no diagnoses.
- Reports accepts `.pdf` output paths in addition to Markdown and HTML.
- Reports can emit bounded escaped `.tex` research tables and optional deterministic SVG/PDF
  figures from four completed typed artifact families.
- Reports can append/read typed analyst history and render it in a distinct non-computed section
  without changing computed claims.
- Reports can save typed `.json` payloads and compare compatible metric/rule/comparison snapshots
  without parsing rendered prose.
- Mock Evaluation Analysis loads only files labelled `dataset_mode=synthetic_mock`; its bundled
  fixture is not participant evidence.

For case-study generation, extended fault evaluation, portfolio reports, browser auditing, and
CLI examples, see [Advanced research tools](advanced_research_tools.md).

## Greater Manchester Baseline Network

TrafficTwin can build a deterministic SUMO road network for Greater Manchester from an
OpenStreetMap extract. This is **infrastructure only**: it produces road geometry. It does not
calibrate traffic, does not validate the model against observations, does not show live traffic,
and does not run a VEC experiment.

The baseline scope is **Greater Manchester** (all ten boroughs). **Manchester local authority is a
filter over that one network**, not a second network, and the baseline is checked to contain both
Manchester city centre and the University of Manchester area.

Everything runs from the command line, never from a page, so no browser refresh can trigger a
download or a build:

```bash
traffictwin integration manchester network scope
traffictwin integration manchester network acquire <workspace> --confirm
traffictwin integration manchester network decode --extract <pbf> --output <osm.xml>
traffictwin integration manchester network build <workspace> --extract <osm.xml> --network-id gm-1
traffictwin integration manchester network status <workspace>
```

Two things are worth knowing before you rely on a build:

- **Rebuilds are not guaranteed to match.** SUMO writes a timestamp into every network file, so the
  raw file always differs. TrafficTwin also records an "identity" checksum with that banner removed
  — but at Greater Manchester scale even that is only *usually* stable: in three measured builds,
  two matched exactly and one differed in 238 of 10.9 million lines, all of them roundabout
  groupings. Road, junction and traffic-light counts were identical every time. So TrafficTwin
  never claims a build is reproducible; it says `not_verified` until you compare two real builds.
- **DfT traffic counts only cover Manchester local authority.** Inside the wider Greater Manchester
  network that is partial coverage. Places without counts are shown as *uncovered*, never as zero
  traffic — no survey point is not the same thing as no vehicles.

Source and licence: OpenStreetMap via Geofabrik, ODbL 1.0, attributed as
`© OpenStreetMap contributors, ODbL 1.0`. Downloaded extracts stay in your workspace and are never
committed to the repository.

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
- The standalone demo does not enable direct launch, Randy/VEC execution, SUMO execution, or live
  data. The separate SUMO Output Import page remains import-only.

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
- [Accepted-row difference provenance](difference_provenance.md)
- [Bounded provenance graph exports](provenance_graph_exports.md)
- [Advanced research tools](advanced_research_tools.md)
- [Common-seed paired statistical studies](statistical_studies.md)
- [Paired equivalence testing](equivalence_testing.md)
- [Versioned regression gates](regression_gates.md)
- [Paired common-seed power analysis](power_analysis.md)
- [Limitations and future work](limitations_and_future_work.md)
