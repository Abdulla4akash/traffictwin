"""Structural coverage for the mechanism-report command line.

Every payload is synthetic and every output lands in ``tmp_path``. The committed
pilot exhibit is rendered from untracked local data, so these tests assert the
script's structure and its refusals rather than pinning bytes no other checkout
can reproduce.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collections,
)
from traffictwin.experiments import evaluate_paired_statistical_study
from traffictwin.integration.vec_campaign.mechanism_report import (
    build_mechanism_report,
    render_mechanism_report_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "render_mechanism_report.py"

FINGERPRINT = "de474e03" + "c" * 56

#: The wording the 27 July 2026 correction superseded. It must never come back.
SUPERSEDED_CLAIM = "do not overlap between adjacent arms"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_mechanism_report", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def renderer() -> ModuleType:
    return _module()


def _study() -> dict[str, Any]:
    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    payload: dict[str, Any] = json.loads(study.model_dump_json())
    return payload


def _descriptive(arm: str, metric: str, seed_values: dict[str, float]) -> dict[str, Any]:
    values = list(seed_values.values())
    return {
        "arm_label": arm,
        "metric_key": metric,
        "seed_values": seed_values,
        "mean": sum(values) / len(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def _analysis() -> dict[str, Any]:
    """Latency ranges overlap across seeds while every seed keeps the same ordering.

    That is the exact shape the corrected wording exists to describe, so the
    fixture reproduces it rather than a case where the distinction is invisible.
    """

    return {
        "schema_version": "1.0",
        "method_version": "vec-campaign-analysis-1.0",
        "experiment_id": "synthetic-mechanism-campaign",
        "design_fingerprint": FINGERPRINT,
        "campaign_status": "completed",
        "primary_metric_key": "tos.task.deadline_success.rate",
        "baseline_label": "cap-2.5",
        "admitted_collection_count": 6,
        "comparisons": [
            {
                "variation_label": "cap-1.0",
                "study_status": "available",
                "admitted_pair_count": 3,
                "mean_paired_difference": 0.0001,
                "bootstrap_lower": 0.0,
                "bootstrap_upper": 0.0003,
                "randomisation_p_value": 1.0,
                "study": _study(),
            }
        ],
        "primary_descriptives": [
            _descriptive(
                "cap-2.5", "tos.task.deadline_success.rate", {"0": 0.790, "1": 0.812, "2": 0.766}
            ),
            _descriptive(
                "cap-1.0", "tos.task.deadline_success.rate", {"0": 0.791, "1": 0.812, "2": 0.766}
            ),
        ],
        "secondary_descriptives": [
            _descriptive(
                "cap-2.5", "task.latency.mean_ms", {"0": 9942.5, "1": 6277.9, "2": 13176.0}
            ),
            # Pooled range [3961.8, 8065.2] overlaps cap-2.5's [6277.9, 13176.0],
            # yet every seed still ranks cap-1.0 below cap-2.5 — the exact shape
            # the corrected wording describes.
            _descriptive(
                "cap-1.0", "task.latency.mean_ms", {"0": 6061.7, "1": 3961.8, "2": 8065.2}
            ),
            _descriptive("cap-2.5", "task.offload.rate", {"0": 0.402608, "1": 0.406349}),
            _descriptive("cap-1.0", "task.offload.rate", {"0": 0.402608, "1": 0.406349}),
        ],
        "generated_at_utc": "2026-07-27T10:31:00+00:00",
        "research_status": "owner_approved_candidate",
        "confirmatory": False,
        "significance_claimed": False,
        "limitations": ["Exploratory owner-approved-candidate evidence only."],
    }


@pytest.fixture
def analysis_json(tmp_path: Path) -> Path:
    path = tmp_path / "campaign_analysis.json"
    path.write_text(json.dumps(_analysis()), encoding="utf-8")
    return path


@pytest.fixture
def exhibit(renderer: ModuleType, analysis_json: Path, tmp_path: Path) -> str:
    output = tmp_path / "exhibit.md"
    renderer.render_exhibit(analysis_json, output)
    return output.read_text(encoding="utf-8")


def test_the_header_states_the_source_identity(exhibit: str, analysis_json: Path) -> None:
    import hashlib

    digest = hashlib.sha256(analysis_json.read_bytes()).hexdigest()

    assert f"| Design fingerprint | `{FINGERPRINT}` |" in exhibit
    assert f"| Source SHA-256 | `{digest}` |" in exhibit
    assert "| Source analysis file | `campaign_analysis.json` |" in exhibit
    assert "| Campaign status | `completed` |" in exhibit


def test_the_header_states_the_exploratory_status(exhibit: str) -> None:
    assert "exploratory, owner_approved_candidate, descriptive non-causal" in exhibit
    assert "not supervisor approval" in exhibit
    assert "not a causal claim" in exhibit


def test_the_corrected_range_wording_is_present_and_the_old_claim_is_not(
    exhibit: str,
) -> None:
    """The superseded sentence is the one thing this exhibit must never say."""

    assert "Pooled per-arm ranges and per-seed ordering answer different questions" in exhibit
    assert "between-seed variation exceeds adjacent-arm separation" in exhibit
    assert "paired within-seed contrast is what the statistical machinery uses" in exhibit
    assert SUPERSEDED_CLAIM not in exhibit


def test_the_accepted_renderer_body_is_emitted_verbatim(exhibit: str, analysis_json: Path) -> None:
    """A header that quietly edited the report would be the worst failure here."""

    expected = render_mechanism_report_markdown(
        build_mechanism_report(json.loads(analysis_json.read_text(encoding="utf-8")))
    )

    assert exhibit.endswith(expected)


def test_the_fixture_really_exercises_overlap_with_consistent_ordering(
    analysis_json: Path,
) -> None:
    """Guards the test above: a fixture without this shape would prove nothing."""

    report = build_mechanism_report(json.loads(analysis_json.read_text(encoding="utf-8")))
    latency = [
        item for item in report.range_comparisons if item.metric_key == "task.latency.mean_ms"
    ]

    assert latency, "the fixture must record a latency range comparison"
    assert all(item.ranges_overlap for item in latency)
    assert all(item.per_seed_ordering_consistent for item in latency)


def test_analysis_limitations_are_copied_rather_than_summarised(exhibit: str) -> None:
    assert "- Exploratory owner-approved-candidate evidence only." in exhibit


def test_related_records_are_listed_when_supplied(
    renderer: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    output = tmp_path / "with_records.md"
    renderer.render_exhibit(
        analysis_json, output, related_records=["Corrected results record: see §2."]
    )
    text = output.read_text(encoding="utf-8")

    assert "## Related records" in text
    assert "- Corrected results record: see §2." in text


def test_the_related_records_section_is_absent_when_none_are_supplied(exhibit: str) -> None:
    assert "## Related records" not in exhibit


def test_both_paths_are_required_and_have_no_defaults(renderer: ModuleType) -> None:
    """Neither an input campaign nor an output location may ever be guessed."""

    with pytest.raises(SystemExit) as raised:
        renderer.main([])
    assert raised.value.code == 2

    with pytest.raises(SystemExit) as raised:
        renderer.main(["only-one-argument.json"])
    assert raised.value.code == 2


def test_an_existing_output_is_kept_unless_overwrite_is_requested(
    renderer: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    output = tmp_path / "exhibit.md"
    output.write_text("do not clobber me", encoding="utf-8")

    with pytest.raises(renderer.MechanismRenderError, match="already exists"):
        renderer.render_exhibit(analysis_json, output)
    assert output.read_text(encoding="utf-8") == "do not clobber me"

    renderer.render_exhibit(analysis_json, output, overwrite=True)
    assert "Campaign mechanism exhibit" in output.read_text(encoding="utf-8")


def test_a_missing_analysis_file_exits_non_zero(
    renderer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = renderer.main([str(tmp_path / "absent.json"), str(tmp_path / "out.md")])

    assert code == 1
    assert "analysis JSON not found" in capsys.readouterr().err
    assert not (tmp_path / "out.md").exists()


def test_a_payload_that_is_not_an_analysis_is_refused(
    renderer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "not_an_analysis.json"
    path.write_text(json.dumps({"experiment_id": "incomplete"}), encoding="utf-8")

    assert renderer.main([str(path), str(tmp_path / "out.md")]) == 1
    assert "not a valid campaign analysis" in capsys.readouterr().err


def test_rendering_is_deterministic(
    renderer: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    renderer.render_exhibit(analysis_json, first)
    renderer.render_exhibit(analysis_json, second)

    assert first.read_bytes() == second.read_bytes()


def test_main_writes_the_exhibit_and_reports_the_path(
    renderer: ModuleType, analysis_json: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "nested" / "exhibit.md"

    assert renderer.main([str(analysis_json), str(output)]) == 0
    assert f"written: {output}" in capsys.readouterr().out
    assert output.is_file()


def test_the_committed_pilot_exhibit_carries_the_corrected_wording_only() -> None:
    """The one rendered artifact this feature commits must not carry the old claim."""

    committed = REPO_ROOT / "docs" / "evaluation" / "capacity_pilot_mechanism_report_20260727.md"
    text = committed.read_text(encoding="utf-8")

    assert SUPERSEDED_CLAIM not in text
    assert "de474e038523e5e7" in text
    assert "exploratory, owner_approved_candidate, descriptive non-causal" in text
    assert "Pooled per-arm ranges and per-seed ordering answer different questions" in text
