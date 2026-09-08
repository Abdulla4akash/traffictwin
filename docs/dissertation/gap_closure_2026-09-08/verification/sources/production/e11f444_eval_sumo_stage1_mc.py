#!/usr/bin/env python
"""Stage-1 eval — MODEL-C faithful (JIT/lax.scan).

Supersedes eval_sumo_stage1_jit.py, which transcribed step_env (Model B:
single shared task type per vehicle, single k-weighted process_agent call).
The frozen policy was TRAINED on step_env_model_c (Model C): per-arrival
heterogeneous task types + a K_MAX-substep SEQUENTIAL within-step queue
accumulation, drained once per second. The integrity check showed the Model-B
transcription inflated synthetic completion 0.91 -> 0.993. This file mirrors
step_env_model_c exactly, while keeping the 2B eval machinery: pad-to-maxN +
active mask, 2D-Euclidean distance, RSU positions from the trace, JIT scan.

Outer scan = time (T seconds). Inner scan = the K_MAX task substeps per second
(this is the piece Model B was missing).
"""
import os, sys, argparse, json, time
# --cap-scalar must take effect BEFORE env.vec_jax import (module-level
# constants), hence this pre-argparse sniff. Enables the 13-dim capscalar
# obs variant (tier one-hots -> continuous capability scalar).
if "--cap-scalar" in sys.argv:
    os.environ["VEC_JAX_CAP_SCALAR"] = "1"
# dose-response knobs (Layer-2 causality tests) — both pre-import
if "--lambda-arrival" in sys.argv:
    os.environ["VEC_JAX_LAMBDA_ARRIVAL"] = sys.argv[sys.argv.index("--lambda-arrival") + 1]
if "--rsu-service-mult" in sys.argv:
    os.environ["VEC_JAX_RSU_SERVICE_MULT"] = sys.argv[sys.argv.index("--rsu-service-mult") + 1]
os.environ.setdefault("VEC_JAX_MODEL_C", "1")
os.environ.setdefault("VEC_JAX_PRIORITY_ALPHA", "0")
os.environ.setdefault("VEC_JAX_STRESS_ARRIVAL", "1")
os.environ.setdefault("VEC_JAX_LAMBDA_ARRIVAL", "1.5")
os.environ.setdefault("VEC_JAX_K_MIN", "0")
os.environ.setdefault("VEC_JAX_K_MAX", "5")
os.environ.setdefault("VEC_JAX_STRESS_SPEED", "0")
os.environ.setdefault("VEC_JAX_STRESS_LANES", "0")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

import numpy as np
import jax, jax.numpy as jnp
from e2_path_instrumentation import summarise_v2i_paths
REPO = os.path.expanduser("~/scratch/vec-offloading-jaxmarl-fullport")
sys.path.insert(0, REPO)
import env.vec_jax as V

PARK = 1.0e7


def euclid(a, b):
    return jnp.sqrt(jnp.sum((a - b) ** 2, axis=-1))


def load_actor(path):
    d = np.load(path)
    W = [jnp.asarray(d[f"Dense_{i}.kernel"]) for i in range(3)]
    b = [jnp.asarray(d[f"Dense_{i}.bias"]) for i in range(3)]
    def apply(o):
        h = jnp.tanh(o @ W[0] + b[0]); h = jnp.tanh(h @ W[1] + b[1])
        return h @ W[2] + b[2]
    return apply


# --- SetofExperiments_2B §A.7: per-country fleet composition presets. ------
# ev_prob = indicative BEV *parc* (stock) share from public national stats;
# tier_probs = (rpi, jetson, gpu_vehicle) compute-tier mix — a country-
# parameterised MODELLING ASSUMPTION tied to fleet-modernity proxies, not a
# measured statistic (§A.7). "synthetic" = the training fleet (_sample_fleet
# defaults: tiers 0.70/0.25/0.05, EV 0.30) — an obs-DISTRIBUTION shift only,
# so the frozen policy applies zero-shot (§2.12).
FLEET_PRESETS = {
    "synthetic": None,  # use V._sample_fleet unchanged
    # CAMPAIGN presets — the 2B_1 two-level fleet design: training fleet vs
    # national-PLAN 2030 fleet (§A.7). 2030 ev_prob = national target compounded
    # through parc turnover; tier_probs = fleet-modernity assumption.
    "uk2030": {"ev_prob": 0.22, "tier_probs": (0.40, 0.35, 0.25),
               "source": "UK ZEV mandate trajectory -> ~2030 BEV parc (indicative)"},
    "de2030": {"ev_prob": 0.30, "tier_probs": (0.40, 0.35, 0.25),
               "source": "DE 15M-EV-2030 target vs ~49M Pkw stock (indicative)"},
    "id2030": {"ev_prob": 0.10, "tier_probs": (0.70, 0.25, 0.05),
               "source": "Perpres 55-2019: 2M EV cars 2030 vs ~20M car parc (indicative)"},
    # DIAGNOSTIC extremes (Layer-2 fleet-gradient dose-response; ev fixed at
    # 0.22 to isolate the compute-tier axis)
    "allrpi": {"ev_prob": 0.22, "tier_probs": (1.0, 0.0, 0.0),
               "source": "diagnostic extreme — all rpi-class"},
    "allgpu": {"ev_prob": 0.22, "tier_probs": (0.0, 0.0, 1.0),
               "source": "diagnostic extreme — all gpu-class"},
    # EXPLORATORY (~2024 parc) — not part of the campaign; kept for the
    # 2026-07-13 single-draw UK finding (over-offload-to-V2I mechanism).
    "uk": {"ev_prob": 0.04,  "tier_probs": (0.60, 0.30, 0.10),
           "source": "DfT vehicle-licensing / SMMT, BEV car parc ~2024 (indicative)"},
    "de": {"ev_prob": 0.03,  "tier_probs": (0.60, 0.30, 0.10),
           "source": "KBA Bestand, BEV Pkw stock ~2024 (indicative)"},
    "id": {"ev_prob": 0.003, "tier_probs": (0.85, 0.13, 0.02),
           "source": "Gaikindo / Perpres 55-2019 roadmap, EV parc <1% (indicative)"},
}


