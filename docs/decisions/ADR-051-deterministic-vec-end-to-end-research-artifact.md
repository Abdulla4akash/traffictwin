# ADR-051: Deterministic VEC End-to-End Research Artifact

Status: accepted

## Context

VEC-01 through VEC-11 produce separate source audits, contracts, execution/reproduction evidence,
joins, scientific admission, interface evidence, and a permission-bounded publication pack. A
dissertation claim needs one artifact that binds those records without copying prohibited raw
inputs or implying that hashes, permissions, or unavailable fields establish stronger science.

## Decision

VEC-12 uses a closed deterministic ZIP contract. It contains only an exact allowlist of
audit/software metadata, accepted reports, generated contracts, citations, limitations,
provenance, and the VEC-11 sanitised sample/aggregates. Sorted members use stored compression,
fixed timestamps and modes, bounded sizes, SHA-256 inventory entries, and a checksum file. A
content-derived manifest ID binds the complete reconciled claim state. A separate receipt hashes
the final ZIP.

The offline verifier reads without extraction and rejects an unexpected/order-drifted member,
duplicate, traversal path, symlink, compression/timestamp drift, oversize content, checksum or
manifest mismatch, and private local path. Creation is atomic and new-only.

The manifest names VEC-08's protocol-seed reproduction separately from VEC-09/VEC-11's `_s102`
best-of-seeds result. It records unavailable metrics, diagnostic readiness, non-causal status,
permission limits, and complete excluded material as first-class fields.

## Consequences

- A reviewer can verify the checked-in VEC evidence chain offline and reproduce its exact bytes.
- Upstream generated evidence drift prevents publication instead of silently changing the claim.
- The archive is not a general raw-data or source redistribution format.
- Checksums establish byte identity, not source correctness or causal validity.
- Public hosting, formal licensing, physical completion, per-task energy, confirmed transfers, and
  blocked diagnostic findings remain outside the accepted claim.
