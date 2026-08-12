#!/usr/bin/env python3
"""Validate v08 requirements baseline operationalisation.

Checks (acceptance criteria):
- recomputes canonical payload hash and count from committed artifact
- IDs unique
- all MUSTs have criteria
- every PARTIALLY_MET has named gap
- every source resolves
- status vocabulary closed
- baseline quotations no drift
- conditional triggers explicit
- MUST arithmetic 3+7+1 and never 3+7+0

Self-contained: recomputes hashes from docs/closure/v08_alignment/
requirements_baseline_v1.json canonical_payload and whole_file_content
fields (both committed). No runtime dependency on .harness.

Exit 0 on pass, 1 on failure. Prints details to stdout.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_baseline_v1.json"
SOURCE_MAP_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_source_map.json"
STATUS_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_status_v08.json"

EXPECTED_PAYLOAD_SHA = "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
EXPECTED_WHOLE_SHA = "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2"
ALLOWED_PRIORITIES = {"MUST", "SHOULD", "MAY"}
ALLOWED_STATUSES = {"VERIFIED_MET", "PARTIALLY_MET", "NOT_APPLICABLE", "DECISION_REQUIRED"}
# MUST may only use these
MUST_ALLOWED_STATUSES = {"VERIFIED_MET", "PARTIALLY_MET", "NOT_APPLICABLE"}


def _load_baseline_data() -> dict[str, Any]:
    return json.loads(BASELINE_JSON.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _canonical_payload_text() -> str:
    data = _load_baseline_data()
    payload = data.get("canonical_payload")
    if not isinstance(payload, str):
        raise ValueError("baseline JSON missing canonical_payload self-contained field")
    return payload


def _whole_file_text() -> str:
    data = _load_baseline_data()
    whole = data.get("whole_file_content")
    if not isinstance(whole, str):
        raise ValueError("baseline JSON missing whole_file_content self-contained field")
    return whole


def compute_payload_hash() -> str:
    payload = _canonical_payload_text()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_whole_hash() -> str:
    whole = _whole_file_text()
    return hashlib.sha256(whole.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def extract_canonical_quotations_from_payload() -> dict[str, str]:
    """Extract id -> canonical inner wording from committed payload."""
    payload = _canonical_payload_text()
    import re

    pattern = re.compile(r"## (TT-REQ-\d{3}).*?\*\*Canonical wording:\*\*.*?\"(.*?)\"", re.DOTALL)
    out: dict[str, str] = {}
    for m in pattern.finditer(payload):
        rid = m.group(1)
        wording = m.group(2).strip()
        out[rid] = wording
    return out


def validate() -> list[str]:
    errors: list[str] = []

    # File existence — only the six allowed committed artifacts
    for p in [BASELINE_JSON, SOURCE_MAP_JSON, STATUS_JSON]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
    if errors:
        return errors

    # Hash checks — recomputed from committed JSON fields
    try:
        payload_hash = compute_payload_hash()
    except Exception as e:
        errors.append(f"payload hash recomputation failed: {e}")
        payload_hash = ""
    if payload_hash and payload_hash != EXPECTED_PAYLOAD_SHA:
        errors.append(f"payload hash mismatch: got {payload_hash} expected {EXPECTED_PAYLOAD_SHA}")

    try:
        whole_hash = compute_whole_hash()
    except Exception as e:
        errors.append(f"whole file hash recomputation failed: {e}")
        whole_hash = ""
    if whole_hash and whole_hash != EXPECTED_WHOLE_SHA:
        errors.append(f"whole file hash mismatch: got {whole_hash} expected {EXPECTED_WHOLE_SHA}")

    baseline = load_json(BASELINE_JSON)
    source_map = load_json(SOURCE_MAP_JSON)
    status = load_json(STATUS_JSON)

    # Baseline JSON hash fields must match expected
    if baseline.get("canonical_payload_sha256") != EXPECTED_PAYLOAD_SHA:
        errors.append("baseline JSON canonical_payload_sha256 drift")
    if baseline.get("whole_file_sha256") != EXPECTED_WHOLE_SHA:
        errors.append("baseline JSON whole_file_sha256 drift")
    # Self-contained payload fields must be present
    if not isinstance(baseline.get("canonical_payload"), str):
        errors.append("baseline JSON missing canonical_payload self-contained field")
    if not isinstance(baseline.get("whole_file_content"), str):
        errors.append("baseline JSON missing whole_file_content self-contained field")
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

    # Canonical quotation drift — compare JSON vs committed payload
    payload_quotations = extract_canonical_quotations_from_payload()
    for r in reqs:
        rid = r.get("id")
        json_q = r.get("canonical_quotation", "").strip()
        expected_q = payload_quotations.get(rid)
        if expected_q is None:
            errors.append(f"{rid} quotation not found in payload")
        elif json_q != expected_q:
            errors.append(
                f"{rid} quotation drift: json {repr(json_q[:60])} vs payload {repr(expected_q[:60])}"  # noqa: E501
            )

    # Source resolution
    resolvable: set[str] = set()
    for s in source_map.get("sources", []):
        sid = s.get("id")
        if sid:
            resolvable.add(sid)
    for s in source_map.get("extended_index", []):
        sid = s.get("id")
        if sid:
            resolvable.add(sid)
    for r in reqs:
        for sid in r.get("source_basis", []):
            base_sid = sid.split()[0] if " " in sid else sid
            if sid.startswith("S-035"):
                base_sid = "S-035"
            if base_sid not in resolvable:
                errors.append(f"{r.get('id')} source {sid} not resolvable in source_map")
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
        # S-035 must narrowly supersede S-012 only, not S-011
        note_lower = (s035.get("note") or "").lower()
        if (
            "s-012" not in note_lower
            and "s012" not in note_lower
            and "overlapping" not in note_lower
        ):
            errors.append("S-035 note must declare narrow supersession of S-012 overlapping body")
        if "s-011" in note_lower and "s-012" not in note_lower:
            errors.append("S-035 must not supersede S-011; only S-012 overlapping body")

    # Exact S-001..S-034 register fidelity
    # SHA 7ce9b43250d8b72e3c1aa9e0bbbc369b251bf7b7aedcae39ea8ed8cdda860d24
    # Derived independently from /Users/akashx/TrafficTwinAudit/source_index.md
    expected_classes: dict[str, str] = {  # noqa: N806
        "S-001": "A",
        "S-002": "A",
        "S-003": "A",
        "S-004": "A",
        "S-005": "A",
        "S-006": "B",
        "S-007": "B",
        "S-008": "C",
        "S-009": "C",
        "S-010": "C",
        "S-011": "C",
        "S-012": "C",
        "S-013": "C",
        "S-014": "C",
        "S-015": "D",
        "S-016": "D",
        "S-017": "D",
        "S-018": "D",
        "S-019": "D",
        "S-020": "D",
        "S-021": "D",
        "S-022": "D",
        "S-023": "D",
        "S-024": "D",
        "S-025": "D",
        "S-026": "D",
        "S-027": "D",
        "S-028": "D",
        "S-029": "E",
        "S-030": "E",
        "S-031": "E",
        "S-032": "E",
        "S-033": "E",
        "S-034": "E",
    }
    # Minimal identity anchors to prevent swapping or misbinding; derived from register titles
    expected_identity_substr: dict[str, str] = {  # noqa: N806
        "S-001": "Project 237",
        "S-002": "COMP60060",
        "S-003": "Rubric",
        "S-004": "Handbook",
        "S-005": "National Highways",
        "S-006": "TfGM",
        "S-007": "Q&A",
        "S-008": "Meeting 1",
        "S-009": "Meeting 2",
        "S-010": "Meeting 3",
        "S-011": "Meeting 4",
        "S-012": "Sandra email",
        "S-013": "Randy email",
        "S-014": "producer data/publication permission",
        "S-015": "Randy Meeting 1",
        "S-016": "Randy Meeting 2",
        "S-017": "TfGM data-access request",
        "S-018": "NTIS",
        "S-019": "disruption",
        "S-020": "v0.4",
        "S-021": "30 July",
        "S-022": "Data Platform",
        "S-023": "Questions for Sandra",
        "S-024": "Week 4",
        "S-025": "Product Design V2",
        "S-026": "PR #11",
        "S-027": "Dissertation skeleton",
        "S-028": "requirement matrix",
        "S-029": "OffloadLens v0.1",
        "S-030": "OffloadLens v0.2",
        "S-031": "v0.5",
        "S-032": "v0.6",
        "S-033": "v0.7",
        "S-034": "code-permission",
    }
    # Build combined class map from both sources and extended_index
    combined_class: dict[str, str] = {}
    combined_entry: dict[str, dict[str, object]] = {}
    for s in source_map.get("sources", []):
        sid = s.get("id")
        if sid:
            combined_class[sid] = s.get("class") or ""
            combined_entry[sid] = s
    for s in source_map.get("extended_index", []):
        sid = s.get("id")
        if sid and sid not in combined_class:
            combined_class[sid] = s.get("class") or ""
            combined_entry[sid] = s
        elif sid:
            # If duplicated, keep sources entry but validate class consistency
            if s.get("class") != combined_class.get(sid):
                errors.append(f"{sid} class inconsistent between sources and extended_index")

    # Total counts must be A5/B2/C7/D14/E6
    from collections import Counter as _Counter

    actual_counts = _Counter(combined_class.get(k, "") for k in expected_classes)
    if actual_counts.get("A", 0) != 5:
        errors.append(f"register count A !=5 got {actual_counts.get('A', 0)}")
    if actual_counts.get("B", 0) != 2:
        errors.append(f"register count B !=2 got {actual_counts.get('B', 0)}")
    if actual_counts.get("C", 0) != 7:
        errors.append(f"register count C !=7 got {actual_counts.get('C', 0)}")
    if actual_counts.get("D", 0) != 14:
        errors.append(f"register count D !=14 got {actual_counts.get('D', 0)}")
    if actual_counts.get("E", 0) != 6:
        errors.append(f"register count E !=6 got {actual_counts.get('E', 0)}")

    for sid, exp_class in expected_classes.items():
        actual = combined_class.get(sid)
        if actual is None:
            errors.append(f"register missing {sid}")
        elif actual != exp_class:
            errors.append(
                f"{sid} class mismatch: got {actual} expected {exp_class} (SHA-verified register)"
            )

    # Identity fidelity checks for entries that have description/original_path
    for sid, substr in expected_identity_substr.items():
        entry = combined_entry.get(sid)
        if entry is None:
            continue
        # For sources we have rich fields; extended_index has class only
        desc = entry.get("description") or ""
        orig = entry.get("original_path") or ""
        combined_text = f"{desc} {orig}".lower()
        # extended_index lacking desc -> skip identity, class verified
        if not desc and not orig:  # noqa: E501
            continue
        if substr.lower() not in combined_text:
            # Special handling: S-002 must not be handbook excerpt
            if sid == "S-002" and "comp60060" not in combined_text:
                errors.append(
                    f"{sid} identity mismatch: expected COMP60060 project guidelines, got {desc!r} / {orig!r}"  # noqa: E501
                )
            elif sid != "S-002":
                errors.append(
                    f"{sid} identity mismatch: expected substring {substr!r} not in description/original_path"  # noqa: E501
                )

    # S-002 must not share S-004's staged_path and must point to COMP60060 file, not handbook
    s002 = source_by_id.get("S-002")
    if s002 is not None:
        s002_orig = s002.get("original_path") or ""
        s002_staged = s002.get("staged_path")
        s004_staged = source_by_id.get("S-004", {}).get("staged_path")
        if "COMP60060" not in s002_orig:
            errors.append(f"S-002 original_path must contain COMP60060, got {s002_orig!r}")
        if "Handbook - Appendices" in s002_orig and "COMP60060" not in s002_orig:
            errors.append("S-002 must not be bound to handbook PDF; must be COMP60060 guidelines")
        if s002_staged is not None and s002_staged == s004_staged:
            errors.append("S-002 staged_path must not reuse S-004 handbook staged_path")
        desc002 = (s002.get("description") or "").lower()
        if "programme handbook excerpt" in desc002:
            errors.append("S-002 description must not claim programme handbook excerpt")

    # S-011/S-012 swap detection: S-011 must be Meeting 4, S-012 must be Sandra email
    s011 = source_by_id.get("S-011")
    s012 = source_by_id.get("S-012")
    if s011 is not None:
        d011 = ((s011.get("description") or "") + " " + (s011.get("original_path") or "")).lower()
        if "meeting 4" not in d011:
            errors.append(
                f"S-011 must be Supervisor Meeting 4 notes, got {s011.get('description')!r}"
            )
        if "sandra" in d011 and "email" in d011 and "meeting" not in d011:
            errors.append("S-011 appears swapped with S-012: S-011 should not be Sandra email")
        # S-011 must NOT carry S-035 supersession note
        note011 = (s011.get("note") or "").lower()
        if "s-035" in note011 and "supersede" in note011:
            errors.append("S-035 narrow supersession must attach only to S-012, not S-011")
    if s012 is not None:
        d012 = ((s012.get("description") or "") + " " + (s012.get("original_path") or "")).lower()
        if "sandra" not in d012 or "email" not in d012:
            errors.append(
                f"S-012 must be relayed Sandra 4 August email, got {s012.get('description')!r}"
            )
        if "meeting 4" in d012 and "sandra" not in d012:
            errors.append("S-012 appears swapped with S-011: S-012 should not be Meeting 4 notes")
        note012 = (s012.get("note") or "").lower()
        if "s-035" not in note012 or "supersede" not in note012:
            errors.append(
                "S-012 must carry note that S-035 narrowly supersedes overlapping body content only"
            )

    # S-017/S-018 class D and descriptions must be outgoing requests, not provider confirmations
    for sid in ("S-017", "S-018"):
        ent = source_by_id.get(sid)
        if ent is not None:
            if ent.get("class") != "D":
                errors.append(f"{sid} must be Class D (outgoing request), got {ent.get('class')!r}")
            d = ((ent.get("description") or "") + " " + (ent.get("note") or "")).lower()
            if "provider" in d and "confirmation" in d and "outgoing" not in d:
                errors.append(
                    f"{sid} description must indicate outgoing student request, not provider confirmation"  # noqa: E501
                )
            # Must not be B/C evidence for MUST
            if ent.get("class") in ("B", "C", "B/C"):
                errors.append(
                    f"{sid} cannot be B/C; it is D and cannot support MUST as B/C evidence"  # noqa: E501
                )
            # Check specific identity
            if sid == "S-017" and "tfgm" not in d:
                errors.append(
                    f"S-017 description must reference TfGM request, got {ent.get('description')!r}"
                )
            if sid == "S-018" and "ntis" not in d and "national highways" not in d:
                errors.append(
                    f"S-018 description must reference National Highways NTIS request, got {ent.get('description')!r}"  # noqa: E501
                )
            standing = ent.get("standing")
            if standing == "PROVIDER_CONDITIONS":  # noqa: SIM102
                errors.append(  # noqa: E501
                    f"{sid} standing must not be PROVIDER_CONDITIONS; it is an outgoing proposal"
                )

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
                if r.get("gap_id"):
                    errors.append(f"{r.get('id')} VERIFIED_MET must not have gap_id")
        if st == "NOT_APPLICABLE":
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
    check_field = must_arith.get("check", "")
    if (
        "3+7+0=11" in check_field
        and "never" not in check_field
        and "prohibited" not in check_field.lower()
    ):
        errors.append("prohibited 3+7+0 arithmetic asserted as valid")

    if status.get("baseline_payload_sha256") != EXPECTED_PAYLOAD_SHA:
        errors.append("status baseline_payload_sha256 drift")

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
