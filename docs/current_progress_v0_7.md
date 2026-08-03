# TrafficTwin v0.7 Current Progress and Build Plan

**Snapshot date:** 3 August 2026

**Development branch:** `claude/complete-v0.7`; Phase 198 is the current bounded implementation
increment. The immutable release baseline and historical checkpoint tags remain unchanged.

**Snapshot scope:** all previously recorded Manchester/VEC/product work plus the Phase 139–146
data-platform v1, Phase 147–170 post-v1/backend-and-composer suite and Phase 173–180 operational
store, lifecycle, console, local-SUMO, benchmark-package, synthetic-XAI, Manchester Gate-D and
supervisor-communication/literature completion, the Phase-181 repository-wide strict-mypy
reconciliation, the Phase-182 non-releasing Gate-F technical audit and Phase-183 rendered-browser
accessibility engineering QA, Phase-184 Manchester Gate-D decision support, Phase-185 authoritative
DfT/WebTRIS/BODS source re-audit and Phase-186 committed-input/submission-release handoff audit.
Phase 187 added the bounded local usage runbook; Phases 188–189 add owner-authorised process-
lifetime National Highways and BODS refresh without changing source, publication or capability
standing. Phase 190 designs the next durable real-workspace, operational-history, source-health,
map-review and provider-gated measured-traffic programme. Phase 191 implements its first bounded
slice: safe creation of a new empty durable workspace, without creating a real owner target or
activating any source. Phase 192 adds the secret-free port-8502 preflight and fixed foreground
launcher over that durable contract without running a private real-source smoke. Phase 193 adds
the dormant, policy-gated aggregate operational-history contract, UTC compaction and closed safe
store adapter without activating a writer or approving retention.
Phase 194 adds the pure complete accepted-snapshot National Highways transition service without
calling a provider, persisting a real transition, or activating the Changes page.
Phase 195 adds identifier-free BODS operational attempts, explicit trend windows and UTC-day
rollups without activating persistence or a trends page.
Phase 196 adds the read-only two-source Source Health page, Phase 197 adds the exact-artifact
resumable one-row map-match review workflow, and Phase 198 adds strict product-specific provider-
contract intake and safe readiness assessment. No real reviewer decision, provider contract,
credentialed probe or TfGM/NTIS measured-traffic adapter was created.
This tracker distinguishes implemented libraries/pages and communication artifacts from designs,
activated schedulers, deployed services, completed studies and accepted scientific evidence.

**Formal release baseline:** immutable `v0.6.0` at
`1c50a25246426128ac6e8530240eff362d16be02`

## 1. Purpose and authority

This is the working progress and sequencing document for TrafficTwin v0.7. Use it with:

1. [TrafficTwin design v0.7](traffictwin-design-v0_7.md), which defines the authoritative product,
   scientific boundaries, capabilities, gates, and completion rules; and
2. [Implementation status](implementation-status.md), which records formal capability truth and
   accepted evidence.

This document answers four practical questions:

- what already works;
- what is only a foundation or bounded slice;
- what can be built next without inventing external evidence; and
- what is blocked by a source, licence, research, governance, or human decision.

It does not independently mark a `MAN-*`, `UX-*`, or `REL-01` capability implemented. If this
summary conflicts with the design or implementation-status record, those documents take
precedence.

## 2. Status vocabulary

| Label | Meaning |
|---|---|
| `accepted` | The complete design acceptance boundary has passed and formal project records agree. |
| `working_bounded` | Tested and usable for an explicitly limited local/private/source-specific workflow, but the complete capability gate has not passed. |
| `foundation_only` | Important contracts or deterministic libraries exist, but the capability's main end-to-end outcome does not yet exist. |
| `unavailable` | TrafficTwin lacks the evidence, authority, source, or accepted prerequisite required to offer the function honestly. |
| `out_of_scope` | The design explicitly excludes the function from v0.7. |

Under the strict v0.7 completion rule, all 15 v0.7 capability rows remain formally `planned`.
This does not mean the branch is empty: substantial bounded source, live-operations, and UI
workflows are already working.

At `v0.7.0-alpha.4` (`4e95a5d`), the Guided Demo is an action-aware cross-page workflow
candidate. It opens the first real task, keeps persistent progress and evidence boundaries
visible, advances from typed successful actions where available, uses one explicit
acknowledgement for review-only stages, and records skipped stages separately. The Phase 2B
Tier 1 presentation harvest (seven pages plus its adversarial test file) is now lead-reviewed and
integrated on `claude/complete-v0.7`. Neither increment by itself accepts any `UX-*` row.

## 3. Current verified baseline

At the latest proportional verification points:

- Phase 161's locked full suite passed 3,944 tests with two expected environment-gated skips;
- the repaired post-v1 suite passed 113 tests, repository Ruff/format, strict mypy across 859
  source files, lock validation, generated-reference drift, package and privacy gates;
- Phase 169's eight-slice platform regression passed 143 tests;
- Phase 170 passed 43 focused and 129 adjacent predictor/composer/registry/safety/live-twin/
  benchmark/UI tests, plus Ruff, formatting, strict mypy, lock and secret checks; and
- the Phase-171 status audit reran 250 meeting/platform/research-workflow tests successfully; and
- Phase 173 passed 22 focused activation tests and 98 aggregate-store/bus-adapter regression tests,
  plus Ruff, formatting, strict mypy, lock, exact-source-byte and path-leakage gates; and
- Phase 174 passed 11 focused lifecycle integration tests and a 157-test adjacent post-v1
  regression, plus Ruff, formatting, strict mypy, lock and privacy/diff gates; and
- Phase 175 passed 63 focused/adjacent console and navigation AppTests and a 116-test console plus
  backend-contract regression, plus Ruff, formatting, strict mypy, lock and privacy/no-action
  gates; and
- Phase 176 passed 18 focused local-transport tests and the 63-test local transport/controller/
  controlled-runner regression, including a real bounded SUMO 1.27.1 loopback smoke; Ruff,
  formatting, strict mypy, lock, fixed-argv/privacy/no-external-client and cleanup gates passed.
