"""Safe readers for the repository-contained TOS Data package contract."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from traffictwin.integration.tos.models import (
    NpzArrayHeader,
    TosEvaluationRun,
    TosSummary,
)

EVALUATION_MASTER = Path("evals/eval_results_master.csv")
EXPECTED_EVALUATION_COLUMNS = (
    "campaign",
    "cell",
    "eval_fleet",
    "fleet_seed",
    "actor",
    "obs_variant",
    "completion",
    "t1_completion",
    "t2_completion",
    "t3_completion",
    "avg_energy_j_per_task",
    "avg_latency_ms_per_task",
    "p_local",
    "p_v2i",
    "p_v2v",
    "fleet_ev_share",
    "T",
    "maxN",
    "trace",
    "engine_version",
)
_RUN_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MASTER_TO_INSTRUMENTED_CAMPAIGN = {
    "baseline": "baseline",
    "capscalar_ippo": "caps_ippo",
    "capscalar_mappo": "caps_mappo",
    "fcdtrain_manwe_mappo": "fcd_s100",
    "fcdtrain_manwe_mappo_s102": "fcd_s102",
    "gridlocktrain_ippo": "glk_ippo",
    "gridlocktrain_mappo": "glk_mappo",
    "gridlocktrain_ft_ippo": "glkft_ippo",
    "gridlocktrain_ft_mappo": "glkft_mappo",
    "ukfleettrain_ippo": "ukft_ippo",
    "ukfleettrain_mappo": "ukft_mappo",
}


class TosPackageError(RuntimeError):
    """Raised when a TOS package cannot be read safely or consistently."""


class HashWriter(Protocol):
    """Minimal hash interface used by streaming file digests."""

    def update(self, data: bytes) -> None:
        """Update the digest with bytes."""


def read_evaluation_runs(root: str | Path) -> list[TosEvaluationRun]:
    """Read and validate documented evaluation summary rows."""

    path = safe_package_path(root, EVALUATION_MASTER)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            missing = sorted(set(EXPECTED_EVALUATION_COLUMNS) - set(headers))
            if missing:
                raise TosPackageError("evaluation master is missing columns: " + ", ".join(missing))
            rows: list[TosEvaluationRun] = []
            for source_row, raw in enumerate(reader, start=2):
                selected = {key: raw.get(key) for key in EXPECTED_EVALUATION_COLUMNS}
                selected["source_row"] = source_row
                try:
                    rows.append(TosEvaluationRun.model_validate(selected))
                except ValidationError as exc:
                    raise TosPackageError(f"invalid evaluation row {source_row}: {exc}") from exc
    except OSError as exc:
        raise TosPackageError(f"cannot read evaluation master: {exc}") from exc
    return rows


def evaluation_headers(root: str | Path) -> list[str]:
    """Return evaluation-master headers without parsing all rows."""

    path = safe_package_path(root, EVALUATION_MASTER)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return next(csv.reader(handle), [])
    except OSError as exc:
        raise TosPackageError(f"cannot read evaluation master: {exc}") from exc


def read_summary(path: str | Path) -> TosSummary:
    """Read one instrumented summary JSON file."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return TosSummary.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise TosPackageError(f"cannot read TOS summary {source.name}: {exc}") from exc


def read_summary_for_key(root: str | Path, run_key: str) -> TosSummary:
    """Read a summary selected by a validated package run key."""

    key = validate_run_key(root, run_key)
    return read_summary(safe_package_path(root, Path("instrumented/json") / f"{key}.json"))


def list_instrumented_runs(root: str | Path) -> list[str]:
    """List run keys that have both summary and per-step artifacts."""

    package = Path(root).resolve()
    summary_dir = safe_package_path(package, "instrumented/json")
    perstep_dir = safe_package_path(package, "instrumented/perstep")
    if not summary_dir.is_dir() or not perstep_dir.is_dir():
        return []
    summaries = {path.stem for path in summary_dir.glob("*.json") if path.is_file()}
    streams = {
        path.name.removesuffix("_perstep.npz")
        for path in perstep_dir.glob("*_perstep.npz")
        if path.is_file()
    }
    return sorted(summaries & streams)


def list_pertask_runs(root: str | Path) -> list[str]:
    """List run keys with full per-arrival showcase arrays."""

    directory = safe_package_path(root, "instrumented/pertask")
    if not directory.is_dir():
        return []
    return sorted(
        path.name.removesuffix("_pertask.npz")
        for path in directory.glob("*_pertask.npz")
        if path.is_file()
    )


def instrumented_key_for_run(run: TosEvaluationRun) -> str:
    """Return the documented abbreviated instrumented key for an evaluation row."""

    prefix = MASTER_TO_INSTRUMENTED_CAMPAIGN.get(run.campaign)
    if prefix is None:
        raise TosPackageError(f"no instrumented campaign mapping for {run.campaign}")
    return f"{prefix}_{run.eval_fleet}_{run.cell}_fs{run.fleet_seed}"


