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
    if report.analyst_annotations:
        lines.extend(
            [
                "## Analyst Annotations — Non-computed",
                "",
                (
                    "> Analyst-authored append-only commentary. These entries are not computed "
                    "findings and do not change metrics, rules, provenance, or claim counts."
                ),
                "",
            ]
        )
        for annotation in report.analyst_annotations:
            lines.extend(
                [
                    (
                        f"### Annotation {annotation.sequence}: "
                        f"{_escape_markdown(annotation.decision_label.value)}"
                    ),
                    "",
                    f"- Author: `{_escape_markdown(annotation.author_label)}`",
                    f"- Timestamp: `{annotation.created_at.isoformat()}`",
                    f"- Target: `{annotation.target.key}`",
                    f"- Annotation ID: `{annotation.annotation_id}`",
                    "",
                ]
            )
            lines.extend(
                f"> {_escape_markdown(note_line)}" if note_line else ">"
                for note_line in annotation.note.split("\n")
            )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _escape_markdown(value: str) -> str:
    """Escape analyst-authored text so it cannot create report structure."""

    escaped = value.replace("\\", "\\\\")
    for character in "`*_{}[]()<>#+-.!|":
        escaped = escaped.replace(character, f"\\{character}")
    return escaped
