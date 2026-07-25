"""Evidence that the baseline-network CLI stays bounded and honest."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app

runner = CliRunner()


def _run(*args: str) -> tuple[int, str]:
    """Invoke the CLI and return the exit code with both streams combined.

    Refusals are written to stderr, so a stdout-only assertion would silently
    pass against an empty string.
    """

    result = runner.invoke(app, list(args))
    streams = [result.stdout]
    with contextlib.suppress(ValueError):  # stderr may not be captured separately
        streams.append(result.stderr)
    return result.exit_code, "".join(stream for stream in streams if stream)


class TestScopeCommand:
    def test_scope_reports_the_approved_baseline_and_filter(self) -> None:
        code, output = _run("integration", "manchester", "network", "scope")
        assert code == 0
        assert "greater_manchester_combined_authority (E47000001)" in output
        assert "manchester_local_authority (E08000003)" in output
        assert "sub_area_is_second_network: false" in output

    def test_scope_reports_required_area_inclusion(self) -> None:
        _code, output = _run("integration", "manchester", "network", "scope")
        assert "required_area: manchester_city_centre inside_baseline=true" in output
        assert "required_area: university_of_manchester inside_baseline=true" in output

    def test_scope_reports_dft_partial_coverage_and_no_zero_fill(self) -> None:
        _code, output = _run("integration", "manchester", "network", "scope")
        assert "dft_coverage: partial (manchester_local_authority only)" in output
        assert "dft_uncovered_state: unavailable" in output
        assert "dft_uncovered_is_zero: false" in output

    def test_scope_keeps_the_capability_planned(self) -> None:
        _code, output = _run("integration", "manchester", "network", "scope")
        assert "capability_status: planned" in output

    def test_scope_json_is_machine_readable(self) -> None:
        code, output = _run("integration", "manchester", "network", "scope", "--format", "json")
        assert code == 0
        payload = json.loads(output)
        assert payload["baseline_scope"] == "greater_manchester_combined_authority"
        assert payload["capability_status"] == "planned"

    def test_scope_labels_the_envelope_as_derived(self) -> None:
        _code, output = _run("integration", "manchester", "network", "scope")
        assert "envelope_derivation: derived_from_display_geometry" in output


class TestAcquireRefusals:
    def test_acquire_refuses_without_explicit_operator_confirmation(self, tmp_path: Path) -> None:
        code, output = _run("integration", "manchester", "network", "acquire", str(tmp_path))
        assert code == 2
        assert "explicit operator authorisation" in output

    def test_acquire_help_exposes_no_url_or_host_option(self) -> None:
        _code, output = _run("integration", "manchester", "network", "acquire", "--help")
        lowered = output.lower()
        for forbidden in ("--url", "--host", "--endpoint", "--mirror"):
            assert forbidden not in lowered


class TestBuildRefusals:
    def test_build_help_exposes_no_command_or_flag_option(self) -> None:
        _code, output = _run("integration", "manchester", "network", "build", "--help")
        lowered = output.lower()
        for forbidden in ("--arg", "--flag", "--option", "--executable", "--tool"):
            assert forbidden not in lowered

    def test_building_a_pbf_extract_refuses_with_the_named_decode_step(
        self, tmp_path: Path
    ) -> None:
        extract = tmp_path / "gm.osm.pbf"
        extract.write_bytes(b"\x00\x00\x00\x0d\x0a\x09OSMHeader\x18\x00" + b"\x00" * 256)
        code, output = _run(
            "integration",
            "manchester",
            "network",
            "build",
            str(tmp_path),
            "--extract",
            str(extract),
            "--network-id",
            "gm-pbf",
        )
        assert code == 1
        assert "OSM_PBF_DECODE_UNAVAILABLE" in output


class TestListAndStatus:
    def test_list_reports_an_empty_workspace_without_pretending(self, tmp_path: Path) -> None:
        code, output = _run("integration", "manchester", "network", "list", str(tmp_path))
        assert code == 0
        assert "no accepted baseline-network candidate exists" in output
        assert "capability_status: planned" in output

    def test_status_reports_planned_and_foundation_only(self) -> None:
        code, output = _run("integration", "manchester", "network", "status")
        assert code == 0
        assert "capability_status: planned" in output
        assert "practical_state: foundation_only" in output
        assert "gate: Gate-D step 1 (network binding) only" in output

    def test_status_keeps_calibration_and_comparison_unavailable(self) -> None:
        _code, output = _run("integration", "manchester", "network", "status")
        assert "calibration_available: false" in output
        assert "comparison_available: false" in output
        assert "live_traffic_available: false" in output

    def test_status_lists_every_map_matching_blocker(self) -> None:
        _code, output = _run("integration", "manchester", "network", "status")
        for blocker in (
            "MANCHESTER_NETWORK_LICENCE_UNAPPROVED",
            "MANCHESTER_NETWORK_NOT_REVIEWED",
            "MAP_MATCH_POLICY_UNAPPROVED",
            "REAL_SOURCE_GATE_B_UNACCEPTED",
        ):
            assert f"map_matching_blocker: {blocker}" in output

    def test_status_states_the_dft_coverage_limit(self) -> None:
        _code, output = _run("integration", "manchester", "network", "status")
        assert "Manchester local authority only" in output
        assert "never zero" in output


class TestVerifyRefusals:
    def test_verifying_an_absent_candidate_fails_closed(self, tmp_path: Path) -> None:
        code, output = _run(
            "integration",
            "manchester",
            "network",
            "verify",
            str(tmp_path),
            "--network-id",
            "absent-network",
        )
        assert code == 1
        assert "NETWORK_DIR_INVALID" in output or "BINDING_MISSING" in output
