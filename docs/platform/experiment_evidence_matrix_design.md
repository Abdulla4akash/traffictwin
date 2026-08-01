# Design — Experiment evidence matrix (post-v1 E-1)

**Status: PROPOSED post-v1 design; owner review pending, unimplemented and not approved for build.
Maximum policy ceiling: `owner_approved_candidate`. This is a provenance and coverage
index, not a meta-analysis, evidence-admission authority or claim that every matrix cell is
scientifically comparable.**

## 1. Purpose

Meeting 3 repeatedly asked how many experiments had been run, which baselines and seeds
were used, whether other traces and demand levels were covered, and which conclusions were
statistically supportable. Today those answers require reading the experiment catalogue,
register, protocols and individual analyses together. The evidence matrix gives each
executed or proposed comparison one typed row and makes gaps visible.

## 2. Unit of record

One `EvidenceMatrixRow` represents one design-compatible comparison or explicitly declared
single arm. Required fields:

- stable experiment/design id and fingerprint;
- status: `proposed`, `executed`, `analysed`, `admitted`, `non_admitted` or `refused`;
- evidence role and policy ceiling;
- trace/source family, locality and provenance digest;
- actor/checkpoint family and observation/action contract digest;
- fleet preset/size, capacity arm(s), demand treatment and simulator/tool versions;
- seed set, pairing rule, held-out/training relationship and execution deviation;
- primary/secondary endpoints and available mechanism diagnostics;
- analysis digest, citation bundle and explicit exclusion reason.

An axis value may be `not_applicable`, `not_recorded` or `not_tested`; these are not
interchangeable with zero.

## 3. Compatibility and grouping

Rows can be grouped only when a versioned `CompatibilityRule` says their design,
observation/action contract, trace treatment, capacity definition, endpoint implementation
and evidence role are compatible for that view. Default behaviour is separation.

The matrix provides counts and coverage, not pooled effect estimates. A future meta-analysis
would need its own protocol, weighting, heterogeneity treatment and owner approval.

Required default facets:

- traces × actors × capacity arms;
- experiments × seed counts × pairing completeness;
- protocol-confirmed × post-hoc × exploratory × descriptive;
- admitted × non-admitted × execution-deviated;
- endpoint availability and mechanism-diagnostic availability;
- measured, proposed and untested coverage.

## 4. Authoritative sources

The builder reads the committed
[experiment catalogue](../evaluation/experiment_catalogue_20260730.md), experiment
registry/records, protocol artifacts and digest-pinned analyses. Hand-entered UI rows are
forbidden. A proposal can appear only as `proposed`/`evidence: false`; execution does not
automatically change it to admitted.

The current Sparse-64 bus/GPU work remains `NON_ADMITTED` and outside the admitted VEC
matrix even though all five fresh seeds completed. Completion and admission are separate
axes. Earlier and fresh execution/provenance deviations remain visible.

## 5. Derived summaries

Safe derived summaries are deterministic counts such as number of compatible rows, unique
seeds, traces, actor families, capacities, missing endpoints and refusal reasons. Every
summary carries the exact included row ids and matrix-build digest.

The confirmed capacity comparison must not be summarised as conventionally significant:
five paired held-out seeds impose an exact two-sided sign-test floor of p=0.0625. A unanimous
direction may be displayed only with that limitation and the endpoint-coherence context
specified by the
[mechanism and policy observatory](mechanism_policy_observatory_design.md).

## 6. API and rendering

Minimum library surface:

- `build_evidence_matrix(source_set) -> EvidenceMatrix | MatrixRefusal`
- `filter_rows(query) -> MatrixSelection | MatrixRefusal`
- `summarise_coverage(selection) -> CoverageSummary`
- `explain_cell(axis_values) -> CellExplanation`

The UI shows row counts, support and exclusions next to every visual. Empty cells say why:
not run, incompatible, refused, non-admitted or metadata missing. Filters never alter row
standing or write back to source records.

## 7. Typed refusals

At minimum: `SOURCE_RECORD_MISSING`, `DIGEST_MISMATCH`, `DESIGN_ID_COLLISION`,
`STATUS_TRANSITION_UNPROVEN`, `INCOMPATIBLE_GROUPING`, `SEED_SET_AMBIGUOUS`,
`HELDOUT_RELATION_UNKNOWN`, `EVIDENCE_ROLE_MIXED`, `NON_ADMITTED_PROMOTION`,
`CITATION_BUNDLE_MISSING` and `PRIVATE_CONTENT_DETECTED`.

## 8. Verification and acceptance

Tests reconcile matrix rows and counts against the authoritative catalogue, preserve
execution deviations, distinguish completion from admission, reject duplicate design ids,
and prove grouping is order-independent. Golden tests pin representative confirmed,
post-hoc, proposed and non-admitted rows. Link and citation audits verify every source.

Acceptance requires exact row-to-source provenance, no private paths, explicit unknowns,
no incompatible pooling, no admission mutation and identical output for the same ordered
source-digest set.

## 9. Owner decisions and stop conditions

The owner must approve the public/default facets, treatment of abandoned proposals and
whether non-admitted rows appear by default or behind a separate view. Stop if a requested
summary requires a new statistical synthesis, unstated compatibility judgement, private
evidence, or reclassification of an experiment's standing.
