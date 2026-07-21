# Diagnostic Rules

TrafficTwin implements deterministic diagnostic hypotheses R0-R8 over `EvidencePack` objects only.
Rules do not read raw CSV files, canonical rows, or simulator state, and they do not recompute metrics.

The outputs are candidate explanations for follow-up investigation. They are not proven root causes.

## Configuration

`RuleSetConfig` is versioned with schema version `1.0` and ruleset version `1.3`.

The default thresholds are provisional and exist for synthetic fixture evaluation only:

- R1 `t1_miss_rate_min`: `0.20`
- R1 `rsu_utilisation_max`: `0.60`
- R1 `offload_rate_max`: `0.20`
- R1 `minimum_task_count`: `20`
- R2 `saturation_threshold`: `0.90`
- R2 `minimum_saturation_duration_s`: `30`
- R2 `queue_length_high_min`: `5`
- R2 `minimum_missed_tasks`: `1`
- R3 `maximum_cross_algorithm_dispersion`: `0.02`
- R3 `maximum_local_gap_from_best`: `0.02`
- R3 `minimum_algorithms`: `2`
- R4 `maximum_jain_index`: `0.80`
- R4 `maximum_mean_utilisation`: `0.80`
- R4 `minimum_rsu_count`: `2`
- R5 `maximum_absolute_gap`: `0.10`
- R5 `minimum_pair_count`: `2`
- R6 `baseline_window_count`: `2`
- R6 `minimum_evaluable_windows`: `4`
- R6 `minimum_deterioration_delta`: `0.10` in the selected metric unit
- R6 `sustained_window_count`: `2`
- R6 `recovery_tolerance`: `0.05` in the selected metric unit
- R6 `recovery_horizon_windows`: `4`
- R7 `dimension`: `vehicle_tier_completion`
- R7 `minimum_outcome_gap`: `0.20`
- R7 `minimum_group_support`: `2`
- R8 `minimum_energy_per_completed_task_j`: `1.50`
- R8 `minimum_completed_tasks`: `10`

These values are not literature-backed claims.

## R0 - Insufficient Or Inconsistent Evidence

Purpose: identify validation or evidence gaps that block or materially qualify diagnostic interpretation.

Inputs:

- validation summary from the EvidencePack;
- evidence availability summary;
- metric statuses.

R0 triggers when validation blocks import, metrics are invalid, diagnosis evidence is unavailable, or task/infrastructure evidence blocks R1/R2.

R0 does not emit causal advice. It recommends repairing or providing evidence.

## R1 - Under-Offloading Candidate

Purpose: identify a pattern where safety-critical task outcomes are poor, infrastructure appears usable, and offloading remains low.

Required metric keys:

- `task.generated.count`
- `task.completion.rate_by_class`
- `task.offload.rate`
- `infra.utilisation.mean`

Trigger pattern:

- task count meets the configured minimum;
- T1 miss rate is at or above threshold;
- mean RSU utilisation is at or below threshold;
- offload rate is at or below threshold.

Limitations:

- Phase 3 evidence does not provide a direct T1-by-low-tier cross-tab.
- Decision-time action availability is not yet present.
- Undertraining is only an alternative explanation unless checkpoint-comparison evidence exists.

## R2 - Infrastructure-Bottleneck Candidate

Purpose: identify infrastructure pressure that may constrain task completion.

Required metric keys:

- `task.generated.count`
- `task.incomplete.rate`
- `infra.utilisation.p95`
- `infra.queue_length.max`
- `infra.saturation.duration_s`
- `infra.saturation.episode_count`

Trigger pattern:

- P95 utilisation meets the configured saturation threshold;
- saturation duration meets the configured minimum;
- maximum queue length meets the configured high-queue threshold;
- estimated missed tasks meet the configured minimum;
- at least one saturation episode exists.

Limitations:

- Phase 3 evidence contains aggregate saturation metrics, not direct task-to-saturation temporal overlap.
- Queue growth is represented by aggregate queue pressure until explicit growth evidence exists.

## R3 - Scenario-Triviality Candidate

Purpose: identify scenarios that may not distinguish policies.

Required experiment-level metric keys:

- `experiment.algorithm.count`
- `experiment.cross_algorithm_dispersion`

Optional supporting metric keys:

- `experiment.always_local_gap_from_best`
- `experiment.pressure.indicator`

Trigger pattern:

- compatible algorithm count meets the configured minimum;
- cross-algorithm dispersion is below the configured maximum;
- when available, always-local gap and pressure evidence support the pattern.

