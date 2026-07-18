"""Safe, read-only access to documented TOS training histories."""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

from pydantic import ValidationError

from traffictwin.integration.tos.analysis_models import (
    TosGreedyEvaluationSummary,
    TosTrainingPoint,
    TosTrainingRun,
    TosTrainingRunSummary,
)
from traffictwin.integration.tos.readers import TosPackageError, package_relative, safe_package_path

TRAINING_COLUMNS = (
    "update",
    "env_step",
    "mean_return",
    "mean_completion",
    "p_local",
    "p_v2i",
    "p_v2v",
    "avg_energy_j",
    "avg_latency_ms",
    "type_1_completion",
    "type_2_completion",
    "type_3_completion",
    "elapsed_s",
    "sps",
)

_SEED_RE = re.compile(r"(?:^|__)seed(?P<seed>\d+)$")


def list_training_runs(root: str | Path) -> list[TosTrainingRunSummary]:
    """Index all source training CSVs in deterministic filename order."""

    directory = safe_package_path(root, "training")
    if not directory.is_dir():
        return []
    return [_summarise_training_csv(root, path) for path in sorted(directory.glob("*.csv"))]


def load_training_run(
    root: str | Path,
    training_id: str,
    *,
    max_points: int = 800,
) -> TosTrainingRun:
    """Load one bounded training curve and its documented greedy summary."""

    if max_points < 2 or max_points > 10_000:
        raise ValueError("max_points must be between 2 and 10000")
    summaries = {summary.training_id: summary for summary in list_training_runs(root)}
    try:
        summary = summaries[training_id]
    except KeyError as exc:
        raise TosPackageError(f"training run not found: {training_id}") from exc
    source = safe_package_path(root, summary.source_file)
    points = _read_training_points(root, source)
    downsampled = len(points) > max_points
    if downsampled:
        indices = _sample_indices(len(points), max_points)
        points = [points[index] for index in indices]
    greedy = None
    if summary.greedy_summary_file is not None:
        greedy = _read_greedy_summary(root, summary.greedy_summary_file)
    return TosTrainingRun(
        summary=summary,
        points=points,
        greedy_evaluation=greedy,
        downsampled=downsampled,
    )


def _summarise_training_csv(root: str | Path, path: Path) -> TosTrainingRunSummary:
    points = _read_training_points(root, path)
    measured = [point for point in points if point.mean_completion is not None]
    greedy_path = path.with_name(f"{path.stem}_greedy_eval.json")
    machine_path = path.with_suffix(".machine.txt")
    seed_match = _SEED_RE.search(path.stem)
    policy_label = path.stem.split("_modelc_", maxsplit=1)[0]
    warnings: list[str] = []
    warmup_count = len(points) - len(measured)
    if warmup_count:
        warnings.append(f"{warmup_count} source warm-up rows have unavailable measured values.")
    if not greedy_path.is_file():
        warnings.append("Greedy-evaluation summary is unavailable for this training run.")
    return TosTrainingRunSummary(
        training_id=path.stem,
        policy_label=policy_label,
        training_seed=int(seed_match.group("seed")) if seed_match else None,
        source_file=package_relative(root, path),
        point_count=len(points),
        measured_point_count=len(measured),
        warmup_unavailable_count=warmup_count,
        final_env_step=points[-1].env_step if points else 0,
        final_mean_completion=measured[-1].mean_completion if measured else None,
        greedy_summary_file=(
            package_relative(root, greedy_path) if greedy_path.is_file() else None
        ),
        machine_record_file=(
            package_relative(root, machine_path) if machine_path.is_file() else None
        ),
        warnings=warnings,
    )


def _read_training_points(root: str | Path, path: Path) -> list[TosTrainingPoint]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            missing = sorted(set(TRAINING_COLUMNS) - set(headers))
            if missing:
                raise TosPackageError(
                    f"training CSV {path.name} is missing columns: {', '.join(missing)}"
                )
            relative = package_relative(root, path)
            points = [
                TosTrainingPoint(
                    update=_integer(raw["update"], "update", source_row),
                    env_step=_integer(raw["env_step"], "env_step", source_row),
                    mean_return=_optional_float(raw["mean_return"]),
                    mean_completion=_optional_float(raw["mean_completion"]),
                    p_local=_optional_float(raw["p_local"]),
                    p_v2i=_optional_float(raw["p_v2i"]),
                    p_v2v=_optional_float(raw["p_v2v"]),
                    avg_energy_j=_optional_float(raw["avg_energy_j"]),
                    avg_latency_ms=_optional_float(raw["avg_latency_ms"]),
                    type_1_completion=_optional_float(raw["type_1_completion"]),
                    type_2_completion=_optional_float(raw["type_2_completion"]),
                    type_3_completion=_optional_float(raw["type_3_completion"]),
                    elapsed_s=_required_float(raw["elapsed_s"], "elapsed_s", source_row),
                    sps=_required_float(raw["sps"], "sps", source_row),
                    source_file=relative,
                    source_row=source_row,
                )
                for source_row, raw in enumerate(reader, start=2)
            ]
    except (OSError, KeyError, ValidationError, ValueError) as exc:
        if isinstance(exc, TosPackageError):
            raise
        raise TosPackageError(f"cannot read training history {path.name}: {exc}") from exc
    if any(
        current.env_step <= previous.env_step
        for previous, current in zip(points, points[1:], strict=False)
    ):
        raise TosPackageError(f"training env_step is not strictly increasing in {path.name}")
    return points


def _read_greedy_summary(root: str | Path, relative: str) -> TosGreedyEvaluationSummary:
    path = safe_package_path(root, relative)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["source_file"] = package_relative(root, path)
        return TosGreedyEvaluationSummary.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise TosPackageError(f"cannot read greedy-evaluation summary {path.name}: {exc}") from exc


def _optional_float(value: str) -> float | None:
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _required_float(value: str, field: str, row: int) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise TosPackageError(f"{field} must be finite at training source row {row}")
    return parsed


def _integer(value: str, field: str, row: int) -> int:
    parsed = float(value)
    if not math.isfinite(parsed) or not parsed.is_integer():
        raise TosPackageError(f"{field} must be an integer at training source row {row}")
    return int(parsed)


def _sample_indices(length: int, limit: int) -> list[int]:
    if length <= limit:
        return list(range(length))
    return sorted({round(index * (length - 1) / (limit - 1)) for index in range(limit)})
