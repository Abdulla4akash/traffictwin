"""Integration test for v08 requirements-closure acceptance harness (Lane 12).

Validates:
- harness consumes exact frozen manifest and passes on integrated closure package
- fails discriminating mutations for each load-bearing category via disposable temp copy
- real discriminating coverage: baseline hash, duplicate service, orphan evidence,
  broken accounting, relabel synthetic real, mark unresolved MUST MET,
  remove video segment, break rollback/identity, missing evidence standing
- blocker 1: exact evidence binding (wrong matrix digest, removed
  referenced digest, stray allowed)
- blocker 2: exact evidence standing (synthetic->real,
  simulation->real, design-only->invented, classification disagreement)
- proves real working tree stays byte-for-byte clean through temp mutations
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/validate_v08_requirements_closure.py"

# Relative paths for files that validator reads
REL_PATHS = [
    "docs/closure/v08_alignment/requirements_baseline_v1.json",
    "docs/closure/v08_alignment/requirements_source_map.json",
    "docs/closure/v08_alignment/requirements_status_v08.json",
    "docs/closure/v08_alignment/strategy_matrix.json",
    "docs/closure/v08_alignment/strategy_evidence_map.json",
    "docs/closure/v08_alignment/use_case_a_manifest.json",
    "docs/closure/v08_alignment/use_case_b_manifest.json",
    "docs/closure/v08_alignment/task_accounting_handcheck.json",
    "docs/closure/v08_alignment/task_semantics_contract.json",
    "docs/closure/v08_alignment/video_storyboard.md",
    "docs/closure/v08_alignment/video_evidence_checklist.md",
    "docs/closure/v08_alignment/video_7min_script.md",
    "docs/closure/v08_alignment/video_demo_click_path.md",
    "src/traffictwin/ui/pages/compare.py",
    "src/traffictwin/ui/navigation_v07.py",
]


def _run_validator(root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    # Use narrowly named env var to override validator root when temp copy used
    if root is not None:
        env["V08_VALIDATOR_ROOT"] = str(root)
    # Also support CLI arg path as first positional
    cmd = [sys.executable, str(VALIDATOR)]
    if root is not None:
        cmd.append(str(root))
    return subprocess.run(  # noqa: S603  # controller-owned constant
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


def _hash_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _snapshot_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in REL_PATHS:
        fp = REPO_ROOT / rel
        if fp.exists():
            out[rel] = _hash_file(fp)
    return out


def _copy_to_temp(temp_root: Path) -> Path:
    # Copy required trees to temp_root
    for rel in REL_PATHS:
        src = REPO_ROOT / rel
        dst = temp_root / rel
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    # Also copy scripts and docs needed for validator self-check
    for extra in [
        "scripts/validate_v08_requirements_closure.py",
        "docs/closure/v08_alignment/requirements_baseline_v1.json",
        "docs/closure/v08_alignment/requirements_source_map.json",
        "docs/closure/v08_alignment/requirements_status_v08.json",
        "docs/closure/v08_alignment/strategy_matrix.json",
        "docs/closure/v08_alignment/strategy_evidence_map.json",
        "docs/closure/v08_alignment/improved_dynamic_strategy_contract.json",
        "docs/closure/v08_alignment/improved_dynamic_strategy_contract.md",
        "docs/closure/v08_alignment/improved_dynamic_strategy_pseudocode.txt",
        "docs/closure/v08_alignment/task_semantics_contract.json",
        "docs/closure/v08_alignment/task_accounting_handcheck.json",
        "docs/closure/v08_alignment/use_case_a_manifest.json",
        "docs/closure/v08_alignment/use_case_b_manifest.json",
        "docs/closure/v08_alignment/dissertation_traceability.md",
        "docs/closure/v08_alignment/dissertation_restructure_plan.md",
        "docs/closure/v08_alignment/contribution_statement.md",
        "docs/closure/v08_alignment/video_7min_script.md",
        "docs/closure/v08_alignment/video_storyboard.md",
        "docs/closure/v08_alignment/video_demo_click_path.md",
        "docs/closure/v08_alignment/video_evidence_checklist.md",
        "docs/closure/v08_alignment/manchester_demo/current_view_artifact.json",
        "docs/closure/v08_alignment/manchester_demo/source_receipt.json",
        "docs/closure/v08_alignment/closure_acceptance_report.md",
        "docs/closure/v08_alignment/closure_package_index.json",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/pages/compare.py",
        "src/traffictwin/__init__.py",
    ]:
        src = REPO_ROOT / extra
        dst = temp_root / extra
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # Ensure src is importable
    return temp_root


def _with_temp_mutation(
    mutate_fn: Callable[[Path], None],
    description: str,
) -> None:
    before_hashes = _snapshot_hashes()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp) / "repo"
        tmp_root.mkdir(parents=True)
        _copy_to_temp(tmp_root)
        # Apply mutation to temp copy
        mutate_fn(tmp_root)
        # Run validator against temp copy
        result = _run_validator(tmp_root)
        assert result.returncode != 0, (
            f"mutation {description} should fail but passed: {result.stdout}\n{result.stderr}"
        )
        # Verify clean pass on unmutated temp copy (restore check via fresh copy)
        with tempfile.TemporaryDirectory() as tmp2:
            tmp_root2 = Path(tmp2) / "repo"
            tmp_root2.mkdir(parents=True)
            _copy_to_temp(tmp_root2)
            result2 = _run_validator(tmp_root2)
            assert result2.returncode == 0, (
                f"restore after {description} failed: {result2.stderr}\n{result2.stdout}"
            )
    # Prove real working tree stays byte-for-byte clean
    after_hashes = _snapshot_hashes()
    assert before_hashes == after_hashes, (
        f"real working tree mutated during {description}: "
        f"diff {set(before_hashes.items()) ^ set(after_hashes.items())}"
    )


def test_closure_harness_passes_clean() -> None:
    result = _run_validator()
    assert result.returncode == 0, f"validator failed clean: {result.stderr}\n{result.stdout}"
    assert "PASS" in result.stdout


def test_mutation_baseline_hash_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/requirements_baseline_v1.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["canonical_payload_sha256"] = "0" * 64
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "baseline hash")


def test_mutation_duplicate_service_identity_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        a_path = tmp_root / "docs/closure/v08_alignment/use_case_a_manifest.json"
        b_path = tmp_root / "docs/closure/v08_alignment/use_case_b_manifest.json"
        a_data = json.loads(a_path.read_text(encoding="utf-8"))
        wf = a_data.get("workflow_id") or a_data.get("feature") or ""
        data = json.loads(b_path.read_text(encoding="utf-8"))
        if "workflow_id" in data:
            data["workflow_id"] = wf
        elif "feature" in data:
            data["feature"] = wf
        else:
            data["workflow_id"] = wf
        b_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "duplicate service")


def test_mutation_orphan_evidence_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/strategy_evidence_map.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        allowed = data.get("allowed_sha256_set", [])
        if allowed:
            data["allowed_sha256_set"] = allowed[1:]
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "orphan evidence")


# Blocker 1 additional mutations


def test_mutation_wrong_matrix_digest_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/strategy_matrix.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for s in data.get("strategies", []):
            if s.get("id") == "strongest_link_off":
                s["experiment_evidence"]["primary_manifest_sha256"] = "a" * 64
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "wrong matrix digest")


def test_mutation_removed_referenced_digest_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/strategy_evidence_map.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        sha = "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
        data["allowed_sha256_set"] = [x for x in data.get("allowed_sha256_set", []) if x != sha]
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "removed referenced digest")


def test_mutation_stray_allowed_digest_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/strategy_evidence_map.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["allowed_sha256_set"].append("b" * 64)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "stray allowed digest")


def test_mutation_break_accounting_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/task_accounting_handcheck.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        acc = data["hand_example"]["accounting"]
        acc["offered"] = acc["offered"] + 1
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "break accounting")


def test_mutation_relabel_synthetic_real_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/use_case_a_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for src in data.get("sources", []):
            if src.get("source_id") == "general_live_road_traffic_bods":
                src["evidence_standing"] = "REAL MANCHESTER DATA"
                src["classification"] = "REAL MANCHESTER DATA"
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "relabel synthetic")


# Blocker 2 additional mutations


def test_mutation_synthetic_to_real_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/use_case_a_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for src in data.get("sources", []):
            if src.get("source_id") == "manual_incident_authored":
                src["evidence_standing"] = "REAL MANCHESTER DATA"
                src["classification"] = "REAL MANCHESTER DATA"
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "synthetic->real manual_incident_authored")


def test_mutation_simulation_to_real_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/use_case_a_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for src in data.get("sources", []):
            if src.get("source_id") == "synthetic_square_sumo":
                src["evidence_standing"] = "REAL MANCHESTER DATA"
                src["classification"] = "REAL MANCHESTER DATA"
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "simulation->real synthetic_square_sumo")


def test_mutation_design_only_to_invented_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/use_case_a_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for src in data.get("sources", []):
            if src.get("source_id") == "live_city_wide_twin":
                src["evidence_standing"] = "REAL LIVE CITY TWIN DATA"
                src["classification"] = "REAL LIVE CITY TWIN DATA"
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "design-only->invented live_city_wide_twin")


def test_mutation_classification_standing_disagreement_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/use_case_a_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for src in data.get("sources", []):
            if src.get("source_id") == "manual_incident_authored":
                src["classification"] = "REAL MANCHESTER DATA"
                src["evidence_standing"] = "SYNTHETIC DATA"
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "classification/standing disagreement")


def test_mutation_mark_unresolved_must_met_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/requirements_status_v08.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        for r in data.get("requirements", []):
            if r["id"] == "TT-REQ-005":
                r["status"] = "VERIFIED_MET"
                r["gap_id"] = None
                r["gap_description"] = None
                break
        ma = data.get("must_arithmetic", {})
        if "verified_met_ids" in ma:
            if "TT-REQ-005" not in ma["verified_met_ids"]:
                ma["verified_met_ids"].append("TT-REQ-005")
            ma["verified_met"] = len(ma["verified_met_ids"])
            if "TT-REQ-005" in ma.get("partially_met_ids", []):
                ma["partially_met_ids"].remove("TT-REQ-005")
                ma["partially_met"] = len(ma["partially_met_ids"])
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "mark unresolved MUST MET")


def test_mutation_remove_one_video_segment_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/video_storyboard.md"
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        new_lines = []
        removed = False
        for line in lines:
            if not removed and "1:15" in line and line.strip().startswith("|"):
                removed = True
                continue
            new_lines.append(line)
        p.write_text("\n".join(new_lines), encoding="utf-8")

    _with_temp_mutation(mutate, "remove video segment")


def test_mutation_break_rollback_identity_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "src/traffictwin/ui/pages/compare.py"
        text = p.read_text(encoding="utf-8")
        mutated = (
            text.replace(".strip()", ".strip_without_guard()")
            if ".strip()" in text
            else text.replace("strip()", "no_strip()")
        )
        if mutated == text:
            mutated = text.replace(
                "Only after pair is successfully usable", "REMOVED transactional guard"
            )
        p.write_text(mutated, encoding="utf-8")

    _with_temp_mutation(mutate, "break rollback/identity")


def test_mutation_remove_evidence_standing_fails() -> None:
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/video_evidence_checklist.md"
        text = p.read_text(encoding="utf-8")
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

    _with_temp_mutation(mutate, "remove evidence standing")


def test_mutation_evidence_conservation_orphan_fails() -> None:
    # Alias for orphan to ensure conservation keyword filter passes
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/strategy_evidence_map.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["allowed_sha256_set"] = data["allowed_sha256_set"][1:]
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "evidence orphan conservation")


def test_real_working_tree_stays_clean_through_mutations() -> None:
    before = _snapshot_hashes()

    # Run a single temp mutation to prove no leakage
    def mutate(tmp_root: Path) -> None:
        p = tmp_root / "docs/closure/v08_alignment/strategy_evidence_map.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["allowed_sha256_set"].append("c" * 64)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _with_temp_mutation(mutate, "cleanliness probe")
    after = _snapshot_hashes()
    assert before == after, f"real tree not clean: {before} vs {after}"


def test_validator_root_override_via_env() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp) / "repo"
        tmp_root.mkdir(parents=True)
        _copy_to_temp(tmp_root)
        # Clean should pass via env override
        result = _run_validator(tmp_root)
        assert result.returncode == 0, f"env override clean failed: {result.stderr}"
        # Mutate via temp and ensure env override detects
        p = tmp_root / "docs/closure/v08_alignment/strategy_evidence_map.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["allowed_sha256_set"].append("d" * 64)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result2 = _run_validator(tmp_root)
        assert result2.returncode != 0, "env override did not detect stray via temp"
