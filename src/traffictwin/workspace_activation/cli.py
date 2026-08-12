"""Feature-local CLI for workspace activation — no shared wiring."""

from __future__ import annotations

from pathlib import Path

import typer

from traffictwin.workspace_activation.models import (
    RetentionPolicy,
    WorkspaceActivationConfirmation,
    WorkspaceActivationRequest,
)
from traffictwin.workspace_activation.service import (
    ActivationRefusedError,
    activate_workspace,
    build_activation_plan,
    deactivate_workspace,
    get_workspace_status,
    plan_to_csv,
    plan_to_json,
    preflight_to_csv,
    preflight_to_json,
    preflight_workspace,
    receipt_to_csv,
    receipt_to_json,
)

app = typer.Typer(help="Local real-workspace activation wizard.", no_args_is_help=True)


def _parse_request(
    destination: str,
    bods_enabled: bool,
    national_highways_enabled: bool,
    retention_days: int,
    anonymize: bool,
    allow_export: bool,
    backup_destination: str | None,
    start_workers: bool,
    workers: str | None,
) -> WorkspaceActivationRequest:
    allowlisted: list[str] = []
    if workers:
        allowlisted = [w.strip() for w in workers.split(",") if w.strip()]
    return WorkspaceActivationRequest(
        destination_path=destination,
        bods_enabled=bods_enabled,
        national_highways_enabled=national_highways_enabled,
        retention_policy=RetentionPolicy(
            retention_days=retention_days, anonymize=anonymize, allow_export=allow_export
        ),
        backup_destination=backup_destination,
        start_workers=start_workers,
        allowlisted_workers=allowlisted,
    )


@app.command("preflight")
def preflight_cmd(
    destination: str = typer.Argument(..., help="Destination workspace path"),
    bods_enabled: bool = typer.Option(False, "--bods/--no-bods", help="Enable BODS provider"),
    national_highways_enabled: bool = typer.Option(
        False,
        "--national-highways/--no-national-highways",
        help="Enable National Highways provider",
    ),
    retention_days: int = typer.Option(30, "--retention-days", min=1, max=3650),
    anonymize: bool = typer.Option(True, "--anonymize/--no-anonymize"),
    allow_export: bool = typer.Option(False, "--allow-export/--no-allow-export"),
    backup_destination: str | None = typer.Option(None, "--backup-destination", help="Backup path"),
    start_workers: bool = typer.Option(False, "--start-workers/--no-start-workers"),
    workers: str | None = typer.Option(
        None, "--workers", help="Comma-separated allowlisted workers"
    ),
    json_out: str | None = typer.Option(None, "--json-out", help="Write JSON to file"),
    csv_out: str | None = typer.Option(None, "--csv-out", help="Write CSV to file"),
) -> None:
    """Dry-run preflight checks without mutation or network."""
    request = _parse_request(
        destination,
        bods_enabled,
        national_highways_enabled,
        retention_days,
        anonymize,
        allow_export,
        backup_destination,
        start_workers,
        workers,
    )
    result = preflight_workspace(request)
    typer.echo(result.canonical_json())
    if json_out:
        Path(json_out).write_text(preflight_to_json(result), encoding="utf-8")
        typer.echo(f"Wrote JSON to {json_out}")
    if csv_out:
        Path(csv_out).write_text(preflight_to_csv(result), encoding="utf-8")
        typer.echo(f"Wrote CSV to {csv_out}")


@app.command("plan")
def plan_cmd(
    destination: str = typer.Argument(..., help="Destination workspace path"),
    bods_enabled: bool = typer.Option(False, "--bods/--no-bods"),
    national_highways_enabled: bool = typer.Option(
        False, "--national-highways/--no-national-highways"
    ),
    retention_days: int = typer.Option(30, "--retention-days", min=1, max=3650),
    anonymize: bool = typer.Option(True, "--anonymize/--no-anonymize"),
    allow_export: bool = typer.Option(False, "--allow-export/--no-allow-export"),
    backup_destination: str | None = typer.Option(None, "--backup-destination"),
    start_workers: bool = typer.Option(False, "--start-workers/--no-start-workers"),
    workers: str | None = typer.Option(None, "--workers"),
    json_out: str | None = typer.Option(None, "--json-out"),
    csv_out: str | None = typer.Option(None, "--csv-out"),
) -> None:
    """Preview deterministic activation plan with confirmation digest."""
    request = _parse_request(
        destination,
        bods_enabled,
        national_highways_enabled,
        retention_days,
        anonymize,
        allow_export,
        backup_destination,
        start_workers,
        workers,
    )
    pre = preflight_workspace(request)
    plan = build_activation_plan(request, pre)
    typer.echo(plan.canonical_json())
    typer.echo(f"Confirmation digest: {plan.confirmation_digest}", err=True)
    if json_out:
        Path(json_out).write_text(plan_to_json(plan), encoding="utf-8")
        typer.echo(f"Wrote JSON to {json_out}")
    if csv_out:
        Path(csv_out).write_text(plan_to_csv(plan), encoding="utf-8")
        typer.echo(f"Wrote CSV to {csv_out}")


