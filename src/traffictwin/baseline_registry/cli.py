"""Feature-local CLI for Baseline Registry — expose app: typer.Typer."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from traffictwin.baseline_registry.models import BaselineRegistry, BaselineScope
from traffictwin.baseline_registry.service import (
    approve_candidate,
    build_candidate,
    create_empty_registry,
    promote_baseline,
    register_candidate,
    supersede_baseline,
    validate_registry_json,
)

app = typer.Typer(help="Baseline Registry & Promotion Workflow", add_completion=False)


def _default_registry_path() -> Path:
    return Path("baseline_registry.json")


def _load_registry(path: Path) -> BaselineRegistry:
    if not path.exists():
        return create_empty_registry()
    try:
        return validate_registry_json(path.read_bytes())
    except Exception as exc:
        typer.echo(f"Could not load registry: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _save_registry(path: Path, registry: BaselineRegistry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry.to_json(), encoding="utf-8")


@app.command("validate")
def validate_cmd(
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Registry JSON path")
    ] = _default_registry_path(),  # noqa: B008
) -> None:
    """Validate a registry JSON file."""
    try:
        reg = validate_registry_json(registry_path.read_bytes())
        typer.echo(  # noqa: E501
            f"Valid registry: {len(reg.ledger)} ledger entries, "
            f"{len(reg.candidates)} candidates, {len(reg.active_baselines)} active"
        )
    except Exception as exc:
        typer.echo(f"Invalid registry: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("register")
def register_cmd(
    candidate_id: Annotated[str, typer.Option("--candidate-id", help="Candidate ID")],
    scope_id: Annotated[str, typer.Option("--scope-id", help="Scope ID")],
    purpose: Annotated[str, typer.Option("--purpose", help="Purpose (12+ chars)")],
    cohort: Annotated[str, typer.Option("--cohort", help="Cohort definition (8+ chars)")],
    artifact_fingerprint: Annotated[
        str, typer.Option("--artifact-fingerprint", help="SHA-256 hex")
    ],
    artifact_type: Annotated[
        str, typer.Option("--artifact-type", help="Artifact type")
    ] = "metric_collection",
    schema_version: Annotated[str, typer.Option("--schema-version", help="Schema version")] = "1.0",
    evidence_standing: Annotated[
        str, typer.Option("--evidence-standing", help="Evidence standing")
    ] = "admitted_research",
    source_standing: Annotated[
        str, typer.Option("--source-standing", help="Source standing")
    ] = "verified",
    regression_gate_policy: Annotated[
        str, typer.Option("--regression-gate-policy", help="Policy")
    ] = "STA-04 exact policy for baseline promotion",
    limitations: Annotated[
        str, typer.Option("--limitations", help="Limitations")
    ] = "Baseline is a review artifact; no causal or deployment claim.",
    metric_contracts: Annotated[
        str, typer.Option("--metric-contracts", help="Comma-separated metric contracts")
    ] = "task.completion.rate@1.0",
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Registry JSON path")
    ] = _default_registry_path(),  # noqa: B008
) -> None:
    """Register a candidate baseline."""
    registry = _load_registry(registry_path)
    scope = BaselineScope(scope_id=scope_id, purpose=purpose, cohort_definition=cohort)
    contracts = [c.strip() for c in metric_contracts.split(",") if c.strip()]
    try:
        candidate = build_candidate(
            candidate_id=candidate_id,
            scope=scope,
            artifact_fingerprint=artifact_fingerprint,
            artifact_type=artifact_type,
            schema_version=schema_version,
            metric_contracts=contracts,
            cohort_definition=cohort,
            evidence_standing=evidence_standing,
            source_standing=source_standing,
            regression_gate_policy=regression_gate_policy,
            limitations=limitations,
        )
        new_registry = register_candidate(registry, candidate, actor="cli")
        _save_registry(registry_path, new_registry)
        typer.echo(
            f"Registered candidate {candidate_id} with fingerprint "  # noqa: E501
            f"{candidate.artifact_fingerprint[:12]}…"
        )
    except Exception as exc:
        typer.echo(f"Register failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("approve")
def approve_cmd(
    candidate_id: Annotated[str, typer.Option("--candidate-id", help="Candidate ID")],
    approver: Annotated[str, typer.Option("--approver", help="Approver name")] = "reviewer",
    note: Annotated[
        str, typer.Option("--note", help="Approval note")
    ] = "Explicit approval for promotion after review.",
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Registry JSON path")
    ] = _default_registry_path(),  # noqa: B008
) -> None:
    """Approve a candidate for promotion."""
    registry = _load_registry(registry_path)
    try:
        new_registry, approval = approve_candidate(
            registry, candidate_id=candidate_id, approver=approver, approval_note=note
        )
        _save_registry(registry_path, new_registry)
        typer.echo(
            f"Approved {candidate_id} with fingerprint {approval.approval_fingerprint[:12]}…"
        )
    except Exception as exc:
        typer.echo(f"Approve failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("promote")
def promote_cmd(
    candidate_id: Annotated[str, typer.Option("--candidate-id", help="Candidate ID")],
    requested_by: Annotated[str, typer.Option("--requested-by", help="Requester")] = "operator",
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Registry JSON path")
    ] = _default_registry_path(),  # noqa: B008
) -> None:
    """Promote an approved candidate to active baseline."""
    registry = _load_registry(registry_path)
    if candidate_id not in registry.candidates:
        typer.echo(f"Candidate {candidate_id!r} not found", err=True)
        raise typer.Exit(code=1)
    candidate = registry.candidates[candidate_id]
    approval = registry.approvals.get(candidate_id)
    if approval is None:
        typer.echo("No approval exists for candidate – BLOCKED", err=True)
        raise typer.Exit(code=1)
    from traffictwin.baseline_registry.models import BaselinePromotionRequest

    request = BaselinePromotionRequest(
        candidate_id=candidate_id,
        scope_id=candidate.scope.scope_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=approval.approval_fingerprint,
        registry_parent_fingerprint=registry.registry_fingerprint,
        requested_by=requested_by,
        requested_at=datetime.now(UTC),
    )
    new_registry, receipt = promote_baseline(registry, request)
    _save_registry(registry_path, new_registry)
    if receipt.status.value == "active":
        typer.echo(
            f"Promoted {candidate_id} -> "  # noqa: E501
            f"{receipt.promoted_record.baseline_id if receipt.promoted_record else ''}"
        )
    else:
        typer.echo(f"Promote BLOCKED: {'; '.join(receipt.blocked_reasons)}", err=True)
        raise typer.Exit(code=1)


@app.command("supersede")
def supersede_cmd(
    scope_id: Annotated[str, typer.Option("--scope-id", help="Scope ID")],
    candidate_id: Annotated[str, typer.Option("--candidate-id", help="Superseding candidate ID")],
    actor: Annotated[str, typer.Option("--actor", help="Actor")] = "operator",
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Registry JSON path")
    ] = _default_registry_path(),  # noqa: B008
) -> None:
    """Supersede active baseline in a scope."""
    registry = _load_registry(registry_path)
    new_registry, receipt = supersede_baseline(
        registry, scope_id=scope_id, superseding_candidate_id=candidate_id, actor=actor
    )
    _save_registry(registry_path, new_registry)
    if receipt.status.value == "active":
        typer.echo(f"Superseded {scope_id} with {candidate_id}")
    else:
        typer.echo(f"Supersede BLOCKED: {'; '.join(receipt.blocked_reasons)}", err=True)
        raise typer.Exit(code=1)


@app.command("show")
def show_cmd(
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Registry JSON path")
    ] = _default_registry_path(),  # noqa: B008
    json_output: Annotated[bool, typer.Option("--json", help="Dump full JSON")] = False,
) -> None:
    """Show registry summary."""
    registry = _load_registry(registry_path)
    if json_output:
        typer.echo(registry.to_json())
        return
    typer.echo(f"Registry fingerprint: {registry.registry_fingerprint}")
    typer.echo(f"Candidates: {len(registry.candidates)}")
    for cand_id, cand in sorted(registry.candidates.items()):
        typer.echo(
            f"  - {cand_id} scope={cand.scope.scope_id} "  # noqa: E501
            f"fp={cand.artifact_fingerprint[:12]}… {cand.evidence_standing.value}"
        )
    typer.echo(f"Active baselines: {len(registry.active_baselines)}")
    for scope, rec in sorted(registry.active_baselines.items()):
        typer.echo(
            f"  - {scope} -> {rec.baseline_id} "  # noqa: E501
            f"candidate={rec.candidate_id} fp={rec.artifact_fingerprint[:12]}…"
        )
    typer.echo(f"Ledger: {len(registry.ledger)} entries")
    for entry in registry.ledger:
        typer.echo(
            f"  [{entry.entry_index}] {entry.event_kind.value} "  # noqa: E501
            f"scope={entry.scope_id} candidate={entry.candidate_id or '-'} "
            f"baseline={entry.baseline_id or '-'}"
        )


@app.command("export")
def export_cmd(
    registry_path: Annotated[
        Path, typer.Option("--registry", help="Registry JSON path")
    ] = _default_registry_path(),  # noqa: B008
    output: Annotated[Path, typer.Option("--output", help="Output path")] = Path(
        "baseline_registry_export.json"
    ),  # noqa: B008
    format: Annotated[str, typer.Option("--format", help="Export format: json or csv")] = "json",
) -> None:
    """Export registry as JSON or CSV."""
    registry = _load_registry(registry_path)
    if format == "json":
        output.write_text(registry.to_json(), encoding="utf-8")
        typer.echo(f"Exported JSON to {output}")
    elif format == "csv":
        from traffictwin.baseline_registry.service import registry_to_csv

        output.write_text(registry_to_csv(registry), encoding="utf-8")
        typer.echo(f"Exported CSV to {output}")
    else:
        typer.echo(f"Unknown format {format!r}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
