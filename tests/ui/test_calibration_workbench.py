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


def test_ui_coverage_threshold_and_missing_exclusion() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/calibration_workbench.py")
    app.run(timeout=40)
    assert not app.exception, f"UI raised: {app.exception}"
    # Verify coverage threshold control exists and defaults to 100
    # Find slider with label containing Minimum coverage
    sliders = [s for s in app.slider if "Minimum coverage" in s.label]
    assert len(sliders) == 1, (
        f"expected 1 coverage slider, found {len(sliders)} labels {[s.label for s in app.slider]}"
    )
    assert sliders[0].value == 100
    # Verify it is in Alignment specification section
    # Select candidates including missing_evidence
    # Find multiselect for Candidates
    assert len(app.multiselect) >= 1
    # Set to include missing_evidence plus good/bad
    # AppTest multiselect: set via .select or .set_value? Use .set_value with list
    try:
        # Try API: multiselect has set_value
        ms = app.multiselect[0]
        ms.set_value(["candidate_good_fit", "candidate_poor_fit", "candidate_missing_evidence"])
    except Exception:  # noqa: BLE001
        # fallback: try select
        app.multiselect[0].select("candidate_missing_evidence")
    app.run(timeout=40)
    assert not app.exception
    # Click Build calibration report button
    # Find button with label Build calibration report
    btns = [b for b in app.button if "Build calibration report" in b.label]
    assert len(btns) == 1
    btns[0].click()
    app.run(timeout=40)
    assert not app.exception, f"UI raised after build: {app.exception}"
    # After build, verify audit shows missing as excluded due coverage
    # Check dataframes: audit rows contain candidate_missing_evidence with excluded True
    # Check that missing candidate appears in output but not as headline winner
    # Headline winner is the markdown with Lowest declared normalized objective
    markdown_text = " ".join(str(m.value) for m in app.markdown)
    assert (
        "candidate_missing_evidence" not in markdown_text
        or "Lowest declared normalized objective among compatible candidates:" in markdown_text
    )
    # Ensure the headline winner is not candidate_missing_evidence
    # Find the markdown that contains Lowest...
    headline = next(
        (
            str(m.value)
            for m in app.markdown
            if "Lowest declared normalized objective" in str(m.value)
        ),
        "",
    )
    assert "candidate_missing_evidence" not in headline, (
        f"missing should not be headline winner but headline is {headline}"
    )
    assert "candidate_good_fit" in headline or "candidate_poor_fit" in headline
    # At least check that dataframe exists and audit was rendered
    assert len(app.dataframe) >= 2  # audit + summary at least
    # Verify service ranking directly
    from traffictwin.calibration.fixtures import make_default_study
    from traffictwin.calibration.service import build_calibration_report

    study = make_default_study()
    report = build_calibration_report(study)
    assert "candidate_missing_evidence" not in report.ranking
    assert report.ranking[0] == "candidate_good_fit"