@app.command("activate")
def activate_cmd(
    destination: str = typer.Argument(..., help="Destination workspace path"),
    confirmation_digest: str = typer.Option(
        ..., "--confirmation-digest", help="Exact preview digest from plan"
    ),
    bods_enabled: bool = typer.Option(False, "--bods/--no-bods"),
    national_highways_enabled: bool = typer.Option(
        False, "--national-highways/--no-national-highways"
    ),
    retention_days: int = typer.Option(30, "--retention-days", min=1, max=3650),
    anonymize: bool = typer.Option(True, "--anonymize/--no-anonymize"),
    allow_export: bool = typer.Option(False, "--allow-export/--no-allow-export"),
    backup_destination: str | None = typer.Option(None, "--backup-destination"),
    start_workers: bool = typer.Option(False, "--start-workers/--no-start-workers"),
    workers: str | None = typer.Option(None, "--workers"),
    json_out: str | None = typer.Option(None, "--json-out"),
    csv_out: str | None = typer.Option(None, "--csv-out"),
) -> None:
    """Activate workspace — requires exact preview digest; no network before confirmation."""
    request = _parse_request(
        destination,
        bods_enabled,
        national_highways_enabled,
        retention_days,
        anonymize,
        allow_export,
        backup_destination,
        start_workers,
        workers,
    )
    pre = preflight_workspace(request)
    plan = build_activation_plan(request, pre)
    confirmation = WorkspaceActivationConfirmation(
        confirmation_digest=confirmation_digest, request_fingerprint=request.fingerprint()
    )
    try:
        receipt = activate_workspace(request, plan, confirmation)
    except ActivationRefusedError as exc:
        typer.echo(f"REFUSED: {exc.code}: {exc.message}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(receipt.canonical_json())
    if json_out:
        Path(json_out).write_text(receipt_to_json(receipt), encoding="utf-8")
        typer.echo(f"Wrote JSON to {json_out}")
    if csv_out:
        Path(csv_out).write_text(receipt_to_csv(receipt), encoding="utf-8")
        typer.echo(f"Wrote CSV to {csv_out}")


@app.command("status")
def status_cmd(
    destination: str = typer.Argument(..., help="Workspace path to query"),
    json_out: str | None = typer.Option(None, "--json-out"),
) -> None:
    """Show workspace status without mutation."""
    status = get_workspace_status(destination)
    typer.echo(status.canonical_json())
    if json_out:
        Path(json_out).write_text(status.canonical_json(), encoding="utf-8")
        typer.echo(f"Wrote JSON to {json_out}")


@app.command("deactivate")
def deactivate_cmd(
    destination: str = typer.Argument(..., help="Workspace path to deactivate"),
    remove_marker: bool = typer.Option(
        False,
        "--remove-marker/--keep-marker",
        help="Remove activation marker (requires confirmation)",
    ),
    confirmation_digest: str | None = typer.Option(
        None,
        "--confirmation-digest",
        help="Exact digest from activation receipt if removing marker",
    ),
    json_out: str | None = typer.Option(None, "--json-out"),
) -> None:
    """Deactivate workspace — preserves data by default; marker removal is confirmation-gated."""
    confirmation = None
    if remove_marker:
        if not confirmation_digest:
            typer.echo("REFUSED: remove-marker requires --confirmation-digest", err=True)
            raise typer.Exit(code=2)
        # We need request fingerprint; we can fetch from status
        status = get_workspace_status(destination)
        fp = status.receipt.request_fingerprint if status.receipt else None
        confirmation = WorkspaceActivationConfirmation(
            confirmation_digest=confirmation_digest, request_fingerprint=fp
        )
    try:
        receipt = deactivate_workspace(
            destination, confirmation=confirmation, remove_marker=remove_marker
        )
    except ActivationRefusedError as exc:
        typer.echo(f"REFUSED: {exc.code}: {exc.message}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(receipt.canonical_json())
    if json_out:
        Path(json_out).write_text(receipt.canonical_json(), encoding="utf-8")
        typer.echo(f"Wrote JSON to {json_out}")


if __name__ == "__main__":
    app()
