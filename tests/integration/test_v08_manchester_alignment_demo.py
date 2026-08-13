"""Integration test for Lane 09 bounded Manchester demonstration.

Validates:
- standing is MIXED and supported by committed receipts (validator recomputes)
- bounded retrieval, no live retrieval in deterministic path
- provenance hashes are exactly 64 hex and recomputed from current tree
- decorated/prefixed pseudo-digests are rejected
- wrong-but-valid 64hex for committed locator fails
- missing/nonexistent locator fails
- unavailable/no-live placeholder counted as observed real-data fails
- no synthetic/bus-only relabelled as measured general-road Manchester
- no DESIGN-ONLY promoted to REAL
- S-035/TT-REQ-008 honesty (SHOULD remains SHOULD)
- deterministic_fixture_marker present, generated_utc unbound absent
- discriminating mutations must fail, restore must pass
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "docs/closure/v08_alignment/manchester_demo"
SOURCE_RECEIPT = DEMO_DIR / "source_receipt.json"
QUALITY_REPORT = DEMO_DIR / "quality_report.json"
CURRENT_VIEW = DEMO_DIR / "current_view_artifact.json"
SCENARIO = DEMO_DIR / "scenario_or_analysis.json"
DATA_CONTRACT = DEMO_DIR / "data_contract.json"
REPRODUCIBILITY = DEMO_DIR / "reproducibility_receipt.json"
LIMITATIONS = DEMO_DIR / "limitations.md"
SCRIPT = REPO_ROOT / "scripts/run_v08_manchester_alignment_demo.py"

PINNED_SHAS = {
    "square.sumocfg": "f63508af4ac0aa9c83baaab4670cb46e6ea2f7757f523d6378f87cdf465c8a1d",
    "square.net.xml": "9dba208715f894606119533ab3c6d3d95133cabe32a910eecc96fd1a47d52126",
    "square.rou.xml": "377e955571566c625c82ee43b5c2e63e55a595960a46491dfbb14d540b6ec4a1",
}
# Real committed SHAs
BODS_SHA = "e60ee7e2a0b1c201e99658d9f8cf8f3105b820b3d32ec6392d98901389508387"
DFT_GATE_B_SHA = "c0a59f4377499ee0226ce90dc5869544b2e701190d691c6a2366a5cb92869081"
DFT_OBS_SHA = "f33cfeab2c2d68c8cf789a20391699d5adff6a8d8fcd06ed773def358d3d6d29"
WEBTRIS_SHA = "229a840ab8d38d6f4b6b219edd338f26d6df9551ed4b7291fb62934782bad13a"
NH_SHA = "5329b1fb183c2616c289f7a36c66df77f01dfb8c881cf0c7fa1476851593bbbc"
GM_SHA = "1bf8a1293de43f1573ec87685e0772ec8b9bd4cb14ec0ae0b0c21cd80d9a313a"
MANC_SHA = "31b78ea21882ec80a82b0cc584a57e0b1d1a4f1c8269e1bfc54826fb9981a51c"
SYNTHETIC_SHA = "a0deb68b86f56f58b19f41367af3c33e42e38bed38da558810e087d36179b449"


def _run_validator() -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _run_validator_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_demo_validation_passes_clean() -> None:
    result = _run_validator()
    assert result.returncode == 0, f"validator failed: {result.stderr}\n{result.stdout}"
    result2 = _run_validator_check()
    assert result2.returncode == 0, f"check mode failed: {result2.stderr}"


def test_source_receipt_has_expected_standing_and_sources() -> None:
    data = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    assert data["standing"] == "MIXED"
    assert data["base_sha"] == "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"
    # deterministic fixture, not generated_utc
    assert "deterministic_fixture_marker" in data
    assert "generated_utc" not in data
    sources = {s["source_id"]: s for s in data["sources"]}
    assert "bods_bus_positions" in sources
    assert "ons_boundary" in sources
    assert "manual_incident_authored" in sources
    assert "synthetic_square_sumo" in sources
    assert "general_live_road_traffic_bods" in sources
    # Bus-only must be REAL MANCHESTER DATA but NOT general traffic, with committed receipt
    assert sources["bods_bus_positions"]["evidence_standing"] == "REAL MANCHESTER DATA"
    assert "bus-only" in sources["bods_bus_positions"]["sub_classification"]
    assert sources["bods_bus_positions"]["committed_evidence_sha256"] == BODS_SHA
    assert (
        sources["bods_bus_positions"]["committed_evidence_locator"]
        == "docs/integration/evidence/manchester_bods_bee_network_probe_20260723.json"
    )
    assert sources["bods_bus_positions"]["private_raw_snapshot_not_committed"] is True
    assert (
        sources["bods_bus_positions"]["source_raw_fingerprint"]
        == "33e07061a500f19c1be5d1cd24f9094b12f0734b6b8edf74f0650c5a2cfed4f7"
    )
    # Synthetic must be SYNTHETIC DATA with real SHA over canonical payload
    assert sources["manual_incident_authored"]["evidence_standing"] == "SYNTHETIC DATA"
    assert sources["manual_incident_authored"]["provenance_sha256"] == SYNTHETIC_SHA
    assert "canonical_payload" in sources["manual_incident_authored"]
    # Simulation must be SIMULATION OUTPUT
    assert sources["synthetic_square_sumo"]["evidence_standing"] == "SIMULATION OUTPUT"
    # Design-only must remain DESIGN-ONLY
    assert (
        sources["general_live_road_traffic_bods"]["evidence_standing"] == "DESIGN-ONLY CAPABILITY"
    )
    assert sources["general_live_road_traffic_bods"]["provenance_sha256"] is None
    assert "unavailable_reason" in sources["general_live_road_traffic_bods"]
    # External must not be REAL MANCHESTER DATA
    assert (
        sources["national_highways_operational"]["evidence_standing"]
        == "REAL EXTERNAL NON-MANCHESTER DATA"
    )
    assert sources["national_highways_operational"]["committed_evidence_sha256"] == NH_SHA
    assert sources["webtris_historical"]["evidence_standing"] == "REAL EXTERNAL NON-MANCHESTER DATA"
    assert sources["webtris_historical"]["committed_evidence_sha256"] == WEBTRIS_SHA
    # TfGM must be DESIGN-ONLY unavailable, not counted as observed
    assert sources["tfgm_signal_locations"]["evidence_standing"] == "DESIGN-ONLY CAPABILITY"
    assert sources["tfgm_signal_locations"]["provenance_sha256"] is None
    assert "unavailable_reason" in sources["tfgm_signal_locations"]
    # ONS boundary SHAs recomputed
    assert sources["ons_boundary"]["provenance_sha256_greater_manchester"] == GM_SHA
    assert sources["ons_boundary"]["provenance_sha256_manchester"] == MANC_SHA
    # Synthetic square pins
    pins = sources["synthetic_square_sumo"]["pinned_inputs"]
    for fname, expected in PINNED_SHAS.items():
        assert pins[fname]["sha256"] == expected
    # DfT must have two committed locators
    dft = sources["dft_historical_counts"]
    locs = {e["locator"]: e["sha256"] for e in dft["committed_evidence_locators"]}
    assert (
        locs["docs/integration/evidence/manchester_dft_gate_b_probe_20260725.json"]
        == DFT_GATE_B_SHA
    )
    assert (
        locs["docs/integration/evidence/manchester_dft_observation_acquisition_20260725.json"]
        == DFT_OBS_SHA
    )
    # No generated_utc anywhere
    assert "generated_utc" not in json.dumps(data)


def test_quality_report_matches_source_receipt() -> None:
    data = json.loads(QUALITY_REPORT.read_text(encoding="utf-8"))
    assert data["standing"] == "MIXED"
    assert "deterministic_fixture_marker" in data
    assert "generated_utc" not in data
    prov = data["provenance"]
    for fname, expected in PINNED_SHAS.items():
        assert prov["pinned_synthetic_square"][fname] == expected
    assert prov["ons_boundary_shas"]["greater_manchester_combined_authority.geojson"] == GM_SHA


def test_current_view_artifact_layers_honest() -> None:
    data = json.loads(CURRENT_VIEW.read_text(encoding="utf-8"))
    assert data["standing"] == "MIXED"
    assert "deterministic_fixture_marker" in data
    assert "generated_utc" not in data
    # fingerprint is 64 hex, not placeholder prefix
    assert len(data["fingerprint"]) == 64
    assert all(c in "0123456789abcdef" for c in data["fingerprint"])
    layers = {layer["layer_id"]: layer for layer in data["layers"]}
    assert layers["ons_boundary"]["evidence_standing"] == "REAL MANCHESTER DATA"
    assert layers["bods_bus_positions_scene"]["evidence_standing"] == "REAL MANCHESTER DATA"
    assert "bus-only" in layers["bods_bus_positions_scene"]["sub_classification"]
    assert layers["bods_bus_positions_scene"]["committed_evidence_sha256"] == BODS_SHA
    assert (
        layers["national_highways_operational_scene"]["evidence_standing"]
        == "REAL EXTERNAL NON-MANCHESTER DATA"
    )
    assert layers["national_highways_operational_scene"]["committed_evidence_sha256"] == NH_SHA
    # TfGM must be unavailable, not in layers
    assert "tfgm_signal_locations" not in layers
    unavailable = {layer["layer_id"]: layer for layer in data["unavailable_layers"]}
    assert unavailable["tfgm_signal_locations"]["evidence_standing"] == "DESIGN-ONLY CAPABILITY"
    assert unavailable["tfgm_signal_locations"]["provenance_sha256"] is None
    assert (
        unavailable["general_live_road_traffic_bods"]["evidence_standing"]
        == "DESIGN-ONLY CAPABILITY"
    )


def test_scenario_or_analysis_honest() -> None:
    data = json.loads(SCENARIO.read_text(encoding="utf-8"))
    assert "deterministic_fixture_marker" in data
    assert "generated_utc" not in data
    assert data["synthetic_incident"]["evidence_standing"] == "SYNTHETIC DATA"
    assert data["synthetic_incident"]["provenance_sha256"] == SYNTHETIC_SHA
    assert "canonical_payload" in data["synthetic_incident"]
    assert data["simulation_output"]["evidence_standing"] == "SIMULATION OUTPUT"
    assert "hand-authored TrafficTwin synthetic-square" in data["simulation_output"]["identity"]
    assert "netconvert 1.27.1" not in data["simulation_output"]["identity"]
    for fname, expected in PINNED_SHAS.items():
        assert data["simulation_output"]["pinned_inputs"][fname]["sha256"] == expected
    # bundle sha is real hex over canonical payload
    bundle_sha = data["what_if_analysis"]["outputs"]["bundle_sha256"]
    assert len(bundle_sha) == 64
    assert all(c in "0123456789abcdef" for c in bundle_sha)
    assert data["tt_req_008_boundary"]["priority"].startswith("SHOULD")
    assert "MUST" not in data["tt_req_008_boundary"]["priority"]


def test_limitations_contains_honesty_and_no_prohibited_claim() -> None:
    text = LIMITATIONS.read_text(encoding="utf-8")
    assert "MIXED" in text
    assert "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed" in text
    assert "S-035 / SANDRA-DIRECT-BODY-2026-08-04" in text
    assert "deterministic_fixture_marker" in text.lower() or "deterministic fixture" in text.lower()
    assert "generated_utc" not in text or "deterministic fixture" in text.lower()
    assert "live city-wide twin is available" not in text.lower()
    # Documenting placeholder example is allowed; validator checks SHA fields, not doc mention
    # Ensure no actual placeholder SHA assigned as provenance (checked in test_no_placeholder_pseudo_digest_anywhere)  # noqa: E501
    blocked = DEMO_DIR / "MANCHESTER_DEMO_BLOCKED.md"
    if blocked.is_file():
        assert (
            "BLOCKED" not in blocked.read_text(encoding="utf-8")
            or "not blocked" in blocked.read_text(encoding="utf-8").lower()
        )


def test_data_contract_bounded() -> None:
    data = json.loads(DATA_CONTRACT.read_text(encoding="utf-8"))
    assert data["retrieval_contract"]["bounded"] is True
    assert data["retrieval_contract"]["live_retrieval_in_deterministic_demo"] is False
    assert "Must not claim measured general road traffic from BODS" in str(data["red_lines"])
    # provenance contract must state recompute
    assert (
        data["provenance_contract"]["validator_recomputes_every_committed_sha256_from_current_tree"]
        is True
    )
    assert "private_raw_distinguished_from_committed_receipt" in str(data["provenance_contract"])


def test_reproducibility_receipt_commands() -> None:
    data = json.loads(REPRODUCIBILITY.read_text(encoding="utf-8"))
    assert data["standing"] == "MIXED"
    assert "deterministic_fixture_marker" in data
    assert "generated_utc" not in data
    assert "scripts/run_v08_manchester_alignment_demo.py" in data["commands"]["generate"]
    # committed SHAs must be present and 64 hex
    for _locator, sha in data["declared_inputs"][
        "committed_evidence_shas_recomputed_by_validator"
    ].items():
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)


def test_no_placeholder_pseudo_digest_anywhere() -> None:
    """Every *_sha256 must be exactly 64 lowercase hex; no decorated prefix allowed."""
    import re

    hex64 = re.compile(r"^[0-9a-f]{64}$")
    for path in [SOURCE_RECEIPT, CURRENT_VIEW, SCENARIO, QUALITY_REPORT, REPRODUCIBILITY]:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = json.dumps(data)

        def walk(obj: object, _path: Path = path) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.endswith("_sha256") or k.endswith("sha256"):
                        if v is None or isinstance(v, bool):
                            continue
                        assert isinstance(v, str), (
                            f"{_path.name} {k} not string, got {type(v).__name__}"
                        )
                        assert "placeholder" not in v.lower(), (
                            f"{_path.name} {k} contains placeholder prefix {v!r}"
                        )
                        assert hex64.match(v), f"{_path.name} {k} must be 64 hex, got {v!r}"
                        # no decorated prefix
                        assert not v.startswith("bods_live_control"), f"{_path.name} {k} decorated"
                        assert not v.startswith("national_highways_control"), (
                            f"{_path.name} {k} decorated"
                        )
                        assert not v.startswith("dft_historical"), f"{_path.name} {k} decorated"
                        assert not v.startswith("webtris_historical"), f"{_path.name} {k} decorated"
                    if isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        # also ensure no placeholder prefix substring in whole file
        assert "bods_live_control_state_placeholder" not in raw
        assert "national_highways_control_state_placeholder" not in raw
        assert "dft_historical_placeholder" not in raw
        assert "webtris_historical_placeholder" not in raw
        assert "tfgm_static_archive_" not in raw
        assert "synthetic_incident_ledger_" not in raw
        assert "what_if_bundle_sha_1234" not in raw


def _mutate_and_run(
    mutate_fn: Callable[[dict[str, object]], None],
) -> subprocess.CompletedProcess[str]:  # noqa: E501
    """Apply mutation to source_receipt, run validator, restore."""
    original = SOURCE_RECEIPT.read_text(encoding="utf-8")
    data = json.loads(original)
    mutated = copy.deepcopy(data)
    mutate_fn(mutated)
    SOURCE_RECEIPT.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
    try:
        result = _run_validator()
        return result
    finally:
        SOURCE_RECEIPT.write_text(original, encoding="utf-8")


def _mutate_current_and_run(
    mutate_fn: Callable[[dict[str, object]], None],
) -> subprocess.CompletedProcess[str]:  # noqa: E501
    original = CURRENT_VIEW.read_text(encoding="utf-8")
    data = json.loads(original)
    mutated = copy.deepcopy(data)
    mutate_fn(mutated)
    CURRENT_VIEW.write_text(json.dumps(mutated, indent=2), encoding="utf-8")
    try:
        result = _run_validator()
        return result
    finally:
        CURRENT_VIEW.write_text(original, encoding="utf-8")


def test_mutation_relabel_synthetic_as_measured_general_road_fails() -> None:
    """Relabel SYNTHETIC DATA as REAL MANCHESTER DATA -> must FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "manual_incident_authored":
                src["evidence_standing"] = "REAL MANCHESTER DATA"
                src["freshness"] = "live_vehicle"

    result = _mutate_and_run(mutate)
    assert result.returncode != 0, (
        "validator should fail when synthetic relabelled as REAL MANCHESTER DATA"
    )
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0


