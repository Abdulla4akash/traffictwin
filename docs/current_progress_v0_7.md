# TrafficTwin v0.7 Current Progress and Build Plan

**Snapshot date:** 24 July 2026

**Development branch:** `claude/complete-v0.7` (integration branch created at the protected
`v0.7.0-alpha.4` checkpoint `4e95a5d` on `codex/traffictwin-v0.7`)

**Snapshot commit:** the head of `claude/complete-v0.7` after Phase 2B Tier 1 integration, the
REL-01 CLI foundation, the MAN-09 temporal-profile foundation, the synthetic analyst-review and
temporal-profile demonstrations, the automated cross-page-state evidence, the external decision
pack with its 24 July 2026 source-documentation probe, and the ADR-058 producer attestation

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

At the snapshot commit:

- 686 Manchester-focused unit tests pass;
- 1,609 unit tests and 169 UI tests pass, 1,778 combined;
- repository-wide Ruff formatting and checks pass;
- strict mypy passes over all 703 configured source and test files;
- lock validation and package build pass;
- the built wheel contains the required Manchester boundary assets; and
- 35 routes across desktop/mobile and light/dark modes produce 140 browser screenshots with zero
  actionable semantic findings.

The browser result is automated regression evidence. It is not a WCAG, screen-reader, participant,
or research-usability acceptance claim.

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
| Gate D | Observation-to-SUMO mapping, calibration, accepted baseline, and observed-versus-simulated comparison | `foundation_only` | Approve a network and scientific contracts; extend the synthetic mapping/review harness to accepted real evidence; build profile/baseline orchestration; register and exercise a real comparison contract | 7–14 working days after decisions |
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
| `MAN-05` BODS live transit | `working_bounded` | Real authenticated acquisition, safe SIRI-VM parsing, live/stale classification, local map, outage fallback, five verified Bee operator identifiers, rate limiting, aggregate history, and precautionary cleanup | Complete Bee service/fleet scope, `BNVB`, registration/retention/publication terms, and complete provider acceptance remain unresolved |
| `MAN-06` Randy Manchester bridge | `working_bounded` | Permission-safe local panel over accepted sanitised VEC-11 evidence, aggregates, citations, fingerprints, and limitations | Full workflow acceptance remains; source limits deliberately prohibit raw identity, geographic/live relabelling, and public hosting |
| `MAN-07` projection/freshness service | `working_bounded` | UTC time-basis contract, source truth states, BODS and National Highways freshness, spatial admission, exclusions, and ONS display boundaries | Real canonical time projection for DfT/WebTRIS is blocked by unresolved source-time semantics; broad real-source projection acceptance remains |
| `MAN-08` Manchester Operations | `working_bounded` | Historical/latest/live-vehicle modes, source-separated maps, BODS and National Highways refreshes, TfGM/DfT/WebTRIS views, filters, source cards, stale fallback, Randy panel, and metadata-only download | Broad/multi-site acceptance, upstream capability acceptance, public-export decisions, and manual accessibility/participant acceptance remain |
| `MAN-09` observation-to-SUMO baseline | `foundation_only` | Deterministic synthetic-only map-matching candidate and typed analyst-review harness with thin in-page synthetic review and temporal-profile demonstrations, a bounded calibration evaluator with coverage, residual, exclusion, parameter, and fingerprint controls, and a day-type/season/slot temporal-profile builder with exact source dates, typed exclusions, visible missing cells, and a frozen-empty production policy registry | No approved Manchester network/licence or real-source matching/review/profile policy, real calibration, uncertainty decision, accepted baseline, or baseline-triggered SUMO run |
| `MAN-10` observed-versus-simulated comparison | `foundation_only` | Deterministic contract model, pairing, exclusions, missingness protection, coverage, lineage, and MAE/RMSE implementation | The production contract registry is intentionally empty; no scientific contract or real compatible comparison has been accepted |
| `MAN-11` Manchester SUMO-to-VEC workflow | `foundation_only` | Strict path-free lineage graph and explicit missing-stage reporting | No accepted baseline, controlled Manchester SUMO receipt, matching one-second FCD/network pair, complete Manchester VEC chain, or research/usability evaluation exists |
| `UX-01` task-oriented navigation | `working_bounded` | All 34 v0.6 pages mapped into five groups with stable direct routes, Material icons, normal v0.7 routing, complete legacy fallback, a candidate action-aware Guided Demo with persistent progress and automatic next-task routing, and automated cross-page shared-state evidence for both routers; minimum/locked Streamlit, wheel, AppTest, and browser checks pass | Final cutover decision, package-version reconciliation, and manual accessibility acceptance remain |
| `UX-02` map-led home/workflow | `working_bounded` | Focused research home, primary actions, meaningful local KPIs, and latest accepted Manchester context | Final release and human usability/participant acceptance remain |
| `UX-03` responsive/accessibility system | `working_bounded` | Native theme/components, presentation mapping, deprecated-width removal, responsive layouts, the integrated Tier 1 page-presentation harvest (SUMO/bundle/TOS import, comparison, About, experiment tracking, and the shared truncated-fingerprint caption with Advanced identity), and 140-view visual regression | Manual keyboard, screen-reader, contrast, zoom, and participant checks remain; automation cannot claim WCAG conformance |
| `REL-01` v0.6/v0.7 isolation | `foundation_only` | Separate v0.7 workspace/registry/cache namespaces, byte-exact read-only v0.6 registry copying, bounded init/inspect/preview/copy CLI commands, a demo-launcher `--port` option for side-by-side operation, and a workspace setup/diagnostics guide | Migration activation, backup, interrupted-migration recovery, rollback, side-by-side clean-checkout acceptance, and final release/tag reconciliation remain |

