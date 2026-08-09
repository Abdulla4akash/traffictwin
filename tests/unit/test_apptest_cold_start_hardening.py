# ruff: noqa: ANN001,ANN002,ANN003,ANN201,ANN202,ANN101,S603,S607,PLR2004,E501,N802,F841,S110,SIM105
# mypy: disable-error-code="attr-defined, misc, operator, assignment, call-arg, unused-ignore, no-untyped-def"
"""Regression tests for AppTest cold-start hardening — real installer.

Pure helper tests may pass with ``--noconftest``; all wrapper tests exercise
the shipped installer from ``tests._apptest_runtime`` over a fake
``streamlit.testing.v1.AppTest``. No test validates a private copy.
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

from tests._apptest_runtime import COLD_FLOOR_SECONDS, effective_timeout

# ---------------------------------------------------------------------------
# Pure helper — may pass without plugin (allowed)
# ---------------------------------------------------------------------------


def test_effective_timeout_first_10_receives_floor() -> None:
    assert effective_timeout(10, is_first=True) == COLD_FLOOR_SECONDS


def test_effective_timeout_second_10_remains_10() -> None:
    assert effective_timeout(10, is_first=False) == 10


def test_effective_timeout_first_above_floor_unchanged() -> None:
    assert effective_timeout(80, is_first=True) == 80
    assert effective_timeout(90, is_first=True) == 90


def test_effective_timeout_never_reduced() -> None:
    for req in [10, 20, 60, 80, 100]:
        assert effective_timeout(req, is_first=True) >= req
        assert effective_timeout(req, is_first=False) == req
    assert effective_timeout(None, is_first=True) == COLD_FLOOR_SECONDS
    assert effective_timeout(None, is_first=False) == 10


def test_effective_timeout_later_25_remains_25() -> None:
    assert effective_timeout(25, is_first=False) == 25
    assert effective_timeout(25, is_first=True) == COLD_FLOOR_SECONDS


# ---------------------------------------------------------------------------
# Lazy guarantees A & B — pure, no Streamlit import
# ---------------------------------------------------------------------------


def test_importing_conftest_does_not_import_streamlit() -> None:
    """A. Importing tests.conftest alone does not place streamlit in sys.modules."""
    repo_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "before = 'streamlit' in sys.modules; "
        "import tests.conftest; "
        "after = 'streamlit' in sys.modules; "
        "print(f'BEFORE:{before} AFTER:{after}'); "
        "assert not after, 'conftest imported streamlit at module import'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"failed:\n{result.stdout}\n{result.stderr}"
    assert "AFTER:False" in result.stdout


def test_collecting_pure_unit_does_not_import_streamlit() -> None:
    """B. Collecting a pure-unit test does not import Streamlit via plugin."""
    repo_root = Path(__file__).resolve().parents[2]
    # Use a helper script that runs pytest --collect-only and checks sys.modules
    helper = (
        "import sys; sys.path.insert(0, '.'); "
        "import pytest; "
        "from tests._apptest_runtime import is_patched; "
        "ret = pytest.main(['--collect-only', '-q', 'tests/unit/test_whatif_pair.py', '-p', 'no:cacheprovider']); "
        "has = 'streamlit' in sys.modules or 'streamlit.testing.v1' in sys.modules; "
        "print(f'HAS:{has} PATCHED:{is_patched()}'); "
        "assert not has, 'pure collection imported streamlit'; "
        "assert not is_patched(), 'pure collection installed patch'"
    )
    result = subprocess.run(
        [sys.executable, "-c", helper],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"failed:\n{result.stdout}\n{result.stderr}"
    assert "HAS:False" in result.stdout


# ---------------------------------------------------------------------------
# Wrapper installed before first run (C), once (D), restored (E)
# ---------------------------------------------------------------------------


def test_wrapper_installed_before_first_run_via_import_hook() -> None:
    """C. After importing streamlit.testing.v1, wrapper is installed before run."""
    # This test itself has already imported streamlit via previous tests? To avoid
    # pollution we check in a fresh subprocess.
    repo_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "import tests.conftest; "
        "from tests._apptest_runtime import is_patched; "
        "assert not is_patched(), 'should start unpatched'; "
        "import importlib; m = importlib.import_module('streamlit.testing.v1'); "
        "from tests._apptest_runtime import is_patched as ip2; "
        "print(f'PATCHED:{ip2()}'); "
        "assert ip2(), 'wrapper not installed after streamlit import'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"failed:\n{result.stdout}\n{result.stderr}"
    assert "PATCHED:True" in result.stdout


def test_wrapper_installed_once_idempotent() -> None:
    """D. Installer is idempotent — second install does not double-wrap."""

    # Ensure clean state for this test (use fake to avoid touching real AppTest twice)
    # We test idempotence via fake module.
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch as inst

        assert inst() is True
        first_run = sys.modules["streamlit.testing.v1"].AppTest.run
        assert inst() is True
        second_run = sys.modules["streamlit.testing.v1"].AppTest.run
        assert first_run is second_run, "second install double-wrapped"
        assert getattr(second_run, "_is_cold_patched", False) is True
    finally:
        _uninstall_fake(fake)


def test_wrapper_restored_at_session_end_via_uninstall() -> None:
    """E. uninstall restores the exact original method."""
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import (
            install_apptest_run_patch,
            uninstall_apptest_run_patch,
        )

        orig = sys.modules["streamlit.testing.v1"].AppTest.run
        install_apptest_run_patch()
        patched = sys.modules["streamlit.testing.v1"].AppTest.run
        assert patched is not orig
        uninstall_apptest_run_patch()
        restored = sys.modules["streamlit.testing.v1"].AppTest.run
        assert restored is orig
        assert not getattr(restored, "_is_cold_patched", False)
    finally:
        _uninstall_fake(fake)


# ---------------------------------------------------------------------------
# Helpers for fake AppTest
# ---------------------------------------------------------------------------

_saved_modules: dict[str, object] = {}


def _make_fake_module() -> types.ModuleType:
    """Create a fake ``streamlit.testing.v1`` module with a spied AppTest."""

    # Use a simple class with run that records calls
    class FakeAppTest:
        def __init__(self) -> None:
            self.last_timeout: float | None = None
            self.last_kwargs: dict[str, object] = {}
            self.call_count = 0
            self.return_sentinel = object()
            self.raise_on_timeout: float | None = None
            self.raise_exc: type[BaseException] | None = None

        def run(self, *args, timeout: float | None = None, **kwargs):  # type: ignore[no-untyped-def]
            self.call_count += 1
            self.last_timeout = timeout
            self.last_kwargs = dict(kwargs)
            # Preserve args check
            if args:
                # store for assertion
                self.last_kwargs["_args"] = args
            if self.raise_exc is not None and timeout == self.raise_on_timeout:
                raise self.raise_exc("boom")  # type: ignore[operator]
            if timeout == 999 and self.raise_exc is None:
                # Legacy sentinel for generic boom
                raise RuntimeError("boom")
            return self.return_sentinel

    mod = types.ModuleType("streamlit.testing.v1")
    mod.AppTest = FakeAppTest
    # Also need parent packages
    pkg_streamlit = types.ModuleType("streamlit")
    pkg_testing = types.ModuleType("streamlit.testing")
    # Mark as packages
    pkg_streamlit.testing = pkg_testing
    pkg_testing.v1 = mod
    return mod


def _install_fake(fake_mod: types.ModuleType) -> None:
    # Save originals
    for name in ("streamlit", "streamlit.testing", "streamlit.testing.v1"):
        _saved_modules[name] = sys.modules.get(name)
    # Install fake hierarchy
    sys.modules["streamlit"] = types.ModuleType("streamlit")
    sys.modules["streamlit"].testing = sys.modules.get("streamlit.testing") or types.ModuleType(  # type: ignore[attr-defined]
        "streamlit.testing"
    )
    sys.modules["streamlit.testing"] = sys.modules["streamlit"].testing
    sys.modules["streamlit.testing.v1"] = fake_mod
    # Reset installer state
    from tests._apptest_runtime import reset_apptest_cold_state, uninstall_apptest_run_patch

    try:
        uninstall_apptest_run_patch()
    except Exception:
        pass
    reset_apptest_cold_state()


def _uninstall_fake(fake_mod: types.ModuleType) -> None:  # noqa: ARG001
    from tests._apptest_runtime import reset_apptest_cold_state, uninstall_apptest_run_patch

    try:
        uninstall_apptest_run_patch()
    except Exception:
        pass
    reset_apptest_cold_state()
    for name, orig in list(_saved_modules.items()):
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig  # type: ignore[assignment]
    _saved_modules.clear()


# ---------------------------------------------------------------------------
# Real wrapper contract tests — install real wrapper over fake
# ---------------------------------------------------------------------------


def test_wrapper_first_timeout_10_becomes_60() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.run(timeout=10)
        assert inst.last_timeout == COLD_FLOOR_SECONDS
    finally:
        _uninstall_fake(fake)


def test_wrapper_second_timeout_10_remains_10() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.run(timeout=10)  # first -> 60
        assert inst.last_timeout == 60
        inst2 = sys.modules["streamlit.testing.v1"].AppTest()
        inst2.run(timeout=10)  # second -> 10
        assert inst2.last_timeout == 10
    finally:
        _uninstall_fake(fake)


def test_wrapper_later_timeout_25_remains_25() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.run(timeout=10)  # consume first
        inst2 = sys.modules["streamlit.testing.v1"].AppTest()
        inst2.run(timeout=25)
        assert inst2.last_timeout == 25
    finally:
        _uninstall_fake(fake)


def test_wrapper_first_timeout_90_remains_90() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.run(timeout=90)
        assert inst.last_timeout == 90
    finally:
        _uninstall_fake(fake)


def test_wrapper_never_reduces_timeout() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        for req in [10, 20, 60, 80, 100]:
            # need fresh state per req? Use reset
            from tests._apptest_runtime import reset_apptest_cold_state

            reset_apptest_cold_state()
            inst = sys.modules["streamlit.testing.v1"].AppTest()
            inst.run(timeout=req)
            assert inst.last_timeout >= req
            # second call in same process should equal req
            inst2 = sys.modules["streamlit.testing.v1"].AppTest()
            inst2.run(timeout=req)
            assert inst2.last_timeout == req
    finally:
        _uninstall_fake(fake)


def test_wrapper_calls_original_exactly_once() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.run(timeout=10)
        assert inst.call_count == 1
        inst2 = sys.modules["streamlit.testing.v1"].AppTest()
        inst2.run(timeout=10)
        assert inst2.call_count == 1
    finally:
        _uninstall_fake(fake)


def test_wrapper_preserves_args_and_kwargs() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        # Pass extra kwarg
        inst.run(timeout=10, extra="value", flag=True)  # type: ignore[call-arg, misc]
        assert inst.last_kwargs.get("extra") == "value"
        assert inst.last_kwargs.get("flag") is True
        # Timeout should still be floored
        assert inst.last_timeout == 60
    finally:
        _uninstall_fake(fake)


def test_wrapper_preserves_return_value() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        ret = inst.run(timeout=10)
        assert ret is inst.return_sentinel
    finally:
        _uninstall_fake(fake)


def test_wrapper_preserves_runtime_error() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.raise_exc = RuntimeError
        inst.raise_on_timeout = COLD_FLOOR_SECONDS  # first call will be floored to 60, so trigger
        with pytest.raises(RuntimeError, match="boom"):
            inst.run(timeout=10)
        # Ensure first-run consumed
        from tests._apptest_runtime import get_has_run_first

        assert get_has_run_first() is True
        # Next call should not be floored
        inst2 = sys.modules["streamlit.testing.v1"].AppTest()
        # Make second not raise
        inst2.raise_exc = None
        inst2.run(timeout=10)
        assert inst2.last_timeout == 10
    finally:
        _uninstall_fake(fake)


def test_wrapper_preserves_arbitrary_exception() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.raise_exc = ValueError
        inst.raise_on_timeout = COLD_FLOOR_SECONDS
        with pytest.raises(ValueError, match="boom"):
            inst.run(timeout=10)
    finally:
        _uninstall_fake(fake)


def test_wrapper_installer_idempotent() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        assert install_apptest_run_patch() is True
        first = sys.modules["streamlit.testing.v1"].AppTest.run
        assert install_apptest_run_patch() is True
        second = sys.modules["streamlit.testing.v1"].AppTest.run
        assert first is second
    finally:
        _uninstall_fake(fake)


def test_wrapper_uninstall_restores_exact_original() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch, uninstall_apptest_run_patch

        orig = sys.modules["streamlit.testing.v1"].AppTest.run
        install_apptest_run_patch()
        patched = sys.modules["streamlit.testing.v1"].AppTest.run
        assert patched is not orig
        uninstall_apptest_run_patch()
        restored = sys.modules["streamlit.testing.v1"].AppTest.run
        assert restored is orig
    finally:
        _uninstall_fake(fake)


def test_wrapper_reset_gives_new_first_allowance() -> None:
    fake = _make_fake_module()
    _install_fake(fake)
    try:
        from tests._apptest_runtime import install_apptest_run_patch, reset_apptest_cold_state

        install_apptest_run_patch()
        inst = sys.modules["streamlit.testing.v1"].AppTest()
        inst.run(timeout=10)
        assert inst.last_timeout == 60
        inst2 = sys.modules["streamlit.testing.v1"].AppTest()
        inst2.run(timeout=10)
        assert inst2.last_timeout == 10
        reset_apptest_cold_state()
        inst3 = sys.modules["streamlit.testing.v1"].AppTest()
        inst3.run(timeout=10)
        assert inst3.last_timeout == 60
    finally:
        _uninstall_fake(fake)


def test_wrapper_install_does_not_call_apptest() -> None:
    fake = _make_fake_module()
    _install_fake(fake)

    # Create a fake where run would record if called
    class CountingFake:
        call_count = 0

        def run(self, *args, timeout=None, **kwargs):  # type: ignore[no-untyped-def]
            CountingFake.call_count += 1
            return self

    fake_mod2 = types.ModuleType("streamlit.testing.v1")
    fake_mod2.AppTest = CountingFake  # type: ignore[attr-defined]
    # Reinstall with this counting fake
    for name in ("streamlit", "streamlit.testing", "streamlit.testing.v1"):
        _saved_modules[name] = sys.modules.get(name)
    sys.modules["streamlit"] = types.ModuleType("streamlit")
    sys.modules["streamlit.testing"] = types.ModuleType("streamlit.testing")
    sys.modules["streamlit.testing.v1"] = fake_mod2
    from tests._apptest_runtime import reset_apptest_cold_state, uninstall_apptest_run_patch

    try:
        uninstall_apptest_run_patch()
    except Exception:
        pass
    reset_apptest_cold_state()
    try:
        from tests._apptest_runtime import install_apptest_run_patch

        install_apptest_run_patch()
        assert CountingFake.call_count == 0, "install called AppTest.run"
    finally:
        try:
            uninstall_apptest_run_patch()
        except Exception:
            pass
        reset_apptest_cold_state()
        for name, orig in list(_saved_modules.items()):
            if orig is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = orig  # type: ignore[assignment]
        _saved_modules.clear()


# ---------------------------------------------------------------------------
# Fail-closed helper import
# ---------------------------------------------------------------------------


def test_broken_helper_import_fails_closed() -> None:
    """A broken tests._apptest_runtime must fail loudly, not be swallowed."""
    repo_root = Path(__file__).resolve().parents[2]
    # Simulate broken helper by temporarily making the file raise on import
    # via a subprocess that injects a broken module into sys.modules before
    # importing conftest. We do this by creating a temp helper that raises.
    code = (
        "import sys; "
        "import types; "
        "broken = types.ModuleType('tests._apptest_runtime'); "
        "broken.__dict__['__file__'] = 'broken'; "
        "exec('raise ImportError(\"simulated helper breakage\")', broken.__dict__); "
        "sys.modules['tests._apptest_runtime'] = broken; "
        "import tests.conftest; "
        "print('UNREACHABLE')"
    )
    # Instead test directly: importing the real helper with a syntax error
    # should raise. We verify that conftest does not swallow ImportError for helper.
    # Check conftest source does not contain broad swallow.
    text = Path(repo_root / "tests" / "conftest.py").read_text()
    assert "except ImportError:" not in text or "streamlit" in text.lower(), (
        "conftest must not swallow helper ImportError"
    )
    # Also verify that a subprocess with broken helper fails
    # Create a temporary copy of the repo where helper is broken, run collect
    import shutil
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td) / "repo"
        shutil.copytree(
            repo_root,
            td_path,
            ignore=shutil.ignore_patterns(".venv", "__pycache__", ".git", ".pytest_cache"),
        )
        # Break helper
        helper_path = td_path / "tests" / "_apptest_runtime.py"
        helper_path.write_text("raise ImportError('simulated helper breakage')\n")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "tests/unit/test_apptest_cold_start_hardening.py",
            ],
            cwd=td_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should fail (non-zero) and mention helper breakage
        assert result.returncode != 0, (
            f"broken helper should fail closed but got {result.returncode}\n{result.stdout}\n{result.stderr}"
        )
        assert "simulated helper" in result.stdout or "simulated helper" in result.stderr


# ---------------------------------------------------------------------------
# Real process-state test — each process gets its own first-run allowance
# ---------------------------------------------------------------------------


def test_process_state_resets_between_processes_via_subprocess() -> None:
    """Each independent process observes its own first call receiving the floor."""
    repo_root = Path(__file__).resolve().parents[2]
    import tempfile

    helper_code = (
        "import sys, types\n"
        "sys.path.insert(0, '.')\n"
        "from tests._apptest_runtime import install_apptest_run_patch, reset_apptest_cold_state\n"
        "import sys as _sys\n"
        "fake = types.ModuleType('streamlit.testing.v1')\n"
        "class F:\n"
        "    last = None\n"
        "    def run(self, *a, timeout=None, **kw):\n"
        "        self.last = timeout\n"
        "        return self\n"
        "fake.AppTest = F\n"
        "_sys.modules['streamlit'] = types.ModuleType('streamlit')\n"
        "_sys.modules['streamlit.testing'] = types.ModuleType('streamlit.testing')\n"
        "_sys.modules['streamlit.testing.v1'] = fake\n"
        "reset_apptest_cold_state()\n"
        "install_apptest_run_patch()\n"
        "a = F(); a.run(timeout=10); first = a.last\n"
        "b = F(); b.run(timeout=10); second = b.last\n"
        "print(f'FIRST:{first} SECOND:{second}')\n"
        "assert first == 60 and second == 10\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        tf.write(helper_code)
        tf_path = tf.name
    try:
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, tf_path],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, f"failed:\n{result.stdout}\n{result.stderr}"
            assert "FIRST:60 SECOND:10" in result.stdout
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_real_plugin_patch_active_in_current_process() -> None:
    """Discriminating: real AppTest is patched when plugin is enabled."""
    # This must fail with --noconftest, proving test power
    from streamlit.testing.v1 import AppTest

    from tests._apptest_runtime import is_patched

    assert is_patched(), "plugin did not install patch before first AppTest.run"
    assert getattr(AppTest.run, "_is_cold_patched", False), "AppTest.run not patched"


def test_auto_install_for_real_apptest_is_visible() -> None:
    """Integration: real AppTest gets patched before first run (without manual install)."""
    repo_root = Path(__file__).resolve().parents[2]
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "import tests.conftest; "
        "from tests._apptest_runtime import is_patched; "
        "# Before importing streamlit, not patched\n"
        "assert not is_patched(); "
        "from streamlit.testing.v1 import AppTest; "
        "from tests._apptest_runtime import is_patched as ip2; "
        "print(f'PATCHED:{ip2()} MARK:{getattr(AppTest.run, \"_is_cold_patched\", False)}'); "
        "assert ip2() and getattr(AppTest.run, '_is_cold_patched', False)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"failed:\n{result.stdout}\n{result.stderr}"
    assert "PATCHED:True" in result.stdout
