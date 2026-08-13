"""Manchester closed-loop journey — Lane 06 deterministic orchestration.

Composes exact upstream identities without duplicating logic.
Every stage binds exact identities and fails closed on drift.
Optimisation convergence does not imply calibrated realism.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from traffictwin.integration.manchester.baseline_package import (
    ManchesterBaselineAcceptanceDecision,
    ManchesterBaselineCandidatePackage,
    ManchesterBaselinePackageError,
    ManchesterBaselineSoftwareValidation,
    verify_baseline_acceptance,
)
from traffictwin.integration.manchester.calibration_workflow import (
    ManchesterCalibrationAcceptanceReceipt,
    ManchesterCalibrationBaselineDecision,
    ManchesterCalibrationWorkflowError,
    ManchesterCalibrationWorkflowResult,
    verify_acceptance_receipt,
)
from traffictwin.integration.manchester.closed_loop_execution import (
    ClosedLoopExecutionReceipt,
    ClosedLoopExecutionRequest,
)
from traffictwin.integration.manchester.comparison_workflow import (
    ManchesterComparisonWorkflowResult,
)
from traffictwin.integration.manchester.demand_package import (
    ManchesterDemandAcceptanceDecision,
    ManchesterDemandPackageError,
    ManchesterDemandPackageResult,
    ManchesterDemandReceipt,
    verify_demand_receipt,
)
from traffictwin.integration.manchester.map_match_workflow import (
    MapMatchWorkflowResult,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.sumo_output_pipeline import (
    ManchesterSumoOutputPackage,
    ManchesterSumoOutputReceipt,
)

JOURNEY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
JOURNEY_METHOD_VERSION: Literal["manchester-closed-loop-journey-1.0"] = (
    "manchester-closed-loop-journey-1.0"
)
JOURNEY_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

LIMITATIONS: tuple[str, ...] = (
    "Closed-loop journey composes stages without executing SUMO on inspection.",
    "SOFTWARE_VALID does not imply SCIENTIFICALLY_ACCEPTED_BASELINE.",
    "Provider-absent stops at PROVIDER_DATA_REQUIRED; synthetic may be AVAILABLE.",
    "Output and comparison are simulated only — non-causal, not validated.",
    "Replay/provenance/report links are plain destinations, not scientific claims.",
    "No SUMO execution on render; narrow Lane 01 contract only.",
)

_EVIDENCE_BOUNDARY = (
    "Manchester closed-loop journey: deterministic stage view over "
    "exact identities. No self-acceptance."
)

_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_RE = re.compile(
    r"(apikey|api_key|secret|password|passwd|token|bearer|credential|authorization)",
    re.IGNORECASE,
)
_JOURNEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


def _reject_private_path(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    if "\\" in value or ".." in value.split("/"):
        raise ValueError(f"{label} must not contain traversal")
    return value


def _reject_secret(value: str, label: str) -> str:
    if _SECRET_RE.search(value):
        raise ValueError(f"{label} must not contain a likely secret")
    return value


def _canonical_json(payload: object) -> str:
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


def _sanitize(msg: str) -> str:
    if _PRIVATE_PATH_RE.search(msg) or _SECRET_RE.search(msg):
        return "invalid input"
    return msg[:500]


class ManchesterJourneyError(ValueError):
    """Typed refusal for the closed-loop journey."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterJourneyModel(ManchesterSnapshotModel):
    """Strict frozen base."""


def _revalidate_strict(model: BaseModel) -> BaseModel:
    if not isinstance(model, BaseModel):
        raise ManchesterJourneyError(
            "JOURNEY_TYPE_MISMATCH",
            "expected a Manchester model instance",
        )
    return model.__class__.model_validate(
        model.model_dump(mode="python"),
        strict=True,
    )


class JourneyStageStatus(ManchesterJourneyModel):
    """One deterministic stage with exact binding."""

    stage_id: Literal[
        "source_standing",
        "baseline",
        "map_review",
        "demand",
        "calibration",
        "sumo_execution",
        "output_import",
        "comparison",
        "replay_provenance_report",
    ]
    standing: Literal[
        "AVAILABLE",
        "SOFTWARE_VALID",
        "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "PROVIDER_DATA_REQUIRED",
        "BLOCKED",
        "UNAVAILABLE",
        "NOT_APPLICABLE_SYNTHETIC",
    ]
    upstream_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    receipt_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    blocker_code: str | None = Field(default=None, max_length=64)
    blocker_message: str | None = Field(default=None, max_length=500)
    owner_action: str = Field(min_length=1, max_length=500)
    evidence_class: Literal[
        "SYNTHETIC_ENGINEERING",
        "DESIGN_ONLY",
        "PRODUCTION",
        "PROVIDER_DATA_REQUIRED",
    ] = "DESIGN_ONLY"

    @field_validator("owner_action", "blocker_code", "blocker_message")
    @classmethod
    def _validate_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _reject_private_path(v, "stage text")
        _reject_secret(v, "stage text")
        return v

    @model_validator(mode="after")
    def _validate(self) -> JourneyStageStatus:
        if (
            self.standing
            in {
                "BLOCKED",
                "PROVIDER_DATA_REQUIRED",
                "UNAVAILABLE",
            }
            and self.blocker_code is None
        ):
            raise ValueError(f"{self.stage_id} standing {self.standing!r} requires blocker")
        return self


