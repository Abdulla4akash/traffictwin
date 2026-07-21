# Analyst Annotations

`REP-02` records human review context beside typed TrafficTwin artifacts without changing the
evidence. An annotation is an append-only author label, note, decision label, timestamp, and target
reference stored in the SQLite registry.

Annotations are not metrics, findings, diagnoses, provenance, recommendations, approvals, or
authenticated signatures. A later annotation can correct or supersede an earlier one, but the
earlier entry remains visible.

## Supported Targets

The closed v1.0 target catalogue is:

- stored and existence-checked: `experiment`, `run`, `bundle_import`, `metric_collection`,
  `evidence_pack`, `experiment_evidence_pack`, and `experiment_protocol`;
- detached generated references: `diagnostic_report`, `comparison_report`, `statistical_study`,
  and `research_report`.

Detached means TrafficTwin validates the typed identifier but does not claim that the generated
artifact has a registry row. Target IDs are path-free. An optional 64-character SHA-256 fingerprint
binds the note to an exact artifact version. An annotation without a target fingerprint applies to
that typed identifier generally; an exact report target includes both general and matching exact-
fingerprint entries.

## Initialise And Add An Annotation

First import or otherwise register a stored target:

```bash
uv run traffictwin bundle import tests/fixtures/bundles/baseline_valid \
  --registry .demo/registry.sqlite
```

Append a review note:

```bash
uv run traffictwin registry annotation-add \
  --registry .demo/registry.sqlite \
  --target-kind run \
  --target-id run-baseline-001 \
  --author "Akash" \
  --decision-label follow_up \
  --note "Verify the synthetic-data limitation before dissertation use."
```

Decision labels are `observation`, `accepted`, `rejected`, `deferred`, and `follow_up`. They are
human labels and are never treated as computed TrafficTwin outcomes.

## Read History

Read all annotations in ascending sequence order:

```bash
uv run traffictwin registry annotation-list \
  --registry .demo/registry.sqlite \
  --format json
```

Limit the result to one target:

```bash
uv run traffictwin registry annotation-list \
  --registry .demo/registry.sqlite \
  --target-kind run \
  --target-id run-baseline-001 \
  --limit 100 \
  --format json
```

Use `--after-sequence N` to retrieve the next page. Every response states `has_more` and has an
ordered history fingerprint. The maximum page size is 500.

## Include Annotations In Reports

Pass the registry explicitly when generating Markdown, HTML, or PDF:

```bash
uv run traffictwin report run tests/fixtures/bundles/baseline_valid \
  --registry .demo/registry.sqlite \
  --output .demo/reports/annotated-run.html
```

Matching history appears only under **Analyst Annotations — Non-computed**. It does not enter the
report's computed `sections`, typed `claim_references`, metrics, rules, availability, provenance,
or scientific fingerprints. Report generation refuses rather than silently truncating more than
500 matching entries.

In the Streamlit **Reports** page, use **Analyst Annotations (REP-02)** to select a target, add an
author/note/label, and inspect its ordered history. Enable **Include matching append-only analyst
annotations** when regenerating a report. The checkbox is unavailable until the configured
registry exists.

## Python API

```python
from traffictwin.annotations import (
    AnalystAnnotationRequest,
    AnalystArtifactReference,
    AnalystDecisionLabel,
)
from traffictwin.storage.registry import Registry

registry = Registry(".demo/registry.sqlite")
annotation = registry.append_analyst_annotation(
    AnalystAnnotationRequest(
        target=AnalystArtifactReference(kind="run", artifact_id="run-baseline-001"),
        author_label="Akash",
        note="Retain the limitation in the final discussion.",
        decision_label=AnalystDecisionLabel.ACCEPTED,
    )
)
history = registry.list_analyst_annotations(target=annotation.target, limit=100)
```

Use `attach_registry_annotations(report, registry)` from
`traffictwin.reporting.annotation_rendering` to add matching history to an existing
`ResearchReport`.

## Integrity And Limits

- SQLite assigns a monotonic sequence and rejects `UPDATE` and `DELETE` with database triggers.
- Exact annotation content and UTC timestamp determine the annotation ID.
- Author labels are declared text, not verified identities or digital signatures.
- Notes permit bounded multiline Unicode but reject blank text and unsupported control characters.
- Markdown, HTML, and PDF escape analyst text so it cannot create report structure or scripts.
- REP-02 does not add access control, collaborative conflict resolution, rich-text editing, file
  attachments, or external identity-provider integration.

See [ADR-040](decisions/ADR-040-append-only-analyst-annotations.md) and the generated
[annotation contract](reference/generated/analyst_annotation_contract.json).
