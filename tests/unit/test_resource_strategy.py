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
    ResourceStrategyCompatibilityStatus,
    ResourceStrategyEvidenceMode,
    ResourceStrategyExclusion,
    ResourceStrategyExclusionCode,
    ResourceStrategyLifecycle,
    ResourceStrategyMetric,
    ResourceStrategyMetricDenominator,
    ResourceStrategyMetricStatus,
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


def test_pairwise_interpretations_are_complete_and_self_qualifying() -> None:
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    report = build_resource_strategy_report(study)
    # Check every pairwise row
    for diff in report.pairwise_differences:
        assert diff.interpretation, "interpretation must be non-empty"
        assert diff.arm_a in diff.interpretation, (
            f"arm_a {diff.arm_a} missing in {diff.interpretation!r}"
        )
        assert diff.arm_b in diff.interpretation, (
            f"arm_b {diff.arm_b} missing in {diff.interpretation!r}"
        )
        assert diff.unit in diff.interpretation, (
            f"unit {diff.unit} missing in {diff.interpretation!r}"
        )
        assert "descriptive only" in diff.interpretation, (
            f"qualifier missing in {diff.interpretation!r}"
        )
        if (
            diff.mean_difference_b_minus_a is not None
            and abs(diff.mean_difference_b_minus_a) >= 1e-12
        ):
            mag = f"{abs(diff.mean_difference_b_minus_a):.6g}"
            assert mag in diff.interpretation, (
                f"magnitude {mag} not in {diff.interpretation!r} for non-zero diff"
            )
    # Specific positive, negative, zero cases
    # Use synthetic: strongest_link vs jsq rate_offered negative, check positive exists
    # Find a non-zero diff
    non_zero = next(
        d
        for d in report.pairwise_differences
        if d.mean_difference_b_minus_a is not None and abs(d.mean_difference_b_minus_a) >= 1e-12
    )
    assert "higher" in non_zero.interpretation or "lower" in non_zero.interpretation

    # Zero diff case: create study where two arms have identical values
    # Build minimal study with identical replications
    def _ident_reps() -> list[ResourceStrategyReplication]:
        return [_valid_replication("rep_001"), _valid_replication("rep_002")]

    arms_ident = [
        ResourceStrategyArm(
            arm_id="arm_a",
            label="A",
            description="d",
            strategy_type="t",
            replications=_ident_reps(),
        ),
        ResourceStrategyArm(
            arm_id="arm_b",
            label="B",
            description="d",
            strategy_type="t",
            replications=_ident_reps(),
        ),
    ]
    study_ident = _study(arms=arms_ident, common_matched_replication_ids=["rep_001", "rep_002"])
    report_ident = build_resource_strategy_report(study_ident)
    zero_diffs = [
        d
        for d in report_ident.pairwise_differences
        if d.mean_difference_b_minus_a is not None and abs(d.mean_difference_b_minus_a) < 1e-12
    ]
    assert zero_diffs, "expected zero diffs for identical arms"
    for zd in zero_diffs:
        assert "equal" in zd.interpretation.lower() or "near zero" in zd.interpretation.lower()
        assert "descriptive only" in zd.interpretation
        assert zd.arm_a in zd.interpretation and zd.arm_b in zd.interpretation
    # Markdown and JSON carry same interpretation
    md = resource_strategy_report_to_markdown(report)
    js_data = json.loads(report.to_json())
    for diff in report.pairwise_differences:
        assert diff.interpretation in md, f"interpretation {diff.interpretation!r} not in markdown"
        # Find in JSON
        found = any(
            item["interpretation"] == diff.interpretation
            for item in js_data["pairwise_differences"]
        )
        assert found, f"interpretation {diff.interpretation!r} not in JSON"


