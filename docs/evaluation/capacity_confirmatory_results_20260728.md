# Capacity Confirmatory Results — 28 July 2026

**Status: the confirmatory result of the signed protocol
[candidate (b)](capacity_confirmatory_candidate_b_latency_primary.md), executed on the
reserved held-out cohort. Label ceiling `owner_approved_candidate` — not supervisor
approval, not scientific validation, not causal. Exactly one contrast carries
confirmatory standing; everything else here is descriptive context.** The
machine-rendered gated report is committed beside this record:
[capacity_confirmatory_report_20260728.md](capacity_confirmatory_report_20260728.md)
(renderer refuses unless the campaign is held-out, authorised, digest-bound, complete,
and fingerprint-consistent — all checks passed).

## The confirmatory finding

**Tightening per-vehicle RSU capacity from 2.5 to 0.75 reduced mean task latency on
every one of the five held-out seeds.** Under the predeclared STA-01 paired design
(pairing on fleet seed, seeds {10–14}, declared before any held-out data existed):

- **Mean paired difference: −8,310.9 ms** (variation − baseline)
- **Bootstrap interval: [−9,097.5, −7,524.3]** (0.95, 10,000 repetitions, fixed seed)
- **Randomisation test: p = 0.0625** — the exact floor attainable with five pairs
  (all five differences share the predeclared direction)
- Arm means: **12,027.5 ms (cap-2.5) → 3,716.6 ms (cap-0.75)** — a 3.24× reduction,
  with non-overlapping per-arm ranges ([10,372.4, 13,446.4] vs [3,283.1, 4,182.4])

The signed protocol's STA-05 planning check had required 3 seeds at 80% power for an
attenuated target of −5,036 ms; the achieved effect (−8,311 ms) exceeded even the
unattenuated pilot estimate. The held-out effect is *larger* than the pilot's
(−6,715 ms), not shrunken — the opposite of a regression-to-noise pattern.

## Descriptive context (no confirmatory standing, reported with equal honesty)

- **The deadline null replicates on fresh seeds.** Mean deadline-success 0.770944
  (cap-2.5) versus 0.772073 (cap-0.75); per-seed differences +0.000761 / +0.000073 /
  +0.000176 / +0.002935 / +0.001698 — flat-to-faintly-rising on all five held-out
  seeds, exactly as in the pilot. The squeeze never reduced deadline attainment.
- **Capacity-invariance replicates.** Per-seed offload rates are identical between the
  two arms on every held-out seed (arm means equal to six decimals: 0.406864), as is
  the no-eligible-target rate. This matches the
  [observability-gap mechanism](../integration/evidence/vec_pilot_observability_gap_20260728.json)
  located in the pilot artifacts: the policy's observed world does not change with
  capacity, so its decisions cannot.

## Execution integrity

- 10/10 cells completed and admitted under the approval binding the signed candidate's
  SHA-256 (`ac9d6cb7…`) with `held_out_authorised = true`; design fingerprint
  `f289db31…` verified end to end; 37,325 s (10.37 h) of cell compute; zero failures,
  zero skips.
- The run was interrupted twice by session-level task kills. The first real resume
  exposed and was blocked by a latent repeat-admission defect — **fail-closed held and
  the registry took no bad write** — the defect was repaired with regression tests
  (commit `bb6992f`), and the repaired resume then confirmed three completed cells
  without re-execution (receipt states `reused`). The interruption story is preserved
  in the launch log and the AGENTS.md Phase 14 amendment as reproducibility evidence.
- Held-out seeds {10–14} are now spent for capacity studies; pilot seeds were never
  pooled; the unchosen candidate (a) remains unexecuted.

## One-sentence framing (per the signed protocol's scope)

On the collapse-hour trace in the Etihad event district, the signed held-out
confirmation establishes that tightening per-vehicle edge capacity 3.3× *reduces* mean
task latency (−8.3 s, CI [−9.1, −7.5]) while deadline attainment stays flat — because
the trained policy's decisions, blind to capacity by observation design, never change;
only the queueing around them does.

## Limitations (binding)

One actor, one fleet preset, one reviewed trace (a deliberately anomalous collapse
hour), one predeclared contrast at one variation level; five held-out seeds;
per-padded-vehicle capacity semantics; deadline success ≠ physical completion;
descriptive_non_causal throughout; `owner_approved_candidate` — the confirmatory
standing is internal to this project's predeclaration discipline, not external
validation.

## Artifacts

| Artifact | Where |
|---|---|
| Signed protocol (byte-frozen) | `capacity_confirmatory_candidate_b_latency_primary.md`, sha `ac9d6cb7…` |
| Gated confirmatory render | `capacity_confirmatory_report_20260728.md` |
| Campaign receipt + analysis | `data/vec-fresh/capacity-confirmatory/campaign_{receipt,analysis}.json` (local) |
| Registry of admitted evidence | `.demo/registry-capacity-confirmatory.sqlite` (local) |
| Launcher (design source) | `scripts/capacity_confirmatory_campaign.py` |
| Pilot context | [pilot results](capacity_pilot_results_20260727.md) · [detailed narrative](capacity_study_detailed_findings.md) |
