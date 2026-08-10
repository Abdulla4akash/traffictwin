#!/usr/bin/env python3
"""
Phase-B readiness check for PR #17 — merge-style-agnostic, fail-closed.

Gate A: GitHub says PR #13 was actually merged (mergedAt != null).
Gate B: live `origin/main` (via --main-path + --expected-main-sha) contains the reviewed
        PR #13 product contract (file existence + content).

Result states (distinct exit codes):
  READY_FOR_PHASE_B              0
  BLOCKED_PR13_OPEN              1
  BLOCKED_CONTENT_MISMATCH       2
  GITHUB_QUERY_ERROR             3
  MAIN_PATH_REVISION_MISMATCH    4
  MAIN_PATH_NOT_DETACHED         5
  MAIN_PATH_DIRTY                6

Gate B only ever inspects a throwaway DETACHED worktree created from exact freshly
fetched `origin/main`: a branch checkout (rehearsal/current worktree) is refused
structurally (exit 5) and a dirty tree is refused structurally (exit 6), both
BEFORE any content is read. Revision binding (exit 4) is checked first, so a
wrong-SHA worktree fails even if its content happens to match.

This script is READ-ONLY, does not modify files, does not run SUMO/VEC.

Usage:
  python tools/check_pr17_phase_b_ready.py  # noqa: E501
  #   --main-path /tmp/worktree --expected-main-sha abc123  # noqa: E501
  #   --pr13-merged-at 2026-08-09T12:00:00Z  # noqa: E501
  python tools/check_pr17_phase_b_ready.py  # noqa: E501
  #   --main-path /tmp/worktree --expected-main-sha abc --pr13-merged-at null  # noqa: E501
  python tools/check_pr17_phase_b_ready.py  # noqa: E501
  #   --main-path /tmp/worktree --expected-main-sha abc --query-gh  # noqa: E501

Exit codes distinct; see docstring. Missing required --main-path fails via argparse (exit 2).
"""

from __future__ import annotations

import argparse
import ast
import pathlib
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


