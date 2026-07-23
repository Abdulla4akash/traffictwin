# Manchester source-to-VEC research lineage

Status: **candidate library evidence — `MAN-11` remains `planned`**

`traffictwin.integration.manchester.research_lineage` builds the proposed
`ManchesterResearchLineage` artifact from references to already-produced evidence. It is a pure,
offline boundary: it does not download data, read artifact files, launch SUMO or VEC, calculate a
metric, approve a contract, publish a pack, or change capability truth.

The graph answers one bounded provenance question: *which exact artifact from each accepted stage
is declared to feed the next stage?* It does not answer whether the simulation is realistic,
whether a Randy policy is valid for Manchester, whether any difference is causal, or whether any
artifact may be publicly hosted.

## Fixed chain

The order is frozen from v0.7 design Gate E and the accepted v0.6 VEC gates:

1. `source_snapshot` — `MAN-01` immutable Manchester source snapshot;
2. `projection` — `MAN-07` canonical projection report;
3. `network_mapping` — `MAN-09` reviewed network/site mapping;
4. `calibration` — `MAN-09` calibration report or accepted-baseline evidence;
5. `sumo_execution` — controlled Manchester SUMO execution receipt;
6. `fcd_preprocessing` — `VEC-06` one-second FCD/network preprocessing receipt;
7. `vec_execution` — `VEC-07` evaluator receipt;
8. `vec_reproduction` — `VEC-08` reproduction report;
9. `scientific_admission` — `VEC-09` admission report;
10. `thin_interface` — `VEC-10` interface evidence;
11. `permission_pack` — `VEC-11` permission-bounded dissertation-pack manifest; and
12. `research_archive` — `VEC-12` deterministic archive receipt.

The builder accepts only an exact contiguous prefix. A projection without a source snapshot, a VEC
receipt without VEC-06, a repeated stage, or any reordering is refused. Every stage after the first
must carry exactly the immediate parent's artifact fingerprint. Artifact IDs and fingerprints are
unique across a lineage. This prevents a later result from being presented as part of the chain
when an earlier gate is missing or when its identity is not bound.

## Reference contract

`ManchesterLineageArtifactReference` contains only portable metadata:

- the fixed stage and exact allowed artifact kind;
- a safe path-free artifact ID;
- the artifact and versioned-contract SHA-256 fingerprints;
- zero parent fingerprints for the source or exactly one for a downstream stage;
- sorted immutable Manchester snapshot IDs on the source stage only;
- the artifact's publication class; and
- the source synthetic classification, preserved unchanged through the whole chain.

No file path, raw row, vehicle identifier, credential, command, executable, URL, output byte, or
arbitrary capability label is representable. The reference proves self-consistent declared
identity, not the authenticity of a file. A caller must still load and verify each typed upstream
artifact through its owning service before constructing the reference.

## Truthful partial lineages

An empty or partial graph is a valid result. The first absent stage is
`artifact_not_supplied`; every later stage is `upstream_stage_unavailable`. This is intentionally
different from silently omitting missing evidence. Each stage publishes its owning capability IDs,
position, state, reason, optional artifact, and a derived evidence label.

For observed-source chains, labels change without changing the source truth:

- source, projection, and mapping are `observed_manchester_evidence`;
- calibration is `manchester_calibration_candidate`;
- SUMO and FCD stages are `manchester_calibrated_simulation`; and
- VEC stages are `randy_policy_on_manchester_calibrated_simulation`.

For fixture-only chains, every available stage remains `synthetic_development`. Mixed synthetic
and observed declarations are refused.

## Reload integrity

`ManchesterResearchLineage` embeds the canonical artifact references, all 12 stages, and all 11
adjacent edges. On JSON reload it re-derives:

- stage order, capability ownership, state, reasons, and evidence labels;
- active edges and both endpoint fingerprints;
- empty/partial/complete state and the furthest available stage;
- available/unavailable counts and source snapshot inventory; and
- the graph fingerprint over the exact artifact, stage, and edge inventories.

Changing a parent hash, stage or edge, count, blocker, source inventory, graph fingerprint, or
classification while retaining the old result therefore fails validation.

## Interpretation boundary

Even a complete 12-stage graph fixes all of these fields to `False`:

- `public_export_available`;
- `execution_performed_by_lineage_builder`;
- `artifact_bytes_embedded`;
- `capability_acceptance_performed`;
- `domain_validity_established`;
- `causal_claim_available`;
- `randy_policy_validated_for_manchester`; and
- `generated_analysis_sites_are_canonical_infrastructure`.

The fixed interpretation is:

> A complete lineage proves that named artifacts form the declared Manchester-to-VEC software
> chain; it does not prove Manchester realism, Randy-policy domain validity, causality,
> public-hosting permission, or capability acceptance.

## Example

The builder records an already-verified prefix. It does not open the referenced artifacts:

```python
from traffictwin.integration.manchester import (
    ManchesterLineageArtifactKind,
    ManchesterLineageArtifactReference,
    ManchesterLineageStageName,
    ManchesterPublicationClass,
    build_manchester_research_lineage,
)

source = ManchesterLineageArtifactReference(
    stage=ManchesterLineageStageName.SOURCE_SNAPSHOT,
    artifact_kind=ManchesterLineageArtifactKind.SOURCE_SNAPSHOT,
    artifact_id="dft-source-manifest",
    artifact_fingerprint="a" * 64,
    contract_fingerprint="b" * 64,
    parent_artifact_fingerprints=(),
    source_snapshot_ids=("dft-20260723T120000Z-aaaaaaaaaaaa",),
    publication_class=ManchesterPublicationClass.PRIVATE,
    synthetic=False,
)

lineage = build_manchester_research_lineage([source])
assert lineage.chain_state == "partial"
assert lineage.furthest_available_stage == "source_snapshot"
```

## Verification and remaining blockers

`tests/unit/test_manchester_research_lineage.py` covers empty, partial, complete, observed, and
synthetic graphs; gaps and reordering; wrong kinds and parents; unsafe source IDs; duplicate
identities; mixed classifications; canonical round trips; top-level, stage, edge, and embedded
artifact mutation; forbidden fields; and every fixed negative claim.

This candidate does **not** complete `MAN-11`. Gate E still needs an accepted Manchester baseline,
reviewed network and calibration, a matching one-second FCD/network pair, real controlled SUMO and
VEC receipts through VEC-12, permission-aware packaging, and the predeclared research/usability
evaluation. The current MAN-09 production calibration registry and MAN-10 production comparison
registry are empty, and a Manchester-calibrated trace still cannot establish Randy-policy domain
validity by itself.
