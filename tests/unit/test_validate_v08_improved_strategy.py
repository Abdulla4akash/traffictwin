"""Unit tests for the V08 improved dynamic strategy contract (lane 06).

Validates the happy path and that all five required semantic mutants are
rejected by scripts/validate_v08_improved_strategy.py.
The mutation tests use temporary copies (no in-place corruption).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = REPO_ROOT / "docs/closure/v08_alignment/improved_dynamic_strategy_contract.json"
MD_PATH = REPO_ROOT / "docs/closure/v08_alignment/improved_dynamic_strategy_contract.md"
PSEUDO_PATH = REPO_ROOT / "docs/closure/v08_alignment/improved_dynamic_strategy_pseudocode.txt"
VALIDATOR = REPO_ROOT / "scripts/validate_v08_improved_strategy.py"

FINGERPRINT_KEYS = [
    "identity",
    "input_state",
    "order",
    "feasible_set",
    "load_and_service_work_quantity",
    "immediate_reservation_update",
    "deterministic_tie_break",
    "admission_interaction",
    "forwarding",
    "refusal_taxonomy",
    "actor_boundary",
]


def _run_validator(*extra_env: tuple[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - trusted sys.executable + fixed validator path
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_validator_against(tmp_root: Path) -> int:
    """Run validator logic inline against tmp files by monkey-patching paths.

    Easiest: copy tmp JSON/MD/pseudo over a temp repo slice and import validator
    as subprocess with PYTHONPATH override. Simpler: directly invoke validator
    after shadowing the three files via a temporary symlink tree.
    For now, run a single-file check helper that replicates validator checks
    on the tmp JSON/MD/pseudo paths.
    """
    # We'll implement a minimal inline validator that mirrors the real one
    # but on the supplied directory. To keep fidelity, call the real validator
    # via an isolated filesystem: create a temp repo layout shadowing the paths.
    import shutil

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Recreate the layout the validator expects relative to REPO_ROOT
        # Validator computes REPO_ROOT as parents[1] of scripts/validate_....py
        # So we construct td/scripts/validate... and td/docs/closure/...
        (td_path / "scripts").mkdir(parents=True)
        (td_path / "docs/closure/v08_alignment").mkdir(parents=True)
        shutil.copy2(VALIDATOR, td_path / "scripts/validate_v08_improved_strategy.py")
        for name in (
            "improved_dynamic_strategy_contract.json",
            "improved_dynamic_strategy_contract.md",
            "improved_dynamic_strategy_pseudocode.txt",
        ):
            src = tmp_root / name
            dst = td_path / "docs/closure/v08_alignment" / name
            shutil.copy2(src, dst)
        result = subprocess.run(  # noqa: S603 - trusted sys.executable + fixed validator path
            [sys.executable, str(td_path / "scripts/validate_v08_improved_strategy.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode


def _load_json(path: Path = JSON_PATH) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_validator_passes_on_committed_contract() -> None:
    result = _run_validator()
    assert result.returncode == 0, (
        f"validator failed:\nSTDOUT:{result.stdout}\nSTDERR:{result.stderr}"
    )
    assert "OK: fingerprint" in result.stdout


def test_fingerprint_determinism() -> None:
    data = _load_json()
    payload = {k: data[k] for k in FINGERPRINT_KEYS}
    h = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    assert data["fingerprint"] == h
    assert data["fingerprint_payload_keys"] == FINGERPRINT_KEYS
    # Markdown and pseudocode carry same hash
    assert h in MD_PATH.read_text(encoding="utf-8")
    assert h in PSEUDO_PATH.read_text(encoding="utf-8")


def test_contract_and_pseudocode_agree_on_core_claims() -> None:
    data = _load_json()
    pseudo = PSEUDO_PATH.read_text(encoding="utf-8")
    md = MD_PATH.read_text(encoding="utf-8")
    # Identity
    assert data["identity"]["is_deterministic"] is True
    assert data["identity"]["is_learned"] is False
    # Gate present
    gate = "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]"
    assert data["admission_interaction"]["deadline_gate"]["formula"] == gate
    assert gate in pseudo
    assert gate in md or "TASK_DEADLINE" in md
    # Actor boundary
    assert data["actor_boundary"]["actor"]["selects_execution_rsu"] is False
    assert "MAPPO" in md
    assert "MAPPO" in pseudo
    # Order
    assert "ascending task-substep" in data["order"]["candidate_order"].lower()
    assert "ascending task-substep" in md.lower()
    # Tie-break
    assert "lowest" in data["deterministic_tie_break"]["rule"].lower()


def test_s035_classification_correct() -> None:
    data = _load_json()
    s035 = data["sandra_direct_body_S035"]
    assert s035["sha256"] == "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed"
    assert s035["tt_req_008_effect"]["priority"] == "SHOULD unchanged"
    assert s035["tt_req_008_effect"]["frozen_baseline_unchanged"] is True


# ---------------------------------------------------------------------------
# Mutant helpers
# ---------------------------------------------------------------------------


def _mutant_setup() -> tuple[Path, dict[str, Any], str, str]:
    tmp = Path(tempfile.mkdtemp())
    data = _load_json()
    md = MD_PATH.read_text(encoding="utf-8")
    pseudo = PSEUDO_PATH.read_text(encoding="utf-8")
    return tmp, data, md, pseudo


def _write_mutant(tmp: Path, data: dict[str, Any], md: str, pseudo: str) -> None:
    (tmp / "improved_dynamic_strategy_contract.json").write_text(
        json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (tmp / "improved_dynamic_strategy_contract.md").write_text(md, encoding="utf-8")
    (tmp / "improved_dynamic_strategy_pseudocode.txt").write_text(pseudo, encoding="utf-8")


# ---------------------------------------------------------------------------
# Five required semantic mutants — each must be rejected
# ---------------------------------------------------------------------------


def test_mutant_common_target_is_rejected() -> None:
    """Mutant: select one argmin per substep and reuse for all candidates (inherited dla)."""
    tmp, data, md, pseudo = _mutant_setup()
    # Make order describe a common-target scheme and adjust pseudocode accordingly
    data["order"]["candidate_order"] = (
        "single argmin per task substep, common target for all vehicle slots"
    )
    # Remove per-task recompute language from pseudocode
    pseudo = pseudo.replace(
        "RECOMPUTE least-busy target for THIS candidate",
        "compute single least-busy target per substep",
    )
    pseudo = pseudo.replace("common-target mutant", "common-target ok")
    # Fix fingerprint to keep hash valid so failure is due to semantic check
    payload = {k: data[k] for k in FINGERPRINT_KEYS}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    # Update fingerprint in md/pseudo to new hash so fingerprint check passes
    new_h = data["fingerprint"]
    old_h = _load_json()["fingerprint"]
    md = md.replace(old_h, new_h)
    pseudo = pseudo.replace(old_h, new_h)
    _write_mutant(tmp, data, md, pseudo)
    rc = _run_validator_against(tmp)
    assert rc != 0, "common-target mutant should be rejected"


def test_mutant_no_reservation_is_rejected() -> None:
    """Mutant: omit immediate reservation update (batch or no update)."""
    tmp, data, md, pseudo = _mutant_setup()
    data["immediate_reservation_update"]["admitted_update"] = (
        "no immediate update; batch reservations at end of substep"
    )
    pseudo = pseudo.replace("no-reservation mutant", "no-reservation ok")
    # Also make immediate_reservation language not trigger validator failure via alternate phrasing?
    # Validator checks for 'add one load' — our mutant lacks it
    payload = {k: data[k] for k in FINGERPRINT_KEYS}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    new_h = data["fingerprint"]
    old_h = _load_json()["fingerprint"]
    md = md.replace(old_h, new_h)
    pseudo = pseudo.replace(old_h, new_h)
    _write_mutant(tmp, data, md, pseudo)
    rc = _run_validator_against(tmp)
    assert rc != 0, "no-reservation mutant should be rejected"


def test_mutant_actor_rsu_credit_is_rejected() -> None:
    """Mutant: credit MAPPO actor with RSU selection / learning placement."""
    tmp, data, md, pseudo = _mutant_setup()
    data["identity"]["selects_execution_rsu_by_actor"] = True
    data["identity"]["is_learned"] = True
    data["identity"]["is_deterministic"] = False
    data["actor_boundary"]["must_not_credit_actor_with_rsu_selection"] = False
    data["actor_boundary"]["placement_is_downstream_deterministic"] = False
    data["actor_boundary"]["actor"]["selects_execution_rsu"] = True
    payload = {k: data[k] for k in FINGERPRINT_KEYS}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    new_h = data["fingerprint"]
    old_h = _load_json()["fingerprint"]
    md = md.replace(old_h, new_h)
    pseudo = pseudo.replace(old_h, new_h)
    _write_mutant(tmp, data, md, pseudo)
    rc = _run_validator_against(tmp)
    assert rc != 0, "actor-RSU-credit mutant should be rejected"


def test_mutant_removed_gate_is_rejected() -> None:
    """Mutant: remove or bypass deadline gate."""
    tmp, data, md, pseudo = _mutant_setup()
    # Remove gate requirement
    data["admission_interaction"]["deadline_gate"]["must_not_be_removed"] = False
    data["admission_interaction"]["deadline_gate"]["formula"] = "always_admit()"
    # Remove gate from pseudocode
    gate = "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]"
    pseudo = pseudo.replace(gate, "always_admit()")
    pseudo = pseudo.replace("MANDATORY", "OPTIONAL")
    payload = {k: data[k] for k in FINGERPRINT_KEYS}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    new_h = data["fingerprint"]
    old_h = _load_json()["fingerprint"]
    md = md.replace(old_h, new_h)
    pseudo = pseudo.replace(old_h, new_h)
    _write_mutant(tmp, data, md, pseudo)
    rc = _run_validator_against(tmp)
    assert rc != 0, "removed-gate mutant should be rejected"


def test_mutant_nondeterministic_tie_is_rejected() -> None:
    """Mutant: random or unspecified tie-break among least-busy RSUs."""
    tmp, data, md, pseudo = _mutant_setup()
    data["deterministic_tie_break"]["rule"] = "random choice among tied least-busy RSUs"
    data["identity"]["is_deterministic"] = False
    pseudo = pseudo.replace("lowest RSU index on exact workload tie", "random among ties")
    pseudo = pseudo.replace("lowest RSU index on exact tie", "random among ties")
    pseudo = pseudo.replace("nondeterministic-tie mutant", "nondeterministic-tie ok")
    payload = {k: data[k] for k in FINGERPRINT_KEYS}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    new_h = data["fingerprint"]
    old_h = _load_json()["fingerprint"]
    md = md.replace(old_h, new_h)
    pseudo = pseudo.replace(old_h, new_h)
    _write_mutant(tmp, data, md, pseudo)
    rc = _run_validator_against(tmp)
    assert rc != 0, "nondeterministic-tie mutant should be rejected"


def test_restore_after_mutations_passes() -> None:
    """After all mutants, committed state must still pass."""
    result = _run_validator()
    assert result.returncode == 0
