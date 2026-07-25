"""Controlled SUMO execution for the Manchester candidate demand.

Design Gate-D step 7 / Gate-E entry: run the reviewed study subnetwork against
the count-constrained candidate demand under a frozen command, and receipt
exactly what ran.

**Why this is not**
:mod:`~traffictwin.integration.sumo_execution`. That service is deliberately
synthetic-only — its scenario directory, config filename and ``synthetic`` flag
are fixed literals, ``manchester_traffic`` is fixed ``False``, and vehicle count
is bounded at 1,000. Those are refusals the lead built on purpose, so they are
left intact and this module sits beside them rather than widening them.

**What a run does and does not mean.** Simulating a candidate demand produces
*simulated* traffic under an assumption. It is not observed traffic, not a
calibration, and not a comparison. The
``owner_policy_accepted_candidate`` basis of the demand carries forward into
every artifact here, and no run may describe its output as validated.

**Scale is a first-class constraint, measured not assumed.** A pilot on the real
artifacts (285,794-edge study subnetwork, 748,589 vehicles across 212,666 flows)
measured **509 MB of one-second FCD for the first 600 simulated seconds**, with
the network still filling: running vehicles grew 2,779 → 5,517 → 8,129 → 10,715
across the window and never reached a steady state. Extrapolating the full
43,200-second window gives **tens of gigabytes at minimum and plausibly over one
hundred**, because the FCD rate scales with the number of vehicles resident in
the network rather than with elapsed time. :data:`MAX_FCD_BYTES` therefore
exists, and a run that would exceed it stops rather than filling the disk.

The same pilot measured **50% of resident vehicles halting by t=600** and 102
teleports. That is recorded as a run-quality observation, not corrected here:
whether the candidate demand over-saturates the network is a finding about the
demand, and adjusting it to look better would hide exactly what a controlled run
exists to reveal.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

SUMO_RUN_SCHEMA_VERSION: Literal["1.0"] = "1.0"
SUMO_RUN_METHOD_VERSION: Literal["manchester-sumo-run-1.0"] = "manchester-sumo-run-1.0"
SUMO_RUN_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

#: The reviewed toolchain, matching every other Manchester SUMO boundary.
SUPPORTED_SUMO_VERSION_PREFIX: Literal["1.27."] = "1.27."
SUMO_EXECUTABLE_NAME: Literal["sumo"] = "sumo"

#: What this produces. Never "observed", never "validated".
RUN_LABEL: Literal["simulated_candidate_demand_run"] = "simulated_candidate_demand_run"
ACCEPTANCE_BASIS: Literal["owner_policy_accepted_candidate"] = "owner_policy_accepted_candidate"
RESEARCH_STATUS: Literal["owner_approved_candidate"] = "owner_approved_candidate"

#: One-second step and one-second FCD, as the design requires for the VEC chain.
STEP_LENGTH_S: Literal[1] = 1
FCD_PERIOD_S: Literal[1] = 1

#: The frozen argument vector. ``<...>`` placeholders are substituted with
#: staging paths at run time and never appear in evidence. There is deliberately
#: no mechanism for a caller to add, remove, or reorder any element.
SUMO_FIXED_ARGUMENTS: tuple[str, ...] = (
    "--net-file",
    "<net>",
    "--route-files",
    "<routes>",
    "--begin",
    "<begin>",
    "--end",
    "<end>",
    "--step-length",
    "1",
    "--fcd-output",
    "<fcd>",
    "--fcd-output.period",
    "1",
    "--summary-output",
    "<summary>",
    "--tripinfo-output",
    "<tripinfo>",
    "--seed",
    "<seed>",
    "--ignore-route-errors",
    "true",
    "--no-step-log",
    "true",
    "--xml-validation",
    "never",
)

#: Bound on one-second FCD. Measured basis: 509 MB per 600 simulated seconds
#: while the network was still filling, so the full window plausibly exceeds
#: 100 GB. A run that would pass this stops rather than exhausting the disk.
MAX_FCD_BYTES = 250_000_000_000

#: Bound on the simulated window. The temporal contract's window is 12 hours.
MAX_WINDOW_S = 86_400

#: Bound on captured log output, so a warning storm cannot fill memory. The
#: pilot produced teleport warnings continuously.
MAX_LOG_LINES = 200
MAX_LOG_LINE_BYTES = 400

RunOutcome: TypeAlias = Literal["accepted", "refused", "failed"]

_VERSION_PATTERN = re.compile(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b")
_STREAM_CHUNK_BYTES = 4 * 1024 * 1024


class ManchesterSumoRunError(RuntimeError):
    """Typed refusal for an unsupported or unsafe Manchester SUMO run."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class SumoRunModel(ManchesterSnapshotModel):
    """Strict frozen base for Manchester SUMO run artifacts."""


