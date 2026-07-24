# Bee Network identifier scope (`MAN-05` candidate)

## Status

TrafficTwin now has a versioned, identifier-only Bee Network classification boundary for accepted
BODS positions. It closes `GA-BEE-1` only for the five operator references observed in the
accepted 23 July 2026 private snapshot. `MAN-05` remains `planned`: retention, consumer terms,
reference-table licensing, complete service coverage and full Gate-B acceptance remain open.

The aggregate machine evidence is
[`manchester_bods_bee_network_probe_20260723.json`](evidence/manchester_bods_bee_network_probe_20260723.json).
No response body, coordinate, line inventory, raw vehicle identifier, credential or private path is
contained in that record.

## Verified policy

Policy `bee-network-operator-allowlist-v1-20260723` uses the SIRI-VM `OperatorRef` field only. One
accepted private Greater Manchester response contained 1,565 parser-admitted positions across 27
operator references:

| Live-verified operator | Positions observed |
|---|---:|
| `BNDB` | 92 |
| `BNFM` | 32 |
| `BNGN` | 340 |
| `BNML` | 422 |
| `BNSM` | 483 |

Those five codes classify 1,369 positions as `bee_network_franchised`. The other 196 positions
remain `non_franchised_or_unknown`; they are not dropped or called non-franchised. `BNVB` was a
Gate-A candidate but did not occur in the snapshot, so it remains pending and does not activate
membership in policy v1.

A deterministic pending-candidate review now scans any later accepted `BodsParseReport` and records
only the aggregate `BNVB` observation count. Seeing `BNVB` creates a review-required result; it does
not silently activate the code, relabel the current policy, or claim fleet/service completeness.
Policy activation still requires a reviewed evidence/licence decision and a new explicit version.

Display names, line branding and geography never decide membership. Geography remains only the
request scope. The policy is local-lookup-only and public export remains unavailable while the
reference-table licence blocker `GA-BEE-4` remains open.

## Library boundary

`src/traffictwin/integration/manchester/bee_network.py` provides:

- `bee_network_scope_policy_v1()` — the immutable policy and its aggregate evidence binding;
- `classify_bee_network_membership(...)` — one exact outcome for every parser-admitted BODS
  position; and
- `verify_bee_network_membership_report(...)` — deterministic re-derivation against the original
  `BodsParseReport`;
- `review_pending_bee_network_operators(...)` — aggregate-only detection of the frozen pending
  candidate in a later accepted report; and
- `verify_bee_network_candidate_review(...)` — exact source/policy-bound re-derivation of that
  review queue.

The report retains a complete activity reconciliation: classified positions, out-of-scope rows,
malformed rows, collapsed duplicates and conflicting duplicates. Missing and ambiguous
`OperatorRef` counts are zero for admitted positions because the strict BODS parser requires
exactly one non-empty value; malformed source activities remain separately visible.

The original `LiveTransitVehicleObservation` still says membership `unverified`. Classification is
an additive projection bound to the source report and policy, rather than a mutation of immutable
source evidence.

## Live-scene behaviour

The controlled BODS live workflow now builds separate map layers for:

- verified Bee Network operator positions; and
- other or unknown operator positions.

Each group remains split by `live_vehicle`, `stale`, `historical` or `synthetic` evidence state.
The two membership groups partition all accepted positions, so enabling the Bee view never hides
unknown coverage silently. The refresh summary carries the policy/report fingerprints and exact
membership counts. The scene remains private and bus-only; road-traffic live evidence and public
export remain unavailable.

## What this does not establish

- automatic `BNVB` membership activation (observation only opens a review);
- complete Bee Network vehicle, line or service coverage;
- that every non-matching operator is outside the franchise;
- a TfGM schedule join or its ODbL publication obligations;
- permission to publish the NOC reference table or private BODS scenes;
- an approved longitudinal retention policy; or
- general Manchester traffic volume, speed or congestion.

## Verification

```bash
.venv/bin/python -m pytest \
  tests/unit/test_manchester_bee_network.py \
  tests/unit/test_manchester_bods_live.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/bee_network.py \
  src/traffictwin/integration/manchester/bods_live.py \
  tests/unit/test_manchester_bee_network.py \
  tests/unit/test_manchester_bods_live.py
.venv/bin/mypy --strict \
  src/traffictwin/integration/manchester/bee_network.py \
  src/traffictwin/integration/manchester/bods_live.py
```

The governing decisions remain the
[v0.7 Gate-A audit](manchester-source-gate-a-audit-v0_7.md) and
[ADR-057](../decisions/ADR-057-bee-network-membership-identifiers.md).
