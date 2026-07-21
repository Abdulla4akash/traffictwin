from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.helpers import FIXED_TIME, fixed_clock
from traffictwin.canonical.records import TaskRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.integration.sumo import compute_metrics_for_sumo, validate_sumo_results
from traffictwin.metrics.catalogue import metric_catalogue, window_metric_catalogue
from traffictwin.metrics.comparison import ComparisonStatus, compare_metric_collections
from traffictwin.metrics.definitions import AggregationScope, MetricDefinition, MetricDomain
from traffictwin.metrics.engine import compute_metrics
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import (
    MetricPluginRegistry,
    MetricPluginRegistryError,
    PluginMetricContract,
    PluginMetricInput,
    PluginMetricResult,
    PluginOutputKind,
    PluginOutputSchema,
    PluginRowPolicy,
    PluginScalarType,
    PluginTableRequirement,
    metric_plugin_api_contract,
)
from traffictwin.metrics.results import (
    MetricCollection,
    MetricStatus,
    RunMetricContext,
    UnavailableReason,
)
from traffictwin.metrics.windowed import WindowedMetricConfig, compute_windowed_metrics
from traffictwin.provenance.models import ProvenanceNodeType
from traffictwin.provenance.query import (
    build_provenance_context,
    get_metric_contributions,
    get_metric_provenance,
    list_traceable_metrics,
)
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

PLUGIN_KEY = "plugin.research.latency_observation_count"


def _task(task_id: str, arrival: float, latency_ms: float | None) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        vehicle_id=f"vehicle-{task_id}",
        task_class=TaskClass.T1,
        arrival_time_s=arrival,
        deadline_ms=100,
        decision=Decision.LOCAL,
        completed=True,
        latency_ms=latency_ms,
        source_file="tasks.csv",
        source_row=int(arrival) + 2,
    )


def _tables() -> CanonicalTables:
    return CanonicalTables(tasks=[_task("t1", 1, 20), _task("t2", 61, None)])


def _context(*, valid: bool = True) -> RunMetricContext:
    return RunMetricContext(
        run_id="run-plugin",
        experiment_id="exp-plugin",
        seed_id="seed-plugin",
        algorithm="test",
        random_seed=7,
        synthetic=True,
        validation_may_import=valid,
    )


def _evidence() -> EvidenceAvailability:
    return EvidenceAvailability(tasks=EvidenceStatus.AVAILABLE)


def _contract(
    *,
    key: str = PLUGIN_KEY,
    version: str = "1.0.0",
    row_policy: PluginRowPolicy = PluginRowPolicy.DROP_INCOMPLETE,
    windowed: bool = True,
    output_schema: PluginOutputSchema | None = None,
) -> PluginMetricContract:
    required_fields = ["latency_ms"]
    return PluginMetricContract(
        plugin_id="research",
        plugin_version=version,
        definition=MetricDefinition(
            key=key,
            human_name="Latency observation count",
            description="Count rows admitted by the declared latency input contract.",
            domain=MetricDomain.CUSTOM,
            unit="count",
            aggregation_scope=AggregationScope.RUN,
            required_tables=["tasks"],
            required_fields={"tasks": required_fields},
            implementation_version=version,
            time_window_applicable=windowed,
            time_anchor="tasks.arrival_time_s" if windowed else None,
            limitations=["Example trusted local extension used only in deterministic tests."],
        ),
        inputs=[
            PluginTableRequirement(
                table="tasks",
                required_fields=required_fields,
                row_policy=row_policy,
            )
        ],
        output_schema=output_schema
        or PluginOutputSchema(
            kind=PluginOutputKind.SCALAR,
            scalar_type=PluginScalarType.INTEGER,
        ),
    )


def _count_latency_rows(inputs: PluginMetricInput) -> PluginMetricResult:
    return PluginMetricResult(value=len(inputs.tables.tasks), metadata={"formula": "row_count"})


