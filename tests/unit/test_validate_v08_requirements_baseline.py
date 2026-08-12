"""Tests for v08 requirements baseline validator.

Focused gate: validates the six allowed files without launching SUMO/VEC/evaluators.
Self-contained: recomputes hashes from committed JSON payload fields only;
no runtime dependency on .harness.
"""

from __future__ import annotations

import copy
import json
import pathlib

import scripts.validate_v08_requirements_baseline as validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BASELINE_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_baseline_v1.json"
SOURCE_MAP_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_source_map.json"
STATUS_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_status_v08.json"


def test_payload_hash_recomputed() -> None:
    assert (
        validator.compute_payload_hash()
        == "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
    )


def test_whole_file_hash_recomputed() -> None:
    assert (
        validator.compute_whole_hash()
        == "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2"
    )


def test_baseline_json_counts() -> None:
    data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    assert data["total_requirements"] == 14
    assert data["must_count"] == 11
    assert data["should_count"] == 2
    assert data["may_count"] == 1
    assert len(data["requirements"]) == 14


def test_ids_unique_and_complete() -> None:
    data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    ids = [r["id"] for r in data["requirements"]]
    assert len(ids) == len(set(ids))
    assert set(ids) == {f"TT-REQ-{i:03d}" for i in range(1, 15)}


def test_all_must_have_acceptance_criteria() -> None:
    data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    for r in data["requirements"]:
        if r["priority"] == "MUST":
            assert (
                isinstance(r["acceptance_criteria"], list) and len(r["acceptance_criteria"]) > 0
            ), r["id"]


def test_canonical_quotations_no_drift() -> None:
    payload_map = validator.extract_canonical_quotations_from_payload()
    data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    for r in data["requirements"]:
        rid = r["id"]
        assert r["canonical_quotation"] == payload_map[rid], f"drift {rid}"


def test_sources_resolve() -> None:
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    source_map = json.loads(SOURCE_MAP_JSON.read_text(encoding="utf-8"))
    resolvable: set[str] = set()
    for s in source_map.get("sources", []):
        resolvable.add(s["id"])
    for s in source_map.get("extended_index", []):
        resolvable.add(s["id"])
    for r in baseline["requirements"]:
        for sid in r["source_basis"]:
            base = sid.split()[0] if " " in sid else sid
            if sid.startswith("S-035"):
                base = "S-035"
            assert base in resolvable, f"{r['id']} unresolved source {sid}"


def test_conditional_triggers_explicit() -> None:
    data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in data["requirements"]}
    for rid in ["TT-REQ-011", "TT-REQ-012", "TT-REQ-013"]:
        assert by_id[rid]["conditional_trigger"] is True, rid
        assert by_id[rid]["conditional_trigger_text"], rid
    assert by_id["TT-REQ-008"]["conditional_trigger"] is True
    assert by_id["TT-REQ-014"]["conditional_trigger"] is True


def test_status_vocabulary_closed() -> None:
    status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    allowed = {"VERIFIED_MET", "PARTIALLY_MET", "NOT_APPLICABLE", "DECISION_REQUIRED"}
    for r in status["requirements"]:
        assert r["status"] in allowed, r["id"]
        if r["priority"] == "MUST":
            assert r["status"] in {"VERIFIED_MET", "PARTIALLY_MET", "NOT_APPLICABLE"}, r["id"]


def test_every_partial_has_named_gap() -> None:
    status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    for r in status["requirements"]:
        if r["status"] == "PARTIALLY_MET":
            assert r.get("gap_id") and r.get("gap_description"), f"{r['id']} missing gap"


def test_must_arithmetic_3_7_1() -> None:
    status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    ma = status["must_arithmetic"]
    assert ma["total_must"] == 11
    assert ma["verified_met"] == 3
    assert ma["partially_met"] == 7
    assert ma["not_applicable_trigger_not_observed"] == 1
    assert set(ma["verified_met_ids"]) == {"TT-REQ-006", "TT-REQ-010", "TT-REQ-012"}
    assert set(ma["partially_met_ids"]) == {
        "TT-REQ-001",
        "TT-REQ-002",
        "TT-REQ-003",
        "TT-REQ-004",
        "TT-REQ-005",
        "TT-REQ-007",
        "TT-REQ-011",
    }
    assert ma["not_applicable_ids"] == ["TT-REQ-013"]
    tt013 = next(r for r in status["requirements"] if r["id"] == "TT-REQ-013")
    assert tt013["status"] == "NOT_APPLICABLE"
    assert tt013["conditional_trigger_observed"] is False


