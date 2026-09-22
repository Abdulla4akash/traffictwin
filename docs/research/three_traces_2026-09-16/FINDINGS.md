# Findings

All statements below use the predeclared all-15 simultaneous intervals. They are conditional on the selected traces, actor and seed-block model.

- **we / per_task_dla_minus_ingress_dla**: +3.7284 pp, [+2.312730, +5.144052]; positive under the all-15 interval.
- **we / dla_minus_ingress_dla**: -2.9961 pp, [-4.229518, -1.762670]; negative under the all-15 interval.
- **we / per_task_dla_minus_causal_round_robin**: +0.5129 pp, [+0.283838, +0.742035]; positive under the all-15 interval.
- **we / per_task_dla_minus_dla_p2c**: +0.5803 pp, [+0.376683, +0.783882]; positive under the all-15 interval.
- **we / dla_p2c_minus_causal_round_robin**: -0.0673 pp, [-0.093887, -0.040805]; negative under the all-15 interval.
- **wd_pm / per_task_dla_minus_ingress_dla**: +4.3588 pp, [+2.406315, +6.311286]; positive under the all-15 interval.
- **wd_pm / dla_minus_ingress_dla**: -3.5939 pp, [-5.403443, -1.784358]; negative under the all-15 interval.
- **wd_pm / per_task_dla_minus_causal_round_robin**: +0.6056 pp, [+0.160167, +1.051039]; positive under the all-15 interval.
- **wd_pm / per_task_dla_minus_dla_p2c**: +0.6463 pp, [+0.289736, +1.002827]; positive under the all-15 interval.
- **wd_pm / dla_p2c_minus_causal_round_robin**: -0.0407 pp, [-0.132506, +0.051149]; inconclusive; the all-15 interval includes zero.
- **ev / per_task_dla_minus_ingress_dla**: +3.7348 pp, [+2.385031, +5.084615]; positive under the all-15 interval.
- **ev / dla_minus_ingress_dla**: -3.5925 pp, [-4.916499, -2.268562]; negative under the all-15 interval.
- **ev / per_task_dla_minus_causal_round_robin**: +0.4276 pp, [+0.254955, +0.600233]; positive under the all-15 interval.
- **ev / per_task_dla_minus_dla_p2c**: +0.5336 pp, [+0.350424, +0.716739]; positive under the all-15 interval.
- **ev / dla_p2c_minus_causal_round_robin**: -0.1060 pp, [-0.121941, -0.090034]; negative under the all-15 interval.

## Interpretation limits

- The primary denominator is all offered tasks, including rejected tasks.
- PM and event use legacy mask-only entry conventions; immediate slot reuse can carry vehicle queue backlog. Weekend and morning have explicit entry resets.
- RSU counts, trace density, slot assignment and queue convention differ by scenario. The descriptive density plot cannot isolate a density effect.
- Incident E2c/E2d contribute four archived fleet draws; morning contributes eight joint-seed blocks. Incident round-robin is unavailable and is not imputed.
- No trace pooling, cross-trace tests, task-level tests, equivalence claims, seed replacements or outcome-based exclusions were used.
- Frozen actor weights do not imply identical observations, logits or actions; matched exogenous inputs and conservation are checked separately.
- Native two-choice and per-task placement differ in candidate sampling and reservation visibility; this is a comparison of complete implementations.
