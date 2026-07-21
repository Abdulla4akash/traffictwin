from __future__ import annotations

from pathlib import Path
from typing import Never

import pytest
import yaml
from pydantic import ValidationError
from pytest import MonkeyPatch

from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.domain.measurement import (
    MeasurementTableKind,
    SyntheticMeasurementImpairmentConfig,
    measurement_impairment_contract,
    stable_measurement_fingerprint,
)
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.integration.sumo.contract import sumo_results_capability_manifest
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import SyntheticScenarioConfig
from traffictwin.synthetic.generator import SyntheticRunData, generate_run_data, serialisable_rows
from traffictwin.synthetic.scenarios import preset_config


def _complete_model(seed: int = 31) -> SyntheticMeasurementImpairmentConfig:
    return SyntheticMeasurementImpairmentConfig(
        random_seed=seed,
        vehicle_position_max_error_m=3.0,
        vehicle_speed_max_error_mps=1.5,
        traffic_speed_max_error_mps=2.0,
        traffic_count_max_error=4,
        infrastructure_utilisation_max_error=0.1,
        infrastructure_queue_max_error=3,
        row_dropout_fraction_by_table={
            MeasurementTableKind.INFRA_STATE: 0.20,
            MeasurementTableKind.VEHICLE_STATE: 0.10,
            MeasurementTableKind.TRAFFIC_OBS: 0.20,
        },
    )


def _config(
    model: SyntheticMeasurementImpairmentConfig,
) -> SyntheticScenarioConfig:
    payload = preset_config("baseline").model_dump(mode="python")
    payload["measurement_imperfections"] = model.model_dump(mode="python")
    return SyntheticScenarioConfig.model_validate(payload)


def test_measurement_model_is_deterministic_and_leaves_outcomes_unchanged() -> None:
    clean = generate_run_data(preset_config("baseline"))
    config = _config(_complete_model())
    first = generate_run_data(config)
    second = generate_run_data(config)

    assert serialisable_rows(first.rows) == serialisable_rows(second.rows)
    assert first.measurement_impairment_audit == second.measurement_impairment_audit
    assert first.measurement_impairment_audit is not None
    assert (
        first.measurement_impairment_audit.fingerprint()
        == first.measurement_impairment_audit.audit_fingerprint
    )
    for table in ("tasks", "trips", "incidents"):
        assert first.rows.get(table) == clean.rows.get(table)


def test_all_noise_values_respect_declared_bounds_and_clamps() -> None:
    model = _complete_model().model_copy(update={"row_dropout_fraction_by_table": {}})
    clean = generate_run_data(preset_config("baseline")).rows
    impaired = generate_run_data(_config(model)).rows

    for before, after in zip(clean["vehicle_state"], impaired["vehicle_state"], strict=True):
        assert abs(float(str(after["x"])) - float(str(before["x"]))) <= 3.0
        assert abs(float(str(after["y"])) - float(str(before["y"]))) <= 3.0
        assert abs(float(str(after["speed"])) - float(str(before["speed"]))) <= 1.5
        assert float(str(after["speed"])) >= 0
    for before, after in zip(clean["traffic_obs"], impaired["traffic_obs"], strict=True):
        assert abs(float(str(after["average_speed"])) - float(str(before["average_speed"]))) <= 2.0
        assert abs(int(str(after["count"])) - int(str(before["count"]))) <= 4
        assert float(str(after["average_speed"])) >= 0
        assert int(str(after["count"])) >= 0
    for before, after in zip(clean["infra_state"], impaired["infra_state"], strict=True):
        assert abs(float(str(after["utilisation"])) - float(str(before["utilisation"]))) <= 0.1
        assert abs(int(str(after["queue_length"])) - int(str(before["queue_length"]))) <= 3
        assert 0 <= float(str(after["utilisation"])) <= 1
        assert int(str(after["queue_length"])) >= 0


def test_dropout_has_exact_counts_and_retains_at_least_one_row() -> None:
    clean = generate_run_data(preset_config("baseline"))
    impaired = generate_run_data(_config(_complete_model()))
    audit = impaired.measurement_impairment_audit

    assert audit is not None
    expected = {
        MeasurementTableKind.INFRA_STATE: 4,
        MeasurementTableKind.VEHICLE_STATE: 22,
        MeasurementTableKind.TRAFFIC_OBS: 2,
    }
    assert {item.table_kind: item.rows_dropped for item in audit.dropout_audits} == expected
    for item in audit.dropout_audits:
        assert item.rows_before == item.rows_dropped + item.rows_retained
        assert item.rows_retained >= 1
        assert len(impaired.rows[item.table_kind.value]) == item.rows_retained
        assert len(clean.rows[item.table_kind.value]) == item.rows_before


def test_noise_axes_are_isolated_and_measurement_seed_changes_output() -> None:
    position = SyntheticMeasurementImpairmentConfig(
        random_seed=7,
        vehicle_position_max_error_m=2.0,
    )
    position_and_traffic = SyntheticMeasurementImpairmentConfig(
        random_seed=7,
        vehicle_position_max_error_m=2.0,
        traffic_speed_max_error_mps=1.0,
    )
    other_seed = position.model_copy(update={"random_seed": 8})

    first = generate_run_data(_config(position)).rows
    extended = generate_run_data(_config(position_and_traffic)).rows
    changed_seed = generate_run_data(_config(other_seed)).rows

    assert first["vehicle_state"] == extended["vehicle_state"]
    assert first["traffic_obs"] != extended["traffic_obs"]
    assert first["vehicle_state"] != changed_seed["vehicle_state"]


