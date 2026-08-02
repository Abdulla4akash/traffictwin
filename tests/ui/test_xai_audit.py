"""AppTests for the synthetic, read-only XAI Decision Audit route."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from traffictwin.platform.xai_instrumentation import (
    SYNTHETIC_ACTOR_CONTRACT_DIGEST,
    SYNTHETIC_CHECKPOINT_DIGEST,
)
from traffictwin.ui.state import default_session_state, load_ui_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "src/traffictwin/ui/app_pages/platform_xai_audit.py"


def _app() -> Any:  # noqa: ANN401
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(SCRIPT)
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


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
    rendered.extend(frame.value.to_csv(index=False) for frame in app.dataframe)
    return " ".join(rendered)


def _source_hashes() -> dict[str, str]:
    return {
        relative: hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in (
            "docs/research_directions_v2.md",
            "docs/producer_citation_requirements.md",
        )
    }


def test_decision_audit_renders_exact_bindings_synthetic_shapes_and_unavailable_states() -> None:
    app = _app().run(timeout=30)
    assert not app.exception
    rendered = _text(app)
    assert "Decision Audit" in rendered
    assert "SYNTHETIC FIXTURE" in rendered
    assert "NOT CAUSAL" in rendered
    assert "REAL ATTRIBUTION UNAVAILABLE" in rendered
    assert "synthetic_policy_fixture" in rendered
    assert SYNTHETIC_ACTOR_CONTRACT_DIGEST in rendered
    assert SYNTHETIC_CHECKPOINT_DIGEST in rendered
    assert "always_local" in rendered
    assert "lyapunov_queue_aware" in rendered
    assert "shap_shaped_synthetic_fixture" in rendered
    assert "integrated_gradients_shaped_synthetic_fixture" in rendered
    assert "Faithfulness validated: false" in rendered
    assert "producer_snapshot_hook" in rendered
    assert "authorised_model_access" in rendered
    assert "validated_application_method" in rendered
    assert "zero substituted" in rendered.lower()


def test_disagreement_browser_filters_without_changing_standing() -> None:
    app = _app().run(timeout=30)
    checkbox = next(item for item in app.checkbox if item.label == "Show policy disagreements only")
    checkbox.set_value(True).run(timeout=30)
    selectbox = next(item for item in app.selectbox if item.label == "Recorded action filter")
    selectbox.set_value("v2i").run(timeout=30)
    assert not app.exception
    rendered = _text(app)
    assert "immutable rows" in rendered
    assert "descriptive action difference" in rendered
    assert "A difference does not identify a correct action" in rendered
    disagreement_table = app.dataframe[1].value
    assert disagreement_table["disagreement"].all()
    assert set(disagreement_table["recorded action"]) == {"v2i"}
    assert not disagreement_table["correct action identified"].any()


def test_decision_audit_is_read_only_and_source_links_are_digest_bound() -> None:
    before = _source_hashes()
    app = _app().run(timeout=30)
    assert not app.exception
    assert _source_hashes() == before
    rendered = _text(app)
    assert "docs/research_directions_v2.md" in rendered
    assert "docs/producer_citation_requirements.md" in rendered
    assert "exact repository bytes; project context only" in rendered
    assert "citation_metadata_only" in rendered
    assert (
        "Literature evidence, project measurements and synthetic fixture output remain separate"
        in rendered
    )


def test_decision_audit_has_unique_filters_and_no_action_or_file_controls() -> None:
    app = _app().run(timeout=30)
    assert not app.exception
    assert [item.label for item in app.checkbox] == ["Show policy disagreements only"]
    assert [item.label for item in app.selectbox] == ["Recorded action filter"]
    assert not app.button
    assert not app.file_uploader
    assert not app.text_input
    assert not app.text_area


def test_decision_audit_source_has_no_write_network_model_loader_or_execution_surface() -> None:
    paths = (
        REPO_ROOT / "src" / "traffictwin" / "ui" / "xai_services.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "pages" / "platform_xai_audit.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "requests.",
        "httpx.",
        "urlopen",
        "subprocess",
        "torch.load",
        "importlib.import_module",
        ".write_text(",
        ".write_bytes(",
        "def execute(",
        "def approve(",
        "def admit(",
    ):
        assert forbidden not in source
