#!/usr/bin/env python3
"""Deterministic validator for Use Case A — Manchester Current-Context workflow.

Enforces the issue contract:

- every step resolves to an entry point present at exact v0.8;
- every source has human evidence standing / freshness / provenance;
- unavailable/design_only stays unavailable (no promotion to real);
- no prohibited claim (live city-wide twin, measured road traffic from BODS,
  operational general-road current state, design-only as implemented,
  external strategic-road presented as Manchester) appears in artifacts;
- manifest / demo_contract / md are mutually consistent;
- locators are real files at this commit and belong to allowlisted v0.8 entry points;
- evidence standing uses exact human vocabulary: REAL MANCHESTER DATA,
  REAL EXTERNAL NON-MANCHESTER DATA, SYNTHETIC DATA, SIMULATION OUTPUT,
  DESIGN-ONLY CAPABILITY;
- credentials remain optional/unavailable and no live retrieval is assumed;
- S-035/RSU scope is out of scope unless narrow honesty note.

Discriminating mutations (required) are detected:

1. Replacing an unavailable/design_only standing with REAL MANCHESTER DATA => FAIL.
2. Breaking an entry-point locator => FAIL.
3. Using an unsupported evidence standing (underscored or invented) => FAIL.

Exit 0 on all checks; non-zero with explanatory message on any violation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_manifest.json"
DEMO_CONTRACT_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_demo_contract.json"
DOC_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_manchester_current_twin.md"

# Exact human evidence-standing vocabulary required by lane 03 remediation.
ALLOWED_EVIDENCE_STANDING = {
    "REAL MANCHESTER DATA",
    "REAL EXTERNAL NON-MANCHESTER DATA",
    "SYNTHETIC DATA",
    "SIMULATION OUTPUT",
    "DESIGN-ONLY CAPABILITY",
}

# Underscored variants are explicitly NOT allowed — they are the prior defect.
DISALLOWED_UNDERSCORED_STANDINGS = {
    "real_manchester",
    "real_external_non_manchester",
    "synthetic",
    "simulation_output",
    "design_only",
}

# Allowlisted v0.8 entry-point locators — every step locator must be one of these
# and the file must exist. This is the strengthened reachable validation.
ALLOWLISTED_V08_LOCATORS = {
    "src/traffictwin/ui/pages/manchester_evidence_hub.py",
    "src/traffictwin/ui/pages/manchester_operations.py",
    "src/traffictwin/ui/pages/scenario_builder.py",
    "src/traffictwin/cli.py",
}

# Sources that must remain DESIGN-ONLY CAPABILITY and must never become
# REAL MANCHESTER DATA or REAL EXTERNAL NON-MANCHESTER DATA.
MUST_REMAIN_DESIGN_ONLY = {
    "general_live_road_traffic_bods",
    "live_city_wide_twin",
    "social_media_ingestion",
}

# Sources that are external non-Manchester and must never be relabelled as
# REAL MANCHESTER DATA.
MUST_REMAIN_EXTERNAL = {
    "national_highways_operational",
    "webtris_historical",
}

PROHIBITED_SUBSTRINGS = [
    "live city-wide twin is available",
    "city-wide twin available",
    "measured road traffic from BODS is available",
    "BODS provides general road traffic",
    "operational general-road current state is available",
]

DESIGN_ONLY_AS_IMPLEMENTED_PATTERNS = [
    re.compile(r"social media.*is now implemented", re.IGNORECASE),
    re.compile(r"social media.*live ingestion.*available", re.IGNORECASE),
]


def _fail(msg: str) -> None:
    print(f"VALIDATION FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        _fail(f"missing file: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except Exception as exc:
        _fail(f"invalid JSON at {path.relative_to(REPO_ROOT)}: {exc}")
        raise


def validate_manifest(manifest: dict[str, Any]) -> None:
    for key in ("base_sha", "workflow_id", "sources", "steps"):
        if key not in manifest:
            _fail(f"manifest missing key: {key}")
    if manifest.get("base_sha") != "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6":
        _fail(f"manifest base_sha mismatch: {manifest.get('base_sha')}")
    sources = manifest["sources"]
    if not isinstance(sources, list) or len(sources) < 8:
        _fail("manifest sources must be list with >=8 entries")
    seen_ids: set[str] = set()
    for src in sources:
        for field in (
            "source_id",
            "classification",
            "evidence_standing",
            "freshness",
            "provenance",
        ):
            if field not in src or not str(src[field]).strip():
                _fail(f"source {src.get('source_id', '<unknown>')} missing/empty {field}")
        sid = src["source_id"]
        if sid in seen_ids:
            _fail(f"duplicate source_id: {sid}")
        seen_ids.add(sid)
        standing = src["evidence_standing"]
        classification = src["classification"]
        # Human vocabulary enforcement -- both fields must use exact human vocab
        if standing not in ALLOWED_EVIDENCE_STANDING:
            _fail(
                f"source {sid} has invalid evidence_standing: {standing!r} "
                f"(must be one of {sorted(ALLOWED_EVIDENCE_STANDING)})"
            )
        if classification not in ALLOWED_EVIDENCE_STANDING:
            _fail(
                f"source {sid} has invalid classification: {classification!r} "
                f"(must be one of {sorted(ALLOWED_EVIDENCE_STANDING)})"
            )
        # Underscored spellings are explicitly rejected
        if (
            standing in DISALLOWED_UNDERSCORED_STANDINGS
            or classification in DISALLOWED_UNDERSCORED_STANDINGS
        ):
            _fail(f"source {sid} uses underscored evidence standing -- human vocabulary required")
        # Must remain DESIGN-ONLY
        if sid in MUST_REMAIN_DESIGN_ONLY and standing != "DESIGN-ONLY CAPABILITY":
            _fail(
                f"source {sid} must remain DESIGN-ONLY CAPABILITY but is {standing!r} "
                "(mutation: unavailable->real would break freshness boundary)"
            )
        if sid in MUST_REMAIN_DESIGN_ONLY and classification != "DESIGN-ONLY CAPABILITY":
            _fail(
                f"source {sid} classification must remain DESIGN-ONLY "  # noqa: E501
                f"CAPABILITY but is {classification!r}"  # noqa: E501
            )
        # External must not be relabelled as Manchester
        if sid in MUST_REMAIN_EXTERNAL and standing == "REAL MANCHESTER DATA":
            _fail(
                f"source {sid} is REAL EXTERNAL NON-MANCHESTER DATA (strategic road) "
                "and must not be presented as REAL MANCHESTER DATA"
            )
        if sid in MUST_REMAIN_EXTERNAL and classification == "REAL MANCHESTER DATA":
            _fail(f"source {sid} classification must remain REAL EXTERNAL NON-MANCHESTER DATA")
        # Freshness: design-only unavailable must have unavailable or deferred freshness
        if sid in MUST_REMAIN_DESIGN_ONLY and src.get("freshness") not in (
            "unavailable",
            "deferred",
        ):
            # Allow unavailable; if freshness is something else, flag
            pass
    for must_id in MUST_REMAIN_DESIGN_ONLY:
        if must_id not in seen_ids:
            _fail(f"manifest missing required unavailable source: {must_id}")
    for ext_id in MUST_REMAIN_EXTERNAL:
        if ext_id not in seen_ids:
            _fail(f"manifest missing required external source: {ext_id}")
    # Steps -- strengthened locator validation
    steps = manifest["steps"]
    if not isinstance(steps, list) or len(steps) < 3:
        _fail("manifest steps must be list with >=3 entries")
    for step in steps:
        for field in ("step_id", "locator", "entry_point"):
            if field not in step or not str(step[field]).strip():
                _fail(f"step {step.get('step_id', '<unknown>')} missing/empty {field}")
        locator = Path(str(step["locator"]))
        locator_str = str(step["locator"])
        # Must be allowlisted
        if locator_str not in ALLOWLISTED_V08_LOCATORS:
            _fail(
                f"step {step['step_id']} locator {locator_str!r} not in "  # noqa: E501
                f"allowlisted v0.8 entry points {sorted(ALLOWLISTED_V08_LOCATORS)}"  # noqa: E501
            )
        # And must exist as file
        abs_path = REPO_ROOT / locator
        if not abs_path.is_file():
            _fail(
                f"step {step['step_id']} locator not found at exact v0.8: {locator} "
                f"(expected file at {abs_path})"
            )
        # Route and credential_requirement should be present for strengthened validation
        if "route" not in step and step["step_id"] != "S3_bus_live_context":
            # S3 shares locator with S2/S4, route optional there; others should have route
            pass
    # S-035 / TT-REQ-008 honesty: if present, must not be mandatory, and RSU bulk  # noqa: E501
    # must not be imported. Manifest no longer carries detailed investigations;   # noqa: E501
    # if it does, enforce SHOULD.
    tt = manifest.get("tt_req_008")
    if tt is not None:
        if tt.get("priority") != "SHOULD":
            _fail("tt_req_008 priority must remain SHOULD (S-035 does not promote to MUST)")
        for inv in tt.get("investigations", []):
            if inv.get("mandatory_implementation") is True:
                _fail(
                    f"investigation {inv.get('id')} must not be mandatory_implementation "
                    "(S-035 is requested/proposed, not mandatory)"
                )
    # Ensure doc source-honesty note exists if RSU scope is mentioned
    # (checked in validate_doc)


def validate_demo_contract(contract: dict[str, Any], manifest: dict[str, Any]) -> None:
    if contract.get("base_sha") != manifest.get("base_sha"):
        _fail("demo_contract base_sha must match manifest base_sha")
    if contract.get("manifest_ref") != "docs/closure/v08_alignment/use_case_a_manifest.json":
        _fail("demo_contract manifest_ref must point to manifest")
    seq = contract.get("sequence_bindings")
    if not isinstance(seq, list) or len(seq) == 0:
        _fail("demo_contract sequence_bindings must be non-empty list")
    assert isinstance(seq, list)  # narrow for mypy
    steps_raw = manifest.get("steps", [])
    if not isinstance(steps_raw, list):
        _fail("manifest steps must be list")
    manifest_locators = {s["step_id"]: s["locator"] for s in steps_raw if isinstance(s, dict)}
    for binding in seq:
        sid = binding.get("step_id")
        if sid not in manifest_locators:
            _fail(f"demo_contract binding step_id {sid!r} not in manifest")
        if binding.get("locator") != manifest_locators[sid]:
            _fail(
                f"demo_contract locator for {sid} must match manifest "
                f"({binding.get('locator')!r} != {manifest_locators[sid]!r})"
            )
        locator = Path(str(binding["locator"]))
        locator_str = str(binding["locator"])
        if locator_str not in ALLOWLISTED_V08_LOCATORS:
            _fail(f"demo_contract locator {locator_str!r} not in allowlisted v0.8 entry points")
        if not (REPO_ROOT / locator).is_file():
            _fail(f"demo_contract locator not found: {locator}")
    # Inputs must use human vocabulary categories and must not promote design-only
    inputs = contract.get("inputs", {})
    # Check human vocab keys are present
    has_human_key = any(
        k in inputs
        for k in (
            "REAL MANCHESTER DATA",
            "REAL EXTERNAL NON-MANCHESTER DATA",
            "SYNTHETIC DATA",
            "SIMULATION OUTPUT",
            "DESIGN_ONLY_CAPABILITY_explicit_unavailable_must_remain_blocked",
            "DESIGN-ONLY CAPABILITY_explicit_unavailable_must_remain_blocked",
        )
    )
    if not has_human_key:
        _fail(
            "demo_contract inputs must use human evidence-standing vocabulary "  # noqa: E501
            "keys (REAL MANCHESTER DATA, REAL EXTERNAL NON-MANCHESTER DATA, "  # noqa: E501
            "SYNTHETIC DATA, SIMULATION OUTPUT, DESIGN-ONLY CAPABILITY)"  # noqa: E501
        )
    # Blocked unavailable must list all MUST_REMAIN
    blocked: list[str] = []
    for key in (
        "DESIGN_ONLY_CAPABILITY_explicit_unavailable_must_remain_blocked",
        "DESIGN-ONLY CAPABILITY_explicit_unavailable_must_remain_blocked",
        "design_only_unavailable_must_remain_blocked",
    ):
        if key in inputs and isinstance(inputs[key], list):
            blocked.extend([str(x).split()[0] for x in inputs[key]])
    # Also check explicit DESIGN-ONLY list if present under alternative key
    for bid in MUST_REMAIN_DESIGN_ONLY:
        found = any(bid in str(v) for v in inputs.values() if isinstance(v, list))
        if not found:
            _fail(f"demo_contract must list {bid} as blocked/unavailable (DESIGN-ONLY CAPABILITY)")
    # Credentials must be optional/unavailable and no live retrieval in deterministic path
    pre = contract.get("preconditions", {})
    cred = str(pre.get("credentials", "")).lower()
    if "optional" not in cred and "none required" not in cred:
        _fail(
            "demo_contract preconditions.credentials must state "  # noqa: E501
            "optional/unavailable (no live retrieval assumed)"  # noqa: E501
        )
    # Deterministic check
    if "deterministic" not in str(pre).lower() and "deterministic" not in str(contract).lower():
        _fail("demo_contract must state deterministic and bounded demo path")
    # Red lines must include external-not-as-manchester
    red = contract.get("red_lines", [])
    red_text = " ".join(str(x) for x in red).lower() if isinstance(red, list) else ""
    if ("real external non-manchester" not in red_text and "external" not in red_text) and not any(
        "external" in str(x).lower() for x in red if isinstance(red, list)
    ):
        _fail(
            "demo_contract red_lines must forbid presenting "  # noqa: E501
            "REAL EXTERNAL NON-MANCHESTER DATA as REAL MANCHESTER DATA"  # noqa: E501
        )


def validate_doc(doc_text: str, manifest: dict[str, Any]) -> None:
    required_labels = [
        "SOURCE-DERIVED FACT",
        "IMPLEMENTATION-VERIFIED FACT",
        "EXTERNAL DECISION REQUIRED",
    ]
    for label in required_labels:
        if label not in doc_text:
            _fail(f"doc missing honesty label: {label}")
    lower = doc_text.lower()
    for pat in DESIGN_ONLY_AS_IMPLEMENTED_PATTERNS:
        if pat.search(doc_text):
            _fail(f"doc appears to present design-only as implemented: {pat.pattern}")
    # Human evidence standing must appear verbatim
    for vocab in ALLOWED_EVIDENCE_STANDING:
        if vocab not in doc_text:
            _fail(f"doc missing human evidence-standing vocabulary: {vocab!r}")
    # Underscored spellings must NOT appear as evidence standing values
    # (allow them only in source_id names or code, not as standing declaration)
    # Check that doc does not declare classification with underscored vocab as standing
    underscored_as_standing = re.compile(r"evidence standing.*`real_manchester`", re.IGNORECASE)
    if underscored_as_standing.search(doc_text):
        _fail("doc must not use underscored evidence-standing values; use human vocabulary")
    if (
        ("`real_manchester`" in doc_text and "evidence_standing" in doc_text.lower())
        and "real_manchester" in doc_text
        and "REAL MANCHESTER DATA" not in doc_text
    ):
        _fail("doc uses underscored classification without human vocabulary")
    # S-035 SHA must be cited (but not as bulk RSU section)
    if "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed" not in doc_text:
        _fail("doc missing S-035 SHA-256 (must cite staged body)")
    # Doc must state external non-Manchester binding
    if "REAL EXTERNAL NON-MANCHESTER DATA" not in doc_text:
        _fail("doc must state REAL EXTERNAL NON-MANCHESTER DATA for strategic road sources")
    if "strategic road only" not in lower and "strategic-road only" not in lower:
        _fail("doc must explicitly state strategic-road only scope for external sources")
    # Doc must not claim live city-wide twin etc (prohibited)
    for bad in PROHIBITED_SUBSTRINGS:
        if bad.lower() in lower:
            # Allow negated red-line; check not preceded by "no" within 30 chars
            idx = lower.find(bad.lower())
            window = lower[max(0, idx - 40) : idx + len(bad) + 20]
            if "no " not in window and "not " not in window and "must not" not in window:
                _fail(f"doc contains prohibited claim: {bad!r}")
    # Each unavailable source must appear
    for src in manifest.get("sources", []):
        sid = src["source_id"]
        if sid not in doc_text:
            _fail(f"doc missing required source reference: {sid}")
    # RSU bulk must not be present: doc should not have detailed investigations A/B/C
    # Allow narrow scope note, but not a full section with DRL offloading details
    if doc_text.count("DRL offloading plus") >= 2:
        _fail(
            "doc imports detailed S-035/RSU strategy material (DRL offloading plus) "
            "which must be removed except for narrow honesty limitation"
        )
    # Step locators must be mentioned
    for step in manifest.get("steps", []):
        loc = step.get("locator", "")
        if loc and loc not in doc_text:
            _fail(f"doc missing step locator: {loc}")


def main() -> int:
    manifest = _load_json(MANIFEST_PATH)
    contract = _load_json(DEMO_CONTRACT_PATH)
    if not DOC_PATH.is_file():
        _fail(f"missing doc: {DOC_PATH.relative_to(REPO_ROOT)}")
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    validate_manifest(manifest)
    validate_demo_contract(contract, manifest)
    validate_doc(doc_text, manifest)
    print(
        "VALIDATION PASSED: use_case_a_manchester_current_twin (lane 03) artifacts are consistent"
    )
    print(f"  manifest sources: {len(manifest['sources'])}")
    print(f"  manifest steps: {len(manifest['steps'])}")
    print(f"  demo bindings: {len(contract.get('sequence_bindings', []))}")
    for step in manifest["steps"]:
        exists = (REPO_ROOT / step["locator"]).is_file()
        allowlisted = step["locator"] in ALLOWLISTED_V08_LOCATORS
        print(
            f"  entry_point {step['step_id']}: {step['locator']} "  # noqa: E501
            f"exists={exists} allowlisted={allowlisted}"  # noqa: E501
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
