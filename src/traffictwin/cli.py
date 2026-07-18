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
from traffictwin.provenance.markdown import trace_to_markdown
from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.provenance.query import (
    ProvenanceQueryError,
    build_provenance_context,
    export_provenance,
    get_metric_provenance,
    get_rule_provenance,
    get_run_provenance,
    get_source_provenance,
    node_type_counts,
)
from traffictwin.provenance.serialization import trace_to_json
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
provenance_app = typer.Typer(no_args_is_help=True, help="Read-only provenance trace commands.")
app.add_typer(registry_app, name="registry")
app.add_typer(bundle_app, name="bundle")
app.add_typer(metrics_app, name="metrics")
app.add_typer(evidence_app, name="evidence")
app.add_typer(experiment_app, name="experiment")
app.add_typer(diagnose_app, name="diagnose")
app.add_typer(provenance_app, name="provenance")


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


@provenance_app.command("metric")
def provenance_metric_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    metric_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Trace one metric result back to definitions, canonical records, and source rows."""

    try:
        context = build_provenance_context(path)
        trace = get_metric_provenance(context, metric_key)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_provenance_trace(trace, output_format)


@provenance_app.command("rule")
def provenance_rule_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    rule_id: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Trace one diagnostic rule result back to cited metric evidence."""

    try:
        context = build_provenance_context(path)
        trace = get_rule_provenance(context, rule_id)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_provenance_trace(trace, output_format)


@provenance_app.command("run")
def provenance_run_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Trace the run, manifest, validation, metric, and diagnostic context."""

    context = build_provenance_context(path)
    trace = get_run_provenance(context)
    _emit_provenance_trace(trace, output_format)


@provenance_app.command("source")
def provenance_source_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    source_file: Annotated[str, typer.Argument()],
    row: Annotated[int, typer.Argument(min=1)],
    context_rows: Annotated[int, typer.Option("--context-rows", min=0)] = 2,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect one read-only CSV source row inside a bundle."""

    context = build_provenance_context(path)
    preview = get_source_provenance(context, source_file, row, context_rows=context_rows)
    if output_format == "json":
        typer.echo(preview.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"source: {preview.file}:{preview.row_number}")
    typer.echo(f"status: {preview.status.value}")
    typer.echo(f"inclusion_status: {preview.inclusion_status}")
    if preview.canonical_record_type is not None:
        typer.echo(f"canonical_record_type: {preview.canonical_record_type}")
    if preview.validation_findings:
        typer.echo(f"validation_findings: {len(preview.validation_findings)}")
    for warning in preview.warnings:
        typer.echo(f"warning: {warning}")


@provenance_app.command("export")
def provenance_export_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    root_type: Annotated[str, typer.Option("--root-type")],
    root_id: Annotated[str, typer.Option("--root-id")] = "",
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Export a provenance trace as JSON or Markdown."""

    try:
        context = build_provenance_context(path)
        if root_type == "metric":
            trace = get_metric_provenance(context, root_id)
        elif root_type == "rule":
            trace = get_rule_provenance(context, root_id)
        elif root_type == "run":
            trace = get_run_provenance(context)
        else:
            msg = "root-type must be one of: metric, rule, run"
            raise ProvenanceQueryError(msg)
        payload = export_provenance(trace, output_format)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output is not None:
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"provenance_trace: {output}")
    else:
        typer.echo(payload)


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


def _emit_provenance_trace(trace: ProvenanceTrace, output_format: str) -> None:
    if output_format == "json":
        typer.echo(trace_to_json(trace))
        return
    if output_format == "markdown":
        typer.echo(trace_to_markdown(trace))
        return
    if output_format != "text":
        typer.echo("only --format text, json, or markdown is supported", err=True)
        raise typer.Exit(code=1)
    counts = node_type_counts(trace)
    typer.echo(f"trace: {trace.trace_id}")
    typer.echo(f"root: {trace.root_node_id}")
    typer.echo(f"completeness: {trace.completeness.overall.value}")
    typer.echo(f"synthetic: {trace.synthetic}")
    typer.echo(f"nodes: {len(trace.nodes)}")
    typer.echo(f"edges: {len(trace.edges)}")
    typer.echo("node_types:")
    for key in sorted(counts):
        typer.echo(f"  {key}: {counts[key]}")
    for warning in trace.warnings:
        typer.echo(f"warning: {warning}")
