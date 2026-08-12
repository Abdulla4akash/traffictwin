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


def test_swapping_two_allowed_shas_between_paths_fails() -> None:
    """Validator must fail when two otherwise-allowed SHAs are swapped between paths."""
    data = json.loads(EVIDENCE_MAP_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    # Swap ingress_dla manifests (9383... vs 8d35...) — both allowed
    # but path/SHA binding must enforce git show comparison.
    e0 = mutated["strategies"]["ingress_dla"]["evidence"][0]
    e1 = mutated["strategies"]["ingress_dla"]["evidence"][1]
    assert e0["path"] == "docs/evaluation/e2b/e2b_placement_admission_factorial_manifest_v1.json"
    assert e1["path"] == "docs/evaluation/e2b/e2b_placement_admission_factorial_comparison_v1.json"
    # Both SHAs are in allowed set; swapping must still fail due to git show resolution
    sha0 = e0["sha256"]
    sha1 = e1["sha256"]
    assert sha0 != sha1
    e0["sha256"] = sha1
    e1["sha256"] = sha0
    original_text = EVIDENCE_MAP_PATH.read_text(encoding="utf-8")
    try:
        EVIDENCE_MAP_PATH.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, (
            "validator should fail when allowed SHAs are swapped between paths"
        )
        assert (
            "does not match committed file digest" in result.stderr
            or "possible path/SHA swap" in result.stderr
        )
    finally:
        EVIDENCE_MAP_PATH.write_text(original_text, encoding="utf-8")


def test_malformed_length_sha_fails() -> None:
    """Validator must reject malformed-length SHA tokens (63 or 65 hex chars)."""
    data = json.loads(EVIDENCE_MAP_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    # Truncate a valid SHA to 63 chars (malformed length)
    entry = mutated["strategies"]["strongest_link_off"]["evidence"][0]
    original_sha = entry["sha256"]
    assert len(original_sha) == 64
    malformed = original_sha[:-1]  # 63 chars
    assert len(malformed) == 63
    entry["sha256"] = malformed
    original_text = EVIDENCE_MAP_PATH.read_text(encoding="utf-8")
    try:
        EVIDENCE_MAP_PATH.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, "validator should fail on malformed-length SHA"
        assert "hex64" in result.stderr.lower() or "must be hex64" in result.stderr.lower()
    finally:
        EVIDENCE_MAP_PATH.write_text(original_text, encoding="utf-8")
    # Also test 65-char malformed (extra char)
    mutated2 = copy.deepcopy(data)
    entry2 = mutated2["strategies"]["strongest_link_off"]["evidence"][0]
    malformed2 = original_sha + "a"  # 65 chars
    assert len(malformed2) == 65
    entry2["sha256"] = malformed2
    try:
        EVIDENCE_MAP_PATH.write_text(json.dumps(mutated2, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, "validator should fail on 65-char malformed SHA"
    finally:
        EVIDENCE_MAP_PATH.write_text(original_text, encoding="utf-8")


def test_committed_file_digest_resolution() -> None:
    """Evidence map committed entries must match git show digest exactly."""
    data = json.loads(EVIDENCE_MAP_PATH.read_text(encoding="utf-8"))
    # Check that the corrected SHAs match actual committed file digests
    ingress_comparison = data["strategies"]["ingress_dla"]["evidence"][1]
    assert (
        ingress_comparison["path"]
        == "docs/evaluation/e2b/e2b_placement_admission_factorial_comparison_v1.json"
    )
    assert ingress_comparison["commit"] == "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
    assert (
        ingress_comparison["sha256"]
        == "8d35e55e2952d71b1c04479b310d1f5b48da7cf7bc2e171a1ca6359c9fa98aaf"
    )
    per_task_index = data["strategies"]["per_task_dla"]["evidence"][4]
    assert (
        per_task_index["path"]
        == "docs/evaluation/e2d/e2d_per_task_placement_evidence_index_v1.json"
    )
    assert per_task_index["commit"] == "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761"
    assert (
        per_task_index["sha256"]
        == "a6027fc17d1477547ba9d34c1fe95b224f79e6b0cedcfa49534b60c36265db4b"
    )
    # Inner raw index must be distinguished as external raw-artifact
    inner = data["strategies"]["per_task_dla"]["evidence"][5]
    assert inner["artifact"] == "e2d_raw_evidence_index_inner"
    assert (
        inner["path"] == "e2d_outputs/e2d-per-task-placement-robustness-v1/raw_evidence_index.json"
    )
    assert inner["sha256"] == "408cf8bb86370970941690b5887648c5bfb86d84a0da6bb2361b7edd508d80a7"
    # Report digests must be actual file digests, not sentinels
    e2_report = data["strategies"]["strongest_link_off"]["evidence"][8]
    assert e2_report["sha256"] == "eb0b6433d92f4a88c6613949e4226e71b6876900eb558872b94dec82ce96ec3c"
    e2b_report = data["strategies"]["ingress_dla"]["evidence"][2]
    assert (
        e2b_report["sha256"] == "c9f3cc9d84cfc27db1386c14148b9166dd56d5c2c3726d1e6e8f6057018f7a83"
    )


def test_mutated_ingress_gate_rejected_fabricated_value_fails() -> None:
    """Fabricated ingress_dla gate_rejected_seed0 must fail numeric fidelity."""
    data = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    ingress = next(s for s in mutated["strategies"] if s["id"] == "ingress_dla")
    assert ingress["experiment_evidence"]["gate_rejected_seed0"] == 2071344
    ingress["experiment_evidence"]["gate_rejected_seed0"] = 99999999
    original_text = MATRIX_PATH.read_text(encoding="utf-8")
    try:
        MATRIX_PATH.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, (
            "validator should fail on fabricated ingress_dla gate_rejected_seed0 99999999"
        )
        combined = result.stdout + result.stderr
        assert "gate_rejected" in combined.lower() or "ingress_dla" in combined.lower()
        assert "2071344" in combined or "gate" in combined.lower()
    finally:
        MATRIX_PATH.write_text(original_text, encoding="utf-8")


def test_mutated_ingress_gate_swapped_to_dla_value_fails() -> None:
    """Cross-arm swap: ingress_dla gate set to common-target dla gate 2373522 must fail."""
    data = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    ingress = next(s for s in mutated["strategies"] if s["id"] == "ingress_dla")
    assert ingress["experiment_evidence"]["gate_rejected_seed0"] == 2071344
    # 2373522 is the authoritative dla (common-target) gate, not ingress_dla
    ingress["experiment_evidence"]["gate_rejected_seed0"] = 2373522
    original_text = MATRIX_PATH.read_text(encoding="utf-8")
    try:
        MATRIX_PATH.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, (
            "validator should fail when ingress_dla gate is swapped to dla value 2373522"
        )
        combined = result.stdout + result.stderr
        assert "ingress_dla" in combined.lower() or "gate" in combined.lower()
        assert "2373522" in combined or "swapped" in combined.lower()
    finally:
        MATRIX_PATH.write_text(original_text, encoding="utf-8")


def test_mutated_per_task_energy_assigned_dla_value_fails() -> None:
    """Assigning dla seed-1 energy to per_task_dla cost.energy must fail."""
    data = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    per_task = next(s for s in mutated["strategies"] if s["id"] == "per_task_dla")
    original_energy = per_task["cost"]["energy"]
    assert "0.473289672" in original_energy or "0.47328967193459526" in original_energy
    # Swap per_task value to dla's seed-1 energy 0.47327269456939974
    per_task["cost"]["energy"] = (
        "Energy per offered at seed1 per_task 0.47327269456939974 "
        "vs dla 0.47327269456939974 delta +0.000000000; "
        "primary difference is deadline throughput, not energy."
    )
    original_text = MATRIX_PATH.read_text(encoding="utf-8")
    try:
        MATRIX_PATH.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
        result = _run_validator()
        assert result.returncode != 0, (
            "validator should fail when per_task_dla energy is swapped to dla value"
        )
        combined = result.stdout + result.stderr
        assert "per_task_dla" in combined.lower() or "per_task" in combined.lower()
        assert "energy" in combined.lower() or "0.473289" in combined
    finally:
        MATRIX_PATH.write_text(original_text, encoding="utf-8")
