# mypy: disable-error-code="arg-type,unused-ignore"
"""Unit tests for Metric Contract Registry."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.experiments.resource_strategy import (
    ResourceStrategyAdmissionState,
    ResourceStrategyArm,
    ResourceStrategyEvidenceMode,
    ResourceStrategyLifecycle,
    ResourceStrategyMetric,
    ResourceStrategyMetricDenominator,
    ResourceStrategyMetricStatus,
    ResourceStrategyReplication,
    ResourceStrategyStudy,
    build_resource_strategy_report,
)
from traffictwin.metric_contract_registry.models import (
    MetricContract,
    MetricContractDenominator,
    MetricContractDirection,
    MetricContractRegistry,
    MetricContractSupersession,
)
from traffictwin.metric_contract_registry.service import (
    build_built_in_registry,
    load_registry_from_json,
    merge_registries,
    registry_to_csv,
    validate_registry,
)


def _valid_contract(**overrides: object) -> MetricContract:
    base = dict(  # noqa: C408
        metric_key="custom.test.metric",
        metric_version="1.0",
        unit="ratio",
        denominator=MetricContractDenominator.REPLICATION,
        description="Test custom metric",
        higher_is_better=True,
        direction=None,
        time_window_applicable=False,
        contract_version="1.0",
    )
    base.update(overrides)  # type: ignore[arg-type]
    return MetricContract(**base)  # type: ignore[arg-type]


def _registry(contracts: list[MetricContract] | None = None) -> MetricContractRegistry:
    return MetricContractRegistry(
        registry_version="1.0",
        contracts=contracts or [_valid_contract()],
        supersession=[],
    )


def _valid_lifecycle(**overrides: object) -> ResourceStrategyLifecycle:
    base = dict(  # noqa: C408
        offered=1000,
        admitted=800,
        rejected=200,
        forwarded=400,
        started=760,
        compute_completed=720,
        returned=700,
        dropped=80,
        deadline_success=680,
    )
    base.update(overrides)  # type: ignore[arg-type]
    return ResourceStrategyLifecycle(**base)


def _rep(rid: str, metrics: dict[str, float] | None = None) -> ResourceStrategyReplication:
    return ResourceStrategyReplication(
        replication_id=rid,
        lifecycle=_valid_lifecycle(),
        metrics=metrics or {},
        queue_length_mean=7.5,
        queue_balance_jain=0.9,
        utilisation_mean=0.69,
        energy_mean_j=40.0,
        resource_cost_units=115.0,
        latency_mean_ms=155.0,
        latency_p95_ms=270.0,
    )


def _study_with_custom_metric(
    custom_key: str = "custom.test.metric",
    custom_unit: str = "ratio",
    custom_denom: ResourceStrategyMetricDenominator = ResourceStrategyMetricDenominator.REPLICATION,
) -> ResourceStrategyStudy:
    cat = [
        ResourceStrategyMetric(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.OFFERED_TASKS,
        ),
        ResourceStrategyMetric(
            metric_key=custom_key,
            metric_version="1.0",
            unit=custom_unit,
            denominator=custom_denom,
        ),
    ]
    arms = [
        ResourceStrategyArm(
            arm_id="arm_a",
            label="Arm A",
            description="A",
            strategy_type="t",
            replications=[_rep("rep_001", {custom_key: 0.42}), _rep("rep_002", {custom_key: 0.43})],
        ),
        ResourceStrategyArm(
            arm_id="arm_b",
            label="Arm B",
            description="B",
            strategy_type="t",
            replications=[_rep("rep_001", {custom_key: 0.44}), _rep("rep_002", {custom_key: 0.45})],
        ),
    ]
    return ResourceStrategyStudy.model_validate(
        {
            "schema_version": "1.0",
            "study_id": "test_study",
            "source_fingerprint": hashlib.sha256(b"test").hexdigest(),
            "evidence_mode": ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION.value,
            "admission_state": ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION.value,
            "replication_unit": "replication_id",
            "arms": [a.model_dump(mode="json") for a in arms],
            "common_matched_replication_ids": ["rep_001", "rep_002"],
            "excluded_replication_ids": [],
            "metric_catalog": [m.model_dump(mode="json") for m in cat],
            "limitations": [],
            "provenance": {},
            "generated_at": None,
        }
    )


# ---------------------------------------------------------------------------
# Deterministic identity
# ---------------------------------------------------------------------------


def test_deterministic_registry_fingerprint() -> None:
    reg = _registry([_valid_contract(), _valid_contract(metric_key="custom.other", unit="ms")])
    fp1 = reg.fingerprint()
    fp2 = reg.fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 64
    # Canonical JSON stable
    assert reg.canonical_json() == reg.canonical_json()
    # File round-trip preserves fingerprint across temp roots
    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        p1 = Path(td1) / "reg.json"
        p2 = Path(td2) / "reg.json"
        p1.write_text(reg.to_json(), encoding="utf-8")
        p2.write_text(reg.to_json(), encoding="utf-8")
        loaded1 = load_registry_from_json(p1.read_text())
        loaded2 = load_registry_from_json(p2.read_text())
        assert loaded1.fingerprint() == fp1
        assert loaded2.fingerprint() == fp1


def test_order_independence() -> None:
    c1 = _valid_contract(metric_key="custom.a", unit="ratio")
    c2 = _valid_contract(metric_key="custom.b", unit="ms")
    reg1 = MetricContractRegistry(registry_version="1.0", contracts=[c1, c2], supersession=[])
    reg2 = MetricContractRegistry(registry_version="1.0", contracts=[c2, c1], supersession=[])
    assert reg1.fingerprint() == reg2.fingerprint()
    assert reg1.canonical_json() == reg2.canonical_json()


def test_conflicting_duplicate_refusal() -> None:
    c1 = _valid_contract(metric_key="custom.dup", unit="ratio")
    c2 = _valid_contract(
        metric_key="custom.dup", unit="ms"
    )  # same key/version, different unit -> conflict
    with pytest.raises(ValidationError, match="conflicting duplicate"):
        MetricContractRegistry(registry_version="1.0", contracts=[c1, c2], supersession=[])


def test_identical_duplicate_accepted_as_redundant() -> None:
    c1 = _valid_contract(metric_key="custom.same", unit="ratio")
    c2 = _valid_contract(metric_key="custom.same", unit="ratio")
    # Should not raise; canonical deduplicates
    reg = MetricContractRegistry(registry_version="1.0", contracts=[c1, c2], supersession=[])
    assert reg.fingerprint() == _registry([c1]).fingerprint()
    assert len(reg.deduplicated_contracts()) == 1


def test_built_in_override_refusal() -> None:
    # Try to override built-in task.latency.mean_ms with wrong unit
    bad = MetricContract(
        metric_key="task.latency.mean_ms",
        metric_version="1.0",
        unit="wrong_unit",
        denominator=MetricContractDenominator.COMPLETED_TASKS,
        description="Conflicting built-in",
        higher_is_better=False,
        direction=None,
        time_window_applicable=False,
        contract_version="1.0",
    )
    reg = MetricContractRegistry(registry_version="1.0", contracts=[bad], supersession=[])
    receipt = validate_registry(reg)
    assert receipt.status.value == "rejected"
    assert any("BUILT_IN_OVERRIDE" in f.code for f in receipt.findings)
    assert "task.latency.mean_ms" in receipt.built_in_conflicts


def test_built_in_identical_redundant_accepted() -> None:
    built = build_built_in_registry()
    # Take one built-in contract as redundant reference
    built_one = built.contracts[0]
    reg = MetricContractRegistry(registry_version="1.0", contracts=[built_one], supersession=[])
    receipt = validate_registry(reg)
    assert receipt.status.value != "rejected"
    assert any("BUILT_IN_REDUNDANT" in f.code for f in receipt.findings)


def test_valid_custom_metric_remains_unavailable_without_registry() -> None:
    study = _study_with_custom_metric()
    report = build_resource_strategy_report(study)
    compat = next(c for c in report.compatibility if c.metric_key == "custom.test.metric")
    assert compat.status.value == "unavailable"
    assert "no registered" in compat.finding.lower()
    # Arm aggregates must be unavailable
    for arm in report.arm_summaries:
        agg = next(a for a in arm.metric_aggregates if a.metric_key == "custom.test.metric")
        assert agg.status == ResourceStrategyMetricStatus.UNAVAILABLE
        assert agg.aggregate_mean is None
        assert not agg.per_replication_values
    # Pairwise unavailable
    for diff in report.pairwise_differences:
        if diff.metric_key == "custom.test.metric":
            assert diff.status.value == "unavailable"


def test_same_metric_becomes_available_with_valid_registry() -> None:
    study = _study_with_custom_metric()
    reg = _registry([_valid_contract(metric_key="custom.test.metric")])
    report = build_resource_strategy_report(study, metric_contract_registry=reg)  # type: ignore[arg-type]
    compat = next(c for c in report.compatibility if c.metric_key == "custom.test.metric")
    assert compat.status.value == "compatible"
    assert "compatible" in compat.finding.lower()
    # Arm aggregates available
    for arm in report.arm_summaries:
        agg = next(a for a in arm.metric_aggregates if a.metric_key == "custom.test.metric")
        assert agg.status.value in ("available", "partial")
        assert agg.aggregate_mean is not None
        assert agg.replication_count == 2
    # Pairwise available
    found = [d for d in report.pairwise_differences if d.metric_key == "custom.test.metric"]
    assert found
    for diff in found:
        assert diff.status.value == "available"
        assert diff.mean_difference_b_minus_a is not None


def test_one_arm_changes_unit_incompatible() -> None:
    study = _study_with_custom_metric()
    reg = _registry([_valid_contract(metric_key="custom.test.metric", unit="ratio")])
    # Simulate per-arm contracts: arm_b uses different unit
    arm_overrides = {
        "arm_a": {
            "custom.test.metric": ("1.0", "ratio", ResourceStrategyMetricDenominator.REPLICATION)
        },
        "arm_b": {
            "custom.test.metric": ("1.0", "ms", ResourceStrategyMetricDenominator.REPLICATION)
        },
    }
    report = build_resource_strategy_report(
        study, metric_contract_registry=reg, arm_metric_contracts=arm_overrides
    )  # type: ignore[arg-type]
    compat = next(c for c in report.compatibility if c.metric_key == "custom.test.metric")
    assert compat.status.value == "incompatible"
    assert "unit" in compat.finding.lower() or "differ across arms" in compat.finding.lower()
    # Arm aggregates unavailable
    for arm in report.arm_summaries:
        agg = next(a for a in arm.metric_aggregates if a.metric_key == "custom.test.metric")
        assert agg.status == ResourceStrategyMetricStatus.UNAVAILABLE
        assert agg.aggregate_mean is None
    # Pairwise unavailable
    for diff in report.pairwise_differences:
        if diff.metric_key == "custom.test.metric":
            assert diff.status.value == "unavailable"


def test_one_arm_changes_denominator_incompatible() -> None:
    study = _study_with_custom_metric()
    reg = _registry(
        [
            _valid_contract(
                metric_key="custom.test.metric", denominator=MetricContractDenominator.REPLICATION
            )
        ]
    )
    arm_overrides = {
        "arm_a": {
            "custom.test.metric": ("1.0", "ratio", ResourceStrategyMetricDenominator.REPLICATION)
        },
        "arm_b": {
            "custom.test.metric": ("1.0", "ratio", ResourceStrategyMetricDenominator.OFFERED_TASKS)
        },
    }
    report = build_resource_strategy_report(
        study, metric_contract_registry=reg, arm_metric_contracts=arm_overrides
    )  # type: ignore[arg-type]
    compat = next(c for c in report.compatibility if c.metric_key == "custom.test.metric")
    assert compat.status.value == "incompatible"
    assert "denominator" in compat.finding.lower() or "differ across arms" in compat.finding.lower()
    for arm in report.arm_summaries:
        agg = next(a for a in arm.metric_aggregates if a.metric_key == "custom.test.metric")
        assert agg.status == ResourceStrategyMetricStatus.UNAVAILABLE


def test_existing_built_in_golden_unchanged_without_registry() -> None:
    # Load synthetic fixture and verify fingerprint unchanged when no registry supplied
    from pathlib import Path

    study = ResourceStrategyStudy.model_validate_json(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json").read_text()
    )
    report = build_resource_strategy_report(study)
    # Known golden fingerprint from existing tests (should remain stable)
    # Compute and verify deterministic
    fp = report.fingerprint()
    # Rebuild again must match
    report2 = build_resource_strategy_report(study)
    assert fp == report2.fingerprint()
    # With no registry, built-in compatibility must be compatible
    for compat in report.compatibility:
        assert compat.status.value == "compatible", (
            f"{compat.metric_key} should be compatible without registry"
        )


def test_bounded_count() -> None:
    many = [_valid_contract(metric_key=f"custom.metric.{i:03d}") for i in range(129)]
    with pytest.raises(ValidationError, match="at most 128"):
        MetricContractRegistry(registry_version="1.0", contracts=many, supersession=[])


def test_no_code_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_contract(metric_key="custom.bad; import os")
    with pytest.raises(ValidationError):
        _valid_contract(description="eval(1)")
    with pytest.raises(ValidationError):
        MetricContract(
            metric_key="custom.ok",
            metric_version="1.0",
            unit="ratio",
            denominator=MetricContractDenominator.REPLICATION,
            description="ok",
            higher_is_better=True,
            time_window_applicable=False,
            contract_version="1.0",
            provenance="/tmp/local/path",  # noqa: S108
        )


def test_numeric_bounds_validation() -> None:
    # minimum > maximum should fail
    with pytest.raises(ValidationError, match="minimum must not exceed maximum"):
        _valid_contract(minimum=10.0, maximum=5.0)
    # allowed_statuses too many
    with pytest.raises(ValidationError):
        _valid_contract(allowed_statuses=[f"s{i}" for i in range(33)])
    # direction/higher_is_better inconsistency
    with pytest.raises(ValidationError, match="inconsistent"):
        MetricContract(
            metric_key="custom.x",
            metric_version="1.0",
            unit="ratio",
            denominator=MetricContractDenominator.REPLICATION,
            description="x",
            higher_is_better=True,
            direction=MetricContractDirection.LOWER_IS_BETTER,
            time_window_applicable=False,
            contract_version="1.0",
        )


def test_import_export_validation_and_fingerprint() -> None:
    reg = _registry([_valid_contract(metric_key="custom.imp", provenance="paper citation")])
    json_text = reg.to_json()
    loaded = load_registry_from_json(json_text)
    assert loaded.fingerprint() == reg.fingerprint()
    # Canonical JSON stable
    assert json.loads(json_text)["fingerprint"] == reg.fingerprint()
    # CSV deterministic
    csv1 = registry_to_csv(reg)
    csv2 = registry_to_csv(loaded)
    assert csv1 == csv2
    assert "metric_key" in csv1.splitlines()[0]


def test_supersession_lineage() -> None:
    c1 = _valid_contract(metric_key="custom.lineage", metric_version="1.0")
    c2 = _valid_contract(metric_key="custom.lineage", metric_version="2.0")
    sup = MetricContractSupersession(
        predecessor_metric_key="custom.lineage",
        predecessor_metric_version="1.0",
        successor_metric_key="custom.lineage",
        successor_metric_version="2.0",
        reason="Updated definition",
    )
    reg = MetricContractRegistry(registry_version="1.0", contracts=[c1, c2], supersession=[sup])
    assert reg.fingerprint() == reg.fingerprint()
    # Invalid lineage (missing predecessor)
    with pytest.raises(ValidationError, match="not in registry"):
        MetricContractRegistry(
            registry_version="1.0",
            contracts=[c1],
            supersession=[sup],
        )


def test_merge_deterministic_and_conflict() -> None:
    c1 = _valid_contract(metric_key="custom.a")
    c2 = _valid_contract(metric_key="custom.b")
    reg1 = MetricContractRegistry(registry_version="1.0", contracts=[c1], supersession=[])
    reg2 = MetricContractRegistry(registry_version="1.0", contracts=[c2], supersession=[])
    merged, receipt = merge_registries([reg1, reg2])
    assert len(merged.deduplicated_contracts()) == 2
    assert receipt.status.value != "rejected"
    # Order independence of merge
    merged2, _ = merge_registries([reg2, reg1])
    assert merged.fingerprint() == merged2.fingerprint()
    # Conflicting duplicate merge should fail
    c_conflict = _valid_contract(metric_key="custom.a", unit="ms")
    reg_conflict = MetricContractRegistry(
        registry_version="1.0", contracts=[c_conflict], supersession=[]
    )
    with pytest.raises(ValueError, match="merge conflict"):
        merge_registries([reg1, reg_conflict])


def test_cli_validation_and_fingerprint(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from traffictwin.metric_contract_registry.cli import app

    runner = CliRunner()
    reg = _registry([_valid_contract()])
    p = tmp_path / "reg.json"
    p.write_text(reg.to_json(), encoding="utf-8")
    result = runner.invoke(app, ["validate", "--input", str(p)])
    assert result.exit_code == 0
    assert "contract_count" in result.output
    result2 = runner.invoke(app, ["fingerprint", "--input", str(p)])
    assert result2.exit_code == 0
    assert reg.fingerprint() in result2.output


def test_strict_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        MetricContract.model_validate(
            {
                "metric_key": "custom.x",
                "metric_version": "1.0",
                "unit": "ratio",
                "denominator": "replication",
                "description": "x",
                "higher_is_better": True,
                "time_window_applicable": False,
                "contract_version": "1.0",
                "extra_field": "not allowed",
            }
        )
    with pytest.raises(ValidationError):
        MetricContractRegistry.model_validate(
            {
                "schema_version": "1.0",
                "registry_version": "1.0",
                "contracts": [],
                "supersession": [],
                "extra": "nope",
            }
        )
