from __future__ import annotations

import json
from pathlib import Path

from traffictwin.research_object import research_object_contract

EXPECTED = Path(__file__).parent / "expected" / "research_object_contract.json"


def test_research_object_contract_matches_approved_golden() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert research_object_contract().model_dump(mode="json") == expected
