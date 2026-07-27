"""Run the whole handoff gate suite with one command.

The gates are written down in seven places — `AGENTS.md`, four batch prompts, a
handoff checklist, and whatever the last terminal happened to remember — and a
gate that is easy to forget is a gate that gets forgotten. This script is the
single list, in the order a handoff runs them, with one table at the end.

**It never modifies anything.** Every declared command is read-only: `ruff check`
without `--fix`, `ruff format` with `--check`, `mypy`, `pytest` without `-p
no:cacheprovider` tricks or `--lf` state changes, and `git diff --check`, which
reports whitespace damage rather than repairing it. A test asserts that property
over the declared list rather than trusting this paragraph.

**A gate that did not run is never reported as passed.** Without `--keep-going`
the battery stops at the first failure, and every gate after it appears in the
table as `NOT RUN`. Gates excluded with `--skip` appear as `SKIP`. Both are
visible rows, because the whole value of a one-command battery is that its table
can be pasted into a handoff, and a table that silently omits what it did not do
is worse than no table.

**Nothing here is parallelised.** Each command runs to completion, one at a
time, in the declared order. `--skip` exists partly so that a suite which must
not run right now — the integration suite while a campaign holds the machine —
is excluded explicitly and shows up as excluded, rather than being quietly
dropped or run anyway.

Exit code is 0 only when every gate that ran passed and none were skipped or
left unrun.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

#: Longest a single gate may run before it is killed and reported as failed.
GATE_TIMEOUT_SECONDS = 7_200
DEFAULT_TAIL_LINES = 15


class GateStatus(StrEnum):
    """What happened to one declared gate."""

    PASSED = "PASS"
    FAILED = "FAIL"
    SKIPPED = "SKIP"
    NOT_RUN = "NOT RUN"


@dataclass(frozen=True)
class Gate:
    """One read-only command in the handoff battery."""

    name: str
    argv: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class CommandOutcome:
    """What a runner reports back about one executed command."""

    exit_code: int
    output: str


@dataclass(frozen=True)
class GateResult:
    """The row this gate contributes to the final table."""

    gate: Gate
    status: GateStatus
    exit_code: int | None
    duration_seconds: float
    output: str

    @property
    def ok(self) -> bool:
        return self.status is GateStatus.PASSED


#: The handoff battery, in the order a handoff runs it.
#:
#: ``ruff format --check`` is repository-wide here. The per-feature gate checks
#: only the files that feature touched; a battery cannot know what "touched"
#: means, and the wider check is the stricter one.
GATES: tuple[Gate, ...] = (
    Gate(
        name="ruff-check",
        argv=("uv", "run", "ruff", "check", "src", "tests", "scripts"),
        summary="Lint rules across source, tests, and scripts.",
    ),
    Gate(
        name="ruff-format",
        argv=("uv", "run", "ruff", "format", "--check", "src", "tests", "scripts"),
        summary="Formatting, checked and never rewritten.",
    ),
    Gate(
        name="mypy",
        argv=("uv", "run", "mypy", "src", "tests"),
        summary="Strict type checking over source and tests.",
    ),
    Gate(
        name="pytest-unit",
        argv=("uv", "run", "pytest", "tests/unit"),
        summary="The unit suite.",
    ),
    Gate(
        name="pytest-ui",
        argv=("uv", "run", "pytest", "tests/ui"),
        summary="The Streamlit AppTest suite.",
    ),
    Gate(
        name="pytest-integration",
        argv=("uv", "run", "pytest", "tests/integration"),
        summary="The integration suite.",
    ),
    Gate(
        name="git-diff-check",
        argv=("git", "diff", "--check"),
        summary="Whitespace damage in the working tree, reported not repaired.",
    ),
)

#: Argument fragments that would make a gate write something. Declared here so
#: the test can assert the list stays read-only as gates are added.
MUTATING_ARGUMENTS: tuple[str, ...] = (
    "--fix",
    "--unsafe-fixes",
    "--write",
    "-w",
    "--in-place",
    "--snapshot-update",
    "add",
    "commit",
    "push",
    "checkout",
    "fetch",
    "pull",
    "reset",
    "clean",
)


class GateBatteryError(RuntimeError):
    """Raised when the battery cannot be assembled from the given arguments."""


def main(argv: list[str] | None = None) -> int:
    """Run the battery and print the table."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.list_only:
        for line in render_listing(GATES):
            print(line)
        return 0
    try:
        selected = select_gates(GATES, skip=arguments.skip or [])
    except GateBatteryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    results = run_battery(
        GATES,
        selected={gate.name for gate in selected},
        keep_going=bool(arguments.keep_going),
        tail_lines=arguments.tail_lines,
        runner=run_command,
        report=print,
    )
    print("")
    for line in render_table(results):
        print(line)
    return 0 if all(result.ok for result in results) else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_all_gates",
        description="Run the full handoff gate suite in order and print one PASS/FAIL table.",
        epilog=(
            "Read-only: no gate rewrites a file, and a gate that did not run is reported "
            "as NOT RUN or SKIP rather than as a pass."
        ),
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Run every gate even after one fails, instead of stopping at the first failure.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        metavar="NAME",
        default=None,
        help=(
            "Repeatable. Exclude a gate by name; it appears in the table as SKIP and the "
            "battery still exits non-zero. Names: " + ", ".join(gate.name for gate in GATES)
        ),
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=DEFAULT_TAIL_LINES,
        help=f"Lines of each command's output to echo (default: {DEFAULT_TAIL_LINES}).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="Print the declared commands and exit without running anything.",
    )
    return parser


