# mypy: disable-error-code="arg-type,unused-ignore"
"""Unit tests for Resource Strategy Explorer."""

from __future__ import annotations

import copy
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
    ResourceStrategyExclusion,
    ResourceStrategyExclusionCode,
    ResourceStrategyLifecycle,
    ResourceStrategyMetric,
    ResourceStrategyMetricDenominator,
    ResourceStrategyReplication,
    ResourceStrategyReplicationUnit,
    ResourceStrategyStudy,
    build_resource_strategy_report,
    load_resource_strategy_study_file,
    load_resource_strategy_study_from_json,
    resource_strategy_report_to_csv,
    resource_strategy_report_to_markdown,
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
    base.update(overrides)  # type: ignore[arg-type]  # noqa: E501
    return ResourceStrategyLifecycle(**base)


def _valid_replication(rid: str, **overrides: object) -> ResourceStrategyReplication:
    lifecycle = overrides.pop("lifecycle", _valid_lifecycle())
    defaults: dict[str, object] = {  # noqa: C408
        "queue_length_mean": 7.5,
        "queue_balance_jain": 0.9,
        "utilisation_mean": 0.69,
        "energy_mean_j": 40.0,
        "resource_cost_units": 115.0,
        "latency_mean_ms": 155.0,
        "latency_p95_ms": 270.0,
        "forwarding_rate": 0.5,
        "metrics": {},
    }
    for key in list(overrides.keys()):
        if key in defaults:
            defaults[key] = overrides.pop(key)  # type: ignore[assignment]
    return ResourceStrategyReplication(
        replication_id=rid,
        lifecycle=lifecycle,
        **defaults,
        **overrides,
    )


def _catalog() -> list[ResourceStrategyMetric]:
    return [
        ResourceStrategyMetric(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.OFFERED_TASKS,
        ),
        ResourceStrategyMetric(
            metric_key="task.completion.rate_admitted",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.ADMITTED_TASKS,
        ),
        ResourceStrategyMetric(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=ResourceStrategyMetricDenominator.COMPLETED_TASKS,
        ),
        ResourceStrategyMetric(
            metric_key="infra.queue_length.mean",
            metric_version="1.0",
            unit="tasks",
            denominator=ResourceStrategyMetricDenominator.REPLICATION,
        ),
        ResourceStrategyMetric(
            metric_key="infra.load_balance.jain",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.REPLICATION,
        ),
        ResourceStrategyMetric(
            metric_key="resource.cost.units",
            metric_version="1.0",
            unit="cost_units",
            denominator=ResourceStrategyMetricDenominator.REPLICATION,
        ),
    ]


def _study(**overrides: object) -> ResourceStrategyStudy:
    arms = [
        ResourceStrategyArm(
            arm_id="arm_a",
            label="Arm A",
            description="Arm A synthetic",
            strategy_type="strongest_link_placement",
            replications=[
                _valid_replication("rep_001"),
                _valid_replication("rep_002"),
                _valid_replication("rep_003"),
            ],
        ),
        ResourceStrategyArm(
            arm_id="arm_b",
            label="Arm B",
            description="Arm B synthetic",
            strategy_type="deterministic_jsq",
            replications=[
                _valid_replication("rep_001"),
                _valid_replication("rep_002"),
                _valid_replication("rep_003"),
            ],
        ),
    ]
    common = ["rep_001", "rep_002", "rep_003"]
    payload: dict[str, object] = dict(  # noqa: C408
        schema_version="1.0",
        study_id="test_study",
        source_fingerprint=hashlib.sha256(b"test").hexdigest(),
        evidence_mode=ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION,
        admission_state=ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION,
        replication_unit=ResourceStrategyReplicationUnit.REPLICATION_ID,
        arms=arms,
        common_matched_replication_ids=common,
        excluded_replication_ids=[],
        metric_catalog=_catalog(),
        limitations=["synthetic"],
        provenance={"fixture": "test"},
        generated_at=None,
    )
    payload.update(overrides)
    return ResourceStrategyStudy.model_validate(payload)


# ---------------------------------------------------------------------------
# Strict validation
# ---------------------------------------------------------------------------


