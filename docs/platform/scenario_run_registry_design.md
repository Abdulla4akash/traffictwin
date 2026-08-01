# Design — Scenario and run registry (post-v1 R-1)

**Status: PROPOSED post-v1 design; owner review pending, unimplemented and not approved for build.
Maximum policy ceiling: `owner_approved_candidate`. The registry records lifecycle and
provenance; it does not approve, schedule, launch, admit or scientifically interpret a
run.**

## 1. Purpose

The [what-if composer](whatif_composer_design.md) can produce a prediction and draft a
verification package, while the existing campaign/admission chain can execute and analyse
authorised work. Meeting 3's what-if vision needs a durable link between those stages so a
user can tell whether a scenario is only a prediction, was approved by the owner, actually
ran, deviated, and was admitted or refused.

## 2. Append-only lifecycle

The registry is an event log. It never overwrites history. Proposed event types are:

| Event | Required proof | Meaning |
|---|---|---|
| `scenario_drafted` | scenario + prediction/draft digest | A draft exists; `evidence: false`, no execution authority |
| `approval_bound` | policy-valid human approval artifact digest | The exact draft was approved; the registry does not create approval |
| `execution_receipted` | instrument receipt and environment/design digests | An execution occurred; not an admission decision |
| `deviation_recorded` | typed deviation record | Intended and observed execution differ |
| `analysis_bound` | analysis artifact digest | An analysis exists with its own role and ceiling |
| `admission_recorded` | authoritative admission/refusal record digest | Standing is copied from the existing admission authority |
| `scenario_closed` | owner-authored reason | No further transition is expected |

Events may arrive later, but their asserted transition must be valid against the prior
digest chain. A new approval for a changed draft creates a new scenario revision, not an
edit to the old approval.

## 3. Core records

`ScenarioRecord` includes:

- scenario id/revision, creation time and creator class;
- structured inputs, units, trace, actor, capacity, fleet preset and seed proposal;
- predictor result/refusal digest and measured compatibility envelope;
- draft predeclaration/design/budget digests;
- `forecast`/`prediction`, `evidence`, `causal` and policy-ceiling flags.

`RunLink` includes exact design fingerprint, approved seed set, execution receipt,
environment/tool versions, output digests, observed resource use and deviations.

`StandingLink` contains only the authoritative admission record digest and copied status.
The registry never stores private approval text, credentials, raw simulator output, raw
BODS data or absolute paths.

## 4. Identity and approval boundary

Only policy-accepted human owner identities may satisfy an approval event. Agent-generated
content, a populated filename, a dashboard click or successful execution is never approval.
The registry validates the approval artifact using the existing governance contract and
binds it to the exact draft digest. It cannot sign on the owner's behalf.

Execution authority is also external. Neither the registry API nor its dashboard view
contains a generic `run` endpoint. A future adapter can add a receipt after an independently
authorised execution, subject to the
[controlled live-twin design](controlled_live_twin_adapter_design.md).

## 5. API

Minimum library surface:

- `register_scenario(draft_bundle) -> ScenarioReceipt | RegistryRefusal`
- `append_event(scenario_id, prior_digest, event) -> EventReceipt | RegistryRefusal`
- `get_timeline(scenario_id) -> ScenarioTimeline`
- `link_execution(receipt_bundle) -> EventReceipt | RegistryRefusal`
- `link_admission(admission_record) -> EventReceipt | RegistryRefusal`

Every write uses optimistic concurrency through `prior_digest`, is idempotent by event
digest and emits an append receipt. Read models are derived and disposable.

## 6. Evidence and separation rules

- A prediction remains `evidence: false` even when its scenario later runs.
- Execution success is not admission, validation or causal confirmation.
- Proposed, approved, executed, analysed and admitted are separate fields.
- Execution deviations remain visible on all later timeline states.
- Non-admitted Sparse-64 work can have a complete timeline but cannot enter the admitted
  VEC evidence view.
- LLM prose may summarise a validated timeline only; it cannot emit lifecycle events.

## 7. Typed refusals

At minimum: `SCENARIO_DIGEST_CONFLICT`, `REVISION_REQUIRED`, `PRIOR_EVENT_MISMATCH`,
`INVALID_TRANSITION`, `AGENT_APPROVAL_FORBIDDEN`, `APPROVAL_DIGEST_MISMATCH`,
`DESIGN_FINGERPRINT_MISMATCH`, `EXECUTION_AUTHORITY_MISSING`,
`ADMISSION_RECORD_UNAUTHORISED`, `PRIVATE_CONTENT_DETECTED` and
`NON_ADMITTED_PROMOTION`.

## 8. Verification and acceptance

State-machine tests cover valid and invalid event orders, concurrent append conflicts,
changed-draft approval mismatch, agent approval refusal, execution without admission,
deviation persistence and non-admitted separation. Replay tests rebuild the same timeline
and digest from the event log. Privacy tests reject paths, secrets and raw payloads.

Acceptance requires an immutable audit trail, exact cross-artifact digest binding, no run
surface, no inferred approval/admission, deterministic replay and a readable distinction
between prediction, execution and evidence standing.

## 9. Owner decisions and stop conditions

The owner must approve lifecycle labels, closure policy, retention, which approval validator
is authoritative and whether the registry is local-only. Stop if implementation would
require moving private signatures into the repository, exposing raw run data, launching
compute, or treating an agent action as approval.