def select_gates(gates: Sequence[Gate], *, skip: Sequence[str]) -> list[Gate]:
    """Return the gates to run, refusing a ``--skip`` name that does not exist.

    An unknown skip name is a refusal rather than a no-op: a typo that silently
    skipped nothing would produce a table claiming more coverage than was asked
    for, and a typo that silently skipped everything would claim less.
    """

    known = {gate.name for gate in gates}
    unknown = sorted(set(skip) - known)
    if unknown:
        raise GateBatteryError(
            f"unknown gate name(s) to skip: {', '.join(unknown)}; known: {', '.join(sorted(known))}"
        )
    excluded = set(skip)
    return [gate for gate in gates if gate.name not in excluded]


def run_battery(
    gates: Sequence[Gate],
    *,
    selected: set[str],
    keep_going: bool,
    tail_lines: int,
    runner: Callable[[Sequence[str]], CommandOutcome],
    report: Callable[[str], None],
    clock: Callable[[], float] = time.monotonic,
) -> list[GateResult]:
    """Run each selected gate in order and return one result per declared gate.

    Every declared gate gets a row, including the ones that were skipped and the
    ones that were never reached, so the returned list is a complete account of
    the battery rather than a list of things that happened to run.
    """

    results: list[GateResult] = []
    stopped = False
    for gate in gates:
        if gate.name not in selected:
            results.append(_unrun(gate, GateStatus.SKIPPED))
            continue
        if stopped:
            results.append(_unrun(gate, GateStatus.NOT_RUN))
            continue

        report(f"→ {gate.name}: {' '.join(gate.argv)}")
        started = clock()
        outcome = runner(gate.argv)
        duration = max(0.0, clock() - started)
        status = GateStatus.PASSED if outcome.exit_code == 0 else GateStatus.FAILED
        results.append(
            GateResult(
                gate=gate,
                status=status,
                exit_code=outcome.exit_code,
                duration_seconds=duration,
                output=outcome.output,
            )
        )
        for line in tail(outcome.output, tail_lines):
            report(f"    {line}")
        report(f"  {status.value} ({_duration(duration)})")
        if status is GateStatus.FAILED and not keep_going:
            stopped = True
    return results


def _unrun(gate: Gate, status: GateStatus) -> GateResult:
    return GateResult(gate=gate, status=status, exit_code=None, duration_seconds=0.0, output="")


def tail(output: str, lines: int) -> list[str]:
    """Return the last ``lines`` non-empty lines of a command's output."""

    if lines <= 0:
        return []
    kept = [line.rstrip() for line in output.splitlines() if line.strip()]
    return kept[-lines:]


def run_command(argv: Sequence[str]) -> CommandOutcome:
    """Run one gate command. Never a shell, never in parallel, never modifying."""

    executable = shutil.which(argv[0])
    if executable is None:
        return CommandOutcome(exit_code=127, output=f"{argv[0]} is not on PATH")
    try:
        completed = subprocess.run(  # noqa: S603 - fixed read-only argv, never a shell
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            check=False,
            timeout=GATE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return CommandOutcome(
            exit_code=124,
            output=f"gate exceeded {GATE_TIMEOUT_SECONDS}s and was killed",
        )
    except (OSError, subprocess.SubprocessError) as error:
        return CommandOutcome(exit_code=125, output=f"gate could not be run: {error}")
    return CommandOutcome(
        exit_code=completed.returncode,
        output=(completed.stdout or "") + (completed.stderr or ""),
    )


def render_table(results: Sequence[GateResult]) -> list[str]:
    """Render the final table: every declared gate, its status, and its duration."""

    header = ("GATE", "STATUS", "DURATION", "COMMAND")
    rows = [
        (
            result.gate.name,
            result.status.value,
            _duration(result.duration_seconds) if result.status is not GateStatus.SKIPPED else "-",
            " ".join(result.gate.argv),
        )
        for result in results
    ]
    widths = [max(len(row[index]) for row in [header, *rows]) for index in range(len(header))]
    lines = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(header)).rstrip(),
        "  ".join("-" * widths[index] for index in range(len(header))),
    ]
    lines += [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip()
        for row in rows
    ]
    lines.append("")
    lines.append(summarise(results))
    return lines


def summarise(results: Sequence[GateResult]) -> str:
    """One line naming exactly what passed and what did not."""

    counts = dict.fromkeys(GateStatus, 0)
    for result in results:
        counts[result.status] += 1
    parts = [f"{counts[status]} {status.value.lower()}" for status in GateStatus if counts[status]]
    verdict = "ALL GATES PASSED" if all(result.ok for result in results) else "BATTERY INCOMPLETE"
    unfinished = [result.gate.name for result in results if result.status is GateStatus.NOT_RUN]
    trailer = f"; not run: {', '.join(unfinished)}" if unfinished else ""
    total = sum(result.duration_seconds for result in results)
    return f"{verdict} — {', '.join(parts)} in {_duration(total)}{trailer}"


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes}m{remainder:02d}s"


def render_listing(gates: Sequence[Gate]) -> list[str]:
    """Render the declared commands without running any of them."""

    lines = ["declared gates, in order:"]
    for index, gate in enumerate(gates, start=1):
        lines.append(f"  {index}. {gate.name}: {' '.join(gate.argv)}")
        lines.append(f"     {gate.summary}")
    lines.append("")
    lines.append("every command above is read-only; none of them rewrites a file.")
    return lines


if __name__ == "__main__":
    sys.exit(main())
