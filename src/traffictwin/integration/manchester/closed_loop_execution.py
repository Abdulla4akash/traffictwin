"""Manchester closed-loop SAFE LOCAL SUMO execution contract.

Composes and strengthens :mod:`traffictwin.integration.sumo_execution` and
:mod:`traffictwin.integration.manchester.sumo_run` without creating a general
process runner.

Safety properties (strengthened composition):

* configured/pinned SUMO detection — an explicit executable path is validated;
  PATH is never searched at execution time;
* exact version capture — ``sumo --version`` is probed with ``shell=False``
  and the reported version must start with ``1.27.``; probe output is bounded
  in memory/disk via a pipe-draining capped collector;
* allowlisted executable identity only — base name must be exactly ``sumo``;
* fixed validated argv generated solely by code — no caller-supplied flags;
* explicit package root and configuration — relative, safe, non-symlink names
  inside the package root;
* bounded hardened XML preflight with defusedxml — rejects DTD/entities,
  malformed/oversized configs, absolute/traversing/URI refs, refs not in
  exact declared inventory, output/log/state/remote/TraCI/command-like options,
  and any unreviewed element capable of reading/writing outside staged isolation;
  ``additional-files`` is explicitly unsupported in this narrow V1 runner and
  is rejected (see limitations);
* declared input content fingerprints verified immediately before launch, with
  per-input and aggregate size bounds enforced before hashing/copying and via
  streaming copy/hash;
* isolated explicit output directory — must not exist, must not overlap the
  package root, parent must already exist;
* isolated private staging directory under the new run output — verified
  declared regular non-symlink inputs are streamed there with bounded hashing,
  staged hashes verified, execution cwd is the staging directory, source package
  remains unchanged;
* reject input drift both immediately before staging and after the run;
* timeout, exit code, bounded stdout/stderr receipts with process-group kill
  and pipe-draining bounded collectors that continue draining/discarding beyond
  the receipt cap so the child cannot deadlock or exhaust disk;
* deterministic run identity — SHA-256 over canonical request fingerprint +
  exact tool digest/version + fixed portable argv + operator authorisation,
  distinct from wall-clock receipt fingerprint; the request-level
  ``deterministic_run_identity`` binds only request fields, while the
  execution/package ``deterministic_run_identity`` is the canonical run
  identity that binds tool and argv;
* sanitized minimal environment — ``PATH`` limited to the executable parent
  plus ``/usr/bin:/bin``, plus ``LANG``/``LC_ALL``/``HOME`` only; no
  SUMO_HOME, no secret/private literals passed to child, never inherit hidden
  variables;
* output size checked BEFORE hashing, per-file and aggregate bounds, reject
  symlinks/extra/missing/duplicate/drift;
* engineering/software vs scientific standing correctly separated;
* portable receipt integrity bundling request/tool/preflight/argv/times/state/
  outputs/limitations with fingerprint, aware-UTC time ordering, and
  deterministic tolerance for measured duration;
* ``shell=False``; no command strings, uploaded scripts, automatic download,
  PATH guessing, arbitrary executable/argv, or network.

Fail-closed typed ``blocked`` standing when SUMO or provider-required inputs
are absent. Portable receipts use only relative names/identities and never
expose machine-private absolute paths, environment values, or secrets.

Engineering ``SOFTWARE_VALID`` is never upgraded to
``SCIENTIFICALLY_ACCEPTED_BASELINE``; the latter requires an explicit,
attributable, timestamped decision outside this contract and is structurally
refused here.

This module does not parse vehicle outputs into VEC tasks, does not launch
research workloads, and does not touch Dynamic Resource/E3 artifacts.

Post-construction ``model_copy`` cannot be globally prevented by a frozen
model alone; this module guarantees canonical revalidation at every public
preflight/run boundary before any file read, staging, or subprocess launch,
and receipt/preflight validation ensures blocked/refusal semantics for forged
requests without launching.

"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLOSED_LOOP_SCHEMA_VERSION: Literal["1.0"] = "1.0"
CLOSED_LOOP_METHOD_VERSION: Literal["manchester-closed-loop-1.0"] = "manchester-closed-loop-1.0"
CLOSED_LOOP_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

SUPPORTED_SUMO_VERSION_PREFIX: Literal["1.27."] = "1.27."
ALLOWED_EXECUTABLE_NAME: Literal["sumo"] = "sumo"

# Fixed argv shape — placeholders are substituted at run time and never
# appear in the portable receipt. No caller may add, remove, or reorder
# any element.
CLOSED_LOOP_FIXED_ARGV: tuple[str, ...] = (
    "-c",
    "<config>",
    "--seed",
    "<seed>",
    "--tripinfo-output",
    "<tripinfo>",
    "--summary-output",
    "<summary>",
    "--no-step-log",
    "true",
)

# Bounded receipt text — prevents a warning storm filling memory/disk.
MAX_LOG_BYTES = 32_000
MAX_LOG_LINES = 200
MAX_LOG_LINE_BYTES = 400
# Cap for version probe capture (stdout+stderr bounded)
MAX_VERSION_CAPTURE_BYTES = 16_000

# Execution bounds
DEFAULT_TIMEOUT_S = 120
MAX_TIMEOUT_S = 600
MIN_TIMEOUT_S = 1

# Config/output bounds
MAX_CONFIG_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 50_000_000
MAX_AGGREGATE_OUTPUT_BYTES = 100_000_000

# Input package bounds — per-input and aggregate, checked before hashing/copying
# where possible and enforced via streaming copy. Compatible with a substantial
# Manchester network/demand package (multi-MB nets/routes) but finite.
MAX_INPUT_BYTES = 20_000_000
MAX_AGGREGATE_INPUT_BYTES = 80_000_000

# Scientific vs engineering standing
ENGINEERING_SOFTWARE_VALID: Literal["SOFTWARE_VALID"] = "SOFTWARE_VALID"
ENGINEERING_NOT_VALID: Literal["ENGINEERING_NOT_VALID"] = "ENGINEERING_NOT_VALID"
SCIENTIFICALLY_NOT_ACCEPTED: Literal["SCIENTIFICALLY_NOT_ACCEPTED"] = "SCIENTIFICALLY_NOT_ACCEPTED"
SCIENTIFIC_ACCEPTED_BASELINE: Literal["SCIENTIFICALLY_ACCEPTED_BASELINE"] = (
    "SCIENTIFICALLY_ACCEPTED_BASELINE"
)

# Synthetic-only limitations — always present, never scientific acceptance.
CLOSED_LOOP_LIMITATIONS: tuple[str, ...] = (
    "Controlled local SUMO execution only: output is simulated demand, not "
    "observed traffic, not calibration, and not comparison.",
    "Engineering SOFTWARE_VALID does not imply SCIENTIFICALLY_ACCEPTED_BASELINE; "
    "scientific baseline acceptance requires an explicit attributable decision "
    "outside this execution contract.",
    "Vehicle outputs are never inferred into VEC tasks; no Dynamic Resource/E3 "
    "semantics are created.",
    "Limited V1 runner scope: additional-files XML is not supported; only "
    "explicit net-file/route-files references admitted, and the runner refuses "
    "any additional-files element.",
)

# Secret / private-path refusal (mirrors Manchester snapshot models)
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_TOKEN_RE = re.compile(
    r"(apikey|api_key|secret|password|passwd|token|bearer|credential)",
    re.IGNORECASE,
)
_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# Narrow allowlist suitable for the test package — additional-files excluded
_ALLOWED_CONFIG_TAGS: set[str] = {
    "configuration",
    "sumoConfiguration",
    "input",
    "net-file",
    "route-files",
    "time",
    "begin",
    "end",
}
# Tags that represent file references whose values must be in declared inventory
_FILE_REFERENCE_TAGS: set[str] = {"net-file", "route-files"}
_FORBIDDEN_TAG_SUBSTRINGS: tuple[str, ...] = (
    "output",
    "log",
    "state",
    "remote",
    "traci",
    "gui",
    "dump",
    "fcd",
    "vehroute",
    "emission",
    "battery",
    "charging",
    "ssm",
    "collision",
    "overhead",
    "edgeData",
    "laneData",
    "queue",
    "amitran",
    "full",
)


def _sanitize_xml_name(name: str) -> str:
    """Stable safe label for untrusted XML tag/attribute names."""
    if not name:
        return "REDACTED_EMPTY"
    if _SECRET_TOKEN_RE.search(name) or _PRIVATE_PATH_RE.search(name):
        h = _sha256_hex(name.encode("utf-8"))[:8]
        return f"REDACTED_NAME_{h}"
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if len(sanitized) > 64:
        sanitized = sanitized[:64]
    if not sanitized or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", sanitized):
        sanitized = f"TAG_{_sha256_hex(name.encode('utf-8'))[:8]}"
    # Final check: if still contains secret (e.g., sanitized still has token substring due to _ handling), fallback  # noqa: E501
    if _SECRET_TOKEN_RE.search(sanitized):
        sanitized = f"REDACTED_NAME_{_sha256_hex(name.encode('utf-8'))[:8]}"
    return sanitized


def _sanitize_finding_text(raw: str) -> str:
    """Per-error sanitization: redact secrets/private paths without erasing the reason."""
    if not raw or not raw.strip():
        return "BLOCKED: unspecified"
    # Redact secrets and private paths per error, preserving a non-empty blocker
    safe = _SECRET_TOKEN_RE.sub("REDACTED", raw)
    safe = _PRIVATE_PATH_RE.sub("{REDACTED}", safe)
    # Remove control characters
    safe = "".join(c if ord(c) >= 32 or c in "\n\t" else "_" for c in safe)
    safe = safe.strip()
    if len(safe) > 1000:
        safe = safe[:1000]
    if not safe:
        return "BLOCKED: redacted"
    # If still contains forbidden, fallback to generic
    if _SECRET_TOKEN_RE.search(safe) or _PRIVATE_PATH_RE.search(safe):
        return "CONFIG_SANITIZED_REJECTED: redacted"
    return safe


def _finalize_findings(findings: list[str]) -> list[str]:
    """Sanitize each finding and deterministically cap to contract bound (32) without holding unbounded strings."""  # noqa: E501
    sanitized: list[str] = []
    suppressed = 0
    for f in findings:
        # If already at cap, count suppressed without holding string
        if len(sanitized) >= 31:
            # Still sanitize to count but do not store; need to account for this finding as suppressed  # noqa: E501
            suppressed += 1
            continue
        s = _sanitize_finding_text(f)
        if not 1 <= len(s) <= 1000:
            s = s[:1000] if len(s) > 1000 else "BLOCKED: truncated"
        if _SECRET_TOKEN_RE.search(s) or _PRIVATE_PATH_RE.search(s):
            s = "CONFIG_SANITIZED_REJECTED: redacted"
        # Ensure sanitized never empty
        if not s.strip():
            s = "BLOCKED: sanitized"
        sanitized.append(s)
        # If we just filled to 31 and there are remaining raw findings, they will be counted as suppressed in next iterations  # noqa: E501
    if suppressed > 0 or len(sanitized) > 32:
        # This path also handles when caller passed >32 raw findings and we capped at 31
        total_raw = len(findings)
        if suppressed == 0 and total_raw > 32:
            suppressed = total_raw - 31
        # Ensure we have at most 31 before marker
        if len(sanitized) > 31:
            suppressed += len(sanitized) - 31
            sanitized = sanitized[:31]
        sanitized.append(f"FINDINGS_TRUNCATED: {suppressed} further findings suppressed")
        # Guarantee bounded
        if len(sanitized) > 32:
            sanitized = sanitized[:31] + [
                f"FINDINGS_TRUNCATED: {suppressed} further findings suppressed"
            ]
    # Final empty guard
    if not sanitized and findings:
        return ["BLOCKED: sanitized"]
    return sanitized


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class ManchesterClosedLoopModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, allow_inf_nan=False, revalidate_instances="never"
    )

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _sha256_hex(self.canonical_json().encode("utf-8"))


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class ManchesterClosedLoopError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Identities
# ---------------------------------------------------------------------------


class ClosedLoopToolIdentity(ManchesterClosedLoopModel):
    executable_name: Literal["sumo"] = ALLOWED_EXECUTABLE_NAME
    reported_version: str = Field(min_length=1, max_length=64)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    supported_version_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX

    @model_validator(mode="after")
    def _check_version(self) -> ClosedLoopToolIdentity:
        if not self.reported_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
            raise ValueError("sumo version must match the reviewed 1.27.x toolchain")
        return self


class ClosedLoopInputDeclaration(ManchesterClosedLoopModel):
    path: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=MAX_INPUT_BYTES)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        if "\x00" in v or any(ord(c) < 32 for c in v):
            raise ValueError("path must not contain control characters")
        pp = PurePosixPath(v)
        if pp.is_absolute() or any(part in {"", ".", ".."} for part in pp.parts):
            raise ValueError("input path must be safe relative")
        if ".." in v or v.startswith("/") or "\\" in v:
            raise ValueError("input path must not escape package root")
        if not _SAFE_NAME_RE.match(pp.name):
            for seg in pp.parts:
                if not _SAFE_NAME_RE.match(seg):
                    raise ValueError(f"unsafe path segment: {seg}")
        if _PRIVATE_PATH_RE.search(v):
            raise ValueError("input path must not contain private absolute path")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("input path must not contain secret token")
        return pp.as_posix()


class ClosedLoopFileEvidence(ManchesterClosedLoopModel):
    path: str = Field(min_length=1, max_length=300)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        pp = PurePosixPath(v)
        if pp.is_absolute() or any(part in {"", ".", ".."} for part in pp.parts):
            raise ValueError("evidence path must be safe relative")
        if _PRIVATE_PATH_RE.search(v):
            raise ValueError("evidence path must not contain private path")
        return pp.as_posix()


# ---------------------------------------------------------------------------
# Request / Preflight / Package / Receipt
# ---------------------------------------------------------------------------


class ClosedLoopExecutionRequest(ManchesterClosedLoopModel):
    schema_version: Literal["1.0"] = CLOSED_LOOP_SCHEMA_VERSION
    method_version: Literal["manchester-closed-loop-1.0"] = CLOSED_LOOP_METHOD_VERSION
    capability_id: Literal["MAN-09"] = CLOSED_LOOP_CAPABILITY_ID
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    package_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_file: str = Field(min_length=1, max_length=200)
    inputs: list[ClosedLoopInputDeclaration] = Field(min_length=1, max_length=32)
    seed: int = Field(ge=0, le=2_147_483_647)
    timeout_seconds: int = Field(ge=MIN_TIMEOUT_S, le=MAX_TIMEOUT_S)
    # Request-scoped deterministic identity (binds request fields only); the
    # canonical execution run identity additionally binds tool and argv and
    # is carried by package/receipt.
    deterministic_run_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_by_operator: Literal[True] = True

    @field_validator("config_file")
    @classmethod
    def _validate_config(cls, v: str) -> str:
        pp = PurePosixPath(v)
        if pp.is_absolute() or len(pp.parts) != 1 or v in {".", ".."}:
            raise ValueError("config_file must be a single safe file name")
        if not _SAFE_NAME_RE.match(v):
            raise ValueError("unsafe config file name")
        if _PRIVATE_PATH_RE.search(v):
            raise ValueError("config file must not contain private path")
        return v

    @model_validator(mode="after")
    def _validate_request(self) -> ClosedLoopExecutionRequest:
        names = [i.path for i in self.inputs]
        if len(set(names)) != len(names):
            raise ValueError("duplicate input paths")
        if self.config_file not in names:
            raise ValueError("config_file must be among declared inputs")
        # Aggregate bound for declared inputs
        total = sum(i.size_bytes for i in self.inputs)
        if total > MAX_AGGREGATE_INPUT_BYTES:
            raise ValueError("aggregate input size exceeds bound")
        for i in self.inputs:
            if i.size_bytes > MAX_INPUT_BYTES:
                raise ValueError("input size exceeds per-file bound")
        payload = {
            "package_fingerprint": self.package_fingerprint,
            "config_file": self.config_file,
            "inputs": sorted(
                [i.model_dump(mode="json") for i in self.inputs],
                key=lambda x: x["path"],
            ),
            "seed": self.seed,
            "timeout_seconds": self.timeout_seconds,
            "run_id": self.run_id,
            "confirmed_by_operator": self.confirmed_by_operator,
        }
        expected = _sha256_hex(_canonical_json(payload).encode("utf-8"))
        if self.deterministic_run_identity != expected:
            raise ValueError("deterministic_run_identity mismatch")
        return self


class ClosedLoopPreflightStatus(str):  # type alias helper, not enum to keep Literal
    pass


class ClosedLoopPreflightReport(ManchesterClosedLoopModel):
    schema_version: Literal["1.0"] = CLOSED_LOOP_SCHEMA_VERSION
    method_version: Literal["manchester-closed-loop-1.0"] = CLOSED_LOOP_METHOD_VERSION
    status: Literal["accepted", "blocked"]
    capability_id: Literal["MAN-09"] = CLOSED_LOOP_CAPABILITY_ID
    tool: ClosedLoopToolIdentity | None = None
    request: ClosedLoopExecutionRequest | None = None
    request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    findings: list[str] = Field(default_factory=list, max_length=32)
    read_only: Literal[True] = True
    mutations_performed: Literal[False] = False

    @field_validator("findings")
    @classmethod
    def _validate_findings(cls, v: list[str]) -> list[str]:
        for item in v:
            if not 1 <= len(item) <= 1000:
                raise ValueError("finding length out of bounds")
            if _PRIVATE_PATH_RE.search(item):
                raise ValueError("finding must not contain private path")
            if _SECRET_TOKEN_RE.search(item):
                raise ValueError("finding must not contain secret token")
        return v

    @model_validator(mode="after")
    def _validate_outcome(self) -> ClosedLoopPreflightReport:
        if self.status == "accepted":
            if self.tool is None or self.request is None or self.request_fingerprint is None:
                raise ValueError("accepted preflight requires tool, request, and fingerprint")
            if self.request_fingerprint != self.request.fingerprint():
                raise ValueError("request fingerprint mismatch")
        elif self.request_fingerprint is not None and self.request is not None:  # noqa: SIM102
            if self.request_fingerprint != self.request.fingerprint():
                raise ValueError("request fingerprint mismatch")
        return self


class ClosedLoopExecutionPackage(ManchesterClosedLoopModel):
    schema_version: Literal["1.0"] = CLOSED_LOOP_SCHEMA_VERSION
    method_version: Literal["manchester-closed-loop-1.0"] = CLOSED_LOOP_METHOD_VERSION
    capability_id: Literal["MAN-09"] = CLOSED_LOOP_CAPABILITY_ID
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    package_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool: ClosedLoopToolIdentity
    argv: list[str] = Field(min_length=2, max_length=32)
    working_directory: Literal["{PACKAGE_ROOT}"] = "{PACKAGE_ROOT}"
    output_directory: Literal["{OUTPUT_ROOT}"] = "{OUTPUT_ROOT}"
    timeout_seconds: int = Field(ge=MIN_TIMEOUT_S, le=MAX_TIMEOUT_S)
    # Canonical run identity binds request_fingerprint + tool digest/version + portable argv
    deterministic_run_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    environment_keys: list[str] = Field(min_length=1, max_length=16)
    shell_used: Literal[False] = False
    caller_supplied_arguments: Literal[False] = False

    @model_validator(mode="after")
    def _validate_package(self) -> ClosedLoopExecutionPackage:
        if len(self.argv) != len(CLOSED_LOOP_FIXED_ARGV) + 1:
            raise ValueError("argv length must match fixed shape plus executable")
        if self.argv[0] != ALLOWED_EXECUTABLE_NAME:
            raise ValueError("only allowlisted executable is permitted")
        if PurePosixPath(self.argv[0]).name != self.argv[0]:
            raise ValueError("argv executable must be base name only")
        for got, expected in zip(self.argv[1:], CLOSED_LOOP_FIXED_ARGV, strict=True):
            if expected.startswith("<") and expected.endswith(">"):
                if not got or _PRIVATE_PATH_RE.search(got):
                    raise ValueError("argv placeholder must not contain private path")
                if _SECRET_TOKEN_RE.search(got):
                    raise ValueError("argv placeholder must not contain secret")
                if any(c in got for c in [";", "&", "|", "`", "$", "\n"]):
                    raise ValueError("argv must not contain shell metacharacters")
            elif got != expected:
                raise ValueError(f"argv token mismatch: {got!r} != {expected!r}")
        # Canonical run identity must bind request, tool, argv
        expected_identity = _canonical_run_identity_from_parts(
            self.request_fingerprint, self.tool, self.argv
        )
        if self.deterministic_run_identity != expected_identity:
            raise ValueError("deterministic_run_identity must match canonical request+tool+argv")
        # Environment keys must be exactly the documented minimal set (order-insensitive)
        allowed = {"PATH", "HOME", "LANG", "LC_ALL"}
        if set(self.environment_keys) != allowed:
            if "SUMO_HOME" in self.environment_keys:
                raise ValueError("SUMO_HOME must not be in environment_keys")
            raise ValueError("environment_keys must be exactly PATH,HOME,LANG,LC_ALL")
        return self


class ClosedLoopExecutionReceipt(ManchesterClosedLoopModel):
    schema_version: Literal["1.0"] = CLOSED_LOOP_SCHEMA_VERSION
    method_version: Literal["manchester-closed-loop-1.0"] = CLOSED_LOOP_METHOD_VERSION
    capability_id: Literal["MAN-09"] = CLOSED_LOOP_CAPABILITY_ID
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    request: ClosedLoopExecutionRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool: ClosedLoopToolIdentity
    argv: list[str] = Field(min_length=2, max_length=32)
    working_directory: Literal["{PACKAGE_ROOT}"] = "{PACKAGE_ROOT}"
    output_directory: Literal["{OUTPUT_ROOT}"] = "{OUTPUT_ROOT}"
    started_at_utc: str = Field(min_length=1, max_length=64)
    completed_at_utc: str = Field(min_length=1, max_length=64)
    duration_s: float = Field(ge=0)
    exit_code: int | None = None
    timed_out: bool
    outcome: Literal["completed", "failed", "timed_out", "blocked"]
    stdout_excerpt: str = Field(max_length=MAX_LOG_BYTES)
    stderr_excerpt: str = Field(max_length=MAX_LOG_BYTES)
    outputs: list[ClosedLoopFileEvidence] = Field(default_factory=list)
    output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    inputs_verified: bool
    deterministic_run_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    engineering_standing: Literal["SOFTWARE_VALID", "ENGINEERING_NOT_VALID"] = Field(
        default="ENGINEERING_NOT_VALID"
    )
    scientific_standing: Literal["SCIENTIFICALLY_NOT_ACCEPTED"] = Field(
        default="SCIENTIFICALLY_NOT_ACCEPTED"
    )
    limitations: list[str] = Field(min_length=1, max_length=8)
    shell_used: Literal[False] = False
    caller_supplied_arguments: Literal[False] = False
    secrets_exposed: Literal[False] = False

    @field_validator("started_at_utc", "completed_at_utc")
    @classmethod
    def _validate_time(cls, v: str) -> str:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        off = dt.utcoffset()
        if off is None or off.total_seconds() != 0:
            raise ValueError("timestamp must be UTC")
        if _PRIVATE_PATH_RE.search(v):
            raise ValueError("timestamp must not contain private path")
        return v

    @field_validator("stdout_excerpt", "stderr_excerpt")
    @classmethod
    def _validate_log(cls, v: str) -> str:
        if _PRIVATE_PATH_RE.search(v):
            raise ValueError("log excerpt must not contain private path")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("log excerpt must not contain secret")
        return v

    @model_validator(mode="after")
    def _validate_receipt(self) -> ClosedLoopExecutionReceipt:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        # Bind preflight identity to exact request + tool
        expected_preflight = _preflight_fingerprint(self.request, self.tool)
        if self.preflight_fingerprint != expected_preflight:
            # Allow blocked preflight synthetic fingerprint only for blocked outcome?
            # For blocked, execution still uses real preflight binding? We allow only canonical.
            if self.outcome != "blocked":
                raise ValueError("preflight_fingerprint must match request+tool")
            # For blocked, also verify synthetic is not accepted as valid canonical
            # blocked receipts use blocked: prefix which is intentionally distinct; reject if
            # they claim canonical preflight while blocked
            # But we still require that any non-canonical blocked fingerprint is exactly
            # the synthetic blocked one derived from request
            synthetic = _sha256_hex(b"blocked:" + self.request.fingerprint().encode())
            if self.preflight_fingerprint not in {expected_preflight, synthetic}:
                raise ValueError("preflight_fingerprint mismatch for blocked")
            if self.preflight_fingerprint == expected_preflight and self.outcome == "blocked":
                # blocked with canonical preflight also allowed; synthetic used for blocked path
                pass  # noqa: S110
        # Canonical run identity must bind request_fingerprint + tool + argv
        expected_run = _canonical_run_identity(self.request, self.tool, self.argv)
        if self.deterministic_run_identity != expected_run:
            raise ValueError("deterministic_run_identity must match canonical request+tool+argv")
        if self.deterministic_run_identity == self.fingerprint():
            raise ValueError("deterministic identity must be distinct from receipt fingerprint")
        # aware UTC and ordering with duration tolerance
        try:
            start = datetime.fromisoformat(self.started_at_utc.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.completed_at_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid timestamp") from exc
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("timestamps must be aware")
        if end < start:
            raise ValueError("completed_at must not be before started_at")
        expected_duration = (end - start).total_seconds()
        # Allow deterministic tolerance for measured clocks (monotonic vs wall clock)
        if abs(self.duration_s - expected_duration) > 2.0 + 1e-6:
            raise ValueError("duration_s must match UTC start/end within tolerance")
        # argv must be fixed shape
        if len(self.argv) != len(CLOSED_LOOP_FIXED_ARGV) + 1:
            raise ValueError("receipt argv must match fixed shape plus executable")
        if self.argv[0] != ALLOWED_EXECUTABLE_NAME:
            raise ValueError("receipt executable must be allowlisted")
        if PurePosixPath(self.argv[0]).name != self.argv[0]:
            raise ValueError("receipt argv executable must be base name only")
        for got, expected in zip(self.argv[1:], CLOSED_LOOP_FIXED_ARGV, strict=True):
            if expected.startswith("<") and expected.endswith(">"):
                if not got:
                    raise ValueError("argv placeholder empty")
                if _PRIVATE_PATH_RE.search(got):
                    raise ValueError("argv must not contain private path")
            elif got != expected:
                raise ValueError("receipt argv token mismatch")
        # outcome / exit / timeout consistency and standing
        if self.outcome == "completed":
            if self.exit_code != 0:
                raise ValueError("completed requires exit 0")
            if self.timed_out:
                raise ValueError("completed cannot be timed out")
            if not self.inputs_verified:
                raise ValueError("completed requires verified inputs")
            required = {"tripinfo.xml", "summary.xml"}
            paths = [o.path for o in self.outputs]
            if len(paths) != len(set(paths)):
                raise ValueError("completed requires distinct required outputs (duplicate)")
            if set(paths) != required or len(self.outputs) != 2:
                raise ValueError("completed requires both tripinfo.xml and summary.xml")
            if self.output_fingerprint is None:
                raise ValueError("completed requires output fingerprint")
            if self.engineering_standing != "SOFTWARE_VALID":
                raise ValueError("completed requires engineering SOFTWARE_VALID")
            if self.scientific_standing != "SCIENTIFICALLY_NOT_ACCEPTED":
                raise ValueError("completed scientific must be SCIENTIFICALLY_NOT_ACCEPTED")
        else:
            # blocked/failed/timed_out must NOT claim SOFTWARE_VALID
            if self.engineering_standing == "SOFTWARE_VALID":
                raise ValueError("non-completed must not claim SOFTWARE_VALID")
            if self.scientific_standing != "SCIENTIFICALLY_NOT_ACCEPTED":
                raise ValueError("scientific must be SCIENTIFICALLY_NOT_ACCEPTED")
            if self.outcome == "blocked":
                if self.exit_code is not None:
                    raise ValueError("blocked must have null exit_code")
                if self.timed_out:
                    raise ValueError("blocked cannot be timed_out")
                if self.inputs_verified:
                    raise ValueError("blocked must have inputs_verified false")
                if self.outputs or self.output_fingerprint is not None:
                    raise ValueError("blocked must have no outputs")
            if self.outcome == "timed_out" and not self.timed_out:
                raise ValueError("timed_out outcome requires timed_out flag")
            if self.outcome == "failed" and self.timed_out:
                raise ValueError("failed cannot be timed_out")
        if (
            self.timed_out != (self.outcome == "timed_out")
            and self.outcome
            in {
                "completed",
                "failed",
                "blocked",
            }
            and self.timed_out
        ):
            raise ValueError("timed_out flag mismatch")
        # never upgrade scientific standing
        if self.scientific_standing != "SCIENTIFICALLY_NOT_ACCEPTED":
            raise ValueError("scientific standing must be SCIENTIFICALLY_NOT_ACCEPTED")
        # portable: no absolute paths, no secrets
        for ev in self.outputs:
            if _PRIVATE_PATH_RE.search(ev.path):
                raise ValueError("output path must be portable")
        if self.output_fingerprint is not None:
            expected = _output_fingerprint(self.outputs)
            if self.output_fingerprint != expected:
                raise ValueError("output fingerprint mismatch")
        if self.secrets_exposed is not False:
            raise ValueError("secrets_exposed must be false")
        if self.shell_used is not False or self.caller_supplied_arguments is not False:
            raise ValueError("shell and caller argument flags must be false")
        if list(self.limitations) != list(CLOSED_LOOP_LIMITATIONS):
            raise ValueError("limitations must match fixed set")
        if not _SHA256_RE.match(self.preflight_fingerprint):
            raise ValueError("preflight_fingerprint must be sha256")
        # Ensure request confirmed
        if self.request.confirmed_by_operator is not True:
            raise ValueError("request must be operator confirmed")
        return self


def _output_fingerprint(outputs: list[ClosedLoopFileEvidence]) -> str:
    payload = [o.model_dump(mode="json") for o in sorted(outputs, key=lambda x: x.path)]
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _preflight_fingerprint(
    request: ClosedLoopExecutionRequest, tool: ClosedLoopToolIdentity
) -> str:
    payload = {
        "request_fingerprint": request.fingerprint(),
        "tool_sha": tool.executable_sha256,
        "tool_version": tool.reported_version,
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _canonical_run_identity(
    request: ClosedLoopExecutionRequest, tool: ClosedLoopToolIdentity, argv: list[str]
) -> str:
    """Canonical execution run identity binding request + tool + argv."""
    payload = {
        "request_fingerprint": request.fingerprint(),
        "tool_sha": tool.executable_sha256,
        "tool_version": tool.reported_version,
        "argv": argv,
        "confirmed_by_operator": request.confirmed_by_operator,
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _canonical_run_identity_from_parts(
    request_fingerprint: str, tool: ClosedLoopToolIdentity, argv: list[str]
) -> str:
    payload = {
        "request_fingerprint": request_fingerprint,
        "tool_sha": tool.executable_sha256,
        "tool_version": tool.reported_version,
        "argv": argv,
        "confirmed_by_operator": True,
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_text(text: str) -> str:
    """Bound and scrub text for receipt portability; never returns empty when input non-empty."""
    if len(text) > MAX_LOG_BYTES:
        text = text[:MAX_LOG_BYTES]
    lines = text.splitlines()
    kept: list[str] = []
    for raw in lines[:MAX_LOG_LINES]:
        if len(raw) > MAX_LOG_LINE_BYTES:
            raw = raw[:MAX_LOG_LINE_BYTES]
        if _PRIVATE_PATH_RE.search(raw):
            continue
        if _SECRET_TOKEN_RE.search(raw):
            continue
        kept.append(raw)
    result = "\n".join(kept)
    if not result.strip() and text.strip():
        return "BLOCKED: sanitized"
    return result


def _controlled_environment(executable: Path, working_dir: Path) -> dict[str, str]:
    # Minimal explicit environment; never inherit hidden variables. No SUMO_HOME.
    # Values are explicit staging/tool-derived, kept out of portable receipt.
    return {
        "PATH": f"{executable.parent}:/usr/bin:/bin",
        "HOME": str(working_dir),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def _validate_package_root(package_root: Path) -> str | None:
    if package_root.is_symlink():
        return "package root must not be a symlink"
    if not package_root.is_dir():
        return "package root must be an existing directory"
    return None


def _validate_output_root(output_root: Path, package_root: Path) -> str | None:
    if output_root.exists():
        return "output directory must not already exist"
    if output_root.is_symlink():
        return "output directory path must not be a symlink"
    parent = output_root.parent
    if not parent.is_dir() or parent.is_symlink():
        return "output parent must be an existing non-symlink directory"
    try:
        pkg = package_root.resolve()
        out = output_root.resolve(strict=False)
        if out == pkg or pkg in out.parents or out in pkg.parents:
            return "output directory must not overlap package root"
    except OSError:
        return "output directory overlap check failed"
    return None


def _verify_declared_inputs(package_root: Path, request: ClosedLoopExecutionRequest) -> list[str]:
    errors: list[str] = []
    pkg_resolved = package_root.resolve()
    total_bytes = 0
    for decl in request.inputs:
        # Declared size bound check before filesystem access where possible
        if decl.size_bytes > MAX_INPUT_BYTES:
            errors.append(f"INPUT_OVERSIZE: {decl.path} {decl.size_bytes} > {MAX_INPUT_BYTES}")
            continue
        candidate = package_root / decl.path
        if candidate.is_symlink():
            errors.append(f"input must not be a symlink: {decl.path}")
            continue
        pp = PurePosixPath(decl.path)
        parent_symlink = False
        cur = package_root
        for part in pp.parts[:-1]:
            cur = cur / part
            if cur.is_symlink():
                errors.append(f"input must not be a symlink: {decl.path}")
                parent_symlink = True
                break
        if parent_symlink:
            continue
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            errors.append(f"input cannot be resolved: {decl.path}")
            continue
        if not candidate.is_file():
            errors.append(f"input missing or not a regular file: {decl.path}")
            continue
        try:
            resolved.relative_to(pkg_resolved)
        except ValueError:
            errors.append(f"input escapes package root: {decl.path}")
            continue
        try:
            actual_size = candidate.stat().st_size
        except OSError:
            errors.append(f"input cannot be read: {decl.path}")
            continue
        if actual_size > MAX_INPUT_BYTES:
            errors.append(f"INPUT_OVERSIZE: {decl.path} {actual_size} > {MAX_INPUT_BYTES}")
            continue
        total_bytes += actual_size
        if total_bytes > MAX_AGGREGATE_INPUT_BYTES:
            errors.append(f"INPUT_AGGREGATE_OVERSIZE: {total_bytes} > {MAX_AGGREGATE_INPUT_BYTES}")
            # continue to collect but avoid hashing huge aggregate
            continue
        if actual_size != decl.size_bytes:
            errors.append(f"input size mismatch: {decl.path}")
            continue
        # Hash only after size checks
        try:
            actual_sha = _sha256_file(candidate)
        except OSError:
            errors.append(f"input cannot be read: {decl.path}")
            continue
        if actual_sha != decl.sha256:
            errors.append(f"input fingerprint mismatch: {decl.path}")
    # Final aggregate check on declared sizes
    declared_total = sum(i.size_bytes for i in request.inputs)
    if declared_total > MAX_AGGREGATE_INPUT_BYTES:
        errors.append(
            f"INPUT_AGGREGATE_OVERSIZE: declared {declared_total} > {MAX_AGGREGATE_INPUT_BYTES}"
        )
    return errors


def _compute_package_fingerprint(
    package_root: Path, inputs: list[ClosedLoopInputDeclaration]
) -> str:
    payload = sorted([i.model_dump(mode="json") for i in inputs], key=lambda x: x["path"])
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _compute_deterministic_identity(
    package_fingerprint: str,
    config_file: str,
    inputs: list[ClosedLoopInputDeclaration],
    seed: int,
    timeout_seconds: int,
    run_id: str,
    confirmed_by_operator: Literal[True],
) -> str:
    payload = {
        "package_fingerprint": package_fingerprint,
        "config_file": config_file,
        "inputs": sorted([i.model_dump(mode="json") for i in inputs], key=lambda x: x["path"]),
        "seed": seed,
        "timeout_seconds": timeout_seconds,
        "run_id": run_id,
        "confirmed_by_operator": confirmed_by_operator,
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _preflight_config_xml(package_root: Path, request: ClosedLoopExecutionRequest) -> list[str]:
    """Hardened XML preflight for the .sumocfg as untrusted execution control."""
    errors: list[str] = []
    suppressed = 0

    def _emit(msg: str) -> None:
        nonlocal suppressed
        if len(errors) < 31:
            errors.append(msg)
        else:
            suppressed += 1

    config_path = package_root / request.config_file
    # Never resolve symlink before checking
    if config_path.is_symlink():
        _emit("CONFIG_SYMLINK_REJECTED: config must not be a symlink")
        return _finalize_preflight_errors(errors, suppressed)
    if not config_path.is_file():
        _emit("CONFIG_MISSING: config file is not a regular file")
        return _finalize_preflight_errors(errors, suppressed)
    try:
        size = config_path.stat().st_size
    except OSError:
        _emit("CONFIG_UNREADABLE: cannot stat config")
        return _finalize_preflight_errors(errors, suppressed)
    if size > MAX_CONFIG_BYTES:
        _emit(f"CONFIG_OVERSIZED: {size} exceeds {MAX_CONFIG_BYTES}")
        return _finalize_preflight_errors(errors, suppressed)
    try:
        data = config_path.read_bytes()
    except OSError:
        _emit("CONFIG_UNREADABLE: cannot read config")
        return _finalize_preflight_errors(errors, suppressed)
    if len(data) > MAX_CONFIG_BYTES:
        _emit("CONFIG_OVERSIZED: byte length exceeds bound")
        return _finalize_preflight_errors(errors, suppressed)
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        _emit("CONFIG_DTD_ENTITY_REJECTED: DTD/entities are forbidden")
        return _finalize_preflight_errors(errors, suppressed)
    # Use defusedxml for safe parsing
    try:
        import defusedxml.ElementTree as defusedxml_et  # noqa: N813 - defused alias

        root = defusedxml_et.fromstring(data)
    except Exception as exc:  # noqa: BLE001 - need to surface malformed
        _emit(f"CONFIG_MALFORMED: {exc}")
        return _finalize_preflight_errors(errors, suppressed)

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    def _safe_val(v: str) -> str:
        if _PRIVATE_PATH_RE.search(v) or _SECRET_TOKEN_RE.search(v):
            return "{REDACTED}"
        return v

    def _validate_file_reference_text(raw_val: str, safe_label: str) -> None:
        """Validate a file-reference string (comma-separated) fail-closed, bounded."""
        # Apply same checks as attribute value
        if _PRIVATE_PATH_RE.search(raw_val):
            _emit("CONFIG_PRIVATE_PATH_REJECTED: value contains private path")
        if _SECRET_TOKEN_RE.search(raw_val):
            _emit("CONFIG_SENSITIVE_REJECTED: value contains disallowed pattern")
        if "://" in raw_val:
            _emit(f"CONFIG_URI_REFERENCE_REJECTED: {_safe_val(raw_val)}")
        if raw_val.startswith("/") or raw_val.startswith("\\"):
            _emit(f"CONFIG_ABSOLUTE_REFERENCE_REJECTED: {_safe_val(raw_val)}")
        if "\\" in raw_val:
            _emit(f"CONFIG_BACKSLASH_REJECTED: {_safe_val(raw_val)}")
        if "\x00" in raw_val:
            _emit("CONFIG_NULL_BYTE_REJECTED: value contains null byte")
        try:
            pp = PurePosixPath(raw_val)
            if ".." in pp.parts:
                _emit(f"CONFIG_TRAVERSAL_REJECTED: {_safe_val(raw_val)}")
        except Exception:
            _emit(f"CONFIG_TRAVERSAL_REJECTED: {_safe_val(raw_val)}")
        if tag in _FILE_REFERENCE_TAGS:
            for ref in raw_val.split(","):
                ref = ref.strip()
                if not ref:
                    continue
                safe_ref = _safe_val(ref)
                if ref not in admitted:
                    _emit(f"CONFIG_REFERENCE_NOT_IN_INVENTORY: {safe_ref}")
                if ".." in PurePosixPath(ref).parts:
                    _emit(f"CONFIG_TRAVERSAL_REJECTED: {safe_ref}")
                if ref.startswith("/") or "\\" in ref:
                    _emit(f"CONFIG_ABSOLUTE_REFERENCE_REJECTED: {safe_ref}")
                if "://" in ref:
                    _emit(f"CONFIG_URI_REFERENCE_REJECTED: {safe_ref}")
                if _PRIVATE_PATH_RE.search(ref):
                    _emit("CONFIG_PRIVATE_PATH_REJECTED: value contains private path")
                if _SECRET_TOKEN_RE.search(ref):
                    _emit("CONFIG_SENSITIVE_REJECTED: value contains disallowed pattern")

    admitted = {i.path for i in request.inputs}
    for elem in root.iter():
        # Bounded early stop: still need to count tail/text errors but without unbounded storage;
        # _emit already bounds. We continue iterating but may stop producing detailed tail errors if suppressed huge.  # noqa: E501
        # To avoid unbounded iteration cost, we keep iterating but each iteration only does cheap checks.  # noqa: E501
        tag = _strip_ns(elem.tag)
        safe_tag = _sanitize_xml_name(tag)
        # Explicit refusal of additional-files in this narrow V1 runner
        if tag == "additional-files":
            _emit("CONFIG_ADDITIONAL_FILES_REJECTED: additional-files not supported in V1 runner")
            continue
        if tag not in _ALLOWED_CONFIG_TAGS:
            low = tag.lower()
            if any(k in low for k in _FORBIDDEN_TAG_SUBSTRINGS):
                _emit(f"CONFIG_FORBIDDEN_OPTION_REJECTED: {safe_tag} is not allowed")
            else:
                _emit(f"CONFIG_UNREVIEWED_ELEMENT_REJECTED: {safe_tag} is not allowlisted")
            # Even for unreviewed tags, still check text/tail channels fail-closed to prevent hidden file refs inside them  # noqa: E501
            # Check any non-whitespace text/tail inside unreviewed element as additional blocker (but already blocked)  # noqa: E501
            # We still scan text/tail to ensure no raw path leaks via earlier _safe_val, but element already blocked.  # noqa: E501
            # Fall through to text checks below to ensure redacted handling, but avoid double inventory checks.  # noqa: E501
        # Validate attributes
        for attr_name, attr_val in list(elem.attrib.items()):
            # Allow XML namespace declarations on root
            if tag in {"configuration", "sumoConfiguration"} and (
                attr_name.startswith("{") or attr_name.startswith("xmlns") or "xsi" in attr_name
            ):
                continue
            if attr_name != "value":
                safe_attr = _sanitize_xml_name(attr_name)
                _emit(
                    f"CONFIG_UNREVIEWED_ATTRIBUTE_REJECTED: {safe_tag} attribute {safe_attr} not allowed"  # noqa: E501
                )
                continue
            val: str = attr_val
            safe = _safe_val(val)
            if _PRIVATE_PATH_RE.search(val):
                _emit("CONFIG_PRIVATE_PATH_REJECTED: value contains private path")
            if _SECRET_TOKEN_RE.search(val):
                _emit("CONFIG_SENSITIVE_REJECTED: value contains disallowed pattern")
            if "://" in val:
                _emit(f"CONFIG_URI_REFERENCE_REJECTED: {safe}")
            if val.startswith("/") or val.startswith("\\"):
                _emit(f"CONFIG_ABSOLUTE_REFERENCE_REJECTED: {safe}")
            if "\\" in val:
                _emit(f"CONFIG_BACKSLASH_REJECTED: {safe}")
            if "\x00" in val:
                _emit("CONFIG_NULL_BYTE_REJECTED: value contains null byte")
            try:
                pp = PurePosixPath(val)
                if ".." in pp.parts:
                    _emit(f"CONFIG_TRAVERSAL_REJECTED: {safe}")
            except Exception:
                _emit(f"CONFIG_TRAVERSAL_REJECTED: {safe}")
            if tag in _FILE_REFERENCE_TAGS:
                for ref in val.split(","):
                    ref = ref.strip()
                    if not ref:
                        continue
                    safe_ref = _safe_val(ref)
                    if ref not in admitted:
                        _emit(f"CONFIG_REFERENCE_NOT_IN_INVENTORY: {safe_ref}")
                    if ".." in PurePosixPath(ref).parts:
                        _emit(f"CONFIG_TRAVERSAL_REJECTED: {safe_ref}")
                    if ref.startswith("/") or "\\" in ref:
                        _emit(f"CONFIG_ABSOLUTE_REFERENCE_REJECTED: {safe_ref}")
                    if "://" in ref:
                        _emit(f"CONFIG_URI_REFERENCE_REJECTED: {safe_ref}")
        # --- Text / tail / itertext channels fail-closed ---
        # For file-reference tags, any non-whitespace character data (including nested via itertext) is a file reference.  # noqa: E501
        if tag in _FILE_REFERENCE_TAGS:
            # Use itertext to capture nested/combined text (ElementTree exposes combined via itertext)  # noqa: E501
            try:
                combined = "".join(elem.itertext())
            except Exception:
                combined = elem.text or ""
            if combined is not None and combined.strip() != "":
                # Validate the combined non-whitespace text as file reference(s)
                stripped = combined.strip()
                # Split respect comma-separated inventory form; but combined may contain whitespace-only separators?  # noqa: E501
                # Validate each logical reference; we also validate whole stripped for absolute/traversal as above  # noqa: E501
                _validate_file_reference_text(stripped, safe_tag)
        else:
            # Non-file tags must not contain non-whitespace character data
            # Check direct .text
            if elem.text is not None and elem.text.strip() != "":
                _emit(f"CONFIG_TEXT_CONTENT_REJECTED: {safe_tag} must not contain character data")
            # Also check combined nested text that isn't inside a file-reference child?
            # For non-file tags, any descendant non-whitespace itertext that isn't inside a file tag child should be blocked.  # noqa: E501
            # Since file tags are children, their text is already validated above; but stray text directly under non-file tag between children is captured via tail checks below and via elem.text.  # noqa: E501
            # To cover nested text not directly in elem.text, we check if any descendant file-tag text would have been validated, otherwise treat as unexpected.  # noqa: E501
            # Simplified: if elem is not file tag and combined stripped is not empty and tag is not file tag, but combined includes file-tag children's text, we shouldn't double-reject.  # noqa: E501
            # So we only reject if the element has no file-tag descendant with text, or we check that no file-tag descendant exists.  # noqa: E501
            # For simplicity, we already handle file tag itertext above; for non-file tags we rely on per-element text/tail checks, not combined.  # noqa: E501
            pass
        # Tail channel — always fail-closed for any non-whitespace tail
        if elem.tail is not None and elem.tail.strip() != "":
            safe_tail = _safe_val(elem.tail.strip())
            # Tail is text after this element's closing tag, inside parent; any non-whitespace tail indicates undeclared character data  # noqa: E501
            _emit(f"CONFIG_TAIL_CONTENT_REJECTED: {safe_tail}")
    return _finalize_preflight_errors(errors, suppressed)


def _finalize_preflight_errors(errors: list[str], suppressed: int) -> list[str]:
    """Cap preflight errors without holding unbounded strings; produce deterministic truncation marker."""  # noqa: E501
    if suppressed > 0:
        # Ensure list capped at 31 before marker
        if len(errors) > 31:
            # Already bounded, but suppressed indicates overflow
            errors = errors[:31]
        elif len(errors) == 31:
            pass
        else:
            # errors <31 but suppressed>0 means we emitted via bounded path
            pass
        # Total further findings = suppressed (additional beyond 31) plus any overflow beyond 31 already counted?  # noqa: E501
        # errors length is at most 31, suppressed is count of dropped
        errors.append(f"FINDINGS_TRUNCATED: {suppressed} further findings suppressed")
        # Guarantee not empty and bounded
        if len(errors) > 32:
            errors = errors[:31] + [f"FINDINGS_TRUNCATED: {suppressed} further findings suppressed"]
        # Ensure non-empty after sanitizing truncation marker not needed; marker is safe
        return errors
    # No suppression, but still need to ensure bounded via normal finalize if caller passed many
    if len(errors) > 32:
        truncated_n = len(errors) - 31
        return errors[:31] + [f"FINDINGS_TRUNCATED: {truncated_n} further findings suppressed"]
    return errors


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
    except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired, OSError):
        pass
    with contextlib.suppress(OSError):
        process.wait(timeout=1)


# ---------------------------------------------------------------------------
# Bounded process helpers
# ---------------------------------------------------------------------------


def _bounded_drain(pipe: object, buf: bytearray, limit: int) -> None:
    """Drain pipe into buf up to limit, discarding beyond limit but continuing to drain."""
    stream = pipe
    try:
        while True:
            chunk = stream.read(8192)  # type: ignore[attr-defined]
            if not chunk:
                break
            if len(buf) < limit:
                needed = limit - len(buf)
                buf.extend(chunk[:needed])
            # discard remainder of chunk beyond limit, continue draining
    except Exception:  # noqa: S110
        pass


def _bounded_version_probe(executable: Path, timeout: int = 15) -> tuple[str, str]:
    """Run sumo --version with bounded capture and shell=False."""
    proc: subprocess.Popen[bytes] | None = None
    out_buf = bytearray()
    err_buf = bytearray()
    try:
        proc = subprocess.Popen(  # noqa: S603 - fixed allowlisted argv, shell=False
            [str(executable), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
        t_out = threading.Thread(
            target=_bounded_drain,
            args=(proc.stdout, out_buf, MAX_VERSION_CAPTURE_BYTES),
            daemon=True,
        )
        t_err = threading.Thread(
            target=_bounded_drain,
            args=(proc.stderr, err_buf, MAX_VERSION_CAPTURE_BYTES),
            daemon=True,
        )
        t_out.start()
        t_err.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_process_group(proc)
        t_out.join(timeout=2)
        t_err.join(timeout=2)
    except (OSError, subprocess.SubprocessError):
        if proc is not None:
            with contextlib.suppress(Exception):
                _terminate_process_group(proc)
        raise
    finally:
        if proc is not None:
            with contextlib.suppress(Exception):
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
    return out_buf.decode("utf-8", errors="replace"), err_buf.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Public API — configured detection, request creation, preflight, package, execution
# ---------------------------------------------------------------------------


def detect_configured_sumo(executable_path: Path) -> ClosedLoopToolIdentity:
    """Validate a configured/pinned SUMO executable and capture exact version.

    No PATH guessing: the caller supplies the exact filesystem path.
    Version probe is bounded in memory/disk via capped pipe draining.
    """
    if executable_path.is_symlink():
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_SYMLINK",
            "configured SUMO executable must not be a symlink",
        )
    if executable_path.name != ALLOWED_EXECUTABLE_NAME:
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_NOT_ALLOWLISTED",
            f"only '{ALLOWED_EXECUTABLE_NAME}' is allowlisted; got {executable_path.name!r}",
        )
    if not executable_path.is_file():
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_MISSING",
            "configured SUMO executable is not a regular file",
        )
    try:
        digest = _sha256_file(executable_path)
    except OSError as exc:
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_UNREADABLE", "SUMO executable could not be hashed"
        ) from exc

    try:
        out_text, err_text = _bounded_version_probe(executable_path)
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        raise ManchesterClosedLoopError(
            "SUMO_VERSION_UNREADABLE", "SUMO did not report a usable version"
        ) from exc

    combined = f"{out_text}\n{err_text}"
    m = _VERSION_RE.search(combined)
    if m is None:
        raise ManchesterClosedLoopError("SUMO_VERSION_UNREADABLE", "SUMO version was not parseable")
    version = m.group(1)
    if not version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
        raise ManchesterClosedLoopError(
            "SUMO_VERSION_DRIFT",
            f"SUMO {version} not in reviewed {SUPPORTED_SUMO_VERSION_PREFIX}x",
        )
    return ClosedLoopToolIdentity(
        reported_version=version,
        executable_sha256=digest,
        supported_version_prefix=SUPPORTED_SUMO_VERSION_PREFIX,
    )


def create_closed_loop_request(
    *,
    package_root: Path,
    config_file: str,
    seed: int = 42,
    timeout_seconds: int = DEFAULT_TIMEOUT_S,
    run_id: str = "run-01",
    confirmed_by_operator: Literal[True] = True,
) -> ClosedLoopExecutionRequest:
    """Build a frozen deterministic request from an explicit package root.

    The caller must explicitly pass ``confirmed_by_operator=True``; omission
    or any non-True value fails closed. The flag is bound into the
    deterministic identity and execution is never a render-side effect.
    """
    if confirmed_by_operator is not True:
        raise ManchesterClosedLoopError(
            "OPERATOR_AUTHORISATION_REQUIRED",
            "execution requires explicit operator authorisation (confirmed_by_operator=True)",
        )
    if not re.match(r"^[a-z0-9][a-z0-9_.-]{0,63}$", run_id):
        raise ManchesterClosedLoopError("INVALID_RUN_ID", "run_id does not match required pattern")

    pkg = Path(package_root)
    if _validate_package_root(pkg) is not None:
        raise ManchesterClosedLoopError("PACKAGE_ROOT_INVALID", _validate_package_root(pkg) or "")

    cfg = PurePosixPath(config_file).as_posix()
    if PurePosixPath(cfg).is_absolute() or len(PurePosixPath(cfg).parts) != 1:
        raise ManchesterClosedLoopError(
            "CONFIG_FILE_INVALID", "config_file must be a single safe file name"
        )

    inputs: list[ClosedLoopInputDeclaration] = []
    aggregate = 0
    for child in sorted(pkg.iterdir(), key=lambda p: p.name):
        if child.is_symlink():
            raise ManchesterClosedLoopError(
                "INPUT_SYMLINK",
                f"input must not be a symlink: {_sanitize_xml_name(child.name)}",
            )
        if child.is_dir():
            raise ManchesterClosedLoopError(
                "UNSUPPORTED_PACKAGE_ENTRY",
                f"unsupported package entry (subdirectory not allowed): {_sanitize_xml_name(child.name)}",  # noqa: E501
            )
        if not child.is_file():
            raise ManchesterClosedLoopError(
                "UNSUPPORTED_PACKAGE_ENTRY",
                f"unsupported package entry: {_sanitize_xml_name(child.name)}",
            )
        if not _SAFE_NAME_RE.match(child.name):
            raise ManchesterClosedLoopError(
                "UNSAFE_PACKAGE_ENTRY",
                f"unsafe package entry: {_sanitize_xml_name(child.name)}",
            )
        # Enforce per-file bound before hashing where possible
        try:
            size = child.stat().st_size
        except OSError as exc:
            raise ManchesterClosedLoopError(
                "INPUT_UNREADABLE", f"cannot stat {child.name}"
            ) from exc
        if size > MAX_INPUT_BYTES:
            raise ManchesterClosedLoopError(
                "INPUT_OVERSIZE", f"{child.name} {size} exceeds per-file bound {MAX_INPUT_BYTES}"
            )
        aggregate += size
        if aggregate > MAX_AGGREGATE_INPUT_BYTES:
            raise ManchesterClosedLoopError(
                "INPUT_AGGREGATE_OVERSIZE",
                f"aggregate {aggregate} exceeds {MAX_AGGREGATE_INPUT_BYTES}",
            )
        sha = _sha256_file(child)
        # Re-verify size after hash to catch race
        try:
            size2 = child.stat().st_size
        except OSError:
            size2 = size
        if size2 != size:
            raise ManchesterClosedLoopError(
                "INPUT_SIZE_CHANGED", f"size changed during hash: {child.name}"
            )
        inputs.append(ClosedLoopInputDeclaration(path=child.name, sha256=sha, size_bytes=size))

    if cfg not in {i.path for i in inputs}:
        raise ManchesterClosedLoopError(
            "CONFIG_FILE_MISSING",
            f"config file {_sanitize_xml_name(cfg)} not in declared package inputs",
        )

    package_fp = _compute_package_fingerprint(pkg, inputs)
    det_id = _compute_deterministic_identity(
        package_fp, cfg, inputs, seed, timeout_seconds, run_id, confirmed_by_operator
    )

    return ClosedLoopExecutionRequest(
        run_id=run_id,
        package_fingerprint=package_fp,
        config_file=cfg,
        inputs=inputs,
        seed=seed,
        timeout_seconds=timeout_seconds,
        deterministic_run_identity=det_id,
        confirmed_by_operator=confirmed_by_operator,
    )


def preflight_closed_loop_execution(
    *,
    package_root: Path,
    output_root: Path,
    request: ClosedLoopExecutionRequest,
    tool: ClosedLoopToolIdentity | None,
) -> ClosedLoopPreflightReport:
    """Read-only preflight; never mutates, never launches.

    Returns ``blocked`` when SUMO or any provider-required input is absent,
    ``accepted`` otherwise. ``blocked`` is a typed standing distinct from
    ``failed`` or ``accepted``.

    Canonical revalidation is performed at the boundary before any file
    access: a forged ``config_file``, inventory, timeout, or authorization
    via ``model_copy`` is treated as typed blocked without launching.
    """
    # Canonical revalidation before any file read / staging / subprocess
    try:
        canonical_request = ClosedLoopExecutionRequest.model_validate(
            request.model_dump(mode="json")
        )
    except Exception as exc:  # noqa: BLE001
        raw = []
        try:
            from pydantic import ValidationError as _VE  # noqa: N814

            if isinstance(exc, _VE):
                for err_detail in exc.errors():
                    loc = ".".join(str(p) for p in err_detail.get("loc", ()))
                    safe_loc = _sanitize_xml_name(loc) if loc else "request"
                    msg = err_detail.get("msg", "")
                    safe_msg = _SECRET_TOKEN_RE.sub("REDACTED", msg)
                    safe_msg = _PRIVATE_PATH_RE.sub("{REDACTED}", safe_msg)
                    safe_msg = safe_msg[:200]
                    raw.append(f"REQUEST_VALIDATION_FAILED: {safe_loc} {safe_msg}")
                if not raw:
                    raw.append("REQUEST_VALIDATION_FAILED: invalid request")
            else:
                raw.append(f"REQUEST_VALIDATION_FAILED: {_sanitize_xml_name(str(exc))[:200]}")
        except Exception:
            raw.append("REQUEST_VALIDATION_FAILED: invalid request")
        _forged_findings = _finalize_findings(raw)
        # Ensure non-empty safe blocker
        if not _forged_findings or not any(f.strip() for f in _forged_findings):
            _forged_findings = ["REQUEST_VALIDATION_FAILED: blocked"]
        # Use original request's fingerprint if possible, fallback to hash of raw
        try:
            fp = request.fingerprint()
        except Exception:
            fp = _sha256_hex(b"invalid:" + str(raw).encode())
        # Use model_construct to avoid re-validating the forged nested request (which is intentionally invalid)  # noqa: E501
        # This ensures a typed blocked artifact is returned without raising ValidationError,
        # while still preserving safe findings and fingerprint binding.
        return ClosedLoopPreflightReport.model_construct(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=fp,
            findings=_forged_findings,
            read_only=True,
            mutations_performed=False,
            schema_version=CLOSED_LOOP_SCHEMA_VERSION,
            method_version=CLOSED_LOOP_METHOD_VERSION,
            capability_id=CLOSED_LOOP_CAPABILITY_ID,
        )
    # Bind to canonical validated request thereafter
    request = canonical_request
    findings: list[str] = []

    if request.confirmed_by_operator is not True:
        findings.append("OPERATOR_AUTHORISATION_MISSING: confirmed_by_operator must be True")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    if tool is None:
        findings.append("SUMO_TOOLCHAIN_UNAVAILABLE: configured SUMO not supplied")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=None,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    _pkg_err = _validate_package_root(Path(package_root))
    if _pkg_err is not None:
        findings.append(f"PACKAGE_ROOT_INVALID: {_pkg_err}")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    _out_err = _validate_output_root(Path(output_root), Path(package_root))
    if _out_err is not None:
        findings.append(f"OUTPUT_ISOLATION_REFUSED: {_out_err}")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    input_errors = _verify_declared_inputs(Path(package_root), request)
    if input_errors:
        for e in input_errors:
            findings.append(f"INPUT_VERIFICATION_FAILED: {_sanitize_finding_text(e)}")
        findings = _finalize_findings(findings)
        if not findings:
            findings = ["INPUT_VERIFICATION_FAILED: blocked"]
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    # Hardened config preflight — handle bounded truncation marker without double counting
    cfg_errors = _preflight_config_xml(Path(package_root), request)
    if cfg_errors:
        # Separate truncation marker from real errors to avoid double capping
        truncated = None
        real_cfg = []
        for e in cfg_errors:
            if e.startswith("FINDINGS_TRUNCATED:"):
                truncated = e
            else:
                real_cfg.append(e)
        for e in real_cfg:
            findings.append(f"CONFIG_PREFLIGHT_FAILED: {_sanitize_finding_text(e)}")
        if truncated is not None:
            # Preserve the preflight's deterministic truncation count
            findings.append(truncated)
        else:
            findings = _finalize_findings(findings)
            # If finalize added a marker, keep it; otherwise no truncation
            # Ensure marker not double wrapped
        if not findings:
            findings = ["CONFIG_PREFLIGHT_FAILED: blocked"]
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    findings.append("PREFLIGHT_ACCEPTED: package, inputs, tool, and output isolation verified")
    findings = _finalize_findings(findings)

    return ClosedLoopPreflightReport(
        status="accepted",
        tool=tool,
        request=request,
        request_fingerprint=request.fingerprint(),
        findings=findings,
    )


def build_closed_loop_execution_package(
    *,
    package_root: Path,
    output_root: Path,
    request: ClosedLoopExecutionRequest,
    tool: ClosedLoopToolIdentity,
    executable_path: Path,
) -> ClosedLoopExecutionPackage:
    """Build the execution package with fixed validated argv."""
    if request.confirmed_by_operator is not True:
        raise ManchesterClosedLoopError(
            "OPERATOR_AUTHORISATION_REQUIRED", "request not operator-authorised"
        )
    if executable_path.name != ALLOWED_EXECUTABLE_NAME:
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_NOT_ALLOWLISTED", "only 'sumo' is allowlisted"
        )
    if executable_path.is_symlink() or not executable_path.is_file():
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_INVALID", "executable must be a regular non-symlink file"
        )
    actual_digest = _sha256_file(executable_path)
    if actual_digest != tool.executable_sha256:
        raise ManchesterClosedLoopError(
            "SUMO_IDENTITY_MISMATCH", "executable digest changed since detection"
        )

    base_tokens: list[str] = []
    for tok in CLOSED_LOOP_FIXED_ARGV:
        if tok == "<config>":
            base_tokens.append(request.config_file)
        elif tok == "<seed>":
            base_tokens.append(str(request.seed))
        elif tok == "<tripinfo>":
            base_tokens.append("tripinfo.xml")
        elif tok == "<summary>":
            base_tokens.append("summary.xml")
        else:
            base_tokens.append(tok)
    argv = [ALLOWED_EXECUTABLE_NAME, *base_tokens]

    env_keys = ["PATH", "HOME", "LANG", "LC_ALL"]

    # Canonical run identity binds request fingerprint + tool + argv
    canonical_identity = _canonical_run_identity(request, tool, argv)

    return ClosedLoopExecutionPackage(
        run_id=request.run_id,
        package_fingerprint=request.package_fingerprint,
        request_fingerprint=request.fingerprint(),
        tool=tool,
        argv=argv,
        working_directory="{PACKAGE_ROOT}",
        output_directory="{OUTPUT_ROOT}",
        timeout_seconds=request.timeout_seconds,
        deterministic_run_identity=canonical_identity,
        environment_keys=env_keys,
        shell_used=False,
        caller_supplied_arguments=False,
    )


def run_closed_loop_execution(
    *,
    package_root: Path,
    output_root: Path,
    request: ClosedLoopExecutionRequest,
    tool: ClosedLoopToolIdentity,
    executable_path: Path,
) -> ClosedLoopExecutionReceipt:
    """Execute the fixed argv locally with isolated staging and bounded receipts.

    Canonical revalidation is performed at the boundary before any file
    access or launch; forged requests are returned as typed blocked without
    launching a subprocess and without echoing raw payload.
    """

    started = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Canonical revalidation before any file read, staging, or subprocess launch
    try:
        canonical_request = ClosedLoopExecutionRequest.model_validate(
            request.model_dump(mode="json")
        )
    except Exception as exc:  # noqa: BLE001
        # Build a safe blocked receipt without launching, without leaking raw payload
        # Use generic safe argv (does not echo forged config_file)
        safe_argv = [ALLOWED_EXECUTABLE_NAME, *list(CLOSED_LOOP_FIXED_ARGV)]
        # Replace placeholders with safe sanitized values (no raw traversal)
        # For blocked due to validation, use sanitized config_file placeholder
        # to avoid leaking traversal payload in argv
        try:
            raw_cfg = str(getattr(request, "config_file", "config"))
        except Exception:
            raw_cfg = "config"
        safe_cfg = _sanitize_xml_name(raw_cfg)
        safe_argv = [
            safe_cfg
            if tok == "<config>"
            else tok
            if not tok.startswith("<")
            else safe_cfg
            if tok in {"<config>", "<seed>", "<tripinfo>", "<summary>"}
            else tok
            for tok in safe_argv
        ]
        # Actually reconstruct correctly: first token is executable, rest are fixed; handle properly
        # Rebuild properly with safe values
        safe_portable = []
        for tok in CLOSED_LOOP_FIXED_ARGV:
            if tok == "<config>":
                safe_portable.append(safe_cfg)
            elif tok == "<seed>":
                safe_portable.append("0")
            elif tok == "<tripinfo>":
                safe_portable.append("tripinfo.xml")
            elif tok == "<summary>":
                safe_portable.append("summary.xml")
            else:
                safe_portable.append(tok)
        safe_argv = [ALLOWED_EXECUTABLE_NAME, *safe_portable]
        # Sanitize error reason per error
        raw_reasons: list[str] = []
        try:
            from pydantic import ValidationError as _VE2  # noqa: N814

            if isinstance(exc, _VE2):
                for err_detail in exc.errors():
                    loc = ".".join(str(p) for p in err_detail.get("loc", ()))
                    safe_loc = _sanitize_xml_name(loc) if loc else "request"
                    msg = err_detail.get("msg", "")
                    safe_msg = _SECRET_TOKEN_RE.sub("REDACTED", msg)
                    safe_msg = _PRIVATE_PATH_RE.sub("{REDACTED}", safe_msg)
                    safe_msg = safe_msg[:200]
                    raw_reasons.append(f"REQUEST_VALIDATION_FAILED: {safe_loc} {safe_msg}")
                if not raw_reasons:
                    raw_reasons.append("REQUEST_VALIDATION_FAILED: invalid request")
            else:
                raw_reasons.append(
                    f"REQUEST_VALIDATION_FAILED: {_sanitize_xml_name(str(exc))[:200]}"
                )
        except Exception:
            raw_reasons.append("REQUEST_VALIDATION_FAILED: invalid request")
        sanitized_reasons = [_sanitize_finding_text(r) for r in raw_reasons]
        reason = "; ".join(s for s in sanitized_reasons if s)
        if not reason:
            reason = "REQUEST_VALIDATION_FAILED: blocked"
        # Build blocked receipt without launching
        completed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        try:
            if datetime.fromisoformat(completed.replace("Z", "+00:00")) < datetime.fromisoformat(
                started.replace("Z", "+00:00")
            ):
                completed = started
        except Exception:
            completed = started
        try:
            s_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            c_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            duration = max(0.0, (c_dt - s_dt).total_seconds())
        except Exception:
            duration = 0.0
        # Deterministic identity for blocked: bind request fingerprint (original) + tool + safe_argv
        try:
            fp = request.fingerprint()
        except Exception:
            fp = _sha256_hex(b"invalid:" + str(raw_reasons).encode())
        # Use synthetic blocked preflight fingerprint
        blocked_preflight = _sha256_hex(b"blocked:" + fp.encode())
        # Compute canonical identity with safe argv
        try:
            det_identity = _canonical_run_identity(request, tool, safe_argv)
        except Exception:
            det_identity = _sha256_hex((fp + tool.executable_sha256 + "".join(safe_argv)).encode())
        # Use model_construct to avoid re-validating forged request
        return ClosedLoopExecutionReceipt.model_construct(
            _fields_set=set(),
            run_id=getattr(request, "run_id", "run-01")
            if isinstance(getattr(request, "run_id", None), str)
            else "run-01",
            request=request,
            request_fingerprint=fp,
            preflight_fingerprint=blocked_preflight,
            tool=tool,
            argv=safe_argv,
            working_directory="{PACKAGE_ROOT}",
            output_directory="{OUTPUT_ROOT}",
            started_at_utc=started,
            completed_at_utc=completed,
            duration_s=duration,
            exit_code=None,
            timed_out=False,
            outcome="blocked",
            stdout_excerpt="",
            stderr_excerpt=_sanitize_text(reason)[:MAX_LOG_BYTES]
            if reason
            else "REQUEST_VALIDATION_FAILED: blocked",
            outputs=[],
            output_fingerprint=None,
            inputs_verified=False,
            deterministic_run_identity=det_identity,
            engineering_standing=ENGINEERING_NOT_VALID,
            scientific_standing=SCIENTIFICALLY_NOT_ACCEPTED,
            limitations=list(CLOSED_LOOP_LIMITATIONS),
            shell_used=False,
            caller_supplied_arguments=False,
            secrets_exposed=False,
            schema_version=CLOSED_LOOP_SCHEMA_VERSION,
            method_version=CLOSED_LOOP_METHOD_VERSION,
            capability_id=CLOSED_LOOP_CAPABILITY_ID,
        )

    # Bind to canonical validated request thereafter
    request = canonical_request

    pkg = Path(package_root)
    out = Path(output_root)

    if request.confirmed_by_operator is not True:
        raise ManchesterClosedLoopError(
            "OPERATOR_AUTHORISATION_REQUIRED", "request not operator-authorised"
        )

    if executable_path.name != ALLOWED_EXECUTABLE_NAME:
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_NOT_ALLOWLISTED",
            f"only '{ALLOWED_EXECUTABLE_NAME}' is allowlisted; got {executable_path.name!r}",
        )
    if executable_path.is_symlink():
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_SYMLINK",
            "configured SUMO executable must not be a symlink",
        )
    if not executable_path.is_file():
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_MISSING",
            "configured SUMO executable is not a regular file",
        )
    if _sha256_file(executable_path) != tool.executable_sha256:
        raise ManchesterClosedLoopError(
            "SUMO_IDENTITY_DRIFT", "executable identity changed before launch"
        )
    if not tool.reported_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
        raise ManchesterClosedLoopError(
            "SUMO_VERSION_DRIFT",
            f"SUMO {tool.reported_version} not in reviewed {SUPPORTED_SUMO_VERSION_PREFIX}x",
        )

    def _portable_argv_for_request() -> list[str]:
        tokens: list[str] = []
        for tok in CLOSED_LOOP_FIXED_ARGV:
            if tok == "<config>":
                tokens.append(request.config_file)
            elif tok == "<seed>":
                tokens.append(str(request.seed))
            elif tok == "<tripinfo>":
                tokens.append("tripinfo.xml")
            elif tok == "<summary>":
                tokens.append("summary.xml")
            else:
                tokens.append(tok)
        return [ALLOWED_EXECUTABLE_NAME, *tokens]

    portable_blocked_argv = _portable_argv_for_request()
    canonical_blocked_identity = _canonical_run_identity(request, tool, portable_blocked_argv)

    def _blocked_receipt(reason: str, inputs_verified: bool = False) -> ClosedLoopExecutionReceipt:
        completed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        # Ensure ordering not reversed: if completed < started, set completed = started
        try:
            if datetime.fromisoformat(completed.replace("Z", "+00:00")) < datetime.fromisoformat(
                started.replace("Z", "+00:00")
            ):
                completed = started
        except Exception:
            completed = started
        # Compute duration that matches UTC timestamps within tolerance
        try:
            s_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            c_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            duration = max(0.0, (c_dt - s_dt).total_seconds())
        except Exception:
            duration = 0.0
        sanitized_reason = _sanitize_text(reason)[:MAX_LOG_BYTES]
        if not sanitized_reason.strip():
            sanitized_reason = "BLOCKED: sanitized"
        return ClosedLoopExecutionReceipt(
            run_id=request.run_id,
            request=request,
            request_fingerprint=request.fingerprint(),
            preflight_fingerprint=_sha256_hex(b"blocked:" + request.fingerprint().encode()),
            tool=tool,
            argv=portable_blocked_argv,
            working_directory="{PACKAGE_ROOT}",
            output_directory="{OUTPUT_ROOT}",
            started_at_utc=started,
            completed_at_utc=completed,
            duration_s=duration,
            exit_code=None,
            timed_out=False,
            outcome="blocked",
            stdout_excerpt="",
            stderr_excerpt=sanitized_reason,
            outputs=[],
            output_fingerprint=None,
            inputs_verified=inputs_verified,
            deterministic_run_identity=canonical_blocked_identity,
            engineering_standing=ENGINEERING_NOT_VALID,
            scientific_standing=SCIENTIFICALLY_NOT_ACCEPTED,
            limitations=list(CLOSED_LOOP_LIMITATIONS),
            shell_used=False,
            caller_supplied_arguments=False,
            secrets_exposed=False,
        )

    # Pre-launch input verification (includes size bounds)
    errors = _verify_declared_inputs(pkg, request)
    if errors:
        sanitized = [_sanitize_finding_text(e) for e in errors]
        reason = "; ".join(s for s in sanitized if s)
        if not reason:
            reason = "INPUT_VERIFICATION_FAILED: blocked"
        return _blocked_receipt(reason)

    # Config preflight — untrusted execution control
    cfg_errors = _preflight_config_xml(pkg, request)
    if cfg_errors:
        sanitized_cfg = [_sanitize_finding_text(e) for e in cfg_errors]
        reason_cfg = "; ".join(s for s in sanitized_cfg if s)
        if not reason_cfg:
            reason_cfg = "CONFIG_PREFLIGHT_FAILED: blocked"
        return _blocked_receipt(reason_cfg)

    # Output isolation
    iso_err = _validate_output_root(out, pkg)
    if iso_err is not None:
        return _blocked_receipt(iso_err)

    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.mkdir(mode=0o700)
    except FileExistsError:
        return _blocked_receipt("output directory must not already exist")
    staging = out / "_staging"
    staging.mkdir(mode=0o700)

    # Aggregate check on declared inputs before streaming copy
    declared_total = sum(d.size_bytes for d in request.inputs)
    if declared_total > MAX_AGGREGATE_INPUT_BYTES:
        with contextlib.suppress(Exception):
            shutil.rmtree(out, ignore_errors=True)
        return _blocked_receipt(f"INPUT_AGGREGATE_OVERSIZE: {declared_total} exceeds bound")
    for decl in request.inputs:
        if decl.size_bytes > MAX_INPUT_BYTES:
            with contextlib.suppress(Exception):
                shutil.rmtree(out, ignore_errors=True)
            return _blocked_receipt(f"INPUT_OVERSIZE: {decl.path} exceeds per-file bound")

    # Copy only verified declared regular non-symlink inputs into staging via streaming
    try:
        for decl in request.inputs:
            src = pkg / decl.path
            if src.is_symlink():
                raise ManchesterClosedLoopError(
                    "INPUT_SYMLINK", f"staged input symlink: {decl.path}"
                )
            if not src.is_file():
                raise ManchesterClosedLoopError(
                    "INPUT_MISSING", f"staged input missing: {decl.path}"
                )
            # Size check before streaming where possible
            try:
                actual_size = src.stat().st_size
            except OSError as exc:
                raise ManchesterClosedLoopError(
                    "INPUT_UNREADABLE", f"cannot stat {decl.path}"
                ) from exc
            if actual_size > MAX_INPUT_BYTES:
                raise ManchesterClosedLoopError(
                    "INPUT_OVERSIZE", f"{decl.path} {actual_size} exceeds bound"
                )
            if actual_size != decl.size_bytes:
                raise ManchesterClosedLoopError(
                    "STAGED_SIZE_MISMATCH",
                    f"staged mismatch: {decl.path} {decl.size_bytes} vs {actual_size}",
                )
            dst = staging / decl.path
            # Ensure parent exists (for subdirs, though request currently flat)
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Stream copy + hash, verify staged hash after write without read_bytes
            h = hashlib.sha256()
            total = 0
            with src.open("rb") as s_fh, dst.open("wb") as d_fh:
                while True:
                    chunk = s_fh.read(1 << 20)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_INPUT_BYTES:
                        raise ManchesterClosedLoopError(
                            "INPUT_OVERSIZE_DURING_COPY", f"{decl.path} exceeds bound"
                        )
                    h.update(chunk)
                    d_fh.write(chunk)
            if total != decl.size_bytes:
                raise ManchesterClosedLoopError(
                    "STAGED_SIZE_MISMATCH", f"staged size mismatch after copy: {decl.path}"
                )
            if h.hexdigest() != decl.sha256:
                raise ManchesterClosedLoopError(
                    "STAGED_HASH_MISMATCH", f"staged hash mismatch: {decl.path}"
                )
            # Reject symlink in staging
            if dst.is_symlink():
                raise ManchesterClosedLoopError(
                    "STAGED_SYMLINK", f"staged became symlink: {decl.path}"
                )
            # Verify staged file hash after write via streaming (already verified)
            if dst.stat().st_size != decl.size_bytes:
                raise ManchesterClosedLoopError(
                    "STAGED_SIZE_VERIFY_FAILED", f"staged size verify: {decl.path}"
                )
    except ManchesterClosedLoopError as exc:
        # Cleanup and return blocked
        with contextlib.suppress(Exception):
            shutil.rmtree(out, ignore_errors=True)
        return _blocked_receipt(str(exc))

    # Re-verify source package not changed after copy (drift before staging)
    post_copy_errors = _verify_declared_inputs(pkg, request)
    if post_copy_errors:
        with contextlib.suppress(Exception):
            shutil.rmtree(out, ignore_errors=True)
        return _blocked_receipt("; ".join(post_copy_errors))

    # Build real argv with isolated paths
    real_argv: list[str] = [str(executable_path)]
    for item in CLOSED_LOOP_FIXED_ARGV:
        if item == "<config>":
            real_argv.append(str(staging / request.config_file))
        elif item == "<seed>":
            real_argv.append(str(request.seed))
        elif item == "<tripinfo>":
            real_argv.append(str(out / "tripinfo.xml"))
        elif item == "<summary>":
            real_argv.append(str(out / "summary.xml"))
        else:
            real_argv.append(item)

    env = _controlled_environment(executable_path, staging)

    started_monotonic = time.monotonic()
    timed_out = False
    exit_code: int | None = None

    portable_tokens: list[str] = []
    for tok in CLOSED_LOOP_FIXED_ARGV:
        if tok == "<config>":
            portable_tokens.append(request.config_file)
        elif tok == "<seed>":
            portable_tokens.append(str(request.seed))
        elif tok == "<tripinfo>":
            portable_tokens.append("tripinfo.xml")
        elif tok == "<summary>":
            portable_tokens.append("summary.xml")
        else:
            portable_tokens.append(tok)
    receipt_argv = [ALLOWED_EXECUTABLE_NAME, *portable_tokens]
    canonical_run_identity = _canonical_run_identity(request, tool, receipt_argv)

    # Bounded execution with pipe-draining collectors (no unbounded file sinks)
    stdout_buf = bytearray()
    stderr_buf = bytearray()
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(  # noqa: S603 - fixed validated argv, shell=False
            real_argv,
            cwd=str(staging),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
        t_out = threading.Thread(
            target=_bounded_drain, args=(proc.stdout, stdout_buf, MAX_LOG_BYTES), daemon=True
        )
        t_err = threading.Thread(
            target=_bounded_drain, args=(proc.stderr, stderr_buf, MAX_LOG_BYTES), daemon=True
        )
        t_out.start()
        t_err.start()
        deadline = started_monotonic + request.timeout_seconds
        while True:
            try:
                exit_code = proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() > deadline:
                    timed_out = True
                    _terminate_process_group(proc)
                    break
        if exit_code is None:
            try:
                exit_code = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _terminate_process_group(proc)
                try:
                    exit_code = proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    exit_code = None
        # Ensure drain threads finish (bounded)
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        # Optionally write bounded excerpts to staging files for debugging, but capped
        try:
            (staging / "stdout.txt").write_bytes(bytes(stdout_buf[:MAX_LOG_BYTES]))
            (staging / "stderr.txt").write_bytes(bytes(stderr_buf[:MAX_LOG_BYTES]))
        except OSError:
            pass
        stdout_text = _sanitize_text(stdout_buf.decode("utf-8", errors="replace"))
        stderr_text = _sanitize_text(stderr_buf.decode("utf-8", errors="replace"))
    except (OSError, subprocess.SubprocessError) as exc:
        if proc is not None:
            with contextlib.suppress(Exception):
                _terminate_process_group(proc)
        stdout_text = _sanitize_text(
            stdout_buf.decode("utf-8", errors="replace") if stdout_buf else ""
        )
        stderr_text = _sanitize_text(str(exc))
        exit_code = None
        timed_out = False
        completed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        duration = max(0.0, time.monotonic() - started_monotonic)
        # Align duration with wall-clock for validation tolerance
        try:
            s_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            c_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            duration = max(duration, 0.0)
            # Ensure duration matches timestamps within tolerance
            expected = (c_dt - s_dt).total_seconds()
            if abs(duration - expected) > 2.0:
                duration = expected
        except Exception:  # noqa: S110
            pass
        preflight_fp = _preflight_fingerprint(request, tool)
        return ClosedLoopExecutionReceipt(
            run_id=request.run_id,
            request=request,
            request_fingerprint=request.fingerprint(),
            preflight_fingerprint=preflight_fp,
            tool=tool,
            argv=receipt_argv,
            working_directory="{PACKAGE_ROOT}",
            output_directory="{OUTPUT_ROOT}",
            started_at_utc=started,
            completed_at_utc=completed,
            duration_s=duration,
            exit_code=exit_code,
            timed_out=timed_out,
            outcome="failed",
            stdout_excerpt=stdout_text,
            stderr_excerpt=stderr_text,
            outputs=[],
            output_fingerprint=None,
            inputs_verified=False,
            deterministic_run_identity=canonical_run_identity,
            engineering_standing=ENGINEERING_NOT_VALID,
            scientific_standing=SCIENTIFICALLY_NOT_ACCEPTED,
            limitations=list(CLOSED_LOOP_LIMITATIONS),
            shell_used=False,
            caller_supplied_arguments=False,
            secrets_exposed=False,
        )
    finally:
        if proc is not None:
            with contextlib.suppress(Exception):
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()

    completed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    duration = max(0.0, time.monotonic() - started_monotonic)
    # Ensure time ordering not reversed and duration matches wall-clock within tolerance
    try:
        s_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        c_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        if c_dt < s_dt:
            completed = started
            duration = 0.0
        else:
            expected = (c_dt - s_dt).total_seconds()
            # If monotonic duration diverges beyond tolerance, align to wall-clock
            if abs(duration - expected) > 2.0:
                duration = expected
    except Exception:
        completed = started
        duration = 0.0

    # Verify source package unchanged after run (input drift)
    after_errors = _verify_declared_inputs(pkg, request)
    inputs_verified = len(after_errors) == 0 and len(errors) == 0
    # Also verify staging still matches (prevent drift)
    if inputs_verified:
        for decl in request.inputs:
            staged = staging / decl.path
            try:
                if staged.is_symlink() or not staged.is_file():
                    inputs_verified = False
                    break
                if _sha256_file(staged) != decl.sha256 or staged.stat().st_size != decl.size_bytes:
                    inputs_verified = False
                    break
            except OSError:
                inputs_verified = False
                break

    output_errors: list[str] = []
    # Bind/verify _staging to close blind spot: staging must contain only declared inputs + bounded logs  # noqa: E501
    try:
        expected_staging = {PurePosixPath(d.path).name for d in request.inputs} | {
            "stdout.txt",
            "stderr.txt",
        }
        # Also account for declared paths that may include subdirectories — check full relative POSIX path  # noqa: E501
        expected_staging_full = {d.path for d in request.inputs} | {"stdout.txt", "stderr.txt"}
        # Second pass: actually detect extra (single iteration; previous placeholder loop removed)
        for child in staging.iterdir():
            # Allow benign macOS system artifacts that may be auto-created when HOME=staging (e.g., Library)  # noqa: E501
            if child.name in {"Library", ".DS_Store", "__pycache__"}:
                continue
            if child.name in expected_staging_full or child.name in expected_staging:
                # For file entries, verify not symlink and expected; subdir handling: if declared inputs have subdirs, the immediate child dir would be expected  # noqa: E501
                # Check if any declared input path starts with child.name + "/"
                is_expected_dir = any(d.path.startswith(child.name + "/") for d in request.inputs)
                if child.is_dir() and is_expected_dir:
                    # Need to recurse? For V1 flat inputs, no subdirs expected; for safety, walk expected subdirs  # noqa: E501
                    # Verify no extra files inside expected subdir beyond declared inputs
                    try:
                        for sub in child.rglob("*"):
                            rel_sub = sub.relative_to(staging).as_posix()
                            if rel_sub in expected_staging_full:
                                if sub.is_symlink():
                                    output_errors.append(f"STAGING_SYMLINK_REJECTED: {rel_sub}")
                                continue
                            if sub.is_symlink():
                                output_errors.append(f"STAGING_SYMLINK_REJECTED: {rel_sub}")
                            elif sub.is_file() or sub.is_dir():
                                output_errors.append(f"STAGING_EXTRA_REJECTED: {rel_sub}")
                    except OSError as exc2:
                        output_errors.append(f"OUTPUT_ENUM_FAILED: staging walk {exc2}")
                    continue
                if child.is_symlink():
                    output_errors.append(f"STAGING_SYMLINK_REJECTED: {child.name}")
                elif child.is_file():
                    # Already expected (stdout/stderr or declared file) — but verify not symlink already handled; keep  # noqa: E501
                    continue
                elif child.is_dir():
                    output_errors.append(f"STAGING_EXTRA_DIR_REJECTED: {child.name}")
                continue
            # Not in expected set => extra blind-spot file/dir/symlink
            if child.name in {"Library", ".DS_Store", "__pycache__"}:
                continue
            if child.is_symlink():
                output_errors.append(f"STAGING_SYMLINK_REJECTED: {child.name}")
            elif child.is_file():
                output_errors.append(f"STAGING_EXTRA_REJECTED: {child.name}")
            elif child.is_dir():
                # Check if dir is prefix of declared input path (allowed)
                is_expected_dir2 = any(d.path.startswith(child.name + "/") for d in request.inputs)
                if is_expected_dir2:
                    # Walk inside
                    try:
                        for sub in child.rglob("*"):
                            rel_sub = sub.relative_to(staging).as_posix()
                            if rel_sub in expected_staging_full:
                                if sub.is_symlink():
                                    output_errors.append(f"STAGING_SYMLINK_REJECTED: {rel_sub}")
                                continue
                            if sub.is_symlink():
                                output_errors.append(f"STAGING_SYMLINK_REJECTED: {rel_sub}")
                            elif sub.is_file() or sub.is_dir():
                                output_errors.append(f"STAGING_EXTRA_REJECTED: {rel_sub}")
                    except OSError as exc3:
                        output_errors.append(f"OUTPUT_ENUM_FAILED: staging walk {exc3}")
                    continue
                output_errors.append(f"STAGING_EXTRA_DIR_REJECTED: {child.name}")
            else:
                output_errors.append(f"STAGING_EXTRA_REJECTED: {child.name}")
    except OSError as exc_staging:
        output_errors.append(f"OUTPUT_ENUM_FAILED: staging {exc_staging}")

    # Collect outputs — size before hashing, aggregate, symlinks, extra, missing/duplicate/drift
    outputs: list[ClosedLoopFileEvidence] = []
    # output_errors already may contain staging blind-spot errors
    total_bytes = 0
    expected_names = {"tripinfo.xml", "summary.xml"}
    # Extra artifacts in output_root (excluding _staging)
    try:
        for child in out.iterdir():
            if child.name == "_staging":
                continue
            # Only expected outputs should be present; any other file is extra
            if child.name not in expected_names:
                # Allow no other files; staging logs are inside _staging
                if child.is_symlink():
                    output_errors.append(f"OUTPUT_SYMLINK_REJECTED: {child.name}")
                elif child.is_file():
                    output_errors.append(f"OUTPUT_EXTRA_REJECTED: {child.name}")
                elif child.is_dir():
                    output_errors.append(f"OUTPUT_EXTRA_DIR_REJECTED: {child.name}")
                else:
                    output_errors.append(f"OUTPUT_EXTRA_REJECTED: {child.name}")
    except OSError as exc:
        output_errors.append(f"OUTPUT_ENUM_FAILED: {exc}")

    for name in ("tripinfo.xml", "summary.xml"):
        p = out / name
        if p.is_symlink():
            output_errors.append(f"OUTPUT_SYMLINK_REJECTED: {name}")
            continue
        if not p.is_file():
            # Will be handled as missing later, but record
            continue
        try:
            size = p.stat().st_size
        except OSError:
            output_errors.append(f"OUTPUT_UNREADABLE: {name}")
            continue
        # Check size BEFORE hashing
        if size > MAX_OUTPUT_BYTES:
            output_errors.append(f"OUTPUT_OVERSIZE: {name} {size} > {MAX_OUTPUT_BYTES}")
            continue
        total_bytes += size
        if total_bytes > MAX_AGGREGATE_OUTPUT_BYTES:
            output_errors.append(
                f"OUTPUT_AGGREGATE_OVERSIZE: {total_bytes} > {MAX_AGGREGATE_OUTPUT_BYTES}"
            )
            # Do not break, continue to collect errors
        try:
            sha = _sha256_file(p)
            outputs.append(ClosedLoopFileEvidence(path=name, sha256=sha, size_bytes=size))
        except OSError:
            output_errors.append(f"OUTPUT_HASH_FAILED: {name}")
            continue

    output_fp = _output_fingerprint(outputs) if outputs else None

    outcome: Literal["completed", "failed", "timed_out", "blocked"]
    stderr_combined = stderr_text
    if timed_out:
        outcome = "timed_out"
    elif exit_code == 0:
        required = {"tripinfo.xml", "summary.xml"}
        present = {o.path for o in outputs}
        missing = sorted(required - present)
        has_duplicates = len(present) != len(outputs)
        has_wrong_set = present != required or len(outputs) != 2
        if output_errors:
            outcome = "failed"
            diag = "; ".join(output_errors[:3])
            combined = f"{stderr_text}\n{diag}" if stderr_text else diag
            stderr_combined = _sanitize_text(combined)[:MAX_LOG_BYTES]
        elif missing or has_duplicates or has_wrong_set or not inputs_verified:
            outcome = "failed"
            if not inputs_verified:
                diag = "INPUT_DRIFT_DETECTED: source or staged inputs changed"
            elif missing:
                diag = f"REQUIRED_OUTPUT_MISSING: {', '.join(missing)}"
            else:
                diag = "REQUIRED_OUTPUT_MISSING: incomplete or duplicate required outputs"
            combined = f"{stderr_text}\n{diag}" if stderr_text else diag
            stderr_combined = _sanitize_text(combined)[:MAX_LOG_BYTES]
        else:
            outcome = "completed"
    elif exit_code is not None and exit_code != 0:
        outcome = "failed"
        if output_errors:
            diag = "; ".join(output_errors[:3])
            combined = f"{stderr_text}\n{diag}" if stderr_text else diag
            stderr_combined = _sanitize_text(combined)[:MAX_LOG_BYTES]
    else:
        outcome = "failed"

    # If inputs not verified, outcome cannot be completed
    if not inputs_verified and outcome == "completed":
        outcome = "failed"

    preflight_fp = _preflight_fingerprint(request, tool)
    stdout_text = _sanitize_text(stdout_text)
    stderr_text = _sanitize_text(stderr_combined)
    outcome_str: str = outcome
    if not stderr_text.strip() and (outcome_str != "completed" or stderr_combined.strip()):
        stderr_text = "BLOCKED: sanitized" if outcome_str == "blocked" else "FAILED: sanitized"
    if not stdout_text.strip() and stdout_text == "":
        # stdout may legitimately be empty on success; keep empty
        pass

    eng: Literal["SOFTWARE_VALID", "ENGINEERING_NOT_VALID"] = (
        ENGINEERING_SOFTWARE_VALID if outcome == "completed" else ENGINEERING_NOT_VALID
    )
    sci: Literal["SCIENTIFICALLY_NOT_ACCEPTED"] = SCIENTIFICALLY_NOT_ACCEPTED

    # Ensure bounded excerpts
    if len(stdout_text) > MAX_LOG_BYTES:
        stdout_text = stdout_text[:MAX_LOG_BYTES]
    if len(stderr_text) > MAX_LOG_BYTES:
        stderr_text = stderr_text[:MAX_LOG_BYTES]

    return ClosedLoopExecutionReceipt(
        run_id=request.run_id,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint=preflight_fp,
        tool=tool,
        argv=receipt_argv,
        working_directory="{PACKAGE_ROOT}",
        output_directory="{OUTPUT_ROOT}",
        started_at_utc=started,
        completed_at_utc=completed,
        duration_s=duration,
        exit_code=exit_code,
        timed_out=timed_out,
        outcome=outcome,
        stdout_excerpt=stdout_text,
        stderr_excerpt=stderr_text,
        outputs=outputs,
        output_fingerprint=output_fp,
        inputs_verified=inputs_verified,
        deterministic_run_identity=canonical_run_identity,
        engineering_standing=eng,
        scientific_standing=sci,
        limitations=list(CLOSED_LOOP_LIMITATIONS),
        shell_used=False,
        caller_supplied_arguments=False,
        secrets_exposed=False,
    )


__all__ = [
    "CLOSED_LOOP_CAPABILITY_ID",
    "CLOSED_LOOP_FIXED_ARGV",
    "CLOSED_LOOP_LIMITATIONS",
    "CLOSED_LOOP_METHOD_VERSION",
    "CLOSED_LOOP_SCHEMA_VERSION",
    "ALLOWED_EXECUTABLE_NAME",
    "DEFAULT_TIMEOUT_S",
    "ENGINEERING_SOFTWARE_VALID",
    "ENGINEERING_NOT_VALID",
    "SCIENTIFICALLY_NOT_ACCEPTED",
    "SCIENTIFIC_ACCEPTED_BASELINE",
    "SUPPORTED_SUMO_VERSION_PREFIX",
    "MAX_CONFIG_BYTES",
    "MAX_OUTPUT_BYTES",
    "MAX_AGGREGATE_OUTPUT_BYTES",
    "MAX_INPUT_BYTES",
    "MAX_AGGREGATE_INPUT_BYTES",
    "MAX_LOG_BYTES",
    "MAX_VERSION_CAPTURE_BYTES",
    "ClosedLoopExecutionPackage",
    "ClosedLoopExecutionReceipt",
    "ClosedLoopExecutionRequest",
    "ClosedLoopFileEvidence",
    "ClosedLoopInputDeclaration",
    "ClosedLoopPreflightReport",
    "ClosedLoopToolIdentity",
    "ManchesterClosedLoopError",
    "ManchesterClosedLoopModel",
    "build_closed_loop_execution_package",
    "create_closed_loop_request",
    "detect_configured_sumo",
    "preflight_closed_loop_execution",
    "run_closed_loop_execution",
]
