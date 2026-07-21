"""Versioned golden-contract regression gates for STA-04."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.experiments.statistical_study import (
    StatisticalComponentStatus,
    StatisticalStudy,
    StatisticalStudyStatus,
    metric_collection_fingerprint,
)
from traffictwin.metrics.results import JsonScalar, MetricCollection, MetricStatus, MetricValue

REGRESSION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
REGRESSION_METHOD_VERSION: Literal["1.0"] = "1.0"
REGRESSION_TOLERANCE_METHOD: Literal["max_absolute_or_relative_v1"] = "max_absolute_or_relative_v1"
MAX_REGRESSION_JSON_BYTES = 2_000_000
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][A-Za-z0-9.-]+)?$")


class RegressionSubjectKind(StrEnum):
    """Typed artifact families admitted by STA-04 version 1.0."""

    METRIC_COLLECTION = "metric_collection"
    PAIRED_STATISTICAL_STUDY = "paired_statistical_study"


class GoldenApprovalStatus(StrEnum):
    """Whether a generated reference has been intentionally accepted."""

    CANDIDATE = "candidate"
    APPROVED = "approved"


class SourceIdentityPolicy(StrEnum):
    """How strictly the current source identity must match the golden."""

    EXACT = "exact"
    COMPATIBLE_CONTEXT = "compatible_context"


class RegressionGateStatus(StrEnum):
    """Machine-readable overall gate decision."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class RegressionCheckStatus(StrEnum):
    """Outcome of one declared scalar assertion."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class RegressionReasonCode(StrEnum):
    """Stable reasons for individual or whole-gate outcomes."""

    ASSERTION_PASSED = "ASSERTION_PASSED"
    TOLERANCE_EXCEEDED = "TOLERANCE_EXCEEDED"
    GOLDEN_CONTRACT_NOT_APPROVED = "GOLDEN_CONTRACT_NOT_APPROVED"
    SUBJECT_KIND_MISMATCH = "SUBJECT_KIND_MISMATCH"
    SUBJECT_EMPTY = "SUBJECT_EMPTY"
    SUBJECT_STATUS_UNAVAILABLE = "SUBJECT_STATUS_UNAVAILABLE"
    SUBJECT_CONTEXT_MISMATCH = "SUBJECT_CONTEXT_MISMATCH"
    SOURCE_FINGERPRINT_MISSING = "SOURCE_FINGERPRINT_MISSING"
    SOURCE_IDENTITY_MISMATCH = "SOURCE_IDENTITY_MISMATCH"
    ASSERTION_TARGET_MISSING = "ASSERTION_TARGET_MISSING"
    ASSERTION_VALUE_UNAVAILABLE = "ASSERTION_VALUE_UNAVAILABLE"
    ASSERTION_VALUE_NOT_FINITE_SCALAR = "ASSERTION_VALUE_NOT_FINITE_SCALAR"
    ASSERTION_UNIT_MISMATCH = "ASSERTION_UNIT_MISMATCH"
    ASSERTION_IMPLEMENTATION_VERSION_MISMATCH = "ASSERTION_IMPLEMENTATION_VERSION_MISMATCH"


class StudyRegressionField(StrEnum):
    """Stable scalar STA-01 projections admitted by version 1.0."""

    ELIGIBLE_PAIR_COUNT = "pairing_audit.eligible_pair_count"
    MEAN_PAIRED_DIFFERENCE = "estimate.mean_paired_difference"
    SAMPLE_SD_PAIRED_DIFFERENCE = "estimate.sample_sd_paired_difference"
    STANDARD_ERROR = "estimate.standard_error"
    BOOTSTRAP_LOWER = "bootstrap_interval.lower"
    BOOTSTRAP_UPPER = "bootstrap_interval.upper"
    RANDOMISATION_P_VALUE = "randomisation_test.p_value"
    COHEN_DZ = "effect_sizes.cohen_dz"
    MATCHED_PAIRS_RANK_BISERIAL = "effect_sizes.matched_pairs_rank_biserial"


class RegressionToleranceSpec(BaseModel):
    """One requested scalar selector and its explicit tolerance pair."""

    model_config = ConfigDict(extra="forbid")

    selector: str = Field(min_length=1)
    absolute_tolerance: float = Field(ge=0.0)
    relative_tolerance: float = Field(ge=0.0)

    @field_validator("selector")
    @classmethod
    def normalise_selector(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("selector must not be blank")
        return stripped

    @model_validator(mode="after")
    def validate_finite_tolerances(self) -> RegressionToleranceSpec:
        if not math.isfinite(self.absolute_tolerance):
            raise ValueError("absolute_tolerance must be finite")
        if not math.isfinite(self.relative_tolerance):
            raise ValueError("relative_tolerance must be finite")
        return self


class RegressionAssertion(BaseModel):
    """One accepted golden scalar and its versioned comparison boundary."""

    model_config = ConfigDict(extra="forbid")

    selector: str = Field(min_length=1)
    expected_value: float
    unit: str = Field(min_length=1)
    implementation_version: str | None = None
    absolute_tolerance: float = Field(ge=0.0)
    relative_tolerance: float = Field(ge=0.0)
    tolerance_method: Literal["max_absolute_or_relative_v1"] = REGRESSION_TOLERANCE_METHOD

    @field_validator("selector", "unit")
    @classmethod
    def normalise_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("assertion text fields must not be blank")
        return stripped

    @model_validator(mode="after")
    def validate_finite_values(self) -> RegressionAssertion:
        for name in ("expected_value", "absolute_tolerance", "relative_tolerance"):
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError(f"{name} must be finite")
        return self


class MetricCollectionRegressionContext(BaseModel):
    """Golden compatibility context for one run-level metric collection."""

    model_config = ConfigDict(extra="forbid")

    subject_kind: Literal["metric_collection"] = "metric_collection"
    metric_version: str = Field(min_length=1)
    experiment_id: str | None = None
    seed_id: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)
    checkpoint: str | None = None
    synthetic: bool
    environment: str | None = None
    environment_version: str | None = None
    environment_commit: str | None = None
    source_input_fingerprint: str = Field(min_length=1)


class StatisticalStudyRegressionContext(BaseModel):
    """Golden compatibility context for one STA-01 paired study."""

    model_config = ConfigDict(extra="forbid")

    subject_kind: Literal["paired_statistical_study"] = "paired_statistical_study"
    study_schema_version: str = Field(min_length=1)
    study_method_version: str = Field(min_length=1)
    config_fingerprint: str = Field(min_length=1)
    metric_unit: str = Field(min_length=1)
    synthetic: bool
    compatibility_signature_fingerprint: str = Field(min_length=1)
    source_input_fingerprints: dict[str, str] = Field(min_length=1)

    @field_validator("source_input_fingerprints")
    @classmethod
    def validate_source_fingerprints(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key or not fingerprint for key, fingerprint in value.items()):
            raise ValueError("source input fingerprint keys and values must not be blank")
        return dict(sorted(value.items()))


RegressionContext: TypeAlias = Annotated[
    MetricCollectionRegressionContext | StatisticalStudyRegressionContext,
    Field(discriminator="subject_kind"),
]


class RegressionGoldenContract(BaseModel):
    """Approved, versioned expected scalar values and compatibility policy."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = REGRESSION_SCHEMA_VERSION
    contract_id: str = Field(min_length=2, max_length=128)
    contract_version: str = Field(min_length=3, max_length=64)
    description: str = Field(min_length=12, max_length=2_000)
    approval_status: GoldenApprovalStatus = GoldenApprovalStatus.CANDIDATE
    approved_by: str | None = None
    approval_note: str | None = None
    source_identity_policy: SourceIdentityPolicy = SourceIdentityPolicy.EXACT
    context: RegressionContext
    assertions: list[RegressionAssertion] = Field(min_length=1, max_length=500)
    created_from_subject_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("contract_id")
    @classmethod
    def validate_contract_id(cls, value: str) -> str:
        stripped = value.strip()
        if not _IDENTIFIER_PATTERN.fullmatch(stripped):
            raise ValueError(
                "contract_id must use 2-128 letters, digits, dots, underscores, or hyphens"
            )
        return stripped

    @field_validator("contract_version")
    @classmethod
    def validate_contract_version(cls, value: str) -> str:
        stripped = value.strip()
        if not _VERSION_PATTERN.fullmatch(stripped):
            raise ValueError("contract_version must be a dotted numeric version")
        return stripped

    @field_validator("description")
    @classmethod
    def normalise_description(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 12:
            raise ValueError("description must contain at least 12 non-space characters")
        return stripped

    @field_validator("approved_by", "approval_note")
    @classmethod
    def normalise_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_contract(self) -> RegressionGoldenContract:
        selectors = [assertion.selector for assertion in self.assertions]
        if len(selectors) != len(set(selectors)):
            raise ValueError("regression assertion selectors must be unique")
        if self.approval_status is GoldenApprovalStatus.APPROVED:
            if not self.approved_by:
                raise ValueError("approved_by is required for an approved golden contract")
            if self.approval_note is None or len(self.approval_note) < 12:
                raise ValueError(
                    "approval_note must contain at least 12 characters for an approved contract"
                )
        elif self.approved_by is not None or self.approval_note is not None:
            raise ValueError("candidate contracts cannot carry approval metadata")
        if isinstance(self.context, MetricCollectionRegressionContext):
            if any(assertion.implementation_version is None for assertion in self.assertions):
                raise ValueError("metric assertions require implementation_version")
        else:
            admitted = {field.value for field in StudyRegressionField}
            unsupported = sorted(set(selectors) - admitted)
            if unsupported:
                raise ValueError(
                    "unsupported paired-study regression selectors: " + ", ".join(unsupported)
                )
            if any(assertion.implementation_version is not None for assertion in self.assertions):
                raise ValueError("paired-study assertions do not use implementation_version")
        return self

    @property
    def subject_kind(self) -> RegressionSubjectKind:
        """Return the discriminated target kind."""

        return RegressionSubjectKind(self.context.subject_kind)

    def to_json(self) -> str:
        """Return stable formatted JSON suitable for committing as a golden."""

        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)

    def fingerprint(self) -> str:
        """Return the stable identity of the complete golden contract."""

        return _fingerprint(self.model_dump(mode="json"))


