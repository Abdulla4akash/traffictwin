"""Focused structural and freshness gates for the cross-regime figure."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate_cross_regime_capacity_figure.py"
PROJECTION = (
    REPO_ROOT
    / "docs"
    / "integration"
    / "evidence"
    / "vec_cross_regime_capacity_projection_20260728.json"
)
COMMITTED_OUTPUT = REPO_ROOT / "docs" / "dissertation_appendices" / "figures" / "cross_regime"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_cross_regime_capacity_figure", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    return _module()


def _projection() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(PROJECTION.read_text(encoding="utf-8"))
    return payload


def test_projection_has_five_ordered_regimes_and_deep_squeeze(generator: ModuleType) -> None:
    _, rows, deep = generator.load_projection(PROJECTION)

    assert [row.trace_id for row in rows] == ["we", "wd_pm", "ev", "wd_am", "inc"]
    assert [row.max_slots for row in rows] == [139, 163, 175, 215, 2488]
    assert [row.response_class for row in rows] == [
        "exactly_inert",
        "exactly_inert",
        "exactly_inert",
        "exactly_inert",
        "outcome_sensitive",
    ]
    assert [item.variation_arm for item in deep] == ["cap-0.5", "cap-0.25", "cap-0.1"]


def test_tampered_recorded_mean_is_refused(generator: ModuleType, tmp_path: Path) -> None:
    payload = _projection()
    payload["standard_squeeze_regimes"][-1]["mean_paired_latency_difference_ms"] = 0.0
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(generator.CrossRegimeFigureError, match="does not equal the mean"):
        generator.load_projection(path)


def test_rendered_files_carry_scope_and_exact_values(generator: ModuleType, tmp_path: Path) -> None:
    svg, tex, provenance = generator.generate_cross_regime_figure(PROJECTION, tmp_path)

    svg_text = svg.read_text(encoding="utf-8")
    assert "Etihad/Co-op Live event district" in svg_text
    assert "−6,715.239" in svg_text
    assert "cap-0.1: -0.024 ms" in svg_text
    assert "Manchester city-wide" not in svg_text

    tex_text = tex.read_text(encoding="utf-8")
    assert "-6715.239015976" in tex_text
    assert "-0.024342325" in tex_text

    note = provenance.read_text(encoding="utf-8")
    assert "not Manchester city-wide" in note
    assert "No cross-regime pooling" in note
    for row in _projection()["standard_squeeze_regimes"]:
        assert row["campaign_analysis_sha256"] in note


def test_regeneration_is_byte_deterministic(generator: ModuleType, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generator.generate_cross_regime_figure(PROJECTION, first)
    generator.generate_cross_regime_figure(PROJECTION, second)

    for path in sorted(first.iterdir()):
        assert path.read_bytes() == (second / path.name).read_bytes()


def test_committed_outputs_are_current(generator: ModuleType, tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generator.generate_cross_regime_figure(PROJECTION, generated)

    for path in sorted(generated.iterdir()):
        assert path.read_bytes() == (COMMITTED_OUTPUT / path.name).read_bytes(), path.name


def test_existing_outputs_require_explicit_overwrite(generator: ModuleType, tmp_path: Path) -> None:
    generator.generate_cross_regime_figure(PROJECTION, tmp_path)
    with pytest.raises(FileExistsError):
        generator.generate_cross_regime_figure(PROJECTION, tmp_path)
    generator.generate_cross_regime_figure(PROJECTION, tmp_path, overwrite=True)
