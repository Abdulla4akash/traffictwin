"""Adversarial evidence for the deterministic SUMO baseline-network build.

Tests that need the real toolchain are skipped when SUMO 1.27.x is absent, so
the suite stays runnable offline without ever faking a build.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.integration.manchester.network_acquisition import (
    OSM_EXTRACT_DATA_CUTOFF_DATE,
    OSM_REFERENCE_DATE,
    OsmExtractIdentity,
)
from traffictwin.integration.manchester.network_build import (
    NETCONVERT_FIXED_ARGUMENTS,
    SUPPORTED_SUMO_VERSION_PREFIX,
    ManchesterBaselineNetworkBinding,
    NetconvertToolIdentity,
    NetworkBuildCommandReceipt,
    NetworkBuildError,
    NetworkBuildRequest,
    build_baseline_network,
    canonical_network_bytes,
    check_builder_input_format,
    discover_netconvert,
    load_binding,
    netconvert_identity,
    validate_network_bytes,
)
from traffictwin.integration.manchester.network_scope import baseline_scope_decision

SYNTHETIC_OSM = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="traffictwin-synthetic-fixture">
 <node id="1" lat="53.4600" lon="-2.2500" version="1"/>
 <node id="2" lat="53.4700" lon="-2.2400" version="1"/>
 <node id="3" lat="53.4800" lon="-2.2300" version="1"/>
 <node id="4" lat="53.4850" lon="-2.2250" version="1"/>
 <way id="100" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/>
  <tag k="highway" v="primary"/></way>
 <way id="101" version="1"><nd ref="2"/><nd ref="4"/>
  <tag k="highway" v="residential"/></way>
</osm>
"""


def _toolchain_available() -> bool:
    executable = discover_netconvert()
    if executable is None:
        return False
    try:
        netconvert_identity()
    except NetworkBuildError:
        return False
    return True


requires_sumo = pytest.mark.skipif(
    not _toolchain_available(),
    reason=f"Eclipse SUMO {SUPPORTED_SUMO_VERSION_PREFIX}x netconvert is not installed",
)


def _extract_identity() -> OsmExtractIdentity:
    return OsmExtractIdentity(
        extract_sha256="a" * 64,
        extract_md5="b" * 32,
        extract_bytes=1_500_000,
        reference_date=OSM_REFERENCE_DATE,
        provider_checksum_verified=True,
        provider_checksum_source="operator_declared",
        synthetic=True,
    )


def _request(network_id: str = "gm-test") -> NetworkBuildRequest:
    return NetworkBuildRequest(network_id=network_id, extract=_extract_identity(), synthetic=True)


def _osm_file(tmp_path: Path) -> Path:
    source = tmp_path / "synthetic.osm"
    source.write_text(SYNTHETIC_OSM, encoding="utf-8")
    return source


def _output_root(tmp_path: Path) -> Path:
    root = tmp_path / "networks"
    root.mkdir()
    return root


def _network_document(orig_boundary: bytes) -> bytes:
    """Build a minimal network-shaped document above the reviewed size floor."""

    header = (
        b"<net>"
        b'<location netOffset="0.00,0.00" convBoundary="0.00,0.00,10.00,10.00" '
        b'origBoundary="' + orig_boundary + b'" '
        b'projParameter="+proj=utm +zone=30 +ellps=WGS84"/>'
    )
    body = b"<edge id='a'/><junction id='j'/><connection from='a'/>" * 64
    return header + body + b"</net>"


class TestFrozenBuilder:
    def test_the_request_exposes_no_command_surface(self) -> None:
        fields = set(NetworkBuildRequest.model_fields)
        forbidden = {
            "arguments",
            "argv",
            "command",
            "executable",
            "flags",
            "options",
            "tool_path",
            "typemap",
        }
        assert not (fields & forbidden), f"request exposes a command surface: {fields & forbidden}"

    def test_the_argument_vector_is_frozen_and_uses_placeholders(self) -> None:
        assert "<input>" in NETCONVERT_FIXED_ARGUMENTS
        assert "<output>" in NETCONVERT_FIXED_ARGUMENTS
        assert NETCONVERT_FIXED_ARGUMENTS[0] == "--osm-files"

    def test_a_receipt_recording_a_different_builder_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exact frozen builder"):
            NetworkBuildCommandReceipt(
                reported_version="1.27.1",
                argument_shape=("--osm-files", "<input>", "--evil"),
                exit_code=0,
                started_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                completed_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                duration_s=Decimal("0"),
            )

    def test_a_receipt_containing_a_private_path_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="private paths"):
            NetworkBuildCommandReceipt(
                reported_version="1.27.1",
                argument_shape=NETCONVERT_FIXED_ARGUMENTS,
                exit_code=0,
                started_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                completed_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                duration_s=Decimal("0"),
                warning_lines=("Warning: could not read /Users/someone/secret.osm",),
            )

    def test_a_receipt_with_reversed_times_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must not run backwards"):
            NetworkBuildCommandReceipt(
                reported_version="1.27.1",
                argument_shape=NETCONVERT_FIXED_ARGUMENTS,
                exit_code=0,
                started_at_utc=datetime(2026, 7, 25, 10, tzinfo=UTC),
                completed_at_utc=datetime(2026, 7, 25, 9, tzinfo=UTC),
                duration_s=Decimal("0"),
            )


