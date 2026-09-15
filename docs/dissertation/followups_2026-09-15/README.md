# Dissertation experiments 7–9 — completed 15 September 2026

Start with **[FINDINGS.md](FINDINGS.md)** for the three findings, actual runtimes and their implications for the hypothesis and research questions. **[RESULTS.md](RESULTS.md)** contains all ten declared comparisons.

## Contents

- `RESULTS_CHART.png` and `.svg`: all ten effects with confidence intervals adjusted across the ten comparisons.
- `ANALYSIS.json`, `CELL_RESULTS.csv`, `PAIRED_EFFECTS.csv`: exact numerical results. The cell table contains 72 new runs plus 32 reused controls.
- `PROTOCOL.md`, `GUARD_AMENDMENT.md`, `evidence/`: the design, reviewed source identity, qualification, independent audits and timing records.
- `runs/`: compact commands, logs, summaries, validation receipts and completion records for all new runs and short qualification attempts.
- `source/`: byte-identical source snapshots for inspection and recovery.
- `historical/`: compact historical records used to bind the reused controls.
- `PACKET_MANIFEST.json`: original paths, copied paths, sizes and SHA-256 hashes for 720 copied evidence/source files.
- `plot_results.py` and `plot-requirements.txt`: chart rendering code and its separate plotting environment requirements.

## Raw data and portability

This compact packet contains tables, source snapshots and audit records. The large raw NPZ arrays remain at:

`/Users/akashx/Downloads/diss_mat/traffictwin-followups-raw-2026-09-15`

The `Raw experiment outputs` and `Live evidence` entries are local shortcuts. The ZIP omits those shortcuts and the large raw arrays. Original absolute paths remain in the scientific receipts; the packet manifest maps them to byte-identical compact copies. Re-executing the experiment requires its recorded runtime, inputs and raw-data environment; these source snapshots are not a relocatable runtime installation.

The experiments use the existing eight seed pairs. The second actor shares the original training seed. The findings document gives the exact interpretation boundaries.
