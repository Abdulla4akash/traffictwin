#!/usr/bin/env python3
# ruff: noqa: ANN401,ANN001,ANN201,S603,S607,E501,N806,N814,S110,S112,TRY003,B904,S108,PLR0915,ANN202,DTZ005,S206,PLR0912,PLR0913,PERF203,C901
"""Strict executable expansion validator — Lane 16.

Dependency-gated, deterministic, non-networked checks over the integrated
Manchester/SUMO, Research Registry, Replay Observatory and Manchester Source
Operations release (lanes 01-14).

Fails closed under real discriminating mutations via legitimate public
construction paths (typed Pydantic validators/services), not name scans.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

_SYS_ROOT: Path = Path(__file__).resolve().parents[1]
_SRC: Path = _SYS_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

SCHEMA_VERSION: str = "1.0"
METHOD_VERSION: str = "traffictwin-expansion-v1-validator-1.0"
EXPANSION_METHOD: str = "expansion-v1"

_PRIVATE_PATH_RE = re.compile(
    r"(/Users/|/home/|/tmp/|/var/folders/|/private/|/var/|/etc/|~/|[A-Za-z]:\\)"
)
_SECRET_VALUE_RE = re.compile(
    r"(?:api[_-]?key\s*[:=]|password\s*[:=]|secret\s*[:=]|bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contains_private_path(s: str) -> bool:
    return bool(_PRIVATE_PATH_RE.search(s))


def _expect_rejection(call: Callable[[], Any]) -> tuple[bool, str]:
    try:
        call()
    except Exception as exc:
        msg = str(exc)[:400]
        if _PRIVATE_PATH_RE.search(msg) or _SECRET_VALUE_RE.search(msg):
            msg = "rejected (sanitized)"
        return True, f"rejected as expected: {exc.__class__.__name__}: {msg}"
    return False, "unexpectedly accepted — fail-closed violation"


def _expect_success(call: Callable[[], Any]) -> tuple[bool, str]:
    try:
        result = call()
        return True, f"accepted as expected: {type(result).__name__}"
    except Exception as exc:
        return False, f"unexpected rejection: {exc.__class__.__name__}: {str(exc)[:600]}"


@dataclass(frozen=True)
class CheckResult:
    id: str
    title: str
    status: str
    detail: str
    mutation: str


# Helpers shared across checks
def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_01_sumo_injection() -> CheckResult:
    from traffictwin.integration.manchester.closed_loop_execution import (
        ClosedLoopExecutionRequest,
        ClosedLoopInputDeclaration,
    )

    def _valid() -> Any:
        fp = "a" * 64
        decl = ClosedLoopInputDeclaration(path="sumo.sumocfg", sha256="b" * 64, size_bytes=100)
        payload = {
            "package_fingerprint": fp,
            "config_file": "sumo.sumocfg",
            "inputs": [decl.model_dump(mode="json")],
            "seed": 1,
            "timeout_seconds": 60,
            "run_id": "valid-run-01",
            "confirmed_by_operator": True,
        }
        det = _sha256_hex(_canonical_json(payload).encode())
        return ClosedLoopExecutionRequest(
            run_id="valid-run-01",
            package_fingerprint=fp,
            config_file="sumo.sumocfg",
            inputs=[decl],
            seed=1,
            timeout_seconds=60,
            deterministic_run_identity=det,
            confirmed_by_operator=True,
        )

    ok, d_ok = _expect_success(_valid)
    if not ok:
        return CheckResult(
            "01",
            "SUMO injection — valid baseline must be accepted",
            "FAIL",
            d_ok,
            "valid construction should succeed",
        )

    def _private_path() -> Any:
        fp = "a" * 64
        decl = ClosedLoopInputDeclaration(path="sumo.sumocfg", sha256="b" * 64, size_bytes=100)
        payload = {
            "package_fingerprint": fp,
            "config_file": "/Users/evil/sumo.sumocfg",
            "inputs": [decl.model_dump(mode="json")],
            "seed": 1,
            "timeout_seconds": 60,
            "run_id": "valid-run-01",
            "confirmed_by_operator": True,
        }
        det = _sha256_hex(_canonical_json(payload).encode())
        return ClosedLoopExecutionRequest(
            run_id="valid-run-01",
            package_fingerprint=fp,
            config_file="/Users/evil/sumo.sumocfg",
            inputs=[decl],
            seed=1,
            timeout_seconds=60,
            deterministic_run_identity=det,
            confirmed_by_operator=True,
        )

    rejected, detail = _expect_rejection(_private_path)
    if not rejected:
        return CheckResult(
            "01",
            "SUMO injection — private path must be rejected",
            "FAIL",
            detail,
            "config_file='/Users/evil/sumo.sumocfg' via ClosedLoopExecutionRequest",
        )

    def _traversal() -> Any:
        decl = ClosedLoopInputDeclaration(path="../evil.xml", sha256="b" * 64, size_bytes=10)
        fp = "a" * 64
        payload = {
            "package_fingerprint": fp,
            "config_file": "../evil.xml",
            "inputs": [decl.model_dump(mode="json")],
            "seed": 0,
            "timeout_seconds": 60,
            "run_id": "traversal-test",
            "confirmed_by_operator": True,
        }
        det = _sha256_hex(_canonical_json(payload).encode())
        return ClosedLoopExecutionRequest(
            run_id="traversal-test",
            package_fingerprint=fp,
            config_file="../evil.xml",
            inputs=[decl],
            seed=0,
            timeout_seconds=60,
            deterministic_run_identity=det,
            confirmed_by_operator=True,
        )

    rejected2, detail2 = _expect_rejection(_traversal)
    if not rejected2:
        return CheckResult(
            "01",
            "SUMO injection — traversal must be rejected",
            "FAIL",
            detail2,
            "input path '../evil.xml' via ClosedLoopInputDeclaration/Request",
        )
    return CheckResult(
        "01",
        "SUMO executable/command injection is rejected via typed validators; valid synthetic remains accepted",
        "PASS",
        f"{d_ok} | {detail} | {detail2}",
        "private path + traversal via ClosedLoopExecutionRequest",
    )


def check_02_source_standing_inflation() -> CheckResult:
    from traffictwin.integration.manchester.snapshot_registry import SnapshotRegistration
    from traffictwin.integration.manchester.source_operations_models import (
        EvidenceStanding,
        SnapshotValidationState,
        SourceFamily,
        SourceFreshnessStanding,
    )

    def _valid_dft() -> Any:
        return SnapshotRegistration(
            registration_id="dft_test-001",
            snapshot_identity="dft_snapshot-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical surveyed counts at admitted DfT count points",
            record_count=10,
            parser_version="parser-1.0",
            schema_version="schema-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.HISTORICAL,
            storage_reference="opaque/dft/001",
            provenance_fingerprint="b" * 64,
            validation_receipt_fingerprint="c" * 64,
            validated_at_utc=datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC),
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )

    ok, d_ok = _expect_success(_valid_dft)
    if not ok:
        return CheckResult(
            "02",
            "source standing — valid DFT accepted must succeed",
            "FAIL",
            d_ok,
            "valid DFT registration should be accepted",
        )

    def _inflated() -> Any:
        return SnapshotRegistration(
            registration_id="tfgm_inflated-001",
            snapshot_identity="tfgm_snapshot-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.TFGM,
            coverage_summary="measured traffic volume on Manchester roads",
            record_count=5,
            parser_version="parser-1.0",
            schema_version="schema-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.HISTORICAL,
            storage_reference="opaque/tfgm/001",
            provenance_fingerprint="b" * 64,
            validation_receipt_fingerprint="c" * 64,
            validated_at_utc=datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC),
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )

    rejected, detail = _expect_rejection(_inflated)
    if not rejected:
        return CheckResult(
            "02",
            "source-standing inflation must be rejected",
            "FAIL",
            detail,
            "TFGM DESIGN_ONLY inflated to REAL MANCHESTER DATA via SnapshotRegistration",
        )

    def _inflated_nh() -> Any:
        return SnapshotRegistration(
            registration_id="nh_inflated-001",
            snapshot_identity="nh_snapshot-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            coverage_summary="Published closures on strategic network external to Manchester city-road",
            record_count=5,
            parser_version="parser-1.0",
            schema_version="schema-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            storage_reference="opaque/nh/001",
            provenance_fingerprint="d" * 64,
            validation_receipt_fingerprint="e" * 64,
            validated_at_utc=datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC),
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )

    rejected2, detail2 = _expect_rejection(_inflated_nh)
    if not rejected2:
        return CheckResult(
            "02",
            "source standing — strategic road inflation must be rejected",
            "FAIL",
            detail2,
            "NATIONAL_HIGHWAYS REAL EXTERNAL inflated to REAL MANCHESTER DATA",
        )
    return CheckResult(
        "02",
        "Source-standing inflation is rejected via frozen definition; valid historical remains accepted",
        "PASS",
        f"{d_ok} | {detail} | {detail2}",
        "TFGM/NH inflation via SnapshotRegistration",
    )


def check_03_bods_relabel() -> CheckResult:
    from traffictwin.integration.manchester.snapshot_registry import SnapshotRegistration
    from traffictwin.integration.manchester.source_operations_models import (
        EvidenceStanding,
        SnapshotValidationState,
        SourceFamily,
        SourceFreshnessStanding,
    )

    def _valid_bods() -> Any:
        return SnapshotRegistration(
            registration_id="bods_valid-001",
            snapshot_identity="bods_snapshot-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.BODS,
            coverage_summary="bus vehicle positions within Greater Manchester request scope (27 services)",
            record_count=100,
            parser_version="parser-1.0",
            schema_version="schema-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque/bods/001",
            provenance_fingerprint="f" * 64,
            validation_receipt_fingerprint="e" * 64,
            validated_at_utc=datetime(2026, 1, 2, 0, 1, 0, tzinfo=UTC),
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )

    ok, d_ok = _expect_success(_valid_bods)
    if not ok:
        return CheckResult(
            "03",
            "BODS valid bus coverage must be accepted",
            "FAIL",
            d_ok,
            "valid bus summary should be accepted",
        )

    def _relabelled() -> Any:
        return SnapshotRegistration(
            registration_id="bods_relabel-001",
            snapshot_identity="bods_snapshot-002",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.BODS,
            coverage_summary="general road traffic volume in Manchester (conflated)",
            record_count=100,
            parser_version="parser-1.0",
            schema_version="schema-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque/bods/002",
            provenance_fingerprint="f" * 64,
            validation_receipt_fingerprint="e" * 64,
            validated_at_utc=datetime(2026, 1, 2, 0, 1, 0, tzinfo=UTC),
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )

    rejected, detail = _expect_rejection(_relabelled)
    if not rejected:
        return CheckResult(
            "03",
            "BODS relabelled as general traffic must be rejected",
            "FAIL",
            detail,
            "BODS coverage_summary='general road traffic' via SnapshotRegistration",
        )

    def _relabelled2() -> Any:
        return SnapshotRegistration(
            registration_id="bods_relabel2-001",
            snapshot_identity="bods_snapshot-003",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.BODS,
            coverage_summary="traffic volume and congestion across Manchester city roads",
            record_count=50,
            parser_version="parser-1.0",
            schema_version="schema-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque/bods/003",
            provenance_fingerprint="f" * 64,
            validation_receipt_fingerprint="e" * 64,
            validated_at_utc=datetime(2026, 1, 2, 0, 1, 0, tzinfo=UTC),
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )

    rejected2, detail2 = _expect_rejection(_relabelled2)
    if not rejected2:
        return CheckResult(
            "03",
            "BODS congestion relabel must be rejected",
            "FAIL",
            detail2,
            "BODS coverage_summary='traffic volume and congestion'",
        )
    return CheckResult(
        "03",
        "BODS bus-only labeling enforced; relabel to general traffic rejected",
        "PASS",
        f"{d_ok} | {detail} | {detail2}",
        "bus-only check via SnapshotRegistration coverage_summary",
    )


def check_04_unresolved_map_match() -> CheckResult:
    from traffictwin.integration.manchester.map_match_workflow import (
        MapMatchDftSourceIdentity,
        build_map_match_workflow,
    )
    from traffictwin.integration.manchester.observation_matching import EdgeCandidate
    from traffictwin.integration.manchester.observation_matching_v11 import (
        ManchesterMapMatchPolicyV11,
        ObservationMatchV11,
        RoadGroupV11,
        build_manual_review_queue,
    )

    policy = ManchesterMapMatchPolicyV11()
    content_fp = "ab" * 32
    snap_id = f"dft_raw_counts-20260726T230000Z-{content_fp[:12]}"
    provenance = f"roadtraffic.dft.gov.uk:/api/raw-counts/pages/page-0001.json#{snap_id}"
    receipt_fp = "cd" * 32

    def _source() -> Any:
        return MapMatchDftSourceIdentity(
            source_family="dft",
            provider="roadtraffic.dft.gov.uk",
            observation_role="historical_measured_count",
            snapshot_id=snap_id,
            content_fingerprint=content_fp,
            provenance=provenance,
            admission_receipt_fingerprint=receipt_fp,
            is_accepted=True,
            is_source_blocked=False,
        )

    def _group() -> RoadGroupV11:
        cand = EdgeCandidate(
            edge_id="e1",
            road_type="highway.primary",
            road_class="primary",
            road_ref="A56",
            normalised_ref="A56",
            distance_m=Decimal("1.200"),
            geometry_source="explicit_edge_shape",
            bearing_degrees=Decimal("45.000"),
            requires_manual_confirmation=False,
        )
        return RoadGroupV11(
            group_key="ref:A56|primary",
            normalised_ref="A56",
            road_class_family="primary",
            members=(cand,),
            nearest_distance_m=Decimal("1.200"),
            contains_service_member=False,
            exact_reference_match=True,
            admitted_by_override=False,
            family_mismatch=None,
        )

    def _obs_unresolved() -> ObservationMatchV11:
        return ObservationMatchV11(
            policy_fingerprint=policy.fingerprint(),
            count_point_id=999,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_normalised_ref="A56",
            groups=(_group(),),
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
            reasons=(),
            review_reasons=("the nearest candidate is beyond the strict clear distance",),
        )

    obs = _obs_unresolved()
    queue = build_manual_review_queue([obs])

    def _honest() -> Any:
        wf = build_map_match_workflow(
            observations=[obs], queue=queue, policy=policy, source=_source()
        )
        assert wf.unresolved_ids == (999,)
        assert wf.observations[0].standing == "UNRESOLVED"
        return wf

    ok, d_ok = _expect_success(_honest)
    if not ok:
        return CheckResult(
            "04",
            "unresolved map match honest workflow must be UNRESOLVED",
            "FAIL",
            d_ok,
            "unresolved observation should yield UNRESOLVED not AUTO_ACCEPTED",
        )

    # Canonical honest projection via public workflow — the honest source for forgery.
    # Build once and reuse as the dumped canonical payload; do not reconstruct private
    # diagnostics via private helpers. This proves the semantic invariant, not a
    # diagnostics mismatch.
    honest_workflow = build_map_match_workflow(
        observations=[obs], queue=queue, policy=policy, source=_source()
    )
    honest_projection = honest_workflow.observations[0]
    assert honest_projection.standing == "UNRESOLVED"
    # Dump via public model_dump (python mode preserves Decimal/tuple) for honest base.
    honest_payload = honest_projection.model_dump()

    def _forged_auto() -> Any:
        from traffictwin.integration.manchester.map_match_workflow import (
            MapMatchObservationProjection,
        )

        # Forge only the acceptance fields; keep all honest derived fields
        # (diagnostics, ambiguity_reason, unmatched_reason, nearest_distance_m,
        # observation, queue_fingerprint, original_disposition, etc.) from the
        # honest public projection. Revalidate via public model_validate to
        # ensure real validation (not unchecked model_copy).
        forged_payload = dict(honest_payload)
        forged_payload["standing"] = "AUTO_ACCEPTED"
        forged_payload["standing_reason"] = (
            "owner policy unambiguously accepted under clear thresholds; "
            "distance alone not sufficient"
        )
        forged_payload["accepted_group_key"] = "ref:A56|primary"
        forged_payload["matched_edge_ids"] = ("e1",)
        return MapMatchObservationProjection.model_validate(forged_payload)

    rejected, detail = _expect_rejection(_forged_auto)
    if not rejected:
        return CheckResult(
            "04",
            "unresolved map match forged AUTO_ACCEPTED must be rejected",
            "FAIL",
            detail,
            "forged AUTO_ACCEPTED projection via MapMatchObservationProjection",
        )
    if "AUTO_ACCEPTED requires owner_policy_accepted_candidate" not in detail:
        return CheckResult(
            "04",
            "unresolved map match forged AUTO_ACCEPTED must be rejected for the semantic invariant",
            "FAIL",
            f"rejection detail did not contain expected semantic reason: {detail}",
            "AUTO_ACCEPTED requires owner_policy_accepted_candidate via MapMatchObservationProjection",
        )
    return CheckResult(
        "04",
        "Unresolved map match correctly remains UNRESOLVED; forged AUTO_ACCEPTED rejected; distance alone never accepts",
        "PASS",
        f"{d_ok} | {detail}",
        "honest UNRESOLVED vs forged AUTO_ACCEPTED via map_match_workflow (semantic invariant)",
    )


def check_05_baseline_not_accepted() -> CheckResult:
    from traffictwin.integration.manchester.closed_loop_journey import build_closed_loop_journey

    def _honest_journey() -> Any:
        j = build_closed_loop_journey(
            journey_id="twin-journey-no-provider",
            source_provider_available=False,
            source_snapshot_id=None,
            baseline_package=None,
            baseline_decision=None,
            baseline_software_validation=None,
            map_workflow=None,
            demand_result=None,
            demand_receipt=None,
            demand_decision=None,
            calibration_result=None,
            calibration_decision=None,
            calibration_receipt=None,
            sumo_request=None,
            sumo_receipt=None,
            output_package=None,
            output_receipt=None,
            comparison_result=None,
        )
        assert j.scientific_acceptance_present is False
        assert j.overall_standing == "PROVIDER_DATA_REQUIRED"
        assert "SOFTWARE_VALID does not imply" in j.limitations[1]
        return j

    ok, d_ok = _expect_success(_honest_journey)
    if not ok:
        return CheckResult(
            "05",
            "synthetic journey must be PROVIDER_DATA_REQUIRED not scientific",
            "FAIL",
            d_ok,
            "honest synthetic journey via closed_loop_journey",
        )

    def _forged_scientific() -> Any:
        from traffictwin.integration.manchester.closed_loop_journey import (
            ManchesterClosedLoopJourney,
        )

        # Build an otherwise type-correct journey (tuple stages, valid fingerprints,
        # valid limitations/evidence boundary) that specifically violates the
        # semantic invariant: overall_standing=SCIENTIFICALLY_ACCEPTED_BASELINE
        # while scientific_acceptance_present=False.
        # Stages as tuple ensures the rejection cannot be attributed to tuple shape.
        stages = build_closed_loop_journey(
            journey_id="twin-journey-no-provider",
            source_provider_available=False,
            source_snapshot_id=None,
            baseline_package=None,
            baseline_decision=None,
            baseline_software_validation=None,
            map_workflow=None,
            demand_result=None,
            demand_receipt=None,
            demand_decision=None,
            calibration_result=None,
            calibration_decision=None,
            calibration_receipt=None,
            sumo_request=None,
            sumo_receipt=None,
            output_package=None,
            output_receipt=None,
            comparison_result=None,
        ).stages
        payload = {
            "schema_version": "1.0",
            "capability_id": "MAN-09",
            "method_version": "manchester-closed-loop-journey-1.0",
            "journey_id": "forged-scientific",
            "stages": tuple(s.model_dump(mode="json") for s in stages),
            "overall_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
            "synthetic_execution_available": True,
            "scientific_acceptance_present": False,
            "limitations": (
                "Closed-loop journey composes stages without executing SUMO on inspection.",
                "SOFTWARE_VALID does not imply SCIENTIFICALLY_ACCEPTED_BASELINE.",
                "Provider-absent stops at PROVIDER_DATA_REQUIRED; synthetic may be AVAILABLE.",
                "Output and comparison are simulated only — non-causal, not validated.",
                "Replay/provenance/report links are plain destinations, not scientific claims.",
                "No SUMO execution on render; narrow Lane 01 contract only.",
            ),
            "evidence_boundary": "Manchester closed-loop journey: deterministic stage view over exact identities. No self-acceptance.",
            "journey_fingerprint": "00" * 32,
        }
        return ManchesterClosedLoopJourney.model_validate(payload)

    rejected, detail = _expect_rejection(_forged_scientific)
    if not rejected:
        return CheckResult(
            "05",
            "forged scientific acceptance must be rejected",
            "FAIL",
            detail,
            "SCIENTIFICALLY_ACCEPTED_BASELINE without scientific present via ManchesterClosedLoopJourney",
        )
    # Prove the rejection is the intended semantic invariant, not tuple shape,
    # stale fingerprint, or unrelated validation.
    if "SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present" not in detail:
        return CheckResult(
            "05",
            "forged scientific acceptance must be rejected for the semantic invariant",
            "FAIL",
            f"rejection detail did not contain expected semantic reason: {detail}",
            "SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present via ManchesterClosedLoopJourney",
        )
    return CheckResult(
        "05",
        "Scientifically unaccepted baseline correctly not marked accepted; forged acceptance rejected for the semantic invariant",
        "PASS",
        f"{d_ok} | {detail}",
        "synthetic journey vs forged scientific via closed_loop_journey (tuple stages, semantic invariant)",
    )


def check_06_incompatible_comparison() -> CheckResult:
    # Prove that incompatible measure/scope is refused and compatible succeeds
    from traffictwin.integration.manchester.comparison import (
        ComparisonIntervalContent,
        ComparisonLineage,
        ManchesterComparisonMetricContract,
        build_observed_comparison_interval,
        build_simulated_comparison_interval,
    )
    from traffictwin.integration.manchester.comparison_workflow import (
        ComparisonWorkflowPrerequisites,
        build_comparison_workflow_request,
        evaluate_comparison_workflow,
    )
    from traffictwin.integration.manchester.models import sha256_hex

    SCOPE_FP = "a" * 64
    TIME_FP = "b" * 64
    PROJECTION_FP = "1" * 64
    MAPPING_FP = "2" * 64
    CAL_FP = "3" * 64
    NET_FP = "4" * 64
    RUN_FP = "5" * 64
    SNAPSHOT_ID = "synthetic_road-20260101T000000Z-abcdef012345"

    def _contract(**overrides: Any) -> ManchesterComparisonMetricContract:
        base: dict[str, Any] = {
            "contract_version": "synthetic-demo-1",
            "evidence_class": "synthetic_development",
            "observed_source": "synthetic_utc_road",
            "scope_label": "synthetic_zone",
            "scope_fingerprint": SCOPE_FP,
            "time_basis_label": "synthetic_utc_hour",
            "time_basis_fingerprint": TIME_FP,
            "interval_duration_s": 900,
            "measure": "vehicle_count",
            "unit": "vehicles_per_interval",
            "minimum_observed_coverage": Decimal("0.500"),
            "minimum_simulated_coverage": Decimal("0.500"),
        }
        base.update(overrides)
        return ManchesterComparisonMetricContract.model_validate(base, strict=True)

    def _content(
        value: str = "10",
        measure: str = "vehicle_count",
        unit: str = "vehicles_per_interval",
        scope: str = "synthetic_zone",
        scope_fp: str = SCOPE_FP,
        time_label: str = "synthetic_utc_hour",
        time_fp: str = TIME_FP,
        start: int = 0,
        end: int = 900,
    ) -> ComparisonIntervalContent:
        return ComparisonIntervalContent.model_validate(
            {
                "site_edge_id": "edgeA",
                "interval_start_s": start,
                "interval_end_s": end,
                "direction": "N",
                "vehicle_class": "car",
                "measure": measure,
                "unit": unit,
                "value": Decimal(value),
                "scope_label": scope,
                "scope_fingerprint": scope_fp,
                "time_basis_label": time_label,
                "time_basis_fingerprint": time_fp,
            },
            strict=True,
        )

    def _observed(value: str = "10", **kw: Any) -> Any:
        interval = _content(value, **kw)
        return build_observed_comparison_interval(
            interval=interval,
            source_row_fingerprint=sha256_hex(
                f"obs-{value}-{json.dumps(kw, sort_keys=True)}".encode()
            ),
            synthetic=True,
            source="synthetic_utc_road",
            source_snapshot_id=SNAPSHOT_ID,
            projection_report_fingerprint=PROJECTION_FP,
            mapping_fingerprint=MAPPING_FP,
        )

    def _simulated(value: str = "12", **kw: Any) -> Any:
        interval = _content(value, **kw)
        return build_simulated_comparison_interval(
            interval=interval,
            source_row_fingerprint=sha256_hex(
                f"sim-{value}-{json.dumps(kw, sort_keys=True)}".encode()
            ),
            synthetic=True,
            network_fingerprint=NET_FP,
            calibration_fingerprint=CAL_FP,
            sumo_run_fingerprint=RUN_FP,
        )

    def _prereq(**overrides: Any) -> ComparisonWorkflowPrerequisites:
        base: dict[str, Any] = {
            "provider_evidence_available": True,
            "map_match_standing": "HUMAN_ACCEPTED",
            "demand_standing": "SYNTHETIC_ENGINEERING_CANDIDATE",
            "demand_software_valid": True,
            "calibration_accepted": True,
            "baseline_accepted": True,
            "output_software_valid": True,
            "output_fingerprint": "9" * 64,
        }
        base.update(overrides)
        return ComparisonWorkflowPrerequisites.model_validate(base, strict=True)

    def _lineage() -> ComparisonLineage:
        return ComparisonLineage(
            observed_snapshot_ids=(SNAPSHOT_ID,),
            projection_report_fingerprint=PROJECTION_FP,
            mapping_fingerprint=MAPPING_FP,
            calibration_fingerprint=CAL_FP,
            network_fingerprint=NET_FP,
            sumo_run_fingerprint=RUN_FP,
        )

    def _compatible() -> Any:
        contract = _contract()
        lineage = _lineage()
        obs = _observed(value="10")
        sim = _simulated(value="12")
        req = build_comparison_workflow_request(
            workflow_id="wf-compat-01",
            contract=contract,
            lineage=lineage,
            observed_inputs=[obs],
            simulated_inputs=[sim],
            prerequisites=_prereq(),
        )
        result = evaluate_comparison_workflow(req)
        assert result.standing not in ("REFUSED_INCOMPATIBLE", "BLOCKED_PROVIDER_DATA_REQUIRED")
        return result

    ok2, d_ok2 = _expect_success(_compatible)
    if not ok2:
        return CheckResult(
            "06",
            "compatible comparison must succeed",
            "FAIL",
            d_ok2,
            "compatible vehicle_count comparison via comparison_workflow",
        )

    def _incompatible() -> Any:
        contract = _contract()
        lineage = _lineage()
        # Mismatched scope in observed interval should be refused as SCOPE_MISMATCH
        obs = _observed(value="10", scope="other_zone", scope_fp="f" * 64)
        sim = _simulated(value="12")
        req = build_comparison_workflow_request(
            workflow_id="wf-incompat-scope",
            contract=contract,
            lineage=lineage,
            observed_inputs=[obs],
            simulated_inputs=[sim],
            prerequisites=_prereq(),
        )
        result = evaluate_comparison_workflow(req)
        assert result.standing == "REFUSED_INCOMPATIBLE"
        assert result.blocker_code == "SCOPE_MISMATCH"
        return result

    ok, detail = _expect_success(_incompatible)
    if not ok:
        return CheckResult(
            "06",
            "incompatible comparison correctly refused must be detectable",
            "FAIL",
            detail,
            "incompatible scope should be REFUSED_INCOMPATIBLE via comparison_workflow",
        )
    # Enrich detail with the proved blocker_code and standings for receipt informativeness
    try:
        # Re-run to capture the actual workflow result for detailed receipt
        _contract_probe = _contract()
        _lineage_probe = _lineage()
        _obs_probe = _observed(value="10", scope="other_zone", scope_fp="f" * 64)
        _sim_probe = _simulated(value="12")
        _req_probe = build_comparison_workflow_request(
            workflow_id="wf-incompat-detail",
            contract=_contract_probe,
            lineage=_lineage_probe,
            observed_inputs=[_obs_probe],
            simulated_inputs=[_sim_probe],
            prerequisites=_prereq(),
        )
        _res_probe = evaluate_comparison_workflow(_req_probe)
        detail_informative = (
            f"incompatible correctly REFUSED_INCOMPATIBLE blocker={_res_probe.blocker_code} "
            f"standing={_res_probe.standing} scope_mismatch=other_zone vs synthetic_zone | {detail} | {d_ok2}"
        )
    except Exception:
        detail_informative = f"{detail} | {d_ok2}"
    return CheckResult(
        "06",
        "Incompatible metric comparison is refused; compatible vehicle_count comparison succeeds",
        "PASS",
        detail_informative,
        "compatible vs incompatible scope via comparison_workflow (SCOPE_MISMATCH)",
    )


def check_07_admitted_missing_sha() -> CheckResult:
    from traffictwin.research_registry.models import (
        AdmissionStatus,
        EvidenceStanding,
        ResearchStudyRecord,
        StudyStatus,
    )

    def _valid_admitted() -> Any:
        return ResearchStudyRecord(
            study="E2b",
            version="1.0",
            title="E2b test study",
            question="Does X affect Y?",
            hypothesis="X improves Y",
            status=StudyStatus.COMPLETED,
            code_sha="a" * 40,
            manifest_hash="b" * 64,
            evaluator_id="eval-001",
            actor_id="c" * 64,
            checkpoint_id="d" * 64,
            trace_id="e" * 64,
            replication_unit="fleet_draw",
            seeds=[0],
            draws=[0, 1],
            arms=["off", "jsq"],
            estimand="mean difference",
            primary_metrics=["offered_task_deadline_attainment"],
            secondary_metrics=None,
            per_draw_values=None,
            declared_summary=None,
            evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
            admission_status=AdmissionStatus.ADMITTED,
            limitations=["limitation"],
            non_claims=["nonclaim"],
            product_links=None,
        )

    ok, d_ok = _expect_success(_valid_admitted)
    if not ok:
        return CheckResult(
            "07",
            "valid admitted study with SHA must be accepted",
            "FAIL",
            d_ok,
            "valid admitted E2b via ResearchStudyRecord",
        )

    def _missing_sha() -> Any:
        return ResearchStudyRecord(
            study="E2c",
            version="1.0",
            title="E2c missing SHA",
            question="Q?",
            hypothesis=None,
            status=StudyStatus.COMPLETED,
            code_sha=None,
            manifest_hash="b" * 64,
            evaluator_id="eval-001",
            actor_id="c" * 64,
            checkpoint_id="d" * 64,
            trace_id="e" * 64,
            replication_unit="fleet_draw",
            seeds=[1],
            draws=[1],
            arms=["a"],
            estimand="diff",
            primary_metrics=["m"],
            secondary_metrics=None,
            per_draw_values=None,
            declared_summary=None,
            evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
            admission_status=AdmissionStatus.ADMITTED,
            limitations=["limitation"],
            non_claims=["nonclaim"],
            product_links=None,
        )

    rejected, detail = _expect_rejection(_missing_sha)
    if not rejected:
        return CheckResult(
            "07",
            "admitted study missing code SHA must be rejected",
            "FAIL",
            detail,
            "ADMITTED without code_sha via ResearchStudyRecord",
        )

    def _bad_sha() -> Any:
        return ResearchStudyRecord(
            study="E2d",
            version="1.0",
            title="E2d bad SHA",
            question="Q?",
            hypothesis=None,
            status=StudyStatus.COMPLETED,
            code_sha="not-hex",
            manifest_hash="b" * 64,
            evaluator_id="eval-001",
            actor_id="c" * 64,
            checkpoint_id="d" * 64,
            trace_id="e" * 64,
            replication_unit="fleet_draw",
            seeds=[1],
            draws=[1],
            arms=["a"],
            estimand="diff",
            primary_metrics=["m"],
            secondary_metrics=None,
            per_draw_values=None,
            declared_summary=None,
            evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
            admission_status=AdmissionStatus.ADMITTED,
            limitations=["l"],
            non_claims=["n"],
            product_links=None,
        )

    rejected2, detail2 = _expect_rejection(_bad_sha)
    if not rejected2:
        return CheckResult(
            "07",
            "admitted study with bad SHA format must be rejected",
            "FAIL",
            detail2,
            "ADMITTED with malformed code_sha",
        )
    return CheckResult(
        "07",
        "Admitted study requires exact 40-hex code SHA; missing/malformed rejected",
        "PASS",
        f"{d_ok} | {detail} | {detail2}",
        "missing SHA via ResearchStudyRecord",
    )


def check_08_fake_e3() -> CheckResult:
    from traffictwin.research_registry.ingestion import ResearchStudyPackage
    from traffictwin.research_registry.models import (
        AdmissionStatus,
        EvidenceStanding,
        ResearchStudyRecord,
        StudyStatus,
    )
    from traffictwin.research_registry.service import RegistryService

    def _honest_registry() -> Any:
        svc = RegistryService.with_default_e2()
        snap = svc.snapshot()
        e3_admitted = [
            r
            for r in snap.records
            if r.study == "E3" and r.admission_status == AdmissionStatus.ADMITTED
        ]
        assert len(e3_admitted) == 0, f"E3 should not be admitted, found {e3_admitted}"
        e2_admitted = [r for r in snap.records if r.study.startswith("E2")]
        assert len(e2_admitted) >= 3, "E2 admitted records missing"
        return snap

    ok, d_ok = _expect_success(_honest_registry)
    if not ok:
        return CheckResult(
            "08",
            "honest registry must have no admitted E3",
            "FAIL",
            d_ok,
            "RegistryService snapshot should contain no admitted E3",
        )

    # Build a structurally valid future E3 record through public models
    def _fake_e3_record() -> ResearchStudyRecord:
        return ResearchStudyRecord(
            study="E3",
            version="9.9",
            title="Future E3 fake",
            question="Fake future research question for E3 validation?",
            hypothesis="Fake hypothesis for future E3",
            status=StudyStatus.COMPLETED,
            code_sha="f" * 40,
            manifest_hash="e" * 64,
            evaluator_id="eval-fake",
            actor_id="a" * 64,
            checkpoint_id="b" * 64,
            trace_id="c" * 64,
            replication_unit="fleet_draw",
            seeds=[99],
            draws=[99],
            arms=["future_arm"],
            estimand="future estimand",
            primary_metrics=["future_metric"],
            secondary_metrics=None,
            per_draw_values=None,
            declared_summary=None,
            evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
            admission_status=AdmissionStatus.ADMITTED,
            limitations=["future"],
            non_claims=["future nonclaim"],
            product_links=None,
        )

    try:
        fake_record = _fake_e3_record()
    except Exception as exc:
        return CheckResult(
            "08",
            "fake E3 record construction unexpectedly rejected",
            "FAIL",
            f"{exc}",
            "synthetic E3 via ResearchStudyRecord",
        )

    # Build a structurally valid future E3 package through public research-registry models
    try:
        fake_package = ResearchStudyPackage.build(records=[fake_record])
    except Exception as exc:
        return CheckResult(
            "08",
            "fake E3 package construction unexpectedly rejected",
            "FAIL",
            f"{exc}",
            "synthetic E3 package via ResearchStudyPackage",
        )

    # Attempt to ingest that exact package through RegistryService configured
    # with the authoritative current E2 admission policy.
    # The future-generic contract must remain capable of later exact allowlisted
    # packages supplied by Sol A — we do not hard-code E3 rejection in registry source.
    try:
        from traffictwin.research_registry.adapters import (
            build_default_e2_admission_policy,
            build_e2_study_package,
        )

        authoritative_pkg = build_e2_study_package()
        authoritative_policy = build_default_e2_admission_policy(authoritative_pkg)
        svc = RegistryService(authoritative_policy)
        # Pre-load the authoritative E2 package (the current admitted state)
        svc.ingest_package(authoritative_pkg)
        snap_before = svc.snapshot()
        before_ids = {(r.study, r.version) for r in snap_before.records}
        before_fp = snap_before.snapshot_fingerprint
        assert before_ids == {("E2b", "1.0"), ("E2c", "1.0"), ("E2d", "1.0")}

        # Attempt the real ingestion path — must reject because E3 is not in the exact allowlist
        rejected, ingest_detail = _expect_rejection(lambda: svc.ingest_package(fake_package))
        if not rejected:
            return CheckResult(
                "08",
                "fake E3 ingestion should be rejected by fail-closed admission policy",
                "FAIL",
                ingest_detail,
                "future E3 via RegistryService.ingest_package with authoritative E2 policy should be rejected (not in allowlist)",
            )

        # Prove the rejection mentions the allowlist / not-in-policy reason (fail-closed), not e.g. malformed packet
        if (
            "not in admission allowlist" not in ingest_detail
            and "allowlist" not in ingest_detail.lower()
        ):
            return CheckResult(
                "08",
                "fake E3 ingestion must be rejected for allowlist reason",
                "FAIL",
                f"rejection detail did not contain allowlist reason: {ingest_detail}",
                "future E3 ingestion via RegistryService should be rejected because not in exact allowlist",
            )

        # Prove service snapshot remains unchanged / no E3 admitted (fail-closed, no contamination)
        snap_after = svc.snapshot()
        after_ids = {(r.study, r.version) for r in snap_after.records}
        if after_ids != before_ids:
            return CheckResult(
                "08",
                "registry snapshot must remain unchanged after rejected E3 ingestion",
                "FAIL",
                f"before {before_ids} after {after_ids}",
                "service snapshot must be unchanged after failed ingestion",
            )
        if snap_after.snapshot_fingerprint != before_fp:
            return CheckResult(
                "08",
                "registry snapshot fingerprint must remain unchanged after rejected E3 ingestion",
                "FAIL",
                f"before {before_fp[:8]} after {snap_after.snapshot_fingerprint[:8]}",
                "snapshot fingerprint must be unchanged",
            )
        e3_admitted_after = [
            r
            for r in snap_after.records
            if r.study == "E3" and r.admission_status == AdmissionStatus.ADMITTED
        ]
        if len(e3_admitted_after) != 0:
            return CheckResult(
                "08",
                "fake E3 must not be admitted after rejected ingestion",
                "FAIL",
                f"E3 admitted after ingestion: {e3_admitted_after}",
                "no E3 admitted after ingestion",
            )
        # Also verify that with_default_e2 snapshot likewise rejects and remains unchanged
        svc_default = RegistryService.with_default_e2()
        snap_def_before_fp = svc_default.snapshot().snapshot_fingerprint
        rejected2, detail2 = _expect_rejection(lambda: svc_default.ingest_package(fake_package))
        if not rejected2:
            return CheckResult(
                "08",
                "fake E3 must also be rejected via with_default_e2 service",
                "FAIL",
                detail2,
                "with_default_e2 ingestion should also reject E3",
            )
        snap_def_after = svc_default.snapshot()
        if snap_def_after.snapshot_fingerprint != snap_def_before_fp:
            return CheckResult(
                "08",
                "with_default_e2 snapshot must remain unchanged after rejected E3",
                "FAIL",
                "fingerprint changed after rejected ingest",
                "snapshot unchanged",
            )

        detail = (
            f"fake E3 package {fake_package.package_fingerprint[:8]}… structurally valid but rejected by authoritative E2 allowlist: {ingest_detail}; "
            f"before {len(snap_before.records)} records, after {len(snap_after.records)} records, fingerprint unchanged {before_fp[:8]}…, no E3 admitted"
        )
        return CheckResult(
            "08",
            "Future E3 package correctly rejected by fail-closed current-policy ingestion; snapshot unchanged/no E3 admitted (future-generic contract preserved)",
            "PASS",
            f"{d_ok} | {detail}",
            "future E3 via ResearchStudyPackage + RegistryService.ingest_package with authoritative E2 policy (allowlist rejection, snapshot unchanged)",
        )
    except Exception as exc:
        # If we raised a CheckResult FAIL above, it would have returned; this is unexpected exception
        if isinstance(exc, ValueError) and "CheckResult" in str(type(exc)):
            raise
        return CheckResult(
            "08",
            "fake E3 ingestion probe unexpectedly failed",
            "FAIL",
            f"{exc.__class__.__name__}: {str(exc)[:800]}",
            "synthetic E3 ingestion via RegistryService",
        )


def check_09_replay_invented_event() -> CheckResult:
    from traffictwin.replay_observatory.models import (
        EntityIdentity,
        EntityKind,
        EventProvenance,
        EventType,
        EvidenceStanding,
        ReplayEventStream,
        SimulationTimeEvent,
        SimulationTimePayload,
        SourceCapabilityManifest,
        SourceDataKind,
        SourceIdentity,
        SourceKind,
    )

    def _valid_manifest() -> Any:
        from traffictwin.replay_observatory.models import EvidenceStanding as _ES

        m = SourceCapabilityManifest(
            manifest_id="manifest-valid-001",
            source=SourceIdentity(
                source_id="src-valid-001",
                source_kind=SourceKind.SYNTHETIC_FIXTURE,
                artifact_sha256="a" * 64,
                schema_version="1.0",
            ),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=_ES.SYNTHETIC_DATA,
            available_event_types=(EventType.SIMULATION_TIME,),
            limitations=("limited",),
        )
        assert EventType.TASK_OFFERED not in m.available_event_types
        return m

    ok, d_ok = _expect_success(_valid_manifest)
    if not ok:
        return CheckResult(
            "09",
            "valid manifest with only SIMULATION_TIME must be accepted",
            "FAIL",
            d_ok,
            "SourceCapabilityManifest public path",
        )

    def _invented() -> Any:
        from traffictwin.replay_observatory.models import (
            EvidenceStanding as _ES2,
        )
        from traffictwin.replay_observatory.models import (
            TaskOfferedEvent,
            TaskOfferedPayload,
        )

        manifest = SourceCapabilityManifest(
            manifest_id="manifest-invented-001",
            source=SourceIdentity(
                source_id="src-manifest-001",
                source_kind=SourceKind.SYNTHETIC_FIXTURE,
                artifact_sha256="f" * 64,
                schema_version="1.0",
            ),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=_ES2.SYNTHETIC_DATA,
            available_event_types=(EventType.SIMULATION_TIME,),
            limitations=("limited",),
        )
        src = SourceIdentity(
            source_id="src-001",
            source_kind=SourceKind.SYNTHETIC_FIXTURE,
            artifact_sha256="a" * 64,
            schema_version="1.0",
        )
        prov = EventProvenance(
            source_artifact_sha256="a" * 64,
            source_record_id="rec-001",
            adapter_id="adapter-test",
            adapter_version="1.0",
        )
        ent = EntityIdentity(entity_id="task-001", kind=EntityKind.TASK)
        payload = TaskOfferedPayload(offered_to_entity_id="res-001")
        event = TaskOfferedEvent(
            event_id="evt-001",
            sequence=0,
            simulator_time_s=0.0,
            entity=ent,
            source=src,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            provenance=prov,
            payload=payload,
        )
        return ReplayEventStream(
            schema_version="1.0",
            stream_id="stream-invented-001",
            capability_manifest=manifest,
            present_event_types=(EventType.TASK_OFFERED,),
            events=(event,),
            limitations=("replay stream",),
        )

    rejected, detail = _expect_rejection(_invented)
    if not rejected:
        return CheckResult(
            "09",
            "invented replay event must be rejected when not in capability",
            "FAIL",
            detail,
            "TASK_OFFERED invented when manifest only has SIMULATION_TIME via ReplayEventStream",
        )

    def _aggregate_only_invented() -> Any:
        from traffictwin.replay_observatory.models import EvidenceStanding as _ES3

        manifest = SourceCapabilityManifest(
            manifest_id="manifest-agg-001",
            source=SourceIdentity(
                source_id="src-agg-manifest-001",
                source_kind=SourceKind.SYNTHETIC_FIXTURE,
                artifact_sha256="c" * 64,
                schema_version="1.0",
            ),
            source_data_kind=SourceDataKind.AGGREGATE_ONLY,
            evidence_standing=_ES3.SYNTHETIC_DATA,
            available_event_types=(),
            limitations=("aggregate",),
        )
        src = SourceIdentity(
            source_id="src-agg-001",
            source_kind=SourceKind.SYNTHETIC_FIXTURE,
            artifact_sha256="b" * 64,
            schema_version="1.0",
        )
        prov = EventProvenance(
            source_artifact_sha256="b" * 64,
            source_record_id="rec-001",
            adapter_id="adapter-test",
            adapter_version="1.0",
        )
        ent = EntityIdentity(entity_id="sim-001", kind=EntityKind.SIMULATION)
        payload = SimulationTimePayload(step_index=0)
        event = SimulationTimeEvent(
            event_id="evt-agg-001",
            sequence=0,
            simulator_time_s=1.0,
            entity=ent,
            source=src,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            provenance=prov,
            payload=payload,
        )
        return ReplayEventStream(
            schema_version="1.0",
            stream_id="stream-agg-001",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(event,),
            limitations=("aggregate replay",),
        )

    rejected2, detail2 = _expect_rejection(_aggregate_only_invented)
    if not rejected2:
        return CheckResult(
            "09",
            "aggregate-only replay must be rejected",
            "FAIL",
            detail2,
            "aggregate-only source adapted into replay via ReplayEventStream",
        )
    return CheckResult(
        "09",
        "Invented replay event correctly rejected via capability manifest; aggregate-only also rejected",
        "PASS",
        f"{d_ok} | {detail} | {detail2}",
        "event not in available_event_types via ReplayEventStream",
    )


def check_10_broken_provenance() -> CheckResult:
    from traffictwin.replay_observatory.models import (
        EntityIdentity,
        EntityKind,
        EventProvenance,
        EventType,
        EvidenceStanding,
        ReplayEventStream,
        SimulationTimeEvent,
        SimulationTimePayload,
        SourceCapabilityManifest,
        SourceDataKind,
        SourceIdentity,
        SourceKind,
    )

    def _valid_chain() -> Any:
        from traffictwin.replay_observatory.models import EvidenceStanding as _ES4

        manifest = SourceCapabilityManifest(
            manifest_id="manifest-ok-001",
            source=SourceIdentity(
                source_id="src-manifest-ok-001",
                source_kind=SourceKind.SYNTHETIC_FIXTURE,
                artifact_sha256="c" * 64,
                schema_version="1.0",
            ),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=_ES4.SYNTHETIC_DATA,
            available_event_types=(EventType.SIMULATION_TIME,),
            limitations=("ok",),
        )
        sha = "c" * 64
        src = SourceIdentity(
            source_id="src-manifest-ok-001",
            source_kind=SourceKind.SYNTHETIC_FIXTURE,
            artifact_sha256=sha,
            schema_version="1.0",
        )
        prov = EventProvenance(
            source_artifact_sha256=sha,
            source_record_id="rec-001",
            adapter_id="adapter-test",
            adapter_version="1.0",
        )
        ent = EntityIdentity(entity_id="sim-ok-001", kind=EntityKind.SIMULATION)
        event = SimulationTimeEvent(
            event_id="evt-ok-001",
            sequence=0,
            simulator_time_s=0.0,
            entity=ent,
            source=src,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            provenance=prov,
            payload=SimulationTimePayload(step_index=0),
        )
        return ReplayEventStream(
            schema_version="1.0",
            stream_id="stream-ok-001",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(event,),
            limitations=("ok",),
        )

    ok, d_ok = _expect_success(_valid_chain)
    if not ok:
        return CheckResult(
            "10",
            "valid provenance chain must be accepted",
            "FAIL",
            d_ok,
            "valid chain via ReplayEventStream",
        )

    def _broken() -> Any:
        from traffictwin.replay_observatory.models import EvidenceStanding as _ES5

        manifest = SourceCapabilityManifest(
            manifest_id="manifest-broken-001",
            source=SourceIdentity(
                source_id="src-manifest-broken-001",
                source_kind=SourceKind.SYNTHETIC_FIXTURE,
                artifact_sha256="d" * 64,
                schema_version="1.0",
            ),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=_ES5.SYNTHETIC_DATA,
            available_event_types=(EventType.SIMULATION_TIME,),
            limitations=("ok",),
        )
        src = SourceIdentity(
            source_id="src-manifest-broken-001",
            source_kind=SourceKind.SYNTHETIC_FIXTURE,
            artifact_sha256="d" * 64,
            schema_version="1.0",
        )
        prov = EventProvenance(
            source_artifact_sha256="e" * 64,
            source_record_id="rec-001",
            adapter_id="adapter-test",
            adapter_version="1.0",
        )
        ent = EntityIdentity(entity_id="sim-broken-001", kind=EntityKind.SIMULATION)
        event = SimulationTimeEvent(
            event_id="evt-broken-001",
            sequence=0,
            simulator_time_s=0.0,
            entity=ent,
            source=src,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            provenance=prov,
            payload=SimulationTimePayload(step_index=0),
        )
        return ReplayEventStream(
            schema_version="1.0",
            stream_id="stream-broken-001",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(event,),
            limitations=("broken",),
        )

    rejected, detail = _expect_rejection(_broken)
    if not rejected:
        return CheckResult(
            "10",
            "broken provenance must be rejected",
            "FAIL",
            detail,
            "provenance sha mismatch via ReplayEventStream",
        )

    def _broken2() -> Any:
        from traffictwin.integration.manchester.snapshot_registry import SnapshotRegistration
        from traffictwin.integration.manchester.source_operations_models import (
            EvidenceStanding as _ESB,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SnapshotValidationState as _SVSB,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SourceFamily,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SourceFreshnessStanding as _SFSB,
        )

        return SnapshotRegistration(
            registration_id="prov-broken-001",
            snapshot_identity="snap-broken-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical surveyed counts at admitted points",
            record_count=1,
            parser_version="p-1",
            schema_version="s-1",
            validation_state=_SVSB.ACCEPTED,
            freshness=_SFSB.HISTORICAL,
            storage_reference="opaque/test/001",
            provenance_fingerprint="ff" * 32,
            validation_receipt_fingerprint="ff" * 32,
            validated_at_utc=datetime(2026, 1, 3, 0, 1, 0, tzinfo=UTC),
            evidence_standing=_ESB.REAL_MANCHESTER_DATA,
        )

    rejected2, detail2 = _expect_rejection(_broken2)
    if not rejected2:
        return CheckResult(
            "10",
            "snapshot provenance == validation receipt must be rejected",
            "FAIL",
            detail2,
            "identical provenance/validation receipt via SnapshotRegistration",
        )
    return CheckResult(
        "10",
        "Broken provenance/identity binding correctly rejected",
        "PASS",
        f"{d_ok} | {detail} | {detail2}",
        "sha mismatch + provenance==receipt via public models",
    )


def check_11_portable_absolute_path() -> CheckResult:
    from traffictwin.integration.manchester.snapshot_registry import SnapshotRegistration
    from traffictwin.integration.manchester.source_operations_models import (
        EvidenceStanding as _ES6,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        SnapshotValidationState as _SVS,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        SourceFamily,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        SourceFreshnessStanding as _SFS,
    )

    def _valid_opaque() -> Any:
        return SnapshotRegistration(
            registration_id="portable-valid-001",
            snapshot_identity="snap-valid-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 4, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical counts",
            record_count=1,
            parser_version="p-1",
            schema_version="s-1",
            validation_state=_SVS.ACCEPTED,
            freshness=_SFS.HISTORICAL,
            storage_reference="opaque/dft/20260104/001",
            provenance_fingerprint="bb" * 32,
            validation_receipt_fingerprint="cc" * 32,
            validated_at_utc=datetime(2026, 1, 4, 0, 1, 0, tzinfo=UTC),
            evidence_standing=_ES6.REAL_MANCHESTER_DATA,
        )

    ok, d_ok = _expect_success(_valid_opaque)
    if not ok:
        return CheckResult(
            "11",
            "valid opaque reference must be accepted",
            "FAIL",
            d_ok,
            "valid opaque storage_reference via SnapshotRegistration",
        )

    def _users_path() -> Any:
        from traffictwin.integration.manchester.source_operations_models import (
            EvidenceStanding as _ES7,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SnapshotValidationState as _SVS2,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SourceFreshnessStanding as _SFS2,
        )

        return SnapshotRegistration(
            registration_id="portable-bad-001",
            snapshot_identity="snap-bad-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 4, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical counts",
            record_count=1,
            parser_version="p-1",
            schema_version="s-1",
            validation_state=_SVS2.ACCEPTED,
            freshness=_SFS2.HISTORICAL,
            storage_reference="/Users/attacker/steal/dft/001",
            provenance_fingerprint="bb" * 32,
            validation_receipt_fingerprint="cc" * 32,
            validated_at_utc=datetime(2026, 1, 4, 0, 1, 0, tzinfo=UTC),
            evidence_standing=_ES7.REAL_MANCHESTER_DATA,
        )

    rejected, detail = _expect_rejection(_users_path)
    if not rejected:
        return CheckResult(
            "11",
            "artifact with /Users/ absolute path must be rejected",
            "FAIL",
            detail,
            "storage_reference='/Users/attacker/...' via SnapshotRegistration",
        )

    def _tmp_path() -> Any:
        from traffictwin.integration.manchester.source_operations_models import (
            EvidenceStanding as _ES8,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SnapshotValidationState as _SVS3,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SourceFreshnessStanding as _SFS3,
        )

        return SnapshotRegistration(
            registration_id="portable-tmp-001",
            snapshot_identity="snap-tmp-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 4, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical counts",
            record_count=1,
            parser_version="p-1",
            schema_version="s-1",
            validation_state=_SVS3.ACCEPTED,
            freshness=_SFS3.HISTORICAL,
            storage_reference="/tmp/private_scratch/dft/001",
            provenance_fingerprint="bb" * 32,
            validation_receipt_fingerprint="cc" * 32,
            validated_at_utc=datetime(2026, 1, 4, 0, 1, 0, tzinfo=UTC),
            evidence_standing=_ES8.REAL_MANCHESTER_DATA,
        )

    rejected2, detail2 = _expect_rejection(_tmp_path)
    if not rejected2:
        return CheckResult(
            "11",
            "artifact with /tmp/ path must be rejected",
            "FAIL",
            detail2,
            "storage_reference='/tmp/...' via SnapshotRegistration",
        )
    try:
        from traffictwin.evidence_admission.e2_research import load_admitted_builtin_e2_research
        from traffictwin.reporting.e2_research import build_e2_research_exports

        pkg, receipt = load_admitted_builtin_e2_research()
        exports = build_e2_research_exports(pkg, receipt)
        blob = exports.json + exports.csv + exports.markdown
        if "/Users/" in blob or "/home/" in blob or "/tmp/" in blob:
            return CheckResult(
                "11",
                "E2 export must not leak absolute paths",
                "FAIL",
                "E2 export contained absolute path",
                "E2 export leakage check",
            )
        detail3 = "E2 export contains no absolute path"
    except Exception as exc:
        return CheckResult(
            "11", "E2 export path check failed to execute", "FAIL", str(exc), "E2 export check"
        )
    return CheckResult(
        "11",
        "Portable artifact private path correctly rejected; E2 export clean",
        "PASS",
        f"{d_ok} | {detail} | {detail2} | {detail3}",
        "private path via SnapshotRegistration + E2 export scan",
    )


def check_12_credential_leakage() -> CheckResult:
    from traffictwin.integration.manchester.snapshot_registry import SnapshotRegistration
    from traffictwin.integration.manchester.source_operations_models import (
        EvidenceStanding as _ES9,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        SnapshotValidationState as _SVS4,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        SourceFamily,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        SourceFreshnessStanding as _SFS4,
    )

    def _valid() -> Any:
        return SnapshotRegistration(
            registration_id="cred-valid-001",
            snapshot_identity="snap-cred-valid-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 5, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical counts",
            record_count=1,
            parser_version="p-1",
            schema_version="s-1",
            validation_state=_SVS4.ACCEPTED,
            freshness=_SFS4.HISTORICAL,
            storage_reference="opaque/cred/001",
            provenance_fingerprint="bb" * 32,
            validation_receipt_fingerprint="cc" * 32,
            validated_at_utc=datetime(2026, 1, 5, 0, 1, 0, tzinfo=UTC),
            evidence_standing=_ES9.REAL_MANCHESTER_DATA,
        )

    ok, d_ok = _expect_success(_valid)
    if not ok:
        return CheckResult(
            "12",
            "valid registration without secret must be accepted",
            "FAIL",
            d_ok,
            "valid registration",
        )

    def _api_key() -> Any:
        from traffictwin.integration.manchester.source_operations_models import (
            EvidenceStanding as _ES10,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SnapshotValidationState as _SVS5,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SourceFreshnessStanding as _SFS5,
        )

        return SnapshotRegistration(
            registration_id="cred-bad-001",
            snapshot_identity="snap-cred-bad-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 5, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical counts with api_key=sk-1234567890abcdef",
            record_count=1,
            parser_version="p-1",
            schema_version="s-1",
            validation_state=_SVS5.ACCEPTED,
            freshness=_SFS5.HISTORICAL,
            storage_reference="opaque/cred/002",
            provenance_fingerprint="bb" * 32,
            validation_receipt_fingerprint="cc" * 32,
            validated_at_utc=datetime(2026, 1, 5, 0, 1, 0, tzinfo=UTC),
            evidence_standing=_ES10.REAL_MANCHESTER_DATA,
        )

    rejected, detail = _expect_rejection(_api_key)
    if not rejected:
        return CheckResult(
            "12",
            "registration with api_key secret must be rejected",
            "FAIL",
            detail,
            "coverage_summary='api_key=...' via SnapshotRegistration",
        )

    def _bearer() -> Any:
        from traffictwin.integration.manchester.source_operations_models import (
            EvidenceStanding as _ES11,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SnapshotValidationState as _SVS6,
        )
        from traffictwin.integration.manchester.source_operations_models import (
            SourceFreshnessStanding as _SFS6,
        )

        return SnapshotRegistration(
            registration_id="cred-bad2-001",
            snapshot_identity="snap-cred-bad2-001",
            content_fingerprint="a" * 64,
            retrieved_at_utc=datetime(2026, 1, 5, 0, 0, 0, tzinfo=UTC),
            source_family=SourceFamily.DFT,
            coverage_summary="historical counts",
            record_count=1,
            parser_version="Bearer eyJhbGciOiJIUzI1NiJ9.fake-token-value-1234567890",
            schema_version="s-1",
            validation_state=_SVS6.ACCEPTED,
            freshness=_SFS6.HISTORICAL,
            storage_reference="opaque/cred/003",
            provenance_fingerprint="bb" * 32,
            validation_receipt_fingerprint="cc" * 32,
            validated_at_utc=datetime(2026, 1, 5, 0, 1, 0, tzinfo=UTC),
            evidence_standing=_ES11.REAL_MANCHESTER_DATA,
        )

    rejected2, detail2 = _expect_rejection(_bearer)
    if not rejected2:
        return CheckResult(
            "12",
            "registration with bearer token must be rejected",
            "FAIL",
            detail2,
            "parser_version='Bearer ...' via SnapshotRegistration",
        )
    return CheckResult(
        "12",
        "Credential/secret leakage correctly rejected via typed validators",
        "PASS",
        f"{d_ok} | {detail} | {detail2}",
        "secret leakage via SnapshotRegistration",
    )


def run_all_checks() -> list[CheckResult]:
    checks: list[Callable[[], CheckResult]] = [
        check_01_sumo_injection,
        check_02_source_standing_inflation,
        check_03_bods_relabel,
        check_04_unresolved_map_match,
        check_05_baseline_not_accepted,
        check_06_incompatible_comparison,
        check_07_admitted_missing_sha,
        check_08_fake_e3,
        check_09_replay_invented_event,
        check_10_broken_provenance,
        check_11_portable_absolute_path,
        check_12_credential_leakage,
    ]
    results: list[CheckResult] = []
    for fn in checks:
        try:
            res = fn()
        except Exception as exc:
            # Canonical crash id: extract leading digits if present (e.g., check_01_* -> 01)
            raw = fn.__name__.replace("check_", "")
            crash_id = raw[:2] if raw[:2].isdigit() else "99"
            res = CheckResult(
                crash_id,
                fn.__doc__ or "check failed with exception",
                "FAIL",
                f"exception in check: {exc.__class__.__name__}: {str(exc)[:800]}",
                "internal error",
            )
        results.append(res)
    return results


def build_validator_receipt(check_results: list[CheckResult]) -> dict[str, Any]:
    sorted_results = sorted(check_results, key=lambda r: r.id)
    checks_payload = [
        {
            "id": r.id,
            "title": r.title,
            "status": r.status,
            "detail": r.detail[:700],
            "mutation": r.mutation[:350],
        }
        for r in sorted_results
    ]
    overall = "PASS" if all(r.status == "PASS" for r in sorted_results) else "FAIL"
    try:
        from traffictwin.ui.expansion_routes import EXPANSION_PAGE_SPECS

        expansion_routes = [
            {"title": s.title, "group": s.group, "url_path": s.url_path, "script": s.script}
            for s in sorted(EXPANSION_PAGE_SPECS, key=lambda x: x.title)
        ]
    except Exception:
        expansion_routes = []
    try:
        from traffictwin.ui.navigation_v07 import (
            V07_NAVIGATION_GROUPS,
            V07_PAGE_SPECS,
        )

        navigation_groups = list(V07_NAVIGATION_GROUPS)
        normative_inventory = len(V07_PAGE_SPECS)
    except Exception:
        navigation_groups = []
        normative_inventory = 0
    synthetic_available = False
    provider_blocked_truthful = False
    try:
        from traffictwin.integration.manchester.closed_loop_journey import build_closed_loop_journey

        # Truthful provider-blocked (no data) must be PROVIDER_DATA_REQUIRED and synthetic false.
        j_blocked = build_closed_loop_journey(
            journey_id="validator-blocked-check",
            source_provider_available=False,
            source_snapshot_id=None,
            baseline_package=None,
            baseline_decision=None,
            baseline_software_validation=None,
            map_workflow=None,
            demand_result=None,
            demand_receipt=None,
            demand_decision=None,
            calibration_result=None,
            calibration_decision=None,
            calibration_receipt=None,
            sumo_request=None,
            sumo_receipt=None,
            output_package=None,
            output_receipt=None,
            comparison_result=None,
        )
        provider_blocked_truthful = j_blocked.overall_standing == "PROVIDER_DATA_REQUIRED"
        # Synthetic engineering remains available even when provider blocked, via synthetic output.
        # This yields SOFTWARE_VALID_SYNTHETIC_AVAILABLE and synthetic true.
        try:
            from traffictwin.integration.manchester.models import sha256_hex as _sha256_hex_v
            from traffictwin.integration.manchester.sumo_output_pipeline import (
                SumoOutputFileDeclaration,
                SumoOutputNetworkIdentity,
                SumoOutputProvenance,
                SumoOutputTimeBasis,
                SumoOutputToolIdentity,
                build_sumo_output_request,
                import_sumo_outputs,
            )

            _trip = b'<tripinfos><tripinfo id="v0" depart="0.0" /></tripinfos>'
            _summ = b'<summary><step time="0.0" running="1" /></summary>'
            _tool = SumoOutputToolIdentity(reported_version="1.27.0", executable_sha256="a" * 64)
            _net = SumoOutputNetworkIdentity(
                network_sha256="b" * 64,
                demand_sha256="c" * 64,
                config_sha256="d" * 64,
                network_file="net.xml",
                demand_file="routes.xml",
                config_file="sumo.sumocfg",
            )
            _tb = SumoOutputTimeBasis(
                window_start_s=0,
                window_end_s=3600,
                step_length_s=1,
                time_basis_label="synthetic_utc_hour",
                time_basis_fingerprint="e" * 64,
            )
            _decls = [
                SumoOutputFileDeclaration(
                    relative_path="tripinfo.xml",
                    sha256=_sha256_hex_v(_trip),
                    size_bytes=len(_trip),
                    required=True,
                    media_type="application/xml",
                ),
                SumoOutputFileDeclaration(
                    relative_path="summary.xml",
                    sha256=_sha256_hex_v(_summ),
                    size_bytes=len(_summ),
                    required=True,
                    media_type="application/xml",
                ),
            ]
            _req = build_sumo_output_request(
                request_id="validator-req-01",
                run_id="validator-run-01",
                tool=_tool,
                network=_net,
                time_basis=_tb,
                files=_decls,
            )
            _pkg = import_sumo_outputs(
                _req,
                {"tripinfo.xml": _trip, "summary.xml": _summ},
                provenance=SumoOutputProvenance(
                    created_at_utc="2026-01-01T00:00:00Z",
                    created_by="validator",
                    parent_fingerprints=(),
                ),
            )
            j_synth = build_closed_loop_journey(
                journey_id="validator-synthetic-check",
                source_provider_available=False,
                source_snapshot_id=None,
                baseline_package=None,
                baseline_decision=None,
                baseline_software_validation=None,
                map_workflow=None,
                demand_result=None,
                demand_receipt=None,
                demand_decision=None,
                calibration_result=None,
                calibration_decision=None,
                calibration_receipt=None,
                sumo_request=None,
                sumo_receipt=None,
                output_package=_pkg,
                output_receipt=None,
                comparison_result=None,
            )
            synthetic_available = (
                j_synth.synthetic_execution_available is True
                and j_synth.overall_standing == "SOFTWARE_VALID_SYNTHETIC_AVAILABLE"
            )
        except Exception:
            synthetic_available = False
    except Exception:
        pass
    e2_admitted_count = 0
    try:
        from traffictwin.research_registry.service import RegistryService

        snap = RegistryService.with_default_e2().snapshot()
        e2_admitted_count = len([r for r in snap.records if r.study.startswith("E2")])
    except Exception:
        pass
    replay_deterministic = False
    try:
        from traffictwin.ui.replay_observatory_service import (
            build_synthetic_engineering_stream,
            create_engine,
        )

        s1 = build_synthetic_engineering_stream()
        s2 = build_synthetic_engineering_stream()
        e1 = create_engine(s1)
        e2 = create_engine(s2)
        replay_deterministic = (
            e1.state().playhead_time_s == e2.state().playhead_time_s
            and e1.stream.stream_id == e2.stream.stream_id
        )
    except Exception:
        pass
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "expansion_method": EXPANSION_METHOD,
        "validator_version": "1.0",
        "overall_result": overall,
        "checks": checks_payload,
        "summary": {
            "total": len(checks_payload),
            "passed": sum(1 for r in sorted_results if r.status == "PASS"),
            "failed": sum(1 for r in sorted_results if r.status == "FAIL"),
        },
        "integration_provenance": {
            "expansion_routes": expansion_routes,
            "navigation_groups": navigation_groups,
            "normative_inventory": normative_inventory,
            "synthetic_execution_available": synthetic_available,
            "provider_blocked_truthful": provider_blocked_truthful,
            "e2_admitted_count": e2_admitted_count,
            "replay_deterministic": replay_deterministic,
        },
        "limitations": [
            "Validator is software acceptance only — no research workloads, no Manchester/E3 experiments, no provider retrieval.",
            "BLOCKED/PROVIDER_DATA_REQUIRED states are truthful; synthetic engineering execution remains available.",
            "Inferences from aggregate evidence, visual sync, distance alone, or convergence to realism are never made.",
            "E3 is absent by design; validator does not fabricate E3.",
            "All checks are deterministic, non-networked, via public typed construction paths.",
        ],
        "evidence_boundary": "TrafficTwin Expansion V1 validator: deterministic, non-networked, fail-closed proof of the integrated release.",
    }
    fingerprint = _sha256_hex(_canonical_json(payload).encode("utf-8"))
    payload["validator_fingerprint"] = fingerprint
    payload["deterministic"] = True
    payload["receipt_fingerprint"] = _sha256_hex(
        f"{fingerprint}:{overall}:{len(checks_payload)}".encode()
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="TrafficTwin Expansion V1 strict validator — Lane 16"
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    parser.add_argument(
        "--output", type=str, default=None, help="write JSON receipt to path (relative, portable)"
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args(argv)
    results = run_all_checks()
    receipt = build_validator_receipt(results)
    leakage_re = re.compile(
        r"(?:api[_-]?key\s*[:=]|password\s*[:=]|secret\s*[:=]|bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,})",
        re.IGNORECASE,
    )
    blob = (
        _canonical_json(receipt)
        if not args.pretty
        else json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False)
    )
    if _contains_private_path(blob):
        print("VALIDATOR_OUTPUT_CONTAINS_PRIVATE_PATH: refused", file=sys.stderr)
        return 2
    if leakage_re.search(blob):
        print(
            "VALIDATOR_OUTPUT_CONTAINS_SECRET: refused (credential value leakage)", file=sys.stderr
        )
        return 2
    if args.output is not None:
        out_path = Path(args.output)
        if out_path.is_absolute() or ".." in out_path.parts or str(out_path).startswith("/"):
            print("output path must be relative portable", file=sys.stderr)
            return 2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(blob, encoding="utf-8")
        print(f"receipt written to {out_path} (portable, deterministic)", file=sys.stderr)
    if args.json or args.output is not None:
        print(blob)
    else:
        for r in sorted(results, key=lambda x: x.id):
            mark = "PASS" if r.status == "PASS" else "FAIL"
            print(f"[{mark}] {r.id}: {r.title}")
            print(f"      {r.detail[:250]}")
        print(
            f"\nOverall: {receipt['overall_result']}  fingerprint: {receipt['validator_fingerprint'][:16]}..."
        )
        print(f"Checks: {receipt['summary']['passed']}/{receipt['summary']['total']} passed")
        print("\nMachine-readable JSON available with --json")
    return 0 if receipt["overall_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
