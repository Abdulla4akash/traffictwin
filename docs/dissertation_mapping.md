# Dissertation Mapping

This document maps repository artifacts to likely dissertation sections. It is not the dissertation chapter text.

| Section | Source modules | Documentation | Possible figures/tables | Evidence available now | Blocked material |
|---|---|---|---|---|---|
| Introduction | n/a | [system_overview.md](system_overview.md), [traffictwin-design-v0_4.md](traffictwin-design-v0_4.md) | Problem/workflow diagram | Approved design and implemented prototype scope | Real stakeholder evaluation |
| Background | n/a | design spec, future literature notes | Literature summary tables | Supervisor/Randy requirements in design spec | Verified literature review and citations |
| Requirements | `domain/`, `config/` | [traceability_matrix.md](traceability_matrix.md), [assumption-register.md](assumption-register.md) | Requirement-to-module matrix | Import-first, deterministic, capability-gated requirements | Real Randy/SUMO controls |
| Research questions | n/a | design spec, [system_overview.md](system_overview.md) | RQ-to-evidence table | RQ framing from v0.4 | Final supervisor-approved RQs |
| Architecture | all package layers | [architecture.md](architecture.md) | Mermaid architecture and pipeline diagrams | Implemented layers and boundaries | Real adapter architecture after artifacts |
| Data model | `canonical/`, `ingestion/manifest.py` | [data_contract.md](data_contract.md), [run_bundle_spec.md](run_bundle_spec.md) | Canonical tables and manifest examples | Synthetic contract and generated schemas | Real Randy/SUMO mapping |
| Implementation | `src/traffictwin/` | [developer_guide.md](developer_guide.md), [api_reference.md](api_reference.md) | Package tree, component table | Complete Phase 1-6A plus Provenance Explorer prototype | External adapters and launchers |
| Validation | `validation/`, `ingestion/` | [validation_codes.md](validation_codes.md) | Validation-code table | Unit/golden/integration tests | Real-source validation results |
| Metrics | `metrics/` | [metrics_catalogue.md](metrics_catalogue.md) | Metric catalogue table | Deterministic metrics and golden outputs | Metrics requiring unavailable real fields |
| Diagnostics | `rules/`, `diagnostics/` | [diagnostic_rules.md](diagnostic_rules.md), [diagnostic_report_spec.md](diagnostic_report_spec.md) | Rule logic table | Synthetic fault-injection implementation checks | External diagnostic validation |
| Provenance and auditability | `provenance/`, canonical source references, UI Provenance Explorer | [provenance_explorer.md](provenance_explorer.md), [provenance_model.md](provenance_model.md), [viva_traceability_demo.md](viva_traceability_demo.md) | Trace DAG diagram, metric-to-source example | Metric/rule/source-row trace tests and golden outputs | Full per-row contribution materialisation for all aggregates |
| Evaluation | `tests/` | [testing_strategy.md](testing_strategy.md), [fault_injection_methodology.md](fault_injection_methodology.md) | Test pyramid, synthetic case results | Current test and coverage snapshot after quality gates | User study, real-run evaluation |
| Discussion | all | [limitations_and_future_work.md](limitations_and_future_work.md) | Implemented vs blocked matrix | Honest scope boundaries | Real-world operational findings |
| Limitations | integration docs | [limitations_and_future_work.md](limitations_and_future_work.md) | Limitation categories | Phase 6A discovery result | Mitigations after artifacts |
| Future work | integration docs | [integration/phase6_decision.md](integration/phase6_decision.md) | Adapter roadmap | Exact artifact request list | Phase 6B implementation |

Related documents:

- [Viva guide](viva_guide.md)
- [Traceability matrix](traceability_matrix.md)
- [Reproducibility guide](reproducibility.md)