def test_strict_validation_rejects_extra_fields() -> None:
    payload = _study().model_dump(mode="json")
    payload["extra_field"] = "not allowed"
    with pytest.raises(ValidationError):
        ResourceStrategyStudy.model_validate(payload)


def test_strict_validation_rejects_wrong_types() -> None:
    with pytest.raises(ValidationError):
        ResourceStrategyLifecycle(
            offered="not_int",
            admitted=800,
            rejected=200,
            forwarded=400,
            started=760,
            compute_completed=720,
            returned=700,
            dropped=80,
            deadline_success=680,
        )


def test_unknown_versus_false_distinguished() -> None:
    # None (unknown) vs 0.0 (false/zero) must be distinct
    rep_unknown = _valid_replication("rep_001", queue_length_mean=None, resource_cost_units=None)
    rep_zero = _valid_replication("rep_001", queue_length_mean=0.0, resource_cost_units=0.0)
    assert rep_unknown.queue_length_mean is None
    assert rep_zero.queue_length_mean == 0.0
    # Fingerprints must differ
    arm_unknown = ResourceStrategyArm(
        arm_id="arm_a",
        label="A",
        description="d",
        strategy_type="t",
        replications=[rep_unknown, _valid_replication("rep_002")],
    )
    arm_zero = ResourceStrategyArm(
        arm_id="arm_a",
        label="A",
        description="d",
        strategy_type="t",
        replications=[rep_zero, _valid_replication("rep_002")],
    )
    study_unknown = _study(
        arms=[
            arm_unknown,
            ResourceStrategyArm(
                arm_id="arm_b",
                label="B",
                description="d",
                strategy_type="t2",
                replications=[_valid_replication("rep_001"), _valid_replication("rep_002")],
            ),
        ],
        common_matched_replication_ids=["rep_001", "rep_002"],
    )
    study_zero = _study(
        arms=[
            arm_zero,
            ResourceStrategyArm(
                arm_id="arm_b",
                label="B",
                description="d",
                strategy_type="t2",
                replications=[_valid_replication("rep_001"), _valid_replication("rep_002")],
            ),
        ],
        common_matched_replication_ids=["rep_001", "rep_002"],
    )
    assert study_unknown.fingerprint() != study_zero.fingerprint()
    # per_replication_disclosed True vs False also distinct
    cat_true = ResourceStrategyMetric(
        metric_key="task.latency.mean_ms",
        metric_version="1.0",
        unit="ms",
        denominator=ResourceStrategyMetricDenominator.COMPLETED_TASKS,
        per_replication_disclosed=True,
    )
    cat_false = ResourceStrategyMetric(
        metric_key="task.latency.mean_ms",
        metric_version="1.0",
        unit="ms",
        denominator=ResourceStrategyMetricDenominator.COMPLETED_TASKS,
        per_replication_disclosed=False,
    )
    assert cat_true.per_replication_disclosed is True
    assert cat_false.per_replication_disclosed is False
    study_true = _study(metric_catalog=[cat_true, _catalog()[0]])
    study_false = _study(metric_catalog=[cat_false, _catalog()[0]])
    assert study_true.fingerprint() != study_false.fingerprint()


# ---------------------------------------------------------------------------
# Deterministic identity
# ---------------------------------------------------------------------------


def test_deterministic_identity_across_temporary_roots() -> None:
    study = _study()
    fp1 = study.fingerprint()
    # Serialize and reload from a different temp directory path — fingerprint must not include path
    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        p1 = Path(td1) / "study.json"
        p2 = Path(td2) / "study.json"
        p1.write_text(study.to_json(), encoding="utf-8")
        p2.write_text(study.to_json(), encoding="utf-8")
        loaded1 = load_resource_strategy_study_file(p1)
        loaded2 = load_resource_strategy_study_file(p2)
        assert loaded1.fingerprint() == fp1
        assert loaded2.fingerprint() == fp1
        assert loaded1.fingerprint() == loaded2.fingerprint()
        # Also direct dict without file
        direct = load_resource_strategy_study_from_json(study.to_json())
        assert direct.fingerprint() == fp1


