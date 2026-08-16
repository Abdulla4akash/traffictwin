# What-If Challenge — controlled study preparation over the recommendation (V1)

Status: implemented (additive route `whatif-challenge`, Platform group,
after Next Investigation). This is a design response to the recorded
project direction — separate the learned Local/V2I/V2V policy,
infrastructure-side placement, RSU resource conditions and scenario
demand as distinct mechanisms — not a supervisor-specified architecture.

**The Challenge Agent does not decide what the evidence means, and it
does not decide what investigation is preferred. Those decisions arrive
from upstream deterministic services. It converts the selected
recommendation into a validated, controlled and reviewable What-If
specification.** The human still decides whether anything is ever run.

## 1. Position in the chain

```
AnalystEvidencePacket → AnalystClassification → RecommendationEvidencePacket
        ↓ plan_challenge()  — deterministic, capability-aware, no values invented
WhatIfChallengeSpec (tracks, held-fixed controls, typed user inputs, readiness)
        ↓ optional consent-gated DeepSeek prose (explains only)
        ↓ build_challenge_prefill()  — pure; validated values only
ChallengeWhatIfDraft → existing challenge→Studio handoff → user reviews → user generates
```

A mismatched recommendation/Analyst pairing is a typed refusal. If the
Analyst is insufficient, the challenge stays insufficient; if the
recommendation is mixed, the challenge preserves two mechanism tracks.

## 2. Challenge taxonomy and deterministic mapping

| Recommendation | Challenge category | Varied dimension | Readiness |
|---|---|---|---|
| INVESTIGATE_MODEL_OR_TRAINING | MODEL_BEHAVIOUR_CHALLENGE | `policy_profile` (six registered `SyntheticPolicyProfile` values; nothing trained or retrained) | NEEDS_USER_INPUT (profile choice) |
| INVESTIGATE_RSU_LOAD_MANAGEMENT | RSU_LOAD_MANAGEMENT_CHALLENGE | none — **NOT_REPRESENTABLE**: no registered What-If dimension varies placement/load management in isolation | NOT_REPRESENTABLE |
| INVESTIGATE_INFRASTRUCTURE_CAPACITY | INFRASTRUCTURE_CAPACITY_CHALLENGE | `rsu_capacity` (service/compute concurrency; queue capacity is not separately exposed and is never conflated) | NEEDS_USER_INPUT (bounded level) |
| INVESTIGATE_SCENARIO_OR_CONTROL | SCENARIO_CONTROL_CHALLENGE | one user-selected scenario dimension from the bounded set (congestion_multiplier, event_demand_multiplier, task_arrival_rate, incident_duration_s, lanes_closed) | NEEDS_USER_INPUT (dimension, then bounded value) |
| MIXED_INVESTIGATION | MIXED_MECHANISM_CHALLENGE | two tracks: capacity (model+scenario fixed) and profile (infrastructure+scenario fixed); never collapsed, never executed together | NEEDS_USER_INPUT |
| NO_ACTIONABLE_PROBLEM_DETECTED | NO_ACTIONABLE_CHALLENGE | none — no study is manufactured | NO_ACTIONABLE_CHALLENGE |
| everything else | INSUFFICIENT_EVIDENCE | none — missing evidence listed | INSUFFICIENT_EVIDENCE |

## 3. Controlled-variation principle and control selection

Each track pins: the variable under investigation, the held-fixed
controls, the expected observables, and the decision question. Held-fixed
controls enumerate every other field of the closed What-If override set
(model, infrastructure, scenario, identity groups) — guaranteeable
because the existing pair generator only changes explicitly overridden
fields — plus the metric contract (same engine, same comparison
contract). Observables are the existing Analyst metric keys per group;
nothing new is measured.

## 4. No invented values; capability awareness

The planner encodes **no numeric literal anywhere** (test-pinned source
scan). A value may enter a challenge only from: the registered
`SyntheticPolicyProfile` choices; the existing `WHATIF_CONTROL_SPEC`
bounds; the registered `DEFAULT_WHATIF_WIDGET_VALUES` defaults (explicit
provenance, shown as the widget default); or explicit user input
validated by `is_value_representable`. Unknown magnitudes become typed
`ChallengeUserInput` entries (`NEEDS_USER_INPUT`), never guesses.
Unrepresentable mechanisms become `NOT_REPRESENTABLE`, never fake
support. Readiness is a five-state enum, not a boolean.

## 5. Studio handoff (implemented, non-executing)

Analyst V1 and Recommendation V1 deferred this handoff for two reasons;
both are resolved here rather than weakened. The magnitude gap is closed
by typed, validated user inputs (no value is invented), and the
challenge-typed contract now carries a genuine challenge: the
`ChallengeWhatIfDraft` identifies the challenge specification
(`whatif-challenge-<fingerprint12>`), its mapped fields cite the resolved
inputs and their provenance, and its warning states that nothing has been
executed. `build_challenge_prefill` is a pure function; the page then
uses the existing pending-draft session contract, Studio's apply-once
review panel appears, and pair generation remains an explicit user act
in Studio. Test-pinned: the handoff writes a valid draft, seeds the
Studio widget, and creates zero bundles.

## 6. LLM boundary, privacy, fail-closed behaviour

Same shared DeepSeek boundary as the first two features (shared
transport, screen, response parser; key presence only; header-only key;
per-request consent; no call on load; 20 s timeout; 16 KiB cap; digests
only). The request is the canonical `ChallengeProseRequest` built by a
function whose only parameter is the spec — user free text has no path
in. The response is exactly `{challenge_explanation, control_explanation,
interpretation_boundary}`; `ChallengeProse` has no category, parameter,
mode, readiness, standing or fingerprint field. Guards refuse: invented
numbers; causal/proof/certainty claims; retraining or expansion commands;
confidence/standing promotion; execution or result claims; readiness
promotion (`LLM_READINESS_PROMOTED`); and any registered profile or
What-If field the challenge did not request (`LLM_CHALLENGE_MUTATED`).
Every refusal falls back to the complete deterministic challenge; the
page is fully functional with no key.

## 7. Research/product separation, limitations, non-goals

No E0–E2d artifact is touched; no E3/P2C/backhaul/free-flow/scaling/
retraining/seed/fleet workload is launched or launchable from this
surface; the Challenge Agent executes no What-If simulation. Limitations:
the load-management challenge stays unrepresentable until a placement
dimension is registered; queue capacity is not separately controllable;
registered profiles are synthetic behaviours, not learned actors; the
mixed challenge requires the user to prepare tracks separately. V1 is not
a chatbot, researcher, experiment runner, simulator controller, trainer,
optimiser, causal engine, parameter-search agent, deployment agent, or
the future Agentic What-If Loop.
