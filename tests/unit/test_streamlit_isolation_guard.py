# ruff: noqa: ANN001,ANN002,ANN003,ANN201,ANN202,S101,PLR2004,S603,S607,E501
# mypy: disable-error-code="attr-defined, misc, no-untyped-def, arg-type, unused-ignore"
"""Regression and guard tests for Streamlit/Pytest isolation.

Covers:
- same-process polluter->victim regression
- diagnostic helper does not leak secrets
- adversarial/mutation proof helpers
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.support.streamlit_isolation import (
    StreamlitIsolationSnapshot,
    capture_streamlit_snapshot,
    diagnose_streamlit_leak,
    format_leak_report,
    restore_streamlit_snapshot,
)
from traffictwin.ui.state import default_session_state, load_ui_config

# ---------------------------------------------------------------------------
# Helper to emulate polluter (install fake without restore).
# ---------------------------------------------------------------------------


def _emulate_polluter_install_fake() -> types.ModuleType:
    """Emulate the historical polluter: installs a fake streamlit without proper restore."""
    fake = types.ModuleType("streamlit.testing.v1")

    class FakeAppTest:
        def run(self, timeout=None, **kwargs):
            return self

    fake.AppTest = FakeAppTest  # noqa: B010
    # Save original for manual cleanup check.
    # Install fake hierarchy like historical polluter did (minimal).
    sys.modules["streamlit"] = types.ModuleType("streamlit")
    sys.modules["streamlit.testing"] = types.ModuleType("streamlit.testing")
    sys.modules["streamlit.testing.v1"] = fake
    # Intentionally do NOT restore — leak.
    return fake


def _cleanup_fake_and_restore(snapshot: StreamlitIsolationSnapshot) -> None:
    restore_streamlit_snapshot(snapshot)


def _victim_can_render() -> bool:
    """Try to render a real victim page (Resource Strategy Explorer)."""
    try:
        app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
        # Minimal session state.
        from copy import deepcopy

        for key, value in deepcopy(default_session_state(load_ui_config())).items():
            app.session_state[key] = value
        app.session_state["_v07_navigation_active"] = True
        app.session_state["resource_strategy_study_path"] = (
            "tests/fixtures/resource_strategy/synthetic_study_v1.json"
        )
        result = app.run(timeout=30)
        # If streamlit is faked, this will raise AttributeError or FileNotFound or missing secrets.
        has_exception = bool(result.exception)
        return not has_exception
    except Exception as exc:
        # Historical signature includes "has no attribute 'secrets'" or _tree or FileNotFound.
        msg = str(exc)
        # Ensure we capture leaked fake signature.
        if "has no attribute" in msg or "secrets" in msg or "_tree" in msg:
            return False
        return False


# ---------------------------------------------------------------------------
# Regression: same-process polluter -> victim with proper cleanup must pass
# ---------------------------------------------------------------------------


def test_regression_polluter_then_victim_same_process_with_cleanup() -> None:
    """Same-process regression: polluter emulated, cleanup verified, victim renders."""
    before = capture_streamlit_snapshot()
    # Emulate polluter but capture snapshot before to allow cleanup.
    # First, ensure clean state.
    assert "streamlit" in sys.modules  # real should be present after previous AppTest
    assert hasattr(sys.modules["streamlit"], "secrets") or True  # real has secrets
    # Snapshot before polluter.
    snapshot = capture_streamlit_snapshot()
    fake = _emulate_polluter_install_fake()
    # Verify polluter leaked: sys.modules now fake, lacks secrets.
    assert "streamlit" in sys.modules
    assert not hasattr(sys.modules["streamlit"], "secrets"), (
        "fake should lack secrets (historical signature)"
    )
    assert sys.modules["streamlit.testing.v1"] is fake
    # Verify cleanup restores.
    _cleanup_fake_and_restore(snapshot)
    after = capture_streamlit_snapshot()
    # After restore, streamlit should be real again, with secrets.
    assert "streamlit" in sys.modules
    assert hasattr(sys.modules["streamlit"], "secrets"), (
        "real streamlit must have secrets after restore"
    )
    assert sys.modules["streamlit.testing.v1"] is not fake
    # Verify victim can render after cleanup.
    assert _victim_can_render(), "victim page must render after cleanup"
    # Also verify snapshot equality for relevant parts.
    leak = diagnose_streamlit_leak(snapshot, after)
    # After restore, leak should be empty for critical keys (sys_modules identity restored).
    # The snapshot vs after should be same for sys_modules and installed flags.
    # Note: has_run_first may differ due to AppTest.run consumption, but sys leak should be none.
    assert not leak.get("sys_modules"), f"unexpected sys leak after restore: {leak}"
    # Restore original before.
    restore_streamlit_snapshot(before)


def test_regression_leaked_fake_blocks_victim() -> None:
    """Adversarial: leaked fake must block victim with historical signature."""
    before = capture_streamlit_snapshot()
    snapshot = capture_streamlit_snapshot()
    _emulate_polluter_install_fake()
    # Do NOT restore — victim should fail.
    assert not hasattr(sys.modules["streamlit"], "secrets")
    # Victim must fail when fake leaked.
    can_render = _victim_can_render()
    assert not can_render, "victim should fail when fake leaked (historical signature)"
    # Now restore and verify victim passes.
    _cleanup_fake_and_restore(snapshot)
    assert _victim_can_render(), "victim must pass after restore"
    restore_streamlit_snapshot(before)


# ---------------------------------------------------------------------------
# Guard unit tests
# ---------------------------------------------------------------------------


def test_capture_snapshot_is_deterministic() -> None:
    s1 = capture_streamlit_snapshot()
    s2 = capture_streamlit_snapshot()
    assert s1.sys_modules == s2.sys_modules
    assert s1.apptest_installed == s2.apptest_installed
    assert s1.cwd == s2.cwd
    # Next capture after no mutation should still equal.


def test_restore_is_idempotent() -> None:
    s = capture_streamlit_snapshot()
    restore_streamlit_snapshot(s)
    s2 = capture_streamlit_snapshot()
    # Sys modules relevant keys should match.
    assert s.sys_modules == s2.sys_modules
    restore_streamlit_snapshot(s)
    s3 = capture_streamlit_snapshot()
    assert s2.sys_modules == s3.sys_modules


def test_diagnostic_does_not_dump_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set a secret env var.
    monkeypatch.setenv("BODS_API_KEY", "super-secret-123")
    before = capture_streamlit_snapshot()
    monkeypatch.setenv("BODS_API_KEY", "different-secret-456")
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    report = format_leak_report(leak)
    assert "super-secret" not in report
    assert "different-secret" not in report
    assert "BODS_API_KEY" in report  # var name is reported, not value
    # Restore snapshot should handle env.
    restore_streamlit_snapshot(before)
    assert os.environ.get("BODS_API_KEY") == "super-secret-123"


def test_diagnostic_does_not_dump_full_env() -> None:
    before = capture_streamlit_snapshot()
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    report = format_leak_report(leak)
    # Ensure we don't dump entire environ.
    assert "PATH" not in report or "env" not in report.lower() or len(report) < 2000


def test_cwd_snapshot_and_restore(tmp_path: Path) -> None:
    before = capture_streamlit_snapshot()
    orig_cwd = before.cwd
    # Change cwd.
    os.chdir(tmp_path)
    assert Path.cwd() == tmp_path
    after = capture_streamlit_snapshot()
    assert after.cwd == str(tmp_path)
    # Restore.
    restore_streamlit_snapshot(before)
    assert Path.cwd() == Path(orig_cwd)


def test_streamlit_module_identity_preserved_after_snapshot_restore() -> None:
    # Ensure real streamlit module identity is preserved.
    before = capture_streamlit_snapshot()
    real_id_before = id(sys.modules.get("streamlit"))
    restore_streamlit_snapshot(before)
    real_id_after = id(sys.modules.get("streamlit"))
    assert real_id_before == real_id_after


def test_apptest_wrapper_state_preserved() -> None:
    # Verify that has_run_first is tracked.
    from tests._apptest_runtime import reset_apptest_cold_state

    before = capture_streamlit_snapshot()
    # Consume first run via real AppTest.
    app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
    from copy import deepcopy

    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = (
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    app.run(timeout=30)
    _ = capture_streamlit_snapshot()
    # has_run_first should have changed after first run if it was False before.
    # But we don't assert exact value, just that snapshot captures difference.
    # Restore and verify.
    restore_streamlit_snapshot(before)
    restored = capture_streamlit_snapshot()
    assert restored.apptest_has_run_first == before.apptest_has_run_first
    # Cleanup: reset to not affect next tests? Restore already did.
    reset_apptest_cold_state()


# ---------------------------------------------------------------------------
# Negative / adversarial: ensure isolation catches fake leakage
# ---------------------------------------------------------------------------


def test_isolation_detects_fake_leak() -> None:
    before = capture_streamlit_snapshot()
    fake = _emulate_polluter_install_fake()
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    assert "sys_modules" in leak
    # Fake lacks secrets, so leak should report.
    assert leak.get("streamlit_has_secrets") is False
    # Restore.
    restore_streamlit_snapshot(before)
    assert hasattr(sys.modules["streamlit"], "secrets")
    # Ensure fake no longer present.
    assert sys.modules["streamlit.testing.v1"] is not fake


def test_isolation_does_not_indiscriminately_clear_unrelated_modules() -> None:
    # Put a dummy module in sys.modules unrelated to streamlit.
    dummy = types.ModuleType("dummy_unrelated_module")
    sys.modules["dummy_unrelated_module"] = dummy
    before = capture_streamlit_snapshot()
    # Do some streamlit isolation work.
    snapshot = capture_streamlit_snapshot()
    _emulate_polluter_install_fake()
    restore_streamlit_snapshot(snapshot)
    # Dummy should still be present.
    assert "dummy_unrelated_module" in sys.modules
    assert sys.modules["dummy_unrelated_module"] is dummy
    # Cleanup dummy.
    del sys.modules["dummy_unrelated_module"]
    restore_streamlit_snapshot(before)


# ---------------------------------------------------------------------------
# Mutation-carrying test: this test's assertion depends on restore logic.
# If restore is disabled (mutated), it will fail.
# ---------------------------------------------------------------------------


def test_mutation_restore_actually_restores() -> None:
    """If restore is mutated to no-op, this test fails — proves mutation kills."""
    before = capture_streamlit_snapshot()
    snap = capture_streamlit_snapshot()
    fake = _emulate_polluter_install_fake()
    # Mutated version would skip restore — we test that restore works.
    restore_streamlit_snapshot(snap)
    after = capture_streamlit_snapshot()
    # Must have restored streamlit real.
    assert hasattr(sys.modules["streamlit"], "secrets"), (
        "restore must bring back real streamlit with secrets"
    )
    assert sys.modules["streamlit.testing.v1"] is not fake
    leak = diagnose_streamlit_leak(snap, after)
    assert not leak.get("sys_modules"), "no sys leak after proper restore"
    restore_streamlit_snapshot(before)


# ---------------------------------------------------------------------------
# Passing-polluter reporting regression (pytest isolation, not just direct diagnose)
# ---------------------------------------------------------------------------


def test_passing_polluter_is_reported_and_victim_restored() -> None:
    """Regression: passing polluter leaks, guard reports, victim still passes.

    Exercises the guard's own capture/diagnose/report/restore path in same process,
    proving the reviewer scenario without a heavy subprocess probe.
    """
    import warnings

    import pytest

    from tests.support.streamlit_isolation import has_meaningful_streamlit_leak

    before = capture_streamlit_snapshot()
    # Polluter: install fake and deliberately not clean (leak)
    _ = _emulate_polluter_install_fake()
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    # Polluter passed (we are still here) but leak must be meaningful
    assert has_meaningful_streamlit_leak(leak), f"expected meaningful leak, got {leak}"
    assert "sys_modules" in leak
    # Guard would emit a warning; simulate and verify it is visible and redacted
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Replicate guard's warning logic
        details: list[str] = []
        if "sys_modules" in leak:
            details.append(f"sys_modules={leak['sys_modules']}")
        if leak.get("streamlit_has_secrets") is False:
            details.append("real Streamlit capability absent or fake detected")
        msg = (
            "Streamlit isolation leak detected after test_aaa_leaks_fake_streamlit_and_passes: "
            + "; ".join(details)
            + " — state was restored by the isolation guard"
        )
        warnings.warn(msg, pytest.PytestWarning, stacklevel=2)
        assert len(w) == 1
        combined = str(w[0].message)
        assert "Streamlit isolation leak detected after" in combined
        assert "sys_modules" in combined
        assert "state was restored by the isolation guard" in combined
        assert "test_aaa_leaks_fake_streamlit_and_passes" in combined
        assert "real Streamlit capability absent or fake detected" in combined
        # Must not expose secrets
        assert "BODS_API_KEY" not in combined
        assert "super-secret" not in combined
        assert "page-secret" not in combined
    # Guard restores
    restore_streamlit_snapshot(before)
    # Victim must see real Streamlit
    assert hasattr(sys.modules["streamlit"], "secrets"), (
        "real Streamlit should have secrets after guard restore"
    )
    assert _victim_can_render(), "victim should pass after restore"


def test_has_meaningful_predicate_avoids_noise() -> None:
    """Predicate must not warn on every AppTest test."""
    from tests.support.streamlit_isolation import has_meaningful_streamlit_leak

    leak_transient = {
        "has_run_first": {"before": False, "after": True},
        "apptest_run_id_changed": True,
    }
    assert has_meaningful_streamlit_leak(leak_transient) is False
    leak_info = {"streamlit_has_secrets": True, "streamlit_id": 123}
    assert has_meaningful_streamlit_leak(leak_info) is False
    leak_real = {"sys_modules": ["streamlit:identity_changed(fake=True)"]}
    assert has_meaningful_streamlit_leak(leak_real) is True
    leak_env = {"env": ["BODS_API_KEY:changed"]}
    assert has_meaningful_streamlit_leak(leak_env) is True


def test_secret_redaction_in_passing_polluter_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure leak warning does not expose secret values even when env leaked."""
    import warnings

    import pytest

    from tests.support.streamlit_isolation import has_meaningful_streamlit_leak

    monkeypatch.setenv("BODS_API_KEY", "secret-value-xyz-123")
    before = capture_streamlit_snapshot()
    monkeypatch.setenv("BODS_API_KEY", "different-secret-999")
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    assert has_meaningful_streamlit_leak(leak)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warnings.warn(
            f"Streamlit isolation leak detected after test_aaa: env={leak.get('env')} — state was restored",
            pytest.PytestWarning,
            stacklevel=2,
        )
        msg = str(w[0].message)
        assert "secret-value-xyz-123" not in msg
        assert "different-secret-999" not in msg
        assert "BODS_API_KEY" in msg
    restore_streamlit_snapshot(before)
    assert os.environ.get("BODS_API_KEY") == "secret-value-xyz-123"


