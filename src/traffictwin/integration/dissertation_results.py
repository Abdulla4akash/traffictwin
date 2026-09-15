"""Import the exact completed joint-randomness study as compact research evidence.

The installed manifest is the trust anchor. User archives cannot supply new
hashes or authorize another study. Reading receipts authenticates historical
validation records; it does not repeat validation of the private raw arrays.
No evaluator, scientific workload, uploaded code, or archive extraction is used.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import stat
import statistics
import zipfile
import zlib
from dataclasses import dataclass, fields
from importlib.resources import files as resource_files
from pathlib import Path, PurePosixPath
from typing import Any, cast

MAX_PACKET_BYTES = 5 * 1024 * 1024
STUDY_ID = "joint_confirmation_2026-09-08"
ARMS = ("ingress_dla", "dla", "per_task_dla", "causal_round_robin")
ARM_LABELS = {
    "ingress_dla": "Ingress",
    "dla": "Common-target",
    "per_task_dla": "Per-task",
    "causal_round_robin": "Round-robin",
}
CONTRASTS = (
    ("per_task_dla", "ingress_dla"),
    ("dla", "ingress_dla"),
    ("per_task_dla", "causal_round_robin"),
)


class ResultsImportError(ValueError):
    """A supplied packet is unavailable, unsafe, or differs from frozen evidence."""


@dataclass(frozen=True)
class CellResult:
    """One arm within one joint fleet/evaluator block; counts use all offered tasks."""

    offered: int
    admitted: int
    successes: int
    terminal_failures: int
    simulation_process_s: float
    validation_s: float
    total_wall_s: float
    started_at: str
    finished_at: str
    max_service_conservation_error_ms: float
    max_vehicle_service_conservation_error_ms: float
    block: int
    fleet_seed: int
    evaluator_seed: int
    arm: str
    attainment_pct: float
    admitted_misses: int
    gate_rejected: int
    capacity_rejected: int
    local_rejected: int
    v2v_rejected: int
    v2i_unavailable: int
    v2v_unavailable: int
    evaluator_scan_wall_s: float


@dataclass(frozen=True)
class PairedContrast:
    """Equal-weight block effects with the sealed simultaneous 95% t interval."""

    contrast: str
    effects_pp: list[float]
    mean_pp: float
    sd_pp: float
    family95_low_pp: float
    family95_high_pp: float


@dataclass(frozen=True)
class DissertationResults:
    """Authenticated originals and parsed values for a thin presentation layer."""

    cells: list[CellResult]
    primary: list[PairedContrast]
    files: dict[str, bytes]
    hashes: dict[str, str]
    seal_sha256: str
    packet_sha256: str
    receipt_summary: list[dict[str, str | int | bool]]

    def export_zip(self) -> bytes:
        """Return a deterministic packet, rechecking originals before export."""
        _authenticate(self.files)
        return _make_zip(self.files)

    def validation_receipt(self) -> dict[str, object]:
        """Describe this import's checks without claiming fresh raw validation."""
        hashes = _authenticate(self.files)
        _validate_compact(self.files)
        return {
            "schema": "traffictwin_dissertation_results_import_v1",
            "study_id": STUDY_ID,
            "status": "passed",
            "source_commit": _manifest()["source_commit"],
            "seal_sha256": hashes["confirmation/SEALED_EXECUTION.json"],
            "packet_sha256": _sha(_make_zip(self.files)),
            "files_sha256": hashes,
            "cells": 32,
            "paired_blocks": 8,
            "primary_contrasts": 3,
            "evidence_standing": "Imported completed simulation research",
            "artifact_integrity": "Matches the trusted frozen study manifest",
            "compact_arithmetic": "passed",
            "validation_scope": "Authenticated historical receipts and compact arithmetic",
            "raw_arrays_checked": False,
            "task_level_validation_repeated": False,
            "research_workloads_launched": 0,
            "denominator": "All offered tasks, including rejected and unavailable tasks",
            "replication_unit": "Joint fleet/evaluator block; equal block weighting",
            "interval": "Two-sided Bonferroni simultaneous 95% Student-t; family=3, df=7",
            "limitations": (
                "Same trace, frozen actor and model; eight blocks with approximate-normality "
                "assumptions. Separate from prior studies and unexecuted E3 research."
            ),
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest() -> dict[str, Any]:
    resource = resource_files("traffictwin.resources.research").joinpath(
        "joint_confirmation_results_manifest.json"
    )
    return cast(dict[str, Any], json.loads(resource.read_bytes()))


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ResultsImportError(message)


def _authenticate(data: dict[str, bytes]) -> dict[str, str]:
    expected = cast(dict[str, str], _manifest()["files"])
    _need(set(data) == set(expected), "Packet has missing or unexpected study files")
    hashes = {name: _sha(content) for name, content in sorted(data.items())}
    for name, digest in hashes.items():
        _need(digest == expected[name], f"Frozen evidence fingerprint mismatch: {name}")
    return hashes


def _make_zip(data: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(data.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def _json(data: dict[str, bytes], name: str) -> Any:  # noqa: ANN401 — authenticated original schemas
    return json.loads(data[name])


def _validate_compact(
    data: dict[str, bytes],
) -> tuple[list[CellResult], list[PairedContrast], list[dict[str, str | int | bool]]]:
    """Check correspondence after exact-byte authentication, using only stdlib."""
    seal_sha = _sha(data["confirmation/SEALED_EXECUTION.json"])
    seal = _json(data, "confirmation/SEALED_EXECUTION.json")
    analysis = _json(data, "evidence/ANALYSIS.json")
    block_receipts = _json(data, "evidence/BLOCK_CONTROLS.json")
    rows = _json(data, "evidence/CELL_RESULTS.json")
    complete = _json(data, "evidence/COMPLETE.json")
    _need(
        analysis["seal_sha256"] == seal_sha
        and analysis["status"] == "completed_primary_confirmation"
        and analysis["equal_block_weighting"] is True
        and analysis["df"] == 7,
        "Analysis identity or statistical scope mismatch",
    )
    _need(
        complete["status"] == "complete"
        and complete["seal_sha256"] == seal_sha
        and complete["full_attempts"] == 32
        and complete["valid_blocks"] == 8,
        "Study completion receipt mismatch",
    )
    cells = [CellResult(**row) for row in rows]
    index = {(cell.block, cell.arm): cell for cell in cells}
    _need(
        set(index) == {(block, arm) for block in range(8) for arm in ARMS}
        and len(cells) == 32
        and len(block_receipts) == 8,
        "Incomplete or duplicate study matrix",
    )
    receipts: list[dict[str, str | int | bool]] = []
    rates: dict[tuple[int, str], float] = {}
    for block in seal["blocks"]:
        b = block["block"]
        control = next(item for item in block_receipts if item["block"] == b)
        _need(
            control["status"] == "passed"
            and control["seal_sha256"] == seal_sha
            and control["shared_exogenous_inputs"] == "identical"
            and control["actions_forced"] is False,
            f"Invalid block control receipt: {b}",
        )
        shared: object = None
        offered: set[int] = set()
        for arm in ARMS:
            cell = index[b, arm]
            prefix = f"evidence/cells/block_{b:02d}_{arm}"
            rec = _json(data, f"{prefix}/VALIDATED.json")
            cfg = rec["configuration"]
            _need(
                _sha(data[f"{prefix}/VALIDATED.json"]) == control["cell_receipt_sha256"][arm]
                and _sha(data[f"{prefix}/summary.json"]) == rec["output_sha256"]["summary.json"]
                and rec["seal_sha256"] == seal_sha
                and cfg["seal_sha256"] == seal_sha
                and rec["status"] == "passed",
                f"Unbound cell receipt: block {b}, {arm}",
            )
            _need(
                cfg["block"] == b
                and cfg["arm"] == arm
                and cfg["steps"] == 10800
                and cell.fleet_seed == cfg["fleet_seed"] == block["fleet_seed"]
                and cell.evaluator_seed == cfg["evaluator_seed"] == block["evaluator_seed"]
                and cfg["inputs"]["trace_sha256"] == seal["inputs"]["trace_sha256"]
                and cfg["inputs"]["actor_sha256"] == seal["inputs"]["actor_sha256"],
                f"Cell configuration mismatch: block {b}, {arm}",
            )
            for key in ("offered", "admitted", "successes", "terminal_failures"):
                _need(getattr(cell, key) == rec[key], f"Cell count mismatch: {key}")
            outcomes = rec["outcome_counts"]
            categories = [
                cell.successes,
                cell.admitted_misses,
                cell.gate_rejected,
                cell.capacity_rejected,
                cell.local_rejected,
                cell.v2v_rejected,
                cell.v2i_unavailable,
                cell.v2v_unavailable,
            ]
            _need(
                outcomes == [0, *categories]
                and cell.offered == sum(categories)
                and cell.admitted == cell.successes + cell.admitted_misses
                and cell.terminal_failures == sum(categories[2:]),
                f"Cell accounting mismatch: block {b}, {arm}",
            )
            if shared is None:
                shared = rec["shared_input_hashes"]
            _need(shared == rec["shared_input_hashes"], f"Shared inputs mismatch: block {b}")
            offered.add(cell.offered)
            rates[b, arm] = 100 * cell.successes / cell.offered
            _need(rates[b, arm] == cell.attainment_pct, "Offered-task rate mismatch")
            receipts.append(
                {
                    "block": b,
                    "arm": arm,
                    "status": "passed",
                    "offered": cell.offered,
                    "successes": cell.successes,
                    "receipt_sha256": _sha(data[f"{prefix}/VALIDATED.json"]),
                    "summary_sha256": _sha(data[f"{prefix}/summary.json"]),
                    "raw_arrays_checked": False,
                }
            )
        _need(len(offered) == 1, f"Unmatched offered denominators: block {b}")
    exported = list(csv.DictReader(io.StringIO(data["evidence/CELL_RESULTS.csv"].decode())))
    _need(
        exported == [{key: str(value) for key, value in row.items()} for row in rows],
        "Cell CSV differs from original JSON",
    )
    _need(set(exported[0]) == {field.name for field in fields(CellResult)}, "Cell schema mismatch")
    expected_effects: list[dict[str, str]] = []
    primary = [PairedContrast(**item) for item in analysis["primary"]]
    _need(
        [item.contrast for item in primary] == [f"{a} minus {b}" for a, b in CONTRASTS],
        "Predeclared contrast mismatch",
    )
    for item, (treated, comparator) in zip(primary, CONTRASTS, strict=True):
        effects = [rates[b, treated] - rates[b, comparator] for b in range(8)]
        mean, sd = statistics.mean(effects), statistics.stdev(effects)
        half = analysis["critical_value"] * sd / math.sqrt(8)
        _need(item.effects_pp == effects, "Paired effects differ from cell rates")
        for actual, expected in (
            (item.mean_pp, mean),
            (item.sd_pp, sd),
            (item.family95_low_pp, mean - half),
            (item.family95_high_pp, mean + half),
        ):
            _need(math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12), "Interval mismatch")
        expected_effects.extend(
            {
                "block": str(b),
                "fleet_seed": str(100 + b),
                "evaluator_seed": str(200 + b),
                "contrast": item.contrast,
                "effect_pp": str(effect),
            }
            for b, effect in enumerate(effects)
        )
    exported_effects = list(
        csv.DictReader(io.StringIO(data["evidence/PAIRED_EFFECTS.csv"].decode()))
    )
    _need(exported_effects == expected_effects, "Paired-effects CSV mismatch")
    return cells, primary, receipts


def _load(data: dict[str, bytes]) -> DissertationResults:
    hashes = _authenticate(data)
    cells, primary, receipts = _validate_compact(data)
    return DissertationResults(
        cells=cells,
        primary=primary,
        files=data,
        hashes=hashes,
        seal_sha256=hashes["confirmation/SEALED_EXECUTION.json"],
        packet_sha256=_sha(_make_zip(data)),
        receipt_summary=receipts,
    )


def load_results_zip(data: bytes) -> DissertationResults:
    """Import only the allowlisted original files, without extracting an archive."""
    _need(len(data) <= MAX_PACKET_BYTES, "ZIP exceeds the 5 MiB compressed size limit")
    expected = cast(dict[str, str], _manifest()["files"])
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            _need(
                len(entries) == len(expected), "ZIP has missing, duplicate, or unexpected entries"
            )
            names = [entry.filename for entry in entries]
            _need(len(set(names)) == len(names), "ZIP has duplicate entries")
            _need(set(names) == set(expected), "ZIP has missing or unexpected study files")
            total = 0
            for entry in entries:
                path = PurePosixPath(entry.filename)
                mode = entry.external_attr >> 16
                _need(
                    not path.is_absolute()
                    and ".." not in path.parts
                    and "\\" not in entry.filename
                    and not entry.is_dir()
                    and not stat.S_ISLNK(mode)
                    and (stat.S_IFMT(mode) in (0, stat.S_IFREG))
                    and entry.orig_filename == entry.filename
                    and not entry.flag_bits & 1,
                    "ZIP contains an unsafe or encrypted entry",
                )
                _need(
                    entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                    "Unsupported ZIP compression method",
                )
                total += entry.file_size
                _need(total <= MAX_PACKET_BYTES, "ZIP exceeds the 5 MiB uncompressed size limit")
            contents: dict[str, bytes] = {}
            total_read = 0
            for entry in entries:
                with archive.open(entry) as stream:
                    content = stream.read(MAX_PACKET_BYTES - total_read + 1)
                total_read += len(content)
                _need(total_read <= MAX_PACKET_BYTES, "ZIP expands beyond the 5 MiB size limit")
                _need(len(content) == entry.file_size, "ZIP entry size mismatch")
                contents[entry.filename] = content
        return _load(contents)
    except ResultsImportError:
        raise
    except (OSError, ValueError, RuntimeError, NotImplementedError, EOFError, zlib.error) as exc:
        raise ResultsImportError(f"Cannot read frozen results ZIP: {exc}") from exc
    except zipfile.BadZipFile as exc:
        raise ResultsImportError(f"Malformed results ZIP: {exc}") from exc


def load_results_directory(path: Path) -> DissertationResults:
    """Read required compact files from a study root; other study files are ignored."""
    expected = cast(dict[str, str], _manifest()["files"])
    try:
        _need(path.is_dir() and not path.is_symlink(), "Study root must be a regular directory")
        data: dict[str, bytes] = {}
        total = 0
        for name in expected:
            target = path
            for part in PurePosixPath(name).parts:
                target = target / part
                _need(not target.is_symlink(), f"Symbolic links are not allowed: {name}")
            _need(target.is_file(), f"Missing required study file: {name}")
            _need(target.stat().st_size <= MAX_PACKET_BYTES - total, "Study exceeds 5 MiB limit")
            with target.open("rb") as stream:
                content = stream.read(MAX_PACKET_BYTES - total + 1)
            total += len(content)
            _need(total <= MAX_PACKET_BYTES, "Study exceeds 5 MiB limit")
            data[name] = content
        return _load(data)
    except ResultsImportError:
        raise
    except OSError as exc:
        raise ResultsImportError(f"Cannot read study directory: {exc}") from exc


def load_builtin_results() -> DissertationResults:
    """Load the shipped original compact study, requiring no private raw directory."""
    try:
        data = (
            resource_files("traffictwin.resources.research")
            .joinpath("joint_confirmation_results.zip")
            .read_bytes()
        )
    except OSError as exc:
        raise ResultsImportError(f"Built-in results packet is unavailable: {exc}") from exc
    _need(_sha(data) == _manifest()["packet_sha256"], "Built-in packet fingerprint mismatch")
    return load_results_zip(data)
