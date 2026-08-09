"""Subprocess cold-start integration proof for AppTest hardening.

This test spawns a *fresh* Python/pytest process and verifies that the first
AppTest with explicit timeout=10 no longer fails solely due to cold import
overhead. It uses real TrafficTwin AppTest behavior (Portfolio Explorer),
not just the pure timeout helper. Marked slow so it does not run in every
routine `pytest` invocation unless explicitly requested, but the hardening PR
report must include its actual cold proof.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.slow
def test_first_apptest_timeout_10_passes_in_fresh_process(tmp_path: Path) -> None:
    # Fresh process: run a single AppTest that internally does app.run(timeout=10)
    # via the real Portfolio Explorer page. With the cold floor (60s), it should
    # pass even though cold imports would previously exceed 10s.
    # We use a known AppTest that is relatively light but still requires cold imports.
    repo_root = Path(__file__).resolve().parents[1]
    # Use the same venv's python
    python = sys.executable
    # Run a single AppTest in a fresh process
    result = subprocess.run(  # noqa: S603
        [
            python,
            "-m",
            "pytest",
            "tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest",
            "-v",
            "--tb=short",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=90,
    )
    # The subprocess should exit 0 and report 1 passed, no RuntimeError timeout
    assert result.returncode == 0, f"fresh cold run failed:\n{result.stdout}\n{result.stderr}"
    assert "1 passed" in result.stdout
    assert "RuntimeError" not in result.stdout
    assert "timed out after 10" not in result.stdout