def sample_fleet_region(key, n, preset):
    """Region fleet draw mirroring V._sample_fleet (same key-split order,
    same SoC and tx-power rules) with §A.7 country ev_prob / tier_probs."""
    k_tier, k_ev, k_soc = jax.random.split(key, 3)
    tiers = jax.random.choice(
        k_tier, jnp.arange(V.N_COMPUTE_TIERS), shape=(n,),
        p=jnp.asarray(preset["tier_probs"]))
    is_ev = jax.random.uniform(k_ev, (n,)) < preset["ev_prob"]
    soc = jax.random.uniform(k_soc, (n,), minval=V.EV_SOC_MIN, maxval=V.EV_SOC_MAX)
    soc = jnp.where(is_ev, soc, 1.0)
    tx_power_dbm = jnp.where(is_ev, V.EV_TX_POWER_DBM, V.V2I_TX_POWER_DBM_ICE)
    tx_power_w = jnp.power(10.0, (tx_power_dbm - 30.0) / 10.0)
    return tiers, is_ev, soc, tx_power_w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--actor", required=True)
    ap.add_argument("--rsu-cap-per-veh", type=float, default=50.0 / 20.0,
                    help="per-RSU admission/in-flight task ceiling as a RATIO "
                         "of the padded fleet width (training parity: the "
                         "policy trained with cap 50 for 20 vehicles). The "
                         "resolved absolute value is recorded per run as "
                         "rsu_max_concurrent.")
    ap.add_argument("--rsu-cap-abs", type=int, default=-1,
                    help="ABSOLUTE per-RSU admission/in-flight ceiling (tasks) "
                         "— overrides --rsu-cap-per-veh when > 0. Robustness "
                         "arm (2026-08-05, after Abdulla's cross-trace "
                         "question): a physical buffer does not grow with the "
                         "scenario's vehicle count, so cross-trace physical "
                         "claims should be checked under a fixed absolute cap.")
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fleet", default="synthetic", choices=sorted(FLEET_PRESETS),
                    help="fleet composition preset (SetofExperiments_2B §A.7)")
    ap.add_argument("--fleet-seed", type=int, default=-1,
                    help="separate PRNG seed for the fleet draw only (task stream "
                         "unchanged); -1 = derive from --seed (legacy-exact)")
    ap.add_argument("--cap-scalar", action="store_true",
                    help="13-dim capscalar obs variant (handled pre-import; "
                         "flag declared here for --help and JSON provenance)")
    ap.add_argument("--per-step-out", default="",
                    help="npz path: per-step time series + per-vehicle "
                         "trajectories + per-RSU state (additive; physics "
                         "unchanged)")
    ap.add_argument("--lambda-arrival", default="",
                    help="override arrival rate lambda (pre-import; provenance only here)")
    ap.add_argument("--rsu-service-mult", default="",
                    help="scale RSU service rate (pre-import; provenance only here)")
    ap.add_argument("--per-task-out", default="",
                    help="npz path: per-task log [T,KMAX,N] (type, latency, "
                         "met, active, outcome, and native V2I ingress / "
                         "selected-target / actual-execution / forwarding / "
                         "admission paths) — large; use for selected runs only")
    ap.add_argument("--rsu-lb", default="off",
                    choices=["off", "jsq", "p2c", "dla", "dla_p2c"],
                    help="inter-RSU load balancer over fiber backhaul: radio "
                         "association unchanged (ingress = best RSU); the "
                         "EXECUTING RSU is chosen per task substep — jsq = "
                         "least-backlog RSU, p2c = power-of-two-choices, "
                         "dla = jsq placement + deadline-aware admission "
                         "(reject early when the target queue already exceeds "
                         "the task's deadline; rejected work leaves the system), "
                         "dla_p2c = the same gate on p2c placement — spreads a "
                         "substep's tasks over RSUs instead of piling them on "
                         "one argmin, which matters once --substep-queue "
                         "sequential charges co-batch queueing")
    ap.add_argument("--rsu-backhaul-ms", type=float, default=0.0,
                    help="forwarding latency (ms) added to V2I when the "
                         "executing RSU differs from the radio-ingress RSU "
                         "(round-trip fiber WAN cost, applied once per task)")
    ap.add_argument("--substep-queue", default="snapshot",
                    choices=["snapshot", "sequential"],
                    help="within-substep RSU queue accounting (2026-08-04). "
                         "snapshot = legacy: every task in a 200 ms substep is "
                         "priced against the PRE-batch backlog (optimistic when "
                         "a balancer concentrates the substep on one RSU). "
                         "sequential = each task also waits for the co-batch "
                         "work placed ahead of it on the same RSU, and (under "
                         "dla) the deadline gate tests that updated backlog "
                         "— the batch-filling discipline of Ying et al.")
    ap.add_argument("--substep-queue-iters", type=int, default=3,
                    help="fixed-point iterations reconciling the dla gate with "
                         "co-batch offsets (rejected tasks occupy no service)")
    ap.add_argument("--veh-queue", default="conserved",
                    choices=["legacy", "conserved"],
                    help="vehicle-side queue semantics under sequential+reject "
                         "(2026-08-05 fix #4). conserved = co-batch sequential "
                         "pricing at V2V helpers + per-task MAX_QUEUE_DEPTH "
                         "rejection (local & V2V) with conserved enqueue. "
                         "legacy = RSU-side treatment only (reproduces the v5 "
                         "campaign). Ignored unless sequential+reject.")
    ap.add_argument("--rsu-cap-mode", default="clamp",
                    choices=["clamp", "reject"],
                    help="behaviour when the RSU concurrency cap binds "
                         "(2026-08-05, after Abdulla's accounting analysis). "
                         "clamp = legacy: surplus tasks stay scored as served "
                         "but only the admitted FRACTION of the batch's work "
                         "enters the backlog (work not conserved — at cap 2.5 "
                         "~18% of eligible V2I work vanished at enqueue in the "
                         "collapse cells). reject = physical: per-task "
                         "admission in vehicle order; a task that finds the "
                         "buffer full is individually REJECTED and scored as "
                         "the standard V2I-unavailable failure; admitted work "
                         "is enqueued in full (conserved). Requires "
                         "--substep-queue sequential.")
    ap.add_argument("--k8s-scale", default="off",
                    choices=["off", "static", "reactive"],
                    help="k8s-style vertical scaling of the RSU offloading "
                         "service (2026-08-04): off = 1x fixed (bit-exact "
                         "legacy); static = fixed --k8s-static-mult on every "
                         "RSU; reactive = HPA-style closed-loop controller "
                         "(per-RSU served-work utilisation EMA; scale up one "
                         "level above --k8s-up, down below --k8s-down after "
                         "--k8s-stab seconds; decisions every --k8s-sync s, "
                         "actuated --k8s-delay s later; levels 1..--k8s-max-mult "
                         "= CPU slice granted on the node)")
    ap.add_argument("--k8s-static-mult", type=float, default=2.0)
    ap.add_argument("--k8s-up", type=float, default=0.8)
    ap.add_argument("--k8s-down", type=float, default=0.5)
    ap.add_argument("--k8s-sync", type=int, default=15)
    ap.add_argument("--k8s-delay", type=int, default=15)
    ap.add_argument("--k8s-stab", type=int, default=300)
    ap.add_argument("--k8s-max-mult", type=float, default=3.0)
    ap.add_argument("--k8s-ema", type=float, default=60.0,
                    help="EMA time constant (s) of the utilisation signal")
    ap.add_argument("--ignore-enter", action="store_true",
                    help="ATTRIBUTION ONLY: ignore the trace's enter channel "
                         "and reproduce the pre-2026-08-03 mask-only queue "
                         "reset (slot-reuse queue carryover artifact)")
    ap.add_argument("--reset-soc-on-enter", action="store_true",
                    help="sensitivity check: re-draw SoC to the slot's initial "
                         "value at each visit start (default: SoC/tier persist "
                         "— slot = fleet-member abstraction)")
    ap.add_argument("--out-json", default="")
    args = ap.parse_args()

    tr = np.load(args.trace)
    pos_x, pos_y, mask = tr["pos_x"], tr["pos_y"], tr["mask"]
    T, N = pos_x.shape
    if args.max_steps > 0:
        T = min(T, args.max_steps)
    pos_x, pos_y, mask = pos_x[:T], pos_y[:T], mask[:T]
    # Per-visit queue reset (2026-08-03, after Yuxiang's slot-reuse report):
    # the builder reuses slots immediately, so mask can stay True across a
    # vehicle handover and the mask-based reset below never fires — the new
    # occupant inherits the old occupant's queue backlog. Traces built with
    # the fixed builder carry an `enter` channel (True at each visit's first
    # step); queue state is zeroed there. Old traces without the channel fall
    # back to the mask-only reset (bit-exact with pre-fix behaviour).
    enter = None
    if "enter" in tr.files and not args.ignore_enter:
        enter = tr["enter"][:T]
    HAS_ENTER = enter is not None
    RESET_SOC = bool(args.reset_soc_on_enter)
    if RESET_SOC and not HAS_ENTER:
        raise SystemExit("--reset-soc-on-enter needs a trace with an "
                         "`enter` channel (and no --ignore-enter)")
    if HAS_ENTER:
        _enter_mode = "ON"
    elif args.ignore_enter:
        _enter_mode = "off (mask-only reset — --ignore-enter)"
    else:
        _enter_mode = "off (mask-only reset — no enter channel in trace)"
    print(f"[mc] enter-reset={_enter_mode} reset_soc_on_enter={RESET_SOC}")
    K8S = args.k8s_scale
    K8S_ON = K8S != "off"
    SEQQ = args.substep_queue == "sequential"
    if SEQQ:
        print(f"[mc] substep-queue=sequential (co-batch queueing charged; "
              f"{args.substep_queue_iters} gate iterations)")
    CAP_REJECT = args.rsu_cap_mode == "reject"
    if CAP_REJECT and not SEQQ:
        raise SystemExit("--rsu-cap-mode reject requires --substep-queue "
                         "sequential (it is part of the physical-accounting "
                         "engine; the clamp is the superseded legacy path)")
    if CAP_REJECT:
        print("[mc] rsu-cap-mode=reject (buffer-full tasks individually "
              "failed; enqueued work conserved)")
    VEHC = SEQQ and CAP_REJECT and args.veh_queue == "conserved"
    if VEHC:
        print("[mc] veh-queue=conserved (helper co-batch pricing + per-task "
              "MQD rejection on vehicle queues)")
    if K8S_ON:
        print(f"[mc] k8s-scale={K8S} static_mult={args.k8s_static_mult} "
              f"up/down={args.k8s_up}/{args.k8s_down} sync/delay/stab="
              f"{args.k8s_sync}/{args.k8s_delay}/{args.k8s_stab} "
              f"max={args.k8s_max_mult} ema={args.k8s_ema}s")

    V.N_VEHICLES = N
    V.wrap_dist = euclid
    V.RSU_POSITIONS = tuple(map(tuple, np.asarray(tr["rsu_xy"])))
    # BUGFIX 2026-07-16: N_RSUS must follow the trace's RSU set. Before this
    # line, evals silently used only RSU_POSITIONS[:2] (import-time N_RSUS=2)
    # — every multi-RSU result produced before this date is superseded.
    V.N_RSUS = len(V.RSU_POSITIONS)
    if args.rsu_cap_abs > 0:
        rsu_cap = int(args.rsu_cap_abs)
        print(f"[mc] ABSOLUTE cap override: {rsu_cap} tasks/RSU "
              f"(ratio form would give {int(round(args.rsu_cap_per_veh * N))})")
    else:
        rsu_cap = int(round(args.rsu_cap_per_veh * N))
    V.RSU_MAX_CONCURRENT = rsu_cap
    R = V.N_RSUS
    KMAX = V.K_MAX_STRESS
    MQD = V.MAX_QUEUE_DEPTH
    print(f"[mc] T={T} maxN={N} RSU_MAX_CONCURRENT={rsu_cap} K_MAX={KMAX}")

    PERSTEP = bool(args.per_step_out)
    PERTASK = bool(args.per_task_out)

    apply = load_actor(args.actor)
    key0 = jax.random.PRNGKey(args.seed)
    key0, kf = jax.random.split(key0)
    if args.fleet_seed >= 0:
        kf = jax.random.PRNGKey(args.fleet_seed)
    preset = FLEET_PRESETS[args.fleet]
    if preset is None:
        tiers, is_ev, soc0, txw = V._sample_fleet(kf)
    else:
        tiers, is_ev, soc0, txw = sample_fleet_region(kf, N, preset)
    print(f"[fleet] {args.fleet}: ev_share={float(jnp.mean(is_ev)):.4f} "
          f"tier_hist={np.bincount(np.asarray(tiers), minlength=V.N_COMPUTE_TIERS).tolist()}")
    dt_ms = jnp.float32(1000.0)

    K8S_STATIC_M = jnp.full((R,), jnp.float32(args.k8s_static_mult))
    _R_IDX = jnp.arange(R)
    _N_IDX = jnp.arange(N)

    def veh_admit(sub_keys, actions, slot_types, best_v2v_idx, best_v2v_ok,
                  qb, qd, active):
        """Vehicle-queue admission & sequential pricing (fix #4, 2026-08-05).

        A vehicle's queue receives, per substep: its own local task (if
        action==0) plus V2V tasks from senders that chose it. Order convention:
        the local task first, then senders by vehicle index. Per-task
        MAX_QUEUE_DEPTH admission replaces the legacy fractional clamp;
        rejected tasks are scored as unavailable (penalty latency, no energy).
        Because the only vehicle-side gate is the depth cap, admission is
        exactly "the first (MQD - depth) tasks in batch order" — a single pass
        is exact (no fixed point needed).

        Returns (loc_cms, v2v_cms, loc_adm, v2v_adm, v2v_extra_ms,
                 n_mqd_loc, n_mqd_v2v).
        """
        k5 = jax.vmap(lambda k: jax.random.split(k, 5))(sub_keys)   # [N,5,2]
        # same draws process_agent realises: k_local = idx 0 (own tier),
        # k_v2v_tgt = idx 2 (TARGET's tier)
        loc_cms = jax.vmap(V.compute_time_ms)(k5[:, 0], slot_types, tiers)
        v2v_cms = jax.vmap(V.compute_time_ms)(
            k5[:, 2], slot_types, tiers[best_v2v_idx])
        cand_loc = active & (actions == 0)
        cand_v2v = active & (actions == 2) & best_v2v_ok
        onehotN = (best_v2v_idx[:, None] == _N_IDX[None, :])        # [N,N]
        c = cand_v2v.astype(jnp.float32)[:, None] * onehotN
        rank_send = jnp.sum((jnp.cumsum(c, axis=0) - c) * onehotN, axis=1)
        avail = jnp.maximum(MQD - qd, 0).astype(jnp.float32)        # per queue
        loc_adm = cand_loc & (avail > 0)
        v2v_adm = cand_v2v & (
            (loc_adm[best_v2v_idx].astype(jnp.float32) + rank_send)
            < avail[best_v2v_idx])
        w = jnp.where(v2v_adm, v2v_cms, 0.0)[:, None] * onehotN
        off_send = jnp.sum((jnp.cumsum(w, axis=0) - w) * onehotN, axis=1)
        v2v_extra = (loc_adm[best_v2v_idx].astype(jnp.float32)
                     * loc_cms[best_v2v_idx] + off_send)
        n_mqd_loc = jnp.sum((cand_loc & ~loc_adm).astype(jnp.float32))
        n_mqd_v2v = jnp.sum((cand_v2v & ~v2v_adm).astype(jnp.float32))
        w_off_veh = (jnp.sum(jnp.where(cand_loc, loc_cms, 0.0))
                     + jnp.sum(jnp.where(cand_v2v, v2v_cms, 0.0)))
        w_adm_veh = (jnp.sum(jnp.where(loc_adm, loc_cms, 0.0))
                     + jnp.sum(jnp.where(v2v_adm, v2v_cms, 0.0)))
        return (loc_cms, v2v_cms, loc_adm, v2v_adm, v2v_extra,
                n_mqd_loc, n_mqd_v2v, w_off_veh, w_adm_veh)

    def _call_agents(sub_keys, actions, s_sub, tgt, v2i_q, v2i_cap, rsu_ok,
                     bv2v, v2v_q, v2v_cap, v2v_ok, fwd, sm, extra,
                     v2v_extra=None, lok=None):
        """vmap process_agent. With every optional arg unset the call is the
        legacy 12-arg form (byte-identical graph); as soon as any is in use we
        pass the full optional set, filling unused ones with neutral values
        (fwd 0 ms, service mult 1.0, offsets 0 ms, loc_ok True)."""
        base = (sub_keys, actions, jnp.arange(N), s_sub, tgt, v2i_q,
                v2i_cap, rsu_ok, bv2v, v2v_q, v2v_cap, v2v_ok)
        ax = (0, 0, 0, None, 0, 0, 0, 0, 0, 0, 0, 0)
        if all(v is None for v in (fwd, sm, extra, v2v_extra, lok)):
            return jax.vmap(V.process_agent, in_axes=ax)(*base)
        fwd = jnp.zeros(N, jnp.float32) if fwd is None else fwd
        sm = jnp.ones(N, jnp.float32) if sm is None else sm
        extra = jnp.zeros(N, jnp.float32) if extra is None else extra
        if v2v_extra is None and lok is None:
            return jax.vmap(V.process_agent, in_axes=ax + (0, 0, 0))(
                *base, fwd, sm, extra)
        v2v_extra = (jnp.zeros(N, jnp.float32) if v2v_extra is None
                     else v2v_extra)
        lok = jnp.ones(N, bool) if lok is None else lok
        return jax.vmap(V.process_agent, in_axes=ax + (0, 0, 0, 0, 0))(
            *base, fwd, sm, extra, v2v_extra, lok)

    def seq_offsets(sub_keys, actions, slot_types, tgt, radio_ok, rb, rl,
                    active, svc_mult, use_dla):
        """Within-substep co-batch queueing (sequential/batch-filling).

        Each V2I task waits for the service time of tasks placed AHEAD of it on
        the same executing RSU in the same substep (order = vehicle index —
        arbitrary but fixed, matching the engine's own scatter order). Under
        dla the deadline gate tests the updated backlog; since a rejected task
        occupies no service, gate and offsets are reconciled by a short fixed
        point (rejections shrink offsets, which can re-admit later tasks).

        With --rsu-cap-mode reject the concurrency cap joins the same fixed
        point per task: task i is admitted only while (in-flight + admitted
        co-batch tasks ahead of it) < cap; surplus tasks are individually
        rejected (scored as the standard V2I-unavailable failure) instead of
        the legacy aggregate work-clamp at enqueue.

        Returns (extra_ms [N], rsu_ok [N], n_gate_rej, n_cap_rej).
        """
        # RSU service time each task WOULD take — same draw process_agent uses
        # (it splits its key into 5; k_rsu is index 1), so the offsets we
        # charge are exactly the service times later realised.
        k5 = jax.vmap(lambda k: jax.random.split(k, 5))(sub_keys)   # [N,5,2]
        cms = jax.vmap(V.compute_time_ms, in_axes=(0, 0, None))(
            k5[:, 1], slot_types, jnp.int32(V.RSU_TIER_IDX))
        if svc_mult is not None:
            cms = cms / svc_mult
        cand = active & (actions == 1) & radio_ok
        onehot = (tgt[:, None] == _R_IDX[None, :])                  # [N,R]
        dl = V.TASK_DEADLINE_MS[slot_types]
        base = rb[tgt]

        def offsets_of(adm):
            w = jnp.where(adm, cms, 0.0)[:, None] * onehot          # [N,R]
            excl = jnp.cumsum(w, axis=0) - w                        # exclusive
            return jnp.sum(excl * onehot, axis=1)                   # [N]

        def rank_of(adm):
            c = adm.astype(jnp.float32)[:, None] * onehot           # [N,R]
            excl = jnp.cumsum(c, axis=0) - c                        # exclusive
            return jnp.sum(excl * onehot, axis=1)                   # [N]

        gate_ok = lambda adm: (base + offsets_of(adm)) < dl
        cap_ok = lambda adm: rank_of(adm) < (
            jnp.float32(V.RSU_MAX_CONCURRENT) - rl.astype(jnp.float32))[tgt]

        adm = cand
        if use_dla or CAP_REJECT:
            for _ in range(max(args.substep_queue_iters, 1)):
                o = cand
                if use_dla:
                    o = o & gate_ok(adm)
                if CAP_REJECT:
                    o = o & cap_ok(adm)
                adm = o
        extra = offsets_of(adm)
        att = active & (actions == 1)
        w_off = jnp.sum(jnp.where(att, cms, 0.0))       # offered V2I work
        if use_dla or CAP_REJECT:
            gate_fail = cand & ~gate_ok(adm) if use_dla else jnp.zeros_like(cand)
            n_gate = jnp.sum(gate_fail.astype(jnp.float32))
            n_cap = jnp.sum((cand & ~adm & ~gate_fail).astype(jnp.float32))
            w_adm = jnp.sum(jnp.where(adm, cms, 0.0))
            return extra, adm, n_gate, n_cap, gate_fail, w_off, w_adm
        w_adm = jnp.sum(jnp.where(cand, cms, 0.0))      # all candidates enqueue
        return (extra, radio_ok, jnp.float32(0.0), jnp.float32(0.0),
                jnp.zeros_like(cand), w_off, w_adm)

    def step(carry, xs):
        if K8S == "reactive":
            (key, q_busy, q_depth, rsu_busy, rsu_load, soc, acc, k8s_st) = carry
            (m_cur, k_ema, k_below, k_plvl, k_pt, k_t, k_acc) = k8s_st
        else:
            key, q_busy, q_depth, rsu_busy, rsu_load, soc, acc = carry
            m_cur = K8S_STATIC_M if K8S == "static" else None
        if HAS_ENTER:
            px_t, py_t, m_t, ent_t = xs
        else:
            px_t, py_t, m_t = xs
        act = m_t                                            # active vehicles
        px = jnp.where(act, px_t, PARK); py = jnp.where(act, py_t, PARK)
        pos_xy = jnp.stack([px, py], axis=1)
        if HAS_ENTER:
            # zero queue state where the slot is inactive OR a new vehicle
            # enters it this step (visit start — covers immediate slot reuse
            # where mask stays True across occupant turnover)
            keep = act & ~ent_t
            q_busy = jnp.where(keep, q_busy, 0.0)
            q_depth = jnp.where(keep, q_depth, 0)
            if RESET_SOC:
                soc = jnp.where(ent_t, soc0, soc)
        else:
            q_busy = jnp.where(act, q_busy, 0.0)
            q_depth = jnp.where(act, q_depth, 0)
        key, kt, ka, kl, ko, kp, kslots = jax.random.split(key, 7)

        # observation task (single per vehicle, as Model C feeds obs)
        obs_type, obs_size = V._sample_tasks(kt, N)
        # k arrivals (masked to active) + per-slot task types/sizes
        k_arr = V._sample_k_arrivals(kp) * act.astype(jnp.int32)   # [N]
        types_slots, sizes_slots = V._sample_k_max_task_slots(kslots)  # [KMAX,N]

        state = V.EnvState(
            positions=pos_xy, speeds=jnp.zeros(N), compute_tier=tiers,
            is_ev=is_ev, soc=soc, tx_power_w=txw, queue_busy_ms=q_busy,
            queue_depth=q_depth, total_energy_j=jnp.zeros(N),
            rsu_busy_ms=rsu_busy, rsu_load=rsu_load, task_type=obs_type,
            task_data_size_mb=obs_size, step_count=jnp.int32(0),
            tasks_total=jnp.int32(0), tasks_completed=jnp.int32(0),
            tasks_deadline_miss=jnp.int32(0), total_latency_ms=jnp.float32(0.0),
            actions_local=jnp.int32(0), actions_v2i=jnp.int32(0),
            actions_v2v=jnp.int32(0), total_reward=jnp.float32(0.0),
            lane_id=jnp.zeros(N, dtype=jnp.int32), desired_speed_kmh=jnp.zeros(N),
            last_task_type=obs_type, n_arrivals_this_step=k_arr)

        obs = V.get_obs_arr(ko, state)
        actor_logits = apply(obs)
        actions = jnp.where(act, jnp.argmax(actor_logits, axis=1).astype(jnp.int32), 0)
        # channel links computed ONCE at step start (constant within the second)
        links = V.compute_per_vehicle_links(kl, state)
        (best_rsu_idx, v2i_q, v2i_cap, best_rsu_ok,
         best_v2v_idx, v2v_q, v2v_cap, best_v2v_ok, _, _, _) = links

        sub_action_keys = jax.random.split(ka, KMAX)  # [KMAX,2]

        # ---- inner scan over K_MAX task substeps (sequential queue build) ----
        def sub_step(c, sub_idx):
            if SEQQ:
                (qb, qd, rb, rl, e_src, e_tgt_src, done_n, ttype_tot,
                 ttype_done, lat_sum, rej) = c
            else:
                (qb, qd, rb, rl, e_src, e_tgt_src, done_n, ttype_tot,
                 ttype_done, lat_sum) = c
            active = (sub_idx < k_arr)                       # [N] bool (k_arr masked)
            active_f = active.astype(jnp.float32)
            slot_types = types_slots[sub_idx]
            slot_sizes = sizes_slots[sub_idx]
            s_sub = state._replace(task_type=slot_types, task_data_size_mb=slot_sizes,
                                   queue_busy_ms=qb, queue_depth=qd,
                                   rsu_busy_ms=rb, rsu_load=rl)
            sub_keys = jax.random.split(sub_action_keys[sub_idx], N)
            if VEHC:
                (loc_cms_pre, v2v_cms_pre, loc_adm, v2v_adm, v2v_extra,
                 n_mqd_loc, n_mqd_v2v, w_off_veh, w_adm_veh) = veh_admit(
                    sub_keys, actions, slot_types, best_v2v_idx, best_v2v_ok,
                    qb, qd, active)
                v2v_ok_eff = v2v_adm      # refined: rejected senders scored unavailable
                loc_ok_eff = loc_adm | ~(active & (actions == 0))
            else:
                v2v_extra, loc_ok_eff, v2v_ok_eff = None, None, best_v2v_ok
                n_mqd_loc = n_mqd_v2v = jnp.float32(0.0)
                w_off_veh = w_adm_veh = jnp.float32(0.0)
            if args.rsu_lb != "off":
                # RSU load balancer (2026-07-27): execution RSU decoupled from
                # radio ingress via fiber backhaul. Re-evaluated every substep
                # on the CURRENT backlog rb, so within-second queue growth is
                # visible to the balancer.
                if args.rsu_lb in ("jsq", "dla"):
                    exec_idx = jnp.full((N,), jnp.argmin(rb).astype(jnp.int32))
                    # NB: one argmin per substep sends the WHOLE substep's V2I
                    # traffic to a single RSU. Under --substep-queue sequential
                    # those tasks queue behind each other, which is why
                    # dla_p2c (per-vehicle spreading + the same gate) exists.
                else:  # p2c / dla_p2c — per-vehicle two random candidates
                    kc1, kc2 = jax.random.split(
                        jax.random.fold_in(sub_action_keys[sub_idx], 97))
                    c1 = jax.random.randint(kc1, (N,), 0, R)
                    c2 = jax.random.randint(kc2, (N,), 0, R)
                    exec_idx = jnp.where(rb[c1] <= rb[c2], c1, c2)
                # radio viability on the INGRESS link; saturation on the
                # EXECUTING RSU (admission happens where the task runs)
                rsu_ok = (v2i_q > 0.0) & (rl[exec_idx] < V.RSU_MAX_CONCURRENT)
                rsu_ok_pre = rsu_ok
                if SEQQ:
                    # sequential accounting: co-batch offsets (+ dla gate on
                    # the updated backlog, reconciled by fixed point)
                    (rsu_extra, rsu_ok, n_grej, n_crej, gate_fail_m,
                     w_off_v2i, w_adm_v2i) = seq_offsets(
                        sub_keys, actions, slot_types, exec_idx, rsu_ok,
                        rb, rl, active, m_cur[exec_idx] if K8S_ON else None,
                        args.rsu_lb in ("dla", "dla_p2c"))
                elif args.rsu_lb in ("dla", "dla_p2c"):
                    # deadline-aware admission: a task whose deadline is
                    # already exceeded by the target backlog is rejected
                    # up-front (counted as the standard V2I-unavailable miss,
                    # NOT enqueued) — queues never grow beyond the largest
                    # deadline plus one substep's admissions.
                    rsu_ok = rsu_ok & (rb[exec_idx] <
                                       V.TASK_DEADLINE_MS[slot_types])
                fwd_ms = jnp.float32(args.rsu_backhaul_ms) * (
                    exec_idx != best_rsu_idx).astype(jnp.float32)
                rsu_tgt = exec_idx
                _sm = m_cur[exec_idx] if K8S_ON else None
                (rew, lat, energies, target_e, dmet,
                 local_cms, target_cms, rsu_cms) = _call_agents(
                    sub_keys, actions, s_sub, rsu_tgt, v2i_q, v2i_cap, rsu_ok,
                    best_v2v_idx, v2v_q, v2v_cap, v2v_ok_eff,
                    fwd_ms, _sm, rsu_extra if SEQQ else None,
                    v2v_extra, loc_ok_eff)
            else:
                rsu_tgt, rsu_ok = best_rsu_idx, best_rsu_ok
                rsu_ok_pre = best_rsu_ok
                if SEQQ:
                    # baseline ingress: co-batch queueing at the nearest RSU
                    (rsu_extra, rsu_ok, n_grej, n_crej, gate_fail_m,
                     w_off_v2i, w_adm_v2i) = seq_offsets(
                        sub_keys, actions, slot_types, rsu_tgt, rsu_ok,
                        rb, rl, active, m_cur[rsu_tgt] if K8S_ON else None,
                        False)
                _sm = m_cur[best_rsu_idx] if K8S_ON else None
                _fwd = jnp.zeros(N, jnp.float32) if (K8S_ON or SEQQ) else None
                (rew, lat, energies, target_e, dmet,
                 local_cms, target_cms, rsu_cms) = _call_agents(
                    sub_keys, actions, s_sub, best_rsu_idx, v2i_q, v2i_cap,
                    best_rsu_ok, best_v2v_idx, v2v_q, v2v_cap, v2v_ok_eff,
                    _fwd, _sm, rsu_extra if SEQQ else None,
                    v2v_extra, loc_ok_eff)
            energies_a = energies * active_f
            target_e_a = target_e * active_f
            dmet_a = dmet & active
            if SEQQ:
                # --- per-task lifecycle taxonomy (2026-08-05, Abdulla Q2) ---
                att_v2i = active & (actions == 1)
                att_v2v = active & (actions == 2)
                att_loc = active & (actions == 0)
                cand_v2i = att_v2i & rsu_ok_pre          # passed radio+coarse checks
                # not-a-candidate = radio unavailable OR coarse pre-cap fail
                unav_v2i = att_v2i & ~rsu_ok_pre
                unav_v2v = att_v2v & ~best_v2v_ok
                if VEHC:
                    rej_mqd_v2v = att_v2v & best_v2v_ok & ~v2v_adm
                    rej_mqd_loc = att_loc & ~loc_adm
                else:
                    rej_mqd_v2v = jnp.zeros_like(att_v2v)
                    rej_mqd_loc = jnp.zeros_like(att_loc)
                rej_v2i = cand_v2i & ~rsu_ok             # gate/cap in-batch rejects
                notadm = (unav_v2i | rej_v2i | unav_v2v | rej_mqd_v2v
                          | rej_mqd_loc)
                # per-task outcome code: 0 inactive, 1 served+met,
                # 2 served+miss, 3 rej dla-gate, 4 rej rsu-cap,
                # 5 rej vehicle-queue (local), 6 rej vehicle-queue (V2V),
                # 7 V2I unavailable, 8 V2V unavailable
                rej_cap_m = rej_v2i & ~gate_fail_m
                outcome = jnp.where(gate_fail_m, 3,
                          jnp.where(rej_cap_m, 4,
                          jnp.where(rej_mqd_loc, 5,
                          jnp.where(rej_mqd_v2v, 6,
                          jnp.where(unav_v2i, 7,
                          jnp.where(unav_v2v, 8,
                          jnp.where(dmet_a, 1, 2))))))).astype(jnp.int8)
                outcome = jnp.where(active, outcome, 0).astype(jnp.int8)
                lat_met_inc = jnp.sum(lat * dmet_a.astype(jnp.float32))
                notadm_lat_inc = jnp.sum(lat * (notadm & active).astype(jnp.float32))
                n_unav_v2i = jnp.sum((unav_v2i).astype(jnp.float32))
                n_unav_v2v = jnp.sum((unav_v2v).astype(jnp.float32))
            # per-task vehicle queue admit (no k scaling)
            if VEHC:
                # per-task admission already decided in veh_admit; admitted
                # work is enqueued IN FULL (conserved), rejected tasks were
                # scored as unavailable. No fractional clamp.
                local_inc_ms = jnp.where(loc_adm, local_cms * active_f, 0.0)
                v2v_inc_ms = jnp.zeros(N).at[best_v2v_idx].add(
                    jnp.where(v2v_adm, target_cms * active_f, 0.0))
                tot_inc_n = (loc_adm.astype(jnp.int32)
                             + jnp.zeros(N, jnp.int32).at[best_v2v_idx].add(
                                 v2v_adm.astype(jnp.int32)))
                qb2 = qb + local_inc_ms + v2v_inc_ms
                qd2 = qd + tot_inc_n
            else:
                local_inc_ms = jnp.where(active & (actions == 0), local_cms * active_f, 0.0)
                local_inc_n = (active & (actions == 0)).astype(jnp.int32)
                v2v_valid = active & (actions == 2) & best_v2v_ok
                v2v_inc_ms = jnp.zeros(N).at[best_v2v_idx].add(
                    jnp.where(v2v_valid, target_cms * active_f, 0.0))
                v2v_inc_n = jnp.zeros(N, jnp.int32).at[best_v2v_idx].add(
                    v2v_valid.astype(jnp.int32))
                tot_inc_ms = local_inc_ms + v2v_inc_ms
                tot_inc_n = local_inc_n + v2v_inc_n
                cap = jnp.maximum(MQD - qd, 0)
                adm_n = jnp.minimum(tot_inc_n, cap)
                adm_frac = jnp.where(tot_inc_n > 0,
                                     adm_n.astype(jnp.float32) / jnp.maximum(tot_inc_n, 1), 0.0)
                qb2 = qb + tot_inc_ms * adm_frac
                qd2 = qd + adm_n
            # per-task RSU admit (scatter to the EXECUTING RSU — equals the
            # radio-ingress RSU unless --rsu-lb redirects it)
            is_v2i = active & (actions == 1) & rsu_ok
            rsu_inc_ms = jnp.zeros(R).at[rsu_tgt].add(
                jnp.where(is_v2i, rsu_cms * active_f, 0.0))
            rsu_inc_n = jnp.zeros(R, jnp.int32).at[rsu_tgt].add(
                is_v2i.astype(jnp.int32))
            if CAP_REJECT:
                # per-task admission already enforced in seq_offsets; every
                # admitted task's work is enqueued IN FULL (work conserved),
                # every surplus task was individually failed. No clamp.
                rb2 = rb + rsu_inc_ms
                rl2 = rl + rsu_inc_n
            else:
                rcap = jnp.maximum(V.RSU_MAX_CONCURRENT - rl, 0)
                radm_n = jnp.minimum(rsu_inc_n, rcap)
                radm_frac = jnp.where(rsu_inc_n > 0,
                                      radm_n.astype(jnp.float32) / jnp.maximum(rsu_inc_n, 1), 0.0)
                rb2 = rb + rsu_inc_ms * radm_frac
                rl2 = rl + radm_n
            # accumulators (per task type 0/1/2 = T1/T2/T3)
            type_oh = jax.nn.one_hot(slot_types, 3) * active_f[:, None]      # [N,3]
            type_done = type_oh * dmet.astype(jnp.float32)[:, None]           # [N,3]
            c2 = (qb2, qd2, rb2, rl2,
                  e_src + energies_a,
                  e_tgt_src + target_e_a,
                  done_n + dmet_a.astype(jnp.int32),
                  ttype_tot + jnp.sum(type_oh, axis=0),                       # [3]
                  ttype_done + jnp.sum(type_done, axis=0),                    # [3]
                  lat_sum + jnp.sum(lat * active_f))                          # ms, per-task
            if SEQQ:
                c2 = c2 + (rej + jnp.array([n_grej, n_crej,
                                            n_mqd_loc, n_mqd_v2v,
                                            n_unav_v2i, n_unav_v2v,
                                            lat_met_inc, notadm_lat_inc,
                                            w_off_v2i, w_adm_v2i,
                                            w_off_veh, w_adm_veh]),)
            # Per-task instrumentation (additive output only — physics/RNG
            # untouched; ys discarded unless --per-task-out).
            if PERTASK:
                v2i_attempt = active & (actions == 1)
                task_ingress_rsu = jnp.where(
                    v2i_attempt, best_rsu_idx, -1).astype(jnp.int16)
                task_selected_execution_rsu = jnp.where(
                    v2i_attempt, rsu_tgt, -1).astype(jnp.int16)
                task_execution_rsu = jnp.where(
                    is_v2i, rsu_tgt, -1).astype(jnp.int16)
                task_forwarded = is_v2i & (rsu_tgt != best_rsu_idx)
                task_forwarding_latency_ms = jnp.where(
                    task_forwarded, jnp.float32(args.rsu_backhaul_ms),
                    jnp.float32(0.0)).astype(jnp.float32)
                ys_sub = (slot_types.astype(jnp.int8),
                          (lat * active_f).astype(jnp.float32),
                          (dmet & active),
                          active,
                          task_ingress_rsu,
                          task_selected_execution_rsu,
                          task_execution_rsu,
                          task_forwarded,
                          task_forwarding_latency_ms,
                          is_v2i) + ((outcome,) if SEQQ else ())
            else:
                ys_sub = None
            return c2, ys_sub

        c0 = (q_busy, q_depth, rsu_busy, rsu_load,
              jnp.zeros(N), jnp.zeros(N), jnp.zeros(N, jnp.int32),
              jnp.zeros(3), jnp.zeros(3), jnp.float32(0.0))
        if SEQQ:
            c0 = c0 + (jnp.zeros(12),)
            (qb, qd, rb, rl, e_src, e_tgt_src, done_n, ttype_tot, ttype_done,
             lat_sum, rej_step), sub_ys = jax.lax.scan(
                sub_step, c0, jnp.arange(KMAX))
        else:
            (qb, qd, rb, rl, e_src, e_tgt_src, done_n, ttype_tot, ttype_done,
             lat_sum), sub_ys = jax.lax.scan(sub_step, c0, jnp.arange(KMAX))

        # ---- drain vehicle queue once (1000 ms) ----
        drained = jnp.minimum(qb, dt_ms); new_busy = qb - drained
        dfrac = jnp.where(qb > 0, drained / jnp.maximum(qb, 1e-6), 0.0)
        tdr = jnp.where(new_busy <= 0.0, qd, jnp.floor(qd.astype(jnp.float32) * dfrac).astype(jnp.int32))
        q_depth_new = jnp.maximum(qd - tdr, 0)
        q_depth_new = jnp.where((new_busy > 0.0) & (q_depth_new == 0), 1, q_depth_new)
        # ---- drain RSU queue once ----
        rdr = jnp.minimum(rb, dt_ms); new_rbusy = rb - rdr
        rfrac = jnp.where(rb > 0, rdr / jnp.maximum(rb, 1e-6), 0.0)
        rtdr = jnp.where(new_rbusy <= 0.0, rl, jnp.floor(rl.astype(jnp.float32) * rfrac).astype(jnp.int32))
        rsu_load_new = jnp.maximum(rl - rtdr, 0)
        rsu_load_new = jnp.where((new_rbusy > 0.0) & (rsu_load_new == 0), 1, rsu_load_new)

        # ---- k8s reactive controller (HPA model, 2026-08-04) ----
        # Runs on this step's drain; produces the multiplier for the NEXT
        # step. Signal = served work / drain capacity (EMA). Decisions on
        # sync ticks, actuated --k8s-delay seconds later (pod resize lag).
        if K8S == "reactive":
            util = rdr / dt_ms                                     # [R]
            k_ema2 = k_ema + (util - k_ema) / jnp.float32(args.k8s_ema)
            k_below2 = jnp.where(k_ema2 < args.k8s_down, k_below + 1, 0)
            # 1) actuate a pending decision whose delay elapsed
            do_apply = (k_pt >= 0) & (k_t >= k_pt)
            m_new = jnp.where(do_apply, k_plvl, m_cur)
            k_pt2 = jnp.where(do_apply, -1, k_pt)
            k_below2 = jnp.where(do_apply, 0, k_below2)
            # 2) sync-tick decision (one level at a time, no pending stacked)
            is_sync = (k_t % args.k8s_sync) == 0
            can = k_pt2 < 0
            go_up = is_sync & can & (k_ema2 > args.k8s_up) & \
                (m_new < args.k8s_max_mult)
            go_dn = is_sync & can & (k_below2 >= args.k8s_stab) & (m_new > 1.0)
            k_plvl2 = jnp.where(go_up, m_new + 1.0,
                                jnp.where(go_dn, m_new - 1.0, k_plvl))
            k_pt2 = jnp.where(go_up | go_dn, k_t + args.k8s_delay, k_pt2)
            # accounting: core-seconds, actuation count, first scale-up time
            k_acc2 = k_acc + jnp.array([
                jnp.sum(m_new),
                jnp.sum(do_apply.astype(jnp.float32)),
                0.0])
            first = jnp.where((k_acc[2] == 0.0) & jnp.any(m_new > 1.0),
                              k_t.astype(jnp.float32) + 1.0, k_acc[2])
            k_acc2 = k_acc2.at[2].set(first)
            k8s_new = (m_new, k_ema2, k_below2, k_plvl2, k_pt2, k_t + 1,
                       k_acc2)

        # energy: scatter source-side target energy to V2V targets, add to source
        tgt_e = jnp.zeros(N).at[best_v2v_idx].add(e_tgt_src)
        per_veh_e = e_src + tgt_e
        soc_new = jnp.where(is_ev, jnp.maximum(soc - per_veh_e / (V.EV_BATTERY_KWH * 3.6e6), 0.0), soc)

        k_arr_f = k_arr.astype(jnp.float32)
        a = acc + jnp.array([
            jnp.sum(k_arr_f),                               # tasks_total (per-arrival)
            jnp.sum(done_n.astype(jnp.float32)),            # tasks_completed
            jnp.sum(per_veh_e),                             # total energy
            jnp.sum((actions == 0).astype(jnp.float32) * k_arr_f),
            jnp.sum((actions == 1).astype(jnp.float32) * k_arr_f),
            jnp.sum((actions == 2).astype(jnp.float32) * k_arr_f),
            ttype_tot[0], ttype_tot[1], ttype_tot[2],       # T1/T2/T3 arrivals
            ttype_done[0], ttype_done[1], ttype_done[2],    # T1/T2/T3 completed
            lat_sum] +                                      # total latency (ms)
            (list(rej_step) if SEQQ else []))
            # gate/cap/mqd-local/mqd-v2v rejects + v2i/v2v unavailable
            # + lat-sum(met) + lat-sum(not-admitted)
        # Per-step instrumentation (additive outputs; --per-step-out).
        ys = {}
        if PERSTEP:
            ys.update(
                arrivals=jnp.sum(k_arr).astype(jnp.int32),
                done=jnp.sum(done_n).astype(jnp.int32),
                lat_sum=lat_sum,
                active=jnp.sum(act).astype(jnp.int32),
                n_local=jnp.sum((actions == 0) * k_arr).astype(jnp.int32),
                n_v2i=jnp.sum((actions == 1) * k_arr).astype(jnp.int32),
                n_v2v=jnp.sum((actions == 2) * k_arr).astype(jnp.int32),
                # per-vehicle trajectories [N]
                veh_action=actions.astype(jnp.int8),
                # frozen actor output [N,3], before greedy argmax; additive
                # cross-arm identity evidence only (never fed back to physics)
                veh_actor_logits=actor_logits.astype(jnp.float32),
                veh_k=k_arr.astype(jnp.int8),
                veh_done=done_n.astype(jnp.int16),
                veh_queue_ms=new_busy.astype(jnp.float32),
                # action targets [N]: best-RSU / best-V2V-peer index at
                # decision time (-1 = no eligible target); the target actually
                # used when the action was V2I / V2V respectively.
                veh_best_rsu=jnp.where(best_rsu_ok, best_rsu_idx, -1).astype(jnp.int16),
                veh_best_v2v=jnp.where(best_v2v_ok, best_v2v_idx, -1).astype(jnp.int16),
                # per-RSU state [R]
                rsu_busy_ms=new_rbusy.astype(jnp.float32),
                rsu_load=rsu_load_new.astype(jnp.int32),
            )
        if PERSTEP and K8S == "reactive":
            ys.update(rsu_mult=m_cur.astype(jnp.float32))   # slice used THIS step
        if PERTASK:
            ys.update(task_type=sub_ys[0], task_lat_ms=sub_ys[1],
                      task_met=sub_ys[2], task_active=sub_ys[3],
                      task_ingress_rsu=sub_ys[4],
                      task_selected_execution_rsu=sub_ys[5],
                      task_execution_rsu=sub_ys[6],
                      task_forwarded=sub_ys[7],
                      task_forwarding_latency_ms=sub_ys[8],
                      task_v2i_admitted=sub_ys[9])
            if SEQQ:
                ys.update(task_outcome=sub_ys[10])
        if K8S == "reactive":
            return (key, new_busy, q_depth_new, new_rbusy, rsu_load_new,
                    soc_new, a, k8s_new), (ys or None)
        return (key, new_busy, q_depth_new, new_rbusy, rsu_load_new, soc_new, a), (ys or None)

    init = (key0, jnp.zeros(N), jnp.zeros(N, jnp.int32), jnp.zeros(R),
            jnp.zeros(R, jnp.int32), soc0, jnp.zeros(25 if SEQQ else 13))
    if K8S == "reactive":
        k8s_init = (jnp.ones(R), jnp.zeros(R), jnp.zeros(R, jnp.int32),
                    jnp.ones(R), jnp.full((R,), -1, jnp.int32),
                    jnp.int32(0), jnp.zeros(3))
        init = init + (k8s_init,)
    if HAS_ENTER:
        xs = (jnp.asarray(pos_x), jnp.asarray(pos_y), jnp.asarray(mask),
              jnp.asarray(enter))
    else:
        xs = (jnp.asarray(pos_x), jnp.asarray(pos_y), jnp.asarray(mask))
    run = jax.jit(lambda i, x: jax.lax.scan(step, i, x))
    t0 = time.time()
    (carry, ys_out) = run(init, xs)
    acc_full = np.asarray(carry[6])
    acc = acc_full[:13]          # 13 core slots (carry[-1] only pre-k8s)
    n_gate_rej = float(acc_full[13]) if SEQQ else 0.0
    n_cap_rej = float(acc_full[14]) if SEQQ else 0.0
    n_mqd_loc = float(acc_full[15]) if SEQQ else 0.0
    n_mqd_v2v = float(acc_full[16]) if SEQQ else 0.0
    n_unav_v2i = float(acc_full[17]) if SEQQ else 0.0
    n_unav_v2v = float(acc_full[18]) if SEQQ else 0.0
    lat_met_sum = float(acc_full[19]) if SEQQ else 0.0
    notadm_lat_sum = float(acc_full[20]) if SEQQ else 0.0
    w_off_v2i = float(acc_full[21]) if SEQQ else 0.0
    w_adm_v2i = float(acc_full[22]) if SEQQ else 0.0
    w_off_veh = float(acc_full[23]) if SEQQ else 0.0
    w_adm_veh = float(acc_full[24]) if SEQQ else 0.0
    if K8S == "reactive":
        k8s_acc = np.asarray(carry[7][6])
        k8s_mean_mult = float(k8s_acc[0]) / (R * T)
        k8s_events = int(k8s_acc[1])
        k8s_first_up = float(k8s_acc[2]) - 1.0 if k8s_acc[2] > 0 else -1.0
    elif K8S == "static":
        k8s_mean_mult, k8s_events, k8s_first_up = args.k8s_static_mult, 0, 0.0
    else:
        k8s_mean_mult, k8s_events, k8s_first_up = 1.0, 0, -1.0
    dt = time.time() - t0
    (tot_tasks, tot_done, tot_energy, n_loc, n_v2i, n_v2v,
     t1_t, t2_t, t3_t, t1_d, t2_d, t3_d, lat_total) = [float(x) for x in acc]
    ta = max(n_loc + n_v2i + n_v2v, 1.0)
    path_summary = None
    if PERTASK:
        path_arrays = {
            name: np.asarray(ys_out[name]) for name in (
                "task_ingress_rsu", "task_selected_execution_rsu",
                "task_execution_rsu", "task_forwarded",
                "task_forwarding_latency_ms", "task_v2i_admitted",
                "task_active")
        }
        if SEQQ:
            path_arrays["task_outcome"] = np.asarray(ys_out["task_outcome"])
        path_summary = summarise_v2i_paths(
            path_arrays, n_rsus=R, rsu_lb=args.rsu_lb)
    out = {"trace": os.path.basename(args.trace), "actor": os.path.basename(args.actor),
           "model": "C", "T": int(T), "maxN": int(N), "rsu_max_concurrent": int(rsu_cap),
           "fleet": args.fleet, "fleet_seed": args.fleet_seed,
           "obs_variant": "capscalar13" if args.cap_scalar else "onehot17",
           "lambda_arrival": float(os.environ.get("VEC_JAX_LAMBDA_ARRIVAL", "1.5")),
           "rsu_service_mult": float(os.environ.get("VEC_JAX_RSU_SERVICE_MULT", "1.0")),
           "rsu_lb": args.rsu_lb, "rsu_backhaul_ms": args.rsu_backhaul_ms,
           "k8s_scale": K8S,
           "k8s_params": ({"static_mult": args.k8s_static_mult} if K8S == "static"
                          else {"up": args.k8s_up, "down": args.k8s_down,
                                "sync_s": args.k8s_sync, "delay_s": args.k8s_delay,
                                "stab_s": args.k8s_stab, "max_mult": args.k8s_max_mult,
                                "ema_s": args.k8s_ema} if K8S == "reactive" else {}),
           "k8s_mean_mult": k8s_mean_mult,
           "k8s_scale_events": k8s_events,
           "k8s_first_scaleup_s": k8s_first_up,
           "rsu_cap_mode": args.rsu_cap_mode,
           "substep_queue": args.substep_queue,
           "v2i_gate_rejected": n_gate_rej,
           "v2i_cap_rejected": n_cap_rej,
           "veh_queue_mode": "conserved" if VEHC else "legacy",
           "local_mqd_rejected": n_mqd_loc,
           "v2v_mqd_rejected": n_mqd_v2v,
           "v2i_unavailable": n_unav_v2i,
           "v2v_unavailable": n_unav_v2v,
           # --- work-conservation ledger (2026-08-05, Abdulla Q3): offered =
           # admitted + rejected, per queue family, in ms of service work.
           # Admitted work enters the corresponding backlog IN FULL; rejected
           # work has a per-task terminal state (task_outcome codes 3-6).
           # v2i offered = all V2I-attempted incl. unavailable; veh offered =
           # local + valid-target V2V candidates (unavailable V2V work has no
           # destination queue and is excluded — counted in v2v_unavailable).
           "work_ms": ({
               "v2i_offered": w_off_v2i, "v2i_admitted": w_adm_v2i,
               "v2i_rejected_or_unavailable": w_off_v2i - w_adm_v2i,
               "veh_offered": w_off_veh, "veh_admitted": w_adm_veh,
               "veh_rejected": w_off_veh - w_adm_veh} if (SEQQ and CAP_REJECT)
               else None),  # exact only under reject semantics (the clamp
                            # path would report pre-clamp admitted work); veh
                            # entries are zero unless veh_queue_mode=conserved
           "enter_reset": bool(HAS_ENTER),
           "reset_soc_on_enter": RESET_SOC,
           "engine_version": "v3_enter_reset" if HAS_ENTER else "v2_post_nrsus_fix",
           "fleet_ev_share": float(jnp.mean(is_ev)),
           "fleet_tier_hist": np.bincount(np.asarray(tiers), minlength=V.N_COMPUTE_TIERS).tolist(),
           "completion": tot_done / max(tot_tasks, 1.0),
           # --- two-population reporting (2026-08-05, per Abdulla's Q2
           # recommendation): OFFERED = every generated task (system-level
           # success; "completion" above); ADMITTED = tasks that entered a
           # service queue (offered minus explicit rejections and
           # unavailability) — admitted-service performance with an honest
           # denominator. avg_latency_met excludes penalty-scored failures
           # entirely (latency conditional on deadline met).
           "n_offered": tot_tasks,
           "n_admitted": (tot_tasks - n_gate_rej - n_cap_rej - n_mqd_loc
                          - n_mqd_v2v - n_unav_v2i - n_unav_v2v) if SEQQ else None,
           "completion_admitted": (tot_done / max(tot_tasks - n_gate_rej
                                    - n_cap_rej - n_mqd_loc - n_mqd_v2v
                                    - n_unav_v2i - n_unav_v2v, 1.0)) if SEQQ else None,
           "avg_latency_admitted_ms": ((lat_total - notadm_lat_sum)
                                       / max(tot_tasks - n_gate_rej - n_cap_rej
                                             - n_mqd_loc - n_mqd_v2v
                                             - n_unav_v2i - n_unav_v2v, 1.0)) if SEQQ else None,
           "avg_latency_met_ms": (lat_met_sum / max(tot_done, 1.0)) if SEQQ else None,
           "t1_completion": t1_d / max(t1_t, 1.0),
           "t2_completion": t2_d / max(t2_t, 1.0),
           "t3_completion": t3_d / max(t3_t, 1.0),
           # Additive raw numerator for independently checking the declared
           # per-offered-task energy denominator. The accumulator and physics
           # are unchanged; this only exposes the already-computed value.
           "total_energy_j": tot_energy,
           "avg_energy_j_per_task": tot_energy / max(tot_tasks, 1.0),
           "avg_latency_ms_per_task": lat_total / max(tot_tasks, 1.0),
           "p_local": n_loc / ta, "p_v2i": n_v2i / ta, "p_v2v": n_v2v / ta,
           "t1_share": t1_t / max(tot_tasks, 1.0), "t2_share": t2_t / max(tot_tasks, 1.0),
           "t3_share": t3_t / max(tot_tasks, 1.0),
           "total_tasks": tot_tasks, "wall_s": round(dt, 1)}
    if PERTASK:
        out["v2i_path_metrics"] = path_summary
    print(json.dumps(out, indent=2))
    if args.out_json:
        open(args.out_json, "w").write(json.dumps(out, indent=2) + "\n")

    if PERSTEP or PERTASK:
        ys_np = {k: np.asarray(v) for k, v in ys_out.items()}
        # Internal consistency: aggregates recomputed from the instrumented
        # streams must equal the accumulator-derived JSON numbers.
        if PERSTEP:
            assert int(ys_np["arrivals"].sum()) == int(tot_tasks), "arrivals mismatch"
            assert int(ys_np["done"].sum()) == int(tot_done), "done mismatch"
            step_keys = ["arrivals", "done", "lat_sum", "active", "n_local",
                         "n_v2i", "n_v2v", "veh_action", "veh_actor_logits",
                         "veh_k", "veh_done", "veh_queue_ms", "veh_best_rsu",
                         "veh_best_v2v", "rsu_busy_ms", "rsu_load"]
            if K8S == "reactive":
                step_keys.append("rsu_mult")   # per-RSU CPU slice [T,R]
            np.savez_compressed(args.per_step_out,
                                times=np.asarray(tr["times"][:T]),
                                # per-slot fleet assignment for this run
                                # (fixed for the whole trace; slots recycle
                                # across SUMO vehicles — see occupancy table)
                                slot_tier=np.asarray(tiers, dtype=np.int8),
                                slot_is_ev=np.asarray(is_ev),
                                **{k: ys_np[k] for k in step_keys})
            print(f"[per-step] wrote {args.per_step_out} "
                  f"(T={T}, N={N}, R={R}; join vehicles on the trace npz "
                  f"pos_x/pos_y/mask for positions)")
        if PERTASK:
            n_task_arrivals = int(ys_np["task_active"].sum())
            assert n_task_arrivals == int(tot_tasks), "per-task arrivals mismatch"
            if SEQQ:
                # consistency: per-task outcome counts == accumulators
                oc = ys_np["task_outcome"]
                for code, ref in [(3, n_gate_rej), (4, n_cap_rej),
                                  (5, n_mqd_loc), (6, n_mqd_v2v),
                                  (7, n_unav_v2i), (8, n_unav_v2v)]:
                    assert int((oc == code).sum()) == int(ref), \
                        f"outcome code {code} mismatch"
            np.savez_compressed(args.per_task_out,
                                task_type=ys_np["task_type"],
                                task_lat_ms=ys_np["task_lat_ms"],
                                **({"task_outcome": ys_np["task_outcome"]}
                                   if SEQQ else {}),
                                task_met=ys_np["task_met"],
                                task_active=ys_np["task_active"],
                                task_ingress_rsu=ys_np["task_ingress_rsu"],
                                task_selected_execution_rsu=ys_np["task_selected_execution_rsu"],
                                task_execution_rsu=ys_np["task_execution_rsu"],
                                task_forwarded=ys_np["task_forwarded"],
                                task_forwarding_latency_ms=ys_np["task_forwarding_latency_ms"],
                                task_v2i_admitted=ys_np["task_v2i_admitted"])
            print(f"[per-task] wrote {args.per_task_out} "
                  f"([T,KMAX,N] = [{T},{KMAX},{N}]; filter on task_active)")


if __name__ == "__main__":
    main()
