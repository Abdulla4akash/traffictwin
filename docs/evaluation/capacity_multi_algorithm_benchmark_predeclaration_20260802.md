# Capacity-aware and multi-algorithm benchmark — PROPOSED / UNSIGNED

This predeclaration creates no evidence, signature, cloud authority or execution.

Protocol digest: `0e3d83190a7cf349d8a09cab803e80dee38d6c3e34ac2e544f964a0285f5f843`
Design reference: docs/platform/capacity_aware_benchmark_design.md
Citation requirements: docs/producer_citation_requirements.md

## Research questions

- capacity-awareness main effect under matched contracts
- algorithm-family main effect under matched contracts
- capacity-representation by algorithm-family interaction

## Frozen factorial

- compatible training cells: 240
- training jobs: 2400
- trained algorithms: mappo, ippo, qmix, vdn, independent_dqn
- evaluation-only controls: deterministic_heuristic, random
- capacity representations: capacity_blind, global_scalar, per_rsu_vector, local_observable, provisioned_remaining, local_utilisation_queue
- action tracks: local_v2i_v2v_unmasked, local_v2i_v2v_feasibility_masked
- reward tracks: balanced_qos_energy, pure_qos, outcome_coherent, fairness_aware
- separately analysed domains: procedural_vec, manchester_corridor, sparse64_whole_fleet, manchester_additional_periods, sumo_networks, dhaka_corridor

## Primary endpoint and statistics

Primary: equal_weight_task_class_deadline_completion
- report: equal_weight_task_class_deadline_completion
- report: task.latency.mean_ms
- report: task.energy.mean_j
- report: task.completion_failure_composition
- report: action_offloading_behaviour
- report: persistent_minority_failure_concentration
- paired difference and 95% paired bootstrap interval
- exact sign test and paired permutation test
- Holm FWER 0.05 confirmatory; BH FDR 0.05 exploratory
- practical thresholds (protocol-digest-bound): 0.01 deadline/failure absolute, 100 ms latency, 0.1 J energy, 0.05 action share and 0.02 minority share
- at least 18 of 20 fresh pairs; no post-hoc seed expansion

## Seeds, checkpoints and compute estimates

- engineering: (2000, 2001, 2002)
- training: (2100, 2101, 2102, 2103, 2104, 2105, 2106, 2107, 2108, 2109)
- tuning: (2200, 2201, 2202, 2203, 2204)
- fresh paired evaluation: (2300, 2301, 2302, 2303, 2304, 2305, 2306, 2307, 2308, 2309, 2310, 2311, 2312, 2313, 2314, 2315, 2316, 2317, 2318, 2319)
- terminal checkpoint primary; 25/50/75/100% milestones robustness only
- GCP Batch primary; AWS Batch failover
- L4/A100/H100 calibration and cross-accelerator reproducibility
- ceilings: 5,000 GPU-hours / GBP 5,000; calibration GBP 250; pilot GBP 750
- all resource figures are estimates until the final owner signature binds them

## Null, deviations and admission

no predeclared practically meaningful capacity, algorithm or interaction difference is a complete valid result
retain every deviation, exclude only by predeclared rules and never expand seeds or select checkpoints from held-out outcomes
Domains remain separate. Existing B-CAP and prior Sparse-64 returns are not inputs.
Rule-based admission eligibility requires exact scope/digest, >=18 pairs, frozen analysis, multiplicity completion and only predeclared deviations; eligibility is not itself admission.

## Sign-off (EMPTY)

| field | value |
|---|---|
| owner identity | |
| owner role | |
| signed at UTC | |
| final markdown SHA-256 | |
| protocol SHA-256 | |
| bounded compute/spend authority | |
