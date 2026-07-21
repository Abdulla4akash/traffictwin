# ADR-047: Permission-aware Deterministic RO-Crate Export

- Status: accepted
- Date: 2026-07-21
- Capability: `OPS-04`

## Context

TrafficTwin already produces a typed validation report, deterministic metrics, an EvidencePack,
diagnostic hypotheses, provenance, and reports. A dissertation archive needs these outputs and
their exact software/source identities together, but packaging must not copy private evidence by
default, invent a licence or DOI, leak local paths, introduce wall-clock nondeterminism, or move
scientific calculations into a renderer.

## Decision

1. Implement an attached RO-Crate 1.3 ZIP with CFF 1.2.0 citation metadata over one accepted
   ordinary generic directory or ZIP bundle. SUMO and TOS report this capability `false` in v1.
2. Require a caller-supplied publication date, scope, raw mode, permission state, licence
   statements, and optional persistent identifier. Infer none of these from a filename or source.
3. Use exactly three raw modes: `embed` copies bounded exact bytes; `reference` records relative
   names, sizes, and hashes; `exclude` records only an aggregate count/reason with no raw
   identifiers or hashes.
4. Permit imported raw embedding only with confirmed permission, written basis, and a raw licence.
   Require the same gate for public references. Unknown/denied public imported evidence must be
   excluded. Only manifest-labelled synthetic evidence may resolve unknown to `not_required`.
5. Include existing typed validation, contract, metric, evidence, rule, provenance, report,
   software, policy, and citation artifacts. Reuse ordinary deterministic library services; the
   archive renderer computes no metrics or hypotheses.
6. Include row-level provenance samples only when raw evidence is embedded. Always redact absolute
   local paths from derived JSON and text. Preserve embedded raw bytes unchanged.
7. Bind request, source, software, method, inventory, exclusions, warnings, sizes, and SHA-256
   values in a strict TrafficTwin manifest. Publish `checksums.sha256`; verify its exact member set
   and reconcile it with both the manifest and RO-Crate file entities.
8. Create byte-deterministic ZIPs with sorted stored members, fixed timestamp/mode, caller-owned
   midnight-UTC derived timestamps, bounded counts/sizes, and no symlink or traversal entries.
9. Re-read raw evidence before publication, build and verify in memory, then fsync a temporary file
   and atomically replace only the explicit destination. Refuse overwrite unless requested.
10. Add repository and archive-specific `CITATION.cff`; do not infer a project licence, DOI,
    repository URL, publication permission, or scientific validity.

## Consequences

- Synthetic and permitted archives can be self-contained; restricted work can remain reference-
  only or disclosure-minimised.
- Same inputs/request/runtime/method versions yield identical archive bytes.
- A private reference-mode crate still discloses raw relative names and hashes and must be handled
  as sensitive metadata.
- Exclusion reduces independent raw-file verification but retains the bundle fingerprint and all
  approved derived evidence.
- The current repository licence remains visibly unspecified.
- General source-specific archival export is deferred to a future contract rather than silently
  treating partial SUMO/TOS evidence as a generic bundle.

## Acceptance Evidence

Unit, golden, integration, and CLI tests cover all three raw modes, inventory reconciliation,
imported/public permission gates, permitted public embed, exact archive determinism, sorted stored
members and fixed timestamps, local-path redaction, CFF/RO-Crate/manifest structure, checksum and
tamper rejection, capability truth, contract stability, atomic publication, and offline verify.

## Rejected Alternatives

- Embed every source by default: rejected because permission and confidentiality are not inferred.
- Reference unknown external raw evidence in a public crate: rejected because names and hashes can
  themselves disclose information.
- Use creation time from the wall clock: rejected because it breaks byte reproducibility.
- Compress ZIP members: rejected to keep the v1 byte contract independent of compressor versions.
- Let reporting recalculate or summarise evidence: rejected because typed upstream services own
  scientific calculation.
- Archive registry/cache/workspace contents automatically: rejected because the v1 source boundary
  is one explicit accepted bundle.
- Claim generic RO-Crate validation: rejected; the verifier checks the supported TrafficTwin
  attached-crate profile and integrity contract.
