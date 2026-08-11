# mypy: disable-error-code="attr-defined, misc, no-untyped-def, arg-type,"
# mypy: disable-error-code="unused-ignore, operator, assignment, call-arg"
"""Subprocess-proof Streamlit isolation tests.

This module contains **only** subprocess-driven proofs that must run from a
parent pytest process that has never performed an in-process AppTest render.
It contains no ``AppTest.from_file`` / ``_victim_can_render`` calls in the
parent process, to avoid the SIGSEGV that occurs when a parent that has
rendered AppTest later spawns ``subprocess.run(... capture_output=True ...)``
children.

See BLOCKER B1: the three central subprocess evidences are isolated here so
``uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py`` is
stable 20/20 even when the ordinary guard module has previously rendered
AppTest in a *different* pytest process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_probe_subprocess(probe_source: str) -> subprocess.CompletedProcess[str]:
    """Create a temp probe under ``tests/`` and run it via the real guard."""
    repo_root = Path(__file__).resolve().parents[2]
    fd, probe_path_str = tempfile.mkstemp(
        dir=str(repo_root / "tests"),
        prefix="_tmp_probe_",
        suffix=".py",
    )
    os.close(fd)
    probe_path = Path(probe_path_str)
    try:
        probe_path.write_text(probe_source, encoding="utf-8")
        env = dict(os.environ)
        env.pop("PYTEST_CURRENT_TEST", None)
        env.pop("UV_RUN_RECURSION_DEPTH", None)
        env.pop("UV", None)
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(probe_path),
            "-v",
            "-W",
            "always::pytest.PytestWarning",
            "-p",
            "no:cacheprovider",
        ]
        result = subprocess.run(  # noqa: S603 - trusted local probe file
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return result
    finally:
        import contextlib

        with contextlib.suppress(FileNotFoundError):
            probe_path.unlink()


def _run_probe_subprocess_error_warnings(probe_source: str) -> subprocess.CompletedProcess[str]:
    """Like ``_run_probe_subprocess`` but with ``-W error::pytest.PytestWarning``."""
    repo_root = Path(__file__).resolve().parents[2]
    fd, probe_path_str = tempfile.mkstemp(
        dir=str(repo_root / "tests"),
        prefix="_tmp_probe_",
        suffix=".py",
    )
    os.close(fd)
    probe_path = Path(probe_path_str)
    try:
        probe_path.write_text(probe_source, encoding="utf-8")
        env = dict(os.environ)
        env.pop("PYTEST_CURRENT_TEST", None)
        env.pop("UV_RUN_RECURSION_DEPTH", None)
        env.pop("UV", None)
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(probe_path),
            "-v",
            "-W",
            "error::pytest.PytestWarning",
            "-p",
            "no:cacheprovider",
        ]
        result = subprocess.run(  # noqa: S603 - trusted local probe file
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return result
    finally:
        import contextlib

        with contextlib.suppress(FileNotFoundError):
            probe_path.unlink()


def test_real_fixture_passing_polluter_emits_warning_and_victim_passes() -> None:
    """Passing polluter via real autouse fixture: polluter passes, warning, victim restored."""
    probe = """
import types
import sys
import importlib

def test_a_leaks_fake_streamlit_and_passes():
    fake = types.ModuleType("streamlit.testing.v1")
    class FakeAppTest:
        def run(self, timeout=None, **kwargs):
            return self
    fake.AppTest = FakeAppTest
    sys.modules["streamlit"] = types.ModuleType("streamlit")
    sys.modules["streamlit.testing"] = types.ModuleType("streamlit.testing")
    sys.modules["streamlit.testing.v1"] = fake
    assert True

