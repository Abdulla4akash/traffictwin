"""Aggregate-level provenance for TOS source-summary imports."""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.evidence.pack import EvidencePack
from traffictwin.integration.tos.metrics import tos_metric_catalogue
from traffictwin.integration.tos.models import TosEvaluationRun, TosValidationReport
from traffictwin.integration.tos.readers import EVALUATION_MASTER, safe_package_path
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.provenance.builder import build_evidence_rule_trace
from traffictwin.provenance.graph import TraceGraph
from traffictwin.provenance.models import (
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    ProvenanceStatus,
    ProvenanceTrace,
    ReferenceConfidence,
    SourceReference,
    SourceRow,
    SourceRowPreview,
    TraceCompleteness,
    TraceCompletenessSummary,
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def build_tos_metric_trace(
    run: TosEvaluationRun,
    metric_collection: MetricCollection,
    validation_report: TosValidationReport,
    metric_key: str,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> ProvenanceTrace:
    """Trace one source-summary metric to its exact CSV row and package context."""

    generated_at = clock()
    graph = TraceGraph()
    metric = metric_collection.by_key().get(metric_key)
    source_definitions = tos_metric_catalogue()
    definition = {**metric_catalogue(), **source_definitions}.get(metric_key)
    metric_node_id = f"metric_result:{run.run_id}:{metric_key}"
    graph.add_node(
        ProvenanceNode(
            node_id=metric_node_id,
            node_type=ProvenanceNodeType.METRIC_RESULT,
            label=metric_key,
            description=definition.description if definition is not None else None,
            status=_metric_status(metric.status if metric is not None else None),
            attributes=metric.model_dump(mode="json") if metric is not None else {},
            synthetic=False,
        )
    )
    if definition is not None:
        definition_id = f"metric_definition:{metric_key}"
        graph.add_node(
            ProvenanceNode(
                node_id=definition_id,
                node_type=ProvenanceNodeType.METRIC_DEFINITION,
                label=metric_key,
                description=definition.description,
                attributes=definition.model_dump(mode="json"),
                synthetic=False,
            )
        )
        graph.add_edge(metric_node_id, definition_id, ProvenanceRelation.DEFINED_BY)
    else:
        unavailable = f"unavailable:metric_definition:{metric_key}"
        graph.add_node(
            ProvenanceNode(
                node_id=unavailable,
                node_type=ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                label="Metric definition unavailable",
                status=ProvenanceStatus.UNAVAILABLE,
            )
        )
        graph.add_edge(
            metric_node_id,
            unavailable,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
    source_row_id = _add_source_context(graph, run, validation_report)
    if metric is not None and metric.status is MetricStatus.AVAILABLE:
        graph.add_edge(
            metric_node_id,
            source_row_id,
            ProvenanceRelation.GENERATED_FROM,
            description="Source-provided summary value was read from this evaluation CSV row.",
        )
    else:
        graph.add_edge(
            metric_node_id,
            source_row_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            description="The row lacks evidence compatible with this TrafficTwin metric.",
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
    required_canonical_tables = definition.required_tables if definition is not None else []
    if metric_key in source_definitions:
        required_canonical_tables = ["tasks"]
    _add_canonical_boundary(graph, metric_node_id, required_canonical_tables)
    return graph.to_trace(
        root_node_id=metric_node_id,
        generated_at=generated_at,
        source_fingerprint=validation_report.package_fingerprint,
        synthetic=False,
        completeness=_tos_completeness(diagnostics=False),
        warnings=[
            "This is aggregate-level provenance: the TOS evaluation master does not identify "
            "contributing canonical task rows.",
            "Source-provided summary metrics are not TrafficTwin recomputations.",
        ],
    )


def build_tos_rule_trace(
    run: TosEvaluationRun,
    evidence_pack: EvidencePack,
    diagnostic_report: DiagnosticReport,
    validation_report: TosValidationReport,
    rule_id: str,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> ProvenanceTrace:
    """Extend an EvidencePack rule trace with exact TOS summary-row provenance."""

    base = build_evidence_rule_trace(rule_id, evidence_pack, diagnostic_report, clock=clock)
    graph = TraceGraph()
    for node in base.nodes:
        graph.add_node(node)
    for edge in base.edges:
        graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            edge.relation,
            description=edge.description,
            confidence=edge.confidence,
        )
    source_row_id = _add_source_context(graph, run, validation_report)
    for node in base.nodes:
        if node.node_type is not ProvenanceNodeType.METRIC_RESULT:
            continue
        status = str(node.attributes.get("status") or "")
        graph.add_edge(
            node.node_id,
            source_row_id,
            ProvenanceRelation.GENERATED_FROM
            if status == MetricStatus.AVAILABLE.value
            else ProvenanceRelation.UNAVAILABLE_BECAUSE,
            description=(
                "Cited metric is a source-provided evaluation summary."
                if status == MetricStatus.AVAILABLE.value
                else "The evaluation row does not provide compatible evidence for this metric."
            ),
            confidence=(
                ReferenceConfidence.EXACT
                if status == MetricStatus.AVAILABLE.value
                else ReferenceConfidence.UNAVAILABLE
            ),
        )
    return graph.to_trace(
        root_node_id=base.root_node_id,
        generated_at=base.generated_at,
        source_fingerprint=validation_report.package_fingerprint,
        synthetic=False,
        completeness=_tos_completeness(diagnostics=True),
        warnings=sorted(
            {
                *base.warnings,
                "Rule lineage reaches source summary rows, not canonical per-task contributors.",
                "RSU source semantics are known, but they do not provide the canonical "
                "queue/utilisation and temporal task linkage required by infrastructure rules.",
            }
        ),
    )


def get_evaluation_source_row(
    root: str | Path,
    row_number: int,
    validation_report: TosValidationReport,
    *,
    context_rows: int = 2,
) -> SourceRowPreview:
    """Return a bounded, read-only preview of one evaluation CSV row."""

    if row_number < 2:
        raise ValueError("evaluation source row must be at least 2")
    if context_rows < 0 or context_rows > 10:
        raise ValueError("context_rows must be between 0 and 10")
    path = safe_package_path(root, EVALUATION_MASTER)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        lower = max(2, row_number - context_rows)
        upper = row_number + context_rows
        selected: dict[str, str | None] | None = None
        surrounding: list[SourceRow] = []
        for current, raw in enumerate(reader, start=2):
            if current < lower:
                continue
            if current > upper:
                break
            values = {header: raw.get(header) for header in headers}
            surrounding.append(SourceRow(row_number=current, values=values))
            if current == row_number:
                selected = values
    if selected is None:
        return SourceRowPreview(
            file=EVALUATION_MASTER.as_posix(),
            row_number=row_number,
            status=ProvenanceStatus.UNAVAILABLE,
            headers=headers,
            surrounding_rows=surrounding,
            warnings=["Requested evaluation row does not exist."],
        )
    findings = [
        item.model_dump(mode="json")
        for item in validation_report.findings
        if item.row in {None, row_number} and item.file in {None, EVALUATION_MASTER.as_posix()}
    ]
    return SourceRowPreview(
        file=EVALUATION_MASTER.as_posix(),
        row_number=row_number,
        status=ProvenanceStatus.AVAILABLE,
        headers=headers,
        raw_values=selected,
        surrounding_rows=surrounding,
        canonical_record_type=None,
        canonical_values={},
        conversions={},
        validation_findings=findings,
        inclusion_status="included_as_source_summary",
        warnings=[
            "This row contains aggregate source metrics, not a canonical task record.",
        ],
    )


def _add_source_context(
    graph: TraceGraph,
    run: TosEvaluationRun,
    report: TosValidationReport,
) -> str:
    fingerprint = report.package_fingerprint or "unavailable"
    bundle_reference = f"tos-data:{fingerprint[:12]}"
    bundle_id = f"bundle:{bundle_reference}"
    source_file_id = f"source_file:{run.source_file}"
    source_row_id = f"source_row:{run.source_file}:{run.source_row}"
    run_node_id = f"run:{run.run_id}"
    nodes = [
        ProvenanceNode(
            node_id=bundle_id,
            node_type=ProvenanceNodeType.BUNDLE,
            label="External TOS Data package",
            attributes={
                "package_commit": report.package_commit,
                "adapter_version": report.adapter_version,
                "semantics_source_commit": report.semantics_source_commit,
            },
        ),
        ProvenanceNode(
            node_id=source_file_id,
            node_type=ProvenanceNodeType.SOURCE_FILE,
            label=run.source_file,
            source_reference=SourceReference(
                bundle_reference=bundle_reference,
                file=run.source_file,
            ),
        ),
        ProvenanceNode(
            node_id=source_row_id,
            node_type=ProvenanceNodeType.SOURCE_ROW,
            label=f"{run.source_file}:{run.source_row}",
            attributes=run.model_dump(mode="json", by_alias=True),
            source_reference=SourceReference(
                bundle_reference=bundle_reference,
                file=run.source_file,
                row=run.source_row,
            ),
        ),
        ProvenanceNode(
            node_id=run_node_id,
            node_type=ProvenanceNodeType.RUN,
            label=f"Run {run.run_id}",
            attributes={
                "run_id": run.run_id,
                "experiment_id": run.experiment_id,
                "seed_id": run.seed_id,
                "algorithm": run.campaign,
                "checkpoint": run.actor,
                "random_seed": run.fleet_seed,
            },
        ),
    ]
    for node in nodes:
        if not graph.has_node(node.node_id):
            graph.add_node(node)
    graph.add_edge(source_row_id, source_file_id, ProvenanceRelation.LOCATED_IN)
    graph.add_edge(source_file_id, bundle_id, ProvenanceRelation.BELONGS_TO)
    graph.add_edge(run_node_id, source_row_id, ProvenanceRelation.GENERATED_FROM)
    _add_run_references(graph, run, run_node_id)
    if report.package_fingerprint:
        fingerprint_id = f"fingerprint:{report.package_fingerprint}"
        if not graph.has_node(fingerprint_id):
            graph.add_node(
                ProvenanceNode(
                    node_id=fingerprint_id,
                    node_type=ProvenanceNodeType.FINGERPRINT,
                    label="TOS package fingerprint",
                    attributes={"sha256": report.package_fingerprint},
                )
            )
        graph.add_edge(bundle_id, fingerprint_id, ProvenanceRelation.IDENTIFIED_BY)
    for index, finding in enumerate(report.findings):
        if finding.file not in {None, run.source_file} or finding.row not in {None, run.source_row}:
            continue
        finding_id = f"validation_finding:tos:{index}:{finding.code}"
        if not graph.has_node(finding_id):
            graph.add_node(
                ProvenanceNode(
                    node_id=finding_id,
                    node_type=ProvenanceNodeType.VALIDATION_FINDING,
                    label=finding.code,
                    description=finding.message,
                    status=(
                        ProvenanceStatus.INVALID
                        if finding.blocks_import
                        else ProvenanceStatus.PARTIAL
                    ),
                    attributes=finding.model_dump(mode="json"),
                )
            )
        graph.add_edge(source_row_id, finding_id, ProvenanceRelation.VALIDATED_BY)
    return source_row_id


def _add_run_references(graph: TraceGraph, run: TosEvaluationRun, run_node_id: str) -> None:
    references = [
        (
            f"experiment:{run.experiment_id}",
            ProvenanceNodeType.EXPERIMENT,
            f"Experiment {run.experiment_id}",
            ProvenanceStatus.AVAILABLE,
            ProvenanceRelation.BELONGS_TO,
            {"experiment_id": run.experiment_id},
        ),
        (
            f"seed:{run.seed_id}",
            ProvenanceNodeType.SCENARIO_SEED,
            f"Source scenario {run.seed_id}",
            ProvenanceStatus.PARTIAL,
            ProvenanceRelation.CONFIGURED_BY,
            {
                "seed_id": run.seed_id,
                "limitation": "No immutable TrafficTwin ScenarioSeed snapshot is present.",
            },
        ),
        (
            f"environment:{run.engine_version}",
            ProvenanceNodeType.ENVIRONMENT,
            f"Evaluation engine {run.engine_version}",
            ProvenanceStatus.PARTIAL,
            ProvenanceRelation.EXECUTED_WITH,
            {
                "version": run.engine_version,
                "commit": None,
                "limitation": "The vec_env source commit is unavailable.",
            },
        ),
        (
            f"checkpoint:{run.actor}",
            ProvenanceNodeType.CHECKPOINT,
            run.actor,
            ProvenanceStatus.PARTIAL,
            ProvenanceRelation.EXECUTED_WITH,
            {"checkpoint_reference": run.actor, "checkpoint_file_present": False},
        ),
    ]
    for node_id, node_type, label, status, relation, attributes in references:
        if not graph.has_node(node_id):
            graph.add_node(
                ProvenanceNode(
                    node_id=node_id,
                    node_type=node_type,
                    label=label,
                    status=status,
                    attributes=attributes,
                )
            )
        graph.add_edge(run_node_id, node_id, relation)
    manifest_id = "unavailable:tos:manifest"
    if not graph.has_node(manifest_id):
        graph.add_node(
            ProvenanceNode(
                node_id=manifest_id,
                node_type=ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                label="TrafficTwin bundle manifest unavailable",
                status=ProvenanceStatus.UNAVAILABLE,
                description="TOS Data is an external results package, not a standard run bundle.",
            )
        )
    graph.add_edge(
        run_node_id,
        manifest_id,
        ProvenanceRelation.UNAVAILABLE_BECAUSE,
        confidence=ReferenceConfidence.UNAVAILABLE,
    )


def _add_canonical_boundary(
    graph: TraceGraph,
    metric_node_id: str,
    required_tables: list[str],
) -> None:
    for table in required_tables:
        table_id = f"canonical_table:{table}"
        if not graph.has_node(table_id):
            graph.add_node(
                ProvenanceNode(
                    node_id=table_id,
                    node_type=ProvenanceNodeType.CANONICAL_TABLE,
                    label=f"Canonical {table}",
                    status=ProvenanceStatus.UNAVAILABLE,
                    description=(
                        "No canonical row set underlies this imported source-summary metric."
                    ),
                    attributes={"record_count": None, "table": table},
                )
            )
        graph.add_edge(
            metric_node_id,
            table_id,
            ProvenanceRelation.COMPUTED_FROM,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )
        missing_id = f"unavailable:tos:canonical:{table}"
        if not graph.has_node(missing_id):
            graph.add_node(
                ProvenanceNode(
                    node_id=missing_id,
                    node_type=ProvenanceNodeType.UNAVAILABLE_REFERENCE,
                    label=f"Canonical {table} contributors unavailable",
                    status=ProvenanceStatus.UNAVAILABLE,
                )
            )
        graph.add_edge(
            table_id,
            missing_id,
            ProvenanceRelation.UNAVAILABLE_BECAUSE,
            confidence=ReferenceConfidence.UNAVAILABLE,
        )


def _metric_status(status: MetricStatus | None) -> ProvenanceStatus:
    if status is MetricStatus.AVAILABLE:
        return ProvenanceStatus.AVAILABLE
    if status is MetricStatus.PARTIAL:
        return ProvenanceStatus.PARTIAL
    if status is MetricStatus.INVALID:
        return ProvenanceStatus.INVALID
    return ProvenanceStatus.UNAVAILABLE


def _tos_completeness(*, diagnostics: bool) -> TraceCompletenessSummary:
    categories = {
        "run_metadata": TraceCompleteness.COMPLETE,
        "seed": TraceCompleteness.PARTIAL,
        "experiment": TraceCompleteness.COMPLETE,
        "bundle": TraceCompleteness.PARTIAL,
        "validation": TraceCompleteness.COMPLETE,
        "canonical_records": TraceCompleteness.UNAVAILABLE,
        "metrics": TraceCompleteness.PARTIAL,
        "diagnostics": (
            TraceCompleteness.PARTIAL if diagnostics else TraceCompleteness.UNAVAILABLE
        ),
        "source_rows": TraceCompleteness.COMPLETE,
    }
    return TraceCompletenessSummary(
        overall=TraceCompleteness.PARTIAL,
        categories=categories,
        reasons={
            "seed": ["No immutable TrafficTwin seed snapshot is present in TOS Data."],
            "bundle": ["The source is not a standard TrafficTwin run bundle."],
            "canonical_records": [
                "Evaluation-master metrics are aggregate summaries without contributing rows."
            ],
            "metrics": ["Only compatible documented summary metrics are available."],
            "diagnostics": ["Infrastructure and trip evidence remain unavailable."],
        },
    )
