"""Descriptive analysis of explicitly labelled synthetic participant-result fixtures."""

from __future__ import annotations

import csv
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskOutcome(StrEnum):
    """Allowed task outcomes from the anonymised result contract."""

    COMPLETED = "completed"
    COMPLETED_WITH_ASSISTANCE = "completed_with_assistance"
    NOT_COMPLETED = "not_completed"


class EvaluationTaskResult(BaseModel):
    """One observed task result."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    outcome: TaskOutcome
    elapsed_seconds: float = Field(ge=0)
    assistance_count: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class ParticipantEvaluationResult(BaseModel):
    """One anonymised participant record."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    participant_code: str = Field(pattern=r"^TT-[A-Z0-9]{6,12}$")
    role_category: Literal[
        "researcher",
        "postgraduate_student",
        "traffic_professional",
        "other",
    ]
    experience_band: Literal[
        "under_1_year",
        "1_to_3_years",
        "4_to_7_years",
        "8_plus_years",
    ]
    session_date: date
    tasks: list[EvaluationTaskResult] = Field(min_length=1)
    ratings: dict[str, int] = Field(default_factory=dict)
    coded_comments: list[str] = Field(default_factory=list)
    withdrawn: bool = False

    @field_validator("ratings")
    @classmethod
    def validate_ratings(cls, value: dict[str, int]) -> dict[str, int]:
        """Enforce the published Q1-Q99 and 1-5 rating contract."""

        if any(re.fullmatch(r"Q[0-9]{1,2}", key) is None for key in value):
            raise ValueError("rating keys must match Q1-Q99")
        if any(rating < 1 or rating > 5 for rating in value.values()):
            raise ValueError("ratings must be integers from 1 to 5")
        return value


class MockParticipantDataset(BaseModel):
    """Container that cannot be confused with collected participant data."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    dataset_mode: Literal["synthetic_mock"]
    description: str
    results: list[ParticipantEvaluationResult]


class TaskAggregate(BaseModel):
    """Descriptive aggregate for one evaluation task."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    observations: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    assisted_count: int = Field(ge=0)
    not_completed_count: int = Field(ge=0)
    success_rate: float | None
    assisted_rate: float | None
    mean_elapsed_seconds: float | None
    median_elapsed_seconds: float | None
    mean_assistance_count: float | None


class RatingAggregate(BaseModel):
    """Descriptive aggregate for one questionnaire item."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    observations: int = Field(ge=0)
    mean_rating: float | None
    median_rating: float | None
    distribution: dict[int, int]


class ParticipantAnalysisReport(BaseModel):
    """Non-inferential summary with withdrawn records excluded."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_mode: Literal["synthetic_mock"]
    labelled_mock_data: bool = True
    total_records: int = Field(ge=0)
    included_records: int = Field(ge=0)
    withdrawn_records_excluded: int = Field(ge=0)
    task_aggregates: list[TaskAggregate]
    rating_aggregates: list[RatingAggregate]
    coded_comment_counts: dict[str, int]
    limitations: list[str]

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)


def load_mock_participant_dataset(path: str | Path) -> MockParticipantDataset:
    """Load only a dataset explicitly labelled synthetic_mock."""

    return MockParticipantDataset.model_validate_json(Path(path).read_text(encoding="utf-8"))


def analyse_participant_results(dataset: MockParticipantDataset) -> ParticipantAnalysisReport:
    """Compute deterministic descriptive summaries, excluding withdrawn records."""

    included = [result for result in dataset.results if not result.withdrawn]
    task_rows: dict[str, list[EvaluationTaskResult]] = defaultdict(list)
    rating_rows: dict[str, list[int]] = defaultdict(list)
    comment_counts: Counter[str] = Counter()
    for result in included:
        for task in result.tasks:
            task_rows[task.task_id].append(task)
        for question_id, rating in result.ratings.items():
            rating_rows[question_id].append(rating)
        comment_counts.update(result.coded_comments)
    return ParticipantAnalysisReport(
        source_mode=dataset.dataset_mode,
        total_records=len(dataset.results),
        included_records=len(included),
        withdrawn_records_excluded=len(dataset.results) - len(included),
        task_aggregates=[
            _task_aggregate(task_id, task_rows[task_id]) for task_id in sorted(task_rows)
        ],
        rating_aggregates=[
            _rating_aggregate(question_id, rating_rows[question_id])
            for question_id in sorted(rating_rows, key=_question_number)
        ],
        coded_comment_counts=dict(sorted(comment_counts.items())),
        limitations=[
            "This report uses labelled synthetic mock records, not participant observations.",
            "Withdrawn records are excluded from every descriptive aggregate.",
            "Small-sample summaries are descriptive and are not population estimates.",
            "Comment codes are supplied labels; no automated qualitative coding or LLM is used.",
            "No recruitment or data collection is authorised by this tooling.",
        ],
    )


def participant_analysis_to_csv(report: ParticipantAnalysisReport) -> str:
    """Render task and rating aggregates as tidy CSV."""

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["section", "identifier", "measure", "value"])
    for task_row in report.task_aggregates:
        values = task_row.model_dump(mode="json")
        for key in sorted(values):
            if key != "task_id":
                writer.writerow(["task", task_row.task_id, key, values[key]])
    for rating_row in report.rating_aggregates:
        values = rating_row.model_dump(mode="json")
        for key in sorted(values):
            if key not in {"question_id", "distribution"}:
                writer.writerow(["rating", rating_row.question_id, key, values[key]])
        for score, count in sorted(rating_row.distribution.items()):
            writer.writerow(["rating", rating_row.question_id, f"score_{score}_count", count])
    for code, count in report.coded_comment_counts.items():
        writer.writerow(["coded_comment", code, "count", count])
    return output.getvalue()


def _task_aggregate(task_id: str, rows: list[EvaluationTaskResult]) -> TaskAggregate:
    observations = len(rows)
    completed = sum(row.outcome is TaskOutcome.COMPLETED for row in rows)
    assisted = sum(row.outcome is TaskOutcome.COMPLETED_WITH_ASSISTANCE for row in rows)
    not_completed = sum(row.outcome is TaskOutcome.NOT_COMPLETED for row in rows)
    elapsed = [row.elapsed_seconds for row in rows]
    assistance = [row.assistance_count for row in rows]
    return TaskAggregate(
        task_id=task_id,
        observations=observations,
        completed_count=completed,
        assisted_count=assisted,
        not_completed_count=not_completed,
        success_rate=(completed + assisted) / observations if observations else None,
        assisted_rate=assisted / observations if observations else None,
        mean_elapsed_seconds=statistics.fmean(elapsed) if elapsed else None,
        median_elapsed_seconds=statistics.median(elapsed) if elapsed else None,
        mean_assistance_count=statistics.fmean(assistance) if assistance else None,
    )


def _rating_aggregate(question_id: str, values: list[int]) -> RatingAggregate:
    counts = Counter(values)
    return RatingAggregate(
        question_id=question_id,
        observations=len(values),
        mean_rating=statistics.fmean(values) if values else None,
        median_rating=statistics.median(values) if values else None,
        distribution={score: counts.get(score, 0) for score in range(1, 6)},
    )


def _question_number(question_id: str) -> int:
    return int(question_id[1:])
