# Manchester Immutable Snapshot Service (Gate B candidate, MAN-01 audit-half successor)

Status: **candidate Gate B library evidence — `MAN-01` remains `planned`**

The snapshot service implements the source-neutral immutable boundary required by
[the v0.7 design](../traffictwin-design-v0_7.md) §8 and the
[Gate A audit](manchester-source-gate-a-audit-v0_7.md). The same package now also contains the
candidate bounded transport, hardened XML, and bounded archive services documented in
[the transport boundary](manchester_transport_boundary.md), plus one audited mapping from a
bounded HTTP response to snapshot primitives. No source-specific adapter, freshness projection,
map, or CLI/UI sync surface is accepted, so this library becoming importable does not change any
capability state.

## Two-stage layout

The configured v0.7 Manchester workspace keeps pre-parse bytes and accepted snapshots in separate
immutable-by-contract areas under the same deterministic snapshot ID:

```text
<manchester workspace root>/
    quarantine/
        <source_id>-<retrieval UTC>-<raw fingerprint[:12]>/
            quarantine-manifest.json  # provenance known before parsing
            quarantine-receipt.json   # pre-parse verification proof
            raw/                       # exact encoded response bytes
    accepted/
        <same snapshot ID>/
            snapshot-manifest.json    # source validation result and findings
            snapshot-receipt.json     # promotion verification proof
            raw/                      # byte-identical verified copy
```

The snapshot ID embeds the retrieval start so a later `duplicate_no_change` retrieval of
byte-identical content is a distinct recorded snapshot, while re-publishing the same retrieval is
refused by the new-only rule. A validation failure leaves the quarantine intact and creates no
accepted directory.

## Public API

From `traffictwin.integration.manchester`:

- **Models** (`models.py`, all strict: `extra="forbid"`, frozen, finite):
  `ManchesterSourceIdentity` (source/adapter/schema/freshness-policy versions),
  `ManchesterRequestIdentity` (HTTPS endpoint identity plus typed parameters; structurally
  incapable of storing a raw URL, query string, or credential),
  `ManchesterRetrievalWindow` (UTC start/end), `ManchesterHttpMetadata` (safe response metadata,
  including admitted content encoding; no header map exists), `ManchesterRawMember` (relative
  path, byte size, media type, SHA-256),
  `ManchesterSnapshotFinding`/`ManchesterFindingSeverity`/`ManchesterValidationState`,
  `ManchesterPriorSnapshotLink`/`ManchesterPriorRelation` (`first_snapshot`, `supersedes`,
  `duplicate_no_change`), `ManchesterPublicationClass` (exactly the design's `private`,
  `redistributable_raw`, `redistributable_derived`, `metadata_only`),
  `ManchesterSnapshotPolicy` (explicit member-count/per-member/total byte bounds),
  `ManchesterQuarantineManifest`/`ManchesterQuarantineReceipt`,
  `ManchesterSnapshotManifest`, and `ManchesterSnapshotReceipt`.
- **Helpers**: `build_raw_fingerprint(members)` (SHA-256 over the canonical ordered
  path/size/hash inventory) and `build_snapshot_id(source_id, retrieval_started_at_utc,
  raw_fingerprint)`.
- **Service** (`snapshots.py`): `publish_manchester_snapshot(workspace_root, manifest, members,
  policy)`, `verify_manchester_snapshot(snapshot_dir)`,
  `read_manchester_member(snapshot_dir, relative_path)`, and the typed refusal
  `ManchesterSnapshotError` (stable `code` attribute).
- **Ordered acquisition service** (`snapshots.py`):
  `publish_manchester_quarantine(...)` and `verify_manchester_quarantine(...)` preserve and prove
  the complete bounded acquisition before parsing; `promote_manchester_quarantine(...)` accepts
  only a source-validated manifest whose complete provenance matches the quarantine;
  `quarantine_validate_and_promote(...)` invokes the supplied validator only after the quarantine
  is durably published and reverified.
- **Transport bridge** (`acquisition.py`):
  `snapshot_parts_from_http_response(response, relative_path, media_type)` maps the bounded
  transport result into the secret-free request identity, retrieval window, safe HTTP metadata,
  raw-member hash/size, and unchanged bytes used by source adapters. It performs no parsing,
  publication, or source-specific inference.

All artifacts expose `canonical_json()` and `fingerprint()` using the repository's existing
canonical-JSON (sorted keys, compact separators, no NaN) and SHA-256 conventions.

## Invariants

1. **Raw-before-parse is enforced by the ordered API.** Exact encoded response bytes and
   secret-free provenance are atomically published and reverified before the validator callback
   is invoked. The snapshot service itself performs no parsing or normalisation.
2. **Publication is atomic, new-only, and fail-closed.** A per-snapshot exclusive publication
   lock serialises cooperative writers. Bytes are staged in an isolated
   temporary sibling inside the workspace root, every member is re-hashed and reconciled against
   the manifest, and only a fully verified payload is renamed into place. The destination must
   not already exist; an existing accepted snapshot is never replaced; failure removes only the
   service's own unpublished temporary directory and never leaves a partial destination.
