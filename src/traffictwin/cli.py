"""Command-line interface for Phase 1 TrafficTwin workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from traffictwin.config.capabilities import default_export_import_manifest, manifest_to_plain_dict
from traffictwin.config.seed_io import SeedIOError, load_seed, normalise_seed_file
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import BundleValidationResult, inspect_bundle, validate_bundle
from traffictwin.ingestion.bundle import import_bundle as import_run_bundle
from traffictwin.metrics.aggregation import aggregate_experiment
from traffictwin.metrics.comparison import compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.evaluation import evaluate_fixture_set, load_fixture_set
from traffictwin.storage.registry import Registry, RegistryConflictError, RegistryNotFoundError

app = typer.Typer(no_args_is_help=True, help="TrafficTwin research-software CLI.")
registry_app = typer.Typer(no_args_is_help=True, help="Metadata registry commands.")
bundle_app = typer.Typer(no_args_is_help=True, help="Run-bundle commands.")
metrics_app = typer.Typer(no_args_is_help=True, help="Deterministic metric commands.")
evidence_app = typer.Typer(no_args_is_help=True, help="Evidence-pack commands.")
experiment_app = typer.Typer(no_args_is_help=True, help="Experiment aggregation commands.")
diagnose_app = typer.Typer(no_args_is_help=True, help="Deterministic diagnostic commands.")
app.add_typer(registry_app, name="registry")
app.add_typer(bundle_app, name="bundle")
app.add_typer(metrics_app, name="metrics")
app.add_typer(evidence_app, name="evidence")
app.add_typer(experiment_app, name="experiment")
app.add_typer(diagnose_app, name="diagnose")


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
    typer.echo(f"metric_collections: {summary.metric_collection_count}")
    typer.echo(f"evidence_packs: {summary.evidence_pack_count}")


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


@metrics_app.command("compute")
def compute_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Compute deterministic metrics for a validated bundle."""

    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    typer.echo(f"run: {collection.run_id}")
    typer.echo(f"metric_version: {collection.metric_version}")
    typer.echo(f"metrics: {len(collection.results)}")
    typer.echo(f"unavailable: {collection.unavailable_count}")
    key_values = collection.by_key()
    for key in (
        "task.completion.rate",
        "infra.utilisation.mean",
        "traffic.speed.mean_mps",
        "trip.duration.mean_s",
    ):
        metric = key_values.get(key)
        if metric is None:
            continue
        value = metric.value if metric.status is MetricStatus.AVAILABLE else "unavailable"
        typer.echo(f"{key}: {value}")
    if not result.report.may_import:
        raise typer.Exit(code=1)


@metrics_app.command("report")
def report_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
) -> None:
    """Emit complete machine-readable metric JSON for a bundle."""

    if output_format != "json":
        typer.echo("only --format json is supported", err=True)
        raise typer.Exit(code=1)
    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    if registry is not None and result.manifest is not None:
        Registry(registry).store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    typer.echo(collection.model_dump_json(indent=2))
    if not result.report.may_import:
        raise typer.Exit(code=1)


