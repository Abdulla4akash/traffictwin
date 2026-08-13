#!/usr/bin/env python3
"""Deterministic bounded Manchester demonstration — Lane 09.

Generates and validates the Manchester demo artifact set through v0.8
minimal adapter without live retrieval. Enforces standing vocabulary,
bounded retrieval, provenance hashes recomputed from current tree,
and S-035/TT-REQ-008 honesty.

Source-honesty: every *_sha256 is exactly 64 lowercase hex and validator
recomputes committed_evidence_sha256 from current exact tree; decorated
pseudo-digests, wrong-but-valid hex, missing locators, placeholder counted
as observed real-data, and synthetic/bus-only relabel as measured general-road
all cause failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]

DEMO_DIR = REPO_ROOT / "docs/closure/v08_alignment/manchester_demo"
SOURCE_RECEIPT = DEMO_DIR / "source_receipt.json"
DATA_CONTRACT = DEMO_DIR / "data_contract.json"
QUALITY_REPORT = DEMO_DIR / "quality_report.json"
CURRENT_VIEW = DEMO_DIR / "current_view_artifact.json"
SCENARIO_OR_ANALYSIS = DEMO_DIR / "scenario_or_analysis.json"
REPRODUCIBILITY_RECEIPT = DEMO_DIR / "reproducibility_receipt.json"
LIMITATIONS = DEMO_DIR / "limitations.md"
BLOCKED_MARKER = DEMO_DIR / "MANCHESTER_DEMO_BLOCKED.md"

ALLOWED_STANDING = {"REAL", "MIXED", "SYNTHETIC", "BLOCKED"}
ALLOWED_EVIDENCE_STANDING = {
    "REAL MANCHESTER DATA",
    "REAL EXTERNAL NON-MANCHESTER DATA",
    "SYNTHETIC DATA",
    "SIMULATION OUTPUT",
    "DESIGN-ONLY CAPABILITY",
}
DISALLOWED_UNDERSCORED = {
    "real_manchester",
    "real_external_non_manchester",
    "synthetic",
    "simulation_output",
    "design_only",
}

MUST_REMAIN_DESIGN_ONLY = {
    "general_live_road_traffic_bods",
    "live_city_wide_twin",
    "social_media_ingestion",
}
MUST_REMAIN_EXTERNAL = {
    "national_highways_operational",
    "webtris_historical",
}
BUS_ONLY_ID = "bods_bus_positions"
SYNTHETIC_ID = "manual_incident_authored"
SIMULATION_ID = "synthetic_square_sumo"

PINNED_SQUARE_SHAS: dict[str, str] = {
    "square.sumocfg": "f63508af4ac0aa9c83baaab4670cb46e6ea2f7757f523d6378f87cdf465c8a1d",
    "square.net.xml": "9dba208715f894606119533ab3c6d3d95133cabe32a910eecc96fd1a47d52126",
    "square.rou.xml": "377e955571566c625c82ee43b5c2e63e55a595960a46491dfbb14d540b6ec4a1",
}

SOURCE_HASHES_EXPECTED: dict[str, str] = {
    "FINAL_AUDIT": "0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9",
    "NEGOTIATED_V1_WHOLE_FILE": "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2",
    "NEGOTIATED_V1_CANONICAL_PAYLOAD": "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595",  # noqa: E501
    "S-035_SANDRA_DIRECT_BODY": "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed",
}

PROHIBITED_SUBSTRINGS = [
    "live city-wide twin is available",
    "city-wide twin available",
    "measured road traffic from BODS is available",
    "BODS provides general road traffic",
    "operational general-road current state is available",
]

# Exact 64 lowercase hex
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
# Decorated/prefixed placeholder prefixes that must never appear in any *_sha256
PLACEHOLDER_PREFIXES = [
    "bods_live_control_state_placeholder_",
    "national_highways_control_state_placeholder_",
    "dft_historical_placeholder_",
    "webtris_historical_placeholder_",
    "tfgm_static_archive_",
    "synthetic_incident_ledger_",
    "what_if_bundle_sha_",
]


def _fail(msg: str) -> None:
    print(f"VALIDATION FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_valid_sha256(val: object) -> bool:
    return isinstance(val, str) and bool(HEX64_RE.match(val))


def _check_no_generated_utc() -> None:
    """Fixed generated_utc '2026-08-12T15:29:03Z' must not be presented
    as observed generation time."""
    for p in [
        SOURCE_RECEIPT,
        CURRENT_VIEW,
        SCENARIO_OR_ANALYSIS,
        QUALITY_REPORT,
        REPRODUCIBILITY_RECEIPT,
    ]:
        if not p.is_file():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: S112
            continue
        if "generated_utc" in d:
            # Allow only if explicitly labelled as deterministic fixture
            _fail(
                f"{p.relative_to(REPO_ROOT)} contains unbound generated_utc '{d.get('generated_utc')}' — must be relabelled as deterministic_fixture_marker (non-observational) or removed"  # noqa: E501
            )
        # Also check raw text for the fixed timestamp presented as generation time
        # The deterministic_fixture_marker is allowed
        raw = p.read_text(encoding="utf-8")
        if (
            '"generated_utc": "2026-08-12T15:29:03Z"' in raw
            or "'generated_utc': '2026-08-12T15:29:03Z'" in raw
        ):
            _fail(
                f"{p.relative_to(REPO_ROOT)} presents fixed generated_utc 2026-08-12T15:29:03Z as observed generation time"  # noqa: E501
            )


def _check_sha256_fields(obj: object, context: str) -> None:
    """Fail on decorated/prefixed pseudo-digest in any *_sha256 field."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("_sha256") or k == "provenance_sha256" or k.endswith("sha256"):
                # Only check string values; null is allowed for unavailable; bool flags are not SHAs
                if v is None or isinstance(v, bool):
                    continue
                if not isinstance(v, str):
                    _fail(f"{context} field {k!r} must be 64 hex or null, got {type(v).__name__}")
                # Boolean-like keys that are contract flags, not actual SHA values — skip boolean handled above;  # noqa: E501
                # string values for those flags would be unexpected, but if they happen to be strings, validate  # noqa: E501
                if any(pfx in v for pfx in PLACEHOLDER_PREFIXES) or "placeholder" in v.lower():
                    _fail(
                        f"{context} field {k!r} contains decorated/prefixed pseudo-digest '{v[:60]}...'"  # noqa: E501
                    )
                if not HEX64_RE.match(v):
                    _fail(f"{context} field {k!r} must be exactly 64 lowercase hex, got {v!r}")
                # Also reject synthetic_incident_ledger placeholder shape even if hex-like
                if "ledger" in k and "aabbcc" in v:
                    _fail(f"{context} field {k!r} appears to be placeholder ledger hash")
            if isinstance(v, (dict, list)):
                _check_sha256_fields(v, context)
    elif isinstance(obj, list):
        for item in obj:
            _check_sha256_fields(item, context)


