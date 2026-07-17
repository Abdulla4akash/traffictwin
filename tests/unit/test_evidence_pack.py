from __future__ import annotations

from datetime import UTC, datetime

from tests.helpers import assert_json_has_no_nan, bundle_result, fixed_clock, metric_collection
from traffictwin.evidence.builder import build_evidence_pack


def test_evidence_pack_serialises_without_narrative_diagnosis_fields() -> None:
    pack = build_evidence_pack(
        bundle_result("baseline_valid"),
        metric_collection("baseline_valid"),
        clock=fixed_clock,
    )
    data = pack.model_dump(mode="json")

    assert pack.schema_version == "1.0"
    assert pack.synthetic is True
    assert data["run_context"]["run_id"] == "run-baseline-001"
    assert "hypothesis" not in data
    assert "recommendation" not in data
    assert_json_has_no_nan(data)


def test_evidence_pack_fingerprint_normalises_generated_timestamps() -> None:
    bundle = bundle_result("baseline_valid")
    pack_a = build_evidence_pack(bundle, clock=fixed_clock)
    pack_b = build_evidence_pack(
        bundle,
        clock=lambda: datetime(2026, 7, 17, 12, 5, tzinfo=UTC),
    )

    assert pack_a.fingerprint() == pack_b.fingerprint()
