from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.experiments.parameter_sweep import (
    MAX_SWEEP_POINTS,
    ParameterSweepError,
    ParameterSweepMode,
    ParameterSweepRequest,
    SweepAxis,
    SweepParameter,
    execute_parameter_sweep,
    expand_parameter_sweep,
    load_parameter_sweep_request,
    parameter_sweep_contract,
    parameter_sweep_request_to_yaml,
    parameter_sweep_response_to_csv,
)
from traffictwin.integration.sumo.contract import sumo_results_capability_manifest
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.metrics.results import MetricStatus
from traffictwin.synthetic.generator import generate_run_data
from traffictwin.synthetic.scenarios import preset_config

FIXED_TIME = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _local_request() -> ParameterSweepRequest:
    return ParameterSweepRequest(
        sweep_id="sweep-demand-capacity",
        title="Demand and capacity response",
        mode=ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES,
        base_synthetic_config=preset_config("baseline", random_seed=11),
        axes=[
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_TASK_ARRIVAL_RATE,
                values=[0.08, 0.12],
            ),
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_RSU_CAPACITY,
                values=[20.0, 35.0],
            ),
        ],
        metric_keys=["task.completion.rate", "infra.utilisation.mean"],
    )


def test_parameter_sweep_expands_complete_grid_deterministically() -> None:
    request = _local_request()
    first = expand_parameter_sweep(request)
    second = expand_parameter_sweep(request)

    assert first == second
    assert first.point_count == 4
    assert [
        [assignment.value for assignment in point.parameter_provenance] for point in first.points
    ] == [[0.08, 20.0], [0.08, 35.0], [0.12, 20.0], [0.12, 35.0]]
    assert len({point.point_id for point in first.points}) == 4
    assert all(point.synthetic_evaluation for point in first.points)
    assert all(point.seed_snapshot.parent_seed_id == "seed-baseline" for point in first.points)
    assert request.base_synthetic_config == preset_config("baseline", random_seed=11)


def test_parameter_sweep_rejects_oversize_duplicate_and_incompatible_axes() -> None:
    with pytest.raises(ValidationError, match=f"maximum is {MAX_SWEEP_POINTS}"):
        ParameterSweepRequest(
            sweep_id="sweep-too-large",
            title="Too large",
            mode=ParameterSweepMode.SEED_SNAPSHOTS,
            base_synthetic_config=preset_config("baseline"),
            axes=[
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_TASK_ARRIVAL_RATE,
                    values=[(index + 1) / 100 for index in range(16)],
                ),
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_RSU_CAPACITY,
                    values=[float(index + 1) for index in range(16)],
                ),
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_VEHICLE_COUNT,
                    values=[1, 2],
                ),
            ],
        )

    with pytest.raises(ValidationError, match="between 1 and 500"):
        ParameterSweepRequest(
            sweep_id="sweep-value-out-of-range",
            title="Out of range",
            mode=ParameterSweepMode.SEED_SNAPSHOTS,
            base_synthetic_config=preset_config("baseline"),
            axes=[
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_VEHICLE_COUNT,
                    values=[501],
                )
            ],
        )

    with pytest.raises(ValidationError, match="must not repeat"):
        ParameterSweepRequest(
            sweep_id="sweep-duplicate",
            title="Duplicate",
            mode=ParameterSweepMode.SEED_SNAPSHOTS,
            base_synthetic_config=preset_config("baseline"),
            axes=[
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_RSU_COUNT,
                    values=[1, 2],
                ),
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_RSU_COUNT,
                    values=[3, 4],
                ),
            ],
        )

    with pytest.raises(ValidationError, match="incompatible with the selected base"):
        ParameterSweepRequest(
            sweep_id="sweep-wrong-base",
            title="Wrong base",
            mode=ParameterSweepMode.SEED_SNAPSHOTS,
            base_seed=generate_run_data(preset_config("baseline")).seed,
            axes=[
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_RSU_COUNT,
                    values=[1, 2],
                )
            ],
        )


