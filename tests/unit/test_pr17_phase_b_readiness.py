# mypy: disable-error-code="call-overload"
# ruff: noqa
"""Tests for PR #17 Phase-B readiness checker — merge-style-agnostic, fail-closed."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest
from tools.check_pr17_phase_b_ready import check_content_gate

REHEARSAL_MAIN = pathlib.Path.cwd()


def _expected_sha(path: pathlib.Path) -> str:
    """Get git HEAD sha for path."""
    r = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def test_missing_required_main_path() -> None:
    """Missing required --main-path must fail closed via argparse."""
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--expected-main-sha",
            "abc",
            "--pr13-merged-at",
            "null",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "required" in result.stderr.lower() or "required" in result.stdout.lower()


def test_wrong_worktree_sha_despite_complete_content(tmp_path: pathlib.Path) -> None:
    """Content present but SHA mismatch must be MAIN_PATH_REVISION_MISMATCH, not READY."""
    # Create a copy of rehearsal's valid main content at tmp_path
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src = REHEARSAL_MAIN / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    # Initialize tmp_path as git repo with a different HEAD
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    actual = _expected_sha(tmp_path)
    # Pass expected sha of REHEARSAL_MAIN (different) to trigger mismatch
    expected = _expected_sha(REHEARSAL_MAIN)
    assert actual != expected
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert (
        "MAIN_PATH_REVISION_MISMATCH" in result.stdout
        or "MAIN_PATH_REVISION_MISMATCH" in result.stderr
    )
    assert result.returncode == 4


def test_pr13_not_merged_blocked() -> None:
    """Gate A: null mergedAt -> BLOCKED_PR13_OPEN."""
    expected = _expected_sha(REHEARSAL_MAIN)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(REHEARSAL_MAIN),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "null",
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_PR13_OPEN" in result.stdout
    assert result.returncode == 1


def test_github_query_error_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    """GitHub query failure must be GITHUB_QUERY_ERROR (distinct from content mismatch)."""
    # Monkeypatch subprocess.run for gh to fail
    original_run = subprocess.run

    def fake_run(*args: object, **kwargs: object) -> object:  # noqa: ANN002,ANN202
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and "gh" in cmd:
            raise FileNotFoundError("gh not found")
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    # Call main with --query-gh, expect GITHUB_QUERY_ERROR
    from tools.check_pr17_phase_b_ready import main

    rc = main(
        [
            "--main-path",
            str(REHEARSAL_MAIN),
            "--expected-main-sha",
            _expected_sha(REHEARSAL_MAIN),
            "--query-gh",
        ]
    )
    assert rc == 3


def test_merged_ready_on_valid_main() -> None:
    """Valid main with mergedAt -> READY."""
    expected = _expected_sha(REHEARSAL_MAIN)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(REHEARSAL_MAIN),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert "READY_FOR_PHASE_B" in result.stdout
    assert result.returncode == 0


def test_merged_blocked_content_mismatch_missing_file(tmp_path: pathlib.Path) -> None:
    """Merged but missing file -> BLOCKED_CONTENT_MISMATCH."""
    # tmp_path empty, init as git repo with HEAD
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"], cwd=tmp_path, capture_output=True
    )
    expected = _expected_sha(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_CONTENT_MISMATCH" in result.stdout
    assert result.returncode == 2


def test_missing_portfolio_registration(tmp_path: pathlib.Path) -> None:
    """0 registrations -> BLOCKED."""
    # Copy valid main then remove PORTFOLIO registration via AST-level mutation
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src = REHEARSAL_MAIN / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    # Remove PORTFOLIO_EXPLORER registration: delete the V07PageSpec block containing it
    nav_path = tmp_path / "src/traffictwin/ui/navigation_v07.py"
    txt = nav_path.read_text()
    # Remove one occurrence: replace UiPage.PORTFOLIO_EXPLORER with UiPage.HOME  # noqa: E501
    txt = txt.replace("UiPage.PORTFOLIO_EXPLORER", "UiPage.HOME")
    nav_path.write_text(txt)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    expected = _expected_sha(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_CONTENT_MISMATCH" in result.stdout
    assert "portfolio_registration_count = 0" in result.stdout
    assert result.returncode == 2


def test_duplicate_portfolio_registration(tmp_path: pathlib.Path) -> None:
    """2 registrations -> BLOCKED (exactly-once)."""
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src = REHEARSAL_MAIN / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    nav_path = tmp_path / "src/traffictwin/ui/navigation_v07.py"
    txt = nav_path.read_text()
    # Duplicate: append another V07PageSpec with PORTFOLIO_EXPLORER at end
    txt += '\nV07PageSpec(UiPage.PORTFOLIO_EXPLORER, "Results", "app_pages/portfolio_explorer.py", "portfolio-explorer", ":material/assessment:")\n'
    nav_path.write_text(txt)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    expected = _expected_sha(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_CONTENT_MISMATCH" in result.stdout
    assert "portfolio_registration_count = 2" in result.stdout
    assert result.returncode == 2


def test_six_challenge_seeds_blocked(tmp_path: pathlib.Path) -> None:
    """Only 6 seeds -> BLOCKED (exactly 7)."""
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src = REHEARSAL_MAIN / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    port = tmp_path / "src/traffictwin/ui/portfolio_explorer.py"
    txt = port.read_text()
    # Remove one seed block (CH-07)
    txt = txt.replace(
        '        challenge_id="CH-07-scaling-strategy",', '        challenge_id="CH-99-missing",', 1
    )
    # Actually need to remove count: easier to delete one ChallengeSeedDefinition block for CH-07
    # Remove the whole block containing CH-07
    import re

    txt2 = re.sub(
        r'ChallengeSeedDefinition\(\s*challenge_id="CH-07-scaling-strategy".*?status=ChallengeExecutionStatus\.REPRESENTABLE_ONLY.*?\n    \),',
        "",
        txt,
        flags=re.DOTALL,
    )
    port.write_text(txt2)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    expected = _expected_sha(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_CONTENT_MISMATCH" in result.stdout
    assert "CH-07" in result.stdout or "challenge_seed_count" in result.stdout
    assert result.returncode == 2


def test_one_non_representable_challenge_blocked(tmp_path: pathlib.Path) -> None:
    """One seed EXECUTABLE -> BLOCKED."""
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src = REHEARSAL_MAIN / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    port = tmp_path / "src/traffictwin/ui/portfolio_explorer.py"
    txt = port.read_text()
    txt = txt.replace(
        "status=ChallengeExecutionStatus.REPRESENTABLE_ONLY",
        "status=ChallengeExecutionStatus.EXECUTABLE",
        1,
    )
    port.write_text(txt)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    expected = _expected_sha(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_CONTENT_MISMATCH" in result.stdout
    assert "non_representable_seed_ids" in result.stdout or "EXECUTABLE" in result.stdout
    assert result.returncode == 2


def test_enum_definition_does_not_inflate_count(tmp_path: pathlib.Path) -> None:
    """Enum REPRESENTABLE_ONLY text should not count as seed."""
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src = REHEARSAL_MAIN / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    # Add enum text occurrence without adding a seed
    port = tmp_path / "src/traffictwin/ui/portfolio_explorer.py"
    txt = port.read_text()
    txt += "\n# REPRESENTABLE_ONLY enum comment fake: REPRESENTABLE_ONLY REPRESENTABLE_ONLY\n"
    port.write_text(txt)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    expected = _expected_sha(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    # Should still be READY because enum text doesn't affect AST count
    assert "READY_FOR_PHASE_B" in result.stdout
    assert result.returncode == 0


def test_valid_seven_seed_contract(tmp_path: pathlib.Path) -> None:
    """Valid 7 seeds all REPRESENTABLE_ONLY -> READY (with correct SHA binding)."""
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src = REHEARSAL_MAIN / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    expected = _expected_sha(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(tmp_path),
            "--expected-main-sha",
            expected,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert "READY_FOR_PHASE_B" in result.stdout
    assert result.returncode == 0


def test_rehearsal_tree_is_rejected_when_expected_main_sha_differs() -> None:
    """Rehearsal tree content present but SHA mismatch -> MAIN_PATH_REVISION_MISMATCH."""
    # REHEARSAL_MAIN has full content, but we pass expected sha of origin/main (different)
    origin_sha = subprocess.run(
        ["git", "rev-parse", "origin/main"], capture_output=True, text=True, check=True
    ).stdout.strip()
    rehearsal_sha = _expected_sha(REHEARSAL_MAIN)
    assert origin_sha != rehearsal_sha
    result = subprocess.run(
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--main-path",
            str(REHEARSAL_MAIN),
            "--expected-main-sha",
            origin_sha,
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
        ],
        capture_output=True,
        text=True,
    )
    assert (
        "MAIN_PATH_REVISION_MISMATCH" in result.stdout
        or "MAIN_PATH_REVISION_MISMATCH" in result.stderr
    )
    assert result.returncode == 4


def test_content_gate_direct() -> None:
    """Direct check_content_gate on rehearsal should pass."""
    is_ready, reasons = check_content_gate(REHEARSAL_MAIN)
    assert is_ready, f"reasons: {reasons}"
    assert reasons == []


def test_content_gate_missing_portfolio(tmp_path: pathlib.Path) -> None:
    """Direct gate fails when missing file."""
    is_ready, reasons = check_content_gate(tmp_path)
    assert not is_ready
    assert any("missing file" in r for r in reasons)
