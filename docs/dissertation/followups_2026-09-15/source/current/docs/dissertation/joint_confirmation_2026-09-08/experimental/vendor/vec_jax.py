"""Pure-JAX port of the VEC task offloading environment.

Faithful reimplementation of `/scratch/vec-offloading/env/` in functional JAX.
All physics constants, reward formulas, and decision logic match the reference
PyTorch implementation; only the execution model differs (pure-functional,
jittable, vmappable).

Reference files this port mirrors (do NOT modify the reference):
  - /scratch/vec-offloading/env/config.py
  - /scratch/vec-offloading/env/channel.py
  - /scratch/vec-offloading/env/task.py
  - /scratch/vec-offloading/env/vehicle.py
  - /scratch/vec-offloading/env/rsu.py
  - /scratch/vec-offloading/env/vec_offloading_env.py

Key design choices:
  * State is a flat pytree (NamedTuple of jnp arrays). Everything has static
    shape so we can JIT / vmap / scan without recompilation.
  * Per-agent action handling is vectorised with jnp.where branching over the
    action index; no Python if/else on traced values.
  * PRNG keys are split explicitly before every stochastic operation.
  * Queue handling is simplified: the reference env.queue_depth stays 0 across
    a step (tasks are evaluated instantaneously, not actually queued), so the
    JAX port stores a static queue_depth=0 unless we explicitly enqueue on
    OOM; behaviour matches the reference `_process_action` → no queue writes.
  * Multi-RSU: we vectorise over RSUs with jnp.min/argmax.

Physics invariants preserved (verified by `tests/test_jax_port_fidelity.py`):
  - TR 37.885 path loss: 32.4 + 20*log10(d) + 20*log10(fc) — deterministic
    part matches to <1% at all distances used by the env.
  - Rician K=9 dB, σ_K=3.5 dB, σ_SF=3 dB — distribution moments match.
  - Shannon capacity at fixed SNR matches to <0.1%.
  - Compute time T = workload_Mc*1e6 / (freq*ipc*cores*util*gpu_factor)
    matches the reference formula bit-for-bit before the ±10% noise.
  - Priority-scaled α reward matches the reference arithmetic exactly.
"""
from __future__ import annotations

import os
from typing import NamedTuple

import jax
import jax.numpy as jnp


# ================================================================
# Constants — mirror env/config.py (hand-translated once, locked)
# ================================================================
# Stress-scenario overrides: set VEC_JAX_STRESS=1 in the environment BEFORE
# importing this module to swap in the 4-cell-ablation stress configuration
# (N=40 vehicles, RSU max_concurrent=10, rpi-heavy fleet, type-1-heavy tasks).
# We use env vars because all shapes in this module are compile-time static.
_STRESS = os.environ.get("VEC_JAX_STRESS", "0") == "1"

# --- ENV ---
N_VEHICLES = 40 if _STRESS else 20
# Paper 2B `gridlocktrain` variant: density/speed overrides (default-off).
# Gridlock-like cell = more vehicles on the same corridor/RSUs + near-static
# speeds (dense stable peer field, chronic RSU/queue overload).
N_VEHICLES = int(os.environ.get("VEC_JAX_N_VEHICLES", str(N_VEHICLES)))
N_RSUS = 2
RSU_POSITIONS = (500.0, 1500.0)
MAX_QUEUE_DEPTH = 10
EPISODE_LENGTH = 200
HIGHWAY_LENGTH_M = 2000.0
VEHICLE_SPEED_MIN_KMH = float(os.environ.get("VEC_JAX_SPEED_MIN_KMH", "60.0"))
VEHICLE_SPEED_MAX_KMH = float(os.environ.get("VEC_JAX_SPEED_MAX_KMH", "120.0"))
RSU_COVERAGE_RADIUS_M = 500.0
# Per-RSU saturation ceiling used by _compute_per_vehicle_links AND by the
# new best_rsu_load obs element. Stress uses 10; default mirrors reference 50.
RSU_MAX_CONCURRENT = 10 if _STRESS else 50
# Paper 2B fcd-replay training: match the eval engine's per-RSU concurrency
# scaling (2.5 x fleet, non-binding by design). Default-off override.
RSU_MAX_CONCURRENT = int(os.environ.get("VEC_JAX_RSU_MAX_CONCURRENT",
                                        str(RSU_MAX_CONCURRENT)))

# --- TASK TYPES (1-based in reference; we store arrays indexed 0..2) ---
# (type 1 → idx 0, type 2 → idx 1, type 3 → idx 2)
TASK_DEADLINE_MS = jnp.array([100.0, 500.0, 100.0])
TASK_DATA_SIZE_MB_MEAN = jnp.array([1.0, 0.0012, 0.001])
TASK_WORKLOAD_MCYCLES = jnp.array([1254.0, 2100.0, 15.0])
TASK_GPU_SPEEDUP = jnp.array([40.0, 5.0, 1.0])
TASK_MAX_PARALLELISM = jnp.array([4, 4, 2], dtype=jnp.int32)
TASK_PRIORITY_WEIGHT = jnp.array([20.0, 3.0, 2.0])
# Stress: type 1 heavy (40/30/30). Default: reference distribution.
# Phase 4 sensitivity sweep: read VEC_JAX_TASK_DIST env var to switch among
# {default, uniform, safety_dominant, pilot_inspired}. Numbers match
# /scratch/vec-offloading/env/config.py TASK_DISTRIBUTION_VARIANTS.
_TASK_DIST_VARIANTS = {
    "default":         [0.20, 0.30, 0.50],
    "uniform":         [0.33, 0.33, 0.34],
    "safety_dominant": [0.50, 0.25, 0.25],
    "pilot_inspired":  [0.10, 0.20, 0.70],
}
_TASK_DIST = os.environ.get("VEC_JAX_TASK_DIST", "default")
if _STRESS:
    TASK_ARRIVAL_PROBS = jnp.array([0.40, 0.30, 0.30])
elif _TASK_DIST in _TASK_DIST_VARIANTS:
    TASK_ARRIVAL_PROBS = jnp.array(_TASK_DIST_VARIANTS[_TASK_DIST])
else:
    TASK_ARRIVAL_PROBS = jnp.array(_TASK_DIST_VARIANTS["default"])
MAX_PRIORITY_WEIGHT = 20.0  # max over task types; used for α_k scaling

# --- COMPUTE TIERS: indices 0=rpi, 1=jetson, 2=gpu_vehicle, 3=rsu ---
# (rsu lives as its own "tier" index so we can dispatch via single lookup)
TIER_CPU_FREQ_GHZ = jnp.array([1.5, 1.5, 2.2, 2.2])
TIER_IPC = jnp.array([1.0, 1.2, 1.5, 1.5])
TIER_CORES = jnp.array([4, 6, 8, 12], dtype=jnp.int32)
TIER_UTIL = jnp.array([1.0, 0.9, 0.85, 0.9])
TIER_HAS_GPU = jnp.array([0.0, 1.0, 1.0, 1.0])  # 0 = no GPU, 1 = has GPU
TIER_GPU_SPEEDUP = jnp.array([1.0, 9.0, 20.0, 5.0])
# Layer-2 dose-response: scale the RSU tier's service RATE (index 3) by
# VEC_JAX_RSU_SERVICE_MULT (default 1.0 = unchanged). Applied to CPU freq so
# both CPU- and GPU-path service times scale together.
_RSU_MULT = float(os.environ.get("VEC_JAX_RSU_SERVICE_MULT", "1.0"))
if _RSU_MULT != 1.0:
    TIER_CPU_FREQ_GHZ = TIER_CPU_FREQ_GHZ.at[3].mul(_RSU_MULT)
TIER_POWER_IDLE_W = jnp.array([3.0, 5.0, 10.0, 15.0])
TIER_POWER_COMPUTE_W = jnp.array([7.0, 15.0, 60.0, 60.0])
RSU_TIER_IDX = 3
N_COMPUTE_TIERS = 3  # vehicle-usable tiers (rpi, jetson, gpu_vehicle)

# Fleet distribution (compute tier idx 0=rpi, 1=jetson, 2=gpu_vehicle).
# Stress: rpi-heavy {rpi:0.70, jetson:0.25, gpu_vehicle:0.05}.
# Default: {rpi:0.50, jetson:0.40, gpu_vehicle:0.10} (matches reference).
# Paper 2B fleet-variant training (e.g. uk2030): override via env vars
# VEC_JAX_FLEET_TIER_PROBS="0.40,0.35,0.25" and VEC_JAX_FLEET_EV_PROB="0.22"
# (same pattern as the other VEC_JAX_* overrides; unset = behaviour unchanged).
FLEET_TIER_PROBS = (jnp.array([0.70, 0.25, 0.05]) if _STRESS
                    else jnp.array([0.50, 0.40, 0.10]))
_FLEET_TIER_PROBS_ENV = os.environ.get("VEC_JAX_FLEET_TIER_PROBS", "")
if _FLEET_TIER_PROBS_ENV:
    FLEET_TIER_PROBS = jnp.array(
        [float(x) for x in _FLEET_TIER_PROBS_ENV.split(",")])
    assert FLEET_TIER_PROBS.shape == (N_COMPUTE_TIERS,), \
        "VEC_JAX_FLEET_TIER_PROBS needs exactly N_COMPUTE_TIERS values"
FLEET_EV_PROB = float(os.environ.get("VEC_JAX_FLEET_EV_PROB", "0.30"))
EV_BATTERY_KWH = 60.0
EV_SOC_MIN = 0.20
EV_SOC_MAX = 0.95

# --- CHANNEL (TR 37.885) ---
V2I_FREQ_GHZ = 5.9
V2I_BANDWIDTH_MHZ = 20.0
V2I_TX_POWER_DBM_ICE = 23.0  # ICE default
V2I_NOISE_FIGURE_DB = 9.0
V2I_ANTENNA_GAIN_DB = 8.0
V2I_RICIAN_K_DB = 9.0
V2I_RICIAN_K_STD_DB = 3.5
V2I_SHADOW_STD_DB = 3.0

V2V_FREQ_GHZ = 5.9
V2V_BANDWIDTH_MHZ = 10.0
V2V_NOISE_FIGURE_DB = 9.0
V2V_ANTENNA_GAIN_DB = 0.0
V2V_RICIAN_K_DB = 9.0
V2V_RICIAN_K_STD_DB = 3.5
V2V_SHADOW_STD_DB = 3.0
V2V_RANGE_M = 300.0

MIN_QUALITY_THRESHOLD = 0.15
SNR_FLOOR_DB = 5.0
SNR_CEIL_DB = 40.0

# EV Tx power reduction
EV_TX_POWER_DBM = 20.0

# --- REWARD ---
OOM_PENALTY = -100.0
DEADLINE_MISS_MULT = 10.0
# BASELINE_ALPHA: QoS weight in the slack reward; (1 - alpha) weights the
# (saturating) energy penalty. Overridable for the pure-QoS ablation
# (VEC_JAX_BASELINE_ALPHA=1.0 -> energy term exactly zero). Default 0.7
# preserves original campaign behaviour. Read at import (JIT-compiled).
BASELINE_ALPHA = float(os.environ.get("VEC_JAX_BASELINE_ALPHA", "0.7"))
ENERGY_NORM_DENOM = 0.1  # J
# Ablation toggle: if VEC_JAX_PRIORITY_ALPHA=0, use constant BASELINE_ALPHA
# regardless of task priority weight; if =1 (default), use the priority-
# scaled α_k = baseline + (1 - baseline) * w_k/max_w formula. Read once at
# import time so it participates in the JIT compile.
PRIORITY_SCALED_ALPHA = os.environ.get("VEC_JAX_PRIORITY_ALPHA", "1") == "1"

# ----------------------------------------------------------------------
# Phase 4 stress-mode flags (Sandra's three challenges + lanes).
# All defaults are OFF, so by default this module behaves exactly as before.
# Each flag is read once at module-import time so it participates in the JIT
# compile. Cross-framework parity with /scratch/vec-offloading/env/
# vec_offloading_env_stress.py is documented per-mechanism.
# ----------------------------------------------------------------------
STRESS_LANES_ENABLED = os.environ.get("VEC_JAX_STRESS_LANES", "0") == "1"
STRESS_AFFECT_CHANNEL = os.environ.get(
    "VEC_JAX_STRESS_AFFECT_CHANNEL", "1") == "1"   # only honoured if lanes on
