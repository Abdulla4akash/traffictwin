"""Allowlisted, bounded HTTP transport for Manchester source adapters."""

from __future__ import annotations

import random
import re
import time
import zlib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from math import isfinite
from pathlib import PurePosixPath
from typing import Protocol, TypeAlias
from urllib.parse import unquote

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

QueryValue: TypeAlias = str | int | float | bool
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_DEFAULT_RETRY_STATUSES = (429, 500, 502, 503, 504)
_SECRET_MARKERS = ("api_key", "apikey", "authorization", "password", "secret", "token")
_SAFE_RESPONSE_HEADERS = (
    "content-encoding",
    "content-length",
    "content-type",
    "etag",
    "last-modified",
)


class ManchesterTransportError(RuntimeError):
    """A URL-redacted failure raised by the bounded transport boundary."""

    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class EndpointPolicy(BaseModel):
    """One exact source endpoint family and its admitted query surface."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    endpoint_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    host: str = Field(pattern=r"^[a-z0-9.-]+$")
    path_prefixes: tuple[str, ...]
    query_parameter_names: tuple[str, ...] = ()
    sensitive_query_parameter_names: tuple[str, ...] = ()
    secret_query_parameter_names: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_endpoint(self) -> EndpointPolicy:
        """Require canonical, non-overlapping endpoint declarations."""

        if not self.path_prefixes:
            raise ValueError("at least one path prefix is required")
        try:
            canonical_prefixes = tuple(_canonical_path(prefix) for prefix in self.path_prefixes)
        except ManchesterTransportError as exc:
            raise ValueError("path prefixes must be canonical absolute paths") from exc
        if canonical_prefixes != self.path_prefixes:
            raise ValueError("path prefixes must be canonical absolute paths")
        if len(set(self.path_prefixes)) != len(self.path_prefixes):
            raise ValueError("path prefixes must be unique")
        if self.host.startswith((".", "-")) or self.host.endswith((".", "-")) or ".." in self.host:
            raise ValueError("host must be a canonical DNS name")
        safe_names = set(self.query_parameter_names)
        sensitive_names = set(self.sensitive_query_parameter_names)
        secret_names = set(self.secret_query_parameter_names)
        if len(safe_names) != len(self.query_parameter_names):
            raise ValueError("query parameter names must be unique")
        if len(secret_names) != len(self.secret_query_parameter_names):
            raise ValueError("secret query parameter names must be unique")
        if len(sensitive_names) != len(self.sensitive_query_parameter_names):
            raise ValueError("sensitive query parameter names must be unique")
        if (
            safe_names & secret_names
            or safe_names & sensitive_names
            or secret_names & sensitive_names
        ):
            raise ValueError("safe, sensitive, and secret query parameter names must not overlap")
        if any(not _valid_query_name(name) for name in safe_names | sensitive_names | secret_names):
            raise ValueError("query parameter names must be canonical")
        if any(_looks_secret(name) for name in safe_names):
            raise ValueError("secret-like names must be declared as secret query parameters")
        return self


class TransportPolicy(BaseModel):
    """Explicit network, retry, redirect, time, and response-size limits."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    connect_timeout_s: float = Field(gt=0, le=120)
    read_timeout_s: float = Field(gt=0, le=300)
    write_timeout_s: float = Field(gt=0, le=120)
    pool_timeout_s: float = Field(gt=0, le=120)
    total_deadline_s: float = Field(gt=0, le=600)
    max_response_bytes: int = Field(gt=0, le=2_000_000_000)
    max_redirects: int = Field(ge=0, le=5)
    max_attempts: int = Field(gt=0, le=5)
    backoff_base_s: float = Field(ge=0, le=30)
    backoff_max_s: float = Field(ge=0, le=120)
    retry_status_codes: tuple[int, ...] = _DEFAULT_RETRY_STATUSES
    allowed_media_types: tuple[str, ...]
    require_content_type: bool = True

    @model_validator(mode="after")
    def validate_transport(self) -> TransportPolicy:
        """Reject inconsistent limits and unsafe response declarations."""

        if self.backoff_base_s > self.backoff_max_s:
            raise ValueError("backoff_base_s cannot exceed backoff_max_s")
        if any(
            timeout > self.total_deadline_s
            for timeout in (
                self.connect_timeout_s,
                self.read_timeout_s,
                self.write_timeout_s,
                self.pool_timeout_s,
            )
        ):
            raise ValueError("individual timeouts cannot exceed the total deadline")
        if len(set(self.retry_status_codes)) != len(self.retry_status_codes):
            raise ValueError("retry status codes must be unique")
        if any(code < 400 or code > 599 for code in self.retry_status_codes):
            raise ValueError("retry status codes must be HTTP error statuses")
        if not self.allowed_media_types:
            raise ValueError("at least one allowed media type is required")
        normalised = tuple(value.strip().lower() for value in self.allowed_media_types)
        if normalised != self.allowed_media_types or len(set(normalised)) != len(normalised):
            raise ValueError("allowed media types must be unique lowercase values")
        return self


