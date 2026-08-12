"""Unit tests for v08 stakeholder packet validator."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/validate_v08_stakeholder_packet.py"
PACKET = ROOT / "docs/closure/v08_alignment/stakeholder_confirmation_packet.md"
AMENDMENT = ROOT / "docs/closure/v08_alignment/proposed_requirements_amendment_v2.md"
REGISTER = ROOT / "docs/closure/v08_alignment/stakeholder_decision_register.json"


def run_validator() -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return result


def test_validator_passes_on_commit():
    result = run_validator()
    assert result.returncode == 0, f"validator failed: {result.stderr}\n{result.stdout}"
    assert "PASS" in result.stdout


def test_all_required_files_exist():
    for p in [
        PACKET,
        AMENDMENT,
        ROOT / "docs/closure/v08_alignment/email_to_sandra.md",
        ROOT / "docs/closure/v08_alignment/email_to_randy.md",
        REGISTER,
    ]:
        assert p.exists(), f"missing {p}"


def test_packet_contains_draft_not_effective():
    text = PACKET.read_text(encoding="utf-8")
    assert "DRAFT / NOT EFFECTIVE" in text


def test_amendment_contains_draft_not_effective():
    text = AMENDMENT.read_text(encoding="utf-8")
    assert "DRAFT / NOT EFFECTIVE" in text


def test_packet_contains_all_frozen_seven():
    text = PACKET.read_text(encoding="utf-8")
    for i in range(1, 8):
        assert f"UD-00{i}" in text, f"missing UD-00{i}"


def test_packet_contains_all_operational_eight():
    text = PACKET.read_text(encoding="utf-8")
    for i in range(1, 9):
        assert f"OQ-00{i}" in text, f"missing OQ-00{i}"


def test_packet_contains_sandra_five_and_randy_six():
    text = PACKET.read_text(encoding="utf-8")
    for sid in [f"SQ-SANDRA-0{i}" for i in range(1, 6)]:
        assert sid in text, f"missing {sid}"
    for rid in [f"RQ-RANDY-0{i}" for i in range(1, 7)]:
        assert rid in text, f"missing {rid}"


def test_register_machine_readable():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["base_sha"] == "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"
    assert data["baseline"]["amendment_v2_standing"] == "DRAFT / NOT EFFECTIVE"
    frozen = data["unresolved_decisions_frozen_seven"]
    assert len(frozen) == 7
    for entry in frozen:
        assert "source_class" in entry
        assert "decision_owner" in entry
        assert "current_standing" in entry
        assert "mapped_asks" in entry
    operational = data["operational_questions_eight"]
    assert len(operational) == 8
    for entry in operational:
        assert "source_class" in entry
        assert "decision_owner" in entry
        assert "current_standing" in entry
    assert len(data["sandra_asks_five"]) == 5
    assert len(data["randy_asks_six"]) == 6


def test_no_effective_claim_in_packet():
    text = PACKET.read_text(encoding="utf-8")
    # Packet must not claim an effective amendment
    assert "has approved" not in text.lower()
    assert "has been approved" not in text.lower()


def test_s035_handling_present():
    text = PACKET.read_text(encoding="utf-8")
    assert "S-035" in text
    assert "S-035-A" in text
    assert "S-035-B" in text
    assert "S-035-C" in text
    # Must not claim mandatory implementation without confirmation
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    for inv in data.get("s035_investigations", []):
        assert "PROVISIONAL_PENDING_SANDRA" in inv["standing"]


def test_provisional_tags_present():
    text = PACKET.read_text(encoding="utf-8")
    assert "PROVISIONAL_PENDING_SANDRA" in text
    assert "PROVISIONAL_PENDING_RANDY" in text


def test_classification_labels_present():
    text = PACKET.read_text(encoding="utf-8")
    for label in [
        "SOURCE-DERIVED FACT",
        "IMPLEMENTATION-VERIFIED FACT",
        "RESEARCH-EVIDENCE FACT",
        "INFERENCE",
        "PROVISIONAL WORDING",
        "EXTERNAL DECISION REQUIRED",
    ]:
        assert label in text, f"missing label {label}"
