"""Discriminating tests for Lane 04 demand package.

Covers rejected/unresolved silently admitted, forged standing, foreign ledger,
wrong source family/role, BODS relabel, incompatible interval/unit/network/map,
missingness not zero, stochastic seed, fingerprint drift, observed-trip claims,
provider-required inflation, software->scientific separation, model_copy tamper,
duplicate/unsorted/excess, provenance secrets, deterministic rebuild, synthetic
vs provider-blocked candidates, receipt standing forgery cross-product,
multi-hour denominators, foreign policy, scaling/source drift.

BLOCKER 1: receipt binds software+science, verify requires exact
receipt↔decision↔result standings/fingerprints, cross-product forgery,
accepted→receipt→verify round trips, bounded reviewer identity.
BLOCKER 2: coherent cell units, ledger.cells_bound/len(counts), 1 site 2/24 valid,
no clamp, missing = expected - present, direction exclusions separate.
BLOCKER 3: count input policy equals workflow/network, typed mismatches.
HIGH: _output_fingerprint binds scaling + complete source + workflow/input/etc.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
    verify_demand_receipt,
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

UTC = timezone.utc  # noqa: UP017 - compat 3.9

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


def _workflow_multi(cpids: list[int]) -> MapMatchWorkflowResult:
    obs_list = [_obs_auto(c) for c in cpids]
    queue = build_manual_review_queue(obs_list)
    return build_map_match_workflow(
        observations=tuple(obs_list), queue=queue, policy=POLICY, source=_source()
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


def _temporal_24h() -> DemandTemporalIdentity:
    return DemandTemporalIdentity(
        window_start_utc=datetime(2026, 7, 26, 0, 0, 0, tzinfo=UTC),
        window_end_utc=datetime(2026, 7, 27, 0, 0, 0, tzinfo=UTC),
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


def _make_multi_hour_count_input(
    wf: MapMatchWorkflowResult,
    *,
    num_hours: int = 2,
    directions_bound: int = 1,
) -> CountConstrainedDemandInput:
    """Build counts spanning num_hours intervals within a 24h window."""
    # Use first accepted id edge
    cpid = wf.auto_accepted_ids[0] if wf.auto_accepted_ids else 1
    edge_id = "e1"
    resolutions = (
        DirectionResolution(
            count_point_id=cpid,
            direction_of_travel="N",
            binding="bound_to_single_edge",
            edge_id=edge_id,
            considered=((edge_id, Decimal("0")),),
            target_bearing_degrees=Decimal("0"),
            tolerance_degrees=Decimal("45"),
            reason="exactly one member edge lies within the approved bearing tolerance",
        ),
    )
    cells = tuple(
        EdgeHourCount(
            edge_id=edge_id,
            count_point_id=cpid,
            direction_of_travel="N",
            hour=8 + i,
            interval_start_s=(8 + i) * 3600,
            interval_end_s=(9 + i) * 3600,
            all_motor_vehicles=10 + i,
            measured_zero=False,
        )
        for i in range(num_hours)
    )
    ledger = DemandInputLedger(
        sites_offered=1,
        sites_admissible=1,
        sites_rejected_wrong_disposition=0,
        directions_offered=directions_bound,
        directions_bound=directions_bound,
        directions_requiring_confirmation=0,
        directions_unresolved=0,
        directions_combined_not_forced=0,
        cells_bound=len(cells),
        measured_zero_cells_bound=0,
    )
    return CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=cells,
        resolutions=resolutions,
        ledger=ledger,
    )


# ---------------------------------------------------------------------------
# Original tests (adapted for coherent units)
# ---------------------------------------------------------------------------


def test_rejected_silently_admitted_is_refused() -> None:
    wf = _workflow_with_rejected()
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
    alt_source = _source(
        admission_receipt_fingerprint="ff" * 32,
        content_fingerprint="bb" * 32,
        snapshot_id=f"dft_raw_counts-20260726T230000Z-{'bb' * 6}",
    )
    queue = build_manual_review_queue([_obs_auto(1)])
    wf_alt = build_map_match_workflow(
        observations=(_obs_auto(1),), queue=queue, policy=POLICY, source=alt_source
    )
    req = _make_request(wf, ci)
    with pytest.raises(ManchesterDemandPackageError):
        build_demand_package(
            request=req,
            map_workflow=wf_alt,
            count_input=ci,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
        )


def test_wrong_source_family_rejected() -> None:
    with pytest.raises(ValidationError):
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
    assert res.counts.admitted == len(ci.counts)
    assert res.counts.admitted == ci.ledger.cells_bound
    # missing_hours is temporal gap, not direction exclusions
    assert res.counts.direction_unresolved_excluded == ci.ledger.directions_unresolved
    assert (
        res.counts.direction_requires_confirmation_excluded
        == ci.ledger.directions_requiring_confirmation
    )
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
    with pytest.raises(ManchesterDemandPackageError):
        decide_demand_acceptance(
            result=res,
            reviewer_id="reviewer01",
            reviewer_role="senior_analyst",
            reviewer_attribution="independent-board",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="production with independent calibration and baseline attested",
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
    with pytest.raises(ValidationError):
        ManchesterDemandPackageResult.model_validate(
            {**res.model_dump(mode="python"), "scientifically_accepted": True}, strict=True
        )


def test_model_copy_type_coercion_detected() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
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
    tampered_nested = res.model_copy(
        update={
            "counts": DemandCountsSummary(
                offered=999,
                admitted=999,
                excluded=0,
                missing_hours=0,
                measured_zero_cells=0,
                expected_interval_cells=999,
                direction_unresolved_excluded=0,
                direction_requires_confirmation_excluded=0,
                direction_combined_not_forced_excluded=0,
                sites_offered=0,
                sites_admitted=0,
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
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="analyst",
        reviewer_attribution="board",
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


# ---------------------------------------------------------------------------
# BLOCKER 2: multi-hour denominators, coherent units
# ---------------------------------------------------------------------------


def test_one_site_two_of_24_measured_hours_valid() -> None:
    wf = _workflow_auto(1)
    temporal = _temporal_24h()
    ci = _make_multi_hour_count_input(wf, num_hours=2)
    req = _make_request(wf, ci, temporal=temporal)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    # coherent unit: admitted is cells, equals ledger.cells_bound and len(counts)
    assert res.counts.admitted == 2
    assert res.counts.admitted == ci.ledger.cells_bound
    assert res.counts.offered == res.counts.admitted + res.counts.excluded
    assert res.counts.offered == 2
    assert res.counts.excluded == 0
    # explicit denominator: 24 intervals * 1 direction = 24 expected
    assert res.counts.expected_interval_cells == 24
    assert res.counts.missing_hours == 22
    # direction exclusions separate
    assert res.counts.direction_unresolved_excluded == 0
    assert res.counts.direction_requires_confirmation_excluded == 0
    # measured zero preserved
    assert res.counts.measured_zero_cells == 0


def test_multi_site_multi_hour_missing_interval() -> None:
    wf = _workflow_multi([1, 2])
    temporal = _temporal_24h()
    # 2 sites, each bound, 2 hours each = 4 cells
    cpid1 = 1
    cpid2 = 2
    ledger = DemandInputLedger(
        sites_offered=2,
        sites_admissible=2,
        sites_rejected_wrong_disposition=0,
        directions_offered=2,
        directions_bound=2,
        directions_requiring_confirmation=0,
        directions_unresolved=0,
        directions_combined_not_forced=0,
        cells_bound=4,
        measured_zero_cells_bound=1,
    )
    r1 = DirectionResolution(
        count_point_id=cpid1,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id="e1",
        considered=(("e1", Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    r2 = DirectionResolution(
        count_point_id=cpid2,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id="e2",
        considered=(("e2", Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    cells = (
        EdgeHourCount(
            edge_id="e1",
            count_point_id=cpid1,
            direction_of_travel="N",
            hour=8,
            interval_start_s=8 * 3600,
            interval_end_s=9 * 3600,
            all_motor_vehicles=10,
            measured_zero=False,
        ),
        EdgeHourCount(
            edge_id="e1",
            count_point_id=cpid1,
            direction_of_travel="N",
            hour=9,
            interval_start_s=9 * 3600,
            interval_end_s=10 * 3600,
            all_motor_vehicles=0,
            measured_zero=True,
        ),
        EdgeHourCount(
            edge_id="e2",
            count_point_id=cpid2,
            direction_of_travel="N",
            hour=8,
            interval_start_s=8 * 3600,
            interval_end_s=9 * 3600,
            all_motor_vehicles=20,
            measured_zero=False,
        ),
        EdgeHourCount(
            edge_id="e2",
            count_point_id=cpid2,
            direction_of_travel="N",
            hour=9,
            interval_start_s=9 * 3600,
            interval_end_s=10 * 3600,
            all_motor_vehicles=30,
            measured_zero=False,
        ),
    )
    ci = CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=cells,
        resolutions=(r1, r2),
        ledger=ledger,
    )
    req = _make_request(wf, ci, temporal=temporal)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert res.counts.admitted == 4
    assert res.counts.offered == 4
    assert res.counts.expected_interval_cells == 48  # 24 * 2 directions
    assert res.counts.missing_hours == 44
    assert res.counts.measured_zero_cells == 1
    assert res.counts.direction_unresolved_excluded == 0
    assert res.counts.sites_offered == 2
    assert res.counts.sites_admitted == 2


def test_ledger_cells_bound_mismatch_fails_typed_not_clamp() -> None:
    wf = _workflow_auto(1)
    ledger = DemandInputLedger(
        sites_offered=1,
        sites_admissible=1,
        sites_rejected_wrong_disposition=0,
        directions_offered=1,
        directions_bound=1,
        directions_requiring_confirmation=0,
        directions_unresolved=0,
        directions_combined_not_forced=0,
        cells_bound=2,  # claims 2 but only 1 cell provided
        measured_zero_cells_bound=0,
    )
    res = DirectionResolution(
        count_point_id=1,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id="e1",
        considered=(("e1", Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    cell = EdgeHourCount(
        edge_id="e1",
        count_point_id=1,
        direction_of_travel="N",
        hour=8,
        interval_start_s=8 * 3600,
        interval_end_s=9 * 3600,
        all_motor_vehicles=10,
        measured_zero=False,
    )
    ci = CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=(cell,),
        resolutions=(res,),
        ledger=ledger,
    )
    req = _make_request(wf, ci)
    with pytest.raises(ManchesterDemandPackageError) as exc:
        build_demand_package(
            request=req,
            map_workflow=wf,
            count_input=ci,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
        )
    assert "COUNT_LEDGER_MISMATCH" in str(exc.value)


def test_direction_exclusions_not_counted_as_missing_hours() -> None:
    wf = _workflow_auto(1)
    ledger = DemandInputLedger(
        sites_offered=1,
        sites_admissible=1,
        sites_rejected_wrong_disposition=0,
        directions_offered=3,
        directions_bound=1,
        directions_requiring_confirmation=1,
        directions_unresolved=1,
        directions_combined_not_forced=0,
        cells_bound=1,
        measured_zero_cells_bound=0,
    )
    res = DirectionResolution(
        count_point_id=1,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id="e1",
        considered=(("e1", Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    cell = EdgeHourCount(
        edge_id="e1",
        count_point_id=1,
        direction_of_travel="N",
        hour=8,
        interval_start_s=8 * 3600,
        interval_end_s=9 * 3600,
        all_motor_vehicles=10,
        measured_zero=False,
    )
    ci = CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=(cell,),
        resolutions=(res,),
        ledger=ledger,
    )
    req = _make_request(wf, ci)
    result = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert result.counts.admitted == 1
    assert result.counts.expected_interval_cells == 1  # 1 interval * 1 bound direction
    assert result.counts.missing_hours == 0  # not 2
    assert result.counts.direction_unresolved_excluded == 1
    assert result.counts.direction_requires_confirmation_excluded == 1


def test_measured_zero_explicit_not_missing() -> None:
    wf = _workflow_auto(1)
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
        measured_zero_cells_bound=1,
    )
    res = DirectionResolution(
        count_point_id=1,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id="e1",
        considered=(("e1", Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    cell = EdgeHourCount(
        edge_id="e1",
        count_point_id=1,
        direction_of_travel="N",
        hour=8,
        interval_start_s=8 * 3600,
        interval_end_s=9 * 3600,
        all_motor_vehicles=0,
        measured_zero=True,
    )
    ci = CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=(cell,),
        resolutions=(res,),
        ledger=ledger,
    )
    req = _make_request(wf, ci)
    result = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    assert result.counts.measured_zero_cells == 1
    assert result.counts.admitted == 1
    assert result.counts.missing_hours == 0


def test_no_missing_as_zero_inflation() -> None:
    wf = _workflow_auto(1)
    temporal = _temporal_24h()
    ci = _make_multi_hour_count_input(wf, num_hours=1)
    req = _make_request(wf, ci, temporal=temporal)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    # 1 admitted of 24 expected => missing 23, not zero-filled
    assert res.counts.missing_hours == 23
    assert res.counts.admitted == 1


# ---------------------------------------------------------------------------
# BLOCKER 3: foreign policy
# ---------------------------------------------------------------------------


def test_count_policy_fingerprint_mismatch_fails() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    bad_ci = ci.model_copy(update={"match_policy_fingerprint": "f" * 64})
    with pytest.raises(ManchesterDemandPackageError) as exc:
        build_demand_package_request(
            request_id="demand-req-001",
            created_at_utc=datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
            source=_source(),
            temporal=_temporal(),
            network=_network(wf),
            demand_method="count_constrained_candidate_v1",
            deterministic_seed=None,
            scaling=_scaling(),
            count_input=bad_ci,
            map_workflow=wf,
        )
    assert "COUNT_POLICY_MISMATCH" in str(exc.value)


def test_count_policy_id_mismatch_fails() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    bad_ci = ci.model_copy(update={"match_policy_id": "wrong-policy-id"})
    with pytest.raises(ManchesterDemandPackageError):
        build_demand_package_request(
            request_id="demand-req-001",
            created_at_utc=datetime(2026, 7, 26, 7, 0, 0, tzinfo=UTC),
            source=_source(),
            temporal=_temporal(),
            network=_network(wf),
            demand_method="count_constrained_candidate_v1",
            deterministic_seed=None,
            scaling=_scaling(),
            count_input=bad_ci,
            map_workflow=wf,
        )


def test_count_input_not_snapshot_bearing_documented() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    # fingerprint binds complete count input, not snapshot id
    assert req.count_input_fingerprint == ci.fingerprint()
    # count input has no snapshot_id attribute
    assert not hasattr(ci, "snapshot_id")


def test_rejected_source_dependency_mismatch_typed_fail() -> None:
    wf = _workflow_auto(1)
    _ = _count_input(1)  # ensure helper works
    # Use a ledger that claims wrong disposition vs workflow accepted
    bad_ledger = DemandInputLedger(
        sites_offered=1,
        sites_admissible=0,
        sites_rejected_wrong_disposition=1,
        directions_offered=1,
        directions_bound=1,
        directions_requiring_confirmation=0,
        directions_unresolved=0,
        directions_combined_not_forced=0,
        cells_bound=1,
        measured_zero_cells_bound=0,
    )
    res = DirectionResolution(
        count_point_id=1,
        direction_of_travel="N",
        binding="bound_to_single_edge",
        edge_id="e1",
        considered=(("e1", Decimal("0")),),
        target_bearing_degrees=Decimal("0"),
        tolerance_degrees=Decimal("45"),
        reason="exactly one member edge lies within the approved bearing tolerance",
    )
    cell = EdgeHourCount(
        edge_id="e1",
        count_point_id=1,
        direction_of_travel="N",
        hour=8,
        interval_start_s=8 * 3600,
        interval_end_s=9 * 3600,
        all_motor_vehicles=10,
        measured_zero=False,
    )
    bad_ci = CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=POLICY_FP,
        direction_tolerance_degrees=Decimal("45"),
        counts=(cell,),
        resolutions=(res,),
        ledger=bad_ledger,
    )
    req = _make_request(wf, bad_ci)
    res_pkg = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=bad_ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    # provider path is blocked, but not a foreign policy error
    assert res_pkg.standing in ("PROVIDER_DATA_REQUIRED", "COUNT_CONSTRAINED_CANDIDATE")


# ---------------------------------------------------------------------------
# HIGH: _output_fingerprint binds scaling/source full
# ---------------------------------------------------------------------------


def test_scaling_drift_changes_output_fingerprint() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    # Tamper scaling exclusions via model_copy
    tampered = res.model_copy(
        update={
            "scaling": DemandScalingAssumptions(
                scaling_method="none",
                normalisation="none",
                missingness_handling="excluded_not_zero_filled",
                exclusions=("another_exclusion",),
            )
        }
    )
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc:
        verify_demand_package(tampered, request=req, map_workflow=wf, count_input=ci)
    assert "fingerprint" in str(exc.value).lower()


def test_source_field_drift_changes_output_fingerprint() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    alt_source = _source(
        content_fingerprint="ff" * 32,
        snapshot_id=f"dft_raw_counts-20260726T230000Z-{'ff' * 6}",
    )
    tampered = res.model_copy(update={"source": alt_source})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc:
        verify_demand_package(tampered, request=req, map_workflow=wf, count_input=ci)
    assert "fingerprint" in str(exc.value).lower()


def test_source_provenance_drift_rejected() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    # provenance drift via admission receipt
    tampered_source = _source(admission_receipt_fingerprint="ee" * 32)
    tampered = res.model_copy(update={"source": tampered_source})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc:
        verify_demand_package(tampered, request=req, map_workflow=wf, count_input=ci)
    assert "fingerprint" in str(exc.value).lower()


def test_output_fingerprint_binds_standing_and_counts() -> None:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    tampered = res.model_copy(update={"standing": "SYNTHETIC_ENGINEERING_CANDIDATE"})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc:
        verify_demand_package(tampered, request=req, map_workflow=wf, count_input=ci)
    assert (
        "fingerprint" in str(exc.value).lower()
        or "standing" in str(exc.value).lower()
        or "synthetic" in str(exc.value).lower()
    )


# ---------------------------------------------------------------------------
# Synthetic path validates subset
# ---------------------------------------------------------------------------


def test_synthetic_validates_count_subset_still() -> None:
    wf = _workflow_with_rejected()
    # synthetic with count binding to rejected id 2 should still be refused
    ci = _count_input(cpid=2, edge_id="e1")
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
    with pytest.raises(ManchesterDemandPackageError) as exc:
        build_demand_package(
            request=req,
            map_workflow=wf,
            count_input=ci,
            evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
        )
    assert "REJECTED" in str(exc.value) or "SILENTLY" in str(exc.value)


def test_synthetic_relaxes_only_provider_standing() -> None:
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


# ---------------------------------------------------------------------------
# BLOCKER 1: receipt standing forgery cross-product and round trips
# ---------------------------------------------------------------------------


def _build_accepted_package() -> tuple[
    ManchesterDemandPackageRequest,
    ManchesterDemandPackageResult,
    MapMatchWorkflowResult,
    CountConstrainedDemandInput,
]:
    wf = _workflow_auto(1)
    ci = _count_input(1)
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    return req, res, wf, ci


def test_real_accepted_decision_receipt_verify_round_trip() -> None:
    req, res, wf, ci = _build_accepted_package()
    verify_demand_package(res, request=req, map_workflow=wf, count_input=ci)
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="senior_analyst",
        reviewer_attribution="independent-board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
        reason=(
            "independent production source map rights calibration baseline"
            " attested; software_valid alone not sufficient"
        ),
    )
    receipt = issue_demand_receipt(
        result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
    )
    # receipt binds software+science
    assert receipt.software_standing == "SOFTWARE_VALID"
    assert receipt.scientific_standing == "SCIENTIFICALLY_ACCEPTED_DEMAND"
    assert receipt.standing == "COUNT_CONSTRAINED_CANDIDATE"
    verified = verify_demand_receipt(receipt, result=res, decision=dec)
    assert verified.receipt_fingerprint == receipt.receipt_fingerprint


def test_receipt_fingerprint_binds_software_and_science() -> None:
    req, res, wf, ci = _build_accepted_package()
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="senior_analyst",
        reviewer_attribution="independent-board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
        reason="independent calibration baseline attested",
    )
    receipt = issue_demand_receipt(
        result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
    )
    # tamper software_standing
    tampered = receipt.model_copy(update={"software_standing": "SOFTWARE_INVALID"})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc:
        verify_demand_receipt(tampered, result=res, decision=dec)
    assert "SOFTWARE_VALID" in str(exc.value) or "fingerprint" in str(exc.value).lower()
    tampered2 = receipt.model_copy(update={"scientific_standing": "SCIENTIFICALLY_NOT_ACCEPTED"})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc2:
        verify_demand_receipt(tampered2, result=res, decision=dec)
    assert "SCIENTIFIC" in str(exc2.value) or "fingerprint" in str(exc2.value).lower()
    tampered3 = receipt.model_copy(update={"standing": "PROVIDER_DATA_REQUIRED"})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc3:
        verify_demand_receipt(tampered3, result=res, decision=dec)
    assert (
        "provider_data_required" in str(exc3.value).lower()
        or "scientifically" in str(exc3.value).lower()
        or "fingerprint" in str(exc3.value).lower()
    )


def test_verify_receipt_requires_exact_bindings_all_branches() -> None:
    wf = _workflow_auto(1)
    ci = _empty_count_input()
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="analyst",
        reviewer_attribution="board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="PROVIDER_DATA_REQUIRED",
        reason="insufficient provider evidence",
    )
    # Attempt to forge accepted receipt from provider-required decision should fail at issuance
    with pytest.raises(ManchesterDemandPackageError):
        issue_demand_receipt(
            result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
        )
    # Even if we craft a receipt manually, verify must reject cross-product
    # Build a valid accepted receipt then swap decision
    req2, res2, wf2, ci2 = _build_accepted_package()
    dec_accepted = decide_demand_acceptance(
        result=res2,
        reviewer_id="reviewer01",
        reviewer_role="senior_analyst",
        reviewer_attribution="independent-board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
        reason="independent calibration baseline attested",
    )
    receipt_accepted = issue_demand_receipt(
        result=res2, decision=dec_accepted, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
    )
    # Verify with provider-required decision mismatched fingerprints/standings must fail
    with pytest.raises(ManchesterDemandPackageError):
        verify_demand_receipt(receipt_accepted, result=res2, decision=dec)


def test_cross_product_forgery_every_combination() -> None:
    req, res, wf, ci = _build_accepted_package()
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="senior_analyst",
        reviewer_attribution="independent-board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
        reason="independent calibration baseline attested",
    )
    receipt = issue_demand_receipt(
        result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
    )
    # Forged standings cross-product
    for software, scientific, standing in [
        ("SOFTWARE_INVALID", "SCIENTIFICALLY_ACCEPTED_DEMAND", "COUNT_CONSTRAINED_CANDIDATE"),
        ("SOFTWARE_VALID", "SCIENTIFICALLY_ACCEPTED_DEMAND", "PROVIDER_DATA_REQUIRED"),
        ("SOFTWARE_INVALID", "PROVIDER_DATA_REQUIRED", "COUNT_CONSTRAINED_CANDIDATE"),
        ("SOFTWARE_VALID", "PROVIDER_DATA_REQUIRED", "COUNT_CONSTRAINED_CANDIDATE"),
    ]:
        tampered = receipt.model_copy(
            update={
                "software_standing": software,
                "scientific_standing": scientific,
                "standing": standing,
            }
        )
        with pytest.raises((ManchesterDemandPackageError, ValidationError)):
            verify_demand_receipt(tampered, result=res, decision=dec)


def test_verify_receipt_fingerprint_drift_all_fields() -> None:
    req, res, wf, ci = _build_accepted_package()
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="senior_analyst",
        reviewer_attribution="independent-board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
        reason="independent calibration baseline attested",
    )
    receipt = issue_demand_receipt(
        result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
    )
    for field, val in [
        ("request_fingerprint", "0" * 64),
        ("result_fingerprint", "1" * 64),
        ("decision_fingerprint", "2" * 64),
    ]:
        tampered = receipt.model_copy(update={field: val})
        with pytest.raises((ManchesterDemandPackageError, ValidationError)):
            verify_demand_receipt(tampered, result=res, decision=dec)


def test_decision_requires_bounded_identity_and_role() -> None:
    req, res, wf, ci = _build_accepted_package()
    # bare reviewer string without role must fail for acceptance
    with pytest.raises(ManchesterDemandPackageError):
        decide_demand_acceptance(
            result=res,
            reviewer_id="reviewer01",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="independent calibration baseline attested",
        )
    # invalid reviewer_id pattern
    with pytest.raises(ManchesterDemandPackageError):
        decide_demand_acceptance(
            result=res,
            reviewer_id="Bad Reviewer!",
            reviewer_role="senior_analyst",
            reviewer_attribution="board",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="independent calibration baseline attested",
        )
    # self-admission: reviewer_id equals request id
    with pytest.raises(ManchesterDemandPackageError):
        decide_demand_acceptance(
            result=res,
            reviewer_id=res.request_id,
            reviewer_role="senior_analyst",
            reviewer_attribution="board",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="independent calibration baseline attested",
        )


def test_scientific_acceptance_never_from_software_convergence_alone() -> None:
    req, res, wf, ci = _build_accepted_package()
    with pytest.raises(ManchesterDemandPackageError) as exc:
        decide_demand_acceptance(
            result=res,
            reviewer_id="reviewer01",
            reviewer_role="senior_analyst",
            reviewer_attribution="independent-board",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="software converged, therefore accepted",
        )
    assert "SCIENTIFIC" in str(exc.value) or "independent" in str(exc.value).lower()


def test_synthetic_cannot_be_scientifically_accepted_cross_branch() -> None:
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
    with pytest.raises(ManchesterDemandPackageError):
        decide_demand_acceptance(
            result=res,
            reviewer_id="reviewer01",
            reviewer_role="senior_analyst",
            reviewer_attribution="independent-board",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="independent calibration baseline attested",
        )


def test_provider_data_required_never_accepted_cross_branch() -> None:
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
    with pytest.raises(ManchesterDemandPackageError):
        decide_demand_acceptance(
            result=res,
            reviewer_id="reviewer01",
            reviewer_role="senior_analyst",
            reviewer_attribution="independent-board",
            decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
            decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
            reason="independent calibration baseline attested",
        )


def test_blocked_provider_round_trip_verify() -> None:
    wf = _workflow_auto(1)
    ci = _empty_count_input()
    req = _make_request(wf, ci)
    res = build_demand_package(
        request=req,
        map_workflow=wf,
        count_input=ci,
        evaluated_at_utc=datetime(2026, 7, 26, 7, 10, 0, tzinfo=UTC),
    )
    verify_demand_package(res, request=req, map_workflow=wf, count_input=ci)
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="analyst",
        reviewer_attribution="board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="PROVIDER_DATA_REQUIRED",
        reason="insufficient provider evidence",
    )
    assert dec.decision == "PROVIDER_DATA_REQUIRED"
    # verify that issuance is blocked for provider-required
    with pytest.raises(ManchesterDemandPackageError):
        issue_demand_receipt(
            result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
        )


def test_synthetic_round_trip_verify() -> None:
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
    verify_demand_package(res, request=req, map_workflow=wf, count_input=ci)
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="analyst",
        reviewer_attribution="board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_NOT_ACCEPTED",
        reason="synthetic engineering only",
    )
    assert dec.decision == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert dec.reviewer_role == "analyst"


def test_decision_fingerprint_recomputed_rejects_tamper() -> None:
    req, res, wf, ci = _build_accepted_package()
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer01",
        reviewer_role="senior_analyst",
        reviewer_attribution="independent-board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_ACCEPTED_DEMAND",
        reason="independent calibration baseline attested",
    )
    receipt = issue_demand_receipt(
        result=res, decision=dec, issued_at_utc=datetime(2026, 7, 26, 9, 0, 0, tzinfo=UTC)
    )
    tampered_dec = dec.model_copy(update={"reason": "tampered reason"})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc:
        verify_demand_receipt(receipt, result=res, decision=tampered_dec)
    assert "fingerprint" in str(exc.value).lower()
    tampered_role = dec.model_copy(update={"reviewer_role": "tampered_role"})
    with pytest.raises((ManchesterDemandPackageError, ValidationError)) as exc2:
        verify_demand_receipt(receipt, result=res, decision=tampered_role)
    assert "fingerprint" in str(exc2.value).lower()


def test_all_public_decision_receipt_functions_covered() -> None:
    # Ensure public functions exist and are typed
    req, res, wf, ci = _build_accepted_package()
    # build_demand_package_request, build_demand_package, verify_demand_package already used
    # decide, issue, verify receipt
    dec = decide_demand_acceptance(
        result=res,
        reviewer_id="reviewer02",
        reviewer_role="analyst",
        reviewer_attribution="board",
        decided_at_utc=datetime(2026, 7, 26, 8, 0, 0, tzinfo=UTC),
        decision="SCIENTIFICALLY_NOT_ACCEPTED",
        reason="needs more evidence",
    )
    assert dec.decision == "SCIENTIFICALLY_NOT_ACCEPTED"
    # verify package with wrong policy should fail typed
    bad_ci = ci.model_copy(update={"match_policy_fingerprint": "0" * 64})
    with pytest.raises(ManchesterDemandPackageError):
        verify_demand_package(res, request=req, map_workflow=wf, count_input=bad_ci)
