# Design — Platform dashboard section (platform P-3)

**Status: IMPLEMENTED in Phase 145 (`45ed8fb`) as three additive Streamlit pages at the
`owner_approved_candidate` ceiling; Phase 170 (`7a661e8`) activated the bounded DeepSeek
scenario-entry panel; Phase 175 added four read-only post-v1 console pages. Nothing existing was
hidden or moved, and label uniqueness and AppTest coverage are enforced. P-D3 says the submitted
ethics materials cover the original pages; any participant use of the enlarged console requires
ethics reconciliation, approval and an explicit owner release. No participant activity,
evaluation result or fixed 11–22 August session is claimed.**

## 1. Page: Data Inventory

One honest table of supported inventory records already present on disk — workspace
receipts, safe quarantine-manifest summaries, registry rows and session records — with
per-dataset source, acquisition mode (attended / scheduled / archive), aggregate
row-or-snapshot count, last-updated, receipt digest, freshness, evidence/admission status,
and any recorded deviation. This is an allowlisted schema reader, not a recursive file
browser. It refuses absolute/private paths, credentials, salts, raw identities and raw
member names at the service boundary; the page never opens raw quarantine bytes.

Freshness reconciles the committed schedule with completion/skip records. A same-day late
window appears from its skip marker; an older missing day is inferred as an absence rather
than presented as a recorded skip. Retention shows prune-*eligible* counts with
"owner-confirmed action pending" because Phase 139 deletes nothing.

Private diagnostic archives (GPU preservation/homecoming) are listed only through their
committed, publication-safe records: digest, date and status string verbatim, including
`NON_ADMITTED` and execution-deviation labels. Their metrics do not enter forecasts,
prediction comparisons or evidence headlines. Read-only; no acquisition, retention,
re-admission or campaign action can be triggered from this page.

## 2. Page: Forecasts

The [bus prediction layer](bus_prediction_design.md) rendered honestly: hourly
concurrency and bus-progression climatology with intervals, support counts on every cell,
`insufficient_support` cells shown exactly as that, exclusions, fit digest, source-date
count and aggregate schema versions in the caption. `FORECAST — NOT EVIDENCE` and
`BUS PROGRESSION — NOT ROAD SPEED` remain visible. The aggregate progression contract is
implemented; when eligible aggregates or support are absent, the page shows the target as
unavailable or `insufficient_support` rather than deriving it from cadence.

Measured aggregates and forecasts use visually and semantically distinct series and
tables; proximity on a chart is not validation. A predeclared held-out verdict, including
a null, appears only after its analysis is admitted and with its own evidence standing.
The DfT demand profile is a separate historical road series, never ground truth for the
bus forecast or evidence of a causal density relationship.

## 3. Page: What-If Composer

The [composer](whatif_composer_design.md) UI: scenario form → prediction card (typed
banner, intervals, unavailable metrics, regime label) or refusal card (the named gap + a
tier-2 *draft* offer) → deterministic download of a design + unsigned predeclaration.
Signing and execution are instructions for a human outside the app, never buttons or
background calls. The page writes no repository/workspace/registry file and launches no
campaign compute. The optional DeepSeek panel is always visibly bounded and reports whether
the process is configured. It sends only privacy-screened owner-entered scenario prose after
explicit per-request consent, validates the returned JSON into the same `ComposerForm`, and
then invokes the unchanged local predictor. The form/template path remains complete without
DeepSeek.

A predictions-vs-measurements table grows only from admitted comparisons, preserving each
side's type and standing. It is empty at launch and visibly so. Execution-deviated
`NON_ADMITTED` bus/GPU results never populate this table.

## 4. Navigation and framing

One new "Platform" group is appended to the existing seven-group navigation; the seven
groups and every current route remain unchanged. Pages are ordered Inventory → Forecasts
→ What-If → Analytics Quality → Evidence Matrix → Mechanism Observatory → Decision Safety
→ Decision Audit → Analyst → Next Investigation → What-If Challenge → Challenge Designer
→ Manchester Gate-D with
unique scripts, URL paths and labels. Each page opens with a one-line scope
banner naming what is and is not claimed — the user-facing articulation of the label
ceilings the project already enforces internally. Producer-derived prediction/measurement
cards carry the mandatory
[producer/SUMO citation bundle](../producer_citation_requirements.md); bus-only pages do
not imply VEC producer involvement.

## 5. Testing and evaluation hooks

AppTest suites per page cover render/empty/error states, persistent banners, unavailable
metrics, `NON_ADMITTED` isolation, citation visibility, label uniqueness, private-path
redaction and the no-write/no-network/no-execution boundary. Navigation tests prove the
existing inventory remains additive. Empty states matter more than usual: inventory gaps,
thin/absent forecasts and an empty honesty table must read as designed honesty rather than
brokenness; first-run guidance follows the UX-02 pattern.

The user-evaluation instrument may gain 2–3 platform tasks (find freshness; read forecast
support; compose a scenario and explain a refusal). They remain a draft owner decision and
must be reconciled with the approved ethics materials before recruitment or data collection.
There are currently no participant results.

## 6. Residual limits

The Phase-175 console now presents analytics quality, evidence coverage, observatory contracts and
Decision-Safety Ruleset v2 output, but it has no automatic default application or execution
control. Editing schedules from the UI, writes against repositories/workspaces/
registries, API acquisition, campaign approval/execution, authentication and public hosting
remain outside this slice. There are no participant results.