def test_s035_exact_key_and_sha() -> None:
    source_map = json.loads(SOURCE_MAP_JSON.read_text(encoding="utf-8"))
    s035 = next(s for s in source_map["sources"] if s["id"] == "S-035")
    assert s035["campaign_key"] == "S-035 / SANDRA-DIRECT-BODY-2026-08-04"
    assert s035["sha256"] == "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed"
    assert s035["standing"] == "DIRECT_SUPERVISOR_SOURCE_BODY"
    assert s035["staged_path"] == ".harness/context/sources/S-035__sandra-direct-email.md"


def test_validator_passes_clean() -> None:
    errors = validator.validate()
    assert errors == [], f"validator failed clean: {errors}"


def test_discriminating_mutation_quotation_fails() -> None:
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(baseline)
    mutated["requirements"][0]["canonical_quotation"] += "x"
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "mutated.json"
        tmp.write_text(json.dumps(mutated), encoding="utf-8")
        orig = validator.BASELINE_JSON
        validator.BASELINE_JSON = tmp
        try:
            errors = validator.validate()
            assert any("drift" in e.lower() or "quotation" in e.lower() for e in errors), errors
        finally:
            validator.BASELINE_JSON = orig


def test_discriminating_mutation_status_fails() -> None:
    status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(status)
    for r in mutated["requirements"]:
        if r["id"] == "TT-REQ-013":
            r["status"] = "VERIFIED_MET"
            r["conditional_trigger_observed"] = True
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "mutated_status.json"
        tmp.write_text(json.dumps(mutated), encoding="utf-8")
        orig = validator.STATUS_JSON
        validator.STATUS_JSON = tmp
        try:
            errors = validator.validate()
            assert len(errors) > 0, "mutation should fail validation"
            assert any("TT-REQ-013" in e or "3+7+1" in e or "4+7+0" in e for e in errors), errors
        finally:
            validator.STATUS_JSON = orig


def test_discriminating_mutation_source_fails() -> None:
    source_map = json.loads(SOURCE_MAP_JSON.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(source_map)
    mutated["sources"] = [s for s in mutated["sources"] if s["id"] != "S-035"]
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "mutated_source.json"
        tmp.write_text(json.dumps(mutated), encoding="utf-8")
        orig = validator.SOURCE_MAP_JSON
        validator.SOURCE_MAP_JSON = tmp
        try:
            errors = validator.validate()
            assert any("S-035" in e for e in errors), errors
        finally:
            validator.SOURCE_MAP_JSON = orig


def test_implementation_target_matches_base() -> None:
    status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    assert status["implementation_target"] == "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"


def test_external_decisions_present() -> None:
    status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    assert len(status["external_decisions"]) >= 5
    reqs_in_ed = {d["requirement"] for d in status["external_decisions"]}
    assert "TT-REQ-008" in reqs_in_ed or any(
        "TT-REQ-008" in str(d) for d in status["external_decisions"]
    )


def test_self_contained_payload_present() -> None:
    data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    assert isinstance(data.get("canonical_payload"), str)
    assert isinstance(data.get("whole_file_content"), str)
    import hashlib

    assert (
        hashlib.sha256(data["canonical_payload"].encode("utf-8")).hexdigest()
        == "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
    )
    assert (
        hashlib.sha256(data["whole_file_content"].encode("utf-8")).hexdigest()
        == "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2"
    )


def test_byte_drift_via_payload_mutation_fails() -> None:
    data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    # Flip one byte in the self-contained payload
    mutated["canonical_payload"] = mutated["canonical_payload"].replace(
        "TrafficTwin shall embody", "TrafficTwin shallXembody", 1
    )
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "mutated_payload.json"
        tmp.write_text(json.dumps(mutated), encoding="utf-8")
        orig = validator.BASELINE_JSON
        validator.BASELINE_JSON = tmp
        try:
            errors = validator.validate()
            assert any("payload hash mismatch" in e for e in errors), errors
        finally:
            validator.BASELINE_JSON = orig
