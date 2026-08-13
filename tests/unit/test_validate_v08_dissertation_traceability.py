"""Tests for v08 dissertation traceability validator (Lane 10).

Focused gate: validates the six allowed lane-10 files without launching SUMO/VEC/evaluators.
Self-contained: reads committed docs only; no .harness runtime dependency.
"""

from __future__ import annotations

import json
import pathlib
import re

import scripts.validate_v08_dissertation_traceability as validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TRACE = REPO_ROOT / "docs/closure/v08_alignment/dissertation_traceability.md"
RESTRUCTURE = REPO_ROOT / "docs/closure/v08_alignment/dissertation_restructure_plan.md"
CONTRIB = REPO_ROOT / "docs/closure/v08_alignment/contribution_statement.md"
LIMITS = REPO_ROOT / "docs/closure/v08_alignment/limitations_register.md"
STATUS = REPO_ROOT / "docs/closure/v08_alignment/requirements_status_v08.json"


def test_all_allowed_files_exist() -> None:
    for p in [TRACE, RESTRUCTURE, CONTRIB, LIMITS]:
        assert p.exists(), f"missing {p}"


def test_validator_passes() -> None:
    assert validator.validate() == [], f"errors: {validator.validate()}"


def test_trace_master_exactly_14_once() -> None:
    text = TRACE.read_text(encoding="utf-8")
    master_section = re.search(r"## 2\. Trace master.*?(?=## 3\.)", text, re.DOTALL)
    assert master_section, "missing trace master section"
    ids = re.findall(r"\|\s*(TT-REQ-\d{3})\s*\|", master_section.group(0))
    assert len(ids) == 14, f"expected 14, got {len(ids)}"
    assert set(ids) == {f"TT-REQ-{i:03d}" for i in range(1, 15)}
    assert len(ids) == len(set(ids)), "duplicate IDs in master"


