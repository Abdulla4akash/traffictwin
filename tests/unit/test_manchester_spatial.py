"""Deterministic admission and refusal evidence for the MAN-07 spatial gate."""

from __future__ import annotations

import json
from base64 import b64decode
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from pyproj import Transformer

from traffictwin.integration.manchester.bods import (
    BodsBoundingBox,
    BodsMemberRef,
    BodsParseScope,
    parse_bods_siri_vm,
)
from traffictwin.integration.manchester.dft import (
    DftCountPointRecord,
    DftMemberRef,
    DftRoadLocation,
)
from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.integration.manchester.spatial import (
    MANCHESTER_SPATIAL_CAPABILITY_ID,
    MANCHESTER_SPATIAL_METHOD_VERSION,
    ManchesterSpatialError,
    ManchesterSpatialPointEvidence,
    SpatialAdmissionPolicy,
    SpatialAdmissionReport,
    bods_spatial_evidence,
    dft_spatial_evidence,
    evaluate_spatial_admission,
    evaluate_spatial_batch,
    source_spatial_policy,
    tfgm_signal_spatial_evidence,
    webtris_spatial_evidence,
)
from traffictwin.integration.manchester.tfgm_signals import (
    TfgmSignalMemberRef,
    parse_tfgm_signal_csv,
)
from traffictwin.integration.manchester.webtris import (
    WebtrisMemberRef,
    parse_webtris_site,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "manchester"
SNAPSHOT = "synthetic_spatial-20260722T120000Z-abcdef012345"
HASH_A = "a" * 64
HASH_B = "b" * 64


def evidence(**changes: object) -> ManchesterSpatialPointEvidence:
    values: dict[str, object] = {
        "source": "synthetic",
        "source_record_fingerprint": HASH_A,
        "point_id": "synthetic:point-1",
        "coordinate_kind": "wgs84",
        "longitude_epsg4326": Decimal("-2.2426"),
        "latitude_epsg4326": Decimal("53.4808"),
        "geographic_scope": "synthetic",
        "scope_basis": "synthetic_contract",
        "scope_evidence_fingerprint": HASH_B,
        "geometry_meaning": "synthetic_point",
        "source_record_state": "eligible",
        "uncertainty_basis": "caller_declared",
        "coordinate_uncertainty_m": Decimal("5"),
        "synthetic": True,
    }
    values.update(changes)
    return ManchesterSpatialPointEvidence.model_validate(values)


def dual_evidence(**changes: object) -> ManchesterSpatialPointEvidence:
    easting = Decimal("383626")
    northing = Decimal("398205")
    longitude, latitude = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True).transform(
        float(easting), float(northing)
    )
    values: dict[str, object] = {
        "source": "dft",
        "source_record_fingerprint": HASH_A,
        "point_id": "dft:12345",
        "coordinate_kind": "bng_and_wgs84",
        "easting_epsg27700": easting,
        "northing_epsg27700": northing,
        "longitude_epsg4326": Decimal(str(longitude)),
        "latitude_epsg4326": Decimal(str(latitude)),
        "geographic_scope": "manchester_local_authority",
        "scope_basis": "audited_dft_authority_e08000003",
        "scope_evidence_fingerprint": HASH_B,
        "geometry_meaning": "road_count_point",
        "source_record_state": "eligible",
        "uncertainty_basis": "source_not_stated",
        "synthetic": False,
    }
    values.update(changes)
    return ManchesterSpatialPointEvidence.model_validate(values)


def test_policy_matrix_records_crs_runtime_and_no_inferred_joins() -> None:
    dual_sources = {"dft", "tfgm_signals"}
    direct_sources = {"webtris", "bods_siri_vm", "synthetic"}
    unavailable_sources = {"randy_tos", "sumo_vec", "analysis_rsu"}

    for source in sorted(dual_sources | direct_sources | unavailable_sources):
        policy = source_spatial_policy(source)  # type: ignore[arg-type]
        assert policy.capability_id == MANCHESTER_SPATIAL_CAPABILITY_ID
        assert policy.method_version == MANCHESTER_SPATIAL_METHOD_VERSION
        assert policy.pyproj_version
        assert policy.proj_version
        assert policy.boundary_inferred_from_coordinates is False
        assert policy.visual_proximity_establishes_identity is False
        if source in dual_sources:
            assert policy.source_crs == ("EPSG:27700", "EPSG:4326")
            assert policy.dual_coordinate_tolerance_m == Decimal("2.5")
        elif source in direct_sources:
            assert policy.source_crs == ("EPSG:4326",)
        else:
            assert policy.source_crs == ()
            assert policy.accepted_coordinate_kinds == ()


