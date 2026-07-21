from __future__ import annotations

import json
from pathlib import Path

from traffictwin.doctor import doctor_contract

EXPECTED = Path(__file__).parent / "expected" / "doctor_contract.json"


def test_doctor_contract_matches_approved_golden() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert doctor_contract().model_dump(mode="json") == expected
