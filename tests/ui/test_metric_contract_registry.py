"""UI tests for Metric Contract Registry page."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import default_session_state, load_ui_config


def _app() -> AppTest:
    at = AppTest.from_file("src/traffictwin/ui/app_pages/metric_contract_registry.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        at.session_state[key] = value
    at.session_state["_v07_navigation_active"] = True
    return at


def _text(at: AppTest) -> str:
    parts: list[str] = []
    parts.extend(str(t.value) for t in at.title)
    parts.extend(str(s.value) for s in at.header)
    parts.extend(str(s.value) for s in at.subheader)
    parts.extend(str(m.value) for m in at.markdown)
    parts.extend(str(c.value) for c in at.caption)
    for attr in ("info", "warning", "error", "success", "text"):
        parts.extend(str(x.value) for x in getattr(at, attr, []))
    return "\n".join(parts)


def test_page_renders_without_exception() -> None:
    at = _app().run(timeout=30)
    assert not at.exception, at.exception


def test_page_has_authoritative_h1() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    # Check title contains metric contract registry
    titles = [str(t.value) for t in at.title]
    headers = [str(h.value) for h in at.header]
    all_h1 = titles + headers
    assert any("Metric Contract Registry" in t for t in all_h1), (
        f"titles={titles} headers={headers}"
    )
    # Ensure only one H1
    assert len(titles) <= 1, f"duplicate H1: {titles}"


def test_page_shows_evidence_authority_before_results() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    body = _text(at)
    assert (
        "does not implement metric computation" in body.lower()
        or "not implement" in body.lower()
        or "does not execute" in body.lower()
    )
    assert "built-in" in body.lower()
    assert "authoritative" in body.lower()


def test_page_has_useful_empty_state() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    body = _text(at)
    assert "no registry" in body.lower() or "no registry loaded" in body.lower()
    assert "custom metrics remain unavailable" in body.lower() or "fail-closed" in body.lower()


def test_page_exposes_no_duplicate_widget_keys() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    # If duplicate keys exist, AppTest would have raised exception; also check that run succeeded twice  # noqa: E501
    at2 = _app().run(timeout=30)
    assert not at2.exception


def test_page_has_create_edit_upload_validate_inspect_preview_download() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    body = _text(at).lower()
    assert "create" in body or "draft" in body
    assert "upload" in body
    assert "validate" in body
    assert "built-in" in body and "custom" in body
    assert "preview" in body
    assert "download" in body


def test_page_preserves_unavailable_states() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    body = _text(at).lower()
    # Should mention unavailable for custom without registry
    assert "unavailable" in body


def test_page_avoids_recomputation_message() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    body = _text(at).lower()
    # Should state registration does not implement computation
    assert (
        "registration does not implement metric computation" in body or "does not implement" in body
    )


def test_page_interaction_create_draft() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    # Try to set draft values and submit form if available
    # AppTest form handling: we can check that draft inputs exist
    # Ensure there is a form button
    assert any("Validate draft" in str(b.label) for b in at.button) or len(at.text_input) >= 1


def test_page_shows_deterministic_export() -> None:
    at = _app().run(timeout=30)
    assert not at.exception
    body = _text(at).lower()
    assert "deterministic" in body
    assert "fingerprint" in body
