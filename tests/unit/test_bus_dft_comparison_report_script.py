"""Structural coverage for the bus-versus-DfT comparison report script.

Every workspace and every edgeData file here is synthetic and built in
``tmp_path``. Nothing acquires, opens a snapshot, or reaches the network — the
script under test cannot, and these tests assert the properties that keep it
that way: the offset must be declared, aggregates only, no quarantine locator
and no absolute path in either written file, excluded hours reported with the
support they had, and no causal vocabulary anywhere in the rendered report.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from traffictwin.integration.manchester.bods_session_identity import (
    SessionProgressionMeasurement,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bus_dft_comparison_report.py"
COMMITTED_EDGEDATA = (
    REPO_ROOT / "docs" / "integration" / "evidence" / "manchester_edgedata_counts_option_a.xml"
)

#: Deliberately distinctive so a leak into either written file is unmistakable.
SNAPSHOT_IDS = ("snap-alpha-0001", "snap-beta-0002", "snap-gamma-0003")

#: Four one-hour intervals labelled 07..10 local by the accepted reducer.
SYNTHETIC_EDGEDATA = """<?xml version="1.0" encoding="UTF-8"?>
<meandata>
  <interval begin="0.00" end="3600.00" id="counts">
    <edge id="e1" entered="100"/>
  </interval>
  <interval begin="3600.00" end="7200.00" id="counts">
    <edge id="e1" entered="200"/>
  </interval>
  <interval begin="7200.00" end="10800.00" id="counts">
    <edge id="e1" entered="300"/>
  </interval>
  <interval begin="10800.00" end="14400.00" id="counts">
    <edge id="e1" entered="400"/>
  </interval>
