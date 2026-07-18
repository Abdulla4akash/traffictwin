"""Self-contained HTML rendering for deterministic reports."""

from __future__ import annotations

from html import escape

from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.models import ResearchReport


def report_to_html(report: ResearchReport) -> str:
    """Render a report to small standalone HTML without remote assets."""

    markdown = escape(report_to_markdown(report))
    title = escape(report.title)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{title}</title>\n"
        "  <style>\n"
        "    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; }\n"
        "    pre { white-space: pre-wrap; line-height: 1.45; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"<pre>{markdown}</pre>\n"
        "</body>\n"
        "</html>\n"
    )