STRESS_SPEED_ENABLED = os.environ.get("VEC_JAX_STRESS_SPEED", "0") == "1"
STRESS_ARRIVAL_ENABLED = os.environ.get("VEC_JAX_STRESS_ARRIVAL", "0") == "1"
STRESS_ORDERING_MODEL = os.environ.get("VEC_JAX_STRESS_ORDERING", "iid")
# Allowed values: iid | markov | round_robin | front_loaded

NUM_LANES_STRESS = int(os.environ.get("VEC_JAX_NUM_LANES", "3"))
LANE_WIDTH_M_STRESS = float(os.environ.get("VEC_JAX_LANE_WIDTH_M", "4.0"))
RSU_LANE_IDX = NUM_LANES_STRESS // 2  # middle lane — fairest placement

LAMBDA_ARRIVAL_STRESS = float(os.environ.get("VEC_JAX_LAMBDA_ARRIVAL", "1.5"))
K_MIN_STRESS = int(os.environ.get("VEC_JAX_K_MIN", "0"))
K_MAX_STRESS = int(os.environ.get("VEC_JAX_K_MAX", "5"))
# D2-A: Model-C arrival semantics. When True, each step iterates over K_MAX
# sub-steps with within-step queue accumulation (each of the k tasks gets its
# own latency check against the CURRENT queue state). When False (default),
# Model-B is used (single latency outcome shared across all k identical tasks,
# multiplied by k in totals).
MODEL_C_ENABLED = os.environ.get("VEC_JAX_MODEL_C", "0") == "1"

OU_THETA_STRESS = float(os.environ.get("VEC_JAX_OU_THETA", "0.05"))
OU_SIGMA_KMH_STRESS = float(os.environ.get("VEC_JAX_OU_SIGMA_KMH", "2.0"))
OU_VMIN_KMH = float(os.environ.get("VEC_JAX_OU_VMIN_KMH", "40.0"))
OU_VMAX_KMH = float(os.environ.get("VEC_JAX_OU_VMAX_KMH", "140.0"))

# Calibrated Markov transition matrix with stationary π = [0.20, 0.30, 0.50]
# (matches /scratch/vec-offloading/env/config.py STRESS_TASK_ORDERING default).
MARKOV_TRANSITION = jnp.array([
    [0.60, 0.15, 0.25],
    [0.10, 0.65, 0.25],
    [0.10, 0.15, 0.75],
])
# Round-robin cycle of length 10 with 2/3/5 → exactly 20/30/50 long-run mix.
# Stored as 0-indexed task types.
ROUND_ROBIN_CYCLE = jnp.array([0, 0, 1, 1, 1, 2, 2, 2, 2, 2], dtype=jnp.int32)
# Front-loaded boundaries for 20/30/50 episode share at episode_length=200.
# Phase 0 (Task 1): steps 0..40; Phase 1 (Task 2): 40..100; Phase 2 (Task 3): 100..200.
FRONT_LOADED_BOUNDS = jnp.array([40, 100, 200], dtype=jnp.int32)
FRONT_LOADED_ORDER = jnp.array([0, 1, 2], dtype=jnp.int32)  # 0-indexed task types

# Poisson Model B documentation (JaxMARL-specific simplification):
# Each step, k_v ~ Poisson(λ) per vehicle v. The agent emits ONE action which is
# replicated to all k_v tasks (each having identical type/size from one sample).
# Rewards, energies, and per-vehicle/RSU compute backlogs scale by k_v.
# This differs from /scratch/vec-offloading/env/vec_offloading_env_stress.py
# which maintains a FIFO pending-task queue. The JaxMARL simplification is
# documented in /scratch/PhD-Project/SetofExperiments_academic_short.md.

# --- OBS ---
# 14-dim observation (reverted 2026-04-17 to match main env revert). The
# `best_rsu_load` element was briefly added and then removed from the main env
# at /scratch/vec-offloading/env/vec_offloading_env.py; the JaxMARL port mirrors
# that revert here for cross-framework parity.
# Layout (matches /scratch/vec-offloading/env/vec_offloading_env.py):
#   [task_type, data_size, deadline, cpu_load, queue_depth, battery_soc,
#    v2i_quality, v2v_quality, nearby_compute, has_task,
#    compute_tier_onehot(3), ev_flag]
# Paper 2B `capscalar` variant (VEC_JAX_CAP_SCALAR=1): both tier one-hots
# (own + V2V target) are replaced by a single continuous capability scalar
# each -> obs 17 -> 13. The scalar is the tier's mean SERVICE RATE over the
# m0pa0 stress task mix (P = 0.40/0.30/0.30), normalised to gpu_vehicle = 1:
#   E[t] = sum_k P_k * W_k / (freq*ipc*min(cores,par_k)*util*gpu_factor_k)
#   cap  = (1/E[t]) / (1/E[t])_gpu_vehicle  ->  [0.0751, 0.4847, 1.0]
# FIXED constants by design (do NOT recompute under VEC_JAX_TASK_DIST — the
# feature definition must not drift across ablations). A future OBU type gets
# rate_new/rate_ref from the same formula (may exceed 1.0) — an
# obs-DISTRIBUTION shift, not an obs-SPACE change (SetofExperiments_2B 2.12).
CAP_SCALAR_ENABLED = os.environ.get("VEC_JAX_CAP_SCALAR", "0") == "1"
TIER_CAP_SCALAR = jnp.array([0.0751, 0.4847, 1.0])
OBS_SIZE = 13 if CAP_SCALAR_ENABLED else 17
ACT_N = 3  # 0=local, 1=V2I, 2=V2V


# ================================================================
# State dataclass
# ================================================================


class EnvState(NamedTuple):
    # Vehicle state (shape [N_VEHICLES, ...])
    positions: jax.Array       # float [N] in m
    speeds: jax.Array          # float [N] in km/h
    compute_tier: jax.Array    # int32 [N], ∈ {0,1,2}
    is_ev: jax.Array           # bool [N]
    soc: jax.Array             # float [N] ∈ [0,1]; non-EV = 1.0
    tx_power_w: jax.Array      # float [N], vehicle Tx power (watts)
    # Compute queue per vehicle (aggregate scalar model):
    #   queue_busy_ms = total remaining compute backlog (ms)
    #   queue_depth   = number of in-flight tasks
    # Tasks drain by 1000 ms/step; depth decays proportional to busy_ms drain.
    queue_busy_ms: jax.Array   # float [N]
    queue_depth: jax.Array     # int32 [N]
    total_energy_j: jax.Array  # float [N]
    # RSU state (symmetric queue model with vehicles):
    #   rsu_busy_ms = total remaining compute backlog per RSU (ms)
    #   rsu_load    = number of in-flight tasks per RSU
    rsu_busy_ms: jax.Array     # float [N_RSUS]
    rsu_load: jax.Array        # int32 [N_RSUS]
    # Current tasks (per agent) — sampled at reset and each step
    task_type: jax.Array       # int32 [N] ∈ {0,1,2}
    task_data_size_mb: jax.Array  # float [N] (with ±20% noise)
    # Episode counter
    step_count: jax.Array      # int32 scalar
    # Running episode metrics (for info dict)
    tasks_total: jax.Array     # int32 scalar
    tasks_completed: jax.Array # int32 scalar
    tasks_deadline_miss: jax.Array  # int32 scalar
    total_latency_ms: jax.Array     # float scalar — sum of all per-task latencies
    actions_local: jax.Array   # int32 scalar
    actions_v2i: jax.Array     # int32 scalar
    actions_v2v: jax.Array     # int32 scalar
    total_reward: jax.Array    # float scalar
    # ----- Phase 4 stress fields (no-op defaults when stress is off) -----
    lane_id: jax.Array            # int32 [N], ∈ {0..NUM_LANES_STRESS-1}; all 0 when STRESS_LANES_ENABLED is False
    desired_speed_kmh: jax.Array  # float [N]; OU target / IDM v_des; = speeds when STRESS_SPEED_ENABLED is False
    last_task_type: jax.Array     # int32 [N]; previous head's type per vehicle, used by Markov ordering
    n_arrivals_this_step: jax.Array  # int32 [N]; k for Model B; all 1 when STRESS_ARRIVAL_ENABLED is False
    # ----- Paper 2B fcd-replay training (VEC_JAX_TRACE_REPLAY; default no-op) -----
    trace_t: jax.Array = 0        # int32 scalar; current index into the replayed trace


class EnvParams(NamedTuple):
    """Hyperparameters; typically constant across an experiment."""
    episode_length: int = EPISODE_LENGTH


def make_default_params() -> EnvParams:
    return EnvParams(episode_length=EPISODE_LENGTH)


# ================================================================
# Physics: path loss, fading, SNR, capacity
# ================================================================


def path_loss_v2x_db(dist_m: jax.Array, fc_ghz: float) -> jax.Array:
    """TR 37.885 Highway LOS deterministic path loss (no fading, no shadow).

    PL = 32.4 + 20*log10(d_3D) + 20*log10(fc)   [dB], d clamped to 1 m.
    """
    d = jnp.maximum(dist_m, 1.0)
    return 32.4 + 20.0 * jnp.log10(d) + 20.0 * jnp.log10(fc_ghz)


def rician_fading_db(key: jax.Array, k_mean_db: float, k_std_db: float) -> jax.Array:
    """Draw a Rician-faded instantaneous power-gain loss in dB.

    Procedure per TR 37.885 evaluation methodology:
      1. Draw K-factor in dB ~ N(K_mean, K_std), convert to linear.
      2. Construct |h|^2 = (los_amp + scat_re)^2 + scat_im^2 with scatter
         sigma = sqrt(1/(2*(K+1))); E[|h|^2] = 1.
      3. Return -10*log10(|h|^2).
    """
    k1, k2, k3 = jax.random.split(key, 3)
    k_db = k_mean_db + k_std_db * jax.random.normal(k1)
    k_linear = jnp.power(10.0, k_db / 10.0)
    los_amp = jnp.sqrt(k_linear / (k_linear + 1.0))
    scat_sigma = jnp.sqrt(1.0 / (2.0 * (k_linear + 1.0)))
    scat_re = scat_sigma * jax.random.normal(k2)
    scat_im = scat_sigma * jax.random.normal(k3)
    amp = jnp.sqrt((los_amp + scat_re) ** 2 + scat_im ** 2)
    power_gain = jnp.maximum(amp ** 2, 1e-10)
    return -10.0 * jnp.log10(power_gain)


def shadow_fading_db(key: jax.Array, sigma_db: float) -> jax.Array:
    return sigma_db * jax.random.normal(key)


def snr_db(path_loss_db: jax.Array, tx_power_dbm: jax.Array,
           noise_figure_db: float, antenna_gain_db: float,
           bandwidth_mhz: float) -> jax.Array:
    """SNR in dB. Thermal noise: N = kTB = -174 dBm/Hz + 10*log10(BW_Hz) + NF."""
    noise_dbm = -174.0 + 10.0 * jnp.log10(bandwidth_mhz * 1e6) + noise_figure_db
    return tx_power_dbm + antenna_gain_db - path_loss_db - noise_dbm


def shannon_capacity_mbps(snr_db_val: jax.Array, bandwidth_mhz: float) -> jax.Array:
    """Shannon capacity [Mbps] = BW * log2(1 + SNR_linear)."""
    snr_linear = jnp.maximum(jnp.power(10.0, snr_db_val / 10.0), 0.0)
    cap_bps = bandwidth_mhz * 1e6 * jnp.log2(1.0 + snr_linear)
    return cap_bps / 1e6


def snr_to_quality(snr_db_val: jax.Array) -> jax.Array:
    """Linear scaling SNR → quality ∈ [0, 1] with floor/ceil."""
    q = (snr_db_val - SNR_FLOOR_DB) / (SNR_CEIL_DB - SNR_FLOOR_DB)
    return jnp.clip(q, 0.0, 1.0)


def wrap_dist(pos_a: jax.Array, pos_b: jax.Array) -> jax.Array:
    """Highway wrap-around 1D distance (used by base behaviour)."""
    d = jnp.abs(pos_a - pos_b)
    return jnp.minimum(d, HIGHWAY_LENGTH_M - d)