- Phase 177 passed 22 focused benchmark-execution tests and the 108-test protocol/execution/
  adjacent job-pack regression; Ruff, formatting, strict mypy, lock, deterministic-export,
  privacy/no-training/no-cloud and diff gates passed.
- Phase 178 passed 27 focused backend tests and the 88-test backend/UI/navigation/adjacent-console
  regression; Ruff, formatting, strict mypy, lock, privacy/language/no-model/no-action and diff
  gates passed.
- Phase 179 passed 15 focused Gate-D integration tests, the 66-test focused/UI/navigation suite and
  the 387-test mapping/review/profile/calibration/comparison/lineage/Manchester-UI regression;
  Ruff, formatting, strict mypy, lock, exact-source/privacy/no-write/no-execution and diff gates
  passed.
- Phase 180 passed five focused artifact/bibliography tests and the full 4,128-test repository
  regression with two expected environment-gated skips. Repository Ruff/format, focused strict
  mypy, lock, 100-source/citation coverage, local-link/privacy and
  four-slide/four-note/four-page structure, full-size visual inspection, overflow and diff gates
  passed.
- Phase 181 removed the eight stale test-only strict-mypy errors without changing production code
  or behavioral assertions. The three repaired modules pass 60 tests, the full repository suite
  passes 4,128 tests with two expected environment-gated skips, and repository-wide strict mypy
  passes across all 890 configured source files.
- Phase 182 passed 58 focused release/migration tests, standalone smoke, lock validation,
  byte-identical isolated regeneration of all 69 reference artifacts, clean source/wheel build and
  Python 3.12 installation, plus a fresh immutable-v0.6.0/v0.7 coexistence check. It created no
  release, tag, deployment, real migration or Gate-F acceptance.
- Phase 183 inspected Home, Manchester Operations, Manchester Gate-D, Guided Demo, Decision Safety
  and Decision Audit at desktop and narrow viewports. It repaired the shared duplicate-`h1` shell
  defect and recorded bounded contrast and 12-stop forward-keyboard observations. The automated
  accessibility regression and adjacent route/navigation suite passed all 371 tests; focused
  Ruff format/check and strict mypy pass. The manual checklist remains
  unticked and genuine zoom, screen-reader and complete human keyboard/focus acceptance remain.
- Phase 184 bound 15 committed Manchester sources into a decision-ready review/calibration/demand
  packet. Its seven-file adjacent Manchester suite passed all 198 tests; Ruff and repository-wide
  strict mypy across 891 configured files pass. It made no human row decision, scientific choice,
  protocol amendment, demand/SUMO run, contract registration, baseline or comparison.
- Phase 185 re-audited seven official DfT, National Highways, and BODS sources. DfT/WebTRIS clock
  bases remain undocumented; BODS general reuse/publication and API registration are now
  documented, while retention duration, multi-day identifier persistence, project privacy and
  public row-level output remain open. Its 19-file source-contract/acquisition/freshness/retention/
  time-basis regression passed all 412 tests; Ruff and repository-wide strict mypy across 892
  configured files pass. No provider contact, account, credential, operational fetch, capability
  acceptance or release authority was created.
- Phase 186 bound nine committed submission, decision-support, source-audit and release-engineering
  artifacts by exact digest; reconfirmed the 8,396-word/100-reference manuscript and four-slide
  sourced deck; found no duplicate long prose; and reconciled the already-resolved network and
  producer-attestation policy in the decision pack. Its six-file submission/release regression
  passed all 68 tests; Ruff, lock validation and repository-wide strict mypy across 893 configured
  files pass. It inspected no ignored/private workspace and changed no manuscript result,
  package/CITATION version, tag, approval, evidence or capability.
- Phase 188 passed 349 focused/adjacent National Highways, Manchester UI and accessibility tests,
  then the full 4,154-test repository suite with the two expected environment-gated skips. Ruff,
  lock validation and repository-wide strict mypy across 896 configured files pass. A local
  real-workspace smoke recorded an automatic receipt and the 30-second watcher rerendered all three
  layers from stale to near-live without the manual button; no credential or private source row was
  committed.
- Phase 189 added a process-local BODS worker with a 60-second default, explicit request scope,
  transient key, the existing shared lock/rate boundary, automatic receipts, source-time stale
  truth, manual fallback, and 30-second local UI change detection. The focused BODS/UI regression
  passed 93 tests and the full repository suite passed 4,160 with two expected skips; Ruff, lock,
  schema, link, diff and strict-mypy checks across 898 files passed. Eleven consecutive private
  real-source cycles completed without adding a failure, and the rendered page advanced without a
  manual click. This creates no official provider quota, automatic deletion, complete Bee/privacy
  approval, city-road coverage, public hosting, capability acceptance or release authority.
- Phase 190 added design only: canonical section 27 now defines eight separate durable
  real-evidence slices with typed boundaries, failure/privacy/time/licence rules, acceptance tests
  and sequencing. Twenty focused release/handoff integrity tests, lock validation, relative-link
  and structure checks, added-line secret/private-path screening and diff checks pass. No private
  workspace, source request, implementation, reviewer decision, provider contract, capability
  acceptance or release was created.
- Phase 191 implements the bounded `NEXT-01` durable-workspace workflow. The 74-test release,
  migration, reconciliation, productisation and CLI regression passes, including atomic
  no-overwrite publication, interruption recovery, owner-only permissions, empty-registry backup/
  restore, exact retry and path-free output adversarial checks. Ruff, format, focused strict mypy,
  lock, generated-reference JSON, changed-document link, privacy/path and diff checks pass. Tests
  created only temporary empty workspaces; no owner-selected real target, source, historical
  store, capability acceptance or release was created.
- Phase 192 implements the bounded `NEXT-02` preflight and local foreground profile. Its 118-test
  durable/release/worker/control/scene/app/CLI regression passes, including missing/invalid source
  configuration, busy locks, corrupt controls, unsafe scenes, port conflict, independent worker
  failure, exact confirmation, dry run, fixed argv and child-only environment checks. Ruff,
  format, focused strict mypy, generated-reference, lock, link, privacy/path and diff checks pass.
  No owner workspace, credential, source request, real server or public process was used.

