# TrafficTwin Analyst — bounded evidence analyst (V1)

Status: implemented (additive route `analyst`, Platform group). This is a
design response to the recorded project directions — analyst-facing
insight, model-vs-infrastructure decision support, agentic assistance with
a simple interface — not a supervisor-specified architecture.

## 1. Architecture

```
TrafficTwin evidence
        ↓ existing deterministic services
BundleAnalysis (validation, metrics, evidence pack, DiagnosticReport)
ConsequenceLensReport (comparison mode)
        ↓ restated, never recomputed
AnalystEvidencePacket        (src/traffictwin/analyst/models.py, packet.py)
        ↓ deterministic mapping over existing rule outcomes
AnalystClassification        (src/traffictwin/analyst/classify.py)
        ↓ optional, consent-gated, per request
DeepSeek prose rendering     (src/traffictwin/analyst/prose.py)
```

ADR-005 is preserved exactly: deterministic diagnostics come first, the
LLM renders prose last, and no LLM output is a metric, a finding, or
evidence. The packet has no wall-clock field; identical inputs produce an
identical canonical form and fingerprint.

## 2. Deterministic classification rules

The classifier introduces **no thresholds**. It maps existing rule
statuses (`RuleStatus`, ruleset 1.3) onto five signals. Side assignment
restates each rule's own recorded hypothesis: R1 (policy under-offloading)
and R5 (training-to-validation drift) are model/policy-side; R2
(infrastructure bottleneck) and R4 (load imbalance) are
infrastructure-side; R0 gates readiness; R3, R6, R7 and R8 are material
candidates without a side.

1. Report missing, readiness `invalid`, or R0 `triggered` →
   `INSUFFICIENT_EVIDENCE` (the readiness gate refused).
2. Both sides triggered, or an existing cross-rule `CONFLICT` (XR1) →
   `MIXED_SIGNAL`; the statement repeats that the evidence does not choose.
3. Only R2/R4 triggered → `INFRASTRUCTURE_SIDE_SIGNAL`.
4. Only R1/R5 triggered → `MODEL_SIDE_SIGNAL`.
5. Only side-less rules triggered → `INSUFFICIENT_EVIDENCE`: a material
   candidate exists but the evidence cannot distinguish the sides.
6. Nothing triggered and both R1 and R2 evaluated `not_triggered` →
   `NO_MATERIAL_PROBLEM_DETECTED`, with unevaluable checks listed as
   limitations; otherwise `INSUFFICIENT_EVIDENCE`.

Confidence is categorical: the weakest `ConfidenceCategory` among the
contributing triggered rules, `unavailable` otherwise. The suggested next
investigation quotes an existing conditional `Recommendation` from a
contributing rule; the Analyst never authors an action of its own.

## 3. The LLM boundary

The LLM receives exactly one thing: the canonical JSON of a validated
`AnalystProseRequest` (classification, supported facts, limitations,
unavailable keys, evidence standing, digest prefixes). The user's free
text never reaches the LLM. Same mechanism family as the What-If
Composer's DeepSeek socket: `DEEPSEEK_API_KEY` presence only, pinned
endpoint/model, injected transport for tests, per-request visible consent,
20 s timeout, 16 KiB response cap, digests retained instead of the
transcript.

The response must be JSON with exactly `explanation` and
`next_investigation`. Deterministic output guards then refuse prose that:
introduces a numeric token absent from the request
(`LLM_NUMBER_INVENTED`); uses causal/proof/faithfulness/optimality
language via the existing XAI `validate_explanation_language` gate
(`LLM_UNSUPPORTED_CLAIM`); or names a standing the packet does not carry,
e.g. "admitted research" over synthetic evidence
(`LLM_STANDING_PROMOTED`). `AnalystProse` has no classification field, so
the LLM structurally cannot change the signal. Every refusal is typed and
the deterministic presentation stands alone — the page is complete with no
key configured.

## 4. Authority boundaries

The Analyst reads run bundles and restates deterministic outputs. It never
executes or launches anything (test-pinned source scan), never creates
evidence (`creates_new_evidence: Literal[False]`), never recomputes
science (`scientific_recomputation_performed: Literal[False]`), never
claims causality (`causal_claim_supported: Literal[False]`), and never
prepares an execution. What-if work stays on the existing What-If
surfaces via plain navigation.

## 5. Deferred beyond V1

- A "Prepare a What-If" review-card handoff (the challenge→Studio prefill
  contract is the intended vehicle).
- Decision-Safety `assess()` integration for ranked multi-option advice.
- Study-scoped lifecycle (offered/admitted/rejected) facts: no run-bundle
  service exposes them today, so the packet does not fabricate them.
- E2 admitted-research subjects: the packet's standing vocabulary covers
  synthetic/imported bundles; admitted-research subjects need the
  `EvidenceMode` binding first.
