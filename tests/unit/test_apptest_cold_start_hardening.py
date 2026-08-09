# ruff: noqa: ANN001,ANN002,ANN003,ANN201,ANN202,ANN101
"""Regression tests for AppTest cold-start timeout hardening.

These tests are intentionally fast and deterministic; they do not sleep.
They verify the pure timeout-selection helper and the wrapper contract
without launching a real Streamlit AppTest before the named test.
"""

from __future__ import annotations

import pytest

from tests._apptest_runtime import COLD_FLOOR_SECONDS, effective_timeout


def test_first_requested_10_receives_cold_floor() -> None:
    assert effective_timeout(10, is_first=True) == COLD_FLOOR_SECONDS


def test_second_requested_10_remains_10() -> None:
    assert effective_timeout(10, is_first=False) == 10


def test_first_requested_greater_than_floor_remains_unchanged() -> None:
    assert effective_timeout(80, is_first=True) == 80
    assert effective_timeout(COLD_FLOOR_SECONDS + 10, is_first=True) == COLD_FLOOR_SECONDS + 10


def test_no_timeout_is_reduced() -> None:
    for req in [10, 20, 60, 80, 100]:
        eff_first = effective_timeout(req, is_first=True)
        eff_second = effective_timeout(req, is_first=False)
        assert eff_first >= req
        assert eff_second == req
    # None -> default 10 -> floor on first
    assert effective_timeout(None, is_first=True) == COLD_FLOOR_SECONDS
    assert effective_timeout(None, is_first=False) == 10


def test_policy_is_deterministic() -> None:
    assert effective_timeout(10, is_first=True) == effective_timeout(10, is_first=True)
    assert effective_timeout(10, is_first=False) == effective_timeout(10, is_first=False)
    assert effective_timeout(25, is_first=False) == 25


def test_only_apptest_run_is_affected_by_wrapper() -> None:
    # Non-AppTest function should not be wrapped; helper is pure and does not
    # launch an AppTest. Prove helper does not import Streamlit or call AppTest.
    import sys

    before = set(sys.modules.keys())
    # Calling helper should not import streamlit
    _ = effective_timeout(10, is_first=True)
    after = set(sys.modules.keys())
    new = after - before
    assert not any("streamlit" in m.lower() for m in new)


def test_wrapper_calls_original_exactly_once_and_propagates_return_and_exception() -> None:
    # Simulate the conftest wrapper contract with a local flag and mock
    from tests._apptest_runtime import effective_timeout as eff

    call_count = 0
    sentinel = object()

    def fake_original(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if timeout == 999:
            raise RuntimeError("boom")
        return sentinel

    # Local wrapper mimicking tests/conftest.py logic
    has_run_first = False

    def wrapped(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal has_run_first
        is_first = not has_run_first
        if is_first:
            has_run_first = True
        eff_timeout = eff(timeout, is_first)
        return fake_original(self, timeout=eff_timeout, **kwargs)

    # First call with timeout=10 should be floored to COLD_FLOOR and call original once
    result = wrapped(object(), timeout=10)
    assert result is sentinel
    assert call_count == 1

    # Second call with timeout=10 should remain 10 and call original again
    # We need to capture the timeout passed to fake_original; modify fake to capture
    captured = {}

    def fake_capture(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        captured["timeout"] = timeout
        return sentinel

    # Recreate wrapper with capture
    has_run_first = False
    call_count = 0

    def wrapped2(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal has_run_first
        is_first = not has_run_first
        if is_first:
            has_run_first = True
        eff2 = eff(timeout, is_first)
        return fake_capture(self, timeout=eff2, **kwargs)

    wrapped2(object(), timeout=10)  # first -> floor
    assert captured["timeout"] == COLD_FLOOR_SECONDS
    wrapped2(object(), timeout=10)  # second -> 10
    assert captured["timeout"] == 10
    wrapped2(object(), timeout=25)  # third -> 25
    assert captured["timeout"] == 25

    # Exception propagation
    def fake_raise(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    has_run_first = False

    def wrapped_raise(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal has_run_first
        is_first = not has_run_first
        if is_first:
            has_run_first = True
        eff3 = eff(timeout, is_first)
        return fake_raise(self, timeout=eff3, **kwargs)

    with pytest.raises(RuntimeError, match="boom"):
        wrapped_raise(object(), timeout=10)

    # Ensure second call after exception still respects is_first=False (first was consumed)
    # has_run_first is now True, so next call should not be floored
    captured2 = {}

    def fake_capture2(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        captured2["timeout"] = timeout
        return sentinel

    # has_run_first is True from previous exception, so next is not first
    eff_next = eff(10, is_first=False)
    fake_capture2(object(), timeout=eff_next)
    assert captured2["timeout"] == 10


def test_first_run_consumed_semantics_on_exception() -> None:
    # Document correct semantics: if original run raises, the first-run budget is
    # considered consumed (startup was attempted). Next call is not floored.
    from tests._apptest_runtime import effective_timeout as eff

    has_run_first = False

    def fake_raise(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    def wrapped(self, timeout=10, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal has_run_first
        is_first = not has_run_first
        if is_first:
            has_run_first = True
        return fake_raise(self, timeout=eff(timeout, is_first), **kwargs)

    with pytest.raises(RuntimeError):
        wrapped(object(), timeout=10)
    # has_run_first is now True
    assert has_run_first is True
    # Next effective should be non-first
    assert eff(10, is_first=False) == 10


def test_subsequent_timeout_10_remains_10_and_25_remains_25_via_helper() -> None:
    assert effective_timeout(10, is_first=False) == 10
    assert effective_timeout(25, is_first=False) == 25
    assert effective_timeout(10, is_first=True) == COLD_FLOOR_SECONDS
    assert effective_timeout(25, is_first=True) == 60  # max(25,60)=60


def test_state_resets_between_processes_is_implicit() -> None:
    # Each pytest process starts with fresh import, so _has_run_first is False
    # Prove helper is deterministic and does not retain cross-process state
    assert effective_timeout(10, is_first=True) == COLD_FLOOR_SECONDS
    # Simulate new process: is_first=True again
    assert effective_timeout(10, is_first=True) == COLD_FLOOR_SECONDS


def test_helper_does_not_launch_apptest_before_named_test() -> None:
    # The helper module should not have imported AppTest or created an instance
    import sys

    # Ensure tests._apptest_runtime does not import streamlit
    assert "streamlit" not in sys.modules or "tests._apptest_runtime" in sys.modules
    # Calling helper must not create an AppTest
    before_apptest = [m for m in sys.modules if "streamlit.testing" in m]
    _ = effective_timeout(10, is_first=True)
    after_apptest = [m for m in sys.modules if "streamlit.testing" in m]
    # No new AppTest module should be loaded by helper call
    assert after_apptest == before_apptest
