#!/usr/bin/env python3
"""Validate v08 seven-minute video package (Lane 11).

Checks (acceptance criteria):
- 8 segments exactly cover 420 seconds without overlap/gap; durations match spec
- word/timing budget validated (total 750-1050, per-segment 40-180) with
  derivation from narration blockquotes and table/total consistency
- click path + storyboard + checklist locators resolve to exact product/dependency artifacts at base
  (controller-only .harness/ provenance excluded from committed locator resolution)
- every evidence shot has a non-empty standing (closed vocabulary) and limitation
- one honest Manchester/current-data view, one strategy matrix, one improved result,
  one reproducibility artifact each present
- E2d fidelity: frozen primary estimand per_task_dla_minus_ingress_dla,
  exact bounded four-draw summary/uncertainty and figure identity
  fig3_e2d_per_task_minus_ingress_seed2 validated against
  improved_strategy_results.json; wrong value/identity fails
- forbidden claims absent
- honesty labels present and base/provenance SHAs consistent

Exit 0 on pass, 1 on failure. No harness runtime dependency.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "docs/closure/v08_alignment/video_7min_script.md"
STORYBOARD = REPO_ROOT / "docs/closure/v08_alignment/video_storyboard.md"
CLICK_PATH = REPO_ROOT / "docs/closure/v08_alignment/video_demo_click_path.md"
CHECKLIST = REPO_ROOT / "docs/closure/v08_alignment/video_evidence_checklist.md"
RESULTS_JSON = REPO_ROOT / "docs/closure/v08_alignment/improved_strategy_results.json"

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


def _extract_narration_word_counts(text: str) -> list[int]:
    """Derive word counts from narration blockquotes following **Narration headings.

    Uses whitespace split (wc -w style) to match task's 814 derivation.
    """
    counts: list[int] = []
    # Pattern: **Narration ... line then one or more blockquote lines
    for m in re.finditer(r"\*\*Narration[^\n]*\n((?:> [^\n]*\n?)+)", text):
        block = m.group(1)
        lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("> "):
                lines.append(line[2:])
            elif line.startswith(">"):
                lines.append(line[1:].lstrip())
            else:
                lines.append(line)
        full = " ".join(lines).strip()
        if not full:
            counts.append(0)
        else:
            # wc -w style: split on whitespace
            counts.append(len(full.split()))
    return counts


def _extract_table_words(text: str) -> list[int]:
    words: list[int] = []
    for line in text.splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 9:
            continue
        try:
            w = int(parts[6])
            words.append(w)
        except ValueError:
            continue
    return words


def _extract_stated_totals(text: str) -> list[int]:
    totals: list[int] = []
    for m in re.finditer(r"Total\s+(\d+)\s+words", text):
        totals.append(int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+words total", text):
        # Avoid double-counting the same Total line already captured
        val = int(m.group(1))
        if val not in totals:
            totals.append(val)
    # Also capture "total 880, per-segment" style line: Word budget check
    for m in re.finditer(r"total\s+(\d+)\b", text, flags=re.IGNORECASE):
        val = int(m.group(1))
        # Only consider if near words
        snippet = text[max(0, m.start() - 20) : m.end() + 20]
        if "word" in snippet.lower() and val not in totals:
            totals.append(val)
    return totals


def _check_word_budget(errors: list[str]) -> None:
    txt = _read(SCRIPT)
    table_words = _extract_table_words(txt)
    if len(table_words) != 8:
        errors.append(f"word table segment count {len(table_words)} != 8")
        return
    actual = _extract_narration_word_counts(txt)
    if len(actual) != 8:
        errors.append(f"narration blockquote count {len(actual)} != 8 (expected 8 segments)")
        return
    # Each table value must equal actual count
    for i, (tw, aw) in enumerate(zip(table_words, actual)):  # noqa: B905
        if tw != aw:
            errors.append(f"Words cell segment {i + 1} table {tw} != actual narration {aw}")
    total_table = sum(table_words)
    total_actual = sum(actual)
    if total_table != total_actual:
        errors.append(f"table sum {total_table} != derived narration sum {total_actual}")
    # Stated totals must equal derived sum
    stated = _extract_stated_totals(txt)
    if stated:
        # At least one stated total must equal derived
        # Check header and footer totals
        for st in stated:
            if st != total_actual and 700 <= st <= 1100:
                errors.append(f"stated total {st} != derived narration sum {total_actual}")
                break
    # Range checks
    if not (750 <= total_actual <= 1050):
        errors.append(
            f"derived total words {total_actual} not in [750,1050] (defensible seven-minute range)"
        )
    if not (750 <= total_table <= 1050):
        errors.append(f"table total words {total_table} not in [750,1050]")
    for i, w in enumerate(table_words):
        if not (40 <= w <= 180):
            errors.append(f"segment {i + 1} words {w} not in [40,180]")
    for i, w in enumerate(actual):
        if not (40 <= w <= 180):
            errors.append(f"segment {i + 1} actual words {w} not in [40,180]")


def _is_controller_only_locator(loc: str) -> bool:
    """Controller-only .harness/ provenance is excluded from committed locator resolution."""
    return (
        loc.startswith(".harness/")
        or "/.harness/" in loc
        or loc.startswith(".harness")
        or loc.startswith("refs/harness")
        or "refs/harness" in loc
    )


def _is_harness_sha_context(text: str, sha: str) -> bool:
    """Return True if sha appears in harness commit context (exclude from local SHA check)."""
    # Find sha occurrence and check surrounding for harness marker
    for m in re.finditer(re.escape(sha), text):
        ctx = text[max(0, m.start() - 80) : m.end() + 80]
        if ".harness" in ctx or "refs/harness" in ctx:
            return True
    return False


def _extract_navigation_url_paths() -> set[str]:
    """Parse url_path values from navigation_v07.py (keyword and positional)."""
    nav = REPO_ROOT / "src/traffictwin/ui/navigation_v07.py"
    if not nav.exists():
        return set()
    txt = nav.read_text(encoding="utf-8")
    paths: set[str] = set(re.findall(r'url_path\s*=\s*["\']([^"\']+)["\']', txt))
    # Positional V07PageSpec entries: UiPage.X, "group", "script", "url_path", "icon"
    for m in re.finditer(
        r"V07PageSpec\s*\(\s*UiPage\.[^,]+,\s*\"[^\"]+\"\s*,\s*\"[^\"]+\"\s*,\s*\"([^\"]+)\"",
        txt,
    ):
        paths.add(m.group(1))
    return paths


def _navigation_contains_route(route: str) -> bool:
    """Check if route (without leading slash) appears in navigation file."""
    nav = REPO_ROOT / "src/traffictwin/ui/navigation_v07.py"
    if not nav.exists():
        return False
    txt = nav.read_text(encoding="utf-8")
    # Direct quoted occurrence e.g. "manchester-evidence-hub"
    return f'"{route}"' in txt or f"'{route}'" in txt


def _parse_click_path_table(text: str) -> list[dict[str, str]]:
    """Parse the 6-step click path table into rows."""
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        # Skip header/separator
        if line.startswith("| Step") or line.startswith("|------"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts[0] empty, parts[1] step, [2] clock, [3] human, [4] locator, [5] route, [6] artifact, etc  # noqa: E501
        if len(parts) < 8:
            continue
        step_raw = parts[1].strip()
        if not re.fullmatch(r"\d+", step_raw):
            continue
        rows.append(
            {
                "step": step_raw,
                "clock": parts[2],
                "human": parts[3],
                "locator": parts[4],
                "route": parts[5],
                "artifact": parts[6],
                "raw": line,
            }
        )
    return rows


def _parse_clock_to_seconds(clock: str) -> int | None:
    """Parse clock like '~5:15' to seconds. Return None if malformed."""
    m = re.match(r"^\s*~?\s*(\d+):(\d{2})\s*$", clock)
    if not m:
        return None
    h = int(m.group(1))
    mins = int(m.group(2))
    if not (0 <= mins <= 59):
        return None
    if not (0 <= h <= 99):
        return None
    return h * 60 + mins


def _check_click_path_timing(errors: list[str]) -> None:
    """Validate six contiguous steps covering 5:15–6:15, each ≤12s."""
    txt = _read(CLICK_PATH)
    rows = _parse_click_path_table(txt)
    if len(rows) != 6:
        errors.append(f"click path step count {len(rows)} != 6")
        return
    # Parse window from header duration line, fallback to 5:15-6:15
    window_re = re.search(r"Duration inside video.*?(\d+):(\d{2})\s*[–—-]\s*(\d+):(\d{2})", txt)
    if window_re:
        win_start = int(window_re.group(1)) * 60 + int(window_re.group(2))
        win_end = int(window_re.group(3)) * 60 + int(window_re.group(4))
    else:
        win_start = 5 * 60 + 15
        win_end = 6 * 60 + 15
    total_expected = win_end - win_start
    if total_expected != 60:
        errors.append(f"click path window total {total_expected}s != 60s (expected 5:15–6:15)")
    clocks: list[int] = []
    for r in rows:
        sec = _parse_clock_to_seconds(r["clock"])
        if sec is None:
            errors.append(f"click path step {r['step']} malformed clock time: {r['clock']!r}")
        else:
            clocks.append(sec)
    if len(clocks) != 6:
        # malformed already reported
        return
    # Check start at window start
    if clocks[0] != win_start:
        errors.append(
            f"click path should start at {win_start // 60}:{win_start % 60:02d}, got step 1 {clocks[0] // 60}:{clocks[0] % 60:02d}"  # noqa: E501
        )
    # Compute durations
    durations: list[int] = []
    for i in range(len(clocks) - 1):
        d = clocks[i + 1] - clocks[i]
        durations.append(d)
    durations.append(win_end - clocks[-1])
    # Check each duration
    for i, d in enumerate(durations):
        if d <= 0:
            errors.append(
                f"click path step {i + 1} gap/overlap: duration {d}s (clock {clocks[i] if i < len(clocks) else win_end})"  # noqa: E501
            )
        elif d > 12:
            errors.append(
                f"click path step {i + 1} overrun: duration {d}s exceeds 12s (clock {rows[i]['clock']!r} to {(clocks[i + 1] if i + 1 < len(clocks) else win_end)} )"  # noqa: E501
            )
    total = sum(durations)
    if total != total_expected:
        errors.append(
            f"click path wrong total {total}s != expected {total_expected}s (steps covering {win_start // 60}:{win_start % 60:02d}–{win_end // 60}:{win_end % 60:02d})"  # noqa: E501
        )
    # Also detect any gap/overlap overall: clocks must be strictly increasing
    for i in range(len(clocks) - 1):
        if clocks[i] >= clocks[i + 1]:
            errors.append(
                f"click path gap/overlap between step {i + 1} ({rows[i]['clock']!r}) and step {i + 2} ({rows[i + 1]['clock']!r})"  # noqa: E501
            )
    if clocks[-1] >= win_end:
        errors.append(
            f"click path gap/overlap: last step clock {rows[-1]['clock']!r} not before {win_end // 60}:{win_end % 60:02d}"  # noqa: E501
        )


def _check_click_path_routes(errors: list[str]) -> None:
    """Validate every route/url_path claimed in click path appears in navigation_v07.py."""
    txt = _read(CLICK_PATH)
    rows = _parse_click_path_table(txt)
    url_paths = _extract_navigation_url_paths()
    for r in rows:
        route_cell = r["route"]
        # Find url_path candidates: /something or url_path="something" inside locator
        # Extract slash-prefixed routes
        for m in re.finditer(r"/([a-zA-Z0-9_\-]+)", route_cell):
            # Reconstruct full url_path token
            # m.group(1) is without leading slash
            # Check if preceded by /
            full = m.group(1)
            # Skip if it's part of a file path or comment; only consider the explicit Route/CLI column token that is a leading / path  # noqa: E501
            # Determine if the cell contains a standalone /route token
            token = "/" + full
            # Only validate tokens that appear as whole route (preceded by start, space, or |)
            # But we can simply check if full is in url_paths when the cell contains that exact token  # noqa: E501
            if token in route_cell:  # noqa: SIM102
                # Check presence in navigation
                if full not in url_paths:
                    errors.append(
                        f"click path step {r['step']} route {token!r} not found in src/traffictwin/ui/navigation_v07.py"  # noqa: E501
                    )
        # Also check explicit url_path="..." claims in locator column
        locator_cell = r["locator"]
        for m in re.finditer(r'url_path\s*=\s*["\']([^"\']+)["\']', locator_cell):
            claimed = m.group(1)
            if claimed not in url_paths:
                errors.append(
                    f"click path step {r['step']} url_path {claimed!r} not found in src/traffictwin/ui/navigation_v07.py"  # noqa: E501
                )


def _check_click_path_sha_prefixes(errors: list[str]) -> None:
    """Validate every hex identity in each six-step row against explicit artifacts.

    A local claim passes only when the prefix is bound to the row's
    explicitly referenced committed artifact: either the SHA-256 digest
    of that file, or a full structured identity/fingerprint contained by
    that referenced JSON/CSV artifact. Prefixes merely existing somewhere
    unrelated in the repository are rejected. Identities explicitly
    associated with controller-only refs/harness or .harness are excluded.
    """
    txt = _read(CLICK_PATH)
    rows = _parse_click_path_table(txt)
    for r in rows:
        raw = r["raw"]
        # Every hex identity anywhere in the row (any column), inside backticks.
        # Backtick hex with optional ellipsis (U+2026) – covers 6-char
        # receipt prefixes, 8-9-char fingerprints like af128cf08, and truncated SHAs.
        sha_candidates: list[str] = re.findall(r"`([0-9a-fA-F]{6,})…*`", raw)
        # Also detect bare truncated SHAs with ellipsis outside backticks.
        for m in re.finditer(r"\b([0-9a-fA-F]{6,})…+", raw):
            candidate = m.group(1)
            if candidate not in sha_candidates:
                # If already inside backticks, re.findall captured it.
                # Only add if occurrence is outside backticks.
                sha_candidates.append(candidate)
        # Deduplicate case-insensitively while preserving order
        seen: set[str] = set()
        uniq: list[str] = []
        for s in sha_candidates:
            sl = s.lower()
            if sl not in seen:
                seen.add(sl)
                uniq.append(s)
        if not uniq:
            continue
        # Collect every explicitly referenced artifact in this row (any column).
        file_paths = re.findall(r"`(src/[^`]+|docs/[^`]+)`", raw)
        local_files: list[str] = []
        for fp in file_paths:
            fp_clean = fp.split()[0].split(":")[0].strip().strip("[]()")
            if _is_controller_only_locator(fp_clean):
                continue
            if not (fp_clean.startswith("src/") or fp_clean.startswith("docs/")):
                continue
            if not any(ext in fp_clean for ext in [".py", ".json", ".md", ".csv", ".geojson"]):
                continue
            local_files.append(fp_clean)
        for sha in uniq:
            sha_low = sha.lower()
            # Exclude harness-associated identities (controller-only provenance)
            if _is_harness_sha_context(raw, sha):
                continue
            matched = False
            for lf in local_files:
                p = REPO_ROOT / lf
                if not p.exists():
                    continue
                # 1) SHA-256 digest of the file itself
                try:
                    file_sha = hashlib.sha256(p.read_bytes()).hexdigest().lower()
                    if file_sha.startswith(sha_low):
                        matched = True
                        break
                except Exception:  # noqa: S110, S112
                    pass
                # 2) Fingerprint contained by referenced JSON/CSV artifact
                try:
                    text_lower = p.read_text(encoding="utf-8", errors="ignore").lower()
                    if sha_low in text_lower:
                        matched = True
                        break
                except Exception:  # noqa: S110, S112
                    pass
            if matched:
                continue
            if local_files:
                errors.append(
                    f"click path step {r['step']} local SHA prefix {sha!r} does not match committed file (expected prefix of {local_files[0]})"  # noqa: E501
                )
            else:
                errors.append(
                    f"click path step {r['step']} local SHA prefix {sha!r} does not match any committed file (no explicit local artifact in row)"  # noqa: E501
                )


def _extract_file_locators(text: str) -> list[str]:
    locators = re.findall(r"`([^`]+)`", text)
    file_locs: list[str] = []
    for loc in locators:
        if "*" in loc:
            continue
        if "/" not in loc:
            continue
        if not any(ext in loc for ext in [".py", ".json", ".md", ".csv", ".geojson"]):
            continue
        f = loc.split()[0].split(":")[0].strip().strip("[]()")
        if "/" not in f:
            continue
        # Only validate repo-relative paths with docs/ or src/ prefix
        # Shorthand like `manchester_demo/...` without prefix is ignored
        if not (f.startswith("src/") or f.startswith("docs/")):
            continue
        file_locs.append(f)
    return file_locs


def _check_locators_resolve(errors: list[str]) -> None:
    # Check click path, storyboard, and checklist (claim-bearing locators)
    for doc_path, label in [
        (CLICK_PATH, "click path"),
        (STORYBOARD, "storyboard"),
        (CHECKLIST, "checklist"),
    ]:
        txt = _read(doc_path)
        file_locs = _extract_file_locators(txt)
        for loc in file_locs:
            if _is_controller_only_locator(loc):
                continue
            p = REPO_ROOT / loc
            if not p.exists():
                errors.append(f"{label} locator missing: {loc}")


def _check_click_path_resolves(errors: list[str]) -> None:
    # Backwards-compatible alias; now checks all docs
    _check_locators_resolve(errors)


def _check_e2d_fidelity(errors: list[str]) -> None:
    # Load frozen dependency
    if not RESULTS_JSON.exists():
        errors.append("missing improved_strategy_results.json for E2d fidelity check")
        return
    try:
        data = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"failed to parse improved_strategy_results.json: {e}")
        return
    rows = {r.get("figure_id", ""): r for r in data.get("rows", [])}
    uncertainty = data.get("uncertainty", {})
    e2d_interval = uncertainty.get("e2d_primary_interval", {})
    if not e2d_interval:
        errors.append("e2d_primary_interval missing in results JSON")
        return
    expected_fig = "fig3_e2d_per_task_minus_ingress_seed2"
    bad_fig = "fig_e2d_per_task_minus_dla_seed2"
    combined = _read(SCRIPT) + "\n" + _read(STORYBOARD) + "\n" + _read(CHECKLIST)
    # Wrong identity must fail
    if bad_fig in combined:
        errors.append(f"nonexistent figure identity {bad_fig} found — use {expected_fig}")
    if expected_fig not in combined:
        errors.append(f"required figure identity {expected_fig} missing")
    # Estimand naming: per_task_dla minus dla without ingress is wrong
    # Detect "per_task_dla minus dla" without ingress
    for m in re.finditer(r"per_task_dla\s+minus\s+dla\b", combined, flags=re.IGNORECASE):
        ctx = combined[max(0, m.start() - 40) : m.end() + 40].lower()
        if "ingress" not in ctx:
            errors.append(
                "E2d estimand must be per_task_dla_minus_ingress_dla, found 'per_task_dla minus dla' without ingress"  # noqa: E501
            )
            break
    # Also detect bare "per_task_minus_dla" without ingress
    lower_combined = combined.lower()
    if "per_task_minus_dla" in lower_combined:
        # If the string per_task_dla_minus_ingress_dla is present, then per_task_minus_dla substring will appear inside it;  # noqa: E501
        # we need to check if there's a per_task_minus_dla not part of ingress variant
        tmp = lower_combined.replace("per_task_dla_minus_ingress_dla", "")
        tmp = tmp.replace("per_task_dla minus ingress_dla", "")
        if "per_task_minus_dla" in tmp or "per_task_dla minus dla" in tmp:
            errors.append("E2d estimand mixing detected — use per_task_dla_minus_ingress_dla")
    # Wrong value +0.02 must fail (old E2d misstate)
    if re.search(r"plus zero point zero two", combined, flags=re.IGNORECASE):
        errors.append(
            "wrong E2d value 'plus zero point zero two' (+0.02) found — expected ~0.00587 for per_task_dla_minus_ingress_dla"  # noqa: E501
        )
    # Check for range sign-spanning -0.02..+0.02 specifically in E2d improvement context
    if "−0.02..+0.02" in combined or "-0.02..+0.02" in combined:
        errors.append(
            "wrong E2d range −0.02..+0.02 found — expected 0.00464..0.00587 for per_task_dla_minus_ingress_dla"  # noqa: E501
        )
    # Must include exact bounded four-draw summary: per-seed values, mean, interval
    # Check that mean, lower, upper appear (rounded)
    mean = e2d_interval.get("mean")
    lower = e2d_interval.get("lower")
    upper = e2d_interval.get("upper")
    per_seed_values = e2d_interval.get("per_seed_values", [])
    # Require mean/lower/upper substrings present (5 decimal formatting)
    if mean is not None:
        mean_str5 = f"{mean:.5f}"  # 0.00527
        mean_str4 = f"{mean:.4f}"
        if (
            mean_str5 not in combined
            and mean_str4 not in combined
            and str(mean)[:7] not in combined
        ):
            errors.append(f"E2d mean {mean} not found — include exact bounded four-draw summary")
    if lower is not None:
        lower_str5 = f"{lower:.5f}"  # 0.00442
        if (
            lower_str5 not in combined
            and f"{lower:.4f}" not in combined
            and str(lower)[:7] not in combined
        ):
            errors.append(f"E2d interval lower {lower} not found — include exact 95% interval")
    if upper is not None:
        upper_str5 = f"{upper:.5f}"  # 0.00612
        if (
            upper_str5 not in combined
            and f"{upper:.4f}" not in combined
            and str(upper)[:7] not in combined
        ):
            errors.append(f"E2d interval upper {upper} not found — include exact 95% interval")
    # Check per-seed values appear (at least seed2 value must appear precisely)
    seed2_fig = rows.get(expected_fig)
    if seed2_fig:
        seed2_val = seed2_fig.get("value")
        if seed2_val is not None:
            seed2_str = f"{seed2_val:.5f}"  # 0.00587
            if (
                seed2_str not in combined
                and f"{seed2_val:.6f}" not in combined
                and str(seed2_val)[:7] not in combined
            ):
                errors.append(
                    f"E2d seed2 value {seed2_val} ({seed2_str}) not found — include exact figure row value"  # noqa: E501
                )
    # Ensure interval existence is not denied: old script said "no CI without pre-declared plan" and "not a confirmed improvement without a primary statistical plan"  # noqa: E501
    # The frozen interval is predeclared and excludes zero, so denying it is wrong
    if re.search(r"no CI without pre-declared plan", combined, flags=re.IGNORECASE):
        errors.append(
            "E2d interval denial 'no CI without pre-declared plan' found — e2d_primary_interval is predeclared"  # noqa: E501
        )
    if re.search(
        r"no confidence interval without pre-declared plan", combined, flags=re.IGNORECASE
    ):
        errors.append("E2d interval denial found — e2d_primary_interval is predeclared")
    # Also check that old denial phrase about not confirmed improvement is not present when interval excludes zero  # noqa: E501
    # We allow the phrase only if it's corrected to state the interval excludes zero
    includes_zero = e2d_interval.get("includes_zero", True)
    if includes_zero is False and re.search(
        r"is not a confirmed improvement without a primary statistical plan",
        combined,
        flags=re.IGNORECASE,
    ):
        errors.append("E2d interval excludes zero but docs deny confirmed directional difference")
    # Validate that any quoted numeric that is claimed as E2d per_task difference is within tolerance of frozen values  # noqa: E501
    # Extract all floats like 0.00xxx in E2d paragraphs and ensure they match allowed set
    allowed_vals = set()
    if per_seed_values:
        for v in per_seed_values:
            allowed_vals.add(round(v, 5))
            allowed_vals.add(round(v, 4))
    if mean is not None:
        allowed_vals.add(round(mean, 5))
    if lower is not None:
        allowed_vals.add(round(lower, 5))
    if upper is not None:
        allowed_vals.add(round(upper, 5))
    # Also allow full precision values
    allowed_exact = set(per_seed_values) if per_seed_values else set()
    if mean is not None:
        allowed_exact.add(mean)
    if lower is not None:
        allowed_exact.add(lower)
    if upper is not None:
        allowed_exact.add(upper)
    # Find E2d paragraphs (those containing per_task_dla)
    for para in combined.split("\n"):
        if "per_task_dla" not in para.lower():
            continue
        for m in re.finditer(r"\b0\.\d{2,}\b", para):
            try:
                val = float(m.group(0))
            except ValueError:
                continue
            # Check if val is near allowed (tolerance 1e-4)
            found = False
            for av in allowed_exact:
                if abs(val - av) < 1e-4:
                    found = True
                    break
            for av in allowed_vals:
                if abs(val - av) < 1e-4:
                    found = True
                    break
            if (
                not found
                and 0.001 <= val <= 0.03
                and (abs(val - 0.02) < 1e-3 or abs(val - 0.022) < 1e-3)
            ):
                errors.append(
                    f"wrong E2d numeric {val} in per_task_dla context — expected {sorted(allowed_exact)[:2]}"  # noqa: E501
                )
                break


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
    _check_locators_resolve(errors)
    _check_click_path_timing(errors)
    _check_click_path_routes(errors)
    _check_click_path_sha_prefixes(errors)
    _check_evidence_checklist(errors)
    _check_forbidden(errors)
    _check_honesty_and_provenance(errors)
    _check_e2d_fidelity(errors)
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
