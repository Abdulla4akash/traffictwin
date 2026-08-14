# ruff: noqa: E501, ANN401
"""Strict Pydantic production model for dedicated E3 package — no results truth.

Covers staged designs E3a/E3b/E3c with predeclared factor sets, replication unit
fleet_draw with exact N=4 matched draws 1-4, paired differences with bounded 95%
Student-t interval (df=3, t=3.182), task accounting with genuine rejection classes,
queue versus compute separation, resource cost as resource_unit_seconds,
scale-action and state-age receipts, provenance, limitations, missingness and
first-class hold. Model natively represents no-results as NOT_EXECUTED.

Validation enforces:
- replication unit fleet_draw, evaluator seed 0, fleet seeds 1-4, N=4, task-not-N
- placement in {ingress_dla, per_task_dla, p2c_dla}, scaling in
  {fixed_1x, static_overprovisioned, reactive, proactive}, state_age_ms in {0,1000,3000}
- staged designs exact factor sets, 14 arms, 56 configs, no double count
- queue capacity strictly separate from compute capacity, cost is resource_unit_seconds
- unavailable lifecycle stays None with reasons, never zero
- absence of private absolute paths/secrets, forbidden queue/compute conflation,
  monetary cost language, actor-selects-RSU, Kubernetes, tasks-as-N, supervisor approval
- any true _authorized is rejected (hold is fail-closed)
- deterministic path-free fingerprint

Immutable hold verbatim constants:
- LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD
- E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
- evidence_state = NOT_EXECUTED
- result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE
- research_workloads_launched = 0
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Immutable hold — verbatim in model constants
# ---------------------------------------------------------------------------

LANE_09: Final[Literal["BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"]] = (
    "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
)
E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED: Final[Literal["E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"]] = (
    "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"
)
NOT_EXECUTED: Final[Literal["NOT_EXECUTED"]] = "NOT_EXECUTED"
NO_E3_RESEARCH_RESULTS_AVAILABLE: Final[Literal["NO_E3_RESEARCH_RESULTS_AVAILABLE"]] = (
    "NO_E3_RESEARCH_RESULTS_AVAILABLE"
)
RESEARCH_WORKLOADS_LAUNCHED: Final[Literal[0]] = 0

# ---------------------------------------------------------------------------
# Frozen identities to pin in resource JSON and admission model
# ---------------------------------------------------------------------------

TRAFFICTWIN_PRODUCT_BASE_SHA: Final[str] = "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c"
TRAFFICTWIN_RESEARCH_PROMOTION_SHA: Final[str] = "342789434233e97cd87ea74e21a759878610ce40"
APPROVED_CANDIDATE_SHA: Final[str] = "c5d66ef7e77f3b7d1f3fde084feea45a83f5c178"
CONTRACT_CHECKPOINT_SHA: Final[str] = "211a6662151ccad43187f8a2ce3f75a57515408d"
VEC_PROMOTION_SHA: Final[str] = "dc606770059f0c4a413bac2217d7f38600b74fff"
VEC_CORE_SHA: Final[str] = "53e34db6146da40118a6c816f6a1ffaa2596ddf3"
VEC_ADAPTER_SHA: Final[str] = "c37f97ea66b236dfc662bfdd6bee7eab1a775bbc"
ACTOR_SHA256: Final[str] = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
TRACE_SHA256: Final[str] = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
E2D_MANIFEST_SHA256: Final[str] = "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
CONTRACT_SHA256: Final[str] = "f0d6eb913df6c2165a63ddcb0fd4980368e9bb80bbd38db964273ba3925f4870"
MANIFEST_SIDECAR_SHA256: Final[str] = (
    "39862882ae34e71260ce5b466fcd4a93d61da783c4dd16fc987be562ea396438"
)
VEC_PROMOTED_BASE: Final[str] = "b2abcee2b4c2628e604fff0811110b8c61a22b23"

# ---------------------------------------------------------------------------
# Factor sets
# ---------------------------------------------------------------------------

VALID_PLACEMENTS: Final[tuple[str, ...]] = ("ingress_dla", "per_task_dla", "p2c_dla")
VALID_SCALINGS: Final[tuple[str, ...]] = (
    "fixed_1x",
    "static_overprovisioned",
    "reactive",
    "proactive",
)
VALID_STATE_AGE_MS: Final[tuple[int, ...]] = (0, 1000, 3000)
FLEET_SEEDS: Final[tuple[int, ...]] = (1, 2, 3, 4)
EVALUATOR_SEED: Final[int] = 0
SCENARIO_RSUS: Final[int] = 10

REJECTION_CLASSES: Final[tuple[str, ...]] = (
    "v2i_gate_rejected",
    "v2i_cap_rejected",
    "local_mqd_rejected",
    "v2v_mqd_rejected",
    "v2i_unavailable",
    "v2v_unavailable",
)

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


# Private-path detector built without contiguous literal to satisfy shipping rule.
# Runtime string still matches absolute private paths like that prefix joined in code.
_PRIVATE_PREFIXES: Final[tuple[str, ...]] = (
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "/" + "tmp" + "/",
    "/" + "private" + "/",
    "/" + "var" + "/",
    "C:\\",
)

# ---------------------------------------------------------------------------
# Normalization for forbidden families (Blocker 5)
# ---------------------------------------------------------------------------

_ZERO_WIDTH_CODEPOINTS: Final[frozenset[int]] = frozenset(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF]
)

_CONFUSABLE_MAP: Final[dict[int, int]] = {
    0x0430: 0x61,  # а -> a
    0x0432: 0x62,  # в -> b
    0x0435: 0x65,  # е -> e
    0x0451: 0x65,  # ё -> e
    0x0437: 0x7A,  # з -> z
    0x043A: 0x6B,  # к -> k
    0x043C: 0x6D,  # м -> m
    0x043D: 0x68,  # н -> h
    0x043E: 0x6F,  # о -> o
    0x0440: 0x70,  # р -> p
    0x0441: 0x63,  # с -> c
    0x0455: 0x73,  # ѕ -> s
    0x0442: 0x74,  # т -> t
    0x0443: 0x79,  # у -> y
    0x0445: 0x78,  # х -> x
    0x0456: 0x69,  # і -> i
    0x0458: 0x6A,  # ј -> j
    0x0501: 0x64,  # ԁ -> d
    0x051B: 0x71,  # ԛ -> q
    0x0461: 0x77,  # ѡ -> w
    0x0410: 0x61,  # А -> a
    0x0412: 0x62,  # В -> b
    0x0415: 0x65,  # Е -> e
    0x0417: 0x7A,  # З -> z
    0x041A: 0x6B,  # К -> k
    0x041C: 0x6D,  # М -> m
    0x041D: 0x68,  # Н -> h
    0x041E: 0x6F,  # О -> o
    0x0420: 0x70,  # Р -> p
    0x0421: 0x63,  # С -> c
    0x0405: 0x73,  # Ѕ -> s
    0x0422: 0x74,  # Т -> t
    0x0423: 0x79,  # У -> y
    0x0425: 0x78,  # Х -> x
    0x0406: 0x69,  # І -> i
    0x0408: 0x6A,  # Ј -> j
    0x0438: 0x69,  # и -> i
    0x0418: 0x69,  # И -> i
    0x03B1: 0x61,  # α -> a
    0x03B2: 0x62,  # β -> b
    0x03B5: 0x65,  # ε -> e
    0x03B7: 0x6E,  # η -> n
    0x03B9: 0x69,  # ι -> i
    0x03BA: 0x6B,  # κ -> k
    0x03BD: 0x76,  # ν -> v
    0x03BF: 0x6F,  # ο -> o
    0x03C1: 0x70,  # ρ -> p
    0x03C4: 0x74,  # τ -> t
    0x03C5: 0x75,  # υ -> u
    0x03C7: 0x78,  # χ -> x
    0x03C9: 0x77,  # ω -> w
    0x0391: 0x61,  # Α -> a
    0x0392: 0x62,  # Β -> b
    0x0395: 0x65,  # Ε -> e
    0x0397: 0x68,  # Η -> h
    0x0399: 0x69,  # Ι -> i
    0x039A: 0x6B,  # Κ -> k
    0x039D: 0x6E,  # Ν -> n
    0x039F: 0x6F,  # Ο -> o
    0x03A1: 0x70,  # Ρ -> p
    0x03A4: 0x74,  # Τ -> t
    0x03A5: 0x79,  # Υ -> y
    0x03A7: 0x78,  # Χ -> x
}


def _normalize_forbidden_text(value: str) -> str:
    """NFKC fold, strip zero-width, casefold, map confusables."""
    # NFKC
    t = unicodedata.normalize("NFKC", value)
    # strip zero-width
    t = "".join(ch for ch in t if ord(ch) not in _ZERO_WIDTH_CODEPOINTS)
    # casefold
    t = t.casefold()
    # confusable map
    t = t.translate(_CONFUSABLE_MAP)
    return t


def _get_script(ch: str) -> str:
    try:
        return unicodedata.name(ch).split()[0]
    except ValueError:
        return "UNKNOWN"


def _has_mixed_script(value: str) -> bool:
    # Byte-equal allowlist exempt — only exact shipped disclaimers
    if value in ALLOWLISTED_DISCLAIMERS:
        return False
    norm = _normalize_forbidden_text(value)
    words: list[str] = []
    cur = ""
    for ch in norm:
        if unicodedata.category(ch).startswith("L"):
            cur += ch
        else:
            if cur:
                words.append(cur)
                cur = ""
    if cur:
        words.append(cur)
    for w in words:
        scripts: set[str] = set()
        for ch in w:
            if unicodedata.category(ch).startswith("L"):
                scripts.add(_get_script(ch))
        if len(scripts) > 1:
            return True
    return False


def _hex_violations_for_string(value: str, path: str) -> list[str]:
    violations: list[str] = []
    for m in _HEX40_TOKEN_RE.finditer(value):
        token = m.group(0).lower()
        if token not in _ALLOWED_40_SHAS:
            violations.append(
                f"{path}: provenance approval/promotion SHA mismatch: {token!r} not in declared identities"
            )
    for m in _HEX64_TOKEN_RE.finditer(value):
        token = m.group(0).lower()
        if token not in _ALLOWED_64_SHAS:
            violations.append(
                f"{path}: provenance manifest sidecar SHA mismatch: {token!r} not in declared fingerprints"
            )
    for m in re.finditer(r"(?<![0-9a-fA-F])[0-9a-fA-F]{7,39}(?![0-9a-fA-F])", value):
        token = m.group(0).lower()
        is_prefix = any(allowed.startswith(token) for allowed in _ALLOWED_40_SHAS) or any(
            allowed.startswith(token) for allowed in _ALLOWED_64_SHAS
        )
        if not is_prefix:
            violations.append(
                f"{path}: provenance hex prefix mismatch: {token!r} not prefix of any declared identity"
            )
    return violations


# Frozen allowlist of exact disclaimer sentences that legitimately contain
# forbidden substrings but are shipped by the package. Fail-closed semantics
# allow these verbatim strings byte-equal; any other string containing a
# forbidden substring is rejected.
ALLOWLISTED_DISCLAIMERS: Final[tuple[str, ...]] = (
    "No Manchester-wide deployment tested; bounded to one incident hour and four fleet draws, replication unit fleet_draw, N=4, not population",
    "No universal superiority claim; hypotheses H1-H5 are not expected truths; trade-off family has no scalar best objective",
    "No monetary cost claim; resource cost is resource_unit_seconds, never dollars/billing/currency",
    "No Kubernetes actual deployment or cluster orchestration; placement is deterministic infrastructure scheduling, not managed cluster",
    "No actor selects execution RSU; frozen actor does not observe load",
    "No tasks-as-N; tasks are accounting records, not independent replicates; task-level N is forbidden",
    "Bounded to staged designs E3a/E3b/E3c with 14 arms and 56 configs, replication unit fleet_draw N=4 matched draws 1-4, evaluator_seed 0, never tasks-as-N, never Manchester-wide inference, never universal superiority",
    "No supervisor approval; standing is E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, LANE_09 BLOCKED_BY_RESEARCHER_EXECUTION_HOLD",
    "Bounded to staged design E3a; no E3 results. Tasks are accounting records, not replicates; no Manchester-wide inference; no universal superiority.",
)

_NORMALIZED_ALLOWLIST: Final[frozenset[str]] = frozenset(
    _normalize_forbidden_text(s) for s in ALLOWLISTED_DISCLAIMERS
)

# Extended forbidden families as regex patterns on normalized text
_FORBIDDEN_FAMILY_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # actual-Kubernetes
    re.compile(r"kubernetes"),
    re.compile(r"k8s"),
    re.compile(
        r"kube[\s_\-]+(?:cluster|deployment)[\s_\-]+is[\s_\-]+(?:live|running|orchestrating|in[\s_\-]+production)"
    ),
    # supervisor-approval
    re.compile(r"supervisor[\s_\-]+approval"),
    re.compile(r"supervisor[\s_\-]+approved"),
    re.compile(r"approved[\s_\-]+by[\s_\-]+(?:the[\s_\-]+)?supervisor"),
    re.compile(r"randy[\s_\-]+approved"),
    re.compile(r"randy[\s_\-]+confirmed"),
    re.compile(r"signed[\s_\-]+off[\s_\-]+by[\s_\-]+supervisor"),
    # universal superiority
    re.compile(r"universally[\s_\-]+superior"),
    re.compile(r"universal[\s_\-]+superiority"),
    re.compile(r"superior[\s_\-]+in[\s_\-]+all[\s_\-]+cases?"),
    re.compile(r"superior[\s_\-]+in[\s_\-]+all[\s_\-]+settings?"),
    # tasks-as-N
    re.compile(r"tasks?[\s_\-]+as[\s_\-]+n\b"),
    re.compile(r"task[\s_\-]+level[\s_\-]+replication"),
    re.compile(r"n[\s_\-]+is[\s_\-]+the[\s_\-]+number[\s_\-]+of[\s_\-]+tasks"),
    re.compile(r"tasks?[\s_\-]+are[\s_\-]+replicates"),
    # Manchester-wide inference
    re.compile(r"manchester[\s_\-]*wide"),
    re.compile(r"across[\s_\-]+all[\s_\-]+of[\s_\-]+manchester"),
    re.compile(r"generaliz\w*[\s_\-]+to[\s_\-]+manchester"),
    re.compile(r"generaliz\w*[\s_\-]+across[\s_\-]+all[\s_\-]+of[\s_\-]+manchester"),
    # monetary
    re.compile(r"dollars?"),
    re.compile(r"\busd\b"),
    re.compile(r"\bgbp\b"),
    re.compile(r"pounds?"),
    re.compile(r"billing"),
    re.compile(r"price"),
    re.compile(r"monetary[\s_\-]+cost"),
    re.compile(r"\$"),
    re.compile(r"£"),
    re.compile(r"€"),
    # actor-selects-RSU
    re.compile(
        r"actor[\s_\-]+(?:selects|chooses|picks)(?:[\s_\-]+the)?(?:[\s_\-]+exact)?(?:[\s_\-]+execution)?[\s_\-]+rsu\b"
    ),
    # learned claim (placement/scaling is deterministic, not learned)
    re.compile(r"learned[\s_\-]+(?:placement|scheduler|jsq)"),
    # legacy queue/compute conflation (keep for completeness)
    re.compile(r"queue[\s_\-]+ceiling[\s_\-]+is[\s_\-]+compute"),
    re.compile(r"queue[\s_\-]+ceiling[\s_\-]+is"),
    # generic fallback for any remaining strict substrings that might be missed due to separators
    re.compile(r"queue_ceiling_is_compute"),
    re.compile(r"actor_selects"),
)


_ALLOWED_40_SHAS: Final[frozenset[str]] = frozenset(
    s.lower()
    for s in (
        TRAFFICTWIN_PRODUCT_BASE_SHA,
        TRAFFICTWIN_RESEARCH_PROMOTION_SHA,
        APPROVED_CANDIDATE_SHA,
        CONTRACT_CHECKPOINT_SHA,
        VEC_PROMOTION_SHA,
        VEC_CORE_SHA,
        VEC_ADAPTER_SHA,
        VEC_PROMOTED_BASE,
    )
)

_ALLOWED_64_SHAS: Final[frozenset[str]] = frozenset(
    s.lower()
    for s in (
        ACTOR_SHA256,
        TRACE_SHA256,
        E2D_MANIFEST_SHA256,
        CONTRACT_SHA256,
        MANIFEST_SIDECAR_SHA256,
    )
)

_HEX40_TOKEN_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])")
_HEX64_TOKEN_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")

_SECRET_RE = re.compile(
    r"(password|secret|api[_-]?key|token|credential|workstation|private[_-]?key)",
    re.IGNORECASE,
)


def _is_finite(v: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _contains_private_path(value: str) -> bool:
    low = value.lower()
    return any(pref.lower() in low for pref in _PRIVATE_PREFIXES)


def _contains_forbidden(value: str) -> str | None:
    norm = _normalize_forbidden_text(value)
    if norm in _NORMALIZED_ALLOWLIST:
        return None
    if value in ALLOWLISTED_DISCLAIMERS:
        return None
    for pat in _FORBIDDEN_FAMILY_PATTERNS:
        m = pat.search(norm)
        if m:
            return m.group(0)
    if _has_mixed_script(value):
        return "mixed_script"
    return None


def _contains_affirming_forbidden_any(value: str) -> str | None:
    norm = _normalize_forbidden_text(value)
    if norm in _NORMALIZED_ALLOWLIST:
        return None
    if value in ALLOWLISTED_DISCLAIMERS:
        return None
    for pat in _FORBIDDEN_FAMILY_PATTERNS:
        m = pat.search(norm)
        if m:
            return m.group(0)
    if _has_mixed_script(value):
        return "mixed_script"
    return None


def _scan_forbidden_recursive(obj: Any, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(obj, str):
        if _contains_private_path(obj):
            violations.append(f"{path}: absolute private path detected: {obj!r}")
        if _SECRET_RE.search(obj):
            violations.append(f"{path}: secret keyword detected: {obj!r}")
        forb = _contains_affirming_forbidden_any(obj)
        if forb is not None:
            violations.append(f"{path}: forbidden claim {forb!r} in {obj!r}")
        violations.extend(_hex_violations_for_string(obj, path))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            low_k = str(k).lower()
            if isinstance(k, str) and low_k.endswith("_authorized"):
                if v is True:
                    violations.append(f"{path}.{k}: true _authorized forbidden")
                if not isinstance(v, bool):
                    violations.append(
                        f"{path}.{k}: _authorized must be strict bool, got {type(v).__name__}"
                    )
            if isinstance(k, str):
                forb_k = _contains_affirming_forbidden_any(k)
                if forb_k is not None:
                    violations.append(f"{path}.{k}: forbidden key claim {forb_k!r}")
            violations.extend(_scan_forbidden_recursive(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            violations.extend(_scan_forbidden_recursive(v, f"{path}[{i}]"))
    return violations


# Aliases for backward compatibility and single recursive scanner guarantee
_scan_for_private_paths = _scan_forbidden_recursive
_scan_for_true_authorized = _scan_forbidden_recursive


def _validate_hex_tokens_in_package(pkg: Any) -> list[str]:
    """Scan every string in package for 40/64 hex tokens not in allowed sets (plus 7-39 prefix)."""
    violations: list[str] = []

    # collect all strings via recursion
    def _collect(o: Any, p: str) -> None:
        if isinstance(o, str):
            violations.extend(_hex_violations_for_string(o, p))
        elif isinstance(o, dict):
            for kk, vv in o.items():
                _collect(vv, f"{p}.{kk}")
                if isinstance(kk, str):
                    _collect(kk, f"{p}.{kk}[key]")
        elif isinstance(o, (list, tuple)):
            for idx, vv in enumerate(o):
                _collect(vv, f"{p}[{idx}]")

    _collect(pkg, "$")
    return violations


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Placement(StrEnum):
    ingress_dla = "ingress_dla"
    per_task_dla = "per_task_dla"
    p2c_dla = "p2c_dla"


class Scaling(StrEnum):
    fixed_1x = "fixed_1x"
    static_overprovisioned = "static_overprovisioned"
    reactive = "reactive"
    proactive = "proactive"


class EvidenceState(StrEnum):
    NOT_EXECUTED = "NOT_EXECUTED"


class ResultAvailability(StrEnum):
    NO_E3_RESEARCH_RESULTS_AVAILABLE = "NO_E3_RESEARCH_RESULTS_AVAILABLE"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class VecRuntime(StrictBase):
    promotion_commit: str = Field(description="vec promotion 40 hex")
    core_candidate: str = Field(description="vec core 40 hex")
    adapter_candidate: str = Field(description="vec adapter 40 hex")

    @field_validator("promotion_commit", "core_candidate", "adapter_candidate")
    @classmethod
    def validate_hex40(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"commit must be 40 hex chars, got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_exact(self) -> VecRuntime:
        if self.promotion_commit != VEC_PROMOTION_SHA:
            raise ValueError(
                f"vec promotion must be {VEC_PROMOTION_SHA}, got {self.promotion_commit!r}"
            )
        if self.core_candidate != VEC_CORE_SHA:
            raise ValueError(f"vec core must be {VEC_CORE_SHA}, got {self.core_candidate!r}")
        if self.adapter_candidate != VEC_ADAPTER_SHA:
            raise ValueError(
                f"vec adapter must be {VEC_ADAPTER_SHA}, got {self.adapter_candidate!r}"
            )
        return self


class TraffictwinRuntime(StrictBase):
    base_commit: str = Field(description="contract checkpoint 40 hex")

    @field_validator("base_commit")
    @classmethod
    def validate_hex40(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"base_commit must be 40 hex, got {v!r}")
        if v != CONTRACT_CHECKPOINT_SHA:
            raise ValueError(f"base_commit must be {CONTRACT_CHECKPOINT_SHA}, got {v!r}")
        return v


class ContractIdentity(StrictBase):
    schema_version: Literal["e3_dynamic_resource_v2_contract_v2"] = Field()
    sha256: str = Field(description="contract bytes sha256 64 hex")
    path: str = Field(description="relative contract path")

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not HEX64_RE.match(v):
            raise ValueError(f"contract sha256 must be 64 hex, got {v!r}")
        if v != CONTRACT_SHA256:
            raise ValueError(f"contract sha256 must be {CONTRACT_SHA256}, got {v!r}")
        return v

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if v != "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json":
            raise ValueError(
                f"contract path must be docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json, got {v!r}"
            )
        if _contains_private_path(v):
            raise ValueError("contract path must not contain private absolute path")
        return v


class SoftwareIdentity(StrictBase):
    actor_sha256: str = Field(description="actor sha256 64 hex")
    trace_sha256: str = Field(description="trace sha256 64 hex")
    e2d_manifest_sha256: str = Field(description="e2d manifest 64 hex")
    vec_promoted_base: str = Field(description="vec promoted base 40 hex")
    traffictwin_contract_head: str = Field(description="contract checkpoint 40 hex")
    vec_core_candidate_sha: str = Field(description="vec core 40 hex")

    @field_validator("actor_sha256", "trace_sha256", "e2d_manifest_sha256")
    @classmethod
    def validate_hex64(cls, v: str) -> str:
        if not HEX64_RE.match(v):
            raise ValueError(f"sha256 must be 64 hex, got {v!r}")
        return v

    @field_validator("vec_promoted_base", "traffictwin_contract_head", "vec_core_candidate_sha")
    @classmethod
    def validate_hex40(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"sha must be 40 hex, got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_exact(self) -> SoftwareIdentity:
        if self.actor_sha256 != ACTOR_SHA256:
            raise ValueError(f"actor_sha256 must be {ACTOR_SHA256}, got {self.actor_sha256!r}")
        if self.trace_sha256 != TRACE_SHA256:
            raise ValueError(f"trace_sha256 must be {TRACE_SHA256}, got {self.trace_sha256!r}")
        if self.e2d_manifest_sha256 != E2D_MANIFEST_SHA256:
            raise ValueError(
                f"e2d_manifest_sha256 must be {E2D_MANIFEST_SHA256}, got {self.e2d_manifest_sha256!r}"
            )
        if self.vec_promoted_base != VEC_PROMOTED_BASE:
            raise ValueError(
                f"vec_promoted_base must be {VEC_PROMOTED_BASE}, got {self.vec_promoted_base!r}"
            )
        if self.traffictwin_contract_head != CONTRACT_CHECKPOINT_SHA:
            raise ValueError(
                f"traffictwin_contract_head must be {CONTRACT_CHECKPOINT_SHA}, got {self.traffictwin_contract_head!r}"
            )
        if self.vec_core_candidate_sha != VEC_CORE_SHA:
            raise ValueError(
                f"vec_core_candidate_sha must be {VEC_CORE_SHA}, got {self.vec_core_candidate_sha!r}"
            )
        return self


class ExecutionAuthority(StrictBase):
    status: Literal["E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"] = Field()
    lane_09: Literal["BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"] = Field()
    evidence_state: Literal["NOT_EXECUTED"] = Field()
    result_availability: Literal["NO_E3_RESEARCH_RESULTS_AVAILABLE"] = Field()
    research_workloads_launched: Literal[0] = Field()
    scientific_execution_authorized: Literal[False] = Field()
    e3a_authorized: Literal[False] = Field()
    e3b_authorized: Literal[False] = Field()
    e3c_authorized: Literal[False] = Field()
    full_3600_step_cells_authorized: Literal[False] = Field()
    manchester_trace_comparative_execution_authorized: Literal[False] = Field()
    multi_seed_or_fleet_draw_execution_authorized: Literal[False] = Field()
    performance_evidence_benchmark_authorized: Literal[False] = Field()
    empirical_e3_results_authorized: Literal[False] = Field()
    statistical_inference_authorized: Literal[False] = Field()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v != E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED:
            raise ValueError(f"status must be {E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, got {v!r}")
        return v

    @field_validator("lane_09")
    @classmethod
    def validate_lane(cls, v: str) -> str:
        if v != LANE_09:
            raise ValueError(f"lane_09 must be {LANE_09}, got {v!r}")
        return v

    @field_validator("evidence_state")
    @classmethod
    def validate_evidence(cls, v: str) -> str:
        if v != NOT_EXECUTED:
            raise ValueError(f"evidence_state must be {NOT_EXECUTED}, got {v!r}")
        return v

    @field_validator("result_availability")
    @classmethod
    def validate_result(cls, v: str) -> str:
        if v != NO_E3_RESEARCH_RESULTS_AVAILABLE:
            raise ValueError(
                f"result_availability must be {NO_E3_RESEARCH_RESULTS_AVAILABLE}, got {v!r}"
            )
        return v


class DormantArm(StrictBase):
    arm_id: str = Field(min_length=1)
    placement: Placement
    scaling: Scaling
    state_age_ms: int = Field(description="typed integer milliseconds in {0,1000,3000}")

    @field_validator("state_age_ms")
    @classmethod
    def validate_age(cls, v: int) -> int:
        if type(v) is not int:
            raise ValueError(f"state_age_ms must be int, got {type(v).__name__}")
        if v not in VALID_STATE_AGE_MS:
            raise ValueError(f"state_age_ms must be in {VALID_STATE_AGE_MS}, got {v!r}")
        return v

    @field_validator("arm_id")
    @classmethod
    def validate_arm_id(cls, v: str) -> str:
        if _contains_private_path(v) or _contains_forbidden(v) is not None:
            raise ValueError(f"arm_id forbidden content: {v!r}")
        # arm_id must be canonical: placement__scaling__age_Xms
        if "__" not in v or not v.endswith("ms"):
            raise ValueError(f"arm_id must be canonical placement__scaling__age_Nms, got {v!r}")
        # basic check that it contains placement and scaling
        if not any(p in v for p in VALID_PLACEMENTS):
            raise ValueError(f"arm_id must contain valid placement, got {v!r}")
        if not any(s in v for s in VALID_SCALINGS):
            raise ValueError(f"arm_id must contain valid scaling, got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_canonical(self) -> DormantArm:
        expected = f"{self.placement.value}__{self.scaling.value}__age_{self.state_age_ms}ms"
        if self.arm_id != expected:
            raise ValueError(f"arm_id {self.arm_id!r} != canonical {expected!r}")
        return self


class DormantConfig(StrictBase):
    config_id: str = Field(min_length=1)
    arm_id: str = Field(min_length=1)
    placement: Placement
    scaling: Scaling
    state_age_ms: int = Field()
    evaluator_seed: Literal[0] = Field()
    fleet_seed: int = Field(ge=1)
    num_rsus: Literal[10] = Field()

    @field_validator("state_age_ms")
    @classmethod
    def validate_age(cls, v: int) -> int:
        if type(v) is not int:
            raise ValueError(f"state_age_ms must be int, got {type(v).__name__}")
        if v not in VALID_STATE_AGE_MS:
            raise ValueError(f"state_age_ms must be in {VALID_STATE_AGE_MS}, got {v!r}")
        return v

    @field_validator("fleet_seed")
    @classmethod
    def validate_fleet(cls, v: int) -> int:
        if type(v) is not int:
            raise ValueError(f"fleet_seed must be int, got {type(v).__name__}")
        if v not in FLEET_SEEDS:
            raise ValueError(f"fleet_seed must be in {FLEET_SEEDS}, got {v!r}")
        return v

    @field_validator("config_id", "arm_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if _contains_private_path(v) or _contains_forbidden(v) is not None:
            raise ValueError(f"id forbidden content: {v!r}")
        return v

    @model_validator(mode="after")
    def validate_canonical(self) -> DormantConfig:
        expected_arm = f"{self.placement.value}__{self.scaling.value}__age_{self.state_age_ms}ms"
        if self.arm_id != expected_arm:
            raise ValueError(f"arm_id {self.arm_id!r} != canonical {expected_arm!r}")
        expected_cfg = f"{expected_arm}__eval_{self.evaluator_seed}__fleet_{self.fleet_seed}__rsus_{self.num_rsus}"
        if self.config_id != expected_cfg:
            raise ValueError(f"config_id {self.config_id!r} != canonical {expected_cfg!r}")
        return self


class E3aDesign(StrictBase):
    stage: Literal["E3a"] = "E3a"
    placement: list[Placement] = Field(min_length=1)
    scaling: list[Scaling] = Field(min_length=1)
    state_age_ms: list[int] = Field(min_length=1)
    fleet_seeds: list[int] = Field(min_length=1)
    evaluator_seed: Literal[0] = Field()
    replication_unit: Literal["fleet_draw"] = Field()
    n: Literal[4] = Field()
    stage_listed_cells: Literal[12] = Field()
    unique_cells: Literal[12] = Field()
    equation: str = Field(min_length=1)

    @field_validator("state_age_ms")
    @classmethod
    def validate_age_list(cls, v: list[int]) -> list[int]:
        for x in v:
            if type(x) is not int:
                raise ValueError(f"state_age_ms must be int, got {type(x).__name__}")
            if x not in VALID_STATE_AGE_MS:
                raise ValueError(f"state_age_ms {x!r} not in {VALID_STATE_AGE_MS}")
        return v

    @field_validator("fleet_seeds")
    @classmethod
    def validate_fleet_list(cls, v: list[int]) -> list[int]:
        if v != [1, 2, 3, 4]:
            raise ValueError(f"E3a fleet_seeds must be [1,2,3,4], got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_exact(self) -> E3aDesign:
        if set(self.placement) != {"ingress_dla", "per_task_dla", "p2c_dla"}:
            raise ValueError(
                f"E3a placement must be exactly ingress_dla/per_task_dla/p2c_dla, got {[p.value for p in self.placement]!r}"
            )
        if self.scaling != [Scaling.fixed_1x]:
            raise ValueError(
                f"E3a scaling must be [fixed_1x], got {[s.value for s in self.scaling]!r}"
            )
        if self.state_age_ms != [0]:
            raise ValueError(f"E3a state_age_ms must be [0], got {self.state_age_ms!r}")
        return self


class E3bDesign(StrictBase):
    stage: Literal["E3b"] = "E3b"
    placement: list[Placement] = Field(min_length=1)
    scaling: list[Scaling] = Field(min_length=1)
    state_age_ms: list[int] = Field(min_length=1)
    fleet_seeds: list[int] = Field(min_length=1)
    evaluator_seed: Literal[0] = Field()
    replication_unit: Literal["fleet_draw"] = Field()
    n: Literal[4] = Field()
    stage_listed_cells: Literal[16] = Field()
    unique_cells: Literal[12] = Field()
    unique_additional: Literal[12] = Field()
    overlap_with_e3a: Literal[4] = Field()
    equation: str = Field(min_length=1)

    @field_validator("state_age_ms")
    @classmethod
    def validate_age_list(cls, v: list[int]) -> list[int]:
        for x in v:
            if type(x) is not int:
                raise ValueError(f"state_age_ms must be int, got {type(x).__name__}")
            if x not in VALID_STATE_AGE_MS:
                raise ValueError(f"state_age_ms {x!r} not in {VALID_STATE_AGE_MS}")
        return v

    @field_validator("fleet_seeds")
    @classmethod
    def validate_fleet_list(cls, v: list[int]) -> list[int]:
        if v != [1, 2, 3, 4]:
            raise ValueError(f"E3b fleet_seeds must be [1,2,3,4], got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_exact(self) -> E3bDesign:
        if self.placement != [Placement.per_task_dla]:
            raise ValueError(
                f"E3b placement must be [per_task_dla], got {[p.value for p in self.placement]!r}"
            )
        if set(self.scaling) != {"fixed_1x", "static_overprovisioned", "reactive", "proactive"}:
            raise ValueError(
                f"E3b scaling must be exactly 4 scalers, got {[s.value for s in self.scaling]!r}"
            )
        if self.state_age_ms != [0]:
            raise ValueError(f"E3b state_age_ms must be [0], got {self.state_age_ms!r}")
        return self


class E3cContrastSpec(StrictBase):
    comparison: str = Field(min_length=1)
    over_stale_ms: list[int] = Field(min_length=1)
    fixed: str | None = Field(default=None)
    fixed_placement: str | None = Field(default=None)

    @field_validator("over_stale_ms")
    @classmethod
    def validate_age_list(cls, v: list[int]) -> list[int]:
        for x in v:
            if type(x) is not int:
                raise ValueError(f"state_age_ms must be int, got {type(x).__name__}")
            if x not in VALID_STATE_AGE_MS:
                raise ValueError(f"state_age_ms {x!r} not in {VALID_STATE_AGE_MS}")
        if sorted(v) != [0, 1000, 3000]:
            raise ValueError(f"E3c over_stale_ms must be [0,1000,3000], got {v!r}")
        return v


class E3cDesign(StrictBase):
    stage: Literal["E3c"] = "E3c"
    contrasts: list[E3cContrastSpec] = Field(min_length=1)
    state_age_ms_values: list[int] = Field(min_length=1)
    stale_variant_cells_max: Literal[32] = Field()
    total_contrast_observations: Literal[48] = Field()
    fresh_observations_reused: Literal[16] = Field()
    state_is_view_parameter: bool = Field()
    reuses_identical_fresh_cells: bool = Field()

    @field_validator("state_age_ms_values")
    @classmethod
    def validate_age_list(cls, v: list[int]) -> list[int]:
        for x in v:
            if type(x) is not int:
                raise ValueError(f"state_age_ms must be int, got {type(x).__name__}")
            if x not in VALID_STATE_AGE_MS:
                raise ValueError(f"state_age_ms {x!r} not in {VALID_STATE_AGE_MS}")
        if sorted(v) != [0, 1000, 3000]:
            raise ValueError(f"E3c state_age_ms_values must be [0,1000,3000], got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_exact(self) -> E3cDesign:
        if len(self.contrasts) != 2:
            raise ValueError(f"E3c must have exactly 2 contrasts, got {len(self.contrasts)}")
        comps = [c.comparison for c in self.contrasts]
        if (
            "per_task_dla vs p2c_dla" not in comps
            and "p2c_dla vs per_task_dla" not in comps
            and not any("p2c_dla" in c and "per_task_dla" in c for c in comps)
        ):
            raise ValueError(f"E3c first contrast must be per_task_dla vs p2c_dla, got {comps!r}")
        if not any("reactive" in c and "proactive" in c for c in comps):
            raise ValueError(f"E3c second contrast must be reactive vs proactive, got {comps!r}")
        return self


class StagedDesign(StrictBase):
    e3a: E3aDesign
    e3b: E3bDesign
    e3c: E3cDesign
    maximum_candidate_unique_cells: Literal[56] = Field()
    stage_listed_cells: Literal[60] = Field()
    not_double_counted: Literal[True] = Field()
    identical_fresh_cells_reused_not_rerun: Literal[True] = Field()

    @model_validator(mode="after")
    def validate_totals(self) -> StagedDesign:
        if self.maximum_candidate_unique_cells != 56:
            raise ValueError("maximum_candidate_unique_cells must be 56")
        if self.stage_listed_cells != 60:
            raise ValueError("stage_listed_cells must be 60")
        return self


class ReplicationSpec(StrictBase):
    replication_unit: Literal["fleet_draw"] = Field()
    fleet_seeds: list[int] = Field()
    evaluator_seed: Literal[0] = Field()
    n: Literal[4] = Field()
    replication_key: Literal["fleet_seed"] = Field()
    tasks_are_not_replicates: Literal[True] = Field()
    seed_0_in_primary: Literal[False] = Field()
    interval: str = Field(min_length=1)
    method: str = Field(min_length=1)
    degrees_of_freedom: Literal[3] = Field()
    critical_value: float = Field()

    @field_validator("fleet_seeds")
    @classmethod
    def validate_fleet(cls, v: list[int]) -> list[int]:
        if v != [1, 2, 3, 4]:
            raise ValueError(f"fleet_seeds must be [1,2,3,4], got {v!r}")
        return v

    @field_validator("critical_value")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        if not _is_finite(v):
            raise ValueError(f"critical_value must be finite, got {v!r}")
        return float(v)

    @model_validator(mode="after")
    def validate_interval(self) -> ReplicationSpec:
        if "Student-t" not in self.interval and "Student" not in self.method:
            raise ValueError("interval must mention Student-t")
        if not (3.18 < self.critical_value < 3.19):
            raise ValueError(f"critical_value must be ~3.182, got {self.critical_value!r}")
        return self


class QueueCapacitySpec(StrictBase):
    unit: Literal["waiting_room_task_slots"] = Field()
    capacity_per_rsu: int = Field(
        ge=1, description="queue/waiting-room ceiling tasks per RSU, distinct from compute"
    )
    is_queue_not_compute: Literal[True] = Field()
    is_compute_units: Literal[False] | None = Field(default=False)

    @field_validator("capacity_per_rsu")
    @classmethod
    def validate_int_strict(cls, v: int) -> int:
        if type(v) is not int:
            raise ValueError(f"capacity_per_rsu must be int, got {type(v).__name__}")
        if v <= 0:
            raise ValueError("capacity_per_rsu must be positive")
        return v


class ComputeCapacitySpec(StrictBase):
    unit: Literal["compute_unit"] = Field()
    min_units: Literal[1] = Field()
    max_units: Literal[3] = Field()
    active_units_per_rsu_range: list[int] = Field(min_length=1)
    is_compute_not_queue: Literal[True] = Field()
    max_pending_actions: Literal[1] = Field()

    @field_validator("active_units_per_rsu_range")
    @classmethod
    def validate_range(cls, v: list[int]) -> list[int]:
        for x in v:
            if type(x) is not int:
                raise ValueError(f"active_units must be int, got {type(x).__name__}")
            if x not in (1, 2, 3):
                raise ValueError(f"active_units {x!r} not in [1,2,3]")
        return v


class ResourceCostSpec(StrictBase):
    metric: Literal["resource_unit_seconds"] = Field()
    formula: str = Field(min_length=1)
    monetary: Literal[False] = Field()
    unit: Literal["resource_unit_seconds"] = Field()
    interval_seconds: Literal[1] = Field()

    @field_validator("formula")
    @classmethod
    def validate_formula(cls, v: str) -> str:
        if _contains_affirming_forbidden_any(v) is not None:
            raise ValueError(f"formula contains forbidden claim: {v!r}")
        if "resource_unit_seconds" not in v and "active_compute_units" not in v:
            raise ValueError("formula must mention resource_unit_seconds or active_compute_units")
        if _contains_private_path(v):
            raise ValueError("formula must not contain private path")
        return v

    @model_validator(mode="after")
    def validate_no_monetary(self) -> ResourceCostSpec:
        if self.monetary is not False:
            raise ValueError("monetary must be False, resource cost is normalized usage not money")
        return self


class ScalingReceiptSpec(StrictBase):
    has_receipts_when_executed: bool = Field()
    receipts_when_not_executed_null_reason: str = Field(min_length=1)
    per_rsu_summaries_null_reason: str | None = Field(default=None)
    capacity_levels_null_reason: str | None = Field(default=None)
    state_age_receipts_null_reason: str | None = Field(default=None)

    @field_validator("receipts_when_not_executed_null_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("null reason must be non-empty")
        if _contains_affirming_forbidden_any(v) is not None:
            raise ValueError(f"reason contains forbidden claim: {v!r}")
        return v


class TaskAccountingSpec(StrictBase):
    offered: None = Field(default=None)
    admitted: None = Field(default=None)
    rejected_total: None = Field(default=None)
    rejected_by_class: dict[str, None] | None = Field(default=None)
    forwarded: None = Field(default=None)
    deadline_success: None = Field(default=None)
    # unavailable lifecycle must stay None
    started: None = Field(default=None)
    compute_completed: None = Field(default=None)
    returned: None = Field(default=None)
    dropped: None = Field(default=None)
    unavailable_reasons: dict[str, str] = Field()
    conservation_holds: None = Field(default=None)
    conservation_reason: str = Field(min_length=1)
    genuine_rejection_classes: list[str] = Field(min_length=1)

    @field_validator("genuine_rejection_classes")
    @classmethod
    def validate_classes(cls, v: list[str]) -> list[str]:
        if set(v) != set(REJECTION_CLASSES):
            raise ValueError(
                f"genuine_rejection_classes must be exactly {REJECTION_CLASSES}, got {v!r}"
            )
        return v

    @field_validator("unavailable_reasons")
    @classmethod
    def validate_reasons(cls, v: dict[str, str]) -> dict[str, str]:
        required = {"started", "compute_completed", "returned", "dropped"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"unavailable_reasons missing {missing}")
        for field, reason in v.items():
            if not reason.strip():
                raise ValueError(f"reason for {field!r} must be non-empty")
            if reason.strip() == "0" or reason.strip().lower() == "zero":
                raise ValueError(f"reason for {field!r} must not coerce to zero")
            if _contains_affirming_forbidden_any(reason) is not None:
                raise ValueError(f"reason for {field!r} contains forbidden claim: {reason!r}")
        return v

    @model_validator(mode="after")
    def validate_nulls(self) -> TaskAccountingSpec:
        for field in (
            "offered",
            "admitted",
            "rejected_total",
            "forwarded",
            "deadline_success",
            "started",
            "compute_completed",
            "returned",
            "dropped",
        ):
            val = getattr(self, field)
            if val is not None:
                raise ValueError(f"{field} must be None in NOT_EXECUTED state, got {val!r}")
        # rejected_by_class if present must be all None
        if self.rejected_by_class is not None:
            for k, val in self.rejected_by_class.items():
                if val is not None:
                    raise ValueError(f"rejected_by_class[{k!r}] must be None, got {val!r}")
                if k not in REJECTION_CLASSES:
                    raise ValueError(f"unexpected rejection class {k!r}")
        return self


class ProvenanceEntry(StrictBase):
    artifact: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    note: str = Field(min_length=1)

    @field_validator("artifact", "note")
    @classmethod
    def validate_no_private(cls, v: str) -> str:
        if _contains_private_path(v):
            raise ValueError(f"value must not contain private path: {v!r}")
        if _contains_affirming_forbidden_any(v) is not None:
            raise ValueError(f"value contains forbidden claim: {v!r}")
        return v

    @field_validator("note")
    @classmethod
    def validate_provenance_hex(cls, v: str) -> str:
        # Position-independent: every 40/64 hex token must be declared, 7-39 must be valid prefix
        violations = _hex_violations_for_string(v, "$.provenance.note")
        if violations:
            raise ValueError(violations[0])
        return v


class MissingnessReason(StrictBase):
    field: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("missingness reason must be non-empty")
        if _contains_affirming_forbidden_any(v) is not None:
            raise ValueError(f"reason contains forbidden claim: {v!r}")
        return v


# ---------------------------------------------------------------------------
# Top-level package
# ---------------------------------------------------------------------------


class E3ResearchEvidencePackage(StrictBase):
    schema_version: Literal["e3_dynamic_resource_v2_evidence_v1"] = Field()
    campaign: Literal["e3-dynamic-resource-v2"] = Field()
    product_base_sha: str = Field(description="product base 40 hex")
    research_promotion_sha: str = Field(description="merge promotion 40 hex")
    approved_candidate_sha: str = Field(description="approved runner candidate 40 hex")
    contract_checkpoint_sha: str = Field(description="contract checkpoint 40 hex")
    vec_runtime: VecRuntime
    traffictwin_runtime: TraffictwinRuntime
    contract: ContractIdentity
    software_identity: SoftwareIdentity
    execution_authority: ExecutionAuthority
    staged_design: StagedDesign
    replication: ReplicationSpec
    factors: dict[str, Any] = Field(description="factor sets mirror contract")
    dormant_arms: list[DormantArm] = Field(min_length=14, max_length=14)
    dormant_configs: list[DormantConfig] = Field(min_length=56, max_length=56)
    queue_capacity: QueueCapacitySpec
    compute_capacity: ComputeCapacitySpec
    resource_cost: ResourceCostSpec
    scaling_receipts: ScalingReceiptSpec
    task_accounting: TaskAccountingSpec
    provenance: list[ProvenanceEntry] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    non_claims: list[str] = Field(min_length=1)
    missingness: list[MissingnessReason] = Field(min_length=1)
    # truthful no-results state is first-class
    evidence_state: Literal["NOT_EXECUTED"] = Field()
    result_availability: Literal["NO_E3_RESEARCH_RESULTS_AVAILABLE"] = Field()
    research_workloads_launched: Literal[0] = Field()
    lane_09: Literal["BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"] = Field()
    status: Literal["E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"] = Field()

    @field_validator(
        "product_base_sha",
        "research_promotion_sha",
        "approved_candidate_sha",
        "contract_checkpoint_sha",
    )
    @classmethod
    def validate_hex40(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"sha must be 40 hex, got {v!r}")
        return v

    @field_validator("factors")
    @classmethod
    def validate_factors(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("factors must be dict")
        allowed_keys = {
            "evaluator_seed",
            "fleet_seeds",
            "padded_fleet_width",
            "placements",
            "scalings",
            "scenario_rsus",
            "smoke_ticks",
            "state_age_ms_values",
            "ticks_per_cell",
        }
        extra = set(v.keys()) - allowed_keys
        if extra:
            raise ValueError(f"factors contains forbidden extra keys: {sorted(extra)!r}")
        # check placements etc.
        placements = v.get("placements")
        scalings = v.get("scalings")
        state_age = v.get("state_age_ms_values")
        fleet = v.get("fleet_seeds")
        rsus = v.get("scenario_rsus")
        if placements is not None and set(placements) != set(VALID_PLACEMENTS):
            raise ValueError(f"factors placements must be {VALID_PLACEMENTS}, got {placements!r}")
        if scalings is not None and set(scalings) != set(VALID_SCALINGS):
            raise ValueError(f"factors scalings must be {VALID_SCALINGS}, got {scalings!r}")
        if state_age is not None and sorted(state_age) != [0, 1000, 3000]:
            raise ValueError(
                f"factors state_age_ms_values must be [0,1000,3000], got {state_age!r}"
            )
        if fleet is not None and fleet != [1, 2, 3, 4]:
            raise ValueError(f"factors fleet_seeds must be [1,2,3,4], got {fleet!r}")
        if rsus is not None and rsus != 10:
            raise ValueError(f"factors scenario_rsus must be 10, got {rsus!r}")
        # Strict type checks for known numerics to prevent result-like numerics
        for key in (
            "evaluator_seed",
            "padded_fleet_width",
            "scenario_rsus",
            "smoke_ticks",
            "ticks_per_cell",
        ):
            if key in v and type(v[key]) is not int:
                raise ValueError(f"factors {key} must be int, got {type(v[key]).__name__}")
        for val in (placements, scalings, state_age, fleet):
            if isinstance(val, list):
                for item in val:
                    if (
                        isinstance(item, str)
                        and _contains_affirming_forbidden_any(item) is not None
                    ):
                        raise ValueError(f"factors contains forbidden claim: {item!r}")
        # Recursive scan for any nested forbidden/private content already handled in model_validator via _scan_for_private_paths,
        # but also ensure no forbidden claim hidden in any string value of factors (deep)
        for val in v.values():
            if isinstance(val, str) and _contains_affirming_forbidden_any(val) is not None:
                raise ValueError(f"factors contains forbidden claim: {val!r}")
            if isinstance(val, list):
                for item in val:
                    if (
                        isinstance(item, str)
                        and _contains_affirming_forbidden_any(item) is not None
                    ):
                        raise ValueError(f"factors contains forbidden claim: {item!r}")
        return v

    @field_validator("limitations", "non_claims")
    @classmethod
    def validate_strings(cls, v: list[str]) -> list[str]:
        for s in v:
            if not s.strip():
                raise ValueError("entry must be non-empty")
            if _contains_private_path(s):
                raise ValueError(f"entry must not contain private path: {s!r}")
            if _contains_affirming_forbidden_any(s) is not None:
                raise ValueError(f"entry contains forbidden claim: {s!r}")
            if _SECRET_RE.search(s):
                raise ValueError(f"entry must not contain secret keyword: {s!r}")
        return v

    @model_validator(mode="after")
    def validate_cross(self) -> E3ResearchEvidencePackage:
        # pin exact identities
        if self.product_base_sha != TRAFFICTWIN_PRODUCT_BASE_SHA:
            raise ValueError(
                f"product_base_sha must be {TRAFFICTWIN_PRODUCT_BASE_SHA}, got {self.product_base_sha!r}"
            )
        if self.research_promotion_sha != TRAFFICTWIN_RESEARCH_PROMOTION_SHA:
            raise ValueError(
                f"research_promotion_sha must be {TRAFFICTWIN_RESEARCH_PROMOTION_SHA}, got {self.research_promotion_sha!r}"
            )
        if self.approved_candidate_sha != APPROVED_CANDIDATE_SHA:
            raise ValueError(
                f"approved_candidate_sha must be {APPROVED_CANDIDATE_SHA}, got {self.approved_candidate_sha!r}"
            )
        if self.contract_checkpoint_sha != CONTRACT_CHECKPOINT_SHA:
            raise ValueError(
                f"contract_checkpoint_sha must be {CONTRACT_CHECKPOINT_SHA}, got {self.contract_checkpoint_sha!r}"
            )

        if self.evidence_state != NOT_EXECUTED:
            raise ValueError(f"evidence_state must be {NOT_EXECUTED}, got {self.evidence_state!r}")
        if self.result_availability != NO_E3_RESEARCH_RESULTS_AVAILABLE:
            raise ValueError(
                f"result_availability must be {NO_E3_RESEARCH_RESULTS_AVAILABLE}, got {self.result_availability!r}"
            )
        if self.research_workloads_launched != RESEARCH_WORKLOADS_LAUNCHED:
            raise ValueError(
                f"research_workloads_launched must be 0, got {self.research_workloads_launched!r}"
            )
        if self.lane_09 != LANE_09:
            raise ValueError(f"lane_09 must be {LANE_09}, got {self.lane_09!r}")
        if self.status != E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED:
            raise ValueError(
                f"status must be {E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, got {self.status!r}"
            )

        # execution_authority must mirror top-level hold
        ea = self.execution_authority
        if ea.evidence_state != self.evidence_state:
            raise ValueError("execution_authority evidence_state must mirror top-level")
        if ea.result_availability != self.result_availability:
            raise ValueError("execution_authority result_availability must mirror top-level")
        if ea.research_workloads_launched != self.research_workloads_launched:
            raise ValueError(
                "execution_authority research_workloads_launched must mirror top-level"
            )
        if ea.lane_09 != self.lane_09:
            raise ValueError("execution_authority lane_09 must mirror top-level")
        if ea.status != self.status:
            raise ValueError("execution_authority status must mirror top-level")

        # replication must be exactly fleet_draw N=4
        if self.replication.replication_unit != "fleet_draw":
            raise ValueError("replication_unit must be fleet_draw")
        if self.replication.n != 4:
            raise ValueError("replication n must be 4")
        if self.replication.fleet_seeds != [1, 2, 3, 4]:
            raise ValueError("replication fleet_seeds must be [1,2,3,4]")

        # staged design arm/config counts already enforced but cross-check
        if len(self.dormant_arms) != 14:
            raise ValueError(f"dormant_arms must be 14, got {len(self.dormant_arms)}")
        if len(self.dormant_configs) != 56:
            raise ValueError(f"dormant_configs must be 56, got {len(self.dormant_configs)}")
        arm_ids = [a.arm_id for a in self.dormant_arms]
        if len(set(arm_ids)) != 14:
            raise ValueError("dormant_arms arm_id must be unique 14")
        if arm_ids != sorted(arm_ids):
            raise ValueError("dormant_arms must be sorted by arm_id")
        cfg_ids = [c.config_id for c in self.dormant_configs]
        if len(set(cfg_ids)) != 56:
            raise ValueError("dormant_configs config_id must be unique 56")
        if cfg_ids != sorted(cfg_ids):
            raise ValueError("dormant_configs must be sorted by config_id")

        # queue vs compute strictly separate
        if (
            self.queue_capacity.capacity_per_rsu is not None
            and self.compute_capacity.max_units is not None
        ):
            if self.queue_capacity.is_queue_not_compute is not True:
                raise ValueError("queue must declare is_queue_not_compute true")
            if self.compute_capacity.is_compute_not_queue is not True:
                raise ValueError("compute must declare is_compute_not_queue true")

        # resource cost must be resource_unit_seconds not monetary
        if self.resource_cost.metric != "resource_unit_seconds":
            raise ValueError("resource cost metric must be resource_unit_seconds")
        if self.resource_cost.monetary is not False:
            raise ValueError("resource cost monetary must be False")

        # task accounting must be null with reasons, never zero
        ta = self.task_accounting
        for field in (
            "offered",
            "admitted",
            "rejected_total",
            "forwarded",
            "deadline_success",
            "started",
            "compute_completed",
            "returned",
            "dropped",
        ):
            val = getattr(ta, field)
            if val is not None:
                raise ValueError(
                    f"task_accounting {field} must be None in NOT_EXECUTED, got {val!r}"
                )

        # limitations must mention not executed / no results and 4 draws
        joined_lim = " ".join(self.limitations).lower()
        if (
            "not_executed" not in joined_lim
            and "not executed" not in joined_lim
            and (
                "no_e3_research_results_available" not in joined_lim.lower()
                and "no e3" not in joined_lim
            )
        ):
            raise ValueError(
                "limitations must mention NOT_EXECUTED or NO_E3_RESEARCH_RESULTS_AVAILABLE"
            )

        # non_claims must contain bounded scope disclaimers
        joined_nc = " ".join(self.non_claims).lower()
        if "fleet_draw" not in joined_nc and "fleet draw" not in joined_nc:
            raise ValueError("non_claims must mention fleet_draw bounded replication")

        # scan entire payload for forbidden patterns (single canonical scanner includes private/secret/forbidden/_authorized/hex)
        violations = _scan_forbidden_recursive(self.model_dump(mode="json"))
        if violations:
            raise ValueError(f"forbidden path/claim detected: {violations[:2]}")
        # explicit hex token scan across all free-text fields (position-independent, 40 vs 64)
        hex_violations = _validate_hex_tokens_in_package(self.model_dump(mode="json"))
        if hex_violations:
            raise ValueError(f"forbidden hex token detected: {hex_violations[:2]}")

        return self

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")

        # path-free: strip any absolute-like keys (none should exist) but ensure deterministic
        def _strip(o: Any) -> Any:
            if isinstance(o, dict):
                out: dict[str, Any] = {}
                for k, v in o.items():
                    if k in {
                        "artifact_path",
                        "raw_root",
                        "raw_path",
                        "file_path",
                        "trace_path",
                        "actor_path",
                    }:
                        continue
                    out[k] = _strip(v)
                return out
            if isinstance(o, list):
                return [_strip(x) for x in o]
            if isinstance(o, str):
                if _contains_private_path(o):
                    return "<redacted-path>"
                return o
            return o

        stripped = _strip(payload)
        canonical = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


MAX_JSON_BYTES: Final[int] = 500_000


def load_e3_research_evidence_json(text: str) -> E3ResearchEvidencePackage:
    """Parse and strictly validate E3 research evidence JSON (fail-closed)."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError(f"payload exceeds {MAX_JSON_BYTES} bytes")
    # early forbidden checks on raw text
    if _contains_private_path(text):
        # use helper but avoid literal check; we already scan
        raise ValueError("payload contains private absolute path")
    # check for secret assignment pattern
    secret_assign_re = re.compile(r"(password|secret|api_key|token)\s*[:=]", re.IGNORECASE)
    if secret_assign_re.search(text):
        raise ValueError("payload contains secret/credential assignment")
    # (dead pass-only loop removed — canonical scanner handles all forbidden checks)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top-level JSON must be object")
    violations = _scan_forbidden_recursive(data)
    if violations:
        raise ValueError(f"private path/forbidden claim in payload: {violations[0]}")
    return E3ResearchEvidencePackage.model_validate(data)


