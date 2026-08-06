"""Read-only validation of future-native VEC runner sidecars."""

from traffictwin.integration.vec_native_runner.models import (
    VEC_NATIVE_RUNNER_METHOD_VERSION,
    VEC_NATIVE_RUNNER_RESEARCH_STATUS,
    VEC_NATIVE_RUNNER_SCHEMA_VERSION,
    VecNativeFileBinding,
    VecNativeFileRole,
    VecNativeProducerKind,
    VecNativeRunnerContract,
    VecNativeRunnerManifest,
    VecNativeRunnerReport,
    VecNativeSemanticsStatus,
    VecUnavailableLifecycleSemantics,
    vec_native_runner_contract,
)
from traffictwin.integration.vec_native_runner.service import (
    MAX_NATIVE_FILE_BYTES,
    MAX_NATIVE_JSONL_LINE_BYTES,
    MAX_NATIVE_JSONL_RECORDS,
    MAX_NATIVE_MANIFEST_BYTES,
    MAX_NATIVE_TOTAL_BYTES,
    VecNativeRunnerError,
    validate_vec_native_sidecar,
)

__all__ = [
    "MAX_NATIVE_FILE_BYTES",
    "MAX_NATIVE_JSONL_LINE_BYTES",
    "MAX_NATIVE_JSONL_RECORDS",
    "MAX_NATIVE_MANIFEST_BYTES",
    "MAX_NATIVE_TOTAL_BYTES",
    "VEC_NATIVE_RUNNER_METHOD_VERSION",
    "VEC_NATIVE_RUNNER_RESEARCH_STATUS",
    "VEC_NATIVE_RUNNER_SCHEMA_VERSION",
    "VecNativeFileBinding",
    "VecNativeFileRole",
    "VecNativeProducerKind",
    "VecNativeRunnerContract",
    "VecNativeRunnerError",
    "VecNativeRunnerManifest",
    "VecNativeRunnerReport",
    "VecNativeSemanticsStatus",
    "VecUnavailableLifecycleSemantics",
    "validate_vec_native_sidecar",
    "vec_native_runner_contract",
]