def test_arm_ordering_not_changing_identity() -> None:
    study = _study()
    # Reverse arm order
    reversed_arms = list(reversed(study.arms))
    study_reversed = _study(arms=reversed_arms)
    assert study.fingerprint() == study_reversed.fingerprint()
    report = build_resource_strategy_report(study)
    report_rev = build_resource_strategy_report(study_reversed)
    assert report.fingerprint() == report_rev.fingerprint()


def test_metric_values_and_denominators_changing_identity() -> None:
    study = _study()
    base_fp = study.fingerprint()
    # Change metric value in one replication
    mutated_arm = copy.deepcopy(study.arms[0])
    mutated_arm.replications[0].queue_length_mean = 999.0  # type: ignore[attr-defined]
    study_mutated = _study(arms=[mutated_arm, study.arms[1]])
    assert study_mutated.fingerprint() != base_fp
    # Change denominator
    cat = _catalog()
    cat[0] = ResourceStrategyMetric(
        metric_key=cat[0].metric_key,
        metric_version="1.0",
        unit="ratio",
        denominator=ResourceStrategyMetricDenominator.ADMITTED_TASKS,
    )
    study_denom = _study(metric_catalog=cat)
    assert study_denom.fingerprint() != base_fp


def test_admission_state_changing_identity() -> None:
    study = _study()
    base_fp = study.fingerprint()
    # Create admitted variant (needs evidence_mode consistent)
    admitted_study = ResourceStrategyStudy.model_validate(
        {
            **study.model_dump(mode="json"),
            "evidence_mode": ResourceStrategyEvidenceMode.ADMITTED_RESEARCH.value,
            "admission_state": ResourceStrategyAdmissionState.ADMITTED.value,
        }
    )
    assert admitted_study.fingerprint() != base_fp
    # Also synthetic vs admitted report fingerprint changes
    report_synth = build_resource_strategy_report(study)
    report_adm = build_resource_strategy_report(admitted_study)
    assert report_synth.fingerprint() != report_adm.fingerprint()


def test_excluded_replication_reasons_changing_identity() -> None:
    study = _study(
        common_matched_replication_ids=["rep_001", "rep_002"],
        excluded_replication_ids=[
            ResourceStrategyExclusion(
                replication_id="rep_003",
                code=ResourceStrategyExclusionCode.RSU_OUTAGE,
                reason="outage A",
            )
        ],
    )
    fp1 = study.fingerprint()
    study2 = _study(
        common_matched_replication_ids=["rep_001", "rep_002"],
        excluded_replication_ids=[
            ResourceStrategyExclusion(
                replication_id="rep_003",
                code=ResourceStrategyExclusionCode.RSU_OUTAGE,
                reason="outage B",
            )
        ],
    )
    assert fp1 != study2.fingerprint()


# ---------------------------------------------------------------------------
# Matched cohort and exclusions
# ---------------------------------------------------------------------------


def test_exact_matched_cohort_calculation() -> None:
    # Three arms with overlapping replications; excluded should be removed
    r1 = [
        _valid_replication("rep_001"),
        _valid_replication("rep_002"),
        _valid_replication("rep_003"),
    ]
    r2 = [
        _valid_replication("rep_001"),
        _valid_replication("rep_002"),
        _valid_replication("rep_004"),
    ]
    r3 = [
        _valid_replication("rep_001"),
        _valid_replication("rep_002"),
        _valid_replication("rep_003"),
        _valid_replication("rep_004"),
    ]
    arms = [
        ResourceStrategyArm(
            arm_id="a", label="A", description="d", strategy_type="t", replications=r1
        ),
        ResourceStrategyArm(
            arm_id="b", label="B", description="d", strategy_type="t", replications=r2
        ),
        ResourceStrategyArm(
            arm_id="c", label="C", description="d", strategy_type="t", replications=r3
        ),
    ]
    # Intersection is rep_001, rep_002
    study = _study(arms=arms, common_matched_replication_ids=["rep_001", "rep_002"])
    assert study.common_matched_replication_ids == ["rep_001", "rep_002"]
    report = build_resource_strategy_report(study)
    assert report.common_matched_replication_ids == ["rep_001", "rep_002"]
    # Add excluded rep_002 -> matched should be only rep_001
    study_ex = _study(
        arms=arms,
        common_matched_replication_ids=["rep_001"],
        excluded_replication_ids=[
            ResourceStrategyExclusion(
                replication_id="rep_002",
                code=ResourceStrategyExclusionCode.MANUAL_EXCLUSION,
                reason="manual",
            )
        ],
    )
    assert study_ex.common_matched_replication_ids == ["rep_001"]
    with pytest.raises(ValidationError, match="does not match computed matched cohort"):
        _study(
            arms=arms,
            common_matched_replication_ids=["rep_001", "rep_002"],
            excluded_replication_ids=[
                ResourceStrategyExclusion(
                    replication_id="rep_002",
                    code=ResourceStrategyExclusionCode.MANUAL_EXCLUSION,
                    reason="manual",
                )
            ],
        )


