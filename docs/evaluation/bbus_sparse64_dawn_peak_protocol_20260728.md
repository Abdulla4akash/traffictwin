# B-BUS Whole-Fleet Sparse-64 Dawn-to-Peak — APPROVED EXPLORATORY PROTOCOL

**Status:** owner-approved successor, with its infrastructure algorithm frozen by the primary
research/integration agent before placement or GPU execution. This arm is explicitly outside
accepted VEC-06 because full coverage is neither required nor expected. It is not actor
admission, a supervisor signature, publication permission, or a scientific verdict.

- Protocol date: 28 July 2026
- Experiment ID: `B-BUS-SPARSE64-DAWN-PEAK-20260728`
- Parent experiment: `B-BUS-DAWN-PEAK-20260728`
- Train/evaluate split: captured dawn session for training; captured peak session once for
  held-out evaluation
- Acquisition or attendance: none

## 1. Owner decision and question

After the parent full-region trace refused VEC-06 full-coverage placement, its result record
presented two numbered successors. The owner answered `cant we do both 1 and 2`. This protocol
is successor 2. The owner selected the experiment; the agent did not take that owner decision.

The question is: can a dawn-trained bus policy transfer to the independently captured peak
window when the complete Greater Manchester bus trace is preserved but V2I opportunity is
limited to one sparse 64-site analysis estate designed from dawn only?

## 2. Frozen sparse-site algorithm

The parent dawn and peak motion arrays remain byte-for-byte unchanged except for adding the
same `rsu_xy` array. There is no spatial filtering, rematching, rerouting, interpolation,
vehicle thinning or subwindow selection.

Sites are derived **only from dawn** as follows:

1. Quantise every active dawn position to a 50 m cell using `floor(position / 50)` and count
   dawn vehicle-seconds in each occupied cell.
2. Candidate sites are the centres of occupied dawn cells. A candidate safely covers another
   cell when their centres are within `500 - 50*sqrt(2)/2` metres, matching the accepted
   full-cell convention.
3. For each of exactly 64 iterations, select the candidate with maximum still-uncovered dawn
   vehicle-second weight, mark its safely covered cells, and continue even though uncovered
   cells remain. Ties resolve to the lexicographically lowest integer cell `(easting_index,
   northing_index)`. Selecting a duplicate or a zero-gain site is a refusal.
4. Store the 64 selected cell centres as float32 in selection order. Add those exact bytes to
   both traces; no peak-derived site, movement or weight may alter them.
5. Compute exact point-to-site coverage at 500 m for dawn and held-out peak in chunks, and
   report covered and uncovered vehicle-seconds, shares, occupied cells and peak concurrent
   buses. These are coverage diagnostics, not a threshold used to tune or reject the result.

The sparse algorithm is a new versioned TrafficTwin successor method. It does not run or claim
the pinned `greedy_urban_cover` full-cover script, does not raise the 64-site bound, does not
call the generated sites observed RSUs, and cannot produce or inherit a VEC-06 receipt.

## 3. GPU campaign and held-out discipline

All parent Phase-107 settings remain binding: producer trace-replay MAPPO Model-C; seeds
`30,31,32,33,34`; dawn-only training; a requested 5,000,000 environment steps; one frozen
actor per seed; and one held-out peak evaluation at capacity per active slot `0.75` and `2.5`
under common random keys. Peak never participates in site selection, training, model selection,
stopping or hyperparameter choice. A GPU is required and CPU fallback is refused.

The primary metric remains equal-weight mean held-out peak deadline-completion share at 0.75.
The parent secondary metrics and publishable null remain unchanged. Coverage share is a named
infrastructure diagnostic and must accompany every result so the arm cannot be mistaken for
full coverage. Training diagnostics are not the primary result; a weak peak result is reported,
never repaired by training on peak or moving sites.

Memory-driven vectorisation may be reduced once, before the first seed, while preserving
effective steps and every scientific setting. The common runtime configuration, exact producer
source bytes, trace hashes, site-array hash, GPU identity and all output hashes are recorded.

## 4. Privacy and claim ceiling

Only the parent protocol's derived, pseudonymised allowlist may enter the owner's private
Colab. Raw BODS material, raw identifiers, salts, snapshot/quarantine references, private local
paths and cross-session links remain forbidden. Public hosting is unauthorised.

Any conclusion is limited to these two one-day bus windows, this derived trajectory policy,
the dawn-designed sparse analysis estate, task generator and five seeds. It cannot establish
full infrastructure coverage, optimal RSU placement, real deployed-RSU performance, a causal
rush-hour effect, same-vehicle change, observed FCD, general Manchester traffic, cross-day
generalisation, VEC-06 compatibility or actor admission.
