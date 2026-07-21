from __future__ import annotations

import json
from pathlib import Path

from traffictwin.storage.migrations import registry_migration_contract

EXPECTED = Path(__file__).parent / "expected" / "registry_migration_contract.json"


def test_registry_migration_contract_matches_approved_golden() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert registry_migration_contract().model_dump(mode="json") == expected
