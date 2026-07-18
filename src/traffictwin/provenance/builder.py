"""Build read-only provenance traces from existing TrafficTwin artifacts."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from pydantic import BaseModel

from traffictwin.canonical.records import CanonicalRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.ingestion.manifest import BundleManifest, FileDeclaration
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.definitions import MetricDefinition
from traffictwin.metrics.results import JsonValue, MetricCollection, MetricStatus, MetricValue
from traffictwin.provenance.graph import TraceGraph
from traffictwin.provenance.models import (
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    ProvenanceStatus,
    ProvenanceTrace,
    ReferenceConfidence,
    SourceReference,
    TraceCompleteness,
    TraceCompletenessSummary,
)
from traffictwin.rules.catalogue import RuleDefinition, rule_catalogue
from traffictwin.rules.models import Finding, FindingSupport, RuleResult, RuleStatus
from traffictwin.validation.findings import ValidationFinding

Clock = Callable[[], datetime]
DEFAULT_SAMPLE_LIMIT = 25


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def build_run_trace(
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection | None = None,
    evidence_pack: EvidencePack | None = None,
    diagnostic_report: DiagnosticReport | None = None,
    *,
    root: str | None = None,
    clock: Clock = utc_now,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> ProvenanceTrace:
    """Build a trace rooted at a run or another requested node id."""

    generated_at = clock()
    graph = TraceGraph()
    warnings: list[str] = []
    run_node_id = _add_run_context(graph, bundle_result, evidence_pack)
    if metric_collection is not None:
        _add_metric_collection_summary(
            graph,
            run_node_id,
            bundle_result,
            metric_collection,
            sample_limit=sample_limit,
            warnings=warnings,
        )
    if diagnostic_report is not None:
        report_node_id = _add_diagnostic_report_node(graph, diagnostic_report)
        graph.add_edge(
            report_node_id,
            run_node_id,
            ProvenanceRelation.GENERATED_FROM,
            description="Diagnostic report was generated from the run evidence pack.",
        )
    root_node_id = root or run_node_id
    completeness = _completeness_for_trace(
        bundle_result=bundle_result,
        metric_collection=metric_collection,
        diagnostic_report=diagnostic_report,
        required_tables=[],
        root_available=graph.has_node(root_node_id),
    )
    return graph.to_trace(
        root_node_id=root_node_id,
        generated_at=generated_at,
        source_fingerprint=bundle_result.fingerprint,
        synthetic=_is_synthetic(bundle_result),
        completeness=completeness,
        warnings=warnings,
    )


def build_metric_trace(
    metric_key: str,
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection,
    evidence_pack: EvidencePack | None = None,
    diagnostic_report: DiagnosticReport | None = None,
    *,
    clock: Clock = utc_now,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> ProvenanceTrace:
    """Build a trace rooted at one metric result."""

    generated_at = clock()
    graph = TraceGraph()
    warnings: list[str] = []
    run_node_id = _add_run_context(graph, bundle_result, evidence_pack)
    if diagnostic_report is not None:
        report_node_id = _add_diagnostic_report_node(graph, diagnostic_report)
        graph.add_edge(
            report_node_id,
            run_node_id,
            ProvenanceRelation.GENERATED_FROM,
            description="Diagnostic report was generated from the run evidence pack.",
        )
    metric_node_id = _add_metric_lineage(
        graph,
        metric_key,
        bundle_result,
        metric_collection,
        parent_node_id=run_node_id,
        parent_relation=ProvenanceRelation.CONTAINS,
        sample_limit=sample_limit,
        warnings=warnings,
    )
    definition = metric_catalogue().get(metric_key)
    required_tables = definition.required_tables if definition is not None else []
    completeness = _completeness_for_trace(
        bundle_result=bundle_result,
        metric_collection=metric_collection,
        diagnostic_report=diagnostic_report,
        required_tables=required_tables,
        root_available=True,
    )
    return graph.to_trace(
        root_node_id=metric_node_id,
        generated_at=generated_at,
        source_fingerprint=bundle_result.fingerprint,
        synthetic=_is_synthetic(bundle_result),
        completeness=completeness,
        warnings=warnings,
    )


def build_rule_trace(
    rule_id: str,
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection,
    evidence_pack: EvidencePack,
    diagnostic_report: DiagnosticReport,
    *,
    clock: Clock = utc_now,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> ProvenanceTrace:
    """Build a trace rooted at one diagnostic rule result."""

    generated_at = clock()
    graph = TraceGraph()
    warnings: list[str] = []
    _add_run_context(graph, bundle_result, evidence_pack)
    report_node_id = _add_diagnostic_report_node(graph, diagnostic_report)
    result = next((item for item in diagnostic_report.results if item.rule_id == rule_id), None)
    if result is None:
        root_node_id = f"unavailable:rule:{rule_id}"
        graph.add_node(
            _node(
                root_node_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                f"Rule {rule_id}",
                status=ProvenanceStatus.UNAVAILABLE,
                description="The requested rule result is not present in this DiagnosticReport.",
                synthetic=diagnostic_report.synthetic,
            )
        )
        graph.add_edge(
            report_node_id,
            root_node_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
    else:
        root_node_id = _add_rule_result_lineage(
            graph,
            result,
            bundle_result,
            metric_collection,
            diagnostic_report,
            parent_node_id=report_node_id,
            sample_limit=sample_limit,
            warnings=warnings,
        )
    required_tables = _required_tables_for_rule(rule_id)
    completeness = _completeness_for_trace(
        bundle_result=bundle_result,
        metric_collection=metric_collection,
        diagnostic_report=diagnostic_report,
        required_tables=required_tables,
        root_available=result is not None,
    )
    return graph.to_trace(
        root_node_id=root_node_id,
        generated_at=generated_at,
        source_fingerprint=bundle_result.fingerprint,
        synthetic=_is_synthetic(bundle_result),
        completeness=completeness,
        warnings=warnings,
    )


def build_evidence_pack_trace(
    evidence_pack: EvidencePack,
    diagnostic_report: DiagnosticReport | None = None,
    *,
    root: str | None = None,
    clock: Clock = utc_now,
) -> ProvenanceTrace:
    """Build an EvidencePack-rooted trace when the source bundle is unavailable."""

    generated_at = clock()
    graph = TraceGraph()
    warnings = [
        "EvidencePack-only traces cannot inspect source rows or canonical records unless the "
        "original run bundle is also available."
    ]
    pack_node_id = _add_evidence_pack_context(graph, evidence_pack)
    if diagnostic_report is not None:
        report_node_id = _add_diagnostic_report_node(graph, diagnostic_report)
        graph.add_edge(report_node_id, pack_node_id, ProvenanceRelation.GENERATED_FROM)
    root_node_id = root or pack_node_id
    completeness = _evidence_only_completeness(diagnostic_report=diagnostic_report)
    return graph.to_trace(
        root_node_id=root_node_id,
        generated_at=generated_at,
        source_fingerprint=evidence_pack.source_bundle_fingerprint,
        synthetic=evidence_pack.synthetic,
        completeness=completeness,
        warnings=warnings,
    )


def build_evidence_rule_trace(
    rule_id: str,
    evidence_pack: EvidencePack,
    diagnostic_report: DiagnosticReport,
    *,
    clock: Clock = utc_now,
) -> ProvenanceTrace:
    """Build a rule trace from an EvidencePack without source bundle access."""

    generated_at = clock()
    graph = TraceGraph()
    warnings = [
        "EvidencePack-only diagnostic traces show metric evidence and explicit missing source-row "
        "links; they do not reconstruct canonical records."
    ]
    pack_node_id = _add_evidence_pack_context(graph, evidence_pack)
    report_node_id = _add_diagnostic_report_node(graph, diagnostic_report)
    graph.add_edge(report_node_id, pack_node_id, ProvenanceRelation.GENERATED_FROM)
    result = next((item for item in diagnostic_report.results if item.rule_id == rule_id), None)
    if result is None:
        root_node_id = f"unavailable:rule:{rule_id}"
        graph.add_node(
            _node(
                root_node_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                f"Rule {rule_id}",
                status=ProvenanceStatus.UNAVAILABLE,
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(
            report_node_id,
            root_node_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
    else:
        root_node_id = _add_evidence_rule_result_lineage(
            graph,
            result,
            evidence_pack,
            diagnostic_report,
            parent_node_id=report_node_id,
        )
    completeness = _evidence_only_completeness(diagnostic_report=diagnostic_report)
    return graph.to_trace(
        root_node_id=root_node_id,
        generated_at=generated_at,
        source_fingerprint=evidence_pack.source_bundle_fingerprint,
        synthetic=evidence_pack.synthetic,
        completeness=completeness,
        warnings=warnings,
    )


def _add_run_context(
    graph: TraceGraph,
    bundle_result: BundleValidationResult,
    evidence_pack: EvidencePack | None,
) -> str:
    manifest = bundle_result.manifest
    synthetic = _is_synthetic(bundle_result)
    bundle_id = manifest.bundle.bundle_id if manifest is not None else "unknown"
    run_id = (
        manifest.run.run_id if manifest is not None else bundle_result.report.run_id or "unknown"
    )
    bundle_node_id = f"bundle:{bundle_id}"
    manifest_node_id = f"manifest:{bundle_id}"
    run_node_id = f"run:{run_id}"
    graph.add_node(
        _node(
            bundle_node_id,
            ProvenanceNodeType.BUNDLE,
            f"Bundle {bundle_id}",
            attributes={
                "bundle_id": bundle_id,
                "source": manifest.bundle.source if manifest is not None else None,
            },
            synthetic=synthetic,
        )
    )
    graph.add_node(
        _node(
            manifest_node_id,
            ProvenanceNodeType.MANIFEST,
            "manifest.yaml",
            attributes={
                "schema_version": manifest.schema_version if manifest is not None else None,
                "producer": manifest.provenance.producer if manifest is not None else None,
            },
            synthetic=synthetic,
        )
    )
    graph.add_edge(bundle_node_id, manifest_node_id, ProvenanceRelation.CONTAINS)
    if bundle_result.fingerprint is not None:
        fingerprint_node_id = f"fingerprint:{bundle_result.fingerprint}"
        graph.add_node(
            _node(
                fingerprint_node_id,
                ProvenanceNodeType.FINGERPRINT,
                "Bundle fingerprint",
                attributes={"sha256": bundle_result.fingerprint},
                synthetic=synthetic,
            )
        )
        graph.add_edge(bundle_node_id, fingerprint_node_id, ProvenanceRelation.IDENTIFIED_BY)
    graph.add_node(
        _node(
            run_node_id,
            ProvenanceNodeType.RUN,
            f"Run {run_id}",
            attributes=_run_attributes(manifest),
            synthetic=synthetic,
        )
    )
    graph.add_edge(manifest_node_id, run_node_id, ProvenanceRelation.CONTAINS)
    if manifest is not None:
        experiment_node_id = f"experiment:{manifest.run.experiment_id}"
        seed_node_id = f"seed:{manifest.run.seed_id}"
        environment_node_id = f"environment:{manifest.environment.name}"
        checkpoint_node_id = f"checkpoint:{manifest.run.checkpoint or 'none'}"
        graph.add_node(
            _node(
                experiment_node_id,
                ProvenanceNodeType.EXPERIMENT,
                f"Experiment {manifest.run.experiment_id}",
                attributes={"experiment_id": manifest.run.experiment_id},
                synthetic=synthetic,
            )
        )
        graph.add_node(
            _node(
                seed_node_id,
                ProvenanceNodeType.SCENARIO_SEED,
                f"Seed {manifest.run.seed_id}",
                attributes=_seed_attributes(bundle_result),
                synthetic=synthetic,
            )
        )
        graph.add_node(
            _node(
                environment_node_id,
                ProvenanceNodeType.ENVIRONMENT,
                f"Environment {manifest.environment.name}",
                attributes=manifest.environment.model_dump(mode="json"),
                synthetic=synthetic,
            )
        )
        graph.add_node(
            _node(
                checkpoint_node_id,
                ProvenanceNodeType.CHECKPOINT,
                manifest.run.checkpoint or "No checkpoint declared",
                attributes={
                    "algorithm": manifest.run.algorithm,
                    "checkpoint": manifest.run.checkpoint,
                },
                synthetic=synthetic,
            )
        )
        graph.add_edge(run_node_id, experiment_node_id, ProvenanceRelation.BELONGS_TO)
        graph.add_edge(run_node_id, seed_node_id, ProvenanceRelation.CONFIGURED_BY)
        graph.add_edge(run_node_id, environment_node_id, ProvenanceRelation.EXECUTED_WITH)
        graph.add_edge(run_node_id, checkpoint_node_id, ProvenanceRelation.EXECUTED_WITH)
    if evidence_pack is not None:
        pack_node_id = f"evidence_pack:{evidence_pack.pack_id}"
        graph.add_node(
            _node(
                pack_node_id,
                ProvenanceNodeType.EVIDENCE_PACK,
                f"EvidencePack {evidence_pack.pack_id}",
                attributes={
                    "schema_version": evidence_pack.schema_version,
                    "fingerprint": evidence_pack.fingerprint(),
                    "metric_version": evidence_pack.metric_collection.metric_version,
                },
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(pack_node_id, run_node_id, ProvenanceRelation.GENERATED_FROM)
    _add_validation_nodes(graph, bundle_result, bundle_node_id)
    return run_node_id


def _add_evidence_pack_context(graph: TraceGraph, evidence_pack: EvidencePack) -> str:
    run_id = str(evidence_pack.run_context.get("run_id") or evidence_pack.metric_collection.run_id)
    pack_node_id = f"evidence_pack:{evidence_pack.pack_id}"
    run_node_id = f"run:{run_id}"
    graph.add_node(
        _node(
            pack_node_id,
            ProvenanceNodeType.EVIDENCE_PACK,
            f"EvidencePack {evidence_pack.pack_id}",
            attributes={
                "schema_version": evidence_pack.schema_version,
                "fingerprint": evidence_pack.fingerprint(),
                "metric_version": evidence_pack.metric_collection.metric_version,
                "source_bundle_fingerprint": evidence_pack.source_bundle_fingerprint,
            },
            synthetic=evidence_pack.synthetic,
        )
    )
    graph.add_node(
        _node(
            run_node_id,
            ProvenanceNodeType.RUN,
            f"Run {run_id}",
            attributes=dict(evidence_pack.run_context),
            synthetic=evidence_pack.synthetic,
        )
    )
    graph.add_edge(pack_node_id, run_node_id, ProvenanceRelation.GENERATED_FROM)
    experiment_id = evidence_pack.run_context.get("experiment_id")
    seed_id = evidence_pack.run_context.get("seed_id")
    environment = evidence_pack.run_context.get("environment")
    if isinstance(experiment_id, str):
        experiment_node_id = f"experiment:{experiment_id}"
        graph.add_node(
            _node(
                experiment_node_id,
                ProvenanceNodeType.EXPERIMENT,
                f"Experiment {experiment_id}",
                attributes={"experiment_id": experiment_id},
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(run_node_id, experiment_node_id, ProvenanceRelation.BELONGS_TO)
    if isinstance(seed_id, str):
        seed_node_id = f"seed:{seed_id}"
        graph.add_node(
            _node(
                seed_node_id,
                ProvenanceNodeType.SCENARIO_SEED,
                f"Seed {seed_id}",
                status=ProvenanceStatus.PARTIAL,
                attributes={"seed_id": seed_id},
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(run_node_id, seed_node_id, ProvenanceRelation.CONFIGURED_BY)
    if isinstance(environment, str):
        environment_node_id = f"environment:{environment}"
        graph.add_node(
            _node(
                environment_node_id,
                ProvenanceNodeType.ENVIRONMENT,
                f"Environment {environment}",
                attributes={
                    "name": environment,
                    "version": evidence_pack.run_context.get("environment_version"),
                    "commit": evidence_pack.run_context.get("environment_commit"),
                },
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(run_node_id, environment_node_id, ProvenanceRelation.EXECUTED_WITH)
    if evidence_pack.source_bundle_fingerprint is not None:
        fingerprint_node_id = f"fingerprint:{evidence_pack.source_bundle_fingerprint}"
        graph.add_node(
            _node(
                fingerprint_node_id,
                ProvenanceNodeType.FINGERPRINT,
                "Source bundle fingerprint",
                attributes={"sha256": evidence_pack.source_bundle_fingerprint},
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(pack_node_id, fingerprint_node_id, ProvenanceRelation.IDENTIFIED_BY)
    return pack_node_id


def _add_metric_collection_summary(
    graph: TraceGraph,
    run_node_id: str,
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection,
    *,
    sample_limit: int,
    warnings: list[str],
) -> None:
    keys = [
        "task.completion.rate",
        "infra.utilisation.p95",
        "trip.duration.p95_s",
    ]
    for key in keys:
        if key in metric_collection.by_key():
            _add_metric_lineage(
                graph,
                key,
                bundle_result,
                metric_collection,
                parent_node_id=run_node_id,
                parent_relation=ProvenanceRelation.CONTAINS,
                sample_limit=sample_limit,
                warnings=warnings,
            )


def _add_metric_lineage(
    graph: TraceGraph,
    metric_key: str,
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection,
    *,
    parent_node_id: str | None,
    parent_relation: ProvenanceRelation | None,
    sample_limit: int,
    warnings: list[str],
) -> str:
    by_key = metric_collection.by_key()
    metric = by_key.get(metric_key)
    definition = metric_catalogue().get(metric_key)
    synthetic = _is_synthetic(bundle_result)
    run_id = metric_collection.run_id
    metric_node_id = f"metric_result:{run_id}:{metric_key}"
    status = _metric_node_status(metric)
    graph.add_node(
        _node(
            metric_node_id,
            ProvenanceNodeType.METRIC_RESULT,
            metric_key,
            description=definition.description if definition is not None else "Metric result",
            status=status,
            attributes=_metric_attributes(metric, definition),
            synthetic=metric.synthetic if metric is not None else synthetic,
        )
    )
    if parent_node_id is not None and parent_relation is not None:
        graph.add_edge(parent_node_id, metric_node_id, parent_relation)
    evidence_key_node_id = f"evidence_key:{metric_key}"
    graph.add_node(
        _node(
            evidence_key_node_id,
            ProvenanceNodeType.EVIDENCE_KEY,
            metric_key,
            attributes={"metric_key": metric_key},
            synthetic=synthetic,
        )
    )
    graph.add_edge(evidence_key_node_id, metric_node_id, ProvenanceRelation.CITES)
    if definition is None:
        unavailable_id = f"unavailable:metric_definition:{metric_key}"
        graph.add_node(
            _node(
                unavailable_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                f"Metric definition {metric_key}",
                status=ProvenanceStatus.UNAVAILABLE,
                description="Metric key is not registered in the metric catalogue.",
                synthetic=synthetic,
            )
        )
        graph.add_edge(
            metric_node_id,
            unavailable_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
        return metric_node_id
    definition_node_id = _add_metric_definition_node(graph, definition, synthetic=synthetic)
    graph.add_edge(metric_node_id, definition_node_id, ProvenanceRelation.DEFINED_BY)
    if metric is None or metric.status in {MetricStatus.UNAVAILABLE, MetricStatus.INVALID}:
        _add_metric_missing_evidence_nodes(
            graph, metric_node_id, metric, definition, synthetic=synthetic
        )
    for table_name in definition.required_tables:
        _add_table_lineage(
            graph,
            metric_node_id,
            table_name,
            bundle_result,
            definition,
            sample_limit=sample_limit,
            warnings=warnings,
        )
    return metric_node_id


def _add_table_lineage(
    graph: TraceGraph,
    metric_node_id: str,
    table_name: str,
    bundle_result: BundleValidationResult,
    definition: MetricDefinition,
    *,
    sample_limit: int,
    warnings: list[str],
) -> None:
    records = _records_for_table(bundle_result.canonical, table_name)
    synthetic = _is_synthetic(bundle_result)
    table_node_id = f"canonical_table:{table_name}"
    status = ProvenanceStatus.AVAILABLE if records else ProvenanceStatus.UNAVAILABLE
    graph.add_node(
        _node(
            table_node_id,
            ProvenanceNodeType.CANONICAL_TABLE,
            f"Canonical {table_name}",
            status=status,
            description="Canonical table eligible as metric input.",
            attributes={
                "table": table_name,
                "record_count": len(records),
                "required_fields": definition.required_fields.get(table_name, []),
                "aggregate_trace_policy": (
                    "Rows are eligible inputs to aggregate computation; no per-row causal "
                    "contribution weights are assigned."
                ),
            },
            synthetic=synthetic,
        )
    )
    confidence = ReferenceConfidence.EXACT if records else ReferenceConfidence.UNAVAILABLE
    graph.add_edge(
        metric_node_id,
        table_node_id,
        ProvenanceRelation.COMPUTED_FROM,
        confidence=confidence,
    )
    if not records:
        unavailable_id = f"unavailable:canonical_table:{table_name}"
        graph.add_node(
            _node(
                unavailable_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                f"No {table_name} records",
                status=ProvenanceStatus.UNAVAILABLE,
                synthetic=synthetic,
            )
        )
        graph.add_edge(
            table_node_id,
            unavailable_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
        return
    if len(records) > sample_limit:
        warnings.append(
            f"{table_name} trace shows {sample_limit} of {len(records)} eligible canonical records."
        )
    for index, record in enumerate(records[:sample_limit]):
        _add_record_lineage(graph, table_node_id, table_name, index, record, bundle_result)


def _add_record_lineage(
    graph: TraceGraph,
    table_node_id: str,
    table_name: str,
    index: int,
    record: CanonicalRecord,
    bundle_result: BundleValidationResult,
) -> None:
    synthetic = _is_synthetic(bundle_result)
    record_node_id = f"canonical_record:{table_name}:{index}"
    graph.add_node(
        _node(
            record_node_id,
            ProvenanceNodeType.CANONICAL_RECORD,
            f"{table_name} record {index}",
            attributes={
                "record_index": index,
                "table": table_name,
                "values": record.model_dump(mode="json"),
            },
            synthetic=synthetic,
            source_reference=SourceReference(
                bundle_reference=_bundle_reference(bundle_result),
                file=record.source_file,
                row=record.source_row,
            ),
        )
    )
    graph.add_edge(table_node_id, record_node_id, ProvenanceRelation.CONTAINS)
    source_file_node_id = _add_source_file_node(graph, bundle_result, record.source_file)
    source_row_node_id = f"source_row:{record.source_file}:{record.source_row}"
    graph.add_node(
        _node(
            source_row_node_id,
            ProvenanceNodeType.SOURCE_ROW,
            f"{record.source_file}:{record.source_row}",
            attributes={"file": record.source_file, "row": record.source_row},
            synthetic=synthetic,
            source_reference=SourceReference(
                bundle_reference=_bundle_reference(bundle_result),
                file=record.source_file,
                row=record.source_row,
            ),
        )
    )
    graph.add_edge(record_node_id, source_row_node_id, ProvenanceRelation.CANONICALISED_FROM)
    graph.add_edge(source_row_node_id, source_file_node_id, ProvenanceRelation.LOCATED_IN)
    for finding in _findings_for_row(bundle_result, record.source_file, record.source_row):
        finding_node_id = _add_validation_finding_node(graph, finding, synthetic=synthetic)
        graph.add_edge(record_node_id, finding_node_id, ProvenanceRelation.VALIDATED_BY)


def _add_rule_result_lineage(
    graph: TraceGraph,
    result: RuleResult,
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection,
    diagnostic_report: DiagnosticReport,
    *,
    parent_node_id: str,
    sample_limit: int,
    warnings: list[str],
) -> str:
    rule_node_id = f"rule_result:{result.rule_id}"
    graph.add_node(
        _node(
            rule_node_id,
            ProvenanceNodeType.RULE_RESULT,
            f"{result.rule_id}: {result.title}",
            status=_rule_node_status(result),
            description=result.hypothesis,
            attributes={
                "rule_id": result.rule_id,
                "rule_version": result.rule_version,
                "status": result.status.value,
                "hypothesis": result.hypothesis,
                "confidence": result.confidence.value,
                "confidence_basis": list(result.confidence_basis),
                "missing_evidence": list(result.missing_evidence),
                "alternative_explanations": list(result.alternative_explanations),
                "recommendations": [
                    recommendation.model_dump(mode="json")
                    for recommendation in result.recommendations
                ],
                "limitations": list(result.limitations),
                "rule_config": _rule_config_for_result(diagnostic_report, result.rule_id),
            },
            synthetic=result.synthetic,
        )
    )
    graph.add_edge(parent_node_id, rule_node_id, ProvenanceRelation.CONTAINS)
    definition = rule_catalogue().get(result.rule_id)
    if definition is not None:
        _add_rule_definition_reference(graph, rule_node_id, definition, synthetic=result.synthetic)
    for finding in result.findings:
        _add_finding_lineage(
            graph,
            rule_node_id,
            finding,
            bundle_result,
            metric_collection,
            sample_limit=sample_limit,
            warnings=warnings,
            synthetic=result.synthetic,
        )
    for missing in result.missing_evidence:
        missing_node_id = f"unavailable:rule:{result.rule_id}:{missing}"
        graph.add_node(
            _node(
                missing_node_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                missing,
                status=ProvenanceStatus.UNAVAILABLE,
                description="Rule reported this evidence as missing.",
                attributes={"missing_evidence": missing},
                synthetic=result.synthetic,
            )
        )
        graph.add_edge(
            rule_node_id,
            missing_node_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
    return rule_node_id


def _add_evidence_rule_result_lineage(
    graph: TraceGraph,
    result: RuleResult,
    evidence_pack: EvidencePack,
    diagnostic_report: DiagnosticReport,
    *,
    parent_node_id: str,
) -> str:
    rule_node_id = f"rule_result:{result.rule_id}"
    graph.add_node(
        _node(
            rule_node_id,
            ProvenanceNodeType.RULE_RESULT,
            f"{result.rule_id}: {result.title}",
            status=_rule_node_status(result),
            description=result.hypothesis,
            attributes={
                "rule_id": result.rule_id,
                "rule_version": result.rule_version,
                "status": result.status.value,
                "hypothesis": result.hypothesis,
                "confidence": result.confidence.value,
                "confidence_basis": list(result.confidence_basis),
                "missing_evidence": list(result.missing_evidence),
                "alternative_explanations": list(result.alternative_explanations),
                "recommendations": [
                    recommendation.model_dump(mode="json")
                    for recommendation in result.recommendations
                ],
                "limitations": list(result.limitations),
                "rule_config": _rule_config_for_result(diagnostic_report, result.rule_id),
            },
            synthetic=result.synthetic,
        )
    )
    graph.add_edge(parent_node_id, rule_node_id, ProvenanceRelation.CONTAINS)
    definition = rule_catalogue().get(result.rule_id)
    if definition is not None:
        _add_rule_definition_reference(graph, rule_node_id, definition, synthetic=result.synthetic)
    for finding in result.findings:
        _add_evidence_only_finding_lineage(graph, rule_node_id, finding, evidence_pack)
    for missing in result.missing_evidence:
        missing_node_id = f"unavailable:rule:{result.rule_id}:{missing}"
        graph.add_node(
            _node(
                missing_node_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                missing,
                status=ProvenanceStatus.UNAVAILABLE,
                description="Rule reported this evidence as missing.",
                synthetic=result.synthetic,
            )
        )
        graph.add_edge(
            rule_node_id,
            missing_node_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
    return rule_node_id


def _add_finding_lineage(
    graph: TraceGraph,
    rule_node_id: str,
    finding: Finding,
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection,
    *,
    sample_limit: int,
    warnings: list[str],
    synthetic: bool,
) -> None:
    finding_node_id = f"finding:{finding.finding_id}"
    graph.add_node(
        _node(
            finding_node_id,
            ProvenanceNodeType.FINDING,
            finding.finding_id,
            description=finding.statement,
            attributes={
                "statement": finding.statement,
                "observed_values": finding.observed_values,
                "expected_condition": finding.expected_condition,
                "support": finding.support.value,
            },
            synthetic=synthetic,
        )
    )
    graph.add_edge(rule_node_id, finding_node_id, ProvenanceRelation.CONTAINS)
    relation = _relation_for_finding_support(finding.support)
    for evidence_key in finding.evidence_keys:
        evidence_node_id = f"evidence_key:{evidence_key}"
        if not graph.has_node(evidence_node_id):
            graph.add_node(
                _node(
                    evidence_node_id,
                    ProvenanceNodeType.EVIDENCE_KEY,
                    evidence_key,
                    attributes={"metric_key": evidence_key},
                    synthetic=synthetic,
                )
            )
        graph.add_edge(finding_node_id, evidence_node_id, relation)
        metric_node_id = _add_metric_lineage(
            graph,
            evidence_key,
            bundle_result,
            metric_collection,
            parent_node_id=evidence_node_id,
            parent_relation=ProvenanceRelation.CITES,
            sample_limit=sample_limit,
            warnings=warnings,
        )
        if relation in {ProvenanceRelation.SUPPORTS, ProvenanceRelation.CONTRADICTS}:
            graph.add_edge(finding_node_id, metric_node_id, relation)


def _add_evidence_only_finding_lineage(
    graph: TraceGraph,
    rule_node_id: str,
    finding: Finding,
    evidence_pack: EvidencePack,
) -> None:
    finding_node_id = f"finding:{finding.finding_id}"
    graph.add_node(
        _node(
            finding_node_id,
            ProvenanceNodeType.FINDING,
            finding.finding_id,
            description=finding.statement,
            attributes={
                "statement": finding.statement,
                "observed_values": finding.observed_values,
                "expected_condition": finding.expected_condition,
                "support": finding.support.value,
            },
            synthetic=evidence_pack.synthetic,
        )
    )
    graph.add_edge(rule_node_id, finding_node_id, ProvenanceRelation.CONTAINS)
    relation = _relation_for_finding_support(finding.support)
    for evidence_key in finding.evidence_keys:
        evidence_node_id = f"evidence_key:{evidence_key}"
        if not graph.has_node(evidence_node_id):
            graph.add_node(
                _node(
                    evidence_node_id,
                    ProvenanceNodeType.EVIDENCE_KEY,
                    evidence_key,
                    attributes={"metric_key": evidence_key},
                    synthetic=evidence_pack.synthetic,
                )
            )
        graph.add_edge(finding_node_id, evidence_node_id, relation)
        metric_node_id = _add_evidence_metric_lineage(graph, evidence_key, evidence_pack)
        graph.add_edge(evidence_node_id, metric_node_id, ProvenanceRelation.CITES)
        if relation in {ProvenanceRelation.SUPPORTS, ProvenanceRelation.CONTRADICTS}:
            graph.add_edge(finding_node_id, metric_node_id, relation)


def _add_evidence_metric_lineage(
    graph: TraceGraph,
    metric_key: str,
    evidence_pack: EvidencePack,
) -> str:
    metric = evidence_pack.metric_collection.by_key().get(metric_key)
    definition = metric_catalogue().get(metric_key)
    metric_node_id = f"metric_result:{evidence_pack.metric_collection.run_id}:{metric_key}"
    graph.add_node(
        _node(
            metric_node_id,
            ProvenanceNodeType.METRIC_RESULT,
            metric_key,
            description=definition.description if definition is not None else "Metric result",
            status=_metric_node_status(metric),
            attributes=_metric_attributes(metric, definition),
            synthetic=evidence_pack.synthetic,
        )
    )
    if definition is None:
        unavailable_id = f"unavailable:metric_definition:{metric_key}"
        graph.add_node(
            _node(
                unavailable_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                f"Metric definition {metric_key}",
                status=ProvenanceStatus.UNAVAILABLE,
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(
            metric_node_id,
            unavailable_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
        return metric_node_id
    definition_node_id = _add_metric_definition_node(
        graph,
        definition,
        synthetic=evidence_pack.synthetic,
    )
    graph.add_edge(metric_node_id, definition_node_id, ProvenanceRelation.DEFINED_BY)
    for table_name in definition.required_tables:
        table_node_id = f"canonical_table:{table_name}"
        graph.add_node(
            _node(
                table_node_id,
                ProvenanceNodeType.CANONICAL_TABLE,
                f"Canonical {table_name}",
                status=ProvenanceStatus.UNAVAILABLE,
                description="Canonical records are unavailable in an EvidencePack-only trace.",
                attributes={
                    "table": table_name,
                    "record_count": None,
                    "required_fields": definition.required_fields.get(table_name, []),
                },
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(
            metric_node_id,
            table_node_id,
            ProvenanceRelation.COMPUTED_FROM,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
        unavailable_id = f"unavailable:evidence_only_source:{table_name}"
        graph.add_node(
            _node(
                unavailable_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                f"Source rows for {table_name}",
                status=ProvenanceStatus.UNAVAILABLE,
                description="The original run bundle is required for source-row inspection.",
                synthetic=evidence_pack.synthetic,
            )
        )
        graph.add_edge(
            table_node_id,
            unavailable_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
    return metric_node_id


def _add_metric_definition_node(
    graph: TraceGraph,
    definition: MetricDefinition,
    *,
    synthetic: bool,
) -> str:
    node_id = f"metric_definition:{definition.key}"
    graph.add_node(
        _node(
            node_id,
            ProvenanceNodeType.METRIC_DEFINITION,
            definition.key,
            description=definition.description,
            attributes=definition.model_dump(mode="json"),
            synthetic=synthetic,
        )
    )
    return node_id


def _add_metric_missing_evidence_nodes(
    graph: TraceGraph,
    metric_node_id: str,
    metric: MetricValue | None,
    definition: MetricDefinition,
    *,
    synthetic: bool,
) -> None:
    missing = metric.missing_evidence if metric is not None else definition.required_tables
    reason_codes = [reason.value for reason in metric.reason_codes] if metric is not None else []
    if not missing and not reason_codes:
        missing = ["metric result unavailable"]
    for item in [*missing, *reason_codes]:
        node_id = f"unavailable:metric:{definition.key}:{item}"
        graph.add_node(
            _node(
                node_id,
                ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                item,
                status=ProvenanceStatus.UNAVAILABLE,
                attributes={"metric_key": definition.key, "reason": item},
                synthetic=synthetic,
            )
        )
        graph.add_edge(
            metric_node_id,
            node_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )


def _add_source_file_node(
    graph: TraceGraph,
    bundle_result: BundleValidationResult,
    source_file: str,
) -> str:
    node_id = f"source_file:{source_file}"
    declaration = _declaration_for_file(bundle_result.manifest, source_file)
    graph.add_node(
        _node(
            node_id,
            ProvenanceNodeType.SOURCE_FILE,
            source_file,
            attributes={
                "path": source_file,
                "declared": declaration is not None,
                "schema_version": declaration.schema_version if declaration is not None else None,
                "required_columns": declaration.required_columns if declaration is not None else [],
                "units": declaration.units if declaration is not None else {},
            },
            synthetic=_is_synthetic(bundle_result),
            source_reference=SourceReference(
                bundle_reference=_bundle_reference(bundle_result),
                file=source_file,
            ),
        )
    )
    for finding in _findings_for_file(bundle_result, source_file):
        finding_node_id = _add_validation_finding_node(
            graph,
            finding,
            synthetic=_is_synthetic(bundle_result),
        )
        graph.add_edge(node_id, finding_node_id, ProvenanceRelation.VALIDATED_BY)
    return node_id


def _add_validation_nodes(
    graph: TraceGraph,
    bundle_result: BundleValidationResult,
    bundle_node_id: str,
) -> None:
    for finding in bundle_result.report.findings:
        if finding.file is None:
            finding_node_id = _add_validation_finding_node(
                graph,
                finding,
                synthetic=_is_synthetic(bundle_result),
            )
            graph.add_edge(bundle_node_id, finding_node_id, ProvenanceRelation.VALIDATED_BY)


def _add_validation_finding_node(
    graph: TraceGraph,
    finding: ValidationFinding,
    *,
    synthetic: bool,
) -> str:
    node_id = _validation_finding_id(finding)
    graph.add_node(
        _node(
            node_id,
            ProvenanceNodeType.VALIDATION_FINDING,
            finding.code.value,
            description=finding.message,
            attributes=finding.model_dump(mode="json"),
            synthetic=synthetic,
            source_reference=SourceReference(
                file=finding.file,
                row=finding.row,
                field=finding.field,
            ),
        )
    )
    return node_id


def _add_diagnostic_report_node(graph: TraceGraph, report: DiagnosticReport) -> str:
    node_id = f"diagnostic_report:{report.report_id}"
    graph.add_node(
        _node(
            node_id,
            ProvenanceNodeType.DIAGNOSTIC_REPORT,
            f"DiagnosticReport {report.report_id}",
            attributes={
                "schema_version": report.schema_version,
                "evidence_pack_id": report.evidence_pack_id,
                "ruleset_version": report.ruleset_version,
                "overall_readiness": report.overall_readiness.value,
                "triggered_rule_ids": list(report.triggered_rule_ids),
                "insufficient_rule_ids": list(report.insufficient_rule_ids),
                "conflicting_rule_ids": list(report.conflicting_rule_ids),
            },
            synthetic=report.synthetic,
        )
    )
    return node_id


def _add_rule_definition_reference(
    graph: TraceGraph,
    rule_node_id: str,
    definition: RuleDefinition,
    *,
    synthetic: bool,
) -> None:
    definition_node_id = f"rule_definition:{definition.rule_id}"
    graph.add_node(
        _node(
            definition_node_id,
            ProvenanceNodeType.RULE_DEFINITION,
            f"{definition.rule_id} dependencies",
            description=definition.purpose,
            attributes=definition.model_dump(mode="json"),
            synthetic=synthetic,
        )
    )
    graph.add_edge(rule_node_id, definition_node_id, ProvenanceRelation.DEFINED_BY)


def _node(
    node_id: str,
    node_type: ProvenanceNodeType,
    label: str,
    *,
    description: str | None = None,
    status: ProvenanceStatus = ProvenanceStatus.AVAILABLE,
    attributes: dict[str, JsonValue] | None = None,
    synthetic: bool = False,
    source_reference: SourceReference | None = None,
) -> ProvenanceNode:
    return ProvenanceNode(
        node_id=node_id,
        node_type=node_type,
        label=label,
        description=description,
        status=status,
        attributes=attributes or {},
        synthetic=synthetic,
        source_reference=source_reference,
    )


def _run_attributes(manifest: BundleManifest | None) -> dict[str, JsonValue]:
    if manifest is None:
        return {}
    return {
        "run_id": manifest.run.run_id,
        "experiment_id": manifest.run.experiment_id,
        "seed_id": manifest.run.seed_id,
        "algorithm": manifest.run.algorithm,
        "checkpoint": manifest.run.checkpoint,
        "random_seed": manifest.run.random_seed,
        "execution_mode": manifest.run.execution_mode.value,
        "environment_name": manifest.environment.name,
        "environment_version": manifest.environment.version,
        "environment_commit": manifest.environment.commit,
    }


def _seed_attributes(bundle_result: BundleValidationResult) -> dict[str, JsonValue]:
    if bundle_result.seed is None:
        return {"seed_id": bundle_result.manifest.run.seed_id if bundle_result.manifest else None}
    seed = bundle_result.seed
    return {
        "seed_id": seed.seed_id,
        "name": seed.name,
        "schema_version": seed.schema_version,
        "compare_against": seed.compare_against,
    }


def _metric_attributes(
    metric: MetricValue | None,
    definition: MetricDefinition | None,
) -> dict[str, JsonValue]:
    if metric is None:
        return {
            "status": ProvenanceStatus.UNAVAILABLE.value,
            "definition_known": definition is not None,
        }
    return {
        "metric_key": metric.metric_key,
        "status": metric.status.value,
        "value": metric.value,
        "unit": metric.unit,
        "scope": metric.scope,
        "dimensions": metric.dimensions,
        "required_evidence": list(metric.required_evidence),
        "missing_evidence": list(metric.missing_evidence),
        "reason_codes": [reason.value for reason in metric.reason_codes],
        "warnings": list(metric.warnings),
        "implementation_version": metric.implementation_version,
        "run_id": metric.run_id,
        "experiment_id": metric.experiment_id,
        "seed_id": metric.seed_id,
        "algorithm": metric.algorithm,
        "checkpoint": metric.checkpoint,
        "random_seed": metric.random_seed,
        "metadata": dict(metric.metadata),
    }


def _metric_node_status(metric: MetricValue | None) -> ProvenanceStatus:
    if metric is None or metric.status is MetricStatus.UNAVAILABLE:
        return ProvenanceStatus.UNAVAILABLE
    if metric.status is MetricStatus.PARTIAL:
        return ProvenanceStatus.PARTIAL
    if metric.status is MetricStatus.INVALID:
        return ProvenanceStatus.INVALID
    return ProvenanceStatus.AVAILABLE


def _rule_node_status(result: RuleResult) -> ProvenanceStatus:
    if result.status is RuleStatus.INVALID:
        return ProvenanceStatus.INVALID
    if result.status is RuleStatus.INSUFFICIENT_EVIDENCE:
        return ProvenanceStatus.PARTIAL
    return ProvenanceStatus.AVAILABLE


def _relation_for_finding_support(support: FindingSupport) -> ProvenanceRelation:
    if support is FindingSupport.SUPPORTS:
        return ProvenanceRelation.SUPPORTS
    if support is FindingSupport.CONTRADICTS:
        return ProvenanceRelation.CONTRADICTS
    return ProvenanceRelation.CITES


def _records_for_table(tables: CanonicalTables, table_name: str) -> list[CanonicalRecord]:
    records: Iterable[CanonicalRecord]
    if table_name == "tasks":
        records = tables.tasks
    elif table_name == "infrastructure":
        records = tables.infrastructure
    elif table_name == "vehicles":
        records = tables.vehicles
    elif table_name == "traffic":
        records = tables.traffic
    elif table_name == "trips":
        records = tables.trips
    elif table_name == "incidents":
        records = tables.incidents
    else:
        records = []
    return list(records)


def _findings_for_row(
    bundle_result: BundleValidationResult,
    source_file: str,
    source_row: int,
) -> list[ValidationFinding]:
    return [
        finding
        for finding in bundle_result.report.findings
        if finding.file == source_file and finding.row == source_row
    ]


def _findings_for_file(
    bundle_result: BundleValidationResult,
    source_file: str,
) -> list[ValidationFinding]:
    return [
        finding
        for finding in bundle_result.report.findings
        if finding.file == source_file and finding.row is None
    ]


def _validation_finding_id(finding: ValidationFinding) -> str:
    parts = [
        "validation",
        finding.code.value,
        finding.file or "bundle",
        str(finding.row) if finding.row is not None else "file",
        finding.field or "none",
    ]
    return ":".join(parts)


def _declaration_for_file(
    manifest: BundleManifest | None,
    source_file: str,
) -> FileDeclaration | None:
    if manifest is None:
        return None
    for declaration in manifest.files.values():
        if declaration.path == source_file:
            return declaration
    return None


def _rule_config_for_result(report: DiagnosticReport, rule_id: str) -> JsonValue:
    key = rule_id.lower()
    config = getattr(report.rule_config, key, None)
    if isinstance(config, BaseModel):
        return config.model_dump(mode="json")
    return None


def _required_tables_for_rule(rule_id: str) -> list[str]:
    definitions = metric_catalogue()
    rule_definition = rule_catalogue().get(rule_id)
    if rule_definition is None:
        return []
    tables: set[str] = set()
    for evidence_key in rule_definition.required_evidence:
        metric_definition = definitions.get(evidence_key)
        if metric_definition is not None:
            tables.update(metric_definition.required_tables)
    return sorted(tables)


def _completeness_for_trace(
    *,
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection | None,
    diagnostic_report: DiagnosticReport | None,
    required_tables: list[str],
    root_available: bool,
) -> TraceCompletenessSummary:
    categories: dict[str, TraceCompleteness] = {}
    reasons: dict[str, list[str]] = {}
    categories["run_metadata"] = (
        TraceCompleteness.COMPLETE
        if bundle_result.manifest is not None
        else TraceCompleteness.UNAVAILABLE
    )
    categories["seed"] = (
        TraceCompleteness.COMPLETE
        if bundle_result.seed is not None
        else TraceCompleteness.UNAVAILABLE
    )
    categories["experiment"] = (
        TraceCompleteness.MINIMAL
        if bundle_result.manifest is not None
        else TraceCompleteness.UNAVAILABLE
    )
    if categories["experiment"] is TraceCompleteness.MINIMAL:
        reasons["experiment"] = ["Only manifest experiment_id is available in bundle traces."]
    categories["bundle"] = (
        TraceCompleteness.COMPLETE
        if bundle_result.fingerprint is not None
        else TraceCompleteness.UNAVAILABLE
    )
    categories["validation"] = TraceCompleteness.COMPLETE
    categories["metrics"] = (
        TraceCompleteness.COMPLETE
        if metric_collection is not None
        else TraceCompleteness.UNAVAILABLE
    )
    categories["diagnostics"] = (
        TraceCompleteness.COMPLETE
        if diagnostic_report is not None
        else TraceCompleteness.UNAVAILABLE
    )
    if required_tables:
        unavailable = [
            table
            for table in required_tables
            if not _records_for_table(bundle_result.canonical, table)
        ]
        categories["canonical_records"] = (
            TraceCompleteness.COMPLETE if not unavailable else TraceCompleteness.PARTIAL
        )
        if unavailable:
            reasons["canonical_records"] = [
                f"Unavailable canonical tables: {', '.join(unavailable)}"
            ]
    else:
        categories["canonical_records"] = TraceCompleteness.MINIMAL
        reasons["canonical_records"] = [
            "No specific canonical table was required for this trace root."
        ]
    categories["source_rows"] = TraceCompleteness.PARTIAL
    reasons["source_rows"] = [
        "Aggregate traces show bounded source-row samples and exact eligible record counts."
    ]
    if not root_available:
        categories["root"] = TraceCompleteness.UNAVAILABLE
        reasons["root"] = ["Requested trace root was not present."]
    overall = _overall_completeness(categories)
    return TraceCompletenessSummary(overall=overall, categories=categories, reasons=reasons)


def _evidence_only_completeness(
    *,
    diagnostic_report: DiagnosticReport | None,
) -> TraceCompletenessSummary:
    categories = {
        "run_metadata": TraceCompleteness.MINIMAL,
        "seed": TraceCompleteness.MINIMAL,
        "experiment": TraceCompleteness.MINIMAL,
        "bundle": TraceCompleteness.UNAVAILABLE,
        "validation": TraceCompleteness.PARTIAL,
        "canonical_records": TraceCompleteness.UNAVAILABLE,
        "metrics": TraceCompleteness.COMPLETE,
        "diagnostics": TraceCompleteness.COMPLETE
        if diagnostic_report is not None
        else TraceCompleteness.UNAVAILABLE,
        "source_rows": TraceCompleteness.UNAVAILABLE,
    }
    reasons = {
        "bundle": ["The source bundle was not provided to this trace builder."],
        "validation": ["Only the EvidencePack validation summary is available."],
        "canonical_records": ["EvidencePack-only traces do not contain canonical rows."],
        "source_rows": ["Source-row inspection requires the original run bundle."],
    }
    return TraceCompletenessSummary(
        overall=_overall_completeness(categories),
        categories=categories,
        reasons=reasons,
    )


def _overall_completeness(categories: dict[str, TraceCompleteness]) -> TraceCompleteness:
    if any(value is TraceCompleteness.INVALID for value in categories.values()):
        return TraceCompleteness.INVALID
    if any(
        value in {TraceCompleteness.PARTIAL, TraceCompleteness.UNAVAILABLE}
        for value in categories.values()
    ):
        return TraceCompleteness.PARTIAL
    if any(value is TraceCompleteness.MINIMAL for value in categories.values()):
        return TraceCompleteness.MINIMAL
    return TraceCompleteness.COMPLETE


def _is_synthetic(bundle_result: BundleValidationResult) -> bool:
    manifest = bundle_result.manifest
    if manifest is None:
        return False
    source = manifest.bundle.source.lower()
    environment = manifest.environment.name.lower()
    producer = manifest.provenance.producer.lower()
    return "synthetic" in source or "synthetic" in environment or "synthetic" in producer


def _bundle_reference(bundle_result: BundleValidationResult) -> str | None:
    if bundle_result.manifest is not None:
        return bundle_result.manifest.bundle.bundle_id
    if bundle_result.report.bundle_id is not None:
        return bundle_result.report.bundle_id
    return None
