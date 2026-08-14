# ruff: noqa: E501, ANN401
"""Fail-closed source-bound admission for the E3 research package — Lane 10.

Exact admission of a future Lane 09 package fails closed today. The model and
admission natively represent evidence_state = NOT_EXECUTED and
result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE with
research_workloads_launched = 0. Admission requires the exact frozen
fingerprints plus an analysis artifact and package fingerprint that do not yet
exist, and therefore returns a typed truthful refusal (no exception, no partial
admission) for every current input. Rejects wrong identities, wrong fingerprint
types, tasks-as-N, queue/compute conflation, monetary cost language,
actor-selects-RSU or actual-Kubernetes claims, and any true _authorized
capability field.

Standing is never supervisor approved. Only LANE_09 holds.

Public API:
  admit_e3_research(package) -> E3ResearchAdmissionRefusal
  validate_e3_package_for_admission(package) -> list[str]
"""

from __future__ import annotations

import re
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from traffictwin.experiments.e3_research_evidence import (
    ACTOR_SHA256,
    APPROVED_CANDIDATE_SHA,
    CONTRACT_CHECKPOINT_SHA,
    CONTRACT_SHA256,
    E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED,
    LANE_09,
    MANIFEST_SIDECAR_SHA256,
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
    NOT_EXECUTED,
    RESEARCH_WORKLOADS_LAUNCHED,
    TRACE_SHA256,
    TRAFFICTWIN_PRODUCT_BASE_SHA,
    TRAFFICTWIN_RESEARCH_PROMOTION_SHA,
    VEC_ADAPTER_SHA,
    VEC_CORE_SHA,
    VEC_PROMOTION_SHA,
    E3ResearchEvidencePackage,
    _scan_forbidden_recursive,
)

STANDING_REFUSED: Final[Literal["E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"]] = (
    E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
)
EVIDENCE_STATE: Final[Literal["NOT_EXECUTED"]] = NOT_EXECUTED
RESULT_AVAILABILITY: Final[Literal["NO_E3_RESEARCH_RESULTS_AVAILABLE"]] = (
    NO_E3_RESEARCH_RESULTS_AVAILABLE
)
LANE_09_HOLD: Final[Literal["BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"]] = LANE_09
RESEARCH_WORKLOADS: Final[Literal[0]] = RESEARCH_WORKLOADS_LAUNCHED

# Expected package fingerprint does not yet exist — future Lane 09 package required.
# No current 64-hex value satisfies this; admission therefore always refuses.
EXPECTED_PACKAGE_FINGERPRINT: Final[None] = None
EXPECTED_ANALYSIS_ARTIFACT_FINGERPRINT: Final[None] = None

