"""Tests for PR #17 Phase-B readiness checker — merge-style-agnostic."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

from tools.check_pr17_phase_b_ready import check_content_gate

# Use the rehearsal branch's product contract as source of truth
REHEARSAL_MAIN = pathlib.Path.cwd()  # will be rehearsal/pr17-phase-b-v1 which has contract


def test_pr13_not_merged_blocked() -> None:
    """Gate A: null mergedAt -> BLOCKED_PR13_OPEN regardless of content."""
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--pr13-merged-at",
            "null",
            "--main-path",
            str(REHEARSAL_MAIN),
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_PR13_OPEN" in result.stdout
    assert result.returncode == 1


def test_merged_blocked_content_mismatch_missing_file(tmp_path: pathlib.Path) -> None:
    """Gate B: merged but missing file -> BLOCKED_CONTENT_MISMATCH."""
    # Copy rehearsal main to tmp and remove a critical file
    # Use tmp_path as main_path with missing portfolio file
    # Create minimal structure missing portfolio_explorer.py
    # Instead, just point to an empty dir -> should be mismatch
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
            "--main-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_CONTENT_MISMATCH" in result.stdout
    assert result.returncode == 2


def test_merged_ready_on_rehearsal() -> None:
    """Gate B: merged + correct contract (rehearsal branch) -> READY."""
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
            "--main-path",
            str(REHEARSAL_MAIN),
        ],
        capture_output=True,
        text=True,
    )
    assert "READY_FOR_PHASE_B" in result.stdout
    assert result.returncode == 0


def test_merged_challenge_status_changed_blocked(tmp_path: pathlib.Path) -> None:
    """Merged but challenge status changed away from REPRESENTABLE_ONLY -> BLOCKED."""
    # Copy current portfolio file to tmp and patch status
    dest_dir = tmp_path / "src/traffictwin/ui"
    dest_dir.mkdir(parents=True)
    # Copy entire structure needed for check_content_gate: we need at least the 3 files + labels/nav
    # Copy required files to tmp main with mutation
    # For simplicity, copy the real file and then mutate one occurrence

    # Create tmp main root and copy required files
    for rel in [
        "src/traffictwin/ui/portfolio_explorer.py",
        "src/traffictwin/ui/pages/portfolio_explorer.py",
        "src/traffictwin/ui/app_pages/portfolio_explorer.py",
        "src/traffictwin/ui/labels.py",
        "src/traffictwin/ui/navigation_v07.py",
        "src/traffictwin/ui/navigation.py",
    ]:
        src_path = REHEARSAL_MAIN / rel
        dst_path = tmp_path / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_path, dst_path)
    # Mutate portfolio file: replace one REPRESENTABLE_ONLY with EXECUTABLE for a seed
    port = tmp_path / "src/traffictwin/ui/portfolio_explorer.py"
    txt = port.read_text()
    # Replace first seed status
    txt = txt.replace(
        "status=ChallengeExecutionStatus.REPRESENTABLE_ONLY",
        "status=ChallengeExecutionStatus.EXECUTABLE",
        1,
    )
    port.write_text(txt)
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "tools/check_pr17_phase_b_ready.py",
            "--pr13-merged-at",
            "2026-08-09T12:00:00Z",
            "--main-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert "BLOCKED_CONTENT_MISMATCH" in result.stdout
    assert "EXECUTABLE" in result.stdout
    assert result.returncode == 2


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
