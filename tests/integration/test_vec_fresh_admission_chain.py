"""Real-artifact chain tests for fresh-run scientific admission.

The full end-to-end case needs two operator-supplied externals: the audited
``tos-data`` clone and one published full-length VEC-07 result directory.
Neither is fabricated here — without them the chain test skips with the exact
missing prerequisite, which is itself the honest state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from traffictwin.integration.vec_fresh_admission import (
    VecFreshAdmissionError,
    VecFreshRunStudyContext,
    VecPairingSeedSource,
    admit_vec_fresh_run,
)
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.storage.registry import Registry

RESULT_DIR_VARIABLE = "TRAFFICTWIN_VEC_FRESH_RESULT_DIR"
TOS_DATA_VARIABLE = "TRAFFICTWIN_TOS_DATA_REPO"
DEFAULT_TOS_DATA = Path(__file__).resolve().parents[2].parent / "external" / "tos-data"


def _study() -> VecFreshRunStudyContext:
    return VecFreshRunStudyContext(
        experiment_id="vec-fresh-chain-check",
        seed_id="chain-baseline",
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        synthetic_fixture=False,
    )


def test_refuses_result_directory_without_receipt(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    with pytest.raises(VecFreshAdmissionError, match="execution_receipt.json"):
        admit_vec_fresh_run(
            result_dir,
            tmp_path / "registry.sqlite",
            _study(),
            tos_data_repo=tmp_path,
        )


def test_refuses_tampered_published_output(tmp_path: Path) -> None:
    source = os.environ.get(RESULT_DIR_VARIABLE)
    if source is None:
        pytest.skip(f"{RESULT_DIR_VARIABLE} is not set; no published fresh run to tamper-check")
    result_dir = tmp_path / "tampered"
    result_dir.mkdir()
    for item in Path(source).iterdir():
        if item.is_file():
            (result_dir / item.name).write_bytes(item.read_bytes())
    receipt_payload = json.loads((result_dir / "execution_receipt.json").read_text())
    target = result_dir / receipt_payload["outputs"][0]["path"]
    target.write_bytes(target.read_bytes() + b"\0")
    with pytest.raises(VecFreshAdmissionError, match="does not match its receipt identity"):
        admit_vec_fresh_run(
            result_dir,
            tmp_path / "registry.sqlite",
            _study(),
            tos_data_repo=DEFAULT_TOS_DATA,
        )


def test_full_chain_admits_one_published_fresh_run(tmp_path: Path) -> None:
    source = os.environ.get(RESULT_DIR_VARIABLE)
    if source is None:
        pytest.skip(f"{RESULT_DIR_VARIABLE} is not set; publish a full VEC-07 run first")
    tos_data = Path(os.environ.get(TOS_DATA_VARIABLE, str(DEFAULT_TOS_DATA)))
    if not tos_data.is_dir():
        pytest.skip("audited tos-data clone is not available")
    registry_path = tmp_path / "registry.sqlite"
    record, outcome = admit_vec_fresh_run(
        Path(source),
        registry_path,
        _study(),
        tos_data_repo=tos_data,
    )
    assert record.reviewed_trace is True
    assert record.study.synthetic_fixture is False
    assert record.research_status == "owner_approved_candidate"
    assert record.reproduction_graded is False
    assert outcome.run_created or outcome.run_idempotent
    payloads = Registry(registry_path).list_metric_collection_json()
    collections = [MetricCollection.model_validate_json(payload) for payload in payloads]
    assert len(collections) == 1
    collection = collections[0]
    assert collection.run_id == record.registry_run_id
    available = [item for item in collection.results if item.status is MetricStatus.AVAILABLE]
    assert len(available) == record.available_metric_count
    assert all(item.synthetic is False for item in collection.results)
