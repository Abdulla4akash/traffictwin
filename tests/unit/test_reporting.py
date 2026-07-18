from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch

from traffictwin.reporting.builder import build_comparison_report, build_run_report
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def report_clock() -> datetime:
    return datetime(2026, 7, 18, tzinfo=UTC)


def test_run_report_contains_disclaimer_without_absolute_paths(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    monkeypatch.chdir(tmp_path)

    report = build_run_report("baseline", clock=report_clock)
    markdown = report_to_markdown(report)

    assert "synthetic fixture data" in markdown
    assert str(tmp_path) not in markdown
    assert "proven cause" not in markdown.lower()


def test_comparison_report_uses_existing_delta_output(tmp_path: Path) -> None:
    baseline = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    stressed = write_synthetic_bundle(preset_config("stressed_demand"), tmp_path / "stressed")

    report = build_comparison_report(baseline, stressed, clock=report_clock)
    markdown = report_to_markdown(report)

    assert "task.completion.rate" in markdown
    assert "Direction" not in markdown
    assert "direction=" in markdown


def test_report_html_escapes_text(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    report = build_run_report(bundle, clock=report_clock)
    report = report.model_copy(update={"sections": [("Injected", ["<script>alert('x')</script>"])]})

    html = report_to_html(report)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
