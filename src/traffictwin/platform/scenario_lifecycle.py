"""Exact local integration between what-if drafts and scenario lifecycle artifacts.

This module implements ``docs/platform/scenario_lifecycle_integration_design.md``.
It appends links to artifacts that already exist beneath one explicit authority
root.  It cannot create approval, execute work, analyse results, or admit evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from traffictwin.integration.vec_campaign.analysis import VecCampaignAnalysis
from traffictwin.integration.vec_campaign.models import VecCampaignDesign, VecCampaignReceipt
from traffictwin.platform.scenario_registry import (
    EventReceipt,
    RegistryEvent,
    ScenarioRecord,
    ScenarioRegistryError,
    ScenarioRunRegistry,
    ScenarioTimeline,
)
from traffictwin.platform.whatif_composer import ComposerDraft

METHOD_VERSION: Literal["scenario-lifecycle-integration-1.0"] = "scenario-lifecycle-integration-1.0"
DESIGN_REFERENCE: Literal["docs/platform/scenario_lifecycle_integration_design.md"] = (
    "docs/platform/scenario_lifecycle_integration_design.md"
)
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_IDENTITY = ("agent", "claude", "codex", "llm", "auto", "tbd", "none", "n/a")
_PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "\\Users\\",
    "BODS_API_KEY",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "Authorization: Bearer",
    "participant_id",
    "participant data",
    "sk-",
)

LifecycleArtifact = TypeVar("LifecycleArtifact", bound=BaseModel)
AdmissionAuthorityValidator = Callable[["ScenarioAdmissionRecord", bytes], bool]


class ScenarioLifecycleError(RuntimeError):
    """Typed integration refusal; lifecycle imports fail closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class LifecycleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class ScenarioLifecycleConfig(LifecycleModel):
    """Explicit local paths; paths are never copied into lifecycle records."""

    log_path: Path = Field(repr=False)
    authority_root: Path = Field(repr=False)
    max_artifact_bytes: int = Field(default=MAX_ARTIFACT_BYTES, ge=1, le=64 * 1024 * 1024)


class ScenarioExecutionDeviation(LifecycleModel):
    """Externally authored deviation record accepted by the import adapter."""

    record_type: Literal["scenario_execution_deviation"] = "scenario_execution_deviation"
    scenario_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    approved_design_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    deviation_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$")
    summary: str = Field(min_length=1, max_length=1_000)
    intended_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    recorded_at_utc: str = Field(min_length=1, max_length=64)
    display_required: Literal[True] = True
    scientific_settings_changed: bool
    metric_based_selection_occurred: bool

    @field_validator("summary")
    @classmethod
    def screen_summary(cls, value: str) -> str:
        _screen_private(value, "deviation summary")
        return value


class ScenarioAdmissionRecord(LifecycleModel):
    """Existing external human decision record; the service never constructs it."""

    record_type: Literal["scenario_admission_record"] = "scenario_admission_record"
    record_kind: Literal["evidence_record"] = "evidence_record"
    scenario_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    approved_design_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_artifact_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: Literal["admitted", "non_admitted", "refused"]
    decision_origin: Literal["explicit_human_owner_direction"]
    decided_by: str = Field(min_length=1, max_length=200)
    decided_role: str = Field(min_length=1, max_length=200)
    decided_at_utc: str = Field(min_length=1, max_length=64)
    policy_ceiling: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    deviations_acknowledged: Literal[True] = True
    limitations: tuple[str, ...] = Field(min_length=1, max_length=16)

    @field_validator("decided_by", "decided_role")
    @classmethod
    def validate_human_identity(cls, value: str) -> str:
        lowered = value.strip().lower()
        if not lowered or any(marker in lowered for marker in _FORBIDDEN_IDENTITY):
            raise ValueError("admission needs an explicit human owner identity and role")
        _screen_private(value, "admission identity")
        return value

    @field_validator("limitations")
    @classmethod
    def screen_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not 1 <= len(item) <= 1_000:
                raise ValueError("limitations must contain 1-1000 characters")
            _screen_private(item, "admission limitation")
        return value


