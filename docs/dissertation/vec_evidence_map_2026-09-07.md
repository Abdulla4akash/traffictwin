# Evidence map for the September VEC integration

Prepared 7 September 2026 for the owner's authorised evidence archiving and
dissertation integration. This map identifies the sources for the integrated
results section; it does not claim supervisor approval or introduce a new
long-form Methodology chapter.

All paths below resolve within the private repository. The
[archive inventory](../evaluation/vec_followup_2026-09-07/ARCHIVE_INVENTORY.json)
binds copied bytes to their original locations and records the large local arrays.
Historical E0–E2d material is pinned to public reporting commit
`e6faab86ddc6fd1097e04db0f4cd5e3cfb1f055e`; it retains its own original scientific
source and manifest identities.

| Section / claim | Exact evidence | Interpretation boundary |
|---|---|---|
| E0 establishes accounting validity | [E0 report and full validation](../evaluation/vec_followup_2026-09-07/historical_e0_e2d/experiments/E0/README.md) | Validation is not a scheduler-performance finding. |
| E1 separates waiting-room capacity from service | [E1 comparison](../evaluation/vec_followup_2026-09-07/historical_e0_e2d/experiments/E1/evidence/e1_multidraw_physical_campaign_comparison_v1.json) | Five draws; primary result inconclusive, without an equivalence claim. |
| E2/E2b separate placement from admission | [E2b report and factorial data](../evaluation/vec_followup_2026-09-07/historical_e0_e2d/experiments/E2b/README.md) | One exploratory draw; `jsq` and `dla` have different admission settings. |
| Incident implementation reversal | [E2c report](../evaluation/vec_followup_2026-09-07/historical_e0_e2d/experiments/E2c/README.md), [E2d paired results](../evaluation/vec_followup_2026-09-07/historical_e0_e2d/experiments/E2d/data/e2d_paired_results.csv) | Four matched draws; reused E2c controls; E2d direct common-target contrast is secondary. |
| MAPPO, ingress and execution responsibilities | [Historical method](../evaluation/vec_followup_2026-09-07/historical_e0_e2d/docs/METHODOLOGY.md), [Randy/Sandra correspondence](../correspondence/sandra_randy_vec_progress_email_thread_2026-08-18.md) | The actor chooses a mode; the environment and infrastructure determine targets and admissions. |
| Sub-second report model and compatibility | [Frozen timing contract](../evaluation/vec_followup_2026-09-07/frozen_evaluator/docs/RSU_STATE_DELAY.md), [compatibility receipt](../evaluation/vec_followup_2026-09-07/frozen_evaluator/validation/evidence/rsu_state_delay_compatibility_v1.json) | Batched arrivals retained; continuous service defines past reports; live admission and immediate acknowledgements retained. Compatibility probes are not an exhaustive historical rerun. |
| State-delay pilot and empty 100 ms reports | [Five-cell comparison](../evaluation/vec_followup_2026-09-07/state-delay-pilot-2026-09-07/comparison.csv), [mechanism audit](../evaluation/vec_followup_2026-09-07/state-delay-pilot-2026-09-07/mechanism_audit.json) | One fleet draw; 100 ms and fresh supply identical workload values; no general staleness-resilience claim. |
| Fixed forwarding overhead | [Qualification](../evaluation/vec_followup_2026-09-07/forwarding-sensitivity-2026-09-07/qualification.json), [analysis receipt](../evaluation/vec_followup_2026-09-07/forwarding-sensitivity-2026-09-07/analysis_validation.json) | Four direct short probes qualify the full-record transformation. No new full positive-cost simulations. No physical network or reconstructed mean-latency claim. |
| Morning trace and absolute capacity | [Input audit](../evaluation/vec_followup_2026-09-07/generalisation-pilot-2026-09-07/input_validation.json), [replication manifest](../evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/manifest.json) | Nine RSUs, canonical entry markers, 6,220 tasks per RSU. Several scenario features differ from the incident case. |
| Exploratory morning pilot | [Pilot results](../evaluation/vec_followup_2026-09-07/generalisation-pilot-2026-09-07/RESULTS.md) | Seed 1 was inspected before replication and is excluded from primary inference. |
| Four new draws and three-arm reversal | [Protocol](../evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/PROTOCOL.md), [paired differences](../evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/paired_differences.csv), [intervals](../evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/paired_intervals.csv) | Seeds 0, 2, 3, 4; locally prespecified before new outcomes, not externally preregistered; fleet-draw inference, conditional on one trace and task seed. |
| Workload and rejection diagnostic | [RSU workload distribution](../evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/rsu_workload_distribution.csv), [run metrics](../evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/runs.csv) | Descriptive mechanism evidence; does not identify a single cause of the cross-scenario effect-size difference. |

## Integration structure

The [current integrated results section](vec_results_integration_2026-09-07.md)
contains the E0–E2d evidence foundation, the new primary morning replication,
two bounded incident sensitivity studies, and critical reflection. The morning
replication is the principal addition; the two single-draw sensitivities provide
supporting evidence and limitations. The full tables, controls and validation
receipts remain in the archive, avoiding a long command ledger in the report body.

Use this section when revising the Evaluation/Reflection chapter within its
existing word allocation. It replaces overlapping draft evaluation material;
it must not simply be appended to the already 8,396-word August manuscript.
The [rubric authority](comp66060_rubric_readiness_2026-08-19.md) continues to
require 7,000–9,000 report words, concise related work inside the Introduction,
and separate Abstract and Conclusion sections.

## Conflicts and remaining manuscript work

The August manuscript centres on an earlier aggregate-latency capacity study.
The later E0–E2d programme uses repaired task accounting and offered-task
deadline attainment. Their scientific identities and denominators must not be
silently combined. The August text is retained as historical drafting material;
the present section follows the later E0–E2d evidence hierarchy.

The new studies are completed follow-ups under the frozen E2d-derived evaluator.
They do not represent execution or approval of the separate E3 Dynamic Resource
V2 campaign. The historical E3 hold remains unchanged.

No new literature search or literature-novelty claim is introduced here. A full
manuscript revision still needs its Introduction/related-work audit, a reviewed
Methodology evidence map, final Abstract/Conclusion alignment, University-template
formatting and whole-report word-count verification. The integrated section is
an evidence-supported draft, not a submission-ready whole dissertation.