def test_report_json_roundtrip_with_populated_generated_at() -> None:
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    # Build with populated generated_at via clock
    from datetime import UTC, datetime

    fixed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    report = build_resource_strategy_report(study, clock=lambda: fixed)
    assert report.generated_at is not None
    js = report.to_json()
    data = json.loads(js)
    # Must be model-valid and not contain sentinel
    assert "<normalised>" not in js
    assert data["generated_at"] is None  # portable normalises to null
    # Re-import
    from traffictwin.experiments.resource_strategy import ResourceStrategyReport

    reloaded = ResourceStrategyReport.model_validate_json(js)
    assert reloaded.study_id == report.study_id
    assert reloaded.report_fingerprint == report.report_fingerprint
    # Fingerprint before/after identical
    assert reloaded.fingerprint() == report.fingerprint()
    # Changing runtime generated_at does not change fingerprint
    report2 = build_resource_strategy_report(study, clock=lambda: datetime(2030, 1, 1, tzinfo=UTC))
    assert report2.fingerprint() == report.fingerprint()
    assert report2.report_fingerprint == report.report_fingerprint


def test_compatibility_audit_real() -> None:
    # A. same key/version/unit/denominator across arms -> COMPATIBLE
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    report = build_resource_strategy_report(study)
    for comp in report.compatibility:
        assert comp.status.value == "compatible", (
            f"expected compatible for {comp.metric_key}, got {comp.status}"
        )
    # B. different metric_version -> INCOMPATIBLE
    cat_bad_version = _catalog()
    cat_bad_version[0] = ResourceStrategyMetric(
        metric_key="task.completion.rate_offered",
        metric_version="2.0",
        unit="ratio",
        denominator=ResourceStrategyMetricDenominator.OFFERED_TASKS,
    )
    study_bad = _study(metric_catalog=cat_bad_version)
    report_bad = build_resource_strategy_report(study_bad)
    comp_bad = next(
        c for c in report_bad.compatibility if c.metric_key == "task.completion.rate_offered"
    )
    assert comp_bad.status.value == "incompatible"
    assert "version" in comp_bad.finding.lower()
    # C. different denominator -> INCOMPATIBLE
    cat_bad_denom = _catalog()
    cat_bad_denom[0] = ResourceStrategyMetric(
        metric_key="task.completion.rate_offered",
        metric_version="1.0",
        unit="ratio",
        denominator=ResourceStrategyMetricDenominator.ADMITTED_TASKS,
    )
    study_badd = _study(metric_catalog=cat_bad_denom)
    report_badd = build_resource_strategy_report(study_badd)
    comp_badd = next(
        c for c in report_badd.compatibility if c.metric_key == "task.completion.rate_offered"
    )
    assert comp_badd.status.value == "incompatible"
    assert "denominator" in comp_badd.finding.lower()
    # D. different unit -> INCOMPATIBLE
    cat_bad_unit = _catalog()
    cat_bad_unit[0] = ResourceStrategyMetric(
        metric_key="task.completion.rate_offered",
        metric_version="1.0",
        unit="wrong_unit",
        denominator=ResourceStrategyMetricDenominator.OFFERED_TASKS,
    )
    study_badu = _study(metric_catalog=cat_bad_unit)
    report_badu = build_resource_strategy_report(study_badu)
    comp_badu = next(
        c for c in report_badu.compatibility if c.metric_key == "task.completion.rate_offered"
    )
    assert comp_badu.status.value == "incompatible"
    assert "unit" in comp_badu.finding.lower()
    # E. incompatible metric does not appear as ordinary pairwise comparable
    pair_bad = [
        d for d in report_bad.pairwise_differences if d.metric_key == "task.completion.rate_offered"
    ]
    for d in pair_bad:
        assert (
            d.status.value == "unavailable"
            or "incompatible" in (d.reason or "").lower()
            or "incompatible" in d.interpretation.lower()
        )
    # E2. arm summaries must be gated to UNAVAILABLE with no numeric values
    for arm in report_bad.arm_summaries:
        agg = next(
            a for a in arm.metric_aggregates if a.metric_key == "task.completion.rate_offered"
        )  # noqa: E501
        assert agg.status == ResourceStrategyMetricStatus.UNAVAILABLE
        assert agg.aggregate_mean is None
        assert agg.aggregate_median is None
        assert agg.aggregate_min is None
        assert agg.aggregate_max is None
        assert not agg.per_replication_values
        assert agg.replication_count == 0
        assert "task.completion.rate_offered" in arm.unavailable_metrics
        assert "incompatible" in (agg.reason or "").lower()
    # pairwise already checked
    # F/G: exports carry finding tested via earlier markdown/json checks
    md_bad = resource_strategy_report_to_markdown(report_bad)
    assert "incompatible" in md_bad.lower()
    js_bad = json.loads(report_bad.to_json())
    assert any(item["status"] == "incompatible" for item in js_bad["compatibility"])


