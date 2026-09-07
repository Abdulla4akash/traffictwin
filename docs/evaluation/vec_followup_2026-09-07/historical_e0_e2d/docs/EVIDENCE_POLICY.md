# Evidence Publication Policy

## Included

- Public-safe compact CSV result tables.
- Machine-readable comparison, validation and mechanism records where they contain no private local paths.
- Public-sanitized derivatives of selected high-value records that did contain private paths.
- Exact source/manifest/evidence hashes.
- Original analysis code written for this public repository.
- Generated figures and explanatory reports.

## Omitted

- Raw per-task/per-step `.npz` arrays.
- Model checkpoints and incident trace files.
- Private TrafficTwin, vec_env and tos-data source.
- Third-party/Manchester simulator source with unclear redistribution rights.
- Private GitHub URLs, local raw-output locations and scratch paths.

## Transformation rule

When a frozen record contains an absolute private path, the public copy is named `*_public_sanitized.json`. Only path-like strings are replaced with `<private-local-path-redacted>`. The original frozen SHA-256 and the new public SHA-256 are both recorded; the sanitized derivative is never represented as byte-identical to the original.

## Integrity rule

Scientific values, estimands, seed roles, confidence intervals, validation outcomes and claim boundaries are not altered during sanitization. Raw ledgers are referenced by identity, not rewritten.

## Licensing

Only documentation, compact extracts, figures and analysis code authored for or owned by this research record are published. Referenced upstream/private code is not included and receives no licence from this repository.