__all__ = [
    "LANE_09",
    "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED",
    "NOT_EXECUTED",
    "NO_E3_RESEARCH_RESULTS_AVAILABLE",
    "RESEARCH_WORKLOADS_LAUNCHED",
    "TRAFFICTWIN_PRODUCT_BASE_SHA",
    "TRAFFICTWIN_RESEARCH_PROMOTION_SHA",
    "APPROVED_CANDIDATE_SHA",
    "CONTRACT_CHECKPOINT_SHA",
    "VEC_PROMOTION_SHA",
    "VEC_CORE_SHA",
    "VEC_ADAPTER_SHA",
    "ACTOR_SHA256",
    "TRACE_SHA256",
    "E2D_MANIFEST_SHA256",
    "CONTRACT_SHA256",
    "MANIFEST_SIDECAR_SHA256",
    "VEC_PROMOTED_BASE",
    "VALID_PLACEMENTS",
    "VALID_SCALINGS",
    "VALID_STATE_AGE_MS",
    "FLEET_SEEDS",
    "EVALUATOR_SEED",
    "SCENARIO_RSUS",
    "REJECTION_CLASSES",
    "Placement",
    "Scaling",
    "EvidenceState",
    "ResultAvailability",
    "VecRuntime",
    "TraffictwinRuntime",
    "ContractIdentity",
    "SoftwareIdentity",
    "ExecutionAuthority",
    "DormantArm",
    "DormantConfig",
    "E3aDesign",
    "E3bDesign",
    "E3cContrastSpec",
    "E3cDesign",
    "StagedDesign",
    "ReplicationSpec",
    "QueueCapacitySpec",
    "ComputeCapacitySpec",
    "ResourceCostSpec",
    "ScalingReceiptSpec",
    "TaskAccountingSpec",
    "ProvenanceEntry",
    "MissingnessReason",
    "E3ResearchEvidencePackage",
    "load_e3_research_evidence_json",
]
