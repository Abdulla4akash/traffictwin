# Controlled TfGM Traffic-Signals Acquisition Workflow (MAN-04 candidate)

Status: **candidate Gate B library evidence — `MAN-01` and `MAN-04` remain `planned`**

`traffictwin.integration.manchester.tfgm_acquisition` connects the existing MAN-01
infrastructure, the bounded archive boundary, and the existing MAN-04 parser in one fixed,
fail-closed order:

```text
BoundedHttpClient download of the single audited ZIP endpoint
    → exact ZIP bytes preserved in MAN-01 quarantine
    → quarantined ZIP re-read and re-hashed
    → bounded archive validation (archive.py)
    → selection of exactly CSV-format/TrafficSignals.csv and TFGM_OGL.txt
    → existing MAN-04 parser (tfgm_signals.py)
    → promote only an explicitly admitted result
```

It reuses the existing [transport boundary](manchester_transport_boundary.md),
[snapshot service](manchester_snapshot_service.md), archive boundary, and
[TfGM signal adapter](manchester_tfgm_signal_adapter.md) without duplicating any HTTP, hashing,
ZIP-extraction, snapshot, or promotion logic, and it changes no capability state.

## Endpoint and request contract

The only reachable resource is the Gate-A-audited static ZIP
`https://odata.tfgm.com/opendata/downloads/TrafficSignals/TrafficSignals_OpenData.zip`, fixed by
one `EndpointPolicy` (host `odata.tfgm.com`, path family `/opendata/downloads/TrafficSignals`,
no query names). `TfgmAcquisitionRequest` carries only a snapshot policy, prior link,
code-specific `admitted_warning_codes` (≤8, sorted, unique), and the `synthetic` declaration —
no host, URL, path, query, parser, executable, archive-limit, or publication-class field exists
(tested). Archive bounds are a fixed module policy sized for the ~1.2 MB audited ZIP
(≤32 MB compressed, ≤128 MB decompressed, ≤16 MB/member, ≤64 members, ratio ≤200), and the
per-download transport byte ceiling is the snapshot policy's member bound.

## Archive safety

`archive.py` provides the single ZIP implementation: it rejects path traversal, absolute paths,
symlink/special members, duplicate member names, nested archives, encrypted members, member-count
and byte bounds, declared-versus-actual size mismatches, and per-member compression-ratio bombs.
This workflow adds only two checks on top of the returned inventory: a deny-list refusal of
executable member types (`UNEXPECTED_MEMBER`) and the required-member selection (a ZIP without
the signal CSV or the attribution member fails `ARCHIVE_REJECTED`). All archive refusals occur
after the complete ZIP is quarantined, so the evidence of a hostile or drifted release is
preserved without ever being promoted.

## Attribution

The manifest and receipts carry the exact attribution shipped inside the audited ZIP
("…database right **2026**."). The Gate-A audit records that the supporting PDF still says 2025;
that discrepancy is documented, not resolved: the acquired artifact's own wording is
authoritative, and a shipped `TFGM_OGL.txt` whose text does not contain the audited wording is a
typed `ATTRIBUTION_DRIFT` refusal (quarantined, never promoted, never silently rewritten). A
2025-worded member is explicitly tested as a refusal.

## Publication class

The full official ZIP is always `private`/workspace-only at this boundary — the request cannot
express any other class, receipts pin `publication_class="private"` as a literal, and replay
refuses a quarantine relabelled to any other class. The separately reviewed three-row
`redistributable_derived` sample (see the adapter guide) is not produced by this workflow.

## Official-release identity

A real (`synthetic=False`) acquisition requires the downloaded ZIP to match the audited release
hash; because the TfGM URL is overwritten in place, a different hash means a new release and
fails `OFFICIAL_ARCHIVE_IDENTITY_MISMATCH` (quarantined for re-audit, never promoted). Synthetic
test ZIPs parse under the `redistributable_derived_sample` evidence class and can never claim to
be the official CSV — the parser separately pins the official CSV hash.

## Receipt integrity: exact internal reconciliation plus one external reference

`TfgmAcquisitionResult` and `TfgmReplayResult` re-derive every internally derivable claim on
each load:

- endpoint host/path, source ID, dataset version, licence, attribution, and publication class
  are literals; `snapshot_id` must carry the TfGM source prefix and end with the
  raw-fingerprint prefix (the timestamp-shaped middle component is preserved as recorded);
- the single-member quarantine inventory, ZIP hash, and raw fingerprint are recomputed; the
  complete ZIP inventory is bound by a deterministic canonical fingerprint covering paths,
  compressed/decompressed sizes, re-derived compression ratios, and the selected CSV and
  attribution members' hash/size evidence (so neither selected hash nor ZIP ratio can drift alone,
  even on synthetic receipts); selected sizes also reconcile directly with the inventory, while
  acquisition and replay re-establish both hashes from the selected raw member bytes;
- an admitted TfGM parse requires complete row reconciliation: `rows_malformed` must be zero and
  `records_accepted` must equal `rows_seen`; sorted unique parser warning codes are preserved,
  `accepted` receipts must carry none, `accepted_with_warnings` receipts must carry some, and an
  acquisition receipt is invalid unless every observed warning code is admitted by the embedded
  request — shrinking the request's admitted set after acquisition invalidates the receipt;
