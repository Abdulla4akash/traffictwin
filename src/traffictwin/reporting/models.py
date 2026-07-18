"""Report-export models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResearchReport(BaseModel):
    """Deterministic report payload rendered to Markdown or HTML."""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    title: str
    generated_at: datetime
    source_reference: str
    synthetic: bool
    sections: list[tuple[str, list[str]]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReportBuildError(RuntimeError):
    """Raised when a requested report cannot be built safely."""