def test_excluded_replication_silently_entering_matched_cohort_is_rejected() -> None:
    # Directly test that validation catches excluded in matched
    arms = [
        ResourceStrategyArm(
            arm_id="a",
            label="A",
            description="d",
            strategy_type="t",
            replications=[_valid_replication("rep_001"), _valid_replication("rep_002")],
        ),
        ResourceStrategyArm(
            arm_id="b",
            label="B",
            description="d",
            strategy_type="t",
            replications=[_valid_replication("rep_001"), _valid_replication("rep_002")],
        ),
    ]
    # Try to include excluded rep in matched
    with pytest.raises(
        ValidationError, match="must not appear in matched cohort|does not match computed"
    ):
        _study(
            arms=arms,
            common_matched_replication_ids=["rep_001", "rep_002"],
            excluded_replication_ids=[
                ResourceStrategyExclusion(
                    replication_id="rep_002",
                    code=ResourceStrategyExclusionCode.RSU_OUTAGE,
                    reason="outage",
                )
            ],
        )


def test_incompatible_metric_versions_failing_closed() -> None:
    # Duplicate metric key triggers validation (simulates incompatible versions)
    cat = _catalog()
    dup = ResourceStrategyMetric(
        metric_key=cat[0].metric_key,
        metric_version="2.0",
        unit="ratio",
        denominator=cat[0].denominator,
    )
    with pytest.raises(ValidationError, match="duplicate metric_key"):
        _study(metric_catalog=[cat[0], dup])
    # Also test incompatible version handling
    # Ensure duplicate key with different version fails closed
    # Simulate via raw dict bypass
    study = _study()
    # Create incompatible via raw dict
    raw = study.model_dump(mode="json")
    raw["metric_catalog"].append(
        {
            "metric_key": "task.completion.rate_offered",
            "metric_version": "2.0",
            "unit": "ratio",
            "denominator": "offered_tasks",
            "description": "",
            "per_replication_disclosed": True,
        }
    )
    with pytest.raises(ValidationError):
        ResourceStrategyStudy.model_validate(raw)


def test_malformed_lifecycle_totals_fail_closed() -> None:
    # offered != admitted + rejected
    with pytest.raises(ValidationError, match="LIFECYCLE_CONSERVATION_VIOLATED"):
        ResourceStrategyLifecycle(
            offered=1000,
            admitted=800,
            rejected=100,
            forwarded=400,
            started=760,
            compute_completed=720,
            returned=700,
            dropped=80,
            deadline_success=680,
        )
    # started > admitted
    with pytest.raises(ValidationError, match="LIFECYCLE_CONSERVATION_VIOLATED"):
        ResourceStrategyLifecycle(
            offered=1000,
            admitted=700,
            rejected=300,
            forwarded=400,
            started=800,
            compute_completed=700,
            returned=680,
            dropped=20,
            deadline_success=600,
        )
    # compute_completed > started
    with pytest.raises(ValidationError, match="LIFECYCLE_CONSERVATION_VIOLATED"):
        ResourceStrategyLifecycle(
            offered=1000,
            admitted=800,
            rejected=200,
            forwarded=400,
            started=600,
            compute_completed=700,
            returned=680,
            dropped=20,
            deadline_success=600,
        )


