"""Markdown rendering for deterministic TrafficTwin reports."""

from __future__ import annotations

from traffictwin.reporting.models import ResearchReport


def report_to_markdown(report: ResearchReport) -> str:
    """Render a report as deterministic Markdown."""

    lines = [
        f"# {report.title}",
        "",
        f"- Report ID: `{report.report_id}`",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        f"- Source: `{report.source_reference}`",
        f"- Synthetic: `{report.synthetic}`",
        "",
    ]
    for warning in report.warnings:
        lines.append(f"> Warning: {warning}")
        lines.append("")
    for title, body in report.sections:
        lines.append(f"## {title}")
        lines.append("")
        for item in body:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