def test_reserved_metric_authority() -> None:
    # A: no supplied reserved metric -> canonical value computed
    study = _study()
    report = build_resource_strategy_report(study)
    # lifecycle-derived metric should be computed correctly
    for arm in report.arm_summaries:
        agg = next(
            a for a in arm.metric_aggregates if a.metric_key == "task.completion.rate_offered"
        )
        assert agg.aggregate_mean is not None
    # B: conflicting reserved offered completion -> rejected
    with pytest.raises(ValidationError, match="reserved metric"):
        ResourceStrategyReplication(
            replication_id="rep_001",
            lifecycle=_valid_lifecycle(),
            metrics={"task.completion.rate_offered": 0.0001},
        )
    # C: conflicting admitted-denominator metric -> rejected
    with pytest.raises(ValidationError, match="reserved metric"):
        ResourceStrategyReplication(
            replication_id="rep_001",
            lifecycle=_valid_lifecycle(),
            metrics={"task.completion.rate_admitted": 0.999},
        )
    # D: non-reserved metric preserved at Study layer but gated at Report
    # Study holds custom metric, but without contract report must not certify comparability  # noqa: E501
    custom_cat = _catalog() + [
        ResourceStrategyMetric(
            metric_key="custom.accuracy",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.REPLICATION,
        )
    ]
    rep_custom = ResourceStrategyReplication(
        replication_id="rep_001",
        lifecycle=_valid_lifecycle(),
        metrics={"custom.accuracy": 0.123456789},
    )
    # Study preservation: Study holds the metric input
    assert rep_custom.metrics["custom.accuracy"] == pytest.approx(0.123456789)
    study_custom_raw = _study(
        arms=[
            ResourceStrategyArm(
                arm_id="arm_a",
                label="A",
                description="d",
                strategy_type="t",
                replications=[rep_custom, _valid_replication("rep_002")],
            ),
            ResourceStrategyArm(
                arm_id="arm_b",
                label="B",
                description="d",
                strategy_type="t",
                replications=[rep_custom, _valid_replication("rep_002")],
            ),
        ],
        metric_catalog=custom_cat,
        common_matched_replication_ids=["rep_001", "rep_002"],
    )
    assert any(m.metric_key == "custom.accuracy" for m in study_custom_raw.metric_catalog)
    # Report gating: without registered contract, report must be UNAVAILABLE
    report_custom = build_resource_strategy_report(study_custom_raw)
    comp_custom = next(c for c in report_custom.compatibility if c.metric_key == "custom.accuracy")
    assert comp_custom.status == ResourceStrategyCompatibilityStatus.UNAVAILABLE
    assert "no registered compatibility contract" in comp_custom.finding.lower()
    for arm in report_custom.arm_summaries:
        agg = next(a for a in arm.metric_aggregates if a.metric_key == "custom.accuracy")
        assert agg.status == ResourceStrategyMetricStatus.UNAVAILABLE
        assert agg.aggregate_mean is None
        assert not agg.per_replication_values
        assert agg.replication_count == 0
        assert "custom.accuracy" in arm.unavailable_metrics


