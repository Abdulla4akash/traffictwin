"""Synthetic derivation, publication, and refusal tests for VEC-11."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.tos_v2_helpers import (
    build_v2_occupancy_rows,
    build_v2_perstep,
    build_v2_pertask,
    build_v2_trace,
    build_v2_tripinfo_records,
)
from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
)
from traffictwin.integration.vec_publication import (
    VecDissertationPackError,
    VecDissertationPackManifest,
    derive_sanitised_matched_sample,
    render_vec_dissertation_pack,
    vec_dissertation_pack_contract,
    verify_vec_dissertation_pack,
    write_vec_dissertation_pack,
)
from traffictwin.integration.vec_science import (
    VecScientificAdmissionReport,
    build_vec_scientific_admission,
)
from traffictwin.integration.vec_task_join import VecTaskJoinReport, build_task_join_report
from traffictwin.integration.vec_trip_join import VecTripJoinDataset, build_trip_join_dataset

NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
RUN_LABEL = "fcd_s102_uk2030_we_fs0"


def _evidence() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    VecIdentitySnapshot,
    VecTaskJoinReport,
    VecTripJoinDataset,
    VecScientificAdmissionReport,
]:
    trace = build_v2_trace()
    perstep = build_v2_perstep()
    pertask = build_v2_pertask()
    header, occupancy = build_v2_occupancy_rows()
    identity = build_vehicle_identity_snapshot(trace, header, occupancy, scenario="we")
    task_report = build_task_join_report(trace, perstep, pertask, identity, run_label=RUN_LABEL)
    trips = [
        *build_v2_tripinfo_records(),
        {
            "id": "veh_synthetic_b",
            "depart": 100.0,
            "arrival": 106.0,
            "duration": 6.0,
            "routeLength": 125.0,
        },
    ]
    xml = "".join(
        (
            f'<tripinfo id="{item["id"]}" depart="{item["depart"]}" '
            f'arrival="{item["arrival"]}" duration="{item["duration"]}" '
            f'routeLength="{item["routeLength"]}"/>'
        )
        for item in trips
    )
    trip_dataset = build_trip_join_dataset(
        trace,
        identity,
        gzip.compress(f"<tripinfos>{xml}</tripinfos>".encode(), mtime=0),
        source_path="tripinfo/synthetic.xml.gz",
    )
    admission = build_vec_scientific_admission(
        trace,
        perstep,
        pertask,
        identity,
        task_report,
        reproduction_report_fingerprint="a" * 64,
        reproduction_grade="numerically_equivalent",
        computed_at=NOW,
        trip_report=trip_dataset.report,
    )
    return trace, perstep, pertask, identity, task_report, trip_dataset, admission


def _render() -> tuple[VecDissertationPackManifest, dict[str, bytes]]:
    trace, perstep, pertask, identity, task_report, trips, admission = _evidence()
    rows = derive_sanitised_matched_sample(
        trace, perstep, pertask, identity, task_report, trips, admission
    )
    return render_vec_dissertation_pack(
        rows,
        admission,
        task_report,
        trips,
        sensitive_vehicle_ids=[span.sumo_vehicle_id for span in identity.spans],
    )


def test_derives_three_action_diverse_rounded_pseudonymous_rows() -> None:
    trace, perstep, pertask, identity, task_report, trips, admission = _evidence()

    rows = derive_sanitised_matched_sample(
        trace, perstep, pertask, identity, task_report, trips, admission
    )

    assert [row.sample_id for row in rows] == ["sample-001", "sample-002", "sample-003"]
    assert {row.action for row in rows} == {Decision.LOCAL, Decision.V2I, Decision.V2V}
    assert all(row.latency_ms_rounded_10 % 10 == 0 for row in rows)
    assert all(row.trip_duration_s_rounded_10 % 10 == 0 for row in rows)
    assert all(row.trip_route_length_m_rounded_100 % 100 == 0 for row in rows)
    dumped = json.dumps([row.model_dump(mode="json") for row in rows])
    assert "veh_synthetic" not in dumped
    assert "time_index" not in dumped
    assert "selected_target" not in dumped


def test_rendered_manifest_carries_permission_disclosures_and_exact_hashes() -> None:
    manifest, payloads = _render()

    assert manifest.status == "accepted"
    assert manifest.selection_label == "_s102_best_of_seeds"
    assert manifest.engine_version == "v2_post_nrsus_fix"
    assert manifest.pseudonym_mapping_retained is False
    assert manifest.anonymity_claimed is False
    assert manifest.public_hosting_authorized is False
    assert manifest.aggregate_metric_count == 26
    assert manifest.available_metric_count == 18
    assert manifest.unavailable_metric_count == 8
    assert set(payloads) == {
        "aggregate_metrics_s102.csv",
        "manifest.json",
        "sanitised_matched_sample_s102.csv",
    }
    combined = b"\n".join(payloads.values())
    assert b"veh_synthetic" not in combined
    assert b"/Users/" not in combined
    assert b"_s102" in combined


def test_atomic_pack_round_trip_is_deterministic_and_refuses_existing_destination(
    tmp_path: Path,
) -> None:
    manifest, payloads = _render()
    first = tmp_path / "first"
    second = tmp_path / "second"

    write_vec_dissertation_pack(first, payloads)
    write_vec_dissertation_pack(second, payloads)

    verified = verify_vec_dissertation_pack(first)
    assert verified == manifest
    for name in payloads:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    with pytest.raises(FileExistsError):
        write_vec_dissertation_pack(first, payloads)


def test_verifier_rejects_extra_files_and_hash_mutation(tmp_path: Path) -> None:
    _, payloads = _render()
    extra = tmp_path / "extra"
    write_vec_dissertation_pack(extra, payloads)
    (extra / "unexpected.txt").write_text("not admitted", encoding="utf-8")
    with pytest.raises(VecDissertationPackError, match="exactly three"):
        verify_vec_dissertation_pack(extra)

    changed = tmp_path / "changed"
    write_vec_dissertation_pack(changed, payloads)
    sample = changed / "sanitised_matched_sample_s102.csv"
    sample.chmod(0o644)
    sample.write_bytes(sample.read_bytes() + b"\n")
    with pytest.raises(VecDissertationPackError, match="size mismatch"):
        verify_vec_dissertation_pack(changed)


def test_source_mismatch_and_strengthened_publication_claim_fail_closed() -> None:
    trace, perstep, pertask, identity, task_report, trips, admission = _evidence()
    payload = admission.model_dump(mode="json")
    payload["task_join_report_fingerprint"] = "b" * 64
    changed = VecScientificAdmissionReport.model_validate(payload)
    with pytest.raises(VecDissertationPackError, match="does not bind"):
        derive_sanitised_matched_sample(
            trace, perstep, pertask, identity, task_report, trips, changed
        )

    manifest, _ = _render()
    strengthened = manifest.model_dump(mode="json")
    strengthened["public_hosting_authorized"] = True
    with pytest.raises(ValidationError, match="public_hosting_authorized"):
        VecDissertationPackManifest.model_validate(strengthened)


def test_renderer_requires_complete_source_leak_inventory_and_action_diversity() -> None:
    trace, perstep, pertask, identity, task_report, trips, admission = _evidence()
    rows = derive_sanitised_matched_sample(
        trace, perstep, pertask, identity, task_report, trips, admission
    )
    with pytest.raises(VecDissertationPackError, match="identifier inventory"):
        render_vec_dissertation_pack(
            rows,
            admission,
            task_report,
            trips,
            sensitive_vehicle_ids=[],
        )
    with pytest.raises(VecDissertationPackError, match="cover local, V2I, and V2V"):
        render_vec_dissertation_pack(
            [rows[0], rows[0].model_copy(update={"sample_id": "sample-002"}), rows[2]],
            admission,
            task_report,
            trips,
            sensitive_vehicle_ids=[span.sumo_vehicle_id for span in identity.spans],
        )


def test_contract_exposes_the_non_anonymity_and_exclusion_boundary() -> None:
    contract = vec_dissertation_pack_contract()

    assert contract.status == "implemented"
    assert contract.sample_rows == 3
    assert "pseudonymisation is not anonymity" in contract.mandatory_disclosures
    assert "actor checkpoints" in contract.excluded_material
    assert contract.fingerprint() == vec_dissertation_pack_contract().fingerprint()