# ---- Paper 2B fcd-replay TRAINING mode (VEC_JAX_TRACE_REPLAY=<trace.npz>) ----
# Mobility comes from a SUMO-FCD trace (build_trace npz: pos_x/pos_y [T,N],
# mask, rsu_xy) instead of the synthetic corridor roam. Episodes are random
# EPISODE_LENGTH windows of the trace; inactive vehicles are parked at 1e7
# with zeroed queues and no arrivals (mirrors eval_sumo_stage1_mc.py exactly).
# Overrides N_VEHICLES / RSU_POSITIONS / N_RSUS from the trace and replaces
# the 1-D ring metric with 2-D Euclidean. Default-off: unset -> no change.
TRACE_REPLAY_PATH = os.environ.get("VEC_JAX_TRACE_REPLAY", "")
TRACE_REPLAY_ENABLED = bool(TRACE_REPLAY_PATH)
if TRACE_REPLAY_ENABLED:
    import numpy as _np
    _tr = _np.load(TRACE_REPLAY_PATH)
    TRACE_POS = jnp.stack([jnp.asarray(_tr["pos_x"], dtype=jnp.float32),
                           jnp.asarray(_tr["pos_y"], dtype=jnp.float32)], axis=-1)
    TRACE_MASK = jnp.asarray(_tr["mask"])                 # [T, N] bool
    TRACE_T_TOTAL = int(TRACE_POS.shape[0])
    TRACE_PARK_XY = jnp.float32(1.0e7)
    N_VEHICLES = int(TRACE_POS.shape[1])
    RSU_POSITIONS = tuple(map(tuple, _np.asarray(_tr["rsu_xy"])))
    N_RSUS = len(RSU_POSITIONS)

    def wrap_dist(pos_a: jax.Array, pos_b: jax.Array) -> jax.Array:  # noqa: F811
        """2-D Euclidean (replaces the ring metric in trace-replay mode)."""
        return jnp.sqrt(jnp.sum((pos_a - pos_b) ** 2, axis=-1))


def wrap_dist_2d(pos_a: jax.Array, lane_a: jax.Array,
                 pos_b: jax.Array, lane_b: jax.Array) -> jax.Array:
    """Phase 4 stress 2D distance with wrap-around in x and lateral lane offset.

    d_2d = sqrt(d_x_wrap² + (lane_width × |Δlane|)²)

    Used by v2i_link / v2v_link only when STRESS_LANES_ENABLED and
    STRESS_AFFECT_CHANNEL are both True; otherwise the original 1D wrap_dist
    is used (so lane_id has no observational effect)."""
    dx = wrap_dist(pos_a, pos_b)
    dy = LANE_WIDTH_M_STRESS * jnp.abs(
        lane_a.astype(jnp.float32) - lane_b.astype(jnp.float32))
    return jnp.sqrt(dx ** 2 + dy ** 2)


# ================================================================
# V2I / V2V quality + capacity (instantaneous, with fresh fading draws)
# ================================================================


def v2i_link(key: jax.Array, veh_pos: jax.Array, veh_tx_power_dbm: jax.Array,
             rsu_pos: jax.Array,
             veh_lane: jax.Array | None = None,
             rsu_lane: jax.Array | None = None) -> tuple[jax.Array, jax.Array]:
    """Return (quality, capacity_mbps) for one V2I link.

    If vehicle outside coverage (>500 m), quality=0, capacity=0.

    Optional lane args (used only when STRESS_LANES_ENABLED and
    STRESS_AFFECT_CHANNEL): if both provided, the effective distance
    is the 2D Pythagorean d_x² + (lane_width·|Δlane|)² with wrap-around in x.
    """
    k_rician, k_shadow = jax.random.split(key, 2)
    if (STRESS_LANES_ENABLED and STRESS_AFFECT_CHANNEL
            and veh_lane is not None and rsu_lane is not None):
        dist = wrap_dist_2d(veh_pos, veh_lane, rsu_pos, rsu_lane)
    else:
        dist = wrap_dist(veh_pos, rsu_pos)
    in_range = dist <= RSU_COVERAGE_RADIUS_M

    pl_det = path_loss_v2x_db(dist, V2I_FREQ_GHZ)
    pl_rician = rician_fading_db(k_rician, V2I_RICIAN_K_DB, V2I_RICIAN_K_STD_DB)
    pl_shadow = shadow_fading_db(k_shadow, V2I_SHADOW_STD_DB)
    pl_total = pl_det + pl_rician + pl_shadow

    snr = snr_db(pl_total, veh_tx_power_dbm, V2I_NOISE_FIGURE_DB,
                 V2I_ANTENNA_GAIN_DB, V2I_BANDWIDTH_MHZ)
    cap = shannon_capacity_mbps(snr, V2I_BANDWIDTH_MHZ)
    q = snr_to_quality(snr)

    q = jnp.where(in_range, q, 0.0)
    cap = jnp.where(in_range, cap, 0.0)
    return q, cap


def v2v_link(key: jax.Array, pos_a: jax.Array, tx_power_a_dbm: jax.Array,
             pos_b: jax.Array,
             lane_a: jax.Array | None = None,
             lane_b: jax.Array | None = None) -> tuple[jax.Array, jax.Array]:
    """Return (quality, capacity_mbps) for one V2V link. Uses pos_a's Tx power.

    Optional lane args: when both provided AND stress lanes affect the
    channel, distance is 2D (lane lateral offset added in Pythagoras)."""
    k_rician, k_shadow = jax.random.split(key, 2)
    if (STRESS_LANES_ENABLED and STRESS_AFFECT_CHANNEL
            and lane_a is not None and lane_b is not None):
        dist = wrap_dist_2d(pos_a, lane_a, pos_b, lane_b)
    else:
        dist = wrap_dist(pos_a, pos_b)
    in_range = dist <= V2V_RANGE_M

    pl_det = path_loss_v2x_db(dist, V2V_FREQ_GHZ)
    pl_rician = rician_fading_db(k_rician, V2V_RICIAN_K_DB, V2V_RICIAN_K_STD_DB)
    pl_shadow = shadow_fading_db(k_shadow, V2V_SHADOW_STD_DB)
    pl_total = pl_det + pl_rician + pl_shadow

    snr = snr_db(pl_total, tx_power_a_dbm, V2V_NOISE_FIGURE_DB,
                 V2V_ANTENNA_GAIN_DB, V2V_BANDWIDTH_MHZ)
    cap = shannon_capacity_mbps(snr, V2V_BANDWIDTH_MHZ)
    q = snr_to_quality(snr)

    q = jnp.where(in_range, q, 0.0)
    cap = jnp.where(in_range, cap, 0.0)
    return q, cap


def tx_time_ms(data_size_mb: jax.Array, quality: jax.Array,
               capacity_mbps: jax.Array) -> jax.Array:
    """Transmission time in ms; returns large sentinel if link below threshold.

    Mirror of reference: if quality < threshold, returns ~inf (we use 1e9 ms
    as a finite but enormous sentinel, then cap to 10*deadline in reward).
    """
    # If capacity is 0 or quality below threshold, use sentinel
    usable = (quality >= MIN_QUALITY_THRESHOLD) & (capacity_mbps > 0)
    transfer_ms = jnp.where(
        capacity_mbps > 1e-9,
        (data_size_mb * 8.0) / jnp.maximum(capacity_mbps, 1e-9) * 1000.0,
        1e9,
    )
    propagation_ms = 0.1
    t = propagation_ms + transfer_ms
    return jnp.where(usable, t, 1e9)


# ================================================================
# Compute time
# ================================================================


def compute_time_ms(key: jax.Array, task_idx: jax.Array,
                    tier_idx: jax.Array) -> jax.Array:
    """Compute time in ms per reference formula + ±10% noise.

    T = workload_Mc * 1e6 / (freq_hz * ipc * eff_cores * util * gpu_factor)
    gpu_factor = min(task_gpu_speedup, device_gpu_speedup) if device has GPU
                 AND task gpu_speedup > 1; else 1.0
    eff_cores = min(device.cores, task.max_parallelism)
    noise ~ U(0.9, 1.1) multiplicatively.
    """
    workload = TASK_WORKLOAD_MCYCLES[task_idx]
    task_max_par = TASK_MAX_PARALLELISM[task_idx]
    task_gpu = TASK_GPU_SPEEDUP[task_idx]

    freq_hz = TIER_CPU_FREQ_GHZ[tier_idx] * 1e9
    ipc = TIER_IPC[tier_idx]
    cores = jnp.minimum(TIER_CORES[tier_idx], task_max_par).astype(jnp.float32)
    util = TIER_UTIL[tier_idx]
    has_gpu = TIER_HAS_GPU[tier_idx]
    dev_gpu = TIER_GPU_SPEEDUP[tier_idx]

    # gpu_factor: condition = has_gpu AND task_gpu > 1.0
    use_gpu = (has_gpu > 0.5) & (task_gpu > 1.0)
    gpu_factor = jnp.where(use_gpu, jnp.minimum(task_gpu, dev_gpu), 1.0)

    cycles = workload * 1e6
    compute_s = cycles / (freq_hz * ipc * cores * util * gpu_factor)
    compute_ms = compute_s * 1000.0

    noise = jax.random.uniform(key, minval=0.9, maxval=1.1)
    return compute_ms * noise


# ================================================================
# Reward
# ================================================================


def compute_reward(task_idx: jax.Array, tier_idx: jax.Array,
                   latency_ms: jax.Array, energy_j: jax.Array,
                   queue_depth: jax.Array, local_compute_ms: jax.Array) -> jax.Array:
    """Priority-scaled α reward (both mechanisms ON).

    Level 1: OOM (queue full) → -100
    Level 2: deadline miss → -w_k * 10 (x2 if local and local_compute > deadline)
    Level 3: priority-scaled α:
        α_k = baseline_α + (1 - baseline_α) * (w_k / max_w)
        R = α_k * w_k * slack - (1 - α_k) * w_k * energy_norm
    """
    w_k = TASK_PRIORITY_WEIGHT[task_idx]
    deadline = TASK_DEADLINE_MS[task_idx]

    # Level 1: OOM
    oom = queue_depth >= MAX_QUEUE_DEPTH
    r_oom = jnp.full_like(latency_ms, OOM_PENALTY)

    # Level 2: deadline miss
    miss = latency_ms > deadline
    # Extra 2x penalty: if local and local_compute > deadline (impossible locally)
    # NOTE: reference applies this for ALL actions by re-running local compute.
    # We replicate that, so multiplier depends only on local_compute_ms > deadline.
    known_impossible = local_compute_ms > deadline
    penalty = w_k * DEADLINE_MISS_MULT * jnp.where(known_impossible, 2.0, 1.0)
    r_miss = -penalty

    # Level 3: slack reward
    slack = (deadline - latency_ms) / deadline
    slack = jnp.clip(slack, 0.0, 1.0)
    energy_norm = jnp.minimum(1.0, energy_j / ENERGY_NORM_DENOM)
    if PRIORITY_SCALED_ALPHA:
        alpha_k = BASELINE_ALPHA + (1.0 - BASELINE_ALPHA) * (w_k / MAX_PRIORITY_WEIGHT)
        alpha_k = jnp.clip(alpha_k, 0.0, 1.0)
    else:
        # Ablation: constant α = baseline across all task priorities
        alpha_k = jnp.full_like(w_k, BASELINE_ALPHA)
    r_slack = alpha_k * w_k * slack - (1.0 - alpha_k) * w_k * energy_norm

    # Select: oom > miss > slack
    r = jnp.where(oom, r_oom, jnp.where(miss, r_miss, r_slack))
    return r


# ================================================================
# Action processing (vectorised per-agent)
# ================================================================


