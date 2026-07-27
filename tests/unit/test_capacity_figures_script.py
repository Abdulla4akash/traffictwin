"""Structural coverage for the capacity-study figure generator.

Every payload here is synthetic and every output lands in ``tmp_path``. The
committed figures are rendered from a local, untracked pilot analysis, so these
tests deliberately assert *structure* — which files appear, which labels reach
which rendered field, which values are copied rather than derived, and that a
rerun rewrites identical bytes — rather than pinning the committed bytes to a
source no other checkout has.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from reportlab.pdfbase.pdfmetrics import stringWidth

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collections,
)
from traffictwin.experiments import evaluate_paired_statistical_study

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate_capacity_figures.py"

FINGERPRINT = "de474e03" + "b" * 56

#: The three status words the brief requires in every figure's rendered text.
REQUIRED_LABELS = ("exploratory", "owner_approved_candidate", "descriptive non-causal")

EXPECTED_SLUGS = (
    "capacity_latency_by_seed",
    "capacity_deadline_success_by_seed",
    "capacity_deadline_success_paired_differences",
    "capacity_offload_invariance",
)


def _module() -> ModuleType:
    """Load the generator by path; ``scripts/`` is not an importable package."""

    spec = importlib.util.spec_from_file_location("generate_capacity_figures", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    return _module()


def _study() -> dict[str, Any]:
    """Build a genuine study through the accepted evaluator, not a hand-written one."""

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
    """A four-arm, three-seed campaign shaped like the pilot; callers mutate their copy."""

    arms = ("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75")
    # Latency falls with capacity, consistently within every seed.
    latency = {
        "cap-2.5": {"0": 9942.563797951792, "1": 6277.913026456375, "2": 13176.048909897081},
        "cap-1.5": {"0": 6061.686518948843, "1": 3961.8236678520807, "2": 8065.249629842364},
        "cap-1.0": {"0": 4067.9586722302943, "1": 2771.9387810405124, "2": 5429.7062705739945},
        "cap-0.75": {"0": 3060.7473606984245, "1": 2097.7063730937098, "2": 4092.3549525838084},
    }
    # Offload rate is bit-identical across every arm within each seed.
    offload = {"0": 0.4026077385889546, "1": 0.4063497181222055, "2": 0.41418079547979947}
    deadline = {
        "cap-2.5": {"0": 0.7924845945705774, "1": 0.8127939588722564, "2": 0.7659568496556425},
        "cap-1.5": {"0": 0.792816188514216, "1": 0.8127939588722564, "2": 0.7659568496556425},
        "cap-1.0": {"0": 0.793023358254372, "1": 0.8127939588722564, "2": 0.7659568496556425},
        "cap-0.75": {"0": 0.7931786782035256, "1": 0.8130743912964543, "2": 0.7659568496556425},
    }
    return {
        "schema_version": "1.0",
        "method_version": "vec-campaign-analysis-1.0",
        "experiment_id": "synthetic-capacity-campaign",
        "design_fingerprint": FINGERPRINT,
        "campaign_status": "completed",
        "primary_metric_key": "tos.task.deadline_success.rate",
        "baseline_label": "cap-2.5",
        "admitted_collection_count": 12,
        "comparisons": [
            {
                "variation_label": arm,
                "study_status": "available",
                "admitted_pair_count": 3,
                "mean_paired_difference": difference,
                "bootstrap_lower": 0.0,
                "bootstrap_upper": difference * 3,
                "randomisation_p_value": 1.0,
                "study": _study(),
            }
            for arm, difference in (
                ("cap-1.5", 0.0001105313145461917),
                ("cap-1.0", 0.00017958789459819138),
                ("cap-0.75", 0.0003248386857153858),
            )
        ],
        "primary_descriptives": [
            _descriptive(arm, "tos.task.deadline_success.rate", deadline[arm]) for arm in arms
        ],
        "secondary_descriptives": [
            *[_descriptive(arm, "task.latency.mean_ms", latency[arm]) for arm in arms],
            *[_descriptive(arm, "task.offload.rate", dict(offload)) for arm in arms],
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
def rendered(generator: ModuleType, analysis_json: Path, tmp_path: Path) -> Path:
    output = tmp_path / "figures"
    generator.generate_capacity_figures(analysis_json, output)
    return output


def test_every_projection_is_published_as_a_tex_and_svg_pair(rendered: Path) -> None:
    for slug in EXPECTED_SLUGS:
        assert (rendered / f"{slug}.tex").is_file()
        assert (rendered / f"{slug}.svg").is_file()
    assert (rendered / "provenance.md").is_file()
    assert len(list(rendered.iterdir())) == len(EXPECTED_SLUGS) * 2 + 1


def test_the_status_labels_reach_the_rendered_text_of_every_figure(rendered: Path) -> None:
    """The SVG draws the title and source line; the LaTeX fragment draws the caption.

    The two renderers surface different projection fields, so a label carried in
    only one of them would silently vanish from half the published figures.
    """

    for slug in EXPECTED_SLUGS:
        svg = (rendered / f"{slug}.svg").read_text(encoding="utf-8")
        # LaTeX escapes the underscores, so compare against unescaped text.
        tex = (rendered / f"{slug}.tex").read_text(encoding="utf-8").replace("\\_", "_")
        for label in REQUIRED_LABELS:
            assert label in svg.lower(), f"{slug}.svg is missing {label!r}"
            assert label in tex.lower(), f"{slug}.tex is missing {label!r}"


def test_rendered_svg_text_fits_inside_the_accepted_canvas(
    generator: ModuleType, rendered: Path
) -> None:
    """A title long enough to carry the labels would clip; this pins that it does not.

    The accepted renderer draws a fixed 1000px-wide canvas with no wrapping, so
    an over-long title or source line is silently truncated by the viewport
    rather than rejected. Nothing else in the pipeline would catch it.
    """

    budget = generator.FIGURE_TEXT_BUDGET_PX
    for slug in EXPECTED_SLUGS:
        svg = (rendered / f"{slug}.svg").read_text(encoding="utf-8")
        title = re.search(r'font-size="24"[^>]*>([^<]+)<', svg)
        source = re.search(r'font-size="13" fill="#526473">([^<]+)<', svg)
        assert title is not None and source is not None
        assert stringWidth(title.group(1), "Helvetica-Bold", 24) <= budget, slug
        assert stringWidth(source.group(1), "Helvetica", 13) <= budget, slug


def test_the_latency_figure_draws_one_bar_per_seed_and_arm_seed_major(
    generator: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    """Each seed's four capacity points must be one contiguous run, in arm order."""

    figures = generator.generate_capacity_figures(analysis_json, tmp_path / "out")
    latency = next(item for item in figures if item.slug == "capacity_latency_by_seed")
    labels = [entry.label for entry in latency.projection.figure_entries]

    assert labels == [
        f"seed {seed} at {arm}"
        for seed in ("0", "1", "2")
        for arm in ("cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75")
    ]
    assert all(entry.numeric_value is not None for entry in latency.projection.figure_entries)


