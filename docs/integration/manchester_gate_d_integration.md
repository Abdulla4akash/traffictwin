# Design — Manchester Gate-D contract integration

**Status: IMPLEMENTED IN PHASE 179. The integration presents existing candidate records, but it
does not turn them into a reviewed mapping, calibrated baseline or real observed-versus-simulated
result.**

## 1. Purpose and present truth

Gate D is no longer an empty foundation. Existing repository work already supplies a reviewed
Greater Manchester network, real DfT acquisition, owner-policy v1.1 map-match candidates, a sealed
one-row-at-a-time analyst-review ledger, a real DfT temporal-profile candidate, pure calibration and
comparison engines, and an owner-candidate comparison contract. These parts are individually
auditable but are not yet joined into one current, read-only decision packet.

The integration packet answers three questions without running anything:

1. What has actually been measured or frozen?
2. Which exact dependency prevents the next Gate-D artifact?
3. Which decision belongs to a person, supervisor or lead rather than software?

Formal `MAN-09`, `MAN-10` and `MAN-11` acceptance remains unchanged. Gate D remains
`foundation_only` because no completed human map review, approved calibration design, viable
calibration run, accepted `ManchesterSumoBaseline` or admitted real comparison exists.

## 2. Fixed source boundary

The UI service may read only these repository-relative files:

- `docs/integration/manchester_map_matching_decision_worksheet.md`;
- `docs/integration/evidence/manchester_map_match_candidates_20260725.json`;
- `docs/integration/evidence/manchester_map_match_policy_v11_20260725.json`;
- `docs/integration/evidence/manchester_dft_temporal_profile_20260725.json`; and
- `docs/integration/evidence/manchester_chain_restoration_20260728.json`.

Each file must be a regular non-symlink inside the resolved repository root, non-empty, below a
fixed size limit and SHA-256 bound. JSON sources are parsed into narrow typed extracts; the complete
raw payload is never sent to the page. The worksheet supplies the two published sensitivity tables
and its exact digest. The service makes no network request, probes no operator workspace, opens no
private match/profile/network artifact and writes nothing.

Repository measurements, typed integration receipts and contracts remain distinct. A source
binding records its role, evidence class, exact digest, support scope, limitation and whether it is
LLM output. LLM output is always false; the integration packet itself is not scientific evidence.

## 3. Mapping-policy decision support

`MapMatchingDecisionSupport` binds owner policy v1.1 and preserves:

- the inherited 50 m retrieval bound, 30/50 m native/fallback eligibility, 10/20 m strict-clear
  thresholds and 45-degree direction tolerance;
- the 5 m exact-signed-reference family override and every non-claim around it;
- all 305 observations: 131 owner-policy accepted candidates, 165 awaiting manual review, nine
  no-suitable-candidate rows and zero unavailable-missing-evidence rows;
- the two acceptance paths (106 strict, 25 override), 51 applied/readmitted candidate edges and
  1,339 refused edges; and
- the full 174-row review queue, with zero human decisions and nine no-candidate rows retained.

Owner-policy acceptance is never renamed human, analyst or supervisor acceptance. A typed
`AnalystReviewReadiness` record refers to the already-implemented sealed ledger contract and keeps
all 174 rows pending. It contains no reviewer identity, decision or editable control.

Threshold sensitivity is presented as measured evidence, not as a selector. The fixed 10/20/30/
50/100 m rows appear for both the 742 known-A-road reference sample and the 305 real DfT-site
sample. Counts, candidate distributions and multi-class percentages must reconcile to their
population; the browser offers no threshold control and no new threshold can be inferred from a
selected row.

## 4. Temporal-profile to calibration orchestration

The profile binding retains the accepted real snapshot identity, local-clock-hour basis, 07:00
simulation-origin convention, exact one-hour intervals, 305 sites, 3,256 series, 39,072 observed
cells, 166 measured zeros, zero filled cells, exact development/held-out denominators and both open
time-semantics blockers. Coverage 1.0 means completeness of that source window only.

`CalibrationOrchestration` is a dependency ledger, not a calibration executor. It connects the
profile's exact hourly-cell semantics to the existing calibration engine's exact-interval input
contract while keeping these unresolved prerequisites visible:

