# TrafficTwin Data Platform — v1 plan (30 July 2026)

**Status: PROPOSED scope under an owner directive.** On 30 July the owner decided the data
platform is in scope for this cycle ("non-negotiable"), following the supervisor's meeting-3
encouragement. This plan converts that directive into buildable slices with the same
discipline as every other piece of this project: what exists is mapped, what is built is
scoped, what is *not* built is stated with its reason, and open decisions are named rather
than assumed. Ceilings unchanged: `owner_approved_candidate` at most, nothing
supervisor-signed, and — binding on every slice below — **no LLM output is ever evidence**.

## 1. The vision (supervisor's components, meeting 3)

A data-engineering platform around the digital twin: (1) real-time ingestion in batches or
streams; (2) historical data storage; (3) analytics; (4) prediction models of future system
states; (5) a what-if scenario agent with a user interface ("what if capacity is reduced
3–4×?") executed through the twin; (6) a decision layer; (7) a decision-support dashboard.

## 2. What already exists, mapped honestly

| Component | State in TrafficTwin today |
|---|---|
| Ingestion | **Exists, batch, receipted**: DfT archive acquisition and live BODS sessions with quarantine, manifests, hash verification. Attended and snapshot-based by accepted policy. |
| Historical storage | **Exists**: workspaces, registries, sealed receipts, evidence records. |
| Analytics | **Exists**: the experiments register, STA-01, the analysis modules, the campaign analyses. |
| Prediction | **Missing.** |
| What-if scenarios | **Backend exists**: the campaign instrument + admission chain literally answered "what if capacity drops 3.3×". Missing: a conversational front end that composes scenarios. |
| Decision layer | **Missing** (the platform reports evidence; it does not recommend). |
| Dashboard | **Partially exists**: the Streamlit evidence UI. Missing: platform-level views (data inventory, forecasts, composer). |

## 3. What v1 builds — three slices

### P-1. What-if scenario composer (LLM-assisted)

Natural language → a **draft** scenario: a campaign design (trace, arms, seeds, metrics)
plus a draft predeclaration in the house format. A human reviews and signs; execution then
flows through the **existing, unmodified** campaign instrument and admission chain; the
composer finally renders an evidence-cited summary of the completed analysis.

Guardrails, type-level where possible: the agent **drafts and never approves** (approval
fields refuse agent identities, as the campaign instrument already enforces); no execution
without a signed predeclaration digest; summaries may only cite numbers present in
committed analyses; the composer cannot touch held-out seeds. Model: Claude via the
Anthropic API (the supervisor's explicit suggestion). One worked example ships with the
slice: the 3.3× capacity scenario reproduced end-to-end through the composer.

### P-2. Prediction layer — small and honest

Hourly forecasting over what the platform has actually ingested: bus fleet concurrency and
progression speed by hour (from the four measured sessions: 41 → 1,162 → 1,433 / 1,481 →
1,522 active across a 36× range, hourly speed series 6.290→3.369 m/s), and DfT-profile-based
demand shape. Simple models with declared uncertainty and published support counts —
descriptive forecasting, no causal claims, thin-data hours visibly thin. The report gets a
prediction *architecture* section; the demo proves the socket works.

### P-3. Platform dashboard section

New UI pages, strictly additive under the house UI/a11y/test rules: a **data inventory**
page (every ingested dataset with its receipts and freshness), a **forecast** page (P-2),
and the **what-if composer** page (P-1).

## 4. Described, deliberately not built: streaming ingestion

The evening-peak session measured per-vehicle feed cadence at a stable **66–68 s across a
36× fleet range**. A ≥60 s micro-batch poll therefore already operates at the source's
information rate; a streaming pipeline would idle ~66 of every 67 seconds. The report
documents the streaming architecture and *proves its non-necessity for this source* — a
stronger statement than building it. Continuous unattended acquisition would also change
the accepted owner-attended BODS boundary, which is decision **P-D2** below, default NO.

## 5. Evaluation synergy

P-1 and P-3 are frozen **before** the proposed 11–22 August user-evaluation window so
participants can exercise platform pages (subject to P-D3). That makes the platform an
*evaluated artifact* rather than a described program — the difference the supervisor's own
"we don't care about programs" remark draws.

## 6. Timeline (hard stop: 4 September)

| Window | Work |
|---|---|
| 30 Jul – 6 Aug | P-1 backend + composer page; P-3 inventory page. |
| 6 – 13 Aug | P-2; polish, tests, screenshots; **platform freeze** for the eval. |
| 11 – 22 Aug | User evaluation (ethics-gated) in parallel with report drafting. Defect fixes only. |
| 22 Aug – 4 Sept | Report (the finding as the science core; the platform as its own chapter + architecture vision), video. **No new features.** |

## 7. Open decisions and dependencies

- **P-D1 (owner):** an Anthropic API key and a small spend for P-1. Without it, P-1 ships
  with a deterministic template-based composer and the LLM socket documented.
- **P-D2 (owner):** unattended/continuous BODS acquisition — default NO; boundary stands.
- **P-D3 (owner + ethics):** whether the approved study script covers platform pages; if
  not, the platform is demonstrated to the supervisor instead of evaluated by participants.
- **Coordination:** all new files (platform modules + new UI pages) are disjoint from
  lead-claimed surfaces; the lead may reassign per AGENTS.md work coordination.

## 8. What the platform is *for*, in the dissertation's own terms

The confirmed capacity finding is the platform's existence proof: a counter-intuitive
result, produced through receipted ingestion, admission, pre-registered campaigns and
statistical gates, that survived adversarial re-derivation. v1 adds the missing front half
— scenarios in, forecasts out — so the story the report tells is one system, not a finding
plus an unrelated program.
