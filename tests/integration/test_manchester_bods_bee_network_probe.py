"""Offline verification of the safe aggregate Bee Network probe record."""

from __future__ import annotations

import json
from pathlib import Path

from traffictwin.integration.manchester.bee_network import bee_network_scope_policy_v1

RECORD = Path("docs/integration/evidence/manchester_bods_bee_network_probe_20260723.json")


def test_probe_record_reconciles_policy_and_contains_no_private_rows() -> None:
    payload = json.loads(RECORD.read_text(encoding="utf-8"))
    policy = bee_network_scope_policy_v1()
    operator_counts = dict(payload["operator_ref_counts"])

    assert payload["capability_status_after_probe"] == "planned"
    assert payload["network_access_performed"] is False
    assert sum(operator_counts.values()) == payload["source_counts"]["records_accepted"]
    assert payload["source_counts"]["records_accepted"] == 1565
    assert payload["source_counts"]["live_vehicle"] == 304
    assert payload["source_counts"]["stale"] == 1261
    assert tuple(payload["policy"]["verified_operator_refs"]) == policy.verified_operator_refs
    assert tuple(payload["policy"]["pending_operator_refs"]) == policy.pending_operator_refs
    assert payload["policy"]["policy_fingerprint"] == policy.fingerprint()
    assert payload["policy"]["bee_network_franchised"] == sum(
        operator_counts[operator_ref] for operator_ref in policy.verified_operator_refs
    )
    assert (
        payload["policy"]["bee_network_franchised"] + payload["policy"]["non_franchised_or_unknown"]
        == payload["source_counts"]["records_accepted"]
    )

    raw = RECORD.read_text(encoding="utf-8")
    for prohibited in (
        "VehicleRef",
        "vehicle_token",
        "api_key",
        "/Users/",
        "longitude",
        "latitude",
    ):
        assert prohibited not in raw
