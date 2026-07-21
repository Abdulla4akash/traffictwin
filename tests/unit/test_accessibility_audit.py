from __future__ import annotations

from traffictwin.ui.audit import AccessibilitySnapshot, analyse_accessibility_snapshots


def test_accessibility_snapshot_audit_passes_clean_page() -> None:
    snapshot = AccessibilitySnapshot(
        page_name="Home",
        page_title="TrafficTwin",
        main_h1_texts=["Home"],
        unnamed_interactive_count=0,
        images_without_alt_count=0,
        duplicate_ids=[],
        horizontal_overflow=False,
    )

    report = analyse_accessibility_snapshots([snapshot])

    assert report.passed is True
    assert report.issues == []


def test_accessibility_snapshot_audit_reports_structural_failures() -> None:
    snapshot = AccessibilitySnapshot(
        page_name="Replay",
        page_title="TrafficTwin",
        main_h1_texts=[],
        unnamed_interactive_count=2,
        images_without_alt_count=1,
        duplicate_ids=["duplicate"],
        horizontal_overflow=True,
    )

    report = analyse_accessibility_snapshots([snapshot])

    assert report.passed is False
    assert {issue.code for issue in report.issues} == {
        "MAIN_HEADING_COUNT",
        "UNNAMED_INTERACTIVE",
        "IMAGE_ALT_MISSING",
        "DUPLICATE_DOM_ID",
        "HORIZONTAL_OVERFLOW",
    }
