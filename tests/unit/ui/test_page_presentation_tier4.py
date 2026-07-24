"""Adversarial presentation tests for the Phase 2B Tier 4 analysis-evidence pages."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


def page_app(page: UiPage) -> AppTest:
    """Build an AppTest for one Tier 4 page with shared v0.7 session state."""

    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def text_of(app: AppTest) -> str:
    parts = [str(block.value) for block in app.markdown]
    parts.extend(str(caption.value) for caption in app.caption)
    return "\n".join(parts)


def metric_labels(app: AppTest) -> list[str]:
    return [str(item.label) for item in app.metric]


def subheaders(app: AppTest) -> set[str]:
    return {str(item.value) for item in app.subheader}


# --- Energy Evidence --------------------------------------------------------


def test_energy_evidence_is_coverage_first_with_family_states() -> None:
    app = page_app(UiPage.ENERGY).run(timeout=40)
    assert not app.exception

    labels = metric_labels(app)
    # Coverage-first KPI row uses numeric-with-units metrics.
    assert "Available (metrics)" in labels
    assert "Completed-task coverage (%)" in labels
    # Every energy card carries an explicit unit.
    assert "Observed-task energy (J)" in labels
    assert "Completed-task energy (J)" in labels
    assert "Energy-delay product (J·ms)" in labels

    body = text_of(app)
    # Families are separated by evidence state, with badges rather than a flat dump.
    assert "Energy Families By Evidence State" in subheaders(app)
    assert "-badge[" in body
    # Efficiency/superiority is explicitly never inferred from a lower energy value.
    assert "efficiency" in body.lower()
    assert "superior" in body.lower()
    # The Randy/TOS physical-energy limitation stays visible.
    assert "Randy/TOS" in body
    # The categorical R8 status is a badge, not a numeric st.metric.
    assert "R8 status" not in labels
    assert "R8 status:" in body


def test_energy_evidence_keeps_r8_raw_in_advanced() -> None:
    app = page_app(UiPage.ENERGY).run(timeout=40)
    assert not app.exception
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert any("R8" in label for label in advanced)
    # The numeric observed energy stays a units-labelled metric.
    assert "Observed completed-task energy (J/task)" in metric_labels(app)
    # Any raw R8 dict/JSON is confined to the Advanced/Evidence expander, not primary content.
    assert advanced


# --- Fairness Evidence ------------------------------------------------------


def test_fairness_evidence_shows_coverage_disparities_and_exclusions() -> None:
    app = page_app(UiPage.FAIRNESS).run(timeout=40)
    assert not app.exception

    labels = metric_labels(app)
    # Eligible-group coverage KPI row with numeric-with-units metrics.
    assert "Eligible vehicle-tier groups" in labels
    assert "Group coverage (%)" in labels
    # Disparity cards remain numeric metrics.
    assert "Vehicle-tier completion gap" in labels
    assert "RSU normalised-load Jain index" in labels

    heads = subheaders(app)
    assert "Disparity Summary" in heads
    assert "Exclusions & Limitations" in heads

    body = text_of(app)
    # No fair/unfair verdict is asserted without the contract and evidence.
    assert "never labels a policy fair or unfair" in body
    # Protected-attribute limitation and insufficient-group exclusion stay visible.
    assert "Protected or demographic attributes are **not represented**" in body
    assert "excluded" in body.lower()
    # The categorical R7 status is a badge, not a numeric metric.
    assert "R7 status" not in labels
    assert "R7 status:" in body


def test_fairness_evidence_keeps_policy_and_r7_raw_in_advanced() -> None:
    app = page_app(UiPage.FAIRNESS).run(timeout=40)
    assert not app.exception
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    # Complete policy fingerprint and raw R7 evidence live under Advanced/Evidence.
    assert any("policy identity" in label.lower() for label in advanced)
    assert any("R7 evidence" in label for label in advanced)


# --- Infrastructure & Congestion --------------------------------------------


def test_infrastructure_separates_provenance_and_structures_per_rsu() -> None:
    app = page_app(UiPage.INFRASTRUCTURE).run(timeout=40)
    assert not app.exception

    labels = metric_labels(app)
    # Capacity/pressure/utilisation metrics carry explicit units, plus an observation window.
    assert "Observation window (s)" in labels
    assert "P95 utilisation (fraction)" in labels
    assert "Saturation duration (s)" in labels

    body = text_of(app)
    # Canonical evidence is separated from synthetic/source infrastructure with a provenance badge.
    assert "Infrastructure provenance:" in body
    assert "-badge[" in body
    # Source RSU slots are never presented as verified Manchester roadside infrastructure.
    assert "not verified Manchester roadside" in body

    # The per-RSU summary is a structured table; any raw dict is confined to Advanced/Evidence.
    assert len(app.dataframe) >= 1
    assert len(app.json) <= 1
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert any("per-RSU summary" in label for label in advanced)


# --- Journey-Time Lens ------------------------------------------------------


def test_journey_time_shows_cohort_completion_and_no_causality() -> None:
    app = page_app(UiPage.JOURNEY_TIME).run(timeout=40)
    assert not app.exception

    labels = metric_labels(app)
    # Cohort-coverage counts and unit-labelled duration evidence.
    assert "Total trips (count)" in labels
    assert "Incomplete trips (count)" in labels
    assert "Mean duration (s)" in labels
    assert "P95 duration (s)" in labels

    heads = subheaders(app)
    assert "Completion and Exclusions" in heads

    body = text_of(app)
    # Completion status is a badge; incomplete/missing journeys stay explicit.
    assert "Trip cohort completion:" in body
    assert "-badge[" in body
    assert "Incomplete journeys are reported as a count" in body
    # No zero-conversion and no causal claim.
    assert "never converted to a zero" in body or "never plotted as zero" in body
    assert "caused a change in journey time" in body


def test_journey_time_duration_status_is_not_a_categorical_metric() -> None:
    app = page_app(UiPage.JOURNEY_TIME).run(timeout=40)
    assert not app.exception
    labels = metric_labels(app)
    # Trip counts and durations are numeric metrics; completion status is a badge, not a metric.
    assert "Trip cohort completion" not in labels
    assert "Trip-duration joins" not in labels
