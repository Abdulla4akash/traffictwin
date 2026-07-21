"""Self-contained HTML rendering for deterministic reports."""

from __future__ import annotations

from html import escape

from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.models import ResearchReport


def report_to_html(report: ResearchReport) -> str:
    """Render a report to small standalone HTML without remote assets."""

    computed_report = report.model_copy(update={"analyst_annotations": []})
    markdown = escape(report_to_markdown(computed_report))
    title = escape(report.title)
    annotations = _annotation_html(report)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{title}</title>\n"
        "  <style>\n"
        "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; }\n"
        "    pre { white-space: pre-wrap; line-height: 1.45; }\n"
        "    .analyst-annotations { margin-top: 2rem; padding: 1rem; "
        "border: 2px solid #2563eb; background: #eff6ff; }\n"
        "    .analyst-annotation { margin-top: 1rem; padding-top: 0.75rem; "
        "border-top: 1px solid #93c5fd; }\n"
        "    .analyst-note { white-space: pre-wrap; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"<pre>{markdown}</pre>\n"
        f"{annotations}"
        "</body>\n"
        "</html>\n"
    )


def _annotation_html(report: ResearchReport) -> str:
    if not report.analyst_annotations:
        return ""
    parts = [
        '<section class="analyst-annotations" aria-label="Analyst annotations">\n',
        "  <h2>Analyst Annotations — Non-computed</h2>\n",
        (
            "  <p><strong>Analyst-authored append-only commentary.</strong> These entries are "
            "not computed findings and do not change metrics, rules, provenance, or claim "
            "counts.</p>\n"
        ),
    ]
    for annotation in report.analyst_annotations:
        parts.extend(
            [
                '  <article class="analyst-annotation">\n',
                (
                    f"    <h3>Annotation {annotation.sequence}: "
                    f"{escape(annotation.decision_label.value)}</h3>\n"
                ),
                (
                    f"    <p>Author: <code>{escape(annotation.author_label)}</code><br>"
                    f"Timestamp: <code>{escape(annotation.created_at.isoformat())}</code><br>"
                    f"Target: <code>{escape(annotation.target.key)}</code><br>"
                    f"Annotation ID: <code>{escape(annotation.annotation_id)}</code></p>\n"
                ),
                f'    <p class="analyst-note">{escape(annotation.note)}</p>\n',
                "  </article>\n",
            ]
        )
    parts.append("</section>\n")
    return "".join(parts)
