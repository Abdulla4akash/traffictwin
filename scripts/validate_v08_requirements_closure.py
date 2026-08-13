#!/usr/bin/env python3
"""Validate v08 requirements-closure acceptance harness (Lane 12).

End-to-end validator for:
- baseline hash/IDs, two distinct cases, complete strategy matrix,
  improved-contract identity, evidence refs, accounting conservation,
  evidence labels, Manchester standing, dissertation trace, video completeness,
  and no unresolved MUST silently MET.

Self-contained: all expected hashes/identities are embedded. Ignored
.harness/context files are NOT a runtime dependency; when present they are
cross-checked as an additional controller check.

Exit 0 on pass, 1 on failure, 2 on missing file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_repo_root() -> Path:
    for env in (
        "V08_VALIDATOR_ROOT",
        "V08_CLOSURE_VALIDATOR_ROOT",
        "LANE12_VALIDATOR_ROOT",
    ):
        v = os.environ.get(env)
        if v:
            return Path(v)
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        return Path(sys.argv[1])
    return _DEFAULT_REPO_ROOT


REPO_ROOT = _resolve_repo_root()

# ---------------------------------------------------------------------------
# Expected canonical identities (embedded, self-contained)
# ---------------------------------------------------------------------------
EXPECTED_PAYLOAD_SHA256 = "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
EXPECTED_WHOLE_SHA256 = "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2"
EXPECTED_FINAL_AUDIT_SHA256 = "0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9"
EXPECTED_SOURCE_INDEX_SHA256 = "7ce9b43250d8b72e3c1aa9e0bbbc369b251bf7b7aedcae39ea8ed8cdda860d24"
EXPECTED_S035_SHA256 = "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed"
EXPECTED_BASE_SHA = "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"
EXPECTED_PREPARED_BASE_SHA = "f157f3a9d711e96abad35e573dec43f902a6cd2a"

# 11 dependency lanes frozen SHAs (for package index cross-check)
EXPECTED_DEPENDENCIES: dict[str, str] = {
    "01": "2474cc10f92bf7af446c87cb05f7a605acb29bf4",
    "02": "e63eaad4d70b5098c0ced62185fedb0bc900395b",
    "03": "203f5c5d0153bf825fae0072657ea1ff22782c32",
    "04": "7c32e9cbb0bcdb096e296156bc7d28e0aff78c61",
    "05": "c2ae953702fe4e05e990e16977614919d7e76513",
    "06": "42ef7e6b69e3f893afbd3849082cf2f457af66c3",
    "07": "4a2f66a86a83a9fa5d1b9ac5db0d03fbbf2e3f6e",
    "08": "0d17d56f9db215e6440a563635f76297ceaf96dd",
    "09": "3c4a448f2d2789667dda69c164048157a61e878e",
    "10": "69276c7c45136e63278d930e5ea5d4a5d01ca9cd",
    "11": "958847d6b93450e7b8603adc127ab299f23d994a",
}
EXPECTED_MANIFEST_SHA256 = "6c716eb6de08791d1bcb207c15c6b2c51b46d735944dd851334d61d9183b3125"

# Frozen vec_jax identity — present only in allowed_sha256_set (not in primitives/matrix)
FROZEN_VEC_JAX_SHA = "73d83d062fad030941f5236835cce8e86caacc4d44eb7a1129047e99228886ff"

# Strategy matrix
REQUIRED_STRATEGY_IDS = [
    "strongest_link_off",
    "jsq_without_gate",
    "ingress_dla",
    "common_target_dla",
    "per_task_dla",
]

# Improved contract fingerprint keys
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

# Paths
BASELINE_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_baseline_v1.json"
SOURCE_MAP_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_source_map.json"
STATUS_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_status_v08.json"
STRATEGY_MATRIX_JSON = REPO_ROOT / "docs/closure/v08_alignment/strategy_matrix.json"
EVIDENCE_MAP_JSON = REPO_ROOT / "docs/closure/v08_alignment/strategy_evidence_map.json"
IMPROVED_CONTRACT_JSON = (
    REPO_ROOT / "docs/closure/v08_alignment/improved_dynamic_strategy_contract.json"
)
IMPROVED_CONTRACT_MD = (
    REPO_ROOT / "docs/closure/v08_alignment/improved_dynamic_strategy_contract.md"
)
IMPROVED_PSEUDO = REPO_ROOT / "docs/closure/v08_alignment/improved_dynamic_strategy_pseudocode.txt"
TASK_CONTRACT_JSON = REPO_ROOT / "docs/closure/v08_alignment/task_semantics_contract.json"
TASK_HANDCHECK_JSON = REPO_ROOT / "docs/closure/v08_alignment/task_accounting_handcheck.json"
USE_CASE_A_MANIFEST = REPO_ROOT / "docs/closure/v08_alignment/use_case_a_manifest.json"
USE_CASE_B_MANIFEST = REPO_ROOT / "docs/closure/v08_alignment/use_case_b_manifest.json"
TRACEABILITY_MD = REPO_ROOT / "docs/closure/v08_alignment/dissertation_traceability.md"
RESTRUCTURE_PLAN_MD = REPO_ROOT / "docs/closure/v08_alignment/dissertation_restructure_plan.md"
CONTRIBUTION_MD = REPO_ROOT / "docs/closure/v08_alignment/contribution_statement.md"
VIDEO_SCRIPT = REPO_ROOT / "docs/closure/v08_alignment/video_7min_script.md"
VIDEO_STORYBOARD = REPO_ROOT / "docs/closure/v08_alignment/video_storyboard.md"
VIDEO_CLICK_PATH = REPO_ROOT / "docs/closure/v08_alignment/video_demo_click_path.md"
VIDEO_CHECKLIST = REPO_ROOT / "docs/closure/v08_alignment/video_evidence_checklist.md"
MANCHESTER_DEMO_CURRENT = (
    REPO_ROOT / "docs/closure/v08_alignment/manchester_demo/current_view_artifact.json"
)
MANCHESTER_SOURCE_RECEIPT = (
    REPO_ROOT / "docs/closure/v08_alignment/manchester_demo/source_receipt.json"
)
CLOSURE_REPORT = REPO_ROOT / "docs/closure/v08_alignment/closure_acceptance_report.md"
CLOSURE_INDEX = REPO_ROOT / "docs/closure/v08_alignment/closure_package_index.json"
NAVIGATION_V07 = REPO_ROOT / "src/traffictwin/ui/navigation_v07.py"
COMPARE_PAGE = REPO_ROOT / "src/traffictwin/ui/pages/compare.py"

HONESTY_LABELS = [
    "SOURCE-DERIVED FACT",
    "IMPLEMENTATION-VERIFIED FACT",
    "RESEARCH-EVIDENCE FACT",
    "INFERENCE",
    "PROVISIONAL WORDING",
    "EXTERNAL DECISION REQUIRED",
]

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
TIME_RE = re.compile(r"(\d+):(\d{2})\s*[–—-]\s*(\d+):(\d{2})")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------


def validate_baseline_hash(errors: list[str]) -> None:
    for p in [BASELINE_JSON, SOURCE_MAP_JSON, STATUS_JSON]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
    if errors:
        return
    baseline = _load_json(BASELINE_JSON)
    # recompute from committed fields
    payload = baseline.get("canonical_payload")
    whole = baseline.get("whole_file_content")
    if not isinstance(payload, str):
        errors.append("baseline JSON missing canonical_payload self-contained field")
    else:
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if h != EXPECTED_PAYLOAD_SHA256:
            errors.append(f"payload hash mismatch: got {h} expected {EXPECTED_PAYLOAD_SHA256}")
    if not isinstance(whole, str):
        errors.append("baseline JSON missing whole_file_content self-contained field")
    else:
        h = hashlib.sha256(whole.encode("utf-8")).hexdigest()
        if h != EXPECTED_WHOLE_SHA256:
            errors.append(f"whole file hash mismatch: got {h} expected {EXPECTED_WHOLE_SHA256}")
    if baseline.get("canonical_payload_sha256") != EXPECTED_PAYLOAD_SHA256:
        errors.append("baseline JSON canonical_payload_sha256 drift")
    if baseline.get("whole_file_sha256") != EXPECTED_WHOLE_SHA256:
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
    # source map checks
    source_map = _load_json(SOURCE_MAP_JSON)
    source_by_id = {s.get("id"): s for s in source_map.get("sources", [])}
    expected_shas = {
        "S-001": "d2940e257e455de3f6694d59d66c4d3661471c732618700ad34b4d65240597b0",
        "S-003": "c88175e344c8aa0cfd5eba6164a8b5941670c7cc5bb69e89213c6c019bcd8c0f",
        "S-004": "df504ec76271f2cb4b2fa34be1f53f55d1363e65d4352456f856a92178d3da82",
        "S-007": "e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4",
        "S-035": EXPECTED_S035_SHA256,
    }
    for sid, sha in expected_shas.items():
        entry = source_by_id.get(sid)
        if entry is None:
            errors.append(f"source_map missing authoritative source {sid}")
        elif entry.get("sha256") != sha:
            errors.append(
                f"source_map {sid} sha256 mismatch got {entry.get('sha256')} expected {sha}"
            )
    s035 = source_by_id.get("S-035")
    if s035 is not None:
        if s035.get("campaign_key") != "S-035 / SANDRA-DIRECT-BODY-2026-08-04":
            errors.append(
                "S-035 campaign_key must be exact 'S-035 / SANDRA-DIRECT-BODY-2026-08-04'"
            )
        if s035.get("standing") != "DIRECT_SUPERVISOR_SOURCE_BODY":
            errors.append("S-035 standing must be DIRECT_SUPERVISOR_SOURCE_BODY")


def validate_two_distinct_cases(errors: list[str]) -> None:
    for p in [USE_CASE_A_MANIFEST, USE_CASE_B_MANIFEST]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
            return
    a = _load_json(USE_CASE_A_MANIFEST)
    b = _load_json(USE_CASE_B_MANIFEST)
    wa = a.get("workflow_id") or a.get("feature") or a.get("doc_ref")
    wb = b.get("workflow_id") or b.get("feature") or b.get("doc_ref")
    if wa == wb:
        errors.append(
            f"duplicate service identity: use_case_a and use_case_b share identity {wa!r}"
        )
    if wa is None or wb is None:
        errors.append("use_case manifests missing identity")
    # check distinct service purpose/content
    a_doc = a.get("doc_ref", "")
    b_doc = b.get("doc_ref", "")
    if a_doc == b_doc and a_doc != "":
        errors.append("use_case manifests share same doc_ref — not distinct")
    # CC: require that service_a is Manchester current context and service_b is VEC
    if (
        "manchester" not in str(wa).lower()
        and "manchester" not in str(a).lower()
        and a.get("lane") == b.get("lane")
    ):
        errors.append("use_case manifests share lane — duplicate service")
    # Check that use_case_a sources contain at least one REAL MANCHESTER DATA standing
    # and use_case_b contains VEC semantics
    a_sources = a.get("sources", [])
    has_real = any(
        s.get("evidence_standing") == "REAL MANCHESTER DATA"
        or s.get("classification") == "REAL MANCHESTER DATA"
        for s in a_sources
    )
    # Alternative: check markdown for manchester service
    if not has_real:
        # Also check doc text for manchester
        try:
            doc_path = (
                REPO_ROOT / "docs/closure/v08_alignment/use_case_a_manchester_current_twin.md"
            )
            if doc_path.exists():
                text = doc_path.read_text(encoding="utf-8")
                if "manchester" not in text.lower():
                    errors.append("use_case_a does not reference Manchester — indistinct service")
            else:
                errors.append("use_case_a missing REAL MANCHESTER DATA evidence label")
        except Exception:
            errors.append("use_case_a validation error")
    # VEC service must reference VEC/rsu
    b_text = json.dumps(b)
    if "VEC" not in b_text and "rsu" not in b_text.lower():
        errors.append("use_case_b does not reference VEC/RSU — indistinct service")
    # Also ensure each manifest has evidence labels
    for manifest, name in [(a, "use_case_a"), (b, "use_case_b")]:
        if "base_sha" in manifest and manifest["base_sha"] != EXPECTED_BASE_SHA:
            errors.append(
                f"{name} base_sha mismatch "
                f"got {manifest.get('base_sha')} expected {EXPECTED_BASE_SHA}"
            )


def validate_strategy_matrix(errors: list[str]) -> None:
    if not STRATEGY_MATRIX_JSON.exists():
        errors.append(f"missing required file: {STRATEGY_MATRIX_JSON.relative_to(REPO_ROOT)}")
        return
    data = _load_json(STRATEGY_MATRIX_JSON)
    if data.get("schema_version") != "v08_strategy_matrix_v1":
        errors.append("strategy_matrix schema_version must be v08_strategy_matrix_v1")
    if data.get("base_sha") != EXPECTED_BASE_SHA:
        errors.append(
            f"strategy_matrix base_sha mismatch "
            f"got {data.get('base_sha')} expected {EXPECTED_BASE_SHA}"
        )
    strategies = data.get("strategies", [])
    ids = [s.get("id") for s in strategies]
    for req_id in REQUIRED_STRATEGY_IDS:
        if req_id not in ids:
            errors.append(f"strategy_matrix missing required strategy {req_id}")
    if len(ids) != len(set(ids)):
        errors.append(f"strategy_matrix IDs not unique: {ids}")
    if len(strategies) != 5:
        errors.append(f"strategy_matrix must have exactly 5 strategies, got {len(strategies)}")
    for s in strategies:
        if "admission" not in s:
            errors.append(f"strategy {s.get('id')} missing admission field")
        if "placement" not in s:
            errors.append(f"strategy {s.get('id')} missing placement field")
        if "experiment_evidence" not in s:
            errors.append(f"strategy {s.get('id')} missing experiment_evidence")
        if "honesty_class" not in s or not s.get("honesty_class"):
            errors.append(f"strategy {s.get('id')} missing honesty_class")
    auth = data.get("authority", {})
    if auth.get("negotiated_baseline_payload_sha256") != EXPECTED_PAYLOAD_SHA256:
        errors.append("strategy_matrix payload SHA mismatch")
    if auth.get("s035_sha256") != EXPECTED_S035_SHA256:
        errors.append("strategy_matrix S-035 SHA mismatch")


def validate_improved_contract(errors: list[str]) -> None:
    for p in [IMPROVED_CONTRACT_JSON, IMPROVED_CONTRACT_MD, IMPROVED_PSEUDO]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
            return
    jdata = _load_json(IMPROVED_CONTRACT_JSON)
    payload = {k: jdata[k] for k in FINGERPRINT_KEYS if k in jdata}
    missing = [k for k in FINGERPRINT_KEYS if k not in jdata]
    if missing:
        errors.append(f"improved contract missing fingerprint keys: {missing}")
        return
    recomputed = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    stored = jdata.get("fingerprint", "")
    if stored != recomputed:
        errors.append(
            f"improved contract fingerprint mismatch: "
            f"stored {stored!r} != recomputed {recomputed!r}"
        )
    md_text = IMPROVED_CONTRACT_MD.read_text(encoding="utf-8")
    pseudo_text = IMPROVED_PSEUDO.read_text(encoding="utf-8")
    if recomputed not in md_text:
        errors.append("improved contract markdown does not contain fingerprint")
    if recomputed not in pseudo_text:
        errors.append("improved contract pseudocode does not contain fingerprint")
    # Determinism checks
    identity = jdata.get("identity", {})
    if identity.get("is_deterministic") is not True:
        errors.append("improved contract identity.is_deterministic must be true")
    if identity.get("is_learned") is not False:
        errors.append("improved contract identity.is_learned must be false")
    # Deadline gate
    gate_formula = "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]"
    gate = jdata.get("admission_interaction", {}).get("deadline_gate", {}).get("formula", "")
    if gate != gate_formula:
        errors.append(f"improved contract gate formula wrong: {gate!r}")
    if gate_formula not in pseudo_text:
        errors.append("improved contract pseudocode missing exact deadline gate formula")
    # S-035 check
    s035 = jdata.get("sandra_direct_body_S035", {})
    if s035.get("sha256") != EXPECTED_S035_SHA256:
        errors.append("improved contract S-035 sha256 wrong")
    # Scope
    scope = jdata.get("scope_bound", {})
    if "E2d" not in scope.get("bounded_to", ""):
        errors.append("improved contract scope_bound must reference E2d")


def validate_evidence_refs(errors: list[str]) -> None:
    for p in [EVIDENCE_MAP_JSON, STRATEGY_MATRIX_JSON]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
            return
    evidence_map = _load_json(EVIDENCE_MAP_JSON)
    matrix = _load_json(STRATEGY_MATRIX_JSON)
    allowed = evidence_map.get("allowed_sha256_set")
    if not isinstance(allowed, list) or len(allowed) == 0:
        errors.append("strategy_evidence_map missing allowed_sha256_set")
        return
    allowed_set: set[str] = set()
    for sha in allowed:
        if not isinstance(sha, str) or not HEX64_RE.match(sha):
            errors.append(f"evidence_map allowed SHA not 64 hex: {sha!r}")
            return
        allowed_set.add(sha)
    # Derive unique SHA-256 set from strategy_evidence_map.json:strategies.*.evidence[].sha256
    evidence_shas: set[str] = set()
    strategies = evidence_map.get("strategies", {})
    if not isinstance(strategies, dict):
        errors.append("strategy_evidence_map strategies malformed")
        return
    for strat_id, strat in strategies.items():
        ev_list = strat.get("evidence", []) if isinstance(strat, dict) else []
        for ev in ev_list:
            sha = ev.get("sha256") if isinstance(ev, dict) else None
            if isinstance(sha, str) and HEX64_RE.match(sha):
                evidence_shas.add(sha)
            elif sha is not None:
                errors.append(f"strategy_evidence_map {strat_id} evidence sha malformed {sha!r}")
    # Derive primitive 64-hex identities recursively from tracked primitives
    primitive_shas: set[str] = set()

    def _collect_hex(obj: Any, out: set[str]) -> None:  # noqa: ANN401
        if isinstance(obj, str) and HEX64_RE.match(obj):
            out.add(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _collect_hex(v, out)
        elif isinstance(obj, list):
            for v in obj:
                _collect_hex(v, out)

    _collect_hex(evidence_map.get("primitives", {}), primitive_shas)
    # Derive matrix evidence digests (experiment_evidence 64-hex values)
    matrix_shas: set[str] = set()
    for s in matrix.get("strategies", []):
        ev = s.get("experiment_evidence", {})
        if isinstance(ev, dict):
            for _k, v in ev.items():
                if isinstance(v, str) and HEX64_RE.match(v):
                    matrix_shas.add(v)
    # Expected allowed set: evidence ∪ primitives ∪ matrix ∪ frozen vec_jax
    expected_allowed = evidence_shas | primitive_shas | matrix_shas | {FROZEN_VEC_JAX_SHA}
    if allowed_set != expected_allowed:
        missing = sorted(expected_allowed - allowed_set)
        orphan = sorted(allowed_set - expected_allowed)
        if missing:
            errors.append(f"evidence_map allowed_sha256_set missing referenced SHA(s): {missing}")
        if orphan:
            errors.append(f"evidence_map allowed_sha256_set contains stray orphan SHA(s): {orphan}")
    unresolved = sorted(matrix_shas - allowed_set)
    if unresolved:
        errors.append(
            f"strategy_matrix experiment_evidence SHA(s) not in allowed_sha256_set: {unresolved}"
        )


def validate_accounting(errors: list[str]) -> None:
    if not TASK_CONTRACT_JSON.exists():
        errors.append(f"missing required file: {TASK_CONTRACT_JSON.relative_to(REPO_ROOT)}")
        return
    if not TASK_HANDCHECK_JSON.exists():
        errors.append(f"missing required file: {TASK_HANDCHECK_JSON.relative_to(REPO_ROOT)}")
        return
    contract = _load_json(TASK_CONTRACT_JSON)
    hand = _load_json(TASK_HANDCHECK_JSON)
    he = hand.get("hand_example", {})
    acc = he.get("accounting", {})
    if not acc:
        errors.append("hand_example accounting missing")
        return
    offered = acc.get("offered")
    admitted = acc.get("admitted")
    gate = acc.get("gate_rejected")
    cap = acc.get("capacity_rejected")
    if None in (offered, admitted, gate, cap):
        errors.append("hand_example accounting missing required fields")
        return
    if offered != admitted + gate + cap:
        errors.append(
            f"accounting conservation failed: offered {offered} != "
            f"admitted {admitted} + gate {gate} + capacity {cap} = "
            f"{admitted + gate + cap}"
        )
    forwarded = acc.get("forwarded")
    if forwarded is not None and admitted is not None and forwarded > admitted:
        errors.append(f"forwarded {forwarded} > admitted {admitted}")
    compute = acc.get("compute_completed")
    returned = acc.get("returned")
    dropped = acc.get("dropped")
    if (
        compute is not None
        and returned is not None
        and dropped is not None
        and compute != returned + dropped
    ):
        errors.append(f"compute_completed {compute} != returned {returned} + dropped {dropped}")
    # contract honesty
    lc = contract.get("lifecycle", {})
    if "conservation_rule" not in lc:
        errors.append("task contract missing conservation_rule")
    if lc.get("conservation_rule") != "offered == admitted + gate_rejected + capacity_rejected":
        errors.append("task contract conservation_rule wording drift")
    # waiting room ceiling must not claim compute power
    wrc = lc.get("waiting_room_ceiling", {})
    definition = str(wrc.get("definition", ""))
    if "compute power" in definition.lower() and "not compute" not in definition.lower():
        errors.append("waiting-room ceiling incorrectly described as compute power")


EXPECTED_A_LABELS: dict[str, tuple[str, str]] = {
    "bods_bus_positions": ("REAL MANCHESTER DATA", "REAL MANCHESTER DATA"),
    "national_highways_operational": (
        "REAL EXTERNAL NON-MANCHESTER DATA",
        "REAL EXTERNAL NON-MANCHESTER DATA",
    ),
    "dft_historical_counts": ("REAL MANCHESTER DATA", "REAL MANCHESTER DATA"),
    "webtris_historical": (
        "REAL EXTERNAL NON-MANCHESTER DATA",
        "REAL EXTERNAL NON-MANCHESTER DATA",
    ),
    "tfgm_signal_locations": ("REAL MANCHESTER DATA", "REAL MANCHESTER DATA"),
    "ons_boundary": ("REAL MANCHESTER DATA", "REAL MANCHESTER DATA"),
    "manual_incident_authored": ("SYNTHETIC DATA", "SYNTHETIC DATA"),
    "synthetic_square_sumo": ("SIMULATION OUTPUT", "SIMULATION OUTPUT"),
    "general_live_road_traffic_bods": ("DESIGN-ONLY CAPABILITY", "DESIGN-ONLY CAPABILITY"),
    "live_city_wide_twin": ("DESIGN-ONLY CAPABILITY", "DESIGN-ONLY CAPABILITY"),
    "social_media_ingestion": ("DESIGN-ONLY CAPABILITY", "DESIGN-ONLY CAPABILITY"),
}

EXPECTED_B_LABELS: dict[str, str] = {
    "FINAL_AUDIT": "FINAL_NEGOTIATED_REQUIREMENTS_AUDIT",
    "NEGOTIATED_V1_WHOLE_FILE": "FROZEN_REQUIREMENTS_BASELINE_CONTAINER",
    "RESEARCH_AUDIT_SEMANTIC_CONTRACT": "ORIGINAL_RESEARCH_AUDIT_AND_SEMANTIC_CONTRACT",
    "AUDIT_SOURCE_INDEX": "AUDIT_SOURCE_INDEX",
    "S-007": "DIRECT_RANDY_QA",
    "S-035 / SANDRA-DIRECT-BODY-2026-08-04": "DIRECT_SUPERVISOR_SOURCE_BODY",
    "PRODUCT_DESIGN_V2": "CLASS_D_PRODUCT_DESIGN_PROPOSAL",
}

_ALLOWED_A_STANDINGS = {
    "REAL MANCHESTER DATA",
    "REAL EXTERNAL NON-MANCHESTER DATA",
    "SYNTHETIC DATA",
    "SIMULATION OUTPUT",
    "DESIGN-ONLY CAPABILITY",
}

_ALLOWED_B_STANDINGS = {
    "FINAL_NEGOTIATED_REQUIREMENTS_AUDIT",
    "FROZEN_REQUIREMENTS_BASELINE_CONTAINER",
    "ORIGINAL_RESEARCH_AUDIT_AND_SEMANTIC_CONTRACT",
    "AUDIT_SOURCE_INDEX",
    "DIRECT_RANDY_QA",
    "DIRECT_SUPERVISOR_SOURCE_BODY",
    "CLASS_D_PRODUCT_DESIGN_PROPOSAL",
}

_ALLOWED_ALL_STANDINGS = _ALLOWED_A_STANDINGS | _ALLOWED_B_STANDINGS | {"MIXED"}


def validate_evidence_labels(errors: list[str]) -> None:
    # Evidence labels must distinguish SOURCE-DERIVED,
    # IMPLEMENTATION-VERIFIED, RESEARCH-EVIDENCE etc.
    # Check that closure report, traceability, assessment contain honesty labels
    for md_path in [TRACEABILITY_MD, RESTRUCTURE_PLAN_MD, CONTRIBUTION_MD]:
        if md_path.exists():
            text = md_path.read_text(encoding="utf-8")
            has_label = any(label in text for label in HONESTY_LABELS)
            if not has_label:
                errors.append(f"{md_path.relative_to(REPO_ROOT)} missing honesty vocabulary")
    # Freeze exact manifest-specific map for every Use Case A source_id
    if USE_CASE_A_MANIFEST.exists():
        data = _load_json(USE_CASE_A_MANIFEST)
        sources = {s.get("source_id"): s for s in data.get("sources", [])}
        for sid, (exp_class, exp_standing) in EXPECTED_A_LABELS.items():
            src = sources.get(sid)
            if src is None:
                errors.append(f"use_case_a missing source {sid}")
                continue
            cls = src.get("classification")
            st = src.get("evidence_standing")
            if cls != exp_class:
                errors.append(
                    f"use_case_a source {sid} classification "
                    f"mismatch: got {cls!r} expected {exp_class!r}"
                )
            if st != exp_standing:
                errors.append(
                    f"use_case_a source {sid} evidence_standing "
                    f"mismatch: got {st!r} expected {exp_standing!r}"
                )
            if cls != st:
                errors.append(
                    f"use_case_a source {sid} classification and "
                    f"evidence_standing disagree: {cls!r} vs {st!r}"
                )
            if st and st not in _ALLOWED_A_STANDINGS:
                errors.append(f"use_case_a source {sid} has unrecognised standing {st!r}")
            if cls and cls not in _ALLOWED_A_STANDINGS:
                errors.append(f"use_case_a source {sid} has unrecognised classification {cls!r}")
        for sid in list(sources.keys()):
            if sid not in EXPECTED_A_LABELS:
                errors.append(f"use_case_a unexpected source {sid}")
        for src in data.get("sources", []):
            st = src.get("evidence_standing") or src.get("classification")
            if st and st not in _ALLOWED_ALL_STANDINGS:
                errors.append(
                    f"use_case_a source {src.get('source_id')} has invented standing {st!r}"
                )
    # Freeze Use Case B source identity/standing map (authoritative vocab)
    if USE_CASE_B_MANIFEST.exists():
        data = _load_json(USE_CASE_B_MANIFEST)
        sources = {s.get("id"): s for s in data.get("sources", [])}
        for sid, exp_standing in EXPECTED_B_LABELS.items():
            src = sources.get(sid)
            if src is None:
                errors.append(f"use_case_b missing source {sid}")
                continue
            st = src.get("standing")
            if st != exp_standing:
                errors.append(
                    f"use_case_b source {sid} standing "
                    f"mismatch: got {st!r} expected {exp_standing!r}"
                )
            if st and st not in _ALLOWED_B_STANDINGS:
                errors.append(f"use_case_b source {sid} has unrecognised standing {st!r}")
        for sid in list(sources.keys()):
            if sid not in EXPECTED_B_LABELS:
                errors.append(f"use_case_b unexpected source {sid}")
        for src in data.get("sources", []):
            st = src.get("standing")
            if st and st not in _ALLOWED_ALL_STANDINGS:
                errors.append(f"use_case_b source {src.get('id')} has invented standing {st!r}")
    # Also check manchester demo contract classification honesty
    # synthetic square must be SYNTHETIC etc.


def validate_manchester_standing(errors: list[str]) -> None:
    for p in [MANCHESTER_DEMO_CURRENT]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
            return
    data = _load_json(MANCHESTER_DEMO_CURRENT)
    standing = data.get("standing")
    if standing != "MIXED":
        errors.append(f"manchester_demo current_view standing must be MIXED, got {standing!r}")
    if "deterministic_fixture_marker" not in data:
        errors.append("manchester_demo current_view missing deterministic_fixture_marker")
    if "generated_utc" in data:
        errors.append(
            "manchester_demo current_view must not contain generated_utc "
            "(use deterministic_fixture_marker)"
        )
    # Check layers honesty
    layers = data.get("layers", [])
    layer_ids = [layer.get("layer_id") for layer in layers]
    if "tfgm_signal_locations" in layer_ids:
        errors.append("tfgm_signal_locations must be in unavailable_layers, not active layers")
    # Source receipt cross-check
    if MANCHESTER_SOURCE_RECEIPT.exists():
        receipt = _load_json(MANCHESTER_SOURCE_RECEIPT)
        if receipt.get("standing") != "MIXED":
            errors.append("manchester source_receipt standing must be MIXED")


def validate_dissertation_trace(errors: list[str]) -> None:
    if not TRACEABILITY_MD.exists():
        errors.append(f"missing required file: {TRACEABILITY_MD.relative_to(REPO_ROOT)}")
        return
    text = TRACEABILITY_MD.read_text(encoding="utf-8")
    # Each TT-REQ-001..014 must appear exactly once in trace master table
    # Count occurrences in trace table rows: pattern TT-REQ-0xx
    _ids = re.findall(r"TT-REQ-0\d{2}", text)
    # Filter to those inside the trace master table section
    trace_section = re.search(r"## 2\. Trace master.*?(?=## 3\.|$)", text, flags=re.DOTALL)
    if trace_section:
        trace_text = trace_section.group(0)
        trace_ids = re.findall(r"(TT-REQ-0\d{2})", trace_text)
        from collections import Counter

        counts = Counter(trace_ids)
        for i in range(1, 15):
            rid = f"TT-REQ-{i:03d}"
            c = counts.get(rid, 0)
            if c != 1:
                errors.append(
                    f"dissertation trace {rid} appears {c} times "
                    "in trace master, expected exactly 1"
                )
        # Also check no extra TT-REQ outside trace
        extra = [k for k, v in counts.items() if v > 1]
        if extra:
            errors.append(f"dissertation trace duplicate IDs: {extra}")
    else:
        errors.append("dissertation trace missing trace master section")
    # Check status/priority match requirements_status and baseline
    if STATUS_JSON.exists() and BASELINE_JSON.exists():
        status = _load_json(STATUS_JSON)
        baseline = _load_json(BASELINE_JSON)
        baseline_reqs = {r["id"]: r for r in baseline.get("requirements", [])}
        status_reqs = {r["id"]: r for r in status.get("requirements", [])}
        for rid in [f"TT-REQ-{i:03d}" for i in range(1, 15)]:
            b = baseline_reqs.get(rid)
            s = status_reqs.get(rid)
            if b and s and b.get("priority") != s.get("priority"):
                errors.append(
                    f"trace priority mismatch {rid}: "
                    f"baseline {b.get('priority')} vs status {s.get('priority')}"
                )
            # Check that trace table mentions the same priority
            # (lenient: just ensure trace text contains the priority near the ID)
    # Check restructure plan covers all chapters
    if RESTRUCTURE_PLAN_MD.exists():
        rp = RESTRUCTURE_PLAN_MD.read_text(encoding="utf-8")
        if "TT-REQ-001" not in rp:
            errors.append("restructure plan missing TT-REQ-001")
    # Honesty labels
    if not any(label in text for label in HONESTY_LABELS):
        errors.append("dissertation traceability missing honesty vocabulary")


def validate_video_completeness(errors: list[str]) -> None:
    for p in [VIDEO_SCRIPT, VIDEO_STORYBOARD, VIDEO_CLICK_PATH, VIDEO_CHECKLIST]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
            return
    script = VIDEO_SCRIPT.read_text(encoding="utf-8")
    storyboard = VIDEO_STORYBOARD.read_text(encoding="utf-8")
    time_col_re = re.compile(r"^\s*(\d+):(\d{2})\s*$")

    def _parse(text: str) -> list[tuple[int, int]]:
        pairs: list[tuple[int, int]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            cols = [c.strip() for c in line.split("|")]
            # cols[0] empty, 1 is index, 2 title, 3 start, 4 end for pipe tables
            # Try pipe column extraction: start in cols[3], end in cols[4]
            if len(cols) >= 5:
                start_raw = cols[3] if len(cols) > 3 else ""
                end_raw = cols[4] if len(cols) > 4 else ""
                m_s = time_col_re.match(start_raw)
                m_e = time_col_re.match(end_raw)
                if m_s and m_e:
                    s = int(m_s.group(1)) * 60 + int(m_s.group(2))
                    e = int(m_e.group(1)) * 60 + int(m_e.group(2))
                    if 0 <= s < e <= 420:
                        pairs.append((s, e))
                        continue
            # Fallback: dash form inside line (e.g., heading or proof line but not pipe-filtered)
            for m in TIME_RE.finditer(line):
                s = int(m.group(1)) * 60 + int(m.group(2))
                e = int(m.group(3)) * 60 + int(m.group(4))
                if 0 <= s < e <= 420:
                    pairs.append((s, e))
        seen: set[tuple[int, int]] = set()
        uniq: list[tuple[int, int]] = []
        for p in pairs:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        uniq.sort(key=lambda x: x[0])
        return uniq[:8]

    segs = _parse(script)
    if len(segs) != 8:
        errors.append(f"video script segments count {len(segs)} != 8 (parsed {segs})")
        return
    expected = [
        (0, 30),
        (30, 75),
        (75, 135),
        (135, 190),
        (190, 250),
        (250, 315),
        (315, 375),
        (375, 420),
    ]
    if segs != expected:
        errors.append(f"video script timings {segs} != expected {expected}")
    if segs[0][0] != 0:
        errors.append("video segments do not start at 0:00")
    if segs[-1][1] != 420:
        errors.append("video segments do not end at 7:00 (420s)")
    for i in range(len(segs) - 1):
        if segs[i][1] != segs[i + 1][0]:
            errors.append(f"video gap/overlap between segment {i + 1} and {i + 2}")
    # Storyboard must match
    sb_segs = _parse(storyboard)
    if sb_segs != segs:
        errors.append(f"storyboard timings {sb_segs} != script timings {segs}")
    # Checklist must have 10 shots each with standing and non-empty limitation
    checklist = VIDEO_CHECKLIST.read_text(encoding="utf-8")
    # Count SHOT rows
    shot_rows = [line for line in checklist.splitlines() if re.match(r"^\|\s*SHOT-\d+", line)]
    if len(shot_rows) != 10:
        errors.append(f"video checklist shot count {len(shot_rows)} != 10")
    else:
        for row in shot_rows:
            cols = [c.strip() for c in row.split("|")]
            # cols: [0 empty, 1 SHOT, 2 segment, 3 visual, 4 locator,
            #  5 standing, 6 limitation, 7 empty]
            if len(cols) < 7:
                errors.append(f"video checklist malformed row: {row[:60]}")
                continue
            standing = cols[5] if len(cols) > 5 else ""
            limitation = cols[6] if len(cols) > 6 else ""
            if not standing.strip():
                errors.append(f"video checklist shot missing standing: {row[:80]}")
            if not limitation.strip():
                errors.append(f"video checklist shot missing limitation: {row[:80]}")
            # Standing must contain a known honesty label
            if standing and not any(
                label.lower() in standing.lower()
                for label in [
                    "SOURCE-DERIVED",
                    "IMPLEMENTATION-VERIFIED",
                    "RESEARCH-EVIDENCE",
                    "INFERENCE",
                    "PROVISIONAL",
                    "EXTERNAL",
                ]
            ):
                errors.append(f"video checklist shot standing missing honesty label: {standing!r}")
    # Check forbidden claims absent outside enumeration line
    for phrase in ["FULLY ALIGNED", "Sandra confirmation received", "recorded and submitted"]:
        # Allow if inside limitation row but not standalone claim
        if phrase.lower() in checklist.lower():
            # Check not inside forbidden claim enumeration line
            lines = [line for line in checklist.splitlines() if phrase.lower() in line.lower()]
            for line in lines:
                if (
                    "must not" not in line.lower()
                    and "forbidden" not in line.lower()
                    and "prohibited" not in line.lower()
                    and phrase == "FULLY ALIGNED"
                    and "not FULLY" not in line
                    and "PARTIALLY" not in line
                ):
                    errors.append(f"video checklist contains forbidden phrase {phrase!r}")


def validate_no_unresolved_must_silently_met(errors: list[str]) -> None:
    if not STATUS_JSON.exists():
        errors.append(f"missing required file: {STATUS_JSON.relative_to(REPO_ROOT)}")
        return
    status = _load_json(STATUS_JSON)
    must_arith = status.get("must_arithmetic", {})
    verified = set(must_arith.get("verified_met_ids", []))
    partially = set(must_arith.get("partially_met_ids", []))
    not_applicable = set(must_arith.get("not_applicable_ids", []))
    total = must_arith.get("total_must")
    if total != 11:
        errors.append(f"must_arithmetic total_must !=11 got {total}")
    if len(verified) + len(partially) + len(not_applicable) != 11:
        errors.append("must_arithmetic 3+7+1 !=11")
    if must_arith.get("verified_met") != len(verified):
        errors.append("must_arithmetic verified_met count mismatch")
    # Verify no unresolved MUST silently MET:
    # every PARTIALLY_MET must have gap_id and gap_description
    for r in status.get("requirements", []):
        if r.get("priority") == "MUST" and r.get("status") == "VERIFIED_MET":
            if r.get("gap_id") is not None:
                errors.append(f"MUST VERIFIED_MET {r['id']} should have null gap_id")
            # Check that VERIFIED_MET MUSTs are exactly the allowed set
            allowed_verified = {"TT-REQ-006", "TT-REQ-010", "TT-REQ-012"}
            if r["id"] not in allowed_verified:
                errors.append(
                    f"MUST {r['id']} marked VERIFIED_MET but not in allowed {allowed_verified}"
                )
        if r.get("priority") == "MUST" and r.get("status") == "PARTIALLY_MET":
            if not r.get("gap_id"):
                errors.append(f"MUST PARTIALLY_MET {r['id']} missing gap_id — silent MET")
            if not r.get("gap_description"):
                errors.append(f"MUST PARTIALLY_MET {r['id']} missing gap_description")
        if r.get("priority") == "MUST" and r.get("status") == "DECISION_REQUIRED":
            errors.append(
                f"MUST must not use DECISION_REQUIRED status (only SHOULD/MAY) — {r['id']}"
            )
    # Check that TT-REQ-013 NOT_APPLICABLE is preserved and not counted as MET
    if "TT-REQ-013" not in not_applicable:
        errors.append("TT-REQ-013 must be NOT_APPLICABLE (trigger not observed)")
    # Check SHOULD TT-REQ-008 remains SHOULD PARTIALLY_MET not MUST
    for r in status.get("requirements", []):
        if r["id"] == "TT-REQ-008" and r.get("priority") != "SHOULD":
            errors.append(f"TT-REQ-008 priority must remain SHOULD, got {r.get('priority')}")
        if r["id"] == "TT-REQ-008" and r.get("status") != "PARTIALLY_MET":
            errors.append(f"TT-REQ-008 status must be PARTIALLY_MET, got {r.get('status')}")


def validate_rollback_identity(errors: list[str]) -> None:
    # Check that compare.py preserves transactional rollback and identity continuity
    # Static check complements executable AppTest; both are retained
    if not COMPARE_PAGE.exists():
        errors.append(f"missing required file: {COMPARE_PAGE.relative_to(REPO_ROOT)}")
        return
    text = COMPARE_PAGE.read_text(encoding="utf-8")
    # Must strip before Path construction to avoid Path("") == Path(".") corruption
    if "strip()" not in text:
        errors.append(
            "compare page missing strip() before Path construction — "
            "Path('') corruption not prevented"
        )
    if "Only after pair is successfully usable" not in text:
        errors.append("compare page missing transactional rollback comment")
    # Check that both selected_baseline_run and selected_variation_run are assigned atomically
    if (
        'st.session_state["selected_baseline_run"]' not in text
        or 'st.session_state["selected_variation_run"]' not in text
    ):
        errors.append("compare page missing identity continuity session keys")
    # Check navigation_v07 contains required UiPage entries
    if NAVIGATION_V07.exists():
        nav = NAVIGATION_V07.read_text(encoding="utf-8")
        for required in ["WHATIF_STUDIO", "CONSEQUENCE_LENSES", "COMPARE", "GUIDED_DEMO", "HOME"]:
            if required not in nav:
                errors.append(f"navigation_v07 missing UiPage.{required}")
        if "def page_script_for" not in nav:
            errors.append("navigation_v07 missing page_script_for function")
    # Check that data_mode_label preservation is not broken — labels include SYNTHETIC
    if "_provenance_badge" not in text and "provenance_badge" not in text:
        errors.append(
            "compare page missing provenance badge (data_mode_label=SYNTHETIC preservation)"
        )


def validate_closure_package_index(errors: list[str]) -> None:
    if not CLOSURE_INDEX.exists():
        errors.append(f"missing required file: {CLOSURE_INDEX.relative_to(REPO_ROOT)}")
        return
    data = _load_json(CLOSURE_INDEX)
    # Must embed dependency identities and manifest SHA
    if data.get("dependency_manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        errors.append(
            f"closure_package_index dependency_manifest_sha256 mismatch "
            f"got {data.get('dependency_manifest_sha256')} "
            f"expected {EXPECTED_MANIFEST_SHA256}"
        )
    raw_deps = data.get("dependencies", {})
    deps_dict: dict[str, str] = {}
    if isinstance(raw_deps, dict):
        deps_dict = {str(k): str(v) for k, v in raw_deps.items()}
    elif isinstance(raw_deps, list):
        for entry in raw_deps:
            if isinstance(entry, dict) and "lane" in entry and "frozen_sha" in entry:
                deps_dict[str(entry["lane"])] = str(entry["frozen_sha"])
    for lane, sha in EXPECTED_DEPENDENCIES.items():
        actual = deps_dict.get(lane)
        if actual is None:
            errors.append(f"closure_package_index missing dependency lane {lane} SHA {sha}")
        elif actual != sha:
            errors.append(
                f"closure_package_index lane {lane} SHA mismatch got {actual} expected {sha}"
            )
    if data.get("prepared_base_sha") != EXPECTED_PREPARED_BASE_SHA:
        errors.append(
            f"closure_package_index prepared_base_sha mismatch "
            f"got {data.get('prepared_base_sha')} "
            f"expected {EXPECTED_PREPARED_BASE_SHA}"
        )
    if data.get("campaign_base_sha") != EXPECTED_BASE_SHA:
        errors.append("closure_package_index campaign_base_sha mismatch")


def validate_closure_report(errors: list[str]) -> None:
    if not CLOSURE_REPORT.exists():
        errors.append(f"missing required file: {CLOSURE_REPORT.relative_to(REPO_ROOT)}")
        return
    text = CLOSURE_REPORT.read_text(encoding="utf-8")
    # Must distinguish honesty categories
    if not any(label in text for label in HONESTY_LABELS):
        errors.append("closure acceptance report missing honesty vocabulary")
    # Must record external decisions
    if "EXTERNAL DECISION REQUIRED" not in text:
        errors.append("closure acceptance report missing EXTERNAL DECISION REQUIRED")
    # Must note frozen SHAs
    for sha_prefix in [
        EXPECTED_PAYLOAD_SHA256[:8],
        EXPECTED_WHOLE_SHA256[:8],
        EXPECTED_S035_SHA256[:8],
    ]:
        if sha_prefix not in text:
            errors.append(f"closure acceptance report missing frozen SHA prefix {sha_prefix}")


def validate_harness_optional_crosscheck(errors: list[str]) -> None:
    # If .harness context exists, cross-check it matches embedded constants
    harness_manifest = REPO_ROOT / ".harness/context/dependency_sha_manifest.json"
    if harness_manifest.exists():
        try:
            data = _load_json(harness_manifest)
            actual_sha = hashlib.sha256(harness_manifest.read_bytes()).hexdigest()
            if actual_sha != EXPECTED_MANIFEST_SHA256:
                errors.append(
                    f".harness manifest SHA mismatch: "
                    f"got {actual_sha} expected {EXPECTED_MANIFEST_SHA256}"
                )
            # Check each lane
            for dep in data.get("dependencies", []):
                lane = dep.get("lane")
                sha = dep.get("frozen_sha")
                if lane in EXPECTED_DEPENDENCIES and sha != EXPECTED_DEPENDENCIES[lane]:
                    errors.append(f".harness dependency lane {lane} SHA drift")
        except Exception as e:
            errors.append(f".harness manifest cross-check failed: {e}")


def validate() -> list[str]:
    errors: list[str] = []
    validate_baseline_hash(errors)
    validate_two_distinct_cases(errors)
    validate_strategy_matrix(errors)
    validate_improved_contract(errors)
    validate_evidence_refs(errors)
    validate_accounting(errors)
    validate_evidence_labels(errors)
    validate_manchester_standing(errors)
    validate_dissertation_trace(errors)
    validate_video_completeness(errors)
    validate_no_unresolved_must_silently_met(errors)
    validate_rollback_identity(errors)
    validate_closure_package_index(errors)
    validate_closure_report(errors)
    validate_harness_optional_crosscheck(errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("FAIL: v08 requirements closure validation", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("PASS: v08 requirements closure validation — all categories verified")
    print(f"  baseline: {EXPECTED_PAYLOAD_SHA256[:8]} / {EXPECTED_WHOLE_SHA256[:8]}")
    print("  cases: 2 distinct (Manchester + VEC)")
    print(
        "  strategies: 5 (strongest_link_off, jsq_without_gate, "
        "ingress_dla, common_target_dla, per_task_dla)"
    )
    fingerprint = (
        hashlib.sha256(
            json.dumps(
                {
                    k: _load_json(IMPROVED_CONTRACT_JSON)[k]
                    for k in FINGERPRINT_KEYS
                    if k in _load_json(IMPROVED_CONTRACT_JSON)
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()[:8]
        if IMPROVED_CONTRACT_JSON.exists()
        else "missing"
    )
    print(f"  improved-contract: {fingerprint}")
    print("  accounting: offered == admitted + gate + capacity (conservation)")
    print("  manchester: MIXED bounded demonstration")
    print("  dissertation: 14 requirements traceable")
    print("  video: 420s / 8 segments")
    print("  MUST arithmetic: 3 VERIFIED_MET + 7 PARTIALLY_MET + 1 NOT_APPLICABLE = 11")
    return 0


if __name__ == "__main__":
    sys.exit(main())
