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

### P-1. What-if engine — predict, then verify (owner design decision, 30 July)

Two tiers, so the platform answers fast *and* honestly:

**Tier 1 — the outcome predictor (the model we build).** A small surrogate fitted on the
project's own admitted cells (~154 across 5 traces, capacities 0.1–2.5, two actors), with
the validated ceiling law as its mechanistic backbone rather than a black box —
uncertainty from seed spread, validity domain declared (studied traces, capacity range,
fleet preset), and a **refusal outside the measured envelope** instead of a silent
extrapolation. Every output is typed `prediction`, never evidence. The precedent that
this can extrapolate honestly is already in the register: the ceiling-law prediction test
HELD 27/27 at 7.5× below its fitted range — that experiment *was* a validated what-if.

**Tier 2 — verification by the twin.** One action escalates a prediction to a real
predeclared campaign: the composer drafts the design + predeclaration in house format, a
human signs (the agent **drafts and never approves**; approval fields already refuse
agent identities), the **unmodified** campaign instrument executes, and the completed
analysis lands beside the prediction it tests. Verified predictions become new fit data.

Interface: a structured form is the baseline (works with zero external dependencies). Phase 170
activated bounded DeepSeek JSON form extraction with an owner-funded `DEEPSEEK_API_KEY` and visible
per-request consent. The LLM only fills the strict form; the local predictor calculates every
number. Summaries may only cite numbers present in committed analyses; held-out seeds are
untouchable. One worked example ships: the 3.3× capacity scenario — prediction versus its
already-confirmed answer.

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

## 6. Timeline

**Amendment (1 August, owner):** the owner intends to seek a deadline extension and has
directed that scope not be cut for time. Until an extension is *granted*, the dates
below remain the working plan (an intent is not an approval — the same rule this
project applies to every other pending decision); if granted, the freeze and stop dates
shift with the new deadline while the ordering is preserved. Per-slice design docs now
live in `docs/platform/` (runner, predictor, composer, bus prediction, dashboard, and
the optional Dhaka corridor).

Original schedule (hard stop 4 September):

| Window | Work |
|---|---|
| 30 Jul – 6 Aug | P-1 backend + composer page; P-3 inventory page. |
| 6 – 13 Aug | P-2; polish, tests, screenshots; **platform freeze** for the eval. |
| 11 – 22 Aug | User evaluation (ethics-gated) in parallel with report drafting. Defect fixes only. |
| 22 Aug – 4 Sept | Report (the finding as the science core; the platform as its own chapter + architecture vision), video. **No new features.** |

## 7. Open decisions and dependencies

- **P-D1 (owner, resolved 2 Aug):** form-first remains the zero-dependency baseline. The owner
  supplied a funded DeepSeek runtime key and explicitly activated the NL layer in Phase 170.
  External transfer requires visible consent on each request; key presence alone is inert. The
  returned JSON passes the same strict form and can neither create prediction values nor approve or
  execute a campaign.
- **P-D2 (owner, 30 Jul): tentative YES to unattended BODS.** Implemented as a
  *scheduled session runner* — same accepted rules (≥60 s spacing, one-at-a-time lock, GM
  box, quarantine + receipts, session-scoped identity, aggregate-only outputs), the
  change being only who triggers it. Each scheduled session is recorded like an attended
  one; the boundary change is recorded as this owner decision. Feeds P-2 more hours.
- **P-D3 (owner, 30 Jul): RESOLVED YES** — the submitted ethics script covers platform
  pages, so participants evaluate the platform in the 11–22 Aug window.
- **Coordination:** all new files (platform modules + new UI pages) are disjoint from
  lead-claimed surfaces; the lead may reassign per AGENTS.md work coordination.

## 8. What the platform is *for*, in the dissertation's own terms

The confirmed capacity finding is the platform's existence proof: a counter-intuitive
result, produced through receipted ingestion, admission, pre-registered campaigns and
statistical gates, that survived adversarial re-derivation. v1 adds the missing front half
— scenarios in, forecasts out — so the story the report tells is one system, not a finding
plus an unrelated program.
