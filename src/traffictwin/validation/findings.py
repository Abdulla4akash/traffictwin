"""Validation findings."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.validation.codes import ValidationCode


class Severity(StrEnum):
    """Validation finding severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class ValidationFinding(BaseModel):
    """One machine-readable validation finding."""

    model_config = ConfigDict(extra="forbid")

    code: ValidationCode
    severity: Severity
    message: str = Field(min_length=1)
    file: str | None = None
    row: int | None = Field(default=None, ge=1)
    field: str | None = None
    value: Any = None
    may_continue: bool
    affected_capabilities: list[str] = Field(default_factory=list)
