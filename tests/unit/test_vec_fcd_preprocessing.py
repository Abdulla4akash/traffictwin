from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.vec_preprocessing import (
    PINNED_VEC_ENV_COMMIT,
    VecFcdPreprocessRequest,
    VecGreedyUrbanPlacement,
    VecPreflightStatus,
    preflight_vec_fcd,
    service,
    vec_fcd_preprocessing_contract,
)
from traffictwin.integration.vec_preprocessing.models import (
    PINNED_SOURCE_FILES,
    VecSourceScriptEvidence,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "vec_fcd" / "synthetic_micro"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(root: Path, **changes: object) -> VecFcdPreprocessRequest:
    payload: dict[str, object] = {
        "input_id": "synthetic-micro",
        "scenario_day": "synthetic-day",
        "window_label": "t100-t103",
        "fcd_file": "fcd.xml",
        "network_file": "network.net.xml",
        "fcd_sha256": _sha256(root / "fcd.xml"),
        "network_sha256": _sha256(root / "network.net.xml"),
        "sumo_seed": 7,
    }
    payload.update(changes)
    return VecFcdPreprocessRequest.model_validate(payload)


def _fake_source(*, clean: bool = True) -> service._SourceState:
    scripts = tuple(
        VecSourceScriptEvidence(path=path, sha256=digest, size_bytes=1)
        for path, digest in sorted(PINNED_SOURCE_FILES.items())
    )
    return service._SourceState(
        head="e98441196270b8fd4cc0eede892df4a0053b2185",
        origin_main=PINNED_VEC_ENV_COMMIT,
        clean=clean,
        scripts=scripts,
        blobs=dict.fromkeys(PINNED_SOURCE_FILES, b"x"),
    )


@pytest.fixture(autouse=True)
def fake_source_and_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_inspect_source_repository", lambda _path: _fake_source())
    monkeypatch.setattr(
        service,
        "_inspect_dependencies",
        lambda: ({"numpy": "2.0.0", "pyproj": "3.7.0", "sumolib": "1.27.0"}, None),
    )


def test_request_is_strict_path_safe_and_fingerprinted() -> None:
    request = _request(FIXTURE)

    assert request.source_commit == PINNED_VEC_ENV_COMMIT
    assert request.fingerprint() == request.fingerprint()
    assert "tests/fixtures" not in request.canonical_json()

    for unsafe in ("../fcd.xml", "/tmp/fcd.xml", "folder\\fcd.xml"):  # noqa: S108
        with pytest.raises(ValidationError):
            _request(FIXTURE, fcd_file=unsafe)
    with pytest.raises(ValidationError):
        VecFcdPreprocessRequest.model_validate(
            {**request.model_dump(mode="json"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        VecGreedyUrbanPlacement(radius_m=10.0, cell_m=100.0)


def test_contract_publishes_exact_source_dependency_and_safety_boundary() -> None:
    contract = vec_fcd_preprocessing_contract()

    assert contract.source_commit == PINNED_VEC_ENV_COMMIT
    assert contract.source_scripts == PINNED_SOURCE_FILES
    assert contract.required_dependencies["sumolib"] == "==1.27.0"
    assert contract.operations == ["preflight_vec_fcd", "preprocess_vec_fcd"]
    assert "preprocessing_receipt.json" in contract.published_outputs
    assert all("launch SUMO" not in operation for operation in contract.operations)
    assert contract.fingerprint() == contract.fingerprint()


def test_preflight_accepts_bounded_one_second_synthetic_pair_without_mutation() -> None:
    before = {path.name: (_sha256(path), path.stat().st_mtime_ns) for path in FIXTURE.glob("*.xml")}

    report = preflight_vec_fcd(FIXTURE, FIXTURE, _request(FIXTURE))

    after = {path.name: (_sha256(path), path.stat().st_mtime_ns) for path in FIXTURE.glob("*.xml")}
    assert report.status is VecPreflightStatus.ACCEPTED
    assert report.read_only is True
    assert report.mutations_performed is False
    assert report.fcd is not None
    assert report.fcd.timestep_count == 4
    assert report.fcd.vehicle_observation_count == 6
    assert report.fcd.unique_vehicle_count == 3
    assert report.fcd.peak_concurrent_vehicles == 2
    assert report.fcd.dense_trace_cells == 8
    assert report.fcd.occupied_placement_cells == 3
    assert report.fcd.coordinates_within_network_boundary is True
    assert [item.code for item in report.findings] == [
        "VEC_FCD_ONE_SECOND_CONFIRMED",
        "VEC_NETWORK_COORDINATES_CONFIRMED",
        "VEC_PINNED_PIPELINE_CONFIRMED",
    ]
    assert before == after


def test_preflight_reports_dependencies_as_unavailable_not_valid_data_as_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service,
        "_inspect_dependencies",
        lambda: ({}, "optional dependencies are absent"),
    )

    report = preflight_vec_fcd(FIXTURE, FIXTURE, _request(FIXTURE))

    assert report.status is VecPreflightStatus.UNAVAILABLE
    assert report.fcd is not None
    assert [item.code for item in report.findings] == ["VEC_PREPROCESSING_DEPENDENCY_UNAVAILABLE"]


@pytest.mark.parametrize(
    ("versions", "message"),
    [
        (
            {"numpy": "1.25.2", "pyproj": "3.7.0", "sumolib": "1.27.0"},
            "numpy >=1.26",
        ),
        (
            {"numpy": "2.0.0", "pyproj": "4.0.0", "sumolib": "1.27.0"},
            "pyproj >=3.6,<4",
        ),
    ],
)
def test_dependency_probe_enforces_every_published_version_bound(
    versions: dict[str, str],
    message: str,
) -> None:
    error = service._dependency_version_error(versions)

    assert error is not None and message in error


@pytest.mark.parametrize(
    ("replacement", "code"),
    [
        (('time="101.00"', 'time="100.50"'), "VEC_FCD_RESOLUTION_INVALID"),
        (('x="300.00"', 'x="3000.00"'), "VEC_FCD_NETWORK_COORDINATE_MISMATCH"),
        (
            (
                "<fcd-export",
                '<!DOCTYPE fcd-export [<!ENTITY unsafe SYSTEM "file:///etc/passwd">]>\n<fcd-export',
            ),
            "VEC_XML_UNSAFE_DECLARATION",
        ),
    ],
)
def test_preflight_rejects_unsafe_or_incompatible_fcd(
    tmp_path: Path,
    replacement: tuple[str, str],
    code: str,
) -> None:
    source = tmp_path / "input"
    shutil.copytree(FIXTURE, source)
    fcd = source / "fcd.xml"
    fcd.write_text(
        fcd.read_text(encoding="utf-8").replace(*replacement),
        encoding="utf-8",
    )

    report = preflight_vec_fcd(source, source, _request(source))

    assert report.status is VecPreflightStatus.REJECTED
    assert [item.code for item in report.findings] == [code]


def test_preflight_rejects_hash_mismatch_and_dirty_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong_hash = "0" * 64
    mismatch = preflight_vec_fcd(
        FIXTURE,
        FIXTURE,
        _request(FIXTURE, fcd_sha256=wrong_hash),
    )
    assert mismatch.status is VecPreflightStatus.REJECTED
    assert [item.code for item in mismatch.findings] == ["VEC_INPUT_HASH_MISMATCH"]

    monkeypatch.setattr(
        service,
        "_inspect_source_repository",
        lambda _path: _fake_source(clean=False),
    )
    dirty = preflight_vec_fcd(FIXTURE, FIXTURE, _request(FIXTURE))
    assert dirty.status is VecPreflightStatus.REJECTED
    assert [item.code for item in dirty.findings] == ["VEC_SOURCE_DIRTY"]


def test_preflight_rejects_symlink_input(tmp_path: Path) -> None:
    source = tmp_path / "input"
    source.mkdir()
    shutil.copy2(FIXTURE / "network.net.xml", source / "network.net.xml")
    (source / "fcd.xml").symlink_to(FIXTURE / "fcd.xml")
    request = VecFcdPreprocessRequest(
        input_id="synthetic-micro",
        scenario_day="synthetic-day",
        window_label="t100-t103",
        fcd_file="fcd.xml",
        network_file="network.net.xml",
        fcd_sha256=_sha256(FIXTURE / "fcd.xml"),
        network_sha256=_sha256(source / "network.net.xml"),
        sumo_seed=7,
    )

    report = preflight_vec_fcd(source, source, request)

    assert report.status is VecPreflightStatus.REJECTED
    assert [item.code for item in report.findings] == ["VEC_INPUT_PATH_UNSAFE"]


def test_preflight_rejects_symlink_parent_beneath_input_root(tmp_path: Path) -> None:
    source = tmp_path / "input"
    actual = source / "actual"
    actual.mkdir(parents=True)
    shutil.copy2(FIXTURE / "fcd.xml", actual / "fcd.xml")
    shutil.copy2(FIXTURE / "fcd.xml", source / "fcd.xml")
    shutil.copy2(FIXTURE / "network.net.xml", source / "network.net.xml")
    (source / "alias").symlink_to(actual, target_is_directory=True)
    request = _request(
        source,
        fcd_file="alias/fcd.xml",
        fcd_sha256=_sha256(actual / "fcd.xml"),
    )

    report = preflight_vec_fcd(source, source, request)

    assert report.status is VecPreflightStatus.REJECTED
    assert [item.code for item in report.findings] == ["VEC_INPUT_PATH_UNSAFE"]