class TestBuilderInputFormat:
    def test_a_pbf_container_is_refused_with_a_named_decode_step(self, tmp_path: Path) -> None:
        # Measured: netconvert 1.27.1 reads OSM XML and fails on PBF with an
        # opaque XML parse error.  The builder names the gap instead.
        pbf = tmp_path / "extract.osm.pbf"
        pbf.write_bytes(b"\x00\x00\x00\x0d\x0a\x09OSMHeader\x18\x00" + b"\x00" * 128)
        with pytest.raises(NetworkBuildError, match="OSM_PBF_DECODE_UNAVAILABLE"):
            check_builder_input_format(pbf)

    def test_osm_xml_is_accepted_as_builder_input(self, tmp_path: Path) -> None:
        check_builder_input_format(_osm_file(tmp_path))

    def test_a_pbf_extract_never_reaches_netconvert(self, tmp_path: Path) -> None:
        pbf = tmp_path / "extract.osm.pbf"
        pbf.write_bytes(b"\x00\x00\x00\x0d\x0a\x09OSMHeader\x18\x00" + b"\x00" * 128)
        root = _output_root(tmp_path)
        with pytest.raises(NetworkBuildError, match="OSM_PBF_DECODE_UNAVAILABLE"):
            build_baseline_network(root, pbf, _request("gm-pbf"))
        assert not (root / "gm-pbf").exists()


class TestToolVersionDrift:
    def test_a_non_reviewed_version_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="reviewed 1.27.x toolchain"):
            NetconvertToolIdentity(reported_version="1.26.0", executable_sha256="a" * 64)

    def test_the_reviewed_version_is_accepted(self) -> None:
        identity = NetconvertToolIdentity(reported_version="1.27.1", executable_sha256="a" * 64)
        assert identity.reported_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX)

    def test_the_build_request_must_bind_the_reviewed_extract_dates(self) -> None:
        stale = OsmExtractIdentity(
            extract_sha256="a" * 64,
            extract_md5="b" * 32,
            extract_bytes=1_500_000,
            reference_date=date(2020, 1, 1),
            provider_checksum_verified=True,
            provider_checksum_source="operator_declared",
            synthetic=True,
        )
        with pytest.raises(ValidationError, match="reviewed extract reference date"):
            NetworkBuildRequest(network_id="gm", extract=stale, synthetic=True)


class TestCanonicalIdentity:
    def test_comments_are_removed_from_the_identity_digest(self) -> None:
        first = b"<!-- generated on 2026-07-25T00:00:00 -->\n<net><edge id='a'/></net>\n"
        second = b"<!-- generated on 2026-07-25T11:11:11 -->\n<net><edge id='a'/></net>\n"
        assert first != second
        assert canonical_network_bytes(first) == canonical_network_bytes(second)

    def test_a_structural_change_changes_the_identity_digest(self) -> None:
        first = b"<!-- banner -->\n<net><edge id='a'/></net>\n"
        second = b"<!-- banner -->\n<net><edge id='b'/></net>\n"
        assert canonical_network_bytes(first) != canonical_network_bytes(second)

    def test_trailing_whitespace_does_not_change_identity(self) -> None:
        first = b"<net>\n  <edge id='a'/>   \n</net>\n"
        second = b"<net>\n  <edge id='a'/>\n</net>\n"
        assert canonical_network_bytes(first) == canonical_network_bytes(second)


