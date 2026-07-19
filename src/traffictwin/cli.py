"""Command-line interface for Phase 1 TrafficTwin workflows."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
import yaml

from traffictwin.config.capabilities import default_export_import_manifest, manifest_to_plain_dict
from traffictwin.config.seed_io import SeedIOError, load_seed, normalise_seed_file
from traffictwin.demo.launcher import launch_workspace
from traffictwin.demo.workspace import initialise_workspace, reset_workspace, workspace_status
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.experiments.protocol import (
    ExperimentProtocol,
    ProtocolMatchStatus,
    build_experiment_protocol,
    match_bundle_manifest,
    protocol_to_csv,
    protocol_to_yaml,
)
from traffictwin.ingestion.bundle import BundleValidationResult, inspect_bundle, validate_bundle
from traffictwin.ingestion.bundle import import_bundle as import_run_bundle
from traffictwin.integration.tos import (
    TosEvaluationRun,
    audit_tos_package,
    build_evaluation_matrix,
    build_generalisation_matrix,
    build_static_results_atlas,
    build_tos_evidence_pack,
    build_tos_integration_readiness,
    build_tos_metric_trace,
    build_tos_research_report,
    build_tos_rule_trace,
    compare_campaigns,
    import_evaluation_summaries,
    list_instrumented_runs,
    list_training_runs,
    load_replay_frame,
    load_rsu_replay_series,
    load_task_sample,
    load_training_run,
    metric_collection_from_evaluation,
    read_evaluation_runs,
    stage_public_tos_atlas,
    summarise_rsu_run,
    summarise_task_outcomes,
    summarise_trace,
    tos_source_contract,
    validate_tos_package,
    write_tos_results_pack,
    write_tos_supervisor_pack,
)
from traffictwin.integration.tos.readers import TosPackageError, instrumented_key_for_run
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
from traffictwin.release import current_release_metadata, stage_synthetic_demo_site
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.models import ReportBuildError, ResearchReport
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.evaluation import evaluate_fixture_set, load_fixture_set
from traffictwin.storage.registry import Registry, RegistryConflictError, RegistryNotFoundError
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.experiments import generate_trivial_multi_algorithm_experiment
from traffictwin.synthetic.scenarios import list_preset_names, preset_config
from traffictwin.synthetic.validation import verify_synthetic_path

app = typer.Typer(no_args_is_help=True, help="TrafficTwin research-software CLI.")
registry_app = typer.Typer(no_args_is_help=True, help="Metadata registry commands.")
bundle_app = typer.Typer(no_args_is_help=True, help="Run-bundle commands.")
metrics_app = typer.Typer(no_args_is_help=True, help="Deterministic metric commands.")
evidence_app = typer.Typer(no_args_is_help=True, help="Evidence-pack commands.")
experiment_app = typer.Typer(
    no_args_is_help=True,
    help="Experiment planning, protocol, and aggregation commands.",
)
diagnose_app = typer.Typer(no_args_is_help=True, help="Deterministic diagnostic commands.")
provenance_app = typer.Typer(no_args_is_help=True, help="Read-only provenance trace commands.")
synthetic_app = typer.Typer(no_args_is_help=True, help="Standalone synthetic fixture commands.")
demo_app = typer.Typer(no_args_is_help=True, help="Standalone demo workspace commands.")
report_app = typer.Typer(no_args_is_help=True, help="Deterministic research-report export.")
release_app = typer.Typer(no_args_is_help=True, help="Release and deployment-readiness commands.")
integration_app = typer.Typer(no_args_is_help=True, help="Evidence-gated external data tools.")
tos_app = typer.Typer(no_args_is_help=True, help="Read-only TOS Data package tools.")
app.add_typer(registry_app, name="registry")
app.add_typer(bundle_app, name="bundle")
app.add_typer(metrics_app, name="metrics")
app.add_typer(evidence_app, name="evidence")
app.add_typer(experiment_app, name="experiment")
app.add_typer(diagnose_app, name="diagnose")
app.add_typer(provenance_app, name="provenance")
app.add_typer(synthetic_app, name="synthetic")
app.add_typer(demo_app, name="demo")
app.add_typer(report_app, name="report")
app.add_typer(release_app, name="release")
app.add_typer(integration_app, name="integration")
integration_app.add_typer(tos_app, name="tos")


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


@experiment_app.command("protocol")
def export_experiment_protocol_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    output_format: Annotated[str, typer.Option("--format")] = "yaml",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Export a registered experiment as a deterministic YAML or CSV protocol."""

    try:
        protocol = _registered_experiment_protocol(registry, experiment_id)
    except (RegistryNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "yaml":
        payload = protocol_to_yaml(protocol)
    elif output_format == "csv":
        payload = protocol_to_csv(protocol)
    else:
        typer.echo("only --format yaml or --format csv is supported", err=True)
        raise typer.Exit(code=1)
    if output is None:
        typer.echo(payload, nl=False)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    typer.echo(f"protocol: {protocol.protocol_id}")
    typer.echo(f"run_slots: {len(protocol.slots)}")
    typer.echo(f"output: {output}")


@experiment_app.command("match-bundle")
def match_experiment_bundle_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Validate and match a completed bundle to a registered protocol slot."""

    try:
        protocol = _registered_experiment_protocol(registry, experiment_id)
    except (RegistryNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    validation = validate_bundle(path)
    if validation.manifest is None or not validation.report.may_import:
        typer.echo("bundle rejected; protocol matching was not performed", err=True)
        for validation_finding in validation.report.findings:
            typer.echo(f"{validation_finding.code.value}: {validation_finding.message}", err=True)
        raise typer.Exit(code=1)
    match = match_bundle_manifest(protocol, validation.manifest)
    if output_format == "json":
        typer.echo(match.to_json())
    elif output_format == "text":
        typer.echo(f"protocol: {match.protocol_id}")
        typer.echo(f"bundle: {match.bundle_id}")
        typer.echo(f"run: {match.run_id}")
        typer.echo(f"status: {match.status.value}")
        typer.echo(f"slot: {match.matched_slot_id or 'none'}")
        for match_finding in match.findings:
            typer.echo(f"finding: {match_finding}")
        for mismatch in match.mismatches:
            typer.echo(
                f"mismatch: {mismatch.field} expected={mismatch.expected!r} "
                f"observed={mismatch.observed!r}"
            )
    else:
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    if match.status not in {ProtocolMatchStatus.EXACT, ProtocolMatchStatus.COMPATIBLE}:
        raise typer.Exit(code=1)


def _registered_experiment_protocol(
    registry_path: Path,
    experiment_id: str,
) -> ExperimentProtocol:
    registry = Registry(registry_path)
    experiment = registry.get_experiment(experiment_id)
    seeds = {seed.seed_id: seed for seed in registry.list_seeds()}
    return build_experiment_protocol(experiment, seeds)


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


@synthetic_app.command("presets")
def synthetic_presets_command() -> None:
    """List standalone synthetic scenario presets."""

    for name in list_preset_names():
        typer.echo(name)


@synthetic_app.command("generate-preset")
def synthetic_generate_preset_command(
    name: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    random_seed: Annotated[int, typer.Option("--seed", min=0)] = 7,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Generate one deterministic synthetic run bundle."""

    try:
        config = preset_config(name, random_seed=random_seed)
        destination = write_synthetic_bundle(config, output, overwrite=overwrite)
    except (ValueError, FileExistsError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    result = validate_bundle(destination)
    typer.echo(f"bundle: {destination}")
    typer.echo(f"status: {result.report.status.value}")
    synthetic = result.manifest.environment.name == "synthetic" if result.manifest else False
    typer.echo(f"synthetic: {synthetic}")
    if not result.report.may_import:
        raise typer.Exit(code=1)


@synthetic_app.command("experiment-generate-preset")
def synthetic_experiment_generate_preset_command(
    name: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    seeds: Annotated[str, typer.Option("--seeds")] = "1,2,3",
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Generate a deterministic multi-seed synthetic experiment."""

    if name != "trivial_multi_algorithm":
        typer.echo("only trivial_multi_algorithm is supported for multi-seed generation", err=True)
        raise typer.Exit(code=1)
    try:
        seed_values = _parse_seed_list(seeds)
        paths = generate_trivial_multi_algorithm_experiment(
            output,
            random_seeds=seed_values,
            overwrite=overwrite,
        )
    except (ValueError, FileExistsError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"experiment: {name}")
    typer.echo(f"bundles: {len(paths)}")
    for path in paths:
        typer.echo(path)


@synthetic_app.command("verify")
def synthetic_verify_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Verify synthetic bundle labels and validation status."""

    result = verify_synthetic_path(path)
    typer.echo(f"path: {result.path}")
    typer.echo(f"checked: {result.checked_bundle_count}")
    typer.echo(f"accepted: {result.accepted_bundle_count}")
    typer.echo(f"rejected: {result.rejected_bundle_count}")
    for message in result.messages:
        typer.echo(message)
    if not result.ok:
        raise typer.Exit(code=1)


@demo_app.command("initialise")
def demo_initialise_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Create a reproducible standalone demo workspace."""

    try:
        result = initialise_workspace(path, force=force)
    except (FileExistsError, ValueError, PermissionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("TrafficTwin standalone demo workspace initialised.")
    typer.echo("Synthetic data only; no Randy, SUMO, or live Manchester data is used.")
    typer.echo(f"workspace: {result.path}")
    typer.echo(f"registry: {result.registry_path}")
    typer.echo(f"bundles: {result.bundle_count}")
    typer.echo(f"imported_runs: {result.imported_run_count}")
    typer.echo(f"manifest: {result.manifest_path}")


@demo_app.command("reset")
def demo_reset_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
    yes: Annotated[bool, typer.Option("--yes")] = False,
) -> None:
    """Reset a marked standalone demo workspace."""

    try:
        result = reset_workspace(path, yes=yes)
    except (FileNotFoundError, ValueError, PermissionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"workspace reset: {result.path}")
    typer.echo(f"imported_runs: {result.imported_run_count}")


@demo_app.command("status")
def demo_status_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
) -> None:
    """Inspect a standalone demo workspace."""

    status = workspace_status(path)
    typer.echo(f"workspace: {status.path}")
    typer.echo(f"exists: {status.exists}")
    typer.echo(f"valid_workspace: {status.valid_workspace}")
    typer.echo(f"registry: {status.registry_path}")
    typer.echo(f"scenarios: {status.scenario_count}")
    typer.echo(f"imported_runs: {status.imported_run_count}")
    typer.echo(f"reports: {status.report_count}")
    typer.echo(f"comparisons: {status.comparison_count}")
    typer.echo(f"diagnostics: {status.diagnostics_status}")
    typer.echo("synthetic: true")
    for message in status.messages:
        typer.echo(f"warning: {message}")
    if not status.valid_workspace:
        raise typer.Exit(code=1)


@demo_app.command("launch")
def demo_launch_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Initialise if needed and launch the Streamlit demo UI."""

    try:
        plan = launch_workspace(path, dry_run=dry_run)
    except (FileExistsError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("TrafficTwin standalone demo uses synthetic fixture data only.")
    typer.echo(f"workspace: {plan.workspace}")
    typer.echo(f"registry: {plan.registry}")
    typer.echo("command: " + " ".join(plan.command))
    if dry_run:
        typer.echo("dry_run: true")


@report_app.command("run")
def report_run_command(
    path_or_run: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Export a deterministic single-run report."""

    _write_report(build_run_report, path_or_run, output)


@report_app.command("compare")
def report_compare_command(
    baseline: Annotated[Path, typer.Argument(exists=True, readable=True)],
    variation: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Export a deterministic baseline-versus-variation report."""

    try:
        report = build_comparison_report(baseline, variation)
    except ReportBuildError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _write_report_payload(report, output)


@report_app.command("diagnostics")
def report_diagnostics_command(
    path_or_run: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Export a deterministic diagnostic report summary."""

    _write_report(build_diagnostics_report, path_or_run, output)


@report_app.command("full")
def report_full_command(
    path_or_run: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    comparison_baseline: Annotated[
        Path | None,
        typer.Option("--comparison-baseline", exists=True, readable=True),
    ] = None,
) -> None:
    """Export a deterministic full report as Markdown or standalone HTML."""

    try:
        report = build_full_report(path_or_run, comparison_baseline=comparison_baseline)
    except ReportBuildError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _write_report_payload(report, output)


@release_app.command("status")
def release_status_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show release, licence, and supported deployment modes."""

    metadata = current_release_metadata()
    payload = {
        **metadata.model_dump(mode="json"),
        "deployment_modes": {
            "synthetic_static_site": "supported",
            "standalone_streamlit_container": "supported",
            "public_tos_atlas": "permission_gated",
            "direct_environment_launch": "unsupported",
            "live_data": "unsupported",
        },
    }
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
        return
    _require_text_format(output_format)
    typer.echo(f"version: {metadata.version}")
    typer.echo(f"release: {metadata.release_label}")
    typer.echo(f"licence: {metadata.licence_status}")
    typer.echo(f"status: {metadata.production_status}")
    for mode, state in payload["deployment_modes"].items():
        typer.echo(f"{mode}: {state}")


@release_app.command("stage-demo-site")
def release_stage_demo_site_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    overwrite: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Stage a Netlify-compatible synthetic-only static demonstration."""

    try:
        manifest = stage_synthetic_demo_site(workspace, output, overwrite=overwrite)
    except (FileExistsError, OSError, PermissionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"site: {output}")
    typer.echo(f"scenarios: {len(manifest.scenarios)}")
    typer.echo("synthetic: true")
    typer.echo("live_data: false")
    typer.echo(f"licence: {manifest.licence_status}")


@tos_app.command("inspect")
def tos_inspect_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    deep: Annotated[bool, typer.Option("--deep/--shallow")] = False,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect TOS artifacts without registry mutation."""

    report = validate_tos_package(path, deep=deep)
    if output_format == "json":
        typer.echo(report.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    inventory = report.inventory
    typer.echo(f"status: {report.status.value}")
    typer.echo(f"may_import_summaries: {report.may_import_summaries}")
    typer.echo(f"package_fingerprint: {report.package_fingerprint or 'unavailable'}")
    typer.echo(f"package_commit: {report.package_commit or 'unavailable'}")
    typer.echo(f"evaluation_rows: {inventory.evaluation_rows}")
    typer.echo(f"perstep_files: {inventory.perstep_files}")
    typer.echo(f"pertask_files: {inventory.pertask_files}")
    typer.echo(f"trace_files: {inventory.trace_files}")
    for finding in report.findings:
        typer.echo(f"{finding.severity.value}: {finding.code}: {finding.message}")


@tos_app.command("contract")
def tos_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the evidence-backed vec_env field, control, and execution contract."""

    contract = tos_source_contract()
    if output_format == "json":
        typer.echo(contract.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"adapter_version: {contract.adapter_version}")
    typer.echo(f"semantics_evidence_commit: {contract.evidence_commit}")
    typer.echo(f"direct_launch: {contract.execution.direct_launch.value}")
    typer.echo(f"execution_status: {contract.execution.status.value}")
    typer.echo("confirmed_fields:")
    for field in contract.fields:
        typer.echo(f"  {field.field}: {field.meaning} [{field.unit or 'no unit'}]")
    typer.echo("launch_blockers:")
    for blocker in contract.execution.blockers:
        typer.echo(f"  - {blocker}")


@tos_app.command("validate")
def tos_validate_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Deep-validate the documented TOS package contracts."""

    report = validate_tos_package(path, deep=True)
    if output_format == "json":
        typer.echo(report.to_json())
    elif output_format == "text":
        typer.echo(f"status: {report.status.value}")
        typer.echo(f"may_import_summaries: {report.may_import_summaries}")
        typer.echo(f"findings: {len(report.findings)}")
        for finding in report.findings:
            typer.echo(f"{finding.severity.value}: {finding.code}: {finding.message}")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    if not report.may_import_summaries:
        raise typer.Exit(code=1)


@tos_app.command("runs")
def tos_runs_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 25,
) -> None:
    """List documented evaluation runs and instrumented run availability."""

    rows = read_evaluation_runs(path)
    instrumented = set(list_instrumented_runs(path))
    typer.echo(f"evaluation_runs: {len(rows)}")
    typer.echo(f"instrumented_runs: {len(instrumented)}")
    for row in rows[:limit]:
        instrumented_key = instrumented_key_for_run(row)
        instrumented_available = instrumented_key in instrumented
        instrumented_reference = (
            f" instrumented_key={instrumented_key}" if instrumented_available else ""
        )
        typer.echo(
            f"{row.run_id} completion={row.completion:.6f} "
            f"instrumented={instrumented_available}{instrumented_reference}"
        )


@tos_app.command("import")
def tos_import_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False, writable=True)],
) -> None:
    """Import validated source summaries into the TrafficTwin registry."""

    try:
        report = validate_tos_package(path, deep=True)
        result = import_evaluation_summaries(
            path,
            registry,
            validation_report=report,
        )
    except (TosPackageError, RegistryConflictError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"registry: {result.registry_reference}")
    typer.echo(f"experiments_created: {result.experiments_created}")
    typer.echo(f"experiments_existing: {result.experiments_existing}")
    typer.echo(f"runs_created: {result.runs_created}")
    typer.echo(f"runs_existing: {result.runs_existing}")
    typer.echo(f"metric_collections_stored: {result.metric_collections_stored}")
    typer.echo(f"evidence_packs_stored: {result.evidence_packs_stored}")


@tos_app.command("metrics")
def tos_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_id: Annotated[str, typer.Argument(help="TrafficTwin run ID or source artifact key")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect explicitly source-provided metrics for one evaluation run."""

    report = validate_tos_package(path, deep=False)
    row = _tos_row(path, run_id)
    if report.package_fingerprint is None:
        typer.echo("package fingerprint unavailable", err=True)
        raise typer.Exit(code=1)
    collection = metric_collection_from_evaluation(row, report.package_fingerprint)
    if output_format == "json":
        typer.echo(collection.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run: {row.run_id}")
    typer.echo(f"metric_version: {collection.metric_version}")
    for key in (
        "tos.task.deadline_success.rate",
        "tos.task.deadline_success.rate_by_class",
        "task.latency.mean_ms",
        "task.offload.rate",
    ):
        metric = collection.by_key()[key]
        typer.echo(f"{key}: {metric.value}")
    typer.echo(f"unavailable_metrics: {collection.unavailable_count}")


@tos_app.command("replay")
def tos_replay_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    index: Annotated[int, typer.Option("--index", min=0)] = 0,
    max_vehicles: Annotated[int, typer.Option("--max-vehicles", min=1, max=1000)] = 25,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect one deterministic historical replay frame."""

    try:
        frame = load_replay_frame(path, run_key, index, max_vehicles=max_vehicles)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(frame.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run_key: {frame.run_key}")
    typer.echo(f"time: {frame.point.timestamp_s}")
    typer.echo(f"arrivals: {frame.point.arrivals}")
    typer.echo(f"deadline_met: {frame.point.deadline_met}")
    typer.echo(f"active_vehicle_slots: {frame.total_active_vehicle_slots}")
    typer.echo(f"displayed_vehicle_slots: {len(frame.vehicles)}")
    typer.echo(f"rsu_source_rows: {len(frame.rsus)}")


@tos_app.command("rsu-series")
def tos_rsu_series_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    stride: Annotated[int, typer.Option("--stride", min=1)] = 1,
    limit: Annotated[int, typer.Option("--limit", min=1, max=10000)] = 250,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect bounded RSU active-task pressure and compute backlog history."""

    try:
        points = load_rsu_replay_series(path, run_key, stride=stride)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    selected = points[:limit]
    if output_format == "json":
        typer.echo(
            json.dumps(
                [point.model_dump(mode="json") for point in selected],
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run_key: {run_key}")
    typer.echo(f"total_points: {len(points)}")
    typer.echo(f"displayed_points: {len(selected)}")
    typer.echo("pressure_semantics: in_flight_tasks / maximum_concurrent_tasks")
    typer.echo("warning: concurrency pressure is not CPU utilisation")
    for point in selected:
        typer.echo(
            f"t={point.timestamp_s:g} {point.rsu_reference} "
            f"active={point.active_task_count} backlog_ms="
            f"{point.remaining_compute_backlog_ms:g} "
            f"pressure={point.concurrency_pressure_fraction:.6f}"
        )


@tos_app.command("task-sample")
def tos_task_sample_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    limit: Annotated[int, typer.Option("--limit", min=1, max=10000)] = 25,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect a bounded per-arrival showcase sample."""

    try:
        sample = load_task_sample(path, run_key, limit=limit)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(sample.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run_key: {sample.run_key}")
    typer.echo(f"active_entries: {sample.total_active_entries}")
    typer.echo(f"sampled_entries: {len(sample.observations)}")
    typer.echo(f"deadline_consistency_verified: {sample.deadline_consistency_verified}")
    for observation in sample.observations:
        typer.echo(
            f"{observation.source_index} {observation.task_class.value} "
            f"deadline_met={observation.deadline_met} latency_ms={observation.latency_ms:.3f}"
        )


@tos_app.command("diagnose")
def tos_diagnose_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_id: Annotated[str, typer.Argument(help="TrafficTwin run ID or source artifact key")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Evaluate existing rules over an explicitly partial TOS EvidencePack."""

    report = validate_tos_package(path, deep=False)
    row = _tos_row(path, run_id)
    if report.package_fingerprint is None:
        typer.echo("package fingerprint unavailable", err=True)
        raise typer.Exit(code=1)
    collection = metric_collection_from_evaluation(row, report.package_fingerprint)
    pack = build_tos_evidence_pack(row, report, collection)
    diagnosis = evaluate_rules(pack)
    if output_format == "json":
        typer.echo(diagnosis.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run: {row.run_id}")
    typer.echo(f"readiness: {diagnosis.overall_readiness.value}")
    for result in diagnosis.results:
        typer.echo(f"{result.rule_id}: {result.status.value}")


@tos_app.command("provenance")
def tos_provenance_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_id: Annotated[str, typer.Argument(help="TrafficTwin run ID or source artifact key")],
    root_type: Annotated[str, typer.Option("--root-type")] = "metric",
    root_id: Annotated[str, typer.Option("--root-id")] = "tos.task.deadline_success.rate",
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Export aggregate-level metric or rule provenance for a TOS run."""

    report = validate_tos_package(path, deep=False)
    row = _tos_row(path, run_id)
    if report.package_fingerprint is None:
        typer.echo("package fingerprint unavailable", err=True)
        raise typer.Exit(code=1)
    collection = metric_collection_from_evaluation(row, report.package_fingerprint)
    if root_type == "metric":
        trace = build_tos_metric_trace(row, collection, report, root_id)
    elif root_type == "rule":
        pack = build_tos_evidence_pack(row, report, collection)
        diagnosis = evaluate_rules(pack)
        trace = build_tos_rule_trace(row, pack, diagnosis, report, root_id)
    else:
        typer.echo("--root-type must be metric or rule", err=True)
        raise typer.Exit(code=1)
    _emit_provenance_trace(trace, output_format)


@tos_app.command("matrix")
def tos_matrix_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    measure: Annotated[str, typer.Option("--measure")] = "tos.task.deadline_success.rate",
    fleet: Annotated[str, typer.Option("--fleet")] = "uk2030",
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Build the deterministic source evaluation matrix."""

    try:
        matrix = build_evaluation_matrix(
            read_evaluation_runs(path), path, measure_key=measure, evaluation_fleet=fleet
        )
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(matrix.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"measure: {matrix.measure.key}")
    typer.echo(f"evaluation_fleet: {matrix.evaluation_fleet}")
    typer.echo(f"campaigns: {len(matrix.campaigns)}")
    typer.echo(f"cells: {len(matrix.cells)}")
    for entry in matrix.entries:
        typer.echo(
            f"{entry.campaign} {entry.cell} n={entry.statistics.n} "
            f"mean={_optional_number(entry.statistics.mean)} "
            f"sample_sd={_optional_number(entry.statistics.sample_sd)}"
        )


@tos_app.command("compare-campaigns")
def tos_compare_campaigns_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    baseline: Annotated[str, typer.Argument()],
    variation: Annotated[str, typer.Argument()],
    measure: Annotated[str, typer.Option("--measure")] = "tos.task.deadline_success.rate",
    fleet: Annotated[str, typer.Option("--fleet")] = "uk2030",
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Compare two campaigns using common fleet seeds within each source cell."""

    try:
        report = compare_campaigns(
            read_evaluation_runs(path),
            path,
            baseline,
            variation,
            evaluation_fleet=fleet,
            measure_keys=[measure],
        )
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(report.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"comparison: {baseline} -> {variation}")
    typer.echo("delta_definition: variation - baseline")
    for item in report.comparisons:
        typer.echo(
            f"{item.cell} paired_n={item.paired_difference_statistics.n} "
            f"mean_delta={_optional_number(item.paired_difference_statistics.mean)}"
        )


@tos_app.command("generalisation")
def tos_generalisation_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show evidenced in-domain, held-out, and unknown source relationships."""

    matrix = build_generalisation_matrix(read_evaluation_runs(path), path)
    if output_format == "json":
        typer.echo(matrix.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    for entry in matrix.entries:
        typer.echo(f"{entry.campaign} {entry.cell}: {entry.evaluation_domain.value}")


@tos_app.command("training-runs")
def tos_training_runs_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 100,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """List source training histories and matched greedy summaries."""

    runs = list_training_runs(path)[:limit]
    if output_format == "json":
        typer.echo(
            json.dumps(
                [run.model_dump(mode="json") for run in runs],
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return
    _require_text_format(output_format)
    typer.echo(f"training_runs: {len(runs)}")
    for run in runs:
        typer.echo(
            f"{run.training_id} points={run.point_count} "
            f"final_completion={_optional_number(run.final_mean_completion)}"
        )


@tos_app.command("training")
def tos_training_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    training_id: Annotated[str, typer.Argument()],
    max_points: Annotated[int, typer.Option("--max-points", min=2, max=10000)] = 800,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect one bounded source training curve."""

    try:
        run = load_training_run(path, training_id, max_points=max_points)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(run.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"training_id: {run.summary.training_id}")
    typer.echo(f"source_points: {run.summary.point_count}")
    typer.echo(f"displayed_points: {len(run.points)}")
    typer.echo(f"warmup_unavailable: {run.summary.warmup_unavailable_count}")
    typer.echo(f"greedy_summary: {run.greedy_evaluation is not None}")


@tos_app.command("trace-summary")
def tos_trace_summary_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    trace_name: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Summarise a processed FCD mobility trace."""

    try:
        summary = summarise_trace(path, trace_name)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(summary.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"trace: {summary.trace_file}")
    typer.echo(f"timeline_points: {summary.timeline_point_count}")
    typer.echo(f"active_slot_observations: {summary.observation_count}")
    typer.echo(f"mean_speed_mps: {_optional_number(summary.speed_mps.mean)}")
    typer.echo("warning: processed SUMO FCD simulation; no trip outputs")


@tos_app.command("rsu-summary")
def tos_rsu_summary_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Summarise source RSU concurrency pressure and compute backlog."""

    try:
        summary = summarise_rsu_run(path, run_key)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(summary.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"run_key: {summary.run_key}")
    typer.echo(f"rsus: {len(summary.rsus)}")
    typer.echo(f"maximum_concurrent_tasks: {summary.maximum_concurrent_tasks}")
    for rsu in summary.rsus:
        typer.echo(
            f"{rsu.rsu_reference} mean_pressure="
            f"{_optional_number(rsu.concurrency_pressure_fraction.mean)} "
            f"max_pressure={_optional_number(rsu.concurrency_pressure_fraction.maximum)}"
        )


@tos_app.command("task-summary")
def tos_task_summary_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Aggregate one complete per-task showcase array."""

    try:
        summary = summarise_task_outcomes(path, run_key)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(summary.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"run_key: {summary.run_key}")
    typer.echo(f"tasks: {summary.task_count}")
    typer.echo(f"deadline_success_rate: {_optional_number(summary.deadline_success_rate)}")
    typer.echo(f"latency_p50_ms: {_optional_number(summary.latency_ms.p50)}")
    typer.echo(f"deadline_consistency_verified: {summary.deadline_consistency_verified}")


@tos_app.command("audit")
def tos_audit_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Audit package reproducibility and artifact coverage."""

    audit = audit_tos_package(path)
    if output_format == "json":
        typer.echo(audit.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"package_fingerprint: {audit.package_fingerprint}")
    typer.echo(f"evaluation_runs: {audit.evaluation_run_count}")
    typer.echo(f"training_histories: {audit.training_history_count}")
    for check in audit.checks:
        typer.echo(f"{check.status.value}: {check.code}: {check.message}")


@tos_app.command("readiness")
def tos_readiness_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
    fixture_permission_confirmed: Annotated[
        bool, typer.Option("--confirm-fixture-permission")
    ] = False,
    publication_permission_confirmed: Annotated[
        bool, typer.Option("--confirm-publication-permission")
    ] = False,
) -> None:
    """Report evidence and permission gates for deeper TOS integration."""

    readiness = build_tos_integration_readiness(
        path,
        fixture_permission=True if fixture_permission_confirmed else None,
        publication_permission=True if publication_permission_confirmed else None,
    )
    if output_format == "json":
        typer.echo(readiness.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"overall_status: {readiness.overall_status.value}")
    typer.echo(f"package_fingerprint: {readiness.package_fingerprint}")
    for capability, status in sorted(readiness.capabilities.items()):
        typer.echo(f"{capability}: {status.value}")
    for gate in readiness.gates:
        typer.echo(f"{gate.status.value}: {gate.gate_id}: {gate.title}")


@tos_app.command("report")
def tos_report_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    variation: Annotated[str, typer.Option("--variation")] = "ukfleettrain_mappo",
) -> None:
    """Write a deterministic imported-simulation research report."""

    report = build_tos_research_report(path, variation_campaign=variation)
    _write_report_payload(report, output)


@tos_app.command("atlas")
def tos_atlas_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Write a self-contained aggregate-only static results atlas."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_static_results_atlas(path), encoding="utf-8")
    typer.echo(f"atlas: {output}")
    typer.echo("publication_permission_required: true")


@tos_app.command("results-pack")
def tos_results_pack_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    variation: Annotated[str, typer.Option("--variation")] = "ukfleettrain_mappo",
) -> None:
    """Write report, matrix, comparison, audit, and static atlas artifacts."""

    try:
        pack = write_tos_results_pack(path, output, variation_campaign=variation)
    except (FileExistsError, TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"results_pack: {pack.directory}")
    typer.echo(f"report: {pack.markdown_report.name}")
    typer.echo(f"atlas: {pack.atlas_html.name}")
    typer.echo("publication_permission_required: true")


@tos_app.command("supervisor-pack")
def tos_supervisor_pack_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    variation: Annotated[str, typer.Option("--variation")] = "ukfleettrain_mappo",
) -> None:
    """Write a checksummed private supervisor and viva evidence pack."""

    try:
        pack = write_tos_supervisor_pack(path, output, variation_campaign=variation)
    except (FileExistsError, OSError, PermissionError, TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"supervisor_pack: {pack.directory}")
    typer.echo(f"manifest: {pack.manifest.name}")
    typer.echo(f"checksums: {pack.checksums.name}")
    typer.echo("classification: private_research_material")
    typer.echo("publication_permission_required: true")


@tos_app.command("stage-public-atlas")
def tos_stage_public_atlas_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    publication_permission_confirmed: Annotated[
        bool, typer.Option("--confirm-publication-permission")
    ] = False,
) -> None:
    """Stage the aggregate TOS atlas after explicit publication permission."""

    try:
        index = stage_public_tos_atlas(
            path,
            output,
            publication_permission_confirmed=publication_permission_confirmed,
        )
    except (FileExistsError, OSError, PermissionError, TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"public_atlas: {index}")
    typer.echo("publication_permission_attested: true")


def _require_text_format(output_format: str) -> None:
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)


def _optional_number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6f}"


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


def _tos_row(path: Path, identifier: str) -> TosEvaluationRun:
    rows = read_evaluation_runs(path)
    for row in rows:
        if identifier in {row.run_id, row.source_key, instrumented_key_for_run(row)}:
            return row
    typer.echo(f"TOS evaluation run not found: {identifier}", err=True)
    raise typer.Exit(code=1)


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


def _parse_seed_list(value: str) -> list[int]:
    seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not seeds:
        msg = "at least one seed is required"
        raise ValueError(msg)
    if any(seed < 0 for seed in seeds):
        msg = "seeds must be non-negative integers"
        raise ValueError(msg)
    return seeds


def _write_report(
    builder: Callable[[str | Path], ResearchReport],
    path: Path,
    output: Path,
) -> None:
    try:
        report = builder(path)
    except ReportBuildError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _write_report_payload(report, output)


def _write_report_payload(report: ResearchReport, output: Path) -> None:
    payload = (
        report_to_html(report) if output.suffix.lower() == ".html" else report_to_markdown(report)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    typer.echo(f"report: {output}")
