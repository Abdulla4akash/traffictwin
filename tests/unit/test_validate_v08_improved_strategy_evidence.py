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


def test_validator_rejects_wrong_e2b_artifact_path() -> None:
    """Discriminating: E2b artifact paths are pinned; wrong path must fail."""
    original_results = RESULTS.read_text()
    try:
        data = json.loads(original_results)
        # Corrupt pinned E2b off arm artifact_path to ingress_dla path (the old bug)
        for row in data["rows"]:
            if row.get("figure_id") == "fig1_e2b_offered_attainment_off":
                row["artifact_path"] = (
                    "/Users/akashx/AntigravityTest/e2b_outputs/e2b-placement-admission-factorial-v1/full/ingress_dla/run_1"
                )
                break
        RESULTS.write_text(json.dumps(data, indent=2))
        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail on wrong E2b artifact path, got pass: {result.stdout}"
        )
        stderr = result.stderr + result.stdout
        assert "artifact_path" in stderr, (
            f"wrong artifact_path failure should mention artifact_path: {stderr}"
        )
    finally:
        RESULTS.write_text(original_results)
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"


def test_validator_rejects_json_csv_value_mismatch() -> None:
    """Discriminating: JSON and CSV headline values must match on figure_id join."""
    original_csv = FIGURE_CSV.read_text()
    try:
        lines = original_csv.splitlines()
        header = lines[0]
        cols = header.split(",")
        mutated_lines = [header]
        for line in lines[1:]:
            # parse safely
            import io

            reader = csv.DictReader(io.StringIO(header + "\n" + line))
            row_csv = next(reader)
            if row_csv.get("figure_id") == "fig1_e2b_offered_attainment_off":
                # perturb headline value
                row_csv["value"] = "0.999999999"
            writer_io = io.StringIO()
            writer = csv.DictWriter(writer_io, fieldnames=cols)
            writer.writerow(row_csv)
            mutated_line = writer_io.getvalue().strip().splitlines()[-1]
            mutated_lines.append(mutated_line)
        FIGURE_CSV.write_text("\n".join(mutated_lines) + "\n")
        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail on JSON/CSV value mismatch, got pass: {result.stdout}"
        )
        stderr = result.stderr + result.stdout
        assert "value" in stderr.lower() or "join mismatch" in stderr.lower(), (
            f"value mismatch failure should mention value/join: {stderr}"
        )
    finally:
        FIGURE_CSV.write_text(original_csv)
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"


def test_validator_rejects_s007_broadcast_misattribution() -> None:
    """Discriminating: S-007 must not be credited with broadcast/microsecond wording."""
    summary = ROOT / "docs/closure/v08_alignment/improved_strategy_evidence_summary.md"
    original = summary.read_text()
    try:
        mutated = original.replace(
            "[SOURCE-DERIVED FACT — S-007, Randy Q&A] RSU queue/waiting-room capacity is an administrative control, not compute power.",  # noqa: E501
            "[SOURCE-DERIVED FACT — S-007, Randy Q&A] RSU queue/waiting-room capacity is an administrative control, not compute power; RSU broadcast of load is infeasible because data becomes obsolete within microseconds under concurrent execution.",  # noqa: E501
        )
        summary.write_text(mutated)
        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail on S-007 broadcast misattribution, got pass: {result.stdout}"
        )
        stderr = result.stderr + result.stdout
        assert "S-007" in stderr and (
            "broadcast" in stderr.lower() or "microsecond" in stderr.lower()
        ), f"S-007 misattribution should mention S-007/broadcast: {stderr}"
    finally:
        summary.write_text(original)
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"


def test_validator_rejects_s035_hedged_promoted_to_fact() -> None:
    """Discriminating: hedged S-035 motivation promoted to SOURCE-DERIVED FACT / implementation verification / mandatory deliverable must fail."""  # noqa: E501
    summary = ROOT / "docs/closure/v08_alignment/improved_strategy_evidence_summary.md"
    original = summary.read_text()
    try:
        # Promote hedged provisional wording to SOURCE-DERIVED FACT
        mutated = original.replace(
            "[PROVISIONAL WORDING — hedged motivation in S-035 / SANDRA-DIRECT-BODY-2026-08-04, SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`] The direct Sandra body motivates current-load / broadcast awareness only as hedged provisional wording — “as it seems to be the case” — and does not by itself establish broadcast feasibility, capacity infeasibility, or a mandatory deliverable.",  # noqa: E501
            "[SOURCE-DERIVED FACT — S-035 / SANDRA-DIRECT-BODY-2026-08-04, SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`] RSU broadcast of load is infeasible and is a mandatory deliverable.",  # noqa: E501
        )
        summary.write_text(mutated)
        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail on S-035 promotion to fact, got pass: {result.stdout}"
        )
        stderr = result.stderr + result.stdout
        assert "S-035" in stderr or "provisional" in stderr.lower() or "hedged" in stderr.lower(), (
            f"S-035 promotion should mention S-035/hedged/provisional: {stderr}"
        )
    finally:
        summary.write_text(original)
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"


