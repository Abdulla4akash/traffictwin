# Campaign offline verification ("campaign doctor")

An examiner reading a campaign's results should not have to take the campaign's
own receipt on trust. This is the check that re-derives the receipt's claims from
the artifacts on disk and reports every place the two disagree.

- Library: `src/traffictwin/integration/vec_campaign/verify.py`
- Command line: `scripts/verify_campaign.py`
- Tests: `tests/unit/test_vec_campaign_verify.py`

## What it checks

| Check | What is re-derived | What a mismatch means |
| --- | --- | --- |
| `design_fingerprint` | the supplied design is re-fingerprinted and compared to `campaign_receipt.json`, together with the experiment id and the seed cohort | the receipt was written by a different run matrix than the one supplied; the two cannot be read as one experiment |
| `cell_grid` | every (arm, seed) cell the design declares is matched to exactly one recorded outcome, and each cell's run id and request fingerprint are recomposed from the design's controls | a declared cell is missing, an undeclared cell appears, or a recorded cell was not produced by the design's controls |
| `cell_receipts` | each executed cell's `execution_receipt.json` is re-read; its request fingerprint, run id, terminal status, and its own fingerprint are re-compared to the campaign cell | a cell directory holds a receipt from a different run, or the receipt bytes changed after the campaign recorded their digest |
| `output_hashes` | every published output file named by an execution receipt is re-hashed and re-sized on disk | a published payload changed after execution |
| `registry_admission` | every admitted cell is looked up under the identity the admission policy derives from its receipt (`vec:fresh:<receipt[:16]>`), with its run's experiment, arm, and pairing seed, its metric collection, and the registered experiment plan | an admitted cell has no registry evidence, or the registry evidence describes a different cell |
| `approval` | the approval block is compared to the design's, and the approved predeclaration is re-hashed against the document on disk | the predeclaration changed after it was approved, or the receipt records a different approval than the design carries |

Findings are typed and carry a severity. A **failure** contradicts the recorded
evidence and forces `FAIL`. A **warning** means evidence is absent or could not
be reached — a missing cell directory, a deleted payload, an unreachable
registry — and is always reported rather than passed over. Checks the caller
declined to run (no registry supplied, `--skip-output-hashes`) are listed in
`checks_not_run`, so a report never lets a skipped check read as a passed one.

## What a PASS does and does not say

A PASS says the artifacts agree with each other and with the design they claim
to implement. It is not a scientific finding, an accepted result, a reproduction,
or supervisor approval, and it says nothing about whether the design was a good
one or what the numbers mean. In particular:

- **Re-hashing is not reproduction.** It proves the published bytes are unchanged
  since the receipt was written. The evaluator is never re-run and no numerical
  equivalence is established.
- **The design is supplied by the caller.** Verification proves the artifacts
  match *that* design. It cannot prove the supplied design is the one a person
  approved — that is what the predeclaration digest check is for, and that check
  binds bytes, not intent.
- **A halted campaign can verify cleanly.** If a campaign halted on failure and
  its receipt records the halt faithfully, the artifacts agree and the verdict is
  PASS. PASS is never a statement that the campaign succeeded.

## Read-only by construction

There is no repair path, no `--fix`, no reconciliation, and no default output
location. The campaign directory, the published payloads, and the predeclaration
are read and never modified; `repairs_performed` and `writes_performed` are
type-level `False` in every report. An exhibit is written only where
`--markdown-out` or `--json-out` explicitly names a path, and an existing file
there is kept unless `--overwrite` is passed.

One honest caveat: the public `Registry` read methods apply their own idempotent
schema migration when they open a database, exactly as any other reader does. No
run, metric collection, experiment, annotation, bundle record, or evidence pack
is ever inserted, updated, or deleted.

The design constructor is *imported*, which executes the module's top level.
Pass only a trusted repository script — never a Python file that arrived with the
campaign directory being verified.

## Usage

```bash
uv run python scripts/verify_campaign.py \
    --design-module scripts/<campaign_script>.py \
    --design-attr <design_constructor> \
    --campaign-dir <campaign output directory> \
    --registry <registry database> \
    --markdown-out docs/evaluation/<exhibit>.md
```

Exit codes: `0` every check passed, `1` at least one check failed, `2`
verification could not be performed at all (missing campaign receipt, design
module that will not import). The middle code is the informative one — it means
the artifacts contradict each other, not that the tool broke.

Re-hashing a full campaign reads every published payload, which for a real
capacity campaign is on the order of a hundred megabytes per cell. Do not run it
against a campaign directory that is currently executing; `--skip-output-hashes`
answers receipt-structure questions without the I/O.
