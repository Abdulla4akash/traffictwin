"""Regenerate figures and metadata from preserved compact sources; never run VEC."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
BASE = "1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name: str, value: object) -> None:
    (HERE / "evidence" / name).write_text(json.dumps(value, indent=2) + "\n")


def main() -> None:
    source = ROOT / "docs/dissertation/joint_confirmation_2026-09-08/evidence/CELL_RESULTS.csv"
    with source.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 32
    blocks = sorted({int(row["block"]) for row in rows})
    assert len(blocks) == 8
    policies = [
        ("dla", "Common-target", "v"),
        ("ingress_dla", "Ingress", "s"),
        ("causal_round_robin", "Round-robin", "D"),
        ("per_task_dla", "Per-task", "o"),
    ]
    rates = {}
    labels = []
    for block in blocks:
        group = [r for r in rows if int(r["block"]) == block]
        assert len(group) == 4 and len({r["offered"] for r in group}) == 1
        labels.append(f"{group[0]['fleet_seed']}/{group[0]['evaluator_seed']}")
    fig, ax = plt.subplots(figsize=(9.2, 4.9), layout="constrained")
    for arm, label, marker in policies:
        chosen = [next(r for r in rows if int(r["block"]) == b and r["arm"] == arm) for b in blocks]
        values = np.array([100 * int(r["successes"]) / int(r["offered"]) for r in chosen])
        rates[arm] = values
        ax.plot(range(8), values, marker=marker, linewidth=1.7, markersize=6, label=label)
    ax.set_xticks(range(8), labels, fontsize=10)
    ax.set_xlabel("Matched block (fleet seed / evaluator seed)")
    ax.set_ylabel("Offered-task deadline attainment (%)")
    ax.set_title("Joint-randomness confirmation: all 32 cells")
    ax.set_ylim(82, 95)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncols=2, loc="lower right", frameon=False)
    for ext in ("pdf", "png"):
        fig.savefig(HERE / "assets" / f"joint_confirmation_eight_blocks.{ext}", dpi=180)
    plt.close(fig)
    total = float(np.mean(rates["per_task_dla"] - rates["ingress_dla"]))
    spreading = float(np.mean(rates["causal_round_robin"] - rates["ingress_dla"]))
    extra = float(np.mean(rates["per_task_dla"] - rates["causal_round_robin"]))
    assert abs(total - spreading - extra) < 1e-12
    write_json(
        "DESCRIPTIVE_SPLIT.json",
        {
            "source": str(source.relative_to(ROOT)),
            "source_sha256": digest(source),
            "replication_unit": "paired block",
            "blocks": 8,
            "weighting": "equal block",
            "mean_attainment_pct": {k: float(v.mean()) for k, v in rates.items()},
            "per_task_minus_ingress_pp": total,
            "round_robin_minus_ingress_pp": spreading,
            "per_task_minus_round_robin_pp": extra,
            "spreading_step_share_pct": 100 * spreading / total,
            "additional_step_share_pct": 100 * extra / total,
            "interpretation": (
                "Post-hoc additive description of mean contrasts; not causal "
                "shares or a new declared interval."
            ),
        },
    )
    layout_source = ROOT / (
        "docs/evaluation/vec_followup_2026-09-07/generalisation-replicati"
        "on-2026-09-07/input_validation.json"
    )
    layout = json.loads(layout_source.read_text())

    def find_positions(obj: object) -> list[list[float]] | None:
        if isinstance(obj, dict):
            for v in obj.values():
                if (
                    isinstance(v, list)
                    and len(v) == 9
                    and all(isinstance(x, list) and len(x) == 2 for x in v)
                ):
                    return v
                got = find_positions(v)
                if got is not None:
                    return got
        if isinstance(obj, list):
            for v in obj:
                got = find_positions(v)
                if got is not None:
                    return got
        return None

    positions = find_positions(layout)
    assert positions is not None, "No authenticated 9-RSU coordinate array"
    xy = np.array(positions, dtype=float)
    fig, ax = plt.subplots(figsize=(8.7, 4.7), layout="constrained")
    ax.scatter(xy[:, 0], xy[:, 1], s=70, marker="s")
    for index, (x, y) in enumerate(xy):
        ax.annotate(f"RSU {index}", (x, y), xytext=(7, 5), textcoords="offset points", fontsize=10)
    ax.set_xlabel("Local trace x coordinate (m)")
    ax.set_ylabel("Local trace y coordinate (m)")
    ax.set_title("Morning simulation: authenticated RSU coordinates")
    ax.set_xlim(-150, 2300)
    ax.set_ylim(-100, 1600)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.2)
    for ext in ("pdf", "png"):
        fig.savefig(HERE / "assets" / f"morning_rsu_layout.{ext}", dpi=180)
    plt.close(fig)
    write_json(
        "RSU_LAYOUT.json",
        {
            "source": str(layout_source.relative_to(ROOT)),
            "sha256": digest(layout_source),
            "coordinates": positions,
            "crs": "Local SUMO trace metres; geographic projection not authenticated",
            "incident_positions": "Not available in the inspected compact source; not fabricated",
        },
    )
    inventories = {}
    for name, base in (("product", ROOT / "src/traffictwin"), ("tests", ROOT / "tests")):
        files = sorted(base.rglob("*.py"))
        items = []
        for file in files:
            text = file.read_text()
            tree = ast.parse(text)
            items.append(
                {
                    "path": str(file.relative_to(ROOT)),
                    "lines": len(text.splitlines()),
                    "sha256": digest(file),
                    "test_definitions": sum(
                        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and n.name.startswith("test_")
                        for n in ast.walk(tree)
                    ),
                }
            )
        inventories[name] = {
            "files": len(files),
            "physical_lines": sum(x["lines"] for x in items),
            "test_definitions": sum(x["test_definitions"] for x in items),
            "inventory": items,
        }
    write_json(
        "ARTEFACT_INVENTORY.json",
        {
            "base_commit": BASE,
            "method": (
                "All Python files under the named roots; physical lines include "
                "blanks/comments; AST test definitions are not passing-test "
                "counts."
            ),
            "components": inventories,
        },
    )
    capture = HERE / "assets/traffictwin_streamlit.png"
    write_json(
        "CAPTURE.json",
        {
            "source_commit": BASE,
            "github_workflow_run": 34614459294,
            "artifact_id": 10269522813,
            "file_sha256": digest(capture),
            "route": "home",
            "browser": "Chromium / Playwright",
            "viewport": [1440, 1000],
            "theme": "light",
            "capture_type": "Actual default Streamlit interface; no research launch",
            "receipt": "evidence/product_capture/ui/accessibility-audit.json",
        },
    )
    inkscape = shutil.which("inkscape")
    if inkscape is None:
        raise RuntimeError("Inkscape is required to convert the five preserved SVGs")
    for svg in sorted((HERE / "assets").glob("*.svg")):
        subprocess.run(  # noqa: S603 -- fixed executable and repository-owned asset paths
            [
                inkscape,
                str(svg),
                "--export-type=pdf",
                f"--export-filename={svg.with_suffix('.pdf')}",
            ],
            check=True,
            capture_output=True,
        )
    print(
        json.dumps(
            {
                "means": {k: float(v.mean()) for k, v in rates.items()},
                "split": [100 * spreading / total, 100 * extra / total],
            }
        )
    )


if __name__ == "__main__":
    main()
