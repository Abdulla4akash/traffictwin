from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

AUDIT_PATH = (
    Path(__file__).parents[2]
    / "docs"
    / "reference"
    / "generated"
    / "vec_source_snapshot_audit.json"
)


def _audit() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(AUDIT_PATH.read_text(encoding="utf-8")))


def test_vec_01_audit_pins_sources_and_hashes_every_admitted_file() -> None:
    audit = _audit()

    assert audit["schema_version"] == "traffictwin.vec-source-snapshot-audit.v1"
    assert audit["capability_id"] == "VEC-01"
    assert audit["audit_outcome"] == "accepted_with_scoped_blockers"
    assert (
        audit["sources"]["vec_env"]["audited_commit"] == "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
    )
    assert (
        audit["sources"]["tos-data"]["audited_commit"] == "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"
    )

    inventory = audit["evidence_inventory"]
    files = inventory["files"]
    assert inventory["file_count"] == len(files) == 154
    environment = next(
        item
        for item in files
        if item["repository"] == "vec_env" and item["path"] == "jaxmarl/env/vec_jax.py"
    )
    assert environment["sha256"] == (
        "4eed6b61f157b9a1ba203d0095acdecb0741f2da8d7fc4f411b6ee16a0bdd4f9"
    )
    assert inventory["total_bytes"] == sum(item["bytes"] for item in files)
    assert len({(item["repository"], item["path"]) for item in files}) == len(files)
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in files)


def test_vec_01_observed_source_contract_checks_pass() -> None:
    observations = _audit()["observations"]

    assert observations["perstep"]["file_count"] == 60
    assert observations["perstep"]["failed_check_counts"] == {}
    assert observations["pertask"]["file_count"] == 6
    assert observations["checkpoints"]["file_count"] == 2
    assert observations["tripinfo"]["file_count"] == 4
    assert observations["evaluation_master"]["row_count"] == 300
    assert observations["evaluation_master"]["engine_values"] == ["v2_post_nrsus_fix"]

    for scenario in observations["trace_and_occupancy"].values():
        occupancy = scenario["occupancy"]
        assert occupancy["exact_mask_match"] is True
        assert occupancy["visit_seconds_match_mask"] is True
        assert occupancy["slot_overlap_count"] == 0
        assert occupancy["same_vehicle_overlap_count"] == 0


def test_vec_01_keeps_unsupported_claims_blocked() -> None:
    audit = _audit()
    pertask = audit["observations"]["pertask"]["files"]
    blocker_ids = {blocker["id"] for blocker in audit["dependent_blockers"]}

    assert all(item["contains_per_task_energy"] is False for item in pertask)
    assert all(item["contains_eventual_physical_completion"] is False for item in pertask)
    assert "per_task_energy_absent" in blocker_ids
    assert "eventual_physical_completion_absent" in blocker_ids
    assert "no_repository_licence" in blocker_ids
    assert audit["rights_boundary"]["not_inferred"] == [
        "open-source licence",
        "raw data redistribution",
        "checkpoint redistribution",
        "blanket publication permission",
    ]
