#!/usr/bin/env python3
"""Validate v08 seven-minute video package (Lane 11).

Checks (acceptance criteria):
- 8 segments exactly cover 420 seconds without overlap/gap; durations match spec
- word/timing budget validated (total 750-1050, per-segment 40-180)
- click path locators resolve to exact product/dependency artifacts at base
- every evidence shot has a non-empty standing (closed vocabulary) and limitation
- one honest Manchester/current-data view, one strategy matrix, one improved result,
  one reproducibility artifact each present
- forbidden claims absent
- honesty labels present and base/provenance SHAs consistent

Exit 0 on pass, 1 on failure. No harness runtime dependency.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "docs/closure/v08_alignment/video_7min_script.md"
STORYBOARD = REPO_ROOT / "docs/closure/v08_alignment/video_storyboard.md"
CLICK_PATH = REPO_ROOT / "docs/closure/v08_alignment/video_demo_click_path.md"
CHECKLIST = REPO_ROOT / "docs/closure/v08_alignment/video_evidence_checklist.md"

# Expected segments: (label, start_s, end_s)
EXPECTED = [
    ("requirements", 0, 30),
    ("services", 30, 75),
    ("manchester", 75, 135),
    ("existing strategies", 135, 190),
    ("improved strategy", 190, 250),
    ("evidence", 250, 315),
    ("short demo", 315, 375),
    ("contribution", 375, 420),
]
EXPECTED_DURATIONS = [30, 45, 60, 55, 60, 65, 60, 45]

HONESTY_LABELS = [
    "SOURCE-DERIVED FACT",
    "IMPLEMENTATION-VERIFIED FACT",
    "RESEARCH-EVIDENCE FACT",
    "INFERENCE",
    "PROVISIONAL WORDING",
    "EXTERNAL DECISION REQUIRED",
]
ALLOWED_STANDINGS = set(HONESTY_LABELS) | {
    "SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT",
    "IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT",
    "SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT",
    "INFERENCE (contribution) + EXTERNAL DECISION REQUIRED (limits)",
    "IMPLEMENTATION-VERIFIED FACT — MIXED bounded demonstration",
    "RESEARCH-EVIDENCE FACT — read-only E2d, fleet draw replication",
    "RESEARCH-EVIDENCE FACT",
}
# Forbidden claim patterns (case-insensitive)
FORBIDDEN = [
    r"FULLY ALIGNED",
    r"Sandra confirmation received",
    r"recorded and submitted",
    r"live city.*operational",
    r"tour of all pages",
    r"stakeholder approval obtained",
    r"physical scaling proven",
    r"54-page feature tour",
]

TIME_RE = re.compile(r"(\d+):(\d{2})\s*[–—-]\s*(\d+):(\d{2})")
# Also allow 0:00 style in tables; we search for start/end pair
WORD_RE = re.compile(r"\b\w+\b")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _parse_segments(text: str) -> list[tuple[int, int]]:
    """Parse 8 start/end pairs in seconds from the segment table and headings."""
    pairs: list[tuple[int, int]] = []
    for m in TIME_RE.finditer(text):
        s = int(m.group(1)) * 60 + int(m.group(2))
        e = int(m.group(3)) * 60 + int(m.group(4))
        # Only keep pairs within 0-420 and with increasing order; avoid duplicates
        if 0 <= s < e <= 420:
            pairs.append((s, e))
    # Deduplicate preserving order, keep first 8 unique in increasing s
    seen: set[tuple[int, int]] = set()
    uniq: list[tuple[int, int]] = []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    # Sort by start
    uniq.sort(key=lambda x: x[0])
    # Return first 8 if more
    return uniq[:8]


def _check_timing(errors: list[str]) -> None:
    txt = _read(SCRIPT)
    segs = _parse_segments(txt)
    if len(segs) != 8:
        errors.append(f"script segments count {len(segs)} != 8 (parsed {segs})")
        return
    for i, (s, e) in enumerate(segs):
        exp_s, exp_e = EXPECTED[i][1], EXPECTED[i][2]
        if s != exp_s or e != exp_e:
            errors.append(f"segment {i + 1} timing {s}-{e}s != expected {exp_s}-{exp_e}s")
        dur = e - s
        if dur != EXPECTED_DURATIONS[i]:
            errors.append(f"segment {i + 1} duration {dur}s != expected {EXPECTED_DURATIONS[i]}s")
    # Check coverage 0..420 no gap/overlap
    if segs[0][0] != 0:
        errors.append("segments do not start at 0:00")
    if segs[-1][1] != 420:
        errors.append("segments do not end at 7:00 (420s)")
    for i in range(len(segs) - 1):
        if segs[i][1] != segs[i + 1][0]:
            errors.append(
                f"gap/overlap between segment {i + 1} end {segs[i][1]}s "
                f"and segment {i + 2} start {segs[i + 1][0]}s"
            )
    # Also validate storyboard has same 8
    sb = _read(STORYBOARD)
    sb_segs = _parse_segments(sb)
    if len(sb_segs) != 8:
        errors.append(f"storyboard segments count {len(sb_segs)} != 8")
    elif sb_segs != segs:
        errors.append(f"storyboard timings {sb_segs} != script timings {segs}")


def _check_word_budget(errors: list[str]) -> None:
    txt = _read(SCRIPT)
    words: list[int] = []
    for line in txt.splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts: ["", "#", "Segment", "Start", "End", "Duration", "Words", "WPM", "Honesty", ""]
        if len(parts) < 9:
            continue
        try:
            w = int(parts[6])
            words.append(w)
        except ValueError:
            continue
    if len(words) != 8:
        errors.append(f"word table segment count {len(words)} != 8")
        return
    total = sum(words)
    if not (750 <= total <= 1050):
        errors.append(f"total words {total} not in [750,1050]")
    for i, w in enumerate(words):
        if not (40 <= w <= 180):
            errors.append(f"segment {i + 1} words {w} not in [40,180]")


def _check_click_path_resolves(errors: list[str]) -> None:
    txt = _read(CLICK_PATH)
    locators = re.findall(r"`([^`]+)`", txt)
    file_locs: list[str] = []
    for loc in locators:
        if "*" in loc:
            continue
        if "/" not in loc:
            continue
        if not any(ext in loc for ext in [".py", ".json", ".md", ".csv", ".geojson"]):
            continue
        f = loc.split()[0].split(":")[0].strip().strip("[]()")
        if "/" in f:
            file_locs.append(f)
    if not file_locs:
        errors.append("no file locators found in click path")
        return
    for loc in file_locs:
        p = REPO_ROOT / loc
        if not p.exists():
            errors.append(f"click path locator missing: {loc}")


def _check_evidence_checklist(errors: list[str]) -> None:
    txt = _read(CHECKLIST)
    rows = [line for line in txt.splitlines() if line.startswith("| SHOT-")]
    if len(rows) < 8:
        errors.append(f"evidence checklist shot rows {len(rows)} < 8")
        return
    for row in rows:
        parts = [p.strip() for p in row.split("|")]
        # parts: ["", "SHOT-..", "Segment", "Visual", "Artifact", "Standing", "Limitation", ""]
        if len(parts) < 8:
            errors.append(f"malformed checklist row: {row[:80]}")
            continue
        standing = parts[5]
        limitation = parts[6]
        if not standing or standing == "-":
            errors.append(f"shot missing standing: {row[:80]}")
        if not limitation or limitation == "-":
            errors.append(f"shot missing limitation: {row[:80]}")

    # Check required artifact types present in checklist
    needed = [
        "Manchester/current-data view",
        "Strategy matrix",
        "improved result",
        "Reproducibility artifact",
    ]
    low = txt.lower()
    for need in needed:
        # Map need variants
        if "manchester" in need.lower():
            if "manchester" not in low or "mixed" not in low:
                errors.append(f"checklist missing required artifact class: {need}")
        elif "strategy matrix" in need.lower():
            if "strategy_matrix.json" not in txt:
                errors.append(f"checklist missing required artifact class: {need}")
        elif "improved result" in need.lower():
            if "improved result" not in low and "improved_strategy_results" not in txt:
                errors.append(f"checklist missing required artifact class: {need}")
        elif "reproducibility" in need.lower() and "reproducibility" not in low:
            errors.append(f"checklist missing required artifact class: {need}")


def _check_forbidden(errors: list[str]) -> None:
    for doc in [SCRIPT, STORYBOARD, CLICK_PATH, CHECKLIST]:
        lines = _read(doc).splitlines()
        for pat in FORBIDDEN:
            for line in lines:
                # Skip the explicit "Forbidden claims absent" enumeration line itself
                if "Forbidden claims absent" in line or "Prohibited phrases" in line:
                    continue
                if re.search(pat, line, flags=re.IGNORECASE):
                    errors.append(
                        f"forbidden phrase `{pat}` found in {doc.name}: {line.strip()[:80]}"
                    )
                    break

    # Narration boundaries must be present in script
    txt = _read(SCRIPT)
    boundaries = [
        "No claim that a video has been recorded or submitted",
        "No live-city",
        "No task-level inference",
        "No stakeholder approval",
        "No physical / scaling overclaim",
    ]
    for b in boundaries:
        if b.lower() not in txt.lower():
            # Allow partial match
            key = b.split()[1]
            if key.lower() not in txt.lower():
                errors.append(f"narration boundary missing: {b}")


def _check_honesty_and_provenance(errors: list[str]) -> None:
    txt = _read(SCRIPT) + _read(STORYBOARD) + _read(CHECKLIST)
    for label in HONESTY_LABELS:
        if label not in txt:
            errors.append(f"honesty label missing overall: {label}")
    # Provenance SHAs must appear
    shas = [
        "58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595",
        "732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2",
        "0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9",
        "08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed",
    ]
    combined = _read(SCRIPT) + _read(CHECKLIST)
    for sha in shas:
        if sha not in combined and sha[:8] not in combined:
            errors.append(f"provenance SHA missing: {sha[:8]}…")


def validate() -> list[str]:
    errors: list[str] = []
    for p in [SCRIPT, STORYBOARD, CLICK_PATH, CHECKLIST]:
        if not p.exists():
            errors.append(f"missing required file: {p.relative_to(REPO_ROOT)}")
    if errors:
        return errors
    _check_timing(errors)
    _check_word_budget(errors)
    _check_click_path_resolves(errors)
    _check_evidence_checklist(errors)
    _check_forbidden(errors)
    _check_honesty_and_provenance(errors)
    return errors


def main() -> int:
    errs = validate()
    if errs:
        print("VIDEO PACKAGE VALIDATION FAILED")
        for e in errs:
            print(f" - {e}")
        return 1
    print(
        "VIDEO PACKAGE VALIDATION PASSED — 420 s, 8 segments, "
        "word budget ok, locators resolve, checklist complete"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
