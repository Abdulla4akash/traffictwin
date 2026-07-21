from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.diagnostics.threshold_sweep import ThresholdSensitivityReport
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.rules.config import RuleSetConfig
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config
from traffictwin.ui.charts import threshold_sweep_figure
from traffictwin.ui.services import (
    ServiceError,
    evaluate_threshold_sweep_for_ui,
    parse_rule_config_json_for_ui,
    rule_config_json_for_ui,
    sweep_point_config_json_for_ui,
)


def _pack(tmp_path: Path) -> EvidencePack:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    validation = validate_bundle(bundle)
    collection = compute_metrics_for_bundle(validation, clock=fixed_clock)
    return build_evidence_pack(validation, collection, clock=fixed_clock)


def test_ui_service_delegates_complete_threshold_grid_and_builds_neutral_chart(
    tmp_path: Path,
) -> None:
    result = evaluate_threshold_sweep_for_ui(
        _pack(tmp_path),
        rule_id="R8",
        minimum_threshold=0.0,
        maximum_threshold=2.0,
        point_count=4,
    )

    assert isinstance(result, ThresholdSensitivityReport)
    assert result.evaluated_point_count == 5
    assert result.source_threshold_injected is True
    assert len(result.flip_boundaries) == 1
    figure = threshold_sweep_figure(result)
    assert len(figure.data) == 1
    assert list(figure.data[0].x) == [point.threshold for point in result.points]
    assert list(figure.data[0].y) == [point.status.value for point in result.points]


def test_ui_service_validates_complete_config_import_and_explicit_point_export(
    tmp_path: Path,
) -> None:
    config = RuleSetConfig.model_validate(
        {"r8": {"minimum_energy_per_completed_task_j": 1.8, "minimum_completed_tasks": 12}}
    )
    imported = parse_rule_config_json_for_ui(rule_config_json_for_ui(config))
    invalid = parse_rule_config_json_for_ui(b'{"r8":{"invented":true}}')

    assert isinstance(imported, RuleSetConfig)
    assert imported == config
    assert isinstance(invalid, ServiceError)

    result = evaluate_threshold_sweep_for_ui(
        _pack(tmp_path),
        rule_id="R8",
        minimum_threshold=0.0,
        maximum_threshold=2.0,
        point_count=3,
        rule_config=config,
    )
    assert isinstance(result, ThresholdSensitivityReport)
    exported = sweep_point_config_json_for_ui(result, config, 2.0)
    unseen = sweep_point_config_json_for_ui(result, config, 1.9)

    assert isinstance(exported, str)
    payload = json.loads(exported)
    assert payload["r8"]["minimum_energy_per_completed_task_j"] == 2.0
    assert payload["r8"]["minimum_completed_tasks"] == 12
    assert isinstance(unseen, ServiceError)


def test_ui_service_returns_errors_for_invalid_grid_and_config(tmp_path: Path) -> None:
    invalid_grid = evaluate_threshold_sweep_for_ui(
        _pack(tmp_path),
        rule_id="R8",
        minimum_threshold=1.0,
        maximum_threshold=1.0,
        point_count=3,
    )
    invalid_json = parse_rule_config_json_for_ui("not-json")

    assert isinstance(invalid_grid, ServiceError)
    assert isinstance(invalid_json, ServiceError)
