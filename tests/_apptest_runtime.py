# ruff: noqa: ANN401
"""Shipped AppTest cold-start patch — installer owns the production behavior.

This module is the single source of truth for the AppTest timeout policy.
``tests/conftest.py`` must orchestrate this module, not duplicate it.
Tests must import and exercise this installer, not a private copy.

Policy:
- First ``AppTest.run`` in a pytest process: ``max(requested, 60)``
- Subsequent runs: requested unchanged
- Never reduces a timeout
"""

from __future__ import annotations

from typing import Any

COLD_FLOOR_SECONDS: int = 60
DEFAULT_TIMEOUT_SECONDS: int = 10

# Internal state — intentionally module-global so it survives across imports
# within a single pytest process but resets for each new process.
_has_run_first: bool = False
_original_run: Any | None = None
_installed: bool = False


def effective_timeout(
    requested: float | int | None,
    *,
    is_first: bool,
    cold_floor: float | int = COLD_FLOOR_SECONDS,
    default: float | int = DEFAULT_TIMEOUT_SECONDS,
) -> float | int:
    """Return the effective AppTest.run timeout.

    - ``None`` is treated as ``default`` (10) before applying the floor.
    - First run: ``max(requested, cold_floor)``
    - Subsequent: ``requested`` unchanged
    """
    req = requested if requested is not None else default
    if is_first:
        return req if req > cold_floor else cold_floor
    return req


def install_apptest_run_patch() -> bool:
    """Install the cold-start wrapper over ``streamlit.testing.v1.AppTest.run``.

    Returns True if installed (or already installed), False if Streamlit is
    not installed and patch was not applied. Only tolerates
    ``ModuleNotFoundError`` for ``streamlit`` itself; any other import error
    (including a broken ``tests._apptest_runtime``) must propagate.

    Idempotent — second call is a no-op without double-wrapping.
    Does not instantiate or run an AppTest.

    Invariant: ``_installed`` is the single source of truth for idempotence.
    """
    global _installed, _original_run, _has_run_first

    if _installed:
        return True

    # Import AppTest lazily — do not import Streamlit at module import time.
    try:
        from streamlit.testing.v1 import AppTest
    except ModuleNotFoundError as exc:
        # Only tolerate Streamlit genuinely not installed.
        # ``exc.name`` is the top-level missing module.
        if exc.name is not None and exc.name.startswith("streamlit"):
            return False
        raise
    # Any other ImportError / SyntaxError from helper or Streamlit internals
    # must fail closed — do not swallow.

    _original_run = AppTest.run
    # Close over the exact original callable at install time — the wrapper must
    # never resolve the mutable global ``_original_run`` at call time, otherwise
    # a captured reference would crash after ``uninstall`` sets it to ``None``.
    original_run = _original_run

    def _patched_run(self: Any, *args: Any, timeout: float | None = None, **kwargs: Any) -> Any:
        global _has_run_first
        is_first = not _has_run_first
        if is_first:
            _has_run_first = True
        # ``effective_timeout`` treats None as default 10.
        eff = effective_timeout(timeout, is_first=is_first, cold_floor=COLD_FLOOR_SECONDS)
        # Preserve all other args/kwargs; inject effective timeout.
        # ``AppTest.run`` is keyword-only for timeout, so pass as keyword.
        return original_run(self, *args, timeout=eff, **kwargs)

    # Mark wrapper for idempotence detection.
    _patched_run._is_cold_patched = True  # type: ignore[attr-defined]

    AppTest.run = _patched_run  # type: ignore[method-assign]
    _installed = True
    return True


def uninstall_apptest_run_patch() -> None:
    """Restore the original ``AppTest.run`` if patched.

    Tolerates Streamlit not installed (no-op). For any other error, fails closed.
    """
    global _installed, _original_run

    if not _installed or _original_run is None:
        return

    try:
        from streamlit.testing.v1 import AppTest
    except ModuleNotFoundError as exc:
        if exc.name is not None and exc.name.startswith("streamlit"):
            _installed = False
            _original_run = None
            return
        raise

    try:
        AppTest.run = _original_run  # type: ignore[method-assign]
    finally:
        _installed = False
        _original_run = None


def reset_apptest_cold_state() -> None:
    """Reset first-run allowance so next ``run`` again receives the cold floor.

    Does not uninstall the wrapper; only resets the per-process first-run flag.
    """
    global _has_run_first
    _has_run_first = False


def is_patched() -> bool:
    """Whether the wrapper is currently installed."""
    return _installed


def get_has_run_first() -> bool:
    """Whether the first-run budget has been consumed in this process."""
    return _has_run_first