def test_invalid_declared_value_is_rejected_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="between 1 and 100"):
        ParameterSweepRequest(
            sweep_id="sweep-invalid-point",
            title="Invalid point",
            mode=ParameterSweepMode.SEED_SNAPSHOTS,
            base_synthetic_config=preset_config("baseline"),
            axes=[
                SweepAxis(
                    parameter_path=SweepParameter.SYNTHETIC_RSU_COUNT,
                    values=[1, 0],
                )
            ],
        )

    assert not (tmp_path / "not-written").exists()


def test_local_sweep_rejects_excessive_complete_row_estimate_before_writing(
    tmp_path: Path,
) -> None:
    request = ParameterSweepRequest(
        sweep_id="sweep-too-many-rows",
        title="Too many local rows",
        mode=ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES,
        base_synthetic_config=preset_config("baseline"),
        axes=[
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_DURATION_S,
                values=[3600.0],
            ),
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_SAMPLING_INTERVAL_S,
                values=[1.0],
            ),
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_VEHICLE_COUNT,
                values=[500],
            ),
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_RSU_CAPACITY,
                values=[20.0, 35.0],
            ),
        ],
        metric_keys=["task.completion.rate"],
    )

    with pytest.raises(ParameterSweepError, match="2,000,000"):
        execute_parameter_sweep(request, tmp_path / "not-written")

    assert not (tmp_path / "not-written").exists()


def test_parameter_sweep_rejects_symbolic_link_destination(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    destination = tmp_path / "destination"
    destination.symlink_to(target, target_is_directory=True)

    with pytest.raises(ParameterSweepError, match="symbolic link"):
        execute_parameter_sweep(_local_request(), destination, overwrite=True)

    assert destination.is_symlink()
    assert not list(target.iterdir())


def test_parameter_sweep_rejects_protected_destination_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ParameterSweepError, match="current directory"):
        execute_parameter_sweep(_local_request(), ".", overwrite=True)
    with pytest.raises(ParameterSweepError, match="must not be empty"):
        execute_parameter_sweep(_local_request(), "", overwrite=True)

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["keep.txt"]


def test_local_sweep_generates_valid_bundles_and_numeric_response_surface(
    tmp_path: Path,
) -> None:
    result = execute_parameter_sweep(
        _local_request(),
        tmp_path / "sweep",
        clock=lambda: FIXED_TIME,
    )

    assert result.status == "completed_local_analysis"
    assert result.point_count == 4
    assert result.response_row_count == 8
    assert result.response_surface_available
    assert result.fingerprint() == result.result_fingerprint
    assert result.direct_launch_supported is False
    assert all(row.metric_status is MetricStatus.AVAILABLE for row in result.response_surface)
    assert all(row.response_value is not None for row in result.response_surface)
    assert all(point.bundle_fingerprint for point in result.points)
    assert (tmp_path / "sweep" / "sweep_result.json").is_file()
    assert (tmp_path / "sweep" / "request.yaml").is_file()
    assert len(list((tmp_path / "sweep" / "bundles").iterdir())) == 4
    rows = list(csv.DictReader(io.StringIO(parameter_sweep_response_to_csv(result))))
    assert len(rows) == 8
    assert {row["synthetic_evaluation"] for row in rows} == {"true"}
    assert {row["synthetic.task_arrival_rate"] for row in rows} == {"0.08", "0.12"}


def test_local_sweep_preserves_non_numeric_metrics_as_unavailable(tmp_path: Path) -> None:
    request = _local_request().model_copy(update={"metric_keys": ["task.completion.rate_by_class"]})

    result = execute_parameter_sweep(request, tmp_path / "mapping")

    assert result.response_row_count == 4
    assert all(row.response_value is None for row in result.response_surface)
    assert all(row.metric_status is MetricStatus.UNAVAILABLE for row in result.response_surface)
    assert all("RESPONSE_VALUE_NON_NUMERIC" in row.reason_codes for row in result.response_surface)
    assert any("not replaced by zero" in warning for warning in result.warnings)


