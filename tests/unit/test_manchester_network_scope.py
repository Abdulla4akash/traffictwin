"""Adversarial scope, inclusion, CRS, and DfT-coverage evidence for the baseline network."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pyproj
import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.network_scope import (
    BASELINE_SCOPE,
    ENVELOPE_MARGIN_DEGREES,
    ENVELOPE_UNCERTAINTY_M,
    SUB_AREA_SCOPE,
    BaselineScopeDecision,
    DftCalibrationCoverage,
    ExtractEnvelope,
    GeographicPoint,
    ManchesterNetworkScopeError,
    baseline_scope_decision,
    classify_dft_coverage,
    derive_extract_envelope,
    evaluate_required_areas,
    in_baseline,
    in_sub_area,
)


def _point(longitude: str, latitude: str) -> GeographicPoint:
    return GeographicPoint(longitude=Decimal(longitude), latitude=Decimal(latitude))


def _mutated_decision(**changes: str) -> dict[str, Any]:
    """Return a JSON payload of the real decision with adversarial changes applied."""

    payload: dict[str, Any] = json.loads(baseline_scope_decision().canonical_json())
    payload.update(changes)
    return payload


def _validate(payload: dict[str, Any]) -> BaselineScopeDecision:
    """Validate through JSON so the strict frozen models parse their own dump."""

    return BaselineScopeDecision.model_validate_json(json.dumps(payload))


class TestBaselineScopeDecision:
    def test_greater_manchester_is_the_baseline_and_manchester_is_a_filter(self) -> None:
        decision = baseline_scope_decision()
        assert decision.baseline_scope == BASELINE_SCOPE == "greater_manchester_combined_authority"
        assert decision.baseline_official_code == "E47000001"
        assert decision.sub_area_scope == SUB_AREA_SCOPE == "manchester_local_authority"
        assert decision.sub_area_official_code == "E08000003"
        assert decision.sub_area_is_filter is True
        assert decision.sub_area_is_second_network is False

    def test_decision_stays_planned_and_cites_its_record(self) -> None:
        decision = baseline_scope_decision()
        assert decision.capability_status == "planned"
        assert decision.decision_record == "ADR-059"
        assert decision.capability_id == "MAN-09"

    def test_decision_is_deterministic(self) -> None:
        assert baseline_scope_decision().fingerprint() == baseline_scope_decision().fingerprint()

    def test_decision_records_the_active_projection_runtime(self) -> None:
        decision = baseline_scope_decision()
        assert decision.pyproj_version == pyproj.__version__
        assert decision.proj_version == pyproj.proj_version_str
        assert decision.geographic_crs == "EPSG:4326"
        assert decision.distance_crs == "EPSG:27700"

    def test_decision_rejects_a_stale_projection_runtime(self) -> None:
        payload = _mutated_decision(pyproj_version="0.0.0-not-installed")
        with pytest.raises(ValidationError, match="active pyproj version"):
            _validate(payload)


class TestRequiredAreaInclusion:
    def test_city_centre_and_university_are_inside_the_baseline(self) -> None:
        probes = {probe.area: probe for probe in baseline_scope_decision().required_areas}
        assert set(probes) == {"manchester_city_centre", "university_of_manchester"}
        for probe in probes.values():
            assert probe.inside_baseline_boundary is True, probe.area
            assert probe.inside_baseline_envelope is True, probe.area

    def test_required_areas_also_fall_inside_the_manchester_filter(self) -> None:
        for probe in baseline_scope_decision().required_areas:
            assert probe.inside_sub_area_boundary is True, probe.area

    def test_probes_carry_their_evaluation_frame_and_no_traffic_claim(self) -> None:
        for probe in baseline_scope_decision().required_areas:
            assert probe.evaluation_frame == "EPSG:4326"
            assert probe.traffic_observation_claim is False

    def test_a_decision_missing_a_required_area_is_refused(self) -> None:
        payload = _mutated_decision()
        payload["required_areas"][0]["inside_baseline_boundary"] = False
        with pytest.raises(ValidationError, match="must contain every required area"):
            _validate(payload)

    def test_a_decision_with_a_substituted_probe_set_is_refused(self) -> None:
        payload = _mutated_decision()
        payload["required_areas"] = payload["required_areas"][:1] * 2
        with pytest.raises(ValidationError, match="reviewed inclusion set"):
            _validate(payload)


class TestSubAreaIsAStrictSubset:
    @pytest.mark.parametrize(
        ("longitude", "latitude", "label"),
        [
            ("-2.6300", "53.5450", "Wigan"),
            ("-2.1600", "53.4100", "Stockport"),
        ],
    )
    def test_points_inside_greater_manchester_can_be_outside_the_filter(
        self, longitude: str, latitude: str, label: str
    ) -> None:
        point = _point(longitude, latitude)
        assert in_baseline(point) is True, label
        assert in_sub_area(point) is False, label

    def test_a_point_outside_both_scopes_is_reported_outside(self) -> None:
        leeds = _point("-1.5491", "53.8008")
        assert in_baseline(leeds) is False
        assert in_sub_area(leeds) is False

    def test_containment_never_mutates_the_tested_point(self) -> None:
        point = _point("-2.6300", "53.5450")
        in_baseline(point)
        in_sub_area(point)
        assert point.longitude == Decimal("-2.6300")
        assert point.latitude == Decimal("53.5450")


class TestExtractEnvelope:
    def test_envelope_is_labelled_derived_and_not_an_administrative_boundary(self) -> None:
        envelope = derive_extract_envelope()
        assert envelope.derivation == "derived_from_display_geometry"
        assert envelope.administrative_boundary is False
        assert envelope.scientific_clipping_boundary is False

    def test_envelope_declares_its_margin_and_uncertainty(self) -> None:
        envelope = derive_extract_envelope()
        assert envelope.margin_degrees == ENVELOPE_MARGIN_DEGREES
        assert envelope.boundary_uncertainty_m == ENVELOPE_UNCERTAINTY_M

    def test_envelope_contains_the_generalised_outline_it_was_derived_from(self) -> None:
        envelope = derive_extract_envelope()
        # Observed Greater Manchester display extent, plus the declared margin.
        assert envelope.min_longitude <= Decimal("-2.7304")
        assert envelope.max_longitude >= Decimal("-1.9096")
        assert envelope.min_latitude <= Decimal("53.3274")
        assert envelope.max_latitude >= Decimal("53.6857")

    def test_envelope_is_wider_than_the_national_highways_operational_envelope(self) -> None:
        # Design §10 reviewed NH envelope: lat 53.30-53.70, lon -2.60 to -1.90.
        # Greater Manchester extends further west; the two are never equal coverage.
        envelope = derive_extract_envelope()
        assert envelope.min_longitude < Decimal("-2.60")

    def test_a_non_positive_margin_is_refused(self) -> None:
        with pytest.raises(ManchesterNetworkScopeError, match="ENVELOPE_MARGIN_REFUSED"):
            derive_extract_envelope(margin_degrees=Decimal("0"))

    def test_an_excessive_margin_is_refused(self) -> None:
        with pytest.raises(ManchesterNetworkScopeError, match="ENVELOPE_MARGIN_REFUSED"):
            derive_extract_envelope(margin_degrees=Decimal("5"))

    def test_an_inverted_envelope_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="longitude range must be increasing"):
            ExtractEnvelope(
                min_longitude=Decimal("-1.0"),
                min_latitude=Decimal("53.0"),
                max_longitude=Decimal("-2.0"),
                max_latitude=Decimal("54.0"),
                margin_degrees=ENVELOPE_MARGIN_DEGREES,
                boundary_uncertainty_m=ENVELOPE_UNCERTAINTY_M,
            )

    def test_envelope_containment_is_inclusive_and_reports_outside_points(self) -> None:
        envelope = derive_extract_envelope()
        assert envelope.contains(_point("-2.2446", "53.4779")) is True
        assert envelope.contains(_point("-1.5491", "53.8008")) is False


class TestDftCalibrationCoverage:
    def test_coverage_is_partial_over_the_greater_manchester_baseline(self) -> None:
        coverage = DftCalibrationCoverage()
        assert coverage.baseline_scope == "greater_manchester_combined_authority"
        assert coverage.observation_scope == "manchester_local_authority"
        assert coverage.coverage_kind == "partial"

    def test_uncovered_locations_are_unavailable_and_never_zero(self) -> None:
        coverage = DftCalibrationCoverage()
        assert coverage.uncovered_state == "unavailable"
        assert coverage.uncovered_is_zero is False
        assert coverage.missing_filled_with_zero is False

    def test_coverage_makes_no_calibration_or_validity_claim(self) -> None:
        coverage = DftCalibrationCoverage()
        assert coverage.calibration_performed is False
        assert coverage.model_validity_claimed is False

    def test_city_centre_is_covered_by_dft_evidence(self) -> None:
        assert classify_dft_coverage(_point("-2.2446", "53.4779")) == "covered"

    @pytest.mark.parametrize(
        ("longitude", "latitude", "label"),
        [
            ("-2.6300", "53.5450", "Wigan"),
            ("-2.1600", "53.4100", "Stockport"),
        ],
    )
    def test_greater_manchester_locations_outside_the_filter_are_uncovered(
        self, longitude: str, latitude: str, label: str
    ) -> None:
        point = _point(longitude, latitude)
        assert in_baseline(point) is True, label
        assert classify_dft_coverage(point) == "uncovered", label

    def test_uncovered_never_becomes_a_numeric_zero(self) -> None:
        state: object = classify_dft_coverage(_point("-2.6300", "53.5450"))
        assert state == "uncovered"
        # An uncovered location must stay a categorical state, never a count.
        assert isinstance(state, str)
        assert not isinstance(state, int | float)


class TestCoordinateHandling:
    def test_coordinates_are_bounded_to_six_decimal_places(self) -> None:
        with pytest.raises(ValidationError, match="six decimal places"):
            GeographicPoint(longitude=Decimal("-2.24460001"), latitude=Decimal("53.4779"))

    def test_out_of_range_coordinates_are_refused(self) -> None:
        with pytest.raises(ValidationError):
            GeographicPoint(longitude=Decimal("-200"), latitude=Decimal("53.4779"))

    def test_required_area_evaluation_is_stable_across_calls(self) -> None:
        envelope = derive_extract_envelope()
        first = evaluate_required_areas(envelope)
        second = evaluate_required_areas(envelope)
        assert [probe.model_dump(mode="json") for probe in first] == [
            probe.model_dump(mode="json") for probe in second
        ]
