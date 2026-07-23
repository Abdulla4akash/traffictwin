# Controlled BODS SIRI-VM Acquisition Workflow (MAN-05 candidate)

Status: **candidate Gate B library evidence — `MAN-01` and `MAN-05` remain `planned`**

`traffictwin.integration.manchester.bods_acquisition` connects the existing MAN-01
infrastructure and the existing MAN-05 SIRI-VM parser in one fixed, fail-closed order:

```text
BoundedHttpClient authenticated fetch of the single audited datafeed endpoint
    → exact response bytes preserved in MAN-01 quarantine
    → quarantined bytes re-read and re-hashed
    → existing MAN-05 parser through the hardened XML boundary
    → promote only an explicitly admitted result
```

It reuses the existing [transport boundary](manchester_transport_boundary.md),
[snapshot service](manchester_snapshot_service.md), hardened XML boundary, and
[BODS adapter](manchester_bods_adapter.md) without duplicating any transport, hashing, XML,
snapshot, or promotion logic, and it changes no capability state.

## Credential usage (the key is never exposed)

BODS requires a registered account whose API key is transmitted as a URL query parameter — the
highest-leak-risk shape ADR-054 anticipates. Handling is structural:

- the key is supplied at runtime as a **transient function argument**
  (`acquire_bods_snapshot(..., api_key=...)`), sourced by the operator from the environment or
  `st.secrets`; there is deliberately no `api_key` field on any request or receipt model, so it
  cannot be persisted, fingerprinted, or round-tripped;
- it travels only through the transport's secret-query channel; the persisted request identity
  records the parameter **name** under `redacted_parameter_names=("api_key",)` and never the
  value (asserted against the quarantine manifest, both receipts, and the accepted manifest
  bytes on disk);
- error messages carry transport failure codes only, never URLs or credential text, and an
  unusable key is refused as `API_KEY_INVALID` with the value withheld;
- because httpx/httpcore log full request URLs at INFO level, the module raises those two
  loggers above INFO for exactly the duration of the authenticated fetch and restores them
  after. A process-wide re-entrant lock serialises this boundary, so overlapping BODS
  acquisitions cannot restore URL logging while another credential-bearing request is active
  or corrupt the prior logger levels. Both key absence and concurrent restoration are tested.

Real-source provenance is also structural: when `synthetic=False`, acquisition refuses an
injected HTTP client or UTC clock as `UNTRUSTED_REAL_SOURCE_BOUNDARY`. A caller therefore cannot
route fixture bytes through a mock transport, select a favourable evaluation time, and obtain a
receipt labelled as real/live evidence. Injection remains available only to clearly labelled
synthetic tests; real acquisition uses the module-owned HTTPS transport and system UTC clock.

## Request contract

`BodsAcquisitionRequest` cannot express a host, URL, path, free query, parser, timeout, byte
limit, publication class, or API key (tested). It carries: a mandatory typed `BodsBoundingBox`
(no Manchester box is invented — geographic scope is the caller's declared choice and never
implies Bee Network membership), optional documented filters `operator_ref`/`line_ref`/
`producer_ref` as bounded identifiers, the snapshot policy, prior link, code-specific
`admitted_warning_codes` (≤8, sorted, unique — e.g. `OUTSIDE_BOUNDING_BOX`), and the `synthetic`
declaration. Transport limits are fixed module constants (10 s connect, 30 s read, 120 s
deadline, ≤1 redirect, ≤2 attempts, `application/xml`/`text/xml` only, response bytes capped by
the snapshot policy's member bound and the parser's 16 MB SIRI ceiling), reflecting the audit's
absent consumer rate-limit policy (`GA-BODS-3`) and the 10-second consumer cache.

## Quarantine-before-parse

