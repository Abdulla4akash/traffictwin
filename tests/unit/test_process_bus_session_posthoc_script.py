"""Coverage for aggregate-only post-hoc processing of captured bus sessions."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from traffictwin.integration.manchester.bods_session_identity import (
    SessionCadenceMeasurement,
    SessionExtractionResult,
    SessionProgressionMeasurement,
    extract_session_observations_from_member,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "process_bus_session_posthoc.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "manchester" / "bods" / "siri-vm-synthetic.xml"
FIRST = "bods_siri_vm-20260728T051226Z-000000000001"
SECOND = "bods_siri_vm-20260728T051333Z-000000000002"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("process_bus_session_posthoc", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def posthoc_script() -> ModuleType:
    return _module()


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    for snapshot_id in (FIRST, SECOND):
        (workspace / "quarantine" / snapshot_id).mkdir(parents=True)
    (workspace / "accepted" / FIRST).mkdir(parents=True)
    return workspace


def _advanced_member() -> bytes:
    text = FIXTURE.read_text(encoding="utf-8")
    return (
        text.replace("2026-07-22T12:00:00Z", "2026-07-22T12:01:00Z")
        .replace("2026-07-22T11:59:50Z", "2026-07-22T12:00:50Z")
        .replace("<Longitude>-2.2400</Longitude>", "<Longitude>-2.2380</Longitude>")
        .encode()
    )


def test_explicit_bounds_select_only_the_declared_session(
    posthoc_script: ModuleType, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)
    outside = "bods_siri_vm-20260728T070223Z-000000000003"
    (workspace / "quarantine" / outside).mkdir()

    selected = posthoc_script.select_snapshot_ids(
        workspace / "quarantine",
        first_snapshot_id=FIRST,
        last_snapshot_id=SECOND,
    )

    assert selected == (FIRST, SECOND)


def test_processing_writes_only_aggregate_artifacts_and_a_receipt(
    posthoc_script: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)

    def fake_extract(
        _workspace_root: Path, snapshot_id: str, *, session_salt: bytes
    ) -> SessionExtractionResult:
        member = FIXTURE.read_bytes() if snapshot_id == FIRST else _advanced_member()
        return extract_session_observations_from_member(
            member, snapshot_id=snapshot_id, session_salt=session_salt
        )

    monkeypatch.setattr(posthoc_script, "extract_session_observations", fake_extract)
    output = posthoc_script.process_session(
        workspace,
        session_label="dawn-20260728",
        first_snapshot_id=FIRST,
        last_snapshot_id=SECOND,
    )

    cadence_path = output / "manchester" / "bus_cadence_probe_measurement.json"
    progression_path = output / "manchester" / "bus_session_progression_measurement.json"
    receipt_path = output / "posthoc_session_receipt.json"
    cadence = SessionCadenceMeasurement.model_validate_json(cadence_path.read_text())
    progression = SessionProgressionMeasurement.model_validate_json(progression_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    assert cadence.policy_id == "manchester-bods-session-identity-1.1"
    assert progression.policy_id == "manchester-bods-session-identity-1.1"
    assert receipt["snapshot_count"] == 2
    assert receipt["promoted_snapshot_count"] == 1
    assert receipt["quarantine_only_snapshot_count"] == 1
    assert receipt["acquisition_performed"] is False
    assert receipt["salt_persisted"] is False
    published = cadence_path.read_text() + progression_path.read_text() + receipt_path.read_text()
    assert "synthetic-vehicle" not in published
    assert "session_token" not in published

    with pytest.raises(posthoc_script.PosthocSessionError, match="will not be overwritten"):
        posthoc_script.process_session(
            workspace,
            session_label="dawn-20260728",
            first_snapshot_id=FIRST,
            last_snapshot_id=SECOND,
        )


def test_output_and_label_cannot_escape_the_workspace(
    posthoc_script: ModuleType, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)

    with pytest.raises(posthoc_script.PosthocSessionError, match="lowercase"):
        posthoc_script.process_session(
            workspace,
            session_label="../escape",
            first_snapshot_id=FIRST,
            last_snapshot_id=SECOND,
        )
    with pytest.raises(posthoc_script.PosthocSessionError, match="inside"):
        posthoc_script.process_session(
            workspace,
            session_label="dawn-20260728",
            first_snapshot_id=FIRST,
            last_snapshot_id=SECOND,
            output_root=tmp_path / "outside",
        )


def test_script_has_no_acquisition_or_api_key_surface() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "coordinated_bods_live_refresh" not in source
    assert "BODS_API_KEY" not in source
