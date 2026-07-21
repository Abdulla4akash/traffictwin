"""Invariant one-page A4 renderer for REP-04 executive summaries."""

from __future__ import annotations

from html import escape
from io import BytesIO

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from traffictwin.reporting.executive import ExecutiveSummary


class ExecutiveSummaryLayoutError(RuntimeError):
    """Raised when complete REP-04 content cannot fit on exactly one A4 page."""


def executive_summary_to_pdf_bytes(summary: ExecutiveSummary) -> bytes:
    """Render every projected warning and limitation, failing closed on page overflow."""

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=15 * mm,
        bottomMargin=14 * mm,
        title=_plain(summary.title),
        author="TrafficTwin",
        subject="Deterministic one-page executive summary",
        invariant=1,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExecutiveTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17324D"),
        spaceAfter=2 * mm,
    )
    meta_style = ParagraphStyle(
        "ExecutiveMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=9.2,
        textColor=colors.HexColor("#4D5E6B"),
        spaceAfter=0.7 * mm,
    )
    heading_style = ParagraphStyle(
        "ExecutiveHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=12.5,
        textColor=colors.HexColor("#0B7285"),
        spaceBefore=2.2 * mm,
        spaceAfter=1 * mm,
    )
    body_style = ParagraphStyle(
        "ExecutiveBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=9.7,
        textColor=colors.HexColor("#243444"),
        bulletIndent=2.5 * mm,
        leftIndent=3.5 * mm,
        firstLineIndent=-2.2 * mm,
        spaceAfter=0.6 * mm,
    )
    small_style = ParagraphStyle(
        "ExecutiveSmall",
        parent=body_style,
        fontSize=6.9,
        leading=8.4,
        textColor=colors.HexColor("#526473"),
        leftIndent=0,
        firstLineIndent=0,
    )
    warning_style = ParagraphStyle(
        "ExecutiveWarning",
        parent=body_style,
        borderColor=colors.HexColor("#D97706"),
        borderWidth=0.5,
        borderPadding=3.5,
        backColor=colors.HexColor("#FFF7E6"),
        leftIndent=0,
        firstLineIndent=0,
        spaceAfter=0.8 * mm,
    )
    story = [Paragraph(_markup(summary.title), title_style)]
    story.extend(
        [
            Paragraph(
                f"<b>Source mode:</b> {_markup(summary.source_mode.value)} | "
                f"<b>Report:</b> {_markup(summary.source_report_id)} | "
                f"<b>Type:</b> {_markup(summary.source_report_type.value)} | "
                f"<b>Generated:</b> {_markup(summary.generated_at)}",
                meta_style,
            ),
            Paragraph(
                f"<b>Source evidence:</b> {_markup(summary.source_reference)} | "
                f"<b>Scientific fingerprint:</b> {_markup(summary.source_scientific_fingerprint)}",
                meta_style,
            ),
            Spacer(1, 0.5 * mm),
        ]
    )
    availability = summary.availability
    cards = Table(
        [
            [
                _card("Typed claims", availability.total_claims, meta_style),
                _card("Available", availability.available_claims, meta_style),
                _card("Unavailable", availability.unavailable_claims, meta_style),
                _card("Beyond highlights", summary.omitted_claims, meta_style),
            ]
        ],
        colWidths=[43.5 * mm] * 4,
    )
    cards.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF6F8")),
                ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFD7DF")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFD7DF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.extend([Paragraph("Evidence availability", heading_style), cards])
    story.append(Paragraph("Selected computed highlights", heading_style))
    if not summary.highlights:
        story.append(
            Paragraph("- No typed computed claims were available for selection.", body_style)
        )
    for item in summary.highlights:
        unit = f" {item.unit}" if item.unit else ""
        reasons = ", ".join(item.reason_codes) or "none"
        story.append(
            KeepTogether(
                [
                    Paragraph(
                        f"<b>{item.rank}. {_markup(item.label)} "
                        f"[{item.provenance_reference_id}]</b>",
                        body_style,
                    ),
                    Paragraph(
                        f"{_markup(item.scientific_key)} | {_markup(item.status)} / "
                        f"{_markup(item.availability.value)} | "
                        f"{_markup(item.display_value + unit)} | Reasons: {_markup(reasons)}",
                        small_style,
                    ),
                ]
            )
        )
    story.append(Paragraph(f"Warnings - all retained ({len(summary.warnings)})", heading_style))
    story.extend(Paragraph(f"- {_markup(item)}", warning_style) for item in summary.warnings)
    story.append(
        Paragraph(f"Limitations - all retained ({len(summary.limitations)})", heading_style)
    )
    story.extend(Paragraph(f"- {_markup(item)}", body_style) for item in summary.limitations)
    story.append(Paragraph("Provenance links", heading_style))
    for link in summary.provenance_links:
        story.append(
            Paragraph(
                f"<b>{link.reference_id}</b> "
                f'<link href="{escape(link.href, quote=True)}">{_markup(link.label)}</link> | '
                f"{_markup(link.target_kind)}:{_markup(link.target_id)} | "
                f"{link.fingerprint[:12]}",
                small_style,
            )
        )
    story.append(
        Paragraph(
            f"<b>Selection boundary:</b> {_markup(summary.selection_policy)} "
            "Analyst annotations included: false. Scientific recomputation performed: false.",
            small_style,
        )
    )
    try:
        document.build(story, onFirstPage=_page_decorations, onLaterPages=_page_decorations)
    except Exception as exc:
        msg = f"executive summary could not be laid out without omitting content: {exc}"
        raise ExecutiveSummaryLayoutError(msg) from exc
    payload = output.getvalue()
    pages = len(PdfReader(BytesIO(payload)).pages)
    if pages != 1:
        msg = (
            f"executive summary requires {pages} A4 pages; one-page export refused because "
            "warnings and limitations cannot be omitted"
        )
        raise ExecutiveSummaryLayoutError(msg)
    return payload


def _card(label: str, value: int, style: ParagraphStyle) -> Paragraph:
    return Paragraph(f"<b><font size=11>{value}</font></b><br/>{_markup(label)}", style)


def _page_decorations(canvas: Canvas, document: SimpleDocTemplate) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#B7C7D3"))
    canvas.line(12 * mm, height - 10 * mm, width - 12 * mm, height - 10 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(colors.HexColor("#526473"))
    canvas.drawString(12 * mm, height - 7.5 * mm, "TRAFFICTWIN EXECUTIVE SUMMARY")
    page_label = "Page 1 of 1"
    page_width = stringWidth(page_label, "Helvetica", 6.5)
    canvas.drawString(width - 12 * mm - page_width, 8 * mm, page_label)
    canvas.drawString(
        12 * mm, 8 * mm, "All warnings and limitations retained - verify source report"
    )
    canvas.restoreState()


def _plain(value: str) -> str:
    return value.replace("\u2013", "-").replace("\u2014", "-").replace("\u2011", "-")


def _markup(value: str) -> str:
    return escape(_plain(value)).replace("\n", "<br/>").replace("`", "")