def test_statuses_match_status_file() -> None:
    status_data = json.loads(STATUS.read_text(encoding="utf-8"))
    by_id = {r["id"]: r["status"] for r in status_data["requirements"]}
    text = TRACE.read_text(encoding="utf-8")
    master_section = re.search(r"## 2\. Trace master.*?(?=## 3\.)", text, re.DOTALL)
    assert master_section
    for line in master_section.group(0).splitlines():
        if line.strip().startswith("| TT-REQ-"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 7:
                rid = parts[1]
                trace_status = parts[6]
                assert trace_status == by_id[rid], (
                    f"{rid}: trace {trace_status} != status file {by_id[rid]}"
                )


def test_chapters_resolve() -> None:
    restructure = RESTRUCTURE.read_text(encoding="utf-8")
    chapters = set(re.findall(r"### Ch(\d)", restructure))
    assert chapters == {str(i) for i in range(1, 9)}


def test_downstream_refs_subset_of_master() -> None:
    text = TRACE.read_text(encoding="utf-8")
    downstream = re.search(r"## 3\. Downstream.*?(?=## 4\.)", text, re.DOTALL)
    assert downstream
    refs = set(re.findall(r"TT-REQ-\d{3}", downstream.group(0)))
    assert refs.issubset({f"TT-REQ-{i:03d}" for i in range(1, 15)})


def test_must_arithmetic_preserved() -> None:
    status_data = json.loads(STATUS.read_text(encoding="utf-8"))
    ma = status_data["must_arithmetic"]
    assert ma["total_must"] == 11
    assert ma["verified_met"] == 3
    assert ma["partially_met"] == 7
    assert ma["not_applicable_trigger_not_observed"] == 1


def test_p0_p1_visible_and_external_decisions() -> None:
    limits = LIMITS.read_text(encoding="utf-8")
    assert "P0" in limits
    assert "P1" in limits
    assert "EXTERNAL DECISION REQUIRED" in limits
    assert "EXTERNAL DECISION REQUIRED" in TRACE.read_text(encoding="utf-8")


def test_contribution_distinguishes_three_classes() -> None:
    contrib = CONTRIB.read_text(encoding="utf-8")
    assert "Software" in contrib
    assert "Scientific evidence" in contrib
    assert "Inference" in contrib


def test_mutation_remove_must_mapping_fails() -> None:
    """Remove one MUST row from trace master — validator must fail."""
    text = TRACE.read_text(encoding="utf-8")
    # Remove the TT-REQ-002 master row (one line starting with | TT-REQ-002 |)
    mutated = re.sub(r"\|\s*TT-REQ-002\s*\|.*\n", "", text, count=1)
    _m = re.search(r"## 2\. Trace master.*?(?=## 3\.)", mutated, re.DOTALL)
    assert _m is not None
    assert "TT-REQ-002" not in re.findall(
        r"\|\s*(TT-REQ-\d{3})\s*\|",
        _m.group(0),
    )
    # Temporarily monkey-patch read
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.TRACE:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected validation to fail after removing a MUST mapping"
        assert any("TT-REQ-002" in e or "IDs mismatch" in e or "14" in e for e in errs), (
            f"unexpected errors: {errs}"
        )
    finally:
        validator._read = orig_read


def test_mutation_promote_partial_to_met_fails() -> None:
    """Mark an unresolved PARTIALLY_MET (TT-REQ-004 P0) as MET — validator must fail."""
    text = TRACE.read_text(encoding="utf-8")

    # Change TT-REQ-004 status from PARTIALLY_MET to VERIFIED_MET in the trace master line
    def replacer(m: re.Match[str]) -> str:
        line = m.group(0)
        return line.replace("PARTIALLY_MET", "VERIFIED_MET", 1)

    # Only mutate the TT-REQ-004 row
    mutated = re.sub(r"\|\s*TT-REQ-004\s*\|[^\n]*PARTIALLY_MET[^\n]*\n", replacer, text, count=1)
    assert "TT-REQ-004" in mutated
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.TRACE:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when promoting PARTIALLY_MET to MET"
        assert any("TT-REQ-004" in e or "mismatch" in e.lower() for e in errs), (
            f"unexpected errors: {errs}"
        )
    finally:
        validator._read = orig_read


def test_forbidden_claims_absent() -> None:
    for p in [TRACE, RESTRUCTURE, CONTRIB, LIMITS]:
        text = p.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "FULLY ALIGNED" in line:
                assert re.search(r"\b(No|not|never|without)\b", line, re.IGNORECASE), (
                    f"raw FULLY ALIGNED claim in {p.name}:{line[:120]}"
                )


def test_mutation_priority_should_to_must_fails() -> None:
    """Mutating TT-REQ-008 priority SHOULD→MUST must fail (baseline priority guard)."""
    text = TRACE.read_text(encoding="utf-8")
    mutated = text.replace("| TT-REQ-008 | SHOULD |", "| TT-REQ-008 | MUST |", 1)
    assert "| TT-REQ-008 | MUST |" in mutated
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.TRACE:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when mutating SHOULD→MUST for TT-REQ-008"
        assert any("priority" in e.lower() and "TT-REQ-008" in e for e in errs), (
            f"unexpected errors: {errs}"
        )
    finally:
        validator._read = orig_read


def test_mutation_entry_point_nonexistent_fails() -> None:
    """Replacing a real entry-point path with a nonexistent path must fail."""
    text = TRACE.read_text(encoding="utf-8")
    # Use a trace entry-point that the validator checks: src/traffictwin/metrics/engine.py
    mutated = text.replace(
        "src/traffictwin/metrics/engine.py",
        "src/traffictwin/metrics/__nonexistent_missing__.py",
        1,
    )
    assert "__nonexistent_missing__" in mutated
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.TRACE:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when entry point is nonexistent"
        assert any("does not exist" in e for e in errs), f"unexpected errors: {errs}"
    finally:
        validator._read = orig_read


def test_mutation_entry_point_contribution_nonexistent_fails() -> None:
    """Replacing a contribution software entry point with a nonexistent path must fail."""
    text = CONTRIB.read_text(encoding="utf-8")
    mutated = text.replace(
        "src/traffictwin/ui/pages/manchester_evidence_hub.py",
        "src/traffictwin/ui/pages/__nonexistent_missing__.py",
        1,
    )
    assert "__nonexistent_missing__" in mutated
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.CONTRIB:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when contribution entry point is nonexistent"
        assert any("does not exist" in e for e in errs), f"unexpected errors: {errs}"
    finally:
        validator._read = orig_read


def test_mutation_unknown_downstream_id_in_restructure_fails() -> None:
    """Adding an unknown TT-REQ ID (TT-REQ-099) to restructure plan must fail."""
    text = RESTRUCTURE.read_text(encoding="utf-8")
    mutated = text + "\nTT-REQ-099\n"
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.RESTRUCTURE:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when unknown TT-REQ-099 added to restructure"
        assert any("TT-REQ-099" in e or "unknown" in e.lower() for e in errs), (
            f"unexpected errors: {errs}"
        )
    finally:
        validator._read = orig_read


def test_mutation_unknown_downstream_id_015_fails() -> None:
    """Adding TT-REQ-015 to restructure plan must also fail."""
    text = RESTRUCTURE.read_text(encoding="utf-8")
    mutated = text + "\nTT-REQ-015\n"
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.RESTRUCTURE:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure for TT-REQ-015"
        assert any("015" in e or "unknown" in e.lower() for e in errs), f"unexpected errors: {errs}"
    finally:
        validator._read = orig_read


def test_mutation_partial_gap_row_removed_fails() -> None:
    """Deleting a PARTIALLY_MET limitations row (TT-REQ-011) must fail."""
    text = LIMITS.read_text(encoding="utf-8")
    mutated = re.sub(r"\|\s*TT-REQ-011\s*\|.*\n", "", text, count=1)
    assert "TT-REQ-011" not in re.findall(r"\|\s*(TT-REQ-011)\s*\|", mutated)
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.LIMITS:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when TT-REQ-011 limitations row removed"
        assert any("TT-REQ-011" in e or "missing" in e.lower() for e in errs), (
            f"unexpected errors: {errs}"
        )
    finally:
        validator._read = orig_read


def test_mutation_scientific_evidence_hash_missing_fails() -> None:
    """Removing frozen hash from a scientific-evidence row must fail."""
    text = CONTRIB.read_text(encoding="utf-8")
    row_orig = (
        "| Filtration of five Project-237 core gaps and SHOULD/MAY standing (audit) "
        "| `FINAL_AUDIT` `0da517b7...`, Negotiated Version 1 payload `58d9b0e7...` "
        "| RESEARCH-EVIDENCE FACT via audit record |"
    )
    row_mut = (
        "| Filtration of five Project-237 core gaps and SHOULD/MAY standing (audit) "
        "| `FINAL_AUDIT` `XXXX`, Negotiated Version 1 payload `YYYY` "
        "| RESEARCH-EVIDENCE FACT via audit record |"
    )
    assert row_orig in text
    mutated = text.replace(row_orig, row_mut, 1)
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.CONTRIB:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when scientific evidence hash removed"
        assert any("frozen" in e.lower() or "hash" in e.lower() for e in errs), (
            f"unexpected errors: {errs}"
        )
    finally:
        validator._read = orig_read


def test_mutation_inference_masquerade_fails() -> None:
    """An inference row masquerading as RESEARCH-EVIDENCE FACT without INFERENCE must fail."""
    text = CONTRIB.read_text(encoding="utf-8")
    mutated = text.replace(
        "INFERENCE + EXTERNAL DECISION REQUIRED",
        "RESEARCH-EVIDENCE FACT",
        1,
    )
    assert "INFERENCE + EXTERNAL DECISION REQUIRED" not in mutated or mutated.count(
        "INFERENCE + EXTERNAL DECISION REQUIRED"
    ) < text.count("INFERENCE + EXTERNAL DECISION REQUIRED")
    orig_read = validator._read

    def fake_read(p: pathlib.Path) -> str:
        if p == validator.CONTRIB:
            return mutated
        return orig_read(p)

    validator._read = fake_read
    try:
        errs = validator.validate()
        assert len(errs) > 0, "expected failure when inference masquerades as RESEARCH-EVIDENCE"
        assert any("masquerades" in e.lower() for e in errs), f"unexpected errors: {errs}"
    finally:
        validator._read = orig_read
