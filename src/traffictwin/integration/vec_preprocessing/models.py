"""Strict portable artifacts for VEC-06 FCD/network preprocessing."""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VEC_FCD_SCHEMA_VERSION = "1.0"
VEC_FCD_METHOD_VERSION = "vec-fcd-preprocessing-1.0"
VEC_FCD_CAPABILITY_ID = "VEC-06"
PINNED_VEC_ENV_COMMIT = "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
PINNED_SOURCE_FILES = {
    "eval/build_trace.py": "5af3aa9b284dd06a9e25989fbb7e9060227c7906a2754e9c5436ddd925090387",
    "eval/place_rsus_cover.py": (
        "33928f4113988ee39f75ff06d99f2c01061182f9d0f17092e051a159a42840a0"
    ),
}

MAX_FCD_BYTES = 128_000_000
MAX_NETWORK_BYTES = 64_000_000
MAX_TIMESTEPS = 100_000
MAX_VEHICLES_PER_TIMESTEP = 10_000
MAX_VEHICLE_OBSERVATIONS = 20_000_000
MAX_DENSE_TRACE_CELLS = 50_000_000
MAX_OCCUPIED_PLACEMENT_CELLS = 5_000
MAX_TIMEOUT_SECONDS = 1_800

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")


class VecPreprocessingModel(BaseModel):
    """Strict finite base model for VEC-06 artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class VecPreflightStatus(StrEnum):
    """Outcome of the read-only VEC-06 preflight."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class VecFindingSeverity(StrEnum):
    """Closed severity vocabulary for preprocessing findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class VecGreedyUrbanPlacement(VecPreprocessingModel):
    """Explicit bounded parameters for the pinned two-dimensional set-cover script."""

    strategy: Literal["greedy_urban_cover"] = "greedy_urban_cover"
    radius_m: float = Field(default=500.0, ge=10.0, le=5_000.0)
    cell_m: float = Field(default=50.0, ge=1.0, le=500.0)
    max_rsus: int = Field(default=64, ge=1, le=256)
    max_occupied_cells: int = Field(
        default=2_000,
        ge=1,
        le=MAX_OCCUPIED_PLACEMENT_CELLS,
    )

    @model_validator(mode="after")
    def validate_effective_radius(self) -> VecGreedyUrbanPlacement:
        if self.radius_m <= self.cell_m * math.sqrt(2.0) / 2.0:
            raise ValueError("radius_m must exceed the grid-cell half diagonal")
        return self


class VecFcdPreprocessRequest(VecPreprocessingModel):
    """Path-safe, bounded request for one pinned FCD/network preprocessing run."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-06"] = "VEC-06"
    source_commit: Literal["068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"] = (
        "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
    )
    input_id: str
    scenario_day: str
    window_label: str
    fcd_file: str
    network_file: str
    fcd_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sumo_seed: int = Field(ge=0, le=2_147_483_647)
    placement: VecGreedyUrbanPlacement = Field(default_factory=VecGreedyUrbanPlacement)
    coordinate_tolerance_m: float = Field(default=1.0, ge=0.0, le=1_000.0)
    max_fcd_bytes: int = Field(default=64_000_000, ge=1, le=MAX_FCD_BYTES)
    max_network_bytes: int = Field(default=32_000_000, ge=1, le=MAX_NETWORK_BYTES)
    max_timesteps: int = Field(default=86_400, ge=1, le=MAX_TIMESTEPS)
    max_vehicles_per_timestep: int = Field(
        default=5_000,
        ge=1,
        le=MAX_VEHICLES_PER_TIMESTEP,
    )
    max_vehicle_observations: int = Field(
        default=10_000_000,
        ge=1,
        le=MAX_VEHICLE_OBSERVATIONS,
    )
    max_dense_trace_cells: int = Field(
        default=20_000_000,
        ge=1,
        le=MAX_DENSE_TRACE_CELLS,
    )
    timeout_seconds: int = Field(default=300, ge=1, le=MAX_TIMEOUT_SECONDS)

    @field_validator("input_id", "scenario_day", "window_label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if not _LABEL_RE.fullmatch(value):
            raise ValueError("labels must use 1-96 ASCII letters, numbers, '.', '_' or '-'")
        return value

    @field_validator("fcd_file", "network_file")
    @classmethod
    def validate_relative_file(cls, value: str) -> str:
        if len(value) > 256 or "\\" in value:
            raise ValueError("input files must be bounded POSIX relative paths")
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("input files must be safe relative paths")
        return path.as_posix()

    @model_validator(mode="after")
    def validate_files(self) -> VecFcdPreprocessRequest:
        if self.fcd_file == self.network_file:
            raise ValueError("FCD and network files must be distinct")
        if not self.fcd_file.lower().endswith(".xml"):
            raise ValueError("the pinned builder accepts an uncompressed FCD XML file")
        if not self.network_file.lower().endswith(".xml"):
            raise ValueError("the pinned builder accepts a SUMO network XML file")
        return self

    def canonical_json(self) -> str:
        """Return deterministic path-safe request JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint every declared preprocessing control and input identity."""

        return _sha256(self.canonical_json().encode("utf-8"))


class VecFileEvidence(VecPreprocessingModel):
    """Portable identity for one input, source, log, or generated artifact."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str
    read_only: bool

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("evidence paths must be safe and relative")
        return path.as_posix()


class VecSourceScriptEvidence(VecPreprocessingModel):
    """One exact source script loaded from the pinned Git commit."""

    repository: Literal["vec_env"] = "vec_env"
    commit: Literal["068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"] = (
        "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
    )
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)


class VecNetworkMetadata(VecPreprocessingModel):
    """Observed network coordinate metadata required to pair FCD coordinates safely."""

    net_version: str
    net_offset_xy: tuple[float, float]
    converted_boundary_xy: tuple[float, float, float, float]
    original_boundary: tuple[float, float, float, float]
    projection_parameter: str


class VecFcdMetadata(VecPreprocessingModel):
    """Observed bounded FCD structure and one-second resolution evidence."""

    root_element: Literal["fcd-export"] = "fcd-export"
    timestep_count: int = Field(ge=1)
    first_time_s: float = Field(ge=0)
    last_time_s: float = Field(ge=0)
    timestep_seconds: float = Field(default=1.0, ge=1.0, le=1.0)
    vehicle_observation_count: int = Field(ge=1)
    unique_vehicle_count: int = Field(ge=1)
    peak_concurrent_vehicles: int = Field(ge=1)
    dense_trace_cells: int = Field(ge=1)
    occupied_placement_cells: int = Field(ge=1)
    coordinate_bounds_xy: tuple[float, float, float, float]
    coordinates_within_network_boundary: bool


class VecPreflightFinding(VecPreprocessingModel):
    """Deterministic preflight decision evidence."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$")
    severity: VecFindingSeverity
    message: str = Field(min_length=1, max_length=1_000)
    artifact: str | None = None


