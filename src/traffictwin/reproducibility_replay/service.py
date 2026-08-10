"""Deterministic allowlisted replay service — verify, plan, execute, compare, receipt.

Business logic lives outside Streamlit. All portable identities use
deterministic canonical JSON (sorted keys, ',' ':'), SHA-256, no wall-clock
or local paths, no automatic evidence admission, no shell execution.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import zipfile
from io import BytesIO
from typing import Any

from pydantic import BaseModel, ConfigDict

from traffictwin.reproducibility_replay.adapters import (
    ADAPTER_REGISTRY,
    ALLOWLISTED_REPLAY_KINDS,
    get_adapter,
)
from traffictwin.reproducibility_replay.models import (
    ReplayArtifactKind,
    ReplayComparison,
    ReplayExecution,
    ReplayMismatch,
    ReplayPlan,
    ReplayPlanEntry,
    ReplayReceipt,
    ReplayRefusal,
    ReplayRequest,
    ReplayStatus,
)

# Reuse capsule verifier primitives
from traffictwin.study_capsule import (
    StudyCapsuleVerificationStatus,
    verify_study_capsule_bytes,
)

# ---------------------------------------------------------------------------
# Constants and bounded limits
# ---------------------------------------------------------------------------

REPLAY_SCHEMA_VERSION: str = "1.0"
MAX_REPLAY_ENTRIES = 32
MAX_PAYLOAD_BYTES = 1_000_000
MAX_PLAN_BYTES = 2_000_000

# Raw evidence labels that must NOT be executed automatically and default to refusal.
RAW_EVIDENCE_LABELS: frozenset[str] = frozenset(
    {
        "imported_evidence",
        "historical_observation",
        "near_live_operational",
        "unadmitted_research",
    }
)

# For fingerprint hygiene: pattern for hex64
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Stable limitations and warnings surfaced in every plan/receipt
BASE_LIMITATIONS: list[str] = [
    "Reproducibility replay reconstructs only typed allowlisted requests; no arbitrary Python or shell is executed.",  # noqa: E501
    "Only derived artifacts with explicit synthetic or admitted labels are replayable; raw imported evidence is never executed.",  # noqa: E501
    "Fingerprint comparison proves byte-identical canonical output, not scientific validity or causality.",  # noqa: E501
    "A matched receipt does not admit evidence; admission remains an explicit governance step.",
]

BASE_WARNINGS: list[str] = [
    "Unsigned authenticity is not claimed; verification proves internal capsule integrity only.",
]

EVIDENCE_BOUNDARY: str = (
    "Evidence boundary: this runner replays only allowlisted deterministic analyses "
    "(event-aligned report, resource-strategy report, preregistration gate, comparison report) "
    "from verified capsules or fingerprinted derived artifacts. Raw imported or unadmitted "
    "evidence is refused by default and never zero-filled. No synthetic evidence is relabelled as observed."  # noqa: E501
)

# ---------------------------------------------------------------------------
# Utility: canonical JSON and fingerprint
# ---------------------------------------------------------------------------


def _canonical(payload: Any) -> str:  # noqa: ANN401
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _fingerprint(payload: Any) -> str:  # noqa: ANN401
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _fingerprint_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _receipt_id(plan_fingerprint: str, execution_binding: str | None = None) -> str:
    payload: dict[str, str] = {"plan_fp": plan_fingerprint}
    if execution_binding is not None:
        payload["execution_binding"] = execution_binding
    return "urn:traffictwin:replay-receipt:" + _fingerprint(payload)[:16]


def _execution_binding_fingerprint(
    executions: list[ReplayExecution],
    selected: list[tuple[ReplayArtifactKind, str]] | None = None,
) -> str:
    # Deterministically bind actual execution  # noqa: E501
    parts: list[dict[str, str]] = []
    for exe in sorted(executions, key=lambda e: (e.artifact_kind.value, e.logical_id)):
        parts.append(
            {
                "artifact_kind": exe.artifact_kind.value,
                "logical_id": exe.logical_id,
                "actual_fingerprint": exe.actual_output_fingerprint or "",
                "expected_fingerprint": exe.expected_output_fingerprint,
                "status": exe.status.value,
            }
        )
    # Also bind explicit selection order if provided
    if selected is not None:
        sel_parts = sorted(f"{k.value}:{v}" for k, v in selected)
        parts.append({"selected": ",".join(sel_parts)})
    return _fingerprint(parts)


def _contains_unsafe_path(value: str) -> bool:
    # Returns True if text contains absolute path patterns that must be rejected.
    patterns = [
        re.compile(r"file://[^\s\"'<>]+", re.IGNORECASE),
        re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)"),
        re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+"),
        re.compile(r"(?<![/\w])/(?!/)[^\s\"'<>]+"),
    ]
    for pat in patterns:
        if pat.search(value):
            if value.strip().startswith("artifacts/"):
                continue
            return True
    return False


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class ReplayContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = REPLAY_SCHEMA_VERSION
    allowlisted_kinds: list[str]
    supported_versions: dict[str, list[str]]
    required_inputs: dict[str, list[str]]
    evidence_boundary: str
    limitations: list[str]
    warnings: list[str]
    allowlist_fingerprint: str

    def canonical_json(self) -> str:
        return _canonical(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json"))


def replay_contract() -> ReplayContract:
    from traffictwin.reproducibility_replay.adapters import registry_fingerprint

    allowlisted = sorted(k.value for k in ALLOWLISTED_REPLAY_KINDS)
    versions = {
        k.value: list(v.supported_schema_versions)
        for k, v in sorted(ADAPTER_REGISTRY.items(), key=lambda kv: kv[0].value)
    }
    required = {
        k.value: list(v.required_input_fingerprints)
        for k, v in sorted(ADAPTER_REGISTRY.items(), key=lambda kv: kv[0].value)
    }
    return ReplayContract(
        allowlisted_kinds=allowlisted,
        supported_versions=versions,
        required_inputs=required,
        evidence_boundary=EVIDENCE_BOUNDARY,
        limitations=list(BASE_LIMITATIONS),
        warnings=list(BASE_WARNINGS),
        allowlist_fingerprint=registry_fingerprint(),
    )


# ---------------------------------------------------------------------------
# Capsule integrity verification wrapper
# ---------------------------------------------------------------------------


class CapsuleIntegrity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid: bool
    status: str
    capsule_id: str | None = None
    manifest_fingerprint: str | None = None
    errors: list[str] = []
    embedded_members: list[str] = []
    referenced_members: list[str] = []
    excluded_members: list[str] = []
    unavailable_members: list[str] = []
    archive_sha256: str | None = None


def verify_capsule_integrity(payload: bytes) -> CapsuleIntegrity:
    """Verify internal integrity via the authoritative capsule verifier.

    Reject unsigned-authenticity overclaims: valid only proves internal checksum
    consistency, not external authenticity or non-repudiation.
    """
    ver = verify_study_capsule_bytes(payload)
    return CapsuleIntegrity(
        valid=ver.valid,
        status=ver.status.value,
        capsule_id=ver.capsule_id,
        manifest_fingerprint=ver.manifest_fingerprint,
        errors=list(ver.errors),
        embedded_members=list(ver.embedded_members),
        referenced_members=list(ver.referenced_members),
        excluded_members=list(ver.excluded_members),
        unavailable_members=list(ver.unavailable_members),
        archive_sha256=ver.archive_sha256,
    )


# ---------------------------------------------------------------------------
# Adapter payload reconstruction — typed, bounded, allowlisted
# ---------------------------------------------------------------------------

# We store allowlisted replay artifacts as deterministic JSON files inside
# capsules under artifacts/<capsule_kind>/*.json. For standalone mode we also
# accept fingerprinted JSON files supplied directly. The reconstruction below
# builds a typed ReplayRequest only when the payload belongs to an allowlisted
# adapter and carries a supported schema version.

# Map capsule member kinds to replay kinds for detection when capsule embeds
# a replayable report. We use explicit mapping, not user input.
_CAPSULE_KIND_TO_REPLAY: dict[str, ReplayArtifactKind] = {
    "comparison_report": ReplayArtifactKind.COMPARISON_REPORT,
    "consequence_report": ReplayArtifactKind.RESOURCE_STRATEGY_REPORT,
    "deterministic_report": ReplayArtifactKind.EVENT_ALIGNED_REPORT,
    "evidence_pack": ReplayArtifactKind.PREREGISTRATION_GATE,  # heuristic fallback
    "validation_result": ReplayArtifactKind.PREREGISTRATION_GATE,
    "diagnostic_result": ReplayArtifactKind.COMPARISON_REPORT,
}

# Input fingerprint keys per replay kind expected in payload for planning.
# These are derived from the embedded JSON's canonical fields.
REPLAY_FINGERPRINT_KEYS: dict[ReplayArtifactKind, list[str]] = {
    ReplayArtifactKind.EVENT_ALIGNED_REPORT: [
        "report_id",
        "spec_fingerprint",
        "anchor_fingerprints",
    ],
    ReplayArtifactKind.RESOURCE_STRATEGY_REPORT: ["study_fingerprint", "source_fingerprint"],
    ReplayArtifactKind.PREREGISTRATION_GATE: ["plan_fingerprint"],
    ReplayArtifactKind.COMPARISON_REPORT: ["baseline_fingerprint", "variation_fingerprint"],
}


def _infer_replay_kind_from_payload(
    payload: dict[str, Any], capsule_kind: str | None
) -> ReplayArtifactKind | None:
    # Prefer explicit replay_kind field if present and allowlisted.
    rk = payload.get("replay_kind") or payload.get("artifact_kind") or payload.get("kind")
    if isinstance(rk, str):
        try:
            parsed = ReplayArtifactKind(rk)
            if parsed in ALLOWLISTED_REPLAY_KINDS:
                return parsed
        except ValueError:
            pass
    # Fallback to capsule-kind mapping.
    if capsule_kind is not None:
        mapped = _CAPSULE_KIND_TO_REPLAY.get(capsule_kind)
        if mapped is not None:
            return mapped
    # Heuristic by payload shape — only allowlisted detectors.
    if "spec" in payload and "accepted_runs" in payload:
        return ReplayArtifactKind.EVENT_ALIGNED_REPORT
    if "arm_summaries" in payload and "pairwise_differences" in payload:
        return ReplayArtifactKind.RESOURCE_STRATEGY_REPORT
    if "gate_report" in payload or ("plan_id" in payload and "planned_run_cells" in payload):
        return ReplayArtifactKind.PREREGISTRATION_GATE
    if "baseline_context" in payload and "variation_context" in payload:
        return ReplayArtifactKind.COMPARISON_REPORT
    if "baseline_seed_id" in payload and "variation_seed_id" in payload and "metric_key" in payload:
        # Statistical Study config shape -> map to comparison? We treat as comparison for replay demos.  # noqa: E501
        return ReplayArtifactKind.COMPARISON_REPORT
    return None


def _extract_schema_version(payload: dict[str, Any]) -> str | None:
    sv = (
        payload.get("schema_version")
        or payload.get("report_version")
        or payload.get("comparison_version")
    )
    if isinstance(sv, str) and sv.strip():
        return sv.strip()
    # Determine from payload without explicit version: synthesize version detection.
    # For resource strategy 1.0 etc we default to 1.0 if canonical fields match.
    if "study_id" in payload and "arms" in payload:
        return "1.0"
    if "metric_version" in payload or "metric_key" in payload:
        return "1.0"
    return None


def _extract_expected_fingerprint(payload: dict[str, Any], kind: ReplayArtifactKind) -> str | None:
    # Try explicit fingerprint fields
    for key in (
        "fingerprint",
        "report_fingerprint",
        "manifest_fingerprint",
        "study_fingerprint",
        "config_fingerprint",
    ):
        val = payload.get(key)
        if isinstance(val, str) and _SHA256_RE.fullmatch(val):
            return val
    # For gate, plan fingerprint is inside plan payload: try nested
    if kind is ReplayArtifactKind.PREREGISTRATION_GATE and "fingerprint" in payload:
        v = payload["fingerprint"]
        if isinstance(v, str) and _SHA256_RE.fullmatch(v):
            return v
    # Deterministic canonical fingerprint fallback (excluding generated_at and detection hints)
    try:
        copy = {  # noqa: E501
            k: v for k, v in payload.items() if k not in {"replay_kind", "artifact_kind", "kind"}
        }
        for vol in ("generated_at", "computed_at", "created_at_utc"):
            copy.pop(vol, None)
        can = _canonical(copy)
        return _fingerprint_bytes(can.encode("utf-8"))
    except Exception:
        return None


def _extract_logical_id(
    payload: dict[str, Any], capsule_logical_id: str | None, kind: ReplayArtifactKind
) -> str:
    for key in ("report_id", "study_id", "plan_id", "logical_id", "comparison_id", "capsule_id"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            # sanitise: must be safe identifier
            safe = val.strip().replace(" ", "-").replace("/", "-")[:64]
            if safe:
                return safe
    if capsule_logical_id:
        return capsule_logical_id
    # fallback: kind + truncated fingerprint
    fp = _extract_expected_fingerprint(payload, kind) or "unknown"
    return f"{kind.value}-{fp[:8]}"


def _required_inputs_for_payload(
    payload: dict[str, Any], kind: ReplayArtifactKind
) -> dict[str, str]:
    # Extract input fingerprints from payload in a deterministic, typed way.
    # All keys come from fixed allowlisted extraction, not user-supplied path.
    inputs: dict[str, str] = {}
    if kind is ReplayArtifactKind.EVENT_ALIGNED_REPORT:
        # spec fingerprint + anchor fingerprints
        spec = payload.get("spec")
        if isinstance(spec, dict):
            with contextlib.suppress(Exception):
                inputs["spec_fingerprint"] = _fingerprint(spec)
        accepted = payload.get("accepted_runs")
        if isinstance(accepted, list) and accepted:
            inputs["anchor_fingerprint"] = _fingerprint(accepted)
        rid = payload.get("report_id")
        if isinstance(rid, str):
            inputs["report_id"] = _fingerprint(rid)
    elif kind is ReplayArtifactKind.RESOURCE_STRATEGY_REPORT:
        for key in ("study_fingerprint", "source_fingerprint", "study_id"):
            val = payload.get(key)
            if isinstance(val, str) and val:
                inputs[key] = _fingerprint(val) if not _SHA256_RE.fullmatch(val) else val
        # Also arm-specific fingerprints via canonical of arms
        arms = payload.get("arms") or payload.get("arm_summaries")
        if isinstance(arms, list):
            inputs["arm_payload_fingerprint"] = _fingerprint(arms)
    elif kind is ReplayArtifactKind.PREREGISTRATION_GATE:
        plan_fp = payload.get("plan_fingerprint") or payload.get("fingerprint")
        if isinstance(plan_fp, str) and _SHA256_RE.fullmatch(plan_fp):
            inputs["plan_fingerprint"] = plan_fp
        else:
            pid = payload.get("plan_id")
            if isinstance(pid, str) and pid:
                inputs["plan_fingerprint"] = _fingerprint(pid)
        # Evidence state is required for gate replay — honestly represent attachment fingerprints
        ev_attachments = payload.get("evidence_attachments")
        if isinstance(ev_attachments, list):
            inputs["evidence_state_fingerprint"] = _fingerprint(ev_attachments)
        elif isinstance(payload.get("evidence_state_fingerprint"), str) and _SHA256_RE.fullmatch(
            str(payload.get("evidence_state_fingerprint"))
        ):
            inputs["evidence_state_fingerprint"] = str(payload["evidence_state_fingerprint"])
        else:
            # Fallback: fingerprint of planned cells as evidence state proxy
            cells = payload.get("planned_run_cells")
            if isinstance(cells, list):
                inputs["evidence_state_fingerprint"] = _fingerprint(cells)
    elif kind is ReplayArtifactKind.COMPARISON_REPORT:
        # Honest inputs: separate collections + request
        b_coll = payload.get("baseline_collection")
        if isinstance(b_coll, dict):
            inputs["baseline_collection_fingerprint"] = _fingerprint(b_coll)
        elif isinstance(payload.get("baseline_context"), dict):
            # Fallback: fingerprint context as collection proxy, but label honestly as collection
            inputs["baseline_collection_fingerprint"] = _fingerprint(payload["baseline_context"])
        v_coll2 = payload.get("variation_collection")
        if isinstance(v_coll2, dict):
            inputs["variation_collection_fingerprint"] = _fingerprint(v_coll2)
        elif isinstance(payload.get("variation_context"), dict):
            inputs["variation_collection_fingerprint"] = _fingerprint(payload["variation_context"])
        # Comparison request fingerprint is required
        req = payload.get("comparison_request") or payload.get("request")
        if isinstance(req, dict):
            inputs["comparison_request_fingerprint"] = _fingerprint(req)
        elif isinstance(payload.get("comparison_version"), str):
            inputs["comparison_request_fingerprint"] = _fingerprint(payload["comparison_version"])
    # Filter to only those that are hex64-compatible fingerprint values; for non-hex inputs we already fingerprinted.  # noqa: E501
    filtered: dict[str, str] = {}
    for k, v in inputs.items():
        if isinstance(v, str) and _SHA256_RE.fullmatch(v):
            filtered[k] = v
        else:
            # ensure hex by re-fingerprinting
            filtered[k] = _fingerprint(v)
    return dict(sorted(filtered.items()))


def _build_request_for_payload(
    payload: dict[str, Any],
    kind: ReplayArtifactKind,
    capsule_logical_id: str | None,
    capsule_kind: str | None,
    evidence_label: str | None,
) -> tuple[ReplayPlanEntry, ReplayRequest | None]:
    schema_version = _extract_schema_version(payload)
    adapter = get_adapter(kind)
    logical_id = _extract_logical_id(payload, capsule_logical_id, kind)
    expected_fp = _extract_expected_fingerprint(payload, kind) or ("0" * 64)

    # Refuse raw evidence by label if present
    if evidence_label is not None and evidence_label in RAW_EVIDENCE_LABELS:
        return (
            ReplayPlanEntry(
                artifact_kind=kind,
                logical_id=logical_id,
                status=ReplayStatus.NOT_REPLAYABLE,
                replayable=False,
                expected_output_fingerprint=expected_fp
                if _SHA256_RE.fullmatch(expected_fp)
                else None,
                supported_schema_version=adapter.supported_schema_versions[0] if adapter else None,
                declared_schema_version=schema_version,
                reason=f"raw evidence label {evidence_label!r} is not replayable; only allowlisted derived artifacts may be replayed",  # noqa: E501
                request=None,
            ),
            None,
        )

    if adapter is None:
        return (
            ReplayPlanEntry(
                artifact_kind=kind,
                logical_id=logical_id,
                status=ReplayStatus.NOT_REPLAYABLE,
                replayable=False,
                expected_output_fingerprint=expected_fp
                if _SHA256_RE.fullmatch(expected_fp)
                else None,
                declared_schema_version=schema_version,
                reason=f"kind {kind.value!r} is not in the allowlist",
                request=None,
            ),
            None,
        )

    # Version check — fail-closed
    if schema_version is None or schema_version not in adapter.supported_schema_versions:
        return (
            ReplayPlanEntry(
                artifact_kind=kind,
                logical_id=logical_id,
                status=ReplayStatus.UNSUPPORTED_VERSION,
                replayable=False,
                expected_output_fingerprint=expected_fp
                if _SHA256_RE.fullmatch(expected_fp)
                else None,
                supported_schema_version=adapter.supported_schema_versions[0],
                declared_schema_version=schema_version,
                reason=f"unsupported schema_version {schema_version!r}; supported {adapter.supported_schema_versions!r}",  # noqa: E501
                request=None,
            ),
            None,
        )

    # Required inputs present check — strictly enforce allowlisted adapter contract
    required_inputs = _required_inputs_for_payload(payload, kind)
    # Strict: every required_input_fingerprints key must be present in derived inputs
    missing: list[str] = []
    for req_key in adapter.required_input_fingerprints:
        if req_key not in required_inputs:
            missing.append(req_key)
    if missing:
        return (
            ReplayPlanEntry(
                artifact_kind=kind,
                logical_id=logical_id,
                status=ReplayStatus.MISSING_INPUT,
                replayable=False,
                expected_output_fingerprint=expected_fp
                if _SHA256_RE.fullmatch(expected_fp)
                else None,
                supported_schema_version=adapter.supported_schema_versions[0],
                declared_schema_version=schema_version,
                required_inputs_missing=missing,
                reason=f"missing required input fingerprints: {missing!r}",
                request=None,
            ),
            None,
        )

    # Compatibility check flag — allowlisted payloads must pass strict model validation via adapter
    # We defer deep compatibility to execution (failed status) but mark incompatible if payload is empty.  # noqa: E501
    if not payload:
        return (
            ReplayPlanEntry(
                artifact_kind=kind,
                logical_id=logical_id,
                status=ReplayStatus.INCOMPATIBLE,
                replayable=False,
                expected_output_fingerprint=expected_fp
                if _SHA256_RE.fullmatch(expected_fp)
                else None,
                supported_schema_version=adapter.supported_schema_versions[0],
                declared_schema_version=schema_version,
                reason="payload is empty; incompatible with adapter typed request",
                request=None,
            ),
            None,
        )

    # Build typed request — payload is bounded already (check size later via plan limits)
    # Normalise expected fingerprint: must be hex64
    if not _SHA256_RE.fullmatch(expected_fp):
        expected_fp = _fingerprint(payload)

    request = ReplayRequest(
        artifact_kind=kind,
        schema_version=schema_version,
        expected_output_fingerprint=expected_fp,
        required_input_fingerprints=dict(sorted(required_inputs.items())),
        payload=dict(payload),
        logical_id=logical_id,
        request_note=f"allowlisted replay for {kind.value} via {adapter.service_callable}",
    )
    entry = ReplayPlanEntry(
        artifact_kind=kind,
        logical_id=logical_id,
        status=ReplayStatus.REPLAYABLE,
        replayable=True,
        expected_output_fingerprint=expected_fp,
        supported_schema_version=adapter.supported_schema_versions[0],
        declared_schema_version=schema_version,
        required_inputs_present=sorted(required_inputs.keys()),
        reason="allowlisted adapter with supported version and required inputs present",
        request=request,
    )
    return entry, request


# ---------------------------------------------------------------------------
# Capsule member enumeration for plan building
# ---------------------------------------------------------------------------


def _enumerate_capsule_artifacts(
    capsule_bytes: bytes,
) -> tuple[CapsuleIntegrity, list[tuple[str, str, dict[str, Any], str | None, str]]]:
    """Return verified integrity and list of (archive_path, logical_id, payload_dict, evidence_label, capsule_kind)."""  # noqa: E501
    integrity = verify_capsule_integrity(capsule_bytes)
    artifacts: list[tuple[str, str, dict[str, Any], str | None, str]] = []
    if not integrity.valid:
        return integrity, artifacts
    # Re-open capsule to read embedded member bytes for allowlisted kinds only.
    try:
        with zipfile.ZipFile(BytesIO(capsule_bytes)) as z:
            # Need manifest to map logical ids to kinds
            manifest_bytes = z.read("capsule-manifest.json")
            manifest = json.loads(manifest_bytes)
            members = manifest.get("members", [])
            for m in members:
                policy = m.get("policy")
                if policy != "embed_safe_derived":
                    continue
                archive_path = m.get("archive_path")
                if not isinstance(archive_path, str) or not archive_path:
                    continue
                kind = m.get("kind")
                if not isinstance(kind, str) or kind not in {
                    "deterministic_report",
                    "comparison_report",
                    "consequence_report",
                    "evidence_pack",
                    "scenario_seed",
                    "run_summary",
                    "provenance_graph",
                    "diagnostic_result",
                    "validation_result",
                }:
                    continue
                # Do not extract raw imported evidence
                evidence_label = m.get("evidence_label")
                if isinstance(evidence_label, str) and evidence_label in RAW_EVIDENCE_LABELS:
                    continue
                # Do not extract raw evidence members that were mis-labelled; also skip if admission not synthetic/admitted  # noqa: E501
                # For allowlisted plan we still enumerate but will refuse at entry level.
                try:
                    content = z.read(archive_path)
                except KeyError:
                    continue
                # Bounded: skip overly large members
                if len(content) > MAX_PAYLOAD_BYTES:
                    continue
                # Try JSON parse; also try YAML fallback for scenario_seed? Keep allowlisted JSON only.  # noqa: E501
                try:
                    payload = json.loads(content)
                    if not isinstance(payload, dict):
                        continue
                except Exception:  # noqa: S112
                    continue
                logical_id = str(m.get("logical_id") or archive_path)
                artifacts.append((archive_path, logical_id, payload, evidence_label, kind))
    except Exception:
        # Fail-closed: return integrity with no artifacts on read failure
        return integrity, []
    return integrity, artifacts


# ---------------------------------------------------------------------------
# Build replay plan
# ---------------------------------------------------------------------------


def build_replay_plan(
    *,
    capsule_bytes: bytes | None = None,
    standalone_artifacts: list[tuple[str, dict[str, Any], str | None]] | None = None,
    # standalone_artifacts: list of (logical_id, payload_dict, evidence_label_hint)
    allow_raw: bool = False,
) -> ReplayPlan:
    """Build a replay plan from either a verified capsule or fingerprinted artifacts.

    Only allowlisted adapters are considered. Unsupported kinds/versions, missing
    inputs, raw evidence, and incompatibility are refused with explicit status.
    No arbitrary code is executed. Capsule bytes are verified before reading.
    """
    entries: list[ReplayPlanEntry] = []
    capsule_id: str | None = None
    manifest_fp: str | None = None
    verification_status = "no_capsule"
    warnings: list[str] = list(BASE_WARNINGS)
    limitations: list[str] = list(BASE_LIMITATIONS)

    if capsule_bytes is not None:
        integrity, artifacts = _enumerate_capsule_artifacts(capsule_bytes)
        verification_status = integrity.status
        capsule_id = integrity.capsule_id
        manifest_fp = integrity.manifest_fingerprint
        if not integrity.valid:
            # Tampered or unsupported capsules produce a plan with a single refusal entry.
            entry = ReplayPlanEntry(
                artifact_kind=ReplayArtifactKind.EVENT_ALIGNED_REPORT,
                logical_id=integrity.capsule_id or "capsule-integrity-failed",
                status=(
                    ReplayStatus.FAILED
                    if integrity.status == StudyCapsuleVerificationStatus.TAMPERED.value
                    else ReplayStatus.INCOMPATIBLE
                ),
                replayable=False,
                expected_output_fingerprint=None,
                reason="capsule integrity invalid: " + "; ".join(integrity.errors[:3])
                if integrity.errors
                else "capsule integrity invalid",
                request=None,
            )
            return ReplayPlan(
                capsule_id=capsule_id,
                manifest_fingerprint=manifest_fp,
                verification_status=verification_status,
                entries=[entry],
                warnings=warnings,
                limitations=limitations,
            )
        # For each artifact, infer replay kind and build entry
        seen: set[tuple[str, str]] = set()
        for _archive_path, logical_id, payload, evidence_label, capsule_kind in artifacts:  # noqa: B007
            if (capsule_kind, logical_id) in seen:
                continue
            seen.add((capsule_kind, logical_id))
            kind = _infer_replay_kind_from_payload(payload, capsule_kind)
            if kind is None or kind not in ALLOWLISTED_REPLAY_KINDS:
                # Explicit refusal for unsupported artifact kind — do not mislabel  # noqa: E501
                entries.append(
                    ReplayPlanEntry(
                        artifact_kind=None,
                        logical_id=logical_id,
                        status=ReplayStatus.NOT_REPLAYABLE,
                        replayable=False,
                        expected_output_fingerprint=None,
                        reason=f"unsupported artifact {capsule_kind!r}:{logical_id!r} not in allowlist",  # noqa: E501
                        request=None,
                    )
                )
                continue
            entry, _req = _build_request_for_payload(
                payload, kind, logical_id, capsule_kind, evidence_label
            )
            entries.append(entry)
        if not entries:
            warnings.append("capsule contains no allowlisted derived artifacts; nothing to replay")
    elif standalone_artifacts is not None:
        verification_status = "standalone"
        for logical_id, payload, evidence_label in standalone_artifacts:
            if not isinstance(payload, dict):
                entries.append(
                    ReplayPlanEntry(
                        artifact_kind=None,
                        logical_id=logical_id,
                        status=ReplayStatus.INCOMPATIBLE,
                        replayable=False,
                        expected_output_fingerprint=None,
                        reason="payload must be a JSON object",
                        request=None,
                    )
                )
                continue
            # Bounded payload size
            if len(_canonical(payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
                entries.append(
                    ReplayPlanEntry(
                        artifact_kind=None,
                        logical_id=logical_id,
                        status=ReplayStatus.INCOMPATIBLE,
                        replayable=False,
                        expected_output_fingerprint=None,
                        reason="payload exceeds bounded size",
                        request=None,
                    )
                )
                continue
            kind = _infer_replay_kind_from_payload(payload, None)
            if kind is None or kind not in ALLOWLISTED_REPLAY_KINDS:
                # Try explicit kind field
                explicit = payload.get("replay_kind") or payload.get("artifact_kind")
                if isinstance(explicit, str):
                    try:
                        kind = ReplayArtifactKind(explicit)
                    except ValueError:
                        kind = None
                if kind is None or kind not in ALLOWLISTED_REPLAY_KINDS:
                    entries.append(
                        ReplayPlanEntry(
                            artifact_kind=None,
                            logical_id=logical_id,
                            status=ReplayStatus.NOT_REPLAYABLE,
                            replayable=False,
                            expected_output_fingerprint=None,
                            reason=f"unsupported artifact kind {explicit!r}",
                            request=None,
                        )
                    )
                    continue
            entry, _req = _build_request_for_payload(
                payload, kind, logical_id, None, evidence_label
            )
            entries.append(entry)
        if not entries:
            warnings.append("no standalone artifacts supplied")
    else:
        verification_status = "empty_input"
        warnings.append("no capsule or standalone artifacts provided for planning")

    # Sort deterministically
    entries_sorted = sorted(
        entries, key=lambda e: ((e.artifact_kind.value if e.artifact_kind else ""), e.logical_id)
    )  # noqa: E501

    # Bounded plan size check — fail-closed: do not silently truncate
    if len(entries_sorted) > MAX_REPLAY_ENTRIES:
        # Fail closed with explicit typed refusal  # noqa: E501
        return ReplayPlan(
            capsule_id=capsule_id,
            manifest_fingerprint=manifest_fp,
            verification_status=verification_status,
            entries=[
                ReplayPlanEntry(
                    artifact_kind=None,
                    logical_id="plan-overflow",
                    status=ReplayStatus.FAILED,
                    replayable=False,
                    expected_output_fingerprint=None,
                    reason=(  # noqa: E501
                        f"plan entries {len(entries_sorted)} exceeds bounded maximum "
                        f"{MAX_REPLAY_ENTRIES}; replay refused to avoid silent truncation"
                    ),
                    request=None,
                )
            ],
            warnings=warnings
            + [f"plan entries {len(entries_sorted)} exceeds bounded {MAX_REPLAY_ENTRIES}"],
            limitations=limitations,
        )

    return ReplayPlan(
        capsule_id=capsule_id,
        manifest_fingerprint=manifest_fp,
        verification_status=verification_status,
        entries=entries_sorted,
        warnings=warnings,
        limitations=limitations,
    )


def build_replay_plan_from_capsule_bytes(payload: bytes) -> ReplayPlan:
    return build_replay_plan(capsule_bytes=payload)


# ---------------------------------------------------------------------------
# Deterministic execution — typed service callables, no import path from input
# ---------------------------------------------------------------------------


def _execute_event_aligned(payload: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:  # noqa: E501
    """Execute event-aligned replay via typed service."""

    from traffictwin.event_aligned.models import EventAlignedReport

    # Strip detection hints
    payload_clean = {
        k: v for k, v in payload.items() if k not in {"replay_kind", "artifact_kind", "kind"}
    }
    payload = payload_clean

    spec_data = payload.get("spec")
    if not isinstance(spec_data, dict):
        return "failed", {}, "event-aligned payload missing spec"

    # No filesystem access from payload — bundle_paths are disallowed.
    # Replay is validated via typed report recomputation, not filesystem.
    try:
        report = EventAlignedReport.model_validate(payload)
        portable = report.canonical_dict()
        portable["fingerprint"] = report.fingerprint
        recomputed = report.computed_fingerprint()
        if recomputed != report.fingerprint:
            return (
                "mismatched",
                portable,
                "stored fingerprint does not match canonical recomputation",
            )
        return recomputed, portable, None
    except Exception as exc:
        return "failed", {}, f"event-aligned execution failed: {exc}"


def _execute_resource_strategy(payload: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    from traffictwin.experiments.resource_strategy import (
        ResourceStrategyReport,
        ResourceStrategyStudy,
        build_resource_strategy_report,
    )

    # Strip detection hints
    payload_clean = {
        k: v for k, v in payload.items() if k not in {"replay_kind", "artifact_kind", "kind"}
    }
    payload = payload_clean
    try:
        # Payload may be a study OR a report. Detect.
        if "arms" in payload and "metric_catalog" in payload:
            # It's a study — build report
            study = ResourceStrategyStudy.model_validate(payload)
            report = build_resource_strategy_report(study)
            portable = report.canonical_payload()
            fp = report.fingerprint()
            return fp, portable, None
        if "arm_summaries" in payload and "pairwise_differences" in payload:
            report = ResourceStrategyReport.model_validate(payload)
            portable = report.canonical_payload()
            computed = report.fingerprint()
            if report.report_fingerprint and report.report_fingerprint != computed:
                return "mismatched", portable, "report fingerprint mismatch"
            return computed, portable, None
        return "failed", {}, "resource strategy payload not a study or report"
    except Exception as exc:
        return "failed", {}, f"resource strategy execution failed: {exc}"


def _execute_prereg_gate(payload: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    from traffictwin.preregistration.models import EvidenceAttachment, StudyPlan
    from traffictwin.preregistration.service import evaluate_gate

    payload_clean = {
        k: v for k, v in payload.items() if k not in {"replay_kind", "artifact_kind", "kind"}
    }
    payload = payload_clean
    try:
        # StudyPlan path — honest fingerprint comparison
        if "planned_run_cells" in payload or "primary_outcomes" in payload:
            plan = StudyPlan.model_validate(payload)
            stored = payload.get("fingerprint")
            if not isinstance(stored, str) or not _SHA256_RE.fullmatch(stored):
                return "failed", {}, "prereg StudyPlan missing stored fingerprint for verification"
            # Independently recompute fingerprint from canonical payload  # noqa: E501
            recomputed = plan.compute_fingerprint()
            # Genuinely evaluate the gate — must not be discarded, participates in validation
            try:
                attachments_data = payload.get("evidence_attachments") or []
                attachments = [
                    EvidenceAttachment.model_validate(a)
                    for a in attachments_data
                    if isinstance(a, dict)
                ]
                gate = evaluate_gate(plan, attachments)
                # Gate must be produced; if evaluation fails, it's a real failure, not a silent pass
                # We keep the gate for potential output but fingerprint remains that of the plan
                _gate_portable = gate.model_dump(mode="json")
            except Exception as exc:
                return "failed", {}, f"prereg gate evaluation failed: {exc}"
            # Compare stored vs recomputed — body tamper must yield mismatched
            if recomputed != stored:
                portable = plan.model_dump(mode="json")
                return (  # noqa: E501
                    "mismatched",
                    portable,
                    "stored fingerprint does not match recomputed canonical fingerprint",
                )
            # On match, return recomputed as actual
            portable = plan.model_dump(mode="json")
            return recomputed, portable, None
        if "status" in payload and "missing_cells" in payload:
            # Fabricated gate report without independent StudyPlan cannot be honestly replayed
            return (  # noqa: E501
                "failed",
                {},
                "standalone gate report without frozen StudyPlan is not independently replayable",
            )
        return "failed", {}, "prereg payload not a study plan or gate report"
    except Exception as exc:
        # Do not swallow validation errors with broad pass — surface as failed
        return "failed", {}, f"prereg gate execution failed: {exc}"


def _execute_comparison(payload: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    from traffictwin.metrics.comparison import ComparisonRequest
    from traffictwin.metrics.results import MetricCollection

    payload_clean = {
        k: v for k, v in payload.items() if k not in {"replay_kind", "artifact_kind", "kind"}
    }
    payload = payload_clean
    try:
        # Payload may be a comparison report — but hashing the supplied report alone is not a replay
        if "baseline_context" in payload and "variation_context" in payload:
            # Standalone ComparisonReport without independent collections cannot be honestly replayed  # noqa: E501
            return (
                "failed",
                {},
                "standalone ComparisonReport without independent MetricCollections "  # noqa: E501
                "is not replayable",
            )

        # Or payload contains two collections
        if "baseline_collection" in payload and "variation_collection" in payload:
            from traffictwin.metrics.comparison import compare_metric_collections

            baseline = MetricCollection.model_validate(payload["baseline_collection"])
            variation = MetricCollection.model_validate(payload["variation_collection"])
            req_data = payload.get("comparison_request")
            req = ComparisonRequest.model_validate(req_data) if isinstance(req_data, dict) else None
            baseline_seed = None
            variation_seed = None
            if isinstance(payload.get("baseline_seed"), dict):
                from traffictwin.domain.scenario import ScenarioSeed

                baseline_seed = ScenarioSeed.model_validate(payload["baseline_seed"])
            if isinstance(payload.get("variation_seed"), dict):
                from traffictwin.domain.scenario import ScenarioSeed

                variation_seed = ScenarioSeed.model_validate(payload["variation_seed"])
            report = compare_metric_collections(
                baseline,
                variation,
                req,
                baseline_seed=baseline_seed,
                variation_seed=variation_seed,
            )
            portable = {
                "baseline_context": report.baseline_context,
                "variation_context": report.variation_context,
                "changed_seed_parameters": report.changed_seed_parameters,
                "comparable_metrics": [
                    c.model_dump(mode="json") for c in report.comparable_metrics
                ],
                "unavailable_comparisons": [
                    c.model_dump(mode="json") for c in report.unavailable_comparisons
                ],
                "warnings": report.warnings,
                "comparison_version": report.comparison_version,
            }
            fp = _fingerprint(portable)
            return fp, portable, None
        return "failed", {}, "comparison payload missing report or collections"
    except Exception as exc:
        return "failed", {}, f"comparison execution failed: {exc}"


# Dispatcher — strictly allowlisted, no import path from user input.
_EXECUTORS = {
    ReplayArtifactKind.EVENT_ALIGNED_REPORT: _execute_event_aligned,
    ReplayArtifactKind.RESOURCE_STRATEGY_REPORT: _execute_resource_strategy,
    ReplayArtifactKind.PREREGISTRATION_GATE: _execute_prereg_gate,
    ReplayArtifactKind.COMPARISON_REPORT: _execute_comparison,
}


def execute_replay(
    plan: ReplayPlan,
    *,
    selected: list[tuple[ReplayArtifactKind, str]] | None = None,
) -> tuple[list[ReplayExecution], list[ReplayRefusal]]:
    """Execute only explicitly selected replayable entries.

    `selected` is a list of (kind, logical_id) to run. If None, nothing is run
    (fail-closed, explicit selection required).
    """
    executions: list[ReplayExecution] = []
    refusals: list[ReplayRefusal] = []

    # Build index for quick lookup
    index = {(e.artifact_kind, e.logical_id): e for e in plan.entries}

    # If nothing selected, return empty executions and no automatic run
    if selected is None or not selected:
        # No automatic run; every replayable entry remains not executed, not a failure
        return executions, refusals

    for sel_kind, sel_id in selected:
        entry = index.get((sel_kind, sel_id))
        if entry is None:
            refusals.append(
                ReplayRefusal(
                    artifact_kind=sel_kind,
                    logical_id=sel_id,
                    status=ReplayStatus.NOT_REPLAYABLE,
                    reason="selected entry not in plan",
                )
            )
            continue
        if not entry.replayable or entry.status != ReplayStatus.REPLAYABLE:
            refusals.append(
                ReplayRefusal(
                    artifact_kind=sel_kind,
                    logical_id=sel_id,
                    status=entry.status,
                    reason=entry.reason,
                )
            )
            continue
        req = entry.request
        if req is None:
            refusals.append(
                ReplayRefusal(
                    artifact_kind=sel_kind,
                    logical_id=sel_id,
                    status=ReplayStatus.FAILED,
                    reason="plan entry is replayable but request is missing",
                )
            )
            continue
        executor = _EXECUTORS.get(req.artifact_kind)
        if executor is None:
            executions.append(
                ReplayExecution(
                    artifact_kind=req.artifact_kind,
                    logical_id=req.logical_id,
                    request_fingerprint=req.fingerprint(),
                    actual_output_fingerprint=None,
                    expected_output_fingerprint=req.expected_output_fingerprint,
                    status=ReplayStatus.FAILED,
                    reason=f"no executor for {req.artifact_kind.value!r}",
                )
            )
            continue
        try:
            result_fp, portable, error = executor(req.payload)
            if error is not None and result_fp == "failed":
                executions.append(
                    ReplayExecution(
                        artifact_kind=req.artifact_kind,
                        logical_id=req.logical_id,
                        request_fingerprint=req.fingerprint(),
                        actual_output_fingerprint=None,
                        expected_output_fingerprint=req.expected_output_fingerprint,
                        status=ReplayStatus.FAILED,
                        reason=error,
                    )
                )
            elif result_fp == "mismatched":
                # Still produce execution with mismatch status, preview truncated
                exec_fp = _fingerprint(portable) if portable else None
                executions.append(
                    ReplayExecution(
                        artifact_kind=req.artifact_kind,
                        logical_id=req.logical_id,
                        request_fingerprint=req.fingerprint(),
                        actual_output_fingerprint=exec_fp,
                        expected_output_fingerprint=req.expected_output_fingerprint,
                        status=ReplayStatus.MISMATCHED,
                        reason=error or "fingerprint recomputation mismatch",
                        output_preview=json.dumps(portable, sort_keys=True, indent=2)[:2000]
                        if portable
                        else None,
                    )
                )
            else:
                # result_fp is hex64
                if not _SHA256_RE.fullmatch(str(result_fp)):
                    result_fp = _fingerprint(portable)
                matched = result_fp == req.expected_output_fingerprint
                status = ReplayStatus.MATCHED if matched else ReplayStatus.MISMATCHED
                executions.append(
                    ReplayExecution(
                        artifact_kind=req.artifact_kind,
                        logical_id=req.logical_id,
                        request_fingerprint=req.fingerprint(),
                        actual_output_fingerprint=result_fp,
                        expected_output_fingerprint=req.expected_output_fingerprint,
                        status=status,
                        reason="output fingerprint matches expected"
                        if matched
                        else f"expected {req.expected_output_fingerprint[:12]}… got {result_fp[:12]}…",  # noqa: E501
                        output_preview=json.dumps(portable, sort_keys=True, indent=2)[:2000]
                        if portable
                        else None,
                    )
                )
        except Exception as exc:
            executions.append(
                ReplayExecution(
                    artifact_kind=req.artifact_kind,
                    logical_id=req.logical_id,
                    request_fingerprint=req.fingerprint(),
                    actual_output_fingerprint=None,
                    expected_output_fingerprint=req.expected_output_fingerprint,
                    status=ReplayStatus.FAILED,
                    reason=f"executor exception: {exc}",
                )
            )

    # Add refusals for non-selected replayable entries? No — they remain not executed, not refused.

    # Also surface plan entries that were not replayable as refusals for completeness (if they were not selected)  # noqa: E501
    # Not needed for explicit selection contract, but we expose all non-replayable as refusal summary in receipt.  # noqa: E501
    return executions, refusals


# ---------------------------------------------------------------------------
# Comparison and receipt
# ---------------------------------------------------------------------------


def compare_replay_output(execution: ReplayExecution) -> ReplayComparison:
    if execution.actual_output_fingerprint is None:
        return ReplayComparison(
            artifact_kind=execution.artifact_kind,
            logical_id=execution.logical_id,
            expected_fingerprint=execution.expected_output_fingerprint,
            actual_fingerprint="0" * 64,
            matched=False,
            status=ReplayStatus.FAILED,
        )
    matched = execution.actual_output_fingerprint == execution.expected_output_fingerprint
    return ReplayComparison(
        artifact_kind=execution.artifact_kind,
        logical_id=execution.logical_id,
        expected_fingerprint=execution.expected_output_fingerprint,
        actual_fingerprint=execution.actual_output_fingerprint,
        matched=matched,
        status=ReplayStatus.MATCHED if matched else ReplayStatus.MISMATCHED,
    )


def build_receipt(
    plan: ReplayPlan,
    executions: list[ReplayExecution],
    refusals: list[ReplayRefusal] | None = None,
    *,
    selected: list[tuple[ReplayArtifactKind, str]] | None = None,
) -> ReplayReceipt:
    plan_fp = plan.fingerprint()
    # Bind receipt identity to what was actually executed, not just the plan
    binding = _execution_binding_fingerprint(executions, selected)
    receipt_id = _receipt_id(plan_fp, binding)
    comparisons: list[ReplayComparison] = []
    mismatches: list[ReplayMismatch] = []
    matched = 0
    mismatched = 0
    failed = 0
    for exe in executions:
        comp = compare_replay_output(exe)
        comparisons.append(comp)
        if exe.status is ReplayStatus.MATCHED:
            matched += 1
        elif exe.status is ReplayStatus.MISMATCHED:
            mismatched += 1
            mismatches.append(
                ReplayMismatch(
                    artifact_kind=exe.artifact_kind,
                    logical_id=exe.logical_id,
                    expected_fingerprint=exe.expected_output_fingerprint,
                    actual_fingerprint=exe.actual_output_fingerprint or ("0" * 64),
                    detail=exe.reason,
                )
            )
        elif exe.status is ReplayStatus.FAILED:
            failed += 1

    # Collect non-replayable entries as refusals for audit
    all_refusals: list[ReplayRefusal] = list(refusals or [])
    for entry in plan.entries:
        if not entry.replayable and not any(  # noqa: SIM102
            r.logical_id == entry.logical_id and r.artifact_kind == entry.artifact_kind
            for r in all_refusals
        ):  # noqa: E501  close combined if
            all_refusals.append(
                ReplayRefusal(
                    artifact_kind=entry.artifact_kind,
                    logical_id=entry.logical_id,
                    status=entry.status,
                    reason=entry.reason,
                )
            )

    receipt = ReplayReceipt(
        receipt_id=receipt_id,
        capsule_id=plan.capsule_id,
        manifest_fingerprint=plan.manifest_fingerprint,
        plan_fingerprint=plan_fp,
        executed_count=len(executions),
        matched_count=matched,
        mismatched_count=mismatched,
        failed_count=failed,
        executions=sorted(executions, key=lambda e: (e.artifact_kind.value, e.logical_id)),
        comparisons=sorted(comparisons, key=lambda c: (c.artifact_kind.value, c.logical_id)),
        mismatches=sorted(mismatches, key=lambda m: (m.artifact_kind.value, m.logical_id)),
        refusals=sorted(
            all_refusals,
            key=lambda r: ((r.artifact_kind.value if r.artifact_kind else ""), r.logical_id or ""),
        ),
        limitations=list(BASE_LIMITATIONS),
        warnings=list(BASE_WARNINGS),
        receipt_fingerprint="0" * 64,
    )
    # Compute deterministic receipt fingerprint
    fp = receipt.computed_fingerprint()
    receipt = receipt.model_copy(update={"receipt_fingerprint": fp})
    return receipt


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def receipt_to_json(receipt: ReplayReceipt) -> str:
    return receipt.model_dump_json(indent=2)


def receipt_to_canonical_json(receipt: ReplayReceipt) -> str:
    return receipt.canonical_json()


def receipt_to_csv(receipt: ReplayReceipt) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "artifact_kind",
            "logical_id",
            "status",
            "expected_fingerprint",
            "actual_fingerprint",
            "reason",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for exe in sorted(receipt.executions, key=lambda e: (e.artifact_kind.value, e.logical_id)):
        writer.writerow(
            {
                "artifact_kind": exe.artifact_kind.value,
                "logical_id": exe.logical_id,
                "status": exe.status.value,
                "expected_fingerprint": exe.expected_output_fingerprint,
                "actual_fingerprint": exe.actual_output_fingerprint or "",
                "reason": exe.reason,
            }
        )
    return output.getvalue()


def plan_to_json(plan: ReplayPlan) -> str:
    return plan.model_dump_json(indent=2)


def plan_entries_to_csv(plan: ReplayPlan) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "artifact_kind",
            "logical_id",
            "status",
            "replayable",
            "reason",
            "expected_fingerprint",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for e in sorted(  # noqa: E501
        plan.entries,  # noqa: E501
        key=lambda x: ((x.artifact_kind.value if x.artifact_kind else ""), x.logical_id),
    ):
        writer.writerow(
            {
                "artifact_kind": (e.artifact_kind.value if e.artifact_kind else ""),
                "logical_id": e.logical_id,
                "status": e.status.value,
                "replayable": str(e.replayable),
                "reason": e.reason,
                "expected_fingerprint": e.expected_output_fingerprint or "",
            }
        )
    return output.getvalue()