def test_validator_rejects_tt_req_008_implementation_verified() -> None:
    """Discriminating: TT-REQ-008 incorrectly tagged IMPLEMENTATION-VERIFIED must fail."""
    summary = ROOT / "docs/closure/v08_alignment/improved_strategy_evidence_summary.md"
    original = summary.read_text()
    try:
        mutated = original.replace(
            "[SOURCE-DERIVED FACT — Negotiated Version 1, whole-file SHA-256 `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2`, canonical payload SHA-256 `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`] TT-REQ-008: Comparative infrastructure-side RSU load management is SHOULD",  # noqa: E501
            "[IMPLEMENTATION-VERIFIED FACT — Negotiated Version 1 TT-REQ-008] Comparative infrastructure-side RSU load management is SHOULD",  # noqa: E501
        )
        summary.write_text(mutated)
        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail on TT-REQ-008 implementation-verified mis-tag, got pass: {result.stdout}"  # noqa: E501
        )
        stderr = result.stderr + result.stdout
        assert "TT-REQ-008" in stderr and "IMPLEMENTATION-VERIFIED" in stderr, (
            f"TT-REQ-008 mis-tag should mention TT-REQ-008/IMPLEMENTATION-VERIFIED: {stderr}"
        )
    finally:
        summary.write_text(original)
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"


def test_validator_rejects_congested_road_fact_attribution() -> None:
    """Discriminating: unsupported congested-road RSU locus presented as RESEARCH-EVIDENCE FACT must fail."""  # noqa: E501
    summary = ROOT / "docs/closure/v08_alignment/improved_strategy_evidence_summary.md"
    original = summary.read_text()
    try:
        mutated = original.replace(
            "and `dla` (common-target) execution-share range 0.237–0.242. [INFERENCE — per-RSU execution-share arrays show the largest deviations on a subset of RSUs; admitted artifacts contain no road-congestion mapping for indexed RSUs, so no congested-road locus is claimed]",  # noqa: E501
            "and `dla` (common-target) execution-share range 0.237–0.242 (max deviation concentrated on congested-road RSUs).",  # noqa: E501
        )
        summary.write_text(mutated)
        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail on congested-road fact attribution, got pass: {result.stdout}"
        )
        stderr = result.stderr + result.stdout
        assert "congested-road" in stderr.lower() or "concentrated" in stderr.lower(), (
            f"congested-road attribution should mention congested-road/concentrated: {stderr}"
        )
    finally:
        summary.write_text(original)
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"


def test_validator_rejects_json_csv_artifact_mismatch_via_join() -> None:
    """Discriminating: JSON/CSV artifact_path join mismatch must fail even for non-E2b pinned rows."""  # noqa: E501
    original_csv = FIGURE_CSV.read_text()
    try:
        lines = original_csv.splitlines()
        header = lines[0]
        cols = header.split(",")
        mutated_lines = [header]
        for line in lines[1:]:
            import io

            reader = csv.DictReader(io.StringIO(header + "\n" + line))
            row_csv = next(reader)
            if row_csv.get("figure_id") == "fig2_e2c_dla_minus_ingress_seed1":
                row_csv["artifact_path"] = "/tmp/wrong_path/run_1"  # noqa: S108
            writer_io = io.StringIO()
            writer = csv.DictWriter(writer_io, fieldnames=cols)
            writer.writerow(row_csv)
            mutated_line = writer_io.getvalue().strip().splitlines()[-1]
            mutated_lines.append(mutated_line)
        FIGURE_CSV.write_text("\n".join(mutated_lines) + "\n")
        result = run_validator()
        assert result.returncode != 0, (
            f"validator should fail on join artifact mismatch, got pass: {result.stdout}"
        )
        stderr = result.stderr + result.stdout
        assert "artifact_path" in stderr or "join mismatch" in stderr.lower(), (
            f"artifact join mismatch should mention artifact_path: {stderr}"
        )
    finally:
        FIGURE_CSV.write_text(original_csv)
        restored = run_validator()
        assert restored.returncode == 0, f"validator should pass after restore: {restored.stderr}"
