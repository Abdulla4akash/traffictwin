"""Gate-F reconciliation: versions, references, and release-line invariants.

Gate F asks for versions, schemas, generated references, CLI, documentation and
CI to be reconciled. Each of these can drift silently — a bumped package version
with a stale citation, or a CLI command that exists but was never regenerated
into the reference — and drift is only visible if something checks.

These are automated candidate checks. They do not accept Gate F.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

import traffictwin

_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"
_CITATION = _ROOT / "CITATION.cff"
_CHANGELOG = _ROOT / "CHANGELOG.md"
_CLI_HELP = _ROOT / "docs" / "reference" / "generated" / "cli_help.json"

#: v0.7 is a development line. A final release tag is the owner's to create, and
#: an agent must never bump the package into it.
_FINAL_V07_VERSION = "0.7.0"


def _pyproject_version() -> str:
    return str(tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"])


def _citation_version() -> str:
    match = re.search(r"^version:\s*(\S+)\s*$", _CITATION.read_text(encoding="utf-8"), re.M)
    assert match is not None, "CITATION.cff must declare a version"
    return match.group(1)


class TestVersionsAgree:
    def test_the_package_and_pyproject_agree(self) -> None:
        assert traffictwin.__version__ == _pyproject_version()

    def test_the_citation_matches_the_package(self) -> None:
        # A stale citation misattributes which version was cited.
        assert _citation_version() == _pyproject_version()

    def test_the_changelog_names_the_development_line(self) -> None:
        text = _CHANGELOG.read_text(encoding="utf-8")
        assert "v0.7.0" in text, "the changelog must record the in-development line"


class TestTheReleaseLineIsNotPrematurelyAdvanced:
    def test_the_package_version_is_not_the_final_v07(self) -> None:
        # v0.7 still has planned capabilities and incomplete gates. Bumping the
        # package to the final version would assert a release that has not
        # happened, whatever any tag says.
        assert _pyproject_version() != _FINAL_V07_VERSION, (
            "the package must not carry the final v0.7.0 version while gates are incomplete"
        )

    def test_no_final_v07_tag_exists(self) -> None:
        git = shutil.which("git")
        if git is None:  # pragma: no cover - git is present in every dev environment
            pytest.skip("git is unavailable")
        result = subprocess.run(  # noqa: S603 - resolved argv, no shell, no caller input
            [git, "tag", "-l", _FINAL_V07_VERSION, f"v{_FINAL_V07_VERSION}"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout.strip() == "", "a final v0.7.0 tag must not exist yet"


class TestGeneratedReferencesAreCurrent:
    def test_the_cli_reference_exists_and_parses(self) -> None:
        payload = json.loads(_CLI_HELP.read_text(encoding="utf-8"))
        assert payload["commands"], "the generated CLI reference must not be empty"

    def test_every_documented_command_exited_cleanly(self) -> None:
        # A non-zero exit captured into the reference means the documented help
        # is an error message.
        payload = json.loads(_CLI_HELP.read_text(encoding="utf-8"))
        broken = [
            " ".join(entry["args"]) for entry in payload["commands"] if entry["exit_code"] != 0
        ]
        assert not broken, f"these documented commands do not exit cleanly: {broken}"

    def test_the_manchester_surface_is_documented(self) -> None:
        payload = json.loads(_CLI_HELP.read_text(encoding="utf-8"))
        manchester = [
            entry for entry in payload["commands"] if "manchester" in " ".join(entry["args"])
        ]
        assert len(manchester) >= 30, (
            "the Manchester command surface is under-documented; regenerate the reference"
        )


class TestNoReleaseArtifactLeaksAPrivatePath:
    #: A real leak is a root plus a *named* segment. Matching the bare prefix
    #: flags prose: the changelog legitimately contains the phrase
    #: "POSIX/Windows/home/file-URI path redaction", which is a description of
    #: the redaction feature, not a path.
    _PRIVATE_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/|/private/tmp/[A-Za-z0-9._-]+")

    @pytest.mark.parametrize("path", [_PYPROJECT, _CITATION, _CHANGELOG])
    def test_a_release_file_carries_no_private_absolute_path(self, path: Path) -> None:
        found = self._PRIVATE_PATH.findall(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name} leaks a private path: {found[:3]}"

    def test_the_leak_check_would_catch_a_real_path(self) -> None:
        # A check that cannot fail proves nothing.
        assert self._PRIVATE_PATH.search("/Users/someone/secret/net.xml")
        assert self._PRIVATE_PATH.search("/private/tmp/claude-501/workspace")

    def test_the_leak_check_does_not_flag_prose(self) -> None:
        assert not self._PRIVATE_PATH.search("POSIX/Windows/home/file-URI path redaction")