def test_invalid_or_stream_incompatible_models_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must enable noise or dropout"):
        SyntheticMeasurementImpairmentConfig()
    with pytest.raises(ValidationError):
        SyntheticMeasurementImpairmentConfig(vehicle_position_max_error_m=100.1)
    with pytest.raises(ValidationError, match="row dropout fractions"):
        SyntheticMeasurementImpairmentConfig(
            row_dropout_fraction_by_table={MeasurementTableKind.TRAFFIC_OBS: 0.96}
        )

    payload = preset_config("baseline").model_dump(mode="python")
    payload["include_vehicles"] = False
    payload["measurement_imperfections"] = {
        "vehicle_position_max_error_m": 1.0,
    }
    with pytest.raises(ValidationError, match="require enabled generated streams"):
        SyntheticScenarioConfig.model_validate(payload)


def test_impaired_bundle_is_labelled_valid_and_ordinary_metrics_run(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(_config(_complete_model()), tmp_path / "impaired")
    validation = validate_bundle(bundle)

    assert validation.report.may_import
    assert validation.manifest is not None
    assert validation.manifest.bundle.source == "synthetic_fixture"
    assert "-imp-" in validation.manifest.bundle.bundle_id
    audit = validation.manifest.synthetic_measurement_impairment
    assert audit is not None
    assert audit.synthetic_evaluation is True
    assert audit.calibrated_sensor_model is False
    assert audit.raw_source_mutated is False
    assert audit.configuration_fingerprint == audit.configuration.fingerprint()
    metrics = compute_metrics_for_bundle(validation)
    assert metrics.run_id == validation.manifest.run.run_id
    assert len(metrics.results) == 63


def test_tampered_measurement_audit_is_rejected(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(_config(_complete_model()), tmp_path / "tampered")
    manifest_path = bundle / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["synthetic_measurement_impairment"]["audit_fingerprint"] = "0" * 64
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    validation = validate_bundle(bundle)

    assert not validation.report.may_import
    assert validation.manifest is None


def test_re_fingerprinted_semantic_audit_tampering_is_rejected(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(_config(_complete_model()), tmp_path / "semantic-tamper")
    manifest_path = bundle / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    audit = manifest["synthetic_measurement_impairment"]
    audit["field_audits"][0]["field"] = "invented_measurement"
    audit["audit_fingerprint"] = ""
    audit["audit_fingerprint"] = stable_measurement_fingerprint(audit)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    validation = validate_bundle(bundle)

    assert not validation.report.may_import
    assert validation.manifest is None


def test_disabled_model_preserves_existing_bundle_bytes(tmp_path: Path) -> None:
    first = write_synthetic_bundle(preset_config("baseline"), tmp_path / "first")
    payload = preset_config("baseline").model_dump(mode="python")
    assert "measurement_imperfections" not in payload
    second = write_synthetic_bundle(
        SyntheticScenarioConfig.model_validate(payload),
        tmp_path / "second",
    )

    first_files = {path.name: path.read_bytes() for path in first.iterdir() if path.is_file()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
    assert first_files == second_files


def test_synthetic_bundle_overwrite_is_protected_and_transactional(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    destination = write_synthetic_bundle(preset_config("baseline"), tmp_path / "replace")
    original_manifest = (destination / "manifest.yaml").read_bytes()

    from traffictwin.synthetic import bundles as bundle_module

    def fail_manifest(_data: SyntheticRunData, _destination: Path) -> Never:
        raise RuntimeError("injected manifest failure")

    monkeypatch.setattr(bundle_module, "_manifest", fail_manifest)
    with pytest.raises(RuntimeError, match="injected manifest failure"):
        write_synthetic_bundle(
            preset_config("stressed_demand"),
            destination,
            overwrite=True,
        )

    assert (destination / "manifest.yaml").read_bytes() == original_manifest


def test_synthetic_bundle_rejects_protected_or_symbolic_link_destinations(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="must not be the current directory"):
        write_synthetic_bundle(preset_config("baseline"), Path.cwd(), overwrite=True)

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="must not be a symbolic link"):
        write_synthetic_bundle(preset_config("baseline"), link, overwrite=True)


def test_contract_and_source_capabilities_are_explicit() -> None:
    contract = measurement_impairment_contract()
    assert contract.distribution.value == "bounded_uniform"
    assert contract.synthetic_only is True
    assert contract.calibrated_sensor_model is False
    assert contract.direct_launch_supported is False
    assert contract.maximum_dropout_fraction == 0.95
    assert (
        default_export_import_manifest().supports.measurement_noise_dropout_models
        is CapabilitySupport.TRUE
    )
    assert (
        sumo_results_capability_manifest().supports.measurement_noise_dropout_models
        is CapabilitySupport.FALSE
    )
    assert (
        tos_data_capability_manifest().supports.measurement_noise_dropout_models
        is CapabilitySupport.FALSE
    )