class SafeResponseMetadata(BaseModel):
    """Persistable response metadata with credentials and full URLs excluded by type."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    endpoint_id: str
    host: str
    request_path: str
    final_path: str
    safe_query_parameters: tuple[tuple[str, str], ...]
    redacted_query_parameter_names: tuple[str, ...]
    status_code: int = Field(ge=100, le=599)
    response_headers: tuple[tuple[str, str], ...]
    retrieval_started_at_utc: datetime
    retrieval_finished_at_utc: datetime
    network_requests: int = Field(gt=0)
    redirect_hops: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_times(self) -> SafeResponseMetadata:
        """Require canonical, secret-free metadata and monotonic UTC times."""

        started = _aware_utc(self.retrieval_started_at_utc)
        finished = _aware_utc(self.retrieval_finished_at_utc)
        if finished < started:
            raise ValueError("retrieval finish cannot precede retrieval start")
        if re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", self.endpoint_id) is None:
            raise ValueError("endpoint_id must be a canonical identifier")
        if (
            re.fullmatch(r"[a-z0-9.-]+", self.host) is None
            or self.host.startswith((".", "-"))
            or self.host.endswith((".", "-"))
            or ".." in self.host
        ):
            raise ValueError("host must be a canonical DNS name")
        try:
            if _canonical_path(self.request_path) != self.request_path:
                raise ValueError("request path must be canonical")
            if _canonical_path(self.final_path) != self.final_path:
                raise ValueError("final path must be canonical")
        except ManchesterTransportError as exc:
            raise ValueError("response paths must be canonical") from exc
        safe_names = [name for name, _value in self.safe_query_parameters]
        if safe_names != sorted(safe_names) or len(set(safe_names)) != len(safe_names):
            raise ValueError("safe query parameters must have sorted unique names")
        if any(not _valid_query_name(name) or _looks_secret(name) for name in safe_names):
            raise ValueError("safe query parameter name is not admissible")
        if any(
            not value or len(value) > 4096 or "\r" in value or "\n" in value
            for _name, value in self.safe_query_parameters
        ):
            raise ValueError("safe query parameter value is not admissible")
        if self.redacted_query_parameter_names != tuple(
            sorted(set(self.redacted_query_parameter_names))
        ):
            raise ValueError("redacted query parameter names must be sorted and unique")
        if any(not _valid_query_name(name) for name in self.redacted_query_parameter_names):
            raise ValueError("redacted query parameter name is not admissible")
        if set(safe_names) & set(self.redacted_query_parameter_names):
            raise ValueError("redacted query names cannot also carry stored values")
        header_names = [name for name, _value in self.response_headers]
        if header_names != sorted(header_names) or len(set(header_names)) != len(header_names):
            raise ValueError("response headers must have sorted unique names")
        if any(name not in _SAFE_RESPONSE_HEADERS for name in header_names):
            raise ValueError("response header is not safe to persist")
        if any(
            len(value) > 4096 or "\r" in value or "\n" in value
            for _name, value in self.response_headers
        ):
            raise ValueError("response header value is not safe to persist")
        if self.redirect_hops >= self.network_requests:
            raise ValueError("redirect hops must be below the total network request count")
        return self


class BoundedHttpResponse(BaseModel):
    """Bounded raw response bytes plus safe snapshot-request metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    metadata: SafeResponseMetadata
    body: bytes = Field(repr=False)


