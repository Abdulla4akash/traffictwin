# Temporal Degradation and Recovery Diagnosis (R6)

TrafficTwin `DIA-01` evaluates a selected fixed-window metric for sustained adverse movement and,
when an event time is explicitly declared, describes whether the metric is observed back inside a
baseline tolerance band. The calculation is deterministic and consumes only typed temporal
evidence attached to an `EvidencePack`.

R6 is a diagnostic candidate. It does not prove statistical drift, infer an incident, identify a
root cause, or establish that a declared event caused a metric change.

## End-to-End Use

```bash
uv run traffictwin diagnose temporal tests/fixtures/bundles/baseline_valid \
  --width-s 5 \
  --start-s 0 \
  --end-s 10 \
  --metric-key task.completion.rate \
  --event-time-s 5 \
  --event-label "declared scenario event" \
  --baseline-windows 1 \
  --minimum-evaluable-windows 2 \
  --sustained-windows 1 \
  --recovery-horizon-windows 1 \
  --format json \
  --output /tmp/temporal-r6.json
```

This small fixture produces a supported `not_triggered` result. Use a study-appropriate window
grid and predeclared thresholds for substantive analysis; do not tune thresholds to force a
trigger.

The output is a `TemporalDiagnosticAnalysis` containing the complete `TemporalEvidence`, the
resulting temporal `EvidencePack`, the ordinary ruleset `DiagnosticReport`, and the R6
`RuleResult`. Use `--format text` for a short status summary. The generated static contract is
[`reference/generated/temporal_diagnosis_contract.json`](reference/generated/temporal_diagnosis_contract.json).

## Evidence Contract

`TemporalEvidenceConfig` selects one metric and declares:

| Field | Default | Meaning |
|---|---:|---|
| `metric_key` | `task.deadline_miss.completed_observed_rate` | Scalar window metric evaluated by R6. |
| `minimum_window_coverage` | `1.0` | Minimum requested-range overlap admitted as a value. This is not sensor completeness. |
| `event_time_s` | none | Optional researcher-declared event time. |
| `event_label` | none | Descriptive label allowed only with an event time. |
| `event_alignment_policy` | `containing_half_open_effective_window_v1` | Maps the event into the existing `[start,end)` grid. |

The metric must be window-applicable, scalar and numeric, use one compatible unit and
implementation version, and declare `higher_is_better`. TrafficTwin derives the adverse direction
from that definition. A count with no objective direction, grouped object, or incompatible series
remains unavailable.

Every grid position is retained as `eligible`, `excluded_partial`, `low_coverage`,
`metric_absent`, `metric_unavailable`, `metric_partial`, `metric_invalid`, `non_numeric`, or
`incompatible`. Only eligible points carry a number into R6. Other states are never converted to
zero or silently removed.

## R6 Configuration

The ruleset schema remains `1.0`; R6 introduced ruleset `1.1`, R7 advanced it to `1.2`, and the
current R8-enabled default ruleset is `1.3`. R6 v1.0 uses:

| Field | Default | Meaning |
|---|---:|---|
| `baseline_window_count` | 2 | Exact consecutive leading windows, or windows immediately before the declared event. |
| `minimum_evaluable_windows` | 4 | Minimum eligible observations in the temporal artifact. |
| `minimum_deterioration_delta` | 0.10 | Absolute adverse change from the baseline mean, in the selected metric unit. |
| `sustained_window_count` | 2 | Consecutive eligible adverse windows required to trigger. |
| `recovery_tolerance` | 0.05 | Maximum adverse change treated as back inside the baseline band. |
| `recovery_horizon_windows` | 4 | Event window plus following grid positions considered for recovery. |

These defaults are provisional synthetic-development values. They are not externally calibrated
and should not be reused for a different metric or claim without a declared methodological basis.

For a lower-is-better metric, adverse delta is `window_value - baseline_mean`. For a
higher-is-better metric, it is `baseline_mean - window_value`. The first consecutive episode
meeting the delta and duration thresholds is reported. Exact baseline, observation, episode,
missing, event, and recovery ordinals are preserved in metadata.

## Missing Intervals and Recovery

- A missing, partial, or low-coverage baseline makes R6 `insufficient_evidence`.
- Any ineligible point breaks a consecutive deterioration run.
- If a complete observation region does not meet the trigger, R6 is `not_triggered`.
- If no episode is found but gaps could hide one, R6 is `insufficient_evidence`.
- A supported episode is `triggered` even if other gaps remain visible; confidence is reduced.
- An ordinary EvidencePack without temporal evidence stays valid and produces explicit R6
  insufficiency.

Post-event recovery is `recovered`, `recovered_after_gap`,
`not_recovered_within_horizon`, `indeterminate_missing_intervals`, `horizon_incomplete`,
`not_assessed_no_degradation`, or `not_applicable_no_event`. Recovery does not cancel a supported
deterioration episode; it describes what was observed later inside the horizon.

## Python API

```python
from traffictwin.diagnostics.temporal import evaluate_temporal_bundle
from traffictwin.evidence.temporal import TemporalEvidenceConfig
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.windowed import WindowedMetricConfig
from traffictwin.rules.config import R6Config, RuleSetConfig

bundle = validate_bundle("tests/fixtures/bundles/baseline_valid")
analysis = evaluate_temporal_bundle(
    bundle,
    WindowedMetricConfig(width_s=5, analysis_start_s=0, analysis_end_s=10),
    TemporalEvidenceConfig(
        metric_key="task.completion.rate",
        event_time_s=5,
        event_label="declared scenario event",
    ),
    rule_config=RuleSetConfig(
        r6=R6Config(
            baseline_window_count=1,
            minimum_evaluable_windows=2,
            sustained_window_count=1,
            recovery_horizon_windows=1,
        )
    ),
)
print(analysis.r6_result.status)
print(analysis.r6_result.metadata)
```

If a series already exists, use `evaluate_temporal_series`. At the lower level,
`build_temporal_evidence` creates the projection and `attach_temporal_evidence` creates a new
fingerprinted EvidencePack.

## UI and Provenance

Open **Temporal Metrics**, compute the fixed-window series, choose a numeric metric, and use
**R6 Temporal Degradation**. The page only collects settings and renders typed library output.

Temporal evidence fingerprints the timestamp-normalised window artifact and retains the bundle
fingerprint. The DiagnosticReport records both fingerprints, while R6 metadata lists exact
ordinals. Trace any reported ordinal with `traffictwin provenance window-metric` or
`traffictwin provenance window-contributors`. Those traces establish lineage, not causality.

## Limitations

- Event times and labels are researcher-declared and never inferred.
- R6 uses the existing fixed grid; it does not recompute event-aligned windows.
- The arithmetic baseline and absolute-delta rule are descriptive, not a statistical trend or
  change-point test.
- There is no seasonality, autocorrelation, confidence interval, or multiple-testing model.
- Cohort anchors and window boundaries can affect adjacent values.
- Requested-range coverage is not evidence of continuous sensor operation.
- Current SUMO and TOS source-specific paths do not expose R6.

The governing decision is [ADR-022](decisions/ADR-022-temporal-evidence-and-r6-semantics.md).