class VecFcdPreflightReport(VecPreprocessingModel):
    """Complete read-only admission report before any output directory exists."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-06"] = "VEC-06"
    method_version: Literal["vec-fcd-preprocessing-1.0"] = "vec-fcd-preprocessing-1.0"
    status: VecPreflightStatus
    request: VecFcdPreprocessRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_worktree_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_worktree_clean: bool
    source_origin_main: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_scripts: list[VecSourceScriptEvidence]
    inputs: list[VecFileEvidence]
    dependencies: dict[str, str]
    network: VecNetworkMetadata | None = None
    fcd: VecFcdMetadata | None = None
    findings: list[VecPreflightFinding]
    read_only: Literal[True] = True
    mutations_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_outcome(self) -> VecFcdPreflightReport:
        has_error = any(item.severity is VecFindingSeverity.ERROR for item in self.findings)
        if self.status is VecPreflightStatus.ACCEPTED and has_error:
            raise ValueError("an accepted preflight cannot contain errors")
        if self.status is VecPreflightStatus.ACCEPTED and (
            self.network is None or self.fcd is None
        ):
            raise ValueError("an accepted preflight requires network and FCD metadata")
        return self

    def canonical_json(self) -> str:
        """Return stable portable preflight JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete preflight decision."""

        return _sha256(self.canonical_json().encode("utf-8"))


class VecPreprocessCommand(VecPreprocessingModel):
    """Path-redacted allowlisted command record."""

    stage: Literal["build_trace", "place_rsus"]
    argv: list[str]
    exit_code: Literal[0] = 0
    stdout_file: str
    stderr_file: str


class VecFcdPreprocessReceipt(VecPreprocessingModel):
    """Deterministic receipt for one atomically published preprocessing result."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-06"] = "VEC-06"
    method_version: Literal["vec-fcd-preprocessing-1.0"] = "vec-fcd-preprocessing-1.0"
    status: Literal["completed"] = "completed"
    request: VecFcdPreprocessRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_worktree_head_before: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_worktree_head_after: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_worktree_clean_before: bool
    source_worktree_clean_after: bool
    source_scripts: list[VecSourceScriptEvidence]
    inputs_before: list[VecFileEvidence]
    inputs_after: list[VecFileEvidence]
    dependencies: dict[str, str]
    commands: list[VecPreprocessCommand]
    outputs: list[VecFileEvidence]
    deterministic_output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    interpretation_limits: list[str]
    external_repositories_modified: Literal[False] = False
    raw_inputs_modified: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> VecFcdPreprocessReceipt:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("receipt request fingerprint does not match request")
        if self.source_worktree_head_before != self.source_worktree_head_after:
            raise ValueError("source worktree head changed during preprocessing")
        if not self.source_worktree_clean_before or not self.source_worktree_clean_after:
            raise ValueError("source worktree must remain clean")
        before = [(item.path, item.sha256, item.size_bytes) for item in self.inputs_before]
        after = [(item.path, item.sha256, item.size_bytes) for item in self.inputs_after]
        if before != after:
            raise ValueError("raw input identity changed during preprocessing")
        expected_output_fingerprint = _output_fingerprint(self.outputs)
        if self.deterministic_output_fingerprint != expected_output_fingerprint:
            raise ValueError("deterministic output fingerprint does not match output inventory")
        return self

    def canonical_json(self) -> str:
        """Return stable portable receipt JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete receipt without filesystem paths or wall-clock state."""

        return _sha256(self.canonical_json().encode("utf-8"))


