# ruff: noqa: ANN001,ANN002,ANN003,ANN201,ANN202,ANN101,S110,S112,ANN401,SIM105,E501
# mypy: disable-error-code="attr-defined, misc, unused-ignore, no-untyped-def, assignment, call-arg"
"""Targeted Streamlit/pytest isolation utility.

Snapshots and restores only relevant state:
- sys.modules["streamlit"] and specific Streamlit submodules
- monkeypatched AppTest objects (AppTest.run)
- known wrapper/global installation flags (tests._apptest_runtime)
- selected environment variables
- cwd
- repository-specific cached module state (streamlit finder)

Does not indiscriminately clear all sys.modules.
Does not reload the whole application after every test unless measurement proves necessary.

Diagnostic helper reports leaked state without dumping credentials or entire env.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Relevant sys.modules keys — only those that may be faked by tests.
_RELEVANT_MODULE_KEYS: tuple[str, ...] = (
    "streamlit",
    "streamlit.testing",
    "streamlit.testing.v1",
)

# Known wrapper flag module.
_RUNTIME_MODULE = "tests._apptest_runtime"

# Selected environment variables that tests may monkeypatch.
# Keep allowlist small and non-secret-leaking for diagnostics.
_RELEVANT_ENV_VARS: tuple[str, ...] = (
    "TRAFFICTWIN_WORKSPACE_PATH",
    "BODS_API_KEY",
    "TRAFFICTWIN_BODS_BOUNDING_BOX",
    "NATIONAL_HIGHWAYS_API_KEY",
    "STREAMLIT_SERVER_PORT",
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS",
)

# Sentinel for absent.
_ABSENT = object()

_SENTINEL = _ABSENT


@dataclass(frozen=True)
class StreamlitIsolationSnapshot:
    """Deterministic snapshot of relevant isolation state."""

    sys_modules: dict[str, Any]
    apptest_installed: bool
    apptest_original: Any | None
    apptest_has_run_first: bool
    apptest_run_id: int | None
    cwd: str
    env: dict[str, str | None]
    finder_present: bool


def _capture_apptest_state() -> tuple[bool, Any, bool, int | None]:
    """Capture wrapper flags without importing streamlit at import time."""
    try:
        mod = sys.modules.get(_RUNTIME_MODULE)
        if mod is None:
            # Lazy import — only if not already loaded; does not import streamlit.
            import importlib

            mod = importlib.import_module(_RUNTIME_MODULE)
        installed: bool = bool(getattr(mod, "_installed", False))
        original: Any = getattr(mod, "_original_run", None)
        has_first: bool = bool(getattr(mod, "_has_run_first", False))
        run_id: int | None = None
        # Capture AppTest.run identity if streamlit already loaded.
        if "streamlit.testing.v1" in sys.modules:
            try:
                app_mod = sys.modules["streamlit.testing.v1"]
                app_cls = getattr(app_mod, "AppTest", None)
                if app_cls is not None:
                    run = getattr(app_cls, "run", None)
                    if run is not None:
                        run_id = id(run)
            except Exception:
                pass
        return installed, original, has_first, run_id
    except Exception:
        return False, None, False, None


def capture_streamlit_snapshot() -> StreamlitIsolationSnapshot:
    """Snapshot only relevant state."""
    # Snapshot sys.modules for relevant keys.
    sys_mods: dict[str, Any] = {}
    for key in _RELEVANT_MODULE_KEYS:
        val = sys.modules.get(key, _SENTINEL)
        # Store sentinel for absent so restore knows to pop.
        sys_mods[key] = val

    installed, original, has_first, run_id = _capture_apptest_state()

    # Snapshot cwd.
    try:
        cwd = os.getcwd()
    except Exception:
        cwd = ""

    # Snapshot selected env vars only.
    env: dict[str, str | None] = {}
    for var in _RELEVANT_ENV_VARS:
        env[var] = os.environ.get(var)

    # Finder presence.
    finder_present = False
    try:
        # Import tests.conftest finder if available.
        tc = sys.modules.get("tests.conftest")
        if tc is not None:
            finder = getattr(tc, "_finder", None)
            if finder is not None:
                finder_present = finder in sys.meta_path
    except Exception:
        pass

    return StreamlitIsolationSnapshot(
        sys_modules=sys_mods,
        apptest_installed=installed,
        apptest_original=original,
        apptest_has_run_first=has_first,
        apptest_run_id=run_id,
        cwd=cwd,
        env=env,
        finder_present=finder_present,
    )


def restore_streamlit_snapshot(snapshot: StreamlitIsolationSnapshot) -> None:
    """Restore only relevant state from snapshot."""
    # Restore sys.modules.
    for key, val in snapshot.sys_modules.items():
        if val is _SENTINEL:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val  # type: ignore[assignment]

    # Restore apptest runtime flags.
    import importlib

    mod = sys.modules.get(_RUNTIME_MODULE)
    if mod is None:
        mod = importlib.import_module(_RUNTIME_MODULE)
    # Restore original and installed.
    # Need to handle AppTest.run restoration directly if needed.
    # If snapshot says installed, ensure AppTest.run is patched; if not, ensure unwrapped.
    # Use uninstall/install to keep invariants.
    cur_installed = bool(getattr(mod, "_installed", False))
    # If state differs, repair.
    if cur_installed != snapshot.apptest_installed:
        if snapshot.apptest_installed:
            # Need to install.
            try:
                from tests._apptest_runtime import install_apptest_run_patch

                install_apptest_run_patch()
            except ModuleNotFoundError as exc:
                if exc.name is None or not exc.name.startswith("streamlit"):
                    raise
        else:
            try:
                from tests._apptest_runtime import uninstall_apptest_run_patch

                uninstall_apptest_run_patch()
            except ModuleNotFoundError as exc:
                if exc.name is None or not exc.name.startswith("streamlit"):
                    raise
    # Restore has_run_first independently (does not affect installed).
    try:
        mod._has_run_first = snapshot.apptest_has_run_first  # type: ignore[attr-defined]
    except Exception:
        pass
    # For extra safety, if run_id mismatch and streamlit loaded, ensure restoration.
    # If snapshot had no streamlit but now has fake, the sys.modules restore already handled.
    # If snapshot had real patched run, the install/uninstall above restored it.

    # Restore cwd.
    try:
        cur_cwd = os.getcwd()
        if cur_cwd != snapshot.cwd and snapshot.cwd and Path(snapshot.cwd).exists():
            os.chdir(snapshot.cwd)
    except Exception:
        pass

    # Restore selected env vars.
    for var, val in snapshot.env.items():
        try:
            if val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = val
        except Exception:
            pass

    # Restore finder presence: we do not remove finder if snapshot expected it present.
    # If snapshot had finder and now missing, re-insert; if snapshot missing and now present, remove.
    # But we generally keep finder present for suite lifetime; don't indiscriminately clear.
    try:
        tc = sys.modules.get("tests.conftest")
        if tc is not None:
            finder = getattr(tc, "_finder", None)
            if finder is not None:
                is_present = finder in sys.meta_path
                if snapshot.finder_present and not is_present:
                    sys.meta_path.insert(0, finder)
                elif not snapshot.finder_present and is_present:
                    try:
                        sys.meta_path.remove(finder)
                    except ValueError:
                        pass
    except Exception:
        pass


def diagnose_streamlit_leak(
    before: StreamlitIsolationSnapshot, after: StreamlitIsolationSnapshot | None = None
) -> dict[str, object]:
    """Report relevant leaked state without dumping credentials or entire env.

    Returns a small dict with only relevant keys, values truncated, secrets redacted.
    """
    if after is None:
        after = capture_streamlit_snapshot()

    leaked: dict[str, object] = {}

    # Check sys.modules.
    sys_leaked: list[str] = []
    for key in _RELEVANT_MODULE_KEYS:
        before_val = before.sys_modules.get(key, _SENTINEL)
        after_val = after.sys_modules.get(key, _SENTINEL)
        before_present = before_val is not _SENTINEL
        after_present = after_val is not _SENTINEL
        if before_present != after_present:
            sys_leaked.append(
                f"{key}:{'present' if after_present else 'absent'}(was {'present' if before_present else 'absent'})"
            )
        elif after_present and before_present and before_val is not after_val:
            # Identity changed (fake vs real)
            before_id = id(before_val) if before_val is not None else 0
            after_id = id(after_val) if after_val is not None else 0
            if before_id != after_id:
                # Check if fake (lacks 'secrets'?) but avoid dumping.
                is_fake = False
                try:
                    is_fake = not hasattr(after_val, "secrets") and hasattr(after_val, "__name__")
                except Exception:
                    pass
                sys_leaked.append(f"{key}:identity_changed(fake={is_fake})")
    if sys_leaked:
        leaked["sys_modules"] = sys_leaked

    # Check apptest installed flag.
    if before.apptest_installed != after.apptest_installed:
        leaked["apptest_installed"] = {
            "before": before.apptest_installed,
            "after": after.apptest_installed,
        }

    # Check has_run_first.
    if before.apptest_has_run_first != after.apptest_has_run_first:
        leaked["has_run_first"] = {
            "before": before.apptest_has_run_first,
            "after": after.apptest_has_run_first,
        }

    # Check run identity.
    if before.apptest_run_id != after.apptest_run_id:
        leaked["apptest_run_id_changed"] = True

    # Check cwd.
    if before.cwd != after.cwd:
        leaked["cwd"] = {"before": before.cwd, "after": after.cwd}

    # Check env — only report which vars changed, not values (to avoid secrets).
    env_changed: list[str] = []
    for var in _RELEVANT_ENV_VARS:
        if before.env.get(var) != after.env.get(var):
            # Do not include values (may be secrets).
            before_present = before.env.get(var) is not None
            after_present = after.env.get(var) is not None
            if before_present != after_present:
                env_changed.append(
                    f"{var}:{'set' if after_present else 'unset'}(was {'set' if before_present else 'unset'})"
                )
            else:
                env_changed.append(f"{var}:changed")
    if env_changed:
        leaked["env"] = env_changed

    # Check finder.
    if before.finder_present != after.finder_present:
        leaked["finder_present"] = {
            "before": before.finder_present,
            "after": after.finder_present,
        }

    # Only attach Streamlit identity details when there is a meaningful sys_modules
    # or apptest leak, to avoid noisy diagnostics on every test (streamlit_id etc
    # would otherwise make the dict non-empty for informational purposes).
    if (
        sys_leaked
        or "apptest_installed" in leaked
        or "env" in leaked
        or "cwd" in leaked
        or "finder_present" in leaked
    ):
        try:
            mod = sys.modules.get("streamlit")
            if mod is not None:
                has_secrets = hasattr(mod, "secrets")
                leaked["streamlit_has_secrets"] = has_secrets
                leaked["streamlit_id"] = id(mod)
            else:
                leaked["streamlit_present"] = False
        except Exception:
            pass

    return leaked


def has_meaningful_streamlit_leak(leak: dict[str, object]) -> bool:
    """Predicate for meaningful isolation breach (not just informational metadata).

    Returns True only for actual state leaks that the guard should report:
    - streamlit module presence/identity changed (sys_modules)
    - streamlit.testing hierarchy changed (sys_modules)
    - real streamlit replaced by fake (sys_modules identity_changed fake)
    - AppTest wrapper installation state leaked (apptest_installed)
    - selected guarded environment state leaked (env)
    - cwd / finder where applicable (cwd, finder_present)

    Transient AppTest execution state such as ``has_run_first`` or
    ``apptest_run_id_changed`` alone is NOT meaningful and is ignored to avoid
    noise on normal AppTest tests. Likewise, informational fields like
    ``streamlit_has_secrets`` / ``streamlit_id`` alone are not meaningful.
    """
    meaningful_keys = {"sys_modules", "apptest_installed", "env", "cwd", "finder_present"}
    return any(key in leak for key in meaningful_keys)


def format_leak_report(leak: dict[str, object]) -> str:
    """Format leak dict as compact string for test failure output."""
    if not leak:
        return "No Streamlit isolation leak detected."
    parts: list[str] = ["Streamlit isolation leak:"]
    for k, v in leak.items():
        parts.append(f"  {k}: {v}")
    return "\n".join(parts)


# Context manager for manual use.
class StreamlitIsolation:
    """Context manager that snapshots on enter and restores on exit."""

    def __init__(self) -> None:
        self._snapshot: StreamlitIsolationSnapshot | None = None

    def __enter__(self) -> StreamlitIsolationSnapshot:
        self._snapshot = capture_streamlit_snapshot()
        return self._snapshot

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # noqa: ANN401
        if self._snapshot is not None:
            restore_streamlit_snapshot(self._snapshot)
            self._snapshot = None
