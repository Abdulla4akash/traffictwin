"""Tiny file fixtures only: no research imports, array audits or campaign commands."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify_research_archives.py"
ARCHIVE = "docs/dissertation/example_2026-09-08"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_research_archives", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(root: Path, archive: str = ARCHIVE) -> tuple[Path, Path]:
    source = root / archive / "frozen.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"x=1\n")
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "baseline_commit": "a" * 40,
                "roots": [archive],
                "files": {
                    source.relative_to(root).as_posix(): {
                        "bytes": 4,
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                },
            }
        )
    )
    (root / "pyproject.toml").write_text(f'[tool.ruff]\nextend-exclude = ["{archive}"]\n')
    return source, manifest


def test_original_bytes_pass_without_executing_source(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path)
    result = _module().verify(tmp_path, manifest)
    assert result["status"] == "passed"
    assert result["checked_files"] == 1
    assert result["checked_bytes"] == 4
    assert source.read_bytes() == b"x=1\n"
    assert not (source.parent / "__pycache__").exists()


def test_exact_dated_research_package_passes_without_executing_source(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path, "docs/research/three_traces_2026-09-16")
    result = _module().verify(tmp_path, manifest)
    assert result["status"] == "passed"
    assert result["archive_roots"] == 1
    assert result["checked_files"] == 1
    assert source.read_bytes() == b"x=1\n"
    assert not (source.parent / "__pycache__").exists()


@pytest.mark.parametrize("archive", ["docs/research", "docs/research/maintained_tools"])
def test_research_exclusion_cannot_expand_beyond_dated_package(
    tmp_path: Path, archive: str
) -> None:
    _, manifest = _fixture(tmp_path, archive)
    with pytest.raises(ValueError, match="dated package"):
        _module().verify(tmp_path, manifest)


@pytest.mark.parametrize("changed", [b"x=2\n", b"x = 1\n"])
def test_semantic_and_format_only_changes_fail(tmp_path: Path, changed: bytes) -> None:
    source, manifest = _fixture(tmp_path)
    source.write_bytes(changed)
    result = _module().verify(tmp_path, manifest)
    assert result["status"] == "failed"
    assert any("Changed file:" in item for item in result["failures"])


def test_missing_file_is_not_a_pass(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path)
    source.unlink()
    result = _module().verify(tmp_path, manifest)
    assert result["status"] == "failed"
    assert any("Missing file:" in item for item in result["failures"])


def test_new_code_cannot_hide_inside_excluded_archive(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path)
    (source.parent / "new_maintained_tool.py").write_text("x = 1\n")
    result = _module().verify(tmp_path, manifest)
    assert result["status"] == "failed"
    assert any("Unexpected file:" in item for item in result["failures"])


def test_symlink_is_rejected_even_if_target_bytes_match(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path)
    copy = tmp_path / "copy.py"
    copy.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(copy)
    result = _module().verify(tmp_path, manifest)
    assert result["status"] == "failed"
    assert any("Symlink inside archive:" in item for item in result["failures"])


def test_configuration_cannot_silently_exclude_more_code(tmp_path: Path) -> None:
    _, manifest = _fixture(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = ["docs"]\n')
    result = _module().verify(tmp_path, manifest)
    assert result["status"] == "failed"
    assert "Ruff exclusions differ" in result["failures"][0]


def test_manifest_cannot_expand_to_entire_docs_tree(tmp_path: Path) -> None:
    _, manifest = _fixture(tmp_path)
    data = json.loads(manifest.read_text())
    data["roots"] = ["docs"]
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="exact dated packages"):
        _module().verify(tmp_path, manifest)


def test_manifest_cannot_escape_checkout(tmp_path: Path) -> None:
    _, manifest = _fixture(tmp_path)
    data = json.loads(manifest.read_text())
    record = next(iter(data["files"].values()))
    data["files"] = {"../outside.py": record}
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Non-canonical relative archive path"):
        _module().verify(tmp_path, manifest)


def test_repository_exclusions_leave_editorial_and_maintained_code_checked() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    exclusions = config["tool"]["ruff"]["extend-exclude"]
    assert len(exclusions) == 12
    assert "docs/dissertation/followups_2026-09-15" in exclusions
    assert "docs/research/three_traces_2026-09-16" in exclusions
    assert "docs/evaluation/e3a_csf3_2026-09-11" in exclusions
    assert "docs/dissertation/examiner_revision_2026-09-11" in exclusions
    for maintained in (
        Path("src"),
        Path("tests"),
        Path("scripts"),
        Path("docs/dissertation/editorial_final_2026-09-09"),
        Path("docs/research/maintained_tools"),
    ):
        assert not any(maintained.is_relative_to(Path(excluded)) for excluded in exclusions)
