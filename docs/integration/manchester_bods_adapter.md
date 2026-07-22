# Manchester BODS SIRI-VM adapter (`MAN-05` candidate)

## Status and boundary

`src/traffictwin/integration/manchester/bods.py` is the offline, deterministic parser half of
`MAN-05`. It parses one already-acquired immutable SIRI-VM XML member. It performs no HTTP
request, reads no API key, launches no simulator, writes no snapshot, and does not activate the
`MAN-05` capability by itself.

The remaining live acquisition and acceptance work is deliberately outside this parser:

- a BODS account/API key and a credential-redacting bounded client;
- one accepted private real Greater Manchester response at Gate B;
- verification of the observed `OperatorRef` values (`GA-BEE-1`);
- an approved retention policy for raw longitudinal vehicle identifiers; and
- outage/service-notice handling around acquisition.

Until those checks pass, the parser outputs Greater Manchester-scope **bus/transit positions
with operator membership unverified**, not “live Bee Network traffic”.

## Accepted input

The parser accepts an exact `(BodsMemberRef, bytes)` pair plus `BodsParseScope`:

- the member has an immutable snapshot ID, path, SHA-256, `private_raw` class, and explicit
  synthetic flag;
- the SHA-256 is verified before XML parsing;
- the XML root and every element must use the SIRI namespace;
- DTDs, entities, external references, oversized input, excessive elements/depth/attributes,
  and excessive text are refused by the shared hardened XML boundary;
- the audited mandatory SIRI-VM fields must occur exactly once; and
- all timestamps must use explicit `Z` UTC syntax.

`Velocity`, `Occupancy`, and `DestinationName` are optional and remain `None` when absent. The
parser never fills or interpolates a position, timestamp, speed, destination, or identifier.

## Deterministic output

`parse_bods_siri_vm(...)` returns a strict, frozen `BodsParseReport` containing:

- complete activity accounting (`seen`, accepted, malformed, out of bounds, duplicates,
  conflicts, and every freshness state);
- typed, redacted findings without payload text or vehicle identifiers;
- accepted `LiveTransitVehicleObservation` records in deterministic order; and
- explicit negative capability flags for retention, public export, raw-ID output, and Bee
  membership.

The raw `VehicleRef` is used only inside the parse to deduplicate
`(VehicleRef, RecordedAtTime)`. Derived observations receive a 24-character SHA-256 token salted
with the snapshot ID. This token is stable only inside that snapshot and changes in the next
snapshot. Raw evidence remains private and immutable; derived records cannot expose or join the
raw identifier across snapshots.

## Freshness policy

`bods_freshness_state(...)` implements the frozen `manchester-freshness-v1` policy without
reading the wall clock:

- synthetic input is always `synthetic`;
- accepted offline replay is always `historical`;
- live mode is `live_vehicle` only when
  `RecordedAtTime <= evaluated_at_utc <= ValidUntilTime` and age is at most 60 seconds; and
- future-dated, expired, or older live-mode observations are `stale`.

The caller supplies the UTC evaluation instant, so repeating a parse produces the same output.
The 60-second limit is TrafficTwin policy, not a BODS uptime or latency guarantee.

## Semantic restrictions

Every observation is structurally restricted to bus/transit meaning:

- no road-traffic volume;
- no private-vehicle flow or general congestion claim;
- no complete-fleet claim;
- no passenger/person inference; and
- no public export while the retention decision is unapproved.

`OperatorRef`, `PublishedLineName`, geography, and strings containing “Bee Network” cannot decide
Bee Network membership. `bee_network_membership` remains `unverified` and the membership
capability remains false while `GA-BEE-1` is open, as required by ADR-057.

## Library usage

```python
from datetime import UTC, datetime
from decimal import Decimal

from traffictwin.integration.manchester.bods import (
    BodsBoundingBox,
    BodsMemberRef,
    BodsParseScope,
    parse_bods_siri_vm,
)
from traffictwin.integration.manchester.models import sha256_hex

xml_bytes = accepted_private_member_bytes
reference = BodsMemberRef(
    snapshot_id="bods-20260722T120020Z-abcdef012345",
    member_path="private/raw/siri-vm.xml",
    member_sha256=sha256_hex(xml_bytes),
    synthetic=False,
)
parse_scope = BodsParseScope(
    evaluated_at_utc=datetime(2026, 7, 22, 12, 0, 30, tzinfo=UTC),
    mode="live",
    bounding_box=BodsBoundingBox(
        min_longitude=Decimal("-3.2"),
        min_latitude=Decimal("53.3"),
        max_longitude=Decimal("-1.9"),
        max_latitude=Decimal("53.7"),
    ),
)
report = parse_bods_siri_vm((reference, xml_bytes), parse_scope)
```

This example intentionally assumes the bytes have already crossed the reviewed snapshot
boundary. Do not put a BODS API key or an unredacted request URL in source code, logs, manifests,
or documentation.

## Verification

Run the isolated offline suite:

```bash
.venv/bin/pytest -q tests/unit/test_manchester_bods.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/bods.py \
  tests/unit/test_manchester_bods.py
.venv/bin/mypy \
  src/traffictwin/integration/manchester/bods.py \
  tests/unit/test_manchester_bods.py
```

The repository fixture is explicitly synthetic and contains no real observation. Real BODS XML
must stay private; a future Gate-B acceptance test may publish only reviewed redacted aggregates
or metadata.

## Evidence basis

The contract follows the accepted
[Manchester Gate-A audit](manchester-source-gate-a-audit-v0_7.md),
[ADR-054](../decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md),
[ADR-055](../decisions/ADR-055-manchester-time-basis.md), and
[ADR-057](../decisions/ADR-057-bee-network-membership-identifiers.md). The authoritative external
schema basis is the DfT
[SIRI-VM technical guidance](https://www.gov.uk/government/publications/technical-guidance-publishing-location-data-using-the-bus-open-data-service-siri-vm/technical-guidance-siri-vm).