The previously recorded 35-route desktop/mobile light/dark browser matrix produced 140
screenshots with zero actionable semantic findings.

The browser result is automated regression evidence. It is not a WCAG, screen-reader, participant,
or research-usability acceptance claim.

### 3.1 Data-platform overlay

| Group | Practical state | What is built | What remains |
|---|---|---|---|
| v1 ingestion/prediction/dashboard | `working_bounded` | Scheduled BODS runner, VEC predictor, bus forecast backend, composer/DeepSeek panel, seven Platform pages and Dhaka network feasibility | Scheduler activation, enough forecast dates, participant evaluation and any Dhaka observation/simulation |
| Store/analytics/evidence/registry | `working_bounded` | Local aggregate SQLite store plus preview-confirmed atomic activation/backup/restore CLI, deterministic analytics feed and evidence-matrix console, append-only registry and exact artifact-revalidating composer lifecycle service | Select real store/lifecycle authority roots and genuine authority/licence artifacts; lifecycle UI remains absent |
| Observatory/decision safety | `working_bounded` | Source-pinned mechanism cards and Ruleset v2 bounded assessments with read-only console presentation | Still no execution authority, overall-service recommendation or evidence creation |
| Controlled live twin | `working_bounded` | Maximum-coverage contracts/fake plus a fixed-argv loopback-only local SUMO/TraCI transport over the pinned synthetic square | BODS/public/cloud/operator transports, deployment inputs, generic scenarios and any scientific/production use |
| Capacity benchmark | `working_bounded` | Frozen protocol plus contract-only manifests/adapters, deterministic unsigned 240-cell/2,400-job and resource-plan exports, 21-job synthetic worker, receipts/resume/checkpoint/analysis-freeze gates | Signed final protocol, real actor/runtime/checkpoint/domain bindings and separately authorised training/evaluation |
| XAI decision audit | `working_bounded` | Synthetic exact-binding snapshots, two pure replay baselines, disagreement browser, behavioural fingerprints, attribution-shaped integrity fixtures and read-only UI | Producer snapshot hook, authorised real actor/checkpoint access, literature-grounded application validation and any separately admitted real attribution result |
| Manchester Gate-D integration | `foundation_only` | Five exact committed records feed typed mapping sensitivity/reconciliation, pending review, temporal profile, calibration/baseline readiness, comparison-contract and lineage views; a 15-source decision pack now makes review, calibration and coverage-targeted demand choices explicit | 174 named-person review decisions, exact-input reconciliation, approved calibration/uncertainty and demand designs, viable demand and runs, contract registration, human baseline decision and real comparison |
| Supervisor communication and literature audit | `working_bounded` | Four-slide editable/verified deck with per-slide sources; exact 100-source matrix, BibTeX catalogue, manuscript bibliography and complete body citation coverage | Supervisor interpretation/decision, private-source format/year, final bibliography breadth, University style/template export, ethics and publication decisions remain human |

These platform labels do not accept any separate `MAN-*`, `UX-*` or `REL-01` capability.

## 4. Gate progress and planning estimates

Estimates below are focused engineering time, not guaranteed calendar deadlines. They assume two
agents can use disjoint files, the integrating agent reviews every merge, and required research or
licence decisions are supplied promptly. External-provider and supervisor decisions have no
reliable engineering-time estimate.

| Gate | Purpose | Current position | Main remaining work | Estimated focused engineering time |
|---|---|---|---|---|
| Gate A | Freeze source, legal, schema, time, security, dependency, map, and publication decisions | `accepted` | Re-audit only when a provider or source contract changes | None for the frozen sources |
| Gate B | Immutable source acquisition, parsing, replay, projection, freshness, and isolation | `working_bounded` | Complete broad/source-wide reconciliation; close time, rate-limit, retention, membership, licence, and publication blockers | 3–6 working days, excluding external decisions |
| Gate C | Manchester Operations, grouped navigation, home page, responsive visual system, and accessibility | `working_bounded` | Final cross-page state and cutover evidence; manual keyboard, screen-reader, contrast, zoom, and participant review where required | 2–4 working days, plus human evaluation time |
| Gate D | Observation-to-SUMO mapping, calibration, accepted baseline, and observed-versus-simulated comparison | `foundation_only` | Integrated: the reviewed Greater Manchester network, owner-policy v1.1 candidate generation, exact 305-site reconciliation, sealed per-row review ledger, real DfT temporal-profile candidate, calibration/comparison engines, owner-candidate comparison contract, versioned baseline-candidate workflow, read-only complete-lineage UI, and both measured sensitivity populations. Remaining: 174 named-person decisions, an explicit treatment for nine unmatched sites, scientific calibration/uncertainty approval, replacement of the gridlocking demand, compatible runs, separate lead registration of production contracts, a human baseline decision, and a real comparison. | 7–14 working days after the remaining human/scientific decisions |
| Gate E | Accepted Manchester SUMO output through FCD/network and VEC-06–VEC-12 | `foundation_only` | Run the accepted baseline, validate one-second FCD/network, execute the gated VEC chain, and assemble research/evaluation evidence | 4–8 working days after Gate D |
| Gate F | v0.6/v0.7 isolation, migration, rollback, packaging, documentation, CI, and immutable release | `foundation_only` | Migration/backup/interruption/rollback and side-by-side clean-checkout tests; reconcile manifests and create the final release | 3–6 working days after claimed capabilities settle |

The critical dependency path is Gate D → Gate E → Gate F. Gate-B reconciliation, Gate-C manual
acceptance, and parts of Gate-F migration tooling can progress in parallel.

## 5. Capability-by-capability progress

