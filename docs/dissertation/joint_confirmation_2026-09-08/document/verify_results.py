"""Relocatable compact-result verification, optionally checking supplied raw files.

No evaluator, JAX import, simulation or task-level reanalysis. Requires SciPy for
the predeclared critical value. This independently recalculates compact tables;
the sealed primary analysis remains confirmation/analyse.py.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import statistics
from scipy.stats import t

PACKAGE = Path(__file__).resolve().parent.parent
ARMS = ("ingress_dla", "dla", "per_task_dla", "causal_round_robin")
CONTRASTS = (("per_task_dla", "ingress_dla"), ("dla", "ingress_dla"),
             ("per_task_dla", "causal_round_robin"))


def load(path):
    if not path.is_file():
        raise ValueError(f"Missing required evidence: {path}")
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(package, raw_root=None):
    evidence = package / "evidence"
    seal_path = package / "confirmation/SEALED_EXECUTION.json"
    seal = load(seal_path)
    analysis = load(evidence / "ANALYSIS.json")
    blocks = load(evidence / "BLOCK_CONTROLS.json")
    rows = load(evidence / "CELL_RESULTS.json")
    require(len(blocks) == 8 and len(rows) == 32, "Incomplete matrix")
    index = {(row["block"], row["arm"]): row for row in rows}
    require(len(index) == 32, "Duplicate compact cell")
    require(analysis["seal_sha256"] == sha(seal_path), "Analysis/seal mismatch")
    rates = {}
    for block in seal["blocks"]:
        b = block["block"]
        br = next(x for x in blocks if x["block"] == b)
        require(br["status"] == "passed" and br["seal_sha256"] == sha(seal_path),
                f"Block {b}: unbound or invalid control receipt")
        require(br["shared_exogenous_inputs"] == "identical", f"Block {b}: inputs")
        shared = None
        offers = set()
        for arm in ARMS:
            row = index[b, arm]
            cell = evidence / "cells" / f"block_{b:02d}_{arm}"
            rec_path = cell / "VALIDATED.json"
            rec = load(rec_path)
            require(sha(rec_path) == br["cell_receipt_sha256"][arm],
                    f"Block {b} {arm}: changed cell receipt")
            require(rec["seal_sha256"] == sha(seal_path) and rec["status"] == "passed",
                    f"Block {b} {arm}: seal/status")
            require(row["fleet_seed"] == block["fleet_seed"] and
                    row["evaluator_seed"] == block["evaluator_seed"],
                    f"Block {b} {arm}: exported seeds")
            cfg = rec["configuration"]
            require(cfg["block"] == b and cfg["arm"] == arm and
                    cfg["fleet_seed"] == block["fleet_seed"] and
                    cfg["evaluator_seed"] == block["evaluator_seed"] and
                    cfg["steps"] == 10800, f"Block {b} {arm}: configuration")
            require(sha(cell / "summary.json") == rec["output_sha256"]["summary.json"],
                    f"Block {b} {arm}: changed summary")
            for key in ("offered", "admitted", "successes", "terminal_failures"):
                require(row[key] == rec[key] and isinstance(row[key], int),
                        f"Block {b} {arm}: {key}")
            oc = rec["outcome_counts"]
            require(rec["offered"] == rec["admitted"] + rec["terminal_failures"]
                    and rec["successes"] == oc[1]
                    and rec["admitted"] == oc[1] + oc[2]
                    and rec["terminal_failures"] == sum(oc[3:]),
                    f"Block {b} {arm}: compact category accounting")
            require(row["admitted_misses"] == oc[2] and row["gate_rejected"] == oc[3],
                    f"Block {b} {arm}: derived categories")
            if shared is None:
                shared = rec["shared_input_hashes"]
            require(shared == rec["shared_input_hashes"], f"Block {b}: shared hashes")
            offers.add(rec["offered"])
            rates[b, arm] = 100 * rec["successes"] / rec["offered"]
            require(rates[b, arm] == row["attainment_pct"], f"Block {b}: rate")
        require(len(offers) == 1, f"Block {b}: offered denominator")
    critical = float(t.ppf(1 - .05 / 6, 7))
    regenerated = []
    for treated, control in CONTRASTS:
        effects = [rates[b, treated] - rates[b, control] for b in range(8)]
        mean = statistics.mean(effects)
        sd = statistics.stdev(effects)
        half = critical * sd / math.sqrt(8)
        values = dict(contrast=f"{treated} minus {control}", effects_pp=effects,
                      mean_pp=mean, sd_pp=sd, family95_low_pp=mean-half,
                      family95_high_pp=mean+half)
        archived = next(x for x in analysis["primary"] if x["contrast"] == values["contrast"])
        require(archived["effects_pp"] == effects, f"{treated}/{control}: paired effects")
        for key in ("mean_pp", "sd_pp", "family95_low_pp", "family95_high_pp"):
            require(math.isclose(values[key], archived[key], rel_tol=0, abs_tol=1e-12),
                    f"{treated}/{control}: {key}")
        regenerated.append(values)
    with (evidence / "CELL_RESULTS.csv").open(newline="") as f:
        exported = list(csv.DictReader(f))
    require(exported == [{k: str(v) for k, v in row.items()} for row in rows],
            "CELL_RESULTS.csv differs from JSON")
    expected_effects = []
    for values in regenerated:
        for b, effect in enumerate(values["effects_pp"]):
            expected_effects.append(dict(block=str(b), fleet_seed=str(100+b),
                                         evaluator_seed=str(200+b),
                                         contrast=values["contrast"], effect_pp=str(effect)))
    with (evidence / "PAIRED_EFFECTS.csv").open(newline="") as f:
        require(list(csv.DictReader(f)) == expected_effects,
                "PAIRED_EFFECTS.csv differs from regenerated effects")
    raw = dict(status="not_checked", reason="Optional private raw-data root not supplied; compact arithmetic does not repeat task-level validation")
    if raw_root is not None:
        inventory = load(evidence / "RAW_INVENTORY.json")
        for item in inventory["files"]:
            path = raw_root / item["path"]
            require(path.is_file(), f"Missing raw record: {path}")
            require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                    f"Raw integrity mismatch: {path}")
        raw = dict(status="integrity_checked", files=len(inventory["files"]),
                   task_level_reanalysis=False)
    return dict(status="passed", cells=32, blocks=8, critical_value=critical,
                primary=regenerated, raw=raw,
                comparison_tolerance_pp=1e-12,
                tolerance_scope="Independent compact arithmetic only; scientific validation tolerances remain sealed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package", type=Path, default=PACKAGE)
    ap.add_argument("--raw-root", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = verify(args.package, args.raw_root)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
