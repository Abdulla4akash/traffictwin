from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffictwin.case_studies.builder import build_synthetic_case_study_pack
from traffictwin.ingestion.bundle import validate_bundle


def test_case_study_pack_builds_three_valid_synthetic_scenarios(tmp_path: Path) -> None:
    output = tmp_path / "case-study"
    generated = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)

    manifest = build_synthetic_case_study_pack(output, clock=lambda: generated)

    assert manifest.synthetic is True
    assert manifest.generated_at == generated
    assert manifest.scenario_ids == [
        "case-baseline",
        "case-incident-demand",
        "case-infrastructure-reduced",
    ]
    assert (output / "manifest.json").is_file()
    assert any(artifact.kind == "research_report" for artifact in manifest.artifacts)
    assert all(len(artifact.sha256) == 64 for artifact in manifest.artifacts)
    for scenario_id in manifest.scenario_ids:
        validation = validate_bundle(output / "bundles" / scenario_id)
        assert validation.report.may_import is True


def test_case_study_pack_refuses_implicit_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "case-study"
    build_synthetic_case_study_pack(output)

    with pytest.raises(FileExistsError):
        build_synthetic_case_study_pack(output)

    replacement = build_synthetic_case_study_pack(output, overwrite=True)
    assert replacement.synthetic is True
