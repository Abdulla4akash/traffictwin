"""AppTests for the four additive read-only post-v1 Platform Console routes."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.platform.analytics_monitor import (
    AnalyticsOperationalPolicy,
    DataQualityReport,
    LocalQualityReportStore,
    QualityObservation,
)
from traffictwin.ui.platform_console_services import ANALYTICS_REPORTS_RELATIVE
from traffictwin.ui.state import default_session_state, load_ui_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_BASE = "https://github.com/Abdulla4akash/traffictwin/blob/main/docs/"
_LABEL_KINDS = ("button", "checkbox", "selectbox", "multiselect", "text_input")


def _app(monkeypatch: MonkeyPatch, workspace: Path, script: str) -> Any:  # noqa: ANN401
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/app_pages/{script}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _tables(app: Any) -> str:  # noqa: ANN401
    return " ".join(frame.value.to_csv(index=False) for frame in app.dataframe)


def _text(app: Any) -> str:  # noqa: ANN401
    collections = (
        app.title,
        app.subheader,
        app.markdown,
        app.caption,
        app.info,
        app.warning,
        app.success,
    )
    rendered = [str(item.value) for collection in collections for item in collection]
    rendered.extend(f"{item.label} {item.value}" for item in app.metric)
    rendered.extend(str(item.label) for item in app.expander)
    return " ".join(rendered)


def _assert_labels_unique(app: Any) -> None:  # noqa: ANN401
    for kind in _LABEL_KINDS:
        labels = [str(element.label).strip().lower() for element in getattr(app, kind)]
        assert all(labels)
        assert len(labels) == len(set(labels)), f"duplicate {kind} labels: {labels}"


def _snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _quality_report(*, unsafe_scope: str | None = None) -> DataQualityReport:
    policy = AnalyticsOperationalPolicy()
    return DataQualityReport(
        accepted=("safe-aggregate-001",),
        warned=(
            QualityObservation(
                rule="source_stale",
                rule_version="2.0",
                scope=unsafe_scope or "safe-aggregate-001",
                measured="35.0 minutes old >= 30-minute warning",
                severity="warning",
                source_sha256="a" * 64,
                support=15,
            ),
        ),
        refused=(
            QualityObservation(
                rule="session_overlap",
                rule_version="2.0",
                scope="safe-aggregate-002",
                measured="overlap retained as an operational refusal",
                severity="refusal",
                source_sha256="b" * 64,
            ),
        ),
        not_observed=("progression unavailable — no segments; not a zero",),
        informational=(
            QualityObservation(
                rule="session_completeness",
                rule_version="2.0",
                scope="safe-aggregate-001",
                measured="1.000 (15/15); missing=0",
                severity="info",
                source_sha256="a" * 64,
                support=15,
            ),
        ),
        standing_note=(
            "operational severity only, never scientific confidence; forecast-readiness is not "
            "forecast validity"
        ),
        generated_at_utc=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        operational_policy_digest=policy.digest(),
        notification_surface=("local_dashboard", "local_report_receipt"),
        retention_policy="indefinite; no automatic deletion",
    )


def _publish_quality_report(workspace: Path, *, unsafe_scope: str | None = None) -> None:
    policy = AnalyticsOperationalPolicy()
    store = LocalQualityReportStore(workspace / ANALYTICS_REPORTS_RELATIVE)
    store.publish(_quality_report(unsafe_scope=unsafe_scope), policy)


def test_analytics_empty_state_is_explicit_and_writes_nothing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    app = _app(monkeypatch, workspace, "platform_analytics.py").run(timeout=20)
    assert not app.exception
    rendered = _text(app)
    assert "Analytics Quality" in rendered
    assert "NOT SCIENTIFIC CONFIDENCE" in rendered
    assert "absent reports and observations are never displayed as zero" in rendered
    assert not workspace.exists()
    _assert_labels_unique(app)


def test_analytics_feed_renders_rules_support_digests_and_is_read_only(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    _publish_quality_report(workspace)
    before = _snapshot(workspace)
    app = _app(monkeypatch, workspace, "platform_analytics.py").run(timeout=20)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "Immutable report feed" in rendered
    assert "source_stale" in rendered
    assert "session_overlap" in rendered
    assert "support" in rendered
    assert "progression unavailable" in rendered
    assert "evidence" in rendered.lower()
    assert _snapshot(workspace) == before
    _assert_labels_unique(app)


def test_analytics_private_report_fails_closed_without_echoing_the_path(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    _publish_quality_report(workspace, unsafe_scope="/Users/private/source")
    app = _app(monkeypatch, workspace, "platform_analytics.py").run(timeout=20)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "Analytics quality unavailable" in rendered
    assert "/Users/private/source" not in rendered


def test_evidence_matrix_default_keeps_non_admitted_separate_and_links_sources(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    app = _app(monkeypatch, workspace, "platform_evidence_matrix.py").run(timeout=30)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "Evidence Matrix" in rendered
    assert "NO META-ANALYSIS" in rendered
    assert "bbus-sparse64-clean-rerun" in rendered
    assert "admitted_with_execution_deviation" in rendered
    assert "bbus-sparse64-homecoming" in rendered
    assert "NON_ADMITTED_SEPARATE_VIEW" in rendered
    assert "vec-fleet-composition-prediction" in rendered
    assert "proposed" in rendered
    assert SOURCE_BASE in rendered
    assert "producer_citation_requirements.md" in rendered
    assert not workspace.exists()
    _assert_labels_unique(app)


def test_analytics_credential_token_fails_closed_without_echo(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    token = "-".join(("sk", "examplecredential123456789"))
    _publish_quality_report(workspace, unsafe_scope=token)
    app = _app(monkeypatch, workspace, "platform_analytics.py").run(timeout=30)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "PRIVATE_CONTENT_REFUSED" in rendered
    assert token not in rendered


def test_evidence_matrix_non_admitted_toggle_never_promotes_standing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace", "platform_evidence_matrix.py")
    app.run(timeout=30)
    checkbox = next(
        item for item in app.checkbox if item.label == "Include the separate NON_ADMITTED view"
    )
    checkbox.set_value(True).run(timeout=30)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "bbus-sparse64-homecoming" in rendered
    assert "non_admitted" in rendered
    assert "NON_ADMITTED included: `true`" in rendered


def test_observatory_preserves_coherence_deviation_limits_and_citations(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    app = _app(monkeypatch, workspace, "platform_observatory.py").run(timeout=30)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "Mechanism Observatory" in rendered
    assert "NO CAUSAL DIAGNOSIS" in rendered
    assert "-8,310.9" in rendered
    assert "p=0.0625" in rendered
    assert "effectively flat" in rendered
    assert "already-failed" in rendered
    assert "bit-identical" in rendered
    assert "admitted_with_execution_deviation" in rendered
    assert "first complete archive was overwritten" in rendered
    assert "producer_citation_requirements.md" in rendered
    assert SOURCE_BASE in rendered
    assert "globally optimal" not in rendered.lower()
    assert "validated policy" not in rendered.lower()
    assert not workspace.exists()
    _assert_labels_unique(app)


def test_observatory_appendix_is_explicitly_non_admitted(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace", "platform_observatory.py")
    app.run(timeout=30)
    checkbox = next(
        item for item in app.checkbox if item.label == "Include the separate NON_ADMITTED appendix"
    )
    checkbox.set_value(True).run(timeout=30)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "Earlier Sparse-64 147-repeat return — NON_ADMITTED appendix" in rendered
    assert "never join admitted views" in rendered


def test_decision_safety_shows_bounded_advice_and_non_executable_draft(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    app = _app(monkeypatch, workspace, "platform_decision_safety.py").run(timeout=30)
    assert not app.exception
    rendered = _text(app) + _tables(app)
    assert "Decision Safety" in rendered
    assert "NO EXECUTION AUTHORITY" in rendered
    assert "cap-0.75, cap-2.5-reference" in rendered
    assert "Metric winner(s):** cap-0.75" in rendered
    assert "within this measured comparison only" in rendered
    assert "not an overall-service ranking" in rendered
    assert "p=0.0625" in rendered
    assert "executable" in rendered
    assert "False" in rendered
    assert "creates new evidence" in rendered.lower()
    assert "none was asserted" in rendered
    assert SOURCE_BASE in rendered
    assert "globally optimal" not in rendered.lower()
    assert "proven safest" not in rendered.lower()
    assert not workspace.exists()
    _assert_labels_unique(app)


def test_console_sources_have_no_mutation_or_external_call_surface() -> None:
    paths = (
        REPO_ROOT / "src" / "traffictwin" / "ui" / "platform_console_services.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "pages" / "platform_analytics.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "pages" / "platform_evidence_matrix.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "pages" / "platform_observatory.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "pages" / "platform_decision_safety.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "subprocess",
        "urlopen",
        "requests.",
        "httpx.",
        ".write_text(",
        ".write_bytes(",
        "def run(",
        "def execute(",
        "def approve(",
        "def admit(",
    ):
        assert forbidden not in source
