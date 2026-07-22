from __future__ import annotations

import gzip
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.transport import (
    BoundedHttpClient,
    EndpointPolicy,
    ManchesterTransportError,
    TransportPolicy,
)


def _endpoint(**updates: object) -> EndpointPolicy:
    values: dict[str, object] = {
        "endpoint_id": "bods_live",
        "host": "example.test",
        "path_prefixes": ("/api/v1/",),
        "query_parameter_names": ("page", "operatorRef"),
        "sensitive_query_parameter_names": ("vehicleRef",),
        "secret_query_parameter_names": ("api_key",),
    }
    values.update(updates)
    return EndpointPolicy.model_validate(values)


def _policy(**updates: object) -> TransportPolicy:
    values: dict[str, object] = {
        "connect_timeout_s": 1.0,
        "read_timeout_s": 2.0,
        "write_timeout_s": 1.0,
        "pool_timeout_s": 1.0,
        "total_deadline_s": 20.0,
        "max_response_bytes": 1024,
        "max_redirects": 1,
        "max_attempts": 2,
        "backoff_base_s": 0.1,
        "backoff_max_s": 1.0,
        "retry_status_codes": (429, 500, 502, 503, 504),
        "allowed_media_types": ("application/json",),
        "require_content_type": True,
    }
    values.update(updates)
    return TransportPolicy.model_validate(values)


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, follow_redirects=True)


def test_success_preserves_raw_bytes_and_redacts_secret_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == "private-value"
        assert request.url.params["operatorRef"] == "BNDB"
        assert request.url.params["vehicleRef"] == "sensitive-vehicle"
        return httpx.Response(
            200,
            headers={
                "content-length": "11",
                "content-type": "application/json; charset=utf-8",
                "etag": "one",
            },
            stream=httpx.ByteStream(b'{"ok":true}'),
        )

    now = datetime(2026, 7, 22, 12, tzinfo=UTC)
    with _client(httpx.MockTransport(handler)) as raw_client:
        bounded = BoundedHttpClient(
            endpoint=_endpoint(),
            policy=_policy(),
            client=raw_client,
            utc_now=lambda: now,
        )
        result = bounded.fetch(
            "/api/v1/datafeed/",
            query={"operatorRef": "BNDB", "page": 1},
            sensitive_query={"vehicleRef": "sensitive-vehicle"},
            secret_query={"api_key": "private-value"},
        )

    assert result.body == b'{"ok":true}'
    assert result.metadata.safe_query_parameters == (("operatorRef", "BNDB"), ("page", "1"))
    assert result.metadata.redacted_query_parameter_names == ("api_key", "vehicleRef")
    assert result.metadata.response_headers == (
        ("content-length", "11"),
        ("content-type", "application/json; charset=utf-8"),
        ("etag", "one"),
    )
    assert "private-value" not in repr(result)
    assert "private-value" not in result.metadata.model_dump_json()
    assert "sensitive-vehicle" not in result.metadata.model_dump_json()


@pytest.mark.parametrize(
    "path",
    [
        "/outside/file",
        "/api/v1/../private",
        "/api/v1/%2e%2e/private",
        "/api/v1/%252e%252e/private",
        "/api/v1/file?api_key=x",
        "https://example.test/api/v1/file",
    ],
)
def test_path_boundary_rejects_non_allowlisted_or_ambiguous_paths(path: str) -> None:
    with _client(httpx.MockTransport(lambda _request: httpx.Response(200))) as raw_client:
        bounded = BoundedHttpClient(endpoint=_endpoint(), policy=_policy(), client=raw_client)
        with pytest.raises(ManchesterTransportError):
            bounded.fetch(path)


def test_safe_query_rejects_unknown_and_secret_like_names() -> None:
    with pytest.raises(ValidationError, match="secret-like"):
        _endpoint(query_parameter_names=("token",))

    with _client(httpx.MockTransport(lambda _request: httpx.Response(200))) as raw_client:
        bounded = BoundedHttpClient(endpoint=_endpoint(), policy=_policy(), client=raw_client)
        with pytest.raises(ManchesterTransportError, match="query_parameter_rejected"):
            bounded.fetch("/api/v1/datafeed/", query={"unknown": "x"})
        with pytest.raises(ManchesterTransportError, match="secret_query_parameter_rejected"):
            bounded.fetch("/api/v1/datafeed/", secret_query={"password": "x"})
        with pytest.raises(ManchesterTransportError, match="sensitive_query_parameter_rejected"):
            bounded.fetch("/api/v1/datafeed/", sensitive_query={"unknown": "x"})


def test_dft_style_bracketed_query_names_are_admitted_when_declared() -> None:
    endpoint = _endpoint(query_parameter_names=("page[size]", "filter[local_authority_id]"))
    with _client(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                stream=httpx.ByteStream(request.url.query),
            )
        )
    ) as raw_client:
        result = BoundedHttpClient(endpoint=endpoint, policy=_policy(), client=raw_client).fetch(
            "/api/v1/datafeed/",
            query={"page[size]": 100, "filter[local_authority_id]": "E08000003"},
        )
    assert result.metadata.safe_query_parameters == (
        ("filter[local_authority_id]", "E08000003"),
        ("page[size]", "100"),
    )


