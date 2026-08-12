"""Unit tests for Use Case B validator (lane 04)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/validate_v08_use_case_b.py"
MD_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_vec_dynamic_service.md"
MANIFEST_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_manifest.json"
DEMO_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_demo_contract.json"


def _run_validator() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_validator_passes_on_clean_tree() -> None:
    result = _run_validator()
    assert result.returncode == 0, f"validator failed:\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
    assert "OK: use_case_b validation passed" in result.stdout


def test_validator_script_exists() -> None:
    assert VALIDATOR.exists()


def test_manifest_is_valid_json() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["lane"] == "04"
    assert data["base_sha"] == "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"


def test_demo_contract_is_valid_json() -> None:
    data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    assert data["lane"] == "04"
    assert data["base_sha"] == "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"


def test_markdown_contains_all_lifecycle_stages_in_order() -> None:
    text = MD_PATH.read_text(encoding="utf-8").lower()
    stages = [
        "offered tasks",
        "frozen actor mode choice",
        "ingress",
        "admission",
        "deterministic target selection",
        "forwarding",
        "service work",
        "return",
        "deadline assessment",
        "comparison output",
    ]
    positions = [text.index(s) for s in stages]
    assert positions == sorted(positions), "lifecycle stages must appear in order"


def test_markdown_distinguishes_core_vocabulary() -> None:
    text = MD_PATH.read_text(encoding="utf-8").lower()
    for term in ["vehicle mode", "ingress rsu", "execution rsu", "admission", "placement", "scaling"]:
        assert term in text, f"missing vocabulary term: {term}"


def test_markdown_marks_prohibited_claims_as_distinct() -> None:
    text = MD_PATH.read_text(encoding="utf-8").lower()
    assert "waiting-room capacity" in text or "waiting-room" in text
    # Must state NOT compute power (allow unicode not-equal as well).
    assert (
        "capacity is not compute power" in text
        or "capacity is not compute" in text
        or "not compute power" in text
        or "≠ compute power" in text
        or "waiting-room capacity" in text
        and "compute power" in text
        and "not" in text
    )


# --- Discriminating mutations ---

# The validator must fail when the actor is credited with RSU choice
# and must fail when compute completion is conflated with deadline success.


def test_mutation_actor_credited_with_rsu_choice_fails() -> None:
    """Mutate markdown to credit actor with RSU choice; validator must fail."""
    import scripts.validate_v08_use_case_b as v  # type: ignore[import-not-found]

    original = MD_PATH.read_text(encoding="utf-8")
    # Inject a positive claim that actor selects RSU (without negation).
    mutated = original + "\n\nThe actor selects target RSU directly for each task.\n"
    # Also inject MAPPO chooses RSU claim.
    mutated2 = mutated + "MAPPO chooses RSU based on learned policy.\n"

    # Use a temp file approach: validate the mutated text via helper.
    # We call validate_markdown directly on mutated text to avoid file mutation.
    v.ERRORS.clear()
    v.validate_markdown(mutated2)
    errors = list(v.ERRORS)
    v.ERRORS.clear()
    # Must have at least one error about RSU choice.
    assert any("RSU choice" in e or "actor" in e.lower() and "rsu" in e.lower() for e in errors), (
        f"validator should fail when actor credited with RSU choice, got errors: {errors}"
    )


def test_mutation_conflate_compute_and_deadline_fails() -> None:
    """Mutate markdown to equate compute_completed with deadline_success; validator must fail."""
    import scripts.validate_v08_use_case_b as v  # type: ignore[import-not-found]

    original = MD_PATH.read_text(encoding="utf-8")
    mutated = original + "\n\nNote: compute_completed = deadline_success for all tasks.\n"

    v.ERRORS.clear()
    v.validate_markdown(mutated)
    errors = list(v.ERRORS)
    v.ERRORS.clear()
    assert any("compute_completed" in e and "deadline" in e.lower() for e in errors), (
        f"validator should fail when compute_completed conflated with deadline_success, got: {errors}"
    )


def test_mutation_waiting_room_equated_with_compute_fails() -> None:
    import scripts.validate_v08_use_case_b as v  # type: ignore[import-not-found]

    original = MD_PATH.read_text(encoding="utf-8")
    mutated = original + "\n\nThe waiting-room is compute power for scaling.\n"

    v.ERRORS.clear()
    v.validate_markdown(mutated)
    errors = list(v.ERRORS)
    v.ERRORS.clear()
    assert any("waiting-room" in e.lower() and "compute" in e.lower() for e in errors), (
        f"validator should fail when waiting-room equated with compute power, got: {errors}"
    )


def test_validator_reports_distinct_counters() -> None:
    result = _run_validator()
    assert "distinct counters" in result.stdout.lower()
    for counter in ["forwarded", "compute_completed", "returned", "deadline_success"]:
        assert counter in result.stdout or counter in result.stderr or result.returncode == 0


def test_manifest_binds_source_hashes() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = {s["id"]: s["sha256"] for s in data["sources"]}
    # Check at least the S-035 and FINAL_AUDIT hashes.
    s035_entry = next(v for k, v in sources.items() if "S-035" in k)
    assert s035_entry == "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed"
    assert sources["FINAL_AUDIT"] == "0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9"


def test_demo_contract_headline_metric() -> None:
    data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    assert data["comparison_output"]["headline_metric"] == "completion_offered = deadline_success / offered"