def _registry(
    compute: Callable[[PluginMetricInput], PluginMetricResult] = _count_latency_rows,
    *,
    contract: PluginMetricContract | None = None,
) -> MetricPluginRegistry:
    registry = MetricPluginRegistry()
    registry.register(contract or _contract(), compute)
    return registry


def _compute(registry: MetricPluginRegistry, *, valid: bool = True) -> MetricCollection:
    return compute_metrics(
        _tables(),
        _context(valid=valid),
        _evidence(),
        MetricEngineConfig(),
        plugin_registry=registry,
        clock=lambda: FIXED_TIME,
    )


def test_plugin_contract_is_strict_aligned_and_fingerprinted() -> None:
    contract = _contract()

    assert len(contract.fingerprint()) == 64
    assert contract.fingerprint() == _contract().fingerprint()
    assert metric_plugin_api_contract().uploaded_code_execution is False
    with pytest.raises(ValueError, match="required_fields must exactly match"):
        PluginMetricContract.model_validate(
            {
                **contract.model_dump(mode="json"),
                "definition": {
                    **contract.definition.model_dump(mode="json"),
                    "required_fields": {},
                },
            }
        )
    with pytest.raises(ValueError, match="canonical input time anchor"):
        PluginMetricContract.model_validate(
            {
                **contract.model_dump(mode="json"),
                "definition": {
                    **contract.definition.model_dump(mode="json"),
                    "time_anchor": "tasks.completion_time_s",
                },
            }
        )


def test_registry_rejects_duplicate_core_collision_and_mixed_plugin_versions() -> None:
    registry = _registry()
    with pytest.raises(MetricPluginRegistryError, match="duplicate"):
        registry.register(_contract(), _count_latency_rows)

    core_collision = _contract().model_copy(
        update={
            "definition": _contract().definition.model_copy(update={"key": "task.generated.count"})
        }
    )
    with pytest.raises(MetricPluginRegistryError, match="collides with core"):
        MetricPluginRegistry().register(core_collision, _count_latency_rows)

    second = _contract(
        key="plugin.research.second_count",
        version="2.0.0",
        windowed=False,
    )
    with pytest.raises(MetricPluginRegistryError, match="mixed plugin versions"):
        registry.register(second, _count_latency_rows)


def test_plugin_result_joins_core_collection_catalogue_and_registry_report() -> None:
    registry = _registry()
    collection = _compute(registry)
    metric = collection.by_key()[PLUGIN_KEY]

    assert metric.status is MetricStatus.AVAILABLE
    assert metric.value == 1
    assert metric.implementation_version == "1.0.0"
    assert metric.metadata["plugin_determinism_verified"] is True
    assert metric.metadata["plugin_input_record_counts"] == {"tasks": 2}
    assert metric.metadata["plugin_eligible_record_counts"] == {"tasks": 1}
    assert len(collection.results) == len(metric_catalogue()) + 1
    assert PLUGIN_KEY in metric_catalogue(registry)
    assert PLUGIN_KEY in window_metric_catalogue(registry)
    report = registry.report()
    assert report.metric_count == 1
    assert len(report.registry_fingerprint) == 64
    assert report == registry.report()


def test_registry_snapshots_contracts_from_later_caller_mutation() -> None:
    contract = _contract()
    registry = _registry(contract=contract)
    report = registry.report()

    contract.definition.human_name = "Caller-mutated name"

    registered = registry.registered()[0].contract
    assert registered.definition.human_name == "Latency observation count"
    assert registry.report() == report


def test_availability_contract_blocks_execution_and_invalid_source_remains_invalid() -> None:
    calls = 0

    def counted(inputs: PluginMetricInput) -> PluginMetricResult:
        nonlocal calls
        calls += 1
        return _count_latency_rows(inputs)

    registry = _registry(counted, contract=_contract(row_policy=PluginRowPolicy.REQUIRE_COMPLETE))
    unavailable = _compute(registry).by_key()[PLUGIN_KEY]

    assert calls == 0
    assert unavailable.status is MetricStatus.UNAVAILABLE
    assert unavailable.reason_codes == [UnavailableReason.PLUGIN_AVAILABILITY_REQUIREMENT_UNMET]
    assert unavailable.metadata["plugin_execution_attempted"] is False

    invalid = _compute(registry, valid=False).by_key()[PLUGIN_KEY]
    assert calls == 0
    assert invalid.status is MetricStatus.INVALID
    assert invalid.reason_codes == [UnavailableReason.INVALID_SOURCE_DATA]