class TestValidationRefusals:
    def test_an_empty_network_is_refused(self) -> None:
        with pytest.raises(NetworkBuildError, match="NETWORK_EMPTY"):
            validate_network_bytes(b"", scope=baseline_scope_decision())

    def test_a_non_network_document_is_refused(self) -> None:
        payload = b"<html><body>not a network</body></html>" + b" " * 2_000
        with pytest.raises(NetworkBuildError, match="NETWORK_CORRUPT"):
            validate_network_bytes(payload, scope=baseline_scope_decision())

    def test_a_network_without_a_location_element_is_refused(self) -> None:
        payload = b"<net>" + b"<edge id='a'/>" * 100 + b"</net>"
        with pytest.raises(NetworkBuildError, match="NETWORK_LOCATION_MISSING"):
            validate_network_bytes(payload, scope=baseline_scope_decision())

    def test_a_network_outside_the_required_areas_is_rejected(self) -> None:
        # A valid-looking network covering Leeds, not Manchester.
        result = validate_network_bytes(
            _network_document(b"-1.60,53.75,-1.50,53.85"), scope=baseline_scope_decision()
        )
        assert result.status == "rejected"
        assert any(
            finding.startswith("REQUIRED_AREA_OUTSIDE_NETWORK") for finding in result.findings
        )

    def test_a_network_covering_the_required_areas_is_accepted(self) -> None:
        result = validate_network_bytes(
            _network_document(b"-2.75,53.30,-1.89,53.70"), scope=baseline_scope_decision()
        )
        assert result.status == "accepted"
        assert all(area.inside_network_boundary for area in result.required_areas)

    def test_an_accepted_validation_cannot_be_forged_without_coverage(self) -> None:
        result = validate_network_bytes(
            _network_document(b"-2.75,53.30,-1.89,53.70"), scope=baseline_scope_decision()
        )
        payload_json: dict[str, Any] = json.loads(result.canonical_json())
        payload_json["status"] = "accepted"
        payload_json["required_areas"][0]["inside_network_boundary"] = False
        with pytest.raises(ValidationError, match="must cover every required area"):
            type(result).model_validate_json(json.dumps(payload_json))


