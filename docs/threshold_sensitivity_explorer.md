# Threshold-Sensitivity Explorer

`DIA-06` v1.0 evaluates and displays a complete bounded threshold grid for the contracted
single-boundary R5, R7, and R8 diagnostic rules. Every point is evaluated by the ordinary rule
engine over the same `EvidencePack`; the Streamlit page contains no rule calculation.

The explorer answers a narrow descriptive question:

> Across this explicitly declared threshold range, which ordinary rule statuses occur and where
> do adjacent sampled points change trigger membership?

It does not calibrate a threshold, optimise a result, estimate significance, establish causality,
or recommend replacing a default.

## Supported Axes

| Rule | Swept parameter | Unit | Held fixed |
|---|---|---|---|
| R5 | `r5.maximum_absolute_gap` | ratio | minimum pair count |
| R7 | `r7.minimum_outcome_gap` | ratio | selected dimension, group count admission, minimum group support |
| R8 | `r8.minimum_energy_per_completed_task_j` | J/task | minimum completed-task support |

R0-R4, R6, and arbitrary declarative rules are visibly unsupported in v1.0. Their ordinary rule
evaluation remains available; the unsupported state applies only to this sweep contract.

## Grid Contract

The request declares:

- an inclusive finite non-negative lower threshold;
- a strictly larger inclusive upper threshold;
- 2 to 101 requested points; and
- one supported rule ID.

R7 cannot exceed its ratio-domain upper bound of 1.0. The library generates an inclusive linear
grid, rounds generated values to 12 decimal places, and inserts the exact source threshold if it
falls inside the declared range but is not already a point. Requested and evaluated counts and the
insertion state remain visible.

For every retained point the report records the exact selected-rule config, ordinary status,
trigger membership, result fingerprint, evidence keys, finding count, and missing-evidence count.
`insufficient_evidence`, `conflicting_evidence`, `invalid`, and `not_triggered` points are never
discarded to make a sweep look favourable.

## Stability And Boundaries

`TriggerStabilitySummary` records:

- counts for every observed `RuleStatus`;
- the number and fraction of triggered points;
- transitions in the full status sequence;
- transitions in triggered/not-triggered membership;
- whether every point has the same status; and
- whether triggered membership forms the expected prefix as an inclusive threshold rises.

A `ThresholdFlipBoundary` is only the interval between two adjacent sampled points whose trigger
membership differs. It is labelled `sampled_interval_not_exact_boundary`. When DIA-05 admits an
exact verified nearest flip from the source configuration, the report embeds that separate typed
artifact and fingerprint. A sampled interval is never substituted for an inadmissible exact flip.

## Use The Streamlit Explorer

Start the application:

```bash
uv run streamlit run src/traffictwin/ui/app.py
```

Then:

1. Select a validated generic or synthetic bundle in the workspace.
2. Open **Threshold Sensitivity** under **Analysis**.
3. Select R5, R7, or R8.
4. Review the source threshold, unit, ruleset, and fixed support/dimension settings.
5. Set inclusive bounds and the requested point count.
6. Select **Run Threshold Sweep**.
7. Inspect the complete status chart/table, stability summary, sampled intervals, and the DIA-05
   exact boundary when available.
8. Download the complete report or explicitly export one evaluated point as a complete
   `RuleSetConfig` JSON.

The page labels all defaults provisional. It does not run automatically when a control changes.

## Explicit Configuration Exchange

The config expander provides two explicit actions:

- **Apply imported rule configuration** validates a complete `RuleSetConfig` JSON and keeps it in
  the current Streamlit session only.
- **Export current complete RuleSetConfig JSON** or **Export selected point as complete
  RuleSetConfig JSON** downloads a new file.

Changing a rule, range, point count, or export selector does not write to the registry, repository,
source bundle, package defaults, or raw evidence. Exported point configs are permitted only for an
exact threshold retained by the report and only when the complete source config still matches the
report.

## Python Usage

```python
from traffictwin.diagnostics.threshold_sweep import (
    ThresholdSweepRequest,
    evaluate_threshold_sweep,
)

request = ThresholdSweepRequest(
    rule_id="R8",
    minimum_threshold=0.0,
    maximum_threshold=3.0,
    point_count=13,
)
report = evaluate_threshold_sweep(evidence_pack, request, rule_config)

for point in report.points:
    print(point.threshold, point.status.value)

print(report.stability.status_counts if report.stability else {})
print(report.fingerprint())
```

Use `config_for_evaluated_point(report, source_config, threshold)` to create an in-memory complete
config for one exact retained point. The function verifies report availability, source-config
identity, ruleset version, and grid membership before returning a new config.

## Artifact And Provenance

`ThresholdSensitivityReport` records:

- request, grid method, source threshold, parameter path, and unit;
- complete source and fixed rule configuration;
- every evaluated point and status;
- stability and sampled flip intervals;
- embedded DIA-05 output when available;
- EvidencePack, source-bundle, source-result, point-result, nearest-flip, and report fingerprints;
- synthetic/source identity, one shared timestamp, and limitations.

The report fingerprint normalises only the generated report and embedded nearest-flip timestamps.
Thresholds, statuses, configurations, constraints, and evidence fingerprints remain unchanged.

## Capability Boundary

The generic bundle capability is true only when an eligible EvidencePack can be built and one of
the supported rules is selected. Current SUMO and TOS source manifests report
`threshold_sensitivity_sweep: false`; missing external energy, fairness, or experiment-pair
semantics are not invented to populate the explorer.

## Appropriate Uses

- demonstrate whether a provisional candidate status is stable across a predeclared range;
- show where a coarse sampled grid brackets a trigger-membership change;
- audit thin-support or missing-evidence behavior across every threshold;
- export a reviewed configuration for a later, separately declared analysis; and
- include a fingerprinted sensitivity artifact in dissertation software-method evidence.

## Inappropriate Uses

- selecting the most favourable threshold after inspecting a result;
- claiming that the exact or sampled boundary is calibrated or optimal;
- lowering pair, group, or task support to force a trigger;
- comparing absolute distances across unrelated units;
- treating synthetic stability as external validation; or
- presenting a trigger transition as significance, discrimination, efficiency, cause, or advice.

## Related Documents

- [ADR-026](decisions/ADR-026-deterministic-threshold-sensitivity-explorer.md)
- [Verified nearest-flip analysis](nearest_flip_analysis.md)
- [Diagnostic rules](diagnostic_rules.md)
- [UI design](ui_design.md)
- [Generated threshold-sensitivity contract](reference/generated/threshold_sensitivity_contract.json)