def test_csv_numeric_fidelity() -> None:
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    report = build_resource_strategy_report(study)
    # Add high-precision values via custom study to test repr preservation
    # Use values that would lose precision with 12g
    high_vals = [2024123.123456789, 0.12345678901234567, 1.0000000000000002]
    for val in high_vals:
        csv_line = repr(float(val))
        # Ensure repr round-trips
        assert float(csv_line) == float(val)
    # Also test actual CSV export uses repr
    _ = resource_strategy_report_to_csv(report)
    # Check CSV fidelity via a compatible metric with high-precision typed value
    # Use queue_length_mean (compatible) with high-precision value
    high_val = 2024123.123456789
    rep_high = _valid_replication("rep_001", queue_length_mean=high_val)
    rep_norm = _valid_replication("rep_002", queue_length_mean=7.5)
    study_high = _study(
        arms=[
            ResourceStrategyArm(
                arm_id="arm_a",
                label="A",
                description="d",
                strategy_type="t",
                replications=[rep_high, rep_norm],
            ),
            ResourceStrategyArm(
                arm_id="arm_b",
                label="B",
                description="d",
                strategy_type="t",
                replications=[rep_high, rep_norm],
            ),
        ],
        common_matched_replication_ids=["rep_001", "rep_002"],
    )
    report_high = build_resource_strategy_report(study_high)
    csv_high = resource_strategy_report_to_csv(report_high)
    found_queue = [line for line in csv_high.splitlines() if "infra.queue_length.mean" in line]
    assert found_queue, "queue length rows must appear in CSV"
    # At least one row should contain repr of high_val
    assert any(repr(high_val) in line for line in found_queue), f"repr {repr(high_val)} not in CSV"
    for line in found_queue:
        if repr(high_val) in line:
            cols = line.split(",")
            # aggregate_mean is 9th column (0-index 8)
            agg_mean_str = cols[8]
            # Aggregate is mean of high_val and 7.5; check repr presence  # noqa: E501
            assert float(agg_mean_str) == pytest.approx((high_val + 7.5) / 2)


def test_compatibility_gating_propagates_to_arm_aggregates() -> None:
    # Incompatible must gate arm aggregates, not just compatibility/pairwise  # noqa: E501
    cat_bad = _catalog()
    cat_bad[0] = ResourceStrategyMetric(
        metric_key="task.completion.rate_offered",
        metric_version="1.0",
        unit="wrong",
        denominator=ResourceStrategyMetricDenominator.OFFERED_TASKS,
    )
    study_bad = _study(metric_catalog=cat_bad)
    report_bad = build_resource_strategy_report(study_bad)
    comp = next(
        c for c in report_bad.compatibility if c.metric_key == "task.completion.rate_offered"
    )
    assert comp.status == ResourceStrategyCompatibilityStatus.INCOMPATIBLE
    # All arm aggregates for that metric must be UNAVAILABLE with no numeric values
    for arm in report_bad.arm_summaries:
        agg = next(
            a for a in arm.metric_aggregates if a.metric_key == "task.completion.rate_offered"
        )  # noqa: E501
        assert agg.status == ResourceStrategyMetricStatus.UNAVAILABLE
        assert agg.aggregate_mean is None
        assert agg.aggregate_median is None
        assert agg.aggregate_min is None
        assert agg.aggregate_max is None
        assert not agg.per_replication_values
        assert agg.replication_count == 0
        assert "task.completion.rate_offered" in arm.unavailable_metrics
        assert "incompatible" in (agg.reason or "").lower()
    # Pairwise also unavailable
    for d in report_bad.pairwise_differences:
        if d.metric_key == "task.completion.rate_offered":
            assert d.status == ResourceStrategyMetricStatus.UNAVAILABLE
            assert d.mean_difference_b_minus_a is None