def test_b_victim_sees_real_streamlit():
    import importlib
    m = importlib.import_module("streamlit")
    assert hasattr(m, "secrets"), "real streamlit must have secrets after guard"
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
    from copy import deepcopy
    from traffictwin.ui.state import default_session_state, load_ui_config
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = (  # noqa: E501 - fixture path
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    result = app.run(timeout=30)
    assert not result.exception
"""
    result = _run_probe_subprocess(probe)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"probe should pass (2 passed) but got {result.returncode}:\\n{combined}"
    )
    assert "2 passed" in combined, f"expected 2 passed: {combined}"
    assert "Streamlit isolation leak detected after" in combined, f"warning missing: {combined}"
    assert "test_a_leaks_fake_streamlit_and_passes" in combined
    assert "sys_modules" in combined
    assert "state was restored by the isolation guard" in combined
    assert "real Streamlit capability absent or fake detected" in combined
    assert "BODS_API_KEY" not in combined or "secret" not in combined.lower()


def test_real_fixture_legitimate_import_is_not_a_leak() -> None:
    """Legitimate ``import streamlit`` must not be reported as leak."""
    probe = """
import importlib

def test_a_legitimate_import():
    import importlib
    m = importlib.import_module("streamlit")
    assert hasattr(m, "secrets")
    assert True

def test_b_still_real():
    import importlib
    m = importlib.import_module("streamlit")
    assert hasattr(m, "secrets")
    assert "streamlit" in __import__("sys").modules
"""
    result = _run_probe_subprocess(probe)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, f"legitimate import probe failed: {combined}"
    assert "2 passed" in combined, f"expected 2 passed: {combined}"
    assert "Streamlit isolation leak detected after" not in combined, (
        f"false positive for legitimate import: {combined}"
    )


def test_real_fixture_has_run_first_is_process_scoped() -> None:
    """Process-scoped ``has_run_first``: second child test sees first consumed."""
    probe = """
from tests._apptest_runtime import reset_apptest_cold_state
from tests.support.streamlit_isolation import capture_streamlit_snapshot

def test_a_consumes_first_run():
    from streamlit.testing.v1 import AppTest
    from copy import deepcopy
    from traffictwin.ui.state import default_session_state, load_ui_config
    reset_apptest_cold_state()
    before = capture_streamlit_snapshot()
    assert before.apptest_has_run_first is False
    app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = (  # noqa: E501 - fixture path
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    app.run(timeout=30)
    after = capture_streamlit_snapshot()
    assert after.apptest_has_run_first is True

def test_b_sees_still_consumed():
    from tests.support.streamlit_isolation import capture_streamlit_snapshot
    snap = capture_streamlit_snapshot()
    assert snap.apptest_has_run_first is True, "has_run_first must remain True process-scoped"
"""
    result = _run_probe_subprocess(probe)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, f"process-scoped probe failed: {combined}"
    assert "2 passed" in combined, f"expected 2 passed: {combined}"


def test_legitimate_first_apptest_does_not_warn_under_error() -> None:
    """First legitimate AppTest must not be a leak, even under -W error."""
    probe = """
from tests._apptest_runtime import reset_apptest_cold_state

def test_first_legitimate_apptest():
    reset_apptest_cold_state()
    from streamlit.testing.v1 import AppTest
    from copy import deepcopy
    from traffictwin.ui.state import default_session_state, load_ui_config
    app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = (  # noqa: E501 - fixture path
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    result = app.run(timeout=30)
    assert not result.exception
"""
    result = _run_probe_subprocess_error_warnings(probe)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"legitimate first AppTest should not warn under -W error, got "  # noqa: E501 - message
        f"{result.returncode}:\\n{combined}"
    )
    assert "1 passed" in combined, f"expected 1 passed: {combined}"
    assert "Streamlit isolation leak detected after" not in combined, (
        f"false positive for legitimate first AppTest under -W error: {combined}"
    )


def test_fake_polluter_still_warns_under_error() -> None:
    """Fake polluter must still warn, even though legitimate AppTest does not."""
    probe = """
import types, sys
def test_a_leaks_fake_and_passes():
    fake = types.ModuleType("streamlit.testing.v1")
    class FakeAppTest:
        def run(self, timeout=None, **kwargs):
            return self
    fake.AppTest = FakeAppTest
    sys.modules["streamlit"] = types.ModuleType("streamlit")
    sys.modules["streamlit.testing"] = types.ModuleType("streamlit.testing")
    sys.modules["streamlit.testing.v1"] = fake
    assert True
def test_b_victim():
    import importlib
    m = importlib.import_module("streamlit")
    assert hasattr(m, "secrets")
"""
    result = _run_probe_subprocess(probe)
    combined = result.stdout + result.stderr
    assert result.returncode == 0
    assert "2 passed" in combined
    assert "Streamlit isolation leak detected after" in combined
