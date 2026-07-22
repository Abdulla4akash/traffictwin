"""Contract tests joining bounded Manchester transport to immutable snapshots."""

from __future__ import annotations

import gzip
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.acquisition import snapshot_parts_from_http_response
from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.integration.manchester.transport import BoundedHttpResponse, SafeResponseMetadata


def test_bounded_response_maps_to_secret_free_snapshot_parts_without_changing_bytes() -> None:
    body = gzip.compress(b'{"synthetic":true}\n')
    response = BoundedHttpResponse(
        metadata=SafeResponseMetadata(
            endpoint_id="synthetic_api",
            host="example.invalid",
            request_path="/api/records",
            final_path="/api/records/page/1",
            safe_query_parameters=(("page", "1"),),
            redacted_query_parameter_names=("api_key",),
            status_code=200,
            response_headers=(
                ("content-encoding", "gzip"),
                ("content-length", str(len(body))),
                ("content-type", "application/json; charset=utf-8"),
                ("etag", '"synthetic-etag"'),
                ("last-modified", "Wed, 22 Jul 2026 09:00:00 GMT"),
            ),
            retrieval_started_at_utc=datetime(2026, 7, 22, 9, 0, tzinfo=UTC),
            retrieval_finished_at_utc=datetime(2026, 7, 22, 9, 1, tzinfo=UTC),
            network_requests=2,
            redirect_hops=1,
        ),
        body=body,
    )

    parts = snapshot_parts_from_http_response(
        response,
        relative_path="pages/page-1.json",
        media_type="application/json",
    )

    assert parts.payload == body
    assert parts.member.byte_size == len(body)
    assert parts.member.sha256 == sha256_hex(body)
    assert parts.request.parameters == (("page", "1"),)
    assert parts.request.redacted_parameter_names == ("api_key",)
    assert parts.http.response_content_type == "application/json"
    assert parts.http.response_content_encoding == "gzip"
    assert parts.http.declared_content_length == len(body)
    assert parts.http.final_path == "/api/records/page/1"
    assert parts.http.network_requests == 2
    assert parts.http.redirect_hops == 1


def test_transport_metadata_refuses_unsafe_headers_and_bridge_refuses_media_type_drift() -> None:
    base = {
        "endpoint_id": "synthetic_api",
        "host": "example.invalid",
        "request_path": "/api/records",
        "final_path": "/api/records",
        "safe_query_parameters": (),
        "redacted_query_parameter_names": (),
        "status_code": 200,
        "retrieval_started_at_utc": datetime(2026, 7, 22, 9, 0, tzinfo=UTC),
        "retrieval_finished_at_utc": datetime(2026, 7, 22, 9, 1, tzinfo=UTC),
        "network_requests": 1,
        "redirect_hops": 0,
    }
    with pytest.raises(ValidationError):
        SafeResponseMetadata.model_validate(
            {**base, "response_headers": (("authorization", "Bearer secret"),)}
        )

    response = BoundedHttpResponse(
        metadata=SafeResponseMetadata.model_validate(
            {**base, "response_headers": (("content-type", "application/json"),)}
        ),
        body=b"{}",
    )
    with pytest.raises(ValueError, match="media type"):
        snapshot_parts_from_http_response(
            response,
            relative_path="body.csv",
            media_type="text/csv",
        )
