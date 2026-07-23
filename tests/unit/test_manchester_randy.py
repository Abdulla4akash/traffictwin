"""Acceptance and refusal evidence for the MAN-06 Randy bridge candidate."""

from __future__ import annotations

import shutil
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.randy import (
    RandyBridgeCitation,
    RandyManchesterBridgeReport,
    load_randy_manchester_bridge,
)

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "docs" / "reference" / "generated" / "vec_dissertation_pack"
MANIFEST_SHA256 = "e5a03a3ca291b67728662deeac5c9efd2182f7dd4c7201ab92c7632c784a7df1"


def report() -> RandyManchesterBridgeReport:
    return load_randy_manchester_bridge(PACK)


def test_checked_in_vec11_pack_loads_as_bounded_case_study() -> None:
    bridge = report()
    assert bridge.status == "candidate"
    assert bridge.source_capability == "VEC-11"
    assert bridge.source_pack_status == "accepted"
    assert bridge.source_pack_manifest_sha256 == MANIFEST_SHA256
    assert bridge.engine_version == "v2_post_nrsus_fix"
    assert bridge.selected_run_label == "fcd_s102_uk2030_we_fs0"
    assert bridge.selection_label == "_s102_best_of_seeds"
    assert len(bridge.samples) == 3
    assert len(bridge.metrics) == 26
    assert bridge.available_metric_count == 18
    assert bridge.unavailable_metric_count == 8


def test_bridge_preserves_both_reviewed_repository_citations() -> None:
    bridge = report()
    assert [citation.repository for citation in bridge.citations] == ["tos-data", "vec_env"]
    assert bridge.citations[0].reviewed_commit == ("f6c67acbed3360dba3a0d5c8d1fd557caa99ecff")
    assert bridge.citations[1].reviewed_commit == ("068b4ea33e640f206ce6a7d04f3d6fae2ac831f4")
    assert all(
        citation.reviewed_commit[:12] in citation.citation_text for citation in bridge.citations
    )


def test_case_study_cannot_be_relabelled_live_geographic_public_or_canonical() -> None:
    bridge = report()
    assert bridge.temporal_semantics == "simulation_clock_removed_by_sanitisation"
    assert bridge.display_mode == "non_geographic_case_study"
    assert bridge.non_geographic_replay_available is True
    assert bridge.geographic_map_layer_available is False
    assert bridge.geographic_unavailable_reason == "no_evidenced_coordinate_projection"
    assert bridge.canonical_manchester_projection_available is False
    assert bridge.freshness_state_available is False
    assert bridge.live_data is False
    assert bridge.general_manchester_telemetry is False
    assert bridge.public_hosting_authorized is False
    assert bridge.permission_is_formal_licence is False

    for field in (
        "geographic_map_layer_available",
        "canonical_manchester_projection_available",
        "freshness_state_available",
        "live_data",
        "general_manchester_telemetry",
        "public_hosting_authorized",
        "permission_is_formal_licence",
    ):
        strengthened = bridge.model_dump(mode="python")
        strengthened[field] = True
        with pytest.raises(ValidationError):
            RandyManchesterBridgeReport.model_validate(strengthened)


def test_sanitised_samples_do_not_regain_identity_clock_geometry_or_target() -> None:
    bridge = report()
    sample_fields = set(type(bridge.samples[0]).model_fields)
    forbidden = {
        "sumo_vehicle_id",
        "vehicle_ref",
        "slot",
        "task_index",
        "time_index",
        "trace_time_s",
        "depart_s",
        "arrival_s",
        "longitude",
        "latitude",
        "selected_target_index",
        "eligible_best_rsu",
        "eligible_best_v2v",
    }
    assert sample_fields.isdisjoint(forbidden)
    assert bridge.raw_source_identity_available is False
    assert "/Users/" not in bridge.canonical_json()
    assert "file://" not in bridge.canonical_json()


def test_metric_availability_and_missing_evidence_remain_explicit() -> None:
    bridge = report()
    metrics = {metric.metric_key: metric for metric in bridge.metrics}

    deadline = metrics["tos.task.deadline_success.rate"]
    assert deadline.status == "available"
    assert deadline.value == pytest.approx(0.9166922343660754)
    assert deadline.unit == "ratio"
    assert deadline.missing_evidence == ()

    completion = metrics["task.completion.rate"]
    assert completion.status == "unavailable"
    assert completion.value is None
    assert completion.missing_evidence == ("physical completion evidence is absent",)
    assert bridge.physical_completion_available is False
    assert bridge.confirmed_transfer_target_available is False
    assert bridge.per_task_energy_available is False


def test_required_permission_and_scientific_limitations_are_retained() -> None:
    bridge = report()
    assert bridge.pseudonymisation_is_anonymity is False
    assert bridge.permission_scope == (
        "repository_and_dissertation_sanitised_samples_and_aggregates"
    )
    assert "Pseudonymisation reduces direct identification but is not anonymity." in (
        bridge.limitations
    )
    assert "Deadline success is not eventual physical task completion." in bridge.limitations

    weakened = bridge.model_dump(mode="python")
    weakened["limitations"] = ()
    with pytest.raises(ValidationError, match="mandatory VEC-11 limitations are absent"):
        RandyManchesterBridgeReport.model_validate(weakened)


def test_output_is_deterministic_and_does_not_record_input_path() -> None:
    first = report()
    second = report()
    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint() == second.fingerprint()
    assert str(PACK) not in first.canonical_json()
    assert [member.relative_path for member in first.members] == [
        "aggregate_metrics_s102.csv",
        "manifest.json",
        "sanitised_matched_sample_s102.csv",
    ]


def test_tampered_or_extra_pack_material_fails_closed(tmp_path: Path) -> None:
    tampered = tmp_path / "tampered"
    shutil.copytree(PACK, tampered)
    aggregate = tampered / "aggregate_metrics_s102.csv"
    aggregate.write_bytes(aggregate.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="mismatch"):
        load_randy_manchester_bridge(tampered)

    extra = tmp_path / "extra"
    shutil.copytree(PACK, extra)
    (extra / "raw-identities.csv").write_text("forbidden\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly three regular files"):
        load_randy_manchester_bridge(extra)


def test_unaccepted_repository_commit_is_unrepresentable() -> None:
    with pytest.raises(ValidationError, match="accepted reviewed commit"):
        RandyBridgeCitation(
            repository="vec_env",
            reviewed_commit="0" * 40,
            citation_text="Randy Putra, vec_env source repository, reviewed commit 000000000000.",
            url="https://gitlab.cs.man.ac.uk/e62992rp/vec_env",
        )


def test_bridge_performs_no_network_or_external_repository_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    bridge = report()
    assert bridge.source_capability == "VEC-11"