@requires_sumo
class TestRealToolchainBuild:
    def test_the_installed_toolchain_is_the_reviewed_version(self) -> None:
        identity = netconvert_identity()
        assert identity.reported_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX)
        assert identity.executable_name == "netconvert"

    def test_a_synthetic_build_produces_a_validated_binding(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        assert binding.validation.status == "accepted"
        assert binding.validation.structure.edge_count > 0
        assert binding.validation.structure.junction_count > 0
        assert binding.command.exit_code == 0

    def test_the_projection_is_read_from_the_network_not_asserted(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        location = binding.validation.location
        assert location.read_from_network is True
        assert location.rederived_by_traffictwin is False
        assert "+proj=utm" in location.proj_parameter
        assert "zone=30" in location.proj_parameter

    def test_rebuilding_reproduces_the_semantic_identity_not_the_raw_bytes(
        self, tmp_path: Path
    ) -> None:
        source = _osm_file(tmp_path)
        root = _output_root(tmp_path)
        first = build_baseline_network(root, source, _request("gm-first"))
        second = build_baseline_network(root, source, _request("gm-second"))
        assert first.network_identity_sha256 == second.network_identity_sha256
        assert first.byte_reproducible is False
        assert first.semantically_reproducible is True

    def test_the_binding_makes_no_calibration_or_execution_claim(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        assert binding.calibration_performed is False
        assert binding.comparison_performed is False
        assert binding.vec_execution_performed is False
        assert binding.live_traffic_claim is False
        assert binding.validation.validated_against_observations is False
        assert binding.capability_status == "planned"
        assert binding.gate_d_step == "network_binding_only"

    def test_the_binding_does_not_unlock_real_matching(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        assert binding.reviewed_manchester_network is True
        assert binding.accepted_for_real_matching is False

    def test_the_licence_and_attribution_are_carried(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        assert binding.licence_id == "ODbL-1.0"
        assert binding.attribution_text == "© OpenStreetMap contributors, ODbL 1.0"
        assert binding.inputs.attribution_text == binding.attribution_text

    def test_scope_is_greater_manchester_with_a_manchester_filter(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        assert binding.baseline_scope == "greater_manchester_combined_authority"
        assert binding.sub_area_filter_scope == "manchester_local_authority"

    def test_a_reload_verifies_both_digests(self, tmp_path: Path) -> None:
        root = _output_root(tmp_path)
        binding = build_baseline_network(root, _osm_file(tmp_path), _request())
        reloaded = load_binding(root / binding.network_id)
        assert reloaded.network_sha256 == binding.network_sha256
        assert reloaded.network_identity_sha256 == binding.network_identity_sha256

    def test_a_mutated_network_file_is_detected_on_reload(self, tmp_path: Path) -> None:
        root = _output_root(tmp_path)
        binding = build_baseline_network(root, _osm_file(tmp_path), _request())
        network_file = root / binding.network_id / f"{binding.network_id}.net.xml"
        network_file.write_bytes(network_file.read_bytes() + b"<!-- tampered -->")
        with pytest.raises(NetworkBuildError, match="NETWORK_MUTATED"):
            load_binding(root / binding.network_id)

    def test_a_mutated_binding_receipt_is_detected_on_reload(self, tmp_path: Path) -> None:
        root = _output_root(tmp_path)
        binding = build_baseline_network(root, _osm_file(tmp_path), _request())
        binding_file = root / binding.network_id / "binding.json"
        payload = json.loads(binding_file.read_text(encoding="utf-8"))
        payload["network_sha256"] = "c" * 64
        binding_file.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NetworkBuildError, match="NETWORK_MUTATED"):
            load_binding(root / binding.network_id)

    def test_a_semantic_only_mutation_is_still_detected(self, tmp_path: Path) -> None:
        root = _output_root(tmp_path)
        binding = build_baseline_network(root, _osm_file(tmp_path), _request())
        binding_file = root / binding.network_id / "binding.json"
        network_file = root / binding.network_id / f"{binding.network_id}.net.xml"
        tampered = network_file.read_bytes().replace(b"<edge ", b"<edge tampered='1' ", 1)
        network_file.write_bytes(tampered)
        payload = json.loads(binding_file.read_text(encoding="utf-8"))
        payload["network_sha256"] = sha256_hex(tampered)
        binding_file.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NetworkBuildError, match="NETWORK_IDENTITY_MUTATED"):
            load_binding(root / binding.network_id)

    def test_environment_warnings_are_recorded_not_suppressed(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        # netconvert emits diagnostics on stderr; whatever it says is kept.
        assert isinstance(binding.command.warning_lines, tuple)
        for line in binding.command.warning_lines:
            assert "/Users/" not in line
            assert "/private/" not in line

    def test_building_into_an_existing_destination_is_refused(self, tmp_path: Path) -> None:
        root = _output_root(tmp_path)
        source = _osm_file(tmp_path)
        build_baseline_network(root, source, _request("gm-once"))
        with pytest.raises(NetworkBuildError, match="DESTINATION_EXISTS"):
            build_baseline_network(root, source, _request("gm-once"))

    def test_a_failed_build_leaves_no_accepted_artifact(self, tmp_path: Path) -> None:
        root = _output_root(tmp_path)
        broken = tmp_path / "broken.osm"
        broken.write_text("<osm><unclosed>", encoding="utf-8")
        with pytest.raises(NetworkBuildError):
            build_baseline_network(root, broken, _request("gm-broken"))
        assert not (root / "gm-broken").exists()
        assert not any(child.name.startswith("gm-broken") for child in root.iterdir())

    def test_a_symlinked_extract_is_refused(self, tmp_path: Path) -> None:
        real = _osm_file(tmp_path)
        link = tmp_path / "link.osm"
        link.symlink_to(real)
        with pytest.raises(NetworkBuildError, match="EXTRACT_PATH_REFUSED"):
            build_baseline_network(_output_root(tmp_path), link, _request())

    def test_a_missing_output_root_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(NetworkBuildError, match="OUTPUT_ROOT_INVALID"):
            build_baseline_network(tmp_path / "absent", _osm_file(tmp_path), _request())

    def test_the_input_manifest_pins_extract_scope_and_tool(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        manifest = binding.inputs
        assert manifest.extract.extract_sha256 == _extract_identity().extract_sha256
        assert manifest.extract.extract_data_cutoff_date == OSM_EXTRACT_DATA_CUTOFF_DATE
        assert manifest.scope.baseline_scope == "greater_manchester_combined_authority"
        assert manifest.tool.reported_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX)
        assert manifest.argument_shape == NETCONVERT_FIXED_ARGUMENTS
        assert manifest.decision_record == "ADR-059"

    def test_no_private_path_appears_anywhere_in_the_binding(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        serialised = binding.canonical_json()
        assert str(tmp_path) not in serialised
        assert "/Users/" not in serialised
        assert "/private/" not in serialised

    def test_a_forged_binding_claiming_matching_acceptance_is_refused(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        payload: dict[str, Any] = json.loads(binding.canonical_json())
        payload["accepted_for_real_matching"] = True
        with pytest.raises(ValidationError):
            ManchesterBaselineNetworkBinding.model_validate_json(json.dumps(payload))

    def test_a_forged_binding_claiming_calibration_is_refused(self, tmp_path: Path) -> None:
        binding = build_baseline_network(_output_root(tmp_path), _osm_file(tmp_path), _request())
        payload: dict[str, Any] = json.loads(binding.canonical_json())
        payload["calibration_performed"] = True
        with pytest.raises(ValidationError):
            ManchesterBaselineNetworkBinding.model_validate_json(json.dumps(payload))
