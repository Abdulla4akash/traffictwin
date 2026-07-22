# One-Click VEC Execution and Automatic Import

Status: implemented `VEC-10` extension (`vec-execute-and-import-1.0`, ADR-052).

One explicit action runs the complete request-specific preflight, executes the exact audited
evaluator through the accepted VEC-07 runner, revalidates every published byte, verifies both
external repositories and the raw trace are unchanged, and imports one immutable source-specific
record into the configured TrafficTwin registry. Nothing here is a second evaluator, a background
queue, a general launcher, or a scientific claim.

Library: `traffictwin.integration.vec_orchestration`
Contract: `docs/reference/generated/vec_orchestration_contract.json`

## Closed presets

Requests are never typed in. The workflow accepts exactly two repository-defined presets over the
reviewed weekend trace (`traces/trace_we_fullrsu.npz`) and the audited UK-2030 Model-C actor:

| Preset | Steps | What it proves | What it never proves |
|---|---:|---|---|
| `smoke_two_step` | 2 | Safe structural execution of the pinned code path | Reproduction, performance, or any dissertation evidence |
| `full_reproduction` | 32,400 | The exact accepted VEC-08 protocol-seed run completed locally | Graded reproduction (needs separate VEC-08 verification); anything about `_s102` best-of-seeds rows |

The full preset is a long foreground operation and requires explicit confirmation. Workload
numbers shown before execution are factual request properties, not runtime promises.

## UI: click-by-click

1. Open **VEC Reproduction Workbench** and inspect the pinned repositories (section 1).
2. In **"2. One-click controlled execution"**, choose a preset and review its factual workload
   and limitation text.
3. Keep the default audited input root, enter a **new** output directory, and confirm the active
   registry path (pre-filled from the configured registry, for example the demo launcher's
   `TRAFFICTWIN_REGISTRY_PATH`).
4. For `full_reproduction`, tick the explicit long-run confirmation.
5. Click **Validate, Run and Import** — the single final action. The button stays disabled while
   any input is missing or unconfirmed.
6. Watch the foreground status, then inspect the stage table, receipt/output/import fingerprints,
   the output inventory, and the limitations. The registry run id links the record to the Run
   Overview page.

A failed, rejected, timed-out, cancelled, or mutated execution shows its findings and imports
nothing. Closing or restarting the app never creates or recovers a job queue.

## CLI

```bash
uv run traffictwin integration vec execute-and-import \
  --preset smoke_two_step \
  --input-root ../external/tos-data \
  --vec-repo ../external/vec_env \
  --tos-data-repo ../external/tos-data \
  --output ./local-evidence/oneclick-smoke \
  --registry .demo/registry.sqlite
```

The command prints the preflight, execution, validation, and import stages and returns non-zero
on any non-imported terminal state. `--preset full_reproduction` additionally requires
`--confirm-full-run`. A published result can be re-validated and re-imported later:

```bash
uv run traffictwin integration vec import-result \
  --result-dir ./local-evidence/oneclick-smoke \
  --registry .demo/registry.sqlite \
  --vec-repo ../external/vec_env \
  --tos-data-repo ../external/tos-data
```

## What automatic import means

Only a `completed` VEC-07 receipt whose request matches a preset fingerprint exactly is
admissible. Before any registry write, the workflow re-reads the receipt, re-hashes every listed
output byte-for-byte, and (with repository paths available) verifies the current worktrees match
the receipt's verified post-run state and that the raw trace hash is unchanged. The imported
record binds:

- the typed request and request fingerprint;
- the preflight fingerprint (taken from the receipt);
- the receipt file SHA-256 and receipt fingerprint;
- the output fingerprint plus per-file hashes and sizes;
- the exact audited `vec_env` and `tos-data` commits;
- runtime evidence, the preset, its evidence grade, timestamps, and the importer version.

Output files are preserved unchanged in the read-only published directory; the registry stores
metadata and the typed record via the existing `register_bundle_import` conventions — no ad hoc
SQLite and no schema migration.

## Idempotency and conflicts

The import identity is `vec-exec:<receipt fingerprint>` with a stable record fingerprint that
excludes only the import wall-clock time. Re-importing the same published result is idempotent
(`import_idempotent: True`; nothing is rewritten). A conflicting record under the same identity
fails visibly with `RegistryConflictError`. Executing a preset again produces a new receipt and
therefore a new, separate record.

## Failure recovery

Nothing needs cleanup on failure: unsuccessful executions publish no outputs, and refused imports
write nothing. Re-run the one-click action with a fresh output directory, or re-import an intact
published result with `import-result`. The workflow receipt records which stage refused and why.

## Scientific and publication limitations

- Scientific admission is explicitly `unavailable` with standing reason codes: the accepted
  VEC-09 admission binds the audited source run (`fcd_s102_uk2030_we_fs0`), not local executions.
- Deadline success is never physical completion; action selection is never confirmed transfer;
  aggregate energy is never per-task energy; smoke output is never a scientific finding. These
  are literal fields in the record and cannot be represented otherwise.
- The full-run preset uses the protocol seed and stays distinct from `_s102` best-of-seeds
  evidence; the accepted CPU/JAX tolerance is not generalised to other platforms, policies, or
  scenarios.
- Import grants no publication permission; VEC-11 packaging remains the only publication path.

## Inspecting imported execution records

- **VEC Reproduction Workbench**: expand **Imported VEC execution records** to inspect the
  persisted preset, evidence grade, admission/publication states, fingerprints, pinned commits,
  output inventory, and limitations after the current Streamlit session or app process ends.
- **Experiment Manager**: the registry run appears as `vec:exec:<fingerprint16>` with status
  `completed`, zero scientific metrics, and the pinned `vec_env` commit. Run Overview remains a
  canonical-bundle analysis page and deliberately does not calculate cards for this structural
  execution record.
- **Registry payloads**: the full typed `VecExecutionImportRecord` is stored as the bundle-import
  manifest under bundle id `vec-exec:<receipt fingerprint>`.
- **On disk**: the published output directory keeps `run.json`, `per-step.npz`, `per-task.npz`,
  bounded logs, and `execution_receipt.json`, all read-only; section 4 of the workbench inspects
  the receipt.

## Related documents

- [VEC-07 evaluator runner](vec_evaluator_runner.md)
- [VEC-10 CLI and UI interface](vec_interface.md)
- [VEC-08 reproduction verification](vec_reproduction_verification.md)
- [ADR-052](../decisions/ADR-052-one-click-vec-execute-and-import.md)
