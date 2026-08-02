"""Integrity checks for the Phase-186 committed-input and handoff audit."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
RECORD = (
    ROOT / "docs" / "integration" / "evidence" / "v07_local_input_and_handoff_audit_20260802.json"
)
MANUSCRIPT = ROOT / "docs" / "dissertation_manuscript_20260801.md"
BIBLIOGRAPHY = ROOT / "docs" / "dissertation_references_20260802.bib"
DECISION_PACK = ROOT / "docs" / "v07_external_decision_pack.md"
PYPROJECT = ROOT / "pyproject.toml"
CITATION = ROOT / "CITATION.cff"


def _record() -> dict[str, Any]:
    payload: object = json.loads(RECORD.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _citation_numbers(text: str) -> set[int]:
    numbers: set[int] = set()
    for match in re.finditer(r"\[([0-9]+)\]\s*[–-]\s*\[([0-9]+)\]", text):
        numbers.update(range(int(match.group(1)), int(match.group(2)) + 1))
    for match in re.finditer(r"\[([0-9][0-9, \-–]*)\]", text):
        for raw_part in match.group(1).split(","):
            part = raw_part.strip()
            separator = "–" if "–" in part else "-" if "-" in part else None
            if separator is None:
                numbers.add(int(part))
                continue
            start, end = (int(value.strip()) for value in part.split(separator, maxsplit=1))
            numbers.update(range(start, end + 1))
    return numbers


def test_all_bound_artifacts_match_exact_bytes_and_digests() -> None:
    artifacts = _record()["bound_artifacts"]
    assert len(artifacts) == 9
    assert len({artifact["path"] for artifact in artifacts}) == len(artifacts)
    for artifact in artifacts:
        path = ROOT / artifact["path"]
        content = path.read_bytes()
        assert len(content) == artifact["bytes"]
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]


def test_all_eight_programme_slices_are_distinct_and_ordered() -> None:
    slices = _record()["programme_slices"]
    assert [item["phase"] for item in slices] == list(range(173, 181))
    assert len({item["commit"] for item in slices}) == 8
    assert len({item["slice"] for item in slices}) == 8


def test_manuscript_and_bibliography_integrity_is_unchanged() -> None:
    text = MANUSCRIPT.read_text(encoding="utf-8")
    body, references = text.split("## References", maxsplit=1)
    numbered = [
        int(match.group(1))
        for match in re.finditer(r"^\[([0-9]+)\] ", references, flags=re.MULTILINE)
    ]
    counted = (
        "## Abstract"
        + text.split("## Abstract", maxsplit=1)[1].split("## References", maxsplit=1)[0]
    )
    entries = re.findall(r"^@\w+\{tt[0-9]{3},", BIBLIOGRAPHY.read_text(), re.MULTILINE)

    assert len(counted.split()) == 8396
    assert numbered == list(range(1, 101))
    assert _citation_numbers(body) == set(range(1, 101))
    assert len(entries) == 100


def test_manuscript_contains_no_exact_duplicate_long_prose() -> None:
    text = MANUSCRIPT.read_text(encoding="utf-8")
    paragraphs = [part.strip() for part in text.split("\n\n") if len(part.strip()) >= 120]
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 60]
    assert [value for value, count in Counter(paragraphs).items() if count > 1] == []
    assert [value for value, count in Counter(lines).items() if count > 1] == []
    assert text.count("presenting a rounded p-value alone.") == 1
    assert text.count("synthetic vehicle paths.") == 1


def test_release_and_external_authority_remain_fail_closed() -> None:
    record = _record()
    boundary = record["release_boundary"]
    external = record["external_state"]
    assert boundary == {
        "package_version": "0.6.0",
        "citation_version": "0.6.0",
        "final_v070_tag_present": False,
        "version_change_authorized": False,
        "tag_or_release_created_by_phase": False,
    }
    assert external["network_decision_missing"] is False
    assert external["producer_attestation_policy_missing"] is False
    for field, value in external.items():
        if field not in {"network_decision_missing", "producer_attestation_policy_missing"}:
            assert value is False
    assert record["capability_accepted"] is False
    assert record["scientific_evidence_created"] is False
    assert record["supervisor_or_ethics_approval_created"] is False
    assert re.search(r'^version = "0\.6\.0"$', PYPROJECT.read_text(), re.MULTILINE)
    assert re.search(r"^version: 0\.6\.0$", CITATION.read_text(), re.MULTILINE)


def test_audit_is_path_free_and_does_not_claim_private_inspection() -> None:
    text = RECORD.read_text(encoding="utf-8")
    record = _record()
    assert record["scope"] == "git_tracked_repository_inputs_only"
    assert record["ignored_or_private_workspace_inspected"] is False
    assert "/".join(("", "Users", "")) not in text
    assert "credential" not in text.lower()


def test_decision_pack_no_longer_calls_resolved_inputs_missing() -> None:
    text = DECISION_PACK.read_text(encoding="utf-8")
    assert "Five recorded decisions block" not in text
    assert "Resolved input: Manchester SUMO network" in text
    assert "Resolved policy: v0.6 producer attestation" in text
    assert "Decision needed (open question 15)" not in text
    assert "owner-policy v1.1 has frozen" in text
