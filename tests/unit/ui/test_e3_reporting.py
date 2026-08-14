"""Tests for E3 reporting and components - deterministic, truthful emptiness."""

from __future__ import annotations

import json
import pathlib
import re

from streamlit.testing.v1 import AppTest

from traffictwin.evidence_admission.e3_research import admit_e3_research
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.reporting.e3_research import build_e3_research_exports


def test_e3_reporting_deterministic_and_no_timestamps() -> None:
    pkg = load_builtin_e3_research()
    receipt = admit_e3_research(pkg)
    b1 = build_e3_research_exports(pkg, receipt)
    b2 = build_e3_research_exports(pkg, receipt)
    assert b1.json == b2.json
    assert b1.csv == b2.csv
    assert b1.markdown == b2.markdown
    # No timestamps or randomness — strict: ISO 8601 timestamps must not appear
    iso_ts_re = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    timestamp_key_re = re.compile(r'"timestamp"\s*:')
    for txt in (b1.json, b1.csv, b1.markdown):
        assert "\r\n" not in txt
        assert not timestamp_key_re.search(txt.lower()), "export must not contain timestamp field"
        assert not iso_ts_re.search(txt), (
            f"export must not contain ISO timestamp, found {iso_ts_re.search(txt).group(0)!r}"
        )
        # No local path leaks
        assert ("/" + "Users" + "/") not in txt
        assert ("/" + "tmp" + "/") not in txt
    j = json.loads(b1.json)
    assert j["hold"]["lane_09"] == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    assert j["hold"]["evidence_state"] == "NOT_EXECUTED"
    assert j["task_accounting"]["offered"] is None
    assert "UNAVAILABLE" in b1.csv
    assert "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in b1.markdown


def test_e3_reporting_matches_typed_payload() -> None:
    pkg = load_builtin_e3_research()
    receipt = admit_e3_research(pkg)
    bundle = build_e3_research_exports(pkg, receipt)
    j = json.loads(bundle.json)
    # Provenance pins
    assert j["provenance"]["product_base_sha"] == "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c"
    assert (
        j["provenance"]["actor_sha256"]
        == "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
    )
    # Dormant counts
    assert j["dormant_counts"]["arms"] == 14
    assert j["dormant_counts"]["configs"] == 56
    # Replication
    assert j["replication"]["replication_unit"] == "fleet_draw"
    assert j["replication"]["n"] == 4
    # No numeric results - all paired differences null
    for stage in ("e3a", "e3b", "e3c"):
        for pd in j["comparison"][stage]["paired_differences"]:
            assert pd["per_seed_values"] is None
            assert pd["mean"] is None
    # Fingerprints are 64 hex
    assert re.fullmatch(r"[0-9a-f]{64}", j["package_fingerprint"])
    assert re.fullmatch(r"[0-9a-f]{64}", j["export_fingerprint"])


def test_e3_components_render_truthful_no_results(tmp_path: pathlib.Path) -> None:
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
    p = tmp_path / "e3_comp_test.py"
    p.write_text(code)
    at = AppTest.from_file(str(p))
    at.run(timeout=30)
    assert not at.exception, at.exception
    body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
        str(x.value) for x in at.caption
    )
    assert "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" in body
    assert "NOT_EXECUTED" in body
    assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" in body
    assert "UNAVAILABLE" in body
    assert "Download E3 JSON" in [b.label for b in at.download_button]
    # No placeholder numbers
    assert "coming soon" not in body.lower()


def test_e3_home_and_guided_demo_entries_present() -> None:
    from copy import deepcopy

    from traffictwin.ui.state import default_session_state

    for page in [
        "src/traffictwin/ui/app_pages/home.py",
        "src/traffictwin/ui/app_pages/guided_demo.py",
    ]:
        at = AppTest.from_file(page)
        for k, v in deepcopy(default_session_state()).items():
            at.session_state[k] = v
        at.session_state["_v07_navigation_active"] = True
        at.run(timeout=30)
        assert not at.exception, f"{page} exception {at.exception}"
        labels = [b.label for b in at.button]
        assert "Inspect E3 Dynamic Resource V2" in labels, f"E3 entry missing on {page}"
        # Unique labels
        assert len(labels) == len(set(labels)), f"duplicate labels on {page}: {labels}"
        body = "\n".join(str(x.value) for x in at.markdown) + "\n".join(
            str(x.value) for x in at.caption
        )
        assert "E3" in body


def test_e3_forbidden_claims_absent_in_rendered(tmp_path: pathlib.Path) -> None:
    # Verify that rendered E3 UI does not contain affirmative forbidden claims
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
    p = tmp_path / "e3_forbidden_check.py"
    p.write_text(code)
    at = AppTest.from_file(str(p))
    at.run(timeout=30)
    body = (
        "\n".join(str(x.value) for x in at.markdown)
        + "\n".join(str(x.value) for x in at.caption)
        + "\n".join(str(x.value) for x in at.subheader)
    )
    lower = body.lower()
    # These affirmative patterns must not appear
    assert "supervisor approved" not in lower or "no supervisor approval" in lower
    assert "k8s" not in lower
    # Check no monetary $ sign
    assert "$" not in body
    # Actor selects RSU affirmatively not present
    if "actor selects execution rsu" in lower:
        assert "no actor selects execution rsu" in lower


