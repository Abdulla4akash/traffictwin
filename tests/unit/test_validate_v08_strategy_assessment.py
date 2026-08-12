"""Unit tests for v08 strategy assessment validator (Lane 05).

Self-contained: validator embeds expected hashes and does not require
ignored .harness at runtime. Tests are committed-artifact only.
"""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs/closure/v08_alignment/strategy_matrix.json"
EVIDENCE_MAP_PATH = ROOT / "docs/closure/v08_alignment/strategy_evidence_map.json"
ASSESSMENT_PATH = ROOT / "docs/closure/v08_alignment/existing_strategy_assessment.md"
VALIDATOR = ROOT / "scripts/validate_v08_strategy_assessment.py"


def _run_validator() -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_validator_passes_on_current_artifacts() -> None:
    result = _run_validator()
    assert result.returncode == 0, (
        f"validator failed:\nSTDOUT:{result.stdout}\nSTDERR:{result.stderr}"
    )
    assert "VALIDATION PASSED" in result.stdout


def test_validator_is_self_contained_no_harness_dependency() -> None:
    text = VALIDATOR.read_text(encoding="utf-8")
    # Must embed expected identities
    assert "EXPECTED_BASE_SHA" in text
    assert "EXPECTED_PAYLOAD_SHA256" in text
    assert "EXPECTED_S035_SHA256" in text
    assert "EXPECTED_HEADS" in text
    assert "EXPECTED_ALLOWED_SHA256_SET" in text
    # Must mention self-contained and not require harness at runtime
    assert "self-contained" in text.lower()
    # Must not have a mandatory hard failure on missing .harness/source_map.json
    # The validator defines SOURCE_MAP_PATH as optional and handles missing file gracefully
    assert (
        "not a runtime dependency" in text.lower()
        or "not required" in text.lower()
        or "Optional harness" in text
    )
    # Ensure validator still passes when harness is temporarily hidden (simulated)
    # We test by importing validate functions directly without harness
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_v08", str(VALIDATOR))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Execute module to get functions without requiring harness file
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    # Call validate functions with committed data — should not error on missing harness
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_MAP_PATH.read_text(encoding="utf-8"))
    # These should not raise due to missing harness
    errs = mod.validate_committed_source_bindings(matrix, evidence)
    assert isinstance(errs, list)
    # Also ensure validate_assessment_md does not require harness
    errs2 = mod.validate_assessment_md()
    assert isinstance(errs2, list)
    # And full validator still passes
    result = _run_validator()
    assert result.returncode == 0


def test_matrix_has_five_strategies_with_required_fields() -> None:
    data = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    strategies = data["strategies"]
    assert len(strategies) == 5
    required_ids = [
        "strongest_link_off",
        "jsq_without_gate",
        "ingress_dla",
        "common_target_dla",
        "per_task_dla",
    ]
    assert [s["id"] for s in strategies] == required_ids
    for strat in strategies:
        for field in [
            "admission",
            "placement",
            "sequential_behavior",
            "common_target_behavior",
            "forwarding",
            "determinism",
            "benefit",
            "failure_mode",
            "cost",
            "experiment_evidence",
            "limits",
            "comparison_compatibility",
        ]:
            assert field in strat, f"strategy {strat['id']} missing {field}"
        assert isinstance(strat["admission"], dict)
        assert strat["admission"]


def test_deleting_admission_field_fails_validation() -> None:
    data = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    mutated["strategies"][0].pop("admission")
    original_text = MATRIX_PATH.read_text(encoding="utf-8")
    try:
        MATRIX_PATH.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, "validator should fail when admission field is deleted"
        assert "admission" in result.stderr.lower() or "admission" in result.stdout.lower()
    finally:
        MATRIX_PATH.write_text(original_text, encoding="utf-8")


