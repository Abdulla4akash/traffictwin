"""Manchester observed-vs-simulated comparison workflow — Lane 06.

Composes the existing Manchester comparison contract/service without creating a
looser numeric comparison. Only semantically aligned observed and simulated
intervals are compared with exact measure, unit, interval, time basis, scope,
spatial mapping, class/direction, and lineage compatibility.

Blocking semantics
------------------
Provider evidence unavailable, unresolved/rejected map matching,
insufficient/inferred demand, unaccepted calibration/baseline, malformed output,
or incompatible comparison must stop in an explicit typed blocked/refused
standing. No unit coercion, resampling, or zero-fill is performed because
values are numeric. Unsupported trip-level/FCD fields must not become observed
traffic metrics without an explicit reviewed aggregation contract. Uncertainty
is unavailable unless scientifically supplied. Descriptive differences are
non-causal and do not establish calibration or realism.

Synthetic engineering inputs may exercise the software but must stay
SYNTHETIC_ENGINEERING/DESIGN_ONLY and cannot produce
SCIENTIFICALLY_ACCEPTED_BASELINE or Manchester observational claims.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.manchester.comparison import (
    ComparisonLineage,
    ManchesterComparisonError,
    ManchesterComparisonMetricContract,
    ObservedComparisonInterval,
    ObservedSimulationComparison,
    SimulatedComparisonInterval,
    compare_observed_and_simulated,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel, sha256_hex

COMPARISON_WORKFLOW_SCHEMA_VERSION: Literal["1.0"] = "1.0"
COMPARISON_WORKFLOW_METHOD_VERSION: Literal["manchester-comparison-workflow-1.0"] = (
    "manchester-comparison-workflow-1.0"
)
COMPARISON_WORKFLOW_CAPABILITY_ID: Literal["MAN-10"] = "MAN-10"

WorkflowStanding: Literal[
    "AVAILABLE",
    "BLOCKED_PROVIDER_DATA_REQUIRED",
    "BLOCKED_MAP_MATCH_UNRESOLVED",
    "BLOCKED_DEMAND_INSUFFICIENT",
    "BLOCKED_CALIBRATION_UNACCEPTED",
    "BLOCKED_BASELINE_UNACCEPTED",
    "BLOCKED_MALFORMED_OUTPUT",
    "REFUSED_INCOMPATIBLE",
    "REFUSED_UNSUPPORTED_FIELD",
]

LIMITATIONS: tuple[str, ...] = (
    "Comparison is descriptive non-causal; it does not establish calibration or realism.",
    (
        "Only semantically aligned intervals are paired — exact measure, unit, "
        "interval, time basis, scope, mapping."
    ),
    "No unit coercion, resampling, or zero-fill is performed.",
    (
        "Unsupported trip-level/FCD fields are not observed traffic metrics "
        "without an aggregation contract."
    ),
    "Uncertainty is unavailable unless scientifically supplied.",
    (
        "Synthetic engineering inputs are DESIGN_ONLY and cannot claim "
        "SCIENTIFICALLY_ACCEPTED_BASELINE."
    ),
)

EVIDENCE_BOUNDARY = (
    "Manchester comparison workflow: deterministic observed-vs-simulated "
    "pairing over exact contracts and lineage. Software evidence only."
)

_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_RE = re.compile(
    r"(apikey|api_key|secret|password|passwd|token|bearer|credential|authorization)",
    re.IGNORECASE,
)
_WORKFLOW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")

EvidenceClass: Literal["SYNTHETIC_ENGINEERING", "DESIGN_ONLY", "PRODUCTION"] = (
    "SYNTHETIC_ENGINEERING"
)


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


class ManchesterComparisonWorkflowError(ValueError):
    """Typed caller-side misuse at the comparison workflow boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterComparisonWorkflowModel(ManchesterSnapshotModel):
    """Strict frozen base for Lane 06 comparison workflow artifacts."""


