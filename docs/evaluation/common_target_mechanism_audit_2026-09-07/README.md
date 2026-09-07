# Completed common-target five-RSU mechanism audit

**Status: complete and archived in the private repository.** This is the
five-RSU audit of the morning common-target runs, separate from the earlier
100 ms state-delay audit. Its findings are integrated into the
[dissertation results section](../../dissertation/vec_results_integration_2026-09-07.md#why-the-same-five-rsus-receive-work).

Across four existing draws, every recorded end-of-second RSU queue was empty,
and all **179,427 observable target selections** followed task substep `k` →
RSU `k`. The combination of five common-target decisions, repeated empty starts,
positive admitted work and lowest-index tie-breaking explains the fixed
RSU 0–4 identities under the audited conditions. Reconstruction showed that
all **511,684 gate-rejected tasks** had at least five other idle RSUs with spare
admission capacity. This does not establish that all those tasks would meet
deadlines after redistribution or explain the entire performance contrast.

## Evidence

- [Complete report: observations, deductions, unavailable fields and limits](evidence/REPORT.md)
- [Machine-readable findings and raw-input hashes](evidence/audit_results.json)
- [All 43,200 per-second target records](evidence/per_second_targets.csv.gz)
- [Seed-by-substep summary](evidence/per_substep_summary.csv)
- [Worked recorded seconds](evidence/worked_examples.json)
- [Analysis source actually executed](evidence/audit.py)
- [Exported-record verification](evidence/verification.json)
- [Archive inventory](ARCHIVE_INVENTORY.json)
- [Archive checksum ledger](SHA256SUMS)

The nine files under `evidence/` are byte-identical copies of the completed
local audit package, including its original checksum ledger. Its original
README/report statements that the audit was local and that `f17298e` was
unchanged describe the state at audit completion. This index records the later
archiving and results integration. The historical evidence archive at
`f17298e` is preserved; no original scientific result or raw array was changed.

The underlying raw arrays and actor/traffic inputs remain in their original
local locations. Archiving this compact audit does not create a complete remote
backup of them. The original analysis expects the sibling study-directory
layout described in its [preserved README](evidence/README.md); the copy here
is for inspection, not execution inside the repository.

## Separate optional extension

The [two-prefix rotating tie-break protocol](TIEBREAK_PREFIX_PROPOSAL.md) is
documented separately. It is **proposed, not implemented or executed**. Neither
the completed audit nor this archival integration launches a simulation.
The proposal does not block completion of the dissertation.

This integration checks copied-file identity, checksum coverage, exported-record
arithmetic and document links. It does not claim another raw-array reanalysis,
fresh figure regeneration or independent scientific review.
