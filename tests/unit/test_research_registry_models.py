"""Strong mutation/discriminating tests for ResearchStudyRecord family."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from traffictwin.research_registry import (
    AdmissionStatus,
    DeclaredSummary,
    EvidenceStanding,
    PerDrawValue,
    ResearchStudyRecord,
    StudyStatus,
)

HEX40_A = "a" * 40
HEX40_B = "b" * 40
HEX64_A = "c" * 64
HEX64_B = "d" * 64
HEX64_C = "e" * 64
HEX64_D = "f" * 64


def _minimal_valid(
    *,
    study: str = "S-001",
    version: str = "1.0",
    status: StudyStatus = StudyStatus.PLANNED,
    evidence: EvidenceStanding = EvidenceStanding.UNAVAILABLE,
    admission: AdmissionStatus = AdmissionStatus.NOT_APPLICABLE,
    **overrides: object,
) -> ResearchStudyRecord:
    base: dict[str, object] = {
        "study": study,
        "version": version,
        "title": "Test study title",
        "question": "Does per-task placement improve deadline attainment under varying load?",
        "hypothesis": "Per-task placement improves attainment",
        "status": status,
        "evidence_standing": evidence,
        "admission_status": admission,
    }
    base.update(overrides)  # type: ignore[arg-type]
    return ResearchStudyRecord.model_validate(base)


# ---------------------------------------------------------------------------
# Valid cases
# ---------------------------------------------------------------------------


def test_valid_future_unavailable_without_evidence() -> None:
    rec = _minimal_valid(
        study="E3",
        version="0.1",
        status=StudyStatus.PLANNED,
        evidence=EvidenceStanding.UNAVAILABLE,
        admission=AdmissionStatus.NOT_APPLICABLE,
    )
    assert rec.study == "E3"
    assert rec.code_sha is None
    assert rec.manifest_hash is None
    j1 = rec.canonical_json()
    j2 = rec.canonical_json()
    assert j1 == j2
    assert rec.fingerprint() == hashlib.sha256(j1.encode()).hexdigest()


def test_valid_completed_with_evidence_requires_hashes() -> None:
    rec = _minimal_valid(
        study="E2",
        version="1.0",
        status=StudyStatus.COMPLETED,
        evidence=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission=AdmissionStatus.ADMITTED,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
        evaluator_id="eval-0",
        actor_id=HEX64_B,
        checkpoint_id=HEX64_C,
        trace_id=HEX64_D,
        replication_unit="fleet_draw",
        seeds=[1, 2, 3, 4],
        draws=[1, 2, 3, 4],
        arms=["off", "jsq", "dla"],
        estimand="difference in offered_task_deadline_attainment",
        primary_metrics=["offered_task_deadline_attainment"],
        secondary_metrics=["admitted_diagnostic"],
        per_draw_values=[
            PerDrawValue(
                draw=i, value=float(i) * 0.01, arm="dla", metric="offered_task_deadline_attainment"
            )
            for i in [1, 2, 3, 4]
        ],
        declared_summary=DeclaredSummary(
            estimate=0.01, ci_lower=0.005, ci_upper=0.015, method="t-interval"
        ),
        limitations=["one Manchester incident hour", "four matched draws"],
        non_claims=["no population inference", "no universal superiority"],
        product_links=["docs/evidence/e2_summary.md", "reports/e2_report.html"],
    )
    assert rec.code_sha == HEX40_A
    assert rec.arms == sorted(["off", "jsq", "dla"])
    assert rec.seeds == [1, 2, 3, 4]
    fp = rec.fingerprint()
    assert len(fp) == 64
    rec2 = ResearchStudyRecord.from_canonical_json(rec.canonical_json())
    assert rec2 == rec


def test_valid_with_relationships_sorted() -> None:
    rec = _minimal_valid(
        study="S-010",
        predecessor=["S-009", "S-001"],
        successor=["S-011"],
        supersedes=["S-002"],
    )
    assert rec.predecessor == sorted(["S-009", "S-001"])
    assert rec.supersedes == ["S-002"]


def test_valid_draws_and_arms_sorted_deterministically() -> None:
    rec = _minimal_valid(seeds=[4, 1, 3, 2], arms=["dla", "off", "jsq"])
    assert rec.seeds == [1, 2, 3, 4]
    assert rec.arms == ["dla", "jsq", "off"]


# ---------------------------------------------------------------------------
# Fail closed: extra fields
# ---------------------------------------------------------------------------


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError, match="extra"):
        ResearchStudyRecord.model_validate(
            {
                "study": "S-001",
                "version": "1.0",
                "title": "t",
                "question": "q?" * 20,
                "status": "planned",
                "evidence_standing": "unavailable",
                "admission_status": "not_applicable",
                "unexpected_extra": "oops",
            }
        )


def test_extra_nested_forbidden() -> None:
    with pytest.raises(ValidationError):
        PerDrawValue.model_validate({"draw": 1, "value": 0.5, "extra": "nope"})


# ---------------------------------------------------------------------------
# Fail closed: nonfinite values
# ---------------------------------------------------------------------------


def test_nonfinite_per_draw_rejected() -> None:
    with pytest.raises(ValidationError, match="finite"):
        PerDrawValue(draw=1, value=float("inf"))
    with pytest.raises(ValidationError, match="finite"):
        PerDrawValue(draw=1, value=float("nan"))
    with pytest.raises(ValidationError, match="finite"):
        DeclaredSummary(estimate=float("inf"), ci_lower=0.0, ci_upper=1.0)


def test_nonfinite_declared_summary_rejected() -> None:
    with pytest.raises(ValidationError, match="finite"):
        DeclaredSummary(estimate=0.1, ci_lower=float("-inf"), ci_upper=0.2)


# ---------------------------------------------------------------------------
# Fail closed: duplicate identities
# ---------------------------------------------------------------------------


def test_duplicate_arms_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _minimal_valid(arms=["off", "off"])


def test_duplicate_seeds_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _minimal_valid(seeds=[1, 1, 2])


def test_duplicate_metrics_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _minimal_valid(primary_metrics=["m1", "m1"])


def test_duplicate_primary_secondary_overlap_rejected() -> None:
    with pytest.raises(ValidationError, match="overlap|duplicate"):
        _minimal_valid(primary_metrics=["m1", "m2"], secondary_metrics=["m2", "m3"])


def test_duplicate_per_draw_identity_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _minimal_valid(
            per_draw_values=[
                PerDrawValue(draw=1, value=0.1, arm="a", metric="m"),
                PerDrawValue(draw=1, value=0.2, arm="a", metric="m"),
            ]
        )


def test_duplicate_relationship_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _minimal_valid(predecessor=["S-001", "S-001"])


def test_duplicate_product_links_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _minimal_valid(product_links=["docs/a.md", "docs/a.md"])


def test_duplicate_limitations_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        _minimal_valid(limitations=["same", "same"])


# ---------------------------------------------------------------------------
# Fail closed: evidence/admission without hashes
# ---------------------------------------------------------------------------


def test_evidence_requires_hashes() -> None:
    with pytest.raises(ValidationError, match="evidence/admission requires"):
        _minimal_valid(
            evidence=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
            admission=AdmissionStatus.NOT_APPLICABLE,
        )
    with pytest.raises(ValidationError, match="evidence/admission requires"):
        _minimal_valid(
            evidence=EvidenceStanding.AVAILABLE,
            admission=AdmissionStatus.NOT_APPLICABLE,
            code_sha=HEX40_A,
            manifest_hash=None,
        )


def test_admission_requires_hashes() -> None:
    with pytest.raises(ValidationError, match="evidence/admission requires"):
        _minimal_valid(evidence=EvidenceStanding.UNAVAILABLE, admission=AdmissionStatus.ADMITTED)
    with pytest.raises(ValidationError, match="evidence/admission requires"):
        _minimal_valid(
            evidence=EvidenceStanding.UNAVAILABLE,
            admission=AdmissionStatus.ADMITTED,
            code_sha=HEX40_A,
            manifest_hash=None,
        )


def test_bad_code_sha_shape_rejected() -> None:
    with pytest.raises(ValidationError, match="40|40-hex|string_too_short|pattern"):
        _minimal_valid(
            evidence=EvidenceStanding.AVAILABLE,
            admission=AdmissionStatus.ADMITTED,
            code_sha="short",
            manifest_hash=HEX64_A,
        )


def test_bad_manifest_shape_rejected() -> None:
    with pytest.raises(ValidationError, match="64|64-hex|string_too_short|pattern"):
        _minimal_valid(
            evidence=EvidenceStanding.AVAILABLE,
            admission=AdmissionStatus.ADMITTED,
            code_sha=HEX40_A,
            manifest_hash="short",
        )


def test_bad_actor_hash_shape_rejected() -> None:
    with pytest.raises(ValidationError, match="64|64-hex|string_too_short|pattern"):
        _minimal_valid(
            evidence=EvidenceStanding.AVAILABLE,
            admission=AdmissionStatus.ADMITTED,
            code_sha=HEX40_A,
            manifest_hash=HEX64_A,
            actor_id="not-hex",
        )


# ---------------------------------------------------------------------------
# Fail closed: private absolute paths
# ---------------------------------------------------------------------------


def test_private_path_in_title_rejected() -> None:
    with pytest.raises(ValidationError, match="private absolute path"):
        _minimal_valid(title="study at /Users/alice/data")


def test_private_path_in_product_link_rejected() -> None:
    with pytest.raises(ValidationError, match="private absolute path"):
        _minimal_valid(product_links=["/tmp/secret.csv"])  # noqa: S108


def test_private_path_in_question_rejected() -> None:
    with pytest.raises(ValidationError, match="private absolute path"):
        _minimal_valid(question="what about /var/folders/abc/data?")


def test_private_path_in_limitation_rejected() -> None:
    with pytest.raises(ValidationError, match="private absolute path"):
        _minimal_valid(limitations=["data at /Users/bob/file.csv"])


def test_windows_absolute_path_rejected() -> None:
    with pytest.raises(ValidationError, match="private absolute path"):
        _minimal_valid(product_links=["C:\\Users\\alice\\data.csv"])


def test_canonical_json_private_path_rejected() -> None:
    rec = _minimal_valid()
    payload = json.loads(rec.canonical_json())
    payload["title"] = "/Users/alice/private"
    raw = json.dumps(payload)
    with pytest.raises((ValidationError, ValueError), match="private"):
        ResearchStudyRecord.from_canonical_json(raw)


# ---------------------------------------------------------------------------
# Fail closed: likely secrets
# ---------------------------------------------------------------------------


def test_secret_in_title_rejected() -> None:
    with pytest.raises(ValidationError, match="likely secret"):
        _minimal_valid(title="my secret key is foo")


def test_secret_api_key_rejected() -> None:
    with pytest.raises(ValidationError, match="likely secret"):
        _minimal_valid(limitations=["api_key=sk-123456"])


def test_secret_token_rejected() -> None:
    with pytest.raises(ValidationError, match="likely secret"):
        _minimal_valid(question="does token abc123 improve?")


def test_secret_password_rejected() -> None:
    with pytest.raises(ValidationError, match="likely secret"):
        _minimal_valid(product_links=["docs/report.md"], limitations=["password=123"])


def test_secret_in_canonical_json_rejected() -> None:
    rec = _minimal_valid()
    payload = json.loads(rec.canonical_json())
    payload["title"] = "contains password= hunter2"
    raw = json.dumps(payload)
    with pytest.raises((ValidationError, ValueError), match="secret"):
        ResearchStudyRecord.from_canonical_json(raw)


# ---------------------------------------------------------------------------
# Future-generic E3 handling – no hard-coded ID rule
# ---------------------------------------------------------------------------


def test_e3_not_admitted_is_valid_future() -> None:
    rec = _minimal_valid(
        study="E3",
        evidence=EvidenceStanding.UNAVAILABLE,
        admission=AdmissionStatus.NOT_APPLICABLE,
    )
    assert rec.study == "E3"


def test_non_e3_admitted_is_valid_with_hashes() -> None:
    rec = _minimal_valid(
        study="E2",
        evidence=EvidenceStanding.AVAILABLE,
        admission=AdmissionStatus.ADMITTED,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
    )
    assert rec.admission_status == AdmissionStatus.ADMITTED


def test_generic_e3_structurally_valid_without_trusted_claim() -> None:
    # E3 is not intrinsically forbidden; a structurally valid E3 record
    # with exact hashes can be modeled in the generic family without
    # claiming its package has been trusted for the registry. Lane 08's
    # trusted adapter decides real admission.
    rec = _minimal_valid(
        study="E3",
        version="1.0",
        status=StudyStatus.COMPLETED,
        evidence=EvidenceStanding.AVAILABLE,
        admission=AdmissionStatus.NOT_APPLICABLE,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
        replication_unit="fleet_draw",
        seeds=[1, 2],
        draws=[1, 2],
        arms=["control", "treatment"],
        primary_metrics=["offered_task_deadline_attainment"],
        per_draw_values=[
            PerDrawValue(
                draw=1, value=0.5, arm="control", metric="offered_task_deadline_attainment"
            ),
            PerDrawValue(
                draw=2, value=0.6, arm="treatment", metric="offered_task_deadline_attainment"
            ),
        ],
        declared_summary=DeclaredSummary(
            estimate=0.55, ci_lower=0.4, ci_upper=0.7, method="bootstrap"
        ),
    )
    assert rec.study == "E3"
    assert rec.code_sha == HEX40_A
    assert rec.manifest_hash == HEX64_A
    # Deterministic fingerprint independent of construction order
    rec2 = _minimal_valid(
        study="E3",
        version="1.0",
        status=StudyStatus.COMPLETED,
        evidence=EvidenceStanding.AVAILABLE,
        admission=AdmissionStatus.NOT_APPLICABLE,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
        replication_unit="fleet_draw",
        seeds=[2, 1],
        draws=[2, 1],
        arms=["treatment", "control"],
        primary_metrics=["offered_task_deadline_attainment"],
        per_draw_values=[
            PerDrawValue(
                draw=2, value=0.6, arm="treatment", metric="offered_task_deadline_attainment"
            ),
            PerDrawValue(
                draw=1, value=0.5, arm="control", metric="offered_task_deadline_attainment"
            ),
        ],
        declared_summary=DeclaredSummary(
            estimate=0.55, ci_lower=0.4, ci_upper=0.7, method="bootstrap"
        ),
    )
    assert rec.fingerprint() == rec2.fingerprint()
    # Also prove an E3 admitted record is structurally valid generically
    # (no hard-coded E3 rejection) – trust is an ingestion concern.
    rec_admitted = _minimal_valid(
        study="E3",
        version="1.0",
        status=StudyStatus.COMPLETED,
        evidence=EvidenceStanding.AVAILABLE,
        admission=AdmissionStatus.ADMITTED,
        code_sha=HEX40_B,
        manifest_hash=HEX64_B,
    )
    assert rec_admitted.study == "E3"
    assert rec_admitted.admission_status == AdmissionStatus.ADMITTED


# ---------------------------------------------------------------------------
# Valid future/unavailable without evidence — explicit missingness
# ---------------------------------------------------------------------------


def test_unavailable_with_no_hashes_and_no_per_draw_is_valid() -> None:
    rec = _minimal_valid(
        study="FUT-01",
        version="0.1.0",
        status=StudyStatus.UNAVAILABLE,
        evidence=EvidenceStanding.UNAVAILABLE,
        admission=AdmissionStatus.NOT_APPLICABLE,
        predecessor=None,
        successor=None,
        code_sha=None,
        manifest_hash=None,
        per_draw_values=None,
        declared_summary=None,
    )
    assert rec.per_draw_values is None
    assert rec.declared_summary is None
    assert rec.code_sha is None


def test_missing_optional_fields_explicit_none() -> None:
    rec = _minimal_valid(hypothesis=None, predecessor=None, product_links=None)
    j = json.loads(rec.canonical_json())
    assert j["hypothesis"] is None
    assert j["predecessor"] is None


# ---------------------------------------------------------------------------
# Interval ordering and hypothesis bounds
# ---------------------------------------------------------------------------


def test_interval_lower_must_be_less_than_upper() -> None:
    with pytest.raises(ValidationError, match="interval ordering"):
        DeclaredSummary(estimate=0.5, ci_lower=0.6, ci_upper=0.4)


def test_estimate_must_be_within_interval() -> None:
    with pytest.raises(ValidationError, match="must lie within interval"):
        DeclaredSummary(estimate=0.9, ci_lower=0.1, ci_upper=0.5)


def test_interval_one_sided_rejected() -> None:
    with pytest.raises(ValidationError, match="both ci_lower and ci_upper"):
        DeclaredSummary(estimate=0.5, ci_lower=0.1, ci_upper=None)


def test_self_reference_in_relationship_rejected() -> None:
    with pytest.raises(ValidationError, match="must not contain self"):
        _minimal_valid(study="S-001", predecessor=["S-001"])


def test_study_version_private_path_rejected() -> None:
    with pytest.raises(ValidationError, match="private|identifier|pattern"):
        _minimal_valid(study="/Users/bad")


def test_title_bounded() -> None:
    long_title = "a" * 301
    with pytest.raises(ValidationError):
        _minimal_valid(title=long_title)


def test_frozen_immutable() -> None:
    rec = _minimal_valid()
    with pytest.raises(ValidationError):
        rec.title = "new title"  # type: ignore[misc]


def test_canonical_json_sorted_keys() -> None:
    rec = _minimal_valid(study="S-002", version="1.0", title="B title")
    j = rec.canonical_json()
    obj = json.loads(j)
    assert list(obj.keys()) == sorted(obj.keys())
    rec2 = _minimal_valid(study="S-003", version="1.0", title="B title")
    assert rec.fingerprint() != rec2.fingerprint()


def test_bounded_seeds_range() -> None:
    with pytest.raises(ValidationError):
        _minimal_valid(seeds=[-1])
    with pytest.raises(ValidationError):
        _minimal_valid(seeds=[1_000_001])


def test_fingerprint_deterministic_across_construction_order() -> None:
    rec1 = _minimal_valid(seeds=[1, 2, 3], arms=["b", "a", "c"])
    rec2 = _minimal_valid(seeds=[3, 1, 2], arms=["c", "a", "b"])
    assert rec1.fingerprint() == rec2.fingerprint()
    assert rec1.arms == ["a", "b", "c"]


def test_malformed_json_rejected() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        ResearchStudyRecord.from_canonical_json("{not json}")


# ---------------------------------------------------------------------------
# Discriminating: ensure model does not hardcode E2-only
# ---------------------------------------------------------------------------


def test_generic_study_not_hardcoded_e2() -> None:
    rec = _minimal_valid(
        study="X-99",
        version="2.1+build.1",
        status=StudyStatus.COMPLETED,
        evidence=EvidenceStanding.AVAILABLE,
        admission=AdmissionStatus.ADMITTED,
        code_sha=HEX40_B,
        manifest_hash=HEX64_B,
        replication_unit="random_seed",
        arms=["control", "treatment"],
        primary_metrics=["latency_ms"],
        per_draw_values=[PerDrawValue(draw=0, value=12.5)],
        declared_summary=DeclaredSummary(
            estimate=12.5, ci_lower=10.0, ci_upper=15.0, method="bootstrap 95%"
        ),
    )
    assert rec.study == "X-99"
    assert rec.version == "2.1+build.1"


def test_extra_field_in_declared_summary_rejected() -> None:
    with pytest.raises(ValidationError):
        DeclaredSummary.model_validate(
            {"estimate": 1.0, "ci_lower": 0.5, "ci_upper": 1.5, "method": "t", "extra": "nope"}
        )
