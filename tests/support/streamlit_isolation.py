"""Targeted Streamlit/pytest isolation utility.

Snapshots and restores only relevant state:
- sys.modules["streamlit"] and the whole ``streamlit.*`` subtree
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

# Relevant sys.modules prefix — whole subtree is snapshot, not just 3 keys.
_STREAMLIT_PREFIX = "streamlit"
_STREAMLIT_DOT = "streamlit."

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


def _is_streamlit_key(key: str) -> bool:
    return key == _STREAMLIT_PREFIX or key.startswith(_STREAMLIT_DOT)


def _is_fake_streamlit_module(mod: object) -> bool:  # noqa: ANN401 - Any needed for module check, object is sufficient
    """Return True if ``mod`` looks like the historical fake (lacks secrets)."""
    if mod is None:
        return False
    try:
        # Real ``streamlit`` has ``secrets``; fake created via ModuleType lacks it.
        return not hasattr(mod, "secrets")
    except Exception:
        return False


def _capture_apptest_state() -> tuple[bool, Any, bool, int | None]:
    """Capture wrapper flags without importing streamlit at import time."""
    try:
        mod = sys.modules.get(_RUNTIME_MODULE)
        if mod is None:
            import importlib

            mod = importlib.import_module(_RUNTIME_MODULE)
        installed: bool = bool(getattr(mod, "_installed", False))
        original: Any = getattr(mod, "_original_run", None)
        has_first: bool = bool(getattr(mod, "_has_run_first", False))
        run_id: int | None = None
        if "streamlit.testing.v1" in sys.modules:
            try:
                app_mod = sys.modules["streamlit.testing.v1"]
                app_cls = getattr(app_mod, "AppTest", None)
                if app_cls is not None:
                    run = getattr(app_cls, "run", None)
                    if run is not None:
                        run_id = id(run)
            except (AttributeError, TypeError):
                pass
        return installed, original, has_first, run_id
    except (ImportError, ModuleNotFoundError, AttributeError):
        return False, None, False, None


def capture_streamlit_snapshot() -> StreamlitIsolationSnapshot:
    """Snapshot only relevant state."""
    sys_mods: dict[str, Any] = {}
    for key, val in sys.modules.items():
        if _is_streamlit_key(key):
            sys_mods[key] = val

    installed, original, has_first, run_id = _capture_apptest_state()

    try:
        cwd = os.getcwd()
    except OSError:
        cwd = ""

    env: dict[str, str | None] = {}
    for var in _RELEVANT_ENV_VARS:
        env[var] = os.environ.get(var)

    finder_present = False
    try:
        tc = sys.modules.get("tests.conftest")
        if tc is not None:
            finder = getattr(tc, "_finder", None)
            if finder is not None:
                finder_present = finder in sys.meta_path
    except (AttributeError, TypeError):
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


def _restore_streamlit_modules(snapshot: StreamlitIsolationSnapshot) -> None:
    """Restore ``streamlit.*`` subtree without creating half-root state."""
    # Snapshot contains only present keys; absent is implicit.
    snapshot_mods = snapshot.sys_modules
    cur_mods: dict[str, Any] = {}
    for key, val in sys.modules.items():
        if _is_streamlit_key(key):
            cur_mods[key] = val

    cur_root = cur_mods.get("streamlit")
    cur_is_fake = _is_fake_streamlit_module(cur_root)
    # Innocent real import: snapshot empty (absent) and current is real.
    # Leave it — do not pop legitimate real tree.
    innocent_real_import = not snapshot_mods and cur_root is not None and not cur_is_fake
    if innocent_real_import:
        # Only ensure snapshot keys that are missing are restored (none in this case).
        # Do not pop innocent real children.
        for key, val in snapshot_mods.items():
            if sys.modules.get(key) is not val:
                sys.modules[key] = val
        return

    if cur_is_fake:
        # Leaked fake — remove all current streamlit keys not in snapshot,
        # then restore snapshot's real tree.
        for key in list(cur_mods.keys()):
            if key not in snapshot_mods:
                sys.modules.pop(key, None)
        for key, val in snapshot_mods.items():
            if sys.modules.get(key) is not val:
                sys.modules[key] = val
        # Also handle snapshot empty + fake: pop everything
        if not snapshot_mods:
            for key in list(cur_mods.keys()):
                sys.modules.pop(key, None)
        return

    # Current is real or absent — restore missing/changed snapshot keys,
    # but do not pop innocent extra real keys.
    # This covers: real present vs real present (no change),  # noqa: E501 - explanatory comment length
    # real absent vs real present (handled above),
    # and fake vs real already handled. For real->absent (test removed real), restore.
    for key, val in snapshot_mods.items():
        cur_val = sys.modules.get(key)
        if cur_val is not val:
            sys.modules[key] = val
    # If snapshot had real and current is absent (removed), the loop restores.
    # If snapshot had real and current is real with same keys, no pop needed.
    # If current has extra keys not in snapshot but current is real, leave them
    # (they are innocent extension of real tree that was already present).


def _restore_apptest(snapshot: StreamlitIsolationSnapshot) -> None:
    import importlib

    mod = sys.modules.get(_RUNTIME_MODULE)
    if mod is None:
        try:
            mod = importlib.import_module(_RUNTIME_MODULE)
        except (ImportError, ModuleNotFoundError):
            return
    cur_installed = bool(getattr(mod, "_installed", False))
    if cur_installed != snapshot.apptest_installed:
        if snapshot.apptest_installed:
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
    # Intentionally do NOT restore _has_run_first per-test;
    # that flag is process-scoped (first AppTest.run in process), not per-test.


def _restore_cwd(snapshot: StreamlitIsolationSnapshot) -> None:
    try:
        cur_cwd = os.getcwd()
    except OSError:
        cur_cwd = ""
    if cur_cwd != snapshot.cwd and snapshot.cwd and Path(snapshot.cwd).exists():
        os.chdir(snapshot.cwd)


def _restore_env(snapshot: StreamlitIsolationSnapshot) -> None:
    for var, val in snapshot.env.items():
        if val is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = val


def _restore_finder(snapshot: StreamlitIsolationSnapshot) -> None:
    import contextlib

    tc = sys.modules.get("tests.conftest")
    if tc is None:
        return
    finder = getattr(tc, "_finder", None)
    if finder is None:
        return
    is_present = finder in sys.meta_path
    if snapshot.finder_present and not is_present:
        sys.meta_path.insert(0, finder)
    elif not snapshot.finder_present and is_present:
        with contextlib.suppress(ValueError):
            sys.meta_path.remove(finder)


def restore_streamlit_snapshot(snapshot: StreamlitIsolationSnapshot) -> None:
    """Restore only relevant state from snapshot."""
    first_exc: BaseException | None = None

    try:
        _restore_streamlit_modules(snapshot)
    except BaseException as exc:
        first_exc = exc

    try:
        _restore_apptest(snapshot)
    except BaseException as exc:
        if first_exc is None:
            first_exc = exc

    try:
        _restore_cwd(snapshot)
    except OSError as exc:
        if first_exc is None:
            first_exc = exc
    except BaseException as exc:
        if first_exc is None:
            first_exc = exc

    try:
        _restore_env(snapshot)
    except OSError as exc:
        if first_exc is None:
            first_exc = exc
    except BaseException as exc:
        if first_exc is None:
            first_exc = exc

    try:
        _restore_finder(snapshot)
    except BaseException as exc:
        if first_exc is None:
            first_exc = exc

    if first_exc is not None:
        raise first_exc


def diagnose_streamlit_leak(
    before: StreamlitIsolationSnapshot, after: StreamlitIsolationSnapshot | None = None
) -> dict[str, object]:
    """Report relevant leaked state without dumping credentials or entire env.

    Returns a small dict with only relevant keys, values truncated, secrets redacted.
    """
    if after is None:
        after = capture_streamlit_snapshot()

    leaked: dict[str, object] = {}

    # Check sys.modules — only report when the post-state is fake.
    # Legitimate lazy import of the real ``streamlit`` package is not a leak.
    sys_leaked: list[str] = []
    before_keys = set(before.sys_modules.keys())
    after_keys = set(after.sys_modules.keys())
    all_keys = before_keys | after_keys
    before_root = before.sys_modules.get("streamlit")
    after_root = after.sys_modules.get("streamlit")
    after_is_fake = _is_fake_streamlit_module(after_root) if after_root is not None else False
    before_is_fake = _is_fake_streamlit_module(before_root) if before_root is not None else False

    # If after is fake, any delta is leak. If both are real (or absent), delta is innocent.
    if after_is_fake or before_is_fake:
        for key in sorted(all_keys):
            before_present = key in before.sys_modules
            after_present = key in after.sys_modules
            before_val = before.sys_modules.get(key)
            after_val = after.sys_modules.get(key)
            if before_present != after_present:
                sys_leaked.append(
                    f"{key}:{'present' if after_present else 'absent'}"  # noqa: E501 - compact leak descriptor
                    f"(was {'present' if before_present else 'absent'})"
                )
            elif after_present and before_present and before_val is not after_val:
                before_id = id(before_val) if before_val is not None else 0
                after_id = id(after_val) if after_val is not None else 0
                if before_id != after_id:
                    is_fake = False
                    try:
                        # For root, fake lacks secrets; for children, infer from root.
                        if key == "streamlit":
                            is_fake = _is_fake_streamlit_module(after_val)
                        else:
                            is_fake = after_is_fake
                    except Exception:
                        is_fake = after_is_fake
                    sys_leaked.append(f"{key}:identity_changed(fake={is_fake})")
    else:
        # After is real (or absent) and before is real (or absent) — not a leak.
        # But handle the case where real was removed (before present, after absent) as leak.
        # That would be a test deleting the real package — treat as leak.
        for key in sorted(all_keys):
            before_present = key in before.sys_modules
            after_present = key in after.sys_modules
            if before_present and not after_present:
                # Real was present before, now absent — leak (removal)
                sys_leaked.append(f"{key}:absent(was present)")
        # If after is real and before absent, it's innocent import — no leak, # noqa: E501 - explanatory
        # so leave sys_leaked empty.
        # Clear the removal entries if after is real innocent import? No, # noqa: E501 - explanatory
        # removal is different from addition.
        # For innocent import, before_keys is empty, after_keys many, but  # noqa: E501 - explanatory
        # after_is_fake False, so we would not enter the fake branch; we # noqa: E501 - explanatory
        # enter else and check removals, but additions are not removals, # noqa: E501 - explanatory
        # so sys_leaked stays empty.
        # That's correct.

    # If we added removal leaks but after is innocent real import, we # noqa: E501 - explanatory
    # should not have added additions.
    # However the else branch currently only adds removals, not additions, # noqa: E501 - explanatory
    # so innocent import stays empty.

    if sys_leaked:
        leaked["sys_modules"] = sys_leaked

    if before.apptest_installed != after.apptest_installed:
        leaked["apptest_installed"] = {
            "before": before.apptest_installed,
            "after": after.apptest_installed,
        }

    if before.apptest_has_run_first != after.apptest_has_run_first:
        leaked["has_run_first"] = {
            "before": before.apptest_has_run_first,
            "after": after.apptest_has_run_first,
        }

    if before.apptest_run_id != after.apptest_run_id:
        leaked["apptest_run_id_changed"] = True

    if before.cwd != after.cwd:
        leaked["cwd"] = {"before": before.cwd, "after": after.cwd}

    env_changed: list[str] = []
    for var in _RELEVANT_ENV_VARS:
        if before.env.get(var) != after.env.get(var):
            before_present = before.env.get(var) is not None
            after_present = after.env.get(var) is not None
            if before_present != after_present:
                env_changed.append(
                    f"{var}:{'set' if after_present else 'unset'}"  # noqa: E501 - compact env descriptor
                    f"(was {'set' if before_present else 'unset'})"
                )
            else:
                env_changed.append(f"{var}:changed")
    if env_changed:
        leaked["env"] = env_changed

    if before.finder_present != after.finder_present:
        leaked["finder_present"] = {
            "before": before.finder_present,
            "after": after.finder_present,
        }

    if sys_leaked or "apptest_installed" in leaked or "cwd" in leaked or "finder_present" in leaked:
        try:
            mod = sys.modules.get("streamlit")
            if mod is not None:
                has_secrets = hasattr(mod, "secrets")
                leaked["streamlit_has_secrets"] = has_secrets
                leaked["streamlit_id"] = id(mod)
            else:
                leaked["streamlit_present"] = False
        except (AttributeError, TypeError):
            pass

    return leaked


def has_meaningful_streamlit_leak(leak: dict[str, object]) -> bool:
    """Predicate for meaningful isolation breach (not just informational metadata).

    Returns True only for actual state leaks that the guard should report:
    - streamlit module presence/identity changed to a fake (sys_modules)
    - cwd / finder where applicable (cwd, finder_present)

    Legitimate first-AppTest initialization (``apptest_installed`` false→true)
    is not a leak by itself and is ignored; a fake still warns via
    ``sys_modules``. Transient ``has_run_first`` or ``apptest_run_id_changed``
    alone and informational ``streamlit_has_secrets`` / ``streamlit_id`` are
    also ignored. ``env`` alone is not warned (restored but not leaked).
    """
    meaningful_keys = {"sys_modules", "cwd", "finder_present"}
    return any(key in leak for key in meaningful_keys)


def format_leak_report(leak: dict[str, object]) -> str:
    """Format leak dict as compact string for test failure output."""
    if not leak:
        return "No Streamlit isolation leak detected."
    parts: list[str] = ["Streamlit isolation leak:"]
    for k, v in leak.items():
        parts.append(f"  {k}: {v}")
    return "\n".join(parts)


class StreamlitIsolation:
    """Context manager that snapshots on enter and restores on exit."""

    def __init__(self) -> None:
        self._snapshot: StreamlitIsolationSnapshot | None = None

    def __enter__(self) -> StreamlitIsolationSnapshot:
        self._snapshot = capture_streamlit_snapshot()
        return self._snapshot

    def __exit__(  # noqa: ANN401
        self,
        exc_type: Any,  # noqa: ANN401
        exc: Any,  # noqa: ANN401
        tb: Any,  # noqa: ANN401
    ) -> None:
        if self._snapshot is not None:
            restore_streamlit_snapshot(self._snapshot)
            self._snapshot = None
