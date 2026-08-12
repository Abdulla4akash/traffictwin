"""Feature-local CLI for reproducibility replay — allowlisted only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from traffictwin.reproducibility_replay.adapters import ADAPTER_REGISTRY
from traffictwin.reproducibility_replay.service import (
    build_receipt,
    build_replay_plan,
    build_replay_plan_from_capsule_bytes,
    execute_replay,
    plan_to_json,
    receipt_to_csv,
    receipt_to_json,
    replay_contract,
    verify_capsule_integrity,
)

app = typer.Typer(
    help="Deterministic allowlisted replay for TrafficTwin analyses.", no_args_is_help=True
)


def _read_capsule_bytes(path: Path) -> bytes:
    if not path.exists() or not path.is_file():
        typer.echo(f"capsule not found: {path}", err=True)
        raise typer.Exit(code=1)
    return path.read_bytes()


def _load_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data: Any = json.loads(text)
    if not isinstance(data, dict):
        typer.echo("payload must be a JSON object", err=True)
        raise typer.Exit(code=1)
    return data


@app.command("verify")
def verify_command(
    capsule: Path = typer.Argument(..., help="Path to capsule ZIP."),  # noqa: B008
    json_output: bool = typer.Option(False, "--json", help="Emit JSON."),  # noqa: B008
) -> None:
    """Verify internal capsule integrity (checksums, manifest fingerprint)."""
    payload = _read_capsule_bytes(capsule)
    integrity = verify_capsule_integrity(payload)
    if json_output:
        typer.echo(json.dumps(integrity.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        typer.echo(f"valid: {integrity.valid}")
        typer.echo(f"status: {integrity.status}")
        if integrity.capsule_id:
            typer.echo(f"capsule_id: {integrity.capsule_id}")
        if integrity.manifest_fingerprint:
            typer.echo(f"manifest_fingerprint: {integrity.manifest_fingerprint}")
        if integrity.errors:
            for err in integrity.errors:
                typer.echo(f"error: {err}", err=True)
        typer.echo(f"embedded: {integrity.embedded_members}")
        typer.echo(f"referenced: {integrity.referenced_members}")
    if not integrity.valid:
        raise typer.Exit(code=1)


@app.command("plan")
def plan_command(
    capsule: Path | None = typer.Option(None, "--capsule", help="Path to capsule ZIP."),  # noqa: B008
    artifact: list[Path] = typer.Option(  # noqa: B008
        [], "--artifact", help="Standalone fingerprinted artifact JSON (repeatable)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON plan."),  # noqa: B008
    csv_output: bool = typer.Option(False, "--csv", help="Emit CSV."),  # noqa: B008
    out: Path | None = typer.Option(None, "--out", help="Write plan JSON to path."),  # noqa: B008
) -> None:
    """Build replay plan from a verified capsule or standalone artifacts."""
    if capsule is None and not artifact:
        typer.echo("provide --capsule or at least one --artifact", err=True)
        raise typer.Exit(code=1)
    if capsule is not None and artifact:
        typer.echo("provide either --capsule or --artifact, not both", err=True)
        raise typer.Exit(code=1)

    if capsule is not None:
        payload = _read_capsule_bytes(capsule)
        plan = build_replay_plan_from_capsule_bytes(payload)
    else:
        standalone: list[tuple[str, dict[str, Any], str | None]] = []
        for p in artifact:
            data = _load_json(p)
            logical_id = str(
                data.get("logical_id") or data.get("report_id") or data.get("study_id") or p.stem
            )
            # Evidence label hint if present
            evidence_label = (
                str(data.get("evidence_label"))
                if isinstance(data.get("evidence_label"), str)
                else None
            )
            standalone.append((logical_id, data, evidence_label))
        plan = build_replay_plan(standalone_artifacts=standalone)

    # bounded plan size guard
    if json_output or out is not None:
        text = plan_to_json(plan)
        if out is not None:
            out.write_text(text, encoding="utf-8")
            typer.echo(f"plan written to {out}")
        if json_output:
            typer.echo(text)
        return
    if csv_output:
        from traffictwin.reproducibility_replay.service import plan_entries_to_csv

        typer.echo(plan_entries_to_csv(plan))
        return

    # Human table
    typer.echo(f"verification_status: {plan.verification_status}")
    typer.echo(f"entries: {len(plan.entries)}")
    for entry in plan.entries:
        typer.echo(
            f"- {(entry.artifact_kind.value if entry.artifact_kind else '')}:{entry.logical_id} {entry.status.value} replayable={entry.replayable} reason={entry.reason}"  # noqa: E501
        )
    for w in plan.warnings:
        typer.echo(f"warning: {w}", err=True)


@app.command("run")
def run_command(
    capsule: Path = typer.Argument(..., help="Path to capsule ZIP."),  # noqa: B008
    select: list[str] = typer.Option(  # noqa: B008
        [],
        "--select",
        help="Explicit replayable entry as kind:logical_id (repeatable). Required — no automatic run.",  # noqa: E501
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit receipt JSON."),  # noqa: B008
    csv_output: bool = typer.Option(False, "--csv", help="Emit receipt CSV."),  # noqa: B008
    out: Path | None = typer.Option(None, "--out", help="Write receipt JSON to path."),  # noqa: B008
) -> None:
    """Execute only explicitly selected replayable entries and emit receipt."""
    from traffictwin.reproducibility_replay.models import ReplayArtifactKind

    payload = _read_capsule_bytes(capsule)
    plan = build_replay_plan_from_capsule_bytes(payload)
    if not select:
        typer.echo(
            "no automatic run: provide --select kind:logical_id for each entry to replay", err=True
        )
        typer.echo("available replayable entries:", err=True)
        for e in plan.entries:
            if e.replayable:
                typer.echo(  # noqa: E501
                    f"  {(e.artifact_kind.value if e.artifact_kind else '')}:{e.logical_id}",
                    err=True,
                )
        raise typer.Exit(code=1)

    selected: list[tuple[ReplayArtifactKind, str]] = []
    for spec in select:
        if ":" not in spec:
            typer.echo(f"invalid --select spec {spec!r}; expected kind:logical_id", err=True)
            raise typer.Exit(code=1)
        kind_str, logical_id = spec.split(":", 1)
        if not logical_id.strip():
            typer.echo(f"invalid --select spec {spec!r}; logical_id must be non-empty", err=True)
            raise typer.Exit(code=1)
        if (  # noqa: E501
            "/" in logical_id
            or "\\" in logical_id
            or logical_id.startswith("~")
            or ".." in logical_id
        ):
            typer.echo(  # noqa: E501
                f"invalid --select logical_id {logical_id!r}; "  # noqa: E501
                "must be a safe identifier without paths",  # noqa: E501
                err=True,
            )
            raise typer.Exit(code=1)
        try:
            kind = ReplayArtifactKind(kind_str)
        except ValueError as exc:
            typer.echo(f"unsupported kind {kind_str!r}", err=True)
            raise typer.Exit(code=1) from exc
        if kind not in ADAPTER_REGISTRY:
            typer.echo(f"kind not allowlisted: {kind_str!r}", err=True)
            raise typer.Exit(code=1)
        selected.append((kind, logical_id))

    executions, refusals = execute_replay(plan, selected=selected)
    receipt = build_receipt(plan, executions, refusals)

    if json_output or out is not None:
        text = receipt_to_json(receipt)
        if out is not None:
            out.write_text(text, encoding="utf-8")
            typer.echo(f"receipt written to {out}")
        if json_output:
            typer.echo(text)
        return
    if csv_output:
        typer.echo(receipt_to_csv(receipt))
        return

    typer.echo(f"receipt_id: {receipt.receipt_id}")
    typer.echo(
        f"executed: {receipt.executed_count} matched: {receipt.matched_count} mismatched: {receipt.mismatched_count} failed: {receipt.failed_count}"  # noqa: E501
    )
    for exe in receipt.executions:
        typer.echo(
            f"- {exe.artifact_kind.value}:{exe.logical_id} {exe.status.value} expected={exe.expected_output_fingerprint[:12]}… actual={exe.actual_output_fingerprint[:12] if exe.actual_output_fingerprint else 'none'}"  # noqa: E501
        )
    for rej in receipt.refusals:
        typer.echo(
            f"refusal: {rej.artifact_kind.value if rej.artifact_kind else 'unknown'}:{rej.logical_id or ''} {rej.status.value} {rej.reason}",  # noqa: E501
            err=True,
        )
    for mis in receipt.mismatches:
        typer.echo(
            f"mismatch: {mis.logical_id} expected {mis.expected_fingerprint[:12]}… got {mis.actual_fingerprint[:12]}… {mis.detail}",  # noqa: E501
            err=True,
        )


@app.command("compare")
def compare_command(
    receipt_path: Path = typer.Argument(..., help="Path to receipt JSON."),  # noqa: B008
    json_output: bool = typer.Option(False, "--json", help="Emit comparison JSON."),  # noqa: B008
) -> None:
    """Show expected vs actual fingerprint comparisons from a receipt."""
    data = _load_json(receipt_path)
    # Verify receipt fingerprint integrity before showing comparisons
    try:
        from traffictwin.reproducibility_replay.models import ReplayReceipt

        receipt = ReplayReceipt.model_validate(data)
        computed = receipt.computed_fingerprint()
        if computed != receipt.receipt_fingerprint:
            typer.echo(
                f"receipt fingerprint mismatch: expected {receipt.receipt_fingerprint} "  # noqa: E501
                f"computed {computed}",
                err=True,
            )
            raise typer.Exit(code=1)
    except SystemExit:
        raise
    except Exception as exc:
        typer.echo(f"invalid receipt: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    comparisons = data.get("comparisons") or []
    mismatches = data.get("mismatches") or []
    if json_output:
        out = {
            "comparisons": comparisons,
            "mismatches": mismatches,
            "matched": data.get("matched_count"),
            "mismatched": data.get("mismatched_count"),
        }
        typer.echo(json.dumps(out, indent=2, sort_keys=True))
        return
    if not comparisons:
        typer.echo("no comparisons in receipt")
        return
    for comp in comparisons:
        matched = comp.get("matched")
        status = comp.get("status")
        typer.echo(
            f"{comp.get('artifact_kind')}:{comp.get('logical_id')} matched={matched} status={status} expected={str(comp.get('expected_fingerprint', ''))[:12]}… actual={str(comp.get('actual_fingerprint', ''))[:12]}…"  # noqa: E501
        )
    if mismatches:
        typer.echo(f"mismatches: {len(mismatches)}", err=True)


@app.command("show-receipt")
def show_receipt_command(
    receipt_path: Path = typer.Argument(..., help="Path to receipt JSON."),  # noqa: B008
    canonical: bool = typer.Option(False, "--canonical", help="Emit canonical fingerprint input."),  # noqa: B008
) -> None:
    """Display a receipt (JSON or canonical payload)."""
    data = _load_json(receipt_path)
    # Verify fingerprint before display
    try:
        from traffictwin.reproducibility_replay.models import ReplayReceipt

        receipt_obj = ReplayReceipt.model_validate(data)
        computed = receipt_obj.computed_fingerprint()
        if computed != receipt_obj.receipt_fingerprint:
            typer.echo(
                f"receipt fingerprint mismatch: expected {receipt_obj.receipt_fingerprint} "  # noqa: E501
                f"computed {computed}",
                err=True,
            )
            raise typer.Exit(code=1)
    except SystemExit:
        raise
    except Exception as exc:
        typer.echo(f"invalid receipt: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if canonical:
        # Recompute canonical if possible
        try:
            from traffictwin.reproducibility_replay.models import ReplayReceipt

            receipt = ReplayReceipt.model_validate(data)
            typer.echo(receipt.canonical_json())
        except Exception as exc:
            typer.echo(f"cannot canonicalise receipt: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    else:
        typer.echo(json.dumps(data, indent=2, sort_keys=True))


@app.command("contract")
def contract_command(
    json_output: bool = typer.Option(True, "--json/--no-json", help="Emit contract JSON."),  # noqa: B008
) -> None:
    """Show the allowlisted replay contract and evidence boundary."""
    contract = replay_contract()
    typer.echo(contract.model_dump_json(indent=2))