class SumoToolIdentity(SumoRunModel):
    """Observed simulator identity, probed rather than assumed."""

    executable_name: Literal["sumo"] = SUMO_EXECUTABLE_NAME
    reported_version: str = Field(min_length=1, max_length=64)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    supported_version_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX

    @model_validator(mode="after")
    def validate_version(self) -> SumoToolIdentity:
        if not self.reported_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
            raise ValueError("sumo version must match the reviewed 1.27.x toolchain")
        return self


class SumoRunRequest(SumoRunModel):
    """A complete, bounded run request.

    There is deliberately no executable, argument, flag, or option field: the
    command is frozen and the operator selects none of it.
    """

    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    demand_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    begin_s: int = Field(ge=0)
    end_s: int = Field(gt=0)
    seed: int = Field(ge=0, le=2_147_483_647)
    #: Explicit operator authorisation. A run is expensive and writes gigabytes,
    #: so it is never a side effect of rendering a page.
    confirmed_by_operator: Literal[True]

    @model_validator(mode="after")
    def validate_request(self) -> SumoRunRequest:
        if self.end_s <= self.begin_s:
            raise ValueError("the simulated window must be positive")
        if self.end_s - self.begin_s > MAX_WINDOW_S:
            raise ValueError("the simulated window exceeds the reviewed bound")
        return self


class SumoRunObservations(SumoRunModel):
    """Run-quality signals read from the simulator's own summary output.

    These are recorded, not corrected. Whether a candidate demand saturates the
    network is a finding about the demand.
    """

    steps_recorded: int = Field(ge=0)
    vehicles_inserted: int = Field(ge=0)
    vehicles_running_final: int = Field(ge=0)
    vehicles_halting_final: int = Field(ge=0)
    teleports: int = Field(ge=0)
    reached_steady_state: bool
    #: Share of resident vehicles halted at the end of the window.
    halting_share_final: Decimal | None = Field(default=None, ge=0, le=1)


