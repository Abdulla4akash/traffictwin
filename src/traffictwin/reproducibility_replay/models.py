"""Typed models for Reproducibility Replay — allowlisted deterministic replay."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReplayArtifactKind(StrEnum):
    """Allowlisted artifact kinds that may be replayed."""

    EVENT_ALIGNED_REPORT = "event_aligned_report"
    RESOURCE_STRATEGY_REPORT = "resource_strategy_report"
    PREREGISTRATION_GATE = "preregistration_gate"
    COMPARISON_REPORT = "comparison_report"


class ReplayStatus(StrEnum):
    """Discriminated replay status for planning and execution."""

    REPLAYABLE = "replayable"
    NOT_REPLAYABLE = "not_replayable"
    UNSUPPORTED_VERSION = "unsupported_version"
    MISSING_INPUT = "missing_input"
    INCOMPATIBLE = "incompatible"
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    FAILED = "failed"


class ReplayAdapterDescriptor(StrictModel):
    """Declaration for one allowlisted adapter."""

    artifact_kind: ReplayArtifactKind
    supported_schema_versions: list[str] = Field(min_length=1)
    required_input_fingerprints: list[str] = Field(default_factory=list)
    typed_request_model: str = Field(min_length=1)
    service_callable: str = Field(min_length=1)
    expected_output_type: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ReplayRequest(StrictModel):
    """Typed replay request reconstructed only via allowlisted adapters.

    All fields are bounded and validated at the boundary. No import path
    comes from user input — adapter selection is allowlist-keyed.
    """

    artifact_kind: ReplayArtifactKind
    schema_version: str = Field(min_length=1, max_length=32)
    expected_output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_input_fingerprints: dict[str, str] = Field(default_factory=dict)
    # Deterministic typed payload — keys are allowlisted per adapter.
    payload: dict[str, Any] = Field(default_factory=dict)  # noqa: ANN401
    logical_id: str = Field(min_length=1, max_length=128)
    # Optional human note, no absolute paths.
    request_note: str | None = Field(default=None, max_length=500)

    @field_validator("required_input_fingerprints")
    @classmethod
    def _fp_values_hex(cls, v: dict[str, str]) -> dict[str, str]:
        import re

        pat = re.compile(r"^[0-9a-f]{64}$")
        for key, fp in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("input fingerprint key must be non-empty")
            if not pat.fullmatch(fp):
                raise ValueError(f"input fingerprint for {key!r} must be hex64")
            if any(ord(c) < 32 for c in key):
                raise ValueError("fingerprint key must not contain control chars")
        return v

    @field_validator("request_note")
    @classmethod
    def _note_no_path(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if _contains_absolute_path(v):
            raise ValueError("request_note must not contain absolute local paths")
        return v

    def canonical_dict(self) -> dict[str, Any]:  # noqa: ANN401
        return {
            "artifact_kind": self.artifact_kind.value,
            "expected_output_fingerprint": self.expected_output_fingerprint,
            "logical_id": self.logical_id,
            "payload": _sorted_payload(self.payload),
            "required_input_fingerprints": dict(sorted(self.required_input_fingerprints.items())),
            "request_note": self.request_note,
            "schema_version": self.schema_version,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ReplayPlanEntry(StrictModel):
    """One entry in a replay plan."""

    artifact_kind: ReplayArtifactKind | None = None
    logical_id: str = Field(min_length=1, max_length=128)
    status: ReplayStatus
    replayable: bool
    expected_output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    supported_schema_version: str | None = None
    declared_schema_version: str | None = None
    required_inputs_present: list[str] = Field(default_factory=list)
    required_inputs_missing: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    request: ReplayRequest | None = None


class ReplayPlan(StrictModel):
    """Deterministic plan over all allowlisted artifacts in a capsule or artifact set."""

    capsule_id: str | None = None
    manifest_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    verification_status: str = Field(min_length=1)
    entries: list[ReplayPlanEntry] = Field(default_factory=list)
    generated_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def canonical_dict(self) -> dict[str, Any]:  # noqa: ANN401
        return {
            "capsule_id": self.capsule_id,
            "entries": sorted(
                [e.model_dump(mode="json") for e in self.entries],
                key=lambda x: (x.get("artifact_kind") or "", x.get("logical_id") or ""),
            ),
            "limitations": sorted(self.limitations),
            "manifest_fingerprint": self.manifest_fingerprint,
            "verification_status": self.verification_status,
            "warnings": sorted(self.warnings),
        }

    def canonical_json(self) -> str:
        payload = self.canonical_dict()
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ReplayExecution(StrictModel):
    """Result of executing one allowlisted request."""

    artifact_kind: ReplayArtifactKind
    logical_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expected_output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ReplayStatus
    reason: str = Field(min_length=1)
    generated_at: datetime | None = None
    # Canonical output bytes stored only for matched/mismatched inspection; bounded.
    output_preview: str | None = Field(default=None, max_length=5000)


class ReplayComparison(StrictModel):
    """Fingerprint comparison for one execution."""

    artifact_kind: ReplayArtifactKind
    logical_id: str
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    matched: bool
    status: ReplayStatus

    def canonical_dict(self) -> dict[str, Any]:  # noqa: ANN401
        return {
            "actual_fingerprint": self.actual_fingerprint,
            "artifact_kind": self.artifact_kind.value,
            "expected_fingerprint": self.expected_fingerprint,
            "logical_id": self.logical_id,
            "matched": self.matched,
            "status": self.status.value,
        }


class ReplayMismatch(StrictModel):
    """Explicit mismatch detail when fingerprints diverge."""

    artifact_kind: ReplayArtifactKind
    logical_id: str
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    detail: str = Field(min_length=1)


class ReplayReceipt(StrictModel):
    """Deterministic receipt over a complete replay run."""

    receipt_id: str = Field(pattern=r"^urn:traffictwin:replay-receipt:[0-9a-f]{16}$")
    capsule_id: str | None = None
    manifest_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    executed_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    mismatched_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    executions: list[ReplayExecution] = Field(default_factory=list)
    comparisons: list[ReplayComparison] = Field(default_factory=list)
    mismatches: list[ReplayMismatch] = Field(default_factory=list)
    refusals: list[ReplayRefusal] = Field(default_factory=list)
    generated_at: datetime | None = None
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    def canonical_dict(self) -> dict[str, Any]:  # noqa: ANN401
        return {
            "capsule_id": self.capsule_id,
            "comparisons": sorted(
                [c.canonical_dict() for c in self.comparisons],
                key=lambda x: (x["artifact_kind"], x["logical_id"]),
            ),
            "executed_count": self.executed_count,
            "executions": sorted(
                [
                    {
                        k: v
                        for k, v in e.model_dump(mode="json").items()
                        if k not in {"generated_at", "output_preview"}
                    }
                    for e in self.executions
                ],
                key=lambda x: (x.get("artifact_kind") or "", x.get("logical_id") or ""),
            ),
            "failed_count": self.failed_count,
            "limitations": sorted(self.limitations),
            "manifest_fingerprint": self.manifest_fingerprint,
            "matched_count": self.matched_count,
            "mismatched_count": self.mismatched_count,
            "mismatches": sorted(
                [m.model_dump(mode="json") for m in self.mismatches],
                key=lambda x: (x.get("artifact_kind") or "", x.get("logical_id") or ""),
            ),
            "plan_fingerprint": self.plan_fingerprint,
            "receipt_id": self.receipt_id,
            "refusals": sorted(
                [r.model_dump(mode="json") for r in self.refusals],
                key=lambda x: (x.get("artifact_kind") or "", x.get("logical_id") or ""),
            ),
            "warnings": sorted(self.warnings),
        }

    def canonical_json(self) -> str:
        payload = self.canonical_dict()
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )

    def computed_fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ReplayRefusal(StrictModel):
    """Explicit refusal record — no automatic admission or execution."""

    artifact_kind: ReplayArtifactKind | None = None
    logical_id: str | None = None
    status: ReplayStatus
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _reason_no_path(cls, v: str) -> str:
        if _contains_absolute_path(v):
            raise ValueError("refusal reason must not contain absolute local paths")
        if not v.strip():
            raise ValueError("refusal reason must not be empty")
        return v.strip()


# ---------------------------------------------------------------------------
# Helpers shared by models
# ---------------------------------------------------------------------------


def _sorted_payload(value: Any) -> Any:  # noqa: ANN401
    if isinstance(value, dict):
        return {k: _sorted_payload(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_sorted_payload(item) for item in value]
    return value


def _contains_absolute_path(text: str) -> bool:
    import re

    patterns = [
        re.compile(r"file://[^\s\"'<>]+", re.IGNORECASE),
        re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)"),
        re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+"),
        re.compile(r"(?<![/\w])/(?!/)[^\s\"'<>]+"),
    ]
    for pat in patterns:
        if pat.search(text):
            # Allow "artifacts/..." relative paths
            if text.strip().startswith("artifacts/") and pat.pattern.startswith("(?<!["):
                # false positive on relative artifact paths; skip
                continue
            return True
    return False
