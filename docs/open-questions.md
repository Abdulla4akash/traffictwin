# TrafficTwin Open Questions

This register separates questions that block implementation from questions that affect later dissertation framing or optional features.

## Questions For Abdulla

Answered before Phase 1:

- `diss/` is the permanent TrafficTwin project root.
- The v0.4 design document was canonical at `diss/docs/traffictwin-design-v0_4.md`; it is now the
  preserved historical rationale and meeting-traceability record.
- The no-timeline v0.5 design document is canonical at
  `diss/docs/traffictwin-design-v0_5.md`; design inclusion does not imply implementation.
- Git should be initialised inside `diss/`.
- Phase 1 should proceed with package and CLI name `traffictwin`.
- Streamlit and other UI work remain out of scope until the later UI phase.

Open:

1. Which exact thresholds should R1-R5 use for dissertation evaluation, and should they remain synthetic-demo defaults until real evidence exists?
2. Which rule outputs should be included in dissertation screenshots?
3. What evidence is needed before R1 can use a T1-by-low-tier cross-tab rather than the current lower-confidence proxy?
4. What evidence is needed before R2 can evaluate temporal overlap between saturation windows and task misses?
5. What matched capacity, routing, and spatial evidence is required to calibrate R4?
6. What matched training/validation protocol and threshold should be used to calibrate R5?
7. Which files from Randy's `TOS Data` package may be committed as small sanitised fixtures?
8. After Randy supplies producer/writer/checkpoint evidence and fixture permission, should the next
   increment trial one sanitised source-specific conversion?
9. Should future persisted metric results materialise contribution-ledger references, or is the
   implemented on-demand complete accepted-row ledger sufficient?
10. May aggregate values from Randy's package be included in a publicly hosted static atlas, or
   only in private supervisor/dissertation materials?

### v0.5 design decisions

