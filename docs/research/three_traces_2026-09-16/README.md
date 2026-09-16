# Three Manchester traces — authorised study

**Status:** all 18 qualification attempts passed; the 120 authorised full
cells are running. See [live status](evidence/LIVE_STATUS.json) for the latest
validated counts. Full execution started at 00:06:39 UTC on 16 September 2026.
The [execution seal](evidence/EXECUTION_SEAL.json) predates full outcomes.

- [Owner task](OWNER_TASK.md): original requested design and authority.
- [Sealed protocol](PROTOCOL.md): selected scenarios, fixed controls,
  statistical families and approved clarification.
- [Source compatibility audit](SOURCE_COMPATIBILITY.md): exact blockers to
  literal unchanged reuse and the approved bounded amendment.
- [Trace inventory](TRACE_INVENTORY.json): all eight files, per-array/file
  hashes, remote-main identity, entry conventions and morning differences.
- [Configuration](CONFIG.json): exact planned traces, arms, blocks and budgets.
- [Runtime preflight](RUNTIME_PREFLIGHT.json): pinned environment and input/source
  checks; does not launch an evaluator.
- [Scientific source identities](SCIENTIFIC_SOURCE_IDENTITY.json): all five
  requested scientific files are byte-identical to the requested base.
- [Work status](WORK_STATUS.json): execution state. The raw inventory will be
  completed after all workers finish and the independent arithmetic audit passes.
- [Source review](evidence/SOURCE_REVIEW.json): approval of the exact frozen
  configuration source `2cec1eee4022a64bc5f80b049eed0471ff4a03bf`.

## Approved owner amendment

The supplied prompt conflates cross-arm exogenous matching with same-arm
compatibility. The current validator also fixes morning dimensions and
requires an entry channel, while PM/event lack one. The owner approved the
configuration parameterisation and qualification contract in
[OWNER_AMENDMENT.md](OWNER_AMENDMENT.md) before evaluator launches. The archived
incident round-robin point is unavailable; E2c/E2d did not include that arm.

## Inventory reproduction

`inventory.py` reads the local candidate NPZ files and verifies them against
the previously fetched vec_env `github/main` tree. Run it with the specified
venv Python in a fresh output directory/check-out; it refuses to overwrite
`TRACE_INVENTORY.json`. No simulation, input mutation or network call occurs.

The original morning trace has not been rerun. Existing studies, manuscripts,
raw inputs and all five protected scientific files remain unchanged.