class ScenarioLifecycleView(LifecycleModel):
    """Disposable typed view over a deterministically replayed registry timeline."""

    method_version: Literal["scenario-lifecycle-integration-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/scenario_lifecycle_integration_design.md"] = (
        DESIGN_REFERENCE
    )
    timeline: ScenarioTimeline
    composer_draft_digest: str
    execution_design_digest: str
    parent_scenario_id: str | None
    draft_mode: Literal["template", "deepseek_json_form"]
    llm_prompt_template_digest: str | None
    llm_input_digest: str | None
    llm_response_digest: str | None
    approval_artifact_digest: str | None
    approved_design_fingerprint: str | None
    execution_receipt_digest: str | None
    analysis_artifact_digest: str | None
    admission_artifact_digest: str | None


class ScenarioLifecycleService:
    """Local artifact-importing lifecycle service with no execution surface."""

    def __init__(
        self,
        config: ScenarioLifecycleConfig,
        *,
        admission_authority_validator: AdmissionAuthorityValidator | None = None,
    ) -> None:
        self._config = config
        self._authority_root = _validate_root(config.authority_root)
        self._external_admission_validator = admission_authority_validator
        _validate_log_path(config.log_path)
        self._registry = ScenarioRunRegistry(
            config.log_path,
            approval_validator=self._approval_validator,
            admission_validator=self._admission_validator,
            event_validator=self._event_validator,
        )

    def register_draft(
        self,
        draft: ComposerDraft,
        *,
        revision: int,
        parent_scenario_id: str | None = None,
    ) -> EventReceipt:
        """Bind one exact composer draft and explicit revision into the registry."""

        if revision < 1:
            raise ScenarioLifecycleError("REVISION_INVALID", "revision must be at least 1")
        timelines = self._registry.list_timelines()
        if revision == 1 and parent_scenario_id is not None:
            raise ScenarioLifecycleError("REVISION_INVALID", "revision 1 cannot have a parent")
        if revision > 1:
            if parent_scenario_id is None:
                raise ScenarioLifecycleError(
                    "REVISION_REQUIRED", "revision greater than 1 requires its exact prior scenario"
                )
            try:
                parent = self._registry.get_timeline(parent_scenario_id).scenario
            except ScenarioRegistryError as exc:
                raise ScenarioLifecycleError(
                    "REVISION_REQUIRED", "the named prior scenario does not exist"
                ) from exc
            if parent.revision != revision - 1:
                raise ScenarioLifecycleError(
                    "REVISION_REQUIRED", "revision must increment the prior revision exactly once"
                )
            if any(item.scenario.parent_scenario_id == parent_scenario_id for item in timelines):
                existing = next(
                    item.scenario
                    for item in timelines
                    if item.scenario.parent_scenario_id == parent_scenario_id
                )
                candidate_digest = _sha256(_canonical_bytes(draft.model_dump(mode="json")))
                if existing.composer_draft_digest == candidate_digest:
                    return self._registry.register_scenario(existing)
                raise ScenarioLifecycleError(
                    "REVISION_CONFLICT", "the prior revision already has a different child"
                )

        provenance = _draft_provenance(draft)
        composer_digest = _sha256(_canonical_bytes(draft.model_dump(mode="json")))
        if revision > 1 and parent.composer_draft_digest == composer_digest:
            raise ScenarioLifecycleError(
                "REVISION_REQUIRED", "identical draft bytes are an idempotent retry, not a revision"
            )
        design_bytes = _canonical_bytes(draft.design_draft)
        prediction_payload: object = draft.prediction or draft.prediction_refusal
        if prediction_payload is None:
            raise ScenarioLifecycleError(
                "DRAFT_PROVENANCE_INVALID", "draft has neither a prediction nor a refusal"
            )
        prediction_digest = _sha256(
            _canonical_bytes(cast(BaseModel, prediction_payload).model_dump(mode="json"))
        )
        execution_projection = _execution_projection_from_draft(draft.design_draft)
        scenario_id = _sha256(
            f"{composer_digest}:{revision}:{parent_scenario_id or 'genesis'}".encode()
        )[:16]
        record = ScenarioRecord(
            scenario_id=scenario_id,
            revision=revision,
            created_at_utc=draft.generated_at_utc,
            creator_class=(
                "composer_llm"
                if provenance["mode"] == "deepseek_json_form"
                else "composer_template"
            ),
            trace=draft.form.trace,
            actor=draft.form.actor,
            capacity=draft.form.requested_capacity,
            fleet_preset=draft.form.fleet_preset,
            seed_proposal=draft.form.fleet_seeds,
            prediction_digest=prediction_digest,
            prediction_available=draft.prediction_available,
            draft_design_digest=_sha256(design_bytes),
            draft_predeclaration_digest=_sha256(draft.predeclaration_markdown.encode("utf-8")),
            composer_draft_digest=composer_digest,
            execution_design_digest=_sha256(_canonical_bytes(execution_projection)),
            parent_scenario_id=parent_scenario_id,
            draft_mode=cast(Literal["template", "deepseek_json_form"], provenance["mode"]),
            llm_provider=provenance.get("provider"),
            llm_model=provenance.get("model"),
            llm_prompt_template_digest=provenance.get("prompt_template_digest"),
            llm_input_digest=provenance.get("input_digest"),
            llm_response_digest=provenance.get("response_digest"),
        )
        return self._registry.register_scenario(record)

    def bind_approval(
        self, scenario_id: str, expected_prior_digest: str, artifact_path: Path
    ) -> EventReceipt:
        raw = self._read_import_artifact(artifact_path)
        design = _parse_model(VecCampaignDesign, raw, "APPROVAL_ARTIFACT_INVALID")
        record = self._registry.get_timeline(scenario_id).scenario
        predeclaration_digest = self._validate_approved_design(record, design)
        artifact_digest = _sha256(raw)
        event = RegistryEvent(
            scenario_id=scenario_id,
            event_type="approval_bound",
            recorded_at_utc=design.approval.approved_at_utc,
            prior_digest=expected_prior_digest,
            payload={
                "approved_by": design.approval.approved_by,
                "approved_role": design.approval.approved_role,
                "draft_design_digest": record.draft_design_digest,
                "approval_artifact_digest": artifact_digest,
                "approved_design_fingerprint": design.fingerprint(),
                "predeclaration_digest": predeclaration_digest,
            },
        )
        self._require_approval_event(record, event.payload)
        return self._registry.append_event(event)

    def import_execution_receipt(
        self, scenario_id: str, expected_prior_digest: str, artifact_path: Path
    ) -> EventReceipt:
        raw = self._read_import_artifact(artifact_path)
        receipt = _parse_model(VecCampaignReceipt, raw, "EXECUTION_ARTIFACT_INVALID")
        timeline = self._registry.get_timeline(scenario_id)
        self._validate_execution(timeline.scenario, timeline.events, receipt)
        if receipt.status.value == "refused":
            raise ScenarioLifecycleError(
                "EXECUTION_RECEIPT_REFUSED", "a refused campaign receipt records no execution"
            )
        event = RegistryEvent(
            scenario_id=scenario_id,
            event_type="execution_receipted",
            recorded_at_utc=receipt.finished_at_utc,
            prior_digest=expected_prior_digest,
            payload={
                "design_fingerprint": timeline.scenario.draft_design_digest,
                "approved_design_fingerprint": receipt.design_fingerprint,
                "receipt_digest": _sha256(raw),
                "experiment_id": receipt.experiment_id,
                "status": receipt.status.value,
                "predeclaration_verified_unchanged": str(
                    receipt.predeclaration_verified_unchanged
                ).lower(),
            },
        )
        return self._registry.append_event(event)

    def import_deviation(
        self, scenario_id: str, expected_prior_digest: str, artifact_path: Path
    ) -> EventReceipt:
        raw = self._read_import_artifact(artifact_path)
        artifact = _parse_model(ScenarioExecutionDeviation, raw, "DEVIATION_ARTIFACT_INVALID")
        timeline = self._registry.get_timeline(scenario_id)
        self._validate_deviation(timeline.scenario, timeline.events, artifact)
        event = RegistryEvent(
            scenario_id=scenario_id,
            event_type="deviation_recorded",
            recorded_at_utc=artifact.recorded_at_utc,
            prior_digest=expected_prior_digest,
            payload={
                "deviation": artifact.deviation_code,
                "deviation_artifact_digest": _sha256(raw),
                "source_receipt_digest": artifact.source_receipt_digest,
                "approved_design_fingerprint": artifact.approved_design_fingerprint,
                "intended_digest": artifact.intended_digest,
                "observed_digest": artifact.observed_digest,
                "display_required": "true",
            },
        )
        return self._registry.append_event(event)

    def import_analysis(
        self, scenario_id: str, expected_prior_digest: str, artifact_path: Path
    ) -> EventReceipt:
        raw = self._read_import_artifact(artifact_path)
        analysis = _parse_model(VecCampaignAnalysis, raw, "ANALYSIS_ARTIFACT_INVALID")
        timeline = self._registry.get_timeline(scenario_id)
        receipt_digest = self._validate_analysis(timeline.scenario, timeline.events, analysis)
        event = RegistryEvent(
            scenario_id=scenario_id,
            event_type="analysis_bound",
            recorded_at_utc=analysis.generated_at_utc,
            prior_digest=expected_prior_digest,
            payload={
                "analysis_digest": _sha256(raw),
                "source_receipt_digest": receipt_digest,
                "approved_design_fingerprint": analysis.design_fingerprint,
                "experiment_id": analysis.experiment_id,
                "campaign_status": analysis.campaign_status,
                "research_status": analysis.research_status,
            },
        )
        return self._registry.append_event(event)

    def import_admission(
        self, scenario_id: str, expected_prior_digest: str, artifact_path: Path
    ) -> EventReceipt:
        raw = self._read_import_artifact(artifact_path)
        artifact = _parse_model(ScenarioAdmissionRecord, raw, "ADMISSION_ARTIFACT_INVALID")
        timeline = self._registry.get_timeline(scenario_id)
        self._validate_admission(timeline.scenario, timeline.events, artifact)
        self._require_admission_authority(artifact, raw)
        event = RegistryEvent(
            scenario_id=scenario_id,
            event_type="admission_recorded",
            recorded_at_utc=artifact.decided_at_utc,
            prior_digest=expected_prior_digest,
            payload={
                "record_kind": artifact.record_kind,
                "status": artifact.status,
                "admission_artifact_digest": _sha256(raw),
                "source_receipt_digest": artifact.source_receipt_digest,
                "analysis_artifact_digest": artifact.analysis_artifact_digest or "",
                "approved_design_fingerprint": artifact.approved_design_fingerprint,
                "decided_by": artifact.decided_by,
            },
        )
        return self._registry.append_event(event)

    def get_view(self, scenario_id: str) -> ScenarioLifecycleView:
        return _lifecycle_view(self._registry.get_timeline(scenario_id))

    def list_views(self) -> tuple[ScenarioLifecycleView, ...]:
        return tuple(_lifecycle_view(timeline) for timeline in self._registry.list_timelines())

    def admitted_views(self) -> tuple[ScenarioLifecycleView, ...]:
        return tuple(_lifecycle_view(timeline) for timeline in self._registry.admitted_view())

    def _read_import_artifact(self, artifact_path: Path) -> bytes:
        try:
            resolved_parent = artifact_path.parent.resolve(strict=True)
        except OSError as exc:
            raise ScenarioLifecycleError(
                "ARTIFACT_UNSAFE", "artifact parent is missing or unreadable"
            ) from exc
        if resolved_parent != self._authority_root or artifact_path.is_symlink():
            raise ScenarioLifecycleError(
                "ARTIFACT_UNSAFE", "imports must be non-symlink direct authority-root files"
            )
        return self._read_regular(artifact_path)

    def _read_regular(self, path: Path) -> bytes:
        try:
            if not path.is_file() or path.is_symlink():
                raise ScenarioLifecycleError("ARTIFACT_UNSAFE", "artifact is not a regular file")
            size = path.stat().st_size
            if size < 1 or size > self._config.max_artifact_bytes:
                raise ScenarioLifecycleError(
                    "ARTIFACT_SIZE_INVALID", "artifact is empty or exceeds the configured bound"
                )
            raw = path.read_bytes()
        except ScenarioLifecycleError:
            raise
        except OSError as exc:
            raise ScenarioLifecycleError("ARTIFACT_UNSAFE", "artifact could not be read") from exc
        if len(raw) != size:
            raise ScenarioLifecycleError("ARTIFACT_CHANGED", "artifact changed while being read")
        try:
            _screen_private(raw.decode("utf-8"), "authority artifact")
        except UnicodeDecodeError as exc:
            raise ScenarioLifecycleError(
                "ARTIFACT_ENCODING_INVALID", "authority artifacts must be UTF-8"
            ) from exc
        return raw

    def _artifact_by_digest(self, digest: str) -> bytes:
        if not _DIGEST_RE.fullmatch(digest):
            raise ScenarioLifecycleError("ARTIFACT_DIGEST_INVALID", "artifact digest is invalid")
        matches: list[bytes] = []
        try:
            children = sorted(self._authority_root.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise ScenarioLifecycleError(
                "ARTIFACT_UNSAFE", "authority root could not be enumerated"
            ) from exc
        for child in children:
            if child.is_symlink() or not child.is_file():
                continue
            try:
                if child.stat().st_size > self._config.max_artifact_bytes:
                    continue
                raw = child.read_bytes()
            except OSError:
                continue
            if _sha256(raw) == digest:
                try:
                    _screen_private(raw.decode("utf-8"), "authority artifact")
                except UnicodeDecodeError as exc:
                    raise ScenarioLifecycleError(
                        "ARTIFACT_ENCODING_INVALID", "authority artifacts must be UTF-8"
                    ) from exc
                matches.append(raw)
        if not matches:
            raise ScenarioLifecycleError(
                "ARTIFACT_DIGEST_MISMATCH", "no authority artifact has the recorded digest"
            )
        return matches[0]

    def _contained_predeclaration(self, relative_path: str) -> bytes:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ScenarioLifecycleError(
                "APPROVAL_ARTIFACT_INVALID", "predeclaration path escapes the authority root"
            )
        current = self._authority_root
        for part in candidate.parts:
            current = current / part
            if current.is_symlink():
                raise ScenarioLifecycleError(
                    "APPROVAL_ARTIFACT_INVALID", "predeclaration path contains a symlink"
                )
        try:
            resolved = current.resolve(strict=True)
        except OSError as exc:
            raise ScenarioLifecycleError(
                "APPROVAL_ARTIFACT_INVALID", "approved predeclaration is missing"
            ) from exc
        if not resolved.is_relative_to(self._authority_root):
            raise ScenarioLifecycleError(
                "APPROVAL_ARTIFACT_INVALID", "predeclaration escapes the authority root"
            )
        return self._read_regular(resolved)

    def _validate_approved_design(self, record: ScenarioRecord, design: VecCampaignDesign) -> str:
        if record.execution_design_digest is None:
            raise ScenarioLifecycleError(
                "DRAFT_PROVENANCE_INVALID", "scenario lacks an execution-design binding"
            )
        observed = _sha256(_canonical_bytes(_execution_projection_from_design(design)))
        if observed != record.execution_design_digest:
            raise ScenarioLifecycleError(
                "APPROVAL_DIGEST_MISMATCH", "approved design changes the registered composer draft"
            )
        predeclaration = self._contained_predeclaration(design.approval.predeclaration_path)
        digest = _sha256(predeclaration)
        if digest != design.approval.predeclaration_sha256:
            raise ScenarioLifecycleError(
                "APPROVAL_DIGEST_MISMATCH", "approved predeclaration bytes changed"
            )
        return digest

    def _require_approval_event(self, record: ScenarioRecord, payload: dict[str, str]) -> None:
        raw = self._artifact_by_digest(payload.get("approval_artifact_digest", ""))
        design = _parse_model(VecCampaignDesign, raw, "APPROVAL_ARTIFACT_INVALID")
        predeclaration_digest = self._validate_approved_design(record, design)
        expected = {
            "approved_by": design.approval.approved_by,
            "approved_role": design.approval.approved_role,
            "draft_design_digest": record.draft_design_digest,
            "approval_artifact_digest": _sha256(raw),
            "approved_design_fingerprint": design.fingerprint(),
            "predeclaration_digest": predeclaration_digest,
        }
        if payload != expected:
            raise ScenarioLifecycleError(
                "APPROVAL_DIGEST_MISMATCH", "approval event does not match its artifact"
            )

    def _validate_execution(
        self,
        record: ScenarioRecord,
        events: tuple[RegistryEvent, ...],
        receipt: VecCampaignReceipt,
    ) -> None:
        approval_event = _one_event(events, "approval_bound", "EXECUTION_AUTHORITY_MISSING")
        approval_raw = self._artifact_by_digest(approval_event.payload["approval_artifact_digest"])
        design = _parse_model(VecCampaignDesign, approval_raw, "APPROVAL_ARTIFACT_INVALID")
        self._validate_approved_design(record, design)
        if (
            receipt.design_fingerprint != design.fingerprint()
            or receipt.experiment_id != design.experiment_id
            or receipt.approval != design.approval
            or not receipt.predeclaration_verified_unchanged
        ):
            raise ScenarioLifecycleError(
                "EXECUTION_RECEIPT_MISMATCH",
                "execution receipt does not match the exact approved design and approval",
            )

    def _validate_deviation(
        self,
        record: ScenarioRecord,
        events: tuple[RegistryEvent, ...],
        artifact: ScenarioExecutionDeviation,
    ) -> None:
        execution = _one_event(events, "execution_receipted", "EXECUTION_RECEIPT_MISSING")
        if (
            artifact.scenario_id != record.scenario_id
            or artifact.source_receipt_digest != execution.payload["receipt_digest"]
            or artifact.approved_design_fingerprint
            != execution.payload["approved_design_fingerprint"]
        ):
            raise ScenarioLifecycleError(
                "DEVIATION_RECEIPT_MISMATCH", "deviation does not bind the scenario execution"
            )

    def _validate_analysis(
        self,
        record: ScenarioRecord,
        events: tuple[RegistryEvent, ...],
        analysis: VecCampaignAnalysis,
    ) -> str:
        del record
        execution = _one_event(events, "execution_receipted", "EXECUTION_RECEIPT_MISSING")
        if (
            analysis.design_fingerprint != execution.payload["approved_design_fingerprint"]
            or analysis.experiment_id != execution.payload["experiment_id"]
            or analysis.campaign_status != execution.payload["status"]
        ):
            raise ScenarioLifecycleError(
                "ANALYSIS_RECEIPT_MISMATCH", "analysis does not bind the imported execution"
            )
        return execution.payload["receipt_digest"]

    def _validate_admission(
        self,
        record: ScenarioRecord,
        events: tuple[RegistryEvent, ...],
        artifact: ScenarioAdmissionRecord,
    ) -> None:
        execution = _one_event(events, "execution_receipted", "EXECUTION_RECEIPT_MISSING")
        analyses = [event for event in events if event.event_type == "analysis_bound"]
        expected_analysis = analyses[-1].payload["analysis_digest"] if analyses else None
        if (
            artifact.scenario_id != record.scenario_id
            or artifact.source_receipt_digest != execution.payload["receipt_digest"]
            or artifact.approved_design_fingerprint
            != execution.payload["approved_design_fingerprint"]
            or artifact.analysis_artifact_digest != expected_analysis
        ):
            raise ScenarioLifecycleError(
                "ADMISSION_RECEIPT_MISMATCH",
                "admission does not bind the exact execution and current analysis",
            )

    def _require_admission_authority(self, artifact: ScenarioAdmissionRecord, raw: bytes) -> None:
        if self._external_admission_validator is None:
            raise ScenarioLifecycleError(
                "ADMISSION_AUTHORITY_MISSING",
                "an external owner-policy validator is required; schema validity is not authority",
            )
        try:
            accepted = self._external_admission_validator(artifact, raw)
        except Exception as exc:
            raise ScenarioLifecycleError(
                "ADMISSION_RECORD_UNAUTHORISED",
                "the external admission authority validator failed closed",
            ) from exc
        if not accepted:
            raise ScenarioLifecycleError(
                "ADMISSION_RECORD_UNAUTHORISED",
                "the external admission authority did not accept this existing record",
            )

    def _approval_validator(self, record: ScenarioRecord, payload: dict[str, str]) -> bool:
        try:
            self._require_approval_event(record, payload)
        except ScenarioLifecycleError:
            return False
        return True

    def _admission_validator(self, record: ScenarioRecord, payload: dict[str, str]) -> bool:
        try:
            raw = self._artifact_by_digest(payload.get("admission_artifact_digest", ""))
            artifact = _parse_model(ScenarioAdmissionRecord, raw, "ADMISSION_ARTIFACT_INVALID")
        except ScenarioLifecycleError:
            return False
        matches = (
            artifact.scenario_id == record.scenario_id
            and artifact.status == payload.get("status")
            and artifact.record_kind == payload.get("record_kind")
            and artifact.source_receipt_digest == payload.get("source_receipt_digest")
            and (artifact.analysis_artifact_digest or "") == payload.get("analysis_artifact_digest")
            and artifact.approved_design_fingerprint == payload.get("approved_design_fingerprint")
            and artifact.decided_by == payload.get("decided_by")
        )
        if not matches:
            return False
        try:
            self._require_admission_authority(artifact, raw)
        except ScenarioLifecycleError:
            return False
        return True

    def _event_validator(
        self,
        record: ScenarioRecord,
        events: tuple[RegistryEvent, ...],
        event: RegistryEvent,
    ) -> bool:
        try:
            if event.event_type == "execution_receipted":
                raw = self._artifact_by_digest(event.payload.get("receipt_digest", ""))
                receipt = _parse_model(VecCampaignReceipt, raw, "EXECUTION_ARTIFACT_INVALID")
                self._validate_execution(record, events, receipt)
                return event.payload == {
                    "design_fingerprint": record.draft_design_digest,
                    "approved_design_fingerprint": receipt.design_fingerprint,
                    "receipt_digest": _sha256(raw),
                    "experiment_id": receipt.experiment_id,
                    "status": receipt.status.value,
                    "predeclaration_verified_unchanged": str(
                        receipt.predeclaration_verified_unchanged
                    ).lower(),
                }
            if event.event_type == "deviation_recorded":
                raw = self._artifact_by_digest(event.payload.get("deviation_artifact_digest", ""))
                deviation_artifact = _parse_model(
                    ScenarioExecutionDeviation, raw, "DEVIATION_ARTIFACT_INVALID"
                )
                self._validate_deviation(record, events, deviation_artifact)
                return event.payload == {
                    "deviation": deviation_artifact.deviation_code,
                    "deviation_artifact_digest": _sha256(raw),
                    "source_receipt_digest": deviation_artifact.source_receipt_digest,
                    "approved_design_fingerprint": (deviation_artifact.approved_design_fingerprint),
                    "intended_digest": deviation_artifact.intended_digest,
                    "observed_digest": deviation_artifact.observed_digest,
                    "display_required": "true",
                }
            if event.event_type == "analysis_bound":
                raw = self._artifact_by_digest(event.payload.get("analysis_digest", ""))
                analysis = _parse_model(VecCampaignAnalysis, raw, "ANALYSIS_ARTIFACT_INVALID")
                receipt_digest = self._validate_analysis(record, events, analysis)
                return event.payload == {
                    "analysis_digest": _sha256(raw),
                    "source_receipt_digest": receipt_digest,
                    "approved_design_fingerprint": analysis.design_fingerprint,
                    "experiment_id": analysis.experiment_id,
                    "campaign_status": analysis.campaign_status,
                    "research_status": analysis.research_status,
                }
            if event.event_type == "admission_recorded":
                raw = self._artifact_by_digest(event.payload.get("admission_artifact_digest", ""))
                admission_artifact = _parse_model(
                    ScenarioAdmissionRecord, raw, "ADMISSION_ARTIFACT_INVALID"
                )
                self._validate_admission(record, events, admission_artifact)
            return True
        except (ScenarioLifecycleError, KeyError):
            return False


def _lifecycle_view(timeline: ScenarioTimeline) -> ScenarioLifecycleView:
    record = timeline.scenario
    if (
        record.composer_draft_digest is None
        or record.execution_design_digest is None
        or record.draft_mode is None
    ):
        raise ScenarioLifecycleError(
            "DRAFT_PROVENANCE_INVALID", "scenario was not registered by the lifecycle service"
        )
    by_type = {event.event_type: event for event in timeline.events}
    approval = by_type.get("approval_bound")
    execution = by_type.get("execution_receipted")
    analysis = by_type.get("analysis_bound")
    admission = by_type.get("admission_recorded")
    return ScenarioLifecycleView(
        timeline=timeline,
        composer_draft_digest=record.composer_draft_digest,
        execution_design_digest=record.execution_design_digest,
        parent_scenario_id=record.parent_scenario_id,
        draft_mode=record.draft_mode,
        llm_prompt_template_digest=record.llm_prompt_template_digest,
        llm_input_digest=record.llm_input_digest,
        llm_response_digest=record.llm_response_digest,
        approval_artifact_digest=(
            approval.payload["approval_artifact_digest"] if approval is not None else None
        ),
        approved_design_fingerprint=(
            approval.payload["approved_design_fingerprint"] if approval is not None else None
        ),
        execution_receipt_digest=(
            execution.payload["receipt_digest"] if execution is not None else None
        ),
        analysis_artifact_digest=(
            analysis.payload["analysis_digest"] if analysis is not None else None
        ),
        admission_artifact_digest=(
            admission.payload["admission_artifact_digest"] if admission is not None else None
        ),
    )


def _draft_provenance(draft: ComposerDraft) -> dict[str, str]:
    provenance = draft.drafted_by
    mode = provenance.get("mode")
    if mode == "template":
        if set(provenance) != {"mode", "method_version"}:
            raise ScenarioLifecycleError(
                "DRAFT_PROVENANCE_INVALID", "template provenance contains unsupported fields"
            )
        return dict(provenance)
    expected = {
        "mode",
        "provider",
        "model",
        "prompt_template_digest",
        "input_digest",
        "response_digest",
    }
    if mode != "deepseek_json_form" or set(provenance) != expected:
        raise ScenarioLifecycleError(
            "DRAFT_PROVENANCE_INVALID", "DeepSeek provenance must be digest-only and complete"
        )
    for key in ("prompt_template_digest", "input_digest", "response_digest"):
        if not _DIGEST_RE.fullmatch(provenance[key]):
            raise ScenarioLifecycleError(
                "DRAFT_PROVENANCE_INVALID", f"{key} is not a SHA-256 digest"
            )
    if provenance["provider"] != "deepseek" or provenance["model"] != "deepseek-v4-flash":
        raise ScenarioLifecycleError(
            "DRAFT_PROVENANCE_INVALID", "DeepSeek provider or model is not the pinned socket"
        )
    return dict(provenance)


_DESIGN_FIELDS = (
    "experiment_id",
    "research_question",
    "run_id_prefix",
    "phase",
    "trace_file",
    "trace_sha256",
    "actor_id",
    "fleet",
    "evaluator_seed",
    "max_steps",
    "timeout_seconds",
    "baseline_arm",
    "variation_arms",
    "pairing_seed_source",
    "fleet_seeds",
    "primary_metric_key",
    "budget",
)


def _execution_projection_from_draft(draft: dict[str, object]) -> dict[str, object]:
    try:
        projection = {key: draft[key] for key in _DESIGN_FIELDS}
        projection["schema_version"] = "1.0"
        projection["method_version"] = draft["schema_mirrors"]
    except KeyError as exc:
        raise ScenarioLifecycleError(
            "DRAFT_PROVENANCE_INVALID", f"campaign draft is missing '{exc.args[0]}'"
        ) from exc
    return projection


def _execution_projection_from_design(design: VecCampaignDesign) -> dict[str, object]:
    payload = design.model_dump(mode="json")
    return {
        "schema_version": payload["schema_version"],
        "method_version": payload["method_version"],
        **{key: payload[key] for key in _DESIGN_FIELDS},
    }


def _one_event(
    events: tuple[RegistryEvent, ...], event_type: str, error_code: str
) -> RegistryEvent:
    matching = [event for event in events if event.event_type == event_type]
    if len(matching) != 1:
        raise ScenarioLifecycleError(error_code, f"timeline needs exactly one {event_type} event")
    return matching[0]


def _parse_model(model: type[LifecycleArtifact], raw: bytes, code: str) -> LifecycleArtifact:
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        raise ScenarioLifecycleError(code, "artifact failed its strict schema") from exc


def _validate_root(root: Path) -> Path:
    if not root.is_absolute() or root.is_symlink():
        raise ScenarioLifecycleError(
            "AUTHORITY_ROOT_UNSAFE", "authority root must be an absolute non-symlink directory"
        )
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ScenarioLifecycleError(
            "AUTHORITY_ROOT_UNSAFE", "authority root does not exist"
        ) from exc
    if not resolved.is_dir():
        raise ScenarioLifecycleError("AUTHORITY_ROOT_UNSAFE", "authority root is not a directory")
    return resolved


def _validate_log_path(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise ScenarioLifecycleError(
            "LIFECYCLE_LOG_UNSAFE", "log path must be absolute and must not be a symlink"
        )
    if not path.parent.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise ScenarioLifecycleError(
            "LIFECYCLE_LOG_UNSAFE", "log parent must be an existing non-symlink directory"
        )


def _screen_private(value: str, context: str) -> None:
    for marker in _PRIVATE_MARKERS:
        if marker.lower() in value.lower():
            raise ScenarioLifecycleError(
                "PRIVATE_CONTENT_DETECTED", f"{context} carries forbidden private content"
            )


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
