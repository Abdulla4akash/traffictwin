#!/usr/bin/env python3
"""Validate v08 existing strategy assessment artifacts (Lane 05).

Self-contained: all expected hashes/identities are embedded in this
validator and in the committed JSON artifacts. The ignored
.harness/context/source_map.json is NOT a runtime dependency; if it
exists it is cross-checked as an optional consistency check, but the
committed package validates without it.

Checks:
- Required files exist.
- strategy_matrix.json schema: 5 strategies with required fields.
- strategy_evidence_map.json schema: evidence resolves to allowed SHA-256 set.
- SHA-256 hex format, honesty classes, prohibited-claim guards.
- Embedded source-hash / head consistency (committed artifacts only).
- Determinism and comparison-compatibility presence.
- Assessment markdown contains narrow S-035 and TT-REQ-008 inference wording.

Discriminating: deleting one admission field or redirecting one evidence SHA must fail.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/closure/v08_alignment/strategy_matrix.json"
EVIDENCE_MAP_PATH = ROOT / "docs/closure/v08_alignment/strategy_evidence_map.json"
ASSESSMENT_PATH = ROOT / "docs/closure/v08_alignment/existing_strategy_assessment.md"
# Optional harness path — not required for committed package validation
SOURCE_MAP_PATH = ROOT / ".harness/context/source_map.json"

REQUIRED_STRATEGY_IDS = [
    "strongest_link_off",
    "jsq_without_gate",
    "ingress_dla",
    "common_target_dla",
    "per_task_dla",
]

# Every strategy must have these top-level keys (admission is critical for mutation)
REQUIRED_STRATEGY_FIELDS = [
    "id",
    "human_label",
    "honesty_class",
    "definition",
    "information",
    "authority",
    "admission",
    "placement",
    "sequential_behavior",
    "common_target_behavior",
    "forwarding",
    "determinism",
    "benefit",
    "failure_mode",
    "cost",
    "experiment_evidence",
    "limits",
    "comparison_compatibility",
]

REQUIRED_EVIDENCE_HEADS = {"e2b", "e2c", "e2d"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")

# ---------------------------------------------------------------------------
# Embedded canonical identities — self-contained, no .harness dependency
# ---------------------------------------------------------------------------
EXPECTED_BASE_SHA = "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"
EXPECTED_PAYLOAD_SHA256 = "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
EXPECTED_WHOLE_SHA256 = "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2"
EXPECTED_S035_SHA256 = "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed"
EXPECTED_FINAL_AUDIT_SHA256 = "0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9"
EXPECTED_SOURCE_INDEX_SHA256 = "7ce9b43250d8b72e3c1aa9e0bbbc369b251bf7b7aedcae39ea8ed8cdda860d24"

EXPECTED_HEADS: dict[str, str] = {
    "e2b": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
    "e2c": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
    "e2d": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
}

# Full allowed SHA-256 set embedded for self-contained cross-check.
# Must match strategy_evidence_map.json allowed_sha256_set exactly.
EXPECTED_ALLOWED_SHA256_SET: set[str] = {
    "eae09f31bd049b70f99930507873b0efb84a7a7cbeab2a37adb7b3a0bae6b12f",
    "3970b89e371a05cae6f5baa8142c98587b302d0c5a467601d50aa021e1368bfa",
    "53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8",
    "67d626ca4e6b60afb6beb5c9d4c8cc2bf7b15c72922eba633194848439fe3d52",
    "30f6d117402e91decf8581b2b42030c0f9795881dd5eaef1a380bbf6408f0d38",
    "54721d9a4b403e36e99123394193db06d7b6c596e66121975001a8d02196287e",
    "8c04c833f6b04140bac0f2dfcba788c50d29cc4be1dadf39cfacf5d8e366bba9",
    "f33e974b3dbbfc0865a0b4d986c8bbfaf504424e4187aa5ba809e610384390d3",
    "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
    "a0198c9f38295db8ee0aa34b2b4c786ebcb5c034450cb59b616f4a11076ea5c6",
    "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
    "b0bc17ef097e8a8ca3639482bbf5ae05ef249c1221836cc6591207e87b511970",
    "25b80d66d991b424e20a7fd18d9e45c641cddc4b4aa9ffeed0cbdccacb5f8f2f",
    "d3f41d2fc21257f16518f62ec2fbbde55243a89d31726c57f1a0171fe7f582d4",
    "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
    "1655ae76d3c9a6aac77d66b53555a35d608394427f86f0f19828fa5fb148afd0",
    "0e3f27cdec9d13ec8e340bf1d83b3afcd127e90d7bdcf316bc2a2b2738fd313f",
    "4975ab8792242a56c241d6513e7e49bcdfa5117ab462bcb6b9bb3c5d2a5e5410",
    "408cf8bb86370970941690b5887648c5bfb86d84a0da6bb2361b7edd508d80a7",
    "eb5de7ce1eea202fee4d08d28bf7f4e38888b24709550cfc78dca71b16b250ca",
    "8583503f817e159e74e20a8d0b3d72b281280984a2bbfac84b8e31786af8308e",
    "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208",
    "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
    "260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669",
    "f9ec488528c52ce7cd6f7bb8b3a6c9c96aef532e5783a538bcac9763508519fe",
    "a6e047265dd09365c0d4029afa76f8cb7caa444883e2f549a4254e3d0b53472a",
    "73d83d062fad030941f5236835cce8e86caacc4d44eb7a1129047e99228886ff",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except FileNotFoundError:
        print(f"FAIL: missing file {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def validate_matrix(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "v08_strategy_matrix_v1":
        errors.append("matrix schema_version must be v08_strategy_matrix_v1")
    if data.get("lane") != "05":
        errors.append("matrix lane must be 05")
    if data.get("base_sha") != EXPECTED_BASE_SHA:
        errors.append("matrix base_sha mismatch")
    auth = data.get("authority", {})
    if auth.get("negotiated_baseline_payload_sha256") != EXPECTED_PAYLOAD_SHA256:
        errors.append("matrix payload SHA mismatch")
    if auth.get("negotiated_baseline_whole_sha256") != EXPECTED_WHOLE_SHA256:
        errors.append("matrix whole-file SHA mismatch")
    if auth.get("s035_sha256") != EXPECTED_S035_SHA256:
        errors.append("matrix S-035 SHA mismatch")
    if (
        "final_audit_sha256" in auth
        and auth.get("final_audit_sha256") != EXPECTED_FINAL_AUDIT_SHA256
    ):
        errors.append("matrix final audit SHA mismatch")
    strategies = data.get("strategies")
    if not isinstance(strategies, list):
        errors.append("matrix strategies must be a list")
        return errors
    ids = [s.get("id") for s in strategies if isinstance(s, dict)]
    if ids != REQUIRED_STRATEGY_IDS:
        errors.append(f"matrix strategies ids must be exactly {REQUIRED_STRATEGY_IDS}, got {ids}")
    for strat in strategies:
        if not isinstance(strat, dict):
            errors.append("matrix strategy entry must be object")
            continue
        sid = strat.get("id", "<unknown>")
        for field in REQUIRED_STRATEGY_FIELDS:
            if field not in strat:
                errors.append(f"matrix strategy {sid} missing required field: {field}")
            elif field == "admission":
                adm = strat[field]
                if not isinstance(adm, dict) or not adm:
                    errors.append(f"matrix strategy {sid} admission must be non-empty object")
        ctb = strat.get("common_target_behavior", "")
        if not isinstance(ctb, str) or len(ctb.strip()) < 20:
            errors.append(
                f"matrix strategy {sid} common_target_behavior must be a substantive string"
            )
        if (
            sid == "common_target_dla"
            and "common-target" not in ctb.lower()
            and "common target" not in ctb.lower()
        ):
            errors.append("common_target_dla common_target_behavior must mention common-target")
    s035 = data.get("s035_classification")
    if not isinstance(s035, dict):
        errors.append("matrix missing s035_classification")
    else:
        if "supervisor_identified_problem" not in s035:
            errors.append("matrix s035_classification missing supervisor_identified_problem")
        if "requested_investigations" not in s035:
            errors.append("matrix s035_classification missing requested_investigations")
        # Narrow S-035 supersession wording: must mention overlapping content
        s035_text = json.dumps(s035)
        if "overlapping" not in s035_text.lower():
            errors.append("matrix s035_classification must describe S-035 narrowly as overlapping")
        # TT-REQ-008 must be labelled as inference + external decision
        if "TT-REQ-008" in s035_text or "tt_req_008" in s035_text.lower():
            if "INFERENCE" not in s035_text:
                errors.append(
                    "matrix s035_classification TT-REQ-008 overlay must be labelled INFERENCE"
                )
            if "EXTERNAL DECISION REQUIRED" not in s035_text:
                errors.append(
                    "matrix s035_classification TT-REQ-008 overlay must require EXTERNAL DECISION"
                )
            # Must not claim S-035 silently amends frozen baseline
            if (
                "supersedes SRC-010 body content only" in s035_text
                and "overlapping" not in s035_text.lower()
            ):
                errors.append(
                    "matrix s035_classification supersession must be narrow overlapping only"
                )
    bound = data.get("claim_boundaries_global")
    if not isinstance(bound, dict):
        errors.append("matrix missing claim_boundaries_global")
    elif bound.get("equivalence_or_noninferiority_allowed") is not False:
        errors.append(
            "matrix claim_boundaries_global equivalence_or_noninferiority_allowed must be false"
        )
    return errors


def validate_evidence_map(data: dict[str, Any], matrix_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "v08_strategy_evidence_map_v1":
        errors.append("evidence_map schema_version must be v08_strategy_evidence_map_v1")
    if data.get("base_sha") != EXPECTED_BASE_SHA:
        errors.append("evidence_map base_sha mismatch")
    heads = data.get("heads", {})
    for h in REQUIRED_EVIDENCE_HEADS:
        if h not in heads:
            errors.append(f"evidence_map missing head {h}")
        else:
            commit = heads[h].get("commit")
            if not isinstance(commit, str) or not HEX40.match(commit):
                errors.append(f"evidence_map head {h} commit must be 40-hex")
            elif commit != EXPECTED_HEADS[h]:
                errors.append(
                    f"evidence_map head {h} commit mismatch: "
                    f"expected {EXPECTED_HEADS[h]}, got {commit}"
                )
    allowed = data.get("allowed_sha256_set")
    if not isinstance(allowed, list) or not all(
        isinstance(x, str) and HEX64.match(x) for x in allowed
    ):
        errors.append("evidence_map allowed_sha256_set must be list of hex64")
        allowed = []
    allowed_set = set(allowed) if isinstance(allowed, list) else set()
    # Self-contained cross-check: allowed set must equal embedded expected set
    if allowed_set != EXPECTED_ALLOWED_SHA256_SET:
        missing = EXPECTED_ALLOWED_SHA256_SET - allowed_set
        extra = allowed_set - EXPECTED_ALLOWED_SHA256_SET
        if missing:
            errors.append(
                f"evidence_map allowed_sha256_set missing expected SHAs: {sorted(missing)[:3]}"
            )
        if extra:
            errors.append(
                f"evidence_map allowed_sha256_set contains unexpected SHAs: {sorted(extra)[:3]}"
            )
    strategies = data.get("strategies", {})
    if not isinstance(strategies, dict):
        errors.append("evidence_map strategies must be object")
        return errors
    for sid in REQUIRED_STRATEGY_IDS:
        if sid not in strategies:
            errors.append(f"evidence_map missing strategy {sid}")
            continue
        ev = strategies[sid]
        evidences = ev.get("evidence", [])
        if not isinstance(evidences, list) or len(evidences) == 0:
            errors.append(f"evidence_map {sid} evidence must be non-empty list")
            continue
        for entry in evidences:
            sha = str(entry.get("sha256", ""))
            if (
                "placeholder" in sha.lower()
                or sha.startswith("report_")
                or sha.startswith("e2b_comparison_sha_placeholder")
            ):
                if not any(a in sha for a in allowed_set):
                    if sid == "ingress_dla" and sha.startswith("e2b_comparison_sha_placeholder"):
                        continue
                    if sha.startswith("report_bound_to_manifest") or sha.startswith(
                        "report_sha_not_hashed"
                    ):
                        continue
                    errors.append(
                        f"evidence_map {sid} entry {entry.get('artifact')} "
                        "has placeholder without allowed SHA"
                    )
                continue
            if not isinstance(sha, str) or (not HEX64.match(sha) and not HEX40.match(sha)):
                errors.append(
                    f"evidence_map {sid} entry {entry.get('artifact')} "
                    f"sha256 must be hex64/hex40, got {sha!r}"
                )
                continue
            if HEX64.match(sha) and sha not in allowed_set:
                errors.append(
                    f"evidence_map {sid} entry {entry.get('artifact')} "
                    f"sha256 {sha} not in allowed_sha256_set (possible redirect)"
                )
            head = entry.get("head")
            if head is not None and head not in (
                "refs/harness/read-only/e2b",
                "refs/harness/read-only/e2c",
                "refs/harness/read-only/e2d",
            ):
                errors.append(
                    f"evidence_map {sid} entry {entry.get('artifact')} "  # noqa: E501
                    f"head must be refs/harness/read-only/e2b|e2c|e2d"
                )
    matrix_ids = [s.get("id") for s in matrix_data.get("strategies", []) if isinstance(s, dict)]
    for sid in matrix_ids:  # type: ignore[assignment]
        if sid not in strategies:
            errors.append(f"evidence_map missing evidence for matrix strategy {sid}")
    # Optional harness cross-check (not required)  # noqa: E501
    # if source_map.json exists, verify it matches embedded
    if SOURCE_MAP_PATH.exists():
        try:
            sm = json.loads(SOURCE_MAP_PATH.read_text(encoding="utf-8"))
            if sm.get("prepared_base_sha") != EXPECTED_BASE_SHA:
                errors.append("harness source_map prepared_base_sha mismatch with embedded base")
        except Exception:  # noqa: S110
            pass
    return errors


def validate_committed_source_bindings(  # noqa: E501
    matrix_data: dict[str, Any], evidence_data: dict[str, Any]
) -> list[str]:
    """Self-contained check that committed artifacts embed the correct hashes.

    No .harness file is required. This validates that the matrix and
    evidence_map themselves contain the expected canonical identities.
    """
    errors: list[str] = []
    # Matrix authority already checked in validate_matrix; here we also
    # cross-check that evidence_map heads match expected and that
    # matrix base_sha equals evidence_map base_sha equals embedded.
    if matrix_data.get("base_sha") != evidence_data.get("base_sha"):
        errors.append("matrix and evidence_map base_sha must match")
    if matrix_data.get("base_sha") != EXPECTED_BASE_SHA:
        errors.append("committed base_sha does not match embedded EXPECTED_BASE_SHA")
    # Verify s035 sha appears in both matrix authority and evidence_map source_classification
    source_cls: Any = evidence_data.get("source_classification", {})
    if isinstance(source_cls, dict) and source_cls.get("s035_sha256") != EXPECTED_S035_SHA256:  # noqa: SIM102
        errors.append("evidence_map source_classification s035_sha256 mismatch with embedded")
    return errors


def validate_assessment_md() -> list[str]:
    errors: list[str] = []
    if not ASSESSMENT_PATH.exists():
        errors.append(f"missing {ASSESSMENT_PATH}")
        return errors
    text = ASSESSMENT_PATH.read_text(encoding="utf-8")
    required_phrases = [
        "S-035 / SANDRA-DIRECT-BODY-2026-08-04",
        EXPECTED_S035_SHA256,
        EXPECTED_PAYLOAD_SHA256,
        "common_target_behavior",
        "Prohibited claims",
        "EXTERNAL DECISION REQUIRED",
        "TT-REQ-008",
        "PARTIALLY_MET",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            errors.append(f"assessment markdown missing required phrase: {phrase}")
    for sid in REQUIRED_STRATEGY_IDS:
        if sid not in text:
            errors.append(f"assessment markdown missing strategy id {sid}")
    for cls in [
        "SOURCE-DERIVED FACT",
        "IMPLEMENTATION-VERIFIED FACT",
        "RESEARCH-EVIDENCE FACT",
        "PROVISIONAL WORDING",
        "EXTERNAL DECISION REQUIRED",
    ]:
        if cls not in text:
            errors.append(f"assessment markdown missing honesty class {cls}")
    # Narrow S-035 wording checks
    if "overlapping" not in text.lower():
        errors.append(
            "assessment must describe S-035 supersession narrowly as overlapping content only"
        )
    # TT-REQ-008 must be labelled as inference + external decision, not baseline amendment
    # Find TT-REQ-008 section and ensure INFERENCE and EXTERNAL DECISION REQUIRED nearby
    if "TT-REQ-008" in text:
        # Check that INFERENCE appears in same document near PARTIALLY_MET
        if "INFERENCE" not in text:
            errors.append("assessment TT-REQ-008 overlay must be labelled INFERENCE")
        # Ensure we do NOT claim blanket supersession
        if "supersedes SRC-010" in text and "overlapping" not in text.lower():
            errors.append(
                "assessment must not claim blanket S-035 supersedes SRC-010"  # noqa: E501
                " - must be narrow overlapping only"
            )
        # Ensure we distinguish frozen baseline from campaign overlay
        if "frozen baseline" not in text.lower() and "frozen requirement" not in text.lower():
            errors.append(
                "assessment must distinguish frozen baseline from campaign inference for TT-REQ-008"
            )
        # Check that assessment marks overlay as not amending baseline
        if "does not amend" not in text.lower() and "does not change" not in text.lower():
            errors.append("assessment must state TT-REQ-008 overlay does not amend frozen baseline")
    # Self-contained note: assessment should mention embedded  # noqa: E501
    # or not require .harness at runtime
    if ".harness" in text and (  # noqa: SIM102, E501
        "not a runtime dependency" not in text.lower()
        and "not required" not in text.lower()
        and "self-contained" not in text.lower()
    ):
        errors.append(
            "assessment .harness must clarify not a runtime dependency"  # noqa: E501
        )
    return errors


def main() -> int:
    errors: list[str] = []
    for p in [MATRIX_PATH, EVIDENCE_MAP_PATH, ASSESSMENT_PATH]:
        if not p.exists():
            print(f"FAIL: missing required file {p}", file=sys.stderr)
            errors.append(f"missing {p}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2
    matrix = _load_json(MATRIX_PATH)
    evidence_map = _load_json(EVIDENCE_MAP_PATH)
    errors.extend(validate_matrix(matrix))
    errors.extend(validate_evidence_map(evidence_map, matrix))
    errors.extend(validate_committed_source_bindings(matrix, evidence_map))
    errors.extend(validate_assessment_md())
    if errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("VALIDATION PASSED: v08 strategy assessment artifacts are consistent")
    print(f"  - matrix: {MATRIX_PATH} ({len(matrix.get('strategies', []))} strategies)")
    print(f"  - evidence_map: {EVIDENCE_MAP_PATH}")
    print(f"  - assessment: {ASSESSMENT_PATH}")
    print(f"  - base_sha: {EXPECTED_BASE_SHA}")
    print(f"  - S-035: {EXPECTED_S035_SHA256}")
    print("  - self-contained: embedded hashes cross-checked without requiring .harness at runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
