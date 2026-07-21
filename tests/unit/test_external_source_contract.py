from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from tests.tos_helpers import write_tos_package
from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.integration.external import (
    ConversionLevel,
    DiscoveryReportStatus,
    DiscoveryStatus,
    ExternalSourceAdapter,
    ExternalSourceError,
    SemanticStatus,
    SumoExternalSourceAdapter,
    TosExternalSourceAdapter,
    ValidationOutcome,
    discover_external_sources,
    external_source_adapters,
    external_source_catalogue,
    inspect_external_source,
)
from traffictwin.integration.sumo import sumo_results_capability_manifest
from traffictwin.integration.tos import tos_data_capability_manifest

SUMO_FIXTURE = Path("tests/fixtures/sumo/square_public")


def _inventory(root: Path) -> dict[str, tuple[str, int, int]]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_catalogue_publishes_closed_runtime_checkable_reference_adapters() -> None:
    adapters = external_source_adapters()
    catalogue = external_source_catalogue()

    assert [adapter.adapter_id for adapter in adapters] == [
        "sumo_results_v1",
        "tos_data_read_only",
    ]
    assert all(isinstance(adapter, ExternalSourceAdapter) for adapter in adapters)
    assert [adapter.adapter_id for adapter in catalogue.adapters] == [
        "sumo_results_v1",
        "tos_data_read_only",
    ]
    assert catalogue.capability_id == "OPS-05"
    assert catalogue.contract_version == "traffictwin-external-source-v1"
    assert len(catalogue.fingerprint()) == 64
    assert catalogue.fingerprint() == external_source_catalogue().fingerprint()
    assert "dynamic plugin discovery or uploaded adapter code" in catalogue.exclusions


def test_reference_contracts_keep_conversion_and_semantics_distinct() -> None:
    sumo = SumoExternalSourceAdapter().contract()
    tos = TosExternalSourceAdapter().contract()

    assert sumo.conversion.level is ConversionLevel.PARTIAL_CANONICAL
    assert sumo.conversion.canonical_outputs == ["TripRecord for departed valid tripinfo records"]
    assert tos.conversion.level is ConversionLevel.AGGREGATE_SUMMARY
    assert not tos.conversion.canonical_outputs
    assert "canonical TaskRecord conversion" in tos.conversion.unavailable_outputs
    assert sumo.capabilities.supports.run_bundle_import is CapabilitySupport.TRUE
    assert tos.capabilities.supports.run_bundle_import is CapabilitySupport.FALSE
    assert all(field.canonical_target is None for field in tos.field_semantics)
    assert any(field.canonical_target for field in sumo.field_semantics)
    assert any(blocker.status is SemanticStatus.UNKNOWN for blocker in tos.blockers)
    assert sumo.fingerprint() != tos.fingerprint()


def test_ops05_capability_truth_is_visible_for_all_three_product_boundaries() -> None:
    assert (
        default_export_import_manifest().supports.generalised_external_source_contract
        is CapabilitySupport.TRUE
    )
    assert (
        sumo_results_capability_manifest().supports.generalised_external_source_contract
        is CapabilitySupport.TRUE
    )
    assert (
        tos_data_capability_manifest().supports.generalised_external_source_contract
        is CapabilitySupport.TRUE
    )


def test_discovery_selects_sumo_by_exact_marker_without_deep_parsing() -> None:
    report = discover_external_sources(SUMO_FIXTURE)

    assert report.status is DiscoveryReportStatus.ONE_MATCH
    assert report.candidate_adapter_ids == ["sumo_results_v1"]
    assert report.results[0].status is DiscoveryStatus.MATCHED
    assert report.results[0].matched_markers == ["sumo-source.yaml"]
    assert report.results[1].status is DiscoveryStatus.NOT_MATCHED
    assert not report.mutations_performed
    assert "/Users/" not in report.canonical_json()


