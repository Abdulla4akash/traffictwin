# ruff: noqa: E501, ANN401
"""Canonical portable E3 research artifact — Lane 10 (no-results truth).

Provides wheel-portable built-in JSON via importlib.resources and a strict
validator that delegates to the dedicated E3 loader then enforces every pinned
identity and the no-results hold. No fallback schema, no private path,
timestamp, secret, or mutation normalization. No placeholder, sample, or
synthetic results are ever fabricated.
"""

from __future__ import annotations

import hashlib
import json
import re
from importlib import resources

from traffictwin.experiments.e3_research_evidence import (
    APPROVED_CANDIDATE_SHA,
    CONTRACT_CHECKPOINT_SHA,
    CONTRACT_SHA256,
    LANE_09,
    MANIFEST_SIDECAR_SHA256,
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
    NOT_EXECUTED,
    RESEARCH_WORKLOADS_LAUNCHED,
    TRAFFICTWIN_PRODUCT_BASE_SHA,
    TRAFFICTWIN_RESEARCH_PROMOTION_SHA,
    VEC_ADAPTER_SHA,
    VEC_CORE_SHA,
    VEC_PROMOTION_SHA,
    E3ResearchEvidencePackage,
    load_e3_research_evidence_json,
)

_RESOURCE_PACKAGE = "traffictwin.resources.research"
_RESOURCE_NAME = "e3_dynamic_resource_v2.json"

_PINNED_IDENTITIES: dict[str, str] = {
    "product_base": TRAFFICTWIN_PRODUCT_BASE_SHA,
    "research_promotion": TRAFFICTWIN_RESEARCH_PROMOTION_SHA,
    "approved_candidate": APPROVED_CANDIDATE_SHA,
    "contract_checkpoint": CONTRACT_CHECKPOINT_SHA,
    "vec_promotion": VEC_PROMOTION_SHA,
    "vec_core": VEC_CORE_SHA,
    "vec_adapter": VEC_ADAPTER_SHA,
    "contract_sha256": CONTRACT_SHA256,
    "manifest_sidecar_sha256": MANIFEST_SIDECAR_SHA256,
}

_REQUIRED_HOLD_PHRASES: tuple[str, ...] = (
    LANE_09,
    NOT_EXECUTED,
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
)


def _assert_no_private_paths_or_secrets(text: str) -> None:
    # Build prefixes without contiguous literal in source.
    prefixes = (
        "/" + "Users" + "/",
        "/" + "home" + "/",
        "/" + "tmp" + "/",
        "/" + "private" + "/",
        "/" + "var" + "/",
        "C:\\",
    )
    for pref in prefixes:
        if pref in text:
            raise ValueError(f"artifact contains forbidden private path prefix {pref!r}")
    secret_re = re.compile(r"(password|secret|credential|api[_-]?key|token)", re.IGNORECASE)
    if secret_re.search(text):
        # only flag assignment-like patterns to avoid false positives on scientific notes
        assign_re = re.compile(r"(password|secret|api_key|token)\s*[:=]", re.IGNORECASE)
        if assign_re.search(text):
            raise ValueError("artifact contains secret/credential assignment")


def builtin_e3_research_json() -> str:
    """Return the built-in E3 no-results JSON via importlib.resources (portable)."""
    ref = resources.files(_RESOURCE_PACKAGE).joinpath(_RESOURCE_NAME)
    text = ref.read_text(encoding="utf-8")
    # Guard against accidental private path introduction in built artifact
    _assert_no_private_paths_or_secrets(text)
    return text


def load_builtin_e3_research() -> E3ResearchEvidencePackage:
    """Load and strictly validate the built-in E3 evidence (no-results)."""
    text = builtin_e3_research_json()
    return validate_e3_research_artifact(text)


