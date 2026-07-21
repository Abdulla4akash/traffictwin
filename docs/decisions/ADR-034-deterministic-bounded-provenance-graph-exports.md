# ADR-034 — Deterministic Bounded Provenance Graph Exports

Status: accepted and implemented
Date: 20 July 2026
Capability: `PRO-02`

## Context

TrafficTwin already builds a versioned `ProvenanceTrace` directed acyclic graph for runs, metrics,
rules, canonical records, source rows, definitions, findings, fingerprints, and unavailable
references. The v0.5 design requires deterministic DOT and GraphML exports plus a bounded explorer
view. Export must not introduce a second lineage calculation, leak machine-local absolute paths,
silently omit an unbounded amount of data, or turn renderer layout into scientific evidence.

The existing trace has stable node identifiers and typed relations, but edges have no explicit
identifier. Trace IDs and generation timestamps are intentionally event-specific, so they are not
a suitable stable identity for an evidence-equivalent graph. Rich node attributes may also contain
private values even after absolute paths have been removed.

## Decision

TrafficTwin adds a separate `ProvenanceGraphView` schema version 1.0. It is a deterministic,
bounded, sanitised projection of an already-built `ProvenanceTrace`; it never reads a source path,
recomputes a metric, evaluates a rule, or derives a new lineage relation.

The default limits are 120 nodes and 240 edges. The public hard maxima are 500 nodes and 2,000
edges. Selection starts at the trace root and performs deterministic undirected breadth-first
traversal over lexically ordered typed edge fields. Treating edges as undirected for selection lets
the view include both upstream and downstream context while preserving every retained edge's
original direction. If capacity remains, disconnected nodes are added in lexical order. Edges
whose endpoints are retained are sorted deterministically and clipped to the edge limit. The view
publishes total, retained, and omitted counts plus an exact `truncated` flag.

Safe node IDs are retained unchanged. If an ID contains a machine-local absolute path, it receives
a deterministic redacted alias within the graph. Each edge receives a stable ID derived from the
sanitised typed source, target, relation, description, and confidence; deterministic suffixes
separate otherwise identical edges. The graph identity is derived from the complete sanitised
graph, not the requested limits, and excludes trace IDs plus trace/node timestamps. Therefore two
bounded views of the same sanitised graph share one graph identity while their view fingerprints
remain limit-specific.

Two disclosure profiles are supported:

- `safe` is the default. It retains typed descriptions, attributes, and bundle-relative source
  references after recursive redaction of POSIX, Windows, home-relative, and `file://` local paths.
- `structure_only` retains IDs, types, labels, statuses, synthetic flags, and relations. It removes
  node descriptions, attributes, source references, and edge descriptions.

Both profiles replace invalid XML control characters. Text is escaped separately for DOT and XML.
The exporter never follows a link or opens a referenced file. Safe mode is path-safe but not an
anonymisation system: ordinary run, vehicle, RSU, file, and canonical scalar values may remain.
Private exports therefore require review or the structure-only profile.

DOT and GraphML are generated with fixed ordering and keys. GraphML contains typed graph, node, and
edge data and is parser-tested. DOT contains escaped labels and stable status/root styling. The
renderer may choose different coordinates or shapes; layout output is deliberately not part of the
deterministic artifact.

The Streamlit explorer calls the same typed bounded-view builder and DOT serializer. It exposes
limits, the disclosure profile, retained/total counts, exact omission counts, a selected-node
inspector, and DOT/GraphML downloads. The CLI extends `provenance export` and publishes a separate
`provenance graph-contract` command.

## Consequences

- A trace can be inspected in Graphviz-compatible tools and GraphML consumers without adding a
  graph database or a runtime Graphviz dependency to deterministic generation.
- Large traces cannot silently overwhelm the UI or export path; every omission is quantified.
- Existing trace node/relation semantics remain authoritative and unchanged.
- Machine timestamps and absolute paths do not make evidence-equivalent graph exports differ.
- Structure-only export offers a lower-disclosure sharing option, but it is not a guarantee of
  anonymity because stable domain identifiers can still be sensitive.
- Current generic traces and evidenced TOS traces can use the serializer. The current SUMO source
  contract does not yet expose a provenance-trace entry point and advertises this capability as
  false.

## Rejected Alternatives

- **Render the full trace unconditionally:** large or adversarially broad traces would violate the
  bounded-view requirement and make omissions impossible to audit.
- **Use insertion order:** construction order is not a scientific or stable traversal policy.
- **Follow only outgoing edges:** some trace roots have important context connected by incoming
  relations.
- **Use volatile `trace_id` as the graph ID:** the trace ID incorporates generation time and would
  change for evidence-equivalent graphs.
- **Export raw absolute paths:** this leaks usernames, mount points, and private directory names.
- **Hash every node ID:** safe stable identifiers are valuable for reconciling JSON, Markdown,
  DOT, GraphML, and the UI.
- **Offer an unrestricted redaction mode:** a convenient unsafe option would weaken the default
  path-safety contract.
- **Treat Graphviz layout as deterministic evidence:** renderer versions and layout engines can
  move nodes without any change to lineage.
- **Build a second graph from UI tables:** duplicate derivation would allow the UI to disagree with
  the tested provenance library.

## Acceptance Evidence

- Unit tests cover root-centred bounds, exact omission counts, limit rejection, deterministic
  graph/view identities, timestamp independence, both disclosure modes, absolute-path redaction,
  DOT escaping, GraphML parsing, and invalid mode rejection.
- Golden DOT and GraphML files pin node/edge IDs, ordering, keys, labels, data, and styling.
- CLI integration tests cover the contract, bounded DOT output, structure-only GraphML, parsing,
  and output-path non-disclosure.
- UI service and Streamlit AppTest coverage prove the page delegates to the typed core and exposes
  graph inspection/downloads.
- Synthetic demo initialization writes deterministic metric-trace DOT and GraphML files.
- Capability manifests, generated schemas/help/contract, architecture, usage, security,
  reproducibility, limitations, status, and traceability records are reconciled.