3. **The manifest is self-reconciling.** Member ordering (sorted, unique, case-fold unique),
   member count, total bytes, the aggregate raw fingerprint, and the snapshot-ID derivation are
   all model invariants, as are validation-state/finding consistency and the prior-relation
   rules (`duplicate_no_change` must repeat the prior raw fingerprint; `supersedes` must not; a
   rejected manifest cannot be published at all).
4. **Reopening re-verifies everything.** Quarantine and accepted verification require the exact
   top-level inventory, applies the stored policy before raw reads, recomputes every member hash
   and size, rejects uninventoried/missing/symlinked files, recomputes the aggregate fingerprint,
   and reconciles the receipt's counts and byte totals against the stored manifest and raw tree.
5. **Read-only where supported; hashes are the authority.** On POSIX, published files drop all
   write bits (`read_only_applied` records this). Filesystem permissions are convenience only —
   drift is detected by hash reconciliation, not by mode bits.
6. **Secrets and private paths are structurally refused.** Parameter names resembling
   credentials (`api_key`, `token`, `secret`, `password`, `authorization`, …) are rejected;
   credential-bearing or query-carrying URLs are rejected as parameter values; redacted
   parameter names are recorded without values; free-text fields reject local absolute paths;
   the module performs no logging and never places raw bytes or vehicle identifiers in error
   messages.
7. **Promotion cannot rewrite provenance.** Source, request, retrieval, HTTP metadata, complete
   member inventory, hashes, publication class, licence, attribution, access date, and synthetic
   state must match exactly. Only validation state, findings, and prior-snapshot relation are added
   after parsing.
8. **Bounds are explicit.** Member count, per-member bytes, and total bytes come from a
   caller-supplied `ManchesterSnapshotPolicy`; manifest and receipt files have fixed read bounds.

## What this library deliberately does not do

- The snapshot service itself performs no network access or parsing. Its sibling transport,
  XML, gzip, and zip boundaries remain source-neutral and do not constitute an accepted adapter.
- No CSV schema interpretation or source-specific XML interpretation exists yet.
- No freshness/truth-label computation (`MAN-07`) and no `ManchesterTimeBasis` promotion
  ([ADR-055](../decisions/ADR-055-manchester-time-basis.md) is enforced upstream).
- No source-specific schema knowledge, no Randy/TOS access, and no publication-rights decision:
  `publication_class` is recorded and preserved, never inferred.
- No capability-state change: `MAN-01` becomes implemented only when Codex reconciles transport,
  parsers, real-source acceptance evidence, generated contracts, project records, and full
  quality gates.

## Test evidence

`tests/unit/test_manchester_models.py` and `tests/unit/test_manchester_snapshots.py`
(synthetic fixtures only, labelled `synthetic: true` with non-Manchester attribution text) cover:
deterministic fingerprints; strict unknown-field rejection; exact raw-byte round trips including
binary content; stable member ordering and case-fold uniqueness; hash/size/count/fingerprint
reconciliation; mutation, extra-file, missing-file, and symlink detection on reopen; duplicate
destination, concurrent-publication lock, and symlinked-destination refusal;
traversal/absolute/dot-segment/drive-letter path refusal; member-count, per-member, and total-byte
policy limits; credential-name, credential-URL,
and query-string refusal; private-path refusal; simulated mid-publication failure with no partial
destination and no staging leftovers; prior/no-change relation validation including a
byte-identical later retrieval publishing under a new snapshot ID; publication-class
preservation on disk; strict immutable collection contracts; receipt count/total/policy tamper
refusal; exact top-level layout; bounded transport-to-snapshot mapping; and POSIX read-only
publication. Encoded-response tests prove that bounded gzip validation retains the exact wire
bytes for snapshot hashing rather than silently replacing them with decoded content. Ordered-flow
tests prove quarantine exists before validator entry, parser failure creates no accepted snapshot,
rejected validation cannot promote, provenance drift is refused, and quarantine tampering blocks
promotion.

Focused validation commands (run 22 July 2026):

```bash
.venv/bin/python -m pytest tests/unit/test_manchester_models.py tests/unit/test_manchester_snapshots.py tests/unit/test_manchester_quarantine.py tests/unit/test_manchester_acquisition.py
.venv/bin/ruff check src/traffictwin/integration/manchester/ tests/unit/test_manchester_models.py tests/unit/test_manchester_snapshots.py
.venv/bin/ruff format --check src/traffictwin/integration/manchester/ tests/unit/test_manchester_models.py tests/unit/test_manchester_snapshots.py
.venv/bin/mypy src/traffictwin/integration/manchester/ tests/unit/test_manchester_models.py tests/unit/test_manchester_snapshots.py
```
