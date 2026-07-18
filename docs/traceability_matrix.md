# Traceability Matrix

This matrix maps meeting-derived requirements recorded in the canonical v0.4 design to implementation and documentation. It does not invent new meeting statements.

| Supervisor/Randy requirement | Design decision | Implementation module | Test evidence | Documentation | Status |
|---|---|---|---|---|---|
| What-if scenarios are the differentiator. | First-class versioned scenario seeds. | `domain/scenario.py`, `config/seed_io.py`, Scenario Studio | `tests/unit/test_scenario.py`, `tests/unit/test_seed_io.py`, UI tests | [API reference](api_reference.md), [user guide](user_guide.md) | implemented |
| Use the group's seed vocabulary. | `ScenarioSeed` YAML with schema version. | `domain/scenario.py` | seed unit tests | [run bundle spec](run_bundle_spec.md), [API reference](api_reference.md) | implemented |
| Import-first execution must always work. | Bundle contract independent of direct launch. | `ingestion/`, `adapters/generic_csv.py` | bundle integration/golden tests | [architecture](architecture.md), [run bundle spec](run_bundle_spec.md) | implemented |
| Do not fake Randy/SUMO launch. | Capability manifest and disabled launch. | `config/capabilities.py`, UI Scenario Studio | `tests/unit/test_capabilities.py`, UI tests | [integration decision](integration/phase6_decision.md) | implemented |
| Randy wants task/RSU monitoring. | OffloadLens metrics and infrastructure views over canonical evidence. | `metrics/task.py`, `metrics/infrastructure.py`, UI pages | metric unit/golden tests | [metrics catalogue](metrics_catalogue.md), [user guide](user_guide.md) | synthetic/generic implemented |
| Which RSU is overwhelmed and how badly. | Per-RSU infrastructure canonical records and metrics. | `canonical/records.py`, `metrics/infrastructure.py` | `tests/unit/test_infrastructure_metrics.py` | [data contract](data_contract.md), [metrics catalogue](metrics_catalogue.md) | implemented when `infra_state` exists |
| Data validation precedes metrics and diagnosis. | ValidationReport gate before metrics and EvidencePack. | `ingestion/bundle.py`, `validation/` | validation golden/integration tests | [validation codes](validation_codes.md) | implemented |
| Numbers come from deterministic code. | Deterministic metric engine. | `metrics/` | metric unit/golden tests | [metrics catalogue](metrics_catalogue.md) | implemented |
| Diagnostic outputs should be hypotheses, not proof. | Rules return candidate hypotheses with alternatives and missing evidence. | `rules/`, `diagnostics/` | rule unit/golden tests | [diagnostic rules](diagnostic_rules.md), [viva guide](viva_guide.md) | implemented |
| LLM may only render existing findings if added later. | No LLM dependency; EvidencePack/DiagnosticReport boundaries. | no LLM modules | absence plus tests around deterministic rules | [limitations](limitations_and_future_work.md) | not implemented by design |
| Sandra asked for easy buttons/screens. | Streamlit prototype over library services. | `ui/` | UI/service tests | [ui design](ui_design.md), [user guide](user_guide.md) | implemented |
| Need reproducibility and provenance. | Registry, fingerprints, versions, source row/file provenance, and read-only Provenance Explorer. | `storage/`, `ingestion/hashes.py`, canonical records, `provenance/`, UI Provenance Explorer | registry tests, bundle tests, provenance unit/integration/golden tests | [reproducibility](reproducibility.md), [provenance explorer](provenance_explorer.md) | implemented |
| Real schemas are unconfirmed. | External uncertainty isolated behind adapters. | `adapters/`, integration docs | Phase 6A discovery docs | [integration inventory](integration/randy_artifact_inventory.md) | blocked |
| Formal/expert evaluation may be needed. | Documentation separates software tests from external validation. | tests, docs | current tests only | [testing strategy](testing_strategy.md), [dissertation mapping](dissertation_mapping.md) | future work |

Related documents:

- [Canonical design specification](traffictwin-design-v0_4.md)
- [Implementation status](implementation-status.md)
- [Assumption register](assumption-register.md)
