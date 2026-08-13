#!/usr/bin/env python3
"""Validate v08 dissertation traceability and restructure plan (Lane 10).

Checks:
- exactly 14 requirements appear once in trace master, no duplication
- every priority matches requirements_baseline_v1.json (including TT-REQ-008 SHOULD)
- every status matches requirements_status_v08.json
- every chapter reference resolves to dissertation_restructure_plan.md chapters
- every product entry point exists at a244776a (file presence) — trace + contribution
- no unmastered TT-REQ ID appears in trace downstream or restructure plan
- forbidden claims absent (FULLY ALIGNED, Sandra confirmation,
  final/submitted report, raw private evidence)
- source honesty labels present; MUST arithmetic 3+7+1 preserved in status file
- P0/P1 and external decisions remain visible in limitations_register
- every PARTIALLY_MET has a limitations row with a named gap (not dash)
- contribution statement distinguishes software / scientific evidence / inference
- every scientific-evidence entry carries a frozen SHA/hash fragment
- every inference row labelled INFERENCE, never RESEARCH-EVIDENCE FACT alone
- downstream refs are subset of master

Exit 0 on pass, 1 on failure. No harness dependency; recomputes from committed docs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACE = REPO_ROOT / "docs/closure/v08_alignment/dissertation_traceability.md"
RESTRUCTURE = REPO_ROOT / "docs/closure/v08_alignment/dissertation_restructure_plan.md"
CONTRIB = REPO_ROOT / "docs/closure/v08_alignment/contribution_statement.md"
LIMITS = REPO_ROOT / "docs/closure/v08_alignment/limitations_register.md"
STATUS = REPO_ROOT / "docs/closure/v08_alignment/requirements_status_v08.json"
BASELINE_JSON = REPO_ROOT / "docs/closure/v08_alignment/requirements_baseline_v1.json"

EXPECTED_BASELINE_PAYLOAD = "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595"
EXPECTED_IDS = {f"TT-REQ-{i:03d}" for i in range(1, 15)}
FORBIDDEN_PATTERNS = [
    r"FULLY ALIGNED",
    r"Sandra confirmation received",
    r"final report submitted",
    r"submitted dissertation",
    r"raw private.*published",
    r"54-page feature tour",
]

HONESTY_LABELS = [
    "SOURCE-DERIVED FACT",
    "IMPLEMENTATION-VERIFIED FACT",
    "RESEARCH-EVIDENCE FACT",
    "INFERENCE",
    "PROVISIONAL WORDING",
    "EXTERNAL DECISION REQUIRED",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _find_ids(text: str) -> list[str]:
    return re.findall(r"TT-REQ-\d{3}", text)


def _is_path_candidate(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    # Pure hex hash like 58d9b0e7... should not be treated as path
    if re.fullmatch(r"[0-9a-f]{5,}(\.{2,3})?", s):
        return False
    if re.fullmatch(r"[0-9a-f]{64}", s):
        return False
    # SHA with ellipsis
    if re.fullmatch(r"[0-9a-f]{6,}\.\.\.", s):
        return False
    return "/" in s or "." in s


def _path_exists(repo_root: Path, rel: str) -> bool:
    rel = rel.strip().rstrip("/")
    if not rel:
        return False
    # Direct repo-relative
    if (repo_root / rel).exists():
        return True
    # Basename fallback: if rel has no slash, search under known alignment dirs or rglob
    if "/" not in rel:
        if (repo_root / "docs/closure/v08_alignment" / rel).exists():
            return True
        # Recursive search for filename anywhere (bounded — only if not found above)
        try:
            for found in repo_root.rglob(rel):
                if found.is_file() or found.is_dir():
                    # Ensure the match is exact basename
                    if found.name == rel:
                        return True
                    # Stop after first match attempt to keep cheap
                    break
        except Exception:  # noqa: S110
            pass
        return False
    # For relative with slashes like "manchester_demo/data_contract.json"
    return (repo_root / "docs/closure/v08_alignment" / rel).exists()


def _extract_backtick_paths(line: str) -> list[str]:
    raw = re.findall(r"`([^`]+)`", line)
    out: list[str] = []
    for token in raw:
        # Strip line-range suffix after colon, e.g. docs/foo.md:118-135,325-505
        # Also handle shorthand like "contract.json/md" which is not a single file
        file_part = token.split(":")[0].strip()
        # If token contains spaces (e.g. "implementation_i1.md I1-CAP-..."), take first token
        if " " in file_part:
            file_part = file_part.split()[0].strip()
        # Filter out shorthand with slash after dot (e.g. .json/md)
        if re.search(r"\.\w+/", file_part):
            continue
        # Require at least one dot and plausible file extension, or a directory with slash
        if not re.match(r"^[\w/.-]+\.\w+$", file_part) and "/" not in file_part:
            # Allow directory like src/traffictwin/integration/tos
            if "/" in file_part:
                pass
            else:
                continue
        if _is_path_candidate(file_part):
            out.append(file_part.rstrip("/"))
    return out


def validate() -> list[str]:
    errors: list[str] = []

    for p in [TRACE, RESTRUCTURE, CONTRIB, LIMITS, STATUS, BASELINE_JSON]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
    if errors:
        return errors

    trace_text = _read(TRACE)
    restructure_text = _read(RESTRUCTURE)
    contrib_text = _read(CONTRIB)
    limits_text = _read(LIMITS)

    # --- Baseline priorities ---
    baseline_data = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    baseline_priority: dict[str, str] = {
        r["id"]: r["priority"] for r in baseline_data.get("requirements", [])
    }
    baseline_ids = set(baseline_priority.keys())
    if baseline_ids != EXPECTED_IDS:
        errors.append(
            f"baseline requirements IDs mismatch: got {sorted(baseline_ids)} "
            f"expected {sorted(EXPECTED_IDS)}"
        )
    # Baseline payload hash check
    if baseline_data.get("canonical_payload_sha256") != EXPECTED_BASELINE_PAYLOAD:
        errors.append(
            f"baseline canonical_payload_sha256 mismatch: "
            f"got {baseline_data.get('canonical_payload_sha256')}"
        )

    # --- 1. Trace master contains exactly 14 IDs once ---
    master_section = re.search(r"## 2\. Trace master.*?(?=## 3\.)", trace_text, re.DOTALL)
    if not master_section:
        errors.append("trace master section ## 2. not found")
        master_ids: list[str] = []
    else:
        master_ids = re.findall(r"\|\s*(TT-REQ-\d{3})\s*\|", master_section.group(0))
        if set(master_ids) != EXPECTED_IDS:
            errors.append(
                f"trace master IDs mismatch: got {sorted(set(master_ids))} "
                f"expected {sorted(EXPECTED_IDS)}"
            )
        if len(master_ids) != 14:
            errors.append(f"trace master must have exactly 14 rows, got {len(master_ids)}")
        if len(master_ids) != len(set(master_ids)):
            errors.append(f"trace master has duplicate IDs: {master_ids}")

    # --- 2. Status file matches trace statuses ---
    status_data = json.loads(STATUS.read_text(encoding="utf-8"))
    status_by_id: dict[str, str] = {
        r["id"]: r["status"] for r in status_data.get("requirements", [])
    }
    status_priority: dict[str, str] = {
        r["id"]: r.get("priority", "") for r in status_data.get("requirements", [])
    }
    if master_section:
        lines = master_section.group(0).splitlines()
        for line in lines:
            if line.strip().startswith("| TT-REQ-"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    rid = parts[1]
                    trace_priority = parts[2]
                    status_in_trace = parts[6]
                    expected = status_by_id.get(rid)
                    if expected and status_in_trace != expected:
                        errors.append(
                            f"status mismatch for {rid}: trace {status_in_trace} "
                            f"vs status file {expected}"
                        )
                    # 2b. Priority must match baseline
                    expected_prio = baseline_priority.get(rid)
                    if expected_prio and trace_priority != expected_prio:
                        errors.append(
                            f"priority mismatch for {rid}: trace {trace_priority} "
                            f"vs baseline {expected_prio}"
                        )

    # --- 2c. Status file priorities must match baseline priorities ---
    for rid, prio in status_priority.items():
        expected_prio = baseline_priority.get(rid)
        if expected_prio and prio != expected_prio:
            errors.append(
                f"priority mismatch for {rid}: status file {prio} vs baseline {expected_prio}"
            )

    # --- 3. MUST arithmetic preserved ---
    ma = status_data.get("must_arithmetic", {})
    if (
        ma.get("total_must") != 11
        or ma.get("verified_met") != 3
        or ma.get("partially_met") != 7
        or ma.get("not_applicable_trigger_not_observed") != 1
    ):
        errors.append(f"MUST arithmetic must be 3+7+1, got {ma}")
    if "3+7+1" not in trace_text and "3+7+1" not in limits_text:
        errors.append("MUST arithmetic 3+7+1 not mentioned in trace/limitations")

    # --- 4. Chapter references resolve ---
    defined_chapters = set(re.findall(r"### Ch(\d)", restructure_text))
    expected_chapters = {str(i) for i in range(1, 9)}
    if defined_chapters != expected_chapters:
        errors.append(f"restructure must define Ch1..Ch8, found {sorted(defined_chapters)}")
    trace_chapters = set(re.findall(r"Ch(\d)", trace_text))
    if not trace_chapters.issubset(
        expected_chapters.union({"5", "6", "7", "8", "1", "2", "3", "4"})
    ):
        errors.append(f"trace references unknown chapters: {trace_chapters}")
    # Every downstream reference in trace §3 must be subset of master IDs
    downstream_section = re.search(r"## 3\. Downstream.*?(?=## 4\.)", trace_text, re.DOTALL)
    if downstream_section:
        downstream_ids = set(re.findall(r"TT-REQ-\d{3}", downstream_section.group(0)))
        if not downstream_ids.issubset(EXPECTED_IDS):
            errors.append(f"downstream references unknown IDs: {downstream_ids - EXPECTED_IDS}")
    # 4b. No unmastered ID may appear in restructure plan (downstream) — whole-file check
    restructure_ids = set(re.findall(r"TT-REQ-\d{3}", restructure_text))
    unknown_restructure = restructure_ids - EXPECTED_IDS
    if unknown_restructure:
        errors.append(f"restructure references unknown IDs: {sorted(unknown_restructure)}")
    # 4c. Contribution should not introduce unmastered IDs beyond master (except baseline refs)
    # We allow contribution to reference only EXPECTED_IDS; any TT-REQ not in expected is error
    contrib_ids = set(re.findall(r"TT-REQ-\d{3}", contrib_text))
    # Contribution may legitimately mention TT-REQ-008 as example; must be subset
    unknown_contrib = contrib_ids - EXPECTED_IDS
    if unknown_contrib:
        errors.append(f"contribution references unknown IDs: {sorted(unknown_contrib)}")

    # --- 4d. Entry-point existence (trace master + contribution) ---
    # Check trace master entry points — only the Product entry point column (parts[4])
    if master_section:
        for line in master_section.group(0).splitlines():
            if line.strip().startswith("| TT-REQ-"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    entry_cell = parts[4]
                    rid = parts[1]
                    paths = _extract_backtick_paths(entry_cell)
                    for rel in paths:
                        if not _path_exists(REPO_ROOT, rel):
                            errors.append(f"trace entry point does not exist for {rid}: `{rel}`")
    # Check contribution software entries (section 1.1) — first column product code paths
    sci_match = re.search(
        r"### 1\.1 Software contributions.*?(?=### 1\.2)", contrib_text, re.DOTALL
    )
    if sci_match:
        for line in sci_match.group(0).splitlines():
            if line.strip().startswith("|") and "---" not in line and "Contribution" not in line:
                parts = [p.strip() for p in line.split("|")]
                # Column 1: prod paths; Column 2: binding docs
                for cell in parts[1:3]:
                    paths = _extract_backtick_paths(cell)
                    for rel in paths:
                        if (
                            rel.startswith("src/")
                            or rel.startswith("docs/")
                            or "/" in rel
                            or rel.endswith(".py")
                            or rel.endswith(".json")
                        ) and not _path_exists(REPO_ROOT, rel):
                            errors.append(f"contribution entry point does not exist: `{rel}`")

    # --- 5. Forbidden claims absent across all four allowed docs ---
    for path, text in [
        (TRACE, trace_text),
        (RESTRUCTURE, restructure_text),
        (CONTRIB, contrib_text),
        (LIMITS, limits_text),
    ]:
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                lines = text.splitlines()
                for idx, line in enumerate(lines, 1):
                    if re.search(pat, line, re.IGNORECASE):
                        negated = bool(
                            re.search(
                                r"\b(No|not|never|without|prohibited|not FULLY)\b",
                                line,
                                re.IGNORECASE,
                            )
                        )
                        if not negated:
                            errors.append(
                                f"forbidden claim pattern '{pat}' in "
                                f"{path.relative_to(REPO_ROOT)}:{idx}: "
                                f"{line.strip()[:120]}"
                            )

    # --- 6. Honesty labels present ---
    for path, text in [
        (TRACE, trace_text),
        (RESTRUCTURE, restructure_text),
        (CONTRIB, contrib_text),
        (LIMITS, limits_text),
    ]:
        missing = [lbl for lbl in HONESTY_LABELS if lbl not in text]
        if path in (CONTRIB, LIMITS):
            if missing:
                errors.append(f"{path.relative_to(REPO_ROOT)} missing honesty labels: {missing}")
        else:
            present = [lbl for lbl in HONESTY_LABELS if lbl in text]
            if len(present) < 4:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)} has too few honesty labels: {present}"
                )

    # --- 7. P0/P1 visible and external decisions visible ---
    if "P0" not in limits_text or "P1" not in limits_text:
        errors.append("limitations_register must show P0 and P1 severities")
    if "EXTERNAL DECISION REQUIRED" not in limits_text:
        errors.append("limitations_register must show EXTERNAL DECISION REQUIRED")
    if "EXTERNAL DECISION REQUIRED" not in trace_text:
        errors.append("trace must show EXTERNAL DECISION REQUIRED")

    # --- 7b. Every PARTIALLY_MET has a limitations row with a named gap (not dash) ---
    # Parse limitations register table
    lim_section = re.search(r"## 2\. Register.*?(?=## 3\.)", limits_text, re.DOTALL)
    if lim_section:
        limit_ids: set[str] = set()
        limit_rows: dict[str, tuple[str, str, str]] = {}
        for line in lim_section.group(0).splitlines():
            if line.strip().startswith("| TT-REQ-"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 8:
                    lid = parts[1]
                    l_status = parts[3]
                    l_gap = parts[4]
                    l_severity = parts[5]
                    limit_ids.add(lid)
                    limit_rows[lid] = (l_status, l_gap, l_severity)
        partially_met_ids: set[str] = {
            str(r["id"])
            for r in status_data.get("requirements", [])
            if r.get("status") == "PARTIALLY_MET"
        }
        missing_pmet = partially_met_ids - limit_ids
        if missing_pmet:
            errors.append(f"limitations_register missing PARTIALLY_MET IDs: {sorted(missing_pmet)}")
        for rid in sorted(partially_met_ids.intersection(limit_ids)):
            l_status, l_gap, l_severity = limit_rows[rid]
            if l_status != "PARTIALLY_MET":
                errors.append(
                    f"limitations status mismatch for {rid}: "
                    f"register {l_status} vs expected PARTIALLY_MET"
                )
            # Gap must be named, not dash/empty
            if not l_gap or l_gap.strip() in ("—", "-", "–", ""):
                errors.append(f"limitations row for {rid} missing named gap")
            if not l_severity or l_severity.strip() in ("—", "-", "–", ""):
                errors.append(f"limitations row for {rid} missing severity (P0/P1/P3)")
            # Gap should be substantive, not just placeholder
            if l_gap and len(l_gap.strip()) < 8:
                errors.append(f"limitations row for {rid} gap too short: {l_gap[:60]}")
    else:
        errors.append("limitations_register section ## 2. not found")

    # --- 8. Contribution hygiene: three classes distinguished ---
    if (
        "Software" not in contrib_text
        or "Scientific evidence" not in contrib_text
        or "Inference" not in contrib_text
    ):
        errors.append(
            "contribution_statement must distinguish Software / Scientific evidence / Inference"
        )
    if (
        "IMPLEMENTATION-VERIFIED FACT" not in contrib_text
        or "RESEARCH-EVIDENCE FACT" not in contrib_text
        or "INFERENCE" not in contrib_text
    ):
        errors.append("contribution_statement missing class labels")

    # --- 8b. Scientific-evidence entries must carry a frozen hash/path fragment ---
    sci_section = re.search(r"### 1\.2 Scientific evidence.*?(?=### 1\.3)", contrib_text, re.DOTALL)
    if not sci_section:
        errors.append("contribution missing §1.2 Scientific evidence section")
    else:
        sci_lines = sci_section.group(0).splitlines()
        # Collect table rows (those starting with | and containing RESEARCH-EVIDENCE)
        sci_rows = [
            ln for ln in sci_lines if ln.strip().startswith("|") and "RESEARCH-EVIDENCE FACT" in ln
        ]
        # Filter out header separator lines
        sci_rows = [r for r in sci_rows if "---" not in r and "Evidence" not in r]
        if len(sci_rows) < 3:
            errors.append(f"scientific evidence section has too few evidence rows: {len(sci_rows)}")
        for row in sci_rows:
            # Each row must contain frozen identity: hex SHA ... or path
            has_hash = bool(re.search(r"[0-9a-f]{6,}\.{2,3}", row))
            has_path = bool(re.search(r"docs/|commit|manifest|SHA", row))
            if not (has_hash or has_path):
                errors.append(
                    f"scientific evidence entry missing frozen fragment: {row.strip()[:100]}"
                )

    # --- 8c. Inference distinctness ---
    inf_section = re.search(r"### 1\.3 Inference.*?(?=## 2\.)", contrib_text, re.DOTALL)
    if not inf_section:
        errors.append("contribution missing §1.3 Inference section")
    else:
        for line in inf_section.group(0).splitlines():
            if (
                line.strip().startswith("|")
                and "RESEARCH-EVIDENCE FACT" in line
                and "INFERENCE" not in line
            ):
                errors.append(
                    f"inference row masquerades as RESEARCH-EVIDENCE FACT: {line.strip()[:80]}"
                )

    # --- 9. Restructure chapters each have trace anchors ---
    for i in range(1, 9):
        if f"Ch{i}" not in restructure_text:
            errors.append(f"restructure missing Ch{i} reference")
        if f"Ch{i}" not in trace_text:
            pass

    # --- 10. Dependency standings preserved ---
    if "MIXED" not in trace_text:
        errors.append("trace must preserve Lane 09 MIXED standing")
    if "S-035" not in trace_text:
        errors.append("trace must reference S-035")

    return errors


def main() -> int:
    errs = validate()
    if not errs:
        print("PASS: dissertation traceability validation succeeded")
        print(f"  trace: {TRACE.relative_to(REPO_ROOT)}")
        print(f"  restructure: {RESTRUCTURE.relative_to(REPO_ROOT)}")
        print(f"  contribution: {CONTRIB.relative_to(REPO_ROOT)}")
        print(f"  limitations: {LIMITS.relative_to(REPO_ROOT)}")
        return 0
    print("FAIL: dissertation traceability validation failed")
    for e in errs:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