def process_agent(key: jax.Array,
                  action: jax.Array,         # int32 scalar ∈ {0,1,2}
                  veh_idx: jax.Array,         # int32 scalar
                  state: EnvState,
                  best_rsu_idx: jax.Array,    # int32 scalar: which RSU
                  v2i_quality: jax.Array,     # float scalar (pre-computed)
                  v2i_cap_mbps: jax.Array,
                  best_rsu_ok: jax.Array,     # bool: RSU not saturated
                  best_v2v_idx: jax.Array,    # int32 scalar: target vehicle
                  v2v_quality: jax.Array,
                  v2v_cap_mbps: jax.Array,
                  best_v2v_ok: jax.Array,     # bool: V2V target available
                  fwd_ms: jax.Array | None = None,   # V2I backhaul forwarding
                  svc_mult: jax.Array | None = None,  # per-RSU service scaling
                  rsu_extra_ms: jax.Array | None = None,  # co-batch queueing
                  v2v_extra_ms: jax.Array | None = None,  # co-batch @ helper
                  loc_ok: jax.Array | None = None):  # own-queue admission
    """Process one agent's action; return (reward, latency_ms, energy_j, info dict).

    fwd_ms (optional): extra one-way-equivalent forwarding latency added to the
    V2I path when an RSU load balancer executes the task at a different RSU
    than the radio-ingress one (fiber WAN backhaul). None (default) leaves the
    computation graph byte-identical to the pre-LB engine.

    svc_mult (optional, 2026-08-04 k8s-scaling model): service-rate multiplier
    of the EXECUTING RSU (vertical scaling — the CPU slice Kubernetes grants
    the offloading service on that node). Divides the RSU compute time, exactly
    like the global VEC_JAX_RSU_SERVICE_MULT env knob but per-RSU and
    time-varying. None (default) leaves the graph byte-identical.
    """
    task_idx = state.task_type[veh_idx]
    data_size_mb = state.task_data_size_mb[veh_idx]
    tier_idx = state.compute_tier[veh_idx]
    tx_power_w = state.tx_power_w[veh_idx]
    queue_depth = state.queue_depth[veh_idx]
    queue_remaining_ms = state.queue_busy_ms[veh_idx]

    k_local, k_rsu, k_v2v_tgt, k_ret_rsu, k_ret_v2v = jax.random.split(key, 5)

    # --- LOCAL (action=0) ---
    local_compute_ms = compute_time_ms(k_local, task_idx, tier_idx)
    # Queue delay: actual remaining compute backlog (ms).
    queue_delay_ms = queue_remaining_ms
    lat_local = local_compute_ms + queue_delay_ms
    # vehicle.compute_energy: P_compute_w * T_s
    p_compute_w_local = TIER_POWER_COMPUTE_W[tier_idx]
    energy_local = p_compute_w_local * local_compute_ms / 1000.0
    if loc_ok is not None:
        # 2026-08-05 conserved vehicle queues: a local task that finds its own
        # queue at MAX_QUEUE_DEPTH is individually rejected (scored like the
        # other unavailable paths: penalty latency, no energy) instead of the
        # legacy fractional work-clamp at enqueue.
        lat_local = jnp.where(loc_ok, lat_local, 1e9)
        energy_local = jnp.where(loc_ok, energy_local, 0.0)

    # --- V2I (action=1) ---
    # Uses best RSU. If not ok (no RSU, quality=0, or saturated) → fails (inf).
    rsu_compute_ms = compute_time_ms(k_rsu, task_idx, jnp.int32(RSU_TIER_IDX))
    if svc_mult is not None:
        rsu_compute_ms = rsu_compute_ms / svc_mult
    tx_ms_v2i = tx_time_ms(data_size_mb, v2i_quality, v2i_cap_mbps)
    # Return tx (1 KB result = 0.001 MB)
    ret_ms_v2i = tx_time_ms(jnp.asarray(0.001), v2i_quality, v2i_cap_mbps)
    # RSU backlog (ms) adds to end-to-end V2I latency.
    rsu_queue_ms = state.rsu_busy_ms[best_rsu_idx]
    if rsu_extra_ms is not None:
        # 2026-08-04 sequential substep accounting: work of co-batch tasks
        # already placed on this RSU within the SAME substep (they are served
        # ahead of this one). Without it, every task in a substep is priced
        # against the pre-batch backlog — optimistic whenever a balancer
        # concentrates a substep's traffic on one RSU.
        rsu_queue_ms = rsu_queue_ms + rsu_extra_ms
    lat_v2i_ok = tx_ms_v2i + rsu_queue_ms + rsu_compute_ms + ret_ms_v2i
    if fwd_ms is not None:
        lat_v2i_ok = lat_v2i_ok + fwd_ms
    # Energy: tx_power_w * (tx_time_ms / 1000). If tx fails, reference sets to 0;
    # the 1.0 J cap is applied later when latency==inf.
    energy_v2i_ok = tx_power_w * (tx_ms_v2i / 1000.0)
    # If tx failed, latency = inf; else = lat_v2i_ok
    v2i_tx_fail = (tx_ms_v2i >= 1e8)
    lat_v2i_raw = jnp.where(best_rsu_ok & ~v2i_tx_fail, lat_v2i_ok, 1e9)
    # Reference: if "V2I unavailable" (no RSU or saturated or quality<=0),
    # set latency=inf, energy=0. If available but tx still fails (quality<thr),
    # transmission_time returns inf → lat=inf, energy=inf. In both inf cases,
    # the inf-cap converts energy to 1.0 J and latency to 10*deadline.
    energy_v2i_raw = jnp.where(best_rsu_ok & ~v2i_tx_fail, energy_v2i_ok, 0.0)

    # --- V2V (action=2) ---
    target_tier = state.compute_tier[best_v2v_idx]
    target_compute_ms = compute_time_ms(k_v2v_tgt, task_idx, target_tier)
    # Target's current compute backlog adds to end-to-end latency.
    target_queue_ms = state.queue_busy_ms[best_v2v_idx]
    if v2v_extra_ms is not None:
        # co-batch work already placed on the helper's queue this substep
        # (its own local task + earlier admitted senders — sequential pricing)
        target_queue_ms = target_queue_ms + v2v_extra_ms
    tx_ms_v2v = tx_time_ms(data_size_mb, v2v_quality, v2v_cap_mbps)
    ret_ms_v2v = tx_time_ms(jnp.asarray(0.001), v2v_quality, v2v_cap_mbps)
    lat_v2v_ok = tx_ms_v2v + target_queue_ms + target_compute_ms + ret_ms_v2v
    energy_v2v_ok = tx_power_w * (tx_ms_v2v / 1000.0)
    v2v_tx_fail = (tx_ms_v2v >= 1e8)
    lat_v2v_raw = jnp.where(best_v2v_ok & ~v2v_tx_fail, lat_v2v_ok, 1e9)
    energy_v2v_raw = jnp.where(best_v2v_ok & ~v2v_tx_fail, energy_v2v_ok, 0.0)

    # Select by action
    a0 = action == 0
    a1 = action == 1
    a2 = action == 2
    latency_raw = jnp.where(a0, lat_local, jnp.where(a1, lat_v2i_raw, lat_v2v_raw))
    energy_raw = jnp.where(a0, energy_local, jnp.where(a1, energy_v2i_raw, energy_v2v_raw))

    # Cap inf values per reference: energy → 1.0 J, latency → 10 * deadline
    deadline = TASK_DEADLINE_MS[task_idx]
    latency = jnp.where(latency_raw >= 1e8, deadline * 10.0, latency_raw)
    energy = jnp.where(energy_raw >= 1e8, 1.0, energy_raw)
    # Also cap the specific "energy went to inf because tx failed" case:
    # reference treats ANY inf energy as 1.0 regardless of latency path. We've
    # already filtered those via best_*_ok & ~*_tx_fail, but the energy for a
    # successful offload might be fine; we only cap truly infinite values.

    # V2V target compute also debits target's energy (not returned here;
    # aggregated in step_env via masking).

    reward = compute_reward(task_idx, tier_idx, latency, energy, queue_depth,
                            local_compute_ms)
    deadline_met = latency <= deadline

    # Target energy for V2V (for target's battery bookkeeping)
    p_compute_w_target = TIER_POWER_COMPUTE_W[target_tier]
    target_compute_energy_j = p_compute_w_target * target_compute_ms / 1000.0
    # Only charged when action==V2V and V2V was usable (finite latency)
    target_energy = jnp.where(
        a2 & best_v2v_ok & ~v2v_tx_fail, target_compute_energy_j, 0.0
    )

    return (reward, latency, energy, target_energy, deadline_met,
            local_compute_ms, target_compute_ms, rsu_compute_ms)


# ================================================================
# Per-step precomputation: best RSU and best V2V target per vehicle
# ================================================================


def compute_per_vehicle_links(key: jax.Array, state: EnvState):
    """For each vehicle, compute best-RSU (quality + capacity + saturation flag)
    and best-V2V-target (idx + quality + capacity + ok flag)."""
    # Split one key per vehicle, then per link
    k_rsu_block, k_v2v_block = jax.random.split(key, 2)

    # --- V2I: for each vehicle, evaluate each RSU with a fresh fading draw ---
    v2i_keys = jax.random.split(k_rsu_block, N_VEHICLES * N_RSUS)
    v2i_keys = v2i_keys.reshape(N_VEHICLES, N_RSUS, 2)

    # RSU lane index: stress-lane mode places all RSUs at middle lane; otherwise 0.
    rsu_lane_const = jnp.int32(RSU_LANE_IDX if STRESS_LANES_ENABLED else 0)

    def _one_v2i(veh_pos, veh_tx_dbm, veh_lane, rsu_keys):
        """Evaluate V2I for one vehicle × all RSUs. Returns (qs, caps)."""
        def _per_rsu(i, rsu_key):
            rsu_pos = jnp.asarray(RSU_POSITIONS)[i]
            return v2i_link(rsu_key, veh_pos, veh_tx_dbm, rsu_pos,
                            veh_lane=veh_lane, rsu_lane=rsu_lane_const)
        # vmap across RSUs
        idxs = jnp.arange(N_RSUS)
        qs, caps = jax.vmap(_per_rsu)(idxs, rsu_keys)
        return qs, caps  # [N_RSUS], [N_RSUS]

    # Convert vehicle Tx power from W → dBm: dBm = 10*log10(W*1000)
    veh_tx_dbm = 10.0 * jnp.log10(jnp.maximum(state.tx_power_w, 1e-12) * 1000.0)

    # vmap across vehicles (each gets its own RSU keys)
    all_v2i_q, all_v2i_cap = jax.vmap(_one_v2i)(
        state.positions, veh_tx_dbm, state.lane_id, v2i_keys
    )  # [N, N_RSUS]

    # Best-RSU per vehicle: argmax over RSUs (tie broken arbitrarily; reference
    # uses > strict inequality which starts with best=None and best_q=0.0, so
    # it picks the first RSU whose q > 0; we mirror by argmax, which picks the
    # largest; the difference only matters for equal qualities which is
    # measure-zero in practice).
    best_rsu_idx = jnp.argmax(all_v2i_q, axis=1)
    rows = jnp.arange(N_VEHICLES)
    v2i_q_best = all_v2i_q[rows, best_rsu_idx]
    v2i_cap_best = all_v2i_cap[rows, best_rsu_idx]
    # RSU saturation: RSU is "not saturated" if load < max_concurrent
    rsu_load_selected = state.rsu_load[best_rsu_idx]
    rsu_not_saturated = rsu_load_selected < RSU_MAX_CONCURRENT
    # Combined "best RSU OK" = quality > 0 (in-range) AND not saturated
    best_rsu_ok = (v2i_q_best > 0.0) & rsu_not_saturated
    # Load fraction of the vehicle's chosen RSU ∈ [0, 1]. If the vehicle has
    # no in-range RSU (v2i_q_best == 0) we surface 0.0 (matches reference
    # main env, which returns 0.0 when best_rsu is None).
    best_rsu_load_frac = jnp.where(
        v2i_q_best > 0.0,
        rsu_load_selected.astype(jnp.float32) / float(RSU_MAX_CONCURRENT),
        0.0,
    )
    best_rsu_load_frac = jnp.clip(best_rsu_load_frac, 0.0, 1.0)

    # --- V2V: for each vehicle, evaluate each other vehicle ---
    v2v_keys = jax.random.split(k_v2v_block, N_VEHICLES * N_VEHICLES)
    v2v_keys = v2v_keys.reshape(N_VEHICLES, N_VEHICLES, 2)

    def _one_v2v(pos_a, tx_dbm_a, lane_a, other_keys):
        def _per_target(j, key):
            pos_b = state.positions[j]
            lane_b = state.lane_id[j]
            return v2v_link(key, pos_a, tx_dbm_a, pos_b,
                            lane_a=lane_a, lane_b=lane_b)
        idxs = jnp.arange(N_VEHICLES)
        qs, caps = jax.vmap(_per_target)(idxs, other_keys)
        return qs, caps

    all_v2v_q, all_v2v_cap = jax.vmap(_one_v2v)(
        state.positions, veh_tx_dbm, state.lane_id, v2v_keys
    )  # [N, N]

    # Eliminate self-link: mask diagonal to 0
    self_mask = jnp.eye(N_VEHICLES, dtype=bool)
    all_v2v_q = jnp.where(self_mask, 0.0, all_v2v_q)
    all_v2v_cap = jnp.where(self_mask, 0.0, all_v2v_cap)
    # Also mask targets whose queue is full (queue_depth >= max_queue_depth)
    target_available = state.queue_depth < MAX_QUEUE_DEPTH  # [N]
    mask_avail = jnp.broadcast_to(target_available[None, :], (N_VEHICLES, N_VEHICLES))
    all_v2v_q_masked = jnp.where(mask_avail, all_v2v_q, 0.0)

    best_v2v_idx = jnp.argmax(all_v2v_q_masked, axis=1)
    v2v_q_best = all_v2v_q_masked[rows, best_v2v_idx]
    v2v_cap_best = all_v2v_cap[rows, best_v2v_idx]
    best_v2v_ok = v2v_q_best > 0.0

    return (best_rsu_idx, v2i_q_best, v2i_cap_best, best_rsu_ok,
            best_v2v_idx, v2v_q_best, v2v_cap_best, best_v2v_ok,
            all_v2v_q, all_v2v_cap, best_rsu_load_frac)


