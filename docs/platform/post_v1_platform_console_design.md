# Design — Post-v1 Platform Console

**Status: IMPLEMENTED IN PHASE 175. Four additive read-only Streamlit views over already
implemented post-v1 backends. Maximum policy ceiling: `owner_approved_candidate`. The console
performs no acquisition, analysis, approval, execution, admission or external request.**

## 1. Purpose and architecture

Phases 148, 150, 152/165 and 151/167 delivered typed backends for evidence coverage, the
mechanism/policy observatory, incremental analytics quality and bounded decision support. This
slice exposes those contracts beside the existing Inventory, Forecasts and Composer pages without
changing the seven normative navigation groups or any existing route.

One page-independent service is the only adapter. It accepts only the configured workspace and
repository root already supplied to the UI. It may read:

- digest-named `DataQualityReport` files from the single allowlisted
  `manchester/analytics/quality-reports` directory;
- the code-registered and digest-pinned evidence matrix;
- the digest-pinned observatory bundle; and
- the confirmed-capacity Decision-Safety policy/options assembled exclusively from validated
  observatory fields and the reviewed confirmatory source digest.

There is no recursive discovery, arbitrary path parameter, SQL, raw quarantine/archive reader,
network client or write method. Every display string is screened for private paths, credentials,
participant markers and raw identifiers before it reaches Streamlit. Committed source citations
become allowlisted public repository links; local filesystem paths never render.

## 2. Analytics Quality

The Analytics Quality route shows the immutable report feed newest-first, the selected latest
report's accepted/warned/refused/not-observed counts, freshness/completeness/exclusion rules,
support and the bound operational-policy/report digests. Operational severity is never scientific
confidence; readiness is never forecast validity; missing reports or observations are explicit
unavailable states rather than zero.

The page does not run the monitor, publish a report, mutate a checkpoint, activate the 15-minute
OS schedule, delete retained reports or send notifications.

## 3. Evidence Matrix

The Evidence Matrix route uses the backend's deterministic filters and coverage summary. Each row
shows design, standing, admission qualifier, evidence role, trace/actor/capacity, seed support,
endpoint, deviation and exclusion. The view lists exact included row ids and explicit reasons for
every excluded row. `NON_ADMITTED` material remains absent by default and joins only through a
visible separate-view checkbox; it can never satisfy an admitted filter. Proposed rows remain
`evidence: false`. Counts are coverage, never pooled effects or a meta-analysis.

Every selected row retains digest-bound source and producer-citation links. Empty selections say
which filters excluded all rows.

## 4. Mechanism Observatory

The Mechanism Observatory route follows the owner-fixed order exactly:
standing/scope/deviation; primary endpoint; uncertainty; companion metrics; mechanisms;
limitations; citations. It renders the coherence-checked headline, exact five-seed sign-test
wording, flat-deadline and already-failed-task companions, action invariance, policy contracts and
role-labelled mechanism cards. The execution-deviated admitted Sparse-64 record stays visible and
unpooled; the earlier `NON_ADMITTED` return appears only through an explicit appendix toggle.

The renderer performs no scientific formula or endpoint recalculation, causal diagnosis, policy
recommendation or evidence upgrade.

## 5. Decision Safety

The Decision Safety route invokes Ruleset v2 over two compatible confirmed-capacity options. The
comparison contract digest binds the validated observatory bundle, design fingerprint, actor,
trace, capacities and metric. The baseline's paired-delta reference is zero by definition and the
variation value is the backend headline's paired mean latency delta; neither substitutes for a
missing observation. Support is the five held-out seeds and uncertainty is available only because
the digest-pinned headline contains the interval.

The page requests the policy-permitted metric-specific ranking and advisory and displays tied
winners, support, exclusions, notices, evidence backing, cause scope, owner default availability
and reviewable instruction drafts. The required confirmed-capacity notice remains adjacent. Every
draft retains `review_required: true`, `executable: false`, `execution_authority: false` and
`creates_new_evidence: false`. Advice is limited to the predeclared latency metric inside this
measured simulation comparison and is never an overall-service, real-road or automatic-control
decision.

## 6. Navigation, presentation and accessibility

Four unique routes are appended inside the existing Platform group:

1. Analytics Quality — `platform-analytics-quality`;
2. Evidence Matrix — `platform-evidence-matrix`;
3. Mechanism Observatory — `platform-mechanism-observatory`; and
4. Decision Safety — `platform-decision-safety`.

Existing Inventory, Forecasts and What-If routes remain unchanged. Pages use native Streamlit
titles, captions, badges, dataframes, metrics, checkboxes/selectboxes and expanders; standing and
refusal meaning never depends on colour. Tables use compact columns and stretch to responsive
width. Every control has a unique visible label.

## 7. Verification and residuals

AppTests cover all four routes, empty/unavailable analytics, default and explicit non-admitted
matrix views, source/citation links, observatory coherence/deviations, decision ranking/advice and
non-executable drafts, unique labels, adversarial wording, private-path redaction and byte-for-byte
no-write behaviour. Navigation tests prove all scripts, labels and paths are additive and unique.
Backend regressions, Ruff, strict mypy, lock and staged-diff/privacy/no-network checks also pass.

The console is local presentation, not public hosting or participant evaluation. No participant
activity or result exists. Real quality reports still require separately activated aggregate
operations; new evidence or decisions require their existing external authorities.
