"""AppTest coverage for the three additive platform dashboard pages.

Empty states matter more than usual here: inventory gaps, thin or absent
forecasts, and the empty predictions-versus-measurements table must read as
designed honesty rather than brokenness. Each page also proves its boundary:
read-only inventory, forecast banners, and the composer's no-write rule.
"""

from __future__ import annotations

import json
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.ui.state import default_session_state, load_ui_config

REPO_ROOT = Path(__file__).resolve().parents[2]

_LABEL_KINDS = ("button", "selectbox", "number_input", "text_input")


def _app(monkeypatch: MonkeyPatch, workspace: Path, script: str) -> Any:  # noqa: ANN401 - AppTest is loaded dynamically
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/app_pages/{script}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _markdown(app: Any) -> str:  # noqa: ANN401 - AppTest is loaded dynamically
    return " ".join(str(item.value) for item in app.markdown)


def _captions(app: Any) -> str:  # noqa: ANN401 - AppTest is loaded dynamically
    return " ".join(str(item.value) for item in app.caption)


def _tables(app: Any) -> str:  # noqa: ANN401 - AppTest is loaded dynamically
    """Untruncated table contents (pandas repr elides wide frames)."""

    return " ".join(frame.value.to_csv(index=False) for frame in app.dataframe)


def _assert_labels_unique(app: Any) -> None:  # noqa: ANN401 - AppTest is loaded dynamically
    for kind in _LABEL_KINDS:
        labels = [str(element.label).strip().lower() for element in getattr(app, kind)]
        assert all(labels), f"an unlabelled {kind} exists"
        duplicates = {label for label in labels if labels.count(label) > 1}
        assert not duplicates, f"duplicated {kind} labels: {sorted(duplicates)}"


def _seed_scheduled_session(workspace: Path) -> None:
    directory = workspace / "manchester" / "scheduled" / "2026-08-01" / "night"
    directory.mkdir(parents=True)
    (directory / "completed.json").write_text(
        json.dumps(
            {
                "record_type": "scheduled_bods_session_completion",
                "label": "night",
                "session_date": "2026-08-01",
                "snapshots_accepted": 15,
                "snapshots_refused": 1,
                "finished_at_utc": "2026-08-01T23:50:00+00:00",
                "accepted_snapshot_ids": [],
            }
        ),
        encoding="utf-8",
    )
    (directory / "activity_aggregate.json").write_text(
        json.dumps(
            {
                "record_type": "bods_session_activity_aggregate",
                "schema_version": "1.0",
                "design_reference": "docs/platform/bus_prediction_design.md",
                "session_kind": "scheduled",
                "label": "night",
                "session_date_local": "2026-08-01",
                "utc_offset_seconds_applied": 3600,
                "timezone_note": "fixture",
                "schedule_digest": None,
                "snapshot_count": 15,
                "concurrency_source": "parser_live_vehicle",
                "per_snapshot_live_vehicle": [
                    {
                        "snapshot_id": f"bods_siri_vm-fix-{index:04d}",
                        "hour_utc": 23,
                        "hour_local": 0,
                        "live_vehicle": 40 + index,
                    }
                    for index in range(15)
                ],
                "progression_available": False,
                "progression_unavailable_reason": "NO_PROGRESSION: fixture",
                "hourly_progression": [],
                "aggregates_only": True,
                "raw_identifiers_published": False,
                "bus_progression_only": True,
                "road_traffic_speed_available": False,
                "session_salt_discarded": True,
            }
        ),
        encoding="utf-8",
    )
    skip_directory = workspace / "manchester" / "scheduled" / "2026-08-01" / "dawn"
    skip_directory.mkdir(parents=True)
    (skip_directory / "skipped.json").write_text(
        json.dumps(
            {
                "record_type": "scheduled_bods_session_skip",
                "label": "dawn",
                "session_date": "2026-08-01",
                "reason": "late",
            }
        ),
        encoding="utf-8",
    )
    (workspace / "manchester" / "scheduled" / "retention_report.json").write_text(
        json.dumps(
            {
                "record_type": "scheduled_bods_retention_report",
                "eligible_snapshot_count": 3,
            }
        ),
        encoding="utf-8",
    )


