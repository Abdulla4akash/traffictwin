# Security And Privacy

TrafficTwin is a local research prototype. The current threat model is limited to safe local handling of imported bundles and metadata.

## ZIP Handling

The bundle loader:

- rejects absolute paths;
- rejects `..` path traversal;
- rejects symlink entries;
- caps extracted content;
- extracts only into a controlled temporary directory;
- cleans temporary files after validation.

## No Execution Of Imported Files

Imported bundle contents are treated as data. TrafficTwin does not execute scripts from bundles.

The custom metric API does execute only callables that trusted application code explicitly
registers in-process. It does not accept bundle scripts, uploaded Python, arbitrary module paths,
or ambient entry-point discovery. This boundary is not a sandbox: registered functions have the
permissions of the TrafficTwin process. Only reviewed local code should be registered. Deep-copied
canonical inputs protect engine-owned records, two-run output checks detect evaluated-input
repeatability failures, and exceptions are isolated, but these controls do not secure hostile code.

Declarative diagnostic YAML is separate from that Python extension boundary. It is parsed with a
bounded safe loader and strict schema that rejects custom tags, anchors/aliases, duplicate keys,
multiple or oversized documents, unknown fields, non-finite thresholds, imports, function calls,
templates, arbitrary expressions/reducers, nested references, and dynamic metric keys. It cannot
define executable Python. The surrounding application is still a local trusted process, so the
grammar is described as trusted local static configuration rather than a general security sandbox.

## Generic Tabular Decoding

Plain CSV, gzip-CSV, and Parquet are admitted only when explicitly declared in the manifest.
Duplicate columns, malformed encodings, and unsupported nested/binary/temporal Parquet columns are
rejected. Gzip decoding counts output bytes; Parquet metadata and decoded Arrow size are checked.
Ordinary ingestion caps each generic table at 10,000,000 decoded bytes. Opt-in streaming uses
explicit nested chunk/table/bundle bounds, rejects a single decoded row larger than its chunk
limit, and keeps exact global reconciliation in a temporary disk-backed SQLite index. The index
and ZIP workspace are cleaned after validation. Streaming chunks are provisional until the final
report permits import; consumers must not publish staged rows from a rejected operation. Bounds do
not include arbitrary caller retention, validation-report growth, or all native-library memory.

## TOS NPZ Inspection

The optional TOS result reader treats NumPy archives as untrusted data:

- package-relative paths are validated and cannot escape the selected package root;
- NPZ members with absolute paths, traversal, backslashes, or symlink metadata are rejected;
- decompressed archive content is capped;
- NumPy object deserialisation is disabled with `allow_pickle=False`;
- replay and task views load only documented keys and return bounded samples;
- the source package is never modified or copied into the registry.

The reader does not execute repository scripts or the source environment. A package Git commit and
content fingerprint provide reproducibility references, not cryptographic trust in the producer.

## Source Immutability

Validation, metrics, diagnostics, and provenance read source files without modifying them. Registry
imports store metadata and JSON payloads, not edited copies of raw files.

Nearest-flip analysis reads a bundle/EvidencePack and optional Pydantic-validated RuleSetConfig
JSON. It does not execute configuration content, modify the source config, update the registry, or
persist its candidate. An output artifact is written only to the explicit CLI `--output` path.

## Batch Path Disclosure

Batch validation/import summaries intentionally record each resolved source path and its original
matching references for reproducibility. Those values can expose usernames, mount points, or
private directory names. Keep summaries local by default and review/redact paths before including
JSON/CSV output in public reports. Batch glob expansion remains bounded and limited to explicitly
supplied references; it does not grant trust to matched files or execute them.

## Provenance Source-Row Preview

The Provenance Explorer source-row preview:

- uses bundle-relative source paths;
- rejects absolute paths and `..` traversal;
- reuses the safe directory/ZIP bundle loader;
- applies the ingestion decoded-size bound and returns only a bounded row window;
- treats source text as data, not executable content.

Trace exports avoid machine-specific absolute paths. They may still include bundle-relative source
filenames, row numbers, validation messages, and raw values from the requested preview, so do not
export traces containing private real data without review.

