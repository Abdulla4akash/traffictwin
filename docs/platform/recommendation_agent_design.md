# Next Investigation — deterministic recommendation over the Analyst (V1)

Status: implemented (additive route `next-investigation`, Platform group,
beside Analyst). This is a design response to the recorded project
direction — investigate deterministic infrastructure-side RSU load
management while keeping the trained MAPPO policy unchanged, rather than
attributing every performance problem to the learned model — not a
supervisor-specified architecture.

## 1. Purpose and relationship to Analyst

The Analyst answers *"what does the current deterministic evidence
indicate"* (a bounded signal). This feature answers *"given that, what is
the most defensible next investigation"* (a bounded category). It consumes
the Analyst's outputs; it never reconstructs them. If the Analyst refuses
a subject, this feature fails closed with the same typed refusal. If the
Analyst is insufficient, the recommendation does not become decisive. If
the Analyst is mixed, both tracks stay visible with no winner.

```
AnalystEvidencePacket → AnalystClassification
        ↓ pure deterministic selection (no thresholds)
RecommendationEvidencePacket
        ↓ optional, consent-gated, per request
DeepSeek prose rendering
```

**The LLM explains a deterministic recommendation. It does not author the
recommendation.** ADR-005 is preserved unchanged.

## 2. Recommendation taxonomy and its exact evidence sources

| Category | Deterministic condition | Source rules |
|---|---|---|
| `INVESTIGATE_MODEL_OR_TRAINING` | Analyst `MODEL_SIDE_SIGNAL` | R1, R5 (triggered subset) |
| `INVESTIGATE_RSU_LOAD_MANAGEMENT` | Analyst `INFRASTRUCTURE_SIDE_SIGNAL` with R4 triggered | R4 (+R2 as alternative) |
| `INVESTIGATE_INFRASTRUCTURE_CAPACITY` | Analyst `INFRASTRUCTURE_SIDE_SIGNAL`, R2-only | R2 |
| `INVESTIGATE_SCENARIO_OR_CONTROL` | Analyst `INSUFFICIENT_EVIDENCE` with a side-less triggered candidate and no readiness gate | R3/R6/R7/R8 (triggered subset) |
| `MIXED_INVESTIGATION` | Analyst `MIXED_SIGNAL` | both tracks (R1/R5 + R2/R4) |
| `NO_ACTIONABLE_PROBLEM_DETECTED` | Analyst `NO_MATERIAL_PROBLEM_DETECTED` | none — no intervention fabricated |
| `INSUFFICIENT_EVIDENCE` | everything else (gate, unevaluable, mismatch) | none |

The R4-before-R2 precedence is the Sandra-aligned direction encoded as a
fixed rule: when load imbalance is supported, RSU load management is
investigated before capacity, and the capacity track survives as a
deterministically supported alternative when R2 also triggered. Low
performance alone never maps to a model-side recommendation; a model-side
category requires a triggered model-side rule, and an unevaluable R5 stays
visible in "missing evidence" all the way into the prose request.

Every suggested action quotes an existing conditional `Recommendation`
object emitted by a triggered rule (action, rationale, expected direction,
prerequisite, verification step; `conditional: True` pinned). The selector
introduces **no numeric thresholds** (test-pinned by source scan) and the
full chain — diagnostic rule → rule status → Analyst classification →
existing recommendation → category — is carried in the packet
(`rule_statuses`, `contributing_rule_ids`, `source_recommendations`).

## 3. The recommendation packet

`RecommendationEvidencePacket` is frozen, closed, and wall-clock-free.
Its provenance references carry only rebuild-stable digest prefixes
(analyst packet, bundle validations, consequence lens); identical inputs
give byte-equivalent canonical JSON and an identical fingerprint
(test-pinned). Authority is pinned at type level:
`creates_new_evidence: False`, `execution_authority: False`,
`causal_claim_supported: False`, `whatif_prefill_available: False`.

## 4. LLM boundary, privacy, fail-closed behaviour

Same bounded DeepSeek family as Analyst/Composer, via the now-shared
transport (`analyst/prose.py`: `default_deepseek_transport`,
`parse_deepseek_response_content`, `screen_prose_payload`,
`guard_prose_output`). `DEEPSEEK_API_KEY` presence only; key in the auth
header only; per-request visible consent; no background calls; 20 s
timeout; 16 KiB response cap; digests retained, transcripts never. The
request is the canonical JSON of `RecommendationProseRequest`, built by a
function whose only parameter is the packet — user free text has no path
into the provider request.

The response must be exactly
`{recommendation_explanation, why_not_alternative,
next_investigation_explanation}`. Deterministic guards refuse prose that:
invents a number absent from the request; claims causality (recommendation
marker set plus the existing XAI language gate); commands retraining
(`LLM_UNSUPPORTED_RETRAINING`) or infrastructure expansion
(`LLM_UNSUPPORTED_EXPANSION`); promotes confidence
(`LLM_CONFIDENCE_PROMOTED`) or evidence standing
(`LLM_STANDING_PROMOTED`); claims an execution happened
(`LLM_UNSUPPORTED_EXECUTION_CLAIM`); or names a recommendation the
selector did not choose (`LLM_RECOMMENDATION_MUTATED` — the declared
alternative is permitted). `RecommendationProse` has no category,
confidence, standing, or numeric field, so the deterministic result is
structurally immutable. Every refusal falls back to the complete
deterministic presentation; the page is fully functional with no key.

## 5. "Prepare a What-If": explicitly deferred

Two reasons, both documented in the packet itself
(`whatif_prefill_deferred_reason`): existing deterministic
recommendations name a direction but no parameter magnitude, so any
prefilled override value would be an invented threshold; and the existing
prefill contract is challenge-typed (`ChallengeWhatIfDraft` with
challenge identity fields and challenge-labelled review captions), so a
recommendation handoff would mislabel provenance. The page links to
What-If Studio instead; running anything stays a human act there.

## 6. Non-goals

Not a chatbot, not an autonomous research agent, not an experiment
planner with execution authority, not a simulator controller, not a
retrainer, not an optimiser, not a causal engine, not an autoscaler, not
an evidence admission system, and not a replacement for the deterministic
rules. No E0–E2d artifact is touched; no E3/P2C/free-flow/backhaul/
scaling/retraining/seed/fleet workload is launched or launchable from
this surface.

## 7. Limitations

- `INVESTIGATE_MODEL_OR_TRAINING` via R5 is theoretical on current
  synthetic bundles (no training evidence there); R1 carries the model
  side in practice, and the gap is always disclosed.
- The scenario/control category currently quotes the triggered side-less
  rules' own comparison recommendations; it does not synthesise a study
  design.
- Prose that reformats a packet number (e.g. 0.71 → 71%) is
  conservatively refused and falls back to the deterministic text.