The exact response bytes are published to MAN-01 quarantine before any XML is touched —
enforced structurally through `quarantine_validate_and_promote` and proven by a test that
intercepts the parser and asserts the quarantined feed and manifest already exist on disk. The
parser re-reads and re-hashes the member. Identity responses pass directly to parsing; a declared
`gzip` response is decoded only at this point through the shared bounded decompressor. The raw
wire-member SHA-256 and the decoded parser-payload SHA-256 are both bound into parser lineage, so
decoding never replaces or weakens the preserved evidence. The unaudited `deflate` encoding and
malformed/oversized/compression-bomb gzip streams fail closed. The parser then applies the
hardened XML boundary (DTDs,
entities, external references, wrong roots, and oversized documents all fail closed as
`PARSE_REJECTED` with the quarantine retained).

## Receipts

`BodsAcquisitionResult` and `BodsReplayResult` follow the hardened receipt pattern: literal
endpoint/source/licence/attribution/publication fields; snapshot-ID prefix/suffix binding; raw
and feed hash reconciliation; embedded typed `ManchesterQuarantineReceipt` (and, for
acquisitions, `ManchesterSnapshotReceipt`) with digest fields that must equal the embedded
receipts' recomputed fingerprints; the persisted `ManchesterRequestIdentity` embedded and bound
(audited endpoint, `api_key`-only redaction, no unaudited visible parameter, and — for
acquisitions — exact agreement with the embedded typed request); complete activity
reconciliation (`malformed == 0`, `conflicting == 0`,
`records == activities − outside − duplicates`, freshness counts partitioning the records, and
synthetic evidence yielding only synthetic freshness); and warning-code coherence with the
embedded admitted set. `parser_report_fingerprint` remains an externally fingerprinted
reference verified by replay, as in the sibling workflows. Receipts carry counts only — no
vehicle records — so raw `VehicleRef` values are structurally absent (asserted), and the parser
itself only ever emits snapshot-scoped pseudonymous tokens.

Both result types embed the exact typed quarantine manifest and reconcile its canonical hash and
fingerprint against the embedded quarantine receipt. Snapshot identity, members, raw fingerprint,
request identity, evidence class, publication contract, source/schema/adapter versions, and the
`manchester-freshness-v1` policy must all equal that manifest. In particular,
`evaluated_at_utc` must equal the manifest's UTC retrieval-completion instant, so a receipt cannot
be re-timed independently of its preserved source evidence.

## Offline replay

`replay_bods_quarantine(workspace, snapshot_id, BodsReplayRequest)` performs zero network access
(tested with sockets disabled), never promotes, re-verifies the quarantine and hashes, and binds
the caller's claim before parsing: source contract, audited endpoint, exact visible parameters
recomputed from the claimed bounding box and filters, the `api_key`-only redaction contract
(missing or extra redacted names are `REDACTION_CONTRACT_MISMATCH`), `private` publication
class, single-member inventory, and evidence class. Replay parses in `offline_replay` mode, so
real records can only be `historical` — replayed evidence is never relabelled live or stale
(a receipt claiming otherwise is unrepresentable). A rejected parse raises typed
`PARSE_REJECTED` with the quarantine ID.

The replay result embeds the typed `BodsReplayRequest` as well as the quarantine manifest. Reload
validation re-derives the visible request parameters, checks the optional evidence-class claim,
and binds both to the manifest. Changing the replay bounding box, filters, evaluation time, or
freshness-policy version after the fact fails validation.

## Retention, publication, and claim limits

- The raw response and the accepted snapshot are always `private`; no other publication class is
  expressible, and replay refuses relabelled quarantines.
- `retention_policy="unapproved"` and `public_export_available=False` are literals: the design
  §18.2 retention/display/export decision has not been made, and `GA-BODS-4` (multi-day
  `VehicleRef` persistence) remains open.
- `bee_network_membership_available=False` is a literal while `GA-BEE-1` is open; the six BN\*
  candidate NOCs are **not** present anywhere in this module (tested against the source text),
  and neither display names nor geography ever decide membership (ADR-057).
- Bus/transit-only semantics are structural: `transit_vehicle_only=True`,
  `road_traffic_volume_available=False`, and no road-count, private-vehicle-flow, congestion, or
  complete-fleet field exists on any model.