def test_external_requests_are_explicitly_not_executed(tmp_path: Path) -> None:
    base = generate_run_data(preset_config("baseline")).seed
    request = ParameterSweepRequest(
        sweep_id="sweep-external",
        title="External coordination",
        mode=ParameterSweepMode.EXTERNAL_RUN_REQUESTS,
        base_seed=base,
        axes=[
            SweepAxis(
                parameter_path=SweepParameter.SEED_DEMAND_MULTIPLIER,
                values=[1.0, 1.5],
            )
        ],
    )

    result = execute_parameter_sweep(request, tmp_path / "external", clock=lambda: FIXED_TIME)

    assert result.status == "external_requests_not_executed"
    assert not result.response_surface_available
    assert result.response_surface == []
    assert all(point.bundle_relative_path is None for point in result.points)
    assert all(point.external_request is not None for point in result.points)
    assert all(
        point.external_request is not None
        and point.external_request.execution_status == "not_executed"
        and point.external_request.direct_launch_supported is False
        and point.external_request.command is None
        and point.external_request.launcher is None
        for point in result.points
    )
    assert len(list((tmp_path / "external" / "external_requests").iterdir())) == 2
    assert not (tmp_path / "external" / "bundles").exists()


def test_seed_snapshot_mode_writes_only_parent_linked_seeds(tmp_path: Path) -> None:
    request = ParameterSweepRequest(
        sweep_id="sweep-seeds",
        title="Seed snapshots",
        mode=ParameterSweepMode.SEED_SNAPSHOTS,
        base_synthetic_config=preset_config("baseline"),
        axes=[
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_VEHICLE_COUNT,
                values=[10, 20],
            )
        ],
    )

    result = execute_parameter_sweep(request, tmp_path / "seeds")

    assert result.status == "expanded_seed_snapshots"
    assert result.response_surface == []
    assert len(list((tmp_path / "seeds" / "seeds").iterdir())) == 2
    assert all(point.seed_snapshot.parent_seed_id == "seed-baseline" for point in result.points)
    assert all(point.bundle_relative_path is None for point in result.points)
    assert all(point.external_request is None for point in result.points)
    assert not (tmp_path / "seeds" / "bundles").exists()
    assert not (tmp_path / "seeds" / "external_requests").exists()


def test_request_round_trip_overwrite_and_result_fingerprint_are_deterministic(
    tmp_path: Path,
) -> None:
    request = _local_request()
    request_path = tmp_path / "request.yaml"
    request_path.write_text(parameter_sweep_request_to_yaml(request), encoding="utf-8")
    assert load_parameter_sweep_request(request_path) == request

    first = execute_parameter_sweep(
        request,
        tmp_path / "first",
        clock=lambda: FIXED_TIME,
    )
    second = execute_parameter_sweep(
        request,
        tmp_path / "second",
        clock=lambda: datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
    )
    assert first.result_fingerprint == second.result_fingerprint
    assert [point.point_fingerprint for point in first.points] == [
        point.point_fingerprint for point in second.points
    ]

    with pytest.raises(FileExistsError):
        execute_parameter_sweep(request, tmp_path / "first")
    replaced = execute_parameter_sweep(request, tmp_path / "first", overwrite=True)
    assert replaced.result_fingerprint == first.result_fingerprint


def test_parameter_sweep_contract_publishes_bounds_and_execution_boundary() -> None:
    contract = parameter_sweep_contract()

    assert contract.max_points == 256
    assert contract.max_axes == 4
    assert contract.max_local_estimated_rows == 2_000_000
    assert contract.direct_launch_supported is False
    assert contract.external_execution_status == "not_executed"
    assert SweepParameter.SYNTHETIC_TASK_ARRIVAL_RATE in contract.synthetic_parameter_paths
    assert SweepParameter.SEED_DEMAND_MULTIPLIER in contract.seed_parameter_paths
    assert "Randy" in contract.limitations[1]


def test_source_specific_adapters_do_not_claim_parameter_sweep_support() -> None:
    assert sumo_results_capability_manifest().supports.parameter_sweep_composer.value == "false"
    assert tos_data_capability_manifest().supports.parameter_sweep_composer.value == "false"
