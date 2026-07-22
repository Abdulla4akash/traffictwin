"""Unit tests for the strict MAN-01 snapshot models (synthetic fixtures only)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import BaseModel, ValidationError

from traffictwin.integration.manchester.models import (
    ManchesterFindingSeverity,
    ManchesterHttpMetadata,
    ManchesterPriorRelation,
    ManchesterPriorSnapshotLink,
    ManchesterPublicationClass,
    ManchesterRawMember,
    ManchesterRequestIdentity,
    ManchesterRetrievalWindow,
    ManchesterSnapshotFinding,
    ManchesterSnapshotManifest,
    ManchesterSnapshotPolicy,
    ManchesterSourceIdentity,
    ManchesterValidationState,
    build_raw_fingerprint,
    build_snapshot_id,
    sha256_hex,
)

SYNTHETIC_BODY = b'{"synthetic": true, "label": "synthetic fixture"}\n'
SYNTHETIC_PAGE = b'{"synthetic": true, "page": 1}\n'
STARTED = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
COMPLETED = datetime(2026, 7, 22, 10, 0, 5, tzinfo=UTC)


def make_members() -> tuple[ManchesterRawMember, ...]:
    return (
        ManchesterRawMember(
            relative_path="body.json",
            byte_size=len(SYNTHETIC_BODY),
            media_type="application/json",
            sha256=sha256_hex(SYNTHETIC_BODY),
        ),
        ManchesterRawMember(
            relative_path="pages/page-1.json",
            byte_size=len(SYNTHETIC_PAGE),
            media_type="application/json",
            sha256=sha256_hex(SYNTHETIC_PAGE),
        ),
    )


def make_manifest(**overrides: object) -> ManchesterSnapshotManifest:
    members = tuple(sorted(make_members(), key=lambda member: member.relative_path))
    raw_fingerprint = build_raw_fingerprint(members)
    values: dict[str, object] = {
        "snapshot_id": build_snapshot_id("synthetic_demo", STARTED, raw_fingerprint),
        "source": ManchesterSourceIdentity(
            source_id="synthetic_demo",
            source_name="Synthetic demo source (not Manchester data)",
            adapter_version="0.0.1",
            source_schema_version="synthetic-1.0",
            freshness_policy_version="synthetic-1.0",
        ),
        "request": ManchesterRequestIdentity(
            host="example.invalid",
            path="/api/synthetic",
            parameters=(("page", 1), ("scope", "synthetic")),
            redacted_parameter_names=(),
        ),
        "retrieval": ManchesterRetrievalWindow(started_at_utc=STARTED, completed_at_utc=COMPLETED),
        "http": ManchesterHttpMetadata(status_code=200, response_content_type="application/json"),
        "members": members,
        "member_count": len(members),
        "total_bytes": sum(member.byte_size for member in members),
        "raw_fingerprint": raw_fingerprint,
        "validation_state": ManchesterValidationState.ACCEPTED,
        "findings": (),
        "prior": ManchesterPriorSnapshotLink(relation=ManchesterPriorRelation.FIRST_SNAPSHOT),
        "publication_class": ManchesterPublicationClass.METADATA_ONLY,
        "licence_id": "synthetic-fixture",
        "attribution_text": "Synthetic TrafficTwin fixture; not observed Manchester data.",
        "access_date": date(2026, 7, 22),
        "synthetic": True,
    }
    values.update(overrides)
    return ManchesterSnapshotManifest.model_validate(values)


def test_manifest_fingerprint_is_deterministic() -> None:
    first = make_manifest()
    second = make_manifest()
    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint() == second.fingerprint()
    assert first.fingerprint() == sha256_hex(first.canonical_json().encode("utf-8"))


def test_manifest_fingerprint_changes_with_content() -> None:
    changed = SYNTHETIC_BODY + b" "
    members = tuple(
        sorted(
            (
                ManchesterRawMember(
                    relative_path="body.json",
                    byte_size=len(changed),
                    media_type="application/json",
                    sha256=sha256_hex(changed),
                ),
                make_members()[1],
            ),
            key=lambda member: member.relative_path,
        )
    )
    raw_fingerprint = build_raw_fingerprint(members)
    other = make_manifest(
        members=members,
        total_bytes=sum(member.byte_size for member in members),
        raw_fingerprint=raw_fingerprint,
        snapshot_id=build_snapshot_id("synthetic_demo", STARTED, raw_fingerprint),
    )
    assert other.fingerprint() != make_manifest().fingerprint()


@pytest.mark.parametrize(
    "model, values",
    [
        (ManchesterRawMember, dict(make_members()[0].model_dump(), bogus=1)),
        (
            ManchesterSnapshotPolicy,
            {"max_member_count": 1, "max_member_bytes": 1, "max_total_bytes": 1, "bogus": 1},
        ),
        (ManchesterSnapshotFinding, {"code": "X", "severity": "info", "message": "m", "bogus": 1}),
    ],
)
def test_unknown_fields_are_rejected(model: type[BaseModel], values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(values)


def test_manifest_unknown_field_rejected() -> None:
    payload = make_manifest().model_dump(mode="json")
    payload["bogus"] = 1
    with pytest.raises(ValidationError):
        ManchesterSnapshotManifest.model_validate(payload)


@pytest.mark.parametrize("publication_class", list(ManchesterPublicationClass))
def test_publication_classes_round_trip(
    publication_class: ManchesterPublicationClass,
) -> None:
    manifest = make_manifest(publication_class=publication_class)
    restored = ManchesterSnapshotManifest.model_validate_json(manifest.canonical_json())
    assert restored.publication_class is publication_class
    assert restored.fingerprint() == manifest.fingerprint()


def test_retrieval_window_requires_utc_and_order() -> None:
    with pytest.raises(ValidationError):
        ManchesterRetrievalWindow(
            started_at_utc=STARTED.replace(tzinfo=None), completed_at_utc=COMPLETED
        )
    with pytest.raises(ValidationError):
        ManchesterRetrievalWindow(started_at_utc=COMPLETED, completed_at_utc=STARTED)


@pytest.mark.parametrize(
    "name",
    ["api_key", "apiKey", "Token", "AUTHORIZATION", "x-secret", "password", "session_id", "auth"],
)
def test_secret_parameter_names_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity(
            host="example.invalid", path="/api", parameters=((name, "value"),)
        )


def test_plain_parameter_names_are_accepted() -> None:
    identity = ManchesterRequestIdentity(
        host="example.invalid",
        path="/api",
        parameters=(("active", True), ("page", 1), ("page_size", 96), ("sites", "100")),
        redacted_parameter_names=("api_key",),
    )
    assert dict(identity.parameters)["page"] == 1
    assert identity.redacted_parameter_names == ("api_key",)


def test_request_identity_requires_canonical_order_and_valid_host() -> None:
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity(
            host="example.invalid", path="/api", parameters=(("page", 1), ("active", True))
        )
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity(
            host="example.invalid", path="/api", parameters=(("page", 1), ("page", 2))
        )
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity(host="example..invalid", path="/api")


def test_models_are_strict_and_collections_are_immutable() -> None:
    with pytest.raises(ValidationError):
        ManchesterRawMember.model_validate(
            {
                "relative_path": "body.json",
                "byte_size": "1",
                "media_type": "application/json",
                "sha256": sha256_hex(b"x"),
            }
        )
    manifest = make_manifest()
    assert isinstance(manifest.members, tuple)
    assert isinstance(manifest.findings, tuple)
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity.model_validate(
            {"host": "example.invalid", "path": "/api", "parameters": {"page": 1}}
        )


def test_redacted_name_cannot_also_carry_a_value() -> None:
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity(
            host="example.invalid",
            path="/api",
            parameters=(("page", 1),),
            redacted_parameter_names=("page",),
        )


@pytest.mark.parametrize(
    "value",
    [
        "https://user:pass@example.invalid/feed",
        "https://example.invalid/feed?api_key=abc",
        "https://example.invalid/feed?page=1",
    ],
)
def test_credential_bearing_url_values_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity(
            host="example.invalid", path="/api", parameters=(("target", value),)
        )


@pytest.mark.parametrize(
    "value",
    ["/Users/someone/data.csv", "~/secrets.txt", "C:\\data\\x.csv", "/private/tmp/x"],
)
def test_private_paths_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        ManchesterSnapshotFinding(
            code="X_CODE",
            severity=ManchesterFindingSeverity.INFO,
            message=f"saw {value}",
        )
    with pytest.raises(ValidationError):
        ManchesterRequestIdentity(
            host="example.invalid", path="/api", parameters=(("note", value),)
        )
    with pytest.raises(ValidationError):
        make_manifest(attribution_text=f"data at {value}")


@pytest.mark.parametrize(
    "path",
    ["/abs.json", "../escape.json", "a//b.json", "a/./b.json", "a\\b.json", "c:/x.json", ".hidden"],
)
def test_unsafe_member_paths_are_rejected(path: str) -> None:
    with pytest.raises(ValidationError):
        ManchesterRawMember(
            relative_path=path,
            byte_size=1,
            media_type="application/json",
            sha256=sha256_hex(b"x"),
        )


def test_member_ordering_and_uniqueness_enforced() -> None:
    members = make_members()
    unsorted_members = (members[1], members[0])
    raw_fingerprint = build_raw_fingerprint(unsorted_members)
    with pytest.raises(ValidationError):
        make_manifest(
            members=unsorted_members,
            raw_fingerprint=raw_fingerprint,
            snapshot_id=build_snapshot_id("synthetic_demo", STARTED, raw_fingerprint),
        )
    duplicate = (members[0], members[0])
    with pytest.raises(ValidationError):
        make_manifest(members=duplicate)
    folded = (
        members[0],
        members[0].model_copy(update={"relative_path": "BODY.JSON"}),
    )
    with pytest.raises(ValidationError):
        make_manifest(members=tuple(sorted(folded, key=lambda member: member.relative_path)))


def test_manifest_reconciliation_is_enforced() -> None:
    with pytest.raises(ValidationError):
        make_manifest(member_count=3)
    with pytest.raises(ValidationError):
        make_manifest(total_bytes=1)
    with pytest.raises(ValidationError):
        make_manifest(raw_fingerprint=sha256_hex(b"other"))
    with pytest.raises(ValidationError):
        make_manifest(snapshot_id="synthetic_demo-20990101T000000Z-000000000000")


def test_prior_relation_invariants() -> None:
    manifest = make_manifest()
    with pytest.raises(ValidationError):
        ManchesterPriorSnapshotLink(
            relation=ManchesterPriorRelation.FIRST_SNAPSHOT,
            prior_snapshot_id=manifest.snapshot_id,
            prior_raw_fingerprint=manifest.raw_fingerprint,
        )
    with pytest.raises(ValidationError):
        ManchesterPriorSnapshotLink(relation=ManchesterPriorRelation.SUPERSEDES)
    prior_id = build_snapshot_id(
        "synthetic_demo", datetime(2026, 7, 21, 9, 0, 0, tzinfo=UTC), manifest.raw_fingerprint
    )
    duplicate = make_manifest(
        prior=ManchesterPriorSnapshotLink(
            relation=ManchesterPriorRelation.DUPLICATE_NO_CHANGE,
            prior_snapshot_id=prior_id,
            prior_raw_fingerprint=manifest.raw_fingerprint,
        )
    )
    assert duplicate.prior.relation is ManchesterPriorRelation.DUPLICATE_NO_CHANGE
    with pytest.raises(ValidationError):
        make_manifest(
            prior=ManchesterPriorSnapshotLink(
                relation=ManchesterPriorRelation.DUPLICATE_NO_CHANGE,
                prior_snapshot_id=prior_id,
                prior_raw_fingerprint=sha256_hex(b"different"),
            )
        )
    with pytest.raises(ValidationError):
        make_manifest(
            prior=ManchesterPriorSnapshotLink(
                relation=ManchesterPriorRelation.SUPERSEDES,
                prior_snapshot_id=prior_id,
                prior_raw_fingerprint=manifest.raw_fingerprint,
            )
        )


def test_validation_state_finding_invariants() -> None:
    warning = ManchesterSnapshotFinding(
        code="SYNTHETIC_WARNING",
        severity=ManchesterFindingSeverity.WARNING,
        message="synthetic warning",
    )
    error = ManchesterSnapshotFinding(
        code="SYNTHETIC_ERROR",
        severity=ManchesterFindingSeverity.ERROR,
        message="synthetic error",
    )
    with pytest.raises(ValidationError):
        make_manifest(findings=(warning,))
    with pytest.raises(ValidationError):
        make_manifest(
            validation_state=ManchesterValidationState.ACCEPTED_WITH_WARNINGS,
            findings=(),
        )
    with pytest.raises(ValidationError):
        make_manifest(
            validation_state=ManchesterValidationState.ACCEPTED_WITH_WARNINGS,
            findings=(error, warning),
        )
    with pytest.raises(ValidationError):
        make_manifest(validation_state=ManchesterValidationState.REJECTED, findings=())
    accepted = make_manifest(
        validation_state=ManchesterValidationState.ACCEPTED_WITH_WARNINGS,
        findings=(warning,),
    )
    assert accepted.validation_state is ManchesterValidationState.ACCEPTED_WITH_WARNINGS


def test_policy_bounds_invariant() -> None:
    with pytest.raises(ValidationError):
        ManchesterSnapshotPolicy(max_member_count=1, max_member_bytes=10, max_total_bytes=5)