## Failure behaviour

| Situation | Code | Durable evidence |
|---|---|---|
| Unusable credential | `API_KEY_INVALID` | none (value withheld) |
| Injected transport or clock used for a real-source request | `UNTRUSTED_REAL_SOURCE_BOUNDARY` | none |
| Transport failure / HTTP rejection / wrong media type / oversized response | `TRANSPORT_FAILURE` | none |
| Response exceeds the snapshot total bound | `TOTAL_BYTES_EXCEEDED` | none |
| Parser rejects (malformed/unsafe XML, profile drift), acquisition or replay | `PARSE_REJECTED` | quarantine retained |
| Warning code outside the admitted set | `WARNINGS_REFUSED` | quarantine retained |
| Quarantined bytes drift | `QUARANTINE_INVALID` / snapshot-service errors | quarantine preserved |
| Replay relabelling | `PRODUCT_MISMATCH` / `SOURCE_CONTRACT_MISMATCH` / `SCOPE_MISMATCH` / `REDACTION_CONTRACT_MISMATCH` / `SYNTHETIC_MISMATCH` | quarantine preserved |
| Repeat acquisition | snapshot-service `DESTINATION_EXISTS` | prior snapshots unchanged |

A transport failure is a typed failure — never zero buses and never stale-as-live evidence.

## Test evidence

`tests/unit/test_manchester_bods_acquisition.py` (all automated cases offline via
`httpx.MockTransport`, injected deterministic clocks, clearly labelled synthetic SIRI-VM XML):
exact allowlisted request with key transmission through the secret channel only; key absence
from canonical JSON, all four persisted artifacts, error strings, and DEBUG-level captured logs;
real-source refusal of injected transports and clocks; concurrent authenticated-log suppression
with exact level restoration; `api_key`-only redaction in the persisted request identity; unsafe
request-field refusal
(including an `api_key` model field); response byte and content-type bounds;
quarantine-before-parse interception proof; promotion with bus-only/retention literals; absence
of hard-coded BN\* codes from the module source; code-specific warning admission in both
directions; malformed XML, DTD/entity, wrong-root, and activity schema-drift refusals with
quarantine retained; accepted-snapshot byte-identity after failed reruns and new-only repeat
refusal; raw gzip preservation plus post-quarantine bounded decoding; sockets-disabled
deterministic replay that never promotes and never relabels live;
replay refusal of altered scope/filters, foreign source, publication relabelling, missing and
extra redacted names, freshness-policy relabelling, and evidence-class mismatch; raw `VehicleRef`
absence from receipts,
logs, and errors; and per-field receipt mutation refusal via `model_validate_json` (snapshot
ID, hashes, counts, freshness partition, warning codes, embedded receipts and digests,
embedded manifest and evaluation time, publication/retention/Bee-Network literals, redaction
contract, acquisition/replay visible parameters, replay scope, and post-hoc admitted-warning
shrinkage).

Validation commands (run at handoff): the focused pytest file; the full
`tests/unit/test_manchester_*.py` suite; `ruff check`/`ruff format --check` and `mypy --strict`
on the two owned Python files; `git diff --check`; and documentation link validation — all
passing.

## Residual blockers

- `GA-BEE-1` (live-feed NOC verification), `GA-BODS-4` (VehicleRef persistence → retention
  decision), `GA-BODS-3` (consumer rate limits), `GA-BODS-6` (registration terms), and the
  design §18.2 retention/display/export contract all remain open; Bee Network membership and
  public export stay unavailable here until they close.
- A controlled real-source probe on 23 July 2026 passed the fetch, quarantine, gzip decoding,
  parser, promotion, privacy-safe projection, and local-scene publication slice. Its exact safe
  evidence is recorded in [the BODS Gate-B probe](manchester_bods_gate_b_probe.md). This does not
  close the retention, membership, terms, or complete Gate-B acceptance blockers.
- `MAN-01` and `MAN-05` remain `planned`; lead reconciliation (exports, generated schemas, docs
  index, capability truth) still gates any claim.
