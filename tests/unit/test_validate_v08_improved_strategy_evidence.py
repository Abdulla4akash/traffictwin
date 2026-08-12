"""Tests for v08 lane 07 improved strategy evidence validator — discriminating validation."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs/closure/v08_alignment/improved_strategy_results.json"
FIGURE_CSV = ROOT / "docs/closure/v08_alignment/improved_strategy_figure_data.csv"
VALIDATOR = ROOT / "scripts/validate_v08_improved_strategy_evidence.py"


def run_validator() -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
    )


def test_validator_passes_on_clean_tree() -> None:
    result = run_validator()
    assert result.returncode == 0, (
        f"validator should pass: stdout={result.stdout} stderr={result.stderr}"
    )
    assert "VALIDATION PASSED" in result.stdout


def test_validator_rejects_orphan_number_and_task_replication() -> None:
    # Discriminating mutation: remove seed/manifest binding from one numeric row
    # and relabel tasks as independent replicates.
    original_results = RESULTS.read_text()
    original_csv = FIGURE_CSV.read_text()
    try:
        data = json.loads(original_results)
        # Remove manifest_sha256 and actor binding from first row, set replication_unit to task
        row = data["rows"][0]
        row.pop("manifest_sha256", None)
        row.pop("actor_sha256", None)
        row["replication_unit"] = "task"
        # Also corrupt top-level replication_unit to task to ensure double failure
        data["replication_unit"] = "task"
        RESULTS.write_text(json.dumps(data, indent=2))

        # Mutate CSV: remove manifest binding and relabel replication to task
        lines = original_csv.splitlines()
        header = lines[0]
        # Find first data line and replace replication_unit column
        # replication_unit is column index 12 (0-based)
        mutated_lines = [header]
        for idx, line in enumerate(lines[1:]):
            if idx == 0:
                # parse csv to mutate correctly
                import io

                reader = csv.DictReader(io.StringIO(header + "\n" + line))
                row_csv = next(reader)
                row_csv["manifest_sha256"] = ""
                row_csv["replication_unit"] = "task"
                # reconstruct
                writer_io = io.StringIO()
                writer = csv.DictWriter(writer_io, fieldnames=header.split(","))
                writer.writerow(row_csv)
                mutated_line = writer_io.getvalue().strip().splitlines()[-1]
                mutated_lines.append(mutated_line)
            else:
                mutated_lines.append(line)
        FIGURE_CSV.write_text("\n".join(mutated_lines) + "\n")

        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail after mutation, got pass: {result.stdout}"
        )
        stderr = result.stderr + result.stdout
        # Must mention at least one of the mutated failure reasons
        assert (
            "manifest_sha256" in stderr or "actor_sha256" in stderr or "replication_unit" in stderr
        ), f"mutation failure should mention binding or replication: {stderr}"

    finally:
        RESULTS.write_text(original_results)
        FIGURE_CSV.write_text(original_csv)
        # Confirm restore passes
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"


def test_every_figure_cell_has_evidence_identity() -> None:
    index = json.loads(
        (ROOT / "docs/closure/v08_alignment/improved_strategy_evidence_index.json").read_text()
    )
    figure_csv_ids = set()
    with FIGURE_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            figure_csv_ids.add(row["evidence_id"])
    evidence_ids = set(index["evidence_identities"].keys())
    # every csv evidence_id must be in index
    missing = figure_csv_ids - evidence_ids
    assert not missing, f"csv evidence_ids missing from index: {missing}"
    # every row in results must also be in index
    results = json.loads(RESULTS.read_text())
    for row in results["rows"]:
        assert row["evidence_id"] in evidence_ids
        assert "manifest_sha256" in row and row["manifest_sha256"]
        assert "actor_sha256" in row and row["actor_sha256"]
        assert "trace_sha256" in row and row["trace_sha256"]


def test_replication_unit_not_task() -> None:
    results = json.loads(RESULTS.read_text())
    assert results["replication_unit"] == "fleet_draw"
    for row in results["rows"]:
        assert row["replication_unit"] in {"fleet_draw", "fleet_seed", "run"}
        assert "task" not in row["replication_unit"].lower()
    with FIGURE_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            assert row["replication_unit"] in {"fleet_draw", "fleet_seed", "run"}
