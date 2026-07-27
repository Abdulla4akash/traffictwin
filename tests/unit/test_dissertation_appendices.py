"""Structural coverage for the dissertation appendix generators.

The generator is run into ``tmp_path`` and its *structure* is asserted — headings,
table shape, sourced counts, determinism. Content bytes are deliberately not
pinned: the appendices track the repository's real dependencies and decision
register, and a test that froze those values would fail every time the project
legitimately changed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate_dissertation_appendices.py"


def _module() -> ModuleType:
    """Load the generator by path; ``scripts/`` is not an importable package."""

    spec = importlib.util.spec_from_file_location("generate_dissertation_appendices", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    return _module()


@pytest.fixture
def generated(generator: ModuleType, tmp_path: Path) -> dict[str, str]:
    written = generator.generate_appendices(REPO_ROOT, tmp_path)
    return {path.name: path.read_text(encoding="utf-8") for path in written}


def test_both_appendices_are_written(generator: ModuleType, tmp_path: Path) -> None:
    written = generator.generate_appendices(REPO_ROOT, tmp_path)

    assert [path.name for path in written] == [
        generator.CAPABILITY_APPENDIX,
        generator.VERSION_APPENDIX,
    ]
    assert all(path.is_file() for path in written)


def test_the_output_directory_is_created_when_absent(generator: ModuleType, tmp_path: Path) -> None:
    target = tmp_path / "nested" / "appendices"

    written = generator.generate_appendices(REPO_ROOT, target)

    assert target.is_dir()
    assert len(written) == 2


def test_regeneration_is_byte_identical(generator: ModuleType, tmp_path: Path) -> None:
    first = {
        path.name: path.read_bytes()
        for path in generator.generate_appendices(REPO_ROOT, tmp_path / "one")
    }
    second = {
        path.name: path.read_bytes()
        for path in generator.generate_appendices(REPO_ROOT, tmp_path / "two")
    }

    # A timestamp or an unsorted collection here would show up as commit churn.
    assert first == second


def test_capability_appendix_has_its_declared_structure(generated: dict[str, str]) -> None:
    body = generated["appendix_a_capability_catalogue.md"]

    assert body.startswith("# Appendix A — Capability catalogue and decision register")
    assert "## A.1 Adapter capability catalogue" in body
    assert "## A.2 Architecture decision register" in body
    assert "| Capability id | Declared support |" in body
    assert "| ADR | Title | Status |" in body
    assert "Do not edit by hand" in body


def test_capability_rows_cover_every_manifest_field(generated: dict[str, str]) -> None:
    from traffictwin.config.capabilities import default_export_import_manifest

    body = generated["appendix_a_capability_catalogue.md"]
    fields = type(default_export_import_manifest().supports).model_fields

    for name in fields:
        assert f"| `{name}` |" in body
    assert f"Total capabilities: {len(fields)}." in body


def test_the_three_valued_state_is_preserved_not_collapsed(generated: dict[str, str]) -> None:
    body = generated["appendix_a_capability_catalogue.md"]

    # The manifest declares all three states; none may be flattened away.
    assert "| `true` |" in body
    assert "| `false` |" in body
    assert "| `unknown` |" in body
    assert "never collapsed into `false`" in body


def test_the_unavailable_join_is_stated_rather_than_invented(generated: dict[str, str]) -> None:
    body = generated["appendix_a_capability_catalogue.md"]

    assert "### A.1.1 Fields this table deliberately omits" in body
    assert "not recorded in machine-readable form" in body
    assert "no capability-to-ADR mapping exists" in body
    # No fabricated family column may appear in the capability table.
    assert "| Capability id | Family |" not in body


def test_adr_register_is_parsed_sorted_and_counted(generator: ModuleType) -> None:
    entries = generator.read_adr_register(REPO_ROOT)

    assert len(entries) > 50
    assert [entry.adr_id for entry in entries] == sorted(entry.adr_id for entry in entries)
    assert all(entry.adr_id.startswith("ADR-") for entry in entries)
    assert all(entry.title and entry.status for entry in entries)


def test_a_missing_adr_register_is_an_explicit_error(generator: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(generator.AppendixGenerationError, match="ADR register not found"):
        generator.read_adr_register(tmp_path)


def test_a_register_without_rows_is_an_explicit_error(
    generator: ModuleType, tmp_path: Path
) -> None:
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "index.md").write_text("# Architecture Decision Records\n", encoding="utf-8")

    with pytest.raises(generator.AppendixGenerationError, match="no ADR rows parsed"):
        generator.read_adr_register(tmp_path)


def test_version_appendix_has_its_declared_structure(generated: dict[str, str]) -> None:
    body = generated["appendix_b_software_versions.md"]

    assert body.startswith("# Appendix B — Software versions and parameters")
    assert "## B.1 Project" in body
    assert "## B.2 Declared dependency constraints" in body
    assert "## B.3 Resolved environment versions" in body
    assert "| Group | Requirement |" in body
    assert "| Package | Resolved version |" in body


def test_version_appendix_reports_the_projects_own_metadata(
    generator: ModuleType, generated: dict[str, str]
) -> None:
    project = generator.read_pyproject(REPO_ROOT)["project"]
    body = generated["appendix_b_software_versions.md"]

    assert f"| Name | `{project['name']}` |" in body
    assert f"| Version | `{project['version']}` |" in body
    assert f"| Requires Python | `{project['requires-python']}` |" in body


def test_pinned_tool_versions_reach_the_appendix(
    generator: ModuleType, generated: dict[str, str]
) -> None:
    body = generated["appendix_b_software_versions.md"]
    optional = generator.read_pyproject(REPO_ROOT)["project"]["optional-dependencies"]
    pinned = [
        requirement for group in optional.values() for requirement in group if "==" in requirement
    ]

    assert pinned, "the project is expected to pin at least one tool version"
    for requirement in pinned:
        assert f"`{requirement}` |" in body


def test_resolved_packages_are_sorted_and_counted(
    generator: ModuleType, generated: dict[str, str]
) -> None:
    packages = generator._resolved_packages(generator.read_lockfile(REPO_ROOT))
    body = generated["appendix_b_software_versions.md"]

    assert packages == sorted(packages)
    assert len(packages) > 20
    assert f"Total locked packages: {len(packages)}." in body


def test_a_missing_lockfile_is_an_explicit_error(generator: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(generator.AppendixGenerationError, match="required source not found"):
        generator.read_lockfile(tmp_path)


def test_unreadable_toml_is_an_explicit_error(generator: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("this is [not valid TOML", encoding="utf-8")

    with pytest.raises(generator.AppendixGenerationError, match="not readable TOML"):
        generator.read_lockfile(tmp_path)


def test_committed_appendices_match_a_fresh_generation(
    generator: ModuleType, tmp_path: Path
) -> None:
    """The committed files must be what the generator currently produces."""

    fresh = generator.generate_appendices(REPO_ROOT, tmp_path)
    committed_dir = REPO_ROOT / "docs" / "dissertation_appendices"

    for path in fresh:
        committed = committed_dir / path.name
        assert committed.is_file(), f"{committed} is not committed"
        assert committed.read_text(encoding="utf-8") == path.read_text(encoding="utf-8"), (
            f"{committed.name} is stale; re-run scripts/generate_dissertation_appendices.py"
        )