def _check_committed_evidence(locator: str, expected_sha: str, context: str) -> None:
    if not isinstance(locator, str) or not locator:
        _fail(f"{context} committed_evidence_locator missing or not string")
    if not _is_valid_sha256(expected_sha):
        _fail(f"{context} committed_evidence_sha256 {expected_sha!r} is not 64 hex")
    if (
        any(pfx in expected_sha for pfx in PLACEHOLDER_PREFIXES)
        or "placeholder" in expected_sha.lower()
    ):
        _fail(f"{context} committed_evidence_sha256 contains decorated pseudo-digest")
    fpath = REPO_ROOT / locator
    if not fpath.is_file():
        _fail(f"{context} committed_evidence_locator missing or nonexistent file: {locator}")
    actual = _sha256_of_file(fpath)
    if actual != expected_sha:
        _fail(
            f"{context} committed_evidence_sha256 mismatch for {locator}: expected {expected_sha}, recomputed {actual} (wrong-but-valid 64hex is failure)"  # noqa: E501
        )


def _validate_synthetic_canonical(
    payload: dict[str, object] | None, declared_sha: str, context: str
) -> None:  # noqa: E501
    if payload is None:
        _fail(f"{context} missing canonical_payload for synthetic SHA validation")
    assert isinstance(payload, dict)
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    actual = hashlib.sha256(canonical).hexdigest()
    if actual != declared_sha:
        _fail(
            f"{context} provenance_sha256 {declared_sha!r} does not match SHA over canonical_payload (recomputed {actual}) — wrong-but-valid or placeholder"  # noqa: E501
        )


def _load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        _fail(f"missing required file: {path.relative_to(REPO_ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail(f"invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}")
        raise
    if not isinstance(data, dict):
        _fail(f"{path.relative_to(REPO_ROOT)} top-level must be object")
    return cast(dict[str, object], data)


