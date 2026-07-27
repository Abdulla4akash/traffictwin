"""AppTest coverage for the additive Match Review page."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.integration.manchester.network_connectivity import MotorAccess
from traffictwin.integration.manchester.network_geometry import build_edge_index
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    match_observation_v11,
)
from traffictwin.integration.manchester.observation_review import load_review_ledger
from traffictwin.ui.state import default_session_state, load_ui_config

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"


def _artifact(tmp_path: Path) -> Path:
    network = tmp_path / "n.net.xml"
    network.write_text(
        "<?xml version='1.0'?>\n<net>\n"
        f'  <location netOffset="-517074.60,-5908760.37" '
        f'convBoundary="0.00,0.00,5000.00,5000.00" '
        f'origBoundary="-2.40,53.30,-2.10,53.60" projParameter="{PROJ}"/>\n'
        '  <junction id="J0" type="priority" x="31000.00" y="16000.00" '
        'incLanes="" intLanes=""/>\n'
        '  <junction id="J1" type="priority" x="31060.00" y="16060.00" '
        'incLanes="" intLanes=""/>\n'
        '  <edge id="e1" from="J0" to="J1" type="highway.unclassified">\n'
        '    <param key="ref" value="A56"/>\n  </edge>\n'
        '  <edge id="e2" from="J0" to="J1" type="highway.residential">\n'
        '    <param key="ref" value="A56"/>\n  </edge>\n'
        "</net>\n",
        encoding="utf-8",
    )
    index = build_edge_index(network)
    geometry = index.geometry(0)
    access: dict[str, MotorAccess] = dict.fromkeys(("e1", "e2"), "passenger_car")
    row = match_observation_v11(
        count_point_id=101,
        easting=geometry[0],
        northing=geometry[1],
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=ManchesterMapMatchPolicyV11(),
        motor_access=access,
    )
    artifact = tmp_path / "match_results.json"
    artifact.write_text(json.dumps([row.model_dump(mode="json")]), encoding="utf-8")
    return artifact


def _app(monkeypatch: MonkeyPatch, tmp_path: Path) -> Any:  # noqa: ANN401 - AppTest is loaded dynamically
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(tmp_path / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path / "workspace"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/match_review.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def test_page_guides_without_an_artifact(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    app = _app(monkeypatch, tmp_path)
    app.run(timeout=15)

    assert not app.exception
    assert any(title.value == "Match Review" for title in app.title)
    info_values = " ".join(str(info.value) for info in app.info)
    assert "rebuilt from the rows themselves" in info_values


def test_full_decision_flow_records_and_seals(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    artifact = _artifact(tmp_path)
    ledger_path = tmp_path / "ledger.json"
    app = _app(monkeypatch, tmp_path)
    app.session_state["match_review_artifact"] = str(artifact)
    app.session_state["match_review_ledger"] = str(ledger_path)
    app.run(timeout=15)

    assert not app.exception
    assert any(metric.label == "Pending" and metric.value == "1" for metric in app.metric)

    next(field for field in app.text_input if field.label == "Reviewer name").set_value(
        "A. Analyst"
    )
    next(field for field in app.text_input if field.label == "Reviewer role").set_value(
        "research analyst"
    )
    next(area for area in app.text_area if "Reason" in area.label).set_value(
        "deferring pending a site visit to distinguish the two A56 carriageways"
    )
    next(button for button in app.button if button.label == "Record this one decision").click().run(
        timeout=15
    )

    assert not app.exception
    assert ledger_path.exists()
    persisted = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert len(persisted["decisions"]) == 1
    assert persisted["decisions"][0]["kind"] == "defer"
    assert persisted["seal"] is None

    app.session_state["match_review_artifact"] = str(artifact)
    app.session_state["match_review_ledger"] = str(ledger_path)
    app.run(timeout=15)
    assert any(metric.label == "Deferred" and metric.value == "1" for metric in app.metric)
    export_field = next(field for field in app.text_input if field.label == "Sealed export path")
    export_field.set_value(str(tmp_path / "sealed.json"))
    next(button for button in app.button if button.label == "Seal and export").click().run(
        timeout=15
    )
    assert not app.exception
    sealed = load_review_ledger((tmp_path / "sealed.json").read_text(encoding="utf-8"))
    assert sealed.live_decisions()[101].kind.value == "defer"
