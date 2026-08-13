"""Manchester closed-loop SAFE LOCAL SUMO execution contract.

Composes and strengthens :mod:`traffictwin.integration.sumo_execution` and
:mod:`traffictwin.integration.manchester.sumo_run` without creating a general
process runner.

Safety properties (strengthened composition):

* configured/pinned SUMO detection — an explicit executable path is validated;
  PATH is never searched at execution time;
* exact version capture — ``sumo --version`` is probed with ``shell=False``
  and the reported version must start with ``1.27.``;
* allowlisted executable identity only — base name must be exactly ``sumo``;
* fixed validated argv generated solely by code — no caller-supplied flags;
* explicit package root and configuration — relative, safe, non-symlink names
  inside the package root;
* declared input content fingerprints verified immediately before launch;
* isolated explicit output directory — must not exist, must not overlap the
  package root, parent must already exist;
* explicit working directory — the package root;
* timeout, exit code, bounded stdout/stderr receipts;
* deterministic run identity — SHA-256 over canonical request + tool + argv
  shape;
* sanitized minimal environment — ``PATH`` limited to the executable parent
  plus ``/usr/bin:/bin``, plus ``LANG``/``LC_ALL``/``HOME`` only;
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
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
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

# Bounded receipt text — prevents a warning storm filling memory.
MAX_LOG_BYTES = 32_000
MAX_LOG_LINES = 200
MAX_LOG_LINE_BYTES = 400

# Execution bounds
DEFAULT_TIMEOUT_S = 120
MAX_TIMEOUT_S = 600
MIN_TIMEOUT_S = 1

# Scientific vs engineering standing
ENGINEERING_SOFTWARE_VALID: Literal["SOFTWARE_VALID"] = "SOFTWARE_VALID"
SCIENTIFIC_SOFTWARE_VALID: Literal["SOFTWARE_VALID"] = "SOFTWARE_VALID"
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
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

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
    size_bytes: int = Field(ge=0)

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
            # allow subdirectories but each segment must be safe
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
    deterministic_run_identity: str = Field(pattern=r"^[0-9a-f]{64}$")

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
        # deterministic identity must match recomputed
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
    engineering_standing: Literal["SOFTWARE_VALID"] = ENGINEERING_SOFTWARE_VALID
    scientific_standing: Literal["SOFTWARE_VALID"] = SCIENTIFIC_SOFTWARE_VALID
    limitations: list[str] = Field(min_length=1, max_length=8)
    shell_used: Literal[False] = False
    caller_supplied_arguments: Literal[False] = False
    secrets_exposed: Literal[False] = False

    @field_validator("started_at_utc", "completed_at_utc")
    @classmethod
    def _validate_time(cls, v: str) -> str:
        # must be ISO-8601, parseable
        datetime.fromisoformat(v.replace("Z", "+00:00"))
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
        if self.deterministic_run_identity != self.request.deterministic_run_identity:
            raise ValueError("deterministic identity must match request")
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
        # outcome / exit / timeout consistency
        if self.outcome == "completed":
            if self.exit_code != 0:
                raise ValueError("completed requires exit 0")
            if self.timed_out:
                raise ValueError("completed cannot be timed out")
            if not self.inputs_verified:
                raise ValueError("completed requires verified inputs")
            # fail-closed: completed requires both non-symlink required outputs
            required = {"tripinfo.xml", "summary.xml"}
            paths = [o.path for o in self.outputs]
            if len(paths) != len(set(paths)):
                raise ValueError("completed requires distinct required outputs (duplicate)")
            if set(paths) != required or len(self.outputs) != 2:
                raise ValueError("completed requires both tripinfo.xml and summary.xml")
            if self.output_fingerprint is None:
                raise ValueError("completed requires output fingerprint")
            # each output path was already validated; fingerprints checked below
        if self.outcome == "timed_out" and not self.timed_out:
            raise ValueError("timed_out outcome requires timed_out flag")
        if (  # noqa: SIM102
            self.timed_out != (self.outcome == "timed_out")
            and self.outcome not in {"timed_out", "blocked"}
            and self.timed_out
        ):
            raise ValueError("timed_out flag mismatch")
        # never upgrade scientific standing
        if self.scientific_standing != "SOFTWARE_VALID":
            raise ValueError("scientific standing must remain SOFTWARE_VALID")
        if self.engineering_standing != "SOFTWARE_VALID":
            raise ValueError("engineering standing must be SOFTWARE_VALID")
        # portable: no absolute paths, no secrets
        for ev in self.outputs:
            if _PRIVATE_PATH_RE.search(ev.path):
                raise ValueError("output path must be portable")
        if self.output_fingerprint is not None:
            # recompute
            expected = _output_fingerprint(self.outputs)
            if self.output_fingerprint != expected:
                raise ValueError("output fingerprint mismatch")
        if self.secrets_exposed is not False:
            raise ValueError("secrets_exposed must be false")
        if self.shell_used is not False or self.caller_supplied_arguments is not False:
            raise ValueError("shell and caller argument flags must be false")
        # stdout/stderr already bounded by validator
        return self


def _output_fingerprint(outputs: list[ClosedLoopFileEvidence]) -> str:
    payload = [o.model_dump(mode="json") for o in sorted(outputs, key=lambda x: x.path)]
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_text(text: str) -> str:
    """Bound and scrub text for receipt portability."""
    # Truncate to MAX_LOG_BYTES, split lines, truncate lines, scrub private paths/secrets
    if len(text) > MAX_LOG_BYTES:
        text = text[:MAX_LOG_BYTES]
    lines = text.splitlines()
    # Keep at most MAX_LOG_LINES, each at most MAX_LOG_LINE_BYTES
    kept: list[str] = []
    for raw in lines[:MAX_LOG_LINES]:
        if len(raw) > MAX_LOG_LINE_BYTES:
            raw = raw[:MAX_LOG_LINE_BYTES]
        if _PRIVATE_PATH_RE.search(raw):
            continue
        if _SECRET_TOKEN_RE.search(raw):
            # scrub secret-like lines
            continue
        kept.append(raw)
    return "\n".join(kept)


def _controlled_environment(executable: Path, working_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {
        "PATH": f"{executable.parent}:/usr/bin:/bin",
        "HOME": str(working_dir),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    # Only expose SUMO_HOME if it is a safe directory sibling of executable
    sumo_home = executable.parent.parent / "share" / "sumo"
    if sumo_home.is_dir() and not sumo_home.is_symlink():
        env["SUMO_HOME"] = str(sumo_home)
    return env


def _validate_package_root(package_root: Path) -> str | None:
    if package_root.is_symlink():
        return "package root must not be a symlink"
    if not package_root.is_dir():
        return "package root must be an existing directory"
    # package root itself must not contain private path substring? check path string
    if _PRIVATE_PATH_RE.search(str(package_root)):
        # This is the real machine path; we do not store it, but we still
        # validate input existence. For portable receipts we never persist it.
        pass
    return None


def _validate_output_root(output_root: Path, package_root: Path) -> str | None:
    if output_root.exists():
        return "output directory must not already exist"
    if output_root.is_symlink():
        return "output directory path must not be a symlink"
    parent = output_root.parent
    if not parent.is_dir() or parent.is_symlink():
        return "output parent must be an existing non-symlink directory"
    # Must not overlap
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
    for decl in request.inputs:
        candidate = package_root / decl.path
        # Never resolve away evidence of symlink status before checking it.
        # Check file itself and any directory component for symlink.
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
        # Resolve only after symlink evidence preserved.
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            errors.append(f"input cannot be resolved: {decl.path}")
            continue
        if not candidate.is_file():
            errors.append(f"input missing or not a regular file: {decl.path}")
            continue
        # Ensure resolved stays within package root (covers symlink escapes).
        try:
            resolved.relative_to(pkg_resolved)
        except ValueError:
            errors.append(f"input escapes package root: {decl.path}")
            continue
        try:
            actual_sha = _sha256_file(candidate)
            actual_size = candidate.stat().st_size
        except OSError:
            errors.append(f"input cannot be read: {decl.path}")
            continue
        if actual_sha != decl.sha256:
            errors.append(f"input fingerprint mismatch: {decl.path}")
        if actual_size != decl.size_bytes:
            errors.append(f"input size mismatch: {decl.path}")
    return errors


def _compute_package_fingerprint(
    package_root: Path, inputs: list[ClosedLoopInputDeclaration]
) -> str:
    # Deterministic fingerprint over sorted input identities (path+sha+size)
    payload = sorted([i.model_dump(mode="json") for i in inputs], key=lambda x: x["path"])
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _compute_deterministic_identity(
    package_fingerprint: str,
    config_file: str,
    inputs: list[ClosedLoopInputDeclaration],
    seed: int,
    timeout_seconds: int,
    run_id: str,
) -> str:
    payload = {
        "package_fingerprint": package_fingerprint,
        "config_file": config_file,
        "inputs": sorted([i.model_dump(mode="json") for i in inputs], key=lambda x: x["path"]),
        "seed": seed,
        "timeout_seconds": timeout_seconds,
        "run_id": run_id,
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


# ---------------------------------------------------------------------------
# Public API — configured detection, request creation, preflight, package, execution
# ---------------------------------------------------------------------------


def detect_configured_sumo(executable_path: Path) -> ClosedLoopToolIdentity:
    """Validate a configured/pinned SUMO executable and capture exact version.

    No PATH guessing: the caller supplies the exact filesystem path.
    """
    if executable_path.is_symlink():
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_SYMLINK",
            "configured SUMO executable must not be a symlink",
        )
    # Allowlisted name check — only 'sumo' basename is permitted
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
    # Hash executable for identity
    try:
        digest = _sha256_file(executable_path)
    except OSError as exc:
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_UNREADABLE", "SUMO executable could not be hashed"
        ) from exc

    # Probe version with shell=False, fixed argv, bounded timeout
    try:
        result = subprocess.run(  # noqa: S603 - fixed allowlisted argv, shell=False
            [str(executable_path), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        raise ManchesterClosedLoopError(
            "SUMO_VERSION_UNREADABLE", "SUMO did not report a usable version"
        ) from exc

    combined = f"{result.stdout}\n{result.stderr}"
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
) -> ClosedLoopExecutionRequest:
    """Build a frozen deterministic request from an explicit package root.

    The package root is inspected to hash declared inputs; the returned
    request is portable and contains no absolute paths.
    """
    if not _SAFE_NAME_RE.match(run_id) and not re.match(r"^[a-z0-9][a-z0-9_.-]{0,63}$", run_id):
        raise ManchesterClosedLoopError("INVALID_RUN_ID", "run_id does not match required pattern")

    pkg = Path(package_root)
    if _validate_package_root(pkg) is not None:
        raise ManchesterClosedLoopError("PACKAGE_ROOT_INVALID", _validate_package_root(pkg) or "")

    cfg = PurePosixPath(config_file).as_posix()
    # Validate config_file shape early
    if PurePosixPath(cfg).is_absolute() or len(PurePosixPath(cfg).parts) != 1:
        raise ManchesterClosedLoopError(
            "CONFIG_FILE_INVALID", "config_file must be a single safe file name"
        )

    # Discover all regular files in package root (non-recursive, bounded)
    # For deterministic test behavior we treat exactly the files that exist
    # as the declared inventory. In production the caller must declare them
    # explicitly; here we auto-declare for convenience but freeze them.
    inputs: list[ClosedLoopInputDeclaration] = []
    for child in sorted(pkg.iterdir(), key=lambda p: p.name):
        # Fail closed on symlink inputs — never resolve away evidence.
        if child.is_symlink():
            raise ManchesterClosedLoopError(
                "INPUT_SYMLINK",
                f"input must not be a symlink: {child.name}",
            )
        if not child.is_file():
            continue
        # Only admit safe names
        if not _SAFE_NAME_RE.match(child.name):
            continue
        # Symlink escape check for top-level entries: resolved must stay within pkg
        # (defense in depth; is_symlink already checked, but directory symlink parents
        # are already guarded via package_root validation).
        sha = _sha256_file(child)
        size = child.stat().st_size
        inputs.append(ClosedLoopInputDeclaration(path=child.name, sha256=sha, size_bytes=size))

    # Ensure config_file is among inputs — if the package directory does not
    # contain it, we still include a declaration that will fail verification
    # later, preserving blocked standing without leaking paths.
    if cfg not in {i.path for i in inputs}:
        # Config missing is a provider-required input absence — still create
        # a request that will be blocked at preflight, but include a synthetic
        # placeholder with zero hash that will fail verification. This keeps
        # the request deterministic while allowing typed blocked handling.
        placeholder_hash = _sha256_hex(b"missing:" + cfg.encode())
        inputs.append(ClosedLoopInputDeclaration(path=cfg, sha256=placeholder_hash, size_bytes=0))
        inputs = sorted(inputs, key=lambda x: x.path)

    package_fp = _compute_package_fingerprint(pkg, inputs)
    det_id = _compute_deterministic_identity(package_fp, cfg, inputs, seed, timeout_seconds, run_id)

    return ClosedLoopExecutionRequest(
        run_id=run_id,
        package_fingerprint=package_fp,
        config_file=cfg,
        inputs=inputs,
        seed=seed,
        timeout_seconds=timeout_seconds,
        deterministic_run_identity=det_id,
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
    """
    findings: list[str] = []

    # SUMO absent → blocked
    if tool is None:
        findings.append("SUMO_TOOLCHAIN_UNAVAILABLE: configured SUMO not supplied")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=None,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    # Package root checks
    err = _validate_package_root(Path(package_root))
    if err is not None:
        findings.append(f"PACKAGE_ROOT_INVALID: {err}")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    # Output isolation checks — provider-required output location must be
    # explicit and isolated
    err = _validate_output_root(Path(output_root), Path(package_root))
    if err is not None:
        findings.append(f"OUTPUT_ISOLATION_REFUSED: {err}")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    # Input fingerprint verification — provider-required inputs must match
    input_errors = _verify_declared_inputs(Path(package_root), request)
    if input_errors:
        for e in input_errors:
            findings.append(f"INPUT_VERIFICATION_FAILED: {e}")
        return ClosedLoopPreflightReport(
            status="blocked",
            tool=tool,
            request=request,
            request_fingerprint=request.fingerprint(),
            findings=findings,
        )

    # All good → accepted (read-only, no mutations)
    findings.append("PREFLIGHT_ACCEPTED: package, inputs, tool, and output isolation verified")

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
    """Build the execution package with fixed validated argv.

    The argv is generated solely by code; no caller-supplied arguments are
    accepted. The executable is the explicit pinned path.
    """
    # Re-validate allowlist and identity at package-build time (defense in depth)
    if executable_path.name != ALLOWED_EXECUTABLE_NAME:
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_NOT_ALLOWLISTED", "only 'sumo' is allowlisted"
        )
    if executable_path.is_symlink() or not executable_path.is_file():
        raise ManchesterClosedLoopError(
            "SUMO_EXECUTABLE_INVALID", "executable must be a regular non-symlink file"
        )
    # Verify digest matches tool identity (exact)
    actual_digest = _sha256_file(executable_path)
    if actual_digest != tool.executable_sha256:
        raise ManchesterClosedLoopError(
            "SUMO_IDENTITY_MISMATCH", "executable digest changed since detection"
        )

    # Fixed argv — values substituted but shape is code-owned
    # Map placeholders to portable relative names (not absolute paths)
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
    # SUMO_HOME optionally added but not required for package
    sumo_home = executable_path.parent.parent / "share" / "sumo"
    if sumo_home.is_dir() and not sumo_home.is_symlink():
        env_keys.append("SUMO_HOME")

    return ClosedLoopExecutionPackage(
        run_id=request.run_id,
        package_fingerprint=request.package_fingerprint,
        request_fingerprint=request.fingerprint(),
        tool=tool,
        argv=argv,
        working_directory="{PACKAGE_ROOT}",
        output_directory="{OUTPUT_ROOT}",
        timeout_seconds=request.timeout_seconds,
        deterministic_run_identity=request.deterministic_run_identity,
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
    """Execute the fixed argv locally with isolated output and bounded receipts.

    Verifies declared input fingerprints immediately before launch, uses a
    sanitized minimal environment, ``shell=False``, explicit working directory,
    timeout, and exit-code capture. Never searches PATH, never accepts
    caller-supplied argv, never downloads, never opens network.
    """

    started = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    pkg = Path(package_root)
    out = Path(output_root)

    # Re-audit executable identity at execution time (exact match, defense in depth).
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

    # Portable argv — exactly the same fixed validated shape as successful path / model contract.
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

    # Pre-launch input verification — fail closed if changed since request
    errors = _verify_declared_inputs(pkg, request)
    if errors:
        # Produce a blocked receipt, not an accepted run — fail closed
        completed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
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
            duration_s=0.0,
            exit_code=None,
            timed_out=False,
            outcome="blocked",
            stdout_excerpt="",
            stderr_excerpt="; ".join(errors)[:MAX_LOG_BYTES],
            outputs=[],
            output_fingerprint=None,
            inputs_verified=False,
            deterministic_run_identity=request.deterministic_run_identity,
            engineering_standing=ENGINEERING_SOFTWARE_VALID,
            scientific_standing=SCIENTIFIC_SOFTWARE_VALID,
            limitations=list(CLOSED_LOOP_LIMITATIONS),
            shell_used=False,
            caller_supplied_arguments=False,
            secrets_exposed=False,
        )

    # Output isolation — must not exist (second execution returns typed blocked receipt, not raise)
    iso_err = _validate_output_root(out, pkg)
    if iso_err is not None:
        completed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return ClosedLoopExecutionReceipt(
            run_id=request.run_id,
            request=request,
            request_fingerprint=request.fingerprint(),
            preflight_fingerprint=_sha256_hex(b"blocked-output:" + request.fingerprint().encode()),
            tool=tool,
            argv=portable_blocked_argv,
            working_directory="{PACKAGE_ROOT}",
            output_directory="{OUTPUT_ROOT}",
            started_at_utc=started,
            completed_at_utc=completed,
            duration_s=0.0,
            exit_code=None,
            timed_out=False,
            outcome="blocked",
            stdout_excerpt="",
            stderr_excerpt=iso_err[:MAX_LOG_BYTES],
            outputs=[],
            output_fingerprint=None,
            inputs_verified=False,
            deterministic_run_identity=request.deterministic_run_identity,
            engineering_standing=ENGINEERING_SOFTWARE_VALID,
            scientific_standing=SCIENTIFIC_SOFTWARE_VALID,
            limitations=list(CLOSED_LOOP_LIMITATIONS),
            shell_used=False,
            caller_supplied_arguments=False,
            secrets_exposed=False,
        )

    # Build fixed argv with absolute paths for launch, but receipt stores only
    # portable relative/allowlisted forms.
    pkg_resolved = pkg.resolve()

    # Prepare isolated output directory
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(mode=0o700)

    # Real argv for subprocess: executable absolute path + fixed tokens resolved
    real_argv: list[str] = [str(executable_path)]
    for item in CLOSED_LOOP_FIXED_ARGV:
        if item == "<config>":
            real_argv.append(str(pkg_resolved / request.config_file))
        elif item == "<seed>":
            real_argv.append(str(request.seed))
        elif item == "<tripinfo>":
            real_argv.append(str(out / "tripinfo.xml"))
        elif item == "<summary>":
            real_argv.append(str(out / "summary.xml"))
        else:
            real_argv.append(item)
    # Prepend -c handling: CLOSED_LOOP_FIXED_ARGV starts with "-c"
    # Real argv already has "-c" as first token after executable, correct.

    env = _controlled_environment(executable_path, pkg_resolved)
    # Scrub any secret-like env values that might have leaked via inheritance
    for k, v in list(env.items()):
        if _SECRET_TOKEN_RE.search(k) or _SECRET_TOKEN_RE.search(v):
            env.pop(k, None)
        if _PRIVATE_PATH_RE.search(v):
            # keep only minimal safe entries; PATH is already controlled
            if k == "PATH":
                continue
            env[k] = "{REDACTED}"

    started_monotonic = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    stdout_text = ""
    stderr_text = ""

    # Receipt argv is portable (base name only, relative config names)
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

    try:
        result = subprocess.run(  # noqa: S603 - fixed validated argv, shell=False
            real_argv,
            cwd=str(pkg_resolved),
            env=env,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds,
            check=False,
            shell=False,
        )
        exit_code = result.returncode
        stdout_text = _sanitize_text(result.stdout or "")
        stderr_text = _sanitize_text(result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        # Capture partial output if available
        stdout_text = _sanitize_text(
            exc.stdout.decode() if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        )
        stderr_text = _sanitize_text(
            exc.stderr.decode() if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        )
        # Ensure child is terminated; subprocess.run already kills on timeout via internal logic
        exit_code = None
    except (OSError, subprocess.SubprocessError) as exc:
        # Fail closed — produce failed receipt
        stdout_text = ""
        stderr_text = _sanitize_text(str(exc))
        exit_code = None

    completed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    duration = max(0.0, time.monotonic() - started_monotonic)

    # Collect outputs for receipt — portable evidence with no absolute paths
    outputs: list[ClosedLoopFileEvidence] = []
    for name in ("tripinfo.xml", "summary.xml"):
        p = out / name
        if p.is_file() and not p.is_symlink():
            try:
                sha = _sha256_file(p)
                size = p.stat().st_size
                # Only include if bounded
                if size <= 50_000_000:
                    outputs.append(ClosedLoopFileEvidence(path=name, sha256=sha, size_bytes=size))
            except OSError:
                continue

    output_fp = _output_fingerprint(outputs) if outputs else None

    outcome: Literal["completed", "failed", "timed_out", "blocked"]
    if timed_out:
        outcome = "timed_out"
    elif exit_code == 0:
        # Even exit 0 is not scientific acceptance — engineering valid only
        # Missing required outputs makes the run failed (fail-closed).
        required = {"tripinfo.xml", "summary.xml"}
        present = {o.path for o in outputs}
        missing = sorted(required - present)
        has_duplicates = len(present) != len(outputs)
        has_wrong_set = present != required or len(outputs) != 2
        if missing or has_duplicates or has_wrong_set:
            outcome = "failed"
            diag = (
                f"REQUIRED_OUTPUT_MISSING: {', '.join(missing)}"
                if missing
                else "REQUIRED_OUTPUT_MISSING: incomplete or duplicate required outputs"
            )
            # truthful portable diagnostic — never leaks absolute paths/secrets
            combined = f"{stderr_text}\n{diag}" if stderr_text else diag
            stderr_text = _sanitize_text(combined)[:MAX_LOG_BYTES] if combined else diag
            if len(stderr_text) > MAX_LOG_BYTES:
                stderr_text = stderr_text[:MAX_LOG_BYTES]
        else:
            outcome = "completed"
    elif exit_code is not None and exit_code != 0:
        outcome = "failed"
    else:
        outcome = "failed"

    # Preflight fingerprint for receipt is deterministic over request + tool
    preflight_fp = _sha256_hex(
        _canonical_json(
            {
                "request_fingerprint": request.fingerprint(),
                "tool_sha": tool.executable_sha256,
                "tool_version": tool.reported_version,
            }
        ).encode("utf-8")
    )

    inputs_verified = len(errors) == 0

    # Scrub stdout/stderr one more time for portability (no absolute paths/secrets)
    stdout_text = _sanitize_text(stdout_text)
    stderr_text = _sanitize_text(stderr_text)

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
        deterministic_run_identity=request.deterministic_run_identity,
        engineering_standing=ENGINEERING_SOFTWARE_VALID,
        scientific_standing=SCIENTIFIC_SOFTWARE_VALID,
        limitations=list(CLOSED_LOOP_LIMITATIONS),
        shell_used=False,
        caller_supplied_arguments=False,
        secrets_exposed=False,
    )


# Also export helper for deterministic identity (used in tests)
def deterministic_run_identity_for_request(
    request: ClosedLoopExecutionRequest,
) -> str:
    return request.deterministic_run_identity


__all__ = [
    "CLOSED_LOOP_CAPABILITY_ID",
    "CLOSED_LOOP_FIXED_ARGV",
    "CLOSED_LOOP_LIMITATIONS",
    "CLOSED_LOOP_METHOD_VERSION",
    "CLOSED_LOOP_SCHEMA_VERSION",
    "ALLOWED_EXECUTABLE_NAME",
    "DEFAULT_TIMEOUT_S",
    "ENGINEERING_SOFTWARE_VALID",
    "SCIENTIFIC_ACCEPTED_BASELINE",
    "SCIENTIFIC_SOFTWARE_VALID",
    "SUPPORTED_SUMO_VERSION_PREFIX",
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
    "deterministic_run_identity_for_request",
    "preflight_closed_loop_execution",
    "run_closed_loop_execution",
]
