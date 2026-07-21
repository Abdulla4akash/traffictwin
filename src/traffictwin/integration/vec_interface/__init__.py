"""Thin capability-gated CLI/UI service boundary for VEC-10."""

from traffictwin.integration.vec_interface.models import (
    VecAdmissionComparison,
    VecArtifactInspection,
    VecInterfaceAvailability,
    VecInterfaceContract,
    VecInterfaceSnapshot,
    VecMetricDelta,
    VecOperationStatus,
    VecRepositorySnapshot,
    vec_interface_contract,
)
from traffictwin.integration.vec_interface.service import (
    VecInterfaceError,
    compare_vec_admissions,
    export_vec_admission,
    inspect_vec_artifact,
    inspect_vec_interface,
    load_preprocess_request,
    load_run_request,
    load_scientific_admission,
)

__all__ = [
    "VecAdmissionComparison",
    "VecArtifactInspection",
    "VecInterfaceAvailability",
    "VecInterfaceContract",
    "VecInterfaceError",
    "VecInterfaceSnapshot",
    "VecMetricDelta",
    "VecOperationStatus",
    "VecRepositorySnapshot",
    "compare_vec_admissions",
    "export_vec_admission",
    "inspect_vec_artifact",
    "inspect_vec_interface",
    "load_preprocess_request",
    "load_run_request",
    "load_scientific_admission",
    "vec_interface_contract",
]
