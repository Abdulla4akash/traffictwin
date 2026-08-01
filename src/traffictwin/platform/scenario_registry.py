"""Scenario and run registry (post-v1 R-1): an append-only lifecycle log.

Implements ``docs/platform/scenario_run_registry_design.md``: the durable
link between a composed what-if scenario and everything that later happens
to it — approval, execution, deviation, analysis, admission — as an
append-only event log that never overwrites history. The registry records
lifecycle and provenance; it does not approve, schedule, launch, admit, or
scientifically interpret anything:

- there is NO run endpoint anywhere in this module;
- approval is a policy-valid HUMAN artifact bound to the exact draft digest
  — agent identities, placeholders, filenames, clicks and successful
  executions are never approval;
- admission standing is COPIED from the authoritative admission chain's
  records, never decided here;
- a prediction stays ``evidence: false`` even after its scenario runs;
  execution deviations stay visible on every later timeline state; and a
  non-admitted timeline is complete but can never enter an admitted view.

Every write chains on ``prior_digest`` (optimistic concurrency), is
idempotent by event digest, and the whole timeline replays deterministically
from the log bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

METHOD_VERSION: Literal["scenario-run-registry-1.0"] = "scenario-run-registry-1.0"
DESIGN_REFERENCE: Literal["docs/platform/scenario_run_registry_design.md"] = (
    "docs/platform/scenario_run_registry_design.md"
)

EventType = Literal[
    "scenario_drafted",
    "approval_bound",
    "execution_receipted",
    "deviation_recorded",
    "analysis_bound",
    "admission_recorded",
    "scenario_closed",
]

#: Which event types may follow each timeline head state.
_VALID_TRANSITIONS: dict[EventType, tuple[EventType, ...]] = {
    "scenario_drafted": ("approval_bound", "scenario_closed"),
    "approval_bound": ("execution_receipted", "scenario_closed"),
    "execution_receipted": (
        "deviation_recorded",
        "analysis_bound",
        "admission_recorded",
        "scenario_closed",
    ),
    "deviation_recorded": (
        "deviation_recorded",
        "analysis_bound",
        "admission_recorded",
        "scenario_closed",
    ),
    "analysis_bound": ("deviation_recorded", "admission_recorded", "scenario_closed"),
    "admission_recorded": ("deviation_recorded", "scenario_closed"),
    "scenario_closed": (),
}

#: Identities that can never satisfy an approval or closure event.
_FORBIDDEN_IDENTITY_MARKERS = ("agent", "tbd", "n/a", "none", "claude", "codex", "llm", "auto")

#: Record kinds the admission link accepts as authoritative.
_AUTHORITATIVE_ADMISSION_KINDS = (
    "vec_fresh_admission_record",
    "vec_campaign_receipt",
    "evidence_record",
)

_PRIVATE_MARKERS = ("/Users/", "/home/", "\\Users\\", "BODS_API_KEY", "ANTHROPIC_API_KEY")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ScenarioRegistryError(RuntimeError):
    """Typed refusal; the registry fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


def _screen_private(value: str, context: str) -> str:
    for marker in _PRIVATE_MARKERS:
        if marker in value:
            raise ScenarioRegistryError(
                "PRIVATE_CONTENT_DETECTED",
                f"{context} carries private content ('{marker}') and was refused",
            )
    return value


class ScenarioRecord(RegistryModel):
    """The registered scenario: structured inputs plus draft digests."""

    scenario_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    revision: int = Field(ge=1)
    created_at_utc: str
    creator_class: Literal["composer_template", "composer_llm", "owner_manual"]
    trace: str
    actor: str
    capacity: float
    fleet_preset: str
    seed_proposal: tuple[int, ...]
    prediction_digest: str | None
    prediction_available: bool
    draft_design_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_predeclaration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    forecast: Literal[False] = False
    prediction: Literal[True] = True
    evidence: Literal[False] = False
    causal: Literal[False] = False
    policy_ceiling: Literal["owner_approved_candidate"] = "owner_approved_candidate"


class RegistryEvent(RegistryModel):
    """One appended lifecycle event, chained on the prior event digest."""

    scenario_id: str
    event_type: EventType
    recorded_at_utc: str
    prior_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: dict[str, str]

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class EventReceipt(RegistryModel):
    scenario_id: str
    event_type: EventType
    event_digest: str
    chain_position: int = Field(ge=1)
    idempotent_replay: bool = False


