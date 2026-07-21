"""Publication-oriented PDF rendering for deterministic research reports."""

from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from traffictwin.reporting.models import ResearchReport


def report_to_pdf_bytes(report: ResearchReport) -> bytes:
    """Render a deterministic report payload as an A4 PDF."""

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=_plain(report.title),
        author="TrafficTwin",
        subject="Deterministic TrafficTwin research-software report",
        invariant=1,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TrafficTwinTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#17324D"),
        alignment=TA_CENTER,
        spaceAfter=10 * mm,
    )
    heading_style = ParagraphStyle(
        "TrafficTwinHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0B7285"),
        spaceBefore=5 * mm,
        spaceAfter=2.5 * mm,
    )
    body_style = ParagraphStyle(
        "TrafficTwinBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11.5,
        textColor=colors.HexColor("#243444"),
        bulletIndent=4 * mm,
        leftIndent=5 * mm,
        firstLineIndent=-3 * mm,
        spaceAfter=1.1 * mm,
    )
    metadata_style = ParagraphStyle(
        "TrafficTwinMetadata",
        parent=body_style,
        leftIndent=0,
        firstLineIndent=0,
        fontSize=8.5,
        textColor=colors.HexColor("#4D5E6B"),
    )
    warning_style = ParagraphStyle(
        "TrafficTwinWarning",
        parent=body_style,
        borderColor=colors.HexColor("#D97706"),
        borderWidth=0.6,
        borderPadding=6,
        backColor=colors.HexColor("#FFF7E6"),
        leftIndent=0,
        firstLineIndent=0,
        spaceBefore=2 * mm,
        spaceAfter=3 * mm,
    )
    annotation_style = ParagraphStyle(
        "TrafficTwinAnalystAnnotation",
        parent=body_style,
        borderColor=colors.HexColor("#2563EB"),
        borderWidth=0.7,
        borderPadding=7,
        backColor=colors.HexColor("#EFF6FF"),
        leftIndent=0,
        firstLineIndent=0,
        spaceBefore=1.5 * mm,
        spaceAfter=2.5 * mm,
    )
    story = [Paragraph(_markup(report.title), title_style)]
    metadata = [
        f"<b>Report ID:</b> {_markup(report.report_id)}",
        f"<b>Generated:</b> {_markup(report.generated_at.isoformat())}",
        f"<b>Source:</b> {_markup(report.source_reference)}",
        f"<b>Synthetic:</b> {_markup(str(report.synthetic))}",
    ]
    story.extend(Paragraph(line, metadata_style) for line in metadata)
    story.append(Spacer(1, 3 * mm))
    story.extend(
        Paragraph(f"<b>Warning:</b> {_markup(item)}", warning_style) for item in report.warnings
    )
    for title, items in report.sections:
        heading = Paragraph(_markup(title), heading_style)
        if not items:
            story.append(heading)
            story.append(Paragraph("No entries.", body_style))
            continue
        first = Paragraph(f"- {_markup(items[0])}", body_style)
        story.append(KeepTogether([heading, first]))
        story.extend(Paragraph(f"- {_markup(item)}", body_style) for item in items[1:])
    if report.analyst_annotations:
        story.append(Paragraph("Analyst Annotations - Non-computed", heading_style))
        story.append(
            Paragraph(
                (
                    "Analyst-authored append-only commentary. These entries are not computed "
                    "findings and do not change metrics, rules, provenance, or claim counts."
                ),
                warning_style,
            )
        )
        for annotation in report.analyst_annotations:
            note = _markup(annotation.note).replace("\n", "<br/>")
            content = (
                f"<b>Annotation {annotation.sequence} - "
                f"{_markup(annotation.decision_label.value)}</b><br/>"
                f"Author: {_markup(annotation.author_label)}<br/>"
                f"Timestamp: {_markup(annotation.created_at.isoformat())}<br/>"
                f"Target: {_markup(annotation.target.key)}<br/>"
                f"Annotation ID: {_markup(annotation.annotation_id)}<br/><br/>"
                f"{note}"
            )
            story.append(Paragraph(content, annotation_style))
    document.build(
        story,
        onFirstPage=_page_decorations,
        onLaterPages=_page_decorations,
    )
    return output.getvalue()


def _page_decorations(canvas: Canvas, document: BaseDocTemplate) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#B7C7D3"))
    canvas.line(20 * mm, height - 15 * mm, width - 20 * mm, height - 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#526473"))
    canvas.drawString(20 * mm, height - 12 * mm, "TRAFFICTWIN RESEARCH REPORT")
    page_label = f"Page {document.page}"
    page_width = stringWidth(page_label, "Helvetica", 7.5)
    canvas.drawString(width - 20 * mm - page_width, 12 * mm, page_label)
    canvas.drawString(20 * mm, 12 * mm, "Deterministic outputs - verify limitations before use")
    canvas.restoreState()


def _plain(value: str) -> str:
    return value.replace("\u2013", "-").replace("\u2014", "-").replace("\u2011", "-")


def _markup(value: str) -> str:
    return escape(_plain(value)).replace("`", "")
