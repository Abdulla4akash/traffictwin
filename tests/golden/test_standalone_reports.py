from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch

from traffictwin.reporting.builder import build_run_report
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def fixed_report_clock() -> datetime:
    return datetime(2026, 7, 18, tzinfo=UTC)


def test_standalone_baseline_report_matches_golden(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    monkeypatch.chdir(tmp_path)

    actual = report_to_markdown(build_run_report("baseline", clock=fixed_report_clock))
    expected = (Path(__file__).parent / "expected" / "standalone_baseline_report.md").read_text(
        encoding="utf-8"
    )

    assert actual == expected
