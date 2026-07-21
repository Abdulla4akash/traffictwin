# Full-text Registry Search

TrafficTwin `REP-05` provides deterministic, bounded, read-only lexical search across the local
research registry and the workspace report directory. It is designed for finding an existing
artifact, not for calculating evidence, judging importance, or searching external services.

## Searchable Categories

| Category | Indexed content |
|---|---|
| Finding | Stored bundle-validation findings plus structured finding and rule-result records in JSON reports. |
| Annotation | Append-only annotation ID, typed target, author label, decision label, timestamp, fingerprint, and note. |
| Report | Basename, format, report type, size, metadata, and bounded UTF-8 body text. PDF metadata is indexed but its binary body is not. |
| Run | Registered run ID, lifecycle status, algorithm, seed, experiment link, environment metadata, and other stored payload fields. |
| Experiment | Experiment ID, status, research question, hypothesis, seeds, algorithms, and planned design metadata. |
| Evidence reference | Run/experiment EvidencePack identifiers and bounded payload references plus structured report claim references. |

Raw bundle tables, canonical source rows, nested report files, symbolic links, files outside
`workspace/reports`, the web, embeddings, and LLM-generated terms are excluded.

## Matching And Ranking

The query is normalised with Unicode NFKC and case-folding. Punctuation separates terms, duplicate
terms are collapsed, and every unique alphanumeric term must occur in at least one sanitised field.
This is an `AND` query: `completion stadium` does not return a record containing only `completion`.

Ranking is integer-only and category-neutral:

- reference, title, metadata, and body fields have weights `12`, `10`, `6`, and `3`;
- exact whole-field phrases, phrase prefixes, and contained phrases receive `80x`, `40x`, and
  `20x` the field weight;
- each term receives its single best exact-token, token-prefix, or substring contribution of
  `8x`, `4x`, or `2x` the field weight;
- ties use score, declared category order, normalised title, and typed reference.

The score expresses lexical relevance only. It is not confidence, severity, scientific value,
causal strength, or a recommendation.

## Redaction And Read-only Boundary

Absolute POSIX, Windows, home-relative, and `file://` paths are replaced with
`[redacted absolute path]` before matching or snippet creation. Report references use basenames;
registry and workspace paths are never returned. Ordinary research identifiers and relative
evidence references remain visible. The result publishes total and per-hit redaction counts.

An existing registry is opened with SQLite `mode=ro`, `immutable=1`, and
`PRAGMA query_only=ON`. Search never calls registry initialisation, creates an FTS table, migrates
a schema, or writes an index. Report access
is limited to a non-symlink `workspace/reports` directory and its direct non-symlink files.

## Streamlit Use

1. Open **Search**.
2. Enter up to 256 characters and 16 unique terms.
3. Select one or more of the six category labels.
4. Choose a result limit from 10 to 200.
5. Inspect rank, category, title, bounded snippet, typed reference, and score.

The page also shows candidate, matching, returned, omitted, skipped-report, and redaction counts,
plus a fingerprint for the exact result. A skipped-report warning means a file was a symlink,
unreadable, non-UTF-8, or larger than the admitted text limit.

## CLI Use

Show the machine-readable contract:

```bash
traffictwin registry search-contract --format json
```

Search all categories:

```bash
traffictwin registry search "completion stadium" \
  --registry .traffictwin-demo/registry.sqlite \
  --workspace .traffictwin-demo
```

Restrict categories and request JSON:

```bash
traffictwin registry search "R4 queue" \
  --registry .traffictwin-demo/registry.sqlite \
  --workspace .traffictwin-demo \
  --category finding \
  --category evidence_reference \
  --limit 25 \
  --format json
```

## Python Use

```python
from traffictwin.registry_search import SearchCategory, search_registry

result = search_registry(
    ".traffictwin-demo/registry.sqlite",
    "completion stadium",
    workspace_path=".traffictwin-demo",
    categories=[SearchCategory.FINDING, SearchCategory.REPORT],
    limit=25,
)
for hit in result.hits:
    print(hit.rank, hit.category.value, hit.title, hit.reference)
```

`RegistrySearchResult.canonical_json()` is byte-stable for unchanged local inputs and
`fingerprint()` identifies the exact query, scope, inventory, counts, and ranked output.

## Bounds And Failure Modes

- result limit: 1–200, default 50;
- query: at most 256 displayed characters and 16 unique alphanumeric terms;
- inventory: at most 20,000 projected documents;
- reports: at most 500 direct files, 2,000,000 bytes per searchable text file;
- projected text: at most 64,000 characters per document;
- snippets: at most 320 characters.

An empty/punctuation-only query, invalid category, corrupt/unreadable registry, excessive report
inventory, or excessive projected document count fails visibly. An absent registry can still
produce report results when a workspace is supplied; this does not imply that registry-backed
categories were available.

## Interpretation Limits

- Search discovers current local records; it does not validate their content.
- A finding or annotation match is not proof, approval, or current consensus.
- Lexical ranking does not replace statistical analysis or provenance inspection.
- Redaction reduces path exposure but does not anonymise domain IDs, annotation prose, or research
  values. Apply the source workspace's access and publication policy before sharing results.

The governing design decision is [ADR-043](decisions/ADR-043-deterministic-read-only-registry-search.md).
