"""Generate the dissertation's quality-gate snapshot appendix.

The write-up's §3.2 quality table is a set of numbers — how many tests exist in
each suite, what the type checker covers, whether lint and format are clean,
which versions of which tools produced all of that, and at which commit. Retyped
by hand they go stale between drafts and nobody can tell which ones did. So they
are collected by this command instead, each one printed beside the exact
invocation a reader runs to re-derive it.

**No test is executed.** Every pytest invocation this script issues carries
``--collect-only -q``: the suites are inventoried, not run. Collection is a
couple of seconds of single-process work, which is why it is safe to take a
snapshot while a long campaign is executing on the same machine.

**A collected count is an inventory, not a result.** The rendered document says
so on the row. `2,744 tests collected` means the suite contains that many tests;
it does not mean they passed, and the dissertation must not let those two read
as the same claim.

**The mypy file count is supplied, not measured.** A full ``mypy src tests``
sweep is sustained compute, which is exactly what a live campaign forbids. The
generator therefore accepts ``--mypy-file-count`` from an operator who has just
run it, and when nobody supplies one it prints the row as *not collected* with
the command beside it. Guessing the number, or silently leaving yesterday's in
place, would be worse than an honest gap.

Ruff check and ruff format are run, because they are seconds of work, and their
status strings are recorded as written rather than flattened into a pass bit.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "dissertation_appendices" / "quality_snapshot.md"

#: Every test suite in the repository, in the order the appendix lists them.
SUITE_PATHS: tuple[tuple[str, str], ...] = (
    ("Unit", "tests/unit"),
    ("UI", "tests/ui"),
    ("Integration", "tests/integration"),
    ("Golden", "tests/golden"),
)

#: Bounded: a collection or version probe that has not answered in this long has
#: gone wrong, and this script must never sit on a machine holding a campaign.
COMMAND_TIMEOUT_SECONDS = 300

NOT_COLLECTED = "not collected in this snapshot"

MYPY_FILE_COUNT_NOTE = (
    "Supplied by the operator from a run of the command beside it. A full type-check sweep "
    "is sustained compute and is not performed by this generator."
)

COLLECTED_NOTE = (
    "Collected, not passed: this is the number of tests the suite contains, which is an "
    "inventory rather than a result."
)


@dataclass(frozen=True)
class CommandResult:
    """One completed probe."""

    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def command(self) -> str:
        return " ".join(self.argv)

    def last_line(self) -> str:
        lines = [line.strip() for line in self.stdout.splitlines() if line.strip()]
        return lines[-1] if lines else ""


CommandRunner = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True)
class Measurement:
    """One appendix row: a value, and the command that reproduces it."""

    label: str
    value: str
    command: str
    note: str = ""


@dataclass(frozen=True)
class QualitySnapshot:
    """Everything the appendix reports, already collected."""

    suites: tuple[Measurement, ...]
    gates: tuple[Measurement, ...]
    tooling: tuple[Measurement, ...]
    repository: tuple[Measurement, ...]
    warnings: tuple[str, ...] = ()

    def sections(self) -> tuple[tuple[str, tuple[Measurement, ...]], ...]:
        return (
            ("Test inventory", self.suites),
            ("Static gates", self.gates),
            ("Toolchain", self.tooling),
            ("Repository", self.repository),
        )


class QualitySnapshotError(RuntimeError):
    """Raised when the snapshot cannot be collected or written."""


def main(argv: list[str] | None = None) -> int:
    """Collect the quality snapshot and write the appendix."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the appendix (default {DEFAULT_OUTPUT.name} in the appendix pack).",
    )
    parser.add_argument(
        "--mypy-file-count",
        type=int,
        default=None,
        help=(
            "Source-file count from a run of `uv run mypy src tests`. Supplied rather than "
            "measured; omit it and the row is reported as not collected."
        ),
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Override the generation timestamp (ISO-8601 UTC). Defaults to now.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="Write nothing; print the rendered appendix to standard output.",
    )
    arguments = parser.parse_args(argv)
    try:
        snapshot = collect_quality_snapshot(
            mypy_file_count=arguments.mypy_file_count,
            ignore_paths=_repo_relative(arguments.output),
        )
        rendered = render_quality_snapshot(
            snapshot, generated_at=arguments.generated_at or _now_utc()
        )
    except QualitySnapshotError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if arguments.print_only:
        print(rendered, end="")
        return 0
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    print(f"written: {arguments.output}")
    for warning in snapshot.warnings:
        print(f"note: {warning}")
    return 0


