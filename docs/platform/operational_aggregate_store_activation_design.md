# Design — Operational aggregate-store activation

**Status: IMPLEMENTED in Phase 173. This design implements bounded activation tooling for the
existing aggregate-only SQLite contract in a deliberately selected external owner workspace. It does not
migrate real data, deploy a service, create scientific standing or make the store a source of
truth.**

## 1. Purpose and inherited boundary

Phases 147 and 160 supplied the strict in-memory and persistent historical-store engines. This
slice supplies the missing operational layer: discover a bounded set of safe import bundles,
preview every effect without mutation, require an exact owner confirmation, build the catalogue
atomically, prove a complete backup can be restored in isolation, and expose path-free catalogue
and integrity reports.

The inherited prohibitions remain unchanged. The activation layer never opens BODS quarantine,
accepts arbitrary JSON, stores raw identifiers, participant material, credentials, salts, private
permission text or absolute paths, changes evidence standing, performs analysis, or deletes source
artifacts. Forecasts remain forecasts with evidence=false. Registration is storage, not scientific
admission.

## 2. Explicit local configuration

Private filesystem choices are held in a repr-suppressed runtime configuration and never enter a
public model or receipt:

- an owner workspace outside the repository;
- one or more import roots contained by that owner workspace and outside the target
  'historical-store' directory;
- an exact versioned licence allowlist; and
- bounded discovery limits.

The selected workspace, import roots, every parent directory and every imported file must be real
non-symlink paths owned by the current user with no group/other permission bits. Directories must
be owner-readable, owner-writable and owner-searchable; files must be regular,
owner-readable and no larger than the configured bound. The repository itself and its descendants
are always refused. Public output uses opaque workspace/import handles only.

The command-line configuration is intentionally local and uncommitted. Reading it is not
confirmation. Activation additionally requires the exact preview digest produced from the
validated import set.

## 3. Import bundle and adapters

Discovery considers only files ending '.safe-aggregate-import.json'. Every manifest is strict,
size-bounded and contains relative handles for two sibling inputs:

1. the exact aggregate artifact, bound by SHA-256; and
2. a strict AuthoritativeSourceRecord JSON, separately bound by SHA-256.

Absolute paths, traversal components, symlinks, duplicate dataset ids, duplicate manifests and
ambiguous handles are refused. Source files are read once into memory; discovery records their
before digests and preview rechecks them before activation. The source artifacts are never moved,
rewritten or deleted.

Only these adapters exist:

| Import kind | Existing validator | Store schema | Payload class | Maximum standing |
| --- | --- | --- | --- | --- |
| 'bods_session_activity_aggregate' | SessionActivityAggregate 1.0 | 'bods.session.activity.aggregate' v1 | aggregate session measurement | the source record's standing |
| 'bus_forecast_fit' | BusForecastFit 1.0 | 'bods.bus.forecast.fit' v1 | model artifact | forecast, not applicable, evidence=false |

Each adapter first parses the exact artifact with its existing strict domain model, then submits the
unchanged bytes to the historical-store schema/privacy/licence gate. There is no fallback adapter.
The activity adapter derives only safe support counts and the declared local service date already
present in the aggregate. The forecast adapter preserves its forecast/non-causal/non-evidence
standing regardless of stronger metadata in a manifest. Both bind the supplied authoritative
source id, record digest and payload digest without inventing authority.

## 4. Preview and refusal semantics

Preview performs no target-store creation. It validates containment and permissions, discovers
bundles deterministically, verifies exact bytes and digests, constructs schema/source/dataset
records, and runs the in-memory migration dry-run. Its digest binds:

- the activation method and policy versions;
- the opaque workspace id;
- schema and licence-policy digests;
- every manifest, source-record and payload digest;
- each immutable dataset-record digest; and
- every dry-run finding.

The public preview reports safe ids, digests, counts and typed refusal codes only. Validation
exceptions are normalised to bounded safe messages; filenames and private paths never appear.
Any refusal makes the preview non-activatable. Empty discovery is also a refusal.

Typed activation refusals are immutable and state explicitly that no target publication occurred.
A caller can distinguish configuration, containment, permission, manifest, digest, schema,
licence, source, dry-run, preview-mismatch, existing-target, backup, restore and publication
failures without receiving private data.

## 5. Atomic activation and exact retry

Activation requires the caller-provided expected preview digest. It immediately rebuilds the
preview from source bytes; a changed source, policy or selection refuses. The implementation then:

1. creates or resumes a deterministic private staging workspace tied to the preview digest;
2. opens the existing SQLite adapter in that staging workspace with the exact preview contracts;
3. registers every candidate, requiring success or an exact idempotent retry;
4. requires a clean recovery report;
5. creates an explicit verified backup;
6. copies that complete backup into a separate private restore-drill workspace;
7. opens the restored catalogue through the normal SQLite adapter and reconciles every expected
   dataset id, record digest and payload digest;
8. writes and fsyncs a path-free activation marker containing the contracts and receipts; and
9. atomically renames the staged 'historical-store' directory to the final target, then fsyncs its
   parent.

No partially populated store is ever published at the final target. A fault before rename leaves
only a deterministic staging workspace; rerunning the exact preview resumes it. A fault after
rename is recognized through the marker as a successful exact retry. An existing target without
the exact marker is never overwritten. Staging areas from other preview digests and unexpected
entries are reported as orphan handles and are never automatically deleted.

The restore drill is substantive rather than a manifest-only check: the backup catalogue and every
payload are copied, opened, replayed and queried with the public adapter. The drill workspace is
an activation-owned temporary directory and is removed after verification; the verified backup in
the staged store remains. Automatic retention deletion remains false.

## 6. Reopen, catalogue and integrity commands

The activation marker serialises only strict public contracts: schemas, authoritative source
records, the licence policy, the preview digest, dataset record digests, the backup receipt and the
activation receipt. This is sufficient to reopen the store without reopening import files.

The CLI provides four commands:

- 'preview': validate and dry-run an uncommitted local configuration;
- 'activate': require the exact preview digest and perform the bounded publication;
- 'catalogue': reopen the activated store and return an allowlisted query result; and
- 'integrity': return SQLite recovery, marker/catalogue and backup-manifest/restore reconciliation.

All commands emit canonical JSON to standard output and bounded safe refusals to standard error.
No output includes the config path, workspace path, import path or source filename.

## 7. Crash, corruption and idempotency verification

Deterministic synthetic tests cover:

- both closed adapter families and unchanged source bytes;
- empty, malformed, oversized, symlinked, traversal and permission-unsafe inputs;
- payload/source digest, schema, standing and licence refusals;
- privacy, identifier, participant and credential screening;
- preview mutation freedom and confirmation-digest mismatch;
- an injected pre-publication crash, deterministic resume and exact post-publication retry;
- conflicting/unmanaged targets and orphan staging reports;
- complete backup creation and isolated restore/replay;
- corruption detection after activation; and
- path-free CLI preview, catalogue, integrity and refusal output.

No test accesses a network, private archive or real owner workspace.

## 8. Residual owner actions

Implementation and synthetic verification do not select the real owner workspace, declare its
actual licence classes, author authoritative source records, approve any import bundle, migrate
real aggregates, schedule backups, monitor disk capacity or deploy a service. Those remain explicit
owner/operations actions. The first real preview and activation must be separately recorded; until
then the correct status is 'operational activation tooling implemented, no real store activated'.