- a completed human decision for the pending map-match rows and a treatment for nine unmatched
  sites;
- a verified projection-report and final mapping fingerprint suitable for downstream binding;
- one predeclared objective, parameter grid/bounds and uncertainty/held-out design;
- a viable demand candidate and completed compatible SUMO candidate runs; and
- reviewed registration of the exact production calibration contract.

The adapter statement permits only a one-to-one representation of an observed 3,600-second cell as
`vehicles_per_interval`; it performs no resampling, timezone conversion, aggregation, interpolation,
source fusion or missing-as-zero substitution. No observation rows are materialised in Phase 179.

## 5. Versioned baseline-candidate workflow

`ManchesterBaselineCandidateWorkflow` freezes the required order:

1. reviewed mapping disposition inventory;
2. compatible temporal-profile binding;
3. admitted calibration contract and completed candidate report;
4. viable controlled-SUMO receipt with complete exclusions/deviations;
5. uncertainty and held-out review; and
6. an explicit human accept-or-refuse record.

The delivered record has `unavailable_missing_inputs` state, lists every missing artifact, and fixes
`baseline_created`, `baseline_accepted`, `sumo_executed`, `automatic_acceptance` and
`scientific_evidence` false. It cannot carry a candidate fingerprint until every upstream
fingerprint exists, and Phase 179 provides no constructor that manufactures those fingerprints.

## 6. Comparison-contract workflow

The existing owner-candidate comparison contract is reused, not copied or relaxed. Its exact
fingerprint binds DfT raw counts, Manchester local-authority scope, local-clock-hour semantics,
3,600-second exact intervals, `vehicle_count` / `vehicles_per_interval`, complete pairing keys,
equal-interval weighting, per-side denominators, exclude-unpaired-never-zero missingness, 0.800
coverage thresholds, MAE/RMSE, `ROUND_HALF_EVEN` at 0.001 and descriptive non-causal wording.

The contract exists but its production registry is empty. `ComparisonContractWorkflow` therefore
reports `candidate_unregistered` and makes metric values structurally unavailable. It also names
the absent compatible projection, reviewed mapping, calibration, accepted baseline, controlled run
and simulated interval inventory. GEH is outside this frozen contract and no acceptance threshold
is invented. A low future error would remain descriptive and would not establish realism,
causality or model validity.

## 7. Complete lineage and refusal semantics

The packet emits an ordered Gate-D lineage from observation source through mapping candidate,
human review, temporal profile, calibration, baseline and comparison. Available candidate records
carry exact artifact/source digests. The first missing input is explicit; every downstream stage
records the dependency it is waiting on. Gaps never disappear and are never represented by zero,
an empty success or a placeholder fingerprint.

The top-level model revalidates every count, source digest, threshold table, stage dependency,
contract fingerprint and fixed negative. It refuses private paths, credentials, participant or
vehicle identifiers, non-finite values, inconsistent queue totals, promoted approval states,
registered-contract claims that disagree with the real registry, and any comparison metric value.

## 8. Read-only Gate-D UI

An additive `manchester-gate-d` page shows source bindings, policy thresholds, both sensitivity
tables, v1.0→v1.1 reconciliation, pending analyst-review status, temporal-profile denominators,
calibration prerequisites, baseline workflow, the exact comparison contract and complete lineage.
Native tables and expanders provide responsive, keyboard-compatible presentation without using
colour as the only carrier of meaning.

There is no input, form, file picker, upload, download, checkbox, selectbox, button, reviewer field,
registry action, launch action or result calculation. Fixed repository links are the only links.

## 9. Verification and residuals

Tests must cover exact source binding, sensitivity denominators, mapping/profile reconciliations,
pending-review truth, calibration and baseline blockers, comparison fingerprint/registry truth,
lineage propagation, deterministic packet identity, reload mutation refusal, privacy, no-write/
no-network/no-execution source checks, route uniqueness and rendered absence of action controls.

Residuals are concrete and external to this slice: 174 per-row review decisions require a real
named person; DfT/WebTRIS provider clock semantics remain unresolved; calibration methodology and
uncertainty require scientific approval; the gridlocking demand must be replaced; compatible runs
must actually execute; a lead must separately register reviewed contracts; and a human must accept
or refuse a baseline. No contract or UI can supply those facts or authorities.