def test_offered_vs_admitted_denominators_kept_separate() -> None:
    study = _study()
    report = build_resource_strategy_report(study)
    # Find aggregates for the two completion rates
    for arm in report.arm_summaries:
        offered = next(
            a for a in arm.metric_aggregates if a.metric_key == "task.completion.rate_offered"
        )
        admitted = next(
            a for a in arm.metric_aggregates if a.metric_key == "task.completion.rate_admitted"
        )
        assert offered.denominator == ResourceStrategyMetricDenominator.OFFERED_TASKS
        assert admitted.denominator == ResourceStrategyMetricDenominator.ADMITTED_TASKS
        # Denominators differ, so values must differ
        assert offered.aggregate_mean is not None and admitted.aggregate_mean is not None
        # Offered rate smaller than admitted (same completed, larger denominator)
        assert offered.aggregate_mean < admitted.aggregate_mean
        # Ensure not swapped: offered ~0.72, admitted ~0.9
        assert 0.6 < offered.aggregate_mean < 0.8
        assert 0.8 < admitted.aggregate_mean < 1.0
    # Pairwise differences must preserve denominator
    for diff in report.pairwise_differences:
        if diff.metric_key == "task.completion.rate_offered":
            assert diff.denominator == ResourceStrategyMetricDenominator.OFFERED_TASKS
        if diff.metric_key == "task.completion.rate_admitted":
            assert diff.denominator == ResourceStrategyMetricDenominator.ADMITTED_TASKS


def test_unadmitted_evidence_not_treated_as_admitted() -> None:
    study = _study(
        evidence_mode=ResourceStrategyEvidenceMode.UNADMITTED_RESEARCH,
        admission_state=ResourceStrategyAdmissionState.UNADMITTED,
    )
    with pytest.raises(ValueError, match="UNADMITTED_EVIDENCE"):
        build_resource_strategy_report(study)
    # Also test that study validation rejects inconsistent evidence/admission
    with pytest.raises(ValidationError):
        _study(
            evidence_mode=ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION,
            admission_state=ResourceStrategyAdmissionState.ADMITTED,
        )


def test_local_source_path_not_entering_fingerprint() -> None:
    study = _study()
    fp = study.fingerprint()
    # Simulate writing to two different paths and reloading; fingerprint must stay same
    with tempfile.TemporaryDirectory() as td:
        p1 = Path(td) / "a" / "study.json"
        p1.parent.mkdir(parents=True, exist_ok=True)
        p2 = Path(td) / "b" / "nested" / "study.json"
        p2.parent.mkdir(parents=True, exist_ok=True)
        json_text = study.to_json()
        p1.write_text(json_text, encoding="utf-8")
        p2.write_text(json_text, encoding="utf-8")
        loaded1 = load_resource_strategy_study_file(p1)
        loaded2 = load_resource_strategy_study_file(p2)
        assert loaded1.fingerprint() == fp
        assert loaded2.fingerprint() == fp
        # Even with path in provenance fingerprint changes; exclude path.
        # Provenance includes path would change fingerprint; exclude path.
        # Verify provenance has no local path; fingerprint excludes path.


def test_deterministic_arm_summaries_and_pairwise() -> None:
    study = _study()
    report1 = build_resource_strategy_report(study)
    report2 = build_resource_strategy_report(study)
    assert report1.fingerprint() == report2.fingerprint()
    assert report1.report_fingerprint == report2.report_fingerprint
    # Summaries deterministic
    for a1, a2 in zip(report1.arm_summaries, report2.arm_summaries, strict=True):
        assert a1.lifecycle_totals == a2.lifecycle_totals
        for agg1, agg2 in zip(a1.metric_aggregates, a2.metric_aggregates, strict=True):
            assert agg1.aggregate_mean == agg2.aggregate_mean
    # Pairwise deterministic
    assert report1.pairwise_differences == report2.pairwise_differences