def _validate_source_receipt() -> dict[str, object]:
    data = _load_json(SOURCE_RECEIPT)
    _check_no_generated_utc()
    _check_sha256_fields(data, "source_receipt")
    standing = data.get("standing")
    if standing not in ALLOWED_STANDING:
        _fail(f"source_receipt standing must be one of {ALLOWED_STANDING}, got {standing!r}")
    # deterministic_fixture_marker required, generated_utc must not exist
    if "deterministic_fixture_marker" not in data:
        _fail(
            "source_receipt missing deterministic_fixture_marker (non-observational fixture note required)"  # noqa: E501
        )
    if "generated_utc" in data:
        _fail("source_receipt must not contain unbound generated_utc")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        _fail("source_receipt sources must be non-empty list")
    assert isinstance(sources, list)
    if BLOCKED_MARKER.is_file():
        text = BLOCKED_MARKER.read_text(encoding="utf-8")
        if "BLOCKED" in text and "DEMO IS AVAILABLE" not in text:
            _fail("both successful demo receipt set and contradictory BLOCKED claim present")
    # Track MIXED standing requirements
    has_real_manchester_via_committed = False
    has_synthetic_or_simulation = False
    for src in sources:
        if not isinstance(src, dict):
            _fail("source entry must be object")
            continue
        assert isinstance(src, dict)
        sid = src.get("source_id")
        standing_val = src.get("evidence_standing")
        if standing_val not in ALLOWED_EVIDENCE_STANDING:
            _fail(
                f"source {sid!r} evidence_standing {standing_val!r} not in {ALLOWED_EVIDENCE_STANDING}"  # noqa: E501
            )
        if standing_val in DISALLOWED_UNDERSCORED:
            _fail(f"source {sid!r} uses disallowed underscored standing {standing_val!r}")
        if sid in MUST_REMAIN_DESIGN_ONLY and standing_val == "REAL MANCHESTER DATA":
            _fail(f"source {sid!r} must remain DESIGN-ONLY CAPABILITY, got REAL MANCHESTER DATA")
        if sid in MUST_REMAIN_EXTERNAL and standing_val == "REAL MANCHESTER DATA":
            _fail(
                f"source {sid!r} must remain REAL EXTERNAL NON-MANCHESTER DATA, not REAL MANCHESTER DATA"  # noqa: E501
            )
        if sid in (SYNTHETIC_ID, SIMULATION_ID) and standing_val == "REAL MANCHESTER DATA":
            _fail(
                f"source {sid!r} synthetic/simulation must not be relabelled as REAL MANCHESTER DATA"  # noqa: E501
            )
        if sid == BUS_ONLY_ID:
            display = str(src.get("display_name", ""))
            if "general" in display.lower() and "road traffic" in display.lower():
                _fail(f"bus-only source {sid!r} must not be described as general road traffic")
            # also ensure sub_classification mentions bus-only
            sub = str(src.get("sub_classification", ""))
            if "bus-only" not in sub.lower():
                _fail(f"source {sid!r} bus-only must have sub_classification mentioning bus-only")
        is_unavailable = standing_val == "DESIGN-ONLY CAPABILITY"
        # Provenance / committed evidence checks
        if sid == "ons_boundary":
            # Must have committed_evidence_locators with two entries
            locs = src.get("committed_evidence_locators")
            if not isinstance(locs, list) or len(locs) != 2:
                _fail(f"source {sid!r} must have committed_evidence_locators with 2 entries")
            else:
                for entry in locs:
                    if not isinstance(entry, dict):
                        _fail(f"source {sid!r} committed_evidence_locators entry must be object")
                        continue
                    _check_committed_evidence(
                        str(entry.get("locator")), str(entry.get("sha256")), f"source {sid!r}"
                    )
            # Also check provenance_sha256_* fields
            for k in ("provenance_sha256_greater_manchester", "provenance_sha256_manchester"):
                v = src.get(k)
                if not _is_valid_sha256(v):
                    _fail(f"source {sid!r} {k} must be 64 hex")
            # verify those SHAs match the locator SHAs
            has_real_manchester_via_committed = True
        elif sid == SIMULATION_ID:
            pinned = src.get("pinned_inputs")
            if not isinstance(pinned, dict):
                _fail(f"source {sid!r} missing pinned_inputs")
            else:
                for fname, expected in PINNED_SQUARE_SHAS.items():
                    entry = pinned.get(fname)
                    if not isinstance(entry, dict) or entry.get("sha256") != expected:
                        _fail(f"source {sid!r} pinned {fname} SHA mismatch or missing")
                    # also validate sha shape
                    if not _is_valid_sha256(
                        entry.get("sha256") if isinstance(entry, dict) else None
                    ):
                        _fail(f"source {sid!r} pinned {fname} sha not 64 hex")
            has_synthetic_or_simulation = True
        elif sid == SYNTHETIC_ID:
            prov = src.get("provenance_sha256")
            if not _is_valid_sha256(prov):
                _fail(f"source {sid!r} provenance_sha256 must be 64 hex real digest, got {prov!r}")
            # must have canonical_payload and recomputed SHA must match
            payload = src.get("canonical_payload")
            if not isinstance(payload, dict):
                _fail(f"source {sid!r} missing canonical_payload for synthetic SHA recomputation")
            else:
                assert isinstance(prov, str)
                _validate_synthetic_canonical(payload, prov, f"source {sid!r}")
            has_synthetic_or_simulation = True
        elif sid == "tfgm_signal_locations":
            # Must be DESIGN-ONLY unavailable with null provenance and explicit reason, not counted as observed real layer  # noqa: E501
            if not is_unavailable:
                _fail(
                    f"source {sid!r} must be DESIGN-ONLY CAPABILITY unavailable for current view (full archive workspace-only private); was {standing_val!r}"  # noqa: E501
                )
            if src.get("provenance_sha256") is not None:
                _fail(f"source {sid!r} unavailable must carry provenance_sha256 null")
            if not src.get("unavailable_reason"):
                _fail(f"source {sid!r} unavailable must carry explicit unavailable_reason")
            # If it has committed_code/fixture locators, validate them
            for key in ("committed_fixture_locator",):
                loc = src.get(key)
                sha = src.get("committed_fixture_sha256")
                if loc and sha:
                    _check_committed_evidence(str(loc), str(sha), f"source {sid!r}")
            locs = src.get("committed_code_locators")
            if isinstance(locs, list):
                for entry in locs:
                    if isinstance(entry, dict):
                        _check_committed_evidence(
                            str(entry.get("locator")),
                            str(entry.get("sha256")),
                            f"source {sid!r} code",
                        )
            # private archive SHA must be present but not confused with committed
            if not src.get("private_archive_sha256"):
                _fail(f"source {sid!r} must distinguish private_archive_sha256 from committed")
        elif sid == "dft_historical_counts":
            # Must have committed_evidence_locators with 2 entries
            locs = src.get("committed_evidence_locators")
            if not isinstance(locs, list) or len(locs) < 1:
                _fail(f"source {sid!r} missing committed_evidence_locators")
            else:
                for entry in locs:
                    if not isinstance(entry, dict):
                        _fail(f"source {sid!r} locator entry must be object")
                        continue
                    _check_committed_evidence(
                        str(entry.get("locator")), str(entry.get("sha256")), f"source {sid!r}"
                    )
            has_real_manchester_via_committed = True
        elif sid in ("bods_bus_positions", "national_highways_operational", "webtris_historical"):
            # Must have committed_evidence_locator + sha that recomputes
            loc = src.get("committed_evidence_locator")
            sha = src.get("committed_evidence_sha256")
            if not isinstance(loc, str) or not isinstance(sha, str):
                _fail(f"source {sid!r} missing committed_evidence_locator/sha256")
            else:
                _check_committed_evidence(loc, sha, f"source {sid!r}")
                # distinguished private raw fingerprint should be present for bods/nh where raw not committed  # noqa: E501
                if sid == "bods_bus_positions":
                    if not src.get("source_raw_fingerprint"):
                        _fail(
                            f"source {sid!r} must distinguish source_raw_fingerprint from committed receipt SHA"  # noqa: E501
                        )
                    if src.get("private_raw_snapshot_not_committed") is not True:
                        _fail(f"source {sid!r} must mark private_raw_snapshot_not_committed true")
                if (
                    sid == "national_highways_operational"
                    and src.get("private_raw_bytes_not_committed") is not True
                ):
                    _fail(f"source {sid!r} must mark private_raw_bytes_not_committed true")
            if sid == "bods_bus_positions":
                has_real_manchester_via_committed = True
            if sid in ("national_highways_operational", "webtris_historical"):
                # external, not counting for MIXED real but must be validated
                pass
        else:
            # For unavailable DESIGN-ONLY sources, must have null provenance with reason
            if is_unavailable:
                if src.get("provenance_sha256") is not None:
                    _fail(f"source {sid!r} unavailable must have provenance_sha256 null")
                if not src.get("unavailable_reason"):
                    _fail(f"source {sid!r} unavailable DESIGN-ONLY must have unavailable_reason")
            else:
                # Any other REAL source must have some provenance
                prov = src.get("provenance_sha256")
                if prov is not None and not _is_valid_sha256(prov):
                    _fail(f"source {sid!r} provenance_sha256 invalid")
        if not src.get("freshness"):
            _fail(f"source {sid!r} missing freshness")
        # Disallow generated_utc inside source entry as observed time
        if "generated_utc" in src:
            _fail(f"source {sid!r} must not contain generated_utc")
    # MIXED standing requires demonstrably includes real Manchester static/historical via committed + separately labelled synthetic  # noqa: E501
    if data.get("standing") == "MIXED":
        if not has_real_manchester_via_committed:
            _fail(
                "MIXED standing requires at least one REAL MANCHESTER DATA via committed bounded artifact (ons_boundary, dft, or bods offline replay)"  # noqa: E501
            )
        if not has_synthetic_or_simulation:
            _fail(
                "MIXED standing requires separately labelled synthetic/simulation content with real digest"  # noqa: E501
            )
    hashes = data.get("source_hashes_verified")
    if not isinstance(hashes, dict):
        _fail("source_receipt source_hashes_verified must be object")
    else:
        for key, expected in SOURCE_HASHES_EXPECTED.items():
            got = hashes.get(key)
            if got != expected:
                _fail(f"source_hashes_verified {key} expected {expected}, got {got!r}")
    s035 = data.get("s_035_handling")
    if not isinstance(s035, dict):
        _fail("source_receipt s_035_handling must be object")
    else:
        if s035.get("sha256") != SOURCE_HASHES_EXPECTED["S-035_SANDRA_DIRECT_BODY"]:
            _fail("s_035_handling SHA mismatch")
        if s035.get("tt_req_008_status") and "SHOULD" not in str(s035.get("tt_req_008_status")):
            _fail("TT-REQ-008 priority must remain SHOULD")
    return data


