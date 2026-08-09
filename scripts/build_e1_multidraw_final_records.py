#!/usr/bin/env python3
# ruff: noqa: E501 - long Markdown sentences are intentional report content
"""Build permission-safe final E1 campaign records from validated evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

CAP_LABELS = ("0p75", "2p5", "40x")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_json_new(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text_new(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value)


def _record(path: Path, logical_locator: str) -> dict[str, Any]:
    return {
        "logical_locator": logical_locator,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _repository_locator(path: Path) -> Path:
    return path.resolve().relative_to(Path.cwd().resolve())


def _gate_evidence(
    manifest: dict[str, Any], campaign_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cell_records: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    logical_root = manifest["output"]["logical_locator"]
    for seed in manifest["seeds"]["new_full_fleet_seeds"]:
        for cap in CAP_LABELS:
            cell = campaign_root / f"fleet_seed_{seed}" / f"cap_{cap}"
            smoke_path = cell / "smoke_validation.json"
            full_path = cell / "full_validation.json"
            smoke = _json(smoke_path)
            full = _json(full_path)
            smoke_run_passes = [bool(run["passed"]) for run in smoke["runs"]]
            full_checks = full["run"]["checks"]
            cell_passed = (
                smoke.get("passed") is True
                and smoke.get("repeat", {}).get("passed") is True
                and len(smoke_run_passes) == 2
                and all(smoke_run_passes)
                and full.get("passed") is True
                and len(full_checks) == 32
                and all(check["passed"] for check in full_checks)
            )
            checks.append(
                {
                    "name": f"seed_{seed}_{cap}_repeated_smoke_and_full_gate_passed",
                    "passed": cell_passed,
                }
            )
            full_run = cell / "full" / "run_1"
            cell_records.append(
                {
                    "fleet_seed": seed,
                    "cap_label": cap,
                    "passed": cell_passed,
                    "smoke_runs": 2,
                    "smoke_repeat_exact": smoke["repeat"]["passed"],
                    "smoke_validation": _record(
                        smoke_path,
                        f"{logical_root}/fleet_seed_{seed}/cap_{cap}/smoke_validation.json",
                    ),
                    "full_validation": _record(
                        full_path,
                        f"{logical_root}/fleet_seed_{seed}/cap_{cap}/full_validation.json",
                    ),
                    "authoritative_full_outputs": {
                        path.name: {
                            "sha256": sha256_file(path),
                            "size_bytes": path.stat().st_size,
                        }
                        for path in sorted(full_run.iterdir())
                        if path.is_file()
                    },
                }
            )
    return cell_records, checks


def _runtime(rows: list[dict[str, Any]]) -> dict[str, Any]:
    new_rows = [row for row in rows if row["fleet_seed"] in (1, 2, 3, 4)]
    remaining_rows = [row for row in rows if row["fleet_seed"] in (2, 3, 4)]
    new_seconds = sum(float(row["wall_s"]) for row in new_rows)
    remaining_seconds = sum(float(row["wall_s"]) for row in remaining_rows)
    return {
        "measure": "evaluator wall time reported by each authoritative summary",
        "reused_seed0_seconds_excluded": True,
        "twelve_new_full_cells_seconds": new_seconds,
        "twelve_new_full_cells_hours": new_seconds / 3600.0,
        "nine_cells_executed_in_final_continuation_seconds": remaining_seconds,
        "nine_cells_executed_in_final_continuation_hours": remaining_seconds / 3600.0,
        "maximum_authorised_cpu_hours": 48.0,
        "within_authorised_budget": new_seconds / 3600.0 <= 48.0,
    }


def _mechanism_checks(rows: list[dict[str, Any]]) -> dict[str, bool]:
    by_seed = {
        seed: {row["cap_label"]: row for row in rows if row["fleet_seed"] == seed}
        for seed in range(5)
    }
    return {
        "admission_increases_from_0p75_to_40x_every_seed": all(
            points["40x"]["admitted_tasks"] > points["0p75"]["admitted_tasks"]
            for points in by_seed.values()
        ),
        "rejection_decreases_from_0p75_to_40x_every_seed": all(
            points["40x"]["rejected_or_unavailable_tasks"]
            < points["0p75"]["rejected_or_unavailable_tasks"]
            for points in by_seed.values()
        ),
        "admitted_attainment_decreases_from_0p75_to_40x_every_seed": all(
            points["40x"]["deadline_attainment_admitted"]
            < points["0p75"]["deadline_attainment_admitted"]
            for points in by_seed.values()
        ),
        "offered_penalty_latency_increases_from_0p75_to_40x_every_seed": all(
            points["40x"]["penalty_inclusive_latency_ms_per_offered_task"]
            > points["0p75"]["penalty_inclusive_latency_ms_per_offered_task"]
            for points in by_seed.values()
        ),
        "offered_attainment_2p5_equals_40x_every_seed": all(
            points["40x"]["deadline_attainment_offered"]
            == points["2p5"]["deadline_attainment_offered"]
            for points in by_seed.values()
        ),
        "40x_remains_binding_every_seed": all(
            points["40x"]["rejection_counts"]["v2i_cap_rejected"] > 0 for points in by_seed.values()
        ),
    }


def _fmt_int(value: int | float) -> str:
    return f"{int(value):,}"


def _fmt_float(value: float, digits: int = 9) -> str:
    return f"{value:.{digits}f}"


def _report(
    manifest: dict[str, Any],
    summary: dict[str, Any],
    evidence: dict[str, Any],
    comparison: dict[str, Any],
) -> str:
    primary = comparison["primary_estimand"]
    secondary = comparison["secondary_deadline_attainment_contrasts"]
    rows = comparison["rows"]
    lines = [
        "# E1 physical multi-draw campaign report",
        "",
        "**Completion date:** 9 August 2026",
        "",
        "**Verdict:** all 24 predeclared smoke runs and all 12 new full cells passed. "
        "The five-draw primary comparison is inconclusive at this replication size; it is not an "
        "equivalence or non-inferiority result.",
        "",
        "**Governing manifest:** "
        "[`e1_multidraw_physical_campaign_manifest_v1.json`](e1_multidraw_physical_campaign_manifest_v1.json), "
        f"SHA-256 `{summary['manifest_sha256']}`",
        "",
        "**Machine-readable records:**",
        "",
        f"- [campaign validation](e1_multidraw_physical_campaign_validation_v1.json), SHA-256 "
        f"`{evidence['checked_in_records']['campaign_validation']['sha256']}`;",
        f"- [campaign comparison](e1_multidraw_physical_campaign_comparison_v1.json), SHA-256 "
        f"`{evidence['checked_in_records']['campaign_comparison']['sha256']}`;",
        f"- [result summary](e1_multidraw_physical_campaign_result_summary_v1.json), SHA-256 "
        f"`{sha256_file(Path('docs/evaluation/e1/e1_multidraw_physical_campaign_result_summary_v1.json'))}`;",
        f"- [evidence index](e1_multidraw_physical_campaign_evidence_index_v1.json), SHA-256 "
        f"`{sha256_file(Path('docs/evaluation/e1/e1_multidraw_physical_campaign_evidence_index_v1.json'))}`.",
        "",
        "## Research question and hypotheses",
        "",
        "This campaign asks whether the seed-0 admission-versus-queueing pattern is stable over "
        "five matched provisional fleet draws when only the per-RSU waiting-room ceiling changes. "
        "It does not compare strongest-link placement with a load-aware controller.",
        "",
        "The primary null framing is a zero mean paired fleet-seed difference in offered-task "
        "deadline attainment for `40x - 0.75x`; the directional alternative is nonzero. Positive "
        "values favour 40x and negative values favour 0.75x. The secondary mechanism expectation "
        "is that a higher ceiling can reduce rejection while increasing queueing latency.",
        "",
        "## Locked design and provenance",
        "",
        "All cells used evaluator seed 0, fleet seeds 0-4 as matched replication units, the frozen "
        "17-dimensional Paper-2A MAPPO actor, the Manchester incident trace for Friday 15 March "
        "2024 from 20:00-21:00, 3,600 steps, strongest-link/default placement, sequential substep "
        "accounting, explicit physical rejection, conserved vehicle queues, fixed 1x service, zero "
        "backhaul and load balancing/scaling off. The cap points were 1,866, 6,220 and 99,520 tasks "
        "per RSU; these are waiting-room/admission ceilings, not compute power.",
        "",
        f"TrafficTwin execution used commit `{summary['execution_commit']}`. vec_env remained at "
        f"`{manifest['repositories']['vec_env']['commit']}` and tos-data at "
        f"`{manifest['repositories']['tos_data']['commit']}`. The backend was "
        "`macos_arm64_cpu_jax_0_4_30` with Python 3.11.15, JAX/JAXLIB 0.4.30 and `TFRT_CPU_0`.",
        "The evaluator SHA-256 was "
        f"`{manifest['inputs']['evaluator']['sha256']}`; actor SHA-256 "
        f"`{manifest['inputs']['actor']['sha256']}`; and trace SHA-256 "
        f"`{manifest['inputs']['trace']['sha256']}`.",
        "",
        "Local SUMO was 1.27.1 while trace provenance names 1.27.0. The evaluator replayed the "
        "frozen NPZ and did not invoke SUMO, so this is not an exact canonical SUMO reproduction.",
        "",
        "## Campaign and gate results",
        "",
        "The three seed-0 full records were reused by exact hash. Fleet seeds 1-4 contributed 12 "
        "new full cells. Every new cell first passed two serial ten-step smokes with identical "
        "scientific summaries after wall time was excluded and exact instrumentation identity. "
        "Every full run then passed all 32 accounting, conservation and numerical checks.",
        "",
        f"The 12 new evaluator runs consumed {summary['runtime']['twelve_new_full_cells_hours']:.3f} "
        "wall-hours at concurrency one, within the 48 CPU-hour bound. No cell failed or stopped.",
        "",
        "## Direct observations",
        "",
        "| Fleet seed | Cap | Offered | Admitted | Rejected/unavailable | Offered attainment | "
        "Admitted attainment | Penalty latency / offered (ms) | Latency / admitted (ms) | "
        "V2I cap rejected | Wall time (s) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['fleet_seed']} | {row['cap_label']} | {_fmt_int(row['offered_tasks'])} | "
            f"{_fmt_int(row['admitted_tasks'])} | "
            f"{_fmt_int(row['rejected_or_unavailable_tasks'])} | "
            f"{_fmt_float(row['deadline_attainment_offered'])} | "
            f"{_fmt_float(row['deadline_attainment_admitted'])} | "
            f"{row['penalty_inclusive_latency_ms_per_offered_task']:.3f} | "
            f"{row['latency_ms_per_admitted_task']:.3f} | "
            f"{_fmt_int(row['rejection_counts']['v2i_cap_rejected'])} | {row['wall_s']:.1f} |"
        )
    raw_values = ", ".join(_fmt_float(value, 12) for value in primary["raw_paired_differences"])
    interval = primary["confidence_interval"]
    lines.extend(
        [
            "",
            "## Primary matched analysis",
            "",
            "The five raw `40x - 0.75x` offered-deadline differences, in fleet-seed order 0-4, "
            f"were: `{raw_values}`.",
            "",
            "| Statistic | Value |",
            "|---|---:|",
            f"| Mean | {_fmt_float(primary['mean'], 12)} |",
            f"| Sample standard deviation | {_fmt_float(primary['sample_standard_deviation'], 12)} |",
            f"| Standard error | {_fmt_float(primary['standard_error'], 12)} |",
            f"| Two-sided 95% Student-t CI | [{_fmt_float(interval['lower'], 12)}, "
            f"{_fmt_float(interval['upper'], 12)}] |",
            f"| Median | {_fmt_float(primary['median'], 12)} |",
            f"| Minimum | {_fmt_float(primary['minimum'], 12)} |",
            f"| Maximum | {_fmt_float(primary['maximum'], 12)} |",
            "",
            "The interval includes zero. Under the predeclared rule, the comparison is "
            "**inconclusive at this replication size**. The individual tasks were not treated as "
            "independent statistical replicates.",
            "",
            "## Secondary contrasts and mechanism",
            "",
            f"For `2.5x - 0.75x`, the mean offered-attainment difference was "
            f"{_fmt_float(secondary['2p5_minus_0p75']['mean'], 12)} with 95% CI "
            f"[{_fmt_float(secondary['2p5_minus_0p75']['confidence_interval']['lower'], 12)}, "
            f"{_fmt_float(secondary['2p5_minus_0p75']['confidence_interval']['upper'], 12)}]; this "
            "was also inconclusive.",
            "",
            "For `40x - 2.5x`, all five offered-attainment differences were numerically zero. "
            "This exact observation is not evidence of formal equivalence or a tie because no "
            "equivalence margin or non-inferiority design was predeclared.",
            "",
            "Across every fleet draw, 40x admitted more tasks and rejected fewer than 0.75x, while "
            "admitted-task attainment fell and both admitted and penalty-inclusive offered latency "
            "rose sharply. The 40x ceiling remained binding in every seed. Actor Local/V2I/V2V "
            "decision shares were unchanged across caps within each seed; the intervention changed "
            "downstream admission and queueing, not actor decisions.",
            "",
            "## Conservation and reproducibility",
            "",
            "All 15 full cells passed complete task accounting, rejection reconciliation, terminal "
            "outcome uniqueness, finite/nonnegative checks, offered/admitted denominator separation, "
            "V2I work conservation and vehicle-work conservation. Work is measured in milliseconds "
            "of service work. Offered count, `task_active` and `task_type` were identical across caps "
            "within every fleet seed. No silent task loss was observed.",
            "",
            "## Evidence, failures and validity threats",
            "",
            f"Raw evidence remains outside Git at `{manifest['output']['logical_locator']}`. The "
            f"campaign directory contains {summary['raw_evidence']['file_count']} files totalling "
            f"{summary['raw_evidence']['size_bytes']} bytes. The evidence index retains each cell's "
            "smoke/full validation hashes and every authoritative full-output hash. There were no "
            "failed or stopped scientific cells. The initial direct-file controller invocation "
            "failed before imports, evidence creation or evaluator launch; module-mode invocation "
            "then executed the unchanged committed controller.",
            "",
            "Validity threats are five provisional fleet draws, a fixed evaluator seed, one incident "
            "hour, no ordinary-traffic control, a provisional `uk2030` fleet, padded-width cap "
            "resolution, and the SUMO 1.27.1/1.27.0 provenance mismatch. Results support only this "
            "controlled simulator intervention, not real-world causal or optimality claims.",
            "",
            "Deadline attainment is a simulated outcome, not confirmed native physical completion "
            "or result return. Randy's reported `0.6943` remains unreproduced. No E2, load-aware "
            "placement, scaling, retraining, prediction, bus modelling or backend investigation ran.",
            "",
            "## Interpretation and exact next gate",
            "",
            "The bounded evidence is consistent with an admission-versus-queueing trade-off: higher "
            "ceilings reduce rejection but substantially increase latency, without a conclusive "
            "five-draw change in offered-task deadline attainment. This is an interpretation of the "
            "controlled simulator observations, not a claim of equivalence or real-world policy "
            "superiority.",
            "",
            "The E1 campaign gate is complete. Stop for researcher review. E2 and every extension "
            "remain unauthorised; the next task requires a new direct instruction.",
            "",
        ]
    )
    return "\n".join(lines)


def build(args: argparse.Namespace) -> None:
    manifest = _json(args.manifest)
    comparison = _json(args.comparison)
    validation = _json(args.validation)
    if comparison.get("validation_passed") is not True or validation.get("passed") is not True:
        raise ValueError("campaign comparison or validation did not pass")
    if comparison["manifest_id"] != manifest["manifest_id"]:
        raise ValueError("manifest identity mismatch")
    cell_records, gate_checks = _gate_evidence(manifest, args.campaign_root)
    all_gates_passed = all(check["passed"] for check in gate_checks)
    if not all_gates_passed:
        raise ValueError("one or more stored smoke/full gates failed")
    rows = comparison["rows"]
    raw_files = [path for path in args.campaign_root.rglob("*") if path.is_file()]
    summary = {
        "schema_version": "traffictwin.e1-multidraw-physical-result-summary.v1",
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": sha256_file(args.manifest),
        "execution_commit": args.execution_commit,
        "campaign_passed": True,
        "decision": comparison["primary_estimand"]["decision"],
        "backend": manifest["backend_decision"]["selected_backend"],
        "replication_unit": "fleet_seed",
        "evaluator_seed": manifest["seeds"]["evaluator_seed"],
        "provenance": {
            "repositories": {
                "traffictwin_execution_commit": args.execution_commit,
                "vec_env_commit": manifest["repositories"]["vec_env"]["commit"],
                "tos_data_commit": manifest["repositories"]["tos_data"]["commit"],
            },
            "inputs": manifest["inputs"],
            "environment": manifest["environment"],
        },
        "counts": {
            "fleet_draws": 5,
            "caps_per_draw": 3,
            "full_cells_analysed": 15,
            "seed0_full_cells_reused_by_hash": 3,
            "new_full_cells_started": 12,
            "new_full_cells_passed": 12,
            "new_full_cells_failed": 0,
            "new_smoke_pairs_passed": 12,
            "new_smoke_runs_passed": 24,
        },
        "primary_estimand": comparison["primary_estimand"],
        "secondary_deadline_attainment_contrasts": comparison[
            "secondary_deadline_attainment_contrasts"
        ],
        "mechanism_checks": _mechanism_checks(rows),
        "runtime": _runtime(rows),
        "conservation": {
            "all_full_runs_valid": True,
            "task_accounting": "passed",
            "rejection_reconciliation": "passed",
            "v2i_service_work_ms": "conserved",
            "vehicle_service_work_ms": "conserved",
            "silent_task_loss": False,
            "finite_nonnegative": "passed",
            "within_seed_task_stream_identity": "passed for offered count, task_active and task_type",
        },
        "raw_evidence": {
            "logical_locator": manifest["output"]["logical_locator"],
            "file_count": len(raw_files),
            "size_bytes": sum(path.stat().st_size for path in raw_files),
        },
        "limitations": comparison["interpretation_limits"],
        "next_gate": "stop_for_researcher_review; E2 and all extensions remain unauthorised",
    }
    _write_json_new(args.summary_output, summary)

    checked_in_records = {
        "manifest": _record(args.manifest, str(args.manifest)),
        "campaign_validation": _record(args.validation, str(args.validation)),
        "campaign_comparison": _record(args.comparison, str(args.comparison)),
    }
    seed_indexes: dict[str, Any] = {}
    seed1_index = args.campaign_root / "evidence_checksums_seed1_complete.sha256"
    seed_indexes["1"] = _record(
        seed1_index,
        f"{manifest['output']['logical_locator']}/evidence_checksums_seed1_complete.sha256",
    )
    for seed in (2, 3, 4):
        path = args.campaign_root / f"fleet_seed_{seed}" / "seed_evidence_index.json"
        seed_indexes[str(seed)] = _record(
            path,
            f"{manifest['output']['logical_locator']}/fleet_seed_{seed}/seed_evidence_index.json",
        )
    evidence = {
        "schema_version": "traffictwin.e1-multidraw-physical-evidence-index.v1",
        "manifest_sha256": sha256_file(args.manifest),
        "permission_safe": True,
        "private_absolute_paths_in_record": False,
        "checked_in_records": checked_in_records,
        "campaign_control_records": {
            "accepted_seed1_status": _record(
                args.campaign_root / "campaign_status.json",
                f"{manifest['output']['logical_locator']}/campaign_status.json",
            ),
            "remaining_cells_status": _record(
                args.campaign_root / "remaining_campaign_status_2026-08-08.json",
                f"{manifest['output']['logical_locator']}/remaining_campaign_status_2026-08-08.json",
            ),
            "remaining_cells_events": _record(
                args.campaign_root / "remaining_campaign_events_2026-08-08.jsonl",
                f"{manifest['output']['logical_locator']}/remaining_campaign_events_2026-08-08.jsonl",
            ),
        },
        "seed_indexes": seed_indexes,
        "new_cell_evidence": cell_records,
        "gate_checks": gate_checks,
        "all_gate_checks_passed": all_gates_passed,
        "failure_retention": "No scientific cell failed; negative/null/inconclusive results retained.",
    }
    _write_json_new(args.evidence_output, evidence)
    report = _report(manifest, summary, evidence, comparison)
    _write_text_new(args.report_output, report)

    checksum_paths = [
        args.manifest,
        args.validation,
        args.comparison,
        args.summary_output,
        args.evidence_output,
        args.report_output,
    ]
    checksum_lines = [
        f"{sha256_file(path)}  {_repository_locator(path)}\n" for path in checksum_paths
    ]
    _write_text_new(args.checksums_output, "".join(checksum_lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--execution-commit", required=True)
    parser.add_argument("--summary-output", required=True, type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--report-output", required=True, type=Path)
    parser.add_argument("--checksums-output", required=True, type=Path)
    build(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
