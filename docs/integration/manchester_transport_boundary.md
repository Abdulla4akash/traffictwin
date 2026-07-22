# Manchester Bounded Transport, XML, and Archive Boundary

Status: **candidate Gate B library evidence; no source adapter or `MAN-*` capability is accepted**

This library implements the transport and untrusted-input controls selected by
[ADR-054](../decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md). It does
not know DfT, WebTRIS, TfGM, or BODS record semantics, write accepted snapshots, project canonical
records, or run from a Streamlit page. Source adapters must supply exact endpoint and resource
policies and then hand the returned raw bytes to
`quarantine_validate_and_promote` or `publish_manchester_quarantine` before parsing. Direct parsing
of a just-fetched response is outside the accepted boundary.

## Bounded HTTP transport

`traffictwin.integration.manchester.transport.BoundedHttpClient` accepts an `EndpointPolicy` and
`TransportPolicy`, never an arbitrary URL. The endpoint policy freezes one lowercase DNS host,
canonical path families, ordinary typed query names, sensitive query names whose values must be
redacted from metadata, and secret query names such as BODS `api_key`.

The transport enforces:

- HTTPS, exact-host and path-prefix admission;
- connect/read/write/pool timeouts plus a caller-visible total deadline;
- redirects disabled in httpx and manually followed only to the same HTTPS host and admitted path;
- explicit bounded retry status codes and attempts with bounded jittered backoff;
- streamed wire-byte ceilings independent of `Content-Length`, plus bounded gzip/deflate
  validation under the same ceiling while retaining the exact encoded response bytes;
- an exact media-type allowlist;
- URL-redacted typed failures with no response body; and
- safe response metadata containing paths, admitted ordinary parameters, redacted parameter names,
  selected safe headers, UTC retrieval times, request count, and redirect count—but never a full
  URL, credential, sensitive parameter value, or raw response body.

The response body is exact post-HTTP-decoding bytes. The caller must publish those bytes through
the immutable snapshot service before parsing them.

## XML boundary

`traffictwin.integration.manchester.xml.parse_xml` uses `defusedxml==0.7.1` and explicitly sets
`forbid_dtd=True`, `forbid_entities=True`, and `forbid_external=True`. It first enforces the input
byte ceiling, then checks the accepted root name and namespaces, element count, maximum depth,
attributes per element, and total text/attribute characters. Its result records the runtime Expat
version and resource counts. Malformed input and forbidden constructs return one typed,
payload-free error.

`parse_gzip_xml` applies bounded gzip decompression before the same XML boundary.

## Compression and archive boundary

`traffictwin.integration.manchester.archive` reads compressed input only in memory. Its explicit
policy bounds compressed bytes, decompressed bytes, member bytes, member count, compression ratio,
and admitted member suffixes.

Gzip output is streamed against byte and ratio ceilings. Zip processing validates the complete
central-directory inventory and actual output, rejects absolute/traversal/non-canonical paths,
duplicates, encryption, symlinks, special files, nested archives, unexpected types, missing
selected members, malformed streams, and declared-versus-actual size drift. Only caller-selected
members are returned, in deterministic order; nothing is extracted to the filesystem.

## Evidence boundary

The focused synthetic suite covers successful byte preservation, query and credential redaction,
path and redirect refusal, retries, time/size/media-type limits, archive inventories and bombs,
unsafe members, DTD/entity/external-reference refusal, namespaces, and every XML resource bound.
It is software-safety evidence only. Real-source schema correctness, source availability, legal
publication, immutable snapshot acceptance, freshness, and canonical projection remain Gate B
work.