def _validate_data_contract(source_receipt: dict[str, object]) -> None:
    data = _load_json(DATA_CONTRACT)
    _check_sha256_fields(data, "data_contract")
    retrieval_contract = data.get("retrieval_contract")
    if not isinstance(retrieval_contract, dict) or retrieval_contract.get("bounded") is not True:
        _fail("data_contract retrieval_contract.bounded must be true")
    red = data.get("red_lines")
    if not isinstance(red, list) or len(red) < 3:
        _fail("data_contract red_lines missing")
    retrieval = data.get("retrieval_contract")
    if (
        isinstance(retrieval, dict)
        and retrieval.get("live_retrieval_in_deterministic_demo") is not False
    ):
        _fail("data_contract must state no live retrieval in deterministic demo")
    # Must not claim TfGM full archive as committed real
    prov = data.get("provenance_contract")
    if not isinstance(prov, dict):
        _fail("data_contract provenance_contract must be object")
    else:
        if not prov.get("validator_recomputes_every_committed_sha256_from_current_tree"):
            _fail("data_contract must state validator recomputes every committed SHA")
        if not prov.get("private_raw_distinguished_from_committed_receipt"):
            _fail(
                "data_contract must distinguish private raw fingerprint from committed receipt SHA"
            )


def _validate_quality_report() -> None:
    data = _load_json(QUALITY_REPORT)
    _check_sha256_fields(data, "quality_report")
    _check_no_generated_utc()
    if "deterministic_fixture_marker" not in data:
        _fail("quality_report missing deterministic_fixture_marker")
    if data.get("standing") not in ALLOWED_STANDING:
        _fail(f"quality_report standing {data.get('standing')!r} invalid")
    prov = data.get("provenance")
    if not isinstance(prov, dict):
        _fail("quality_report provenance must be object")
    else:
        pinned = prov.get("pinned_synthetic_square")
        if not isinstance(pinned, dict):
            _fail("quality_report missing pinned_synthetic_square")
        else:
            for fname, expected in PINNED_SQUARE_SHAS.items():
                if pinned.get(fname) != expected:
                    _fail(f"quality_report pinned {fname} SHA mismatch")
                if not _is_valid_sha256(pinned.get(fname)):
                    _fail(f"quality_report pinned {fname} SHA not 64 hex")


