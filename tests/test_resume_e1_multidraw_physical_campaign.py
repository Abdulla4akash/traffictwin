from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.resume_e1_multidraw_physical_campaign import (
    ACCEPTED_SEED1_INDEX_SHA256,
    _json_new,
    _require_accepted_seed1,
)


def test_json_new_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "record.json"
    _json_new(target, {"first": True})

    with pytest.raises(FileExistsError):
        _json_new(target, {"first": False})

    assert json.loads(target.read_text(encoding="utf-8")) == {"first": True}


def test_accepted_seed1_checkpoint_requires_exact_index(tmp_path: Path) -> None:
    index = tmp_path / "evidence_checksums_seed1_complete.sha256"
    index.write_text("not the accepted index\n", encoding="utf-8")
    assert ACCEPTED_SEED1_INDEX_SHA256

    with pytest.raises(ValueError, match="seed-1 evidence index identity"):
        _require_accepted_seed1(tmp_path)


def test_remaining_seed_directory_prevents_resume_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = tmp_path / "evidence_checksums_seed1_complete.sha256"
    index.write_text("accepted\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.resume_e1_multidraw_physical_campaign.sha256_file",
        lambda path: ACCEPTED_SEED1_INDEX_SHA256 if path == index else "unexpected",
    )
    (tmp_path / "fleet_seed_2").mkdir()

    with pytest.raises(FileExistsError, match="fleet_seed_2"):
        _require_accepted_seed1(tmp_path)