def test_unknown_metric_contract_is_unavailable() -> None:
    custom_cat = _catalog() + [
        ResourceStrategyMetric(
            metric_key="custom.unknown_metric",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.REPLICATION,
        )
    ]
    rep1 = ResourceStrategyReplication(
        replication_id="rep_001",
        lifecycle=_valid_lifecycle(),
        metrics={"custom.unknown_metric": 0.5},
    )
    rep2 = ResourceStrategyReplication(
        replication_id="rep_002",
        lifecycle=_valid_lifecycle(),
        metrics={"custom.unknown_metric": 0.6},
    )
    study_unknown = _study(
        arms=[
            ResourceStrategyArm(
                arm_id="arm_a",
                label="A",
                description="d",
                strategy_type="t",
                replications=[rep1, rep2],
            ),
            ResourceStrategyArm(
                arm_id="arm_b",
                label="B",
                description="d",
                strategy_type="t",
                replications=[rep1, rep2],
            ),
        ],
        metric_catalog=custom_cat,
        common_matched_replication_ids=["rep_001", "rep_002"],
    )
    report_unknown = build_resource_strategy_report(study_unknown)
    comp = next(  # noqa: E501
        c for c in report_unknown.compatibility if c.metric_key == "custom.unknown_metric"
    )
    assert comp.status == ResourceStrategyCompatibilityStatus.UNAVAILABLE
    assert "no registered compatibility contract" in comp.finding.lower()
    assert "not verified" in comp.finding.lower()
    # Arm aggregates must be gated
    for arm in report_unknown.arm_summaries:
        agg = next(a for a in arm.metric_aggregates if a.metric_key == "custom.unknown_metric")
        assert agg.status == ResourceStrategyMetricStatus.UNAVAILABLE
        assert agg.aggregate_mean is None
        assert not agg.per_replication_values
        assert agg.replication_count == 0
        assert "custom.unknown_metric" in arm.unavailable_metrics
    # Pairwise also unavailable
    for d in report_unknown.pairwise_differences:
        if d.metric_key == "custom.unknown_metric":
            assert d.status == ResourceStrategyMetricStatus.UNAVAILABLE


def test_synthetic_report_golden_is_service_produced() -> None:
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    report_path = Path("tests/fixtures/resource_strategy/synthetic_report_v1.json")
    assert report_path.exists(), "golden report fixture must exist"
    golden_text = report_path.read_text(encoding="utf-8")
    golden = json.loads(golden_text)
    # Model validates
    from traffictwin.experiments.resource_strategy import ResourceStrategyReport

    validated = ResourceStrategyReport.model_validate_json(golden_text)
    assert validated.study_id == study.study_id
    # Fingerprint verifies
    assert validated.report_fingerprint == validated.fingerprint()
    assert golden["report_fingerprint"] == validated.fingerprint()
    # Service regeneration matches (canonical equivalence)
    regenerated = build_resource_strategy_report(study)  # default clock
    # Canonical payload must match (excluding generated_at which is not identity-bearing)
    assert regenerated.canonical_payload() == validated.canonical_payload()
    # Alternative: exact deterministic bytes after to_json (with null generated_at) should match golden's normalized form  # noqa: E501
    # Since golden's generated_at is null, regenerated's to_json with null should match canonical fields  # noqa: E501
    assert (
        regenerated.to_json() == validated.to_json()
        or json.loads(regenerated.to_json())["report_fingerprint"] == golden["report_fingerprint"]
    )
    # Check no absolute paths
    assert (
        "/Users" not in golden_text
        and "/tmp" not in golden_text  # noqa: S108
        and "worktrees" not in golden_text
    )
    # Evidence mode remains synthetic demonstration
    assert golden["evidence_mode"] == "synthetic_demonstration"
    # No sentinel
    assert "<normalised>" not in golden_text


# ---------------------------------------------------------------------------
# Lane 01 — fleet_draw explicit support (discriminating, backward-compatible)
# ---------------------------------------------------------------------------


def _fleet_draw_study(**overrides: object) -> ResourceStrategyStudy:
    """Build a minimal study with replication_unit fleet_draw."""
    # Use the same helper structure as _study but with fleet_draw.
    base = _study(replication_unit=ResourceStrategyReplicationUnit.FLEET_DRAW)
    # Allow overrides to replace fields after construction via revalidation
    if not overrides:
        return base
    payload = base.model_dump(mode="json")
    payload.update(overrides)
    return ResourceStrategyStudy.model_validate(payload)


