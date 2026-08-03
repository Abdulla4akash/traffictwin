# National Highways Accepted-Snapshot Transitions

Phase 194 implements the bounded `NEXT-04` comparison service. It compares only a caller-confirmed
consecutive pair of complete, accepted National Highways parser reports with the same product,
study envelope, feed/model contract and evidence class. It performs no provider request and does
not activate persistence or a UI page.

The service uses the existing opaque `record_token` as the comparison key and the source-record
fingerprint as content identity. It emits exactly one reconciled state per token:
`first_seen`, `content_changed`, `unchanged`, `no_longer_listed`, `validity_expired`, or
`reappeared`. Reappearance requires bounded prior-presence memory; it is never inferred from one
pair alone. Changed fields use a closed allowlist, with `unprojected_source_content` when the raw
fingerprint changed but no safe projected field did.

Absence wording is deliberately “No longer listed in the latest accepted feed.” It is not a claim
that a road cleared or a sign was removed. Failed, partial, time-reversed, product-mixed,
scope-changed or model-changed pairs refuse before comparison. Literal VMS display text and
measured speed, flow, congestion and city-road claims remain unavailable.

Private transition rows retain only the opaque token, fingerprints, allowlisted field names,
source publication times and exact snapshot lineage. `public_transition_aggregate()` removes
tokens, rows and locations and still marks public release unapproved. A licence/publication review
is required before any public artifact is released.

See [National Highways operational feeds](manchester_national_highways_operational_feeds.md),
[aggregate operational history](manchester_operational_history.md), and the
[canonical v0.7 design](../traffictwin-design-v0_7.md).
