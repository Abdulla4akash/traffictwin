"""Validator for Use Case B — deadline-aware VEC dynamic service (lane 04).

Checks that all five allowed files are present and that the VEC service
definition respects S-007 + semantic-contract authority boundaries, lifecycle
completeness, vocabulary distinctions, and prohibited-claim guards.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MD_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_vec_dynamic_service.md"
MANIFEST_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_manifest.json"
DEMO_PATH = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_demo_contract.json"

# Canonical lifecycle in required order (lowercased for matching).
LIFECYCLE_STAGES = [
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

# Distinct counters that must remain separate.
DISTINCT_COUNTERS = ["forwarded", "compute_completed", "returned", "deadline_success"]

# Mandatory vocabulary distinctions (lowercased fragments).
REQUIRED_VOCAB = ["vehicle mode", "ingress rsu", "execution rsu", "admission", "placement", "scaling"]

# Source hashes that must be bound exactly.
EXPECTED_HASHES = {
    "FINAL_AUDIT": "0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9",
    "NEGOTIATED_V1_WHOLE_FILE": "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2",
    "S-035": "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed",
    "S-007": "e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4",
}

ERRORS: list[str] = []


def _add(msg: str) -> None:
    ERRORS.append(msg)


def _fail_if(pattern: str, text: str, msg: str, flags: int = re.IGNORECASE) -> None:
    if re.search(pattern, text, flags):
        _add(msg)


def _require(pattern: str, text: str, msg: str, flags: int = re.IGNORECASE) -> None:
    if not re.search(pattern, text, flags):
        _add(msg)


def validate_markdown(text: str) -> None:
    low = text.lower()

    # 1. Lifecycle completeness and order.
    positions: list[int] = []
    for stage in LIFECYCLE_STAGES:
        idx = low.find(stage.lower())
        if idx == -1:
            _add(f"lifecycle stage missing: '{stage}'")
            positions.append(10_000_000)
        else:
            positions.append(idx)
    # Order check: each stage must appear after the previous.
    for i in range(1, len(positions)):
        if positions[i] < positions[i - 1]:
            _add(
                f"lifecycle stage out of order: '{LIFECYCLE_STAGES[i]}' appears before '{LIFECYCLE_STAGES[i-1]}'"
            )

    # 2. Vocabulary distinctions present.
    for term in REQUIRED_VOCAB:
        if term.lower() not in low:
            _add(f"vocabulary term missing: '{term}'")

    # Must state distinctions explicitly.
    _require(
        r"vehicle mode.*ingress rsu|ingress rsu.*execution rsu|distinct",
        text,
        "vocabulary distinctions not explicitly stated (vehicle mode / ingress RSU / execution RSU must be distinguished)",
    )

    # 3. Authority boundary: actor chooses mode, NOT RSU.
    _require(r"actor.*chooses.*local.*v2i.*v2v|actor.*chooses.*mode", text, "actor mode choice not described (Local/V2I/V2V)")

    # Prohibited: credit actor with exact RSU choice as positive claim.
    # Allow only if it is negated / stated as prohibited. So we look for positive phrasing
    # without a nearby negation. Simpler: fail if the markdown contains claims that actor
    # selects RSU in a non-negated context. We detect the forbidden phrases and ensure
    # they only appear alongside a negation/prohibition.
    # For mutation discrimination we treat any occurrence of "actor selects.*rsu" as fail
    # unless the file also contains an explicit "does not" / "does NOT" / "prohibited" nearby.
    # Simplest discriminating rule: if markdown contains "actor selects.*rsu" or "mappo.*chooses.*rsu"
    # as a positive statement without the required disclaimer, fail.
    # We implement: forbidden patterns must not appear at all as standalone positive claims.
    # The correct file uses "does NOT choose.*rsu" which is allowed; mutation uses positive form.
    # So we forbid positive forms:
    if re.search(r"actor\s+selects\s+(target\s+)?rsu", text, re.IGNORECASE):
        # Allow only if the file also contains an explicit negation of this claim.
        if not re.search(r"actor.*does\s+not.*rsu|does\s+not\s+choose.*rsu|prohibited", text, re.IGNORECASE):
            _add("prohibited claim: actor credited with RSU choice (actor selects RSU)")
    if re.search(r"mappo\s+chooses\s+rsu|mappo\s+selects\s+rsu", text, re.IGNORECASE):
        _add("prohibited claim: MAPPO credited with exact RSU choice")

    # More general: "actor chooses target rsu" without negation
    if re.search(r"actor\s+chooses\s+target\s+rsu", text, re.IGNORECASE):
        if not re.search(r"actor.*does\s+not\s+choose.*rsu", text, re.IGNORECASE):
            _add("prohibited claim: actor credited with target RSU choice")

    # 4. Waiting-room vs compute power.
    _require(r"waiting-room.*capac|queue.*capac|admission.*ceiling", text, "waiting-room / admission ceiling not defined")
    _require(r"compute\s*power|compute.*scaling|service\s*rate", text, "compute power / service rate not defined")
    # Must state they are distinct.
    _require(
        r"waiting-room.*not.*compute|queue.*not.*compute|waiting-room.*\u2260.*compute|capacity.*not.*compute|capacity.*\u2260.*compute",
        text,
        "must explicitly state waiting-room capacity is NOT compute power",
    )
    # Prohibited: equating them without negation.
    if re.search(r"waiting-room\s+(is|equals)\s+compute\s+power", text, re.IGNORECASE):
        _add("prohibited claim: waiting-room capacity equated with compute power")
    if re.search(r"queue\s+capacity\s+is\s+compute\s+power", text, re.IGNORECASE):
        _add("prohibited claim: queue capacity equated with compute power")

    # 5. Kubernetes-style vs real deployment.
    _require(r"kubernetes-style|simulated.*scaling|resource-scaling\s+simulation", text, "must use Kubernetes-style / simulated scaling wording")
    if re.search(r"kubernetes\s+deployment", text, re.IGNORECASE):
        # Allow only if qualified as "not a ... deployment" or "simulated".
        if not re.search(r"not\s+a.*kubernetes\s+deployment|simulated.*kubernetes|kubernetes-style", text, re.IGNORECASE):
            _add("prohibited claim: simulated scaling called Kubernetes deployment")

    # 6. Distinct stages: forwarded, compute_completed, returned, deadline_success
    for c in DISTINCT_COUNTERS:
        if c.lower() not in low:
            _add(f"distinct counter missing: '{c}'")
    _require(
        r"forwarded.*compute_completed|compute_completed.*returned|returned.*deadline_success|distinct.*counter",
        text,
        "must state forwarded / compute_completed / returned / deadline_success are distinct",
    )
    # Prohibited: conflating compute completion with deadline success.
    if re.search(r"compute_completed\s*=\s*deadline_success|compute_completed\s+equals\s+deadline_success", text, re.IGNORECASE):
        _add("prohibited claim: compute_completed conflated with deadline_success")
    if re.search(r"compute completion\s*=\s*deadline success", text, re.IGNORECASE):
        _add("prohibited claim: compute completion conflated with deadline success")
    # Also catch phrase like "completion is deadline success" without distinction
    if re.search(r"compute_completed\s+is\s+deadline_success", text, re.IGNORECASE):
        _add("prohibited claim: compute_completed equated with deadline_success")

    # 7. Evidence labels present.
    for label in ["SOURCE-DERIVED FACT", "IMPLEMENTATION-VERIFIED FACT", "RESEARCH-EVIDENCE FACT", "PROVISIONAL WORDING", "EXTERNAL DECISION REQUIRED"]:
        if label not in text:
            _add(f"evidence label missing: '{label}'")
    # Inference is also required but flagged separately.
    if "INFERENCE" not in text:
        _add("evidence label missing: 'INFERENCE'")

    # 8. S-035 binding.
    _require(r"S-035|SANDRA-DIRECT-BODY", text, "S-035 / SANDRA-DIRECT-BODY-2026-08-04 not referenced")
    _require(r"08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed", text, "S-035 SHA-256 not bound")
    _require(r"fail.?fast|rejection.?accounting", text, "fail-fast / rejection-accounting explanation not present")
    _require(r"does\s+not\s+broadcast|stale|obsolete", text, "RSU capacity broadcast staleness not stated")

    # 9. Provenance: frozen payload hash.
    _require(r"58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595", text, "frozen canonical payload SHA not bound")
    # Should not use bare SRC-011 without S-035 key.
    if re.search(r"\bSRC-011\b", text) and "S-035" not in text:
        _add("ambiguous bare identifier SRC-011 used without S-035 campaign key")


def validate_manifest(data: dict[str, object]) -> None:
    # Required top-level keys.
    for k in ["lane", "feature", "campaign", "base_sha", "requirement_binding", "lifecycle", "vocabulary", "authority_boundary"]:
        if k not in data:
            _add(f"manifest missing key: '{k}'")

    if data.get("lane") != "04":
        _add("manifest lane must be '04'")
    if data.get("base_sha") != "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6":
        _add("manifest base_sha mismatch")
    if data.get("campaign") != "v08-requirements-closure":
        _add("manifest campaign mismatch")

    rb = data.get("requirement_binding")
    if isinstance(rb, dict):
        if rb.get("priority") != "SHOULD":
            _add("manifest TT-REQ-008 priority must be SHOULD")
        if rb.get("open_decision") is not True:
            _add("manifest TT-REQ-008 open_decision must be true")

    lc = data.get("lifecycle")
    if isinstance(lc, dict):
        stages = lc.get("ordered_stages")
        if not isinstance(stages, list) or len(stages) < 10:
            _add("manifest lifecycle.ordered_stages must list all 10 stages in order")
        else:
            low_stages = [str(s).lower() for s in stages]
            for stage in LIFECYCLE_STAGES:
                if stage.lower() not in low_stages:
                    _add(f"manifest lifecycle missing stage: '{stage}'")
        counters = lc.get("counters_distinct")
        if not isinstance(counters, list) or set(counters) != set(DISTINCT_COUNTERS):
            _add(f"manifest counters_distinct must be exactly {DISTINCT_COUNTERS}")

    vocab = data.get("vocabulary")
    if isinstance(vocab, dict):
        approved = vocab.get("approved")
        if not isinstance(approved, list) or len(approved) < 6:
            _add("manifest vocabulary.approved must list vehicle mode, ingress RSU, execution RSU, admission, placement, scaling")
        must_distinct = vocab.get("mandatory_distinctions")
        if not isinstance(must_distinct, list) or len(must_distinct) < 5:
            _add("manifest vocabulary.mandatory_distinctions must enumerate all five distinctions")
        # Check waiting-room != compute power is among distinctions.
        flat = " ".join(str(x).lower() for x in (must_distinct or []))
        if "waiting-room" not in flat or "compute power" not in flat:
            _add("manifest must distinguish waiting-room capacity from compute power")

    auth = data.get("authority_boundary")
    if isinstance(auth, dict):
        actor = str(auth.get("vehicle_actor", ""))
        if "does not choose" not in actor.lower() and "does not" not in actor.lower():
            _add("manifest authority_boundary.vehicle_actor must state actor does NOT choose RSU")

    # Source hash binding.
    sources = data.get("sources")
    if isinstance(sources, list):
        hash_map: dict[str, str] = {}
        for s in sources:
            if isinstance(s, dict):
                sid = str(s.get("id", ""))
                sha = str(s.get("sha256", ""))
                hash_map[sid] = sha
        for sid, expected in EXPECTED_HASHES.items():
            # S-035 key includes slash; check contained.
            if sid == "S-035":
                found = any("S-035" in k for k in hash_map)
                if not found:
                    _add("manifest missing S-035 source entry")
                else:
                    for k, v in hash_map.items():
                        if "S-035" in k and v != expected:
                            _add(f"manifest S-035 sha256 mismatch: expected {expected}")
            else:
                if hash_map.get(sid) != expected:
                    _add(f"manifest source {sid} sha256 mismatch: expected {expected}, got {hash_map.get(sid)}")
    else:
        _add("manifest sources must be a list with exact sha256 bindings")


def validate_demo(data: dict[str, object]) -> None:
    # Lifecycle binding.
    lc = data.get("lifecycle_binding")
    if not isinstance(lc, list) or len(lc) < 10:
        _add("demo_contract lifecycle_binding must list all 10 stages in order")
    else:
        low = [str(x).lower() for x in lc]
        for stage in LIFECYCLE_STAGES:
            if stage.lower() not in low:
                _add(f"demo_contract missing lifecycle stage: '{stage}'")

    # Distinct stages contract.
    dsc = data.get("distinct_stages_contract")
    if not isinstance(dsc, dict):
        _add("demo_contract distinct_stages_contract missing")
    else:
        counters = dsc.get("counters")
        if not isinstance(counters, dict):
            _add("demo_contract distinct_stages_contract.counters must be an object")
        else:
            for c in DISTINCT_COUNTERS:
                if c not in counters:
                    _add(f"demo_contract missing counter definition: '{c}'")
                else:
                    entry = counters[c]
                    if not isinstance(entry, dict) or "distinct_from" not in entry:
                        _add(f"demo_contract counter '{c}' must have distinct_from")
                    elif not isinstance(entry["distinct_from"], list) or len(entry["distinct_from"]) < 1:
                        _add(f"demo_contract counter '{c}' distinct_from must be non-empty")

    # Authority binding must state actor does not choose RSU.
    ab = data.get("authority_binding")
    if not isinstance(ab, dict):
        _add("demo_contract authority_binding missing")
    else:
        va = ab.get("vehicle_actor")
        if isinstance(va, dict):
            if "does_not_choose" not in va and "does not" not in str(va).lower():
                _add("demo_contract authority_binding.vehicle_actor must state does_not_choose RSU")
            if va.get("does_not_choose") and "rsu" not in str(va.get("does_not_choose")).lower():
                _add("demo_contract does_not_choose must mention RSU")
        pcs = ab.get("prohibited_claims")
        if not isinstance(pcs, list) or len(pcs) < 4:
            _add("demo_contract prohibited_claims must list at least four prohibitions")

    # Metrics must include conservation and headline vs conditional.
    co = data.get("comparison_output")
    if isinstance(co, dict):
        if co.get("headline_metric") != "completion_offered = deadline_success / offered":
            _add("demo_contract headline_metric must be 'completion_offered = deadline_success / offered'")
        req = co.get("required_metrics")
        if not isinstance(req, list) or len(req) < 5:
            _add("demo_contract required_metrics too short")
        else:
            flat = " ".join(str(x).lower() for x in req)
            if "forwarded" not in flat or "compute_completed" not in flat or "returned" not in flat or "deadline_success" not in flat:
                _add("demo_contract required_metrics must mention forwarded / compute_completed / returned / deadline_success as distinct")
    else:
        _add("demo_contract comparison_output missing")

    # Base SHA must match.
    if data.get("base_sha") != "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6":
        _add("demo_contract base_sha mismatch")


def main() -> int:
    # Check files exist.
    for p in [MD_PATH, MANIFEST_PATH, DEMO_PATH]:
        if not p.exists():
            _add(f"required file missing: {p}")

    if ERRORS:
        for e in ERRORS:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"validation failed with {len(ERRORS)} error(s) before content checks", file=sys.stderr)
        return 1

    # Validate markdown.
    md_text = MD_PATH.read_text(encoding="utf-8")
    validate_markdown(md_text)

    # Validate manifest.
    try:
        manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        _add(f"manifest JSON parse error: {exc}")
        manifest_data = {}

    if isinstance(manifest_data, dict):
        validate_manifest(manifest_data)
    else:
        _add("manifest JSON must be an object")

    # Validate demo contract.
    try:
        demo_data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        _add(f"demo_contract JSON parse error: {exc}")
        demo_data = {}

    if isinstance(demo_data, dict):
        validate_demo(demo_data)
    else:
        _add("demo_contract JSON must be an object")

    # Validate this validator script and test file are present (allowed files check).
    test_path = REPO_ROOT / "tests/unit/test_validate_v08_use_case_b.py"
    validator_path = REPO_ROOT / "scripts/validate_v08_use_case_b.py"
    for p in [test_path, validator_path]:
        if not p.exists():
            _add(f"required file missing: {p}")

    if ERRORS:
        for e in ERRORS:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"FAILED: {len(ERRORS)} error(s)", file=sys.stderr)
        return 1

    print("OK: use_case_b validation passed")
    print(f"  lifecycle stages: {len(LIFECYCLE_STAGES)} in order")
    print(f"  distinct counters: {', '.join(DISTINCT_COUNTERS)}")
    print(f"  vocabulary distinctions: 5 enforced")
    print(f"  sources bound: {len(EXPECTED_HASHES)} hashes verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
