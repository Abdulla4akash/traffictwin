# E3 Dynamic Resource V2 — Dormant Staged Design (No Results)

One Manchester incident hour 2024-03-15 20:00-21:00 Europe/London, provisional uk2030 fleet width 2488, 10 RSUs, 3600 ticks per cell (dormant), waiting-room ceiling 6220 (2.5x), fixed 1x service baseline, zero backhaul — bounded VEC staged design rendered through typed product code without running research.

Today there are **NO results**. Every numeric surface renders the truthful hold state explicitly. This is **NOT_EXECUTED** with **NO_E3_RESEARCH_RESULTS_AVAILABLE**. Admission fails closed until an exact approved Lane 09 package exists.

Immutable hold verbatim in code, docs, traceability and receipts:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Hosted CI truthfully `HOSTED_CI_UNAVAILABLE`. This is not a research approval.

No supervisor approval; standing is E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, LANE_09 BLOCKED_BY_RESEARCHER_EXECUTION_HOLD
No monetary cost claim; resource cost is resource_unit_seconds, never dollars/billing/currency
No Manchester-wide deployment tested; bounded to one incident hour and four fleet draws, replication unit fleet_draw, N=4, not population
No universal superiority claim; hypotheses H1-H5 are not expected truths; trade-off family has no scalar best objective
No Kubernetes actual deployment or cluster orchestration; placement is deterministic infrastructure scheduling, not managed cluster
No actor selects execution RSU; frozen actor does not observe load
No tasks-as-N; tasks are accounting records, not independent replicates; task-level N is forbidden
Bounded to staged designs E3a/E3b/E3c with 14 arms and 56 configs, replication unit fleet_draw N=4 matched draws 1-4, evaluator_seed 0, never tasks-as-N, never Manchester-wide inference, never universal superiority
Bounded to staged design E3a; no E3 results. Tasks are accounting records, not replicates; no Manchester-wide inference; no universal superiority.

## Launch

```bash
pip install -e .   # or use the packaged wheel
streamlit run src/traffictwin/ui/app.py -- --help   # then open the app
# Or via the package entry point:
traffictwin --help
```

No confidential values, no absolute-path configuration, no `run_e3_dynamic_resource_v2` needed. Research workloads launched remains 0 — the product re-presents dormant staged design, not results. The existing E2 product route is preserved byte-for-byte: `docs/e2_research_product.md` still describes the admitted VEC study and `scripts/validate_e2_research_product.py` still passes.

## Navigate

1. **Home** — find the card *Inspect E3 Dynamic Resource V2 — dormant staged design (no results)*.
2. Click **Inspect E3 Dynamic Resource V2**. This sets a one-shot session intent `resource_strategy_intent = "e3"` and switches to **Resource Strategy Explorer**.
3. The Explorer's top container shows *TrafficTwin E3 Dynamic Resource V2 (dormant - no results)* — the route `home.py -> app_pages/resource_strategy.py -> pages/resource_strategy_explorer.py` is validated by the AppTest journey and the validator's broken-route check. Direct access via the sidebar *Resource Strategy Explorer* also works (the visibly separate **Load TrafficTwin E3 Dynamic Resource V2** button is always present at the top, separate from the E2 button).

If the intent is missing the Explorer still offers the same obvious E3 action. The generic synthetic demonstration fixture remains available and the E2 preset **Load TrafficTwin E2 research** remains byte-for-byte unchanged.

Guided Demo also exposes the same E3 entry: *Inspect E3 Dynamic Resource V2* (dormant staged design, no results) with the same `resource_strategy_intent = "e3"` one-shot intent.

## Load built-in (one click, no path)

In **Resource Strategy Explorer**, click **Load TrafficTwin E3 Dynamic Resource V2**.

- Implementation: `load_builtin_e3_research()` via `importlib.resources` reads `traffictwin.resources.research.e3_dynamic_resource_v2.json`; `validate_e3_research_artifact()` delegates to `load_e3_research_evidence_json()` then checks every pinned identity and the no-results hold; `admit_e3_research(package)` returns typed `E3ResearchAdmissionRefusal` with `admitted=False`, `status=REFUSED`, `reason_code=REFUSED_MISSING_FUTURE_ARTIFACT`. No filesystem path input is needed for this preset. Any mutation fails closed and panels are withheld.

The E3 preset declares via `importlib.resources`, not via a filesystem path, so no absolute workstation path contributes. Exports contain no confidential values, no workstation paths, no timestamps.

