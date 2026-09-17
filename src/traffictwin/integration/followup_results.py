"""Read the frozen September 15 results; never execute the archived experiments."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from dataclasses import asdict, dataclass
from importlib.resources import files as resource_files
from typing import Any

from traffictwin.integration.dissertation_results import ResultsImportError

STUDY_LABELS = {
    "07_two_choice": "7 · Two-choice comparator",
    "08_half_speed": "8 · Half-speed servers",
    "09_second_actor": "9 · Second actor",
}
ARM_LABELS = {
    "ingress_dla": "Ingress",
    "dla": "Common-target",
    "per_task_dla": "Per-task",
    "causal_round_robin": "Round-robin",
    "dla_p2c": "Two-choice",
}
BASE_ARMS = tuple(arm for arm in ARM_LABELS if arm != "dla_p2c")
CONDITION_ARMS = {
    "baseline": BASE_ARMS,
    "07_two_choice": ("dla_p2c",),
    "08_half_speed": BASE_ARMS,
    "09_second_actor": BASE_ARMS,
}
# Each term names the exact condition, policy and sign in the archived contrast.
CONTRAST_TERMS: dict[tuple[str, str], tuple[tuple[str, str, int], ...]] = {
    ("07_two_choice", "per_task_minus_two_choice"): (
        ("baseline", "per_task_dla", 1),
        ("07_two_choice", "dla_p2c", -1),
    ),
    ("07_two_choice", "two_choice_minus_ingress"): (
        ("07_two_choice", "dla_p2c", 1),
        ("baseline", "ingress_dla", -1),
    ),
    ("07_two_choice", "two_choice_minus_round_robin"): (
        ("07_two_choice", "dla_p2c", 1),
        ("baseline", "causal_round_robin", -1),
    ),
    ("08_half_speed", "change_in_per_task_minus_round_robin_gap"): (
        ("08_half_speed", "per_task_dla", 1),
        ("08_half_speed", "causal_round_robin", -1),
        ("baseline", "per_task_dla", -1),
        ("baseline", "causal_round_robin", 1),
    ),
    **{
        (study, f"{left}_minus_{right}"): ((study, left, 1), (study, right, -1))
        for study in ("08_half_speed", "09_second_actor")
        for left, right in (
            ("per_task_dla", "ingress_dla"),
            ("dla", "ingress_dla"),
            ("per_task_dla", "causal_round_robin"),
        )
    },
}


@dataclass(frozen=True)
class FollowupCell:
    """One archived policy/block row with its original offered denominator."""

    study: str
    block: int
    fleet_seed: int
    evaluator_seed: int
    arm: str
    reused_reference: bool
    offered: int
    admitted: int
    successes: int
    attainment_pct: float


@dataclass(frozen=True)
class FollowupContrast:
    """One original contrast using the all-ten simultaneous interval family."""

    study: str
    name: str
    effects_pp: tuple[float, ...]
    mean_pp: float
    low_pp: float
    high_pp: float


@dataclass(frozen=True)
class FollowupResults:
    """Authenticated original files and typed values for the presentation layer."""

    cells: tuple[FollowupCell, ...]
    contrasts: tuple[FollowupContrast, ...]
    means: dict[tuple[str, str], float]
    files: dict[str, bytes]
    hashes: dict[str, str]
    packet: bytes
    repository_commit: str
    execution_source_commit: str

    def cells_for(self, study: str) -> tuple[FollowupCell, ...]:
        """Include the three explicitly reused comparator policies for study 7."""
        _need(study in STUDY_LABELS, "Unknown follow-up study")
        return tuple(
            cell
            for cell in self.cells
            if cell.study == study
            or (
                study == "07_two_choice"
                and cell.study == "baseline"
                and cell.arm in ("ingress_dla", "per_task_dla", "causal_round_robin")
            )
        )

    def gap_reference_cells(self) -> tuple[FollowupCell, ...]:
        """Original-speed controls for the half-speed difference-in-differences."""
        return tuple(
            cell
            for cell in self.cells
            if cell.study == "baseline" and cell.arm in ("per_task_dla", "causal_round_robin")
        )


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ResultsImportError(message)


def _close(actual: float, expected: float) -> bool:
    return math.isfinite(actual) and math.isclose(actual, expected, rel_tol=0, abs_tol=5e-12)


def _resource_bytes(name: str) -> bytes:
    return resource_files("traffictwin.resources.research").joinpath(name).read_bytes()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_values(
    originals: dict[str, bytes],
) -> tuple[tuple[FollowupCell, ...], tuple[FollowupContrast, ...], dict[tuple[str, str], float]]:
    analysis = json.loads(originals["ANALYSIS.json"])
    audit = json.loads(originals["evidence/FINAL_ANALYSIS_AUDIT.json"])
    seal = json.loads(originals["evidence/EXECUTION_SEAL.json"])
    _need(
        analysis["status"] == "complete"
        and audit["status"] == "passed"
        and analysis["new_full_cells"] == 72
        and analysis["reused_full_cells"] == 32
        and analysis["blocks_per_study"] == 8
        and audit["cell_rows_checked"] == 104
        and audit["contrasts_checked"] == 10
        and audit["blocks_per_study"] == 8
        and audit["source_commit"] == seal["source_commit"],
        "Follow-up completion or audit scope mismatch",
    )
    for field, name in (
        ("analysis_sha256", "ANALYSIS.json"),
        ("cell_results_csv_sha256", "CELL_RESULTS.csv"),
        ("paired_effects_csv_sha256", "PAIRED_EFFECTS.csv"),
        ("execution_seal_sha256", "evidence/EXECUTION_SEAL.json"),
        ("baseline_ledger_sha256", "evidence/BASELINE.json"),
        ("root_complete_sha256", "runs/COMPLETE.json"),
    ):
        _need(audit[field] == _sha(originals[name]), f"Historical audit binding mismatch: {name}")
    _need(
        analysis["execution_seal_sha256"] == audit["execution_seal_sha256"],
        "Analysis execution seal mismatch",
    )
    cells = tuple(FollowupCell(**row) for row in analysis["cells"])
    index = {(c.study, c.block, c.arm): c for c in cells}
    _need(
        len(cells) == len(index) == 104
        and set(index)
        == {
            (study, block, arm)
            for study, arms in CONDITION_ARMS.items()
            for block in range(8)
            for arm in arms
        },
        "Incomplete or duplicate follow-up matrix",
    )
    for cell in cells:
        _need(
            cell.reused_reference is (cell.study == "baseline")
            and (cell.fleet_seed, cell.evaluator_seed) == (100 + cell.block, 200 + cell.block)
            and 0 <= cell.successes <= cell.admitted <= cell.offered
            and cell.offered > 0
            and _close(cell.attainment_pct, 100 * cell.successes / cell.offered),
            "Follow-up count, denominator or block identity mismatch",
        )
    csv_rows = list(csv.DictReader(io.StringIO(originals["CELL_RESULTS.csv"].decode())))
    _need(
        csv_rows == [{key: str(value) for key, value in asdict(c).items()} for c in cells],
        "Cell CSV differs from archived analysis",
    )
    means = {
        (study, arm): value
        for study, arms in analysis["arm_mean_attainment_pct"].items()
        for arm, value in arms.items()
    }
    _need(
        set(means) == {(study, arm) for study, arms in CONDITION_ARMS.items() for arm in arms},
        "Arm mean matrix mismatch",
    )
    for (study, arm), value in means.items():
        _need(
            _close(value, statistics.mean(index[study, b, arm].attainment_pct for b in range(8))),
            "Arm means must give each block equal weight",
        )
    contrasts = []
    seen = set()
    for row in analysis["contrasts"]:
        key = (row["study"], row["contrast"])
        _need(key in CONTRAST_TERMS and key not in seen, "Unknown or duplicate follow-up contrast")
        seen.add(key)
        effects = row["effects_pp"]
        expected = [
            math.fsum(
                sign * index[study, b, arm].attainment_pct
                for study, arm, sign in CONTRAST_TERMS[key]
            )
            for b in range(8)
        ]
        interval = row["all_ten_family95"]
        _need(
            len(effects) == 8
            and all(_close(a, b) for a, b in zip(effects, expected, strict=True))
            and interval["family_size"] == 10
            and interval["df"] == 7
            and interval["n_blocks"] == 8
            and _close(interval["mean_pp"], statistics.mean(effects))
            and math.isfinite(interval["low_pp"])
            and math.isfinite(interval["high_pp"])
            and interval["low_pp"] <= interval["mean_pp"] <= interval["high_pp"],
            "Follow-up paired effects or all-ten interval scope mismatch",
        )
        contrasts.append(
            FollowupContrast(
                study=row["study"],
                name=row["contrast"],
                effects_pp=tuple(effects),
                mean_pp=interval["mean_pp"],
                low_pp=interval["low_pp"],
                high_pp=interval["high_pp"],
            )
        )
    _need(seen == set(CONTRAST_TERMS), "Missing declared follow-up comparison")
    return cells, tuple(contrasts), means


def load_followup_results() -> FollowupResults:
    """Load only the installed, fingerprint-bound September 15 packet."""
    try:
        manifest: dict[str, Any] = json.loads(_resource_bytes("followup_results_manifest.json"))
        packet = _resource_bytes("followup_results.zip")
        _need(_sha(packet) == manifest["packet_sha256"], "Follow-up packet fingerprint mismatch")
        with zipfile.ZipFile(io.BytesIO(packet)) as archive:
            _need(
                len(archive.namelist()) == len(manifest["files"])
                and set(archive.namelist()) == set(manifest["files"]),
                "Follow-up packet file set mismatch",
            )
            originals = {name: archive.read(name) for name in manifest["files"]}
        hashes = {name: _sha(data) for name, data in originals.items()}
        _need(hashes == manifest["files"], "Follow-up evidence fingerprint mismatch")
        cells, contrasts, means = _validate_values(originals)
        _need(
            manifest["execution_source_commit"]
            == json.loads(originals["evidence/EXECUTION_SEAL.json"])["source_commit"],
            "Follow-up execution source mismatch",
        )
        return FollowupResults(
            cells,
            contrasts,
            means,
            originals,
            hashes,
            packet,
            manifest["repository_commit"],
            manifest["execution_source_commit"],
        )
    except ResultsImportError:
        raise
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise ResultsImportError(f"Follow-up evidence is unavailable or invalid: {exc}") from exc
