# Completed VEC follow-ups — private evidence archive

Archived 7 September 2026. **The twelve-run morning replication is complete:**
common-target < ingress < sequential per-task placement in all four new fleet
draws. Mean per-task minus ingress attainment was **+3.89852 percentage points**,
with a simultaneous 95% family interval of **[+2.67129, +5.12575] pp**.
The inspected pilot is excluded from primary inference.

Start with the [integrated dissertation results](../../dissertation/vec_results_integration_2026-09-07.md),
[evidence map](../../dissertation/vec_evidence_map_2026-09-07.md), or
[replication publication summary](generalisation-replication-2026-09-07/PUBLICATION_SUMMARY.md).

## Completed studies and their standing

| Evidence package | Completed work | Standing |
|---|---|---|
| [Historical E0–E2d](historical_e0_e2d/README.md) | Original accounting, capacity, placement/admission and dispatch studies | Frozen historical reporting copy, with original scientific identities preserved. |
| [Incident state-delay pilot](state-delay-pilot-2026-09-07/RESULTS.md) | Five full cells: ingress, fresh, 100/500/1,000 ms | One draw, descriptive. Read the [empty-report mechanism audit](state-delay-pilot-2026-09-07/mechanism_audit.json) before interpreting 100 ms equality. |
| [Forwarding sensitivity](forwarding-sensitivity-2026-09-07/RESULTS.md) | 0/1/2.5/5/10 ms costs; four direct short qualification probes; reused full records | One draw, qualified fixed-overhead counterfactual; zero new full positive-cost simulations. |
| [Morning pilot](generalisation-pilot-2026-09-07/RESULTS.md) | Two full cells, seed 1 | Exploratory and already inspected before replication. |
| [Morning replication](generalisation-replication-2026-09-07/RESULTS.md) | Twelve full cells and twelve preflight probes; seeds 0, 2, 3, 4 × three arms | Locally prespecified paired fleet-draw analysis; pilot separate. |

These are E2d-derived follow-ups, not execution of the separate held E3 Dynamic
Resource V2 campaign. Scaling was off in the new studies.

## What is preserved

The [inventory](ARCHIVE_INVENTORY.json) records **386 byte-identical copied
files**: compact tables, reports, original protocols/manifests, command and
validation records, logs, analysis/runner source and figures. It also lists
**87 local NPZ files, totalling 1,762,464,782 bytes**, with their original paths,
sizes and SHA-256 hashes. The large arrays are not included in Git. Virtual
environments, caches and ephemeral runner locks are excluded.

The historical public reporting copy is pinned to
`e6faab86ddc6fd1097e04db0f4cd5e3cfb1f055e` of
`Abdulla4akash/traffictwin-vec-research`. It retains the distinction between
public-sanitized derivatives and original private scientific records.
The new evaluator is pinned to
`908bd10f86542de94fc38af90dd56c2ccc08cf9b` of
`Abdulla4akash/vec_env`; selected source files, the
[timing contract](frozen_evaluator/docs/RSU_STATE_DELAY.md) and
[compatibility receipt](frozen_evaluator/validation/evidence/rsu_state_delay_compatibility_v1.json)
are copied under `frozen_evaluator/`.

The copied studies are historical artifacts and are **not rewritten for this
archive**. Their absolute paths, earlier forecasts, `NEXT_STEPS.md`, initial
test failure and subsequent correction, old status descriptions and original
checksum ledgers retain their original meaning. For current completion, use
this index and the terminal receipts. Historical future-work wording does not
mean the completed forwarding or replication work still needs running.

The scoped Git attributes preserve original line endings and generated
whitespace inside the six copied evidence directories. They do not exempt the
new integration prose or verification utilities from normal whitespace checks.

## Verify and reuse

From this directory, using Python 3.11 or later:

```sh
python3 verify_archive.py
python3 verify_archive.py --check-local-arrays
```

The first command verifies copied-file identity and the archive ledger. The
second additionally requires all inventoried NPZ files at their original local
paths and verifies their bytes. On the owner's Mac, these files remain under
the four dated study directories in `/Users/akashx/Downloads/diss_mat/`.
`SHA256SUMS` at this archive root covers repository contents; nested original
ledgers may reference arrays deliberately omitted from Git.

Compact statistics can be checked without the arrays using the recorded
SciPy environment and the historical verifier:

```sh
python3 historical_e0_e2d/analysis/verify_statistics.py
python3 verify_compact_results.py
```

The second command checks the new tables against saved run summaries, task
accounting, paired input hashes, pilot separation and draw-level confidence
intervals. It reads compact records only and does not launch an evaluator.

For full task-level reanalysis, use the original study directories or restore
the inventoried arrays and exact input artifacts. The archived runners retain
their original Mac paths and are evidence copies, not portable launchers.
Do not run them inside this archive. An approved reproduction should use a new
output directory, the pinned evaluator/runtime and the recorded manifest and
commands. Reproduction on a different backend needs its own agreement checks.

The repository copy is a compact evidence archive, not a complete remote backup
of the large arrays, actor or traffic inputs. It does not make the new evidence
public. The [supervisor update](../../correspondence/sandra_randy_vec_followup_update_draft_2026-09-07.md)
is a draft only.
