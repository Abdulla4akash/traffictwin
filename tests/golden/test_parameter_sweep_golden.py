from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.experiments.parameter_sweep import (
    ParameterSweepMode,
    ParameterSweepRequest,
    SweepAxis,
    SweepParameter,
    execute_parameter_sweep,
    parameter_sweep_response_to_csv,
)
from traffictwin.synthetic.scenarios import preset_config


def test_small_parameter_sweep_matches_approved_response_and_provenance(
    tmp_path: Path,
) -> None:
    request = ParameterSweepRequest(
        sweep_id="sweep-golden",
        title="Golden demand response",
        mode=ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES,
        base_synthetic_config=preset_config("baseline", random_seed=7),
        axes=[
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_TASK_ARRIVAL_RATE,
                values=[0.08, 0.12],
            )
        ],
        metric_keys=["task.completion.rate", "infra.utilisation.mean"],
    )
    result = execute_parameter_sweep(
        request,
        tmp_path / "sweep",
        clock=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
    )
    projection = {
        "schema_version": result.schema_version,
        "capability_id": "EXP-01",
        "method_version": result.method_version,
        "sweep_id": result.sweep_id,
        "mode": result.mode.value,
        "status": result.status,
        "request_fingerprint": result.request_fingerprint,
        "base_fingerprint": result.base_fingerprint,
        "result_fingerprint": result.result_fingerprint,
        "point_count": result.point_count,
        "response_row_count": result.response_row_count,
        "synthetic_evaluation": result.synthetic_evaluation,
        "direct_launch_supported": result.direct_launch_supported,
        "points": [
            {
                "point_id": point.point_id,
                "point_fingerprint": point.point_fingerprint,
                "assignments": [
                    assignment.model_dump(mode="json") for assignment in point.parameter_provenance
                ],
                "seed_id": point.seed_snapshot.seed_id,
                "seed_fingerprint": point.seed_fingerprint,
                "bundle_fingerprint": point.bundle_fingerprint,
            }
            for point in result.points
        ],
        "responses": [
            {
                "point_id": response.point_id,
                "metric_key": response.metric_key,
                "metric_status": response.metric_status.value,
                "response_value": response.response_value,
                "unit": response.unit,
                "reason_codes": response.reason_codes,
                "bundle_fingerprint": response.bundle_fingerprint,
            }
            for response in result.response_surface
        ],
    }

    expected_dir = Path("tests/golden/expected")
    assert projection == json.loads(
        (expected_dir / "parameter_sweep_small.json").read_text(encoding="utf-8")
    )
    assert parameter_sweep_response_to_csv(result) == (
        expected_dir / "parameter_sweep_small.csv"
    ).read_text(encoding="utf-8")
