# ADR-054: Bounded Manchester Acquisition Transport and Hardened Parsing

- Status: accepted (Gate A decision; Gate B must implement and accept before any adapter exists)
- Date: 2026-07-22
- Capability: `MAN-01` (audit half) and the `MAN-02`–`MAN-05` transport boundary

## Context

The v0.7 design requires allowlisted HTTPS acquisition with bounded timeouts, redirects, retries,
pages, bytes, and decompressed bytes, hardened XML parsing for SIRI-VM, and credential privacy
(design §3.9–§3.12, §18.1). The current package contains no HTTP client, no XML hardening, and no
network code at all, so these are new dependency decisions. The Gate A audit
([manchester-source-gate-a-audit-v0_7.md](../integration/manchester-source-gate-a-audit-v0_7.md))
confirmed the concrete threat surface: an anonymous unversioned DfT JSON API plus bulk zips on a
shared Google Storage host, an anonymous WebTRIS JSON API with mandatory pagination and an
announced multi-month 2026 interruption, an anonymous TfGM zip whose URL is overwritten in place,
and a BODS SIRI-VM XML feed authenticated by an **API key in the URL query string**.

Documented library facts (fetched 2026-07-22): `httpx` enforces default timeouts, does not follow
redirects by default, and does not retry by default (python-httpx.org); `requests` has no default
timeout and follows redirects by default (requests.readthedocs.io); the stdlib `xml` module's
entity-expansion protections depend on the runtime Expat version (docs.python.org/3/library/xml.html);
`defusedxml` 0.7.1 provides a purpose-built hardened `ElementTree`; the stdlib `zipfile`/`gzip`
docs acknowledge decompression bombs and document no built-in protection.

## Decision

1. **HTTP client: `httpx>=0.28.1,<1`** (BSD licence), HTTP/1.1 only (no `http2` extra).
   The reviewed stable release is 0.28.1; Gate B must lock an exact resolved version. Rationale: its
   defaults match the fail-closed posture — timeouts on, redirects off, retries off — so safety
   does not depend on remembering per-call arguments. `requests` is rejected because its
   defaults (no timeout, follow redirects) invert that posture.
2. **Explicit transport policy object per source adapter**, no ambient defaults: connect/read/
   write/pool timeouts always set; total-deadline enforced by the caller; redirects disabled at
   the client and re-enabled only as an explicit same-host, depth-limited follow with each hop
   recorded in snapshot metadata (cross-host redirects fail closed as findings); retries only for
   idempotent GETs on retryable failures (connect errors, 5xx, 429), bounded attempts with
   jittered backoff, never on 4xx.
3. **Allowlist by exact HTTPS host and path family.** The DfT bulk entry is path-prefixed
   (`storage.googleapis.com/dft-statistics/road-traffic/`) because the host is shared
   multi-tenant storage. No user-supplied URL, host, port, or scheme is ever accepted.
4. **Response-size enforcement on the stream.** Bodies are read via the streaming API against a
   per-source byte ceiling; `Content-Length` is advisory only. Page-count and row caps bound
   paginated reads (WebTRIS report endpoints require pagination; `page_size` is self-capped).
5. **Credentials never appear in URLs at rest.** Secrets come only from environment or
   `st.secrets`. Because BODS transmits `api_key` as a query parameter, request URLs are never
   logged, and snapshot request metadata persists the endpoint identity with all credential and
   otherwise-sensitive query values removed (the existing design §8 rule made concrete). Keys are
   never fingerprinted into artifacts or sent to any other host.
6. **XML/SIRI parsing: `defusedxml==0.7.1`** for all untrusted XML. Every parse call explicitly
   sets `forbid_dtd=True`, `forbid_entities=True`, and `forbid_external=True`; the first option
   defaults to false and must not be implicit. Parsing runs only after the byte ceiling has been
   enforced on the raw bytes. At startup the adapter records `pyexpat.EXPAT_VERSION` in diagnostic
   metadata, because stdlib protections are Expat-version-dependent. If `lxml` is ever
   introduced for performance, it must be constructed with entity/DTD/network resolution and
   `huge_tree` explicitly disabled rather than relying on version-dependent defaults; the
   deprecated `defusedxml.lxml` shim is not used.
7. **Compression and archive bounds are adapter code**, because the stdlib provides none:
   streamed gzip/deflate decompression with an output-byte ceiling; zip handling with member
   count, per-member size, total size, and compression-ratio caps; rejection of nested archives,
   absolute paths, path traversal, symlinks, duplicate member names, and unexpected content
   types. Only expected members are extracted (e.g. the TfGM CSV/GeoJSON/prj members; the KML
   member is not parsed).
8. **Raw-before-parse invariant.** Exact response bytes are hashed and published to the immutable
   snapshot area before any parsing; hashes are rechecked before acceptance; failed or partial
   fetches quarantine and never replace the last accepted snapshot (design §8 unchanged).
9. Dependency additions (`httpx`, `defusedxml`, and pins) happen at Gate B through the normal
   lead-owned `pyproject.toml`/lock process; this ADR adds nothing to packaging now.

## Consequences

- Every acquisition failure mode maps to a typed finding and a quarantined snapshot, never a
  partially replaced accepted state.
- BODS key leakage is prevented structurally (no URL logging, stripped snapshot metadata) rather
  than by reviewer vigilance.
- The Expat-version record makes the XML trust boundary auditable on any user machine.
- Open items tracked in the audit: absent rate-limit policies (`GA-DFT-2`, `GA-WT-5`,
  `GA-BODS-3`) requiring conservative self-imposed bounds, and
  the sign-in-gated GTFS-RT path (`GA-BODS-1`).

## Rejected alternatives

- `requests`: unsafe defaults for this posture (no timeout, redirects on) — every call site would
  need to remember to re-arm safety.
- Raw stdlib `xml.etree` alone: protection depends on the runtime Expat version, which
  TrafficTwin cannot guarantee on user machines.
- Host-wide allowlisting of `storage.googleapis.com`: rejected; it would allowlist arbitrary
  third-party buckets.
- Automatic background retry daemons or long-lived connection pools in Streamlit pages: rejected;
  network sync stays a separate bounded operation per the design.
