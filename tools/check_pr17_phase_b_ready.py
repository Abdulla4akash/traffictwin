#!/usr/bin/env python3
"""
Phase-B readiness check for PR #17 — merge-style-agnostic.

Gate A: GitHub says PR #13 was actually merged (mergedAt != null).
Gate B: live `origin/main` (or supplied --main-path) contains the reviewed
        PR #13 product contract (file existence + content).

Result states:
  BLOCKED_PR13_OPEN          mergedAt is null -> no Phase B
  BLOCKED_CONTENT_MISMATCH   merged but content contract not satisfied
  READY_FOR_PHASE_B          both gates pass

This script is READ-ONLY, does not modify files, does not run SUMO/VEC.

Usage:
  python tools/check_pr17_phase_b_ready.py --pr13-merged-at 2026-08-09T12:00:00Z
  python tools/check_pr17_phase_b_ready.py --pr13-merged-at null --main-path /tmp/main
  # or let it query gh (if available):
  python tools/check_pr17_phase_b_ready.py --query-gh

Exit codes: 0 for READY, 1 for BLOCKED_PR13_OPEN, 2 for BLOCKED_CONTENT_MISMATCH
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

# Expected PR #13 contract — derived from live PR #13 head 2d7e85f
EXPECTED_FILES = [
    "src/traffictwin/ui/portfolio_explorer.py",
    "src/traffictwin/ui/pages/portfolio_explorer.py",
    "src/traffictwin/ui/app_pages/portfolio_explorer.py",
]

EXPECTED_LABELS = "src/traffictwin/ui/labels.py"
EXPECTED_NAV_V07 = "src/traffictwin/ui/navigation_v07.py"
EXPECTED_NAV = "src/traffictwin/ui/navigation.py"

# Challenge seed contract
EXPECTED_CHALLENGE_IDS = [
    "CH-01-arena-surge",
    "CH-02-lane-closure-corridor",
    "CH-03-t1-heavy-weak-fleet",
    "CH-04-rsu-waiting-room-squeeze",
    "CH-05-load-aware-forwarding",
    "CH-06-stale-state-scheduling",
    "CH-07-scaling-strategy",
]


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


def check_content_gate(main_path: pathlib.Path) -> tuple[bool, list[str]]:
    """Check Gate B: does main_path contain PR #13 product contract?"""
    reasons: list[str] = []

    # 1. Expected files exist
    for rel in EXPECTED_FILES:
        p = main_path / rel
        if not p.is_file():
            reasons.append(f"missing file {rel}")

    # 2. labels.py contains PORTFOLIO_EXPLORER
    labels = main_path / EXPECTED_LABELS
    if labels.is_file():
        txt = _read(labels)
        if "PORTFOLIO_EXPLORER" not in txt:
            reasons.append("labels.py missing PORTFOLIO_EXPLORER")
        # exactly once for page contract (allow 1 or more but check at least once)
        cnt = txt.count("PORTFOLIO_EXPLORER")
        if cnt < 1:
            reasons.append(f"labels.py PORTFOLIO_EXPLORER count {cnt} <1")
    else:
        reasons.append(f"missing {EXPECTED_LABELS}")

    # 3. navigation_v07.py contains PORTFOLIO_EXPLORER
    nav_v07 = main_path / EXPECTED_NAV_V07
    if nav_v07.is_file():
        txt = _read(nav_v07)
        if "PORTFOLIO_EXPLORER" not in txt:
            reasons.append("navigation_v07.py missing PORTFOLIO_EXPLORER")
        # should appear at least once
        if txt.count("PORTFOLIO_EXPLORER") < 1:
            reasons.append("navigation_v07.py PORTFOLIO_EXPLORER count <1")
    else:
        reasons.append(f"missing {EXPECTED_NAV_V07}")

    # 4. navigation.py contains portfolio explorer registration
    nav = main_path / EXPECTED_NAV
    if nav.is_file():
        txt = _read(nav)
        # Look for portfolio string (lowercase) - at least one
        if "portfolio" not in txt.lower():
            reasons.append("navigation.py missing portfolio reference")
    else:
        reasons.append(f"missing {EXPECTED_NAV}")

    # 5. Challenge seed library contracts
    port = main_path / "src/traffictwin/ui/portfolio_explorer.py"
    if port.is_file():
        txt = _read(port)
        # Check ChallengeSeedDefinition and SELECTOR_CONSUMED_FIELDS exist
        if "class ChallengeSeedDefinition" not in txt:
            reasons.append("portfolio_explorer.py missing ChallengeSeedDefinition")
        if "SELECTOR_CONSUMED_FIELDS" not in txt:
            reasons.append("portfolio_explorer.py missing SELECTOR_CONSUMED_FIELDS")
        if "get_challenge_seed_library" not in txt:
            reasons.append("portfolio_explorer.py missing get_challenge_seed_library")
        if "get_challenge_seed" not in txt:
            reasons.append("portfolio_explorer.py missing get_challenge_seed")
        # Check fingerprint semantics: must contain challenge_target_surfaces and selector_input_features  # noqa: E501
        if "challenge_target_surfaces" not in txt:
            reasons.append(
                "portfolio_explorer.py missing fingerprint binding challenge_target_surfaces"
            )
        if "selector_input_features" not in txt:
            reasons.append(
                "portfolio_explorer.py missing fingerprint binding selector_input_features"
            )
        # Check no generic ScenarioSeed→run executor (should NOT contain def run_challenge etc)
        # We check for forbidden generic executor strings
        forbidden = ["def run_challenge", "def execute_challenge", "def run_scenario_seed"]
        for f in forbidden:
            if f in txt:
                reasons.append(f"portfolio_explorer.py contains forbidden generic executor {f!r}")
        # Check all seven challenge IDs present
        for cid in EXPECTED_CHALLENGE_IDS:
            if cid not in txt:
                reasons.append(f"portfolio_explorer.py missing challenge seed {cid}")
        # Check all seven remain REPRESENTABLE_ONLY
        # Count occurrences of status=ChallengeExecutionStatus.REPRESENTABLE_ONLY
        cnt_repr = txt.count("REPRESENTABLE_ONLY")
        # There should be at least 7 (one per seed) + definitions; we expect exactly 7 seeds + class default = 8 occurrences  # noqa: E501
        # Safer: ensure not 0 and ensure no other status like EXECUTABLE for seeds
        # Check that no seed has status EXECUTABLE or NOT_YET_EXECUTABLE (should be only REPRESENTABLE_ONLY for seeds)  # noqa: E501
        # Look for ChallengeSeedDefinition blocks with status != REPRESENTABLE_ONLY
        # Simple: if "EXECUTABLE" appears outside StrEnum definition, it's suspicious.
        # The StrEnum itself contains EXECUTABLE, so we check for status=.*EXECUTABLE but not in enum  # noqa: E501
        if re.search(r"status\s*=\s*ChallengeExecutionStatus\.EXECUTABLE", txt):
            reasons.append(
                "portfolio_explorer.py contains EXECUTABLE status (should be REPRESENTABLE_ONLY)"  # noqa: E501
            )
        if re.search(r"status\s*=\s*ChallengeExecutionStatus\.NOT_YET_EXECUTABLE", txt):
            reasons.append("portfolio_explorer.py contains NOT_YET_EXECUTABLE for a seed")
        # Ensure at least 7 REPRESENTABLE_ONLY for seeds (the enum also has one)
        if cnt_repr < 7:
            reasons.append(f"portfolio_explorer.py REPRESENTABLE_ONLY count {cnt_repr} <7")
    else:
        reasons.append("missing src/traffictwin/ui/portfolio_explorer.py")

    # 6. No duplicate Portfolio page registration check: count occurrences of portfolio_explorer in navigation files should be reasonable (1 each)  # noqa: E501
    # Already checked existence; just ensure not 0

    is_ready = len(reasons) == 0
    return is_ready, reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PR #17 Phase-B readiness check (merge-style-agnostic)"
    )
    parser.add_argument(
        "--main-path",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Path to checked-out main (default cwd)",
    )
    parser.add_argument(
        "--pr13-merged-at",
        type=str,
        default=None,
        help="PR #13 mergedAt value (null or ISO timestamp). If not supplied, will try --query-gh.",
    )
    parser.add_argument(
        "--query-gh",
        action="store_true",
        help="Query gh pr view 13 for mergedAt (requires gh auth)",
    )
    parser.add_argument(
        "--pr13-head-oid",
        type=str,
        default=None,
        help="Optional informational PR #13 head OID (not required for readiness)",
    )
    args = parser.parse_args(argv)

    merged_at = args.pr13_merged_at

    if args.query_gh and merged_at is None:
        try:
            res = subprocess.run(
                [  # noqa: S603,S607
                    "gh",
                    "pr",
                    "view",
                    "13",
                    "--repo",
                    "Abdulla4akash/traffictwin",
                    "--json",
                    "mergedAt,headRefOid",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            import json

            j = json.loads(res.stdout)
            merged_at = j.get("mergedAt")
            print(f"gh query: PR #13 mergedAt={merged_at!r} headRefOid={j.get('headRefOid')}")
        except Exception as e:
            print(f"ERROR querying gh: {e}", file=sys.stderr)
            return 2

    # Gate A
    if merged_at is None or str(merged_at).strip().lower() in ("null", "none", ""):
        print("BLOCKED_PR13_OPEN: PR #13 mergedAt is null/None — PR #13 not merged, no Phase B.")
        if args.pr13_head_oid:
            print(f"  informational head {args.pr13_head_oid} ancestry check not required")
        print("  Gate A (GitHub mergedAt != null) FAILED")
        return 1

    print(f"Gate A PASS: PR #13 mergedAt={merged_at!r}")

    # Gate B
    main_path = args.main_path.resolve()
    print(f"Checking Gate B content contract on main_path={main_path}")
    is_ready, reasons = check_content_gate(main_path)
    if is_ready:
        print("Gate B PASS: PR #13 product contract present on live main")
        print("READY_FOR_PHASE_B: PR #13 reports merged AND product contract exists on live main.")
        # Informational ancestry check (not required)
        if args.pr13_head_oid:
            try:
                # Try to check ancestry, but don't fail on it
                r = subprocess.run(  # noqa: S603,S607
                    ["git", "merge-base", "--is-ancestor", args.pr13_head_oid, "origin/main"],  # noqa: S607
                    capture_output=True,
                )
                anc = "TRUE" if r.returncode == 0 else "FALSE"
                print(
                    f"  informational: git merge-base --is-ancestor {args.pr13_head_oid[:7]} origin/main → {anc} (not required for READY)"  # noqa: E501
                )
            except Exception:  # noqa: S110
                pass  # noqa: S110
        return 0
    else:
        print("Gate B FAIL: PR #13 product contract NOT satisfied on live main")
        for reason in reasons:
            print(f"  - {reason}")
        print(
            "BLOCKED_CONTENT_MISMATCH: PR #13 reports merged, but main does not satisfy expected Portfolio/Challenge product contract."  # noqa: E501
        )
        print("  Investigate merge result; do not proceed to Phase B.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