Ordinary single-run EvidencePacks return `insufficient_evidence` for R3.

The standalone demo generates R3-compatible evidence by creating multiple low-pressure synthetic
policy-profile bundles, computing ordinary Phase 3 metrics, and summarising them with the Phase 3
aggregation layer. These profiles are not real trained algorithms.

## R4 - Load-Imbalance Candidate

Purpose: identify uneven capacity-normalised RSU load while aggregate utilisation suggests some
capacity remains.

Required metric keys:

- `infra.load_balance.jain_capacity_normalised`
- `infra.utilisation.mean`
- `infra.observed_rsu.count`

R4 triggers when the RSU count meets the minimum, the Jain index is at or below the configured
imbalance threshold, and mean utilisation is at or below the aggregate-capacity threshold. It
returns conflicting evidence when imbalance is present but total pressure is also high.

Limitations:

- active-task and capacity evidence are required for the Jain metric;
- spatial demand, task-to-RSU routing, placement context, and temporal persistence are not proven;
- the result is a candidate for a controlled siting/routing comparison, not a causal conclusion.

## R5 - Training-To-Validation Drift Candidate

Purpose: identify a descriptive gap between explicitly paired training and validation scalar
observations.

Required experiment-level metric keys:

- `experiment.training_validation.pair_count`
- `experiment.training_validation.max_absolute_gap`

The mean absolute and signed gaps are optional descriptive context. R5 triggers only when both the
configured pair-count minimum and gap threshold are met. A large gap with too few pairs is
conflicting evidence. No relationship is inferred from filenames, algorithm names, or row order.

R5 is not proof of overfitting. Checkpoint, environment, metric-definition, and common-seed
comparability remain prerequisites for interpretation.

## R6 - Temporal Degradation And Recovery Candidate

Purpose: identify sustained adverse movement over a compatible fixed-window scalar metric and,
when an event is explicitly declared, classify observed return to the baseline band.

Required EvidencePack content:

- a typed `temporal_evidence` section built from `WindowedMetricSeries`;
- a scalar window-applicable metric with a declared objective direction;
- compatible unit and implementation version;
- the configured minimum eligible windows and exact consecutive baseline.

Missing, excluded, partial, low-coverage, invalid, and non-numeric windows remain visible and
break consecutive episodes. They never support a trigger and are not replaced with zero. If gaps
prevent a supported non-trigger, R6 returns `insufficient_evidence`.

An optional event time is researcher-declared and mapped to the containing half-open fixed window.
R6 never infers an incident or event from metric movement. Recovery states distinguish recovered,
recovered after a gap, no recovery within a complete horizon, missing-interval uncertainty,
truncated horizons, no degradation, and no event.

R6 is descriptive and deterministic. Its defaults are provisional synthetic-development
thresholds, not a calibrated change-point test, proof of drift, causal incident attribution, or
root-cause diagnosis. See [temporal diagnosis](temporal_diagnosis.md) and
[ADR-022](decisions/ADR-022-temporal-evidence-and-r6-semantics.md).

## R7 - Operational Outcome-Disparity Candidate

Purpose: identify a supported completion-rate disparity over exactly one selected operational
dimension. R7 is the reference core rule compiled through the closed declarative grammar.

Selectable evidence:

- `fairness.vehicle_tier.completion_rate.max_gap` under the exact operational-fairness policy; or
- `spatial.rsu.task.completion_rate_by_target` under the exact execution-target RSU contract.

The selected metric must be available, have unit `ratio`, carry its exact policy/contract and full
coverage metadata, contain at least two groups, and meet the configured support in every group.
The default trigger is an absolute gap at or above `0.20`. Null, missing, partial, incompatible, or
thin groups produce `insufficient_evidence`; they are not discarded or treated as zero.

Vehicle tier is an operational resource grouping, not a protected attribute. Target RSU is an
observed execution group, not a geographic or causal assignment. R7 does not establish
discrimination, statistical significance, geography, siting/routing cause, or acceptable overall
performance. The threshold is provisional synthetic-development configuration. See
[R7 operational outcome-disparity diagnosis](fairness_diagnosis.md),
[declarative diagnostic rules](declarative_rules.md), and
[ADR-023](decisions/ADR-023-declarative-rule-grammar-and-r7-fairness.md).

## R8 - Completed-Task Energy-Anomaly Candidate

Purpose: identify high mean energy cost per completed task under one exact canonical energy
contract and a minimum completed-task support requirement.

Required metric keys:

- `task.energy.per_completed_j`;
- `task.completed.count`.