PRO-02 DOT/GraphML exports recursively redact POSIX, Windows, home-relative, and `file://` local
paths and replace invalid XML control characters. An unsafe path-bearing node ID receives a
redacted alias, and the exporter never opens a node path or follows a link. The default safe profile
still retains bundle-relative filenames, ordinary identifiers, descriptions, and scalar
attributes. The structure-only profile removes descriptions, attributes, and source references,
but neither mode guarantees anonymity. Every graph view is bounded and reports exact omissions.

PRO-03 completeness JSON/CSV does not embed raw row values, but it retains report/claim IDs,
artifact keys, bundle-relative filenames through evidence fingerprints, statuses, counts, reason
codes, and limitations. It is path-safe by construction, not anonymous. Review it before public
sharing, especially when ordinary identifiers or filenames are private. The scorer never opens a
path supplied by a claim and never parses report HTML/Markdown.

EXP-01 writes only under the exact caller-selected destination. It validates the complete grid in
memory, builds a temporary sibling tree, and replaces an existing directory only when overwrite is
explicit. Empty and symbolic-link destinations plus the current directory, home, filesystem root,
and current/home ancestors are rejected before expansion. Parameter paths come from a closed enum
rather than user-controlled filesystem or object traversal. External artifacts contain no inferred executable command or launcher. Sweep
JSON/CSV/seeds may still contain user-authored identifiers and metadata and require review before
sharing.

EXP-02 additionally treats the source bundle as immutable evidence. It rejects source-root and
internal symlinks, imported/raw labels, and inferred/canonicalised manifests; reads within fixed
file/byte/row/request bounds; and mutates only one declared uncompressed CSV target in a temporary
sibling tree. The complete changed-row ledger is bounded at 20,000 rows and never silently
truncated. Protected/symlink destination checks and explicit overwrite mirror EXP-01. Parent and
destination paths may not overlap in either direction; failed final publication restores the
previous destination. The mutation
manifest is path-safe rather than anonymous: row identifiers, RSU/vehicle/task IDs, filenames, and
field values may remain sensitive and require review before sharing.

EXP-03 does not accept an imported bundle or executable model. A strict YAML/JSON synthetic
configuration is size-bounded, safely parsed, and limited to closed numeric fields/tables. The
generator copies its in-memory rows before applying independently hash-derived bounded errors and
exact dropout. Output publication uses a temporary sibling, rejects empty/protected/symbolic-link
destinations, requires explicit overwrite, and preserves the previous directory when generation
fails. The embedded audit may retain scenario/run identifiers and exact row/error counts; it is
path-safe synthetic provenance, not anonymous data.

## Manifest And Text Handling

Manifest, validation, and diagnostic text may be displayed in the UI. The current UI does not intentionally render untrusted HTML. Future richer rendering should continue to escape or treat imported text as plain text.

## Local SQLite Registry

The Threshold Sensitivity page never writes its range, point selection, imported session config,
or exported candidate to SQLite. Import requires an explicit complete JSON apply action and remains
in session state; export is a deliberate browser download. Neither action changes source bundles,
raw evidence, repository files, or package defaults.

The registry is a local SQLite file for metadata:

- seeds;
- experiments;
- runs;
- bundle import metadata;
- metric JSON;
- evidence-pack JSON.

It is not a credentials store and should not contain private tokens.

## Credentials

The immutable v0.6 workflow and every repository-contained synthetic demonstration require no
credential. The opt-in v0.7 Manchester development workflow can use two operator-supplied
credentials:

- `BODS_API_KEY` for one explicitly submitted BODS SIRI-VM request; and
- `NATIONAL_HIGHWAYS_API_KEY` for the fixed three-product National Highways operational refresh,
  automatically every five minutes for the configured Streamlit process plus a manual fallback.

Both values are read from the process environment and passed transiently to the bounded transport
boundary. They must never be committed, placed in a Streamlit widget or session state, written to
SQLite, copied into request models/receipts/scenes/snapshots, or included in errors and logs. BODS
uses a redacted secret query parameter. National Highways uses a redacted secret request header.
The acquisition tests inspect canonical JSON, persisted artifacts, exceptions, and captured logs
for credential leakage. Environment variables still remain visible to the local process and may be
visible to sufficiently privileged local users; TrafficTwin is not a secrets manager.
The National Highways daemon retains its key only in process memory and stops with Streamlit. It
does not authorise or poll BODS or another source.

