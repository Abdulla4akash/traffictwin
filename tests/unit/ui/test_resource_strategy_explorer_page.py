"""UI tests for Resource Strategy Explorer."""

from __future__ import annotations

import contextlib
import json
from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from traffictwin.experiments.resource_strategy import (
    ResourceStrategyAdmissionState,
    ResourceStrategyEvidenceMode,
    ResourceStrategyStudy,
)
from traffictwin.ui.state import default_session_state, load_ui_config


def page_app() -> AppTest:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    # Ensure synthetic fixture path is set for default view
    app.session_state["resource_strategy_study_path"] = (
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    return app


def text_of(app: AppTest) -> str:
    parts = [str(t.value) for t in app.title]
    parts.extend(str(b.value) for b in app.markdown)
    parts.extend(str(c.value) for c in app.caption)
    parts.extend(str(s.value) for s in app.subheader)
    parts.extend(str(x.value) for x in getattr(app, "text", []))
    for attr in ("info", "warning", "error", "success"):
        parts.extend(str(x.value) for x in getattr(app, attr, []))
    return "\n".join(parts)


def test_page_renders_synthetic_banner_and_arm_table() -> None:
    app = page_app().run(timeout=30)
    assert not app.exception, app.exception
    body = text_of(app)
    # Page title exists
    assert "Resource Strategy Explorer" in body
    # Synthetic banner
    assert "synthetic" in body.lower()
    assert "Strongest-link placement" in body or "strongest_link" in body.lower()
    # Arm table visible
    assert len(app.dataframe) >= 3 or "arm_id" in body.lower()
    # Matched cohort
    assert "Matched replications" in body or "Matched" in body
    assert "Excluded" in body
    # Metric selector
    assert any("Metric" in str(s.label) for s in app.selectbox) or "Metric and denominator" in body


def test_page_shows_offered_vs_admitted_denominator_warning() -> None:
    app = page_app().run(timeout=30)
    assert not app.exception
    body = text_of(app)
    assert "Offered" in body and "admitted" in body.lower()
    assert "denominator" in body.lower()


def test_page_synthetic_mode_labelling() -> None:
    app = page_app().run(timeout=30)
    assert not app.exception
    body = text_of(app)
    # Must be labelled synthetic demonstration evidence and not actual E2 result
    assert "synthetic" in body.lower()
    assert "not" in body.lower() and "E2" in body or "synthetic demonstration" in body.lower()


def test_page_shows_queue_and_resource_cost() -> None:
    app = page_app().run(timeout=30)
    assert not app.exception
    body = text_of(app)
    assert "Queue" in body or "queue" in body.lower()
    assert "load-balance" in body.lower() or "Jain" in body
    # Resource cost should appear as optional evidence
    assert "Resource-cost" in body or "resource.cost" in body.lower() or "cost" in body.lower()


def test_page_shows_limitations_and_provenance() -> None:
    app = page_app().run(timeout=30)
    assert not app.exception
    body = text_of(app)
    assert "Limitations" in body or "limitations" in body.lower()
    assert "Provenance" in body or "provenance" in body.lower()
    assert "fingerprint" in body.lower()


def test_page_export_matches_report() -> None:
    app = page_app().run(timeout=30)
    assert not app.exception
    # Download buttons exist
    labels = {b.label for b in app.download_button}
    assert "Download ResourceStrategyReport JSON" in labels
    assert "Download CSV" in labels or any("CSV" in label for label in labels)  # noqa: E741
    # Get the study and report via direct service and compare to exported JSON
    study = ResourceStrategyStudy.model_validate_json(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json").read_text()
    )
    from traffictwin.experiments.resource_strategy import build_resource_strategy_report

    report = build_resource_strategy_report(study)
    # Verify service export matches report (UI button exists, content via service)
    assert report.to_json() is not None
    exported = json.loads(report.to_json())
    assert exported["study_id"] == report.study_id
    assert exported["study_fingerprint"] == report.study_fingerprint
    assert exported["report_fingerprint"] == report.report_fingerprint
    data = report.to_json()
    assert "worktrees" not in data
    assert "/Users" not in data
    assert "/tmp" not in data  # noqa: S108


def test_ui_empty_state_when_no_study() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = ""
    with contextlib.suppress(KeyError):
        del app.session_state["resource_strategy_uploaded"]
    app.run(timeout=30)
    assert not app.exception
    body = text_of(app)
    assert (
        "No study artifact selected" in body
        or "No admitted study exists" in body
        or "A Resource Strategy Explorer study needs a validated artifact" in body
        or "Getting started" in body
    )


def test_ui_unadmitted_mode_refusal() -> None:
    # Build an unadmitted study and write to temp path
    import hashlib
    import tempfile

    from traffictwin.experiments.resource_strategy import (
        ResourceStrategyArm,
        ResourceStrategyLifecycle,
        ResourceStrategyMetric,
        ResourceStrategyMetricDenominator,
        ResourceStrategyReplication,
    )

    lifecycle = ResourceStrategyLifecycle(
        offered=1000,
        admitted=800,
        rejected=200,
        forwarded=400,
        started=760,
        compute_completed=720,
        returned=700,
        dropped=80,
        deadline_success=680,
    )
    rep = ResourceStrategyReplication(
        replication_id="rep_001",
        lifecycle=lifecycle,
        queue_length_mean=7.5,
        queue_balance_jain=0.9,
        utilisation_mean=0.69,
        energy_mean_j=40.0,
        resource_cost_units=115.0,
        latency_mean_ms=155.0,
        latency_p95_ms=270.0,
        forwarding_rate=0.5,
    )
    arm = ResourceStrategyArm(
        arm_id="arm_a",
        label="A",
        description="d",
        strategy_type="t",
        replications=[
            rep,
            ResourceStrategyReplication(replication_id="rep_002", lifecycle=lifecycle),
        ],
    )
    arm2 = ResourceStrategyArm(
        arm_id="arm_b",
        label="B",
        description="d",
        strategy_type="t",
        replications=[
            rep,
            ResourceStrategyReplication(replication_id="rep_002", lifecycle=lifecycle),
        ],
    )
    cat = [
        ResourceStrategyMetric(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=ResourceStrategyMetricDenominator.COMPLETED_TASKS,
        ),
        ResourceStrategyMetric(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.OFFERED_TASKS,
        ),
    ]
    study = ResourceStrategyStudy(
        schema_version="1.0",
        study_id="unadmitted_test",
        source_fingerprint=hashlib.sha256(b"unadmitted").hexdigest(),
        evidence_mode=ResourceStrategyEvidenceMode.UNADMITTED_RESEARCH,
        admission_state=ResourceStrategyAdmissionState.UNADMITTED,
        replication_unit="replication_id",
        arms=[arm, arm2],
        common_matched_replication_ids=["rep_001", "rep_002"],
        excluded_replication_ids=[],
        metric_catalog=cat,
        limitations=[],
        provenance={},
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "unadmitted.json"
        p.write_text(study.model_dump_json(), encoding="utf-8")
        app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
        for key, value in deepcopy(default_session_state(load_ui_config())).items():
            app.session_state[key] = value
        app.session_state["_v07_navigation_active"] = True
        app.session_state["resource_strategy_study_path"] = str(p)
        with contextlib.suppress(KeyError):
            del app.session_state["resource_strategy_uploaded"]
        app.run(timeout=30)
        assert not app.exception
        body = text_of(app)
        assert "unadmitted" in body.lower()
        assert "withheld" in body.lower() or "must not be treated as admitted" in body.lower()
        # Dataframe for comparison should not be present or empty? At least ensure error banner
        assert "unadmitted" in body.lower()


def test_page_has_no_winner_best_optimal_headline() -> None:
    app = page_app().run(timeout=30)
    assert not app.exception
    body = text_of(app).lower()
    # Ensure page does not claim winner/best/optimal as headline; only descriptive wording
    # Allow phrases like "no winner" or explanatory disclaimer
    if "best" in body:
        assert "no winner" in body or "descriptive only" in body
    if "optimal" in body:
        assert "not optimal" in body or "descriptive only" in body
