"""Unit tests for scripts/validate_v08_use_case_a.py — lane 03.

Discriminating mutations required by contract:

- Replacing an unavailable/DESIGN-ONLY CAPABILITY standing with REAL MANCHESTER DATA => FAIL.
- Breaking an entry-point locator (unreachable file or not allowlisted) => FAIL.
- Using an unsupported evidence standing (underscored or invented) => FAIL.
- Replacing a real service/entry point with a nonexistent path => FAIL (and restore => PASS).
- Replacing a real service with an unrelated existing path => FAIL.
- Introducing a nonexistent src/... reference in Markdown => FAIL.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from scripts.validate_v08_use_case_a import (
    validate_demo_contract,
    validate_doc,
    validate_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_manifest.json"
DEMO_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_demo_contract.json"
DOC_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_manchester_current_twin.md"


def _load_manifest() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def _load_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(DEMO_PATH.read_text(encoding="utf-8")))


def _load_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_manifest_validates_clean() -> None:
    manifest = _load_manifest()
    validate_manifest(manifest)


def test_demo_contract_validates_clean() -> None:
    manifest = _load_manifest()
    contract = _load_contract()
    validate_demo_contract(contract, manifest)


def test_doc_validates_clean() -> None:
    manifest = _load_manifest()
    doc = _load_doc()
    validate_doc(doc, manifest)


def test_mutation_unavailable_to_real_fails() -> None:
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    for src in mutated["sources"]:
        if src["source_id"] == "general_live_road_traffic_bods":
            src["classification"] = "REAL MANCHESTER DATA"
            src["evidence_standing"] = "REAL MANCHESTER DATA"
            src["freshness"] = "live_vehicle"
            break
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_social_media_to_real_fails() -> None:
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    for src in mutated["sources"]:
        if src["source_id"] == "social_media_ingestion":
            src["classification"] = "REAL MANCHESTER DATA"
            src["evidence_standing"] = "REAL MANCHESTER DATA"
            break
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_external_to_manchester_fails() -> None:
    """National Highways/WebTRIS must not be relabelled as REAL MANCHESTER DATA."""
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    for src in mutated["sources"]:
        if src["source_id"] == "national_highways_operational":
            src["classification"] = "REAL MANCHESTER DATA"
            src["evidence_standing"] = "REAL MANCHESTER DATA"
            break
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_broken_entry_point_fails() -> None:
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    mutated["steps"][0]["locator"] = "src/traffictwin/ui/pages/does_not_exist_at_v08.py"
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_unallowlisted_entry_point_fails() -> None:
    """Locator not in allowlisted v0.8 entry points must fail even if file exists."""
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    # Use a real file but not in allowlist
    mutated["steps"][0]["locator"] = "src/traffictwin/ui/pages/home.py"
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_demo_contract_broken_locator_fails() -> None:
    manifest = _load_manifest()
    contract = _load_contract()
    mutated = copy.deepcopy(contract)
    mutated["sequence_bindings"][0]["locator"] = "src/traffictwin/ui/pages/ghost_page.py"
    with pytest.raises(SystemExit) as exc:
        validate_demo_contract(mutated, manifest)
    assert exc.value.code != 0


def test_mutation_unsupported_evidence_standing_fails() -> None:
    """Underscored or invented standing must fail."""
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    for src in mutated["sources"]:
        if src["source_id"] == "bods_bus_positions":
            src["evidence_standing"] = "real_manchester"
            src["classification"] = "real_manchester"
            break
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_invented_evidence_standing_fails() -> None:
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    mutated["sources"][0]["evidence_standing"] = "INVENTED STANDING"
    mutated["sources"][0]["classification"] = "INVENTED STANDING"
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_tt_req_008_priority_escalation_fails() -> None:
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    mutated["tt_req_008"] = {
        "priority": "MUST",
        "investigations": [{"id": "A", "mandatory_implementation": False}],
    }
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_tt_req_008_mandatory_flag_fails() -> None:
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    mutated["tt_req_008"] = {
        "priority": "SHOULD",
        "investigations": [{"id": "A", "mandatory_implementation": True}],
    }
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_manifest_service_to_nonexistent_fails_and_restore_passes() -> None:
    """Discriminating mutation: real service -> nonexistent path must FAIL, restore -> PASS."""
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    # S5 is Scenario Builder — replace its real service with nonexistent path
    for step in mutated["steps"]:
        if step["step_id"] == "S5_synthetic_what_if":
            step["service"] = "src/traffictwin/ui/services/nonexistent_service.py"
            break
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0
    # Restore must pass
    validate_manifest(manifest)


def test_mutation_manifest_service_to_unrelated_existing_fails() -> None:
    """Replacing service with an existing but unrelated page (home.py) must FAIL."""
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    mutated["steps"][4]["service"] = "src/traffictwin/ui/pages/home.py"
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0


def test_mutation_demo_contract_service_to_nonexistent_fails_and_restore_passes() -> None:
    """Demo contract service mutation to nonexistent path must FAIL, restore -> PASS."""
    manifest = _load_manifest()
    contract = _load_contract()
    mutated = copy.deepcopy(contract)
    # Mutate last binding (S5) service to nonexistent
    for binding in mutated["sequence_bindings"]:
        if binding["step_id"] == "S5_synthetic_what_if":
            binding["service"] = "src/traffictwin/platform/platform_composer.py"
            break
    with pytest.raises(SystemExit) as exc:
        validate_demo_contract(mutated, manifest)
    assert exc.value.code != 0
    # Restore must pass
    validate_demo_contract(contract, manifest)


def test_mutation_doc_nonexistent_src_fails_and_restore_passes() -> None:
    """Markdown src/... reference to nonexistent path must FAIL, restore -> PASS."""
    manifest = _load_manifest()
    doc = _load_doc()
    mutated = doc + "\nReference `src/traffictwin/platform/platform_composer.py` for test.\n"
    with pytest.raises(SystemExit) as exc:
        validate_doc(mutated, manifest)
    assert exc.value.code != 0
    # Restore must pass
    validate_doc(doc, manifest)


def test_mutation_doc_missing_scenario_service_binding_fails() -> None:
    """Doc missing the real Scenario Builder service identity must FAIL."""
    manifest = _load_manifest()
    doc = _load_doc()
    # Remove the real service reference and replace with unrelated existing path
    mutated = doc.replace(
        "src/traffictwin/ui/services/scenario.py",
        "src/traffictwin/ui/pages/home.py",
    )
    with pytest.raises(SystemExit) as exc:
        validate_doc(mutated, manifest)
    assert exc.value.code != 0