def test_mutation_relabel_bus_only_as_general_road_traffic_fails() -> None:
    """Relabel bus-only REAL MANCHESTER DATA as if it were general road traffic -> FAIL via DESIGN-ONLY promotion."""  # noqa: E501

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "general_live_road_traffic_bods":
                src["evidence_standing"] = "REAL MANCHESTER DATA"
                src["freshness"] = "live_vehicle"
                src["provenance_sha256"] = "a" * 64

    result = _mutate_and_run(mutate)
    assert result.returncode != 0, (
        "validator should fail when DESIGN-ONLY promoted to REAL MANCHESTER DATA"
    )
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0


def test_mutation_remove_provenance_hash_fails() -> None:
    """Remove provenance_sha256 from a REAL source -> must FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "bods_bus_positions":
                src.pop("committed_evidence_sha256", None)
                src.pop("committed_evidence_locator", None)

    result = _mutate_and_run(mutate)
    assert result.returncode != 0, "validator should fail when provenance hash removed"
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0


def test_mutation_remove_pinned_sha_fails() -> None:
    """Remove a pinned synthetic square SHA -> must FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "synthetic_square_sumo":
                src["pinned_inputs"].pop("square.sumocfg", None)

    result = _mutate_and_run(mutate)
    assert result.returncode != 0
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0


