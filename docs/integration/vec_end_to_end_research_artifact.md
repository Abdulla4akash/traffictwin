# VEC-12 End-to-End Research Artifact

Status: implemented and accepted for the audited VEC-01 through VEC-11 evidence chain.

The checked-in artifact is
[`vec_end_to_end_research_artifact.zip`](../reference/generated/vec_end_to_end_research_artifact.zip),
with a separate
[`receipt`](../reference/generated/vec_end_to_end_research_artifact_receipt.json). It is a
deterministic, offline-verifiable reconciliation artifact, not a raw-data archive and not evidence
that every blocked scientific interpretation has become available.

## What it binds

The manifest binds all accepted upstream capability evidence:

- VEC-01/VEC-02 audited source commits, file evidence, and observed source contract;
- VEC-03/VEC-04/VEC-05 identity, task/action/target, and trip join reports;
- VEC-06 as an accepted alternative preprocessing path, explicitly marked as not consumed by the
  selected reproduction case;
- VEC-07 request/receipt identity through the accepted VEC-08 reproduction report;
- VEC-08's protocol-seed numerical-equivalence result and recorded runtime environment;
- VEC-09's distinct `_s102_best_of_seeds` scientific run, 18 available metrics, eight unavailable
  metrics, and R1/R2/R6/R7 readiness without findings;
- VEC-10 thin-interface acceptance evidence; and
- VEC-11's three-row sanitised sample, aggregates, citations, permission, and exclusions.

The VEC-08 protocol-seed case and VEC-09/VEC-11 selected `_s102` run are deliberately distinct in
the manifest. Their labels must not be collapsed into one run claim.

## Archive format and verification

The ZIP contains exactly 27 sorted, stored members with a fixed 1980 timestamp. It includes a
manifest, one checksum line for every other member, citations, limitations, provenance, generated
contracts, accepted audit/report metadata, and the VEC-11 publication pack. Members are bounded to
1 MB each and the complete archive to 2 MB. Verification does not extract files and requires no
network or external repository access.

```bash
uv run traffictwin integration vec research-verify \
  docs/reference/generated/vec_end_to_end_research_artifact.zip
```

For machine-readable output:

```bash
uv run traffictwin integration vec research-verify \
  docs/reference/generated/vec_end_to_end_research_artifact.zip \
  --format json
```

The verifier checks the exact member set and order, duplicate/traversal/symlink refusal, fixed ZIP
metadata, stored compression, size bounds, every SHA-256, manifest inventory, artifact identity,
sample count, and private-path exclusion.

## Rebuild

The destination ZIP and receipt must not already exist:

```bash
uv run python scripts/build_vec_end_to_end_artifact.py \
  --generated-root docs/reference/generated \
  --output /tmp/vec_end_to_end_research_artifact.zip \
  --receipt /tmp/vec_end_to_end_research_artifact_receipt.json
```

The builder fails closed if a generated contract is stale, an upstream report is not accepted, a
fingerprint/commit/run label does not reconcile, a required member is unsafe, or a publication
claim exceeds the VEC-11 permission. A successful rebuild is byte-identical to the checked-in ZIP.

The same operations are available from Python through
`traffictwin.integration.vec_research` and from the CLI through `research-contract`,
`research-create`, and `research-verify` under `traffictwin integration vec`.

## Deliberate limits

The archive embeds no raw NPZ/XML, evaluator output bytes, actor checkpoint, source repository,
source identity mapping, private path, or third-party SUMO asset. Hashes prove artifact identity,
not scientific truth by themselves. Deadline success is not physical completion; eligible targets
are not confirmed transfers; per-task energy remains unavailable; R1, R2, and R7 remain blocked;
R6 remains conditional; no causal claim is made. The sample is pseudonymised, not anonymous.
Randy's permission is not a formal software/data licence, and public hosting remains unauthorised.

## Acceptance checks

```bash
uv run pytest -q tests/unit/test_vec_research.py tests/integration/test_vec_research.py
```

The tests cover byte-identical rebuilds, checked-in receipt reconciliation, offline verification,
corruption and extra-member refusal, stale-contract refusal, strengthened-claim refusal, complete
VEC-01–VEC-11 lineage, and CLI operation.

## Related evidence

- [VEC-01 source audit](randy-source-snapshot-audit-v0_6.md)
- [VEC-08 reproduction verification](vec_reproduction_verification.md)
- [VEC-09 scientific admission](vec_scientific_admission.md)
- [VEC-11 dissertation pack](vec_dissertation_pack.md)
- [Generated VEC-12 contract](../reference/generated/vec_end_to_end_contract.json)
- [ADR-051](../decisions/ADR-051-deterministic-vec-end-to-end-research-artifact.md)
