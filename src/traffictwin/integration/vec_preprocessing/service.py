"""Read-only preflight and isolated execution for the pinned VEC FCD pipeline."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy.typing as npt

from traffictwin.integration.vec_preprocessing.models import (
    PINNED_SOURCE_FILES,
    PINNED_VEC_ENV_COMMIT,
    VecFcdMetadata,
    VecFcdPreflightReport,
    VecFcdPreprocessReceipt,
    VecFcdPreprocessRequest,
    VecFileEvidence,
    VecFindingSeverity,
    VecNetworkMetadata,
    VecPreflightFinding,
    VecPreflightStatus,
    VecPreprocessCommand,
    VecSourceScriptEvidence,
    output_fingerprint,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_UNSAFE_XML_RE = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_LOG_LIMIT_BYTES = 256_000


class VecFcdPreprocessingError(RuntimeError):
    """Raised when VEC-06 refuses or cannot complete preprocessing."""

    def __init__(self, message: str, *, preflight: VecFcdPreflightReport | None = None) -> None:
        super().__init__(message)
        self.preflight = preflight


@dataclass(frozen=True)
class _SourceState:
    head: str
    origin_main: str
    clean: bool
    scripts: tuple[VecSourceScriptEvidence, ...]
    blobs: dict[str, bytes]


@dataclass(frozen=True)
class _ParsedInputs:
    network: VecNetworkMetadata
    fcd: VecFcdMetadata
    evidence: tuple[VecFileEvidence, ...]


@dataclass(frozen=True)
class _InputPaths:
    root: Path
    fcd: Path
    network: Path


class _InputValidationError(ValueError):
    def __init__(self, code: str, message: str, artifact: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.artifact = artifact


def preflight_vec_fcd(
    input_root: str | Path,
    vec_repo: str | Path,
    request: VecFcdPreprocessRequest,
) -> VecFcdPreflightReport:
    """Inspect inputs, dependencies, and pinned source without writing any files."""

    source = _inspect_source_repository(Path(vec_repo))
    findings: list[VecPreflightFinding] = []
    if not source.clean:
        findings.append(
            _finding(
                "VEC_SOURCE_DIRTY",
                VecFindingSeverity.ERROR,
                "the external vec_env worktree must be clean",
                "vec_env",
            )
        )
    if source.origin_main != PINNED_VEC_ENV_COMMIT:
        findings.append(
            _finding(
                "VEC_SOURCE_REF_MISMATCH",
                VecFindingSeverity.ERROR,
                "vec_env origin/main does not match the audited VEC-06 commit",
                "vec_env",
            )
        )

    dependencies, dependency_error = _inspect_dependencies()
    if dependency_error is not None:
        findings.append(
            _finding(
                "VEC_PREPROCESSING_DEPENDENCY_UNAVAILABLE",
                VecFindingSeverity.ERROR,
                dependency_error,
            )
        )

    parsed: _ParsedInputs | None = None
    try:
        paths = _resolve_input_paths(Path(input_root), request)
        parsed = _parse_inputs(paths, request)
    except _InputValidationError as exc:
        findings.append(_finding(exc.code, VecFindingSeverity.ERROR, str(exc), exc.artifact))

    if not findings:
        findings.extend(
            [
                _finding(
                    "VEC_FCD_ONE_SECOND_CONFIRMED",
                    VecFindingSeverity.INFO,
                    "all FCD timesteps are finite, strictly ordered, and exactly one second apart",
                    request.fcd_file,
                ),
                _finding(
                    "VEC_NETWORK_COORDINATES_CONFIRMED",
                    VecFindingSeverity.INFO,
                    "all admitted FCD coordinates are inside the declared network boundary",
                    request.network_file,
                ),
                _finding(
                    "VEC_PINNED_PIPELINE_CONFIRMED",
                    VecFindingSeverity.INFO,
                    "both preprocessing script hashes match the VEC-01 source audit",
                    "vec_env",
                ),
            ]
        )

    dependency_only = findings and all(
        item.code == "VEC_PREPROCESSING_DEPENDENCY_UNAVAILABLE"
        or item.severity is not VecFindingSeverity.ERROR
        for item in findings
    )
    status = (
        VecPreflightStatus.ACCEPTED
        if not any(item.severity is VecFindingSeverity.ERROR for item in findings)
        else VecPreflightStatus.UNAVAILABLE
        if dependency_only
        else VecPreflightStatus.REJECTED
    )
    return VecFcdPreflightReport(
        status=status,
        request=request,
        request_fingerprint=request.fingerprint(),
        source_worktree_head=source.head,
        source_worktree_clean=source.clean,
        source_origin_main=source.origin_main,
        source_scripts=list(source.scripts),
        inputs=list(parsed.evidence) if parsed is not None else [],
        dependencies=dependencies,
        network=parsed.network if parsed is not None else None,
        fcd=parsed.fcd if parsed is not None else None,
        findings=findings,
    )


def preprocess_vec_fcd(
    input_root: str | Path,
    vec_repo: str | Path,
    output_dir: str | Path,
    request: VecFcdPreprocessRequest,
) -> VecFcdPreprocessReceipt:
    """Run the exact pinned scripts and atomically publish verified immutable outputs."""

    input_paths = _resolve_input_paths(Path(input_root), request)
    source_repo = Path(vec_repo).resolve()
    preflight = preflight_vec_fcd(input_paths.root, source_repo, request)
    if preflight.status is not VecPreflightStatus.ACCEPTED:
        raise VecFcdPreprocessingError(
            f"VEC-06 preflight is {preflight.status.value}",
            preflight=preflight,
        )
    destination = _validate_destination(Path(output_dir), input_paths.root, source_repo)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-vec-fcd-", dir=destination.parent)
    )
    payload = temporary_root / "payload"
    runtime = temporary_root / "runtime"
    staged_source = runtime / "source" / "eval"
    logs = payload / "logs"
    payload.mkdir()
    staged_source.mkdir(parents=True)
    logs.mkdir()

    try:
        source_before = _inspect_source_repository(source_repo)
        if (
            source_before.head != preflight.source_worktree_head
            or source_before.origin_main != preflight.source_origin_main
            or not source_before.clean
        ):
            raise VecFcdPreprocessingError("vec_env changed after preflight")
        _stage_scripts(staged_source, source_before)

        intermediate_trace = runtime / "builder-trace.npz"
        occupancy_path = payload / "occupancy.csv"
        final_trace = payload / "trace.npz"
        builder_argv = [
            sys.executable,
            str(staged_source / "build_trace.py"),
            "--fcd",
            str(input_paths.fcd),
            "--net",
            str(input_paths.network),
            "--out",
            str(intermediate_trace),
            "--seed",
            str(request.sumo_seed),
            "--occupancy-out",
            str(occupancy_path),
        ]
        builder = _run_stage(builder_argv, runtime, request.timeout_seconds)
        _write_log(
            logs / "build_trace.stdout.txt",
            builder.stdout,
            input_paths.root,
            source_repo,
            temporary_root,
        )
        _write_log(
            logs / "build_trace.stderr.txt",
            builder.stderr,
            input_paths.root,
            source_repo,
            temporary_root,
        )

        placement = request.placement
        placement_argv = [
            sys.executable,
            str(staged_source / "place_rsus_cover.py"),
            "--in",
            str(intermediate_trace),
            "--out",
            str(final_trace),
            "--radius",
            _format_float(placement.radius_m),
            "--cell",
            _format_float(placement.cell_m),
            "--max-rsus",
            str(placement.max_rsus),
        ]
        placed = _run_stage(placement_argv, runtime, request.timeout_seconds)
        _write_log(
            logs / "place_rsus.stdout.txt",
            placed.stdout,
            input_paths.root,
            source_repo,
            temporary_root,
        )
        _write_log(
            logs / "place_rsus.stderr.txt",
            placed.stderr,
            input_paths.root,
            source_repo,
            temporary_root,
        )

        _validate_generated_outputs(
            intermediate_trace,
            final_trace,
            occupancy_path,
            preflight,
        )
        _write_rsu_placement(payload / "rsu_placement.csv", final_trace, request)

        inputs_after = _input_evidence(input_paths, request)
        source_after = _inspect_source_repository(source_repo)
        _assert_immutable(preflight, inputs_after, source_after)

        commands = [
            VecPreprocessCommand(
                stage="build_trace",
                argv=[
                    "{python}",
                    "source/eval/build_trace.py",
                    "--fcd",
                    f"inputs/{request.fcd_file}",
                    "--net",
                    f"inputs/{request.network_file}",
                    "--out",
                    "runtime/builder-trace.npz",
                    "--seed",
                    str(request.sumo_seed),
                    "--occupancy-out",
                    "outputs/occupancy.csv",
                ],
                stdout_file="logs/build_trace.stdout.txt",
                stderr_file="logs/build_trace.stderr.txt",
            ),
            VecPreprocessCommand(
                stage="place_rsus",
                argv=[
                    "{python}",
                    "source/eval/place_rsus_cover.py",
                    "--in",
                    "runtime/builder-trace.npz",
                    "--out",
                    "outputs/trace.npz",
                    "--radius",
                    _format_float(placement.radius_m),
                    "--cell",
                    _format_float(placement.cell_m),
                    "--max-rsus",
                    str(placement.max_rsus),
                ],
                stdout_file="logs/place_rsus.stdout.txt",
                stderr_file="logs/place_rsus.stderr.txt",
            ),
        ]
        outputs = _output_inventory(payload)
        receipt = VecFcdPreprocessReceipt(
            request=request,
            request_fingerprint=request.fingerprint(),
            preflight_fingerprint=preflight.fingerprint(),
            source_worktree_head_before=source_before.head,
            source_worktree_head_after=source_after.head,
            source_worktree_clean_before=source_before.clean,
            source_worktree_clean_after=source_after.clean,
            source_scripts=list(source_before.scripts),
            inputs_before=preflight.inputs,
            inputs_after=inputs_after,
            dependencies=preflight.dependencies,
            commands=commands,
            outputs=outputs,
            deterministic_output_fingerprint=output_fingerprint(outputs),
            interpretation_limits=[
                "The input pair is caller-declared and coordinate-envelope consistent; the FCD "
                "format does not cryptographically name its network file.",
                "RSUs are deterministic grid-cell centres selected for full observed-point "
                "coverage, not measured infrastructure locations.",
                "The pinned placement script uses allow_pickle=True only on the freshly generated "
                "and schema-verified intermediate trace; arbitrary NPZ input is never accepted.",
                "This preprocessing receipt establishes artifact identity and structural validity, "
                "not traffic realism or scientific validity.",
            ],
        )
        receipt_path = payload / "preprocessing_receipt.json"
        receipt_path.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
        _make_payload_read_only(payload)
        payload.replace(destination)
        return receipt
    except subprocess.TimeoutExpired as exc:
        raise VecFcdPreprocessingError(
            f"pinned preprocessing exceeded {request.timeout_seconds} seconds"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = _bounded_text(exc.stderr or "")
        raise VecFcdPreprocessingError(
            f"pinned preprocessing stage failed with exit {exc.returncode}: {stderr}"
        ) from exc
    except VecFcdPreprocessingError:
        raise
    except (OSError, ValueError, csv.Error) as exc:
        raise VecFcdPreprocessingError(f"VEC-06 preprocessing failed: {exc}") from exc
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _inspect_source_repository(repo: Path) -> _SourceState:
    source = repo.resolve()
    if repo.is_symlink() or not source.is_dir():
        raise VecFcdPreprocessingError("vec_env must be a direct readable directory")
    git = shutil.which("git")
    if git is None:
        raise VecFcdPreprocessingError("git is required to read the pinned source snapshot")
    head = _git_text(git, source, "rev-parse", "HEAD").strip()
    origin_main = _git_text(git, source, "rev-parse", "refs/remotes/origin/main").strip()
    if not _GIT_COMMIT_RE.fullmatch(head) or not _GIT_COMMIT_RE.fullmatch(origin_main):
        raise VecFcdPreprocessingError("vec_env returned an invalid Git commit identity")
    _git_text(git, source, "cat-file", "-e", f"{PINNED_VEC_ENV_COMMIT}^{{commit}}")
    clean = not _git_text(
        git,
        source,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    blobs: dict[str, bytes] = {}
    evidence: list[VecSourceScriptEvidence] = []
    for relative, expected_hash in sorted(PINNED_SOURCE_FILES.items()):
        blob = _git_bytes(git, source, "show", f"{PINNED_VEC_ENV_COMMIT}:{relative}")
        actual_hash = _sha256_bytes(blob)
        if actual_hash != expected_hash:
            raise VecFcdPreprocessingError(
                f"pinned source hash mismatch for {relative}: {actual_hash}"
            )
        blobs[relative] = blob
        evidence.append(
            VecSourceScriptEvidence(
                path=relative,
                sha256=actual_hash,
                size_bytes=len(blob),
            )
        )
    return _SourceState(
        head=head,
        origin_main=origin_main,
        clean=clean,
        scripts=tuple(evidence),
        blobs=blobs,
    )


def _git_text(git: str, repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(  # noqa: S603 - resolved executable and fixed argv, never a shell
            [git, "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecFcdPreprocessingError(f"could not inspect vec_env Git state: {exc}") from exc
    return result.stdout


def _git_bytes(git: str, repo: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(  # noqa: S603 - resolved executable and fixed argv, never a shell
            [git, "-C", str(repo), *args],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecFcdPreprocessingError(f"could not read pinned vec_env source: {exc}") from exc
    return result.stdout


def _inspect_dependencies() -> tuple[dict[str, str], str | None]:
    code = (
        "import json, numpy, pyproj, sumolib; "
        "print(json.dumps({'numpy': numpy.__version__, 'pyproj': pyproj.__version__, "
        "'sumolib': getattr(sumolib, '__version__', 'unknown')}))"
    )
    try:
        result = subprocess.run(  # noqa: S603 - current interpreter and fixed probe code
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            env=_controlled_environment(),
        )
        loaded = json.loads(result.stdout)
        dependencies = {key: str(value) for key, value in sorted(loaded.items())}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {}, (
            "VEC preprocessing requires optional numpy, sumolib 1.27.0, and pyproj dependencies: "
            f"{type(exc).__name__}"
        )
    return dependencies, _dependency_version_error(dependencies)


def _dependency_version_error(dependencies: dict[str, str]) -> str | None:
    if dependencies.get("sumolib") != "1.27.0":
        return "the pinned preprocessing contract requires sumolib 1.27.0"
    numpy_version = _major_minor(dependencies.get("numpy"))
    pyproj_version = _major_minor(dependencies.get("pyproj"))
    if numpy_version is None or numpy_version < (1, 26):
        return "the pinned preprocessing contract requires numpy >=1.26"
    if pyproj_version is None or not (3, 6) <= pyproj_version < (4, 0):
        return "the pinned preprocessing contract requires pyproj >=3.6,<4"
    return None


def _major_minor(value: str | None) -> tuple[int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)(?:\.|$)", value or "")
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _resolve_input_paths(root: Path, request: VecFcdPreprocessRequest) -> _InputPaths:
    if root.is_symlink():
        raise _InputValidationError(
            "VEC_INPUT_ROOT_UNSAFE",
            "the input root must not be a symbolic link",
        )
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise _InputValidationError(
            "VEC_INPUT_ROOT_INVALID",
            "the input root must be a readable directory",
        )
    fcd = _safe_input_file(resolved_root, request.fcd_file)
    network = _safe_input_file(resolved_root, request.network_file)
    return _InputPaths(root=resolved_root, fcd=fcd, network=network)


def _safe_input_file(root: Path, relative: str) -> Path:
    unresolved = root / relative
    current = root
    contains_symlink = False
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            contains_symlink = True
            break
    if contains_symlink:
        raise _InputValidationError(
            "VEC_INPUT_PATH_UNSAFE",
            "symbolic-link input files or parent directories are not accepted",
            relative,
        )
    try:
        resolved = unresolved.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _InputValidationError(
            "VEC_INPUT_FILE_MISSING",
            "declared input is missing or escapes the input root",
            relative,
        ) from exc
    if not resolved.is_file():
        raise _InputValidationError(
            "VEC_INPUT_FILE_INVALID",
            "declared input must be a regular file",
            relative,
        )
    return resolved


def _parse_inputs(paths: _InputPaths, request: VecFcdPreprocessRequest) -> _ParsedInputs:
    evidence = _input_evidence(paths, request)
    network_bytes = _bounded_read(
        paths.network,
        request.max_network_bytes,
        "VEC_NETWORK_SIZE_EXCEEDED",
        request.network_file,
    )
    fcd_bytes = _bounded_read(
        paths.fcd,
        request.max_fcd_bytes,
        "VEC_FCD_SIZE_EXCEEDED",
        request.fcd_file,
    )
    network = _parse_network(network_bytes, request.network_file)
    fcd = _parse_fcd(fcd_bytes, network, request)
    after = _input_evidence(paths, request)
    if evidence != after:
        raise _InputValidationError(
            "VEC_INPUT_CHANGED_DURING_PREFLIGHT",
            "raw input identity changed during preflight",
        )
    return _ParsedInputs(network=network, fcd=fcd, evidence=tuple(evidence))


def _input_evidence(
    paths: _InputPaths,
    request: VecFcdPreprocessRequest,
) -> list[VecFileEvidence]:
    items = [
        (request.fcd_file, paths.fcd, request.fcd_sha256, "application/xml"),
        (request.network_file, paths.network, request.network_sha256, "application/xml"),
    ]
    evidence: list[VecFileEvidence] = []
    for relative, path, expected_hash, media_type in sorted(items):
        size = path.stat().st_size
        actual_hash = _sha256_file(path)
        if actual_hash != expected_hash:
            raise _InputValidationError(
                "VEC_INPUT_HASH_MISMATCH",
                f"declared SHA-256 does not match {relative}",
                relative,
            )
        evidence.append(
            VecFileEvidence(
                path=relative,
                sha256=actual_hash,
                size_bytes=size,
                media_type=media_type,
                read_only=True,
            )
        )
    return evidence


def _bounded_read(path: Path, limit: int, code: str, artifact: str) -> bytes:
    size = path.stat().st_size
    if size > limit:
        raise _InputValidationError(code, f"input size {size} exceeds limit {limit}", artifact)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise _InputValidationError(code, f"input could not be read: {exc}", artifact) from exc
    if _UNSAFE_XML_RE.search(data):
        raise _InputValidationError(
            "VEC_XML_UNSAFE_DECLARATION",
            "DOCTYPE and ENTITY declarations are not accepted",
            artifact,
        )
    return data


def _parse_network(data: bytes, artifact: str) -> VecNetworkMetadata:
    try:
        root = ET.fromstring(data)  # noqa: S314 - bounded input rejects DTD/entity declarations
    except ET.ParseError as exc:
        raise _InputValidationError(
            "VEC_NETWORK_XML_INVALID",
            f"network XML could not be parsed: {exc}",
            artifact,
        ) from exc
    if root.tag != "net":
        raise _InputValidationError(
            "VEC_NETWORK_ROOT_INVALID",
            "network XML root must be 'net'",
            artifact,
        )
    location = root.find("location")
    if location is None:
        raise _InputValidationError(
            "VEC_NETWORK_LOCATION_MISSING",
            "network XML must declare location metadata",
            artifact,
        )
    net_offset = _parse_tuple(location.get("netOffset"), 2, "netOffset", artifact)
    converted = _parse_tuple(location.get("convBoundary"), 4, "convBoundary", artifact)
    original = _parse_tuple(location.get("origBoundary"), 4, "origBoundary", artifact)
    if converted[0] >= converted[2] or converted[1] >= converted[3]:
        raise _InputValidationError(
            "VEC_NETWORK_BOUNDARY_INVALID",
            "converted network boundary must have positive width and height",
            artifact,
        )
    projection = location.get("projParameter", "").strip()
    if not projection or projection == "!":
        raise _InputValidationError(
            "VEC_NETWORK_PROJECTION_UNAVAILABLE",
            "the pinned builder's sensor conversion requires network geo-projection metadata",
            artifact,
        )
    version = root.get("version", "").strip()
    if not version:
        raise _InputValidationError(
            "VEC_NETWORK_VERSION_MISSING",
            "network XML must declare a version",
            artifact,
        )
    return VecNetworkMetadata(
        net_version=version,
        net_offset_xy=(net_offset[0], net_offset[1]),
        converted_boundary_xy=(converted[0], converted[1], converted[2], converted[3]),
        original_boundary=(original[0], original[1], original[2], original[3]),
        projection_parameter=projection,
    )


def _parse_tuple(
    value: str | None,
    length: int,
    label: str,
    artifact: str,
) -> tuple[float, ...]:
    try:
        parts = tuple(float(item) for item in (value or "").split(","))
    except ValueError as exc:
        raise _InputValidationError(
            "VEC_NETWORK_LOCATION_INVALID",
            f"network {label} must contain {length} finite numbers",
            artifact,
        ) from exc
    if len(parts) != length or not all(math.isfinite(item) for item in parts):
        raise _InputValidationError(
            "VEC_NETWORK_LOCATION_INVALID",
            f"network {label} must contain {length} finite numbers",
            artifact,
        )
    return parts


def _parse_fcd(
    data: bytes,
    network: VecNetworkMetadata,
    request: VecFcdPreprocessRequest,
) -> VecFcdMetadata:
    times: list[float] = []
    unique_ids: set[str] = set()
    placement_cells: set[tuple[int, int]] = set()
    observation_count = 0
    peak = 0
    xmin = math.inf
    ymin = math.inf
    xmax = -math.inf
    ymax = -math.inf
    root_tag: str | None = None
    try:
        context = ET.iterparse(  # noqa: S314 - bounded input rejects DTD/entity declarations
            io.BytesIO(data),
            events=("start", "end"),
        )
        for event, element in context:
            if root_tag is None and event == "start":
                root_tag = element.tag
            if event != "end" or element.tag != "timestep":
                continue
            if len(times) >= request.max_timesteps:
                raise _InputValidationError(
                    "VEC_FCD_TIMESTEP_LIMIT_EXCEEDED",
                    f"FCD exceeds {request.max_timesteps} timesteps",
                    request.fcd_file,
                )
            time_s = _finite_float(element.get("time"), "timestep time", request.fcd_file)
            if time_s < 0:
                raise _InputValidationError(
                    "VEC_FCD_TIME_INVALID",
                    "FCD timestep time must be non-negative",
                    request.fcd_file,
                )
            if times and not math.isclose(time_s - times[-1], 1.0, abs_tol=1e-9):
                raise _InputValidationError(
                    "VEC_FCD_RESOLUTION_INVALID",
                    "FCD timesteps must be strictly ordered exactly one second apart",
                    request.fcd_file,
                )
            timestep_ids: set[str] = set()
            vehicles = element.findall("vehicle")
            if len(vehicles) > request.max_vehicles_per_timestep:
                raise _InputValidationError(
                    "VEC_FCD_CONCURRENCY_LIMIT_EXCEEDED",
                    f"one timestep exceeds {request.max_vehicles_per_timestep} vehicles",
                    request.fcd_file,
                )
            for vehicle in vehicles:
                vehicle_id = (vehicle.get("id") or "").strip()
                if not vehicle_id or len(vehicle_id) > 256:
                    raise _InputValidationError(
                        "VEC_FCD_VEHICLE_ID_INVALID",
                        "vehicle IDs must contain 1-256 non-whitespace characters",
                        request.fcd_file,
                    )
                if vehicle_id in timestep_ids:
                    raise _InputValidationError(
                        "VEC_FCD_DUPLICATE_VEHICLE",
                        f"duplicate vehicle ID in one timestep: {vehicle_id}",
                        request.fcd_file,
                    )
                timestep_ids.add(vehicle_id)
                unique_ids.add(vehicle_id)
                x = _finite_float(vehicle.get("x"), "vehicle x", request.fcd_file)
                y = _finite_float(vehicle.get("y"), "vehicle y", request.fcd_file)
                speed = _finite_float(vehicle.get("speed"), "vehicle speed", request.fcd_file)
                if speed < 0:
                    raise _InputValidationError(
                        "VEC_FCD_SPEED_INVALID",
                        "vehicle speed must be non-negative",
                        request.fcd_file,
                    )
                xmin, ymin = min(xmin, x), min(ymin, y)
                xmax, ymax = max(xmax, x), max(ymax, y)
                placement_cells.add(
                    (
                        math.floor(x / request.placement.cell_m),
                        math.floor(y / request.placement.cell_m),
                    )
                )
                observation_count += 1
                if observation_count > request.max_vehicle_observations:
                    raise _InputValidationError(
                        "VEC_FCD_OBSERVATION_LIMIT_EXCEEDED",
                        f"FCD exceeds {request.max_vehicle_observations} vehicle observations",
                        request.fcd_file,
                    )
                if len(placement_cells) > request.placement.max_occupied_cells:
                    raise _InputValidationError(
                        "VEC_FCD_PLACEMENT_CELL_LIMIT_EXCEEDED",
                        "occupied placement cells exceed the safe quadratic set-cover limit",
                        request.fcd_file,
                    )
            peak = max(peak, len(timestep_ids))
            times.append(time_s)
            element.clear()
    except ET.ParseError as exc:
        raise _InputValidationError(
            "VEC_FCD_XML_INVALID",
            f"FCD XML could not be parsed: {exc}",
            request.fcd_file,
        ) from exc
    if root_tag != "fcd-export":
        raise _InputValidationError(
            "VEC_FCD_ROOT_INVALID",
            "FCD XML root must be 'fcd-export'",
            request.fcd_file,
        )
    if not times or observation_count == 0 or peak == 0:
        raise _InputValidationError(
            "VEC_FCD_EMPTY",
            "FCD must contain at least one timestep and vehicle observation",
            request.fcd_file,
        )
    dense_cells = len(times) * peak
    if dense_cells > request.max_dense_trace_cells:
        raise _InputValidationError(
            "VEC_FCD_DENSE_TRACE_LIMIT_EXCEEDED",
            f"dense trace would contain {dense_cells} cells, over the configured limit",
            request.fcd_file,
        )
    boundary = network.converted_boundary_xy
    tolerance = request.coordinate_tolerance_m
    coordinates_within = (
        xmin >= boundary[0] - tolerance
        and ymin >= boundary[1] - tolerance
        and xmax <= boundary[2] + tolerance
        and ymax <= boundary[3] + tolerance
    )
    if not coordinates_within:
        raise _InputValidationError(
            "VEC_FCD_NETWORK_COORDINATE_MISMATCH",
            "FCD coordinates fall outside the declared network boundary",
            request.fcd_file,
        )
    return VecFcdMetadata(
        timestep_count=len(times),
        first_time_s=times[0],
        last_time_s=times[-1],
        vehicle_observation_count=observation_count,
        unique_vehicle_count=len(unique_ids),
        peak_concurrent_vehicles=peak,
        dense_trace_cells=dense_cells,
        occupied_placement_cells=len(placement_cells),
        coordinate_bounds_xy=(xmin, ymin, xmax, ymax),
        coordinates_within_network_boundary=coordinates_within,
    )


def _finite_float(value: str | None, label: str, artifact: str) -> float:
    try:
        parsed = float(value or "")
    except ValueError as exc:
        raise _InputValidationError(
            "VEC_FCD_VALUE_INVALID",
            f"{label} must be finite",
            artifact,
        ) from exc
    if not math.isfinite(parsed):
        raise _InputValidationError(
            "VEC_FCD_VALUE_INVALID",
            f"{label} must be finite",
            artifact,
        )
    return parsed


def _validate_destination(destination: Path, input_root: Path, source_repo: Path) -> Path:
    unresolved = destination.expanduser()
    if unresolved.exists() or unresolved.is_symlink():
        raise VecFcdPreprocessingError("VEC-06 output directory must not already exist")
    if _has_symlink_component(unresolved.parent):
        raise VecFcdPreprocessingError("VEC-06 output parent must not contain symbolic links")
    resolved = unresolved.resolve(strict=False)
    protected = (Path.cwd().resolve(), Path.home().resolve(), Path("/").resolve())
    if any(resolved == item or resolved in item.parents for item in protected):
        raise VecFcdPreprocessingError("VEC-06 output directory is too broad")
    for protected_root, label in ((input_root, "input root"), (source_repo, "vec_env")):
        if (
            resolved == protected_root
            or resolved in protected_root.parents
            or protected_root in resolved.parents
        ):
            raise VecFcdPreprocessingError(f"VEC-06 output must not overlap the {label}")
    return resolved


def _has_symlink_component(path: Path) -> bool:
    current = path
    while current != current.parent:
        if current.exists() and current.is_symlink():
            return True
        current = current.parent
    return current.is_symlink()


def _stage_scripts(destination: Path, source: _SourceState) -> None:
    for relative, blob in sorted(source.blobs.items()):
        target = destination / Path(relative).name
        target.write_bytes(blob)
        target.chmod(0o444)


def _run_stage(argv: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - exact pinned script and allowlisted argv, never a shell
        argv,
        cwd=cwd,
        env=_controlled_environment(),
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _controlled_environment() -> dict[str, str]:
    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.defpath,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }


def _write_log(
    path: Path,
    value: str,
    input_root: Path,
    source_repo: Path,
    temporary_root: Path,
) -> None:
    redacted = value
    for raw, replacement in (
        (str(temporary_root), "{WORKSPACE}"),
        (str(input_root), "{INPUT_ROOT}"),
        (str(source_repo), "{VEC_REPO}"),
    ):
        redacted = redacted.replace(raw, replacement)
    path.write_text(_bounded_text(redacted), encoding="utf-8")


def _bounded_text(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= _LOG_LIMIT_BYTES:
        return encoded.decode("utf-8")
    marker = b"\n[TrafficTwin log truncated]\n"
    return (encoded[: _LOG_LIMIT_BYTES - len(marker)] + marker).decode("utf-8", errors="replace")


def _validate_generated_outputs(
    intermediate_path: Path,
    final_path: Path,
    occupancy_path: Path,
    preflight: VecFcdPreflightReport,
) -> None:
    np = _numpy()
    if preflight.fcd is None:
        raise VecFcdPreprocessingError("accepted preflight is missing FCD metadata")
    expected_keys = {
        "pos_x",
        "pos_y",
        "speed",
        "mask",
        "rsu_xy",
        "times",
        "dt",
        "maxN",
        "T",
        "window",
        "sumo_seed",
    }
    try:
        with (
            np.load(intermediate_path, allow_pickle=False) as intermediate,
            np.load(final_path, allow_pickle=False) as final,
        ):
            if set(intermediate.files) != expected_keys or set(final.files) != expected_keys:
                raise VecFcdPreprocessingError("generated trace keys do not match the contract")
            t_count = preflight.fcd.timestep_count
            max_n = preflight.fcd.peak_concurrent_vehicles
            for name in ("pos_x", "pos_y", "speed", "mask"):
                if tuple(final[name].shape) != (t_count, max_n):
                    raise VecFcdPreprocessingError(f"generated {name} shape is invalid")
            expected_dtypes = {
                "pos_x": "float32",
                "pos_y": "float32",
                "speed": "float32",
                "mask": "bool",
                "times": "float32",
                "rsu_xy": "float32",
            }
            for name, dtype in expected_dtypes.items():
                if str(final[name].dtype) != dtype:
                    raise VecFcdPreprocessingError(f"generated {name} dtype is invalid")
            if tuple(final["times"].shape) != (t_count,):
                raise VecFcdPreprocessingError("generated times shape is invalid")
            if tuple(final["rsu_xy"].shape)[1:] != (2,) or final["rsu_xy"].shape[0] < 1:
                raise VecFcdPreprocessingError("generated RSU placement shape is invalid")
            if final["rsu_xy"].shape[0] > preflight.request.placement.max_rsus:
                raise VecFcdPreprocessingError("generated RSU count exceeds the request")
            if int(final["T"]) != t_count or int(final["maxN"]) != max_n:
                raise VecFcdPreprocessingError("generated scalar dimensions are invalid")
            if float(final["dt"]) != 1.0:
                raise VecFcdPreprocessingError("generated trace dt is not one second")
            if int(final["sumo_seed"]) != preflight.request.sumo_seed:
                raise VecFcdPreprocessingError("generated trace seed does not match request")
            if str(final["window"]) != Path(preflight.request.fcd_file).name:
                raise VecFcdPreprocessingError("generated trace window does not match FCD")
            if not np.all(np.diff(final["times"]) == 1.0):
                raise VecFcdPreprocessingError("generated trace times are not one-second")
            if int(final["mask"].sum()) != preflight.fcd.vehicle_observation_count:
                raise VecFcdPreprocessingError("generated active count does not match FCD")
            if not all(
                np.array_equal(intermediate[name], final[name])
                for name in expected_keys - {"rsu_xy"}
            ):
                raise VecFcdPreprocessingError("RSU placement changed non-placement trace arrays")
            _validate_occupancy(occupancy_path, final["mask"])
            _validate_full_coverage(
                final["pos_x"],
                final["pos_y"],
                final["mask"],
                final["rsu_xy"],
                preflight.request.placement.radius_m,
            )
    except (OSError, ValueError) as exc:
        raise VecFcdPreprocessingError(f"generated trace could not be validated: {exc}") from exc


def _validate_occupancy(path: Path, mask: npt.NDArray[Any]) -> None:
    np = _numpy()
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != ["sumo_vehicle_id", "slot", "t_enter", "t_exit"]:
                raise VecFcdPreprocessingError("generated occupancy header is invalid")
            reconstructed = np.zeros_like(mask, dtype=bool)
            seen_spans: dict[int, list[tuple[int, int]]] = {}
            visit_seconds = 0
            for row in reader:
                slot = int(row["slot"])
                enter = int(row["t_enter"])
                exit_ = int(row["t_exit"])
                if not row["sumo_vehicle_id"] or not 0 <= slot < mask.shape[1]:
                    raise VecFcdPreprocessingError("generated occupancy identity/slot is invalid")
                if not 0 <= enter <= exit_ < mask.shape[0]:
                    raise VecFcdPreprocessingError("generated occupancy interval is invalid")
                spans = seen_spans.setdefault(slot, [])
                if any(
                    enter <= prior_exit and prior_enter <= exit_
                    for prior_enter, prior_exit in spans
                ):
                    raise VecFcdPreprocessingError("generated occupancy intervals overlap")
                spans.append((enter, exit_))
                reconstructed[enter : exit_ + 1, slot] = True
                visit_seconds += exit_ - enter + 1
    except (OSError, KeyError, TypeError, ValueError, csv.Error) as exc:
        raise VecFcdPreprocessingError(f"generated occupancy could not be parsed: {exc}") from exc
    if visit_seconds != int(mask.sum()) or not np.array_equal(reconstructed, mask):
        raise VecFcdPreprocessingError("generated occupancy does not exactly reproduce trace mask")


def _validate_full_coverage(
    pos_x: npt.NDArray[Any],
    pos_y: npt.NDArray[Any],
    mask: npt.NDArray[Any],
    rsu_xy: npt.NDArray[Any],
    radius_m: float,
) -> None:
    np = _numpy()
    points = np.stack([pos_x[mask], pos_y[mask]], axis=-1)
    for start in range(0, len(points), 100_000):
        chunk = points[start : start + 100_000]
        squared = ((chunk[:, None, :] - rsu_xy[None, :, :]) ** 2).sum(axis=-1)
        if not np.all(squared.min(axis=1) <= radius_m**2):
            raise VecFcdPreprocessingError("generated RSU placement does not provide full coverage")


def _write_rsu_placement(
    path: Path,
    trace_path: Path,
    request: VecFcdPreprocessRequest,
) -> None:
    np = _numpy()
    with np.load(trace_path, allow_pickle=False) as trace:
        coordinates = trace["rsu_xy"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["rsu_index", "x_m", "y_m", "radius_m", "strategy"])
            for index, (x, y) in enumerate(coordinates):
                writer.writerow(
                    [
                        index,
                        format(float(x), ".9g"),
                        format(float(y), ".9g"),
                        _format_float(request.placement.radius_m),
                        request.placement.strategy,
                    ]
                )


def _assert_immutable(
    preflight: VecFcdPreflightReport,
    inputs_after: list[VecFileEvidence],
    source_after: _SourceState,
) -> None:
    if not source_after.clean or source_after.head != preflight.source_worktree_head:
        raise VecFcdPreprocessingError("vec_env changed during preprocessing")
    if source_after.origin_main != preflight.source_origin_main:
        raise VecFcdPreprocessingError("vec_env origin/main changed during preprocessing")
    if list(source_after.scripts) != preflight.source_scripts:
        raise VecFcdPreprocessingError("pinned source script identity changed")
    before = [(item.path, item.sha256, item.size_bytes) for item in preflight.inputs]
    after = [(item.path, item.sha256, item.size_bytes) for item in inputs_after]
    if before != after:
        raise VecFcdPreprocessingError("raw input identity changed during preprocessing")


def _output_inventory(payload: Path) -> list[VecFileEvidence]:
    media_types = {
        ".npz": "application/x-npz",
        ".csv": "text/csv",
        ".txt": "text/plain",
    }
    outputs: list[VecFileEvidence] = []
    for path in sorted(item for item in payload.rglob("*") if item.is_file()):
        relative = path.relative_to(payload).as_posix()
        outputs.append(
            VecFileEvidence(
                path=relative,
                sha256=_sha256_file(path),
                size_bytes=path.stat().st_size,
                media_type=media_types[path.suffix],
                read_only=True,
            )
        )
    return outputs


def _make_payload_read_only(payload: Path) -> None:
    for path in payload.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _finding(
    code: str,
    severity: VecFindingSeverity,
    message: str,
    artifact: str | None = None,
) -> VecPreflightFinding:
    return VecPreflightFinding(
        code=code,
        severity=severity,
        message=message,
        artifact=artifact,
    )


def _format_float(value: float) -> str:
    return format(value, ".12g")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    digest = hashlib.sha256(value).hexdigest()
    if not _SHA256_RE.fullmatch(digest):  # pragma: no cover - hashlib invariant
        raise AssertionError("invalid SHA-256 digest")
    return digest


def _numpy() -> Any:  # noqa: ANN401 - NumPy is an optional integration dependency
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise VecFcdPreprocessingError(
            'VEC FCD preprocessing requires: pip install -e ".[vec]"'
        ) from exc
    return np
