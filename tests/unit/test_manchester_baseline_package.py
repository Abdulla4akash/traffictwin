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
)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _make_valid_synthetic() -> ManchesterBaselineCandidatePackage:
    return make_synthetic_candidate(provider_data_required=True)


def _make_observed_candidate(
    rights: str = "ODbL-1.0",
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
    validation = validate_candidate_software(
        cand, validated_at_utc=datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    )
    assert validation.software_standing == "SOFTWARE_VALID"
    assert validation.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert validation.scientifically_accepted is False
    assert validation.is_scientific_evidence is False
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand,
            decided_by="Dr. Sampaio",
            decided_at_utc=datetime(2026, 2, 2, 10, 0, 0, tzinfo=UTC),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="attempt to accept synthetic",
            prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
            software_validation=validation,
        )
    assert exc.value.code == "PROVIDER_DATA_REQUIRED"
    blocked = decide_baseline_acceptance(
        cand,
        decided_by="Dr. Sampaio",
        decided_at_utc=datetime(2026, 2, 2, 10, 0, 0, tzinfo=UTC),
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
    future = datetime.now(UTC) + timedelta(days=2)
    cand = _make_valid_synthetic()
    bad_prov = cand.provenance.model_copy(update={"created_at_utc": future})
    bad_cand = cand.model_copy(update={"provenance": bad_prov})
    v = validate_candidate_software(bad_cand)
    assert v.software_standing == "SOFTWARE_INVALID"
    assert "PROVENANCE_BROKEN" in v.rejection_reasons
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            bad_cand,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="PROVIDER_DATA_REQUIRED",
            rationale="broken prov",
            prerequisites_verified=tuple(sorted(["boundary", "demand", "network"])),
        )
    assert exc.value.code == "PROVENANCE_BROKEN"


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
    decision_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "candidate_fingerprint": "a" * 64,
                "candidate_package_id": "test-package-001",
                "scientific_standing": "PROVIDER_DATA_REQUIRED",
                "decided_by": "reviewer@example.com",
                "decided_at_utc": now.isoformat(),
                "rationale": "blocked",
                "prerequisites_verified": ["boundary"],
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
    decision_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "candidate_fingerprint": cand.fingerprint(),
                "candidate_package_id": cand.package_id,
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
                "decided_by": "reviewer@example.com",
                "decided_at_utc": now.isoformat(),
                "rationale": "all ok",
                "prerequisites_verified": sorted(
                    ["boundary", "calibration", "demand", "map_match", "network"]
                ),
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
    # keep production evidence class but calibration false should be caught
    # First need to bypass candidate validation that production requires calibration
    # So use synthetic_development evidence_class for candidate but
    # acceptance with calibration missing prereq should fail
    cand2 = cand.model_copy(
        update={
            "calibration_identity": cal_false,
            "prerequisites": tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
        }
    )
    val = validate_candidate_software(cand2)
    with pytest.raises(ManchesterBaselinePackageError) as exc:
        decide_baseline_acceptance(
            cand2,
            decided_by="reviewer@example.com",
            decided_at_utc=_utc_now(),
            scientific_standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
            rationale="needs calibration",
            prerequisites_verified=tuple(
                sorted(["boundary", "calibration", "demand", "map_match", "network"])
            ),
            software_validation=val,
        )
    assert exc.value.code == "MISSING_CALIBRATION"


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
