"""Safe, evidence-gated VEC FCD/network preprocessing."""

from traffictwin.integration.vec_preprocessing.models import (
    PINNED_VEC_ENV_COMMIT,
    VecFcdPreflightReport,
    VecFcdPreprocessingContract,
    VecFcdPreprocessReceipt,
    VecFcdPreprocessRequest,
    VecGreedyUrbanPlacement,
    VecPreflightStatus,
    vec_fcd_preprocessing_contract,
)
from traffictwin.integration.vec_preprocessing.service import (
    VecFcdPreprocessingError,
    preflight_vec_fcd,
    preprocess_vec_fcd,
)

__all__ = [
    "PINNED_VEC_ENV_COMMIT",
    "VecFcdPreprocessReceipt",
    "VecFcdPreprocessRequest",
    "VecFcdPreflightReport",
    "VecFcdPreprocessingContract",
    "VecFcdPreprocessingError",
    "VecGreedyUrbanPlacement",
    "VecPreflightStatus",
    "preflight_vec_fcd",
    "preprocess_vec_fcd",
    "vec_fcd_preprocessing_contract",
]
