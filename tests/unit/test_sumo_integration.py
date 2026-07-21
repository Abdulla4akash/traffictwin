from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.evidence.availability import EvidenceStatus
from traffictwin.integration.sumo import (
    SumoTripStatus,
    compute_metrics_for_sumo,
    sumo_results_capability_manifest,
    sumo_source_contract,
    validate_sumo_results,
)
from traffictwin.metrics.results import MetricStatus
from traffictwin.validation.codes import ValidationCode

FIXTURE = Path("tests/fixtures/sumo/square_public")
FIXED_TIME = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_public_sumo_fixture_is_validated_without_mutating_raw_xml() -> None:
    before = {path.name: _sha256(path) for path in FIXTURE.glob("*.xml")}

    result = validate_sumo_results(FIXTURE, clock=fixed_clock)

    after = {path.name: _sha256(path) for path in FIXTURE.glob("*.xml")}
    assert result.report.may_import
    assert result.report.status.value == "accepted_with_warnings"
    assert result.report.import_timestamp == FIXED_TIME
    assert result.fingerprint == "024c1092c2a700793ae07dc0b227584bc041915175dc305ecc3a5dfc92d0d392"
    assert before == after
    assert {item.path: item.sha256 for item in result.raw_files} == {
        "summary.xml": "5ce8c9e1020a71bb082cd6a57b40e12903d014d92191f83da130487120620a91",
        "tripinfo.xml": "d648c403ec75099628401b23533188f4f92119e5e6ed4d390054ee5701c791eb",
    }


def test_sumo_tripinfo_and_summary_have_bounded_explicit_mappings() -> None:
    result = validate_sumo_results(FIXTURE, clock=fixed_clock)

    assert len(result.trip_observations) == 142
    assert len(result.canonical.trips) == 127
    assert len(result.summary_steps) == 1800
    statuses = [item.status for item in result.trip_observations]
    assert statuses.count(SumoTripStatus.COMPLETED) == 41
    assert statuses.count(SumoTripStatus.INCOMPLETE) == 86
    assert statuses.count(SumoTripStatus.UNDEPARTED) == 15
    first = result.canonical.trips[0]
    assert first.trip_id == "vertic.0"
    assert first.vehicle_id == "vertic.0"
    assert first.departure_time_s == 0.0
    assert first.arrival_time_s == 34.0
    assert first.duration_s == 34.0
    assert first.route_id is None
    assert result.summary_steps[0].running == 5
    assert result.summary_steps[-1].time_s == 179.9
    assert result.summary_steps[-1].running == 86
    assert result.evidence.trips is EvidenceStatus.AVAILABLE
    assert result.evidence.traffic is EvidenceStatus.UNAVAILABLE
    assert not result.canonical.traffic
    codes = {finding.code for finding in result.report.findings}
    assert ValidationCode.SUMO_SUMMARY_SOURCE_ONLY in codes
    assert ValidationCode.SUMO_FCD_MAPPING_REQUIRED in codes
    assert ValidationCode.SUMO_DIRECT_LAUNCH_UNSUPPORTED in codes


def test_sumo_metrics_use_canonical_completed_and_incomplete_trips() -> None:
    result = validate_sumo_results(FIXTURE, clock=fixed_clock)
    metrics = compute_metrics_for_sumo(result, clock=fixed_clock).by_key()

    assert metrics["trip.records.count"].value == 127
    assert metrics["trip.completed.count"].value == 41
    assert metrics["trip.incomplete.count"].value == 86
    assert metrics["trip.completion.rate"].value == 41 / 127
    assert metrics["trip.duration.mean_s"].status is MetricStatus.AVAILABLE
    assert metrics["traffic.count.total"].status is MetricStatus.UNAVAILABLE
    assert metrics["traffic.count.total"].missing_evidence == ["traffic"]
    assert metrics["spatial.rsu.task.count_by_target"].status is MetricStatus.UNAVAILABLE
    assert (
        metrics["spatial.vehicle.observation_count_by_grid_cell"].status is MetricStatus.UNAVAILABLE
    )


