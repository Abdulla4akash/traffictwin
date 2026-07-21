"""Attach append-only analyst history to reports without changing computed claims."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from traffictwin.annotations import (
    MAX_ANNOTATIONS_PER_REPORT,
    AnalystAnnotation,
    AnalystAnnotationHistory,
    AnalystArtifactReference,
    annotation_target_matches,
)
from traffictwin.reporting.models import ReportClaimExclusion, ResearchReport


class AnnotationHistoryReader(Protocol):
    """Minimal registry read boundary needed by report rendering."""

    def list_analyst_annotations(
        self,
        *,
        target: AnalystArtifactReference | None = None,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> AnalystAnnotationHistory: ...


class ReportAnnotationError(ValueError):
    """Raised when history cannot be attached without loss or target drift."""


def attach_analyst_annotations(
    report: ResearchReport,
    annotations: Iterable[AnalystAnnotation],
) -> ResearchReport:
    """Return a report copy with a distinct, ordered analyst-authored history."""

    ordered = sorted(annotations, key=lambda item: item.sequence)
    if len(ordered) > MAX_ANNOTATIONS_PER_REPORT:
        raise ReportAnnotationError(
            f"report annotation count exceeds {MAX_ANNOTATIONS_PER_REPORT}; "
            "history was not attached"
        )
    identities = [item.annotation_id for item in ordered]
    if len(identities) != len(set(identities)):
        raise ReportAnnotationError("report annotation history contains duplicate identifiers")
    sequences = [item.sequence for item in ordered]
    if len(sequences) != len(set(sequences)):
        raise ReportAnnotationError("report annotation history contains duplicate sequences")
    if any(
        not any(
            annotation_target_matches(item.target, target) for target in report.annotation_targets
        )
        for item in ordered
    ):
        raise ReportAnnotationError("report annotation history contains an unrelated target")
    exclusions = list(report.claim_exclusions)
    if ordered and not any(item.category == "analyst_annotations" for item in exclusions):
        exclusions.append(
            ReportClaimExclusion(
                category="analyst_annotations",
                reason=(
                    "Append-only analyst-authored notes and decisions are commentary, not "
                    "computed TrafficTwin result claims."
                ),
                examples=["observation", "accepted", "rejected", "follow-up"],
            )
        )
    return report.model_copy(
        update={
            "analyst_annotations": ordered,
            "claim_exclusions": exclusions,
        }
    )


def attach_registry_annotations(
    report: ResearchReport,
    reader: AnnotationHistoryReader,
) -> ResearchReport:
    """Load all matching bounded history or refuse a silently truncated report."""

    by_identifier: dict[str, AnalystAnnotation] = {}
    for target in report.annotation_targets:
        page = reader.list_analyst_annotations(
            target=target,
            limit=MAX_ANNOTATIONS_PER_REPORT,
        )
        if page.has_more:
            raise ReportAnnotationError(
                "matching annotation history exceeds the report bound; use the paginated "
                "registry history export"
            )
        for annotation in page.annotations:
            by_identifier[annotation.annotation_id] = annotation
        if len(by_identifier) > MAX_ANNOTATIONS_PER_REPORT:
            raise ReportAnnotationError(
                f"report annotation count exceeds {MAX_ANNOTATIONS_PER_REPORT}; "
                "history was not attached"
            )
    return attach_analyst_annotations(report, by_identifier.values())