def validate_run_key(root: str | Path, run_key: str) -> str:
    """Reject traversal and require a key present in the package index."""

    if not _RUN_KEY_RE.fullmatch(run_key):
        raise TosPackageError("invalid instrumented run key")
    if run_key not in list_instrumented_runs(root):
        raise TosPackageError(f"instrumented run not found: {run_key}")
    return run_key


def perstep_path(root: str | Path, run_key: str) -> Path:
    """Return a safe per-step source path for a package run."""

    key = validate_run_key(root, run_key)
    return safe_package_path(root, Path("instrumented/perstep") / f"{key}_perstep.npz")


def pertask_path(root: str | Path, run_key: str) -> Path:
    """Return a safe per-task source path for a package run."""

    key = validate_run_key(root, run_key)
    if key not in list_pertask_runs(root):
        raise TosPackageError(f"per-task showcase not found: {run_key}")
    return safe_package_path(root, Path("instrumented/pertask") / f"{key}_pertask.npz")


def trace_path(root: str | Path, trace_name: str) -> Path:
    """Return a safe trace path from a summary-declared basename."""

    if Path(trace_name).name != trace_name:
        raise TosPackageError("trace reference must be a basename")
    return safe_package_path(root, Path("traces") / trace_name)


def read_npz_headers(
    path: str | Path,
    *,
    max_uncompressed_bytes: int = 2_000_000_000,
) -> list[NpzArrayHeader]:
    """Read NPY member headers without materialising array payloads."""

    source = Path(path)
    np = _numpy()
    headers: list[NpzArrayHeader] = []
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            total = sum(info.file_size for info in infos)
            if total > max_uncompressed_bytes:
                raise TosPackageError(
                    f"NPZ uncompressed size exceeds limit: {total} > {max_uncompressed_bytes}"
                )
            for info in sorted(infos, key=lambda item: item.filename):
                _validate_npz_member(info)
                if not info.filename.endswith(".npy"):
                    raise TosPackageError(f"unsupported NPZ member: {info.filename}")
                with archive.open(info, "r") as member:
                    version = np.lib.format.read_magic(member)
                    if version == (1, 0):
                        shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(member)
                    elif version == (2, 0):
                        shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(member)
                    else:
                        raise TosPackageError(
                            f"unsupported NPY header version {version} in {info.filename}"
                        )
                headers.append(
                    NpzArrayHeader(
                        name=Path(info.filename).stem,
                        shape=list(shape),
                        dtype=str(dtype),
                        fortran_order=bool(fortran_order),
                        uncompressed_bytes=info.file_size,
                    )
                )
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        if isinstance(exc, TosPackageError):
            raise
        raise TosPackageError(f"cannot inspect NPZ {source.name}: {exc}") from exc
    return headers


def package_git_commit(root: str | Path) -> str | None:
    """Return the data-package commit when the source is a Git checkout."""

    package = Path(root).resolve()
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable and argument list
            [git, "-C", str(package), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if re.fullmatch(r"[0-9a-fA-F]{40}", value) else None


def package_fingerprint(root: str | Path) -> str:
    """Fingerprint the documented summary contract without hashing large NPZ payloads."""

    package = Path(root).resolve()
    hasher = hashlib.sha256()
    for relative in (Path("README.md"), Path("DATA_DICTIONARY.md"), EVALUATION_MASTER):
        path = safe_package_path(package, relative)
        if not path.is_file():
            raise TosPackageError(f"required package file is missing: {relative.as_posix()}")
        hasher.update(relative.as_posix().encode("utf-8"))
        _update_hash(hasher, path)
    commit = package_git_commit(package)
    hasher.update((commit or "no-git-commit").encode("ascii"))
    return hasher.hexdigest()


def file_sha256(path: str | Path) -> str:
    """Return a streaming SHA-256 digest for a selected source artifact."""

    hasher = hashlib.sha256()
    _update_hash(hasher, Path(path))
    return hasher.hexdigest()


def safe_package_path(root: str | Path, relative: str | Path) -> Path:
    """Resolve a package-relative path and reject path escape."""

    package = Path(root).resolve()
    candidate = (package / relative).resolve()
    if candidate != package and package not in candidate.parents:
        raise TosPackageError("source path escapes the TOS package root")
    return candidate


def package_relative(root: str | Path, path: str | Path) -> str:
    """Return a safe package-relative source reference."""

    package = Path(root).resolve()
    source = Path(path).resolve()
    try:
        return source.relative_to(package).as_posix()
    except ValueError as exc:
        raise TosPackageError("source path is outside the TOS package") from exc


def _validate_npz_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise TosPackageError(f"unsafe NPZ member path: {name}")
    mode = info.external_attr >> 16
    if mode and stat.S_ISLNK(mode):
        raise TosPackageError(f"NPZ symlink member is not allowed: {name}")


def _update_hash(hasher: HashWriter, path: Path) -> None:
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                hasher.update(chunk)
    except OSError as exc:
        raise TosPackageError(f"cannot hash {path.name}: {exc}") from exc


def _numpy() -> Any:  # noqa: ANN401 - optional NumPy module is loaded dynamically
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise TosPackageError(
            'TOS NPZ support requires the optional dependency: pip install -e ".[tos]"'
        ) from exc
    return np
