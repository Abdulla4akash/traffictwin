# Capacity-study figure provenance

Status: **exploratory, owner_approved_candidate, descriptive non-causal**. Owner-approved-candidate is not supervisor
approval, not validation, and not a causal claim.

## Source

| Field | Value |
|---|---|
| Source analysis file | `campaign_analysis.json` |
| Source SHA-256 | `7507639a41ad8b287e5a6f4103ba3739a323adf5382a772d29e13849e9421ac9` |
| Experiment | `vec-capacity-squeeze-pilot` |
| Design fingerprint | `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90` |
| Campaign status | `completed` |
| Analysis method version | `vec-campaign-analysis-1.0` |
| Analysis generated at | `2026-07-27T09:31:46.676341+00:00` |
| Primary metric | `tos.task.deadline_success.rate` |
| Baseline arm | `cap-2.5` |
| Latency metric rendered | `task.latency.mean_ms` |
| Capacity arms | `cap-2.5`, `cap-1.5`, `cap-1.0`, `cap-0.75` |
| Fleet seeds | `0`, `1`, `2` |
| Admitted collections | 12 |

The analysis file was read and never written. No registry, campaign service, or
live campaign directory is opened by the generator.

## Published figures

Each row is one projection rendered twice from the same fingerprinted payload, so
the table and the figure cannot disagree.

| Figure | Projection fingerprint | File | SHA-256 | Bytes |
|---|---|---|---|---|
| `capacity_latency_by_seed` | `fec39a3f4d19361c3f77f892f10c2439b8f548bcc8856e4db80eca25d80adf7f` | `capacity_latency_by_seed.tex` | `62b7b0f7f520fc07ef987b7aa2d8969f472d8bbd8c86404ba1c7b9afba69e86d` | 923 |
| `capacity_latency_by_seed` | `fec39a3f4d19361c3f77f892f10c2439b8f548bcc8856e4db80eca25d80adf7f` | `capacity_latency_by_seed.svg` | `df15c2c80af3fea7f128e4517c10a3aaabda27b86a324fa3c416e2da8087caab` | 4985 |
| `capacity_deadline_success_by_seed` | `f20101c8be7d6a50db6e16548f0a935814718411dd352903de254408d918c67b` | `capacity_deadline_success_by_seed.tex` | `3eda25101b7d2295184be9df1b83ef71791ca4944ef7cd304072436e64b0900a` | 1047 |
| `capacity_deadline_success_by_seed` | `f20101c8be7d6a50db6e16548f0a935814718411dd352903de254408d918c67b` | `capacity_deadline_success_by_seed.svg` | `a896472a4f29e6b641622742092e214b00b3d0dc0f5fd08e0a7d89b584a021a0` | 5008 |
| `capacity_deadline_success_paired_differences` | `fa4f43f1afa28fe7b671b3ad781de8529da79bc4c85f7aa53128965ed405c001` | `capacity_deadline_success_paired_differences.tex` | `25153fed164d29928977dc9a29cf8743c75bebb344f7d7d3636050142c95b34a` | 1014 |
| `capacity_deadline_success_paired_differences` | `fa4f43f1afa28fe7b671b3ad781de8529da79bc4c85f7aa53128965ed405c001` | `capacity_deadline_success_paired_differences.svg` | `bc80167b5d16c5cc882435c52d7957e7577fb88334cd25ba098ae8237878ca3c` | 2068 |
| `capacity_offload_invariance` | `b5432ec8080a08dbd6cec0bb9712217d9b1289b726595bb358274497a8a8a3b3` | `capacity_offload_invariance.tex` | `56fa553ed5c4821450f0dd97f651cd7ad48364fc53734acad39681d859a776c5` | 2354 |
| `capacity_offload_invariance` | `b5432ec8080a08dbd6cec0bb9712217d9b1289b726595bb358274497a8a8a3b3` | `capacity_offload_invariance.svg` | `a03895828e5347b2b1c398afa0679e6da83737adb29978b69ad6990a3d466b9f` | 5209 |

## How to read these figures

- **Every number is a recorded value.** The generator selects and lays out values
  the completed analysis and the accepted mechanism report already computed. It
  derives no metric, no difference, and no summary of its own.
- **Table cells carry full round-trip precision** rather than a rounded display, so
  the invariance column can be checked against the digits beside it. Two values that
  print identically in the table are identical in the recorded bytes.
- **The bars are a bar series, not a polyline.** The accepted renderer draws
  horizontal bars on a shared signed linear scale, so a per-seed latency curve
  appears as one contiguous run of bars per seed, in capacity order. The companion
  table holds the exact values the curve is drawn from.
- **The deadline-success chart is zero-anchored** because the accepted scale always
  is. That is deliberate: at true size the band is visibly flat, which is the
  finding. `capacity_deadline_success_paired_differences` publishes the paired differences the analysis
  recorded, which is where the within-band structure can be read without magnifying
  a difference into an apparent effect.
- **Invariance categories render in the renderer's neutral colour.** Its categorical
  palette is keyed to diagnostic-rule statuses, which these are not, so the
  categories are distinguished by their text rather than by a borrowed colour.

## Limitations, copied from the analysis

- Exploratory owner-approved-candidate evidence only; no confirmatory claim, no significance claim, and no scientific acceptance is made by this analysis.
- The comparisons share one baseline without multiplicity correction; the predeclaration reserves any corrected claim for the separately signed confirmatory protocol on the held-out seeds.
- Deadline success is never physical completion; reconstructed evaluator behaviour is never an observed journey; results describe one audited policy on one reviewed trace with one fleet preset.
- Interval and randomisation outputs are reported verbatim as STA-01 diagnostics of the exploratory pilot, not as accepted thresholds.

## Regenerating

```bash
uv run python scripts/generate_capacity_figures.py \
  <path-to-campaign_analysis.json> --overwrite
```

The input path has no default. Regeneration on unchanged input rewrites identical
bytes, so a regenerated figure never appears as commit churn.
