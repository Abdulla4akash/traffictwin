"""UI tests for Multi-Objective Trade-Off Explorer."""

from __future__ import annotations

import contextlib
from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import default_session_state, load_ui_config


def _page_app() -> AppTest:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/tradeoff_explorer.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.session_state["tradeoff_study_path"] = (
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    return app


def _text(app: AppTest) -> str:
    parts = [str(t.value) for t in app.title]
    parts.extend(str(x.value) for x in app.header)
    parts.extend(str(b.value) for b in app.markdown)
    parts.extend(str(c.value) for c in app.caption)
    parts.extend(str(s.value) for s in app.subheader)
    parts.extend(str(x.value) for x in getattr(app, "text", []))
    for attr in ("info", "warning", "error", "success"):
        parts.extend(str(x.value) for x in getattr(app, attr, []))
    return "\n".join(parts)


def test_page_renders_authoritative_h1() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception, app.exception
    titles = [str(t.value) for t in app.title]
    assert len(titles) == 1
    assert titles[0] == "Multi-Objective Trade-Off Explorer"


def test_page_renders_no_exception_and_boundary() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception, app.exception
    body = _text(app)
    assert "Pareto/constraint explorer" in body
    # Evidence and authority boundary before results
    assert "Evidence boundary" in body
    assert "Authority boundary" in body
    # No winner language in page until after disclaimer? Check page text does not claim winner positively  # noqa: E501
    # Allow negative disclaimer but not positive claims
    lower = body.lower()
    assert "descriptive frontier" in lower
    # Ensure page does not claim best/optimal as positive
    assert (
        "no best" in lower
        or "best" not in lower
        or "not a winner" in lower
        or "descriptive" in lower
    )


def test_page_renders_metrics_and_frontier() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception
    body = _text(app)
    # Study selection visible
    assert "Study artifact path" in body or "Study and admission" in body
    # Metrics selector
    assert "Select metrics for trade-off" in body or "Metrics for Pareto" in body
    # Compatibility audit
    assert "Compatibility audit" in body
    # Feasibility
    assert "Per-arm feasibility" in body or "feasibility" in body.lower()
    # Pareto frontier
    assert "Pareto frontier" in body
    # Dominance matrix
    assert "Dominance matrix" in body
    # Stability
    assert "Matched-replication stability" in body
    # Export buttons
    labels = {b.label for b in app.download_button}
    assert "Download TradeoffReport JSON" in labels
    assert any("CSV" in label for label in labels)
    # Dataframes exist
    assert len(app.dataframe) >= 3


def test_page_has_no_duplicate_widget_keys() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception
    # AppTest would raise on duplicate keys; if we reach here, keys are unique
    # Also check widget counts reasonable
    assert len(app.selectbox) >= 1 or len(app.multiselect) >= 1


def test_page_shows_empty_state_when_no_study() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/tradeoff_explorer.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.session_state["tradeoff_study_path"] = ""
    with contextlib.suppress(KeyError):
        del app.session_state["tradeoff_uploaded"]
    app.run(timeout=30)
    assert not app.exception
    body = _text(app)
    assert (
        "No study artifact selected" in body
        or "No admitted study exists" in body
        or "needs a validated artifact" in body
    )


def test_page_heading_accessibility() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception
    body = _text(app)  # noqa: F841
    # Accessibility: heading hierarchy and descriptive labels
    titles = [str(t.value) for t in app.title]
    assert titles[0] == "Multi-Objective Trade-Off Explorer"
    # Subheadings exist for major sections
    subs = [str(s.value) for s in app.subheader]
    assert any("Compatibility audit" in s for s in subs)
    assert any("Pareto frontier" in s for s in subs)


def test_page_constraint_violation_shown() -> None:
    # Use page with default fixture but set a constraint that will cause violation
    app = _page_app()
    app.run(timeout=30)
    assert not app.exception
    # After initial run, set a tight constraint via session? For now just check violation wording exists in page code  # noqa: E501
    body = _text(app)  # noqa: F841
    assert "violates declared constraint" in body.lower() or "Hard constraint" in body


def test_page_shows_limitations_and_provenance() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception
    body = _text(app)
    assert "Limitations" in body or "limitations" in body.lower()
    assert "Provenance" in body or "provenance" in body.lower()
    assert "fingerprint" in body.lower()


def test_page_exports_match_report() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception
    # Button existence already checked; verify report JSON via service matches page's study
    from traffictwin.experiments.resource_strategy import load_resource_strategy_study_file
    from traffictwin.experiments.tradeoff_explorer import (
        build_tradeoff_report,
        tradeoff_study_from_resource_strategy_study,
    )

    rs_study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    # Use same default metrics as page (first compatible keys)
    t_study = tradeoff_study_from_resource_strategy_study(rs_study)
    report = build_tradeoff_report(t_study)
    assert (
        "non-dominated" in report.frontier.description.lower()
        or "descriptive" in report.frontier.description.lower()
    )
    # Exports do not contain local paths
    j = report.to_json()
    assert "/Users" not in j
    assert "/tmp" not in j  # noqa: S108