# ================================================================
# Observation
# ================================================================


def get_obs_arr(key: jax.Array, state: EnvState) -> jax.Array:
    """Per-agent observation array of shape [N_VEHICLES, OBS_SIZE].

    Uses fresh fading draws (matches reference, which redraws in _get_obs).
    """
    (_, v2i_q, _, _,
     best_v2v_idx, v2v_q, _, best_v2v_ok,
     all_v2v_q, _, _) = compute_per_vehicle_links(key, state)

    # nearby_compute: avg (1 - cpu_load) over neighbours with v2v_q > 0
    # cpu_load = (queue_depth/max_queue + has_current_task)/2; our env has
    # no "current_task" slot (tasks processed instantly), so cpu_load =
    # queue_depth/max/2. Reference Vehicle.cpu_load actually does
    # min(1.0, (queue_load + 1.0)/2) when current_task is not None. Since our
    # queue stays empty, cpu_load = 0.0 and (1 - cpu_load) = 1.0 for all.
    # We replicate by using the same rule.
    queue_load = state.queue_depth.astype(jnp.float32) / MAX_QUEUE_DEPTH
    cpu_load = jnp.minimum(1.0, queue_load / 2.0)  # current_task always None in port
    one_minus_load = 1.0 - cpu_load  # [N]

    # For agent i, avg over j where all_v2v_q[i,j] > 0
    nbr_mask = all_v2v_q > 0.0  # [N, N]
    nbr_count = jnp.sum(nbr_mask, axis=1)
    nbr_sum = jnp.sum(jnp.where(nbr_mask, one_minus_load[None, :], 0.0), axis=1)
    nearby_compute = jnp.where(nbr_count > 0, nbr_sum / jnp.maximum(nbr_count, 1), 0.0)

    # task scalars (task is always present in our port → has_task=1)
    task_type_norm = (state.task_type.astype(jnp.float32) + 1.0) / 3.0  # 0→1/3, 1→2/3, 2→1.0
    data_size_norm = jnp.minimum(1.0, state.task_data_size_mb / 5.0)
    deadline_norm = jnp.minimum(1.0, TASK_DEADLINE_MS[state.task_type] / 2000.0)

    has_task = jnp.ones(N_VEHICLES, dtype=jnp.float32)
    queue_frac = state.queue_depth.astype(jnp.float32) / MAX_QUEUE_DEPTH
    soc_obs = jnp.where(state.is_ev, state.soc, 0.0)

    # Compute tier feature: one-hot [rpi, jetson, gpu_vehicle] (default) or
    # the continuous capability scalar (capscalar variant). Python-level
    # branch on a module constant — static under JIT.
    if CAP_SCALAR_ENABLED:
        tier_feat = TIER_CAP_SCALAR[state.compute_tier][:, None]          # [N, 1]
    else:
        tier_feat = jax.nn.one_hot(state.compute_tier, N_COMPUTE_TIERS)   # [N, 3]
    ev_flag = state.is_ev.astype(jnp.float32)

    obs = jnp.stack([
        task_type_norm,
        data_size_norm,
        deadline_norm,
        cpu_load,
        queue_frac,
        soc_obs,
        v2i_q,
        v2v_q,
        nearby_compute,
        has_task,
    ], axis=1)  # [N, 10]
    obs = jnp.concatenate([obs, tier_feat, ev_flag[:, None]], axis=1)  # [N, 14|12]
    # V2V target tier: one-hot (default) or capability scalar (capscalar).
    # If no usable V2V target, output zeros (no tier signal).
    v2v_target_tier = state.compute_tier[best_v2v_idx]                    # [N] int32
    if CAP_SCALAR_ENABLED:
        v2v_tier_feat = TIER_CAP_SCALAR[v2v_target_tier][:, None]         # [N, 1]
    else:
        v2v_tier_feat = jax.nn.one_hot(v2v_target_tier, N_COMPUTE_TIERS)  # [N, 3]
    v2v_tier_feat = v2v_tier_feat * best_v2v_ok.astype(jnp.float32)[:, None]
    obs = jnp.concatenate([obs, v2v_tier_feat], axis=1)                   # [N, 17|13]
    return obs


def get_action_masks_arr(key: jax.Array, state: EnvState) -> jax.Array:
    """Per-agent action mask [N, 3]. 1 = available, 0 = masked."""
    (_, v2i_q, _, best_rsu_ok,
     _, v2v_q, _, best_v2v_ok,
     _, _, _) = compute_per_vehicle_links(key, state)

    # Local always available
    m_local = jnp.ones(N_VEHICLES, dtype=jnp.float32)
    # V2I: mask if best RSU quality < threshold OR RSU saturated OR no RSU.
    # Combined in best_rsu_ok, but reference also masks on q < threshold even
    # if quality > 0. best_rsu_ok already implies q > 0, but we need the
    # threshold check too:
    m_v2i = (best_rsu_ok & (v2i_q >= MIN_QUALITY_THRESHOLD)).astype(jnp.float32)
    # V2V: mask if quality < threshold
    m_v2v = (v2v_q >= MIN_QUALITY_THRESHOLD).astype(jnp.float32)
    return jnp.stack([m_local, m_v2i, m_v2v], axis=1)


# ================================================================
# Reset / Step
# ================================================================


# ================================================================
# Phase 4 stress helpers (no-op when corresponding flag is OFF)
# ================================================================


def _sample_lane_ids(key: jax.Array) -> jax.Array:
    """Per-vehicle lane assignment uniform in {0..NUM_LANES_STRESS-1}."""
    if not STRESS_LANES_ENABLED:
        return jnp.zeros(N_VEHICLES, dtype=jnp.int32)
    return jax.random.randint(
        key, shape=(N_VEHICLES,), minval=0, maxval=NUM_LANES_STRESS)


def _evolve_speeds_ou(key: jax.Array, speeds_kmh: jax.Array,
                      v_target_kmh: jax.Array) -> jax.Array:
    """Ornstein-Uhlenbeck update of vehicle speeds toward per-vehicle targets.

    v(t+1) = v(t) + θ (v_target - v) + σ √dt N(0, 1), clipped to [v_min, v_max].
    """
    if not STRESS_SPEED_ENABLED:
        return speeds_kmh
    noise = jax.random.normal(key, (N_VEHICLES,))
    new_speed = (speeds_kmh
                 + OU_THETA_STRESS * (v_target_kmh - speeds_kmh)
                 + OU_SIGMA_KMH_STRESS * noise)
    return jnp.clip(new_speed, OU_VMIN_KMH, OU_VMAX_KMH)


def _sample_k_arrivals(key: jax.Array) -> jax.Array:
    """Per-vehicle Poisson k (Model B).

    When STRESS_ARRIVAL_ENABLED is False, returns 1 for every vehicle (matching
    base-env behaviour). When True, samples k_v ~ Poisson(λ), clips to
    [K_MIN_STRESS, K_MAX_STRESS]."""
    if not STRESS_ARRIVAL_ENABLED:
        return jnp.ones(N_VEHICLES, dtype=jnp.int32)
    k = jax.random.poisson(key, lam=LAMBDA_ARRIVAL_STRESS, shape=(N_VEHICLES,))
    return jnp.clip(k, K_MIN_STRESS, K_MAX_STRESS).astype(jnp.int32)


def _sample_task_types_ordered(key: jax.Array,
                               step_count: jax.Array,
                               last_task_type: jax.Array) -> jax.Array:
    """Sample one task type per vehicle, honouring the active ordering model.

    For Markov, the per-vehicle previous task type drives the transition.
    For round-robin / front-loaded, the env-level step_count drives the cycle.
    For iid (default), uses TASK_ARRIVAL_PROBS — identical to the base
    `_sample_tasks` distribution component.
    """
    if STRESS_ORDERING_MODEL == "markov":
        # Per vehicle: row = last_task_type, draw from that row.
        # We sample one categorical per vehicle.
        # logits = log(P[last_type, :])
        per_keys = jax.random.split(key, N_VEHICLES)
        def _one_markov(k, prev):
            probs = MARKOV_TRANSITION[prev]
            return jax.random.choice(k, jnp.arange(3), p=probs)
        return jax.vmap(_one_markov)(per_keys, last_task_type)
    if STRESS_ORDERING_MODEL == "round_robin":
        cycle_len = ROUND_ROBIN_CYCLE.shape[0]
        idx = jnp.mod(step_count, cycle_len)
        # All vehicles get the same type at any given step (driven by env-step).
        return jnp.broadcast_to(ROUND_ROBIN_CYCLE[idx], (N_VEHICLES,))
    if STRESS_ORDERING_MODEL == "front_loaded":
        # phase = first k for which step_count < FRONT_LOADED_BOUNDS[k]
        # Use jnp.searchsorted to find the phase index.
        phase = jnp.searchsorted(FRONT_LOADED_BOUNDS, step_count, side="right")
        phase = jnp.minimum(phase, FRONT_LOADED_ORDER.shape[0] - 1)
        return jnp.broadcast_to(FRONT_LOADED_ORDER[phase], (N_VEHICLES,))
    # Default — iid sampling (same as _sample_tasks distribution leg).
    return jax.random.choice(
        key, jnp.arange(3), shape=(N_VEHICLES,), p=TASK_ARRIVAL_PROBS)


def _sample_fleet(key: jax.Array):
    """Sample compute tier, is_ev, SoC, tx_power_w per vehicle."""
    k_tier, k_ev, k_soc = jax.random.split(key, 3)
    tiers = jax.random.choice(
        k_tier, jnp.arange(N_COMPUTE_TIERS), shape=(N_VEHICLES,),
        p=FLEET_TIER_PROBS,
    )
    ev_draw = jax.random.uniform(k_ev, (N_VEHICLES,))
    is_ev = ev_draw < FLEET_EV_PROB
    soc = jax.random.uniform(k_soc, (N_VEHICLES,), minval=EV_SOC_MIN, maxval=EV_SOC_MAX)
    soc = jnp.where(is_ev, soc, 1.0)

    # Tx power: EV → 20 dBm = 0.1 W; else → 23 dBm = ~0.1995 W.
    tx_power_dbm = jnp.where(is_ev, EV_TX_POWER_DBM, V2I_TX_POWER_DBM_ICE)
    tx_power_w = jnp.power(10.0, (tx_power_dbm - 30.0) / 10.0)
    return tiers, is_ev, soc, tx_power_w


def _sample_tasks(key: jax.Array, n: int):
    k_type, k_size = jax.random.split(key, 2)
    types = jax.random.choice(
        k_type, jnp.arange(3), shape=(n,), p=TASK_ARRIVAL_PROBS
    )
    mean_size = TASK_DATA_SIZE_MB_MEAN[types]
    noise = jax.random.uniform(k_size, (n,), minval=0.8, maxval=1.2)
    sizes = mean_size * noise
    return types, sizes


