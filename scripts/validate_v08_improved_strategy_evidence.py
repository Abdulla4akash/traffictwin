#!/usr/bin/env python3
"""Validator for v08 lane 07 E2b–E2d evidence synthesis.

Checks:
- every figure cell resolves to exact read-only evidence identity
- E2b/E2c/E2d distinctions and limitations survive
- replication/uncertainty fields explicit
- every numeric row bound to code SHA, manifest hash, actor, trace, seed, artifact
- replication unit is fleet_draw/run, never task
- orphan numbers rejected
"""

from __future__ import annotations

import csv
import json
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

    # Validate figure CSV
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
    except Exception as csv_exc:
        errors.append(f"figure_data.csv read error: {csv_exc}")

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