def test_queue_and_resource_cost_evidence() -> None:
    study = _study()
    report = build_resource_strategy_report(study)
    for arm in report.arm_summaries:
        queue = next(a for a in arm.metric_aggregates if a.metric_key == "infra.queue_length.mean")
        assert queue.status.value in ("available", "partial")
        assert queue.aggregate_mean is not None
        cost = next(a for a in arm.metric_aggregates if a.metric_key == "resource.cost.units")
        assert cost.status.value in ("available", "partial")
    # Ensure resource cost is optional but present in fixture
    assert any(m.metric_key == "resource.cost.units" for m in study.metric_catalog)


def test_typed_unavailable_states() -> None:
    # Create study where one metric is missing for one arm (resource cost removed)
    # Ensure matched cohort valid; catalog missing key means unavailable not counted
    # Instead create replication with None for queue to test unavailable
    rep_none = _valid_replication("rep_001", queue_length_mean=None, queue_balance_jain=None)
    arms = [
        ResourceStrategyArm(
            arm_id="arm_a",
            label="A",
            description="d",
            strategy_type="t",
            replications=[rep_none, _valid_replication("rep_002"), _valid_replication("rep_003")],
        ),
        ResourceStrategyArm(
            arm_id="arm_b",
            label="B",
            description="d",
            strategy_type="t",
            replications=[
                _valid_replication("rep_001"),
                _valid_replication("rep_002"),
                _valid_replication("rep_003"),
            ],
        ),
    ]
    study = _study(arms=arms)
    report = build_resource_strategy_report(study)
    arm_a = next(a for a in report.arm_summaries if a.arm_id == "arm_a")
    q_agg = next(a for a in arm_a.metric_aggregates if a.metric_key == "infra.queue_length.mean")
    # Since one replication is None, status should be partial
    assert q_agg.status.value == "partial"
    assert q_agg.reason is not None


def test_export_json_and_csv_match_report() -> None:
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    report = build_resource_strategy_report(study)
    json_text = report.to_json()
    loaded = json.loads(json_text)
    assert loaded["study_id"] == study.study_id
    assert loaded["study_fingerprint"] == report.study_fingerprint
    assert loaded["report_fingerprint"] == report.report_fingerprint
    csv_text = resource_strategy_report_to_csv(report)
    assert "study_id" in csv_text.splitlines()[0]
    assert study.study_id in csv_text
    md = resource_strategy_report_to_markdown(report)
    assert "# Resource Strategy Report" in md
    assert study.study_id in md
    assert "Descriptive differences only" in md
    assert "winner" not in md.lower() or "no winner" in md.lower()


def test_end_to_end_load_build_render_export() -> None:
    # Simulate UI journey: load -> build -> export
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    assert study.evidence_mode == ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION
    assert study.admission_state == ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION
    report = build_resource_strategy_report(study)
    assert len(report.arm_summaries) == 3
    assert len(report.common_matched_replication_ids) == 4
    assert len(report.excluded_replication_ids) == 1
    # Verify that report contains expected metric denominators distinct
    assert any(
        m.denominator == ResourceStrategyMetricDenominator.OFFERED_TASKS
        for m in study.metric_catalog
    )
    assert any(
        m.denominator == ResourceStrategyMetricDenominator.ADMITTED_TASKS
        for m in study.metric_catalog
    )
    # Export must match report
    exported_json = report.to_json()
    assert hashlib.sha256(report.canonical_json().encode()).hexdigest() == report.fingerprint()
    assert json.loads(exported_json)["report_fingerprint"] == report.report_fingerprint


def test_inconsistent_lifecycle_totals_being_accepted_is_prevented() -> None:
    # Mutate a valid study to have inconsistent totals and ensure validation fails
    study = _study()
    mutated = copy.deepcopy(study)
    # Make offered not equal admitted+rejected for one replication
    mutated.arms[0].replications[
        0
    ].lifecycle.offered = 999  # admitted 800 + rejected 200 =1000 not 999
    with pytest.raises(ValidationError, match="LIFECYCLE_CONSERVATION_VIOLATED"):
        ResourceStrategyStudy.model_validate(mutated.model_dump(mode="json"))
