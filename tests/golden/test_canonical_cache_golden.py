from __future__ import annotations

import json
from pathlib import Path

from traffictwin.ingestion.cache import canonical_cache_contract

EXPECTED = Path(__file__).parent / "expected" / "canonical_cache_contract.json"


def test_canonical_cache_contract_matches_approved_golden() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert canonical_cache_contract().model_dump(mode="json") == expected