| Capability | Practical state | Built now | Why it is not fully accepted |
|---|---|---|---|
| `MAN-01` Manchester snapshot/source contract | `working_bounded` | Gate A, bounded transport, secret redaction, pre-parse quarantine, immutable hashing, validation, atomic promotion, offline replay, catalogues, and real narrow source probes | Complete Gate-B source reconciliation plus source-wide licence, retention, publication, and provider-contract acceptance remain open |
| `MAN-02` DfT historical road counts | `working_bounded` | Real count-point/raw-count/AADF acquisition, exact parsing, replay, catalogue, survey filters/charts, and Manchester reference scene | Full Manchester bulk acceptance, raw-count hour timezone, provider rate-limit/SLA, calibration-profile approval, and final UI acceptance remain |
| `MAN-03` WebTRIS strategic-road evidence | `working_bounded` | Real site/day/quality acquisition, exact historical replay, missing-value preservation, charts, and selected-site scene | Provider-wide/multi-site acceptance and source timezone remain open; real probing confirmed that WebTRIS must be refused as near-live |
| `MAN-04` TfGM signal reference layer | `working_bounded` | Real 2,529-row archive, exact parser, coordinate conversion, attribution, spatial admission, and static map layer | Final common Gate-B/licence/release reconciliation remains; an overwritten future archive must be re-audited |
| `MAN-05` BODS live transit | `working_bounded` | Real authenticated acquisition, safe SIRI-VM parsing, live/stale classification, local map, outage fallback, five verified Bee operator identifiers, rate limiting, aggregate history, precautionary cleanup, and documented general BODS reuse/publication plus API-registration terms | Complete Bee service/fleet scope, `BNVB`, identifier privacy/retention, project public-output treatment, and complete provider acceptance remain unresolved |
| `MAN-06` Randy Manchester bridge | `working_bounded` | Permission-safe local panel over accepted sanitised VEC-11 evidence, aggregates, citations, fingerprints, and limitations | Full workflow acceptance remains; source limits deliberately prohibit raw identity, geographic/live relabelling, and public hosting |
| `MAN-07` projection/freshness service | `working_bounded` | UTC time-basis contract, source truth states, BODS and National Highways freshness, spatial admission, exclusions, and ONS display boundaries | Real canonical time projection for DfT/WebTRIS is blocked by unresolved source-time semantics; broad real-source projection acceptance remains |
| `MAN-08` Manchester Operations | `working_bounded` | Historical/latest/live-vehicle modes, source-separated maps, BODS and National Highways refreshes, TfGM/DfT/WebTRIS views, filters, source cards, stale fallback, Randy panel, and metadata-only download | Broad/multi-site acceptance, upstream capability acceptance, public-export decisions, and manual accessibility/participant acceptance remain |
| `MAN-09` observation-to-SUMO baseline | `foundation_only` | Reviewed Greater Manchester network; owner-policy v1.1 candidates over all 305 real sites (131 owner-policy candidates, 165 ambiguous, nine no-candidate); sealed per-row human-review ledger; real 39,072-cell DfT temporal-profile candidate; deterministic calibration evaluator; Phase-179 calibration dependency and versioned baseline-candidate workflows | All 174 queued rows remain undecided by a person; the nine unmatched sites have no accepted treatment; calibration/uncertainty is unsigned; the existing demand gridlocks; no compatible candidate run, admitted calibration or accepted/refused baseline exists |
| `MAN-10` observed-versus-simulated comparison | `foundation_only` | Deterministic pairing/exclusion/coverage/lineage/MAE/RMSE engine plus the exact owner-candidate contract (`b1d31a1b…`) and Phase-179 read-only contract/readiness UI | The production registry is empty, GEH is outside the frozen contract, compatible simulated intervals do not exist and no real comparison was executed |
| `MAN-11` Manchester SUMO-to-VEC workflow | `foundation_only` | Strict path-free research lineage plus Phase-179 complete Gate-D source→mapping→review→profile→calibration→baseline→comparison readiness lineage | No accepted baseline, controlled Manchester SUMO receipt, matching one-second FCD/network pair, complete Manchester VEC chain, or research/usability evaluation exists |
| `UX-01` task-oriented navigation | `working_bounded` | All 34 v0.6 pages mapped into five groups with stable direct routes, Material icons, normal v0.7 routing, complete legacy fallback, a candidate action-aware Guided Demo with persistent progress and automatic next-task routing, and automated cross-page shared-state evidence for both routers; minimum/locked Streamlit, wheel, AppTest, and browser checks pass | Final cutover decision, package-version reconciliation, and manual accessibility acceptance remain |
| `UX-02` map-led home/workflow | `working_bounded` | Focused research home, primary actions, meaningful local KPIs, and latest accepted Manchester context | Final release and human usability/participant acceptance remain |
| `UX-03` responsive/accessibility system | `working_bounded` | Native theme/components, presentation mapping, deprecated-width removal, responsive layouts, the integrated Tier 1 page-presentation harvest (SUMO/bundle/TOS import, comparison, About, experiment tracking, and the shared truncated-fingerprint caption with Advanced identity), the Tier 2 harvest (Statistical Study tabs and per-seed chart, VEC Workbench staged workflow, Temporal Metrics reconciliation, Threshold Sensitivity response panels), the Tier 3 harvest (Diagnostics & Evidence grouped availability, Provenance Explorer structured dependency views, Operations View replay/active-filter/window panels, Triviality descriptive chart, Participant Evaluation readiness checklist, Manifest Inference preview/confirm separation), the Tier 4 analysis-evidence harvest (Energy coverage-first family dashboard and joule-comparison chart, Fairness eligible-group coverage and Exclusions & Limitations, Infrastructure canonical-vs-source provenance/window and native per-RSU charts, Journey-Time cohort-completion and distribution chart, Spatial & RSU coordinate-frame and target/coordinate reconciliation), the Tier 5 research-workflow harvest (Scenario Builder sequential authored-vs-generated flow, Scenario Mutations three-stage before/after, Experiment Planner define/validate/inspect/register run matrix, Parameter Sweep choose/define/preview/export with a preview chart, Reports peer-view tabs), and 140-view visual regression | Manual keyboard, screen-reader, contrast, zoom, and participant checks remain; automation cannot claim WCAG conformance |
| `REL-01` v0.6/v0.7 isolation | `foundation_only` | Separate v0.7 workspace/registry/cache namespaces, byte-exact read-only v0.6 registry copying, the ADR-058 operator attestation, an attested same-schema activation workflow with durable backup, interruption quarantine, and receipt-gated rollback, bounded CLI commands for the whole chain, a demo-launcher `--port` option for side-by-side operation, a passing scripted v0.6.0 clean-checkout coexistence check, and a workspace setup/diagnostics guide | Package/release version alignment, cross-schema migration if schemas diverge, and final release/tag reconciliation remain |

