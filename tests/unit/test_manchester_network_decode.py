"""Adversarial evidence for the controlled osmium PBF-to-OSM-XML decode.

Tests needing the real decoder are skipped when osmium is absent, so the suite
stays runnable offline without ever faking a decode.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import UTC, date, datetime
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
    UNSEALED_FINGERPRINT,
    DecodeSourceExpectation,
    NetworkDecodeCommandReceipt,
    NetworkDecodeError,
    OsmDecodeReceipt,
    OsmiumToolIdentity,
    argument_fingerprint,
    decode_pbf_to_osm_xml,
    discover_osmium,
    is_pbf,
    osmium_identity,
    pinned_source_expectation,
    read_source_header,
    validate_osm_xml_structure,
    verify_decoded_artifact,
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

    target = tmp_path / "tiny.osm.pbf"
    if target.is_file():
        return target  # idempotent: osmium refuses to overwrite
    source = tmp_path / "tiny.osm"
    source.write_text(SYNTHETIC_OSM, encoding="utf-8")
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
            decode_pbf_to_osm_xml(
                source, tmp_path / "out.osm.xml", allow_unpinned_source=True, synthetic=True
            )


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
            decode_pbf_to_osm_xml(source, destination, allow_unpinned_source=True, synthetic=True)
        assert destination.read_text(encoding="utf-8") == "existing"

    def test_a_missing_destination_directory_is_refused(self, tmp_path: Path) -> None:
        source = _fake_pbf(tmp_path)
        with pytest.raises(NetworkDecodeError, match="DESTINATION_INVALID"):
            decode_pbf_to_osm_xml(
                source,
                tmp_path / "absent" / "out.osm.xml",
                allow_unpinned_source=True,
                synthetic=True,
            )

    def test_an_oversized_source_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from traffictwin.integration.manchester import network_decode

        monkeypatch.setattr(network_decode, "MAX_PBF_INPUT_BYTES", 16)
        with pytest.raises(NetworkDecodeError, match="SOURCE_TOO_LARGE"):
            decode_pbf_to_osm_xml(
                _fake_pbf(tmp_path),
                tmp_path / "out.osm.xml",
                allow_unpinned_source=True,
                synthetic=True,
            )

    def test_insufficient_disk_space_refuses_before_starting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from traffictwin.integration.manchester import network_decode

        monkeypatch.setattr(network_decode, "DECODE_EXPANSION_HEADROOM", 10**12)
        with pytest.raises(NetworkDecodeError, match="INSUFFICIENT_DISK_SPACE"):
            decode_pbf_to_osm_xml(
                _fake_pbf(tmp_path),
                tmp_path / "out.osm.xml",
                allow_unpinned_source=True,
                synthetic=True,
            )


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
        receipt = decode_pbf_to_osm_xml(
            source, destination, allow_unpinned_source=True, synthetic=True
        )
        assert destination.is_file()
        assert destination.read_bytes().lstrip().startswith(b"<?xml")
        assert b"<osm" in destination.read_bytes()[:512]
        assert receipt.command.exit_code == 0
        assert receipt.decoded_bytes == destination.stat().st_size

    def test_the_decode_preserves_every_way_and_node(self, tmp_path: Path) -> None:
        # Conversion only: nothing is filtered out on the way through.
        source = _real_pbf(tmp_path)
        destination = tmp_path / "decoded.osm.xml"
        decode_pbf_to_osm_xml(source, destination, allow_unpinned_source=True, synthetic=True)
        decoded = destination.read_bytes()
        assert decoded.count(b"<node") == SYNTHETIC_OSM.count("<node")
        assert decoded.count(b"<way") == SYNTHETIC_OSM.count("<way")
        assert b'k="highway"' in decoded

    def test_the_decode_is_deterministic(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        first = tmp_path / "a.osm.xml"
        second = tmp_path / "b.osm.xml"
        one = decode_pbf_to_osm_xml(source, first, allow_unpinned_source=True, synthetic=True)
        two = decode_pbf_to_osm_xml(source, second, allow_unpinned_source=True, synthetic=True)
        assert one.decoded_sha256 == two.decoded_sha256
        assert first.read_bytes() == second.read_bytes()

    def test_a_failed_decode_leaves_no_partial_artifact(self, tmp_path: Path) -> None:
        # PBF framing present but the body is not a valid PBF, so osmium fails.
        source = _fake_pbf(tmp_path)
        destination = tmp_path / "out.osm.xml"
        with pytest.raises(NetworkDecodeError):
            decode_pbf_to_osm_xml(source, destination, allow_unpinned_source=True, synthetic=True)
        assert not destination.exists()
        assert not any(child.name.startswith(".osm-decode-") for child in tmp_path.iterdir())

    def test_no_private_path_appears_in_the_receipt(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        receipt = decode_pbf_to_osm_xml(
            source, tmp_path / "decoded.osm.xml", allow_unpinned_source=True, synthetic=True
        )
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
        receipt = decode_pbf_to_osm_xml(
            source, destination, allow_unpinned_source=True, synthetic=True
        )
        from traffictwin.integration.manchester.models import sha256_hex

        assert receipt.source_sha256 == sha256_hex(source.read_bytes())
        assert receipt.decoded_sha256 == sha256_hex(destination.read_bytes())


class TestSourceIdentityBinding:
    def test_the_pinned_expectation_keeps_the_three_dates_distinct(self) -> None:
        expectation = pinned_source_expectation()
        assert expectation.expected_data_cutoff_date != expectation.expected_retrieval_date
        assert expectation.expected_data_cutoff_date.isoformat() == "2026-07-24"
        assert expectation.expected_retrieval_date.isoformat() == "2026-07-25"
        assert expectation.expected_provider_last_modified == "Sat, 25 Jul 2026 00:29:36 GMT"

    def test_collapsing_the_cutoff_and_retrieval_dates_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must stay distinct"):
            DecodeSourceExpectation(
                expected_filename="greater-manchester-260724.osm.pbf",
                expected_sha256="a" * 64,
                expected_md5="b" * 32,
                expected_data_cutoff_date=date(2026, 7, 25),
                expected_retrieval_date=date(2026, 7, 25),
                expected_provider_last_modified="Sat, 25 Jul 2026 00:29:36 GMT",
            )

    @requires_osmium
    def test_a_source_sha_mismatch_is_refused_before_decoding(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        renamed = tmp_path / "greater-manchester-260724.osm.pbf"
        source.rename(renamed)
        with pytest.raises(NetworkDecodeError, match="SOURCE_IDENTITY_MISMATCH"):
            decode_pbf_to_osm_xml(
                renamed, tmp_path / "out.osm.xml", expectation=pinned_source_expectation()
            )
        assert not (tmp_path / "out.osm.xml").exists()

    @requires_osmium
    def test_a_provider_md5_mismatch_is_refused(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        renamed = tmp_path / "greater-manchester-260724.osm.pbf"
        source.rename(renamed)
        from traffictwin.integration.manchester.network_decode import _sha256_file

        observed, _ = _sha256_file(renamed)
        expectation = DecodeSourceExpectation(
            expected_filename="greater-manchester-260724.osm.pbf",
            expected_sha256=observed,
            expected_md5="0" * 32,
            expected_data_cutoff_date=date(2026, 7, 24),
            expected_retrieval_date=date(2026, 7, 25),
            expected_provider_last_modified="Sat, 25 Jul 2026 00:29:36 GMT",
        )
        with pytest.raises(NetworkDecodeError, match="PROVIDER_MD5_MISMATCH"):
            decode_pbf_to_osm_xml(renamed, tmp_path / "out.osm.xml", expectation=expectation)

    @requires_osmium
    def test_a_wrong_filename_is_refused(self, tmp_path: Path) -> None:
        source = _real_pbf(tmp_path)
        from traffictwin.integration.manchester.network_decode import _md5_file, _sha256_file

        observed, _ = _sha256_file(source)
        expectation = DecodeSourceExpectation(
            expected_filename="greater-manchester-260724.osm.pbf",
            expected_sha256=observed,
            expected_md5=_md5_file(source),
            expected_data_cutoff_date=date(2026, 7, 24),
            expected_retrieval_date=date(2026, 7, 25),
            expected_provider_last_modified="Sat, 25 Jul 2026 00:29:36 GMT",
        )
        with pytest.raises(NetworkDecodeError, match="SOURCE_FILENAME_MISMATCH"):
            decode_pbf_to_osm_xml(source, tmp_path / "out.osm.xml", expectation=expectation)


@requires_osmium
class TestOfflineReplay:
    def _decoded(self, tmp_path: Path) -> Path:
        destination = tmp_path / "decoded.osm.xml"
        decode_pbf_to_osm_xml(
            _real_pbf(tmp_path), destination, allow_unpinned_source=True, synthetic=True
        )
        return destination

    def test_a_receipt_is_persisted_beside_the_artifact(self, tmp_path: Path) -> None:
        self._decoded(tmp_path)
        assert (tmp_path / "decoded.osm.xml.receipt.json").is_file()

    def test_replay_revalidates_without_provider_or_decoder(self, tmp_path: Path) -> None:
        destination = self._decoded(tmp_path)
        receipt = verify_decoded_artifact(destination)
        assert receipt.decoded_filename == "decoded.osm.xml"
        assert receipt.decoded_bytes == destination.stat().st_size

    def test_replay_reproduces_the_recorded_identity(self, tmp_path: Path) -> None:
        destination = self._decoded(tmp_path)
        first = verify_decoded_artifact(destination)
        second = verify_decoded_artifact(destination)
        assert first.decoded_sha256 == second.decoded_sha256
        assert first.fingerprint() == second.fingerprint()

    def test_a_mutated_artifact_is_detected(self, tmp_path: Path) -> None:
        destination = self._decoded(tmp_path)
        destination.write_bytes(destination.read_bytes() + b"<!-- tampered -->")
        with pytest.raises(NetworkDecodeError, match="DECODED_ARTIFACT_MUTATED"):
            verify_decoded_artifact(destination)

    def test_a_mutated_receipt_is_detected(self, tmp_path: Path) -> None:
        # The seal covers the whole payload, so an edited field is rejected before
        # any downstream check gets to run.
        destination = self._decoded(tmp_path)
        receipt_file = tmp_path / "decoded.osm.xml.receipt.json"
        payload = json.loads(receipt_file.read_text(encoding="utf-8"))
        payload["decoded_sha256"] = "c" * 64
        receipt_file.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NetworkDecodeError, match="DECODE_RECEIPT_INVALID"):
            verify_decoded_artifact(destination)

    def test_an_unsealed_receipt_is_rejected(self, tmp_path: Path) -> None:
        destination = self._decoded(tmp_path)
        receipt_file = tmp_path / "decoded.osm.xml.receipt.json"
        payload = json.loads(receipt_file.read_text(encoding="utf-8"))
        payload["receipt_fingerprint"] = UNSEALED_FINGERPRINT
        receipt_file.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NetworkDecodeError, match="DECODE_RECEIPT_INVALID"):
            verify_decoded_artifact(destination)

    def test_a_malformed_receipt_is_detected(self, tmp_path: Path) -> None:
        destination = self._decoded(tmp_path)
        (tmp_path / "decoded.osm.xml.receipt.json").write_text("{ not json", encoding="utf-8")
        with pytest.raises(NetworkDecodeError, match="DECODE_RECEIPT_INVALID"):
            verify_decoded_artifact(destination)

    def test_a_receipt_for_a_different_artifact_is_detected(self, tmp_path: Path) -> None:
        # Use a genuinely sealed receipt from a second decode rather than a hand-edited
        # one, so this exercises the artifact binding and not the seal.
        destination = self._decoded(tmp_path)
        other = tmp_path / "somethingelse.osm.xml"
        decode_pbf_to_osm_xml(
            _real_pbf(tmp_path), other, allow_unpinned_source=True, synthetic=True
        )
        foreign = (tmp_path / "somethingelse.osm.xml.receipt.json").read_text(encoding="utf-8")
        (tmp_path / "decoded.osm.xml.receipt.json").write_text(foreign, encoding="utf-8")
        with pytest.raises(NetworkDecodeError, match="DECODE_RECEIPT_MISMATCH"):
            verify_decoded_artifact(destination)

    def test_a_missing_receipt_is_detected(self, tmp_path: Path) -> None:
        destination = self._decoded(tmp_path)
        (tmp_path / "decoded.osm.xml.receipt.json").unlink()
        with pytest.raises(NetworkDecodeError, match="DECODE_RECEIPT_MISSING"):
            verify_decoded_artifact(destination)

    def test_a_failed_rerun_preserves_the_accepted_artifact(self, tmp_path: Path) -> None:
        destination = self._decoded(tmp_path)
        original = destination.read_bytes()
        with pytest.raises(NetworkDecodeError, match="DESTINATION_EXISTS"):
            decode_pbf_to_osm_xml(
                _real_pbf(tmp_path), destination, allow_unpinned_source=True, synthetic=True
            )
        assert destination.read_bytes() == original
        verify_decoded_artifact(destination)


class TestNoRawArtifactIsTracked:
    """Raw extracts, decoded XML and built networks are private workspace
    artifacts. This audits the actual Git index rather than trusting policy.

    Two small pre-existing synthetic fixtures are named exceptions: the closed
    SUMO synthetic-square scenario (1,048 bytes) and a VEC micro test fixture
    (433 bytes). Neither is Manchester or OSM derived. They are listed
    explicitly so the audit stays strict rather than being broadened away.
    """

    PERMITTED_SYNTHETIC_FIXTURES = frozenset(
        {
            "src/traffictwin/integration/sumo_execution/scenario_synthetic_square/square.net.xml",
            "tests/fixtures/vec_fcd/synthetic_micro/network.net.xml",
        }
    )

    @staticmethod
    def _tracked_files() -> list[str]:
        git = shutil.which("git")
        assert git is not None, "git is required for the tracked-file audit"
        repository = Path(__file__).resolve().parents[2]
        return subprocess.run(  # noqa: S603 - resolved git path, fixed read-only argv
            [git, "-C", str(repository), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout.splitlines()

    def test_no_raw_osm_or_network_artifact_is_tracked(self) -> None:
        forbidden = tuple(
            name
            for name in self._tracked_files()
            if name.endswith((".osm", ".osm.pbf", ".osm.xml", ".net.xml", ".pbf"))
            and name not in self.PERMITTED_SYNTHETIC_FIXTURES
        )
        assert not forbidden, f"raw source or network artifacts are tracked: {forbidden}"

    def test_no_dated_provider_extract_is_tracked(self) -> None:
        # Matches the provider's dated artifact shape, e.g.
        # greater-manchester-260724.osm.pbf, without flagging documentation
        # whose filename merely mentions Greater Manchester.
        dated_extract = re.compile(r"greater-manchester-\d{6}\.osm(\.pbf|\.xml)?$")
        suspicious = tuple(
            name for name in self._tracked_files() if dated_extract.search(name.lower())
        )
        assert not suspicious, f"provider source extracts are tracked: {suspicious}"

    def test_no_tracked_file_is_implausibly_large(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        oversized = [
            (name, (repository / name).stat().st_size)
            for name in self._tracked_files()
            if (repository / name).is_file() and (repository / name).stat().st_size > 8_000_000
        ]
        assert not oversized, f"unexpectedly large tracked files: {oversized}"


class TestPinnedSourceIsTheDefault:
    """An unpinned decode is admitted only as clearly-labelled synthetic evidence."""

    def test_an_unpinned_real_decode_is_refused_by_default(self, tmp_path: Path) -> None:
        with pytest.raises(NetworkDecodeError, match="UNPINNED_SOURCE_REFUSED"):
            decode_pbf_to_osm_xml(
                _fake_pbf(tmp_path), tmp_path / "out.osm.xml", allow_unpinned_source=True
            )

    def test_the_default_path_demands_the_pinned_identity(self, tmp_path: Path) -> None:
        # Without an opt-out the pinned expectation applies, so a placeholder
        # extract fails identity rather than being quietly decoded.
        with pytest.raises(NetworkDecodeError):
            decode_pbf_to_osm_xml(_fake_pbf(tmp_path), tmp_path / "out.osm.xml")

    @requires_osmium
    def test_a_synthetic_decode_is_labelled_synthetic_in_its_receipt(self, tmp_path: Path) -> None:
        receipt = decode_pbf_to_osm_xml(
            _real_pbf(tmp_path),
            tmp_path / "out.osm.xml",
            allow_unpinned_source=True,
            synthetic=True,
        )
        assert receipt.synthetic is True
        assert receipt.source_pinned_by_default is False
        assert receipt.source_identity_verified is False


class TestWorkspaceContainment:
    @requires_osmium
    def test_a_destination_outside_the_workspace_is_refused(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        with pytest.raises(NetworkDecodeError, match="WORKSPACE_ESCAPE_REFUSED"):
            decode_pbf_to_osm_xml(
                _real_pbf(tmp_path),
                tmp_path / "elsewhere.osm.xml",
                workspace_root=workspace,
                allow_unpinned_source=True,
                synthetic=True,
            )

    @requires_osmium
    def test_a_traversal_destination_is_refused(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        with pytest.raises(NetworkDecodeError, match="WORKSPACE_ESCAPE_REFUSED"):
            decode_pbf_to_osm_xml(
                _real_pbf(tmp_path),
                workspace / ".." / "escaped.osm.xml",
                workspace_root=workspace,
                allow_unpinned_source=True,
                synthetic=True,
            )

    @requires_osmium
    def test_the_recorded_workspace_identity_discloses_no_private_path(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        receipt = decode_pbf_to_osm_xml(
            _real_pbf(tmp_path),
            workspace / "out.osm.xml",
            workspace_root=workspace,
            allow_unpinned_source=True,
            synthetic=True,
        )
        assert receipt.workspace_identity is not None
        assert str(tmp_path) not in receipt.workspace_identity
        assert "/" not in receipt.workspace_identity
        assert receipt.workspace_identity.startswith("workspace:")


class TestDecodedStructureIsValidated:
    def test_a_wrong_root_element_is_refused(self, tmp_path: Path) -> None:
        target = tmp_path / "wrong.osm.xml"
        target.write_text(
            "<?xml version='1.0'?>\n<netconvert><node id='1'/></netconvert>\n", encoding="utf-8"
        )
        with pytest.raises(NetworkDecodeError, match="DECODED_WRONG_XML_ROOT"):
            validate_osm_xml_structure(target)

    def test_an_osm_document_with_no_content_is_refused(self, tmp_path: Path) -> None:
        target = tmp_path / "empty.osm.xml"
        target.write_text("<?xml version='1.0'?>\n<osm version='0.6'>\n</osm>\n", encoding="utf-8")
        with pytest.raises(NetworkDecodeError, match="DECODED_OSM_XML_EMPTY"):
            validate_osm_xml_structure(target)

    def test_a_real_osm_document_reports_its_root_and_content(self, tmp_path: Path) -> None:
        target = tmp_path / "good.osm.xml"
        target.write_text(SYNTHETIC_OSM, encoding="utf-8")
        root, elements = validate_osm_xml_structure(target)
        assert root == "osm"
        assert elements > 0


class TestReceiptCarriesItsProvenance:
    @requires_osmium
    def test_the_receipt_records_licence_and_attribution(self, tmp_path: Path) -> None:
        receipt = decode_pbf_to_osm_xml(
            _real_pbf(tmp_path),
            tmp_path / "out.osm.xml",
            allow_unpinned_source=True,
            synthetic=True,
        )
        assert receipt.licence_id == "ODbL-1.0"
        assert receipt.attribution_text == "© OpenStreetMap contributors, ODbL 1.0"

    @requires_osmium
    def test_the_receipt_binds_the_frozen_argument_vector(self, tmp_path: Path) -> None:
        receipt = decode_pbf_to_osm_xml(
            _real_pbf(tmp_path),
            tmp_path / "out.osm.xml",
            allow_unpinned_source=True,
            synthetic=True,
        )
        assert receipt.argument_fingerprint == argument_fingerprint()

    @requires_osmium
    def test_a_receipt_recording_a_changed_argument_vector_is_refused(self, tmp_path: Path) -> None:
        receipt = decode_pbf_to_osm_xml(
            _real_pbf(tmp_path),
            tmp_path / "out.osm.xml",
            allow_unpinned_source=True,
            synthetic=True,
        )
        payload: dict[str, Any] = json.loads(receipt.canonical_json())
        payload["argument_fingerprint"] = "d" * 64
        with pytest.raises(ValidationError, match="exact frozen argument vector"):
            OsmDecodeReceipt.model_validate_json(json.dumps(payload))

    @requires_osmium
    def test_the_receipt_states_the_decode_changed_no_content(self, tmp_path: Path) -> None:
        receipt = decode_pbf_to_osm_xml(
            _real_pbf(tmp_path),
            tmp_path / "out.osm.xml",
            allow_unpinned_source=True,
            synthetic=True,
        )
        assert receipt.conversion_only is True
        assert receipt.content_filtered is False
        assert receipt.bounding_box_clipped is False
        assert receipt.simplified is False
        assert receipt.road_classes_selected is False

    @requires_osmium
    def test_a_receipt_claiming_real_evidence_without_a_pinned_source_is_refused(
        self, tmp_path: Path
    ) -> None:
        receipt = decode_pbf_to_osm_xml(
            _real_pbf(tmp_path),
            tmp_path / "out.osm.xml",
            allow_unpinned_source=True,
            synthetic=True,
        )
        payload: dict[str, Any] = json.loads(receipt.canonical_json())
        payload["synthetic"] = False
        with pytest.raises(ValidationError):
            OsmDecodeReceipt.model_validate_json(json.dumps(payload))
