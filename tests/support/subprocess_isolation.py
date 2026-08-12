"""Process-safe probe launcher using posix_spawn to avoid fork-unsafe SIGSEGV.

After an in-process ``AppTest.run()`` the parent pytest process contains
threads and locks that make ``fork()`` (used implicitly by
``subprocess.run(capture_output=True)``) unsafe on macOS, leading to
``returncode=-11`` with empty stdout/stderr. ``os.posix_spawn`` avoids the
unsafe fork path and remains stable even when the parent has previously
rendered AppTest.

This helper provides a ``subprocess.run``-like interface that works after
AppTest, using ``os.posix_spawn`` with explicit file actions for
stdout/stderr capture and ``/dev/null`` stdin. It is intentionally minimal
and does not add new dependencies.
"""

from __future__ import annotations

import contextlib
import os
import select
import time
from collections.abc import Mapping
from pathlib import Path


class SpawnResult:
    """Minimal ``CompletedProcess``-like result for probe assertions."""

    def __init__(self, args: list[str], returncode: int, stdout: str, stderr: str) -> None:
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def posix_spawn_run(
    cmd: list[str],
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> SpawnResult:
    """Run ``cmd`` via ``os.posix_spawn`` and capture stdout/stderr.

    This avoids the ``fork()``-based ``subprocess`` path that SIGSEGVs after
    AppTest. It is safe to call even when the parent has previously executed
    ``AppTest.run()``.
    """
    # Fast path: if posix_spawn not available, fall back to subprocess (unsafe).
    if not hasattr(os, "posix_spawn"):
        import subprocess  # noqa: S603 - fallback

        result = subprocess.run(  # noqa: S603 - fallback posix_spawn unavailable
            cmd,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return SpawnResult(list(cmd), result.returncode, result.stdout, result.stderr)

    # Prepare pipes for stdout/stderr.
    r_out, w_out = os.pipe()
    r_err, w_err = os.pipe()
    # Open /dev/null for stdin.
    devnull_fd = os.open(os.devnull, os.O_RDONLY)

    # File actions for child: stdin from devnull, stdout/stderr to pipes.
    # Close read ends in child, close write ends are duped.
    file_actions: list[tuple[int, int, int] | tuple[int, int]] = [
        (os.POSIX_SPAWN_DUP2, devnull_fd, 0),
        (os.POSIX_SPAWN_DUP2, w_out, 1),
        (os.POSIX_SPAWN_DUP2, w_err, 2),
        (os.POSIX_SPAWN_CLOSE, r_out),
        (os.POSIX_SPAWN_CLOSE, r_err),
    ]

    # Handle cwd by temporarily chdir in parent around spawn, restoring after.
    # This is not thread-safe but tests run serially.
    orig_cwd: str | None = None
    if cwd is not None:
        orig_cwd = os.getcwd()
        cwd_str = str(cwd)
    else:
        cwd_str = None

    # Prepare env dict.
    if env is None:
        env_dict: dict[str, str] | None = None
    else:
        env_dict = {str(k): str(v) for k, v in env.items()}

    pid: int | None = None
    try:
        if cwd_str is not None:
            os.chdir(cwd_str)
        # posix_spawn expects argv[0] as path, and argv list including program.
        # Use posix_spawnp to search PATH if needed, but we have absolute path via sys.executable.
        # Use posix_spawn with setsid=True to isolate.
        pid = os.posix_spawn(
            cmd[0],
            cmd,
            env_dict if env_dict is not None else os.environ,
            file_actions=file_actions,
            setsid=True,
        )
    finally:
        if orig_cwd is not None:
            with contextlib.suppress(OSError):
                os.chdir(orig_cwd)
        # Close child-side fds in parent.
        with contextlib.suppress(OSError):
            os.close(devnull_fd)
        with contextlib.suppress(OSError):
            os.close(w_out)
        with contextlib.suppress(OSError):
            os.close(w_err)

    assert pid is not None

    # Read stdout/stderr with timeout handling.
    # Use non-blocking read via select.
    out_chunks: list[bytes] = []
    err_chunks: list[bytes] = []
    # Make read ends non-blocking.
    try:
        os.set_blocking(r_out, False)
        os.set_blocking(r_err, False)
    except AttributeError:
        # Python <3.7 fallback: use fcntl
        import fcntl

        for fd in (r_out, r_err):
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    # Track which fds are still open.
    open_fds = {r_out, r_err}
    fd_to_chunks: dict[int, list[bytes]] = {r_out: out_chunks, r_err: err_chunks}
    # Wait for child with timeout.
    start = time.monotonic()
    returncode: int | None = None
    # Use select to read while waiting.
    while open_fds or returncode is None:
        # Check timeout.
        if timeout is not None and (time.monotonic() - start) > timeout:
            with contextlib.suppress(OSError):
                os.kill(pid, 9)
            # Drain what we have.
            for fd in list(open_fds):
                try:
                    while True:
                        chunk = os.read(fd, 4096)
                        if not chunk:
                            break
                        fd_to_chunks[fd].append(chunk)
                except (BlockingIOError, OSError):
                    pass
                with contextlib.suppress(OSError):
                    os.close(fd)
                open_fds.discard(fd)
            # Reap child.
            try:
                _, status = os.waitpid(pid, 0)
                if os.WIFEXITED(status):
                    returncode = os.WEXITSTATUS(status)
                elif os.WIFSIGNALED(status):
                    returncode = -os.WTERMSIG(status)
                else:
                    returncode = -1
            except ChildProcessError:
                returncode = -1
            break

        # Check if child exited (non-blocking).
        try:
            pid_result, status = os.waitpid(pid, os.WNOHANG)
            if pid_result == pid:
                if os.WIFEXITED(status):
                    returncode = os.WEXITSTATUS(status)
                elif os.WIFSIGNALED(status):
                    returncode = -os.WTERMSIG(status)
                else:
                    returncode = -1
                # Child exited, but still need to drain pipes.
        except ChildProcessError:
            returncode = -1

        # Use select to wait for data with short timeout.
        if open_fds:
            try:
                readable, _, _ = select.select(list(open_fds), [], [], 0.1)
            except (OSError, ValueError):
                readable = []
            for fd in readable:
                try:
                    chunk = os.read(fd, 4096)
                    if chunk == b"":
                        # EOF
                        with contextlib.suppress(OSError):
                            os.close(fd)
                        open_fds.discard(fd)
                    else:
                        fd_to_chunks[fd].append(chunk)
                except (BlockingIOError, OSError):
                    continue

        # If child has exited and no more data, break.
        if returncode is not None and not open_fds:
            break
        # Small sleep to avoid busy loop if no select.
        if not open_fds and returncode is None:
            time.sleep(0.01)

    # Ensure child reaped if not already.
    if returncode is None:
        try:
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                returncode = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                returncode = -os.WTERMSIG(status)
            else:
                returncode = -1
        except ChildProcessError:
            returncode = -1

    # Close any remaining fds.
    for fd in list(open_fds):
        with contextlib.suppress(OSError):
            os.close(fd)

    stdout = b"".join(out_chunks).decode("utf-8", errors="replace")
    stderr = b"".join(err_chunks).decode("utf-8", errors="replace")
    return SpawnResult(list(cmd), int(returncode) if returncode is not None else -1, stdout, stderr)