def test_e3_reporting_forbidden_mutated_limitations_rejected() -> None:
    """Regression: mutating limitations post-construction must be rejected in export."""
    pkg = load_builtin_e3_research()
    # Mutate limitations to inject a forbidden claim (supervisor approved)
    mutated = pkg.model_copy(update={"limitations": ["supervisor approved"]})
    # The package itself will fail validation if we try to admit, but we test export re-scan
    # Use original receipt but mutated package – export should raise via forbidden-claim scan
    receipt = admit_e3_research(pkg)
    # Build exports with mutated package – should fail closed via Lane-10 scan
    try:
        from traffictwin.reporting.e3_research import build_e3_research_exports

        build_e3_research_exports(mutated, receipt)  # type: ignore[arg-type]
        raise AssertionError("export should have raised on mutated forbidden limitation")
    except ValueError as exc:
        assert "forbidden" in str(exc).lower() or "supervisor" in str(exc).lower()
    # Also try with monetary claim
    mutated2 = pkg.model_copy(update={"limitations": ["cost is $100 dollars"]})
    try:
        build_e3_research_exports(mutated2, receipt)  # type: ignore[arg-type]
        raise AssertionError("export should have raised on monetary claim")
    except ValueError as exc:
        assert "forbidden" in str(exc).lower() or "dollar" in str(exc).lower() or "$" in str(exc)


def test_e3_reporting_rendered_constants_match_package() -> None:
    """Drift regression: every scientific constant rendered equals typed package value."""
    pkg = load_builtin_e3_research()
    # Verify that the typed package's constants are exactly the frozen identities
    assert pkg.factors["scenario_rsus"] == 10
    assert pkg.factors["padded_fleet_width"] == 2488
    assert pkg.factors["ticks_per_cell"] == 3600
    assert pkg.queue_capacity.capacity_per_rsu == 6220
    assert pkg.compute_capacity.active_units_per_rsu_range == [1, 2, 3]
    assert pkg.resource_cost.interval_seconds == 1
    assert pkg.replication.n == 4
    assert list(pkg.replication.fleet_seeds) == [1, 2, 3, 4]
    assert pkg.replication.evaluator_seed == 0
    assert pkg.replication.degrees_of_freedom == 3
    assert 3.18 < pkg.replication.critical_value < 3.19
    assert pkg.factors["state_age_ms_values"] == [0, 1000, 3000]
    assert len(pkg.dormant_arms) == 14
    assert len(pkg.dormant_configs) == 56
    # Verify reporting respects these (not hardcoded drift)
    from traffictwin.reporting.e3_research import build_e3_research_exports

    receipt = admit_e3_research(pkg)
    bundle = build_e3_research_exports(pkg, receipt)
    import json

    j = json.loads(bundle.json)
    # Check that JSON's tradeoff and rsu counts equal package
    assert j["tradeoff_structure"]["state_age_ms_allowed"] == sorted(
        pkg.factors["state_age_ms_values"]
    )
    assert j["per_rsu_structure"]["rsu_count"] == pkg.factors["scenario_rsus"]
    assert j["queue_capacity"]["capacity_per_rsu"] == pkg.queue_capacity.capacity_per_rsu
    assert j["compute_capacity"]["active_units_per_rsu_range"] == list(
        pkg.compute_capacity.active_units_per_rsu_range
    )
    assert j["resource_cost"]["interval_seconds"] == pkg.resource_cost.interval_seconds
    assert j["replication"]["n"] == pkg.replication.n
    assert j["replication"]["fleet_seeds"] == list(pkg.replication.fleet_seeds)
    assert j["dormant_counts"]["arms"] == len(pkg.dormant_arms)
    assert j["dormant_counts"]["configs"] == len(pkg.dormant_configs)
    # Extend drift regression to export TEXT (CSV/Markdown) — package-derived, not hard-coded
    # CSV replication detail and dormant reason
    assert f"N={pkg.replication.n}" in bundle.csv, "CSV must contain package-derived N"
    assert f"evaluator_seed {pkg.replication.evaluator_seed}" in bundle.csv
    assert f"{len(pkg.dormant_configs)} configs dormant" in bundle.csv, (
        "CSV dormant reason must be derived from len(dormant_configs)"
    )
    # Markdown arms/configs expected and total
    assert f"({len(pkg.dormant_arms)} expected)" in bundle.markdown
    assert f"({len(pkg.dormant_configs)} expected)" in bundle.markdown
    assert f"Total configs {len(pkg.dormant_configs)}" in bundle.markdown
    # Ensure markdown does not contain stale hard-coded opposite (would indicate drift) -
    # Also verify CSV detail uses derived values for both N and configs
    assert (
        f"fleet_draw N={pkg.replication.n} evaluator_seed {pkg.replication.evaluator_seed}"  # noqa: E501
        in bundle.csv
    )
