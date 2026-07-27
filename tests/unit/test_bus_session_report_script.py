"""Structural coverage for the attended bus-session post-session report.

Every workspace here is synthetic and built in ``tmp_path``. Nothing acquires,
opens a snapshot, or reaches the network — the script under test cannot, and
these tests assert the properties that keep it that way: aggregates only, no
identifier of any kind in the rendered report, and measured values presented as
B1 candidates rather than as chosen thresholds.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from traffictwin.integration.manchester.bods_session_identity import (
    SessionCadenceMeasurement,
    SessionProgressionMeasurement,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bus_session_report.py"
EDGEDATA = (
    REPO_ROOT / "docs" / "integration" / "evidence" / "manchester_edgedata_counts_option_a.xml"
)

#: Deliberately distinctive so a leak into the rendered report is unmistakable.
SNAPSHOT_IDS = ("snap-alpha-0001", "snap-beta-0002", "snap-gamma-0003")


def _module() -> ModuleType:
    """Load the report script by path; ``scripts/`` is not an importable package."""

    spec = importlib.util.spec_from_file_location("bus_session_report", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report_script() -> ModuleType:
    return _module()


def _cadence() -> SessionCadenceMeasurement:
    """A night-probe-shaped cadence measurement: mostly stale, a few live vehicles."""

    return SessionCadenceMeasurement(
        snapshot_ids=SNAPSHOT_IDS,
        snapshot_count=len(SNAPSHOT_IDS),
        vehicles_seen_total=872,
        vehicles_linked_across_snapshots=41,
        observation_count=12960,
        repeated_identical_fix_count=11672,
        update_delta_seconds_median=68.0,
        update_delta_seconds_p90=75.0,
        update_delta_seconds_max=11520.0,
        displacement_m_median=418.0,
        displacement_m_p90=910.0,
        displacement_m_max=1980.0,
        implied_speed_mps_max=28.4,
    )


def _progression() -> SessionProgressionMeasurement:
    return SessionProgressionMeasurement(
        snapshot_ids=SNAPSHOT_IDS[:2],
        # Deliberately out of order, so the report's sorting is actually exercised.
        hour_utc=(9, 7, 8),
        segment_count_by_hour=(120, 60, 240),
        speed_mps_median_by_hour=(6.0, 4.0, 8.0),
        speed_mps_p90_by_hour=(9.0, 6.0, 12.0),
        vehicles_contributing_by_hour=(30, 12, 55),
    )


def _workspace(
    tmp_path: Path,
    *,
    cadence: SessionCadenceMeasurement | None = None,
    progression: SessionProgressionMeasurement | None = None,
) -> Path:
    workspace = tmp_path / "workspace"
    manchester = workspace / "manchester"
    manchester.mkdir(parents=True)
    if cadence is not None:
        (manchester / "bus_cadence_probe_measurement.json").write_text(
            cadence.model_dump_json(), encoding="utf-8"
        )
    if progression is not None:
        (manchester / "bus_session_progression_measurement.json").write_text(
            progression.model_dump_json(), encoding="utf-8"
        )
    return workspace


@pytest.fixture
def full_report(report_script: ModuleType, tmp_path: Path) -> str:
    workspace = _workspace(tmp_path, cadence=_cadence(), progression=_progression())
    return str(report_script.render_session_report(workspace))


def test_the_artifact_names_match_the_accepted_bus_sessions_surface(
    report_script: ModuleType,
) -> None:
    """Two independent readers of the same files must not drift apart on the names."""

    from traffictwin.ui import bus_sessions_services

    assert report_script.CADENCE_ARTIFACT_NAME == bus_sessions_services.CADENCE_ARTIFACT_NAME
    assert (
        report_script.PROGRESSION_ARTIFACT_NAME == bus_sessions_services.PROGRESSION_ARTIFACT_NAME
    )
    assert report_script.MANCHESTER_SUBDIRECTORY == bus_sessions_services.MANCHESTER_SUBDIRECTORY


def test_a_workspace_without_a_manchester_directory_is_refused(
    report_script: ModuleType, tmp_path: Path
) -> None:
    with pytest.raises(report_script.BusSessionReportError, match="no manchester/ directory"):
        report_script.render_session_report(tmp_path / "empty")


def test_a_workspace_with_neither_artifact_is_refused(
    report_script: ModuleType, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)

    with pytest.raises(report_script.BusSessionReportError, match="neither measurement artifact"):
        report_script.render_session_report(workspace)


def test_cadence_percentiles_and_active_vehicle_counts_are_reported(full_report: str) -> None:
    assert "| Vehicles seen | 872 |" in full_report
    assert "| Vehicles actively updating (linked across snapshots) | 41 |" in full_report
    assert "| Update interval (s) | 68.000 | 75.000 | 11520.000 |" in full_report
    assert "| Displacement (m) | 418.000 | 910.000 | 1980.000 |" in full_report
    assert "28.400 m/s" in full_report


def test_the_stale_fix_share_is_stated_as_two_counts_not_a_bare_percentage(
    full_report: str,
) -> None:
    """The B1 draft states it as 'N of M'; a lone percentage loses the support."""

    assert "11672 of 12960 linked observations (90.1%)" in full_report


def test_hourly_progression_rows_are_ordered_by_utc_hour(full_report: str) -> None:
    hourly = [line for line in full_report.splitlines() if line.startswith("| 0")]

    assert hourly == [
        "| 07 | 60 | 12 | 4.000 | 6.000 |",
        "| 08 | 240 | 55 | 8.000 | 12.000 |",
        "| 09 | 120 | 30 | 6.000 | 9.000 |",
    ]


def test_no_snapshot_id_token_or_salt_reaches_the_rendered_report(full_report: str) -> None:
    """Identifiers must be absent from the reported data, not merely disclaimed.

    The closing section names tokens, salts, and snapshot ids in order to deny
    publishing them, so the check runs over everything above it — where a real
    leak would land — rather than over the disclaimer that mentions the words.
    """

    reported, _, denial = full_report.partition("## 6. What this report is not")
    assert denial, "the boundaries section must exist for this split to be meaningful"

    for snapshot_id in SNAPSHOT_IDS:
        assert snapshot_id not in full_report, "an id must not leak even into the disclaimer"
    lowered = reported.lower()
    for forbidden in ("session_token", "salt", "vehicleref", "vehicle_ref"):
        assert forbidden not in lowered, f"{forbidden!r} reached the reported data"
    # The count is published; the ids behind it are not.
    assert "| Snapshots in session | 3 |" in reported


def test_the_b1_block_separates_measured_values_from_owner_thresholds(
    full_report: str,
) -> None:
    """A measurement that silently became a threshold is the failure this guards."""

    assert "B1 FILL-FROM-PROBE candidate values" in full_report
    assert "median 68.000 s / p90 75.000 s" in full_report
    # The two rows that could be misread as decisions must say they are not.
    assert "28.400 m/s | **informs** the `FILL-AT-SIGNING` bound; does not set it |" in full_report
    assert "11520.000 s | **informs** the `FILL-AT-SIGNING` ceiling; does not set it |" in (
        full_report
    )
    assert "not decisions" in full_report


def test_the_busiest_hour_informs_the_trace_window_without_choosing_it(
    full_report: str,
) -> None:
    assert "08 UTC with 55 contributing vehicles" in full_report
    assert "linked-vehicle" in full_report


def test_an_absent_progression_artifact_reports_the_recorded_reason(
    report_script: ModuleType, tmp_path: Path
) -> None:
    """Its absence is normal — no runner writes one — and must not read as failure."""

    workspace = _workspace(tmp_path, cadence=_cadence())
    report = report_script.render_session_report(workspace)

    assert "No attended-session runner writes a progression measurement yet" in report
    assert "| Vehicles seen | 872 |" in report


def test_an_artifact_that_is_not_aggregate_only_is_refused(
    report_script: ModuleType, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path, cadence=_cadence())
    tampered = workspace / "manchester" / "bus_cadence_probe_measurement.json"
    tampered.write_text(
        tampered.read_text(encoding="utf-8").replace(
            '"raw_identifiers_published":false', '"raw_identifiers_published":true'
        ),
        encoding="utf-8",
    )

    with pytest.raises(report_script.BusSessionReportError, match="neither measurement artifact"):
        report_script.render_session_report(workspace)


def test_the_comparison_is_absent_and_says_why_when_no_edgedata_is_supplied(
    full_report: str,
) -> None:
    assert "No --dft-edgedata file was supplied, so no comparison was attempted." in full_report


def test_the_comparison_runs_through_the_accepted_module_when_edgedata_is_supplied(
    report_script: ModuleType, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path, cadence=_cadence(), progression=_progression())

    report = report_script.render_session_report(
        workspace, dft_edgedata_path=EDGEDATA, utc_to_local_offset_hours=1
    )

    assert "| DfT source SHA-256 |" in report
    assert "| UTC-to-local offset applied | 1 h |" in report
    assert "bus progression speed is not road speed" in report


def test_an_unreadable_edgedata_file_is_an_unavailable_state_not_a_crash(
    report_script: ModuleType, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path, cadence=_cadence(), progression=_progression())

    report = report_script.render_session_report(
        workspace, dft_edgedata_path=tmp_path / "absent.xml"
    )

    assert "The edgeData file could not be reduced to an hourly shape" in report


def test_the_report_denies_road_traffic_and_acquisition_explicitly(full_report: str) -> None:
    assert "never road-traffic speed" in full_report
    assert "road-traffic volume is not available" in full_report
    assert "No BODS call, no API key, no network access" in full_report


def test_rendering_is_deterministic(report_script: ModuleType, tmp_path: Path) -> None:
    """A wall-clock stamp would make every report differ from the last one."""

    workspace = _workspace(tmp_path, cadence=_cadence(), progression=_progression())

    first = report_script.render_session_report(workspace)
    second = report_script.render_session_report(workspace)

    assert first == second


def test_the_workspace_argument_is_required_and_has_no_default(
    report_script: ModuleType,
) -> None:
    with pytest.raises(SystemExit) as raised:
        report_script.main([])

    assert raised.value.code == 2


def test_main_writes_to_an_output_path_when_asked(
    report_script: ModuleType, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path, cadence=_cadence())
    destination = tmp_path / "reports" / "session.md"

    assert report_script.main([str(workspace), "--output", str(destination)]) == 0
    assert "| Vehicles seen | 872 |" in destination.read_text(encoding="utf-8")


def test_main_reports_an_unreadable_workspace_on_stderr(
    report_script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert report_script.main([str(tmp_path / "absent")]) == 1
    assert "no manchester/ directory" in capsys.readouterr().err
