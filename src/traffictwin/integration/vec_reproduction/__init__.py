"""Public VEC-08 instrumented-reproduction API."""

from traffictwin.integration.vec_reproduction.models import (
    LATENCY_STREAM_TOLERANCE,
    PINNED_CASE_ID,
    PINNED_EXPECTED_FILES,
    PINNED_TOS_DATA_COMMIT,
    SCALAR_TOLERANCE,
    VecComparisonStatus,
    VecNumericTolerance,
    VecRepeatRunEvidence,
    VecReproductionCheck,
    VecReproductionContract,
    VecReproductionGrade,
    VecReproductionReport,
    VecReproductionRequest,
    VecReproductionSource,
    VecReproductionSummary,
    vec_reproduction_contract,
)
from traffictwin.integration.vec_reproduction.service import (
    VecReproductionError,
    verify_vec_reproduction,
)

__all__ = [
    "LATENCY_STREAM_TOLERANCE",
    "PINNED_CASE_ID",
    "PINNED_EXPECTED_FILES",
    "PINNED_TOS_DATA_COMMIT",
    "SCALAR_TOLERANCE",
    "VecComparisonStatus",
    "VecNumericTolerance",
    "VecReproductionCheck",
    "VecReproductionContract",
    "VecReproductionError",
    "VecReproductionGrade",
    "VecReproductionReport",
    "VecReproductionRequest",
    "VecReproductionSource",
    "VecReproductionSummary",
    "VecRepeatRunEvidence",
    "vec_reproduction_contract",
    "verify_vec_reproduction",
]