class ManchesterClosedLoopJourney(ManchesterJourneyModel):
    """Complete deterministic journey view."""

    schema_version: Literal["1.0"] = JOURNEY_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = JOURNEY_CAPABILITY_ID
    method_version: Literal["manchester-closed-loop-journey-1.0"] = JOURNEY_METHOD_VERSION
    journey_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    stages: tuple[JourneyStageStatus, ...] = Field(min_length=9, max_length=9)
    overall_standing: Literal[
        "PROVIDER_DATA_REQUIRED",
        "SOFTWARE_VALID_SYNTHETIC_AVAILABLE",
        "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "BLOCKED",
        "INCOMPLETE",
    ]
    synthetic_execution_available: bool
    scientific_acceptance_present: bool
    limitations: tuple[str, ...] = LIMITATIONS
    evidence_boundary: str = _EVIDENCE_BOUNDARY
    journey_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("journey_id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        _reject_private_path(v, "journey_id")
        _reject_secret(v, "journey_id")
        if not _JOURNEY_ID_RE.fullmatch(v):
            raise ValueError("journey_id must match safe pattern")
        return v

    @field_validator("limitations", "evidence_boundary")
    @classmethod
    def _validate_text(cls, v: str | tuple[str, ...]) -> str | tuple[str, ...]:
        if isinstance(v, str):
            _reject_private_path(v, "provenance text")
            _reject_secret(v, "provenance text")
        else:
            for item in v:
                _reject_private_path(item, "limitation")
                _reject_secret(item, "limitation")
        return v

    @model_validator(mode="after")
    def _validate(self) -> ManchesterClosedLoopJourney:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be exact literal")
        if self.evidence_boundary != _EVIDENCE_BOUNDARY:
            raise ValueError("evidence_boundary must be exact literal")
        expected_ids = (
            "source_standing",
            "baseline",
            "map_review",
            "demand",
            "calibration",
            "sumo_execution",
            "output_import",
            "comparison",
            "replay_provenance_report",
        )
        actual_ids = tuple(s.stage_id for s in self.stages)
        if actual_ids != expected_ids:
            raise ValueError(f"stages must be in exact order {expected_ids}")
        if (
            self.scientific_acceptance_present
            and self.overall_standing != "SCIENTIFICALLY_ACCEPTED_BASELINE"
        ):
            raise ValueError("scientific present requires SCIENTIFICALLY_ACCEPTED_BASELINE")
        if (
            not self.scientific_acceptance_present
            and self.overall_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE"
        ):
            raise ValueError("SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present")
        expected_fp = _journey_fingerprint(self)
        if self.journey_fingerprint != expected_fp:
            raise ValueError("journey_fingerprint must be re-derived")
        return self


def _journey_fingerprint(journey: ManchesterClosedLoopJourney) -> str:
    payload = {
        "journey_id": journey.journey_id,
        "stages": [json.loads(s.model_dump_json()) for s in journey.stages],
        "overall_standing": journey.overall_standing,
        "synthetic_execution_available": journey.synthetic_execution_available,
        "scientific_acceptance_present": journey.scientific_acceptance_present,
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def build_closed_loop_journey(
    *,
    journey_id: str,
    source_provider_available: bool,
    source_snapshot_id: str | None,
    baseline_package: ManchesterBaselineCandidatePackage | None,
    baseline_decision: ManchesterBaselineAcceptanceDecision | None,
    baseline_software_validation: ManchesterBaselineSoftwareValidation | None = None,
    map_workflow: MapMatchWorkflowResult | None,
    demand_result: ManchesterDemandPackageResult | None,
    demand_receipt: ManchesterDemandReceipt | None,
    demand_decision: ManchesterDemandAcceptanceDecision | None = None,
    calibration_result: ManchesterCalibrationWorkflowResult | None = None,
    calibration_decision: ManchesterCalibrationBaselineDecision | None,
    calibration_receipt: ManchesterCalibrationAcceptanceReceipt | None,
    sumo_request: ClosedLoopExecutionRequest | None,
    sumo_receipt: ClosedLoopExecutionReceipt | None,
    output_package: ManchesterSumoOutputPackage | None,
    output_receipt: ManchesterSumoOutputReceipt | None,
    comparison_result: ManchesterComparisonWorkflowResult | None,
) -> ManchesterClosedLoopJourney:
    """Compose journey from exact upstream artifacts.

    Convergence does not imply calibrated realism.
    """
    if baseline_package is not None:
        _revalidate_strict(baseline_package)
    if baseline_decision is not None:
        _revalidate_strict(baseline_decision)
    if baseline_software_validation is not None:
        _revalidate_strict(baseline_software_validation)
    if map_workflow is not None:
        _revalidate_strict(map_workflow)
    if demand_result is not None:
        _revalidate_strict(demand_result)
    if demand_receipt is not None:
        _revalidate_strict(demand_receipt)
    if demand_decision is not None:
        _revalidate_strict(demand_decision)
    if calibration_result is not None:
        _revalidate_strict(calibration_result)
    if calibration_decision is not None:
        _revalidate_strict(calibration_decision)
    if calibration_receipt is not None:
        _revalidate_strict(calibration_receipt)
    if sumo_request is not None:
        _revalidate_strict(sumo_request)
    if sumo_receipt is not None:
        _revalidate_strict(sumo_receipt)
    if output_package is not None:
        _revalidate_strict(output_package)
    if output_receipt is not None:
        _revalidate_strict(output_receipt)
    if comparison_result is not None:
        _revalidate_strict(comparison_result)

    if not source_provider_available:
        source_stage = JourneyStageStatus(
            stage_id="source_standing",
            standing="PROVIDER_DATA_REQUIRED",
            blocker_code="PROVIDER_DATA_REQUIRED",
            blocker_message="No admitted Manchester provider snapshot is available",
            owner_action="Provide an admitted snapshot or run synthetic design",
            evidence_class="PROVIDER_DATA_REQUIRED",
        )
    else:
        if source_snapshot_id is None:
            raise ManchesterJourneyError(
                "JOURNEY_SOURCE_ID_MISSING",
                "provider-available source requires a snapshot id",
            )
        _reject_private_path(source_snapshot_id, "source snapshot id")
        _reject_secret(source_snapshot_id, "source snapshot id")
        source_stage = JourneyStageStatus(
            stage_id="source_standing",
            standing="AVAILABLE",
            upstream_fingerprint=_sha256_hex(source_snapshot_id.encode("utf-8")),
            owner_action="Source snapshot available — proceed to baseline review",
            evidence_class="PRODUCTION",
        )

    if baseline_package is None:
        baseline_stage = JourneyStageStatus(
            stage_id="baseline",
            standing="UNAVAILABLE",
            blocker_code="BASELINE_PACKAGE_MISSING",
            blocker_message="No baseline candidate package has been built",
            owner_action="Build a baseline candidate package from the approved scope",
            evidence_class="PROVIDER_DATA_REQUIRED"
            if not source_provider_available
            else "DESIGN_ONLY",
        )
    else:
        pkg_fp = baseline_package.fingerprint()
        if baseline_decision is not None:
            try:
                verify_baseline_acceptance(
                    baseline_decision,
                    baseline_package,
                    baseline_software_validation,
                )
            except ManchesterBaselinePackageError as exc:
                raise ManchesterJourneyError(
                    "JOURNEY_BASELINE_VERIFICATION_FAILED",
                    _sanitize(str(exc)),
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise ManchesterJourneyError(
                    "JOURNEY_BASELINE_VERIFICATION_FAILED",
                    _sanitize(str(exc)),
                ) from exc
            if baseline_decision.scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
                baseline_stage = JourneyStageStatus(
                    stage_id="baseline",
                    standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
                    upstream_fingerprint=pkg_fp,
                    receipt_fingerprint=baseline_decision.fingerprint(),
                    owner_action="Baseline is scientifically accepted — proceed to map review",
                    evidence_class="PRODUCTION",
                )
            else:
                baseline_stage = JourneyStageStatus(
                    stage_id="baseline",
                    standing="BLOCKED",
                    upstream_fingerprint=pkg_fp,
                    receipt_fingerprint=baseline_decision.fingerprint(),
                    blocker_code="BASELINE_NOT_ACCEPTED",
                    blocker_message=(
                        f"Baseline decision is {baseline_decision.scientific_standing!r} "
                        "— not accepted"
                    ),
                    owner_action=(
                        "Review baseline decision and re-accept with attributable review"
                    ),
                    evidence_class="DESIGN_ONLY",
                )
        else:
            if baseline_software_validation is not None:
                baseline_stage = JourneyStageStatus(
                    stage_id="baseline",
                    standing="BLOCKED",
                    upstream_fingerprint=pkg_fp,
                    blocker_code="BASELINE_DECISION_MISSING",
                    blocker_message="Validation without decision cannot be accepted",
                    owner_action="Request attributable acceptance for this fingerprint",
                    evidence_class="DESIGN_ONLY",
                )
            elif not source_provider_available:
                baseline_stage = JourneyStageStatus(
                    stage_id="baseline",
                    standing="PROVIDER_DATA_REQUIRED",
                    upstream_fingerprint=pkg_fp,
                    blocker_code="PROVIDER_DATA_REQUIRED",
                    blocker_message="Synthetic engineering — provider data required for acceptance",
                    owner_action="Synthetic baseline is SOFTWARE_VALID; provide observed evidence",
                    evidence_class="SYNTHETIC_ENGINEERING",
                )
            else:
                baseline_stage = JourneyStageStatus(
                    stage_id="baseline",
                    standing="SOFTWARE_VALID",
                    upstream_fingerprint=pkg_fp,
                    blocker_code="BASELINE_DECISION_PENDING",
                    blocker_message=(
                        "Baseline is software-valid but not yet scientifically accepted"
                    ),
                    owner_action=("Request attributable acceptance for this fingerprint"),
                    evidence_class="DESIGN_ONLY",
                )

    if map_workflow is None:
        map_stage = JourneyStageStatus(
            stage_id="map_review",
            standing="UNAVAILABLE",
            blocker_code="MAP_WORKFLOW_MISSING",
            blocker_message="No map-match workflow result is available",
            owner_action="Run map-match workflow over admitted DfT observations",
            evidence_class="PROVIDER_DATA_REQUIRED"
            if not source_provider_available
            else "DESIGN_ONLY",
        )
    else:
        wf_fp = map_workflow.fingerprint()
        unresolved = tuple(map_workflow.unresolved_ids)
        rejected = tuple(map_workflow.rejected_ids)
        if len(unresolved) > 0 or len(rejected) > 0:
            map_stage = JourneyStageStatus(
                stage_id="map_review",
                standing="BLOCKED",
                upstream_fingerprint=wf_fp,
                blocker_code="MAP_MATCH_UNRESOLVED",
                blocker_message="Map matching has unresolved or rejected rows — cannot advance",
                owner_action="Complete named-person review for unresolved matches",
                evidence_class="DESIGN_ONLY",
            )
        else:
            accepted = tuple(map_workflow.auto_accepted_ids) + tuple(
                map_workflow.human_accepted_ids
            )
            if len(accepted) == 0:
                map_stage = JourneyStageStatus(
                    stage_id="map_review",
                    standing="BLOCKED",
                    upstream_fingerprint=wf_fp,
                    blocker_code="MAP_MATCH_NO_ACCEPTED",
                    blocker_message="No accepted map matches are available",
                    owner_action="Run map-match workflow to obtain accepted projections",
                    evidence_class="DESIGN_ONLY",
                )
            else:
                map_stage = JourneyStageStatus(
                    stage_id="map_review",
                    standing="AVAILABLE",
                    upstream_fingerprint=wf_fp,
                    owner_action="Map matches accepted — proceed to demand construction",
                    evidence_class="PRODUCTION"
                    if source_provider_available
                    else "SYNTHETIC_ENGINEERING",
                )

    earlier_blocked = any(
        s.standing in {"BLOCKED", "PROVIDER_DATA_REQUIRED"}
        for s in (source_stage, baseline_stage, map_stage)
    )

    if demand_result is None:
        demand_stage = JourneyStageStatus(
            stage_id="demand",
            standing="UNAVAILABLE",
            blocker_code="DEMAND_MISSING",
            blocker_message="No demand package result is available",
            owner_action="Build demand package from accepted map projections",
            evidence_class="PROVIDER_DATA_REQUIRED"
            if not source_provider_available
            else "DESIGN_ONLY",
        )
    else:
        if earlier_blocked:
            demand_stage = JourneyStageStatus(
                stage_id="demand",
                standing="BLOCKED",
                upstream_fingerprint=demand_result.fingerprint(),
                blocker_code="EARLIER_STAGE_BLOCKED",
                blocker_message="Earlier stage is blocked — cannot advance demand",
                owner_action="Resolve earlier blocker before advancing demand",
                evidence_class="DESIGN_ONLY",
            )
        elif demand_receipt is not None:
            if demand_decision is None:
                raise ManchesterJourneyError(
                    "JOURNEY_DEMAND_DECISION_MISSING",
                    "demand receipt without exact decision is drift — blocked",
                )
            try:
                verify_demand_receipt(
                    demand_receipt,
                    result=demand_result,
                    decision=demand_decision,
                )
            except ManchesterDemandPackageError as exc:
                raise ManchesterJourneyError(
                    "JOURNEY_DEMAND_VERIFICATION_FAILED",
                    _sanitize(str(exc)),
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise ManchesterJourneyError(
                    "JOURNEY_DEMAND_VERIFICATION_FAILED",
                    _sanitize(str(exc)),
                ) from exc
            if demand_receipt.scientific_standing == "SCIENTIFICALLY_ACCEPTED_DEMAND":
                demand_stage = JourneyStageStatus(
                    stage_id="demand",
                    standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
                    upstream_fingerprint=demand_result.fingerprint(),
                    receipt_fingerprint=demand_receipt.fingerprint(),
                    owner_action="Demand accepted — proceed to calibration",
                    evidence_class="PRODUCTION",
                )
            elif demand_receipt.standing == "SYNTHETIC_ENGINEERING_CANDIDATE":
                demand_stage = JourneyStageStatus(
                    stage_id="demand",
                    standing="SOFTWARE_VALID",
                    upstream_fingerprint=demand_result.fingerprint(),
                    receipt_fingerprint=demand_receipt.fingerprint(),
                    blocker_code="DEMAND_SYNTHETIC_ONLY",
                    blocker_message="Demand is synthetic — software-valid, not accepted",
                    owner_action="Demand is AVAILABLE for synthetic; provide observed demand",
                    evidence_class="SYNTHETIC_ENGINEERING",
                )
            else:
                demand_stage = JourneyStageStatus(
                    stage_id="demand",
                    standing="SOFTWARE_VALID",
                    upstream_fingerprint=demand_result.fingerprint(),
                    receipt_fingerprint=demand_receipt.fingerprint(),
                    blocker_code="DEMAND_NOT_ACCEPTED",
                    blocker_message="Demand not scientifically accepted",
                    owner_action="Demand is software-valid — request acceptance",
                    evidence_class="DESIGN_ONLY",
                )
        else:
            if demand_result.standing == "PROVIDER_DATA_REQUIRED":
                demand_stage = JourneyStageStatus(
                    stage_id="demand",
                    standing="PROVIDER_DATA_REQUIRED",
                    upstream_fingerprint=demand_result.fingerprint(),
                    blocker_code="PROVIDER_DATA_REQUIRED",
                    blocker_message="Demand requires provider data",
                    owner_action="Provide admitted DfT counts and accepted map matches",
                    evidence_class="PROVIDER_DATA_REQUIRED",
                )
            elif demand_result.software_standing == "SOFTWARE_VALID":
                demand_stage = JourneyStageStatus(
                    stage_id="demand",
                    standing="SOFTWARE_VALID",
                    upstream_fingerprint=demand_result.fingerprint(),
                    blocker_code="DEMAND_DECISION_PENDING",
                    blocker_message="Demand is software-valid but not yet accepted",
                    owner_action="Request attributable acceptance for this fingerprint",
                    evidence_class="SYNTHETIC_ENGINEERING"
                    if demand_result.standing == "SYNTHETIC_ENGINEERING_CANDIDATE"
                    else "DESIGN_ONLY",
                )
            else:
                demand_stage = JourneyStageStatus(
                    stage_id="demand",
                    standing="BLOCKED",
                    upstream_fingerprint=demand_result.fingerprint(),
                    blocker_code="DEMAND_BLOCKED",
                    blocker_message="Demand construction is blocked",
                    owner_action="Review demand construction inputs and prerequisites",
                    evidence_class="DESIGN_ONLY",
                )

    earlier_blocked_for_cal = earlier_blocked or demand_stage.standing in {
        "BLOCKED",
        "PROVIDER_DATA_REQUIRED",
        "UNAVAILABLE",
    }
    if calibration_result is None and calibration_decision is None and calibration_receipt is None:
        cal_stage = JourneyStageStatus(
            stage_id="calibration",
            standing="UNAVAILABLE",
            blocker_code="CALIBRATION_MISSING",
            blocker_message="No calibration decision or receipt is available",
            owner_action="Run calibration workflow and obtain attributable decision",
            evidence_class="DESIGN_ONLY",
        )
    elif earlier_blocked_for_cal:
        fp = None
        if calibration_result is not None:
            fp = calibration_result.evaluation_fingerprint
        elif calibration_decision is not None:
            fp = calibration_decision.fingerprint()
        elif calibration_receipt is not None:
            fp = calibration_receipt.fingerprint()
        cal_stage = JourneyStageStatus(
            stage_id="calibration",
            standing="BLOCKED",
            upstream_fingerprint=fp,
            blocker_code="EARLIER_STAGE_BLOCKED",
            blocker_message=(
                "Earlier stage blocked — cannot advance calibration; convergence not realism"
            ),
            owner_action=("Resolve earlier blocker; convergence does not imply realism"),
            evidence_class="DESIGN_ONLY",
        )
    elif calibration_receipt is not None or calibration_decision is not None:
        if calibration_result is None:
            raise ManchesterJourneyError(
                "JOURNEY_CALIBRATION_RESULT_MISSING",
                "calibration receipt/decision without exact result is insufficient — blocked",
            )
        if calibration_decision is None:
            raise ManchesterJourneyError(
                "JOURNEY_CALIBRATION_DECISION_MISSING",
                "calibration receipt without exact decision is insufficient — blocked",
            )
        if calibration_receipt is None:
            cal_stage = JourneyStageStatus(
                stage_id="calibration",
                standing="BLOCKED",
                upstream_fingerprint=calibration_decision.fingerprint(),
                blocker_code="CALIBRATION_RECEIPT_MISSING",
                blocker_message="ACCEPTED decision alone insufficient; receipt and result required",
                owner_action="Issue attributable receipt with exact workflow result",
                evidence_class="DESIGN_ONLY",
            )
        else:
            try:
                verify_acceptance_receipt(
                    calibration_receipt,
                    calibration_decision,
                    calibration_result,
                )
            except ManchesterCalibrationWorkflowError as exc:
                raise ManchesterJourneyError(
                    "JOURNEY_CALIBRATION_VERIFICATION_FAILED",
                    _sanitize(str(exc)),
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise ManchesterJourneyError(
                    "JOURNEY_CALIBRATION_VERIFICATION_FAILED",
                    _sanitize(str(exc)),
                ) from exc
            if calibration_decision.decision == "ACCEPTED":
                cal_stage = JourneyStageStatus(
                    stage_id="calibration",
                    standing="SCIENTIFICALLY_ACCEPTED_BASELINE",
                    upstream_fingerprint=calibration_decision.fingerprint(),
                    receipt_fingerprint=calibration_receipt.fingerprint(),
                    owner_action="Calibration accepted — proceed to SUMO execution",
                    evidence_class="PRODUCTION",
                )
            else:
                cal_stage = JourneyStageStatus(
                    stage_id="calibration",
                    standing="BLOCKED",
                    upstream_fingerprint=calibration_decision.fingerprint(),
                    receipt_fingerprint=calibration_receipt.fingerprint(),
                    blocker_code="CALIBRATION_NOT_ACCEPTED",
                    blocker_message=f"Calibration decision is {calibration_decision.decision!r}",
                    owner_action="Calibration not accepted — convergence does not imply realism",
                    evidence_class="DESIGN_ONLY",
                )
    else:
        cal_stage = JourneyStageStatus(
            stage_id="calibration",
            standing="UNAVAILABLE",
            blocker_code="CALIBRATION_MISSING",
            blocker_message="No calibration artifacts are available",
            owner_action="Run calibration workflow",
            evidence_class="DESIGN_ONLY",
        )

    earlier_blocked_for_sumo = earlier_blocked_for_cal or cal_stage.standing in {
        "BLOCKED",
        "PROVIDER_DATA_REQUIRED",
        "UNAVAILABLE",
    }
    # SUMO execution
    sumo_stage: JourneyStageStatus
    if sumo_receipt is None and sumo_request is None:
        sumo_stage = JourneyStageStatus(
            stage_id="sumo_execution",
            standing="UNAVAILABLE",
            blocker_code="SUMO_EXECUTION_MISSING",
            blocker_message="No SUMO execution request or receipt is available",
            owner_action="Submit operator-confirmed SUMO request via narrow Lane 01 contract",
            evidence_class="DESIGN_ONLY",
        )
    elif sumo_receipt is not None:
        _revalidate_strict(sumo_receipt)
        if sumo_request is not None:
            _revalidate_strict(sumo_request)
            if sumo_receipt.request_fingerprint != sumo_request.fingerprint():
                raise ManchesterJourneyError(
                    "JOURNEY_IDENTITY_DRIFT",
                    "SUMO receipt does not bind the submitted request",
                )
            # Valid binding
            if sumo_receipt.outcome == "completed":
                sumo_stage = JourneyStageStatus(
                    stage_id="sumo_execution",
                    standing="SOFTWARE_VALID",
                    upstream_fingerprint=sumo_receipt.fingerprint(),
                    receipt_fingerprint=sumo_receipt.fingerprint(),
                    owner_action="SUMO completed — software-valid, not scientifically validated",
                    evidence_class="SYNTHETIC_ENGINEERING",
                )
            elif sumo_receipt.outcome == "blocked":
                sumo_stage = JourneyStageStatus(
                    stage_id="sumo_execution",
                    standing="BLOCKED",
                    upstream_fingerprint=sumo_receipt.fingerprint(),
                    blocker_code="SUMO_BLOCKED",
                    blocker_message="SUMO execution was blocked — check preflight",
                    owner_action="Review SUMO preflight and resolve blocked inputs",
                    evidence_class="DESIGN_ONLY",
                )
            else:
                sumo_stage = JourneyStageStatus(
                    stage_id="sumo_execution",
                    standing="BLOCKED",
                    upstream_fingerprint=sumo_receipt.fingerprint(),
                    blocker_code="SUMO_FAILED",
                    blocker_message=f"SUMO outcome is {sumo_receipt.outcome!r}",
                    owner_action="Review SUMO logs and retry with operator confirmation",
                    evidence_class="DESIGN_ONLY",
                )
        else:
            # Receipt without request
            if sumo_receipt.outcome == "completed":
                sumo_stage = JourneyStageStatus(
                    stage_id="sumo_execution",
                    standing="BLOCKED",
                    upstream_fingerprint=sumo_receipt.fingerprint(),
                    blocker_code="SUMO_REQUEST_MISSING",
                    blocker_message="Completed receipt without exact request cannot be valid",
                    owner_action="Provide the exact request that produced this receipt",
                    evidence_class="DESIGN_ONLY",
                )
            elif sumo_receipt.outcome == "blocked":
                sumo_stage = JourneyStageStatus(
                    stage_id="sumo_execution",
                    standing="BLOCKED",
                    upstream_fingerprint=sumo_receipt.fingerprint(),
                    blocker_code="SUMO_BLOCKED",
                    blocker_message="SUMO execution was blocked",
                    owner_action="Review SUMO preflight",
                    evidence_class="DESIGN_ONLY",
                )
            else:
                sumo_stage = JourneyStageStatus(
                    stage_id="sumo_execution",
                    standing="BLOCKED",
                    upstream_fingerprint=sumo_receipt.fingerprint(),
                    blocker_code="SUMO_FAILED",
                    blocker_message=f"SUMO outcome is {sumo_receipt.outcome!r}",
                    owner_action="Review SUMO logs",
                    evidence_class="DESIGN_ONLY",
                )
    else:
        assert sumo_request is not None
        if earlier_blocked_for_sumo:
            sumo_stage = JourneyStageStatus(
                stage_id="sumo_execution",
                standing="BLOCKED",
                upstream_fingerprint=sumo_request.fingerprint(),
                blocker_code="EARLIER_STAGE_BLOCKED",
                blocker_message="Earlier stage blocked — cannot advance SUMO",
                owner_action="Resolve earlier blocker before SUMO execution",
                evidence_class="DESIGN_ONLY",
            )
        else:
            sumo_stage = JourneyStageStatus(
                stage_id="sumo_execution",
                standing="AVAILABLE",
                upstream_fingerprint=sumo_request.fingerprint(),
                owner_action="SUMO request pending — operator confirmation required",
                evidence_class="SYNTHETIC_ENGINEERING",
            )

    if output_package is None:
        output_stage = JourneyStageStatus(
            stage_id="output_import",
            standing="UNAVAILABLE",
            blocker_code="OUTPUT_MISSING",
            blocker_message="No SUMO output package has been imported",
            owner_action="Import controlled SUMO outputs via bounded pipeline",
            evidence_class="DESIGN_ONLY",
        )
    else:
        if not source_provider_available:
            # Synthetic design may still import outputs when provider absent.
            if (
                output_receipt is not None
                and output_receipt.package_fingerprint != output_package.package_fingerprint
            ):
                raise ManchesterJourneyError(
                    "JOURNEY_IDENTITY_DRIFT",
                    "output receipt does not bind the imported package",
                )
            output_stage = JourneyStageStatus(
                stage_id="output_import",
                standing="SOFTWARE_VALID",
                upstream_fingerprint=output_package.package_fingerprint,
                receipt_fingerprint=output_receipt.fingerprint() if output_receipt else None,
                owner_action="Output imported — synthetic simulated evidence",
                evidence_class="SYNTHETIC_ENGINEERING",
            )
        elif earlier_blocked_for_sumo or sumo_stage.standing in {
            "BLOCKED",
            "UNAVAILABLE",
        }:
            output_stage = JourneyStageStatus(
                stage_id="output_import",
                standing="BLOCKED",
                upstream_fingerprint=output_package.package_fingerprint,
                blocker_code="EARLIER_STAGE_BLOCKED",
                blocker_message="Earlier SUMO stage blocked — output cannot be valid",
                owner_action="Resolve earlier blocker before importing outputs",
                evidence_class="DESIGN_ONLY",
            )
        else:
            if (
                output_receipt is not None
                and output_receipt.package_fingerprint != output_package.package_fingerprint
            ):
                raise ManchesterJourneyError(
                    "JOURNEY_IDENTITY_DRIFT",
                    "output receipt does not bind the imported package",
                )
            output_stage = JourneyStageStatus(
                stage_id="output_import",
                standing="SOFTWARE_VALID",
                upstream_fingerprint=output_package.package_fingerprint,
                receipt_fingerprint=output_receipt.fingerprint() if output_receipt else None,
                owner_action="Output imported — software-valid simulated evidence",
                evidence_class="SYNTHETIC_ENGINEERING",
            )

    if comparison_result is None:
        comp_stage = JourneyStageStatus(
            stage_id="comparison",
            standing="UNAVAILABLE",
            blocker_code="COMPARISON_MISSING",
            blocker_message="No compatible comparison has been produced",
            owner_action="Build comparison over aligned observed and simulated intervals",
            evidence_class="DESIGN_ONLY",
        )
    else:
        if earlier_blocked_for_sumo or output_stage.standing in {
            "BLOCKED",
            "UNAVAILABLE",
        }:
            comp_stage = JourneyStageStatus(
                stage_id="comparison",
                standing="BLOCKED",
                upstream_fingerprint=comparison_result.fingerprint(),
                blocker_code="EARLIER_STAGE_BLOCKED",
                blocker_message="Earlier stage blocked — comparison cannot be available",
                owner_action="Resolve earlier blocker before comparison",
                evidence_class="DESIGN_ONLY",
            )
        elif comparison_result.standing == "AVAILABLE":
            comp_stage = JourneyStageStatus(
                stage_id="comparison",
                standing="AVAILABLE",
                upstream_fingerprint=comparison_result.fingerprint(),
                owner_action="Comparison available — descriptive only, not calibration",
                evidence_class="PRODUCTION"
                if comparison_result.evidence_class == "PRODUCTION"
                else "SYNTHETIC_ENGINEERING",
            )
        else:
            comp_stage = JourneyStageStatus(
                stage_id="comparison",
                standing="BLOCKED",
                upstream_fingerprint=comparison_result.fingerprint(),
                blocker_code=comparison_result.blocker_code or "COMPARISON_BLOCKED",
                blocker_message=comparison_result.blocker_message
                or "Comparison is blocked or refused",
                owner_action="Resolve comparison blocker — incompatible values refused",
                evidence_class="DESIGN_ONLY",
            )

    if output_package is not None or comparison_result is not None:
        replay_fp = _sha256_hex(
            _canonical_json(
                {
                    "output": output_package.package_fingerprint if output_package else None,
                    "comparison": comparison_result.fingerprint() if comparison_result else None,
                }
            ).encode("utf-8")
        )
        replay_stage = JourneyStageStatus(
            stage_id="replay_provenance_report",
            standing="AVAILABLE",
            upstream_fingerprint=replay_fp,
            owner_action="Replay/provenance/report links are plain destinations",
            evidence_class="DESIGN_ONLY",
        )
    else:
        replay_stage = JourneyStageStatus(
            stage_id="replay_provenance_report",
            standing="UNAVAILABLE",
            blocker_code="LINKS_UNAVAILABLE",
            blocker_message="No output or comparison is available for links",
            owner_action="Complete output import or comparison to enable links",
            evidence_class="DESIGN_ONLY",
        )

    stages = (
        source_stage,
        baseline_stage,
        map_stage,
        demand_stage,
        cal_stage,
        sumo_stage,
        output_stage,
        comp_stage,
        replay_stage,
    )

    scientific_present = any(s.standing == "SCIENTIFICALLY_ACCEPTED_BASELINE" for s in stages)
    # Synthetic available when any synthetic artifact exists, even if provider required.
    synthetic_available = bool(
        output_package is not None
        or comparison_result is not None
        or sumo_stage.standing in {"SOFTWARE_VALID", "AVAILABLE"}
        or output_stage.standing == "SOFTWARE_VALID"
    )

    if not source_provider_available:
        if synthetic_available:
            overall: Literal[
                "PROVIDER_DATA_REQUIRED",
                "SOFTWARE_VALID_SYNTHETIC_AVAILABLE",
                "SCIENTIFICALLY_ACCEPTED_BASELINE",
                "BLOCKED",
                "INCOMPLETE",
            ] = "SOFTWARE_VALID_SYNTHETIC_AVAILABLE"
        else:
            overall = "PROVIDER_DATA_REQUIRED"
    elif scientific_present:
        if (
            baseline_stage.standing == "SCIENTIFICALLY_ACCEPTED_BASELINE"
            and cal_stage.standing == "SCIENTIFICALLY_ACCEPTED_BASELINE"
        ):
            overall = "SCIENTIFICALLY_ACCEPTED_BASELINE"
        else:
            overall = "INCOMPLETE"
    elif any(s.standing == "BLOCKED" for s in stages):
        overall = "BLOCKED"
    elif all(
        s.standing in {"AVAILABLE", "SOFTWARE_VALID", "SCIENTIFICALLY_ACCEPTED_BASELINE"}
        for s in stages
    ):
        overall = "SCIENTIFICALLY_ACCEPTED_BASELINE" if scientific_present else "INCOMPLETE"
    else:
        overall = "INCOMPLETE"

    if not source_provider_available and synthetic_available:
        overall = "SOFTWARE_VALID_SYNTHETIC_AVAILABLE"

    if not scientific_present and overall == "SCIENTIFICALLY_ACCEPTED_BASELINE":
        overall = "BLOCKED"

    tmp_journey = ManchesterClosedLoopJourney.model_construct(
        journey_id=journey_id,
        stages=stages,
        overall_standing=overall,
        synthetic_execution_available=synthetic_available,
        scientific_acceptance_present=scientific_present,
        journey_fingerprint="0" * 64,
    )
    fp = _journey_fingerprint(tmp_journey)
    return ManchesterClosedLoopJourney(
        journey_id=journey_id,
        stages=stages,
        overall_standing=overall,
        synthetic_execution_available=synthetic_available,
        scientific_acceptance_present=scientific_present,
        journey_fingerprint=fp,
    )


def request_sumo_execution(
    package_root: object,
    output_root: object,
    request: ClosedLoopExecutionRequest,
) -> ClosedLoopExecutionReceipt:
    """Narrow approved operator-confirmed SUMO execution."""
    request = ClosedLoopExecutionRequest.model_validate(
        json.loads(request.model_dump_json()),
        strict=True,
    )
    if request.confirmed_by_operator is not True:
        raise ManchesterJourneyError(
            "OPERATOR_AUTHORISATION_REQUIRED",
            "SUMO execution requires explicit operator confirmation",
        )
    for attr in (
        "executable",
        "argv",
        "shell",
        "cwd",
        "working_directory",
        "upload",
        "network",
        "url",
    ):
        if hasattr(request, attr) and attr not in {
            "confirmed_by_operator",
            "run_id",
            "package_fingerprint",
            "config_file",
            "inputs",
            "seed",
            "timeout_seconds",
            "deterministic_run_identity",
        }:
            raise ManchesterJourneyError(
                "ARBITRARY_FIELD_REFUSED",
                f"field {attr!r} is not part of the narrow contract",
            )

    from pathlib import Path as _Path

    if isinstance(package_root, str):
        _reject_private_path(package_root, "package_root")
        _reject_secret(package_root, "package_root")
        package_root = _Path(package_root)
    if isinstance(output_root, str):
        _reject_private_path(output_root, "output_root")
        _reject_secret(output_root, "output_root")
        output_root = _Path(output_root)

    raise ManchesterJourneyError(
        "SUMO_EXECUTION_REQUIRES_EXPLICIT_TOOL",
        "SUMO execution via journey requires explicit tool — "
        "call closed_loop_execution.run_closed_loop_execution directly",
    )


def verify_journey(
    journey: ManchesterClosedLoopJourney,
) -> ManchesterClosedLoopJourney:
    """Revalidate a journey at a public boundary."""

    return ManchesterClosedLoopJourney.model_validate(
        json.loads(journey.model_dump_json()),
        strict=True,
    )


__all__ = [
    "JOURNEY_CAPABILITY_ID",
    "JOURNEY_METHOD_VERSION",
    "JOURNEY_SCHEMA_VERSION",
    "LIMITATIONS",
    "JourneyStageStatus",
    "ManchesterClosedLoopJourney",
    "ManchesterJourneyError",
    "build_closed_loop_journey",
    "request_sumo_execution",
    "verify_journey",
]