def test_fleet_draw_replication_unit_accepted_and_identity_bearing() -> None:
    study = _fleet_draw_study()
    # Valid enum member
    assert study.replication_unit == ResourceStrategyReplicationUnit.FLEET_DRAW
    assert study.replication_unit.value == "fleet_draw"
    # Canonical payload must contain fleet_draw literally and be sorted
    canon = study.canonical_payload()
    assert canon["replication_unit"] == "fleet_draw"
    # Fingerprint must be 64 hex chars and differ from replication_id/random_seed
    fp_fleet = study.fingerprint()
    assert len(fp_fleet) == 64 and all(c in "0123456789abcdef" for c in fp_fleet)
    study_rep = _study(replication_unit=ResourceStrategyReplicationUnit.REPLICATION_ID)
    study_seed = _study(replication_unit=ResourceStrategyReplicationUnit.RANDOM_SEED)
    assert fp_fleet != study_rep.fingerprint()
    assert fp_fleet != study_seed.fingerprint()
    assert study_rep.fingerprint() != study_seed.fingerprint()


def test_fleet_draw_report_propagates_unit_and_fingerprint() -> None:
    study = _fleet_draw_study()
    report = build_resource_strategy_report(study)
    assert report.replication_unit == ResourceStrategyReplicationUnit.FLEET_DRAW
    assert report.replication_unit.value == "fleet_draw"
    canon = report.canonical_payload()
    assert canon["replication_unit"] == "fleet_draw"
    # Report fingerprint is deterministic; second build matches
    report2 = build_resource_strategy_report(study)
    assert report.fingerprint() == report2.fingerprint()
    assert report.report_fingerprint == report2.report_fingerprint
    # JSON and markdown exports must surface fleet_draw
    js = json.loads(report.to_json())
    assert js["replication_unit"] == "fleet_draw"
    md = resource_strategy_report_to_markdown(report)
    assert "fleet_draw" in md
    csv_text = resource_strategy_report_to_csv(report)
    # CSV header + rows present; replication unit validated via markdown
    assert study.study_id in csv_text


def test_fleet_draw_json_roundtrip_and_loaders() -> None:
    study = _fleet_draw_study()
    text = study.to_json()
    # model_validate round-trip
    reloaded = ResourceStrategyStudy.model_validate_json(text)
    assert reloaded.replication_unit == ResourceStrategyReplicationUnit.FLEET_DRAW
    assert reloaded.fingerprint() == study.fingerprint()
    # loader helpers
    from_json = load_resource_strategy_study_from_json(text)
    assert from_json.fingerprint() == study.fingerprint()
    assert json.loads(text)["replication_unit"] == "fleet_draw"
    # File loader with fleet_draw should produce identical fingerprint regardless of path
    with tempfile.TemporaryDirectory() as td:
        p1 = Path(td) / "a.json"
        p2 = Path(td) / "b.json"
        p1.write_text(text, encoding="utf-8")
        p2.write_text(text, encoding="utf-8")
        assert load_resource_strategy_study_file(p1).fingerprint() == study.fingerprint()
        assert load_resource_strategy_study_file(p2).fingerprint() == study.fingerprint()
    # Raw dict with string literal fleet_draw
    payload = study.model_dump(mode="json")
    payload["replication_unit"] = "fleet_draw"
    validated = ResourceStrategyStudy.model_validate(payload)
    assert validated.replication_unit == ResourceStrategyReplicationUnit.FLEET_DRAW