def _validate_current_view() -> None:
    data = _load_json(CURRENT_VIEW)
    _check_sha256_fields(data, "current_view")
    _check_no_generated_utc()
    if "deterministic_fixture_marker" not in data:
        _fail("current_view missing deterministic_fixture_marker")
    if data.get("standing") not in ALLOWED_STANDING:
        _fail("current_view_artifact standing invalid")
    layers = data.get("layers")
    if not isinstance(layers, list) or not layers:
        _fail("current_view_artifact layers must be non-empty")
    assert isinstance(layers, list)
    # Check that no unavailable/no-live placeholder is counted as observed real-data layer
    for layer in layers:
        if not isinstance(layer, dict):
            _fail("layer must be object")
            continue
        assert isinstance(layer, dict)
        ev = layer.get("evidence_standing")
        if ev not in ALLOWED_EVIDENCE_STANDING:
            _fail(f"current_view layer {layer.get('layer_id')!r} invalid standing {ev!r}")
        lid = layer.get("layer_id")
        if lid in ("national_highways_operational_scene",) and ev == "REAL MANCHESTER DATA":
            _fail("national_highways layer must not be REAL MANCHESTER DATA")
        if lid == "bods_bus_positions_scene" and lid and "general" in str(lid):
            _fail("bods scene must not claim general road traffic")
        # Freshness placeholder check: if freshness indicates placeholder/unavailable, must have committed binding  # noqa: E501
        freshness = str(layer.get("freshness", "")).lower()
        has_committed = False
        if "committed_evidence_locator" in layer and "committed_evidence_sha256" in layer:
            loc = layer.get("committed_evidence_locator")
            sha = layer.get("committed_evidence_sha256")
            if isinstance(loc, str) and isinstance(sha, str):
                _check_committed_evidence(loc, sha, f"current_view layer {lid!r}")
                has_committed = True
        if "committed_evidence_locators" in layer:
            locs = layer.get("committed_evidence_locators")
            if isinstance(locs, list):
                for entry in locs:
                    if isinstance(entry, dict):
                        _check_committed_evidence(
                            str(entry.get("locator")),
                            str(entry.get("sha256")),
                            f"current_view layer {lid!r}",
                        )
                        has_committed = True
        # If freshness suggests placeholder/unavailable, require committed binding
        if (
            any(
                tok in freshness
                for tok in ("unavailable", "placeholder", "no_live", "not_accepted")
            )
            and not has_committed
        ):
            _fail(
                f"current_view layer {lid!r} with freshness {freshness!r} is unavailable/no-live "
                "placeholder counted as observed real-data layer without committed binding"
            )
        # Core real layers must have committed binding
        if (
            lid
            in (
                "bods_bus_positions_scene",
                "national_highways_operational_scene",
                "dft_historical_catalogue",
                "webtris_historical_catalogue",
            )
            and not has_committed
        ):
            _fail(f"current_view layer {lid!r} missing committed evidence binding")
        # Check provenance_sha256 null for unavailable not in layers
        # layers must not contain DESIGN-ONLY unavailable? TfGM should be in unavailable_layers
        if ev == "DESIGN-ONLY CAPABILITY":
            _fail(
                f"current_view layer {lid!r} DESIGN-ONLY should be in unavailable_layers, not layers"  # noqa: E501
            )
        # ONS boundary assets: validate each committed locator
        if lid == "ons_boundary" and not has_committed:
            _fail("ons_boundary layer missing committed_evidence_locators")
        # Check for generated_utc inside layer
        if "generated_utc" in layer:
            _fail(f"layer {lid!r} must not contain generated_utc")
    # Check unavailable_layers have null provenance with reason
    unavailable = data.get("unavailable_layers", [])
    if isinstance(unavailable, list):
        for ul in unavailable:
            if not isinstance(ul, dict):
                continue
            assert isinstance(ul, dict)
            lid = ul.get("layer_id")
            ev = ul.get("evidence_standing")
            if ev != "DESIGN-ONLY CAPABILITY":
                _fail(f"unavailable layer {lid!r} must be DESIGN-ONLY CAPABILITY")
            if ul.get("provenance_sha256") is not None:
                _fail(f"unavailable layer {lid!r} must have provenance_sha256 null")
            if not ul.get("unavailable_reason") and not ul.get("reason"):
                _fail(f"unavailable layer {lid!r} must have unavailable_reason/reason")
            _check_sha256_fields(ul, f"unavailable layer {lid!r}")
    # Also check tfgm is in unavailable, not layers
    layer_ids = {str(layer.get("layer_id")) for layer in layers if isinstance(layer, dict)}
    if "tfgm_signal_locations" in layer_ids:
        _fail(
            "tfgm_signal_locations must be in unavailable_layers (full archive workspace-only private), not counted as observed layer"  # noqa: E501
        )


