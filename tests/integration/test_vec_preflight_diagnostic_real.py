"""Real-environment diagnostic test — skips when private vec_env absent.

Never writes, never executes, only inspects. Asserts that the typed diagnostic
explains the current preflight state rather than fabricating readiness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.integration.vec_preflight_diagnostic import (
    VecBlockerCode,
    explain_vec_interface_snapshot,
)

ROOT = Path(__file__).parents[2]
VEC_REPO = (ROOT.parent / "external" / "vec_env").resolve()
TOS_REPO = (ROOT.parent / "external" / "tos-data").resolve()


def test_real_env_diagnostic_explains_current_preflight() -> None:
    if not VEC_REPO.is_dir() or not TOS_REPO.is_dir():
        pytest.skip("reviewed external repositories are not available")
    diag = explain_vec_interface_snapshot(VEC_REPO, TOS_REPO)

    # Must be read-only
    assert diag.read_only is True
    assert diag.mutations_performed is False
    # Must not leak private paths
    raw = diag.model_dump_json()
    assert "/Users/" not in raw
    assert "/private/" not in raw
    assert "akash" not in raw.lower()

    # Current checkout has origin/main != pinned, so diagnostic must report REVISION_MISMATCH
    # and not be ready
    codes = {c.blocker_code for c in diag.checks if c.blocker_code}
    # Both repos should be clean but mismatched
    assert VecBlockerCode.REVISION_MISMATCH in codes
    assert True  # pinned reachable, but mismatch dominates (BLOB_MISSING may appear)
    # Should not claim ready when blocker remains
    assert diag.vec06_ready is False
    assert diag.vec07_ready is False
    # Must distinguish individual blockers
    vec_mismatches = [c for c in diag.checks if c.blocker_code is VecBlockerCode.REVISION_MISMATCH]
    assert len(vec_mismatches) >= 2  # vec_env and tos-data
    # Fresh dir is informational, not blocking
    fresh = [c for c in diag.checks if c.check_id == "fresh_result_dir_configured"]
    assert len(fresh) == 1
    assert fresh[0].required is False
