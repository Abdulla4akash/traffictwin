"""Read-only integration for Randy Putra's TOS Data results package.

This integration imports documented evaluation summaries and exposes selected
instrumented arrays for inspection. It does not launch the source environment
or assign semantics to the unresolved RSU arrays.
"""

from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
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
from traffictwin.integration.tos.replay import load_replay_frame, load_replay_series
from traffictwin.integration.tos.tasks import load_task_sample
from traffictwin.integration.tos.validation import inspect_tos_package, validate_tos_package

__all__ = [
    "TosEvaluationRun",
    "TosImportSummary",
    "TosPackageInventory",
    "TosReplayFrame",
    "TosReplayPoint",
    "TosSummary",
    "TosTaskObservation",
    "TosTaskSample",
    "TosValidationReport",
    "build_tos_evidence_pack",
    "build_tos_metric_trace",
    "build_tos_rule_trace",
    "import_evaluation_summaries",
    "inspect_tos_package",
    "list_instrumented_runs",
    "load_replay_frame",
    "load_replay_series",
    "load_task_sample",
    "metric_collection_from_evaluation",
    "tos_metric_catalogue",
    "package_fingerprint",
    "read_evaluation_runs",
    "read_npz_headers",
    "get_evaluation_source_row",
    "tos_data_capability_manifest",
    "validate_tos_package",
]
