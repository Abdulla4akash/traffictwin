"""Structural coverage for the single-command gate battery.

No real gate is executed here. Every command is answered from a table by a fake
runner, and the clock is a counter — running the actual suites from a unit test
would take longer than the suites themselves and would prove nothing about the
battery.

What is asserted instead is what makes the battery's table trustworthy: the
declared commands are read-only, a gate that did not run is never rendered as a
pass, a skipped gate is still a visible row, and the exit code is 0 only when
every declared gate genuinely passed.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_all_gates.py"


def _module() -> ModuleType:
    """Load the battery by path; ``scripts/`` is not an importable package."""

    spec = importlib.util.spec_from_file_location("run_all_gates_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BATTERY = _module()


class FakeRunner:
    """Answers each command from a table of exit codes, and records the order."""

    def __init__(self, exit_codes: dict[str, int] | None = None) -> None:
        self.exit_codes = exit_codes or {}
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> object:
        self.calls.append(tuple(argv))
        key = " ".join(argv)
        code = next((value for name, value in self.exit_codes.items() if name in key), 0)
        return BATTERY.CommandOutcome(
            exit_code=code,
            output=f"line one\nline two\nresult for {key}",
        )


class FakeClock:
    """A monotonic counter, so durations are deterministic."""

    def __init__(self, step: float = 2.0) -> None:
        self.step = step
        self.now = 0.0

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value


def _run(
    *,
    exit_codes: dict[str, int] | None = None,
    skip: Sequence[str] = (),
    keep_going: bool = False,
    tail_lines: int = 15,
) -> tuple[list[Any], FakeRunner, list[str]]:
    runner = FakeRunner(exit_codes)
    reported: list[str] = []
    selected = {gate.name for gate in BATTERY.select_gates(BATTERY.GATES, skip=list(skip))}
    results = BATTERY.run_battery(
        BATTERY.GATES,
        selected=selected,
        keep_going=keep_going,
        tail_lines=tail_lines,
        runner=runner,
        report=reported.append,
        clock=FakeClock(),
    )
    return results, runner, reported


# --- the declared command list ----------------------------------------------


def test_the_battery_declares_the_handoff_gates_in_order() -> None:
    names = [gate.name for gate in BATTERY.GATES]

    assert names == [
        "ruff-check",
        "ruff-format",
        "mypy",
        "pytest-unit",
        "pytest-ui",
        "pytest-integration",
        "git-diff-check",
    ]


def test_every_declared_command_is_read_only() -> None:
    """The battery reports on the tree; it never edits it."""

    for gate in BATTERY.GATES:
        for argument in gate.argv:
            assert argument not in BATTERY.MUTATING_ARGUMENTS, (
                f"gate {gate.name} would modify the tree: {' '.join(gate.argv)}"
            )


def test_ruff_format_is_checked_and_never_rewritten() -> None:
    formatting = next(gate for gate in BATTERY.GATES if gate.name == "ruff-format")

    assert "format" in formatting.argv
    assert "--check" in formatting.argv


def test_ruff_check_never_carries_a_fix_flag() -> None:
    linting = next(gate for gate in BATTERY.GATES if gate.name == "ruff-check")

    assert "--fix" not in linting.argv
    assert linting.argv[:4] == ("uv", "run", "ruff", "check")


def test_git_gate_only_inspects_the_diff() -> None:
    git_gate = next(gate for gate in BATTERY.GATES if gate.name == "git-diff-check")

    assert git_gate.argv == ("git", "diff", "--check")


def test_every_gate_covers_a_declared_suite_or_check() -> None:
    commands = {" ".join(gate.argv) for gate in BATTERY.GATES}

    assert "uv run pytest tests/unit" in commands
    assert "uv run pytest tests/ui" in commands
    assert "uv run pytest tests/integration" in commands
    assert "uv run mypy src tests" in commands


def test_listing_prints_every_command_without_running_anything() -> None:
    lines = BATTERY.render_listing(BATTERY.GATES)
    body = "\n".join(lines)

    for gate in BATTERY.GATES:
        assert " ".join(gate.argv) in body
    assert "read-only" in body


# --- ordering, stopping, and skipping ---------------------------------------


def test_gates_run_in_declared_order_when_all_pass() -> None:
    results, runner, _ = _run()

    assert [tuple(gate.argv) for gate in BATTERY.GATES] == runner.calls
    assert all(result.status is BATTERY.GateStatus.PASSED for result in results)


def test_first_failure_stops_the_battery_and_later_gates_are_not_run() -> None:
    results, runner, _ = _run(exit_codes={"mypy": 1})

    statuses = {result.gate.name: result.status for result in results}
    assert statuses["ruff-check"] is BATTERY.GateStatus.PASSED
    assert statuses["mypy"] is BATTERY.GateStatus.FAILED
    assert statuses["pytest-unit"] is BATTERY.GateStatus.NOT_RUN
    assert statuses["git-diff-check"] is BATTERY.GateStatus.NOT_RUN
    # The suites after the failure were never executed, not executed and ignored.
    assert not any("pytest" in " ".join(call) for call in runner.calls)


def test_keep_going_runs_every_gate_after_a_failure() -> None:
    results, runner, _ = _run(exit_codes={"mypy": 1}, keep_going=True)

    assert len(runner.calls) == len(BATTERY.GATES)
    statuses = [result.status for result in results]
    assert statuses.count(BATTERY.GateStatus.FAILED) == 1
    assert BATTERY.GateStatus.NOT_RUN not in statuses


def test_a_skipped_gate_is_still_a_row_and_is_never_executed() -> None:
    results, runner, _ = _run(skip=["pytest-integration"])

    statuses = {result.gate.name: result.status for result in results}
    assert statuses["pytest-integration"] is BATTERY.GateStatus.SKIPPED
    assert len(results) == len(BATTERY.GATES)
    assert not any("tests/integration" in " ".join(call) for call in runner.calls)


def test_an_unknown_skip_name_is_refused() -> None:
    with pytest.raises(BATTERY.GateBatteryError, match="unknown gate name"):
        BATTERY.select_gates(BATTERY.GATES, skip=["pytest-unti"])


def test_every_declared_gate_gets_a_row_whatever_happened() -> None:
    results, _, _ = _run(exit_codes={"ruff check": 1}, skip=["pytest-ui"])

    assert [result.gate.name for result in results] == [gate.name for gate in BATTERY.GATES]


def test_each_gate_reports_its_tail_and_status_as_it_finishes() -> None:
    _, _, reported = _run(tail_lines=2)
    body = "\n".join(reported)

    assert "→ ruff-check: uv run ruff check src tests scripts" in body
    # Tail is the last lines, not the whole output.
    assert "result for uv run mypy src tests" in body
    assert "line one" not in body
    assert "line two" in body


def test_tail_returns_nothing_when_no_lines_are_requested() -> None:
    assert BATTERY.tail("a\nb\nc", 0) == []
    assert BATTERY.tail("a\n\n  \nb", 5) == ["a", "b"]


# --- the table ---------------------------------------------------------------


def test_table_renders_every_gate_with_status_and_duration() -> None:
    results, _, _ = _run()
    lines = BATTERY.render_table(results)
    body = "\n".join(lines)

    assert "GATE" in lines[0] and "STATUS" in lines[0] and "DURATION" in lines[0]
    for gate in BATTERY.GATES:
        assert gate.name in body
    assert "ALL GATES PASSED" in body
    assert "2.0s" in body


def test_table_marks_unrun_gates_as_not_run_rather_than_passed() -> None:
    results, _, _ = _run(exit_codes={"pytest-unit": 1, "tests/unit": 1})
    body = "\n".join(BATTERY.render_table(results))

    assert "NOT RUN" in body
    assert "BATTERY INCOMPLETE" in body
    assert "not run: pytest-ui, pytest-integration, git-diff-check" in body


def test_table_shows_a_skipped_gate_without_a_duration() -> None:
    results, _, _ = _run(skip=["pytest-integration"])
    row = next(
        line for line in BATTERY.render_table(results) if line.startswith("pytest-integration")
    )

    assert "SKIP" in row
    assert row.rstrip().endswith("uv run pytest tests/integration")


def test_summary_line_is_incomplete_when_a_gate_was_skipped() -> None:
    results, _, _ = _run(skip=["pytest-ui"])

    summary = BATTERY.summarise(results)

    # Everything that ran passed, but the battery did not cover the suite.
    assert "BATTERY INCOMPLETE" in summary
    assert "1 skip" in summary


def test_durations_are_rendered_in_minutes_past_a_minute() -> None:
    assert BATTERY._duration(0.0) == "0.0s"
    assert BATTERY._duration(59.4) == "59.4s"
    assert BATTERY._duration(60.0) == "1m00s"
    assert BATTERY._duration(158.5) == "2m38s"


# --- exit codes --------------------------------------------------------------


def test_main_exits_zero_only_when_every_gate_passed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(BATTERY, "run_command", FakeRunner())

    assert BATTERY.main([]) == 0
    assert "ALL GATES PASSED" in capsys.readouterr().out


def test_main_exits_non_zero_on_a_failing_gate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(BATTERY, "run_command", FakeRunner({"tests/ui": 1}))

    assert BATTERY.main(["--keep-going"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_exits_non_zero_when_a_gate_was_skipped(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A partial battery must not be reportable as a green one."""

    monkeypatch.setattr(BATTERY, "run_command", FakeRunner())

    assert BATTERY.main(["--skip", "pytest-integration"]) == 1
    assert "SKIP" in capsys.readouterr().out


def test_main_refuses_an_unknown_skip_name(capsys: pytest.CaptureFixture[str]) -> None:
    assert BATTERY.main(["--skip", "nope"]) == 2
    assert "unknown gate name" in capsys.readouterr().err


def test_main_list_prints_the_commands_and_runs_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(BATTERY, "run_command", runner)

    assert BATTERY.main(["--list"]) == 0
    assert runner.calls == []
    assert "uv run pytest tests/unit" in capsys.readouterr().out
