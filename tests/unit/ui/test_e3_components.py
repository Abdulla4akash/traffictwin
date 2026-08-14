"""Tests for E3 UI components — component-scoped, truthful no-results.

Covers individual E3 Streamlit components in isolation with the promoted Lane 10
typed package. No reporting determinism checks (those live in test_e3_reporting.py);
this file is genuinely component-scoped with non-duplicated coverage.
"""

from __future__ import annotations

import pathlib

from streamlit.testing.v1 import AppTest

from traffictwin.evidence_admission.e3_research import admit_e3_research
from traffictwin.experiments.e3_comparison import build_e3_comparison_view
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.experiments.e3_task_accounting import build_e3_task_accounting_view
from traffictwin.reporting.e3_research import build_e3_research_exports


def _render_code(tmp_path: pathlib.Path, code_fragment: str) -> AppTest:
    p = tmp_path / f"e3_component_{abs(hash(code_fragment)) % 100000}.py"
    p.write_text(code_fragment)
    at = AppTest.from_file(str(p))
    at.run(timeout=30)
    return at


def test_e3_hold_banner_renders_immutable_hold(tmp_path: pathlib.Path) -> None:
    code = """
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.evidence_admission.e3_research import admit_e3_research
from traffictwin.ui.components.e3_research import render_e3_hold_banner
pkg=load_builtin_e3_research()
receipt=admit_e3_research(pkg)
render_e3_hold_banner(pkg, receipt)
"""
    at = _render_code(tmp_path, code)
    assert not at.exception, at.exception
    body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
        str(x.value) for x in at.caption
    )
    assert "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" in body
    assert "NOT_EXECUTED" in body
    assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" in body
    assert "research_workloads_launched = 0" in body


def test_e3_admission_banner_refused_state(tmp_path: pathlib.Path) -> None:
    code = """
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.evidence_admission.e3_research import admit_e3_research
from traffictwin.ui.components.e3_research import render_e3_admission_banner
pkg=load_builtin_e3_research()
receipt=admit_e3_research(pkg)
render_e3_admission_banner(pkg, receipt)
"""
    at = _render_code(tmp_path, code)
    assert not at.exception, at.exception
    body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
        str(x.value) for x in at.caption
    )
    assert "REFUSED" in body
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" in body
    assert (
        "REFUSED_MISSING_FUTURE_ARTIFACT" in body
        or "reason_code" in body.lower()
        or "Reason code" in body
    )


def test_e3_scientific_question_uses_package_constants(tmp_path: pathlib.Path) -> None:
    pkg = load_builtin_e3_research()
    code = """
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.ui.components.e3_research import render_e3_scientific_question
pkg=load_builtin_e3_research()
render_e3_scientific_question(pkg)
"""
    at = _render_code(tmp_path, code)
    assert not at.exception, at.exception
    body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
        str(x.value) for x in at.caption
    )
    # Must use package-derived constants, not hardcoded drift
    assert str(pkg.factors["padded_fleet_width"]) in body
    assert str(pkg.factors["scenario_rsus"]) in body
    assert str(pkg.factors["ticks_per_cell"]) in body
    assert str(pkg.replication.n) in body
    assert "ingress_dla" in body
    assert "resource_unit_seconds" in body


def test_e3_strategy_semantics_renders_families(tmp_path: pathlib.Path) -> None:
    code = """
from traffictwin.experiments.e3_strategy_semantics import e3_strategy_semantics
from traffictwin.ui.components.e3_research import render_e3_strategy_semantics
sems=e3_strategy_semantics()
render_e3_strategy_semantics(sems)
"""
    at = _render_code(tmp_path, code)
    assert not at.exception, at.exception
    body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
        str(x.value) for x in at.caption
    )
    assert "ingress_dla" in body
    assert "per_task_dla" in body
    assert "p2c_dla" in body
    assert "fixed_1x" in body
    # Staleness values derived from semantics — exact typed grid, not generic digits
    assert "0, 1000, 3000 ms" in body


def test_e3_tradeoff_structure_reads_from_package(tmp_path: pathlib.Path) -> None:
    pkg = load_builtin_e3_research()
    code = """
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.ui.components.e3_research import render_e3_tradeoff_structure
pkg=load_builtin_e3_research()
render_e3_tradeoff_structure(pkg)
"""
    at = _render_code(tmp_path, code)
    assert not at.exception, at.exception
    body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
        str(x.value) for x in at.caption
    )
    assert str(pkg.queue_capacity.capacity_per_rsu) in body
    assert str(pkg.factors["scenario_rsus"]) in body
    assert "resource_unit_seconds" in body
    # Staleness grid must be package-derived, not fallback literal
    assert ", ".join(str(v) for v in pkg.factors["state_age_ms_values"]) in body
    assert str(len(pkg.dormant_arms)) in body
    assert str(len(pkg.dormant_configs)) in body


def test_e3_per_rsu_structure_uses_package_rsu_count(tmp_path: pathlib.Path) -> None:
    pkg = load_builtin_e3_research()
    code = """
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.experiments.e3_task_accounting import build_e3_task_accounting_view
from traffictwin.ui.components.e3_research import render_e3_per_rsu_and_scale_action_structure
pkg=load_builtin_e3_research()
acct=build_e3_task_accounting_view()
render_e3_per_rsu_and_scale_action_structure(pkg, acct)
"""
    at = _render_code(tmp_path, code)
    assert not at.exception, at.exception
    body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
        str(x.value) for x in at.caption
    )
    assert str(pkg.factors["scenario_rsus"]) in body
    assert "Per-RSU" in body or "per-RSU" in body.lower()
    assert "Scale-action" in body or "scale-action" in body.lower()


def test_e3_components_no_hardcoded_drift(tmp_path: pathlib.Path) -> None:
    """Drift regression: components must reflect package values, not literals."""
    pkg = load_builtin_e3_research()
    receipt = admit_e3_research(pkg)
    build_e3_comparison_view(pkg)
    build_e3_task_accounting_view()
    build_e3_research_exports(pkg, receipt)
    code = """
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.evidence_admission.e3_research import admit_e3_research
from traffictwin.experiments.e3_comparison import build_e3_comparison_view
from traffictwin.experiments.e3_task_accounting import build_e3_task_accounting_view
from traffictwin.reporting.e3_research import build_e3_research_exports
from traffictwin.ui.components.e3_research import render_e3_research
pkg=load_builtin_e3_research()
receipt=admit_e3_research(pkg)
comp=build_e3_comparison_view(pkg)
acct=build_e3_task_accounting_view()
exports=build_e3_research_exports(pkg, receipt)
render_e3_research(pkg, receipt, comp, acct, exports)
"""
    at = _render_code(tmp_path, code)
    assert not at.exception, at.exception
    body = (
        "\n".join(str(x.value) for x in at.markdown)
        + "\n".join(str(x.value) for x in at.caption)
        + "\n".join(str(x.value) for x in at.subheader)
    )
    # Verify package-derived constants appear
    assert str(pkg.factors["padded_fleet_width"]) in body
    assert str(pkg.queue_capacity.capacity_per_rsu) in body
    assert str(pkg.factors["scenario_rsus"]) in body
    assert ", ".join(str(v) for v in pkg.factors["state_age_ms_values"]) in body
    assert "Download E3 JSON" in [b.label for b in at.download_button]
