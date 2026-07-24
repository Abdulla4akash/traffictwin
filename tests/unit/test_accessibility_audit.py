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
        expected_h1="Replay",
        main_h1_texts=[],
        main_landmark_count=0,
        streamlit_exception_count=1,
        unnamed_interactive_count=2,
        images_without_alt_count=1,
        duplicate_ids=["duplicate"],
        horizontal_overflow=True,
    )

    report = analyse_accessibility_snapshots([snapshot])

    assert report.passed is False
    assert {issue.code for issue in report.issues} == {
        "MAIN_HEADING_COUNT",
        "MAIN_LANDMARK_COUNT",
        "STREAMLIT_EXCEPTION",
        "UNNAMED_INTERACTIVE",
        "IMAGE_ALT_MISSING",
        "DUPLICATE_DOM_ID",
        "HORIZONTAL_OVERFLOW",
    }


def test_accessibility_snapshot_audit_reports_wrong_primary_heading() -> None:
    snapshot = AccessibilitySnapshot(
        page_name="Manchester Operations [dark/mobile]",
        page_title="TrafficTwin",
        expected_h1="Manchester Operations",
        url_path="manchester",
        viewport="mobile",
        viewport_width=390,
        viewport_height=844,
        requested_theme="dark",
        main_h1_texts=["Operations View"],
        unnamed_interactive_count=0,
        images_without_alt_count=0,
        duplicate_ids=[],
        horizontal_overflow=False,
    )

    report = analyse_accessibility_snapshots([snapshot])

    assert report.passed is False
    assert [issue.code for issue in report.issues] == ["MAIN_HEADING_MISMATCH"]