def test_plugin_cannot_mutate_canonical_inputs_owned_by_the_engine() -> None:
    tables = _tables()

    def mutating(inputs: PluginMetricInput) -> PluginMetricResult:
        inputs.tables.tasks.clear()
        return PluginMetricResult(value=0)

    collection = compute_metrics(
        tables,
        _context(),
        _evidence(),
        plugin_registry=_registry(mutating),
        clock=lambda: FIXED_TIME,
    )

    assert len(tables.tasks) == 2
    assert collection.by_key()["task.generated.count"].value == 2
    assert collection.by_key()[PLUGIN_KEY].value == 0


def test_nondeterminism_exception_and_invalid_output_are_independently_isolated() -> None:
    counter = 0

    def changing(_: PluginMetricInput) -> PluginMetricResult:
        nonlocal counter
        counter += 1
        return PluginMetricResult(value=counter)

    def failing(_: PluginMetricInput) -> PluginMetricResult:
        raise RuntimeError("private details are not copied into results")

    def invalid(_: PluginMetricInput) -> PluginMetricResult:
        return PluginMetricResult(value=float("nan"))

    registry = MetricPluginRegistry()
    registry.register(_contract(), changing)
    registry.register(
        _contract(key="plugin.research.failing_count", windowed=False),
        failing,
    )
    registry.register(
        _contract(key="plugin.research.invalid_count", windowed=False),
        invalid,
    )
    registry.register(
        _contract(key="plugin.research.healthy_count", windowed=False),
        _count_latency_rows,
    )
    metrics = _compute(registry).by_key()

    assert metrics[PLUGIN_KEY].reason_codes == [UnavailableReason.PLUGIN_NONDETERMINISTIC]
    assert metrics["plugin.research.failing_count"].reason_codes == [
        UnavailableReason.PLUGIN_EXECUTION_FAILED
    ]
    assert metrics["plugin.research.invalid_count"].reason_codes == [
        UnavailableReason.PLUGIN_OUTPUT_INVALID
    ]
    assert metrics["plugin.research.healthy_count"].value == 1
    assert metrics["task.generated.count"].value == 2
    assert "private details" not in metrics["plugin.research.failing_count"].model_dump_json()


def test_plugin_declared_unavailability_and_grouped_partial_output_remain_explicit() -> None:
    def unavailable(_: PluginMetricInput) -> PluginMetricResult:
        return PluginMetricResult(
            status=MetricStatus.UNAVAILABLE,
            missing_evidence=["calibrated local threshold"],
        )

    metric = _compute(_registry(unavailable)).by_key()[PLUGIN_KEY]
    assert metric.value is None
    assert metric.reason_codes == [UnavailableReason.PLUGIN_DECLARED_UNAVAILABLE]

    grouped_contract = _contract(
        key="plugin.research.latency_by_class",
        windowed=False,
        output_schema=PluginOutputSchema(
            kind=PluginOutputKind.GROUPED,
            scalar_type=PluginScalarType.NUMBER,
            allow_null_group_values=True,
        ),
    )

    def grouped(_: PluginMetricInput) -> PluginMetricResult:
        return PluginMetricResult(
            status=MetricStatus.PARTIAL,
            value={"T2": None, "T1": 20.0},
            missing_evidence=["T2 latency"],
        )

    grouped_metric = _compute(_registry(grouped, contract=grouped_contract)).by_key()[
        grouped_contract.definition.key
    ]
    assert grouped_metric.status is MetricStatus.PARTIAL
    assert grouped_metric.value == {"T1": 20.0, "T2": None}


