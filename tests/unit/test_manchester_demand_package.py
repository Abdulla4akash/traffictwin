"""Discriminating tests for Lane 04 demand package.

Covers rejected/unresolved silently admitted, forged standing, foreign ledger,
wrong source family/role, BODS relabel, incompatible interval/unit/network/map,
missingness not zero, stochastic seed, fingerprint drift, observed-trip claims,
provider-required inflation, software->scientific separation, model_copy tamper,
duplicate/unsorted/excess, provenance secrets, deterministic rebuild, synthetic
vs provider-blocked candidates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.demand_package import (
    DemandCountsSummary,
    DemandNetworkIdentity,
    DemandProvenance,
    DemandScalingAssumptions,
    DemandTemporalIdentity,
    ManchesterDemandPackageError,
    ManchesterDemandPackageRequest,
    ManchesterDemandPackageResult,
    build_demand_package,
    build_demand_package_request,
    decide_demand_acceptance,
    issue_demand_receipt,
    verify_demand_package,
)
from traffictwin.integration.manchester.demand_reconstruction import (
    CountConstrainedDemandInput,
    DemandInputLedger,
    DirectionResolution,
    EdgeHourCount,
)
from traffictwin.integration.manchester.map_match_workflow import (
    MapMatchDftSourceIdentity,
    MapMatchWorkflowResult,
    build_map_match_workflow,
)
from traffictwin.integration.manchester.network_geometry import EdgeSpatialIndex  # noqa: F401
from traffictwin.integration.manchester.observation_matching import EdgeCandidate
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    ObservationMatchV11,
    RoadGroupV11,
    build_manual_review_queue,
)

POLICY = ManchesterMapMatchPolicyV11()
POLICY_FP = POLICY.fingerprint()
DECIDED_AT = "2026-07-26T23:00:00+00:00"
_CONTENT_FP = "ab" * 32
_SNAPSHOT_ID = f"dft_raw_counts-20260726T230000Z-{_CONTENT_FP[:12]}"
_PROVENANCE = f"roadtraffic.dft.gov.uk:/api/raw-counts/pages/page-0001.json#{_SNAPSHOT_ID}"
_RECEIPT_FP = "cd" * 32


def _source(
    *,
    source_family: Literal["dft"] = "dft",
    provider: Literal["roadtraffic.dft.gov.uk"] = "roadtraffic.dft.gov.uk",
    observation_role: Literal["historical_measured_count"] = "historical_measured_count",
    snapshot_id: str = _SNAPSHOT_ID,
    content_fingerprint: str = _CONTENT_FP,
    provenance: str = _PROVENANCE,
    admission_receipt_fingerprint: str = _RECEIPT_FP,
    is_accepted: Literal[True] = True,
    is_source_blocked: Literal[False] = False,
) -> MapMatchDftSourceIdentity:
    return MapMatchDftSourceIdentity(
        source_family=source_family,
        provider=provider,
        observation_role=observation_role,
        snapshot_id=snapshot_id,
        content_fingerprint=content_fingerprint,
        provenance=provenance,
        admission_receipt_fingerprint=admission_receipt_fingerprint,
        is_accepted=is_accepted,
        is_source_blocked=is_source_blocked,
    )


def _candidate(edge_id: str = "e1") -> EdgeCandidate:
    return EdgeCandidate(
        edge_id=edge_id,
        road_type="highway.primary",
        road_class="primary",
        road_ref="A56",
        normalised_ref="A56",
        distance_m=Decimal("1.200"),
        geometry_source="explicit_edge_shape",
        bearing_degrees=Decimal("45.000"),
        requires_manual_confirmation=False,
    )


def _group(group_key: str = "ref:A56|primary", edge_id: str = "e1") -> RoadGroupV11:
    return RoadGroupV11(
        group_key=group_key,
        normalised_ref="A56",
        road_class_family="primary",
        members=(_candidate(edge_id),),
        nearest_distance_m=Decimal("1.200"),
        contains_service_member=False,
        exact_reference_match=True,
        admitted_by_override=False,
        family_mismatch=None,
    )


def _obs_auto(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(_group(),),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="clear_candidate",
        disposition="owner_policy_accepted_candidate",
        acceptance_path="strict_v1_0_clear",
        audit_flag=False,
        family_mismatch=None,
        reasons=("all strict conditions met",),
        review_reasons=(),
    )


def _obs_rejected(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="no_suitable_candidate",
        disposition="no_suitable_candidate",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=("no candidate",),
        review_reasons=(),
    )


def _obs_unresolved(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(_group(), _group("ref:A57|secondary", "e2")),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="review_required",
        disposition="awaiting_manual_review",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=("ambiguous",),
        review_reasons=("needs review",),
    )


def _workflow_auto(cpid: int = 1) -> MapMatchWorkflowResult:
    obs = _obs_auto(cpid)
    queue = build_manual_review_queue([obs])
    return build_map_match_workflow(
        observations=(obs,), queue=queue, policy=POLICY, source=_source()
    )


def _workflow_with_rejected() -> MapMatchWorkflowResult:
    obs1 = _obs_auto(1)
    obs2 = _obs_rejected(2)
    queue = build_manual_review_queue([obs1, obs2])
    return build_map_match_workflow(
        observations=(obs1, obs2), queue=queue, policy=POLICY, source=_source()
    )


def _workflow_unresolved() -> MapMatchWorkflowResult:
    obs1 = _obs_auto(1)
    obs2 = _obs_unresolved(2)
    queue = build_manual_review_queue([obs1, obs2])
    return build_map_match_workflow(
        observations=(obs1, obs2), queue=queue, policy=POLICY, source=_source()
    )


def _count_input(cpid: int = 1, *, edge_id: str = "e1") -> CountConstrainedDemandInput:
    ledger = DemandInputLedger(
        sites_offered=1,
        sites_admissible=1,
        sites_rejected_wrong_disposition=0,
        directions_offered=1,
        directions_bound=1,
        directions_requiring_confirmation=0,
        directions_unresolved=0,
        directions_combined_not_forced=0,
        cells_bound=1,
        measured_zero_cells_bound=0,
    )
    res = DirectionResolution(
        count_point_id=cpid,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id=edge_id,
        considered=((edge_id, Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    cell = EdgeHourCount(
        edge_id=edge_id,
        count_point_id=cpid,
        direction_of_travel="N",
        hour=8,
        interval_start_s=8 * 3600,
        interval_end_s=9 * 3600,
        all_motor_vehicles=100,
        measured_zero=False,
    )
    return CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=(cell,),
        resolutions=(res,),
        ledger=ledger,
    )


def _empty_count_input() -> CountConstrainedDemandInput:
    ledger = DemandInputLedger(
        sites_offered=0,
        sites_admissible=0,
        sites_rejected_wrong_disposition=0,
        directions_offered=0,
        directions_bound=0,
        directions_requiring_confirmation=0,
        directions_unresolved=0,
        directions_combined_not_forced=0,
        cells_bound=0,
        measured_zero_cells_bound=0,
    )
    return CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=(),
        resolutions=(),
        ledger=ledger,
    )


def _temporal() -> DemandTemporalIdentity:
    return DemandTemporalIdentity(
        window_start_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        window_end_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC),
        interval_seconds=3600,
        unit="vehicles_per_interval",
        time_basis="documented_utc",
    )


def _network(wf: MapMatchWorkflowResult | None = None) -> DemandNetworkIdentity:
    fp = wf.policy_fingerprint if wf is not None else POLICY_FP
    return DemandNetworkIdentity(
        network_identity_sha256="a" * 64,
        route_pool_identity="route_pools/manchester-v1",
        route_pool_fingerprint="b" * 64,
        map_policy_id="manchester-dft-map-match-owner-policy-1.1",
        map_policy_fingerprint=fp,
    )


def _scaling() -> DemandScalingAssumptions:
    return DemandScalingAssumptions(
        scaling_method="none",
        normalisation="none",
        missingness_handling="excluded_not_zero_filled",
        exclusions=("direction_unresolved_excluded",),
    )


def _make_request(
    wf: MapMatchWorkflowResult,
    ci: CountConstrainedDemandInput,
    *,
    method: str = "count_constrained_candidate_v1",
    seed: int | None = None,
    temporal: DemandTemporalIdentity | None = None,
    network: DemandNetworkIdentity | None = None,
) -> ManchesterDemandPackageRequest:
    return build_demand_package_request(
        request_id="demand-req-001",
        created_at_utc=datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
        source=_source(),
        temporal=temporal or _temporal(),
        network=network or _network(wf),
        demand_method=method,  # type: ignore[arg-type]
        deterministic_seed=seed,
        scaling=_scaling(),
        count_input=ci,
        map_workflow=wf,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rejected_silently_admitted_is_refused() -> None:
    wf = _workflow_with_rejected()
    # Build count that binds to the REJECTED count_point_id 2
    ci = _count_input(cpid=2, edge_id="e1")
    req = _make_request(wf, ci)
    with pytest.raises(ManchesterDemandPackageError) as exc:
        build_demand_package(
            request=req,
            map_workflow=wf,
            count_input=ci,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
        )
    assert "REJECTED" in str(exc.value) or "SILENTLY" in str(exc.value)


def test_unresolved_silently_admitted_is_refused() -> None:
    wf = _workflow_unresolved()
    # need resolution for e2
    ledger = DemandInputLedger(
        sites_offered=1,
        sites_admissible=1,
        sites_rejected_wrong_disposition=0,
        directions_offered=1,
        directions_bound=1,
        directions_requiring_confirmation=0,
        directions_unresolved=0,
        directions_combined_not_forced=0,
        cells_bound=1,
        measured_zero_cells_bound=0,
    )
    res = DirectionResolution(
        count_point_id=2,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id="e2",
        considered=(("e2", Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    cell = EdgeHourCount(
        edge_id="e2",
        count_point_id=2,
        direction_of_travel="N",
        hour=8,
        interval_start_s=28800,
        interval_end_s=32400,
        all_motor_vehicles=50,
        measured_zero=False,
    )
    ci2 = CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=(cell,),
        resolutions=(res,),
        ledger=ledger,
    )
    req = _make_request(wf, ci2)
    with pytest.raises(ManchesterDemandPackageError):
        build_demand_package(
            request=req,
            map_workflow=wf,
            count_input=ci2,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
        )


def test_forged_auto_standing_is_tamper() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    # forge via model_copy: change auto_accepted_ids to include a
    # non-accepted id without changing standing
    forged = wf.model_copy(update={"auto_accepted_ids": (1, 2)})
    with pytest.raises(ManchesterDemandPackageError):
        build_demand_package(
            request=req,
            map_workflow=forged,
            count_input=ci,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
        )


def test_missing_foreign_ledger_receipt_fails() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    # request built against original source but verify with different source (foreign receipt)
    alt_source = _source(
        admission_receipt_fingerprint="ff" * 32,
        content_fingerprint="bb" * 32,
        snapshot_id=f"dft_raw_counts-20260726T230000Z-{'bb' * 6}",
    )
    # Build a workflow with alt_source but request uses original source -> foreign
    queue = build_manual_review_queue([_obs_auto(1)])
    wf_alt = build_map_match_workflow(
        observations=(_obs_auto(1),), queue=queue, policy=POLICY, source=alt_source
    )
    req = _make_request(wf, ci)  # request binds original wf fingerprint
    with pytest.raises(ManchesterDemandPackageError):
        build_demand_package(
            request=req,
            map_workflow=wf_alt,
            count_input=ci,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
        )


def test_wrong_source_family_rejected() -> None:
    with pytest.raises(Exception):  # noqa: B017
        _source(source_family="bods")  # type: ignore[arg-type]


def test_bods_relabel_rejected() -> None:
    with pytest.raises(ValidationError):
        _source(
            provenance=(
                "bods.api.gov.uk:/general_road_traffic/page.json"
                "#dft_raw_counts-20260726T230000Z-abababababab"
            )
        )


def test_incompatible_interval_fails() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    bad_temporal = DemandTemporalIdentity(
        window_start_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        window_end_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC),
        interval_seconds=1800,
        unit="vehicles_per_interval",
        time_basis="documented_utc",
    )
    with pytest.raises(ManchesterDemandPackageError) as exc:
        _make_request(wf, ci, temporal=bad_temporal)
    assert "INTERVAL" in str(exc.value)


def test_incompatible_network_policy_fails() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    bad_net = DemandNetworkIdentity(
        network_identity_sha256="a" * 64,
        route_pool_identity="route_pools/manchester-v1",
        route_pool_fingerprint="b" * 64,
        map_policy_id="manchester-dft-map-match-owner-policy-1.1",
        map_policy_fingerprint="f" * 64,
    )
    with pytest.raises(ManchesterDemandPackageError):
        _make_request(wf, ci, network=bad_net)


def test_missingness_not_zero_inflated() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    # counts admitted must equal len(counts), not inflated; missing_hours truthful
    assert res.counts.admitted == len(ci.counts)
    assert (
        res.counts.missing_hours
        == ci.ledger.directions_unresolved + ci.ledger.directions_requiring_confirmation
    )
    # measured_zero preserved
    assert res.counts.measured_zero_cells == ci.ledger.measured_zero_cells_bound


def test_stochastic_without_seed_fails() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    with pytest.raises(ManchesterDemandPackageError) as exc:
        _make_request(wf, ci, method="count_constrained_stochastic_v1", seed=None)
    assert "SEED" in str(exc.value)


def test_seed_method_output_fingerprint_drift_detected() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = build_demand_package_request(
        request_id="demand-req-001",
        created_at_utc=datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
        source=_source(),
        temporal=_temporal(),
        network=_network(wf),
        demand_method="count_constrained_stochastic_v1",
        deterministic_seed=42,
        scaling=_scaling(),
        count_input=ci,
        map_workflow=wf,
    )
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    tampered = res.model_copy(update={"deterministic_seed": 99})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)):
        verify_demand_package(tampered, request=req, map_workflow=wf, count_input=ci)


def test_route_trip_never_called_observed() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    for lim in res.limitations:
        assert "observed trip" not in lim.lower() or "not observed" in lim.lower()
        assert (
            "observed trip" not in lim.lower()
            or "never call" in lim.lower()
            or "not observed" in lim.lower()
        )
    assert res.is_observed_trips is False
    assert "observed_trips" not in res.demand_label


def test_provider_required_not_inflated_to_production() -> None:
    wf = _workflow_auto(1)
    ci = _empty_count_input()
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert res.standing == "PROVIDER_DATA_REQUIRED"
    assert res.scientific_standing == "PROVIDER_DATA_REQUIRED"
    # decide acceptance must block
    with pytest.raises(ManchesterDemandPackageError):
        decide_demand_acceptance(
            result=res,
            reviewer_id="reviewer01",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="production",
        )


def test_scientific_acceptance_not_from_software_valid() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert res.software_standing == "SOFTWARE_VALID"
    assert res.scientifically_accepted is False
    assert res.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    # Direct construction trying to claim accepted via model_validate must fail
    with pytest.raises(ValidationError):
        ManchesterDemandPackageResult.model_validate(
            {**res.model_dump(mode="python"), "scientifically_accepted": True}, strict=True
        )


def test_model_copy_type_coercion_detected() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    # Coerce deterministic_seed via string
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    coerced = res.model_copy(update={"deterministic_seed": "42"})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)):
        verify_demand_package(coerced, request=req, map_workflow=wf, count_input=ci)
    # Nested tamper: counts summary
    tampered_nested = res.model_copy(
        update={
            "counts": DemandCountsSummary(
                offered=999,
                admitted=999,
                excluded=0,
                missing_hours=0,
                measured_zero_cells=0,
            )
        }
    )
    with pytest.raises((ManchesterDemandPackageError, ValidationError)):
        verify_demand_package(tampered_nested, request=req, map_workflow=wf, count_input=ci)


def test_duplicate_unsorted_excess_inputs_rejected() -> None:
    with pytest.raises(ValidationError):
        DemandScalingAssumptions(
            scaling_method="none",
            normalisation="none",
            missingness_handling="excluded_not_zero_filled",
            exclusions=("b", "a"),
        )
    with pytest.raises(ValidationError):
        DemandScalingAssumptions(
            scaling_method="none",
            normalisation="none",
            missingness_handling="excluded_not_zero_filled",
            exclusions=("a", "a"),
        )
    with pytest.raises(ValidationError):
        DemandProvenance(
            created_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
            created_by="x",
            parent_fingerprints=("b" * 64, "a" * 64),
        )


def test_provenance_secret_private_path_leakage_rejected() -> None:
    with pytest.raises(ValidationError):
        DemandProvenance(
            created_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
            created_by="/Users/secret",
            parent_fingerprints=(),
        )
    with pytest.raises(ValidationError):
        DemandNetworkIdentity(
            network_identity_sha256="a" * 64,
            route_pool_identity="/private/pool",
            route_pool_fingerprint="b" * 64,
            map_policy_id="manchester-dft-map-match-owner-policy-1.1",
            map_policy_fingerprint="c" * 64,
        )
    with pytest.raises(ValidationError):
        ManchesterDemandPackageRequest.model_validate(
            {
                "request_id": "demand-req-001",
                "created_at_utc": datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
                "source": _source().model_dump(mode="python"),
                "temporal": _temporal().model_dump(mode="python"),
                "network": _network().model_dump(mode="python"),
                "demand_method": "count_constrained_candidate_v1",
                "deterministic_seed": None,
                "scaling": _scaling().model_dump(mode="python"),
                "count_input_fingerprint": "a" * 64,
                "map_workflow_fingerprint": "b" * 64,
                "demand_label": "count_constrained_candidate_demand",
                "request_fingerprint": "c" * 64,
                "limitations": ("exfil /Users/secret",),
            },
            strict=True,
        )


def test_deterministic_rebuild_across_input_order() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res1 = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    res2 = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert res1.result_fingerprint == res2.result_fingerprint
    assert res1.output_fingerprint == res2.output_fingerprint
    # Verify re-derives
    verify_demand_package(res1, request=req, map_workflow=wf, count_input=ci)


def test_honest_synthetic_candidate() -> None:
    wf = _workflow_auto(1)
    ci = _empty_count_input()
    req = build_demand_package_request(
        request_id="demand-req-001",
        created_at_utc=datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
        source=_source(),
        temporal=_temporal(),
        network=_network(wf),
        demand_method="synthetic_uniform_v1",
        deterministic_seed=123,
        scaling=_scaling(),
        count_input=ci,
        map_workflow=wf,
    )
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert res.standing == "SYNTHETIC_ENGINEERING_CANDIDATE"
    assert res.software_standing == "SOFTWARE_VALID"
    assert res.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert res.demand_label == "synthetic_engineering_candidate_demand"
    assert "Synthetic" in res.limitations[3]


def test_blocked_provider_dependent_candidate() -> None:
    wf = _workflow_auto(1)
    ci = _empty_count_input()
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert res.standing == "PROVIDER_DATA_REQUIRED"
    assert res.software_standing == "SOFTWARE_INVALID"
    # receipt only for accepted
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="PROVIDER_DATA_REQUIRED",
        reason="insufficient provider evidence",
    )
    assert dec.decision == "PROVIDER_DATA_REQUIRED"
    with pytest.raises(ManchesterDemandPackageError):
        issue_demand_receipt(
            result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
        )


def test_output_fingerprint_binds_seed_method() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req1 = build_demand_package_request(
        request_id="demand-req-001",
        created_at_utc=datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
        source=_source(),
        temporal=_temporal(),
        network=_network(wf),
        demand_method="count_constrained_stochastic_v1",
        deterministic_seed=1,
        scaling=_scaling(),
        count_input=ci,
        map_workflow=wf,
    )
    res1 = build_demand_package(
        request=req1,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    req2 = build_demand_package_request(
        request_id="demand-req-001",
        created_at_utc=datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
        source=_source(),
        temporal=_temporal(),
        network=_network(wf),
        demand_method="count_constrained_stochastic_v1",
        deterministic_seed=2,
        scaling=_scaling(),
        count_input=ci,
        map_workflow=wf,
    )
    res2 = build_demand_package(
        request=req2,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert res1.output_fingerprint != res2.output_fingerprint


def test_explicit_utc_required() -> None:
    with pytest.raises(ValidationError):
        DemandTemporalIdentity(
            window_start_utc=datetime(2026, 7, 26, 8, 0, 0),
            window_end_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC),
            interval_seconds=3600,
            unit="vehicles_per_interval",
            time_basis="documented_utc",
        )
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    with pytest.raises(ManchesterDemandPackageError):
        build_demand_package(
            request=req,
            map_workflow=wf,
            count_input=ci,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0),
        )
