# E2 Research Product — Admitted VEC Evidence

One Manchester incident hour, four matched provisional fleet draws, evaluator seed 0, fixed 1x compute service, zero backhaul — bounded VEC study rendered through typed product code without re-running research.

This is **ADMITTED RESEARCH** under **OWNER-AUTHORIZED PRODUCT ADMISSION**. This is not supervisor approval and not Randy confirmation. Placement is deterministic infrastructure-side RSU management, optionally termed Kubernetes-inspired deterministic scheduling; it is not actual Kubernetes deployment or cluster orchestration, not learned, and not autonomous infrastructure control.

## Launch

```bash
pip install -e .   # or use the packaged wheel
streamlit run src/traffictwin/ui/app.py -- --help   # then open the app
# Or via the package entry point:
traffictwin --help
```

No environment secrets, no absolute-path configuration, and no `eval_sumo`/`run_e2` needed. Research workloads launched must be zero — the product re-presents frozen evidence.

## Navigate

1. **Home** — find the card *Inspect real E2 research — admitted VEC study*.
2. Click **Inspect real E2 research**. This sets a one-shot session intent `resource_strategy_intent = "e2"` and switches to **Resource Strategy Explorer**.
3. The Explorer's top container shows *TrafficTwin E2 research (packaged canonical artifact)* — the route `home.py -> app_pages/resource_strategy.py -> pages/resource_strategy_explorer.py` is validated by the AppTest journey and the validator's broken-route check. Direct access via the sidebar *Resource Strategy Explorer* also works.

If the intent is missing the Explorer still offers the same obvious action.

## Load built-in (one click, no path)

In **Resource Strategy Explorer**, click **Load TrafficTwin E2 research**.

- Implementation: `builtin_e2_research_json()` via `importlib.resources` reads `traffictwin.resources.research.e2_resource_strategy_v1.json`; `validate_e2_research_artifact()` delegates to `load_e2_research_evidence_json()` then checks every pinned identity; `load_admitted_builtin_e2_research()` returns `(package, receipt)` and `admit_e2_research(package).verify()` must pass. No filesystem path input is needed for this preset. Any mutation fails closed and panels are withheld.

## What is displayed (exact)

### Admission

- Badge: `ADMITTED RESEARCH` and `OWNER-AUTHORIZED PRODUCT ADMISSION` with caption *This is not supervisor approval and not Randy confirmation.*
- Package fingerprint `195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269` and receipt fingerprint `45e8c2782ff40495e472bc0e6de3ba3be1610fdb974f88b7ffd12a754d031ebc` (distinct, cryptographically bound); forged self-consistent receipts are rejected.

### Strategies

Typed `E2StrategySemantics` for five IDs: `off`, `jsq`, `ingress_dla`, `dla`, `per_task_dla`. Summaries:

- `off`: strongest-link execution, no load-aware placement.
- `jsq`: least-busy without gate, per-substep common target.
- `ingress_dla`: strongest-link plus deadline-aware gate.
- `dla`: one common target per substep with deadline gate (not canonical per-task JSQ).
- `per_task_dla`: sequential per-task least-busy feasible-RSU with immediate reservation.

All: MAPPO frozen `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` does not observe current RSU load and does not choose execution RSU; `is_learned=False`, `is_deterministic=True`; described as Kubernetes-inspired, not Kubernetes deployment.

### E2b — offered-task deadline attainment (one draw descriptive, fleet seed 0)

| arm | value | standing |
| --- | --- | --- |
| off | 0.683619229 | RESEARCH-EVIDENCE FACT |
| jsq | 0.675681775 | RESEARCH-EVIDENCE FACT |
| ingress_dla | 0.715773211 | RESEARCH-EVIDENCE FACT |
| dla | 0.694939919 | RESEARCH-EVIDENCE FACT |

Metric `offered_task_deadline_attainment`, replication unit `fleet_draw`, evaluator seed 0, head `fe2ed4e9bd9043b19b96a5f179390db629b01ccb`, manifest `9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91`. No population inference.

### E2c — common-target dla minus ingress_dla (fleet seeds 1–4)

Per-seed: `-0.022097034972`, `-0.020519134179`, `-0.021447383092`, `-0.020825491499` (all negative). Declared mean `-0.021222260935`, 95% CI `[-0.02233525407, -0.0201092678]` (`two-sided Student-t 95% interval over fleet-draw differences`, df 3). Head `1a08d6e148a1e8c430da39c3d575eda3f8ea5929`, manifest `fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a`.