def test_source_policy_matrix_cannot_be_semantically_rewritten() -> None:
    policy = source_spatial_policy("webtris")
    changed = policy.model_dump(mode="python")
    changed["required_scope"] = "greater_manchester"
    with pytest.raises(ValidationError, match="frozen MAN-07 policy matrix"):
        SpatialAdmissionPolicy.model_validate(changed)

    unavailable = source_spatial_policy("sumo_vec").model_dump(mode="python")
    unavailable["dual_coordinate_tolerance_m"] = Decimal("2.5")
    with pytest.raises(ValidationError):
        SpatialAdmissionPolicy.model_validate(unavailable)


def test_direct_wgs84_admission_retains_exact_source_values_and_bounds() -> None:
    item = evidence()
    result = evaluate_spatial_admission(item)

    assert result.status == "admitted"
    assert result.reason == "direct_wgs84_admitted"
    assert result.longitude == item.longitude_epsg4326
    assert result.latitude == item.latitude_epsg4326
    assert result.target_bounds is not None
    assert result.target_bounds.min_longitude == item.longitude_epsg4326
    assert result.coordinate_error_m is None
    assert result.transformation_used_for_validation is False
    assert result.map_rendering_available is True
    assert result.identity_join_established is False


def test_dual_coordinate_admission_uses_transform_only_for_validation() -> None:
    item = dual_evidence()
    result = evaluate_spatial_admission(item)

    assert result.status == "admitted"
    assert result.reason == "dual_coordinates_admitted"
    assert result.longitude == item.longitude_epsg4326
    assert result.latitude == item.latitude_epsg4326
    assert result.coordinate_error_m is not None
    assert result.coordinate_error_m <= Decimal("2.5")
    assert result.transformation_used_for_validation is True
    assert result.target_uses_declared_source_wgs84 is True


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        (
            evidence(source_record_state="inactive"),
            "source_record_inactive",
        ),
        (
            evidence(
                source="sumo_vec",
                coordinate_kind="unknown",
                longitude_epsg4326=None,
                latitude_epsg4326=None,
                geographic_scope="unavailable",
                scope_basis="none",
                scope_evidence_fingerprint=None,
                geometry_meaning="simulation_position",
                source_record_state="unavailable",
            ),
            "no_evidenced_coordinate_projection",
        ),
        (
            evidence(
                source="webtris",
                coordinate_kind="unknown",
                longitude_epsg4326=None,
                latitude_epsg4326=None,
                geographic_scope="strategic_approaches",
                scope_basis="selected_webtris_strategic_site",
                geometry_meaning="strategic_road_detector",
            ),
            "unknown_source_crs",
        ),
        (
            evidence(
                source="webtris",
                coordinate_kind="incomplete",
                latitude_epsg4326=None,
                geographic_scope="strategic_approaches",
                scope_basis="selected_webtris_strategic_site",
                geometry_meaning="strategic_road_detector",
            ),
            "source_coordinates_missing",
        ),
        (
            dual_evidence(
                coordinate_kind="bng_only",
                longitude_epsg4326=None,
                latitude_epsg4326=None,
            ),
            "dual_coordinate_evidence_required",
        ),
        (
            evidence(
                source="webtris",
                geographic_scope="unavailable",
                scope_basis="none",
                scope_evidence_fingerprint=None,
                geometry_meaning="strategic_road_detector",
            ),
            "scope_evidence_missing",
        ),
        (
            evidence(
                source="webtris",
                geographic_scope="greater_manchester",
                scope_basis="bods_request_bounds",
                geometry_meaning="strategic_road_detector",
            ),
            "scope_basis_mismatch",
        ),
        (
            evidence(
                source="webtris",
                geographic_scope="strategic_approaches",
                scope_basis="selected_webtris_strategic_site",
                geometry_meaning="traffic_signal_site",
            ),
            "source_semantics_mismatch",
        ),
    ],
)
def test_explicit_refusal_reasons(
    item: ManchesterSpatialPointEvidence,
    reason: str,
) -> None:
    result = evaluate_spatial_admission(item)
    assert result.status == "excluded"
    assert result.reason == reason
    assert result.longitude is None
    assert result.latitude is None
    assert result.target_bounds is None
    assert result.map_rendering_available is False


