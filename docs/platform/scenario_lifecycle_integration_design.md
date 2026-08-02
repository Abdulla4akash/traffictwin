# Design — Scenario lifecycle integration

**Status: IMPLEMENTED IN PHASE 174 as a local-only, artifact-importing integration over the
Phase-149/161 append-only registry. Maximum policy ceiling: `owner_approved_candidate`. This
service records links; it creates no approval, execution, analysis, admission or scientific
evidence. Selecting a real authority root and importing real artifacts remain separate owner
actions.**

## 1. Purpose and boundary

The Phase-142/170 composer emits a strict structured draft and, when explicitly used, a DeepSeek
translation receipt. The Phase-149/161 registry provides the append-only state machine but has no
exact adapter from those artifacts to later campaign artifacts. This slice supplies that adapter
as a local library service.

The service has no `run`, `launch`, `execute`, scheduler, subprocess, network or agent-signature
surface. Its only writes append validated lifecycle records to one explicit JSONL log. Approval,
execution, analysis and admission artifacts must already exist beneath an explicit local authority
root. Importing them does not manufacture the action they describe.

## 2. Exact draft and revision identity

Registration canonicalises the complete `ComposerDraft`, the unsigned campaign-design mapping,
the predeclaration bytes, and the prediction or refusal independently. It records SHA-256 digests
for all four. A fifth digest covers the execution-design projection: every field that must survive
promotion into a `VecCampaignDesign`, excluding only the externally supplied approval.

The scenario id binds the complete composer-draft digest, explicit revision, and prior scenario id.
Revision 1 has no parent. Revision N requires an existing parent at N-1; the parent may have only
one child, and identical draft bytes cannot be presented as a new revision. A changed registered
draft is never edited in place. Exact registration retries are idempotent.

Template drafts retain only their method version. DeepSeek-origin drafts retain `mode`, provider,
model, prompt-template digest, input digest and response digest. Submitted prose, provider response
text, credentials and token-bearing headers are never accepted by the registry model or written to
the log. Predictions remain `evidence: false` in every replay view.

## 3. Authority root and artifact resolution

The service is configured with one JSONL log and one existing authority directory. Import methods
accept a direct child file of that directory, reject symlinks/non-regular files/oversized files,
read bytes once, and store only its SHA-256 in registry payloads. Replay resolves an artifact by
digest across direct regular children; names and private paths never enter the log. Duplicate files
with identical bytes are equivalent; conflicting bytes cannot satisfy the recorded digest.

Artifacts are strict and finite:

- approval: an existing `VecCampaignDesign`; its referenced predeclaration is contained beneath the
  same authority root, exact-hashed, and matched to the approval record;
- execution: an existing `VecCampaignReceipt`, matched to the approved design fingerprint,
  experiment id, embedded approval and unchanged-predeclaration flag;
- deviation: an explicit `ScenarioExecutionDeviation` artifact binding scenario, approved design,
  exact execution receipt, intended/observed digests and a display-required code;
- analysis: an existing `VecCampaignAnalysis`, matched to the approved design, experiment and
  execution status, with the exact source receipt digest added only as a lifecycle link; and
- admission: an existing external `ScenarioAdmissionRecord` carrying explicit human decision
  origin, status, source receipt, optional analysis digest, policy ceiling and limitations. A
  caller-supplied owner-policy validator must independently accept its exact bytes on append and
  replay; schema validity and an asserted identity are never authority.

The service defines strict schemas for deviation and admission artifacts so it can validate an
external record; it exposes no factory or writer for those records. Approval and admission
identities reject agent/LLM/placeholder markers. Artifact prose is privacy-screened while registry
events retain only bounded codes, standing and digests.

## 4. Append and replay rules

Every import requires the caller's expected current head digest. The underlying registry performs
optimistic concurrency and rejects a stale prior. Exact event retries return the original receipt
without appending bytes. Lifecycle transitions remain those of the existing registry.

The registry gains an optional general proof validator. It runs both during append and replay, so
the lifecycle service reopens and strictly validates every external artifact rather than trusting
payload assertions. Approval/admission retain the registry's existing dedicated policy-validator
gates. Removing or changing an authority artifact makes service replay fail closed. Replaying
unchanged log and artifact bytes produces byte-identical typed views and head digests.

The typed view exposes proposed, approved, executed, analysed, admission and closure state plus
separate digest-only links. Deviations remain visible after analysis/admission. Non-admitted state
never appears in the admitted view.

## 5. Refusals and privacy

The integration preserves registry refusals and adds bounded lifecycle refusals for invalid
revision lineage, draft provenance, unsafe/missing/oversized artifacts, invalid artifact schema,
artifact digest mismatch, receipt/analysis/admission binding mismatch and private content.

At minimum, tests exercise changed drafts, duplicate revision children, stale priors, wrong
approval projection, changed predeclaration, mismatched execution receipt/design/approval,
deviation source mismatch, analysis mismatch, admission source/analysis mismatch, agent decision,
private prose, artifact mutation/removal, idempotent retry and deterministic replay. Logs are
screened for absolute paths, credentials, natural-language input and provider response prose.

## 6. Acceptance and residuals

Acceptance requires focused integration/adversarial tests, the existing registry and composer
regressions, Ruff, strict mypy, lock validation and staged-diff/privacy checks. No real approval,
campaign receipt, analysis or admission is imported in this phase; tests use deterministic
synthetic artifacts. Selecting a real authority root and supplying genuine externally authorised
artifacts remain separate owner actions.
