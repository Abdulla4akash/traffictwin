# Execution timing

Clock elapsed time below includes host sleep. The elapsed-hour values in the sealed analysis output and RESULTS.md are the runner monotonic timers; those values are preserved unchanged.

| Trace | Clock elapsed (h) | Runner timer (h) | Difference (h) |
|---|---:|---:|---:|
| we | 9.571310 | 7.334248 | 2.237062 |
| wd_pm | 9.270222 | 7.033164 | 2.237058 |
| ev | 9.266075 | 7.029017 | 2.237058 |

See [timestamp-derived timing](evidence/EXECUTION_TIMING.json) and the compact FULL_STARTED.json / COMPLETE.json receipts for exact values.

The Mac entered low-power sleep at 03:10:01 UTC and woke on AC power at 05:22:15 UTC on 16 September 2026 (7,934 seconds). The same attempts resumed; none were retried. See the [operational interruption record](evidence/RUNTIME_INTERRUPTION.json).