def test_dual_coordinate_disagreement_is_measured_and_excluded() -> None:
    item = dual_evidence(longitude_epsg4326=Decimal("-3.0"))
    result = evaluate_spatial_admission(item)

    assert result.status == "excluded"
    assert result.reason == "dual_coordinate_mismatch"
    assert result.coordinate_error_m is not None
    assert result.coordinate_error_m > Decimal("2.5")
    assert result.transformation_used_for_validation is True


def test_coordinate_kind_scope_and_uncertainty_are_self_consistent() -> None:
    for mutation in (
        {"coordinate_kind": "unknown"},
        {"scope_evidence_fingerprint": None},
        {"coordinate_uncertainty_m": None},
        {"uncertainty_basis": "source_not_stated"},
        {"source": "synthetic", "synthetic": False},
    ):
        with pytest.raises(ValidationError):
            evidence(**mutation)


def test_official_source_family_can_retain_a_synthetic_fixture_label() -> None:
    item = dual_evidence(synthetic=True)
    assert item.source == "dft"
    assert item.synthetic is True
    assert evaluate_spatial_admission(item).status == "admitted"


def test_batch_is_order_independent_and_completely_reconciled() -> None:
    admitted = evidence()
    excluded = evidence(
        source_record_fingerprint="c" * 64,
        point_id="synthetic:point-2",
        source_record_state="inactive",
    )
    forward = evaluate_spatial_batch((admitted, excluded))
    reverse = evaluate_spatial_batch((excluded, admitted))

    assert forward == reverse
    assert forward.status == "partial"
    assert forward.counts.inputs_seen == 2
    assert forward.counts.admitted == 1
    assert forward.counts.source_state_exclusions == 1
    assert tuple(result.evidence_fingerprint for result in forward.results) == (
        forward.input_evidence_fingerprints
    )


def test_empty_batch_is_explicitly_unavailable() -> None:
    report = evaluate_spatial_batch(())
    assert report.status == "unavailable"
    assert report.counts.inputs_seen == 0
    assert report.results == ()


def test_duplicate_evidence_and_source_records_are_refused() -> None:
    item = evidence()
    with pytest.raises(ManchesterSpatialError, match="duplicate spatial evidence"):
        evaluate_spatial_batch((item, item))

    second = evidence(point_id="synthetic:point-2")
    with pytest.raises(ManchesterSpatialError, match="source record"):
        evaluate_spatial_batch((item, second))


def test_result_and_report_mutations_fail_closed() -> None:
    report = evaluate_spatial_batch((evidence(),))
    result = report.results[0]

    broken_result = result.model_dump(mode="python")
    broken_result["identity_join_established"] = True
    with pytest.raises(ValidationError):
        type(result).model_validate(broken_result)

    broken_result = result.model_dump(mode="python")
    broken_result["policy_fingerprint"] = HASH_A
    with pytest.raises(ValidationError):
        type(result).model_validate(broken_result)

    broken_report = report.model_dump(mode="python")
    broken_report["counts"]["coordinate_exclusions"] = 1
    with pytest.raises(ValidationError):
        SpatialAdmissionReport.model_validate(broken_report)


