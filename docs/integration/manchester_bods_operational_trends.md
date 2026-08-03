# BODS Identifier-Free Operational Trends

Phase 195 implements the bounded `NEXT-05` aggregate contract. A successful artifact is derived
inside the verified `BodsLiveRefresh` boundary while records are still in memory; only reconciled
counts, source-time statistics and contract fingerprints leave that function. A failed attempt
contains an allowlisted safe code and zero response counts.

The artifact records accepted/live/stale/synthetic/historical, outside-box, malformed, duplicate,
conflicting-duplicate and exact Bee-membership totals. It retains a distinct-operator count but no
operator name or code. It calculates exact integer-millisecond minimum, nearest-rank median,
nearest-rank p95 and maximum source age, negative-age/skew count, earliest/latest source time and
comparable successful-update cadence.

Vehicle, journey, service, block, line, coordinate, bearing, operator and salted/pseudonymised
tokens are forbidden from the output. Operator distinctness is response coverage, not fleet or
service completeness. Source-time cadence is not bus speed, road speed, progression speed or a
trajectory.

Trend windows use explicit UTC bounds and a caller-declared automatic-attempt denominator. Missing
intervals are never inferred from successful rows. Fewer than two successes is status-only and is
marked `single_or_no_success`; it does not draw a trend. Stable UTC-day rollups bind the exact
attempt fingerprints. These are library projections only: no real writer, long-term partition,
page or public export is activated.

See [aggregate operational history](manchester_operational_history.md),
[BODS live source](manchester_bods_live.md), and the
[canonical v0.7 design](../traffictwin-design-v0_7.md).