## 6. Major work ready to build now

The following tasks have useful implementation work that can begin without pretending an
unavailable live source exists. Real acceptance may still depend on the decisions listed in the
next section.

### 6.1 Gate D: complete the research core

1. Owner-policy v1.1 candidate generation is complete and integrated over the reviewed network;
   have a named person decide all 174 queued rows and record a treatment for nine unmatched sites.
2. The sealed per-row ledger and read-only Phase-179 review status are built; no UI or agent may
   stand in for the named reviewer.
3. The real DfT temporal-profile candidate and its exact local-clock/partition accounting are
   integrated; provider time semantics and production use remain external.
4. The calibration dependency workflow is built; approve the objective, parameter grid,
   uncertainty/held-out design, replace the gridlocking demand and execute compatible candidates.
5. The versioned baseline-candidate workflow is built in `unavailable_missing_inputs` state;
   complete its ordered evidence and obtain an explicit human accept-or-refuse decision.
6. The exact owner-candidate comparison contract and read-only UI are integrated; separately
   review/register it and run only after compatible real observed/simulated inputs exist.

### 6.2 Gate E: execute the research chain

1. Run an accepted baseline through controlled SUMO.
2. Verify the matching one-second FCD and network pair.
3. Enter VEC-06 through VEC-12 without broadening their existing scientific claims.
4. Materialise the existing `MAN-11` lineage graph from real accepted artifacts.
5. Assemble the permission-aware research pack and predeclared RQ12–RQ16 evaluation evidence.

### 6.3 Gate B/C/F closure work

1. Finish broad bounded-source reconciliation and formal acceptance records for the source slices
   whose evidence is sufficient.
2. Complete cross-page state and manual accessibility checks.
3. Migration preview, backup, transactional copy, interruption quarantine, refusal, activation,
   and rollback: done for ADR-058-attested same-schema sources; side-by-side clean-checkout
   acceptance remains.
4. Run v0.6 and v0.7 from separate clean checkouts, ports, and workspaces: automated by
   `scripts/side_by_side_check.py` with a passing 24 July 2026 evidence record; formal Gate-F
   acceptance still happens at release reconciliation.
5. Reconcile CLI, generated schemas/references, capability manifest, documentation, package
   version, CI, and final immutable tag.

### 6.4 Post-v1 integration work that is buildable without new external evidence

1. ~~Add read-only dashboard pages/services for the analytics quality feed, experiment evidence
   matrix, mechanism observatory and Decision-Safety assessments.~~ Completed in Phase 175.
2. ~~Implement and test a concrete local-SUMO live-twin transport against the existing safe public
   fixture, retaining engineering-only receipts and launching no scientific campaign.~~ Completed
   in Phase 176 over the pinned repository-owned synthetic square.
3. ~~Extend benchmark tooling with actor/runtime plugin manifests, local job-pack export, receipt
   ingestion and deterministic synthetic workers.~~ Completed in Phase 177 as contract-only and
   engineering-only infrastructure; real training remains separately authorised after a signed
   protocol and concrete resources exist.
4. ~~Build the fenced XAI instrumentation contract and synthetic decision-audit/disagreement UI.~~
   Completed in Phase 178; real attribution remains unavailable until a compatible producer
   snapshot hook, authorised model access and validation method exist.
5. ~~Integrate the safe Manchester Gate-D candidate records, baseline/comparison workflows and
   read-only lineage UI.~~ Completed in Phase 179 without human review, registration, execution,
   baseline or real comparison.
6. ~~Produce the requested 3–4-slide supervisor deck and expand/verify the dissertation
   bibliography.~~ Completed in Phase 180; neither artifact creates supervisor approval or
   research evidence.

Completed in Phase 173: the owner-workspace aggregate SQLite activation command now supplies
mutation-free preview, exact confirmation, closed safe-artifact adapters, atomic/idempotent
publication, orphan/corruption reporting, and complete-backup isolated restore verification. No
real workspace or artifact was activated.

Completed in Phase 174: canonical composer drafts and explicit revision lineage now enter the
append-only registry through a local service; digest-only DeepSeek provenance and strict external
approval/execution/deviation/analysis/admission adapters are revalidated on append and replay.
Admission also requires a caller-supplied owner-policy validator; schema validity alone refuses.
There is no run, signature, approval creation or automatic admission surface, and no real authority
artifact was imported.

Completed in Phase 175: four additive unique Platform routes now present the immutable analytics
quality feed, filtered evidence matrix, coherence-checked observatory and Ruleset v2 assessment.
The pages retain roles, exclusions, uncertainty, deviations, citation digests and explicit
non-admitted separation; the instruction draft is review-only and non-executable. The service has
no recursive browser, write, network or launch surface, and no real report, authority, participant
result or new evidence was created.

Completed in Phase 176: the existing single-owner live-twin controller can now inject a real local
SUMO 1.27.x process with exact runtime/preset/network/policy binding, private staging, fixed
shell-free argv, loopback TraCI, aggregate-only snapshots, bounded command mappings and complete
crash/timeout/protocol/cleanup recovery. A local synthetic smoke advanced 0→5 seconds and produced
an engineering-only terminal receipt. No BODS/public/cloud/operator connection, generic scenario,
scientific campaign, evidence, production claim or road effect occurred.

Completed in Phase 177: the exact Phase-169 factorial now has deterministic contract-only actor,
runtime and adapter manifests; an unsigned 2,400-job export; estimate-only provider-neutral
resource records; and a tiny 21-job engineering worker with path-free receipts, bounded retry/
resume, checkpoint inventory and synthetic analysis-input freezing. Planned returns are gated by
an exact separately supplied owner signature plus seed, budget, endpoint and checkpoint identity.
No real actor, training, cloud request, spend, benchmark result, evidence or admission occurred.