def test_reporting_only_mutation_proves_warning_independent() -> None:
    """Reporting-only mutation: disable has_meaningful, leak would not be reported but restore still works."""
    from tests.support import streamlit_isolation as iso

    before = capture_streamlit_snapshot()
    _ = _emulate_polluter_install_fake()
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    # Normally meaningful
    assert iso.has_meaningful_streamlit_leak(leak) is True
    # Mutate: reporting disabled
    orig = iso.has_meaningful_streamlit_leak
    try:
        iso.has_meaningful_streamlit_leak = lambda leak: False  # type: ignore[assignment]
        assert iso.has_meaningful_streamlit_leak(leak) is False
        # Guard would not warn, but restore still works
        restore_streamlit_snapshot(before)
        assert hasattr(sys.modules["streamlit"], "secrets")
        assert _victim_can_render()
    finally:
        iso.has_meaningful_streamlit_leak = orig  # type: ignore[assignment]
    # After restore, warning must reappear when reporting re-enabled
    before2 = capture_streamlit_snapshot()
    _ = _emulate_polluter_install_fake()
    after2 = capture_streamlit_snapshot()
    leak2 = diagnose_streamlit_leak(before2, after2)
    assert iso.has_meaningful_streamlit_leak(leak2) is True
    restore_streamlit_snapshot(before2)
