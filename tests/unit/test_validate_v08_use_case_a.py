"""Unit tests for scripts/validate_v08_use_case_a.py — lane 03.

Discriminating mutations required by contract:

- Replacing an unavailable/DESIGN-ONLY CAPABILITY standing with REAL MANCHESTER DATA => FAIL.
- Breaking an entry-point locator (unreachable file or not allowlisted) => FAIL.
- Using an unsupported evidence standing (underscored or invented) => FAIL.
- Replacing a real service/entry point with a nonexistent path => FAIL (and restore => PASS).
- Replacing a real service with an unrelated existing path => FAIL.
- Introducing a nonexistent src/... reference in Markdown => FAIL.
- Fabricated route bindings must FAIL while derived real routes PASS.
- Reintroducing false netconvert 1.27.1 provenance for synthetic square must FAIL.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from scripts.validate_v08_use_case_a import (
    EXPECTED_ROUTE_FOR_LOCATOR,
    HAND_AUTHOR_SHORT,
    PINNED_SQUARE_SHAS,
    _derived_expected_routes,
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


def test_derived_routes_match_navigation_spec() -> None:
    """Derived routes must equal exact v0.8 registration; incorrect fabricated routes must fail."""

    derived = _derived_expected_routes()
    # Real routes derived from navigation_v07 spec objects must be the lower-kebab forms
    assert (
        derived["src/traffictwin/ui/pages/manchester_evidence_hub.py"] == "/manchester-evidence-hub"
    )
    assert derived["src/traffictwin/ui/pages/manchester_operations.py"] == "/manchester"
    assert derived["src/traffictwin/ui/pages/scenario_builder.py"] == "/scenario-builder"
    # Global map must be same object (imported) and contain those values
    assert derived == EXPECTED_ROUTE_FOR_LOCATOR


def test_mutation_incorrect_route_fails_while_real_passes() -> None:
    """An incorrect fabricated route must FAIL while the derived real route PASSES."""

    manifest = _load_manifest()
    # Baseline must pass with real routes
    validate_manifest(manifest)
    # Mutate S1 to fabricated old route /Manchester_Evidence_Hub -> must fail
    mutated = copy.deepcopy(manifest)
    mutated["steps"][0]["route"] = "/Manchester_Evidence_Hub"
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0
    # Restore derived real route must pass again
    mutated["steps"][0]["route"] = "/manchester-evidence-hub"
    validate_manifest(mutated)
    # Also test demo contract fabricated route fails
    contract = _load_contract()
    mutated_contract = copy.deepcopy(contract)
    mutated_contract["sequence_bindings"][0]["route"] = "/Manchester_Evidence_Hub"
    with pytest.raises(SystemExit) as exc2:
        validate_demo_contract(mutated_contract, manifest)
    assert exc2.value.code != 0
    # Doc fabricated route must also fail
    doc = _load_doc()
    mutated_doc = doc.replace("/manchester-evidence-hub", "/Manchester_Evidence_Hub", 1)
    with pytest.raises(SystemExit) as exc3:
        validate_doc(mutated_doc, manifest)
    assert exc3.value.code != 0
    # Restore clean must pass
    validate_doc(doc, manifest)


def test_mutation_demo_contract_fabricated_manchester_route_fails() -> None:
    """Fabricated /Manchester_Operations must fail vs real /manchester."""

    manifest = _load_manifest()
    contract = _load_contract()
    mutated = copy.deepcopy(contract)
    for b in mutated["sequence_bindings"]:
        if b["locator"] == "src/traffictwin/ui/pages/manchester_operations.py":
            b["route"] = "/Manchester_Operations"
            break
    with pytest.raises(SystemExit) as exc:
        validate_demo_contract(mutated, manifest)
    assert exc.value.code != 0


def test_mutation_demo_contract_fabricated_scenario_route_fails() -> None:
    """Fabricated /Scenario_Builder must fail vs real /scenario-builder."""

    manifest = _load_manifest()
    contract = _load_contract()
    mutated = copy.deepcopy(contract)
    for b in mutated["sequence_bindings"]:
        if b["locator"] == "src/traffictwin/ui/pages/scenario_builder.py":
            b["route"] = "/Scenario_Builder"
            break
    with pytest.raises(SystemExit) as exc:
        validate_demo_contract(mutated, manifest)
    assert exc.value.code != 0
    # Restore real route passes
    validate_demo_contract(contract, manifest)


def test_manchester_chain_stated_in_doc() -> None:
    """Manchester chain app_pages/manchester.py -> pages/manchester_operations must be stated."""

    manifest = _load_manifest()
    doc = _load_doc()
    assert "app_pages/manchester.py" in doc
    assert 'url_path="manchester"' in doc
    assert "run_manchester_page_script" in doc
    # Removing the chain must fail
    mutated = doc.replace("app_pages/manchester.py", "app_pages/ghost.py")
    with pytest.raises(SystemExit) as exc:
        validate_doc(mutated, manifest)
    assert exc.value.code != 0


def test_synthetic_provenance_is_hand_authored_with_pinned_shas() -> None:
    """Clean artifacts must contain hand-authored identity and all three SHA pins, and no fabricated netconvert."""  # noqa: E501

    manifest = _load_manifest()
    contract = _load_contract()
    doc = _load_doc()
    validate_manifest(manifest)
    validate_demo_contract(contract, manifest)
    validate_doc(doc, manifest)
    # Check SHAs are present and hand-authored phrase present
    for _fname, (sha, _sz) in PINNED_SQUARE_SHAS.items():
        assert sha in json.dumps(manifest)
        assert sha in json.dumps(contract)
        assert sha in doc
    assert HAND_AUTHOR_SHORT.lower() in json.dumps(manifest).lower()
    assert HAND_AUTHOR_SHORT.lower() in json.dumps(contract).lower()
    assert HAND_AUTHOR_SHORT.lower() in doc.lower()


def test_mutation_synthetic_netconvert_reintroduction_fails_manifest() -> None:
    """Reintroducing the false netconvert 1.27.1 provenance in manifest must FAIL."""

    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    for src in mutated["sources"]:
        if src["source_id"] == "synthetic_square_sumo":
            src["display_name"] = "Pinned synthetic SUMO square scenario (netconvert 1.27.1)"
            src["coverage_scope"] = "Synthetic fixture (netconvert 1.27.1)"
            break
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0
    # Restore must pass
    validate_manifest(manifest)


def test_mutation_synthetic_netconvert_reintroduction_fails_contract() -> None:
    """Reintroducing false netconvert in demo contract SIMULATION_OUTPUT must FAIL."""

    manifest = _load_manifest()
    contract = _load_contract()
    mutated = copy.deepcopy(contract)
    for key in list(mutated.get("inputs", {}).keys()):
        if "SIMULATION" in key:
            for idx, item in enumerate(mutated["inputs"][key]):
                if "synthetic_square_sumo" in str(item):
                    mutated["inputs"][key][idx] = (
                        "synthetic_square_sumo (SIMULATION OUTPUT — pinned synthetic square fixture "  # noqa: E501
                        "netconvert 1.27.1; not Manchester observation)"
                    )
    with pytest.raises(SystemExit) as exc:
        validate_demo_contract(mutated, manifest)
    assert exc.value.code != 0
    validate_demo_contract(contract, manifest)


def test_mutation_synthetic_netconvert_reintroduction_fails_doc() -> None:
    """Reintroducing false netconvert display_name in doc must FAIL."""

    manifest = _load_manifest()
    doc = _load_doc()
    mutated = doc.replace(
        HAND_AUTHOR_SHORT,
        "Pinned synthetic SUMO square scenario (netconvert 1.27.1)",
    )
    # Also ensure the exact fabricated table entry appears
    if "Pinned synthetic SUMO square scenario (netconvert 1.27.1)" not in mutated:
        mutated = mutated.replace(
            "Hand-authored TrafficTwin synthetic-square",
            "Pinned synthetic SUMO square scenario (netconvert 1.27.1)",
        )
    with pytest.raises(SystemExit) as exc:
        validate_doc(mutated, manifest)
    assert exc.value.code != 0
    validate_doc(doc, manifest)


def test_mutation_synthetic_missing_sha_fails() -> None:
    """Removing a pinned SHA from manifest or contract must FAIL."""

    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    for src in mutated["sources"]:
        if src["source_id"] == "synthetic_square_sumo":
            # Strip first SHA
            first_sha = next(iter(PINNED_SQUARE_SHAS.values()))[0]
            src["provenance"] = src["provenance"].replace(first_sha, "0" * 64)
            break
    with pytest.raises(SystemExit) as exc:
        validate_manifest(mutated)
    assert exc.value.code != 0
    # Contract missing SHA
    contract = _load_contract()
    mutated_c = copy.deepcopy(contract)
    for key in list(mutated_c.get("inputs", {}).keys()):
        if "SIMULATION" in key:
            mutated_c["inputs"][key][0] = mutated_c["inputs"][key][0].replace(first_sha, "0" * 64)
    with pytest.raises(SystemExit) as exc2:
        validate_demo_contract(mutated_c, manifest)
    assert exc2.value.code != 0
