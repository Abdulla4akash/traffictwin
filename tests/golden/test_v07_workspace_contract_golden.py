from __future__ import annotations

import json
from pathlib import Path

from traffictwin.release.compatibility import v07_workspace_contract

EXPECTED = (
    Path(__file__).parents[2] / "docs" / "reference" / "generated" / "v07_workspace_contract.json"
)


def test_v07_workspace_contract_matches_approved_golden() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert v07_workspace_contract().model_dump(mode="json") == expected