class BoundedHttpClient:
    """Execute exact endpoint requests without accepting caller-supplied URLs."""

    def __init__(
        self,
        *,
        endpoint: EndpointPolicy,
        policy: TransportPolicy,
        client: httpx.Client | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._endpoint = endpoint
        self._policy = policy
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._jitter = jitter
        self._owns_client = client is None
        self._timeout = httpx.Timeout(
            connect=policy.connect_timeout_s,
            read=policy.read_timeout_s,
            write=policy.write_timeout_s,
            pool=policy.pool_timeout_s,
        )
        self._client = client or httpx.Client(
            timeout=self._timeout,
            follow_redirects=False,
            http2=False,
        )

    def __enter__(self) -> BoundedHttpClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close only a client created by this boundary."""

        if self._owns_client:
            self._client.close()

    def fetch(
        self,
        path: str,
        *,
        query: Mapping[str, QueryValue] | None = None,
        sensitive_query: Mapping[str, QueryValue] | None = None,
        secret_query: Mapping[str, str] | None = None,
    ) -> BoundedHttpResponse:
        """Fetch one allowlisted HTTPS resource under all configured bounds."""

        canonical_path = _canonical_path(path)
        self._check_path(canonical_path)
        safe_query = _validated_safe_query(query or {}, self._endpoint)
        sensitive = _validated_sensitive_query(sensitive_query or {}, self._endpoint)
        secrets = _validated_secret_query(secret_query or {}, self._endpoint)
        combined_query = {**dict(safe_query), **sensitive, **secrets}

        start_monotonic = self._monotonic()
        started_at = _aware_utc(self._utc_now())
        deadline = start_monotonic + self._policy.total_deadline_s
        url = httpx.URL(scheme="https", host=self._endpoint.host, path=canonical_path)
        redirect_hops = 0
        network_requests = 0
        final_path = canonical_path
        first_request = True

        while True:
            attempt = 0
            while True:
                attempt += 1
                network_requests += 1
                self._check_deadline(deadline)
                try:
                    outcome = self._request_once(
                        url,
                        query=combined_query if first_request else None,
                        deadline=deadline,
                    )
                except httpx.HTTPError:
                    if attempt >= self._policy.max_attempts:
                        raise ManchesterTransportError("network_failure") from None
                    self._backoff(attempt, deadline)
                    continue

                response, body = outcome
                if response.status_code in self._policy.retry_status_codes:
                    if attempt >= self._policy.max_attempts:
                        raise ManchesterTransportError(
                            "retry_exhausted", status_code=response.status_code
                        )
                    self._backoff(attempt, deadline)
                    continue
                break

            if response.status_code in _REDIRECT_STATUSES:
                if redirect_hops >= self._policy.max_redirects:
                    raise ManchesterTransportError("redirect_limit_exceeded")
                location = response.headers.get("location")
                if not location:
                    raise ManchesterTransportError("redirect_location_missing")
                next_url = response.url.join(location)
                self._check_redirect(response.url, next_url)
                url = next_url
                final_path = _canonical_path(next_url.path)
                redirect_hops += 1
                first_request = False
                continue

            if not 200 <= response.status_code < 300:
                raise ManchesterTransportError(
                    "http_status_rejected", status_code=response.status_code
                )
            finished_at = _aware_utc(self._utc_now())
            metadata = SafeResponseMetadata(
                endpoint_id=self._endpoint.endpoint_id,
                host=self._endpoint.host,
                request_path=canonical_path,
                final_path=final_path,
                safe_query_parameters=safe_query,
                redacted_query_parameter_names=tuple(sorted(set(sensitive) | set(secrets))),
                status_code=response.status_code,
                response_headers=_safe_headers(response.headers),
                retrieval_started_at_utc=started_at,
                retrieval_finished_at_utc=finished_at,
                network_requests=network_requests,
                redirect_hops=redirect_hops,
            )
            return BoundedHttpResponse(metadata=metadata, body=body)

    def _request_once(
        self,
        url: httpx.URL,
        *,
        query: Mapping[str, str] | None,
        deadline: float,
    ) -> tuple[httpx.Response, bytes]:
        with self._client.stream(
            "GET",
            url,
            params=query,
            follow_redirects=False,
            timeout=self._timeout,
        ) as response:
            if response.status_code in _REDIRECT_STATUSES:
                return response, b""
            if response.status_code in self._policy.retry_status_codes:
                return response, b""
            if not 200 <= response.status_code < 300:
                return response, b""
            self._check_response_headers(response)
            body = bytearray()
            decoder = _BoundedContentDecoder(response.headers.get("content-encoding"))
            for chunk in response.iter_raw():
                self._check_deadline(deadline)
                body.extend(chunk)
                if len(body) > self._policy.max_response_bytes:
                    raise ManchesterTransportError("response_size_exceeded")
                decoder.consume(chunk, limit=self._policy.max_response_bytes)
            decoder.finish(limit=self._policy.max_response_bytes)
            return response, bytes(body)

    def _check_response_headers(self, response: httpx.Response) -> None:
        content_type = response.headers.get("content-type")
        if not content_type:
            if self._policy.require_content_type:
                raise ManchesterTransportError("content_type_missing")
        else:
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type not in self._policy.allowed_media_types:
                raise ManchesterTransportError("content_type_rejected")
        content_length = response.headers.get("content-length")
        if content_length is not None:
            if not content_length.isdigit():
                raise ManchesterTransportError("content_length_invalid")
            if int(content_length) > self._policy.max_response_bytes:
                raise ManchesterTransportError("response_size_exceeded")
        content_encoding = response.headers.get("content-encoding")
        if content_encoding not in {None, "", "identity", "gzip", "deflate"}:
            raise ManchesterTransportError("content_encoding_rejected")

    def _check_redirect(self, current: httpx.URL, target: httpx.URL) -> None:
        if (
            target.scheme != "https"
            or target.host != self._endpoint.host
            or target.port not in {None, 443}
            or target.userinfo
            or target.fragment
        ):
            raise ManchesterTransportError("redirect_target_rejected")
        target_path = _canonical_path(target.path)
        self._check_path(target_path)
        if target.query and target.query != current.query:
            raise ManchesterTransportError("redirect_query_rejected")

    def _check_path(self, path: str) -> None:
        if not any(_path_has_prefix(path, prefix) for prefix in self._endpoint.path_prefixes):
            raise ManchesterTransportError("path_not_allowlisted")

    def _check_deadline(self, deadline: float) -> None:
        if self._monotonic() > deadline:
            raise ManchesterTransportError("total_deadline_exceeded")

    def _backoff(self, attempt: int, deadline: float) -> None:
        ceiling = min(
            self._policy.backoff_max_s,
            self._policy.backoff_base_s * (2 ** (attempt - 1)),
        )
        delay = ceiling * min(max(self._jitter(), 0.0), 1.0)
        remaining = deadline - self._monotonic()
        if remaining <= 0 or delay >= remaining:
            raise ManchesterTransportError("total_deadline_exceeded")
        self._sleep(delay)


def _validated_safe_query(
    query: Mapping[str, QueryValue], endpoint: EndpointPolicy
) -> tuple[tuple[str, str], ...]:
    unexpected = set(query) - set(endpoint.query_parameter_names)
    if unexpected:
        raise ManchesterTransportError("query_parameter_rejected")
    values: list[tuple[str, str]] = []
    for name, value in query.items():
        if _looks_secret(name):
            raise ManchesterTransportError("secret_in_safe_query")
        values.append((name, _query_value(value)))
    return tuple(sorted(values))


def _validated_secret_query(query: Mapping[str, str], endpoint: EndpointPolicy) -> dict[str, str]:
    unexpected = set(query) - set(endpoint.secret_query_parameter_names)
    if unexpected:
        raise ManchesterTransportError("secret_query_parameter_rejected")
    result: dict[str, str] = {}
    for name, value in query.items():
        if not value or len(value) > 4096 or any(character in value for character in "\r\n"):
            raise ManchesterTransportError("secret_query_value_rejected")
        result[name] = value
    return result


def _validated_sensitive_query(
    query: Mapping[str, QueryValue], endpoint: EndpointPolicy
) -> dict[str, str]:
    unexpected = set(query) - set(endpoint.sensitive_query_parameter_names)
    if unexpected:
        raise ManchesterTransportError("sensitive_query_parameter_rejected")
    return {name: _query_value(value) for name, value in query.items()}


def _query_value(value: QueryValue) -> str:
    if isinstance(value, bool):
        result = "true" if value else "false"
    elif isinstance(value, int):
        result = str(value)
    elif isinstance(value, float):
        if not isfinite(value):
            raise ManchesterTransportError("query_value_rejected")
        result = str(value)
    elif isinstance(value, str):
        result = value
    else:
        raise ManchesterTransportError("query_value_rejected")
    if not result or len(result) > 4096 or any(character in result for character in "\r\n"):
        raise ManchesterTransportError("query_value_rejected")
    return result


def _canonical_path(value: str) -> str:
    if (
        not value.startswith("/")
        or "\\" in value
        or "?" in value
        or "#" in value
        or "\x00" in value
    ):
        raise ManchesterTransportError("path_rejected")
    decoded = value
    for _ in range(3):
        decoded_once = unquote(decoded)
        if decoded_once == decoded:
            break
        decoded = decoded_once
    path = PurePosixPath(decoded)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ManchesterTransportError("path_rejected")
    canonical = path.as_posix()
    if not canonical.startswith("/"):
        canonical = f"/{canonical}"
    if decoded.endswith("/") and canonical != "/":
        canonical += "/"
    if canonical != decoded:
        raise ManchesterTransportError("path_rejected")
    return canonical


def _path_has_prefix(path: str, prefix: str) -> bool:
    if path == prefix:
        return True
    boundary = prefix if prefix.endswith("/") else f"{prefix}/"
    return path.startswith(boundary)


def _valid_query_name(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z][A-Za-z0-9_.\[\]-]{0,63}", value) is not None


def _looks_secret(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _safe_headers(headers: httpx.Headers) -> tuple[tuple[str, str], ...]:
    return tuple((name, headers[name]) for name in _SAFE_RESPONSE_HEADERS if name in headers)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ManchesterTransportError("utc_clock_invalid")
    return value.astimezone(UTC)


class _BoundedContentDecoder:
    """Count decoded transfer bytes while retaining the exact wire body."""

    def __init__(self, encoding: str | None) -> None:
        self._encoding = encoding or "identity"
        self._decoded_bytes = 0
        self._decoder: _ZlibDecoder | None
        if self._encoding == "gzip":
            self._decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif self._encoding == "deflate":
            self._decoder = zlib.decompressobj(zlib.MAX_WBITS)
        else:
            self._decoder = None

    def consume(self, chunk: bytes, *, limit: int) -> None:
        """Admit one raw chunk only if its decoded output remains bounded."""

        if self._decoder is None:
            self._decoded_bytes += len(chunk)
            self._check_limit(limit)
            return
        remaining_input = chunk
        try:
            while remaining_input:
                remaining_output = limit - self._decoded_bytes
                output = self._decoder.decompress(remaining_input, remaining_output + 1)
                self._decoded_bytes += len(output)
                self._check_limit(limit)
                remaining_input = self._decoder.unconsumed_tail
        except zlib.error as exc:
            raise ManchesterTransportError("content_encoding_invalid") from exc

    def finish(self, *, limit: int) -> None:
        """Require a complete single encoded stream and bound its final output."""

        if self._decoder is None:
            return
        try:
            remaining_output = limit - self._decoded_bytes
            output = self._decoder.flush(remaining_output + 1)
        except zlib.error as exc:
            raise ManchesterTransportError("content_encoding_invalid") from exc
        self._decoded_bytes += len(output)
        self._check_limit(limit)
        if not self._decoder.eof or self._decoder.unused_data:
            raise ManchesterTransportError("content_encoding_invalid")

    def _check_limit(self, limit: int) -> None:
        if self._decoded_bytes > limit:
            raise ManchesterTransportError("response_size_exceeded")


class _ZlibDecoder(Protocol):
    """Structural subset of the private typeshed zlib decoder type."""

    @property
    def unconsumed_tail(self) -> bytes: ...

    @property
    def unused_data(self) -> bytes: ...

    @property
    def eof(self) -> bool: ...

    def decompress(self, data: bytes, max_length: int = 0) -> bytes: ...

    def flush(self, length: int = ...) -> bytes: ...