def test_dft_adapter_preserves_dual_coordinates_and_synthetic_lineage() -> None:
    item = dual_evidence()
    record = DftCountPointRecord(
        source=DftMemberRef(
            snapshot_id=SNAPSHOT,
            member_path="raw/count-point.json",
            member_sha256=HASH_A,
            synthetic=True,
        ),
        row_index=0,
        source_row_id=1,
        count_point_id=12345,
        aadf_year=2025,
        region_id=5,
        local_authority_id=85,
        ons_code="E08000003",
        location=DftRoadLocation(
            road_name="Synthetic road",
            road_category="PA",
            road_type="Major",
            easting=item.easting_epsg27700,
            northing=item.northing_epsg27700,
            longitude=item.longitude_epsg4326,
            latitude=item.latitude_epsg4326,
        ),
    )

    adapted = dft_spatial_evidence(record)
    assert adapted.synthetic is True
    assert adapted.source_record_fingerprint == record.fingerprint()
    assert evaluate_spatial_admission(adapted).status == "admitted"


def test_webtris_adapter_requires_selected_site_scope_and_preserves_status() -> None:
    payload = b64decode((FIXTURES / "webtris" / "site-34.json.b64").read_text(encoding="ascii"))
    ref = WebtrisMemberRef(
        snapshot_id=SNAPSHOT,
        member_path="raw/site-34.json",
        member_sha256=sha256_hex(payload),
        member_role="site",
        synthetic=False,
    )
    record = parse_webtris_site((ref, payload)).records[0]
    adapted = webtris_spatial_evidence(record, selection_fingerprint=HASH_B)

    assert adapted.geometry_meaning == "strategic_road_detector"
    assert adapted.scope_evidence_fingerprint == HASH_B
    assert evaluate_spatial_admission(adapted).status == "admitted"

    with pytest.raises(ValidationError):
        webtris_spatial_evidence(record, selection_fingerprint="not-a-fingerprint")


def test_tfgm_adapter_revalidates_the_preserved_dual_coordinates() -> None:
    payload = b64decode(
        (FIXTURES / "tfgm" / "signals-manchester-3.csv.b64").read_text(encoding="ascii")
    )
    ref = TfgmSignalMemberRef(
        snapshot_id=SNAPSHOT,
        member_path="derived/signals-manchester-3.csv",
        member_sha256=sha256_hex(payload),
        evidence_class="redistributable_derived_sample",
        synthetic=False,
    )
    record = parse_tfgm_signal_csv((ref, payload)).records[0]
    adapted = tfgm_signal_spatial_evidence(record)

    assert adapted.source_record_fingerprint == record.fingerprint()
    assert evaluate_spatial_admission(adapted).reason == "dual_coordinates_admitted"


def test_bods_adapter_binds_request_bounds_without_claiming_bee_membership() -> None:
    payload = (FIXTURES / "bods" / "siri-vm-synthetic.xml").read_bytes()
    ref = BodsMemberRef(
        snapshot_id=SNAPSHOT,
        member_path="private/raw/siri-vm.xml",
        member_sha256=sha256_hex(payload),
        synthetic=True,
    )
    scope = BodsParseScope(
        evaluated_at_utc=datetime(2026, 7, 22, 12, 0, 30, tzinfo=UTC),
        mode="live",
        bounding_box=BodsBoundingBox(
            min_longitude=Decimal("-3"),
            min_latitude=Decimal("53"),
            max_longitude=Decimal("-1.5"),
            max_latitude=Decimal("54"),
        ),
    )
    record = parse_bods_siri_vm((ref, payload), scope).records[0]
    adapted = bods_spatial_evidence(record, request_bounds_fingerprint=scope.fingerprint())

    assert adapted.synthetic is True
    assert adapted.geometry_meaning == "transit_vehicle_position"
    assert adapted.geographic_scope == "request_bounding_box"
    assert record.bee_network_membership == "unverified"
    assert evaluate_spatial_admission(adapted).status == "admitted"


def test_models_are_strict_frozen_and_canonical_json_is_stable() -> None:
    item = evidence()
    round_trip = ManchesterSpatialPointEvidence.model_validate_json(item.canonical_json())
    assert round_trip == item
    assert round_trip.fingerprint() == item.fingerprint()
    with pytest.raises(ValidationError):
        ManchesterSpatialPointEvidence.model_validate(
            {**json.loads(item.canonical_json()), "unexpected": "field"}
        )
    with pytest.raises(ValidationError):
        item.point_id = "changed"  # type: ignore[misc]
