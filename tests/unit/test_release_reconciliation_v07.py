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
import tomllib
from pathlib import Path

import pytest

import traffictwin
from traffictwin.release.metadata import current_release_metadata

_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"
_CITATION = _ROOT / "CITATION.cff"
_CHANGELOG = _ROOT / "CHANGELOG.md"
_CLI_HELP = _ROOT / "docs" / "reference" / "generated" / "cli_help.json"

#: Main now carries the owner-authorised v0.7 package identity. Tag publication
#: remains a separate repository-owner action.
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

    def test_the_changelog_names_the_release_line(self) -> None:
        text = _CHANGELOG.read_text(encoding="utf-8")
        assert "## v0.7.0 - 2026-08-03" in text, "the changelog must record the release line"


class TestTheReleaseLineIsReconciled:
    def test_the_package_carries_the_v07_identity(self) -> None:
        assert _pyproject_version() == _FINAL_V07_VERSION

    def test_release_identity_does_not_claim_production_readiness(self) -> None:
        metadata = current_release_metadata()
        assert metadata.version == _FINAL_V07_VERSION
        assert metadata.production_status == "Research prototype; not production-ready."


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
