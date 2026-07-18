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

## Provenance Source-Row Preview

The Provenance Explorer source-row preview:

- uses bundle-relative source paths;
- rejects absolute paths and `..` traversal;
- reuses the safe directory/ZIP bundle loader;
- reads a bounded row window rather than an entire large source file;
- treats source text as data, not executable content.

Trace exports avoid machine-specific absolute paths. They may still include bundle-relative source
filenames, row numbers, validation messages, and raw values from the requested preview, so do not
export traces containing private real data without review.

## Manifest And Text Handling

Manifest, validation, and diagnostic text may be displayed in the UI. The current UI does not intentionally render untrusted HTML. Future richer rendering should continue to escape or treat imported text as plain text.

## Local SQLite Registry

The registry is a local SQLite file for metadata:

- seeds;
- experiments;
- runs;
- bundle import metadata;
- metric JSON;
- evidence-pack JSON.

It is not a credentials store and should not contain private tokens.

## Credentials

No credentials, tokens, API keys, or private keys are required by the current prototype. Future external integrations must avoid committing credentials and should use environment variables or local configuration outside version control.

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

## Future Live Data

Near-live or true-live traffic data would require additional security and privacy review, including retention, consent/authority, access control, and audit considerations.

## Future User-Study Data

Formal user evaluation data should be handled according to ethics approval, anonymisation requirements, consent terms, and university data-management rules.

## Standalone Workspace And Reports

- `demo reset` operates only on a marked TrafficTwin standalone workspace and requires `--yes`.
- The standalone launcher uses a fixed argument-list subprocess command and no shell interpolation.
- Report HTML escapes text and uses no remote assets or JavaScript.
- Reports normalise absolute local paths where practical.
- Generated standalone data remains synthetic and contains no credentials.

## Current Threat-Model Limitations

The optional TOS static atlas embeds precomputed aggregate values in a self-contained HTML file.
It excludes machine-record contents, absolute external paths, raw NPZ arrays, and remote assets,
and it renders source strings with DOM `textContent`. This reduces technical exposure but does not
grant permission to publish source-derived results. Public hosting remains blocked until permitted.

- The project is not hardened for hostile multi-user deployment.
- Streamlit is intended for local research demonstration.
- JSON fingerprints support reproducibility, not adversarial tamper-proofing.
- External simulator execution is not implemented.

Related documents:

- [Run bundle specification](run_bundle_spec.md)
- [Architecture](architecture.md)
- [Provenance Explorer](provenance_explorer.md)
- [Standalone demo](standalone_demo.md)
- [Report export](report_export.md)
- [Limitations and future work](limitations_and_future_work.md)