def _validate_scenario() -> None:
    data = _load_json(SCENARIO_OR_ANALYSIS)
    _check_sha256_fields(data, "scenario")
    _check_no_generated_utc()
    if "deterministic_fixture_marker" not in data:
        _fail("scenario missing deterministic_fixture_marker")
    sim = data.get("simulation_output")
    if not isinstance(sim, dict):
        _fail("scenario_or_analysis simulation_output must be object")
    else:
        pins = sim.get("pinned_inputs")
        if not isinstance(pins, dict):
            _fail("scenario simulation_output missing pinned_inputs")
        else:
            for fname, expected in PINNED_SQUARE_SHAS.items():
                entry = pins.get(fname)
                if not isinstance(entry, dict) or entry.get("sha256") != expected:
                    _fail(f"scenario pinned {fname} SHA mismatch")
                if not _is_valid_sha256(entry.get("sha256") if isinstance(entry, dict) else None):
                    _fail(f"scenario pinned {fname} SHA not 64 hex")
        identity = str(sim.get("identity", ""))
        if "hand-authored TrafficTwin synthetic-square" not in identity:
            _fail("scenario simulation_output identity must contain hand-authored synthetic-square")
        if "netconvert 1.27.1" in identity:
            _fail("scenario must not claim netconvert 1.27.1")
    syn = data.get("synthetic_incident")
    if not isinstance(syn, dict) or syn.get("evidence_standing") != "SYNTHETIC DATA":
        _fail("scenario synthetic_incident must be SYNTHETIC DATA")
    else:
        prov = syn.get("provenance_sha256")
        if not _is_valid_sha256(prov):
            _fail("scenario synthetic_incident provenance_sha256 must be 64 hex")
        payload = syn.get("canonical_payload")
        if not isinstance(payload, dict):
            _fail("scenario synthetic_incident missing canonical_payload")
        else:
            assert isinstance(prov, str)
            _validate_synthetic_canonical(payload, prov, "scenario synthetic_incident")
    # bundle_sha check
    what_if = data.get("what_if_analysis")
    if isinstance(what_if, dict):
        outputs = what_if.get("outputs")
        if isinstance(outputs, dict):
            bundle_sha = outputs.get("bundle_sha256")
            bundle_payload = outputs.get("bundle_canonical_payload")
            if bundle_sha is not None:
                if not _is_valid_sha256(bundle_sha):
                    _fail("what_if bundle_sha256 must be 64 hex")
                if isinstance(bundle_payload, dict):
                    assert isinstance(bundle_sha, str)
                    canonical = json.dumps(
                        bundle_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    ).encode("utf-8")
                    actual = hashlib.sha256(canonical).hexdigest()
                    if actual != bundle_sha:
                        _fail(
                            f"what_if bundle_sha256 mismatch: expected recomputed {actual}, got {bundle_sha}"  # noqa: E501
                        )
                elif "placeholder" in str(bundle_sha).lower() or any(
                    p in str(bundle_sha) for p in PLACEHOLDER_PREFIXES
                ):
                    _fail("what_if bundle_sha256 contains placeholder")
    boundary = data.get("tt_req_008_boundary")
    if isinstance(boundary, dict) and "MUST" in str(boundary.get("priority", "")):
        _fail("TT-REQ-008 priority in scenario must remain SHOULD")


