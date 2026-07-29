"""Derive an update-boundary checkpointable B-BUS trainer.

The permitted producer trainer remains byte-for-byte unchanged.  This module
performs a fail-closed, marker-based transformation while a private Colab pack
is being built.  The derived script saves all mutable training state after a
completed PPO update and can continue at the following update.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

METHOD_VERSION = "bbus-update-checkpoint-transform-1.0"
UPSTREAM_TRAIN_SHA256 = "d19453529babb1c1691fdc9da5188aa0e3e233e3dcf6a65ac84ada2ef25355e1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"producer trainer layout changed at {label}")
    return source.replace(old, new, 1)


def checkpointed_train_text(source: str, *, verify_upstream: bool = True) -> str:
    """Return the checkpointable derivative of the exact staged trainer."""

    if verify_upstream and sha256_bytes(source.encode("utf-8")) != UPSTREAM_TRAIN_SHA256:
        raise ValueError("staged producer trainer differs from the checkpoint transform input")

    transformed = _replace_once(
        source,
        "import argparse\nimport csv\nimport json\nimport os\nimport sys\nimport time\n",
        "import argparse\nimport csv\nimport hashlib\nimport io\nimport json\nimport os\n"
        "import sys\nimport tempfile\nimport time\nimport zipfile\n",
        label="imports",
    )
    transformed = _replace_once(
        transformed,
        '    ap.add_argument("--tag", type=str, default="",\n'
        '                    help="Short tag appended to log lines for multi-cell runs.")\n',
        '    ap.add_argument("--tag", type=str, default="",\n'
        '                    help="Short tag appended to log lines for multi-cell runs.")\n'
        '    ap.add_argument("--checkpoint-path", type=Path, default=None,\n'
        '                    help="Atomic update-boundary checkpoint ZIP to write.")\n'
        '    ap.add_argument("--checkpoint-every-updates", type=int, default=50,\n'
        '                    help="Write a checkpoint after this many completed updates.")\n'
        '    ap.add_argument("--resume-checkpoint", type=Path, default=None,\n'
        '                    help="Validated checkpoint ZIP from which to continue.")\n'
        '    ap.add_argument("--stop-after-update", type=int, default=None,\n'
        '                    help="Execution-only test hook: stop after N completed updates.")\n',
        label="checkpoint arguments",
    )
    transformed = _replace_once(
        transformed,
        "    args = ap.parse_args()\n\n",
        "    args = ap.parse_args()\n"
        "    if args.checkpoint_every_updates < 1:\n"
        '        raise ValueError("--checkpoint-every-updates must be positive")\n'
        "    if args.stop_after_update is not None and args.stop_after_update < 1:\n"
        '        raise ValueError("--stop-after-update must be positive")\n'
        "    if args.resume_checkpoint is not None and args.checkpoint_path is None:\n"
        '        raise ValueError("--resume-checkpoint requires --checkpoint-path")\n\n',
        label="argument validation",
    )
    transformed = _replace_once(
        transformed,
        "    import flax.linen as nn\n    import optax\n"
        "    from flax.training.train_state import TrainState\n",
        "    import flax.linen as nn\n    import optax\n"
        "    from flax import serialization\n"
        "    from flax.training.train_state import TrainState\n",
        label="serialization import",
    )

    old_state_block = '''    # --- init envs ---
    key, rk = jax.random.split(key)
    reset_keys = jax.random.split(rk, num_envs)
    obs, env_state = reset_batch(reset_keys)

    ep_ret = np.zeros(num_envs, dtype=np.float64)
    finished_returns = []
    # Completion counters: raw task counts per env (step-by-step)
    ep_tasks_total = np.zeros(num_envs, dtype=np.int64)
    ep_tasks_completed = np.zeros(num_envs, dtype=np.int64)
    finished_completions = []
    ep_action_hist = np.zeros((num_envs, 3), dtype=np.int64)
    finished_action_hists = []
    # Per-type completion counters: types are 0,1,2 (= 3GPP task type 1,2,3).
    ep_type_total = np.zeros((num_envs, 3), dtype=np.int64)
    ep_type_completed = np.zeros((num_envs, 3), dtype=np.int64)
    finished_type_completions = []   # list of [3] arrays (rate per type per episode)
    # Per-episode fleet-total energy; avg_energy_j = fleet_total / tasks_total
    # to mirror the reference PyTorch env's `avg_energy_j` metric.
    ep_energy_j = np.zeros(num_envs, dtype=np.float64)
    finished_avg_energies = []
    # Per-episode fleet-total latency; avg_latency_ms = total_latency / tasks_total
    # to mirror the reference PyTorch env's `avg_latency_ms` metric.
    ep_latency_ms = np.zeros(num_envs, dtype=np.float64)
    finished_avg_latencies = []

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    f = open(out_csv, "w", newline="")
    w = csv.writer(f)
    w.writerow([
        "update", "env_step", "mean_return", "mean_completion",
        "p_local", "p_v2i", "p_v2v", "avg_energy_j", "avg_latency_ms",
        "type_1_completion", "type_2_completion", "type_3_completion",
        "elapsed_s", "sps",
    ])

    total_env_steps = 0
    t_start = time.perf_counter()

    # Raw per-rollout-step decision-time array (one entry per call to the
    # actor forward → produces actions for all num_envs × num_agents at once).
    # Times the whole "decide-an-action" cost: mask computation + actor forward.
    # block_until_ready() is called to force JAX synchronisation so we don't
    # measure dispatch-only time. Saved to decision_ms_raw.npz at the end.
    raw_decision_ms_all = []
    raw_decision_step_idx = []
    _global_step = 0

    for upd in range(updates_per_total):
'''
    new_state_block = '''    # --- init envs ---
    key, rk = jax.random.split(key)
    reset_keys = jax.random.split(rk, num_envs)
    obs, env_state = reset_batch(reset_keys)

    ep_ret = np.zeros(num_envs, dtype=np.float64)
    finished_returns = []
    # Completion counters: raw task counts per env (step-by-step)
    ep_tasks_total = np.zeros(num_envs, dtype=np.int64)
    ep_tasks_completed = np.zeros(num_envs, dtype=np.int64)
    finished_completions = []
    ep_action_hist = np.zeros((num_envs, 3), dtype=np.int64)
    finished_action_hists = []
    # Per-type completion counters: types are 0,1,2 (= 3GPP task type 1,2,3).
    ep_type_total = np.zeros((num_envs, 3), dtype=np.int64)
    ep_type_completed = np.zeros((num_envs, 3), dtype=np.int64)
    finished_type_completions = []   # list of [3] arrays (rate per type per episode)
    # Per-episode fleet-total energy; avg_energy_j = fleet_total / tasks_total
    # to mirror the reference PyTorch env's `avg_energy_j` metric.
    ep_energy_j = np.zeros(num_envs, dtype=np.float64)
    finished_avg_energies = []
    # Per-episode fleet-total latency; avg_latency_ms = total_latency / tasks_total
    # to mirror the reference PyTorch env's `avg_latency_ms` metric.
    ep_latency_ms = np.zeros(num_envs, dtype=np.float64)
    finished_avg_latencies = []

    # Raw per-rollout-step decision-time arrays.  They are operational timing
    # observations, but their indices and values are retained across restarts.
    raw_decision_ms_all = []
    raw_decision_step_idx = []
    _global_step = 0
    total_env_steps = 0
    start_update = 0
    elapsed_before_resume = 0.0

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    trainer_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    trace_sha256 = os.environ.get("VEC_JAX_TRACE_SHA256", "")
    checkpoint_settings = {
        "seed": args.seed,
        "total_timesteps": args.total_timesteps,
        "num_envs": num_envs,
        "rollout_len": rollout_len,
        "updates_per_total": updates_per_total,
        "update_epochs": args.update_epochs,
        "num_minibatches": args.num_minibatches,
        "lr": args.lr,
        "gamma": args.gamma,
        "gae_lambda": args.gae_lambda,
        "clip_eps": args.clip_eps,
        "ent_coef": args.ent_coef,
        "vf_coef": args.vf_coef,
        "max_grad_norm": args.max_grad_norm,
        "hidden": args.hidden,
        "ippo": args.ippo,
        "use_mask": args.use_mask,
        "init_actor": args.init_actor,
        "task_dist": args.task_dist,
        "stress_config": args.stress_config,
        "trace_sha256": trace_sha256,
        "trainer_sha256": trainer_sha256,
    }

    def _sha256(value):
        return hashlib.sha256(value).hexdigest()

    def _state_values_equal(left, right):
        if isinstance(left, dict) and isinstance(right, dict):
            return left.keys() == right.keys() and all(
                _state_values_equal(left[key], right[key]) for key in left
            )
        if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
            return len(left) == len(right) and all(
                _state_values_equal(a, b) for a, b in zip(left, right)
            )
        return np.array_equal(np.asarray(left), np.asarray(right))

    def _atomic_bytes(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(value)
        os.replace(temporary, path)

    def _checkpoint_device_template():
        return {
            "actor_state": actor_state,
            "critic_state": critic_state,
            "key": key,
            "obs": obs,
            "env_state": env_state,
        }

    def _write_checkpoint(next_update, elapsed_s):
        if args.checkpoint_path is None:
            return
        checkpoint_path = Path(args.checkpoint_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        device_bytes = serialization.to_bytes(_checkpoint_device_template())
        with tempfile.TemporaryDirectory(
            prefix=checkpoint_path.name + ".", dir=checkpoint_path.parent
        ) as temporary_dir:
            temporary_root = Path(temporary_dir)
            host_path = temporary_root / "host.npz"
            np.savez_compressed(
                host_path,
                next_update=np.int64(next_update),
                total_env_steps=np.int64(total_env_steps),
                global_step=np.int64(_global_step),
                elapsed_s=np.float64(elapsed_s),
                ep_ret=ep_ret,
                finished_returns=np.asarray(finished_returns, dtype=np.float64),
                ep_tasks_total=ep_tasks_total,
                ep_tasks_completed=ep_tasks_completed,
                finished_completions=np.asarray(finished_completions, dtype=np.float64),
                ep_action_hist=ep_action_hist,
                finished_action_hists=np.asarray(
                    finished_action_hists, dtype=np.int64
                ).reshape((-1, 3)),
                ep_type_total=ep_type_total,
                ep_type_completed=ep_type_completed,
                finished_type_completions=np.asarray(
                    finished_type_completions, dtype=np.float64
                ).reshape((-1, 3)),
                ep_energy_j=ep_energy_j,
                finished_avg_energies=np.asarray(
                    finished_avg_energies, dtype=np.float64
                ),
                ep_latency_ms=ep_latency_ms,
                finished_avg_latencies=np.asarray(
                    finished_avg_latencies, dtype=np.float64
                ),
                raw_decision_ms_all=np.asarray(raw_decision_ms_all, dtype=np.float64),
                raw_decision_step_idx=np.asarray(raw_decision_step_idx, dtype=np.int64),
            )
            host_bytes = host_path.read_bytes()
            curve_bytes = out_csv.read_bytes()
            components = {
                "device.msgpack": device_bytes,
                "host.npz": host_bytes,
                "curve.csv": curve_bytes,
            }
            manifest = {
                "schema_version": "bbus-update-checkpoint-1.0",
                "next_update": next_update,
                "total_env_steps": total_env_steps,
                "settings": checkpoint_settings,
                "components": {
                    name: {"bytes": len(value), "sha256": _sha256(value)}
                    for name, value in components.items()
                },
            }
            manifest_bytes = (
                json.dumps(manifest, indent=2, sort_keys=True) + "\\n"
            ).encode("utf-8")
            components["manifest.json"] = manifest_bytes
            archive_temporary = temporary_root / "checkpoint.zip"
            with zipfile.ZipFile(
                archive_temporary,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                for name, value in components.items():
                    info = zipfile.ZipInfo(name, date_time=(2026, 7, 29, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100600 << 16
                    archive.writestr(info, value)
            archive_bytes = archive_temporary.read_bytes()
            os.replace(archive_temporary, checkpoint_path)
        status = {
            "schema_version": "bbus-update-checkpoint-status-1.0",
            "checkpoint_filename": checkpoint_path.name,
            "checkpoint_bytes": len(archive_bytes),
            "checkpoint_sha256": _sha256(archive_bytes),
            "next_update": next_update,
            "total_env_steps": total_env_steps,
        }
        _atomic_bytes(
            Path(str(checkpoint_path) + ".json"),
            (json.dumps(status, indent=2, sort_keys=True) + "\\n").encode("utf-8"),
        )

    if args.resume_checkpoint is not None:
        resume_path = Path(args.resume_checkpoint)
        with zipfile.ZipFile(resume_path) as archive:
            expected_names = {"device.msgpack", "host.npz", "curve.csv", "manifest.json"}
            if set(archive.namelist()) != expected_names or archive.testzip() is not None:
                raise ValueError("checkpoint ZIP inventory or CRC is invalid")
            component_bytes = {name: archive.read(name) for name in expected_names}
        manifest = json.loads(component_bytes["manifest.json"])
        if manifest.get("schema_version") != "bbus-update-checkpoint-1.0":
            raise ValueError("checkpoint schema differs")
        if manifest.get("settings") != checkpoint_settings:
            raise ValueError("checkpoint training settings differ from this invocation")
        for name in ("device.msgpack", "host.npz", "curve.csv"):
            expected_component = manifest["components"].get(name, {})
            value = component_bytes[name]
            if expected_component != {"bytes": len(value), "sha256": _sha256(value)}:
                raise ValueError(f"checkpoint component changed: {name}")
        start_update = int(manifest["next_update"])
        if not 0 < start_update <= updates_per_total:
            raise ValueError("checkpoint next update is outside the frozen run")
        curve_text = component_bytes["curve.csv"].decode("utf-8")
        curve_rows = list(csv.DictReader(io.StringIO(curve_text)))
        if len(curve_rows) != start_update:
            raise ValueError("checkpoint curve row count differs from next update")
        if int(curve_rows[-1]["update"]) != start_update - 1:
            raise ValueError("checkpoint curve last update differs")
        restored = serialization.from_bytes(
            _checkpoint_device_template(), component_bytes["device.msgpack"]
        )
        archived_state = serialization.msgpack_restore(component_bytes["device.msgpack"])
        restored_state = serialization.to_state_dict(restored)
        if not _state_values_equal(archived_state, restored_state):
            raise ValueError("checkpoint device state values are not an exact round trip")
        actor_state = restored["actor_state"]
        critic_state = restored["critic_state"]
        key = restored["key"]
        obs = restored["obs"]
        env_state = restored["env_state"]
        with np.load(io.BytesIO(component_bytes["host.npz"]), allow_pickle=False) as host:
            if int(host["next_update"].item()) != start_update:
                raise ValueError("checkpoint host next update differs")
            total_env_steps = int(host["total_env_steps"].item())
            _global_step = int(host["global_step"].item())
            elapsed_before_resume = float(host["elapsed_s"].item())
            ep_ret = host["ep_ret"].copy()
            finished_returns = host["finished_returns"].tolist()
            ep_tasks_total = host["ep_tasks_total"].copy()
            ep_tasks_completed = host["ep_tasks_completed"].copy()
            finished_completions = host["finished_completions"].tolist()
            ep_action_hist = host["ep_action_hist"].copy()
            finished_action_hists = [row.copy() for row in host["finished_action_hists"]]
            ep_type_total = host["ep_type_total"].copy()
            ep_type_completed = host["ep_type_completed"].copy()
            finished_type_completions = [
                row.copy() for row in host["finished_type_completions"]
            ]
            ep_energy_j = host["ep_energy_j"].copy()
            finished_avg_energies = host["finished_avg_energies"].tolist()
            ep_latency_ms = host["ep_latency_ms"].copy()
            finished_avg_latencies = host["finished_avg_latencies"].tolist()
            raw_decision_ms_all = host["raw_decision_ms_all"].tolist()
            raw_decision_step_idx = host["raw_decision_step_idx"].tolist()
        if total_env_steps != start_update * num_envs * rollout_len:
            raise ValueError("checkpoint environment-step count differs")
        if _global_step != start_update * rollout_len:
            raise ValueError("checkpoint decision-step index differs")
        _atomic_bytes(out_csv, component_bytes["curve.csv"])
        f = open(out_csv, "a", newline="")
        print(
            f"[resume] checkpoint={resume_path.name} next_update={start_update} "
            f"env_step={total_env_steps} device_roundtrip=bitwise_equal",
            flush=True,
        )
    else:
        f = open(out_csv, "w", newline="")
        w_initial = csv.writer(f)
        w_initial.writerow([
            "update", "env_step", "mean_return", "mean_completion",
            "p_local", "p_v2i", "p_v2v", "avg_energy_j", "avg_latency_ms",
            "type_1_completion", "type_2_completion", "type_3_completion",
            "elapsed_s", "sps",
        ])
        f.flush()
    w = csv.writer(f)
    t_start = time.perf_counter()

    for upd in range(start_update, updates_per_total):
'''
    transformed = _replace_once(
        transformed,
        old_state_block,
        new_state_block,
        label="training state and loop boundary",
    )
    transformed = _replace_once(
        transformed,
        "        elapsed = time.perf_counter() - t_start\n",
        "        elapsed = elapsed_before_resume + time.perf_counter() - t_start\n",
        label="elapsed accumulation",
    )
    transformed = _replace_once(
        transformed,
        "        f.flush()\n        if upd % 5 == 0 or upd == updates_per_total - 1:\n",
        "        f.flush()\n"
        "        os.fsync(f.fileno())\n"
        "        next_update = upd + 1\n"
        "        if (\n"
        "            args.checkpoint_path is not None\n"
        "            and (\n"
        "                next_update % args.checkpoint_every_updates == 0\n"
        "                or next_update == updates_per_total\n"
        "                or (\n"
        "                    args.stop_after_update is not None\n"
        "                    and next_update >= args.stop_after_update\n"
        "                )\n"
        "            )\n"
        "        ):\n"
        "            _write_checkpoint(next_update, elapsed)\n"
        "        if args.stop_after_update is not None and next_update >= args.stop_after_update:\n"
        "            f.close()\n"
        "            print(\n"
        "                f\"[stop] execution test stopped after update {next_update}\",\n"
        "                flush=True,\n"
        "            )\n"
        "            return\n"
        "        if upd % 5 == 0 or upd == updates_per_total - 1:\n",
        label="checkpoint commit boundary",
    )
    compile(transformed, "train_mappo_vec_checkpointed.py", "exec")
    return transformed


def write_checkpointed_trainer(source: Path, destination: Path) -> dict[str, object]:
    """Create a new private derived trainer and return its provenance binding."""

    if destination.exists():
        raise ValueError("checkpointed trainer destination must be new")
    source_bytes = source.read_bytes()
    transformed = checkpointed_train_text(source_bytes.decode("utf-8"))
    destination.write_text(transformed, encoding="utf-8")
    return {
        "method_version": METHOD_VERSION,
        "upstream_path": source.name,
        "upstream_sha256": sha256_bytes(source_bytes),
        "derived_path": destination.name,
        "derived_sha256": sha256_bytes(destination.read_bytes()),
        "scientific_settings_changed": False,
        "checkpoint_boundary": "completed_ppo_update",
    }