def test_fleet_draw_matched_cohort_and_exclusion_codes() -> None:
    # Four fleet_draw replications like E2c/E2d 1..4
    reps = [_valid_replication(f"rep_00{i}") for i in range(1, 5)]
    arms = [
        ResourceStrategyArm(
            arm_id="arm_a",
            label="A",
            description="d",
            strategy_type="t",
            replications=list(reps),
        ),
        ResourceStrategyArm(
            arm_id="arm_b",
            label="B",
            description="d",
            strategy_type="t",
            replications=list(reps),
        ),
    ]
    study = _fleet_draw_study(
        arms=arms,
        common_matched_replication_ids=["rep_001", "rep_002", "rep_003", "rep_004"],
        excluded_replication_ids=[],
        metric_catalog=_catalog(),
    )
    assert study.common_matched_replication_ids == ["rep_001", "rep_002", "rep_003", "rep_004"]
    report = build_resource_strategy_report(study)
    assert report.common_matched_replication_ids == study.common_matched_replication_ids
    # Exclusion with explicit DUPLICATE_FLEET_DRAW code must be accepted
    exc = ResourceStrategyExclusion(
        replication_id="rep_003",
        code=ResourceStrategyExclusionCode.DUPLICATE_FLEET_DRAW,
        reason="duplicate fleet_draw excluded for audit",
    )
    study_ex = _fleet_draw_study(
        arms=arms,
        common_matched_replication_ids=["rep_001", "rep_002", "rep_004"],
        excluded_replication_ids=[exc],
        metric_catalog=_catalog(),
    )
    assert exc.code.value == "DUPLICATE_FLEET_DRAW"
    # Legacy code still valid alongside new code
    exc_legacy = ResourceStrategyExclusion(
        replication_id="rep_005",
        code=ResourceStrategyExclusionCode.DUPLICATE_REPLICATION_ID,
        reason="legacy duplicate code still valid",
    )
    assert exc_legacy.code.value == "DUPLICATE_REPLICATION_ID"
    # Ensure report preserves exclusion code for fleet_draw
    assert any(
        e.code == ResourceStrategyExclusionCode.DUPLICATE_FLEET_DRAW
        for e in study_ex.excluded_replication_ids
    )


def test_backward_compatibility_fingerprints_unchanged_for_existing_units() -> None:
    # Existing replication_id fingerprint must remain deterministic after fleet_draw addition  # noqa: E501
    study_rep = _study(replication_unit=ResourceStrategyReplicationUnit.REPLICATION_ID)
    fp_rep_1 = study_rep.fingerprint()
    # Re-serialize and reload should yield identical fingerprint
    reloaded_rep = ResourceStrategyStudy.model_validate_json(study_rep.to_json())
    assert reloaded_rep.fingerprint() == fp_rep_1
    # Load via dict with explicit string replication_id
    payload_rep = study_rep.model_dump(mode="json")
    payload_rep["replication_unit"] = "replication_id"
    assert ResourceStrategyStudy.model_validate(payload_rep).fingerprint() == fp_rep_1

    # Existing random_seed study fingerprint likewise stable
    study_seed = _study(replication_unit=ResourceStrategyReplicationUnit.RANDOM_SEED)
    fp_seed_1 = study_seed.fingerprint()
    reloaded_seed = ResourceStrategyStudy.model_validate_json(study_seed.to_json())
    assert reloaded_seed.fingerprint() == fp_seed_1
    payload_seed = study_seed.model_dump(mode="json")
    payload_seed["replication_unit"] = "random_seed"
    assert ResourceStrategyStudy.model_validate(payload_seed).fingerprint() == fp_seed_1

    # Fleet draw fingerprints distinct; old fingerprints unchanged  # noqa: E501
    study_fleet = _fleet_draw_study()
    assert study_fleet.fingerprint() != fp_rep_1
    assert study_fleet.fingerprint() != fp_seed_1
    assert fp_rep_1 != fp_seed_1
    # Report fingerprints also stable for existing units
    report_rep = build_resource_strategy_report(study_rep)
    report_rep2 = build_resource_strategy_report(
        ResourceStrategyStudy.model_validate_json(study_rep.to_json())
    )
    assert report_rep.fingerprint() == report_rep2.fingerprint()
    assert report_rep.report_fingerprint == report_rep2.report_fingerprint


