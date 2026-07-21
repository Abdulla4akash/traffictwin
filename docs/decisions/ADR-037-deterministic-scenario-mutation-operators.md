# ADR-037 — Deterministic Scenario Mutation Operators

Status: accepted and implemented
Date: 21 July 2026
Capability: `EXP-02`

## Context

TrafficTwin needs reproducible robustness cases that perturb completed labelled fixtures without
changing raw source evidence or pretending to rerun a simulator. The v0.5 specification names row
dropout, timestamp jitter, and RSU removal and requires a `MutationManifest` containing the parent
fingerprint, deterministic operator/parameters/seed, changed rows/files, and synthetic label.

Arbitrary row-edit expressions would create an unsafe data-transformation language. Mutating real
imported evidence would break the raw-immutability contract. Reassigning tasks after removing an
RSU would invent policy behavior that can only be observed by an evidenced execution.

## Decision

EXP-02 version 1.0 accepts one ordinary-valid parent bundle explicitly labelled
`synthetic_fixture`, `synthetic_mutation`, or `synthetic_evaluation`, or using synthetic execution
mode. It rejects real/imported labels, invalid parents, symbolic links, and confirmation-gated
inference manifests. The parent is read-only and the output is a separate derived bundle.

One request applies exactly one closed operator:

- `row_dropout` targets one declared table and drops
  `max(1, floor(row_count × drop_fraction))` rows. Selection uses ascending SHA-256 over the method,
  explicit random seed, table, parent line, and complete parent row.
- `timestamp_jitter` targets one declared table with explicit seconds units. One SHA-256-derived
  signed delta is applied to every present absolute timestamp in a row. The shared delta preserves
  within-row differences and is clamped only when required to keep the earliest value non-negative.
- `rsu_removal` removes exact matching infrastructure rows and records the RSU in the derived seed.
  Tasks are copied unchanged: no decision, target, outcome, timing, energy, rerouting, scheduling,
  retraining, or policy response is inferred.

The mutable target must be a declared uncompressed CSV. Non-target files are copied byte-for-byte.
Gzip and Parquet targets require future encoding-preservation decisions and are unsupported.

The bounds are 64 source files, 25,000,000 source bytes, 100,000 target rows, 20,000 changed rows,
3,600 seconds maximum jitter, and a 1,000,000-byte request. A complete exact ledger is mandatory;
the system rejects rather than truncates it.

Every output receives deterministic derived bundle/run/seed IDs, parent-linked seed provenance,
`source=synthetic_mutation`, synthetic execution mode, recomputed declared-file checksums, and a
deterministic bundle fingerprint. The result records request, plan, parent bundle, derived bundle,
and timestamp-independent result fingerprints.

Materialisation writes `bundle/` under a temporary sibling, validates it with the ordinary bundle
pipeline, checks the planned fingerprint, writes `mutation_manifest.json` beside—not inside—the
bundle, and only then replaces the exact destination with explicit overwrite. Protected broad and
symbolic-link destinations are rejected, as is any destination that equals, contains, or sits
inside its parent bundle. Overwrite moves the previous destination aside and restores it when the
final publication rename fails.

## Consequences

- Robustness cases are reproducible and every changed row is auditable.
- The ordinary validator/metric/rule/provenance stack sees a normal derived bundle.
- Parent bytes and identifiers remain authoritative and unchanged.
- RSU removal can make exact target-based evidence incomplete without fabricating a rerouting
  outcome.
- Mutation chains remain explicit because each request has one parent and one operator.
- EXP-03 measurement-noise/dropout models remain separate generator-level work.

## Rejected Alternatives

- **Edit a parent bundle in place:** destroys raw/source identity and reproducibility.
- **Admit any imported bundle:** a label is required so real evidence cannot be silently rewritten.
- **Arbitrary Python, expressions, JSONPath, or row predicates:** creates an unbounded code/data
  transformation surface.
- **Random module state:** results could vary with call order or process state.
- **Silent ledger truncation:** would conceal changed evidence.
- **Rewrite tasks after RSU removal:** invents an unevidenced policy response.
- **Put the mutation manifest inside the derived fingerprinted bundle:** creates a circular
  dependency when the manifest records that fingerprint.
- **Treat mutations as real sensor/failure models:** controlled fixtures do not establish fidelity.

## Acceptance Evidence

- Unit tests pin seeded dropout, jitter bounds/invariants, RSU behavior, parent immutability,
  request round trips, ZIP equivalence, source-label/target/limit/protected-path rejection,
  source/destination separation, rollback-preserving transactional overwrite, capability
  boundaries, and stable fingerprints.
- Golden coverage pins the exact changed row, parent line/fingerprint, file checksums/counts,
  derived identities, bundle fingerprint, and result fingerprint.
- CLI integration covers the public contract, successful ordinary-valid materialisation, and
  destination conflicts.
- UI service and Streamlit AppTest coverage prove the page delegates planning and execution to the
  typed library layer.
- Generated schemas/contracts, architecture, assumptions, status, security, usage, limitations,
  and traceability records expose the same boundary.