Completed in Phase 178: a built-in exact-binding Decision Audit fixture now exercises aggregate
decision snapshots, two pure engineering-baseline replays, policy-disagreement filtering,
action-share fingerprints by declared load, attribution-shaped integrity metadata and explicit
real-method unavailable states. The read-only Platform page exposes full synthetic source/actor/
checkpoint lineage and rejects unsupported causal/faithful/validated/optimal wording. No real
model, checkpoint, attribution, evidence, execution or admission occurred.

Completed in Phase 179: five exact committed Manchester records now feed one typed, read-only
Gate-D packet. It preserves both measured radius-sensitivity populations, the exact 305-site v1.1
reconciliation, an empty 174-row human-review ledger, the 39,072-cell real DfT profile candidate,
calibration dependencies, an unavailable versioned baseline workflow, the unregistered
`b1d31a1b…` comparison contract and complete gaps-first lineage. No private artifact, person,
scientific choice, SUMO run, baseline, metric, evidence or acceptance was created.

Completed in Phase 180: a four-slide editable PowerPoint and visually verified four-page PDF now
cover the digital-twin loop, bounded what-if differentiator, traffic/VEC lenses, exact signed
capacity result, portfolio/benchmark direction, status and residual decisions. All slides carry
`[Sources]` notes and a companion claim/source-class audit. The literature matrix and BibTeX source
contain exactly 100 distinct candidates—88 DOI-bearing, nine official/standards and three private
producer records—and the manuscript now has 100 numbered references with complete body citation
coverage. Literature context, project measurements and LLM drafting remain separate. No
supervisor, ethics, publication, production or real-road approval or new research evidence was
created.

### 6.5 Phase-190 durable real-evidence programme design

