# B-DENSITY predeclaration — where does capacity begin to bind, as a function of density?

**Status: PROPOSED, exploratory, `owner_approved_candidate` ceiling. Not supervisor-approved,
not confirmatory, no significance claimed. GPU-track diagnostic: outputs are never admitted
evidence and never actor-admission candidates. Prepared by the primary research/integration
agent for the GPU track lead (Codex) to run — not launched here.**

## 1. The gap this exists to attack

The local capacity programme is closed except for one hole. Capacity is exactly inert at
139, 163, 175 and 215 concurrent slots and binds at 2,488, so **saturation onset is bracketed
in (215, 2488] and no artifact we hold sits inside it**. The real observed Manchester bus
fleet peaks at ~1,216–1,250 concurrent, measured twice — squarely in the unmeasured band.

Locally the gap cannot be closed. `VecRunRequest` has no fleet-size control, so density can
only change by changing the trace, and a derived trace would need an allowlist extension of a
class the project has deliberately never made
([options memo](density_gap_options_20260728.md)).

**On the producer synthetic environment the constraint disappears**, because density is a
parameter of an environment you construct rather than a property of a fixed replayed trace.
That environment is *code*, which Randy's recorded permission covers for Colab
([permission record](../integration/randy_code_permission_20260728.md)); producer traces,
occupancy arrays and checkpoints-as-data are **not** used, read, or uploaded here.

## 2. Precedent this follows exactly

B-CAP applied a reviewed transform to a disposable copy of `vec_jax.py`, trained ten actors
from scratch on the synthetic environment, touched no producer data — and **reproduced the
capacity-invariance mechanism from scratch**, with 17-D controls exactly invariant. B-DENSITY
is the same class of operation with a different reviewed transform: parameterising the
concurrent-vehicle count instead of the observation width.

## 3. Hypothesis and prediction, frozen before any job runs

**Observation grounding it.** Binding onset is not a fixed capacity — it moves with density.
On `ev` (175 slots) outcomes are inert at cap-0.5 and cap-0.25 and bind only at cap-0.1. On
`inc` (2,488 slots) latency responds across the whole range from cap-2.5 down. That is ~25×
in onset capacity against ~14× in density.

**Hypothesis H-D.** Onset capacity scales with concurrent density: `c_onset ∝ N`, so
`c_onset · N⁻¹` is approximately constant.

**Prediction.** Across the density grid, the capacity at which outcome sensitivity first
appears will rise monotonically with N, and a log–log fit of `c_onset` against `N` will have
slope **1.0 ± 0.3**.

**Verdict rule, fixed now.**

- **HELD** — onset is monotone in N and the fitted slope lies in [0.7, 1.3].
- **REFUTED** — onset is non-monotone in N, or the slope falls outside that interval.
- **NO ONSET** — if no density in the grid shows any capacity sensitivity, the result is
  that the synthetic environment does not reproduce saturation at these densities. That is a
  publishable negative about the environment's fidelity, **not** a failed experiment, and it
  would materially weaken the case for using the synthetic environment for any density claim.

A refutation is more informative than a confirmation: it would mean the onset is set by
something other than vehicle count (task arrival rate, RSU count, service time), which
immediately reshapes what "capacity" means in the finding.

## 4. Design

| | |
|---|---|
| Environment | producer synthetic environment via a reviewed transform of a **disposable copy** of `vec_jax.py`; no producer data of any kind |
| Density grid (N) | **128, 256, 512, 1024, 1536, 2048** — brackets the unresolved (215, 2488] band from both sides |
| Capacity arms | **2.5, 1.0, 0.5, 0.25** per density |
| Actors | one from-scratch 17-D actor **trained per density**, so no actor is evaluated off its own training density |
| Model seeds | 3 per density |
| Observation | 17-D, matching the audited actors' structure — this studies outcomes, not capacity-awareness (that is B-CAP's question) |
| Backend | GPU required; a non-GPU JAX backend must **refuse**, as B-CAP does |
| Outputs | training curves + per-(N, capacity) greedy evaluation; diagnostics only |

**Why train per density rather than train once and sweep.** Evaluating one actor across
densities it never trained on confounds density with distribution shift — and distribution
shift is precisely the Year-1 concern this programme already inherited. Training per density
costs more and removes the confound.

**Two-phase execution.** Phase 1 is an engineering smoke at two densities × two capacities
with tiny timesteps, proving the density transform, the refusal paths and the manifests
before any real budget is spent. Phase 2 is the full grid. Phase 2 must not start until
Phase 1's manifest is inspected.

**Sizing is deliberately left to the GPU lead.** Timesteps per job are not fixed here because
the compute budget is the owner's and the lead's to allocate; the grid shape is what this
document freezes.

## 5. What the result can and cannot say

- It locates onset **in the synthetic environment**. It is *not* a measurement of where
  `inc`'s threshold sits, and no number from it may be quoted as a property of the Manchester
  traces or of the Etihad district.
- It is a **non-admitted diagnostic**, like every GPU-track output. It cannot enter the
  registry, cannot be admitted, and cannot support a confirmatory claim.
- Returned actors are **not** actor-admission candidates.
- If H-D holds in both the synthetic environment and the local low-density onset sweep
  (which tests the same hypothesis on audited traces at 139/163/175/215 slots), the two
  independent routes corroborate each other. **Neither alone is sufficient**, and the local
  route is the one closer to the real evidence.

## 6. Boundaries

- No producer trace, occupancy array, checkpoint-as-data, bus artifact, `.demo/`, quarantine
  material or `data/vec-fresh/` content is read or uploaded.
- Randy's permission covers **code** on Colab and CSF with citation in every output; the data
  half remains an open ask and is not relied on here.
- The transform applies to a disposable copy; the pinned producer clones are never modified
  or fetched.
- Every output carries the citation the permission requires.

## Sign-off

| Field | Value |
|---|---|
| Proposed by | primary research/integration agent |
| To be run by | GPU track lead (Codex) — **not launched by the proposer** |
| Approved by | *(owner decision; relayed delegation recorded at execution, never an owner-typed signature)* |
| Supervisor approval | **none — not sought, not implied** |