## What is displayed (exact — truthful no-results)

### Hold banner and truthful refusal

- Banner: `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD` with `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`, `evidence_state = NOT_EXECUTED`, `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`, `research_workloads_launched = 0`.
- Admission panel: `REFUSED` `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED` `BLOCKED_BY_RESEARCHER_EXECUTION_HOLD` `REFUSED_MISSING_FUTURE_ARTIFACT` — admission fails closed until an exact approved Lane 09 package with the frozen fingerprints plus future analysis artifact and package fingerprint exists. No current input satisfies. The typed refusal includes `diagnostics.expected_missing` with both expected fingerprints null today.

### Scientific question and bounded scope

- Question: How do placement (ingress_dla vs per_task_dla vs p2c_dla), scaling (fixed_1x vs static_overprovisioned vs reactive vs proactive), and staleness (0/1000/3000 ms) trade off offered-task deadline attainment, rejection share, and resource_unit_seconds across matched fleet draws fleet_draw N=4 evaluator_seed 0 under a frozen MAPPO actor that does not observe load?
- Bounded to staged designs E3a/E3b/E3c with 14 arms and 56 configs, replication unit fleet_draw N=4 matched draws 1-4, evaluator_seed 0, never tasks-as-N, never Manchester-wide inference, never universal superiority
- One incident hour, 10 RSUs, 3600 ticks per cell dormant, waiting-room ceiling 6220, fixed 1x service baseline, zero backhaul.

### Strategy semantics

Typed `E3StrategySemantics` for each dormant arm (ingress_dla, per_task_dla, p2c_dla x fixed_1x, static_overprovisioned, reactive, proactive x state_age_ms 0/1000/3000). Example labels:

- `ingress_dla / fixed_1x @ 0 ms` — strongest-link execution plus deadline gate, 1 compute unit
- `per_task_dla / fixed_1x @ 0 ms` — per-task least-busy plus deadline gate, 1 unit
- `p2c_dla / fixed_1x @ 1000 ms` — pair-choice diffusion with stale view 1000 ms

All: MAPPO frozen `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` does not observe current RSU load and does not choose execution RSU; `is_learned=False`, `is_deterministic=True`; queue capacity is waiting-room tasks per RSU (6220 ceiling), compute capacity is active units 1..3 per RSU each drains 1000 work_ms per second, resource cost is resource_unit_seconds normalized usage not money. Waiting-room slots are distinct from compute units, strictly separate and never conflated. No Kubernetes actual deployment or cluster orchestration; placement is deterministic infrastructure scheduling, not managed cluster.

### Placement / scaling / staleness / resource trade-off structure

- Placements: `ingress_dla`, `per_task_dla`, `p2c_dla`
- Scalings: `fixed_1x`, `static_overprovisioned`, `reactive`, `proactive`
- State ages (typed int milliseconds): `0`, `1000`, `3000` — view parameter only, does not mutate true state, multiples of 1000, no drift.
- Compute capacity: active units per RSU range `[1, 2, 3]` (min 1, max 3, unit compute_unit, max_pending_actions 1) — free/unbounded scaling outside 1..3 is forbidden.
- Queue capacity: waiting-room `6220` tasks per RSU, unit waiting_room_task_slots, strictly separate from compute.
- Resource cost: metric `resource_unit_seconds` (unit resource_unit_seconds, interval 1 s, formula sum_over_RSU sum_over_interval active_compute_units * interval_seconds, normalized usage not money, monetary False) — missing denominator fails closed, currency claims are forbidden.
- Staged design: E3a 12 cells (3 placements x 1 scaling x 1 staleness x 4 draws), E3b 16 stage-listed, 12 unique additional (4 scalers x 1 placement x 1 staleness x 4 draws minus 4 overlap), E3c 32 stale variants max (not rerun, view parameter) over 56 unique configs, 14 arms, not double counted, maximum candidate unique cells 56.

Dormant arms (14) and configs (56) are structure only — not results. Every arm/config lists placement/scaling/state_age_ms exactly.

### Per-RSU and scale-action summary structure (null with reasons)

- Per-RSU summaries: `value = None` — UNAVAILABLE per-RSU summaries null before execution.
- Scale-action receipts: `value = None` — UNAVAILABLE scale-action receipts null before execution, research_workloads_launched = 0, evidence_state = NOT_EXECUTED.
- Capacity levels: `value = None` — UNAVAILABLE capacity levels null before execution.
- State-age receipts: `value = None` — typed int milliseconds 0/1000/3000, null with reason before execution, state_age receipts not yet run.

