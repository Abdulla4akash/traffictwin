"""Frozen follow-up evidence, denominator and cross-condition regressions."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

import pytest

from traffictwin.integration import followup_results
from traffictwin.integration.dissertation_results import ResultsImportError
from traffictwin.integration.followup_results import FollowupResults, load_followup_results


@pytest.fixture(scope="module")
def results() -> FollowupResults:
    return load_followup_results()


def test_completed_matrix_and_actual_all_ten_effects(results: FollowupResults) -> None:
    assert len(results.cells) == 104
    assert sum(c.reused_reference for c in results.cells) == 32
    assert len({c.block for c in results.cells}) == 8
    assert [c.mean_pp for c in results.contrasts] == pytest.approx(
        [
            0.6488842834325474,
            3.488012115405363,
            -0.01836129961034949,
            4.215340868119345,
            -3.395907452258715,
            0.8238624881765144,
            0.19333950435431646,
            3.5389505589014316,
            -3.440358265679123,
            0.549706124886356,
        ]
    )
    first = results.contrasts[0]
    assert (first.low_pp, first.high_pp) == pytest.approx((0.5171956268205418, 0.7805729400445531))
    assert results.means["08_half_speed", "per_task_dla"] == pytest.approx(89.05096014987511)
    assert results.means["09_second_actor", "per_task_dla"] == pytest.approx(93.0523111340683)
    cell = results.cells[0]
    assert cell.attainment_pct == 100 * cell.successes / cell.offered
    assert cell.attainment_pct != 100 * cell.successes / cell.admitted


def test_two_choice_explicitly_joins_reused_controls(results: FollowupResults) -> None:
    cells = results.cells_for("07_two_choice")
    assert len(cells) == 32
    assert sum(c.reused_reference for c in cells) == 24
    assert {c.arm for c in cells} == {
        "dla_p2c",
        "ingress_dla",
        "per_task_dla",
        "causal_round_robin",
    }
    assert all(c.study == "baseline" for c in cells if c.reused_reference)
    with pytest.raises(ResultsImportError, match="Unknown"):
        results.cells_for("E3")


def test_half_speed_interaction_uses_paired_original_speed_controls(
    results: FollowupResults,
) -> None:
    cells = results.cells_for("08_half_speed")
    references = results.gap_reference_cells()
    assert len(cells) == 32 and not any(c.reused_reference for c in cells)
    assert len(references) == 16 and all(c.reused_reference for c in references)
    index = {(c.study, c.block, c.arm): c.attainment_pct for c in (*cells, *references)}
    gap = next(c for c in results.contrasts if c.name == "change_in_per_task_minus_round_robin_gap")
    effects = [
        (
            index["08_half_speed", b, "per_task_dla"]
            - index["08_half_speed", b, "causal_round_robin"]
        )
        - (index["baseline", b, "per_task_dla"] - index["baseline", b, "causal_round_robin"])
        for b in range(8)
    ]
    assert gap.effects_pp == pytest.approx(effects)
    assert gap.mean_pp == pytest.approx(statistics.mean(effects))
    assert gap.mean_pp != pytest.approx(0.8238624881765144)


def test_resources_are_relocatable_original_bytes(
    results: FollowupResults,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    for name, content in results.files.items():
        assert content == (root / "docs/dissertation/followups_2026-09-15" / name).read_bytes()
    monkeypatch.chdir(tmp_path)
    assert load_followup_results() == results


def test_modified_packet_is_refused_before_rendering(
    monkeypatch: pytest.MonkeyPatch,
    results: FollowupResults,
) -> None:
    original = followup_results._resource_bytes
    monkeypatch.setattr(
        followup_results,
        "_resource_bytes",
        lambda name: (
            results.packet[:-1] + bytes([results.packet[-1] ^ 1])
            if name.endswith(".zip")
            else original(name)
        ),
    )
    with pytest.raises(ResultsImportError, match="packet fingerprint"):
        load_followup_results()


def test_missing_resource_becomes_explicit_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> bytes:
        raise FileNotFoundError("missing study")

    monkeypatch.setattr(followup_results, "_resource_bytes", missing)
    with pytest.raises(ResultsImportError, match="unavailable"):
        load_followup_results()


@pytest.mark.parametrize(
    "mutation",
    [
        "admitted_denominator",
        "duplicate_block",
        "reused_flag",
        "missing_contrast",
        "individual_interval",
        "half_speed_simple_gap",
        "wrong_seed",
    ],
)
def test_semantic_validation_rejects_misbound_results(
    results: FollowupResults, mutation: str
) -> None:
    # Exercise semantic guards independently of the enclosing byte authentication.
    originals = dict(results.files)
    analysis: dict[str, Any] = json.loads(originals["ANALYSIS.json"])
    if mutation == "admitted_denominator":
        c = analysis["cells"][0]
        c["attainment_pct"] = 100 * c["successes"] / c["admitted"]
    elif mutation == "duplicate_block":
        analysis["cells"][1] = dict(analysis["cells"][0])
    elif mutation == "reused_flag":
        analysis["cells"][0]["reused_reference"] = False
    elif mutation == "wrong_seed":
        analysis["cells"][0]["fleet_seed"] = 101
    elif mutation == "missing_contrast":
        analysis["contrasts"].pop()
    elif mutation == "individual_interval":
        c = analysis["contrasts"][0]
        c["all_ten_family95"] = c["individual95"]
    else:
        analysis["contrasts"][6]["effects_pp"] = analysis["contrasts"][5]["effects_pp"]
    originals["ANALYSIS.json"] = json.dumps(analysis).encode()
    audit = json.loads(originals["evidence/FINAL_ANALYSIS_AUDIT.json"])
    audit["analysis_sha256"] = hashlib.sha256(originals["ANALYSIS.json"]).hexdigest()
    originals["evidence/FINAL_ANALYSIS_AUDIT.json"] = json.dumps(audit).encode()
    with pytest.raises(ResultsImportError):
        followup_results._validate_values(originals)


def test_changed_audit_binding_is_rejected(results: FollowupResults) -> None:
    originals = dict(results.files)
    originals["CELL_RESULTS.csv"] += b"\n"
    with pytest.raises(ResultsImportError, match="audit binding"):
        followup_results._validate_values(originals)