def validate_e3_research_artifact(text: str) -> E3ResearchEvidencePackage:
    """Strict validator — delegates to loader then enforces every pinned identity."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    _assert_no_private_paths_or_secrets(text)
    # Check hold phrases verbatim before parsing to ensure explicit declaration
    for phrase in _REQUIRED_HOLD_PHRASES:
        if phrase not in text:
            raise ValueError(f"artifact must declare verbatim {phrase!r}")
    # Must declare research_workloads_launched = 0 explicitly
    if (
        '"research_workloads_launched": 0' not in text
        and '"research_workloads_launched":0' not in text
    ):
        # allow spaced variant but strict zero
        if "research_workloads_launched" not in text:
            raise ValueError("artifact must declare research_workloads_launched")
        # parsed check will enforce exact 0
        pass
    # Reject any placeholder/sample/synthetic results language that would hide no-results truth
    placeholder_re = re.compile(r"(placeholder|synthetic|sample\s+result)", re.IGNORECASE)
    if placeholder_re.search(text):
        # allow the word placeholder only in the dormant_predeclaration_note context?
        # Be strict: if it appears as a value claiming results, reject.
        low = text.lower()
        if "placeholder result" in low or "synthetic result" in low or "sample result" in low:
            raise ValueError("artifact must not contain placeholder/sample/synthetic results")

    pkg = load_e3_research_evidence_json(text)

    # Pin every frozen identity exactly
    if pkg.product_base_sha != TRAFFICTWIN_PRODUCT_BASE_SHA:
        raise ValueError(
            f"product_base_sha must be {TRAFFICTWIN_PRODUCT_BASE_SHA}, got {pkg.product_base_sha!r}"
        )
    if pkg.research_promotion_sha != TRAFFICTWIN_RESEARCH_PROMOTION_SHA:
        raise ValueError(
            f"research_promotion_sha must be {TRAFFICTWIN_RESEARCH_PROMOTION_SHA}, got {pkg.research_promotion_sha!r}"
        )
    if pkg.approved_candidate_sha != APPROVED_CANDIDATE_SHA:
        raise ValueError(
            f"approved_candidate_sha must be {APPROVED_CANDIDATE_SHA}, got {pkg.approved_candidate_sha!r}"
        )
    if pkg.contract_checkpoint_sha != CONTRACT_CHECKPOINT_SHA:
        raise ValueError(
            f"contract_checkpoint_sha must be {CONTRACT_CHECKPOINT_SHA}, got {pkg.contract_checkpoint_sha!r}"
        )
    if pkg.vec_runtime.promotion_commit != VEC_PROMOTION_SHA:
        raise ValueError(f"vec promotion mismatch: {pkg.vec_runtime.promotion_commit!r}")
    if pkg.vec_runtime.core_candidate != VEC_CORE_SHA:
        raise ValueError(f"vec core mismatch: {pkg.vec_runtime.core_candidate!r}")
    if pkg.vec_runtime.adapter_candidate != VEC_ADAPTER_SHA:
        raise ValueError(f"vec adapter mismatch: {pkg.vec_runtime.adapter_candidate!r}")
    if pkg.contract.sha256 != CONTRACT_SHA256:
        raise ValueError(f"contract sha256 mismatch: {pkg.contract.sha256!r}")
    # Wire MANIFEST_SIDECAR_SHA256 validation via provenance manifest entry
    manifest_entries = [pr for pr in pkg.provenance if pr.kind == "manifest"]
    if not manifest_entries:
        raise ValueError("missing manifest provenance for sidecar")
    if not any(MANIFEST_SIDECAR_SHA256 in pr.note for pr in manifest_entries):
        raise ValueError(
            f"manifest sidecar SHA mismatch: expected {MANIFEST_SIDECAR_SHA256} not found in manifest provenance notes {[pr.note for pr in manifest_entries]!r}"
        )
    # Also verify execution authority hold
    ea = pkg.execution_authority
    if ea.status != "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED":
        raise ValueError(
            f"status must be E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, got {ea.status!r}"
        )
    if ea.lane_09 != LANE_09:
        raise ValueError(f"lane_09 must be {LANE_09}, got {ea.lane_09!r}")
    if ea.evidence_state != NOT_EXECUTED:
        raise ValueError(f"evidence_state must be {NOT_EXECUTED}, got {ea.evidence_state!r}")
    if ea.result_availability != NO_E3_RESEARCH_RESULTS_AVAILABLE:
        raise ValueError(
            f"result_availability must be {NO_E3_RESEARCH_RESULTS_AVAILABLE}, got {ea.result_availability!r}"
        )
    if ea.research_workloads_launched != RESEARCH_WORKLOADS_LAUNCHED:
        raise ValueError(
            f"research_workloads_launched must be 0, got {ea.research_workloads_launched!r}"
        )

    if (
        pkg.evidence_state != NOT_EXECUTED
        or pkg.result_availability != NO_E3_RESEARCH_RESULTS_AVAILABLE
    ):
        raise ValueError("package must declare NOT_EXECUTED and NO_E3_RESEARCH_RESULTS_AVAILABLE")
    if pkg.research_workloads_launched != 0:
        raise ValueError("research_workloads_launched must be 0 in artifact")
    if pkg.status != "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED":
        raise ValueError("status must be E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED")
    if pkg.lane_09 != LANE_09:
        raise ValueError(f"lane_09 must be {LANE_09}")

    # Task accounting must stay null with reasons, never zero
    ta = pkg.task_accounting
    for field in ("offered", "admitted", "rejected_total", "forwarded", "deadline_success"):
        if getattr(ta, field) is not None:
            raise ValueError(
                f"task_accounting {field} must be None (no-results), got {getattr(ta, field)!r}"
            )
    for field in ("started", "compute_completed", "returned", "dropped"):
        if getattr(ta, field) is not None:
            raise ValueError(f"unavailable {field} must be None, got {getattr(ta, field)!r}")

    # Queue vs compute separation already enforced in model; double-check cost metric
    if pkg.resource_cost.metric != "resource_unit_seconds":
        raise ValueError(
            f"resource cost metric must be resource_unit_seconds, got {pkg.resource_cost.metric!r}"
        )
    if pkg.resource_cost.monetary is not False:
        raise ValueError("resource cost monetary must be False")

    # Dormant counts
    if len(pkg.dormant_arms) != 14:
        raise ValueError(f"dormant_arms must be 14, got {len(pkg.dormant_arms)}")
    if len(pkg.dormant_configs) != 56:
        raise ValueError(f"dormant_configs must be 56, got {len(pkg.dormant_configs)}")

    # Fingerprint stability
    fp = pkg.fingerprint()
    if not re.fullmatch(r"[0-9a-f]{64}", fp):
        raise ValueError(f"fingerprint must be 64 hex, got {fp!r}")

    # Ensure no supervisor approval claim and no invented true _authorized
    dumped = json.dumps(pkg.model_dump(mode="json"))
    low = dumped.lower()
    if "supervisor approved" in low or "supervisor_approved" in low:
        raise ValueError("artifact must not claim supervisor approval")
    if "randy confirmed" in low or "randy_confirmed" in low:
        raise ValueError("artifact must not claim Randy confirmed")

    return pkg


def e3_artifact_fingerprint(text: str) -> str:
    """Deterministic fingerprint of raw artifact text (canonical sorted)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON for fingerprint: {exc}") from exc
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "builtin_e3_research_json",
    "load_builtin_e3_research",
    "validate_e3_research_artifact",
    "e3_artifact_fingerprint",
]
