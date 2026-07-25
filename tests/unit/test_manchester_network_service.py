"""Evidence that the baseline-network service stays read-only and honest."""

from __future__ import annotations

import inspect
from pathlib import Path

from traffictwin.integration.manchester import network_service
from traffictwin.integration.manchester.network_service import (
    NETWORKS_DIRECTORY_NAME,
    baseline_network_status,
    list_network_candidates,
    toolchain_availability,
)


class TestServiceIsReadOnly:
    def test_the_service_performs_no_network_or_subprocess_work(self) -> None:
        status = baseline_network_status()
        assert status.performs_network_access is False
        assert status.performs_subprocess_execution is False

    def test_the_service_module_imports_no_transport_or_subprocess(self) -> None:
        source = inspect.getsource(network_service)
        for forbidden in ("import subprocess", "import httpx", "BoundedHttpClient"):
            assert forbidden not in source, f"service must not reference {forbidden}"

    def test_the_service_exposes_no_acquire_or_build_entry_point(self) -> None:
        public = {name for name in dir(network_service) if not name.startswith("_")}
        for forbidden in ("acquire_osm_extract_snapshot", "build_baseline_network"):
            assert forbidden not in public


class TestHonestStatus:
    def test_status_keeps_the_capability_planned_and_foundation_only(self) -> None:
        status = baseline_network_status()
        assert status.capability_status == "planned"
        assert status.practical_state == "foundation_only"
        assert status.gate == "Gate-D step 1 (network binding) only"

    def test_status_refuses_calibration_comparison_and_live_claims(self) -> None:
        status = baseline_network_status()
        assert status.calibration_available is False
        assert status.comparison_available is False
        assert status.live_traffic_available is False

    def test_status_retains_every_map_matching_blocker(self) -> None:
        status = baseline_network_status()
        assert status.map_matching_preflight.blockers == (
            "MANCHESTER_NETWORK_LICENCE_UNAPPROVED",
            "MANCHESTER_NETWORK_NOT_REVIEWED",
            "MAP_MATCH_POLICY_UNAPPROVED",
            "REAL_SOURCE_GATE_B_UNACCEPTED",
        )

    def test_status_states_the_dft_coverage_limit(self) -> None:
        reasons = " ".join(baseline_network_status().unavailable_reasons)
        assert "Manchester local authority only" in reasons
        assert "never zero" in reasons

    def test_status_reports_an_empty_workspace_explicitly(self, tmp_path: Path) -> None:
        status = baseline_network_status(tmp_path)
        assert status.candidate_count == 0
        assert any(
            "No accepted baseline-network candidate" in r for r in status.unavailable_reasons
        )

    def test_status_carries_the_approved_scope(self) -> None:
        scope = baseline_network_status().scope
        assert scope.baseline_scope == "greater_manchester_combined_authority"
        assert scope.sub_area_scope == "manchester_local_authority"
        assert scope.sub_area_is_filter is True


class TestCandidateListing:
    def test_a_missing_root_lists_nothing_rather_than_failing(self, tmp_path: Path) -> None:
        assert list_network_candidates(tmp_path / "absent") == ()

    def test_a_symlinked_root_lists_nothing(self, tmp_path: Path) -> None:
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real)
        assert list_network_candidates(link) == ()

    def test_an_unverifiable_candidate_is_omitted_not_shown_healthy(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken-network"
        broken.mkdir()
        (broken / "binding.json").write_text("{ not json", encoding="utf-8")
        assert list_network_candidates(tmp_path) == ()

    def test_the_networks_directory_name_is_stable(self) -> None:
        assert NETWORKS_DIRECTORY_NAME == "networks"


class TestToolchainReporting:
    def test_toolchain_availability_never_raises(self) -> None:
        availability = toolchain_availability()
        assert availability.required_version_prefix == "1.27."
        if availability.available:
            assert availability.reported_version is not None
            assert availability.reported_version.startswith("1.27.")
        else:
            assert availability.blocker is not None
