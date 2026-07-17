"""Diagnostic report serialisation helpers."""

from __future__ import annotations

from pathlib import Path

from traffictwin.diagnostics.report import DiagnosticReport


def write_diagnostic_report(report: DiagnosticReport, path: str | Path) -> None:
    """Write a diagnostic report as JSON."""

    Path(path).write_text(report.to_json(), encoding="utf-8")


def read_diagnostic_report(path: str | Path) -> DiagnosticReport:
    """Read a diagnostic report from JSON."""

    return DiagnosticReport.model_validate_json(Path(path).read_text(encoding="utf-8"))
