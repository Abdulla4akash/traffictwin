# Diagnostic Rules

Phase 5 implements deterministic diagnostic hypotheses over `EvidencePack` objects only.
Rules do not read raw CSV files, canonical rows, or simulator state, and they do not recompute metrics.

The outputs are candidate explanations for follow-up investigation. They are not proven root causes.

## Configuration

`RuleSetConfig` is versioned with schema version `1.0` and ruleset version `1.0`.

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

## Confidence

Confidence is categorical: `low`, `moderate`, `high`, or `unavailable`.

It is derived from evidence completeness, sample size, supporting conditions, contradictions, validation quality, and directness of evidence. It is not a probability.