def _actual_head_sha(main_path: pathlib.Path) -> str | None:
    """Run git -C main_path rev-parse HEAD, return sha or None on error."""
    try:
        r = subprocess.run(  # noqa: S603
            ["git", "-C", str(main_path), "rev-parse", "HEAD"],  # noqa: S603,S607
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode != 0:
            return None
        return r.stdout.strip()
    except Exception:
        return None


def _checked_out_branch(main_path: pathlib.Path) -> str | None:
    """Return the branch name if main_path is a branch checkout, None if detached."""
    r = subprocess.run(  # noqa: S603
        ["git", "-C", str(main_path), "symbolic-ref", "-q", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return None
    return r.stdout.strip() or "(unknown ref)"


def _status_porcelain(main_path: pathlib.Path) -> str | None:
    """Return `git status --porcelain` output, or None on error."""
    r = subprocess.run(  # noqa: S603
        ["git", "-C", str(main_path), "status", "--porcelain"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return None
    return r.stdout


def _count_portfolio_registrations_via_ast(main_path: pathlib.Path) -> tuple[int, list[str]]:
    """
    Authoritative registration count for Portfolio Explorer.

    Parses src/traffictwin/ui/navigation_v07.py via AST and counts V07PageSpec
    where page=UiPage.PORTFOLIO_EXPLORER. Excludes comments/docs/tests/enum.
    Returns (count, reasons).
    """
    reasons: list[str] = []
    nav_v07_path = main_path / EXPECTED_NAV_V07
    if not nav_v07_path.is_file():
        return 0, [f"missing {EXPECTED_NAV_V07}"]
    try:
        tree = ast.parse(_read(nav_v07_path), filename=str(nav_v07_path))
    except Exception as e:
        return 0, [f"navigation_v07.py AST parse error: {e}"]
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check func is V07PageSpec
            func = node.func
            func_name = ""
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name == "V07PageSpec":
                # Check both positional first arg and keyword page=
                candidates = []
                if node.args:
                    candidates.append(node.args[0])
                for kw in node.keywords:
                    if kw.arg == "page":
                        candidates.append(kw.value)
                for val in candidates:
                    if (
                        isinstance(val, ast.Attribute)
                        and val.attr == "PORTFOLIO_EXPLORER"
                        and (
                            isinstance(val.value, ast.Name)
                            and val.value.id == "UiPage"
                            or isinstance(val.value, ast.Attribute)
                        )
                    ):
                        count += 1
                        break
    return count, reasons


def _parse_challenge_seeds_via_ast(  # noqa: E501
    main_path: pathlib.Path,
) -> tuple[list[tuple[str, str]], list[str]]:
    """
    Parse portfolio_explorer.py via AST to extract ChallengeSeedDefinition challenge_id and status.
    Returns list of (challenge_id, status_str) and reasons.
    Status_str is like "REPRESENTABLE_ONLY", "EXECUTABLE", etc.
    """
    reasons: list[str] = []
    port_path = main_path / "src/traffictwin/ui/portfolio_explorer.py"
    if not port_path.is_file():
        return [], ["missing src/traffictwin/ui/portfolio_explorer.py"]
    try:
        tree = ast.parse(_read(port_path), filename=str(port_path))
    except Exception as e:
        return [], [f"portfolio_explorer.py AST parse error: {e}"]
    seeds: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            func_name = ""
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name == "ChallengeSeedDefinition":
                cid = None
                status = "REPRESENTABLE_ONLY"  # default per class definition
                for kw in node.keywords:
                    if (
                        kw.arg == "challenge_id"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        cid = kw.value.value
                    elif kw.arg == "status":
                        # status=ChallengeExecutionStatus.REPRESENTABLE_ONLY
                        val = kw.value
                        if isinstance(val, ast.Attribute):
                            status = val.attr
                        elif isinstance(val, ast.Constant) and isinstance(val.value, str):
                            status = val.value
                if cid is not None and cid.startswith("CH-"):
                    seeds.append((cid, status))
    return seeds, reasons


def check_content_gate(main_path: pathlib.Path) -> tuple[bool, list[str]]:
    """Check Gate B: does main_path contain PR #13 product contract?"""
    reasons: list[str] = []

    # 1. Expected files exist
    for rel in EXPECTED_FILES:
        p = main_path / rel
        if not p.is_file():
            reasons.append(f"missing file {rel}")

    # 2. labels.py contains PORTFOLIO_EXPLORER (presence, not count for page registration)
    labels = main_path / EXPECTED_LABELS
    if labels.is_file():
        txt = _read(labels)
        if "PORTFOLIO_EXPLORER" not in txt:
            reasons.append("labels.py missing PORTFOLIO_EXPLORER")
    else:
        reasons.append(f"missing {EXPECTED_LABELS}")

    # 3. navigation_v07.py authoritative registration count ==1 (exactly once, via AST)
    count, nav_reasons = _count_portfolio_registrations_via_ast(main_path)
    reasons.extend(nav_reasons)
    if count != 1 and not any("missing" in r for r in nav_reasons):
        reasons.append(
            f"portfolio_registration_count = {count} expected = 1 "  # noqa: E501
            "(navigation_v07.py V07PageSpec PORTFOLIO_EXPLORER)"  # noqa: E501
        )

    # 4. navigation.py contains portfolio explorer registration  # noqa: E501
    nav = main_path / EXPECTED_NAV
    if nav.is_file():
        txt = _read(nav)
        if "portfolio" not in txt.lower():
            reasons.append("navigation.py missing portfolio reference")
    else:
        reasons.append(f"missing {EXPECTED_NAV}")

    # 5. Challenge seed library contracts via AST (structural, not token count)
    port = main_path / "src/traffictwin/ui/portfolio_explorer.py"
    if port.is_file():
        txt = _read(port)
        if "class ChallengeSeedDefinition" not in txt:
            reasons.append("portfolio_explorer.py missing ChallengeSeedDefinition")
        if "SELECTOR_CONSUMED_FIELDS" not in txt:
            reasons.append("portfolio_explorer.py missing SELECTOR_CONSUMED_FIELDS")
        if "get_challenge_seed_library" not in txt:
            reasons.append("portfolio_explorer.py missing get_challenge_seed_library")
        if "get_challenge_seed" not in txt:
            reasons.append("portfolio_explorer.py missing get_challenge_seed")
        if "challenge_target_surfaces" not in txt:
            reasons.append(
                "portfolio_explorer.py missing fingerprint binding challenge_target_surfaces"
            )
        if "selector_input_features" not in txt:
            reasons.append(
                "portfolio_explorer.py missing fingerprint binding selector_input_features"
            )
        forbidden = ["def run_challenge", "def execute_challenge", "def run_scenario_seed"]
        for f in forbidden:
            if f in txt:
                reasons.append(f"portfolio_explorer.py contains forbidden generic executor {f!r}")
        # Structural challenge seed count
        seeds, seed_reasons = _parse_challenge_seeds_via_ast(main_path)
        reasons.extend(seed_reasons)
        # Check exactly 7
        if len(seeds) != 7:
            reasons.append(f"challenge_seed_count = {len(seeds)} expected = 7 (found {seeds})")
        # Check IDs exactly match expected set
        found_ids = {cid for cid, _ in seeds}
        expected_ids = set(EXPECTED_CHALLENGE_IDS)
        if found_ids != expected_ids:
            missing = expected_ids - found_ids
            extra = found_ids - expected_ids
            if missing:
                for cid in sorted(missing):
                    reasons.append(f"portfolio_explorer.py missing challenge seed {cid}")
            if extra:
                reasons.append(
                    f"portfolio_explorer.py has unexpected challenge seeds {sorted(extra)}"
                )
        # Check all 7 are REPRESENTABLE_ONLY structurally
        non_repr = [(cid, st) for cid, st in seeds if st != "REPRESENTABLE_ONLY"]
        if non_repr:
            ids = [f"{cid}={st}" for cid, st in non_repr]
            reasons.append(
                f"non_representable_seed_ids = {ids} expected = [] (all 7 must be REPRESENTABLE_ONLY)"  # noqa: E501
            )
        # Also ensure no status EXECUTABLE etc remains (covered by non_repr)
        # Enum definition itself not counted because we only count ChallengeSeedDefinition calls
    else:
        reasons.append("missing src/traffictwin/ui/portfolio_explorer.py")

    is_ready = len(reasons) == 0
    return is_ready, reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PR #17 Phase-B readiness check (merge-style-agnostic, fail-closed)"
    )
    parser.add_argument(
        "--main-path",
        type=pathlib.Path,
        required=True,
        help="Path to checked-out main (throwaway worktree at exact origin/main SHA)",
    )
    parser.add_argument(
        "--expected-main-sha",
        type=str,
        required=True,
        help="Expected git rev-parse origin/main SHA that main-path must exactly match",
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
            print(f"GITHUB_QUERY_ERROR: ERROR querying gh: {e}", file=sys.stderr)
            return 3

    # Gate A
    if merged_at is None or str(merged_at).strip().lower() in ("null", "none", ""):
        print("BLOCKED_PR13_OPEN: PR #13 mergedAt is null/None — PR #13 not merged, no Phase B.")
        if args.pr13_head_oid:
            print(f"  informational head {args.pr13_head_oid} ancestry check not required")
        print("  Gate A (GitHub mergedAt != null) FAILED")
        return 1

    print(f"Gate A PASS: PR #13 mergedAt={merged_at!r}")

    # Verify main-path revision binding BEFORE content check
    main_path = args.main_path.resolve()
    expected_sha = args.expected_main_sha.strip()
    actual_sha = _actual_head_sha(main_path)
    if actual_sha is None:
        print(  # noqa: E501
            f"MAIN_PATH_REVISION_MISMATCH: cannot determine HEAD of main_path={main_path}",  # noqa: E501
            file=sys.stderr,
        )
        print(f"  expected-main-sha={expected_sha}")
        return 4
    if actual_sha != expected_sha:
        print(  # noqa: E501
            f"MAIN_PATH_REVISION_MISMATCH: main_path HEAD {actual_sha} != expected {expected_sha}",  # noqa: E501
            file=sys.stderr,
        )
        print(f"  main_path={main_path} expected-main-sha={expected_sha} actual={actual_sha}")
        print("  Gate B not evaluated — worktree does not match fetch.")
        return 4
    print(f"Main-path revision binding PASS: {actual_sha} == expected {expected_sha}")

    # Structural throwaway-worktree binding: Gate B must only ever read a DETACHED,
    # CLEAN worktree created from freshly fetched origin/main — a populated
    # rehearsal/current branch checkout is refused even at the right SHA.
    branch = _checked_out_branch(main_path)
    if branch is not None:
        print(
            f"MAIN_PATH_NOT_DETACHED: main_path is a branch checkout ({branch}); "
            "Gate B requires a throwaway detached worktree created from exact "
            "freshly fetched origin/main",
            file=sys.stderr,
        )
        print(f"  main_path={main_path}")
        print("  Gate B not evaluated — refusing populated rehearsal/current worktree.")
        return 5
    dirty = _status_porcelain(main_path)
    if dirty is None:
        print(
            f"MAIN_PATH_DIRTY: cannot determine working-tree status of main_path={main_path}",
            file=sys.stderr,
        )
        print("  Gate B not evaluated — fail closed on unknown tree state.")
        return 6
    if dirty.strip():
        print(
            f"MAIN_PATH_DIRTY: main_path working tree is not clean:\n{dirty.rstrip()}",
            file=sys.stderr,
        )
        print(f"  main_path={main_path}")
        print("  Gate B not evaluated — tree content could deviate from the bound revision.")
        return 6
    print("Main-path throwaway-worktree binding PASS: detached HEAD, clean tree")

    # Gate B
    print(f"Checking Gate B content contract on main_path={main_path}")
    is_ready, reasons = check_content_gate(main_path)
    if is_ready:
        print("Gate B PASS: PR #13 product contract present on live main")
        print("READY_FOR_PHASE_B: PR #13 reports merged AND product contract exists on live main.")
        if args.pr13_head_oid:
            try:
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
