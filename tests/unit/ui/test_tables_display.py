"""Tests for the additive table presentation layer."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.tables import (
    COLUMN_LABELS,
    MACHINE_ID_COLUMNS,
    ColumnDisplay,
    column_display,
    display_label,
    table_column_config,
)


def test_display_label_uses_known_labels_and_sentence_case_fallback() -> None:
    assert display_label("metric_key") == "Metric"
    assert display_label("reason_codes") == "Reason codes"
    assert display_label("absolute_delta") == "Absolute delta"
    assert display_label("unknown_new_field") == "Unknown new field"


def test_column_display_hides_machine_ids_by_default() -> None:
    assert column_display("run_id").hidden
    assert column_display("bundle_fingerprint").hidden
    assert column_display("some_other_id").hidden
    assert not column_display("metric_key").hidden
    assert not column_display("value").hidden


def test_column_display_can_keep_machine_ids_visible() -> None:
    spec = column_display("run_id", hide_machine_ids=False)
    assert not spec.hidden
    assert spec.label == "Run id"


def test_column_display_appends_units_to_labels() -> None:
    spec = column_display("value", unit="veh/h")
    assert spec.label == "Value (veh/h)"
    assert spec.unit == "veh/h"


def test_table_column_config_maps_hidden_number_and_text_columns() -> None:
    rows = [
        {"metric_key": "flow", "value": 12.5, "share": 0.42, "run_id": "run-1"},
        {"metric_key": "speed", "value": 8.0, "share": 0.58, "run_id": "run-2"},
    ]
    config = table_column_config(
        rows,
        units={"value": "veh/h"},
        number_formats={"value": "%.3f", "share": "percent"},
    )
    assert config["run_id"] is None
    assert isinstance(config["value"], type(st.column_config.NumberColumn("x")))
    assert isinstance(config["metric_key"], type(st.column_config.TextColumn("x")))
    assert set(config) == {"metric_key", "value", "share", "run_id"}


def test_table_column_config_respects_overrides() -> None:
    rows = [{"run_id": "run-1", "value": 1.0}]
    override = ColumnDisplay(key="run_id", label="Run", hidden=False)
    config = table_column_config(rows, overrides={"run_id": override})
    assert config["run_id"] is not None


def test_table_column_config_never_mutates_row_values() -> None:
    rows = [{"metric_key": "flow", "value": 12.5, "run_id": "run-1"}]
    snapshot = [dict(row) for row in rows]
    table_column_config(rows, number_formats={"value": "%.1f"})
    assert rows == snapshot


def test_machine_id_columns_do_not_swallow_semantic_columns() -> None:
    assert "metric_key" not in MACHINE_ID_COLUMNS
    assert "status" not in MACHINE_ID_COLUMNS
    for key in MACHINE_ID_COLUMNS:
        assert key not in COLUMN_LABELS
