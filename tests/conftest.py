# ruff: noqa: ANN001,ANN002,ANN003,ANN201,ANN202,S110,SIM105
"""Pytest session hardening for Streamlit AppTest cold start.

First AppTest.run in a pytest process gets a larger startup budget (cold floor)
to cover import/startup overhead. Subsequent runs keep their requested timeout
unchanged. This is test-only, does not affect production `src/`, and does not
perform a hidden warm-up AppTest before the named test.

Implementation is intentionally lazy: Streamlit is imported only if the test
session actually collects AppTest-using tests, but the patch is installed
early enough to cover the first real AppTest.run.
"""

from __future__ import annotations

import pytest

try:
    from streamlit.testing.v1 import AppTest as _AppTest  # type: ignore[import-untyped]

    from tests._apptest_runtime import COLD_FLOOR_SECONDS, effective_timeout

    _ORIGINAL_RUN = _AppTest.run
    _has_run_first = False

    def _patched_run(self, timeout: int = 10, **kwargs):  # type: ignore[no-untyped-def]
        global _has_run_first
        is_first = not _has_run_first
        if is_first:
            _has_run_first = True
        eff = effective_timeout(timeout, is_first, cold_floor=COLD_FLOOR_SECONDS)
        return _ORIGINAL_RUN(self, timeout=eff, **kwargs)

    _AppTest.run = _patched_run  # type: ignore[method-assign]

    @pytest.fixture(autouse=True, scope="session")
    def _restore_apptest_run():  # type: ignore[no-untyped-def]
        yield
        # Restore at session teardown to avoid leaking into other pytest invocations
        # in the same interpreter (e.g., `pytest --forked` is not used, but be tidy).
        try:
            _AppTest.run = _ORIGINAL_RUN  # type: ignore[method-assign]
        except Exception:
            pass

except ImportError:
    # Streamlit not installed — nothing to patch (e.g., minimal CI without UI deps)
    pass