@app.command("compare")
def compare_command(
    baseline: Annotated[str, typer.Argument()],
    variation: Annotated[str, typer.Argument()],
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Compare two bundles or two registered metric collections."""

    baseline_collection, baseline_seed = _collection_from_identifier(baseline, registry)
    variation_collection, variation_seed = _collection_from_identifier(variation, registry)
    report = compare_metric_collections(
        baseline_collection,
        variation_collection,
        baseline_seed=baseline_seed,
        variation_seed=variation_seed,
    )
    if output_format == "json":
        typer.echo(report.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"baseline: {baseline_collection.run_id}")
    typer.echo(f"variation: {variation_collection.run_id}")
    for metric in report.comparable_metrics:
        if metric.metric_key in {
            "task.completion.rate",
            "infra.queue_length.mean",
            "traffic.speed.mean_mps",
            "trip.duration.mean_s",
        }:
            typer.echo(
                f"{metric.metric_key}: delta={metric.absolute_delta} "
                f"relative={metric.relative_delta} direction={metric.direction.value}"
            )
    typer.echo(f"unavailable_comparisons: {len(report.unavailable_comparisons)}")


@evidence_app.command("build")
def build_evidence_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
) -> None:
    """Build a versioned evidence-pack JSON document."""

    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    pack = build_evidence_pack(result, collection)
    payload = pack.to_json()
    if output is not None:
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"evidence_pack: {output}")
    else:
        typer.echo(payload)
    if registry is not None:
        Registry(registry).store_evidence_pack(
            pack_id=pack.pack_id,
            run_id=collection.run_id,
            source_fingerprint=collection.input_fingerprint,
            payload_json=payload,
        )
    if not result.report.may_import:
        raise typer.Exit(code=1)


@experiment_app.command("summarise")
def summarise_experiment_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Summarise stored metric collections for one experiment."""

    collections = [
        collection
        for payload in Registry(registry).list_metric_collection_json()
        if (collection := MetricCollection.model_validate_json(payload)).results
        and collection.results[0].experiment_id == experiment_id
    ]
    report = aggregate_experiment(collections)
    if output_format == "json":
        typer.echo(report.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"experiment: {experiment_id}")
    typer.echo(f"conditions: {report.condition_count}")
    for condition in report.conditions:
        typer.echo(f"{condition.condition_id}: runs={condition.run_count}")


@diagnose_app.command("bundle")
def diagnose_bundle_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Evaluate deterministic diagnostics for a bundle."""

    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    pack = build_evidence_pack(result, collection)
    report = evaluate_rules(pack)
    typer.echo(f"run: {collection.run_id}")
    typer.echo(f"report: {report.report_id}")
    typer.echo(f"readiness: {report.overall_readiness.value}")
    typer.echo(f"triggered: {', '.join(report.triggered_rule_ids) or 'none'}")
    typer.echo(f"insufficient: {', '.join(report.insufficient_rule_ids) or 'none'}")
    if not result.report.may_import:
        typer.echo("bundle rejected; ordinary hypotheses are suppressed", err=True)
        raise typer.Exit(code=1)


@diagnose_app.command("evidence")
def diagnose_evidence_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Evaluate deterministic diagnostics for a saved EvidencePack JSON file."""

    pack = EvidencePack.model_validate_json(path.read_text(encoding="utf-8"))
    report = evaluate_rules(pack)
    typer.echo(f"evidence_pack: {pack.pack_id}")
    typer.echo(f"report: {report.report_id}")
    typer.echo(f"readiness: {report.overall_readiness.value}")
    typer.echo(f"triggered: {', '.join(report.triggered_rule_ids) or 'none'}")


@diagnose_app.command("report")
def diagnose_report_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Emit a complete machine-readable DiagnosticReport for a bundle or EvidencePack JSON."""

    if output_format != "json":
        typer.echo("only --format json is supported", err=True)
        raise typer.Exit(code=1)
    report = _diagnostic_report_from_path(path)
    typer.echo(report.to_json())


@diagnose_app.command("evaluate")
def diagnose_evaluate_command(
    fixture_set: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Evaluate labelled synthetic diagnostic fixtures."""

    report = evaluate_fixture_set(load_fixture_set(fixture_set))
    typer.echo(report.to_json())


def _collection_from_identifier(
    identifier: str,
    registry_path: Path | None,
) -> tuple[MetricCollection, ScenarioSeed | None]:
    path = Path(identifier)
    if path.exists():
        result = validate_bundle(path)
        _ensure_metric_context_available(result)
        return compute_metrics_for_bundle(result), result.seed
    if registry_path is None:
        typer.echo(f"path not found and --registry not provided: {identifier}", err=True)
        raise typer.Exit(code=1)
    try:
        payload = Registry(registry_path).get_metric_collection_json(identifier)
    except RegistryNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    return MetricCollection.model_validate_json(payload), None


def _ensure_metric_context_available(result: BundleValidationResult) -> None:
    if result.manifest is None:
        report = result.report
        typer.echo(
            f"bundle rejected: {report.status.value}; manifest is unavailable for metric context",
            err=True,
        )
        raise typer.Exit(code=1)


def _diagnostic_report_from_path(path: Path) -> DiagnosticReport:
    if path.is_file() and path.suffix.lower() == ".json":
        pack = EvidencePack.model_validate_json(path.read_text(encoding="utf-8"))
        return evaluate_rules(pack)
    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    pack = build_evidence_pack(result, collection)
    return evaluate_rules(pack)
