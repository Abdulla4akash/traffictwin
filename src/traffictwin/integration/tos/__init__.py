"""Read-only integration for Randy Putra's TOS Data results package.

This integration imports documented evaluation summaries and exposes selected
instrumented arrays for inspection. It does not launch the source environment
or promote source-specific RSU fields to incompatible canonical metrics.
"""

from traffictwin.integration.tos.analysis import (
    build_evaluation_matrix,
    build_generalisation_matrix,
    compare_campaigns,
    tos_analysis_catalogue,
)
from traffictwin.integration.tos.analysis_models import (
    TosCampaignComparisonReport,
    TosEvaluationMatrix,
    TosGeneralisationMatrix,
    TosReproducibilityAudit,
    TosRsuRunSummary,
    TosTaskOutcomeSummary,
    TosTraceSummary,
    TosTrainingRun,
    TosTrainingRunSummary,
)
from traffictwin.integration.tos.audit import audit_tos_package
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.integration.tos.contract import (
    TosSourceContract,
    tos_source_contract,
)
from traffictwin.integration.tos.exports import (
    TosResultsPack,
    build_static_results_atlas,
    build_tos_research_report,
    write_tos_results_pack,
)
from traffictwin.integration.tos.importer import import_evaluation_summaries
from traffictwin.integration.tos.metrics import (
    build_tos_evidence_pack,
    metric_collection_from_evaluation,
    tos_metric_catalogue,
)
from traffictwin.integration.tos.models import (
    TosEvaluationRun,
    TosImportSummary,
    TosPackageInventory,
    TosReplayFrame,
    TosReplayPoint,
    TosRsuReplayPoint,
    TosSummary,
    TosTaskObservation,
    TosTaskSample,
    TosValidationReport,
)
from traffictwin.integration.tos.provenance import (
    build_tos_metric_trace,
    build_tos_rule_trace,
    get_evaluation_source_row,
)
from traffictwin.integration.tos.readers import (
    list_instrumented_runs,
    package_fingerprint,
    read_evaluation_runs,
    read_npz_headers,
)
from traffictwin.integration.tos.replay import (
    load_replay_frame,
    load_replay_series,
    load_rsu_replay_series,
    summarise_rsu_run,
    summarise_trace,
)
from traffictwin.integration.tos.tasks import load_task_sample, summarise_task_outcomes
from traffictwin.integration.tos.training import list_training_runs, load_training_run
from traffictwin.integration.tos.validation import inspect_tos_package, validate_tos_package

__all__ = [
    "TosEvaluationRun",
    "TosEvaluationMatrix",
    "TosCampaignComparisonReport",
    "TosGeneralisationMatrix",
    "TosImportSummary",
    "TosPackageInventory",
    "TosReplayFrame",
    "TosReplayPoint",
    "TosReproducibilityAudit",
    "TosResultsPack",
    "TosRsuRunSummary",
    "TosRsuReplayPoint",
    "TosSourceContract",
    "TosSummary",
    "TosTaskObservation",
    "TosTaskSample",
    "TosTaskOutcomeSummary",
    "TosTraceSummary",
    "TosTrainingRun",
    "TosTrainingRunSummary",
    "TosValidationReport",
    "build_tos_evidence_pack",
    "build_evaluation_matrix",
    "build_generalisation_matrix",
    "build_static_results_atlas",
    "build_tos_research_report",
    "build_tos_metric_trace",
    "build_tos_rule_trace",
    "import_evaluation_summaries",
    "audit_tos_package",
    "compare_campaigns",
    "inspect_tos_package",
    "list_instrumented_runs",
    "list_training_runs",
    "load_replay_frame",
    "load_replay_series",
    "load_rsu_replay_series",
    "load_task_sample",
    "load_training_run",
    "metric_collection_from_evaluation",
    "tos_metric_catalogue",
    "package_fingerprint",
    "read_evaluation_runs",
    "read_npz_headers",
    "summarise_rsu_run",
    "summarise_task_outcomes",
    "summarise_trace",
    "tos_analysis_catalogue",
    "get_evaluation_source_row",
    "tos_data_capability_manifest",
    "tos_source_contract",
    "validate_tos_package",
    "write_tos_results_pack",
]
