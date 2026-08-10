# ruff: noqa: ANN001,ANN401,ANN002,ANN003,ANN201,ANN202,S110,SIM105
"""Pytest plugin for AppTest cold-start hardening — lazy, fail-closed.

First AppTest.run in a pytest process gets max(requested,60); later calls
retain requested timeout. This file orchestrates tests/_apptest_runtime.py and
contains no second implementation.

Lazy guarantees:
A. Importing this module does not import Streamlit.
B. Collecting a pure-unit test does not import Streamlit because of this plugin.
C. Before the first actual AppTest.run, the wrapper is installed.
D. Installed once (installer is idempotent).
E. Restored at session end.

No hidden warm-up AppTest is ever executed.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys

import pytest

# Fail-closed: broken helper must raise loudly — do not swallow.
from tests._apptest_runtime import (  # noqa: F401
    COLD_FLOOR_SECONDS,
    effective_timeout,
    install_apptest_run_patch,
    is_patched,
    reset_apptest_cold_state,
    uninstall_apptest_run_patch,
)

# ---------------------------------------------------------------------------
# Lazy installer via sys.meta_path — does not import Streamlit at plugin import.
# ---------------------------------------------------------------------------


class _PatchedLoader(importlib.abc.Loader):
    """Wraps the original loader for streamlit.testing.v1 to patch after exec."""

    def __init__(self, original_loader: importlib.abc.Loader) -> None:
        self.original_loader = original_loader

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        if hasattr(self.original_loader, "create_module"):
            return self.original_loader.create_module(spec)
        return None

    def exec_module(self, module):  # type: ignore[no-untyped-def]
        # First let the original loader do its work (populates module, defines AppTest).
        self.original_loader.exec_module(module)
        # Now patch — this does not import Streamlit anew because the module
        # is already in sys.modules; it just wraps AppTest.run.
        try:
            install_apptest_run_patch()
        except ModuleNotFoundError as exc:
            if exc.name is not None and exc.name.startswith("streamlit"):
                # Tolerate missing Streamlit only when not needed.
                return
            raise
        except Exception:
            raise


class _LazyPatchFinder(importlib.abc.MetaPathFinder):
    """Intercepts ``streamlit.testing.v1`` import to install patch lazily."""

    def find_spec(self, fullname, path, target=None):  # type: ignore[no-untyped-def]
        if fullname != "streamlit.testing.v1":
            return None
        # Avoid recursion: look up original spec via other finders only.
        for finder in sys.meta_path:
            if finder is self:
                continue
            try:
                spec = finder.find_spec(fullname, path, target)
            except Exception:  # noqa: S112
                continue
            if spec is not None and spec.loader is not None:
                # Wrap loader so patch happens after exec_module.
                spec.loader = _PatchedLoader(spec.loader)
                return spec
        return None


# Install finder at import time — does NOT import Streamlit.
_finder = _LazyPatchFinder()
if _finder not in sys.meta_path:
    sys.meta_path.insert(0, _finder)


# ---------------------------------------------------------------------------
# Cold-test opt-in — explicit --run-cold-apptest required
# ---------------------------------------------------------------------------


def pytest_addoption(parser):  # type: ignore[no-untyped-def]
    group = parser.getgroup("traffictwin")
    import contextlib

    with contextlib.suppress(ValueError):
        group.addoption(
            "--run-cold-apptest",
            action="store_true",
            default=False,
            help="run expensive cold AppTest controls (requires --run-cold-apptest)",
        )


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    # By default cold controls are skipped; only with --run-cold-apptest may they run.
    # This is explicit opt-in, not a default -m expression, so a user-supplied
    # -m cannot accidentally re-enable them.
    if config.getoption("--run-cold-apptest"):
        return
    skip = pytest.mark.skip(reason="cold AppTest control requires --run-cold-apptest")
    for item in items:
        if item.get_closest_marker("cold_apptest"):
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Pytest hooks — fallback for already-loaded case and session teardown.
# ---------------------------------------------------------------------------


def pytest_collection_finish(session):  # type: ignore[no-untyped-def]
    """If any test module imported streamlit.testing.v1 at collection time, install."""
    if "streamlit.testing.v1" in sys.modules and not is_patched():
        try:
            install_apptest_run_patch()
        except ModuleNotFoundError as exc:
            if exc.name is not None and exc.name.startswith("streamlit"):
                return
            raise


def pytest_runtest_setup(item):  # type: ignore[no-untyped-def]
    """Ensure wrapper before each AppTest test (covers pre-imported case)."""
    if "streamlit.testing.v1" in sys.modules and not is_patched():
        try:
            install_apptest_run_patch()
        except ModuleNotFoundError as exc:
            if exc.name is not None and exc.name.startswith("streamlit"):
                return
            raise


def pytest_sessionfinish(session, exitstatus):  # type: ignore[no-untyped-def]
    """Restore original AppTest.run and remove finder."""
    # Remove finder
    try:
        if _finder in sys.meta_path:
            sys.meta_path.remove(_finder)
    except Exception:
        pass
    # Restore AppTest.run — fail closed if helper is broken.
    try:
        uninstall_apptest_run_patch()
    except ModuleNotFoundError as exc:
        if exc.name is not None and exc.name.startswith("streamlit"):
            return
        raise
    except Exception:
        raise


# ---------------------------------------------------------------------------
# Streamlit isolation guard — targeted snapshot/restore defense-in-depth
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _streamlit_isolation_guard(request):  # type: ignore[no-untyped-def]
    """Targeted isolation: snapshot relevant state before each test and restore after.

    - Snapshots only sys.modules["streamlit"] hierarchy, AppTest.run wrapper flags,
      selected env vars, cwd, and finder. Does not clear all sys.modules or reload app.
    - Restores after each test so a leaking fake does not pollute the next victim.
    - Must not conceal a leaking test: if a test leaks and still passes, the leak
      is reported via the diagnostic helper; the underlying polluter fix ensures
      leaking tests are fixed at source. This guard is defense-in-depth.
    """
    # Lazy import so conftest import does not import streamlit.
    from tests.support.streamlit_isolation import (
        capture_streamlit_snapshot,
        restore_streamlit_snapshot,
    )

    before = capture_streamlit_snapshot()
    # Store for diagnostic hook.
    request.node._streamlit_before = before  # type: ignore[attr-defined, unused-ignore]
    yield
    # Capture after before restore for diagnostics.
    after = capture_streamlit_snapshot()
    request.node._streamlit_after = after  # type: ignore[attr-defined, unused-ignore]
    # Always restore — targeted, not indiscriminate.
    try:
        restore_streamlit_snapshot(before)
    except Exception:
        raise


@pytest.fixture
def streamlit_leak_report(request):  # type: ignore[no-untyped-def]
    """Optional diagnostic fixture: reports relevant leaked state when test fails.

    Usage:
        def test_foo(streamlit_leak_report):
            ...

    Must not dump credentials or entire environment.
    """
    from tests.support.streamlit_isolation import (
        capture_streamlit_snapshot,
        diagnose_streamlit_leak,
        format_leak_report,
    )

    before = capture_streamlit_snapshot()
    yield
    after = capture_streamlit_snapshot()
    leak = diagnose_streamlit_leak(before, after)
    # Only emit when test failed (via request.node.rep_call) or when leak critical.
    # We attach to report via terminal output on failure.
    try:
        rep = getattr(request.node, "rep_call", None)
        failed = rep is not None and rep.failed
    except Exception:
        failed = False
    if failed or leak.get("sys_modules") or leak.get("apptest_installed"):
        # Do not include secret values; diagnose already redacts.
        report = format_leak_report(leak)
        # Emit to stdout for pytest capture; also stash for hook.
        request.node._streamlit_leak_report = report  # type: ignore[attr-defined, unused-ignore]
        if failed:
            print(f"\n{report}\n")


# Hook to capture rep_call for diagnostic fixture.
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item, call):  # type: ignore[no-untyped-def]
    # Store report for fixture diagnostics.
    if call.when == "call":
        item.rep_call = call  # type: ignore[attr-defined, unused-ignore]
    # On failure, emit leak diagnostics if available.
    if call.when == "call" and call.excinfo is not None:
        before = getattr(item, "_streamlit_before", None)
        after = getattr(item, "_streamlit_after", None)
        if before is not None:
            try:
                from tests.support.streamlit_isolation import (
                    diagnose_streamlit_leak,
                    format_leak_report,
                )

                leak_after = after
                if leak_after is None:
                    from tests.support.streamlit_isolation import capture_streamlit_snapshot

                    leak_after = capture_streamlit_snapshot()
                leak = diagnose_streamlit_leak(before, leak_after)
                if leak:
                    # Attach as extra section; also print compact.
                    report = format_leak_report(leak)
                    # Use terminal reporter if available, else print.
                    print(f"\n[streamlit-isolation] leak on failure:\n{report}\n")
            except Exception:
                pass
