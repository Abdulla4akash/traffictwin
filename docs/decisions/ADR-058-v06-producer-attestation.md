# ADR-058: Operator clean-checkout attestation for v0.6 registry provenance

Status: accepted (repository owner approved the recommended policy from the
[v0.7 external decision pack](../v07_external_decision_pack.md) on 24 July 2026)

## Context

`REL-01` migration and activation were blocked by open question 15: a structurally valid
registry does not encode which package produced it, and the frozen v0.6 SQLite schema records
schema migrations but no verifiable producing checkout. The implemented compatibility preview
therefore fixes `source_product_version` to unknown, and automatic activation is
unrepresentable.

## Decision

A v0.6 registry may claim `v0.6.0` producer provenance only through an explicit operator
attestation created after running the immutable `v0.6.0` tag from a clean checkout against that
registry. The typed attestation binds, at attestation time:

- the exact tag name `v0.6.0` and tag commit `1c50a25246426128ac6e8530240eff362d16be02`;
- the producer package version `0.6.0`;
- the exact registry SHA-256 and byte size;
- a timezone-aware attestation instant; and
- the operator's literal statement that the registry was produced or re-verified by that clean
  checkout.

Verification re-hashes the current registry bytes and fails closed on any drift, naive
timestamp, or altered tag/commit/version literal. A verified attestation is provenance
evidence only: it does not approve migration, activation, rollback, or any capability, and
weaker bases (schema shape, file location, operator memory without the statement) remain
refused.

## Consequences

- The migration/backup/activation/rollback build-out can proceed against attested sources.
- TrafficTwin never manufactures provenance: the operator action and statement remain the
  irreducible human step, and an unattested registry keeps `source_product_version` unknown.
- The attestation model is versioned; changing the accepted basis requires a new ADR.