def test_window_engine_reuses_plugin_contract_and_filters_by_declared_anchor() -> None:
    whole_run_calls = 0

    def whole_run_only(inputs: PluginMetricInput) -> PluginMetricResult:
        nonlocal whole_run_calls
        whole_run_calls += 1
        return _count_latency_rows(inputs)

    registry = _registry()
    registry.register(
        _contract(key="plugin.research.whole_run_only", windowed=False),
        whole_run_only,
    )
    series = compute_windowed_metrics(
        _tables(),
        _context(),
        _evidence(),
        WindowedMetricConfig(width_s=60, analysis_start_s=0, analysis_end_s=120),
        plugin_registry=registry,
        clock=lambda: FIXED_TIME,
    )

    assert PLUGIN_KEY in series.applicable_metric_keys
    assert "plugin.research.whole_run_only" not in series.applicable_metric_keys
    assert whole_run_calls == 0
    assert series.slices[0].metrics is not None
    assert series.slices[1].metrics is not None
    assert series.slices[0].metrics.by_key()[PLUGIN_KEY].value == 1
    second = series.slices[1].metrics.by_key()[PLUGIN_KEY]
    assert second.status is MetricStatus.UNAVAILABLE
    assert second.reason_codes == [UnavailableReason.PLUGIN_AVAILABILITY_REQUIREMENT_UNMET]


def test_plugin_comparison_requires_equal_contract_fingerprint() -> None:
    baseline = _compute(_registry())
    variation = _compute(_registry(contract=_contract(version="1.0.1")))
    report = compare_metric_collections(baseline, variation)
    comparison = next(
        item for item in report.unavailable_comparisons if item.metric_key == PLUGIN_KEY
    )

    assert comparison.status is ComparisonStatus.UNAVAILABLE
    assert UnavailableReason.COMPARISON_PAIR_INCOMPATIBLE in comparison.reason_codes


def test_plugin_contract_drives_trace_and_complete_declared_input_ledger(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    context = build_provenance_context(bundle, plugin_registry=_registry(), clock=fixed_clock)

    assert PLUGIN_KEY in list_traceable_metrics(context)
    contributions = get_metric_contributions(context, PLUGIN_KEY)
    trace = get_metric_provenance(context, PLUGIN_KEY, clock=fixed_clock)

    assert contributions.complete_row_ledger
    assert contributions.candidate_row_count == 33
    assert contributions.included_row_count == 31
    assert contributions.excluded_row_count == 2
    assert any(node.node_type is ProvenanceNodeType.METRIC_DEFINITION for node in trace.nodes)
    assert not any(
        node.node_id == f"unavailable:metric_definition:{PLUGIN_KEY}" for node in trace.nodes
    )


def test_sumo_canonical_trip_path_accepts_explicit_compatible_plugin_registry() -> None:
    contract = PluginMetricContract(
        plugin_id="research",
        plugin_version="1.0.0",
        definition=MetricDefinition(
            key="plugin.research.sumo_trip_count",
            human_name="SUMO canonical trip count",
            description="Count explicitly admitted canonical SUMO trip rows.",
            domain=MetricDomain.CUSTOM,
            unit="count",
            aggregation_scope=AggregationScope.RUN,
            required_tables=["trips"],
            required_fields={"trips": ["trip_id"]},
            implementation_version="1.0.0",
        ),
        inputs=[
            PluginTableRequirement(
                table="trips",
                required_fields=["trip_id"],
                row_policy=PluginRowPolicy.REQUIRE_COMPLETE,
            )
        ],
        output_schema=PluginOutputSchema(
            kind=PluginOutputKind.SCALAR,
            scalar_type=PluginScalarType.INTEGER,
        ),
    )

    def trip_count(inputs: PluginMetricInput) -> PluginMetricResult:
        return PluginMetricResult(value=len(inputs.tables.trips))

    registry = _registry(trip_count, contract=contract)
    metrics = compute_metrics_for_sumo(
        validate_sumo_results(Path("tests/fixtures/sumo/square_public"), clock=fixed_clock),
        plugin_registry=registry,
        clock=fixed_clock,
    )

    assert metrics.by_key()[contract.definition.key].value == 127
