"""Structural coverage for the quality-gate snapshot generator.

Every probe here is faked. The tests never shell out, never collect a real
suite, and never run a real gate — they assert the properties that make the
generated appendix trustworthy: no test is ever executed, collected counts are
labelled as collected, a missing type-check count is an honest gap rather than a
guess, and every rendered row carries the command that reproduces it.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate_quality_snapshot.py"
GENERATED_APPENDIX = REPO_ROOT / "docs" / "dissertation_appendices" / "quality_snapshot.md"

GENERATED_AT = "2026-07-27T18:00:00+00:00"


def _module() -> ModuleType:
    """Load the generator by path; ``scripts/`` is not an importable package."""

    spec = importlib.util.spec_from_file_location("generate_quality_snapshot", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    """Answers every probe from a table, and records what was asked."""

    def __init__(self, module: ModuleType, *, overrides: dict[str, str] | None = None) -> None:
        self.module = module
        self.calls: list[tuple[str, ...]] = []
        self.overrides = overrides or {}

    def __call__(self, argv: Sequence[str]) -> object:
        command = tuple(argv)
        self.calls.append(command)
        joined = " ".join(command)
        if joined in self.overrides:
            return self.module.CommandResult(
                argv=command, exit_code=0, stdout=self.overrides[joined], stderr=""
            )
        return self.module.CommandResult(
            argv=command, exit_code=0, stdout=self._default(command), stderr=""
        )

    def _default(self, command: tuple[str, ...]) -> str:
        if "--collect-only" in command:
            counts = {
                "tests/unit": 2_744,
                "tests/ui": 476,
                "tests/integration": 214,
                "tests/golden": 63,
            }
            path = next(part for part in command if part.startswith("tests/"))
            return f"a_test.py::test_one\n\n{counts[path]} tests collected in 2.11s\n"
        if command[:4] == ("uv", "run", "ruff", "check"):
            return "All checks passed!\n"
        if command[:4] == ("uv", "run", "ruff", "format"):
            return "822 files already formatted\n"
        if command[:2] == ("git", "rev-parse"):
            if "--abbrev-ref" in command:
                return "claude/complete-v0.7\n"
            return "a" * 40 + "\n"
        if command[:2] == ("git", "status"):
            return ""
        return "tool 1.2.3\n"


# --- the standing promise: nothing is executed ------------------------------


def test_every_pytest_invocation_is_collection_only() -> None:
    module = _module()
    runner = FakeRunner(module)

    module.collect_quality_snapshot(mypy_file_count=796, runner=runner)

    pytest_calls = [call for call in runner.calls if "pytest" in call and "--version" not in call]
    assert pytest_calls
    for call in pytest_calls:
        assert "--collect-only" in call
        assert "-q" in call


def test_the_suite_command_builder_is_collection_only() -> None:
    module = _module()

    assert module.suite_collect_argv("tests/unit") == (
        "uv",
        "run",
        "pytest",
        "tests/unit",
        "--collect-only",
        "-q",
    )


def test_no_probe_touches_campaign_data_or_a_registry() -> None:
    module = _module()
    runner = FakeRunner(module)

    module.collect_quality_snapshot(mypy_file_count=796, runner=runner)

    for call in runner.calls:
        joined = " ".join(call)
        assert "vec-fresh" not in joined
        assert "registry" not in joined
        assert "capacity" not in joined


# --- the numbers ------------------------------------------------------------


def test_every_suite_is_inventoried_and_totalled() -> None:
    module = _module()

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module))

    values = {row.label: row.value for row in snapshot.suites}
    assert values["Unit tests"] == "2,744 collected"
    assert values["UI tests"] == "476 collected"
    assert values["Integration tests"] == "214 collected"
    assert values["Golden tests"] == "63 collected"
    assert values["All suites"] == "3,497 collected"


def test_collected_counts_are_labelled_as_collected_not_passed() -> None:
    module = _module()

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module))
    rendered = module.render_quality_snapshot(snapshot, generated_at=GENERATED_AT)

    assert "Collected, not passed" in rendered
    assert "Collected is not passed" in rendered
    for row in snapshot.suites:
        assert "passed" not in row.value


def test_an_unparseable_suite_inventory_is_a_gap_not_a_guess() -> None:
    module = _module()
    runner = FakeRunner(
        module,
        overrides={"uv run pytest tests/golden --collect-only -q": "no summary line here\n"},
    )

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=runner)

    values = {row.label: row.value for row in snapshot.suites}
    assert values["Golden tests"] == module.NOT_COLLECTED
    assert values["All suites"].startswith("at least ")
    assert any("golden suite inventory" in warning for warning in snapshot.warnings)


def test_the_type_check_count_is_supplied_not_measured() -> None:
    module = _module()
    runner = FakeRunner(module)

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=runner)

    row = next(item for item in snapshot.gates if item.label == "Strict type check")
    assert row.value == "796 source files checked"
    assert row.command == "uv run mypy src tests"
    assert "supplied by the operator" in row.note.lower()
    # The generator must never spend the compute itself.
    assert all("mypy" not in call or "--version" in call for call in runner.calls)


def test_a_missing_type_check_count_is_reported_as_a_gap() -> None:
    module = _module()

    snapshot = module.collect_quality_snapshot(mypy_file_count=None, runner=FakeRunner(module))

    row = next(item for item in snapshot.gates if item.label == "Strict type check")
    assert row.value == module.NOT_COLLECTED
    assert any("--mypy-file-count" in warning for warning in snapshot.warnings)
    rendered = module.render_quality_snapshot(snapshot, generated_at=GENERATED_AT)
    assert "Gaps in this snapshot" in rendered


def test_gate_status_strings_are_recorded_as_the_tool_wrote_them() -> None:
    module = _module()

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module))

    values = {row.label: row.value for row in snapshot.gates}
    assert "All checks passed!" in values["Lint (ruff check)"]
    assert "822 files already formatted" in values["Format (ruff format --check)"]


def test_a_failing_gate_reports_what_the_tool_said() -> None:
    module = _module()
    runner = FakeRunner(module)
    original = runner.__call__

    def failing(argv: Sequence[str]) -> object:
        result = original(argv)
        if tuple(argv)[:4] == ("uv", "run", "ruff", "check"):
            return module.CommandResult(
                argv=tuple(argv), exit_code=1, stdout="Found 3 errors.\n", stderr=""
            )
        return result

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=failing)

    values = {row.label: row.value for row in snapshot.gates}
    assert values["Lint (ruff check)"] == "Found 3 errors."


def test_a_dirty_working_tree_is_reported_as_dirty() -> None:
    module = _module()
    runner = FakeRunner(module, overrides={"git status --porcelain": " M AGENTS.md\n?? new.py\n"})

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=runner)

    tree = next(item for item in snapshot.repository if item.label == "Working tree")
    assert tree.value.startswith("dirty — 2 uncommitted")
    assert any("uncommitted path" in warning for warning in snapshot.warnings)


def test_the_appendix_being_written_does_not_count_as_a_dirty_tree() -> None:
    module = _module()
    runner = FakeRunner(
        module,
        overrides={
            "git status --porcelain": "?? docs/dissertation_appendices/quality_snapshot.md\n"
        },
    )

    snapshot = module.collect_quality_snapshot(
        mypy_file_count=796,
        runner=runner,
        ignore_paths=("docs/dissertation_appendices/quality_snapshot.md",),
    )

    tree = next(item for item in snapshot.repository if item.label == "Working tree")
    assert tree.value == "clean"
    assert not any("uncommitted path" in warning for warning in snapshot.warnings)


def test_an_unrelated_dirty_path_is_still_reported_alongside_the_output() -> None:
    module = _module()
    runner = FakeRunner(
        module,
        overrides={
            "git status --porcelain": (
                "?? docs/dissertation_appendices/quality_snapshot.md\n M src/traffictwin/cli.py\n"
            )
        },
    )

    snapshot = module.collect_quality_snapshot(
        mypy_file_count=796,
        runner=runner,
        ignore_paths=("docs/dissertation_appendices/quality_snapshot.md",),
    )

    tree = next(item for item in snapshot.repository if item.label == "Working tree")
    assert tree.value.startswith("dirty — 1 uncommitted")


def test_the_commit_and_branch_are_recorded() -> None:
    module = _module()

    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module))

    values = {row.label: row.value for row in snapshot.repository}
    assert values["Commit"] == f"`{'a' * 40}`"
    assert values["Branch"] == "claude/complete-v0.7"


# --- the rendered appendix --------------------------------------------------


def test_every_rendered_row_carries_its_reproduction_command() -> None:
    module = _module()
    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module))

    rendered = module.render_quality_snapshot(snapshot, generated_at=GENERATED_AT)

    body = [line for line in rendered.splitlines() if line.startswith("| ")]
    data_rows = [line for line in body if not line.startswith("| Measure") and "---" not in line]
    assert data_rows
    for line in data_rows:
        assert line.rstrip().endswith("` |"), line


def test_a_row_without_a_command_is_refused() -> None:
    module = _module()
    snapshot = module.QualitySnapshot(
        suites=(module.Measurement("Unit tests", "1 collected", ""),),
        gates=(),
        tooling=(),
        repository=(),
    )

    with pytest.raises(module.QualitySnapshotError, match="carries no reproduction command"):
        module.render_quality_snapshot(snapshot, generated_at=GENERATED_AT)


def test_the_generation_timestamp_is_rendered() -> None:
    module = _module()
    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module))

    rendered = module.render_quality_snapshot(snapshot, generated_at=GENERATED_AT)

    assert GENERATED_AT in rendered
    assert rendered.startswith("# Appendix — Quality-gate snapshot")


def test_the_appendix_states_these_are_not_scientific_results() -> None:
    module = _module()
    snapshot = module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module))

    rendered = module.render_quality_snapshot(snapshot, generated_at=GENERATED_AT)

    assert "Nothing here is a scientific result" in rendered


def test_rendering_is_deterministic_for_a_fixed_timestamp() -> None:
    module = _module()

    first = module.render_quality_snapshot(
        module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module)),
        generated_at=GENERATED_AT,
    )
    second = module.render_quality_snapshot(
        module.collect_quality_snapshot(mypy_file_count=796, runner=FakeRunner(module)),
        generated_at=GENERATED_AT,
    )

    assert first == second


def test_the_command_writes_the_appendix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    runner = FakeRunner(module)
    monkeypatch.setattr(module, "run_command", runner)
    output = tmp_path / "quality_snapshot.md"

    code = module.main(
        [
            "--output",
            str(output),
            "--mypy-file-count",
            "796",
            "--generated-at",
            GENERATED_AT,
        ]
    )

    assert code == 0
    text = output.read_text(encoding="utf-8")
    assert "2,744 collected" in text
    assert "796 source files checked" in text


def test_the_committed_appendix_exists_and_reports_its_commands() -> None:
    assert GENERATED_APPENDIX.is_file()

    text = GENERATED_APPENDIX.read_text(encoding="utf-8")

    assert text.startswith("# Appendix — Quality-gate snapshot")
    assert "uv run pytest tests/unit --collect-only -q" in text
    assert "uv run mypy src tests" in text
    assert "Collected is not passed" in text
