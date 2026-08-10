# ruff: noqa: ANN001,ANN002,ANN003,ANN201,ANN202,S603,S607,C416,E501
# mypy: disable-error-code="attr-defined, misc, operator, assignment, call-arg, unused-ignore, no-untyped-def"
"""Genuine cold AppTest proof — negative and positive controls.

This file owns the expensive cold proof. It is marked ``cold_apptest`` and
excluded from routine runs via ``addopts = "-m 'not cold_apptest'"`` in
pyproject.toml. Run deliberately with:

    pytest -m cold_apptest -v

Each control runs in a *genuinely cold* environment:

- unique empty ``PYTHONPYCACHEPREFIX``,
- ``-p no:cacheprovider``,
- fresh subprocess,
- no preceding AppTest in that process.

Inner target is identical except for hardening enablement:

- NEGATIVE: ``--noconftest`` (hardening disabled) → expects timeout failure
- POSITIVE: with plugin → expects pass

If the negative unexpectedly passes (machine genuinely faster), the test
reports the environment and deterministic installer tests remain the invariant.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

# Inner target — must be a real TrafficTwin AppTest that does ``app.run(timeout=10)``
INNER_TARGET = "tests/integration/test_ui_demo_flow.py::test_streamlit_app_starts_with_apptest"
OUTER_TIMEOUT = 240  # defensible headroom for cold start (cold imports + AppTest)


def _run_cold_subprocess(
    *, hardening_enabled: bool, tmp_prefix: Path
) -> subprocess.CompletedProcess[str]:
    """Run the inner AppTest in a genuinely cold subprocess.

    Returns the CompletedProcess. Caller asserts on returncode/stdout.
    On TimeoutExpired, pytest fails with diagnostics (command, stdout, stderr,
    elapsed, hardening, pycache prefix) instead of opaque error.
    """
    repo_root = Path(__file__).resolve().parents[1]
    python = sys.executable

    # Unique empty pycache prefix for this invocation
    pycache_prefix = tmp_prefix / f"pyc_{'hardened' if hardening_enabled else 'plain'}"
    pycache_prefix.mkdir(parents=True, exist_ok=True)

    env = {
        **{k: v for k, v in __import__("os").environ.items()},
        "PYTHONPYCACHEPREFIX": str(pycache_prefix),
        # Ensure no polluted watcher type inside subprocess
        "STREAMLIT_WATCHER_TYPE": "none",
    }

    # Build pytest command — identical except for --noconftest
    cmd = [
        python,
        "-m",
        "pytest",
        INNER_TARGET,
        "-v",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]
    if not hardening_enabled:
        cmd.append("--noconftest")

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=OUTER_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        # Fail with full diagnostics, not opaque TimeoutExpired
        pytest.fail(
            "Cold subprocess timed out\n"
            f"  command: {' '.join(cmd)}\n"
            f"  hardening_enabled: {hardening_enabled}\n"
            f"  pycache_prefix: {pycache_prefix}\n"
            f"  elapsed: {elapsed:.1f}s / {OUTER_TIMEOUT}s\n"
            f"  stdout: {exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout}\n"
            f"  stderr: {exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr}\n"
        )
    elapsed = time.monotonic() - start
    # Attach diagnostics for easier triage if caller asserts
    result.elapsed = elapsed  # type: ignore[attr-defined]
    result.pycache_prefix = str(pycache_prefix)  # type: ignore[attr-defined]
    result.cmd_str = " ".join(cmd)  # type: ignore[attr-defined]
    return result


@pytest.mark.cold_apptest
def test_cold_negative_without_hardening(tmp_path: Path) -> None:
    """Negative control: hardening disabled, explicit timeout=10 should time out.

    If the machine is genuinely faster and this passes, report environment
    and rely on deterministic wrapper tests as invariant.
    """
    result = _run_cold_subprocess(hardening_enabled=False, tmp_prefix=tmp_path)

    # We *expect* failure when hardening is disabled and cold overhead >10s.
    # The proof is discriminating: enabled should pass, disabled should fail.
    # If disabled unexpectedly passes, do not fake a failure — report.
    if result.returncode == 0 and "1 passed" in result.stdout:
        # Environment is faster than Claude's darwin measurement (8-12s cold).
        # Report and let the positive control + deterministic tests be the invariant.
        print(
            f"[cold negative] unexpectedly passed — machine cold time <10s\n"
            f"  cmd: {result.cmd_str}\n"  # type: ignore[attr-defined]
            f"  elapsed: {result.elapsed:.1f}s\n"  # type: ignore[attr-defined]
            f"  pycache: {result.pycache_prefix}\n"  # type: ignore[attr-defined]
            f"  stdout:\n{result.stdout}\n"
            f"  This does not invalidate the hardening; deterministic installer tests prove the policy."
        )
        # Do not fail — the deterministic wrapper tests are the invariant proof.
        # But record that the control was not discriminating in this env.
        pytest.skip(
            "Cold negative passed — env faster than measured 8-12s; deterministic tests are invariant"
        )

    # Otherwise we expect a timeout failure
    assert result.returncode != 0, (
        f"Negative control expected failure but got {result.returncode}\n"
        f"  cmd: {result.cmd_str}\n"  # type: ignore[attr-defined]
        f"  elapsed: {result.elapsed:.1f}s\n"  # type: ignore[attr-defined]
        f"  pycache: {result.pycache_prefix}\n"  # type: ignore[attr-defined]
        f"  stdout:\n{result.stdout}\n"
        f"  stderr:\n{result.stderr}\n"
    )
    # Check for RuntimeError timeout signature
    combined = result.stdout + result.stderr
    assert "RuntimeError" in combined or "timed out" in combined.lower(), (
        f"Negative control failed but not with timeout signature\n"
        f"  stdout:\n{result.stdout}\n"
        f"  stderr:\n{result.stderr}\n"
    )


@pytest.mark.cold_apptest
def test_cold_positive_with_hardening(tmp_path: Path) -> None:
    """Positive control: hardening enabled, same target should pass even cold."""
    result = _run_cold_subprocess(hardening_enabled=True, tmp_prefix=tmp_path)

    assert result.returncode == 0, (
        f"Positive control expected pass but failed\n"
        f"  cmd: {result.cmd_str}\n"  # type: ignore[attr-defined]
        f"  elapsed: {result.elapsed:.1f}s\n"  # type: ignore[attr-defined]
        f"  pycache: {result.pycache_prefix}\n"  # type: ignore[attr-defined]
        f"  stdout:\n{result.stdout}\n"
        f"  stderr:\n{result.stderr}\n"
    )
    assert "1 passed" in result.stdout
    assert "RuntimeError" not in result.stdout
    assert "timed out after 10" not in result.stdout
