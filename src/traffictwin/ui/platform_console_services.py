"""Read-only adapters for the four post-v1 Platform Console pages."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict

from traffictwin.platform.analytics_monitor import (
    AnalyticsMonitorError,
    DataQualityReport,
    LocalQualityReportStore,
)
from traffictwin.platform.decision_safety import (
    CONFIRMATORY_RECORD_PATH,
    CONFIRMATORY_RECORD_SHA256,
    DecisionOption,
    DecisionSafetyError,
    DecisionSafetyPolicy,
    DecisionSupportAssessment,
    SafetyNotice,
    assess,
    confirmed_capacity_notice,
)
from traffictwin.platform.evidence_matrix import (
    CoverageSummary,
    EvidenceMatrix,
    EvidenceMatrixError,
    EvidenceRole,
    MatrixSelection,
    RowStatus,
    build_evidence_matrix,
    filter_rows,
    summarise_coverage,
)
from traffictwin.platform.observatory import (
    EvidenceRole as ObservatoryEvidenceRole,
)
from traffictwin.platform.observatory import (
    MechanismCard,
    ObservatoryBundle,
    ObservatoryError,
    StudyCard,
    build_observatory_bundle,
    select_mechanism_cards,
)

ANALYTICS_REPORTS_RELATIVE = Path("manchester") / "analytics" / "quality-reports"
PUBLIC_SOURCE_BASE = "https://github.com/Abdulla4akash/traffictwin/blob/main/"

_SAFE_REPOSITORY_PATH = re.compile(r"^docs/[A-Za-z0-9_./-]+$")
_PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "\\Users\\",
    "BODS_API_KEY",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "participant_id",
    "raw_vehicle_id",
    "Authorization: Bearer",
)
_SECRET_TOKEN = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}", re.IGNORECASE)


class PlatformConsoleError(RuntimeError):
    """Typed presentation refusal; unsafe backend output never reaches a page."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ConsoleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class SourceLink(ConsoleModel):
    label: str
    relative_path: str
    sha256: str
    url: str


class AnalyticsReportSummary(ConsoleModel):
    report_digest: str
    generated_at_utc: datetime | None
    accepted_count: int
    warning_count: int
    refusal_count: int
    not_observed_count: int
    policy_digest: str | None
    evidence: bool


class AnalyticsConsole(ConsoleModel):
    reports: tuple[DataQualityReport, ...]
    feed: tuple[AnalyticsReportSummary, ...]
    latest: DataQualityReport | None
    unavailable_reason: str | None


class EvidenceConsole(ConsoleModel):
    matrix: EvidenceMatrix
    selection: MatrixSelection
    summary: CoverageSummary
    exclusions: dict[str, str]
    source_links: tuple[SourceLink, ...]


class ObservatoryConsole(ConsoleModel):
    bundle: ObservatoryBundle
    studies: tuple[StudyCard, ...]
    mechanism_cards: tuple[MechanismCard, ...]
    source_links: tuple[SourceLink, ...]


class DecisionConsole(ConsoleModel):
    policy: DecisionSafetyPolicy
    options: tuple[DecisionOption, ...]
    assessment: DecisionSupportAssessment
    required_notice: SafetyNotice
    source_links: tuple[SourceLink, ...]


class _SourceBinding(Protocol):
    path: str
    sha256: str


def _screen(value: str, context: str) -> str:
    lowered = value.lower()
    for marker in _PRIVATE_MARKERS:
        if marker.lower() in lowered:
            raise PlatformConsoleError(
                "PRIVATE_CONTENT_REFUSED", f"{context} contains private or credential material"
            )
    if _SECRET_TOKEN.search(value):
        raise PlatformConsoleError(
            "PRIVATE_CONTENT_REFUSED", f"{context} contains private or credential material"
        )
    return value


def _screen_model(model: BaseModel, context: str) -> None:
    _screen(model.model_dump_json(), context)


def _source_link(binding: _SourceBinding) -> SourceLink:
    path = binding.path
    if (
        not _SAFE_REPOSITORY_PATH.fullmatch(path)
        or Path(path).is_absolute()
        or ".." in Path(path).parts
    ):
        raise PlatformConsoleError(
            "SOURCE_LINK_REFUSED", "a backend source is not an allowlisted repository document"
        )
    return SourceLink(
        label=Path(path).name,
        relative_path=path,
        sha256=binding.sha256,
        url=f"{PUBLIC_SOURCE_BASE}{quote(path, safe='/')}",
    )


