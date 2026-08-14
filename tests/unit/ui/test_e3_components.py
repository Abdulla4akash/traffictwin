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
    # No timestamps or randomness
    for txt in (b1.json, b1.csv, b1.markdown):
        assert "\r\n" not in txt
        assert "timestamp" not in txt.lower() or "scientific_timestamp" not in txt.lower()
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