def test_sumo_contract_is_import_only_and_does_not_map_fcd_or_summary_counts() -> None:
    contract = sumo_source_contract()
    capabilities = sumo_results_capability_manifest()
    by_source = {mapping.source: mapping for mapping in contract.mappings}

    assert capabilities.supports.run_bundle_import is CapabilitySupport.TRUE
    assert capabilities.supports.streaming_canonicalisation is CapabilitySupport.FALSE
    assert capabilities.supports.canonical_table_caching is CapabilitySupport.FALSE
    assert capabilities.supports.environment_doctor is CapabilitySupport.FALSE
    assert capabilities.supports.ro_crate_archival_export is CapabilitySupport.FALSE
    assert capabilities.supports.generalised_external_source_contract is CapabilitySupport.TRUE
    assert capabilities.supports.time_windowed_metrics is CapabilitySupport.FALSE
    assert capabilities.supports.latency_percentile_family is CapabilitySupport.FALSE
    assert capabilities.supports.energy_metric_family is CapabilitySupport.FALSE
    assert capabilities.supports.fairness_metric_family is CapabilitySupport.FALSE
    assert capabilities.supports.spatial_rsu_metric_family is CapabilitySupport.FALSE
    assert capabilities.supports.custom_metric_plugin_api is CapabilitySupport.TRUE
    assert capabilities.supports.declarative_rule_authoring is CapabilitySupport.TRUE
    assert capabilities.supports.fairness_disparity_diagnosis is CapabilitySupport.FALSE
    assert capabilities.supports.energy_anomaly_diagnosis is CapabilitySupport.FALSE
    assert capabilities.supports.nearest_flip_analysis is CapabilitySupport.FALSE
    assert capabilities.supports.threshold_sensitivity_sweep is CapabilitySupport.FALSE
    assert capabilities.supports.cross_rule_reasoning is CapabilitySupport.FALSE
    assert capabilities.supports.paired_statistical_study is CapabilitySupport.FALSE
    assert capabilities.supports.n_way_policy_ranking is CapabilitySupport.FALSE
    assert capabilities.supports.equivalence_testing is CapabilitySupport.FALSE
    assert capabilities.supports.difference_provenance is CapabilitySupport.FALSE
    assert capabilities.supports.provenance_graph_export is CapabilitySupport.FALSE
    assert capabilities.supports.provenance_completeness_score is CapabilitySupport.FALSE
    assert capabilities.supports.direct_launch is CapabilitySupport.FALSE
    assert capabilities.supports.asynchronous_launch is CapabilitySupport.FALSE
    assert by_source["summary.step"].destination is None
    assert by_source["fcd-export"].status == "unsupported"
    assert "SUMO launch or rerun" in contract.unsupported


def test_sumo_checksum_mismatch_rejects_before_xml_parsing(tmp_path: Path) -> None:
    package = tmp_path / "sumo"
    shutil.copytree(FIXTURE, package)
    tripinfo = package / "tripinfo.xml"
    tripinfo.write_text(tripinfo.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = validate_sumo_results(package, clock=fixed_clock)

    assert not result.report.may_import
    assert not result.trip_observations
    assert ValidationCode.SUMO_FILE_CHECKSUM_MISMATCH in {
        finding.code for finding in result.report.findings
    }


def test_sumo_dtd_or_entity_declaration_is_rejected(tmp_path: Path) -> None:
    package = tmp_path / "sumo"
    shutil.copytree(FIXTURE, package)
    tripinfo = package / "tripinfo.xml"
    tripinfo.write_text(
        '<?xml version="1.0"?><!DOCTYPE tripinfos [<!ENTITY x "unsafe">]>'
        '<tripinfos><tripinfo id="&x;" depart="0" arrival="1" duration="1"/></tripinfos>',
        encoding="utf-8",
    )
    _update_manifest_checksum(package, "tripinfo", tripinfo)

    result = validate_sumo_results(package, clock=fixed_clock)

    assert not result.report.may_import
    assert ValidationCode.SUMO_XML_UNSAFE in {finding.code for finding in result.report.findings}


def test_sumo_non_finite_numeric_value_is_rejected(tmp_path: Path) -> None:
    package = tmp_path / "sumo"
    shutil.copytree(FIXTURE, package)
    tripinfo = package / "tripinfo.xml"
    content = tripinfo.read_text(encoding="utf-8")
    tripinfo.write_text(content.replace('depart="0.00"', 'depart="NaN"', 1), encoding="utf-8")
    _update_manifest_checksum(package, "tripinfo", tripinfo)

    result = validate_sumo_results(package, clock=fixed_clock)

    assert not result.report.may_import
    assert ValidationCode.SUMO_XML_VALUE_INVALID in {
        finding.code for finding in result.report.findings
    }


def _update_manifest_checksum(package: Path, kind: str, path: Path) -> None:
    manifest_path = package / "sumo-source.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][kind]["checksum_sha256"] = _sha256(path)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