Every numeric surface for per-RSU and scale-action renders NOT_EXECUTED / NO_E3_RESEARCH_RESULTS_AVAILABLE explicitly — never a number, never an empty chart implying zero.

### Task accounting (offered / admitted / rejected / forwarded / deadline_success — null lifecycle with reasons)

All counts are null with reasons in NOT_EXECUTED state. Conservation is null with reason. Genuine rejection classes are structure, not counts.

| field | value | status | reason |
| --- | --- | --- | --- |
| offered | None | UNAVAILABLE | no E3 research workloads launched, research_workloads_launched = 0 |
| admitted | None | UNAVAILABLE | no E3 cells executed under hold |
| rejected_total | None | UNAVAILABLE | genuine rejection classes not yet observed |
| forwarded | None | UNAVAILABLE | forwarding null before execution |
| deadline_success | None | UNAVAILABLE | deadline success null before execution |
| started | None | UNAVAILABLE | not separately emitted |
| compute_completed | None | UNAVAILABLE | not distinct from deadline_success |
| returned | None | UNAVAILABLE | not distinct from deadline_success |
| dropped | None | UNAVAILABLE | cannot derive without split |

Genuine rejection classes (structure only): `v2i_gate_rejected`, `v2i_cap_rejected`, `local_mqd_rejected`, `v2v_mqd_rejected`, `v2i_unavailable`, `v2v_unavailable` — all remain null with reasons, never zero. Validator and UI refuse unavailable-to-zero coercion.

Queue vs compute strictly separate: queue waiting_room_task_slots vs compute compute_unit, is_separate True.

Resource cost: metric resource_unit_seconds monetary False value None reason UNAVAILABLE — resource_unit_seconds null before execution, not monetary, not zero.

### Missingness (first-class)

Every unavailable field is null with an explicit reason; never hidden, never zero. Fields include offered/admitted/rejected_total/forwarded/deadline_success plus unavailable lifecycle and scaling receipts and resource_unit_seconds and paired_differences (null with N=4 interval not yet computed).

### Comparison structure (E3a / E3b / E3c — no results)

Replication unit fleet_draw N=4 matched draws 1-4, evaluator_seed 0, two-sided Student-t 95% interval df=3, t=3.182. All per-draw values are null with reasons while hold is active. Tasks are accounting records, not replicates.

- E3a: p2c_dla minus per_task_dla, p2c_dla minus ingress_dla at fixed_1x stale 0 — 2 paired differences, both per_seed null.
- E3b: static_overprovisioned/reactive/proactive minus fixed_1x across offered deadline attainment, rejection_share, resource_unit_seconds at per_task_dla stale 0 — 6 paired differences, all null.
- E3c: p2c_dla vs per_task_dla and reactive vs proactive across staleness values — 4 paired differences, all null, state as view parameter over 0/1000/3000.

No empirical offering; no placeholder fabricated results.

### Provenance

- Product base SHA: `2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c`
- Research promotion SHA: `342789434233e97cd87ea74e21a759878610ce40`
- Approved candidate SHA: `c5d66ef7e77f3b7d1f3fde084feea45a83f5c178`
- Contract checkpoint SHA: `211a6662151ccad43187f8a2ce3f75a57515408d`
- VEC promotion: `dc606770059f0c4a413bac2217d7f38600b74fff` core: `53e34db6146da40118a6c816f6a1ffaa2596ddf3` adapter: `c37f97ea66b236dfc662bfdd6bee7eab1a775bbc`
- Actor SHA-256: `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` — does not observe load and does not select execution RSU, frozen implementation-verified fact
- Trace SHA-256: `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`
- Contract SHA-256: `f0d6eb913df6c2165a63ddcb0fd4980368e9bb80bbd38db964273ba3925f4870`
- Manifest sidecar SHA: `39862882ae34e71260ce5b466fcd4a93d61da783c4dd16fc987be562ea396438`
- E3 package fingerprint (canonical sorted SHA-256): `e5ff1bc0e3410d47520c2e841803c8fa67efb3581b8f52a66e407552457b8e8c`
- Lane promotions: Lane 08 approved `c5d66ef7e77f3b7d1f3fde084feea45a83f5c178` promotion `342789434233e97cd87ea74e21a759878610ce40`; Lane 10 approved `194941f0dcb1e2f72351fb030d7f58679c001205` promotion `8a2f0fffb605fac94ec625f49f80260a54daba6d`; Lane 11 approved `e87b2ed39d1ad2ebd6d98dd0f0a9156158ea166d` promotion `6edf8f447244ede8bcc942c4d6a7c03fef45a606`
- Campaign: `e3-dynamic-resource-v2`, Lane 12 base integration `4f1ef5bc82585e2a719387a71c38e188f3f43594`, campaign base `6e3fd0d385c20c7262e096f2d7da4995a7d9c21b`
- Hosted CI: `HOSTED_CI_UNAVAILABLE`