## Sanitised Fixtures

Future real-schema fixtures should remove:

- usernames and private paths;
- tokens and keys;
- vehicle or person identifiers if sensitive;
- large private datasets;
- checkpoint binaries unless explicitly permitted.

They should preserve schema, units, and representative values.

## Large Or Private Data

Do not commit large real datasets or private checkpoints. Store only small sanitised fixtures where permission exists.

## Live And Near-Live Data

The v0.7 development branch contains bounded private acquisition for BODS bus positions and three
National Highways operational products. With explicit workspace, scope, and process-only keys,
local process workers refresh BODS every minute and National Highways every five minutes.
Every request is quarantined before parsing, admitted only through source-specific validation,
published as an immutable accepted snapshot, and replayed locally with source-time freshness and
outage states. BODS raw evidence may retain source vehicle identifiers, even though rendered
records are pseudonymised. Workers stop with Streamlit and never delete snapshots automatically.
National Highways outputs remain private pending release/licence review.

Continuous collection, public hosting/export, changed retention, multi-user access, or additional
live sources still require an explicit security, privacy, licensing, retention, and operational
review. A recently retrieved response must never be called live merely because its download time
is recent.

## Future User-Study Data

Formal user evaluation data should be handled according to ethics approval, anonymisation requirements, consent terms, and university data-management rules.

## Standalone Workspace And Reports

- `demo reset` operates only on a marked TrafficTwin standalone workspace and requires `--yes`.
- The standalone launcher uses a fixed argument-list subprocess command and no shell interpolation.
- Report HTML escapes text and uses no remote assets or JavaScript.
- Reports normalise absolute local paths where practical.
- REP-01 escapes LaTeX text, recursively bounds projected content, redacts absolute POSIX/Windows
  paths to basename-only markers, preserves ordinary web URLs, and embeds no remote assets,
  scripts, shell commands, or raw tables. SVG is self-contained and PDF uses fixed local drawing.
- REP-01 writes only explicit `.tex`/`.svg`/`.pdf` targets, requires deliberate overwrite, rejects
  duplicate/symbolic-link targets, and returns receipts without absolute output paths.
- REP-02 target identifiers are path-free, author/note/control content is bounded and validated,
  report surfaces escape analyst text, and SQLite triggers reject annotation update/delete.
- REP-02 author labels are declared metadata, not authenticated identities or digital signatures;
  the prototype has no multi-user access control or external identity-provider integration.
- REP-03 accepts at most 2,000,000 bytes per strict report JSON payload, validates finite bounded
  typed claim content, rejects duplicate identities, and caps sections, claims, nesting, and field
  changes. It never executes report content or parses rendered HTML/Markdown/PDF.
- REP-03 output excludes report display paths and section bodies from the scientific fingerprint,
  but exact typed claim values may still be sensitive research results; apply the source's ordinary
  access and publication policy before sharing a diff.
- REP-04 accepts only the same bounded strict typed report payloads, reduces absolute source display
  paths to basenames, escapes Markdown/HTML/PDF content, and generates only relative local
  source/claim links. It does not execute links or assume a hosted provenance endpoint.
- REP-04 summaries still contain selected typed research values, reason codes, identifiers, and
  fingerprints. Apply the source report's access/publication policy before sharing them. PDF
  overflow is a safe refusal and never authorises manual caveat deletion.
- REP-05 opens SQLite with `mode=ro`, immutable mode, and `query_only`, creates no sidecar or
  persistent index, reads only
  direct non-symlink files under the bounded report directory, and redacts POSIX, Windows,
  home-relative, and file-URI absolute paths before matching or snippet creation.
- REP-05 still exposes ordinary domain IDs, annotation prose, report text, and research values.
  Lexical search is not anonymisation; apply the registry/workspace access and publication policy
  before sharing JSON results or screenshots.