def _source_links(bindings: Iterable[_SourceBinding]) -> tuple[SourceLink, ...]:
    links: dict[tuple[str, str], SourceLink] = {}
    for binding in bindings:
        link = _source_link(binding)
        links[(link.relative_path, link.sha256)] = link
    return tuple(links[key] for key in sorted(links))


def load_analytics_console(workspace_path: Path | None) -> AnalyticsConsole:
    """Read the one allowlisted immutable quality-report feed; never publish."""

    if workspace_path is None or not workspace_path.is_dir():
        return AnalyticsConsole(
            reports=(),
            feed=(),
            latest=None,
            unavailable_reason=(
                "no configured workspace exists; no immutable analytics quality report is available"
            ),
        )
    report_directory = workspace_path / ANALYTICS_REPORTS_RELATIVE
    try:
        reports = LocalQualityReportStore(report_directory).reports()
    except AnalyticsMonitorError as exc:
        raise PlatformConsoleError("ANALYTICS_FEED_INVALID", str(exc)) from exc
    for report in reports:
        _screen_model(report, "analytics report")
    if not reports:
        return AnalyticsConsole(
            reports=(),
            feed=(),
            latest=None,
            unavailable_reason=(
                "the allowlisted immutable quality-report feed is empty; missing is not zero"
            ),
        )
    epoch = datetime.min.replace(tzinfo=UTC)
    ordered = tuple(
        sorted(
            reports,
            key=lambda report: (report.generated_at_utc or epoch, report.digest()),
            reverse=True,
        )
    )
    feed = tuple(
        AnalyticsReportSummary(
            report_digest=report.digest(),
            generated_at_utc=report.generated_at_utc,
            accepted_count=len(report.accepted),
            warning_count=len(report.warned),
            refusal_count=len(report.refused),
            not_observed_count=len(report.not_observed),
            policy_digest=report.operational_policy_digest,
            evidence=report.evidence,
        )
        for report in ordered
    )
    return AnalyticsConsole(
        reports=ordered,
        feed=feed,
        latest=ordered[0],
        unavailable_reason=None,
    )


def load_evidence_console(
    repo_root: Path,
    *,
    trace_family: str | None = None,
    status: RowStatus | None = None,
    evidence_role: EvidenceRole | None = None,
    include_non_admitted: bool = False,
) -> EvidenceConsole:
    """Build and filter the code-registered matrix without changing standing."""

    try:
        matrix = build_evidence_matrix(repo_root)
        selection = filter_rows(
            matrix,
            trace_family=trace_family,
            status=status,
            evidence_role=evidence_role,
            include_non_admitted=include_non_admitted,
        )
        summary = summarise_coverage(selection)
    except EvidenceMatrixError as exc:
        raise PlatformConsoleError("EVIDENCE_MATRIX_UNAVAILABLE", str(exc)) from exc
    _screen_model(matrix, "evidence matrix")
    selected_ids = set(selection.row_ids)
    exclusions: dict[str, str] = {}
    for row in matrix.rows:
        if row.design_id in selected_ids:
            continue
        if row.status == "non_admitted" and not include_non_admitted:
            reason = "NON_ADMITTED_SEPARATE_VIEW"
        elif trace_family is not None and row.trace_family != trace_family:
            reason = "TRACE_FILTER"
        elif status is not None and row.status != status:
            reason = "STATUS_FILTER"
        elif evidence_role is not None and row.evidence_role != evidence_role:
            reason = "EVIDENCE_ROLE_FILTER"
        else:
            reason = "NOT_SELECTED"
        exclusions[row.design_id] = reason
    links = _source_links(
        binding
        for row in selection.rows
        for binding in cast(tuple[_SourceBinding, ...], row.sources)
    )
    return EvidenceConsole(
        matrix=matrix,
        selection=selection,
        summary=summary,
        exclusions=exclusions,
        source_links=links,
    )


def load_observatory_console(
    repo_root: Path,
    *,
    evidence_role: ObservatoryEvidenceRole | None = None,
    include_non_admitted_appendix: bool = False,
) -> ObservatoryConsole:
    """Build the digest-pinned observatory and select cards without pooling roles."""

    try:
        bundle = build_observatory_bundle(repo_root)
        cards = select_mechanism_cards(
            bundle,
            evidence_role=evidence_role,
            include_non_admitted_appendix=include_non_admitted_appendix,
        )
    except ObservatoryError as exc:
        raise PlatformConsoleError("OBSERVATORY_UNAVAILABLE", str(exc)) from exc
    _screen_model(bundle, "observatory bundle")
    studies = tuple(
        study
        for study in bundle.studies
        if evidence_role is None or study.evidence_role == evidence_role
    )
    bindings: list[_SourceBinding] = []
    for study in studies:
        bindings.extend(cast(tuple[_SourceBinding, ...], study.sources))
    for card in cards:
        bindings.extend(cast(tuple[_SourceBinding, ...], card.sources))
    bindings.extend(cast(tuple[_SourceBinding, ...], bundle.headline.sources))
    bindings.extend(cast(tuple[_SourceBinding, ...], bundle.action_invariance.sources))
    for check in bundle.coherence_checks:
        bindings.extend(cast(tuple[_SourceBinding, ...], check.sources))
    for contract in bundle.policy_contracts:
        bindings.extend(cast(tuple[_SourceBinding, ...], contract.sources))
    return ObservatoryConsole(
        bundle=bundle,
        studies=studies,
        mechanism_cards=cards,
        source_links=_source_links(bindings),
    )