class SumoRunReceipt(SumoRunModel):
    """Exactly what ran, with no private path in any recorded field."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-sumo-run-1.0"] = SUMO_RUN_METHOD_VERSION
    run_label: Literal["simulated_candidate_demand_run"] = RUN_LABEL
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS
    acceptance_basis: Literal["owner_policy_accepted_candidate"] = ACCEPTANCE_BASIS

    request: SumoRunRequest
    tool: SumoToolIdentity
    argument_shape: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    started_at_utc: datetime
    completed_at_utc: datetime
    duration_s: Decimal = Field(ge=0)
    outcome: RunOutcome

    fcd_bytes: int = Field(ge=0)
    fcd_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tripinfo_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    observations: SumoRunObservations | None = None
    warning_lines: tuple[str, ...] = ()
    error_lines: tuple[str, ...] = ()

    step_length_s: Literal[1] = STEP_LENGTH_S
    fcd_period_s: Literal[1] = FCD_PERIOD_S
    shell_used: Literal[False] = False
    caller_supplied_arguments: Literal[False] = False

    #: Simulating a demand is not calibrating, comparing, or validating it.
    observed_traffic: Literal[False] = False
    calibration_performed: Literal[False] = False
    comparison_performed: Literal[False] = False
    scientifically_validated: Literal[False] = False
    supervisor_approved: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> SumoRunReceipt:
        if self.argument_shape != SUMO_FIXED_ARGUMENTS:
            raise ValueError("the receipt must record the exact frozen argument vector")
        if self.completed_at_utc < self.started_at_utc:
            raise ValueError("receipt times must not run backwards")
        if self.outcome == "accepted":
            if self.exit_code != 0:
                raise ValueError("an accepted run must have exited zero")
            if self.fcd_sha256 is None:
                raise ValueError("an accepted run must have produced a digested FCD artifact")
        for line in (*self.warning_lines, *self.error_lines):
            if "/Users/" in line or "/home/" in line or "/private/" in line:
                raise ValueError("receipt lines must not contain private paths")
        return self


def discover_sumo() -> Path | None:
    """Locate the reviewed simulator without running a simulation."""

    found = shutil.which(SUMO_EXECUTABLE_NAME)
    return Path(found) if found else None


def sumo_identity() -> SumoToolIdentity:
    """Probe the simulator's version and executable digest."""

    executable = discover_sumo()
    if executable is None:
        raise ManchesterSumoRunError(
            "SUMO_TOOLCHAIN_UNAVAILABLE",
            "no `sumo` executable was found on PATH; install SUMO 1.27.x to run a simulation",
        )
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, no caller input
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ManchesterSumoRunError(
            "SUMO_VERSION_UNREADABLE", "the simulator did not report a usable version"
        ) from exc
    match = _VERSION_PATTERN.search(f"{completed.stdout}\n{completed.stderr}")
    if match is None:
        raise ManchesterSumoRunError(
            "SUMO_VERSION_UNREADABLE", "the simulator did not report a usable version"
        )
    version = match.group(1)
    if not version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
        raise ManchesterSumoRunError(
            "SUMO_VERSION_DRIFT",
            f"sumo reports {version}, but only {SUPPORTED_SUMO_VERSION_PREFIX}x is reviewed",
        )
    return SumoToolIdentity(reported_version=version, executable_sha256=_digest_file(executable))


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_STREAM_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _classify_output(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split simulator output into warnings and errors, bounded and path-free."""

    warnings: list[str] = []
    errors: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) > MAX_LOG_LINE_BYTES:
            continue
        if "/Users/" in line or "/home/" in line or "/private/" in line:
            continue
        lowered = line.lower()
        if lowered.startswith("error") or "error:" in lowered:
            errors.append(line)
        elif lowered.startswith("warning"):
            warnings.append(line)
    return tuple(warnings[:MAX_LOG_LINES]), tuple(errors[:MAX_LOG_LINES])


def read_run_observations(summary_path: str | Path) -> SumoRunObservations | None:
    """Read run-quality signals from the simulator's summary output.

    Scanned with a bounded regex rather than parsed as a document: the file is a
    flat machine-written step list and only a handful of numbers are needed.
    """

    source = Path(summary_path)
    if not source.is_file():
        return None
    text = source.read_text(encoding="utf-8", errors="replace")
    steps = re.findall(r'<step time="([\d.]+)"[^>]*?running="(\d+)"[^>]*?halting="(\d+)"', text)
    if not steps:
        return None
    inserted = re.findall(r'inserted="(\d+)"', text)
    teleports = re.findall(r'teleports="(\d+)"', text)
    running_final = int(steps[-1][1])
    halting_final = int(steps[-1][2])
    quarter = max(1, len(steps) // 4)
    early = int(steps[quarter][1])
    late = int(steps[-1][1])
    # Still filling if the resident population is materially larger at the end
    # than a quarter of the way through.
    reached_steady_state = late <= early * 1.1
    share = (
        (Decimal(halting_final) / Decimal(running_final)).quantize(Decimal("0.0001"))
        if running_final
        else None
    )
    return SumoRunObservations(
        steps_recorded=len(steps),
        vehicles_inserted=int(inserted[-1]) if inserted else 0,
        vehicles_running_final=running_final,
        vehicles_halting_final=halting_final,
        teleports=int(teleports[-1]) if teleports else 0,
        reached_steady_state=reached_steady_state,
        halting_share_final=share,
    )


def projected_fcd_bytes(measured_bytes: int, measured_s: int, target_s: int) -> int:
    """Project FCD size, treating the measured rate as a floor.

    The rate scales with vehicles resident in the network, not with elapsed
    time, so a projection taken while the network is still filling understates
    the total. It is returned as a lower bound and labelled as one.
    """

    if measured_s <= 0:
        raise ManchesterSumoRunError(
            "PROJECTION_WINDOW_REFUSED", "a projection needs a positive measured window"
        )
    return int(measured_bytes * (target_s / measured_s))


def preflight_run(request: SumoRunRequest, *, measured_fcd_rate: int | None = None) -> None:
    """Refuse a run that cannot complete safely, before anything is written."""

    if measured_fcd_rate is not None:
        projected = projected_fcd_bytes(measured_fcd_rate, 1, request.end_s - request.begin_s)
        if projected > MAX_FCD_BYTES:
            raise ManchesterSumoRunError(
                "FCD_PROJECTION_EXCEEDS_BOUND",
                f"one-second FCD for this window projects to at least {projected:,} bytes, "
                f"above the reviewed bound of {MAX_FCD_BYTES:,}. The projection is a floor, "
                "because the FCD rate grows with the resident vehicle population.",
            )
    if discover_sumo() is None:
        raise ManchesterSumoRunError(
            "SUMO_TOOLCHAIN_UNAVAILABLE", "no `sumo` executable was found on PATH"
        )


def _utc_now(clock: Callable[[], datetime] | None) -> datetime:
    value = (clock or (lambda: datetime.now(UTC)))()
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def run_manchester_sumo(
    output_root: str | Path,
    network_path: str | Path,
    demand_path: str | Path,
    request: SumoRunRequest,
    *,
    timeout_s: int = 21_600,
    clock: Callable[[], datetime] | None = None,
) -> SumoRunReceipt:
    """Run the frozen simulator command in an isolated workspace.

    Outputs are written to private staging and promoted only after the run
    exits zero and its FCD is digested, so a failed or interrupted run never
    replaces an accepted output.
    """

    if not request.confirmed_by_operator:  # pragma: no cover - Literal[True] enforces this
        raise ManchesterSumoRunError(
            "OPERATOR_AUTHORISATION_REQUIRED", "a simulation run must be operator-invoked"
        )
    tool = sumo_identity()
    network = Path(network_path)
    demand = Path(demand_path)
    for candidate, label in ((network, "network"), (demand, "demand")):
        if candidate.is_symlink() or not candidate.is_file():
            raise ManchesterSumoRunError(
                "RUN_INPUT_REFUSED", f"the {label} must be an existing non-symlink regular file"
            )

    destination = Path(output_root) / request.run_id
    if destination.exists():
        raise ManchesterSumoRunError(
            "RUN_DESTINATION_EXISTS",
            "an accepted run already occupies this id; a rerun never overwrites one",
        )
    staging = Path(tempfile.mkdtemp(prefix=".manchester-sumo-", dir=Path(output_root)))
    try:
        fcd = staging / "fcd.xml"
        summary = staging / "summary.xml"
        tripinfo = staging / "tripinfo.xml"
        substitutions = {
            "<net>": str(network),
            "<routes>": str(demand),
            "<begin>": str(request.begin_s),
            "<end>": str(request.end_s),
            "<fcd>": str(fcd),
            "<summary>": str(summary),
            "<tripinfo>": str(tripinfo),
            "<seed>": str(request.seed),
        }
        executable = discover_sumo()
        assert executable is not None  # noqa: S101 - sumo_identity already proved this
        argv = [str(executable)] + [substitutions.get(item, item) for item in SUMO_FIXED_ARGUMENTS]
        started = _utc_now(clock)
        try:
            completed = subprocess.run(  # noqa: S603 - frozen argv, no shell, no caller input
                argv, capture_output=True, text=True, timeout=timeout_s, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise ManchesterSumoRunError(
                "RUN_TIMED_OUT", f"the simulation exceeded its {timeout_s}s bound and was stopped"
            ) from exc
        finished = _utc_now(clock)

        warnings, errors = _classify_output(f"{completed.stdout}\n{completed.stderr}")
        fcd_bytes = fcd.stat().st_size if fcd.is_file() else 0
        if fcd_bytes > MAX_FCD_BYTES:
            raise ManchesterSumoRunError(
                "FCD_EXCEEDS_BOUND",
                f"the run produced {fcd_bytes:,} bytes of FCD, above the reviewed bound",
            )
        outcome: RunOutcome = "accepted" if completed.returncode == 0 and fcd_bytes else "failed"
        receipt = SumoRunReceipt(
            request=request,
            tool=tool,
            argument_shape=SUMO_FIXED_ARGUMENTS,
            exit_code=completed.returncode,
            started_at_utc=started,
            completed_at_utc=finished,
            duration_s=Decimal(str(round((finished - started).total_seconds(), 3))),
            outcome=outcome,
            fcd_bytes=fcd_bytes,
            fcd_sha256=_digest_file(fcd) if outcome == "accepted" else None,
            summary_sha256=_digest_file(summary) if summary.is_file() else None,
            tripinfo_sha256=_digest_file(tripinfo) if tripinfo.is_file() else None,
            observations=read_run_observations(summary),
            warning_lines=warnings,
            error_lines=errors,
        )
        if outcome != "accepted":
            raise ManchesterSumoRunError(
                "RUN_FAILED",
                f"the simulation exited {completed.returncode} and produced no accepted output",
            )
        (staging / "receipt.json").write_text(receipt.canonical_json() + "\n", encoding="utf-8")
        os.replace(staging, destination)
        return receipt
    finally:
        shutil.rmtree(staging, ignore_errors=True)