The canonical [v0.7 design](traffictwin-design-v0_7.md#27-post-phase-189-durable-real-evidence-programme)
now defines eight separate next slices. None is implemented merely because its design exists:

1. preview-confirmed, new-only creation of a durable v0.7 workspace outside the repository;
2. a secret-free preflight and foreground port-8502 run profile over the existing BODS and
   National Highways workers, leaving the synthetic demo on 8501;
3. a hash-chained aggregate attempt journal and immutable UTC-day partitions beyond the current
   24-hour hot control histories, gated by an owner-approved retention/publication policy;
4. complete National Highways first-seen/changed/unchanged/no-longer-listed/expired/reappeared
   tracking between compatible complete accepted snapshots;
5. identifier-free BODS live/stale, verified-operator coverage, source-age, cadence, refusal and
   failure trends;
6. a read-only Source Health route exposing configuration presence, worker state, freshness,
   history/integrity and blockers without values, paths, identifiers or network actions;
7. a registered-artifact, resumable, one-row-at-a-time named-person workflow for all 174 Gate-D
   review rows, preserving append-only supersession and prohibiting bulk/agent decisions; and
8. a provider-access contract and fail-closed adapter sequence for any TfGM SCOOT/UTC/UTMC/counter
   or NTIS measured-traffic product offered after the provider enquiry.

`NEXT-01`–`NEXT-08` are programme labels only. The first seven have independent engineering work;
real long-term retention still requires the owner's policy, real row decisions require the named
reviewer, and `NEXT-08` source implementation waits for exact provider access/schema/rate/time/
identifier/security/licence/publication evidence. No workspace was created or inspected, no
credential was used, no source was fetched, no reviewer decision was recorded, and no capability
or release standing changed in Phase 190.

### 6.6 Phase-191 durable workspace foundation (`NEXT-01`)

The first programme slice is now `working_bounded`. Two additive release commands provide a
path-free, mutation-free preview and exact digest-confirmed creation of a new v0.7 workspace. The
workflow refuses existing targets, repository descendants, symlinks and unsafe parents; uses
private sibling staging and atomic rename; enforces owner-only permissions; copies the empty
registry; validates a byte-exact isolated restore; reopens the normal v0.7 inspector; and writes a
path-free terminal receipt. Exact immediate retry reconciles every managed artifact and refuses a
moved, used, changed or unmanaged target.

The operator procedure is documented in
[durable v0.7 workspace creation](v07_durable_workspace.md). Verification uses temporary test
parents only. It does not prove that an owner-selected real workspace exists, and the receipt
explicitly records no accepted source data, acquisition or historical-store activation. `REL-01`
and every `MAN-*`/`UX-*` capability therefore retain their formal `planned` standing. `NEXT-02`
through `NEXT-08` remain separate slices.

### 6.7 Phase-192 local real-workspace run profile (`NEXT-02`)

The second programme slice is now `working_bounded`. A read-only preflight binds one exact durable
workspace receipt, current manifest/registry and fixed app-entrypoint digests; probes only
`127.0.0.1:8502`; reports credential presence, BODS box fingerprint and exact interval status;
validates existing hot controls, non-mutating source-lock availability and cached scenes; and
preserves source contract/freshness versions plus unresolved policy blockers. Its plan and CLI
outputs contain no credential value, coordinate box, shell fragment or private path and make no
provider request.

Exact digest confirmation launches only the fixed Streamlit argv in the foreground, overwriting
the child process's workspace/registry environment with the verified values. It binds loopback,
disables usage-stat collection and retains the existing independent BODS/National Highways worker,
manual fallback, lock/rate and stale-cache behaviour. The operator procedure is
[local real-workspace run profile](v07_real_workspace_run.md). Verification uses temporary empty
workspaces, fake local port probes and an injected process runner; it does not prove a real
workspace process or either provider was reached. `NEXT-03`–`NEXT-08` remain separate at the end
of Phase 192.

### 6.8 Phase-193 aggregate operational history (`NEXT-03`)

The third programme slice is now `working_bounded`. It supplies strict identifier-free terminal
records, an owner-only canonical hash chain, atomic exact-retry append, deterministic 24-hour UTC
compaction for both sources, explicit cadence denominators, London offset/fold projection and a
closed descriptive `SAFE_ANALYSIS_SUMMARY` adapter. Partial, divergent, duplicate, reordered,
unsafe or permission-invalid inputs fail closed. Immutable private day publication additionally
requires an exact owner-approved retention-policy fingerprint, a caller authority validator and
the configured delay.

The two release commands are read-only status and day-preview surfaces. The proposed policy cannot
mutate; the current workers are not wired to the journal; the existing 24-hour hot controls are
unchanged; and no raw quarantine is read. The operator contract is documented in
[Manchester aggregate operational history](integration/manchester_operational_history.md).
`NEXT-04`–`NEXT-08` remain separate, and real `NEXT-03` activation remains blocked on the owner
policy recorded in section 7.

### 6.9 Phase-194 National Highways transitions (`NEXT-04`)

The fourth programme slice is `working_bounded`. Exact accepted receipt/report bindings feed a
deterministic complete set reconciliation for consecutive same-product/scope/model snapshots. It
implements all six designed states, bounded opaque reappearance memory, a closed changed-field
allowlist, exact prior/current lineage and aggregate-only public-candidate projection. Absence is
labelled only as no longer listed unless the source validity end establishes expiry.

The service is pure and not wired to a real refresh or UI page. No public row release is approved,
and literal VMS display text and measured traffic remain unavailable. See
[National Highways transitions](integration/manchester_national_highways_transitions.md).

### 6.10 Phase-195 BODS operational trends (`NEXT-05`)

The fifth slice is `working_bounded`. Exact-bound live-refresh components yield only reconciled
counts, contract fingerprints, a distinct-operator total and exact source-age/skew/cadence
statistics. Safe failure attempts invent no response denominator. Explicit UTC windows retain
caller-declared expected cadence and refuse to present fewer than two successes as a trend;
deterministic UTC-day rollups bind their input fingerprints.

No vehicle, journey, service, location, operator or pseudonymised identifier survives the builder,
and no speed, trajectory or fleet-completeness claim is available. The library is not wired to a
real writer or page. See [BODS operational trends](integration/manchester_bods_operational_trends.md).

### 6.11 Phase-196 read-only Source Health (`NEXT-06`)

The sixth slice is `working_bounded`. An additive Overview route projects verified durable
workspace preflight, accepted BODS/National Highways hot controls, process-local worker registries
and the aggregate operational journal into two semantic health cards. Missing configuration,
starting/running/degraded/stopped state, local attempt/success/eligibility times, exact safe failure
codes, conservative local intervals, journal integrity and unresolved policy blockers remain
distinct. The page rerenders local state every 30 seconds without performing a provider request.

The JSON download is allowlisted and excludes credential values/hashes/prefixes, request-box
coordinates/fingerprints, workspace paths/handles and raw identifiers. Provider quota remains
unknown and local intervals are not relabelled as provider limits. BODS source time is unavailable
because the accepted hot summary does not retain it. The page cannot start/stop a worker, repair or
delete state, approve retention/licensing/publication, create evidence or host publicly. See
[Manchester Source Health](integration/manchester_source_health.md). `NEXT-07` remains the next
independent build; `NEXT-08` remains at fail-closed contract intake pending the provider reply.

### 6.12 Phase-197 resumable named-person review (`NEXT-07`)

The seventh slice is `working_bounded`. Match Review now discovers only the exact committed
305-row/174-queue Manchester v1.1 registration inside a verified workspace; the page accepts no
artifact, ledger or export path. It derives the private working ledger from registration, queue and
policy identities, resumes pending work, supports presentation-only search/filter/sort and local
bookmark state, captures one real person's local session identity, and shows explicit current
decision/revision lineage.

Each one-row save now refuses stale concurrent editors and uses lock, private temporary file,
fsync, atomic replace and strict readback before offering **Next pending**. Corrections explicitly
supersede and never overwrite. Seals are content-addressed, new-only, read back and leave the
working ledger untouched. A midpoint-restarted 174-row synthetic session proves the complete
workflow without a bulk API. The real v1.1 artifact does not retain coordinates or edge shapes, so
map rendering/map-text equivalence remains unavailable rather than inferred; human keyboard and
contrast acceptance also remains open. No real identity or Manchester decision was recorded. See
[resumable named-person review](integration/manchester_match_review.md).

### 6.13 Phase-198 provider-contract intake (`NEXT-08`)

The eighth slice is implemented only through its honest pre-reply boundary. A strict
`RestrictedTrafficFeedAccessContract` keeps TfGM SCOOT, UTC, UTMC, automatic counters and NTIS
measured traffic independent and requires reviewed access, delivery, cost, onboarding, quota,
licence/retention/publication, detector, timezone/DST, sensitive-field and exact technical-schema
facts. Unknowns fail closed; paid/bespoke terms require a quotation decision and approved budget
authority. Private provider prose, agreements, endpoints, credentials, paths and rows cannot enter
the safe assessment.

The CLI can emit an all-unknown template and inspect a private contract:

```bash
uv run traffictwin integration manchester provider template tfgm_scoot --format json
uv run traffictwin integration manchester provider status /private/path/contract.json --format text
```

Even a fully reviewed accepted contract stops at
`contract_accepted_adapter_not_implemented`; it authorises no credentialed probe and exposes no
measured traffic. No provider response/agreement is recorded in the repository, so the actual
TfGM/NTIS adapters remain unavailable pending product-specific evidence and a separately reviewed
transport/probe/parser stage. See [restricted traffic-feed contract intake](integration/manchester_restricted_traffic_feed_contract.md).

## 7. Decisions or evidence required before acceptance

| Required decision/evidence | Blocks |
|---|---|
| ~~Approved Manchester SUMO network, construction/version, CRS, date, and licence~~ — **answered 25 July 2026** (ADR-059: Greater Manchester baseline, Manchester LA filter, OSM/Geofabrik, netconvert 1.27.1, UTM 30N read from the network, ODbL 1.0) | ~~`MAN-09`, `MAN-11`, Gates D/E~~ |
| ~~PBF-to-OSM-XML decode step~~ — **resolved 25 July 2026**: the owner approved `osmium-tool` as a controlled external runtime; the full Greater Manchester network is built and validated | ~~Full Greater Manchester baseline network build~~ |
| ~~Owner-candidate map-matching thresholds/direction/road-class/confidence policy~~ — answered by v1.1; supervisor acceptance and 174 named-person row decisions remain | `MAN-09` human/scientific completion |
| Calibration objective, parameters, bounds, uncertainty treatment, and held-out design | `MAN-09`, `MAN-10` |
| Approved production comparison metric contract | `MAN-10` |
| WebTRIS source timezone semantics | Full `MAN-03`/`MAN-07` canonical time projection |
| DfT raw-count hour timezone and defensible profile policy | Full `MAN-02`/`MAN-09` use |
| BODS multi-day identifier persistence plus project privacy/data-management and public row-level output treatment; general reuse/publication and API registration were documented in Phase 185 | Full `MAN-05` and any public live output |
| Owner-approved private duration, backup, disk, deletion and public-output policy for identifier-free operational day aggregates | `NEXT-03` real long-term activation and public trend export |
| Complete versioned Bee Network service/operator/NOC membership evidence | Complete Bee Network claim in `MAN-05` |
| Exact provider response/agreement for each offered TfGM SCOOT/UTC/UTMC/counter or NTIS product, including access, cost, schema, quota, time/DST, detector, security, retention, licence and publication terms | `NEXT-08` source implementation and any resulting `MAN-07`–`MAN-10` use |
| Final publication classes and licence reconciliation for all source/reference/network artifacts | Gate B, Gate F, public release |
| Decision on participant usability study and any ethics/supervisor approval | RQ16 and final UX research acceptance |

An unknown answer blocks only its dependent capability. Other disjoint work should continue.
Each of these decisions is prepared for approval, with options, recommendations, and required
acceptance evidence, in the [v0.7 external decision pack](v07_external_decision_pack.md).

## 8. Functions that cannot be created honestly from current sources

| Function | Current status | Reason |
|---|---|---|
| Manchester-wide live private-vehicle counts, measured speeds, density, or congestion | `unavailable` | No authorised, audited city-road telemetry source has been supplied; BODS buses and National Highways operational events cannot substitute for it |
| Live traffic-signal phase, timing, queue, or controller state | `unavailable` | The TfGM source is a dated infrastructure-location archive only |
| Guaranteed complete Bee Network fleet/service coverage | `unavailable` | Complete membership, NOC/service reference rights, and feed completeness are unresolved |
| Public live/raw scene hosting | `unavailable` | General BODS reuse/publication is documented, but identifier privacy/retention and project row-level output approval, National Highways release review, other source licences, and complete gate acceptance remain open |
| External online road basemap | `unavailable` by current decision | The current map deliberately uses no tile provider to avoid hidden network and licensing claims; official ONS boundaries provide offline context |
| Running always-on daemon or cloud scheduler | `unavailable` | Phase 168 implements bounded unattended/cloud contracts, but no deployment account, funded authority, concrete transport or running service exists |

WebTRIS remains a useful historical/latest-available source. It is explicitly refused as
`near_live` after the controlled recency probe and must not be presented as current road telemetry.

## 9. Recommended execution order

1. ~~Freeze the network, decode step and owner-candidate matching policy; integrate the measured
   mapping/profile/contract readiness chain.~~ Completed through Phase 179. Complete the named-person
   row review and freeze the remaining calibration/uncertainty decisions.
2. Replace the gridlocking demand candidate and execute compatible calibration candidates under an
   approved, registered contract.
3. Complete the versioned baseline workflow and record the explicit human accept-or-refuse result.
4. Review/register the existing comparison contract and run the observed-versus-SUMO comparison
   only after compatible real inputs exist.
5. Execute the controlled SUMO-to-VEC chain and materialise complete lineage.
6. In parallel, close eligible Gate-B source records, Gate-C manual acceptance, and Gate-F
   migration/rollback tooling.
7. Reconcile project records, generated artifacts, security/licence evidence, capability truth,
   package version, CI, documentation, and the final immutable release tag.

The Phase-190 operational track can proceed alongside that scientific path: implement `NEXT-01`
then `NEXT-02`; freeze `NEXT-03` before `NEXT-04`/`NEXT-05`; build `NEXT-06` over their read-only
status contracts; and progress `NEXT-07` independently with the authorised named reviewer. Keep
`NEXT-08` at contract intake until the provider response closes its exact external blockers.

## 10. Update protocol

After a meaningful v0.7 increment, the integrating agent should:

1. update the relevant row and gate in this document;
2. update [implementation-status.md](implementation-status.md) with the evidence-backed formal
   truth;
3. update assumptions, open questions, architecture, ADRs, source audits, or licence records when
   their facts change;
4. record exact tests, real-source evidence, residual blockers, branch, and commit;
5. never change a capability to `accepted` from this tracker alone; and
6. preserve the immutable `v0.6.0` release and read-only external repositories.

## 11. Supporting records

- [Canonical TrafficTwin design v0.7](traffictwin-design-v0_7.md)
- [Implementation status](implementation-status.md)
- [Manchester live-feature matrix](integration/manchester_live_feature_matrix.md)
- [Accepted Manchester Gate-A audit](integration/manchester-source-gate-a-audit-v0_7.md)
- [Manchester Operations UI](integration/manchester_operations_ui.md)
- [Manchester calibration foundation](integration/manchester_calibration.md)
- [Manchester comparison foundation](integration/manchester_comparison.md)
- [Manchester research lineage](integration/manchester_research_lineage.md)
- [v0.7 compatibility and workspace isolation](v07_release_compatibility.md)
- [v0.7 external decision pack](v07_external_decision_pack.md)
- [Provider enquiry drafts (DfT, WebTRIS, BODS)](integration/provider_enquiry_drafts.md)
- [Supervisor Gate-D contract decision form](evaluation/supervisor_contract_decision_form.md)
- [Manchester SUMO network decision worksheet](integration/manchester_network_decision_worksheet.md)
- [Greater Manchester baseline network foundation](integration/manchester_baseline_network.md)
- [ADR-059 Greater Manchester baseline network](decisions/ADR-059-greater-manchester-baseline-network.md)
- [Operator v0.6 attestation procedure](integration/v06_attestation_procedure.md)
- [Manual accessibility checklist and evidence record](evaluation/manual_accessibility_checklist.md)
- [Assumption register](assumption-register.md)
- [Open questions](open-questions.md)