def test_same_host_allowlisted_redirect_is_followed_explicitly() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("datafeed/"):
            return httpx.Response(302, headers={"location": "/api/v1/result"})
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(b"{}"),
        )

    with _client(httpx.MockTransport(handler)) as raw_client:
        result = BoundedHttpClient(endpoint=_endpoint(), policy=_policy(), client=raw_client).fetch(
            "/api/v1/datafeed/"
        )

    assert paths == ["/api/v1/datafeed/", "/api/v1/result"]
    assert result.metadata.redirect_hops == 1
    assert result.metadata.final_path == "/api/v1/result"


@pytest.mark.parametrize(
    "location",
    ["https://evil.test/api/v1/result", "http://example.test/api/v1/result", "/outside/result"],
)
def test_redirect_fails_closed_for_cross_host_scheme_or_path(location: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(302, headers={"location": location})
    )
    with _client(transport) as raw_client:
        bounded = BoundedHttpClient(endpoint=_endpoint(), policy=_policy(), client=raw_client)
        with pytest.raises(ManchesterTransportError):
            bounded.fetch("/api/v1/datafeed/")


def test_retry_is_explicit_bounded_and_url_redacted() -> None:
    statuses = iter((503, 200))
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(
            status,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(b"{}"),
        )

    with _client(httpx.MockTransport(handler)) as raw_client:
        result = BoundedHttpClient(
            endpoint=_endpoint(),
            policy=_policy(),
            client=raw_client,
            sleep=sleeps.append,
            jitter=lambda: 0.5,
        ).fetch("/api/v1/datafeed/", secret_query={"api_key": "never-log-this"})

    assert result.metadata.network_requests == 2
    assert sleeps == [0.05]
    assert "never-log-this" not in repr(result)


def test_retry_exhaustion_returns_only_typed_code() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(503))
    with _client(transport) as raw_client:
        bounded = BoundedHttpClient(
            endpoint=_endpoint(),
            policy=_policy(),
            client=raw_client,
            sleep=lambda _seconds: None,
            jitter=lambda: 0.0,
        )
        with pytest.raises(ManchesterTransportError) as caught:
            bounded.fetch("/api/v1/datafeed/", secret_query={"api_key": "never-log-this"})
    assert caught.value.code == "retry_exhausted"
    assert caught.value.status_code == 503
    assert str(caught.value) == "retry_exhausted"


@pytest.mark.parametrize(
    ("headers", "content", "code"),
    [
        ({}, b"{}", "content_type_missing"),
        ({"content-type": "text/html"}, b"{}", "content_type_rejected"),
        (
            {"content-type": "application/json", "content-length": "invalid"},
            b"{}",
            "content_length_invalid",
        ),
        ({"content-type": "application/json"}, b"12345", "response_size_exceeded"),
    ],
)
def test_response_headers_and_streamed_bytes_are_bounded(
    headers: dict[str, str], content: bytes, code: str
) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, headers=headers, stream=httpx.ByteStream(content))
    )
    with _client(transport) as raw_client:
        bounded = BoundedHttpClient(
            endpoint=_endpoint(), policy=_policy(max_response_bytes=4), client=raw_client
        )
        with pytest.raises(ManchesterTransportError, match=code):
            bounded.fetch("/api/v1/datafeed/")


def test_http_content_decoding_is_bounded_by_output_bytes() -> None:
    compressed = gzip.compress(b"x" * 1_000)
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-encoding": "gzip",
                "content-length": str(len(compressed)),
            },
            stream=httpx.ByteStream(compressed),
        )
    )
    with _client(transport) as raw_client:
        bounded = BoundedHttpClient(
            endpoint=_endpoint(), policy=_policy(max_response_bytes=100), client=raw_client
        )
        with pytest.raises(ManchesterTransportError, match="response_size_exceeded"):
            bounded.fetch("/api/v1/datafeed/")


def test_encoded_response_preserves_exact_wire_bytes_after_bounded_validation() -> None:
    compressed = gzip.compress(b'{"synthetic":true}')
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-encoding": "gzip",
                "content-length": str(len(compressed)),
            },
            stream=httpx.ByteStream(compressed),
        )
    )
    with _client(transport) as raw_client:
        result = BoundedHttpClient(
            endpoint=_endpoint(), policy=_policy(max_response_bytes=100), client=raw_client
        ).fetch("/api/v1/datafeed/")
    assert result.body == compressed
    assert result.metadata.response_headers[0] == ("content-encoding", "gzip")


def test_total_deadline_is_enforced_before_network_access() -> None:
    ticks: Iterator[float] = iter((0.0, 21.0))
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    with _client(httpx.MockTransport(handler)) as raw_client:
        bounded = BoundedHttpClient(
            endpoint=_endpoint(),
            policy=_policy(total_deadline_s=20.0),
            client=raw_client,
            monotonic=lambda: next(ticks),
        )
        with pytest.raises(ManchesterTransportError, match="total_deadline_exceeded"):
            bounded.fetch("/api/v1/datafeed/")
    assert calls == 0


def test_transport_models_reject_unknown_fields_and_inconsistent_limits() -> None:
    with pytest.raises(ValidationError):
        _endpoint(extra_field="x")
    with pytest.raises(ValidationError, match="backoff_base_s"):
        _policy(backoff_base_s=2.0, backoff_max_s=1.0)
    with pytest.raises(ValidationError, match="lowercase"):
        _policy(allowed_media_types=("Application/JSON",))
    with pytest.raises(ValidationError, match="total deadline"):
        _policy(total_deadline_s=1.0, read_timeout_s=2.0)
    with pytest.raises(ValidationError, match="canonical DNS"):
        _endpoint(host="example..test")
    with pytest.raises(ValidationError, match="must not overlap"):
        _endpoint(sensitive_query_parameter_names=("page",))
