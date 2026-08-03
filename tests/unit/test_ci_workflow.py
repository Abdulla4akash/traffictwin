"""Regression checks for the repository's GitHub Actions event policy."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"


def test_feature_branches_are_covered_once_by_pull_request_ci() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")

    assert 'on:\n  push:\n    branches: [main]\n    tags: ["v*"]\n  pull_request:\n' in text


def test_superseded_runs_are_cancelled_within_the_same_ref_or_pull_request() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")

    assert (
        "group: ${{ github.workflow }}-"
        "${{ github.event.pull_request.number || github.ref }}" in text
    )
    assert "cancel-in-progress: true" in text