- the typed `ManchesterQuarantineReceipt` (and, for acquisitions, the typed
  `ManchesterSnapshotReceipt`) is embedded and re-verified against this receipt's snapshot ID,
  raw fingerprint, member byte total, and requested policy; the bare `*_fingerprint` fields must
  equal the embedded receipts' recomputed fingerprints, so digest strings cannot drift alone;
- a rejected parser status and a non-synthetic receipt without both audited official hashes are
  unrepresentable.

One field is deliberately **not** internally re-derivable: `parser_report_fingerprint` is an
externally fingerprinted reference to the full MAN-04 parse report. The receipt does not embed
the report, so a swapped digest passes model validation by design; offline replay recomputes the
report from quarantined bytes and exposes the mismatch (tested). Every other mutation listed
above fails `model_validate_json` directly (tested field-by-field, including embedded-receipt
and ZIP-member-metadata, attribution-hash, and compression-ratio mutations).

## Offline replay

`replay_tfgm_quarantine` performs no network calls (tested with sockets disabled), never
promotes or replaces anything, re-verifies the quarantine via the unmodified MAN-01 verifier,
re-hashes the ZIP against the manifest, re-runs archive validation, attribution verification,
and the MAN-04 parser, and refuses relabelling: a foreign source ID (`PRODUCT_MISMATCH`), any
altered adapter/schema/freshness version, licence, attribution, endpoint, parameter set, member
inventory, or publication class (`SOURCE_CONTRACT_MISMATCH`), and an evidence-class disagreement
(`SYNTHETIC_MISMATCH`).

## Semantic limits

Inherited unchanged from the MAN-04 parser and asserted structurally: records are
`static_reference` infrastructure with literal `False` availability for live state, phase,
timing, queue, traffic count, and incident meaning; receipts carry no observation-time or
freshness fields; the dataset version date is a release label, not a live timestamp; retrieval
time stays in retrieval metadata; and nothing here joins signals to SUMO, DfT, or WebTRIS
identities.

## Failure behaviour

| Situation | Code | Durable evidence |
|---|---|---|
| Transport failure / HTTP rejection / oversized download | `TRANSPORT_FAILURE` | none |
| ZIP bytes exceed the snapshot total bound | `TOTAL_BYTES_EXCEEDED` | none |
| Unsafe/incomplete archive (traversal, symlink, duplicate, nested, bomb, missing member) | `ARCHIVE_REJECTED` | quarantine retained |
| Executable member type | `UNEXPECTED_MEMBER` | quarantine retained |
| Shipped attribution differs from the audited wording | `ATTRIBUTION_DRIFT` | quarantine retained |
| Real download is not the audited release | `OFFICIAL_ARCHIVE_IDENTITY_MISMATCH` | quarantine retained |
| Parser rejects the CSV (header/schema drift, malformed rows), during acquisition or replay | `PARSE_REJECTED` | quarantine retained |
| Warning code outside the admitted set | `WARNINGS_REFUSED` | quarantine retained |
| Quarantined bytes drift | `QUARANTINE_INVALID` / snapshot-service `MEMBER_MUTATED` | quarantine preserved |
| Replay relabelling | `PRODUCT_MISMATCH` / `SOURCE_CONTRACT_MISMATCH` / `SYNTHETIC_MISMATCH` | quarantine preserved |
| Repeat acquisition | snapshot-service `DESTINATION_EXISTS` | prior snapshots unchanged |

Accepted snapshots are never replaced; failing reruns leave them byte-identical (tested).

## Test evidence

`tests/unit/test_manchester_tfgm_acquisition.py` (26 tests, all offline via
`httpx.MockTransport`, injected deterministic clocks, bounded synthetic ZIP bytes): exact
allowed request; URL/path/query/limit/parser injection refusal; download byte bound;
quarantine-before-decompression interception proof; successful promotion with exact attribution
retention; 2025-PDF-wording refusal; traversal/absolute/duplicate/nested/bomb/symlink/missing
member refusals; executable-member refusal; malformed-CSV schema drift; code-specific warning
admission and refusal; accepted-snapshot preservation and repeat-publication refusal; offline
deterministic replay; replay relabelling, foreign-source, publication-class, and hash-mutation
refusal; typed `PARSE_REJECTED` replay of a quarantined malformed CSV; official-release identity
enforcement for real requests; per-field receipt mutation refusal via `model_validate_json`
(snapshot ID prefix/suffix, ZIP/CSV hashes, embedded quarantine/snapshot receipts and their
digest fields, count and malformed-row reconciliation, warning-code coherence, ZIP inventory
fingerprint, ZIP-member metadata, selected-member evidence, and post-hoc admitted-warning-set
shrinkage); the documented replay-detected `parser_report_fingerprint` reference; and structural
infrastructure-only semantics.

Validation commands (run 2026-07-22): the focused pytest file, the full
`tests/unit/test_manchester_*.py` suite (335 passing), `ruff check`/`ruff format --check`, and
`mypy --strict` over the two owned Python files, plus `git diff --check` — all passing at
handoff.

## Residual blockers

- No real-network acceptance run was performed; the lead's Gate B acceptance must run the real
  download and reconcile the pinned release hashes.
- The in-place-overwritten TfGM URL means any future release fails closed until re-audited; the
  twice-yearly update aim makes this an expected operational event.
- `GA-LIC-1` (exact OGL clause text) remains an open audit blocker; the recorded attribution is
  the artifact-shipped wording.
- `MAN-01` and `MAN-04` remain `planned`; lead reconciliation (exports, generated schemas, docs
  index, capability truth) still gates any claim.
