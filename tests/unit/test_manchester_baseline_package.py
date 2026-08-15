"""Discriminating tests for the Manchester baseline package.

Covers acceptance inflation, mismatched candidate hash, missing provider
evidence, unlicensed/unknown rights where acceptance requires rights,
changed network hash, broken provenance, secret/path leakage, deterministic
fingerprint, and valid software-only synthetic engineering package.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.baseline_package import (
    BaselineProvenance,
    BoundaryIdentity,
    CalibrationIdentity,
    DemandIdentity,
    GeographicIdentity,
    ManchesterBaselineAcceptanceDecision,
    ManchesterBaselineCandidatePackage,
    ManchesterBaselinePackageError,
    ManchesterBaselineSoftwareValidation,
    MapMatchPolicyIdentity,
    NetworkIdentity,
    PortableNetworkFile,
    SourceAndRights,
    decide_baseline_acceptance,
    make_synthetic_candidate,
    validate_candidate_software,
    verify_baseline_acceptance,
)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _make_valid_synthetic() -> ManchesterBaselineCandidatePackage:
    return make_synthetic_candidate(provider_data_required=True)


def _make_observed_candidate(
    rights: str = "ODbL-1.0",
    with_build_receipt: bool = True,
) -> ManchesterBaselineCandidatePackage:
    now = _utc_now()
    pf = PortableNetworkFile(
        relative_path="networks/observed/network.xml",
        sha256="a" * 64,
        byte_size=1000,
        media_type="application/xml",
    )
    inv = [{"relative_path": pf.relative_path, "sha256": pf.sha256, "byte_size": pf.byte_size}]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    geo = GeographicIdentity(
        envelope_fingerprint="b" * 64,
        boundary_asset_sha256="c" * 64,
        boundary_asset_name="greater_manchester_combined_authority.geojson",
    )
    net = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(pf,),
        network_identity_sha256=net_sha,
        edge_count=200,
        junction_count=100,
    )
    bound_fp = hashlib.sha256(
        json.dumps(
            {
                "scope": "greater_manchester_combined_authority",
                "asset_sha256": "c" * 64,
                "asset_name": "greater_manchester_combined_authority.geojson",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    boundary = BoundaryIdentity(
        scope="greater_manchester_combined_authority",
        asset_sha256="c" * 64,
        asset_name="greater_manchester_combined_authority.geojson",
        identity_fingerprint=bound_fp,
    )
    demand = DemandIdentity(
        identity_fingerprint="e" * 64,
        source_snapshot_ids=("dft_raw_counts-20260725T063354Z-61965dc5c182",),
        provider_evidence_available=True,
    )
    mmap = MapMatchPolicyIdentity(
        policy_id="manchester-dft-map-match-owner-policy-1.1",
        policy_fingerprint="f" * 64,
        approved_for_manchester=True,
        requires_named_person_review=False,
    )
    cal = CalibrationIdentity(
        contract_fingerprint="1" * 64,
        receipt_fingerprint="2" * 64,
        contract_version="v1",
        evidence_class="production",
        calibration_performed=True,
    )
    src = SourceAndRights(
        source_standing="OBSERVED_MANCHESTER_EVIDENCE",
        evidence_standing="OBSERVED_MANCHESTER_EVIDENCE",
        evidence_class="production",
        rights_standing=rights,  # type: ignore[arg-type]
        licence_id=rights
        if rights not in ("UNKNOWN", "UNLICENSED")
        else "ODbL-1.0"
        if rights == "UNKNOWN"
        else "UNLICENSED",
        attribution_text="© OpenStreetMap contributors, ODbL 1.0",
        rights_required_for_acceptance=True,
    )
    if rights in ("UNKNOWN", "UNLICENSED"):
        src = SourceAndRights(
            source_standing="OBSERVED_MANCHESTER_EVIDENCE",
            evidence_standing="OBSERVED_MANCHESTER_EVIDENCE",
            evidence_class="production",
            rights_standing=rights,  # type: ignore[arg-type]
            licence_id=rights,
            attribution_text="© OpenStreetMap contributors",
            rights_required_for_acceptance=True,
        )
    prov = BaselineProvenance(
        created_at_utc=now, created_by="analyst@example.com", software_version="0.7.0"
    )
    return ManchesterBaselineCandidatePackage(
        package_id="observed-baseline-001",
        geographic_identity=geo,
        network_identity=net,
        boundary_identity=boundary,
        demand_identity=demand,
        map_match_policy_identity=mmap,
        calibration_identity=cal,
        source_and_rights=src,
        limitations=("Observed baseline candidate with provider data",),
        provenance=prov,
        provider_data_required=False,
        prerequisites=tuple(sorted(["boundary", "calibration", "demand", "map_match", "network"])),
        build_receipt_fingerprint=("9" * 64 if with_build_receipt else None),
    )


def test_deterministic_fingerprint() -> None:
    fixed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    pf = PortableNetworkFile(
        relative_path="networks/synthetic/network.xml",
        sha256="a" * 64,
        byte_size=12345,
        media_type="application/xml",
    )
    inv = [{"relative_path": pf.relative_path, "sha256": pf.sha256, "byte_size": pf.byte_size}]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    geo = GeographicIdentity(
        envelope_fingerprint="b" * 64,
        boundary_asset_sha256="c" * 64,
        boundary_asset_name="greater_manchester_combined_authority.geojson",
    )
    net = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(pf,),
        network_identity_sha256=net_sha,
        edge_count=100,
        junction_count=50,
    )
    bound_fp = hashlib.sha256(
        json.dumps(
            {
                "scope": "greater_manchester_combined_authority",
                "asset_sha256": "c" * 64,
                "asset_name": "greater_manchester_combined_authority.geojson",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    boundary = BoundaryIdentity(
        scope="greater_manchester_combined_authority",
        asset_sha256="c" * 64,
        asset_name="greater_manchester_combined_authority.geojson",
        identity_fingerprint=bound_fp,
    )
    demand = DemandIdentity(
        identity_fingerprint="e" * 64, source_snapshot_ids=(), provider_evidence_available=False
    )
    mmap = MapMatchPolicyIdentity(
        policy_id="manchester-dft-map-match-owner-policy-1.1",
        policy_fingerprint="f" * 64,
        approved_for_manchester=False,
        requires_named_person_review=True,
    )
    cal = CalibrationIdentity(
        contract_fingerprint=None,
        receipt_fingerprint=None,
        contract_version=None,
        evidence_class="synthetic_development",
        calibration_performed=False,
    )
    src = SourceAndRights(
        source_standing="PROVIDER_DATA_REQUIRED",
        evidence_standing="PROVIDER_DATA_REQUIRED",
        evidence_class="synthetic_test_only",
        rights_standing="ODbL-1.0",
        licence_id="ODbL-1.0",
        attribution_text="© OpenStreetMap contributors, ODbL 1.0",
        rights_required_for_acceptance=True,
    )
    prov = BaselineProvenance(
        created_at_utc=fixed, created_by="test-engineer@example.com", software_version="0.7.0"
    )
    cand1 = ManchesterBaselineCandidatePackage(
        package_id="synthetic-baseline-001",
        geographic_identity=geo,
        network_identity=net,
        boundary_identity=boundary,
        demand_identity=demand,
        map_match_policy_identity=mmap,
        calibration_identity=cal,
        source_and_rights=src,
        limitations=("Synthetic engineering baseline only",),
        provenance=prov,
        provider_data_required=True,
        prerequisites=tuple(sorted(["boundary", "demand", "network"])),
    )
    cand2 = ManchesterBaselineCandidatePackage(
        package_id="synthetic-baseline-001",
        geographic_identity=geo,
        network_identity=net,
        boundary_identity=boundary,
        demand_identity=demand,
        map_match_policy_identity=mmap,
        calibration_identity=cal,
        source_and_rights=src,
        limitations=("Synthetic engineering baseline only",),
        provenance=prov,
        provider_data_required=True,
        prerequisites=tuple(sorted(["boundary", "demand", "network"])),
    )
    assert cand1.fingerprint() == cand2.fingerprint()
    assert cand1.canonical_json() == cand2.canonical_json()


def test_valid_software_only_synthetic_engineering() -> None:
    cand = _make_valid_synthetic()
    validated_at = cand.provenance.created_at_utc + timedelta(seconds=10)
    decided_at = validated_at + timedelta(seconds=10)
    validation = validate_candidate_software(cand, validated_at_utc=validated_at)
    assert validation.software_standing == "SOFTWARE_VALID"
    assert validation.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert validation.scientifically_accepted is False
    assert validation.is_scientific_evidence is False
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="Dr. Sampaio",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="attempt to accept synthetic",
            prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
            software_validation=validation,
        )
    assert exc.value.code == "PROVIDER_DATA_REQUIRED"
    blocked = decide_baseline_acceptance(
        cand,
        decided_by="Dr. Sampaio",
        decided_at_utc=decided_at,
        scientific_standing="PROVIDER_DATA_REQUIRED",
        rationale="blocked due to missing provider data",
        prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
        software_validation=validation,
    )
    assert blocked.scientific_standing == "PROVIDER_DATA_REQUIRED"
    assert "PROVIDER_DATA_REQUIRED" in blocked.rejection_reasons


def test_acceptance_inflation_refused() -> None:
    cand = _make_valid_synthetic()
    validation = validate_candidate_software(cand)
    assert validation.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    with pytest.raises(ValidationError):
        ManchesterBaselineSoftwareValidation.model_validate(
            {
                "candidate_fingerprint": cand.fingerprint(),
                "candidate_package_id": cand.package_id,
                "network_identity_sha256": cand.network_identity.network_identity_sha256,
                "software_standing": "SOFTWARE_VALID",
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
                "scientifically_accepted": True,
                "checks_performed": tuple(sorted(["boundary_fingerprint"])),
                "rejection_reasons": (),
                "validated_at_utc": _utc_now(),
                "is_scientific_evidence": True,
            }
        )


def test_mismatched_candidate_hash() -> None:
    cand = _make_observed_candidate()
    other_pf = PortableNetworkFile(
        relative_path="networks/observed/network.xml",
        sha256="b" * 64,
        byte_size=1000,
        media_type="application/xml",
    )
    inv = [
        {
            "relative_path": other_pf.relative_path,
            "sha256": other_pf.sha256,
            "byte_size": other_pf.byte_size,
        }
    ]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    mutated_net = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(other_pf,),
        network_identity_sha256=net_sha,
        edge_count=200,
        junction_count=100,
    )
    mutated_cand = cand.model_copy(update={"network_identity": mutated_net})
    mutated_validation = validate_candidate_software(mutated_cand)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="mismatched",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=mutated_validation,
        )
    assert exc.value.code == "MISMATCHED_CANDIDATE_FINGERPRINT"


def test_missing_provider_evidence_blocked() -> None:
    cand = _make_valid_synthetic()
    validation = validate_candidate_software(cand)
    assert cand.provider_data_required is True
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="missing provider",
            prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
            software_validation=validation,
        )
    assert "PROVIDER_DATA_REQUIRED" in str(exc.value)


def test_unlicensed_blocks_acceptance() -> None:
    cand = _make_observed_candidate(rights="UNKNOWN")
    validation = validate_candidate_software(cand)
    assert validation.software_standing == "SOFTWARE_VALID"
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="unknown rights",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=validation,
        )
    assert exc.value.code == "RIGHTS_UNKNOWN"
    cand2 = _make_observed_candidate(rights="UNLICENSED")
    val2 = validate_candidate_software(cand2)
    with pytest.raises(ManchesterBaselinePackageError) as exc2:
        decide_baseline_acceptance(
            cand2,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="unlicensed",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val2,
        )
    assert exc2.value.code == "RIGHTS_UNLICENSED"


def test_changed_network_hash_changes_fingerprint() -> None:
    cand = _make_valid_synthetic()
    fp1 = cand.fingerprint()
    pf2 = PortableNetworkFile(
        relative_path="networks/synthetic/network.xml",
        sha256="b" * 64,
        byte_size=12345,
        media_type="application/xml",
    )
    inv = [{"relative_path": pf2.relative_path, "sha256": pf2.sha256, "byte_size": pf2.byte_size}]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    net2 = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(pf2,),
        network_identity_sha256=net_sha,
        edge_count=100,
        junction_count=50,
    )
    cand2 = cand.model_copy(update={"network_identity": net2})
    assert cand2.fingerprint() != fp1
    v2 = validate_candidate_software(cand2)
    assert v2.software_standing == "SOFTWARE_VALID"
    assert v2.network_identity_sha256 == net_sha


def test_broken_provenance() -> None:
    # provenance after validation => SOFTWARE_INVALID with PROVENANCE_BROKEN,
    # and decision before provenance => TEMPORAL_VIOLATION
    future = datetime.now(UTC) + timedelta(days=2)
    cand = _make_valid_synthetic()
    bad_prov = cand.provenance.model_copy(update={"created_at_utc": future})
    bad_cand = cand.model_copy(update={"provenance": bad_prov})
    # explicitly validate at a time before provenance -> broken
    v = validate_candidate_software(
        bad_cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert v.software_standing == "SOFTWARE_INVALID"
    assert "PROVENANCE_BROKEN" in v.rejection_reasons
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            bad_cand,
            decided_by="reviewer@example.com",
            decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
            scientific_standing="PROVIDER_DATA_REQUIRED",
            rationale="broken prov",
            prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
        )
    assert exc.value.code in ("PROVENANCE_BROKEN", "TEMPORAL_VIOLATION")


def test_provenance_must_be_utc() -> None:
    now_naive = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(ValidationError):
        BaselineProvenance(
            created_at_utc=now_naive, created_by="x@example.com", software_version="0.7.0"
        )


def test_secret_path_leakage_refused() -> None:
    with pytest.raises(ValidationError) as exc:
        cand = _make_valid_synthetic()
        ManchesterBaselineCandidatePackage.model_validate(
            {**cand.model_dump(), "limitations": ("/Users/secret/file",)}
        )
    assert "private" in str(exc.value).lower()
    with pytest.raises(ValidationError):
        make_synthetic_candidate(package_id="my-secret-token-package")
    cand = _make_observed_candidate()
    with pytest.raises((ValidationError, ManchesterBaselinePackageError, ValueError)):
        decide_baseline_acceptance(
            cand,
            decided_by="my apikey holder",
            decided_at_utc=_utc_now(),
            scientific_standing="PROVIDER_DATA_REQUIRED",
            rationale="leak",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
        )


def test_traversal_refused() -> None:
    with pytest.raises(ValidationError):
        PortableNetworkFile(
            relative_path="../escape/network.xml",
            sha256="a" * 64,
            byte_size=100,
            media_type="application/xml",
        )
    with pytest.raises(ValidationError):
        PortableNetworkFile(
            relative_path="/etc/passwd",
            sha256="a" * 64,
            byte_size=100,
            media_type="application/xml",
        )


def test_duplicate_network_files_refused() -> None:
    pf = PortableNetworkFile(
        relative_path="networks/a.xml", sha256="a" * 64, byte_size=100, media_type="application/xml"
    )
    with pytest.raises(ValidationError):
        NetworkIdentity(
            tool_reported_version="1.27.1",
            tool_executable_sha256="d" * 64,
            network_files=(pf, pf),
            network_identity_sha256="e" * 64,
            edge_count=0,
            junction_count=0,
        )


def test_duplicate_prerequisites_refused() -> None:
    cand = _make_valid_synthetic()
    with pytest.raises(ValidationError):
        ManchesterBaselineCandidatePackage.model_validate(
            {**cand.model_dump(), "prerequisites": ("boundary", "boundary")}
        )


def test_noncanonical_ordering_refused() -> None:
    pf1 = PortableNetworkFile(
        relative_path="networks/b.xml", sha256="a" * 64, byte_size=100, media_type="application/xml"
    )
    pf2 = PortableNetworkFile(
        relative_path="networks/a.xml", sha256="b" * 64, byte_size=100, media_type="application/xml"
    )
    # inventory sorted but constructor requires sorted input, so unsorted tuple should fail
    sorted_files = sorted((pf1, pf2), key=lambda p: p.relative_path)
    inv = [
        {"relative_path": f.relative_path, "sha256": f.sha256, "byte_size": f.byte_size}
        for f in sorted_files
    ]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValidationError):
        NetworkIdentity(
            tool_reported_version="1.27.1",
            tool_executable_sha256="d" * 64,
            network_files=(pf1, pf2),
            network_identity_sha256=net_sha,
            edge_count=0,
            junction_count=0,
        )


def test_malformed_hash_refused() -> None:
    with pytest.raises(ValidationError):
        PortableNetworkFile(
            relative_path="networks/a.xml",
            sha256="not-a-hash",
            byte_size=100,
            media_type="application/xml",
        )
    with pytest.raises(ValidationError):
        PortableNetworkFile(
            relative_path="networks/a.xml",
            sha256="g" * 64,
            byte_size=100,
            media_type="application/xml",
        )


def test_inconsistent_calibration_stage() -> None:
    with pytest.raises(ValidationError):
        CalibrationIdentity(
            contract_fingerprint=None,
            receipt_fingerprint=None,
            contract_version="v1",
            evidence_class="production",
            calibration_performed=True,
        )


def test_silent_source_inflation() -> None:
    with pytest.raises(ValidationError):
        DemandIdentity(
            identity_fingerprint="e" * 64,
            source_snapshot_ids=("dft_raw_counts-20260725T063354Z-61965dc5c182",),
            provider_evidence_available=False,
        )


def test_decision_against_different_candidate() -> None:
    cand = _make_observed_candidate()
    validation = validate_candidate_software(cand)
    payload = {
        "candidate_fingerprint": "f" * 64,
        "candidate_package_id": cand.package_id,
        "scientific_standing": "PROVIDER_DATA_REQUIRED",
        "decided_by": "reviewer@example.com",
        "decided_at_utc": _utc_now().isoformat(),
        "rationale": "forged",
        "prerequisites_verified": sorted(
            ["boundary", "calibration", "demand", "map_match", "network"]
        ),
        "rejection_reasons": ["PROVIDER_DATA_REQUIRED"],
        "decision_fingerprint": "a" * 64,
    }
    with pytest.raises(ValidationError):
        ManchesterBaselineAcceptanceDecision.model_validate(payload)
    good = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=_utc_now(),
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="all prereqs ok",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=validation,
    )
    assert good.candidate_fingerprint == cand.fingerprint()


def test_missing_prerequisites_blocks_acceptance() -> None:
    cand = _make_observed_candidate()
    validation = validate_candidate_software(cand)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="missing prereq",
            prerequisites_verified=tuple(sorted(["boundary"])),
            software_validation=validation,
        )
    assert exc.value.code == "MISSING_PREREQUISITES"


def test_map_match_unapproved_blocks() -> None:
    cand = _make_observed_candidate()
    mmap = MapMatchPolicyIdentity(
        policy_id="manchester-dft-map-match-owner-policy-1.1",
        policy_fingerprint="f" * 64,
        approved_for_manchester=False,
        requires_named_person_review=True,
    )
    cand2 = cand.model_copy(update={"map_match_policy_identity": mmap})
    val = validate_candidate_software(cand2)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand2,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="unapproved policy",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code == "MAP_MATCH_POLICY_UNAPPROVED"


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        PortableNetworkFile.model_validate(
            {
                "relative_path": "networks/a.xml",
                "sha256": "a" * 64,
                "byte_size": 100,
                "media_type": "application/xml",
                "extra": "nope",
            }
        )


def test_frozen_model() -> None:
    pf = PortableNetworkFile(
        relative_path="networks/a.xml", sha256="a" * 64, byte_size=100, media_type="application/xml"
    )
    with pytest.raises(ValidationError):
        pf.relative_path = "other.xml"  # type: ignore[misc]


# --- Mutation tests for former pass/bypass and deterministic fingerprints ---


def test_provider_evidence_requires_snapshot_ids() -> None:
    with pytest.raises(ValidationError) as exc:
        DemandIdentity(
            identity_fingerprint="e" * 64,
            source_snapshot_ids=(),
            provider_evidence_available=True,
        )
    assert "source snapshot" in str(exc.value).lower()


def test_production_calibration_must_be_performed() -> None:
    with pytest.raises(ValidationError) as exc:
        CalibrationIdentity(
            contract_fingerprint="a" * 64,
            receipt_fingerprint="b" * 64,
            contract_version="v1",
            evidence_class="production",
            calibration_performed=False,
        )
    assert "production calibration" in str(exc.value).lower()


def test_boundary_geographic_mismatch_refused() -> None:
    cand = _make_observed_candidate()
    # mutate geographic boundary sha to mismatch
    geo2 = GeographicIdentity(
        envelope_fingerprint="b" * 64,
        boundary_asset_sha256="d" * 64,
        boundary_asset_name="greater_manchester_combined_authority.geojson",
    )
    payload = {**cand.model_dump(), "geographic_identity": geo2.model_dump()}
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineCandidatePackage.model_validate(payload)
    assert "boundary asset mismatch" in str(exc.value).lower()


def test_boundary_name_mismatch_refused() -> None:
    cand = _make_observed_candidate()
    bound_payload = {
        "scope": "greater_manchester_combined_authority",
        "asset_sha256": "c" * 64,
        "asset_name": "manchester_local_authority.geojson",
    }
    bound_fp2 = hashlib.sha256(
        json.dumps(bound_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    boundary2 = BoundaryIdentity(
        scope="greater_manchester_combined_authority",
        asset_sha256="c" * 64,
        asset_name="manchester_local_authority.geojson",
        identity_fingerprint=bound_fp2,
    )
    payload = {**cand.model_dump(), "boundary_identity": boundary2.model_dump()}
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineCandidatePackage.model_validate(payload)
    assert "boundary asset name mismatch" in str(exc.value).lower()


def test_production_demand_requires_provider_evidence() -> None:
    cand = _make_observed_candidate()
    demand_no_provider = DemandIdentity(
        identity_fingerprint="e" * 64,
        source_snapshot_ids=(),
        provider_evidence_available=False,
    )
    # production evidence with no provider demand should be rejected at candidate validation
    payload = {**cand.model_dump(), "demand_identity": demand_no_provider.model_dump()}
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineCandidatePackage.model_validate(payload)
    assert "production evidence requires provider" in str(exc.value).lower()


def test_production_requires_observed_standing() -> None:
    cand = _make_observed_candidate()
    src_synth = SourceAndRights(
        source_standing="SYNTHETIC_ENGINEERING",
        evidence_standing="SYNTHETIC_ENGINEERING",
        evidence_class="production",
        rights_standing="ODbL-1.0",
        licence_id="ODbL-1.0",
        attribution_text="© OpenStreetMap contributors",
        rights_required_for_acceptance=True,
    )
    payload = {**cand.model_dump(), "source_and_rights": src_synth.model_dump()}
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineCandidatePackage.model_validate(payload)
    assert "production requires" in str(exc.value).lower()


def test_blocked_provider_data_required_must_carry_reason() -> None:
    now = _utc_now()
    # Fingerprint now binds rejection_reasons, receipt bindings and schema fields
    decision_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "candidate_build_receipt_fingerprint": None,
                "candidate_fingerprint": "a" * 64,
                "candidate_package_id": "test-package-001",
                "capability_id": "MAN-09",
                "decided_at_utc": now.isoformat(),
                "decided_by": "reviewer@example.com",
                "method_version": "manchester-baseline-package-1.0",
                "prerequisites_verified": ["boundary"],
                "rationale": "blocked",
                "rejection_reasons": [],
                "schema_version": "1.0",
                "scientific_standing": "PROVIDER_DATA_REQUIRED",
                "software_validation_fingerprint": None,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineAcceptanceDecision(
            candidate_fingerprint="a" * 64,
            candidate_package_id="test-package-001",
            scientific_standing="PROVIDER_DATA_REQUIRED",
            decided_by="reviewer@example.com",
            decided_at_utc=now,
            rationale="blocked",
            prerequisites_verified=("boundary",),
            rejection_reasons=(),
            decision_fingerprint=decision_fingerprint,
        )
    assert "PROVIDER_DATA_REQUIRED must carry" in str(exc.value)


def test_scientific_acceptance_cannot_carry_reasons() -> None:
    cand = _make_observed_candidate()
    now = _utc_now()
    prereqs = tuple(sorted(["boundary", "calibration", "demand", "map_match", "network"]))
    # Fingerprint must bind the actual rejection_reasons and receipt bindings
    validation = validate_candidate_software(cand, validated_at_utc=now)
    decision_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "candidate_build_receipt_fingerprint": cand.build_receipt_fingerprint,
                "candidate_fingerprint": cand.fingerprint(),
                "candidate_package_id": cand.package_id,
                "capability_id": "MAN-09",
                "decided_at_utc": now.isoformat(),
                "decided_by": "reviewer@example.com",
                "method_version": "manchester-baseline-package-1.0",
                "prerequisites_verified": sorted(
                    ["boundary", "calibration", "demand", "map_match", "network"]
                ),
                "rationale": "all ok",
                "rejection_reasons": ["PROVIDER_DATA_REQUIRED"],
                "schema_version": "1.0",
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
                "software_validation_fingerprint": validation.fingerprint(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    payload = {
        "candidate_fingerprint": cand.fingerprint(),
        "candidate_package_id": cand.package_id,
        "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "decided_by": "reviewer@example.com",
        "decided_at_utc": now,
        "rationale": "all ok",
        "prerequisites_verified": prereqs,
        "rejection_reasons": ("PROVIDER_DATA_REQUIRED",),
        "software_validation_fingerprint": validation.fingerprint(),
        "candidate_build_receipt_fingerprint": cand.build_receipt_fingerprint,
        "decision_fingerprint": decision_fingerprint,
    }
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineAcceptanceDecision.model_validate(payload)
    assert "cannot carry rejection" in str(exc.value).lower()


def test_verified_prerequisites_must_be_declared() -> None:
    cand = _make_observed_candidate()
    validation = validate_candidate_software(cand)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="extra prereq",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network", "extra"])
            ),
            software_validation=validation,
        )
    assert exc.value.code == "MISSING_PREREQUISITES"


def test_production_acceptance_requires_approved_map_match() -> None:
    cand = _make_observed_candidate()
    mmap = MapMatchPolicyIdentity(
        policy_id="manchester-dft-map-match-owner-policy-1.1",
        policy_fingerprint="f" * 64,
        approved_for_manchester=False,
        requires_named_person_review=True,
    )
    cand2 = cand.model_copy(update={"map_match_policy_identity": mmap})
    val = validate_candidate_software(cand2)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand2,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="production needs map match",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code == "MAP_MATCH_POLICY_UNAPPROVED"


def test_production_acceptance_requires_calibration() -> None:
    cand = _make_observed_candidate()
    cal_false = CalibrationIdentity(
        contract_fingerprint=None,
        receipt_fingerprint=None,
        contract_version=None,
        evidence_class="synthetic_development",
        calibration_performed=False,
    )
    cand2 = cand.model_copy(
        update={
            "calibration_identity": cal_false,
            "prerequisites": tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
        }
    )
    # Ensure validation deterministic: after provenance
    val = validate_candidate_software(
        cand2, validated_at_utc=cand2.provenance.created_at_utc + timedelta(seconds=5)
    )
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand2,
            decided_by="reviewer@example.com",
            decided_at_utc=cand2.provenance.created_at_utc + timedelta(seconds=10),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="needs calibration",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code in ("MISSING_CALIBRATION", "EVIDENCE_NOT_PRODUCTION")


def test_deterministic_fingerprint_mutation() -> None:
    cand = _make_observed_candidate()
    fp_before = cand.fingerprint()
    # mutate package_id
    cand2 = cand.model_copy(update={"package_id": "observed-baseline-002"})
    assert cand2.fingerprint() != fp_before
    # mutate network file size
    pf = cand.network_identity.network_files[0]
    inv = [{"relative_path": pf.relative_path, "sha256": pf.sha256, "byte_size": pf.byte_size + 1}]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    # need new pf with updated size
    pf2 = PortableNetworkFile(
        relative_path=pf.relative_path,
        sha256=pf.sha256,
        byte_size=pf.byte_size + 1,
        media_type=pf.media_type,
    )
    net2 = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(pf2,),
        network_identity_sha256=net_sha,
        edge_count=cand.network_identity.edge_count,
        junction_count=cand.network_identity.junction_count,
    )
    cand3 = cand.model_copy(update={"network_identity": net2})
    assert cand3.fingerprint() != fp_before
    assert cand3.fingerprint() != cand2.fingerprint()


def test_software_valid_never_implies_scientific() -> None:
    cand = _make_observed_candidate()
    validation = validate_candidate_software(cand)
    assert validation.software_standing == "SOFTWARE_VALID"
    assert validation.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert validation.scientifically_accepted is False
    assert validation.is_scientific_evidence is False
    # Even with SOFTWARE_VALID, decide must explicitly set scientific standing
    # Attempt without provider mismatch should succeed only with explicit decision
    decision = decide_baseline_acceptance(
        cand,
        decided_by="Prof. Reviewer",
        decided_at_utc=_utc_now(),
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="software valid plus all checks",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=validation,
    )
    assert decision.candidate_fingerprint == cand.fingerprint()
    assert decision.scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE"
    assert validation.candidate_fingerprint == decision.candidate_fingerprint


# --- New discriminating tests for remediated gaps ---


def test_acceptance_without_software_validation_blocked() -> None:
    cand = _make_observed_candidate()
    # No software_validation supplied — must fail for ACCEPTED
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="no software validation",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=None,
        )
    assert exc.value.code == "SOFTWARE_NOT_VALID"


def test_synthetic_acceptance_inflation_refused() -> None:
    # Synthetic engineering candidate with forged booleans must never be accepted
    cand_synth = make_synthetic_candidate(provider_data_required=True, approved_map_match=True)
    # Forge synthetic_development to claim production-like fields but keep synthetic class
    # Add calibration performed and build receipt to try to inflate
    cal = CalibrationIdentity(
        contract_fingerprint="1" * 64,
        receipt_fingerprint="2" * 64,
        contract_version="v1",
        evidence_class="synthetic_development",
        calibration_performed=True,
    )
    cand_forged = cand_synth.model_copy(
        update={
            "calibration_identity": cal,
            "provider_data_required": False,
            "source_and_rights": SourceAndRights(
                source_standing="SYNTHETIC_ENGINEERING",
                evidence_standing="SYNTHETIC_ENGINEERING",
                evidence_class="synthetic_development",
                rights_standing="ODbL-1.0",
                licence_id="ODbL-1.0",
                attribution_text="© OpenStreetMap contributors",
                rights_required_for_acceptance=True,
            ),
            "demand_identity": DemandIdentity(
                identity_fingerprint="e" * 64,
                source_snapshot_ids=("dft_raw_counts-20260725T063354Z-61965dc5c182",),
                provider_evidence_available=True,
            ),
            "build_receipt_fingerprint": "9" * 64,
            "prerequisites": tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
        }
    )
    # Re-validate to ensure candidate is structurally valid
    cand_forged = ManchesterBaselineCandidatePackage.model_validate(cand_forged.model_dump())
    val = validate_candidate_software(
        cand_forged, validated_at_utc=cand_forged.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_VALID"
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand_forged,
            decided_by="reviewer@example.com",
            decided_at_utc=cand_forged.provenance.created_at_utc + timedelta(seconds=10),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="forge synthetic as production",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code == "EVIDENCE_NOT_PRODUCTION"


def test_missing_calibration_receipt_blocked() -> None:
    cand = _make_observed_candidate()
    # Remove receipt but keep contract
    cal_no_receipt = CalibrationIdentity(
        contract_fingerprint="1" * 64,
        receipt_fingerprint=None,
        contract_version="v1",
        evidence_class="production",
        calibration_performed=True,
    )
    # Need to bypass CalibrationIdentity model validation that receipt may be None
    # with production? It's allowed per model (only checks contract requires receipt,
    # but receipt missing is allowed structurally); acceptance will block.
    cand2 = cand.model_copy(update={"calibration_identity": cal_no_receipt})
    val = validate_candidate_software(
        cand2, validated_at_utc=cand2.provenance.created_at_utc + timedelta(seconds=5)
    )
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand2,
            decided_by="reviewer@example.com",
            decided_at_utc=cand2.provenance.created_at_utc + timedelta(seconds=10),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="missing receipt",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code == "MISSING_CALIBRATION"


def test_software_decision_time_reversal_blocked() -> None:
    cand = _make_observed_candidate()
    # provenance at helper now, validation at +5s, decision at +2s (reversed)
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=2),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="time reversal",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code == "TEMPORAL_VIOLATION"
    # Also provenance after validation
    early_val_time = cand.provenance.created_at_utc - timedelta(seconds=5)
    val_early = validate_candidate_software(cand, validated_at_utc=early_val_time)
    assert val_early.software_standing == "SOFTWARE_INVALID"
    assert "PROVENANCE_BROKEN" in val_early.rejection_reasons


def test_rejection_reason_mutation_invalidates_fingerprint() -> None:
    cand = _make_valid_synthetic()
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    decided_at = cand.provenance.created_at_utc + timedelta(seconds=10)
    decision = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=decided_at,
        scientific_standing="SCIENTIFICALLY_NOT_ACCEPTED",
        rationale="explicit non-acceptance",
        prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
        software_validation=val,
    )
    # Mutation of rejection_reasons without updating fingerprint must fail
    mutated = {**decision.model_dump(), "rejection_reasons": ("CANDIDATE_TAMPERED",)}
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineAcceptanceDecision.model_validate(mutated)
    assert "decision_fingerprint must bind" in str(exc.value)
    # Also fingerprint must bind rationale
    mutated3 = {**decision.model_dump(), "rationale": "different rationale"}
    with pytest.raises(ValidationError):
        ManchesterBaselineAcceptanceDecision.model_validate(mutated3)


def test_fake_build_receipt_absence_blocked() -> None:
    cand = _make_observed_candidate(with_build_receipt=False)
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_VALID"
    # Software valid but missing build receipt must not be scientifically accepted
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="no build receipt",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code == "BUILD_RECEIPT_MISSING"


def test_provenance_chain_tamper_refused() -> None:
    now = _utc_now()
    # Valid chain with parents empty and no chain is ok
    prov_ok = BaselineProvenance(
        created_at_utc=now, created_by="x@example.com", software_version="0.7.0"
    )
    assert prov_ok.chain_fingerprint is None
    # Valid chain with parents
    parents = tuple(sorted(["a" * 64, "b" * 64]))
    expected_chain = hashlib.sha256(
        json.dumps(list(parents), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    prov_chain = BaselineProvenance(
        created_at_utc=now,
        created_by="x@example.com",
        software_version="0.7.0",
        parent_fingerprints=parents,
        chain_fingerprint=expected_chain,
    )
    assert prov_chain.chain_fingerprint == expected_chain
    # Tampered chain must fail closed via direct construction
    with pytest.raises(ValidationError):
        BaselineProvenance(
            created_at_utc=now,
            created_by="x@example.com",
            software_version="0.7.0",
            parent_fingerprints=parents,
            chain_fingerprint="f" * 64,
        )
    with pytest.raises(ValidationError):
        BaselineProvenance.model_validate(
            {
                "created_at_utc": now,
                "created_by": "x@example.com",
                "software_version": "0.7.0",
                "method_version": "manchester-baseline-package-1.0",
                "parent_fingerprints": list(parents),
                "chain_fingerprint": "0" * 64,
            }
        )


def test_valid_explicitly_evidenced_future_production_acceptance() -> None:
    # Future timestamps explicitly evidenced and coherent must be accepted
    future_prov = datetime(2027, 6, 1, 12, 0, 0, tzinfo=UTC)
    future_val = future_prov + timedelta(seconds=10)
    future_dec = future_val + timedelta(seconds=10)
    pf = PortableNetworkFile(
        relative_path="networks/observed/network.xml",
        sha256="a" * 64,
        byte_size=1000,
        media_type="application/xml",
    )
    inv = [{"relative_path": pf.relative_path, "sha256": pf.sha256, "byte_size": pf.byte_size}]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    geo = GeographicIdentity(
        envelope_fingerprint="b" * 64,
        boundary_asset_sha256="c" * 64,
        boundary_asset_name="greater_manchester_combined_authority.geojson",
    )
    net = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(pf,),
        network_identity_sha256=net_sha,
        edge_count=200,
        junction_count=100,
    )
    bound_fp = hashlib.sha256(
        json.dumps(
            {
                "scope": "greater_manchester_combined_authority",
                "asset_sha256": "c" * 64,
                "asset_name": "greater_manchester_combined_authority.geojson",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    boundary = BoundaryIdentity(
        scope="greater_manchester_combined_authority",
        asset_sha256="c" * 64,
        asset_name="greater_manchester_combined_authority.geojson",
        identity_fingerprint=bound_fp,
    )
    demand = DemandIdentity(
        identity_fingerprint="e" * 64,
        source_snapshot_ids=("dft_raw_counts-20270701T120000Z-aaaaaaaaaaaa",),
        provider_evidence_available=True,
    )
    mmap = MapMatchPolicyIdentity(
        policy_id="manchester-dft-map-match-owner-policy-1.1",
        policy_fingerprint="f" * 64,
        approved_for_manchester=True,
        requires_named_person_review=False,
    )
    cal = CalibrationIdentity(
        contract_fingerprint="1" * 64,
        receipt_fingerprint="2" * 64,
        contract_version="v1",
        evidence_class="production",
        calibration_performed=True,
    )
    src = SourceAndRights(
        source_standing="OBSERVED_MANCHESTER_EVIDENCE",
        evidence_standing="OBSERVED_MANCHESTER_EVIDENCE",
        evidence_class="production",
        rights_standing="ODbL-1.0",
        licence_id="ODbL-1.0",
        attribution_text="© OpenStreetMap contributors, ODbL 1.0",
        rights_required_for_acceptance=True,
    )
    prov = BaselineProvenance(
        created_at_utc=future_prov, created_by="analyst@example.com", software_version="0.7.0"
    )
    cand = ManchesterBaselineCandidatePackage(
        package_id="observed-baseline-future-001",
        geographic_identity=geo,
        network_identity=net,
        boundary_identity=boundary,
        demand_identity=demand,
        map_match_policy_identity=mmap,
        calibration_identity=cal,
        source_and_rights=src,
        limitations=("Future production baseline with explicit evidence",),
        provenance=prov,
        provider_data_required=False,
        prerequisites=tuple(sorted(["boundary", "calibration", "demand", "map_match", "network"])),
        build_receipt_fingerprint="9" * 64,
    )
    val = validate_candidate_software(cand, validated_at_utc=future_val)
    assert val.software_standing == "SOFTWARE_VALID"
    decision = decide_baseline_acceptance(
        cand,
        decided_by="Prof. Future Reviewer",
        decided_at_utc=future_dec,
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="future production with explicit coherent evidence",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=val,
    )
    assert decision.scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE"
    assert decision.decided_at_utc == future_dec


# --- Hardening: receipt binding and verification ---


def test_forged_accepted_decision_without_validation_binding_rejected() -> None:
    cand = _make_observed_candidate()
    now = _utc_now()
    # Attempt to model-validate an ACCEPTED decision without receipt bindings
    forged_fp = hashlib.sha256(
        json.dumps(
            {
                "candidate_build_receipt_fingerprint": None,
                "candidate_fingerprint": cand.fingerprint(),
                "candidate_package_id": cand.package_id,
                "capability_id": "MAN-09",
                "decided_at_utc": now.isoformat(),
                "decided_by": "reviewer@example.com",
                "method_version": "manchester-baseline-package-1.0",
                "prerequisites_verified": sorted(
                    ["boundary", "calibration", "demand", "map_match", "network"]
                ),
                "rationale": "forged without receipts",
                "rejection_reasons": [],
                "schema_version": "1.0",
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
                "software_validation_fingerprint": None,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with pytest.raises(ValidationError) as exc:
        ManchesterBaselineAcceptanceDecision.model_validate(
            {
                "candidate_fingerprint": cand.fingerprint(),
                "candidate_package_id": cand.package_id,
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
                "decided_by": "reviewer@example.com",
                "decided_at_utc": now,
                "rationale": "forged without receipts",
                "prerequisites_verified": tuple(
                    sorted(["boundary", "calibration", "demand", "map_match", "network"])
                ),
                "rejection_reasons": (),
                "software_validation_fingerprint": None,
                "candidate_build_receipt_fingerprint": None,
                "decision_fingerprint": forged_fp,
            }
        )
    assert "must carry" in str(exc.value).lower()


def test_wrong_validation_rejected_by_verification() -> None:
    cand = _make_observed_candidate()
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    decision = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="valid",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=val,
    )
    # Wrong candidate build receipt
    other_cand = cand.model_copy(update={"build_receipt_fingerprint": "8" * 64})
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        verify_baseline_acceptance(decision, other_cand, val)
    assert exc.value.code in ("BUILD_RECEIPT_MISSING", "MISMATCHED_CANDIDATE_FINGERPRINT")
    # Wrong software validation (different candidate)
    other_pf = PortableNetworkFile(
        relative_path="networks/observed/network.xml",
        sha256="b" * 64,
        byte_size=1000,
        media_type="application/xml",
    )
    inv = [
        {
            "relative_path": other_pf.relative_path,
            "sha256": other_pf.sha256,
            "byte_size": other_pf.byte_size,
        }
    ]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    other_net = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(other_pf,),
        network_identity_sha256=net_sha,
        edge_count=200,
        junction_count=100,
    )
    altered_cand = cand.model_copy(update={"network_identity": other_net})
    wrong_val = validate_candidate_software(
        altered_cand, validated_at_utc=altered_cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    with pytest.raises(ManchesterBaselinePackageError):
        verify_baseline_acceptance(decision, cand, wrong_val)
    # Wrong validation via mismatched fingerprint field
    with pytest.raises(ManchesterBaselinePackageError):
        verify_baseline_acceptance(decision, altered_cand, val)


def test_model_copy_mutation_caught_by_verification() -> None:
    cand = _make_observed_candidate()
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    decision = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="valid",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=val,
    )
    # Canonical revalidation: mutate rationale without updating fingerprint must fail at model level
    mutated_dump = decision.model_dump()
    mutated_dump["rationale"] = "mutated rationale"
    with pytest.raises(ValidationError):
        ManchesterBaselineAcceptanceDecision.model_validate(mutated_dump)
    # model_copy on frozen does not revalidate immediately, but canonical
    # revalidation and verification must still catch the mutation
    mutated_via_copy = decision.model_copy(update={"rationale": "mutated rationale"})
    with pytest.raises(ValidationError):
        ManchesterBaselineAcceptanceDecision.model_validate(mutated_via_copy.model_dump())
    with pytest.raises(ManchesterBaselinePackageError):
        verify_baseline_acceptance(mutated_via_copy, cand, val)
    # Create a second candidate with slightly different package_id and verify fails
    cand2 = cand.model_copy(update={"package_id": "observed-baseline-002"})
    with pytest.raises(ManchesterBaselinePackageError):
        verify_baseline_acceptance(decision, cand2, val)
    # Also ensure verify catches decision fingerprint tamper via revalidation
    # Build a decision that is self-consistent but bound to different candidate
    forged = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="valid",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=val,
    )
    # Verify succeeds for exact round trip before mutation
    verify_baseline_acceptance(forged, cand, val)
    # Now verify with mismatched candidate must fail
    with pytest.raises(ManchesterBaselinePackageError):
        forged.verify(cand2, val)


def test_exact_accepted_round_trip_verifies() -> None:
    cand = _make_observed_candidate()
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    decision = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="all good production",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=val,
    )
    # Check bindings are exact
    assert decision.software_validation_fingerprint == val.fingerprint()
    assert decision.candidate_build_receipt_fingerprint == cand.build_receipt_fingerprint
    # Fingerprint includes bindings
    payload = {
        "candidate_fingerprint": cand.fingerprint(),
        "candidate_package_id": cand.package_id,
        "candidate_build_receipt_fingerprint": cand.build_receipt_fingerprint,
        "decided_by": "reviewer@example.com",
        "decided_at_utc": decision.decided_at_utc.isoformat(),
        "prerequisites_verified": sorted(decision.prerequisites_verified),
        "rationale": "all good production",
        "rejection_reasons": [],
        "schema_version": "1.0",
        "capability_id": "MAN-09",
        "method_version": "manchester-baseline-package-1.0",
        "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "software_validation_fingerprint": val.fingerprint(),
    }
    expected_fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert decision.decision_fingerprint == expected_fp
    # Verification succeeds via function and method
    verify_baseline_acceptance(decision, cand, val)
    decision.verify(cand, val)
    # Deserialized round trip still verifies
    restored = ManchesterBaselineAcceptanceDecision.model_validate(decision.model_dump())
    verify_baseline_acceptance(restored, cand, val)


def test_non_accepted_provider_required_path_remains_truthful() -> None:
    cand = _make_valid_synthetic()
    # Decide provider-required without validation (truthful)
    decision = decide_baseline_acceptance(
        cand,
        decided_by="Dr. Sampaio",
        decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
        scientific_standing="PROVIDER_DATA_REQUIRED",
        rationale="blocked due to missing provider data",
        prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
        software_validation=None,
    )
    assert decision.scientific_standing == "PROVIDER_DATA_REQUIRED"
    assert decision.software_validation_fingerprint is None
    assert decision.candidate_build_receipt_fingerprint is None
    assert "PROVIDER_DATA_REQUIRED" in decision.rejection_reasons
    # Verification of non-accepted with exact candidate and no validation must not upgrade
    verify_baseline_acceptance(decision, cand, None)
    decision.verify(cand, None)
    # Even if we supply a synthetic valid software validation, it must not upgrade
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    verify_baseline_acceptance(decision, cand, val)
    assert decision.scientific_standing == "PROVIDER_DATA_REQUIRED"
    # SCIENTIFICALLY_NOT_ACCEPTED also remains truthful — for a provider-required
    # candidate it truthfully carries PROVIDER_DATA_REQUIRED, not invented tamper
    decision2 = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=cand.provenance.created_at_utc + timedelta(seconds=10),
        scientific_standing="SCIENTIFICALLY_NOT_ACCEPTED",
        rationale="explicit non-acceptance",
        prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
        software_validation=val,
    )
    assert decision2.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert decision2.software_validation_fingerprint is None
    # Provider-blocked synthetic must carry PROVIDER_DATA_REQUIRED truthfully
    assert "PROVIDER_DATA_REQUIRED" in decision2.rejection_reasons
    verify_baseline_acceptance(decision2, cand, val)
    # Deserialized still verifies
    restored2 = ManchesterBaselineAcceptanceDecision.model_validate(decision2.model_dump())
    verify_baseline_acceptance(restored2, cand, val)
    # An observed production candidate explicitly marked NOT_ACCEPTED should
    # truthfully carry EXPLICIT_NON_ACCEPTANCE when no other blocker exists
    obs_cand = _make_observed_candidate()
    obs_val = validate_candidate_software(
        obs_cand, validated_at_utc=obs_cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    decision3 = decide_baseline_acceptance(
        obs_cand,
        decided_by="reviewer@example.com",
        decided_at_utc=obs_cand.provenance.created_at_utc + timedelta(seconds=10),
        scientific_standing="SCIENTIFICALLY_NOT_ACCEPTED",
        rationale="explicit non-acceptance for review",
        prerequisites_verified=tuple(
            sorted(["boundary", "calibration", "demand", "map_match", "network"])
        ),
        software_validation=obs_val,
    )
    assert "EXPLICIT_NON_ACCEPTANCE" in decision3.rejection_reasons
    assert decision3.software_validation_fingerprint is None
    assert decision3.candidate_build_receipt_fingerprint is None
    verify_baseline_acceptance(decision3, obs_cand, obs_val)


# --- Focused mutation tests for controller gaps 1-4 ---


def _build_self_consistent_accepted_decision(
    candidate: ManchesterBaselineCandidatePackage,
    software_validation: ManchesterBaselineSoftwareValidation,
    decided_at_utc: datetime,
) -> ManchesterBaselineAcceptanceDecision:
    """Helper to forge a self-consistent ACCEPTED decision binding exact receipts.

    Bypasses :func:`decide_baseline_acceptance` to produce a fingerprint-
    correct payload even when candidate violates rights or other preconditions.
    The decision itself will be structurally valid; verification must still
    refuse it.
    """
    payload = {
        "candidate_fingerprint": candidate.fingerprint(),
        "candidate_package_id": candidate.package_id,
        "candidate_build_receipt_fingerprint": candidate.build_receipt_fingerprint,
        "decided_by": "reviewer@example.com",
        "decided_at_utc": decided_at_utc.isoformat(),
        "prerequisites_verified": sorted(candidate.prerequisites),
        "rationale": "forged self-consistent accepted",
        "rejection_reasons": [],
        "schema_version": "1.0",
        "capability_id": "MAN-09",
        "method_version": "manchester-baseline-package-1.0",
        "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "software_validation_fingerprint": software_validation.fingerprint(),
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ManchesterBaselineAcceptanceDecision.model_validate(
        {
            "candidate_fingerprint": candidate.fingerprint(),
            "candidate_package_id": candidate.package_id,
            "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
            "decided_by": "reviewer@example.com",
            "decided_at_utc": decided_at_utc,
            "rationale": "forged self-consistent accepted",
            "prerequisites_verified": tuple(sorted(candidate.prerequisites)),
            "rejection_reasons": (),
            "software_validation_fingerprint": software_validation.fingerprint(),
            "candidate_build_receipt_fingerprint": candidate.build_receipt_fingerprint,
            "decision_fingerprint": fp,
        }
    )


def test_verification_refuses_unknown_rights_self_consistent_accepted() -> None:
    cand = _make_observed_candidate(rights="UNKNOWN")
    # Rights UNKNOWN but otherwise production-valid; software validation still valid
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_VALID"
    decided_at = cand.provenance.created_at_utc + timedelta(seconds=10)
    forged = _build_self_consistent_accepted_decision(cand, val, decided_at)
    # Structurally self-consistent, but verification must refuse due to rights
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        verify_baseline_acceptance(forged, cand, val)
    assert exc.value.code == "RIGHTS_UNKNOWN"
    # Builder must also refuse to produce acceptance for same candidate
    with pytest.raises(ManchesterBaselinePackageError) as exc2:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="attempt unknown rights",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc2.value.code == "RIGHTS_UNKNOWN"
    # model_copy mutation: start from licensed candidate then mutate rights via model_copy
    licensed = _make_observed_candidate(rights="ODbL-1.0")
    val_licensed = validate_candidate_software(
        licensed, validated_at_utc=licensed.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val_licensed.software_standing == "SOFTWARE_VALID"
    # Mutate candidate rights via model_copy bypass: create mutated candidate and its own validation
    mutated_src = licensed.source_and_rights.model_copy(update={"rights_standing": "UNKNOWN"})
    mutated_cand = licensed.model_copy(update={"source_and_rights": mutated_src})
    val_mutated = validate_candidate_software(
        mutated_cand, validated_at_utc=mutated_cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val_mutated.software_standing == "SOFTWARE_VALID"
    forged2 = _build_self_consistent_accepted_decision(
        mutated_cand, val_mutated, licensed.provenance.created_at_utc + timedelta(seconds=10)
    )
    # Even though forged2 is self-consistent for mutated candidate, shared checker must catch rights
    with pytest.raises(ManchesterBaselinePackageError) as exc3:
        verify_baseline_acceptance(forged2, mutated_cand, val_mutated)
    assert exc3.value.code == "RIGHTS_UNKNOWN"


def test_verification_refuses_unlicensed_rights_self_consistent_accepted() -> None:
    cand = _make_observed_candidate(rights="UNLICENSED")
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_VALID"
    decided_at = cand.provenance.created_at_utc + timedelta(seconds=10)
    forged = _build_self_consistent_accepted_decision(cand, val, decided_at)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        verify_baseline_acceptance(forged, cand, val)
    assert exc.value.code == "RIGHTS_UNLICENSED"
    with pytest.raises(ManchesterBaselinePackageError) as exc2:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="attempt unlicensed",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc2.value.code == "RIGHTS_UNLICENSED"


def test_model_copy_software_standing_rejection_inconsistency_blocked() -> None:
    # Create a candidate whose software validation is INVALID (future provenance)
    future = datetime.now(UTC) + timedelta(days=2)
    base = _make_observed_candidate()
    bad_prov = base.provenance.model_copy(update={"created_at_utc": future})
    bad_cand = base.model_copy(update={"provenance": bad_prov})
    # Validate at time before provenance => INVALID with PROVENANCE_BROKEN
    val_invalid = validate_candidate_software(
        bad_cand, validated_at_utc=base.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val_invalid.software_standing == "SOFTWARE_INVALID"
    assert "PROVENANCE_BROKEN" in val_invalid.rejection_reasons
    # Forged: model_copy to SOFTWARE_VALID while retaining rejection reasons
    forged_val = val_invalid.model_copy(update={"software_standing": "SOFTWARE_VALID"})
    # Direct construction via model_dump with tampered standing must also not pass helper
    # The forged validation is structurally invalid, but model_copy bypassed validator.
    # Canonical revalidation in helper must catch it.
    decided_at = bad_cand.provenance.created_at_utc + timedelta(seconds=10)
    # Build a self-consistent decision that binds the forged validation fingerprint
    # (this decision would be structurally valid if helper didn't revalidate software)
    payload = {
        "candidate_fingerprint": bad_cand.fingerprint(),
        "candidate_package_id": bad_cand.package_id,
        "candidate_build_receipt_fingerprint": bad_cand.build_receipt_fingerprint,
        "decided_by": "reviewer@example.com",
        "decided_at_utc": decided_at.isoformat(),
        "prerequisites_verified": sorted(bad_cand.prerequisites),
        "rationale": "forge invalid as valid",
        "rejection_reasons": [],
        "schema_version": "1.0",
        "capability_id": "MAN-09",
        "method_version": "manchester-baseline-package-1.0",
        "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "software_validation_fingerprint": forged_val.fingerprint(),
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    forged_decision = ManchesterBaselineAcceptanceDecision.model_validate(
        {
            "candidate_fingerprint": bad_cand.fingerprint(),
            "candidate_package_id": bad_cand.package_id,
            "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
            "decided_by": "reviewer@example.com",
            "decided_at_utc": decided_at,
            "rationale": "forge invalid as valid",
            "prerequisites_verified": tuple(sorted(bad_cand.prerequisites)),
            "rejection_reasons": (),
            "software_validation_fingerprint": forged_val.fingerprint(),
            "candidate_build_receipt_fingerprint": bad_cand.build_receipt_fingerprint,
            "decision_fingerprint": fp,
        }
    )
    # Verifier must fail closed (CANDIDATE_TAMPERED via revalidation)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        verify_baseline_acceptance(forged_decision, bad_cand, forged_val)
    assert exc.value.code == "CANDIDATE_TAMPERED"
    # Builder must also fail when given forged validation
    with pytest.raises(ManchesterBaselinePackageError) as exc2:
        decide_baseline_acceptance(
            bad_cand,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="forge invalid as valid",
            prerequisites_verified=tuple(sorted(bad_cand.prerequisites)),
            software_validation=forged_val,
        )
    assert exc2.value.code == "CANDIDATE_TAMPERED"
    # Direct construction of invalid SOFTWARE_VALID with rejection reasons must be refused at model level  # noqa: E501
    with pytest.raises(ValidationError):
        ManchesterBaselineSoftwareValidation.model_validate(
            {**val_invalid.model_dump(), "software_standing": "SOFTWARE_VALID"}
        )


def test_model_copy_software_check_set_mismatch_blocked() -> None:
    cand = _make_observed_candidate()
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_VALID"
    # Craft SOFTWARE_VALID with arbitrary checks_performed (missing one)
    # Use direct construction via model_validate bypass? Do via model_copy to keep valid structure
    forged_checks = tuple(sorted(["boundary_fingerprint"]))  # minimal, not canonical 7
    forged_val = val.model_copy(update={"checks_performed": forged_checks})
    # model_copy bypassed checks validation? checks are sorted/unique but minimal is allowed structurally  # noqa: E501
    # However canonical receipt check must reject it because not equal to validator output
    # Need to create decision binding forged_val
    decided_at = cand.provenance.created_at_utc + timedelta(seconds=10)
    payload = {
        "candidate_fingerprint": cand.fingerprint(),
        "candidate_package_id": cand.package_id,
        "candidate_build_receipt_fingerprint": cand.build_receipt_fingerprint,
        "decided_by": "reviewer@example.com",
        "decided_at_utc": decided_at.isoformat(),
        "prerequisites_verified": sorted(cand.prerequisites),
        "rationale": "forge checks",
        "rejection_reasons": [],
        "schema_version": "1.0",
        "capability_id": "MAN-09",
        "method_version": "manchester-baseline-package-1.0",
        "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "software_validation_fingerprint": forged_val.fingerprint(),
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    forged_decision = ManchesterBaselineAcceptanceDecision.model_validate(
        {
            "candidate_fingerprint": cand.fingerprint(),
            "candidate_package_id": cand.package_id,
            "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
            "decided_by": "reviewer@example.com",
            "decided_at_utc": decided_at,
            "rationale": "forge checks",
            "prerequisites_verified": tuple(sorted(cand.prerequisites)),
            "rejection_reasons": (),
            "software_validation_fingerprint": forged_val.fingerprint(),
            "candidate_build_receipt_fingerprint": cand.build_receipt_fingerprint,
            "decision_fingerprint": fp,
        }
    )
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        verify_baseline_acceptance(forged_decision, cand, forged_val)
    assert exc.value.code == "CANDIDATE_TAMPERED"
    with pytest.raises(ManchesterBaselinePackageError) as exc2:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="forge checks",
            prerequisites_verified=tuple(sorted(cand.prerequisites)),
            software_validation=forged_val,
        )
    assert exc2.value.code == "CANDIDATE_TAMPERED"
    # Direct construction with same forged checks but empty rejection should still be structurally valid  # noqa: E501
    # but canonical verification must catch it; ensure original valid checks still verify
    valid_val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert valid_val.checks_performed == tuple(
        sorted(
            [
                "boundary_fingerprint",
                "demand_source_ids_sorted",
                "limitations_bounded",
                "network_file_identities",
                "no_private_paths",
                "rights_sanitized",
                "provenance_utc",
            ]
        )
    )
    decision = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=decided_at,
        scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
        rationale="canonical",
        prerequisites_verified=tuple(sorted(cand.prerequisites)),
        software_validation=valid_val,
    )
    verify_baseline_acceptance(decision, cand, valid_val)


def test_model_copy_provider_flag_and_snapshot_mutations_blocked() -> None:
    cand = _make_observed_candidate()
    val = validate_candidate_software(
        cand, validated_at_utc=cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_VALID"
    decided_at = cand.provenance.created_at_utc + timedelta(seconds=10)
    # Mutate provider flag via model_copy: set provider_evidence_available False via demand copy
    mutated_demand = cand.demand_identity.model_copy(update={"provider_evidence_available": False})
    mutated_cand = cand.model_copy(update={"demand_identity": mutated_demand})
    # Provider flag mutation makes candidate structurally inconsistent (provider false with snapshot ids)  # noqa: E501
    # Revalidation must catch it as CANDIDATE_TAMPERED before PROVIDER_DATA_REQUIRED
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            mutated_cand,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="provider flag mutated",
            prerequisites_verified=tuple(sorted(cand.prerequisites)),
            software_validation=val,
        )
    assert exc.value.code in ("CANDIDATE_TAMPERED", "PROVIDER_DATA_REQUIRED")
    # Also verify path: craft decision binding mutated candidate and original validation (which mismatches fingerprint)  # noqa: E501
    # First need valid-looking forged validation for mutated candidate? But val was for original cand, fingerprint mismatched.  # noqa: E501
    # Instead test direct snapshot removal: provider still true but snapshot ids empty
    # This direct construction should already be refused by DemandIdentity validator
    with pytest.raises(ValidationError):
        DemandIdentity(
            identity_fingerprint="e" * 64,
            source_snapshot_ids=(),
            provider_evidence_available=True,
        )
    # Via model_copy bypass: create inconsistent demand then embed
    good_demand = cand.demand_identity
    bypass_demand = good_demand.model_copy(update={"source_snapshot_ids": ()})
    # bypass DemandIdentity validator, now candidate has empty snapshots but provider true
    cand_no_snap = cand.model_copy(update={"demand_identity": bypass_demand})
    with pytest.raises(ManchesterBaselinePackageError) as exc2:
        decide_baseline_acceptance(
            cand_no_snap,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="snapshot mutated",
            prerequisites_verified=tuple(sorted(cand.prerequisites)),
            software_validation=val,
        )
    assert exc2.value.code in (
        "CANDIDATE_TAMPERED",
        "PROVIDER_DATA_REQUIRED",
        "MISMATCHED_CANDIDATE_FINGERPRINT",
    )


def test_model_copy_map_match_and_calibration_mutations_blocked() -> None:
    cand = _make_observed_candidate()  # noqa: F841 - val removed, cand used directly
    decided_at = cand.provenance.created_at_utc + timedelta(seconds=10)
    # Map-match approval mutation via model_copy
    mutated_mmap = cand.map_match_policy_identity.model_copy(
        update={"approved_for_manchester": False}
    )
    mutated_cand = cand.model_copy(update={"map_match_policy_identity": mutated_mmap})
    mutated_val = validate_candidate_software(
        mutated_cand, validated_at_utc=mutated_cand.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert mutated_val.software_standing == "SOFTWARE_VALID"
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            mutated_cand,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="map match mutated",
            prerequisites_verified=tuple(sorted(cand.prerequisites)),
            software_validation=mutated_val,
        )
    assert exc.value.code == "MAP_MATCH_POLICY_UNAPPROVED"
    # Verify also refuses
    forged = _build_self_consistent_accepted_decision(mutated_cand, mutated_val, decided_at)
    with pytest.raises(ManchesterBaselinePackageError) as exc2:
        verify_baseline_acceptance(forged, mutated_cand, mutated_val)
    assert exc2.value.code == "MAP_MATCH_POLICY_UNAPPROVED"
    # Calibration receipt mutation: remove receipt via model_copy
    mutated_cal = cand.calibration_identity.model_copy(update={"receipt_fingerprint": None})
    cand_no_receipt = cand.model_copy(update={"calibration_identity": mutated_cal})
    val_no_receipt = validate_candidate_software(
        cand_no_receipt,
        validated_at_utc=cand_no_receipt.provenance.created_at_utc + timedelta(seconds=5),
    )
    assert val_no_receipt.software_standing == "SOFTWARE_VALID"
    with pytest.raises(ManchesterBaselinePackageError) as exc3:
        decide_baseline_acceptance(
            cand_no_receipt,
            decided_by="reviewer@example.com",
            decided_at_utc=decided_at,
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="calibration missing receipt",
            prerequisites_verified=tuple(sorted(cand.prerequisites)),
            software_validation=val_no_receipt,
        )
    assert exc3.value.code == "MISSING_CALIBRATION"
    forged2 = _build_self_consistent_accepted_decision(cand_no_receipt, val_no_receipt, decided_at)
    with pytest.raises(ManchesterBaselinePackageError) as exc4:
        verify_baseline_acceptance(forged2, cand_no_receipt, val_no_receipt)
    assert exc4.value.code == "MISSING_CALIBRATION"
    # Direct construction of calibration with missing receipt but production class is structurally allowed;  # noqa: E501
    # acceptance must still block.


# --- Opus remediation discriminating vectors (must never produce SOFTWARE_VALID, never leak) ---


def test_opus_private_path_vector_never_valid() -> None:
    cand = _make_valid_synthetic()
    # model_copy tampering to inject private path into limitations
    tampered = cand.model_copy(update={"limitations": ("/Users/secret/hidden/file",)})
    val = validate_candidate_software(
        tampered, validated_at_utc=tampered.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing != "SOFTWARE_VALID"
    assert val.software_standing == "SOFTWARE_INVALID"
    assert (
        "SECRET_OR_PATH_LEAKAGE" in val.rejection_reasons
        or "CANDIDATE_TAMPERED" in val.rejection_reasons
    )
    # must not echo private payload
    assert "/Users/secret" not in str(val.rejection_reasons)
    assert "/Users/secret" not in str(val.checks_performed)
    # Direct model_validate with private payload should fail without reaching SOFTWARE_VALID
    # Use raw dict to bypass model_copy freezing but still test canonical revalidation path
    payload = tampered.model_dump(mode="json")
    payload["limitations"] = ["/private/var/secret_leak"]
    tampered3 = cand.model_copy(update={"limitations": ("/private/var/secret_leak",)})
    val3 = validate_candidate_software(
        tampered3, validated_at_utc=tampered3.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val3.software_standing == "SOFTWARE_INVALID"
    assert "/private/var" not in str(val3.rejection_reasons)


def test_opus_secret_like_content_vector_never_valid() -> None:
    cand = _make_valid_synthetic()
    secret_payload = "api_key=[REDACTED]"  # noqa: S105
    tampered = cand.model_copy(update={"limitations": (secret_payload,)})
    val = validate_candidate_software(
        tampered, validated_at_utc=tampered.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_INVALID"
    assert "SECRET_OR_PATH_LEAKAGE" in val.rejection_reasons
    # never echo secret payload
    assert secret_payload not in str(val.rejection_reasons)
    assert secret_payload not in str(val.checks_performed)
    # also secret in package_id via raw attempt
    with pytest.raises((ValueError, Exception)):
        ManchesterBaselineCandidatePackage.model_validate(
            {**cand.model_dump(mode="json"), "package_id": "my-secret-token-package"}
        )


def test_opus_traversal_package_id_vector_never_valid() -> None:
    cand = _make_valid_synthetic()
    tampered = cand.model_copy(update={"package_id": "../escape"})
    val = validate_candidate_software(
        tampered, validated_at_utc=tampered.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_INVALID"
    assert (
        "SECRET_OR_PATH_LEAKAGE" in val.rejection_reasons
        or "CANDIDATE_TAMPERED" in val.rejection_reasons
    )
    assert ".." not in str(val.rejection_reasons) or "SECRET_OR_PATH_LEAKAGE" in str(
        val.rejection_reasons
    )
    # also traversal in network file path is already blocked at construction, but model_copy bypass
    payload = cand.model_dump(mode="json")
    payload["package_id"] = "synthetic-baseline-001"
    # Inject traversal via limitations to ensure not leaked
    tampered2 = cand.model_copy(update={"limitations": ("../escape attempt",)})
    val2 = validate_candidate_software(
        tampered2, validated_at_utc=tampered2.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val2.software_standing == "SOFTWARE_INVALID"


def test_opus_empty_limitations_vector_never_valid() -> None:
    cand = _make_valid_synthetic()
    tampered = cand.model_copy(update={"limitations": ()})
    val = validate_candidate_software(
        tampered, validated_at_utc=tampered.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_INVALID"
    assert "CANDIDATE_TAMPERED" in val.rejection_reasons
    assert val.software_standing == "SOFTWARE_INVALID"


def test_opus_unsorted_inventory_vector_never_valid() -> None:
    # Create two files unsorted
    pf_a = PortableNetworkFile(
        relative_path="networks/a.xml", sha256="a" * 64, byte_size=100, media_type="application/xml"
    )
    pf_b = PortableNetworkFile(
        relative_path="networks/b.xml", sha256="b" * 64, byte_size=100, media_type="application/xml"
    )
    # Sorted inventory sha
    sorted_files = sorted((pf_b, pf_a), key=lambda p: p.relative_path)
    inv = [
        {"relative_path": f.relative_path, "sha256": f.sha256, "byte_size": f.byte_size}
        for f in sorted_files
    ]
    net_sha = hashlib.sha256(
        json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    # Unsorted tuple (pf_b, pf_a) is unsorted
    # Need to bypass validation via model_copy: create valid then mutate
    cand = _make_valid_synthetic()
    # Build a network identity with unsorted files via direct model_dump tampering
    valid_net = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(pf_a, pf_b),
        network_identity_sha256=net_sha,
        edge_count=10,
        junction_count=5,
    )
    # Now tamper to unsorted order without updating sha
    unsorted_net = valid_net.model_copy(update={"network_files": (pf_b, pf_a)})
    tampered = cand.model_copy(update={"network_identity": unsorted_net})
    val = validate_candidate_software(
        tampered, validated_at_utc=tampered.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_INVALID"
    assert (
        "NETWORK_HASH_MISMATCH" in val.rejection_reasons
        or "CANDIDATE_TAMPERED" in val.rejection_reasons
    )


def test_opus_boundary_geographic_divergence_vector_never_valid() -> None:
    cand = _make_observed_candidate()
    # Diverge geographic identity sha
    geo_diverged = GeographicIdentity(
        envelope_fingerprint="b" * 64,
        boundary_asset_sha256="d" * 64,
        boundary_asset_name="greater_manchester_combined_authority.geojson",
    )
    tampered = cand.model_copy(update={"geographic_identity": geo_diverged})
    val = validate_candidate_software(
        tampered, validated_at_utc=tampered.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val.software_standing == "SOFTWARE_INVALID"
    assert (
        "BOUNDARY_MISMATCH" in val.rejection_reasons
        or "CANDIDATE_TAMPERED" in val.rejection_reasons
    )
    # also name divergence
    bound_payload = {
        "scope": "greater_manchester_combined_authority",
        "asset_sha256": "c" * 64,
        "asset_name": "manchester_local_authority.geojson",
    }
    bound_fp2 = hashlib.sha256(
        json.dumps(bound_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    boundary2 = BoundaryIdentity(
        scope="greater_manchester_combined_authority",
        asset_sha256="c" * 64,
        asset_name="manchester_local_authority.geojson",
        identity_fingerprint=bound_fp2,
    )
    tampered2 = cand.model_copy(update={"boundary_identity": boundary2})
    val2 = validate_candidate_software(
        tampered2, validated_at_utc=tampered2.provenance.created_at_utc + timedelta(seconds=5)
    )
    assert val2.software_standing == "SOFTWARE_INVALID"
    assert (
        "BOUNDARY_MISMATCH" in val2.rejection_reasons
        or "CANDIDATE_TAMPERED" in val2.rejection_reasons
    )


def test_opus_model_copy_mutations_never_produce_software_valid() -> None:
    cand = _make_valid_synthetic()
    base_time = cand.provenance.created_at_utc + timedelta(seconds=5)
    vectors: list[dict[str, object]] = [
        {"limitations": ("/Users/opus/private",)},
        {"limitations": ("secret_token_leak",)},
        {"package_id": "../traversal"},
        {"limitations": ()},
    ]
    for upd in vectors:
        tampered = cand.model_copy(update=upd)
        val = validate_candidate_software(tampered, validated_at_utc=base_time)
        assert val.software_standing != "SOFTWARE_VALID", f"vector {upd} produced SOFTWARE_VALID"
        assert val.software_standing == "SOFTWARE_INVALID"
        # checks_performed must be truthful and derived, not falsely claim success
        assert "no_private_paths" in val.checks_performed
        # never leak payload
        for v in upd.values():
            if isinstance(v, str) and "secret" in v.lower():
                assert "secret" not in str(
                    val.rejection_reasons
                ).lower() or "SECRET_OR_PATH_LEAKAGE" in str(val.rejection_reasons)
    # package_id secret
    with pytest.raises((ValueError, Exception)):
        ManchesterBaselineCandidatePackage.model_validate(
            {**cand.model_dump(mode="json"), "package_id": "evil-secret-token"}
        )


def test_package_root_file_integrity_streaming_and_caps() -> None:
    import tempfile
    from pathlib import Path

    cand = _make_valid_synthetic()
    # Ensure deterministic time: candidate uses fixed 2026-01-01
    assert cand.provenance.created_at_utc == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    # Prepare temp root with correct file
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        pf = cand.network_identity.network_files[0]
        target = root / pf.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # Create content for streaming test; declared sha is placeholder
        # so create candidate with matching sha via streaming
        # Build a new candidate with correct sha for this test.
        content = b"hello world synthetic network"
        sha = hashlib.sha256(content).hexdigest()
        size = len(content)
        pf2 = PortableNetworkFile(
            relative_path="networks/synthetic/network.xml",
            sha256=sha,
            byte_size=size,
            media_type="application/xml",
        )
        inv = [
            {"relative_path": pf2.relative_path, "sha256": pf2.sha256, "byte_size": pf2.byte_size}
        ]
        net_sha = hashlib.sha256(
            json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        geo = cand.geographic_identity
        net = NetworkIdentity(
            tool_reported_version="1.27.1",
            tool_executable_sha256="d" * 64,
            network_files=(pf2,),
            network_identity_sha256=net_sha,
            edge_count=10,
            junction_count=5,
        )
        # Reuse other identities from cand but with fixed time
        prov = BaselineProvenance(
            created_at_utc=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            created_by="test-engineer@example.com",
            software_version="0.7.0",
        )
        new_cand = ManchesterBaselineCandidatePackage(
            package_id="synthetic-baseline-001",
            geographic_identity=geo,
            network_identity=net,
            boundary_identity=cand.boundary_identity,
            demand_identity=cand.demand_identity,
            map_match_policy_identity=cand.map_match_policy_identity,
            calibration_identity=cand.calibration_identity,
            source_and_rights=cand.source_and_rights,
            limitations=cand.limitations,
            provenance=prov,
            provider_data_required=cand.provider_data_required,
            prerequisites=cand.prerequisites,
        )
        # Write correct file
        target2 = root / pf2.relative_path
        target2.parent.mkdir(parents=True, exist_ok=True)
        target2.write_bytes(content)
        val_time = prov.created_at_utc + timedelta(seconds=5)
        val = validate_candidate_software(new_cand, validated_at_utc=val_time, package_root=root)
        assert val.software_standing == "SOFTWARE_VALID"
        assert "package_root_file_integrity" in val.checks_performed
        # Tamper file content -> hash mismatch
        target2.write_bytes(b"tampered content")
        with pytest.raises(ManchesterBaselinePackageError) as exc:
            validate_candidate_software(new_cand, validated_at_utc=val_time, package_root=root)
        assert exc.value.code == "NETWORK_HASH_MISMATCH"
        assert "tampered" not in str(exc.value).lower()
        # Test cap: declare huge file exceeding cap should be rejected before unbounded read
        huge_pf = PortableNetworkFile(
            relative_path="networks/synthetic/huge.xml",
            sha256="a" * 64,
            byte_size=600_000_000,  # exceeds 500M cap
            media_type="application/xml",
        )
        inv_huge = [
            {
                "relative_path": huge_pf.relative_path,
                "sha256": huge_pf.sha256,
                "byte_size": huge_pf.byte_size,
            }
        ]
        net_sha_huge = hashlib.sha256(
            json.dumps(inv_huge, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        net_huge = NetworkIdentity(
            tool_reported_version="1.27.1",
            tool_executable_sha256="d" * 64,
            network_files=(huge_pf,),
            network_identity_sha256=net_sha_huge,
            edge_count=0,
            junction_count=0,
        )
        huge_cand = new_cand.model_copy(update={"network_identity": net_huge})
        # Even without file, validation should reject due to cap
        with pytest.raises(ManchesterBaselinePackageError) as exc2:
            validate_candidate_software(huge_cand, validated_at_utc=val_time, package_root=root)
        assert exc2.value.code == "NETWORK_HASH_MISMATCH"
        assert "huge" not in str(exc2.value).lower()
        # Ensure no private path leak in package_root errors
        with pytest.raises(ManchesterBaselinePackageError) as exc3:
            validate_candidate_software(
                new_cand,
                validated_at_utc=val_time,
                package_root="/tmp/secret/path",  # noqa: S108
            )
        # Even if package_root is weird, error must not echo it
        assert "/tmp/secret" not in str(exc3.value)  # noqa: S108


def test_builder_verifier_agree_rights_unknown_provider_false() -> None:
    # Synthetic with rights UNKNOWN and provider_data_required False must be internally coherent
    # and builder/verifier must agree: exact rights blocker, not mislabelled provider absence
    fixed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    cand = make_synthetic_candidate(
        rights_standing="UNKNOWN", provider_data_required=False, created_at_utc=fixed
    )
    assert cand.provider_data_required is False
    assert cand.source_and_rights.rights_standing == "UNKNOWN"
    # Demand must not carry provider evidence (never manufacture)
    assert cand.demand_identity.provider_evidence_available is False
    assert cand.demand_identity.source_snapshot_ids == ()
    # Software validation should be valid (structural)
    val = validate_candidate_software(cand, validated_at_utc=fixed + timedelta(seconds=5))
    assert val.software_standing == "SOFTWARE_VALID"
    # Builder with PROVIDER_DATA_REQUIRED standing must represent exact rights blocker, not mislabel
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="reviewer@example.com",
            decided_at_utc=fixed + timedelta(seconds=10),
            scientific_standing="PROVIDER_DATA_REQUIRED",
            rationale="attempt provider label for rights blocker",
            prerequisites_verified=tuple(sorted(cand.prerequisites)),
            software_validation=val,
        )
    assert exc.value.code == "RIGHTS_UNKNOWN"
    # Builder with NOT_ACCEPTED should carry RIGHTS_UNKNOWN and verify
    decision = decide_baseline_acceptance(
        cand,
        decided_by="reviewer@example.com",
        decided_at_utc=fixed + timedelta(seconds=10),
        scientific_standing="SCIENTIFICALLY_NOT_ACCEPTED",
        rationale="rights unknown blocker",
        prerequisites_verified=tuple(sorted(cand.prerequisites)),
        software_validation=val,
    )
    assert "RIGHTS_UNKNOWN" in decision.rejection_reasons
    assert decision.software_validation_fingerprint is None
    # Verifier must agree with builder's artifact
    verify_baseline_acceptance(decision, cand, val)
    decision.verify(cand, val)
    # Also make_synthetic_candidate deterministic time explicit: same inputs same fingerprint
    cand2 = make_synthetic_candidate(
        rights_standing="UNKNOWN", provider_data_required=False, created_at_utc=fixed
    )
    assert cand.fingerprint() == cand2.fingerprint()


def test_make_synthetic_deterministic_time_explicit() -> None:
    fixed = datetime(2026, 6, 15, 9, 0, 0, tzinfo=UTC)
    cand_fixed = make_synthetic_candidate(created_at_utc=fixed)
    assert cand_fixed.provenance.created_at_utc == fixed
    cand_default = make_synthetic_candidate()
    assert cand_default.provenance.created_at_utc == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    # Same fixed time yields same fingerprint
    cand_fixed2 = make_synthetic_candidate(created_at_utc=fixed)
    assert cand_fixed.fingerprint() == cand_fixed2.fingerprint()