### Limitations and non-claims

Limitations (8) — bounded incident hour, fleet draws, actor/trace frozen, queue/compute separation and resource_unit_seconds not money, task counts unavailable, staleness typed int, provenance first-class, admission fail-closed.

Non-claims (10):
- No Manchester-wide deployment tested; bounded to one incident hour and four fleet draws, replication unit fleet_draw, N=4, not population
- No universal superiority claim; hypotheses H1-H5 are not expected truths; trade-off family has no scalar best objective
- No monetary cost claim; resource cost is resource_unit_seconds, never dollars/billing/currency
- No Kubernetes actual deployment or cluster orchestration; placement is deterministic infrastructure scheduling, not managed cluster
- No actor selects execution RSU; frozen actor does not observe load
- No tasks-as-N; tasks are accounting records, not independent replicates; task-level N is forbidden
- No supervisor approval; standing is E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, LANE_09 BLOCKED_BY_RESEARCHER_EXECUTION_HOLD
- Queue capacity is waiting-room slots, not compute units; queue/compute conflation forbidden
- No physical result-return verification; deadline_success is simulator outcome when executed
- No stale-state communication savings proven; H1 remains hypothesis about pair-only vs global least-busy dependence

The validator fails if any limitation is removed or any non-claim is affirmed as an affirmative deployment/monetary/universal/Manchester/supervisor claim. Tasks are accounting records, never replicates.

## E2 preservation (frozen)

The E2 admitted research product is pinned byte-for-byte: package fingerprint `195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269` and receipt `45e8c2782ff40495e472bc0e6de3ba3be1610fdb974f88b7ffd12a754d031ebc`, base `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`. The Home `Inspect real E2 research` intent `e2` and Explorer `Load TrafficTwin E2 research` (no path, via importlib.resources) still work exactly as documented in `docs/e2_research_product.md`; the existing E2 route returns ADMITTED RESEARCH with the four pinned E2b/E2c/E2d numerics. The E3 validator pins these and proves the E2 journey still works.

## Deterministic export

In the Explorer's E3 mode, three downloads are offered: **Download E3 JSON**, **Download E3 CSV**, **Download E3 Markdown** from `build_e3_research_exports(package, receipt) -> E3ResearchExportBundle`. They are byte-identical across rebuilds (two live deterministic builds compared), contain no absolute workstation paths, no secrets, no timestamps, and echo the exact hold, dormant counts (14 arms, 56 configs), provenance, missingness and typed null lifecycle above. The validator compares JSON/CSV/Markdown vs the typed payload and fails on mismatch. Exports contain `resource_unit_seconds` as the cost denominator, queue vs compute separation notes, and state_age_ms typed ints 0/1000/3000.

Run the strict validator locally:

```bash
python scripts/validate_e3_research_product.py
pytest tests/integration/test_e3_research_product_acceptance.py -v
```

Both must pass without launching research workloads. Hosted CI is `HOSTED_CI_UNAVAILABLE`.

## What this product does not claim

No supervisor approval; standing is E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, LANE_09 BLOCKED_BY_RESEARCHER_EXECUTION_HOLD
No Kubernetes actual deployment or cluster orchestration; placement is deterministic infrastructure scheduling, not managed cluster
Not a live traffic claim, not population inference, not free-flow validated, not physically verified return, not a research approval
No monetary cost claim; resource cost is resource_unit_seconds, never dollars/billing/currency
No actor selects execution RSU; frozen actor does not observe load
No universal superiority claim; hypotheses H1-H5 are not expected truths; trade-off family has no scalar best objective — it re-presents the bounded dormant staged design through a typed, deterministic UI and export path with truthful empty state until exact Lane 09 approval.

