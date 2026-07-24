"""Run the immutable v0.6.0 release beside the v0.7 checkout without collision.

The script creates a clean detached checkout of the `v0.6.0` tag, installs it
from its own lockfile, initialises a synthetic demo workspace with its own
CLI, and serves it on one port while the current v0.7 checkout serves an
isolated `workspace-v0.7` on another port. It then verifies both servers
respond, that every workspace/registry path is distinct, and that neither
side changed the other side's registry bytes. A machine-readable evidence
record is written for the project records.

This is REL-01/Gate-F side-by-side evidence only: it proves independent
installation and coexistence, not release acceptance, migration approval, or
any capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

V06_TAG = "v0.6.0"
V06_COMMIT = "1c50a25246426128ac6e8530240eff362d16be02"
SCHEMA_VERSION = "traffictwin.side-by-side-check.v1"


def main() -> int:
    """Run the complete check and return a process exit code."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port-v06", type=int, default=8611)
    parser.add_argument("--port-v07", type=int, default=8612)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/integration/evidence/side_by_side_check.json"),
    )
    arguments = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    findings: list[str] = []
    scratch = Path(tempfile.mkdtemp(prefix="traffictwin-side-by-side-"))
    checkout = scratch / "traffictwin-v0.6.0"
    processes: list[subprocess.Popen[bytes]] = []
    worktree_added = False
    try:
        _run(["git", "worktree", "add", "--detach", str(checkout), V06_TAG], cwd=repo_root)
        worktree_added = True
        head = _run(["git", "rev-parse", "HEAD"], cwd=checkout).strip()
        _require(head == V06_COMMIT, f"clean checkout is at {head}, expected {V06_COMMIT}")
        findings.append(f"clean v0.6.0 checkout created at commit {head}")

        _run(["uv", "sync", "--frozen", "--python", "3.12"], cwd=checkout)
        v06_python = checkout / ".venv/bin/python"
        v06_cli = checkout / ".venv/bin/traffictwin"
        _require(v06_cli.is_file(), "v0.6.0 installation did not produce its CLI entry point")
        findings.append("v0.6.0 installed independently from its own lockfile")

        demo_workspace = scratch / "demo-v0.6"
        _run([str(v06_cli), "demo", "initialise", str(demo_workspace)], cwd=checkout)
        status = _run([str(v06_cli), "demo", "status", str(demo_workspace)], cwd=checkout)
        _require("valid_workspace: True" in status, "v0.6.0 demo workspace failed validation")
        findings.append("v0.6.0 CLI initialised and validated its own synthetic demo workspace")

        v07_workspace = scratch / "workspace-v0.7"
        v07_python = repo_root / ".venv/bin/python"
        v07_cli = repo_root / ".venv/bin/traffictwin"
        _run([str(v07_cli), "release", "v07-workspace-init", str(v07_workspace)], cwd=repo_root)
        findings.append("v0.7 checkout initialised its separately marked workspace")

        v06_registry = demo_workspace / "registry.sqlite"
        v07_registry = v07_workspace / "registry" / "traffictwin.sqlite"
        registries_distinct = v06_registry.resolve() != v07_registry.resolve()
        _require(registries_distinct, "workspace registries must be distinct files")
        v06_registry_before = _sha256(v06_registry)
        v07_registry_before = _sha256(v07_registry)

        processes.append(
            _start_streamlit(
                v06_python,
                checkout,
                arguments.port_v06,
                {
                    "TRAFFICTWIN_WORKSPACE_PATH": str(demo_workspace),
                    "TRAFFICTWIN_REGISTRY_PATH": str(v06_registry),
                    "TRAFFICTWIN_FIXTURE_PATH": str(demo_workspace / "bundles"),
                },
            )
        )
        processes.append(
            _start_streamlit(
                v07_python,
                repo_root,
                arguments.port_v07,
                {
                    "TRAFFICTWIN_WORKSPACE_PATH": str(v07_workspace),
                    "TRAFFICTWIN_REGISTRY_PATH": str(v07_registry),
                },
            )
        )
        v06_status = _wait_for_http(arguments.port_v06, arguments.timeout_seconds)
        # Both servers must be our own live processes, not a pre-existing squatter
        # on the port, or the coexistence claim would be false.
        _require(
            processes[0].poll() is None,
            "the v0.6.0 server process exited before responding (port may be in use)",
        )
        v07_status = _wait_for_http(arguments.port_v07, arguments.timeout_seconds)
        _require(
            processes[1].poll() is None,
            "the v0.7 server process exited before responding (port may be in use)",
        )
        _require(v06_status == 200, f"v0.6.0 server returned HTTP {v06_status}")
        _require(v07_status == 200, f"v0.7 server returned HTTP {v07_status}")
        findings.append(
            f"both servers responded concurrently (v0.6.0 on {arguments.port_v06}, "
            f"v0.7 on {arguments.port_v07})"
        )

        _require(
            processes[0].poll() is None and _wait_for_http(arguments.port_v06, 10) == 200,
            "v0.6.0 server stopped responding while v0.7 was serving",
        )
        v06_registry_after = _sha256(v06_registry)
        v07_registry_after = _sha256(v07_registry)
        v07_unchanged = v07_registry_after == v07_registry_before
        v06_unchanged = v06_registry_after == v06_registry_before
        _require(v07_unchanged, "the v0.7 registry changed while serving side by side")
        _require(v06_unchanged, "the v0.6.0 registry changed while serving side by side")
        cross_registry_mutation_observed = not (v06_unchanged and v07_unchanged)
        findings.append("neither registry changed while both applications served")

        evidence = {
            "schema_version": SCHEMA_VERSION,
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "v06_tag": V06_TAG,
            "v06_commit": head,
            "v07_commit": _run(["git", "rev-parse", "HEAD"], cwd=repo_root).strip(),
            "v06_port": arguments.port_v06,
            "v07_port": arguments.port_v07,
            "v06_http_status": v06_status,
            "v07_http_status": v07_status,
            "v06_registry_sha256": v06_registry_after,
            "v07_registry_sha256": v07_registry_after,
            "registries_distinct": registries_distinct,
            "cross_registry_mutation_observed": cross_registry_mutation_observed,
            "findings": findings,
            "release_acceptance": "not_claimed",
            "capability_status": "REL-01 remains planned",
        }
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for line in findings:
            print(f"ok: {line}")
        print(f"evidence: {arguments.output}")
        return 0
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        if worktree_added:
            subprocess.run(  # noqa: S603 - fixed argv, no shell.
                ["git", "worktree", "remove", "--force", str(checkout)],  # noqa: S607
                cwd=repo_root,
                check=False,
                capture_output=True,
            )
        subprocess.run(  # noqa: S603 - fixed argv, no shell.
            ["rm", "-rf", str(scratch)],  # noqa: S607
            check=False,
        )


def _run(command: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell.
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=900,
    )
    return completed.stdout


def _start_streamlit(
    python: Path,
    checkout: Path,
    port: int,
    extra_env: dict[str, str],
) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.Popen(  # noqa: S603 - fixed argv, no shell.
        [
            str(python),
            "-m",
            "streamlit",
            "run",
            str(checkout / "src/traffictwin/ui/app.py"),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=checkout,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_http(port: int, timeout_seconds: int) -> int:
    deadline = time.monotonic() + timeout_seconds
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed local http URL.
                f"http://127.0.0.1:{port}/", timeout=5
            ) as response:
                return int(response.status)
        except (urllib.error.URLError, OSError) as exc:
            last_error = str(exc)
            time.sleep(1)
    raise RuntimeError(f"port {port} did not respond within {timeout_seconds}s: {last_error}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


if __name__ == "__main__":
    sys.exit(main())
