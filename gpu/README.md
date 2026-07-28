# TrafficTwin GPU track

Status: engineering harnesses only. Nothing in this directory is a scientific result,
an admitted actor, or permission to move external assets.

## First Colab experiment: B-CAP synthetic smoke

[`colab/bcap_synthetic_smoke.ipynb`](colab/bcap_synthetic_smoke.ipynb) is a deliberately
synthetic stand-in for the first capacity-aware retraining experiment. It checks that a
Colab GPU can:

- run pinned JAX-style array training;
- randomize the capacity-per-padded-slot grid `{2.5, 1.5, 1.0, 0.75}` per batch item;
- train matched toy actors with the original 17-D hidden-capacity observation and a
  proposed 19-D observation carrying normalized capacity and RSU headroom;
- use at least five independent model seeds and common fixed evaluation contexts;
- save 17/19-64-64-3 checkpoint-shaped NPZ files, curves, greedy diagnostics, a
  deterministic design manifest, and a hashed output inventory; and
- record that every output is synthetic, diagnostic, non-admissible, and ineligible for
  the TrafficTwin actor allowlist.

The policy-gradient task is a small contextual bandit written for harness validation. It
is **not MAPPO**, does not reproduce the producer environment, and cannot answer the
TrafficTwin research question. The real B-CAP run still requires the corrected producer
observation/state implementation, predeclaration, permission, source review, and
checkpoint homecoming described in
[`docs/research_directions_v2.md`](../docs/research_directions_v2.md).

## Hard boundary

The notebook clones only the TrafficTwin GitHub repository. It does not accept a trace,
checkpoint, repository root, URL, upload, or Drive mount as an experiment input. Do not
add or upload any of the following:

- `../external/vec_env` or `../external/tos-data`;
- any Randy checkpoint, trace, source archive, or university GitLab content;
- raw or derived bus data; or
- anything under `.demo/`, `data/vec-fresh/`, or a quarantine workspace.

Real producer code/data may enter Colab only after Randy's written permission is recorded.
Raw BODS quarantine snapshots never enter Colab under any permission state.

## Run in Colab

Open the notebook from the `claude/complete-v0.7` branch and select a GPU runtime. The
notebook refuses to start its default run unless JAX reports a GPU device. It clones the
branch into a fresh `/content/traffictwin-bcap-smoke` directory, records the resolved Git
commit in the manifest, and writes only to `/content/bcap-synthetic-smoke-output`.

The default is five model seeds per observation variant, 250 policy-gradient updates,
and three fixed evaluation-context seeds. Inspect `summary.json` only as an engineering
diagnostic. Do not select hyperparameters or formulate a scientific claim from it.

## Tiny local CPU validation

The full default belongs on Colab. A tiny bounded CPU run is available for code validation:

```bash
JAX_PLATFORMS=cpu uv run python -m gpu.colab.bcap_synthetic_smoke \
  --output-dir /tmp/traffictwin-bcap-smoke \
  --model-seeds 100 \
  --evaluation-seeds 9000 \
  --updates 2 \
  --batch-size 32 \
  --evaluation-batch-size 64
```

The output directory must be absent or empty. The driver never overwrites an existing
non-empty directory.

## Outputs

| File | Meaning |
|---|---|
| `design_manifest.json` | Canonical design plus SHA-256 fingerprint and hard-boundary flags |
| `execution_manifest.json` | Resolved TrafficTwin commit, driver hash, JAX version, and devices |
| `summary.json` | Cross-model diagnostic summaries; explicitly non-evidence |
| `*_training_curve.csv` | Toy policy-gradient optimization diagnostics |
| `*_greedy_eval.json` | Common-context deterministic toy evaluation |
| `*_actor_params.npz` | Checkpoint-shaped synthetic toy parameters; never actor-admissible |
| `output_inventory.json` | SHA-256 and size of every preceding returned file |

## Second Colab experiment: B-BUS synthetic trace replay

[`colab/bbus_synthetic_trace_smoke.ipynb`](colab/bbus_synthetic_trace_smoke.ipynb) is the
permission-safe precursor to B-BUS. It procedurally creates two deterministic toy motion domains —
`bus_like_fixture` and `general_traffic_fixture` — without reading observed or derived motion. It
then trains five matched `17-64-64-3` toy actors per training domain and evaluates every checkpoint
on common held-out synthetic traces from both domains.

This proves the fixed-trace replay bundle, training-domain identity, model-seed discipline,
train-by-evaluate matrix, checkpoint packaging, manifest, and hashed return path. A bus-like
procedural fixture is not a bus observation: its results cannot support a distribution-shift,
Manchester, transport, or policy claim.

The notebook accepts no upload, Drive mount, trace path, URL, repository root, or checkpoint. The
real B-BUS experiment remains blocked on the attended peak session, G1–G5 signing, derived-trace
viability, cloud permission where applicable, predeclaration, and reviewed admission.

The full default is five model seeds per synthetic training domain, 250 updates, one fixed 32,768-row
training trace per domain, and three held-out 16,384-row evaluation traces per domain. A tiny local
CPU validation is:

```bash
JAX_PLATFORMS=cpu uv run python -m gpu.colab.bbus_synthetic_trace_smoke \
  --output-dir /tmp/traffictwin-bbus-smoke \
  --model-seeds 200 \
  --evaluation-seeds 9100 \
  --updates 2 \
  --batch-size 32 \
  --training-trace-size 64 \
  --evaluation-trace-size 64
```

Its additional `synthetic_training_trace_bundle.npz` output contains only generated fixture rows;
`*_cross_domain_eval.json` records each toy checkpoint's complete two-domain diagnostic matrix.
