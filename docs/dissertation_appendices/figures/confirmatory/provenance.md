# Capacity-study figure provenance

Status: **exploratory, owner_approved_candidate, descriptive non-causal**. Owner-approved-candidate is not supervisor
approval, not validation, and not a causal claim.

## Source

| Field | Value |
|---|---|
| Source analysis file | `campaign_analysis.json` |
| Source SHA-256 | `a62e3e50f8d3f3124a8fbb4bfa9a3a48efb3eb2d400fcda90b5a722e318ff8da` |
| Experiment | `vec-capacity-confirmatory` |
| Design fingerprint | `f289db31ce28b6361f91911485c36483b068fdee1ed73aa1d4ef0a8b57bc1754` |
| Campaign status | `completed` |
| Analysis method version | `vec-campaign-analysis-1.0` |
| Analysis generated at | `2026-07-27T23:33:37.258443+00:00` |
| Primary metric | `task.latency.mean_ms` |
| Baseline arm | `cap-2.5` |
| Latency metric rendered | `task.latency.mean_ms` |
| Capacity arms | `cap-2.5`, `cap-0.75` |
| Fleet seeds | `10`, `11`, `12`, `13`, `14` |
| Admitted collections | 10 |

The analysis file was read and never written. No registry, campaign service, or
live campaign directory is opened by the generator.

## Published figures

Each row is one projection rendered twice from the same fingerprinted payload, so
the table and the figure cannot disagree.

| Figure | Projection fingerprint | File | SHA-256 | Bytes |
|---|---|---|---|---|
| `capacity_latency_by_seed` | `af0dc67a49a48bf7625205b187e6d8ba99b5ec3023fc51f3cecd34512d0f7644` | `capacity_latency_by_seed.tex` | `9b7079888188a3be9abc88b2c08606b11cdbb7c179e4e5fad115d5290564d35a` | 872 |
| `capacity_latency_by_seed` | `af0dc67a49a48bf7625205b187e6d8ba99b5ec3023fc51f3cecd34512d0f7644` | `capacity_latency_by_seed.svg` | `6c1339b7f67176b0ed959723d2adfa152c5ac1e263cba92d3f05f2fc1c4404f2` | 4348 |
| `capacity_deadline_success_by_seed` | `6bfb8004f799b30cc2bc27aaa3976bd84b8f94389f9ebdb838257defe20ff7b3` | `capacity_deadline_success_by_seed.tex` | `afa77f67aa659f9862d3116aeec2bacd96a296f629bf365ce48481477819e1ef` | 994 |
| `capacity_deadline_success_by_seed` | `6bfb8004f799b30cc2bc27aaa3976bd84b8f94389f9ebdb838257defe20ff7b3` | `capacity_deadline_success_by_seed.svg` | `c8e0eb00503a09fdde24f9bebd18ca3123fa84ef4adc6db0efef954d43072bac` | 4356 |
| `capacity_deadline_success_paired_differences` | `3791158360b975594066a7254332dc2013c5ef7861cfd48d54d0a2d5fa766e8d` | `capacity_deadline_success_paired_differences.tex` | `c93281793dce4d156332269bdb9bbde0990c06404b2a521d45ffc2796d9c7463` | 844 |
| `capacity_deadline_success_paired_differences` | `3791158360b975594066a7254332dc2013c5ef7861cfd48d54d0a2d5fa766e8d` | `capacity_deadline_success_paired_differences.svg` | `66214fa4b0f2880bc9f8c46d67180ddef46635b78705332396efac348a71e2b1` | 1404 |
| `capacity_offload_invariance` | `3e4c897ae72a1758c50288cd7433fe3e4f8da624766f60720545ab368d775714` | `capacity_offload_invariance.tex` | `07d0a8089c8afe1dc1f03ba892f0e0b2b0c19008d25817163761178d323fb43a` | 2472 |
| `capacity_offload_invariance` | `3e4c897ae72a1758c50288cd7433fe3e4f8da624766f60720545ab368d775714` | `capacity_offload_invariance.svg` | `8dbd7e262d9e0547be31f8976ffa78c78089dd448366fdeb9824f389d2cc326c` | 7998 |

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
