"""AppTests for Manchester Source Operations page (Lane 14)."""

from __future__ import annotations

import pathlib
import tempfile

from streamlit.testing.v1 import AppTest


def _run_page(path: str) -> AppTest:
    at = AppTest.from_file(path, default_timeout=30)
    at.run()
    return at


def _run_pages_render() -> AppTest:
    tmp = pathlib.Path(tempfile.mkdtemp())
    runner = tmp / "runner.py"
    runner.write_text(
        "from traffictwin.ui.pages.manchester_source_operations import render\nrender()\n",
        encoding="utf-8",
    )
    at = AppTest.from_file(str(runner), default_timeout=30)
    at.run()
    return at


def test_manchester_source_operations_page_renders() -> None:
    at = _run_pages_render()
    assert not at.exception, f"Page raised: {at.exception}"
    titles = [str(t.value) for t in at.title]
    assert any("Manchester Source Operations" in t for t in titles), f"titles: {titles}"
    captions = [str(c.value) for c in at.caption]
    all_text = " ".join(
        captions + [str(x.value) for x in at.markdown] + [str(x.value) for x in at.subheader]
    )
    assert "BODS" in all_text or "bus" in all_text.lower()
    subheaders = [str(s.value) for s in at.subheader]
    assert any("Source operations" in s for s in subheaders)
    assert any("Quality" in s or "coverage" in s.lower() for s in subheaders)


def test_manchester_source_operations_app_page_renders() -> None:
    at = _run_page("src/traffictwin/ui/app_pages/manchester_source_operations.py")
    assert not at.exception, f"App page raised: {at.exception}"
    titles = [str(t.value) for t in at.title]
    assert any("Manchester Source Operations" in t for t in titles)


def test_manchester_source_operations_shows_all_families_and_contracts() -> None:
    at = _run_pages_render()
    assert not at.exception
    assert len(at.dataframe) >= 2, f"expected at least 2 dataframes, got {len(at.dataframe)}"
    expander_labels = [str(e.label) for e in at.expander]
    assert len(expander_labels) >= 8
    all_markdown = " ".join(
        [str(m.value) for m in at.markdown] + [str(c.value) for c in at.caption]
    )
    assert (
        "CAN infer" in all_markdown or "can_infer" in all_markdown.lower() or "Bus" in all_markdown
    )
    assert "CANNOT" in all_markdown or "cannot_infer" in all_markdown.lower()
    all_values = " ".join(
        [str(t.value) for t in at.title]
        + [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
        + [str(e.label) for e in at.expander]
    )
    assert "/Users/" not in all_values
    assert "/private/" not in all_values
    assert "/tmp/" not in all_values  # noqa: S108
    assert "Bearer" not in all_values
    assert (
        "api_key" not in all_values.lower()
        or "api_key" in all_values.lower()
        and "api_key" not in all_values
    )
    assert (
        "PROVIDER_DATA_REQUIRED" in all_values
        or "provider-data-required" in all_values.lower()
        or "TfGM" in all_values
    )
    assert "bus" in all_values.lower()


def test_manchester_source_operations_no_composite_score() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join(
        [str(t.value) for t in at.title]
        + [str(s.value) for s in at.subheader]
        + [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
    ).lower()
    assert "quality_score" not in all_text
    assert "composite_score" not in all_text
    if "quality score" in all_text:
        assert "not combined" in all_text
    if "composite" in all_text:
        assert "not combined" in all_text or "no composite" in all_text
    assert "missingness" in all_text or "duplicate" in all_text


def test_manchester_source_operations_demonstrator_never_claims_credentials() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join(
        [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
        + [str(t.value) for t in at.title]
    )
    assert "CREDENTIAL_REQUIRED" in all_text or "credential-required" in all_text.lower()
    assert "sk-" not in all_text
    assert "Bearer " not in all_text


def test_manchester_source_operations_unavailable_markers_and_exact_denominators() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join(
        [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
        + [str(s.value) for s in at.subheader]
    )
    # Unavailable marker must be rendered as — with explicit unavailable text
    assert "—" in all_text
    assert "unavailable" in all_text.lower() or "not measured" in all_text.lower()
    # Denominator semantics must be explicit (rows unit) and no snapshot/row mix
    low = all_text.lower()
    assert "rejected_rate" in low or "rejected" in low
    assert "rows" in low
    assert "latest exact pointer" in low or "aggregation" in low.lower()
    # Dataframe must show — for total_expected/present/missing etc.
    # Check that at least one dataframe contains — in its values
    found_dash = False
    for df in at.dataframe:
        # AppTest Dataframe.value is pandas.DataFrame; to_string() always returns str
        val_str = df.value.to_string()
        if "—" in val_str:
            found_dash = True
    assert found_dash, "quality dataframe should contain unavailable marker —"
    # Ensure screened error not leaking exception payload: trigger no
    # exception, but check message code
    # The page should show lane-local reachability text
    assert (
        "not registered in shared navigation" in all_text.lower()
        or "lane-local" in all_text.lower()
    )


def test_manchester_source_operations_no_default_zero_for_unmeasured() -> None:
    """Unmeasured components must be — not 0 in dataframe."""

    at = _run_pages_render()
    assert not at.exception
    # Find quality dataframe (second one)
    assert len(at.dataframe) >= 2
    # The quality dataframe is the second; check its columns for unavailable
    # At least total_expected, missingness, duplicate should be —
    for df in at.dataframe:
        # AppTest Dataframe.value is pandas.DataFrame; to_dict() always returns dict
        s = str(df.value.to_dict())
        if "total_expected" in s or "missingness" in s:
            assert "—" in s, f"expected unavailable marker in {s[:500]}"


def test_manchester_source_operations_navigation_not_registered() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join([str(c.value) for c in at.caption] + [str(m.value) for m in at.markdown])
    assert (
        "parent reconciliation deferred" in all_text.lower()
        or "reconciliation deferred" in all_text.lower()
    )
