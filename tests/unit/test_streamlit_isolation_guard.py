# mypy: disable-error-code="attr-defined, misc, no-untyped-def, arg-type,"
# mypy: disable-error-code="unused-ignore, operator, assignment, call-arg"
"""Regression and guard tests for Streamlit/Pytest isolation.

Covers:
- same-process polluter->victim regression (with AppTest rendering)
- diagnostic helper does not leak secrets
- adversarial/mutation proof helpers
- helper-level meaningful-leak predicate

Subprocess proofs are in ``test_streamlit_isolation_subprocess.py`` to avoid
parent-process AppTest poisoning (BLOCKER B1).
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
        def run(self, timeout=None, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
            return self

    fake.AppTest = FakeAppTest  # noqa: B010
    sys.modules["streamlit"] = types.ModuleType("streamlit")
    sys.modules["streamlit.testing"] = types.ModuleType("streamlit.testing")
    sys.modules["streamlit.testing.v1"] = fake
    return fake


def _cleanup_fake_and_restore(snapshot: StreamlitIsolationSnapshot) -> None:
    restore_streamlit_snapshot(snapshot)


def _victim_can_render() -> bool:
    """Try to render a real victim page (Resource Strategy Explorer)."""
    try:
        app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
        from copy import deepcopy

        for key, value in deepcopy(default_session_state(load_ui_config())).items():
            app.session_state[key] = value
        app.session_state["_v07_navigation_active"] = True
        app.session_state["resource_strategy_study_path"] = (
            "tests/fixtures/resource_strategy/synthetic_study_v1.json"
        )
        result = app.run(timeout=30)
        has_exception = bool(result.exception)
        return not has_exception
    except Exception as exc:
        msg = str(exc)
        if "has no attribute" in msg or "secrets" in msg or "_tree" in msg:
            return False
        return False


# ---------------------------------------------------------------------------
# Regression: same-process polluter -> victim with proper cleanup must pass
# ---------------------------------------------------------------------------


def test_regression_polluter_then_victim_same_process_with_cleanup() -> None:
    """Same-process regression: polluter emulated, cleanup verified, victim renders."""
    before = capture_streamlit_snapshot()
    assert "streamlit" in sys.modules
    assert hasattr(sys.modules["streamlit"], "secrets")
    snapshot = capture_streamlit_snapshot()
    fake = _emulate_polluter_install_fake()
    assert "streamlit" in sys.modules
    assert not hasattr(sys.modules["streamlit"], "secrets"), (
        "fake should lack secrets (historical signature)"
    )
    assert sys.modules["streamlit.testing.v1"] is fake
    _cleanup_fake_and_restore(snapshot)
    after = capture_streamlit_snapshot()
    assert "streamlit" in sys.modules
    assert hasattr(sys.modules["streamlit"], "secrets"), (
        "real streamlit must have secrets after restore"
    )
    assert sys.modules["streamlit.testing.v1"] is not fake
    assert _victim_can_render(), "victim page must render after cleanup"
    leak = diagnose_streamlit_leak(snapshot, after)
    assert not leak.get("sys_modules"), f"unexpected sys leak after restore: {leak}"
    restore_streamlit_snapshot(before)


def test_regression_leaked_fake_blocks_victim() -> None:
    """Adversarial: leaked fake must block victim with historical signature."""
    before = capture_streamlit_snapshot()
    snapshot = capture_streamlit_snapshot()
    _emulate_polluter_install_fake()
    assert not hasattr(sys.modules["streamlit"], "secrets")
    can_render = _victim_can_render()
    assert not can_render, "victim should fail when fake leaked (historical signature)"
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


def test_restore_is_idempotent() -> None:
    s = capture_streamlit_snapshot()
    restore_streamlit_snapshot(s)
    s2 = capture_streamlit_snapshot()
    assert s.sys_modules == s2.sys_modules
    restore_streamlit_snapshot(s)
    s3 = capture_streamlit_snapshot()
    assert s2.sys_modules == s3.sys_modules


def test_diagnostic_does_not_dump_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BODS_API_KEY", "super-secret-123")
    before = capture_streamlit_snapshot()
    monkeypatch.setenv("BODS_API_KEY", "different-secret-456")
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    report = format_leak_report(leak)
    assert "super-secret" not in report
    assert "different-secret" not in report
    assert "BODS_API_KEY" in report
    restore_streamlit_snapshot(before)
    assert os.environ.get("BODS_API_KEY") == "super-secret-123"


def test_diagnostic_does_not_dump_full_env() -> None:
    before = capture_streamlit_snapshot()
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    report = format_leak_report(leak)
    assert "PATH" not in report
    assert len(report) < 2000


def test_cwd_snapshot_and_restore(tmp_path: Path) -> None:
    before = capture_streamlit_snapshot()
    orig_cwd = before.cwd
    os.chdir(tmp_path)
    assert Path.cwd() == tmp_path
    after = capture_streamlit_snapshot()
    assert after.cwd == str(tmp_path)
    restore_streamlit_snapshot(before)
    assert Path.cwd() == Path(orig_cwd)


def test_streamlit_module_identity_preserved_after_snapshot_restore() -> None:
    before = capture_streamlit_snapshot()
    real_id_before = id(sys.modules.get("streamlit"))
    restore_streamlit_snapshot(before)
    real_id_after = id(sys.modules.get("streamlit"))
    assert real_id_before == real_id_after


def test_apptest_wrapper_has_run_first_is_process_scoped() -> None:
    """Process-scoped: first-run state must not be rewound per-test."""
    from tests._apptest_runtime import reset_apptest_cold_state

    before = capture_streamlit_snapshot()
    # Ensure clean start for this test.
    reset_apptest_cold_state()
    snap_before = capture_streamlit_snapshot()
    assert snap_before.apptest_has_run_first is False
    app = AppTest.from_file("src/traffictwin/ui/app_pages/resource_strategy.py")
    from copy import deepcopy

    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = (
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    app.run(timeout=30)
    snap_after = capture_streamlit_snapshot()
    assert snap_after.apptest_has_run_first is True
    # Guard would snapshot before, then restore after test — but must NOT rewind has_run_first.
    # Simulate guard restore: it should leave has_run_first True.
    restore_streamlit_snapshot(snap_before)
    snap_restored = capture_streamlit_snapshot()
    # New behavior: has_run_first remains True (process-scoped), not rewound to False.
    assert snap_restored.apptest_has_run_first is True, (
        "has_run_first must remain process-scoped and not be rewound per-test"
    )
    # Cleanup.
    reset_apptest_cold_state()
    restore_streamlit_snapshot(before)


# ---------------------------------------------------------------------------
# Negative / adversarial: ensure isolation catches fake leakage
# ---------------------------------------------------------------------------


def test_isolation_detects_fake_leak() -> None:
    before = capture_streamlit_snapshot()
    fake = _emulate_polluter_install_fake()
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    assert "sys_modules" in leak
    assert leak.get("streamlit_has_secrets") is False
    restore_streamlit_snapshot(before)
    assert hasattr(sys.modules["streamlit"], "secrets")
    assert sys.modules["streamlit.testing.v1"] is not fake


def test_isolation_does_not_indiscriminately_clear_unrelated_modules() -> None:
    dummy = types.ModuleType("dummy_unrelated_module")
    sys.modules["dummy_unrelated_module"] = dummy
    before = capture_streamlit_snapshot()
    snapshot = capture_streamlit_snapshot()
    _emulate_polluter_install_fake()
    restore_streamlit_snapshot(snapshot)
    assert "dummy_unrelated_module" in sys.modules
    assert sys.modules["dummy_unrelated_module"] is dummy
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
    restore_streamlit_snapshot(snap)
    after = capture_streamlit_snapshot()
    assert hasattr(sys.modules["streamlit"], "secrets"), (
        "restore must bring back real streamlit with secrets"
    )
    assert sys.modules["streamlit.testing.v1"] is not fake
    leak = diagnose_streamlit_leak(snap, after)
    assert not leak.get("sys_modules"), "no sys leak after proper restore"
    restore_streamlit_snapshot(before)


def test_has_meaningful_predicate_avoids_noise() -> None:
    """Predicate must not warn on every AppTest test; env alone is not meaningful."""
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
    # Env alone is NOT meaningful after MAJOR 5 fix
    leak_env = {"env": ["BODS_API_KEY:changed"]}
    assert has_meaningful_streamlit_leak(leak_env) is False
    leak_cwd = {"cwd": {"before": "/a", "after": "/b"}}  # noqa: S108 - test dummy paths
    assert has_meaningful_streamlit_leak(leak_cwd) is True


def test_secret_redaction_does_not_expose_values() -> None:
    """Leak report must not expose secret values, only var names."""
    import warnings

    import pytest

    monkeypatch_secret = "super-secret-xyz-123"  # noqa: S105, S106 - test secret value
    # Use direct env snapshot to prove redaction without relying on meaningful predicate for env
    before = capture_streamlit_snapshot()
    # Set secret then change
    os.environ["BODS_API_KEY"] = monkeypatch_secret
    mid = capture_streamlit_snapshot()
    os.environ["BODS_API_KEY"] = "different-secret-999"
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(mid, after)
    # Leak should contain env change but report must not dump values
    report = format_leak_report(leak)
    assert "super-secret-xyz-123" not in report
    assert "different-secret-999" not in report
    assert "BODS_API_KEY" in report
    # Also ensure warning path would not dump secrets
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warnings.warn(
            f"Streamlit isolation leak detected after test_aaa: env={leak.get('env')}"  # noqa: E501 - test message
            " — state was restored",
            pytest.PytestWarning,
            stacklevel=2,
        )
        msg = str(w[0].message)
        assert "super-secret-xyz-123" not in msg
        assert "different-secret-999" not in msg
        assert "BODS_API_KEY" in msg
    restore_streamlit_snapshot(before)


def test_diagnose_legitimate_import_not_meaningful() -> None:
    """Direct diagnose: legitimate real import must not be meaningful."""

    from tests.support.streamlit_isolation import has_meaningful_streamlit_leak

    before = capture_streamlit_snapshot()
    # Ensure streamlit not yet imported in this capture? It is already imported from earlier tests,
    # so we need a fresh empty snapshot via manual construction.
    # Instead, test the predicate on a synthetic innocent leak: before empty, after real.
    # Use the helper to ensure real import is not considered leak.
    # Capture before as empty (no streamlit), then import real, then diagnose.
    # If streamlit already present, we test the other way: no leak when already present and no fake.
    after = capture_streamlit_snapshot()
    # If both have real, diagnose should be empty or not meaningful
    leak = diagnose_streamlit_leak(after, after)
    assert has_meaningful_streamlit_leak(leak) is False
    # Also test synthetic: before empty -> after real should not be meaningful
    empty = StreamlitIsolationSnapshot(
        sys_modules={},
        apptest_installed=before.apptest_installed,
        apptest_original=before.apptest_original,
        apptest_has_run_first=before.apptest_has_run_first,
        apptest_run_id=before.apptest_run_id,
        cwd=before.cwd,
        env=before.env,
        finder_present=before.finder_present,
    )
    # Real after has many keys, but should not be meaningful because not fake
    leak2 = diagnose_streamlit_leak(empty, after)
    assert has_meaningful_streamlit_leak(leak2) is False
    # Fake should be meaningful
    _ = _emulate_polluter_install_fake()
    leak3 = diagnose_streamlit_leak(after, capture_streamlit_snapshot())
    assert has_meaningful_streamlit_leak(leak3) is True
    restore_streamlit_snapshot(after)
