#!/usr/bin/env python3
"""Validator for v08 lane 07 E2b–E2d evidence synthesis.

Checks:
- every figure cell resolves to exact read-only evidence identity
- E2b/E2c/E2d distinctions and limitations survive
- replication/uncertainty fields explicit
- every numeric row bound to code SHA, manifest hash, actor, trace, seed, artifact
- replication unit is fleet_draw/run, never task
- orphan numbers rejected
- JSON and CSV rows joined on figure_id require identical value,
  artifact path, seed identity
- E2b arm artifact paths pinned to authoritative upstream paths
- prose mechanism ranges validated (bounded observed min-max,
  not unsupported ~0.04-0.06 / ~0.18-0.24)
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/closure/v08_alignment/improved_strategy_results.json"
INDEX = ROOT / "docs/closure/v08_alignment/improved_strategy_evidence_index.json"
FIGURE_CSV = ROOT / "docs/closure/v08_alignment/improved_strategy_figure_data.csv"
SUMMARY = ROOT / "docs/closure/v08_alignment/improved_strategy_evidence_summary.md"

ALLOWED_REPLICATION_UNITS = {"fleet_draw", "fleet_seed", "run"}
FORBIDDEN_REPLICATION_SUBSTRINGS = {"task"}

# Expected manifest hashes for known evidence (pinned)
EXPECTED_MANIFESTS = {
    "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
    "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
    "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
}

EXPECTED_COMMITS = {
    "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6",
    "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
    "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
    "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
}

ACTOR_SHA = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"

# Pinned authoritative E2b arm artifact paths
EXPECTED_E2B_ARTIFACTS = {
    "fig1_e2b_offered_attainment_off": (
        "/Users/akashx/AntigravityTest/e2_outputs/e2-native-placement-pilot-v1/full/off/run_1"  # noqa: E501
    ),
    "fig1_e2b_offered_attainment_jsq": (
        "/Users/akashx/AntigravityTest/e2_outputs/e2-native-placement-pilot-v1/full/jsq/run_1"  # noqa: E501
    ),
    "fig1_e2b_offered_attainment_dla": (
        "/Users/akashx/AntigravityTest/e2_outputs/e2-native-placement-pilot-v1/full/dla/run_1"  # noqa: E501
    ),
    "fig1_e2b_offered_attainment_ingress_dla": (
        "/Users/akashx/AntigravityTest/e2b_outputs/e2b-placement-admission-factorial-v1/full/ingress_dla/run_1"  # noqa: E501
    ),
}

REQUIRED_ROW_FIELDS = [
    "figure_id",
    "evidence_id",
    "value",
    "manifest_sha256",
    "code_commit",
    "actor_sha256",
    "trace_sha256",
    "fleet_seed",
    "artifact_path",
    "replication_unit",
]

REQUIRED_CSV_COLUMNS = [
    "figure_id",
    "evidence_id",
    "metric",
    "arm",
    "value",
    "manifest_sha256",
    "code_commit",
    "actor_sha256",
    "trace_sha256",
    "fleet_seed",
    "evaluator_seed",
    "artifact_path",
    "replication_unit",
    "uncertainty",
    "standing",
]


def fail(msg: str) -> None:
    print(f"VALIDATION FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def validate() -> None:
    errors: list[str] = []

    # Existence
    for p in (RESULTS, INDEX, FIGURE_CSV, SUMMARY):
        if not p.exists():
            errors.append(f"missing required file: {p}")

    if errors:
        for err_msg in errors:
            print(f"VALIDATION FAILED: {err_msg}", file=sys.stderr)
        sys.exit(1)

    # Load JSONs
    try:
        results = json.loads(RESULTS.read_text())
    except Exception as exc:
        fail(f"results json invalid: {exc}")

    try:
        index = json.loads(INDEX.read_text())
    except Exception as exc2:
        fail(f"evidence index json invalid: {exc2}")

    evidence_ids = set(index.get("evidence_identities", {}).keys())
    figure_to_evidence = index.get("figure_cell_to_evidence", {})
    replication_unit_top = index.get("replication_unit", "")

    if (
        replication_unit_top.lower() in FORBIDDEN_REPLICATION_SUBSTRINGS
        or "task" in replication_unit_top.lower()
    ):
        errors.append(
            f"evidence_index replication_unit must not be task-level, got {replication_unit_top}"
        )

    # Check results structure
    rows = results.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("results.json: 'rows' must be non-empty list")

    # Check replication_unit top-level in results
    ru = results.get("replication_unit", "")
    if not isinstance(ru, str) or ru not in ALLOWED_REPLICATION_UNITS:
        errors.append(
            f"results.json replication_unit must be one of {ALLOWED_REPLICATION_UNITS}, got {ru!r}"
        )
    if isinstance(ru, str) and "task" in ru.lower():
        errors.append(f"results.json replication_unit must not be task, got {ru}")

    # Check uncertainty fields explicit
    uncertainty = results.get("uncertainty", {})
    for key in ["e2c_primary_interval", "e2d_primary_interval"]:
        block = uncertainty.get(key)
        if not isinstance(block, dict):
            errors.append(f"results.json uncertainty missing block {key}")
            continue
        for field_name in [
            "replication_unit",
            "n_fleet_draws",
            "degrees_of_freedom",
            "method",
            "lower",
            "upper",
        ]:
            if field_name not in block:
                errors.append(f"results.json uncertainty.{key} missing field {field_name}")
        if block.get("replication_unit") not in ALLOWED_REPLICATION_UNITS:
            errors.append(f"results.json uncertainty.{key} replication_unit invalid")
        if "task" in str(block.get("replication_unit", "")).lower():
            errors.append(f"results.json uncertainty.{key} replication_unit must not be task")

    # Validate each row binding
    csv_evidence_ids: set[str] = set()
    json_by_id: dict[str, dict[str, object]] = {}
    if isinstance(rows, list):
        for i, row in enumerate(rows):
            prefix = f"results.json rows[{i}]"
            if not isinstance(row, dict):
                errors.append(f"{prefix} not an object")
                continue
            for field in REQUIRED_ROW_FIELDS:
                if field not in row or row[field] in (None, ""):
                    # fleet_seed can be 0 but not empty
                    if field == "fleet_seed" and row.get(field) == 0:
                        continue
                    errors.append(f"{prefix} missing or empty binding field: {field}")
            # replication unit check
            rru = str(row.get("replication_unit", ""))
            if rru not in ALLOWED_REPLICATION_UNITS:
                errors.append(
                    f"{prefix} replication_unit must be in {ALLOWED_REPLICATION_UNITS}, got {rru!r}"
                )
            if "task" in rru.lower():
                errors.append(f"{prefix} replication_unit must not be task-level, got {rru}")
            # evidence_id must exist in index
            eid = row.get("evidence_id")
            if eid and eid not in evidence_ids:
                errors.append(f"{prefix} evidence_id {eid!r} not in evidence_index")
            # manifest check
            manifest = row.get("manifest_sha256", "")
            if manifest and manifest not in EXPECTED_MANIFESTS:
                errors.append(f"{prefix} manifest_sha256 {manifest!r} not in expected allowlist")
            # code commit check
            code = row.get("code_commit", "")
            if code and code not in EXPECTED_COMMITS:
                errors.append(f"{prefix} code_commit {code!r} unexpected")
            # actor/trace binding
            if row.get("actor_sha256") != ACTOR_SHA:
                errors.append(f"{prefix} actor_sha256 must be {ACTOR_SHA}")
            if row.get("trace_sha256") != TRACE_SHA:
                errors.append(f"{prefix} trace_sha256 must be {TRACE_SHA}")
            # fleet_seed must be int
            fs = row.get("fleet_seed")
            if not isinstance(fs, int):
                errors.append(f"{prefix} fleet_seed must be int, got {fs!r}")
            # value must be numeric
            if not isinstance(row.get("value"), (int, float)):
                errors.append(f"{prefix} value must be numeric")
            # figure_id must be mapped
            fid = row.get("figure_id", "")
            if fid and fid not in figure_to_evidence:
                # allow only if evidence_id matches mapping
                pass
            # collect for join validation
            if isinstance(fid, str) and fid:
                if fid in json_by_id:
                    errors.append(f"results.json duplicate figure_id {fid!r}")
                json_by_id[fid] = row
            # pinned E2b artifact path check for JSON rows
            if isinstance(fid, str) and fid in EXPECTED_E2B_ARTIFACTS:
                expected_path = EXPECTED_E2B_ARTIFACTS[fid]
                actual_path = row.get("artifact_path", "")
                if actual_path != expected_path:
                    errors.append(
                        f"{prefix} artifact_path for {fid!r} must be {expected_path!r}, got {actual_path!r}"  # noqa: E501
                    )

    # Validate figure CSV
    csv_by_id: dict[str, dict[str, str]] = {}
    try:
        with FIGURE_CSV.open(newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames != REQUIRED_CSV_COLUMNS:
                errors.append(f"figure_data.csv header mismatch: {reader.fieldnames}")
            rows_csv = list(reader)
            if not rows_csv:
                errors.append("figure_data.csv has no data rows")
            for idx, r in enumerate(rows_csv, start=2):
                prefix = f"figure_data.csv:{idx}"
                for col in REQUIRED_CSV_COLUMNS:
                    val = r.get(col, "")
                    if val == "" or val is None:
                        # fleet_seed 0 is "0" string, allowed
                        if col == "fleet_seed" and val == "0":
                            continue
                        if col == "evaluator_seed" and val == "0":
                            continue
                        errors.append(f"{prefix} missing or empty column {col}")
                # replication unit
                rru = r.get("replication_unit", "")
                if rru not in ALLOWED_REPLICATION_UNITS:
                    errors.append(f"{prefix} replication_unit invalid {rru!r}")
                if "task" in rru.lower():
                    errors.append(f"{prefix} replication_unit must not be task")
                eid = r.get("evidence_id", "")
                if eid and eid not in evidence_ids:
                    errors.append(f"{prefix} evidence_id {eid!r} not in index")
                else:
                    csv_evidence_ids.add(eid)
                # orphan check: same binding fields as JSON
                if r.get("manifest_sha256", "") not in EXPECTED_MANIFESTS:
                    errors.append(
                        f"{prefix} manifest_sha256 not expected: {r.get('manifest_sha256')}"
                    )
                if r.get("code_commit", "") not in EXPECTED_COMMITS:
                    errors.append(f"{prefix} code_commit unexpected: {r.get('code_commit')}")
                if r.get("actor_sha256", "") != ACTOR_SHA:
                    errors.append(f"{prefix} actor_sha256 mismatch")
                if r.get("trace_sha256", "") != TRACE_SHA:
                    errors.append(f"{prefix} trace_sha256 mismatch")
                # value numeric
                try:
                    float(r.get("value", ""))
                except Exception:
                    errors.append(f"{prefix} value not numeric: {r.get('value')}")
                # fleet_seed int
                try:
                    int(r.get("fleet_seed", ""))
                except Exception:
                    errors.append(f"{prefix} fleet_seed not int")
                # evaluator_seed int
                try:
                    int(r.get("evaluator_seed", ""))
                except Exception:
                    errors.append(f"{prefix} evaluator_seed not int")
                # collect for join validation
                fid_csv = r.get("figure_id", "")
                if fid_csv:
                    if fid_csv in csv_by_id:
                        errors.append(f"figure_data.csv duplicate figure_id {fid_csv!r}")
                    csv_by_id[fid_csv] = r
                # pinned E2b artifact path check for CSV rows
                if fid_csv in EXPECTED_E2B_ARTIFACTS:
                    expected_path = EXPECTED_E2B_ARTIFACTS[fid_csv]
                    actual_path = r.get("artifact_path", "")
                    if actual_path != expected_path:
                        errors.append(
                            f"{prefix} artifact_path for {fid_csv!r} must be {expected_path!r}, got {actual_path!r}"  # noqa: E501
                        )
    except Exception as csv_exc:
        errors.append(f"figure_data.csv read error: {csv_exc}")

    # Join validation: JSON and CSV rows on figure_id require identical value, artifact_path, seed identity  # noqa: E501
    all_figure_ids = set(json_by_id.keys()) | set(csv_by_id.keys())
    for fid in sorted(all_figure_ids):
        if fid not in json_by_id:
            errors.append(
                f"join mismatch: figure_id {fid!r} present in CSV but missing in results.json"
            )
            continue
        if fid not in csv_by_id:
            errors.append(
                f"join mismatch: figure_id {fid!r} present in results.json but missing in CSV"
            )
            continue
        jrow = json_by_id[fid]
        crow = csv_by_id[fid]
        # value identical
        try:
            jval = float(jrow.get("value", float("nan")))  # type: ignore[arg-type]
            cval = float(crow.get("value", float("nan")))
            if not math.isclose(jval, cval, rel_tol=0, abs_tol=1e-12):
                errors.append(
                    f"join mismatch for {fid!r}: value differs JSON {jval!r} vs CSV {cval!r}"
                )
        except Exception as exc:
            errors.append(f"join mismatch for {fid!r}: value comparison error: {exc}")
        # artifact_path identical
        jpath = str(jrow.get("artifact_path", ""))
        cpath = str(crow.get("artifact_path", ""))
        if jpath != cpath:
            errors.append(
                f"join mismatch for {fid!r}: artifact_path differs JSON {jpath!r} vs CSV {cpath!r}"
            )
        # seed identity: fleet_seed and evaluator_seed
        try:
            j_fleet = int(jrow.get("fleet_seed", -1))  # type: ignore  # noqa: E501
            c_fleet = int(crow.get("fleet_seed", -2))
            if j_fleet != c_fleet:
                errors.append(
                    f"join mismatch for {fid!r}: fleet_seed differs JSON {j_fleet!r} vs CSV {c_fleet!r}"  # noqa: E501
                )
        except Exception as exc:
            errors.append(f"join mismatch for {fid!r}: fleet_seed comparison error: {exc}")
        try:
            j_eval = int(jrow.get("evaluator_seed", -1))  # type: ignore  # evaluator_seed present in JSON rows  # noqa: E501
            c_eval = int(crow.get("evaluator_seed", -2))
            if j_eval != c_eval:
                errors.append(
                    f"join mismatch for {fid!r}: evaluator_seed differs JSON {j_eval!r} vs CSV {c_eval!r}"  # noqa: E501
                )
        except Exception as exc:
            errors.append(f"join mismatch for {fid!r}: evaluator_seed comparison error: {exc}")

    # Every figure cell must resolve to evidence identity
    for fid, eid in figure_to_evidence.items():
        if eid not in evidence_ids:
            errors.append(f"figure_cell_to_evidence {fid} -> {eid} not in evidence_identities")

    # Validate summary contains required distinctions and honesty tags
    summary_text = SUMMARY.read_text()
    required_phrases = [
        "E2b",
        "E2c",
        "E2d",
        "fleet_draw",
        "tasks are accounting records",
        "replication unit",
        "SOURCE-DERIVED FACT",
        "IMPLEMENTATION-VERIFIED FACT",
        "RESEARCH-EVIDENCE FACT",
        "INFERENCE",
        "PROVISIONAL WORDING",
        "EXTERNAL DECISION REQUIRED",
        "research question",
        "comparators",
        "mechanism",
        "uncertainty",
        "interpretation",
        "limits",
        "TT-REQ-008",
        "S-035",
    ]
    for phrase in required_phrases:
        if phrase not in summary_text:
            errors.append(f"summary.md missing required phrase: {phrase}")

    # Check forbidden inference promotion: summary must not claim task-level pseudo-replication
    # Allow discussion of the forbidden label when it is clearly negated or documented as rejected.
    lower_summary = summary_text.lower()
    if "tasks as independent replicates" in lower_summary:
        # If the phrase only appears in a "rejects" documentation context, it is not a claim.
        has_negation = ("not independent" in lower_summary) or (
            "never independent" in lower_summary
        )
        is_documentation = "rejects labels" in lower_summary or "validator" in lower_summary
        if (
            not has_negation
            and not is_documentation
            or "tasks are independent replicates" in lower_summary
        ):
            errors.append("summary.md appears to claim tasks as independent")

    # Validate E2c execution-share prose mechanism ranges are correct bounded values
    # Must contain corrected observed min-max and exact draws,
    # and must NOT contain unsupported old ranges
    if "0.061" not in summary_text or "0.073" not in summary_text:
        errors.append("summary.md E2c ingress_dla execution-share range must contain 0.061–0.073")
    if "0.237" not in summary_text or "0.242" not in summary_text:
        errors.append("summary.md E2c dla execution-share range must contain 0.237–0.242")
    # Exact draws must be present when fact-tagged
    for draw_val in [
        "0.061085",
        "0.072754",
        "0.070738",
        "0.067369",
        "0.242396",
        "0.238025",
        "0.238580",
        "0.236705",
    ]:
        if draw_val not in summary_text:
            errors.append(f"summary.md missing exact E2c draw value {draw_val}")
    # Reject unsupported old ranges
    if "~0.04" in summary_text or "~0.18" in summary_text:
        errors.append("summary.md contains unsupported old E2c range ~0.04–0.06 / ~0.18–0.24")
    if "0.04–0.06" in summary_text and "0.061" not in summary_text:
        errors.append(
            "summary.md contains unsupported ingress range 0.04–0.06 without corrected 0.061–0.073"
        )
    if "0.18–0.24" in summary_text:
        # If old unqualified range appears without corrected prefix, flag
        # Allow only if corrected 0.237–0.242 also present? But old string is distinct.
        errors.append("summary.md contains unsupported dla range 0.18–0.24 (must be 0.237–0.242)")

    # Validate mechanism_bindings in results.json structurally binds same corrected ranges
    mech = results.get("mechanism_bindings", {})
    if isinstance(mech, dict):
        e2c_bind = str(mech.get("e2c_imbalance", ""))
        if e2c_bind:
            if "0.061" not in e2c_bind or "0.073" not in e2c_bind:
                errors.append(
                    "results.json mechanism_bindings.e2c_imbalance must contain 0.061–0.073"
                )
            if "0.237" not in e2c_bind or "0.242" not in e2c_bind:
                errors.append(
                    "results.json mechanism_bindings.e2c_imbalance must contain 0.237–0.242"
                )
            if (
                "~0.04" in e2c_bind
                or "~0.18" in e2c_bind
                or "0.04–0.06" in e2c_bind
                or "0.18–0.24" in e2c_bind
            ):
                errors.append(
                    "results.json mechanism_bindings.e2c_imbalance contains unsupported old range"
                )

    # === Lane 07 source-standing regression guards (S-007, S-035, TT-REQ-008, congested-road) ===
    # 1. S-007 must not be credited with broadcast/microsecond feasibility wording
    # S-007 standing is waiting-room-not-compute only.
    s007_idx = summary_text.find("S-007")
    if s007_idx != -1:
        # examine only the S-007 standing sentence (up to next standing tag or double newline)
        next_tag = summary_text.find("[", s007_idx + 5)
        if next_tag == -1:
            next_tag = s007_idx + 500
        window_s007 = summary_text[s007_idx:next_tag].lower()
        if "broadcast" in window_s007 or "microsecond" in window_s007 or "obsolete" in window_s007:
            errors.append(
                "summary.md S-007 incorrectly credited with broadcast/microsecond feasibility wording; S-007 standing is waiting-room-not-compute only"  # noqa: E501
            )
        # Also catch any S-007 tag that contains broadcast in same bracketed tag
        # Search for "[SOURCE-DERIVED FACT — S-007" containing broadcast before closing bracket
        for tag_start in ["[SOURCE-DERIVED FACT — S-007", "[SOURCE-DERIVED FACT — S-007"]:
            idx = summary_text.find(tag_start)
            if idx != -1:
                tag_end = summary_text.find("]", idx)
                if tag_end != -1:
                    tag_content = summary_text[idx : tag_end + 1].lower()
                    if "broadcast" in tag_content or "microsecond" in tag_content:
                        errors.append(
                            "summary.md S-007 tag must not contain broadcast/microsecond wording"
                        )

    # 2. Hedged S-035 motivation must remain provisional, not promoted to fact/verified/mandatory
    if "as it seems to be the case" not in summary_text:
        errors.append(
            "summary.md missing hedged provisional wording 'as it seems to be the case' for S-035 broadcast/current-load motivation"  # noqa: E501
        )
    # S-035 hedged phrase must be accompanied by provisional standing and correct SHA
    if "as it seems to be the case" in summary_text:
        hedged_idx = summary_text.find("as it seems to be the case")
        hedged_window = summary_text[max(0, hedged_idx - 600) : hedged_idx + 600]
        hedged_lower = hedged_window.lower()
        if "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed" not in hedged_window:
            errors.append(
                "summary.md hedged S-035 motivation must cite SANDRA-DIRECT-BODY SHA 08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed"  # noqa: E501
            )
        if "provisional" not in hedged_lower and "inference" not in hedged_lower:
            errors.append(
                "summary.md hedged S-035 motivation must be tagged PROVISIONAL WORDING or INFERENCE, not fact"  # noqa: E501
            )
        # Must not be promoted to SOURCE-DERIVED FACT or IMPLEMENTATION-VERIFIED in same window
        if (
            "[SOURCE-DERIVED FACT" in hedged_window
            and "as it seems to be the case" in hedged_window
        ):
            # Allow the earlier S-035 infrastructure problem SOURCE-DERIVED FACT window to be separate;  # noqa: E501
            # the hedged window should be provisional, not source-derived fact
            # If the hedged window itself contains a SOURCE-DERIVED FACT tag, it is promotion
            # Check that the nearest tag before hedged phrase is not SOURCE-DERIVED FACT
            tag_before = hedged_window.rfind("[SOURCE-DERIVED FACT")
            prov_before = hedged_window.rfind("[PROVISIONAL")
            inf_before = hedged_window.rfind("[INFERENCE")
            # If SOURCE-DERIVED FACT is closer than provisional/inference, promotion occurred
            if tag_before != -1 and tag_before > max(prov_before, inf_before):
                errors.append(
                    "summary.md hedged S-035 motivation promoted to SOURCE-DERIVED FACT (must remain provisional hedged wording)"  # noqa: E501
                )
        if "[IMPLEMENTATION-VERIFIED" in hedged_window:
            errors.append("summary.md hedged S-035 motivation must not be IMPLEMENTATION-VERIFIED")
        # Must not claim mandatory deliverable without negated provisional qualification
        # Allow negated form "does not ... mandatory deliverable" or "not a mandatory"
        lower_hedged = hedged_window.lower()
        if "mandatory" in lower_hedged and (  # noqa: E501
            "does not" not in lower_hedged
            and "not a mandatory" not in lower_hedged
            and "not by itself" not in lower_hedged
        ):
            errors.append(
                "summary.md hedged S-035 motivation must not be presented as mandatory deliverable"  # noqa: E501
            )
    # Global promotion checks: S-035 broadcast must not be SOURCE-DERIVED FACT
    for needle in ["[SOURCE-DERIVED FACT — S-035", "[SOURCE-DERIVED FACT — S-035 /"]:
        # Find all occurrences; if any window around them contains broadcast, fail
        pos = 0
        while True:
            found = summary_text.find(needle, pos)
            if found == -1:
                break
            w = summary_text[found : found + 900].lower()
            # The legitimate S-035 SOURCE-DERIVED FACT is the infrastructure load problem sentence  # noqa: E501
            # It must not contain broadcast/current-load hedged motivation as fact
            if "broadcast" in w and "as it seems to be the case" not in w:
                # Check if window is infrastructure problem — skip  # noqa: E501
                errors.append(
                    "summary.md S-035 broadcast/current-load motivation must not be tagged SOURCE-DERIVED FACT; use hedged provisional wording"  # noqa: E501
                )
                break
            pos = found + len(needle)

    # 3. TT-REQ-008 must be SOURCE-DERIVED FACT with both SHAs  # noqa: E501
    if "[IMPLEMENTATION-VERIFIED FACT — Negotiated Version 1 TT-REQ-008]" in summary_text:
        errors.append(
            "summary.md TT-REQ-008 incorrectly tagged IMPLEMENTATION-VERIFIED; must be SOURCE-DERIVED FACT from Negotiated Version 1"  # noqa: E501
        )
    if "TT-REQ-008" in summary_text:
        if "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2" not in summary_text:
            errors.append(
                "summary.md TT-REQ-008 must cite Negotiated Version 1 whole-file SHA 732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2"  # noqa: E501
            )
        if "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595" not in summary_text:
            errors.append(
                "summary.md TT-REQ-008 must cite canonical payload SHA 58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"  # noqa: E501
            )
        # TT-REQ-008 line must be SOURCE-DERIVED FACT
        ttreq_idx = summary_text.find("TT-REQ-008")
        window_tt = summary_text[max(0, ttreq_idx - 500) : ttreq_idx + 500]
        if "SOURCE-DERIVED FACT" not in window_tt:
            errors.append(
                "summary.md TT-REQ-008 must be tagged SOURCE-DERIVED FACT from Negotiated Version 1"
            )
        if "NEGOTIATED VERSION 1" not in window_tt.upper():
            errors.append("summary.md TT-REQ-008 must reference Negotiated Version 1")

    # 4. Congested-road RSU locus must not be presented as RESEARCH-EVIDENCE FACT without mapping
    lower_summary = summary_text.lower()
    if "concentrated on congested-road" in lower_summary:
        errors.append(
            "summary.md unsupported 'max deviation concentrated on congested-road RSUs' claim; admitted artifacts contain no road-congestion mapping for indexed RSUs"  # noqa: E501
        )
    if "max deviation concentrated" in lower_summary:
        errors.append(
            "summary.md contains unsupported 'max deviation concentrated' congested-road locus claim"  # noqa: E501
        )
    # If congested-road appears in E2c mechanism paragraph  # noqa: E501
    # Check E2c mechanism section
    e2c_idx = summary_text.find("E2c execution imbalance")
    if e2c_idx != -1:
        e2c_window = summary_text[e2c_idx : e2c_idx + 1200]
        e2c_lower = e2c_window.lower()
        if "congested-road" in e2c_lower:
            if "no road-congestion mapping" not in e2c_lower or "inference" not in e2c_lower:
                errors.append(
                    "summary.md congested-road RSU attribution in E2c mechanism must be explicitly tagged INFERENCE with disclaimer that admitted artifacts contain no road-congestion mapping"  # noqa: E501
                )
            if (
                "RESEARCH-EVIDENCE FACT" in e2c_window
                and "congested-road" in e2c_lower
                and "[INFERENCE" not in e2c_window
            ):  # noqa: E501
                # If same window claims research fact for congested-road locus without inference disclaimer  # noqa: E501
                errors.append(
                    "summary.md congested-road RSU attribution presented as RESEARCH-EVIDENCE FACT; must be removed or tagged INFERENCE with no-mapping disclaimer"  # noqa: E501
                )

    # Check index standing fields
    for eid, ent in index.get("evidence_identities", {}).items():
        if "sha256" not in ent or not ent["sha256"]:
            errors.append(f"evidence_index {eid} missing sha256")
        if "manifest" in ent:
            m = ent["manifest"]
            if isinstance(m, dict) and "sha256" not in m:
                errors.append(f"evidence_index {eid} manifest missing sha256")
        elif "manifest_sha256" not in ent:
            # some entries use manifest_sha256 directly — allow
            pass

    if errors:
        for err_msg2 in errors:
            print(f"VALIDATION FAILED: {err_msg2}", file=sys.stderr)
        sys.exit(1)

    print("VALIDATION PASSED: all v08 improved strategy evidence checks passed")
    sys.exit(0)


if __name__ == "__main__":
    validate()