</meandata>
"""


def _module() -> ModuleType:
    """Load the report script by path; ``scripts/`` is not an importable package."""

    spec = importlib.util.spec_from_file_location("bus_dft_comparison_report", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _progression(
    *,
    hour_utc: tuple[int, ...] = (6, 7, 8, 9),
    segments: tuple[int, ...] = (40, 50, 60, 10),
    medians: tuple[float, ...] = (8.0, 6.0, 4.0, 9.0),
) -> SessionProgressionMeasurement:
    return SessionProgressionMeasurement(
        snapshot_ids=SNAPSHOT_IDS,
        hour_utc=hour_utc,
        segment_count_by_hour=segments,
        speed_mps_median_by_hour=medians,
        speed_mps_p90_by_hour=tuple(value + 2.0 for value in medians),
        vehicles_contributing_by_hour=tuple(max(2, count // 8) for count in segments),
    )


def _workspace(tmp_path: Path, measurement: SessionProgressionMeasurement | None = None) -> Path:
    module = _module()
    workspace = tmp_path / "workspace"
    directory = workspace / module.MANCHESTER_SUBDIRECTORY
    directory.mkdir(parents=True)
    payload = (measurement if measurement is not None else _progression()).model_dump_json(indent=2)
    (directory / module.PROGRESSION_ARTIFACT_NAME).write_text(payload, encoding="utf-8")
    return workspace


def _edgedata(tmp_path: Path, text: str = SYNTHETIC_EDGEDATA) -> Path:
    path = tmp_path / "edgedata.xml"
    path.write_text(text, encoding="utf-8")
    return path


def _run(tmp_path: Path, *extra: str, workspace: Path | None = None) -> tuple[int, Path]:
    module = _module()
    output = tmp_path / "out"
    code = module.main(
        [
            str(workspace if workspace is not None else _workspace(tmp_path)),
            str(output),
            "--utc-offset-hours",
            "1",
            "--dft-edgedata",
            str(_edgedata(tmp_path)),
            *extra,
        ]
    )
    return code, output


# --- the declared offset ----------------------------------------------------


def test_the_offset_is_required_and_never_defaulted(tmp_path: Path) -> None:
    module = _module()

    with pytest.raises(SystemExit):
        module.main([str(_workspace(tmp_path)), str(tmp_path / "out")])


def test_the_declared_offset_is_carried_onto_the_artifact(tmp_path: Path) -> None:
    module = _module()

    report = module.build_comparison_report(
        _workspace(tmp_path),
        dft_edgedata_path=_edgedata(tmp_path),
        utc_to_local_offset_hours=1,
    )

    assert report.utc_to_local_offset_hours == 1


def test_a_different_offset_aligns_different_hours(tmp_path: Path) -> None:
    module = _module()
    workspace = _workspace(tmp_path)
    edgedata = _edgedata(tmp_path)

    at_one = module.build_comparison_report(
        workspace, dft_edgedata_path=edgedata, utc_to_local_offset_hours=1
    )
    at_two = module.build_comparison_report(
        workspace, dft_edgedata_path=edgedata, utc_to_local_offset_hours=2
    )

    assert at_one.aligned_hour_local_labels != at_two.aligned_hour_local_labels


# --- the comparison itself --------------------------------------------------


def test_the_accepted_comparison_is_reported_not_recomputed(tmp_path: Path) -> None:
    module = _module()

    report = module.build_comparison_report(
        _workspace(tmp_path),
        dft_edgedata_path=_edgedata(tmp_path),
        utc_to_local_offset_hours=1,
    )

    # Hours 07/08/09 clear the gate; hour 10 has 10 segments and does not.
    assert report.aligned_hour_local_labels == (7, 8, 9)
    assert report.bus_speed_mps_median_by_hour == (8.0, 6.0, 4.0)
    assert report.bus_segment_support_by_hour == (40, 50, 60)
    assert report.dft_share_by_hour == (0.1, 0.2, 0.3)
    assert report.dft_total_entered == 1_000
    assert report.spearman_rho == pytest.approx(-1.0)
    assert report.spearman_pair_count == 3


def test_excluded_hours_are_reported_with_the_support_they_had(tmp_path: Path) -> None:
    module = _module()

    report = module.build_comparison_report(
        _workspace(tmp_path),
        dft_edgedata_path=_edgedata(tmp_path),
        utc_to_local_offset_hours=1,
    )

    assert report.hours_excluded_for_support == (10,)
    assert report.excluded_hour_segment_support == (10,)
    markdown = module.render_comparison_markdown(report)
    assert "Hours excluded for support" in markdown
    assert "| 10 | 10 |" in markdown


def test_an_override_gate_changes_which_hours_survive(tmp_path: Path) -> None:
    module = _module()

    report = module.build_comparison_report(
        _workspace(tmp_path),
        dft_edgedata_path=_edgedata(tmp_path),
        utc_to_local_offset_hours=1,
        minimum_segments_per_hour=5,
    )

    assert report.minimum_segments_per_hour == 5
    assert report.aligned_hour_local_labels == (7, 8, 9, 10)
    assert report.hours_excluded_for_support == ()


def test_too_few_surviving_hours_reports_no_correlation(tmp_path: Path) -> None:
    module = _module()
    workspace = _workspace(tmp_path, _progression(segments=(40, 50, 10, 10)))

    report = module.build_comparison_report(
        workspace, dft_edgedata_path=_edgedata(tmp_path), utc_to_local_offset_hours=1
    )

    assert report.spearman_rho is None
    assert report.spearman_pair_count == 0
    markdown = module.render_comparison_markdown(report)
    assert "No Spearman value is reported" in markdown


# --- what must not travel ---------------------------------------------------


def test_no_snapshot_id_reaches_either_written_file(tmp_path: Path) -> None:
    code, output = _run(tmp_path)
    assert code == 0

    written = "\n".join(
        (output / name).read_text(encoding="utf-8")
        for name in ("bus_dft_comparison.json", "bus_dft_comparison.md")
    )
    for snapshot_id in SNAPSHOT_IDS:
        assert snapshot_id not in written
    payload = json.loads((output / "bus_dft_comparison.json").read_text(encoding="utf-8"))
    assert payload["session_snapshot_count"] == len(SNAPSHOT_IDS)
    assert payload["session_snapshot_ids_published"] is False
    assert "session_snapshot_ids" not in payload


def test_no_absolute_path_reaches_either_written_file(tmp_path: Path) -> None:
    code, output = _run(tmp_path)
    assert code == 0

    written = "\n".join(
        (output / name).read_text(encoding="utf-8")
        for name in ("bus_dft_comparison.json", "bus_dft_comparison.md")
    )
    assert str(tmp_path) not in written
    assert str(REPO_ROOT) not in written


def test_a_workspace_artifact_that_is_not_aggregate_only_is_refused(tmp_path: Path) -> None:
    module = _module()
    workspace = _workspace(tmp_path)
    artifact = workspace / module.MANCHESTER_SUBDIRECTORY / module.PROGRESSION_ARTIFACT_NAME
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["aggregates_only"] = False
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(module.BusDftComparisonReportError):
        module.build_comparison_report(
            workspace, dft_edgedata_path=_edgedata(tmp_path), utc_to_local_offset_hours=1
        )


def test_the_rendered_report_uses_no_causal_vocabulary(tmp_path: Path) -> None:
    module = _module()
    report = module.build_comparison_report(
        _workspace(tmp_path),
        dft_edgedata_path=_edgedata(tmp_path),
        utc_to_local_offset_hours=1,
    )

    markdown = module.render_comparison_markdown(report).lower()

    for banned in (
        "causes",
        "caused by",
        "because of",
        "leads to",
        "due to",
        "drives",
        "explains",
        "statistically significant",
        "ground truth",
        "scientifically validated",
        "proves",
    ):
        assert banned not in markdown
    # "validated" may only ever appear inside its own negation.
    assert markdown.count("validated") == markdown.count("not validated")
    assert "not a significance statement" in markdown
    assert "owner_approved_candidate" in markdown


def test_the_report_states_the_two_sources_stay_distinct(tmp_path: Path) -> None:
    module = _module()
    report = module.build_comparison_report(
        _workspace(tmp_path),
        dft_edgedata_path=_edgedata(tmp_path),
        utc_to_local_offset_hours=1,
    )

    assert report.bus_speed_is_not_road_speed is True
    assert report.road_counts_are_not_bus_counts is True
    assert report.significance_claimed is False
    joined = " ".join(report.limitations).lower()
    assert "not road-traffic speed" in joined
    assert "road counts are not bus counts" in joined


# --- the command ------------------------------------------------------------


def test_the_command_writes_both_artifacts(tmp_path: Path) -> None:
    code, output = _run(tmp_path)

    assert code == 0
    assert (output / "bus_dft_comparison.json").is_file()
    assert (output / "bus_dft_comparison.md").is_file()


def test_an_existing_output_is_kept_unless_overwrite_is_passed(tmp_path: Path) -> None:
    module = _module()
    code, output = _run(tmp_path)
    assert code == 0
    (output / "bus_dft_comparison.md").write_text("hand written\n", encoding="utf-8")

    workspace = _workspace(tmp_path / "second")
    assert _run(tmp_path, workspace=workspace)[0] == 1
    assert (output / "bus_dft_comparison.md").read_text(encoding="utf-8") == "hand written\n"

    assert _run(tmp_path, "--overwrite", workspace=workspace)[0] == 0
    assert "hand written" not in (output / "bus_dft_comparison.md").read_text(encoding="utf-8")
    assert module.JSON_OUTPUT_NAME == "bus_dft_comparison.json"


def test_a_workspace_without_a_progression_artifact_fails_with_a_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    workspace = tmp_path / "empty"
    (workspace / module.MANCHESTER_SUBDIRECTORY).mkdir(parents=True)

    code = module.main(
        [
            str(workspace),
            str(tmp_path / "out"),
            "--utc-offset-hours",
            "1",
            "--dft-edgedata",
            str(_edgedata(tmp_path)),
        ]
    )

    assert code == 1
    assert "no hourly progression measurement" in capsys.readouterr().err


def test_the_default_edgedata_is_the_committed_option_a_file() -> None:
    module = _module()

    assert module.DEFAULT_EDGEDATA_PATH.as_posix() == (
        "docs/integration/evidence/manchester_edgedata_counts_option_a.xml"
    )
    assert COMMITTED_EDGEDATA.is_file()


def test_the_committed_option_a_file_reduces_to_an_hourly_shape(tmp_path: Path) -> None:
    module = _module()

    report = module.build_comparison_report(
        _workspace(tmp_path),
        dft_edgedata_path=COMMITTED_EDGEDATA,
        utc_to_local_offset_hours=1,
    )

    assert report.dft_edgedata_name == COMMITTED_EDGEDATA.name
    assert report.dft_total_entered > 0