# --- Data Inventory ----------------------------------------------------------


def test_inventory_empty_state_reads_as_designed_honesty(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace", "platform_inventory.py")
    app.run(timeout=20)
    assert not app.exception
    assert any(title.value == "Data Inventory" for title in app.title)
    markdown = _markdown(app)
    assert "READ-ONLY" in markdown
    assert "NO RAW BYTES" in markdown
    captions = _captions(app)
    assert "nothing can be acquired, deleted, or re-admitted" in captions
    assert "owner-confirmed and never automatic" in captions
    _assert_labels_unique(app)


def test_inventory_lists_records_gaps_and_retention_without_private_paths(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    _seed_scheduled_session(workspace)
    app = _app(monkeypatch, workspace, "platform_inventory.py")
    app.run(timeout=20)
    assert not app.exception
    assert app.dataframe, "the seeded inventory must render at least one table"
    rendered = _tables(app)
    assert "scheduled session 2026-08-01/night" in rendered
    assert "1 refusal(s) ledgered" in rendered
    assert "recorded_skip" in rendered
    captions = _captions(app)
    assert "3 scheduled snapshot(s) are prune-eligible" in captions
    # NON_ADMITTED isolation: committed GPU preservation records surface with
    # their standing verbatim and the never-enters-forecasts statement.
    assert "never enter forecasts" in captions
    # Redaction: the absolute workspace path never reaches the page.
    everything = rendered + captions + _markdown(app)
    assert str(workspace) not in everything


# --- Forecasts ---------------------------------------------------------------


def test_forecasts_empty_state_keeps_its_banners(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    app = _app(monkeypatch, tmp_path / "workspace", "platform_forecasts.py")
    app.run(timeout=20)
    assert not app.exception
    markdown = _markdown(app)
    assert "FORECAST — NOT EVIDENCE" in markdown
    assert "BUS PROGRESSION — NOT ROAD SPEED" in markdown
    info_values = " ".join(str(info.value) for info in app.info)
    assert "designed honesty" in info_values
    captions = _captions(app)
    assert "held-out validation has not run" in captions
    _assert_labels_unique(app)


def test_forecasts_render_support_counts_and_the_unavailable_speed_target(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    _seed_scheduled_session(workspace)
    app = _app(monkeypatch, workspace, "platform_forecasts.py")
    app.run(timeout=20)
    assert not app.exception
    captions = _captions(app)
    assert "eligible distinct local service dates, never wall-clock days" in captions
    rendered = _tables(app)
    assert "support (dates)" in rendered or "eligible dates" in rendered
    warnings = " ".join(str(warning.value) for warning in app.warning)
    assert "never derived from cadence" in warnings
    assert "forecast=true / evidence=false / causal=false" in captions


# --- What-If Composer --------------------------------------------------------


def test_composer_renders_the_form_and_the_empty_honesty_table(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace", "platform_composer.py")
    app.run(timeout=20)
    assert not app.exception
    markdown = _markdown(app)
    assert "PREDICTION — NOT EVIDENCE" in markdown
    assert "DRAFT-ONLY" in markdown
    assert "NO EXECUTION" in markdown
    captions = _captions(app)
    assert "signing is a human act" in captions.lower() or "human act" in captions
    assert "Empty, and visibly so" in captions
    assert "NON_ADMITTED bus/GPU results never populate it" in captions
    assert "producer_citation_requirements.md" in captions
    # The external-LLM field is absent: only the four declared form controls.
    assert len(app.text_input) == 1
    assert len(app.selectbox) == 2
    _assert_labels_unique(app)


def test_composer_writes_nothing_into_the_repository(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    drafts_directory = REPO_ROOT / "docs" / "evaluation" / "drafts"
    existed_before = drafts_directory.exists()
    app = _app(monkeypatch, tmp_path / "workspace", "platform_composer.py")
    app.run(timeout=20)
    assert not app.exception
    assert drafts_directory.exists() == existed_before
    assert not (tmp_path / "workspace").exists() or not list(
        (tmp_path / "workspace").rglob("*draft*")
    )
