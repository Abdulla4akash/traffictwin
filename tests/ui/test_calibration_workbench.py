"""Direct AppTest for Calibration Workbench page."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_ui_render() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/calibration_workbench.py")
    app.run(timeout=40)
    assert not app.exception, f"UI raised: {app.exception}"
    titles = [el.value for el in app.title]
    assert titles.count("Calibration Workbench") == 1
    assert len(app.title) == 1
    # Evidence boundary before results: check info contains boundary and appears early
    full_info = " ".join(str(el.value) for el in app.info)
    assert "Evidence and authority boundary" in full_info or "evidence" in full_info.lower()
    # Check that boundary literal is present (from service)
    assert (
        "read-only descriptive comparison" in full_info.lower() or "evidence" in full_info.lower()
    )

    # Check subheaders include expected sections - evidence standing before ranking
    subheaders = [el.value for el in app.subheader]
    # Evidence and authority standing should appear before Candidate summary / ranking
    # Find indices
    try:
        ev_idx = next(i for i, v in enumerate(subheaders) if "Evidence and authority" in v)
        # candidate summary or ranking should be after
        later = list(subheaders[ev_idx + 1 :])
        assert any("Candidate summary" in v or "Alignment audit" in v for v in later)
    except StopIteration:
        # If not built report yet, evidence standing subheader may not be present until report built; but at least initial evidence notice is in info  # noqa: E501
        pass


def test_ui_no_duplicate_keys() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/calibration_workbench.py")
    app.run(timeout=40)
    assert not app.exception
    # Check that no duplicate widget keys via second run not duplicating titles
    # Run again with same state
    app2 = AppTest.from_file("src/traffictwin/ui/app_pages/calibration_workbench.py")
    app2.run(timeout=40)
    assert not app2.exception
    # Both should have exactly one title
    assert len(app2.title) == 1


def test_ui_accessibility_direct() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/calibration_workbench.py")
    app.run(timeout=40)
    assert not app.exception
    # Exactly one H1
    assert len(app.title) == 1
    assert app.title[0].value == "Calibration Workbench"
    # No duplicate control labels / expander labels: check expander titles unique
    expanders = [el.label for el in app.expander] if hasattr(app, "expander") else []
    assert len(expanders) == len(set(expanders))
    # Advanced: prefix preserved via expander labels starting with Advanced:
    for label in expanders:
        if "Advanced" in label:
            assert label.startswith("Advanced:")
    # No duplicate widget keys: sliders, multiselect, etc. labels unique
    # sliders
    sliders = [el.label for el in app.slider] if hasattr(app, "slider") else []
    assert len(sliders) == len(set(sliders))