class ScenarioTimeline(RegistryModel):
    """The derived read model: separate fields, standing never inferred."""

    scenario: ScenarioRecord
    head_digest: str
    proposed: Literal[True] = True
    approved: bool
    executed: bool
    analysed: bool
    admission_status: str | None
    deviations: tuple[str, ...]
    closed: bool
    closure_reason: str | None
    events: tuple[RegistryEvent, ...]

    @property
    def in_admitted_view(self) -> bool:
        return self.admission_status == "admitted"


class ScenarioRunRegistry:
    """Append-only registry over one explicit local event-log file."""

    def __init__(
        self,
        log_path: Path,
        *,
        approval_validator: Callable[[ScenarioRecord, dict[str, str]], bool] | None = None,
        admission_validator: Callable[[ScenarioRecord, dict[str, str]], bool] | None = None,
    ) -> None:
        self._log_path = log_path
        self._approval_validator = approval_validator
        self._admission_validator = admission_validator
        self._scenarios: dict[str, ScenarioRecord] = {}
        self._events: dict[str, list[RegistryEvent]] = {}
        self._digests: dict[str, list[str]] = {}
        if log_path.exists():
            self._replay(log_path.read_text(encoding="utf-8"))

    # -- persistence ---------------------------------------------------------

    def _replay(self, raw: str) -> None:
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                kind = entry.pop("_kind")
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ScenarioRegistryError(
                    "PRIOR_EVENT_MISMATCH",
                    f"registry line {line_number} is incomplete or invalid",
                ) from exc
            if kind == "scenario":
                record = ScenarioRecord.model_validate_json(json.dumps(entry))
                if record.scenario_id in self._scenarios:
                    raise ScenarioRegistryError(
                        "SCENARIO_DIGEST_CONFLICT",
                        f"registry line {line_number} repeats scenario '{record.scenario_id}'",
                    )
                self._scenarios[record.scenario_id] = record
                self._events.setdefault(record.scenario_id, [])
                self._digests.setdefault(record.scenario_id, [_scenario_genesis_digest(record)])
            elif kind == "event":
                event = RegistryEvent.model_validate_json(json.dumps(entry))
                event_record = self._scenarios.get(event.scenario_id)
                if event_record is None:
                    raise ScenarioRegistryError(
                        "SCENARIO_DIGEST_CONFLICT",
                        f"registry line {line_number} references an unknown scenario",
                    )
                events = self._events[event.scenario_id]
                chain = self._digests[event.scenario_id]
                if event.prior_digest != chain[-1]:
                    raise ScenarioRegistryError(
                        "PRIOR_EVENT_MISMATCH",
                        f"registry line {line_number} breaks the prior-event digest chain",
                    )
                head_type: EventType = events[-1].event_type if events else "scenario_drafted"
                if event.event_type not in _VALID_TRANSITIONS[head_type]:
                    raise ScenarioRegistryError(
                        "INVALID_TRANSITION",
                        f"registry line {line_number} has invalid transition "
                        f"'{head_type}' -> '{event.event_type}'",
                    )
                self._validate_event_proof(event_record, events, event)
                self._events[event.scenario_id].append(event)
                self._digests[event.scenario_id].append(event.digest())
            else:
                raise ScenarioRegistryError(
                    "INVALID_TRANSITION",
                    f"registry line {line_number} has unknown record kind '{kind}'",
                )

    def _append_line(self, kind: str, payload: dict[str, object]) -> None:
        line = json.dumps({"_kind": kind, **payload}, sort_keys=True)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # -- API -----------------------------------------------------------------

    def register_scenario(self, record: ScenarioRecord) -> EventReceipt:
        for value in (record.trace, record.actor, record.fleet_preset):
            _screen_private(value, "scenario field")
        existing = self._scenarios.get(record.scenario_id)
        if existing is not None:
            if existing == record:
                return EventReceipt(
                    scenario_id=record.scenario_id,
                    event_type="scenario_drafted",
                    event_digest=_scenario_genesis_digest(record),
                    chain_position=1,
                    idempotent_replay=True,
                )
            raise ScenarioRegistryError(
                "SCENARIO_DIGEST_CONFLICT",
                f"scenario '{record.scenario_id}' exists with different content; a "
                "changed draft is a new revision, never an edit",
            )
        self._append_line("scenario", record.model_dump(mode="json"))
        self._scenarios[record.scenario_id] = record
        self._events[record.scenario_id] = []
        self._digests[record.scenario_id] = [_scenario_genesis_digest(record)]
        return EventReceipt(
            scenario_id=record.scenario_id,
            event_type="scenario_drafted",
            event_digest=_scenario_genesis_digest(record),
            chain_position=1,
        )

    def append_event(self, event: RegistryEvent) -> EventReceipt:
        record = self._scenarios.get(event.scenario_id)
        if record is None:
            raise ScenarioRegistryError(
                "SCENARIO_DIGEST_CONFLICT", f"unknown scenario '{event.scenario_id}'"
            )
        for key, value in event.payload.items():
            _screen_private(value, f"event payload field '{key}'")
        chain = self._digests[event.scenario_id]
        events = self._events[event.scenario_id]
        if events and event.digest() in {existing.digest() for existing in events}:
            return EventReceipt(
                scenario_id=event.scenario_id,
                event_type=event.event_type,
                event_digest=event.digest(),
                chain_position=chain.index(event.digest()) + 1,
                idempotent_replay=True,
            )
        if event.prior_digest != chain[-1]:
            raise ScenarioRegistryError(
                "PRIOR_EVENT_MISMATCH",
                "the event chains on a stale prior digest; reload the timeline and "
                "re-append (optimistic concurrency)",
            )
        head_type: EventType = events[-1].event_type if events else "scenario_drafted"
        if event.event_type not in _VALID_TRANSITIONS[head_type]:
            raise ScenarioRegistryError(
                "INVALID_TRANSITION",
                f"'{event.event_type}' may not follow '{head_type}'",
            )
        self._validate_event_proof(record, events, event)
        self._append_line("event", event.model_dump(mode="json"))
        events.append(event)
        chain.append(event.digest())
        return EventReceipt(
            scenario_id=event.scenario_id,
            event_type=event.event_type,
            event_digest=event.digest(),
            chain_position=len(chain),
        )

    def _validate_event_proof(
        self,
        record: ScenarioRecord,
        events: list[RegistryEvent],
        event: RegistryEvent,
    ) -> None:
        payload = event.payload
        if event.event_type == "approval_bound":
            approver = payload.get("approved_by", "")
            lowered = approver.lower()
            if not approver or any(marker in lowered for marker in _FORBIDDEN_IDENTITY_MARKERS):
                raise ScenarioRegistryError(
                    "AGENT_APPROVAL_FORBIDDEN",
                    "approval needs a policy-valid human identity; agent identities, "
                    "placeholders, filenames, clicks and executions are never approval",
                )
            if payload.get("draft_design_digest") != record.draft_design_digest:
                raise ScenarioRegistryError(
                    "APPROVAL_DIGEST_MISMATCH",
                    "the approval binds a different draft digest; a changed draft "
                    "needs a new scenario revision (REVISION_REQUIRED)",
                )
            artifact_digest = payload.get("approval_artifact_digest", "")
            if not _DIGEST_PATTERN.fullmatch(artifact_digest):
                raise ScenarioRegistryError(
                    "APPROVAL_DIGEST_MISMATCH",
                    "approval must bind a SHA-256 digest for an existing external artifact",
                )
            if self._approval_validator is None or not self._approval_validator(record, payload):
                raise ScenarioRegistryError(
                    "APPROVAL_DIGEST_MISMATCH",
                    "the configured policy validator did not accept the external approval "
                    "artifact; the registry cannot create or infer approval",
                )
        if event.event_type == "execution_receipted":
            if not any(item.event_type == "approval_bound" for item in events):
                raise ScenarioRegistryError(
                    "EXECUTION_AUTHORITY_MISSING",
                    "no bound approval precedes this execution receipt; the registry "
                    "cannot infer authority",
                )
            if payload.get("design_fingerprint") != record.draft_design_digest:
                raise ScenarioRegistryError(
                    "DESIGN_FINGERPRINT_MISMATCH",
                    "the executed design fingerprint differs from the approved draft",
                )
        if event.event_type == "admission_recorded":
            if payload.get("record_kind") not in _AUTHORITATIVE_ADMISSION_KINDS:
                raise ScenarioRegistryError(
                    "ADMISSION_RECORD_UNAUTHORISED",
                    "admission standing is copied from the authoritative admission "
                    f"chain only ({', '.join(_AUTHORITATIVE_ADMISSION_KINDS)})",
                )
            artifact_digest = payload.get("admission_artifact_digest", "")
            if not _DIGEST_PATTERN.fullmatch(artifact_digest):
                raise ScenarioRegistryError(
                    "ADMISSION_RECORD_UNAUTHORISED",
                    "admission must bind a SHA-256 digest for an existing authoritative record",
                )
            if payload.get("status") not in {"admitted", "non_admitted", "refused"}:
                raise ScenarioRegistryError(
                    "ADMISSION_RECORD_UNAUTHORISED",
                    "the authoritative admission status is missing or unsupported",
                )
            if self._admission_validator is None or not self._admission_validator(record, payload):
                raise ScenarioRegistryError(
                    "ADMISSION_RECORD_UNAUTHORISED",
                    "the configured admission validator did not accept the external record; "
                    "the registry cannot create or promote standing",
                )
        if event.event_type == "scenario_closed":
            author = payload.get("closed_by", "").lower()
            if not author or any(marker in author for marker in _FORBIDDEN_IDENTITY_MARKERS):
                raise ScenarioRegistryError(
                    "AGENT_APPROVAL_FORBIDDEN",
                    "closure is owner-authored; an agent cannot close a scenario",
                )

    def get_timeline(self, scenario_id: str) -> ScenarioTimeline:
        record = self._scenarios.get(scenario_id)
        if record is None:
            raise ScenarioRegistryError(
                "SCENARIO_DIGEST_CONFLICT", f"unknown scenario '{scenario_id}'"
            )
        events = tuple(self._events[scenario_id])
        deviations = tuple(
            event.payload.get("deviation", "recorded")
            for event in events
            if event.event_type == "deviation_recorded"
        )
        admission: str | None = None
        for event in events:
            if event.event_type == "admission_recorded":
                admission = event.payload.get("status", "unknown")
        closure = next((event for event in events if event.event_type == "scenario_closed"), None)
        return ScenarioTimeline(
            scenario=record,
            head_digest=self._digests[scenario_id][-1],
            approved=any(event.event_type == "approval_bound" for event in events),
            executed=any(event.event_type == "execution_receipted" for event in events),
            analysed=any(event.event_type == "analysis_bound" for event in events),
            admission_status=admission,
            deviations=deviations,
            closed=closure is not None,
            closure_reason=(closure.payload.get("reason") if closure is not None else None),
            events=events,
        )

    def admitted_view(self) -> tuple[ScenarioTimeline, ...]:
        """Only admitted timelines; requesting more is a typed promotion."""

        timelines = [self.get_timeline(scenario_id) for scenario_id in self._scenarios]
        return tuple(timeline for timeline in timelines if timeline.admission_status == "admitted")

    def require_admitted(self, scenario_id: str) -> ScenarioTimeline:
        timeline = self.get_timeline(scenario_id)
        if timeline.admission_status != "admitted":
            raise ScenarioRegistryError(
                "NON_ADMITTED_PROMOTION",
                f"scenario '{scenario_id}' has admission status "
                f"'{timeline.admission_status}'; execution success is not admission "
                "and the registry cannot promote it",
            )
        return timeline


