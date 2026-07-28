from __future__ import annotations

from pathlib import Path

import pytest
from scripts.prepare_bbus_successors import (
    APPROVAL_PATH,
    APPROVAL_SHA256,
    CORRIDOR_PROTOCOL_PATH,
    CORRIDOR_PROTOCOL_SHA256,
    SPARSE_PROTOCOL_PATH,
    SPARSE_PROTOCOL_SHA256,
    _new_private_output,
    _sha256_file,
)

from traffictwin.integration.manchester.bbus_successors import BBusSuccessorError


def test_script_bindings_match_both_approved_protocols_and_receipt() -> None:
    expected = {
        CORRIDOR_PROTOCOL_PATH: CORRIDOR_PROTOCOL_SHA256,
        SPARSE_PROTOCOL_PATH: SPARSE_PROTOCOL_SHA256,
        APPROVAL_PATH: APPROVAL_SHA256,
    }
    for path, digest in expected.items():
        assert _sha256_file(Path(path)) == digest


def test_successor_output_is_private_and_new_only(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    output = _new_private_output(tmp_path, Path("data/successors"))
    assert output == (tmp_path / "data" / "successors").resolve()
    with pytest.raises(BBusSuccessorError, match="never overwritten"):
        _new_private_output(tmp_path, Path("data/successors"))
    with pytest.raises(BBusSuccessorError, match="named child"):
        _new_private_output(tmp_path, Path("elsewhere"))
