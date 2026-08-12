"""Feature-local Typer app for Metric Contract Registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .models import MetricContractRegistry
from .service import (
    load_registry_from_file,
    load_registry_from_json,
    merge_registries,
    registry_to_csv,
    registry_to_json,
    validate_registry,
)

app = typer.Typer(
    no_args_is_help=True, help="Metric Contract Registry — closed metadata contracts."
)


@app.command("validate")
def validate_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Registry JSON file")] = Path(
        "-"
    ),
    output_format: Annotated[
        str, typer.Option("--format", help="Output format: text or json")
    ] = "text",
) -> None:
    """Validate a registry JSON file and report findings."""
    try:
        if str(input_path) == "-":
            # Read from stdin
            import sys

            text = sys.stdin.read()
            registry = load_registry_from_json(text)
        else:
            registry = load_registry_from_file(input_path)
    except Exception as exc:
        typer.secho(f"Failed to load registry: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    receipt = validate_registry(registry)
    if output_format == "json":
        payload = {
            "registry_fingerprint": receipt.registry_fingerprint,
            "registry_version": receipt.registry_version,
            "contract_count": receipt.contract_count,
            "status": receipt.status.value,
            "findings": [f.model_dump(mode="json") for f in receipt.findings],
            "built_in_conflicts": receipt.built_in_conflicts,
            "supersession_count": receipt.supersession_count,
        }
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        typer.echo(f"registry_fingerprint: {receipt.registry_fingerprint}")
        typer.echo(f"registry_version: {receipt.registry_version}")
        typer.echo(f"contract_count: {receipt.contract_count}")
        typer.echo(f"status: {receipt.status.value}")
        typer.echo(f"supersession_count: {receipt.supersession_count}")
        if receipt.findings:
            typer.echo("findings:")
            for finding in receipt.findings:
                typer.echo(f"  - {finding.severity.value}: {finding.code}: {finding.message}")
        if receipt.built_in_conflicts:
            typer.echo(f"built_in_conflicts: {', '.join(receipt.built_in_conflicts)}")
        if receipt.status.value == "rejected":
            typer.echo("note: registry rejected — built-in override or validation error", err=True)

    if receipt.status.value == "rejected":
        raise typer.Exit(code=1)


@app.command("show")
def show_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Registry JSON file")],
    output_format: Annotated[
        str, typer.Option("--format", help="Output format: text or json")
    ] = "text",
) -> None:
    """Show registry contracts deterministically."""
    try:
        registry = load_registry_from_file(input_path)
    except Exception as exc:
        typer.secho(f"Failed to load registry: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    if output_format == "json":
        typer.echo(registry_to_json(registry))
    else:
        typer.echo(f"registry_fingerprint: {registry.fingerprint()}")
        typer.echo(f"registry_version: {registry.registry_version}")
        typer.echo(f"contracts ({len(registry.deduplicated_contracts())}):")
        for contract in registry.deduplicated_contracts():
            typer.echo(
                f"  - {contract.metric_key} v{contract.metric_version} "
                f"[{contract.unit}/{contract.denominator.value}] — {contract.description[:60]}"
            )
        if registry.supersession:
            typer.echo(f"supersession lineage ({len(registry.supersession)}):")
            for sup in sorted(
                registry.supersession,
                key=lambda s: (s.predecessor_metric_key, s.predecessor_metric_version),
            ):
                typer.echo(
                    f"  - {sup.predecessor_metric_key}:{sup.predecessor_metric_version} "
                    f"-> {sup.successor_metric_key}:{sup.successor_metric_version} ({sup.reason})"
                )
        typer.echo("note: registration does not implement metric computation")


@app.command("merge")
def merge_command(
    inputs: Annotated[list[Path], typer.Argument(help="Registry JSON files to merge")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output path")] = Path(
        "merged_registry.json"
    ),
    output_format: Annotated[
        str, typer.Option("--format", help="Output format: json or csv")
    ] = "json",
) -> None:
    """Merge multiple registries deterministically."""
    registries: list[MetricContractRegistry] = []
    for path in inputs:
        try:
            reg = load_registry_from_file(path)
        except Exception as exc:
            typer.secho(f"Failed to load {path}: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        registries.append(reg)

    try:
        merged, receipt = merge_registries(registries)
    except Exception as exc:
        typer.secho(f"Merge failed: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    if receipt.status.value == "rejected":
        typer.secho(
            f"Merge produced rejected registry: {receipt.findings}", err=True, fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    if output_format == "csv":
        text = registry_to_csv(merged)
        output.write_text(text, encoding="utf-8")
        typer.echo(f"merged registry written to {output} (csv, fingerprint {merged.fingerprint()})")
    else:
        text = registry_to_json(merged)
        output.write_text(text, encoding="utf-8")
        typer.echo(f"merged registry written to {output} (fingerprint {merged.fingerprint()})")
    typer.echo(f"contract_count: {len(merged.deduplicated_contracts())}")


@app.command("fingerprint")
def fingerprint_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Registry JSON file")],
) -> None:
    """Print deterministic fingerprint for a registry."""
    try:
        registry = load_registry_from_file(input_path)
    except Exception as exc:
        typer.secho(f"Failed to load registry: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.echo(registry.fingerprint())


@app.command("export-csv")
def export_csv_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Registry JSON file")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output CSV path")],
) -> None:
    """Export registry contracts to deterministic CSV."""
    try:
        registry = load_registry_from_file(input_path)
    except Exception as exc:
        typer.secho(f"Failed to load registry: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    text = registry_to_csv(registry)
    output.write_text(text, encoding="utf-8")
    typer.echo(f"csv exported to {output}")


@app.command("built-in")
def built_in_command(
    output_format: Annotated[
        str, typer.Option("--format", help="Output format: text or json")
    ] = "text",
) -> None:
    """Show authoritative built-in metric contracts."""
    from .service import build_built_in_registry

    registry = build_built_in_registry()
    if output_format == "json":
        typer.echo(registry_to_json(registry))
    else:
        typer.echo(f"built-in contracts: {len(registry.contracts)}")
        for contract in sorted(registry.contracts, key=lambda c: c.metric_key):
            typer.echo(
                f"  - {contract.metric_key} v{contract.metric_version} [{contract.unit}/{contract.denominator.value}]"  # noqa: E501
            )
        typer.echo("note: built-in contracts remain authoritative")