def test_table_cells_carry_full_round_trip_precision(rendered: Path) -> None:
    """Rounded cells could print two different values identically beside an
    'identical across arms' verdict, which would read as evidence it is not."""

    tex = (rendered / "capacity_offload_invariance.tex").read_text(encoding="utf-8")

    assert "0.4026077385889546" in tex
    assert float("0.4026077385889546") == 0.4026077385889546


def test_invariance_categories_come_from_the_accepted_exact_equality_check(
    generator: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    figures = generator.generate_capacity_figures(analysis_json, tmp_path / "out")
    invariance = next(item for item in figures if item.slug == "capacity_offload_invariance")
    categories = {entry.label: entry.category for entry in invariance.projection.figure_entries}

    assert categories["task.offload.rate seed 0"] == generator.IDENTICAL
    assert categories["task.offload.rate seed 1"] == generator.IDENTICAL
    assert categories["task.latency.mean_ms seed 0"] == generator.VARIES
    # The primary endpoint is flat but not identical in seed 0, and identical in seed 2.
    assert categories["tos.task.deadline_success.rate seed 0"] == generator.VARIES
    assert categories["tos.task.deadline_success.rate seed 2"] == generator.IDENTICAL
    entries = invariance.projection.figure_entries
    assert all(entry.numeric_value is None for entry in entries)


def test_paired_differences_are_copied_from_the_analysis_not_recomputed(
    generator: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    figures = generator.generate_capacity_figures(analysis_json, tmp_path / "out")
    differences = next(
        item for item in figures if item.slug == "capacity_deadline_success_paired_differences"
    )
    recorded = [comparison["mean_paired_difference"] for comparison in _analysis()["comparisons"]]

    assert [entry.numeric_value for entry in differences.projection.figure_entries] == recorded


def test_regeneration_rewrites_identical_bytes(
    generator: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    """A generator that churned on rerun would make every regeneration a fake diff."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    generator.generate_capacity_figures(analysis_json, first)
    generator.generate_capacity_figures(analysis_json, second)

    for path in sorted(first.iterdir()):
        assert path.read_bytes() == (second / path.name).read_bytes(), path.name


def test_existing_outputs_are_kept_unless_overwrite_is_requested(
    generator: ModuleType, analysis_json: Path, rendered: Path
) -> None:
    with pytest.raises(FileExistsError):
        generator.generate_capacity_figures(analysis_json, rendered)

    generator.generate_capacity_figures(analysis_json, rendered, overwrite=True)


def test_the_analysis_path_is_required_and_has_no_default(generator: ModuleType) -> None:
    """The script must never be able to reach for a campaign directory on its own."""

    with pytest.raises(SystemExit) as raised:
        generator.main([])

    assert raised.value.code == 2


def test_a_missing_analysis_file_exits_non_zero(
    generator: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert generator.main([str(tmp_path / "absent.json"), "--output-dir", str(tmp_path)]) == 1
    assert "analysis JSON not found" in capsys.readouterr().err


def test_a_payload_that_is_not_an_analysis_is_refused(
    generator: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "not_an_analysis.json"
    path.write_text(json.dumps({"experiment_id": "incomplete"}), encoding="utf-8")

    assert generator.main([str(path), "--output-dir", str(tmp_path / "out")]) == 1
    assert "not a valid campaign analysis" in capsys.readouterr().err


def test_an_absent_latency_metric_is_named_rather_than_rendered_empty(
    generator: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    with pytest.raises(generator.CapacityFigureError, match="no secondary metric"):
        generator.generate_capacity_figures(
            analysis_json, tmp_path / "out", latency_metric="task.nonexistent"
        )


def test_the_provenance_note_records_the_source_identity_and_every_fingerprint(
    generator: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    """The source analysis is untracked local data, so the digest is the only
    link a later reader has between a committed figure and what produced it."""

    output = tmp_path / "out"
    figures = generator.generate_capacity_figures(analysis_json, output)
    note = (output / "provenance.md").read_text(encoding="utf-8")

    assert FINGERPRINT in note
    assert "campaign_analysis.json" in note
    assert "synthetic-capacity-campaign" in note
    for figure in figures:
        assert figure.projection.fingerprint() in note
        for item in figure.receipt.files:
            assert item.checksum_sha256 in note
    assert "Exploratory owner-approved-candidate evidence only." in note


def test_the_provenance_note_carries_no_wall_clock_or_absolute_path(
    generator: ModuleType, analysis_json: Path, tmp_path: Path
) -> None:
    output = tmp_path / "out"
    generator.generate_capacity_figures(analysis_json, output)
    note = (output / "provenance.md").read_text(encoding="utf-8")

    assert str(tmp_path) not in note
    # The only timestamp is the one the analysis itself recorded.
    assert note.count("2026-07-27T10:31:00+00:00") == 1
