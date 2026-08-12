"""Fork-safety regression for the production SUMO version probe (V4, Phase 10).

Observed during V4 integration review: repeated
``pytest tests/ui/test_accessibility.py`` runs emitted hidden
``Fatal Python error: Segmentation fault`` on stderr while pytest still
reported all tests passing. The traceback pointed at the child forked by
``subprocess.run`` inside ``sumo_execution.service._probe_version`` while the
SUMO import page rendered under Streamlit AppTest — the same macOS
fork-after-AppTest class Lane 12 fixed for test support, occurring here in
production code. ``_probe_version`` now spawns via ``os.posix_spawn``
(``_spawn_capture_output``), which never forks the interpreter.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from traffictwin.integration.sumo_execution.service import (
    _probe_version,
    _spawn_capture_output,
)

_FAKE_SUMO = "#!/bin/sh\necho 'Eclipse SUMO sumo Version 1.27.0'\n"


def _write_executable(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _open_fd_count() -> int:
    return len(os.listdir("/dev/fd"))


def test_spawn_capture_collects_stdout_and_stderr(tmp_path: Path) -> None:
    script = _write_executable(
        tmp_path / "both.sh", "#!/bin/sh\necho out-line\necho err-line >&2\n"
    )
    stdout, stderr = _spawn_capture_output([str(script)], timeout_s=10)
    assert stdout == "out-line\n"
    assert stderr == "err-line\n"


def test_spawn_capture_missing_executable_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        _spawn_capture_output([str(tmp_path / "does-not-exist")], timeout_s=5)


def test_spawn_capture_timeout_kills_child_and_leaks_nothing(tmp_path: Path) -> None:
    script = _write_executable(tmp_path / "hang.sh", "#!/bin/sh\nsleep 60\n")
    fds_before = _open_fd_count()
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        _spawn_capture_output([str(script)], timeout_s=1)
    assert time.monotonic() - started < 10, "timeout must be enforced, not the child's runtime"
    assert _open_fd_count() == fds_before, "no fd may leak on the timeout path"


def test_spawn_capture_leaks_no_fds_on_success(tmp_path: Path) -> None:
    script = _write_executable(tmp_path / "ok.sh", _FAKE_SUMO)
    fds_before = _open_fd_count()
    for _ in range(5):
        stdout, _stderr = _spawn_capture_output([str(script)], timeout_s=10)
        assert "1.27.0" in stdout
    assert _open_fd_count() == fds_before


def test_probe_version_parses_via_spawn(tmp_path: Path) -> None:
    script = _write_executable(tmp_path / "sumo-fake.sh", _FAKE_SUMO)
    assert _probe_version(script) == "1.27.0"


def test_probe_version_survives_apptest_tainted_parent(tmp_path: Path) -> None:
    """The probe must not fork-crash after AppTest has run in the process.

    A child Python process first renders a Streamlit AppTest (recreating the
    threaded parent state the accessibility suite produces), then calls the
    production ``_probe_version`` repeatedly. Under the old ``subprocess.run``
    fork path this intermittently SIGSEGVs the forked grandchild — the probe
    returns None and ``Fatal Python error`` lands on stderr while the exit
    code stays 0. The child is itself spawned with ``_spawn_capture_output``
    so this test also stays safe when earlier tests in the same pytest
    process have run AppTest.
    """

    fake_sumo = _write_executable(tmp_path / "sumo-fake.sh", _FAKE_SUMO)
    inner = tmp_path / "tainted_probe.py"
    inner.write_text(
        textwrap.dedent(
            """
            import sys
            from pathlib import Path

            from streamlit.testing.v1 import AppTest

            AppTest.from_string("import streamlit as st\\nst.title('taint')").run(timeout=15)

            from traffictwin.integration.sumo_execution.service import _probe_version

            fake = Path(sys.argv[1])
            for iteration in range(10):
                version = _probe_version(fake)
                assert version == "1.27.0", f"iteration {iteration}: {version!r}"
            print("PROBE_OK")
            """
        ),
        encoding="utf-8",
    )
    stdout, stderr = _spawn_capture_output(
        [sys.executable, str(inner), str(fake_sumo)], timeout_s=120
    )
    assert "PROBE_OK" in stdout, f"tainted probe failed:\n{stdout}\n{stderr}"
    for marker in ("Fatal Python error", "Segmentation fault"):
        assert marker not in stderr, f"hidden child crash: {marker} in\n{stderr}"
