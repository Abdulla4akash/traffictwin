from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from traffictwin.integration.manchester.artifact_integrity import (
    ArtifactIdentity,
    ArtifactIntegrityError,
    SourceDerivedRecord,
    refuse_ephemeral_dependency,
    refuse_source_derived_collision,
    verify_recorded_identity,
)

PBF_BYTES = b"pbf-source-payload"
XML_BYTES = b"decoded-xml-payload-which-is-longer"


def _identity(role: str, payload: bytes, representation: str) -> ArtifactIdentity:
    return ArtifactIdentity(
        role=role,
        representation=representation,
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        md5=hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    )


def test_distinct_source_and_derived_identities_are_accepted() -> None:
    record = SourceDerivedRecord(
        source=_identity("source", PBF_BYTES, "downloaded pbf"),
        derived=_identity("derived", XML_BYTES, "decoded osm xml"),
    )
    refuse_source_derived_collision(record)


def test_the_25_july_defect_is_refused_by_hash() -> None:
    """The decoded artifact's identity recorded in the source fields."""

    decoded = _identity("derived", XML_BYTES, "decoded osm xml")
    record = SourceDerivedRecord(
        source=ArtifactIdentity(
            role="source",
            representation="downloaded pbf (wrongly holding the decode output identity)",
            byte_size=decoded.byte_size,
            sha256=decoded.sha256,
            md5=decoded.md5,
        ),
        derived=decoded,
    )
    with pytest.raises(ArtifactIntegrityError, match="SOURCE_DERIVED_IDENTITY_COLLISION"):
        refuse_source_derived_collision(record)


def test_shared_byte_size_alone_is_refused() -> None:
    source = _identity("source", PBF_BYTES, "downloaded pbf")
    derived = ArtifactIdentity(
        role="derived",
        representation="decoded osm xml",
        byte_size=source.byte_size,
        sha256=hashlib.sha256(XML_BYTES).hexdigest(),
    )
    with pytest.raises(ArtifactIntegrityError, match="SOURCE_DERIVED_SIZE_COLLISION"):
        refuse_source_derived_collision(SourceDerivedRecord(source=source, derived=derived))


def test_recorded_identity_must_match_the_file(tmp_path: Path) -> None:
    path = tmp_path / "extract.pbf"
    path.write_bytes(PBF_BYTES)
    identity = _identity("source", PBF_BYTES, "downloaded pbf")
    verify_recorded_identity(identity, path)

    path.write_bytes(PBF_BYTES + b"drift")
    with pytest.raises(ArtifactIntegrityError, match="ARTIFACT_SIZE_MISMATCH"):
        verify_recorded_identity(identity, path)


def test_missing_artifact_is_refused(tmp_path: Path) -> None:
    identity = _identity("source", PBF_BYTES, "downloaded pbf")
    with pytest.raises(ArtifactIntegrityError, match="ARTIFACT_MISSING"):
        verify_recorded_identity(identity, tmp_path / "absent.pbf")


def test_durable_build_location_is_accepted() -> None:
    refuse_ephemeral_dependency(Path.cwd() / "data" / "network-build" / "gm.net.xml")


def test_ephemeral_build_locations_are_refused() -> None:
    """pytest's own tmp_path is ephemeral too, which is exactly the point."""

    ephemeral = (
        "/tmp/gmfinal/network.net.xml",  # noqa: S108 - refusal fixture, never written
        "/private/tmp/session/scratchpad/net",  # noqa: S108 - refusal fixture
    )
    for path in ephemeral:
        with pytest.raises(ArtifactIntegrityError, match="EPHEMERAL_DEPENDENCY_REFUSED"):
            refuse_ephemeral_dependency(path)
