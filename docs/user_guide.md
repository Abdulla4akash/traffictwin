# User Guide

TrafficTwin is currently an import-first Streamlit prototype. It supports synthetic fixtures and imported historical bundles. It does not run Randy/VEC, SUMO, live Manchester data, or near-live feeds.

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

Warning: direct simulator launch, live data, and Randy/SUMO integration are not implemented. The capability manifest must show direct launch as unsupported for the default adapter.

## Scenario Studio

Scenario Studio creates or edits a `ScenarioSeed` draft.

Steps:

1. Fill in seed ID, name, description, parent/preset references, demand multiplier, workload mix, fleet settings, RSU settings, decisions, policy, checkpoint, random seed, and provenance.
2. Review live validation errors.
3. Review the YAML preview.
4. Download/export the seed YAML.
5. Optionally register the seed if using a registry.

Controls for unknown or unsupported environment capabilities remain disabled. The Run button is disabled because direct launch is unavailable.

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

## Reading Validation Findings

Severity meanings:

- `info`: context only.
- `warning`: import may proceed, but downstream evidence may be limited.
- `error`: invalid data or metadata; import may proceed only when the finding says it may continue.
- `fatal`: validation cannot safely continue.

Unavailable evidence is not the same as zero. It means the required source table or field is absent, invalid, or not declared.

## Operations View

Phase 4/5 Operations View is historical replay only.

Expected labels:

- `HISTORICAL REPLAY`
- `SYNTHETIC` or `IMPORTED`

The replay clock filters imported timestamps. It does not consume wall-clock live data. If coordinates are absent, the UI shows time-series and tables rather than fabricating a map.

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

## What-if Compare

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

## Evidence & Diagnostic Hypotheses

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

## Downloading JSON

The UI can expose:

- EvidencePack JSON;
- DiagnosticReport JSON;
- validation/metric data through CLI commands.

These JSON documents are useful for reproducibility, tests, and dissertation appendices.

## Data-Mode Labels

| Label | Meaning in current prototype |
|---|---|
| `SYNTHETIC` | Repository fixture data, not real experiment output. |
| `IMPORTED` | A user-supplied historical bundle accepted by validation. |
| `HISTORICAL REPLAY` | Timestamp-driven replay over imported records. |
| `NEAR-LIVE` | Future unsupported mode. |
| `TRUE LIVE` | Future unsupported mode requiring real live source. |

Related documents:

- [Demo script](demo_script.md)
- [Demo checklist](demo_checklist.md)
- [CLI reference](cli_reference.md)
- [Limitations and future work](limitations_and_future_work.md)
