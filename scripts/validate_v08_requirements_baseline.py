#!/usr/bin/env python3
"""Validate v08 requirements baseline operationalisation.

Checks (acceptance criteria):
- recomputes canonical payload hash and count
- IDs unique
- all MUSTs have criteria
- every PARTIALLY_MET has named gap
- every source resolves
- status vocabulary closed
- baseline quotations no drift
- conditional triggers explicit
- MUST arithmetic 3+7+1 and never 3+7+0

Exit 0 on pass, 1 on failure. Prints details to stdout.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGED_BASELINE = (
    REPO_ROOT / ".harness/context/sources/NEGOTIATED_V1_WHOLE_FILE__canonical_baseline_v1.md"
)
BASELINE_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_baseline_v1.json"
SOURCE_MAP_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_source_map.json"
STATUS_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_status_v08.json"

EXPECTED_PAYLOAD_SHA = "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
EXPECTED_WHOLE_SHA = "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2"
ALLOWED_PRIORITIES = {"MUST", "SHOULD", "MAY"}
ALLOWED_STATUSES = {"VERIFIED_MET", "PARTIALLY_MET", "NOT_APPLICABLE", "DECISION_REQUIRED"}
# MUST may only use these
MUST_ALLOWED_STATUSES = {"VERIFIED_MET", "PARTIALLY_MET", "NOT_APPLICABLE"}


def compute_payload_hash() -> str:
    text = STAGED_BASELINE.read_text(encoding="utf-8")
    begin = "<!-- BEGIN CANONICAL PAYLOAD -->"
    end = "<!-- END CANONICAL PAYLOAD -->"
    if begin not in text or end not in text:
        raise ValueError("canonical payload delimiters missing")
    payload = text.split(begin)[1].split(end)[0]
    # Spec: after delimiter newline
    if payload.startswith("\n"):
        payload = payload[1:]
    # payload now is exact bytes before END line (no trailing delimiter)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_whole_hash() -> str:
    data = STAGED_BASELINE.read_bytes()
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def extract_canonical_quotations_from_payload() -> dict[str, str]:
    """Extract id -> canonical inner wording from staged payload."""
    text = STAGED_BASELINE.read_text(encoding="utf-8")
    # Only inspect payload region to avoid drift outside
    payload = text.split("<!-- BEGIN CANONICAL PAYLOAD -->")[1].split(
        "<!-- END CANONICAL PAYLOAD -->"
    )[0]
    import re

    # Find each TT-REQ block in payload
    pattern = re.compile(r"## (TT-REQ-\d{3}).*?\*\*Canonical wording:\*\*.*?\"(.*?)\"", re.DOTALL)
    out: dict[str, str] = {}
    for m in pattern.finditer(payload):
        rid = m.group(1)
        wording = m.group(2).strip()
        # Normalise: payload uses exact sentence without surrounding quotes already stripped
        out[rid] = wording
    return out


def validate() -> list[str]:
    errors: list[str] = []

    # File existence
    for p in [STAGED_BASELINE, BASELINE_JSON, SOURCE_MAP_JSON, STATUS_JSON]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
    if errors:
        return errors

    # Hash checks
    payload_hash = compute_payload_hash()
    if payload_hash != EXPECTED_PAYLOAD_SHA:
        errors.append(f"payload hash mismatch: got {payload_hash} expected {EXPECTED_PAYLOAD_SHA}")
    whole_hash = compute_whole_hash()
    if whole_hash != EXPECTED_WHOLE_SHA:
        errors.append(f"whole file hash mismatch: got {whole_hash} expected {EXPECTED_WHOLE_SHA}")

    baseline = load_json(BASELINE_JSON)
    source_map = load_json(SOURCE_MAP_JSON)
    status = load_json(STATUS_JSON)

    # Baseline JSON hash fields must match expected
    if baseline.get("canonical_payload_sha256") != EXPECTED_PAYLOAD_SHA:
        errors.append("baseline JSON canonical_payload_sha256 drift")
    if baseline.get("whole_file_sha256") != EXPECTED_WHOLE_SHA:
        errors.append("baseline JSON whole_file_sha256 drift")
    if baseline.get("total_requirements") != 14:
        errors.append(f"baseline total_requirements !=14 got {baseline.get('total_requirements')}")
    if baseline.get("must_count") != 11:
        errors.append(f"baseline must_count !=11 got {baseline.get('must_count')}")

    reqs = baseline.get("requirements", [])
    if len(reqs) != 14:
        errors.append(f"baseline requirements count !=14 got {len(reqs)}")

    ids = [r.get("id") for r in reqs]
    if len(ids) != len(set(ids)):
        errors.append(f"baseline IDs not unique: {ids}")
    expected_ids = {f"TT-REQ-{i:03d}" for i in range(1, 15)}
    if set(ids) != expected_ids:
        errors.append(f"baseline IDs mismatch expected 001-014 got {sorted(set(ids))}")

    # Priority counts
    pri_counts: dict[str, int] = {}
    for r in reqs:
        pri = r.get("priority")
        if pri not in ALLOWED_PRIORITIES:
            errors.append(f"{r.get('id')} invalid priority {pri}")
        pri_counts[pri] = pri_counts.get(pri, 0) + 1
        # MUST must have acceptance criteria
        if pri == "MUST":
            ac = r.get("acceptance_criteria")
            if not isinstance(ac, list) or len(ac) == 0:
                errors.append(f"{r.get('id')} MUST missing acceptance_criteria")
        # conditional trigger explicit: check 011,012,013,008,014,009 have conditional_trigger true
        # Also any requirement with conditional wording should be flagged
        conditional_ids = {
            "TT-REQ-008",
            "TT-REQ-009",
            "TT-REQ-011",
            "TT-REQ-012",
            "TT-REQ-013",
            "TT-REQ-014",
        }
        # Enforce that 011,012,013 are marked conditional (MUST conditionals)
        if r.get("id") in {"TT-REQ-011", "TT-REQ-012", "TT-REQ-013"}:
            if r.get("conditional_trigger") is not True:
                errors.append(f"{r.get('id')} must have conditional_trigger true")
            if not r.get("conditional_trigger_text"):
                errors.append(f"{r.get('id')} missing conditional_trigger_text")
        # For others, if they are conditional, check text present
        if r.get("id") in conditional_ids and r.get("conditional_trigger") is True:  # noqa: SIM102
            if not r.get("conditional_trigger_text"):  # noqa: SIM102
                errors.append(f"{r.get('id')} conditional but missing trigger text")

    if pri_counts.get("MUST", 0) != 11:
        errors.append(f"MUST count !=11 got {pri_counts.get('MUST', 0)}")
    if pri_counts.get("SHOULD", 0) != 2:
        errors.append(f"SHOULD count !=2 got {pri_counts.get('SHOULD', 0)}")
    if pri_counts.get("MAY", 0) != 1:
        errors.append(f"MAY count !=1 got {pri_counts.get('MAY', 0)}")

    # Canonical quotation drift
    payload_quotations = extract_canonical_quotations_from_payload()
    for r in reqs:
        rid = r.get("id")
        json_q = r.get("canonical_quotation", "").strip()
        # The frozen payload stores sentence without surrounding quotes; json should match exactly
        expected_q = payload_quotations.get(rid)
        if expected_q is None:
            errors.append(f"{rid} quotation not found in payload")
        elif json_q != expected_q:
            errors.append(
                f"{rid} quotation drift: json {repr(json_q[:60])} vs payload {repr(expected_q[:60])}"  # noqa: E501
            )

    # Source resolution
    # Build resolvable source ids from source_map
    resolvable: set[str] = set()
    for s in source_map.get("sources", []):
        sid = s.get("id")
        if sid:
            resolvable.add(sid)
    for s in source_map.get("extended_index", []):
        sid = s.get("id")
        if sid:
            resolvable.add(sid)
    # Also frozen refs not needed but ensure primary ids present
    for r in reqs:
        for sid in r.get("source_basis", []):
            # Handle S-035 campaign key variant
            base_sid = sid.split()[0] if " " in sid else sid
            # Allow S-035 with suffix
            if sid.startswith("S-035"):
                base_sid = "S-035"
            if base_sid not in resolvable:
                errors.append(f"{r.get('id')} source {sid} not resolvable in source_map")
            # Also handle S- prefix check
            if base_sid not in resolvable:
                errors.append(f"{r.get('id')} source {base_sid} missing from source_map")

    # Standing for authoritative sources: verify SHA where expected
    expected_shas = {
        "S-001": "d2940e257e455de3f6694d59d66c4d3661471c732618700ad34b4d65240597b0",
        "S-003": "c88175e344c8aa0cfd5eba6164a8b5941670c7cc5bb69e89213c6c019bcd8c0f",
        "S-004": "df504ec76271f2cb4b2fa34be1f53f55d1363e65d4352456f856a92178d3da82",
        "S-007": "e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4",
        "S-035": "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed",
    }
    source_by_id = {s.get("id"): s for s in source_map.get("sources", [])}
    for sid, sha in expected_shas.items():
        entry = source_by_id.get(sid)
        if entry is None:
            errors.append(f"source_map missing authoritative source {sid}")
        elif entry.get("sha256") != sha:
            errors.append(
                f"source_map {sid} sha256 mismatch got {entry.get('sha256')} expected {sha}"
            )

    # Check S-035 campaign key not using SRC-011 alone
    # Ensure S-035 entry has campaign_key and does not rely on SRC-011
    s035 = source_by_id.get("S-035")
    if s035 is None:
        errors.append("source_map missing S-035")
    else:
        if s035.get("campaign_key") != "S-035 / SANDRA-DIRECT-BODY-2026-08-04":
            errors.append(
                "S-035 campaign_key must be exact 'S-035 / SANDRA-DIRECT-BODY-2026-08-04'"
            )
        if s035.get("standing") != "DIRECT_SUPERVISOR_SOURCE_BODY":
            errors.append("S-035 standing must be DIRECT_SUPERVISOR_SOURCE_BODY")

    # Status validation
    status_reqs = status.get("requirements", [])
    if len(status_reqs) != 14:
        errors.append(f"status requirements count !=14 got {len(status_reqs)}")
    status_ids = [r.get("id") for r in status_reqs]
    if set(status_ids) != expected_ids:
        errors.append(f"status IDs mismatch expected 001-014 got {sorted(status_ids)}")
    if len(status_ids) != len(set(status_ids)):
        errors.append("status IDs not unique")

    # Vocabulary closed
    for r in status_reqs:
        st = r.get("status")
        if st not in ALLOWED_STATUSES:
            errors.append(f"{r.get('id')} status {st} not in closed vocabulary {ALLOWED_STATUSES}")
        pri = r.get("priority")
        if pri == "MUST" and st not in MUST_ALLOWED_STATUSES:
            errors.append(f"{r.get('id')} MUST status {st} not allowed {MUST_ALLOWED_STATUSES}")
        if st == "PARTIALLY_MET":  # noqa: SIM102
            if not r.get("gap_id") or not r.get("gap_description"):  # noqa: SIM102
                errors.append(f"{r.get('id')} PARTIALLY_MET missing named gap")
        if st == "VERIFIED_MET":  # noqa: SIM102
            if r.get("gap_id") is not None and r.get("gap_id") not in (None, ""):  # noqa: SIM102
                # allow null gap for verified
                if r.get("gap_id"):
                    errors.append(f"{r.get('id')} VERIFIED_MET must not have gap_id")
        if st == "NOT_APPLICABLE":
            # Must be TT-REQ-013 only for MUST
            if r.get("id") != "TT-REQ-013":
                errors.append(f"NOT_APPLICABLE only allowed for TT-REQ-013 got {r.get('id')}")
            if r.get("conditional_trigger_observed") is not False:
                errors.append(f"{r.get('id')} NOT_APPLICABLE trigger_not_observed must be false")
            if "trigger" not in (r.get("conditional_trigger_text") or "").lower():
                errors.append(f"{r.get('id')} NOT_APPLICABLE missing conditional trigger text")

    # MUST arithmetic — recompute from status entries and compare to declared
    must_entries = [r for r in status_reqs if r.get("priority") == "MUST"]
    computed_verified = sum(1 for r in must_entries if r.get("status") == "VERIFIED_MET")
    computed_partial = sum(1 for r in must_entries if r.get("status") == "PARTIALLY_MET")
    computed_na = sum(1 for r in must_entries if r.get("status") == "NOT_APPLICABLE")
    if computed_verified != 3 or computed_partial != 7 or computed_na != 1:
        errors.append(
            f"MUST arithmetic recomputed 3+7+1 violated: got {computed_verified}+{computed_partial}+{computed_na}=11"  # noqa: E501
        )
    must_arith = status.get("must_arithmetic", {})
    if must_arith.get("total_must") != 11:
        errors.append("must_arithmetic total_must !=11")
    if must_arith.get("verified_met") != 3:
        errors.append(f"must_arithmetic verified_met !=3 got {must_arith.get('verified_met')}")
    if must_arith.get("partially_met") != 7:
        errors.append(f"must_arithmetic partially_met !=7 got {must_arith.get('partially_met')}")
    if must_arith.get("not_applicable_trigger_not_observed") != 1:
        errors.append("must_arithmetic not_applicable !=1")
    # Check sets match
    if set(must_arith.get("verified_met_ids", [])) != {"TT-REQ-006", "TT-REQ-010", "TT-REQ-012"}:
        errors.append(f"verified_met_ids mismatch got {must_arith.get('verified_met_ids')}")
    if set(must_arith.get("partially_met_ids", [])) != {
        "TT-REQ-001",
        "TT-REQ-002",
        "TT-REQ-003",
        "TT-REQ-004",
        "TT-REQ-005",
        "TT-REQ-007",
        "TT-REQ-011",
    }:
        errors.append(f"partially_met_ids mismatch got {must_arith.get('partially_met_ids')}")
    if must_arith.get("not_applicable_ids") != ["TT-REQ-013"]:
        errors.append(f"not_applicable_ids mismatch got {must_arith.get('not_applicable_ids')}")
    # Prohibit 3+7+0 as claimed valid arithmetic: ensure no field asserts 3+7+0=11 as the true count
    # The string "3+7+0" may appear in explanatory notes about what is prohibited; check only the must_arith check field  # noqa: E501  # noqa: E501
    check_field = must_arith.get("check", "")
    if (
        "3+7+0=11" in check_field
        and "never" not in check_field
        and "prohibited" not in check_field.lower()
    ):
        errors.append("prohibited 3+7+0 arithmetic asserted as valid")

    # Also check status file payload hash matches
    if status.get("baseline_payload_sha256") != EXPECTED_PAYLOAD_SHA:
        errors.append("status baseline_payload_sha256 drift")

    # Check external decisions present
    ext = status.get("external_decisions", [])
    if not isinstance(ext, list) or len(ext) < 5:
        errors.append(
            f"external_decisions must list >=5 got {len(ext) if isinstance(ext, list) else 'non-list'}"  # noqa: E501
        )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("VALIDATION FAILED")
        for e in errors:
            print(f" - {e}")
        return 1
    print("VALIDATION PASSED")
    print(f"payload_sha256={EXPECTED_PAYLOAD_SHA}")
    print(f"whole_sha256={EXPECTED_WHOLE_SHA}")
    print("IDs=14 unique, MUST=11, SHOULD=2, MAY=1")
    print("MUST arithmetic: 3 VERIFIED_MET + 7 PARTIALLY_MET + 1 NOT_APPLICABLE = 11")
    print(
        "All MUSTs have acceptance criteria; all PARTIALLY_MET have named gaps; all sources resolve; vocabulary closed; quotations no drift; triggers explicit"  # noqa: E501
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