def collect_quality_snapshot(
    *,
    mypy_file_count: int | None = None,
    runner: CommandRunner | None = None,
    ignore_paths: Sequence[str] = (),
) -> QualitySnapshot:
    """Collect every appendix figure without executing a single test.

    ``ignore_paths`` names repository-relative paths that must not count towards
    the dirty-tree report — in practice the appendix this run is about to write,
    which is an output of the snapshot rather than evidence of unrelated
    uncommitted work.
    """

    run = runner if runner is not None else run_command
    warnings: list[str] = []
    suites = _collect_suites(run, warnings)
    gates = _collect_gates(run, mypy_file_count, warnings)
    tooling = _collect_tooling(run)
    repository = _collect_repository(run, warnings, ignore_paths)
    return QualitySnapshot(
        suites=suites,
        gates=gates,
        tooling=tooling,
        repository=repository,
        warnings=tuple(warnings),
    )


def render_quality_snapshot(snapshot: QualitySnapshot, *, generated_at: str) -> str:
    """Render the appendix; every row carries the command that reproduces it."""

    lines = [
        "# Appendix — Quality-gate snapshot",
        "",
        f"Generated {generated_at} by `uv run python scripts/generate_quality_snapshot.py`.",
        "",
        "Every number below is printed beside the exact command that reproduces it. Nothing",
        "here was retyped from a terminal, and no test was executed to collect it — the",
        "suites are inventoried with `--collect-only`, never run.",
        "",
    ]
    if snapshot.warnings:
        lines.append("## Gaps in this snapshot")
        lines.append("")
        lines.extend(f"- {warning}" for warning in snapshot.warnings)
        lines.append("")
    for title, rows in snapshot.sections():
        lines.extend([f"## {title}", "", "| Measure | Value | Reproduce with |", "|---|---|---|"])
        for row in rows:
            if not row.command:
                raise QualitySnapshotError(
                    f"the row {row.label!r} carries no reproduction command; a number a "
                    "reader cannot re-derive is not evidence"
                )
            lines.append(f"| {row.label} | {row.value} | `{row.command}` |")
        lines.append("")
        notes = [row.note for row in rows if row.note]
        for note in dict.fromkeys(notes):
            lines.append(f"{note}")
            lines.append("")
    lines.extend(
        [
            "## How to read this appendix",
            "",
            "- **Collected is not passed.** The test-inventory rows report how many tests each",
            "  suite contains. A suite result is a separate claim, made by running the suite.",
            "- **The snapshot is of one commit.** If the repository row reports a dirty working",
            "  tree, the figures describe that tree and not the named commit alone.",
            "- **Nothing here is a scientific result.** These are software-quality gates for the",
            "  implementation chapter; they say nothing about any measurement the system makes.",
            "",
        ]
    )
    return "\n".join(lines)


