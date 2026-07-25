"""Adversarial evidence for the controlled osmium PBF-to-OSM-XML decode.

Tests needing the real decoder are skipped when osmium is absent, so the suite
stays runnable offline without ever faking a decode.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.network_decode import (
    MIN_DECODED_BYTES,
    OSMIUM_FIXED_ARGUMENTS,
    PBF_HEADER_MARKER,
    SUPPORTED_OSMIUM_MAJOR,
    NetworkDecodeCommandReceipt,
    NetworkDecodeError,
    OsmDecodeReceipt,
    OsmiumToolIdentity,
    decode_pbf_to_osm_xml,
    discover_osmium,
    is_pbf,
    osmium_identity,
    read_source_header,
)


def _build_synthetic_osm(node_count: int = 40) -> str:
    """Build a labelled synthetic OSM XML document.

    Deliberately larger than the reviewed truncation floor so the fixture
    exercises a real decode without weakening that safety check.
    """

    nodes = [
        f'  <node id="{index}" lat="{53.4700 + index * 0.0005:.6f}" '
        f'lon="{-2.2500 + index * 0.0005:.6f}" version="1"/>'
        for index in range(1, node_count + 1)
    ]
    ways = [
        f'  <way id="{100 + index}" version="1"><nd ref="{index}"/>'
        f'<nd ref="{index + 1}"/><tag k="highway" v="primary"/></way>'
        for index in range(1, node_count)
    ]
    body = "\n".join([*nodes, *ways])
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        '<osm version="0.6" generator="traffictwin-synthetic-fixture">\n'
        f"{body}\n</osm>\n"
    )


SYNTHETIC_OSM = _build_synthetic_osm()


def _decoder_available() -> bool:
    if discover_osmium() is None:
        return False
    try:
        osmium_identity()
    except NetworkDecodeError:
        return False
    return True


requires_osmium = pytest.mark.skipif(
    not _decoder_available(),
    reason=f"osmium-tool {SUPPORTED_OSMIUM_MAJOR}x is not installed",
)


def _fake_pbf(tmp_path: Path, name: str = "extract.osm.pbf") -> Path:
    """A PBF-framed placeholder: enough to be recognised, not a real extract."""

    target = tmp_path / name
    target.write_bytes(b"\x00\x00\x00\x0d" + PBF_HEADER_MARKER + b"\x18\x00" + b"\x00" * 256)
    return target


def _real_pbf(tmp_path: Path) -> Path:
    """Build a genuine tiny PBF by round-tripping synthetic XML through osmium."""

    source = tmp_path / "tiny.osm"
    source.write_text(SYNTHETIC_OSM, encoding="utf-8")
    target = tmp_path / "tiny.osm.pbf"
    import subprocess

    executable = discover_osmium()
    assert executable is not None
    subprocess.run(  # noqa: S603 - fixed argv in a test fixture
        [str(executable), "cat", "--output-format", "pbf", "--output", str(target), str(source)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return target


class TestFrozenDecoder:
    def test_the_argument_vector_is_frozen_and_uses_placeholders(self) -> None:
        assert OSMIUM_FIXED_ARGUMENTS[0] == "cat"
        assert "<input>" in OSMIUM_FIXED_ARGUMENTS
        assert "<output>" in OSMIUM_FIXED_ARGUMENTS

    def test_the_decoder_applies_no_content_selection(self) -> None:
        # A filter, bbox, or tag argument would turn a format conversion into a
        # scientific decision hidden in a conversion step.
        joined = " ".join(OSMIUM_FIXED_ARGUMENTS)
        for forbidden in ("tags-filter", "extract", "--bbox", "--polygon", "-t ", "filter"):
            assert forbidden not in joined

    def test_a_receipt_recording_a_different_decoder_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exact frozen decoder"):
            NetworkDecodeCommandReceipt(
                reported_version="1.19.1",
                argument_shape=("cat", "--tags-filter", "w/highway"),
                exit_code=0,
                started_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                completed_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                duration_s=Decimal("0"),
            )

    def test_a_receipt_containing_a_private_path_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="private paths"):
            NetworkDecodeCommandReceipt(
                reported_version="1.19.1",
                argument_shape=OSMIUM_FIXED_ARGUMENTS,
                exit_code=0,
                started_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                completed_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                duration_s=Decimal("0"),
                error_lines=("Error reading /Users/someone/private/extract.pbf",),
            )

    def test_a_receipt_with_reversed_times_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must not run backwards"):
            NetworkDecodeCommandReceipt(
                reported_version="1.19.1",
                argument_shape=OSMIUM_FIXED_ARGUMENTS,
                exit_code=0,
                started_at_utc=datetime(2026, 7, 25, 10, tzinfo=UTC),
                completed_at_utc=datetime(2026, 7, 25, 9, tzinfo=UTC),
                duration_s=Decimal("0"),
            )


class TestToolVersionDrift:
    def test_a_non_reviewed_major_version_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="reviewed 1.x decoder"):
            OsmiumToolIdentity(reported_version="2.0.0", executable_sha256="a" * 64)

    def test_the_reviewed_version_is_accepted(self) -> None:
        identity = OsmiumToolIdentity(reported_version="1.19.1", executable_sha256="a" * 64)
        assert identity.reported_version.startswith(SUPPORTED_OSMIUM_MAJOR)

    def test_the_licence_note_records_execution_not_linking(self) -> None:
        identity = OsmiumToolIdentity(reported_version="1.19.1", executable_sha256="a" * 64)
        assert "executed, never linked" in identity.licence_note


class TestFramingDetection:
    def test_a_pbf_is_detected(self, tmp_path: Path) -> None:
        assert is_pbf(_fake_pbf(tmp_path)) is True

    def test_osm_xml_is_not_detected_as_pbf(self, tmp_path: Path) -> None:
        target = tmp_path / "a.osm"
        target.write_text(SYNTHETIC_OSM, encoding="utf-8")
        assert is_pbf(target) is False

    def test_decoding_a_non_pbf_is_refused(self, tmp_path: Path) -> None:
        source = tmp_path / "a.osm"
        source.write_text(SYNTHETIC_OSM, encoding="utf-8")
        with pytest.raises(NetworkDecodeError, match="SOURCE_NOT_PBF"):
            decode_pbf_to_osm_xml(source, tmp_path / "out.osm.xml")


class TestPathAndBoundRefusals:
    def test_a_symlinked_source_is_refused(self, tmp_path: Path) -> None:
        real = _fake_pbf(tmp_path)
        link = tmp_path / "link.osm.pbf"
        link.symlink_to(real)
        with pytest.raises(NetworkDecodeError, match="SOURCE_PATH_REFUSED"):
            decode_pbf_to_osm_xml(link, tmp_path / "out.osm.xml")

    def test_a_missing_source_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(NetworkDecodeError, match="SOURCE_PATH_REFUSED"):
            decode_pbf_to_osm_xml(tmp_path / "absent.osm.pbf", tmp_path / "out.osm.xml")

    def test_an_existing_destination_is_never_replaced(self, tmp_path: Path) -> None:
        source = _fake_pbf(tmp_path)
        destination = tmp_path / "out.osm.xml"
        destination.write_text("existing", encoding="utf-8")
        with pytest.raises(NetworkDecodeError, match="DESTINATION_EXISTS"):
            decode_pbf_to_osm_xml(source, destination)
        assert destination.read_text(encoding="utf-8") == "existing"

    def test_a_missing_destination_directory_is_refused(self, tmp_path: Path) -> None:
        source = _fake_pbf(tmp_path)
        with pytest.raises(NetworkDecodeError, match="DESTINATION_INVALID"):
            decode_pbf_to_osm_xml(source, tmp_path / "absent" / "out.osm.xml")

    def test_an_oversized_source_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from traffictwin.integration.manchester import network_decode

        monkeypatch.setattr(network_decode, "MAX_PBF_INPUT_BYTES", 16)
        with pytest.raises(NetworkDecodeError, match="SOURCE_TOO_LARGE"):
            decode_pbf_to_osm_xml(_fake_pbf(tmp_path), tmp_path / "out.osm.xml")

    def test_insufficient_disk_space_refuses_before_starting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from traffictwin.integration.manchester import network_decode

        monkeypatch.setattr(network_decode, "DECODE_EXPANSION_HEADROOM", 10**12)
        with pytest.raises(NetworkDecodeError, match="INSUFFICIENT_DISK_SPACE"):
            decode_pbf_to_osm_xml(_fake_pbf(tmp_path), tmp_path / "out.osm.xml")


class TestReceiptContract:
    def test_the_receipt_declares_conversion_only(self) -> None:
        fields = OsmDecodeReceipt.model_fields
        assert fields["conversion_only"].default is True
        assert fields["content_filtered"].default is False
        assert fields["bounding_box_clipped"].default is False
        assert fields["simplified"].default is False
        assert fields["road_classes_selected"].default is False

    def test_the_receipt_keeps_the_artifact_private_and_uncommitted(self) -> None:
        fields = OsmDecodeReceipt.model_fields
        assert fields["publication_class"].default == "private"
        assert fields["committed_to_git"].default is False

    def test_the_receipt_keeps_the_capability_planned(self) -> None:
        assert OsmDecodeReceipt.model_fields["capability_status"].default == "planned"

    def test_a_forged_receipt_claiming_filtering_is_refused(self, tmp_path: Path) -> None:
        payload: dict[str, Any] = {
            "source_sha256": "a" * 64,
            "source_bytes": 10,
            "decoded_sha256": "b" * 64,
            "decoded_bytes": MIN_DECODED_BYTES,
            "source_header": {},
            "tool": {"reported_version": "1.19.1", "executable_sha256": "c" * 64},
            "command": {
                "reported_version": "1.19.1",
                "argument_shape": list(OSMIUM_FIXED_ARGUMENTS),
                "exit_code": 0,
                "started_at_utc": "2026-07-25T00:00:00Z",
                "completed_at_utc": "2026-07-25T00:00:01Z",
                "duration_s": "1",
            },
            "content_filtered": True,
        }
        with pytest.raises(ValidationError):
            OsmDecodeReceipt.model_validate_json(json.dumps(payload))


@requires_osmium
class TestRealDecoder:
    def test_the_installed_decoder_is_the_reviewed_major_version(self) -> None:
        identity = osmium_identity()
        assert identity.reported_version.startswith(SUPPORTED_OSMIUM_MAJOR)
        assert identity.executable_name == "osmium"
        assert identity.libosmium_version is not None

    def test_a_real_pbf_decodes_to_osm_xml(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        destination = tmp_path / "decoded.osm.xml"
        receipt = decode_pbf_to_osm_xml(source, destination)
        assert destination.is_file()
        assert destination.read_bytes().lstrip().startswith(b"<?xml")
        assert b"<osm" in destination.read_bytes()[:512]
        assert receipt.command.exit_code == 0
        assert receipt.decoded_bytes == destination.stat().st_size

    def test_the_decode_preserves_every_way_and_node(self, tmp_path: Path) -> None:
        # Conversion only: nothing is filtered out on the way through.
        source = _real_pbf(tmp_path)
        destination = tmp_path / "decoded.osm.xml"
        decode_pbf_to_osm_xml(source, destination)
        decoded = destination.read_bytes()
        assert decoded.count(b"<node") == SYNTHETIC_OSM.count("<node")
        assert decoded.count(b"<way") == SYNTHETIC_OSM.count("<way")
        assert b'k="highway"' in decoded

    def test_the_decode_is_deterministic(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        first = tmp_path / "a.osm.xml"
        second = tmp_path / "b.osm.xml"
        one = decode_pbf_to_osm_xml(source, first)
        two = decode_pbf_to_osm_xml(source, second)
        assert one.decoded_sha256 == two.decoded_sha256
        assert first.read_bytes() == second.read_bytes()

    def test_a_failed_decode_leaves_no_partial_artifact(self, tmp_path: Path) -> None:
        # PBF framing present but the body is not a valid PBF, so osmium fails.
        source = _fake_pbf(tmp_path)
        destination = tmp_path / "out.osm.xml"
        with pytest.raises(NetworkDecodeError):
            decode_pbf_to_osm_xml(source, destination)
        assert not destination.exists()
        assert not any(child.name.startswith(".osm-decode-") for child in tmp_path.iterdir())

    def test_no_private_path_appears_in_the_receipt(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        receipt = decode_pbf_to_osm_xml(source, tmp_path / "decoded.osm.xml")
        serialised = receipt.canonical_json()
        assert str(tmp_path) not in serialised
        assert "/Users/" not in serialised
        assert "/private/" not in serialised

    def test_the_source_header_is_read_from_the_file_not_the_filename(self, tmp_path: Path) -> None:
        executable = discover_osmium()
        assert executable is not None
        header = read_source_header(executable, _real_pbf(tmp_path))
        assert header.read_from_source_header is True
        assert header.generator is not None

    def test_the_receipt_binds_both_input_and_output_digests(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        destination = tmp_path / "decoded.osm.xml"
        receipt = decode_pbf_to_osm_xml(source, destination)
        from traffictwin.integration.manchester.models import sha256_hex

        assert receipt.source_sha256 == sha256_hex(source.read_bytes())
        assert receipt.decoded_sha256 == sha256_hex(destination.read_bytes())