R8 admits evaluation only when completed-task energy is available, finite, non-negative,
`J/task`, completely covered, and carries the exact v1.0 task-energy contract, quantity, unit, and
eligibility metadata. Eligible/population counts must match the completed-task count. The default
inclusive trigger is `>= 1.50 J/task` with at least 10 completed tasks. A high value with thin
support is conflicting; partial, missing, mixed-unit, incompatible, or inconsistent evidence is
insufficient rather than zero.

R8 is a single-run deterministic candidate. It is not a statistical anomaly test, hardware
benchmark, causal diagnosis, efficiency standard, or externally calibrated recommendation. See
[R8 completed-task energy diagnosis](energy_diagnosis.md) and
[ADR-024](decisions/ADR-024-contract-gated-r8-energy-anomaly.md).

## DIA-05 - Verified Nearest Flip

Nearest-flip analysis is a separate typed sensitivity artifact over an existing rule result; it is
not an R9 rule. v1.0 supports R5, R7, and R8 because each has one inclusive continuous severity
boundary after unchanged discrete pair/group/task support admission. For an eligible
`not_triggered` result, the service lowers only that threshold to the admitted observation and
returns it only when ordinary rule-engine re-evaluation produces `triggered`.

R0-R4, R6, and arbitrary declarative rules return `unsupported`. Triggered, conflicting,
insufficient, invalid, disabled, or thin-support source results return `not_applicable`. The output
reports exact configs, constraints, units, delta, ties, evidence/result fingerprints, and a
deterministic artifact fingerprint. It never mutates or persists a threshold and is not a
recommended or calibrated default. See [nearest-flip analysis](nearest_flip_analysis.md) and
[ADR-025](decisions/ADR-025-verified-single-boundary-nearest-flip.md).

## DIA-06 - Interactive Threshold Sensitivity

The v1.0 library service evaluates a bounded inclusive linear grid for the R5, R7, or R8 severity
threshold. It preserves the exact `EvidencePack`, timestamp, non-swept dimension/support settings,
and complete source configuration while invoking the ordinary selected rule at every point.

`ThresholdSensitivityReport` retains all statuses, status/trigger transitions, monotonic-prefix
membership, sampled adjacent flip intervals, and the exact DIA-05 artifact when admissible. The
Streamlit page is a thin renderer and supports only explicit complete-config session import and
download; controls do not persist a default. See
[threshold-sensitivity explorer](threshold_sensitivity_explorer.md) and
[ADR-026](decisions/ADR-026-deterministic-threshold-sensitivity-explorer.md).

## DIA-07 - Deterministic Cross-Rule Relationships

After every enabled rule returns an ordinary result, DIA-07 evaluates a separate static v1.0
policy over those completed results. R1/R2 conflict requires both triggers and exact shared
`task.generated.count`; R1/R4 contextual corroboration requires both triggers and exact shared
`infra.utilisation.mean`; R0 presentation suppression requires a target explicitly named in
`blocked_rules`.

R0 readiness precedence is 100 and every ordinary rule has equal precedence 50. All original
results, statuses, reasons, evidence, confidence categories, and fingerprints remain unchanged.
Conflict selects no winner, corroboration does not raise confidence, and suppression means only
that the retained target is non-actionable while blocked. Undeclared pairs produce no inferred
relationship. See [deterministic cross-rule reasoning](cross_rule_reasoning.md) and
[ADR-027](decisions/ADR-027-deterministic-cross-rule-relationships.md).

## Confidence

Confidence is categorical: `low`, `moderate`, `high`, or `unavailable`.

It is derived from evidence completeness, sample size, supporting conditions, contradictions, validation quality, and directness of evidence. It is not a probability.

## Related Documents

- [EvidencePack specification](evidence_pack_spec.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [Temporal degradation and recovery diagnosis](temporal_diagnosis.md)
- [R7 operational outcome-disparity diagnosis](fairness_diagnosis.md)
- [R8 completed-task energy-anomaly diagnosis](energy_diagnosis.md)
- [Verified nearest-flip analysis](nearest_flip_analysis.md)
- [Threshold-sensitivity explorer](threshold_sensitivity_explorer.md)
- [Deterministic cross-rule reasoning](cross_rule_reasoning.md)
- [Declarative diagnostic rules](declarative_rules.md)
- [Standalone demo](standalone_demo.md)
- [Experiment research tools](experiment_research_tools.md)
- [Synthetic data model](synthetic_data_model.md)
- [Viva guide](viva_guide.md)
- [Generated rule catalogue](reference/generated/rule_catalogue.json)
