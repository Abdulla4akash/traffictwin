# ADR-048: Generalised External-source Contract

- Status: accepted
- Date: 2026-07-21
- Capability: `OPS-05`

## Context

TrafficTwin already has three materially different source boundaries. Ordinary generic bundles are
first-party complete run bundles. The public SUMO adapter maps a bounded subset of `tripinfo` into
canonical trips while retaining summary evidence as source-specific. The private TOS adapter imports
producer aggregate summaries and exposes source-specific replay arrays, but lacks compatible
canonical task, persistent vehicle, task-to-RSU, infrastructure-utilisation, and trip semantics.

Without a shared interface, future sources could duplicate discovery and capability logic or be
forced into a misleading common schema. The interface must expose differences, unknowns, blockers,
and provenance requirements rather than hide them.

## Decision

1. Define a runtime-checkable `ExternalSourceAdapter` protocol with exactly four operations:
   `discover`, `contract`, `validate`, and `inspect`.
2. Publish strict portable models for exact discovery markers, field semantics, provenance
   requirements/observations, complete capability manifests, conversion profiles, typed blockers,
   validation summaries, inspections, and the adapter catalogue.
3. Keep the v1 registry closed and deterministic with two reviewed reference adapters:
   `sumo_results_v1` and `tos_data_read_only`. Generic bundles retain their existing first-party
   validation path.
4. Discover only exact direct relative markers. Do not guess from extensions or directory names.
   Return no-match, ambiguity, and symbolic-link states explicitly; never auto-select among multiple
   matches.
5. Call the existing source-specific validator after selection. The portable summary retains the
   validator/report type, version, finding codes/counts, source fingerprint, declared import state,
   and output counts while excluding wall-clock timestamps and absolute paths.
6. Use four evidence states for meanings and provenance: `confirmed`, `inferred`, `unknown`, and
   `unsupported`. Unknown rights, units, identity, joins, coverage, or versions remain unknown.
7. Use non-ordinal conversion descriptions. SUMO is `partial_canonical` only for its listed
   `TripRecord` projection. TOS is `aggregate_summary` with no canonical-row output. Implementing the
   protocol never establishes equivalence between them.
8. Require each contract to enumerate exact canonical, source-specific, registry, and unavailable
   outputs plus blockers and the evidence needed to revisit each blocker.
9. Keep discovery/inspection read-only: no launch, registry mutation, package repair, manifest
   inference, automatic conversion, dynamic plugin discovery, or uploaded adapter execution.
10. Expose catalogue, discovery, and inspection through a thin `traffictwin integration external`
    CLI and generated JSON/Pydantic references.

## Consequences

- Future sources have one explicit admission shape without inheriting unsupported SUMO or TOS
  semantics.
- Users can see why a package matched, what validation accepted, exactly what conversion occurred,
  and what remains unavailable.
- The same unchanged source and software contract produce a stable portable inspection fingerprint.
- A discovery match is not a validation, permission, realism, or compatibility claim.
- A new adapter requires code review, a versioned contract, fixtures, and acceptance evidence; it
  cannot be installed from an untrusted runtime path in v1.
- Cross-source statistical or metric compatibility remains governed by the downstream metric and
  study contracts, not by adapter-interface membership.

## Acceptance Evidence

Unit, integration, golden, and CLI tests cover protocol conformance, exact catalogue stability,
distinct conversion profiles, complete capability truth, SUMO and TOS discovery/inspection,
unknown rights, deterministic/path-free output, source non-mutation, rejected validation, explicit
adapter mismatch, no match, ambiguity, root/marker symbolic links, and generated references.

## Rejected Alternatives

- Convert every source into an ordinary generic bundle: rejected because TOS and SUMO lack different
  required semantics and would need fabricated fields.
- Treat conversion levels as maturity scores: rejected because output breadth is not evidence
  quality or scientific validity.
- Select the adapter with the most markers: rejected because mixed packages require human-owned
  source identification, not a heuristic tie-break.
- Dynamic Python entry points or uploaded adapters: rejected for v1 because they enlarge the trusted
  code surface and weaken reviewable deterministic contracts.
- Duplicate validators in the shared layer: rejected because source-specific validators remain
  authoritative and tested.
- Include absolute paths or inspection time in fingerprints: rejected because they are local,
  sensitive, and unrelated to the portable source contract.