def load_decision_console(repo_root: Path) -> DecisionConsole:
    """Run Ruleset v2 on the validated confirmed-capacity comparison only."""

    try:
        bundle = build_observatory_bundle(repo_root)
        required_notice = confirmed_capacity_notice(repo_root)
    except (ObservatoryError, DecisionSafetyError) as exc:
        raise PlatformConsoleError("DECISION_SAFETY_UNAVAILABLE", str(exc)) from exc
    headline = bundle.headline
    contract_material = {
        "bundle_digest": bundle.bundle_digest,
        "design_fingerprint": "f289db31ce28b636",
        "trace": "inc",
        "actor": "ukfleettrain_mappo_model_c_17",
        "capacities": (2.5, 0.75),
        "metric": "paired mean task latency delta versus cap-2.5 (ms)",
    }
    contract_digest = hashlib.sha256(
        json.dumps(contract_material, sort_keys=True).encode()
    ).hexdigest()
    companions = ("deadline_attainment", "action_change", "failure_locus")
    policy = DecisionSafetyPolicy(
        policy_id="confirmed-capacity-console-policy",
        policy_version="2.0",
        source_digest=CONFIRMATORY_RECORD_SHA256,
        comparison_contract_digest=contract_digest,
        minimum_support_count=5,
        required_overall_service_companions=companions,
        ranking_allowed=True,
        advisory_recommendation_allowed=True,
        execution_instruction_drafts_allowed=True,
        maximum_cause_scope="none",
    )
    common: dict[str, object] = {
        "kind": "admitted_analysis",
        "source_digest": CONFIRMATORY_RECORD_SHA256,
        "comparison_contract_digest": contract_digest,
        "compatibility_group": "confirmed-capacity-inc-latency",
        "trace": "inc",
        "actor": "ukfleettrain_mappo_model_c_17",
        "inside_measured_envelope": True,
        "actor_capacity_measured": True,
        "matched_budget": True,
        "comparison_predeclared": True,
        "support_count": 5,
        "interval_status": "available",
        "primary_metric_name": "paired mean task latency delta versus cap-2.5 (ms)",
        "metric_direction": "lower_is_better",
        "overall_service_claimed": False,
        "service_endpoint_present": True,
        "companions_present": companions,
        "cause_scope": "none",
        "citation_reference": bundle.citation_reference,
    }
    baseline = DecisionOption.model_validate(
        {
            **common,
            "option_id": "cap-2.5-reference",
            "capacity": 2.5,
            "primary_metric_value": 0.0,
            "headline_improvement_claimed": False,
            "wording": "Reference arm for the paired latency difference; not a zero measurement.",
        }
    )
    variation = DecisionOption.model_validate(
        {
            **common,
            "option_id": "cap-0.75",
            "capacity": 0.75,
            "primary_metric_value": headline.mean_latency_delta_ms,
            "headline_improvement_claimed": True,
            "execution_instruction_draft": (
                "Review a simulation-only instruction for the already predeclared cap-0.75 "
                "comparison arm; this draft cannot execute."
            ),
            "wording": (
                "Metric-specific latency result inside the measured simulation comparison only."
            ),
        }
    )
    options = (baseline, variation)
    try:
        assessment = assess(
            options,
            policy=policy,
            request_ranking=True,
            request_advisory_recommendation=True,
        )
    except DecisionSafetyError as exc:
        raise PlatformConsoleError("DECISION_SAFETY_UNAVAILABLE", str(exc)) from exc
    for model in (policy, *options, assessment, required_notice):
        _screen_model(model, "decision-safety output")
    source_binding = next(
        binding for binding in headline.sources if binding.path == CONFIRMATORY_RECORD_PATH
    )
    return DecisionConsole(
        policy=policy,
        options=options,
        assessment=assessment,
        required_notice=required_notice,
        source_links=_source_links((cast(_SourceBinding, source_binding),)),
    )