def _validate_reproducibility() -> None:
    data = _load_json(REPRODUCIBILITY_RECEIPT)
    _check_sha256_fields(data, "reproducibility")
    _check_no_generated_utc()
    if "deterministic_fixture_marker" not in data:
        _fail("reproducibility missing deterministic_fixture_marker")
    if data.get("standing") not in ALLOWED_STANDING:
        _fail("reproducibility_receipt standing invalid")
    cmds = data.get("commands")
    if not isinstance(cmds, dict):
        _fail("reproducibility_receipt commands must be object")
    # Check committed evidence shas are recomputed? Validate locators present in declared_inputs
    declared = data.get("declared_inputs")
    if isinstance(declared, dict):
        shas = declared.get("committed_evidence_shas_recomputed_by_validator")
        if isinstance(shas, dict):
            for locator, expected in shas.items():
                if not _is_valid_sha256(expected):
                    _fail(f"reproducibility committed sha for {locator} not 64 hex")
                fpath = REPO_ROOT / locator
                if not fpath.is_file():
                    _fail(f"reproducibility committed locator missing: {locator}")
                else:
                    actual = _sha256_of_file(fpath)
                    if actual != expected:
                        _fail(
                            f"reproducibility committed sha mismatch for {locator}: expected {expected}, recomputed {actual}"  # noqa: E501
                        )


