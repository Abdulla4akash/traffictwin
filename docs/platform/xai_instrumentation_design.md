# Design — Fenced XAI instrumentation and decision audit

**Status: IMPLEMENTED IN PHASE 178. The delivered surface is an auditable
synthetic contract fixture, not an explanation of a real actor. It creates no causal claim,
faithfulness validation, optimality result, scientific evidence, execution authority or
admission.**

## 1. Purpose and boundary

Meeting-1 framed explainability as decision-level instrumentation: preserve what the policy saw,
compare its recorded choice with compatible simple baselines, and describe behaviour against load
instead of inferring mechanism from aggregate reward. Existing admitted keyed-action evidence
motivates that instrumentation, but it is not input to this slice and is not re-analysed here.

The implementation supplies schemas, pure adapters, deterministic synthetic fixtures and a
read-only browser. The repository still lacks a compatible producer snapshot hook, model access
for a real actor and a literature-grounded application-validation method. Consequently real actor
attribution is explicitly unavailable. SHAP- and Integrated-Gradients-shaped fixtures prove only
that the artifact contracts, integrity gates and UI can represent future outputs.

## 2. Decision-time snapshot and source support

Each snapshot binds all of the following by value or SHA-256 identity:

- source artifact and individual source-record digest;
- actor id, actor-contract digest and checkpoint digest;
- observation-contract and action-vocabulary digest;
- ordered aggregate feature names/values as visible before that action;
- simulation step and the recorded local/V2I/V2V action; and
- source-support record ids plus `synthetic_fixture: true` for the delivered fixture.

Snapshot features are aggregate synthetic controls such as declared load, queue fraction and
deadline pressure. Vehicle, task, trip, route, participant and credential fields are forbidden.
Missing values, non-finite numbers, duplicate features, changed bindings and private content
refuse. The snapshot is an instrumentation record, not proof that an actor used a feature or that
the feature caused its action.

Source-support records distinguish:

- `project_context`: repository framing that motivates an instrumentation question;
- `method_reference`: literature that defines an artifact shape but does not validate this use;
- `synthetic_fixture`: deterministic bytes used for software verification; and
- `unavailable_requirement`: a concrete missing producer/model/validation input.

Every record carries an exact digest, support scope, limitations and an evidence role. LLM text is
never a source and no source-support record upgrades the synthetic fixture.

## 3. Counterfactual replay and disagreement

A narrow `CounterfactualReplayAdapter` protocol accepts one immutable snapshot and returns one
action without mutating it. Phase 178 implements two synthetic-compatible engineering baselines:

1. `always_local`, which always returns local; and
2. `lyapunov_queue_aware`, a fixed threshold rule over declared load, queue fraction and deadline
   pressure.

Both manifests bind the same observation/action contract, declare `real_policy: false` and make no
optimality claim. The replay result binds adapter, snapshot, input and output digests. There is no
generic plugin import, model loader, checkpoint reader, subprocess, network or arbitrary code
surface.

Policy-disagreement rows compare the recorded synthetic action with one named replay action at the
same snapshot. They expose equality/disagreement, both exact bindings and a descriptive rule label.
They never label one action correct, safer, better or causal. A pure browser filters the immutable
rows by disagreement and action without reading files or changing standing.

## 4. Behavioural fingerprints

Fingerprints report action shares for the recorded synthetic policy and each replay baseline over
three declared-load bins. Every row carries its inclusive/exclusive bin definition, support count,
local/V2I/V2V shares and exact decision-set digest. Counts must reconcile and shares must sum to
one when support is non-zero. Empty bins are unavailable, not zero-filled.

These are descriptive response profiles, not learned feature importance, causal sensitivity,
generalisation, validation or a policy ranking. The synthetic fixture is too small for scientific
inference and remains `evidence: false`.

## 5. Attribution contracts and unavailable states

An attribution artifact binds source/actor/checkpoint/snapshot, method, feature order, baseline,
output and contribution values. Separate metadata records:

- reconstruction/fidelity metric name, value and evaluation scope;
- repeat-stability metric name, value, repeats and perturbation scope;
- method/runtime versions; and
- application-validation standing.

The two delivered artifacts are labelled `shap_shaped_synthetic_fixture` and
`integrated_gradients_shaped_synthetic_fixture`. Their arithmetic reconstruction and repeat
stability checks validate fixture integrity only. Type-level flags keep `real_actor: false`,
`faithfulness_validated: false`, `causal: false`, `scientific_evidence: false` and
`optimality_supported: false`.

Alongside them, real SHAP and Integrated Gradients capability rows are `unavailable` with the exact
missing producer hook, model access and validation-method requirements. Absence never becomes an
all-zero attribution.

## 6. Language gate

All human-readable claims in the bundle and UI pass a deterministic language gate. Without
corresponding explicit support it refuses phrases that assert a causal effect, proof, faithful or
validated explanation, optimal/best/safest action, solved problem or guaranteed outcome. Negated
boundary wording such as “not causal” remains permitted. The gate is not a general truth checker;
it is a minimum protection against overstating this instrument.

## 7. Read-only Decision Audit UI

One unique additive Platform route, `platform-xai-audit`, renders only the built-in synthetic
bundle and two fixed repository source links. It shows:

- exact source, actor, contract and checkpoint bindings;
- snapshot and replay counts;
- filters over policy-disagreement rows;
- per-load-bin behavioural fingerprints;
- attribution-shaped fixture values and integrity metadata;
- real-attribution unavailable requirements; and
- source-support roles, limitations and citations.

Every visible section repeats the synthetic/non-causal/non-faithful boundary. Native Streamlit
tables, metrics, checkboxes, selectboxes and expanders provide responsive and keyboard-compatible
presentation; meaning never depends on colour. There is no file picker, arbitrary path, upload,
write, network, execution, approval or admission action.

## 8. Verification and residuals

Unit tests cover exact snapshot binding, privacy/schema refusals, both replay adapters,
counterfactual integrity, disagreement browsing, fingerprint reconciliation, both attribution
shapes, quality metadata, unavailable requirements, deterministic bundle identity and adversarial
causal/optimal/faithful/validated wording. AppTests cover route uniqueness, exact bindings,
filters, unavailable states, citations, responsive native elements, no-write behaviour and
absence of action surfaces.

Residuals are explicit: a real producer must emit compatible decision snapshots; a real actor and
checkpoint must be accessible through an authorised read-only adapter; the selected attribution
method must be justified for that architecture and validated with predeclared fidelity/stability
tests; and any resulting scientific claim needs separate analysis and admission. None of those
inputs or actions exists merely because Phase 178 implements this contract.