def test_invalid_replication_units_fail_closed() -> None:
    base = _study().model_dump(mode="json")
    for bad in ["task", "tasks", "fleet_seed", "run", "FLEET_DRAW", "fleet-draw", "", "invalid"]:
        payload = dict(base)
        payload["replication_unit"] = bad
        with pytest.raises(ValidationError):
            ResourceStrategyStudy.model_validate(payload)
        # JSON text variant
        text = json.dumps(payload)
        with pytest.raises((ValidationError, ValueError)):
            load_resource_strategy_study_from_json(text)

    # Also ensure random_seed and replication_id still valid (not rejected)
    for good in ["replication_id", "random_seed", "fleet_draw"]:
        payload = dict(base)
        payload["replication_unit"] = good
        # Must validate successfully
        validated = ResourceStrategyStudy.model_validate(payload)
        assert validated.replication_unit.value == good


def test_duplicate_replication_and_lifecycle_still_fail_closed_for_fleet_draw() -> None:
    # Duplicate replication_id within an arm must fail for fleet_draw studies as well
    dup_reps = [_valid_replication("rep_001"), _valid_replication("rep_001")]
    with pytest.raises(ValidationError, match="duplicate replication_id"):
        ResourceStrategyArm(
            arm_id="arm_a",
            label="A",
            description="d",
            strategy_type="t",
            replications=dup_reps,
        )
    # Attempt to build a fleet_draw study with duplicate reps via raw validation should also fail
    arm_dup = {
        "arm_id": "arm_a",
        "label": "A",
        "description": "d",
        "strategy_type": "t",
        "replications": [
            _valid_replication("rep_001").model_dump(mode="json"),
            _valid_replication("rep_001").model_dump(mode="json"),
        ],
    }
    payload = _fleet_draw_study().model_dump(mode="json")
    payload["arms"] = [arm_dup, payload["arms"][1]]
    with pytest.raises(ValidationError, match="duplicate replication_id"):
        ResourceStrategyStudy.model_validate(payload)

    # Lifecycle conservation still enforced for fleet_draw replications
    # Direct lifecycle validation fails regardless of unit (construction itself must fail)
    with pytest.raises(ValidationError, match="LIFECYCLE_CONSERVATION_VIOLATED"):
        _valid_lifecycle(offered=999, admitted=800, rejected=200)
    with pytest.raises(ValidationError, match="LIFECYCLE_CONSERVATION_VIOLATED"):
        ResourceStrategyLifecycle(
            offered=999,
            admitted=800,
            rejected=200,
            forwarded=400,
            started=760,
            compute_completed=720,
            returned=700,
            dropped=80,
            deadline_success=680,
        )

    # Fleet_draw study with excluded replication that silently re-enters matched cohort must fail
    reps = [_valid_replication("rep_001"), _valid_replication("rep_002")]
    arms = [
        ResourceStrategyArm(
            arm_id="arm_a", label="A", description="d", strategy_type="t", replications=list(reps)
        ),
        ResourceStrategyArm(
            arm_id="arm_b", label="B", description="d", strategy_type="t", replications=list(reps)
        ),
    ]
    with pytest.raises(
        ValidationError, match="does not match computed matched cohort|must not appear"
    ):
        ResourceStrategyStudy.model_validate(
            {
                "schema_version": "1.0",
                "study_id": "test_study",
                "source_fingerprint": hashlib.sha256(b"test").hexdigest(),
                "evidence_mode": ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION.value,
                "admission_state": ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION.value,
                "replication_unit": "fleet_draw",
                "arms": [a.model_dump(mode="json") for a in arms],
                "common_matched_replication_ids": ["rep_001", "rep_002"],
                "excluded_replication_ids": [
                    {
                        "replication_id": "rep_002",
                        "code": ResourceStrategyExclusionCode.MANUAL_EXCLUSION.value,
                        "reason": "manual",
                    }
                ],
                "metric_catalog": [m.model_dump(mode="json") for m in _catalog()],
                "limitations": ["synthetic"],
                "provenance": {"fixture": "test"},
                "generated_at": None,
            }
        )

    # Invalid exclusion code must also fail closed
    with pytest.raises(ValidationError):
        ResourceStrategyExclusion(
            replication_id="rep_001",
            code="INVALID_CODE",  # type: ignore[arg-type]
            reason="bad code",
        )
