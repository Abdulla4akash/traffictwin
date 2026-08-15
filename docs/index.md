# TrafficTwin Documentation Index

**Current release:** `main` at `337f1624e5ffe188393554b1110a35ababcce8e1`

This index prioritises current authoritative/operational documents. Historical versioned designs, lane records, ADRs, evaluation records, and receipts remain in the repository and Git history for traceability.

## Start here — current release

- [Root README](../README.md)
- [Current implementation status](implementation-status.md)
- [Product Design V3 — integrated release](traffictwin_product_design_v3.md)
- [Use Cases V3 — integrated release](traffictwin_use_cases_v3.md)
- [Current release architecture](architecture_current_release.md)
- [Architecture entrypoint](architecture.md)
- [Final release status and exact identities](quality/final_release_status_20260815.md)
- [Complete product and usage guide](full_product_guide.md)
- [User guide](user_guide.md)
- [Developer guide](developer_guide.md)
- [CLI reference](cli_reference.md)

## Agent/controller entrypoints

- [`../AGENTS.md`](../AGENTS.md)
- [`../CONTROLLER.md`](../CONTROLLER.md)
- [`../CLAUDE.md`](../CLAUDE.md)
- [`../CURRENT_STATUS_CONTEXT_PROMPT.md`](../CURRENT_STATUS_CONTEXT_PROMPT.md)
- [V6 concurrent orchestration policy](quality/controller_concurrent_orchestration_policy_v6.md)

## Current scientific truth

The E3 product/software surface is integrated but E3 scientific execution remains unauthorised and unexecuted. The authoritative release overlay records:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

See [final release status](quality/final_release_status_20260815.md) and [Product Design V3](traffictwin_product_design_v3.md).

## Current bounded use cases

- [Use Cases V3](traffictwin_use_cases_v3.md)
- Historical detailed Manchester context Use Case A: [v0.8 use case A](closure/v08_alignment/use_case_a_manchester_current_twin.md)
- Historical detailed VEC dynamic-service Use Case B: [v0.8 use case B](closure/v08_alignment/use_case_b_vec_dynamic_service.md)

The v0.8 use-case files remain source-bound historical records. V3 states their current release interpretation and E3 no-results boundary.

## Manchester evidence and integration

- [Manchester source Gate A audit](integration/manchester-source-gate-a-audit-v0_7.md)
- [Manchester aggregate operational history](integration/manchester_operational_history.md)
- [National Highways transitions](integration/manchester_national_highways_transitions.md)
- [BODS operational trends](integration/manchester_bods_operational_trends.md)
- [Manchester Source Health](integration/manchester_source_health.md)
- [Restricted TfGM/NTIS contract intake](integration/manchester_restricted_traffic_feed_contract.md)
- [Manchester map-match review](integration/manchester_match_review.md)
- [Manchester demand reconstruction](integration/manchester_demand_reconstruction.md)
- [Manchester comparison](integration/manchester_comparison.md)
- [Manchester research lineage](integration/manchester_research_lineage.md)

## Research/evidence tooling

- [Experiment research tools](experiment_research_tools.md)
- [Statistical studies](statistical_studies.md)
- [N-way ranking](n_way_ranking.md)
- [Equivalence testing](equivalence_testing.md)
- [Regression gates](regression_gates.md)
- [Power analysis](power_analysis.md)
- [Difference provenance](difference_provenance.md)
- [Provenance Explorer](provenance_explorer.md)
- [Provenance graph exports](provenance_graph_exports.md)
- [Provenance completeness](provenance_completeness.md)
- [Research objects / RO-Crate](research_objects.md)
- [Report export](report_export.md)

## Product and UI

- [Product polish / research UX](product_polish.md)
- [UI design](ui_design.md)
- [v0.7 navigation history](v07_navigation.md)
- [Standalone demo](standalone_demo.md)
- [Scenario mutations](scenario_mutations.md)
- [Parameter sweeps](parameter_sweeps.md)
- [Measurement imperfections](measurement_imperfections.md)
- [Threshold sensitivity](threshold_sensitivity_explorer.md)
- [Nearest-flip analysis](nearest_flip_analysis.md)
- [Cross-rule reasoning](cross_rule_reasoning.md)

## Historical/versioned design records

These remain important context but are not the current release overlay:

- [TrafficTwin design v0.7](traffictwin-design-v0_7.md)
- [TrafficTwin design v0.6](traffictwin-design-v0_6.md)
- [TrafficTwin design v0.5](traffictwin-design-v0_5.md)
- [Product Design V2 proposal](traffictwin_product_design_v2.md)
- [v0.7 beta goals](traffictwin-design-v0_7_beta-goals.md)
- [v0.7 current-progress historical tracker](current_progress_v0_7.md)
- [Assumption register](assumption-register.md)
- [Open questions](open-questions.md)

## Quality, decisions, and evidence history

- `docs/quality/` — integration/review/gate records
- `docs/decisions/` — ADRs
- `docs/evaluation/` — predeclarations, results, user-evaluation material
- `docs/integration/evidence/` — machine-readable evidence/receipts
- `docs/closure/` — requirements-closure and source-bound use-case records
- `docs/dissertation_appendices/` — dissertation-oriented traceability and generated snapshots

Historical records should be preserved rather than rewritten to match current prose. Add a new current overlay when meaning changes materially.
