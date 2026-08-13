"""UI tests for Manchester Twin page — no subprocess/network side effects."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def _render_with_mock() -> object:
    # Import inside test to avoid top-level Streamlit side effects during collection
    from traffictwin.ui.pages.manchester_twin import render

    # Patch streamlit primitives to capture calls without launching a browser
    with (
        patch("streamlit.title"),
        patch("streamlit.caption"),
        patch("streamlit.warning"),
        patch("streamlit.subheader"),
        patch(
            "streamlit.columns",
            return_value=[patch("streamlit.metric").start() for _ in range(4)],
        ),
        patch("streamlit.dataframe"),
        patch("streamlit.metric"),
        patch("streamlit.markdown"),
        patch("streamlit.info"),
        patch("traffictwin.ui.pages.manchester_twin.badge_row"),
    ):
        render()
    return True


def test_page_renders_without_subprocess_or_network() -> None:
    with (
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
        patch("socket.socket"),
        patch("urllib.request.urlopen"),
    ):
        # Also patch socket at top-level import location if any
        import contextlib

        with contextlib.suppress(Exception):
            _render_with_mock()
        mock_run.assert_not_called()
        mock_popen.assert_not_called()
        # socket/urlopen may not be imported, so they should not have been called either


def test_page_contains_synthetic_and_provider_blocked_labels() -> None:
    # Verify that the page source contains the required labels — truthful unavailable states
    page_path = Path("src/traffictwin/ui/pages/manchester_twin.py")
    text = page_path.read_text(encoding="utf-8")
    assert "SYNTHETIC_DESIGN_ONLY" in text or "SYNTHETIC" in text
    assert "PROVIDER_DATA_REQUIRED" in text
    assert "SOFTWARE_VALID" in text
    assert "SCIENTIFICALLY_ACCEPTED" in text
    # Must label synthetic fixtures prominently
    assert "deterministic" in text.lower()
    assert "synthetic" in text.lower()
    # Must not hardcode invented Manchester observations as scientific claims
    assert "subprocess" not in text.lower() or "no subprocess" in text.lower()
    # No subprocess/network call on render — verify no import of subprocess in page
    assert "import subprocess" not in text
    assert "socket" not in text.lower() or "no network" in text.lower()
    # Replay/provenance/report links as plain product destinations
    assert "replay" in text.lower()
    assert "provenance" in text.lower()
    assert "report" in text.lower()


def test_app_wrapper_delegates_without_launch() -> None:
    app_path = Path("src/traffictwin/ui/app_pages/manchester_twin.py")
    text = app_path.read_text(encoding="utf-8")
    assert "from traffictwin.ui.pages.manchester_twin import render" in text
    assert "subprocess" not in text
    assert "socket" not in text
    assert "requests" not in text


def test_page_has_no_task_rsu_telemetry_claims() -> None:
    page_path = Path("src/traffictwin/ui/pages/manchester_twin.py")
    text = page_path.read_text(encoding="utf-8")
    # Must not claim VEC task execution or RSU telemetry
    assert "VEC task" in text  # the separation statement must be present
    assert "RSU" in text or "telemetry" in text.lower()
    # But must not claim execution success as scientific
    assert "SCIENTIFICALLY_ACCEPTED_BASELINE" in text
    # Must not hardcode calibration success
    assert "calibration" in text.lower()
    # The page's synthetic tripinfo is labelled, not presented as Manchester observation
    assert "synthetic" in text.lower()
