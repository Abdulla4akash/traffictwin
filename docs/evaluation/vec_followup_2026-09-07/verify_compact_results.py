"""Recheck archived compact results without launching simulations or writing files."""

import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

from scipy.stats import t

ROOT = Path(__file__).resolve().parent


def rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read(path):
    return json.loads(path.read_text())


def close(actual, expected):
    if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-10):
        raise ValueError(f"Mismatch: {actual} versus {expected}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    campaign = ROOT / "generalisation-replication-2026-09-07"
    manifest = read(campaign / "manifest.json")
    require(manifest["primary_fleet_seeds"] == [0, 2, 3, 4], "Primary seed set")
    require(manifest["excluded_pilot_seed"] == 1, "Pilot exclusion")
    run_rows = rows(campaign / "runs.csv")
    require(len(run_rows) == 12, "Full run count")
    measurements, identities = {}, {}
    for row in run_rows:
        seed, arm = int(row["fleet_seed"]), row["arm"]
        directory = campaign / "cells" / f"seed_{seed}_{arm}" / "attempt_001"
        summary = read(directory / "summary.json")
        receipt = read(directory / "validation.json")
        require(receipt["status"] == "passed", "Full validation failed")
        require(read(directory / "workload_validation.json")["status"] == "passed", "Work validation failed")
        require(summary["T"] == 10800 and summary["rsu_max_concurrent"] == 6220, "Controls changed")
        require(summary["fleet_seed"] == seed, "Fleet seed changed")
        close(row["offered"], summary["n_offered"])
        close(row["admitted"], summary["n_admitted"])
        close(row["attainment_pct"], 100 * summary["completion"])
        close(int(row["deadline_met"]) / int(row["offered"]), summary["completion"])
        close(row["gate_rejected"], summary["v2i_gate_rejected"])
        rejected = sum(int(row[key]) for key in (
            "gate_rejected", "cap_rejected", "local_mqd_rejected", "v2v_mqd_rejected",
            "v2i_unavailable", "v2v_unavailable"))
        require(int(row["offered"]) == int(row["admitted"]) + rejected, "Task conservation")
        require(hashlib.sha256((directory / "validation.json").read_bytes()).hexdigest()
                == row["validation_sha256"], "Run receipt binding")
        require(identities.setdefault(seed, receipt["input_identity"]) == receipt["input_identity"],
                "Paired input identity")
        measurements[(seed, arm)] = float(row["attainment_pct"])
    require(len(measurements) == 12, "Duplicate run")
    for directory in (campaign / "preflight").glob("*/attempt_001"):
        require(read(directory / "validation.json")["status"] == "passed", "Probe failed")
    probes = list((campaign / "preflight").glob("*/attempt_001/validation.json"))
    require(len(probes) == 12, "Probe count")
    reversal = sum(measurements[(seed, "common_target")] < measurements[(seed, "ingress")]
                   < measurements[(seed, "per_task")] for seed in manifest["primary_fleet_seeds"])
    for row in rows(campaign / "arm_summary.csv"):
        values = [measurements[(seed, row["arm"])] for seed in manifest["primary_fleet_seeds"]]
        close(row["mean_attainment_pct"], statistics.mean(values))
        close(row["sd_attainment_pct"], statistics.stdev(values))
    contrasts = []
    for row in rows(campaign / "paired_intervals.csv"):
        left, right = row["contrast"].split("_minus_")
        values = [measurements[(seed, left)] - measurements[(seed, right)]
                  for seed in manifest["primary_fleet_seeds"]]
        mean, sd = statistics.mean(values), statistics.stdev(values)
        close(row["mean_pp"], mean)
        close(row["sd_pp"], sd)
        close(row["min_pp"], min(values))
        close(row["max_pp"], max(values))
        for prefix, alpha in (("ci95", .05), ("family95", .05 / 3)):
            margin = t.ppf(1 - alpha / 2, 3) * sd / math.sqrt(4)
            close(row[prefix + "_low_pp"], mean - margin)
            close(row[prefix + "_high_pp"], mean + margin)
        contrasts.append({"contrast": row["contrast"], "mean_pp": mean})
    supplementary = rows(campaign / "supplementary_five_draws.csv")
    require(len(supplementary) == 5, "Supplementary count")
    pilot = ROOT / "generalisation-pilot-2026-09-07"
    for row in supplementary:
        seed = int(row["fleet_seed"])
        for arm, folder in (("ingress", "02_ingress"), ("per_task", "01_fresh")):
            expected = (100 * read(pilot / "cells" / folder / "attempt_001/summary.json")["completion"]
                        if seed == 1 else measurements[(seed, arm)])
            close(row[arm + "_pct"], expected)
        close(row["difference_pp"], float(row["per_task_pct"]) - float(row["ingress_pct"]))
        if seed == 1:
            require(row["role"] == "already inspected exploratory pilot", "Pilot label")
    delay = ROOT / "state-delay-pilot-2026-09-07"
    names = ("01_fresh", "02_delay_100", "03_delay_500", "04_delay_1000", "05_ingress")
    for row, name in zip(rows(delay / "comparison.csv"), names, strict=True):
        close(row["deadline_attainment"], read(delay / "cells" / name / "attempt_001/summary.json")["completion"])
    audit = read(delay / "mechanism_audit.json")
    require(audit["rows"][1]["report_matches_live_fraction"] == 1, "100 ms report identity")
    forward = ROOT / "forwarding-sensitivity-2026-09-07"
    for row, recorded in zip(rows(forward / "forwarding_sensitivity.csv"),
                             read(forward / "analysis_validation.json")["rows"], strict=True):
        for key, value in row.items():
            close(value, recorded[key])
    return {"status": "passed", "full_runs": 12, "preflight_probes": 12,
            "historical_reversal_draws": reversal, "contrasts": contrasts,
            "pilot_kept_separate": True, "state_delay_rows": 5, "forwarding_rows": 5,
            "scope": "Compact arithmetic, saved controls and receipts; no new raw-array reanalysis or simulations"}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
