"""AppTests for the read-only Manchester Gate-D integration page."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from traffictwin.integration.manchester.owner_candidate_contracts import (
    comparison_contract_fingerprint,
)
from traffictwin.ui.manchester_gate_d_services import SOURCE_REFS
from traffictwin.ui.state import default_session_state, load_ui_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "src/traffictwin/ui/app_pages/manchester_gate_d.py"


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
        for relative in SOURCE_REFS
    }


def test_gate_d_page_renders_mapping_profile_contract_and_lineage_truth() -> None:
    app = _app().run(timeout=30)
    assert not app.exception
    rendered = _text(app)
    assert "Manchester Gate-D" in rendered
    assert "FOUNDATION ONLY" in rendered
    assert "OWNER-APPROVED CANDIDATE CEILING" in rendered
    assert "NO REAL COMPARISON" in rendered
    assert "305" in rendered
    assert "131" in rendered
    assert "165" in rendered
    assert "no_suitable_candidate" in rendered
    assert "39,072" in rendered or "39072" in rendered
    assert "GA-DFT-1" in rendered
    assert "GA-WT-1" in rendered
    assert comparison_contract_fingerprint() in rendered
    assert "candidate_unregistered" in rendered
    assert "baseline accepted: false" in rendered.lower()
    assert "observed_simulated_comparison" in rendered


def test_gate_d_page_shows_both_sensitivity_populations_and_exact_review_boundary() -> None:
    app = _app().run(timeout=30)
    assert not app.exception
    rendered = _text(app)
    assert "known_a_road_reference_sample" in rendered
    assert "real_dft_count_points_with_raw_counts" in rendered
    assert "Population n=742" in rendered
    assert "Population n=305" in rendered
    assert "174/174 queued rows have no decision" in rendered
    assert "preserves 9 no-candidate rows" in rendered
    assert "this page cannot edit it" in rendered


def test_gate_d_page_is_read_only_and_fixed_source_links_are_digest_bound() -> None:
    before = _source_hashes()
    app = _app().run(timeout=30)
    assert not app.exception
    assert _source_hashes() == before
    rendered = _text(app)
    for relative, digest in before.items():
        assert relative in rendered
        assert digest in rendered
    assert "This page and its prose are not evidence" in rendered


def test_gate_d_page_has_no_input_file_or_action_controls() -> None:
    app = _app().run(timeout=30)
    assert not app.exception
    assert not app.button
    assert not app.checkbox
    assert not app.selectbox
    assert not app.multiselect
    assert not app.text_input
    assert not app.text_area
    assert not app.file_uploader
    assert not app.download_button


def test_gate_d_ui_source_has_no_write_network_review_or_execution_surface() -> None:
    paths = (
        REPO_ROOT / "src" / "traffictwin" / "ui" / "manchester_gate_d_services.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "pages" / "manchester_gate_d.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "requests.",
        "httpx.",
        "urlopen",
        "subprocess",
        ".write_text(",
        ".write_bytes(",
        "st.button(",
        "st.form(",
        "st.file_uploader(",
        "def execute(",
        "def accept(",
        "def register(",
    ):
        assert forbidden not in source