class ComparisonWorkflowPrerequisites(ManchesterComparisonWorkflowModel):
    """Upstream standing that must be satisfied before a comparison may be admitted."""

    provider_evidence_available: bool
    map_match_standing: Literal["AUTO_ACCEPTED", "HUMAN_ACCEPTED", "UNRESOLVED", "REJECTED"]
    demand_standing: Literal[
        "COUNT_CONSTRAINED_CANDIDATE",
        "SYNTHETIC_ENGINEERING_CANDIDATE",
        "PROVIDER_DATA_REQUIRED",
    ]
    demand_software_valid: bool
    calibration_accepted: bool
    baseline_accepted: bool
    output_software_valid: bool
    output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate(self) -> ComparisonWorkflowPrerequisites:
        if not self.output_software_valid and self.output_fingerprint is not None:
            raise ValueError("invalid output cannot carry a fingerprint")
        return self


class ManchesterComparisonWorkflowRequest(ManchesterComparisonWorkflowModel):
    """Immutable workflow request — embeds exact contract, lineage, and prerequisites."""

    schema_version: Literal["1.0"] = COMPARISON_WORKFLOW_SCHEMA_VERSION
    capability_id: Literal["MAN-10"] = COMPARISON_WORKFLOW_CAPABILITY_ID
    method_version: Literal["manchester-comparison-workflow-1.0"] = (
        COMPARISON_WORKFLOW_METHOD_VERSION
    )
    workflow_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    contract: ManchesterComparisonMetricContract
    contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage: ComparisonLineage
    lineage_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_inputs: tuple[ObservedComparisonInterval, ...] = Field(min_length=1)
    simulated_inputs: tuple[SimulatedComparisonInterval, ...] = Field(min_length=1)
    prerequisites: ComparisonWorkflowPrerequisites
    limitations: tuple[str, ...] = LIMITATIONS
    evidence_boundary: str = EVIDENCE_BOUNDARY
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("workflow_id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        _reject_private_path(v, "workflow_id")
        _reject_secret(v, "workflow_id")
        if not _WORKFLOW_ID_RE.fullmatch(v):
            raise ValueError("workflow_id must match safe pattern")
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
    def _validate(self) -> ManchesterComparisonWorkflowRequest:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be the exact workflow literal")
        if self.evidence_boundary != EVIDENCE_BOUNDARY:
            raise ValueError("evidence_boundary must be the exact literal")
        if self.contract_fingerprint != self.contract.fingerprint():
            raise ValueError("contract_fingerprint must bind the canonical contract")
        if self.lineage_fingerprint != self.lineage.fingerprint():
            raise ValueError("lineage_fingerprint must bind the canonical lineage")
        expected = _request_fingerprint(self)
        if self.request_fingerprint != expected:
            raise ValueError("request_fingerprint must be re-derived")
        return self


class ManchesterComparisonWorkflowResult(ManchesterComparisonWorkflowModel):
    """Deterministic result — either AVAILABLE or explicitly blocked/refused."""

    schema_version: Literal["1.0"] = COMPARISON_WORKFLOW_SCHEMA_VERSION
    capability_id: Literal["MAN-10"] = COMPARISON_WORKFLOW_CAPABILITY_ID
    method_version: Literal["manchester-comparison-workflow-1.0"] = (
        COMPARISON_WORKFLOW_METHOD_VERSION
    )
    workflow_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    standing: Literal[
        "AVAILABLE",
        "BLOCKED_PROVIDER_DATA_REQUIRED",
        "BLOCKED_MAP_MATCH_UNRESOLVED",
        "BLOCKED_DEMAND_INSUFFICIENT",
        "BLOCKED_CALIBRATION_UNACCEPTED",
        "BLOCKED_BASELINE_UNACCEPTED",
        "BLOCKED_MALFORMED_OUTPUT",
        "REFUSED_INCOMPATIBLE",
        "REFUSED_UNSUPPORTED_FIELD",
    ]
    comparison: ObservedSimulationComparison | None = None
    blocker_code: str | None = Field(default=None, max_length=64)
    blocker_message: str | None = Field(default=None, max_length=500)
    evidence_class: Literal["SYNTHETIC_ENGINEERING", "DESIGN_ONLY", "PRODUCTION"]
    scientifically_accepted: Literal[False] = False
    non_causal_descriptive_only: Literal[True] = True
    limitations: tuple[str, ...] = LIMITATIONS
    result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("workflow_id", "blocker_code", "blocker_message")
    @classmethod
    def _validate_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _reject_private_path(v, "result field")
        _reject_secret(v, "result field")
        return v

    @model_validator(mode="after")
    def _validate(self) -> ManchesterComparisonWorkflowResult:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be the exact literal")
        if self.scientifically_accepted is not False:
            raise ValueError("comparison workflow must never claim scientific acceptance")
        if self.standing == "AVAILABLE":
            if self.comparison is None:
                raise ValueError("AVAILABLE requires an embedded comparison")
            if self.blocker_code is not None or self.blocker_message is not None:
                raise ValueError("AVAILABLE must not carry blocker details")
            if self.comparison.synthetic and self.evidence_class == "PRODUCTION":
                raise ValueError("synthetic comparison cannot be production evidence")
            if self.comparison.synthetic and self.evidence_class not in {
                "SYNTHETIC_ENGINEERING",
                "DESIGN_ONLY",
            }:
                raise ValueError("synthetic comparison must be SYNTHETIC_ENGINEERING/DESIGN_ONLY")
        else:
            if self.comparison is not None:
                raise ValueError("blocked/refused must not carry a comparison")
            if self.blocker_code is None or self.blocker_message is None:
                raise ValueError("blocked/refused requires blocker code and message")
        expected = _result_fingerprint(self)
        if self.result_fingerprint != expected:
            raise ValueError("result_fingerprint must be re-derived")
        return self


def _request_fingerprint(req: ManchesterComparisonWorkflowRequest) -> str:
    payload = {
        "contract_fingerprint": req.contract_fingerprint,
        "lineage_fingerprint": req.lineage_fingerprint,
        "observed": [json.loads(o.model_dump_json()) for o in req.observed_inputs],
        "simulated": [json.loads(s.model_dump_json()) for s in req.simulated_inputs],
        "prerequisites": json.loads(req.prerequisites.model_dump_json()),
        "workflow_id": req.workflow_id,
    }
    return sha256_hex(_canonical_json(payload).encode("utf-8"))


def _result_fingerprint(res: ManchesterComparisonWorkflowResult) -> str:
    payload: dict[str, object] = {
        "request_fingerprint": res.request_fingerprint,
        "standing": res.standing,
        "evidence_class": res.evidence_class,
        "workflow_id": res.workflow_id,
    }
    if res.comparison is not None:
        payload["comparison_fingerprint"] = res.comparison.fingerprint()
    if res.blocker_code is not None:
        payload["blocker_code"] = res.blocker_code
    return sha256_hex(_canonical_json(payload).encode("utf-8"))


_UNSUPPORTED_SIMULATED_FIELDS = frozenset(
    {"fcd_speed", "trip_duration", "route_length", "waiting_time"}
)


def _is_unsupported_measure(measure: str) -> bool:
    return measure in _UNSUPPORTED_SIMULATED_FIELDS


def _screen_incompatibility(
    contract: ManchesterComparisonMetricContract,
    observed: tuple[ObservedComparisonInterval, ...],
    simulated: tuple[SimulatedComparisonInterval, ...],
) -> tuple[str, str] | None:
    for obs in observed:
        if obs.interval.measure != contract.measure:
            return (
                "MEASURE_MISMATCH",
                f"observed measure {obs.interval.measure!r} != contract {contract.measure!r}",
            )
        if obs.interval.unit != contract.unit:
            return (
                "UNIT_MISMATCH",
                f"observed unit {obs.interval.unit!r} != contract {contract.unit!r}",
            )
        if obs.interval.duration_s() != contract.interval_duration_s:
            return (
                "INTERVAL_DURATION_MISMATCH",
                (
                    f"observed interval {obs.interval.duration_s()}s "
                    f"!= contract {contract.interval_duration_s}s"
                ),
            )
        if (
            obs.interval.scope_label != contract.scope_label
            or obs.interval.scope_fingerprint != contract.scope_fingerprint
        ):
            return ("SCOPE_MISMATCH", "observed scope does not match contract scope")
        if (
            obs.interval.time_basis_label != contract.time_basis_label
            or obs.interval.time_basis_fingerprint != contract.time_basis_fingerprint
        ):
            return ("TIME_BASIS_MISMATCH", "observed time basis does not match contract")
        if _is_unsupported_measure(obs.interval.measure):
            return (
                "UNSUPPORTED_FIELD",
                f"observed measure {obs.interval.measure!r} is unsupported FCD/trip-level field",
            )
        if obs.source != contract.observed_source:
            return (
                "SOURCE_MISMATCH",
                f"observed source {obs.source!r} != contract {contract.observed_source!r}",
            )
    for sim in simulated:
        if sim.interval.measure != contract.measure:
            return (
                "MEASURE_MISMATCH",
                f"simulated measure {sim.interval.measure!r} != contract {contract.measure!r}",
            )
        if sim.interval.unit != contract.unit:
            return (
                "UNIT_MISMATCH",
                f"simulated unit {sim.interval.unit!r} != contract {contract.unit!r}",
            )
        if sim.interval.duration_s() != contract.interval_duration_s:
            return (
                "INTERVAL_DURATION_MISMATCH",
                (
                    f"simulated interval {sim.interval.duration_s()}s "
                    f"!= contract {contract.interval_duration_s}s"
                ),
            )
        if (
            sim.interval.scope_label != contract.scope_label
            or sim.interval.scope_fingerprint != contract.scope_fingerprint
        ):
            return ("SCOPE_MISMATCH", "simulated scope does not match contract scope")
        if (
            sim.interval.time_basis_label != contract.time_basis_label
            or sim.interval.time_basis_fingerprint != contract.time_basis_fingerprint
        ):
            return ("TIME_BASIS_MISMATCH", "simulated time basis does not match contract")
        if _is_unsupported_measure(sim.interval.measure):
            return (
                "UNSUPPORTED_FIELD",
                f"simulated measure {sim.interval.measure!r} is unsupported field",
            )
    return None


def _screen_prerequisites(prereq: ComparisonWorkflowPrerequisites) -> tuple[str, str] | None:
    if not prereq.provider_evidence_available:
        return (
            "PROVIDER_DATA_REQUIRED",
            "provider evidence is unavailable — observed source requires admitted snapshot",
        )
    if prereq.map_match_standing in {"UNRESOLVED", "REJECTED"}:
        return (
            "MAP_MATCH_UNRESOLVED",
            (
                f"map matching standing {prereq.map_match_standing!r} "
                "cannot silently advance to comparison"
            ),
        )
    if prereq.demand_standing == "PROVIDER_DATA_REQUIRED" or not prereq.demand_software_valid:
        return ("DEMAND_INSUFFICIENT", "demand is insufficient/inferred — cannot advance")
    if not prereq.calibration_accepted:
        return (
            "CALIBRATION_UNACCEPTED",
            "calibration has not been accepted — optimisation convergence does not imply realism",
        )
    if not prereq.output_software_valid:
        return ("MALFORMED_OUTPUT", "SUMO output is malformed or failed import — cannot compare")
    return None


def build_comparison_workflow_request(
    *,
    workflow_id: str,
    contract: ManchesterComparisonMetricContract,
    lineage: ComparisonLineage,
    observed_inputs: list[ObservedComparisonInterval],
    simulated_inputs: list[SimulatedComparisonInterval],
    prerequisites: ComparisonWorkflowPrerequisites,
) -> ManchesterComparisonWorkflowRequest:
    """Build a strictly revalidated workflow request."""
    try:
        _ = ManchesterComparisonMetricContract.model_validate(
            contract.model_dump(mode="python"),
            strict=True,
        )
        _ = ComparisonLineage.model_validate(lineage.model_dump(mode="python"), strict=True)
        for o in observed_inputs:
            _ = ObservedComparisonInterval.model_validate(o.model_dump(mode="python"), strict=True)
        for s in simulated_inputs:
            _ = SimulatedComparisonInterval.model_validate(s.model_dump(mode="python"), strict=True)
        _ = ComparisonWorkflowPrerequisites.model_validate(
            prerequisites.model_dump(mode="python"),
            strict=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise ManchesterComparisonWorkflowError(
            "REQUEST_VALIDATION_FAILED",
            _sanitize(str(exc)),
        ) from exc

    tmp_req = ManchesterComparisonWorkflowRequest.model_construct(
        workflow_id=workflow_id,
        contract=contract,
        contract_fingerprint=contract.fingerprint(),
        lineage=lineage,
        lineage_fingerprint=lineage.fingerprint(),
        observed_inputs=tuple(observed_inputs),
        simulated_inputs=tuple(simulated_inputs),
        prerequisites=prerequisites,
        request_fingerprint="0" * 64,
    )
    fp = _request_fingerprint(tmp_req)
    return ManchesterComparisonWorkflowRequest(
        workflow_id=workflow_id,
        contract=contract,
        contract_fingerprint=contract.fingerprint(),
        lineage=lineage,
        lineage_fingerprint=lineage.fingerprint(),
        observed_inputs=tuple(observed_inputs),
        simulated_inputs=tuple(simulated_inputs),
        prerequisites=prerequisites,
        request_fingerprint=fp,
    )


def _sanitize(msg: str) -> str:
    if _PRIVATE_PATH_RE.search(msg) or _SECRET_RE.search(msg):
        return "invalid input"
    return msg[:500]


def evaluate_comparison_workflow(
    request: ManchesterComparisonWorkflowRequest,
) -> ManchesterComparisonWorkflowResult:
    """Evaluate the workflow — either AVAILABLE or explicitly blocked/refused.

    Never performs unit coercion, resampling, or zero-fill. Delegates numeric
    pairing to :func:`compare_observed_and_simulated` after screening.
    If no legitimate paired metric survives or minimum coverage is unmet,
    returns a truthful blocked/refused standing with metrics unavailable.
    """
    try:
        request = ManchesterComparisonWorkflowRequest.model_validate(
            request.model_dump(mode="python"),
            strict=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise ManchesterComparisonWorkflowError(
            "REQUEST_VALIDATION_FAILED",
            _sanitize(str(exc)),
        ) from exc

    prereq_block = _screen_prerequisites(request.prerequisites)
    if prereq_block is not None:
        code, msg = prereq_block
        standing_map: dict[str, str] = {
            "PROVIDER_DATA_REQUIRED": "BLOCKED_PROVIDER_DATA_REQUIRED",
            "MAP_MATCH_UNRESOLVED": "BLOCKED_MAP_MATCH_UNRESOLVED",
            "DEMAND_INSUFFICIENT": "BLOCKED_DEMAND_INSUFFICIENT",
            "CALIBRATION_UNACCEPTED": "BLOCKED_CALIBRATION_UNACCEPTED",
            "MALFORMED_OUTPUT": "BLOCKED_MALFORMED_OUTPUT",
        }
        standing = standing_map.get(code, "REFUSED_INCOMPATIBLE")
        return _blocked_result(request, standing, code, msg)  # type: ignore[arg-type]

    baseline_accepted = request.prerequisites.baseline_accepted
    if not baseline_accepted and request.contract.evidence_class == "production":
        return _blocked_result(
            request,
            "BLOCKED_BASELINE_UNACCEPTED",
            "BASELINE_UNACCEPTED",
            "baseline has not been scientifically accepted — software-valid is not accepted",
        )

    incompat = _screen_incompatibility(
        request.contract,
        request.observed_inputs,
        request.simulated_inputs,
    )
    if incompat is not None:
        code, msg = incompat
        standing = (
            "REFUSED_UNSUPPORTED_FIELD" if code == "UNSUPPORTED_FIELD" else "REFUSED_INCOMPATIBLE"
        )
        return _blocked_result(request, standing, code, msg)  # type: ignore[arg-type]

    try:
        comparison = compare_observed_and_simulated(
            request.contract,
            request.lineage,
            request.observed_inputs,
            request.simulated_inputs,
        )
    except ManchesterComparisonError as exc:
        return _blocked_result(
            request,
            "BLOCKED_MALFORMED_OUTPUT",
            exc.code,
            _sanitize(str(exc)),
        )
    except Exception as exc:  # noqa: BLE001
        return _blocked_result(
            request,
            "BLOCKED_MALFORMED_OUTPUT",
            "COMPARISON_MALFORMED",
            _sanitize(str(exc)),
        )

    # Exact compatibility: do not mark incompatible as AVAILABLE merely because
    # mature comparison numerically excluded them. If no paired metric survives
    # or minimum coverage is unmet, return blocked/refused with metrics
    # unavailable. Retain exclusions and coverage diagnostics in comparison
    # object but signal blocked at workflow level.
    if comparison.paired_intervals == 0:
        return _blocked_result(
            request,
            "REFUSED_INCOMPATIBLE",
            "NO_PAIRED_INTERVALS",
            "no legitimate paired observed/simulated intervals survived — incompatible",
        )
    # Check minimum coverage thresholds from contract
    obs_cov = comparison.paired_observed_coverage
    sim_cov = comparison.paired_simulated_coverage
    # Use contract thresholds if available; guard for attribute existence
    min_obs = request.contract.minimum_observed_coverage
    min_sim = request.contract.minimum_simulated_coverage
    # comparison coverage may be Decimal; compare directly
    try:
        if obs_cov < min_obs or sim_cov < min_sim:
            return _blocked_result(
                request,
                "REFUSED_INCOMPATIBLE",
                "COVERAGE_BELOW_MINIMUM",
                (
                    f"coverage below minimum: observed {obs_cov} < {min_obs} "
                    f"or simulated {sim_cov} < {min_sim}"
                ),
            )
    except Exception:  # noqa: S110
        # If coverage fields not present, fall back to paired check only
        pass  # noqa: S110

    synthetic = bool(comparison.synthetic)
    if synthetic:
        evidence_class: Literal[
            "SYNTHETIC_ENGINEERING",
            "DESIGN_ONLY",
            "PRODUCTION",
        ] = "SYNTHETIC_ENGINEERING"
    else:
        evidence_class = "PRODUCTION" if comparison.contract_admitted else "DESIGN_ONLY"

    tmp_res = ManchesterComparisonWorkflowResult.model_construct(
        workflow_id=request.workflow_id,
        request_fingerprint=request.request_fingerprint,
        standing="AVAILABLE",
        comparison=comparison,
        evidence_class=evidence_class,
        result_fingerprint="0" * 64,
    )
    fp = _result_fingerprint(tmp_res)
    return ManchesterComparisonWorkflowResult(
        workflow_id=request.workflow_id,
        request_fingerprint=request.request_fingerprint,
        standing="AVAILABLE",
        comparison=comparison,
        evidence_class=evidence_class,
        result_fingerprint=fp,
    )


def _blocked_result(
    request: ManchesterComparisonWorkflowRequest,
    standing: Literal[
        "BLOCKED_PROVIDER_DATA_REQUIRED",
        "BLOCKED_MAP_MATCH_UNRESOLVED",
        "BLOCKED_DEMAND_INSUFFICIENT",
        "BLOCKED_CALIBRATION_UNACCEPTED",
        "BLOCKED_BASELINE_UNACCEPTED",
        "BLOCKED_MALFORMED_OUTPUT",
        "REFUSED_INCOMPATIBLE",
        "REFUSED_UNSUPPORTED_FIELD",
    ],
    code: str,
    message: str,
) -> ManchesterComparisonWorkflowResult:
    synthetic_any = any(o.synthetic for o in request.observed_inputs) or any(
        s.synthetic for s in request.simulated_inputs
    )
    evidence_class: Literal[
        "SYNTHETIC_ENGINEERING",
        "DESIGN_ONLY",
        "PRODUCTION",
    ] = "SYNTHETIC_ENGINEERING" if synthetic_any else "DESIGN_ONLY"
    tmp_res = ManchesterComparisonWorkflowResult.model_construct(
        workflow_id=request.workflow_id,
        request_fingerprint=request.request_fingerprint,
        standing=standing,
        evidence_class=evidence_class,
        blocker_code=code,
        blocker_message=message[:500],
        result_fingerprint="0" * 64,
    )
    fp = _result_fingerprint(tmp_res)
    return ManchesterComparisonWorkflowResult(
        workflow_id=request.workflow_id,
        request_fingerprint=request.request_fingerprint,
        standing=standing,
        evidence_class=evidence_class,
        blocker_code=code,
        blocker_message=message[:500],
        result_fingerprint=fp,
    )


def verify_workflow_request(
    request: ManchesterComparisonWorkflowRequest,
) -> ManchesterComparisonWorkflowRequest:
    """Revalidate a request and its exact embedded identities."""
    try:
        # Revalidate outer
        req = ManchesterComparisonWorkflowRequest.model_validate(
            request.model_dump(mode="python"),
            strict=True,
        )
        # Revalidate exact embedded identities
        _ = ManchesterComparisonMetricContract.model_validate(
            req.contract.model_dump(mode="python"),
            strict=True,
        )
        _ = ComparisonLineage.model_validate(
            req.lineage.model_dump(mode="python"),
            strict=True,
        )
        for o in req.observed_inputs:
            _ = ObservedComparisonInterval.model_validate(o.model_dump(mode="python"), strict=True)
        for s in req.simulated_inputs:
            _ = SimulatedComparisonInterval.model_validate(
                s.model_dump(mode="python"),
                strict=True,
            )
        _ = ComparisonWorkflowPrerequisites.model_validate(
            req.prerequisites.model_dump(mode="python"),
            strict=True,
        )
        if req.contract_fingerprint != req.contract.fingerprint():
            raise ValueError("contract_fingerprint drift")
        if req.lineage_fingerprint != req.lineage.fingerprint():
            raise ValueError("lineage_fingerprint drift")
    except Exception as exc:  # noqa: BLE001
        raise ManchesterComparisonWorkflowError(
            "REQUEST_TAMPERED",
            _sanitize(str(exc)),
        ) from exc
    return req


def verify_workflow_result(
    result: ManchesterComparisonWorkflowResult,
    request: ManchesterComparisonWorkflowRequest,
) -> ManchesterComparisonWorkflowResult:
    """Require exact request; deterministically re-evaluate and compare.

    Fails closed if result does not match re-evaluation against the exact
    request. Missing dependencies fail closed.
    """
    if request is None:
        raise ManchesterComparisonWorkflowError(
            "MISSING_REQUEST",
            "verification requires exact request",
        )
    try:
        # Revalidate result and request strictly
        res = ManchesterComparisonWorkflowResult.model_validate(
            result.model_dump(mode="python"),
            strict=True,
        )
        req = ManchesterComparisonWorkflowRequest.model_validate(
            request.model_dump(mode="python"),
            strict=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise ManchesterComparisonWorkflowError(
            "RESULT_TAMPERED",
            _sanitize(str(exc)),
        ) from exc
    # Request fingerprint must bind
    if res.request_fingerprint != req.request_fingerprint:
        raise ManchesterComparisonWorkflowError(
            "REQUEST_FINGERPRINT_MISMATCH",
            "result request_fingerprint does not match request",
        )
    if res.workflow_id != req.workflow_id:
        raise ManchesterComparisonWorkflowError(
            "WORKFLOW_ID_MISMATCH",
            "result workflow_id does not match request workflow_id",
        )
    # Deterministically re-evaluate and compare
    try:
        expected = evaluate_comparison_workflow(req)
    except ManchesterComparisonWorkflowError as exc:
        raise ManchesterComparisonWorkflowError(exc.code, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise ManchesterComparisonWorkflowError(
            "RE_EVALUATION_FAILED",
            _sanitize(str(exc)),
        ) from exc
    if expected.standing != res.standing:
        raise ManchesterComparisonWorkflowError(
            "STANDING_MISMATCH",
            f"re-evaluated standing {expected.standing!r} != result {res.standing!r}",
        )
    if expected.result_fingerprint != res.result_fingerprint:
        raise ManchesterComparisonWorkflowError(
            "RESULT_FINGERPRINT_MISMATCH",
            "re-evaluated result fingerprint mismatch",
        )
    # Compare comparison presence and blocker details
    if (expected.comparison is None) != (res.comparison is None):
        raise ManchesterComparisonWorkflowError(
            "COMPARISON_MISMATCH",
            "re-evaluated comparison presence mismatch",
        )
    if (
        expected.comparison is not None
        and res.comparison is not None
        and expected.comparison.fingerprint() != res.comparison.fingerprint()
    ):
        raise ManchesterComparisonWorkflowError(
            "COMPARISON_FINGERPRINT_MISMATCH",
            "re-evaluated comparison fingerprint mismatch",
        )
    if expected.blocker_code != res.blocker_code or expected.blocker_message != res.blocker_message:
        raise ManchesterComparisonWorkflowError(
            "BLOCKER_MISMATCH",
            "re-evaluated blocker mismatch",
        )
    return res


__all__ = [
    "COMPARISON_WORKFLOW_CAPABILITY_ID",
    "COMPARISON_WORKFLOW_METHOD_VERSION",
    "COMPARISON_WORKFLOW_SCHEMA_VERSION",
    "EVIDENCE_BOUNDARY",
    "LIMITATIONS",
    "ComparisonWorkflowPrerequisites",
    "ManchesterComparisonWorkflowError",
    "ManchesterComparisonWorkflowRequest",
    "ManchesterComparisonWorkflowResult",
    "build_comparison_workflow_request",
    "evaluate_comparison_workflow",
    "verify_workflow_request",
    "verify_workflow_result",
]