def test_mutation_external_to_manchester_fails() -> None:
    """Relabel REAL EXTERNAL NON-MANCHESTER DATA as REAL MANCHESTER DATA -> FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "national_highways_operational":
                src["evidence_standing"] = "REAL MANCHESTER DATA"

    result = _mutate_and_run(mutate)
    assert result.returncode != 0
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0


def test_mutation_decorated_pseudo_digest_fails() -> None:
    """A decorated/prefixed pseudo-digest in any *_sha256 field must FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "bods_bus_positions":
                src["committed_evidence_sha256"] = (
                    "bods_live_control_state_placeholder_8f3a9c1d2e4b5a6f7e8d9c0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3"
                )

    result = _mutate_and_run(mutate)
    assert result.returncode != 0, "validator should fail on decorated pseudo-digest"
    assert "VALIDATION FAILED" in result.stderr
    assert "placeholder" in result.stderr.lower() or "64" in result.stderr.lower()
    assert _run_validator().returncode == 0


def test_mutation_wrong_valid_64hex_for_committed_locator_fails() -> None:
    """Wrong but syntactically valid 64-hex digest for committed locator must FAIL via recomputed mismatch."""  # noqa: E501

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "bods_bus_positions":
                # valid hex but wrong value (all 'a's)
                src["committed_evidence_sha256"] = "a" * 64

    result = _mutate_and_run(mutate)
    assert result.returncode != 0, "validator should fail on wrong 64hex committed SHA"
    assert "VALIDATION FAILED" in result.stderr
    assert "mismatch" in result.stderr.lower() or "recomputed" in result.stderr.lower()
    assert _run_validator().returncode == 0


