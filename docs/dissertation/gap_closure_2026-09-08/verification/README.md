# Relocatable verification and retrospective diagnostics

This directory is a verification package, not a simulator. Inputs copied under `sources/` are byte-identical compact records or source snapshots; `SOURCE_BINDINGS.json` identifies their original repositories, revisions and SHA-256 values. No historical files are edited. NumPy/SciPy are needed for raw/summary arithmetic; the reference kernel itself uses Python's standard library. Optional production comparison requires JAX. No actor, SUMO or campaign runner is loaded.

## Field contract established before raw calculations (8 September 2026)

- Offered: `task_active`, emitted from `ks > substep` by the evaluator. Inactive padded slots are excluded. `task_type` indexes source deadlines `[100,500,100]` milliseconds; it is not a saved deadline measurement.
- Final V2I admission: `task_v2i_admitted`, emitted from the actual enqueue predicate `active & (actions == 1) & rsu_ok`. `task_execution_rsu >= 0` is an independently stored expression of that same predicate, not independent physics evidence or a departure event.
- Non-V2I admission: active local/V2V attempts excluding outcome codes 5/6/8. These rejection predicates are computed from local/V2V admission and radio masks before the deadline flag; using this partition does not infer admission from success. There is no separately saved local/V2V execution mask.
- Declared outcomes: code 0 inactive, 1 admitted/met, 2 admitted/miss, 3 backlog-gate rejection, 4 RSU-capacity rejection, 5 local-queue rejection, 6 V2V-queue rejection, 7 V2I unavailable, 8 V2V unavailable. The source gives gate failure precedence. For common-target, its final gate-failure calculation need not equal the retained third admission mask on arbitrary inputs; therefore codes 1/2 alone are not treated as independent V2I admission evidence.
- Deadline flag: `task_met`, emitted from `dmet & active`; `dmet` tests mapped latency `<= deadline`. This flag and latency are dependent measurements. Code 1 uses that flag only after rejection classification. The audit tests their agreement, not independent physical accuracy.
- Latency: `task_lat_ms = latency * active`. Source maps raw latency >= 1e8 ms to 10 times the task deadline. A finite rejected latency different from 10D is a non-penalty discrepancy; equality to 10D is consistent with penalty mapping but cannot exclude a coincident finite value. Finiteness alone does not imply false success.
- Summary `n_admitted` subtracts the rejection counters from offered; `completion` sums deadline flags. The audit reconciles these with the saved task records and separately checks actual V2I admission against declared categories. These checks are not independent validations of the physical model.

Legacy E0/E1 at `0f01f4d` and E2 at `e11f444` use refined `rsu_ok` for enqueue and rejection but earlier `best_rsu_ok` for off-path scoring. E2b reuses E2 off; its new ingress arm is at `0e5ed2f`. Off-path capacity rejection can retain non-penalty latency. Passing the corrected mask would also change V2I transmission energy; energy changes state of charge and later actor observations. A fixed-history admission-consistent score is therefore not a corrected full simulation. The September gate-enabled path passes refined admission into scoring and is audited separately.

## Historical availability update — 8 September 2026

E0/E1/E2 original raw outputs unavailable; deletion reported by the author; no known backup. No further broad filesystem searches are made. This does not imply that the experiments never ran or that no copy could exist anywhere. Surviving manifests, summaries, figures, sources and validation receipts remain unchanged. Their arithmetic and recorded checks remain inspectable, but fresh historical task-level checks and a fixed-history rescore are **not assessable from available records**. E2b's reused E2 off cell inherits that availability limitation. Availability of other E2b/E2c/E2d original arrays is not established here; no deletion is inferred for them. September records are not replacements for any of these historical records.

All 87 September NPZ entries are checked against the archived inventory before any analysis. The 19 full runs selected for fresh task audits are the twelve morning primary cells, two excluded morning pilot cells and five incident state-delay pilot cells. Qualification/preflight arrays receive integrity checks only. Runs are loaded one at a time; inputs remain untouched. Small packed masks for later joins are temporary derived caches, not raw backups. No raw arrays are included in this package.

## Run from any directory

Use an analysis-only Python environment with `requirements-analysis.txt` installed; no scientific runtime changes are needed. Python 3.13.5, NumPy 2.5.3 and SciPy 1.18.1 were used for this revision. The scalar kernel uses the standard library. Commands below are examples with explicit paths, not assumptions about the examiner's machine.

```sh
python /path/to/verification/verify.py --output /tmp/traffictwin-check
python /path/to/verification/verify.py --output /tmp/traffictwin-raw-check --raw-root /path/to/evidence-root
```

The first command checks all bound compact/source files, regenerates `CENTRAL_TABLES.csv`/`ARITHMETIC.json`, extracts historical receipt coverage and reruns the bounded kernel. The second additionally requires all 87 files listed in `RAW_INPUTS.json` beneath the supplied root, authenticates them before analysis, audits the 19 full cells and recreates all 23 eligible matched transitions. Missing or mismatched files produce a nonzero exit and an explicit diagnostic, never a zero-discrepancy result. Temporary packed masks are removed when the entry point finishes.

Optionally add `--production-python /path/to/jax-python` to compare the frozen helpers. This was checked using the existing read-only Python 3.11.15/JAX 0.4.30/NumPy 1.26.4 environment; its packages were not changed. The full evaluator is not imported. Output `VERIFY.json` states coverage for that invocation; existing individual result files document separately executed checks. A compact-only invocation does not claim raw checks were repeated.

`results/RAW_AUDIT.json` gives each full run's coverage, rejection counts, discrepancies, summary reconciliation and zero/nonzero fixed-history adjustment. `HISTORICAL_COVERAGE.json` contains 30 receipt rows, including smoke runs and explicitly identified reuse; those rows are not 30 independent replications. `OUTCOME_TRANSITIONS.json` retains every eligible pair, including unchanged and adverse transitions. `KERNEL_RESULTS.json` retains all explicit inputs, intermediate masks, final offsets and minimisation trials; `PRODUCTION_AGREEMENT.json` records the returned-field comparison. The finite suite is a diagnostic, not a performance benchmark.

## Preservation and access proposal (unexecuted)

Proposed destination: a restricted **University-managed research-storage endpoint**, in a dated `TrafficTwin/evidence/2026-09-08/` directory, with author/supervisor administration and an agreed examiner read-access route. The actual approved endpoint, owner, permissions and retention period require author confirmation; no functioning backup destination is claimed. An approved encrypted external drive stored separately would be another author decision, not a second folder on this disk. No transfer or upload is executed here.

The proposed package should retain the 87 authenticated September arrays (1,762,464,782 bytes), their inventory, the compact/source package, and separately authorised actor/trace/runtime inputs. Verify destination hashes after copying and test access from the examiner's account. Current local presence is not off-machine preservation; a checksum cannot recover deleted data. Historical E0/E1/E2 raw files cannot be added from the available records. Any later simulation would be a separately identified reproduction attempt, never recovery of those original outputs.
