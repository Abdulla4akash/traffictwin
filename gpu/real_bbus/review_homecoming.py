"""Independently recheck a returned checkpointed B-BUS result archive."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import statistics
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gpu.real_bbus.run_campaign import (
    CAMPAIGN_VERSION,
    CAPACITY_PER_SLOT,
    CHECKPOINT_EVERY_UPDATES,
    CHECKPOINT_SCHEMA_VERSION,
    EFFECTIVE_TIMESTEPS,
    EVALUATION_TASK_SEED_OFFSET,
    EXPECTED_RUNTIME,
    EXPECTED_UPDATES,
    JAX_PLATFORM,
    LEARNING_RATE,
    MODEL_SEEDS,
    NUM_ENVS,
    REQUESTED_TIMESTEPS,
    ROLLOUT_LEN,
    TRAINING_CAPACITY_PER_SLOT,
    _summarise,
    _validate_completed_job,
    campaign_jobs,
    sha256_file,
    verify_pack,
)

METHOD_VERSION = "bbus-checkpointed-local-homecoming-review-1.0"


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _checked_members(archive: zipfile.ZipFile, expected_root: str) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError("ZIP contains duplicate member names")
    for info in infos:
        if info.flag_bits & 0x1:
            raise ValueError("ZIP contains an encrypted member")
        if "\\" in info.filename:
            raise ValueError("ZIP member uses a non-portable path separator")
        member = PurePosixPath(info.filename)
        if (
            member.is_absolute()
            or not member.parts
            or member.parts[0] != expected_root
            or ".." in member.parts
        ):
            raise ValueError(f"ZIP member escapes the expected root: {info.filename}")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError("ZIP contains a symbolic link")
    if archive.testzip() is not None:
        raise ValueError("ZIP failed CRC verification")
    return infos


def _extract_checked(archive_path: Path, destination: Path, expected_root: str) -> dict[str, int]:
    with zipfile.ZipFile(archive_path) as archive:
        infos = _checked_members(archive, expected_root)
        for info in infos:
            relative = PurePosixPath(info.filename)
            target = destination.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return {
        "zip_members": len(infos),
        "uncompressed_member_bytes": sum(info.file_size for info in infos),
    }


def _verify_inventory(output_root: Path) -> dict[str, int]:
    inventory_path = output_root / "campaign_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if inventory.get("scientific_evidence") is not False:
        raise ValueError("campaign inventory promotes scientific evidence")
    if inventory.get("actor_admission_eligible") is not False:
        raise ValueError("campaign inventory promotes actor admission")
    declared = inventory.get("files")
    if not isinstance(declared, list):
        raise ValueError("campaign inventory has no file list")
    by_path: dict[str, dict[str, Any]] = {}
    for item in declared:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise ValueError("campaign inventory row shape differs")
        relative = str(item["path"])
        if relative in by_path:
            raise ValueError("campaign inventory repeats a path")
        by_path[relative] = item
    observed = {
        path.relative_to(output_root).as_posix(): path
        for path in output_root.rglob("*")
        if path.is_file() and path != inventory_path
    }
    if set(observed) != set(by_path):
        raise ValueError("campaign inventory member set differs")
    for relative, path in observed.items():
        item = by_path[relative]
        if path.stat().st_size != item["bytes"]:
            raise ValueError(f"campaign inventory byte count differs: {relative}")
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"campaign inventory digest differs: {relative}")
    return {"inventoried_payload_members": len(observed)}


def _verify_design(pack_root: Path, output_root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    design = json.loads((output_root / "campaign_design.json").read_text(encoding="utf-8"))
    exact = {
        "campaign_version": CAMPAIGN_VERSION,
        "experiment_id": binding["experiment_id"],
        "arm": binding["arm"],
        "binding_sha256": sha256_file(pack_root / "campaign_binding.json"),
        "protocol_sha256": binding["protocol_sha256"],
        "jobs": [{"model_seed": seed} for seed in MODEL_SEEDS],
        "training_trace": "dawn_trace.npz",
        "held_out_trace": "peak_trace.npz",
        "training_capacity_per_slot": TRAINING_CAPACITY_PER_SLOT,
        "evaluation_capacity_per_slot": list(CAPACITY_PER_SLOT),
        "evaluation_task_seed_offset": EVALUATION_TASK_SEED_OFFSET,
        "fleet_seed_equals_model_seed": True,
        "requested_timesteps_per_job": REQUESTED_TIMESTEPS,
        "effective_timesteps_per_job": EFFECTIVE_TIMESTEPS,
        "num_envs": NUM_ENVS,
        "rollout_len": ROLLOUT_LEN,
        "learning_rate": LEARNING_RATE,
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "checkpoint_transform": binding["checkpoint_execution"],
        "checkpoint_every_updates": CHECKPOINT_EVERY_UPDATES,
        "checkpoint_boundary": "completed_ppo_update",
        "checkpointing_changes_scientific_settings": False,
        "peak_used_for_training_or_selection": False,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    for key, expected in exact.items():
        if design.get(key) != expected:
            raise ValueError(f"campaign design differs for {key}")
    runtime = design.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("campaign design has no runtime record")
    for package, version in EXPECTED_RUNTIME.items():
        if runtime.get(package) != version:
            raise ValueError(f"campaign runtime differs for {package}")
    if runtime.get("jax_backend") != "gpu" or not runtime.get("nvidia_gpu_name"):
        raise ValueError("campaign runtime is not a named GPU backend")
    common = design.get("common_environment")
    if not isinstance(common, dict) or common.get("JAX_PLATFORMS") != JAX_PLATFORM:
        raise ValueError("campaign common environment differs")
    return design


def _verify_progress(output_root: Path) -> dict[str, Any]:
    progress = json.loads((output_root / "campaign_progress.json").read_text(encoding="utf-8"))
    if progress.get("campaign_version") != CAMPAIGN_VERSION:
        raise ValueError("campaign progress version differs")
    if progress.get("status") != "completed" or progress.get("execution_max_workers") != 5:
        raise ValueError("campaign progress is not five-worker complete")
    jobs = progress.get("jobs")
    expected = {f"model-seed-{seed}" for seed in MODEL_SEEDS}
    if not isinstance(jobs, dict) or set(jobs) != expected:
        raise ValueError("campaign progress job set differs")
    if any(value.get("status") != "completed" for value in jobs.values()):
        raise ValueError("campaign progress contains an incomplete job")
    return progress


def _verify_jobs(output_root: Path, binding: dict[str, Any]) -> dict[int, dict[str, Any]]:
    validations: dict[int, dict[str, Any]] = {}
    for job in campaign_jobs():
        observed = _validate_completed_job(output_root, job, binding)
        manifest_path = output_root / f"model-seed-{job.model_seed}_run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exact = {
            "campaign_version": CAMPAIGN_VERSION,
            "experiment_id": binding["experiment_id"],
            "arm": binding["arm"],
            "job": {"model_seed": job.model_seed},
            "resumed_from_update_checkpoint": True,
            "validation": observed,
            "scientific_evidence": False,
            "actor_admission_eligible": False,
        }
        for key, expected in exact.items():
            if manifest.get(key) != expected:
                raise ValueError(f"model seed {job.model_seed} manifest differs for {key}")
        command = manifest.get("train_command", [])
        if "--resume-checkpoint" not in command:
            raise ValueError(f"model seed {job.model_seed} does not disclose resume")
        evaluations = manifest.get("evaluation_commands")
        if not isinstance(evaluations, list) or [
            item.get("capacity_per_slot") for item in evaluations
        ] != list(CAPACITY_PER_SLOT):
            raise ValueError(f"model seed {job.model_seed} evaluation commands differ")
        validations[job.model_seed] = observed
    return validations


def _metric_summary(validations: dict[int, dict[str, Any]]) -> dict[str, Any]:
    keys = (
        "completion",
        "t1_completion",
        "t2_completion",
        "t3_completion",
        "avg_latency_ms_per_task",
        "avg_energy_j_per_task",
        "p_local",
        "p_v2i",
        "p_v2v",
    )
    result: dict[str, Any] = {}
    for slug in ("0p75", "2p5"):
        rows = [validations[seed]["held_out_peak"][slug] for seed in MODEL_SEEDS]
        result[slug] = {
            **{key: statistics.fmean(float(row[key]) for row in rows) for key in keys},
            "completion_sample_sd": statistics.stdev(float(row["completion"]) for row in rows),
            "completion_minimum": min(float(row["completion"]) for row in rows),
            "completion_maximum": max(float(row["completion"]) for row in rows),
            "total_tasks": sum(int(row["total_tasks"]) for row in rows),
            "per_seed": [
                {
                    "model_seed": seed,
                    **{key: validations[seed]["held_out_peak"][slug][key] for key in keys},
                    "total_tasks": int(validations[seed]["held_out_peak"][slug]["total_tasks"]),
                }
                for seed in MODEL_SEEDS
            ],
        }
    result["difference_2p5_minus_0p75"] = {
        key: result["2p5"][key] - result["0p75"][key]
        for key in (
            "completion",
            "avg_latency_ms_per_task",
            "avg_energy_j_per_task",
            "p_local",
            "p_v2i",
            "p_v2v",
        )
    }
    return result


def _return_event_counts(text: str) -> dict[str, Any]:
    """Count completed result returns, including a download before a wait timeout.

    The supervisor moves a CRC-checked result download into place before waiting for
    the foreground ``colab exec`` RPC to exit.  If that wait times out, the terminal
    JSON is never written even though a complete campaign archive was returned.
    Counting only terminal JSON would therefore conceal a repeated held-out run.
    """

    returned_hashes = re.findall(r'^  "result_sha256": "([0-9a-f]{64})",$', text, re.MULTILINE)
    successful_downloads = len(
        re.findall(
            r"\[colab\] Downloaded '/content/bbus_sparse64_results\.zip' "
            r"to '[^']+bbus_sparse64_results\.zip\.download'",
            text,
        )
    )
    complete_returns = max(len(returned_hashes), successful_downloads)
    return {
        "returned_hashes": returned_hashes,
        "terminal_return_records": len(returned_hashes),
        "successful_result_downloads": successful_downloads,
        "complete_returned_campaigns": complete_returns,
        "post_download_timeout_events": len(
            re.findall(r"error: TimeoutExpired: Command .* timed out after", text)
        ),
    }


def _supervision_history(
    *, supervisor_log: Path, supervisor_result: Path, archive: Path, output_root: Path
) -> dict[str, Any]:
    text = supervisor_log.read_text(encoding="utf-8")
    events = _return_event_counts(text)
    returned_hashes = events["returned_hashes"]
    if not returned_hashes:
        raise ValueError("supervisor log contains no returned campaign record")
    current_digest = sha256_file(archive)
    result = json.loads(supervisor_result.read_text(encoding="utf-8"))
    if (
        result.get("status") != "returned"
        or result.get("result_sha256") != current_digest
        or returned_hashes[-1] != current_digest
        or result.get("result_bytes") != archive.stat().st_size
    ):
        raise ValueError("supervisor terminal result does not bind the retained archive")
    checkpoint_matches: dict[str, bool] = {}
    for seed in MODEL_SEEDS:
        local = supervisor_log.parent / f"model-seed-{seed}.checkpoint.zip"
        returned = output_root / f"model-seed-{seed}.checkpoint.zip"
        checkpoint_matches[str(seed)] = local.is_file() and sha256_file(local) == sha256_file(
            returned
        )
    if not all(checkpoint_matches.values()):
        raise ValueError("returned terminal checkpoints differ from the local mirror")
    complete_returns = int(events["complete_returned_campaigns"])
    return {
        "supervisor_log_sha256": sha256_file(supervisor_log),
        "supervisor_result_sha256": sha256_file(supervisor_result),
        "complete_returned_campaigns": complete_returns,
        "unintended_complete_repeats_after_the_first": complete_returns - 1,
        "successful_result_downloads": events["successful_result_downloads"],
        "terminal_return_records": events["terminal_return_records"],
        "post_download_timeout_events": events["post_download_timeout_events"],
        "unique_returned_archive_hashes": len(set(returned_hashes)),
        "retained_archive_is_last_return": True,
        "runtime_loss_events_before_completion": len(
            re.findall(r"attempt ended: RuntimeError: remote campaign output disappeared", text)
        ),
        "terminal_checkpoint_matches_local_mirror": checkpoint_matches,
        "held_out_peak_one_shot_execution_observed": complete_returns == 1,
    }


def review_homecoming(
    *,
    pack_archive: Path,
    result_archive: Path,
    supervisor_log: Path,
    supervisor_result: Path,
    reviewed_at_utc: str,
) -> dict[str, Any]:
    pack_archive = pack_archive.resolve()
    result_archive = result_archive.resolve()
    with tempfile.TemporaryDirectory(prefix="bbus-homecoming-") as temporary:
        root = Path(temporary)
        pack_stats = _extract_checked(pack_archive, root / "pack", "bbus_sparse64_colab")
        result_stats = _extract_checked(result_archive, root / "result", "bbus_sparse64_results")
        pack_root = root / "pack/bbus_sparse64_colab"
        output_root = root / "result/bbus_sparse64_results"
        binding = verify_pack(pack_root)
        if binding.get("arm") != "sparse64":
            raise ValueError("homecoming pack is not the Sparse-64 arm")
        design = _verify_design(pack_root, output_root, binding)
        progress = _verify_progress(output_root)
        inventory = _verify_inventory(output_root)
        validations = _verify_jobs(output_root, binding)
        observed_summary = json.loads(
            (output_root / "campaign_summary.json").read_text(encoding="utf-8")
        )
        recomputed_summary = _summarise(output_root, binding)
        if observed_summary != recomputed_summary:
            raise ValueError("campaign summary differs from independent recomputation")
        history = _supervision_history(
            supervisor_log=supervisor_log.resolve(),
            supervisor_result=supervisor_result.resolve(),
            archive=result_archive,
            output_root=output_root,
        )
        metrics = _metric_summary(validations)
    one_shot = history["held_out_peak_one_shot_execution_observed"]
    if history["post_download_timeout_events"]:
        deviation_cause = (
            "the supervisor downloaded and CRC-checked a complete archive, then timed out "
            "waiting for the already-terminal foreground Colab RPC; launchd restarted before "
            "terminal state was written and caused a second held-out evaluation/return"
        )
    elif not one_shot:
        deviation_cause = (
            "launchd relaunched the successful supervisor because no terminal-result "
            "idempotence guard existed"
        )
    else:
        deviation_cause = None
    return {
        "schema_version": "1.0",
        "method_version": METHOD_VERSION,
        "reviewed_at_utc": reviewed_at_utc,
        "experiment_id": binding["experiment_id"],
        "arm": "sparse64",
        "status": (
            "RETURNED_ARCHIVE_INTEGRITY_PASS__ONE_SHOT_HELD_OUT_EXECUTION_OBSERVED__"
            "NON_ADMITTED_PENDING_INDEPENDENT_ADMISSION"
            if one_shot
            else "RETURNED_ARCHIVE_INTEGRITY_PASS__HELD_OUT_REPEAT_DEVIATION__NON_ADMITTED"
        ),
        "returned_archive": {
            "filename": result_archive.name,
            "compressed_bytes": result_archive.stat().st_size,
            "sha256": sha256_file(result_archive),
            **result_stats,
            **inventory,
        },
        "frozen_pack": {
            "filename": pack_archive.name,
            "compressed_bytes": pack_archive.stat().st_size,
            "sha256": sha256_file(pack_archive),
            **pack_stats,
            "campaign_binding_sha256": design["binding_sha256"],
            "protocol_sha256": design["protocol_sha256"],
        },
        "local_checks": {
            "safe_unique_non_symlink_zip_paths": True,
            "all_zip_crc_checks_pass": True,
            "inventory_member_set_size_and_sha256_exact": True,
            "campaign_progress_completed": progress["status"] == "completed",
            "completed_jobs": len(validations),
            "expected_jobs": len(MODEL_SEEDS),
            "all_terminal_checkpoints_at_update": EXPECTED_UPDATES,
            "all_effective_timesteps": EFFECTIVE_TIMESTEPS,
            "all_actor_input_shapes": [17, 64],
            "all_resume_disclosures_present": True,
            "all_evaluation_metadata_and_action_shares_checked": True,
            "summary_recomputed_exactly": True,
        },
        "runtime": design["runtime"],
        "checkpoint_execution": {
            "transform": design["checkpoint_transform"],
            "every_updates": CHECKPOINT_EVERY_UPDATES,
            "boundary": design["checkpoint_boundary"],
            "scientific_settings_changed": False,
            "cross_process_float32_trajectory_claimed_bitwise_identical": False,
        },
        "supervision_history": history,
        "execution_deviation": {
            "requirement": "each frozen actor evaluates the held-out peak once",
            "observed_complete_returned_campaigns": history["complete_returned_campaigns"],
            "cause": deviation_cause,
            "actor_or_scientific_setting_changed_after_terminal_checkpoint": False,
            "metric_based_selection_performed_by_supervisor": False,
            "cross_repeat_metric_identity_verifiable_from_preserved_archives": one_shot,
            "effect": (
                "no held-out repeat deviation was observed; actor admission and supervisor "
                "approval remain separate and incomplete"
                if one_shot
                else "current archive can be reported only as execution-deviated, non-admitted "
                "descriptive output; it does not satisfy the literal one-shot held-out run"
            ),
        },
        "held_out_peak": metrics,
        "coverage_diagnostics": {
            "dawn_vehicle_second_share": binding["traces"]["dawn"]["exact_coverage_share"],
            "peak_vehicle_second_share": binding["traces"]["peak"]["exact_coverage_share"],
            "analysis_sites": binding["traces"]["dawn"]["rsu_count"],
            "vec06_compatible": False,
        },
        "claim_ceiling": {
            "scientific_evidence": False,
            "actor_admission_eligible": False,
            "local_archive_homecoming_review_completed": True,
            "independent_actor_admission_completed": False,
            "supervisor_approved": False,
            "causal_rush_hour_claim": False,
            "real_computing_tasks_observed": False,
            "observed_rsus": False,
            "general_manchester_claim": False,
        },
        "owner_decisions_taken_by_agent": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--supervisor-log", type=Path, required=True)
    parser.add_argument("--supervisor-result", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--reviewed-at-utc", default=datetime.now(UTC).isoformat())
    args = parser.parse_args(argv)
    try:
        result = review_homecoming(
            pack_archive=args.pack,
            result_archive=args.result,
            supervisor_log=args.supervisor_log,
            supervisor_result=args.supervisor_result,
            reviewed_at_utc=args.reviewed_at_utc,
        )
        _atomic_json(args.out_json, result)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
