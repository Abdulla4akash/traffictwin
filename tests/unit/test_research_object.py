from __future__ import annotations

import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

import pytest

from traffictwin.research_object import (
    InventoryDisposition,
    PermissionStatus,
    PublicationScope,
    RawEvidenceDisposition,
    ResearchObjectError,
    ResearchObjectRequest,
    build_research_object,
    create_research_object_archive,
    research_object_contract,
    verify_research_object,
    verify_research_object_bytes,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "bundles"
BASELINE = FIXTURES / "baseline_valid"
PUBLICATION_DATE = date(2026, 7, 21)


def _request(
    *,
    raw_evidence: RawEvidenceDisposition = RawEvidenceDisposition.REFERENCE,
    publication_scope: PublicationScope = PublicationScope.PRIVATE,
    permission_status: PermissionStatus = PermissionStatus.UNKNOWN,
    permission_basis: str | None = None,
    raw_evidence_licence: str | None = None,
) -> ResearchObjectRequest:
    return ResearchObjectRequest(
        publication_date=PUBLICATION_DATE,
        raw_evidence=raw_evidence,
        publication_scope=publication_scope,
        permission_status=permission_status,
        permission_basis=permission_basis,
        raw_evidence_licence=raw_evidence_licence,
    )


def _imported_bundle(tmp_path: Path) -> Path:
    target = tmp_path / "imported"
    shutil.copytree(BASELINE, target)
    manifest = target / "manifest.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace('name: "synthetic"', 'name: "vec_env"'),
        encoding="utf-8",
    )
    return target


def test_research_object_contract_is_versioned_and_permission_aware() -> None:
    contract = research_object_contract()

    assert contract.capability_id == "OPS-04"
    assert contract.ro_crate_context == "https://w3id.org/ro/crate/1.3/context"
    assert contract.cff_version == "1.2.0"
    assert set(contract.raw_evidence_modes) == {"embed", "reference", "exclude"}
    assert len(contract.fingerprint()) == 64


@pytest.mark.parametrize(
    ("mode", "embedded_raw", "referenced_raw", "excluded_raw"),
    [
        (RawEvidenceDisposition.EMBED, True, 0, 0),
        (RawEvidenceDisposition.REFERENCE, False, 6, 0),
        (RawEvidenceDisposition.EXCLUDE, False, 0, 6),
    ],
)
def test_raw_evidence_modes_are_explicit_and_reconcile(
    mode: RawEvidenceDisposition,
    embedded_raw: bool,
    referenced_raw: int,
    excluded_raw: int,
) -> None:
    built = build_research_object(BASELINE, _request(raw_evidence=mode))
    raw_entries = [item for item in built.manifest.inventory if item.role == "raw_evidence"]

    assert any(name.startswith("data/raw/") for name in built.members) is embedded_raw
    assert (
        sum(item.disposition is InventoryDisposition.REFERENCED for item in raw_entries)
        == referenced_raw
    )
    assert sum(item.count for item in built.manifest.exclusions) == excluded_raw
    if mode is RawEvidenceDisposition.EXCLUDE:
        assert all(item.source_path is None for item in built.manifest.inventory)
        assert all(not item.identifiers_included for item in built.manifest.exclusions)
        attached = b"\n".join(built.members.values())
        for raw_name in (
            "manifest.yaml",
            "seed.yaml",
            "tasks.csv",
            "infra_state.csv",
            "traffic_obs.csv",
            "trips.csv",
        ):
            assert raw_name.encode() not in attached


def test_exclude_mode_scrubs_raw_names_from_caller_metadata() -> None:
    built = build_research_object(
        BASELINE,
        ResearchObjectRequest(
            publication_date=PUBLICATION_DATE,
            title="Analysis of tasks.csv",
            raw_evidence=RawEvidenceDisposition.EXCLUDE,
        ),
    )

    assert b"tasks.csv" not in b"\n".join(built.members.values())
    assert built.manifest.title == "Analysis of [excluded raw path]"