class RegressionBlockingFinding(BaseModel):
    """A subject-level reason no complete numerical gate can be evaluated."""

    model_config = ConfigDict(extra="forbid")

    code: RegressionReasonCode
    detail: str


class RegressionCheck(BaseModel):
    """One reconciled golden-versus-actual scalar check."""

    model_config = ConfigDict(extra="forbid")

    selector: str
    status: RegressionCheckStatus
    reason_code: RegressionReasonCode
    expected_value: float
    actual_value: float | None = None
    unit: str
    absolute_tolerance: float
    relative_tolerance: float
    absolute_error: float | None = None
    relative_error: float | None = None
    allowed_error: float
    boundary_inclusive: Literal[True] = True
    detail: str


class RegressionGateReport(BaseModel):
    """Complete CI-ready STA-04 gate decision and audit."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = REGRESSION_SCHEMA_VERSION
    method_version: Literal["1.0"] = REGRESSION_METHOD_VERSION
    gate_id: str
    generated_at: datetime
    status: RegressionGateStatus
    contract: RegressionGoldenContract
    contract_fingerprint: str
    subject_kind: RegressionSubjectKind
    subject_fingerprint: str
    source_identity_fingerprint: str | None
    check_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    ignored_subject_field_count: int = Field(ge=0)
    blocking_findings: list[RegressionBlockingFinding] = Field(default_factory=list)
    checks: list[RegressionCheck]
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return strict formatted JSON."""

        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)

    def canonical_json(self) -> str:
        """Return canonical JSON with only generation time normalised."""

        payload = self.model_dump(mode="json")
        payload["generated_at"] = "<normalised>"
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Return the deterministic report fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class RegressionGateMethodContract(BaseModel):
    """Published STA-04 subject, tolerance, and decision boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = REGRESSION_SCHEMA_VERSION
    method_version: Literal["1.0"] = REGRESSION_METHOD_VERSION
    subject_kinds: list[RegressionSubjectKind]
    approval_policy: str
    tolerance_method: Literal["max_absolute_or_relative_v1"] = REGRESSION_TOLERANCE_METHOD
    tolerance_formula: str
    source_identity_policies: list[SourceIdentityPolicy]
    overall_precedence: list[RegressionGateStatus]
    study_fields: list[StudyRegressionField]
    unavailable_behavior: str
    ci_exit_codes: dict[str, int]
    unsupported: list[str]
    limitations: list[str]

    def fingerprint(self) -> str:
        """Return the deterministic method-contract fingerprint."""

        return _fingerprint(self.model_dump(mode="json"))


RegressionSubject: TypeAlias = MetricCollection | StatisticalStudy


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def regression_gate_method_contract() -> RegressionGateMethodContract:
    """Return the complete bounded STA-04 v1 method contract."""

    return RegressionGateMethodContract(
        subject_kinds=list(RegressionSubjectKind),
        approval_policy=(
            "Candidate goldens are review artifacts and evaluate as unavailable. Approved "
            "goldens require an approver label and approval note."
        ),
        tolerance_formula=(
            "abs(actual - expected) <= max(absolute_tolerance, "
            "relative_tolerance * abs(expected)); equality passes"
        ),
        source_identity_policies=list(SourceIdentityPolicy),
        overall_precedence=[
            RegressionGateStatus.UNAVAILABLE,
            RegressionGateStatus.FAILED,
            RegressionGateStatus.PASSED,
        ],
        study_fields=list(StudyRegressionField),
        unavailable_behavior=(
            "Missing, partial, unavailable, invalid, non-finite, non-scalar, unit/version/context, "
            "or source-incompatible evidence is unavailable and never replaced by zero."
        ),
        ci_exit_codes={"passed": 0, "failed": 1, "unavailable": 2},
        unsupported=[
            "STA-02 N-way ranking and STA-03 equivalence artifacts",
            "diagnostic, report, grouped, array, arbitrary JSONPath, or rendered-prose gates",
            "automatic tolerance estimation or automatic golden approval",
            "raw-row comparison or metric/study recomputation inside the gate",
        ],
        limitations=_limitations(),
    )


def build_regression_golden_contract(
    subject: RegressionSubject,
    *,
    contract_id: str,
    contract_version: str,
    description: str,
    tolerances: Sequence[RegressionToleranceSpec],
    source_identity_policy: SourceIdentityPolicy = SourceIdentityPolicy.EXACT,
    approval_status: GoldenApprovalStatus = GoldenApprovalStatus.CANDIDATE,
    approved_by: str | None = None,
    approval_note: str | None = None,
) -> RegressionGoldenContract:
    """Build a candidate or explicitly approved golden from one typed subject."""

    specs = list(tolerances)
    _validate_tolerance_specs(specs)
    snapshot = subject.model_dump(mode="json")
    context: RegressionContext
    if isinstance(subject, MetricCollection):
        context = _metric_collection_context(subject)
        assertions = [_metric_assertion(subject, spec) for spec in specs]
        subject_fingerprint = metric_collection_fingerprint(subject)
    else:
        context = _statistical_study_context(subject)
        assertions = [_study_assertion(subject, spec) for spec in specs]
        subject_fingerprint = subject.fingerprint()
    contract = RegressionGoldenContract(
        contract_id=contract_id,
        contract_version=contract_version,
        description=description,
        approval_status=approval_status,
        approved_by=approved_by,
        approval_note=approval_note,
        source_identity_policy=source_identity_policy,
        context=context,
        assertions=assertions,
        created_from_subject_fingerprint=subject_fingerprint,
    )
    if subject.model_dump(mode="json") != snapshot:
        raise RuntimeError("regression golden generation mutated its input subject")
    return contract


def evaluate_regression_gate(
    subject: RegressionSubject,
    contract: RegressionGoldenContract,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> RegressionGateReport:
    """Evaluate one approved golden contract against one typed completed artifact."""

    subject_snapshot = subject.model_dump(mode="json")
    contract_snapshot = contract.model_dump(mode="json")
    subject_kind = _subject_kind(subject)
    subject_fingerprint = _subject_fingerprint(subject)
    contract_fingerprint = contract.fingerprint()
    blockers: list[RegressionBlockingFinding] = []
    if contract.approval_status is not GoldenApprovalStatus.APPROVED:
        blockers.append(
            RegressionBlockingFinding(
                code=RegressionReasonCode.GOLDEN_CONTRACT_NOT_APPROVED,
                detail="The golden contract is a candidate and has not been explicitly approved.",
            )
        )
    if subject_kind is not contract.subject_kind:
        blockers.append(
            RegressionBlockingFinding(
                code=RegressionReasonCode.SUBJECT_KIND_MISMATCH,
                detail=(
                    f"The golden expects {contract.subject_kind.value}, but the supplied subject "
                    f"is {subject_kind.value}."
                ),
            )
        )

    actual_context: RegressionContext | None = None
    try:
        actual_context = (
            _metric_collection_context(subject)
            if isinstance(subject, MetricCollection)
            else _statistical_study_context(subject)
        )
    except ValueError as exc:
        blockers.append(_blocking_finding_from_context_error(str(exc)))

    if actual_context is not None and subject_kind is contract.subject_kind:
        blockers.extend(_context_findings(actual_context, contract))

    source_identity_fingerprint = _source_identity_fingerprint(actual_context)
    if blockers:
        first = blockers[0]
        checks = [
            _unavailable_check(
                assertion,
                first.code,
                "The assertion was not evaluated because a subject-level gate requirement failed.",
            )
            for assertion in contract.assertions
        ]
    elif isinstance(subject, MetricCollection):
        checks = [
            _evaluate_metric_assertion(subject, assertion) for assertion in contract.assertions
        ]
    else:
        checks = [
            _evaluate_study_assertion(subject, assertion) for assertion in contract.assertions
        ]

    passed_count = sum(check.status is RegressionCheckStatus.PASSED for check in checks)
    failed_count = sum(check.status is RegressionCheckStatus.FAILED for check in checks)
    unavailable_count = sum(check.status is RegressionCheckStatus.UNAVAILABLE for check in checks)
    if blockers or unavailable_count:
        status = RegressionGateStatus.UNAVAILABLE
    elif failed_count:
        status = RegressionGateStatus.FAILED
    else:
        status = RegressionGateStatus.PASSED

    ignored_count = _ignored_subject_field_count(subject, contract)
    warnings: list[str] = []
    if contract.source_identity_policy is SourceIdentityPolicy.COMPATIBLE_CONTEXT:
        warnings.append(
            "The compatible-context policy permits source identities to differ; this is a "
            "threshold gate, not an exact-fixture reproducibility claim."
        )
    if ignored_count:
        warnings.append(
            f"{ignored_count} supported subject fields were outside this golden contract and "
            "did not affect the decision."
        )
    gate_id = (
        "gate-"
        + _fingerprint(
            {
                "contract_fingerprint": contract_fingerprint,
                "subject_fingerprint": subject_fingerprint,
            }
        )[:16]
    )
    report = RegressionGateReport(
        gate_id=gate_id,
        generated_at=clock(),
        status=status,
        contract=contract,
        contract_fingerprint=contract_fingerprint,
        subject_kind=subject_kind,
        subject_fingerprint=subject_fingerprint,
        source_identity_fingerprint=source_identity_fingerprint,
        check_count=len(checks),
        passed_count=passed_count,
        failed_count=failed_count,
        unavailable_count=unavailable_count,
        ignored_subject_field_count=ignored_count,
        blocking_findings=blockers,
        checks=checks,
        provenance={
            "method_contract_fingerprint": regression_gate_method_contract().fingerprint(),
            "golden_contract_id": contract.contract_id,
            "golden_contract_version": contract.contract_version,
            "source_identity_policy": contract.source_identity_policy.value,
            "subject_kind": subject_kind.value,
        },
        warnings=warnings,
        limitations=_limitations(),
    )
    if subject.model_dump(mode="json") != subject_snapshot:
        raise RuntimeError("regression gate evaluation mutated its input subject")
    if contract.model_dump(mode="json") != contract_snapshot:
        raise RuntimeError("regression gate evaluation mutated its golden contract")
    return report


def parse_regression_golden_contract_json(
    payload: bytes | str,
    *,
    maximum_bytes: int = MAX_REGRESSION_JSON_BYTES,
) -> RegressionGoldenContract:
    """Parse one bounded strict golden-contract JSON payload."""

    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(data) > maximum_bytes:
        raise ValueError(f"regression golden JSON exceeds {maximum_bytes} bytes")
    return RegressionGoldenContract.model_validate_json(data)


def parse_statistical_study_json(
    payload: bytes | str,
    *,
    maximum_bytes: int = MAX_REGRESSION_JSON_BYTES,
) -> StatisticalStudy:
    """Parse one bounded strict STA-01 study JSON payload."""

    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(data) > maximum_bytes:
        raise ValueError(f"statistical study JSON exceeds {maximum_bytes} bytes")
    return StatisticalStudy.model_validate_json(data)


def regression_gate_to_markdown(report: RegressionGateReport) -> str:
    """Render a deterministic human-readable gate report."""

    lines = [
        "# TrafficTwin Regression Gate",
        "",
        f"- Gate: `{report.gate_id}`",
        f"- Status: `{report.status.value}`",
        (
            f"- Golden: `{report.contract.contract_id}` version "
            f"`{report.contract.contract_version}` (`{report.contract.approval_status.value}`)"
        ),
        f"- Subject kind: `{report.subject_kind.value}`",
        f"- Source identity policy: `{report.contract.source_identity_policy.value}`",
        f"- Contract fingerprint: `{report.contract_fingerprint}`",
        f"- Subject fingerprint: `{report.subject_fingerprint}`",
        "",
        "## Checks",
        "",
        "| Selector | Status | Expected | Actual | Allowed error | Absolute error | Reason |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for check in report.checks:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{check.selector}`",
                    check.status.value,
                    _format_number(check.expected_value),
                    _format_number(check.actual_value),
                    _format_number(check.allowed_error),
                    _format_number(check.absolute_error),
                    check.reason_code.value,
                ]
            )
            + " |"
        )
    if report.blocking_findings:
        lines.extend(["", "## Blocking findings", ""])
        lines.extend(
            f"- `{finding.code.value}` — {finding.detail}" for finding in report.blocking_findings
        )
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "A pass means only that every declared scalar assertion was available, compatible, "
                "and inside its versioned tolerance. Unselected fields were not evaluated."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def regression_gate_to_csv(report: RegressionGateReport) -> str:
    """Render one deterministic audit row per declared assertion."""

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "gate_id",
            "gate_status",
            "contract_id",
            "contract_version",
            "subject_kind",
            "selector",
            "check_status",
            "reason_code",
            "expected_value",
            "actual_value",
            "unit",
            "absolute_tolerance",
            "relative_tolerance",
            "allowed_error",
            "absolute_error",
            "relative_error",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for check in report.checks:
        writer.writerow(
            {
                "gate_id": report.gate_id,
                "gate_status": report.status.value,
                "contract_id": report.contract.contract_id,
                "contract_version": report.contract.contract_version,
                "subject_kind": report.subject_kind.value,
                "selector": check.selector,
                "check_status": check.status.value,
                "reason_code": check.reason_code.value,
                "expected_value": check.expected_value,
                "actual_value": check.actual_value,
                "unit": check.unit,
                "absolute_tolerance": check.absolute_tolerance,
                "relative_tolerance": check.relative_tolerance,
                "allowed_error": check.allowed_error,
                "absolute_error": check.absolute_error,
                "relative_error": check.relative_error,
            }
        )
    return output.getvalue()


def _validate_tolerance_specs(specs: list[RegressionToleranceSpec]) -> None:
    if not specs:
        raise ValueError("at least one regression tolerance specification is required")
    selectors = [spec.selector for spec in specs]
    if len(selectors) != len(set(selectors)):
        raise ValueError("regression tolerance selectors must be unique")


def _metric_collection_context(collection: MetricCollection) -> MetricCollectionRegressionContext:
    if not collection.results:
        raise ValueError("SUBJECT_EMPTY: the metric collection contains no results")
    if not collection.input_fingerprint:
        raise ValueError(
            "SOURCE_FINGERPRINT_MISSING: the metric collection has no input fingerprint"
        )
    first = collection.results[0]
    common = _metric_context_projection(first)
    for metric in collection.results:
        if metric.run_id != collection.run_id:
            raise ValueError("SUBJECT_CONTEXT_MISMATCH: metric run IDs are internally inconsistent")
        if _metric_context_projection(metric) != common:
            raise ValueError(
                "SUBJECT_CONTEXT_MISMATCH: metric run contexts are internally inconsistent"
            )
    return MetricCollectionRegressionContext(
        metric_version=collection.metric_version,
        experiment_id=first.experiment_id,
        seed_id=first.seed_id,
        algorithm=first.algorithm,
        checkpoint=first.checkpoint,
        synthetic=first.synthetic,
        environment=first.environment,
        environment_version=first.environment_version,
        environment_commit=first.environment_commit,
        source_input_fingerprint=collection.input_fingerprint,
    )


def _statistical_study_context(study: StatisticalStudy) -> StatisticalStudyRegressionContext:
    if study.status is not StatisticalStudyStatus.AVAILABLE:
        raise ValueError(f"SUBJECT_STATUS_UNAVAILABLE: paired study status is {study.status.value}")
    if study.synthetic is None or study.metric_unit is None:
        raise ValueError("SUBJECT_CONTEXT_MISMATCH: paired study source mode or unit is unresolved")
    if study.compatibility_signature_fingerprint is None:
        raise ValueError("SUBJECT_CONTEXT_MISMATCH: paired study compatibility signature is absent")
    if not study.input_collection_fingerprints or any(
        not value for value in study.input_collection_fingerprints.values()
    ):
        raise ValueError("SOURCE_FINGERPRINT_MISSING: paired study input identity is incomplete")
    return StatisticalStudyRegressionContext(
        study_schema_version=study.schema_version,
        study_method_version=study.method_version,
        config_fingerprint=study.config_fingerprint,
        metric_unit=study.metric_unit,
        synthetic=study.synthetic,
        compatibility_signature_fingerprint=study.compatibility_signature_fingerprint,
        source_input_fingerprints=study.input_collection_fingerprints,
    )


def _metric_context_projection(metric: MetricValue) -> tuple[object, ...]:
    return (
        metric.seed_id,
        metric.algorithm,
        metric.checkpoint,
        metric.random_seed,
        metric.synthetic,
        metric.environment,
        metric.environment_version,
        metric.environment_commit,
    )


def _metric_assertion(
    collection: MetricCollection,
    spec: RegressionToleranceSpec,
) -> RegressionAssertion:
    metrics = [metric for metric in collection.results if metric.metric_key == spec.selector]
    if len(metrics) != 1:
        raise ValueError(
            f"metric selector {spec.selector!r} must resolve to exactly one result; "
            f"found {len(metrics)}"
        )
    metric = metrics[0]
    value = _available_finite_scalar(metric)
    if value is None:
        raise ValueError(
            f"metric selector {spec.selector!r} is not an available finite scalar golden value"
        )
    return RegressionAssertion(
        selector=spec.selector,
        expected_value=value,
        unit=metric.unit,
        implementation_version=metric.implementation_version,
        absolute_tolerance=spec.absolute_tolerance,
        relative_tolerance=spec.relative_tolerance,
    )


def _study_assertion(study: StatisticalStudy, spec: RegressionToleranceSpec) -> RegressionAssertion:
    try:
        field = StudyRegressionField(spec.selector)
    except ValueError as exc:
        raise ValueError(f"unsupported paired-study regression selector: {spec.selector}") from exc
    value, unit = _study_field_value(study, field)
    if value is None or not math.isfinite(value):
        raise ValueError(f"paired-study selector {field.value!r} is unavailable")
    return RegressionAssertion(
        selector=field.value,
        expected_value=value,
        unit=unit,
        absolute_tolerance=spec.absolute_tolerance,
        relative_tolerance=spec.relative_tolerance,
    )


def _context_findings(
    actual: RegressionContext,
    contract: RegressionGoldenContract,
) -> list[RegressionBlockingFinding]:
    expected = contract.context
    if type(actual) is not type(expected):
        return [
            RegressionBlockingFinding(
                code=RegressionReasonCode.SUBJECT_KIND_MISMATCH,
                detail="The actual and golden context types differ.",
            )
        ]
    if isinstance(actual, MetricCollectionRegressionContext) and isinstance(
        expected, MetricCollectionRegressionContext
    ):
        actual_payload = actual.model_dump(mode="json", exclude={"source_input_fingerprint"})
        expected_payload = expected.model_dump(mode="json", exclude={"source_input_fingerprint"})
        actual_source: object = actual.source_input_fingerprint
        expected_source: object = expected.source_input_fingerprint
    elif isinstance(actual, StatisticalStudyRegressionContext) and isinstance(
        expected, StatisticalStudyRegressionContext
    ):
        actual_payload = actual.model_dump(mode="json", exclude={"source_input_fingerprints"})
        expected_payload = expected.model_dump(mode="json", exclude={"source_input_fingerprints"})
        actual_source = actual.source_input_fingerprints
        expected_source = expected.source_input_fingerprints
    else:
        raise AssertionError("unreachable regression context type")
    findings: list[RegressionBlockingFinding] = []
    if actual_payload != expected_payload:
        findings.append(
            RegressionBlockingFinding(
                code=RegressionReasonCode.SUBJECT_CONTEXT_MISMATCH,
                detail=(
                    "The actual subject context does not equal the golden compatibility context."
                ),
            )
        )
    if (
        contract.source_identity_policy is SourceIdentityPolicy.EXACT
        and actual_source != expected_source
    ):
        findings.append(
            RegressionBlockingFinding(
                code=RegressionReasonCode.SOURCE_IDENTITY_MISMATCH,
                detail=(
                    "The exact source-identity policy requires the accepted source fingerprints."
                ),
            )
        )
    return findings


def _evaluate_metric_assertion(
    collection: MetricCollection,
    assertion: RegressionAssertion,
) -> RegressionCheck:
    matches = [metric for metric in collection.results if metric.metric_key == assertion.selector]
    if len(matches) != 1:
        return _unavailable_check(
            assertion,
            RegressionReasonCode.ASSERTION_TARGET_MISSING,
            f"Expected exactly one metric target; found {len(matches)}.",
        )
    metric = matches[0]
    if metric.status is not MetricStatus.AVAILABLE:
        return _unavailable_check(
            assertion,
            RegressionReasonCode.ASSERTION_VALUE_UNAVAILABLE,
            f"The actual metric status is {metric.status.value}.",
        )
    value = _finite_scalar(metric.value)
    if value is None:
        return _unavailable_check(
            assertion,
            RegressionReasonCode.ASSERTION_VALUE_NOT_FINITE_SCALAR,
            "The actual metric is not a finite numeric scalar.",
        )
    if metric.unit != assertion.unit:
        return _unavailable_check(
            assertion,
            RegressionReasonCode.ASSERTION_UNIT_MISMATCH,
            f"Actual unit {metric.unit!r} does not match golden unit {assertion.unit!r}.",
            actual=value,
        )
    if metric.implementation_version != assertion.implementation_version:
        return _unavailable_check(
            assertion,
            RegressionReasonCode.ASSERTION_IMPLEMENTATION_VERSION_MISMATCH,
            (
                f"Actual implementation version {metric.implementation_version!r} does not match "
                f"golden version {assertion.implementation_version!r}."
            ),
            actual=value,
        )
    return _numeric_check(assertion, value)


def _evaluate_study_assertion(
    study: StatisticalStudy,
    assertion: RegressionAssertion,
) -> RegressionCheck:
    field = StudyRegressionField(assertion.selector)
    value, unit = _study_field_value(study, field)
    if value is None or not math.isfinite(value):
        return _unavailable_check(
            assertion,
            RegressionReasonCode.ASSERTION_VALUE_UNAVAILABLE,
            "The selected paired-study component is unavailable.",
        )
    if unit != assertion.unit:
        return _unavailable_check(
            assertion,
            RegressionReasonCode.ASSERTION_UNIT_MISMATCH,
            f"Actual unit {unit!r} does not match golden unit {assertion.unit!r}.",
            actual=value,
        )
    return _numeric_check(assertion, value)


def _numeric_check(assertion: RegressionAssertion, actual: float) -> RegressionCheck:
    absolute_error = abs(actual - assertion.expected_value)
    allowed_error = _allowed_error(assertion)
    relative_error = (
        absolute_error / abs(assertion.expected_value) if assertion.expected_value != 0.0 else None
    )
    passed = absolute_error <= allowed_error
    return RegressionCheck(
        selector=assertion.selector,
        status=RegressionCheckStatus.PASSED if passed else RegressionCheckStatus.FAILED,
        reason_code=(
            RegressionReasonCode.ASSERTION_PASSED
            if passed
            else RegressionReasonCode.TOLERANCE_EXCEEDED
        ),
        expected_value=assertion.expected_value,
        actual_value=actual,
        unit=assertion.unit,
        absolute_tolerance=assertion.absolute_tolerance,
        relative_tolerance=assertion.relative_tolerance,
        absolute_error=absolute_error,
        relative_error=relative_error,
        allowed_error=allowed_error,
        detail=(
            "The absolute error is inside or on the inclusive allowed boundary."
            if passed
            else "The absolute error exceeds the declared allowed boundary."
        ),
    )


def _unavailable_check(
    assertion: RegressionAssertion,
    code: RegressionReasonCode,
    detail: str,
    *,
    actual: float | None = None,
) -> RegressionCheck:
    return RegressionCheck(
        selector=assertion.selector,
        status=RegressionCheckStatus.UNAVAILABLE,
        reason_code=code,
        expected_value=assertion.expected_value,
        actual_value=actual,
        unit=assertion.unit,
        absolute_tolerance=assertion.absolute_tolerance,
        relative_tolerance=assertion.relative_tolerance,
        allowed_error=_allowed_error(assertion),
        detail=detail,
    )


def _allowed_error(assertion: RegressionAssertion) -> float:
    return max(
        assertion.absolute_tolerance,
        assertion.relative_tolerance * abs(assertion.expected_value),
    )


def _study_field_value(
    study: StatisticalStudy,
    field: StudyRegressionField,
) -> tuple[float | None, str]:
    metric_unit = study.metric_unit or "unavailable"
    if field is StudyRegressionField.ELIGIBLE_PAIR_COUNT:
        return float(study.pairing_audit.eligible_pair_count), "count"
    if field is StudyRegressionField.MEAN_PAIRED_DIFFERENCE:
        return study.estimate.mean_paired_difference, metric_unit
    if field is StudyRegressionField.SAMPLE_SD_PAIRED_DIFFERENCE:
        return study.estimate.sample_sd_paired_difference, metric_unit
    if field is StudyRegressionField.STANDARD_ERROR:
        return study.estimate.standard_error, metric_unit
    if field is StudyRegressionField.BOOTSTRAP_LOWER:
        return study.bootstrap_interval.lower, metric_unit
    if field is StudyRegressionField.BOOTSTRAP_UPPER:
        return study.bootstrap_interval.upper, metric_unit
    if field is StudyRegressionField.RANDOMISATION_P_VALUE:
        if study.randomisation_test.status is StatisticalComponentStatus.UNAVAILABLE:
            return None, "probability"
        return study.randomisation_test.p_value, "probability"
    if field is StudyRegressionField.COHEN_DZ:
        return study.effect_sizes.cohen_dz, "dimensionless"
    if field is StudyRegressionField.MATCHED_PAIRS_RANK_BISERIAL:
        return study.effect_sizes.matched_pairs_rank_biserial, "dimensionless"
    raise AssertionError("unreachable paired-study regression field")


def _available_finite_scalar(metric: MetricValue) -> float | None:
    if metric.status is not MetricStatus.AVAILABLE:
        return None
    return _finite_scalar(metric.value)


def _finite_scalar(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _subject_kind(subject: RegressionSubject) -> RegressionSubjectKind:
    return (
        RegressionSubjectKind.METRIC_COLLECTION
        if isinstance(subject, MetricCollection)
        else RegressionSubjectKind.PAIRED_STATISTICAL_STUDY
    )


def _subject_fingerprint(subject: RegressionSubject) -> str:
    return (
        metric_collection_fingerprint(subject)
        if isinstance(subject, MetricCollection)
        else subject.fingerprint()
    )


def _source_identity_fingerprint(context: RegressionContext | None) -> str | None:
    if isinstance(context, MetricCollectionRegressionContext):
        return _fingerprint(context.source_input_fingerprint)
    if isinstance(context, StatisticalStudyRegressionContext):
        return _fingerprint(context.source_input_fingerprints)
    return None


def _ignored_subject_field_count(
    subject: RegressionSubject,
    contract: RegressionGoldenContract,
) -> int:
    asserted = {assertion.selector for assertion in contract.assertions}
    if isinstance(subject, MetricCollection):
        available_keys = {
            metric.metric_key
            for metric in subject.results
            if _available_finite_scalar(metric) is not None
        }
        return len(available_keys - asserted)
    available_fields = {
        field.value
        for field in StudyRegressionField
        if (value := _study_field_value(subject, field)[0]) is not None and math.isfinite(value)
    }
    return len(available_fields - asserted)


def _blocking_finding_from_context_error(detail: str) -> RegressionBlockingFinding:
    prefix, separator, message = detail.partition(":")
    if separator and prefix in RegressionReasonCode._value2member_map_:
        return RegressionBlockingFinding(
            code=RegressionReasonCode(prefix),
            detail=message.strip(),
        )
    return RegressionBlockingFinding(
        code=RegressionReasonCode.SUBJECT_CONTEXT_MISMATCH,
        detail=detail,
    )


def _limitations() -> list[str]:
    return [
        "A pass applies only to the selected scalar assertions and declared compatibility policy.",
        "A numerical regression gate does not establish scientific validity, equivalence, cause, "
        "or deployment safety.",
        "Compatible-context gates may compare different source inputs and are not exact fixture "
        "reproducibility checks.",
        "Tolerance selection and golden approval remain researcher or project-owner decisions.",
        "Synthetic golden results provide software evidence only, not external validation.",
    ]


def _format_number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.12g}"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