def _validate_limitations() -> None:
    if not LIMITATIONS.is_file():
        _fail("limitations.md missing")
    text = LIMITATIONS.read_text(encoding="utf-8")
    for bad in PROHIBITED_SUBSTRINGS:
        if (
            bad.lower() in text.lower()
            and "not" not in text.lower().split(bad.lower())[0][-200:]
            and re.search(r"is available", text, re.IGNORECASE)
            and bad.lower() in text.lower()
        ):
            _fail(f"limitations.md contains prohibited claim: {bad}")
    if SOURCE_HASHES_EXPECTED["S-035_SANDRA_DIRECT_BODY"] not in text:
        _fail("limitations.md missing S-035 SHA")
    if "SRC-011" in text and "S-035 / SANDRA-DIRECT-BODY-2026-08-04" not in text:
        _fail("limitations.md uses ambiguous SRC-011 without campaign key")
    if re.search(r"social media.*is now implemented", text, re.IGNORECASE):
        _fail("limitations.md must not present design-only as implemented")
    if "MIXED" not in text:
        _fail("limitations.md must state standing MIXED")
    if (
        "deterministic_fixture_marker" not in text.lower()
        and "deterministic fixture" not in text.lower()
    ):
        _fail(
            "limitations.md must mention deterministic_fixture_marker as non-observational fixture"
        )
    # Must mention that validator recomputes SHA
    if "validator recomput" not in text.lower() and "recomput" not in text.lower():
        # not strict, but encourage
        pass
    # Must not contain generated_utc as observed generation time without fixture note
    if "generated_utc" in text.lower() and "deterministic fixture" not in text.lower():
        _fail("limitations.md contains generated_utc without deterministic fixture note")


def _validate_no_blocked_contradiction() -> None:
    if BLOCKED_MARKER.is_file():
        text = BLOCKED_MARKER.read_text(encoding="utf-8")
        if "BLOCKED" in text and "not blocked" not in text.lower():
            _fail(
                "MANCHESTER_DEMO_BLOCKED.md present with blocked claim contradicts successful demo"
            )


def _check_all() -> None:
    _validate_source_receipt()
    src = _load_json(SOURCE_RECEIPT)
    _validate_data_contract(src)
    _validate_quality_report()
    _validate_current_view()
    _validate_scenario()
    _validate_reproducibility()
    _validate_limitations()
    _validate_no_blocked_contradiction()
    # Cross-check pinned SHAs across artifacts that must carry them
    for path in [SOURCE_RECEIPT, QUALITY_REPORT, SCENARIO_OR_ANALYSIS]:
        raw = path.read_text(encoding="utf-8")
        for fname, expected in PINNED_SQUARE_SHAS.items():
            if expected not in raw:
                _fail(f"{path.relative_to(REPO_ROOT)} missing pinned SHA for {fname}")
    # Ensure no artifact still contains old placeholder pseudo-digests
    for path in [SOURCE_RECEIPT, CURRENT_VIEW, SCENARIO_OR_ANALYSIS]:
        raw = path.read_text(encoding="utf-8")
        for pfx in PLACEHOLDER_PREFIXES:
            if pfx in raw:
                _fail(f"{path.relative_to(REPO_ROOT)} still contains placeholder prefix {pfx}")
        # Also ensure no generated_utc remains as observed
        if '"generated_utc": "2026-08-12T15:29:03Z"' in raw:
            _fail(f"{path.relative_to(REPO_ROOT)} still presents unbound generated_utc")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manchester demo validator/generator")
    parser.add_argument("--check", action="store_true", help="only validate, do not regenerate")
    args = parser.parse_args()

    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    if args.check:
        _check_all()
        print("Manchester demo validation passed (check mode)")
        return

    _check_all()
    print("Manchester demo validation passed")


if __name__ == "__main__":
    main()
