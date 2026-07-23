"""Offline integrity checks for the scoped real DfT Gate-B probe record."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import cast

from traffictwin.integration.manchester.models import ManchesterRawMember, build_raw_fingerprint

ROOT = Path(__file__).parents[2]
RECORD = ROOT / "docs/integration/evidence/manchester_dft_gate_b_probe_20260723.json"
EXPECTED_CASES = {
    "raw_counts": ("/api/raw-counts", 43177),
    "count_points": ("/api/count-points", 6046),
    "aadf": ("/api/average-annual-daily-flow", 9219),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _record() -> dict[str, object]:
    return cast(dict[str, object], json.loads(RECORD.read_text(encoding="utf-8")))


def test_probe_record_is_permission_safe_and_keeps_capability_planned() -> None:
    text = RECORD.read_text(encoding="utf-8")
    record = json.loads(text)

    assert record["outcome"] == "accepted_with_scoped_blockers"
    assert record["capability_status_after_probe"] == "planned"
    assert record["source_authentication"] == "anonymous"
    assert record["synthetic"] is False
    assert record["raw_bytes_committed_by_probe"] is False
    assert record["open_blockers"] == ["GA-DFT-1", "GA-DFT-2", "GA-DFT-3"]
    assert "/" + "tmp/" not in text
    assert "/Users/" not in text
    assert "api_key" not in text.lower()
    assert "authorization" not in text.lower()


def test_probe_implementation_hashes_bind_the_executed_dirty_sources() -> None:
    record = _record()
    entries = record["implementation_files"]
    assert isinstance(entries, list)

    for entry in entries:
        assert isinstance(entry, dict)
        path = entry["path"]
        expected_sha256 = entry["sha256"]
        assert isinstance(path, str)
        assert isinstance(expected_sha256, str)
        assert _sha256((ROOT / path).read_bytes()) == expected_sha256


def test_every_probe_result_reconciles_inventory_parser_and_fixture() -> None:
    record = _record()
    results = record["results"]
    assert isinstance(results, list)
    assert {result["dataset"] for result in results} == set(EXPECTED_CASES)

    for result in results:
        assert isinstance(result, dict)
        dataset = result["dataset"]
        assert isinstance(dataset, str)
        endpoint, filter_id = EXPECTED_CASES[dataset]
        assert result["endpoint_path"] == endpoint
        assert result["filter_id"] == filter_id
        assert result["parser_status"] == "accepted"
        assert result["rows_seen"] == result["records_accepted"] == 1
        assert result["parser_report_fingerprint"] == result["accepted_replay_fingerprint"]

        member = ManchesterRawMember(
            relative_path=result["member_path"],
            byte_size=result["member_bytes"],
            media_type="application/json",
            sha256=result["member_sha256"],
        )
        assert build_raw_fingerprint((member,)) == result["raw_fingerprint"]
        assert str(result["snapshot_id"]).endswith(f"-{str(result['raw_fingerprint'])[:12]}")

        fixture_path = ROOT / str(result["retained_fixture"])
        fixture_payload = base64.b64decode(fixture_path.read_text(encoding="utf-8"))
        assert _sha256(fixture_payload) == result["retained_fixture_payload_sha256"]
        assert result["retained_fixture_row_equal"] is True


def test_probe_reconciliation_is_complete_but_explicitly_scoped() -> None:
    record = _record()
    reconciliation = record["reconciliation"]
    assert isinstance(reconciliation, dict)
    assert all(
        reconciliation[name] is True
        for name in (
            "all_responses_promoted_after_quarantine",
            "all_parser_statuses_accepted",
            "all_counts_reconcile_one_to_one",
            "all_accepted_replay_fingerprints_match",
            "all_retained_fixture_rows_equal",
        )
    )
    limitations = record["limitations"]
    assert isinstance(limitations, list)
    joined = " ".join(str(item) for item in limitations).lower()
    assert "not a full manchester bulk" in joined
    assert "does not by itself accept" in joined

    downstream = record["downstream_replay"]
    assert isinstance(downstream, dict)
    survey = downstream["raw_count_survey_view"]
    layer = downstream["count_point_layer"]
    catalogue = downstream["accepted_catalogue"]
    assert isinstance(survey, dict)
    assert isinstance(layer, dict)
    assert isinstance(catalogue, dict)
    assert survey["selected_records"] == survey["values_present"] == 1
    assert survey["values_missing"] == 0
    assert survey["time_basis"] == "local_clock_hour"
    assert survey["utc_timestamps_available"] is False
    assert layer["spatial_admitted"] == 1
    assert layer["spatial_excluded"] == 0
    assert layer["layer_status"] == "available"
    assert catalogue["snapshot_count"] == 3
    assert catalogue["raw_counts"] == catalogue["count_points"] == catalogue["aadf"] == 1
    assert catalogue["network_access_performed"] is False
