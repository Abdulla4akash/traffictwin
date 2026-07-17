"""Base interfaces and helpers for diagnostic rules."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import JsonScalar, MetricStatus, MetricValue
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.models import ConfidenceCategory, RuleResult


class Clock(Protocol):
    """Callable clock returning an aware timestamp."""

    def __call__(self) -> datetime: ...


class DiagnosticRule(ABC):
    """Base class for deterministic diagnostic rules."""

    rule_id: str
    rule_version: str = "1.0"
    title: str

    @abstractmethod
    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate the rule against one EvidencePack."""


class MetricLookup:
    """Convenience access to available metric values."""

    def __init__(self, evidence_pack: EvidencePack) -> None:
        self.evidence_pack = evidence_pack
        self._metrics = evidence_pack.metric_collection.by_key()

    def metric(self, key: str) -> MetricValue | None:
        """Return a metric by key."""

        return self._metrics.get(key)

    def has_available(self, key: str) -> bool:
        """Return True when a metric exists and is available."""

        metric = self.metric(key)
        return metric is not None and metric.status is MetricStatus.AVAILABLE

    def numeric(self, key: str) -> float | None:
        """Return an available finite numeric metric value."""

        metric = self.metric(key)
        if metric is None or metric.status is not MetricStatus.AVAILABLE:
            return None
        value = metric.value
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return numeric

    def mapping_number(self, key: str, child_key: str) -> float | None:
        """Return a numeric value from an available mapping metric."""

        metric = self.metric(key)
        if metric is None or metric.status is not MetricStatus.AVAILABLE:
            return None
        if not isinstance(metric.value, dict):
            return None
        value = metric.value.get(child_key)
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return numeric

    def available_metric_keys(self) -> set[str]:
        """Return all metric keys present in the evidence pack."""

        return set(self._metrics)


def validation_issue_count(evidence_pack: EvidencePack) -> int:
    """Return warning/error/fatal validation finding count from evidence summary."""

    counts = evidence_pack.validation_summary.get("counts_by_severity")
    if not isinstance(counts, dict):
        return 0
    total = 0
    for key in ("warning", "error", "fatal"):
        value = counts.get(key, 0)
        if isinstance(value, int):
            total += value
    return total


def validation_blocking_count(evidence_pack: EvidencePack) -> int:
    """Return error/fatal count from evidence summary."""

    counts = evidence_pack.validation_summary.get("counts_by_severity")
    if not isinstance(counts, dict):
        return 0
    total = 0
    for key in ("error", "fatal"):
        value = counts.get(key, 0)
        if isinstance(value, int):
            total += value
    return total


def confidence_from_support(
    *,
    required_complete: bool,
    supporting_conditions: int,
    contradiction_count: int,
    validation_issues: int,
    missing_context: int = 0,
) -> ConfidenceCategory:
    """Derive categorical confidence from evidence completeness and consistency."""

    if not required_complete:
        return ConfidenceCategory.UNAVAILABLE
    if contradiction_count:
        return ConfidenceCategory.LOW
    if supporting_conditions >= 4 and validation_issues == 0 and missing_context == 0:
        return ConfidenceCategory.HIGH
    if supporting_conditions >= 3 and validation_issues <= 1:
        return ConfidenceCategory.MODERATE
    return ConfidenceCategory.LOW


def scalar(value: object) -> JsonScalar:
    """Convert a display value into a JSON scalar."""

    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)