- OPS-01 rejects unknown SQLite objects before schema changes, validates object types/columns and
  the immutable checksum ledger, and rolls back the complete plan on failure. `migration-status`
  uses `mode=ro`, immutable mode, and `query_only`; it does not initialise or migrate.
- Migration is not a backup, access-control system, or scientific-payload validator. Protect the
  registry file, make an independent backup before valuable upgrades, and do not manually change
  `user_version` or ledger rows.
- OPS-02 refuses cache roots inside raw directory bundles and rejects symlinked roots, entries, and
  payloads. It verifies exact sizes/SHA-256 digests before Parquet decoding, caps stored bytes,
  decoded bytes, metadata bytes, and table rows, and strictly revalidates all records/summaries.
- Cache files can repeat identifiers and research values from canonical evidence. They are derived,
  not anonymised or encrypted. Apply the raw bundle's access policy, keep shared cache permissions
  restrictive, and do not publish caches containing private evidence. TrafficTwin provides no
  signature, encryption, remote-cache authentication, or automatic secure erasure in OPS-02.
- OPS-03 opens only explicitly selected workspace/registry/cache paths through bounded readers and
  immutable OPS-01/OPS-02 inspectors. It never runs discovered commands, launches simulators,
  repairs files, creates cache entries, migrates registries, or makes network requests. Permission
  checks use `os.access` as advisory setup evidence and are not an operating-system ACL proof.
- Doctor JSON can disclose local paths, installed versions, executable locations, capability gaps,
  and registry/cache condition. Treat it as local diagnostic material and redact or review it
  before publication; its fingerprint supports reproducibility, not tamper resistance.
- Generated standalone data remains synthetic and contains no credentials.

## Current Threat-Model Limitations

The Netlify build consumes only repository-generated synthetic workspace outputs. It does not read
the external TOS package, copy raw bundles, or publish SQLite state. The staged site embeds escaped,
finite JSON and receives restrictive response headers through `netlify.toml`.

The Streamlit Docker image contains only the standalone synthetic workspace. No credentials,
checkpoints, external repositories, or private results are copied into the image.

Public TOS atlas staging requires an explicit permission attestation. This protects against
accidental publication but is not a substitute for obtaining permission.

The optional TOS static atlas embeds precomputed aggregate values in a self-contained HTML file.
It excludes machine-record contents, absolute external paths, raw NPZ arrays, and remote assets,
and it renders source strings with DOM `textContent`. This reduces technical exposure but does not
grant permission to publish source-derived results. Public hosting remains blocked until permitted.

- The project is not hardened for hostile multi-user deployment.
- Streamlit is intended for local research demonstration.
- JSON fingerprints support reproducibility, not adversarial tamper-proofing.
- External simulator execution is not implemented.

OPS-04 research objects use an explicit raw-evidence disclosure policy. `embed` copies exact raw
bytes and is permitted for imported evidence only after the caller declares confirmed permission,
its written basis, and a raw licence. `reference` omits bytes but retains relative names, sizes,
and hashes, so private reference archives remain sensitive. `exclude` retains only an aggregate
count/reason and no raw names or hashes. Public imported embed/reference is refused while
permission is unknown or denied. Derived local paths are redacted and row-level source samples are
omitted unless raw evidence is embedded. These technical gates do not grant legal permission.

OPS-05 external-source discovery is intentionally shallow and read-only. It accepts only exact
direct markers from a closed reviewed adapter registry, blocks symbolic-link roots/markers, and
refuses unknown or ambiguous selection. Portable inspections omit absolute paths and wall-clock
timestamps. The interface loads no uploaded adapter code and performs no launch, registry write,
source repair, or automatic conversion. It also exposes TOS licence and redistribution permission
as `unknown`; successful discovery or validation never grants publication rights.

Related documents:

- [Run bundle specification](run_bundle_spec.md)
- [Architecture](architecture.md)
- [Provenance Explorer](provenance_explorer.md)
- [Standalone demo](standalone_demo.md)
- [Report export](report_export.md)
- [LaTeX research tables and static figures](latex_research_exports.md)
- [RO-Crate research objects and citation](research_objects.md)
- [General external-source contract](integration/external_source_contract.md)
- [Deployment](deployment.md)
- [Limitations and future work](limitations_and_future_work.md)