class VecFcdPreprocessingContract(VecPreprocessingModel):
    """Published, machine-readable boundary for VEC-06 preprocessing."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-06"] = "VEC-06"
    method_version: Literal["vec-fcd-preprocessing-1.0"] = "vec-fcd-preprocessing-1.0"
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_scripts: dict[str, str]
    operations: list[str]
    required_inputs: list[str]
    required_dependencies: dict[str, str]
    published_outputs: list[str]
    admission_checks: list[str]
    security_controls: list[str]
    interpretation_limits: list[str]

    def canonical_json(self) -> str:
        """Return stable contract JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete published contract."""

        return _sha256(self.canonical_json().encode("utf-8"))


def vec_fcd_preprocessing_contract() -> VecFcdPreprocessingContract:
    """Return the immutable public contract for the accepted VEC-06 method."""

    return VecFcdPreprocessingContract(
        source_commit=PINNED_VEC_ENV_COMMIT,
        source_scripts=dict(PINNED_SOURCE_FILES),
        operations=[
            "preflight_vec_fcd",
            "preprocess_vec_fcd",
        ],
        required_inputs=[
            "uncompressed SUMO FCD XML with exact one-second timesteps",
            "matching SUMO network XML with projection and converted boundary metadata",
            "caller-declared SHA-256 identities for both raw inputs",
            "explicit scenario day, window label, SUMO seed, and placement controls",
        ],
        required_dependencies={
            "numpy": ">=1.26",
            "pyproj": ">=3.6,<4",
            "sumolib": "==1.27.0",
        },
        published_outputs=[
            "trace.npz",
            "occupancy.csv",
            "rsu_placement.csv",
            "logs/build_trace.stdout.txt",
            "logs/build_trace.stderr.txt",
            "logs/place_rsus.stdout.txt",
            "logs/place_rsus.stderr.txt",
            "preprocessing_receipt.json",
        ],
        admission_checks=[
            "source repository is clean and origin/main identifies the reviewed commit",
            "source scripts match their reviewed Git-blob SHA-256 identities",
            "runtime dependencies satisfy the published versions",
            "raw inputs are regular non-symlink files with matching caller hashes",
            "XML contains no DTD or entity declaration and remains within size limits",
            "FCD timesteps are finite, strictly increasing, and exactly one second apart",
            "vehicle identifiers are unique per timestep and coordinates are finite",
            "FCD coordinates remain inside the declared network boundary plus tolerance",
            "observation, concurrency, dense-trace, and placement-cell limits are met",
        ],
        security_controls=[
            "preflight is read-only and creates no destination",
            "only exact source blobs loaded from the pinned Git commit are executed",
            "subprocesses use allowlisted argv without a shell and a controlled environment",
            "source access, raw inputs, logs, and outputs are rehashed and validated",
            "publication uses a private staging directory and atomic new-only rename",
            "published artifacts are made read-only and never overwrite prior evidence",
            "allow_pickle=True is isolated inside the reviewed placement script; "
            "TrafficTwin reads NPZ with allow_pickle=False",
        ],
        interpretation_limits=[
            "preprocessing does not prove that the supplied FCD and network were "
            "generated together",
            "greedy_urban_cover produces analysis sites, not evidence of real deployed RSUs",
            "a completed receipt is software-execution evidence, not an experimental result",
            "the wrapper does not launch SUMO, train a policy, or claim Randy data provenance",
        ],
    )


def output_fingerprint(outputs: list[VecFileEvidence]) -> str:
    """Return the deterministic identity of the sorted published output inventory."""

    return _output_fingerprint(outputs)


def _output_fingerprint(outputs: list[VecFileEvidence]) -> str:
    payload = [
        {
            "path": item.path,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
            "media_type": item.media_type,
        }
        for item in sorted(outputs, key=lambda value: value.path)
    ]
    return _sha256(_canonical_json(payload).encode("utf-8"))


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
