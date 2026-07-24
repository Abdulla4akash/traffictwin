"""Audited mapping from bounded transport responses to snapshot primitives."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from traffictwin.integration.manchester.models import (
    ManchesterHttpMetadata,
    ManchesterRawMember,
    ManchesterRequestIdentity,
    ManchesterRetrievalWindow,
    sha256_hex,
)
from traffictwin.integration.manchester.transport import BoundedHttpResponse


class ManchesterHttpSnapshotParts(BaseModel):
    """Secret-free provenance and exact raw bytes for one bounded HTTP response."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    request: ManchesterRequestIdentity
    retrieval: ManchesterRetrievalWindow
    http: ManchesterHttpMetadata
    member: ManchesterRawMember
    payload: bytes


def snapshot_parts_from_http_response(
    response: BoundedHttpResponse,
    *,
    relative_path: str,
    media_type: str,
) -> ManchesterHttpSnapshotParts:
    """Map the sole transport result into the sole snapshot provenance contract.

    The function does not parse, normalise, publish, or log the body. Sensitive
    and secret values are already absent from ``SafeResponseMetadata``; only
    their sorted names survive in the request identity.
    """

    metadata = response.metadata
    headers = dict(metadata.response_headers)
    declared_content_length = _declared_content_length(headers.get("content-length"))
    response_content_type = _bare_media_type(headers.get("content-type"))
    if response_content_type is not None and response_content_type != media_type:
        raise ValueError("snapshot member media type does not match the bounded response")
    request = ManchesterRequestIdentity(
        host=metadata.host,
        path=metadata.request_path,
        parameters=metadata.safe_query_parameters,
        redacted_parameter_names=tuple(
            sorted(
                set(metadata.redacted_query_parameter_names) | set(metadata.redacted_header_names)
            )
        ),
    )
    retrieval = ManchesterRetrievalWindow(
        started_at_utc=metadata.retrieval_started_at_utc,
        completed_at_utc=metadata.retrieval_finished_at_utc,
    )
    http = ManchesterHttpMetadata(
        status_code=metadata.status_code,
        final_path=metadata.final_path,
        network_requests=metadata.network_requests,
        redirect_hops=metadata.redirect_hops,
        response_content_type=response_content_type,
        response_content_encoding=_content_encoding(headers.get("content-encoding")),
        declared_content_length=declared_content_length,
        etag=headers.get("etag"),
        last_modified=headers.get("last-modified"),
    )
    member = ManchesterRawMember(
        relative_path=relative_path,
        byte_size=len(response.body),
        media_type=media_type,
        sha256=sha256_hex(response.body),
    )
    return ManchesterHttpSnapshotParts(
        request=request,
        retrieval=retrieval,
        http=http,
        member=member,
        payload=response.body,
    )


def _declared_content_length(value: str | None) -> int | None:
    if value is None:
        return None
    if not value.isdigit():
        raise ValueError("transport metadata contains an invalid content length")
    return int(value)


def _bare_media_type(value: str | None) -> str | None:
    if value is None:
        return None
    return value.split(";", 1)[0].strip().lower()


def _content_encoding(value: str | None) -> Literal["gzip", "deflate"] | None:
    if value in {None, "", "identity"}:
        return None
    if value == "gzip":
        return "gzip"
    if value == "deflate":
        return "deflate"
    raise ValueError("transport metadata contains an unsupported content encoding")
