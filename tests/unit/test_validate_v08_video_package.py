"""Tests for v08 video package validator (Lane 11).

Focused gate: validates the six allowed files without launching SUMO/VEC/evaluators.
Self-contained: checks timing, word budget, locators, checklist, forbidden claims, honesty.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

import scripts.validate_v08_video_package as validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "docs/closure/v08_alignment/video_7min_script.md"
STORYBOARD = REPO_ROOT / "docs/closure/v08_alignment/video_storyboard.md"
CLICK_PATH = REPO_ROOT / "docs/closure/v08_alignment/video_demo_click_path.md"
CHECKLIST = REPO_ROOT / "docs/closure/v08_alignment/video_evidence_checklist.md"


def test_all_files_exist() -> None:
    for p in [SCRIPT, STORYBOARD, CLICK_PATH, CHECKLIST]:
        assert p.exists(), f"missing {p.relative_to(REPO_ROOT)}"


def test_validator_passes() -> None:
    errs = validator.validate()
    assert errs == [], f"validator errors: {errs}"


def test_segments_cover_420s() -> None:
    errs = validator.validate()
    # Filter timing errors
    timing = [e for e in errs if "segment" in e.lower() or "420" in e or "gap/overlap" in e.lower()]
    assert timing == [], f"timing errors: {timing}"


def test_word_budget() -> None:
    txt = SCRIPT.read_text(encoding="utf-8")
    words: list[int] = []
    for line in txt.splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 9:
            continue
        try:
            words.append(int(parts[6]))
        except ValueError:
            continue
    assert len(words) == 8
    assert 750 <= sum(words) <= 1050
    for w in words:
        assert 40 <= w <= 180


def test_click_path_locators_resolve() -> None:
    txt = CLICK_PATH.read_text(encoding="utf-8")
    for pat in [
        "manchester_evidence_hub.py",
        "manchester_operations.py",
        "strategy_matrix.json",
        "improved_dynamic_strategy_contract.json",
    ]:
        assert pat in txt, f"locator {pat} missing in click path"
    errs = [e for e in validator.validate() if "locator" in e.lower()]
    assert errs == [], f"locator errors: {errs}"


def test_evidence_checklist_standing_and_limitation() -> None:
    txt = CHECKLIST.read_text(encoding="utf-8")
    rows = [line for line in txt.splitlines() if line.startswith("| SHOT-")]
    assert len(rows) >= 8
    for row in rows:
        parts = [p.strip() for p in row.split("|")]
        assert len(parts) >= 8, row
        assert parts[5] not in ("", "-"), f"missing standing {row}"
        assert parts[6] not in ("", "-"), f"missing limitation {row}"


def test_one_manchester_view_and_matrix_and_result_and_reproducibility() -> None:
    txt = CHECKLIST.read_text(encoding="utf-8")
    assert "current_view_artifact.json" in txt
    assert "strategy_matrix.json" in txt
    assert "improved_strategy_results.json" in txt or "improved result" in txt.lower()
    assert "reproducibility" in txt.lower()


def test_forbidden_claims_absent() -> None:
    combined = "".join(
        p.read_text(encoding="utf-8") for p in [SCRIPT, STORYBOARD, CLICK_PATH, CHECKLIST]
    )
    for pat in validator.FORBIDDEN:
        assert re.search(pat, combined, flags=re.IGNORECASE) is None, f"forbidden {pat} found"


def test_honesty_labels_present() -> None:
    combined = (
        SCRIPT.read_text(encoding="utf-8")
        + STORYBOARD.read_text(encoding="utf-8")
        + CHECKLIST.read_text(encoding="utf-8")
    )
    for label in validator.HONESTY_LABELS:
        assert label in combined, f"missing honesty label {label}"


def test_mutation_timing_overlap_detected() -> None:
    """Discriminating: overlap/gap must fail."""
    original = SCRIPT.read_text(encoding="utf-8")
    # Mutate heading timing to create overlap (validator parses heading dash timings)
    mutated = original.replace("0:30–1:15", "0:29–1:15", 1)
    if mutated == original:
        mutated = original.replace("0:30-1:15", "0:29-1:15", 1)
    # Also mutate table pipe timing as fallback
    if mutated == original:
        mutated = original.replace("0:30 | 1:15", "0:29 | 1:15", 1)
    SCRIPT.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        assert any("gap/overlap" in e.lower() or "timing" in e.lower() for e in errs), (
            f"expected timing failure, got {errs}"
        )
    finally:
        SCRIPT.write_text(original, encoding="utf-8")


def test_mutation_missing_standing_detected() -> None:
    """Discriminating: remove one evidence standing must fail."""
    original = CHECKLIST.read_text(encoding="utf-8")
    # Empty first shot standing
    mutated = original.replace(
        " | SOURCE-DERIVED FACT | PARTIALLY_ALIGNED",
        " |  | PARTIALLY_ALIGNED",
        1,
    )
    # Fallback: blank first standing cell of SHOT-01
    if mutated == original:
        # More generic: blank a standing cell
        mutated = original.replace(
            "SOURCE-DERIVED FACT | PARTIALLY_ALIGNED", " | PARTIALLY_ALIGNED", 1
        )
    CHECKLIST.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        assert any("standing" in e.lower() for e in errs), f"expected standing failure, got {errs}"
    finally:
        CHECKLIST.write_text(original, encoding="utf-8")


def test_e2d_wrong_figure_identity_must_fail() -> None:
    """Wrong E2d figure identity must fail."""
    original = CHECKLIST.read_text(encoding="utf-8")
    mutated = original.replace(
        "fig3_e2d_per_task_minus_ingress_seed2",
        "fig_e2d_per_task_minus_dla_seed2",
        1,
    )
    assert mutated != original, "mutation did not change checklist"
    CHECKLIST.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        assert any("figure" in e.lower() or "nonexistent" in e.lower() for e in errs), (
            f"expected figure identity failure, got {errs}"
        )
    finally:
        CHECKLIST.write_text(original, encoding="utf-8")


def test_e2d_wrong_value_must_fail() -> None:
    """Wrong E2d value (+0.02) must fail; correct value is ~0.00587."""
    original = SCRIPT.read_text(encoding="utf-8")
    # Reintroduce wrong +0.02 value in E2d segment
    mutated = original.replace("0.00587", "0.02", 1)
    if mutated == original:
        mutated = original.replace("plus zero point zero zero five", "plus zero point zero two", 1)
    # Ensure we actually mutated
    if mutated == original:
        mutated = original.replace(
            "fig3_e2d_per_task_minus_ingress_seed2",
            "fig_e2d_per_task_minus_dla_seed2",
            1,
        )
    SCRIPT.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        # Check for wrong value or figure error
        assert any(
            "wrong e2d" in e.lower() or "figure" in e.lower() or "0.02" in e for e in errs
        ), f"expected wrong E2d value/figure failure, got {errs}"
    finally:
        SCRIPT.write_text(original, encoding="utf-8")


def test_word_budget_altered_cell_must_fail() -> None:
    """Altered Words cell inconsistent with narration must fail."""
    original = SCRIPT.read_text(encoding="utf-8")
    mutated = original.replace(
        "| 1 | Requirements — Negotiated Version 1 baseline | 0:00 | 0:30 | 30 | 63 |",
        "| 1 | Requirements — Negotiated Version 1 baseline | 0:00 | 0:30 | 30 | 64 |",
        1,
    )
    assert mutated != original, "Words cell mutation did not apply"
    SCRIPT.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        assert any("words cell" in e.lower() or "table" in e.lower() for e in errs), (
            f"expected Words cell failure, got {errs}"
        )
    finally:
        SCRIPT.write_text(original, encoding="utf-8")


def test_word_budget_stated_total_must_fail() -> None:
    """Stated total inconsistent with derived sum must fail."""
    original = SCRIPT.read_text(encoding="utf-8")
    mutated = original.replace("Total words 826,", "Total words 880,", 1)
    if mutated == original:
        mutated = original.replace("826 words total", "880 words total", 1)
    assert mutated != original, "stated total mutation did not apply"
    SCRIPT.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        assert any("stated total" in e.lower() or "derived" in e.lower() for e in errs), (
            f"expected stated total failure, got {errs}"
        )
    finally:
        SCRIPT.write_text(original, encoding="utf-8")


def test_nonexistent_storyboard_locator_must_fail() -> None:
    """Nonexistent storyboard locator must fail (extend beyond click-path)."""
    original = STORYBOARD.read_text(encoding="utf-8")
    mutated = original.replace(
        "src/traffictwin/integration/tos/contract.py",
        "src/traffictwin/integration/tos/nonexistent_contract.py",
        1,
    )
    assert mutated != original
    STORYBOARD.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        assert any("locator" in e.lower() for e in errs), f"expected locator failure, got {errs}"
    finally:
        STORYBOARD.write_text(original, encoding="utf-8")


def test_nonexistent_checklist_locator_must_fail() -> None:
    """Nonexistent checklist locator must fail."""
    original = CHECKLIST.read_text(encoding="utf-8")
    mutated = original.replace(
        "docs/closure/v08_alignment/requirements_baseline_v1.json",
        "docs/closure/v08_alignment/nonexistent_baseline.json",
        1,
    )
    assert mutated != original
    CHECKLIST.write_text(mutated, encoding="utf-8")
    try:
        errs = validator.validate()
        assert any("locator" in e.lower() for e in errs), (
            f"expected checklist locator failure, got {errs}"
        )
    finally:
        CHECKLIST.write_text(original, encoding="utf-8")


def test_pristine_temporary_package_without_harness_must_pass(
    tmp_path: pathlib.Path,
) -> None:
    """Pristine committed-tree temporary copy without .harness must pass."""
    pristine = tmp_path / "pristine"
    pristine.mkdir()
    # Use git ls-files to get committed files
    result = subprocess.run(
        ["git", "ls-files", "-z"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    files = result.stdout.decode().split("\0")
    for f in files:
        if not f:
            continue
        if f.startswith(".harness/"):
            continue
        src = REPO_ROOT / f
        dst = pristine / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    # Patch validator to use pristine root
    orig_root = validator.REPO_ROOT
    orig_script = validator.SCRIPT
    orig_story = validator.STORYBOARD
    orig_click = validator.CLICK_PATH
    orig_check = validator.CHECKLIST
    orig_results = validator.RESULTS_JSON
    try:
        validator.REPO_ROOT = pristine
        validator.SCRIPT = pristine / "docs/closure/v08_alignment/video_7min_script.md"
        validator.STORYBOARD = pristine / "docs/closure/v08_alignment/video_storyboard.md"
        validator.CLICK_PATH = pristine / "docs/closure/v08_alignment/video_demo_click_path.md"
        validator.CHECKLIST = pristine / "docs/closure/v08_alignment/video_evidence_checklist.md"
        validator.RESULTS_JSON = (
            pristine / "docs/closure/v08_alignment/improved_strategy_results.json"
        )
        assert not (pristine / ".harness").exists(), ".harness should not exist in pristine copy"
        errs = validator.validate()
        assert errs == [], f"pristine validator should pass, got {errs}"
    finally:
        validator.REPO_ROOT = orig_root
        validator.SCRIPT = orig_script
        validator.STORYBOARD = orig_story
        validator.CLICK_PATH = orig_click
        validator.CHECKLIST = orig_check
        validator.RESULTS_JSON = orig_results
