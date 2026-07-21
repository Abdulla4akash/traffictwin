from __future__ import annotations

import json
from pathlib import Path

from traffictwin.integration.external import external_source_catalogue

EXPECTED = Path(__file__).parent / "expected" / "external_source_contract.json"


def test_external_source_contract_matches_approved_golden() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert external_source_catalogue().model_dump(mode="json") == expected
