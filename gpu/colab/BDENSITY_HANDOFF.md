# B-DENSITY handoff to the GPU track lead

**Prepared by the primary research/integration agent. Not launched here — the GPU track is
Codex's lane and this must not start a parallel one.**

## What this is and why it exists

The local capacity programme is closed except for one hole: capacity is exactly inert at
139–215 concurrent slots and binds at 2,488, so **saturation onset is bracketed in
(215, 2488] and nothing we hold sits inside it**. The observed Manchester bus fleet peaks at
~1,216–1,250 concurrent — inside that band.

Locally the gap cannot be closed. `VecRunRequest` has no fleet-size control, so density only
changes by changing the trace, and admitting a derived trace would extend the allowlist in a
class the project has deliberately never used
([memo](../../docs/evaluation/density_gap_options_20260728.md)).

**On the synthetic environment the constraint disappears**, because density is a parameter of
an environment you construct rather than a property of a fixed replayed trace. That
environment is *code*, which the recorded permission covers for Colab; producer traces,
occupancy arrays and checkpoints-as-data are not used.

## Why this is permitted where the local campaigns are not

[The permission record](../../docs/integration/randy_code_permission_20260728.md) covers the
**code** for Colab and CSF with citation, and explicitly leaves the **data blobs** (traces,
occupancy, instrumented arrays, checkpoints-as-data) as an open ask. The running local
campaigns evaluate a pinned checkpoint on `trace_inc_fullrsu.npz`, so they cannot go to
Colab. **This one uses no producer data at all**, exactly like B-CAP, which is why B-CAP
already runs there.

## Files

| File | Purpose |
|---|---|
| `docs/evaluation/bdensity_predeclaration_20260728.md` | The frozen design, hypothesis, prediction and verdict rule. Bind its SHA-256 before Phase 2. |
| `gpu/colab/bdensity_smoke.py` | Phase 1 engineering smoke. Proves the density axis, the non-GPU refusal and the manifests. |

## The hypothesis, frozen before anything runs

`c_onset ∝ N` — onset capacity scales with concurrent density. Grounded in two measured
points: `ev` (175 slots) binds only at cap-0.1 while `inc` (2,488) responds from cap-2.5,
i.e. ~25× in onset capacity against ~14× in density.

**Verdict rule:** HELD if onset is monotone in N and a log–log slope lands in [0.7, 1.3];
REFUTED otherwise; **NO ONSET** if no density shows sensitivity, which is a publishable
negative about the synthetic environment's fidelity rather than a failed run.

## Phase 1 status — run it, then read the manifest

The smoke has been lint-clean and dry-run locally. Two behaviours are verified:

- **The non-GPU refusal fires.** On a CPU backend it exits with `NON_GPU_BACKEND_REFUSED`.
  `--allow-cpu` exists only for a dry run whose outputs must never be reported.
- **The density axis responds** at both smoke capacities.

**Read this before interpreting any Phase-1 number.** The Phase-1 model's capacity semantics
are deliberately the *opposite* of the real system's: here capacity acts as a service rate,
so backlog falls as capacity rises. In the real evaluator `rsu_capacity_per_vehicle` is a
backlog **allowance**, which is why the measured tail-latency ceiling is *proportional* to
capacity (`L(c) = 39,959 ms × c`) and why squeezing capacity *reduces* latency. Phase 1
proves plumbing only. **Phase 2's reviewed transform must preserve the allowance semantics**,
or it will answer a different question than the local programme.

## Phase 2, if you take it

Substitute a reviewed transform of a disposable `vec_jax.py` copy — the same operation
B-CAP already performs for the 19-D observation — parameterising the concurrent-vehicle
count instead. Grid frozen in the predeclaration: densities 128 / 256 / 512 / 1024 / 1536 /
2048 × capacities 2.5 / 1.0 / 0.5 / 0.25, one from-scratch 17-D actor trained **per density**
(so no actor is evaluated off its own training density), 3 model seeds.

**Timesteps per job are deliberately not fixed** — the compute budget is yours and the
owner's to allocate. The grid shape is what the predeclaration freezes.

## What the result may and may not say

- It locates onset **in the synthetic environment**. It is not a measurement of `inc`'s
  threshold, and no number may be quoted as a property of the Manchester traces or the
  Etihad district.
- Non-admitted diagnostic, like every GPU-track output. Returned actors are not
  actor-admission candidates.
- A **local** counterpart is already queued that tests the same hypothesis on audited traces
  at 139 / 163 / 175 / 215 slots. If both agree they corroborate each other; neither alone is
  sufficient, and **the local route is the one closer to the real evidence**.

## Coordination

No campaign is launched, no allowlist is touched, no pinned clone is fetched or modified, and
no producer data leaves the machine. If you would rather fold this into the existing GPU
queue behind B-BUS, that ordering is fine — nothing here is time-critical.