def reset_env(key: jax.Array, params: EnvParams | None = None) -> tuple[jax.Array, EnvState]:
    """Initialise a new episode."""
    k_fleet, k_pos, k_spd, k_task, k_lane, k_obs = jax.random.split(key, 6)
    tiers, is_ev, soc, tx_power_w = _sample_fleet(k_fleet)
    if TRACE_REPLAY_ENABLED:
        # Episode = random EPISODE_LENGTH window of the replayed trace.
        trace_t0 = jax.random.randint(
            k_pos, (), 0, TRACE_T_TOTAL - EPISODE_LENGTH - 1)
        m0 = TRACE_MASK[trace_t0]
        positions = jnp.where(m0[:, None], TRACE_POS[trace_t0], TRACE_PARK_XY)
        speeds = jnp.zeros(N_VEHICLES, dtype=jnp.float32)
    else:
        trace_t0 = jnp.int32(0)
        positions = jax.random.uniform(k_pos, (N_VEHICLES,), minval=0.0,
                                       maxval=HIGHWAY_LENGTH_M)
        speeds = jax.random.uniform(k_spd, (N_VEHICLES,), minval=VEHICLE_SPEED_MIN_KMH,
                                    maxval=VEHICLE_SPEED_MAX_KMH)
    task_type, task_data_size = _sample_tasks(k_task, N_VEHICLES)
    # Stress-mode fields. Defaults make them no-ops when corresponding flag is OFF.
    lane_id = _sample_lane_ids(k_lane)
    desired_speed = speeds  # OU target = initial speed; used only when SPEED enabled
    last_task_type = task_type  # Markov: prev type for first transition

    state = EnvState(
        positions=positions,
        speeds=speeds,
        compute_tier=tiers,
        is_ev=is_ev,
        soc=soc,
        tx_power_w=tx_power_w,
        queue_busy_ms=jnp.zeros(N_VEHICLES, dtype=jnp.float32),
        queue_depth=jnp.zeros(N_VEHICLES, dtype=jnp.int32),
        total_energy_j=jnp.zeros(N_VEHICLES, dtype=jnp.float32),
        rsu_busy_ms=jnp.zeros(N_RSUS, dtype=jnp.float32),
        rsu_load=jnp.zeros(N_RSUS, dtype=jnp.int32),
        task_type=task_type,
        task_data_size_mb=task_data_size,
        step_count=jnp.int32(0),
        tasks_total=jnp.int32(0),
        tasks_completed=jnp.int32(0),
        tasks_deadline_miss=jnp.int32(0),
        total_latency_ms=jnp.float32(0.0),
        actions_local=jnp.int32(0),
        actions_v2i=jnp.int32(0),
        actions_v2v=jnp.int32(0),
        total_reward=jnp.float32(0.0),
        lane_id=lane_id,
        desired_speed_kmh=desired_speed,
        last_task_type=last_task_type,
        n_arrivals_this_step=jnp.ones(N_VEHICLES, dtype=jnp.int32),
        trace_t=jnp.int32(trace_t0),
    )
    obs = get_obs_arr(k_obs, state)
    return obs, state


def step_env(key: jax.Array, state: EnvState,
             actions: jax.Array, params: EnvParams | None = None):
    """Advance the environment by one step.

    Args:
      actions: int32 [N_VEHICLES] ∈ {0,1,2}
    Returns:
      obs, state, rewards[N], dones[N] (all agents share done), info
    """
    params = params if params is not None else make_default_params()

    # Extra key streams for stress mechanisms (Poisson k, OU speed, ordering).
    k_links, k_actions, k_task, k_move, k_obs, k_poisson, k_ou, k_ord = jax.random.split(key, 8)

    # Precompute per-vehicle best RSU + best V2V target with one fading draw
    links = compute_per_vehicle_links(k_links, state)
    (best_rsu_idx, v2i_q, v2i_cap, best_rsu_ok,
     best_v2v_idx, v2v_q, v2v_cap, best_v2v_ok,
     _, _, _) = links

    # Process all agents in parallel (vmap)
    per_agent_keys = jax.random.split(k_actions, N_VEHICLES)
    veh_idxs = jnp.arange(N_VEHICLES)

    (rewards, latencies, energies, target_energies, deadline_mets,
     local_compute_ms, target_compute_ms, rsu_compute_ms) = jax.vmap(
        process_agent,
        in_axes=(0, 0, 0, None, 0, 0, 0, 0, 0, 0, 0, 0),
    )(per_agent_keys, actions, veh_idxs, state,
      best_rsu_idx, v2i_q, v2i_cap, best_rsu_ok,
      best_v2v_idx, v2v_q, v2v_cap, best_v2v_ok)

    # ------------------------------------------------------------------
    # Phase 4 stress — Model B Poisson arrivals:
    # Each vehicle's per-step outcomes (reward, energy, compute/RSU load)
    # scale by k_v ~ Poisson(λ). When STRESS_ARRIVAL_ENABLED is False, k_v=1
    # uniformly, so behaviour is identical to the base env. The action is
    # replicated to each of the k_v identical tasks.
    # ------------------------------------------------------------------
    k_arrivals = _sample_k_arrivals(k_poisson)  # [N] int32; 1 if stress off
    k_arrivals_f = k_arrivals.astype(jnp.float32)
    rewards = rewards * k_arrivals_f
    energies = energies * k_arrivals_f
    target_energies = target_energies * k_arrivals_f

    # Aggregate per-vehicle energies:
    #   source vehicle i: total_energy += energies[i]
    #   V2V target t:     total_energy += target_energies[i] for all i that targeted t
    src_energy = energies  # [N]
    # Scatter target_energies to their target indices
    tgt_energy = jnp.zeros(N_VEHICLES, dtype=jnp.float32).at[best_v2v_idx].add(
        target_energies
    )
    new_total_energy = state.total_energy_j + src_energy + tgt_energy

    # Update EV SoC: SoC -= (E / (B * 3.6e6)), clamped at 0.
    # Non-EVs: SoC stays at 1.0.
    per_vehicle_energy = src_energy + tgt_energy
    soc_drop = per_vehicle_energy / (EV_BATTERY_KWH * 3.6e6)  # kWh = 3.6e6 J
    new_soc = jnp.where(
        state.is_ev,
        jnp.maximum(state.soc - soc_drop, 0.0),
        state.soc,
    )

    # ------------------------------------------------------------------
    # Compute queue update: enqueue incoming tasks, then drain by 1 step.
    # Incoming tasks per vehicle v:
    #   + local:  source v's own local_compute_ms  (if action[v] == 0)
    #   + V2V:    target compute from any source s where action[s]==2 AND best_v2v_idx[s]==v
    # Queue full rejects the surplus tasks but keeps admitted ones.
    # ------------------------------------------------------------------
    # Local incoming: only vehicle i itself, gated on action==0. Scaled by k.
    local_incoming_ms = jnp.where(actions == 0, local_compute_ms * k_arrivals_f, 0.0)
    local_incoming_n = ((actions == 0).astype(jnp.int32)) * k_arrivals
    # V2V incoming: scatter target compute times into [N] by target index, scaled by k.
    v2v_valid = (actions == 2) & best_v2v_ok
    v2v_ms_by_src = jnp.where(v2v_valid, target_compute_ms * k_arrivals_f, 0.0)
    v2v_n_by_src = (v2v_valid.astype(jnp.int32)) * k_arrivals
    v2v_incoming_ms = jnp.zeros(N_VEHICLES, dtype=jnp.float32).at[best_v2v_idx].add(v2v_ms_by_src)
    v2v_incoming_n = jnp.zeros(N_VEHICLES, dtype=jnp.int32).at[best_v2v_idx].add(v2v_n_by_src)

    total_incoming_ms = local_incoming_ms + v2v_incoming_ms
    total_incoming_n = local_incoming_n + v2v_incoming_n

    # Admit only up to the remaining capacity, proportionally allocating
    # admitted compute time across admitted tasks.
    capacity = jnp.maximum(MAX_QUEUE_DEPTH - state.queue_depth, 0)
    admitted_n = jnp.minimum(total_incoming_n, capacity)
    accept_frac = jnp.where(
        total_incoming_n > 0,
        admitted_n.astype(jnp.float32) / jnp.maximum(total_incoming_n, 1).astype(jnp.float32),
        0.0,
    )
    admitted_ms = total_incoming_ms * accept_frac

    busy_after_admit = state.queue_busy_ms + admitted_ms
    depth_after_admit = state.queue_depth + admitted_n

    # Drain 1000 ms / step. Decay queue_depth proportionally to the
    # fraction of work drained: tasks_drained ≈ depth * (drained_ms / busy_ms).
    dt_ms = jnp.float32(1000.0)
    drained_ms = jnp.minimum(busy_after_admit, dt_ms)
    new_busy_ms = busy_after_admit - drained_ms
    # Proportional depth decay (integer floor; never leaves residual busy_ms
    # with zero depth — clamped below).
    drain_frac = jnp.where(
        busy_after_admit > 0,
        drained_ms / jnp.maximum(busy_after_admit, 1e-6),
        0.0,
    )
    tasks_drained = jnp.floor(depth_after_admit.astype(jnp.float32) * drain_frac).astype(jnp.int32)
    # If all backlog drained (new_busy_ms ≈ 0), force depth to 0.
    tasks_drained = jnp.where(new_busy_ms <= 0.0, depth_after_admit, tasks_drained)
    new_queue_depth = jnp.maximum(depth_after_admit - tasks_drained, 0)
    # If any backlog remains, keep at least one task in flight.
    new_queue_depth = jnp.where(
        (new_busy_ms > 0.0) & (new_queue_depth == 0),
        jnp.int32(1),
        new_queue_depth,
    )

    # RSU queue: symmetric to vehicle queue.
    #   + enqueue rsu_compute_ms on each V2I success (scatter to best_rsu_idx)
    #   + admit only up to MAX_RSU_CONCURRENT − current load
    #   + drain 1 s (1000 ms) per step with proportional depth decay
    is_v2i_success = (actions == 1) & best_rsu_ok
    rsu_ms_by_src = jnp.where(is_v2i_success, rsu_compute_ms * k_arrivals_f, 0.0)
    rsu_n_by_src = (is_v2i_success.astype(jnp.int32)) * k_arrivals
    rsu_incoming_ms = jnp.zeros(N_RSUS, dtype=jnp.float32).at[best_rsu_idx].add(rsu_ms_by_src)
    rsu_incoming_n = jnp.zeros(N_RSUS, dtype=jnp.int32).at[best_rsu_idx].add(rsu_n_by_src)

    rsu_capacity = jnp.maximum(RSU_MAX_CONCURRENT - state.rsu_load, 0)
    rsu_admitted_n = jnp.minimum(rsu_incoming_n, rsu_capacity)
    rsu_accept_frac = jnp.where(
        rsu_incoming_n > 0,
        rsu_admitted_n.astype(jnp.float32) / jnp.maximum(rsu_incoming_n, 1).astype(jnp.float32),
        0.0,
    )
    rsu_admitted_ms = rsu_incoming_ms * rsu_accept_frac

    rsu_busy_after_admit = state.rsu_busy_ms + rsu_admitted_ms
    rsu_load_after_admit = state.rsu_load + rsu_admitted_n

    rsu_dt_ms = jnp.float32(1000.0)
    rsu_drained_ms = jnp.minimum(rsu_busy_after_admit, rsu_dt_ms)
    new_rsu_busy_ms = rsu_busy_after_admit - rsu_drained_ms
    rsu_drain_frac = jnp.where(
        rsu_busy_after_admit > 0,
        rsu_drained_ms / jnp.maximum(rsu_busy_after_admit, 1e-6),
        0.0,
    )
    rsu_tasks_drained = jnp.floor(
        rsu_load_after_admit.astype(jnp.float32) * rsu_drain_frac
    ).astype(jnp.int32)
    rsu_tasks_drained = jnp.where(
        new_rsu_busy_ms <= 0.0, rsu_load_after_admit, rsu_tasks_drained)
    new_rsu_load = jnp.maximum(rsu_load_after_admit - rsu_tasks_drained, 0)
    new_rsu_load = jnp.where(
        (new_rsu_busy_ms > 0.0) & (new_rsu_load == 0),
        jnp.int32(1),
        new_rsu_load,
    )

    # Action counters — scale by k arrivals for Model B (one action replicates).
    n_local = jnp.sum((actions == 0).astype(jnp.int32) * k_arrivals)
    n_v2i = jnp.sum((actions == 1).astype(jnp.int32) * k_arrivals)
    n_v2v = jnp.sum((actions == 2).astype(jnp.int32) * k_arrivals)
    n_done_ok = jnp.sum(deadline_mets.astype(jnp.int32) * k_arrivals)
    n_missed = jnp.sum(((~deadline_mets).astype(jnp.int32)) * k_arrivals)
    # Per-step latency sum — scaled by k arrivals to mirror Model-B
    # (each "decision" represents k identical tasks).
    step_latency_sum_ms = jnp.sum(latencies * k_arrivals_f)
    # Total task count this step also scales with k.
    n_step_tasks = jnp.sum(k_arrivals)

    # Phase 4 stress — OU speed evolution. Update actual speed toward
    # per-vehicle desired_speed_kmh. No-op when STRESS_SPEED_ENABLED is False.
    new_speeds_kmh = _evolve_speeds_ou(k_ou, state.speeds,
                                       state.desired_speed_kmh)

    # Update positions (dt=1s) using the freshly-evolved speeds.
    speed_ms = new_speeds_kmh / 3.6
    new_positions = jnp.mod(state.positions + speed_ms, HIGHWAY_LENGTH_M)

    # Phase 4 stress — ordering-aware next task sampling.
    if STRESS_ORDERING_MODEL == "iid":
        next_types, next_sizes = _sample_tasks(k_task, N_VEHICLES)
    else:
        next_types = _sample_task_types_ordered(
            k_ord, state.step_count + 1, state.task_type)
        # Sample sizes (same ±20 % noise as base _sample_tasks).
        mean_size = TASK_DATA_SIZE_MB_MEAN[next_types]
        size_noise = jax.random.uniform(k_task, (N_VEHICLES,),
                                        minval=0.8, maxval=1.2)
        next_sizes = mean_size * size_noise

    step_count = state.step_count + 1
    done_scalar = step_count >= params.episode_length
    dones = jnp.full(N_VEHICLES, done_scalar)

    new_state = EnvState(
        positions=new_positions,
        speeds=new_speeds_kmh,
        compute_tier=state.compute_tier,
        is_ev=state.is_ev,
        soc=new_soc,
        tx_power_w=state.tx_power_w,
        queue_busy_ms=new_busy_ms,
        queue_depth=new_queue_depth,
        total_energy_j=new_total_energy,
        rsu_busy_ms=new_rsu_busy_ms,
        rsu_load=new_rsu_load,
        task_type=next_types,
        task_data_size_mb=next_sizes,
        step_count=step_count,
        tasks_total=state.tasks_total + n_step_tasks,
        tasks_completed=state.tasks_completed + n_done_ok,
        tasks_deadline_miss=state.tasks_deadline_miss + n_missed,
        total_latency_ms=state.total_latency_ms + step_latency_sum_ms,
        actions_local=state.actions_local + n_local,
        actions_v2i=state.actions_v2i + n_v2i,
        actions_v2v=state.actions_v2v + n_v2v,
        total_reward=state.total_reward + jnp.sum(rewards),
        # Stress fields passthrough / updates
        lane_id=state.lane_id,                       # constant per episode
        desired_speed_kmh=state.desired_speed_kmh,   # OU target constant per episode
        last_task_type=state.task_type,              # previous step's type → Markov
        n_arrivals_this_step=k_arrivals,
    )

    obs = get_obs_arr(k_obs, new_state)
    # Per-step per-agent energy for logging (source + V2V-target debit attributed
    # to the source agent so the row-sum equals the fleet's per-step total).
    per_step_energy_j = src_energy + tgt_energy  # [N]
    # Fleet-cumulative totals for episode-level avg_energy_j reporting.
    fleet_total_energy_j = jnp.sum(new_state.total_energy_j)
    # avg_energy_j_per_task = fleet_total_energy / tasks_total (mirrors the
    # reference `metrics["total_energy_j"] / metrics["tasks_total"]` in
    # /scratch/vec-offloading/env/vec_offloading_env.py::get_metrics).
    avg_energy_j_per_task = fleet_total_energy_j / jnp.maximum(
        new_state.tasks_total.astype(jnp.float32), 1.0
    )
    # avg_latency_ms = total_latency / tasks_total (mirrors the reference
    # PyTorch env's `metrics["total_latency_ms"] / metrics["tasks_total"]`).
    avg_latency_ms_per_task = new_state.total_latency_ms / jnp.maximum(
        new_state.tasks_total.astype(jnp.float32), 1.0
    )
    # Per-agent task type of the just-processed step (for per-type completion
    # logging). state.task_type holds the tasks that were acted on in this step
    # (the new tasks are in new_state.task_type / next_types).
    step_task_type = state.task_type                # int32 [N] ∈ {0,1,2}
    info = {
        "latency_ms": latencies,
        "energy_j": energies,                     # per-agent per-step source energy
        "per_step_energy_j": per_step_energy_j,   # per-agent per-step total (src + v2v_tgt debit)
        "deadline_met": deadline_mets,
        "task_type": step_task_type,              # int32 [N], task that was just processed
        "completion_rate": new_state.tasks_completed / jnp.maximum(new_state.tasks_total, 1),
        "fleet_total_energy_j": fleet_total_energy_j,
        "avg_energy_j_per_task": avg_energy_j_per_task,
        "avg_latency_ms_per_task": avg_latency_ms_per_task,
        # Per-step fleet-total latency (k-scaled), for host-side episode accum.
        "step_latency_sum_ms": step_latency_sum_ms,
    }
    return obs, new_state, rewards, dones, info