def run_command(argv: Sequence[str]) -> CommandResult:
    """Run one bounded, fixed, read-only probe. Never a shell."""

    executable = shutil.which(argv[0])
    if executable is None:
        return CommandResult(
            argv=tuple(argv), exit_code=127, stdout="", stderr=f"{argv[0]} is not on PATH"
        )
    try:
        completed = subprocess.run(  # noqa: S603 - fixed read-only argv, never a shell
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            cwd=REPO_ROOT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return CommandResult(argv=tuple(argv), exit_code=1, stdout="", stderr=str(error))
    return CommandResult(
        argv=tuple(argv),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def suite_collect_argv(path: str) -> tuple[str, ...]:
    """Return the inventory command for one suite. Always collection-only."""

    return ("uv", "run", "pytest", path, "--collect-only", "-q")


def _collect_suites(run: CommandRunner, warnings: list[str]) -> tuple[Measurement, ...]:
    rows: list[Measurement] = []
    total = 0
    total_known = True
    for label, path in SUITE_PATHS:
        argv = suite_collect_argv(path)
        result = run(argv)
        count = _parse_collected(result)
        if count is None:
            total_known = False
            warnings.append(
                f"The {label.lower()} suite inventory could not be parsed from "
                f"`{result.command}`, so its count is reported as {NOT_COLLECTED}."
            )
            rows.append(Measurement(f"{label} tests", NOT_COLLECTED, result.command))
            continue
        total += count
        rows.append(
            Measurement(f"{label} tests", f"{count:,} collected", result.command, COLLECTED_NOTE)
        )
    total_value = f"{total:,} collected" if total_known else f"at least {total:,} collected"
    rows.append(
        Measurement(
            "All suites",
            total_value,
            "uv run pytest --collect-only -q",
            COLLECTED_NOTE,
        )
    )
    return tuple(rows)


def _collect_gates(
    run: CommandRunner, mypy_file_count: int | None, warnings: list[str]
) -> tuple[Measurement, ...]:
    lint = run(("uv", "run", "ruff", "check", "src", "tests", "scripts"))
    fmt = run(("uv", "run", "ruff", "format", "--check", "src", "tests", "scripts"))
    mypy_command = "uv run mypy src tests"
    if mypy_file_count is None:
        warnings.append(
            f"The type-check file count is {NOT_COLLECTED}: it is supplied rather than "
            f"measured, and no value was passed. Run `{mypy_command}` and re-run this "
            "generator with --mypy-file-count."
        )
        mypy_value = NOT_COLLECTED
    else:
        mypy_value = f"{mypy_file_count:,} source files checked"
    return (
        Measurement("Lint (ruff check)", _status_line(lint, "clean"), lint.command),
        Measurement("Format (ruff format --check)", _status_line(fmt, "clean"), fmt.command),
        Measurement("Strict type check", mypy_value, mypy_command, MYPY_FILE_COUNT_NOTE),
    )


def _collect_tooling(run: CommandRunner) -> tuple[Measurement, ...]:
    probes = (
        ("Python", ("uv", "run", "python", "--version")),
        ("uv", ("uv", "--version")),
        ("Ruff", ("uv", "run", "ruff", "--version")),
        ("mypy", ("uv", "run", "mypy", "--version")),
        ("pytest", ("uv", "run", "pytest", "--version")),
    )
    rows: list[Measurement] = []
    for label, argv in probes:
        result = run(argv)
        rows.append(Measurement(label, _reported_line(result) or NOT_COLLECTED, result.command))
    return tuple(rows)


def _collect_repository(
    run: CommandRunner, warnings: list[str], ignore_paths: Sequence[str]
) -> tuple[Measurement, ...]:
    commit = run(("git", "rev-parse", "HEAD"))
    branch = run(("git", "rev-parse", "--abbrev-ref", "HEAD"))
    status = run(("git", "status", "--porcelain"))
    ignored = set(ignore_paths)
    dirty_paths = [
        line
        for line in status.stdout.splitlines()
        if line.strip() and line[3:].strip().strip('"') not in ignored
    ]
    if dirty_paths:
        warnings.append(
            f"The working tree carried {len(dirty_paths)} uncommitted path(s) when this "
            "snapshot was taken, so the figures describe that tree rather than the named "
            "commit alone."
        )
        tree = f"dirty — {len(dirty_paths)} uncommitted path(s)"
    else:
        tree = "clean"
    return (
        Measurement("Commit", f"`{commit.last_line() or NOT_COLLECTED}`", commit.command),
        Measurement("Branch", branch.last_line() or NOT_COLLECTED, branch.command),
        Measurement("Working tree", tree, status.command),
    )


def _parse_collected(result: CommandResult) -> int | None:
    """Read `N tests collected` out of a `pytest --collect-only -q` summary."""

    for line in reversed(result.stdout.splitlines()):
        text = line.strip()
        if not text:
            continue
        parts = text.split()
        if len(parts) >= 3 and parts[1] in {"test", "tests"} and parts[2] == "collected":
            try:
                return int(parts[0].replace(",", ""))
            except ValueError:
                return None
    return None


def _status_line(result: CommandResult, clean_text: str) -> str:
    """Record what the tool actually said, not a reduced pass/fail bit."""

    text = _reported_line(result)
    if result.exit_code == 0:
        return f"{clean_text} — {text}" if text else clean_text
    return text or f"exit code {result.exit_code}"


def _reported_line(result: CommandResult) -> str:
    """Return what the probe printed, preferring stdout and falling back to stderr."""

    text = result.last_line()
    if text:
        return text
    stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    return stderr_lines[0] if stderr_lines else ""


def _repo_relative(output: Path) -> tuple[str, ...]:
    """Return the output path as git reports it, when it sits inside the repository."""

    try:
        return (Path(output).resolve().relative_to(REPO_ROOT).as_posix(),)
    except ValueError:
        return ()


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