def test_mutation_missing_or_nonexistent_locator_fails() -> None:
    """Missing or nonexistent committed evidence locator must FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "bods_bus_positions":
                src["committed_evidence_locator"] = (
                    "docs/integration/evidence/nonexistent_probe_20260799.json"
                )
                src["committed_evidence_sha256"] = "b" * 64

    result = _mutate_and_run(mutate)
    assert result.returncode != 0, "validator should fail on missing locator"
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0


def test_mutation_placeholder_counted_as_observed_real_layer_fails() -> None:
    """Unavailable/no-live placeholder counted as observed real-data layer must FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        # Add a fake layer that looks like a real Manchester layer but with placeholder freshness and no committed binding  # noqa: E501
        d["layers"].append(
            {
                "layer_id": "general_live_road_traffic_bods",
                "evidence_standing": "REAL MANCHESTER DATA",
                "freshness": "no_live_placeholder",
                "provenance_sha256": None,
                "honesty_label": "FAKE",
            }
        )

    result = _mutate_current_and_run(mutate)
    assert result.returncode != 0, (
        "validator should fail when placeholder counted as observed real-data layer"
    )
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0


def test_mutation_synthetic_relabelled_as_general_road_fails() -> None:
    """Synthetic or bus-only input relabelled as measured general-road Manchester data must FAIL."""

    def mutate(d: dict[str, Any]) -> None:
        for src in d["sources"]:
            if src["source_id"] == "manual_incident_authored":
                src["evidence_standing"] = "REAL MANCHESTER DATA"
                src["sub_classification"] = "measured general road traffic"
            if src["source_id"] == "bods_bus_positions":
                # remove bus-only qualifier and claim general traffic
                src["sub_classification"] = "measured general road traffic"
                src["display_name"] = "Measured general road traffic from BODS"

    result = _mutate_and_run(mutate)
    assert result.returncode != 0, (
        "validator should fail when synthetic/bus-only relabelled as general-road"
    )
    assert "VALIDATION FAILED" in result.stderr
    assert _run_validator().returncode == 0