# ================================================================
# Model-C step (D2-A port)
# ================================================================
# Within a step, iterate K_MAX_STRESS sub-steps. Each sub-step:
#   - active mask = (sub_idx < k_arrivals[v])
#   - active vehicles each process ONE task with current queue state
#   - queue states evolve TASK-BY-TASK (not k-scaled in lump like Model-B)
# After all sub-steps, drain queue by 1000 ms (once), advance physics.

def _sample_k_max_task_slots(key: jax.Array):
    """Pre-sample K_MAX task types + sizes per vehicle (one slot per sub-step).
    Returns:
      types_slots: int32 [K_MAX, N]
      sizes_slots: float32 [K_MAX, N]
    Each slot is sampled iid from TASK_ARRIVAL_PROBS (only iid ordering for now;
    Markov/round-robin/front-loaded retain the existing per-step single-task path).
    """
    keys = jax.random.split(key, K_MAX_STRESS)
    def one_slot(k):
        types, sizes = _sample_tasks(k, N_VEHICLES)
        return types, sizes
    types_slots, sizes_slots = jax.vmap(one_slot)(keys)
    return types_slots, sizes_slots


def step_env_model_c(key: jax.Array, state: EnvState,
                     actions: jax.Array, params: EnvParams | None = None):
    """Model-C variant: within-step k-task sequential queue accumulation.

    Same signature and return as step_env. Use when VEC_JAX_MODEL_C=1.
    """
    params = params if params is not None else make_default_params()

    k_links, k_actions_base, k_task, k_move, k_obs, k_poisson, k_ou, k_ord, k_slots = jax.random.split(key, 9)

    if TRACE_REPLAY_ENABLED:
        # Inactive (parked) vehicles carry no queue and generate no arrivals —
        # mirrors eval_sumo_stage1_mc.py's per-step masking exactly.
        _act_now = TRACE_MASK[state.trace_t]
        state = state._replace(
            queue_busy_ms=jnp.where(_act_now, state.queue_busy_ms, 0.0),
            queue_depth=jnp.where(_act_now, state.queue_depth, 0))

    # Channel links computed ONCE at start (do not change within step)
    links = compute_per_vehicle_links(k_links, state)
    (best_rsu_idx, v2i_q, v2i_cap, best_rsu_ok,
     best_v2v_idx, v2v_q, v2v_cap, best_v2v_ok,
     _, _, _) = links

    # Sample per-vehicle k arrivals + per-slot task types/sizes
    k_arrivals = _sample_k_arrivals(k_poisson)  # [N]
    if TRACE_REPLAY_ENABLED:
        k_arrivals = k_arrivals * _act_now.astype(jnp.int32)
    types_slots, sizes_slots = _sample_k_max_task_slots(k_slots)  # [K_MAX, N]

    # Pre-split per-substep action keys so process_agent gets fresh randomness
    sub_action_keys_base = jax.random.split(k_actions_base, K_MAX_STRESS)  # [K_MAX, 2]

    # Initial per-vehicle accumulators
    init_totals = {
        "reward_sum":      jnp.zeros(N_VEHICLES, dtype=jnp.float32),
        "energy_sum":      jnp.zeros(N_VEHICLES, dtype=jnp.float32),
        "target_e_sum":    jnp.zeros(N_VEHICLES, dtype=jnp.float32),
        "latency_sum":     jnp.zeros(N_VEHICLES, dtype=jnp.float32),
        "deadline_met_n":  jnp.zeros(N_VEHICLES, dtype=jnp.int32),
        "n_processed":     jnp.zeros(N_VEHICLES, dtype=jnp.int32),
        # Type-level counters (3 types)
        "type_n":          jnp.zeros((N_VEHICLES, 3), dtype=jnp.int32),
        "type_done_n":     jnp.zeros((N_VEHICLES, 3), dtype=jnp.int32),
    }

    # Initial state-for-substeps (start with the env state at step entry;
    # this gets mutated each sub-step as the queue evolves).
    # We override task_type/size per sub-step.
    def sub_step(carry, sub_idx):
        s, totals = carry

        # active mask
        active = (sub_idx < k_arrivals)  # [N] bool
        active_f = active.astype(jnp.float32)

        # task types/sizes for this slot
        slot_types = types_slots[sub_idx]
        slot_sizes = sizes_slots[sub_idx]

        # Build a sub-step state with the slot's task info
        s_sub = s._replace(
            task_type=slot_types,
            task_data_size_mb=slot_sizes,
        )

        # Per-agent keys this sub-step
        sub_keys = jax.random.split(sub_action_keys_base[sub_idx], N_VEHICLES)

        # vmap process_agent (re-uses links from step start — channel quality
        # doesn't change within step).
        (rewards, latencies, energies, target_energies, deadline_mets,
         local_compute_ms, target_compute_ms, rsu_compute_ms) = jax.vmap(
            process_agent,
            in_axes=(0, 0, 0, None, 0, 0, 0, 0, 0, 0, 0, 0),
        )(sub_keys, actions, jnp.arange(N_VEHICLES), s_sub,
          best_rsu_idx, v2i_q, v2i_cap, best_rsu_ok,
          best_v2v_idx, v2v_q, v2v_cap, best_v2v_ok)

        # Mask outputs by active (inactive vehicles contribute zero this sub-step).
        rewards_a = rewards * active_f
        latencies_a = latencies * active_f
        energies_a = energies * active_f
        target_energies_a = target_energies * active_f
        deadline_mets_a = deadline_mets & active  # bool
        local_compute_ms_a = local_compute_ms * active_f
        target_compute_ms_a = target_compute_ms * active_f
        rsu_compute_ms_a = rsu_compute_ms * active_f

        # Per-task queue updates (no k-scaling — these are PER-TASK contributions)
        local_inc_ms = jnp.where(active & (actions == 0), local_compute_ms_a, 0.0)
        local_inc_n = (active & (actions == 0)).astype(jnp.int32)
        v2v_valid = active & (actions == 2) & best_v2v_ok
        v2v_ms_by_src = jnp.where(v2v_valid, target_compute_ms_a, 0.0)
        v2v_n_by_src = v2v_valid.astype(jnp.int32)
        v2v_inc_ms = jnp.zeros(N_VEHICLES, dtype=jnp.float32).at[best_v2v_idx].add(v2v_ms_by_src)
        v2v_inc_n = jnp.zeros(N_VEHICLES, dtype=jnp.int32).at[best_v2v_idx].add(v2v_n_by_src)
        total_inc_ms = local_inc_ms + v2v_inc_ms
        total_inc_n = local_inc_n + v2v_inc_n

        # Vehicle queue admit (capacity check)
        capacity = jnp.maximum(MAX_QUEUE_DEPTH - s.queue_depth, 0)
        admitted_n = jnp.minimum(total_inc_n, capacity)
        accept_frac = jnp.where(
            total_inc_n > 0,
            admitted_n.astype(jnp.float32) / jnp.maximum(total_inc_n, 1).astype(jnp.float32),
            0.0,
        )
        admitted_ms = total_inc_ms * accept_frac
        new_busy_ms = s.queue_busy_ms + admitted_ms
        new_depth = s.queue_depth + admitted_n

        # RSU queue admit
        is_v2i = active & (actions == 1) & best_rsu_ok
        rsu_inc_ms_src = jnp.where(is_v2i, rsu_compute_ms_a, 0.0)
        rsu_inc_n_src = is_v2i.astype(jnp.int32)
        rsu_inc_ms = jnp.zeros(N_RSUS, dtype=jnp.float32).at[best_rsu_idx].add(rsu_inc_ms_src)
        rsu_inc_n = jnp.zeros(N_RSUS, dtype=jnp.int32).at[best_rsu_idx].add(rsu_inc_n_src)
        rsu_cap = jnp.maximum(RSU_MAX_CONCURRENT - s.rsu_load, 0)
        rsu_admitted_n = jnp.minimum(rsu_inc_n, rsu_cap)
        rsu_accept_frac = jnp.where(
            rsu_inc_n > 0,
            rsu_admitted_n.astype(jnp.float32) / jnp.maximum(rsu_inc_n, 1).astype(jnp.float32),
            0.0,
        )
        rsu_admitted_ms = rsu_inc_ms * rsu_accept_frac
        new_rsu_busy = s.rsu_busy_ms + rsu_admitted_ms
        new_rsu_load = s.rsu_load + rsu_admitted_n

        # Update state (NO drain within sub-step; drain happens once after K_MAX subs)
        new_s = s._replace(
            queue_busy_ms=new_busy_ms,
            queue_depth=new_depth,
            rsu_busy_ms=new_rsu_busy,
            rsu_load=new_rsu_load,
            # Don't update task_type here — it gets used by next sub_step's slot;
            # we override via s_sub each call. The carry's task_type is irrelevant.
        )

        # Update per-vehicle totals
        # Type counters: increment type_n[v, slot_types[v]] for active vehicles
        type_onehot = jax.nn.one_hot(slot_types, 3, dtype=jnp.int32)  # [N, 3]
        type_inc = type_onehot * active.astype(jnp.int32)[:, None]
        type_done_inc = type_onehot * deadline_mets_a.astype(jnp.int32)[:, None]
        new_totals = {
            "reward_sum":     totals["reward_sum"] + rewards_a,
            "energy_sum":     totals["energy_sum"] + energies_a,
            "target_e_sum":   totals["target_e_sum"] + target_energies_a,
            "latency_sum":    totals["latency_sum"] + latencies_a,
            "deadline_met_n": totals["deadline_met_n"] + deadline_mets_a.astype(jnp.int32),
            "n_processed":    totals["n_processed"] + active.astype(jnp.int32),
            "type_n":         totals["type_n"] + type_inc,
            "type_done_n":    totals["type_done_n"] + type_done_inc,
        }
        return (new_s, new_totals), None

    (after_subs_state, totals), _ = jax.lax.scan(
        sub_step, (state, init_totals), jnp.arange(K_MAX_STRESS))

    # ============================================================
    # Post-sub-step: aggregate per-vehicle outcomes; drain queue by 1000 ms.
    # ============================================================
    rewards = totals["reward_sum"]
    src_energy = totals["energy_sum"]
    target_energies_total = totals["target_e_sum"]

    # Scatter target_energies (already on source side) to target vehicles
    # Actually target_energies are aggregated per-source; for V2V the energy
    # is debited to the V2V target. We need to scatter the per-sub-step
    # target_e to best_v2v_idx. Since process_agent's target_energy is gated
    # on action==V2V AND ok, and the source's target stays the same across
    # sub-steps (best_v2v_idx is constant within a step), the scatter target
    # is the same for all sub-steps — we can scatter the SUM.
    tgt_energy = jnp.zeros(N_VEHICLES, dtype=jnp.float32).at[best_v2v_idx].add(
        target_energies_total
    )
    new_total_energy = state.total_energy_j + src_energy + tgt_energy

    # EV SoC update
    per_vehicle_energy = src_energy + tgt_energy
    soc_drop = per_vehicle_energy / (EV_BATTERY_KWH * 3.6e6)
    new_soc = jnp.where(state.is_ev, jnp.maximum(state.soc - soc_drop, 0.0), state.soc)

    # Drain vehicle queue once: 1000 ms
    dt_ms = jnp.float32(1000.0)
    busy_pre_drain = after_subs_state.queue_busy_ms
    depth_pre_drain = after_subs_state.queue_depth
    drained_ms = jnp.minimum(busy_pre_drain, dt_ms)
    new_busy_ms = busy_pre_drain - drained_ms
    drain_frac = jnp.where(busy_pre_drain > 0,
                           drained_ms / jnp.maximum(busy_pre_drain, 1e-6), 0.0)
    tasks_drained = jnp.floor(depth_pre_drain.astype(jnp.float32) * drain_frac).astype(jnp.int32)
    tasks_drained = jnp.where(new_busy_ms <= 0.0, depth_pre_drain, tasks_drained)
    new_queue_depth = jnp.maximum(depth_pre_drain - tasks_drained, 0)
    new_queue_depth = jnp.where(
        (new_busy_ms > 0.0) & (new_queue_depth == 0), jnp.int32(1), new_queue_depth)

    # Drain RSU queue once: 1000 ms
    rsu_busy_pre_drain = after_subs_state.rsu_busy_ms
    rsu_load_pre_drain = after_subs_state.rsu_load
    rsu_drained_ms = jnp.minimum(rsu_busy_pre_drain, dt_ms)
    new_rsu_busy_ms = rsu_busy_pre_drain - rsu_drained_ms
    rsu_drain_frac = jnp.where(rsu_busy_pre_drain > 0,
                               rsu_drained_ms / jnp.maximum(rsu_busy_pre_drain, 1e-6), 0.0)
    rsu_tasks_drained = jnp.floor(rsu_load_pre_drain.astype(jnp.float32) * rsu_drain_frac).astype(jnp.int32)
    rsu_tasks_drained = jnp.where(new_rsu_busy_ms <= 0.0, rsu_load_pre_drain, rsu_tasks_drained)
    new_rsu_load = jnp.maximum(rsu_load_pre_drain - rsu_tasks_drained, 0)
    new_rsu_load = jnp.where(
        (new_rsu_busy_ms > 0.0) & (new_rsu_load == 0), jnp.int32(1), new_rsu_load)

    # Action counters
    # In Model-C, ONE decision per vehicle per step, but k tasks processed
    # under that decision. Count the decisions × k (matches Model-B totals).
    n_local = jnp.sum((actions == 0).astype(jnp.int32) * k_arrivals)
    n_v2i = jnp.sum((actions == 1).astype(jnp.int32) * k_arrivals)
    n_v2v = jnp.sum((actions == 2).astype(jnp.int32) * k_arrivals)
    n_done_ok = jnp.sum(totals["deadline_met_n"])
    n_step_tasks = jnp.sum(totals["n_processed"])
    n_missed = n_step_tasks - n_done_ok
    step_latency_sum_ms = jnp.sum(totals["latency_sum"])

    # Mobility: trace replay (positions from the FCD trace) or the synthetic
    # OU/corridor movement (default).
    if TRACE_REPLAY_ENABLED:
        _t_next = jnp.minimum(state.trace_t + 1, TRACE_T_TOTAL - 1)
        _m_next = TRACE_MASK[_t_next]
        new_positions = jnp.where(_m_next[:, None], TRACE_POS[_t_next], TRACE_PARK_XY)
        new_speeds_kmh = jnp.zeros(N_VEHICLES, dtype=jnp.float32)
    else:
        _t_next = state.trace_t
        new_speeds_kmh = _evolve_speeds_ou(k_ou, state.speeds, state.desired_speed_kmh)
        speed_ms = new_speeds_kmh / 3.6
        new_positions = jnp.mod(state.positions + speed_ms, HIGHWAY_LENGTH_M)

    # Next-step OBSERVATION task: a single sampled task per vehicle (the agent
    # only sees one task in obs at decision time; the env then samples k arrivals
    # internally for that step). Match Model-B convention.
    if STRESS_ORDERING_MODEL == "iid":
        next_types, next_sizes = _sample_tasks(k_task, N_VEHICLES)
    else:
        next_types = _sample_task_types_ordered(k_ord, state.step_count + 1, state.task_type)
        mean_size = TASK_DATA_SIZE_MB_MEAN[next_types]
        size_noise = jax.random.uniform(k_task, (N_VEHICLES,), minval=0.8, maxval=1.2)
        next_sizes = mean_size * size_noise

    step_count = state.step_count + 1
    done_scalar = step_count >= params.episode_length
    dones = jnp.full(N_VEHICLES, done_scalar)

    new_state = EnvState(
        positions=new_positions,
        speeds=new_speeds_kmh,
        compute_tier=state.compute_tier,
        is_ev=state.is_ev,
        soc=new_soc,
        tx_power_w=state.tx_power_w,
        queue_busy_ms=new_busy_ms,
        queue_depth=new_queue_depth,
        total_energy_j=new_total_energy,
        rsu_busy_ms=new_rsu_busy_ms,
        rsu_load=new_rsu_load,
        task_type=next_types,
        task_data_size_mb=next_sizes,
        step_count=step_count,
        tasks_total=state.tasks_total + n_step_tasks,
        tasks_completed=state.tasks_completed + n_done_ok,
        tasks_deadline_miss=state.tasks_deadline_miss + n_missed,
        total_latency_ms=state.total_latency_ms + step_latency_sum_ms,
        actions_local=state.actions_local + n_local,
        actions_v2i=state.actions_v2i + n_v2i,
        actions_v2v=state.actions_v2v + n_v2v,
        total_reward=state.total_reward + jnp.sum(rewards),
        lane_id=state.lane_id,
        desired_speed_kmh=state.desired_speed_kmh,
        last_task_type=state.task_type,
        n_arrivals_this_step=k_arrivals,
        trace_t=_t_next,
    )

    obs = get_obs_arr(k_obs, new_state)
    per_step_energy_j = src_energy + tgt_energy
    fleet_total_energy_j = jnp.sum(new_state.total_energy_j)
    avg_energy_j_per_task = fleet_total_energy_j / jnp.maximum(new_state.tasks_total.astype(jnp.float32), 1.0)
    avg_latency_ms_per_task = new_state.total_latency_ms / jnp.maximum(new_state.tasks_total.astype(jnp.float32), 1.0)

    # task_type used for per-type completion logging: dominant slot 0 type
    # (closest to "the task in obs"). For accurate per-type, the host-side
    # uses totals["type_n"] / totals["type_done_n"] — but the existing host
    # script expects per-step task_type[N] and deadline_met[N], so we
    # approximate via slot 0 (which is always the first arrival).
    step_task_type = types_slots[0]
    # deadline_met[N] for host accounting: aggregate as (deadline_met_n > 0)
    # — at least one of the k tasks met deadline. Imperfect proxy for the
    # host's deadline_met-as-boolean expectation, but consistent with
    # treating the "step's decision" as a single yes/no outcome.
    step_deadline_met = totals["deadline_met_n"] >= totals["n_processed"]
    step_deadline_met = jnp.where(totals["n_processed"] > 0, step_deadline_met, jnp.bool_(True))

    info = {
        "latency_ms": totals["latency_sum"] / jnp.maximum(totals["n_processed"], 1).astype(jnp.float32),
        "energy_j": src_energy,
        "per_step_energy_j": per_step_energy_j,
        "deadline_met": step_deadline_met,
        "task_type": step_task_type,
        "completion_rate": new_state.tasks_completed / jnp.maximum(new_state.tasks_total, 1),
        "fleet_total_energy_j": fleet_total_energy_j,
        "avg_energy_j_per_task": avg_energy_j_per_task,
        "avg_latency_ms_per_task": avg_latency_ms_per_task,
        "step_latency_sum_ms": step_latency_sum_ms,
        # Model-C-only: exact per-type counts this step (useful for accurate host stats)
        "type_n": totals["type_n"],
        "type_done_n": totals["type_done_n"],
    }
    return obs, new_state, rewards, dones, info


def step_env_dispatch(key: jax.Array, state: EnvState,
                      actions: jax.Array, params: EnvParams | None = None):
    """Dispatch between Model-B (default) and Model-C based on VEC_JAX_MODEL_C."""
    if MODEL_C_ENABLED:
        return step_env_model_c(key, state, actions, params)
    return step_env(key, state, actions, params)