_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class E3ResearchAdmissionRefusal(StrictBase):
    """Typed truthful refusal — no exception, no partial admission."""

    status: Literal["REFUSED"] = Field(default="REFUSED")
    admitted: Literal[False] = Field(default=False)
    lane_09: Literal["BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"] = Field(default=LANE_09_HOLD)
    standing: Literal["E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"] = Field(default=STANDING_REFUSED)
    evidence_state: Literal["NOT_EXECUTED"] = Field(default=EVIDENCE_STATE)
    result_availability: Literal["NO_E3_RESEARCH_RESULTS_AVAILABLE"] = Field(
        default=RESULT_AVAILABILITY
    )
    research_workloads_launched: Literal[0] = Field(default=RESEARCH_WORKLOADS)
    campaign: Literal["e3-dynamic-resource-v2"] = Field(default="e3-dynamic-resource-v2")
    product_base_sha: str = Field(default=TRAFFICTWIN_PRODUCT_BASE_SHA)
    research_promotion_sha: str = Field(default=TRAFFICTWIN_RESEARCH_PROMOTION_SHA)
    approved_candidate_sha: str = Field(default=APPROVED_CANDIDATE_SHA)
    contract_checkpoint_sha: str = Field(default=CONTRACT_CHECKPOINT_SHA)
    vec_promotion_sha: str = Field(default=VEC_PROMOTION_SHA)
    vec_core_sha: str = Field(default=VEC_CORE_SHA)
    vec_adapter_sha: str = Field(default=VEC_ADAPTER_SHA)
    actor_sha256: str = Field(default=ACTOR_SHA256)
    trace_sha256: str = Field(default=TRACE_SHA256)
    contract_sha256: str = Field(default=CONTRACT_SHA256)
    manifest_sidecar_sha256: str = Field(default=MANIFEST_SIDECAR_SHA256)
    reason_code: str = Field(min_length=1, description="typed refusal code")
    reason_detail: str = Field(min_length=1, description="human-readable detail")
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    expected_package_fingerprint: None = Field(default=None)
    expected_analysis_artifact_fingerprint: None = Field(default=None)
    received_package_fingerprint: str | None = Field(default=None)
    received_analysis_artifact_fingerprint: str | None = Field(default=None)

    @field_validator(
        "product_base_sha",
        "research_promotion_sha",
        "approved_candidate_sha",
        "contract_checkpoint_sha",
        "vec_promotion_sha",
        "vec_core_sha",
        "vec_adapter_sha",
    )
    @classmethod
    def validate_hex40(cls, v: str) -> str:
        if not _HEX40_RE.match(v):
            raise ValueError(f"sha must be 40 hex, got {v!r}")
        return v

    @field_validator("actor_sha256", "trace_sha256", "contract_sha256", "manifest_sidecar_sha256")
    @classmethod
    def validate_hex64(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError(f"sha256 must be 64 hex, got {v!r}")
        return v


def _build_refusal(
    reason_code: str,
    reason_detail: str,
    diagnostics: dict[str, Any] | None = None,
    received_package_fingerprint: str | None = None,
    received_analysis_artifact_fingerprint: str | None = None,
) -> E3ResearchAdmissionRefusal:
    return E3ResearchAdmissionRefusal(
        status="REFUSED",
        admitted=False,
        lane_09=LANE_09_HOLD,
        standing=STANDING_REFUSED,
        evidence_state=EVIDENCE_STATE,
        result_availability=RESULT_AVAILABILITY,
        research_workloads_launched=RESEARCH_WORKLOADS,
        reason_code=reason_code,
        reason_detail=reason_detail,
        diagnostics=diagnostics or {},
        received_package_fingerprint=received_package_fingerprint,
        received_analysis_artifact_fingerprint=received_analysis_artifact_fingerprint,
    )


def validate_e3_package_for_admission(
    package: E3ResearchEvidencePackage | dict[str, Any] | None,
) -> list[str]:
    """Return list of refusal reasons without side effects (no exception).

    Empty list means package structure is not immediately rejected, but admission
    still requires the missing future artifact and fingerprint and will therefore
    return NOT_EXECUTED refusal.
    """
    if package is None:
        return [
            "missing_package: package is None, research_workloads_launched = 0, evidence_state = NOT_EXECUTED"
        ]

    # If dict, parse via model validation
    if isinstance(package, dict):
        try:
            parsed = E3ResearchEvidencePackage.model_validate(package)
            package = parsed
        except Exception as exc:
            return [f"invalid_package_structure: {exc}"]

    if not isinstance(package, E3ResearchEvidencePackage):
        return [
            f"invalid_package_type: expected E3ResearchEvidencePackage, got {type(package).__name__}"
        ]

    pkg: E3ResearchEvidencePackage = package
    errs: list[str] = []

    # Identity mismatches
    if pkg.product_base_sha != TRAFFICTWIN_PRODUCT_BASE_SHA:
        errs.append(
            f"identity_mismatch product_base_sha: expected {TRAFFICTWIN_PRODUCT_BASE_SHA} got {pkg.product_base_sha!r}"
        )
    if pkg.research_promotion_sha != TRAFFICTWIN_RESEARCH_PROMOTION_SHA:
        errs.append(
            f"identity_mismatch research_promotion_sha: expected {TRAFFICTWIN_RESEARCH_PROMOTION_SHA} got {pkg.research_promotion_sha!r}"
        )
    if pkg.approved_candidate_sha != APPROVED_CANDIDATE_SHA:
        errs.append(
            f"identity_mismatch approved_candidate_sha: expected {APPROVED_CANDIDATE_SHA} got {pkg.approved_candidate_sha!r}"
        )
    if pkg.contract_checkpoint_sha != CONTRACT_CHECKPOINT_SHA:
        errs.append(
            f"identity_mismatch contract_checkpoint_sha: expected {CONTRACT_CHECKPOINT_SHA} got {pkg.contract_checkpoint_sha!r}"
        )
    if pkg.vec_runtime.promotion_commit != VEC_PROMOTION_SHA:
        errs.append(
            f"identity_mismatch vec_promotion: expected {VEC_PROMOTION_SHA} got {pkg.vec_runtime.promotion_commit!r}"
        )
    if pkg.vec_runtime.core_candidate != VEC_CORE_SHA:
        errs.append(
            f"identity_mismatch vec_core: expected {VEC_CORE_SHA} got {pkg.vec_runtime.core_candidate!r}"
        )
    if pkg.vec_runtime.adapter_candidate != VEC_ADAPTER_SHA:
        errs.append(
            f"identity_mismatch vec_adapter: expected {VEC_ADAPTER_SHA} got {pkg.vec_runtime.adapter_candidate!r}"
        )
    if pkg.contract.sha256 != CONTRACT_SHA256:
        errs.append(
            f"identity_mismatch contract_sha256: expected {CONTRACT_SHA256} got {pkg.contract.sha256!r}"
        )
    if pkg.software_identity.actor_sha256 != ACTOR_SHA256:
        errs.append(
            f"identity_mismatch actor_sha256: expected {ACTOR_SHA256} got {pkg.software_identity.actor_sha256!r}"
        )
    if pkg.software_identity.trace_sha256 != TRACE_SHA256:
        errs.append(
            f"identity_mismatch trace_sha256: expected {TRACE_SHA256} got {pkg.software_identity.trace_sha256!r}"
        )

    # Fingerprint types (shape)
    for name, val, pattern in [
        ("product_base_sha", pkg.product_base_sha, _HEX40_RE),
        ("research_promotion_sha", pkg.research_promotion_sha, _HEX40_RE),
        ("actor_sha256", pkg.software_identity.actor_sha256, _HEX64_RE),
        ("trace_sha256", pkg.software_identity.trace_sha256, _HEX64_RE),
        ("contract_sha256", pkg.contract.sha256, _HEX64_RE),
    ]:
        if not pattern.match(val):
            errs.append(f"wrong_fingerprint_type {name}: must match {pattern.pattern}, got {val!r}")

    # Replication must be fleet_draw N=4, not tasks_as_N
    if pkg.replication.replication_unit != "fleet_draw":
        errs.append(
            f"forbidden_claim tasks_as_N: replication_unit must be fleet_draw, got {pkg.replication.replication_unit!r}"
        )
    if pkg.replication.n != 4:
        errs.append(f"forbidden_claim tasks_as_N: n must be 4, got {pkg.replication.n!r}")
    if tuple(pkg.replication.fleet_seeds) != (1, 2, 3, 4):
        errs.append(
            f"identity_mismatch fleet_seeds must be [1,2,3,4], got {pkg.replication.fleet_seeds!r}"
        )

    # Hold state must be NOT_EXECUTED
    if pkg.evidence_state != NOT_EXECUTED:
        errs.append(
            f"hold_mismatch evidence_state must be {NOT_EXECUTED}, got {pkg.evidence_state!r}"
        )
    if pkg.result_availability != NO_E3_RESEARCH_RESULTS_AVAILABLE:
        errs.append(
            f"hold_mismatch result_availability must be {NO_E3_RESEARCH_RESULTS_AVAILABLE}, got {pkg.result_availability!r}"
        )
    if pkg.research_workloads_launched != 0:
        errs.append(
            f"hold_mismatch research_workloads_launched must be 0, got {pkg.research_workloads_launched!r}"
        )
    if pkg.lane_09 != LANE_09:
        errs.append(f"hold_mismatch lane_09 must be {LANE_09}, got {pkg.lane_09!r}")
    if pkg.status != E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED:
        errs.append(
            f"hold_mismatch status must be {E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, got {pkg.status!r}"
        )

    # Queue/compute conflation, monetary cost, actor-selects, kubernetes, tasks_as_n, supervisor
    scan = _scan_forbidden_recursive(pkg.model_dump(mode="json"))
    if scan:
        for entry in scan:
            errs.append(f"forbidden_claim: {entry}")

    # Deprecated: we already check _authorized via scan, but double-count for diagnostics
    # The scan already covers true _authorized.

    return errs


def admit_e3_research(
    package: E3ResearchEvidencePackage | dict[str, Any] | None,
    *,
    analysis_artifact_fingerprint: str | None = None,
    package_fingerprint: str | None = None,
) -> E3ResearchAdmissionRefusal:
    """Admit an E3 research package — fail-closed today, typed refusal always.

    For every current input this returns an E3ResearchAdmissionRefusal with
    admitted=False, evidence_state=NOT_EXECUTED,
    result_availability=NO_E3_RESEARCH_RESULTS_AVAILABLE,
    research_workloads_launched=0, lane_09=BLOCKED_BY_RESEARCHER_EXECUTION_HOLD,
    standing=E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED and a typed reason_code.
    No exception is raised for invalid package content; diagnostics explain why.
    A future Lane 09 package with the exact frozen fingerprints plus a valid
    analysis artifact and package fingerprint would be required for admission,
    but such artifacts do not exist today.
    """
    # First, collect immediate package diagnostics (no exception)
    diagnostics: dict[str, Any] = {}
    package_pre_errors = validate_e3_package_for_admission(package)

    # Fingerprint type checks for provided fingerprints if any
    received_pkg_fp = (
        package_fingerprint.strip().lower() if isinstance(package_fingerprint, str) else None
    )
    received_analysis_fp = (
        analysis_artifact_fingerprint.strip().lower()
        if isinstance(analysis_artifact_fingerprint, str)
        else None
    )

    fingerprint_errors: list[str] = []
    if package_fingerprint is not None:
        if not isinstance(package_fingerprint, str):
            fingerprint_errors.append(
                f"wrong_fingerprint_type package_fingerprint must be str, got {type(package_fingerprint).__name__}"
            )
        elif not _HEX64_RE.fullmatch(package_fingerprint.strip().lower()):
            fingerprint_errors.append(
                f"wrong_fingerprint_type package_fingerprint must be 64 hex, got {package_fingerprint!r}"
            )
    if analysis_artifact_fingerprint is not None:
        if not isinstance(analysis_artifact_fingerprint, str):
            fingerprint_errors.append(
                f"wrong_fingerprint_type analysis_artifact_fingerprint must be str, got {type(analysis_artifact_fingerprint).__name__}"
            )
        elif not _HEX64_RE.fullmatch(analysis_artifact_fingerprint.strip().lower()):
            fingerprint_errors.append(
                f"wrong_fingerprint_type analysis_artifact_fingerprint must be 64 hex, got {analysis_artifact_fingerprint!r}"
            )

    # Priority: missing package is already in pre_errors
    # Next: fingerprint type mismatches are typed refusal, not exception
    if fingerprint_errors:
        diagnostics["fingerprint_errors"] = fingerprint_errors
        diagnostics["package_pre_errors"] = package_pre_errors
        return _build_refusal(
            reason_code="REFUSED_WRONG_FINGERPRINT_TYPE",
            reason_detail="; ".join(fingerprint_errors)
            + "; expected 64 hex for SHA256 fingerprints; no_current_package_satisfies",
            diagnostics=diagnostics,
            received_package_fingerprint=received_pkg_fp,
            received_analysis_artifact_fingerprint=received_analysis_fp,
        )

    if package_pre_errors:
        # Choose most informative code
        first = package_pre_errors[0]
        if "identity_mismatch" in first:
            code = "REFUSED_IDENTITY_MISMATCH"
        elif "wrong_fingerprint_type" in first:
            code = "REFUSED_WRONG_FINGERPRINT_TYPE"
        elif "forbidden_claim" in first or "forbidden" in first.lower():
            code = "REFUSED_FORBIDDEN_CLAIM"
        elif "missing_package" in first:
            code = "REFUSED_MISSING_PACKAGE"
        elif "hold_mismatch" in first:
            code = "REFUSED_HOLD_MISMATCH"
        else:
            code = "REFUSED_PACKAGE_INVALID"
        diagnostics["package_pre_errors"] = package_pre_errors
        return _build_refusal(
            reason_code=code,
            reason_detail="; ".join(package_pre_errors)[:2000],
            diagnostics=diagnostics,
            received_package_fingerprint=received_pkg_fp,
            received_analysis_artifact_fingerprint=received_analysis_fp,
        )

    # Even if package is perfect, admission requires future artifacts that do not exist.
    # The expected fingerprints are None (dormant). No provided fingerprints satisfy today.
    if EXPECTED_PACKAGE_FINGERPRINT is None or EXPECTED_ANALYSIS_ARTIFACT_FINGERPRINT is None:
        diagnostics["package_pre_errors"] = package_pre_errors
        diagnostics["expected_missing"] = {
            "expected_package_fingerprint": EXPECTED_PACKAGE_FINGERPRINT,
            "expected_analysis_artifact_fingerprint": EXPECTED_ANALYSIS_ARTIFACT_FINGERPRINT,
        }
        # Also check provided fingerprints are either missing or mismatch
        if received_pkg_fp is None or received_analysis_fp is None:
            return _build_refusal(
                reason_code="REFUSED_MISSING_FUTURE_ARTIFACT",
                reason_detail=(
                    f"NO_E3_RESEARCH_RESULTS_AVAILABLE: research_workloads_launched = 0, "
                    f"evidence_state = {NOT_EXECUTED}, {E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, "
                    f"{LANE_09}. Admission requires an analysis artifact and package fingerprint "
                    "that do not yet exist (future Lane 09 package). No current input satisfies."
                ),
                diagnostics=diagnostics,
                received_package_fingerprint=received_pkg_fp,
                received_analysis_artifact_fingerprint=received_analysis_fp,
            )
        # Provided fingerprints but expected is None → still mismatch
        return _build_refusal(
            reason_code="REFUSED_FUTURE_ARTIFACT_MISMATCH",
            reason_detail=(
                f"NO_E3_RESEARCH_RESULTS_AVAILABLE: provided fingerprints {received_pkg_fp!r}, "
                f"{received_analysis_fp!r} do not match any future Lane 09 expected artifact; "
                f"hold {LANE_09} blocks admission"
            ),
            diagnostics=diagnostics,
            received_package_fingerprint=received_pkg_fp,
            received_analysis_artifact_fingerprint=received_analysis_fp,
        )

    # This branch is unreachable today because expected fingerprints are None,
    # but keep for future completeness: exact comparison would happen here.
    # If we ever had expected fingerprints, we would compare:
    # if received_pkg_fp != EXPECTED_PACKAGE_FINGERPRINT.lower() -> refused mismatch
    # etc., and only on exact match would we return an admitted receipt.
    # Since we never admit today, we refuse:
    diagnostics["unreachable"] = True
    return _build_refusal(
        reason_code="REFUSED_NOT_EXECUTED",
        reason_detail=(
            f"evidence_state = {NOT_EXECUTED}, result_availability = {NO_E3_RESEARCH_RESULTS_AVAILABLE}, "
            f"{E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, {LANE_09}"
        ),
        diagnostics=diagnostics,
        received_package_fingerprint=received_pkg_fp,
        received_analysis_artifact_fingerprint=received_analysis_fp,
    )


__all__ = [
    "E3ResearchAdmissionRefusal",
    "admit_e3_research",
    "validate_e3_package_for_admission",
    "EXPECTED_PACKAGE_FINGERPRINT",
    "EXPECTED_ANALYSIS_ARTIFACT_FINGERPRINT",
    "LANE_09_HOLD",
    "STANDING_REFUSED",
    "EVIDENCE_STATE",
    "RESULT_AVAILABILITY",
    "RESEARCH_WORKLOADS",
]
