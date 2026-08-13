"""Integration test for v08 requirements-closure acceptance harness (Lane 12).

Validates:
- harness consumes exact frozen manifest and passes on integrated closure package
- fails discriminating mutations for each load-bearing category
- real discriminating coverage: baseline hash, duplicate service, orphan evidence,
  broken accounting, relabel synthetic real, mark unresolved MUST MET,
  remove video segment, break rollback/identity, missing evidence standing
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/validate_v08_requirements_closure.py"
BASELINE_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_baseline_v1.json"
A_MANIFEST = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_manifest.json"
B_MANIFEST = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_manifest.json"
STATUS_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_status_v08.json"
HANDCHECK = REPO_ROOT / "docs/closure/v08_alignment/task_accounting_handcheck.json"
EVIDENCE_MAP = REPO_ROOT / "docs/closure/v08_alignment/strategy_evidence_map.json"
STORYBOARD = REPO_ROOT / "docs/closure/v08_alignment/video_storyboard.md"
CHECKLIST = REPO_ROOT / "docs/closure/v08_alignment/video_evidence_checklist.md"
COMPARE_PAGE = REPO_ROOT / "src/traffictwin/ui/pages/compare.py"


def _run_validator() -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # controller-owned constant
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_closure_harness_passes_clean() -> None:
    result = _run_validator()
    assert result.returncode == 0, f"validator failed clean: {result.stderr}\n{result.stdout}"
    assert "PASS" in result.stdout


def _with_mutation(path: Path, mutate_fn: Callable[[Path], None], check_prefix: str) -> None:
    original = path.read_bytes()
    try:
        mutate_fn(path)
        result = _run_validator()
        assert result.returncode != 0, (
            f"mutation {check_prefix} should fail but passed: {result.stdout}"
        )
    finally:
        path.write_bytes(original)
        # restore must pass
        result2 = _run_validator()
        assert result2.returncode == 0, f"restore after {check_prefix} failed: {result2.stderr}"


def test_mutation_baseline_hash_fails() -> None:
    def mutate(p: Path) -> None:
        data = json.loads(p.read_text(encoding="utf-8"))
        data["canonical_payload_sha256"] = "0" * 64
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_mutation(BASELINE_JSON, mutate, "baseline hash")


def test_mutation_duplicate_service_identity_fails() -> None:
    def mutate(p: Path) -> None:
        a_data = json.loads(A_MANIFEST.read_text(encoding="utf-8"))
        wf = a_data.get("workflow_id") or a_data.get("feature") or ""
        data = json.loads(p.read_text(encoding="utf-8"))
        # Duplicate identity from A
        if "workflow_id" in data:
            data["workflow_id"] = wf
        elif "feature" in data:
            data["feature"] = wf
        else:
            data["workflow_id"] = wf
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_mutation(B_MANIFEST, mutate, "duplicate service")


def test_mutation_orphan_evidence_fails() -> None:
    def mutate(p: Path) -> None:
        data = json.loads(p.read_text(encoding="utf-8"))
        # Remove a required SHA that must be present
        allowed = data.get("allowed_sha256_set", [])
        # Remove first SHA that is known must-present
        if allowed:
            data["allowed_sha256_set"] = allowed[1:]
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_mutation(EVIDENCE_MAP, mutate, "orphan evidence")


def test_mutation_break_accounting_fails() -> None:
    def mutate(p: Path) -> None:
        data = json.loads(p.read_text(encoding="utf-8"))
        acc = data["hand_example"]["accounting"]
        acc["offered"] = acc["offered"] + 1  # break conservation
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_mutation(HANDCHECK, mutate, "break accounting")


def test_mutation_relabel_synthetic_real_fails() -> None:
    def mutate(p: Path) -> None:
        data = json.loads(p.read_text(encoding="utf-8"))
        for src in data.get("sources", []):
            if src.get("source_id") == "general_live_road_traffic_bods":
                src["evidence_standing"] = "REAL MANCHESTER DATA"
                src["classification"] = "REAL MANCHESTER DATA"
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_mutation(A_MANIFEST, mutate, "relabel synthetic")


def test_mutation_mark_unresolved_must_met_fails() -> None:
    def mutate(p: Path) -> None:
        data = json.loads(p.read_text(encoding="utf-8"))
        for r in data.get("requirements", []):
            if r["id"] == "TT-REQ-005":
                r["status"] = "VERIFIED_MET"
                r["gap_id"] = None
                r["gap_description"] = None
                break
        # Also fix arithmetic to reflect illegal promotion — validator must still catch
        ma = data.get("must_arithmetic", {})
        if "verified_met_ids" in ma:
            if "TT-REQ-005" not in ma["verified_met_ids"]:
                ma["verified_met_ids"].append("TT-REQ-005")
            ma["verified_met"] = len(ma["verified_met_ids"])
            if "TT-REQ-005" in ma.get("partially_met_ids", []):
                ma["partially_met_ids"].remove("TT-REQ-005")
                ma["partially_met"] = len(ma["partially_met_ids"])
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_mutation(STATUS_JSON, mutate, "mark unresolved MUST MET")


def test_mutation_remove_one_video_segment_fails() -> None:
    def mutate(p: Path) -> None:
        text = p.read_text(encoding="utf-8")
        # Remove segment 3 row from table (contains 1:15)
        lines = text.splitlines()
        new_lines = []
        removed = False
        for line in lines:
            if not removed and "1:15" in line and line.strip().startswith("|"):
                # Skip this row (segment 3)
                removed = True
                continue
            new_lines.append(line)
        p.write_text("\n".join(new_lines), encoding="utf-8")

    _with_mutation(STORYBOARD, mutate, "remove video segment")


def test_mutation_break_rollback_identity_fails() -> None:
    def mutate(p: Path) -> None:
        text = p.read_text(encoding="utf-8")
        # Remove strip() guard
        mutated = (
            text.replace(".strip()", ".strip_without_guard()")
            if ".strip()" in text
            else text.replace("strip()", "no_strip()")
        )
        # Also if no strip at all, remove the transactional comment
        if mutated == text:
            mutated = text.replace(
                "Only after pair is successfully usable", "REMOVED transactional guard"
            )
        p.write_text(mutated, encoding="utf-8")

    _with_mutation(COMPARE_PAGE, mutate, "break rollback/identity")


def test_mutation_remove_evidence_standing_fails() -> None:
    def mutate(p: Path) -> None:
        text = p.read_text(encoding="utf-8")
        # Clear standing cell for SHOT-01 row (table column 5)
        lines = text.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith("| SHOT-01 "):
                cols = line.split("|")
                if len(cols) >= 6:
                    cols[5] = " "
                    line = "|".join(cols)
            new_lines.append(line)
        p.write_text("\n".join(new_lines), encoding="utf-8")

    _with_mutation(CHECKLIST, mutate, "remove evidence standing")