def _scenario_genesis_digest(record: ScenarioRecord) -> str:
    material = json.dumps(record.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def scenario_record_from_draft(
    *,
    draft_design_json: str,
    predeclaration_markdown: str,
    trace: str,
    actor: str,
    capacity: float,
    fleet_preset: str,
    seed_proposal: tuple[int, ...],
    prediction_digest: str | None,
    prediction_available: bool,
    created_at_utc: str,
    creator_class: Literal["composer_template", "composer_llm", "owner_manual"],
) -> ScenarioRecord:
    """Derive the registered scenario from a composer draft bundle."""

    design_digest = hashlib.sha256(draft_design_json.encode("utf-8")).hexdigest()
    predeclaration_digest = hashlib.sha256(predeclaration_markdown.encode("utf-8")).hexdigest()
    scenario_id = hashlib.sha256(f"{design_digest}:{predeclaration_digest}".encode()).hexdigest()[
        :16
    ]
    try:
        return ScenarioRecord(
            scenario_id=scenario_id,
            revision=1,
            created_at_utc=created_at_utc,
            creator_class=creator_class,
            trace=trace,
            actor=actor,
            capacity=capacity,
            fleet_preset=fleet_preset,
            seed_proposal=seed_proposal,
            prediction_digest=prediction_digest,
            prediction_available=prediction_available,
            draft_design_digest=design_digest,
            draft_predeclaration_digest=predeclaration_digest,
        )
    except ValidationError as exc:
        raise ScenarioRegistryError(
            "SCENARIO_DIGEST_CONFLICT", f"draft bundle is not registrable: {exc.errors()[0]['msg']}"
        ) from exc