def test_imported_raw_evidence_requires_permission_for_embed_or_public_reference(
    tmp_path: Path,
) -> None:
    imported = _imported_bundle(tmp_path)

    with pytest.raises(ResearchObjectError, match="embedding imported raw evidence"):
        build_research_object(
            imported,
            _request(raw_evidence=RawEvidenceDisposition.EMBED),
        )
    with pytest.raises(ResearchObjectError, match="public imported raw evidence"):
        build_research_object(
            imported,
            _request(publication_scope=PublicationScope.PUBLIC),
        )

    excluded = build_research_object(
        imported,
        _request(
            raw_evidence=RawEvidenceDisposition.EXCLUDE,
            publication_scope=PublicationScope.PUBLIC,
        ),
    )
    permitted = build_research_object(
        imported,
        _request(
            raw_evidence=RawEvidenceDisposition.EMBED,
            publication_scope=PublicationScope.PUBLIC,
            permission_status=PermissionStatus.CONFIRMED,
            permission_basis="Written permission recorded by the researcher.",
            raw_evidence_licence="Permission-limited research reuse.",
        ),
    )

    assert excluded.manifest.source.raw_evidence is RawEvidenceDisposition.EXCLUDE
    assert any(name.startswith("data/raw/") for name in permitted.members)


def test_archive_is_byte_deterministic_bounded_and_redacts_local_paths(tmp_path: Path) -> None:
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    request = _request(raw_evidence=RawEvidenceDisposition.EMBED)

    first_receipt = create_research_object_archive(BASELINE, first, request)
    second_receipt = create_research_object_archive(BASELINE, second, request)

    assert first.read_bytes() == second.read_bytes()
    assert first_receipt.archive_sha256 == second_receipt.archive_sha256
    verification = verify_research_object(first)
    assert verification.valid is True
    assert verification.manifest_fingerprint == first_receipt.manifest_fingerprint
    with zipfile.ZipFile(first) as archive:
        infos = archive.infolist()
        assert [item.filename for item in infos] == sorted(item.filename for item in infos)
        assert {item.compress_type for item in infos} == {zipfile.ZIP_STORED}
        assert {item.date_time for item in infos} == {(1980, 1, 1, 0, 0, 0)}
        derived_text = b"\n".join(
            archive.read(item) for item in archive.namelist() if not item.startswith("data/raw/")
        )
        assert b"</html>" in archive.read("reports/run-report.html")
    assert str(BASELINE.resolve()).encode() not in derived_text


def test_request_rejects_absolute_local_paths() -> None:
    with pytest.raises(ValueError, match="must not contain absolute local paths"):
        ResearchObjectRequest(
            publication_date=PUBLICATION_DATE,
            title="Results from /Users/researcher/private",
        )


def test_atomic_publication_cleans_temporary_file_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "crate.zip"

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr("traffictwin.research_object.os.replace", fail_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        create_research_object_archive(BASELINE, destination, _request())

    assert destination.exists() is False
    assert list(tmp_path.glob(".crate.zip.*.tmp")) == []


def test_verifier_rejects_tampered_payload(tmp_path: Path) -> None:
    archive = tmp_path / "crate.zip"
    create_research_object_archive(BASELINE, archive, _request())
    payload = bytearray(archive.read_bytes())
    offset = payload.find(b'"metric_version"')
    assert offset > 0
    payload[offset + 1] ^= 1

    verification = verify_research_object_bytes(bytes(payload))

    assert verification.valid is False
    assert verification.errors


def test_attached_crate_has_citation_manifest_checksums_and_ro_crate_graph() -> None:
    built = build_research_object(BASELINE, _request())

    assert {
        "CITATION.cff",
        "checksums.sha256",
        "research-object-manifest.json",
        "ro-crate-metadata.json",
    }.issubset(built.members)
    metadata = json.loads(built.members["ro-crate-metadata.json"])
    graph = {item["@id"]: item for item in metadata["@graph"]}
    assert metadata["@context"] == "https://w3id.org/ro/crate/1.3/context"
    assert graph["ro-crate-metadata.json"]["about"] == {"@id": "./"}
    assert graph["./"]["@type"] == "Dataset"
    assert graph["./"]["datePublished"] == "2026-07-21"
