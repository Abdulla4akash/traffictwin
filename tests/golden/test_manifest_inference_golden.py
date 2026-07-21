from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from traffictwin.ingestion.manifest_inference import infer_manifest

FIXTURES = Path("tests/fixtures/manifest_inference")
EXPECTED = Path("tests/golden/expected")


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("value_patterns", "manifest_inference_value_patterns.json"),
        ("ambiguous", "manifest_inference_ambiguity.json"),
    ],
)
def test_manifest_inference_golden_projection(fixture: str, expected: str) -> None:
    first = _projection(FIXTURES / fixture)
    second = _projection(FIXTURES / fixture)
    golden = json.loads((EXPECTED / expected).read_text(encoding="utf-8"))

    assert first == second
    assert first == golden


def _projection(source: Path) -> dict[str, Any]:
    draft = infer_manifest(source)
    return {
        "source_fingerprint": draft.source_fingerprint,
        "draft_fingerprint": draft.draft_fingerprint,
        "analysis_ready": draft.analysis_ready,
        "confirmation_required": draft.confirmation_required,
        "files": [
            {
                "path": file.path,
                "status": file.status.value,
                "suggested_kind": file.suggested_kind,
                "sampled_rows": file.sampled_rows,
                "eligible_candidates": [
                    {
                        "kind": candidate.kind,
                        "score": candidate.score,
                        "required": {
                            field.canonical_field: {
                                "status": field.status.value,
                                "source": field.suggested_source_column,
                                "methods": [
                                    method.value
                                    for method in (
                                        field.candidates[0].methods if field.candidates else []
                                    )
                                ],
                                "unit": field.suggested_unit,
                            }
                            for field in candidate.fields
                            if field.required
                        },
                    }
                    for candidate in file.kind_candidates
                    if candidate.eligible
                ],
            }
            for file in draft.files
        ],
        "finding_codes": [finding.code.value for finding in draft.findings],
    }