The complete decision list is maintained in
[TrafficTwin v0.5 §14](traffictwin-design-v0_5.md#14-open-design-decisions). The most immediate
cross-cutting questions are:

1. Resolved for `MET-01` by `ADR-016` and `DIA-01` by `ADR-022`: aligned half-open `[start,end)`
   windows, versioned table anchors, explicit/inferred ranges, visible empty/partial windows, and a
   typed R6 projection that preserves gaps. An optional declared event maps to its containing
   effective window; future event-aligned window recomputation remains separate.
2. Resolved for `STA-01` by `ADR-028`: the estimand is the original-unit mean variation-minus-
   baseline paired difference; uncertainty uses a deterministic paired percentile bootstrap; the
   two-sided test uses exact/seeded-Monte-Carlo sign flips; paired secondary effects are Cohen's dz
   and matched-pairs rank-biserial. Cliff's delta is not automatic, and its difference-test
   non-significance is never interpreted as equivalence.
3. Resolved for `STA-02` by `ADR-029`: policies are ranked independently inside each scenario
   family over identical complete common-seed rows; objective-aware ties/ranks/regret reuse the
   winner map, and joint paired-seed bootstrap reports mean/rank uncertainty without tests or
   equivalence claims.
4. Resolved for the `STA-03` method boundary by `ADR-030`: paired-mean TOST reuses the STA-01
   cohort and demonstrates equivalence only when both one-sided tests reject against a
   predeclared positive symmetric absolute margin. Margin basis and justification are mandatory;
   literature claims require a reference. The defensible numeric margin for each primary
   dissertation metric remains a study-specific research decision, not a software default.
5. Resolved for `STA-04` v1.0 by `ADR-031`: candidate goldens cannot pass; approved versioned
   contracts target completed MetricCollection or STA-01 artifacts; each scalar uses the inclusive
   maximum of declared absolute and relative tolerance. Exact-source and compatible-context source
   policies are separate, and invalid comparisons remain unavailable.
6. Resolved for `STA-05` v1.0 by `ADR-032`: use prospective two-sided paired-mean normal-
   approximation planning over an explicitly declared target effect and paired-difference
   variance; return the smallest bounded common-seed count meeting target power; label small,
   synthetic, and provisional inputs; and make no retrospective-power or guarantee claim. The
   defensible numeric effect and variance remain study-specific researcher decisions.
7. Which future external sources can satisfy the implemented task-energy, task-to-RSU target, and
   vehicle coordinate-frame contracts without relabelling incompatible evidence?
8. Resolved for `DIA-04` and reference R7 by `ADR-023`: flat `all`/`any`, finite scalar thresholds,
   mapping maximum gaps, exact booleans, exact unit/scalar metadata, and explicit group support.
   Arbitrary code/imports/formulas/templates/dynamic keys/nested rules and unsafe YAML are rejected.
9. Resolved for `PRO-01` by `ADR-033`: the closed v1.0 registry admits direct scalar counts, sums,
   means, and rates only after exact accepted-row reconciliation. Percentiles, extrema, distinct/
   episode metrics, grouped/fairness/spatial aggregates, and plugins without a separate formula
   expose eligible lineage without weights; mapping-valued comparisons are not flattened.
10. Resolved for `PRO-02` by `ADR-034`: use root-centred deterministic breadth-first selection,
    explicit default/hard bounds, stable path-safe node/edge identities, timestamp-independent
    graph identity, safe and structure-only disclosure profiles, and DOT/GraphML parser/golden
    evidence. Layout remains renderer-dependent presentation, not lineage evidence.
11. Resolved for `PRO-03` by `ADR-035`: use the selected report template's explicit typed
    metric/rule/comparison references as the denominator, retain unavailable claims, publish named
    non-claim exclusions, award no partial credit, require complete non-empty accepted-row ledgers
    for the numerator, and publish null for a zero-claim report.
12. Resolved for `EXP-01` by `ADR-036`: accept one strict synthetic-config or seed base, a closed
    scalar parameter catalogue, no more than four axes/16 values each/256 points, and at most 16
    local core response metrics, with published value ranges and a 2,000,000 declared-row local
    admission limit. Only labelled local synthetic generation plus ordinary
    validation/metrics may execute; external requests stay explicitly `not_executed` with no
    launcher or command.
13. Resolved for `EXP-02` by `ADR-037`: admit only ordinarily valid, explicitly labelled
    synthetic/evaluation bundles; apply exactly one closed row-dropout, timestamp-jitter, or
    RSU-removal operator to a copied uncompressed CSV target; derive row choices from SHA-256 and
    a declared seed; retain an exact bounded row/file ledger; validate the derived bundle before
    transactional publication; and never infer rerouting or external execution.
14. Resolved for `EXP-03` by `ADR-038`: use only independently hash-derived bounded-uniform noise
    over the closed generated-observation field set and exact hash-ranked dropout over observation
    streams; retain one row; keep outcome/time/routing evidence unchanged; require a strict typed
    manifest audit and explicit synthetic/not-calibrated/raw-unchanged labels.
15. Resolved for `REP-01` by `ADR-039`: render only four existing typed artifact families through
    one bounded fingerprinted projection; preserve source/availability/warning/status semantics;
    use escaped package-free LaTeX2e plus self-contained SVG or invariant PDF; redact absolute
    paths; and publish explicit exact files without adding scientific calculations.
16. Resolved for `REP-02` by `ADR-040`: store bounded author/note/decision records against a closed
    typed target reference; verify registry-resident targets, admit explicit detached generated
    references, assign monotonic sequence/content identity, reject update/delete, and render only
    in a non-computed report section outside scientific claims.
17. Resolved for `REP-03` by `ADR-041`: compare only compatible structured report payloads through
    prose-free typed claim snapshots; classify exact section/claim changes through canonical JSON
    paths; exclude rendering, timestamps, warnings, labels, commands, and annotations; and retain
    typed unavailable outcomes for incompatible or non-claim content.
18. Resolved for `REP-04` by `ADR-042`: project one compatible typed report through a closed
    five-highlight quota policy; retain complete availability counts, all warnings, all exact
    limitations, and relative fingerprinted provenance links; exclude annotations and scientific
    recomputation; and fail closed when complete A4 content needs more than one page.
19. Resolved for `REP-05` by `ADR-043`: rebuild an on-demand six-category local projection; open
    SQLite read-only; inspect only bounded direct report files; redact absolute paths before
    matching; use published Unicode lexical AND ranking and stable ties; expose complete counts,
    skips, category labels, snippets, and fingerprints; and treat score as relevance only.
20. Resolved for registry history by `ADR-044`: support formal migration versions 1–4, empty
    databases, and recognised unversioned repository-era additive shapes. Representative future
    workload sizes remain open; cache, doctor, and RO-Crate private-artifact policies are now
    resolved by ADR-045, ADR-046, and ADR-047 respectively.
21. Resolved for `OPS-04` by `ADR-047`: one accepted ordinary generic bundle may embed exact raw
    bytes, privately reference relative names/sizes/hashes, or exclude all raw identifiers. Public
    imported embed/reference needs confirmed permission, written basis, and a raw licence; unknown
    or denied public evidence must be excluded. Citation/licence/identifier claims are not inferred.
22. Resolved for `OPS-05` by `ADR-048`: use a closed runtime-checkable four-operation interface;
    discover exact direct markers only; refuse no-match, ambiguity, and symbolic links; delegate to
    existing source validators; and publish path-free semantics, capabilities, provenance,
    non-ordinal conversion profiles, blockers, and required evidence. SUMO stays partial canonical
    for trips; TOS stays aggregate/source-specific with unknown publication rights and no canonical
    task/RSU conversion. New adapters require reviewed code, fixtures, and acceptance evidence.

Resolved for `EXP-02`: `ADR-037` fixes immutable-parent admission, the three v1.0 operators,
hash-derived determinism, target-table restrictions, exact provenance ledgers, validation, and
transactional publication. Multi-operator composition is represented only by an explicit chain of
individually materialised derived bundles. Encoding-preserving gzip-CSV/Parquet mutation and any
scientifically justified dissertation severity/seed matrix remain future, researcher-owned work.

Resolved for `EXP-03`: `ADR-038` fixes the supported fields, bounded-uniform/integer error
semantics, clamps, separate seed, exact retain-one dropout, ordering, independent hash inputs,
strict embedded audit, synthetic-only labels, and transactional generated-bundle publication.
Empirical distributions, correlated errors, drift/bias/occlusion, calibrated missingness, real
sensor validation, and externally defensible dissertation bounds remain future research choices.

Resolved for `REP-01`: `ADR-039` fixes the four supported artifact families, shared projection
fingerprint, row/column/cell/figure bounds, escaping and path-redaction policy, source-mode labels,
signed-linear and categorical figure semantics, deterministic SVG/PDF methods, exact-file
publication, and checksum receipts. Dissertation-specific table styling, wide-table pagination,
interactive charts, and additional artifact families remain future renderer choices; they cannot
move metric, statistical, or diagnostic logic into reporting.

Resolved for `REP-02`: `ADR-040` fixes the closed target/decision catalogues, stored-versus-
detached target policy, exact/unbound fingerprint matching, author/note/ID/time bounds, monotonic
sequence, database update/delete guards, bounded pagination, complete-or-refuse report inclusion,
and structural separation from computed claims. Authentication, access control, rich text,
attachments, external identity providers, and collaborative conflict resolution remain future
operational choices.

Resolved for `REP-03`: `ADR-041` fixes supported report types, compatibility codes, typed claim
snapshots, scientific/excluded fields, the five classifications, canonical JSON Pointer changes,
fingerprints, bounds, and JSON/Markdown/CLI/UI surfaces. Rendering diffs, statistical
interpretation, causal attribution, automatic merging, rich review workflows, and new scientific
calculations remain outside this capability.

Resolved for `REP-04`: `ADR-042` fixes compatible typed-report admission, the five-slot quota
selection order, complete availability/omission disclosure, retain-all-or-refuse caveat policy,
relative source/claim links, path redaction, four output formats, invariant PDF rendering, and
exactly-one-page overflow refusal. Importance ranking, recommendation, causal interpretation,
free-text summarisation, hosted provenance routing, annotation inclusion, and scientific
recalculation remain outside this capability.

Resolved for `REP-05`: `ADR-043` fixes the six categories, registry/report source inventory,
read-only SQLite mode, direct non-symlink report policy, Unicode AND matching, integer field/
phrase/token weights, tie order, path redaction before matching, query/result/candidate/report/text
bounds, exact counts/fingerprint, CLI/UI surfaces, and interpretation limits. Persistent FTS,
fuzzy/semantic search, PDF extraction, raw-row search, permissions, remote services, and scientific
importance ranking remain outside this capability.

Resolved for `OPS-01`: `ADR-044` fixes five contiguous schema versions, `PRAGMA user_version`, an
immutable checksummed ledger, whole-plan `BEGIN IMMEDIATE` rollback, object/type/column and
`quick_check` validation, formal v1-v4 plus known unversioned adoption, payload preservation,
read-only status, and CLI/library surfaces. Downgrades, arbitrary third-party objects, automatic
backups, scientific-payload reinterpretation, and recovery of manually corrupted ledgers remain
outside the automatic migration boundary.

Resolved for `OPS-02`: `ADR-045` fixes exact raw re-fingerprinting, a complete raw/adapter/
validator/mapping/canonical-schema/cache-format key, six strict Parquet tables, checksummed typed
metadata, accepted-result-only admission, atomic publish-after-reread, byte/row/decoded-size bounds,
and visible miss/stale/incompatible/corrupt states. Raw evidence stays separate and bad entries are
never automatically deleted or overwritten. Streaming, SUMO/TOS, retention/eviction, remote/shared
caches, signatures/encryption, and representative future workload sizes remain outside v1.

Resolved for `OPS-03`: `ADR-046` fixes the four check states, required-check-only overall health,
Python/core/optional inventories, path-only external command discovery, complete generic/SUMO/TOS
capability summaries, bounded standalone-workspace inspection, immutable OPS-01 registry status,
OPS-02 read-only cache status, advisory access probes, text/JSON output, and blocked-only non-zero
exit. Package installation, external command execution, registry/cache/workspace repair, persisted
permission attestation, scientific validation, and a `--fix` mode remain outside v1.

Resolved for `ING-01`: the legally reusable acceptance fixture is the official Eclipse SUMO 1.27.1
`tools/game/square` scenario at tag `v1_27_1`. `ADR-011` records the pinned commit, licence,
generation command, and conservative mapping.

Resolved for `ING-02`: `ADR-012` defines the closed header-alias catalogue, three distinctive task
value patterns, published sampling bounds, unit-evidence rule, explicit confirmation/edit artifact,
stale-source rejection, and ambiguity behavior. Adding aliases or vocabularies later is a versioned
contract change, not an automatic learning process.

Resolved for `ING-03`: `ADR-013` makes format/compression explicit, admits only flat supported
Parquet scalar types, applies a 10,000,000-byte decoded-table limit, keeps a stable logical record
locator, and retains exact raw-byte bundle identity. Larger memory-bounded input is handled by the
separate `ING-05` decision below.

Resolved for `ING-04`: `ADR-014` defines explicit path/glob resolution, deterministic
deduplication/order, 64-reference and 256-candidate preflight bounds, typed consolidated and
per-bundle outcomes, one existing registry transaction per accepted candidate, unchanged
idempotency/conflict semantics, and non-zero partial/failed CLI behavior. Larger single-table
memory handling is resolved separately by `ING-05` below.

Resolved for `ING-05`: `ADR-015` keeps ordinary ingestion unchanged and defines opt-in row/byte-
bounded CSV, gzip-CSV, and Parquet decoding; a structural pre-pass; provisional synchronous chunk
consumption; exact temporary SQLite reconciliation; stable logical row locators; nested table/ZIP
bounds; metadata-only streaming import; and a generated-fixture equivalence/memory benchmark.
Question 6 remains open for representative deployment benchmark sizes and full-process RSS/Randy
workloads; the current measurement is a labelled 75,000-task synthetic implementation fixture.

Resolved for `MET-01`: `ADR-016` assigns task outcomes to arrival cohorts, trip outcomes to
departure cohorts, and observed-state tables to their timestamps; uses aligned half-open windows;
keeps empty and excluded partial windows visible; defines coverage only as requested-range overlap;
and declares all then-current task/infrastructure/traffic/trip metrics window-applicable. MET-03
through MET-05 extend the current core window-applicable total to 60. Multi-table metrics use only
independently in-window support. True observation-completeness evidence remains unavailable;
`DIA-01` now projects the complete artifact into typed temporal evidence without pretending that
geometric coverage proves observation completeness.

Resolved for `MET-02`: `ADR-017` retains deterministic linear rank-`n-1` interpolation for task
latency P50/P95 and adds P99. The default minimum sample is one; a singleton returns its sole value
with a warning, zero latency observations use `NO_LATENCY_VALUES`, and a configured unmet minimum
uses `INSUFFICIENT_SAMPLE_SIZE`. Sample P99 is descriptive, not a worst-case or confidence bound.

Resolved for `MET-03`: `ADR-018` admits per-task total energy in joules only through the strict
manifest `TaskEnergyContract` v1.0. It fixes row level and eligibility for observed-task energy,
completed-task energy, and completed-task energy-delay product; missing values are excluded and
negative values rejected. Pairwise comparison requires equal semantic fingerprints. Generated
synthetic bundles satisfy this contract; current SUMO and TOS sources do not. Which future external
sources can truthfully declare the contract remains open.

Resolved for `MET-04`: `ADR-019` limits fairness outputs to exact operational vehicle-tier and RSU
groups, requires two groups, support of two eligible observations in every observed group, and
complete in-scope coverage, and versions/fingerprints the policy and exact group set. Vehicle tier
is not a protected attribute. Current SUMO/TOS contracts remain unavailable.

Resolved for generic/synthetic `MET-05`: `ADR-020` admits per-RSU task outcomes only under an
explicit contract declaring V2I `target_id` as the observed executing RSU, complete non-empty
target coverage, and exact canonical RSU joins. Vehicle spatial summaries require a separate named
metre-based source frame, fixed grid geometry, required x/y columns, and complete finite
coordinates. Nearest-RSU assignment, task-position interpolation, CRS/geographic inference, and
causal attribution are excluded. Whether a future external source satisfies either contract
remains an adapter evidence question.

Resolved for `MET-06`: `ADR-021` uses explicit trusted in-process registration with no uploaded
code, arbitrary module path, or automatic environment discovery. Contracts declare canonical
inputs, availability, units, scope, version, output schema, optional window anchor, unavailable
behavior, and row provenance. The engine uses deep-copied bounded inputs, verifies two canonical
outputs, rejects duplicate/core keys before evaluation, isolates each failure, and requires equal
contract fingerprints for scalar comparison. Process isolation, signed packages, timeouts, and
ambient plugin discovery remain optional future engineering questions rather than blockers.

Resolved for `DIA-01`: `ADR-022` retains the `EvidencePack` as the sole rule boundary, projects one
direction-declared scalar series without dropping window states, maps only an optional declared
event, and defines exact consecutive baseline/degradation/recovery semantics. R6 thresholds remain
provisional until representative per-metric evidence and domain review establish defensible
values; event-aligned recomputation and statistical change detection are separate future methods.

Resolved for `DIA-02` and `DIA-04`: `ADR-023` defines the bounded trusted-local static YAML
grammar, three-valued evaluation, exact unit/metadata/group admission, local/core identifier
boundary, and definition fingerprint. R7 selects either stable operational vehicle-tier completion
or exact execution-target RSU completion; it never merges dimensions or infers protected
attributes, geography, significance, or cause. Its `0.20` default remains provisional pending a
predeclared study-specific basis and representative domain review.

Resolved for `DIA-05`: `ADR-025` admits exact nearest flips only for the inclusive single-boundary
R5, R7, and R8 severity thresholds after unchanged discrete support requirements pass. A candidate
must be verified by the ordinary rule engine over the same EvidencePack. R0-R4, R6, and arbitrary
declarative rules remain explicitly unsupported until a defensible monotonicity, distance, and
constraint contract exists.

Resolved for `DIA-06`: `ADR-026` evaluates only those contracted R5/R7/R8 axes over a bounded
inclusive linear grid, retains every ordinary rule status, separates sampled transition intervals
from exact DIA-05 output, and keeps all non-swept support/dimension settings fixed. The Streamlit
surface uses session-only configuration and requires explicit complete-config import/download;
multi-parameter, R6, compound-core, and arbitrary declarative sweeps remain open future design.

Resolved for `DIA-07`: `ADR-027` gives R0 readiness presentation precedence 100 over ordinary
rules at equal precedence 50. R1/R2 conflict and R1/R4 corroboration activate only when both rules
trigger and cite the declared exact shared evidence key. R0 suppression activates only for an
explicit `blocked_rules` target and changes actionability/presentation only. Every original result
and reason is retained; confidence is unchanged; undeclared pairs remain unclassified.

Implemented while these questions remain open:

- a synthetic-only public static dashboard that contains no Randy-derived values;
- a private checksummed TOS supervisor pack;
- a public TOS atlas command that refuses to stage without explicit permission attestation;
- machine-readable readiness gates that keep all unrelated technical blockers intact.

Resolved during Phase 3:

- Saturation threshold is held in `MetricEngineConfig` and documented as synthetic-demo configuration.
- Synthetic expected metric outputs are stored as JSON golden projections under `tests/golden/expected/`.

Resolved during Phase 4:

- The first UI supports both direct bundle paths and optional registry-backed imports.
- Run Overview prioritises task completion, incomplete rate, deadline-miss rate, latency, and offload metrics.
- The Streamlit launch command is documented rather than adding a Typer wrapper.

Resolved during Phase 5:

- The UI page is now `Evidence & Diagnostic Hypotheses`.
- Diagnostic rules are deterministic code over EvidencePacks only.
- R3 returns `insufficient_evidence` for ordinary single-run bundles.

Resolved during the Independent Research Tools increment:

- R3 experiment evidence is now a first-class reusable EvidencePack built from stored metrics.
- R4/R5 are deterministic candidates with explicit evidence requirements and unavailable states;
  R5 pair sets now reject mixed policy, checkpoint, metric, environment-role, or repeated-seed
  provenance.
- Winner maps exclude incompatible seed-family observations instead of ranking mixed units or
  versions.
- A fixed synthetic portfolio study now covers five families, three policy profiles, three random
  seeds, and a disjoint S5/S6 held-out partition; real policy calibration and statistical/external
  evaluation remain open.
- S5/S6 and full incident/event round-trip plus linked what-if authoring are available as synthetic
  workflow fixtures.
- Protocol execution can be tracked manually without implying simulator launch.
- Participant-evaluation documents exist as unapproved drafts; formal approval remains open.

Resolved during Phase 6A:

- The original repository did not contain real Randy/VEC or SUMO artifacts.
- Randy has now supplied an external `TOS Data` package with real evaluation summaries, instrumented NPZ outputs, traces, and training records.
- Evaluation summaries and instrumented NPZ schemas are sufficient for a conservative read-only
  integration without interpreting RSU fields.
- Vehicle array slots are time-local padded indices, not safe persistent vehicle IDs.
- The read-only integration now validates/imports summaries, exposes replay/task samples, and
  produces partial evidence and aggregate provenance.
- Randy later supplied `vec_env`; source inspection confirmed task/action codes, deadlines, trace
  units, RSU active-task/backlog/capacity meanings, scenario-control mechanisms, and the evaluator
  CLI.
- The source evaluator is not yet a TrafficTwin launcher because checkpoints, instrumented writer,
  portable paths, and local runtime verification are absent.

Resolved during TOS Results Workbench productisation:

- All 300 source-summary rows can be explored as a campaign/cell matrix without canonicalising
  absent task records.
- Campaign comparison pairs exact common fleet seeds and reports descriptive deltas only.
- Training warm-up non-finite values are represented as unavailable rather than JSON NaN.
- Processed FCD supports mobility-state replay but not persistent identity or trip duration.
- The static atlas can be generated offline, but public deployment remains permission-gated.

Resolved during guided-workflow polish:

- First-time and mobile users can enter the workflow through Home without opening the collapsed
  Streamlit sidebar.
- The synthetic and imported-TOS walkthroughs are separate evidence tracks and do not imply direct
  simulator launch, live data, or canonical TOS conversion.

Resolved during documentation pass:

- Documentation reference artifacts are generated from code under `docs/reference/generated/`.
- A manual screenshot checklist was documented; the later advanced-tools increment added
  executable browser screenshot and bounded semantic accessibility regression checks.

Resolved during Provenance Explorer productisation:

- Provenance is read-only and does not recompute metrics or reinterpret rules.
- Aggregate metric traces show eligible rows and bounded samples. The later additive contribution
  query exports every accepted candidate row and its deterministic eligibility state without
  fabricated per-row causal weights.
- EvidencePack-only fault-injection traces mark source-row links unavailable unless a bundle exists.

Resolved during Standalone Product phase:

- TrafficTwin can be demonstrated without Randy/VEC, SUMO, external services, or live data.
- Standalone scenarios are generated as ordinary run bundles and imported through the Phase 2
  registry path.
- Synthetic policy profiles use `synthetic-*` labels and do not impersonate real trained
  algorithms.
- Report export is deterministic Markdown/HTML/PDF and does not use an LLM.
- The one-click demo launcher initialises the workspace if absent and starts Streamlit with
  explicit workspace environment variables.

Resolved during the Advanced Research Tools increment:

- Fault evaluation now spans severity and random-seed variants and reports false positives,
  specificity, robustness, split summaries, and failure IDs.
- Portfolio studies now report variability, failure cases, pairwise dominance, and CSV/Markdown.
- Synthetic baseline/incident/infrastructure case-study packs are generated automatically.
- Full accepted-canonical-row metric contribution ledgers are available on demand.
- Deterministic A4 PDF reports, constrained findings prose, a non-geographic corridor replay,
  automated desktop/mobile screenshots, and basic semantic accessibility checks are implemented.
- Labelled mock participant results can be analysed descriptively, but formal data collection
  remains ethics-gated and unimplemented.

## Questions For Dr. Sandra Sampaio

1. Confirm the actual dissertation submission date and interim milestone dates.
2. Confirm whether TrafficTwin should lead with OffloadLens, the journey-time lens, or the dual-lens platform framing.
3. Confirm whether the C1 plus C2 framing, platform plus portfolio/selector, is appropriate for dissertation scale.
4. Confirm whether formal participant evaluation is required for dissertation evidence.
5. If formal evaluation is required, confirm survey versus semi-structured interview and whether business-school contacts may participate.
6. Confirm whether the earlier XITS note to wait for `MATERIALS COMPLETE` is also superseded for dissertation planning, not only for implementation.
7. Confirm whether Manchester is only the first case study or should constrain the implementation choices more strongly.
8. Confirm whether the digital-twin term should be qualified as replay-and-scenario digital twin in the dissertation.

## Questions For Randy

Randy answered the five source-integration questions on 21 July 2026:

1. `vec_env` commit `068b4ea…` contains the trace and instrumented-output writers.
2. Updated `tos-data` contains frozen baseline and `ukfleettrain-MAPPO` actors plus an exact
   dictionary command intended to run from clones of both repositories.
3. The updated artifacts are reported to include completion summaries, exact occupancy-based
   `sumo_vehicle_id` spans, tier/EV fields, chosen RSU/V2V targets, and four scenario-day
   `tripinfo` sets.
4. Arbitrary one-second SUMO FCD plus its network file is reported to use the same pipeline and can
   emit exact occupancy tables.
5. Sanitised samples and aggregates may be used in the repository/dissertation when both
   repositories, engine `v2_post_nrsus_fix`, and any `_s102` best-of-seeds selection are disclosed.

The `VEC-01` audit now confirms both remote refs and inspects the pinned files without changing the
older clean worktrees. It resolves the first three source questions:

1. Per-task rows expose deadline success only; no eventual physical-completion field exists.
2. Target fields are best eligible decision-time targets and `-1` means none eligible. A policy can
   still select V2I/V2V with `-1`, so an action is not unconditional proof of transfer.
3. No compatible per-task energy field exists; only aggregate run energy is available.

Two scoped questions remain for later publication/reproduction decisions, not for Gate A:

1. What exact redistribution basis applies to full checkpoints, raw occupancy/trip files, and
   third-party SUMO assets beyond the written sanitized-sample/aggregate permission?
2. VEC-08 now freezes and accepts a narrow JAX/JAXLIB 0.4.30 CPU tolerance for one full weekend
   protocol-seed case. What additional tolerance, if any, is justified on other CPU/GPU hardware?

The complete source evidence is in
[the VEC-01 audit](integration/randy-source-snapshot-audit-v0_6.md); the implementation plan is in
[the v0.6 design](traffictwin-design-v0_6.md).

## Implementation Blockers

- The updated source snapshot, completion meaning, target semantics, and identity/trip coverage are
  verified by `VEC-01`; VEC-02 is accepted with its exact contract, synthetic suite, and VEC-11
  permission-manifested real sanitised pack. VEC-03–VEC-05 joins are separately accepted.
- Direct launch now has accepted VEC-07 typed-runner evidence and VEC-08 full weekend protocol-seed
  reproduction evidence against exact supplied Git blobs. VEC-10 exposes it only as conditional,
  foreground, request-preflight-gated execution; VEC-08 still does not establish cross-platform or
  scenario-wide equivalence.
- Arbitrary one-second FCD/network preprocessing is implemented by VEC-06, but input pairing remains
  caller-declared because FCD XML has no authenticated network-file identity. Its generated coverage
  sites are analysis locations, not evidence of deployed RSUs.
- External canonical energy metrics require per-task source rows and a compatible semantic
  contract; drop-cause, queue-clearance, and capacity-normalised metrics still require confirmed
  source fields and units.
- R1-R8 thresholds require synthetic calibration first and real calibration only after representative data is supplied; R6/R7/R8 defaults are explicitly provisional.
- R1 direct low-tier/T1 evidence is now a candidate occupancy/task/tier join and must pass complete
  reconciliation before EvidencePack admission.
- R2 temporal-overlap evidence is now a candidate task/target/RSU join, but `rsu_load` and
  `rsu_busy_ms` remain active-task count and compute backlog rather than canonical utilisation or
  queue length.
- UI controls must remain unavailable or unknown until adapter capabilities are evidenced.
- Phase 2 generic CSV validation can proceed with synthetic fixtures, but real Randy compatibility needs an adapter because the supplied lower-level files are NPZ/JSON, not standard bundle CSV.
- Phase 3 can compute deterministic metrics on synthetic fixtures, but real-world interpretation remains blocked on confirmed Randy/SUMO mapping and expert review.
- The read-only TOS integration remains the imported-results baseline. VEC-01–VEC-12 and Gates
  A–G are accepted. Remaining VEC questions concern new scientific evidence, formal licensing and
  public-hosting authority, or broader platform/scenario claims—not an unbuilt catalogue item.
- Documentation is now broad enough for supervisor review, but dissertation claims still require real integration, literature verification, and any formal evaluation evidence.
- Persisting contribution-ledger references inside each `MetricValue` remains a future storage
  choice; complete accepted-row ledgers are already available on demand.
- VEC-03 now resolves source vehicle identity for every active cell in the five audited traces.
  VEC-04 now resolves the six matched task/action/target streams and VEC-05 resolves all audited
  tripinfo joins. VEC-09 admits the compatible source metrics but leaves R1/R2/R7 blocked and R6
  conditional; a predeclared temporal threshold study remains open before any real rule finding.
- A project licence still needs explicit selection before public release.
- A synthetic demonstration can be hosted publicly without TOS data, but publishing source code or
  Randy-derived results still requires the relevant licence and permission decisions.
- Randy's response plus `VEC-01` resolve producer/checkpoint/writer presence and the narrow
  sanitized-fixture/aggregate permission boundary. A local evaluator reproduction and broader
  redistribution basis remain open.
- Experiment planning is not blocked by external integration: it records a proposed design only.
  Executing planned run slots remains adapter-gated and unavailable.
- Deterministic YAML/CSV protocols now support manual coordination and later manifest matching;
  who or what executes each slot, and the actual environment/checkpoint provenance, remain external
  responsibilities until an evidenced launcher exists.
- R4 needs comparable multi-RSU capacity, active-task, utilisation, placement/routing, and spatial
  demand evidence before real interpretation.
- R5 needs explicitly paired training-validation results with compatible policy, checkpoint,
  metric, environment, and common-seed provenance before real interpretation.
- Formal participant recruitment and data collection remain blocked until the relevant ethics and
  supervisory approvals are recorded.

## Non-Blocking Unknowns

- Real portfolio rules, calibration, and statistical evaluation.
- Later use of DuckDB or Polars.
- Optional XAI instrumentation.
- Near-live or true-live data sources.
- Encoding-preserving mutation writers for gzip-CSV/Parquet and evidence-backed severity/seed
  matrices beyond the closed EXP-02 v1.0 contract.
- Empirically calibrated measurement-error distributions, correlation/drift models, and
  evidence-backed dropout mechanisms beyond the closed EXP-03 synthetic fixture contract.
- Persistent multi-user settings or authentication.
- Formal accessibility and assistive-technology evaluation beyond the bounded automated audit.