def test_discovery_selects_tos_and_reports_optional_markers(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")

    report = discover_external_sources(package)

    assert report.status is DiscoveryReportStatus.ONE_MATCH
    assert report.candidate_adapter_ids == ["tos_data_read_only"]
    tos = next(item for item in report.results if item.adapter_id == "tos_data_read_only")
    assert tos.status is DiscoveryStatus.MATCHED
    assert tos.matched_markers == [
        "DATA_DICTIONARY.md",
        "evals/eval_results_master.csv",
        "instrumented",
        "traces",
        "training",
    ]


def test_unknown_ambiguous_and_symlinked_sources_fail_closed(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown"
    unknown.mkdir()
    assert discover_external_sources(unknown).status is DiscoveryReportStatus.NO_MATCH
    with pytest.raises(ExternalSourceError, match="no registered"):
        inspect_external_source(unknown)

    ambiguous = tmp_path / "ambiguous"
    shutil.copytree(SUMO_FIXTURE, ambiguous)
    (ambiguous / "evals").mkdir()
    (ambiguous / "evals/eval_results_master.csv").write_text("not,parsed\n", encoding="utf-8")
    report = discover_external_sources(ambiguous)
    assert report.status is DiscoveryReportStatus.AMBIGUOUS
    assert report.candidate_adapter_ids == ["sumo_results_v1", "tos_data_read_only"]
    with pytest.raises(ExternalSourceError, match="multiple"):
        inspect_external_source(ambiguous)

    symlink = tmp_path / "source-link"
    symlink.symlink_to(SUMO_FIXTURE.resolve(), target_is_directory=True)
    blocked = discover_external_sources(symlink)
    assert blocked.status is DiscoveryReportStatus.BLOCKED
    assert all(item.status is DiscoveryStatus.BLOCKED for item in blocked.results)
    with pytest.raises(ExternalSourceError, match="blocked"):
        inspect_external_source(symlink)

    marker_link = tmp_path / "marker-link"
    marker_link.mkdir()
    (marker_link / "sumo-source.yaml").symlink_to((SUMO_FIXTURE / "sumo-source.yaml").resolve())
    blocked_marker = discover_external_sources(marker_link)
    assert blocked_marker.status is DiscoveryReportStatus.BLOCKED
    sumo = next(item for item in blocked_marker.results if item.adapter_id == "sumo_results_v1")
    assert sumo.status is DiscoveryStatus.BLOCKED
    assert sumo.unsafe_markers == ["sumo-source.yaml"]


def test_explicit_adapter_must_exist_and_match_markers(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")

    with pytest.raises(ExternalSourceError, match="unknown external-source adapter"):
        inspect_external_source(package, adapter_id="invented")
    with pytest.raises(ExternalSourceError, match="did not safely match"):
        inspect_external_source(package, adapter_id="sumo_results_v1")


def test_sumo_inspection_is_deterministic_path_free_and_non_mutating(tmp_path: Path) -> None:
    package = tmp_path / "public-sumo"
    shutil.copytree(SUMO_FIXTURE, package)
    before = _inventory(package)

    first = inspect_external_source(package)
    second = inspect_external_source(package)

    assert first.adapter_id == "sumo_results_v1"
    assert first.validation.outcome is ValidationOutcome.ACCEPTED_WITH_WARNINGS
    assert first.validation.accepted_for_declared_import
    assert first.validation.output_counts == {
        "canonical_trips": 127,
        "source_summary_steps": 1800,
        "source_trip_observations": 142,
    }
    assert first.conversion.level is ConversionLevel.PARTIAL_CANONICAL
    provenance = {item.key: item for item in first.observed_provenance}
    assert provenance["licence_spdx"].status is SemanticStatus.CONFIRMED
    assert provenance["redistribution_allowed"].value is True
    assert len(first.validation.source_fingerprint or "") == 64
    assert first.fingerprint() == second.fingerprint()
    assert first.canonical_json() == second.canonical_json()
    assert str(package.resolve()) not in first.canonical_json()
    assert before == _inventory(package)


def test_tos_inspection_retains_unknown_rights_and_source_summary_boundary(
    tmp_path: Path,
) -> None:
    package = write_tos_package(tmp_path / "tos-private")
    before = _inventory(package)

    inspection = inspect_external_source(package, deep=True)

    assert inspection.adapter_id == "tos_data_read_only"
    assert inspection.validation.outcome is ValidationOutcome.ACCEPTED_WITH_WARNINGS
    assert inspection.validation.accepted_for_declared_import
    assert inspection.validation.output_counts["evaluation_rows"] == 2
    assert inspection.conversion.level is ConversionLevel.AGGREGATE_SUMMARY
    assert not inspection.conversion.canonical_outputs
    provenance = {item.key: item for item in inspection.observed_provenance}
    assert provenance["package_fingerprint"].status is SemanticStatus.CONFIRMED
    assert provenance["licence_statement"].status is SemanticStatus.UNKNOWN
    assert provenance["redistribution_permission"].status is SemanticStatus.UNKNOWN
    assert provenance["licence_statement"].value is None
    assert {item.code for item in inspection.blockers} >= {
        "TOS_DIRECT_LAUNCH_BLOCKED",
        "TOS_CANONICAL_TASK_CONVERSION_BLOCKED",
        "TOS_PUBLICATION_PERMISSION_UNKNOWN",
    }
    assert str(package.resolve()) not in inspection.canonical_json()
    assert before == _inventory(package)


def test_rejected_source_still_returns_typed_validation_without_conversion_claim(
    tmp_path: Path,
) -> None:
    package = tmp_path / "broken-sumo"
    shutil.copytree(SUMO_FIXTURE, package)
    (package / "tripinfo.xml").write_text("<broken>", encoding="utf-8")

    inspection = inspect_external_source(package)

    assert inspection.validation.outcome is ValidationOutcome.REJECTED
    assert not inspection.validation.accepted_for_declared_import
    assert inspection.validation.output_counts["canonical_trips"] == 0
    assert inspection.conversion.level is ConversionLevel.PARTIAL_CANONICAL
    assert "SUMO_FILE_CHECKSUM_MISMATCH" in inspection.validation.finding_codes
