from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch

from traffictwin.reporting import build_run_report as build_run_report_public
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.models import ReportClaimKind, ResearchReportType
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


def test_report_builders_publish_exact_typed_claim_inventories(tmp_path: Path) -> None:
    baseline = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    stressed = write_synthetic_bundle(preset_config("stressed_demand"), tmp_path / "stressed")

    run = build_run_report_public(baseline, clock=report_clock)
    diagnostics = build_diagnostics_report(baseline, clock=report_clock)
    comparison = build_comparison_report(baseline, stressed, clock=report_clock)
    full = build_full_report(stressed, comparison_baseline=baseline, clock=report_clock)

    assert run.report_type is ResearchReportType.RUN
    assert diagnostics.report_type is ResearchReportType.DIAGNOSTICS
    assert comparison.report_type is ResearchReportType.COMPARISON
    assert full.report_type is ResearchReportType.FULL
    assert len(run.claim_references) == len(diagnostics.claim_references) == 33
    assert len(comparison.claim_references) == 14
    assert len(full.claim_references) == 47
    assert len(run.claim_snapshots) == len(run.claim_references)
    assert len(diagnostics.claim_snapshots) == len(diagnostics.claim_references)
    assert len(comparison.claim_snapshots) == len(comparison.claim_references)
    assert len(full.claim_snapshots) == len(full.claim_references)
    assert {item.claim_id for item in full.claim_snapshots} == {
        item.claim_id for item in full.claim_references
    }
    assert len({claim.claim_id for claim in full.claim_references}) == 47
    assert {claim.claim_kind for claim in run.claim_references} == {
        ReportClaimKind.METRIC_RESULT,
        ReportClaimKind.RULE_RESULT,
    }
    assert {claim.claim_kind for claim in comparison.claim_references} == {
        ReportClaimKind.METRIC_COMPARISON
    }
    assert len(run.claim_exclusions) == 3
    assert len(comparison.claim_exclusions) == 4


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
