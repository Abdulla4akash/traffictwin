#!/usr/bin/env python3
"""Scheduled BODS session supervisor (platform slice 1, decision P-D2).

Runs the committed daily schedule (``docs/platform/bods_schedule.json``)
through the accepted acquisition boundary. The supervisor is designed to be
started ONCE by the owner as a detached process and left alone; it sleeps
until the next window, runs it, and never runs a window late.

Subcommands:

``run``
    Supervise in the foreground. ``--once`` exits after the first completed
    session — the owner-attended smoke the design requires before the first
    unattended day (point it at a temporary schedule file with a 1-snapshot
    window a few minutes ahead).

``launch``
    Start ``run`` detached (``start_new_session`` + ``caffeinate -i`` + log
    file) — the pattern that survives harness/session kills. The supervisor
    writes its own pid file and refuses to start beside a live one, so a
    double launch is safe: the second process exits with a typed refusal.

The API key is read from ``BODS_API_KEY`` and never echoed or persisted. A
missing key refuses at start, not mid-window (design §5).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.bods_live_control import coordinated_bods_live_refresh
from traffictwin.integration.manchester.bods_scheduled_sessions import (
    AcquiredSnapshot,
    BodsScheduledSessionError,
    run_supervisor,
    scheduled_root,
)

#: The Greater Manchester box recorded in the accepted Bee Network probe.
GREATER_MANCHESTER_BOX = BodsBoundingBox(
    min_longitude=Decimal("-2.7304178"),
    min_latitude=Decimal("53.3273147"),
    max_longitude=Decimal("-1.9096224"),
    max_latitude=Decimal("53.6857188"),
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEDULE = REPO_ROOT / "docs" / "platform" / "bods_schedule.json"
_CAFFEINATE = "/usr/bin/caffeinate"


def _require_api_key() -> str | None:
    api_key = os.environ.get("BODS_API_KEY")
    if not api_key:
        print(
            "BODS_API_KEY is not configured; the supervisor refuses to start (design §5).",
            file=sys.stderr,
        )
        return None
    return api_key


def _acquire_factory(workspace: Path, api_key: str) -> Callable[[], AcquiredSnapshot]:
    def _acquire() -> AcquiredSnapshot:
        refresh = coordinated_bods_live_refresh(workspace, GREATER_MANCHESTER_BOX, api_key=api_key)
        summary = refresh.refresh.summary
        return AcquiredSnapshot(
            snapshot_id=summary.snapshot_id,
            records_accepted=summary.records_accepted,
            live_vehicle=summary.live_vehicle,
        )

    return _acquire


def _run(args: argparse.Namespace) -> int:
    api_key = _require_api_key()
    if api_key is None:
        return 2
    workspace = args.workspace.expanduser().resolve()
    schedule_path = args.schedule.expanduser().resolve()
    try:
        sessions_run = run_supervisor(
            workspace,
            schedule_path,
            acquire=_acquire_factory(workspace, api_key),
            max_sessions=1 if args.once else None,
        )
    except BodsScheduledSessionError as error:
        print(str(error), file=sys.stderr)
        return 1
    if args.once:
        print(f"--once: exiting after {sessions_run} session(s)", flush=True)
    return 0


def _launch(args: argparse.Namespace) -> int:
    if _require_api_key() is None:
        return 2
    workspace = args.workspace.expanduser().resolve()
    schedule_path = args.schedule.expanduser().resolve()
    log_path = scheduled_root(workspace) / "supervisor.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        _CAFFEINATE,
        "-i",
        sys.executable,
        str(Path(__file__).resolve()),
        "run",
        "--workspace",
        str(workspace),
        "--schedule",
        str(schedule_path),
    ]
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(  # noqa: S603 - fixed argv built above, never a shell
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    print(f"detached supervisor launched: pid {process.pid}")
    print(f"log: {log_path}")
    print(
        "the supervisor writes its own pid file and refuses to start beside a "
        "live one, so a double launch exits with a typed refusal"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, command in (("run", _run), ("launch", _launch)):
        sub = subparsers.add_parser(name)
        sub.add_argument("--workspace", required=True, type=Path)
        sub.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE)
        if name == "run":
            sub.add_argument(
                "--once",
                action="store_true",
                help="exit after the first completed session (owner-attended smoke)",
            )
        sub.set_defaults(handler=command)
    args = parser.parse_args()
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
