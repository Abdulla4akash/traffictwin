"""Read-only compact regeneration of manuscript Tables 6, 7, 7a and 7b.

No evaluator/JAX import, raw-array analysis, server, plotting or output-file write.
The existing joint-confirmation verifier binds its compact receipts; the other
rows use archived paired effects with the same declared interval families.
"""

from pathlib import Path
import importlib.util
import hashlib
import json
import subprocess
import sys
import numpy as np
import scipy
from scipy.stats import t

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
SOURCES = {}


def read(path, commit=None):
    if commit:
        raw = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
    else:
        raw = (ROOT / path).read_bytes()
    SOURCES[(commit + ":" if commit else "") + path] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def estimate(effects, family):
    effects = np.asarray(effects, dtype=float)
    mean = float(np.mean(effects))
    half = float(
        t.ppf(1 - 0.05 / (2 * family), len(effects) - 1)
        * np.std(effects, ddof=1)
        / np.sqrt(len(effects))
    )
    return [mean, mean - half, mean + half]


def check(values, expected):
    if not np.allclose(values, expected, rtol=0, atol=1e-12):
        raise ValueError((values, expected))


morning = read(
    "docs/evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/analysis_validation.json"
)
output = {"6": []}
for row in morning["primary_contrasts"]:
    effects = [x[row["contrast"] + "_pp"] for x in morning["primary_paired"]]
    values = estimate(effects, 3)
    check(values, [row["mean_pp"], row["family95_low_pp"], row["family95_high_pp"]])
    individual = estimate(effects, 1)
    check(individual, [row["mean_pp"], row["ci95_low_pp"], row["ci95_high_pp"]])
    output["6"].append(
        dict(contrast=row["contrast"], mean_and_family95=values, individual95=individual[1:])
    )
path = ROOT / "docs/dissertation/joint_confirmation_2026-09-08/document/verify_results.py"
SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location("joint_compact_verifier", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
joint = module.verify(path.parents[1])
output["7"] = joint["primary"]
for table, commit, path, key, family in [
    (
        "7a",
        "fe8c8d9e4f725665508e47e61dc6e3286d005450",
        "docs/dissertation/followups_2026-09-15/ANALYSIS.json",
        "all_ten_family95",
        10,
    ),
    (
        "7b",
        "c95e4f86d6dd83207ed3c810826ca48768af8471",
        "docs/research/three_traces_2026-09-16/ANALYSIS.json",
        "all_fifteen_family95",
        15,
    ),
]:
    data = read(path, commit)
    output[table] = []
    for row in data["contrasts"]:
        values = estimate(row["effects_pp"], family)
        expected = row[key]
        check(values, [expected["mean_pp"], expected["low_pp"], expected["high_pp"]])
        output[table].append(
            dict(
                contrast=row["contrast"],
                condition=row.get("study", row.get("trace")),
                mean_and_family95=values,
            )
        )
print(
    json.dumps(
        {
            "status": "passed",
            "tables": output,
            "source_sha256": SOURCES,
            "runtime": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
            "scope": "Compact paired arithmetic; existing joint receipt checks; no raw-task revalidation or new research. All declared rows retained, including rows not printed in shortened manuscript tables.",
            "research_workloads_launched": 0,
        },
        indent=2,
    )
)