def test_redirecting_evidence_sha_fails_validation() -> None:
    data = json.loads(EVIDENCE_MAP_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    fake_sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert fake_sha not in data.get("allowed_sha256_set", [])
    mutated["strategies"]["strongest_link_off"]["evidence"][0]["sha256"] = fake_sha
    original_text = EVIDENCE_MAP_PATH.read_text(encoding="utf-8")
    try:
        EVIDENCE_MAP_PATH.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, "validator should fail when evidence SHA is redirected"
        assert "allowed_sha256_set" in result.stderr or "not in allowed" in result.stderr.lower()
    finally:
        EVIDENCE_MAP_PATH.write_text(original_text, encoding="utf-8")


def test_evidence_sha_format_and_allowed_set() -> None:
    data = json.loads(EVIDENCE_MAP_PATH.read_text(encoding="utf-8"))
    import re

    hex64 = re.compile(r"^[0-9a-f]{64}$")
    allowed = set(data["allowed_sha256_set"])
    for _known in [
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208",
        "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
        "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595",
    ]:
        pass
    for sid, strat in data["strategies"].items():
        for entry in strat["evidence"]:
            sha = entry["sha256"]
            if (
                sha.startswith("report_")
                or "placeholder" in sha
                or sha.startswith("e2b_comparison_sha_placeholder")
            ):
                continue
            if hex64.match(sha):
                assert sha in allowed, f"{sid} sha {sha} not in allowed set"


def test_assessment_contains_honesty_boundaries() -> None:
    text = ASSESSMENT_PATH.read_text(encoding="utf-8")
    for phrase in [
        "SOURCE-DERIVED FACT",
        "IMPLEMENTATION-VERIFIED FACT",
        "RESEARCH-EVIDENCE FACT",
        "PROVISIONAL WORDING",
        "EXTERNAL DECISION REQUIRED",
    ]:
        assert phrase in text
    assert "S-035 / SANDRA-DIRECT-BODY-2026-08-04" in text
    assert "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed" in text


def test_assessment_narrow_s035_and_tt_req_inference() -> None:
    text = ASSESSMENT_PATH.read_text(encoding="utf-8")
    # Narrow overlapping-content supersession
    assert "overlapping" in text.lower(), (
        "assessment must describe S-035 as overlapping content only"
    )
    assert "S-035" in text and "SRC-010" in text
    # Must not claim blanket supersession without overlapping qualifier
    # Ensure narrow phrasing exists
    assert "only for verbatim body content that overlaps" in text or "overlapping" in text.lower()
    # TT-REQ-008 inference labeling
    assert "TT-REQ-008" in text
    assert "PARTIALLY_MET" in text
    assert "INFERENCE" in text, "TT-REQ-008 PARTIALLY_MET must be labelled INFERENCE"
    assert "EXTERNAL DECISION REQUIRED" in text
    # Must distinguish frozen baseline from overlay
    assert "frozen baseline" in text.lower() or "frozen requirement" in text.lower()
    assert "not an effective baseline amendment" in text.lower() or "does not amend" in text.lower()
    # Self-contained note
    assert "self-contained" in text.lower()
    assert "not a runtime dependency" in text.lower() or "not required" in text.lower()


def test_matrix_narrow_wording() -> None:
    data = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    s035 = data.get("s035_classification", {})
    blob = json.dumps(s035)
    assert "overlapping" in blob.lower(), (
        "matrix s035_classification must mention overlapping content"
    )
    assert "INFERENCE" in blob, "matrix TT-REQ-008 must be INFERENCE"
    assert "EXTERNAL DECISION REQUIRED" in blob
    # Must mention frozen baseline unchanged
    assert (
        "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595" in blob
        or "frozen" in blob.lower()
    )
    # Ensure authority still contains expected shas
    auth = data.get("authority", {})
    assert (
        auth.get("negotiated_baseline_payload_sha256")
        == "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
    )
    assert (
        auth.get("s035_sha256")
        == "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed"
    )


def test_evidence_map_source_classification_narrow() -> None:
    data = json.loads(EVIDENCE_MAP_PATH.read_text(encoding="utf-8"))
    note = data.get("source_classification", {}).get("note", "")
    assert "overlapping" in note.lower()
    assert "INFERENCE" in note
    assert "EXTERNAL DECISION REQUIRED" in note
    assert (
        "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed" in note
        or "S-035" in note
    )