### E2d — per_task_dla minus ingress_dla (fleet seeds 1–4)

Per-seed: `0.004636732564`, `0.005867285642`, `0.005071796666`, `0.005509919752` (all positive). Declared mean `0.005271433656`, 95% CI `[0.004422143925, 0.006120723387]` (df 3). Head `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`, manifest `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740`. Secondary `per_task_dla` minus inherited common-target DLA: mean `0.026493694591`, CI `[0.026210763951, 0.026776625232]`; sd/se null for that secondary entry per source. Bounded direction statement: within four matched incident-hour fleet draws, changing granularity reversed the observed direction. Not universal.

### Accounting — E2d per_task_dla seed 1

`offered 13076234`, `admitted 10594205`, `rejected_total 2482029 (= offered - admitted, DERIVED)`, `forwarded 600885`, `deadline_success 9475948`. `rejected_total` is `DERIVED / INFERENCE FROM CONSERVATION`, not directly observed. Conservation `offered == admitted + rejected_total` holds.

Headline is offered denominator: `0.724669503 = 9475948 / 13076234`. Admitted-conditional diagnostic is `0.8944463506228169 = 9475948 / 10594205` — kept separate and labelled diagnostic only.

### Unavailable (never zero)

| field | value | reason contains |
| --- | --- | --- |
| gate_rejected | UNAVAILABLE (null) | gate vs capacity split not separately instrumented |
| capacity_rejected | UNAVAILABLE (null) | split unavailable without additional instrumentation |
| started | UNAVAILABLE (null) | started not independently instrumented |
| compute_completed | UNAVAILABLE (null) | not separately emitted |
| returned | UNAVAILABLE (null) | physical return not distinct from deadline_success |
| dropped | UNAVAILABLE (null) | cannot derive without compute_completed/returned split |

Validator and UI refuse converting these to `0` or claiming `started==admitted`.

### Provenance

- Actor SHA-256 `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`, trace `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`, base `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`, replication unit `fleet_draw`, evaluator seed `0`, VEC service `1x`, waiting-room `2.5x (6220/RSU)`, backhaul `0.0`, study hour `2024-03-15 20:00-21:00 Europe/London`, provisional fleet `uk2030`.

### Limitations and non-claims

Limitations (15) include: one Manchester incident hour; four matched provisional fleet draws; evaluator seed 0; fixed 1x compute; zero backhaul; inherited deadline gate; frozen vehicle actor; actor does not observe load / does not choose RSU; E2b one-draw descriptive; E2d reuses already-observed E2c controls / not independent held-out replication; tasks are accounting records, not independent replicates; no ordinary/free-flow control; physical return not instrumented.

Non-claims (14) include: actual Kubernetes deployment / cluster orchestration; autonomous infrastructure control; learned placement / learned RSU scheduler; MAPPO choosing RSU / observing load; Manchester-wide and population-wide performance; physical RSU deployment / physical result-return verification; universal JSQ/per_task_dla superiority; free-flow validation; independent held-out E2d replication; task-level statistical replication; zero-backhaul realism. The validator fails if any limitation substring or non-claim is removed or affirmed as a deployment claim.

All comparisons use `fleet_draw` as the replication unit. Individual tasks are never statistical replications.

## Deterministic export

In the Explorer's E2 mode, three downloads are offered: **Download JSON**, **Download CSV**, **Download Markdown** from `build_e2_research_exports(package, receipt) -> E2ResearchExportBundle`. They are byte-identical across rebuilds (two builds compared), contain no absolute workstation paths, no secrets, and no scientific timestamps, and they echo the exact numbers, provenance and missingness above. The validator compares the bundle file content to the live service output and fails on mismatch.

Run the strict validator locally:

```bash
python scripts/validate_e2_research_product.py
pytest tests/integration/test_e2_research_product_acceptance.py -v
```

Both must pass without launching research workloads.

## What this product does not claim

Not supervisor or Randy approved, not Kubernetes deployed, not a live traffic or Manchester-wide claim, not population inference, not task-level replication, not free-flow validated, not physically verified return, not a research approval — it re-presents the bounded frozen study through an admitted, typed, deterministic UI and export path.
