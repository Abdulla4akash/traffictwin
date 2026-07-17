"""Command-line interface for Phase 1 TrafficTwin workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from traffictwin.config.capabilities import default_export_import_manifest, manifest_to_plain_dict
from traffictwin.config.seed_io import SeedIOError, load_seed, normalise_seed_file
from traffictwin.ingestion.bundle import import_bundle as import_run_bundle
from traffictwin.ingestion.bundle import inspect_bundle, validate_bundle
from traffictwin.storage.registry import Registry, RegistryConflictError

app = typer.Typer(no_args_is_help=True, help="TrafficTwin research-software CLI.")
registry_app = typer.Typer(no_args_is_help=True, help="Metadata registry commands.")
bundle_app = typer.Typer(no_args_is_help=True, help="Run-bundle commands.")
app.add_typer(registry_app, name="registry")
app.add_typer(bundle_app, name="bundle")


@app.command("validate-seed")
def validate_seed(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Validate a scenario seed YAML file."""

    try:
        seed = load_seed(path)
    except SeedIOError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"valid seed: {seed.seed_id}")


@app.command("normalise-seed")
def normalise_seed(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    destination: Annotated[Path, typer.Argument(dir_okay=False, writable=True)],
) -> None:
    """Validate and export a deterministic YAML representation."""

    try:
        document = normalise_seed_file(source, destination)
    except SeedIOError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"normalised seed: {document.seed.seed_id} -> {destination}")


@app.command("capabilities")
def capabilities() -> None:
    """Show the default export/import-only capability manifest."""

    manifest = default_export_import_manifest()
    typer.echo(yaml.safe_dump(manifest_to_plain_dict(manifest), sort_keys=False))


@registry_app.command("init")
def init_registry(
    path: Annotated[Path, typer.Argument(dir_okay=False, writable=True)],
) -> None:
    """Initialise a SQLite metadata registry."""

    registry = Registry(path)
    registry.initialize()
    typer.echo(f"registry initialised: {path}")


@registry_app.command("inspect")
def inspect_registry(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Inspect a SQLite metadata registry."""

    summary = Registry(path).inspect()
    typer.echo(f"registry: {summary.path}")
    typer.echo(f"seeds: {summary.seed_count}")
    typer.echo(f"experiments: {summary.experiment_count}")
    typer.echo(f"runs: {summary.run_count}")
    typer.echo(f"bundle_imports: {summary.bundle_import_count}")


@bundle_app.command("validate")
def validate_run_bundle(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Validate a directory or ZIP run bundle."""

    result = validate_bundle(path)
    report = result.report
    typer.echo(f"bundle: {report.bundle_id or 'unknown'}")
    typer.echo(f"run: {report.run_id or 'unknown'}")
    typer.echo(f"status: {report.status.value}")
    typer.echo(f"may_import: {report.may_import}")
    typer.echo(f"findings: {len(report.findings)}")
    if not report.may_import:
        raise typer.Exit(code=1)


@bundle_app.command("inspect")
def inspect_run_bundle(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Inspect a bundle without registry mutation."""

    result = inspect_bundle(path)
    report = result.report
    typer.echo(f"bundle: {report.bundle_id or 'unknown'}")
    typer.echo(f"run: {report.run_id or 'unknown'}")
    typer.echo(f"status: {report.status.value}")
    typer.echo(f"declared_files: {len(result.manifest.files) if result.manifest else 0}")
    typer.echo(f"available_evidence: {', '.join(report.available_evidence_categories) or 'none'}")
    typer.echo(
        f"unavailable_evidence: {', '.join(report.unavailable_evidence_categories) or 'none'}"
    )


@bundle_app.command("import")
def import_run_bundle_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False, writable=True)],
) -> None:
    """Validate and register an accepted bundle."""

    try:
        result = import_run_bundle(path, registry)
    except RegistryConflictError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"bundle: {result.bundle_id or 'unknown'}")
    typer.echo(f"run: {result.run_id or 'unknown'}")
    typer.echo(f"status: {result.status}")
    typer.echo(f"idempotent: {result.idempotent}")
    typer.echo(result.message)
    if result.status == "rejected":
        raise typer.Exit(code=1)


@bundle_app.command("report")
def report_run_bundle(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Write a machine-readable validation report."""

    if output_format != "json":
        typer.echo("only --format json is supported", err=True)
        raise typer.Exit(code=1)
    result = validate_bundle(path)
    typer.echo(result.report.to_json())
