# RO-Crate Research Objects And Citation

TrafficTwin `OPS-04` turns one accepted ordinary generic directory or ZIP run bundle into a
verified, deterministic attached
[RO-Crate 1.3](https://www.researchobject.org/ro-crate/specification/1.3/index.html) ZIP with
[Citation File Format 1.2](https://citation-file-format.github.io/). The archive packages existing
deterministic
metrics, evidence, diagnostic hypotheses, provenance, and reports; it does not add new scientific
calculations or infer publication rights.

## Quick Start

Create a private archive that references raw files by relative name, size, and SHA-256 without
copying their bytes:

```bash
.venv/bin/traffictwin archive create path/to/bundle build/run-ro-crate.zip \
  --publication-date 2026-07-21 \
  --raw-evidence reference
```

Verify it offline:

```bash
.venv/bin/traffictwin archive verify build/run-ro-crate.zip
```

Inspect the public method contract:

```bash
.venv/bin/traffictwin archive contract --format json
```

The publication date is required because wall-clock time is never read into a reproducible
archive. The caller owns the date and every publication, licence, permission, and identifier
statement.

## Raw-Evidence Modes

| Mode | Raw bytes copied? | Raw relative names and SHA-256 retained? | Intended use |
|---|---:|---:|---|
| `embed` | yes | yes | Synthetic evidence, or imported evidence with explicit confirmed permission, basis, and licence |
| `reference` | no | yes | Private working archive when evidence must remain in its controlled location |
| `exclude` | no | no | Public/private archive where even raw names and hashes must not be disclosed |

`exclude` records only an aggregate file count and reason. It deliberately carries no raw path,
identifier, or checksum. Derived artifacts remain attached and retain the bundle-level source
fingerprint.

For a labelled TrafficTwin synthetic bundle, an unknown raw permission resolves to
`not_required`, while every raw inventory item remains visibly `synthetic=true`. For imported
historical evidence:

- `embed` requires `--permission-status confirmed`, `--permission-basis`, and
  `--raw-evidence-licence`;
- public `reference` requires the same confirmation and licence;
- public unknown or denied evidence must use `exclude`;
- `not_required` is rejected because TrafficTwin cannot infer that an external source needs no
  permission.

Example permitted public embed:

```bash
.venv/bin/traffictwin archive create path/to/bundle build/public-ro-crate.zip \
  --publication-date 2026-07-21 \
  --publication-scope public \
  --raw-evidence embed \
  --permission-status confirmed \
  --permission-basis "Written permission held in the project records" \
  --raw-evidence-licence "Permission-limited research reuse"
```

TrafficTwin records these caller statements but does not validate their legal sufficiency.

## Archive Contents

Every archive contains:

- `ro-crate-metadata.json` using the RO-Crate 1.3 JSON-LD context;
- an archive-specific CFF 1.2.0 `CITATION.cff` of type `dataset`;
- `research-object-manifest.json`, the strict TrafficTwin inventory and inclusion policy;
- `checksums.sha256` for all payload members and the TrafficTwin manifest;
- the accepted source manifest and validation report;
- canonical schema/mapping and software/method version metadata;
- the deterministic `MetricCollection`, `EvidencePack`, `DiagnosticReport`, and provenance trace;
- the structured report plus Markdown and self-contained HTML renderings;
- raw evidence under `data/raw/` only when the resolved policy is `embed`.

The repository-level [CITATION.cff](../CITATION.cff) describes the TrafficTwin software. The copy
inside each archive describes that particular research dataset and publication date.

## Determinism And Integrity

For identical raw bytes, request, TrafficTwin/Python versions, and method contracts, archive bytes
are identical. The builder:

1. safely opens the directory or ZIP and requires an accepted ordinary generic bundle;
2. reads bounded raw files and confirms the validator fingerprint;
3. fixes all derived timestamps to midnight UTC on the declared publication date;
4. computes metrics, evidence, rules, provenance, and reports through their existing library
   services;
5. re-reads raw files before publication to detect a concurrent change;
6. renders sorted members with fixed permissions, stored ZIP entries, and the fixed ZIP timestamp
   `1980-01-01T00:00:00`;
7. verifies member safety, limits, CFF, manifest reconciliation, RO-Crate graph, sizes, SHA-256
   values, and public-permission policy in memory;
8. fsyncs a private temporary file and atomically replaces the explicit destination.

The builder refuses symlinked sources/destinations, unsafe archive paths, duplicate members,
non-stored or non-deterministically timestamped input archives, oversized files/archives, checksum
drift, inventory drift, and an existing destination unless `--overwrite` is explicit.

Absolute POSIX, Windows, home-relative, and `file://` paths are redacted from derived JSON and
reports. Raw file contents are never rewritten; if embedded, their exact bytes are copied.
Row-level provenance samples are included only with `embed`, because a sample can disclose raw
values even when raw bytes are not attached.

## Python API

```python
from datetime import date

from traffictwin.research_object import (
    RawEvidenceDisposition,
    ResearchObjectRequest,
    create_research_object_archive,
    verify_research_object,
)

request = ResearchObjectRequest(
    publication_date=date(2026, 7, 21),
    raw_evidence=RawEvidenceDisposition.REFERENCE,
)
receipt = create_research_object_archive(
    "path/to/bundle",
    "build/run-ro-crate.zip",
    request,
)
verification = verify_research_object("build/run-ro-crate.zip")
assert verification.valid
```

`build_research_object()` returns the in-memory typed manifest and members without publishing a
file. `research_object_contract()` returns the stable method/safety contract. The JSON contract is
also generated at
[reference/generated/research_object_contract.json](reference/generated/research_object_contract.json).

## Interpretation And Limits

- Checksums prove byte identity, not truth, quality, originality, authorship, or causal validity.
- Provenance records lineage and does not establish causality.
- A complete crate does not prove that publication permission or a licence statement is correct.
- The root repository licence is still unspecified; the default statement grants no additional
  rights.
- v1 accepts only the complete ordinary generic bundle pipeline. SUMO and TOS remain explicitly
  unsupported for OPS-04 until their source-specific artifacts can satisfy the complete typed
  metrics/evidence/diagnostics/provenance/report contract without false equivalence.
- The verifier is an offline TrafficTwin conformance/integrity check, not a general JSON-LD or
  legal-review service.

See [ADR-047](decisions/ADR-047-permission-aware-deterministic-ro-crate.md),
[security and privacy](security_and_privacy.md), and
[reproducibility](reproducibility.md).
