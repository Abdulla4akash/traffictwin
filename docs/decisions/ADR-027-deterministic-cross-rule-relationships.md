# ADR-027 — Deterministic Cross-Rule Relationships

Status: accepted and implemented
Date: 20 July 2026
Capability: `DIA-07`

## Context

TrafficTwin retains independent deterministic `RuleResult` objects, but multiple rules can be
active over related evidence. `DIA-07` requires explicit conflict, corroboration, and suppression
without inventing probabilistic confidence or hiding an original result. The repository already
reported two untyped conflict observations, including the R1/R2 mixed-fault case, but those strings
did not publish a versioned activation policy, exact overlap, precedence, or result fingerprints.

An unrestricted pairwise inference mechanism would imply relationships that have not been
calibrated. In particular, similar words, common metric domains, or simultaneous triggering do not
by themselves establish conflict or corroboration. Suppression is especially risky because it can
make inconvenient evidence disappear.

## Decision

TrafficTwin implements an additive `CrossRuleReasoningReport` over completed `RuleResult` objects.
It cannot read source files, recalculate metrics, change a status or confidence, delete a result,
or add a recommendation. Every input result and its timestamp-normalised fingerprint is retained;
the ordinary `DiagnosticReport.results` list remains authoritative.

The version 1.0 policy admits exactly three relationships:

1. **R1/R2 conflict:** both rules must be `triggered` and both must cite the exact
   `task.generated.count` key. The relationship records competing policy-under-use and
   infrastructure-saturation candidates and chooses no winner.
2. **R1/R4 corroboration:** both rules must be `triggered` and both must cite the exact
   `infra.utilisation.mean` key. This records compatible remaining-capacity/load-distribution
   context only. It does not raise either rule's categorical confidence.
3. **R0 suppression:** R0 must be `triggered` and explicitly name the target in its existing
   `blocked_rules` metadata. R0 has data-readiness precedence 100; ordinary diagnostic rules have
   equal precedence 50. Suppression means the retained target is non-actionable while blocked. It
   never deletes or rewrites the target.

Fixed-pair relationships require their declared exact shared evidence key. The report also records
all exact shared, source-only, and target-only cited keys. R0 suppression uses its explicit blocker
declaration and may have no shared available key because absence is the reason for the block.

No pairwise ranking exists among ordinary rules. No probability, relationship strength, confidence
increment, causal attribution, or automatic recommendation is computed. R3, R5-R8, undeclared
core pairs, and arbitrary declarative rules remain visibly unclassified until a separately
approved policy exists. No relationship is safer than an inferred one.

Each activated record includes the policy/version, source and target status, evidence-overlap
basis, precedence, presentation effect, limitations, and fingerprints of both unchanged input
results. The complete report records relationship counts, retained IDs, suppressed IDs,
unclassified triggered IDs, unresolved blocker references, the source evidence fingerprint, and
the static policy-contract fingerprint.

Legacy `conflict_observations` remain for backward-compatible rendering, but the R1/R2 message is
derived from the typed relationship rather than evaluated by a second policy.

## Consequences

- Mixed hypotheses become machine-readable and provenance-bearing without choosing a root cause.
- R0 can prevent unsupported advice from being treated as actionable while the original result
  remains inspectable and downloadable.
- Corroboration is deliberately contextual, not a confidence calculation.
- Exact evidence-key overlap is auditable, but it remains shared lineage rather than independence,
  statistical association, or causality.
- New pairs require an ADR/policy addition and tests; they cannot appear through ambient discovery.
- SUMO and TOS remain capability-unavailable because their current contracts do not support the
  relevant core diagnostic relationship set.

## Rejected Alternatives

- **Infer every simultaneously triggered pair:** coincidence does not define a scientific
  relationship.
- **Rank ordinary rules by confidence:** categorical confidence is not a comparable probability.
- **Suppress by removing lower-priority results:** violates the evidence-retention requirement.
- **Use keyword or vector similarity over hypotheses:** non-deterministic semantic inference is not
  an approved diagnostic policy.
- **Treat a shared key as causal corroboration:** shared lineage is not causal evidence.
- **Let an LLM reconcile diagnoses:** conflicts and precedence must remain deterministic and tested.

## Acceptance Evidence

- Unit tests cover all three policies, exact-key gates, precedence, retention, unclassified pairs,
  unresolved blocker references, duplicate rejection, timestamp-normalised fingerprints, and input
  immutability.
- Golden output pins the mixed-fault typed relationship projection.
- CLI/report and Streamlit integration tests prove that typed relationships are exposed while every
  original rule result remains visible.
- Generated schemas and the static policy contract, capability manifests, architecture, usage,
  limitations, and implementation records are reconciled in the same increment.
