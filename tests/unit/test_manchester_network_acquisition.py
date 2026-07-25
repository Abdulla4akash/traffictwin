"""Adversarial evidence for bounded, operator-invoked OSM extract acquisition."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.models import (
    ManchesterSnapshotPolicy,
    sha256_hex,
)
from traffictwin.integration.manchester.network_acquisition import (
    OSM_CHECKSUM_MEMBER_PATH,
    OSM_CHECKSUM_PATH,
    OSM_EXTRACT_DATA_CUTOFF_DATE,
    OSM_EXTRACT_FILENAME,
    OSM_EXTRACT_MEMBER_PATH,
    OSM_EXTRACT_PATH,
    OSM_MIN_EXTRACT_BYTES,
    OSM_REFERENCE_DATE,
    LocalOsmExtractImportRequest,
    OperatorAuthorisation,
    OsmAcquisitionError,
    OsmExtractAcquisitionRequest,
    acquire_osm_extract_snapshot,
    check_pbf_framing,
    import_local_osm_extract,
    parse_provider_md5,
    read_accepted_extract,
)
from traffictwin.integration.manchester.snapshots import (
    ACCEPTED_DIRECTORY_NAME,
    verify_manchester_snapshot,
)

PBF_HEADER = b"\x00\x00\x00\x0d\x0a\x09OSMHeader\x18\x00"


def _synthetic_pbf(size: int = OSM_MIN_EXTRACT_BYTES + 512) -> bytes:
    """Build a labelled synthetic payload with valid PBF framing.

    This is deliberately not a real OSM extract.  It exercises framing,
    hashing, bounds, and promotion only.
    """

    body = b"SYNTHETIC-TRAFFICTWIN-FIXTURE-NOT-MANCHESTER-DATA" * 64
    payload = PBF_HEADER + body
    return payload + b"\x00" * max(0, size - len(payload))


def _md5(payload: bytes) -> str:
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


def _checksum_file(payload: bytes) -> bytes:
    return f"{_md5(payload)}  greater-manchester-latest.osm.pbf\n".encode("ascii")


def _authorisation() -> OperatorAuthorisation:
    return OperatorAuthorisation(
        confirmed_by_operator=True,
        invoked_via="test_harness",
        reason="synthetic acquisition fixture",
    )


def _policy() -> ManchesterSnapshotPolicy:
    return ManchesterSnapshotPolicy(
        max_member_count=8,
        max_member_bytes=64_000_000,
        max_total_bytes=128_000_000,
    )


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace-v0.7" / "manchester" / "networks"
    root.mkdir(parents=True)
    return root


def _transport(extract: bytes, checksum: bytes | None = None) -> httpx.Client:
    """Return a client whose only routes are the two frozen endpoint paths."""

    checksum_body = _checksum_file(extract) if checksum is None else checksum

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == OSM_EXTRACT_PATH:
            return httpx.Response(
                200,
                headers={"content-type": "application/octet-stream"},
                stream=httpx.ByteStream(extract),
            )
        if request.url.path == OSM_CHECKSUM_PATH:
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                stream=httpx.ByteStream(checksum_body),
            )
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def _clock() -> datetime:
    return datetime(2026, 7, 25, 9, 0, 0, tzinfo=UTC)


class TestOperatorAuthorisation:
    def test_acquisition_requires_explicit_operator_confirmation(self) -> None:
        with pytest.raises(ValidationError):
            OperatorAuthorisation(
                confirmed_by_operator=False,  # type: ignore[arg-type]
                invoked_via="cli",
                reason="should be impossible",
            )

    def test_authorisation_records_how_it_was_invoked(self) -> None:
        assert _authorisation().invoked_via == "test_harness"

    def test_request_has_no_caller_supplied_network_identity(self) -> None:
        fields = set(OsmExtractAcquisitionRequest.model_fields)
        forbidden = {"host", "url", "path", "mirror", "query", "parser", "endpoint", "max_bytes"}
        assert not (fields & forbidden), f"request exposes network identity: {fields & forbidden}"

    def test_request_refuses_a_policy_above_the_reviewed_bound(self) -> None:
        with pytest.raises(ValidationError, match="reviewed OSM extract bound"):
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(),
                policy=ManchesterSnapshotPolicy(
                    max_member_count=8,
                    max_member_bytes=1_000_000_000,
                    max_total_bytes=1_500_000_000,
                ),
                synthetic=True,
            )


class TestBoundedAcquisition:
    def test_extract_and_checksum_are_acquired_and_promoted(self, tmp_path: Path) -> None:
        extract = _synthetic_pbf()
        root = _workspace(tmp_path)
        result = acquire_osm_extract_snapshot(
            root,
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            http_client=_transport(extract),
            utc_now=_clock,
        )
        assert result.acquisition_mode == "bounded_http"
        assert result.identity.extract_sha256 == sha256_hex(extract)
        assert result.identity.extract_md5 == _md5(extract)
        assert result.identity.provider_checksum_verified is True
        assert result.identity.provider_checksum_source == "provider_md5_companion"
        assert {member.relative_path for member in result.members} == {
            OSM_EXTRACT_MEMBER_PATH,
            OSM_CHECKSUM_MEMBER_PATH,
        }

    def test_accepted_snapshot_reverifies_and_preserves_raw_bytes(self, tmp_path: Path) -> None:
        extract = _synthetic_pbf()
        root = _workspace(tmp_path)
        result = acquire_osm_extract_snapshot(
            root,
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            http_client=_transport(extract),
            utc_now=_clock,
        )
        snapshot_dir = root / ACCEPTED_DIRECTORY_NAME / result.snapshot_id
        verify_manchester_snapshot(snapshot_dir)
        assert read_accepted_extract(snapshot_dir) == extract

    def test_licence_and_attribution_are_carried_on_the_receipt(self, tmp_path: Path) -> None:
        result = acquire_osm_extract_snapshot(
            _workspace(tmp_path),
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            http_client=_transport(_synthetic_pbf()),
            utc_now=_clock,
        )
        assert result.identity.licence_id == "ODbL-1.0"
        assert result.identity.attribution_text == "© OpenStreetMap contributors, ODbL 1.0"
        assert result.identity.publication_class == "private"

    def test_reference_date_is_pinned_to_the_adr_decision(self, tmp_path: Path) -> None:
        result = acquire_osm_extract_snapshot(
            _workspace(tmp_path),
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            http_client=_transport(_synthetic_pbf()),
            utc_now=_clock,
        )
        assert result.identity.reference_date == OSM_REFERENCE_DATE == date(2026, 7, 25)

    def test_retrieval_date_stays_separate_from_the_extract_data_cutoff(
        self, tmp_path: Path
    ) -> None:
        # Design §3.1: observation time is not retrieval time.  The operator
        # decided on 25 July 2026, but the newest published extract carries a
        # 24 July 2026 data cutoff; both are recorded and never collapsed.
        result = acquire_osm_extract_snapshot(
            _workspace(tmp_path),
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            http_client=_transport(_synthetic_pbf()),
            utc_now=_clock,
        )
        assert result.identity.reference_date == date(2026, 7, 25)
        assert result.identity.extract_data_cutoff_date == OSM_EXTRACT_DATA_CUTOFF_DATE
        assert result.identity.extract_data_cutoff_date == date(2026, 7, 24)
        assert result.identity.reference_date != result.identity.extract_data_cutoff_date

    def test_the_pinned_path_is_dated_and_never_the_moving_latest_alias(self) -> None:
        # `-latest` 302-redirects to a dated file, so pinning it would make the
        # baseline non-reproducible.  Redirects are disallowed outright.
        assert "latest" not in OSM_EXTRACT_PATH
        assert OSM_EXTRACT_PATH.endswith("greater-manchester-260724.osm.pbf")
        assert OSM_EXTRACT_FILENAME == "greater-manchester-260724.osm.pbf"

    def test_result_makes_no_build_or_calibration_claim(self, tmp_path: Path) -> None:
        result = acquire_osm_extract_snapshot(
            _workspace(tmp_path),
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            http_client=_transport(_synthetic_pbf()),
            utc_now=_clock,
        )
        assert result.network_build_performed is False
        assert result.calibration_performed is False
        assert result.capability_status == "planned"


class TestAdversarialAcquisition:
    def test_checksum_drift_refuses_and_publishes_nothing(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)
        wrong = _checksum_file(b"different-bytes-entirely")
        with pytest.raises(OsmAcquisitionError, match="CHECKSUM_IDENTITY_DRIFT"):
            acquire_osm_extract_snapshot(
                root,
                OsmExtractAcquisitionRequest(
                    authorisation=_authorisation(), policy=_policy(), synthetic=True
                ),
                http_client=_transport(_synthetic_pbf(), checksum=wrong),
                utc_now=_clock,
            )
        accepted = root / ACCEPTED_DIRECTORY_NAME
        assert not accepted.exists() or not any(accepted.iterdir())

    def test_a_non_pbf_payload_is_refused(self, tmp_path: Path) -> None:
        payload = b"<html>not an extract</html>" + b"\x00" * OSM_MIN_EXTRACT_BYTES
        with pytest.raises(OsmAcquisitionError, match="EXTRACT_NOT_PBF"):
            acquire_osm_extract_snapshot(
                _workspace(tmp_path),
                OsmExtractAcquisitionRequest(
                    authorisation=_authorisation(), policy=_policy(), synthetic=True
                ),
                http_client=_transport(payload),
                utc_now=_clock,
            )

    def test_an_implausibly_small_extract_is_refused(self) -> None:
        with pytest.raises(OsmAcquisitionError, match="EXTRACT_TOO_SMALL"):
            check_pbf_framing(PBF_HEADER + b"tiny")

    def test_an_unexpected_host_path_is_never_requested(self, tmp_path: Path) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(f"{request.url.host}{request.url.path}")
            body = _synthetic_pbf()
            if request.url.path == OSM_EXTRACT_PATH:
                return httpx.Response(
                    200,
                    headers={"content-type": "application/octet-stream"},
                    stream=httpx.ByteStream(body),
                )
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                stream=httpx.ByteStream(_checksum_file(body)),
            )

        acquire_osm_extract_snapshot(
            _workspace(tmp_path),
            OsmExtractAcquisitionRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            utc_now=_clock,
        )
        assert seen == [
            f"download.geofabrik.de{OSM_EXTRACT_PATH}",
            f"download.geofabrik.de{OSM_CHECKSUM_PATH}",
        ]

    def test_an_unexpected_content_type_is_refused(self, tmp_path: Path) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                stream=httpx.ByteStream(_synthetic_pbf()),
            )

        with pytest.raises(OsmAcquisitionError, match="TRANSPORT_FAILURE"):
            acquire_osm_extract_snapshot(
                _workspace(tmp_path),
                OsmExtractAcquisitionRequest(
                    authorisation=_authorisation(), policy=_policy(), synthetic=True
                ),
                http_client=httpx.Client(transport=httpx.MockTransport(handler)),
                utc_now=_clock,
            )

    def test_a_redirect_is_refused(self, tmp_path: Path) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://elsewhere.example/x.pbf"})

        with pytest.raises(OsmAcquisitionError, match="TRANSPORT_FAILURE"):
            acquire_osm_extract_snapshot(
                _workspace(tmp_path),
                OsmExtractAcquisitionRequest(
                    authorisation=_authorisation(), policy=_policy(), synthetic=True
                ),
                http_client=httpx.Client(
                    transport=httpx.MockTransport(handler), follow_redirects=False
                ),
                utc_now=_clock,
            )

    def test_an_oversized_response_is_refused(self, tmp_path: Path) -> None:
        oversized = _synthetic_pbf(size=5_000_000)
        policy = ManchesterSnapshotPolicy(
            max_member_count=8, max_member_bytes=2_000_000, max_total_bytes=4_000_000
        )
        with pytest.raises(OsmAcquisitionError, match="TRANSPORT_FAILURE"):
            acquire_osm_extract_snapshot(
                _workspace(tmp_path),
                OsmExtractAcquisitionRequest(
                    authorisation=_authorisation(), policy=policy, synthetic=True
                ),
                http_client=_transport(oversized),
                utc_now=_clock,
            )

    def test_a_transport_outage_never_substitutes_data(self, tmp_path: Path) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        root = _workspace(tmp_path)
        with pytest.raises(OsmAcquisitionError, match="TRANSPORT_FAILURE"):
            acquire_osm_extract_snapshot(
                root,
                OsmExtractAcquisitionRequest(
                    authorisation=_authorisation(), policy=_policy(), synthetic=True
                ),
                http_client=httpx.Client(transport=httpx.MockTransport(handler)),
                utc_now=_clock,
            )
        accepted = root / ACCEPTED_DIRECTORY_NAME
        assert not accepted.exists() or not any(accepted.iterdir())


class TestProviderChecksumParsing:
    def test_a_valid_companion_line_parses(self) -> None:
        payload = b"d41d8cd98f00b204e9800998ecf8427e  greater-manchester-latest.osm.pbf\n"
        assert parse_provider_md5(payload) == "d41d8cd98f00b204e9800998ecf8427e"

    def test_an_empty_companion_is_refused(self) -> None:
        with pytest.raises(OsmAcquisitionError, match="CHECKSUM_FILE_REFUSED"):
            parse_provider_md5(b"")

    def test_a_multi_line_companion_is_refused(self) -> None:
        line = b"d41d8cd98f00b204e9800998ecf8427e  a.pbf\n"
        with pytest.raises(OsmAcquisitionError, match="CHECKSUM_FILE_MALFORMED"):
            parse_provider_md5(line * 2)

    def test_a_malformed_companion_is_refused(self) -> None:
        with pytest.raises(OsmAcquisitionError, match="CHECKSUM_FILE_MALFORMED"):
            parse_provider_md5(b"not-a-digest  file.pbf\n")

    def test_an_oversized_companion_is_refused(self) -> None:
        with pytest.raises(OsmAcquisitionError, match="CHECKSUM_FILE_REFUSED"):
            parse_provider_md5(b"a" * 8192)


class TestLocalImportAndOfflineReplay:
    def test_a_local_extract_imports_with_no_network_access(self, tmp_path: Path) -> None:
        extract = _synthetic_pbf()
        source = tmp_path / "gm.osm.pbf"
        source.write_bytes(extract)
        root = _workspace(tmp_path)
        result = import_local_osm_extract(
            root,
            source,
            LocalOsmExtractImportRequest(
                authorisation=_authorisation(),
                policy=_policy(),
                expected_sha256=sha256_hex(extract),
                synthetic=True,
            ),
            utc_now=_clock,
        )
        assert result.acquisition_mode == "local_import"
        assert result.identity.provider_checksum_source == "operator_declared"
        assert read_accepted_extract(root / ACCEPTED_DIRECTORY_NAME / result.snapshot_id) == extract

    def test_offline_replay_reproduces_identical_bytes_and_digest(self, tmp_path: Path) -> None:
        extract = _synthetic_pbf()
        source = tmp_path / "gm.osm.pbf"
        source.write_bytes(extract)
        root = _workspace(tmp_path)
        result = import_local_osm_extract(
            root,
            source,
            LocalOsmExtractImportRequest(
                authorisation=_authorisation(), policy=_policy(), synthetic=True
            ),
            utc_now=_clock,
        )
        snapshot_dir = root / ACCEPTED_DIRECTORY_NAME / result.snapshot_id
        replayed = read_accepted_extract(snapshot_dir)
        assert replayed == extract
        assert sha256_hex(replayed) == result.identity.extract_sha256

    def test_declared_sha_drift_is_refused(self, tmp_path: Path) -> None:
        source = tmp_path / "gm.osm.pbf"
        source.write_bytes(_synthetic_pbf())
        with pytest.raises(OsmAcquisitionError, match="EXTRACT_IDENTITY_DRIFT"):
            import_local_osm_extract(
                _workspace(tmp_path),
                source,
                LocalOsmExtractImportRequest(
                    authorisation=_authorisation(),
                    policy=_policy(),
                    expected_sha256="0" * 64,
                    synthetic=True,
                ),
                utc_now=_clock,
            )

    def test_declared_md5_drift_is_refused(self, tmp_path: Path) -> None:
        source = tmp_path / "gm.osm.pbf"
        source.write_bytes(_synthetic_pbf())
        with pytest.raises(OsmAcquisitionError, match="CHECKSUM_IDENTITY_DRIFT"):
            import_local_osm_extract(
                _workspace(tmp_path),
                source,
                LocalOsmExtractImportRequest(
                    authorisation=_authorisation(),
                    policy=_policy(),
                    expected_md5="0" * 32,
                    synthetic=True,
                ),
                utc_now=_clock,
            )

    def test_a_symlinked_extract_path_is_refused(self, tmp_path: Path) -> None:
        real = tmp_path / "real.osm.pbf"
        real.write_bytes(_synthetic_pbf())
        link = tmp_path / "link.osm.pbf"
        link.symlink_to(real)
        with pytest.raises(OsmAcquisitionError, match="EXTRACT_PATH_REFUSED"):
            import_local_osm_extract(
                _workspace(tmp_path),
                link,
                LocalOsmExtractImportRequest(
                    authorisation=_authorisation(), policy=_policy(), synthetic=True
                ),
                utc_now=_clock,
            )

    def test_a_missing_extract_path_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(OsmAcquisitionError, match="EXTRACT_PATH_REFUSED"):
            import_local_osm_extract(
                _workspace(tmp_path),
                tmp_path / "absent.osm.pbf",
                LocalOsmExtractImportRequest(
                    authorisation=_authorisation(), policy=_policy(), synthetic=True
                ),
                utc_now=_clock,
            )

    def test_reading_from_a_non_directory_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(OsmAcquisitionError, match="SNAPSHOT_INVALID"):
            read_accepted_extract(tmp_path / "nope")