## 6. Major work ready to build now

The following tasks have useful implementation work that can begin without pretending an
unavailable live source exists. Real acceptance may still depend on the decisions listed in the
next section.

### 6.1 Gate D: complete the research core

1. Extend the existing deterministic synthetic-only site-to-edge harness to a reviewed Manchester
   network and accepted real projections without weakening its complete Cartesian reconciliation.
2. Analyst-review UI: a thin synthetic demonstration panel now walks the typed review boundary
   (clear, ambiguous, and no-candidate situations with explicit per-observation decisions and a
   downloadable typed record) inside Manchester Operations; extending it to real evidence still
   requires the approved real-source matching policy.
3. Temporal-profile builder: done as a candidate foundation (exact source dates, gaps, typed
   exclusions, day type, season, structural time basis, and no missing-as-zero behaviour);
   production policy approval and resolved source timezone semantics remain external.
4. Connect the existing calibration evaluator to mapping, parameter selection, residual review,
   uncertainty, and explicit analyst acceptance.
5. Produce the versioned `ManchesterSumoBaseline` artifact and bind it to the existing controlled
   SUMO service.
6. Approve/register one versioned `ManchesterComparisonMetricContract`, wire the existing
   comparison engine to accepted evidence, and add the comparison UI.

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
3. Implement v0.6 migration preview, backup, transactional copy, interruption recovery, refusal,
   activation, and rollback.
4. Run v0.6 and v0.7 from separate clean checkouts, ports, and workspaces.
5. Reconcile CLI, generated schemas/references, capability manifest, documentation, package
   version, CI, and final immutable tag.

## 7. Decisions or evidence required before acceptance

| Required decision/evidence | Blocks |
|---|---|
| Approved Manchester SUMO network, construction/version, CRS, date, and licence | `MAN-09`, `MAN-11`, Gates D/E |
| Map-matching thresholds, direction/road-class rules, confidence categories, and analyst policy | `MAN-09` |
| Calibration objective, parameters, bounds, uncertainty treatment, and held-out design | `MAN-09`, `MAN-10` |
| Approved production comparison metric contract | `MAN-10` |
| WebTRIS source timezone semantics | Full `MAN-03`/`MAN-07` canonical time projection |
| DfT raw-count hour timezone and defensible profile policy | Full `MAN-02`/`MAN-09` use |
| BODS identifier retention, display, export, publication, and registration terms | Full `MAN-05` and any public live output |
| Complete versioned Bee Network service/operator/NOC membership evidence | Complete Bee Network claim in `MAN-05` |
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
| Public live/raw scene hosting | `unavailable` | BODS retention/publication, National Highways release review, other source licences, and complete gate acceptance remain open |
| External online road basemap | `unavailable` by current decision | The current map deliberately uses no tile provider to avoid hidden network and licensing claims; official ONS boundaries provide offline context |
| Always-on daemon or cloud scheduler | `out_of_scope` | v0.7 defines explicit bounded/operator-triggered acquisition; a persistent service needs a separate deployment and governance design |

WebTRIS remains a useful historical/latest-available source. It is explicitly refused as
`near_live` after the controlled recency probe and must not be presented as current road telemetry.

## 9. Recommended execution order

1. Freeze the Manchester SUMO network and Gate-D scientific decisions.
2. Extend the synthetic map-matching/review foundations to the accepted network and build temporal
   profiles.
3. Complete calibration orchestration and create the first reviewable baseline.
4. Approve one production comparison contract and run the observed-versus-SUMO comparison.
5. Execute the controlled SUMO-to-VEC chain and materialise complete lineage.
6. In parallel, close eligible Gate-B source records, Gate-C manual acceptance, and Gate-F
   migration/rollback tooling.
7. Reconcile project records, generated artifacts, security/licence evidence, capability truth,
   package version, CI, documentation, and the final immutable release tag.

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
- [Assumption register](assumption-register.md)
- [Open questions](open-questions.md)
