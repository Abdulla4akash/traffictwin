from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

from pypdf import PdfReader

from traffictwin.reporting.builder import build_run_report
from traffictwin.reporting.pdf import report_to_pdf_bytes


def test_pdf_report_is_readable_and_contains_required_sections() -> None:
    report = build_run_report(
        "tests/fixtures/bundles/baseline_valid",
        clock=lambda: datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )

    payload = report_to_pdf_bytes(report)
    reader = PdfReader(BytesIO(payload))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert payload.startswith(b"%PDF")
    assert len(reader.pages) >= 1
    assert report.title in text
    assert "Metrics" in text
    assert "Diagnostic Hypotheses" in text
    assert "Limitations" in text
    assert "Page 1" in text
    assert payload == report_to_pdf_bytes(report)
